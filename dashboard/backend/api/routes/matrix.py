"""Matrix view endpoint — framework × model comparison.

GET /api/v1/matrix/{run_id}    — return all cells for one matrix run
GET /api/v1/matrix/leaderboard — aggregate leaderboard across runs

Data sourced from:
- results/matrix/{run_id}/manifest.json  (cell statuses)
- evaluation_data PG table               (per-sample metrics)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()

# Repo root is 4 levels up from this file: backend/api/routes/matrix.py
_REPO_ROOT = Path(__file__).resolve().parents[4]
_MATRIX_RESULTS = _REPO_ROOT / "results" / "matrix"


@router.get("/matrix/runs")
def list_runs() -> dict[str, Any]:
    """List all available matrix runs."""
    if not _MATRIX_RESULTS.exists():
        return {"runs": []}
    runs = []
    for d in sorted(_MATRIX_RESULTS.iterdir(), reverse=True):
        if d.is_dir() and (d / "manifest.json").exists():
            try:
                with open(d / "manifest.json") as f:
                    m = json.load(f)
                runs.append({
                    "run_id": m["run_id"],
                    "started_at": m.get("started_at"),
                    "ended_at": m.get("ended_at"),
                    "n_cells": len(m.get("cells", [])),
                    "n_done": sum(1 for c in m.get("cells", []) if c.get("status") == "done"),
                })
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Skipping malformed manifest at {d}: {e}")
    return {"runs": runs}


@router.get("/matrix/latest")
def get_latest_run() -> dict[str, Any]:
    """Return the matrix view of the latest run (LATEST pointer)."""
    latest_file = _MATRIX_RESULTS / "LATEST"
    if not latest_file.exists():
        raise HTTPException(404, "No matrix run found")
    run_id = latest_file.read_text().strip()
    return get_run(run_id)


@router.get("/matrix/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    """Return cells + per-cell aggregate metrics for one run."""
    manifest_path = _MATRIX_RESULTS / run_id / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(404, f"Run {run_id} not found")

    with open(manifest_path) as f:
        manifest = json.load(f)

    cells = manifest.get("cells", [])
    framework_set = sorted({c["framework"] for c in cells})
    model_set = sorted({c["model_alias"] for c in cells})

    # Per-cell metrics (queries PG by exp_id)
    cells_with_metrics = []
    for c in cells:
        metrics = _cell_metrics(c["exp_id"])
        cells_with_metrics.append({**c, "metrics": metrics})

    return {
        "run_id": run_id,
        "started_at": manifest.get("started_at"),
        "ended_at": manifest.get("ended_at"),
        "frameworks": framework_set,
        "model_aliases": model_set,
        "cells": cells_with_metrics,
    }


@router.get("/matrix/leaderboard")
def leaderboard() -> dict[str, Any]:
    """Cross-run aggregate leaderboard: best (framework, model) for each metric."""
    # Aggregate over all judged samples in DB grouped by (agent_type, model_name)
    from sota_rca.utils.sqlmodel_utils import SQLModelUtils  # lazy import
    from sqlmodel import Session, select, text

    engine = SQLModelUtils.get_engine()
    rows = []
    with Session(engine) as session:
        result = session.exec(text("""
            SELECT
                agent_type,
                model_name,
                exp_id,
                COUNT(*) AS n_total,
                SUM(CASE WHEN correct THEN 1 ELSE 0 END) AS n_correct,
                ROUND(AVG(CASE WHEN correct THEN 1.0 ELSE 0.0 END) * 100, 1) AS ac_at_1,
                AVG((meta->'graph_metrics'->'primary'->>'node_f1')::float) AS avg_node_f1,
                AVG((meta->'cost_metrics'->>'total_tokens')::int) AS avg_total_tokens
            FROM evaluation_data
            WHERE stage = 'judged'
            GROUP BY agent_type, model_name, exp_id
            ORDER BY ac_at_1 DESC
        """))
        for r in result:
            rows.append({
                "agent_type": r[0],
                "model_name": r[1],
                "exp_id": r[2],
                "n_total": r[3],
                "n_correct": r[4],
                "ac_at_1": float(r[5] or 0),
                "avg_node_f1": float(r[6] or 0),
                "avg_total_tokens": float(r[7] or 0),
            })
    return {"leaderboard": rows}


def _cell_metrics(exp_id: str) -> dict[str, Any]:
    """Query PG for per-cell aggregate metrics."""
    try:
        from sota_rca.utils.sqlmodel_utils import SQLModelUtils
        from sqlmodel import Session, text
        engine = SQLModelUtils.get_engine()
        with Session(engine) as session:
            r = session.exec(text("""
                SELECT
                    COUNT(*) AS n_total,
                    SUM(CASE WHEN stage='judged' THEN 1 ELSE 0 END) AS n_judged,
                    SUM(CASE WHEN correct THEN 1 ELSE 0 END) AS n_correct,
                    AVG((meta->'graph_metrics'->'primary'->>'node_f1')::float) AS avg_node_f1,
                    AVG((meta->'cost_metrics'->>'total_tokens')::int) AS avg_total_tokens
                FROM evaluation_data
                WHERE exp_id = :eid
            """), {"eid": exp_id}).first()
        if r is None:
            return {}
        return {
            "n_total": r[0],
            "n_judged": r[1] or 0,
            "n_correct": r[2] or 0,
            "ac_at_1": round((r[2] or 0) / r[0] * 100, 1) if r[0] else 0,
            "avg_node_f1": round(float(r[3] or 0), 3),
            "avg_total_tokens": int(r[4] or 0),
        }
    except Exception as e:  # noqa: BLE001
        logger.warning(f"_cell_metrics failed for {exp_id}: {e}")
        return {}
