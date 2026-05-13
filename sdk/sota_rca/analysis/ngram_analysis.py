"""N-gram analysis of SQL query sequences.

Extracts data_type:intent token sequences from agent trajectories,
computes n-gram distributions, and analyzes correlation with RCA accuracy.
"""

from collections import Counter
from dataclasses import dataclass, field

from .extractor import ExtractedStep


@dataclass
class NgramResult:
    """N-gram analysis result for a single sample."""

    sample_id: int
    correct: bool
    token_sequence: list[str] = field(default_factory=list)
    ngrams: dict[int, list[tuple[str, ...]]] = field(default_factory=dict)


@dataclass
class NgramAccuracy:
    """Accuracy statistics for a single n-gram."""

    total: int = 0
    correct: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total > 0 else 0.0


@dataclass
class NgramReport:
    """Aggregated n-gram analysis report across samples."""

    # Basic stats
    vocabulary: dict[str, int] = field(default_factory=dict)
    sequence_lengths: list[int] = field(default_factory=list)
    total_samples: int = 0
    correct_samples: int = 0

    # N-gram frequencies
    ngram_counts: dict[int, dict[tuple[str, ...], int]] = field(default_factory=dict)

    # Accuracy correlation: n -> {ngram -> NgramAccuracy}
    ngram_accuracy: dict[int, dict[tuple[str, ...], NgramAccuracy]] = field(default_factory=dict)

    # Pattern discovery
    correct_only_ngrams: dict[int, list[tuple[str, ...]]] = field(default_factory=dict)
    incorrect_only_ngrams: dict[int, list[tuple[str, ...]]] = field(default_factory=dict)

    # First-step analysis
    first_token_accuracy: dict[str, NgramAccuracy] = field(default_factory=dict)

    # Transition matrix: (token_i, token_j) -> count
    transitions: dict[tuple[str, str], int] = field(default_factory=dict)


def _extract_ngrams(sequence: list[str], n: int) -> list[tuple[str, ...]]:
    """Extract n-grams from a token sequence."""
    if len(sequence) < n:
        return []
    return [tuple(sequence[i : i + n]) for i in range(len(sequence) - n + 1)]


def extract_token_sequence(steps: list[ExtractedStep]) -> list[str]:
    """Convert steps to a token sequence for n-gram analysis."""
    return [step.ngram_token for step in steps]


def analyze_single_sample(
    sample_id: int,
    correct: bool,
    steps: list[ExtractedStep],
    n_range: tuple[int, int] = (1, 4),
) -> NgramResult:
    """Analyze n-grams for a single sample."""
    tokens = extract_token_sequence(steps)
    ngrams: dict[int, list[tuple[str, ...]]] = {}
    for n in range(n_range[0], n_range[1]):
        ngrams[n] = _extract_ngrams(tokens, n)
    return NgramResult(sample_id=sample_id, correct=correct, token_sequence=tokens, ngrams=ngrams)


def analyze_ngrams(
    results: list[NgramResult],
    n_range: tuple[int, int] = (1, 4),
) -> NgramReport:
    """Aggregate n-gram analysis across all samples."""
    report = NgramReport(
        total_samples=len(results),
        correct_samples=sum(1 for r in results if r.correct),
    )

    # Vocabulary
    vocab_counter: Counter[str] = Counter()
    for r in results:
        vocab_counter.update(r.token_sequence)
        report.sequence_lengths.append(len(r.token_sequence))
    report.vocabulary = dict(vocab_counter.most_common())

    # N-gram counts and accuracy
    for n in range(n_range[0], n_range[1]):
        count_all: Counter[tuple[str, ...]] = Counter()
        correct_ngrams_set: set[tuple[str, ...]] = set()
        incorrect_ngrams_set: set[tuple[str, ...]] = set()

        accuracy_map: dict[tuple[str, ...], NgramAccuracy] = {}

        for r in results:
            sample_ngrams = r.ngrams.get(n, [])
            unique_ngrams = set(sample_ngrams)
            count_all.update(sample_ngrams)

            for ng in unique_ngrams:
                if ng not in accuracy_map:
                    accuracy_map[ng] = NgramAccuracy()
                accuracy_map[ng].total += 1
                if r.correct:
                    accuracy_map[ng].correct += 1

            if r.correct:
                correct_ngrams_set.update(unique_ngrams)
            else:
                incorrect_ngrams_set.update(unique_ngrams)

        report.ngram_counts[n] = dict(count_all.most_common())
        report.ngram_accuracy[n] = accuracy_map
        report.correct_only_ngrams[n] = sorted(correct_ngrams_set - incorrect_ngrams_set)
        report.incorrect_only_ngrams[n] = sorted(incorrect_ngrams_set - correct_ngrams_set)

    # First-token analysis
    for r in results:
        if r.token_sequence:
            first = r.token_sequence[0]
            if first not in report.first_token_accuracy:
                report.first_token_accuracy[first] = NgramAccuracy()
            report.first_token_accuracy[first].total += 1
            if r.correct:
                report.first_token_accuracy[first].correct += 1

    # Transition matrix
    transition_counter: Counter[tuple[str, str]] = Counter()
    for r in results:
        for i in range(len(r.token_sequence) - 1):
            transition_counter[(r.token_sequence[i], r.token_sequence[i + 1])] += 1
    report.transitions = dict(transition_counter.most_common())

    return report


def format_report(report: NgramReport) -> str:
    """Format report as human-readable text."""
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("N-GRAM ANALYSIS REPORT")
    lines.append("=" * 80)

    lines.append(f"\nSamples: {report.total_samples} (correct: {report.correct_samples})")
    avg_len = sum(report.sequence_lengths) / len(report.sequence_lengths) if report.sequence_lengths else 0
    lines.append(f"Average sequence length: {avg_len:.1f}")

    # Vocabulary
    lines.append(f"\n{'─' * 60}")
    lines.append("TOKEN VOCABULARY")
    lines.append(f"{'─' * 60}")
    for token, count in report.vocabulary.items():
        lines.append(f"  {token:<35} {count:>6}")

    # N-gram frequency and accuracy
    for n, counts in sorted(report.ngram_counts.items()):
        lines.append(f"\n{'─' * 60}")
        lines.append(f"{n}-GRAM FREQUENCY & ACCURACY (top 20)")
        lines.append(f"{'─' * 60}")
        lines.append(f"  {'n-gram':<50} {'count':>6}  {'acc':>6}")
        for ng, count in list(counts.items())[:20]:
            acc = report.ngram_accuracy[n][ng]
            ng_str = " → ".join(ng)
            lines.append(f"  {ng_str:<50} {count:>6}  {acc.accuracy:>5.1%}")

    # Correct-only / incorrect-only patterns
    for n in sorted(report.correct_only_ngrams.keys()):
        correct_only = report.correct_only_ngrams[n]
        incorrect_only = report.incorrect_only_ngrams[n]
        if correct_only or incorrect_only:
            lines.append(f"\n{'─' * 60}")
            lines.append(f"{n}-GRAM EXCLUSIVE PATTERNS")
            lines.append(f"{'─' * 60}")
            if correct_only:
                lines.append(f"  Correct-only ({len(correct_only)}):")
                for ng in correct_only[:10]:
                    lines.append(f"    ✅ {' → '.join(ng)}")
            if incorrect_only:
                lines.append(f"  Incorrect-only ({len(incorrect_only)}):")
                for ng in incorrect_only[:10]:
                    lines.append(f"    ❌ {' → '.join(ng)}")

    # First-token analysis
    lines.append(f"\n{'─' * 60}")
    lines.append("FIRST-TOKEN EFFECT")
    lines.append(f"{'─' * 60}")
    for token, acc in sorted(report.first_token_accuracy.items(), key=lambda x: -x[1].total):
        lines.append(f"  {token:<35} n={acc.total:<4}  acc={acc.accuracy:.1%}")

    # Transition matrix (top transitions)
    lines.append(f"\n{'─' * 60}")
    lines.append("TOP TRANSITIONS (token_i → token_j)")
    lines.append(f"{'─' * 60}")
    for (src, tgt), count in list(report.transitions.items())[:15]:
        lines.append(f"  {src:<30} → {tgt:<30} {count:>4}")

    return "\n".join(lines)
