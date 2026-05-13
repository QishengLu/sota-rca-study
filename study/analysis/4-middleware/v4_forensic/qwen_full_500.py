"""qwen-plus 对 thinkdepthai-qwen3.5-plus 全部 500 case 打 intent，对比 final labels.

并发 10，预期 30-40 分钟。"""
import json
import os
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

os.environ["UTU_DB_URL"] = "postgresql://postgres:postgres@localhost:5433/SOTA-Agents"
sys.path.insert(0, "/home/nn/SOTA-agents/RCAgentEval")
sys.path.insert(0, "/home/nn/SOTA-agents/Deep_Research/middleware")

from sqlalchemy import create_engine, text
from langchain_openai import ChatOpenAI
from utu.eval.analysis.llm_intent_classifier import extract_sql_rounds
from intent_classifier import IntentClassifier

EXP_ID = "thinkdepthai-qwen3.5-plus"
OUT_FILE = Path("/home/nn/SOTA-agents/analysis/4-middleware/v4_forensic/qwen_500_results.json")
PROGRESS_FILE = Path("/home/nn/SOTA-agents/analysis/4-middleware/v4_forensic/qwen_500_progress.json")
N_WORKERS = 10
API_KEY = os.environ.get("OPENAI_API_KEY", "sk-1101031b58f74cc7b093e4535a3436ff")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"


def fetch_all_cases():
    e = create_engine(os.environ["UTU_DB_URL"])
    with e.connect() as c:
        rows = c.execute(text("""
            SELECT dataset_index, trajectories,
                   meta::jsonb->'llm_intents'->'final' AS final_labels
            FROM evaluation_data
            WHERE exp_id = :eid
            ORDER BY dataset_index
        """), {"eid": EXP_ID}).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def extract_sqls(traj_str):
    if not traj_str:
        return []
    if isinstance(traj_str, str):
        traj = json.loads(traj_str)
    else:
        traj = traj_str
    rounds = extract_sql_rounds(traj)
    return [(s, r.round_index) for r in rounds for s in r.queries]


def make_classifier():
    m = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0.0,
        max_tokens=4096,
        request_timeout=120,
        max_retries=2,
    )
    return IntentClassifier(m)


def process_case(case_data):
    """One worker handles one case end-to-end."""
    di, traj_str, final_labels = case_data
    try:
        sqls = extract_sqls(traj_str)
        if not sqls:
            return {"di": di, "n_sql": 0, "skipped": True}
        cls = make_classifier()
        results = cls.classify_batch(sqls)
        qwen_intents = [r["intent"] for r in results]
        # final labels: insertion order (no global_index)
        final_intents = [e["intent"] for e in (final_labels or [])]

        match = 0
        n_compared = min(len(qwen_intents), len(final_intents))
        per_pair = []
        for i in range(n_compared):
            ok = qwen_intents[i] == final_intents[i]
            match += ok
            per_pair.append({"i": i, "qwen": qwen_intents[i], "final": final_intents[i], "match": ok})

        return {
            "di": di,
            "n_sql_qwen": len(qwen_intents),
            "n_sql_final": len(final_intents),
            "n_compared": n_compared,
            "n_match": match,
            "qwen_intents": qwen_intents,
            "pairs": per_pair,
        }
    except Exception as ex:
        return {"di": di, "error": str(ex)[:200]}


def main():
    print("Loading 500 cases from DB...", flush=True)
    cases = fetch_all_cases()
    print(f"  {len(cases)} cases", flush=True)

    results_by_di = {}
    n_done = 0
    n_total_sqls = 0
    n_total_match = 0
    n_total_compared = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
        futures = {ex.submit(process_case, c): c[0] for c in cases}
        for fut in as_completed(futures):
            di = futures[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = {"di": di, "error": f"future-exc: {e}"}
            results_by_di[di] = r
            n_done += 1
            if "n_match" in r:
                n_total_sqls += r["n_sql_qwen"]
                n_total_match += r["n_match"]
                n_total_compared += r["n_compared"]
            elapsed = time.time() - t0
            rate = n_done / elapsed if elapsed > 0 else 0
            eta = (len(cases) - n_done) / rate if rate > 0 else 0
            agreement = 100 * n_total_match / max(1, n_total_compared)
            print(f"[{n_done}/{len(cases)}] di={di}  agreement={agreement:.1f}%  elapsed={elapsed:.0f}s  ETA={eta:.0f}s", flush=True)

            # Persist intermediate
            if n_done % 25 == 0 or n_done == len(cases):
                PROGRESS_FILE.write_text(json.dumps({
                    "n_done": n_done,
                    "n_total": len(cases),
                    "n_total_match": n_total_match,
                    "n_total_compared": n_total_compared,
                    "agreement": agreement,
                }))

    # Save full results
    n_errored = sum(1 for r in results_by_di.values() if "error" in r)
    OUT_FILE.write_text(json.dumps({
        "exp_id": EXP_ID,
        "model": MODEL,
        "n_cases": len(cases),
        "n_errored": n_errored,
        "n_total_compared": n_total_compared,
        "n_total_match": n_total_match,
        "agreement": 100 * n_total_match / max(1, n_total_compared),
        "results": results_by_di,
    }, default=str))
    print(f"\nDone. Saved {OUT_FILE}", flush=True)
    print(f"Total: {n_total_match}/{n_total_compared} = {100*n_total_match/max(1,n_total_compared):.2f}% agreement (qwen vs final)", flush=True)
    print(f"Errored cases: {n_errored}", flush=True)


if __name__ == "__main__":
    main()
