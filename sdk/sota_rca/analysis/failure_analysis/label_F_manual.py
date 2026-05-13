#!/usr/bin/env python
"""Write F-axis (per-framework architectural failure) labels.

Reads: merged/F_labels.jsonl — {agent, case_id, F_framework, F_code}
Writes: meta.failure_analysis.v1.F_framework, meta.failure_analysis.v1.F_code

F_framework and F_code are paired: either both null (non-architectural failure)
or both non-null (architectural failure with framework-specific code).
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
from harp_config import DB_URL, FRAMEWORKS, F_CATALOG_JSON  # noqa: E402


def main(dry_run: bool) -> None:
    if not F_CATALOG_JSON.exists():
        print(f"MISSING {F_CATALOG_JSON}; nothing to write. If no F labels exist, that's OK.")
        return

    rows = [json.loads(line) for line in F_CATALOG_JSON.open()]
    by_agent: dict[str, dict[int, dict]] = {}
    for r in rows:
        by_agent.setdefault(r["agent"], {})[int(r["case_id"])] = r

    engine = create_engine(DB_URL)

    with Session(engine) as s:
        total_updated = 0
        for agent_key, by_case in by_agent.items():
            exp_id, _labels_path, _field, _ws = FRAMEWORKS[agent_key]
            stmt = select(EvaluationSample).where(
                EvaluationSample.exp_id == exp_id,
                EvaluationSample.correct == False,  # noqa: E712
                EvaluationSample.stage == "judged",
            )
            samples = list(s.exec(stmt).all())
            updated = 0
            for sample in samples:
                f_row = by_case.get(sample.dataset_index)
                if not f_row:
                    continue
                meta = sample.meta or {}
                fa = meta.setdefault("failure_analysis", {})
                v1 = fa.setdefault("v1", {})
                v1["F_framework"] = f_row["F_framework"]
                v1["F_code"] = f_row["F_code"]
                sample.meta = meta
                flag_modified(sample, "meta")
                updated += 1
            total_updated += updated
            print(f"[{agent_key}] F-labeled {updated} / {len(by_case)} rows")

        if not dry_run:
            s.commit()
            print(f"COMMITTED ({total_updated} total)")
        else:
            print(f"DRY RUN ({total_updated} would be updated)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
