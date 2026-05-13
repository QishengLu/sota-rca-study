"""Rejudge — score CausalGraph outputs using aegis v3 rca_metrics.

Drop-in replacement for old SOTA-agents `rejudge_samples.py`. Reads samples
with stage='rollout' or 'judged', computes node/edge/RC F1, writes
meta.graph_metrics.primary, marks stage='judged'.

Must filter by exp_id in shared DB scenarios (avoid cross-contamination).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from ..runner.db_writer import EvaluationSample, get_engine

logger = logging.getLogger(__name__)


def rejudge_exp(exp_id: str, *, redo_judged: bool = False) -> dict[str, int]:
    """Re-judge all samples for an exp_id.

    Args:
        exp_id: filter by this exp_id only (REQUIRED in shared DB)
        redo_judged: if True, also re-judge stage='judged' samples (default False)

    Returns counts: {processed, correct, incorrect, errors}
    """
    try:
        from rcabench_platform.v3.sdk.evaluation.rca_metrics import evaluate_graphs  # type: ignore
        from rcabench_platform.v3.sdk.evaluation.causal_graph import CausalGraph  # type: ignore
    except ImportError:
        # Fallback: use local lightweight metric
        from .rca_metrics_fallback import evaluate_graphs, CausalGraph  # type: ignore

    engine = get_engine()
    stages = ["rollout"] + (["judged"] if redo_judged else [])

    stats = {"processed": 0, "correct": 0, "incorrect": 0, "errors": 0}

    with Session(engine) as session:
        stmt = select(EvaluationSample).where(
            EvaluationSample.exp_id == exp_id,
            EvaluationSample.stage.in_(stages),
        )
        samples = session.exec(stmt).all()

        for s in samples:
            try:
                pred_graph = CausalGraph.from_json(s.response or "{}")
                gold_graph = CausalGraph.from_json(s.correct_answer or "{}")
                metrics = evaluate_graphs(pred=pred_graph, gold=gold_graph)
                correct = metrics.get("node_f1", 0.0) >= 0.5

                meta = s.meta or {}
                if isinstance(meta, str):
                    meta = json.loads(meta)
                meta.setdefault("graph_metrics", {})["primary"] = metrics
                s.meta = meta
                flag_modified(s, "meta")

                s.correct = correct
                s.stage = "judged"
                session.add(s)

                stats["processed"] += 1
                stats["correct" if correct else "incorrect"] += 1
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Sample {s.id} judge failed: {e}")
                stats["errors"] += 1

        session.commit()

    logger.info(f"[{exp_id}] rejudge: {stats}")
    return stats
