#!/usr/bin/env python
"""Classify pending TRACES / GROUP BY + aggregation SQLs.

Priority rules (first match wins):
  1. SELECT has MIN/MAX(time)                        → error_timeline      [user_traces_minmax_time]
  2. WHERE has error filter (status=ERROR / http 4xx/5xx)
     OR SELECT has CASE WHEN ERROR / error count     → error_rate_scan     [user_traces_error_agg]
  3. GROUP BY includes parent_span_id                 → call_tree_build     [user_traces_gb_parent]
  4. GROUP BY trace_id                                → latency_ranking    [user_traces_gb_trace_id]
  5. SELECT has AVG/MAX/SUM(duration) AND ORDER BY duration
                                                      → latency_ranking    [user_traces_latency]
  6. SELECT has COUNT only AND ORDER BY count_like    → throughput_compare [user_traces_throughput]
  7. Both count + duration with ORDER BY count        → throughput_compare [user_traces_throughput_mixed]
  8. Both count + duration with ORDER BY duration     → latency_ranking    [user_traces_latency_mixed]
  9. other                                            → skip (stay pending)
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


def classify(sql: str) -> tuple[str | None, str]:
    u = flatten_subq(sql)

    # Scope: TRACES only, no logs/metrics, no normal_*
    has_ab_traces = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,120}?ABNORMAL_TRACES\b", u, re.DOTALL))
    has_bare_traces = bool(re.search(r"\b(?:FROM|JOIN)\s+TRACES\b", u))
    has_nm_traces = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,120}?(?<!AB)NORMAL_TRACES\b", u, re.DOTALL))
    has_logs = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,120}?(?:AB)?NORMAL_LOGS\b|\b(?:FROM|JOIN)\s+LOGS\b", u, re.DOTALL))
    has_metrics = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,120}?(?:AB)?NORMAL_METRICS", u, re.DOTALL))

    if has_nm_traces:
        return None, "normal_traces"
    if has_logs or has_metrics:
        return None, "cross-modal"
    if not (has_ab_traces or has_bare_traces):
        return None, "not traces"

    # Must have GROUP BY
    if not re.search(r"\bGROUP\s+BY\b", u):
        return None, "no GROUP BY"

    # SELECT clause
    sel_m = re.search(r"\bSELECT\b(.*?)\bFROM\b", u, re.DOTALL)
    sel = sel_m.group(1) if sel_m else ""
    # WHERE clause
    wm = re.search(r"\bWHERE\b(.*?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|\bUNION\b|\bHAVING\b|$)",
                   u, re.DOTALL)
    where = wm.group(1) if wm else ""
    # GROUP BY cols
    gb_m = re.search(r"\bGROUP\s+BY\b(.*?)(?:\bORDER\b|\bLIMIT\b|\bUNION\b|\bHAVING\b|$)",
                     u, re.DOTALL)
    gb_text = gb_m.group(1) if gb_m else ""
    # ORDER BY text
    ob_m = re.search(r"\bORDER\s+BY\b(.*?)(?:\bLIMIT\b|\bUNION\b|$)", u, re.DOTALL)
    ob_text = ob_m.group(1) if ob_m else ""

    # Features
    has_minmax_time = bool(re.search(r"(MIN|MAX)\s*\(\s*TIME", sel))
    # self-join on parent_span_id=span_id or trace_id=trace_id
    has_self_join = bool(re.search(
        r"\bPARENT_SPAN_ID\s*=\s*\w*\.?SPAN_ID\b|\bSPAN_ID\s*=\s*\w*\.?PARENT_SPAN_ID\b|"
        r"\bTRACE_ID\s*=\s*\w+\.TRACE_ID\b|\w+\.TRACE_ID\s*=\s*\w+\.TRACE_ID\b",
        u,
    ))
    # WHERE has span_name/message LIKE
    has_msg_like = bool(re.search(r"\b(MESSAGE|SPAN_NAME)\s*(NOT\s+)?LIKE", where))
    # WHERE has service_name LIKE (we treat any as potential keyword territory)
    has_svc_like = bool(re.search(r"\bSERVICE_NAME\s+LIKE\s+['\"]", where))
    # WHERE has trace_id IN (subquery)
    has_trace_sub = bool(re.search(r"\bTRACE_ID\s+IN\s*__SUBQ__", where))
    # error signals
    err_where = bool(re.search(r"ATTR_STATUS_CODE\s*(=|IN)\s*['\"]?ERROR", where, re.IGNORECASE)) \
        or bool(re.search(r"ATTR_HTTP_RESPONSE_STATUS_CODE\s*(=|>=|IN)\s*['\"]?[45]", where))
    err_select = bool(re.search(r"CASE\s+WHEN\b[^)]*?(?:ERROR|ATTR_STATUS_CODE|STATUS_CODE)",
                                sel, re.IGNORECASE | re.DOTALL))
    err_select_count = bool(re.search(r"COUNT\s*\(\s*CASE\s+WHEN", sel, re.IGNORECASE))
    # GROUP BY includes status code → per-status aggregation → error_rate_scan
    gb_has_status = bool(re.search(r"ATTR_STATUS_CODE|ATTR_HTTP_RESPONSE_STATUS_CODE", gb_text))
    err_signal = err_where or err_select or err_select_count or gb_has_status
    # duration aggregations
    has_dur_agg = bool(re.search(r"(AVG|MAX|MIN|SUM)\s*\(\s*DURATION", sel))
    has_count_star = bool(re.search(r"COUNT\s*\(\s*\*\s*\)", sel))
    # GROUP BY cols
    gb_has_parent = "PARENT_SPAN_ID" in gb_text
    gb_has_trace_id = bool(re.search(r"(?<!_)\bTRACE_ID\b", gb_text))
    gb_has_service = "SERVICE_NAME" in gb_text
    # ORDER BY direction
    ob_by_duration = bool(re.search(r"\bDURATION\b|\bAVG_DUR\b|\bMAX_DUR\b|\bLATENCY\b|"
                                    r"\bDUR(?:_MS|_SEC|_NS)?\b|\bMS\b|\bP99\b",
                                    ob_text))
    ob_by_count = bool(re.search(r"\bCOUNT\b|\bCNT\b|\bNUM\b|\bTOTAL\b", ob_text))

    # Rule 1: self-join → skip (call_tree_build territory)
    if has_self_join:
        return None, "self-join (call_tree_build territory)"

    # Rule 2: WHERE/HAVING has span_name/message LIKE → skip (keyword_search territory)
    # Also check HAVING for LIKE
    having_m = re.search(r"\bHAVING\b(.*?)(?:\bLIMIT\b|\bUNION\b|$)", u, re.DOTALL)
    having_text = having_m.group(1) if having_m else ""
    if has_msg_like or re.search(r"\b(MESSAGE|SPAN_NAME)\s*(NOT\s+)?LIKE", having_text):
        return None, "span_name/message LIKE (keyword territory)"
    if len(re.findall(r"\bSERVICE_NAME\s+LIKE\s+['\"]", where)) >= 2:
        return None, "multi service_name LIKE (keyword territory)"

    # Rule 3: trace_id IN (subquery) → skip (call_tree_build territory)
    if has_trace_sub:
        return None, "trace_id IN(subquery) (call_tree territory)"

    # Rule 4: MIN/MAX(time) → error_timeline (after excluding LIKE cases)
    if has_minmax_time:
        return "error_timeline", "user_traces_minmax_time"

    # Rule 5: error signal → error_rate_scan
    if err_signal:
        return "error_rate_scan", "user_traces_error_agg"

    # Rule 6: GROUP BY parent_span_id → call_tree_build
    if gb_has_parent:
        return "call_tree_build", "user_traces_gb_parent"

    # Rule 7: GROUP BY trace_id (no service) → skip (ambiguous)
    if gb_has_trace_id and not gb_has_service:
        return None, "GROUP BY trace_id only (ambiguous)"

    # Rule 8/9: duration vs count decision
    if has_dur_agg and has_count_star:
        if ob_by_duration and not ob_by_count:
            return "latency_ranking", "user_traces_latency_mixed"
        if ob_by_count and not ob_by_duration:
            return "throughput_compare", "user_traces_throughput_mixed"
        # ambiguous ORDER BY (both or neither) → skip, keep pending
        return None, "mixed count+duration, ORDER BY ambiguous"
    if has_dur_agg and not has_count_star:
        return "latency_ranking", "user_traces_latency"
    if has_count_star and not has_dur_agg:
        return "throughput_compare", "user_traces_throughput"

    return None, "no count/duration aggregation"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    args = p.parse_args()

    eng = create_engine(DB_URL)
    total_pending = 0
    reject_counter: Counter = Counter()
    rule_counter: Counter = Counter()
    intent_counter: Counter = Counter()
    votes_by_rule: dict[str, Counter] = {}
    examples: dict[str, list[dict]] = {}
    staged: list[dict] = []

    with eng.connect() as c:
        for exp in EXPS:
            agent = exp.split("-", 1)[0]
            rows = c.execute(
                text(
                    "SELECT dataset_index, trajectories, meta FROM evaluation_data "
                    "WHERE exp_id=:e AND stage='judged'"
                ),
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

                def vote_at(key, r, si):
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
                        intent, tag = classify(sql)
                        if intent is None:
                            reject_counter[tag] += 1
                            continue
                        rule_counter[tag] += 1
                        intent_counter[intent] += 1
                        votes = {vk: vote_at(vk, *pos) for vk in VOTE_KEYS}
                        votes_by_rule.setdefault(tag, Counter())
                        for v in votes.values():
                            if v:
                                votes_by_rule[tag][v] += 1
                        examples.setdefault(tag, [])
                        if len(examples[tag]) < 4:
                            examples[tag].append(
                                {"exp": exp, "idx": idx, "pos": pos, "sql": sql, "votes": votes}
                            )
                        staged.append(
                            {"exp": exp, "idx": idx, "round": pos[0],
                             "sql_index": pos[1], "intent": intent, "rule": tag}
                        )

    print(f"Total pending scanned: {total_pending}")
    print(f"\nMatches by rule → intent:")
    for tag, n in rule_counter.most_common():
        sample_intent = next((s["intent"] for s in staged if s["rule"] == tag), "?")
        print(f"  {tag:<34} → {sample_intent:<20} {n:>4}")
    print(f"\nAggregated by intent:")
    for i, n in intent_counter.most_common():
        print(f"  {i}: {n}")
    print(f"\nRejection reasons (top 8):")
    for r, n in reject_counter.most_common(8):
        print(f"  {r}: {n}")
    print(f"\nLLM vote distribution per rule:")
    for tag, cnt in votes_by_rule.items():
        top = dict(cnt.most_common(5))
        print(f"  [{tag}]: {top}")

    for tag, exs in examples.items():
        print(f"\n=== Sample [{tag}] (up to 4) ===")
        for i, ex in enumerate(exs, 1):
            print(f"\n--- [{i}] {ex['exp']} case={ex['idx']} r={ex['pos'][0]} si={ex['pos'][1]}")
            print(f"VOTES: {ex['votes']}")
            print(ex["sql"][:400])

    if not args.write:
        print("\n(dry-run — pass --write to commit.)")
        return

    per_sample: dict[tuple[str, int], list[dict]] = {}
    for s in staged:
        per_sample.setdefault((s["exp"], s["idx"]), []).append(
            {"round": s["round"], "sql_index": s["sql_index"], "intent": s["intent"], "rule": s["rule"]}
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
