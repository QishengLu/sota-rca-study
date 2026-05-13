#!/usr/bin/env python
"""Phase 6 prereq — build per-case per-round transitions parquet for failed cases.

Scope: failed cases across 5 DR agents:
  - thinkdepthai-qwen3.5-plus       (105 failed)
  - thinkdepthai-claude-sonnet-4.6  (51  failed)
  - aiq-qwen3.5-plus                (113 failed)
  - claudecode-qwen3.5-plus         (103 failed)
  - taskweaver-qwen3.5-plus         (202 failed, reserved — no v1 labels yet)
Total ≈ 574 cases. Expected ~23k transition rows, <5 MB parquet.

Output: analysis/3-failure-modes/_cache/transitions_per_case.parquet

Independent of the dashboard viz cache (scripts/dashboard/analysis_cache.json);
rebuilding this file has zero effect on the running dashboard.

Usage:
    cd RCAgentEval
    uv run python scripts/failure_analysis/build_transitions_cache.py
    uv run python scripts/failure_analysis/build_transitions_cache.py --limit 10  # smoke test
    uv run python scripts/failure_analysis/build_transitions_cache.py --exp_id aiq-qwen3.5-plus
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import Counter
from pathlib import Path

import pandas as pd
from sqlmodel import Session, create_engine, select

REPO_ROOT = Path(__file__).resolve().parents[3]
RCABENCH_ROOT = REPO_ROOT / "RCAgentEval"
sys.path.insert(0, str(RCABENCH_ROOT))
# dashboard backend uses flat imports (e.g. `from api.deps import get_db`),
# so its own root (scripts/dashboard/backend) has to be on sys.path.
sys.path.insert(0, str(RCABENCH_ROOT / "scripts" / "dashboard" / "backend"))

from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402
from sota_rca.analysis.triplet_coherence import analyze_transitions  # noqa: E402
from api.routes.analysis import (  # noqa: E402
    _extract_steps_with_llm_intents,
    _load_gt_context,
    _load_gt_from_causal_graph,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = "postgresql://postgres:postgres@localhost:5433/SOTA-Agents"
DEFAULT_AGENTS = [
    "thinkdepthai-qwen3.5-plus",
    "thinkdepthai-claude-sonnet-4.6",
    "aiq-qwen3.5-plus",
    "claudecode-qwen3.5-plus",
    "taskweaver-qwen3.5-plus",
]
DEFAULT_OUT = REPO_ROOT / "analysis" / "3-failure-modes" / "_cache" / "transitions_per_case.parquet"


def iter_failed_samples(session: Session, exp_ids: list[str], limit: int | None):
    stmt = (
        select(EvaluationSample)
        .where(
            EvaluationSample.exp_id.in_(exp_ids),
            EvaluationSample.stage == "judged",
            EvaluationSample.correct == False,  # noqa: E712
        )
        .order_by(EvaluationSample.exp_id, EvaluationSample.dataset_index)
    )
    rows = session.exec(stmt).all()
    if limit:
        rows = rows[:limit]
    return rows


def build_rows_for_sample(sample: EvaluationSample) -> list[dict]:
    steps = _extract_steps_with_llm_intents(sample)
    if not steps:
        return []
    gt = _load_gt_from_causal_graph(sample) or _load_gt_context(sample)
    report = analyze_transitions(sample.id, bool(sample.correct), steps, gt)
    if not report.transitions:
        return []

    meta = sample.meta or {}
    v1 = (meta.get("failure_analysis") or {}).get("v1") or {}
    pivot = v1.get("pivot_round")
    primary = v1.get("primary")

    out = []
    for i, t in enumerate(report.transitions):
        out.append({
            "exp_id": sample.exp_id,
            "dataset_index": int(sample.dataset_index),
            "sample_id": int(sample.id),
            "correct": bool(sample.correct),
            "pivot_round": int(pivot) if isinstance(pivot, int) else None,
            "primary": primary,
            "transition_idx": i,
            "round_from": int(t.pair[0]),
            "round_to": int(t.pair[1]),
            "label": t.label,
            "rt_utilization": t.rt_utilization,
            "prev_dist": int(t.prev_dist) if t.prev_dist is not None else None,
            "next_dist": int(t.next_dist) if t.next_dist is not None else None,
            "is_new_service": bool(t.is_new_service),
            "prev_services_on_gt": "|".join(t.prev_services_on_gt or []),
            "next_services_on_gt": "|".join(t.next_services_on_gt or []),
        })
    return out


def summarize(df: pd.DataFrame) -> None:
    if df.empty:
        logger.warning("empty dataframe, nothing to summarize")
        return
    logger.info("=== Build summary ===")
    logger.info("rows (transitions): %d", len(df))
    logger.info("cases: %d", df.groupby(["exp_id", "dataset_index"]).ngroups)
    per_agent = (
        df.groupby("exp_id")
        .agg(
            cases=("dataset_index", "nunique"),
            transitions=("transition_idx", "count"),
            avg_trans_per_case=("transition_idx", lambda s: round(len(s) / s.nunique(), 1) if s.nunique() else 0),
            pct_with_pivot=("pivot_round", lambda s: round(100 * s.notna().mean(), 1)),
        )
        .reset_index()
    )
    logger.info("per agent:\n%s", per_agent.to_string(index=False))

    label_counts = Counter(df["label"])
    logger.info("label distribution (top 14): %s", sorted(label_counts.items(), key=lambda x: -x[1]))

    rt_counts = Counter(df["rt_utilization"])
    logger.info("rt_utilization distribution: %s", sorted(rt_counts.items(), key=lambda x: -x[1]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 6 prereq — build transitions_per_case.parquet")
    parser.add_argument("--db", default=DEFAULT_DB_URL)
    parser.add_argument(
        "--exp_id",
        action="append",
        default=None,
        help="Limit to one exp_id (repeatable). Default = 5 DR agents.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=None, help="Smoke-test cap on samples")
    parser.add_argument("--dry-run", action="store_true", help="Build in-memory, don't write parquet")
    args = parser.parse_args()

    exp_ids = args.exp_id if args.exp_id else DEFAULT_AGENTS
    logger.info("scope: exp_ids=%s limit=%s", exp_ids, args.limit)

    engine = create_engine(args.db)
    t0 = time.time()
    all_rows: list[dict] = []
    skipped_no_steps = 0
    skipped_no_trans = 0

    with Session(engine) as session:
        samples = iter_failed_samples(session, exp_ids, args.limit)
        logger.info("fetched %d failed judged samples", len(samples))

        for idx, sample in enumerate(samples, 1):
            if idx % 50 == 0 or idx == len(samples):
                logger.info(
                    "progress: %d/%d  (%.1f cases/sec, %d rows so far)",
                    idx, len(samples), idx / max(time.time() - t0, 1e-6), len(all_rows),
                )
            try:
                rows = build_rows_for_sample(sample)
            except Exception as exc:
                logger.error(
                    "exc building transitions for exp_id=%s idx=%s: %s",
                    sample.exp_id, sample.dataset_index, exc,
                )
                continue
            if not rows:
                # Determine reason: no steps or no transitions
                steps = _extract_steps_with_llm_intents(sample)
                if not steps:
                    skipped_no_steps += 1
                else:
                    skipped_no_trans += 1
                continue
            all_rows.extend(rows)

    elapsed = time.time() - t0
    logger.info("done in %.1fs. rows=%d skipped_no_steps=%d skipped_no_trans=%d",
                elapsed, len(all_rows), skipped_no_steps, skipped_no_trans)

    if not all_rows:
        logger.error("no rows produced; aborting write")
        sys.exit(2)

    df = pd.DataFrame(all_rows)
    summarize(df)

    if args.dry_run:
        logger.info("--dry-run set; skipping parquet write")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.output, index=False, compression="zstd")
    size_mb = args.output.stat().st_size / 1024 / 1024
    logger.info("wrote %s (%.2f MB, %d rows)", args.output, size_mb, len(df))


if __name__ == "__main__":
    main()
