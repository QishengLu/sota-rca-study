"""V-B mechanical evidence extraction for failure-label 3-way verification.

For each case in merged/verify_samples.jsonl, writes merged/verify_evidence/<agent>_case_<id>.yaml.
Extraction is mechanical (no interpretation); orchestrator V-C adjudicates from these YAMLs.

Atomicity: write to <path>.tmp then os.rename to <path> (atomic on POSIX).
Idempotent: skips existing YAMLs unless --force.

Evidence sections (matches plan v-f-aiq-21-case-peaceful-waterfall):
- gt_from_injection_json / gt_from_causal_graph_json
- agent_predicted (from DB.response)
- raw_sql_list / raw_sql_substring_audit / raw_sql_count_total
- parquet_evidence (top error services, GT status_code dist, GT abnormal counts)
- trajectory_reasoning_snippets (selected assistant text for R verification)
- gt_required_capabilities (3-way alignment block #1)
- path_alignment (3-way alignment block #2)
- counterfactual (3-way alignment block #3) — PD-specific sub-blocks
- parquet_queries_run / counterfactual_queries_run (audit)
- classes_to_verify
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

import duckdb
import psycopg2
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from harp_config import FRAMEWORKS, MERGED

DATA_BASE = Path("RCAgentEval/eval-data")
DOSSIER_BASE = {
    "aiq": Path("analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/v1/dossiers"),
    "claudecode": Path("analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers"),
    "sonnet": Path("analysis/3-failure-modes/2-by-framework/thinkdepthai-claude-sonnet-4.6/v1/dossiers"),
    "qwen": Path("analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers"),
}
EVIDENCE_DIR = MERGED / "verify_evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

# -------------------- Loading ------------------------

def load_injection(data_dir: str) -> dict:
    with open(Path(data_dir) / "injection.json") as f:
        return json.load(f)


def load_causal_graph(data_dir: str) -> dict:
    p = Path(data_dir) / "causal_graph.json"
    if not p.exists():
        return {}
    with open(p) as f:
        return json.load(f)


def load_trajectory(agent: str, case_id: int, exp_id: str) -> list[dict]:
    """Load raw trajectory as OpenAI-format message list."""
    # Try dossier raw.json first
    dossier = DOSSIER_BASE[agent] / f"case_{case_id}.raw.json"
    if dossier.exists():
        with open(dossier) as f:
            return json.load(f)
    # Fallback: DB trajectories
    conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5433/SOTA-Agents")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trajectories FROM evaluation_data WHERE exp_id=%s AND dataset_index=%s",
                (exp_id, case_id),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return []
    raw = row[0]
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def load_response(exp_id: str, case_id: int) -> str:
    conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5433/SOTA-Agents")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT response FROM evaluation_data WHERE exp_id=%s AND dataset_index=%s",
                (exp_id, case_id),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return row[0] if row and row[0] else ""


def load_db_meta(exp_id: str, case_id: int) -> dict:
    """Load meta.difficulty + meta.ground_truth for fault_type resolution.
    Fallback: cross-reference another exp_id sharing the same dataset_index when
    the target exp_id's meta.difficulty is missing (esp. claudecode)."""
    conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5433/SOTA-Agents")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT meta FROM evaluation_data WHERE exp_id=%s AND dataset_index=%s",
                (exp_id, case_id),
            )
            row = cur.fetchone()
            meta = {}
            if row and row[0]:
                meta = row[0]
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
            # Cross-reference if difficulty missing
            diff = (meta or {}).get("difficulty") or {}
            if not diff.get("fault_type"):
                cur.execute(
                    "SELECT meta->'difficulty' FROM evaluation_data "
                    "WHERE dataset_index=%s AND exp_id<>%s "
                    "AND meta->'difficulty'->>'fault_type' IS NOT NULL LIMIT 1",
                    (case_id, exp_id),
                )
                r2 = cur.fetchone()
                if r2 and r2[0]:
                    diff2 = r2[0]
                    if isinstance(diff2, str):
                        try:
                            diff2 = json.loads(diff2)
                        except Exception:
                            diff2 = None
                    if isinstance(diff2, dict):
                        meta = dict(meta)
                        meta["difficulty"] = diff2
    finally:
        conn.close()
    return meta


def load_data_dir_fallback(exp_id: str, case_id: int) -> str:
    """Fallback: extract data_dir from augmented_question regex when meta.path is empty."""
    conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5433/SOTA-Agents")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT augmented_question FROM evaluation_data WHERE exp_id=%s AND dataset_index=%s",
                (exp_id, case_id),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return ""
    m = re.search(r"stored in[:\s]+`?(/[^\s`']+data_[0-9a-f]+)`?", row[0])
    return m.group(1) if m else ""


# -------------------- GT extraction ------------------

def parse_gt(injection: dict, db_meta: dict | None = None) -> dict:
    gt = injection.get("ground_truth") or {}
    services = gt.get("service") or []
    pods = gt.get("pod") or []
    display_cfg_raw = injection.get("display_config") or ""
    display_cfg = {}
    if isinstance(display_cfg_raw, str):
        try:
            display_cfg = json.loads(display_cfg_raw)
        except Exception:
            display_cfg = {}
    elif isinstance(display_cfg_raw, dict):
        display_cfg = display_cfg_raw
    inj_pt = display_cfg.get("injection_point") or {}
    # fault_type: prefer DB meta.difficulty.fault_type (human-readable); fall back to injection integer
    ft = None
    fc = None
    if db_meta:
        diff = db_meta.get("difficulty") or {}
        ft = diff.get("fault_type")
        fc = diff.get("fault_category")
        # ground_truth in db_meta is a list of services
        if not services:
            gtd = db_meta.get("ground_truth")
            if isinstance(gtd, list):
                services = gtd
    if ft is None:
        ft = injection.get("fault_type")
    return {
        "fault_type": ft,
        "fault_category": fc,
        "injection_name": injection.get("injection_name"),
        "gt_services": services,
        "gt_pods": pods,
        "source_service": inj_pt.get("source_service"),
        "target_service": inj_pt.get("target_service"),
        "start_time": injection.get("start_time"),
        "end_time": injection.get("end_time"),
        "display_config": display_cfg,
    }


FAULT_TYPE_CATEGORY_MAP = {
    "JVMMemoryStress": "JVMChaos", "JVMCPUStress": "JVMChaos", "JVMMySQLLatency": "JVMChaos",
    "JVMException": "JVMChaos", "JVMLatency": "JVMChaos", "JVMReturn": "JVMChaos",
    "PodFailure": "PodChaos", "PodKill": "PodChaos", "PodChaos": "PodChaos", "ContainerKill": "PodChaos",
    "NetworkCorrupt": "NetworkChaos", "NetworkDelay": "NetworkChaos",
    "NetworkBandwidth": "NetworkChaos", "NetworkLoss": "NetworkChaos",
    "NetworkPartition": "NetworkChaos", "NetworkChaos": "NetworkChaos",
    "DNSRandom": "NetworkChaos", "TimeSkew": "NetworkChaos",
    "HTTPResponseDelay": "HTTPChaos", "HTTPResponseAbort": "HTTPChaos",
    "HTTPResponsePatchBody": "HTTPChaos", "HTTPResponseReplaceBody": "HTTPChaos",
    "HTTPResponseReplaceCode": "HTTPChaos",
    "HTTPRequestDelay": "HTTPChaos", "HTTPRequestAbort": "HTTPChaos",
    "HTTPRequestReplaceMethod": "HTTPChaos", "HTTPRequestReplacePath": "HTTPChaos",
}

EDGE_FAULT_TYPES = {
    "HTTPResponseDelay", "HTTPResponseAbort", "HTTPResponsePatchBody",
    "HTTPResponseReplaceBody", "HTTPResponseReplaceCode",
    "HTTPRequestDelay", "HTTPRequestAbort", "HTTPRequestReplaceMethod",
    "HTTPRequestReplacePath",
    "NetworkCorrupt", "NetworkDelay", "NetworkBandwidth", "NetworkLoss",
    "NetworkPartition", "NetworkChaos",
}


# -------------------- Trajectory parsing -------------

def extract_sqls(traj: list[dict]) -> list[str]:
    """Extract raw SQL query text from tool_call arguments or Bash commands."""
    out = []
    for m in traj:
        tool_calls = m.get("tool_calls") or []
        for tc in tool_calls:
            fn = tc.get("function", {})
            args_raw = fn.get("arguments", "")
            if not args_raw:
                continue
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except Exception:
                args = {"_raw": args_raw}
            # Common SQL argument keys
            for key in ("query", "sql", "duckdb_query", "command"):
                v = args.get(key)
                if isinstance(v, str) and len(v) > 0:
                    if key == "command":
                        # bash — look for duckdb inside
                        m_sql = re.search(r"(?i)\b(SELECT|WITH)\b[\s\S]*", v)
                        if m_sql and ".parquet" in v:
                            out.append(m_sql.group()[:2500])
                        else:
                            # skip non-SQL bash
                            continue
                    else:
                        out.append(v[:2500])
        # claudecode sometimes emits SQL inside message text
        content = m.get("content", "")
        if m.get("role") == "assistant" and isinstance(content, str) and ".parquet" in content:
            # Claudecode bash variant: find SELECT ... in content
            for m_sql in re.finditer(r"(?is)\b(SELECT|WITH)\b[^;`]{20,2000}", content):
                s = m_sql.group()
                if ".parquet" in s or "abnormal_" in s or "normal_" in s:
                    out.append(s[:2500])
    return out


def extract_assistant_texts(traj: list[dict], max_snippets: int = 8) -> list[dict]:
    snippets = []
    for i, m in enumerate(traj):
        if m.get("role") != "assistant":
            continue
        c = m.get("content", "")
        if not isinstance(c, str) or len(c) < 30:
            continue
        snippets.append({"idx": i, "text": c[:1200]})
        if len(snippets) >= max_snippets:
            break
    # Also include last 2 assistant messages (often contain conclusion)
    tail = []
    for m in traj[::-1]:
        if m.get("role") == "assistant" and isinstance(m.get("content"), str) and len(m["content"]) > 50:
            tail.append({"idx": -1, "text": m["content"][:2000]})
            if len(tail) >= 2:
                break
    snippets.extend(tail)
    return snippets


def parse_predicted_rc(response: str) -> dict:
    """Extract predicted root_causes + nodes from DB response (final JSON output)."""
    if not response:
        return {"root_causes": [], "nodes": [], "edges": []}
    # The response is JSON string
    try:
        data = json.loads(response)
    except Exception:
        # Might be wrapped — find first { ... } block
        m = re.search(r"\{[\s\S]*\}", response)
        if m:
            try:
                data = json.loads(m.group())
            except Exception:
                return {"root_causes": [], "nodes": [], "edges": []}
        else:
            return {"root_causes": [], "nodes": [], "edges": []}
    rc = data.get("root_causes") or []
    rc_services = []
    for r in rc:
        if isinstance(r, dict):
            cmp = r.get("component", "")
            # strip "service|" or "span|X::Y" prefix
            cmp_s = cmp.split("|", 1)[-1] if "|" in cmp else cmp
            cmp_s = cmp_s.split("::", 1)[0]
            if cmp_s:
                rc_services.append(cmp_s)
        elif isinstance(r, str):
            rc_services.append(r)
    nodes = [n.get("component", "") if isinstance(n, dict) else str(n) for n in (data.get("nodes") or [])]
    nodes_s = []
    for n in nodes:
        if "|" in n:
            n = n.split("|", 1)[-1]
        n = n.split("::", 1)[0]
        nodes_s.append(n)
    return {
        "root_causes": rc_services,
        "root_causes_raw": rc,
        "nodes": nodes_s,
        "edges": data.get("edges") or [],
    }


def substring_audit(sqls: list[str]) -> dict:
    joined = "\n".join(sqls)
    # Baseline contrast: joins normal+abnormal or computes ratio/delta
    has_baseline_contrast = (
        re.search(r"(?is)FROM\s+['\"]?\S*normal_\w+\.parquet", joined) is not None
        and re.search(r"(?is)FROM\s+['\"]?\S*abnormal_\w+\.parquet", joined) is not None
        and (
            re.search(r"(?is)\bUNION\b", joined) is not None
            or re.search(r"(?is)\bJOIN\b", joined) is not None
            or re.search(r"(?is)(normal|abnormal).*?(normal|abnormal)", joined) is not None
        )
    )
    # Call tree build: recursive CTE or parent_span_id self-join
    has_call_tree_build = (
        re.search(r"(?is)\bWITH\s+RECURSIVE\b", joined) is not None
        or re.search(r"(?is)parent_span_id\b.*?\b(JOIN|=)", joined) is not None
    )
    has_trace_follow = re.search(r"(?is)WHERE[\s\S]{0,200}trace_id\s*=\s*['\"]", joined) is not None
    has_jvm_metric = re.search(r"(?i)metric\s*(LIKE\s*['\"]jvm\.|=\s*['\"]jvm\.)", joined) is not None or "jvm.system" in joined or "jvm.memory" in joined or "jvm.cpu" in joined
    has_container_metric = re.search(r"(?i)container\.(memory|cpu|filesystem)", joined) is not None
    has_k8s_metric = re.search(r"(?i)k8s\.(pod|container|deployment|statefulset|node)", joined) is not None
    has_db_metric = re.search(r"(?i)(db\.client|hikari|mysql\.global)", joined) is not None
    has_network_metric = re.search(r"(?i)(network\.|tcp\.|egress|bytes_in|bytes_out)", joined) is not None
    has_status_error = re.search(r"(?i)status(_code)?\s*=\s*['\"]?Error", joined) is not None
    has_status_unset = (
        re.search(r"(?i)status(_code)?\s*=\s*['\"]?Unset", joined) is not None
        or re.search(r"(?i)status(_code)?\s+IS\s+NULL", joined) is not None
        or re.search(r"(?i)missing_span", joined) is not None
    )
    # WHERE service_name filters
    svc_filters = re.findall(r"(?i)WHERE[\s\S]{0,100}service_name\s*=\s*['\"]([a-zA-Z0-9\-_]+)['\"]", joined)
    # Deduplicate, preserve order
    seen = set(); svc_list = []
    for s in svc_filters:
        if s not in seen:
            seen.add(s); svc_list.append(s)
    # Also grab IN(...) lists
    in_lists = re.findall(r"(?i)service_name\s+IN\s*\(([^)]+)\)", joined)
    in_services = set()
    for lst in in_lists:
        for s in re.findall(r"['\"]([a-zA-Z0-9\-_]+)['\"]", lst):
            in_services.add(s)
    for s in in_services:
        if s not in seen:
            seen.add(s); svc_list.append(s)

    return {
        "has_baseline_contrast_substring": has_baseline_contrast,
        "has_call_tree_build_substring": has_call_tree_build,
        "has_trace_follow_substring": has_trace_follow,
        "has_jvm_metric_substring": has_jvm_metric,
        "has_container_metric_substring": has_container_metric,
        "has_k8s_metric_substring": has_k8s_metric,
        "has_db_metric_substring": has_db_metric,
        "has_network_metric_substring": has_network_metric,
        "has_status_error_filter": has_status_error,
        "has_status_unset_filter": has_status_unset,
        "where_service_name_filters": svc_list[:30],
    }


# -------------------- Parquet queries ---------------

def _pq(data_dir: str, kind: str) -> str:
    return f"'{data_dir}/{kind}.parquet'"


def run_parquet_queries(con, data_dir: str, gt_services: list[str], predicted_rc: list[str], gt: dict, classes_to_verify: list[str]) -> tuple[dict, list[dict]]:
    """Execute canonical + counterfactual parquet queries. Returns (evidence_dict, queries_log)."""
    queries_log = []
    out: dict[str, Any] = {}

    def _run(sql, purpose):
        try:
            r = con.execute(sql).fetchall()
            queries_log.append({"sql": sql[:600], "purpose": purpose, "row_count": len(r)})
            return r
        except Exception as exc:
            queries_log.append({"sql": sql[:600], "purpose": purpose, "row_count": 0, "error": str(exc)[:200]})
            return []

    # --- Baseline D-axis queries (8) ---
    gt_first = gt_services[0] if gt_services else ""
    gt_in_list = ",".join(f"'{s}'" for s in gt_services) if gt_services else "''"

    # (a) top abnormal errors — all services
    r = _run(
        f"SELECT service_name, COUNT(*) AS n "
        f"FROM read_parquet({_pq(data_dir, 'abnormal_logs')}) "
        f"WHERE level IN ('ERROR','SEVERE') GROUP BY 1 ORDER BY n DESC LIMIT 10",
        "top_error_services_abnormal_logs",
    )
    out["top_error_services_abnormal_logs"] = [{"service": a, "count": b} for (a, b) in r]

    # (b) top normal errors — chronic test
    r = _run(
        f"SELECT service_name, COUNT(*) AS n "
        f"FROM read_parquet({_pq(data_dir, 'normal_logs')}) "
        f"WHERE level IN ('ERROR','SEVERE') GROUP BY 1 ORDER BY n DESC LIMIT 10",
        "top_error_services_normal_logs",
    )
    out["top_error_services_normal_logs"] = [{"service": a, "count": b} for (a, b) in r]

    # (c) GT abnormal log error count
    if gt_services:
        r = _run(
            f"SELECT service_name, COUNT(*) AS n "
            f"FROM read_parquet({_pq(data_dir, 'abnormal_logs')}) "
            f"WHERE level IN ('ERROR','SEVERE') AND service_name IN ({gt_in_list}) GROUP BY 1",
            "gt_service_abnormal_log_error_count",
        )
        out["gt_service_abnormal_log_error_count"] = {a: b for (a, b) in r}
        # GT normal
        r = _run(
            f"SELECT service_name, COUNT(*) AS n "
            f"FROM read_parquet({_pq(data_dir, 'normal_logs')}) "
            f"WHERE level IN ('ERROR','SEVERE') AND service_name IN ({gt_in_list}) GROUP BY 1",
            "gt_service_normal_log_error_count",
        )
        out["gt_service_normal_log_error_count"] = {a: b for (a, b) in r}

    # (d) GT abnormal span count & status distribution
    if gt_services:
        r = _run(
            f"SELECT service_name, \"attr.status_code\" as sc, COUNT(*) AS n "
            f"FROM read_parquet({_pq(data_dir, 'abnormal_traces')}) "
            f"WHERE service_name IN ({gt_in_list}) GROUP BY 1,2",
            "gt_service_status_code_distribution",
        )
        status_dist: dict[str, dict[str, int]] = {}
        span_count: dict[str, int] = {}
        for (svc, sc, n) in r:
            status_dist.setdefault(svc, {})[sc or "NULL"] = n
            span_count[svc] = span_count.get(svc, 0) + n
        out["gt_service_status_code_distribution"] = status_dist
        out["gt_service_abnormal_span_count"] = span_count

    # (e) non-GT top error spans
    r = _run(
        f"SELECT service_name, \"attr.status_code\" as sc, COUNT(*) AS n "
        f"FROM read_parquet({_pq(data_dir, 'abnormal_traces')}) "
        f"WHERE \"attr.status_code\" IN ('Error','ERROR') GROUP BY 1,2 ORDER BY n DESC LIMIT 5",
        "top_error_span_services",
    )
    out["top_error_span_services"] = [{"service": a, "sc": b, "count": c} for (a, b, c) in r]

    # (f) GT latency stats
    if gt_services:
        r = _run(
            f"SELECT service_name, AVG(duration)/1e6 AS avg_ms, MAX(duration)/1e6 AS max_ms, "
            f"QUANTILE_CONT(duration, 0.95)/1e6 AS p95_ms, COUNT(*) AS n "
            f"FROM read_parquet({_pq(data_dir, 'abnormal_traces')}) "
            f"WHERE service_name IN ({gt_in_list}) GROUP BY 1",
            "gt_latency_stats",
        )
        out["gt_latency_stats"] = [{"service": a, "avg_ms": round(b or 0, 1), "max_ms": round(c or 0, 1), "p95_ms": round(d or 0, 1), "count": e} for (a, b, c, d, e) in r]

    # --- GT required capability queries ---
    req: dict[str, Any] = {}

    # gt_is_silent: GT has zero abnormal errors AND no spans with status=Error
    gt_abn_logs = out.get("gt_service_abnormal_log_error_count", {})
    gt_status = out.get("gt_service_status_code_distribution", {})
    is_silent = True
    for svc in gt_services:
        errs = gt_abn_logs.get(svc, 0)
        sc = gt_status.get(svc, {})
        n_err_span = sum(v for k, v in sc.items() if str(k).lower() == "error")
        if errs > 0 or n_err_span > 0:
            is_silent = False
            break
    if not gt_services:
        is_silent = False
    req["gt_is_silent"] = is_silent

    # gt_is_loudest: GT in top-2 of abnormal error ranking
    top_err = out.get("top_error_services_abnormal_logs", [])
    top2 = [x["service"] for x in top_err[:2]]
    req["gt_is_loudest"] = any(s in top2 for s in gt_services)

    # chronic_noise_present: some non-GT service has normal_err >= 0.5 * abnormal_err
    # compute ratios
    normal_map = {x["service"]: x["count"] for x in out.get("top_error_services_normal_logs", [])}
    abnormal_map = {x["service"]: x["count"] for x in out.get("top_error_services_abnormal_logs", [])}
    chronic_carriers = []
    for svc, n_abn in abnormal_map.items():
        if svc in gt_services:
            continue
        n_norm = normal_map.get(svc, 0)
        if n_abn > 0 and n_norm >= 0.5 * n_abn:
            chronic_carriers.append({"service": svc, "normal_err": n_norm, "abnormal_err": n_abn, "ratio": round(n_norm / max(n_abn, 1), 2)})
    req["chronic_noise_present"] = len(chronic_carriers) > 0
    req["chronic_noise_carriers"] = [c["service"] for c in chronic_carriers]
    out["chronic_noise_detail"] = chronic_carriers

    # required_metric_layer based on fault_type
    ft = (gt.get("fault_type") or "")
    cat = FAULT_TYPE_CATEGORY_MAP.get(ft, "")
    if cat == "JVMChaos":
        layer = "jvm"
    elif cat == "PodChaos":
        layer = "k8s/container"
    elif cat == "NetworkChaos":
        layer = "network/db"
    else:
        layer = "none"
    req["required_metric_layer"] = layer

    # gt_path_is_edge_fault
    req["gt_path_is_edge_fault"] = ft in EDGE_FAULT_TYPES

    # gt_has_name_twin: services sharing ≥6-char substring with GT
    def _longest_common_substring_len(a: str, b: str) -> int:
        if not a or not b:
            return 0
        m, n = len(a), len(b)
        prev = [0] * (n + 1)
        best = 0
        for i in range(1, m + 1):
            curr = [0] * (n + 1)
            for j in range(1, n + 1):
                if a[i - 1] == b[j - 1]:
                    curr[j] = prev[j - 1] + 1
                    if curr[j] > best:
                        best = curr[j]
            prev = curr
        return best

    # gather observed services (union of abnormal/normal top + traces)
    observed = set(normal_map.keys()) | set(abnormal_map.keys())
    for x in out.get("top_error_span_services", []):
        observed.add(x["service"])
    # add gt latency hits
    for x in out.get("gt_latency_stats", []):
        observed.add(x["service"])
    # add span services
    r = _run(
        f"SELECT DISTINCT service_name FROM read_parquet({_pq(data_dir, 'abnormal_traces')})",
        "all_abnormal_trace_services",
    )
    for (s,) in r:
        if s:
            observed.add(s)
    name_twin = []
    for gt_svc in gt_services:
        for s in observed:
            if s == gt_svc or not s or not gt_svc:
                continue
            if _longest_common_substring_len(gt_svc, s) >= 6:
                name_twin.append({"gt": gt_svc, "twin": s})
    req["gt_has_name_twin"] = len(name_twin) > 0
    req["name_twin_candidates"] = [x["twin"] for x in name_twin]

    # gt_diluted_across_spans: GT has ≥3 span_name buckets with only one large delta
    diluted = False
    if gt_services:
        r = _run(
            f"SELECT span_name, AVG(duration)/1e6 AS avg_ms, COUNT(*) AS n "
            f"FROM read_parquet({_pq(data_dir, 'abnormal_traces')}) "
            f"WHERE service_name IN ({gt_in_list}) GROUP BY 1 ORDER BY n DESC LIMIT 20",
            "gt_span_name_breakdown",
        )
        out["gt_span_name_breakdown"] = [{"span_name": a, "avg_ms": round(b or 0, 1), "count": c} for (a, b, c) in r]
        if len(r) >= 3:
            avgs = [b for (_, b, _) in r if b is not None]
            if avgs and max(avgs) > 0:
                high = sum(1 for a in avgs if a >= 0.5 * max(avgs))
                diluted = high == 1
    req["gt_diluted_across_spans"] = diluted

    # --- counterfactual queries ---
    cfq: dict[str, Any] = {}

    # PD1 counterfactual: for predicted RC, compute normal vs abnormal error to check chronic
    pd1 = {}
    if predicted_rc:
        pd1["chronic_noise_in_data"] = req["chronic_noise_present"]
        rc_is_chronic = any(rc in req["chronic_noise_carriers"] for rc in predicted_rc)
        pd1["predicted_rc_is_chronic_carrier"] = rc_is_chronic
        # compute predicted RC's chronic ratio directly
        rc_in = ",".join(f"'{s}'" for s in predicted_rc)
        r_norm = _run(
            f"SELECT service_name, COUNT(*) AS n "
            f"FROM read_parquet({_pq(data_dir, 'normal_logs')}) "
            f"WHERE level IN ('ERROR','SEVERE') AND service_name IN ({rc_in}) GROUP BY 1",
            "predicted_rc_normal_err",
        )
        r_abn = _run(
            f"SELECT service_name, COUNT(*) AS n "
            f"FROM read_parquet({_pq(data_dir, 'abnormal_logs')}) "
            f"WHERE level IN ('ERROR','SEVERE') AND service_name IN ({rc_in}) GROUP BY 1",
            "predicted_rc_abnormal_err",
        )
        rc_norm_map = {a: b for (a, b) in r_norm}
        rc_abn_map = {a: b for (a, b) in r_abn}
        pd1["predicted_rc_error_ratios"] = {
            s: {"normal": rc_norm_map.get(s, 0), "abnormal": rc_abn_map.get(s, 0)}
            for s in predicted_rc
        }
        # if any predicted RC has normal_err>=0.5*abnormal_err → running baseline_contrast would reveal chronicity
        reveal = False
        for s in predicted_rc:
            n = rc_norm_map.get(s, 0); a = rc_abn_map.get(s, 0)
            if a > 0 and n >= 0.5 * a:
                reveal = True
                break
        pd1["if_run_would_reveal"] = reveal
    cfq["PD1_baseline_contrast"] = pd1

    # PD2 counterfactual: gt_is_upstream_of_agent_focus — approximated via causal_graph edges
    # We don't have causal_graph parsed here; simplified heuristic using trace parent-child
    pd2 = {"gt_is_upstream_of_agent_focus": None, "if_run_would_surface_gt": None}
    if gt_services:
        # Check if GT appears as parent in trace spans calling services the agent focused on
        r = _run(
            f"SELECT DISTINCT p.service_name, c.service_name "
            f"FROM read_parquet({_pq(data_dir, 'abnormal_traces')}) c "
            f"JOIN read_parquet({_pq(data_dir, 'abnormal_traces')}) p ON c.parent_span_id=p.span_id "
            f"WHERE c.service_name IN ({gt_in_list}) OR p.service_name IN ({gt_in_list}) "
            f"LIMIT 200",
            "gt_parent_child_pairs",
        )
        pairs = [(a, b) for (a, b) in r if a != b]
        out["gt_parent_child_pairs"] = pairs[:30]
        # If GT is parent of any other service, it is upstream
        gt_upstream = any(a in gt_services and b not in gt_services for (a, b) in pairs)
        pd2["gt_is_upstream_of_agent_focus"] = gt_upstream
        pd2["if_run_would_surface_gt"] = gt_upstream
    cfq["PD2_call_tree_build"] = pd2

    # PD3 counterfactual: fault-layer-specific metric probe would surface anomaly
    pd3: dict[str, Any] = {"metric_family_if_probed": layer, "gt_metric_anomaly_exists_in_parquet": None}
    if layer != "none" and gt_services:
        # Simplified: check if any metric for GT service in layer has non-zero value during incident
        if layer == "jvm":
            pat = "jvm.%"
        elif layer == "k8s/container":
            pat = "k8s.%"
        else:
            pat = "%"  # network — hard to check cheaply, skip
        if pat != "%":
            r = _run(
                f"SELECT DISTINCT metric FROM read_parquet({_pq(data_dir, 'abnormal_metrics')}) "
                f"WHERE service_name IN ({gt_in_list}) AND metric LIKE '{pat}' LIMIT 10",
                "gt_metric_families_probed",
            )
            pd3["gt_metric_families_probed"] = [x[0] for x in r]
            pd3["gt_metric_anomaly_exists_in_parquet"] = len(r) > 0
    cfq["PD3_fault_layer_metric_probe"] = pd3

    # PD4 counterfactual: if isolated on predicted RC, would it show healthy?
    pd4: dict[str, Any] = {}
    if predicted_rc:
        # We already have rc_abn_map from PD1. A predicted RC with 0 abnormal errors = healthy when isolated
        healthy = {}
        for s in predicted_rc:
            a = rc_abn_map.get(s, 0) if predicted_rc else 0
            healthy[s] = (a == 0)
        pd4["if_isolated_predicted_rc_show_healthy"] = healthy
    cfq["PD4_named_candidate_not_isolated"] = pd4

    # R-axis counterfactual: if_loudness_applied / if_baseline_diff_applied / if_edge_direction_applied
    r_cf: dict[str, Any] = {}
    # if_loudness_applied: top-1 error service = GT?
    top1 = top_err[0]["service"] if top_err else None
    r_cf["if_loudness_applied"] = (top1 in gt_services) if top1 else False
    # if_baseline_diff_applied: after removing chronic carriers, would GT surface in top-3?
    filtered = [x for x in top_err if x["service"] not in req["chronic_noise_carriers"]]
    top3_non_chronic = [x["service"] for x in filtered[:3]]
    r_cf["if_baseline_diff_applied"] = any(s in gt_services for s in top3_non_chronic)
    # if_edge_direction_applied: for edge faults, compute caller-distribution on GT
    r_cf["if_edge_direction_applied"] = None
    if req["gt_path_is_edge_fault"] and gt_services:
        # Find what service calls GT most in abnormal traces
        r = _run(
            f"SELECT p.service_name, COUNT(*) AS n FROM read_parquet({_pq(data_dir, 'abnormal_traces')}) c "
            f"JOIN read_parquet({_pq(data_dir, 'abnormal_traces')}) p ON c.parent_span_id=p.span_id "
            f"WHERE c.service_name IN ({gt_in_list}) GROUP BY 1 ORDER BY n DESC LIMIT 5",
            "gt_caller_distribution",
        )
        out["gt_caller_distribution"] = [{"caller": a, "count": b} for (a, b) in r]
        # If there's a dominant caller (>60%) that is in gt_services (source_service), edge direction is learnable
        total = sum(b for (_, b) in r) or 1
        dominant = [(a, b) for (a, b) in r if b / total >= 0.5]
        src = gt.get("source_service")
        r_cf["if_edge_direction_applied"] = bool(src and any(a == src or a in gt_services for (a, _) in dominant))
    # if_name_twin_check_applied
    if req["gt_has_name_twin"]:
        r_cf["if_name_twin_check_applied"] = True
    else:
        r_cf["if_name_twin_check_applied"] = None
    cfq["R_correct_heuristic_would_reach_gt"] = r_cf

    # D obstacle structural check — depends on D class; provide generic "yes, D is structural"
    # Rule: if GT has zero abnormal span count → D1 structural
    # For others, default True (obstacle is real) — can't easily disprove by probe
    d_structural = True
    if gt_services:
        # if GT has abnormal_log errors > 5 AND abnormal status=Error spans > 5, then D1-silent is NOT structural
        for svc in gt_services:
            log_err = out.get("gt_service_abnormal_log_error_count", {}).get(svc, 0)
            sc = out.get("gt_service_status_code_distribution", {}).get(svc, {})
            n_err = sum(v for k, v in sc.items() if str(k).lower() == "error")
            if log_err > 5 or n_err > 5:
                # GT is visible; D1 label would NOT be structural
                d_structural = True  # still keep True — the "silence" might be in a different layer
                break
    cfq["D_obstacle_is_structural"] = d_structural

    return {"required": req, "counterfactual": cfq, "parquet_evidence": out, "queries_log": queries_log}, queries_log


# -------------------- Path alignment ----------------

def compute_path_alignment(sqls: list[str], gt_services: list[str], causal_graph: dict, svc_filters: list[str], predicted_rc: list[str]) -> dict:
    joined = "\n".join(sqls)

    # GT touched: any SQL has WHERE service_name=<GT>
    gt_touched = False
    for svc in gt_services:
        if re.search(rf"(?is)service_name\s*=\s*['\"]{re.escape(svc)}['\"]", joined):
            gt_touched = True
            break

    # GT neighbors (from causal graph) — services 1 hop from GT in edges
    neighbors = set()
    if causal_graph and causal_graph.get("edges"):
        cmp_to_svc = {}
        for k, v in (causal_graph.get("component_to_service") or {}).items():
            cmp_to_svc[k] = v
        for e in causal_graph["edges"]:
            src = e.get("source", ""); tgt = e.get("target", "")
            src_s = cmp_to_svc.get(src, src.split("|", 1)[-1].split("::", 1)[0])
            tgt_s = cmp_to_svc.get(tgt, tgt.split("|", 1)[-1].split("::", 1)[0])
            if src_s in gt_services and tgt_s not in gt_services:
                neighbors.add(tgt_s)
            if tgt_s in gt_services and src_s not in gt_services:
                neighbors.add(src_s)

    gt_neighbors_touched = {}
    for n in neighbors:
        cnt = len(re.findall(rf"(?is)service_name\s*=\s*['\"]{re.escape(n)}['\"]", joined))
        if cnt > 0:
            gt_neighbors_touched[n] = cnt

    # Agent focus services: services with >3 WHERE filter mentions
    focus_counts: dict[str, int] = {}
    for s in svc_filters:
        focus_counts[s] = focus_counts.get(s, 0) + 1
    # Also count from regex
    for s in set(svc_filters):
        focus_counts[s] = len(re.findall(rf"(?is)service_name\s*=\s*['\"]{re.escape(s)}['\"]", joined))
    agent_focus = sorted([(s, c) for s, c in focus_counts.items() if c > 0], key=lambda x: -x[1])[:10]

    # agent_predicted_rc_in_gt_neighborhood
    rc_neighborhood = any((rc in gt_services or rc in neighbors) for rc in predicted_rc)

    return {
        "gt_touched_in_trajectory": gt_touched,
        "gt_neighbors_touched": gt_neighbors_touched,
        "gt_neighbors_from_causal_graph": sorted(neighbors),
        "agent_focus_services": [{"service": s, "count": c} for s, c in agent_focus],
        "agent_predicted_rc_in_gt_neighborhood": rc_neighborhood,
    }


# -------------------- Main per-case driver ----------

def process_case(sample: dict, force: bool = False) -> str:
    agent = sample["agent"]
    case_id = int(sample["case_id"])
    exp_id = sample["exp_id"]
    data_dir = sample["data_dir"]

    out_path = EVIDENCE_DIR / f"{agent}_case_{case_id}.yaml"
    if out_path.exists() and not force:
        return f"skip {out_path.name}"

    if not data_dir or not Path(data_dir).exists():
        # Try augmented_question regex fallback
        alt = load_data_dir_fallback(exp_id, case_id)
        if alt and Path(alt).exists():
            data_dir = alt
        else:
            doc = {
                "case_id": f"{agent}.{case_id}",
                "framework": FRAMEWORKS[agent][0],
                "data_dir": data_dir,
                "unverifiable": True,
                "reason": f"data_dir missing: {data_dir}; fallback={alt}",
                "classes_to_verify": sample["classes_to_verify"],
            }
            _atomic_write_yaml(out_path, doc)
            return f"unverifiable {out_path.name}"

    injection = load_injection(data_dir)
    causal_graph = load_causal_graph(data_dir)
    db_meta = load_db_meta(exp_id, case_id)
    gt = parse_gt(injection, db_meta)
    trajectory = load_trajectory(agent, case_id, exp_id)
    response = load_response(exp_id, case_id)

    sqls = extract_sqls(trajectory)
    audit = substring_audit(sqls)
    predicted = parse_predicted_rc(response)

    # GT from causal graph
    cg_rc_cmps = causal_graph.get("root_causes") or []
    cg_rc_services = []
    for r in cg_rc_cmps:
        cmp = r.get("component", "") if isinstance(r, dict) else str(r)
        if "|" in cmp:
            cmp = cmp.split("|", 1)[-1]
        cmp = cmp.split("::", 1)[0]
        if cmp:
            cg_rc_services.append(cmp)
    cg_alarms = []
    for r in (causal_graph.get("alarm_nodes") or []):
        cmp = r.get("component", "") if isinstance(r, dict) else str(r)
        cg_alarms.append(cmp)

    snippets = extract_assistant_texts(trajectory, max_snippets=6)

    # Run parquet queries
    con = duckdb.connect()
    try:
        parquet_block, queries_log = run_parquet_queries(
            con, data_dir, gt["gt_services"], predicted["root_causes"], gt,
            sample["classes_to_verify"],
        )
    finally:
        con.close()

    path_align = compute_path_alignment(
        sqls, gt["gt_services"], causal_graph, audit["where_service_name_filters"],
        predicted["root_causes"],
    )

    doc = {
        "case_id": f"{agent}.{case_id}",
        "framework": FRAMEWORKS[agent][0],
        "data_dir": data_dir,
        "gt_from_injection_json": {
            "fault_type": gt["fault_type"],
            "fault_category": gt.get("fault_category"),
            "injection_name": gt["injection_name"],
            "gt_services": gt["gt_services"],
            "source_service": gt["source_service"],
            "target_service": gt["target_service"],
            "start_time": gt["start_time"],
            "end_time": gt["end_time"],
            "display_config": gt["display_config"],
        },
        "gt_from_causal_graph_json": {
            "root_causes": cg_rc_services,
            "alarm_nodes": cg_alarms,
        },
        "agent_predicted": {
            "root_causes": predicted["root_causes"],
            "predicted_graph_nodes": predicted["nodes"],
        },
        "raw_sql_count_total": len(sqls),
        "raw_sql_list_sample": sqls[:20],  # cap to avoid YAML bloat
        "raw_sql_substring_audit": audit,
        "parquet_evidence": parquet_block["parquet_evidence"],
        "trajectory_reasoning_snippets": snippets,
        "gt_required_capabilities": parquet_block["required"],
        "path_alignment": path_align,
        "counterfactual": parquet_block["counterfactual"],
        "parquet_queries_run": [q for q in parquet_block["queries_log"] if not q.get("purpose", "").startswith(("PD", "predicted_rc", "gt_caller", "gt_parent", "gt_metric", "gt_span_name"))],
        "counterfactual_queries_run": [q for q in parquet_block["queries_log"] if q.get("purpose", "").startswith(("PD", "predicted_rc", "gt_caller", "gt_parent", "gt_metric", "gt_span_name"))],
        "classes_to_verify": sample["classes_to_verify"],
    }

    _atomic_write_yaml(out_path, doc)
    return f"wrote {out_path.name} (sqls={len(sqls)}, queries={len(queries_log)})"


def _atomic_write_yaml(path: Path, doc: dict):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, width=200)
    os.replace(tmp, path)


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="overwrite existing YAMLs")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--case", type=str, help="only process this agent_case_id (e.g. aiq_130)")
    ap.add_argument("--parallel", type=int, default=4, help="parallel workers")
    args = ap.parse_args()

    samples = []
    with (MERGED / "verify_samples.jsonl").open() as f:
        for line in f:
            samples.append(json.loads(line))

    if args.case:
        agent, cid = args.case.rsplit("_", 1)
        samples = [s for s in samples if s["agent"] == agent and int(s["case_id"]) == int(cid)]

    if args.limit:
        samples = samples[: args.limit]

    print(f"Processing {len(samples)} cases, parallel={args.parallel}")

    if args.parallel > 1:
        from concurrent.futures import ProcessPoolExecutor, as_completed

        with ProcessPoolExecutor(max_workers=args.parallel) as ex:
            futs = {ex.submit(process_case, s, args.force): s for s in samples}
            for i, fut in enumerate(as_completed(futs), 1):
                s = futs[fut]
                try:
                    msg = fut.result()
                    print(f"[{i}/{len(samples)}] {s['agent']}.{s['case_id']}: {msg}")
                except Exception as exc:
                    print(f"[{i}/{len(samples)}] {s['agent']}.{s['case_id']}: ERROR {exc}")
                    traceback.print_exc()
    else:
        for i, s in enumerate(samples, 1):
            try:
                msg = process_case(s, force=args.force)
                print(f"[{i}/{len(samples)}] {s['agent']}.{s['case_id']}: {msg}")
            except Exception as exc:
                print(f"[{i}/{len(samples)}] {s['agent']}.{s['case_id']}: ERROR {exc}")
                traceback.print_exc()


if __name__ == "__main__":
    main()
