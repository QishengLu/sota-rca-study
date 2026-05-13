"""Matrix experiment config loader and cell expansion.

Reads configs/matrix/*.yaml + configs/models/catalog.yaml, expands into
list of (framework, model_spec, subset_spec) cells.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .model_env import ModelSpec, load_catalog

logger = logging.getLogger(__name__)


@dataclass
class SubsetSpec:
    kind: str                       # full | demo | filter | indices
    limit: int | None = None
    filters: dict[str, Any] = field(default_factory=dict)
    indices: list[int] | None = None
    demo_count: int = 20
    seed: int = 42


@dataclass
class ExecutionSpec:
    cell_concurrency: int = 2
    rollout_concurrency_max: int = 5
    timeout_per_sample: int = 600
    resume: bool = True
    failure_tolerance: float = 0.2
    retry_failed_samples: int = 1


@dataclass
class PostSpec:
    auto_judge: bool = True
    auto_intent_classify: bool = True
    auto_failure_tag: bool = False
    refresh_dashboard_cache: bool = True
    cache_target: str = "analysis_cache.json"


@dataclass
class MatrixConfig:
    version: int
    preset: str                     # full | demo
    exp_id_template: str
    output_dir: str
    frameworks: list[str]
    models: list[ModelSpec]
    subset: SubsetSpec
    execution: ExecutionSpec
    post: PostSpec
    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d-%H%M%S"))


@dataclass
class Cell:
    framework: str
    model: ModelSpec
    subset: SubsetSpec
    exp_id: str
    log_dir: Path


def load_matrix_config(path: str | Path, *, catalog_path: str | Path | None = None) -> MatrixConfig:
    """Load a matrix yaml + resolve model aliases against the catalog."""
    path = Path(path)
    with open(path) as f:
        raw = yaml.safe_load(f)

    catalog = load_catalog(catalog_path)

    # Resolve models from catalog by alias
    models: list[ModelSpec] = []
    for m in raw.get("models", []):
        alias = m["alias"]
        if alias not in catalog:
            raise KeyError(f"Model alias {alias!r} not in catalog (matrix yaml: {path})")
        models.append(catalog[alias])

    subset_raw = raw.get("subset", {})
    subset = SubsetSpec(
        kind=subset_raw.get("kind", "full"),
        limit=subset_raw.get("limit"),
        filters=subset_raw.get("filters", {}),
        indices=subset_raw.get("indices"),
        demo_count=subset_raw.get("demo_count", 20),
        seed=subset_raw.get("seed", 42),
    )

    exec_raw = raw.get("execution", {})
    execution = ExecutionSpec(
        cell_concurrency=exec_raw.get("cell_concurrency", 2),
        rollout_concurrency_max=exec_raw.get("rollout_concurrency_max", 5),
        timeout_per_sample=exec_raw.get("timeout_per_sample", 600),
        resume=exec_raw.get("resume", True),
        failure_tolerance=exec_raw.get("failure_tolerance", 0.2),
        retry_failed_samples=exec_raw.get("retry_failed_samples", 1),
    )

    post_raw = raw.get("post", {})
    post = PostSpec(
        auto_judge=post_raw.get("auto_judge", True),
        auto_intent_classify=post_raw.get("auto_intent_classify", True),
        auto_failure_tag=post_raw.get("auto_failure_tag", False),
        refresh_dashboard_cache=post_raw.get("refresh_dashboard_cache", True),
        cache_target=post_raw.get("cache_target", "analysis_cache.json"),
    )

    return MatrixConfig(
        version=raw.get("version", 1),
        preset=raw.get("preset", "full"),
        exp_id_template=raw.get("exp_id_template", "{framework}-{model_alias}-{subset_kind}"),
        output_dir=raw.get("output_dir", "results/matrix/{run_id}/"),
        frameworks=raw["frameworks"],
        models=models,
        subset=subset,
        execution=execution,
        post=post,
    )


def expand_cells(cfg: MatrixConfig) -> list[Cell]:
    """Return one Cell per (framework × model) combination."""
    out: list[Cell] = []
    for fw in cfg.frameworks:
        for m in cfg.models:
            exp_id = cfg.exp_id_template.format(
                framework=fw, model_alias=m.alias, subset_kind=cfg.subset.kind,
            )
            log_dir = Path(cfg.output_dir.format(run_id=cfg.run_id)) / exp_id / "logs"
            out.append(Cell(framework=fw, model=m, subset=cfg.subset, exp_id=exp_id, log_dir=log_dir))
    return out


def estimate_budget(cfg: MatrixConfig, samples_per_cell: int) -> dict[str, float]:
    """Crude budget estimate based on catalog pricing.

    Assumes ~30 LLM calls × 2000 in_tokens + 1000 out_tokens per sample.
    Conservative; real number depends on framework verbosity.
    """
    per_sample_in = 30 * 2000
    per_sample_out = 30 * 1000
    total = {"cells": len(cfg.frameworks) * len(cfg.models), "samples": samples_per_cell, "cost_usd": 0.0}
    for m in cfg.models:
        if not m.pricing:
            continue
        in_cost = (per_sample_in * samples_per_cell * len(cfg.frameworks)) / 1_000_000 * m.pricing.get("input", 0.0)
        out_cost = (per_sample_out * samples_per_cell * len(cfg.frameworks)) / 1_000_000 * m.pricing.get("output", 0.0)
        total["cost_usd"] += in_cost + out_cost
    return total
