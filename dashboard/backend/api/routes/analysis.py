"""API routes for trajectory analysis (n-gram & triplet coherence).

All analysis results are cached in memory after first computation.
Call POST /analysis/refresh to clear cache and recompute.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, select

# Add project root for imports
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from api.deps import get_db
from rcabench_platform.v3.sdk.llm_eval.db.eval_datapoint import EvaluationSample
from sota_rca.analysis.extractor import GTContext, ExtractedStep, extract_steps
from sota_rca.analysis.ngram_analysis import analyze_ngrams, analyze_single_sample
from sota_rca.analysis.trajectory_normalizer import normalize_by_agent
from sota_rca.analysis.triplet_coherence import analyze_transitions
from rcabench_platform.v3.sdk.evaluation.causal_graph import CausalGraph

# Preferred intent sources, priority order:
# 1. `final` → human-curated authoritative labels (intent only, no data_type)
# 2. `claude_opus_4_6` → original LLM classification (intent + data_type)
# Both are merged during overlay: final overrides intent, 4.6 provides data_type.
_LLM_INTENT_MODEL_KEY = "claude_opus_4_6"
_FINAL_INTENT_KEY = "final"

# exp_ids that belong to the new 5-agent strict-LLM batch. When strict, steps
# without a matching LLM intent get action_intent="unlabeled" (downstream
# n-gram / transition / radar endpoints filter those out), so rule-based labels
# never leak into the new pipeline. Demo (48-case) stays non-strict.
_STRICT_AGENT_TYPES = {"claudecode", "aiq", "taskweaver"}
_THINKDEPTHAI_STRICT_EXP_IDS = {
    "thinkdepthai-claude-sonnet-4.6",
    "thinkdepthai-qwen3.5-plus",
}


def _agent_type_from_exp(exp_id: str) -> str:
    return exp_id.split("-", 1)[0] if exp_id else ""


def _is_strict_exp(exp_id: str) -> bool:
    return (
        _agent_type_from_exp(exp_id) in _STRICT_AGENT_TYPES
        or exp_id in _THINKDEPTHAI_STRICT_EXP_IDS
    )


def _extract_steps_with_llm_intents(
    sample: EvaluationSample,
    strict_llm: bool | None = None,
) -> list[ExtractedStep]:
    """Extract steps from trajectory, overlaying LLM-classified intents if available.

    Args:
        sample: EvaluationSample row to extract from.
        strict_llm: When True, steps without an LLM intent entry get
            action_intent="unlabeled" (instead of keeping the rule-based intent).
            When False, legacy behavior: rule-based intents remain when LLM
            labels are absent. When None (default), auto-detected from
            sample.exp_id via `_is_strict_exp`.
    """
    traj = sample.trajectories
    if not traj:
        return []
    if isinstance(traj, str):
        try:
            traj = json.loads(traj)
        except (json.JSONDecodeError, ValueError):
            return []
    if not isinstance(traj, list):
        return []

    # Framework-specific normalization (e.g., claudecode Bash -> query_parquet_files)
    exp_id = sample.exp_id or ""
    traj = normalize_by_agent(_agent_type_from_exp(exp_id), traj)

    if strict_llm is None:
        strict_llm = _is_strict_exp(exp_id)

    steps = extract_steps(traj)
    if not steps:
        return steps

    # Overlay intents — priority: `final` (human-curated) > `claude_opus_4_6` (LLM)
    meta = sample.meta if isinstance(sample.meta, dict) else {}
    llm_intents_old = meta.get("llm_intents", {}).get(_LLM_INTENT_MODEL_KEY, [])
    final_intents = meta.get("llm_intents", {}).get(_FINAL_INTENT_KEY, [])

    if not llm_intents_old and not final_intents:
        if strict_llm:
            for step in steps:
                if step.action_intent != "discovery":
                    step.action_intent = "unlabeled"
        return steps

    # Build lookup: (round, sql_index) → entry
    old_lookup: dict[tuple[int, int], dict] = {
        (e["round"], e.get("sql_index", 1)): e for e in llm_intents_old
    }
    final_lookup: dict[tuple[int, int], dict] = {
        (e["round"], e.get("sql_index", 1)): e for e in final_intents
    }

    # Map steps to (turn_index, sql_position) — skip discovery steps
    turn_counts: dict[int, int] = {}
    for step in steps:
        if step.action_intent == "discovery":
            continue
        turn = step.assistant_turn_index
        turn_counts[turn] = turn_counts.get(turn, 0) + 1
        sql_idx = turn_counts[turn]
        pos = (turn, sql_idx)

        old_entry = old_lookup.get(pos)
        final_entry = final_lookup.get(pos)

        # Intent: prefer final, fall back to old LLM
        if final_entry and final_entry.get("intent"):
            step.action_intent = final_entry["intent"]
        elif old_entry and old_entry.get("intent"):
            step.action_intent = old_entry["intent"]
        elif strict_llm:
            step.action_intent = "unlabeled"

        # data_type: only available in old LLM entries
        if old_entry and old_entry.get("data_type") and old_entry["data_type"] != "unknown":
            step.action_data_type = old_entry["data_type"]

    return steps

_logger = logging.getLogger(__name__)

DBSession = Annotated[Session, Depends(get_db)]

router = APIRouter()

# ── Persistent cache ─────────────────────────────────────────────────────────
# Cache stored as JSON file, loaded at startup, updated on refresh.
_CACHE_FILE = Path(os.environ.get("ANALYSIS_CACHE_FILE",
    str(Path(__file__).parent.parent.parent.parent / "analysis_cache.json")))
_cache: dict[str, Any] = {}

# Method 2 Δ charts pool these thinkdepthai experiments only. Currently the
# allowlist restricts display to claude-sonnet-4.6 + qwen3.5-plus, so pooling
# happens over 2 models.
_POOLED_EXP_IDS = {
    "thinkdepthai-claude-sonnet-4.6",
    "thinkdepthai-qwen3.5-plus",
}


def _cache_key(endpoint: str, exp_ids: list[str] | None) -> str:
    if exp_ids:
        return f"{endpoint}|{','.join(sorted(exp_ids))}"
    return f"{endpoint}|all"


# ── Schemas ──────────────────────────────────────────────────────────────────


class NgramBarItem(BaseModel):
    """A single bar in the n-gram comparison chart."""

    ngram: str
    correct_count: int
    incorrect_count: int


class NgramChartData(BaseModel):
    """N-gram chart data for a specific n value and experiment."""

    exp_id: str
    n: int
    total_samples: int = 0
    correct_samples: int = 0
    incorrect_samples: int = 0
    items: list[NgramBarItem]


class PooledDeltaItem(BaseModel):
    """A single label/pattern with its Method 2 weighted delta."""

    label: str
    pooled_delta: float
    model_deltas: dict[str, float] = {}


class PooledDeltaChart(BaseModel):
    """Method 2 pooled overview chart data."""

    method: str = "method2_weighted_delta"
    total_models: int
    total_cases: int
    items: list[PooledDeltaItem]


class NgramPooledDelta(BaseModel):
    """Method 2 pooled delta for n-grams at a specific n."""

    n: int
    items: list[PooledDeltaItem]


class NgramResponse(BaseModel):
    """Response containing n-gram charts for all experiments and n values."""

    charts: list[NgramChartData]
    pooled_deltas: list[NgramPooledDelta] = []


class TransitionLabelItem(BaseModel):
    """Distribution of a single transition label."""

    label: str
    correct_pct: float
    incorrect_pct: float
    all_pct: float


class TransitionExpData(BaseModel):
    """Transition taxonomy data for a single experiment."""

    exp_id: str
    correct_count: int
    incorrect_count: int
    correct_rates: dict[str, float]
    incorrect_rates: dict[str, float]
    label_distribution: list[TransitionLabelItem]
    total_transitions: int = 0  # total spatial transitions (correct + incorrect)


class TransitionResponse(BaseModel):
    """Response containing step transition taxonomy data."""

    rate_keys: list[str]
    rate_labels: dict[str, str]
    experiments: list[TransitionExpData]
    aggregated: TransitionExpData | None = None
    pooled_delta: PooledDeltaChart | None = None


# ── Markov Chain Analysis Schemas ─────────────────────────────────────────


class MarkovTransitionCell(BaseModel):
    """A single cell in the transition matrix."""

    from_state: str
    to_state: str
    correct_prob: float
    incorrect_prob: float


class MarkovStateMetrics(BaseModel):
    """Per-state metrics."""

    state: str
    correct_stationary: float  # pi for correct group
    incorrect_stationary: float  # pi for incorrect group
    kl_divergence: float  # row-level KL(correct || incorrect)


class MarkovLayerData(BaseModel):
    """Markov chain analysis for one layer (modality:intent or intent-only)."""

    states: list[str]
    transitions: list[MarkovTransitionCell]
    state_metrics: list[MarkovStateMetrics]
    correct_entropy: float
    incorrect_entropy: float
    total_kl: float


class MarkovExpData(BaseModel):
    """Markov chain analysis for a single experiment."""

    exp_id: str
    correct_count: int
    incorrect_count: int
    states: list[str]  # ordered state labels
    transitions: list[MarkovTransitionCell]  # flat list of matrix cells
    state_metrics: list[MarkovStateMetrics]
    correct_entropy: float  # H(next|current) for correct group
    incorrect_entropy: float  # H(next|current) for incorrect group
    total_kl: float  # average KL divergence across states
    intent_only: MarkovLayerData | None = None  # intent-only layer
    phase_layer: MarkovLayerData | None = None  # 5-phase aggregated layer


class MarkovResponse(BaseModel):
    """Response containing Markov chain analysis."""

    experiments: list[MarkovExpData]


# ── Intent → Phase Mapping (19 intents → 5 phases) ──────────────────────────

INTENT_TO_PHASE: dict[str, str] = {
    # triage（分诊定向）
    "latency_ranking": "triage",
    "throughput_compare": "triage",
    "error_rate_scan": "triage",
    "error_log_overview": "triage",
    "metric_scan": "triage",
    # trace_investigate（链路调查）
    "service_trace_scan": "trace_investigate",
    "trace_follow": "trace_investigate",
    "call_tree_build": "trace_investigate",
    # log_investigate（日志调查）
    "service_error_log": "log_investigate",
    "service_log_browse": "log_investigate",
    "keyword_search": "log_investigate",
    "error_timeline": "log_investigate",
    # metric_diagnose（指标诊断）
    "container_resource": "metric_diagnose",
    "jvm_state": "metric_diagnose",
    "network_layer": "metric_diagnose",
    "k8s_state": "metric_diagnose",
    "db_state": "metric_diagnose",
    # baseline（基线对比）
    "baseline_collect": "baseline",
    "baseline_contrast": "baseline",
}


def intent_to_phase(intent: str, data_type: str = "") -> str:
    """Map intent to 5-phase (cognitive depth grouping). No dynamic mapping needed."""
    return INTENT_TO_PHASE.get(intent, "triage")


# ── Fingerprint Schemas ──────────────────────────────────────────────────────


class FingerprintDimension(BaseModel):
    """A single dimension in the behavioral fingerprint."""

    key: str
    label: str
    value: float  # 0~1 normalized
    raw_value: float  # original value before normalization


class FingerprintExpData(BaseModel):
    """Behavioral fingerprint for a single experiment."""

    exp_id: str
    model_name: str | None = None
    total_samples: int
    accuracy: float
    dimensions: list[FingerprintDimension]


class FingerprintResponse(BaseModel):
    """Response containing behavioral fingerprints for multi-model comparison."""

    dimension_keys: list[str]
    dimension_labels: dict[str, str]
    experiments: list[FingerprintExpData]


class IntentHeatmapCell(BaseModel):
    """A single cell in the intent × model heatmap."""

    intent: str
    exp_id: str
    usage_rate: float  # % of samples that use this intent
    correct_rate: float  # usage rate among correct samples
    incorrect_rate: float  # usage rate among incorrect samples


class IntentHeatmapResponse(BaseModel):
    """Response for intent distribution heatmap."""

    intents: list[str]  # row labels (ordered)
    experiments: list[str]  # column labels (ordered)
    cells: list[IntentHeatmapCell]


class ModalityProgressionBin(BaseModel):
    """A single bin in the modality progression chart."""

    progress: float  # 0.0 ~ 1.0 (center of bin)
    logs: float  # proportion 0~1
    traces: float
    metrics: float


class ModalityProgressionExpData(BaseModel):
    """Modality progression for a single experiment."""

    exp_id: str
    bins: list[ModalityProgressionBin]


class ModalityProgressionResponse(BaseModel):
    """Response for modality progression stacked area chart."""

    experiments: list[ModalityProgressionExpData]


# ── Cache Management ─────────────────────────────────────────────────────────

# Response model registry for deserialization
_RESPONSE_MODELS: dict[str, type[BaseModel]] = {
    "ngrams": NgramResponse,
    "transitions": TransitionResponse,
    "markov": MarkovResponse,
    "fingerprint": FingerprintResponse,
    "intent-heatmap": IntentHeatmapResponse,
    "modality-progression": ModalityProgressionResponse,
}


def _save_cache() -> None:
    """Persist cache to JSON file."""
    try:
        serializable = {}
        for k, v in _cache.items():
            serializable[k] = v.model_dump() if hasattr(v, "model_dump") else v
        _CACHE_FILE.write_text(json.dumps(serializable, ensure_ascii=False))
        _logger.info(f"[Cache] Saved {len(serializable)} entries to {_CACHE_FILE}")
    except Exception as e:
        _logger.warning(f"[Cache] Failed to save: {e}")


def _load_cache() -> int:
    """Load cache from JSON file. Returns number of entries loaded."""
    if not _CACHE_FILE.exists():
        return 0
    try:
        data = json.loads(_CACHE_FILE.read_text())
        for k, v in data.items():
            endpoint = k.split("|")[0]
            model_cls = _RESPONSE_MODELS.get(endpoint)
            if model_cls:
                _cache[k] = model_cls(**v)
            else:
                _cache[k] = v
        _logger.info(f"[Cache] Loaded {len(data)} entries from {_CACHE_FILE}")
        return len(data)
    except Exception as e:
        _logger.warning(f"[Cache] Failed to load: {e}")
        return 0


@router.post("/analysis/refresh")
def refresh_analysis_cache(db: DBSession = None):
    """Clear cache, recompute ALL endpoints for ALL experiments, persist to file."""
    _cache.clear()
    _precompute_all(db)
    return {"status": "ok", "cached": len(_cache)}


@router.get("/analysis/cache-status")
def cache_status():
    """Show what's cached."""
    return {"entries": len(_cache), "keys": sorted(_cache.keys())}


def _precompute_all(session: Session) -> None:
    """Pre-compute all 6 analysis endpoints for each experiment. Called at startup."""
    start = time.time()
    samples = _get_judged_samples(session)
    if not samples:
        _logger.info("[Cache] No judged samples, skipping precompute")
        return

    exp_ids = sorted(set(s.exp_id for s in samples))
    # Apply prod allowlist if configured
    from api.deps import get_allowed_exp_ids
    allowed = get_allowed_exp_ids()
    if allowed:
        exp_ids = [e for e in exp_ids if e in allowed]
        _logger.info(f"[Cache] Allowlist active: {len(exp_ids)} experiments selected")
    _logger.info(f"[Cache] Precomputing 6 endpoints × {len(exp_ids)} experiments ({len(samples)} samples)...\n"
                 f"  Order: transitions → markov → modality → ngrams → fingerprint → intent-heatmap")

    for eid in exp_ids:
        exp_samples = [s for s in samples if s.exp_id == eid]
        t0 = time.time()

        # 1. Transitions (needed by fingerprint for evidence_rt_rate)
        try:
            key = _cache_key("transitions", [eid])
            if key not in _cache:
                _cache[key] = _compute_transitions(exp_samples, eid)
        except Exception as e:
            _logger.warning(f"[Cache] transitions failed for {eid}: {e}")

        # 2. Markov
        try:
            key = _cache_key("markov", [eid])
            if key not in _cache:
                _cache[key] = _compute_markov(exp_samples, eid)
        except Exception as e:
            _logger.warning(f"[Cache] markov failed for {eid}: {e}")

        # 3. Modality progression
        try:
            key = _cache_key("modality-progression", [eid])
            if key not in _cache:
                _cache[key] = _compute_modality_progression(exp_samples, eid)
        except Exception as e:
            _logger.warning(f"[Cache] modality-progression failed for {eid}: {e}")

        # 4. Ngrams
        try:
            key = _cache_key("ngrams", [eid])
            if key not in _cache:
                _cache[key] = _compute_ngrams(exp_samples, eid, n_max=6, top_k=8)
        except Exception as e:
            _logger.warning(f"[Cache] ngrams failed for {eid}: {e}")

        # 5. Fingerprint (depends on transitions cache for evidence_rt_rate)
        try:
            key = _cache_key("fingerprint", [eid])
            if key not in _cache:
                _cache[key] = _compute_fingerprint_response(exp_samples, eid)
        except Exception as e:
            _logger.warning(f"[Cache] fingerprint failed for {eid}: {e}")

        # 6. Intent heatmap
        try:
            key = _cache_key("intent-heatmap", [eid])
            if key not in _cache:
                _cache[key] = _compute_intent_heatmap(exp_samples, eid)
        except Exception as e:
            _logger.warning(f"[Cache] intent-heatmap failed for {eid}: {e}")

        _logger.info(f"[Cache] {eid}: 6 endpoints in {time.time()-t0:.1f}s")

    elapsed = time.time() - start
    _logger.info(f"[Cache] Precompute done in {elapsed:.1f}s, {len(_cache)} entries")
    _save_cache()


def _compute_ngrams(exp_samples: list[EvaluationSample], eid: str, n_max: int = 6, top_k: int = 8) -> NgramResponse:
    """Compute ngrams for a single experiment."""
    ngram_results = []
    for sample in exp_samples:
        if not sample.trajectories:
            continue
        steps = _extract_steps_with_llm_intents(sample)
        if not steps:
            continue
        steps = [s for s in steps if s.action_intent != "discovery"]
        if not steps:
            continue
        result = analyze_single_sample(sample_id=sample.id, correct=bool(sample.correct), steps=steps, n_range=(1, n_max))
        ngram_results.append(result)

    if not ngram_results:
        return NgramResponse(charts=[])

    total_samples = len(ngram_results)
    correct_samples = sum(1 for r in ngram_results if r.correct)
    incorrect_samples = total_samples - correct_samples

    report = analyze_ngrams(ngram_results, n_range=(1, n_max))
    charts = []
    for n_val in range(1, n_max):
        accuracy_data = report.ngram_accuracy.get(n_val, {})
        if not accuracy_data:
            continue
        sorted_ngrams = sorted(accuracy_data.items(), key=lambda x: x[1].total, reverse=True)[:top_k]
        items = []
        for ng, acc in sorted_ngrams:
            ng_str = " -> ".join(ng)
            items.append(NgramBarItem(ngram=ng_str, correct_count=acc.correct, incorrect_count=acc.total - acc.correct))
        if items:
            charts.append(NgramChartData(
                exp_id=eid, n=n_val, items=items,
                total_samples=total_samples, correct_samples=correct_samples, incorrect_samples=incorrect_samples,
            ))
    return NgramResponse(charts=charts)


def _compute_transitions(exp_samples: list[EvaluationSample], eid: str) -> TransitionResponse:
    """Compute Round-based transitions for a single experiment (cache builder).

    Uses the same 10-type taxonomy + 4-state R→T as get_transition_analysis().
    """
    from collections import Counter

    RATE_KEYS = [
        "advancing_rate", "consecutive_rate", "derailed_rate", "drifted_rate",
        "returned_rate", "regressing_rate",
        "rt_utilized_rate", "rt_partial_rate", "rt_ignored_rate", "rt_no_data_rate",
    ]
    RATE_LABELS = {
        "advancing_rate": "Advancing",
        "consecutive_rate": "Consecutive / Advancing",
        "derailed_rate": "Derailed",
        "drifted_rate": "Drifted",
        "returned_rate": "Returned",
        "regressing_rate": "Regressing",
        "rt_utilized_rate": "R→T Utilized",
        "rt_partial_rate": "R→T Partial",
        "rt_ignored_rate": "R→T Ignored",
        "rt_no_data_rate": "R→T No Data",
    }
    LABEL_ORDER = [
        "advancing:consecutive", "advancing:skip",
        "lateral:revisit", "lateral:explore",
        "returned:revisit", "returned:discover",
        "regressing:backtrack", "regressing:explore",
        "derailed", "drifted",
        "rt:utilized", "rt:partial", "rt:ignored", "rt:no_data",
    ]

    correct_reports: list = []
    incorrect_reports: list = []

    for sample in exp_samples:
        if not sample.trajectories:
            continue
        steps = _extract_steps_with_llm_intents(sample)
        if not steps:
            continue
        gt_ctx = _load_gt_from_causal_graph(sample)
        if gt_ctx is None:
            gt_ctx = _load_gt_context(sample)
        try:
            report = analyze_transitions(sample.id, bool(sample.correct), steps, gt_ctx)
        except Exception:
            continue
        if not report.transitions:
            continue
        if report.correct:
            correct_reports.append(report)
        else:
            incorrect_reports.append(report)

    # Per-experiment counters (transition labels + R→T labels)
    cor_labels = Counter(t.label for r in correct_reports for t in r.transitions)
    inc_labels = Counter(t.label for r in incorrect_reports for t in r.transitions)
    cor_rt = Counter(f"rt:{t.rt_utilization}" for r in correct_reports for t in r.transitions)
    inc_rt = Counter(f"rt:{t.rt_utilization}" for r in incorrect_reports for t in r.transitions)

    def _build_label_dist(cor_lab, inc_lab, cor_r, inc_r):
        t_cor = sum(cor_lab.values()) or 1
        t_inc = sum(inc_lab.values()) or 1
        t_cor_rt = sum(cor_r.values()) or 1
        t_inc_rt = sum(inc_r.values()) or 1

        merged = Counter()
        merged.update(cor_lab)
        merged.update(inc_lab)
        merged.update(cor_r)
        merged.update(inc_r)

        keys = sorted(
            merged.keys(),
            key=lambda x: LABEL_ORDER.index(x) if x in LABEL_ORDER else 99,
        )
        dist = []
        for k in keys:
            if k.startswith("rt:"):
                c_pct = cor_r.get(k, 0) / t_cor_rt
                i_pct = inc_r.get(k, 0) / t_inc_rt
                a_pct = (cor_r.get(k, 0) + inc_r.get(k, 0)) / (t_cor_rt + t_inc_rt)
            else:
                c_pct = cor_lab.get(k, 0) / t_cor
                i_pct = inc_lab.get(k, 0) / t_inc
                a_pct = (cor_lab.get(k, 0) + inc_lab.get(k, 0)) / (t_cor + t_inc)
            dist.append(TransitionLabelItem(
                label=k, correct_pct=c_pct, incorrect_pct=i_pct, all_pct=a_pct,
            ))
        return dist

    def avg_rates(reports):
        if not reports:
            return {k: 0.0 for k in RATE_KEYS}
        return {k: sum(getattr(r, k) for r in reports) / len(reports) for k in RATE_KEYS}

    return TransitionResponse(
        rate_keys=RATE_KEYS,
        rate_labels=RATE_LABELS,
        experiments=[TransitionExpData(
            exp_id=eid,
            correct_count=len(correct_reports),
            incorrect_count=len(incorrect_reports),
            correct_rates=avg_rates(correct_reports),
            incorrect_rates=avg_rates(incorrect_reports),
            label_distribution=_build_label_dist(cor_labels, inc_labels, cor_rt, inc_rt),
            total_transitions=sum(cor_labels.values()) + sum(inc_labels.values()),
        )],
    )


def _compute_markov(exp_samples: list[EvaluationSample], eid: str) -> MarkovResponse:
    """Compute markov for a single experiment."""
    correct_full, incorrect_full = [], []
    # Also collect (intent, data_type) pairs for dynamic phase mapping
    correct_step_pairs: list[list[tuple[str, str]]] = []
    incorrect_step_pairs: list[list[tuple[str, str]]] = []

    for sample in exp_samples:
        if not sample.trajectories:
            continue
        steps = _extract_steps_with_llm_intents(sample)
        steps = [s for s in steps if s.action_intent != "discovery"]
        if len(steps) < 2:
            continue
        tokens = [s.ngram_token for s in steps if s.ngram_token]
        if not tokens:
            continue
        pairs = [(s.action_intent, s.action_data_type or "") for s in steps]
        if sample.correct:
            correct_full.append(tokens)
            correct_step_pairs.append(pairs)
        else:
            incorrect_full.append(tokens)
            incorrect_step_pairs.append(pairs)

    if not correct_full and not incorrect_full:
        return MarkovResponse(experiments=[])

    full_layer = _compute_markov_layer(correct_full, incorrect_full)
    if not full_layer:
        return MarkovResponse(experiments=[])

    correct_intent = [[t.split(":")[-1] if ":" in t else t for t in seq] for seq in correct_full]
    incorrect_intent = [[t.split(":")[-1] if ":" in t else t for t in seq] for seq in incorrect_full]
    intent_layer = _compute_markov_layer(correct_intent, incorrect_intent)

    # 5-phase aggregated layer (cognitive depth grouping)
    def _pairs_to_phase(pairs: list[tuple[str, str]]) -> list[str]:
        return [intent_to_phase(intent, dt) for intent, dt in pairs]

    correct_phase = [_pairs_to_phase(p) for p in correct_step_pairs]
    incorrect_phase = [_pairs_to_phase(p) for p in incorrect_step_pairs]
    phase_layer = _compute_markov_layer(correct_phase, incorrect_phase)

    return MarkovResponse(experiments=[MarkovExpData(
        exp_id=eid, correct_count=len(correct_full), incorrect_count=len(incorrect_full),
        states=full_layer.states, transitions=full_layer.transitions,
        state_metrics=full_layer.state_metrics,
        correct_entropy=full_layer.correct_entropy, incorrect_entropy=full_layer.incorrect_entropy,
        total_kl=full_layer.total_kl, intent_only=intent_layer, phase_layer=phase_layer,
    )])


def _compute_fingerprint_response(exp_samples: list[EvaluationSample], eid: str) -> FingerprintResponse:
    """Compute fingerprint response for a single experiment."""
    # Try to get round-level R→T utilized rate from transitions cache
    evidence_rt_rate = None
    ck = _cache_key("transitions", [eid])
    if ck in _cache:
        tr_data = _cache[ck]
        if hasattr(tr_data, "experiments") and tr_data.experiments:
            exp0 = tr_data.experiments[0]
            cr = exp0.correct_rates.get("rt_utilized_rate", 0)
            ir = exp0.incorrect_rates.get("rt_utilized_rate", 0)
            nc = exp0.correct_count or 0
            ni = exp0.incorrect_count or 0
            total = nc + ni
            evidence_rt_rate = (cr * nc + ir * ni) / total if total else 0

    raw = _compute_fingerprint(exp_samples, evidence_rt_rate=evidence_rt_rate)
    n = len(exp_samples)
    nc = sum(1 for s in exp_samples if s.correct)
    model = exp_samples[0].model_name if exp_samples else None
    dims = [FingerprintDimension(key=k, label=lab, value=raw.get(k, 0.0), raw_value=raw.get(k, 0.0))
            for k, lab in FINGERPRINT_DIMENSIONS]
    return FingerprintResponse(
        dimension_keys=[k for k, _ in FINGERPRINT_DIMENSIONS],
        dimension_labels={k: v for k, v in FINGERPRINT_DIMENSIONS},
        experiments=[FingerprintExpData(exp_id=eid, model_name=model, total_samples=n,
                                        accuracy=nc / n * 100 if n else 0, dimensions=dims)],
    )


def _compute_modality_progression(
    exp_samples: list[EvaluationSample], eid: str
) -> ModalityProgressionResponse:
    """Compute data-source (logs/traces/metrics) distribution over normalized trajectory progress."""
    n_bins = 20
    bin_counts: list[dict[str, int]] = [{"logs": 0, "traces": 0, "metrics": 0} for _ in range(n_bins)]

    for sample in exp_samples:
        if not sample.trajectories:
            continue
        steps = _extract_steps_with_llm_intents(sample)
        steps = [s for s in steps if s.action_intent != "discovery"]
        if not steps:
            continue
        n_steps = len(steps)
        for i, step in enumerate(steps):
            progress = i / n_steps  # 0.0 ~ 1.0
            bin_idx = min(int(progress * n_bins), n_bins - 1)
            dt = step.action_data_type
            if dt in ("logs", "traces", "metrics"):
                bin_counts[bin_idx][dt] += 1

    bins = []
    for b in range(n_bins):
        total = sum(bin_counts[b].values())
        if total > 0:
            bins.append(ModalityProgressionBin(
                progress=(b + 0.5) / n_bins,
                logs=bin_counts[b]["logs"] / total,
                traces=bin_counts[b]["traces"] / total,
                metrics=bin_counts[b]["metrics"] / total,
            ))
        else:
            bins.append(ModalityProgressionBin(progress=(b + 0.5) / n_bins, logs=0, traces=0, metrics=0))

    return ModalityProgressionResponse(experiments=[ModalityProgressionExpData(exp_id=eid, bins=bins)])


def _compute_intent_heatmap(exp_samples: list[EvaluationSample], eid: str) -> IntentHeatmapResponse:
    """Compute intent heatmap for a single experiment."""
    n = len(exp_samples)
    n_correct = sum(1 for s in exp_samples if s.correct)
    n_incorrect = n - n_correct
    intent_counts: dict[str, dict[str, int]] = {}

    for sample in exp_samples:
        if not sample.trajectories:
            continue
        steps = _extract_steps_with_llm_intents(sample)
        sample_intents = {s.action_intent for s in steps if s.action_intent and s.action_intent != "discovery"}
        for intent in sample_intents:
            if intent not in intent_counts:
                intent_counts[intent] = {"correct": 0, "incorrect": 0, "total": 0}
            intent_counts[intent]["total"] += 1
            if sample.correct:
                intent_counts[intent]["correct"] += 1
            else:
                intent_counts[intent]["incorrect"] += 1

    sorted_intents = sorted(intent_counts.keys(), key=lambda x: -intent_counts[x]["total"])
    cells = []
    for intent in sorted_intents:
        counts = intent_counts[intent]
        cells.append(IntentHeatmapCell(
            intent=intent, exp_id=eid,
            usage_rate=counts["total"] / n if n else 0,
            correct_rate=counts["correct"] / n_correct if n_correct else 0,
            incorrect_rate=counts["incorrect"] / n_incorrect if n_incorrect else 0,
        ))

    return IntentHeatmapResponse(intents=sorted_intents, experiments=[eid], cells=cells)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _load_gt_context(sample: EvaluationSample) -> GTContext:
    """Load ground truth context from sample's correct_answer."""
    answer = sample.correct_answer or ""
    if answer.strip().startswith("{"):
        try:
            data = json.loads(answer)
            graph = CausalGraph.from_dict(data)
            return GTContext.from_causal_graph(graph)
        except (json.JSONDecodeError, Exception):
            pass
    services = {s.strip() for s in answer.split(",") if s.strip()}
    return GTContext(
        path_services=services,
        root_cause_services=services,
        alarm_services=set(),
        service_edges=set(),
    )


def _load_gt_from_causal_graph(sample: EvaluationSample) -> GTContext | None:
    """Load GT context from causal_graph.json via meta.path (includes edges).

    Mirrors viz_trajectory.py's load_causal_graph enhancements:
    - loadgenerator removal (traffic generator, not part of SUT)
    - Leaf node alarm promotion when all original alarms are removed
    """
    meta = sample.meta
    if not meta or "path" not in meta:
        return None
    gt_path = Path(meta["path"]) / "causal_graph.json"
    if not gt_path.exists():
        return None
    try:
        with open(gt_path) as f:
            data = json.load(f)
        graph = CausalGraph.from_dict(data)
        gt = GTContext.from_causal_graph(graph)

        # Remove loadgenerator (traffic generator, not part of SUT)
        _excluded = {"loadgenerator"}
        gt.path_services = {s for s in gt.path_services if s not in _excluded}
        gt.root_cause_services = {s for s in gt.root_cause_services if s not in _excluded}
        gt.alarm_services = {s for s in gt.alarm_services if s not in _excluded}
        gt.service_edges = {(s, t) for s, t in gt.service_edges if s not in _excluded and t not in _excluded}

        # Promote leaf nodes as alarms if all alarms were removed
        if not gt.alarm_services and gt.service_edges:
            sources = {s for s, _ in gt.service_edges}
            targets = {t for _, t in gt.service_edges}
            leaves = (gt.path_services - sources) & targets
            if leaves:
                gt.alarm_services = leaves
            elif len(gt.path_services) > 1:
                gt.alarm_services = gt.path_services - gt.root_cause_services

        return gt
    except Exception:
        return None


def _get_judged_samples(session: Session, exp_ids: list[str] | None = None) -> list[EvaluationSample]:
    """Fetch judged samples, optionally filtered by exp_ids.
    Always applies prod allowlist unless caller explicitly specifies exp_ids."""
    stmt = select(EvaluationSample).where(EvaluationSample.stage == "judged")
    if exp_ids:
        stmt = stmt.where(EvaluationSample.exp_id.in_(exp_ids))
    else:
        from api.deps import get_allowed_exp_ids
        allowed = get_allowed_exp_ids()
        if allowed:
            stmt = stmt.where(EvaluationSample.exp_id.in_(allowed))
    return list(session.exec(stmt).all())


def _compute_ngram_pooled_deltas(charts: list[NgramChartData], top_k: int = 15) -> list[NgramPooledDelta]:
    """Compute Method 2 pooled deltas for n-grams across experiments.

    Only pools the 4 large thinkdepthai experiments defined in _POOLED_EXP_IDS.
    """
    from collections import defaultdict

    by_n: dict[int, list[NgramChartData]] = defaultdict(list)
    for c in charts:
        if c.exp_id in _POOLED_EXP_IDS:
            by_n[c.n].append(c)

    results = []
    for n_val, n_charts in sorted(by_n.items()):
        if len(n_charts) < 2:
            continue

        # Collect all unique ngrams across experiments
        all_ngrams: set[str] = set()
        for c in n_charts:
            for item in c.items:
                all_ngrams.add(item.ngram)

        delta_items = []
        for ngram in all_ngrams:
            numerator = 0.0
            denominator = 0.0
            m_deltas: dict[str, float] = {}
            for c in n_charts:
                item = next((i for i in c.items if i.ngram == ngram), None)
                cr = 0.0
                ir = 0.0
                if item:
                    if c.correct_samples > 0:
                        cr = item.correct_count / c.correct_samples
                    if c.incorrect_samples > 0:
                        ir = item.incorrect_count / c.incorrect_samples
                delta = cr - ir
                weight = c.total_samples
                numerator += delta * weight
                denominator += weight
                m_deltas[c.exp_id] = round(delta, 4)

            pd = numerator / denominator if denominator > 0 else 0.0
            delta_items.append(PooledDeltaItem(label=ngram, pooled_delta=round(pd, 4), model_deltas=m_deltas))

        delta_items.sort(key=lambda x: abs(x.pooled_delta), reverse=True)
        results.append(NgramPooledDelta(n=n_val, items=delta_items[:top_k]))

    return results


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/analysis/ngrams", response_model=NgramResponse)
def get_ngram_analysis(
    exp_id: list[str] | None = Query(default=None),
    n_max: int = Query(default=6, ge=2, le=6),
    top_k: int = Query(default=8, ge=1, le=20),
    db: DBSession = None,
):
    """Get n-gram analysis data for dashboard charts."""
    # Try cache: merge per-experiment cached results
    cached_charts = []
    all_cached = True
    target_eids = exp_id or [k.split("|")[1] for k in _cache if k.startswith("ngrams|")]
    for eid in target_eids:
        ck = _cache_key("ngrams", [eid])
        if ck in _cache:
            cached_charts.extend(_cache[ck].charts)
        else:
            all_cached = False
            break
    if all_cached and target_eids:
        return NgramResponse(charts=cached_charts, pooled_deltas=_compute_ngram_pooled_deltas(cached_charts))

    samples = _get_judged_samples(db, exp_id)
    if not samples:
        return NgramResponse(charts=[])

    # Group by exp_id
    by_exp: dict[str, list[EvaluationSample]] = {}
    for s in samples:
        by_exp.setdefault(s.exp_id, []).append(s)

    charts: list[NgramChartData] = []

    for eid, exp_samples in sorted(by_exp.items()):
        # Extract n-gram results
        ngram_results = []
        for sample in exp_samples:
            if not sample.trajectories:
                continue
            steps = _extract_steps_with_llm_intents(sample)
            if not steps:
                continue
            # Filter out discovery steps (e.g. list_tables_in_directory)
            steps = [s for s in steps if s.action_intent != "discovery"]
            if not steps:
                continue
            result = analyze_single_sample(
                sample_id=sample.id,
                correct=bool(sample.correct),
                steps=steps,
                n_range=(1, n_max),
            )
            ngram_results.append(result)

        if not ngram_results:
            continue

        total_s = len(ngram_results)
        correct_s = sum(1 for r in ngram_results if r.correct)
        incorrect_s = total_s - correct_s
        report = analyze_ngrams(ngram_results, n_range=(1, n_max))

        # Build charts for each n
        for n in range(1, n_max):
            accuracy_data = report.ngram_accuracy.get(n, {})
            if not accuracy_data:
                continue

            # Sort by total count, take top_k
            sorted_ngrams = sorted(accuracy_data.items(), key=lambda x: x[1].total, reverse=True)[:top_k]

            items = []
            for ng, acc in sorted_ngrams:
                ng_str = " -> ".join(ng)
                items.append(
                    NgramBarItem(
                        ngram=ng_str,
                        correct_count=acc.correct,
                        incorrect_count=acc.total - acc.correct,
                    )
                )

            if items:
                charts.append(NgramChartData(
                    exp_id=eid, n=n, items=items,
                    total_samples=total_s, correct_samples=correct_s, incorrect_samples=incorrect_s,
                ))

    return NgramResponse(charts=charts, pooled_deltas=_compute_ngram_pooled_deltas(charts))


@router.get("/analysis/transitions", response_model=TransitionResponse)
def get_transition_analysis(
    exp_id: list[str] | None = Query(default=None),
    db: DBSession = None,
):
    """Get step transition taxonomy analysis for dashboard."""
    cached_exps = []
    all_cached = True
    target_eids = exp_id or [k.split("|")[1] for k in _cache if k.startswith("transitions|")]
    for eid in target_eids:
        ck = _cache_key("transitions", [eid])
        if ck in _cache:
            cached_exps.extend(_cache[ck].experiments)
        else:
            all_cached = False
            break
    if all_cached and cached_exps:
        first_ck = _cache_key("transitions", [target_eids[0]])
        # Compute aggregated micro-average from cached per-experiment distributions
        agg = None
        if len(cached_exps) > 1:
            from collections import Counter

            LABEL_ORDER = [
                "advancing:consecutive", "advancing:skip",
                "lateral:revisit", "lateral:explore",
                "returned:revisit", "returned:discover",
                "regressing:backtrack", "regressing:explore",
                "derailed", "drifted",
                "rt:utilized", "rt:partial", "rt:ignored", "rt:no_data",
            ]
            agg_cor: Counter = Counter()
            agg_inc: Counter = Counter()
            agg_cor_rt: Counter = Counter()
            agg_inc_rt: Counter = Counter()
            total_cor = 0
            total_inc = 0
            for exp in cached_exps:
                total_cor += exp.correct_count
                total_inc += exp.incorrect_count
                for item in exp.label_distribution:
                    if item.label.startswith("rt:"):
                        agg_cor_rt[item.label] += item.correct_pct * exp.correct_count
                        agg_inc_rt[item.label] += item.incorrect_pct * exp.incorrect_count
                    else:
                        agg_cor[item.label] += item.correct_pct * exp.correct_count
                        agg_inc[item.label] += item.incorrect_pct * exp.incorrect_count
            # Normalize
            merged = Counter()
            merged.update(agg_cor)
            merged.update(agg_inc)
            merged.update(agg_cor_rt)
            merged.update(agg_inc_rt)
            keys = sorted(merged.keys(), key=lambda x: LABEL_ORDER.index(x) if x in LABEL_ORDER else 99)
            dist = []
            t_cor = total_cor or 1
            t_inc = total_inc or 1
            t_all = t_cor + t_inc
            for k in keys:
                if k.startswith("rt:"):
                    c_pct = agg_cor_rt.get(k, 0) / t_cor
                    i_pct = agg_inc_rt.get(k, 0) / t_inc
                    a_pct = (agg_cor_rt.get(k, 0) + agg_inc_rt.get(k, 0)) / t_all
                else:
                    c_pct = agg_cor.get(k, 0) / t_cor
                    i_pct = agg_inc.get(k, 0) / t_inc
                    a_pct = (agg_cor.get(k, 0) + agg_inc.get(k, 0)) / t_all
                dist.append(TransitionLabelItem(label=k, correct_pct=c_pct, incorrect_pct=i_pct, all_pct=a_pct))
            agg = TransitionExpData(
                exp_id="__all__", correct_count=total_cor, incorrect_count=total_inc,
                correct_rates={}, incorrect_rates={}, label_distribution=dist,
            )

        # Method 2: per-model Δ weighted by total transitions
        # Only pool the 4 large thinkdepthai experiments to avoid noise from small tests.
        pooled = None
        pooled_exps = [e for e in cached_exps if e.exp_id in _POOLED_EXP_IDS]
        if len(pooled_exps) > 1:
            pooled_items = []
            total_cases = sum(e.correct_count + e.incorrect_count for e in pooled_exps)
            for label in LABEL_ORDER:
                numerator = 0.0
                denominator = 0.0
                m_deltas: dict[str, float] = {}
                for exp in pooled_exps:
                    item = next((i for i in exp.label_distribution if i.label == label), None)
                    if item is None:
                        continue
                    delta = item.correct_pct - item.incorrect_pct
                    weight = exp.total_transitions if exp.total_transitions > 0 else (exp.correct_count + exp.incorrect_count)
                    numerator += delta * weight
                    denominator += weight
                    m_deltas[exp.exp_id] = round(delta, 4)
                pd = numerator / denominator if denominator > 0 else 0.0
                pooled_items.append(PooledDeltaItem(label=label, pooled_delta=round(pd, 4), model_deltas=m_deltas))
            pooled = PooledDeltaChart(total_models=len(pooled_exps), total_cases=total_cases, items=pooled_items)

        return TransitionResponse(
            rate_keys=_cache[first_ck].rate_keys,
            rate_labels=_cache[first_ck].rate_labels,
            experiments=cached_exps,
            aggregated=agg,
            pooled_delta=pooled,
        )
    """

    Returns transition label distribution and rates per experiment,
    split by correct/incorrect.
    """
    from collections import Counter

    RATE_KEYS = [
        "advancing_rate",
        "consecutive_rate",
        "derailed_rate",
        "drifted_rate",
        "returned_rate",
        "regressing_rate",
        "rt_utilized_rate",
        "rt_partial_rate",
        "rt_ignored_rate",
        "rt_no_data_rate",
    ]
    RATE_LABELS = {
        "advancing_rate": "Advancing",
        "consecutive_rate": "Consecutive / Advancing",
        "derailed_rate": "Derailed",
        "drifted_rate": "Drifted",
        "returned_rate": "Returned",
        "regressing_rate": "Regressing",
        "rt_utilized_rate": "R→T Utilized",
        "rt_partial_rate": "R→T Partial",
        "rt_ignored_rate": "R→T Ignored",
        "rt_no_data_rate": "R→T No Data",
    }

    LABEL_ORDER = [
        "advancing:consecutive", "advancing:skip",
        "lateral:revisit", "lateral:explore",
        "returned:revisit", "returned:discover",
        "regressing:backtrack", "regressing:explore",
        "derailed", "drifted",
        "rt:utilized", "rt:partial", "rt:ignored", "rt:no_data",
    ]

    samples = _get_judged_samples(db, exp_id)
    if not samples:
        return TransitionResponse(rate_keys=RATE_KEYS, rate_labels=RATE_LABELS, experiments=[])

    by_exp: dict[str, list[EvaluationSample]] = {}
    for s in samples:
        by_exp.setdefault(s.exp_id, []).append(s)

    experiments: list[TransitionExpData] = []

    # Accumulators for aggregated micro-average
    agg_cor_labels: Counter = Counter()
    agg_inc_labels: Counter = Counter()
    agg_cor_rt: Counter = Counter()
    agg_inc_rt: Counter = Counter()
    agg_correct_count = 0
    agg_incorrect_count = 0

    def _build_label_dist(cor_labels, inc_labels, cor_rt, inc_rt):
        """Build label distribution from raw counters."""
        t_cor = sum(cor_labels.values()) or 1
        t_inc = sum(inc_labels.values()) or 1
        t_cor_rt = sum(cor_rt.values()) or 1
        t_inc_rt = sum(inc_rt.values()) or 1

        merged = Counter()
        merged.update(cor_labels)
        merged.update(inc_labels)
        merged.update(cor_rt)
        merged.update(inc_rt)

        keys = sorted(
            merged.keys(),
            key=lambda x: LABEL_ORDER.index(x) if x in LABEL_ORDER else 99,
        )
        dist = []
        for k in keys:
            if k.startswith("rt:"):
                c_pct = cor_rt.get(k, 0) / t_cor_rt
                i_pct = inc_rt.get(k, 0) / t_inc_rt
                a_pct = (cor_rt.get(k, 0) + inc_rt.get(k, 0)) / (t_cor_rt + t_inc_rt)
            else:
                c_pct = cor_labels.get(k, 0) / t_cor
                i_pct = inc_labels.get(k, 0) / t_inc
                a_pct = (cor_labels.get(k, 0) + inc_labels.get(k, 0)) / (t_cor + t_inc)
            dist.append(TransitionLabelItem(
                label=k, correct_pct=c_pct, incorrect_pct=i_pct, all_pct=a_pct,
            ))
        return dist

    for eid, exp_samples in sorted(by_exp.items()):
        correct_reports = []
        incorrect_reports = []

        for sample in exp_samples:
            if not sample.trajectories:
                continue
            steps = _extract_steps_with_llm_intents(sample)
            if not steps:
                continue
            gt = _load_gt_from_causal_graph(sample)
            if gt is None:
                gt = _load_gt_context(sample)
            report = analyze_transitions(
                sample_id=sample.id,
                correct=bool(sample.correct),
                steps=steps,
                gt=gt,
            )
            if not report.transitions:
                continue
            if report.correct:
                correct_reports.append(report)
            else:
                incorrect_reports.append(report)

        def avg_rates(reports):
            if not reports:
                return {k: 0.0 for k in RATE_KEYS}
            return {k: sum(getattr(r, k) for r in reports) / len(reports) for k in RATE_KEYS}

        # Per-experiment counters
        cor_labels = Counter(t.label for r in correct_reports for t in r.transitions)
        inc_labels = Counter(t.label for r in incorrect_reports for t in r.transitions)
        cor_rt = Counter(f"rt:{t.rt_utilization}" for r in correct_reports for t in r.transitions)
        inc_rt = Counter(f"rt:{t.rt_utilization}" for r in incorrect_reports for t in r.transitions)

        # Accumulate for aggregated view
        agg_cor_labels.update(cor_labels)
        agg_inc_labels.update(inc_labels)
        agg_cor_rt.update(cor_rt)
        agg_inc_rt.update(inc_rt)
        agg_correct_count += len(correct_reports)
        agg_incorrect_count += len(incorrect_reports)

        experiments.append(
            TransitionExpData(
                exp_id=eid,
                correct_count=len(correct_reports),
                incorrect_count=len(incorrect_reports),
                correct_rates=avg_rates(correct_reports),
                incorrect_rates=avg_rates(incorrect_reports),
                label_distribution=_build_label_dist(cor_labels, inc_labels, cor_rt, inc_rt),
            )
        )

    # ── Aggregated micro-average across all experiments ──
    aggregated = None
    if experiments:
        aggregated = TransitionExpData(
            exp_id="__all__",
            correct_count=agg_correct_count,
            incorrect_count=agg_incorrect_count,
            correct_rates={},
            incorrect_rates={},
            label_distribution=_build_label_dist(agg_cor_labels, agg_inc_labels, agg_cor_rt, agg_inc_rt),
        )

    return TransitionResponse(rate_keys=RATE_KEYS, rate_labels=RATE_LABELS, experiments=experiments, aggregated=aggregated)


# ── Markov Chain Analysis ─────────────────────────────────────────────────


def _build_markov_matrix(sequences: list[list[str]], states: list[str]) -> list[list[float]]:
    """Build transition probability matrix from sequences.

    Returns NxN matrix where matrix[i][j] = P(next=j | cur=i).
    """
    from collections import Counter

    n = len(states)
    state_idx = {s: i for i, s in enumerate(states)}
    counts = [[0] * n for _ in range(n)]

    for seq in sequences:
        for k in range(len(seq) - 1):
            i = state_idx.get(seq[k])
            j = state_idx.get(seq[k + 1])
            if i is not None and j is not None:
                counts[i][j] += 1

    # Normalize rows
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        row_sum = sum(counts[i])
        if row_sum > 0:
            for j in range(n):
                matrix[i][j] = counts[i][j] / row_sum

    return matrix


def _stationary_distribution(matrix: list[list[float]], states: list[str]) -> list[float]:
    """Compute stationary distribution via power iteration."""
    import numpy as np

    n = len(states)
    if n == 0:
        return []

    P = np.array(matrix)

    # Handle zero rows (absorbing states) by making them self-loops
    for i in range(n):
        if P[i].sum() == 0:
            P[i][i] = 1.0

    # Power iteration
    pi = np.ones(n) / n
    for _ in range(200):
        pi_next = pi @ P
        if np.allclose(pi, pi_next, atol=1e-10):
            break
        pi = pi_next

    # Normalize
    total = pi.sum()
    if total > 0:
        pi = pi / total

    return pi.tolist()


def _conditional_entropy(matrix: list[list[float]], stationary: list[float]) -> float:
    """Compute H(next | current) = -sum_i pi_i * sum_j P_ij * log(P_ij)."""
    import math

    h = 0.0
    for i, pi_i in enumerate(stationary):
        if pi_i <= 0:
            continue
        row_h = 0.0
        for j in range(len(matrix[i])):
            p = matrix[i][j]
            if p > 0:
                row_h -= p * math.log2(p)
        h += pi_i * row_h
    return h


def _row_kl_divergence(row_p: list[float], row_q: list[float]) -> float:
    """Compute KL(P || Q) for a single row. Uses smoothing to avoid log(0)."""
    import math

    eps = 1e-10
    kl = 0.0
    for p, q in zip(row_p, row_q):
        p_s = max(p, eps)
        q_s = max(q, eps)
        if p > eps:
            kl += p_s * math.log2(p_s / q_s)
    return kl


def _compute_markov_layer(
    correct_seqs: list[list[str]],
    incorrect_seqs: list[list[str]],
) -> MarkovLayerData | None:
    """Compute Markov chain metrics for a set of token sequences."""
    all_states: set[str] = set()
    for seq in correct_seqs:
        all_states.update(seq)
    for seq in incorrect_seqs:
        all_states.update(seq)

    if not all_states:
        return None

    states = sorted(all_states)
    cor_matrix = _build_markov_matrix(correct_seqs, states)
    inc_matrix = _build_markov_matrix(incorrect_seqs, states)
    cor_stationary = _stationary_distribution(cor_matrix, states)
    inc_stationary = _stationary_distribution(inc_matrix, states)
    cor_entropy = _conditional_entropy(cor_matrix, cor_stationary)
    inc_entropy = _conditional_entropy(inc_matrix, inc_stationary)

    transitions = []
    state_metrics_list = []
    total_kl = 0.0
    kl_weight_sum = 0.0

    for i, state in enumerate(states):
        kl = _row_kl_divergence(cor_matrix[i], inc_matrix[i])
        weight = cor_stationary[i] + inc_stationary[i]
        total_kl += kl * weight
        kl_weight_sum += weight

        state_metrics_list.append(MarkovStateMetrics(
            state=state,
            correct_stationary=cor_stationary[i] if i < len(cor_stationary) else 0.0,
            incorrect_stationary=inc_stationary[i] if i < len(inc_stationary) else 0.0,
            kl_divergence=kl,
        ))

        for j, to_state in enumerate(states):
            transitions.append(MarkovTransitionCell(
                from_state=state,
                to_state=to_state,
                correct_prob=cor_matrix[i][j],
                incorrect_prob=inc_matrix[i][j],
            ))

    avg_kl = total_kl / kl_weight_sum if kl_weight_sum > 0 else 0.0

    return MarkovLayerData(
        states=states,
        transitions=transitions,
        state_metrics=state_metrics_list,
        correct_entropy=cor_entropy,
        incorrect_entropy=inc_entropy,
        total_kl=avg_kl,
    )


@router.get("/analysis/markov", response_model=MarkovResponse)
def get_markov_analysis(
    exp_id: list[str] | None = Query(default=None),
    db: DBSession = None,
):
    """Get Markov chain analysis of modality:intent sequences."""
    cached_exps = []
    all_cached = True
    target_eids = exp_id or [k.split("|")[1] for k in _cache if k.startswith("markov|")]
    for eid in target_eids:
        ck = _cache_key("markov", [eid])
        if ck in _cache:
            cached_exps.extend(_cache[ck].experiments)
        else:
            all_cached = False
            break
    if all_cached and target_eids:
        return MarkovResponse(experiments=cached_exps)

    samples = _get_judged_samples(db, exp_id)
    if not samples:
        return MarkovResponse(experiments=[])

    by_exp: dict[str, list[EvaluationSample]] = {}
    for s in samples:
        by_exp.setdefault(s.exp_id, []).append(s)

    experiments: list[MarkovExpData] = []

    for eid, exp_samples in sorted(by_exp.items()):
        # Collect both modality:intent and intent-only sequences
        correct_full: list[list[str]] = []
        incorrect_full: list[list[str]] = []
        correct_intent: list[list[str]] = []
        incorrect_intent: list[list[str]] = []
        correct_pairs: list[list[tuple[str, str]]] = []
        incorrect_pairs: list[list[tuple[str, str]]] = []

        for sample in exp_samples:
            if not sample.trajectories:
                continue
            steps = _extract_steps_with_llm_intents(sample)
            if not steps:
                continue
            non_disc = [s for s in steps if s.action_intent != "discovery"]
            full_tokens = [s.ngram_token for s in non_disc]
            intent_tokens = [s.action_intent for s in non_disc]
            pairs = [(s.action_intent, s.action_data_type or "") for s in non_disc]
            if len(full_tokens) < 2:
                continue

            if sample.correct:
                correct_full.append(full_tokens)
                correct_intent.append(intent_tokens)
                correct_pairs.append(pairs)
            else:
                incorrect_full.append(full_tokens)
                incorrect_intent.append(intent_tokens)
                incorrect_pairs.append(pairs)

        if not correct_full and not incorrect_full:
            continue

        # Compute modality:intent layer
        full_layer = _compute_markov_layer(correct_full, incorrect_full)
        if not full_layer:
            continue

        # Compute intent-only layer
        intent_layer = _compute_markov_layer(correct_intent, incorrect_intent)

        # Compute 5-phase layer (with dynamic mapping)
        def _pairs_to_phase(pairs: list[tuple[str, str]]) -> list[str]:
            return [intent_to_phase(intent, dt) for intent, dt in pairs]
        correct_phase = [_pairs_to_phase(p) for p in correct_pairs]
        incorrect_phase = [_pairs_to_phase(p) for p in incorrect_pairs]
        phase_layer = _compute_markov_layer(correct_phase, incorrect_phase)

        experiments.append(MarkovExpData(
            exp_id=eid,
            correct_count=len(correct_full),
            incorrect_count=len(incorrect_full),
            states=full_layer.states,
            transitions=full_layer.transitions,
            state_metrics=full_layer.state_metrics,
            correct_entropy=full_layer.correct_entropy,
            incorrect_entropy=full_layer.incorrect_entropy,
            total_kl=full_layer.total_kl,
            intent_only=intent_layer,
            phase_layer=phase_layer,
        ))

    return MarkovResponse(experiments=experiments)


# ── Fingerprint API ──────────────────────────────────────────────────────────

import re as _re

FINGERPRINT_DIMENSIONS = [
    ("cost", "Cost Saving"),
    ("multimodal", "Multi-modal Acquisition"),
    ("evidence", "Evidence Utilization"),
    ("depth", "Investigation Depth"),
    ("focus", "Investigation Focus"),
    ("phase_coverage", "Phase Coverage"),
    ("accuracy", "Accuracy"),
    ("baseline", "Baseline Comparison"),
]

# Intent groups for fingerprint dimensions (from intention_category.md, cognitive depth grouping)
_FP_BASELINE_INTENTS = {"baseline_collect", "baseline_contrast"}

# 5 diagnostic phases for phase_coverage
_FP_PHASE_MAP = {
    "triage": {"latency_ranking", "throughput_compare", "error_rate_scan", "error_log_overview", "metric_scan"},
    "trace_investigate": {"service_trace_scan", "trace_follow", "call_tree_build"},
    "log_investigate": {"service_error_log", "service_log_browse", "keyword_search", "error_timeline"},
    "metric_diagnose": {"container_resource", "jvm_state", "network_layer", "k8s_state", "db_state"},
    "baseline": {"baseline_collect", "baseline_contrast"},
}


def _compute_fingerprint(
    samples: list[EvaluationSample],
    evidence_rt_rate: float | None = None,
) -> dict[str, float]:
    """Compute behavioral fingerprint with 8 dimensions.

    Dimensions:
      - cost:           1 / avg_cost_usd (raw, normalized across experiments later)
      - multimodal:     avg data source types per sample / 3
      - evidence:       R→T utilized rate (round-level, sample-level mean) from transitions
      - depth:          avg non-discovery tool calls per sample (raw, normalized later)
      - focus:          avg (GT-path services / all services) per sample
      - phase_coverage: avg (phases covered / 5) per sample
      - accuracy:       AC@1
      - baseline:       % samples using baseline_collect or baseline_contrast
    """
    if not samples:
        return {k: 0.0 for k, _ in FINGERPRINT_DIMENSIONS}

    n = len(samples)
    n_correct = sum(1 for s in samples if s.correct)

    baseline_count = 0
    total_cost = 0.0
    cost_count = 0
    total_tool_calls = 0
    sample_with_traj = 0
    multimodal_scores: list[float] = []
    phase_coverage_scores: list[float] = []
    focus_scores: list[float] = []

    for sample in samples:
        steps = _extract_steps_with_llm_intents(sample)
        non_disc = [s for s in steps if s.action_intent not in ("discovery", "think", "schema_discovery")]
        if not non_disc:
            continue

        sample_with_traj += 1
        total_tool_calls += len(non_disc)

        # Intent set
        sample_intents = {s.action_intent for s in non_disc if s.action_intent}
        if sample_intents & _FP_BASELINE_INTENTS:
            baseline_count += 1

        # Phase coverage: how many of 5 diagnostic phases are covered
        phases_covered = sum(1 for intents in _FP_PHASE_MAP.values() if sample_intents & intents)
        phase_coverage_scores.append(phases_covered / 5.0)

        # Multimodal: how many distinct data source types used
        data_types = {s.action_data_type for s in non_disc if s.action_data_type in ("logs", "traces", "metrics")}
        multimodal_scores.append(len(data_types) / 3.0)

        # Focus: GT-path services / all services investigated
        gt = _load_gt_from_causal_graph(sample)
        if gt is None:
            gt = _load_gt_context(sample)
        all_svcs: set[str] = set()
        gt_svcs: set[str] = set()
        for step in non_disc:
            for svc in step.action_services:
                normed = svc.lower().replace("ts-", "").replace("-service", "").replace("_", "-").strip()
                all_svcs.add(normed)
                if gt.is_on_path(svc):
                    gt_svcs.add(normed)
        if all_svcs:
            focus_scores.append(len(gt_svcs) / len(all_svcs) if gt_svcs else 0.0)

        # Cost
        meta = sample.meta if isinstance(sample.meta, dict) else {}
        cm = meta.get("cost_metrics", {})
        cost_usd = cm.get("cost_usd", {})
        if isinstance(cost_usd, dict) and cost_usd.get("total"):
            total_cost += cost_usd["total"]
            cost_count += 1

    avg_cost = total_cost / cost_count if cost_count else 0.0
    avg_tool_calls = total_tool_calls / sample_with_traj if sample_with_traj else 0.0

    return {
        "cost": 1.0 / avg_cost if avg_cost > 0 else 0.0,
        "multimodal": sum(multimodal_scores) / n if n else 0,
        "evidence": evidence_rt_rate if evidence_rt_rate is not None else 0.0,
        "depth": avg_tool_calls,  # raw; normalized across experiments later
        "focus": sum(focus_scores) / len(focus_scores) if focus_scores else 0.0,
        "phase_coverage": sum(phase_coverage_scores) / len(phase_coverage_scores) if phase_coverage_scores else 0.0,
        "accuracy": n_correct / n if n else 0,
        "baseline": baseline_count / n if n else 0,
    }


def _normalize_fingerprint_dims(experiments: list) -> None:
    """Normalize cost and depth dimensions to 0-1 across experiments using raw_value."""
    for dim_key in ("cost", "depth"):
        max_raw = max(
            (d.raw_value for e in experiments for d in e.dimensions if d.key == dim_key),
            default=1.0,
        ) or 1.0
        for e in experiments:
            for d in e.dimensions:
                if d.key == dim_key:
                    d.value = d.raw_value / max_raw


@router.get("/analysis/fingerprint", response_model=FingerprintResponse)
def get_fingerprint_analysis(
    exp_id: list[str] | None = Query(default=None),
    db: DBSession = None,
):
    """Compute behavioral fingerprint for multi-model radar chart comparison."""
    if exp_id:
        cached_exps = []
        all_cached = True
        for eid in exp_id:
            ck = _cache_key("fingerprint", [eid])
            if ck in _cache:
                cached_exps.extend(_cache[ck].experiments)
            else:
                all_cached = False
                break
        if all_cached:
            # Re-normalize cost and depth across the selected experiments
            _normalize_fingerprint_dims(cached_exps)
            return FingerprintResponse(
                dimension_keys=[k for k, _ in FINGERPRINT_DIMENSIONS],
                dimension_labels={k: v for k, v in FINGERPRINT_DIMENSIONS},
                experiments=cached_exps,
            )

    samples = _get_judged_samples(db, exp_id)
    if not samples:
        return FingerprintResponse(
            dimension_keys=[k for k, _ in FINGERPRINT_DIMENSIONS],
            dimension_labels={k: v for k, v in FINGERPRINT_DIMENSIONS},
            experiments=[],
        )

    by_exp: dict[str, list[EvaluationSample]] = {}
    for s in samples:
        by_exp.setdefault(s.exp_id, []).append(s)

    experiments = []
    for eid, exp_samples in sorted(by_exp.items()):
        resp = _compute_fingerprint_response(exp_samples, eid)
        experiments.extend(resp.experiments)

    # Normalize cost and depth across all experiments
    _normalize_fingerprint_dims(experiments)

    # Cache individual experiment results after normalization
    for e in experiments:
        single_resp = FingerprintResponse(
            dimension_keys=[k for k, _ in FINGERPRINT_DIMENSIONS],
            dimension_labels={k: v for k, v in FINGERPRINT_DIMENSIONS},
            experiments=[e],
        )
        _cache[_cache_key("fingerprint", [e.exp_id])] = single_resp

    return FingerprintResponse(
        dimension_keys=[k for k, _ in FINGERPRINT_DIMENSIONS],
        dimension_labels={k: v for k, v in FINGERPRINT_DIMENSIONS},
        experiments=experiments,
    )


# ── Intent Heatmap API ────────────────────────────────────────────────────────


@router.get("/analysis/intent-heatmap", response_model=IntentHeatmapResponse)
def get_intent_heatmap(
    exp_id: list[str] | None = Query(default=None),
    db: DBSession = None,
):
    """Compute intent usage heatmap: intent × experiment, split by correct/incorrect."""
    if exp_id:
        all_cached = True
        all_intents = set()
        all_cells = []
        for eid in exp_id:
            ck = _cache_key("intent-heatmap", [eid])
            if ck in _cache:
                all_intents.update(_cache[ck].intents)
                all_cells.extend(_cache[ck].cells)
            else:
                all_cached = False
                break
        if all_cached:
            sorted_intents = sorted(all_intents, key=lambda x: -sum(c.usage_rate for c in all_cells if c.intent == x))
            return IntentHeatmapResponse(intents=sorted_intents, experiments=sorted(exp_id), cells=all_cells)

    samples = _get_judged_samples(db, exp_id)
    if not samples:
        return IntentHeatmapResponse(intents=[], experiments=[], cells=[])

    by_exp: dict[str, list[EvaluationSample]] = {}
    for s in samples:
        by_exp.setdefault(s.exp_id, []).append(s)

    all_intents: set[str] = set()
    # {exp_id: {intent: {correct: n_samples, incorrect: n_samples, total: n_samples}}}
    usage: dict[str, dict[str, dict[str, int]]] = {}

    for eid, exp_samples in sorted(by_exp.items()):
        usage[eid] = {}
        n_correct = sum(1 for s in exp_samples if s.correct)
        n_incorrect = len(exp_samples) - n_correct

        for sample in exp_samples:
            if not sample.trajectories:
                continue
            steps = _extract_steps_with_llm_intents(sample)
            # Get unique intents used in this sample
            sample_intents = {s.action_intent for s in steps if s.action_intent and s.action_intent != "discovery"}
            for intent in sample_intents:
                all_intents.add(intent)
                if intent not in usage[eid]:
                    usage[eid][intent] = {"correct": 0, "incorrect": 0, "total": 0}
                usage[eid][intent]["total"] += 1
                if sample.correct:
                    usage[eid][intent]["correct"] += 1
                else:
                    usage[eid][intent]["incorrect"] += 1

    # Sort intents by total usage across all experiments
    intent_totals = {}
    for eid_data in usage.values():
        for intent, counts in eid_data.items():
            intent_totals[intent] = intent_totals.get(intent, 0) + counts["total"]
    sorted_intents = sorted(all_intents, key=lambda x: -intent_totals.get(x, 0))
    sorted_exps = sorted(by_exp.keys())

    cells = []
    for intent in sorted_intents:
        for eid in sorted_exps:
            exp_samples = by_exp[eid]
            n = len(exp_samples)
            n_correct = sum(1 for s in exp_samples if s.correct)
            n_incorrect = n - n_correct

            counts = usage.get(eid, {}).get(intent, {"correct": 0, "incorrect": 0, "total": 0})
            cells.append(IntentHeatmapCell(
                intent=intent,
                exp_id=eid,
                usage_rate=counts["total"] / n if n else 0,
                correct_rate=counts["correct"] / n_correct if n_correct else 0,
                incorrect_rate=counts["incorrect"] / n_incorrect if n_incorrect else 0,
            ))

    return IntentHeatmapResponse(
        intents=sorted_intents,
        experiments=sorted_exps,
        cells=cells,
    )


# ── Modality Progression API ────────────────────────────────────────────────


@router.get("/analysis/modality-progression", response_model=ModalityProgressionResponse)
def get_modality_progression(
    exp_id: list[str] | None = Query(default=None),
    db: DBSession = None,
):
    """Get data-source (logs/traces/metrics) distribution over normalized trajectory progress."""
    cached_exps = []
    all_cached = True
    target_eids = exp_id or [k.split("|")[1] for k in _cache if k.startswith("modality-progression|")]
    for eid in target_eids:
        ck = _cache_key("modality-progression", [eid])
        if ck in _cache:
            for exp in _cache[ck].experiments:
                cached_exps.append(exp)
        else:
            all_cached = False
            break
    if all_cached and cached_exps:
        return ModalityProgressionResponse(experiments=cached_exps)

    samples = _get_judged_samples(db, exp_id)
    if not samples:
        return ModalityProgressionResponse(experiments=[])
    by_exp: dict[str, list[EvaluationSample]] = {}
    for s in samples:
        by_exp.setdefault(s.exp_id, []).append(s)
    all_exp_data = []
    for eid, exp_samples in sorted(by_exp.items()):
        resp = _compute_modality_progression(exp_samples, eid)
        all_exp_data.extend(resp.experiments)
    return ModalityProgressionResponse(experiments=all_exp_data)
