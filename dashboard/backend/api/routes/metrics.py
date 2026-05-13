"""Metrics overview API endpoint."""

import logging
import os
from typing import Annotated, Any

from api.deps import get_db
from api.utils import avg, get_difficulty_from_meta, parse_json_field, safe_query
from fastapi import APIRouter, Depends, Query
from schemas.metrics import (
    DistributionItem,
    ExperimentMetrics,
    MetricsOverview,
    PrimaryMetricsResponse,
)
from sqlmodel import Session


def _get_demo_exp_ids_constraint() -> str:
    """If in demo mode, return SQL IN clause to restrict exp_ids.
    Otherwise apply prod allowlist."""
    from api.deps import demo_exp_id_sql_constraint, get_allowed_exp_ids
    demo_c = demo_exp_id_sql_constraint("e")
    if demo_c:
        return demo_c
    allowed = get_allowed_exp_ids()
    if allowed:
        quoted = ", ".join(f"'{e}'" for e in allowed)
        return f" AND e.exp_id IN ({quoted})"
    return ""

logger = logging.getLogger(__name__)

DBSession = Annotated[Session, Depends(get_db)]

router = APIRouter()


def extract_metrics(meta: dict[str, Any] | None) -> dict[str, float | None]:
    """Extract primary metrics from meta field."""
    if not meta:
        return {}
    graph_metrics = meta.get("graph_metrics", {})
    primary = graph_metrics.get("primary", {})
    pr = primary.get("path_reachability")
    return {
        "root_cause_f1": primary.get("root_cause_f1"),
        "root_cause_precision": primary.get("root_cause_precision"),
        "root_cause_recall": primary.get("root_cause_recall"),
        "node_f1": primary.get("node_f1"),
        "node_precision": primary.get("node_precision"),
        "node_recall": primary.get("node_recall"),
        "edge_f1": primary.get("edge_f1"),
        "edge_precision": primary.get("edge_precision"),
        "edge_recall": primary.get("edge_recall"),
        "path_reachability": float(pr) if pr is not None else None,
    }


def _append_metric(values_dict: dict[str, list[float]], metrics: dict[str, float | None]) -> None:
    """Append non-None metrics to their respective lists.

    For path_reachability, treat None (no correct root cause) as 0.0 (False).
    """
    metric_keys = [
        ("root_cause_f1", "rc_f1"),
        ("root_cause_precision", "rc_precision"),
        ("root_cause_recall", "rc_recall"),
        ("node_f1", "node_f1"),
        ("node_precision", "node_precision"),
        ("node_recall", "node_recall"),
        ("edge_f1", "edge_f1"),
        ("edge_precision", "edge_precision"),
        ("edge_recall", "edge_recall"),
    ]
    for src_key, dst_key in metric_keys:
        if metrics.get(src_key) is not None:
            values_dict[dst_key].append(metrics[src_key])

    # Special handling for path_reachability: treat None as 0.0 (False)
    pr = metrics.get("path_reachability")
    if pr is not None:
        values_dict["path_reachability"].append(float(pr))
    else:
        values_dict["path_reachability"].append(0.0)


def _build_primary_metrics(values: dict[str, list[float]]) -> PrimaryMetricsResponse:
    """Build PrimaryMetricsResponse from aggregated values."""
    return PrimaryMetricsResponse(
        root_cause_f1=avg(values.get("rc_f1", [])),
        root_cause_precision=avg(values.get("rc_precision", [])),
        root_cause_recall=avg(values.get("rc_recall", [])),
        node_f1=avg(values.get("node_f1", [])),
        node_precision=avg(values.get("node_precision", [])),
        node_recall=avg(values.get("node_recall", [])),
        edge_f1=avg(values.get("edge_f1", [])),
        edge_precision=avg(values.get("edge_precision", [])),
        edge_recall=avg(values.get("edge_recall", [])),
        path_reachability=avg(values.get("path_reachability", [])),
    )


def _new_metric_lists() -> dict[str, list[float]]:
    """Create a new dict with empty metric lists."""
    return {
        "rc_f1": [],
        "rc_precision": [],
        "rc_recall": [],
        "node_f1": [],
        "node_precision": [],
        "node_recall": [],
        "edge_f1": [],
        "edge_precision": [],
        "edge_recall": [],
        "path_reachability": [],
    }


@router.get("/metrics/overview", response_model=MetricsOverview)
def get_metrics_overview(
    exp_id: str | None = Query(None, description="Filter by experiment ID"),
    model_name: str | None = Query(None, description="Filter by model name"),
    tag: str | None = Query(None, description="Filter by tag"),
    fault_category: str | None = Query(None, description="Filter by fault category"),
    spl: int | None = Query(None, description="Filter by SPL value"),
    db: DBSession = None,
) -> MetricsOverview:
    """Get overview metrics with optional filtering."""
    # Build query with filters
    query = """
        SELECT
            e.id, e.exp_id, e.model_name, e.agent_type,
            e.dataset_index, e.correct, e.meta, e.time_cost,
            d.tags, d.meta as data_meta
        FROM evaluation_data e
        LEFT JOIN data d ON e.dataset_index = d."index" AND e.dataset = d.dataset
        WHERE e.stage = 'judged'
    """
    # Demo mode: restrict to demo exp_ids
    query += _get_demo_exp_ids_constraint()
    params: dict[str, Any] = {}

    if exp_id:
        query += " AND e.exp_id = :exp_id"
        params["exp_id"] = exp_id

    if model_name:
        query += " AND e.model_name = :model_name"
        params["model_name"] = model_name

    query += " ORDER BY e.exp_id, e.dataset_index"

    rows = safe_query(db, query, params)

    # Filter by tag if specified (needs post-processing since tags is JSON)
    if tag:
        filtered_rows = []
        for row in rows:
            tags_list = parse_json_field(row[8])
            if isinstance(tags_list, list) and tag in tags_list:
                filtered_rows.append(row)
        rows = filtered_rows

    # Filter by difficulty dimensions (needs post-processing since meta is JSON)
    if fault_category or spl is not None:
        filtered_rows = []
        for row in rows:
            data_meta = parse_json_field(row[9]) or {}
            difficulty = get_difficulty_from_meta(data_meta)
            if fault_category and difficulty.get("fault_category") != fault_category:
                continue
            if spl is not None and difficulty.get("spl") != spl:
                continue
            filtered_rows.append(row)
        rows = filtered_rows

    # Process results
    total_samples = len(rows)
    correct_count = 0
    time_costs: list[float] = []
    overall_metrics = _new_metric_lists()

    # Group by experiment
    exp_data: dict[str, dict[str, Any]] = {}

    # Group by fault type, root cause service, and difficulty dimensions
    fault_type_data: dict[str, dict[str, int]] = {}
    rc_service_data: dict[str, dict[str, int]] = {}
    fault_category_data: dict[str, dict[str, int]] = {}
    spl_data: dict[str, dict[str, int]] = {}
    n_svc_data: dict[str, dict[str, int]] = {}
    n_edge_data: dict[str, dict[str, int]] = {}

    for row in rows:
        (
            _sample_id,
            row_exp_id,
            row_model_name,
            agent_type,
            _dataset_index,
            correct,
            meta_str,
            time_cost,
            _tags_str,
            data_meta_str,
        ) = row

        # Parse meta (handle both SQLite string and PostgreSQL dict)
        meta = parse_json_field(meta_str) or {}
        data_meta = parse_json_field(data_meta_str) or {}

        # Count correct
        if correct:
            correct_count += 1

        # Time cost
        if time_cost is not None:
            time_costs.append(time_cost)

        # Extract and aggregate metrics
        metrics = extract_metrics(meta)
        _append_metric(overall_metrics, metrics)

        # Group by experiment
        if row_exp_id not in exp_data:
            exp_data[row_exp_id] = {
                "exp_id": row_exp_id,
                "model_name": row_model_name,
                "agent_type": agent_type,
                "total": 0,
                "correct": 0,
                "time_costs": [],
                "total_tokens": [],
                "cost_usds": [],
                "effective_rounds": [],
                "metrics": _new_metric_lists(),
            }
        exp_data[row_exp_id]["total"] += 1
        if correct:
            exp_data[row_exp_id]["correct"] += 1
        if time_cost is not None:
            exp_data[row_exp_id]["time_costs"].append(time_cost)
        _append_metric(exp_data[row_exp_id]["metrics"], metrics)

        # Cost metrics
        cost_metrics = meta.get("cost_metrics", {})
        if cost_metrics.get("total_tokens"):
            exp_data[row_exp_id]["total_tokens"].append(cost_metrics["total_tokens"])
        if cost_metrics.get("effective_rounds"):
            exp_data[row_exp_id]["effective_rounds"].append(cost_metrics["effective_rounds"])
        cost_usd = cost_metrics.get("cost_usd", {})
        if isinstance(cost_usd, dict) and cost_usd.get("total"):
            exp_data[row_exp_id]["cost_usds"].append(cost_usd["total"])

        # Extract fault type, root cause service, and difficulty from pre-computed meta
        ground_truth = data_meta.get("ground_truth", [])
        difficulty = get_difficulty_from_meta(data_meta)

        fault_type = difficulty.get("fault_type", "unknown")
        fault_cat = difficulty.get("fault_category", "unknown")
        sample_spl = difficulty.get("spl")
        sample_n_svc = difficulty.get("n_svc")
        sample_n_edge = difficulty.get("n_edge")

        rc_service = ground_truth[0] if ground_truth else "unknown"

        # Group by fault type
        if fault_type not in fault_type_data:
            fault_type_data[fault_type] = {"success": 0, "fail": 0}
        fault_type_data[fault_type]["success" if correct else "fail"] += 1

        # Group by root cause service
        if rc_service not in rc_service_data:
            rc_service_data[rc_service] = {"success": 0, "fail": 0}
        rc_service_data[rc_service]["success" if correct else "fail"] += 1

        # Group by fault category
        if fault_cat and fault_cat != "unknown":
            if fault_cat not in fault_category_data:
                fault_category_data[fault_cat] = {"success": 0, "fail": 0}
            fault_category_data[fault_cat]["success" if correct else "fail"] += 1

        # Group by SPL
        if sample_spl is not None:
            spl_key = str(sample_spl)
            if spl_key not in spl_data:
                spl_data[spl_key] = {"success": 0, "fail": 0}
            spl_data[spl_key]["success" if correct else "fail"] += 1

        # Group by N_svc
        if sample_n_svc is not None:
            n_svc_key = str(sample_n_svc)
            if n_svc_key not in n_svc_data:
                n_svc_data[n_svc_key] = {"success": 0, "fail": 0}
            n_svc_data[n_svc_key]["success" if correct else "fail"] += 1

        # Group by N_edge
        if sample_n_edge is not None:
            n_edge_key = str(sample_n_edge)
            if n_edge_key not in n_edge_data:
                n_edge_data[n_edge_key] = {"success": 0, "fail": 0}
            n_edge_data[n_edge_key]["success" if correct else "fail"] += 1

    # Build experiment metrics
    by_experiment = [
        ExperimentMetrics(
            exp_id=data["exp_id"],
            model_name=data["model_name"],
            agent_type=data["agent_type"],
            total_samples=data["total"],
            correct_count=data["correct"],
            accuracy=data["correct"] / data["total"] * 100 if data["total"] > 0 else 0,
            avg_time_cost=avg(data["time_costs"]),
            avg_tokens=avg(data["total_tokens"]),
            avg_cost_usd=avg(data["cost_usds"]),
            total_cost_usd=sum(data["cost_usds"]),
            avg_rounds=avg(data["effective_rounds"]),
            metrics=_build_primary_metrics(data["metrics"]),
        )
        for data in exp_data.values()
    ]

    # Build distribution items
    def build_distribution(data: dict[str, dict[str, int]], sort_by_name: bool = False) -> list[DistributionItem]:
        if sort_by_name:
            # Sort by name (useful for numeric keys like SPL=0, 1, 2...)
            sorted_items = sorted(
                data.items(), key=lambda x: (x[0].isdigit(), int(x[0]) if x[0].isdigit() else 0, x[0])
            )
        else:
            sorted_items = sorted(data.items(), key=lambda x: -(x[1]["success"] + x[1]["fail"]))
        return [
            DistributionItem(
                name=name,
                success=counts["success"],
                fail=counts["fail"],
                total=(total := counts["success"] + counts["fail"]),
                accuracy=counts["success"] / total * 100 if total > 0 else 0,
            )
            for name, counts in sorted_items
        ]

    return MetricsOverview(
        total_samples=total_samples,
        correct_count=correct_count,
        accuracy=correct_count / total_samples * 100 if total_samples > 0 else 0,
        avg_time_cost=avg(time_costs),
        metrics=_build_primary_metrics(overall_metrics),
        by_experiment=by_experiment,
        by_fault_type=build_distribution(fault_type_data),
        by_root_cause_service=build_distribution(rc_service_data),
        by_fault_category=build_distribution(fault_category_data),
        by_spl=build_distribution(spl_data, sort_by_name=True),
        by_n_svc=build_distribution(n_svc_data, sort_by_name=True),
        by_n_edge=build_distribution(n_edge_data, sort_by_name=True),
    )
