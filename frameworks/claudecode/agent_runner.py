#!/usr/bin/env python
"""
agent_runner.py — Claude Code (via Aliyun Coding Plan) RCA 评测接口

使用 `claude -p` 作为 agent 框架，通过 Coding Plan 的 Anthropic 兼容端点调用模型。
Claude Code 自带 Bash / Read 等工具，天然支持 DuckDB 查询 parquet 文件。

stdin:  JSON { question, system_prompt, user_prompt,
               compress_system_prompt, compress_user_prompt, data_dir }
stdout: JSON { output (CausalGraph JSON), trajectory (OpenAI 格式), usage }
"""
import json
import os
import re
import subprocess
import sys
import time


# ── 配置 ────────────────────────────────────────────────────────────────────

CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "/home/nn/.vscode-server/extensions/anthropic.claude-code-2.1.96-linux-x64/resources/native-binary/claude")
RCA_MODEL = os.environ.get("RCA_MODEL", "qwen3.5-plus")
CODING_PLAN_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL_OVERRIDE",
    "https://coding.dashscope.aliyuncs.com/apps/anthropic",
)
TIMEOUT = int(os.environ.get("CLAUDE_TIMEOUT", "1800"))
# 预拷贝的干净数据目录（只含白名单 parquet，无答案文件）
CLEAN_DATA_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


# ── 工具函数 ─────────────────────────────────────────────────────────────────

def strip_markdown_json(text: str) -> str:
    """剥离 LLM 返回的 ```json ... ``` 代码块，提取纯 JSON。"""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def _extract_causal_graph_from_markdown(text: str) -> str | None:
    """从 markdown 格式的分析报告中提取 root cause，构建最小合法 CausalGraph JSON。

    当模型输出 markdown 而非 JSON 时作为 fallback。
    """
    # 尝试直接 parse 为 JSON（可能已经是纯 JSON）
    try:
        obj = json.loads(text)
        if "root_causes" in obj or "nodes" in obj:
            return text
    except (json.JSONDecodeError, TypeError):
        pass

    # 从 markdown 提取 root cause 服务名
    root_causes = []
    # Pattern: **ts-xxx-service** or `ts-xxx-service` near "root cause"
    for m in re.finditer(
        r'[Rr]oot\s+[Cc]ause[^{}\n]{0,80}?[\*`]+(ts-[\w-]+|mysql|ts-rabbitmq)[\*`]+',
        text[:3000],
    ):
        svc = m.group(1).strip()
        if svc not in root_causes:
            root_causes.append(svc)

    # Fallback: first bold service name in the text
    if not root_causes:
        m = re.search(r'\*\*(ts-[\w-]+)\*\*', text[:2000])
        if m:
            root_causes.append(m.group(1))

    if not root_causes:
        return None

    # 提取其他被提及的服务名作为 nodes
    all_services = set(root_causes)
    for m in re.finditer(r'(ts-[\w-]+)', text):
        all_services.add(m.group(1))
    # 常见非服务名过滤
    all_services -= {"ts-ui-dashboard"}  # 网关，不是独立故障源

    # 构建 edges：root cause → 其他 nodes
    nodes = []
    edges = []
    for svc in all_services:
        state = ["HIGH_ERROR_RATE"]  # 默认状态
        nodes.append({"component": svc, "state": state})

    for rc in root_causes:
        for svc in all_services:
            if svc != rc:
                edges.append({"source": rc, "target": svc})

    rc_nodes = [{"component": rc, "state": ["HIGH_ERROR_RATE"]} for rc in root_causes]

    graph = {
        "nodes": nodes,
        "edges": edges,
        "root_causes": rc_nodes,
        "component_to_service": {},
    }
    return json.dumps(graph, ensure_ascii=False)


def parse_stream_events(jsonl_path: str):
    """解析 stream-json 事件，构建 trajectory 和提取最终结果。"""
    trajectory = []
    result_text = ""
    usage = {}
    cost_usd = 0.0

    with open(jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")

            if event_type == "assistant":
                msg = event.get("message", {})
                contents = msg.get("content", [])
                for block in contents:
                    block_type = block.get("type", "")

                    if block_type == "tool_use":
                        # assistant 发起 tool call — 保留原始工具名，让意图分类器根据内容判断
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})
                        tool_id = block.get("id", "")
                        args_str = json.dumps(tool_input, ensure_ascii=False)

                        trajectory.append({
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [{
                                "id": tool_id,
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": args_str,
                                },
                            }],
                        })

                    elif block_type == "text":
                        text = block.get("text", "")
                        if text.strip():
                            trajectory.append({
                                "role": "assistant",
                                "content": text,
                            })

                    elif block_type == "thinking":
                        # thinking 内容记录为 assistant（类似 think_tool）
                        thinking = block.get("thinking", "")
                        if thinking.strip():
                            trajectory.append({
                                "role": "assistant",
                                "content": f"[thinking] {thinking}",
                            })

            elif event_type == "user":
                # tool results 以 type=user 事件返回
                msg = event.get("message", {})
                contents = msg.get("content", [])
                for block in contents:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_id = block.get("tool_use_id", "")
                        content = block.get("content", "")
                        if isinstance(content, list):
                            content = "\n".join(
                                b.get("text", "") for b in content
                                if isinstance(b, dict)
                            )
                        trajectory.append({
                            "role": "tool",
                            "content": str(content)[:5000],  # 截断过长结果
                            "tool_call_id": tool_id,
                        })

            elif event_type == "result":
                result_text = event.get("result", "")
                cost_usd = event.get("total_cost_usd", 0.0)
                raw_usage = event.get("usage", {})
                usage = {
                    "total_tokens": (
                        raw_usage.get("input_tokens", 0)
                        + raw_usage.get("cache_creation_input_tokens", 0)
                        + raw_usage.get("cache_read_input_tokens", 0)
                        + raw_usage.get("output_tokens", 0)
                    ),
                    "prompt_tokens": (
                        raw_usage.get("input_tokens", 0)
                        + raw_usage.get("cache_creation_input_tokens", 0)
                        + raw_usage.get("cache_read_input_tokens", 0)
                    ),
                    "completion_tokens": raw_usage.get("output_tokens", 0),
                    "reasoning_tokens": 0,
                    "llm_call_count": event.get("num_turns", 1),
                    "cost_usd": cost_usd,
                }

    return result_text, trajectory, usage


def _compress_to_json(
    result_text: str,
    trajectory: list,
    compress_sp: str,
    compress_up: str,
    usage: dict,
) -> str:
    """用 claude -p 调 LLM，将 markdown 分析结果转换为 CausalGraph JSON。

    与其他 agent 的 compress_research 步骤等价，但通过 Claude Code CLI 执行。
    """
    # 构建 investigation context：trajectory 摘要 + 最终分析
    investigation_summary = []
    for msg in trajectory:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "assistant" and content and not content.startswith("[thinking]"):
            investigation_summary.append(f"[Assistant] {content[:1000]}")
        elif role == "tool":
            investigation_summary.append(f"[Tool Result] {content[:500]}")
    investigation_summary.append(f"\n[Final Analysis]\n{result_text}")
    investigation_context = "\n\n".join(investigation_summary[-30:])

    # 组合 prompt：investigation context + compress_up
    compress_prompt = f"{investigation_context}\n\n---\n\n{compress_up}"

    import anthropic

    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=CODING_PLAN_BASE_URL,
    )

    try:
        print("[ClaudeCode] Compress: calling Anthropic API to extract JSON...", file=sys.stderr)
        resp = client.messages.create(
            model=RCA_MODEL,
            system=compress_sp,
            max_tokens=8000,
            messages=[
                {"role": "user", "content": compress_prompt},
            ],
        )
        raw = ""
        for block in (resp.content or []):
            if getattr(block, "type", "") == "text":
                raw = block.text
                break
        extracted = strip_markdown_json(raw)

        # 累加 usage
        if resp.usage:
            usage["total_tokens"] = usage.get("total_tokens", 0) + resp.usage.input_tokens + resp.usage.output_tokens
            usage["prompt_tokens"] = usage.get("prompt_tokens", 0) + resp.usage.input_tokens
            usage["completion_tokens"] = usage.get("completion_tokens", 0) + resp.usage.output_tokens
            usage["llm_call_count"] = usage.get("llm_call_count", 0) + 1

        obj = json.loads(extracted)
        if "root_causes" in obj or "nodes" in obj:
            print("[ClaudeCode] Compress: success", file=sys.stderr)
            return extracted
        print("[ClaudeCode] Compress: JSON missing required fields", file=sys.stderr)
    except Exception as e:
        print(f"[ClaudeCode] Compress failed: {e}", file=sys.stderr)

    # Compress 失败，fallback regex
    fallback = _extract_causal_graph_from_markdown(result_text)
    if fallback:
        print("[ClaudeCode] Fallback: regex extraction from markdown", file=sys.stderr)
        return fallback
    return result_text


# ── 主流程 ────────────────────────────────────────────────────────────────────

def _strip_tool_instructions(sp: str) -> str:
    """移除 system prompt 中的 <Available Tools> 段落和工具调用指引。

    Claude Code 自带 Bash/Read 工具，不需要 list_tables_in_directory 等自定义工具说明。
    保留其余所有内容（任务描述、数据说明、输出格式、分析指导）以确保公平对比。
    """
    # 移除 <Available Tools>...</Available Tools> 块
    sp = re.sub(r"<Available Tools>.*?</Available Tools>\s*", "", sp, flags=re.DOTALL)
    # 移除引用自定义工具名的行
    sp = re.sub(r".*(?:list_tables_in_directory|get_schema|query_parquet_files|think_tool).*\n?", "", sp)
    # 移除 "Call this FIRST/SECOND" 之类的工具调用顺序指引
    sp = re.sub(r".*Call this (?:FIRST|SECOND).*\n?", "", sp)
    # 清理多余空行
    sp = re.sub(r"\n{3,}", "\n\n", sp)
    return sp.strip()


def _strip_tool_instructions_up(up: str) -> str:
    """移除 user prompt 中的工具调用指引，保留调查策略和输出格式。"""
    # 移除明确引用自定义工具名的行
    up = re.sub(r".*(?:list_tables_in_directory|get_schema|query_parquet_files|think_tool).*\n?", "", up)
    # 移除 "Call `xxx`" 格式的行
    up = re.sub(r"\s*- Call `[^`]+`.*\n?", "", up)
    # 清理多余空行
    up = re.sub(r"\n{3,}", "\n\n", up)
    return up.strip()


def main():
    payload = json.loads(sys.stdin.read())

    # 复用 RolloutRunner 传入的标准 prompt，只移除工具相关段落
    system_prompt = _strip_tool_instructions(payload["system_prompt"])
    user_prompt = _strip_tool_instructions_up(payload["user_prompt"])
    data_dir = payload.get("data_dir", "")

    # 使用预拷贝的干净数据目录（只含白名单 parquet，无答案文件、无 symlink）
    sandbox_dir = ""
    if data_dir:
        # data_dir 形如 .../eval-data/<exp_id>/data_<hash>
        data_hash = os.path.basename(data_dir.rstrip("/"))  # data_xxxxxxxx
        clean_dir = os.path.join(CLEAN_DATA_BASE, data_hash)
        if os.path.isdir(clean_dir):
            sandbox_dir = clean_dir
        else:
            # fallback: 运行时拷贝（新 case 或预拷贝缺失）
            import tempfile, shutil
            sandbox_dir = tempfile.mkdtemp(prefix="rca_sandbox_")
            for fname in [
                "abnormal_logs.parquet", "normal_logs.parquet",
                "abnormal_traces.parquet", "normal_traces.parquet",
                "abnormal_metrics.parquet", "normal_metrics.parquet",
                "abnormal_metrics_histogram.parquet", "normal_metrics_histogram.parquet",
                "abnormal_metrics_sum.parquet", "normal_metrics_sum.parquet",
            ]:
                src = os.path.join(data_dir, fname)
                dst = os.path.join(sandbox_dir, fname)
                if os.path.exists(src):
                    shutil.copy2(src, dst)

        # 替换 prompt 中的原始 data_dir 路径为 sandbox 路径，防止泄漏
        system_prompt = system_prompt.replace(data_dir, sandbox_dir)
        user_prompt = user_prompt.replace(data_dir, sandbox_dir)

        user_prompt += (
            f"\n\n## Data Location\n\n"
            f"The telemetry data for this incident is located at: `{sandbox_dir}`\n"
            f"Use `duckdb` to query the parquet files.\n"
            f"This directory contains exactly 10 parquet files covering logs, traces, and metrics "
            f"(normal and abnormal variants). All your evidence must come from these files.\n"
            f"Do NOT attempt to access any other directories or files."
        )

    # stream-json 输出到临时文件
    stream_file = f"/tmp/claude_rca_{os.getpid()}.jsonl"

    # Bash + Read 开放，禁 Write/Edit（不需要写文件）
    cmd = [
        CLAUDE_BIN, "-p", user_prompt,
        "--model", RCA_MODEL,
        "--system-prompt", system_prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--bare",
        "--no-session-persistence",
        "--dangerously-skip-permissions",
        "--allowedTools", "Bash(*)", "Read(*)",
        "--disallowedTools", "Write(*)", "Edit(*)",
        "--add-dir", sandbox_dir,
    ]

    # 环境变量：Coding Plan endpoint + key
    env = {**os.environ}
    env["ANTHROPIC_BASE_URL"] = CODING_PLAN_BASE_URL
    # ANTHROPIC_API_KEY 从环境继承（运行前 export）

    print(f"[ClaudeCode] Starting: model={RCA_MODEL}, sandbox={sandbox_dir}",
          file=sys.stderr)

    start = time.time()

    with open(stream_file, "w") as out_f:
        proc = subprocess.run(
            cmd,
            stdout=out_f,
            stderr=subprocess.PIPE,
            env=env,
            timeout=TIMEOUT,
            text=True,
        )

    elapsed = time.time() - start
    print(f"[ClaudeCode] Finished in {elapsed:.1f}s, exit={proc.returncode}",
          file=sys.stderr)

    # 清理运行时拷贝的临时沙箱（预拷贝目录不删除）
    if sandbox_dir and sandbox_dir.startswith("/tmp/rca_sandbox_"):
        import shutil
        shutil.rmtree(sandbox_dir, ignore_errors=True)

    if proc.returncode != 0:
        print(f"[ClaudeCode] stderr: {proc.stderr[:2000]}", file=sys.stderr)
        # 尝试解析已有输出
        if not os.path.exists(stream_file) or os.path.getsize(stream_file) == 0:
            sys.exit(1)

    # 解析 stream 事件
    result_text, trajectory, usage = parse_stream_events(stream_file)

    # 清理临时文件
    try:
        os.unlink(stream_file)
    except OSError:
        pass

    if not result_text:
        print("[ClaudeCode] No result text found", file=sys.stderr)
        sys.exit(1)

    # 提取 CausalGraph JSON：优先直接 parse，失败则用 compress LLM 提取
    cleaned = strip_markdown_json(result_text)
    need_compress = False
    try:
        obj = json.loads(cleaned)
        if "root_causes" not in obj and "nodes" not in obj:
            raise ValueError("missing required fields")
        final_output = cleaned
    except (json.JSONDecodeError, ValueError):
        need_compress = True

    if need_compress:
        compress_sp = payload.get("compress_system_prompt", "")
        compress_up = payload.get("compress_user_prompt", "")
        if compress_sp and compress_up:
            final_output = _compress_to_json(
                result_text, trajectory, compress_sp, compress_up, usage,
            )
        else:
            # 无 compress prompt，尝试 regex fallback
            fallback = _extract_causal_graph_from_markdown(result_text)
            if fallback:
                print("[ClaudeCode] Fallback: regex extraction from markdown", file=sys.stderr)
                final_output = fallback
            else:
                print("[ClaudeCode] Failed to extract CausalGraph", file=sys.stderr)
                final_output = cleaned

    output = {
        "output": final_output,
        "trajectory": trajectory,
        "usage": usage,
    }

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
