"""Compare qwen3.5-plus intent labeling against opus + final labels on 53 v4 cases.

Methodology:
1. Pull SQLs + existing labels from DB (exp_id = thinkdepthai-qwen3.5-plus-2026-02-15-mw-v4-run)
2. Re-classify same SQLs with qwen3.5-plus
3. Compare per-SQL agreement: qwen vs opus, qwen vs final
4. Report accuracy, per-class F1, confusion patterns

Output: qwen_intent_results.json + qwen_intent_summary.md
"""
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# Force shubiaobiao API for qwen3.5-plus
os.environ["UTU_DB_URL"] = "postgresql://postgres:postgres@localhost:5433/SOTA-Agents"

sys.path.insert(0, "/home/nn/SOTA-agents/Deep_Research")
sys.path.insert(0, "/home/nn/SOTA-agents/RCAgentEval")

from sqlalchemy import create_engine, text
from langchain_openai import ChatOpenAI

# Reuse existing classifier
sys.path.insert(0, "/home/nn/SOTA-agents/Deep_Research/middleware")
from intent_classifier import IntentClassifier, _VALID_INTENTS_SET

# Canonical SQL extractor — same logic that produced opus labels
from utu.eval.analysis.llm_intent_classifier import extract_sql_rounds

OUTPUT_DIR = Path("/home/nn/SOTA-agents/analysis/4-middleware/v4_forensic")
EXP_ID = "thinkdepthai-qwen3.5-plus-2026-02-15-mw-v4-run"


def get_qwen_model():
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY/DASHSCOPE_API_KEY not set; cannot call qwen-plus")
    # Aliyun DashScope OpenAI-compatible standard endpoint
    base_url = os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model = os.environ.get("QWEN_MODEL", "qwen-plus")
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.0,
        max_tokens=4096,
    )


def extract_sqls_from_trajectory(trajectory):
    """Use canonical extract_sql_rounds (same logic as opus labeling pipeline)."""
    if not trajectory:
        return []
    if isinstance(trajectory, str):
        try:
            trajectory = json.loads(trajectory)
        except Exception:
            return []
    rounds = extract_sql_rounds(trajectory)
    sqls = []
    for r in rounds:
        for sql in r.queries:
            sqls.append((sql, r.round_index))
    return sqls


def fetch_cases():
    """Pull all 53 cases with existing intent labels and trajectories."""
    e = create_engine(os.environ["UTU_DB_URL"])
    with e.connect() as c:
        rows = c.execute(text("""
            SELECT dataset_index, trajectories, meta::jsonb->'llm_intents' AS intents
            FROM evaluation_data
            WHERE exp_id = :eid
            ORDER BY dataset_index
        """), {"eid": EXP_ID}).fetchall()
    cases = []
    for r in rows:
        di, traj, intents = r
        cases.append({
            "dataset_index": di,
            "trajectory": traj,
            "intents": intents or {},
        })
    return cases


def opus_intents_ordered(intent_list):
    """Return opus intents sorted by global_index (or insertion order if missing)."""
    if not intent_list:
        return []
    return [e["intent"] for e in sorted(intent_list, key=lambda x: x.get("global_index", 0))]


def final_intents_ordered(intent_list):
    """Final lookup falls back to insertion order (no global_index in 'final')."""
    if not intent_list:
        return []
    return [e["intent"] for e in intent_list]


def main():
    print("Loading cases from DB...")
    cases = fetch_cases()
    print(f"  {len(cases)} cases loaded")

    print("Initializing qwen3.5-plus model...")
    qwen_model = get_qwen_model()
    classifier = IntentClassifier(qwen_model)

    # Process each case
    case_results = []
    total_sqls = 0
    matched_against_opus = 0
    matched_against_final = 0
    qwen_unknown = 0

    qwen_labels = []  # list of {di, round, sql_index, qwen_intent, opus_intent, final_intent}
    case_summary = []

    t0 = time.time()
    for ci, case in enumerate(cases):
        di = case["dataset_index"]
        traj = case["trajectory"]
        sqls = extract_sqls_from_trajectory(traj)
        if not sqls:
            print(f"[{ci+1}/{len(cases)}] di={di}: no SQLs")
            continue

        opus_seq = opus_intents_ordered(case["intents"].get("claude_opus_4_6", []))
        final_seq = final_intents_ordered(case["intents"].get("final", []))

        # Run qwen3.5-plus classifier
        try:
            results = classifier.classify_batch(sqls)
        except Exception as ex:
            print(f"[{ci+1}/{len(cases)}] di={di}: ERROR {ex}", flush=True)
            continue

        case_match_opus = 0
        case_match_final = 0
        case_n_sql = 0
        # Align by index: i-th extracted SQL <-> i-th opus/final label
        for i, (sql, rnd) in enumerate(sqls):
            if i >= len(results):
                continue
            qwen_intent = results[i]["intent"]
            opus_intent = opus_seq[i] if i < len(opus_seq) else None
            final_intent = final_seq[i] if i < len(final_seq) else None

            qwen_labels.append({
                "di": di,
                "i": i,
                "qwen": qwen_intent,
                "opus": opus_intent,
                "final": final_intent,
            })

            if qwen_intent == "unknown":
                qwen_unknown += 1
            if opus_intent and qwen_intent == opus_intent:
                matched_against_opus += 1
                case_match_opus += 1
            if final_intent and qwen_intent == final_intent:
                matched_against_final += 1
                case_match_final += 1
            case_n_sql += 1
            total_sqls += 1

        case_summary.append({
            "di": di,
            "n_sql": case_n_sql,
            "match_opus": case_match_opus,
            "match_final": case_match_final,
        })
        elapsed = time.time() - t0
        print(f"[{ci+1}/{len(cases)}] di={di}: {case_n_sql} SQLs | qwen↔opus={case_match_opus}/{case_n_sql} | qwen↔final={case_match_final}/{case_n_sql} | elapsed={elapsed:.0f}s", flush=True)

    # Aggregate stats
    total_with_opus = sum(1 for x in qwen_labels if x["opus"] is not None)
    total_with_final = sum(1 for x in qwen_labels if x["final"] is not None)
    print(f"\n=== Final ===")
    print(f"Total SQLs: {total_sqls}")
    print(f"qwen unknown rate: {qwen_unknown}/{total_sqls} = {100*qwen_unknown/total_sqls:.2f}%")
    print(f"qwen vs opus: {matched_against_opus}/{total_with_opus} = {100*matched_against_opus/max(1,total_with_opus):.2f}%")
    print(f"qwen vs final: {matched_against_final}/{total_with_final} = {100*matched_against_final/max(1,total_with_final):.2f}%")

    # Per-class F1 (treating final as ground truth)
    per_class = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "support": 0})
    for x in qwen_labels:
        if x["final"] is None:
            continue
        per_class[x["final"]]["support"] += 1
        if x["qwen"] == x["final"]:
            per_class[x["final"]]["tp"] += 1
        else:
            per_class[x["final"]]["fn"] += 1
            per_class[x["qwen"]]["fp"] += 1

    # Confusion: qwen→final
    confusion = Counter()
    for x in qwen_labels:
        if x["final"] is not None and x["qwen"] != x["final"]:
            confusion[(x["final"], x["qwen"])] += 1

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "exp_id": EXP_ID,
        "n_cases": len(case_summary),
        "n_sqls": total_sqls,
        "qwen_unknown": qwen_unknown,
        "match_qwen_vs_opus": matched_against_opus,
        "total_with_opus": total_with_opus,
        "match_qwen_vs_final": matched_against_final,
        "total_with_final": total_with_final,
        "per_class": dict(per_class),
        "top_confusions": confusion.most_common(20),
        "case_summary": case_summary,
        "labels": qwen_labels,
    }
    out_file = OUTPUT_DIR / "qwen_intent_results.json"
    out_file.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    print(f"\nSaved {out_file}")


if __name__ == "__main__":
    main()
