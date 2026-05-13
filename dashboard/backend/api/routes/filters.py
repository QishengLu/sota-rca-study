"""Filter options API endpoint."""

import json
import logging
import os
from pathlib import Path
from typing import Annotated

from api.deps import get_db
from api.utils import parse_datapack_name, parse_json_field, safe_query
from fastapi import APIRouter, Depends
from schemas.metrics import FilterOptions, RangeMinMax
from sqlmodel import Session

logger = logging.getLogger(__name__)

DBSession = Annotated[Session, Depends(get_db)]

router = APIRouter()


def _get_demo_exp_ids() -> list[str] | None:
    """Return demo exp_ids if in demo mode."""
    from api.deps import get_demo_exp_ids
    return get_demo_exp_ids()


@router.get("/filters", response_model=FilterOptions)
def get_filters(db: DBSession) -> FilterOptions:
    """Get available filter options from the database."""
    # Demo mode: only return exp_ids from cache file
    demo_eids = _get_demo_exp_ids()
    if demo_eids is not None:
        return FilterOptions(exp_ids=demo_eids)

    # Get distinct exp_ids
    exp_ids_result = safe_query(
        db, "SELECT DISTINCT exp_id FROM evaluation_data WHERE stage = 'judged' ORDER BY exp_id"
    )
    exp_ids = [row[0] for row in exp_ids_result if row[0]]

    # Prod allowlist: restrict to the 7 active experiments
    from api.deps import get_allowed_exp_ids
    allowed = get_allowed_exp_ids()
    if allowed:
        exp_ids = [e for e in exp_ids if e in allowed]

    # Get distinct model names
    models_result = safe_query(
        db,
        "SELECT DISTINCT model_name FROM evaluation_data "
        "WHERE stage = 'judged' AND model_name IS NOT NULL ORDER BY model_name",
    )
    models = [row[0] for row in models_result if row[0]]

    # Get distinct agent types
    agent_types_result = safe_query(
        db,
        "SELECT DISTINCT agent_type FROM evaluation_data "
        "WHERE stage = 'judged' AND agent_type IS NOT NULL ORDER BY agent_type",
    )
    agent_types = [row[0] for row in agent_types_result if row[0]]

    # Get all tags from data table (no DISTINCT on JSON type for PostgreSQL compatibility)
    tags_result = safe_query(db, "SELECT tags FROM data WHERE tags IS NOT NULL")
    tags_set: set[str] = set()
    for row in tags_result:
        tag_list = parse_json_field(row[0])
        if isinstance(tag_list, list):
            tags_set.update(tag_list)
    tags = sorted(tags_set)

    # Get fault types and difficulty metadata from evaluated data (JOIN ensures we only
    # show options that have actual evaluation results, not just dataset entries).
    # Note: avoid SELECT DISTINCT on JSON columns — PostgreSQL lacks equality operator for json type.
    difficulty_result = safe_query(
        db,
        "SELECT d.meta FROM evaluation_data e "
        'LEFT JOIN data d ON e.dataset_index = d."index" AND e.dataset = d.dataset '
        "WHERE e.stage = 'judged' AND d.meta IS NOT NULL",
    )
    fault_types_set: set[str] = set()
    fault_categories_set: set[str] = set()
    spl_set: set[int] = set()
    n_svc_values: list[int] = []
    n_edge_values: list[int] = []
    for row in difficulty_result:
        meta = parse_json_field(row[0])
        if isinstance(meta, dict):
            # Extract difficulty sub-field if present
            difficulty = meta.get("difficulty")
            if isinstance(difficulty, dict):
                ft = difficulty.get("fault_type", "")
                if ft and ft != "unknown":
                    fault_types_set.add(ft)
                fc = difficulty.get("fault_category", "")
                if fc and fc != "unknown":
                    fault_categories_set.add(fc)
                spl = difficulty.get("spl")
                if spl is not None:
                    spl_set.add(int(spl))
                n_svc = difficulty.get("n_svc")
                if n_svc is not None:
                    n_svc_values.append(int(n_svc))
                n_edge = difficulty.get("n_edge")
                if n_edge is not None:
                    n_edge_values.append(int(n_edge))
            else:
                # Fallback: parse from datapack_name
                datapack_name = meta.get("datapack_name", "")
                if datapack_name:
                    fault_type, _ = parse_datapack_name(datapack_name)
                    if fault_type and fault_type != "unknown":
                        fault_types_set.add(fault_type)
    fault_types = sorted(fault_types_set)
    fault_categories = sorted(fault_categories_set)
    spl_values = sorted(spl_set)
    n_svc_range = RangeMinMax(min=min(n_svc_values), max=max(n_svc_values)) if n_svc_values else RangeMinMax()
    n_edge_range = RangeMinMax(min=min(n_edge_values), max=max(n_edge_values)) if n_edge_values else RangeMinMax()

    return FilterOptions(
        exp_ids=exp_ids,
        models=models,
        agent_types=agent_types,
        tags=tags,
        fault_types=fault_types,
        fault_categories=fault_categories,
        spl_values=spl_values,
        n_svc_range=n_svc_range,
        n_edge_range=n_edge_range,
    )
