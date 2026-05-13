"""Shared config for HARP (failure-taxonomy unification) DB-write scripts.

Keeps a single source of truth for:
- framework ↔ exp_id mapping
- framework ↔ labels.jsonl path + case_id field name
- merged/ artifact paths
"""
from pathlib import Path

DB_URL = "postgresql://postgres:postgres@localhost:5433/SOTA-Agents"

ROOT = Path("analysis/3-failure-modes")
MERGED = ROOT / "merged"

# agent_key → (exp_id, labels_path, case_id_field, workspace_dir)
FRAMEWORKS = {
    "aiq": (
        "aiq-qwen3.5-plus",
        ROOT / "2-by-framework/aiq-qwen3.5-plus/v1/labels.jsonl",
        "dataset_index",
        ROOT / "2-by-framework/aiq-qwen3.5-plus/v1",
    ),
    "claudecode": (
        "claudecode-qwen3.5-plus",
        ROOT / "2-by-framework/claudecode-qwen3.5-plus/v1/labels.jsonl",
        "case",
        ROOT / "2-by-framework/claudecode-qwen3.5-plus/v1",
    ),
    "sonnet": (
        "thinkdepthai-claude-sonnet-4.6",
        ROOT / "2-by-framework/thinkdepthai-claude-sonnet-4.6/v1/labels.jsonl",
        "dataset_index",
        ROOT / "2-by-framework/thinkdepthai-claude-sonnet-4.6/v1",
    ),
    "qwen": (
        "thinkdepthai-qwen3.5-plus",
        ROOT / "2-by-framework/thinkdepthai-qwen3.5-plus/v2/labels.jsonl",
        "case",
        ROOT / "2-by-framework/thinkdepthai-qwen3.5-plus/v1_harp",
    ),
}

# merged artifacts
D_PROJECTION = MERGED / "D_projection.jsonl"
D_TAXONOMY = MERGED / "D_taxonomy.md"
R_MERGE_TABLE = MERGED / "R_merge_table.jsonl"
UNIFIED_R = MERGED / "unified_R.md"
F_CATALOG_JSON = MERGED / "F_labels.jsonl"  # aggregate input for label_F_manual.py
PD_PROJECTION = MERGED / "PD_projection.jsonl"  # process-defects multi-label projection
PD_TAXONOMY = MERGED / "PD_taxonomy.md"


def labels_by_case_id(agent_key: str) -> dict:
    """Load labels.jsonl and key by case_id int."""
    import json
    _exp, path, field, _ws = FRAMEWORKS[agent_key]
    out = {}
    with path.open() as f:
        for line in f:
            row = json.loads(line)
            out[int(row[field])] = row
    return out
