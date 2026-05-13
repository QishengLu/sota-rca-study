#!/usr/bin/env python
"""run_matrix.py — Multi-framework × multi-model matrix orchestrator.

Usage:
    uv run python scripts/run_matrix.py configs/matrix/demo.yaml

Reads:
- A matrix yaml (configs/matrix/*.yaml)
- The model catalog (configs/models/catalog.yaml)

Per cell (framework × model):
1. Build env: UTU_LLM_* + provider shims (OPENAI_*/ANTHROPIC_*/GOOGLE_*)
2. Preprocess: insert init samples into PG (idempotent)
3. Rollout: invoke `rca llm-eval run` with the appropriate -a <framework>
4. On completion: trigger judge + analysis (via post_matrix.sh)

Resume: cells with all samples stage='judged' are auto-skipped.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Repo root → SDK path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk"))

from sota_rca.matrix import expand_cells, load_matrix_config, MatrixConfig, Cell  # noqa: E402
from sota_rca.manifest import RunManifest, CellStatus, write_manifest  # noqa: E402
from sota_rca.model_env import build_llm_env, merge_env  # noqa: E402
from sota_rca.data.ops_lite import iter_cases, DEFAULT_CACHE_DIR  # noqa: E402
from sota_rca.eval.preprocess import preprocess_exp  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("run_matrix")


async def run_cell(cfg: MatrixConfig, cell: Cell, sem: asyncio.Semaphore) -> CellStatus:
    """Execute one (framework, model) cell."""
    async with sem:
        status = CellStatus(
            exp_id=cell.exp_id,
            framework=cell.framework,
            model_alias=cell.model.alias,
            started_at=datetime.now().isoformat(),
            log_dir=str(cell.log_dir),
        )
        cell.log_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Build env
            env = build_llm_env(cell.model)
            env_full = merge_env(None, env)
            logger.info(f"[{cell.exp_id}] LLM_MODEL={cell.model.name} BASE_URL={cell.model.base_url}")

            # 2. Preprocess (insert init samples if not yet)
            if cell.subset.kind == "demo":
                from sota_rca.data.ops_lite import iter_cases
                cases = list(iter_cases(limit=cell.subset.demo_count))
            elif cell.subset.kind == "filter":
                fc = cell.subset.filters.get("fault_category")
                cases = list(iter_cases(fault_categories=fc, limit=cell.subset.limit))
            else:
                cases = list(iter_cases(limit=cell.subset.limit))

            n_inserted = preprocess_exp(
                exp_id=cell.exp_id,
                agent_type=cell.framework,
                model_name=cell.model.name,
                cases=cases,
            )
            status.total = len(cases)
            logger.info(f"[{cell.exp_id}] preprocessed: {n_inserted} new / {len(cases)} total")

            # 3. Rollout via aegis v3 CLI
            log_file = cell.log_dir / "rollout.log"
            cmd = [
                "uv", "run", "rca", "llm-eval", "run",
                "--exp-id", cell.exp_id,
                "-a", cell.framework,
                "--max-concurrency", str(cfg.execution.rollout_concurrency_max),
                "--timeout", str(cfg.execution.timeout_per_sample),
            ]
            logger.info(f"[{cell.exp_id}] starting rollout: {' '.join(cmd)}")
            with open(log_file, "w") as lf:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(REPO_ROOT),
                    env=env_full,
                    stdout=lf,
                    stderr=asyncio.subprocess.STDOUT,
                )
                rc = await proc.wait()

            if rc != 0:
                status.status = "error"
                status.error_msg = f"rollout exited with code {rc}; see {log_file}"
                logger.error(status.error_msg)
            else:
                status.status = "done"
                logger.info(f"[{cell.exp_id}] rollout done")

        except Exception as e:  # noqa: BLE001
            status.status = "error"
            status.error_msg = str(e)
            logger.exception(f"[{cell.exp_id}] cell failed: {e}")

        status.ended_at = datetime.now().isoformat()
        return status


async def main_async(config_path: Path) -> int:
    cfg = load_matrix_config(config_path)
    cells = expand_cells(cfg)
    logger.info(f"Run ID: {cfg.run_id}")
    logger.info(f"Cells: {len(cells)}")

    output_dir = REPO_ROOT / cfg.output_dir.format(run_id=cfg.run_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = RunManifest(
        run_id=cfg.run_id,
        matrix_config_path=str(config_path),
        cells=[CellStatus(
            exp_id=c.exp_id,
            framework=c.framework,
            model_alias=c.model.alias,
            log_dir=str(c.log_dir),
        ) for c in cells],
    )
    write_manifest(manifest, output_dir)

    sem = asyncio.Semaphore(cfg.execution.cell_concurrency)
    tasks = [run_cell(cfg, c, sem) for c in cells]
    statuses = await asyncio.gather(*tasks, return_exceptions=True)

    # Update manifest with results
    manifest.cells = [s for s in statuses if isinstance(s, CellStatus)]
    manifest.ended_at = datetime.now().isoformat()
    write_manifest(manifest, output_dir)

    # Summary
    n_done = sum(1 for s in manifest.cells if s.status == "done")
    n_err = sum(1 for s in manifest.cells if s.status == "error")
    logger.info(f"Matrix run complete: {n_done} done / {n_err} errors / {len(cells)} total")
    logger.info(f"Manifest: {output_dir / 'manifest.json'}")

    if cfg.post.auto_judge or cfg.post.auto_intent_classify or cfg.post.refresh_dashboard_cache:
        logger.info("Triggering post-matrix pipeline...")
        post_script = REPO_ROOT / "scripts" / "post_matrix.sh"
        if post_script.exists():
            subprocess.run(["bash", str(post_script), cfg.run_id], cwd=str(REPO_ROOT))

    return 0 if n_err == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Multi-framework × multi-model matrix orchestrator")
    ap.add_argument("config", type=Path, help="Path to matrix yaml")
    args = ap.parse_args()
    sys.exit(asyncio.run(main_async(args.config)))


if __name__ == "__main__":
    main()
