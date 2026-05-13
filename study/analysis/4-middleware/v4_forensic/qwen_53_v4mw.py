"""qwen-plus 对 thinkdepthai-qwen3.5-plus-2026-02-15-mw-v4-run 53 case 打 intent."""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

os.environ["UTU_DB_URL"] = "postgresql://postgres:postgres@localhost:5433/SOTA-Agents"
sys.path.insert(0, "/home/nn/SOTA-agents/RCAgentEval")
sys.path.insert(0, "/home/nn/SOTA-agents/Deep_Research/middleware")

from sqlalchemy import create_engine, text
from langchain_openai import ChatOpenAI
from utu.eval.analysis.llm_intent_classifier import extract_sql_rounds
from intent_classifier import IntentClassifier

EXP_ID = "thinkdepthai-qwen3.5-plus-2026-02-15-mw-v4-run"
OUT_FILE = Path("/home/nn/SOTA-agents/analysis/4-middleware/v4_forensic/qwen_53_v4mw_results.json")
N_WORKERS = 10
API_KEY = "sk-1101031b58f74cc7b093e4535a3436ff"


def fetch_cases():
    e = create_engine(os.environ["UTU_DB_URL"])
    with e.connect() as c:
        rows = c.execute(text("""
            SELECT dataset_index, trajectories
            FROM evaluation_data WHERE exp_id = :eid ORDER BY dataset_index
        """), {"eid": EXP_ID}).fetchall()
    return [(r[0], r[1]) for r in rows]


def make_classifier():
    m = ChatOpenAI(model="qwen-plus", api_key=API_KEY,
                   base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                   temperature=0.0, max_tokens=4096, request_timeout=120, max_retries=2)
    return IntentClassifier(m)


def process_case(case_data):
    di, traj_str = case_data
    try:
        if isinstance(traj_str, str):
            traj = json.loads(traj_str)
        else:
            traj = traj_str
        rounds = extract_sql_rounds(traj)
        sqls = [(s, r.round_index) for r in rounds for s in r.queries]
        if not sqls:
            return {"di": di, "n_sql": 0, "skipped": True}
        cls = make_classifier()
        results = cls.classify_batch(sqls)
        # qwen returns global_index implicitly via order
        intents_per_pos = []
        for i, (sql, rnd) in enumerate(sqls):
            intents_per_pos.append({
                "global_index": i + 1,
                "round": rnd,
                "intent": results[i]["intent"],
            })
        return {"di": di, "n_sql": len(sqls), "qwen": intents_per_pos}
    except Exception as ex:
        return {"di": di, "error": str(ex)[:200]}


def main():
    print("Loading 53 v4 mw cases...", flush=True)
    cases = fetch_cases()
    print(f"  {len(cases)} cases", flush=True)
    results = {}
    n_done = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
        futures = {ex.submit(process_case, c): c[0] for c in cases}
        for fut in as_completed(futures):
            di = futures[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = {"di": di, "error": f"future-exc: {e}"}
            results[str(di)] = r
            n_done += 1
            elapsed = time.time() - t0
            print(f"[{n_done}/{len(cases)}] di={di} n_sql={r.get('n_sql','?')} elapsed={elapsed:.0f}s", flush=True)
    OUT_FILE.write_text(json.dumps({"exp_id": EXP_ID, "results": results}, default=str))
    print(f"\nDone. Saved {OUT_FILE}", flush=True)


if __name__ == "__main__":
    main()
