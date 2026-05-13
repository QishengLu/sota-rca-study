"""Smoke test: SDK modules can be imported without errors."""
from __future__ import annotations

import pytest


def test_import_sdk():
    import sota_rca  # noqa: F401
    assert sota_rca.__version__


def test_import_trajectory_helpers():
    from sota_rca.data import trajectory  # noqa: F401
    from sota_rca.data.trajectory import (  # noqa: F401
        iter_messages,
        iter_messages_with_context,
        wrap_openai_flat_to_v3,
        count_effective_rounds,
        count_tool_calls,
        aggregate_token_count,
    )


def test_import_model_env():
    from sota_rca.model_env import (  # noqa: F401
        load_catalog,
        resolve_model_alias,
        build_llm_env,
        write_compat_shims,
    )


def test_import_tracker():
    from sota_rca.tracker import auto_install, UsageTracker, get_tracker  # noqa: F401


def test_import_matrix():
    from sota_rca.matrix import (  # noqa: F401
        load_matrix_config,
        expand_cells,
        MatrixConfig,
        Cell,
    )


def test_import_ops_lite():
    from sota_rca.data.ops_lite import (  # noqa: F401
        download_dataset,
        load_manifest,
        iter_cases,
        Case,
        DEFAULT_CACHE_DIR,
    )


def test_import_eval():
    from sota_rca.eval.preprocess import preprocess_exp  # noqa: F401
    from sota_rca.eval.rejudge import rejudge_exp  # noqa: F401
    from sota_rca.eval.difficulty import patch_difficulty_for_exp  # noqa: F401


def test_catalog_loads():
    """Catalog should have 12+ models."""
    from sota_rca.model_env import load_catalog
    cat = load_catalog()
    assert len(cat) >= 8
    assert "sonnet46" in cat
    assert "qwen36" in cat


def test_demo_yaml_loads():
    from pathlib import Path
    from sota_rca.matrix import load_matrix_config, expand_cells
    repo = Path(__file__).resolve().parent.parent
    cfg = load_matrix_config(repo / "configs" / "matrix" / "demo.yaml")
    cells = expand_cells(cfg)
    assert len(cells) >= 1
    assert cfg.preset == "demo"
