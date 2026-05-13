#!/usr/bin/env python
"""Final sweep: comprehensive classification of all remaining pending SQLs.

Combines all established rules + LLM vote confidence. For each pending SQL:
  - Apply rule-based classification (all our rules)
  - Check LLM vote majority
  - Only commit if rule-intent == 3/4 LLM majority, OR LLM 4/4 unanimous
  - Otherwise: collect for user review

Output:
  - committed: rule + ≥3 votes match
  - ambiguous: everything else (save as JSON report for user review)
"""
import argparse
import json
import re
import sys
from collections import Counter

from sqlalchemy import create_engine, text
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session

sys.path.insert(0, str(__file__).rsplit("/scripts/", 1)[0])
from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402
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


def flatten_subq(sql: str) -> tuple[str, list[str]]:
    u = sql.upper()
    subs: list[str] = []
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
                inner = u[start + 1 : i]
                if "SELECT" in inner:
                    subs.append(inner)
                    u = u[:start] + " __SUBQ__ " + u[i + 1 :]
                    i = start + len(" __SUBQ__ ") - 1
                    start = -1
                else:
                    start = -1
        i += 1
    return u, subs


def extract_where(u: str) -> str:
    def _mask(m):
        return "'" + "_" * (len(m.group(0)) - 2) + "'"
    masked = re.sub(r"'[^']*'", _mask, u)
    wm = re.search(r"\bWHERE\b(.*?)(?:\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|\bUNION\b|\bHAVING\b|$)",
                   masked, re.DOTALL)
    return u[wm.span(1)[0]:wm.span(1)[1]] if wm else ""


def rule_classify(sql: str) -> str | None:
    """Apply all established rules. Return intent or None if no rule matches."""
    u, subs = flatten_subq(sql)
    where = extract_where(u)
    sel_m = re.search(r"\bSELECT\b(.*?)\bFROM\b", u, re.DOTALL)
    sel = sel_m.group(1) if sel_m else ""

    # modality
    has_ab_logs = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,120}?ABNORMAL_LOGS\b", u, re.DOTALL))
    has_ab_traces = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,120}?ABNORMAL_TRACES\b", u, re.DOTALL))
    has_bare_traces = bool(re.search(r"\b(?:FROM|JOIN)\s+TRACES\b", u))
    has_ab_metric = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,160}?ABNORMAL_METRICS(?:_HISTOGRAM|_SUM)?\b", u, re.DOTALL))
    has_nm_logs = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,120}?(?<!AB)NORMAL_LOGS\b", u, re.DOTALL))
    has_nm_traces = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,120}?(?<!AB)NORMAL_TRACES\b", u, re.DOTALL))
    has_nm_metric = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,160}?(?<!AB)NORMAL_METRICS", u, re.DOTALL))
    has_nm = has_nm_logs or has_nm_traces or has_nm_metric
    has_ab = has_ab_logs or has_ab_traces or has_ab_metric or has_bare_traces

    # baseline
    if has_nm and has_ab:
        return "baseline_contrast"
    if has_nm and not has_ab:
        return "baseline_collect"

    # self-join / topology
    has_self_join = bool(re.search(
        r"\bPARENT_SPAN_ID\s*=\s*\w*\.?SPAN_ID\b|\bSPAN_ID\s*=\s*\w*\.?PARENT_SPAN_ID\b",
        u))

    # ==== LOGS ====
    if has_ab_logs and not has_ab_traces and not has_ab_metric:
        has_msg_like = bool(re.search(r"\bMESSAGE\s*(NOT\s+)?LIKE", where))
        svc_like_n = len(re.findall(r"\bSERVICE_NAME\s+LIKE\s+['\"]", where))
        has_svc = bool(re.search(r"\bSERVICE_NAME\s*(=|IN|!=|<>|NOT\s+IN)", where))
        has_level = bool(re.search(r"\bLEVEL\s*(=|IN|!=|<>|NOT\s+IN)", where))
        if has_msg_like: return "keyword_search"
        if svc_like_n >= 2: return "keyword_search"
        if svc_like_n == 1: return "service_error_log"
        if has_svc: return "service_error_log" if has_level else "service_log_browse"
        if re.search(r"(MIN|MAX)\s*\(\s*TIME", sel):
            return "error_timeline"
        return "error_log_overview"

    # ==== METRICS ====
    if has_ab_metric and not has_ab_logs and not has_ab_traces:
        # metric literals
        lits: list[str] = []
        for m in re.finditer(r"\bMETRIC\s*(?:=|LIKE)\s*'([^']+)'", where):
            lits.append(m.group(1))
        for m in re.finditer(r"\bMETRIC\s+IN\s*\(([^)]+)\)", where):
            lits.extend(re.findall(r"'([^']+)'", m.group(1)))
        def dom(lit):
            l = lit.upper()
            if re.search(r"\bJVM\b|\bGC\b|THREAD|HEAP|HIKARI", l): return "jvm_state"
            if re.search(r"\bDB\b|MYSQL|\bCONN\b|\bSQL\b", l): return "db_state"
            if re.search(r"HTTP|\bNET\b|NETWORK|\bTCP\b|HUBBLE|PACKET|\bDROP\b|LATENCY|DURATION|REQUEST", l):
                return "network_layer"
            if re.search(r"CPU|MEMORY|\bMEM\b|OOM|FILESYSTEM|\bDISK\b", l): return "container_resource"
            if re.search(r"RESTART|\bKILL\b|\bPHASE\b|READY|TERMINAT|EVICT|DEPLOY|\bPOD\b", l):
                return "k8s_state"
            return None
        if lits:
            counts = Counter(d for d in (dom(l) for l in lits) if d)
            if len(counts) == 1:
                return next(iter(counts))
            if counts:
                top, topn = counts.most_common(1)[0]
                if topn / len(lits) > 0.5:
                    return top
            if any(re.search(r"%?ERROR|%?FAIL|%?5XX|%?4XX", l.upper()) for l in lits):
                return "metric_scan"
            return "metric_scan"
        # no metric literal
        if re.search(r"(MIN|MAX)\s*\(\s*TIME", sel):
            return "error_timeline"
        has_svc = bool(re.search(r"\bSERVICE_NAME\s*(=|IN|!=|<>|LIKE|NOT\s+IN)", where))
        if has_svc:
            return "metric_scan"  # per user's rule 7 extension
        return "metric_scan"

    # ==== TRACES ====
    if has_ab_traces or has_bare_traces:
        # Self-join with caller-callee
        if has_self_join:
            return "call_tree_build"

        has_trace_id_eq = bool(re.search(r"\bTRACE_ID\s*=\s*['\"]", where))
        has_trace_id_in_lit = bool(re.search(r"\bTRACE_ID\s+IN\s*\(\s*['\"]", where))
        has_trace_id_in_sub = bool(re.search(r"\bTRACE_ID\s+IN\s*\(?\s*__SUBQ__", where))
        has_parent_eq = bool(re.search(r"\bPARENT_SPAN_ID\s*=\s*['\"]", where))
        has_parent_in_lit = bool(re.search(r"\bPARENT_SPAN_ID\s+IN\s*\(\s*['\"]", where))
        has_parent_in_sub = bool(re.search(r"\bPARENT_SPAN_ID\s+IN\s*__SUBQ__|\bPARENT_SPAN_ID\s*=\s*\(?\s*__SUBQ__", where))
        has_msg_like = bool(re.search(r"\bSPAN_NAME\s*(NOT\s+)?LIKE", where))
        svc_like_n = len(re.findall(r"\bSERVICE_NAME\s+LIKE\s+['\"]", where))
        has_svc_eq = bool(re.search(r"\bSERVICE_NAME\s*=\s*['\"]", where))
        has_svc_in = bool(re.search(r"\bSERVICE_NAME\s+IN\s*\(", where))
        has_svc_filter = has_svc_eq or has_svc_in or bool(re.search(r"\bSERVICE_NAME\s*(!=|<>|NOT\s+IN)", where))
        has_dur_filter = bool(re.search(r"\bDURATION\s*[><]", where))
        has_group = "GROUP BY" in u
        has_count = bool(re.search(r"\bCOUNT\s*\(", sel))
        has_dur_agg = bool(re.search(r"(AVG|MAX|MIN|SUM)\s*\(\s*DURATION", sel))
        has_minmax_time = bool(re.search(r"(MIN|MAX)\s*\(\s*TIME", sel))
        has_distinct = "DISTINCT" in sel
        err_where = bool(re.search(r"ATTR_STATUS_CODE\s*(=|IN)\s*['\"]?ERROR", where, re.IGNORECASE)) \
            or bool(re.search(r"ATTR_HTTP_RESPONSE_STATUS_CODE\s*(=|IN|>=)\s*['\"]?[45]", where))
        err_select = bool(re.search(r"CASE\s+WHEN\b[^)]*?(?:ERROR|STATUS_CODE)", sel, re.IGNORECASE | re.DOTALL))
        gb_text = re.search(r"\bGROUP\s+BY\b(.*?)(?:\bORDER\b|\bLIMIT\b|\bUNION\b|\bHAVING\b|$)", u, re.DOTALL)
        gb = gb_text.group(1) if gb_text else ""
        gb_status = bool(re.search(r"ATTR_STATUS_CODE|ATTR_HTTP_RESPONSE_STATUS_CODE", gb))
        ob_m = re.search(r"\bORDER\s+BY\s+(.*?)(?:\bLIMIT\b|\bUNION\b|$)", u, re.DOTALL)
        ob = ob_m.group(1) if ob_m else ""
        ob_dur = bool(re.search(r"\bDURATION\b|\bMS\b|\bSEC\b|\bP99\b|\bLATENCY\b|\bAVG_DUR\b|\bMAX_DUR\b", ob))
        ob_count = bool(re.search(r"\bCOUNT\b|\bCNT\b|\bNUM\b|\bTOTAL\b", ob))

        # Rule 1: STRING_AGG path
        if re.search(r"\b(STRING_AGG|LIST_AGG|ARRAY_AGG)\s*\(", sel):
            return "call_tree_build"

        # Rule 2: MIN/MAX(time)
        if has_minmax_time and not has_msg_like:
            return "error_timeline"

        # Rule 3: keyword_search on span_name LIKE in WHERE OR in subquery
        if has_msg_like:
            return "keyword_search"
        if any(re.search(r"\b(MESSAGE|SPAN_NAME)\s*(NOT\s+)?LIKE", sq) for sq in subs):
            return "keyword_search"

        # Rule 4: parent_span_id filter (literal or subquery)
        if has_parent_eq or has_parent_in_lit or has_parent_in_sub:
            if has_svc_filter and has_parent_in_sub:
                return "service_trace_scan"  # narrowed
            if has_parent_in_sub and has_nm_traces:
                return "baseline_collect"
            # parent_span_id literal/sub → call_tree_build
            if has_svc_filter:
                return "service_trace_scan"
            return "call_tree_build"

        # Rule 5: trace_id IN (subquery)
        if has_trace_id_in_sub:
            # With parent_span_id in SELECT (previous rule)
            if "PARENT_SPAN_ID" in sel:
                if has_svc_filter:
                    return "service_trace_scan"
                return "call_tree_build"
            # No parent_span_id: only safe rule is outer svc filter → service_trace_scan
            if has_svc_filter:
                return "service_trace_scan"
            # everything else ambiguous
            return None

        # Rule 6: trace_id = X literal → trace_follow
        if has_trace_id_eq:
            return "trace_follow"

        # Rule 7: trace_id IN literal list, with span_id literal → trace_follow
        if has_trace_id_in_lit:
            return "trace_follow"

        # Rule 8: error filter → error_rate_scan (aggregate) OR stay none
        if (err_where or err_select or gb_status) and has_group:
            return "error_rate_scan"
        if err_where and has_distinct:
            return "error_rate_scan"
        # non-aggregate error filter — could be trace_follow or service_trace_scan
        # leave ambiguous

        # Rule 9: GROUP BY aggregations
        if has_group:
            if has_count and has_dur_agg:
                if ob_dur and not ob_count: return "latency_ranking"
                if ob_count and not ob_dur: return "throughput_compare"
                return None  # ambiguous
            if has_dur_agg:
                return "latency_ranking"
            if has_count:
                return "throughput_compare"

        # Rule 10: DISTINCT service_name → service_trace_scan
        if has_distinct:
            if has_svc_filter:  # narrowed
                return "service_trace_scan"
            return "service_trace_scan"

        # Rule 11: svc filter alone
        if has_svc_filter:
            if has_dur_filter or (has_dur_agg and ob_dur):
                return "latency_ranking"
            return "service_trace_scan"

        # Rule 12: duration filter alone
        if has_dur_filter:
            return "latency_ranking"

        # Rule 13: nothing else matches
        return None

    return None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    p.add_argument("--min-vote", type=int, default=3,
                   help="Require this many LLM votes to agree with rule for commit (default 3)")
    p.add_argument("--dump", type=str, default=None,
                   help="Write ambiguous cases to this JSON file")
    args = p.parse_args()

    eng = create_engine(DB_URL)
    total = 0
    committed: list[dict] = []
    ambiguous: list[dict] = []
    rule_none: list[dict] = []

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
                    rounds = extract_sql_rounds(normalize_by_agent(agent, traj))
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
                        total += 1
                        intent = rule_classify(sql)
                        votes = {vk: v_at(vk, *pos) for vk in VOTE_KEYS}
                        vote_vals = [v for v in votes.values() if v]
                        vote_counts = Counter(vote_vals)
                        record = {
                            "exp": exp, "idx": idx, "round": pos[0], "sql_index": pos[1],
                            "sql": sql, "votes": votes, "rule_intent": intent,
                        }
                        top = vote_counts.most_common(1)
                        top_intent = top[0][0] if top else None
                        top_n = top[0][1] if top else 0
                        if intent is None:
                            # No rule — accept LLM if ≥3/4 consensus
                            if top_n >= 3:
                                record["rule_intent"] = top_intent
                                record["agree"] = top_n
                                record["note"] = "LLM-majority (no rule)"
                                committed.append(record)
                            else:
                                rule_none.append(record)
                            continue
                        # Rule returned an intent
                        agree = vote_counts.get(intent, 0)
                        if agree >= args.min_vote:
                            record["agree"] = agree
                            committed.append(record)
                        elif top_n >= 3:
                            # Rule disagrees with 3/4 LLM majority → trust LLMs
                            record["rule_intent"] = top_intent
                            record["agree"] = top_n
                            record["note"] = "LLM-majority override"
                            committed.append(record)
                        else:
                            record["rule_agree"] = agree
                            ambiguous.append(record)

    print(f"Total pending scanned: {total}")
    print(f"Committed (rule ≥{args.min_vote} votes OR 4/4 LLM consensus): {len(committed)}")
    print(f"Ambiguous (rule + LLM disagree): {len(ambiguous)}")
    print(f"Rule returned None (no clear rule): {len(rule_none)}")

    print(f"\n=== Committed intent distribution ===")
    intent_c = Counter(r["rule_intent"] for r in committed)
    for i, n in intent_c.most_common():
        print(f"  {i}: {n}")

    if args.dump:
        with open(args.dump, "w") as f:
            json.dump({
                "committed": committed,
                "ambiguous": ambiguous,
                "rule_none": rule_none,
            }, f, default=str, indent=2)
        print(f"\nDumped full report to {args.dump}")

    if not args.write:
        print("\n(dry-run — pass --write to commit.)")
        return

    per_sample: dict[tuple[str, int], list[dict]] = {}
    for r in committed:
        per_sample.setdefault((r["exp"], r["idx"]), []).append(
            {"round": r["round"], "sql_index": r["sql_index"],
             "intent": r["rule_intent"], "rule": "user_final_sweep"}
        )
    written = 0
    with Session(eng) as sess:
        for (exp, idx), new_entries in per_sample.items():
            row = sess.execute(
                text("SELECT id FROM evaluation_data WHERE exp_id=:e AND dataset_index=:i AND stage='judged'"),
                {"e": exp, "i": idx},
            ).first()
            if not row:
                continue
            obj = sess.get(EvaluationSample, row[0])
            if not obj:
                continue
            meta = dict(obj.meta or {})
            llm = dict(meta.get("llm_intents") or {})
            finals = list(llm.get("final") or [])
            existing = {(e["round"], e["sql_index"]) for e in finals}
            for ent in new_entries:
                if (ent["round"], ent["sql_index"]) in existing:
                    continue
                finals.append(ent)
                written += 1
            llm["final"] = finals
            meta["llm_intents"] = llm
            obj.meta = meta
            flag_modified(obj, "meta")
        sess.commit()
    print(f"Wrote {written} new final entries.")


if __name__ == "__main__":
    main()
