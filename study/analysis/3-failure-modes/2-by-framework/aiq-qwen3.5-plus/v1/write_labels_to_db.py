#!/usr/bin/env python
"""Write failure-mode labels to evaluation_data.meta.failure_analysis.v1.*
for aiq-qwen3.5-plus rows.

Reads labels.jsonl, mutates meta, uses flag_modified before commit.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/nn/SOTA-agents/RCAgentEval")

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402
from sqlmodel import Session, create_engine, select  # noqa: E402
from utu.db import EvaluationSample  # noqa: E402

DB_URL = "postgresql://postgres:postgres@localhost:5433/SOTA-Agents"
EXP_ID = "aiq-qwen3.5-plus"

V1_DIR = Path("/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/v1")


def main(dry_run: bool = False) -> None:
    labels_path = V1_DIR / "labels.jsonl"
    labels = [json.loads(line) for line in labels_path.open()]
    label_by_idx = {l["dataset_index"]: l for l in labels}

    engine = create_engine(DB_URL)

    updated = 0
    skipped = 0
    with Session(engine) as s:
        stmt = select(EvaluationSample).where(
            EvaluationSample.exp_id == EXP_ID,
            EvaluationSample.correct == False,  # noqa: E712
            EvaluationSample.stage == "judged",
        )
        samples = list(s.exec(stmt).all())
        print(f"Found {len(samples)} failed cases in DB; have {len(labels)} labels")

        for sample in samples:
            idx = sample.dataset_index
            lbl = label_by_idx.get(idx)
            if not lbl:
                skipped += 1
                continue
            meta = sample.meta or {}
            fa = meta.setdefault("failure_analysis", {})
            v1 = fa.setdefault("v1", {})
            v1["primary"] = lbl["primary"]
            v1["secondary"] = lbl["secondary"]
            v1["proximate_cause"] = lbl["proximate_cause"]
            v1["pivot_round"] = lbl["pivot_round"]
            v1["evidence"] = lbl["evidence"]
            v1["labeler"] = lbl["labeler"]
            v1["taxonomy_version"] = "aiq-qwen3.5-plus-v1-frozen"

            sample.meta = meta
            flag_modified(sample, "meta")
            updated += 1

        if not dry_run:
            s.commit()
            print(f"COMMITTED. Updated {updated} rows, skipped {skipped}")
        else:
            print(f"DRY RUN. Would update {updated} rows, skip {skipped}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
