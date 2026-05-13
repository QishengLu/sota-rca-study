"""Common base for framework adapters.

Each agent in frameworks/<name>/ has its own `eval_agent.py` that subclasses
aegis v3 `BaseAgent`. This module provides shared helpers (e.g. subprocess
runner for legacy stdin/stdout fallback during transition).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from rcabench_platform.v3.sdk.llm_eval.agents.base_agent import BaseAgent, AgentResult  # type: ignore
    from rcabench_platform.v3.sdk.llm_eval.trajectory import Trajectory  # type: ignore
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
    BaseAgent = object  # type: ignore
    AgentResult = None  # type: ignore
    Trajectory = None  # type: ignore


async def run_subprocess_agent(
    cwd: Path,
    cmd: list[str],
    incident: str,
    data_dir: Path,
    env: dict[str, str] | None = None,
    timeout: int = 600,
) -> dict[str, Any]:
    """Run a legacy stdin/stdout agent as a subprocess.

    Used as fallback during migration. Production path is direct
    BaseAgent.run() via setuptools entry-point.

    Returns parsed last-line JSON.
    """
    payload = {
        "question": incident,
        "incident": incident,
        "data_dir": str(data_dir),
    }
    proc_env = dict(os.environ)
    if env:
        proc_env.update(env)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        env=proc_env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=json.dumps(payload).encode()),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise

    if proc.returncode != 0:
        raise RuntimeError(
            f"Subprocess failed (rc={proc.returncode}):\nstderr={stderr.decode(errors='replace')}"
        )

    last_line = stdout.decode(errors="replace").strip().splitlines()[-1]
    return json.loads(last_line)
