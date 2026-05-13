"""LLM-based intent classifier for agent trajectories.

Classifies each SQL query into one of 19 troubleshooting intents
using an LLM (via OpenAI-compatible API). Fully decoupled from extractor.py.

Each SQL gets its own intent, organized within rounds:
- round: trajectory round index (1-based)
- sql_index: position within the round (1-based)
- global_index: position across the entire trajectory (1-based, cross-round)

Usage:
    from sota_rca.analysis.llm_intent_classifier import classify_trajectory, extract_sql_rounds

    rounds = extract_sql_rounds(trajectory_json)
    results = classify_trajectory(rounds, client, model="claude-haiku-4-5-20251001")
"""

import json
import logging
import random
import re
import time
from dataclasses import dataclass, field

from .intent_prompt import (
    FEW_SHOT_ASSISTANT,
    FEW_SHOT_USER,
    SYSTEM_PROMPT,
    USER_TEMPLATE,
    VALID_INTENTS,
)


logger = logging.getLogger(__name__)


@dataclass
class SQLRound:
    """A round in the trajectory that contains SQL queries."""

    round_index: int  # 1-based round index (counting all assistant+tool_calls rounds)
    queries: list[str] = field(default_factory=list)  # SQL query strings
    tool_names: list[str] = field(default_factory=list)  # tool function names


@dataclass
class SQLIntent:
    """Classification result for a single SQL query."""

    round_index: int  # round number in trajectory
    sql_index: int  # 1-based position within the round
    global_index: int  # 1-based position across entire trajectory
    intent: str
    data_type: str = ""  # logs, traces, metrics (from table name)
    reasoning: str = ""


# ── Data Type Classification (local, no LLM) ────────────────────────────────

_TABLE_PATTERNS = [
    (re.compile(r"\blog[s]?\b", re.IGNORECASE), "logs"),
    (re.compile(r"\btrace[s]?\b", re.IGNORECASE), "traces"),
    (re.compile(r"\bmetric[s]?\b|metrics_sum|metrics_histogram", re.IGNORECASE), "metrics"),
]


def classify_data_type(sql: str) -> str:
    """Classify SQL query's data modality by table name.

    Returns: "logs", "traces", "metrics", or "unknown".
    """
    # Look for FROM/JOIN table names
    from_tables = re.findall(r"(?:FROM|JOIN)\s+(\w+)", sql, re.IGNORECASE)
    types_found = set()
    for table in from_tables:
        tl = table.lower()
        if "log" in tl:
            types_found.add("logs")
        elif "trace" in tl:
            types_found.add("traces")
        elif "metric" in tl:
            types_found.add("metrics")

    if len(types_found) == 1:
        return types_found.pop()
    if len(types_found) > 1:
        # Multiple modalities in one SQL (e.g., JOIN traces + metrics) — pick first FROM
        for table in from_tables:
            tl = table.lower()
            if "log" in tl:
                return "logs"
            if "trace" in tl:
                return "traces"
            if "metric" in tl:
                return "metrics"
    return "unknown"


# ── Trajectory Parsing ──────────────────────────────────────────────────────


def extract_sql_rounds(trajectory: list[dict]) -> list[SQLRound]:
    """Extract rounds containing SQL queries from a trajectory.

    Skips rounds that only contain think_tool, list_tables, get_schema calls.
    """
    rounds: list[SQLRound] = []
    round_index = 0

    for msg in trajectory:
        if msg.get("role") != "assistant" or not msg.get("tool_calls"):
            continue
        round_index += 1

        sqls: list[str] = []
        tool_names: list[str] = []

        for tc in msg["tool_calls"]:
            fn = tc.get("function", {}).get("name", "")
            tool_names.append(fn)

            # Skip non-SQL tools
            if fn in ("think_tool", "list_tables_in_directory", "get_schema", "think"):
                continue

            args_raw = tc.get("function", {}).get("arguments", "")
            try:
                args = json.loads(args_raw) if args_raw else {}
            except (json.JSONDecodeError, TypeError):
                args = {}

            # Extract SQL from common parameter names
            sql = args.get("query", args.get("sql", args.get("sql_query", "")))
            if sql and "SELECT" in sql.upper():
                sqls.append(sql.strip())

        if sqls:
            rounds.append(SQLRound(round_index=round_index, queries=sqls, tool_names=tool_names))

    return rounds


def format_rounds_for_prompt(rounds: list[SQLRound]) -> str:
    """Format SQL rounds into text for the LLM prompt.

    Always labels each SQL with -- SQL N for clarity, even single-SQL rounds.
    """
    parts = []
    for r in rounds:
        header = f"Round {r.round_index} ({len(r.queries)} SQL {'queries' if len(r.queries) > 1 else 'query'}):"
        sql_parts = []
        for i, sql in enumerate(r.queries, 1):
            sql_parts.append(f"-- SQL {i}\n{sql}")
        parts.append(f"{header}\n```sql\n{chr(10).join(sql_parts)}\n```")
    return "\n\n".join(parts)


# ── LLM Classification ─────────────────────────────────────────────────────


def _parse_llm_response(content: str, rounds: list[SQLRound]) -> list[SQLIntent]:
    """Parse LLM JSON response into SQLIntent objects with global_index."""
    # Extract JSON from possible markdown code blocks
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", content, re.DOTALL)
    raw = json_match.group(1) if json_match else content

    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON: %s", content[:200])
        return []

    if not isinstance(items, list):
        logger.warning("LLM response is not a list: %s", type(items))
        return []

    # Build mappings: (round_index, sql_index) -> global_index and SQL text
    global_idx_map: dict[tuple[int, int], int] = {}
    sql_text_map: dict[tuple[int, int], str] = {}
    gi = 0
    for r in rounds:
        for si, sql in enumerate(r.queries, 1):
            gi += 1
            global_idx_map[(r.round_index, si)] = gi
            sql_text_map[(r.round_index, si)] = sql

    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        intent = item.get("intent", "")
        if intent not in VALID_INTENTS:
            logger.warning("Invalid intent '%s' for round %s sql %s, skipping", intent, item.get("round"), item.get("sql_index"))
            continue

        round_idx = item.get("round", 0)
        sql_idx = item.get("sql_index", 1)
        key = (round_idx, sql_idx)
        if key not in global_idx_map:
            # LLM hallucinated a non-existent (round, sql_index) pair.
            # Drop it instead of storing a phantom entry with global_index=0.
            logger.warning(
                "Dropping phantom LLM entry at round=%s sql_index=%s (no such SQL in trajectory)",
                round_idx, sql_idx,
            )
            continue
        g_idx = global_idx_map[key]
        sql_text = sql_text_map[key]

        # data_type: prefer LLM-provided if present, else derive from SQL table name.
        # reasoning: optional; slim-output prompts omit it entirely.
        results.append(
            SQLIntent(
                round_index=round_idx,
                sql_index=sql_idx,
                global_index=g_idx,
                intent=intent,
                data_type=item.get("data_type") or classify_data_type(sql_text),
                reasoning=item.get("reasoning", ""),
            )
        )

    # Sort by global_index for consistent ordering
    results.sort(key=lambda x: (x.round_index, x.sql_index))

    return results


def classify_trajectory(
    rounds: list[SQLRound],
    client,  # openai.OpenAI instance
    model: str = "claude-haiku-4-5-20251001",
    temperature: float = 0.0,
    max_retries: int = 5,
) -> list[SQLIntent]:
    """Classify all SQL queries in a trajectory using one LLM call.

    Args:
        rounds: SQL rounds extracted by extract_sql_rounds()
        client: OpenAI-compatible client
        model: Model ID on the API
        temperature: Sampling temperature (0 for deterministic)
        max_retries: Retry count if LLM returns unparseable / empty output.
            Subsequent retries add a nudge reminding JSON-only output.

    Returns:
        List of SQLIntent, one per SQL query. Empty list if all retries fail.
    """
    if not rounds:
        return []

    rounds_text = format_rounds_for_prompt(rounds)
    user_content = USER_TEMPLATE.format(rounds_text=rounds_text)

    base_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        # Few-shot example
        {"role": "user", "content": FEW_SHOT_USER},
        {"role": "assistant", "content": FEW_SHOT_ASSISTANT},
        # Actual request
        {"role": "user", "content": user_content},
    ]

    # Backoff schedule: 429 / rate limit errors get longer waits; parse errors reuse short wait.
    # Schedule is generous to absorb upstream backpressure. Capped at max_retries tries total.
    rate_limit_backoff = [5.0, 15.0, 45.0, 90.0, 180.0]

    def _is_rate_limit(err: Exception) -> bool:
        s = str(err).lower()
        return "429" in s or "rate" in s or "上游负载" in s or "upstream" in s

    last_err: Exception | None = None
    for attempt in range(max_retries):
        messages = list(base_messages)
        if attempt > 0 and last_err is None:
            # Previous attempt succeeded but JSON was unparseable → nudge
            messages.append({
                "role": "user",
                "content": "The previous response was not parseable JSON. Return ONLY a valid JSON array, no markdown, no prose.",
            })
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                # 16k: Gemini emits ~3× more reasoning tokens than Claude; 8k truncates big samples
                max_tokens=16384,
            )
            content = response.choices[0].message.content or ""
            # Detect truncation: finish_reason == 'length' means output was cut off
            try:
                finish = response.choices[0].finish_reason
                if finish == "length":
                    logger.warning(
                        "Attempt %d/%d hit max_tokens (finish_reason=length); response truncated",
                        attempt + 1, max_retries,
                    )
            except Exception:
                pass
        except Exception as e:
            last_err = e
            if _is_rate_limit(e):
                wait = rate_limit_backoff[min(attempt, len(rate_limit_backoff) - 1)]
                # Add jitter so concurrent workers don't synchronize on retry
                wait = wait * (0.8 + random.random() * 0.4)
                logger.warning(
                    "LLM attempt %d/%d hit rate limit; backing off %.1fs before retry",
                    attempt + 1, max_retries, wait,
                )
                time.sleep(wait)
            else:
                logger.warning("LLM call attempt %d/%d failed: %s", attempt + 1, max_retries, e)
            continue

        last_err = None
        results = _parse_llm_response(content, rounds)
        if results:
            if attempt > 0:
                logger.info("Recovered after %d retries", attempt)
            return results
        logger.warning(
            "Attempt %d/%d produced 0 parseable entries (content prefix: %r)",
            attempt + 1, max_retries, content[:120],
        )

    if last_err is not None:
        logger.error("All %d attempts failed; last error: %s", max_retries, last_err)
    else:
        logger.error("All %d attempts produced unparseable output", max_retries)
    return []
