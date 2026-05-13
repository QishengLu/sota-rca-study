"""Difficulty metadata pre-populator — fills data.meta.difficulty.

Dashboard distribution plots need this populated; otherwise everything shows
'unknown'. Idempotent: re-runs OK.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from ..runner.db_writer import EvaluationSample, get_engine

logger = logging.getLogger(__name__)


def patch_difficulty_for_exp(exp_id: str, *, force: bool = False) -> int:
    """Walk all samples for exp_id and ensure meta.difficulty is populated."""
    engine = get_engine()
    n_patched = 0
    with Session(engine) as session:
        stmt = select(EvaluationSample).where(EvaluationSample.exp_id == exp_id)
        for s in session.exec(stmt):
            meta = s.meta or {}
            if not force and "difficulty" in meta and meta["difficulty"]:
                continue

            # preprocess.py already sets these — we just sanity check
            diff = {
                "n_svc": meta.get("n_svc", 0),
                "n_alarm_svc": meta.get("n_alarm_svc", 0),
                "fault_type": meta.get("primary_kind", "unknown"),
                "fault_category": meta.get("chaos_family", "unknown"),
                "root_cause_service": (meta.get("root_services") or [None])[0],
                "system": meta.get("system", "unknown"),
            }
            meta["difficulty"] = diff
            s.meta = meta
            flag_modified(s, "meta")
            session.add(s)
            n_patched += 1

        session.commit()

    logger.info(f"[{exp_id}] difficulty patched: {n_patched}")
    return n_patched
