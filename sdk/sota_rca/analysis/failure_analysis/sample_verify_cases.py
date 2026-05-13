"""V-A sampling: stratified random sampling of D / R / PD cases for 3-way verification.

Reads D_projection.jsonl, PD_projection.jsonl, and DB meta.failure_analysis.v1.R.
Selects 5 cases per class (or all if class has <5). For framework-specific R / PD,
selects min(3, class_size). Collapses to distinct cases, so one case can satisfy
multiple class slots simultaneously.

Output: merged/verify_samples.jsonl — one row per distinct case, with classes_to_verify list.
Seeded for reproducibility.
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).parent))
from harp_config import (
    D_PROJECTION,
    FRAMEWORKS,
    MERGED,
    PD_PROJECTION,
)

SEED = 20260422
UNIFIED_R_CLASSES = {
    "U1_LoudnessAnchorOverSilentVictim",
    "U2_ChronicAmbientNoiseAnchor",
    "U3_EdgeDirectionOrRegionEndpointError",
    "U4_NameTwinSiblingConfusion",
    "U5_SilenceReadAsHealthOrPaused",
}
# D taxonomy: class phrase in projection -> short id
D_CLASS_MAP = {
    "D_victim_silent_on_path": "D1",
    "D_cross_layer_signal_gap": "D2",
    "D_ambient_noise_dominates": "D3",
    "D_edge_symmetric_ambiguity": "D4",
    "D_cascade_symptom_louder_than_GT": "D5",
    "D_name_twin_on_path": "D6",
    "D_diluted_multi_candidate": "D7",
    # D8 dataset_anomaly skipped per plan
}

EXP_TO_AGENT = {exp: key for key, (exp, *_rest) in FRAMEWORKS.items()}


def _pick(rng, lst, k):
    if len(lst) <= k:
        return list(lst)
    return rng.sample(list(lst), k=k)


def _load_db_r_labels():
    """exp_id -> {case_id (int): R_class}"""
    # Access pgsql via docker exec — but we can use psycopg directly since it's localhost
    conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5433/SOTA-Agents")
    out: dict[str, dict[int, str]] = defaultdict(dict)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT exp_id, dataset_index, meta->'failure_analysis'->'v1'->>'R' AS R_cls, meta->>'path' AS data_dir
            FROM evaluation_data
            WHERE meta->'failure_analysis'->'v1' IS NOT NULL
            """
        )
        rows = cur.fetchall()
    conn.close()
    data_dirs: dict[tuple[str, int], str] = {}
    for exp_id, case_id, r_cls, data_dir in rows:
        out[exp_id][int(case_id)] = r_cls or ""
        data_dirs[(exp_id, int(case_id))] = data_dir or ""
    return out, data_dirs


def main():
    rng = random.Random(SEED)

    # --- Load D labels ---
    d_by_class: dict[str, list[tuple[str, int]]] = defaultdict(list)  # D_phrase -> [(agent, case_id)]
    with D_PROJECTION.open() as f:
        for ln in f:
            row = json.loads(ln)
            d_cls = row["d_class"]
            if d_cls not in D_CLASS_MAP:
                continue  # skip D_dataset_anomaly
            d_by_class[d_cls].append((row["agent"], int(row["case_id"])))

    # --- Load R labels from DB ---
    r_db, data_dirs_by_exp = _load_db_r_labels()
    r_by_class: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for exp_id, case_map in r_db.items():
        agent_key = EXP_TO_AGENT[exp_id]
        for case_id, r_cls in case_map.items():
            if not r_cls:
                continue
            r_by_class[r_cls].append((agent_key, case_id))

    # --- Load PD labels ---
    pd_by_class: dict[str, list[tuple[str, int]]] = defaultdict(list)
    with PD_PROJECTION.open() as f:
        for ln in f:
            row = json.loads(ln)
            ag = row["agent"]
            cid = int(row["case_id"])
            for pd_cls in row.get("process_defects", []):
                pd_by_class[pd_cls].append((ag, cid))
            for pd_cls in row.get("framework_specific", []):
                pd_by_class[pd_cls].append((ag, cid))

    # --- Build sampling plan ---
    case_to_classes: dict[tuple[str, int], set[str]] = defaultdict(set)
    sampling_log: list[dict] = []

    # D: 5 per class (or all)
    for d_cls, members in d_by_class.items():
        short = D_CLASS_MAP[d_cls]
        chosen = _pick(rng, members, 5)
        sampling_log.append({"axis": "D", "class": short, "requested": 5, "available": len(members), "picked": len(chosen)})
        for (ag, cid) in chosen:
            case_to_classes[(ag, cid)].add(short)

    # R unified: 5 per class
    for r_cls in UNIFIED_R_CLASSES:
        members = r_by_class.get(r_cls, [])
        chosen = _pick(rng, members, 5)
        sampling_log.append({"axis": "R", "class": r_cls, "requested": 5, "available": len(members), "picked": len(chosen)})
        for (ag, cid) in chosen:
            case_to_classes[(ag, cid)].add(r_cls)

    # R framework-specific: min(3, size)
    for r_cls, members in r_by_class.items():
        if r_cls in UNIFIED_R_CLASSES:
            continue
        if not members:
            continue
        chosen = _pick(rng, members, 3)
        sampling_log.append({"axis": "R_fw", "class": r_cls, "requested": 3, "available": len(members), "picked": len(chosen)})
        for (ag, cid) in chosen:
            case_to_classes[(ag, cid)].add(r_cls)

    # PD unified: 5 per class
    unified_pd = {"PD_NoBaselineContrast", "PD_NoCallTreeBuild", "PD_NoFaultLayerMetricProbe",
                  "PD_NamedCandidateNotIsolated", "PD_ErrorOnlyFilterBias", "PD_SurveyWithoutDrill",
                  "PD_LateExplorationDegenerate", "PD_MultiRCCompromise", "PD_TraceFollowAbsent"}
    for pd_cls in unified_pd:
        members = pd_by_class.get(pd_cls, [])
        chosen = _pick(rng, members, 5)
        sampling_log.append({"axis": "PD", "class": pd_cls, "requested": 5, "available": len(members), "picked": len(chosen)})
        for (ag, cid) in chosen:
            case_to_classes[(ag, cid)].add(pd_cls)

    # PD framework-specific: min(3, size)
    for pd_cls, members in pd_by_class.items():
        if pd_cls in unified_pd:
            continue
        if not members:
            continue
        chosen = _pick(rng, members, 3)
        sampling_log.append({"axis": "PD_fw", "class": pd_cls, "requested": 3, "available": len(members), "picked": len(chosen)})
        for (ag, cid) in chosen:
            case_to_classes[(ag, cid)].add(pd_cls)

    # --- Write output ---
    out_path = MERGED / "verify_samples.jsonl"
    log_path = MERGED / "verify_samples.log.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Build rows — each distinct case gets a row
    rows_out = []
    for (agent, case_id), classes in sorted(case_to_classes.items()):
        exp_id = FRAMEWORKS[agent][0]
        data_dir = data_dirs_by_exp.get((exp_id, case_id), "")
        rows_out.append({
            "agent": agent,
            "exp_id": exp_id,
            "case_id": case_id,
            "data_dir": data_dir,
            "classes_to_verify": sorted(classes),
        })

    with out_path.open("w") as f:
        for r in rows_out:
            f.write(json.dumps(r) + "\n")

    total_slots = sum(len(r["classes_to_verify"]) for r in rows_out)
    summary = {
        "seed": SEED,
        "total_distinct_cases": len(rows_out),
        "total_class_slots": total_slots,
        "per_axis_log": sampling_log,
    }
    with log_path.open("w") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote {out_path} — {len(rows_out)} distinct cases, {total_slots} class-slots total")
    print(f"Sampling log: {log_path}")


if __name__ == "__main__":
    main()
