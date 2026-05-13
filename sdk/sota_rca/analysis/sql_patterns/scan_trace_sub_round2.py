#!/usr/bin/env python
"""Round 2: confident classifications for pending trace_id IN (subquery) + NO parent_span_id.

Confident rules (priority order):
  1. Subquery contains span_name/message LIKE → keyword_search [user_trace_sub_subq_like]
  2. SELECT has STRING_AGG/LIST_AGG ordered by time (path reconstruction)
     → call_tree_build [user_trace_sub_path_agg]

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

    # Mask quoted literals for safer WHERE extraction
    def _mask(m):
        return "'" + "_" * (len(m.group(0)) - 2) + "'"
    masked = re.sub(r"'[^']*'", _mask, u)
    wm = re.search(r"\bWHERE\b(.*?)(?:\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|\bUNION\b|\bHAVING\b|$)",
                   masked, re.DOTALL)
    where = u[wm.span(1)[0]:wm.span(1)[1]] if wm else ""

    if not re.search(r"\bTRACE_ID\s+IN\s*\(?\s*__SUBQ__", where):
        return None, "no trace_id IN(sub)"

    sel_from = re.search(r"\bSELECT\b(.*?)\bFROM\b", u, re.DOTALL)
    sel = sel_from.group(1) if sel_from else ""
    if "PARENT_SPAN_ID" in sel:
        return None, "has parent_span_id (prev rule)"

    # Rule 1: subquery has span_name/message LIKE → keyword_search
    if any(re.search(r"\b(MESSAGE|SPAN_NAME)\s*(NOT\s+)?LIKE", sq) for sq in subqs):
        return "keyword_search", "user_trace_sub_subq_like"

    # Rule 2: SELECT has STRING_AGG/LIST_AGG (path/chain reconstruction) → call_tree_build
    if re.search(r"\b(STRING_AGG|LIST_AGG|ARRAY_AGG)\s*\(", sel):
        return "call_tree_build", "user_trace_sub_path_agg"

    return None, "ambiguous (manual review)"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    args = p.parse_args()

    eng = create_engine(DB_URL)
    total = 0
    rule_counter: Counter = Counter()
    intent_counter: Counter = Counter()
    votes_by_rule: dict[str, Counter] = {}
    examples: dict[str, list[dict]] = {}
    rejects: Counter = Counter()
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
                        intent, tag = classify(sql)
                        if intent is None:
                            rejects[tag] += 1
                            continue
                        rule_counter[tag] += 1
                        intent_counter[intent] += 1
                        votes = {vk: v_at(vk, *pos) for vk in VOTE_KEYS}
                        votes_by_rule.setdefault(tag, Counter())
                        for v in votes.values():
                            if v:
                                votes_by_rule[tag][v] += 1
                        examples.setdefault(tag, [])
                        if len(examples[tag]) < 4:
                            examples[tag].append({"exp": exp, "idx": idx, "pos": pos, "sql": sql, "votes": votes})
                        staged.append({
                            "exp": exp, "idx": idx, "round": pos[0], "sql_index": pos[1],
                            "intent": intent, "rule": tag,
                        })

    print(f"Total pending scanned: {total}")
    print(f"\nMatches:")
    for tag, n in rule_counter.most_common():
        sample_intent = next((s["intent"] for s in staged if s["rule"] == tag), "?")
        print(f"  {tag:<30} → {sample_intent:<18} {n:>4}  votes: {dict(votes_by_rule[tag].most_common(4))}")
    print(f"\nAggregated by intent:")
    for i, n in intent_counter.most_common():
        print(f"  {i}: {n}")
    print(f"\nRejection reasons (top 6):")
    for r, n in rejects.most_common(6):
        print(f"  {r}: {n}")
    for tag, exs in examples.items():
        print(f"\n=== Sample [{tag}] ===")
        for ex in exs:
            print(f"  {ex['exp']} case={ex['idx']} pos={ex['pos']} votes={ex['votes']}")
            print(f"  SQL: {ex['sql'][:280].replace(chr(10), ' ')}")

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
