"""v4 orchestration — wraps state, intent classifier, and the metacognitive advisor.

Two public methods:

- ``after_tool_round(...)``: called by agent_runner after each tool_node
  execution. Updates state and decides whether to fire the mid-check.
  Returns intervention text (HumanMessage content) or None.

- ``check_before_conclusion()``: called from the new pre_conclusion_check
  node. Returns intervention text or None.

The L1 intent classifier is reused from v3 (it only needs a model with
.invoke()); we point it at the same opus-4.7 client.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from ..intent_classifier import IntentClassifier
from .config import V4Config
from .metacognitive_advisor import MetacognitiveAdvisor
from .state import V4State, _MidCheckRecord

logger = logging.getLogger(__name__)


_INTERVENTION_TAG = "[Investigation Advisor — v4]"


class V4Pipeline:
    """One pipeline instance per agent run / case."""

    def __init__(self, config: V4Config | None = None):
        self.config = config or V4Config()
        self.state = V4State()
        self.advisor = MetacognitiveAdvisor(self.config)
        # Reuse v3's intent classifier; it only needs a model with .invoke().
        self.classifier: IntentClassifier | None = None
        if self.config.enabled and self.advisor._llm is not None:
            self.classifier = IntentClassifier(self.advisor._llm)

        self._pending_sqls: list[tuple[str, int]] = []
        logger.info(
            "v4 middleware ready: enabled=%s framework=%s mid_round=%s",
            self.config.enabled, self.config.framework, self.config.mid_check_round,
        )

    @property
    def enabled(self) -> bool:
        return self.config.enabled and self.advisor._llm is not None

    # ── primary entry: after each tool_node ───────────────────────────

    def after_tool_round(
        self,
        tool_calls: list[dict],
        round_num: int,
        assistant_content: str = "",
    ) -> str | None:
        """Update state from this round; fire mid-check if threshold reached."""
        if not self.enabled:
            return None

        # 1) capture reasoning + SQLs regardless of whether we'll check.
        self.state.extract_reasoning(tool_calls, assistant_content)
        self.state.increment_round()

        for tc in tool_calls or []:
            if tc.get("name") != "query_parquet_files":
                continue
            sql = (tc.get("args") or {}).get("query", "") or ""
            if sql:
                self._pending_sqls.append((sql, round_num))
                self.state.add_raw_sql(sql)

        # 2) Should we fire mid-check now?
        if self.state.mid_check_done:
            return None
        if self.state.intervention_count >= self.config.max_interventions:
            return None
        if self.state.round_count < self.config.mid_check_round:
            return None

        # 3) Flush L1 batch classification (keeps intent_log fresh for opus).
        self._flush_intents()

        # 4) Run advisor.
        snapshot = self.state.trajectory_snapshot("mid")
        result = self.advisor.check(snapshot, "mid", prior_mid_check=None)
        # Mark as done regardless of trigger so we don't re-fire mid every round.
        self.state.mid_check_done = True
        self.state.mid_check_record = _MidCheckRecord(
            triggered=result.triggered,
            primary=result.primary_dimension,
            secondary=list(result.secondary_dimensions),
            intervention_text=result.intervention_text,
            round=self.state.round_count,
            brief_reasoning=result.brief_reasoning,
        )
        if not result.triggered:
            logger.info(
                "v4 mid-check NOT triggered at round %d: %s",
                self.state.round_count, result.reason_if_not_triggered,
            )
            return None

        self.state.intervention_count += 1
        text = self._wrap_intervention(result, "mid")
        logger.info(
            "v4 mid-check FIRED at round %d primary=%s secondary=%s",
            self.state.round_count, result.primary_dimension,
            result.secondary_dimensions,
        )
        return text

    # ── secondary entry: before conclusion ────────────────────────────

    def check_before_conclusion(self) -> str | None:
        if not self.enabled:
            return None
        if self.state.conclusion_check_done:
            return None
        if self.state.intervention_count >= self.config.max_interventions:
            self.state.conclusion_check_done = True
            return None

        # Flush any unclassified SQLs.
        self._flush_intents()

        snapshot = self.state.trajectory_snapshot("conclusion")
        prior_dict: dict | None = None
        if self.state.mid_check_record is not None:
            prior_dict = asdict(self.state.mid_check_record)

        result = self.advisor.check(snapshot, "conclusion", prior_mid_check=prior_dict)
        self.state.conclusion_check_done = True

        if not result.triggered:
            logger.info(
                "v4 conclusion-check NOT triggered: %s", result.reason_if_not_triggered,
            )
            return None

        self.state.intervention_count += 1
        text = self._wrap_intervention(result, "conclusion")
        logger.info(
            "v4 conclusion-check FIRED at round %d primary=%s secondary=%s",
            self.state.round_count, result.primary_dimension,
            result.secondary_dimensions,
        )
        return text

    # ── helpers ──────────────────────────────────────────────────────

    def _flush_intents(self) -> None:
        if not self._pending_sqls or self.classifier is None:
            return
        try:
            results = self.classifier.classify_batch(self._pending_sqls)
            for r in results:
                self.state.add_intent(r)
        except Exception:  # noqa: BLE001 — best-effort
            logger.warning("v4 L1 batch classification failed", exc_info=True)
        self._pending_sqls.clear()

    def _wrap_intervention(self, result: Any, phase: str) -> str:
        """Produce the HumanMessage content the agent will see."""
        primary = result.primary_dimension or "?"
        secondary = "+".join(result.secondary_dimensions) if result.secondary_dimensions else ""
        sub_tag = f"phase={phase} primary={primary}"
        if secondary:
            sub_tag += f" secondary={secondary}"
        body = result.intervention_text.strip()
        return f"{_INTERVENTION_TAG} {sub_tag}\n{body}"

    # ── audit ────────────────────────────────────────────────────────

    def audit_record(self) -> dict:
        """Return what happened during this case, for trajectory metadata."""
        return {
            "framework": self.config.framework,
            "mid_check_round_threshold": self.config.mid_check_round,
            "intervention_count": self.state.intervention_count,
            "mid_check": (
                asdict(self.state.mid_check_record)
                if self.state.mid_check_record else None
            ),
            "conclusion_check_done": self.state.conclusion_check_done,
            "round_count": self.state.round_count,
            "draft_root_causes": list(self.state.draft_root_causes),
        }
