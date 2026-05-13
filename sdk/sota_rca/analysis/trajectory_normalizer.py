"""Framework-specific trajectory normalizers.

Rewrites agent trajectories so downstream extractors (extract_steps,
extract_sql_rounds) see a uniform OpenAI-style query_parquet_files tool_call
regardless of the underlying agent framework.

Numbering invariants preserved by every normalizer:
- Assistant message count unchanged (-> round numbers stable)
- For each assistant message: the ORDER of steps preserved
- When a single tool_call holds N>1 SQLs, it is split in-place into N
  synthetic tool_calls at the same position in the same assistant message,
  and N corresponding tool-result messages are emitted so (tool_call_id -> result)
  linkage stays intact.
"""

from __future__ import annotations

import copy
import json
import logging
import re
import shlex
from typing import Any, Callable

logger = logging.getLogger(__name__)

_PARQUET_RE = re.compile(r"[^\s'\"]+\.parquet")
_SELECT_LOOSE = re.compile(r"\bSELECT\b", re.IGNORECASE)


def _extract_sqls_from_bash(command: str) -> list[str]:
    """Extract SQL SELECT statements from a Bash command string.

    Handles duckdb invocations in these forms:
        duckdb -c "SELECT ..."
        duckdb -c 'SELECT ...'
        duckdb path.db -c "..." -c "..."        (multi -c chain)
        duckdb <<< "SELECT ..."
        duckdb <<< 'SELECT ...'
        duckdb <<EOF\nSELECT ...\nEOF           (heredoc)
        echo "SELECT ..." | duckdb path.db      (pipe)

    Falls back to a loose SELECT ... scan if no structured form matches but
    the command contains SELECT.
    """
    if not command or not _SELECT_LOOSE.search(command):
        return []

    sqls: list[str] = []

    # 1) Multi -c chains. We use shlex to split respecting quotes, then grab
    #    the argument that follows every -c flag.
    try:
        tokens = shlex.split(command, posix=True)
        i = 0
        while i < len(tokens) - 1:
            if tokens[i] == "-c" and _SELECT_LOOSE.search(tokens[i + 1]):
                sqls.append(tokens[i + 1].strip())
                i += 2
            else:
                i += 1
    except ValueError:
        # Unbalanced quotes: fall through to regex-based fallbacks
        pass

    # 2) Heredoc forms (shlex can't help here since heredoc bodies aren't tokens)
    for m in re.finditer(
        r"<<\s*['\"]?(\w+)['\"]?\s*\n(.*?)\n\1\b",
        command,
        re.DOTALL,
    ):
        body = m.group(2).strip()
        if _SELECT_LOOSE.search(body):
            sqls.append(body)

    # 3) <<< here-strings: duckdb <<<"SELECT ..." or <<<'SELECT ...'
    for m in re.finditer(r"<<<\s*(['\"])(.*?)\1", command, re.DOTALL):
        body = m.group(2).strip()
        if _SELECT_LOOSE.search(body):
            sqls.append(body)

    # Dedupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for s in sqls:
        if s not in seen:
            seen.add(s)
            deduped.append(s)

    # 4) Fallback: no structured SQL found but SELECT is in the command.
    #    Pull every distinct "SELECT ... <terminator>" substring.
    if not deduped:
        for m in re.finditer(
            r"SELECT\s+.+?(?:;|$|'|\"|\|\s*duckdb|\n\s*\n)",
            command,
            re.IGNORECASE | re.DOTALL,
        ):
            candidate = m.group(0).rstrip(";\"'| \n")
            candidate = candidate.strip()
            if candidate and candidate not in seen:
                seen.add(candidate)
                deduped.append(candidate)

    return deduped


def _detect_parquet_files(command: str) -> list[str]:
    """Pull parquet file paths referenced in the Bash command."""
    return list(dict.fromkeys(_PARQUET_RE.findall(command)))


def _duplicate_result_message(original: dict, new_id: str) -> dict:
    """Create a tool-result clone with a new tool_call_id."""
    clone = copy.deepcopy(original)
    clone["tool_call_id"] = new_id
    return clone


def normalize_claudecode(trajectory: list[dict]) -> list[dict]:
    """Rewrite Bash-only claudecode trajectories so downstream extractors see
    query_parquet_files tool_calls.

    Rules:
    - Bash calls whose `command` contains one or more SELECT statements are
      rewritten to one or more `query_parquet_files` tool_calls (1:N split if
      the command runs multiple SQLs).
    - Non-SQL Bash (ls/find/cat/head/etc.) is left untouched so downstream
      classifiers skip it as discovery.
    - Round numbers (=assistant_turn_index) are NOT affected: splits happen
      within a single assistant message.
    - When a Bash is split into N tool_calls, the original tool-result message
      is duplicated N-1 times with fresh tool_call_ids so every synthetic
      tool_call still has a matching result.
    """
    result: list[dict] = []
    # tool_call_id -> list[new_ids]: when a bash with id X is split into N,
    # the first result keeps id X and N-1 duplicates are appended for X::sql2..N
    id_remap: dict[str, list[str]] = {}

    for msg in trajectory:
        if msg.get("role") != "assistant" or not msg.get("tool_calls"):
            result.append(msg)
            continue

        new_msg = copy.deepcopy(msg)
        new_tool_calls: list[dict] = []
        for tc in new_msg.get("tool_calls") or []:
            fn = (tc.get("function") or {}).get("name", "")
            if fn != "Bash":
                new_tool_calls.append(tc)
                continue

            args_raw = (tc.get("function") or {}).get("arguments", "")
            try:
                args = json.loads(args_raw) if args_raw else {}
            except (json.JSONDecodeError, TypeError):
                args = {}
            command = args.get("command", "") if isinstance(args, dict) else ""

            sqls = _extract_sqls_from_bash(command)
            if not sqls:
                # Leave as-is; non-SQL bash (ls/find/cat/wc/etc.)
                new_tool_calls.append(tc)
                continue

            parquet_files = _detect_parquet_files(command)
            base_id = tc.get("id", "") or ""

            if len(sqls) == 1:
                synth = copy.deepcopy(tc)
                synth["function"]["name"] = "query_parquet_files"
                synth["function"]["arguments"] = json.dumps(
                    {"query": sqls[0], "parquet_files": parquet_files}
                )
                new_tool_calls.append(synth)
                continue

            # 1 -> N split. Keep the first id as-is for the original result;
            # append new ids for subsequent SQLs and record remap so we can
            # duplicate the tool-result message later.
            new_ids = [base_id]
            for k in range(1, len(sqls)):
                new_ids.append(f"{base_id}::sql{k + 1}")
            if base_id:
                id_remap[base_id] = new_ids[1:]

            for sql, nid in zip(sqls, new_ids):
                synth = copy.deepcopy(tc)
                synth["id"] = nid
                synth["function"]["name"] = "query_parquet_files"
                synth["function"]["arguments"] = json.dumps(
                    {"query": sql, "parquet_files": parquet_files}
                )
                new_tool_calls.append(synth)

        new_msg["tool_calls"] = new_tool_calls
        result.append(new_msg)

    # Second pass: duplicate tool-result messages for split Bash calls
    if not id_remap:
        return result

    final: list[dict] = []
    for msg in result:
        if msg.get("role") != "tool":
            final.append(msg)
            continue
        final.append(msg)
        tcid = msg.get("tool_call_id", "")
        for extra_id in id_remap.get(tcid, []):
            final.append(_duplicate_result_message(msg, extra_id))
    return final


# ── Dispatch table ───────────────────────────────────────────────────────────

NORMALIZERS: dict[str, Callable[[list[dict]], list[dict]]] = {
    "claudecode": normalize_claudecode,
}


def normalize_by_agent(agent_type: str, trajectory: list[dict]) -> list[dict]:
    """Apply the normalizer for this agent_type, or return trajectory unchanged.

    agent_type is the first '-' segment of an exp_id
    (e.g., 'claudecode-qwen3.5-plus' -> 'claudecode').
    """
    norm = NORMALIZERS.get(agent_type)
    return norm(trajectory) if norm else trajectory
