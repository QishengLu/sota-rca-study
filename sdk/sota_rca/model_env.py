"""Model environment contract — UTU_LLM_* canonical vars + compat shims.

Single source of truth for which LLM agents use. Aligned 100% with
ThinkDepthAI's UTU_LLM_TYPE/MODEL/BASE_URL/API_KEY contract.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ModelSpec:
    alias: str
    name: str
    api_format: str          # openai | anthropic | google
    base_url: str
    api_key_env: str
    pricing: dict[str, float] | None = None
    notes: str = ""


def load_catalog(catalog_path: str | Path | None = None) -> dict[str, ModelSpec]:
    """Load model catalog from configs/models/catalog.yaml.

    Returns dict keyed by alias.
    """
    if catalog_path is None:
        # Default: repo's configs/models/catalog.yaml
        catalog_path = Path(__file__).resolve().parent.parent.parent.parent / "configs" / "models" / "catalog.yaml"
    catalog_path = Path(catalog_path)
    with open(catalog_path) as f:
        data = yaml.safe_load(f)

    out: dict[str, ModelSpec] = {}
    for entry in data.get("models", []):
        out[entry["alias"]] = ModelSpec(
            alias=entry["alias"],
            name=entry["name"],
            api_format=entry["api_format"],
            base_url=entry["base_url"],
            api_key_env=entry.get("api_key_env", ""),
            pricing=entry.get("pricing"),
            notes=entry.get("notes", ""),
        )
    return out


def resolve_model_alias(alias: str, catalog_path: str | Path | None = None) -> ModelSpec:
    """Look up a model alias in the catalog. Raises KeyError if not found."""
    catalog = load_catalog(catalog_path)
    if alias not in catalog:
        raise KeyError(
            f"Model alias {alias!r} not in catalog. "
            f"Available: {sorted(catalog.keys())}. "
            f"To add: edit configs/models/catalog.yaml"
        )
    return catalog[alias]


def build_llm_env(spec: ModelSpec, *, api_key: str | None = None) -> dict[str, str]:
    """Build env dict for a child process running with a given ModelSpec.

    Returns the canonical UTU_LLM_* vars + compat shims (OPENAI_*/ANTHROPIC_*/GOOGLE_*).

    If `api_key` is None, reads from os.environ[spec.api_key_env].
    """
    if api_key is None:
        api_key = os.environ.get(spec.api_key_env, "")
        if not api_key:
            raise RuntimeError(
                f"API key env var {spec.api_key_env!r} is empty. "
                f"Set it in .env or pass api_key= explicitly."
            )

    env: dict[str, str] = {
        # Canonical (read by all 6 agents)
        "UTU_LLM_TYPE": "chat.completions",
        "UTU_LLM_MODEL": spec.name,
        "UTU_LLM_BASE_URL": spec.base_url,
        "UTU_LLM_API_KEY": api_key,
        # Convenient extras
        "SOTA_RCA_MODEL_ALIAS": spec.alias,
        "SOTA_RCA_API_FORMAT": spec.api_format,
    }

    # Compat shims for SDKs that read provider-specific env vars
    env.update(write_compat_shims(spec, api_key))
    return env


def write_compat_shims(spec: ModelSpec, api_key: str) -> dict[str, str]:
    """Return provider-specific env shim dict based on api_format.

    All shims read the SAME api_key but route to the SDK that knows about
    that provider's auth header style.
    """
    fmt = spec.api_format.lower()
    shims: dict[str, str] = {}

    if fmt == "openai":
        shims.update({
            "OPENAI_API_KEY": api_key,
            "OPENAI_BASE_URL": spec.base_url,
        })
    elif fmt == "anthropic":
        shims.update({
            "ANTHROPIC_API_KEY": api_key,
            "ANTHROPIC_BASE_URL": spec.base_url,
            # Some tools still read OPENAI_* for misc HTTP — keep as fallback
            "OPENAI_API_KEY": api_key,
            "OPENAI_BASE_URL": spec.base_url,
        })
    elif fmt == "google":
        shims.update({
            "GOOGLE_API_KEY": api_key,
            "GOOGLE_BASE_URL": spec.base_url,
            "GOOGLE_GENERATIVE_AI_API_KEY": api_key,
        })
    return shims


def merge_env(base: dict[str, str] | None, overlay: dict[str, str]) -> dict[str, str]:
    """Merge two env dicts, overlay wins. Useful for orchestrator subprocess env."""
    out = dict(base or os.environ)
    out.update(overlay)
    return out
