#!/usr/bin/env python
"""Export 3-way comparison CSV for user review.

Combines Claude 4.6 + Gemini 3.1 Pro Preview + Claude Opus 4.7 arbiter labels.
Per-SQL verdict:
  - CLAUDE_GEMINI_AGREE     Claude and Gemini gave same label (no arbiter needed)
  - ARBITER_CONFIRMS_CLAUDE 4.7 agrees with Claude 4.6  (Gemini is outlier)
  - ARBITER_CONFIRMS_GEMINI 4.7 agrees with Gemini     (Claude was wrong)
  - ALL_DIFFER              Three models three labels  (user must judge)

By default only exports rows where arbiter ran (i.e., the original Claude-vs-Gemini
disagreement set). Pre-accepted pairs (metric_scan → baseline_collect) are
included with verdict=ACCEPT_GEMINI (no arbiter run).

CSV columns include:
  exp_id, dataset_index, round, sql_index, verdict,
  claude_intent, gemini_intent, arbiter_intent,
  sql, rule_intent (for reference),
  user_decision (blank — user fills in)

Usage:
    uv run python scripts/export_3way_review.py \\
        --db postgresql://... --out review.csv \\
        [--only-all-differ]   # reduce to just ALL_DIFFER rows
"""

import argparse
import csv
import json
import re
import sys

from sqlalchemy import create_engine, text

sys.path.insert(0, str(__file__).rsplit("/scripts/", 1)[0])

from sota_rca.analysis.extractor import classify_intent
from sota_rca.analysis.llm_intent_classifier import extract_sql_rounds
from sota_rca.analysis.trajectory_normalizer import normalize_by_agent
from scripts.arbitrate_disagreements import (
    agent_of, EXPS, CLAUDE_KEY, GEMINI_KEY, ARBITER_KEY, EXCLUDED_PAIRS,
)


VERDICT_ORDER = {
    "ALL_DIFFER": 0,
    "ARBITER_CONFIRMS_GEMINI": 1,
    "ARBITER_CONFIRMS_CLAUDE": 2,
    "ACCEPT_GEMINI": 3,        # pre-accepted pair
    "CLAUDE_GEMINI_AGREE": 4,  # no disagreement
    "ARBITER_MISSING": 5,      # disagreement but arbiter didn't label
}


def verdict(claude: str, gemini: str, arbiter: str | None, pair_excluded: bool) -> str:
    if claude == gemini:
        return "CLAUDE_GEMINI_AGREE"
    if pair_excluded:
        return "ACCEPT_GEMINI"
    if arbiter is None:
        return "ARBITER_MISSING"
    if arbiter == claude == gemini:
        return "CLAUDE_GEMINI_AGREE"  # shouldn't happen but safe
    if arbiter == claude:
        return "ARBITER_CONFIRMS_CLAUDE"
    if arbiter == gemini:
        return "ARBITER_CONFIRMS_GEMINI"
    return "ALL_DIFFER"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", default="review_3way.csv")
    parser.add_argument("--only-all-differ", action="store_true",
                        help="Export only ALL_DIFFER rows (the ones you need to judge)")
    parser.add_argument("--exclude-agree", action="store_true",
                        help="Exclude CLAUDE_GEMINI_AGREE rows (they were never disputed)")
    args = parser.parse_args()

    engine = create_engine(
        args.db,
        connect_args={"check_same_thread": False} if args.db.startswith("sqlite") else {},
    )

    rows_out: list[dict] = []
    counts: dict[str, int] = {k: 0 for k in VERDICT_ORDER}

    with engine.connect() as conn:
        for exp_id in EXPS:
            rs = conn.execute(text(
                f"""SELECT dataset_index, trajectories, meta FROM evaluation_data
                    WHERE exp_id='{exp_id}' AND stage='judged'
                      AND (meta::jsonb->'llm_intents') ? '{CLAUDE_KEY}'"""
            )).fetchall()
            for idx, traj_raw, meta_raw in rs:
                tr = json.loads(traj_raw) if isinstance(traj_raw, str) else traj_raw
                m = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
                ents_c = (m.get("llm_intents") or {}).get(CLAUDE_KEY, [])
                ents_g = (m.get("llm_intents") or {}).get(GEMINI_KEY, [])
                ents_a = (m.get("llm_intents") or {}).get(ARBITER_KEY, [])
                c_by = {(e.get("round"), e.get("sql_index")): e.get("intent", "") for e in ents_c}
                g_by = {(e.get("round"), e.get("sql_index")): e.get("intent", "") for e in ents_g}
                a_by = {(e.get("round"), e.get("sql_index")): e.get("intent", "") for e in ents_a}

                tr_norm = normalize_by_agent(agent_of(exp_id), tr)
                sql_by = {
                    (r.round_index, i + 1): sql
                    for r in extract_sql_rounds(tr_norm)
                    for i, sql in enumerate(r.queries)
                }

                for pos, ic in c_by.items():
                    sql = sql_by.get(pos, "")
                    if not sql:
                        continue
                    ig = g_by.get(pos)
                    if ig is None:
                        continue  # Gemini missing
                    pair_excluded = (ic, ig) in EXCLUDED_PAIRS
                    ia = a_by.get(pos)
                    v = verdict(ic, ig, ia, pair_excluded)
                    counts[v] = counts.get(v, 0) + 1

                    # Output filters
                    if args.only_all_differ and v != "ALL_DIFFER":
                        continue
                    if args.exclude_agree and v == "CLAUDE_GEMINI_AGREE":
                        continue

                    rule_int = classify_intent("query_parquet_files", sql)
                    rows_out.append({
                        "verdict": v,
                        "exp_id": exp_id,
                        "dataset_index": idx,
                        "round": pos[0],
                        "sql_index": pos[1],
                        "claude_intent": ic,
                        "gemini_intent": ig,
                        "arbiter_intent": ia or "",
                        "rule_intent": rule_int,
                        "sql": re.sub(r"\s+", " ", sql).strip()[:600],
                        "user_decision": "",
                    })

    # Sort: ALL_DIFFER first (highest priority review), then ARBITER_CONFIRMS_GEMINI (Claude errors), etc.
    rows_out.sort(key=lambda r: (VERDICT_ORDER.get(r["verdict"], 99),
                                  r["exp_id"], r["dataset_index"], r["round"], r["sql_index"]))

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        if rows_out:
            writer = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
            writer.writeheader()
            writer.writerows(rows_out)

    print(f"=== Counts ===")
    total = sum(counts.values())
    for verdict_name in VERDICT_ORDER:
        n = counts.get(verdict_name, 0)
        pct = 100 * n / total if total else 0
        print(f"  {verdict_name:30s} {n:>7d} ({pct:>5.1f}%)")
    print(f"  {'TOTAL':30s} {total:>7d}")
    print(f"\nExported {len(rows_out)} rows to {args.out}")
    print("User fills `user_decision`: claude / gemini / arbiter / rule / other:<intent>")


if __name__ == "__main__":
    main()
