#!/usr/bin/env python
"""Phase 6 — Behavior × Intent × Failure-mode statistical join.

Runs six cross-tables to answer: "which behavior/intent patterns cluster with
which failure modes?" Pure statistics — no labeling, no interpretation.

Inputs (read from DB):
  - meta.failure_analysis.v1.primary          ← failure mode theme per case
  - meta.failure_analysis.v1.pivot_round      ← round where agent diverged
  - meta.llm_intents.claude_opus_4_6          ← per-SQL intent sequence
  - meta.graph_metrics.diagnostic             ← matched/missed/hallucinated
  - meta.cost_metrics                         ← effective_rounds, tokens, time
  - meta.difficulty.fault_category            ← for stratification

Outputs:
  - <out_dir>/behavior_failure_join.md
  - <out_dir>/behavior_failure_join.json

Tables:
  1. failure × intent at pivot round                    (χ²)
  2. failure × 5-stage at pivot round                   (χ²)
  3. failure × pre-pivot 2-gram prefix                  (Fisher, BH-corrected)
  4. failure × phase coverage before pivot              (mean vector + 95% CI)
  5. failure × evidence-utilization at pivot (R→T)      (χ²)
  6. failure × cost signature                           (ANOVA + BH)

Usage:
    cd RCAgentEval
    uv run python scripts/failure_analysis/behavior_failure_join.py \\
        --db $UTU_DB_URL \\
        --exp_id thinkdepthai-qwen3.5-plus \\
        --out_dir analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2
"""

import argparse
import json
import logging
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sqlmodel import Session, create_engine, select

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402

try:
    from scipy.stats import chi2_contingency, f_oneway, fisher_exact
except ImportError as exc:  # noqa: BLE001
    print(f"scipy required for Phase 6 statistics: {exc}", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

VERSION_KEY = "v1"
INTENT_MODEL_KEY = "claude_opus_4_6"

STAGE_BY_INTENT = {
    "latency_ranking": "T",
    "throughput_compare": "T",
    "error_rate_scan": "T",
    "error_log_overview": "T",
    "metric_scan": "T",
    "service_trace_scan": "V",
    "trace_follow": "V",
    "call_tree_build": "V",
    "service_error_log": "L",
    "service_log_browse": "L",
    "keyword_search": "L",
    "error_timeline": "L",
    "container_resource": "M",
    "jvm_state": "M",
    "network_layer": "M",
    "k8s_state": "M",
    "db_state": "M",
    "baseline_collect": "B",
    "baseline_contrast": "B",
}
STAGES = ["T", "V", "L", "M", "B"]


# ── Case loading ────────────────────────────────────────────────────────────


def get_engine(db_url: str):
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(db_url, connect_args=connect_args)


def load_cases(engine, exp_id: str) -> list[dict]:
    out: list[dict] = []
    with Session(engine) as session:
        stmt = select(EvaluationSample).where(
            EvaluationSample.exp_id == exp_id,
            EvaluationSample.stage == "judged",
        )
        for s in session.exec(stmt).all():
            meta = s.meta or {}
            fa = (meta.get("failure_analysis") or {}).get(VERSION_KEY)
            if not fa or not fa.get("primary"):
                continue
            intents_raw = (meta.get("llm_intents") or {}).get(INTENT_MODEL_KEY) or []
            # Group per round
            per_round: dict[int, list[dict]] = defaultdict(list)
            for e in intents_raw:
                if not isinstance(e, dict):
                    continue
                rd = e.get("round")
                if rd is None:
                    continue
                per_round[int(rd)].append(e)
            out.append(
                {
                    "dataset_index": s.dataset_index,
                    "primary": fa["primary"],
                    "secondary": fa.get("secondary") or [],
                    "pivot_round": fa.get("pivot_round"),
                    "intents_by_round": per_round,
                    "fault_category": (meta.get("difficulty") or {}).get("fault_category", "?"),
                    "graph_diag": (meta.get("graph_metrics") or {}).get("diagnostic", {}) or {},
                    "cost": meta.get("cost_metrics") or {},
                }
            )
    logger.info("loaded %d labeled cases for %s", len(out), exp_id)
    return out


# ── Feature extractors ─────────────────────────────────────────────────────


def dominant_stage(round_intents: list[dict]) -> str:
    if not round_intents:
        return "-"
    tags = [STAGE_BY_INTENT.get(e.get("intent", ""), "-") for e in round_intents]
    return max(set(tags), key=tags.count)


def dominant_intent(round_intents: list[dict]) -> str:
    if not round_intents:
        return "-"
    names = [e.get("intent", "") for e in round_intents if e.get("intent")]
    if not names:
        return "-"
    return Counter(names).most_common(1)[0][0]


def intent_at_pivot(case: dict) -> str:
    pr = case.get("pivot_round")
    if pr is None:
        return "-"
    return dominant_intent(case["intents_by_round"].get(pr, []))


def stage_at_pivot(case: dict) -> str:
    pr = case.get("pivot_round")
    if pr is None:
        return "-"
    return dominant_stage(case["intents_by_round"].get(pr, []))


def pre_pivot_2gram(case: dict) -> str:
    pr = case.get("pivot_round")
    if pr is None or pr < 2:
        return "-"
    r1 = dominant_intent(case["intents_by_round"].get(pr - 2, []))
    r2 = dominant_intent(case["intents_by_round"].get(pr - 1, []))
    if r1 == "-" and r2 == "-":
        return "-"
    return f"{r1}→{r2}"


def phase_coverage_before_pivot(case: dict) -> list[int]:
    """Binary 5-vec of {T, V, L, M, B} visited before pivot."""
    pr = case.get("pivot_round") or 0
    visited: set[str] = set()
    for rd, entries in case["intents_by_round"].items():
        if rd < pr:
            visited.add(dominant_stage(entries))
    return [1 if st in visited else 0 for st in STAGES]


def evidence_utilization_at_pivot(case: dict) -> str:
    """Approximate: no data = pivot round has no intents; utilized/partial/ignored is a 3-way
    proxy from graph_diag at the case level since we don't have per-round hit info.
    We classify case-level with these rules:
      - no data:     no intents at pivot_round
      - utilized:    the agent reached at least one matched_service
      - ignored:     agent hallucinated but missed all GT
      - partial:     otherwise
    """
    pr = case.get("pivot_round")
    if pr is None or not case["intents_by_round"].get(pr):
        return "no_data"
    gd = case["graph_diag"] or {}
    matched = gd.get("matched_services") or []
    missed = gd.get("missed_services") or []
    if matched and not missed:
        return "utilized"
    if matched:
        return "partial"
    return "ignored"


def cost_features(case: dict) -> dict[str, float]:
    cm = case["cost"] or {}
    return {
        "effective_rounds": float(cm.get("effective_rounds") or 0),
        "total_tokens": float(cm.get("total_tokens") or 0),
        "time_cost": float(cm.get("time_cost") or 0),
    }


# ── Statistical helpers ────────────────────────────────────────────────────


def chi2_table(rows: list[tuple[str, str]]) -> dict:
    themes = sorted({r[0] for r in rows})
    cats = sorted({r[1] for r in rows})
    table = [[sum(1 for t, c in rows if t == theme and c == cat) for cat in cats] for theme in themes]
    if not table or not table[0]:
        return {"table": [], "themes": themes, "cats": cats, "chi2": None, "p": None}
    try:
        chi2, pval, dof, _ = chi2_contingency(table)
        n = sum(sum(row) for row in table)
        k = min(len(themes), len(cats))
        v = math.sqrt(chi2 / (n * (k - 1))) if n and k > 1 else 0.0
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "themes": themes, "cats": cats, "table": table}
    return {
        "themes": themes,
        "cats": cats,
        "table": table,
        "chi2": round(chi2, 3),
        "p": round(pval, 5),
        "dof": dof,
        "cramers_v": round(v, 3),
    }


def bh_correct(pvals: list[float], alpha: float = 0.05) -> list[bool]:
    """Benjamini–Hochberg procedure. Returns mask of 'significant' booleans."""
    m = len(pvals)
    indexed = sorted(enumerate(pvals), key=lambda x: x[1])
    reject = [False] * m
    threshold_reached = False
    for rank, (orig_i, p) in enumerate(indexed, 1):
        thresh = alpha * rank / m
        if p <= thresh:
            threshold_reached = True
            last_rank = rank
    if threshold_reached:
        for rank, (orig_i, p) in enumerate(indexed, 1):
            if rank <= last_rank:  # noqa: F821
                reject[orig_i] = True
    return reject


# ── Tables ─────────────────────────────────────────────────────────────────


def table_intent_at_pivot(cases: list[dict]) -> dict:
    rows = [(c["primary"], intent_at_pivot(c)) for c in cases]
    rows = [r for r in rows if r[1] != "-"]
    return {
        "title": "1. Failure mode × intent at pivot round",
        **chi2_table(rows),
    }


def table_stage_at_pivot(cases: list[dict]) -> dict:
    rows = [(c["primary"], stage_at_pivot(c)) for c in cases]
    rows = [r for r in rows if r[1] != "-"]
    return {
        "title": "2. Failure mode × 5-stage at pivot round",
        **chi2_table(rows),
    }


def table_pre_pivot_2gram(cases: list[dict], top_k: int = 20) -> dict:
    rows_all = [(c["primary"], pre_pivot_2gram(c)) for c in cases if pre_pivot_2gram(c) != "-"]
    # Restrict columns to top_k 2-grams
    gram_counts = Counter(r[1] for r in rows_all)
    top_grams = {g for g, _ in gram_counts.most_common(top_k)}
    rows = [(t, g) for t, g in rows_all if g in top_grams]
    stats = chi2_table(rows)

    # Per (theme, 2-gram) Fisher exact
    themes = stats["themes"]
    cats = stats["cats"]
    table = stats["table"]
    total_by_theme = [sum(row) for row in table]
    total_by_cat = [sum(table[i][j] for i in range(len(themes))) for j in range(len(cats))]
    grand = sum(total_by_theme)
    pvals: list[float] = []
    cells: list[tuple[int, int]] = []
    for i, theme in enumerate(themes):
        for j, cat in enumerate(cats):
            a = table[i][j]
            b = total_by_theme[i] - a
            c_ = total_by_cat[j] - a
            d = grand - a - b - c_
            if a == 0 and b == 0 and c_ == 0 and d == 0:
                continue
            try:
                _, p = fisher_exact([[a, b], [c_, d]], alternative="greater")
            except Exception:  # noqa: BLE001
                p = 1.0
            pvals.append(p)
            cells.append((i, j))
    bh = bh_correct(pvals) if pvals else []
    sig_cells = [
        {"theme": themes[i], "2gram": cats[j], "count": table[i][j], "p": round(pvals[k], 5)}
        for k, (i, j) in enumerate(cells)
        if bh[k]
    ]
    return {
        "title": "3. Failure mode × pre-pivot 2-gram prefix (Fisher + BH)",
        **stats,
        "significant_cells": sig_cells,
    }


def table_phase_coverage(cases: list[dict]) -> dict:
    by_theme: dict[str, list[list[int]]] = defaultdict(list)
    for c in cases:
        by_theme[c["primary"]].append(phase_coverage_before_pivot(c))
    out: dict[str, Any] = {
        "title": "4. Failure mode × phase coverage before pivot (mean vector)",
        "stages": STAGES,
        "rows": [],
    }
    for theme, vecs in sorted(by_theme.items()):
        n = len(vecs)
        if n == 0:
            continue
        means = [sum(v[i] for v in vecs) / n for i in range(5)]
        out["rows"].append(
            {
                "theme": theme,
                "n": n,
                "mean": [round(m, 3) for m in means],
            }
        )
    return out


def table_evidence_util(cases: list[dict]) -> dict:
    rows = [(c["primary"], evidence_utilization_at_pivot(c)) for c in cases]
    return {
        "title": "5. Failure mode × evidence-utilization at pivot (R→T)",
        **chi2_table(rows),
    }


def table_cost_signature(cases: list[dict]) -> dict:
    by_theme: dict[str, list[dict[str, float]]] = defaultdict(list)
    for c in cases:
        by_theme[c["primary"]].append(cost_features(c))
    metrics = ["effective_rounds", "total_tokens", "time_cost"]
    out: dict[str, Any] = {
        "title": "6. Failure mode × cost signature (ANOVA)",
        "metrics": metrics,
        "rows": [],
        "anova": {},
    }
    for theme, feats in sorted(by_theme.items()):
        if not feats:
            continue
        n = len(feats)
        mean_row = {m: round(sum(f[m] for f in feats) / n, 2) for m in metrics}
        out["rows"].append({"theme": theme, "n": n, **mean_row})
    # One-way ANOVA per metric
    for m in metrics:
        groups = [[f[m] for f in feats] for feats in by_theme.values() if feats]
        if len(groups) < 2 or any(len(g) < 2 for g in groups):
            out["anova"][m] = {"error": "insufficient groups"}
            continue
        try:
            F, p = f_oneway(*groups)
        except Exception as exc:  # noqa: BLE001
            out["anova"][m] = {"error": str(exc)}
            continue
        out["anova"][m] = {"F": round(float(F), 3), "p": round(float(p), 5)}
    return out


# ── Render report ──────────────────────────────────────────────────────────


def render_md(tables: list[dict], negative_results: list[str]) -> str:
    lines = ["# Phase 6 — Behavior × Intent × Failure-Mode join", ""]
    for t in tables:
        lines.append(f"## {t['title']}")
        lines.append("")
        if "error" in t:
            lines.append(f"- error: {t['error']}")
            lines.append("")
            continue
        # Generic stats line
        if "chi2" in t and t["chi2"] is not None:
            lines.append(f"- χ² = {t['chi2']}, p = {t['p']}, dof = {t.get('dof', '?')}, Cramér's V = {t.get('cramers_v', '?')}")
        if "anova" in t:
            for m, st in t["anova"].items():
                if "error" in st:
                    lines.append(f"- ANOVA {m}: {st['error']}")
                else:
                    lines.append(f"- ANOVA {m}: F = {st['F']}, p = {st['p']}")
        # Contingency table for chi2 tables
        if "table" in t and t.get("themes") and t.get("cats"):
            lines.append("")
            header = "| theme ↓ / col → | " + " | ".join(t["cats"]) + " |"
            sep = "|" + "---|" * (1 + len(t["cats"]))
            lines.append(header)
            lines.append(sep)
            for theme, row in zip(t["themes"], t["table"], strict=False):
                lines.append(f"| {theme} | " + " | ".join(str(v) for v in row) + " |")
        # Phase coverage rows
        if t["title"].startswith("4."):
            lines.append("")
            lines.append("| theme | n | T | V | L | M | B |")
            lines.append("|---|---|---|---|---|---|---|")
            for row in t["rows"]:
                lines.append(f"| {row['theme']} | {row['n']} | " + " | ".join(f"{v:.2f}" for v in row["mean"]) + " |")
        # Cost rows
        if t["title"].startswith("6."):
            lines.append("")
            metrics = t.get("metrics", [])
            lines.append("| theme | n | " + " | ".join(metrics) + " |")
            lines.append("|" + "---|" * (2 + len(metrics)))
            for row in t["rows"]:
                lines.append(
                    f"| {row['theme']} | {row['n']} | " + " | ".join(str(row[m]) for m in metrics) + " |"
                )
        # Significant cells (2-gram)
        if "significant_cells" in t and t["significant_cells"]:
            lines.append("")
            lines.append("**Significant (BH-corrected) cells:**")
            for cell in t["significant_cells"]:
                lines.append(f"- `{cell['theme']}` × `{cell['2gram']}`: count={cell['count']}, p={cell['p']}")
        lines.append("")

    lines.append("## Negative results")
    lines.append("")
    lines.append("Failure modes with NO significant behavioral signature in any of the six tables above.")
    lines.append("These cannot be treated by behavior-level middleware and require a different intervention layer.")
    lines.append("")
    if negative_results:
        for theme in negative_results:
            lines.append(f"- `{theme}`")
    else:
        lines.append("- (every failure mode has at least one significant behavioral correlate)")
    return "\n".join(lines)


def compute_negative_results(tables: list[dict], alpha: float = 0.05) -> list[str]:
    """A failure mode is 'negative' if no table shows a significant correlate touching it."""
    all_themes: set[str] = set()
    signal_themes: set[str] = set()
    for t in tables:
        if "themes" in t:
            all_themes.update(t["themes"])
        p = t.get("p")
        if p is not None and p < alpha:
            signal_themes.update(t.get("themes", []))
        # 2-gram table: significant cells
        for cell in t.get("significant_cells", []) or []:
            signal_themes.add(cell["theme"])
        # ANOVA table (cost signature): if any metric significant, credit all themes
        if "anova" in t:
            for _, st in t["anova"].items():
                if isinstance(st, dict) and st.get("p") is not None and st["p"] < alpha:
                    signal_themes.update(r["theme"] for r in t.get("rows", []))
    return sorted(all_themes - signal_themes)


# ── Main ───────────────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser(description="Phase 6 — behavior/intent × failure-mode statistical join")
    p.add_argument("--db", required=True)
    p.add_argument("--exp_id", default="thinkdepthai-qwen3.5-plus")
    p.add_argument("--out_dir", required=True)
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    engine = get_engine(args.db)
    cases = load_cases(engine, args.exp_id)
    if not cases:
        logger.error("no labeled cases found — run Phase 4 first")
        sys.exit(1)

    tables = [
        table_intent_at_pivot(cases),
        table_stage_at_pivot(cases),
        table_pre_pivot_2gram(cases),
        table_phase_coverage(cases),
        table_evidence_util(cases),
        table_cost_signature(cases),
    ]
    negative = compute_negative_results(tables)

    md = render_md(tables, negative)
    (out_dir / "behavior_failure_join.md").write_text(md, encoding="utf-8")

    machine = {
        "exp_id": args.exp_id,
        "n_cases": len(cases),
        "tables": tables,
        "negative_results": negative,
    }
    (out_dir / "behavior_failure_join.json").write_text(
        json.dumps(machine, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    logger.info("wrote %s and .json", out_dir / "behavior_failure_join.md")
    logger.info("negative results: %d themes", len(negative))


if __name__ == "__main__":
    main()
