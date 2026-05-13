"""L2+L3 merged caller — single opus-4.7 invocation per check-point.

Implements the contract from analysis/4-middleware/v4_principles.md:
- Inputs: A1-A6 (dim library) + B1-B7 (snapshot) + C1-C3 (context).
- Output JSON:
    {
      "triggered": bool,
      "reason_if_not_triggered": str,
      "primary_dimension": "M1" | null,
      "secondary_dimensions": ["M6", ...],
      "intervention_text": str,
      "brief_reasoning": str
    }

Returns a typed dict (advisor result). Caller decides whether to inject.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from .config import V4Config
from .dimension_cards import DimensionCardLibrary

logger = logging.getLogger(__name__)

# Authoritative system prompt — keep terse, the bulk of dimensional knowledge
# is interpolated via the rendered cards. This text codifies v4 principle 4
# (the 8 intervention rules) for opus-4.7.
_SYSTEM_PROMPT = """\
You are the Metacognitive Investigation Advisor for an RCA agent.
The agent is investigating a microservice incident on TrainTicket; you observe
its trajectory at a CHECK POINT and decide whether to inject a metacognitive
nudge. You DO NOT see the ground-truth root cause and DO NOT know the
fault category.

You are given:
1. A pool of dimensions (M1..M10), split into PRIMARY (preferred at this
   check-point) and SECONDARY (only fire if evidence is unambiguously strong).
2. A trajectory snapshot from the agent (B1..B7).
3. Per-case context including any prior intervention.

You must follow these intervention rules (v4 principle 4 - non-negotiable):
1. NEVER reveal the answer, root-cause service, or fault category.
2. NEVER write SQL strings, table names, column names, or metric names.
3. NEVER list service names, error-message strings, or domain-specific terms.
4. NEVER use directional concepts (upstream/downstream/source/sink/victim/
   perpetrator/caller/callee). Use neutral language: "another service",
   "another possibility", "a related service".
5. DO make the agent aware of what it just did or just observed.
6. DO use rhetorical questions and multiple possibilities ("X is not
   necessarily Y; it could also be Z or W").
7. DO follow a 1-primary + 0-3-secondary structure. If only one dimension
   actually hits, the primary stands alone - do not pad.
8. DO reference what the agent has actually done ("you ran ranking queries
   in the last few rounds" is allowed; "you ran SELECT service_name..." is
   not).

Decision guidance (you decide autonomously - there is no scoring threshold):
- Default: focus on whether any PRIMARY dimension is hit. PRIMARY dimensions
  are the ones suited for THIS check point.
- A SECONDARY dimension fires only when the trajectory shows unambiguously
  strong evidence for it - more obvious than for any PRIMARY hit. Otherwise
  do not include it.
- If a SECONDARY dimension's evidence clearly outweighs every PRIMARY
  candidate, you may promote it to primary_dimension. This is the
  flexibility escape hatch; use it sparingly.
- If no dimension has clear evidence, set triggered=false.
- The intervention follows: 1 primary (mandatory when triggered) + 0..3
  secondaries (only the ones that genuinely hit). Do NOT pad to reach 3.
- Same dimension already used in a prior intervention (per [C2 PRIOR
  INTERVENTION HISTORY]) MUST NOT be reused as the primary; if it is the
  best candidate, prefer triggered=false unless another, different
  dimension is ALSO clearly hit.

Output format (return ONLY this JSON, no prose around it):
{
  "triggered": true | false,
  "reason_if_not_triggered": "..." (only when triggered=false; otherwise ""),
  "primary_dimension": "M1" | null,
  "secondary_dimensions": ["M6", ...] (may be empty),
  "intervention_text": "..." (only when triggered=true; concrete prompt that
     the agent will receive verbatim - must obey rules 1-8 above),
  "brief_reasoning": "..." (1-3 sentences explaining your dimension choices)
}

When triggered=false: set primary_dimension=null, secondary_dimensions=[],
intervention_text="", and explain in reason_if_not_triggered.
"""


@dataclass
class AdvisorResult:
    triggered: bool
    primary_dimension: str | None
    secondary_dimensions: list[str]
    intervention_text: str
    brief_reasoning: str
    reason_if_not_triggered: str
    raw_response: str  # for audit / debugging
    error: str | None = None


class MetacognitiveAdvisor:
    """Single-call opus-4.7 advisor used for both mid- and conclusion-checks."""

    def __init__(self, config: V4Config):
        self.config = config
        self.lib = DimensionCardLibrary(config.dimension_cards_dir)
        self._llm = self._build_llm()

    def _build_llm(self):
        """Build the opus-4.7 LangChain client. Anthropic SDK via shubiaobiao.

        We construct lazily so that pure-import smoke tests don't need network.
        """
        if not self.config.enabled:
            return None
        if not self.config.llm_api_key:
            logger.warning(
                "v4 middleware: LLM api key empty; advisor will return triggered=false"
            )
            return None

        from langchain_anthropic import ChatAnthropic

        # ChatAnthropic wants base_url WITHOUT trailing /v1
        base = self.config.llm_base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]

        return ChatAnthropic(
            model=self.config.llm_model,
            api_key=self.config.llm_api_key,
            base_url=base,
            max_tokens=self.config.llm_max_tokens,
            temperature=self.config.llm_temperature,
        )

    # ── public API ────────────────────────────────────────────────────

    def check(
        self,
        snapshot: dict,
        check_point: str,
        prior_mid_check: dict | None = None,
    ) -> AdvisorResult:
        """Run one advisor invocation.

        Args:
            snapshot: from V4State.trajectory_snapshot(check_point=...)
            check_point: 'mid' or 'conclusion'
            prior_mid_check: serialised mid-check record if conclusion-time

        Returns AdvisorResult — caller decides whether to use.
        """
        if self._llm is None:
            return AdvisorResult(
                triggered=False,
                primary_dimension=None,
                secondary_dimensions=[],
                intervention_text="",
                brief_reasoning="",
                reason_if_not_triggered="middleware llm disabled or unconfigured",
                raw_response="",
            )

        sys_prompt = _SYSTEM_PROMPT
        user_payload = self._render_user_payload(
            snapshot, check_point, prior_mid_check
        )

        from langchain_core.messages import HumanMessage, SystemMessage

        try:
            resp = self._llm.invoke(
                [SystemMessage(content=sys_prompt),
                 HumanMessage(content=user_payload)]
            )
            text = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as e:  # noqa: BLE001 — defensive at trust boundary
            logger.warning("v4 advisor LLM call failed: %s", e)
            return AdvisorResult(
                triggered=False,
                primary_dimension=None,
                secondary_dimensions=[],
                intervention_text="",
                brief_reasoning="",
                reason_if_not_triggered=f"llm error: {e}",
                raw_response="",
                error=str(e),
            )

        # Anthropic returns content as either str or list[dict] (text blocks)
        if isinstance(text, list):
            text = "".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in text
            )

        return self._parse(text)

    # ── prompt rendering ──────────────────────────────────────────────

    def _render_user_payload(
        self,
        snapshot: dict,
        check_point: str,
        prior_mid_check: dict | None,
    ) -> str:
        adapter = self.config.adapter()
        if check_point == "mid":
            primary_pool = adapter["mid_primary_pool"]
            secondary_pool = adapter["mid_secondary_pool"]
        else:
            primary_pool = adapter["concl_primary_pool"]
            secondary_pool = adapter["concl_secondary_pool"]

        primary_block = "\n".join(
            "- " + self.lib.render_for_prompt(m, "primary")
            for m in primary_pool
        )
        secondary_block = "\n".join(
            "- " + self.lib.render_for_prompt(m, "secondary")
            for m in secondary_pool
        )

        # Trim snapshot to a manageable size for opus prompt cost.
        intent_log = snapshot.get("intent_log", [])
        intent_log_repr = "\n".join(
            f"  R{e.get('round')}: {e.get('intent')}"
            + (f"  svc={e.get('services')}" if e.get('services') else "")
            for e in intent_log[-40:]
        )
        recent_reflections = "\n---\n".join(
            f"({i+1}) {r}"
            for i, r in enumerate(snapshot.get("recent_reasoning", []))
        ) or "(none)"

        prior_str = "(none)"
        if prior_mid_check:
            prior_str = json.dumps(prior_mid_check, ensure_ascii=False)[:1500]

        # Compact text payload — opus parses this as natural language.
        return f"""\
[CHECK POINT] {check_point}
[FRAMEWORK] {self.config.framework}
[FRAMEWORK HINT] {self.config.framework_hint}

[A2 PRIMARY DIMENSION POOL — preferred at this check point]
{primary_block}

[A3 SECONDARY DIMENSION POOL — strong evidence required to fire]
{secondary_block}

[B1 INTENT LOG (most recent 40)]
{intent_log_repr or "(empty)"}

[B2 RECENT REFLECTIONS (last 5)]
{recent_reflections}
[B2 EARLIER SUMMARY]
{snapshot.get('earlier_reasoning_summary') or '(none)'}

[B4 WHERE-FILTER SERVICES (distinct)]
{', '.join(snapshot.get('where_service_filters', [])) or '(none)'}

[B5 OBSERVED SERVICES (distinct)]
{', '.join(snapshot.get('observed_services', [])) or '(none)'}

[B6 STRUCTURAL COUNTS]
round_count = {snapshot.get('round_count')}
intent_type_counts = {json.dumps(snapshot.get('intent_type_counts', {}), ensure_ascii=False)}
phases_visited = {snapshot.get('phases_visited')}
baseline_intent_count = {snapshot.get('baseline_intent_count')}
runtime_layer_intent_count = {snapshot.get('runtime_layer_intent_count')}

[B7 LAST RANKING TOP-3]
{json.dumps(snapshot.get('last_ranking_top3', []), ensure_ascii=False) or '(none)'}

[CANDIDATE ROOT CAUSES (heuristic from reasoning)]
{snapshot.get('draft_root_causes') or '(none)'}

[C2 PRIOR INTERVENTION HISTORY]
mid_check: {prior_str}

Return ONLY the JSON object as specified.
"""

    # ── output parsing ────────────────────────────────────────────────

    _JSON_RE = re.compile(r"\{[\s\S]*\}")

    def _parse(self, text: str) -> AdvisorResult:
        raw = text or ""
        # Strip ```json fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        # Try direct json then bracket extraction
        for candidate in (cleaned, self._extract_json_block(raw)):
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return self._build_result(parsed, raw)
            except json.JSONDecodeError:
                continue
        logger.warning("v4 advisor returned non-JSON: %s", raw[:300])
        return AdvisorResult(
            triggered=False,
            primary_dimension=None,
            secondary_dimensions=[],
            intervention_text="",
            brief_reasoning="",
            reason_if_not_triggered="parse failure",
            raw_response=raw,
            error="parse failure",
        )

    @classmethod
    def _extract_json_block(cls, text: str) -> str | None:
        m = cls._JSON_RE.search(text or "")
        return m.group(0) if m else None

    @staticmethod
    def _build_result(parsed: dict, raw: str) -> AdvisorResult:
        triggered = bool(parsed.get("triggered", False))
        return AdvisorResult(
            triggered=triggered,
            primary_dimension=parsed.get("primary_dimension"),
            secondary_dimensions=list(parsed.get("secondary_dimensions") or []),
            intervention_text=parsed.get("intervention_text") or "",
            brief_reasoning=parsed.get("brief_reasoning") or "",
            reason_if_not_triggered=parsed.get("reason_if_not_triggered") or "",
            raw_response=raw,
        )
