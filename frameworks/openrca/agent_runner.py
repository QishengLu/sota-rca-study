#!/usr/bin/env python
"""
agent_runner.py — OpenRCA adapter for SOTA-agents evaluation pipeline

stdin:  JSON { question, system_prompt, user_prompt,
               compress_system_prompt, compress_user_prompt, data_dir }
stdout: last line JSON { output (CausalGraph JSON with root_causes), trajectory }

Architecture:
  OpenRCA = Controller LLM (instructs) + Executor LLM (writes Python) + IPython kernel (executes)
  We adapt it by:
  1. Building a dynamic basic_prompt with our parquet schema + candidate services
  2. Running the standard control_loop from OpenRCA
  3. Parsing the root cause component from the output
"""

import json
import os
import re
import sys
from pathlib import Path

try:
    from sota_rca.tracker import auto_install
    _tracker = auto_install()
except ImportError:
    _tracker = None  # sota_rca not on PYTHONPATH; tracker disabled




from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ── Redirect stdout→stderr before any IPython/pandas output can pollute stdout ──
_real_stdout_fd = os.dup(1)   # save real stdout fd
os.dup2(2, 1)                  # fd 1 (stdout) now goes to stderr
sys.stdout = sys.stderr        # Python-level redirect too

# ── Now safe to import everything (their print()s go to stderr) ──────────────

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} {level} {message}")

import pandas as pd

# Import and patch api_router configs BEFORE control_loop import
from rca.api_router import configs

configs["SOURCE"] = "AI"
configs["MODEL"] = os.environ.get("OPENRCA_MODEL", "kimi-k2-0905-preview")
configs["API_KEY"] = os.environ.get("OPENAI_API_KEY", "")
configs["API_BASE"] = os.environ.get("OPENAI_BASE_URL", "https://api.moonshot.cn/v1")

from rca.baseline.rca_agent.controller import control_loop
import rca.baseline.rca_agent.prompt.agent_prompt as ap


# ── Schema template for our parquet-based telemetry ──────────────────────────

_SCHEMA_TMPL = """\
## TELEMETRY DIRECTORY STRUCTURE:

The telemetry data for this incident is stored in: `{data_dir}`

This directory contains the following Apache Parquet files (use `pd.read_parquet(path)`):

- `abnormal_metrics.parquet`  — metrics during the fault period
- `normal_metrics.parquet`    — baseline metrics (before the fault)
- `abnormal_traces.parquet`   — distributed traces during the fault
- `normal_traces.parquet`     — baseline traces
- `abnormal_logs.parquet`     — logs during the fault
- `normal_logs.parquet`       — baseline logs
- `env.json`                  — timing metadata

## DATA SCHEMA

### 1. Metric Files (abnormal_metrics.parquet / normal_metrics.parquet)
Columns:
- `time`                        : UTC datetime64[ns, UTC] — convert with .dt.tz_convert('Asia/Shanghai')
- `metric`                      : metric name (str), e.g. 'k8s.container.cpu_usage_rate',
                                  'k8s.pod.network_receive_bytes_rate', 'http.server.request_duration'
- `value`                       : float64
- `service_name`                : owning service (str), e.g. 'ts-auth-service'
- `attr.k8s.pod.name`           : pod name (str)
- `attr.k8s.container.name`     : container name (str)
- `attr.destination_workload`   : destination service for span/network metrics (str, may be NaN)
- `attr.source_workload`        : source service for span/network metrics (str, may be NaN)

Example usage:
```python
import pandas as pd
df = pd.read_parquet('{data_dir}/abnormal_metrics.parquet')
df['time_local'] = df['time'].dt.tz_convert('Asia/Shanghai')
```

### 2. Trace Files (abnormal_traces.parquet / normal_traces.parquet)
Columns:
- `time`                          : UTC datetime64[ns, UTC]
- `trace_id`, `span_id`, `parent_span_id` : span IDs (str)
- `span_name`                     : operation name (str), e.g. 'POST /api/v1/users/login'
- `service_name`                  : service that generated the span (str)
- `duration`                      : span duration in **nanoseconds** (uint64) — divide by 1e6 for ms
- `attr.status_code`              : 'STATUS_CODE_OK', 'STATUS_CODE_ERROR', 'STATUS_CODE_UNSET'
- `attr.http.response.status_code`: HTTP status (float64, NaN if not HTTP)
- `attr.span_kind`                : 'SPAN_KIND_CLIENT', 'SPAN_KIND_SERVER', etc.

Example usage:
```python
traces = pd.read_parquet('{data_dir}/abnormal_traces.parquet')
# Error rate per service:
error_spans = traces[traces['attr.status_code'] == 'STATUS_CODE_ERROR']
```

### 3. Log Files (abnormal_logs.parquet / normal_logs.parquet)
Columns:
- `time`            : UTC datetime64[ns, UTC]
- `level`           : 'INFO', 'ERROR', 'WARN', 'DEBUG'
- `service_name`    : service that emitted the log (str)
- `message`         : log message content (str)
- `trace_id`, `span_id` : correlation IDs (str, may be None)

Example usage:
```python
logs = pd.read_parquet('{data_dir}/abnormal_logs.parquet')
error_logs = logs[logs['level'] == 'ERROR']
```

### 4. env.json
```python
import json
with open('{data_dir}/env.json') as f:
    env = json.load(f)
# env keys: ABNORMAL_START, ABNORMAL_END, NORMAL_START, NORMAL_END (Unix seconds), TIMEZONE, NAMESPACE
fault_start = pd.Timestamp(int(env['ABNORMAL_START']), unit='s', tz='UTC').tz_convert('Asia/Shanghai')
fault_end   = pd.Timestamp(int(env['ABNORMAL_END']),   unit='s', tz='UTC').tz_convert('Asia/Shanghai')
```
"""

_CAND_TMPL = """\
## POSSIBLE ROOT CAUSE COMPONENTS:

{service_list}

NOTE: The root cause component MUST be selected from the list above.
"""


def _get_service_candidates(data_dir: str) -> str:
    """Extract unique ts-* service names from abnormal_metrics.parquet."""
    try:
        df = pd.read_parquet(
            os.path.join(data_dir, "abnormal_metrics.parquet"),
            columns=["service_name"],
        )
        services = sorted(
            s for s in df["service_name"].dropna().unique()
            if isinstance(s, str) and s.startswith("ts-")
        )
        if services:
            return _CAND_TMPL.format(service_list="\n".join(f"- {s}" for s in services))
    except Exception as e:
        logger.warning(f"Failed to extract candidates from parquet: {e}")
    return ""


def _build_objective(question: str, data_dir: str) -> str:
    """Build task instruction from augmented_question + env.json timing."""
    time_info = ""
    try:
        with open(os.path.join(data_dir, "env.json")) as f:
            env = json.load(f)
        t0 = pd.Timestamp(int(env["ABNORMAL_START"]), unit="s", tz="UTC")
        t1 = pd.Timestamp(int(env["ABNORMAL_END"]), unit="s", tz="UTC")
        time_info = (
            f"The anomaly window is from {t0.strftime('%Y-%m-%d %H:%M:%S')} UTC "
            f"to {t1.strftime('%Y-%m-%d %H:%M:%S')} UTC "
            f"({int((t1 - t0).total_seconds())} seconds)."
        )
    except Exception:
        pass

    return (
        f"{question}\n\n"
        f"{time_info}\n\n"
        "Your task: identify the ROOT CAUSE microservice that caused the SLO violations, "
        "and build a **causal propagation graph** showing how the fault propagated through the system.\n\n"
        "During your investigation, keep track of:\n"
        "- Which services are affected (nodes) and their abnormal state\n"
        "- How faults propagate between services (edges)\n"
        "- Which service(s) are the root cause (the origin of the fault propagation)\n\n"
        "## Required Output Format\n\n"
        "Your final answer MUST be a CausalGraph JSON with this structure:\n"
        "```json\n"
        "{\n"
        '  "nodes": [\n'
        '    {"component": "ts-xxx-service", "kind": "service", "state": ["HIGH_LATENCY"], "timestamp": 1234567890}\n'
        "  ],\n"
        '  "edges": [\n'
        '    {"source": "ts-a-service", "target": "ts-b-service", "kind": "calls"}\n'
        "  ],\n"
        '  "root_causes": [\n'
        '    {"component": "ts-xxx-service", "kind": "service", "state": ["HIGH_ERROR_RATE"], "timestamp": 1234567890}\n'
        "  ],\n"
        '  "component_to_service": {}\n'
        "}\n"
        "```\n\n"
        "**Available States**: HEALTHY, HIGH_ERROR_RATE, HIGH_LATENCY, UNAVAILABLE, "
        "TIMEOUT, HIGH_CPU, HIGH_MEMORY, HIGH_DISK_USAGE, NETWORK_DELAY, NETWORK_LOSS, "
        "KILLED, PROCESS_PAUSED, CONNECTION_RESET\n\n"
        "**Available Node Kinds**: service, pod, container, span, deployment\n"
        "**Available Edge Kinds**: calls, depends_on, affects, routes_to\n"
    )


def _parse_root_causes(answer: str) -> list[str]:
    """Extract root cause service names from OpenRCA JSON output."""
    if not answer:
        return []

    # Try JSON parse: {"1": {"root cause component": "ts-auth-service", ...}}
    try:
        parsed = json.loads(answer)
        if isinstance(parsed, dict):
            results = []
            for val in parsed.values():
                if isinstance(val, dict):
                    comp = val.get("root cause component", "")
                    if comp:
                        results.append(comp.strip())
            if results:
                return results
    except (json.JSONDecodeError, AttributeError):
        pass

    # Fallback: regex for ts-*-service patterns
    matches = re.findall(r"\bts-[a-z][a-z0-9-]*service\b", answer, re.IGNORECASE)
    return list(dict.fromkeys(matches))  # deduplicate, preserve order


def _convert_trajectory(trajectory: list) -> list:
    """Convert OpenRCA code/result trajectory to OpenAI role format."""
    result = []
    for i, step in enumerate(trajectory):
        code = step.get("code", "")
        obs = step.get("result", "")
        if code:
            result.append({"role": "assistant", "content": code})
        if obs:
            result.append({"role": "tool", "content": obs, "tool_call_id": f"exec_{i}"})
    return result


def _strip_markdown_json(text: str) -> str:
    """Strip ```json ... ``` code blocks, extract pure JSON."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def _compress_findings(
    trajectory_messages: list,
    compress_sp: str,
    compress_up: str,
    question: str,
) -> str | None:
    """Call LLM with compress prompts to synthesize a full CausalGraph JSON.

    Returns the CausalGraph JSON string, or None on failure.
    """
    from openai import OpenAI

    # Build messages: system + trajectory context + compress user prompt
    messages = [{"role": "system", "content": compress_sp}]

    # Add trajectory as conversation context
    for msg in trajectory_messages:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        if role == "tool":
            # Convert tool messages to user messages for context
            messages.append({"role": "user", "content": f"[Tool Result]\n{content}"})
        else:
            messages.append({"role": role, "content": content})

    # Add the compress user prompt (with incident description from question)
    # Extract incident description from the question for the compress prompt
    incident_desc = question[:500] if question else "Unknown incident"
    final_up = compress_up.replace("{incident_description}", incident_desc)
    messages.append({"role": "user", "content": final_up})

    try:
        client = OpenAI(
            api_key=configs["API_KEY"],
            base_url=configs["API_BASE"],
        )
        response = client.chat.completions.create(
            model=configs["MODEL"],
            messages=messages,
            temperature=0.0,
        )
        raw = response.choices[0].message.content or ""
        logger.info(f"Compress response (first 500 chars): {raw[:500]}")

        # Parse and validate
        cleaned = _strip_markdown_json(raw)
        parsed = json.loads(cleaned)
        # Must have at least root_causes
        if isinstance(parsed, dict) and "root_causes" in parsed:
            # Ensure all required fields exist
            parsed.setdefault("nodes", [])
            parsed.setdefault("edges", [])
            parsed.setdefault("component_to_service", {})
            return json.dumps(parsed, ensure_ascii=False)
        logger.warning(f"Compress output missing root_causes: {cleaned[:200]}")
    except Exception as e:
        logger.error(f"Compress step failed: {e}", exc_info=True)

    return None


def _write_stdout(data: dict) -> None:
    """Write the final JSON to the real stdout fd (not the redirected one)."""
    line = json.dumps(data, ensure_ascii=False) + "\n"
    os.write(_real_stdout_fd, line.encode("utf-8"))
    os.close(_real_stdout_fd)


def main():
    raw = sys.stdin.buffer.read()
    payload = json.loads(raw)

    question = payload.get("question", "")
    data_dir = payload.get("data_dir", "")

    # Fallback: extract data_dir from question text
    if not data_dir or not os.path.isdir(data_dir):
        m = re.search(r"stored in[:\s]+`([^`]+)`", question)
        if m:
            data_dir = m.group(1).strip()

    if not data_dir or not os.path.isdir(data_dir):
        logger.error(f"data_dir not found: {data_dir!r}")
        _write_stdout({"output": json.dumps({"nodes": [], "edges": [], "root_causes": []}), "trajectory": []})
        sys.exit(0)

    logger.info(f"data_dir: {data_dir}")

    # ── Build dynamic basic_prompt ─────────────────────────────────────────
    cand = _get_service_candidates(data_dir)
    schema = _SCHEMA_TMPL.format(data_dir=data_dir) + "\n" + cand

    class BasicPrompt:
        pass

    bp = BasicPrompt()
    bp.schema = schema
    bp.cand = cand

    # ── Build objective ────────────────────────────────────────────────────
    objective = _build_objective(question, data_dir)
    logger.info(f"Objective (first 200 chars): {objective[:200]}")

    # ── Run OpenRCA control loop ───────────────────────────────────────────
    try:
        answer, trajectory, _prompt = control_loop(
            objective=objective,
            plan="",
            ap=ap,
            bp=bp,
            logger=logger,
            max_step=20,
            max_turn=5,
        )
        logger.info(f"OpenRCA answer: {str(answer)[:300]}")
    except Exception as e:
        logger.error(f"control_loop error: {e}", exc_info=True)
        _write_stdout({
            "output": json.dumps({"nodes": [], "edges": [], "root_causes": []}),
            "trajectory": [],
        })
        sys.exit(1)

    # ── Convert trajectory to OpenAI format ─────────────────────────────
    openai_trajectory = _convert_trajectory(trajectory)

    # ── Compress findings into full CausalGraph ───────────────────────────
    compress_sp = payload.get("compress_system_prompt", "")
    compress_up = payload.get("compress_user_prompt", "")

    output_json = None
    if compress_sp and compress_up:
        logger.info("Running compress step to generate full CausalGraph...")
        output_json = _compress_findings(
            openai_trajectory, compress_sp, compress_up, question
        )

    # Fallback: root_causes only (no nodes/edges)
    if not output_json:
        logger.warning("Compress step skipped or failed, falling back to root_causes only")
        rc_names = _parse_root_causes(str(answer))
        logger.info(f"Parsed root causes: {rc_names}")
        root_causes = [{"component": rc, "state": []} for rc in rc_names]
        output_json = json.dumps({"nodes": [], "edges": [], "root_causes": root_causes})

    _write_stdout({
        "output": output_json,
        "trajectory": openai_trajectory,
        "usage": _tracker.get_usage(),
    })


if __name__ == "__main__":
    main()
