#!/usr/bin/env python
"""Generate a standalone HTML visualization of an agent's reasoning trajectory.

Usage:
    # From DB
    uv run python scripts/viz_trajectory.py \
        --exp_id thinkdepthai-claude-sonnet-4.6 \
        --dataset_index 42 \
        --output trace.html

    # From pre-exported JSON (fully decoupled, no DB needed)
    uv run python scripts/viz_trajectory.py --json payload.json --output trace.html

    # Export JSON only (for migration / debugging)
    uv run python scripts/viz_trajectory.py \
        --exp_id thinkdepthai-claude-sonnet-4.6 \
        --dataset_index 42 \
        --export-json payload.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path

# ---------------------------------------------------------------------------
# Minimal inline helpers — self-contained, no project imports needed
# ---------------------------------------------------------------------------

# Known services in TrainTicket (copied for decoupling; authoritative list in
# extractor.py but we only need it for zone classification)
_KNOWN_SERVICES: set[str] = {
    "ts-route-plan-service", "ts-travel-service", "ts-travel2-service",
    "ts-preserve-service", "ts-travel-plan-service", "ts-cancel-service",
    "ts-basic-service", "ts-order-service", "ts-route-service",
    "ts-seat-service", "ts-order-other-service", "ts-train-service",
    "ts-station-service", "ts-inside-payment-service", "ts-payment-service",
    "ts-food-service", "ts-security-service", "ts-user-service",
    "ts-config-service", "ts-consign-service", "ts-contacts-service",
    "ts-auth-service", "ts-price-service", "ts-assurance-service",
    "ts-train-food-service", "ts-station-food-service",
    "ts-verification-code-service", "ts-consign-price-service",
    "ts-ui-dashboard",
    "ts-delivery-service", "ts-food-delivery-service", "ts-notification-service",
    "ts-food-map-service",
    "ts-news-service", "ts-rebook-service", "ts-ticket-office-service",
    "ts-voucher-service", "ts-admin-service", "ts-execute-service",
    "ts-admin-basic-info-service", "ts-admin-order-service",
    "ts-admin-route-service", "ts-admin-travel-service", "ts-admin-user-service",
    "ts-avatar-service", "ts-gateway-service",
    "ts-preserve-other-service",
}
_NON_TS_SERVICES: set[str] = {
    "loadgenerator", "mysql", "redis", "rabbitmq", "nacos", "mongodb", "kafka", "zookeeper",
}
_ALL_KNOWN: set[str] = _KNOWN_SERVICES | _NON_TS_SERVICES

# Normalized form -> canonical
_NORM_TO_CANONICAL: dict[str, str] = {}
for _svc in _ALL_KNOWN:
    _norm = _svc.strip().lower().replace("-", "").replace("_", "")
    if _norm.startswith("ts"):
        _norm_no_prefix = _norm[2:]
    else:
        _norm_no_prefix = _norm
    _NORM_TO_CANONICAL[_norm] = _svc
    _NORM_TO_CANONICAL[_norm_no_prefix] = _svc


def _normalize(name: str) -> str:
    return name.strip().lower().replace("-", "").replace("_", "")


# Pod name patterns for K8s: service-<replicaset>-<pod> or service-<hash>
# ReplicaSet hash: 8-10 alphanumeric chars with at least one digit
# Pod hash: 1-6 alphanumeric chars
_POD_SUFFIX = re.compile(r"-(?=[a-z0-9]*\d)[a-z0-9]{7,12}-[a-z0-9]{1,6}$")
# Single hash suffix: -<digit-containing-hash> (e.g., -5, -58879bf4df)
_POD_SUFFIX2 = re.compile(r"-(?=\d)[a-z0-9]{1,12}$")


def _strip_pod_suffix(name: str) -> str:
    """Strip K8s pod hash suffixes: ts-foo-service-5cc86cdd64-lqpr6 → ts-foo-service"""
    name = _POD_SUFFIX.sub("", name)
    name = _POD_SUFFIX2.sub("", name)
    return name


def resolve_known(name: str) -> str | None:
    """Resolve a candidate name to a known canonical service, or None.

    Handles: exact match, normalized match, pod names, truncated names.
    """
    # 1. Direct normalized match
    n = _normalize(name)
    if n.startswith("ts"):
        n_no = n[2:]
    else:
        n_no = n
    result = _NORM_TO_CANONICAL.get(n) or _NORM_TO_CANONICAL.get(n_no)
    if result:
        return result

    # 2. Strip pod suffix and retry
    stripped = _strip_pod_suffix(name)
    if stripped != name:
        return resolve_known(stripped)

    # 3. Truncated name: check if any known service starts with this prefix
    #    (only if the candidate is at least 5 chars after ts- to avoid false positives)
    if name.startswith("ts-") and len(name) >= 6:
        for svc in _ALL_KNOWN:
            if svc.startswith(name) and svc != name:
                return svc

    return None


def is_known_service(name: str) -> bool:
    return resolve_known(name) is not None


# ---------------------------------------------------------------------------
# Service extraction from SQL (lightweight, self-contained)
# ---------------------------------------------------------------------------

_SVC_PATTERN = re.compile(r"ts-[a-z0-9][-a-z0-9]*(?:-service)?", re.IGNORECASE)
_LIKE_PATTERN = re.compile(r"service_name\s+(?:I?LIKE)\s+['\"]%?([^'\"]+)%?['\"]", re.IGNORECASE)
# Match service_name = 'xxx' or IN ('xxx', 'yyy') — catches non-ts services like mysql
_EQ_PATTERN = re.compile(r"service_name\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
_IN_PATTERN = re.compile(r"service_name\s+IN\s*\(([^)]+)\)", re.IGNORECASE)
_QUOTED = re.compile(r"['\"]([^'\"]+)['\"]")


def extract_services_from_text(text: str) -> list[str]:
    """Extract service names from any text (SQL, tool args, file paths)."""
    found: list[str] = []
    seen: set[str] = set()

    def _add(candidate: str):
        canonical = resolve_known(candidate)
        if canonical and canonical not in seen:
            found.append(canonical)
            seen.add(canonical)

    # Direct ts-xxx mentions
    for m in _SVC_PATTERN.finditer(text):
        _add(m.group())

    # service_name = 'xxx'
    for m in _EQ_PATTERN.finditer(text):
        _add(m.group(1))

    # service_name IN ('xxx', 'yyy')
    for m in _IN_PATTERN.finditer(text):
        for qm in _QUOTED.finditer(m.group(1)):
            _add(qm.group(1))

    # service_name LIKE '%xxx%'
    for m in _LIKE_PATTERN.finditer(text):
        _add(m.group(1))

    # Non-ts known services by exact word match (mysql, redis, nacos, etc.)
    for svc in _NON_TS_SERVICES:
        if svc not in seen and re.search(r"\b" + re.escape(svc) + r"\b", text, re.IGNORECASE):
            found.append(svc)
            seen.add(svc)

    return found


# ---------------------------------------------------------------------------
# Intent classification (simplified, covers the 19 categories)
# ---------------------------------------------------------------------------

def classify_intent(sql: str, tool_name: str, data_type: str) -> str:
    """Minimal intent check — only distinguishes 'discovery' from real SQL.

    Actual 19-category intent classification comes from LLM labels in
    meta.llm_intents, overlaid by _overlay_llm_intents().
    """
    if not sql or "SELECT" not in sql.upper():
        return "discovery"
    return "unknown"


def detect_data_type(sql: str, tool_args: str = "") -> str:
    """Detect data type from SQL or tool arguments."""
    combined = (sql + " " + tool_args).lower()
    if "metrics" in combined or "metric" in combined:
        return "metrics"
    if "log" in combined:
        return "logs"
    if "trace" in combined or "span" in combined:
        return "traces"
    return "unknown"


# ---------------------------------------------------------------------------
# Step extraction from OpenAI-format trajectory
# ---------------------------------------------------------------------------

def extract_steps(trajectory: list[dict]) -> list[dict]:
    """Extract structured steps from OpenAI-format trajectory.

    Returns a list of step dicts (plain JSON-serializable, no dataclasses).
    """
    if not trajectory:
        return []

    # Build tool_call_id -> result mapping
    results_by_id: dict[str, str] = {}
    for msg in trajectory:
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            results_by_id[msg["tool_call_id"]] = msg.get("content", "")

    steps: list[dict] = []
    step_index = 0
    assistant_turn_index = 0
    pending_thought = ""

    for msg in trajectory:
        if msg.get("role") != "assistant":
            continue
        assistant_turn_index += 1
        tool_calls = msg.get("tool_calls") or []

        # Accumulate thought from content
        content = msg.get("content") or ""

        # Check for think_tool calls (accumulate as thought, don't create step)
        real_calls = []
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            if name == "think" or name == "think_tool":
                args = fn.get("arguments", "")
                if isinstance(args, str):
                    try:
                        args_parsed = json.loads(args)
                        pending_thought += " " + args_parsed.get("thought", args_parsed.get("content", ""))
                    except json.JSONDecodeError:
                        pending_thought += " " + args
                continue
            real_calls.append(tc)

        if content:
            pending_thought += " " + content

        for tc in real_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args_raw = fn.get("arguments", "{}")
            tc_id = tc.get("id", "")

            # Parse SQL from arguments
            if isinstance(args_raw, str):
                try:
                    args_dict = json.loads(args_raw)
                except json.JSONDecodeError:
                    args_dict = {}
            else:
                args_dict = args_raw

            sql = args_dict.get("sql", args_dict.get("query", ""))
            tool_args_str = json.dumps(args_dict)

            # Skip schema discovery tools
            if name in ("list_tables_in_directory", "get_schema", "list_tables"):
                pending_thought = ""
                continue

            data_type = detect_data_type(sql, tool_args_str)
            intent = classify_intent(sql, name, data_type)
            if intent == "discovery":
                pending_thought = ""
                continue

            # Extract services from SQL + tool arguments
            action_services = extract_services_from_text(sql + " " + tool_args_str)
            result_content = results_by_id.get(tc_id, "")
            result_is_error = bool(re.search(r"error|exception|traceback", result_content[:200], re.IGNORECASE))

            # Extract services from result content (agent "saw" these)
            result_services = extract_services_from_text(result_content[:3000])

            # Merge: action + result, dedup preserving order
            all_services = list(action_services)
            seen_svc = set(action_services)
            for rs in result_services:
                if rs not in seen_svc:
                    all_services.append(rs)
                    seen_svc.add(rs)

            # Detect hallucinated services: ts-xxx patterns not in whitelist
            hallucinated = []
            halluc_seen: set[str] = set()
            for text in [sql, result_content[:3000]]:
                for m in _SVC_PATTERN.finditer(text):
                    candidate = m.group()
                    if not is_known_service(candidate) and candidate not in halluc_seen:
                        hallucinated.append(candidate)
                        halluc_seen.add(candidate)

            category = _INTENT_TO_CATEGORY.get(intent, "triage")
            steps.append({
                "index": step_index,
                "assistant_turn_index": assistant_turn_index,
                "thought": pending_thought.strip()[:300] if pending_thought.strip() else None,
                "tool_name": name,
                "sql": sql,
                "data_type": data_type,
                "intent": intent,
                "intent_category": category,
                "services": all_services,
                "action_services": action_services,
                "hallucinated": hallucinated,
                "result_is_error": result_is_error,
            })
            step_index += 1
            pending_thought = ""

    return steps


# ---------------------------------------------------------------------------
# GT graph helpers
# ---------------------------------------------------------------------------

def _component_to_service_fallback(component: str) -> str:
    """Fallback: extract service name from span/URL patterns."""
    # Try URL pattern: http://ts-xxx-service:port/...
    m = re.search(r"https?://(ts-[a-z0-9-]+?)(?::\d+)?/", component)
    if m:
        return m.group(1)
    # Try span|ServiceClass.method or span|POST /api/v1/xxxservice/...
    m = re.search(r"/api/v1/([a-z_]+service)/", component)
    if m:
        # Convert URL path style to ts-xxx-service style
        svc_path = m.group(1).replace("_", "-")
        canonical = resolve_known(svc_path)
        if canonical:
            return canonical
    # Strip span| or service| prefix
    if "|" in component:
        component = component.split("|", 1)[1]
    return component


def load_causal_graph(data_dir: str | Path) -> dict | None:
    """Load causal_graph.json and return a service-level simplified structure."""
    path = Path(data_dir) / "causal_graph.json"
    if not path.exists():
        return None
    with open(path) as f:
        raw = json.load(f)

    c2s = raw.get("component_to_service", {})

    def to_service(component: str) -> str:
        mapped = c2s.get(component)
        if mapped:
            return mapped
        return _component_to_service_fallback(component)

    # Aggregate to service level (dedup)
    nodes: set[str] = set()
    for n in raw.get("nodes", []):
        nodes.add(to_service(n.get("component", "")))
    # Remove loadgenerator (traffic generator, not part of SUT)
    nodes.discard("loadgenerator")

    edges: list[tuple[str, str]] = []
    edge_set: set[tuple[str, str]] = set()
    for e in raw.get("edges", []):
        src = to_service(e.get("source", ""))
        tgt = to_service(e.get("target", ""))
        if src != tgt and (src, tgt) not in edge_set:
            edges.append((src, tgt))
            edge_set.add((src, tgt))

    root_causes: set[str] = set()
    for rc in raw.get("root_causes", []):
        root_causes.add(to_service(rc.get("component", "")))

    alarms: set[str] = set()
    for a in raw.get("alarm_nodes", []):
        alarms.add(to_service(a.get("component", "")))

    # Remove loadgenerator from all sets and edges (traffic generator, not SUT)
    _excluded = {"loadgenerator"}
    nodes -= _excluded
    root_causes -= _excluded
    alarms -= _excluded
    edges = [(s, t) for s, t in edges if s not in _excluded and t not in _excluded]

    # If all alarms were removed, promote leaf nodes (no outgoing edges) as alarms
    if not alarms:
        sources = {s for s, _ in edges}
        targets = {t for _, t in edges}
        leaves = (nodes - sources) & targets  # nodes with incoming but no outgoing
        if leaves:
            alarms = leaves
        else:
            # Fallback: nodes at max BFS distance from root
            alarms = nodes - root_causes if len(nodes) > 1 else set()

    return {
        "nodes": sorted(nodes),
        "edges": edges,
        "root_causes": sorted(root_causes),
        "alarms": sorted(alarms),
    }


def compute_distance_to_root(
    service: str,
    root_causes: set[str],
    edges: list[tuple[str, str]],
) -> int | None:
    """BFS distance from service to nearest root cause (reverse edges)."""
    norm = _normalize(service)
    root_norm = {_normalize(r) for r in root_causes}
    if norm in root_norm:
        return 0

    # reverse adjacency: target -> [sources]
    rev: dict[str, list[str]] = {}
    for src, tgt in edges:
        sn, tn = _normalize(src), _normalize(tgt)
        rev.setdefault(tn, []).append(sn)

    visited = {norm}
    queue: deque[tuple[str, int]] = deque([(norm, 0)])
    while queue:
        cur, dist = queue.popleft()
        for nb in rev.get(cur, []):
            if nb in root_norm:
                return dist + 1
            if nb not in visited:
                visited.add(nb)
                queue.append((nb, dist + 1))
    return None


# ---------------------------------------------------------------------------
# Transition classification (self-contained, mirrors triplet_coherence.py)
# ---------------------------------------------------------------------------

_LABEL_DESCRIPTIONS = {
    "advancing:consecutive": "沿因果链前进到相邻节点",
    "advancing:skip": "跳过中间节点向根因前进",
    "lateral:revisit": "同层重访已访问节点",
    "lateral:explore": "同层探索新节点",
    "regressing:backtrack": "回退到已访问的下游节点",
    "regressing:explore": "向下游探索新节点",
    "returned:revisit": "从偏离路径返回，重访已知节点",
    "returned:discover": "从偏离路径返回，发现新节点",
    "drifted": "偏离 GT 因果路径",
    "derailed": "前后两轮都不在 GT 路径上",
}

_INTENT_DESCRIPTIONS = {
    "latency_ranking": "Global service latency ranking",
    "throughput_compare": "Global throughput comparison",
    "error_rate_scan": "Global error rate scan",
    "service_trace_scan": "Service trace inspection",
    "trace_follow": "Single request trace follow",
    "call_tree_build": "Build call dependency tree",
    "error_log_overview": "Global error log overview",
    "service_error_log": "Service error log check",
    "service_log_browse": "Browse service logs",
    "keyword_search": "Keyword search",
    "error_timeline": "Error timeline analysis",
    "metric_scan": "Explore / browse metrics",
    "container_resource": "Container resource (CPU/Memory)",
    "jvm_state": "JVM state (GC/thread/pool)",
    "network_layer": "Network layer metrics",
    "k8s_state": "K8s state (pod/restart)",
    "db_state": "Database state (connections)",
    "baseline_collect": "Collect baseline data",
    "baseline_contrast": "Baseline vs abnormal comparison",
    "discovery": "Schema discovery",
}

# 5-stage intent categories (cognitive depth)
_INTENT_TO_CATEGORY = {
    "latency_ranking": "triage",
    "throughput_compare": "triage",
    "error_rate_scan": "triage",
    "error_log_overview": "triage",
    "metric_scan": "triage",
    "service_trace_scan": "trace_investigate",
    "trace_follow": "trace_investigate",
    "call_tree_build": "trace_investigate",
    "service_error_log": "log_investigate",
    "service_log_browse": "log_investigate",
    "keyword_search": "log_investigate",
    "error_timeline": "log_investigate",
    "container_resource": "metric_diagnose",
    "jvm_state": "metric_diagnose",
    "network_layer": "metric_diagnose",
    "k8s_state": "metric_diagnose",
    "db_state": "metric_diagnose",
    "baseline_collect": "baseline",
    "baseline_contrast": "baseline",
    "discovery": "triage",
}

_CATEGORY_LABELS = {
    "triage": "Triage",
    "trace_investigate": "Trace",
    "log_investigate": "Log",
    "metric_diagnose": "Diagnose",
    "baseline": "Baseline",
}

_CATEGORY_COLORS = {
    "triage": "#ffee58",
    "trace_investigate": "#00e5ff",
    "log_investigate": "#69f0ae",
    "metric_diagnose": "#ff9100",
    "baseline": "#b388ff",
}


def classify_transitions(
    rounds: list[dict],
    gt_nodes: set[str],
    root_causes: set[str],
    edges: list[tuple[str, str]],
) -> list[dict]:
    """Classify transitions between adjacent Rounds."""
    transitions: list[dict] = []
    if len(rounds) < 2:
        return transitions

    gt_norm = {_normalize(s) for s in gt_nodes}
    visited_norm: set[str] = set()

    for i in range(len(rounds) - 1):
        prev_r = rounds[i]
        next_r = rounds[i + 1]

        # Mark prev round as visited BEFORE checking next round
        for svc in prev_r["all_services"]:
            visited_norm.add(_normalize(svc))

        prev_svc = prev_r["primary_service"]
        next_svc = next_r["primary_service"]

        prev_on = _normalize(prev_svc) in gt_norm
        next_on = _normalize(next_svc) in gt_norm

        prev_dist = prev_r["distance_to_root"]
        next_dist = next_r["distance_to_root"]

        next_visited = _normalize(next_svc) in visited_norm

        label = _classify_one(prev_on, next_on, prev_dist, next_dist, next_visited)

        transitions.append({
            "from_round": prev_r["round_index"],
            "to_round": next_r["round_index"],
            "label": label,
            "prev_dist": prev_dist,
            "next_dist": next_dist,
        })

    return transitions


def _classify_one(
    prev_on: bool, next_on: bool,
    prev_dist: int | None, next_dist: int | None,
    next_visited: bool,
) -> str:
    # Both off path
    if not prev_on and not next_on:
        return "derailed"

    # Drifted off path
    if prev_on and not next_on:
        return "drifted"

    # Returned to path
    if not prev_on and next_on:
        return "returned:revisit" if next_visited else "returned:discover"

    # Both on path
    if prev_dist is not None and next_dist is not None:
        if next_dist < prev_dist:
            diff = prev_dist - next_dist
            return "advancing:consecutive" if diff == 1 else "advancing:skip"
        elif next_dist == prev_dist:
            return "lateral:revisit" if next_visited else "lateral:explore"
        else:
            return "regressing:backtrack" if next_visited else "regressing:explore"

    return "lateral:explore"


# ---------------------------------------------------------------------------
# Primary node selection for a Round
# ---------------------------------------------------------------------------

def select_primary_service(
    services: list[str],
    root_causes: set[str],
    gt_nodes: set[str],
    edges: list[tuple[str, str]],
    visited_norm: set[str],
    visit_counts: dict[str, int],
) -> str | None:
    """Pick the best primary service for a Round.

    Priority chain:
    1. Shortest distance to root cause
    2. Unvisited > visited
    3. Among visited, higher query count wins
    4. Tie → first in list
    """
    if not services:
        return None

    gt_norm = {_normalize(s) for s in gt_nodes}

    def sort_key(svc: str) -> tuple:
        n = _normalize(svc)
        on_gt = n in gt_norm
        raw_dist = compute_distance_to_root(svc, root_causes, edges) if on_gt else None
        dist = raw_dist if raw_dist is not None else 999
        is_visited = n in visited_norm
        count = visit_counts.get(n, 0)
        # Sort: lowest dist first, then unvisited first, then highest count first
        return (dist, is_visited, -count)

    return min(services, key=sort_key)


# ---------------------------------------------------------------------------
# Round aggregation
# ---------------------------------------------------------------------------

def aggregate_rounds(
    steps: list[dict],
    root_causes: set[str],
    gt_nodes: set[str],
    edges: list[tuple[str, str]],
) -> list[dict]:
    """Aggregate steps by assistant_turn_index into Rounds."""
    from itertools import groupby

    gt_norm = {_normalize(s) for s in gt_nodes}
    visited_norm: set[str] = set()
    visit_counts: dict[str, int] = {}

    # Group steps by turn
    turn_groups: list[tuple[int, list[dict]]] = []
    for turn_idx, group in groupby(steps, key=lambda s: s["assistant_turn_index"]):
        turn_groups.append((turn_idx, list(group)))

    rounds: list[dict] = []
    round_idx = 0

    for turn_idx, turn_steps in turn_groups:
        # Collect action services (agent actively queried) and all services (action + result)
        action_svcs: list[str] = []
        all_services: list[str] = []
        seen_action: set[str] = set()
        seen_all: set[str] = set()
        for step in turn_steps:
            for svc in step.get("action_services", step.get("services", [])):
                if svc not in seen_action:
                    action_svcs.append(svc)
                    seen_action.add(svc)
            for svc in step.get("services", []):
                if svc not in seen_all:
                    all_services.append(svc)
                    seen_all.add(svc)

        # Primary chosen from action_services (what agent actively targeted)
        # Fallback to all_services if no action services
        primary_candidates = action_svcs if action_svcs else all_services
        primary = select_primary_service(
            primary_candidates, root_causes, gt_nodes, edges,
            visited_norm, visit_counts,
        )

        # Skip rounds with no locatable service (pure global queries with no result services)
        if not primary:
            continue

        primary_norm = _normalize(primary)
        dist = compute_distance_to_root(primary, root_causes, edges)
        on_gt = primary_norm in gt_norm

        secondary = [s for s in all_services if s != primary]
        intents = [s["intent"] for s in turn_steps]
        data_types = list(dict.fromkeys(s["data_type"] for s in turn_steps))

        rounds.append({
            "round_index": round_idx,
            "turn_index": turn_idx,
            "primary_service": primary,
            "secondary_services": secondary,
            "all_services": all_services,
            "intents": intents,
            "data_types": data_types,
            "on_gt_path": on_gt,
            "distance_to_root": dist,
            "steps": turn_steps,
        })
        round_idx += 1

        # Update visited and counts for ALL services (action + result)
        for svc in all_services:
            n = _normalize(svc)
            visited_norm.add(n)
            visit_counts[n] = visit_counts.get(n, 0) + 1

    return rounds


# ---------------------------------------------------------------------------
# Zone classification
# ---------------------------------------------------------------------------

def classify_zones(
    gt_graph: dict,
    steps: list[dict],
) -> dict:
    """Classify all visited services into three zones.

    - GT path: services on the causal propagation path
    - Off-path known: real services (in whitelist) not on GT path
    - Hallucinated: service names that don't exist in the system (not in whitelist)
    """
    gt_nodes_norm = {_normalize(s) for s in gt_graph["nodes"]}

    zone_gt: list[str] = list(gt_graph["nodes"])
    zone_known: list[str] = []
    zone_hallucinated: list[str] = []
    halluc_seen: set[str] = set()

    seen: set[str] = set()
    for step in steps:
        for svc in step.get("services", []):
            canonical = resolve_known(svc) or svc
            if canonical in seen:
                continue
            seen.add(canonical)
            if _normalize(canonical) in gt_nodes_norm:
                continue
            zone_known.append(canonical)

        for h in step.get("hallucinated", []):
            if h not in halluc_seen:
                halluc_seen.add(h)
                zone_hallucinated.append(h)

    return {
        "gt_path": zone_gt,
        "off_path_known": zone_known,
        "hallucinated": zone_hallucinated,
    }


# ---------------------------------------------------------------------------
# Build full payload
# ---------------------------------------------------------------------------

def _overlay_llm_intents(steps: list[dict], llm_intents: dict) -> None:
    """Overlay LLM-classified intents onto rule-based steps (in-place).

    Matches by (assistant_turn_index, sql_index_within_turn) → LLM's (round, sql_index).
    LLM intents take precedence over rule-based classify_intent().
    """
    if not llm_intents:
        return

    # Prefer claude_opus_4_6, fallback to first available key
    model_key = "claude_opus_4_6" if "claude_opus_4_6" in llm_intents else next(iter(llm_intents), None)
    if not model_key:
        return
    entries = llm_intents[model_key]
    if not entries:
        return

    # Build lookup: (round, sql_index) → entry
    llm_lookup: dict[tuple[int, int], dict] = {}
    for e in entries:
        llm_lookup[(e["round"], e.get("sql_index", 1))] = e

    # Map steps to (turn_index, sql_position_within_turn) — skip discovery steps
    turn_counts: dict[int, int] = {}
    for step in steps:
        if step.get("intent") == "discovery":
            continue
        turn = step["assistant_turn_index"]
        turn_counts[turn] = turn_counts.get(turn, 0) + 1
        sql_idx = turn_counts[turn]

        llm_entry = llm_lookup.get((turn, sql_idx))
        if llm_entry:
            step["intent"] = llm_entry["intent"]
            step["intent_category"] = _INTENT_TO_CATEGORY.get(llm_entry["intent"], "triage")
            if llm_entry.get("data_type") and llm_entry["data_type"] != "unknown":
                step["data_type"] = llm_entry["data_type"]
            step["intent_source"] = "llm"
        else:
            step["intent_source"] = "rule"


def build_payload(
    meta: dict,
    gt_graph: dict,
    trajectory: list[dict],
) -> dict:
    """Build the complete JSON payload for the HTML template."""
    steps = extract_steps(trajectory)

    # Overlay LLM intents if available in meta
    llm_intents = meta.get("llm_intents")
    if llm_intents:
        _overlay_llm_intents(steps, llm_intents)

    root_set = set(gt_graph["root_causes"])
    gt_set = set(gt_graph["nodes"])

    # Aggregate steps into rounds
    rounds = aggregate_rounds(steps, root_set, gt_set, gt_graph["edges"])

    # Classify transitions between rounds
    transitions = classify_transitions(rounds, gt_set, root_set, gt_graph["edges"])

    zones = classify_zones(gt_graph, steps)

    # Node roles for GT path
    gt_node_roles: dict[str, str] = {}
    for n in gt_graph["nodes"]:
        if n in gt_graph["root_causes"]:
            gt_node_roles[n] = "root_cause"
        elif n in gt_graph["alarms"]:
            gt_node_roles[n] = "alarm"
        else:
            gt_node_roles[n] = "intermediate"

    return {
        "meta": meta,
        "gt_graph": {
            "nodes": gt_graph["nodes"],
            "edges": [{"source": s, "target": t} for s, t in gt_graph["edges"]],
            "root_causes": gt_graph["root_causes"],
            "alarms": gt_graph["alarms"],
            "node_roles": gt_node_roles,
        },
        "zones": zones,
        "rounds": rounds,
        "steps": steps,
        "transitions": transitions,
        "label_descriptions": _LABEL_DESCRIPTIONS,
        "intent_descriptions": _INTENT_DESCRIPTIONS,
        "intent_categories": _INTENT_TO_CATEGORY,
        "category_labels": _CATEGORY_LABELS,
        "category_colors": _CATEGORY_COLORS,
    }


# ---------------------------------------------------------------------------
# DB loading (only import when actually used)
# ---------------------------------------------------------------------------

def load_from_db(exp_id: str, dataset_index: int) -> tuple[dict, dict, list[dict]]:
    """Load sample data from DB. Returns (meta, gt_graph, trajectory)."""
    from sqlmodel import select

    # Minimal project imports — only DB access
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from sota_rca.runner._fallback_db import DatasetSample, EvaluationSample
    from sota_rca.utils.sqlmodel_utils import SQLModelUtils

    session = SQLModelUtils.create_session()
    try:
        stmt = select(EvaluationSample).where(
            EvaluationSample.exp_id == exp_id,
            EvaluationSample.dataset_index == dataset_index,
            EvaluationSample.stage.in_(["rollout", "judged"]),  # type: ignore[union-attr]
        )
        sample = session.exec(stmt).first()
        if not sample:
            raise SystemExit(f"Sample not found: exp_id={exp_id}, dataset_index={dataset_index}")

        # Resolve data_dir via DatasetSample
        ds_stmt = select(DatasetSample).where(
            DatasetSample.dataset == sample.dataset,
            DatasetSample.source == sample.source,
        )
        ds = session.exec(ds_stmt).first()
        data_dir = None
        if ds and ds.meta and "source_data_dir" in ds.meta:
            data_dir = ds.meta["source_data_dir"]

        # Load GT causal graph
        gt_graph = None
        if data_dir:
            gt_graph = load_causal_graph(data_dir)
        if not gt_graph:
            raise SystemExit(f"Cannot load causal_graph.json from data_dir={data_dir}")

        # Parse trajectory
        traj = sample.trajectories
        if isinstance(traj, str):
            traj = json.loads(traj)

        # Extract LLM intents if available
        sample_meta = sample.meta or {}
        llm_intents = sample_meta.get("llm_intents", {})

        meta = {
            "exp_id": sample.exp_id,
            "dataset_index": sample.dataset_index,
            "agent_type": sample.agent_type,
            "model_name": sample.model_name,
            "correct": sample.correct,
            "source": sample.source,
            "stage": sample.stage,
            "llm_intents": llm_intents,
        }

        return meta, gt_graph, traj
    finally:
        session.close()


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RCA Trajectory · {{TITLE}}</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700&family=JetBrains+Mono:wght@300;400;500&family=Exo+2:wght@200;300;400;500;600&display=swap');
:root{--bg:#04070f;--cyan:#00e5ff;--blue:#448aff;--red:#ff1744;--orange:#ff9100;--yellow:#ffd600;--green:#00e676;--purple:#b388ff;--w90:rgba(255,255,255,.9);--w60:rgba(255,255,255,.6);--w30:rgba(255,255,255,.3);--w10:rgba(255,255,255,.1);--w04:rgba(255,255,255,.04)}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:#fff;font-family:'Exo 2',sans-serif;overflow:hidden;height:100vh;width:100vw}

/* Scanlines */
.scan{position:fixed;inset:0;z-index:2;pointer-events:none;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.02) 2px,rgba(0,0,0,.02) 4px)}

/* Grid background */
.grid-bg{position:fixed;inset:0;z-index:0;background-image:linear-gradient(rgba(0,229,255,.018) 1px,transparent 1px),linear-gradient(90deg,rgba(0,229,255,.018) 1px,transparent 1px);background-size:50px 50px}
.radial-glow{position:fixed;inset:0;z-index:0;background:radial-gradient(ellipse at 50% 0%,rgba(0,229,255,.03) 0%,transparent 60%),radial-gradient(ellipse at 50% 100%,rgba(255,23,68,.025) 0%,transparent 50%)}

/* Layout */
.main{position:fixed;inset:0;z-index:10;display:flex}
.left-panel{width:220px;background:rgba(4,7,15,.88);border-right:1px solid rgba(0,229,255,.1);backdrop-filter:blur(16px);overflow-y:auto;min-height:0;flex-shrink:0;z-index:20}
.svg-container{flex:1;position:relative;overflow:hidden}
.right-panel{width:320px;background:rgba(4,7,15,.88);border-left:1px solid rgba(0,229,255,.1);backdrop-filter:blur(16px);overflow-y:auto;min-height:0;flex-shrink:0;z-index:20;padding:14px}
svg{width:100%;height:100%}

/* HUD Header */
.hud-top{position:fixed;top:0;left:220px;right:320px;z-index:30;text-align:center;padding:10px 16px;background:rgba(4,7,15,.75);border-bottom:1px solid rgba(0,229,255,.08);backdrop-filter:blur(12px);display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap}
.hud-title{font-family:'Orbitron',sans-serif;font-size:11px;font-weight:600;letter-spacing:2px;text-transform:uppercase}
.hud-title .sym{color:var(--cyan)}.hud-title .arr{color:var(--w30);margin:0 4px}.hud-title .rc{color:var(--green)}
.hud-select{background:rgba(255,255,255,.04);color:var(--cyan);border:1px solid rgba(0,229,255,.2);border-radius:4px;padding:3px 8px;font-family:'JetBrains Mono',monospace;font-size:10px;max-width:240px;backdrop-filter:blur(8px)}
.hud-select:focus{outline:none;border-color:var(--cyan)}
.hud-tag{padding:2px 8px;border-radius:10px;font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px}
.tag-correct{background:rgba(0,230,118,.15);color:var(--green);border:1px solid rgba(0,230,118,.3)}
.tag-incorrect{background:rgba(255,23,68,.15);color:var(--red);border:1px solid rgba(255,23,68,.3)}
.tag-info{background:rgba(0,229,255,.08);color:var(--cyan);border:1px solid rgba(0,229,255,.15)}
.case-name{font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--w30);letter-spacing:1px;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* Left Panel — Visited */
.panel-header{padding:10px 12px 8px;border-bottom:1px solid rgba(0,229,255,.06);font-family:'Orbitron',sans-serif;font-size:9px;letter-spacing:2px;color:var(--cyan);display:flex;align-items:center;gap:6px}
.panel-header .blink{width:5px;height:5px;border-radius:50%;background:var(--cyan);animation:blink 1.2s ease-in-out infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.visited-body{padding:8px 10px;font-family:'JetBrains Mono',monospace;font-size:10px}
.visited-group-title{font-size:8px;letter-spacing:1.5px;text-transform:uppercase;margin:10px 0 4px;padding-bottom:3px;border-bottom:1px solid rgba(255,255,255,.04)}
.visited-group-title.gt{color:var(--cyan)}.visited-group-title.off{color:var(--w30)}.visited-group-title.hal{color:var(--red)}
.visited-item{padding:3px 6px;margin-bottom:2px;border-radius:3px;display:flex;align-items:center;gap:5px;line-height:1.3;color:var(--w60);word-break:break-all;font-size:9px}
.visited-item .dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.visited-item.new-node{background:rgba(0,230,118,.08);animation:nodeIn .8s ease}
.visited-item.queried-now{background:rgba(0,229,255,.1);color:var(--cyan)}
@keyframes nodeIn{from{background:rgba(0,230,118,.25);transform:translateX(-4px)}to{background:rgba(0,230,118,.08);transform:translateX(0)}}
.new-tag{font-size:7px;color:var(--green);margin-left:auto;letter-spacing:1px;flex-shrink:0}

/* SVG Nodes */
.node{cursor:grab}.node:active{cursor:grabbing}
.node polygon{transition:all .4s ease}
.node .label{font-family:'JetBrains Mono',monospace;font-size:9px;fill:var(--w30);pointer-events:none}
.node .type-label{font-family:'Exo 2',sans-serif;font-size:8px;fill:rgba(255,255,255,.15);pointer-events:none}
.node .step-label{font-family:'Orbitron',sans-serif;font-size:8px;pointer-events:none}
.node.root_cause .label{fill:var(--red)}.node.alarm .label{fill:var(--yellow)}.node.intermediate .label{fill:rgba(0,229,255,.8)}
.node.off_path .label{fill:var(--w30)}.node.hallucinated .label{fill:rgba(255,23,68,.6)}
.node.active polygon{filter:drop-shadow(0 0 16px var(--cyan));animation:heartbeat 1.6s ease-in-out infinite}
.node.active .pulse-ring{animation:pulseRing 1.6s ease-out infinite}
.node.queried polygon{filter:drop-shadow(0 0 10px rgba(0,229,255,.4))}
@keyframes heartbeat{0%,100%{filter:drop-shadow(0 0 12px var(--cyan))}15%{filter:drop-shadow(0 0 28px var(--cyan)) drop-shadow(0 0 6px #fff)}30%{filter:drop-shadow(0 0 12px var(--cyan))}42%{filter:drop-shadow(0 0 24px var(--cyan)) drop-shadow(0 0 4px #fff)}56%{filter:drop-shadow(0 0 12px var(--cyan))}}
@keyframes pulseRing{0%{r:0;opacity:.6;stroke-width:2}100%{r:36;opacity:0;stroke-width:.5}}

/* GT edges */
.gt-edge{stroke:rgba(255,255,255,.06);stroke-width:1.5;stroke-dasharray:4 6;fill:none;marker-end:url(#gt-arrow)}
/* Traj lines */
.traj-line{fill:none;stroke-linecap:round;cursor:pointer}
.traj-line:hover{filter:drop-shadow(0 0 10px currentColor)}
.laser-head{pointer-events:none;mix-blend-mode:screen}
.traj-sec{fill:none;stroke-width:1.2;stroke-linecap:round;pointer-events:none;opacity:.45}
.layer-label{font-family:'Orbitron',sans-serif;font-size:8px;fill:rgba(0,229,255,.15);letter-spacing:1px}

/* Tooltip */
.tooltip{position:fixed;background:rgba(4,7,15,.92);border:1px solid rgba(0,229,255,.2);border-radius:8px;padding:10px 14px;font-family:'JetBrains Mono',monospace;font-size:10px;pointer-events:none;opacity:0;transition:opacity .15s;z-index:100;max-width:320px;line-height:1.7;backdrop-filter:blur(12px);box-shadow:0 4px 24px rgba(0,0,0,.5)}
.tooltip .tt-label{color:var(--cyan);font-weight:500}.tooltip .tt-intent{color:var(--green)}.tooltip .tt-data{color:var(--purple)}

/* Controls */
.controls{position:absolute;bottom:14px;left:50%;transform:translateX(-50%);display:flex;gap:6px;align-items:center;z-index:25;background:rgba(4,7,15,.85);border:1px solid rgba(0,229,255,.1);border-radius:8px;padding:6px 14px;backdrop-filter:blur(12px)}
.btn{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:1px;padding:4px 12px;border-radius:4px;border:1px solid var(--w10);background:var(--w04);color:var(--w60);cursor:pointer;transition:all .2s;text-transform:uppercase}
.btn:hover{border-color:var(--cyan);color:var(--cyan)}.btn.active{background:rgba(0,229,255,.15);border-color:var(--cyan);color:var(--cyan)}
.controls input[type=range]{width:160px;accent-color:var(--cyan)}
.step-display{font-family:'Orbitron',sans-serif;font-size:11px;min-width:80px;text-align:center;color:var(--cyan)}
.controls select{background:var(--w04);color:var(--w60);border:1px solid var(--w10);border-radius:4px;padding:2px 6px;font-family:'JetBrains Mono',monospace;font-size:9px}

/* Right Panel — Detail */
.detail-header{padding:10px 0 8px;border-bottom:1px solid rgba(0,229,255,.06);font-family:'Orbitron',sans-serif;font-size:9px;letter-spacing:2px;color:var(--cyan);margin-bottom:10px}
.detail-section{margin-bottom:12px}
.detail-section h3{font-family:'JetBrains Mono',monospace;font-size:8px;color:var(--w30);margin-bottom:3px;text-transform:uppercase;letter-spacing:1px}
.detail-value{font-size:11px;color:var(--w90);font-family:'JetBrains Mono',monospace}
.detail-badge{display:inline-block;padding:1px 6px;border-radius:3px;font-size:9px;margin-right:3px;font-family:'JetBrains Mono',monospace}
.badge-advancing{background:rgba(0,230,118,.15);color:var(--green);border:1px solid rgba(0,230,118,.3)}
.badge-lateral{background:rgba(255,214,0,.12);color:var(--yellow);border:1px solid rgba(255,214,0,.2)}
.badge-regressing{background:rgba(255,145,0,.12);color:var(--orange);border:1px solid rgba(255,145,0,.2)}
.badge-drifted{background:rgba(255,23,68,.12);color:var(--red);border:1px solid rgba(255,23,68,.2)}
.badge-derailed{background:rgba(179,136,255,.1);color:var(--purple);border:1px solid rgba(179,136,255,.2)}
.badge-returned{background:rgba(68,138,255,.12);color:var(--blue);border:1px solid rgba(68,138,255,.2)}
.expandable{cursor:pointer;color:var(--w30);transition:color .2s}.expandable:hover{color:var(--cyan)}
.expanded-content{display:none;margin-top:4px;padding:6px;background:rgba(0,229,255,.02);border:1px solid rgba(0,229,255,.06);border-radius:4px;font-size:9px;white-space:pre-wrap;word-break:break-all;max-height:220px;overflow-y:auto;color:var(--w60);font-family:'JetBrains Mono',monospace}

/* Legend */
.legend{position:absolute;top:50px;right:8px;z-index:25;background:rgba(4,7,15,.85);border:1px solid rgba(0,229,255,.08);border-radius:6px;padding:8px 10px;backdrop-filter:blur(8px);font-family:'JetBrains Mono',monospace;font-size:8px;line-height:1.8}
.legend-item{display:flex;align-items:center;gap:5px;color:var(--w30)}
.legend-swatch{width:16px;height:2px;border-radius:1px}
.legend-swatch.dashed{background:repeating-linear-gradient(90deg,rgba(255,255,255,.08) 0 3px,transparent 3px 6px)}

/* Progress bar */
.progress-wrap{position:absolute;top:6px;left:50%;transform:translateX(-50%);width:min(400px,60%);z-index:25;pointer-events:none}
.progress-bar{height:2px;background:var(--w04);border-radius:1px;overflow:hidden}
.progress-fill{height:100%;width:0%;background:linear-gradient(90deg,var(--cyan),var(--green));border-radius:1px;transition:width .5s ease}
</style>
</head>
<body>
<div class="scan"></div>
<div class="grid-bg"></div>
<div class="radial-glow"></div>

<div class="main">
  <!-- Left: Visited Nodes -->
  <div class="left-panel">
    <div class="panel-header"><div class="blink"></div>VISITED NODES</div>
    <div class="visited-body" id="visited-list"></div>
  </div>

  <!-- Center: SVG -->
  <div class="svg-container" id="svg-container">
    <!-- HUD top bar -->
    <div class="hud-top">
      <div class="hud-title"><span class="sym">SYMPTOM</span><span class="arr">━▸</span><span class="rc">ROOT CAUSE</span></div>
      <select class="hud-select" id="sel-model"></select>
      <select class="hud-select" id="sel-case"></select>
      <span class="hud-tag" id="h-correct"></span>
      <span class="hud-tag tag-info" id="h-rounds"></span>
      <div class="case-name" id="h-case-name"></div>
    </div>

    <div class="progress-wrap"><div class="progress-bar"><div class="progress-fill" id="pFill"></div></div></div>

    <svg id="canvas"></svg>

    <div class="controls">
      <button class="btn" id="btn-prev">&lt;&lt;</button>
      <button class="btn" id="btn-play">PLAY</button>
      <button class="btn" id="btn-next">&gt;&gt;</button>
      <input type="range" id="slider" min="-1" value="-1">
      <span class="step-display" id="step-display">READY</span>
      <select id="speed-select">
        <option value="400">0.4s</option><option value="800">0.8s</option>
        <option value="1200" selected>1.2s</option><option value="2000">2s</option>
      </select>
    </div>

    <div class="legend" id="legend"></div>
    <div class="tooltip" id="tooltip"></div>
  </div>

  <!-- Right: Detail Panel -->
  <div class="right-panel" id="right-panel">
    <div class="detail-header">ROUND INFO</div>
    <div class="detail-value" style="color:var(--w30)">Select a case, then press PLAY</div>
  </div>
</div>

<script>
const ALL=__JSON_DATA__;
const COLORS={"advancing:consecutive":"#00e676","advancing:skip":"#69f0ae","lateral:revisit":"#ffd600","lateral:explore":"#ffee58","regressing:backtrack":"#ff9100","regressing:explore":"#ffab40","returned:revisit":"#448aff","returned:discover":"#82b1ff","drifted":"#ff1744","derailed":"#b388ff"};
const DT_COLORS={traces:"#00e5ff",logs:"#00e676",metrics:"#b388ff",unknown:"#666"};
const NODE_R=24,NODE_R_SM=16;

// Hex path helper
function hexPath(r){let d="";for(let i=0;i<=6;i++){const a=Math.PI*2/6*i-Math.PI/2;const x=r*Math.cos(a),y=r*Math.sin(a);d+=(i===0?"M":"L")+x.toFixed(1)+","+y.toFixed(1)}return d+"Z"}

const selModel=document.getElementById("sel-model"),selCase=document.getElementById("sel-case");
ALL.models.forEach(m=>{const o=document.createElement("option");o.value=m;o.textContent=m.replace("thinkdepthai-","");selModel.appendChild(o)});
ALL.cases.forEach(c=>{const o=document.createElement("option");o.value=c.dataset_index;o.textContent=`#${c.dataset_index} ${c.source}`;selCase.appendChild(o)});

let DATA=null,simulation=null,curRound=-1,playing=false,playTimer=null;
let simNodes=[],svcToNode={},nodeEls=null,gtEdges=null,trajGroup,secGroup,markerGroup,layerLabelGroup;
const container=document.getElementById("svg-container"),svg=d3.select("#canvas"),tooltip=document.getElementById("tooltip"),slider=document.getElementById("slider");
const transLookup={};

function loadCase(){
  stopPlay();curRound=-1;
  const model=selModel.value,idx=selCase.value;
  const p=ALL.payloads[model]&&ALL.payloads[model][idx];
  if(!p){document.getElementById("right-panel").innerHTML='<div class="detail-header">ROUND INFO</div><div style="color:var(--red)">No data</div>';return}
  DATA=p;
  const hc=document.getElementById("h-correct");
  hc.textContent=DATA.meta.correct?"CORRECT":"INCORRECT";
  hc.className="hud-tag "+(DATA.meta.correct?"tag-correct":"tag-incorrect");
  document.getElementById("h-rounds").textContent=`${DATA.rounds.length}R / ${DATA.steps.length}S`;
  document.getElementById("h-case-name").textContent=DATA.meta.source||"";
  slider.max=DATA.rounds.length-1;slider.value=-1;
  document.getElementById("step-display").textContent="READY";
  document.getElementById("visited-list").innerHTML="";
  document.getElementById("pFill").style.width="0%";
  document.getElementById("right-panel").innerHTML='<div class="detail-header">ROUND INFO</div><div class="detail-value" style="color:var(--w30)">Press PLAY or click &gt;&gt;</div>';
  for(const k in transLookup)delete transLookup[k];
  DATA.transitions.forEach(t=>{transLookup[t.to_round]=t});
  buildGraph();
}
selModel.onchange=loadCase;selCase.onchange=loadCase;

function buildGraph(){
  if(simulation){simulation.stop();simulation=null}
  svg.selectAll("*").remove();simNodes=[];svcToNode={};
  const rootSet=new Set(DATA.gt_graph.root_causes),alarmSet=new Set(DATA.gt_graph.alarms),gtNS=new Set(DATA.gt_graph.nodes);
  const distMap={};
  {const q=[];rootSet.forEach(r=>{distMap[r]=0;q.push(r)});while(q.length){const c=q.shift();DATA.gt_graph.edges.forEach(e=>{if(e.source===c&&distMap[e.target]===undefined){distMap[e.target]=distMap[c]+1;q.push(e.target)}})}}
  const mx=Math.max(0,...Object.values(distMap));DATA.gt_graph.nodes.forEach(n=>{if(distMap[n]===undefined)distMap[n]=mx+1});
  const allSvcs=[...DATA.zones.gt_path,...DATA.zones.off_path_known];
  allSvcs.forEach(svc=>{
    let layer,role;
    if(gtNS.has(svc)){layer=distMap[svc]??0;role=rootSet.has(svc)?"root_cause":(alarmSet.has(svc)?"alarm":"intermediate")}
    else{layer=-1;role="off_path"}
    const n={id:svc,layer,role,r:gtNS.has(svc)?NODE_R:NODE_R_SM};simNodes.push(n);svcToNode[svc]=n;
  });

  const W=container.clientWidth,H=container.clientHeight,pad=80;
  const lg={};simNodes.forEach(n=>{if(!lg[n.layer])lg[n.layer]=[];lg[n.layer].push(n)});
  const gtL=Object.keys(lg).map(Number).filter(l=>l>=0).sort((a,b)=>a-b);
  const nL=gtL.length||1,cx=W*.35;
  gtL.forEach((layer,li)=>{const g=lg[layer];const yF=1-(li/Math.max(1,nL-1));const y=pad+(H-2*pad-60)*yF;
    g.forEach((n,gi)=>{const xo=(gi-(g.length-1)/2)*110;n.x=cx+xo;n.y=y;n.targetY=y})});
  const offG=lg[-1]||[];const offCols=2,offColW=100,offRowH=50;
  offG.forEach((n,i)=>{const col=i%offCols;const row=Math.floor(i/offCols);n.x=W*.62+col*offColW;n.y=pad+50+row*offRowH;n.targetY=n.y});
  (lg[-2]||[]).forEach((n,i)=>{n.x=W*.08;n.y=pad+50+i*55;n.targetY=n.y});

  svg.attr("viewBox",`0 0 ${W} ${H}`);
  const defs=svg.append("defs");
  defs.append("marker").attr("id","gt-arrow").attr("viewBox","0 0 10 10").attr("refX",10).attr("refY",5).attr("markerWidth",6).attr("markerHeight",6).attr("orient","auto-start-reverse").append("path").attr("d","M 0 0 L 10 5 L 0 10 z").attr("fill","rgba(255,255,255,0.1)");
  defs.append("marker").attr("id","traj-arrow").attr("viewBox","0 0 8 8").attr("refX",8).attr("refY",4).attr("markerWidth",5).attr("markerHeight",5).attr("orient","auto").append("path").attr("d","M 0 1 L 8 4 L 0 7 z").attr("fill","var(--green)");
  // Glow filter
  const glow=defs.append("filter").attr("id","glow");
  glow.append("feGaussianBlur").attr("stdDeviation","3").attr("result","blur");
  glow.append("feMerge").html('<feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/>');

  const zoomG=svg.append("g").attr("id","zoom-container");
  svg.call(d3.zoom().scaleExtent([.3,3]).on("zoom",ev=>{zoomG.attr("transform",ev.transform)}));
  layerLabelGroup=zoomG.append("g");
  const gtEG=zoomG.append("g");gtEdges=gtEG.selectAll("path").data(DATA.gt_graph.edges).enter().append("path").attr("class","gt-edge");
  trajGroup=zoomG.append("g");secGroup=zoomG.append("g");
  const nodeGroup=zoomG.append("g");

  nodeEls=nodeGroup.selectAll("g.node").data(simNodes,d=>d.id).enter().append("g")
    .attr("class",d=>`node ${d.role}`).attr("id",d=>`node-${d.id.replace(/[^a-zA-Z0-9]/g,"_")}`)
    .call(d3.drag().on("start",dragS).on("drag",dragD).on("end",dragE));

  // Hexagonal nodes
  const roleStroke={"root_cause":"#ff1744","alarm":"#ffd600","intermediate":"rgba(0,229,255,0.5)","off_path":"rgba(255,255,255,0.08)","hallucinated":"rgba(255,23,68,0.4)"};
  const roleFill={"root_cause":"rgba(255,23,68,0.1)","alarm":"rgba(255,214,0,0.08)","intermediate":"rgba(0,229,255,0.05)","off_path":"rgba(255,255,255,0.02)","hallucinated":"rgba(255,23,68,0.05)"};
  nodeEls.append("path").attr("d",d=>hexPath(d.r)).attr("stroke",d=>roleStroke[d.role]).attr("stroke-width",1.5).attr("fill",d=>roleFill[d.role]);

  // Labels
  nodeEls.append("text").attr("class","label").attr("dy",d=>d.r+14).attr("text-anchor","middle")
    .text(d=>d.id.replace("ts-",""));

  // Role icons
  nodeEls.filter(d=>d.role==="root_cause").append("text").attr("dy",3).attr("text-anchor","middle").attr("font-size",12).attr("fill","#ff1744").text("★");
  nodeEls.filter(d=>d.role==="alarm").append("text").attr("dy",3).attr("text-anchor","middle").attr("font-size",10).attr("fill","#ffd600").text("🔔");

  markerGroup=zoomG.append("g");

  simulation=d3.forceSimulation(simNodes).force("collide",d3.forceCollide().radius(d=>d.r+14).strength(.8)).force("yLayer",d3.forceY().y(d=>d.targetY).strength(.6)).force("charge",d3.forceManyBody().strength(-150).distanceMax(280)).alphaDecay(.05).on("tick",tick);
}

function tick(){
  if(!nodeEls)return;
  nodeEls.attr("transform",d=>`translate(${d.x},${d.y})`);
  gtEdges.attr("d",e=>{const s=svcToNode[e.source],t=svcToNode[e.target];if(!s||!t)return"";const dx=t.x-s.x,dy=t.y-s.y,d2=Math.sqrt(dx*dx+dy*dy)||1;return`M ${s.x+dx/d2*s.r} ${s.y+dy/d2*s.r} L ${t.x-dx/d2*t.r} ${t.y-dy/d2*t.r}`});
  if(curRound>=0)redrawTraj();
  layerLabelGroup.selectAll("*").remove();
  [...new Set(simNodes.filter(n=>n.layer>=0).map(n=>n.layer))].sort((a,b)=>a-b).forEach(l=>{
    const ns=simNodes.filter(n=>n.layer===l);const ay=d3.mean(ns,n=>n.y);
    layerLabelGroup.append("text").attr("class","layer-label").attr("x",14).attr("y",ay+4).text(l===0?"L0 ★ ROOT":`L${l}`)});
}

function dragS(ev,d){if(!ev.active)simulation.alphaTarget(.15).restart();d.fx=d.x;d.fy=d.y}
function dragD(ev,d){d.fx=ev.x;d.fy=ev.y}
function dragE(ev,d){if(!ev.active)simulation.alphaTarget(0);d.targetY=d.fy}

function shortName(s){return(s||"").replace("ts-","")}
function getSpeed(){return parseInt(document.getElementById("speed-select").value)}

// ── Build path geometry for a transition ──
function buildPathD(lastNd,nd,edgeCounts){
  const ek=[lastNd.id,nd.id].sort().join("|");edgeCounts[ek]=(edgeCounts[ek]||0)+1;const ofs=(edgeCounts[ek]-1);
  const dx=nd.x-lastNd.x,dy=nd.y-lastNd.y,dist=Math.sqrt(dx*dx+dy*dy)||1;
  const isSelf=dist<5;
  if(isSelf){
    const loopR=18+ofs*10,side=ofs%2===0?1:-1;
    return{d:`M ${nd.x+side*6} ${nd.y-nd.r*.6} A ${loopR} ${loopR} 0 1 ${side>0?1:0} ${nd.x+side*6} ${nd.y+nd.r*.6}`,isSelf:true};
  }else{
    const curveMag=22+ofs*14,px=-dy/dist*curveMag,py=dx/dist*curveMag;
    return{d:`M ${lastNd.x} ${lastNd.y} Q ${(lastNd.x+nd.x)/2+px} ${(lastNd.y+nd.y)/2+py} ${nd.x} ${nd.y}`,isSelf:false};
  }
}

// ── Animate a path with laser beam effect ──
function animateLine(line,dur,color){
  const node=line.node();if(!node)return;
  const len=node.getTotalLength();
  const pathD=line.attr("d");
  const parent=line.node().parentNode;

  // 1. Trail grows from start to end (the base line)
  line.attr("stroke-dasharray",len+" "+len).attr("stroke-dashoffset",len)
    .transition().duration(dur).ease(d3.easeLinear).attr("stroke-dashoffset",0)
    .on("end",function(){
      const origDash=d3.select(this).attr("data-dash");
      d3.select(this).attr("stroke-dasharray",origDash==="none"?null:origDash);
    });

  // 2. Laser head: bright short segment racing ahead of the trail
  const headLen=Math.min(30,len*.25);
  const laserHead=d3.select(parent).append("path").attr("class","laser-head")
    .attr("d",pathD).attr("fill","none")
    .attr("stroke","#fff").attr("stroke-width",2).attr("stroke-linecap","round")
    .style("filter","drop-shadow(0 0 8px "+color+") drop-shadow(0 0 3px #fff)")
    .attr("stroke-dasharray",headLen+" "+(len+headLen))
    .attr("stroke-dashoffset",headLen);
  laserHead.transition().duration(dur).ease(d3.easeLinear)
    .attr("stroke-dashoffset",-(len))
    .on("end",function(){d3.select(this).remove()});

  // 3. Impact flash at destination
  const endPt=node.getPointAtLength(len);
  const flash=d3.select(parent).append("circle")
    .attr("cx",endPt.x).attr("cy",endPt.y).attr("r",3)
    .attr("fill","#fff").style("filter","drop-shadow(0 0 12px "+color+") drop-shadow(0 0 4px #fff)")
    .style("opacity",0);
  flash.transition().delay(dur*.85).duration(120).style("opacity",1).attr("r",10)
    .transition().duration(350).style("opacity",0).attr("r",0)
    .on("end",function(){d3.select(this).remove()});
}

// ── Pan camera to center on a node ──
function panToNode(nd){
  const container=document.getElementById("svg-container");
  const w=container.clientWidth,h=container.clientHeight;
  const zoomBehavior=svg.property("__zoom")||d3.zoomIdentity;
  const k=zoomBehavior.k||1;
  const tx=w/2-nd.x*k,ty=h/2-nd.y*k;
  const t=d3.zoomIdentity.translate(tx,ty).scale(k);
  svg.transition().duration(500).ease(d3.easeCubicInOut).call(d3.zoom().scaleExtent([.3,3]).on("zoom",ev=>{d3.select("#zoom-container").attr("transform",ev.transform)}).transform,t);
}

function redrawTraj(){
  trajGroup.selectAll("*").remove();secGroup.selectAll("*").remove();markerGroup.selectAll("*").remove();
  // Reset node styles and remove old pulse rings
  nodeEls.classed("active",false).classed("queried",false).classed("visited-hist",false);
  nodeEls.select("path").attr("d",d=>hexPath(d.r));
  nodeEls.selectAll(".pulse-ring").remove();

  let lastNode=null;const edgeCounts={};
  const visitedSet=new Set(),newThisRound=new Set(),queriedThisRound=new Set();
  const ANIM_DUR=420;let curNd=null;

  for(let i=0;i<=curRound&&i<DATA.rounds.length;i++){
    const round=DATA.rounds[i],svc=round.primary_service,nd=svcToNode[svc];if(!nd)continue;
    const isCur=(i===curRound),age=curRound-i,opacity=isCur?1:Math.max(.1,1-age*.06);
    if(isCur){round.all_services.forEach(s=>{if(!visitedSet.has(s))newThisRound.add(s);queriedThisRound.add(s)});curNd=nd}
    round.all_services.forEach(s=>visitedSet.add(s));

    if(lastNode){
      const trans=transLookup[round.round_index],label=trans?trans.label:"lateral:explore",color=COLORS[label]||"#666";
      const {d:pathD,isSelf}=buildPathD(lastNode,nd,edgeCounts);
      // Depth: current line thicker + glow; older lines progressively thinner
      const sw=isCur?3.5:Math.max(1,2.5-age*.12);
      const glow=isCur?"drop-shadow(0 0 6px "+color+")":"drop-shadow(0 0 2px "+color+")";
      const dash=isSelf&&!isCur?"4 3":"none";
      const line=trajGroup.append("path").attr("class","traj-line").attr("d",pathD)
        .attr("stroke",color).style("opacity",opacity).attr("stroke-width",sw)
        .style("filter",glow).attr("data-dash",dash)
        .attr("marker-end",isCur?"url(#traj-arrow)":"");
      if(trans)line.on("mouseenter",ev=>showTT(ev,trans,round)).on("mouseleave",hideTT);
      // Animate only the newest line
      if(isCur)animateLine(line,ANIM_DUR,color);
      else line.attr("stroke-dasharray",dash==="none"?null:dash);
    }

    // Secondary fan-out (laser beams to secondary nodes)
    if(isCur)(round.secondary_services||[]).forEach((s,si)=>{const sn=svcToNode[s];if(sn){
      const secD=`M ${nd.x} ${nd.y} L ${sn.x} ${sn.y}`;
      const secLine=secGroup.append("path").attr("class","traj-sec").attr("d",secD)
        .attr("stroke","var(--cyan)").attr("data-dash","3 4");
      animateLine(secLine,ANIM_DUR*.7,"#00e5ff");
    }});

    // Round marker (animate entrance on current round)
    const mr=nd.r+14,ang=(i*.8)%(2*Math.PI)-Math.PI/2;
    const mmx=nd.x+mr*Math.cos(ang),mmy=nd.y+mr*Math.sin(ang);
    const mCircle=markerGroup.append("circle").attr("cx",mmx).attr("cy",mmy)
      .attr("fill",isCur?"var(--cyan)":"rgba(255,255,255,0.06)")
      .attr("stroke",isCur?"var(--cyan)":"rgba(255,255,255,0.1)").attr("stroke-width",.5);
    const mText=markerGroup.append("text").attr("x",mmx).attr("y",mmy)
      .attr("text-anchor","middle").attr("dy",".35em").attr("font-size",7)
      .attr("fill",isCur?"var(--bg)":"var(--w30)")
      .attr("font-family","'Orbitron',sans-serif").attr("font-weight","600").text(`R${i+1}`);
    if(isCur){
      mCircle.attr("r",0).transition().duration(300).delay(ANIM_DUR*.6).ease(d3.easeBackOut.overshoot(2.5)).attr("r",6);
      mText.style("opacity",0).transition().duration(200).delay(ANIM_DUR*.6+100).style("opacity",1);
    }else{mCircle.attr("r",6)}

    const nSel=d3.select(`#node-${svc.replace(/[^a-zA-Z0-9]/g,"_")}`);
    nSel.classed("active",isCur).classed("visited-hist",!isCur);
    if(isCur){nSel.append("circle").attr("class","pulse-ring").attr("cx",0).attr("cy",0).attr("r",0).attr("fill","none").attr("stroke","var(--cyan)").attr("stroke-width",2)}
    lastNode=nd;
  }

  // Enlarge queried nodes
  queriedThisRound.forEach(s=>{const nid=`#node-${s.replace(/[^a-zA-Z0-9]/g,"_")}`;d3.select(nid).classed("queried",true);const nd=svcToNode[s];if(nd)d3.select(nid).select("path").transition().duration(300).attr("d",hexPath(nd.r*1.3))});
  visitedSet.forEach(s=>{if(!queriedThisRound.has(s))d3.select(`#node-${s.replace(/[^a-zA-Z0-9]/g,"_")}`).classed("visited-hist",true)});

  updateVisited(visitedSet,newThisRound,queriedThisRound);
  // Progress bar
  document.getElementById("pFill").style.width=(DATA.rounds.length>0?((curRound+1)/DATA.rounds.length*100):0)+"%";
  // Pan camera to current active node
  if(curNd)panToNode(curNd);
}

function updateVisited(vs,ns,qs){
  const el=document.getElementById("visited-list");el.innerHTML="";
  const rc={"root_cause":"var(--red)","alarm":"var(--yellow)","intermediate":"var(--cyan)","off_path":"var(--w30)"};
  const gtSet=new Set(DATA.zones.gt_path);
  const gtN=[],offN=[];
  vs.forEach(svc=>{if(gtSet.has(svc))gtN.push(svc);else offN.push(svc)});
  function renderGroup(title,cls,nodes){
    if(!nodes.length)return"";
    let h=`<div class="visited-group-title ${cls}">${title} (${nodes.length})</div>`;
    nodes.forEach(svc=>{const nd=svcToNode[svc];const role=nd?nd.role:"off_path";
      const c="visited-item"+(ns.has(svc)?" new-node":"")+(qs.has(svc)?" queried-now":"");
      h+=`<div class="${c}"><span class="dot" style="background:${rc[role]||'var(--w30)'}"></span>${shortName(svc)}${ns.has(svc)?'<span class="new-tag">NEW</span>':""}</div>`});
    return h;
  }
  el.innerHTML=renderGroup("GT PATH","gt",gtN)+renderGroup("OFF-PATH KNOWN","off",offN);
}

function drawToRound(target){curRound=target;redrawTraj();
  document.getElementById("step-display").textContent=target>=0?`R${target+1}/${DATA.rounds.length}`:"READY";
  slider.value=target;updateDetail(target)}

function showTT(ev,trans,round){
  const ld=(ALL.label_descriptions||{})[trans.label]||"";
  const ih=[...new Set(round.intents)].map(i=>{const cat=(ALL.intent_categories||{})[i]||"";const cc=(ALL.category_colors||{})[cat]||"#666";const cl=(ALL.category_labels||{})[cat]||"";return `<span style="color:${cc};font-size:9px">[${cl}]</span> <span class="tt-intent">${i}</span> ${(ALL.intent_descriptions||{})[i]||""}`}).join("<br>");
  const dh=round.data_types.map(dt=>`<span class="tt-data" style="color:${DT_COLORS[dt]||'#666'}">${dt}</span>`).join(" ");
  tooltip.innerHTML=`<div><span class="tt-label">${trans.label}</span> — ${ld}</div><div>${ih}</div><div>${dh}</div>`;
  tooltip.style.opacity=1;tooltip.style.left=(ev.pageX+14)+"px";tooltip.style.top=(ev.pageY-14)+"px"}
function hideTT(){tooltip.style.opacity=0}

function updateDetail(ri){
  const p=document.getElementById("right-panel");
  if(!DATA||ri<0||ri>=DATA.rounds.length){p.innerHTML='<div class="detail-header">ROUND INFO</div><div class="detail-value" style="color:var(--w30)">Press PLAY or click &gt;&gt;</div>';return}
  const r=DATA.rounds[ri],tr=transLookup[r.round_index],bc=tr?`badge-${tr.label.split(":")[0]}`:"";
  const th=tr?`<span class="detail-badge ${bc}">${tr.label}</span> ${tr.prev_dist!=null&&tr.next_dist!=null?`<span style="color:var(--w30)">dist ${tr.prev_dist} → ${tr.next_dist}</span>`:""}`:"<span style='color:var(--w30)'>— first round</span>";
  const dtB=r.data_types.map(dt=>`<span class="detail-badge" style="background:${DT_COLORS[dt]||'#333'}22;color:${DT_COLORS[dt]||'#666'};border:1px solid ${DT_COLORS[dt]||'#333'}44">${dt}</span>`).join(" ");
  const cats=[...new Set(r.steps.map(s=>s.intent_category||"triage"))];
  const catB=cats.map(c=>`<span class="detail-badge" style="background:${(ALL.category_colors||{})[c]||'#333'}22;color:${(ALL.category_colors||{})[c]||'#666'};border:1px solid ${(ALL.category_colors||{})[c]||'#333'}44">${(ALL.category_labels||{})[c]||c}</span>`).join(" ");
  const iu=[...new Set(r.intents)];
  const CC=ALL.category_colors||{};const CL=ALL.category_labels||{};
  const sH=r.steps.map(s=>{const cat=s.intent_category||"triage";const cc=CC[cat]||"#666";const cl=CL[cat]||cat;
    return `<div style="margin-bottom:8px;padding:5px 7px;border-left:3px solid ${cc}44;background:${cc}08;border-radius:0 4px 4px 0"><div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:3px"><span style="font-size:7px;padding:1px 5px;border-radius:2px;background:${cc}22;color:${cc};border:1px solid ${cc}44;font-family:'JetBrains Mono',monospace;font-weight:500">${cl}</span><span style="font-size:8px;color:var(--w60);font-family:'JetBrains Mono',monospace">${s.intent}</span><span style="font-size:7px;padding:1px 4px;border-radius:2px;background:${({"traces":"#00e5ff","logs":"#69f0ae","metrics":"#ff9100"})[s.data_type]||"#666"}18;color:${({"traces":"#00e5ff","logs":"#69f0ae","metrics":"#ff9100"})[s.data_type]||"#666"};border:1px solid ${({"traces":"#00e5ff","logs":"#69f0ae","metrics":"#ff9100"})[s.data_type]||"#666"}33">${s.data_type}</span>${s.intent_source==="llm"?'<span style="font-size:6px;color:var(--w30)">LLM</span>':""}</div><pre style="font-size:9px;color:var(--w60);margin:0;white-space:pre-wrap;word-break:break-all;font-family:'JetBrains Mono',monospace">${escapeHtml(s.sql||"")}</pre></div>`}).join("");
  p.innerHTML=`<div class="detail-header">ROUND ${ri+1} / ${DATA.rounds.length}</div>
    <div class="detail-section"><h3>Data Types & Intents</h3><div class="detail-value">${dtB} ${catB}</div><div style="color:var(--w60);font-size:9px;margin-top:3px">${iu.join(", ")}</div><div style="color:var(--w30);font-size:9px;margin-top:2px">${r.steps.length} SQL quer${r.steps.length>1?"ies":"y"}</div></div>
    <div class="detail-section"><h3>Primary Node</h3><div class="detail-value" style="color:var(--cyan)">${shortName(r.primary_service)} ${r.on_gt_path?'<span style="color:var(--green)">✓ GT</span>':'<span style="color:var(--red)">✗ OFF</span>'} ${r.distance_to_root!=null?'<span style="color:var(--w30)">(dist='+r.distance_to_root+')</span>':''}</div></div>
    ${r.secondary_services.length?`<div class="detail-section"><h3>Also Queried</h3><div class="detail-value" style="color:var(--w60)">${r.secondary_services.map(s=>shortName(s)).join(", ")}</div></div>`:""}
    <div class="detail-section"><h3>Transition</h3><div class="detail-value">${th}</div></div>
    <div class="detail-section"><h3>Steps Detail (${r.steps.length})</h3><div id="sd" style="display:block">${sH}</div></div>`}

function togExp(id){const e=document.getElementById(id);if(e)e.style.display=e.style.display==="block"?"none":"block"}
function escapeHtml(t){const d=document.createElement("div");d.textContent=t;return d.innerHTML}
function roundFwd(){if(DATA&&curRound<DATA.rounds.length-1)drawToRound(curRound+1);else stopPlay()}
function roundBwd(){if(curRound>-1)drawToRound(curRound-1)}
function startPlay(){playing=true;document.getElementById("btn-play").textContent="PAUSE";document.getElementById("btn-play").classList.add("active");playTimer=setInterval(roundFwd,getSpeed())}
function stopPlay(){playing=false;document.getElementById("btn-play").textContent="PLAY";document.getElementById("btn-play").classList.remove("active");if(playTimer){clearInterval(playTimer);playTimer=null}}
document.getElementById("btn-play").onclick=()=>playing?stopPlay():startPlay();
document.getElementById("btn-prev").onclick=()=>{stopPlay();roundBwd()};
document.getElementById("btn-next").onclick=()=>{stopPlay();roundFwd()};
slider.oninput=()=>{stopPlay();drawToRound(parseInt(slider.value))};
document.getElementById("speed-select").onchange=()=>{if(playing){clearInterval(playTimer);playTimer=setInterval(roundFwd,getSpeed())}};

// Legend
document.getElementById("legend").innerHTML=[
  ["GT causal edge","",true],
  ["advancing:consecutive","#00e676"],["advancing:skip","#69f0ae"],
  ["lateral:explore","#ffee58"],["lateral:revisit","#ffd600"],
  ["regressing:explore","#ffab40"],["regressing:backtrack","#ff9100"],
  ["returned:discover","#82b1ff"],["returned:revisit","#448aff"],
  ["drifted","#ff1744"],["derailed","#b388ff"],
].map(([l,c,d])=>d?`<div class="legend-item"><div class="legend-swatch dashed"></div>${l}</div>`
  :`<div class="legend-item"><div class="legend-swatch" style="background:${c}"></div>${l}</div>`).join("");

loadCase();
</script>
</body>
</html>"""


def load_demo_data() -> dict:
    """Load all 4 models × common cases for demo mode."""
    from sqlmodel import select, func

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from sota_rca.runner._fallback_db import DatasetSample, EvaluationSample
    from sota_rca.utils.sqlmodel_utils import SQLModelUtils

    session = SQLModelUtils.create_session()

    DEMO_MODELS = [
        "thinkdepthai-claude-sonnet-4.6",
        "thinkdepthai-gpt-5.3",
        "thinkdepthai-qwen3.5-plus",
        "thinkdepthai-gemini-3.1-pro",
    ]

    # Fallback: auto-detect from DB if hardcoded models not found
    check_stmt = select(EvaluationSample.exp_id).where(
        EvaluationSample.stage == "judged",
    ).distinct()
    db_exp_ids = set(session.exec(check_stmt).all())
    if not db_exp_ids.intersection(DEMO_MODELS):
        DEMO_MODELS = sorted(db_exp_ids)
    if not DEMO_MODELS:
        print("No judged samples found")
        session.close()
        return {"models": [], "cases": [], "payloads": {}}
    try:
        # Find common judged dataset_indexes
        idx_sets = []
        for exp in DEMO_MODELS:
            stmt = select(EvaluationSample.dataset_index).where(
                EvaluationSample.exp_id == exp,
                EvaluationSample.stage == "judged",
            )
            idx_sets.append(set(session.exec(stmt).all()))

        common = sorted(idx_sets[0].intersection(*idx_sets[1:]))
        print(f"Found {len(common)} common cases across {len(DEMO_MODELS)} models")

        # Build case list with source names
        case_list: list[dict] = []
        for idx in common:
            stmt = select(EvaluationSample).where(
                EvaluationSample.exp_id == DEMO_MODELS[0],
                EvaluationSample.dataset_index == idx,
                EvaluationSample.stage == "judged",
            )
            s = session.exec(stmt).first()
            if s:
                case_list.append({"dataset_index": idx, "source": s.source or ""})

        # Load all payloads
        all_payloads: dict[str, dict[str, dict]] = {}  # {exp_id: {dataset_index: payload}}
        total = len(DEMO_MODELS) * len(common)
        done = 0

        for exp in DEMO_MODELS:
            all_payloads[exp] = {}
            for idx in common:
                stmt = select(EvaluationSample).where(
                    EvaluationSample.exp_id == exp,
                    EvaluationSample.dataset_index == idx,
                    EvaluationSample.stage == "judged",
                )
                sample = session.exec(stmt).first()
                if not sample:
                    continue

                # Resolve data_dir
                ds_stmt = select(DatasetSample).where(
                    DatasetSample.dataset == sample.dataset,
                    DatasetSample.source == sample.source,
                )
                ds = session.exec(ds_stmt).first()
                data_dir = ds.meta.get("source_data_dir") if ds and ds.meta else None
                gt_graph = load_causal_graph(data_dir) if data_dir else None
                if not gt_graph:
                    continue

                traj = sample.trajectories
                if isinstance(traj, str):
                    traj = json.loads(traj)

                sample_meta = sample.meta or {}
                meta = {
                    "exp_id": sample.exp_id,
                    "dataset_index": sample.dataset_index,
                    "agent_type": sample.agent_type,
                    "model_name": sample.model_name,
                    "correct": sample.correct,
                    "source": sample.source,
                    "stage": sample.stage,
                    "llm_intents": sample_meta.get("llm_intents", {}),
                }

                payload = build_payload(meta, gt_graph, traj)
                all_payloads[exp][str(idx)] = payload
                done += 1
                if done % 10 == 0:
                    print(f"  [{done}/{total}] extracted...")

        print(f"Extracted {done}/{total} payloads")
        return {
            "models": DEMO_MODELS,
            "cases": case_list,
            "payloads": all_payloads,
            "label_descriptions": _LABEL_DESCRIPTIONS,
            "intent_descriptions": _INTENT_DESCRIPTIONS,
            "intent_categories": _INTENT_TO_CATEGORY,
            "category_labels": _CATEGORY_LABELS,
            "category_colors": _CATEGORY_COLORS,
        }
    finally:
        session.close()


def generate_html(payload: dict) -> str:
    """Inject JSON payload into HTML template (single mode)."""
    title = f"{payload['meta']['exp_id']} #{payload['meta']['dataset_index']}"
    # Wrap single payload in multi-model structure
    demo_data = {
        "models": [payload["meta"]["exp_id"]],
        "cases": [{"dataset_index": payload["meta"]["dataset_index"], "source": payload["meta"].get("source", "")}],
        "payloads": {payload["meta"]["exp_id"]: {str(payload["meta"]["dataset_index"]): payload}},
        "label_descriptions": payload.get("label_descriptions", _LABEL_DESCRIPTIONS),
        "intent_descriptions": payload.get("intent_descriptions", _INTENT_DESCRIPTIONS),
    }
    json_str = json.dumps(demo_data, ensure_ascii=False)
    html = HTML_TEMPLATE.replace("__JSON_DATA__", json_str)
    html = html.replace("{{TITLE}}", title)
    return html


def generate_demo_html(demo_data: dict) -> str:
    """Inject multi-model demo data into HTML template."""
    json_str = json.dumps(demo_data, ensure_ascii=False)
    html = HTML_TEMPLATE.replace("__JSON_DATA__", json_str)
    html = html.replace("{{TITLE}}", f"Demo: {len(demo_data['models'])} models × {len(demo_data['cases'])} cases")
    return html


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate trajectory one-stroke visualization")
    parser.add_argument("--exp_id", help="Experiment ID (DB mode)")
    parser.add_argument("--dataset_index", type=int, help="Dataset index (DB mode)")
    parser.add_argument("--json", dest="json_input", help="Pre-exported JSON payload (bypass DB)")
    parser.add_argument("--export-json", dest="export_json", help="Export JSON payload to file (no HTML)")
    parser.add_argument("--demo", action="store_true", help="Demo mode: 4 models × 43 common cases")
    parser.add_argument("--output", "-o", default="trace.html", help="Output HTML file path")
    args = parser.parse_args()

    if args.demo:
        demo_data = load_demo_data()
        if args.export_json:
            with open(args.export_json, "w") as f:
                json.dump(demo_data, f, ensure_ascii=False)
            print(f"Exported demo JSON to {args.export_json}")
            return
        html = generate_demo_html(demo_data)
        with open(args.output, "w") as f:
            f.write(html)
        print(f"Generated demo {args.output} ({len(html) // 1024}KB)")
    elif args.json_input:
        with open(args.json_input) as f:
            raw = json.load(f)
        # Detect if multi-model or single payload
        if "payloads" in raw:
            html = generate_demo_html(raw)
        else:
            html = generate_html(raw)
        with open(args.output, "w") as f:
            f.write(html)
        print(f"Generated {args.output} ({len(html) // 1024}KB)")
    elif args.exp_id and args.dataset_index is not None:
        meta, gt_graph, trajectory = load_from_db(args.exp_id, args.dataset_index)
        payload = build_payload(meta, gt_graph, trajectory)
        print(f"Extracted {len(payload['steps'])} steps → {len(payload['rounds'])} rounds, "
              f"{len(payload['zones']['gt_path'])} GT nodes, "
              f"{len(payload['zones']['off_path_known'])} off-path, "
              f"{len(payload['zones']['hallucinated'])} hallucinated")
        if args.export_json:
            with open(args.export_json, "w") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"Exported JSON to {args.export_json}")
            return
        html = generate_html(payload)
        with open(args.output, "w") as f:
            f.write(html)
        print(f"Generated {args.output} ({len(html) // 1024}KB)")
    else:
        parser.error("Provide --demo, --exp_id + --dataset_index, or --json")


if __name__ == "__main__":
    main()
