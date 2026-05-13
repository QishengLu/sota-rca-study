"""Synthesize a free-text incident_description from ops-lite manifest fields.

The 6 agents (ported from older SOTA-agents code) historically received an
`incident_description` string that read like a natural-language ops report.
ops-lite gives us structured fields (chaos_family / primary_kind / subtypes /
root_services / n_alarm_svc / system), which we recompose into the same
"feel" so existing prompts work unchanged.
"""
from __future__ import annotations

from datetime import datetime, UTC


def build_incident_description(case) -> str:
    """Compose a natural-language incident description for the prompt.

    `case` is a sota_rca.data.ops_lite.Case (avoid circular import by duck-typing).
    """
    parts: list[str] = []

    # Header
    sys_label = {"ts": "TrainTicket", "hs": "HotelReservation", "otel-demo": "OpenTelemetry Demo"}.get(
        case.system, case.system
    )
    parts.append(f"# Incident Report — {sys_label}")
    parts.append("")

    # Telemetry summary
    parts.append(f"An SLO violation has been detected affecting {case.n_alarm_svc} services "
                 f"out of {case.n_svc} in the {sys_label} system.")

    # Alarms
    if case.root_services:
        services = ", ".join(f"`{s}`" for s in case.root_services)
        parts.append(f"\nUser-visible alarms originate from: {services}.")

    # Available data
    parts.append("")
    parts.append("## Available telemetry")
    parts.append("All data is in the local case directory as parquet files:")
    parts.append("- `abnormal_metrics.parquet`, `abnormal_traces.parquet`, `abnormal_logs.parquet`")
    parts.append("- `abnormal_metrics_histogram.parquet`, `abnormal_metrics_sum.parquet`")
    parts.append("- `normal_metrics.parquet`, `normal_traces.parquet`, `normal_logs.parquet`")
    parts.append("")
    parts.append("(`normal_*` parquets are baseline observations from before the incident.)")

    # Task
    parts.append("")
    parts.append("## Task")
    parts.append("Identify the root cause(s) of the SLO violation. Multiple root causes "
                 "and propagation edges are possible. Return your findings as a structured "
                 "causal graph (the synthesis step will format your investigation messages "
                 "into the required JSON schema).")

    # Timestamp
    parts.append("")
    parts.append(f"_Report generated {datetime.now(UTC).isoformat()}_")

    return "\n".join(parts)
