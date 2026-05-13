#!/usr/bin/env python
"""Scan pending TRACES with `trace_id IN (subquery)` but NO parent_span_id in
outer SELECT (those WITH parent_span_id were handled by user_subquery_trace_tree).

Categorize by outer features and show LLM votes to decide intent.
"""
import json
import re
import sys
from collections import Counter

from sqlalchemy import create_engine, text

sys.path.insert(0, str(__file__).rsplit("/scripts/", 1)[0])
from sota_rca.analysis.llm_intent_classifier import extract_sql_rounds  # noqa: E402
from sota_rca.analysis.trajectory_normalizer import normalize_by_agent  # noqa: E402

EXPS = [
    "thinkdepthai-claude-sonnet-4.6",
    "thinkdepthai-qwen3.5-plus",
    "aiq-qwen3.5-plus",
    "claudecode-qwen3.5-plus",
    "taskweaver-qwen3.5-plus",
]
DB_URL = "postgresql://postgres:postgres@localhost:5433/SOTA-Agents"
VOTE_KEYS = ["claude_opus_4_6", "gemini_3_1_pro_preview", "claude_opus_4_7_arbiter", "claude_opus_4_6_arbiter"]


def flatten_subq(sql: str) -> str:
    u = sql.upper()
    i = 0
    depth = 0
    start = -1
    while i < len(u):
        c = u[i]
        if c == "(":
            if depth == 0:
                start = i
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0 and start >= 0:
                if "SELECT" in u[start + 1 : i]:
                    u = u[:start] + " __SUBQ__ " + u[i + 1 :]
                    i = start + len(" __SUBQ__ ") - 1
                    start = -1
                else:
                    start = -1
        i += 1
    return u


def categorize(sql: str) -> tuple[str, dict]:
    u = flatten_subq(sql)

    # FROM abnormal/bare traces only
    if not re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,120}?ABNORMAL_TRACES\b|\b(?:FROM|JOIN)\s+TRACES\b",
                     u, re.DOTALL):
        return "not traces", {}
    if re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,120}?(?<!AB)NORMAL_TRACES\b", u, re.DOTALL):
        return "normal_traces", {}

    wm = re.search(r"\bWHERE\b(.*?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|\bUNION\b|\bHAVING\b|$)",
                   u, re.DOTALL)
    where = wm.group(1) if wm else ""

    # Must have trace_id IN (subquery)
    if not re.search(r"\bTRACE_ID\s+IN\s*\(?\s*__SUBQ__", where):
        return "no trace_id IN(sub)", {}

    sel_from = re.search(r"\bSELECT\b(.*?)\bFROM\b", u, re.DOTALL)
    sel = sel_from.group(1) if sel_from else ""
    has_parent_id = "PARENT_SPAN_ID" in sel
    has_span_id = bool(re.search(r"(?<!_)\bSPAN_ID\b(?!\s*[A-Z_])", sel))

    # Skip: has parent_span_id (already handled by previous rule)
    if has_parent_id:
        return "has parent_span_id (prev rule)", {}

    # Feature detection on outer
    has_group_by = bool(re.search(r"\bGROUP\s+BY\b", u))
    has_count = bool(re.search(r"\bCOUNT\s*\(", sel))
    has_dur_agg = bool(re.search(r"(AVG|MAX|MIN|SUM)\s*\(\s*DURATION", sel))
    has_minmax_time = bool(re.search(r"(MIN|MAX)\s*\(\s*TIME", sel))
    ob_m = re.search(r"\bORDER\s+BY\s+(.*?)(?:\bLIMIT\b|\bUNION\b|$)", u, re.DOTALL)
    ob = ob_m.group(1) if ob_m else ""
    order_duration = bool(re.search(r"\bDURATION\b", ob))
    has_msg_like = bool(re.search(r"\b(MESSAGE|SPAN_NAME)\s*(NOT\s+)?LIKE", where))
    has_svc_eq = bool(re.search(r"\bSERVICE_NAME\s*=\s*['\"]", where))
    has_svc_in = bool(re.search(r"\bSERVICE_NAME\s+IN\s*\(", where))
    has_svc_neq = bool(re.search(r"\bSERVICE_NAME\s*(!=|<>)\s*['\"]|\bSERVICE_NAME\s+NOT\s+IN", where))
    err_filter = bool(re.search(r"ATTR_STATUS_CODE\s*(=|IN)\s*['\"]?ERROR", where, re.IGNORECASE)) \
        or bool(re.search(r"ATTR_HTTP_RESPONSE_STATUS_CODE\s*(=|IN|>=)\s*['\"]?[45]", where))

    feats = {
        "has_span_id": has_span_id, "has_msg_like": has_msg_like,
        "has_svc_eq": has_svc_eq, "has_svc_in": has_svc_in, "has_svc_neq": has_svc_neq,
        "has_group_by": has_group_by, "has_count": has_count,
        "has_dur_agg": has_dur_agg, "has_minmax_time": has_minmax_time,
        "order_duration": order_duration, "err_filter": err_filter,
    }

    # Classification (no write — show only)
    if has_minmax_time:
        cat = "minmax_time"
    elif has_msg_like:
        cat = "msg_like"
    elif has_group_by and has_count and not has_dur_agg:
        cat = "groupby_count_only"
    elif has_group_by and has_dur_agg:
        cat = "groupby_duration"
    elif has_group_by:
        cat = "groupby_other"
    elif err_filter:
        cat = "outer_err_filter"
    elif has_svc_eq or has_svc_in or has_svc_neq:
        cat = "outer_svc_filter"
    elif order_duration or has_dur_agg:
        cat = "order_duration"
    else:
        cat = "pure (no outer filter)"
    return cat, feats


def main() -> None:
    eng = create_engine(DB_URL)
    total_pending = 0
    cat_counter: Counter = Counter()
    votes_by_cat: dict[str, Counter] = {}
    examples: dict[str, list[dict]] = {}
    skip_counter: Counter = Counter()

    with eng.connect() as c:
        for exp in EXPS:
            agent = exp.split("-", 1)[0]
            rows = c.execute(
                text("SELECT dataset_index, trajectories, meta FROM evaluation_data "
                     "WHERE exp_id=:e AND stage='judged'"),
                {"e": exp},
            ).fetchall()
            for idx, traj_raw, meta_raw in rows:
                traj = json.loads(traj_raw) if isinstance(traj_raw, str) else traj_raw
                meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
                if not traj or not meta:
                    continue
                finals = (meta.get("llm_intents") or {}).get("final", [])
                done = {(e["round"], e["sql_index"]) for e in finals}
                try:
                    norm = normalize_by_agent(agent, traj)
                    rounds = extract_sql_rounds(norm)
                except Exception:
                    continue
                llm = meta.get("llm_intents") or {}

                def v_at(key, r, si):
                    for e in llm.get(key, []) or []:
                        if e.get("round") == r and e.get("sql_index") == si:
                            return e.get("intent")
                    return None

                for rnd in rounds:
                    for si0, sql in enumerate(rnd.queries):
                        si = si0 + 1
                        pos = (rnd.round_index, si)
                        if pos in done:
                            continue
                        total_pending += 1
                        cat, feats = categorize(sql)
                        # Skip non-target cases
                        if cat in {"not traces", "normal_traces", "no trace_id IN(sub)",
                                   "has parent_span_id (prev rule)"}:
                            skip_counter[cat] += 1
                            continue
                        cat_counter[cat] += 1
                        votes = {vk: v_at(vk, *pos) for vk in VOTE_KEYS}
                        votes_by_cat.setdefault(cat, Counter())
                        for v in votes.values():
                            if v:
                                votes_by_cat[cat][v] += 1
                        examples.setdefault(cat, [])
                        if len(examples[cat]) < 3:
                            examples[cat].append({"exp": exp, "idx": idx, "pos": pos, "sql": sql, "votes": votes})

    print(f"Total pending scanned: {total_pending}")
    print(f"\nSub-category distribution (target set: trace_id IN subquery, NO parent_span_id):")
    for cat, n in cat_counter.most_common():
        votes = votes_by_cat.get(cat, Counter())
        top3 = ", ".join(f"{i}:{c}" for i, c in votes.most_common(4))
        print(f"  {cat:<28} {n:>4}   LLM_votes: {top3}")
    print(f"\nSkipped:")
    for cat, n in skip_counter.most_common():
        print(f"  {cat}: {n}")
    print(f"\n=== Sample SQLs (up to 3 per category) ===")
    for cat, exs in sorted(examples.items(), key=lambda x: -cat_counter[x[0]]):
        print(f"\n--- [{cat}] ({cat_counter[cat]} SQLs) ---")
        for ex in exs:
            print(f"  {ex['exp']} case={ex['idx']} pos={ex['pos']}")
            print(f"  votes={ex['votes']}")
            print(f"  SQL: {ex['sql'][:300].replace(chr(10), ' ')}")


if __name__ == "__main__":
    main()
