"""Dry-run: extract SQLs from 53 cases, no LLM call. Verify count + alignment."""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

os.environ["UTU_DB_URL"] = "postgresql://postgres:postgres@localhost:5433/SOTA-Agents"

from sqlalchemy import create_engine, text

EXP_ID = "thinkdepthai-qwen3.5-plus-2026-02-15-mw-v4-run"


def extract_sqls_from_trajectory(trajectory):
    sqls = []
    if not trajectory:
        return sqls
    if isinstance(trajectory, str):
        try:
            trajectory = json.loads(trajectory)
        except Exception:
            return sqls
    round_num = 0
    for msg in trajectory:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        if role == "assistant":
            round_num += 1
            tcs = msg.get("tool_calls") or []
            for tc in tcs:
                fn = tc.get("function") or {}
                if fn.get("name") == "query_parquet_files":
                    args = fn.get("arguments")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    sql = args.get("query") if isinstance(args, dict) else None
                    if sql:
                        sqls.append((sql, round_num))
    return sqls


def make_lookup(intent_list):
    if not intent_list:
        return {}
    return {(e["round"], e.get("sql_index", 1)): e["intent"] for e in intent_list if "round" in e and "intent" in e}


def main():
    e = create_engine(os.environ["UTU_DB_URL"])
    with e.connect() as c:
        rows = c.execute(text("""
            SELECT dataset_index, trajectories, meta::jsonb->'llm_intents' AS intents
            FROM evaluation_data
            WHERE exp_id = :eid
            ORDER BY dataset_index
        """), {"eid": EXP_ID}).fetchall()
    print(f"Loaded {len(rows)} cases")

    total_sqls = 0
    cases_with_intents = 0
    aligned = 0
    misaligned = 0
    sample_misalignments = []

    for row in rows:
        di, traj, intents = row
        sqls = extract_sqls_from_trajectory(traj)
        opus_lookup = make_lookup((intents or {}).get("claude_opus_4_6", []))
        n_opus = len(opus_lookup)

        total_sqls += len(sqls)
        if intents:
            cases_with_intents += 1
            if len(sqls) == n_opus:
                aligned += 1
            else:
                misaligned += 1
                if len(sample_misalignments) < 5:
                    sample_misalignments.append((di, len(sqls), n_opus))

    print(f"Total extracted SQLs: {total_sqls}")
    print(f"Cases with intent labels: {cases_with_intents}")
    print(f"Aligned (extract count == opus count): {aligned}")
    print(f"Misaligned: {misaligned}")
    if sample_misalignments:
        print("Sample mismatches (di, extracted, opus):")
        for s in sample_misalignments:
            print(f"  {s}")

    # Estimate cost
    avg_per_case = total_sqls / len(rows)
    print(f"\nAvg SQLs per case: {avg_per_case:.1f}")
    # 53 LLM calls (one per case) for batched classification
    print(f"Estimated LLM calls (one batch per case): 53")
    print(f"Estimated total tokens (rough): ~{total_sqls * 200} input + ~{total_sqls * 50} output")


if __name__ == "__main__":
    main()
