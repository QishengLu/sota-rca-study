"""OpenRCA eval agent — wraps legacy agent_runner.py.

Note: OpenRCA uses dual-layer Controller+Executor with IPython kernel. The
legacy agent_runner.py handles stdout isolation and root-cause regex fallback.
"""
from __future__ import annotations

from pathlib import Path

from sota_rca.legacy_agent import LegacySubprocessAgent, LegacyAgentConfig

_FW_DIR = Path(__file__).resolve().parent.parent.parent.parent  # frameworks/openrca


class OpenRCAEvalAgent(LegacySubprocessAgent):
    @staticmethod
    def name() -> str:
        return "openrca"

    @classmethod
    def _default_config(cls) -> LegacyAgentConfig:
        return LegacyAgentConfig(
            framework_name="openrca",
            framework_dir=_FW_DIR,
            # OpenRCA uses pip + Python 3.11+ (not uv) historically. We try uv first.
            cmd=["uv", "run", "--", "python", "agent_runner.py"],
            prompt_yaml=_FW_DIR / "src" / "openrca" / "prompts" / "agents" / "langgraph" / "rca.yaml",
            timeout=1800,
            multi_agent=False,
        )
