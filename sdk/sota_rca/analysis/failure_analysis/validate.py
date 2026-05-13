#!/usr/bin/env python
"""Phase 5 — Validation for failure-mode labels.

Four checks:
  1. Spot check (interactive): sample N cases, print dossier + per-case analysis,
     prompt user for Correct / Wrong / Ambiguous.
  2. Exhaustiveness: fraction of `primary == 'unclassified'` vs total.
  3. Orthogonality (χ²): independence test between label group
     (data-side vs reasoning-side) and `fault_category`.
  4. Cross-framework sanity summary: if labels exist for other exp_ids,
     report per-exp unclassified fraction.

Sub-commands:
    spot-check  → interactive reviewer
    stats       → exhaustiveness + orthogonality + cross-framework summary

Usage:
    uv run python scripts/failure_analysis/validate.py spot-check \\
        --db $UTU_DB_URL \\
        --exp_id thinkdepthai-qwen3.5-plus \\
        --dossier_dir .../v2/dossiers \\
        --analysis .../v2/per_case_analysis.md \\
        --n 20

    uv run python scripts/failure_analysis/validate.py stats \\
        --db $UTU_DB_URL \\
        --exp_id thinkdepthai-qwen3.5-plus \\
        --theme_category .../v2/theme_category.json \\
        --out .../v2/validation.md
"""

import argparse
import json
import logging
import random
import re
import sys
from collections import Counter
from pathlib import Path

from sqlmodel import Session, create_engine, select

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402

try:
    from scipy.stats import chi2_contingency
except ImportError:  # noqa: BLE001
    chi2_contingency = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

VERSION_KEY = "v1"


def get_engine(db_url: str):
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(db_url, connect_args=connect_args)


def load_labeled_samples(engine, exp_id: str) -> list[dict]:
    out: list[dict] = []
    with Session(engine) as session:
        stmt = select(EvaluationSample).where(
            EvaluationSample.exp_id == exp_id,
            EvaluationSample.stage == "judged",
        )
        for s in session.exec(stmt).all():
            meta = s.meta or {}
            fa = (meta.get("failure_analysis") or {}).get(VERSION_KEY)
            if not fa:
                continue
            out.append(
                {
                    "dataset_index": s.dataset_index,
                    "primary": fa.get("primary"),
                    "secondary": fa.get("secondary") or [],
                    "pivot_round": fa.get("pivot_round"),
                    "evidence": fa.get("evidence"),
                    "fault_category": (meta.get("difficulty") or {}).get("fault_category", "?"),
                    "fault_type": (meta.get("difficulty") or {}).get("fault_type", "?"),
                    "correct": s.correct,
                }
            )
    return out


# ── Spot check (interactive) ────────────────────────────────────────────────


ANALYSIS_BLOCK_RE = re.compile(
    r"^## case_(\d+)\b(.*?)(?=^## case_\d+|\Z)", re.MULTILINE | re.DOTALL
)


def load_per_case_analysis_blocks(analysis_md: Path) -> dict[int, str]:
    if not analysis_md.exists():
        return {}
    text = analysis_md.read_text(encoding="utf-8")
    blocks: dict[int, str] = {}
    for m in ANALYSIS_BLOCK_RE.finditer(text):
        idx = int(m.group(1))
        body = f"## case_{idx}{m.group(2)}"
        blocks[idx] = body.strip()
    return blocks


def run_spot_check(args) -> None:
    engine = get_engine(args.db)
    samples = load_labeled_samples(engine, args.exp_id)
    if not samples:
        logger.error("no labeled samples found for exp_id=%s", args.exp_id)
        return
    rng = random.Random(args.seed)
    rng.shuffle(samples)
    picked = samples[: args.n]

    blocks = load_per_case_analysis_blocks(Path(args.analysis)) if args.analysis else {}
    dossier_dir = Path(args.dossier_dir)
    results: list[dict] = []

    print(f"Spot-check {len(picked)} cases. Mark each: (c)orrect / (w)rong / (a)mbiguous / (s)kip / (q)uit\n")
    for i, s in enumerate(picked, 1):
        idx = s["dataset_index"]
        print(f"\n{'=' * 70}")
        print(f"[{i}/{len(picked)}] case_{idx}  fault={s['fault_category']}/{s['fault_type']}")
        print(f"primary: {s['primary']}")
        print(f"secondary: {s['secondary']}")
        print(f"pivot_round: {s['pivot_round']}")
        print(f"evidence: {s['evidence']}")
        print(f"dossier: {dossier_dir}/case_{idx}.md")
        block = blocks.get(idx)
        if block:
            print("\n--- analyst block ---")
            print(block[:2000])
            print("---")
        else:
            print("\n(no per-case analysis block found for this case)")

        verdict = ""
        while verdict not in {"c", "w", "a", "s", "q"}:
            verdict = input("verdict [c/w/a/s/q]: ").strip().lower()
        if verdict == "q":
            break
        if verdict == "s":
            continue
        note = input("note (optional, enter to skip): ").strip()
        results.append(
            {
                "dataset_index": idx,
                "primary": s["primary"],
                "verdict": {"c": "correct", "w": "wrong", "a": "ambiguous"}[verdict],
                "note": note,
            }
        )

    # Summary
    counter = Counter(r["verdict"] for r in results)
    total = sum(counter.values())
    print(f"\n{'=' * 70}")
    print(f"Spot-check done: {total} reviewed")
    for k in ("correct", "wrong", "ambiguous"):
        pct = counter[k] / total * 100 if total else 0
        print(f"  {k:10s}: {counter[k]}  ({pct:.1f}%)")

    if args.out:
        Path(args.out).write_text(
            json.dumps(
                {
                    "exp_id": args.exp_id,
                    "n": len(picked),
                    "reviewed": total,
                    "counts": dict(counter),
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.info("spot-check results saved to %s", args.out)


# ── Stats: exhaustiveness + orthogonality + cross-framework ────────────────


def compute_exhaustiveness(samples: list[dict]) -> dict:
    total = len(samples)
    unclass = sum(1 for s in samples if s["primary"] == "unclassified")
    return {
        "total": total,
        "unclassified": unclass,
        "unclassified_pct": (unclass / total * 100) if total else 0.0,
        "pass": (unclass / total <= 0.10) if total else False,
    }


def compute_orthogonality(samples: list[dict], theme_category_map: dict[str, str]) -> dict:
    """χ² independence: theme_category (data/reasoning) × fault_category."""
    if chi2_contingency is None:
        return {"error": "scipy not available", "pass": False}
    rows = []
    for s in samples:
        cat = theme_category_map.get(s["primary"])
        if not cat:
            continue
        rows.append((cat, s["fault_category"]))
    if not rows:
        return {"error": "no rows", "pass": False}
    cats = sorted({r[0] for r in rows})
    faults = sorted({r[1] for r in rows})
    table = [[sum(1 for c, f in rows if c == cat and f == fault) for fault in faults] for cat in cats]
    try:
        chi2, pval, dof, _ = chi2_contingency(table)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "pass": False}
    # Cramér's V
    import math

    n = sum(sum(row) for row in table)
    k = min(len(cats), len(faults))
    cramers_v = math.sqrt(chi2 / (n * (k - 1))) if n and k > 1 else 0.0
    return {
        "categories": cats,
        "fault_categories": faults,
        "table": table,
        "chi2": round(chi2, 3),
        "p_value": round(pval, 5),
        "dof": dof,
        "cramers_v": round(cramers_v, 3),
        "pass": pval > 0.05 or cramers_v < 0.3,  # orthogonal if not strongly dependent
    }


def cross_framework_summary(engine, primary_exp: str) -> list[dict]:
    rows: list[dict] = []
    with Session(engine) as session:
        result = session.exec(select(EvaluationSample.exp_id).distinct())
        exp_ids = sorted({r for r in result.all() if r})
    for exp in exp_ids:
        samples = load_labeled_samples(engine, exp)
        if not samples:
            continue
        unclass = sum(1 for s in samples if s["primary"] == "unclassified")
        rows.append(
            {
                "exp_id": exp,
                "labeled": len(samples),
                "unclassified": unclass,
                "unclassified_pct": round(unclass / len(samples) * 100, 2) if samples else 0.0,
                "is_primary": exp == primary_exp,
            }
        )
    return rows


def render_stats_report(exh: dict, orth: dict, cross: list[dict]) -> str:
    lines = ["# Phase 5 validation report", ""]
    lines.append("## 1. Exhaustiveness")
    lines.append(f"- total labeled: {exh['total']}")
    lines.append(f"- unclassified: {exh['unclassified']} ({exh['unclassified_pct']:.2f}%)")
    lines.append(f"- target: ≤ 10%")
    lines.append(f"- **{'PASS' if exh['pass'] else 'FAIL'}**")
    lines.append("")
    lines.append("## 2. Orthogonality (theme_category × fault_category χ²)")
    if "error" in orth:
        lines.append(f"- error: {orth['error']}")
    else:
        lines.append(f"- categories: {orth['categories']}")
        lines.append(f"- fault_categories: {orth['fault_categories']}")
        lines.append(f"- χ² = {orth['chi2']}, p = {orth['p_value']}, dof = {orth['dof']}")
        lines.append(f"- Cramér's V = {orth['cramers_v']}")
        lines.append(f"- contingency table:")
        lines.append(f"  {orth['table']}")
        lines.append(f"- **{'PASS (orthogonal)' if orth['pass'] else 'FAIL (strongly dependent)'}**")
    lines.append("")
    lines.append("## 3. Cross-framework sanity")
    lines.append("| exp_id | labeled | unclassified | pct | primary |")
    lines.append("|---|---|---|---|---|")
    for r in cross:
        lines.append(
            f"| {r['exp_id']} | {r['labeled']} | {r['unclassified']} | {r['unclassified_pct']}% | {'yes' if r['is_primary'] else ''} |"
        )
    lines.append("")
    lines.append("## 4. Spot-check (human reviewer)")
    lines.append("- Run `validate.py spot-check` separately and paste the summary here.")
    lines.append("- Target: ≥ 85% correct.")
    return "\n".join(lines)


def run_stats(args) -> None:
    engine = get_engine(args.db)
    samples = load_labeled_samples(engine, args.exp_id)
    logger.info("loaded %d labeled samples for %s", len(samples), args.exp_id)

    exh = compute_exhaustiveness(samples)

    theme_cat_map: dict[str, str] = {}
    if args.theme_category:
        with Path(args.theme_category).open("r", encoding="utf-8") as f:
            theme_cat_map = json.load(f)
    orth = compute_orthogonality(samples, theme_cat_map) if theme_cat_map else {"error": "no theme_category map provided", "pass": False}

    cross = cross_framework_summary(engine, args.exp_id)

    report = render_stats_report(exh, orth, cross)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        logger.info("stats report saved to %s", args.out)
    else:
        print(report)


def main():
    p = argparse.ArgumentParser(description="Phase 5 validation CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("spot-check", help="Interactive spot-check reviewer")
    sp.add_argument("--db", required=True)
    sp.add_argument("--exp_id", default="thinkdepthai-qwen3.5-plus")
    sp.add_argument("--dossier_dir", required=True)
    sp.add_argument("--analysis", help="Path to per_case_analysis.md")
    sp.add_argument("--n", type=int, default=20)
    sp.add_argument("--seed", type=int, default=42)
    sp.add_argument("--out", help="Optional JSON output for review results")
    sp.set_defaults(func=run_spot_check)

    ss = sub.add_parser("stats", help="Compute exhaustiveness + orthogonality + cross-framework summary")
    ss.add_argument("--db", required=True)
    ss.add_argument("--exp_id", default="thinkdepthai-qwen3.5-plus")
    ss.add_argument("--theme_category", help="JSON map: theme_name -> 'data' | 'reasoning'")
    ss.add_argument("--out", help="Output validation.md path")
    ss.set_defaults(func=run_stats)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
