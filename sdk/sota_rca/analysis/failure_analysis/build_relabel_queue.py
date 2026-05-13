"""X-4: Build relabel_queue.v2.jsonl from verify_verdicts.v2.jsonl.

For each non-agree verdict, classify into one of:
  - remove_label: redundant / fabricated / mislabel-tax — the case should NOT carry this label
  - relabel_class: misaligned with explicit suggested_alternative_class — re-route
  - dispute_strong_audit: high-confidence labeler error needing removal (e.g. PD4 RC actually probed)
  - skip_human: dispute-weak (threshold fence) / unverifiable (need trajectory-text extractor)

Output: one row per non-agree verdict in JSONL with action + confidence.
"""
from __future__ import annotations
import json
import os
import sys
from collections import Counter
from pathlib import Path

VERDICTS = Path(os.environ.get("VERIFY_VERDICTS_PATH",
                               "analysis/3-failure-modes/merged/verify_verdicts.v2.jsonl"))
OUT = Path(os.environ.get("RELABEL_QUEUE_PATH",
                          "analysis/3-failure-modes/merged/relabel_queue.v2.jsonl"))


def classify(v: dict) -> dict | None:
    verdict = v.get("verdict")
    cls = v.get("class")
    reason = v.get("reason") or ""
    suggested = v.get("suggested_alternative_class") or ""

    if verdict == "agree":
        return None
    if verdict == "unverifiable":
        return None  # blocked on trajectory-text extractor (separate workstream)

    # Action policy:
    if verdict == "fabricated":
        return {"action": "remove_label", "confidence": "high",
                "reason_short": "fabricated D obstacle (agent never reached GT path)"}
    if verdict == "redundant":
        # PD label fires but counterfactual would be no-op → remove under v2 Detection∧Counterfactual gate
        return {"action": "remove_label", "confidence": "high",
                "reason_short": "v2 PD requires Detection∧Counterfactual; counterfactual fails"}
    if verdict == "misaligned":
        # has explicit suggested_alternative_class → mechanical relabel
        if suggested:
            return {"action": "relabel_class", "confidence": "high",
                    "new_class": suggested,
                    "reason_short": f"R-class implied capability mismatches GT requirement; reroute to {suggested}"}
        return {"action": "remove_label", "confidence": "medium",
                "reason_short": "misaligned without explicit suggested target"}
    if verdict == "dispute-strong":
        # Tight-regex dispute-strong → high confidence label is wrong
        # Examples:
        #  - PD4 RC actually in WHERE filters (regex hit)
        #  - PD2 call_tree_build substring fired
        #  - PD3 layer probed
        #  - PD5 has_unset_filter present
        #  - PD1 baseline_contrast substring fired
        #  - D5 GT is loudest
        #  - claudecode.PD4 GT in WHERE
        #  - D3 no chronic noise
        #  - U1 RC == GT (rare)
        #  - D4 fault not edge-level
        #  - D6 no name twin
        #  - aiq.R_hub_fabrication RC observed
        # All of these are tight regex / parquet hits → high confidence
        # NEW v2: D1 dispute-strong (gt_err > 5 or status=Error) — tight parquet hit
        # NEW v2: D5 dispute-strong (gt is loudest) — tight parquet
        return {"action": "remove_label", "confidence": "high",
                "reason_short": "tight-regex/parquet evidence contradicts label"}
    if verdict == "dispute-weak":
        # Threshold-sensitive — defer to human; do not relabel mechanically
        return {"action": "skip_human", "confidence": "low",
                "reason_short": "threshold-sensitive; needs human judgment"}
    return {"action": "skip_human", "confidence": "low",
            "reason_short": f"unhandled verdict: {verdict}"}


def main():
    counts = Counter()
    by_action = Counter()
    by_class_action = Counter()
    rows = []
    n_total = 0
    n_agree = 0
    with VERDICTS.open() as f:
        for line in f:
            v = json.loads(line)
            n_total += 1
            counts[v.get("verdict", "?")] += 1
            if v.get("verdict") == "agree":
                n_agree += 1
                continue
            entry = classify(v)
            if entry is None:
                continue
            row = {
                "agent": v["agent"],
                "case_id": v["case_id"],
                "axis": v.get("axis"),
                "class": v["class"],
                "v2_verdict": v.get("verdict"),
                "v2_reason": v.get("reason"),
                **entry,
            }
            rows.append(row)
            by_action[entry["action"]] += 1
            by_class_action[(v["class"], entry["action"])] += 1

    tmp = OUT.with_suffix(".tmp")
    with tmp.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
            f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, OUT)

    print(f"Verdict distribution (n_total={n_total}):")
    for k, v in counts.most_common():
        print(f"  {k}: {v} ({100*v/n_total:.1f}%)")
    print()
    print(f"agree={n_agree}; non-agree={n_total - n_agree}; queue rows={len(rows)}")
    print()
    print("Queue actions:")
    for k, v in by_action.most_common():
        print(f"  {k}: {v}")
    print()
    print("Top-12 (class, action) cells:")
    for (c, a), n in by_class_action.most_common(12):
        print(f"  {c} → {a}: {n}")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
