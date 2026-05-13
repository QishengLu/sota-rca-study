#!/usr/bin/env python
"""Dossier builder for aiq-qwen3.5-plus (adapter v2, standalone).

Part A (GT reality) is identical to thinkdepthai v1 builder — reads the same
injection.json / causal_graph.json / conclusion / parquet data per case.

Part B (agent trajectory) is aiq-specific:

  * The trajectory contains 3 sub-loop stages (data_research main + 2 refine
    iterations); each stage terminates with a content-only assistant message.
  * Each round carries a pipeline_stage label {stage_0_main, stage_1_refine1,
    stage_2_refine2, stage_X_truncated}, derived from cumulative terminator
    count + keyword regex on the terminator content.
  * Stage-transition terminators are surfaced as first-class events in the
    dossier, with full content printed, so the analyst can see where the LLM
    said "I'm done, this is my conclusion" vs where max_rounds cut it off.
  * Reasoning is collected from BOTH think_tool.reflection AND
    assistant.content (qwen 3.5 often emits content with tool_calls in the
    same message, unlike thinkdepthai which keeps them separate).

Usage:
    cd RCAgentEval
    uv run python analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/build_dossier.py \\
        --db postgresql://postgres:postgres@localhost:5433/SOTA-Agents \\
        --exp_id aiq-qwen3.5-plus \\
        --out_dir analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/v1/dossiers
"""

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from sqlmodel import Session, create_engine, select

sys.path.insert(0, "RCAgentEval")

from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402

# Reuse Part A loaders from the thinkdepthai builder (they are GT-data code,
# agent-independent). Importing avoids duplicating ~400 lines.
sys.path.insert(0, "RCAgentEval/scripts/failure_analysis")
import build_dossiers as tdt  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ── aiq-specific trajectory parsing ─────────────────────────────────────────

SERVICE_RE = re.compile(r"ts-[a-z0-9\-]+")
ERROR_RE = re.compile(
    r"\b(5\d\d|error|refused|timeout|exception|connection reset|upstream connect"
    r"|OOM|OutOfMemory|killed|restarting|CrashLoopBackOff)\b",
    re.IGNORECASE,
)
HYP_PATTERNS = [
    re.compile(r"root cause[^\n]{0,40}?(?:is|=|:)[^\n]{0,30}?(ts-[a-z0-9\-]+)", re.IGNORECASE),
    re.compile(r"(ts-[a-z0-9\-]+)\s+is\s+the\s+(?:root cause|origin|culprit)", re.IGNORECASE),
    re.compile(r"conclude[^\n]{0,30}?(ts-[a-z0-9\-]+)", re.IGNORECASE),
    re.compile(r"identified\s+(ts-[a-z0-9\-]+)\s+as", re.IGNORECASE),
    re.compile(r"\*\*(ts-[a-z0-9\-]+)\*\*", re.IGNORECASE),  # markdown bold often wraps the verdict
]

TOOL_RESULT_DISPLAY_LIMIT = 2000

# Stage identity keyword regex (applied to terminator content).
# Priority order matters: check more specific markers first.
STAGE_ID_REGEX = [
    ("stage_2_refine2", re.compile(r"strengthen|validates?|strengthened", re.IGNORECASE)),
    ("stage_1_refine1", re.compile(r"refine.+(graph|root.cause)|sufficient evidence to refine", re.IGNORECASE)),
    ("stage_0_main", re.compile(r"final (causal|root cause).{0,30}graph|construct.{0,30}(causal|graph)|"
                                r"comprehensive analysis|final structured|all the information needed", re.IGNORECASE)),
]

INTENT_MODEL_KEY = "claude_opus_4_6"

STAGE_BY_INTENT = {
    "latency_ranking": "T", "throughput_compare": "T", "error_rate_scan": "T",
    "error_log_overview": "T", "metric_scan": "T",
    "service_trace_scan": "V", "trace_follow": "V", "call_tree_build": "V",
    "service_error_log": "L", "service_log_browse": "L", "keyword_search": "L",
    "error_timeline": "L",
    "container_resource": "M", "jvm_state": "M", "network_layer": "M",
    "k8s_state": "M", "db_state": "M",
    "baseline_collect": "B", "baseline_contrast": "B",
}


@dataclass
class ToolResultParsed:
    raw: str
    display: str
    row_count: int | None = None
    error_snippets: list[str] = field(default_factory=list)
    services_mentioned: list[str] = field(default_factory=list)


@dataclass
class Round:
    index: int  # 1-based, continuous across all 3 stages
    pipeline_stage: str  # stage_0_main / stage_1_refine1 / stage_2_refine2 / stage_X_truncated
    think: str | None = None  # merged from think_tool reflections AND assistant.content
    tools: list[dict] = field(default_factory=list)
    results: list[ToolResultParsed] = field(default_factory=list)


@dataclass
class StageTerminator:
    """A content-only assistant message terminating a sub-loop."""
    after_round: int           # round_idx that this terminator follows
    stage_closed: str          # which stage label this is closing
    content: str               # full text, not truncated
    char_count: int


def _msg_content_text(msg: dict) -> str:
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                t = item.get("text") or item.get("content") or ""
                parts.append(str(t))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return ""


def _extract_think_arg(arg_str: str) -> str | None:
    try:
        obj = json.loads(arg_str)
        if isinstance(obj, dict):
            for k in ("reflection", "thought", "text", "content"):
                if k in obj and obj[k]:
                    return str(obj[k])
    except json.JSONDecodeError:
        pass
    return arg_str[:2000] if arg_str else None


def _parse_tool_result(content: str) -> ToolResultParsed:
    raw = content.strip()
    display = raw[:TOOL_RESULT_DISPLAY_LIMIT]
    if len(raw) > TOOL_RESULT_DISPLAY_LIMIT:
        display += f"\n... ({len(raw)} chars total, truncated)"
    lines = raw.splitlines()
    row_count = len(lines) - 1 if len(lines) > 2 else None
    error_snippets = sorted(set(m.group(0) for m in ERROR_RE.finditer(raw)))[:5]
    services_mentioned = sorted(set(SERVICE_RE.findall(raw)))
    return ToolResultParsed(raw=raw, display=display, row_count=row_count,
                            error_snippets=error_snippets, services_mentioned=services_mentioned)


def _identify_stage_from_terminator(content: str) -> str | None:
    for label, pat in STAGE_ID_REGEX:
        if pat.search(content):
            return label
    return None


def _expected_stage_label(stage_idx: int) -> str:
    """Expected label if no truncation: stage_idx 0 → stage_0_main, 1 → stage_1_refine1, 2 → stage_2_refine2."""
    mapping = {0: "stage_0_main", 1: "stage_1_refine1", 2: "stage_2_refine2"}
    return mapping.get(stage_idx, f"stage_{stage_idx}_extra")


def parse_aiq_trajectory(traj_str: str | None) -> tuple[list[Round], list[StageTerminator], dict]:
    """Return (rounds, terminators, summary).

    summary contains:
      - terminator_count
      - truncated_stages: list of stage labels that were truncated
      - final_stage_status: one of {all_concluded, one_truncated, two_truncated, all_truncated}
    """
    if not traj_str:
        return [], [], {}
    try:
        traj = json.loads(traj_str)
    except json.JSONDecodeError:
        return [], [], {}

    rounds: list[Round] = []
    terminators: list[StageTerminator] = []

    current_stage_idx = 0  # we start in stage 0 (data_research main)
    round_idx = 0

    for msg in traj:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")

        if role == "assistant":
            tool_calls = msg.get("tool_calls") or []
            content = _msg_content_text(msg).strip()

            if not tool_calls and content:
                # Stage terminator: LLM chose to stop calling tools
                identified = _identify_stage_from_terminator(content)
                stage_closed = identified or _expected_stage_label(current_stage_idx)
                terminators.append(StageTerminator(
                    after_round=round_idx,
                    stage_closed=stage_closed,
                    content=content,
                    char_count=len(content),
                ))
                current_stage_idx += 1
                continue

            if not tool_calls and not content:
                # Empty assistant message — skip (rare)
                continue

            round_idx += 1
            stage_label = _expected_stage_label(current_stage_idx)
            r = Round(index=round_idx, pipeline_stage=stage_label)

            # Capture assistant content (qwen thinking-aloud)
            if content:
                r.think = content

            for tc in tool_calls:
                fn = (tc.get("function") or {}) if isinstance(tc, dict) else {}
                name = fn.get("name", "")
                arg_str = fn.get("arguments", "") or ""
                if name == "think_tool":
                    think_text = _extract_think_arg(arg_str)
                    if think_text:
                        r.think = (r.think + "\n---\n" + think_text) if r.think else think_text
                    continue
                services = sorted(set(SERVICE_RE.findall(arg_str)))
                r.tools.append({"name": name, "args_full": arg_str, "services": services})
            rounds.append(r)

        elif role == "tool":
            if rounds:
                content = _msg_content_text(msg)
                if content:
                    rounds[-1].results.append(_parse_tool_result(content))

    # Compute summary
    expected_stages = 3
    truncated_stages: list[str] = []
    terminated_labels = {t.stage_closed for t in terminators}
    for i in range(expected_stages):
        expected = _expected_stage_label(i)
        if expected not in terminated_labels:
            truncated_stages.append(expected)

    if len(terminators) == expected_stages:
        final_status = "all_concluded"
    elif len(terminators) == 0:
        final_status = "all_truncated"
    elif len(terminators) == 1:
        final_status = "two_truncated"
    else:
        final_status = "one_truncated"

    # Mark rounds in truncated stages appropriately.
    # After the last terminator, remaining rounds belong to the next stage which is
    # truncated. Before that, we can only heuristically split — we use terminator
    # positions (after_round) to partition.
    #
    # If a stage had no terminator, its rounds are labeled stage_X_truncated.
    # We reconstruct stage ownership by walking terminators in order.
    if terminators:
        # terminator[i] closes at after_round; rounds 1..after_round belong to whichever
        # stage that terminator represents; rounds after that belong to next stage.
        # When truncation occurred, the mapping gets ambiguous — we keep what we
        # originally assigned (based on terminator count at parse time), which may
        # over-assign to an earlier stage. For clarity, flag rounds whose assigned
        # stage is not in terminated_labels AND not the final open stage.
        expected_labels_in_order = ["stage_0_main", "stage_1_refine1", "stage_2_refine2"]
        # Re-label: partition rounds by terminator boundaries.
        # Segment i = rounds (prev_boundary+1 .. terminator[i].after_round)
        prev = 0
        for i, term in enumerate(terminators):
            boundary = term.after_round
            for r in rounds:
                if prev < r.index <= boundary:
                    r.pipeline_stage = term.stage_closed
            prev = boundary
        # Rounds after the last terminator → next expected stage, marked _truncated
        remaining_labels = [lbl for lbl in expected_labels_in_order if lbl not in terminated_labels]
        if remaining_labels and any(r.index > prev for r in rounds):
            next_label = remaining_labels[0] + "_truncated"
            for r in rounds:
                if r.index > prev:
                    r.pipeline_stage = next_label
    else:
        # Zero terminators — all rounds are in stage_0_main (or beyond) and truncated.
        # Conservative: label every round stage_0_main_truncated.
        for r in rounds:
            r.pipeline_stage = "stage_0_main_truncated"

    summary = {
        "terminator_count": len(terminators),
        "truncated_stages": truncated_stages,
        "final_stage_status": final_status,
    }
    return rounds, terminators, summary


def extract_hypothesis(think_text: str | None) -> str | None:
    if not think_text:
        return None
    for pat in HYP_PATTERNS:
        m = pat.search(think_text)
        if m:
            return m.group(1)
    return None


def intent_overlay(meta: dict) -> dict[int, list[dict]]:
    llm_intents = (meta or {}).get("llm_intents", {}) or {}
    entries = llm_intents.get(INTENT_MODEL_KEY) or []
    out: dict[int, list[dict]] = {}
    for e in entries:
        if isinstance(e, dict) and e.get("round") is not None:
            out.setdefault(int(e["round"]), []).append(
                {"intent": e.get("intent", ""), "data_type": e.get("data_type", "")}
            )
    return out


def round_intent_tag(intents_this_round: list[dict]) -> str:
    if not intents_this_round:
        return "-"
    tags = [STAGE_BY_INTENT.get(i.get("intent", ""), "-") for i in intents_this_round]
    return max(set(tags), key=tags.count)


# ── Dossier rendering (aiq-specific Part B) ─────────────────────────────────


def render_dossier(d: dict) -> str:
    meta: dict = d["meta"] or {}
    diff = meta.get("difficulty", {}) or {}
    gt_svcs = meta.get("ground_truth") or []
    gm = (meta.get("graph_metrics") or {}).get("diagnostic", {}) or {}
    cm = meta.get("cost_metrics") or {}
    cge = meta.get("causal_graph_evaluation") or {}
    inj = d["injection_full"]
    cg = d["causal_graph_full"]
    k8s = d["k8s_summary"]
    spans = d["spans"]
    errors = d["errors"]
    zmetrics = d["zmetrics"]
    rounds: list[Round] = d["rounds"]
    terminators: list[StageTerminator] = d["terminators"]
    summary: dict = d["trajectory_summary"]
    intent_by_round = d["intent_by_round"]

    L: list[str] = []
    dsi = d["dataset_index"]
    ft = diff.get("fault_type", "?")
    fc = diff.get("fault_category", "?")
    L.append(f"# case_{dsi} — {fc} / {ft}  (aiq-qwen3.5-plus)")
    L.append("")
    L.append(f"- dataset_index: **{dsi}**")
    L.append(f"- exp_id: {d['exp_id']}")
    L.append(f"- datapack: `{meta.get('datapack_name', '?')}`")
    L.append(f"- source_data_dir: `{d['src_dir']}`")
    L.append(f"- spl={diff.get('spl')}  n_svc={diff.get('n_svc')}  n_edge={diff.get('n_edge')}")
    L.append("")

    # ── PART A (GT reality — identical to thinkdepthai builder) ──
    L.append("## Part A — GT reality (what actually happened)")
    L.append("")

    # A.1 Injection spec
    L.append("### A.1 Injection spec")
    if inj:
        L.append(f"- fault_type_raw: `{inj.get('fault_type_raw')}`")
        L.append(f"- injection_name: `{inj.get('injection_name')}`")
        L.append(f"- start_time: `{inj.get('start_time')}`")
        L.append(f"- end_time: `{inj.get('end_time')}`")
        L.append(f"- pre_duration: {inj.get('pre_duration')} min")
        dc = inj.get("display_config")
        if dc:
            L.append("- **display_config** (human-readable injection params):")
            for k, v in dc.items():
                L.append(f"  - {k}: `{v}`")
        L.append(f"- gt_services: {inj.get('gt_services')}")
        L.append(f"- gt_pods: {inj.get('gt_pods')}")
        gf = inj.get("gt_functions")
        if gf:
            L.append(f"- **gt_functions** (targeted method): {gf}")
        gmet = inj.get("gt_metrics")
        if gmet:
            L.append(f"- **gt_metrics** (targeted metric dimension): {gmet}")
    else:
        L.append("- injection.json not found")
    L.append("")

    # A.2 GT root-cause services
    L.append("### A.2 Ground-truth root-cause services (from DB meta)")
    for s in gt_svcs:
        L.append(f"- `{s}`")
    if not gt_svcs:
        L.append("- (none)")
    L.append("")

    # A.3 GT causal graph
    L.append("### A.3 GT causal graph")
    if cg:
        L.append(f"- nodes: {len(cg.get('nodes', []))},  raw_edges: {cg.get('raw_edges_count', 0)}")
        L.append(f"- root_causes: {cg.get('root_causes')}")
        L.append(f"- alarm_nodes: {cg.get('alarm_nodes')}")
        L.append("")
        nodes = cg.get("nodes") or []
        if nodes:
            L.append("**Per-node expected states** (what anomalies SHOULD be visible):")
            L.append("")
            L.append("| component | service | expected_states |")
            L.append("|---|---|---|")
            for n in nodes:
                L.append(f"| `{n['component']}` | `{n['service']}` | {n['state']} |")
            L.append("")
        se = cg.get("service_edges") or []
        if se:
            L.append("**Service-level propagation chain** (rolled up from span edges):")
            L.append("")
            for src, tgt in se:
                L.append(f"- `{src}` → `{tgt}`")
            L.append("")
    else:
        L.append("- causal_graph.json not found")
        L.append("")

    # A.4 Span-level footprint
    L.append("### A.4 Span-level footprint (top 20)")
    if spans:
        L.append("| span | abn_succ | norm_succ | abn_ms | norm_ms |")
        L.append("|---|---|---|---|---|")
        for s in spans:
            L.append(f"| `{s['span'][:80]}` | {s['abnormal_succ_rate']} | {s['normal_succ_rate']} | {s['abnormal_avg_ms']} | {s['normal_avg_ms']} |")
    else:
        L.append("- conclusion data not available")
    L.append("")

    # A.5a Error log signatures
    L.append("### A.5a Top error log signatures (abnormal period)")
    if errors:
        for e in errors:
            svc = e.get("services", [])
            L.append(f"- ({e['count']}) `{e['signature']}`" + (f"  — {svc}" if svc else ""))
    else:
        L.append("- no error logs found")
    L.append("")

    # A.5b Log delta
    ld = d["log_delta"]
    L.append("### A.5b Log delta (abnormal vs normal period)")
    if ld:
        L.append(f"- total errors: normal={ld.get('total_nor_errors', '?')}, abnormal={ld.get('total_abn_errors', '?')}")
        L.append("")
        err_d = ld.get("error_delta") or []
        if err_d:
            L.append("**Per-service ERROR count delta:**")
            L.append("")
            L.append("| service | normal_errors | abnormal_errors | delta |")
            L.append("|---|---|---|---|")
            for row in err_d:
                L.append(f"| `{row['service']}` | {row['normal_errors']} | {row['abnormal_errors']} | {row['delta']:+d} |")
            L.append("")
        vol_d = ld.get("volume_delta") or []
        if vol_d:
            L.append("**Per-service log VOLUME delta:**")
            L.append("")
            L.append("| service | normal_total | abnormal_total | delta |")
            L.append("|---|---|---|---|")
            for row in vol_d:
                L.append(f"| `{row['service']}` | {row['normal']} | {row['abnormal']} | {row['delta']:+d} |")
            L.append("")
    else:
        L.append("- normal_logs not available for comparison")
    L.append("")

    # A.5c Trace delta
    td = d["trace_delta"]
    L.append("### A.5c Trace span delta (abnormal vs normal period)")
    if td:
        es = td.get("error_span") or {}
        if es:
            L.append(f"- Error spans: normal={es.get('normal_error_spans', 0)}, abnormal={es.get('abnormal_error_spans', 0)}")
            if es.get("error_by_service"):
                L.append(f"- Error spans by service: {es['error_by_service']}")
        hi = td.get("http_error") or {}
        if hi:
            L.append(f"- HTTP 4xx/5xx responses: normal={hi.get('normal_http_errors', 0)}, abnormal={hi.get('abnormal_http_errors', 0)}")
            if hi.get("by_service"):
                L.append(f"- HTTP errors by service: {hi['by_service']}")
        L.append("")
        span_d = td.get("span_delta") or []
        if span_d:
            L.append("**Per-service span count delta:**")
            L.append("")
            L.append("| service | normal_spans | abnormal_spans | delta |")
            L.append("|---|---|---|---|")
            for row in span_d:
                L.append(f"| `{row['service']}` | {row['normal_spans']} | {row['abnormal_spans']} | {row['delta']:+d} |")
            L.append("")
    else:
        L.append("- normal_traces not available for comparison")
    L.append("")

    # A.6 Anomalous metrics
    L.append("### A.6 Anomalous metrics (|z| ≥ 3, across gauge/sum/histogram parquets)")
    if zmetrics:
        L.append("| service | metric | normal | abnormal | z | source |")
        L.append("|---|---|---|---|---|---|")
        for m in zmetrics:
            z_val = m['z']
            z_str = f"{z_val:.2f}" if z_val is not None else "?"
            L.append(f"| {m['service']} | {m['metric']} | {m['normal_mean']} | {m['abnormal_mean']} | {z_str} | {m.get('source', '')} |")
    else:
        L.append("- no metrics exceeding threshold in any of the 3 metric parquets")
    L.append("")

    # A.7 K8s state
    L.append("### A.7 K8s state (pods & events for GT-related services)")
    if k8s:
        for item in k8s:
            if item.get("kind") == "Pod":
                L.append(f"- Pod `{item['name']}` container=`{item.get('container')}` restartCount={item.get('restartCount')} ready={item.get('ready')} state={item.get('state')}")
            elif item.get("kind") == "Event":
                L.append(f"- Event `{item['name']}` reason={item.get('reason')} count={item.get('count')}: {item.get('message', '')[:200]}")
    else:
        L.append("- k8s.json not found or no matching entries")
    L.append("")

    # A.8 result.json propagation paths
    rj = d["result_json"]
    L.append("### A.8 GT propagation paths (from result.json)")
    if rj and rj.get("paths"):
        L.append(f"- injection_nodes: {rj.get('injection_nodes')}")
        L.append(f"- injection_states: {rj.get('injection_states')}")
        L.append(f"- propagation paths: {len(rj['paths'])}")
        L.append("")
        for pi, path in enumerate(rj["paths"][:5], 1):
            L.append(f"**Path {pi}** (confidence={path.get('confidence')})")
            L.append("")
            states = path.get("states") or []
            edges = path.get("edges") or []
            delays = path.get("propagation_delays") or []
            L.append("| step | node_id | states | edge_to_next | delay(s) |")
            L.append("|---|---|---|---|---|")
            for si, node_id in enumerate(path.get("node_ids") or []):
                st = states[si] if si < len(states) else []
                edge = edges[si] if si < len(edges) else ""
                delay = delays[si] if si < len(delays) else ""
                L.append(f"| {si} | {node_id} | {st} | {edge} | {delay} |")
            L.append("")
    else:
        L.append("- result.json not found or no propagation paths")
    L.append("")

    # A.9 abnormal_connection
    ac = d["abnormal_connection"]
    L.append("### A.9 Infrastructure topology (from abnormal_connection/)")
    if ac:
        ac_nodes = ac.get("nodes") or []
        if ac_nodes:
            L.append(f"**Abnormal nodes** ({len(ac_nodes)} pods/components with anomalies):")
            L.append("")
            L.append("| kind | name | state |")
            L.append("|---|---|---|")
            for n in ac_nodes:
                L.append(f"| {n['kind']} | `{n['node_name']}` | {n['state']} |")
            L.append("")
        pp = ac.get("propagation_patterns") or []
        if pp:
            L.append(f"**Propagation patterns** ({len(pp)} edges with metric data):")
            L.append("")
            L.append("| src → dst | pattern | dst_state | latency_ratio | error_delta |")
            L.append("|---|---|---|---|---|")
            for p in pp:
                L.append(f"| `{p['src']}` → `{p['dst']}` | {p['pattern']} | {p['dst_state']} | {p['latency_ratio']} | {p['error_delta']} |")
            L.append("")
    else:
        L.append("- abnormal_connection/ not available for this case")
    L.append("")

    # A.10 Signal observability summary
    L.append("### A.10 Signal observability summary")
    L.append("")
    has_error_logs = len(errors) > 0
    has_metric_anomaly = len(zmetrics) > 0
    has_span_anomaly = len(spans) > 0
    has_k8s_restart = any(item.get("restartCount", 0) > 0 for item in k8s if item.get("kind") == "Pod")
    L.append(f"- error logs (ERROR/SEVERE in abnormal period): {'yes' if has_error_logs else 'no'}")
    L.append(f"- metric anomalies (z>3): {'yes' if has_metric_anomaly else 'no'}")
    L.append(f"- span success/latency anomalies: {'yes' if has_span_anomaly else 'no'}")
    L.append(f"- k8s pod restarts (restartCount>0): {'yes' if has_k8s_restart else 'no'}")
    L.append(f"- result.json propagation paths: {'yes' if rj and rj.get('paths') else 'no'}")
    L.append(f"- abnormal_connection data: {'yes' if ac else 'no'}")
    if d["log_delta"]:
        L.append("- log delta available: yes")
    if d["trace_delta"]:
        L.append("- trace delta available: yes")
    L.append("")

    # ── PART B (aiq-specific) ──
    L.append("## Part B — Agent trajectory (what the agent did)")
    L.append("")

    # B.0 Prompt to agent
    aq = d.get("augmented_question") or ""
    if aq:
        L.append("### B.0 Prompt received by agent (augmented_question)")
        L.append("```")
        L.append(aq)
        L.append("```")
        L.append("")

    # B.1 Final answer + predicted graph
    L.append("### B.1 Final answer")
    pred_rc = cge.get("root_cause_services") or []
    L.append(f"- predicted root_cause_services: {pred_rc}")
    L.append(f"- judged correct: {cge.get('correct')}")
    if cge.get("reasoning"):
        L.append(f"- judge reasoning: {cge['reasoning']}")
    L.append("")
    resp_json = d.get("response_json")
    if resp_json:
        L.append("**Agent's full predicted causal graph:**")
        L.append("")
        pred_nodes = resp_json.get("nodes") or []
        if pred_nodes:
            L.append("| component | state | timestamp |")
            L.append("|---|---|---|")
            for pn in pred_nodes:
                if isinstance(pn, dict):
                    L.append(f"| `{pn.get('component', '?')}` | {pn.get('state', [])} | {pn.get('timestamp', '')} |")
            L.append("")
        pred_edges = resp_json.get("edges") or []
        if pred_edges:
            L.append(f"Predicted edges ({len(pred_edges)}):")
            L.append("")
            for pe in pred_edges[:30]:
                if isinstance(pe, dict):
                    L.append(f"- `{pe.get('source', '?')}` → `{pe.get('target', '?')}`")
            if len(pred_edges) > 30:
                L.append(f"- ... ({len(pred_edges)} total)")
            L.append("")
        pred_rcs = resp_json.get("root_causes") or []
        if pred_rcs:
            L.append(f"Predicted root_causes: {pred_rcs}")
            L.append("")
    L.append("")

    # B.2 Graph metrics diagnostic
    L.append("### B.2 Graph metrics diagnostic")
    L.append(f"- matched_services: {gm.get('matched_services') or []}")
    L.append(f"- missed_services: {gm.get('missed_services') or []}")
    L.append(f"- hallucinated_services: {gm.get('hallucinated_services') or []}")
    L.append(f"- matched_service_edges: {gm.get('matched_service_edges') or []}")
    L.append(f"- missed_service_edges: {gm.get('missed_service_edges') or []}")
    L.append(f"- hallucinated_service_edges: {gm.get('hallucinated_service_edges') or []}")
    L.append("")

    # B.3 Cost
    L.append("### B.3 Cost signature")
    L.append(f"- effective_rounds: {cm.get('effective_rounds')}")
    L.append(f"- total_tokens: {cm.get('total_tokens')}")
    L.append(f"- time_cost: {cm.get('time_cost')}")
    L.append(f"- model: {cm.get('model')}")
    L.append("")

    # B.4 aiq pipeline stage summary
    L.append("### B.4 Pipeline stage summary (aiq-specific)")
    L.append("")
    L.append(f"- total rounds: {len(rounds)}")
    L.append(f"- terminator count: {summary.get('terminator_count')}/3")
    L.append(f"- truncated stages (hit max_rounds): {summary.get('truncated_stages')}")
    L.append(f"- final status: **{summary.get('final_stage_status')}**")
    L.append("")
    # Per-stage round counts
    from collections import Counter
    stage_counts = Counter(r.pipeline_stage for r in rounds)
    if stage_counts:
        L.append("**Rounds per pipeline stage:**")
        L.append("")
        L.append("| stage | rounds |")
        L.append("|---|---|")
        for label, n in stage_counts.items():
            L.append(f"| {label} | {n} |")
        L.append("")
    # Hypothesis at each stage terminator
    if terminators:
        L.append("**Hypothesis at each stage terminator** (regex-extracted root-cause service mention):")
        L.append("")
        L.append("| stage_closed | after_round | content_len | extracted_hypothesis |")
        L.append("|---|---|---|---|")
        for t in terminators:
            hyp = extract_hypothesis(t.content)
            L.append(f"| {t.stage_closed} | {t.after_round} | {t.char_count} | `{hyp}` |")
        L.append("")

    # B.5 Stage terminators (full text — these are the agent's conclusions)
    L.append("### B.5 Stage terminator conclusions (full text)")
    L.append("")
    L.append("These are assistant messages where the LLM chose to stop calling tools and write a conclusion,")
    L.append("terminating each sub-loop. If a stage has no terminator, that sub-loop hit max_rounds and was")
    L.append("force-serialized into findings without an LLM conclusion step.")
    L.append("")
    if terminators:
        for ti, t in enumerate(terminators, 1):
            L.append(f"#### Terminator {ti} — closes `{t.stage_closed}` (after round {t.after_round})")
            L.append("")
            L.append("```")
            for line in t.content.splitlines():
                L.append(line)
            L.append("```")
            L.append("")
    else:
        L.append("- **NO terminators** — all sub-loops hit max_rounds and returned serialized tool history as findings.")
    L.append("")

    # B.6 Full trajectory round-by-round (grouped by pipeline stage)
    L.append("### B.6 Full round-by-round trajectory")
    L.append(f"- (raw trajectory JSON: `case_{dsi}.raw.json`)")
    L.append("")

    # Group rounds by pipeline_stage in order of first appearance
    stage_order: list[str] = []
    for r in rounds:
        if r.pipeline_stage not in stage_order:
            stage_order.append(r.pipeline_stage)

    for stage_label in stage_order:
        stage_rounds = [r for r in rounds if r.pipeline_stage == stage_label]
        L.append(f"#### ── Pipeline stage: `{stage_label}` ({len(stage_rounds)} rounds) ──")
        L.append("")
        # Interleave any terminator that closes this stage at the appropriate point
        term_for_stage = next((t for t in terminators if t.stage_closed == stage_label), None)
        for r in stage_rounds:
            hyp = extract_hypothesis(r.think)
            intents_r = intent_by_round.get(r.index, [])
            intent_tag = round_intent_tag(intents_r)
            intent_tags = [f"{i.get('intent', '')}({i.get('data_type', '')})" for i in intents_r]

            L.append(f"##### Round {r.index}  [stage={stage_label} intent_stage={intent_tag}]")
            if hyp:
                L.append(f"- **hypothesis_at_round**: `{hyp}`")
            if intent_tags:
                L.append(f"- intents: {intent_tags}")
            if r.think:
                L.append("- reasoning (think_tool.reflection and/or assistant.content):")
                for line in r.think.strip().splitlines():
                    L.append(f"  > {line}")
            for i, t in enumerate(r.tools, 1):
                L.append(f"- tool[{i}] `{t['name']}` services={t['services']}")
                L.append("  ```")
                L.append(f"  {t['args_full']}")
                L.append("  ```")
            for j, tr in enumerate(r.results, 1):
                L.append(f"- result[{j}]:")
                if tr.error_snippets:
                    L.append(f"  - **error_keywords**: {tr.error_snippets}")
                if tr.services_mentioned:
                    L.append(f"  - **services_in_result**: {tr.services_mentioned}")
                if tr.row_count is not None and tr.row_count > 0:
                    L.append(f"  - rows: ~{tr.row_count}")
                L.append("  ```")
                for line in tr.display.splitlines():
                    L.append(f"  {line}")
                L.append("  ```")
            L.append("")
        if term_for_stage:
            L.append(f"**→ stage terminator (after round {term_for_stage.after_round}, {term_for_stage.char_count} chars — closes `{stage_label}`)**")
            L.append("")
        elif stage_label.endswith("_truncated"):
            L.append(f"**→ stage ended at max_rounds (no natural conclusion for `{stage_label}`)**")
            L.append("")

    # Footer for analyst
    L.append("---")
    L.append("")
    L.append("## Analyst section (fill during per-case analysis)")
    L.append("")
    L.append("- **pivot_round**: <int>")
    L.append("- **pipeline_stage_at_pivot**: <stage label or 'truncated'>")
    L.append("- **proximate_cause** (short phrase): ")
    L.append("")

    return "\n".join(L)


# ── Main loop ──────────────────────────────────────────────────────────────


def get_engine(db_url: str):
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(db_url, connect_args=connect_args)


def iter_failed_cases(engine, exp_id: str, limit: int | None):
    with Session(engine) as session:
        stmt = select(EvaluationSample).where(
            EvaluationSample.exp_id == exp_id,
            EvaluationSample.correct == False,  # noqa: E712
            EvaluationSample.stage == "judged",
        )
        samples = session.exec(stmt).all()
    samples.sort(key=lambda s: s.dataset_index or 0)
    if limit:
        samples = samples[:limit]
    return samples


def build_one(sample: EvaluationSample) -> dict:
    meta = sample.meta or {}
    src_dir = tdt.find_source_dir(meta)
    gt_svcs = meta.get("ground_truth") or []

    inj_full = tdt.load_injection_full(src_dir) if src_dir else {}
    cg_full = tdt.load_causal_graph_full(src_dir) if src_dir else {}
    k8s_targets = list(set(gt_svcs + (inj_full.get("gt_services") or [])))
    k8s_summary = tdt.load_k8s_summary(src_dir, k8s_targets) if src_dir else []
    result_json = tdt.load_result_json(src_dir) if src_dir else {}
    abn_conn = tdt.load_abnormal_connection(src_dir) if src_dir else {}
    log_delta = tdt.log_delta_per_service(src_dir) if src_dir else {}
    trace_delta = tdt.trace_delta_per_service(src_dir) if src_dir else {}
    conclusion_df = tdt.load_conclusion(src_dir) if src_dir else None
    spans = tdt.top_anomalous_spans(conclusion_df) if conclusion_df is not None else []
    errors = tdt.top_error_logs(src_dir) if src_dir else []
    zmetrics = tdt.zscore_anomalous_metrics(src_dir) if src_dir else []

    rounds, terminators, summary = parse_aiq_trajectory(sample.trajectories)
    intent_by_round = intent_overlay(meta)

    response_json = None
    if sample.response:
        try:
            response_json = json.loads(sample.response)
        except json.JSONDecodeError:
            pass

    return {
        "dataset_index": sample.dataset_index,
        "exp_id": sample.exp_id,
        "meta": meta,
        "src_dir": src_dir,
        "injection_full": inj_full,
        "causal_graph_full": cg_full,
        "k8s_summary": k8s_summary,
        "spans": spans,
        "errors": errors,
        "zmetrics": zmetrics,
        "rounds": rounds,
        "terminators": terminators,
        "trajectory_summary": summary,
        "intent_by_round": intent_by_round,
        "log_delta": log_delta,
        "trace_delta": trace_delta,
        "raw_trajectory": sample.trajectories,
        "augmented_question": sample.augmented_question,
        "response_json": response_json,
        "result_json": result_json,
        "abnormal_connection": abn_conn,
    }


def write_index(out_dir: Path, rows: list[dict]) -> None:
    L = ["# Dossier index — aiq-qwen3.5-plus (v1)", ""]
    L.append(f"- total failed cases: {len(rows)}")
    L.append("")
    # Summary of terminator distribution
    from collections import Counter
    status_counter = Counter(r["trajectory_summary"].get("final_stage_status") for r in rows)
    L.append("**Final stage status distribution:**")
    L.append("")
    for status, n in status_counter.most_common():
        L.append(f"- {status}: {n}")
    L.append("")
    L.append("| dataset_index | fault_category | fault_type | n_svc | spl | rounds | terminators | status | file |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        d = (r["meta"].get("difficulty") or {})
        fc = d.get("fault_category", "?")
        ft = d.get("fault_type", "?")
        n_svc = d.get("n_svc", "?")
        spl = d.get("spl", "?")
        nr = len(r["rounds"])
        nt = r["trajectory_summary"].get("terminator_count", 0)
        status = r["trajectory_summary"].get("final_stage_status", "?")
        dsi = r["dataset_index"]
        L.append(f"| {dsi} | {fc} | {ft} | {n_svc} | {spl} | {nr} | {nt} | {status} | [case_{dsi}.md](case_{dsi}.md) |")
    (out_dir / "index.md").write_text("\n".join(L), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description="aiq-qwen3.5-plus failure-mode dossier builder")
    p.add_argument("--db", required=True, help="DB URL")
    p.add_argument("--exp_id", default="aiq-qwen3.5-plus")
    p.add_argument("--out_dir", required=True, help="Output directory for case_<idx>.md files")
    p.add_argument("--limit", type=int, default=None, help="Process only first N failed cases")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    engine = get_engine(args.db)
    samples = iter_failed_cases(engine, args.exp_id, args.limit)
    logger.info("Building dossiers for %d failed cases (exp_id=%s)", len(samples), args.exp_id)

    rows: list[dict] = []
    for i, s in enumerate(samples, 1):
        row = build_one(s)
        md = render_dossier(row)
        md_path = out_dir / f"case_{s.dataset_index}.md"
        md_path.write_text(md, encoding="utf-8")
        raw_path = out_dir / f"case_{s.dataset_index}.raw.json"
        raw_path.write_text(row.get("raw_trajectory") or "[]", encoding="utf-8")
        rows.append(row)
        logger.info("[%d/%d] wrote %s  rounds=%d terminators=%d status=%s src=%s",
                    i, len(samples), md_path.name, len(row["rounds"]),
                    row["trajectory_summary"].get("terminator_count", 0),
                    row["trajectory_summary"].get("final_stage_status", "?"),
                    row["src_dir"])

    write_index(out_dir, rows)
    logger.info("Done. Index at %s", out_dir / "index.md")


if __name__ == "__main__":
    main()
