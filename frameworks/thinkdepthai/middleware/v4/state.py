"""v4 per-case state — captures everything opus-4.7 may need at check-points.

Filled incrementally as the agent calls tools. Pure data class, no LLM logic.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# 19-class intent → {triage, trace, log, metric, baseline} (mirrors v3 PHASE_MAP).
PHASE_MAP: dict[str, str] = {
    "latency_ranking": "triage",
    "throughput_compare": "triage",
    "error_rate_scan": "triage",
    "error_log_overview": "triage",
    "metric_scan": "triage",
    "service_trace_scan": "trace",
    "trace_follow": "trace",
    "call_tree_build": "trace",
    "service_error_log": "log",
    "service_log_browse": "log",
    "keyword_search": "log",
    "error_timeline": "log",
    "container_resource": "metric",
    "jvm_state": "metric",
    "network_layer": "metric",
    "k8s_state": "metric",
    "db_state": "metric",
    "baseline_collect": "baseline",
    "baseline_contrast": "baseline",
}

RANKING_INTENTS: set[str] = {
    "latency_ranking", "throughput_compare", "error_rate_scan", "metric_scan",
}

RUNTIME_LAYER_INTENTS: set[str] = {
    "container_resource", "jvm_state", "network_layer", "k8s_state", "db_state",
}


# Service name extractor — TrainTicket convention.
_SVC_RE = re.compile(r"\bts-[a-zA-Z0-9-]+\b")
_RANKING_TOP3_HINT = re.compile(
    r"(?:top[\s-]?3|first three|first 3|top three|leading|highest)",
    re.IGNORECASE,
)


@dataclass
class _MidCheckRecord:
    """What opus-4.7 emitted at the mid-check point. None ⇒ not yet checked."""

    triggered: bool
    primary: str | None
    secondary: list[str]
    intervention_text: str
    round: int
    brief_reasoning: str = ""


@dataclass
class V4State:
    """Per-case investigation state.

    All fields are derived from runtime-observable signals only
    (per v4 principle 2: no GT, no fault_category, no chronic_noise list).
    """

    # ── primary signals ───────────────────────────────────────────────
    intent_sequence: list[dict] = field(default_factory=list)
    """Each entry: {round, intent, data_type, services, sql, sql_index?}."""

    raw_sqls: list[str] = field(default_factory=list)
    reasoning_log: list[str] = field(default_factory=list)
    """Each entry: a think_tool reflection or substantive assistant.content (≤500 chars)."""

    # round_count = number of AIMessage rounds with tool_calls (effective_rounds).
    round_count: int = 0
    query_count: int = 0     # number of query_parquet_files calls

    # ── derived structural data ───────────────────────────────────────
    last_ranking_top3: list[dict] = field(default_factory=list)
    """Up to 3 most recent ranking SQL results: {round, intent, top3: [svc,svc,svc]}."""

    where_filters: set[str] = field(default_factory=set)
    """All ts-* services that have appeared in WHERE service_name = ... clauses."""

    observed_services: set[str] = field(default_factory=set)
    """All ts-* names ever seen in SQL or reasoning (union of query targets, log/trace results)."""

    draft_root_causes: list[str] = field(default_factory=list)
    """Best-effort guess of agent's current commit candidate(s).

    Heuristic: most-recent reasoning text that contains "root cause" / "the cause is" /
    "I believe" / "candidate is" — service tokens extracted there. Updated on each
    reasoning_log append.
    """

    # ── mid / conclusion-check book-keeping ───────────────────────────
    mid_check_done: bool = False
    mid_check_record: _MidCheckRecord | None = None
    conclusion_check_done: bool = False
    intervention_count: int = 0

    # ── derived properties ────────────────────────────────────────────

    @property
    def intent_type_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for x in self.intent_sequence:
            i = x.get("intent", "unknown")
            out[i] = out.get(i, 0) + 1
        return out

    @property
    def phases_visited(self) -> set[str]:
        return {
            PHASE_MAP[x["intent"]]
            for x in self.intent_sequence
            if x.get("intent") in PHASE_MAP
        }

    @property
    def baseline_intent_count(self) -> int:
        return sum(
            1
            for x in self.intent_sequence
            if x.get("intent") in {"baseline_collect", "baseline_contrast"}
        )

    @property
    def runtime_layer_intent_count(self) -> int:
        return sum(
            1
            for x in self.intent_sequence
            if x.get("intent") in RUNTIME_LAYER_INTENTS
        )

    @property
    def has_queried_normal(self) -> bool:
        if self.baseline_intent_count > 0:
            return True
        for sql in self.raw_sqls:
            if re.search(r"(?<!ab)normal_", sql.lower()):
                return True
        return False

    @property
    def recent_intents(self, k: int = 8) -> list[str]:
        return [x.get("intent", "unknown") for x in self.intent_sequence[-k:]]

    # ── mutation API ──────────────────────────────────────────────────

    def add_intent(self, entry: dict) -> None:
        self.intent_sequence.append(entry)
        # Track ranking top-3 if we can. The actual SQL result is not available
        # at intent-add time; we only know the intent label. If a downstream
        # consumer wants to seed last_ranking_top3 from real query results,
        # call ``record_ranking_result`` after the SQL runs.
        for svc in entry.get("services", []):
            self.observed_services.add(svc)
            self.where_filters.add(svc)

    def add_raw_sql(self, sql: str) -> None:
        self.raw_sqls.append(sql)
        self.query_count += 1
        # Cheap WHERE-filter scan
        for m in re.finditer(
            r"(?:service_name|service|component)\s*=\s*'?(ts-[a-zA-Z0-9-]+)'?",
            sql, re.IGNORECASE,
        ):
            self.where_filters.add(m.group(1))
        for svc in _SVC_RE.findall(sql):
            self.observed_services.add(svc)

    def record_ranking_result(
        self, round_num: int, intent: str, top3: list[str]
    ) -> None:
        """Optional: caller may invoke this after a ranking SQL returns to
        populate ``last_ranking_top3``. If not invoked, opus-4.7 sees an
        empty list which still works (M1 still triggers via reasoning text).
        """
        if not top3:
            return
        self.last_ranking_top3.append(
            {"round": round_num, "intent": intent, "top3": top3[:3]}
        )
        # Keep only most recent 3 entries
        self.last_ranking_top3 = self.last_ranking_top3[-3:]
        for s in top3[:3]:
            self.observed_services.add(s)

    def extract_reasoning(
        self,
        tool_calls: list[dict] | None,
        assistant_content: str = "",
    ) -> None:
        """Extract reflections / substantive content from one round."""
        for tc in tool_calls or []:
            if tc.get("name") != "think_tool":
                continue
            args = tc.get("args", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, TypeError):
                    args = {}
            reflection = args.get("reflection", "")
            if reflection:
                self.reasoning_log.append(reflection[:1500])
                self._update_draft_rc(reflection)

        if assistant_content and len(assistant_content) > 50:
            self.reasoning_log.append(assistant_content[:1500])
            self._update_draft_rc(assistant_content)

    def increment_round(self) -> None:
        self.round_count += 1

    # ── internal helpers ──────────────────────────────────────────────

    def _update_draft_rc(self, text: str) -> None:
        """Heuristic update of draft_root_causes from a reflection / content blob."""
        commit_signal = re.search(
            r"(root\s*cause|i (?:believe|conclude|think)|the cause is|"
            r"candidate(?:\s+is|s? are)|appears? to be|points? to)",
            text, re.IGNORECASE,
        )
        if not commit_signal:
            return
        # Take the surrounding ~120-char window after the signal
        window = text[commit_signal.start(): commit_signal.start() + 240]
        services = _SVC_RE.findall(window)
        if not services:
            return
        # De-dup while preserving order; keep most recent ones at the front
        new_rc: list[str] = []
        for s in services:
            if s not in new_rc:
                new_rc.append(s)
        self.draft_root_causes = new_rc[:3]
        for s in new_rc:
            self.observed_services.add(s)

    # ── snapshot for opus-4.7 prompt ──────────────────────────────────

    def trajectory_snapshot(self, check_point: str) -> dict:
        """Build the B1-B7 + derived signals payload for opus-4.7.

        check_point: 'mid' | 'conclusion'
        """
        # B2: recent 5 reflections full + earlier summary
        recent = self.reasoning_log[-5:]
        earlier = self.reasoning_log[:-5]
        earlier_summary = ""
        if earlier:
            joined = " | ".join(r[:200] for r in earlier[-10:])
            earlier_summary = f"({len(earlier)} earlier reflections; tail-10 condensed) {joined[:1500]}"

        return {
            "check_point": check_point,
            # B1
            "intent_log": [
                {
                    "round": x.get("round"),
                    "intent": x.get("intent", "unknown"),
                    "services": x.get("services", []),
                }
                for x in self.intent_sequence
            ],
            # B2
            "recent_reasoning": recent,
            "earlier_reasoning_summary": earlier_summary,
            # B4
            "where_service_filters": sorted(self.where_filters),
            # B5
            "observed_services": sorted(self.observed_services),
            # B6
            "round_count": self.round_count,
            "tool_call_count_estimate": len(self.intent_sequence)
                                     + sum(1 for r in self.reasoning_log if r),
            "intent_type_counts": self.intent_type_counts,
            "phases_visited": sorted(self.phases_visited),
            "baseline_intent_count": self.baseline_intent_count,
            "runtime_layer_intent_count": self.runtime_layer_intent_count,
            # B7
            "last_ranking_top3": list(self.last_ranking_top3),
            # extra: candidate
            "draft_root_causes": list(self.draft_root_causes),
        }
