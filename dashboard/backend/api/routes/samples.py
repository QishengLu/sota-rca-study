"""Samples API endpoints."""

import json
import logging
import math
import re
from pathlib import Path
from typing import Annotated, Any

from api.deps import get_db
from api.utils import get_difficulty_from_meta, parse_json_field, safe_query
from fastapi import APIRouter, Depends, HTTPException, Query
from schemas.sample import (
    DiagnosticInfoResponse,
    GraphEdge,
    GraphNode,
    ParsedGraph,
    SampleDetail,
    SampleListItem,
    SampleListResponse,
    SampleMeta,
    SampleMetrics,
    ToolUsageStats,
    TrajectoryItem,
)
from sqlmodel import Session

logger = logging.getLogger(__name__)

DBSession = Annotated[Session, Depends(get_db)]

router = APIRouter()


def extract_metrics(meta: dict[str, Any] | None) -> SampleMetrics:
    """Extract primary metrics from meta field."""
    if not meta:
        return SampleMetrics()
    graph_metrics = meta.get("graph_metrics", {})
    primary = graph_metrics.get("primary", {})
    pr = primary.get("path_reachability")
    return SampleMetrics(
        root_cause_f1=primary.get("root_cause_f1"),
        root_cause_precision=primary.get("root_cause_precision"),
        root_cause_recall=primary.get("root_cause_recall"),
        node_f1=primary.get("node_f1"),
        node_precision=primary.get("node_precision"),
        node_recall=primary.get("node_recall"),
        edge_f1=primary.get("edge_f1"),
        edge_precision=primary.get("edge_precision"),
        edge_recall=primary.get("edge_recall"),
        path_reachability=bool(pr) if pr is not None else None,
    )


def parse_trajectories(trajectories_str: str | list | None) -> list[TrajectoryItem]:
    """Parse trajectories JSON string or list into list of TrajectoryItem."""
    if not trajectories_str:
        return []

    try:
        # Handle both SQLite (string) and PostgreSQL (list)
        data = parse_json_field(trajectories_str)
        if data is None:
            return []
        items = []

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    # Format 1: {step, action, observation} - LangGraph agent format
                    if "step" in item and "observation" in item:
                        items.append(
                            TrajectoryItem(
                                role="assistant",
                                content=item.get("observation"),
                                tool_calls=None,
                                tool_call_id=None,
                                name=item.get("action"),
                            )
                        )
                    # Format 2: {role, content, tool_calls} - OpenAI format
                    elif "role" in item:
                        items.append(
                            TrajectoryItem(
                                role=item.get("role", "unknown"),
                                content=item.get("content"),
                                tool_calls=item.get("tool_calls"),
                                tool_call_id=item.get("tool_call_id"),
                                name=item.get("name"),
                            )
                        )
            return items
        elif isinstance(data, dict):
            # Format 3: {agent_name: [messages]} - Orchestra format
            for agent_name, messages in data.items():
                if isinstance(messages, list):
                    for msg in messages:
                        if isinstance(msg, dict):
                            items.append(
                                TrajectoryItem(
                                    role=msg.get("role", "unknown"),
                                    content=msg.get("content"),
                                    tool_calls=msg.get("tool_calls"),
                                    tool_call_id=msg.get("tool_call_id"),
                                    name=msg.get("name") or agent_name,
                                )
                            )
            return items
    except (json.JSONDecodeError, TypeError):
        pass

    return []


def compute_tool_usage(trajectories: list[TrajectoryItem]) -> ToolUsageStats:
    """Compute tool usage statistics from trajectories."""
    total_calls = 0
    success_count = 0
    failure_count = 0
    tools_used: set[str] = set()

    for item in trajectories:
        if item.tool_calls:
            for tool_call in item.tool_calls:
                total_calls += 1
                if isinstance(tool_call, dict):
                    func = tool_call.get("function", {})
                    tool_name = func.get("name", "unknown")
                    tools_used.add(tool_name)

        # Check for tool results
        if item.role == "tool":
            if item.content and "error" in item.content.lower():
                failure_count += 1
            else:
                success_count += 1

    return ToolUsageStats(
        total_calls=total_calls,
        success_count=success_count,
        failure_count=failure_count,
        tools_used=sorted(tools_used),
    )


def parse_graph_data(graph_data: dict[str, Any] | None, mark_root_causes: bool = True) -> ParsedGraph:
    """Parse causal graph from a dict structure.

    Args:
        graph_data: Dict containing nodes, edges, and root_causes.
        mark_root_causes: Whether to mark nodes as root causes.

    Returns:
        ParsedGraph with nodes, edges, and root_causes.
    """
    if not graph_data or not isinstance(graph_data, dict):
        return ParsedGraph()

    nodes = []
    edges = []
    root_causes = []

    # Parse nodes (skip loadgenerator — traffic generator, not part of SUT)
    for node_data in graph_data.get("nodes", []):
        if isinstance(node_data, dict):
            component = node_data.get("component", "")
            if component.lower() == "loadgenerator":
                continue
            state = node_data.get("state", [])
            if isinstance(state, (set, frozenset)):
                state = list(state)
            nodes.append(
                GraphNode(
                    id=component,
                    component=component,
                    state=state if isinstance(state, list) else [],
                    is_root_cause=False,
                )
            )

    # Parse edges (skip any involving loadgenerator)
    for edge_data in graph_data.get("edges", []):
        if isinstance(edge_data, dict):
            source = edge_data.get("source", "")
            target = edge_data.get("target", "")
            if source.lower() == "loadgenerator" or target.lower() == "loadgenerator":
                continue
            edges.append(
                GraphEdge(
                    source=source,
                    target=target,
                )
            )

    # Parse root causes
    node_map = {n.component: n for n in nodes}
    for rc_data in graph_data.get("root_causes", []):
        component = rc_data.get("component", "") if isinstance(rc_data, dict) else rc_data
        if component:
            root_causes.append(component)
            if mark_root_causes and component in node_map:
                node_map[component].is_root_cause = True

    return ParsedGraph(nodes=nodes, edges=edges, root_causes=root_causes)


def parse_graph_from_meta(meta: dict[str, Any] | None, key: str = "parsed_graph") -> ParsedGraph:
    """Parse causal graph from meta field."""
    if not meta:
        return ParsedGraph()
    return parse_graph_data(meta.get(key, {}))


def parse_graph_from_response(response_data: dict[str, Any] | None) -> ParsedGraph:
    """Parse causal graph from response field (agent's prediction)."""
    return parse_graph_data(response_data, mark_root_causes=True)


def _normalize_service_name(name: str) -> str:
    """Normalize service name for comparison.

    - Remove prefixes like 'service|', 'span|'
    - Convert to lowercase
    - Remove 'ts-' prefix
    - Remove hyphens
    """
    normalized = name.strip().lower()
    # Remove type prefixes
    if "|" in normalized:
        normalized = normalized.split("|", 1)[1]
    # Remove ts- prefix
    if normalized.startswith("ts-"):
        normalized = normalized[3:]
    # Remove hyphens
    normalized = normalized.replace("-", "")
    return normalized


def _find_best_matching_service(
    component: str,
    known_services: set[str],
) -> str | None:
    """Find the best matching service for a component using similarity detection.

    Strategy:
    1. Extract service name hints from the component (e.g., from URL paths or span names)
    2. Match against known services using normalized comparison

    Args:
        component: The component name (e.g., 'span|HTTP POST http://ts-ui-dashboard:8080/...')
        known_services: Set of known service names to match against

    Returns:
        The best matching service name, or None if no match found
    """
    if not component or not known_services:
        return None

    # Normalize known services for comparison
    # Build multiple lookup structures for different matching strategies
    normalized_to_original: dict[str, str] = {}
    # Extract core service name (e.g., "travel-plan" from "ts-travel-plan-service")
    core_name_to_original: dict[str, str] = {}

    for svc in known_services:
        normalized = _normalize_service_name(svc)
        normalized_to_original[normalized] = svc

        # Extract core name: ts-travel-plan-service -> travelplan
        core = svc.lower()
        if core.startswith("ts-"):
            core = core[3:]
        if core.endswith("-service"):
            core = core[:-8]
        core = core.replace("-", "")
        if core:
            core_name_to_original[core] = svc

    # Extract potential service name from component
    component_lower = component.lower()

    # Strategy 1: Check if any known service name appears in the component
    for normalized, original in normalized_to_original.items():
        # Check various forms of the service name
        service_variants = [
            original.lower(),  # ts-order-service
            original.lower().replace("-", ""),  # tsorderservice
            normalized,  # orderservice
        ]
        # Also check without ts- prefix
        if original.lower().startswith("ts-"):
            service_variants.append(original[3:].lower())  # order-service
            service_variants.append(original[3:].lower().replace("-", ""))  # orderservice

        for variant in service_variants:
            if variant and len(variant) > 3 and variant in component_lower:
                return original

    # Strategy 2: Check if core service name appears in component
    # This handles cases like "TravelPlanController" matching "ts-travel-plan-service"
    for core, original in core_name_to_original.items():
        if core and len(core) > 3 and core in component_lower.replace("-", ""):
            return original

    # Strategy 3: Extract service name from URL path patterns
    # e.g., "/api/v1/orderservice/..." -> order-service
    url_patterns = [
        r"/api/v\d+/([a-z]+)service/",  # /api/v1/orderservice/
        r"/api/v\d+/([a-z]+-[a-z]+)-service/",  # /api/v1/order-service/
        r"http://([a-z0-9-]+):\d+",  # http://ts-order-service:8080
    ]

    for pattern in url_patterns:
        match = re.search(pattern, component_lower)
        if match:
            extracted = match.group(1)
            # Try to match extracted name against known services
            extracted_normalized = extracted.replace("-", "")
            for normalized, original in normalized_to_original.items():
                if extracted_normalized == normalized or extracted in original.lower():
                    return original

    return None


def _get_service_for_component(
    component: str,
    component_to_service: dict[str, str],
    known_services: set[str],
) -> str:
    """Get service name for a component, using mapping or similarity matching.

    Args:
        component: The component name
        component_to_service: Direct mapping from component to service
        known_services: Set of known service names for fallback matching

    Returns:
        The service name (from mapping, similarity match, or original component)
    """
    # First try direct mapping
    if component in component_to_service:
        return component_to_service[component]

    # Try similarity matching
    matched_service = _find_best_matching_service(component, known_services)
    if matched_service:
        return matched_service

    # Fallback to original component
    return component


def _convert_edges_to_service_level(
    edges_data: list[dict[str, Any]],
    component_to_service: dict[str, str],
    known_services: set[str] | None = None,
) -> list[GraphEdge]:
    """Convert component-level edges to service-level edges and deduplicate.

    Args:
        edges_data: List of edge dicts with "source" and "target" keys (component level)
        component_to_service: Mapping from component names to service names
        known_services: Set of known service names for fallback similarity matching

    Returns:
        List of unique service-level GraphEdge objects
    """
    seen_edges: set[tuple[str, str]] = set()
    service_edges: list[GraphEdge] = []

    # Build known services set from mapping values if not provided
    if known_services is None:
        known_services = set(component_to_service.values())

    for edge_data in edges_data:
        if not isinstance(edge_data, dict):
            continue

        source_component = edge_data.get("source", "")
        target_component = edge_data.get("target", "")

        # Convert to service level using mapping with similarity fallback
        source_service = _get_service_for_component(source_component, component_to_service, known_services)
        target_service = _get_service_for_component(target_component, component_to_service, known_services)

        # Skip self-loops at service level
        if source_service == target_service:
            continue

        # Skip loadgenerator (traffic generator, not part of the system under test)
        if source_service.lower() == "loadgenerator" or target_service.lower() == "loadgenerator":
            continue

        edge_tuple = (source_service, target_service)
        if edge_tuple not in seen_edges:
            seen_edges.add(edge_tuple)
            service_edges.append(GraphEdge(source=source_service, target=target_service))

    return service_edges


def _convert_nodes_to_service_level(
    nodes_data: list[dict[str, Any]],
    component_to_service: dict[str, str],
    root_causes_components: list[str],
    known_services: set[str] | None = None,
) -> list[GraphNode]:
    """Convert component-level nodes to service-level nodes and deduplicate.

    Args:
        nodes_data: List of node dicts with "component" key
        component_to_service: Mapping from component names to service names
        root_causes_components: List of root cause component names
        known_services: Set of known service names for fallback similarity matching

    Returns:
        List of unique service-level GraphNode objects
    """
    seen_services: set[str] = set()
    service_nodes: list[GraphNode] = []

    # Build known services set from mapping values if not provided
    if known_services is None:
        known_services = set(component_to_service.values())

    # Build set of root cause services (with similarity matching)
    root_cause_services = {
        _get_service_for_component(rc, component_to_service, known_services) for rc in root_causes_components
    }

    for node_data in nodes_data:
        if not isinstance(node_data, dict):
            continue

        component = node_data.get("component", "")
        service = _get_service_for_component(component, component_to_service, known_services)

        # Skip loadgenerator
        if service.lower() == "loadgenerator":
            continue

        if service not in seen_services:
            seen_services.add(service)
            service_nodes.append(
                GraphNode(
                    id=service,
                    component=service,
                    state=[],
                    is_root_cause=service in root_cause_services,
                )
            )

    return service_nodes


def build_ground_truth_graph(data_meta: dict[str, Any] | None) -> tuple[ParsedGraph, dict[str, str]]:
    """Build ground truth graph from causal_graph.json file.

    The graph is converted to service-level (not component-level) to align with
    agent predictions which are typically at service granularity.

    Returns:
        Tuple of (ParsedGraph at service level, component_to_service mapping)
    """
    if not data_meta:
        return ParsedGraph(), {}

    # Get path to data directory
    # Try "path" first (from evaluation_data), then "source_data_dir" (from data table)
    data_path = data_meta.get("path", "") or data_meta.get("source_data_dir", "")
    ground_truth_services = data_meta.get("ground_truth", [])

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    root_causes = list(ground_truth_services) if isinstance(ground_truth_services, list) else []
    component_to_service: dict[str, str] = {}

    # Try to read causal_graph.json from data directory
    if data_path:
        causal_graph_path = Path(data_path).expanduser() / "causal_graph.json"
        if causal_graph_path.exists():
            try:
                with open(causal_graph_path) as f:
                    causal_graph = json.load(f)

                # Get component_to_service mapping
                component_to_service = causal_graph.get("component_to_service", {})

                # Build known services set for similarity matching
                known_services = set(component_to_service.values())

                # Parse root causes (component level)
                root_causes_components: list[str] = []
                for rc_data in causal_graph.get("root_causes", []):
                    if isinstance(rc_data, dict):
                        root_causes_components.append(rc_data.get("component", ""))
                    elif isinstance(rc_data, str):
                        root_causes_components.append(rc_data)

                # Convert root causes to service level (with similarity matching)
                root_causes = list(
                    {
                        _get_service_for_component(rc, component_to_service, known_services)
                        for rc in root_causes_components
                    }
                )

                # Convert nodes to service level
                nodes = _convert_nodes_to_service_level(
                    causal_graph.get("nodes", []),
                    component_to_service,
                    root_causes_components,
                    known_services,
                )

                # Convert edges to service level
                edges = _convert_edges_to_service_level(
                    causal_graph.get("edges", []),
                    component_to_service,
                    known_services,
                )

                return ParsedGraph(nodes=nodes, edges=edges, root_causes=root_causes), component_to_service
            except (json.JSONDecodeError, OSError):
                pass

    # Fallback: check if causal_graph is embedded in data_meta
    causal_graph = data_meta.get("causal_graph", {})
    if causal_graph:
        component_to_service = causal_graph.get("component_to_service", {})

        # Build known services set for similarity matching
        known_services = set(component_to_service.values())

        # Parse root causes (component level)
        root_causes_components = []
        for rc_data in causal_graph.get("root_causes", root_causes):
            if isinstance(rc_data, dict):
                root_causes_components.append(rc_data.get("component", ""))
            elif isinstance(rc_data, str):
                root_causes_components.append(rc_data)

        # Convert root causes to service level (with similarity matching)
        root_causes = list(
            {_get_service_for_component(rc, component_to_service, known_services) for rc in root_causes_components}
        )

        # Convert nodes to service level
        nodes = _convert_nodes_to_service_level(
            causal_graph.get("nodes", []),
            component_to_service,
            root_causes_components,
            known_services,
        )

        # Convert edges to service level
        edges = _convert_edges_to_service_level(
            causal_graph.get("edges", []),
            component_to_service,
            known_services,
        )

        return ParsedGraph(nodes=nodes, edges=edges, root_causes=root_causes), component_to_service

    # Final fallback: create nodes from ground_truth list only
    for rc in root_causes:
        nodes.append(
            GraphNode(
                id=rc,
                component=rc,
                state=[],
                is_root_cause=True,
            )
        )

    return ParsedGraph(nodes=nodes, edges=edges, root_causes=root_causes), component_to_service


def extract_diagnostic_info(meta: dict[str, Any] | None) -> DiagnosticInfoResponse:
    """Extract diagnostic info from meta."""
    if not meta:
        return DiagnosticInfoResponse()

    graph_metrics = meta.get("graph_metrics", {})
    diagnostic = graph_metrics.get("diagnostic", {})

    return DiagnosticInfoResponse(
        matched_services=diagnostic.get("matched_services", []),
        missed_services=diagnostic.get("missed_services", []),
        hallucinated_services=diagnostic.get("hallucinated_services", []),
        matched_service_edges=diagnostic.get("matched_service_edges", []),
        missed_service_edges=diagnostic.get("missed_service_edges", []),
        hallucinated_service_edges=diagnostic.get("hallucinated_service_edges", []),
    )


@router.get("/samples", response_model=SampleListResponse)
def get_samples(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    exp_id: str | None = Query(None, description="Filter by experiment ID"),
    model_name: str | None = Query(None, description="Filter by model name"),
    correct: bool | None = Query(None, description="Filter by correctness"),
    min_rc_f1: float | None = Query(None, ge=0, le=1, description="Minimum root cause F1"),
    max_rc_f1: float | None = Query(None, ge=0, le=1, description="Maximum root cause F1"),
    fault_type: str | None = Query(None, description="Filter by fault type"),
    fault_category: str | None = Query(None, description="Filter by fault category"),
    spl: int | None = Query(None, description="Filter by SPL value"),
    min_n_svc: int | None = Query(None, description="Minimum N_svc"),
    max_n_svc: int | None = Query(None, description="Maximum N_svc"),
    min_n_edge: int | None = Query(None, description="Minimum N_edge"),
    max_n_edge: int | None = Query(None, description="Maximum N_edge"),
    sort_by: str = Query("dataset_index", description="Sort field"),
    sort_order: str = Query("asc", description="Sort order (asc/desc)"),
    db: DBSession = None,
) -> SampleListResponse:
    """Get paginated list of samples with filtering."""
    # Build base query
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
    from api.deps import demo_exp_id_sql_constraint
    query += demo_exp_id_sql_constraint("e")
    params: dict[str, Any] = {}

    if exp_id:
        query += " AND e.exp_id = :exp_id"
        params["exp_id"] = exp_id

    if model_name:
        query += " AND e.model_name = :model_name"
        params["model_name"] = model_name

    if correct is not None:
        query += " AND e.correct = :correct"
        params["correct"] = correct

    rows = safe_query(db, query, params)

    # Post-process for metric filters and difficulty filters
    filtered_rows = []
    for row in rows:
        meta_str = row[6]
        data_meta_str = row[9]
        meta = parse_json_field(meta_str) or {}
        data_meta = parse_json_field(data_meta_str) or {}
        metrics = extract_metrics(meta)
        difficulty = get_difficulty_from_meta(data_meta)

        # Apply metric filters
        if min_rc_f1 is not None:
            if metrics.root_cause_f1 is None or metrics.root_cause_f1 < min_rc_f1:
                continue
        if max_rc_f1 is not None:
            if metrics.root_cause_f1 is None or metrics.root_cause_f1 > max_rc_f1:
                continue

        # Apply difficulty filters
        if fault_type and difficulty.get("fault_type") != fault_type:
            continue
        if fault_category and difficulty.get("fault_category") != fault_category:
            continue
        if spl is not None and difficulty.get("spl") != spl:
            continue
        if min_n_svc is not None:
            sample_n_svc = difficulty.get("n_svc")
            if sample_n_svc is None or sample_n_svc < min_n_svc:
                continue
        if max_n_svc is not None:
            sample_n_svc = difficulty.get("n_svc")
            if sample_n_svc is None or sample_n_svc > max_n_svc:
                continue
        if min_n_edge is not None:
            sample_n_edge = difficulty.get("n_edge")
            if sample_n_edge is None or sample_n_edge < min_n_edge:
                continue
        if max_n_edge is not None:
            sample_n_edge = difficulty.get("n_edge")
            if sample_n_edge is None or sample_n_edge > max_n_edge:
                continue

        datapack_name = meta.get("datapack_name")
        filtered_rows.append((row, meta, metrics, difficulty, datapack_name))

    # Sort
    sort_key_map = {
        "dataset_index": lambda x: x[0][4] or 0,
        "time_cost": lambda x: x[0][7] or 0,
        "correct": lambda x: x[0][5] or False,
        "root_cause_f1": lambda x: x[2].root_cause_f1 or 0,
        "node_f1": lambda x: x[2].node_f1 or 0,
        "edge_f1": lambda x: x[2].edge_f1 or 0,
        "spl": lambda x: x[3].get("spl") or 0,
        "n_svc": lambda x: x[3].get("n_svc") or 0,
        "n_edge": lambda x: x[3].get("n_edge") or 0,
    }
    sort_key = sort_key_map.get(sort_by, sort_key_map["dataset_index"])
    reverse = sort_order.lower() == "desc"
    filtered_rows.sort(key=sort_key, reverse=reverse)

    # Pagination
    total = len(filtered_rows)
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_rows = filtered_rows[start_idx:end_idx]

    # Build response items
    items = []
    for row, _, metrics, difficulty, datapack_name in page_rows:
        (
            sample_id,
            row_exp_id,
            row_model_name,
            agent_type,
            dataset_index,
            is_correct,
            meta_str,
            time_cost,
            tags_str,
            data_meta_str,
        ) = row

        data_meta = parse_json_field(data_meta_str) or {}
        ground_truth = data_meta.get("ground_truth", [])
        rc_service = ground_truth[0] if ground_truth else None

        items.append(
            SampleListItem(
                id=sample_id,
                exp_id=row_exp_id,
                model_name=row_model_name,
                agent_type=agent_type,
                dataset_index=dataset_index,
                datapack_name=datapack_name,
                correct=is_correct,
                time_cost=time_cost,
                fault_type=difficulty.get("fault_type"),
                fault_category=difficulty.get("fault_category"),
                root_cause_service=rc_service,
                spl=difficulty.get("spl"),
                n_svc=difficulty.get("n_svc"),
                n_edge=difficulty.get("n_edge"),
                metrics=metrics,
            )
        )

    return SampleListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/samples/{sample_id}", response_model=SampleDetail)
def get_sample_detail(
    sample_id: int,
    db: DBSession = None,
) -> SampleDetail:
    """Get detailed information for a single sample."""
    query = """
        SELECT
            e.id, e.exp_id, e.model_name, e.agent_type,
            e.dataset_index, e.raw_question, e.augmented_question,
            e.correct_answer, e.response, e.correct, e.time_cost,
            e.reasoning, e.trajectories, e.meta,
            d.meta as data_meta
        FROM evaluation_data e
        LEFT JOIN data d ON e.dataset_index = d."index" AND e.dataset = d.dataset
        WHERE e.id = :sample_id
    """

    rows = safe_query(db, query, {"sample_id": sample_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Sample not found")

    row = rows[0]

    (
        db_id,
        exp_id,
        model_name,
        agent_type,
        dataset_index,
        raw_question,
        augmented_question,
        correct_answer,
        response,
        correct,
        time_cost,
        reasoning,
        trajectories_str,
        meta_str,
        data_meta_str,
    ) = row

    meta = parse_json_field(meta_str) or {}
    data_meta = parse_json_field(data_meta_str) or {}

    # Parse response as the agent's predicted graph
    response_data = None
    if response:
        response_data = parse_json_field(response)

    # Parse trajectories
    trajectories = parse_trajectories(trajectories_str)

    # Compute tool usage
    tool_usage = compute_tool_usage(trajectories)

    # Build sample meta
    ground_truth = data_meta.get("ground_truth", [])
    datapack_name = data_meta.get("datapack_name")

    sample_meta = SampleMeta(
        ground_truth=ground_truth if isinstance(ground_truth, list) else [],
        datapack_name=datapack_name,
        graph_metrics=meta.get("graph_metrics"),
        tool_usage=tool_usage,
    )

    # Parse graphs - use response for prediction, fall back to meta if needed
    parsed_response = parse_graph_from_response(response_data)
    if not parsed_response.nodes and not parsed_response.edges:
        # Fallback to meta.parsed_graph if response parsing yields nothing
        parsed_response = parse_graph_from_meta(meta, "parsed_graph")
    ground_truth_graph, component_to_service = build_ground_truth_graph(data_meta)

    # Extract diagnostic info
    diagnostic = extract_diagnostic_info(meta)

    # Add match status to nodes and edges
    matched_services = set(diagnostic.matched_services)
    missed_services = set(diagnostic.missed_services)
    hallucinated_services = set(diagnostic.hallucinated_services)

    for node in parsed_response.nodes:
        if node.component in matched_services:
            node.match_status = "matched"
        elif node.component in hallucinated_services:
            node.match_status = "hallucinated"

    for node in ground_truth_graph.nodes:
        if node.component in matched_services:
            node.match_status = "matched"
        elif node.component in missed_services:
            node.match_status = "missed"

    matched_edges = {tuple(e) for e in diagnostic.matched_service_edges}
    missed_edges = {tuple(e) for e in diagnostic.missed_service_edges}
    hallucinated_edges = {tuple(e) for e in diagnostic.hallucinated_service_edges}

    for edge in parsed_response.edges:
        edge_tuple = (edge.source, edge.target)
        if edge_tuple in matched_edges:
            edge.match_status = "matched"
        elif edge_tuple in hallucinated_edges:
            edge.match_status = "hallucinated"

    for edge in ground_truth_graph.edges:
        edge_tuple = (edge.source, edge.target)
        if edge_tuple in matched_edges:
            edge.match_status = "matched"
        elif edge_tuple in missed_edges:
            edge.match_status = "missed"

    return SampleDetail(
        id=db_id,
        exp_id=exp_id,
        model_name=model_name,
        agent_type=agent_type,
        dataset_index=dataset_index,
        raw_question=raw_question or "",
        augmented_question=augmented_question,
        correct_answer=correct_answer,
        response=response,
        correct=correct,
        time_cost=time_cost,
        reasoning=reasoning,
        trajectories=trajectories,
        meta=sample_meta,
        parsed_response=parsed_response,
        ground_truth_graph=ground_truth_graph,
        diagnostic=diagnostic,
        component_to_service=component_to_service,
    )
