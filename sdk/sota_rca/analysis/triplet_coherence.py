"""Triplet coherence analysis for trajectory evaluation.

Analyzes semantic consistency within and between thought-action-result triplets:

Internal (within single triplet):
  ① Thought → Action: service match & data type match
  ② Action → Result: effectiveness & GT discovery

External (between adjacent triplets):
  ③ Thought_i → Thought_{i+1}: progression along GT causal chain
  ④ Result_i → Thought_{i+1}: information utilization
  ⑤ Action_i → Action_{i+1}: investigation focus drift

Round Transition Taxonomy (between adjacent Rounds — aggregated by assistant turn):
  5 major categories, 10 sub-labels classifying Round-to-Round transitions
  based on primary_service's GT path membership and BFS distance to root cause.
  See docs/trajectory-visualization.md for full specification.
"""

from collections import deque
from dataclasses import dataclass, field

from .extractor import ExtractedStep, GTContext, _normalize_service

# ── Data Structures ─────────────────────────────────────────────────────────


@dataclass
class InternalCoherence:
    """Internal coherence analysis for a single triplet."""

    step_index: int

    # ① Thought → Action
    ta_service_match: str = "no_mention"  # match / mismatch / no_mention
    ta_matched_services: list[str] = field(default_factory=list)
    ta_datatype_match: str = "no_mention"  # match / mismatch / no_mention

    # ② Action → Result
    ar_effectiveness: str = "empty"  # effective / empty / error
    ar_gt_services_found: list[str] = field(default_factory=list)


@dataclass
class ExternalCoherence:
    """External coherence analysis between adjacent triplets."""

    pair: tuple[int, int]  # (step_i, step_i+1)

    # ③ Thought_i → Thought_{i+1}: progression
    tt_progression: str = "no_thought"  # advancing / lateral / regressing / off_path / no_thought
    tt_prev_gt_services: list[str] = field(default_factory=list)
    tt_next_gt_services: list[str] = field(default_factory=list)

    # ④ Result_i → Thought_{i+1}: information utilization
    rt_utilization: str = "no_data"  # utilized / ignored / no_data
    rt_carried_services: list[str] = field(default_factory=list)

    # ⑤ Action_i → Action_{i+1}: drift
    aa_drift: str = "both_off"  # on_path / drifted / returned / both_off


@dataclass
class CoherenceReport:
    """Coherence analysis report for a single sample."""

    sample_id: int
    correct: bool

    # Internal rates
    ta_service_match_rate: float = 0.0
    ta_datatype_match_rate: float = 0.0
    ar_effectiveness_rate: float = 0.0
    ar_gt_discovery_rate: float = 0.0

    # External rates
    tt_advancing_rate: float = 0.0
    rt_utilization_rate: float = 0.0
    aa_on_path_rate: float = 0.0

    # Detail
    internal: list[InternalCoherence] = field(default_factory=list)
    external: list[ExternalCoherence] = field(default_factory=list)


# ── Step Transition Taxonomy ────────────────────────────────────────────────


@dataclass
class StepTransition:
    """Classification of the transition between two adjacent non-discovery steps.

    Labels follow a major:minor format (10 types):
      advancing:consecutive, advancing:skip,
      lateral:revisit, lateral:explore,
      regressing:backtrack, regressing:explore,
      returned:revisit, returned:discover,
      drifted, derailed
    """

    pair: tuple[int, int]  # (prev.step_index, next.step_index)
    label: str  # e.g. "advancing:consecutive"
    rt_utilization: str  # "utilized" / "ignored" / "no_data"
    prev_services_on_gt: list[str] = field(default_factory=list)
    next_services_on_gt: list[str] = field(default_factory=list)
    prev_dist: int | None = None
    next_dist: int | None = None
    is_new_service: bool = False  # next GT service is first-time discovery


@dataclass
class TransitionReport:
    """Step transition taxonomy report for a single sample."""

    sample_id: int
    correct: bool
    transitions: list[StepTransition] = field(default_factory=list)

    # Rates (computed from transitions)
    advancing_rate: float = 0.0
    consecutive_rate: float = 0.0  # consecutive / advancing
    derailed_rate: float = 0.0
    drifted_rate: float = 0.0
    returned_rate: float = 0.0
    regressing_rate: float = 0.0
    rt_utilized_rate: float = 0.0
    rt_partial_rate: float = 0.0
    rt_ignored_rate: float = 0.0
    rt_no_data_rate: float = 0.0


# ── Internal Analysis ────────────────────────────────────────────────────────


def _analyze_internal(step: ExtractedStep, gt: GTContext) -> InternalCoherence:
    """Analyze internal coherence for a single step."""
    ic = InternalCoherence(step_index=step.step_index)

    # ① Thought → Action: service consistency
    if step.thought and step.thought_services:
        thought_norm = {_normalize_service(s) for s in step.thought_services}
        action_norm = {_normalize_service(s) for s in step.action_services}
        matched = thought_norm & action_norm
        if matched:
            ic.ta_service_match = "match"
            ic.ta_matched_services = [s for s in step.thought_services if _normalize_service(s) in matched]
        else:
            ic.ta_service_match = "mismatch"
    # else: no_mention (default)

    # ① Thought → Action: data type consistency
    if step.thought and step.thought_data_types:
        if step.action_data_type in step.thought_data_types:
            ic.ta_datatype_match = "match"
        else:
            ic.ta_datatype_match = "mismatch"
    # else: no_mention (default)

    # ② Action → Result: effectiveness
    if step.result_is_error:
        ic.ar_effectiveness = "error"
    elif step.result_services:
        ic.ar_effectiveness = "effective"
    else:
        ic.ar_effectiveness = "empty"

    # ② Action → Result: GT service discovery
    ic.ar_gt_services_found = [s for s in step.result_services if gt.is_on_path(s)]

    return ic


# ── External Analysis ────────────────────────────────────────────────────────


def _analyze_external(prev: ExtractedStep, next_step: ExtractedStep, gt: GTContext) -> ExternalCoherence:
    """Analyze external coherence between adjacent steps."""
    ec = ExternalCoherence(pair=(prev.step_index, next_step.step_index))

    # ③ Thought progression
    if prev.thought is None or next_step.thought is None:
        ec.tt_progression = "no_thought"
    else:
        prev_gt = [s for s in prev.thought_services if gt.is_on_path(s)]
        next_gt = [s for s in next_step.thought_services if gt.is_on_path(s)]
        ec.tt_prev_gt_services = prev_gt
        ec.tt_next_gt_services = next_gt

        if not prev_gt and not next_gt:
            ec.tt_progression = "off_path"
        elif not prev_gt or not next_gt:
            # One is on path, one is not
            ec.tt_progression = "off_path"
        else:
            # Both on GT path - check if advancing toward root cause
            prev_dists = [gt.distance_to_root(s) for s in prev_gt]
            next_dists = [gt.distance_to_root(s) for s in next_gt]
            prev_min = min((d for d in prev_dists if d is not None), default=None)
            next_min = min((d for d in next_dists if d is not None), default=None)

            if prev_min is None or next_min is None:
                ec.tt_progression = "off_path"
            elif next_min < prev_min:
                ec.tt_progression = "advancing"
            elif next_min == prev_min:
                ec.tt_progression = "lateral"
            else:
                ec.tt_progression = "regressing"

    # ④ Result → Thought: information utilization
    prev_result_gt = [s for s in prev.result_services if gt.is_on_path(s)]
    if not prev_result_gt:
        ec.rt_utilization = "no_data"
    elif next_step.thought is None:
        ec.rt_utilization = "ignored"
    else:
        prev_result_norm = {_normalize_service(s) for s in prev_result_gt}
        next_thought_norm = {_normalize_service(s) for s in next_step.thought_services}
        carried = prev_result_norm & next_thought_norm
        if carried:
            ec.rt_utilization = "utilized"
            ec.rt_carried_services = [s for s in prev_result_gt if _normalize_service(s) in carried]
        else:
            ec.rt_utilization = "ignored"

    # ⑤ Action drift
    prev_on = any(gt.is_on_path(s) for s in prev.action_services)
    next_on = any(gt.is_on_path(s) for s in next_step.action_services)
    if prev_on and next_on:
        ec.aa_drift = "on_path"
    elif prev_on and not next_on:
        ec.aa_drift = "drifted"
    elif not prev_on and next_on:
        ec.aa_drift = "returned"
    else:
        ec.aa_drift = "both_off"

    return ec


# ── Main Analysis ────────────────────────────────────────────────────────────


def analyze_coherence(
    sample_id: int,
    correct: bool,
    steps: list[ExtractedStep],
    gt: GTContext,
) -> CoherenceReport:
    """Analyze coherence for a single sample."""
    report = CoherenceReport(sample_id=sample_id, correct=correct)

    # Internal analysis
    for step in steps:
        ic = _analyze_internal(step, gt)
        report.internal.append(ic)

    # External analysis
    for i in range(len(steps) - 1):
        ec = _analyze_external(steps[i], steps[i + 1], gt)
        report.external.append(ec)

    # Compute rates
    if report.internal:
        n = len(report.internal)
        ta_with_mention = [ic for ic in report.internal if ic.ta_service_match != "no_mention"]
        if ta_with_mention:
            report.ta_service_match_rate = sum(1 for ic in ta_with_mention if ic.ta_service_match == "match") / len(
                ta_with_mention
            )
        dt_with_mention = [ic for ic in report.internal if ic.ta_datatype_match != "no_mention"]
        if dt_with_mention:
            report.ta_datatype_match_rate = sum(1 for ic in dt_with_mention if ic.ta_datatype_match == "match") / len(
                dt_with_mention
            )
        report.ar_effectiveness_rate = sum(1 for ic in report.internal if ic.ar_effectiveness == "effective") / n
        report.ar_gt_discovery_rate = sum(1 for ic in report.internal if ic.ar_gt_services_found) / n

    if report.external:
        m = len(report.external)
        tt_with_thought = [ec for ec in report.external if ec.tt_progression != "no_thought"]
        if tt_with_thought:
            report.tt_advancing_rate = sum(1 for ec in tt_with_thought if ec.tt_progression == "advancing") / len(
                tt_with_thought
            )
        rt_with_data = [ec for ec in report.external if ec.rt_utilization != "no_data"]
        if rt_with_data:
            report.rt_utilization_rate = sum(1 for ec in rt_with_data if ec.rt_utilization == "utilized") / len(
                rt_with_data
            )
        report.aa_on_path_rate = sum(1 for ec in report.external if ec.aa_drift == "on_path") / m

    return report


# ── Step Transition Taxonomy: Core Functions ─────────────────────────────


def _bfs_upstream(start: str, target: str, gt: GTContext) -> bool:
    """BFS from start along reverse GT edges (toward root cause), check if target is reachable.

    GT edges are (source, target) where source is upstream (closer to root).
    Reverse direction: from a node, follow edges backward to parents.
    """
    start_n = _normalize_service(start)
    target_n = _normalize_service(target)
    if start_n == target_n:
        return True

    # Build reverse adjacency: child -> [parent1, parent2, ...]
    reverse_adj: dict[str, list[str]] = {}
    for src, tgt in gt.service_edges:
        src_n = _normalize_service(src)
        tgt_n = _normalize_service(tgt)
        reverse_adj.setdefault(tgt_n, []).append(src_n)

    visited: set[str] = {start_n}
    queue: deque[str] = deque([start_n])

    while queue:
        current = queue.popleft()
        for neighbor in reverse_adj.get(current, []):
            if neighbor == target_n:
                return True
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return False


def _has_direct_edge(upstream: str, downstream: str, gt: GTContext) -> bool:
    """Check if there is a direct GT edge from upstream to downstream."""
    up_n = _normalize_service(upstream)
    down_n = _normalize_service(downstream)
    return any(
        _normalize_service(src) == up_n and _normalize_service(tgt) == down_n
        for src, tgt in gt.service_edges
    )


def _best_gt_service(services_on_gt: list[str], gt: GTContext) -> str | None:
    """Return the GT service with minimum distance to root (closest to root cause)."""
    best = None
    best_dist = float("inf")
    for s in services_on_gt:
        d = gt.distance_to_root(s)
        if d is not None and d < best_dist:
            best_dist = d
            best = s
    return best


def classify_transition(
    prev: ExtractedStep,
    next_step: ExtractedStep,
    prev_services: set[str],
    next_services: set[str],
    visited: set[str],
    gt: GTContext,
) -> tuple[str, list[str], list[str], int | None, int | None, bool]:
    """Classify a single step transition.

    Returns: (label, prev_gt_services, next_gt_services, prev_dist, next_dist, is_new)
    """
    prev_gt = [s for s in prev_services if gt.is_on_path(s)]
    next_gt = [s for s in next_services if gt.is_on_path(s)]

    prev_on = bool(prev_gt)
    next_on = bool(next_gt)

    # Quadrant 1: both OFF → derailed
    if not prev_on and not next_on:
        return "derailed", prev_gt, next_gt, None, None, False

    # Quadrant 2: prev ON, next OFF → drifted
    if prev_on and not next_on:
        return "drifted", prev_gt, next_gt, None, None, False

    # Quadrant 3: prev OFF, next ON → returned
    if not prev_on and next_on:
        next_gt_norm = {_normalize_service(s) for s in next_gt}
        visited_norm = {_normalize_service(s) for s in visited}
        is_revisit = bool(next_gt_norm & visited_norm)
        if is_revisit:
            return "returned:revisit", prev_gt, next_gt, None, None, False
        return "returned:discover", prev_gt, next_gt, None, None, True

    # Quadrant 4: both ON → compute distances
    prev_dist = min((d for s in prev_gt if (d := gt.distance_to_root(s)) is not None), default=None)
    next_dist = min((d for s in next_gt if (d := gt.distance_to_root(s)) is not None), default=None)

    # Safety: if distance computation fails (shouldn't happen with valid GT)
    if prev_dist is None or next_dist is None:
        return "lateral:explore", prev_gt, next_gt, prev_dist, next_dist, False

    # Check if next GT services are new
    next_gt_norm = {_normalize_service(s) for s in next_gt}
    visited_norm = {_normalize_service(s) for s in visited}
    is_new = not bool(next_gt_norm & visited_norm)

    # Same distance → lateral
    if next_dist == prev_dist:
        # Check if same services (prev and next overlap)
        prev_gt_norm = {_normalize_service(s) for s in prev_gt}
        if prev_gt_norm & next_gt_norm:
            return "lateral:revisit", prev_gt, next_gt, prev_dist, next_dist, False
        if not is_new:
            return "lateral:revisit", prev_gt, next_gt, prev_dist, next_dist, False
        return "lateral:explore", prev_gt, next_gt, prev_dist, next_dist, True

    # Distance increased → regressing (moving away from root cause)
    if next_dist > prev_dist:
        if not is_new:
            return "regressing:backtrack", prev_gt, next_gt, prev_dist, next_dist, False
        return "regressing:explore", prev_gt, next_gt, prev_dist, next_dist, True

    # Distance decreased → advancing (moving toward root cause)
    best_prev = _best_gt_service(prev_gt, gt)
    best_next = _best_gt_service(next_gt, gt)

    if best_prev and best_next:
        # Check direct edge: next (upstream) → prev (downstream)
        if _has_direct_edge(best_next, best_prev, gt):
            return "advancing:consecutive", prev_gt, next_gt, prev_dist, next_dist, is_new

        # Same-chain check: BFS upstream from prev, can we reach next?
        if _bfs_upstream(best_prev, best_next, gt):
            return "advancing:skip", prev_gt, next_gt, prev_dist, next_dist, is_new

    return "advancing:skip", prev_gt, next_gt, prev_dist, next_dist, is_new


def classify_rt_utilization_round(
    prev_round: dict,
    next_round: dict,
    gt: GTContext,
) -> str:
    """Classify R→T information utilization at Round level.

    prev_round's all result_services (GT only) vs next_round's all action_services.

    Returns:
      - "no_data": prev round found no GT services in results
      - "utilized": next round's action_services ⊆ prev round's result GT services
      - "partial": next round's action_services ∩ prev result GT ≠ ∅ but not full subset
      - "ignored": next round's action_services ∩ prev result GT = ∅
    """
    # Collect all GT services from prev round's results
    prev_result_gt_norm: set[str] = set()
    for step in prev_round["steps"]:
        for svc in step.result_services:
            if gt.is_on_path(svc):
                prev_result_gt_norm.add(_normalize_service(svc))

    if not prev_result_gt_norm:
        return "no_data"

    # Collect all action services from next round
    next_action_norm: set[str] = set()
    for step in next_round["steps"]:
        for svc in step.action_services:
            next_action_norm.add(_normalize_service(svc))

    if not next_action_norm:
        return "ignored"

    overlap = next_action_norm & prev_result_gt_norm
    if not overlap:
        return "ignored"
    if next_action_norm <= prev_result_gt_norm:
        return "utilized"
    return "partial"


def _select_primary_service(
    action_services: list[str],
    all_services: list[str],
    gt: GTContext,
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
    candidates = action_services if action_services else all_services
    if not candidates:
        return None

    def sort_key(svc: str) -> tuple:
        n = _normalize_service(svc)
        on_gt = gt.is_on_path(svc)
        dist = gt.distance_to_root(svc) if on_gt else None
        dist_val = dist if dist is not None else 999
        is_visited = n in visited_norm
        count = visit_counts.get(n, 0)
        return (dist_val, is_visited, -count)

    return min(candidates, key=sort_key)


def _aggregate_rounds(
    steps: list[ExtractedStep],
    gt: GTContext,
) -> list[dict]:
    """Aggregate steps by assistant_turn_index into Rounds.

    Each Round = one LLM assistant turn's tool_calls. Transitions only
    between Rounds, not within. This matches viz_trajectory.py's logic.
    """
    from itertools import groupby

    visited_norm: set[str] = set()
    visit_counts: dict[str, int] = {}

    # Group steps by turn
    non_discovery = [s for s in steps if s.action_intent != "discovery"]
    turn_groups: list[tuple[int, list[ExtractedStep]]] = []
    for turn_idx, group in groupby(non_discovery, key=lambda s: s.assistant_turn_index):
        turn_groups.append((turn_idx, list(group)))

    rounds: list[dict] = []
    round_idx = 0

    for turn_idx, turn_steps in turn_groups:
        # Collect action services and all services (action + result)
        action_svcs: list[str] = []
        all_services: list[str] = []
        seen_action: set[str] = set()
        seen_all: set[str] = set()
        for step in turn_steps:
            for svc in step.action_services:
                if svc not in seen_action:
                    action_svcs.append(svc)
                    seen_action.add(svc)
            for svc in list(step.action_services) + list(step.result_services):
                if svc not in seen_all:
                    all_services.append(svc)
                    seen_all.add(svc)

        primary = _select_primary_service(
            action_svcs, all_services, gt, visited_norm, visit_counts,
        )
        if not primary:
            continue

        primary_on_gt = gt.is_on_path(primary)
        primary_dist = gt.distance_to_root(primary) if primary_on_gt else None

        rounds.append({
            "round_index": round_idx,
            "primary_service": primary,
            "all_services": all_services,
            "on_gt_path": primary_on_gt,
            "distance_to_root": primary_dist,
            "steps": turn_steps,
        })
        round_idx += 1

        # Update visited and counts for ALL services (action + result)
        for svc in all_services:
            n = _normalize_service(svc)
            visited_norm.add(n)
            visit_counts[n] = visit_counts.get(n, 0) + 1

    return rounds


def analyze_transitions(
    sample_id: int,
    correct: bool,
    steps: list[ExtractedStep],
    gt: GTContext,
) -> TransitionReport:
    """Analyze Round-based transitions for a single sample.

    Steps are aggregated into Rounds (by assistant_turn_index).
    Transitions are classified between adjacent Rounds based on
    primary_service's BFS distance to root cause on the GT causal graph.
    """
    report = TransitionReport(sample_id=sample_id, correct=correct)

    rounds = _aggregate_rounds(steps, gt)
    if len(rounds) < 2:
        return report

    visited_norm: set[str] = set()

    for i in range(len(rounds) - 1):
        prev_r = rounds[i]
        next_r = rounds[i + 1]

        # Mark prev round as visited BEFORE checking next round
        for svc in prev_r["all_services"]:
            visited_norm.add(_normalize_service(svc))

        prev_svc = prev_r["primary_service"]
        next_svc = next_r["primary_service"]

        prev_on = prev_r["on_gt_path"]
        next_on = next_r["on_gt_path"]
        prev_dist = prev_r["distance_to_root"]
        next_dist = next_r["distance_to_root"]

        next_visited = _normalize_service(next_svc) in visited_norm

        # Classify transition
        label, prev_gt, next_gt, is_new = _classify_round_transition(
            prev_on, next_on, prev_dist, next_dist, next_visited,
            prev_svc, next_svc, gt,
        )

        # R→T utilization at round level
        rt = classify_rt_utilization_round(prev_r, next_r, gt)

        report.transitions.append(StepTransition(
            pair=(prev_r["round_index"], next_r["round_index"]),
            label=label,
            rt_utilization=rt,
            prev_services_on_gt=prev_gt,
            next_services_on_gt=next_gt,
            prev_dist=prev_dist,
            next_dist=next_dist,
            is_new_service=is_new,
        ))

    # Compute rates
    _compute_transition_rates(report)

    return report


def _classify_round_transition(
    prev_on: bool, next_on: bool,
    prev_dist: int | None, next_dist: int | None,
    next_visited: bool,
    prev_svc: str, next_svc: str,
    gt: GTContext,
) -> tuple[str, list[str], list[str], bool]:
    """Classify a single Round-to-Round transition.

    Returns: (label, prev_gt_services, next_gt_services, is_new)
    """
    prev_gt = [prev_svc] if prev_on else []
    next_gt = [next_svc] if next_on else []

    # Both off path
    if not prev_on and not next_on:
        return "derailed", prev_gt, next_gt, False

    # Drifted off path
    if prev_on and not next_on:
        return "drifted", prev_gt, next_gt, False

    # Returned to path
    if not prev_on and next_on:
        if next_visited:
            return "returned:revisit", prev_gt, next_gt, False
        return "returned:discover", prev_gt, next_gt, True

    # Both on path — compare BFS distances
    if prev_dist is not None and next_dist is not None:
        is_new = not next_visited

        if next_dist < prev_dist:
            diff = prev_dist - next_dist
            label = "advancing:consecutive" if diff == 1 else "advancing:skip"
            return label, prev_gt, next_gt, is_new
        elif next_dist == prev_dist:
            label = "lateral:revisit" if next_visited else "lateral:explore"
            return label, prev_gt, next_gt, is_new
        else:
            label = "regressing:backtrack" if next_visited else "regressing:explore"
            return label, prev_gt, next_gt, is_new

    return "lateral:explore", prev_gt, next_gt, False


def _compute_transition_rates(report: TransitionReport) -> None:
    """Compute summary rates from transitions."""
    n = len(report.transitions)
    if n == 0:
        return

    labels = [t.label for t in report.transitions]
    major_labels = [lab.split(":")[0] for lab in labels]

    advancing_count = major_labels.count("advancing")
    report.advancing_rate = advancing_count / n
    report.derailed_rate = major_labels.count("derailed") / n
    report.drifted_rate = major_labels.count("drifted") / n
    report.returned_rate = major_labels.count("returned") / n
    report.regressing_rate = major_labels.count("regressing") / n

    if advancing_count > 0:
        report.consecutive_rate = labels.count("advancing:consecutive") / advancing_count

    # R→T rates (4 states: utilized / partial / ignored / no_data)
    report.rt_utilized_rate = sum(1 for t in report.transitions if t.rt_utilization == "utilized") / n
    report.rt_partial_rate = sum(1 for t in report.transitions if t.rt_utilization == "partial") / n
    report.rt_ignored_rate = sum(1 for t in report.transitions if t.rt_utilization == "ignored") / n
    report.rt_no_data_rate = sum(1 for t in report.transitions if t.rt_utilization == "no_data") / n


# ── Formatting ───────────────────────────────────────────────────────────────


def format_report(report: CoherenceReport) -> str:
    """Format a single sample's coherence report as text."""
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append(f"COHERENCE REPORT - Sample {report.sample_id} (correct={report.correct})")
    lines.append("=" * 80)

    # Summary rates
    lines.append(f"\n{'─' * 60}")
    lines.append("SUMMARY RATES")
    lines.append(f"{'─' * 60}")
    lines.append("  Internal:")
    lines.append(f"    ① T→A service match:    {report.ta_service_match_rate:.1%}")
    lines.append(f"    ① T→A datatype match:   {report.ta_datatype_match_rate:.1%}")
    lines.append(f"    ② A→R effectiveness:    {report.ar_effectiveness_rate:.1%}")
    lines.append(f"    ② A→R GT discovery:     {report.ar_gt_discovery_rate:.1%}")
    lines.append("  External:")
    lines.append(f"    ③ T→T advancing:        {report.tt_advancing_rate:.1%}")
    lines.append(f"    ④ R→T utilization:      {report.rt_utilization_rate:.1%}")
    lines.append(f"    ⑤ A→A on_path:          {report.aa_on_path_rate:.1%}")

    # Internal details
    lines.append(f"\n{'─' * 60}")
    lines.append("INTERNAL COHERENCE (per step)")
    lines.append(f"{'─' * 60}")
    lines.append(f"  {'#':>3}  {'T→A svc':>10}  {'T→A dt':>10}  {'A→R eff':>10}  GT found")
    for ic in report.internal:
        gt_str = ", ".join(ic.ar_gt_services_found) if ic.ar_gt_services_found else "—"
        lines.append(
            f"  {ic.step_index:>3}  {ic.ta_service_match:>10}  {ic.ta_datatype_match:>10}"
            f"  {ic.ar_effectiveness:>10}  {gt_str}"
        )

    # External details
    if report.external:
        lines.append(f"\n{'─' * 60}")
        lines.append("EXTERNAL COHERENCE (adjacent pairs)")
        lines.append(f"{'─' * 60}")
        lines.append(f"  {'pair':>8}  {'③ T→T':>12}  {'④ R→T':>10}  {'⑤ A→A':>10}")
        for ec in report.external:
            pair_str = f"#{ec.pair[0]}→#{ec.pair[1]}"
            lines.append(f"  {pair_str:>8}  {ec.tt_progression:>12}  {ec.rt_utilization:>10}  {ec.aa_drift:>10}")

    return "\n".join(lines)


def format_aggregate_report(reports: list[CoherenceReport]) -> str:
    """Format aggregate statistics across all samples."""
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("AGGREGATE COHERENCE REPORT")
    lines.append("=" * 80)

    total = len(reports)
    correct_reports = [r for r in reports if r.correct]
    incorrect_reports = [r for r in reports if not r.correct]
    lines.append(f"\nSamples: {total} (correct: {len(correct_reports)}, incorrect: {len(incorrect_reports)})")

    def avg_rate(rs: list[CoherenceReport], attr: str) -> float:
        vals = [getattr(r, attr) for r in rs]
        return sum(vals) / len(vals) if vals else 0.0

    metrics = [
        ("① T→A service match", "ta_service_match_rate"),
        ("① T→A datatype match", "ta_datatype_match_rate"),
        ("② A→R effectiveness", "ar_effectiveness_rate"),
        ("② A→R GT discovery", "ar_gt_discovery_rate"),
        ("③ T→T advancing", "tt_advancing_rate"),
        ("④ R→T utilization", "rt_utilization_rate"),
        ("⑤ A→A on_path", "aa_on_path_rate"),
    ]

    lines.append(f"\n{'─' * 60}")
    lines.append(f"  {'Metric':<30} {'All':>8} {'Correct':>8} {'Incorrect':>8}  {'Delta':>8}")
    lines.append(f"{'─' * 60}")
    for label, attr in metrics:
        all_avg = avg_rate(reports, attr)
        cor_avg = avg_rate(correct_reports, attr) if correct_reports else 0.0
        inc_avg = avg_rate(incorrect_reports, attr) if incorrect_reports else 0.0
        delta = cor_avg - inc_avg
        delta_str = f"+{delta:.1%}" if delta >= 0 else f"{delta:.1%}"
        lines.append(f"  {label:<30} {all_avg:>7.1%} {cor_avg:>8.1%} {inc_avg:>8.1%}  {delta_str:>8}")

    # Distribution of external coherence values
    from collections import Counter

    lines.append(f"\n{'─' * 60}")
    lines.append("EXTERNAL COHERENCE DISTRIBUTION")
    lines.append(f"{'─' * 60}")

    for label, field_name in [("③ T→T progression", "tt_progression"), ("④ R→T utilization", "rt_utilization"), ("⑤ A→A drift", "aa_drift")]:
        all_vals = Counter(getattr(ec, field_name) for r in reports for ec in r.external)
        cor_vals = Counter(getattr(ec, field_name) for r in correct_reports for ec in r.external)
        inc_vals = Counter(getattr(ec, field_name) for r in incorrect_reports for ec in r.external)

        total_all = sum(all_vals.values()) or 1
        total_cor = sum(cor_vals.values()) or 1
        total_inc = sum(inc_vals.values()) or 1

        lines.append(f"\n  {label}:")
        all_keys = sorted(set(all_vals.keys()) | set(cor_vals.keys()) | set(inc_vals.keys()))
        for k in all_keys:
            a = all_vals.get(k, 0) / total_all
            c = cor_vals.get(k, 0) / total_cor
            i = inc_vals.get(k, 0) / total_inc
            lines.append(f"    {k:<15} all={a:>5.1%}  correct={c:>5.1%}  incorrect={i:>5.1%}")

    return "\n".join(lines)


def format_transition_report(report: TransitionReport) -> str:
    """Format a single sample's step transition report as text."""
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append(f"TRANSITION REPORT - Sample {report.sample_id} (correct={report.correct})")
    lines.append("=" * 80)

    # Summary rates
    lines.append(f"\n{'─' * 60}")
    lines.append("SUMMARY RATES")
    lines.append(f"{'─' * 60}")
    lines.append(f"  advancing:     {report.advancing_rate:>6.1%}  (consecutive: {report.consecutive_rate:.1%})")
    lines.append(f"  derailed:      {report.derailed_rate:>6.1%}")
    lines.append(f"  drifted:       {report.drifted_rate:>6.1%}  (hallucinated: {report.hallucination_rate:.1%})")
    lines.append(f"  returned:      {report.returned_rate:>6.1%}")
    lines.append(f"  regressing:    {report.regressing_rate:>6.1%}")
    lines.append(f"  R→T utilized:  {report.rt_utilized_rate:>6.1%}")

    # Transition details
    if report.transitions:
        lines.append(f"\n{'─' * 60}")
        lines.append("TRANSITIONS (per pair)")
        lines.append(f"{'─' * 60}")
        lines.append(f"  {'pair':>8}  {'label':<25} {'R→T':<10} {'dist':>8}  {'new?':>4}  GT services")
        for t in report.transitions:
            pair_str = f"#{t.pair[0]}→#{t.pair[1]}"
            dist_str = f"{t.prev_dist}→{t.next_dist}" if t.prev_dist is not None and t.next_dist is not None else "—"
            new_str = "NEW" if t.is_new_service else ""
            gt_str = ", ".join(t.next_services_on_gt) if t.next_services_on_gt else "—"
            lines.append(
                f"  {pair_str:>8}  {t.label:<25} {t.rt_utilization:<10} {dist_str:>8}  {new_str:>4}  {gt_str}"
            )

    return "\n".join(lines)


def format_aggregate_transition_report(reports: list[TransitionReport]) -> str:
    """Format aggregate transition statistics across all samples."""
    from collections import Counter

    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("AGGREGATE TRANSITION REPORT")
    lines.append("=" * 80)

    total = len(reports)
    correct_reports = [r for r in reports if r.correct]
    incorrect_reports = [r for r in reports if not r.correct]
    lines.append(f"\nSamples: {total} (correct: {len(correct_reports)}, incorrect: {len(incorrect_reports)})")

    def avg_rate(rs: list[TransitionReport], attr: str) -> float:
        vals = [getattr(r, attr) for r in rs]
        return sum(vals) / len(vals) if vals else 0.0

    metrics = [
        ("advancing", "advancing_rate"),
        ("  consecutive/advancing", "consecutive_rate"),
        ("derailed", "derailed_rate"),
        ("drifted", "drifted_rate"),
        ("returned", "returned_rate"),
        ("regressing", "regressing_rate"),
        ("R→T utilized", "rt_utilized_rate"),
    ]

    lines.append(f"\n{'─' * 70}")
    lines.append(f"  {'Metric':<30} {'All':>8} {'Correct':>8} {'Incorrect':>8}  {'Delta':>8}")
    lines.append(f"{'─' * 70}")
    for label, attr in metrics:
        all_avg = avg_rate(reports, attr)
        cor_avg = avg_rate(correct_reports, attr) if correct_reports else 0.0
        inc_avg = avg_rate(incorrect_reports, attr) if incorrect_reports else 0.0
        delta = cor_avg - inc_avg
        delta_str = f"+{delta:.1%}" if delta >= 0 else f"{delta:.1%}"
        lines.append(f"  {label:<30} {all_avg:>7.1%} {cor_avg:>8.1%} {inc_avg:>8.1%}  {delta_str:>8}")

    # Label distribution
    lines.append(f"\n{'─' * 70}")
    lines.append("TRANSITION LABEL DISTRIBUTION")
    lines.append(f"{'─' * 70}")

    all_labels = Counter(t.label for r in reports for t in r.transitions)
    cor_labels = Counter(t.label for r in correct_reports for t in r.transitions)
    inc_labels = Counter(t.label for r in incorrect_reports for t in r.transitions)

    total_all = sum(all_labels.values()) or 1
    total_cor = sum(cor_labels.values()) or 1
    total_inc = sum(inc_labels.values()) or 1

    # Sort by major category then sub-label
    label_order = [
        "advancing:consecutive", "advancing:skip",
        "lateral:revisit", "lateral:explore",
        "returned:revisit", "returned:discover",
        "regressing:backtrack", "regressing:explore",
        "derailed", "drifted",
    ]
    all_keys = sorted(
        set(all_labels.keys()) | set(cor_labels.keys()) | set(inc_labels.keys()),
        key=lambda x: label_order.index(x) if x in label_order else 99,
    )
    for k in all_keys:
        a = all_labels.get(k, 0) / total_all
        c = cor_labels.get(k, 0) / total_cor
        i = inc_labels.get(k, 0) / total_inc
        lines.append(f"  {k:<25} all={a:>5.1%}  correct={c:>5.1%}  incorrect={i:>5.1%}")

    # R→T utilization distribution
    lines.append(f"\n{'─' * 70}")
    lines.append("R→T UTILIZATION DISTRIBUTION")
    lines.append(f"{'─' * 70}")

    all_rt = Counter(t.rt_utilization for r in reports for t in r.transitions)
    cor_rt = Counter(t.rt_utilization for r in correct_reports for t in r.transitions)
    inc_rt = Counter(t.rt_utilization for r in incorrect_reports for t in r.transitions)

    total_all_rt = sum(all_rt.values()) or 1
    total_cor_rt = sum(cor_rt.values()) or 1
    total_inc_rt = sum(inc_rt.values()) or 1

    for k in ["utilized", "ignored", "no_data"]:
        a = all_rt.get(k, 0) / total_all_rt
        c = cor_rt.get(k, 0) / total_cor_rt
        i = inc_rt.get(k, 0) / total_inc_rt
        lines.append(f"  {k:<25} all={a:>5.1%}  correct={c:>5.1%}  incorrect={i:>5.1%}")

    return "\n".join(lines)
