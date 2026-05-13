"""X-6.3: Final V-C v4 — re-adjudicate against post-relabel projections + DB.

For each case (372 total):
  Build new classes_to_verify from:
    - D_projection.v3.jsonl  → D shorthand (D1..D7) or skip if d_class is null
    - PD_projection.v3.jsonl → process_defects + framework_specific
    - DB query                → meta.failure_analysis.v1.R (post-relabel)
  Load corresponding YAML evidence (unchanged).
  Run judge_d / judge_r / judge_pd against new classes_to_verify.

Output: verify_verdicts.v4.jsonl, verify_mismatch_report.final.md
"""
from __future__ import annotations
import json
import os
import sys
import subprocess
from pathlib import Path
import yaml

ROOT = Path("analysis/3-failure-modes/merged")
EVIDENCE_DIR = ROOT / "verify_evidence"
D_V3 = ROOT / "D_projection.v3.jsonl"
PD_V3 = ROOT / "PD_projection.v3.jsonl"
V4_VERDICTS = ROOT / "verify_verdicts.v4.jsonl"

D_LONG_TO_SHORT = {
    "D_victim_silent_on_path": "D1",
    "D_cross_layer_signal_gap": "D2",
    "D_ambient_noise_dominates": "D3",
    "D_edge_symmetric_ambiguity": "D4",
    "D_cascade_symptom_louder_than_GT": "D5",
    "D_name_twin_on_path": "D6",
    "D_diluted_multi_candidate": "D7",
    "D_dataset_anomaly": "D8",
}
AGENT_EXP_MAP = {
    "aiq": "aiq-qwen3.5-plus",
    "claudecode": "claudecode-qwen3.5-plus",
    "sonnet": "thinkdepthai-claude-sonnet-4.6",
    "qwen": "thinkdepthai-qwen3.5-plus",
}

sys.path.insert(0, str(Path(__file__).parent))
import importlib.util
_spec = importlib.util.spec_from_file_location("verify_adjudicate", str(Path(__file__).parent / "verify_adjudicate.py"))
adj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adj)


def load_d_projection() -> dict[tuple, dict]:
    out = {}
    with D_V3.open() as f:
        for line in f:
            r = json.loads(line)
            out[(r["agent"], r["case_id"])] = r
    return out


def load_pd_projection() -> dict[tuple, dict]:
    out = {}
    with PD_V3.open() as f:
        for line in f:
            r = json.loads(line)
            out[(r["agent"], r["case_id"])] = r
    return out


def fetch_db_r() -> dict[tuple, str]:
    """Bulk fetch current R label from DB for all 372 cases."""
    sql = (
        "SELECT exp_id, dataset_index, meta::jsonb -> 'failure_analysis' -> 'v1' ->> 'R' as r "
        "FROM evaluation_data "
        "WHERE exp_id IN ('aiq-qwen3.5-plus','claudecode-qwen3.5-plus','thinkdepthai-claude-sonnet-4.6','thinkdepthai-qwen3.5-plus') "
        "AND meta::jsonb -> 'failure_analysis' -> 'v1' IS NOT NULL"
    )
    proc = subprocess.run(
        ["docker", "exec", "-i", "sota-agents-postgres",
         "psql", "-U", "postgres", "-d", "SOTA-Agents",
         "-A", "-t", "-F", "|", "-c", sql],
        capture_output=True, text=True, check=True,
    )
    exp_to_agent = {v: k for k, v in AGENT_EXP_MAP.items()}
    out = {}
    for line in proc.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue
        exp_id, ds_idx, r_label = parts[0], parts[1], parts[2] if len(parts) > 2 else ""
        agent = exp_to_agent.get(exp_id)
        if not agent:
            continue
        try:
            cid = int(ds_idx)
        except (ValueError, TypeError):
            continue
        if r_label and r_label not in ("", "null"):
            out[(agent, cid)] = r_label
    return out


def build_classes_to_verify(agent: str, cid: int, d_proj, pd_proj, r_map) -> list[str]:
    classes = []
    drow = d_proj.get((agent, cid))
    if drow:
        d_long = drow.get("d_class")
        if d_long:
            d_short = D_LONG_TO_SHORT.get(d_long)
            if d_short and d_short != "D8":  # D8 is parking lot
                classes.append(d_short)
    pdrow = pd_proj.get((agent, cid))
    if pdrow:
        for c in (pdrow.get("process_defects") or []):
            classes.append(c)
        for c in (pdrow.get("framework_specific") or []):
            classes.append(c)
    r_label = r_map.get((agent, cid))
    if r_label and r_label != "null":
        classes.append(r_label)
    return classes


def judge(cls: str, doc: dict) -> dict:
    axis = adj.classify_axis(cls)
    if axis == "D":
        return adj.judge_d(cls, doc)
    if axis == "R":
        return adj.judge_r(cls, doc)
    if axis == "PD":
        return adj.judge_pd(cls, doc)
    return {"verdict": "unverifiable", "reason": f"unknown axis: {cls}"}


def write_jsonl_atomic(path: Path, rows: list[dict]):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
            f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def main():
    d_proj = load_d_projection()
    pd_proj = load_pd_projection()
    r_map = fetch_db_r()
    print(f"D projection: {len(d_proj)}; PD projection: {len(pd_proj)}; DB R: {len(r_map)}")

    rows = []
    n_yaml_missing = 0
    n_classes = 0
    for yaml_path in sorted(EVIDENCE_DIR.glob("*.yaml")):
        with yaml_path.open() as f:
            doc = yaml.safe_load(f)
        case_id_str = doc.get("case_id", "")
        if "." not in case_id_str:
            continue
        agent = case_id_str.split(".")[0]
        try:
            cid = int(case_id_str.split(".", 1)[1])
        except ValueError:
            continue
        classes_v4 = build_classes_to_verify(agent, cid, d_proj, pd_proj, r_map)
        if not classes_v4:
            continue
        if doc.get("unverifiable"):
            for cls in classes_v4:
                rows.append({"agent": agent, "case_id": cid, "class": cls, "axis": adj.classify_axis(cls),
                             "verdict": "unverifiable",
                             "positive_criteria_check": "n/a", "gt_required_capability_check": "n/a",
                             "path_alignment_check": "n/a", "counterfactual_check": "n/a",
                             "reason": doc.get("reason", "unverifiable YAML")})
                n_classes += 1
            continue
        for cls in classes_v4:
            v = judge(cls, doc)
            row = {"agent": agent, "case_id": cid, "class": cls,
                   "axis": adj.classify_axis(cls), **v}
            rows.append(row)
            n_classes += 1

    write_jsonl_atomic(V4_VERDICTS, rows)

    from collections import Counter
    counts = Counter(r["verdict"] for r in rows)
    n_total = len(rows)
    n_agree = counts.get("agree", 0)
    print(f"v4 pool: {n_total}; agree: {n_agree} ({100*n_agree/max(n_total,1):.1f}%)")
    for k, v in counts.most_common():
        print(f"  {k}: {v} ({100*v/n_total:.1f}%)")
    print(f"Wrote {V4_VERDICTS}")


if __name__ == "__main__":
    main()
