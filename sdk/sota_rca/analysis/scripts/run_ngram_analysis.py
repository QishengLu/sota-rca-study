"""Entry script for N-gram analysis of SQL query sequences.

Usage:
    python scripts/analysis/run_ngram_analysis.py --db sqlite:///thinkdepthai_init.db
    python scripts/analysis/run_ngram_analysis.py --db sqlite:///thinkdepthai_init.db --export results.json
    python scripts/analysis/run_ngram_analysis.py --db sqlite:///test.db --exp_id claude45
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlmodel import Session, create_engine, select

from sota_rca.analysis.extractor import extract_steps
from sota_rca.analysis.ngram_analysis import (
    NgramResult,
    analyze_ngrams,
    analyze_single_sample,
    format_report,
)
from sota_rca.runner._fallback_db import EvaluationSample


def main():
    parser = argparse.ArgumentParser(description="N-gram analysis of SQL query sequences")
    parser.add_argument("--db", type=str, default="sqlite:///thinkdepthai_init.db", help="Database URL")
    parser.add_argument("--exp_id", type=str, default=None, help="Filter by experiment ID")
    parser.add_argument("--sample_id", type=int, default=None, help="Analyze single sample")
    parser.add_argument("--n_range", type=str, default="1,4", help="N-gram range (e.g., '1,4' for 1-gram to 3-gram)")
    parser.add_argument("--export", type=str, default=None, help="Export JSON path")
    args = parser.parse_args()

    n_min, n_max = map(int, args.n_range.split(","))
    n_range = (n_min, n_max)

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

    # Extract and analyze
    results: list[NgramResult] = []
    for sample in samples:
        if not sample.trajectories:
            continue
        steps = extract_steps(sample.trajectories)
        if not steps:
            continue
        result = analyze_single_sample(
            sample_id=sample.id,
            correct=bool(sample.correct),
            steps=steps,
            n_range=n_range,
        )
        results.append(result)

    if not results:
        print("No valid trajectories found for analysis.")
        return

    print(f"Successfully extracted {len(results)} token sequences.\n")

    # Aggregate report
    report = analyze_ngrams(results, n_range=n_range)
    print(format_report(report))

    # Export
    if args.export:
        export_data = {
            "total_samples": report.total_samples,
            "correct_samples": report.correct_samples,
            "vocabulary": report.vocabulary,
            "sequence_lengths": report.sequence_lengths,
            "ngram_counts": {
                str(n): {" → ".join(ng): count for ng, count in counts.items()}
                for n, counts in report.ngram_counts.items()
            },
            "ngram_accuracy": {
                str(n): {
                    " → ".join(ng): {"total": acc.total, "correct": acc.correct, "accuracy": acc.accuracy}
                    for ng, acc in accs.items()
                }
                for n, accs in report.ngram_accuracy.items()
            },
            "first_token_accuracy": {
                token: {"total": acc.total, "correct": acc.correct, "accuracy": acc.accuracy}
                for token, acc in report.first_token_accuracy.items()
            },
            "transitions": {f"{src} → {tgt}": count for (src, tgt), count in report.transitions.items()},
            "per_sample": [
                {"sample_id": r.sample_id, "correct": r.correct, "sequence": r.token_sequence} for r in results
            ],
        }
        Path(args.export).write_text(json.dumps(export_data, ensure_ascii=False, indent=2))
        print(f"\nExported to: {args.export}")


if __name__ == "__main__":
    main()
