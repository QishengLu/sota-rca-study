"""Pydantic schemas for sample-related API responses."""

from typing import Any

from pydantic import BaseModel, Field


class SampleMetrics(BaseModel):
    """Metrics for a single sample."""

    root_cause_f1: float | None = None
    root_cause_precision: float | None = None
    root_cause_recall: float | None = None
    node_f1: float | None = None
    node_precision: float | None = None
    node_recall: float | None = None
    edge_f1: float | None = None
    edge_precision: float | None = None
    edge_recall: float | None = None
    path_reachability: bool | None = None


class SampleListItem(BaseModel):
    """Sample item for list view."""

    id: int
    exp_id: str
    model_name: str | None = None
    agent_type: str | None = None
    dataset_index: int | None = None
    datapack_name: str | None = None
    correct: bool | None = None
    time_cost: float | None = None
    fault_type: str | None = None
    fault_category: str | None = None
    root_cause_service: str | None = None
    spl: int | None = None
    n_svc: int | None = None
    n_edge: int | None = None
    metrics: SampleMetrics = Field(default_factory=SampleMetrics)


class SampleListResponse(BaseModel):
    """Paginated response for sample list."""

    items: list[SampleListItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 0


class TrajectoryItem(BaseModel):
    """A single item in the conversation trajectory."""

    role: str = Field(..., description="Role: user, assistant, or tool")
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class GraphNode(BaseModel):
    """A node in the causal graph."""

    id: str
    component: str
    state: list[str] = Field(default_factory=list)
    is_root_cause: bool = False
    match_status: str | None = None  # matched, missed, hallucinated


class GraphEdge(BaseModel):
    """An edge in the causal graph."""

    source: str
    target: str
    match_status: str | None = None  # matched, missed, hallucinated


class ParsedGraph(BaseModel):
    """Parsed causal graph from response."""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    root_causes: list[str] = Field(default_factory=list)


class DiagnosticInfoResponse(BaseModel):
    """Diagnostic information for graph matching."""

    matched_services: list[str] = Field(default_factory=list)
    missed_services: list[str] = Field(default_factory=list)
    hallucinated_services: list[str] = Field(default_factory=list)
    matched_service_edges: list[tuple[str, str]] = Field(default_factory=list)
    missed_service_edges: list[tuple[str, str]] = Field(default_factory=list)
    hallucinated_service_edges: list[tuple[str, str]] = Field(default_factory=list)


class ToolUsageStats(BaseModel):
    """Tool usage statistics."""

    total_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    tools_used: list[str] = Field(default_factory=list)


class SampleMeta(BaseModel):
    """Metadata for a sample."""

    ground_truth: list[str] = Field(default_factory=list)
    datapack_name: str | None = None
    graph_metrics: dict[str, Any] | None = None
    tool_usage: ToolUsageStats = Field(default_factory=ToolUsageStats)


class SampleDetail(BaseModel):
    """Detailed sample information."""

    id: int
    exp_id: str
    model_name: str | None = None
    agent_type: str | None = None
    dataset_index: int | None = None
    raw_question: str = ""
    augmented_question: str | None = None
    correct_answer: str | None = None
    response: str | None = None
    correct: bool | None = None
    time_cost: float | None = None
    reasoning: str | None = None
    trajectories: list[TrajectoryItem] = Field(default_factory=list)
    meta: SampleMeta = Field(default_factory=SampleMeta)
    parsed_response: ParsedGraph = Field(default_factory=ParsedGraph)
    ground_truth_graph: ParsedGraph = Field(default_factory=ParsedGraph)
    diagnostic: DiagnosticInfoResponse = Field(default_factory=DiagnosticInfoResponse)
    component_to_service: dict[str, str] = Field(default_factory=dict)
