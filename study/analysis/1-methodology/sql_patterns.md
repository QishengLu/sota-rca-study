# Agent 排障意图全集（troubleshooting intents）

> thinkdepthai + claude-sonnet-4.6, 200 样本, 7335 条查询
> 从人类排障视角重新分类，按 Agent 在做什么分析动作（而非 SQL 语法结构）

## 27 种排障意图（按频次排序，分 7 大类）

### 第一类：发现与枚举 —— "系统里有什么"

| # | 意图 | 次数 | 含义 | SQL 特征 |
|---|------|------|------|---------|
| 1 | **discovery** | 2646 | 发现数据源和 schema | `list_tables`, `get_schema`, `think_tool` |
| 2 | **enumerate_values** | 321 | 列举可用值（服务列表、指标列表、span 列表） | `SELECT DISTINCT metric / service_name / span_name` |
| 3 | **service_metric_discovery** | 184 | 查特定服务有哪些可用指标 | `SELECT DISTINCT metric WHERE service_name=` |
| 4 | **service_endpoint_analysis** | 43 | 查特定服务有哪些 endpoint/span | `DISTINCT span_name WHERE service_name= + COUNT` |

### 第二类：日志分析 —— "发生了什么错误"

| # | 意图 | 次数 | 含义 | SQL 特征 |
|---|------|------|------|---------|
| 5 | **log_stats_overview** | 174 | 各服务各级别的日志数量总览 | `logs GROUP BY service_name, level COUNT(*)` |
| 6 | **error_scan_global** | 154 | 全局错误扫描（不限服务） | `logs WHERE level IN ('ERROR','SEVERE')` 无 service 过滤 |
| 7 | **service_error_log** | 353 | 查特定服务的错误日志 | `logs WHERE service_name= AND level IN (...)` |
| 8 | **service_log_browse** | 166 | 浏览特定服务的全部日志（不限级别） | `logs WHERE service_name= ORDER BY time` |
| 9 | **keyword_search** | 105 | 在日志/span 中搜索关键词 | `message/span_name LIKE '%keyword%'` |

### 第三类：调用链分析 —— "请求怎么流转的"

| # | 意图 | 次数 | 含义 | SQL 特征 |
|---|------|------|------|---------|
| 10 | **trace_call_chain** | 402 | 追踪单次请求的完整调用链 | `traces WHERE trace_id= ORDER BY time` |
| 11 | **call_tree_build** | 5 | 构建调用树（parent→child span 关系） | `JOIN parent_span_id = span_id` |
| 12 | **trace_aggregate** | 45 | 对调用链做聚合分析 | `traces WHERE trace_id= + GROUP BY` |
| 13 | **service_trace_browse** | 186 | 浏览特定服务的 trace 列表 | `traces WHERE service_name= 无 GROUP BY` |

### 第四类：延迟与错误率分析 —— "哪个服务最慢 / 最多错"

| # | 意图 | 次数 | 含义 | SQL 特征 |
|---|------|------|------|---------|
| 14 | **global_latency_ranking** | 297 | 全服务延迟排名 | `traces GROUP BY service_name AVG(duration) ORDER BY desc` |
| 15 | **service_latency_analysis** | 337 | 特定服务延迟细分（按 endpoint） | `traces WHERE service_name= GROUP BY span_name AVG(duration)` |
| 16 | **error_rate_analysis** | 38 | 错误率/状态码分布分析 | `traces GROUP BY + status_code + COUNT` |
| 17 | **global_error_stats** | 19 | 全局 trace 错误统计 | `traces WHERE status_code='Error' COUNT(*)` |

### 第五类：基线对比 —— "跟正常时候比有什么变化"

| # | 意图 | 次数 | 含义 | SQL 特征 |
|---|------|------|------|---------|
| 18 | **baseline_collect** | 460 | 采集正常期数据作为基准 | 仅查 `normal_*` 表 |
| 19 | **baseline_contrast** | 254 | 直接对比正常期 vs 异常期 | `UNION normal_* + abnormal_*` |

### 第六类：资源与基础设施检查 —— "底层有没有问题"

| # | 意图 | 次数 | 含义 | SQL 特征 |
|---|------|------|------|---------|
| 20 | **resource_check** | 395 | 查 CPU/内存/磁盘等 K8s 容器资源指标 | `metrics WHERE metric IN ('container.cpu', 'k8s.pod.memory', ...)` |
| 21 | **jvm_check** | 12 | 查 JVM/GC/线程池/连接池指标 | `metrics WHERE metric LIKE 'jvm.%' / 'queueSize'` |
| 22 | **network_check** | 104 | 查网络/HTTP 层指标（hubble, 丢包, 延迟分布） | `metrics WHERE metric LIKE 'hubble%'` |
| 23 | **k8s_resource_check** | 48 | 查 Pod/Node 级别资源（跨服务对比） | `metrics WHERE attr_k8s_pod_name= / attr_k8s_node_name=` |
| 24 | **cumulative_metric_fetch** | 96 | 查累积指标的具体值（DB连接数、线程池等） | `metrics_sum WHERE service_name= AND metric=` |
| 25 | **cumulative_metric_browse** | 277 | 浏览累积指标表 | `FROM metrics_sum` 混合过滤 |

### 第七类：其他

| # | 意图 | 次数 | 含义 |
|---|------|------|------|
| 26 | **general_exploration** | 190 | 无法归入以上类别的探索性查询 |
| 27 | **metric_value_fetch** | 5 | 查特定服务特定指标的时序原始值 |
| 28 | **global_metric_stats** | 24 | 全局指标统计（不按服务过滤） |

---

## 待讨论：合并与拆分建议

### 1. resource_check (395) vs jvm_check (12) vs network_check (104) — 按排障层面拆还是合？

- **合并理由**：都是"查指标值"，SQL 结构相同，只是 metric 名称不同
- **保留理由**：对应不同排障层面（基础设施 vs 应用 vs 网络），失败模式 D4（信号跨层）说明 Agent 需要切换层面查看
- jvm_check 仅 12 次，可能需要合入其他类

### 2. service_error_log (353) vs service_log_browse (166) — 是否合并为"服务日志查看"？

- 区别仅在于是否有 `level=` 过滤
- **保留理由**：有 level 过滤 = Agent 有明确的"找错误"意图；无过滤 = 泛查/浏览

### 3. cumulative_metric_fetch (96) vs cumulative_metric_browse (277) — 都是查累积指标

- browse 占比大，但很多可能是 fetch 的变体（只是 WHERE 条件不同）
- 可能合并为一个 `cumulative_metric_check`

### 4. enumerate_values (321) vs service_metric_discovery (184) vs service_endpoint_analysis (43)

- 都是"发现有什么可用的"
- **区别**：发现什么类型的信息（通用值 / 指标列表 / endpoint 列表）
- 可能合为 `discovery_enumerate`，或保留分开

### 5. trace_call_chain (402) vs trace_aggregate (45) vs service_trace_browse (186)

- call_chain: 看一条 trace 完整流转（最典型的排障动作）
- aggregate: 多条 trace 聚合统计（定量分析）
- browse: 看某服务的 trace 列表（扫描式）
- 三者排障目的不同，建议保留分开

### 6. general_exploration (190) 过大

- 需要检查具体内容，可能包含了误分类的查询
- 可能拆分出"指标值读取"或"多条件混合过滤"等子类
