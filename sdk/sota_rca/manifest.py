"""Run manifest reader/writer — tracks per-cell status across a matrix run.

Located at {output_dir}/manifest.json. Source of truth for dashboard and
post-matrix scripts to know which cells finished, partial, failed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class CellStatus:
    exp_id: str
    framework: str
    model_alias: str
    started_at: str | None = None
    ended_at: str | None = None
    status: str = "pending"          # pending | running | partial_ok | done | error | skipped
    total: int = 0
    judged: int = 0
    errors: int = 0
    cost_usd: float | None = None
    log_dir: str | None = None
    error_msg: str | None = None


@dataclass
class RunManifest:
    run_id: str
    matrix_config_path: str
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: str | None = None
    cells: list[CellStatus] = field(default_factory=list)


def write_manifest(manifest: RunManifest, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    p = output_dir / "manifest.json"
    with open(p, "w") as f:
        json.dump(asdict(manifest), f, indent=2)
    # Update LATEST pointer
    latest = output_dir.parent / "LATEST"
    latest.write_text(str(output_dir.name))
    return p


def read_manifest(output_dir: Path) -> RunManifest:
    p = Path(output_dir) / "manifest.json"
    with open(p) as f:
        data = json.load(f)
    cells = [CellStatus(**c) for c in data.get("cells", [])]
    return RunManifest(
        run_id=data["run_id"],
        matrix_config_path=data["matrix_config_path"],
        started_at=data.get("started_at"),
        ended_at=data.get("ended_at"),
        cells=cells,
    )


def update_cell(manifest: RunManifest, exp_id: str, **kwargs: Any) -> None:
    """Update a cell's fields in-place."""
    for cell in manifest.cells:
        if cell.exp_id == exp_id:
            for k, v in kwargs.items():
                setattr(cell, k, v)
            return
    raise KeyError(f"Cell with exp_id {exp_id!r} not found in manifest")
