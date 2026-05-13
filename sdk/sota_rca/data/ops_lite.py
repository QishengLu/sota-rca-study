"""ops-lite dataset loader — HuggingFace download + local cache + sha256 verify.

The dataset is `anon-ops/ops-lite` (or `lincyaw/openrca2-lite-v3` mirror).
500 cases, 4.13 GB. Cached to ~/.cache/sota-rca/ops-lite by default.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

DEFAULT_DATASET_NAME = "anon-ops/ops-lite"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "sota-rca" / "ops-lite"


@dataclass
class Case:
    """A single ops-lite case."""
    name: str
    data_dir: Path                # Local path to cases/{name}/
    chaos_family: str
    primary_kind: str
    subtypes: list[str]
    root_services: list[str]
    n_svc: int
    n_alarm_svc: int
    hybrid: bool
    has_kill_leg: bool
    system: str                   # ts | hs | otel-demo
    raw_manifest: dict            # original manifest dict

    @property
    def injection_json_path(self) -> Path:
        return self.data_dir / "injection.json"

    @property
    def causal_graph_path(self) -> Path:
        return self.data_dir / "causal_graph.json"

    @property
    def parquet_files(self) -> list[Path]:
        return sorted(self.data_dir.glob("*.parquet"))

    def synthesize_incident_description(self) -> str:
        """Compose a free-text incident_description from manifest fields.

        Modeled after the kind of text agents have seen in legacy rcabench.
        """
        from .incident_synth import build_incident_description
        return build_incident_description(self)


def download_dataset(
    dataset_name: str = DEFAULT_DATASET_NAME,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    *,
    force: bool = False,
) -> Path:
    """Download ops-lite from HuggingFace to cache_dir.

    Returns the path to the local cache directory.
    """
    cache_dir = Path(cache_dir).expanduser().resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = cache_dir / "manifest.jsonl"
    if manifest_path.exists() and not force:
        logger.info(f"Dataset already cached at {cache_dir}")
        return cache_dir

    try:
        from huggingface_hub import snapshot_download  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "huggingface-hub not installed. Run: uv sync"
        ) from e

    logger.info(f"Downloading {dataset_name} to {cache_dir}...")
    snapshot_download(
        repo_id=dataset_name,
        repo_type="dataset",
        local_dir=str(cache_dir),
        local_dir_use_symlinks=False,
    )
    logger.info(f"Download complete: {cache_dir}")
    return cache_dir


def load_manifest(cache_dir: Path = DEFAULT_CACHE_DIR) -> list[dict]:
    """Load manifest.jsonl, return list of dicts."""
    cache_dir = Path(cache_dir).expanduser().resolve()
    mp = cache_dir / "manifest.jsonl"
    if not mp.exists():
        raise FileNotFoundError(
            f"manifest.jsonl not found at {mp}. "
            f"Run: uv run sota-rca data download"
        )
    out = []
    with open(mp) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def iter_cases(
    cache_dir: Path = DEFAULT_CACHE_DIR,
    *,
    fault_categories: list[str] | None = None,
    limit: int | None = None,
    indices: list[int] | None = None,
) -> Iterator[Case]:
    """Iterate over cases, optionally filtered.

    Args:
        fault_categories: filter by chaos_family
        limit: max number of cases
        indices: specific case indices (overrides filters)
    """
    cache_dir = Path(cache_dir).expanduser().resolve()
    manifest = load_manifest(cache_dir)

    if indices is not None:
        records = [manifest[i] for i in indices if 0 <= i < len(manifest)]
    else:
        records = manifest
        if fault_categories:
            records = [r for r in records if r.get("chaos_family") in fault_categories]
        if limit:
            records = records[:limit]

    for rec in records:
        data_dir = cache_dir / "cases" / rec["name"]
        if not data_dir.exists():
            logger.warning(f"Case dir missing: {data_dir}")
            continue
        yield Case(
            name=rec["name"],
            data_dir=data_dir,
            chaos_family=rec.get("chaos_family", "unknown"),
            primary_kind=rec.get("primary_kind", "unknown"),
            subtypes=rec.get("subtypes", []),
            root_services=rec.get("root_services", []),
            n_svc=rec.get("n_svc", 0),
            n_alarm_svc=rec.get("n_alarm_svc", 0),
            hybrid=rec.get("hybrid", False),
            has_kill_leg=rec.get("has_kill_leg", False),
            system=rec.get("system", "unknown"),
            raw_manifest=rec,
        )


def get_case(name: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> Case | None:
    """Get a single case by name."""
    for c in iter_cases(cache_dir):
        if c.name == name:
            return c
    return None


def compute_sha256(path: Path) -> str:
    """Compute sha256 of a file (for dataset integrity check)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_dataset(cache_dir: Path = DEFAULT_CACHE_DIR, *, check_sha: bool = False) -> bool:
    """Verify dataset integrity.

    Returns True if OK. With check_sha=True, also verifies parquet checksums
    against a (currently TODO) sha256 manifest.
    """
    cache_dir = Path(cache_dir).expanduser().resolve()
    if not cache_dir.exists():
        logger.error(f"Cache dir missing: {cache_dir}")
        return False
    manifest = load_manifest(cache_dir)
    missing = 0
    for rec in manifest:
        d = cache_dir / "cases" / rec["name"]
        if not d.exists():
            missing += 1
            if missing <= 5:
                logger.warning(f"Missing case: {d}")
    if missing:
        logger.error(f"{missing}/{len(manifest)} case dirs missing")
        return False
    logger.info(f"Verified {len(manifest)} cases at {cache_dir}")
    return True
