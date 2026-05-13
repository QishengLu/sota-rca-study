"""ThinkDepthAI eval agent — wraps the legacy agent_runner.py via
LegacySubprocessAgent. Bit-identical prompt + UTU_LLM_* env contract.
"""
from __future__ import annotations

from pathlib import Path

from sota_rca.legacy_agent import LegacySubprocessAgent, LegacyAgentConfig

_FW_DIR = Path(__file__).resolve().parent.parent.parent.parent  # frameworks/thinkdepthai


class ThinkDepthAIEvalAgent(LegacySubprocessAgent):
    @staticmethod
    def name() -> str:
        return "thinkdepthai"

    @classmethod
    def _default_config(cls) -> LegacyAgentConfig:
        return LegacyAgentConfig(
            framework_name="thinkdepthai",
            framework_dir=_FW_DIR,
            cmd=["uv", "run", "python", "agent_runner.py"],
            prompt_yaml=_FW_DIR / "src" / "thinkdepthai" / "prompts" / "agents" / "langgraph" / "rca.yaml",
            timeout=1800,
            multi_agent=False,
        )
