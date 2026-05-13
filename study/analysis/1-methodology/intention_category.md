# Agent 排障意图分类体系（19 类）

> 用于 Markov 状态矩阵的原子意图集合。
> 从两个角度对齐：① 各故障类型的必要诊断动作；② 人类 SRE 真实排障动作。
> 不预设顺序，顺序由 Markov 转移矩阵刻画。
> schema_discovery（list_tables/get_schema）和 think（think_tool）不计入意图，前者每条轨迹固定出现，后者是推理动作而非分析意图。

## 分类方式

使用 LLM（claude-opus-4-6）对每条 SQL 独立分类。每条 SQL 对应一个意图，按 round 组织，支持 round 级聚合和全局序列分析。

分类脚本：`RCAgentEval/scripts/classify_intents.py`
Prompt 模板：`RCAgentEval/utu/eval/analysis/intent_prompt.py`
分类器：`RCAgentEval/utu/eval/analysis/llm_intent_classifier.py`

结果存储在 DB 的 `meta.llm_intents.<model_key>` 字段中，每条记录包含：
- `round`: trajectory 中的 round 序号（1-based）
- `sql_index`: round 内 SQL 序号（1-based）
- `global_index`: 整条轨迹的全局 SQL 序号（1-based，跨 round 递增）
- `intent`: 19 类意图之一
- `data_type`: logs / traces / metrics（从 SQL 表名本地判断）
- `reasoning`: LLM 分类理由

## 意图定义

| # | 意图 | 中文解释 | 故障线索 | SRE 排障动作 |
|---|------|---------|---------|------------|
| | **—— Traces ——** | | | |
| 1 | **latency_ranking** | 全服务延迟排名 | HTTP delay/bandwidth; Network delay; Code stress | 看大盘：谁最慢？ |
| 2 | **throughput_compare** | 全服务流量对比 | Network partition/loss; HTTP abort; duplicate | 看大盘：谁的请求量变了？ |
| 3 | **error_rate_scan** | 全服务错误率分布 | HTTP replace-code/abort; Network loss; Code exception | 看大盘：谁失败率最高？ |
| 4 | **service_trace_scan** | 特定服务 trace 检查 | 所有（服务级排查） | 点进服务：看 span、延迟、状态码、接口 |
| 5 | **trace_follow** | 追踪单次请求调用链 | 所有（还原因果传播路径） | 找一条异常请求逐跳看 |
| 6 | **call_tree_build** | 构建调用树 | 长链路传播（delay→timeout 级联） | 画调用拓扑，理解依赖 |
| | **—— Logs ——** | | | |
| 7 | **error_log_overview** | 全局错误日志总览 | 所有 | 扫一眼：哪些服务有 ERROR？ |
| 8 | **service_error_log** | 特定服务错误日志 | Code exception/mysql; Resource kill; HTTP replace-body | 点进服务：报了什么错？ |
| 9 | **service_log_browse** | 浏览特定服务全部日志 | HTTP replace-body（200+Error 矛盾）; dns | 通读日志找隐藏线索 |
| 10 | **keyword_search** | 搜索特定关键词 | 所有（假设验证） | 搜 "timeout"/"OOM"/"reset" |
| 11 | **error_timeline** | 建立错误时间线 | Resource kill; Code mysql | 排时间线：谁先出问题？首次/末次出错时间 |
| | **—— Metrics ——** | | | |
| 12 | **metric_scan** | 探索/浏览指标 | 所有（选择分析方向的前提） | 看有哪些指标、维度（pod/workload/service）可查 |
| 13 | **container_resource** | 容器资源（CPU/内存/磁盘） | Resource cpu/memory-exhaustion; Code stress | CPU 打满？内存 OOM？ |
| 14 | **jvm_state** | JVM 状态（GC/线程池/连接池） | Code gc/return/stress; HTTP bandwidth | GC 停顿？连接池耗尽？ |
| 15 | **network_layer** | 网络层指标（hubble/丢包/p95） | Network 全部; HTTP bandwidth; Code return | 丢包？HTTP p95？ |
| 16 | **k8s_state** | K8s 状态（pod restart/deployment） | Resource kill/failure | Pod 重启了？ |
| 17 | **db_state** | 数据库状态（连接数/慢查询） | Code mysql; Resource kill | DB 连接池？慢查询？ |
| | **—— Baseline 对比 ——** | | | |
| 18 | **baseline_collect** | 采集正常期数据 | 所有（量化偏差的前提） | 先看正常时候什么样 |
| 19 | **baseline_contrast** | 正常 vs 异常直接对比 | 所有（核心分析手段） | 并排对比变了多少 |

### 改名记录（相对旧版）

| 旧名 | 新名 | 原因 |
|------|------|------|
| `temporal_ordering` | `error_timeline` | 旧名太窄（只覆盖 MIN/MAX time GROUP BY），实际还包括 ORDER BY time + error focus、EPOCH() 时间戳提取等模式。新名更贴合 SRE 动作 |
| `service_latency_drill` | `service_trace_scan` | 旧名只强调延迟，实际包括状态码检查、span 浏览、LIKE 模糊匹配服务名等，远不止 latency drill |
| `metric_discovery` | `metric_scan` | 旧名只覆盖"列举指标名"，实际还包括探索维度值（pod/workload/destination）、无特定域过滤的指标浏览 |

---

## 分类优先级（单条 SQL → 单个意图）

一条 SQL 可能匹配多个意图，按以下优先级取**第一个命中的**：

| 优先级 | 意图 | 判定信号 | 为什么优先 |
|--------|------|---------|-----------|
| **P1 结构独特** | **call_tree_build** | JOIN parent_span_id = span_id | SQL 结构唯一，不可能是别的意图 |
| | **baseline_contrast** | UNION/JOIN normal + abnormal | SQL 结构唯一 |
| **P2 表独特** | **baseline_collect** | 仅查 normal_* 表（不含 abnormal） | 不管查什么列，查 normal 表就是在建基线 |
| **P3 ID 定位** | **trace_follow** | WHERE trace_id = | 精确到单次请求，比服务级过滤更具体 |
| **P4 时间线** | **error_timeline** | MIN/MAX(time) GROUP BY svc, EPOCH(time), ORDER BY time + error focus | 建立"谁先出错"的时间线 |
| **P5 指标域** | **network_layer** | metric 名含 hubble / http_request / http.server / network / tcp / drop | 指标名（精确或 LIKE 模糊）决定排障域 |
| | **jvm_state** | metric 名含 jvm / gc / queue / hikari / thread / heap | |
| | **k8s_state** | metric 名含 k8s.deployment / restart / pod-kill / pod.phase | |
| | **db_state** | metric 名含 db.client / mysql / connections | |
| | **container_resource** | metric 名含 container.cpu / container.memory / k8s.pod.cpu / k8s.pod.memory | |
| **P5.5 指标浏览** | **metric_scan** | metrics 表 + SELECT DISTINCT (metric/pod/workload) 或无 metric 过滤条件 | 未指定具体指标域 = 在探索/浏览 |
| **P6 文本搜索** | **keyword_search** | message / span_name LIKE '%keyword%' | 有 LIKE 说明在验证特定假设 |
| **P7 日志分析** | **service_error_log** | logs WHERE service_name = AND level IN (...) | 服务 + 级别双过滤 |
| | **service_log_browse** | logs WHERE service_name =（无 level 过滤） | 只有服务过滤 |
| | **error_log_overview** | logs GROUP BY service_name, level（无 WHERE service_name） | 全局扫描 |
| **P8 Trace 分析** | **error_rate_scan** | traces + status_code 过滤或分组 | 状态码是独特信号 |
| | **service_trace_scan** | traces WHERE service_name = / LIKE '%svc%' | 服务级 trace 检查 |
| | **throughput_compare** | traces GROUP BY service_name COUNT(*) | 流量分析 |
| | **latency_ranking** | traces GROUP BY service_name AVG(duration) — Traces 兜底 | 全局延迟排名 |

**P5 指标域判定说明**：不区分查的是 metrics (gauge)、metrics_sum 还是 metrics_histogram 表，统一按 WHERE 中的 metric 名称（精确匹配或 LIKE 模糊匹配）归入对应域。如果 metric 名称未命中任何特定域且无 DISTINCT/无 metric 过滤，则归入 metric_scan (P5.5)。

---

## 三层行为分析框架

Dashboard 中的行为分析由三层递进式可视化组成，从宏观策略到微观模式。

### 第一层：5 阶段 Markov 转移矩阵

19 个意图按**认知深度**聚合为 5 个排障阶段，做 5×5 转移矩阵热力图。前端可切换到 19×19 意图视图。

| 阶段 | 意图 | 认知阶段 | 占比 |
|------|------|---------|------|
| **triage**（分诊定向） | latency_ranking, throughput_compare, error_rate_scan, error_log_overview, metric_scan | "发生了什么，有什么可查" | 27.2% |
| **trace_investigate**（链路调查） | service_trace_scan, trace_follow, call_tree_build | "请求怎么走的，谁调谁" | 33.9% |
| **log_investigate**（日志调查） | service_error_log, service_log_browse, keyword_search, error_timeline | "日志说了什么，时间线怎样" | 15.1% |
| **metric_diagnose**（指标诊断） | container_resource, jvm_state, network_layer, k8s_state, db_state | "具体哪个组件有问题" | 15.3% |
| **baseline**（基线对比） | baseline_collect, baseline_contrast | "和正常时比变了多少" | 8.6% |

**分组逻辑**：
- `metric_scan` 归入 triage 而非 metric_diagnose，因为它是"探索有什么指标可查"的定向动作，和全局扫描同属认知建立阶段
- `metric_diagnose` 只包含有明确目标域的指标查询（CPU/JVM/网络/K8s/DB），都是定向诊断
- 每个意图固定归属一个阶段，无动态映射

### 第二层：多模态面积图（Modality Progression）

X 轴=归一化轨迹进度(0%-100%)，Y 轴=logs/traces/metrics 三种数据源占比（堆叠到 100%）。

**数据来源**：直接使用 `meta.llm_intents.<model_key>` 中每条 SQL 的 `data_type` 字段，按 `global_index` 排序。不再依赖旧的 `classify_data_type()` 函数。

每条 SQL 的 `data_type` 在分类时已从 SQL 表名自动判定并存储：
- 表名含 `log` → logs
- 表名含 `trace` → traces
- 表名含 `metric`（含 metrics_sum、metrics_histogram）→ metrics

**与意图的关系**：`data_type` 和 `intent` 是同一条 SQL 的两个独立标签。例如同一条 `keyword_search` 的 SQL，`data_type` 可能是 traces（搜 span_name）或 logs（搜 message），取决于实际查的表。

### 第三层：N-gram 分析

基于 19 类意图的 N-gram 频率分析，两个视图：

| 视图 | 用途 | 展示方式 |
|------|------|---------|
| **Cross-Model 热力图** | 跨模型对比 top-K n-gram 使用率 | X=n-gram 模式, Y=实验 ID, 颜色=使用率(%)。按样本数归一化 |
| **Correct vs Incorrect 双栏** | 同一模型正确/错误行为差异 | 左右双栏横向柱状图, 柱长=使用率(%), 高亮独有模式 |

N（gram 大小）和 K（top-K）均可在前端手动调节。

---

## 能力维度聚合（Behavioral Fingerprint 雷达图）

8 个维度，来源于不同的分析模块。意图维度（5/6/7/8）直接复用 5 阶段分组，19 个意图全覆盖。

**数据来源**：维度 2/4/5/6/7/8 均从 `meta.llm_intents.<model_key>` 读取，每条记录包含 `intent`、`data_type`、`global_index`。

| # | 维度 | 英文 key | 数据来源 | 包含意图 | 计算方式 |
|---|------|---------|---------|---------|---------|
| 1 | **开销** | cost | meta.cost_metrics | — | 1/avg_cost_usd, max-normalize 到 0-1 |
| 2 | **多模态获取** | multimodal | llm_intents.data_type | — | 每样本使用的 data_type 种类(logs/traces/metrics) / 3, 取平均 |
| 3 | **推理一致性** | coherence | Triplet Coherence | — | R→T utilized_rate |
| 4 | **调查深度** | depth | llm_intents | — | 每样本 SQL 总数（len(llm_intents)）, max-normalize 到 0-1 |
| 5 | **分诊定向** | triage | llm_intents.intent | latency_ranking, throughput_compare, error_rate_scan, error_log_overview, metric_scan (5个) | 做过任一的样本占比 |
| 6 | **链路调查** | trace_investigate | llm_intents.intent | service_trace_scan, trace_follow, call_tree_build (3个) | 做过任一的样本占比 |
| 7 | **诊断能力** | diagnose | llm_intents.intent | service_error_log, service_log_browse, keyword_search, error_timeline, container_resource, jvm_state, network_layer, k8s_state, db_state (9个, log_investigate + metric_diagnose) | 做过任一的样本占比 |
| 8 | **基线对比** | baseline | llm_intents.intent | baseline_collect, baseline_contrast (2个) | 做过任一的样本占比 |

**聚合逻辑说明**：
- 维度 5/6/7/8 按意图覆盖统计：每个样本的 `llm_intents` 中出现过该组内任一意图则计数，取所有样本的比率。值域 0-1。
- 维度 7 合并了 log_investigate 和 metric_diagnose 两个阶段（都是定向诊断），避免雷达图维度过多。
- 维度 1（cost）需要跨实验 max-normalize 到 0-1。
- 维度 4（depth）改为直接统计每样本 `llm_intents` 条数（即有效 SQL 查询数），max-normalize 到 0-1。
- 维度 3（coherence）从已有的 Triplet Coherence 缓存取 R→T utilized_rate。
- 维度 2（multimodal）从 `llm_intents` 的 `data_type` 字段统计每样本使用了几种数据源，除以 3 归一化。

---

## Intent Usage Heatmap（意图使用热力图）

19×N 热力图，展示每个实验（或模型）对各意图的使用频率。

**数据来源**：`meta.llm_intents.<model_key>`，按 `intent` 字段聚合。

### 计算方式

对每个实验的所有样本，统计每个意图的使用指标：

| 指标 | 计算 | 用途 |
|------|------|------|
| **覆盖率**（sample coverage） | 使用过该意图的样本数 / 总样本数 | 热力图主色 |
| **平均频次**（avg frequency） | 该意图出现总次数 / 总样本数 | tooltip 详情 |
| **占比**（share） | 该意图出现次数 / 所有意图出现总次数 | 归一化对比 |

### 可视化布局

```
              latency  throughput  error_rate  ... baseline_contrast
claude-4.6    0.85     0.12        0.93       ...  0.72
gemini-3.1    0.79     0.05        0.88       ...  0.65
gpt-5.3       0.60     0.02        0.72       ...  0.05
qwen3.5       0.91     0.14        0.95       ...  0.21
```

- X 轴：19 个意图，按 5 阶段分组排列（triage | trace_investigate | log_investigate | metric_diagnose | baseline）
- Y 轴：各实验/模型
- 颜色：覆盖率 0-1（白→深色）
- 分组分隔线标注 5 个阶段

### 与 5 阶段 Markov 的关系

- Heatmap 展示**每个意图的使用频率**（静态统计）
- Markov 矩阵展示**阶段间的转移概率**（动态序列）
- 两者互补：Heatmap 回答"用了什么"，Markov 回答"怎么用的"

---

## 旧版动态映射说明（已废弃）

> 旧版 5 阶段（global_overview / trace_drill / log_drill / metric_drill / baseline）要求 keyword_search 和 temporal_ordering 根据实际查的表动态归入不同阶段。
> 新版按认知深度分组后，每个意图**固定归属一个阶段**，keyword_search 固定归 log_investigate，error_timeline 固定归 log_investigate，无需动态映射。
