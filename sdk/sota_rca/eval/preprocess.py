"""Preprocess — populate EvaluationSample (stage='init') for an exp_id.

Reads ops-lite manifest, creates one row per case with the agent's
incident_description and data_dir reference. Idempotent: re-running
won't duplicate rows.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlmodel import Session, select

from ..data.ops_lite import DEFAULT_CACHE_DIR, iter_cases, Case
from ..runner.db_writer import EvaluationSample, get_engine

logger = logging.getLogger(__name__)


def preprocess_exp(
    exp_id: str,
    *,
    agent_type: str,
    model_name: str,
    cases: list[Case] | None = None,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    limit: int | None = None,
) -> int:
    """Create EvaluationSample rows for each case under this exp_id.

    Returns the number of rows inserted (skips already-existing ones).
    """
    if cases is None:
        cases = list(iter_cases(cache_dir=cache_dir, limit=limit))

    engine = get_engine()
    inserted = 0
    skipped = 0

    with Session(engine) as session:
        for idx, case in enumerate(cases):
            stmt = select(EvaluationSample).where(
                EvaluationSample.exp_id == exp_id,
                EvaluationSample.dataset_index == idx,
            )
            existing = session.exec(stmt).first()
            if existing:
                skipped += 1
                continue

            sample = EvaluationSample(
                dataset="ops-lite",
                dataset_index=idx,
                source=case.name,
                raw_question="",
                augmented_question=case.synthesize_incident_description(),
                correct_answer=json.dumps(_load_causal_graph(case)),
                exp_id=exp_id,
                agent_type=agent_type,
                model_name=model_name,
                stage="init",
                meta={
                    "case_name": case.name,
                    "data_dir": str(case.data_dir),
                    "chaos_family": case.chaos_family,
                    "primary_kind": case.primary_kind,
                    "subtypes": case.subtypes,
                    "root_services": case.root_services,
                    "n_svc": case.n_svc,
                    "n_alarm_svc": case.n_alarm_svc,
                    "system": case.system,
                    "difficulty": _compute_difficulty(case),
                },
            )
            session.add(sample)
            inserted += 1

        session.commit()

    logger.info(f"[{exp_id}] preprocess: inserted={inserted}, skipped={skipped}")
    return inserted


def _load_causal_graph(case: Case) -> dict:
    """Load ground-truth causal_graph.json for the case."""
    try:
        with open(case.causal_graph_path) as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to load causal_graph for {case.name}: {e}")
        return {}


def _compute_difficulty(case: Case) -> dict:
    """Compute difficulty fields for dashboard distribution plots.

    Returns dict with: spl, n_svc, n_edge, fault_type, fault_category, root_cause_service.
    """
    return {
        "n_svc": case.n_svc,
        "n_alarm_svc": case.n_alarm_svc,
        "fault_type": case.primary_kind,
        "fault_category": case.chaos_family,
        "root_cause_service": case.root_services[0] if case.root_services else None,
        "hybrid": case.hybrid,
    }
