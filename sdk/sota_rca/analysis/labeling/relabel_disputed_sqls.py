#!/usr/bin/env python
"""Re-label disputed SQLs using a second LLM (e.g., Opus 4.7) for cross-validation.

Strategy:
1. Scan all claude_opus_4_6 labeled samples for structural violations:
   - call_tree_build without JOIN parent_span_id=span_id
   - baseline_contrast without both normal+abnormal tables
   - trace_follow without WHERE trace_id filter
   - baseline_collect on abnormal-only tables
   - trace/metric/log intent mismatching the actual table
2. Collect samples that contain ≥1 disputed SQL
3. Re-run classify_trajectory (full sample for context) using the second model
4. Store results under meta.llm_intents.<model_key>

Usage:
    OPENAI_API_KEY=xxx uv run python scripts/relabel_disputed_sqls.py \
        --db postgresql://postgres:postgres@localhost:5433/SOTA-Agents \
        --base-model-key claude_opus_4_6 \
        --second-model claude-opus-4-7 \
        --concurrency 10
"""

import argparse
import json
import logging
import os
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI
from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, create_engine, select

sys.path.insert(0, str(__file__).rsplit("/scripts/", 1)[0])

from sota_rca.runner._fallback_db import EvaluationSample
from sota_rca.analysis.llm_intent_classifier import classify_trajectory, extract_sql_rounds
from sota_rca.analysis.trajectory_normalizer import normalize_by_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EXPS = [
    "thinkdepthai-claude-sonnet-4.6",
    "thinkdepthai-qwen3.5-plus",
    "aiq-qwen3.5-plus",
    "claudecode-qwen3.5-plus",
    "taskweaver-qwen3.5-plus",
]

# Intent taxonomy by strict modality.
# We split into "strict" groups (modality is REQUIRED by the intent definition) and
# "lenient" groups (intent can legitimately apply across modalities per LLM prompt).
#
# STRICT_LOG_INTENTS: these intents are definitionally only meaningful on logs tables.
# STRICT_METRIC_INTENTS: these intents explicitly name metric domains.
# STRICT_TRACE_INTENTS: these intents talk about traces-specific concepts
#                       (latency/throughput/error rate across services; call tree).
# AMBIGUOUS: these can apply across modalities and must NOT be flagged as violation
#            even when the SQL queries a non-native table.
STRICT_LOG_INTENTS = {"service_log_browse", "service_error_log", "error_log_overview"}
STRICT_METRIC_INTENTS = {"container_resource", "jvm_state", "network_layer", "k8s_state", "db_state", "metric_scan"}
STRICT_TRACE_INTENTS = {"latency_ranking", "throughput_compare", "error_rate_scan", "service_trace_scan", "call_tree_build"}
AMBIGUOUS_MODALITY = {
    "keyword_search",   # LIKE on message (logs) OR span_name (traces)
    "error_timeline",   # MIN/MAX(time) GROUP BY on EITHER logs OR traces
    "trace_follow",     # WHERE trace_id = X can apply to logs AND traces (both have trace_id)
    "baseline_collect", # can be on normal_logs / normal_metrics / normal_traces
    "baseline_contrast",# union of normal_X + abnormal_X — X is any modality
}


def model_key(model_name: str) -> str:
    return model_name.replace("/", "_").replace(".", "_").replace("-", "_")


def agent_of(exp_id: str) -> str:
    return exp_id.split("-", 1)[0] if exp_id else ""


def is_disputed(sql: str, llm_intent: str) -> tuple[str, str] | None:
    """Return (category, reason) if SQL + intent is a structural violation, else None.

    Only flags HARD violations where the intent is impossible given the SQL shape.
    Ambiguous modality intents (keyword_search, error_timeline, trace_follow,
    baseline_*) are NOT flagged just for modality; they still get flagged for
    structural prerequisites (e.g., baseline_contrast MUST have both tables).
    """
    s = re.sub(r"\s+", " ", sql.upper())
    has_ab = "ABNORMAL_" in s
    has_nm = bool(re.search(r"(?<!AB)NORMAL_", s))
    has_tree_join = bool(re.search(r"PARENT_SPAN_ID\s*=\s*\w*\.?SPAN_ID|\w*\.?SPAN_ID\s*=\s*\w*\.?PARENT_SPAN_ID", s))
    # WHERE clause, excluding JOIN ON clauses (which can appear before WHERE)
    wm = re.search(r"\bWHERE\b(.*?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|\bUNION\b|\bHAVING\b|$)", s, re.DOTALL)
    where = wm.group(1) if wm else ""
    has_trace_id = bool(re.search(r"TRACE_ID\s*(=|IN)", where))
    has_service_filter = bool(re.search(r"SERVICE_NAME\s*(=|IN|LIKE)", where))
    has_level_filter = bool(re.search(r"\bLEVEL\s*(=|IN)", where))
    has_logs = bool(re.search(r"\b(?:ABNORMAL_|NORMAL_)?LOGS\b", s))
    has_metrics = bool(re.search(r"\b(?:ABNORMAL_|NORMAL_)?METRICS\b", s))
    has_traces = bool(re.search(r"\b(?:ABNORMAL_|NORMAL_)?TRACES\b", s))

    # ── Structural prerequisites (absolute requirements from intent definitions) ──
    if llm_intent == "call_tree_build" and not has_tree_join:
        return ("call_tree_no_join", "call_tree_build REQUIRES JOIN parent_span_id=span_id, absent here")
    if llm_intent == "baseline_contrast" and not (has_ab and has_nm):
        return ("baseline_contrast_single_table", "baseline_contrast REQUIRES both normal_* AND abnormal_* tables")
    if llm_intent == "baseline_collect" and not has_nm:
        return ("baseline_collect_no_normal", "baseline_collect REQUIRES normal_* table(s)")
    if llm_intent == "trace_follow" and not has_trace_id:
        return ("trace_follow_no_trace_id", "trace_follow REQUIRES WHERE trace_id = / IN (...)")

    # ── Strict modality violations (impossible given SQL table) ──
    # STRICT_LOG_INTENTS: service_log_browse / service_error_log / error_log_overview
    # These definitionally query logs — if SQL is on metrics/traces only, it's wrong.
    if llm_intent in STRICT_LOG_INTENTS and not has_logs:
        return ("log_intent_not_on_logs", f"{llm_intent} REQUIRES logs table, SQL queries metrics/traces only")

    # STRICT_METRIC_INTENTS: container_resource / jvm_state / ... / metric_scan
    # These definitionally query metrics — if SQL is on logs/traces only, wrong.
    if llm_intent in STRICT_METRIC_INTENTS and not has_metrics:
        return ("metric_intent_not_on_metrics", f"{llm_intent} REQUIRES metrics table, SQL queries logs/traces only")

    # STRICT_TRACE_INTENTS: latency/throughput/error_rate_scan/service_trace_scan/call_tree_build
    # These talk about trace-specific concepts. If SQL is on logs only, wrong.
    # (NOT flagging if SQL is on traces OR multi-modal.)
    if llm_intent in STRICT_TRACE_INTENTS and not has_traces:
        return ("trace_intent_not_on_traces", f"{llm_intent} REQUIRES traces table, SQL queries logs/metrics only")

    # service_error_log REQUIRES both service_name AND level filter (per rule taxonomy)
    if llm_intent == "service_error_log" and not (has_service_filter and has_level_filter):
        return ("service_error_log_missing_filter", "service_error_log REQUIRES service_name AND level filter")

    # service_log_browse REQUIRES service_name filter (otherwise it's error_log_overview)
    if llm_intent == "service_log_browse" and not has_service_filter:
        return ("service_log_browse_missing_svc_filter", "service_log_browse REQUIRES WHERE service_name = X")

    return None


def find_disputed_samples(engine, base_key: str) -> list[tuple[str, int]]:
    """Return [(exp_id, dataset_index), ...] for samples with ≥1 disputed SQL."""
    disputed_samples: list[tuple[str, int]] = []
    dispute_categories: Counter = Counter()
    with engine.connect() as conn:
        for exp_id in EXPS:
            rows = conn.execute(
                text(
                    f"SELECT dataset_index, trajectories, meta FROM evaluation_data "
                    f"WHERE exp_id='{exp_id}' AND stage='judged' "
                    f"AND (meta::jsonb->'llm_intents') ? '{base_key}'"
                )
            ).fetchall()
            for idx, traj_raw, meta_raw in rows:
                tr = json.loads(traj_raw) if isinstance(traj_raw, str) else traj_raw
                meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
                ents = (meta.get("llm_intents") or {}).get(base_key, [])
                tr_norm = normalize_by_agent(agent_of(exp_id), tr)
                sql_by_pos = {
                    (r.round_index, i + 1): sql
                    for r in extract_sql_rounds(tr_norm)
                    for i, sql in enumerate(r.queries)
                }
                has_dispute = False
                for e in ents:
                    sql = sql_by_pos.get((e.get("round"), e.get("sql_index")), "")
                    if not sql:
                        continue
                    v = is_disputed(sql, e.get("intent", ""))
                    if v is not None:
                        dispute_categories[v[0]] += 1
                        has_dispute = True
                if has_dispute:
                    disputed_samples.append((exp_id, idx))
    logger.info("Found %d disputed samples; violation breakdown: %s", len(disputed_samples), dispute_categories.most_common())
    return disputed_samples


def relabel(engine, samples: list[tuple[str, int]], second_model: str, client: OpenAI, concurrency: int, force: bool) -> None:
    mkey = model_key(second_model)
    stats = {"total": len(samples), "done": 0, "skipped": 0, "failed": 0}
    lock = threading.Lock()
    tls = threading.local()

    def get_session() -> Session:
        s = getattr(tls, "session", None)
        if s is None:
            s = Session(engine)
            tls.session = s
        return s

    def process(exp_id: str, idx: int) -> None:
        session = get_session()
        try:
            stmt = select(EvaluationSample).where(
                EvaluationSample.exp_id == exp_id,
                EvaluationSample.dataset_index == idx,
                EvaluationSample.stage == "judged",
            )
            sample = session.exec(stmt).first()
            if not sample:
                return
            meta = sample.meta or {}
            llm_intents = meta.get("llm_intents", {})
            if mkey in llm_intents and not force:
                with lock:
                    stats["skipped"] += 1
                return
            tr = json.loads(sample.trajectories) if isinstance(sample.trajectories, str) else (sample.trajectories or [])
            tr_norm = normalize_by_agent(agent_of(exp_id), tr)
            rounds = extract_sql_rounds(tr_norm)
            if not rounds:
                llm_intents[mkey] = []
                meta["llm_intents"] = llm_intents
                sample.meta = meta
                flag_modified(sample, "meta")
                session.add(sample)
                session.commit()
                with lock:
                    stats["done"] += 1
                return
            t0 = time.time()
            results = classify_trajectory(rounds, client, model=second_model)
            elapsed = time.time() - t0
            if not results:
                with lock:
                    stats["failed"] += 1
                return
            llm_intents[mkey] = [
                {
                    "round": r.round_index,
                    "sql_index": r.sql_index,
                    "global_index": r.global_index,
                    "intent": r.intent,
                    "data_type": r.data_type,
                    "reasoning": r.reasoning,
                }
                for r in results
            ]
            meta["llm_intents"] = llm_intents
            sample.meta = meta
            flag_modified(sample, "meta")
            session.add(sample)
            session.commit()
            with lock:
                stats["done"] += 1
                done = stats["done"] + stats["skipped"]
                total = stats["total"]
            logger.info("[%d/%d] %s idx=%d: %d SQL (%.1fs)", done, total, exp_id, idx, len(results), elapsed)
        except Exception as e:
            try:
                session.rollback()
            except Exception:
                pass
            logger.exception("Worker failed exp_id=%s idx=%d: %s", exp_id, idx, e)
            with lock:
                stats["failed"] += 1

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(process, e, i) for e, i in samples]
        for _ in as_completed(futures):
            pass
    logger.info("Relabel done: %s", stats)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--base-model-key", default="claude_opus_4_6")
    parser.add_argument("--second-model", default="gemini-3.1-pro",
                        help="Cross-validation model; prefer a different family (e.g. gemini-3.1-pro) for error independence")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Only report disputed samples; don't call LLM")
    args = parser.parse_args()

    engine = create_engine(args.db, connect_args={"check_same_thread": False} if args.db.startswith("sqlite") else {})
    samples = find_disputed_samples(engine, args.base_model_key)
    logger.info("Disputed samples: %d", len(samples))
    if args.dry_run:
        return
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.shubiaobiao.cn/v1")
    client = OpenAI(api_key=api_key, base_url=base_url)
    relabel(engine, samples, args.second_model, client, args.concurrency, args.force)


if __name__ == "__main__":
    main()
