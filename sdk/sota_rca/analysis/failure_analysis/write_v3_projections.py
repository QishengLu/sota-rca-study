"""X-6.1: Apply relabel queue to projection JSONLs and emit DB R-update queue.

Inputs:
  - merged/relabel_queue.v2.jsonl (the actions)
  - merged/D_projection.jsonl, merged/PD_projection.jsonl (current projections)

Outputs (atomic temp+rename):
  - merged/D_projection.v3.jsonl     (D label removed → set d_class=null)
  - merged/PD_projection.v3.jsonl    (process_defects / framework_specific lists pruned)
  - merged/R_relabel_db_queue.v3.jsonl (DB update queue, one row per case to UPDATE meta.failure_analysis.v1.R)

R is stored in DB rather than projection file. We emit a queue of operations for a downstream apply
to write into postgres.
"""
from __future__ import annotations
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path("analysis/3-failure-modes/merged")
QUEUE = ROOT / "relabel_queue.v2.jsonl"
D_IN = ROOT / "D_projection.jsonl"
PD_IN = ROOT / "PD_projection.jsonl"

D_OUT = ROOT / "D_projection.v3.jsonl"
PD_OUT = ROOT / "PD_projection.v3.jsonl"
DB_R_OUT = ROOT / "R_relabel_db_queue.v3.jsonl"


# Map D shorthand "D1".."D7" → projection's d_class string
D_SHORT_TO_LONG = {
    "D1": "D_victim_silent_on_path",
    "D2": "D_cross_layer_signal_gap",
    "D3": "D_ambient_noise_dominates",
    "D4": "D_edge_symmetric_ambiguity",
    "D5": "D_cascade_symptom_louder_than_GT",
    "D6": "D_name_twin_on_path",
    "D7": "D_diluted_multi_candidate",
    "D8": "D_dataset_anomaly",
}
D_LONG_TO_SHORT = {v: k for k, v in D_SHORT_TO_LONG.items()}


def write_jsonl(path: Path, rows: list[dict]):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
            f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def main():
    # Load queue grouped by (agent, case_id)
    actions_by_case: dict[tuple, list[dict]] = defaultdict(list)
    with QUEUE.open() as f:
        for line in f:
            r = json.loads(line)
            actions_by_case[(r["agent"], r["case_id"])].append(r)

    # ---- D projection update ----
    d_rows = []
    d_changed = 0
    d_relabeled = 0
    d_removed = 0
    with D_IN.open() as f:
        for line in f:
            row = json.loads(line)
            agent = row["agent"]
            cid = row["case_id"]
            cur_d_short = D_LONG_TO_SHORT.get(row.get("d_class") or "")
            if not cur_d_short:
                d_rows.append(row)  # unrecognized → keep
                continue
            updated = dict(row)
            applied = []
            for act in actions_by_case.get((agent, cid), []):
                if act["class"] != cur_d_short:
                    continue
                action = act["action"]
                if action == "remove_label":
                    updated["d_class"] = None
                    updated["d_phrase"] = None
                    updated["v3_action"] = "removed"
                    updated["v3_reason"] = act.get("reason_short")
                    applied.append("removed")
                    d_removed += 1
                elif action == "relabel_class":
                    new_short = (act.get("new_class") or "").split(" or ")[0].strip()
                    new_long = D_SHORT_TO_LONG.get(new_short)
                    if new_long:
                        updated["d_class"] = new_long
                        updated["v3_action"] = "relabeled"
                        updated["v3_from"] = D_SHORT_TO_LONG.get(cur_d_short)
                        updated["v3_to"] = new_long
                        updated["v3_reason"] = act.get("reason_short")
                        applied.append("relabeled")
                        d_relabeled += 1
            if applied:
                d_changed += 1
            d_rows.append(updated)

    # ---- PD projection update ----
    pd_rows = []
    pd_changed = 0
    pd_removed_count = 0
    with PD_IN.open() as f:
        for line in f:
            row = json.loads(line)
            agent = row["agent"]
            cid = row["case_id"]
            actions = actions_by_case.get((agent, cid), [])
            if not actions:
                pd_rows.append(row)
                continue
            updated = dict(row)
            removed = []
            relabeled = []
            for act in actions:
                cls = act["class"]
                action = act["action"]
                if action == "remove_label":
                    if cls in (updated.get("process_defects") or []):
                        updated["process_defects"] = [c for c in updated["process_defects"] if c != cls]
                        removed.append(cls)
                        pd_removed_count += 1
                    if cls in (updated.get("framework_specific") or []):
                        updated["framework_specific"] = [c for c in updated["framework_specific"] if c != cls]
                        removed.append(cls)
                        pd_removed_count += 1
                # relabel_class for PD is rare; current taxonomy doesn't suggest it. Skip.
            if removed or relabeled:
                pd_changed += 1
                updated["v3_removed"] = removed
                updated["v3_relabeled"] = relabeled
            pd_rows.append(updated)

    # ---- DB R update queue ----
    # For each (agent, case_id) where action targets a U class:
    db_r_rows = []
    db_remove_count = 0
    db_relabel_count = 0
    seen_db = set()
    for (agent, cid), acts in actions_by_case.items():
        for act in acts:
            cls = act["class"]
            if not (cls.startswith("U") or cls.startswith("aiq.R") or
                    cls.startswith("claudecode.R") or cls.startswith("sonnet.R") or
                    cls.startswith("qwen.R")):
                continue
            row = {
                "agent": agent,
                "case_id": cid,
                "old_class": cls,
                "action": act["action"],
                "new_class": act.get("new_class"),
                "reason": act.get("reason_short"),
            }
            db_r_rows.append(row)
            seen_db.add((agent, cid))
            if act["action"] == "remove_label":
                db_remove_count += 1
            elif act["action"] == "relabel_class":
                db_relabel_count += 1

    write_jsonl(D_OUT, d_rows)
    write_jsonl(PD_OUT, pd_rows)
    write_jsonl(DB_R_OUT, db_r_rows)

    print(f"D projection: {d_changed} cases changed (removed={d_removed}, relabeled={d_relabeled})")
    print(f"  → {D_OUT}")
    print(f"PD projection: {pd_changed} cases changed (labels removed={pd_removed_count})")
    print(f"  → {PD_OUT}")
    print(f"DB R update queue: {len(db_r_rows)} rows ({len(seen_db)} unique cases; remove={db_remove_count}, relabel={db_relabel_count})")
    print(f"  → {DB_R_OUT}")


if __name__ == "__main__":
    main()
