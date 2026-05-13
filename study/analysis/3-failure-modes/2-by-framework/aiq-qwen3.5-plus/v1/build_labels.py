#!/usr/bin/env python
"""Build labels.jsonl from per_case_analysis.md + evidence.json.

Applies the primary-selection priority defined in taxonomy.md v1.
"""
import json
import re
from pathlib import Path

V1_DIR = Path("/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/v1")

# Phrase -> primary theme mapping (raw mapping before priority reconciliation)
PHRASE_TO_THEME = {
    # T1
    "stopped at loudest upstream error volume": "T1_ErrorVolumeAnchor",
    "largest error delta taken as cause": "T1_ErrorVolumeAnchor",
    # T2
    "stopped one hop short upstream": "T2_StoppedOneHopShortUpstream",
    # T3
    "anchored on pre-existing RabbitMQ noise": "T3_BaselineNoiseAnchored",
    "pod mem stress mistaken for RabbitMQ": "T3_BaselineNoiseAnchored",
    "pod kill mistaken for broker failure": "T3_BaselineNoiseAnchored",
    "reflection escalated to hallucinated broker": "T3_BaselineNoiseAnchored",
    "latency fault mistaken for broker failure": "T3_BaselineNoiseAnchored",
    "reflection escalated to baseline noise": "T3_BaselineNoiseAnchored",
    # T4
    "latency fault missed by error-count search": "T4_SilentSignalMissed",
    "cpu stress missed by error-count search": "T4_SilentSignalMissed",
    "missing-span signal ignored": "T4_SilentSignalMissed",
    # T5
    "reflection reversed correct conclusion": "T5_ReflectionReversesCorrect",
    "reflection moved away from correct signal": "T5_ReflectionReversesCorrect",
    "reflection oscillates between neighbors": "T5_ReflectionReversesCorrect",
    # T6
    "hub hallucinated over no-error-signal": "T6_HallucinatedHub",
    "hub hallucinated for shared latency": "T6_HallucinatedHub",
    "hub hallucinated over strong signal": "T6_HallucinatedHub",
    # T7
    "confused similarly-named service": "T7_SimilarlyNamedServiceConfusion",
    # T8
    "compress overwrote correct refine hypothesis": "T8_CompressOverwritesTerminator",
    "compress overwrote correct stage0 hypothesis": "T8_CompressOverwritesTerminator",
    "compress overwrote correct terminator hypothesis": "T8_CompressOverwritesTerminator",
}


def extract_pivot_round(block_text: str) -> int | None:
    m = re.search(r"[Pp]ivot round[^:]*:\s*~?(\d+)", block_text)
    if m:
        return int(m.group(1))
    m = re.search(r"[Ss]tage at pivot[^\n]*stage_(\d+)", block_text)
    # fallback None
    return None


def parse_per_case_md() -> dict[int, dict]:
    p = V1_DIR / "per_case_analysis.md"
    text = p.read_text()
    cases = {}
    blocks = re.split(r"\n(?=## case_\d)", text)
    for blk in blocks:
        m = re.match(r"## case_(\d+)", blk)
        if not m:
            continue
        idx = int(m.group(1))
        phrase_m = re.search(r"[Pp]roximate cause[^`]*`([^`]+)`", blk)
        phrase = phrase_m.group(1).strip() if phrase_m else None
        pivot = extract_pivot_round(blk)
        # find overlay line
        overlay_m = re.search(r"Overlay:\s*([^\n]+)", blk)
        overlay = overlay_m.group(1).strip() if overlay_m else ""
        # attempt to find evidence text: first round cited, or short quote
        cases[idx] = {
            "idx": idx,
            "phrase": phrase,
            "pivot_round": pivot,
            "overlay": overlay,
            "block": blk,
        }
    return cases


def load_evidence_json() -> dict[int, dict]:
    p = V1_DIR / "evidence.json"
    rows = json.loads(p.read_text())
    return {r["dataset_index"]: r for r in rows}


def choose_primary(phrase: str, evidence: dict, overlay: str) -> tuple[str, list[str]]:
    """Apply the priority defined in taxonomy.md to pick primary; return (primary, secondary_list)."""
    base = PHRASE_TO_THEME.get(phrase)
    if not base:
        return ("unclassified", [])

    secondary: list[str] = []

    # Detect overlay hints to catch co-occurrences
    # overlay is free-form text like "A3", "A1+A4", "A7", "A2+A6", etc.
    overlay_hints = re.findall(r"\bA(\d)\b", overlay)
    # Map A# letters to themes (from working taxonomy draft — informs secondary)
    A_TO_THEME = {
        "1": "T1_ErrorVolumeAnchor",
        "2": "T3_BaselineNoiseAnchored",
        "3": "T5_ReflectionReversesCorrect",
        "4": "T4_SilentSignalMissed",
        "5": "T2_StoppedOneHopShortUpstream",
        "6": "T6_HallucinatedHub",
        "7": "T8_CompressOverwritesTerminator",
        "8": "T3_BaselineNoiseAnchored",  # A8 was escalation, maps to T3
        "9": "T7_SimilarlyNamedServiceConfusion",
    }
    for letter in overlay_hints:
        t = A_TO_THEME.get(letter)
        if t and t != base and t not in secondary:
            secondary.append(t)

    # Apply priority: T8 > T5 > T3 > T6 > T7 > T2 > T4 > T1
    # If base is T1 but overlay has T3/T6/T7/T2, pick higher-priority from overlay hints
    priority_order = [
        "T8_CompressOverwritesTerminator",
        "T5_ReflectionReversesCorrect",
        "T3_BaselineNoiseAnchored",
        "T6_HallucinatedHub",
        "T7_SimilarlyNamedServiceConfusion",
        "T2_StoppedOneHopShortUpstream",
        "T4_SilentSignalMissed",
        "T1_ErrorVolumeAnchor",
    ]

    candidates = [base] + secondary
    primary = min(candidates, key=lambda x: priority_order.index(x) if x in priority_order else 99)
    # remaining become secondary (deduped)
    rest = [c for c in candidates if c != primary]
    return (primary, rest)


def build_labels():
    cases = parse_per_case_md()
    evidence = load_evidence_json()

    labels = []
    theme_counts = {}
    for idx in sorted(cases):
        c = cases[idx]
        ev = evidence.get(idx, {})
        phrase = c["phrase"]
        primary, secondary = choose_primary(phrase, ev, c["overlay"])
        theme_counts[primary] = theme_counts.get(primary, 0) + 1

        # Evidence short quote = first stage terminator hypothesis
        term_hyps = ev.get("terminator_hypotheses") or []
        evidence_str = f"terminators={term_hyps}  log_top_pos={ev.get('log_signal', {}).get('top_pos_err_delta')}"[:400]

        labels.append({
            "dataset_index": idx,
            "primary": primary,
            "secondary": secondary,
            "proximate_cause": phrase,
            "pivot_round": c["pivot_round"],
            "evidence": evidence_str,
            "labeler": "claude-opus-4.7-human-readthrough",
        })

    # Write
    out_path = V1_DIR / "labels.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for lbl in labels:
            f.write(json.dumps(lbl, ensure_ascii=False) + "\n")

    # Summary
    print(f"Wrote {len(labels)} labels to {out_path}")
    print("\nTheme distribution (primary):")
    for theme, n in sorted(theme_counts.items(), key=lambda x: -x[1]):
        pct = n / len(labels) * 100
        print(f"  {theme}: {n} ({pct:.1f}%)")


if __name__ == "__main__":
    build_labels()
