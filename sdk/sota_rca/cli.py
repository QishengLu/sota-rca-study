"""`sota-rca` CLI entry-point.

Sub-commands:
    sota-rca data download    — Download ops-lite dataset
    sota-rca data verify      — Verify dataset integrity
    sota-rca matrix <yaml>    — Run a matrix experiment
    sota-rca dashboard        — Launch dashboard
    sota-rca doctor           — Environment check
    sota-rca preprocess       — Populate EvaluationSamples for an exp_id
    sota-rca rejudge          — Re-judge an exp_id
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)
data_app = typer.Typer(no_args_is_help=True)
app.add_typer(data_app, name="data", help="Dataset management")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sota-rca")


# ============================================================
# data sub-commands
# ============================================================

@data_app.command("download")
def data_download(
    dataset: str = typer.Option("anon-ops/ops-lite", help="HuggingFace dataset id"),
    cache_dir: str = typer.Option("", help="Override cache dir"),
    force: bool = typer.Option(False, help="Re-download even if cached"),
) -> None:
    """Download ops-lite dataset from HuggingFace."""
    from .data.ops_lite import DEFAULT_CACHE_DIR, download_dataset
    cdir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    download_dataset(dataset_name=dataset, cache_dir=cdir, force=force)
    typer.echo(f"Done. Cache: {cdir}")


@data_app.command("verify")
def data_verify(cache_dir: str = typer.Option("", help="Cache dir to verify")) -> None:
    """Verify dataset integrity."""
    from .data.ops_lite import DEFAULT_CACHE_DIR, verify_dataset
    cdir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    ok = verify_dataset(cdir)
    sys.exit(0 if ok else 1)


# ============================================================
# matrix
# ============================================================

@app.command("matrix")
def matrix_cmd(
    config: Path = typer.Argument(..., help="Path to matrix yaml"),
    frameworks: str = typer.Option("", help="Comma-separated override (e.g. thinkdepthai,aiq)"),
    models: str = typer.Option("", help="Comma-separated model aliases override"),
    subset: str = typer.Option("", help="Override subset kind: full | demo | filter"),
    dry_run: bool = typer.Option(False, help="Show plan, do not run"),
) -> None:
    """Run a matrix experiment."""
    from .matrix import expand_cells, load_matrix_config, estimate_budget

    cfg = load_matrix_config(config)
    # CLI overrides
    if frameworks:
        cfg.frameworks = [f.strip() for f in frameworks.split(",")]
    if models:
        from .model_env import load_catalog
        cat = load_catalog()
        cfg.models = [cat[a.strip()] for a in models.split(",")]
    if subset:
        cfg.subset.kind = subset

    cells = expand_cells(cfg)
    typer.echo(f"Run ID: {cfg.run_id}")
    typer.echo(f"Cells:  {len(cells)}")
    for c in cells:
        typer.echo(f"  {c.exp_id}  (framework={c.framework}, model={c.model.name})")

    if cfg.subset.limit:
        budget = estimate_budget(cfg, cfg.subset.limit)
        typer.echo(f"\nEstimated budget: ${budget['cost_usd']:.2f}  ({budget['samples']} samples × {budget['cells']} cells)")

    if dry_run:
        return

    # Hand off to scripts/run_matrix.py for actual execution
    import subprocess
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    cmd = ["uv", "run", "python", str(repo_root / "scripts" / "run_matrix.py"), str(config)]
    subprocess.run(cmd, check=True)


# ============================================================
# dashboard
# ============================================================

@app.command("dashboard")
def dashboard_cmd(
    mode: str = typer.Option("prod", help="prod | demo | dev"),
    port: int = typer.Option(8001, help="HTTP port"),
) -> None:
    """Launch dashboard."""
    import subprocess
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    script = repo_root / "dashboard" / "run_dashboard.py"
    if not script.exists():
        typer.echo(f"Dashboard launcher not found at {script}", err=True)
        sys.exit(1)
    subprocess.run(["uv", "run", "python", str(script), "--mode", mode, "--port", str(port)])


# ============================================================
# doctor / preprocess / rejudge
# ============================================================

@app.command("doctor")
def doctor_cmd() -> None:
    """Run environment check."""
    import subprocess
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    subprocess.run(["uv", "run", "python", str(repo_root / "infra" / "doctor.py")])


@app.command("preprocess")
def preprocess_cmd(
    exp_id: str = typer.Argument(...),
    agent_type: str = typer.Option(..., help="e.g. thinkdepthai"),
    model_name: str = typer.Option(..., help="e.g. claude-sonnet-4-6"),
    limit: int = typer.Option(0, help="Limit number of samples (0 = all)"),
) -> None:
    """Populate EvaluationSamples (stage='init') for an exp_id from ops-lite."""
    from .eval.preprocess import preprocess_exp
    n = preprocess_exp(
        exp_id=exp_id,
        agent_type=agent_type,
        model_name=model_name,
        limit=limit or None,
    )
    typer.echo(f"Inserted {n} samples for exp_id={exp_id}")


@app.command("rejudge")
def rejudge_cmd(
    exp_id: str = typer.Argument(...),
    redo_judged: bool = typer.Option(False, help="Also re-score already-judged samples"),
) -> None:
    """Re-judge an exp_id."""
    from .eval.rejudge import rejudge_exp
    stats = rejudge_exp(exp_id, redo_judged=redo_judged)
    typer.echo(f"{stats}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
