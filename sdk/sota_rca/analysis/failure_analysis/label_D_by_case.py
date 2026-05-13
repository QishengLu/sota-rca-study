#!/usr/bin/env python
"""Write D-axis labels to evaluation_data.meta.failure_analysis.v1.D
for all 4 exp_ids, keyed on merged/D_projection.jsonl.

Reads: merged/D_projection.jsonl (one row per labeled case, produced by Phase C D agent).
Writes: meta.failure_analysis.v1.D (string) + meta.failure_analysis.v1.D_phrase (string).

Non-destructive: preserves primary/secondary/pivot_round/evidence/labeler fields.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "RCAgentEval")

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402
from sqlmodel import Session, create_engine, select  # noqa: E402
from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from harp_config import D_PROJECTION, DB_URL, FRAMEWORKS  # noqa: E402


def main(dry_run: bool) -> None:
    rows = [json.loads(line) for line in D_PROJECTION.open()]
    by_agent: dict[str, dict[int, dict]] = {}
    for r in rows:
        by_agent.setdefault(r["agent"], {})[int(r["case_id"])] = r

    engine = create_engine(DB_URL)
    totals = {}

    with Session(engine) as s:
        for agent_key, by_case in by_agent.items():
            exp_id, _labels_path, _field, _ws = FRAMEWORKS[agent_key]
            stmt = select(EvaluationSample).where(
                EvaluationSample.exp_id == exp_id,
                EvaluationSample.correct == False,  # noqa: E712
                EvaluationSample.stage == "judged",
            )
            samples = list(s.exec(stmt).all())
            updated = skipped = 0
            for sample in samples:
                proj = by_case.get(sample.dataset_index)
                if not proj:
                    skipped += 1
                    continue
                meta = sample.meta or {}
                fa = meta.setdefault("failure_analysis", {})
                v1 = fa.setdefault("v1", {})
                v1["D"] = proj["d_class"]
                v1["D_phrase"] = proj.get("d_phrase")
                v1["D_confidence"] = proj.get("confidence")
                sample.meta = meta
                flag_modified(sample, "meta")
                updated += 1
            totals[agent_key] = (updated, skipped, len(by_case))
            print(f"[{agent_key}] DB rows: update={updated}, skip(no_label)={skipped}, D_projection rows={len(by_case)}")

        if not dry_run:
            s.commit()
            print("COMMITTED")
        else:
            print("DRY RUN (no commit)")

    for k, (u, sk, total) in totals.items():
        print(f"  {k}: labeled_in_db={u} / projection_rows={total}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
