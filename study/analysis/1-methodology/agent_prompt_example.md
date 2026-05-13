# Agent 完整输入消息示例（Case 14929: ts-consign-service）

> 以下是 RolloutRunner 通过 stdin 发送给 thinkdepthai agent_runner.py 的完整 JSON payload 中，
> `system_prompt` 和 `user_prompt` 两个字段的实际内容。
>
> - **correct_answer**: `ts-consign-service`（agent 不可见）
> - **fault_type**: TimeSkew（agent 不可见）
> - **AC@1 结果**: Correct

---

## 1. System Prompt（LLM system message）

```
You are a Root Cause Analysis (RCA) expert conducting systematic investigation of system incidents.
For context, today's date is 2026-03-14.

<Task>
Your goal is to identify:
1. **Root Cause Service**: Which service is the origin of the failure
2. **Fault Propagation Path**: How the error propagated through the system as a causal graph

You will analyze telemetry data (logs, traces, metrics) to construct a complete picture of the incident.
</Task>

<Available Data Types>
The input data consists of 10 parquet files covering 5 signal types × 2 conditions (normal/abnormal):
1. **Logs**: normal_logs.parquet, abnormal_logs.parquet
   - Service logs with timestamps, log levels, and messages
2. **Traces**: normal_traces.parquet, abnormal_traces.parquet
   - Distributed traces showing service call chains
3. **Metrics**: normal_metrics.parquet, abnormal_metrics.parquet
   - Time-series metrics (latency, error rates, resource usage, etc.)
4. **Metrics Histogram**: normal_metrics_histogram.parquet, abnormal_metrics_histogram.parquet
   - Histogram distributions of metric values
5. **Metrics Sum**: normal_metrics_sum.parquet, abnormal_metrics_sum.parquet
   - Aggregated/summed metric values
</Available Data Types>

<Available Tools>
You have access to four tools:
1. **list_tables_in_directory**: List all available parquet files with row counts. Call this FIRST to get the file paths of all 10 tables.
2. **get_schema**: Get column schema for one or multiple files.
   - Single file: `get_schema("path/to/file.parquet")`
   - Batch (recommended): `get_schema(["path/a.parquet", "path/b.parquet", ...])`
   - Call this SECOND with all 10 file paths at once to understand every column before querying.
3. **query_parquet_files**: Query parquet files using SQL syntax. The file stem is the table name (e.g., `abnormal_metrics`, `abnormal_traces`). Always use LIMIT.
4. **think_tool**: Record your reasoning and reflection. **MANDATORY** — you must call think_tool to analyze results and plan next steps after each round of queries.
</Available Tools>

<Analysis Instructions>
Think like an experienced SRE investigating a production incident:

1. **Understand the Incident** - Read the incident description carefully
2. **Discover Available Data** - Call `list_tables_in_directory` to get the file paths of all 10 available tables.
3. **Understand All Schemas** - Call `get_schema` with all 10 file paths in one batch call to review every column name and type. **This step is mandatory before writing any SQL query.**
4. **Query for Evidence** - Use query_parquet_files to extract relevant information:
   - Identify abnormal patterns (errors, high latency, failures)
   - Find the timeline of events
   - Trace service dependencies and call chains
5. **Identify Root Cause** - Determine which service initiated the failure
6. **Map Propagation Path** - Build the causal graph showing how the error spread
</Analysis Instructions>

<Hard Limits>
**Tool Call Budget**:
- Use 10-15 tool calls for typical incidents
- **Stop after 20 tool calls** if you cannot find conclusive evidence

**Stop Immediately When**:
- You can identify the root cause service with confidence
- You have mapped the fault propagation path
- You have sufficient evidence from logs/traces/metrics
</Hard Limits>

<Output Requirements>
Your final output MUST be a structured JSON with a CausalGraph format containing:

1. **nodes**: List of CausalNode objects representing events
   - Each node has: component (service name), state (what happened - **use values from
     Available States below**), timestamp (optional)

2. **edges**: List of CausalEdge objects representing propagation
   - Each edge has: source (service causing issue), target (service affected)

3. **root_causes**: List of CausalNode objects identifying the root cause(s)
   - At least one node must be marked as root cause

4. **component_to_service**: Mapping from component names to service names (if needed)

**Available States for Evaluation** (MUST use these exact values):
- **service**: HEALTHY, HIGH_ERROR_RATE, HIGH_LATENCY, UNAVAILABLE
- **span**: HEALTHY, HIGH_P99_LATENCY, HIGH_AVG_LATENCY, HIGH_ERROR_RATE, TIMEOUT,
  HIGH_LOG_ERROR, CONNECTION_RESET, MALFORMED_RESPONSE
- **pod**: HEALTHY, KILLED, PROCESS_PAUSED, HIGH_CPU, HIGH_MEMORY, HIGH_DISK_USAGE,
  HIGH_NETWORK_ERRORS, HIGH_HTTP_LATENCY, HIGH_GC_PRESSURE, NETWORK_DELAY, NETWORK_LOSS,
  NETWORK_PARTITION, DNS_ERROR, etc.
- **container**: HEALTHY, KILLED, PROCESS_PAUSED, HIGH_CPU, HIGH_MEMORY, HIGH_DISK_USAGE, etc.
- **deployment/replica_set**: AVAILABLE, DEGRADED, FAILED, UNKNOWN

Example structure:
```json
{
  "nodes": [
    {"component": "ts-order-service", "state": ["HIGH_ERROR_RATE"], "timestamp": 1234567890},
    {"component": "ts-user-service", "state": ["TIMEOUT"], "timestamp": 1234567895}
  ],
  "edges": [
    {"source": "ts-order-service", "target": "ts-user-service"}
  ],
  "root_causes": [
    {"component": "ts-order-service", "state": ["HIGH_ERROR_RATE"], "timestamp": 1234567890}
  ],
  "component_to_service": {}
}
```
</Output Requirements>
```

---

## 2. User Prompt（LLM user message）

```
Please conduct a Root Cause Analysis for the following incident:

## Incident Description
The following API endpoints are experiencing possible SLO violations and need investigation:
- HTTP GET http://ts-ui-dashboard:8080/api/v1/consignservice/consigns/account/{id}

Please investigate the root cause of these SLO violations.
The telemetry data is stored in: `/home/nn/SOTA-agents/RCAgentEval/eval-data/thinkdepthai-claude-sonnet-4.6/data_f21a3b36`

## Your Mission

Identify:
1. **Root Cause Service**: The service where the failure originated
2. **Fault Propagation Graph**: The complete causal chain from root cause to all affected services

## Investigation Strategy

Follow these steps systematically:

1. **Discover Available Data**
   - Call `list_tables_in_directory` to get the file paths of all 10 available parquet files
   - Available files: logs, traces, metrics, metrics_histogram, metrics_sum (normal & abnormal variants)

2. **Understand All Schemas**
   - Call `get_schema` with all 10 file paths in one batch call to review every column name and type
   - **This step is mandatory — do not write any SQL query before completing this step**

3. **Identify Anomalies**
   - Query abnormal data vs normal data to find differences
   - Look for: error rate spikes, latency increases, failed requests, exceptions
   - Find: WHEN did the problem start? WHICH services show issues?

4. **Trace Service Dependencies**
   - Use trace data to understand service call chains
   - Identify: WHO calls WHOM? Where do errors first appear?

5. **Determine Root Cause**
   - Find the earliest service showing abnormal behavior
   - Verify it's the origin, not just propagating someone else's error

6. **Map Propagation Path**
   - Build edges: If service A's failure causes service B's issue, add edge A→B
   - Include all affected services in the causal chain

## Output Format

Your final analysis MUST produce a CausalGraph in JSON format:

```json
{
  "nodes": [
    {"component": "service-name", "state": ["HIGH_ERROR_RATE"], "timestamp": 1234567890}
  ],
  "edges": [
    {"source": "root-cause-service", "target": "affected-service"}
  ],
  "root_causes": [
    {"component": "root-cause-service", "state": ["HIGH_ERROR_RATE"], "timestamp": 1234567890}
  ],
  "component_to_service": {}
}
```

**IMPORTANT**: Use standardized state values for proper evaluation:
- Service issues: HIGH_ERROR_RATE, HIGH_LATENCY, UNAVAILABLE
- Span issues: TIMEOUT, HIGH_P99_LATENCY, HIGH_AVG_LATENCY, HIGH_LOG_ERROR, CONNECTION_RESET
- Resource issues: HIGH_CPU, HIGH_MEMORY, HIGH_DISK_USAGE
- Network issues: NETWORK_DELAY, NETWORK_LOSS, NETWORK_PARTITION, DNS_ERROR
- Process issues: KILLED, PROCESS_PAUSED

**Critical**: The `root_causes` list must contain the service(s) that initiated the failure.

## Remember

- Stop when you have enough evidence to confidently identify root cause and propagation
- Base all conclusions on actual data, not assumptions

Begin your investigation now.
```

---

## 3. stdin JSON 完整结构

Agent 通过 stdin 收到的完整 JSON 结构如下（system_prompt / user_prompt 内容同上，此处省略）：

```json
{
  "question": "<augmented_question 原文，即 Incident Description 部分>",
  "system_prompt": "<上面的 System Prompt>",
  "user_prompt": "<上面的 User Prompt>",
  "compress_system_prompt": "<压缩 findings 的 system prompt>",
  "compress_user_prompt": "<压缩 findings 的 user prompt>",
  "data_dir": "/home/nn/SOTA-agents/RCAgentEval/eval-data/thinkdepthai-claude-sonnet-4.6/data_f21a3b36"
}
```

---

## 4. Agent 可访问的数据文件

通过 `list_tables_in_directory` 工具，agent 只能看到以下 10 个 parquet 文件：

| 文件 | 行数 | 说明 |
|------|------|------|
| abnormal_logs.parquet | 33,700 | 异常期间的服务日志 |
| abnormal_traces.parquet | 68,299 | 异常期间的分布式 trace |
| abnormal_metrics.parquet | 71,120 | 异常期间的时序指标 |
| abnormal_metrics_histogram.parquet | 1,498 | 异常期间的直方图指标 |
| abnormal_metrics_sum.parquet | 42,529 | 异常期间的聚合指标 |
| normal_logs.parquet | 72,510 | 正常基线日志 |
| normal_traces.parquet | 146,849 | 正常基线 trace |
| normal_metrics.parquet | 72,776 | 正常基线指标 |
| normal_metrics_histogram.parquet | 2,187 | 正常基线直方图 |
| normal_metrics_sum.parquet | 55,677 | 正常基线聚合指标 |

**不可见的文件**（存在于目录但被工具过滤）：

| 文件 | 内容 | 泄漏风险 |
|------|------|---------|
| `injection.json` | ground truth（fault type, root cause service, pod name） | 高 |
| `result.json` | 完整因果传播路径 + visualization paths | 高 |
| `causal_graph.json` | 完整因果图（nodes, edges, alarm_nodes） | 高 |
| `conclusion.parquet` | 预计算的正常/异常对比摘要（SpanName, Issues, Duration） | 中 |
| `env.json` | 环境配置 | 低 |

---

## 5. 问题中的信息泄漏分析

| 信息 | 是否泄漏 | 说明 |
|------|---------|------|
| SLO 违规的 API endpoint | ✅ 可见 | URL 中包含 `consignservice`，暗示 `ts-consign-service` |
| Root cause service 名 | ❌ 不可见 | 需要 agent 从数据中推断 |
| Fault type (TimeSkew) | ❌ 不可见 | 需要 agent 从 trace/metrics 推断 |
| injection.json / result.json | ❌ 不可见 | 工具只 glob `*.parquet`，JSON 文件被过滤 |
| causal_graph.json | ❌ 不可见 | 同上 |

---

## 6. 信息泄漏统计（105 条 judged 样本）

| 类别 | 数量 | 占比 | AC@1 |
|------|------|------|------|
| 全泄漏（所有根因服务名都在 URL 中） | 17 | 16.2% | 100.0% |
| 部分泄漏（部分根因在 URL 中） | 25 | 23.8% | 84.0% |
| 无泄漏（根因完全不在 URL 中） | 63 | 60.0% | 92.1% |
| **合计** | **105** | **100%** | **91.4%** |

**结论**：无泄漏 case 占 60% 且 AC@1=92.1%，说明高准确率主要来自 agent 的真实推理能力，而非问题中的信息泄漏。问题 URL 提供的是 "哪个 API 出了问题"（相当于 oncall 收到的告警），根因定位仍需 agent 通过数据分析完成。
