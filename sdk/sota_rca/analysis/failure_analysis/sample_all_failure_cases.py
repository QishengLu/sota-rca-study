"""Generate verify_samples.jsonl covering ALL 372 labeled failure cases.

For each (agent, case_id) in the failure pool:
- classes_to_verify = its actual D + R + PD(+framework_specific) labels from projections + DB
- Skip D_dataset_anomaly (D8) per plan

Output: merged/verify_samples.jsonl (overwrites the stratified-sample file)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).parent))
from harp_config import D_PROJECTION, FRAMEWORKS, MERGED, PD_PROJECTION

D_CLASS_MAP = {
    "D_victim_silent_on_path": "D1",
    "D_cross_layer_signal_gap": "D2",
    "D_ambient_noise_dominates": "D3",
    "D_edge_symmetric_ambiguity": "D4",
    "D_cascade_symptom_louder_than_GT": "D5",
    "D_name_twin_on_path": "D6",
    "D_diluted_multi_candidate": "D7",
    # D8 dataset_anomaly skipped
}

EXP_TO_AGENT = {exp: key for key, (exp, *_rest) in FRAMEWORKS.items()}


def main():
    # --- Load D labels ---
    d_per_case: dict[tuple[str, int], str] = {}
    with D_PROJECTION.open() as f:
        for ln in f:
            row = json.loads(ln)
            d_cls = row["d_class"]
            if d_cls not in D_CLASS_MAP:
                continue
            d_per_case[(row["agent"], int(row["case_id"]))] = D_CLASS_MAP[d_cls]

    # --- Load PD labels (multi-label) ---
    pd_per_case: dict[tuple[str, int], list[str]] = defaultdict(list)
    with PD_PROJECTION.open() as f:
        for ln in f:
            row = json.loads(ln)
            ag = row["agent"]; cid = int(row["case_id"])
            for pd_cls in row.get("process_defects", []):
                pd_per_case[(ag, cid)].append(pd_cls)
            for pd_cls in row.get("framework_specific", []):
                pd_per_case[(ag, cid)].append(pd_cls)

    # --- Load R labels from DB + data_dir ---
    conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5433/SOTA-Agents")
    r_per_case: dict[tuple[str, int], str] = {}
    data_dirs: dict[tuple[str, int], str] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT exp_id, dataset_index, meta->'failure_analysis'->'v1'->>'R' AS R, meta->>'path' AS data_dir
            FROM evaluation_data
            WHERE meta->'failure_analysis'->'v1' IS NOT NULL
            """
        )
        for exp_id, cid, r_cls, dd in cur.fetchall():
            agent = EXP_TO_AGENT[exp_id]
            key = (agent, int(cid))
            if r_cls:
                r_per_case[key] = r_cls
            data_dirs[key] = dd or ""
    conn.close()

    # Build the universe: union of cases that have ANY label
    all_keys = set(d_per_case.keys()) | set(r_per_case.keys()) | set(pd_per_case.keys())

    rows = []
    stats = defaultdict(int)
    for key in sorted(all_keys):
        ag, cid = key
        classes: list[str] = []
        d_cls = d_per_case.get(key)
        if d_cls:
            classes.append(d_cls)
        r_cls = r_per_case.get(key)
        if r_cls:
            classes.append(r_cls)
        for pd_cls in pd_per_case.get(key, []):
            classes.append(pd_cls)
        classes = sorted(set(classes))
        if not classes:
            continue
        exp_id = FRAMEWORKS[ag][0]
        dd = data_dirs.get(key, "")
        rows.append({
            "agent": ag,
            "exp_id": exp_id,
            "case_id": cid,
            "data_dir": dd,
            "classes_to_verify": classes,
        })
        stats["cases"] += 1
        stats["slots"] += len(classes)
        stats[f"agent:{ag}"] += 1

    out = MERGED / "verify_samples.jsonl"
    with out.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    print(f"Wrote {out}")
    print(f"Total cases: {stats['cases']}")
    print(f"Total class-slots: {stats['slots']}")
    for k, v in sorted(stats.items()):
        if k.startswith("agent:"):
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
