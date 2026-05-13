# Parquet 数据表格式说明

本文档描述 RCAgentEval 中每个数据包（datapack）包含的 10 张 Parquet 表 + 1 张 Conclusion 表的完整 schema、含义、使用方法，以及故障排查的标准 SOP。

---

## 数据包结构

每个数据包对应一次故障注入实验，目录下包含：

```
data_XXXXXXXX/
├── abnormal_logs.parquet           # 异常时段的服务日志
├── abnormal_traces.parquet         # 异常时段的分布式追踪 span
├── abnormal_metrics.parquet        # 异常时段的 Gauge 型指标
├── abnormal_metrics_histogram.parquet  # 异常时段的 Histogram 型指标
├── abnormal_metrics_sum.parquet    # 异常时段的 Sum/Counter 型指标
├── normal_logs.parquet             # 正常时段的服务日志
├── normal_traces.parquet           # 正常时段的分布式追踪 span
├── normal_metrics.parquet          # 正常时段的 Gauge 型指标
├── normal_metrics_histogram.parquet    # 正常时段的 Histogram 型指标
├── normal_metrics_sum.parquet      # 正常时段的 Sum/Counter 型指标
├── conclusion.parquet              # API 级 SLO 对比摘要（预计算）
├── env.json                        # 时间窗口和命名空间
├── injection.json                  # 故障注入详情和 ground truth
└── causal_graph.json               # 因果图 ground truth
```

**核心分组**: 10 张数据表按 `normal_` / `abnormal_` 前缀分为两组，schema 完全相同。`normal_` 是故障注入前的健康基线，`abnormal_` 是故障注入期间的数据。两组时间窗口由 `env.json` 定义（各约 4 分钟）。

---

## 一、Traces（追踪）

### abnormal_traces.parquet / normal_traces.parquet

**用途**: 记录每个 HTTP 请求在微服务间的调用链。每一行是一个 **span**（一次函数调用/RPC），通过 `trace_id` 串联成完整调用链，通过 `parent_span_id` 构建调用树。

**典型规模**: normal ~100K-200K 行，abnormal ~5K-30K 行

| 列名 | 类型 | 说明 |
|------|------|------|
| `time` | timestamp[ns, UTC] | span 开始时间 |
| `trace_id` | string | 全局唯一的追踪 ID，同一个用户请求的所有 span 共享此 ID |
| `span_id` | string | 当前 span 的唯一 ID |
| `parent_span_id` | string | 父 span 的 ID。为空表示根 span（通常是 loadgenerator 或 ts-ui-dashboard） |
| `span_name` | string | 操作名。格式多样：`HTTP POST http://...`（Client span）、`POST /api/v1/...`（Server span）、`ControllerName.methodName`（Internal span）、`SELECT table`（DB span） |
| `attr.span_kind` | string | span 类型：**Server**（接收请求）、**Client**（发出请求）、**Internal**（内部调用） |
| `service_name` | string | 产生此 span 的服务名，如 `ts-route-service` |
| `duration` | uint64 | span 持续时间，单位 **纳秒**。转换：`duration / 1e6` = 毫秒，`duration / 1e9` = 秒 |
| `attr.status_code` | string | OpenTelemetry 状态：`Unset`（正常）、`Ok`（显式成功）、`Error`（错误） |
| `attr.k8s.pod.name` | string | 运行此服务的 Pod 名，如 `ts-route-service-f6fbc58bc-gqbt9` |
| `attr.k8s.service.name` | string | K8s Service 名（通常与 service_name 一致） |
| `attr.k8s.namespace.name` | string | K8s Namespace，如 `ts2` |
| `attr.http.request.content_length` | uint64 | HTTP 请求体大小（字节） |
| `attr.http.response.content_length` | uint64 | HTTP 响应体大小（字节） |
| `attr.http.request.method` | string | HTTP 方法：GET / POST |
| `attr.http.response.status_code` | uint16 | HTTP 响应状态码：200, 500, 502, 503, 504 等 |

**关键用法**:

```sql
-- 1. 构建调用树：找到某个 trace 的完整调用链
SELECT span_id, parent_span_id, service_name, span_name, duration/1e6 as ms
FROM abnormal_traces
WHERE trace_id = 'xxx'
ORDER BY time

-- 2. 找错误 span
SELECT service_name, span_name, COUNT(*)
FROM abnormal_traces
WHERE attr_status_code = 'Error' OR attr_http_response_status_code >= 500
GROUP BY service_name, span_name

-- 3. 按服务统计延迟
SELECT service_name, AVG(duration)/1e9 as avg_sec, MAX(duration)/1e9 as max_sec
FROM abnormal_traces
GROUP BY service_name ORDER BY avg_sec DESC

-- 4. 追踪调用链（自连接）
SELECT t1.service_name as parent, t2.service_name as child,
       AVG(t2.duration)/1e6 as child_avg_ms
FROM abnormal_traces t1
JOIN abnormal_traces t2 ON t1.span_id = t2.parent_span_id
GROUP BY parent, child
```

**调用树示例**（一个完整 trace）:
```
loadgenerator → HTTP POST ts-ui-dashboard/travelPlan/minStation (20001ms, Error)
  └─ ts-ui-dashboard → POST /travelplanservice/travelPlan/minStation (20000ms)
    └─ ts-travel-plan-service → TravelPlanController.getByMinStation (25820ms)
      └─ ts-route-plan-service → RoutePlanController.getMinStopStations (25531ms)
        └─ ts-route-service → RouteController.queryByStartAndTerminal (5745ms)  ← 根因
          └─ ts-route-service → SELECT ts.route (928ms)  ← DB 慢查询
```

---

## 二、Logs（日志）

### abnormal_logs.parquet / normal_logs.parquet

**用途**: 记录各服务的应用日志。包含 ERROR/WARN 级别的异常信息（如 DB 连接失败、NPE 异常、超时）和 INFO 级别的正常操作日志。

**典型规模**: normal ~50K-100K 行，abnormal ~3K-25K 行

| 列名 | 类型 | 说明 |
|------|------|------|
| `time` | timestamp[ns, UTC] | 日志产生时间 |
| `trace_id` | string | 关联的 trace ID（可与 traces 表关联） |
| `span_id` | string | 关联的 span ID |
| `level` | string | 日志级别：`ERROR`、`WARN`、`INFO`、`DEBUG`、`TRACE`、`SEVERE` |
| `service_name` | string | 产生日志的服务名 |
| `message` | string | 日志正文。包含异常堆栈、错误描述、业务日志等 |
| `attr.k8s.pod.name` | string | Pod 名 |
| `attr.k8s.service.name` | string | K8s Service 名 |
| `attr.k8s.namespace.name` | string | Namespace |

**关键用法**:

```sql
-- 1. 扫描所有错误日志
SELECT time, service_name, level, message
FROM abnormal_logs
WHERE level IN ('ERROR', 'WARN', 'SEVERE')
ORDER BY time

-- 2. 按服务统计错误数量
SELECT service_name, level, COUNT(*) as count
FROM abnormal_logs
WHERE level IN ('ERROR', 'WARN')
GROUP BY service_name, level ORDER BY count DESC

-- 3. 搜索特定关键词（DB 连接、NPE、超时等）
SELECT time, service_name, message
FROM abnormal_logs
WHERE message LIKE '%HikariPool%' OR message LIKE '%NullPointerException%'
```

**常见错误模式**:
| 日志关键词 | 含义 | 提示的根因方向 |
|-----------|------|--------------|
| `HikariPool-1 - Failed to validate connection` | 数据库连接池验证失败 | MySQL 故障或网络中断 |
| `HikariPool-1 - Thread starvation or clock leap` | 线程饥饿 | 服务自身 CPU 过载 |
| `Connection reset` / `broken pipe` | TCP 连接被对端重置 | 对端服务崩溃或网络故障 |
| `NullPointerException` | 空指针异常 | 代码 bug 或依赖服务返回异常数据 |
| `Failed to check/redeclare auto-delete queue` | RabbitMQ 连接异常 | **通常是背景噪声**，非本次故障根因 |
| `Order already exist` | 业务层幂等冲突 | 上游重试导致，通常是症状非原因 |

> **注意**: RabbitMQ 相关错误（`Failed to check/redeclare auto-delete queue`）在几乎所有数据包中都出现，是集群的常态噪声，**不应**被当作故障根因。

---

## 三、Metrics — Gauge（即时值指标）

### abnormal_metrics.parquet / normal_metrics.parquet

**用途**: 记录各容器/Pod/Node 的即时值指标（Gauge），包括 CPU 使用率、内存用量、文件系统、JVM 运行时、K8s 部署状态、网络延迟（Hubble）等。

**典型规模**: ~70K 行（每 5 秒一个数据点 × 多个 metric × 多个 Pod）

| 列名 | 类型 | 说明 |
|------|------|------|
| `time` | timestamp[ns, UTC] | 采集时间 |
| `metric` | string | 指标名（见下方指标字典） |
| `value` | double | 指标值 |
| `service_name` | string | 服务名（部分指标为空，需用 k8s 属性关联） |
| `attr.k8s.node.name` | string | **K8s 节点名**（如 worker1~worker5），用于拓扑分析 |
| `attr.k8s.pod.name` | string | Pod 名 |
| `attr.k8s.container.name` | string | 容器名 |
| `attr.k8s.deployment.name` | string | Deployment 名 |
| `attr.k8s.namespace.name` | string | Namespace |
| `attr.k8s.statefulset.name` | string | StatefulSet 名（MySQL 用这个） |
| `attr.k8s.replicaset.name` | string | ReplicaSet 名 |
| `attr.destination_workload` | string | Hubble 指标：目标服务 |
| `attr.source_workload` | string | Hubble 指标：源服务 |
| `attr.destination` | string | Hubble：目标地址 |
| `attr.source` | string | Hubble：源地址 |

**指标字典**:

| 指标名 | 含义 | 正常范围 | 异常信号 |
|--------|------|---------|---------|
| **container.cpu.usage** | 容器 CPU 用量（cores） | 0.01~0.5 | >1.0 core 疑似异常 |
| **container.memory.usage** | 容器内存用量（bytes） | 因服务而异 | 突然飙升 |
| **container.memory.rss** | 常驻内存集 | — | — |
| **jvm.cpu.recent_utilization** | JVM 最近 CPU 利用率 (0~1) | 0.01~0.3 | >0.8 高负载 |
| **jvm.system.cpu.load_1m** | 系统 1 分钟平均负载 | 1~30 | >100 严重过载 |
| **jvm.system.cpu.utilization** | 系统 CPU 利用率 (0~1) | 0.1~0.5 | >0.9 |
| **k8s.container.restarts** | 容器重启次数 | 0 | **>0 = Pod 重启过**（PodChaos 关键信号） |
| **k8s.container.ready** | 容器就绪状态 (0/1) | 1 | 0 = 服务不可用 |
| **k8s.pod.cpu.usage** | Pod 级 CPU 用量 | — | — |
| **k8s.pod.cpu_limit_utilization** | CPU 限额利用率 (0~1) | <0.5 | >0.9 接近限额 |
| **k8s.pod.memory_limit_utilization** | 内存限额利用率 (0~1) | <0.7 | >0.95 OOM 风险 |
| **k8s.deployment.available** | Deployment 可用副本数 | = desired | < desired = 缩容/故障 |
| **hubble_http_request_duration_p99_seconds** | 服务间 HTTP 请求 P99 延迟 | <0.5s | >2s |
| **queueSize** | 消息队列大小 | <100 | 持续增长 = 消费者跟不上 |

```sql
-- 1. 对比服务 CPU（正常 vs 异常）
SELECT 'abnormal' as period, service_name, AVG(value) as avg_cpu
FROM abnormal_metrics WHERE metric = 'container.cpu.usage'
GROUP BY service_name
UNION ALL
SELECT 'normal', service_name, AVG(value)
FROM normal_metrics WHERE metric = 'container.cpu.usage'
GROUP BY service_name

-- 2. 检查 Pod 重启（PodChaos 关键）
SELECT time, service_name, value as restarts
FROM abnormal_metrics WHERE metric = 'k8s.container.restarts' AND value > 0

-- 3. 找同一 K8s Node 上的所有服务（拓扑关联）
SELECT DISTINCT attr_k8s_node_name, service_name
FROM abnormal_metrics WHERE attr_k8s_node_name IS NOT NULL
ORDER BY attr_k8s_node_name

-- 4. Hubble 网络延迟（服务间）
SELECT attr_destination_workload, AVG(value) as avg_p99
FROM abnormal_metrics
WHERE metric = 'hubble_http_request_duration_p99_seconds'
GROUP BY attr_destination_workload ORDER BY avg_p99 DESC
```

---

## 四、Metrics — Histogram（分布型指标）

### abnormal_metrics_histogram.parquet / normal_metrics_histogram.parquet

**用途**: 记录需要了解分布（count/sum/min/max）的指标，主要是 HTTP 请求延迟、DB 连接等待时间、JVM GC 暂停时间。

**典型规模**: ~4K-5K 行

| 列名 | 类型 | 说明 |
|------|------|------|
| `time` | timestamp[ns, UTC] | 采集时间 |
| `metric` | string | 指标名 |
| `service_name` | string | 服务名 |
| `count` | double | 采样窗口内的事件数 |
| `sum` | double | 采样窗口内的总值（秒） |
| `min` | double | 采样窗口内的最小值（秒） |
| `max` | double | 采样窗口内的最大值（秒） |
| `attr.k8s.pod.name` | string | Pod 名 |
| `attr.k8s.service.name` | string | K8s Service 名 |
| `attr.k8s.namespace.name` | string | Namespace |
| `attr.jvm.gc.action` | string | GC 动作类型：`end of minor GC`、`end of major GC` |
| `attr.jvm.gc.name` | string | GC 名称：`G1 Young Generation`、`G1 Old Generation` |
| `attr.destination` | string | Hubble：目标 |
| `attr.source` | string | Hubble：源 |

**指标字典**:

| 指标名 | 含义 | 用法 |
|--------|------|------|
| **http.server.request.duration** | 服务端处理 HTTP 请求的耗时（秒） | `sum/count` = 平均延迟 |
| **http.client.request.duration** | 客户端发出 HTTP 请求的耗时（秒） | 对比 server 端可知网络开销 |
| **db.client.connections.use_time** | DB 连接使用时间（秒） | `max` 飙升 = DB 慢查询 |
| **db.client.connections.wait_time** | 等待 DB 连接的时间（秒） | `max > 0` = 连接池耗尽 |
| **jvm.gc.duration** | GC 暂停时间（秒） | `max > 1s` = 严重 GC 问题（stop-the-world） |
| **hubble_http_request_duration_seconds** | Hubble 网络层 HTTP 耗时（秒） | 服务网格级延迟 |

```sql
-- 1. 对比 HTTP Server 延迟（正常 vs 异常）
SELECT 'abnormal' as period, service_name,
       SUM(sum)/SUM(count) as avg_duration_sec, MAX(max) as max_sec
FROM abnormal_metrics_histogram
WHERE metric = 'http.server.request.duration'
GROUP BY service_name
UNION ALL
SELECT 'normal', service_name,
       SUM(sum)/SUM(count), MAX(max)
FROM normal_metrics_histogram
WHERE metric = 'http.server.request.duration'
GROUP BY service_name

-- 2. 检查 DB 连接等待（连接池瓶颈）
SELECT service_name, MAX(max) as max_wait_sec
FROM abnormal_metrics_histogram
WHERE metric = 'db.client.connections.wait_time'
GROUP BY service_name ORDER BY max_wait_sec DESC

-- 3. GC 暂停分析
SELECT service_name, attr_jvm_gc_name, MAX(max) as max_gc_sec, SUM(count) as gc_count
FROM abnormal_metrics_histogram
WHERE metric = 'jvm.gc.duration'
GROUP BY service_name, attr_jvm_gc_name ORDER BY max_gc_sec DESC
```

---

## 五、Metrics — Sum/Counter（累积型指标）

### abnormal_metrics_sum.parquet / normal_metrics_sum.parquet

**用途**: 记录单调递增的计数器型指标（Counter/Sum），包括 DB 连接池状态、JVM 内存/线程、网络流量、Hub 流量统计等。

**典型规模**: ~90K-100K 行

| 列名 | 类型 | 说明 |
|------|------|------|
| `time` | timestamp[ns, UTC] | 采集时间 |
| `metric` | string | 指标名 |
| `value` | double | 累积值或当前值 |
| `service_name` | string | 服务名 |
| `attr.k8s.node.name` | string | K8s 节点名 |
| `attr.k8s.pod.name` | string | Pod 名 |
| `attr.k8s.container.name` | string | 容器名 |
| ... | | （其余 K8s 属性同 metrics 表） |

**指标字典**:

| 指标名 | 含义 | 异常信号 |
|--------|------|---------|
| **db.client.connections.usage** | 当前使用的 DB 连接数 | 接近 max = 连接池耗尽 |
| **db.client.connections.max** | DB 连接池最大容量 | 通常 10 |
| **db.client.connections.pending_requests** | 等待连接的请求数 | **>0 = 连接池瓶颈**（关键信号） |
| **db.client.connections.idle.min** | 最少空闲连接数 | 突降 = 连接被占满 |
| **jvm.memory.used** | JVM 内存用量（bytes） | 接近 limit = OOM 风险 |
| **jvm.memory.limit** | JVM 内存上限 | — |
| **jvm.thread.count** | JVM 线程数 | 飙升 = 线程泄漏 |
| **jvm.cpu.time** | JVM 累积 CPU 时间 | 增长率变化 |
| **jvm.class.count** | 已加载类数 | — |
| **k8s.pod.network.errors** | Pod 网络错误数 | >0 = 网络问题 |
| **k8s.pod.network.io** | Pod 网络 IO（bytes） | 突降 = 网络中断 |
| **hubble_drop_total** | Cilium 丢包总数 | 突增 = 网络丢包 |
| **hubble_http_requests_total** | Hubble HTTP 请求总数 | — |

```sql
-- 1. DB 连接池状态对比
SELECT service_name, metric, AVG(value) as avg_val, MAX(value) as max_val
FROM abnormal_metrics_sum
WHERE metric LIKE 'db.client.connections%'
GROUP BY service_name, metric ORDER BY service_name

-- 2. 检查是否有 pending requests（连接池耗尽的铁证）
SELECT time, service_name, value
FROM abnormal_metrics_sum
WHERE metric = 'db.client.connections.pending_requests' AND value > 0

-- 3. JVM 线程数异常
SELECT service_name,
       AVG(value) as avg_threads, MAX(value) as max_threads
FROM abnormal_metrics_sum
WHERE metric = 'jvm.thread.count'
GROUP BY service_name ORDER BY max_threads DESC
```

---

## 六、Conclusion（预计算摘要）

### conclusion.parquet

**用途**: 按 API endpoint 级别预计算的 SLO 对比表。每行是一个从 `loadgenerator` 发起的 API 端点，对比其在正常/异常时段的延迟和成功率。

**典型规模**: ~15-20 行

| 列名 | 类型 | 说明 |
|------|------|------|
| `SpanName` | string | API 端点全名，如 `HTTP POST http://ts-ui-dashboard:8080/api/v1/preserveservice/preserve` |
| `Issues` | string | JSON 格式的问题描述。`{}` = 无异常；非空 = 检测到 SLO 违规 |
| `AbnormalAvgDuration` | double | 异常时段平均延迟（秒） |
| `NormalAvgDuration` | double | 正常时段平均延迟（秒） |
| `AbnormalSuccRate` | double | 异常时段成功率 (0~1) |
| `NormalSuccRate` | double | 正常时段成功率（通常 = 1.0） |
| `AbnormalP90/P95/P99` | double | 异常时段延迟百分位（秒） |
| `NormalP90/P95/P99` | double | 正常时段延迟百分位（秒） |

**用法**: 快速定位哪些 API 受影响最严重，作为调查的起点。

```sql
-- 找出延迟恶化最严重的 API
SELECT SpanName,
       AbnormalAvgDuration / NormalAvgDuration as slowdown_ratio,
       AbnormalAvgDuration, NormalAvgDuration
FROM conclusion
WHERE Issues != '{}'
ORDER BY slowdown_ratio DESC
```

---

## 七、表间关系图

```
┌─────────────┐     trace_id/span_id     ┌─────────────┐
│    Logs      │ ◄───────────────────────► │   Traces    │
│ (日志详情)    │                           │ (调用链)     │
└──────┬───────┘                           └──────┬───────┘
       │ service_name                             │ service_name
       │                                          │ parent_span_id → span_id (自连接)
       ▼                                          ▼
┌─────────────┐                           ┌─────────────┐
│  Conclusion  │ ◄── SpanName 对应          │   Traces    │
│ (SLO 摘要)   │     traces.span_name      │ (自连接调用树) │
└─────────────┘                           └─────────────┘
       │                                          │
       │                                          │ attr.k8s.pod.name
       │                                          │ attr.k8s.node.name
       ▼                                          ▼
┌──────────────────────────────────────────────────┐
│              Metrics (三张表)                       │
│  ┌──────────┐  ┌───────────────┐  ┌────────────┐ │
│  │  Gauge   │  │  Histogram    │  │   Sum      │ │
│  │ (即时值)  │  │ (延迟分布)    │  │ (累积计数)  │ │
│  └──────────┘  └───────────────┘  └────────────┘ │
│  service_name / attr.k8s.pod.name 关联            │
└──────────────────────────────────────────────────┘
```

**关联方式**:
- **Logs ↔ Traces**: 通过 `trace_id` + `span_id` 精确关联（某条日志对应某个 span）
- **Traces 自连接**: 通过 `parent_span_id = span_id` 构建调用树
- **Traces ↔ Metrics**: 通过 `service_name` 或 `attr.k8s.pod.name` 关联
- **Conclusion ↔ Traces**: Conclusion 的 SpanName 对应 traces 中 loadgenerator 发出的 Client span
- **Metrics 三表互补**: Gauge（CPU/内存等即时值）、Histogram（延迟分布）、Sum（连接池/线程等计数器）描述同一服务的不同维度

---

## 八、故障排查 SOP

### 阶段流程图

```
Phase 1: 定位受影响范围              Phase 2: 追踪调用链              Phase 3: 定位根因
┌──────────────────┐           ┌──────────────────┐           ┌──────────────────┐
│ ① conclusion     │           │ ④ traces 自连接   │           │ ⑦ metrics (gauge)│
│   看哪些 API 异常  │           │   构建调用树       │           │   CPU/内存/重启    │
│                  │           │                  │           │                  │
│ ② traces 统计    │           │ ⑤ traces + logs  │           │ ⑧ metrics_sum    │
│   按服务聚合延迟   │ ────────► │   关联错误日志      │ ────────► │   DB 连接池/JVM   │
│                  │           │                  │           │                  │
│ ③ logs 错误扫描   │           │ ⑥ normal 对比     │           │ ⑨ metrics_hist   │
│   ERROR/WARN 概览 │           │   量化偏差程度      │           │   延迟/GC 分布     │
└──────────────────┘           └──────────────────┘           └──────────────────┘
                                                                      │
                                                                      ▼
                                                              ┌──────────────────┐
                                                              │ ⑩ 综合判定        │
                                                              │   输出因果图       │
                                                              └──────────────────┘
```

### 详细步骤

#### Phase 1: 定位受影响范围（用 conclusion + traces + logs）

**Step ①: 从 conclusion 开始，找受影响的 API**

```sql
SELECT SpanName,
       AbnormalAvgDuration / NULLIF(NormalAvgDuration, 0) as slowdown,
       AbnormalSuccRate, NormalSuccRate
FROM conclusion
WHERE Issues != '{}'
ORDER BY slowdown DESC
```

> 产出：受影响的 API 列表及恶化倍数。例如 `travelPlan/minStation` 延迟从 0.45s → 15s (33x)。

**Step ②: 在 traces 中按服务聚合异常**

```sql
SELECT service_name,
       COUNT(*) as total,
       SUM(CASE WHEN attr_status_code='Error' THEN 1 ELSE 0 END) as errors,
       AVG(duration)/1e9 as avg_sec,
       MAX(duration)/1e9 as max_sec
FROM abnormal_traces
GROUP BY service_name ORDER BY avg_sec DESC
```

> 产出：各服务的平均延迟排名，找出延迟最高的服务。

**Step ③: 扫描 ERROR/WARN 日志**

```sql
SELECT service_name, level, COUNT(*) as count
FROM abnormal_logs
WHERE level IN ('ERROR', 'WARN', 'SEVERE')
GROUP BY service_name, level ORDER BY count DESC
```

> 产出：错误日志数量排名。但**不要**仅凭错误数量判断根因——错误多的可能是受害者，不是源头。

---

#### Phase 2: 追踪调用链（用 traces 自连接 + logs 关联 + normal 对比）

**Step ④: 从受影响 API 追踪调用树**

```sql
-- 找一个高延迟 trace
SELECT trace_id FROM abnormal_traces
WHERE span_name LIKE '%travelPlan%' AND duration > 10e9
LIMIT 1

-- 展开完整调用树
SELECT span_id, parent_span_id, service_name, span_name,
       duration/1e6 as ms, attr_status_code
FROM abnormal_traces
WHERE trace_id = '<上一步结果>'
ORDER BY time
```

> 产出：完整的服务调用树。找到延迟最集中的叶子节点。

**Step ⑤: 关联异常服务的错误日志**

```sql
SELECT time, level, message
FROM abnormal_logs
WHERE service_name = '<可疑服务>'
  AND level IN ('ERROR', 'WARN', 'SEVERE')
ORDER BY time
```

> 产出：特定服务的错误详情。看是否有 DB 连接失败、NPE、连接重置等。

**Step ⑥: 与正常基线做定量对比**

```sql
SELECT 'abnormal' as period, service_name, span_name,
       AVG(duration)/1e9 as avg_sec
FROM abnormal_traces
WHERE service_name = '<可疑服务>'
GROUP BY service_name, span_name
UNION ALL
SELECT 'normal', service_name, span_name,
       AVG(duration)/1e9
FROM normal_traces
WHERE service_name = '<可疑服务>'
GROUP BY service_name, span_name
```

> 产出：该服务在正常/异常时段的延迟对比。如果异常延迟 > 正常的 5x 以上，基本可确认异常。

---

#### Phase 3: 定位根因（用三张 metrics 表交叉验证）

**Step ⑦: 检查资源指标（Gauge）**

```sql
-- CPU 对比
SELECT 'abnormal' as period, service_name, AVG(value) as avg_cpu, MAX(value) as max_cpu
FROM abnormal_metrics WHERE metric = 'container.cpu.usage'
GROUP BY service_name
UNION ALL
SELECT 'normal', service_name, AVG(value), MAX(value)
FROM normal_metrics WHERE metric = 'container.cpu.usage'
GROUP BY service_name

-- Pod 重启检查
SELECT time, service_name, value
FROM abnormal_metrics
WHERE metric = 'k8s.container.restarts' AND value > 0
```

> 产出：CPU/内存/重启对比。PodChaos 会导致 `k8s.container.restarts > 0`。

**Step ⑧: 检查 DB 连接池和 JVM（Sum）**

```sql
-- DB 连接池
SELECT service_name, metric, AVG(value) as avg, MAX(value) as max
FROM abnormal_metrics_sum
WHERE metric IN ('db.client.connections.pending_requests',
                 'db.client.connections.usage', 'db.client.connections.max')
GROUP BY service_name, metric ORDER BY service_name

-- JVM 线程
SELECT service_name, AVG(value) as avg_threads, MAX(value) as max_threads
FROM abnormal_metrics_sum
WHERE metric = 'jvm.thread.count'
GROUP BY service_name ORDER BY max_threads DESC
```

> 产出：`pending_requests > 0` = 连接池耗尽。`thread.count` 飙升 = 线程堆积。

**Step ⑨: 检查延迟分布和 GC（Histogram）**

```sql
-- HTTP 延迟对比
SELECT 'abnormal' as period, service_name,
       SUM(sum)/SUM(count) as avg_sec, MAX(max) as max_sec
FROM abnormal_metrics_histogram
WHERE metric = 'http.server.request.duration'
GROUP BY service_name
UNION ALL
SELECT 'normal', service_name,
       SUM(sum)/SUM(count), MAX(max)
FROM normal_metrics_histogram
WHERE metric = 'http.server.request.duration'
GROUP BY service_name

-- GC 暂停
SELECT service_name, MAX(max) as max_gc_pause_sec
FROM abnormal_metrics_histogram
WHERE metric = 'jvm.gc.duration'
GROUP BY service_name ORDER BY max_gc_pause_sec DESC
```

> 产出：GC 暂停 > 1s 通常意味着 JVM 内存压力。

---

#### Phase 4: 综合判定

**Step ⑩: 区分症状和原因，输出因果图**

根据 Phase 1-3 的证据，按以下优先级判定根因：

| 优先级 | 证据模式 | 根因类型 |
|--------|---------|---------|
| 1 | `k8s.container.restarts > 0` 且时间最早 | **PodChaos**（Pod 被 kill） |
| 2 | DB 连接失败日志 + `pending_requests > 0` | **MySQL 故障**（连接中断） |
| 3 | HTTP 500/503 + 调用链上延迟最高的叶子节点 | **HTTPFault**（延迟/错误注入） |
| 4 | GC 暂停飙升 + CPU 高 + 线程堆积 | **JVMChaos**（JVM 故障注入） |
| 5 | 调用链上延迟从某节点开始急剧增加 | **NetworkChaos**（网络延迟/丢包） |

**关键原则**:
1. **向上游追溯**: 调用链中延迟最高的**最深层节点**更可能是根因
2. **时间最早**: 异常最先出现的服务更可能是源头
3. **排除噪声**: RabbitMQ 日志、loadgenerator 超时是常规噪声
4. **区分症状**: 上游服务超时可能只是在等待下游——真正的根因在调用链的末端

---

## 九、按故障类型的排查侧重点

| 故障类型 | 典型信号 | 优先查的表 | 关键 SQL |
|---------|---------|-----------|---------|
| **NetworkDelay** | 某服务延迟飙升、无 HTTP 错误码 | traces（延迟对比）+ metrics（hubble） | `abnormal/normal traces duration UNION` |
| **NetworkLoss** | 间歇性 500/504、连接重置 | traces（错误码）+ logs（connection reset） | `WHERE attr_http_response_status_code >= 500` |
| **HTTPResponseDelay** | 特定 API 延迟固定增加 | traces（调用树）+ conclusion | 调用树找叶子节点 |
| **HTTPResponseReplaceCode** | 特定 API 返回非预期状态码 | traces（状态码分析） | `GROUP BY attr_http_response_status_code` |
| **JVMChaos** | GC 暂停飙升、CPU 高、线程堆积 | metrics_histogram（GC）+ metrics_sum（JVM） | `WHERE metric = 'jvm.gc.duration'` |
| **ContainerKill** | Pod 重启、服务短暂不可用 | metrics（restarts）+ logs（启动日志） | `WHERE metric = 'k8s.container.restarts'` |
| **PodFailure** | 服务完全不可用、503 | metrics（ready=0）+ traces（503） | `WHERE metric = 'k8s.container.ready'` |

---

## 十、常见陷阱

| # | 陷阱 | 说明 | 正确做法 |
|---|------|------|---------|
| 1 | 把 loadgenerator 当根因 | loadgenerator 是流量发生器，它的超时是下游问题的反映 | 忽略 loadgenerator，从 ts-ui-dashboard 开始追踪 |
| 2 | RabbitMQ 日志误导 | `Failed to check/redeclare auto-delete queue` 几乎每个 case 都有 | 除非有其他 MQ 证据，否则忽略 |
| 3 | 被 CPU 尖峰吸引 | CPU 飙升常是下游超时导致的线程堆积（症状），不是原因 | 先查调用链，确认是上游还是下游导致 |
| 4 | 只看异常数据不看正常基线 | 无法判断"高延迟"到底多高 | 始终 UNION normal 和 abnormal 做对比 |
| 5 | duration 单位错误 | traces 中的 duration 是**纳秒**（uint64），不是毫秒或秒 | `duration / 1e6` = ms，`duration / 1e9` = s |
| 6 | 只看错误数量不看调用链 | 错误最多的服务往往是中间层受害者 | 沿调用链向下/向上追溯 |
| 7 | 忽略 Internal span | Internal span 记录了服务内部的 Controller/Repository 调用 | 区分 Server（接收）、Client（发出）、Internal（内部），三者延迟关系揭示瓶颈 |
| 8 | HikariPool 日志直接归因 MySQL | 连接池失败可能是应用端问题（如 Pod 重启后重连） | 检查 MySQL 自身指标 + Pod 重启状态 |
