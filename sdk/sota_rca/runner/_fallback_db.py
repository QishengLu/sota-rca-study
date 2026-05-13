"""Fallback DB schema used when aegis v3 rcabench_platform is not installed.

Mirrors the relevant fields of v3 EvaluationSample for scaffolding/test use.
Production runtime always uses the real v3 schema.
"""
from __future__ import annotations

import os
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel, create_engine


class EvaluationSample(SQLModel, table=True):
    __tablename__ = "evaluation_data"

    id: int | None = Field(default=None, primary_key=True)
    dataset: str = ""
    dataset_index: int | None = None
    source: str = ""
    raw_question: str = ""
    augmented_question: str | None = None
    correct_answer: str | None = None

    # Rollout
    response: str | None = None
    trajectories: Any = Field(default=None, sa_column=Column(JSON))
    time_cost: float | None = None

    # Judge
    extracted_final_answer: str | None = None
    correct: bool | None = None
    reasoning: str | None = None

    # Meta
    exp_id: str = Field(default="", index=True)
    agent_type: str | None = Field(default=None, index=True)
    model_name: str | None = Field(default=None, index=True)
    stage: str = Field(default="init", index=True)
    meta: Any = Field(default=None, sa_column=Column(JSON))


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = os.environ.get("UTU_DB_URL", "sqlite:///./results/local.db")
        _engine = create_engine(url, echo=False)
        SQLModel.metadata.create_all(_engine)
    return _engine
