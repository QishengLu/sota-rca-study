#!/usr/bin/env python
"""Write PD-axis (process-defects multi-label) labels to
evaluation_data.meta.failure_analysis.v1.process_defects / process_defects_framework_specific /
process_defects_evidence / process_defects_confidence.

Reads: merged/PD_projection.jsonl (one row per labeled case, produced by Phase PD-C.3).
Writes to meta.failure_analysis.v1:
- process_defects: list[str] (unified PD names, can be empty)
- process_defects_framework_specific: list[str] (e.g. ["qwen.PD_ServiceAvgInsteadOfSpanMax"])
- process_defects_evidence: dict[str, str] (PD name -> one-line evidence)
- process_defects_confidence: "high" | "medium" | "low"

Non-destructive: preserves D/R/F and any other v1 fields.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "RCAgentEval")

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402
from sqlmodel import Session, create_engine, select  # noqa: E402
from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from harp_config import PD_PROJECTION, DB_URL, FRAMEWORKS  # noqa: E402


def main(dry_run: bool) -> None:
    rows = [json.loads(line) for line in PD_PROJECTION.open()]
    by_agent: dict[str, dict[int, dict]] = {}
    for r in rows:
        by_agent.setdefault(r["agent"], {})[int(r["case_id"])] = r

    engine = create_engine(DB_URL)
    totals: dict[str, tuple[int, int, int]] = {}
    pd_counter: Counter[str] = Counter()
    fw_counter: Counter[str] = Counter()
    len_histogram: Counter[int] = Counter()

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
                pds = list(proj.get("process_defects", []))
                fws = list(proj.get("framework_specific", []))
                v1["process_defects"] = pds
                v1["process_defects_framework_specific"] = fws
                v1["process_defects_evidence"] = proj.get("evidence", {})
                v1["process_defects_confidence"] = proj.get("confidence", "medium")
                sample.meta = meta
                flag_modified(sample, "meta")
                updated += 1
                for pd in pds:
                    pd_counter[pd] += 1
                for fw in fws:
                    fw_counter[fw] += 1
                len_histogram[len(pds)] += 1
            totals[agent_key] = (updated, skipped, len(by_case))
            print(
                f"[{agent_key}] DB rows: update={updated}, "
                f"skip(no_label)={skipped}, PD_projection rows={len(by_case)}"
            )

        if not dry_run:
            s.commit()
            print("COMMITTED")
        else:
            print("DRY RUN (no commit)")

    print("\n=== Per-agent totals ===")
    for k, (u, sk, total) in totals.items():
        print(f"  {k}: labeled_in_db={u} / projection_rows={total}")

    print("\n=== Unified PD counts ===")
    for pd, ct in pd_counter.most_common():
        print(f"  {pd}: {ct}")
    print("\n=== Framework-specific PD counts ===")
    for pd, ct in fw_counter.most_common():
        print(f"  {pd}: {ct}")
    print("\n=== Multi-label len histogram ===")
    for n in sorted(len_histogram):
        print(f"  len={n}: {len_histogram[n]} cases")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
