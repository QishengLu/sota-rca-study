# CLAUDE.md — ClaudeCode Agent

Claude Code CLI 作为 RCA agent 框架，通过 Aliyun Coding Plan 的 Anthropic 兼容端点调用 qwen3.5-plus 模型。

---

## 架构设计

```
RolloutRunner
  │  stdin: {question, system_prompt, user_prompt, compress_sp, compress_up, data_dir}
  ▼
agent_runner.py
  │
  ├── 1. Prompt 准备
  │     ├── _strip_tool_instructions(sp)  → 移除 <Available Tools> 段、自定义工具名
  │     └── _strip_tool_instructions_up(up) → 移除工具调用指引行
  │
  ├── 2. 沙箱隔离
  │     └── 创建 tmpdir，只软链接 10 个白名单 parquet 文件（隔离答案文件）
  │
  ├── 3. 调查阶段（claude -p）
  │     ├── claude -p <user_prompt> --model qwen3.5-plus
  │     ├── --allowedTools Bash(*) Read(*)    ← 天然支持 DuckDB 查询
  │     ├── --disallowedTools Write(*) Edit(*)
  │     ├── --output-format stream-json --verbose
  │     └── 输出 → /tmp/claude_rca_<pid>.jsonl
  │
  ├── 4. Stream 解析（parse_stream_events）
  │     ├── assistant → tool_use / text / thinking → trajectory
  │     ├── user → tool_result → trajectory
  │     └── result → result_text + usage（含 cache tokens）
  │
  ├── 5. 输出提取（三层防御）
  │     ├── L1: strip_markdown_json → json.loads → 有 root_causes? → 直接用
  │     ├── L2: _compress_to_json → Anthropic SDK 调 Coding Plan → compress prompt 提取 JSON
  │     └── L3: _extract_causal_graph_from_markdown → regex 提取 root cause → 构建最小 CausalGraph
  │
  └── stdout: {"output": "<CausalGraph JSON>", "trajectory": [...], "usage": {...}}
```

### 与其他 Agent 的关键区别

| 维度 | 其他 Agent（LangGraph 等） | ClaudeCode |
|------|--------------------------|------------|
| 框架 | Python SDK (LangGraph/litellm/etc.) | Claude Code CLI (`claude -p`) |
| 工具 | 自定义 `query_parquet_files` 等 | 原生 Bash + Read（DuckDB 查询） |
| Prompt 处理 | 原样使用共享 prompt | 移除 `<Available Tools>` 段和工具引用行 |
| Usage 采集 | UsageTracker monkey-patch OpenAI SDK | stream-json `result` 事件中的 usage 字段 |
| 输出格式 | 框架内 compress_research 节点 | 后处理三层提取（直接 parse → compress → regex） |
| API 端点 | shubiaobiao OpenAI 代理 | Aliyun Coding Plan Anthropic 兼容端点 |
| 认证方式 | OPENAI_API_KEY 环境变量 | ANTHROPIC_API_KEY 环境变量（运行时传入） |

---

## 文件说明

| 文件 | 作用 |
|------|------|
| `agent_runner.py` | 主入口，遵循标准 stdin/stdout 接口 |
| `backfill_compress.py` | 一次性脚本：对 DB 中 markdown 格式 response 的 case 用 compress 提取 JSON |

---

## 配置

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ANTHROPIC_API_KEY` | （必须） | Coding Plan API key，运行时传入 |
| `CLAUDE_BIN` | VSCode 扩展内的 claude 二进制 | Claude Code CLI 路径 |
| `RCA_MODEL` | `qwen3.5-plus` | 模型名（Coding Plan 端点） |
| `CLAUDE_TIMEOUT` | `1800` | 单样本超时（秒） |
| `COMPRESS_MODEL` | 同 `RCA_MODEL` | compress 阶段使用的模型 |

### RolloutRunner 配置

```yaml
# RolloutRunner/configs/agents/claudecode.yaml
name: claudecode
cmd: ["python3", "/home/nn/SOTA-agents/ClaudeCode/agent_runner.py"]
cwd: /home/nn/SOTA-agents/ClaudeCode
exp_id: claudecode-qwen3.5-plus
model_name: qwen3.5-plus
agent_type: claudecode
concurrency: 5
timeout: 1800
data_dir: /home/nn/SOTA-agents/RolloutRunner/data
```

---

## 运行方式

```bash
# 单样本冒烟测试
cd /home/nn/SOTA-agents/RolloutRunner
ANTHROPIC_API_KEY=xxx uv run python scripts/run_rollout.py \
  --agent claudecode --source_exp_id claudecode-qwen3.5-plus --limit 1

# 全量 rollout
ANTHROPIC_API_KEY=xxx uv run python scripts/run_rollout.py \
  --agent claudecode --source_exp_id claudecode-qwen3.5-plus

# Rejudge
cd /home/nn/SOTA-agents/RCAgentEval
UTU_DB_URL="postgresql://postgres:postgres@localhost:5433/SOTA-Agents" \
  uv run python scripts/rejudge_samples.py --exp_id claudecode-qwen3.5-plus

# Backfill compress（对已有 markdown response 的 case）
ANTHROPIC_API_KEY=xxx python3 /home/nn/SOTA-agents/ClaudeCode/backfill_compress.py
```

---

## 输出格式三层提取（核心设计）

qwen3.5 通过 Claude Code 框架输出时，`result` 字段可能是 markdown 分析报告而非要求的 JSON。
三层防御确保最终输出为合法 CausalGraph JSON：

### L1: 直接解析

```
strip_markdown_json(result_text) → json.loads → 检查 root_causes/nodes 字段
```

成功率约 83%（143/173 case 直接输出 JSON）。

### L2: Compress LLM 提取

当 L1 失败时，用 Anthropic SDK 调 Coding Plan（同模型 qwen3.5-plus）重新提取：

```python
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], base_url=CODING_PLAN_BASE_URL)
resp = client.messages.create(model=RCA_MODEL, system=compress_sp, messages=[...])
```

- 输入：trajectory 摘要（最近 30 条）+ 最终 markdown 分析 + compress_up prompt
- 输出：纯 CausalGraph JSON
- Usage 累加到主流程的 usage 中
- 注意：qwen3.5 会返回 ThinkingBlock，需遍历 `resp.content` 取 `type=="text"` 的 block

### L3: Regex Fallback

当 L2 也失败时，从 markdown 中 regex 提取 root cause 服务名，构建最小 CausalGraph：

```
正则匹配 "Root Cause" 附近的 **ts-xxx-service** 或 `ts-xxx-service`
→ 构建 {nodes, edges, root_causes, component_to_service}
```

---

## 已知坑

1. **Claude Code 需要登录**：`claude -p` 需要已认证的 session，compress 阶段改用 Anthropic SDK 直接调 API
2. **stream-json 需 --verbose**：`--output-format stream-json` 必须搭配 `--verbose`，否则报错
3. **ThinkingBlock**：qwen3.5 通过 Coding Plan 会返回 ThinkingBlock，`resp.content[0].text` 会报错，需遍历找 `type=="text"` 的 block
4. **429 限流**：Coding Plan 有小时配额限制，限流时 agent 返回 `API Error: 429`，runner.py 会将其写入 DB 导致 stage=rollout 无法重跑 → 建议控制并发
5. **Prompt 过滤**：移除 `<Available Tools>` 整个段落和工具名引用行，但保留输出格式要求和分析指导

---

## 评测结果

| exp_id | 模型 | judged | correct | AC@1 | 备注 |
|--------|------|--------|---------|------|------|
| claudecode-qwen3.5-plus | qwen3.5-plus | 173 | 156 | 90.2% | 327 个 init 待重跑（101 个 429 限流回退 + 226 个原始未跑） |
