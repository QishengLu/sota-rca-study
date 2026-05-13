"""Write failure_analysis.v1 labels to DB meta field for thinkdepthai-qwen3.5-plus."""
import json
import os
import sys

os.environ.setdefault("UTU_DB_URL", "postgresql://postgres:postgres@localhost:5433/SOTA-Agents")

sys.path.insert(0, "/home/nn/SOTA-agents/RCAgentEval")

from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified
from utu.db.eval_datapoint import EvaluationSample
from utu.utils.sqlmodel_utils import SQLModelUtils

LABELS_FILE = "/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/labels.jsonl"
EXP_ID = "thinkdepthai-qwen3.5-plus"
DRY_RUN = "--dry-run" in sys.argv


def load_labels():
    labels = {}
    with open(LABELS_FILE) as f:
        for line in f:
            d = json.loads(line)
            labels[d["case"]] = d
    return labels


def main():
    labels = load_labels()
    print(f"Loaded {len(labels)} labels from {LABELS_FILE}")

    updated = 0
    not_found = []

    with SQLModelUtils.create_session() as session:
        # Fetch all EvaluationSamples for this exp_id whose dataset_index is in labels
        dataset_indexes = list(labels.keys())
        samples = session.exec(
            __import__("sqlmodel").select(EvaluationSample).where(
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
            meta["failure_analysis"] = {
                "v1": {
                    "T": label["label"],
                    "D": label["D"],
                    "R": label["R"],
                    "pivot_round": label["pivot_round"],
                    "proximate_cause": label["proximate_cause"],
                    "gt_services": label["gt_services"],
                    "predicted": label["predicted"],
                }
            }
            sample.meta = meta
            flag_modified(sample, "meta")
            updated += 1

        if not DRY_RUN:
            session.commit()
            print(f"Committed {updated} updates")
        else:
            print(f"[DRY RUN] Would commit {updated} updates")

    if not_found:
        print(f"WARNING: {len(not_found)} cases not found in DB: {not_found[:10]}")

    print(f"Done. Updated: {updated}, Not found: {len(not_found)}")


if __name__ == "__main__":
    main()
