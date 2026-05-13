#!/usr/bin/env python
"""FastAPI labeling server for human-in-the-loop intent review.

Serves a single-page HTML annotation UI that walks the user through pending
SQL positions (those not yet in meta.llm_intents.final). User picks one of
the 4 model labels (or enters custom) via keyboard shortcuts; decision is
written back to meta.llm_intents.final with rule="user".

Run:
    uv run python scripts/labeling_server.py --db postgresql://... --port 8777
Open http://localhost:8777
"""

import argparse
import json
import logging
import os
import re
import sys
from collections import Counter, defaultdict
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

sys.path.insert(0, str(__file__).rsplit("/scripts/", 1)[0])

from sota_rca.runner._fallback_db import EvaluationSample
from sota_rca.analysis.intent_prompt import VALID_INTENTS
from sota_rca.analysis.llm_intent_classifier import extract_sql_rounds
from sota_rca.analysis.trajectory_normalizer import normalize_by_agent
from scripts.arbitrate_disagreements import EXPS, EXCLUDED_PAIRS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CLAUDE_OLD = "claude_opus_4_6"
CLAUDE_NEW = "claude_opus_4_6_arbiter"
GEMINI = "gemini_3_1_pro_preview"
C47 = "claude_opus_4_7_arbiter"
FINAL_KEY = "final"


# ── SQL structural fingerprint ──────────────────────────────────────────────
#
# A tuple of boolean/categorical features that captures the SYNTACTIC shape
# of an SQL query. Two SQLs with the SAME fingerprint are treated as the
# same "rule": if the user labels one, we can safely apply that label to all
# other pending cases with the identical fingerprint.

_METRIC_KW = [
    ("net",     r"%?(?:HTTP|NET|TCP|HUBBLE|DROP|LATENCY|PACKET)"),
    ("cpu_mem", r"%?(?:CPU|MEMORY|MEM|OOM|FILESYSTEM|DISK)"),
    ("jvm",     r"%?(?:JVM|GC|THREAD|QUEUE|HEAP|HIKARI)"),
    ("k8s",     r"%?(?:RESTART|KILL|PHASE|READY|TERMINAT|EVICT|DEPLOY|POD)"),
    ("db",      r"%?(?:\bDB|MYSQL|CONN)"),
]

_MESSAGE_KW = [
    ("timeout", r"TIMEOUT"),
    ("error",   r"\bERROR\b"),
    ("oom",     r"\bOOM\b|OUT\s+OF\s+MEMORY"),
    ("chaos",   r"CHAOS|FAULT"),
    ("5xx",     r"\b5\d{2}\b|STATUS.*5"),
]


def sql_fingerprint(sql: str) -> tuple:
    """Return a tuple of ~25 features describing the SQL's structural shape.

    Two SQLs with the same fingerprint are considered "same rule": a user
    decision on one is safe to propagate to others. Fingerprint excludes
    specific identifiers (service names, trace_ids, literal values) and
    focuses only on the SHAPE of the query.
    """
    u = re.sub(r"\s+", " ", sql.upper()).strip()
    # tables
    has_logs = bool(re.search(r"\b(?:ABNORMAL_|NORMAL_)?LOGS\b", u))
    has_traces = bool(re.search(r"\b(?:ABNORMAL_|NORMAL_)?TRACES\b", u))
    has_metrics = bool(re.search(r"\b(?:ABNORMAL_|NORMAL_)?METRICS(?:_SUM|_HISTOGRAM)?\b", u))
    has_ab = "ABNORMAL_" in u
    has_nm = bool(re.search(r"(?<!AB)NORMAL_", u))
    # structural
    has_self_join = bool(re.search(r"PARENT_SPAN_ID\s*=\s*\w*\.?SPAN_ID|\w*\.?SPAN_ID\s*=\s*\w*\.?PARENT_SPAN_ID", u))
    # WHERE clause
    wm = re.search(r"\bWHERE\b(.*?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|\bUNION\b|\bHAVING\b|\)|$)", u, re.DOTALL)
    where = wm.group(1) if wm else ""
    has_trace_id = bool(re.search(r"TRACE_ID\s*(=|IN)", where))
    has_svc_eq = bool(re.search(r"SERVICE_NAME\s*(=|IN)", where))
    has_svc_like = bool(re.search(r"SERVICE_NAME\s+LIKE", where))
    has_level = bool(re.search(r"\bLEVEL\s*(=|IN)", where))
    has_status = bool(re.search(r"STATUS_CODE", u))
    has_metric_eq = bool(re.search(r"\bMETRIC\s*(=|IN)", where))
    has_metric_like = bool(re.search(r"\bMETRIC\s+LIKE", where))
    has_msg_like = bool(re.search(r"\b(?:MESSAGE|SPAN_NAME)\s+LIKE", where))
    has_parent_in_sub = bool(re.search(r"PARENT_SPAN_ID\s+IN\s*\(\s*SELECT", where))
    has_parent_in_lit = bool(re.search(r"PARENT_SPAN_ID\s+IN\s*\(\s*['\"]", where))
    has_parent_eq = bool(re.search(r"PARENT_SPAN_ID\s*=\s*['\"]", where))
    has_attr_workload = "ATTR_DESTINATION_WORKLOAD" in u or "ATTR_SOURCE_WORKLOAD" in u or "ATTR.DESTINATION_WORKLOAD" in u or "ATTR.SOURCE_WORKLOAD" in u
    has_hubble = "HUBBLE" in u
    # SELECT clause (between SELECT and FROM, accounting for nested)
    sm = re.search(r"SELECT\s+(.*?)\s+FROM\b", u, re.DOTALL)
    sel = sm.group(1) if sm else ""
    has_minmax_time = bool(re.search(r"(MIN|MAX)\s*\(\s*TIME", sel))
    has_count = bool(re.search(r"\bCOUNT\s*\(", sel))
    has_avg_dur = bool(re.search(r"AVG\s*\(\s*DURATION", sel))
    has_distinct = "DISTINCT" in sel
    has_order_time = bool(re.search(r"ORDER\s+BY\s+[^,]*\bTIME\b", u))
    has_group_by = "GROUP BY" in u
    # metric LIKE keyword tags
    metric_tags = []
    for tag, pat in _METRIC_KW:
        if re.search(rf"METRIC\s+(?:=|LIKE)\s+'{pat}", where, re.IGNORECASE):
            metric_tags.append(tag)
    metric_tags = tuple(sorted(set(metric_tags)))
    # message LIKE keyword tags
    msg_tags = []
    for tag, pat in _MESSAGE_KW:
        if re.search(rf"(?:MESSAGE|SPAN_NAME)\s+LIKE\s+'[^']*{pat}", where, re.IGNORECASE):
            msg_tags.append(tag)
    msg_tags = tuple(sorted(set(msg_tags)))
    return (
        # which modality
        has_logs, has_traces, has_metrics,
        # which period
        has_ab, has_nm,
        # structural
        has_self_join,
        # WHERE
        has_trace_id, has_svc_eq, has_svc_like, has_level, has_status,
        has_metric_eq, has_metric_like, has_msg_like,
        has_parent_in_sub, has_parent_in_lit, has_parent_eq,
        has_attr_workload, has_hubble,
        # SELECT / ordering
        has_minmax_time, has_count, has_avg_dur, has_distinct,
        has_order_time, has_group_by,
        # keyword domains
        metric_tags, msg_tags,
    )


_FINGERPRINT_FIELDS = [
    "has_logs", "has_traces", "has_metrics", "has_ab", "has_nm",
    "has_self_join",
    "has_trace_id", "has_svc_eq", "has_svc_like", "has_level", "has_status_code",
    "has_metric_eq", "has_metric_like", "has_msg_like",
    "has_parent_in_sub", "has_parent_in_lit", "has_parent_eq",
    "has_attr_workload", "has_hubble",
    "has_minmax_time", "has_count", "has_avg_dur", "has_distinct",
    "has_order_time", "has_group_by",
    "metric_tags", "msg_tags",
]


def fingerprint_human(fp: tuple) -> str:
    """Short human-readable description of a fingerprint."""
    vals = dict(zip(_FINGERPRINT_FIELDS, fp))
    parts = []
    # table + period
    tbl = []
    if vals["has_logs"]: tbl.append("logs")
    if vals["has_traces"]: tbl.append("traces")
    if vals["has_metrics"]: tbl.append("metrics")
    tbl_s = "/".join(tbl) if tbl else "?"
    per = ""
    if vals["has_ab"] and vals["has_nm"]: per = "both"
    elif vals["has_ab"]: per = "abnormal"
    elif vals["has_nm"]: per = "normal"
    parts.append(f"[{per}_{tbl_s}]" if per else f"[{tbl_s}]")
    # filters
    f = []
    if vals["has_trace_id"]: f.append("trace_id=")
    if vals["has_svc_eq"]: f.append("svc=")
    if vals["has_svc_like"]: f.append("svc~")
    if vals["has_level"]: f.append("level=")
    if vals["has_status_code"]: f.append("status_code")
    if vals["has_metric_eq"]: f.append("metric=")
    if vals["has_metric_like"]: f.append("metric~")
    if vals["has_msg_like"]: f.append("msg~")
    if vals["has_parent_in_sub"]: f.append("parent∈SELECT")
    if vals["has_parent_in_lit"]: f.append("parent∈literal")
    if vals["has_parent_eq"]: f.append("parent=")
    if vals["has_attr_workload"]: f.append("attr.workload")
    if vals["has_hubble"]: f.append("hubble")
    # structural
    if vals["has_self_join"]: f.append("JOIN_parent=span")
    # SELECT features
    s = []
    if vals["has_distinct"]: s.append("DISTINCT")
    if vals["has_minmax_time"]: s.append("MIN/MAX(time)")
    if vals["has_count"]: s.append("COUNT")
    if vals["has_avg_dur"]: s.append("AVG(dur)")
    # ordering
    o = []
    if vals["has_group_by"]: o.append("GROUP_BY")
    if vals["has_order_time"]: o.append("ORDER_time")
    # tags
    tags = []
    if vals["metric_tags"]: tags.append("metric:" + "+".join(vals["metric_tags"]))
    if vals["msg_tags"]: tags.append("msg:" + "+".join(vals["msg_tags"]))
    return " | ".join(parts + [",".join(f)] + [",".join(s)] + [",".join(o)] + tags)


# ── Case / state structures ─────────────────────────────────────────────────


class Case:
    __slots__ = ("uid", "exp_id", "dataset_index", "round", "sql_index", "sql",
                 "old", "new", "g", "c47", "theme", "subtype", "fp", "fp_human")

    def __init__(self, uid, exp_id, idx, round_, sql_idx, sql, old, new, g, c47, theme, subtype):
        self.uid = uid
        self.exp_id = exp_id
        self.dataset_index = idx
        self.round = round_
        self.sql_index = sql_idx
        self.sql = sql
        self.old = old
        self.new = new
        self.g = g
        self.c47 = c47
        self.theme = theme
        self.subtype = subtype
        self.fp = sql_fingerprint(sql)
        self.fp_human = fingerprint_human(self.fp)

    def to_dict(self):
        # Sort unique labels, deduped
        options = []
        seen = set()
        for tag, v in [("claude_4_6_old", self.old), ("claude_4_6_new", self.new),
                        ("gemini", self.g), ("claude_4_7", self.c47)]:
            if v and v not in seen:
                options.append({"source": tag, "intent": v, "models": [tag]})
                seen.add(v)
        # Merge: find models that voted for the same intent
        intent_to_models = defaultdict(list)
        for tag, v in [("4.6-OLD", self.old), ("4.6-NEW", self.new),
                        ("Gemini", self.g), ("4.7", self.c47)]:
            if v:
                intent_to_models[v].append(tag)
        merged_options = [
            {"intent": intent, "models": models, "count": len(models)}
            for intent, models in sorted(intent_to_models.items(), key=lambda x: -len(x[1]))
        ]
        return {
            "uid": self.uid,
            "exp_id": self.exp_id,
            "dataset_index": self.dataset_index,
            "round": self.round,
            "sql_index": self.sql_index,
            "sql": self.sql,
            "options": merged_options,
            "theme": self.theme,
            "subtype": self.subtype,
            "fp_human": self.fp_human,
            "all_intents": list(VALID_INTENTS),
        }


# ── Theme / subtype heuristics (copy from categorize script) ─────────────────


def _theme_of(labels: set[str]) -> str | None:
    if labels == {"error_rate_scan", "error_timeline"} or \
       labels == {"error_log_overview", "error_timeline"} or \
       labels == {"service_error_log", "error_timeline"} or \
       labels == {"service_trace_scan", "error_timeline"}:
        return "T1 (Gemini error_timeline)"
    if labels & {"call_tree_build"} and labels & {"trace_follow", "service_trace_scan"}:
        return "T2 (call_tree vs trace_follow)"
    if labels == {"metric_scan", "network_layer"}:
        return "T3 (metric_scan vs network_layer)"
    if labels == {"service_error_log", "service_log_browse"}:
        return "T4 (service_error_log vs service_log_browse)"
    if labels == {"keyword_search", "service_trace_scan"}:
        return "T5 (keyword_search vs service_trace_scan)"
    return "T0 (other)"


def categorize_by_modality(sql: str) -> tuple[str, str]:
    """Return (modality, sub_category) for sidebar grouping.

    Groups pending SQLs by coarse shape: modality (LOGS/TRACES/METRICS/CROSS)
    × dominant feature (msg_LIKE, trace_id IN(sub), status only, etc.).
    This is what the new grouped sidebar uses.
    """
    u = re.sub(r"\s+", " ", sql.upper()).strip()
    # Flatten subqueries for outer-WHERE/SELECT extraction
    flat = u
    depth = 0
    start = -1
    i = 0
    while i < len(flat):
        c = flat[i]
        if c == "(":
            if depth == 0:
                start = i
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0 and start >= 0:
                inner = flat[start + 1 : i]
                if "SELECT" in inner:
                    flat = flat[:start] + " __SUBQ__ " + flat[i + 1 :]
                    i = start + len(" __SUBQ__ ") - 1
                    start = -1
                else:
                    start = -1
        i += 1
    wm = re.search(r"\bWHERE\b(.*?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|\bUNION\b|\bHAVING\b|$)",
                   flat, re.DOTALL)
    where = wm.group(1) if wm else ""
    sel_from = re.search(r"\bSELECT\b(.*?)\bFROM\b", flat, re.DOTALL)
    sel = sel_from.group(1) if sel_from else ""

    has_ab_logs = bool(re.search(r"\bABNORMAL_LOGS\b", u))
    has_nm_logs = bool(re.search(r"\bNORMAL_LOGS\b", u)) and not re.search(r"\bABNORMAL_LOGS\b", u[:u.index("NORMAL_LOGS")+12]) if "NORMAL_LOGS" in u else False
    has_nm_logs = bool(re.search(r"(?<!AB)\bNORMAL_LOGS\b", u))
    has_ab_traces = bool(re.search(r"\bABNORMAL_TRACES\b", u))
    has_nm_traces = bool(re.search(r"(?<!AB)\bNORMAL_TRACES\b", u))
    has_ab_metrics = bool(re.search(r"\bABNORMAL_METRICS(?:_HISTOGRAM|_SUM)?\b", u))
    has_nm_metrics = bool(re.search(r"(?<!AB)\bNORMAL_METRICS(?:_HISTOGRAM|_SUM)?\b", u))

    has_logs = has_ab_logs or has_nm_logs
    has_traces = has_ab_traces or has_nm_traces
    has_metrics = has_ab_metrics or has_nm_metrics
    has_nm = has_nm_logs or has_nm_traces or has_nm_metrics
    has_ab = has_ab_logs or has_ab_traces or has_ab_metrics
    n_mod = sum([has_logs, has_traces, has_metrics])

    # features
    has_group_by = bool(re.search(r"\bGROUP\s+BY\b", flat))
    has_count = bool(re.search(r"\bCOUNT\s*\(", sel))
    has_distinct = "DISTINCT" in sel
    has_msg_like = bool(re.search(r"\b(MESSAGE|SPAN_NAME)\s*(NOT\s+)?LIKE", where))
    has_level = bool(re.search(r"\bLEVEL\s*(=|IN|!=)", where))
    has_trace_id_sub = bool(re.search(r"\bTRACE_ID\s+IN\s*__SUBQ__", where))
    has_trace_id = bool(re.search(r"\bTRACE_ID\s*(=|IN)", where))
    has_svc = bool(re.search(r"\bSERVICE_NAME\s*(=|IN|!=|<>)", where))
    has_parent_span = bool(re.search(r"\bPARENT_SPAN_ID\s*(=|IN)", where))
    has_metric_like = bool(re.search(r"\bMETRIC\s+LIKE", where))
    has_metric_eq = bool(re.search(r"\bMETRIC\s*(=|IN)", where))
    has_status = "STATUS_CODE" in u
    has_dur_filter = bool(re.search(r"\bDURATION\s*[><]", where))
    has_attr_k8s = "ATTR_K8S" in u
    has_attr_wkld = ("ATTR_DESTINATION_WORKLOAD" in u or "ATTR_SOURCE_WORKLOAD" in u or "HUBBLE" in u)

    # modality label (prefer baseline marker)
    if has_nm and has_ab:
        mod_prefix = "BASELINE+AB"
    elif has_nm and not has_ab:
        mod_prefix = "NORMAL"
    else:
        mod_prefix = ""
    if n_mod > 1:
        tags = [t for t, p in [("logs", has_logs), ("traces", has_traces), ("metrics", has_metrics)] if p]
        modality = f"CROSS({'+'.join(tags)})"
    elif has_logs:
        modality = "LOGS"
    elif has_traces:
        modality = "TRACES"
    elif has_metrics:
        modality = "METRICS"
    else:
        modality = "UNKNOWN"
    if mod_prefix:
        modality = f"{mod_prefix}_{modality}"

    # sub-category
    if has_logs and not has_traces and not has_metrics:
        if has_msg_like:
            sub = "msg_LIKE"
        elif has_level and has_svc:
            sub = "svc+level"
        elif has_level:
            sub = "level_only"
        elif has_svc:
            sub = "svc_only"
        elif has_group_by and has_count:
            sub = "GROUPBY+COUNT"
        elif has_distinct:
            sub = "DISTINCT"
        else:
            sub = "other"
    elif has_traces and not has_logs and not has_metrics:
        if has_trace_id_sub:
            sub = "trace_id IN(sub)"
        elif has_trace_id:
            sub = "trace_id literal"
        elif has_parent_span:
            sub = "parent_span filter"
        elif has_msg_like:
            sub = "span_name LIKE"
        elif has_svc and has_dur_filter:
            sub = "svc+duration"
        elif has_svc and has_status:
            sub = "svc+status"
        elif has_svc:
            sub = "svc only"
        elif has_status:
            sub = "status only"
        elif has_dur_filter:
            sub = "duration"
        elif has_group_by and has_count:
            sub = "GROUPBY+COUNT"
        elif has_distinct:
            sub = "DISTINCT"
        else:
            sub = "other"
    elif has_metrics and not has_logs and not has_traces:
        if has_metric_like:
            sub = "metric_LIKE"
        elif has_metric_eq:
            sub = "metric="
        elif has_attr_wkld:
            sub = "network_attr"
        elif has_attr_k8s:
            sub = "k8s_attr"
        elif has_group_by and has_count:
            sub = "GROUPBY+COUNT"
        elif has_distinct:
            sub = "DISTINCT"
        else:
            sub = "other"
    else:
        sub = "cross_modal"
    return modality, sub


def _subtype(theme: str, sql: str) -> str:
    u = sql.upper()
    if theme.startswith("T1"):
        has_minmax = bool(re.search(r"(MIN|MAX)\s*\(\s*TIME", u))
        has_group = "GROUP BY" in u
        has_order_time = bool(re.search(r"ORDER\s+BY\s+[^,]*\bTIME\b", u))
        has_svc = bool(re.search(r"SERVICE_NAME\s*(=|IN|LIKE)", u))
        has_logs = bool(re.search(r"\b(?:ABNORMAL_|NORMAL_)?LOGS\b", u))
        has_traces = bool(re.search(r"\b(?:ABNORMAL_|NORMAL_)?TRACES\b", u))
        if has_minmax and has_group: return "T1a"
        if has_order_time and has_svc: return "T1c"
        if has_order_time and has_traces: return "T1e"
        if has_order_time and has_logs: return "T1d"
        if has_minmax: return "T1f"
        return "T1z"
    if theme.startswith("T2"):
        has_join = bool(re.search(r"PARENT_SPAN_ID\s*=\s*\w*\.?SPAN_ID|\w*\.?SPAN_ID\s*=\s*\w*\.?PARENT_SPAN_ID", u))
        has_trace_id = bool(re.search(r"TRACE_ID\s*(=|IN)", u))
        has_parent_in = bool(re.search(r"PARENT_SPAN_ID\s+IN", u))
        has_parent_eq = bool(re.search(r"PARENT_SPAN_ID\s*=\s*['\"]", u))
        if has_join: return "T2a"
        if has_trace_id and has_parent_in: return "T2b"
        if has_parent_in and u.count("SELECT") > 1: return "T2d"
        if has_parent_eq: return "T2f"
        if has_trace_id: return "T2g"
        return "T2z"
    if theme.startswith("T3"):
        if "HUBBLE" in u: return "T3a"
        if "ATTR_DESTINATION_WORKLOAD" in u or "ATTR_SOURCE_WORKLOAD" in u: return "T3b"
        if re.search(r"METRIC\s+LIKE\s+'%[^']*(?:HTTP|NET|TCP|HUBBLE|DROP|LATENCY|REQUEST)", u): return "T3c"
        if any(k in u for k in ["HTTP_REQUEST", "TCP", "NETWORK", "DROP", "LATENCY"]): return "T3d"
        if "DISTINCT METRIC" in u or ("SELECT DISTINCT" in u and "METRIC" in u[:200]): return "T3e"
        if re.search(r"METRIC\s+LIKE", u): return "T3f"
        return "T3z"
    return "-"


# ── Case loading ─────────────────────────────────────────────────────────────


def load_pending_cases(engine) -> list[Case]:
    """Scan DB; return all positions not yet in meta.llm_intents.final."""
    out: list[Case] = []
    with engine.connect() as conn:
        for exp_id in EXPS:
            rows = conn.execute(text(f"""
                SELECT dataset_index, trajectories, meta
                FROM evaluation_data
                WHERE exp_id='{exp_id}' AND stage='judged'
            """)).fetchall()
            for idx, traj_raw, meta_raw in rows:
                m = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
                d = m.get("llm_intents") or {}
                final_set = {(e.get("round"), e.get("sql_index")) for e in d.get(FINAL_KEY, [])}
                maps = {
                    k: {(e.get("round"), e.get("sql_index")): e.get("intent", "")
                        for e in d.get(dbk, [])}
                    for k, dbk in [("old", CLAUDE_OLD), ("new", CLAUDE_NEW), ("g", GEMINI), ("c47", C47)]
                }
                traj = json.loads(traj_raw) if isinstance(traj_raw, str) else traj_raw
                rounds = extract_sql_rounds(normalize_by_agent(exp_id.split("-", 1)[0], traj))
                sql_by_pos = {(r.round_index, i + 1): sql
                              for r in rounds for i, sql in enumerate(r.queries)}
                for pos in set().union(*[set(mm.keys()) for mm in maps.values()]):
                    if pos in final_set:
                        continue
                    labels = {maps[k].get(pos) for k in maps if maps[k].get(pos)}
                    if len(labels) <= 1:
                        continue
                    sql = sql_by_pos.get(pos, "")
                    if not sql:
                        continue
                    # New grouped sidebar: by (modality, sub_category)
                    # Falls back to the old theme/subtype only if categorize yields UNKNOWN.
                    theme, sub = categorize_by_modality(sql)
                    if theme == "UNKNOWN":
                        theme = _theme_of(labels)
                        sub = _subtype(theme, sql)
                    uid = f"{exp_id}|{idx}|{pos[0]}|{pos[1]}"
                    out.append(Case(
                        uid=uid, exp_id=exp_id, idx=idx, round_=pos[0], sql_idx=pos[1],
                        sql=sql, old=maps["old"].get(pos), new=maps["new"].get(pos),
                        g=maps["g"].get(pos), c47=maps["c47"].get(pos),
                        theme=theme, subtype=sub,
                    ))
    # Sort: group by theme + subtype so user sees related cases together
    out.sort(key=lambda c: (c.theme, c.subtype, c.exp_id, c.dataset_index, c.round, c.sql_index))
    return out


# ── FastAPI app ──────────────────────────────────────────────────────────────


class Decision(BaseModel):
    uid: str
    intent: str
    note: str | None = None


app = FastAPI()
STATE = {"engine": None, "cases": [], "case_by_uid": {}}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


@app.get("/api/health")
async def health():
    return {"ok": True, "pending": sum(1 for c in STATE["cases"] if c.uid not in STATE["decided"])}


@app.get("/api/stats")
async def stats():
    by_theme = Counter(c.theme for c in STATE["cases"])
    decided_by_theme = Counter(c.theme for c in STATE["cases"] if c.uid in STATE["decided"])
    return {
        "total": len(STATE["cases"]),
        "decided": len(STATE["decided"]),
        "pending": len(STATE["cases"]) - len(STATE["decided"]),
        "themes": [
            {"theme": t, "total": n, "decided": decided_by_theme[t], "pending": n - decided_by_theme[t]}
            for t, n in sorted(by_theme.items())
        ],
    }


@app.get("/api/case")
async def get_case(theme: str | None = None, subtype: str | None = None,
                     exp_id: str | None = None, skip_decided: bool = True):
    """Return the next pending case matching filters."""
    for c in STATE["cases"]:
        if skip_decided and c.uid in STATE["decided"]:
            continue
        if theme and not c.theme.startswith(theme):
            continue
        if subtype and c.subtype != subtype:
            continue
        if exp_id and c.exp_id != exp_id:
            continue
        return c.to_dict()
    return JSONResponse({"done": True}, status_code=200)


@app.post("/api/decide")
async def decide(d: Decision):
    case = STATE["case_by_uid"].get(d.uid)
    if not case:
        raise HTTPException(404, "unknown uid")
    if d.intent not in VALID_INTENTS:
        raise HTTPException(400, f"invalid intent: {d.intent}")

    engine = STATE["engine"]
    with Session(engine) as session:
        sample = session.exec(
            select(EvaluationSample).where(
                EvaluationSample.exp_id == case.exp_id,
                EvaluationSample.dataset_index == case.dataset_index,
                EvaluationSample.stage == "judged",
            )
        ).first()
        if not sample:
            raise HTTPException(404, "sample not found")
        meta = sample.meta or {}
        d_ = meta.setdefault("llm_intents", {})
        arr = d_.setdefault(FINAL_KEY, [])
        # replace existing entry at this position if any, else append
        existing = {(e.get("round"), e.get("sql_index")): i for i, e in enumerate(arr)}
        new_entry = {
            "round": case.round,
            "sql_index": case.sql_index,
            "intent": d.intent,
            "rule": "user",
        }
        if d.note:
            new_entry["note"] = d.note
        if (case.round, case.sql_index) in existing:
            arr[existing[(case.round, case.sql_index)]] = new_entry
        else:
            arr.append(new_entry)
        d_[FINAL_KEY] = sorted(arr, key=lambda x: (x.get("round", 0), x.get("sql_index", 0)))
        meta["llm_intents"] = d_
        sample.meta = meta
        flag_modified(sample, "meta")
        session.add(sample)
        session.commit()

    STATE["decided"].add(d.uid)
    return {"ok": True, "decided": len(STATE["decided"]),
            "pending": len(STATE["cases"]) - len(STATE["decided"])}


@app.post("/api/skip")
async def skip(d: Decision):
    """Mark case as skipped for this session (not written to DB)."""
    STATE["decided"].add(d.uid)
    return {"ok": True, "skipped": d.uid,
            "pending": len(STATE["cases"]) - len(STATE["decided"])}


# Legacy BatchApply / _pattern model-vote logic removed: rule propagation now
# uses SQL fingerprint ONLY (see /api/propagate_user_decisions).


def _scan_user_labels(engine, case_by_pos) -> dict[tuple, list[str]]:
    """Return {sql_fingerprint → list of user-chosen intents}.

    Only counts entries with rule='user' (direct human decisions). Propagated
    labels don't count as new evidence.
    """
    user_decisions_by_fp: dict[tuple, list[str]] = defaultdict(list)
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT exp_id, dataset_index, meta
            FROM evaluation_data
            WHERE stage='judged'
              AND (meta::jsonb->'llm_intents'->'{FINAL_KEY}') IS NOT NULL
        """)).fetchall()
    for exp_id, idx, meta_raw in rows:
        m = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
        for entry in (m.get("llm_intents") or {}).get(FINAL_KEY, []):
            if entry.get("rule", "") != "user":
                continue
            pos = (exp_id, idx, entry.get("round"), entry.get("sql_index"))
            case = case_by_pos.get(pos)
            if not case:
                continue
            user_decisions_by_fp[case.fp].append(entry.get("intent", ""))
    return user_decisions_by_fp


@app.get("/api/rule_status")
async def rule_status(subtype: str | None = None, min_confirmations: int = 1):
    """Return the current rule induction state keyed by SQL fingerprint.

    Each rule groups pending cases by their SQL structural fingerprint.
    User-labeled cases are evidence for that fingerprint's intent.

    Status:
      - "unseen"      — no user label for this fingerprint (🔴)
      - "insufficient"— user labels < min_confirmations but all agree (🟡)
      - "saturated"   — user labels ≥ min_confirmations and all agree (🟢)
      - "conflicting" — user labels disagree on this fingerprint (⚠️)
    """
    case_by_pos = {(c.exp_id, c.dataset_index, c.round, c.sql_index): c for c in STATE["cases"]}
    user_labels = _scan_user_labels(STATE["engine"], case_by_pos)

    # Count pending cases per fingerprint
    pending_by_fp: Counter = Counter()
    example_sql: dict[tuple, str] = {}
    for c in STATE["cases"]:
        if c.uid in STATE["decided"]:
            continue
        if subtype and c.subtype != subtype:
            continue
        pending_by_fp[c.fp] += 1
        example_sql.setdefault(c.fp, c.sql)

    rules = []
    for fp, pending_ct in pending_by_fp.most_common():
        labels = user_labels.get(fp, [])
        n_lab = len(labels)
        uniq = set(labels)
        if n_lab == 0:
            status = "unseen"; dominant = None
        elif len(uniq) == 1:
            status = "saturated" if n_lab >= min_confirmations else "insufficient"
            dominant = next(iter(uniq))
        else:
            status = "conflicting"; dominant = Counter(labels).most_common(1)[0][0]
        rules.append({
            "fp_human": fingerprint_human(fp),
            "fp": list(fp),
            "pending_matches": pending_ct,
            "user_labels": labels,
            "n_user_labels": n_lab,
            "intent": dominant,
            "status": status,
            "example_sql": re.sub(r"\s+", " ", example_sql[fp])[:200],
        })

    summary = Counter(r["status"] for r in rules)
    pending_covered_by_saturated = sum(r["pending_matches"] for r in rules if r["status"] == "saturated")
    return {
        "min_confirmations": min_confirmations,
        "rules": rules,
        "summary": dict(summary),
        "pending_covered_by_saturated": pending_covered_by_saturated,
        "total_pending": sum(r["pending_matches"] for r in rules),
    }


@app.post("/api/propagate_user_decisions")
async def propagate_user_decisions(scope_subtype: str | None = None, dry_run: bool = False,
                                     min_confirmations: int = 3):
    """Apply the user's prior decisions to all pending cases with the SAME
    (subtype, 4-model vote pattern) as a case the user has already labeled.

    For each SQL fingerprint the user has labeled:
      - If ALL user labels at this (subtype, pattern) chose the same intent → apply
        that intent to all remaining pending cases with same (subtype, pattern).
      - If user labels split (e.g. picked error_rate_scan for 2, error_timeline for 1):
        skip this group (ambiguous — leave for more manual review).

    Writes rule="user_propagated" to distinguish from direct rule="user" decisions.
    """
    engine = STATE["engine"]
    case_by_pos = {(c.exp_id, c.dataset_index, c.round, c.sql_index): c for c in STATE["cases"]}
    user_decisions_by_fp = _scan_user_labels(engine, case_by_pos)

    # Saturated: ≥ min_confirmations labels for this fingerprint, all agree
    fp_to_intent = {}
    conflicting = []
    insufficient = []
    for fp, intents in user_decisions_by_fp.items():
        unique = set(intents)
        if len(intents) >= min_confirmations and len(unique) == 1:
            fp_to_intent[fp] = next(iter(unique))
        elif len(unique) > 1:
            conflicting.append({"fp_human": fingerprint_human(fp),
                                 "labels_given": dict(Counter(intents))})
        else:
            insufficient.append({"fp_human": fingerprint_human(fp),
                                  "intent": next(iter(unique)) if unique else None,
                                  "n_labels": len(intents)})

    # Find pending cases matching any fingerprint in the decided map
    targets = []
    fp_match_count = Counter()
    for c in STATE["cases"]:
        if c.uid in STATE["decided"]:
            continue
        if c.fp in fp_to_intent:
            targets.append((c, fp_to_intent[c.fp]))
            fp_match_count[c.fp] += 1

    if dry_run:
        return {
            "min_confirmations": min_confirmations,
            "saturated_rules": len(fp_to_intent),
            "conflicting_rules": len(conflicting),
            "insufficient_rules": len(insufficient),
            "would_write": len(targets),
            "conflicts": conflicting[:20],
            "insufficient_sample": insufficient[:10],
            "learned_summary": [
                {"fp_human": fingerprint_human(fp), "intent": intent,
                 "pending_matches": fp_match_count.get(fp, 0),
                 "user_labels_count": len(user_decisions_by_fp.get(fp, []))}
                for fp, intent in fp_to_intent.items()
            ],
        }

    # Write in groups by sample
    by_sample: dict[tuple[str, int], list] = defaultdict(list)
    for c, intent in targets:
        by_sample[(c.exp_id, c.dataset_index)].append((c, intent))

    written = 0
    with Session(engine) as session:
        for (exp_id, idx), group in by_sample.items():
            sample = session.exec(
                select(EvaluationSample).where(
                    EvaluationSample.exp_id == exp_id,
                    EvaluationSample.dataset_index == idx,
                    EvaluationSample.stage == "judged",
                )
            ).first()
            if not sample:
                continue
            meta = sample.meta or {}
            d_ = meta.setdefault("llm_intents", {})
            arr = d_.setdefault(FINAL_KEY, [])
            existing = {(e.get("round"), e.get("sql_index")): i for i, e in enumerate(arr)}
            for c, intent in group:
                entry = {
                    "round": c.round,
                    "sql_index": c.sql_index,
                    "intent": intent,
                    "rule": "user_propagated",
                }
                if (c.round, c.sql_index) in existing:
                    arr[existing[(c.round, c.sql_index)]] = entry
                else:
                    arr.append(entry)
                STATE["decided"].add(c.uid)
                written += 1
            d_[FINAL_KEY] = sorted(arr, key=lambda x: (x.get("round", 0), x.get("sql_index", 0)))
            meta["llm_intents"] = d_
            sample.meta = meta
            flag_modified(sample, "meta")
            session.add(sample)
        session.commit()

    return {
        "written": written,
        "learned_groups": len(pattern_to_intent),
        "conflicting_groups": len(conflicting),
        "pending": len(STATE["cases"]) - len(STATE["decided"]),
    }


# pattern_breakdown endpoint removed (was model-vote based; now superseded by rule_status)


@app.get("/api/subtype_summary")
async def subtype_summary():
    """Per-(theme, subtype) counts of pending cases, for UI sidebar."""
    stats = defaultdict(lambda: {"total": 0, "pending": 0, "sample_intents": Counter()})
    for c in STATE["cases"]:
        key = (c.theme, c.subtype)
        stats[key]["total"] += 1
        if c.uid not in STATE["decided"]:
            stats[key]["pending"] += 1
    out = []
    for (theme, sub), s in sorted(stats.items()):
        out.append({"theme": theme, "subtype": sub, "total": s["total"], "pending": s["pending"]})
    return {"subtypes": out}


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Intent Labeling</title>
<style>
  body{font-family:system-ui,-apple-system,sans-serif;margin:0;padding:0;background:#0d1117;color:#e6edf3;height:100vh;display:flex;flex-direction:column}
  header{padding:8px 16px;background:#161b22;border-bottom:1px solid #30363d;display:flex;justify-content:space-between;align-items:center;gap:16px}
  header h1{margin:0;font-size:15px;font-weight:600}
  header .stats{font-size:13px;color:#8b949e}
  header .filter{display:flex;gap:8px;align-items:center;font-size:12px}
  header select{background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:4px;padding:3px 6px;font-size:12px}
  .progress-bar{height:3px;background:#30363d;position:relative}
  .progress-fill{position:absolute;left:0;top:0;height:100%;background:#2f81f7;transition:width .2s}
  main{flex:1;display:grid;grid-template-columns:220px 1fr 400px;gap:12px;padding:12px;overflow:hidden}
  .sidebar{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:10px;overflow:auto;font-size:12px}
  .sidebar h3{margin:0 0 8px 0;font-size:12px;color:#8b949e;font-weight:500}
  .sidebar .sub-row{display:flex;justify-content:space-between;padding:4px 6px;border-radius:4px;cursor:pointer;margin-bottom:2px}
  .sidebar .sub-row:hover{background:#21262d}
  .sidebar .sub-row.active{background:#2f81f7;color:#fff}
  .sidebar .sub-row .count{color:#8b949e;font-family:monospace}
  .sidebar .sub-row.active .count{color:#fff}
  .sidebar .sub-row.done{color:#6e7681;text-decoration:line-through}
  .sql-pane{display:flex;flex-direction:column;background:#0d1117;border:1px solid #30363d;border-radius:8px;overflow:hidden}
  .sql-meta{padding:8px 12px;background:#161b22;border-bottom:1px solid #30363d;font-size:12px;color:#8b949e;display:flex;gap:16px;flex-wrap:wrap}
  .sql-meta strong{color:#e6edf3}
  .sql-meta .theme{color:#d29922;font-weight:600}
  .sql-body{padding:16px;overflow:auto;flex:1;font-family:ui-monospace,SFMono-Regular,monospace;font-size:14px;line-height:1.5;white-space:pre-wrap;word-break:break-word;color:#c9d1d9}
  .options-pane{display:flex;flex-direction:column;gap:8px;overflow:auto}
  .options-pane h2{margin:0 0 4px 0;font-size:13px;color:#8b949e;font-weight:500}
  .option-btn{background:#21262d;border:1px solid #30363d;border-radius:6px;padding:12px 14px;cursor:pointer;text-align:left;transition:all .15s;color:#e6edf3;font-size:14px}
  .option-btn:hover{background:#30363d;border-color:#2f81f7}
  .option-btn .key{display:inline-block;width:20px;height:20px;background:#30363d;border-radius:4px;text-align:center;font-size:11px;line-height:20px;margin-right:8px;color:#8b949e;font-family:monospace}
  .option-btn .intent{font-weight:600;color:#7ee787;font-family:ui-monospace,monospace;font-size:14px}
  .option-btn .models{display:block;font-size:11px;color:#8b949e;margin-top:4px;margin-left:28px}
  .option-btn .count{font-size:11px;background:#2f81f7;color:#fff;border-radius:10px;padding:2px 7px;margin-left:8px}
  .custom-pane{margin-top:12px;border-top:1px solid #30363d;padding-top:12px;display:flex;flex-direction:column;gap:6px}
  .custom-pane label{font-size:12px;color:#8b949e}
  .custom-pane select{background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:4px;padding:6px;font-size:13px;font-family:monospace}
  .custom-pane button{background:#238636;color:#fff;border:none;border-radius:6px;padding:8px;cursor:pointer;font-size:13px;margin-top:4px}
  .custom-pane button:hover{background:#2ea043}
  .skip-btn{background:#6e7681;color:#fff;border:none;border-radius:6px;padding:6px 12px;cursor:pointer;font-size:12px;margin-top:8px}
  .skip-btn:hover{background:#8b949e}
  .batch-pane{margin-top:12px;border-top:1px solid #30363d;padding-top:12px;background:#161b22;border-radius:4px;padding:10px}
  .batch-pane h3{margin:0 0 8px 0;font-size:12px;color:#d29922;font-weight:600}
  .batch-pane select{background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:4px;padding:6px;font-size:13px;font-family:monospace;width:100%;margin-bottom:6px}
  .batch-pane button{background:#d29922;color:#0d1117;border:none;border-radius:6px;padding:8px;cursor:pointer;font-size:13px;width:100%;font-weight:600}
  .batch-pane button:hover{background:#e7b536}
  .batch-pane .info{font-size:11px;color:#8b949e;margin-bottom:6px}
  .hint{font-size:11px;color:#8b949e;margin-top:12px;padding:8px;background:#161b22;border-radius:4px;line-height:1.6}
  .hint kbd{background:#30363d;color:#e6edf3;border-radius:3px;padding:1px 5px;font-family:monospace;font-size:10px}
  .done{text-align:center;padding:80px 20px;font-size:24px;color:#7ee787}
</style>
</head>
<body>
<header>
  <h1>Intent Labeling</h1>
  <div class="stats" id="stats">Loading...</div>
  <div class="filter">
    <label>Theme:
      <select id="theme-filter" onchange="loadNext()">
        <option value="">(all)</option>
      </select>
    </label>
    <label>Subtype:
      <select id="subtype-filter" onchange="loadNext()">
        <option value="">(all)</option>
      </select>
    </label>
  </div>
</header>
<div class="progress-bar"><div class="progress-fill" id="progress"></div></div>
<main>
  <aside class="sidebar">
    <h3>Subtypes (click to filter)</h3>
    <div id="sub-list"></div>
  </aside>
  <div class="sql-pane">
    <div class="sql-meta" id="meta"></div>
    <div class="sql-body" id="sql"></div>
  </div>
  <div class="options-pane" id="options-pane">
    <h2>Pick intent (click or press number)</h2>
    <div id="options"></div>
    <div class="custom-pane">
      <label for="custom-select">Or pick any intent:</label>
      <select id="custom-select"></select>
      <button onclick="submitCustom()">Submit custom</button>
      <button class="skip-btn" onclick="skipCase()">Skip this (S)</button>
    </div>
    <div class="batch-pane">
      <h3>🧠 Rule saturation (current subtype)</h3>
      <div class="info" style="margin-bottom:4px">
        Each rule = (subtype, 4-vote pattern). Label multiple cases with same pattern;
        when they all agree (≥ threshold), rule is <strong>🟢 saturated</strong>.
      </div>
      <div style="display:flex;gap:4px;align-items:center;font-size:11px">
        Threshold:
        <input type="number" id="min-conf" value="3" min="1" max="10" style="width:40px;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:3px;padding:2px"/>
        <button onclick="refreshRules()" style="padding:3px 8px;font-size:11px;background:#30363d;color:#e6edf3;border:1px solid #30363d;border-radius:3px;cursor:pointer">Refresh</button>
      </div>
      <div id="rule-list" style="max-height:260px;overflow:auto;margin-top:8px;font-size:11px"></div>
      <button onclick="propagateDecisions(true)" id="prop-dry-btn" style="background:#2f81f7;margin-top:4px">
        Preview apply saturated 🟢
      </button>
      <button onclick="propagateDecisions(false)" id="prop-apply-btn" style="background:#238636;margin-top:4px">
        Apply all saturated rules
      </button>
      <div id="prop-summary" style="margin-top:8px;font-size:11px;color:#8b949e;white-space:pre-wrap"></div>
    </div>
    <div class="hint">
      <strong>Shortcuts</strong><br>
      <kbd>1</kbd>..<kbd>4</kbd> pick corresponding option &nbsp;
      <kbd>S</kbd> skip &nbsp;
      <kbd>U</kbd> undo last (TODO)<br>
      <kbd>Ctrl+Enter</kbd> submit custom
    </div>
  </div>
</main>
<script>
let current = null;
let themes = [];

// Restore sticky subtype selection across page reloads
let activeSubtype = sessionStorage.getItem('activeSubtype') || null;

async function loadStats() {
  const r = await fetch('/api/stats'); const s = await r.json();
  document.getElementById('stats').textContent = `${s.decided}/${s.total} done (${s.pending} pending)`;
  const pct = s.total ? (s.decided / s.total * 100) : 0;
  document.getElementById('progress').style.width = pct + '%';
  const sel = document.getElementById('theme-filter');
  if (sel.options.length <= 1) {
    s.themes.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.theme.split(' ')[0];
      opt.textContent = `${t.theme} — ${t.pending} left`;
      sel.appendChild(opt);
    });
  }
}

async function loadSubtypeSidebar() {
  const r = await fetch('/api/subtype_summary'); const s = await r.json();
  const list = document.getElementById('sub-list');
  list.innerHTML = '';
  // group by theme
  const by_theme = {};
  s.subtypes.forEach(x => { (by_theme[x.theme] = by_theme[x.theme] || []).push(x); });
  Object.keys(by_theme).sort().forEach(theme => {
    const hdr = document.createElement('div');
    hdr.style.cssText = 'color:#d29922;font-size:11px;font-weight:600;margin:8px 0 4px 0';
    hdr.textContent = theme;
    list.appendChild(hdr);
    by_theme[theme].forEach(x => {
      const row = document.createElement('div');
      row.className = 'sub-row' + (x.pending === 0 ? ' done' : '') + (activeSubtype === x.subtype ? ' active' : '');
      row.innerHTML = `<span>${x.subtype}</span><span class="count">${x.pending}/${x.total}</span>`;
      row.onclick = () => {
        activeSubtype = (activeSubtype === x.subtype) ? null : x.subtype;
        loadSubtypeSidebar();
        loadNext();
        refreshRules();
      };
      list.appendChild(row);
    });
  });
}

// updateBatchInfo removed — old batch-apply panel was replaced by rule saturation view.
function updateBatchInfo_removed() {
  const info = document.getElementById('batch-info');
  const btn = document.getElementById('batch-btn');
  if (!activeSubtype) {
    info.textContent = 'Select a subtype on the left.';
    btn.textContent = 'Apply to all (0)';
    btn.disabled = true;
    return;
  }
  fetch('/api/subtype_summary').then(r => r.json()).then(s => {
    const row = s.subtypes.find(x => x.subtype === activeSubtype);
    if (row) {
      info.textContent = `Selected: ${activeSubtype} (${row.pending} pending of ${row.total}).`;
      btn.textContent = `Apply to all ${row.pending}`;
      btn.disabled = row.pending === 0;
    }
  });
}

async function refreshRules() {
  const mcEl = document.getElementById('min-conf');
  const ul = document.getElementById('rule-list');
  if (!ul) return;  // UI not mounted yet
  const minConf = (mcEl && mcEl.value) || 1;
  const sub = activeSubtype || '';
  const url = '/api/rule_status?min_confirmations=' + minConf + (sub ? '&subtype=' + encodeURIComponent(sub) : '');
  const r = await fetch(url); const res = await r.json();
  ul.innerHTML = '';
  const emoji = {unseen:'🔴', insufficient:'🟡', saturated:'🟢', conflicting:'⚠️'};
  res.rules.slice(0, 30).forEach(rule => {
    const div = document.createElement('div');
    div.style.cssText = 'border:1px solid #30363d;border-radius:4px;padding:6px;margin-bottom:4px;background:#161b22';
    const intentPart = rule.intent ? `<span style="color:#7ee787">→ ${rule.intent}</span>` : '';
    const labels = rule.user_labels.length ? `<span style="color:#8b949e">(${rule.n_user_labels} lab: ${[...new Set(rule.user_labels)].join('/')})</span>` : '';
    div.innerHTML = `
      <div style="display:flex;justify-content:space-between">
        <span>${emoji[rule.status]||''} <strong>${rule.pending_matches}</strong> pending</span>
        <span>${intentPart} ${labels}</span>
      </div>
      <div style="font-family:monospace;color:#8b949e;font-size:10px;margin-top:2px">${rule.fp_human}</div>
    `;
    ul.appendChild(div);
  });
  const sat = res.pending_covered_by_saturated || 0;
  ul.insertAdjacentHTML('afterbegin',
    `<div style="padding:4px 0;color:#7ee787">${sat} pending covered by saturated 🟢 rules</div>`);
}

async function propagateDecisions(dryRun) {
  const minConf = document.getElementById('min-conf').value || 1;
  const r = await fetch('/api/propagate_user_decisions?dry_run=' + (dryRun ? 'true' : 'false') + '&min_confirmations=' + minConf,
    {method: 'POST'});
  if (!r.ok) { alert('Error: ' + await r.text()); return; }
  const res = await r.json();
  const summaryEl = document.getElementById('prop-summary');
  if (dryRun) {
    let txt = `min_conf=${res.min_confirmations}: ${res.saturated_rules} saturated rules.\n`;
    txt += `Would write ${res.would_write} new labels.\n`;
    if (res.conflicting_rules > 0) txt += `⚠️ ${res.conflicting_rules} conflicting\n`;
    if (res.insufficient_rules > 0) txt += `🟡 ${res.insufficient_rules} insufficient (below threshold)\n`;
    if (res.learned_summary && res.learned_summary.length > 0) {
      txt += '\nTop saturated:\n';
      res.learned_summary.slice(0, 5).forEach(g => {
        txt += `  → ${g.intent} [${g.user_labels_count} labels] matches ${g.pending_matches}\n`;
      });
    }
    summaryEl.textContent = txt;
  } else {
    // Remember which subtype is active so we restore it after reload
    if (activeSubtype) {
      sessionStorage.setItem('activeSubtype', activeSubtype);
    }
    summaryEl.textContent = `✓ Wrote ${res.written} labels (${res.saturated_rules} rules). Reloading…`;
    setTimeout(() => location.reload(), 600);
  }
}

async function loadNext() {
  const theme = document.getElementById('theme-filter').value;
  const subtype = activeSubtype || document.getElementById('subtype-filter').value;
  let url = '/api/case?';
  if (theme) url += 'theme=' + encodeURIComponent(theme) + '&';
  if (subtype) url += 'subtype=' + encodeURIComponent(subtype) + '&';
  const r = await fetch(url); const c = await r.json();
  if (c.done) {
    // Non-destructive: write "done" message into sql-body and clear options,
    // keep sidebar and batch pane alive so user can still apply remaining rules
    // or switch subtypes.
    document.getElementById('meta').innerHTML = '<span style="color:#7ee787">🎉 No more pending in current filter</span>';
    document.getElementById('sql').textContent = 'Switch subtype on the left, or clear filter.';
    document.getElementById('options').innerHTML = '';
    current = null;
    await loadStats();
    await loadSubtypeSidebar();
    refreshRules();
    return;
  }
  current = c;
  document.getElementById('meta').innerHTML =
    `<span class="theme">${c.theme}</span> <span>subtype <strong>${c.subtype}</strong></span>
     <span>exp <strong>${c.exp_id}</strong></span>
     <span>idx <strong>${c.dataset_index}</strong></span>
     <span>round <strong>${c.round}.${c.sql_index}</strong></span>
     <br><span style="color:#7ee787;font-family:monospace;font-size:11px">fp: ${c.fp_human || ''}</span>`;
  document.getElementById('sql').textContent = c.sql;
  const optDiv = document.getElementById('options');
  optDiv.innerHTML = '';
  c.options.forEach((opt, i) => {
    const btn = document.createElement('button');
    btn.className = 'option-btn';
    btn.innerHTML =
      `<span class="key">${i+1}</span>
       <span class="intent">${opt.intent}</span>
       ${opt.count > 1 ? '<span class="count">' + opt.count + '</span>' : ''}
       <span class="models">${opt.models.join(' + ')}</span>`;
    btn.onclick = () => submitIntent(opt.intent);
    optDiv.appendChild(btn);
  });
  // populate custom dropdown (batch-intent no longer exists — we now use rule saturation UI)
  const custSel = document.getElementById('custom-select');
  if (custSel && custSel.options.length === 0) {
    c.all_intents.forEach(i => {
      const opt = document.createElement('option');
      opt.value = i; opt.textContent = i;
      custSel.appendChild(opt);
    });
  }
  await loadStats();
  await loadSubtypeSidebar();
  refreshRules();
}

async function submitIntent(intent) {
  if (!current) return;
  const body = JSON.stringify({uid: current.uid, intent: intent});
  const r = await fetch('/api/decide', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: body});
  if (r.ok) { await loadNext(); refreshRules(); }
  else { const t = await r.text(); alert('Error: ' + t); }
}

async function skipCase() {
  if (!current) return;
  await fetch('/api/skip', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({uid: current.uid, intent: 'skip'})});
  loadNext();
}

function submitCustom() {
  const v = document.getElementById('custom-select').value;
  if (v) submitIntent(v);
}

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'SELECT' || e.target.tagName === 'INPUT') return;
  if (e.key >= '1' && e.key <= '9') {
    const idx = parseInt(e.key) - 1;
    if (current && current.options[idx]) submitIntent(current.options[idx].intent);
  } else if (e.key.toLowerCase() === 's') {
    skipCase();
  } else if (e.ctrlKey && e.key === 'Enter') {
    submitCustom();
  }
});

loadNext();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(HTML_PAGE)


@app.get("/favicon.ico")
async def favicon():
    return JSONResponse({}, status_code=204)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8777)
    args = parser.parse_args()

    engine = create_engine(
        args.db,
        connect_args={"check_same_thread": False} if args.db.startswith("sqlite") else {},
        pool_size=10, max_overflow=10, pool_pre_ping=True,
    )
    STATE["engine"] = engine

    logger.info("Loading pending cases from DB...")
    cases = load_pending_cases(engine)
    STATE["cases"] = cases
    STATE["case_by_uid"] = {c.uid: c for c in cases}
    STATE["decided"] = set()
    logger.info("Loaded %d pending cases", len(cases))

    # Summary by theme
    theme_cnt = Counter(c.theme for c in cases)
    for t, n in sorted(theme_cnt.items()):
        logger.info("  %s: %d", t, n)

    logger.info("Starting server on http://%s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
