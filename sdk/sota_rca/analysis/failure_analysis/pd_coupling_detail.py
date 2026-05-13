#!/usr/bin/env python
"""Identify the specific D or R class each red-zone PD couples with, and print
yellow-zone couplings for coupled_with tags in PD_taxonomy.md.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harp_config import DB_URL, FRAMEWORKS  # noqa: E402

sys.path.insert(0, "RCAgentEval")
from sqlmodel import Session, create_engine, select  # noqa: E402
from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402


proj_path = Path("analysis/3-failure-modes/merged/PD_projection_refactored.jsonl")
d_path = Path("analysis/3-failure-modes/merged/D_projection.jsonl")

rows = [json.loads(l) for l in proj_path.open()]
d_rows = [json.loads(l) for l in d_path.open()]
d_map = {(r["agent"], int(r["case_id"])): r["d_class"] for r in d_rows}

engine = create_engine(DB_URL)
r_map: dict[tuple[str, int], str] = {}
with Session(engine) as s:
    for agent_key, (exp_id, *_) in FRAMEWORKS.items():
        stmt = select(EvaluationSample).where(
            EvaluationSample.exp_id == exp_id,
            EvaluationSample.correct == False,  # noqa: E712
            EvaluationSample.stage == "judged",
        )
        for sample in s.exec(stmt).all():
            meta = sample.meta or {}
            v1 = (meta.get("failure_analysis") or {}).get("v1") or {}
            r = v1.get("R") or v1.get("unified_R")
            if r:
                r_map[(agent_key, sample.dataset_index)] = r


pd_names = sorted({pd for row in rows for pd in row["process_defects"]})
print(f"Analyzing {len(pd_names)} unified PDs")

# For each PD, report conditional distribution of R and D
for pd_name in pd_names:
    cases_with = [(r["agent"], int(r["case_id"])) for r in rows if pd_name in r["process_defects"]]
    r_counter = Counter(r_map.get(k, "?") for k in cases_with)
    d_counter = Counter(d_map.get(k, "?") for k in cases_with)
    total = len(cases_with)
    print(f"\n=== {pd_name} (n={total}) ===")
    print("  Top R classes:")
    for cls, ct in r_counter.most_common(5):
        pct = 100 * ct / total
        print(f"    {cls}: {ct} ({pct:.1f}%)")
    print("  Top D classes:")
    for cls, ct in d_counter.most_common(5):
        pct = 100 * ct / total
        print(f"    {cls}: {ct} ({pct:.1f}%)")
