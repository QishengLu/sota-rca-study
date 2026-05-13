"""ClaudeCode eval agent — wraps legacy agent_runner.py (Claude Code CLI).

Note: ClaudeCode uses `claude -p` subprocess and stream-json events. The legacy
agent_runner.py parses stream-json into OpenAI-flat messages, including the
three-layer JSON fallback (parse → compress LLM → regex). Requires `claude`
CLI installed: `npm install -g @anthropic-ai/claude-code-cli`.
"""
from __future__ import annotations

from pathlib import Path

from sota_rca.legacy_agent import LegacySubprocessAgent, LegacyAgentConfig

_FW_DIR = Path(__file__).resolve().parent.parent.parent.parent  # frameworks/claudecode


class ClaudeCodeEvalAgent(LegacySubprocessAgent):
    @staticmethod
    def name() -> str:
        return "claudecode"

    @classmethod
    def _default_config(cls) -> LegacyAgentConfig:
        return LegacyAgentConfig(
            framework_name="claudecode",
            framework_dir=_FW_DIR,
            cmd=["uv", "run", "python", "agent_runner.py"],
            prompt_yaml=_FW_DIR / "src" / "claudecode_rca" / "prompts" / "agents" / "langgraph" / "rca.yaml",
            timeout=1800,
            multi_agent=False,
        )
