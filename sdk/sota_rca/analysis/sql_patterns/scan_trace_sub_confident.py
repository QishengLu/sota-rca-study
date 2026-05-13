#!/usr/bin/env python
"""Write only CONFIDENT classifications for pending TRACES `trace_id IN (subquery)` + no parent_span_id:

  A. outer has service_name filter (=/IN/!=/NOT IN)          → service_trace_scan [user_trace_sub_narrow_np]
  B. GROUP BY + COUNT only + subquery contains error filter  → error_rate_scan    [user_trace_sub_err_count]
  C. outer WHERE has message/span_name LIKE                  → keyword_search     [user_trace_sub_keyword]

Everything else stays pending for manual review.
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
    """Return (flattened, list of subquery contents (uppercase))."""
    u = sql.upper()
    subqueries: list[str] = []
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
                    subqueries.append(inner)
                    u = u[:start] + " __SUBQ__ " + u[i + 1 :]
                    i = start + len(" __SUBQ__ ") - 1
                    start = -1
                else:
                    start = -1
        i += 1
    return u, subqueries


def classify(sql: str) -> tuple[str | None, str]:
    u, subqs = flatten_subq(sql)

    if not re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,120}?ABNORMAL_TRACES\b|\b(?:FROM|JOIN)\s+TRACES\b",
                     u, re.DOTALL):
        return None, "not traces"
    if re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,120}?(?<!AB)NORMAL_TRACES\b", u, re.DOTALL):
        return None, "normal_traces"

    wm = re.search(r"\bWHERE\b(.*?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|\bUNION\b|\bHAVING\b|$)",
                   u, re.DOTALL)
    where = wm.group(1) if wm else ""

    if not re.search(r"\bTRACE_ID\s+IN\s*\(?\s*__SUBQ__", where):
        return None, "no trace_id IN(sub)"

    sel_from = re.search(r"\bSELECT\b(.*?)\bFROM\b", u, re.DOTALL)
    sel = sel_from.group(1) if sel_from else ""
    if "PARENT_SPAN_ID" in sel:
        return None, "has parent_span_id (prev rule)"

    # Feature detection
    has_msg_like = bool(re.search(r"\b(MESSAGE|SPAN_NAME)\s*(NOT\s+)?LIKE", where))
    has_svc_eq = bool(re.search(r"\bSERVICE_NAME\s*=\s*['\"]", where))
    has_svc_in = bool(re.search(r"\bSERVICE_NAME\s+IN\s*\(", where))
    has_svc_neq = bool(re.search(r"\bSERVICE_NAME\s*(!=|<>)\s*['\"]|\bSERVICE_NAME\s+NOT\s+IN", where))
    has_svc_filter = has_svc_eq or has_svc_in or has_svc_neq
    has_group_by = bool(re.search(r"\bGROUP\s+BY\b", u))
    has_count = bool(re.search(r"\bCOUNT\s*\(", sel))
    has_dur_agg = bool(re.search(r"(AVG|MAX|MIN|SUM)\s*\(\s*DURATION", sel))

    # subquery contains error filter?
    subq_err = False
    for sq in subqs:
        if re.search(r"ATTR_STATUS_CODE\s*(=|IN)\s*['\"]?ERROR", sq) \
                or re.search(r"ATTR_HTTP_RESPONSE_STATUS_CODE\s*(=|IN|>=)\s*['\"]?[45]", sq):
            subq_err = True
            break

    # Rule C: outer msg_like → keyword_search
    if has_msg_like:
        return "keyword_search", "user_trace_sub_keyword"

    # Rule A: outer svc filter → service_trace_scan (even without parent_span_id)
    if has_svc_filter:
        return "service_trace_scan", "user_trace_sub_narrow_np"

    # Rule B: GROUP BY + COUNT only + subquery has error filter → error_rate_scan
    if has_group_by and has_count and not has_dur_agg and subq_err:
        return "error_rate_scan", "user_trace_sub_err_count"

    # Else: ambiguous, leave pending
    return None, "ambiguous (manual review)"


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
                        intent, tag = classify(sql)
                        if intent is None:
                            reject_counter[tag] += 1
                            continue
                        rule_counter[tag] += 1
                        intent_counter[intent] += 1
                        votes = {vk: v_at(vk, *pos) for vk in VOTE_KEYS}
                        votes_by_rule.setdefault(tag, Counter())
                        for v in votes.values():
                            if v:
                                votes_by_rule[tag][v] += 1
                        examples.setdefault(tag, [])
                        if len(examples[tag]) < 3:
                            examples[tag].append({"exp": exp, "idx": idx, "pos": pos, "sql": sql, "votes": votes})
                        staged.append({
                            "exp": exp, "idx": idx, "round": pos[0],
                            "sql_index": pos[1], "intent": intent, "rule": tag,
                        })

    print(f"Total pending scanned: {total_pending}")
    print(f"\nMatches by rule → intent:")
    for tag, n in rule_counter.most_common():
        print(f"  {tag:<30} {n:>4}  votes: {dict(votes_by_rule.get(tag, Counter()).most_common(4))}")
    print(f"\nAggregated by intent:")
    for i, n in intent_counter.most_common():
        print(f"  {i}: {n}")
    print(f"\nRejection reasons (top 8):")
    for r, n in reject_counter.most_common(8):
        print(f"  {r}: {n}")
    for tag, exs in examples.items():
        print(f"\n=== Sample [{tag}] ===")
        for ex in exs:
            print(f"  {ex['exp']} case={ex['idx']} pos={ex['pos']} votes={ex['votes']}")
            print(f"  SQL: {ex['sql'][:250].replace(chr(10), ' ')}")

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
