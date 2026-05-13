"""Database session dependency for FastAPI."""

import json
import os
from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session

from sota_rca.utils.sqlmodel_utils import SQLModelUtils

# Demo mode: restrict all DB queries to these exp_ids + common dataset_indexes
_DEMO_EXP_IDS: list[str] | None = None
_DEMO_DATASET_INDEXES: list[int] | None = None

# Prod allowlist: hide all other exp_ids from filter/cache/analysis.
# Empty list means no filtering (show all).
ALLOWED_EXP_IDS: list[str] = [
    "thinkdepthai-claude-sonnet-4.6",
    "thinkdepthai-qwen3.5-plus",
    "aiq-qwen3.5-plus",
    "taskweaver-qwen3.5-plus",
    "openrca-qwen3.5-plus",
    "claudecode-qwen3.5-plus",
    "mabc-qwen3.5-plus",
]


def get_allowed_exp_ids() -> list[str]:
    """Return prod allowlist of exp_ids. Empty list means allow all."""
    return ALLOWED_EXP_IDS


def init_demo_mode():
    """Initialize demo mode from ANALYSIS_CACHE_FILE env var.
    Also compute common dataset_indexes across all demo exp_ids."""
    global _DEMO_EXP_IDS, _DEMO_DATASET_INDEXES
    cache_file = os.environ.get("ANALYSIS_CACHE_FILE")
    if not cache_file:
        return
    p = Path(cache_file)
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text())
        _DEMO_EXP_IDS = sorted({k.split("|", 1)[1] for k in data if "|" in k})
    except Exception:
        return

    # Compute common dataset_indexes from DB
    if not _DEMO_EXP_IDS or len(_DEMO_EXP_IDS) < 2:
        return
    try:
        with SQLModelUtils.create_session() as session:
            from sqlalchemy import text
            # Find dataset_indexes that appear in ALL demo exp_ids (judged)
            intersect_parts = " INTERSECT ".join(
                f"SELECT dataset_index FROM evaluation_data WHERE exp_id = '{eid}' AND stage = 'judged'"
                for eid in _DEMO_EXP_IDS
            )
            result = session.execute(text(f"SELECT dataset_index FROM ({intersect_parts}) t ORDER BY dataset_index"))
            _DEMO_DATASET_INDEXES = [row[0] for row in result]
            import logging
            logging.getLogger(__name__).info(
                f"[Demo] {len(_DEMO_EXP_IDS)} exp_ids, {len(_DEMO_DATASET_INDEXES)} common cases"
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"[Demo] Failed to compute common cases: {e}")


def get_demo_exp_ids() -> list[str] | None:
    """Return demo exp_ids if in demo mode, else None."""
    return _DEMO_EXP_IDS


def demo_exp_id_sql_constraint(table_alias: str = "e") -> str:
    """Return SQL AND clause to restrict to demo exp_ids + common cases. Empty if not demo."""
    if _DEMO_EXP_IDS is None:
        return ""
    quoted = ", ".join(f"'{e}'" for e in _DEMO_EXP_IDS)
    constraint = f" AND {table_alias}.exp_id IN ({quoted})"
    if _DEMO_DATASET_INDEXES is not None:
        indexes = ", ".join(str(i) for i in _DEMO_DATASET_INDEXES)
        constraint += f" AND {table_alias}.dataset_index IN ({indexes})"
    return constraint


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting database session."""
    with SQLModelUtils.create_session() as session:
        yield session
