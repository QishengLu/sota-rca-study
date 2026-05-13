"""v4 middleware configuration.

Single source of truth for:
- master enable flag (ENABLE_MIDDLEWARE=1 + MIDDLEWARE_VERSION=v4)
- per-framework dimension pools and mid-check trigger thresholds
- opus-4.7 API connection
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Per-framework adapter parameters (D-5/D-6/D-7 outputs frozen 2026-04-22)
# Keep these in code (not env) because they are design-locked.
# ---------------------------------------------------------------------------

FRAMEWORK_ADAPTERS: dict[str, dict] = {
    # thinkdepthai: shared adapter for qwen3.5-plus + claude-sonnet-4.6
    # (per analysis/4-middleware/v4_thinkdepthai_qwen3.5_plus.md)
    "thinkdepthai-qwen3.5-plus": {
        "mid_check_round": 30,            # correct-case P25 anchor (D-7.5)
        "mid_primary_pool":   ["M6", "M7", "M9"],
        "mid_secondary_pool": ["M1", "M2", "M3", "M4", "M5", "M10"],
        "concl_primary_pool":   ["M1", "M2", "M3", "M4", "M5", "M8", "M10"],
        "concl_secondary_pool": ["M6", "M7", "M9"],
        "framework_hint": (
            "thinkdepthai-qwen3.5-plus: U1 (LoudnessAnchor) 41.9%, U2 (ChronicNoise) 24.8%, "
            "M5 (Silence-as-Health) 16.2% — all are HIGH-FREQ failure modes for this framework. "
            "Prioritise M1/M2/M5 when their evidence is present."
        ),
    },
    "thinkdepthai-claude-sonnet-4.6": {
        "mid_check_round": 22,
        "mid_primary_pool":   ["M6", "M7", "M9"],
        "mid_secondary_pool": ["M1", "M2", "M3", "M4", "M5", "M10"],
        "concl_primary_pool":   ["M1", "M2", "M3", "M4", "M5", "M8", "M10"],
        "concl_secondary_pool": ["M6", "M7", "M9"],
        "framework_hint": (
            "thinkdepthai-claude-sonnet-4.6: U3 (EdgeDirection / Output-Graph) 44.0% — HIGHEST. "
            "Prioritise M3 when reasoning text shows graph-direction errors."
        ),
    },
    # aiq / claudecode adapters can be added later (out of scope for first cut)
}


def framework_for(exp_id: str | None, model_name: str | None) -> str:
    """Resolve framework key from agent exp_id / model_name.

    Returns the matching FRAMEWORK_ADAPTERS key, falling back to qwen.
    """
    s = (exp_id or "") + " " + (model_name or "")
    s = s.lower()
    if "claude-sonnet" in s or "sonnet-4" in s:
        return "thinkdepthai-claude-sonnet-4.6"
    return "thinkdepthai-qwen3.5-plus"


# ---------------------------------------------------------------------------
# Master config
# ---------------------------------------------------------------------------


@dataclass
class V4Config:
    """v4 runtime configuration assembled from env vars + framework key.

    Env vars consulted:
    - ``ENABLE_MIDDLEWARE``  → master switch ("1" = on)
    - ``MIDDLEWARE_VERSION`` → must be "v4" to route to this code
    - ``MIDDLEWARE_FRAMEWORK`` → optional override; otherwise inferred
    - ``MIDDLEWARE_LLM_API_KEY`` / ``MIDDLEWARE_LLM_BASE_URL`` / ``MIDDLEWARE_LLM_MODEL``
      → opus-4.7 connection (defaults to shubiaobiao Coding Plan)
    - ``MIDDLEWARE_LLM_TEMPERATURE`` (default 0)
    - ``MW_MID_CHECK_ROUND`` → override per-framework threshold
    - ``MW_MAX_INTERVENTIONS`` (default 2) — caps mid+conclusion combined
    - ``MW_MATCH_THRESHOLD`` (default 0.7) — secondary dimension floor
    - ``MW_DIMENSION_CARDS_DIR`` → optional override of cards path
    """

    enabled: bool = field(
        default_factory=lambda: (
            os.environ.get("ENABLE_MIDDLEWARE", "0") == "1"
            and os.environ.get("MIDDLEWARE_VERSION", "v3").lower() == "v4"
        )
    )
    framework: str = field(
        default_factory=lambda: os.environ.get(
            "MIDDLEWARE_FRAMEWORK", "thinkdepthai-qwen3.5-plus"
        )
    )

    # opus-4.7 connection
    llm_api_key: str = field(
        default_factory=lambda: os.environ.get("MIDDLEWARE_LLM_API_KEY", "")
        or os.environ.get("OPENAI_API_KEY", "")
    )
    llm_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "MIDDLEWARE_LLM_BASE_URL", "https://api.shubiaobiao.cn/v1"
        )
    )
    # NOTE: design spec says claude-opus-4-7, but shubiaobiao currently lists
    # 4-7 as an INVALID_MODEL_ID. Latest callable opus is claude-opus-4-6.
    # User chose claude-sonnet-4-6 for cost/speed; override via env.
    llm_model: str = field(
        default_factory=lambda: os.environ.get(
            "MIDDLEWARE_LLM_MODEL", "claude-sonnet-4-6"
        )
    )
    llm_temperature: float = field(
        default_factory=lambda: float(
            os.environ.get("MIDDLEWARE_LLM_TEMPERATURE", "0")
        )
    )
    llm_max_tokens: int = field(
        default_factory=lambda: int(
            os.environ.get("MIDDLEWARE_LLM_MAX_TOKENS", "4000")
        )
    )

    # Behaviour knobs
    max_interventions: int = field(
        default_factory=lambda: int(
            os.environ.get("MW_MAX_INTERVENTIONS", "2")
        )
    )
    # NOTE: v4 design (D-3 revision of principle 7) explicitly removed any
    # hard score threshold. opus-4.7 decides triggered / primary / secondary
    # autonomously from the natural-language guidance in the system prompt.
    mid_check_round_override: int | None = field(
        default_factory=lambda: (
            int(os.environ["MW_MID_CHECK_ROUND"])
            if "MW_MID_CHECK_ROUND" in os.environ
            else None
        )
    )

    # Path to v4 dimension cards (analysis/4-middleware/v4_dimensions/M*.md)
    dimension_cards_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get(
                "MW_DIMENSION_CARDS_DIR",
                "/home/nn/SOTA-agents/analysis/4-middleware/v4_dimensions",
            )
        )
    )

    # ── Derived adapter params ──────────────────────────────────────────

    def adapter(self) -> dict:
        return FRAMEWORK_ADAPTERS.get(
            self.framework, FRAMEWORK_ADAPTERS["thinkdepthai-qwen3.5-plus"]
        )

    @property
    def mid_check_round(self) -> int:
        if self.mid_check_round_override is not None:
            return self.mid_check_round_override
        return self.adapter()["mid_check_round"]

    @property
    def mid_primary_pool(self) -> list[str]:
        return list(self.adapter()["mid_primary_pool"])

    @property
    def mid_secondary_pool(self) -> list[str]:
        return list(self.adapter()["mid_secondary_pool"])

    @property
    def concl_primary_pool(self) -> list[str]:
        return list(self.adapter()["concl_primary_pool"])

    @property
    def concl_secondary_pool(self) -> list[str]:
        return list(self.adapter()["concl_secondary_pool"])

    @property
    def framework_hint(self) -> str:
        return self.adapter()["framework_hint"]
