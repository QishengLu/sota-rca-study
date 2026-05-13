#!/usr/bin/env python
"""
一次性脚本：对 DB 中 29 个 markdown 格式 response 的 case，
用 claude -p + compress prompt 提取 CausalGraph JSON，更新 DB 后等待 rejudge。
"""
import json
import os
import re
import subprocess
import sys
import datetime

os.environ.setdefault("UTU_DB_URL", "postgresql://postgres:postgres@localhost:5433/SOTA-Agents")

from sqlalchemy import create_engine, text

# 复用 agent_runner 的配置和函数
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "/home/nn/.vscode-server/extensions/anthropic.claude-code-2.1.96-linux-x64/resources/native-binary/claude")
RCA_MODEL = os.environ.get("RCA_MODEL", "qwen3.5-plus")
CODING_PLAN_BASE_URL = "https://coding.dashscope.aliyuncs.com/apps/anthropic"

# compress prompt（从 rca.yaml 提取，date 已填充）
TODAY = datetime.date.today().isoformat()

COMPRESS_SP = f"""You are an expert Root Cause Analysis synthesizer.
Your task is to convert investigation findings into structured CausalGraph JSON format.
For context, today's date is {TODAY}."""

COMPRESS_UP = f"""You are an RCA expert who has conducted a thorough investigation of a system incident.
Your job is now to synthesize all findings into a structured CausalGraph JSON format.
For context, today's date is {TODAY}.

<Task>
You need to transform all investigation findings into a structured CausalGraph that shows:
1. **Root Cause**: Which service(s) initiated the failure
2. **Propagation Path**: How the fault spread through the system (as a directed graph)
3. **All Affected Services**: Complete list of impacted services

The output MUST be valid JSON that can be parsed programmatically.
</Task>

<Output Requirements>
You MUST output ONLY a valid JSON object in the following CausalGraph format:

```json
{{
  "nodes": [
    {{"component": "service-name", "state": ["HIGH_ERROR_RATE"], "timestamp": 1234567890}}
  ],
  "edges": [
    {{"source": "source-service", "target": "target-service"}}
  ],
  "root_causes": [
    {{"component": "root-cause-service", "state": ["HIGH_ERROR_RATE"], "timestamp": 1234567890}}
  ],
  "component_to_service": {{}}
}}
```

**Available States**: HIGH_ERROR_RATE, HIGH_LATENCY, UNAVAILABLE, TIMEOUT, HIGH_P99_LATENCY,
HIGH_AVG_LATENCY, HIGH_CPU, HIGH_MEMORY, KILLED, PROCESS_PAUSED, NETWORK_DELAY, NETWORK_LOSS,
NETWORK_PARTITION, DNS_ERROR, CONNECTION_RESET, MALFORMED_RESPONSE, HIGH_LOG_ERROR

</Output Requirements>

<Critical Rules>
- Output ONLY the JSON object, no markdown, no explanations
- The `root_causes` field is MANDATORY
- Service names must match those in the investigation data
</Critical Rules>

Based on ALL the investigation messages above, output the CausalGraph JSON NOW:"""


def strip_markdown_json(t: str) -> str:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.DOTALL)
    return m.group(1).strip() if m else t.strip()


def parse_stream_result(jsonl_path: str) -> str:
    """只提取 result text。"""
    result = ""
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "result":
                result = ev.get("result", "")
    return result


def compress_one(markdown_response: str, trajectories_json: str | None) -> tuple[str | None, dict | None]:
    """用 Anthropic SDK + Coding Plan 端点将 markdown 转为 CausalGraph JSON。

    返回 (graph_json, compress_usage) 或 (None, None)。
    """
    import anthropic

    # 构建 investigation context
    parts = []
    if trajectories_json:
        try:
            traj = json.loads(trajectories_json)
            for msg in traj[-30:]:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "assistant" and content and not content.startswith("[thinking]"):
                    parts.append(f"[Assistant] {content[:1000]}")
                elif role == "tool":
                    parts.append(f"[Tool Result] {content[:500]}")
        except (json.JSONDecodeError, TypeError):
            pass
    parts.append(f"\n[Final Analysis]\n{markdown_response}")
    context = "\n\n".join(parts)

    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=CODING_PLAN_BASE_URL,
    )

    try:
        resp = client.messages.create(
            model=RCA_MODEL,
            system=COMPRESS_SP,
            max_tokens=8000,
            messages=[
                {"role": "user", "content": context + "\n\n---\n\n" + COMPRESS_UP},
            ],
        )
        raw = ""
        for block in (resp.content or []):
            if getattr(block, "type", "") == "text":
                raw = block.text
                break
        extracted = strip_markdown_json(raw)
        obj = json.loads(extracted)

        compress_usage = None
        if resp.usage:
            compress_usage = {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
            }

        if "root_causes" in obj or "nodes" in obj:
            return extracted, compress_usage
    except Exception as e:
        print(f"  compress error: {e}", file=sys.stderr)
    return None, None


def main():
    dry_run = "--dry-run" in sys.argv
    engine = create_engine(os.environ["UTU_DB_URL"])

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, dataset_index, response::text, trajectories::text, meta::text
            FROM evaluation_data
            WHERE exp_id = 'claudecode-qwen3.5-plus' AND stage = 'judged'
              AND reasoning = 'Failed to parse CausalGraph'
        """)).fetchall()

    print(f"Found {len(rows)} markdown cases to compress")
    if dry_run:
        print("(dry-run mode, not updating DB)")

    success = 0
    failed = 0

    for i, r in enumerate(rows):
        rid, idx, resp, traj, meta_str = r
        print(f"[{i+1}/{len(rows)}] id={rid} idx={idx} ...", end=" ", flush=True)

        graph_json, compress_usage = compress_one(resp, traj)
        if graph_json:
            # 累加 compress usage 到 meta.cost_metrics
            meta = json.loads(meta_str) if meta_str else {}
            cost = meta.get("cost_metrics", {})
            if compress_usage and cost:
                cost["total_tokens"] = cost.get("total_tokens", 0) + compress_usage["total_tokens"]
                cost["prompt_tokens"] = cost.get("prompt_tokens", 0) + compress_usage["input_tokens"]
                cost["completion_tokens"] = cost.get("completion_tokens", 0) + compress_usage["output_tokens"]
                cost["llm_call_count"] = cost.get("llm_call_count", 0) + 1
                meta["cost_metrics"] = cost

            print(f"OK (compress +{compress_usage['total_tokens']}tok)" if compress_usage else "OK")
            success += 1
            if not dry_run:
                with engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE evaluation_data
                        SET response = :resp,
                            meta = :meta,
                            extracted_final_answer = NULL,
                            judged_response = NULL,
                            reasoning = NULL,
                            correct = NULL,
                            confidence = NULL,
                            stage = 'rollout'
                        WHERE id = :id
                    """), {"resp": graph_json, "meta": json.dumps(meta, ensure_ascii=False), "id": rid})
        else:
            print(f"FAILED")
            failed += 1

    print(f"\nDone: {success} compressed, {failed} failed")
    if not dry_run and success > 0:
        print(f"Run rejudge: cd /home/nn/SOTA-agents/RCAgentEval && uv run python scripts/rejudge_samples.py --exp_id claudecode-qwen3.5-plus")


if __name__ == "__main__":
    main()
