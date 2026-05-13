#!/usr/bin/env python
"""Arbiter: Claude Opus 4.7 re-labels ONLY the SQLs where Claude 4.6 and Gemini 3.1 disagree.

Per-SQL classification (no round context, no reasoning). Excludes pre-accepted
confusion pairs (e.g., metric_scan→baseline_collect, where user accepts Gemini's label).

Pipeline:
1. Load all (exp_id, idx, round, sql_idx, sql_text, claude_intent, gemini_intent) where
   claude_intent != gemini_intent AND (claude_intent, gemini_intent) not in excluded pairs.
2. Group into batches of BATCH_SIZE SQLs.
3. For each batch: call Opus 4.7 with a minimal prompt (SQL text + 19 intent list + tie-break).
4. Output: {"i": <batch_index>, "x": "<intent>"} per SQL.
5. Store results in meta.llm_intents.claude_opus_4_7_arbiter keyed by (round, sql_index).

Usage:
    OPENAI_API_KEY=xxx uv run python scripts/arbitrate_disagreements.py \
        --db postgresql://... --concurrency 10 --batch-size 30
"""

import argparse
import json
import logging
import os
import random
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI
from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, create_engine, select

sys.path.insert(0, str(__file__).rsplit("/scripts/", 1)[0])

from sota_rca.runner._fallback_db import EvaluationSample
from sota_rca.analysis.trajectory_normalizer import normalize_by_agent
from sota_rca.analysis.llm_intent_classifier import extract_sql_rounds
from sota_rca.analysis.intent_prompt import VALID_INTENTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EXPS = [
    "thinkdepthai-claude-sonnet-4.6",
    "thinkdepthai-qwen3.5-plus",
    "aiq-qwen3.5-plus",
    "claudecode-qwen3.5-plus",
    "taskweaver-qwen3.5-plus",
]

CLAUDE_KEY = "claude_opus_4_6"
GEMINI_KEY = "gemini_3_1_pro_preview"
# Default arbiter key (back-compat); overridden by _arbiter_key_for(model) at runtime
ARBITER_KEY = "claude_opus_4_7_arbiter"


def _arbiter_key_for(model: str) -> str:
    """Derive meta.llm_intents key for arbiter labels from the model name."""
    return model_key(model) + "_arbiter"

# Disagreement (claude_intent, gemini_intent) pairs that the user accepts as Gemini's win.
EXCLUDED_PAIRS: set[tuple[str, str]] = {
    ("metric_scan", "baseline_collect"),
}


ARBITER_SYSTEM_PROMPT = f"""\
You are classifying SQL queries from an agent's Root Cause Analysis trajectory.
Each SQL runs against tables named abnormal_logs / normal_logs / abnormal_traces / normal_traces /
abnormal_metrics / normal_metrics (one or more per query). Pick ONE intent per SQL from:

Traces:
- latency_ranking: Global latency overview across all services (GROUP BY service, AVG/MAX duration)
- throughput_compare: Global request volume (GROUP BY service, COUNT)
- error_rate_scan: Global error distribution (GROUP BY service, status_code / error count)
- service_trace_scan: Examine one service's traces — spans, duration, status, endpoints
  (WHERE service = X, or LIKE '%service_name%' on traces)
- trace_follow: Follow one request by trace_id on a TRACES table (WHERE trace_id = X).
  If the same trace_id filter is on a logs table instead, use service_log_browse.
- call_tree_build: STRICT — requires a SELF-JOIN of traces with parent_span_id = span_id.
  DO NOT use this label for queries that merely SELECT DISTINCT service_name or select span_name
  from one trace; those are service_trace_scan (with WHERE service) or trace_follow (with WHERE trace_id).

Logs:
- error_log_overview: Global log scan across services (GROUP BY service, level)
- service_error_log: Specific service's error logs (service = X AND level = ERROR/WARN)
- service_log_browse: Browse a service's logs without level filter (service = X).
  Also used when logs are filtered by trace_id on a LOGS table.
- keyword_search: LIKE pattern on message / span_name fields to find error phrases
  (timeout, OOM, chaos, exception, 500, etc.).
  If LIKE is on service_name, use service_trace_scan (traces) or service_log_browse (logs) instead.
- error_timeline: Establish error timeline — first/last occurrence, time range
  (MIN/MAX time, ORDER BY time with error focus, EPOCH). Applicable to logs or traces.

Metrics:
- metric_scan: ONLY when SELECT DISTINCT metric_name, or metrics are browsed without any
  domain keyword anywhere in the SQL. If you can identify a domain (cpu/memory/jvm/k8s/db/network)
  from metric filter, LIKE pattern, or metric name in SELECT, use that specific domain label instead.
- container_resource: CPU / memory metrics (container.cpu, container.memory, memory.working_set)
- jvm_state: JVM metrics (jvm, gc, hikari, thread, heap)
- network_layer: Network metrics (hubble, http_request, tcp, drop, p95)
- k8s_state: Kubernetes state (k8s.pod.phase, restart, deployment)
- db_state: Database metrics (db.client, mysql, connections)

Baseline:
- baseline_collect: Query touches ONLY normal_* tables (establishing baseline).
  This wins over trace_follow/service_trace_scan/call_tree_build when only normal_* tables are involved.
- baseline_contrast: Compare normal vs abnormal — REQUIRES both normal_* AND abnormal_* tables
  (UNION / JOIN / EXCEPT). Single-table queries cannot be baseline_contrast.

## Tie-break (when multiple intents match)
1. JOIN parent_span_id=span_id → call_tree_build
2. Only normal_* tables → baseline_collect;  normal_* + abnormal_* → baseline_contrast
3. trace_id on traces → trace_follow
4. Logs + service + level → service_error_log
5. LIKE on message/span_name → keyword_search
6. Specific metric domain keyword → that domain; else metric_scan

## Output format (STRICT)
Return ONLY a JSON array. Each entry: {{"i": <input id>, "x": "<intent>"}}.
Example: [{{"i":1,"x":"service_error_log"}},{{"i":2,"x":"baseline_collect"}}]
NO reasoning. NO markdown. NO prose. Intent MUST be one of: {", ".join(VALID_INTENTS)}.
"""

USER_TEMPLATE = "{items}"


def model_key(model_name: str) -> str:
    return model_name.replace("/", "_").replace(".", "_").replace("-", "_")


def agent_of(exp_id: str) -> str:
    return exp_id.split("-", 1)[0] if exp_id else ""


def get_engine(db_url: str, concurrency: int = 1):
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(
        db_url,
        connect_args=connect_args,
        pool_size=max(concurrency * 2, 30),
        max_overflow=10,
        pool_pre_ping=True,
    )


def load_disagreements(engine) -> list[dict]:
    """Return list of dicts: {exp_id, dataset_index, round, sql_idx, sql_text, claude_intent, gemini_intent}
    for every (sample, round, sql_idx) where the two models disagree, excluding pre-accepted pairs.
    """
    out: list[dict] = []
    with engine.connect() as conn:
        for exp_id in EXPS:
            rows = conn.execute(
                text(
                    f"""SELECT dataset_index, trajectories, meta FROM evaluation_data
                        WHERE exp_id='{exp_id}' AND stage='judged'
                          AND (meta::jsonb->'llm_intents') ? '{CLAUDE_KEY}'
                          AND (meta::jsonb->'llm_intents') ? '{GEMINI_KEY}'"""
                )
            ).fetchall()
            for idx, traj_raw, meta_raw in rows:
                tr = json.loads(traj_raw) if isinstance(traj_raw, str) else traj_raw
                m = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
                ents_c = (m.get("llm_intents") or {}).get(CLAUDE_KEY, [])
                ents_g = (m.get("llm_intents") or {}).get(GEMINI_KEY, [])
                c_by_pos = {(e.get("round"), e.get("sql_index")): e.get("intent", "") for e in ents_c}
                g_by_pos = {(e.get("round"), e.get("sql_index")): e.get("intent", "") for e in ents_g}

                # Extract SQL text by position
                tr_norm = normalize_by_agent(agent_of(exp_id), tr)
                sql_by_pos = {
                    (r.round_index, i + 1): sql
                    for r in extract_sql_rounds(tr_norm)
                    for i, sql in enumerate(r.queries)
                }

                for pos, ic in c_by_pos.items():
                    ig = g_by_pos.get(pos)
                    if ig is None or ic == ig or (ic, ig) in EXCLUDED_PAIRS:
                        continue
                    sql = sql_by_pos.get(pos)
                    if not sql:
                        continue
                    out.append({
                        "exp_id": exp_id,
                        "dataset_index": idx,
                        "round": pos[0],
                        "sql_idx": pos[1],
                        "sql": sql,
                        "claude_intent": ic,
                        "gemini_intent": ig,
                    })
    return out


def _is_rate_limit(err: Exception) -> bool:
    s = str(err).lower()
    return "429" in s or "rate" in s or "上游负载" in s or "upstream" in s


def _parse_arbiter_response(content: str, batch_size: int) -> dict[int, str]:
    """Parse [{i,x}, ...] into {i: x}. Tolerate markdown fences, surrounding prose."""
    m = re.search(r"\[.*\]", content, re.DOTALL)
    raw = m.group(0) if m else content
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    out: dict[int, str] = {}
    if not isinstance(items, list):
        return out
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            i = int(it.get("i", 0))
        except (TypeError, ValueError):
            continue
        x = it.get("x", "")
        if i <= 0 or i > batch_size or x not in VALID_INTENTS:
            continue
        out[i] = x
    return out


def arbitrate_batch(
    items: list[dict],
    client: OpenAI,
    model: str,
    max_retries: int = 5,
) -> dict[int, str]:
    """Send a batch of disagreeing SQLs to the arbiter LLM. Return {batch_id: intent}."""
    # Truncate very long SQL to keep batch within a sensible context window
    body_lines = []
    for k, it in enumerate(items, 1):
        sql = re.sub(r"\s+", " ", it["sql"]).strip()[:600]
        body_lines.append(f"{k}: {sql}")
    user_msg = "\n".join(body_lines)

    messages = [
        {"role": "system", "content": ARBITER_SYSTEM_PROMPT},
        {"role": "user", "content": USER_TEMPLATE.format(items=user_msg)},
    ]
    rate_backoff = [5.0, 15.0, 45.0, 90.0, 180.0]

    # Opus 4.7+ (and some newer models) reject `temperature`; pass it only for models that accept it.
    # Simple heuristic: skip temperature for opus-4-7 and later.
    extra_params = {}
    if "opus-4-6" in model or "opus-4.6" in model or "gemini" in model or "haiku" in model or "sonnet" in model:
        extra_params["temperature"] = 0.0

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=8192,
                **extra_params,
            )
            content = resp.choices[0].message.content or ""
            parsed = _parse_arbiter_response(content, len(items))
            if len(parsed) >= max(1, int(0.7 * len(items))):
                # require >=70% of batch parsed; else treat as malformed and retry
                return parsed
            logger.warning(
                "Attempt %d/%d parsed only %d/%d; content prefix=%r",
                attempt + 1, max_retries, len(parsed), len(items), content[:160],
            )
        except Exception as e:
            last_err = e
            if _is_rate_limit(e):
                wait = rate_backoff[min(attempt, len(rate_backoff) - 1)]
                wait = wait * (0.8 + random.random() * 0.4)
                logger.warning(
                    "Arbiter attempt %d/%d rate-limited; sleeping %.1fs",
                    attempt + 1, max_retries, wait,
                )
                time.sleep(wait)
            else:
                logger.warning("Arbiter attempt %d/%d error: %s", attempt + 1, max_retries, e)
    logger.error("Arbiter gave up on batch of %d (last_err=%s)", len(items), last_err)
    return {}


def store_results(engine, items: list[dict], arbiter_labels: dict[int, str], key: str = ARBITER_KEY) -> int:
    """Merge per-position arbiter labels into meta.llm_intents[key]."""
    # Group labels by (exp_id, idx)
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for k, it in enumerate(items, 1):
        if k not in arbiter_labels:
            continue
        grouped[(it["exp_id"], it["dataset_index"])].append({
            "round": it["round"],
            "sql_index": it["sql_idx"],
            "intent": arbiter_labels[k],
        })

    written = 0
    with Session(engine) as session:
        for (exp_id, idx), entries in grouped.items():
            sample = session.exec(
                select(EvaluationSample).where(
                    EvaluationSample.exp_id == exp_id,
                    EvaluationSample.dataset_index == idx,
                    EvaluationSample.stage == "judged",
                )
            ).first()
            if not sample:
                continue
            meta = sample.meta or {}
            llm_intents = meta.setdefault("llm_intents", {})
            existing = {
                (e.get("round"), e.get("sql_index")): e
                for e in llm_intents.get(key, [])
            }
            for e in entries:
                existing[(e["round"], e["sql_index"])] = e
            llm_intents[key] = sorted(
                existing.values(),
                key=lambda x: (x.get("round", 0), x.get("sql_index", 0)),
            )
            meta["llm_intents"] = llm_intents
            sample.meta = meta
            flag_modified(sample, "meta")
            session.add(sample)
            written += len(entries)
        session.commit()
    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--model", default="claude-opus-4-7")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=30)
    parser.add_argument("--limit", type=int, default=None, help="Limit to first N disagreements (for testing)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    engine = get_engine(args.db, concurrency=args.concurrency)
    items = load_disagreements(engine)
    logger.info("Found %d disagreeing SQL positions (excluding pre-accepted pairs)", len(items))
    if args.limit:
        items = items[: args.limit]
        logger.info("Limited to first %d items", len(items))
    if args.dry_run:
        return

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.shubiaobiao.cn/v1")
    client = OpenAI(api_key=api_key, base_url=base_url)

    arbiter_key = _arbiter_key_for(args.model)
    logger.info("Writing results under meta.llm_intents.%s", arbiter_key)

    # Skip items that already have arbiter label (for resume)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""SELECT exp_id, dataset_index, meta->'llm_intents'->'{arbiter_key}'
                    FROM evaluation_data
                    WHERE stage='judged' AND (meta::jsonb->'llm_intents') ? '{arbiter_key}'"""
            )
        ).fetchall()
    already_labeled: set[tuple[str, int, int, int]] = set()
    for exp_id, idx, arbiter_ents in rows:
        ents = json.loads(arbiter_ents) if isinstance(arbiter_ents, str) else (arbiter_ents or [])
        for e in ents:
            already_labeled.add((exp_id, idx, e.get("round"), e.get("sql_index")))
    pending = [
        it for it in items
        if (it["exp_id"], it["dataset_index"], it["round"], it["sql_idx"]) not in already_labeled
    ]
    logger.info("After resume-skip: %d remaining (previously labeled: %d)",
                len(pending), len(items) - len(pending))

    # Batch
    batches: list[list[dict]] = []
    for i in range(0, len(pending), args.batch_size):
        batches.append(pending[i : i + args.batch_size])
    logger.info("Dispatching %d batches × %d items with concurrency=%d",
                len(batches), args.batch_size, args.concurrency)

    lock = threading.Lock()
    stats = {"done": 0, "failed": 0, "total_labels": 0}

    def process_batch(batch: list[dict]) -> None:
        labels = arbitrate_batch(batch, client, args.model)
        if not labels:
            with lock:
                stats["failed"] += 1
            return
        written = store_results(engine, batch, labels, key=arbiter_key)
        with lock:
            stats["done"] += 1
            stats["total_labels"] += written
            done = stats["done"] + stats["failed"]
        logger.info("[%d/%d] batch done: %d labels written", done, len(batches), written)

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [executor.submit(process_batch, b) for b in batches]
        for fut in as_completed(futures):
            exc = fut.exception()
            if exc is not None:
                logger.error("Worker exception: %s", exc)

    logger.info("DONE: batches_ok=%d failed=%d total_labels_written=%d",
                stats["done"], stats["failed"], stats["total_labels"])


if __name__ == "__main__":
    main()
