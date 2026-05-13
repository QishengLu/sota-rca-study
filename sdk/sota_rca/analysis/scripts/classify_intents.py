#!/usr/bin/env python
"""Classify agent trajectory rounds into 19 troubleshooting intents using LLM.

Usage:
    # 10-sample test with haiku
    uv run python scripts/classify_intents.py \
        --db sqlite:///demo-48cases.db \
        --model claude-haiku-4-5-20251001 \
        --limit 10

    # Same 10 samples with gemini for comparison
    uv run python scripts/classify_intents.py \
        --db sqlite:///demo-48cases.db \
        --model gemini-2.5-flash \
        --limit 10

    # Full run (all 172 common samples)
    uv run python scripts/classify_intents.py \
        --db sqlite:///demo-48cases.db \
        --model claude-haiku-4-5-20251001

    # Compare two models' results
    uv run python scripts/classify_intents.py \
        --db sqlite:///demo-48cases.db \
        --compare claude-haiku-4-5-20251001 gemini-2.5-flash

Environment:
    OPENAI_API_KEY: API key for shubiaobiao
    OPENAI_BASE_URL: https://api.shubiaobiao.cn/v1 (default)
"""

import argparse
import json
import logging
import os
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI
from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, create_engine, select

# Add project root for imports
sys.path.insert(0, str(__file__).rsplit("/scripts/", 1)[0])

from sota_rca.runner._fallback_db import EvaluationSample
from sota_rca.analysis.llm_intent_classifier import (
    SQLIntent,
    classify_trajectory,
    extract_sql_rounds,
)
from sota_rca.analysis.trajectory_normalizer import normalize_by_agent


def _agent_type_from_exp(exp_id: str) -> str:
    """Extract agent_type from exp_id (first '-' segment).

    e.g., 'claudecode-qwen3.5-plus' -> 'claudecode'
          'thinkdepthai-claude-sonnet-4.6' -> 'thinkdepthai'
    """
    return exp_id.split("-", 1)[0] if exp_id else ""

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── DB helpers ──────────────────────────────────────────────────────────────


def get_engine(db_url: str, concurrency: int = 1):
    """Create engine with pool sized for thread concurrency.

    Default SQLAlchemy pool is 5 + overflow 10 = 15. At concurrency > 15, thread-local
    sessions contend and time out. We set pool_size = max(concurrency * 2, 30) so each
    worker can hold its session without contention.
    """
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(
        db_url,
        connect_args=connect_args,
        pool_size=max(concurrency * 2, 30),
        max_overflow=10,
        pool_pre_ping=True,
    )


def get_common_dataset_indexes(engine, exp_ids: list[str]) -> list[int]:
    """Find dataset_indexes common to all exp_ids (judged stage only)."""
    with engine.connect() as conn:
        intersect = " INTERSECT ".join(
            f"SELECT dataset_index FROM evaluation_data WHERE exp_id = '{e}' AND stage = 'judged'" for e in exp_ids
        )
        rows = conn.execute(text(f"SELECT dataset_index FROM ({intersect}) t ORDER BY dataset_index")).fetchall()
    return [r[0] for r in rows]


def get_exp_ids(engine) -> list[str]:
    """Get all exp_ids with judged samples."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT exp_id FROM evaluation_data WHERE stage = 'judged' ORDER BY exp_id")
        ).fetchall()
    return [r[0] for r in rows]


def model_key(model_name: str) -> str:
    """Convert model name to a safe key for storing in meta.llm_intents.<key>."""
    return model_name.replace("/", "_").replace(".", "_").replace("-", "_")


# ── AIMD adaptive concurrency (thread-based) ────────────────────────────────


class AdaptiveConcurrency:
    """Thread-safe AIMD concurrency limiter.

    Slow-start from `initial_capacity`, +1 every 3 consecutive successes (up to
    `max_capacity`). On failure: capacity = max(1, capacity - 1) and streak
    resets. Callers hold a slot for the whole request (acquire/release bracket).
    """

    def __init__(self, max_capacity: int, initial_capacity: int) -> None:
        self.max_capacity = max(1, max_capacity)
        self.capacity = max(1, min(initial_capacity, self.max_capacity))
        self._active = 0
        self._success_streak = 0
        self._cond = threading.Condition()

    def acquire(self) -> None:
        with self._cond:
            self._cond.wait_for(lambda: self._active < self.capacity)
            self._active += 1

    def release(self, success: bool) -> None:
        with self._cond:
            self._active -= 1
            if success:
                self._success_streak += 1
                if self._success_streak >= 3 and self.capacity < self.max_capacity:
                    self.capacity += 1
                    self._success_streak = 0
                    logger.info(
                        "[AIMD] capacity ↑ to %d/%d (streak reset)",
                        self.capacity, self.max_capacity,
                    )
            else:
                new_cap = max(1, self.capacity - 1)
                if new_cap < self.capacity:
                    logger.warning("[AIMD] capacity ↓ %d → %d (failure)", self.capacity, new_cap)
                self.capacity = new_cap
                self._success_streak = 0
            self._cond.notify_all()


# ── Main logic ──────────────────────────────────────────────────────────────


def _indexes_for_exp(engine, exp_id: str) -> list[int]:
    """All judged dataset_indexes for a single exp_id (no intersection)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"SELECT DISTINCT dataset_index FROM evaluation_data "
                f"WHERE exp_id = '{exp_id}' AND stage = 'judged' ORDER BY dataset_index"
            )
        ).fetchall()
    return [r[0] for r in rows]


def run_classify(args):
    engine = get_engine(args.db, concurrency=args.concurrency)

    if args.exp_ids:
        # Per-exp_id mode: full coverage per exp_id (no intersection)
        exp_ids = [e.strip() for e in args.exp_ids.split(",") if e.strip()]
        logger.info("Using --exp_ids filter (full coverage per exp_id): %s", exp_ids)
        indexes_by_exp: dict[str, list[int]] = {e: _indexes_for_exp(engine, e) for e in exp_ids}
        if args.limit:
            indexes_by_exp = {e: idxs[: args.limit] for e, idxs in indexes_by_exp.items()}
            logger.info("Limited to first %d cases per exp_id", args.limit)
        for e, idxs in indexes_by_exp.items():
            logger.info("  %s: %d samples", e, len(idxs))
    else:
        # Legacy mode: intersection across ALL judged exp_ids (48-case demo style)
        exp_ids = get_exp_ids(engine)
        logger.info("Found exp_ids: %s", exp_ids)
        common_indexes = get_common_dataset_indexes(engine, exp_ids)
        logger.info("Common dataset_indexes across %d exp_ids: %d cases", len(exp_ids), len(common_indexes))
        if args.limit:
            common_indexes = common_indexes[: args.limit]
            logger.info("Limited to first %d cases", args.limit)
        indexes_by_exp = {e: common_indexes for e in exp_ids}

    # Init OpenAI client (thread-safe, share across workers)
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.shubiaobiao.cn/v1")
    client = OpenAI(api_key=api_key, base_url=base_url)

    mkey = model_key(args.model)

    # Flatten work queue across all exp_ids
    work_items: list[tuple[str, int]] = []
    for exp_id in exp_ids:
        for idx in indexes_by_exp.get(exp_id, []):
            work_items.append((exp_id, idx))

    # Shared state across workers (guarded by lock)
    stats = {"total": 0, "classified": 0, "skipped": 0, "failed": 0}
    all_intents: Counter = Counter()
    lock = threading.Lock()

    # AIMD limiter: start small, ramp up after consecutive successes; cap at --concurrency
    aimd = AdaptiveConcurrency(
        max_capacity=max(1, args.concurrency),
        initial_capacity=max(1, args.initial_concurrency or args.concurrency),
    )
    logger.info("[AIMD] initial capacity=%d, max=%d", aimd.capacity, aimd.max_capacity)

    # Per-thread session via thread-local (avoid session thread-safety issues)
    _tls = threading.local()

    def get_session() -> Session:
        sess = getattr(_tls, "session", None)
        if sess is None:
            sess = Session(engine)
            _tls.session = sess
        return sess

    def process_one(exp_id: str, idx: int) -> None:
        session = get_session()
        try:
            stmt = select(EvaluationSample).where(
                EvaluationSample.exp_id == exp_id,
                EvaluationSample.dataset_index == idx,
                EvaluationSample.stage == "judged",
            )
            sample = session.exec(stmt).first()
            if not sample:
                return

            with lock:
                stats["total"] += 1

            # Check if already classified by this model (skip for resume)
            meta = sample.meta or {}
            llm_intents = meta.get("llm_intents", {})
            if mkey in llm_intents and not args.force:
                with lock:
                    stats["skipped"] += 1
                return

            # Parse trajectory
            traj_str = sample.trajectories or "[]"
            try:
                trajectory = json.loads(traj_str)
            except json.JSONDecodeError:
                logger.warning("Bad trajectory JSON: exp_id=%s idx=%d", exp_id, idx)
                with lock:
                    stats["failed"] += 1
                return

            # Framework-specific normalization
            trajectory = normalize_by_agent(_agent_type_from_exp(exp_id), trajectory)

            rounds = extract_sql_rounds(trajectory)
            if not rounds:
                logger.debug("No SQL rounds: exp_id=%s idx=%d", exp_id, idx)
                llm_intents[mkey] = []
                meta["llm_intents"] = llm_intents
                sample.meta = meta
                flag_modified(sample, "meta")
                session.add(sample)
                session.commit()
                with lock:
                    stats["classified"] += 1
                return

            # Classify (LLM call) — gated by AIMD limiter so success/failure
            # adjusts effective concurrency
            aimd.acquire()
            t0 = time.time()
            results = classify_trajectory(rounds, client, model=args.model)
            elapsed = time.time() - t0
            aimd.release(success=bool(results))

            if not results:
                logger.warning("Empty LLM result: exp_id=%s idx=%d (%.1fs)", exp_id, idx, elapsed)
                with lock:
                    stats["failed"] += 1
                return

            result_dicts = [
                {
                    "round": r.round_index,
                    "sql_index": r.sql_index,
                    "global_index": r.global_index,
                    "intent": r.intent,
                    "data_type": r.data_type,
                    "reasoning": r.reasoning,
                }
                for r in results
            ]
            llm_intents[mkey] = result_dicts
            meta["llm_intents"] = llm_intents
            sample.meta = meta
            flag_modified(sample, "meta")
            session.add(sample)
            session.commit()

            n_rounds = len({r.round_index for r in results})
            with lock:
                stats["classified"] += 1
                for r in results:
                    all_intents[r.intent] += 1
                done = stats["classified"] + stats["skipped"]
                total = stats["total"]
            logger.info(
                "[%d/%d] exp_id=%s idx=%d: %d SQL in %d rounds (%.1fs)",
                done, total, exp_id, idx, len(results), n_rounds, elapsed,
            )
        except Exception as e:
            try:
                session.rollback()
            except Exception:
                pass
            logger.exception("Worker failed on exp_id=%s idx=%d: %s", exp_id, idx, e)
            with lock:
                stats["failed"] += 1

    concurrency = max(1, args.concurrency)
    logger.info("Dispatching %d work items with concurrency=%d", len(work_items), concurrency)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(process_one, exp_id, idx) for exp_id, idx in work_items]
        for fut in as_completed(futures):
            # Surface any uncaught exceptions
            exc = fut.exception()
            if exc is not None:
                logger.error("Unhandled worker exception: %s", exc)

    logger.info(
        "Done: %d classified, %d skipped, %d failed out of %d total",
        stats["classified"], stats["skipped"], stats["failed"], stats["total"],
    )
    if all_intents:
        logger.info("Intent distribution:")
        for intent, count in all_intents.most_common():
            logger.info("  %-25s %d", intent, count)


def run_compare(args):
    """Compare classification results between two models."""
    engine = get_engine(args.db)
    exp_ids = get_exp_ids(engine)
    common_indexes = get_common_dataset_indexes(engine, exp_ids)

    key_a = model_key(args.compare[0])
    key_b = model_key(args.compare[1])

    total_rounds = 0
    agree = 0
    disagree_details: list[dict] = []

    with Session(engine) as session:
        for exp_id in exp_ids:
            for idx in common_indexes:
                stmt = select(EvaluationSample).where(
                    EvaluationSample.exp_id == exp_id,
                    EvaluationSample.dataset_index == idx,
                    EvaluationSample.stage == "judged",
                )
                sample = session.exec(stmt).first()
                if not sample:
                    continue

                meta = sample.meta or {}
                llm_intents = meta.get("llm_intents", {})
                # Key by (round, sql_index) for v2 format
                def _make_key(r):
                    return (r.get("round", 0), r.get("sql_index", 1))

                results_a = {_make_key(r): r for r in llm_intents.get(key_a, [])}
                results_b = {_make_key(r): r for r in llm_intents.get(key_b, [])}

                all_keys = sorted(set(results_a.keys()) | set(results_b.keys()))
                for k in all_keys:
                    total_rounds += 1
                    intent_a = results_a.get(k, {}).get("intent", "MISSING")
                    intent_b = results_b.get(k, {}).get("intent", "MISSING")
                    if intent_a == intent_b:
                        agree += 1
                    else:
                        disagree_details.append(
                            {
                                "exp_id": exp_id,
                                "dataset_index": idx,
                                "round": k[0],
                                "sql_index": k[1],
                                key_a: intent_a,
                                key_b: intent_b,
                                "reasoning_a": results_a.get(k, {}).get("reasoning", ""),
                                "reasoning_b": results_b.get(k, {}).get("reasoning", ""),
                            }
                        )

    if total_rounds == 0:
        logger.error("No rounds found for comparison. Run classification first.")
        return

    pct = agree / total_rounds * 100
    print(f"\n{'='*70}")
    print(f"Model A: {args.compare[0]} (key: {key_a})")
    print(f"Model B: {args.compare[1]} (key: {key_b})")
    print(f"{'='*70}")
    print(f"Total rounds: {total_rounds}")
    print(f"Agreement:    {agree} ({pct:.1f}%)")
    print(f"Disagreement: {len(disagree_details)} ({100-pct:.1f}%)")

    if disagree_details:
        print(f"\n{'─'*70}")
        print("Disagreements (first 30):")
        print(f"{'─'*70}")
        for d in disagree_details[:30]:
            print(f"\n  exp_id={d['exp_id']} idx={d['dataset_index']} round={d['round']} sql={d.get('sql_index', 1)}")
            print(f"    {key_a}: {d[key_a]}")
            print(f"    {key_b}: {d[key_b]}")

    # Intent-level confusion
    confusion: Counter = Counter()
    for d in disagree_details:
        pair = (d[key_a], d[key_b])
        confusion[pair] += 1

    if confusion:
        print(f"\n{'─'*70}")
        print("Top confusion pairs (A → B):")
        print(f"{'─'*70}")
        for (a, b), count in confusion.most_common(15):
            print(f"  {a:30s} → {b:30s}  ({count})")


def main():
    parser = argparse.ArgumentParser(description="LLM-based intent classification for agent trajectories")
    parser.add_argument("--db", required=True, help="Database URL (e.g., sqlite:////path/to/db)")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001", help="Model ID for classification")
    parser.add_argument("--limit", type=int, default=None, help="Limit to first N cases (per exp_id when --exp_ids is set, else across the intersection)")
    parser.add_argument("--force", action="store_true", help="Re-classify even if results exist")
    parser.add_argument("--compare", nargs=2, metavar="MODEL", help="Compare two models' results")
    parser.add_argument(
        "--exp_ids",
        default=None,
        help="Comma-separated exp_ids to classify (full coverage per exp_id, no intersection). "
             "Example: --exp_ids claudecode-qwen3.5-plus,aiq-qwen3.5-plus",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Max concurrent LLM calls (AIMD ceiling). Each worker uses its own DB session.",
    )
    parser.add_argument(
        "--initial-concurrency",
        type=int,
        default=None,
        help="AIMD starting capacity (slow-start). Defaults to --concurrency (no ramp). "
             "Example: --concurrency 10 --initial-concurrency 6 starts at 6, ramps to 10 after streaks.",
    )

    args = parser.parse_args()

    if args.compare:
        run_compare(args)
    else:
        run_classify(args)


if __name__ == "__main__":
    main()
