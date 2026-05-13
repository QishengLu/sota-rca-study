#!/usr/bin/env python
"""Compact per-case evidence extractor for fast batch analysis.

For each failed case, produces a structured one-page summary containing the
signals I need to write a proximate-cause phrase without reading the full
5000-line dossier.

Output: v1/evidence.md (all 113 cases, sortable by fault_category).
"""
import argparse
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

import pandas as pd
from sqlmodel import Session, create_engine, select

sys.path.insert(0, "/home/nn/SOTA-agents/RCAgentEval")
from utu.db import EvaluationSample  # noqa: E402

sys.path.insert(0, "/home/nn/SOTA-agents/RCAgentEval/scripts/failure_analysis")
import build_dossiers as tdt  # noqa: E402

sys.path.insert(0, "/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus")
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location(
    "aiq_builder",
    "/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/build_dossier.py",
)
aiq_builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aiq_builder)


def compact_log_delta_signal(src_dir: Path, gt_services: list[str]) -> dict:
    """Which services have notable log error deltas; was GT in the signal?"""
    if not src_dir:
        return {}
    ld = tdt.log_delta_per_service(src_dir)
    if not ld:
        return {}
    err = ld.get("error_delta") or []
    # top positive (new errors during abnormal)
    top_pos = [e for e in err if e["delta"] > 0][:5]
    top_neg = sorted([e for e in err if e["delta"] < 0], key=lambda e: e["delta"])[:5]

    gt_set = {s.lower() for s in gt_services}
    gt_in_pos = [e for e in top_pos if any(gt in e["service"].lower() for gt in gt_set)]
    gt_in_neg = [e for e in top_neg if any(gt in e["service"].lower() for gt in gt_set)]

    return {
        "top_pos_err_delta": [(e["service"], e["delta"]) for e in top_pos],
        "top_neg_err_delta": [(e["service"], e["delta"]) for e in top_neg],
        "gt_in_top_pos": bool(gt_in_pos),
        "gt_in_top_neg": bool(gt_in_neg),
        "gt_error_delta_rows": [(e["service"], e["normal_errors"], e["abnormal_errors"], e["delta"])
                                 for e in err if any(gt in e["service"].lower() for gt in gt_set)],
    }


def gt_metric_anomaly_signal(src_dir: Path, gt_services: list[str]) -> dict:
    """Are there z-score anomalies on GT services' metrics? How strong?"""
    if not src_dir:
        return {}
    zm = tdt.zscore_anomalous_metrics(src_dir, z_threshold=3.0, top_k=60)
    gt_set = {s.lower() for s in gt_services}
    gt_metrics = [m for m in zm if m.get("service") and any(gt in m["service"].lower() for gt in gt_set)]
    return {
        "num_gt_metric_anomalies": len(gt_metrics),
        "top_gt_metrics": [(m["service"], m["metric"], m.get("z"))
                           for m in gt_metrics[:8]],
        "total_z_anomalies": len(zm),
    }


def extract_pod_restarts(src_dir: Path) -> list[tuple[str, int]]:
    """Pod restart counts — strong signal for JVMChaos/PodChaos."""
    if not src_dir:
        return []
    k8s_path = src_dir.parent / "k8s.json" if src_dir else None
    if not k8s_path or not k8s_path.exists():
        return []
    try:
        k8s = json.loads(k8s_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    items = k8s if isinstance(k8s, list) else (k8s.get("items") or [])
    for item in items:
        if not isinstance(item, dict):
            continue
        status = item.get("status") or {}
        cs_list = status.get("containerStatuses") or []
        for cs in cs_list:
            if isinstance(cs, dict) and cs.get("restartCount", 0) > 0:
                out.append((item.get("metadata", {}).get("name", "?"), cs["restartCount"]))
    return sorted(out, key=lambda x: -x[1])[:10]


def analyze_case(sample: EvaluationSample) -> dict:
    meta = sample.meta or {}
    diff = meta.get("difficulty") or {}
    gt_svcs = meta.get("ground_truth") or []
    gm = (meta.get("graph_metrics") or {}).get("diagnostic", {}) or {}
    cge = meta.get("causal_graph_evaluation") or {}
    src_dir = tdt.find_source_dir(meta)
    inj = tdt.load_injection_full(src_dir) if src_dir else {}
    cg = tdt.load_causal_graph_full(src_dir) if src_dir else {}

    # trajectory pipeline summary
    rounds, terminators, summary = aiq_builder.parse_aiq_trajectory(sample.trajectories)

    # Hypothesis at each terminator
    term_hyps = []
    for t in terminators:
        hyp = aiq_builder.extract_hypothesis(t.content)
        term_hyps.append((t.stage_closed, hyp, t.char_count))

    predicted_rcs = cge.get("root_cause_services") or []

    # Compare predicted vs GT
    gt_norm = {s.lower().replace("_", "-").replace("ts-", "") for s in gt_svcs}
    pred_norm = {s.lower().replace("_", "-").replace("ts-", "") for s in predicted_rcs}
    matched = pred_norm & gt_norm
    is_hallucination = len(matched) == 0

    # Propagation path membership check: is predicted on the GT propagation path?
    svc_edges = cg.get("service_edges") or []
    propagation_nodes = set()
    for src, tgt in svc_edges:
        propagation_nodes.add(src.lower().replace("_", "-"))
        propagation_nodes.add(tgt.lower().replace("_", "-"))
    propagation_simple = {n.replace("ts-", "") for n in propagation_nodes}
    pred_on_path = bool(pred_norm & propagation_simple)

    # Signal summaries
    log_sig = compact_log_delta_signal(src_dir, gt_svcs)
    metric_sig = gt_metric_anomaly_signal(src_dir, gt_svcs)
    restarts = extract_pod_restarts(src_dir)

    return {
        "dataset_index": sample.dataset_index,
        "fault_category": diff.get("fault_category"),
        "fault_type": diff.get("fault_type"),
        "spl": diff.get("spl"),
        "n_svc": diff.get("n_svc"),
        "gt_services": gt_svcs,
        "gt_functions": inj.get("gt_functions"),
        "gt_metrics_dim": inj.get("gt_metrics"),
        "predicted_rcs": predicted_rcs,
        "is_hallucination": is_hallucination,
        "pred_on_propagation_path": pred_on_path,
        "matched_services": gm.get("matched_services") or [],
        "missed_services": gm.get("missed_services") or [],
        "hallucinated_services": gm.get("hallucinated_services") or [],
        "final_status": summary.get("final_stage_status"),
        "terminator_count": summary.get("terminator_count"),
        "truncated_stages": summary.get("truncated_stages") or [],
        "terminator_hypotheses": term_hyps,
        "hypothesis_changed_at_refine": len({h for _, h, _ in term_hyps if h}) > 1,
        "log_signal": log_sig,
        "metric_signal": metric_sig,
        "pod_restarts": restarts,
    }


def render_line(r: dict) -> str:
    idx = r["dataset_index"]
    fc = r["fault_category"]
    ft = r["fault_type"]
    gt = r["gt_services"]
    gt_func = r.get("gt_functions") or []
    pred = r["predicted_rcs"]
    L = []
    L.append(f"### case_{idx}  [{fc}/{ft}]  spl={r['spl']} n_svc={r['n_svc']}")
    L.append(f"- gt: {gt}" + (f"  gt_fn: {gt_func}" if gt_func else ""))
    L.append(f"- pred: {pred}  on_propagation_path={r['pred_on_propagation_path']}  hallucination={r['is_hallucination']}")
    L.append(f"- diagnostic: matched={r['matched_services']} missed={r['missed_services']} hallucinated={r['hallucinated_services']}")
    L.append(f"- terminators ({r['terminator_count']}/3 {r['final_status']}): {r['terminator_hypotheses']}  changed_across_stages={r['hypothesis_changed_at_refine']}")
    if r["truncated_stages"]:
        L.append(f"- truncated: {r['truncated_stages']}")
    ls = r["log_signal"]
    if ls:
        L.append(f"- log err_delta top+: {ls.get('top_pos_err_delta')}")
        L.append(f"- log err_delta top-: {ls.get('top_neg_err_delta')}")
        L.append(f"- gt log_err_rows: {ls.get('gt_error_delta_rows')}")
    ms = r["metric_signal"]
    if ms:
        L.append(f"- gt metric anomalies ({ms.get('num_gt_metric_anomalies')}/{ms.get('total_z_anomalies')} total): {ms.get('top_gt_metrics')[:3]}")
    if r["pod_restarts"]:
        L.append(f"- pod_restarts: {r['pod_restarts'][:5]}")
    L.append("")
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="postgresql://postgres:postgres@localhost:5433/SOTA-Agents")
    p.add_argument("--exp_id", default="aiq-qwen3.5-plus")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    engine = create_engine(args.db)
    with Session(engine) as s:
        stmt = select(EvaluationSample).where(
            EvaluationSample.exp_id == args.exp_id,
            EvaluationSample.correct == False,  # noqa: E712
            EvaluationSample.stage == "judged",
        )
        samples = list(s.exec(stmt).all())
    samples.sort(key=lambda s: s.dataset_index or 0)

    print(f"Processing {len(samples)} cases...", file=sys.stderr)
    rows = []
    for s in samples:
        r = analyze_case(s)
        rows.append(r)
        print(f"  case_{r['dataset_index']} {r['fault_category']}/{r['fault_type']} pred={r['predicted_rcs']} on_path={r['pred_on_propagation_path']}", file=sys.stderr)

    # Group by fault_category
    by_fc = defaultdict(list)
    for r in rows:
        by_fc[r["fault_category"]].append(r)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write(f"# Case evidence — aiq-qwen3.5-plus (113 failed cases)\n\n")
        for fc in sorted(by_fc):
            cases = by_fc[fc]
            f.write(f"\n## {fc} ({len(cases)} cases)\n\n")
            for r in cases:
                f.write(render_line(r))
                f.write("\n")

    # Also dump JSON for later taxonomy automation
    json_path = out_path.with_suffix(".json")
    # Convert non-serializable items
    def safe(r):
        return {k: (list(v) if isinstance(v, set) else v) for k, v in r.items()}
    with json_path.open("w", encoding="utf-8") as f:
        json.dump([safe(r) for r in rows], f, indent=2, default=str, ensure_ascii=False)

    print(f"\nWrote: {out_path}\nJSON: {json_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
