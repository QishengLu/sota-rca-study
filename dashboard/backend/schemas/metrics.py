"""Pydantic schemas for metrics-related API responses."""

from pydantic import BaseModel, Field


class RangeMinMax(BaseModel):
    """Min/max range for numeric filter."""

    min: int = 0
    max: int = 0


class FilterOptions(BaseModel):
    """Available filter options for the dashboard."""

    exp_ids: list[str] = Field(default_factory=list, description="Available experiment IDs")
    models: list[str] = Field(default_factory=list, description="Available model names")
    agent_types: list[str] = Field(default_factory=list, description="Available agent types")
    tags: list[str] = Field(default_factory=list, description="Available tags")
    fault_types: list[str] = Field(default_factory=list, description="Available fault types")
    fault_categories: list[str] = Field(
        default_factory=list, description="Available fault categories (6 coarse classes)"
    )
    spl_values: list[int] = Field(default_factory=list, description="Available SPL values")
    n_svc_range: RangeMinMax = Field(default_factory=RangeMinMax, description="N_svc min/max range")
    n_edge_range: RangeMinMax = Field(default_factory=RangeMinMax, description="N_edge min/max range")


class PrimaryMetricsResponse(BaseModel):
    """Primary metrics for evaluation."""

    root_cause_f1: float = Field(default=0.0, description="Root cause F1 score")
    root_cause_precision: float = Field(default=0.0, description="Root cause precision")
    root_cause_recall: float = Field(default=0.0, description="Root cause recall")
    node_f1: float = Field(default=0.0, description="Node F1 score")
    node_precision: float = Field(default=0.0, description="Node precision")
    node_recall: float = Field(default=0.0, description="Node recall")
    edge_f1: float = Field(default=0.0, description="Edge F1 score")
    edge_precision: float = Field(default=0.0, description="Edge precision")
    edge_recall: float = Field(default=0.0, description="Edge recall")
    path_reachability: float | None = Field(
        default=None, description="Path reachability rate (applicable samples only)"
    )


class ExperimentMetrics(BaseModel):
    """Metrics for a single experiment."""

    exp_id: str
    model_name: str | None = None
    agent_type: str | None = None
    total_samples: int = 0
    correct_count: int = 0
    accuracy: float = 0.0
    avg_time_cost: float = 0.0
    avg_tokens: float = 0.0
    avg_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    avg_rounds: float = 0.0
    metrics: PrimaryMetricsResponse = Field(default_factory=PrimaryMetricsResponse)


class DistributionItem(BaseModel):
    """Distribution item for charts."""

    name: str
    success: int = 0
    fail: int = 0
    total: int = 0
    accuracy: float = 0.0


class MetricsOverview(BaseModel):
    """Overall metrics overview for the dashboard."""

    total_samples: int = 0
    correct_count: int = 0
    accuracy: float = 0.0
    avg_time_cost: float = 0.0
    metrics: PrimaryMetricsResponse = Field(default_factory=PrimaryMetricsResponse)
    by_experiment: list[ExperimentMetrics] = Field(default_factory=list)
    by_fault_type: list[DistributionItem] = Field(default_factory=list)
    by_root_cause_service: list[DistributionItem] = Field(default_factory=list)
    by_fault_category: list[DistributionItem] = Field(default_factory=list)
    by_spl: list[DistributionItem] = Field(default_factory=list)
    by_n_svc: list[DistributionItem] = Field(default_factory=list)
    by_n_edge: list[DistributionItem] = Field(default_factory=list)
