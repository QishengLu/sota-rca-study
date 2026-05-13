"""Write failure_analysis.v1 labels to DB meta field for thinkdepthai-claude-sonnet-4.6.

Per Phase 7.3 spec: each agent writes its own primary/secondary theme labels
into meta.failure_analysis.v1.{primary, secondary, pivot_round, proximate_cause}.
No D/R columns at this stage — those are assigned only at the Phase 7.5 merge step.

Dry-run: python write_labels_to_db.py --dry-run
Commit:  python write_labels_to_db.py
"""
import json
import os
import sys

os.environ.setdefault("UTU_DB_URL", "postgresql://postgres:postgres@localhost:5433/SOTA-Agents")

sys.path.insert(0, "/home/nn/SOTA-agents/RCAgentEval")

import sqlmodel
from sqlalchemy.orm.attributes import flag_modified
from utu.db.eval_datapoint import EvaluationSample
from utu.utils.sqlmodel_utils import SQLModelUtils

LABELS_FILE = "/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-claude-sonnet-4.6/v1/labels.jsonl"
EXP_ID = "thinkdepthai-claude-sonnet-4.6"
DRY_RUN = "--dry-run" in sys.argv


def load_labels():
    labels = {}
    with open(LABELS_FILE) as f:
        for line in f:
            d = json.loads(line)
            labels[d["dataset_index"]] = d
    return labels


def main():
    labels = load_labels()
    print(f"Loaded {len(labels)} labels from {LABELS_FILE}")

    updated = 0
    not_found = []

    with SQLModelUtils.create_session() as session:
        dataset_indexes = list(labels.keys())
        samples = session.exec(
            sqlmodel.select(EvaluationSample).where(
                EvaluationSample.exp_id == EXP_ID,
                EvaluationSample.dataset_index.in_(dataset_indexes),
            )
        ).all()

        print(f"Found {len(samples)} matching samples in DB")

        sample_map = {s.dataset_index: s for s in samples}

        for case_idx, label in labels.items():
            sample = sample_map.get(case_idx)
            if sample is None:
                not_found.append(case_idx)
                continue

            meta = sample.meta or {}
            fa = meta.setdefault("failure_analysis", {})
            fa["v1"] = {
                "primary": label["primary"],
                "secondary": label.get("secondary"),
                "pivot_round": label.get("pivot_round"),
                "proximate_cause": label["proximate_cause"],
            }
            sample.meta = meta
            flag_modified(sample, "meta")
            updated += 1

        if DRY_RUN:
            print(f"[DRY RUN] Would commit {updated} updates")
            session.rollback()
        else:
            session.commit()
            print(f"Committed {updated} updates")

    if not_found:
        print(f"WARNING: {len(not_found)} cases not found in DB: {not_found[:10]}")


if __name__ == "__main__":
    main()
