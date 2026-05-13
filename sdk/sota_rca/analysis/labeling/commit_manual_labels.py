#!/usr/bin/env python
"""Commit manual classifications to meta.llm_intents.final with rule='user_manual_review'."""
import argparse
import json
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session

sys.path.insert(0, str(__file__).rsplit("/scripts/", 1)[0])
from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402

DB_URL = "postgresql://postgres:postgres@localhost:5433/SOTA-Agents"

# Manual classifications (position index in /tmp/pending_all.json → intent)
LABELS = {
    1: "latency_ranking", 2: "latency_ranking", 3: "service_trace_scan", 4: "latency_ranking",
    5: "keyword_search", 6: "service_trace_scan", 7: "call_tree_build", 8: "keyword_search",
    9: "keyword_search", 10: "keyword_search", 11: "keyword_search", 12: "keyword_search",
    13: "call_tree_build", 14: "call_tree_build", 15: "call_tree_build", 16: "keyword_search",
    17: None, 18: "call_tree_build", 19: "call_tree_build", 20: "keyword_search",
    21: "keyword_search", 22: None, 23: "keyword_search", 24: "keyword_search",
    25: "keyword_search", 26: "keyword_search", 27: "error_rate_scan", 28: "error_rate_scan",
    29: "error_rate_scan", 30: "error_rate_scan", 31: "call_tree_build", 32: "call_tree_build",
    33: "call_tree_build", 34: "call_tree_build", 35: "call_tree_build", 36: None,
    37: "keyword_search", 38: "error_rate_scan", 39: "service_trace_scan", 40: "service_trace_scan",
    41: "service_trace_scan", 42: "keyword_search", 43: "keyword_search", 44: "keyword_search",
    45: "error_rate_scan", 46: "keyword_search", 47: "call_tree_build", 48: "call_tree_build",
    49: "call_tree_build", 50: "error_rate_scan", 51: "call_tree_build", 52: "call_tree_build",
    53: "service_trace_scan", 54: "error_rate_scan", 55: "keyword_search", 56: "call_tree_build",
    57: "call_tree_build", 58: "call_tree_build", 59: "keyword_search", 60: "service_trace_scan",
    61: "call_tree_build", 62: "error_rate_scan", 63: "call_tree_build", 64: "latency_ranking",
    65: "call_tree_build", 66: "call_tree_build", 67: "error_rate_scan", 68: "error_rate_scan",
    69: "call_tree_build", 70: "service_trace_scan", 71: "call_tree_build", 72: "service_trace_scan",
    73: "error_rate_scan", 74: "keyword_search", 75: "keyword_search", 76: "service_trace_scan",
    77: "service_trace_scan", 78: "service_trace_scan", 79: "service_trace_scan", 80: "keyword_search",
    81: "call_tree_build", 82: "service_trace_scan", 83: "service_trace_scan", 84: "service_trace_scan",
    85: "keyword_search", 86: "call_tree_build", 87: "service_trace_scan", 88: "throughput_compare",
    89: "keyword_search", 90: None,  # ambiguous
    91: "service_trace_scan", 92: "keyword_search", 93: "service_trace_scan", 94: "service_trace_scan",
    95: "error_rate_scan", 96: "error_rate_scan", 97: "call_tree_build", 98: "call_tree_build",
    99: "service_trace_scan", 100: None,
    101: "latency_ranking", 102: "call_tree_build", 103: "call_tree_build", 104: "call_tree_build",
    105: "call_tree_build", 106: "call_tree_build", 107: "call_tree_build", 108: "call_tree_build",
    109: "error_rate_scan", 110: "call_tree_build", 111: "service_trace_scan", 112: "error_rate_scan",
    113: "keyword_search", 114: "keyword_search", 115: "service_trace_scan", 116: "keyword_search",
    117: "keyword_search", 118: "call_tree_build", 119: "error_rate_scan", 120: "latency_ranking",
    121: "error_rate_scan", 122: "error_rate_scan", 123: "error_rate_scan", 124: "keyword_search",
    125: "call_tree_build", 126: "error_rate_scan", 127: "error_rate_scan", 128: "error_rate_scan",
    129: "call_tree_build", 130: "call_tree_build", 131: "service_trace_scan", 132: "error_rate_scan",
    133: "latency_ranking", 134: "latency_ranking", 135: "latency_ranking", 136: "latency_ranking",
    137: "error_timeline", 138: "service_trace_scan", 139: "call_tree_build", 140: "keyword_search",
    141: "call_tree_build", 142: "keyword_search", 143: "service_trace_scan", 144: "service_trace_scan",
    145: "call_tree_build", 146: "latency_ranking", 147: "error_rate_scan", 148: "call_tree_build",
    149: "call_tree_build", 150: "call_tree_build",
    151: "call_tree_build", 152: "call_tree_build", 153: "keyword_search", 154: "error_rate_scan",
    155: "service_trace_scan", 156: "error_rate_scan", 157: "error_rate_scan", 158: "call_tree_build",
    159: "keyword_search", 160: "service_trace_scan", 161: "latency_ranking", 162: "service_trace_scan",
    163: "latency_ranking", 164: "keyword_search", 165: "keyword_search", 166: "keyword_search",
    167: "call_tree_build", 168: "latency_ranking", 169: "throughput_compare", 170: "keyword_search",
    171: "keyword_search", 172: "keyword_search", 173: "error_rate_scan", 174: "keyword_search",
    175: "keyword_search", 176: "keyword_search", 177: "error_rate_scan", 178: "error_timeline",
    179: "keyword_search", 180: "latency_ranking", 181: "keyword_search", 182: "keyword_search",
    183: "keyword_search", 184: "call_tree_build", 185: "call_tree_build", 186: "latency_ranking",
    187: "keyword_search", 188: "call_tree_build", 189: "keyword_search", 190: "keyword_search",
    191: "service_trace_scan", 192: "error_rate_scan", 193: "keyword_search", 194: "call_tree_build",
    195: "keyword_search", 196: "keyword_search", 197: "keyword_search", 198: "keyword_search",
    199: "call_tree_build", 200: "keyword_search",
    201: "call_tree_build", 202: "call_tree_build", 203: "keyword_search", 204: "service_trace_scan",
    205: "error_rate_scan", 206: "keyword_search", 207: "error_rate_scan", 208: "call_tree_build",
    209: "call_tree_build", 210: "error_rate_scan", 211: "keyword_search", 212: "call_tree_build",
    213: "latency_ranking", 214: "keyword_search", 215: "keyword_search", 216: "keyword_search",
    217: "call_tree_build", 218: "keyword_search", 219: "service_trace_scan", 220: "call_tree_build",
    221: "keyword_search", 222: "throughput_compare", 223: "keyword_search", 224: "keyword_search",
    225: "keyword_search", 226: "keyword_search", 227: "keyword_search", 228: "latency_ranking",
    229: "keyword_search", 230: "keyword_search", 231: "service_trace_scan", 232: "error_rate_scan",
    233: "keyword_search", 234: "keyword_search", 235: "keyword_search", 236: "service_trace_scan",
    237: "call_tree_build", 238: "latency_ranking", 239: "keyword_search", 240: "call_tree_build",
    241: "keyword_search", 242: "keyword_search", 243: "keyword_search", 244: "keyword_search",
    245: "throughput_compare", 246: "trace_follow", 247: "throughput_compare", 248: "error_rate_scan",
    249: "latency_ranking", 250: "latency_ranking", 251: "error_rate_scan", 252: "service_trace_scan",
    253: "error_rate_scan",
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    args = p.parse_args()

    pending = json.load(open("/tmp/pending_all.json"))
    eng = create_engine(DB_URL)

    from collections import Counter
    by_intent: Counter = Counter()
    skip_count = 0
    staged: list[dict] = []
    for i, item in enumerate(pending, 1):
        intent = LABELS.get(i)
        if intent is None:
            skip_count += 1
            continue
        by_intent[intent] += 1
        staged.append({
            "exp": item["exp"], "idx": item["idx"],
            "round": item["round"], "sql_index": item["sql_index"],
            "intent": intent,
        })

    print(f"Total to commit: {len(staged)}")
    print(f"Skipped (intent=None): {skip_count}")
    print(f"\nBy intent:")
    for i, n in by_intent.most_common():
        print(f"  {i}: {n}")

    if not args.write:
        print("\n(dry-run — pass --write to commit.)")
        return

    per_sample: dict[tuple[str, int], list[dict]] = {}
    for s in staged:
        per_sample.setdefault((s["exp"], s["idx"]), []).append({
            "round": s["round"], "sql_index": s["sql_index"],
            "intent": s["intent"], "rule": "user_manual_review",
        })
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
