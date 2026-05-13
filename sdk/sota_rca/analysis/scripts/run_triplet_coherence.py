"""Entry script for triplet coherence analysis.

Usage:
    python scripts/analysis/run_triplet_coherence.py --db sqlite:///thinkdepthai_init.db
    python scripts/analysis/run_triplet_coherence.py --db sqlite:///thinkdepthai_init.db --sample_id 9
    python scripts/analysis/run_triplet_coherence.py --db sqlite:///test.db --exp_id claude45 --export results.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlmodel import Session, create_engine, select

from sota_rca.analysis.extractor import GTContext, extract_steps
from sota_rca.analysis.triplet_coherence import (
    CoherenceReport,
    analyze_coherence,
    format_aggregate_report,
    format_report,
)
from sota_rca.runner._fallback_db import EvaluationSample
from rcabench_platform.v3.sdk.evaluation.causal_graph import CausalGraph


def _load_gt_context(sample: EvaluationSample) -> GTContext:
    """Load ground truth context from sample's correct_answer.

    correct_answer can be:
    1. JSON string of CausalGraph
    2. Comma-separated service names (simple format)
    """
    answer = sample.correct_answer or ""

    # Try JSON first (CausalGraph format)
    if answer.strip().startswith("{"):
        try:
            data = json.loads(answer)
            graph = CausalGraph.from_dict(data)
            return GTContext.from_causal_graph(graph)
        except (json.JSONDecodeError, Exception):
            pass

    # Fall back to comma-separated service names
    services = {s.strip() for s in answer.split(",") if s.strip()}
    return GTContext(
        path_services=services,
        root_cause_services=services,  # Can't distinguish without graph
        alarm_services=set(),
        service_edges=set(),
    )


def main():
    parser = argparse.ArgumentParser(description="Triplet coherence analysis")
    parser.add_argument("--db", type=str, default="sqlite:///thinkdepthai_init.db", help="Database URL")
    parser.add_argument("--exp_id", type=str, default=None, help="Filter by experiment ID")
    parser.add_argument("--sample_id", type=int, default=None, help="Analyze single sample (show detail)")
    parser.add_argument("--export", type=str, default=None, help="Export JSON path")
    args = parser.parse_args()

    engine = create_engine(args.db)
    with Session(engine) as session:
        stmt = select(EvaluationSample).where(EvaluationSample.stage == "judged")
        if args.exp_id:
            stmt = stmt.where(EvaluationSample.exp_id == args.exp_id)
        if args.sample_id:
            stmt = stmt.where(EvaluationSample.id == args.sample_id)
        samples = list(session.exec(stmt).all())

    if not samples:
        print("No judged samples found. Check --db and --exp_id.")
        return

    print(f"Analyzing {len(samples)} samples...")

    reports: list[CoherenceReport] = []
    for sample in samples:
        if not sample.trajectories:
            continue
        steps = extract_steps(sample.trajectories)
        if not steps:
            continue

        gt = _load_gt_context(sample)
        report = analyze_coherence(
            sample_id=sample.id,
            correct=bool(sample.correct),
            steps=steps,
            gt=gt,
        )
        reports.append(report)

        # Print per-sample detail if single sample
        if args.sample_id:
            print(format_report(report))

    if not reports:
        print("No valid trajectories found for analysis.")
        return

    # Print aggregate report (unless single sample mode)
    if not args.sample_id:
        print(f"\nSuccessfully analyzed {len(reports)} samples.\n")
        print(format_aggregate_report(reports))

    # Export
    if args.export:
        export_data = {
            "total_samples": len(reports),
            "correct_samples": sum(1 for r in reports if r.correct),
            "samples": [
                {
                    "sample_id": r.sample_id,
                    "correct": r.correct,
                    "rates": {
                        "ta_service_match_rate": r.ta_service_match_rate,
                        "ta_datatype_match_rate": r.ta_datatype_match_rate,
                        "ar_effectiveness_rate": r.ar_effectiveness_rate,
                        "ar_gt_discovery_rate": r.ar_gt_discovery_rate,
                        "tt_advancing_rate": r.tt_advancing_rate,
                        "rt_utilization_rate": r.rt_utilization_rate,
                        "aa_on_path_rate": r.aa_on_path_rate,
                    },
                    "internal": [
                        {
                            "step": ic.step_index,
                            "ta_service_match": ic.ta_service_match,
                            "ta_datatype_match": ic.ta_datatype_match,
                            "ar_effectiveness": ic.ar_effectiveness,
                            "ar_gt_services_found": ic.ar_gt_services_found,
                        }
                        for ic in r.internal
                    ],
                    "external": [
                        {
                            "pair": list(ec.pair),
                            "tt_progression": ec.tt_progression,
                            "rt_utilization": ec.rt_utilization,
                            "aa_drift": ec.aa_drift,
                        }
                        for ec in r.external
                    ],
                }
                for r in reports
            ],
        }
        Path(args.export).write_text(json.dumps(export_data, ensure_ascii=False, indent=2))
        print(f"\nExported to: {args.export}")


if __name__ == "__main__":
    main()
