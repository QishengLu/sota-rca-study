"""LegacySubprocessAgent — aegis v3 BaseAgent wrapper around a stdin/stdout
agent_runner.py.

The 6 frameworks all carry their original agent_runner.py (which speaks
the legacy 6-field stdin / JSON stdout protocol). This wrapper:
1. Implements aegis v3 BaseAgent.run() signature
2. Reads canonical UTU_LLM_* env (already in os.environ by orchestrator)
3. Loads the framework's bit-identical rca.yaml prompts via PromptManager
4. Spawns the legacy agent_runner.py as subprocess
5. Converts OpenAI-flat trajectory → v3 Trajectory via converters
6. Wraps response + cost_metrics into AgentResult

Each framework's eval_agent.py can either subclass LegacySubprocessAgent
(minimum code, just declares cmd/cwd/converter) OR fully implement run()
in-process if the framework has been refactored.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Lazy v3 imports
try:
    from rcabench_platform.v3.sdk.llm_eval.agents.base_agent import BaseAgent, AgentResult  # type: ignore
    from rcabench_platform.v3.sdk.llm_eval.trajectory import Trajectory  # type: ignore
    _V3 = True
except ImportError:
    _V3 = False
    # Define minimal stand-ins so module is importable for tests
    class BaseAgent:  # type: ignore
        @staticmethod
        def name() -> str: ...
        async def run(self, incident: str, data_dir: str, **kwargs) -> Any: ...

    @dataclass
    class AgentResult:  # type: ignore
        response: str = ""
        trajectory: Any = None
        metadata: dict = field(default_factory=dict)

from .data.converters import (
    build_single_agent_trajectory,
    build_multi_agent_trajectory,
)
from .prompts.manager import PromptManager


@dataclass
class LegacyAgentConfig:
    """Per-framework configuration."""
    framework_name: str
    framework_dir: Path                                # frameworks/<name>
    cmd: list[str]                                     # e.g. ["uv", "run", "python", "agent_runner.py"]
    prompt_yaml: Path | None = None                    # if None, use sdk/sota_rca/prompts/rca.yaml
    timeout: int = 1800
    multi_agent: bool = False                          # True for mabc
    # Optional hook: transform stdout JSON before wrapping
    post_process: Callable[[dict], dict] | None = None


class LegacySubprocessAgent(BaseAgent):
    """aegis v3 BaseAgent that wraps a legacy stdin/stdout agent_runner.py."""

    config: LegacyAgentConfig

    def __init__(self, config: LegacyAgentConfig | None = None):
        if config is None:
            config = self._default_config()
        self.config = config

    @classmethod
    def _default_config(cls) -> LegacyAgentConfig:
        raise NotImplementedError("Subclass must provide _default_config() or pass config to __init__")

    @staticmethod
    def name() -> str:
        raise NotImplementedError

    def model_name(self) -> str | None:
        return os.environ.get("UTU_LLM_MODEL")

    # ------------------------------------------------------------
    # The core v3 BaseAgent contract
    # ------------------------------------------------------------

    async def run(self, incident: str, data_dir: str, **kwargs) -> AgentResult:
        """Run the framework's legacy agent_runner.py as subprocess, then
        convert its OpenAI-flat output to v3 Trajectory.
        """
        date_str = datetime.now().strftime("%Y-%m-%d")

        # 1. Load prompts (4-key bit-identical yaml)
        prompt_path = self.config.prompt_yaml or _default_prompt_path()
        prompts = PromptManager.get_prompts(prompt_path)

        agent_contract = self._get_agent_contract()

        rca_sp = prompts["RCA_ANALYSIS_SP"].format(date=date_str)
        rca_up = prompts["RCA_ANALYSIS_UP"].format(incident_description=incident)
        comp_sp = prompts["COMPRESS_FINDINGS_SP"].format(
            date=date_str, agent_contract=agent_contract
        )
        comp_up = prompts["COMPRESS_FINDINGS_UP"].format(incident_description=incident)

        # 2. Build legacy stdin payload (6 fields, matches old SOTA-agents schema)
        payload = {
            "question": incident,
            "system_prompt": rca_sp,
            "user_prompt": rca_up,
            "compress_system_prompt": comp_sp,
            "compress_user_prompt": comp_up,
            "data_dir": str(data_dir),
        }

        # 3. Spawn subprocess
        started = time.time()
        env = dict(os.environ)
        proc = await asyncio.create_subprocess_exec(
            *self.config.cmd,
            cwd=str(self.config.framework_dir),
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=json.dumps(payload).encode()),
                timeout=self.config.timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise

        elapsed = time.time() - started

        if proc.returncode != 0:
            err_text = stderr.decode(errors="replace")
            raise RuntimeError(
                f"[{self.config.framework_name}] subprocess rc={proc.returncode}: {err_text[-2000:]}"
            )

        # Last line of stdout = JSON result
        lines = stdout.decode(errors="replace").strip().splitlines()
        if not lines:
            raise RuntimeError(f"[{self.config.framework_name}] empty stdout")
        try:
            result_data = json.loads(lines[-1])
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"[{self.config.framework_name}] last stdout line not JSON: {lines[-1][:500]}"
            ) from e

        if self.config.post_process:
            result_data = self.config.post_process(result_data)

        # 4. Convert OpenAI-flat trajectory → v3 Trajectory
        traj = self._build_trajectory(result_data, rca_sp)

        # 5. Pack metadata (cost_metrics + trace_id)
        usage = result_data.get("usage", {}) or {}
        metadata = {
            "cost_metrics": {
                "total_tokens": usage.get("total_tokens", 0),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "token_source": "actual" if usage.get("total_tokens") else "estimated",
                "effective_rounds": self._count_effective_rounds(result_data.get("trajectory", [])),
                "time_cost": elapsed,
                "model": self.model_name(),
            },
            "trace_id": result_data.get("trace_id"),
            "framework": self.config.framework_name,
        }
        # Include any extra fields the agent emitted
        for k, v in result_data.items():
            if k not in ("output", "response", "trajectory", "usage", "trace_id"):
                metadata[k] = v

        return AgentResult(
            response=str(result_data.get("output", result_data.get("response", ""))),
            trajectory=traj,
            metadata=metadata,
        )

    # ------------------------------------------------------------
    # Hooks for subclasses
    # ------------------------------------------------------------

    def _build_trajectory(self, result_data: dict, system_prompt: str) -> Trajectory:
        """Convert result_data['trajectory'] (OpenAI flat) → v3 Trajectory."""
        flat = result_data.get("trajectory", [])
        if self.config.multi_agent:
            # Subclass should override; default: best-effort single trajectory
            return build_single_agent_trajectory(
                flat,
                agent_name=self.config.framework_name,
                system_prompt=system_prompt,
                metadata={},
            )
        return build_single_agent_trajectory(
            flat,
            agent_name=self.config.framework_name,
            system_prompt=system_prompt,
            metadata={},
        )

    def _get_agent_contract(self) -> str:
        """Return the schema contract injected into COMPRESS_FINDINGS_SP."""
        try:
            from rcabench_platform.v3.sdk.evaluation.v2 import get_agent_contract_prompt  # type: ignore
            return get_agent_contract_prompt()
        except ImportError:
            return _DEFAULT_AGENT_CONTRACT

    @staticmethod
    def _count_effective_rounds(flat_trajectory: list[dict]) -> int:
        return sum(
            1 for m in flat_trajectory
            if m.get("role") == "assistant" and m.get("tool_calls")
        )


def _default_prompt_path() -> Path:
    """Path to the canonical SDK-level rca.yaml (used when framework hasn't shipped its own)."""
    return Path(__file__).resolve().parent / "prompts" / "rca.yaml"


_DEFAULT_AGENT_CONTRACT = """
Output schema (strict JSON, no markdown):
{
  "nodes": [
    {"component": "<service|pod|namespace>", "state": "<state>", "fault_type": "<type>"}
  ],
  "edges": [
    {"from": "<component:state>", "to": "<component:state>"}
  ],
  "root_causes": ["<component:state>", ...]
}
""".strip()
