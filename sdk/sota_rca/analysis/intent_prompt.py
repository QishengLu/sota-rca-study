"""Prompt templates for LLM-based intent classification of agent trajectories.

19 troubleshooting intent categories for classifying SQL queries from RCA agent traces.
"""

VALID_INTENTS = [
    "latency_ranking",
    "throughput_compare",
    "error_rate_scan",
    "service_trace_scan",
    "trace_follow",
    "call_tree_build",
    "error_log_overview",
    "service_error_log",
    "service_log_browse",
    "keyword_search",
    "error_timeline",
    "metric_scan",
    "container_resource",
    "jvm_state",
    "network_layer",
    "k8s_state",
    "db_state",
    "baseline_collect",
    "baseline_contrast",
]

SYSTEM_PROMPT = """\
Classify each SQL query into one of the intents below. Pick the closest match.

## Intents

Traces:
- latency_ranking: Global latency overview across all services (GROUP BY service, AVG/MAX duration)
- throughput_compare: Global request volume comparison (GROUP BY service, COUNT)
- error_rate_scan: Global error distribution (GROUP BY service, status_code / error count)
- service_trace_scan: Examine a specific service's traces — spans, duration, status, endpoints
  (WHERE service = X, or LIKE '%service_name%' on traces)
- trace_follow: Follow one request by trace_id on a TRACES table (WHERE trace_id = X).
  If the same trace_id filter is on a logs table instead, use service_log_browse.
- call_tree_build: STRICT — requires a SELF-JOIN of traces with parent_span_id = span_id.
  DO NOT use this label for queries that merely SELECT DISTINCT service_name or select span_name
  from one trace; those are service_trace_scan (with WHERE service) or trace_follow (with WHERE trace_id).

Logs:
- error_log_overview: Global log scan across services (GROUP BY service, level)
- service_error_log: Specific service's error logs (WHERE service = X AND level = ERROR/WARN)
- service_log_browse: Browse a service's logs without level filter (WHERE service = X).
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

## Tie-break rules (when multiple intents seem to match)

1. Structural signal wins: JOIN parent_span_id=span_id → call_tree_build overrides other trace intents
2. Table exclusivity beats predicate: normal_* ONLY → baseline_collect;
   both normal_* AND abnormal_* → baseline_contrast
3. ID-level scope beats service-level: trace_id= on traces → trace_follow beats service_trace_scan
4. Level filter beats bare service filter in logs:
   service_name + level → service_error_log beats service_log_browse
5. Text search on message/span_name beats generic service scan: LIKE '%timeout%' → keyword_search
6. Specific metric domain beats metric_scan: if any CPU/MEM/JVM/K8S/DB/NETWORK keyword is visible,
   pick that domain; metric_scan is only for pure DISTINCT-metric exploration

## Output format (STRICT)

Return a COMPACT JSON array. Each entry has EXACTLY 3 fields:
  {"round": <int>, "sql_index": <int>, "intent": "<one of the 19 intents>"}

NO "reasoning" field. NO "data_type" field. NO markdown code fences. NO prose before or after.
NO indentation or pretty-printing — single line preferred to save tokens.

## Rules

1. One intent per SQL. If a round has N SQL queries, return N entries.
2. Use ONLY the intent names listed above.
3. Output ONLY the JSON array.
"""

FEW_SHOT_USER = """\
Round 4 (2 SQL):
```sql
-- SQL 1
SELECT service_name, COUNT(*), AVG(duration), SUM(CASE WHEN attr_status_code='ERROR' THEN 1 ELSE 0 END) as errors
FROM abnormal_traces GROUP BY service_name ORDER BY errors DESC
-- SQL 2
SELECT service_name, level, COUNT(*) FROM abnormal_logs GROUP BY service_name, level
```

Round 6 (2 SQL):
```sql
-- SQL 1
SELECT time, message FROM abnormal_logs
WHERE service_name = 'ts-order-service' AND level IN ('ERROR','SEVERE')
-- SQL 2
SELECT DISTINCT service_name FROM abnormal_traces
```

Round 8 (1 SQL):
```sql
-- SQL 1
SELECT * FROM abnormal_traces WHERE trace_id = 'abc123' ORDER BY time
```

Round 10 (2 SQL):
```sql
-- SQL 1
SELECT t1.service_name as caller, t2.service_name as callee
FROM normal_traces t1 JOIN normal_traces t2 ON t1.span_id = t2.parent_span_id
-- SQL 2
SELECT time, value FROM abnormal_metrics WHERE metric = 'container.cpu.usage' AND service_name = 'ts-order-service'
```

Round 12 (2 SQL):
```sql
-- SQL 1
SELECT 'normal' as period, AVG(duration) FROM normal_traces WHERE service_name = 'ts-order-service'
UNION ALL
SELECT 'abnormal', AVG(duration) FROM abnormal_traces WHERE service_name = 'ts-order-service'
-- SQL 2
SELECT time, level, message FROM abnormal_logs WHERE service_name = 'ts-order-service' ORDER BY time
```
"""

FEW_SHOT_ASSISTANT = """\
[{"round":4,"sql_index":1,"intent":"error_rate_scan"},{"round":4,"sql_index":2,"intent":"error_log_overview"},{"round":6,"sql_index":1,"intent":"service_error_log"},{"round":6,"sql_index":2,"intent":"latency_ranking"},{"round":8,"sql_index":1,"intent":"trace_follow"},{"round":10,"sql_index":1,"intent":"call_tree_build"},{"round":10,"sql_index":2,"intent":"container_resource"},{"round":12,"sql_index":1,"intent":"baseline_contrast"},{"round":12,"sql_index":2,"intent":"service_log_browse"}]\
"""

USER_TEMPLATE = """\
{rounds_text}\
"""
