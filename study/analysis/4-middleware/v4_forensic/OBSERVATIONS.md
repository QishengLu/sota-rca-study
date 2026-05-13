# 12 个 wrong→correct case · 用户观察笔记

**目的**：在 case-by-case 深入审核 12 个翻盘 case 期间，把每一轮发现的设计缺陷 / 改进想法 / 待讨论问题记录在这里，**不立即下结论，等全部 12 个看完再统一讨论 v4.1 改进方案**。

**进度**：✅ 9 / 12  ·  Case 281 / 572 / 807 / 1114 / 1143 / 1394 / 2390 / 2988 / 3059 完成

---

## v4.1 设计决策（用户确认）

### D1 · 维度卡片库全部改写为英文（2026-04-27）

**问题**：[`Deep_Research/middleware/v4/dimension_cards.py`](../../Deep_Research/middleware/v4/dimension_cards.py) 里 M1-M8 的所有字段（tagline / trigger / intervention_template / conflict）都是中文写的。advisor user payload 因此混合两种语言：英文 system prompt + 英文 trajectory snapshot + 中文维度卡片。

**后果**：opus 输出 intervention_text 时语言不可控——大多数 case 出英文，但 case 3059 mid 干预出中文（因为 LLM sampling 跟随了卡片语言）。

**v4.1 修复**：dimension_cards.py 中所有字段统一改为英文（与 system prompt 一致）。

**触达范围**：M1, M2, M3, M4, M5, M6, M7, M8（如果 v4.1 加 M9/M10/M11 也走英文）。

### O13 · 中文输出 + HARD 违规组合（case 3716）

**实证发现**（用户记录 2026-04-27）：53 case 中目前观察到 2 个中文干预（case 3059, case 3716），其中 case 3716 是 53 case 中唯一标 🔴 HARD 违规的样本：

[case 3716 conclusion intervention 原文](case3716_review.md):
> "...如果这个候选服务完全健康、没有任何重启，你在 traces 里看到的那些 503 错误还会发生吗？**ts-preserve-service 的 Error 状态还会出现吗？**...你有没有查过这个服务重启的直接原因（比如 **OOMKilled、liveness probe 失败**、还是其他）？"

| 违规元素 | 类别 | 等级 |
|---|---|---|
| `ts-preserve-service` | 服务名硬编码 | 🔴 HARD（违反原则 4 #3）|
| `OOMKilled` | 故障机制硬编码 | 🔴 HARD（违反原则 4 #2-3）|
| `liveness probe 失败` | 运行时层具体词 | 🟠 MEDIUM |

**假设**：中文输出激活的 LLM 风格更"详细解释"，advisor 倾向列举具体故障类型。case 3716 + case 3059 都是中文干预，case 3716 出 HARD violation；其他 6 case 英文干预，最高只到 STRONG（case 1143 EXTREME 是 SQL operation 级，但服务名/故障机制级别是 STRONG）。

**实质后果**：case 3716 conc 后 R67 agent think 完全照抄 advisor 列出的 4 个故障类型（OOMKilled / liveness probe / Resource constraints / Dependency failures），R68-R83 真去查这些——**这不是元认知贡献，是 advisor 直接喂答案**。

**v4.1 修复关联到 D1**：维度卡片改写为英文后，需要扫一遍卡片模板里是否含具体故障机制名（OOMKilled / RabbitMQ / DNS / liveness probe 等），把这类硬编码全部替换为抽象表述（如 "the direct cause of the restart"）。

---

---

## Case 281 · `ts0-ts-station-food-service-stress-j5qdln` ✅

**结果**：MW 真承重（M6 mid 干预触发 baseline 对比 → R32 首次 normal_logs query → R42 anchor flip 75x latency）。

### 用户观察

#### O1 · M8 conclusion 干预用了"database-level"——违反 v4 原则 4 #2-3

> 原则 4 #2: 不能写出具体的表名、SQL 字符串、列名、metric 名
> 原则 4 #3: 不能列出服务名、错误消息字串、领域专有名词

case 281 conclusion 干预原文：

> "It's also worth asking: **the database-level errors you found** — could those be a symptom of something acting on that service from outside, rather than a fault that originated inside it?"

advisor LLM (claude-opus-4-7) 在生成 intervention text 时，从 trajectory 里读到 agent 提到 `Duplicate entry on station_store_idx` → 自然地用了 "database-level errors" 这个**具体层级**词。

#### 全 53 case 量化扫描结果

| 违规类别 | 出现次数 | top 词 |
|---|---:|---|
| **方向词**（`origin / victim / upstream / downstream`）| **68 次** | origin (37), victim (28), downstream (3) |
| **runtime-layer 词**（`JVM / container / k8s / GC`）| **21 次** | JVM (7), container (7), k8s (4), GC (2) |
| **data-layer 词**（`database / mysql / rabbitmq`）| **6 次** | database (4), database-level (1), rabbitmq (1) |
| **故障机制硬编码** | **2 次** | OOMKilled |
| **服务名硬编码** | **1 次** | ts-preserve-service (case 3716) |

**总：54 / 97 干预 = 56% 含某种程度违规**。

#### 三级违规分级

| 级别 | 描述 | 案例 |
|---|---|---|
| 🟡 MILD | 引用 agent 自己已说过的领域词 | case 281 "the **database-level errors you found**" |
| 🟠 MEDIUM | advisor 主动列举具体层级 | case 1421 mid: "container resource, JVM, network-level signals" |
| 🔴 HARD | 服务名 / 故障机制名硬编码 | case 3716: "OOMKilled、liveness probe" + ts-preserve-service |

#### O2 · M8 卡片本身就违反原则——origin/victim 是禁词

`origin / victim` 这对词在 conclusion 干预中出现 65 次（占 47 个 conclusion 干预的 137%——平均每个干预出现超过一次）。

但 v4 原则 4 #4 明确禁止方向性概念："上游/下游/源/汇/受害者/故障源"。

**这是 M8 卡片设计阶段就埋下的违规**。M8 prompt 模板基于"victim-vs-origin"二分判断，advisor LLM 继承了这个词汇。

**潜在因果链**（待全 12 个 case 看完再验证）：

```
M8 卡片设计 → advisor 大量用 origin/victim 二分语言 → qwen 跟着做"是不是 victim"判断
         → 在 cascade 故障里 victim 也表现出"如果它健康，cascade 错就不会发生"
         → agent 加固对 victim 的锚定 → A1 victim-shifted 失败模式 (34% 未救 case)
```

#### 待讨论的设计问题

1. v4 实现里**没有 post-filter 步骤**——LLM 输出什么就是什么，没有领域脱敏环节
2. 维度卡片设计阶段就允许了原则 4 禁词（origin/victim, JVM/container/k8s 等都在 M-card 里出现）
3. trade-off：完全去掉具体词 → 干预太抽象 agent 不知道在指什么；保留具体词 → 违规且可能误导

#### 暂存的 v4.1 改进 idea（**等全 12 个看完再确认**）

- ⚪ 给 advisor LLM 加 post-filter 步骤（去除服务名 / 数据层名 / 方向词）
- ⚪ 重写 M8 卡片，把"victim/origin 二分"改为"internal-failure vs external-call-failed 归类"
- ⚪ 维度卡片审核增加"原则 4 禁词扫描"

---

## Case 572 · `ts1-ts-food-service-response-patch-body-qjhx5h` ✅

**结果**：v4 advisor **0 干预**（**真因：mid + conc 都因 claude-opus-4-7 API 400 错误降级**，agent 没收到任何中间件信号）。v4 因部分匹配 GT 被 judge 算 correct。

### 用户观察

#### O3 · "右答案 + 错推理" 现象（修正：评分计算 = 设计正确）

v4 推理把 `ts-food-service` 当 RC 的理由是它有 "earliest error timestamp + UnknownHostException ts-rabbitmq"。但：
- 这个 DNS error 在 normal 期间出现 **233 次** vs abnormal 157 次 → 是 **chronic background noise**
- 真实故障是 HTTP body 被 patch（trace 层信号），agent **从未查过 ts-train-food-service** 的任何数据

v4 pred `[ts-food-service]` ∩ GT `[ts-food-service, ts-train-food-service]` ≠ ∅ → judge 算 correct。

**用户澄清**：partial match 是 judge 的**设计**（GT 多服务时 agent 命中任一即算对），这部分是正确的。这个 case 的"对答错由"现象只是评测设计内的合理结果，不算 judge bug。

但仍然值得记录的是：**v4 在这个 case 里完全没起作用**（API 错误降级），翻盘归因不能算 MW 功劳。

#### 🚨 O4 · v4 实测中遭遇 API 错误降级（系统性问题）

扫全 53 case 的 advisor 日志（`Deep_Research/logs/v4-run/idx_*.log`）发现：

| 状态 | 数量（共 53）|
|---|---:|
| mid 干预 FIRED | 47 |
| mid 因 API 400 降级 NOT triggered | **4** (case 315, 572, 1934, 3059...) |
| mid advisor 主动判断 false | 1 (case 2678) |
| mid 解析失败 | 1 (case 3114) |
| **conc 干预 FIRED** | **50** |
| **conc 因 API 400 降级 NOT triggered** | **3** (case 572, 784, 3059) |

**API 错误信息**：
```
Error code: 400 - 'Invalid model. Please select a different model to continue.'
reason: INVALID_MODEL_ID
```

shubiaobiao API 偶发返回这个错（约 6-8% 失败率）。降级逻辑（`triggered=false`）让 agent 静默失去这次干预。

**待讨论的设计问题**：
- 当前实现：API 错误 → 直接 `triggered=false` → agent 没收到任何提示
- 改进方向：API 错误 → retry N 次 → 若仍失败用 fallback prompt（基于 trajectory 简单规则触发预设干预）→ 至少不让"必备"的 conc 检查空过
- 影响范围：可能 5/53 = 9.4% case 的 v4 表现被这个问题拖累；如果修了 retry，翻盘率可能从 22.6% 上升

#### 暂存的 v4.1 改进 idea

- ⚪ Advisor LLM call 加 **重试 + fallback prompt** 机制
- ⚪ 区分 advisor "主动判 false" vs "API 失败降级" 两种情况，前者正常后者要 retry/告警

---

## Case 807 · `ts1-ts-train-service-stress-jfr96k` ✅

**结果**：M7 承重（runtime layer 提示让 agent 查 ts-train-service 自己的 CPU + container restart metric → 找到 92% spike + 14:42:12 restart）。但**M7 是延迟生效**：触发后 14 round 后才真正切到 metric 层。

### 用户观察

#### O5 · M7 trigger 实现 vs 卡片描述不一致（实现 bug）

M7 卡片（[v4_dimensions/M7_layer_coverage_reflex.md](../v4_dimensions/M7_layer_coverage_reflex.md)）说 `runtime_layer_intents = 6 个`（含 `metric_scan`），但 v4 state.py 代码里 `RUNTIME_LAYER_INTENTS = 5 个`（不含 metric_scan）：

```python
# Deep_Research/middleware/v4/state.py
RUNTIME_LAYER_INTENTS = {
    "container_resource", "jvm_state", "network_layer", "k8s_state", "db_state"
}
# metric_scan 在 PHASE_MAP 里被归到 "triage"（应用层）
```

**实际影响**：agent 跑 `SELECT DISTINCT metric FROM abnormal_metrics`（被分到 metric_scan）→ 按卡片应算运行时层不触发 M7，但按代码算应用层仍触发。**M7 实际比卡片描述更激进**。

#### O5b · 修正 O5：metric_scan 应该归 runtime layer（1 行代码 fix）

[v4 state.py](../../Deep_Research/middleware/v4/state.py) 把 metric_scan 在 PHASE_MAP 里归到 "triage"，且 RUNTIME_LAYER_INTENTS 不包含它。**M7 卡片设计里 metric_scan 属于 runtime layer**——直接对齐：

```python
RUNTIME_LAYER_INTENTS = {
    "container_resource", "jvm_state", "network_layer", "k8s_state", "db_state",
    "metric_scan",   # ← 加这一行（卡片对齐）
}
PHASE_MAP["metric_scan"] = "metric"  # 原 "triage"，改为 "metric"
```

**潜在影响**：M7 触发条件变严格（之前 metric_scan 不算 runtime → M7 仍触发；改后算 runtime → M7 不触发）。需在历史数据上重放评估，估计触发量降低 5-10%。

#### O5c · M7 干预 prompt 列具体层名是有意的违规（trade-off 选择）

[M7 卡片](../v4_dimensions/M7_layer_coverage_reflex.md) "重要审核点 #2" 原文：

> "Intervention 中列了'容器、进程、网络、数据库'作为括号内例子。这是引导吗？我的判断：不算引导——这些都是 RCA 任务中的标准层级名称。**但若审核认为'列出层级清单'也算暗示，可改成只说'运行时层'不展开例子——但会降低 agent 对该建议的可执行性**。"

**结论**：v4 卡片作者**有意识地**为 actionability 牺牲了脱敏度。**但**：M7 这个 trade-off 决策**扩散到了所有维度**——advisor LLM (opus-4.7) 看到 M7 列具体例子，开始在 M8 conclusion 也列具体词（database-level / OOMKilled / origin-victim）。**56% 干预含违规词是这个口子的连锁反应**。

**改写候选**（v4.1 提议）：
```
当前: "你目前的调查集中在应用层（日志和 trace），还没有看过候选服务的运行时层数据..."

候选 A（中性 metrics 表述，保留 actionability，不强调异常）:
"trajectory 里 metric 类的表（含 normal_metrics、abnormal_metrics 以及它们的 histogram / sum 聚合表）你都没碰过——
 这一类数据跟你查过的 logs/traces 视角不重叠。在 commit 前，能不能用同样精度的方法去看看？"

（用户反馈 2026-04-25：不应强调 'abnormal' 表，要把 normal + 聚合表一起列上让 agent 自己决定。）

候选 B（更抽象，最大脱敏）:
"trajectory 里有一类数据你完全没用过。同样的故障在不同数据视角下可能呈现非常不同的形态。
 回去看一下你没查过的那类数据，确认它们对你的判断是支持还是冲突。"
```

候选 A 指向"另一张表"（actionable），但不暗示故障类别。

#### O6 · 19 类 intent 漏掉了多个故障层

19 类 intent 只覆盖：应用层（11） + 运行时层（5） + 基线对比（2）= 17 个有效层。完全没覆盖的层：

| 漏掉的层 | 典型故障 | 影响的 case |
|---|---|---|
| **HTTP body 内容层** | `HTTPResponsePatchBody` / `HTTPResponseReplaceBody` | case 572（saved 但右答错由）、case 860, 2836 |
| **时钟偏移层** | `TimeSkew` | case 323, 3878 |
| **DNS / L3 网络层** | `DNSRandom`（hubble 是 L7 不是 DNS）| case 1421 |
| **业务一致性层** | "订单存在但支付未触发" | T7_Business-Logic-Confabulation 全类 |
| **配置 / 部署变更层** | image 变更、env var 变更 | （间接被 k8s_state 触及）|
| **存储 / 磁盘 IO 层** | disk full / fd 耗尽 | （未观察到具体 case）|
| **长期性能漂移层** | 慢 leak / 长 trend 异常 | （需要 trend 而非单时段对比）|
| **认证授权层** | 401/403 | （归到 service_error_log）|
| **HTTP request 模式层** | payload 异常 | （未观察到具体 case）|

**关键含义**：
- M7 只能在"应用层 ↔ 运行时层"之间触发反思
- 对于 HTTP body / TimeSkew / 业务逻辑类故障，**M7 即使触发也救不了**，需要新维度
- 这解释了 task2 里 T6/T7/T8 三类故障 0 救活率

#### 🚨 O6b · 重要修正：这些"漏掉的层"其实**数据基本都在 parquet 里**

实测 4 个代表性 case 的 parquet 数据：

| 故障 | case | 数据是否完整？ | 信号位置 | 真正的盲区 |
|---|---|---|---|---|
| HTTPResponsePatchBody | 572 | ✅ 完整 | abnormal_logs: `foodStoresListResult is null` 11 行 | M6/M7 都不针对"业务级 NULL/parse 错"反思 |
| DNSRandom | 1421 | ✅ 完整 | abnormal_logs: `UnknownHostException`（混 chronic noise）| 需 baseline 对比 + 信号语义辨识 |
| TimeSkew | 323 | ✅ 完整 | abnormal_traces: 15 个 span duration > 5s（max 21.5s）| 没有"trace duration anomaly"专门维度 |
| PodKill 业务一致性 | 3114 | ⚠️ 部分 | container.restarts=0（PodKill 不留痕）+ deployment.available=1 + app log "Order already exist" | 基础设施层数据局部缺失 + 维度盲区 |

**关键修正**：之前我说"19 类没覆盖这些层"暗示数据缺失，**实际不准确**。准确说法：

- **数据基本都有信号**（app log + trace 都能反映 9 大类故障的副作用）
- **缺的不是数据，是"信号语义辨识"维度**——agent 看到 `foodStoresListResult is null` 不知道是 patched body 的下游副作用；看到 `21s span` 不知道是 TimeSkew 而不是 latency degradation
- **真正的数据盲区只有 1 类**：长期性能漂移（dataset 设计就只覆盖 4 min normal，不能做 trend）+ PodKill 的 container.restarts/deployment.available 部分缺失

**这归到"分析难点"而不是"数据难点"**。需要新的 v4 维度专门处理"业务级 NULL / parse error / span duration anomaly / 业务逻辑 retry 错误"这类信号。

---

#### 🚨 O6c · 2026-04-25 修正：实测因果链推翻"信号都在"的乐观判断

跑了 4 个 case 的 normal vs abnormal SQL（duckdb 直查 parquet），发现之前的论断**部分是错的**：

##### Case 572 HTTPResponsePatchBody（实测）

| 指标 | normal | abnormal | 解读 |
|---|---:|---:|---|
| `foodStoresListResult is null` | 15 行 | 11 行 | **chronic noise！normal 比 abnormal 多** |
| ts-train-food-service trace status | 全 Unset/200 | 全 Unset/200 | trace 层无 error 信号 |
| ts-train-food-service span max duration | 17 ms | 522 ms | **30x 升 — 唯一真信号** |

→ **chaos 不改 status_code → error_rate 维度全失效**；M6 baseline 对比反而**否决**真信号（agent 看到 "foodStoresListResult is null" 在 normal 更多 → 判 chronic 抑制）。**真信号只在 trace duration**。

##### Case 1421 DNSRandom（实测）

| 指标 | normal | abnormal | 解读 |
|---|---:|---:|---|
| ts-station-service ERROR/SEVERE log | 0 | 0 | **GT 服务完全 silent** |
| ts-station-service trace count | 8120 | 4880 | **跌 40%** — 唯一信号 |
| 专门 DNS metric | (无) | (无) | hubble 是 L7 不含 DNS |

→ DNS chaos 让 GT 服务自己**无任何 log/trace error**。真信号是 **trace count 跌 40%**——v4 无维度检测。

##### Case 323 TimeSkew（实测）

按 max_duration_ratio 排序，**GT 服务 ts-travel-plan-service 排第 5（4.3x）**，而下游受时钟传播污染的 ts-order-service 排第 1（19.6x）、ts-order-other-service 第 2（18.8x）等。**duration spike 启发式会锚定错服务**。

##### Case 3114 PodKill（实测）

| 信号 | 状态 |
|---|---|
| `k8s.container.restarts` | 0（新 pod 算 restart=0，旧 pod 已 kill 不上报） |
| `k8s.deployment.available` | 一直 = 1（多 replica 设计） |
| `Order already exist` log | normal 160 vs abnormal 120（**chronic noise**） |
| trace count drop | normal 1053 → abnormal 623（**40% 跌**）|
| `Order already exist` 时间聚集 | 7 秒内 8 行集中爆发（隐藏信号）|

→ 多 replica 部署 + chaos kill 不留传统痕迹；只剩 trace count drop + 事件聚类两个隐藏信号，**v4 无维度**。

##### 修正后的难点矩阵

| 故障 | 数据难点 | 维度难点 |
|---|:-:|:-:|
| HTTPResponsePatchBody | ⚠️ 部分（status 不变需 duration 维度）| 🔴 M6 反作用 + 缺 duration anomaly 维度 |
| DNSRandom | 🔴 数据缺 DNS metric | 🔴 缺 trace count drop 维度 |
| TimeSkew | ❌ 不是数据问题 | 🔴 max duration spike 启发式误导 |
| PodKill 业务一致性 | ⚠️ 多 replica metric 缺失 | 🔴 缺 silence detection + 事件聚类维度 |

##### 暂存的 v4.1 改进 idea

- ⚪ 新维度 **M11 · Trace Count Anomaly**：检测某服务在 abnormal 窗口的 trace count 比 normal 显著下跌（DNSRandom + PodKill 类）
- ⚪ 新维度 **M12 · Duration Spike Path Localization**：max duration 出现时引导 agent 沿调用树**向上**定位"wait gap 起点"而不是停在 spike 末端（TimeSkew 类）
- ⚪ 新维度 **M13 · Status-Invariant Body Anomaly**：status 全 200 但 duration / log NULL pattern 异常时 → 怀疑 body / payload 类故障（HTTPResponsePatchBody 类）
- ⚪ M6 改进：baseline 对比时区分**"chronic message 的密度变化"**vs**"chronic message 的存在/缺失"**——case 572 里 "foodStoresListResult is null" 减少不代表故障消失
- ⚪ **DNS metric 数据补全**（数据集层面）：未来给 trainticket 加 DNS resolution metric

---

#### 🚨 O6d · 2026-04-25 第二轮修正：上一轮修正本身也有错（用户挑战 4 个因果链）

用户挑战每个故障的因果链是否真成立，跑深入数据后**第二轮修正**（之前的因果论断有多处错）：

##### 修正 1 · HTTPResponsePatchBody (572)：duration 30x 是单点 outlier

之前说"duration normal 17ms → abnormal 522ms (30x) 是真信号"。

**实测**：1609 个 abnormal spans 中，**只有 1 条**是 522ms。同 span_name 的 **avg 几乎不变**（normal 6.12ms vs abnormal 6.78ms）。**那条 522ms 是孤立 outlier，不是 patch chaos 因果。**

**真相**：HTTPResponsePatchBody 不改 status_code，不改 duration（除非 chaos 引擎有额外开销），只改 body 字节。在当前 trainticket 数据集里**几乎完全无 incident-specific 信号**。

**case 572 的 v4 翻盘**几乎确定是 sampling 巧合 — agent 完全没看到真信号，只是 random 选了 GT 集合的其中一个。

##### 修正 2 · DNSRandom (1421)：40% drop 是系统级而非 GT 特异

之前说"ts-station-service trace count drop 40% 是 DNSRandom 信号"。

**实测**：30 个服务的 drop 分布——**绝大多数都跌 38-44%**（系统级 baseline 偏移）：
```
ts-station-service (GT)    跌 39.9%   ← 跟全系统几乎一样
ts-route-service           跌 39.8%
ts-train-service           跌 39.6%
ts-config-service          跌 38.5%
... 大部分 ...
真正异常: ts-cancel-service 跌 83%, ts-consign-service 反而 +290%
```

**真相**：abnormal 窗口整体 trace 量比 normal 低 ~40%（可能是 chaos 启动扰动了 loadgen），跟 DNSRandom 无直接因果。GT 信号比想象的更隐蔽，需要看 trace 父子关系层（"哪些 trace 没有 ts-station-service 子 span"）。

##### 修正 3 · TimeSkew (323)：不必然 duration 增加

之前说"TimeSkew 必然让 duration 增加"。

**实测**：这个 case 的 ts-travel-plan-service abnormal **没有 neg/zero duration**——是单向（正向）skew。但理论上**反向 skew 会让 duration 减小**（甚至负，会被 trace pipeline 过滤）。

**真相**：TimeSkew 的方向取决于 chaos 配置，duration 可以 increase / decrease / bimodal。我之前论断方向太单向。

##### 修正 4 · PodKill 3114 "Order already exist" 不是 retry 副作用

之前说"PodKill → 客户端 retry → 同 OrderId 撞库 → Order already exist"。

**实测**：
- normal 80 OrderIds × 2 行 = 160；abnormal 60 × 2 = 120
- 每个 OrderId **恰好** 2 行（callee + caller 各 log 一次同一次失败，**不是 retry**）
- 每秒密度 normal 2.29/sec vs abnormal 2.35/sec — **几乎相同**
- ts-preserve-service trace 按分钟：105/118/87/313 — 没有 burst 也没有 dip

**真相**：trainticket benchmark 里 **OrderId 是确定性生成的**（基于 user+train+date hash），loadgen 自然产生重复请求 → "Order already exist" 是 benchmark **自带 chronic noise**，跟 PodKill 完全**无因果**。

**case 3114 实际几乎无 incident-specific 信号**——v4 失败是合理的。

##### 方法论教训

| 错误 | 修正 |
|---|---|
| 用 max 做对比 | 必须看 distribution（avg / p50 / p95） |
| 单服务 drop 论断 | 必须跨服务对照（看是不是系统级现象） |
| 直觉因果链 | 实测验证（同 OrderId 出现次数 / 时间密度等具体维度） |
| 单方向论断（TimeSkew 必增） | 考虑双向（chaos 方向取决于配置） |

##### 对 v4.1 设计的影响

之前提出的"M11 trace count drop / M13 status-invariant body anomaly"维度**也可能不奏效**：
- M11 在 case 1421 上失败（不是 GT 特异，全系统都跌）
- M13 在 case 572 上失败（duration 不是真信号，只有 1 outlier）

**真实情况是**：HTTPResponsePatchBody / DNSRandom / PodKill 这三类故障**在 trainticket 数据集里**几乎找不到清晰 GT 信号。这意味着：
- 不是"维度盲区"的问题，是**数据信号本身就被 benchmark 噪声淹没**
- v4 在这些 case 上失败是**合理的**（不是 v4 缺陷）
- 应该把这些 case 归为 **`unsolvable:dataset-noise-floor`** 类别

**v4.1 改进重心**应该聚焦在**信号清晰**的故障（JVM stress / Pod restart / CPU spike），这些已经被 M6/M7/M5 覆盖。

#### O7 · M7 干预 prompt 中再次出现 medium 违规词

case 807 mid 干预 prompt：
> "运行时层（**容器**、**JVM**、**网络**等）的指标"

`容器 / JVM / 网络` 都是 medium 违规词（v4 原则 4 #2-3 禁止具体层名）。但 M7 卡片本身就要求 prompt 列出"哪些是运行时层" — **这是卡片设计阶段就埋下的违规**（与 case 281 M8 origin/victim 同类问题）。

**自检矛盾**：M7 卡片"自检清单"里第 7 项写"用反问 + 多种可能性"通过，但同时把"容器/进程/网络"作为括号内例子列出 — **卡片作者自己也意识到这个矛盾**（卡片末尾"重要审核点 #2"明确讨论了这个 trade-off：列了具体层提升可执行性 vs 降低脱敏性，最终选了"列具体例子"路线）。

#### 暂存的 v4.1 改进 idea

- ⚪ M7 trigger 实现统一（卡片和代码对齐 metric_scan 的层归属）
- ⚪ 给 19 类 intent 增加"层维度"扩展（HTTP body / TimeSkew / 业务一致性）
- ⚪ 重新审视 v4 维度库的层覆盖矩阵

---

## Case 1114 · `ts2-ts-config-service-stress-j8gm95` ✅

**结果**：M5 mid 干预**单独承重**（R30 触发 → R31 立即跑非常规 SQL "找 normal child 看 abnormal 缺啥" → R38 think_tool 显式复述 advisor → R35-R45 anchor flip 到 ts-config-service 并锁定 restart 0→1 信号）。conc 干预 R78 是 supporting（agent 已答对，只加固）。

GT 信号非常强：container restart 0→1（vs ts-ticket-office-service 3→3 chronic）+ container CPU 排第一（avg 0.77 比第二名 5x）+ jvm.system.cpu 2.34× + k8s.pod.memory.page_faults 2.95× + span duration 分布偏移（5-50ms 桶 16×、>500ms 桶 23 条 vs normal 0）。baseline 失败模式 **T1 Silence-as-Health**：anchored 在 ts-seat-service 的 117 个 Error span（loud victim），把 ts-config-service 的 "Unset" 当成 "healthy"，75 round 一次都没查 ts-config-service 自己的 metrics/restart。

### 用户观察

#### 🟢 O8 · M5 干预的有效成分**不依赖**禁词（比 M7/M8 trade-off 缓和）

case 1114 mid 干预原文同时含：
- ✅ **真正起作用的成分**：`silent in your data not because healthy` / `absence of signal ≠ absence of problem` / `a service that should appear in the call path but doesn't`
- ❌ 违规词：`originates`（原则 4 #4 禁词）+ `showing connection failures`（引用 agent 自己的具体发现，O1 同款 MILD 违规）

但 agent R38 think_tool 复述时用的是 "**MISSING**"——是从抽象的 silence/absence 概念抓住要点，**没用** "originates" 这个方向词。

**结论**：M5 卡片完全可以去掉 `originates`、`fault originates` 这种方向语言，**actionability 不会下降**——因为 "silence/absence/missing-in-call-path" 已经足够具体可操作。这比 case 281（M8 origin/victim 二分语言已经写进卡片设计）+ case 807（M7 trade-off 主动选择列具体层名）的 trade-off 都更乐观。

**v4.1 改进 idea（暂存）**：M5 卡片去除 origin/originates 词族，保留 silence/absence/should-appear-but-missing 概念语言。

#### 🟡 O9 · v4 agent 自己犯了 "max-only" 错，但 case 1114 信号强足以挽救

v4 R82 think 写 "**Latency comparison: ~1.8ms vs ~926ms (500x increase!)**"——但 926ms 是单条 outlier，真实分布是 avg 3.7× / p95 2.6× / p99 7.8×（不是 500x）。

实测桶分布（验证不是单点）：

| bucket | normal | abnormal |
|---|---:|---:|
| 5-50ms | 75 | **1215** ← 16× |
| >500ms | 0 | **23** ← normal 完全无 |

**关键观察**：case 1114 的 GT 信号有多条独立强信号（restart + CPU + page_faults + duration distribution），即使 agent 用了错误的 "500x" 叙述也指向了对的服务。但**如果在信号更弱的 case 里用 max-only 论证，可能锚定到 outlier 服务**。

这是 **agent 的推理瑕疵，不是 MW 的问题**。但提示了一个潜在维度："look at distribution, not max alone"。先存档，等更多 case 看完再决定是否需要 M14。

#### 案例特定要点

- 翻盘是真承重（不是 sampling 巧合）：R31 的 SQL 模式（`SELECT ... FROM normal_traces WHERE parent_span_id IN ... 'ts-seat-service' AND span_name='GET'`）是 advisor 提示后立即执行的非常规查询，baseline 75 round 没跑过类似 SQL；R38 think 显式引用 "the advisor"
- M5 的成功有前置条件：normal_traces 里**能看到 GT 服务的父子调用关系**。如果 normal trace 也没记录该调用（极端情况），M5 找不到"该出现但没出现"的目标
- ts-ticket-office-service 是漂亮的 distractor：它在 normal+abnormal 都有 3 次 restart（chronic）且在 abnormal 期完全 silent（没 log/trace）。R51 think 一度被它吸引，但 R46 按 pod_name 拉详情后明确区分了"chronic vs new"

---

---

## 🚨 O10 · v4 advisor 输入泄漏 —— 系统性问题，影响所有"承重"判断（2026-04-27）

**用户挑战触发**：case 1114 mid intervention 出现 "showing connection failures" 这种引用 agent 自己 reasoning 的具体词。我去查 [`metacognitive_advisor.py:208-290`](../../Deep_Research/middleware/v4/metacognitive_advisor.py#L208-L290) + [`state.py:196-293`](../../Deep_Research/middleware/v4/state.py#L196-L293) 实现，确认了严重设计漏洞。

### 实际喂给 opus-4.7 advisor 的内容

`_render_user_payload` 构造的 user message 含：

| 字段 | 内容 | 是否含 agent 推理原文 |
|---|---|:-:|
| `[B1 INTENT LOG (last 40)]` | 每条 SQL 的 intent + services | ✅ 具体服务名 |
| **`[B2 RECENT REFLECTIONS (last 5)]`** | **think_tool reflection + assistant_content 原文，每条 ≤1500 字符** | ✅ **完整原文** |
| **`[B2 EARLIER SUMMARY]`** | 早期 reflection tail-10 condensed (200 字符 × 10) | ✅ 拼接原文 |
| `[B4 WHERE-FILTER SERVICES]` / `[B5 OBSERVED SERVICES]` | SQL 触及的所有服务名 distinct list | ✅ 具体服务名 |
| `[B7 LAST RANKING TOP-3]` | agent 自己排名的 top-3 服务 | ✅ 具体服务名 |
| **`[CANDIDATE ROOT CAUSES]`** | **`_update_draft_rc()` 从 reasoning 启发式抽出的根因候选** | ✅ **直接抽答案候选** |

`extract_reasoning(tool_calls, assistant_content)` 在每个 round 后被调用：
```python
if reflection: self.reasoning_log.append(reflection[:1500])           # think_tool 原文
if assistant_content and len(assistant_content) > 50:
    self.reasoning_log.append(assistant_content[:1500])                # assistant 原文
```

### 这违反了 v3 CLAUDE.md "设计原则 #1"

> "中间件观察 agent 的**行为模式**...绝不提示具体该查哪个服务、哪张表、或答案方向"

v4 实现把 reasoning 原文 + 服务名列表 + 启发式根因候选**全部喂给 opus**。opus 不是在"独立判断方法论缺陷"，而是"看着 agent 的草稿 reasoning 写一段维度包装的回写"。

### case 1114 实测：opus 看到了什么

R30 mid 触发时，v4 reasoning_log 含 R3 / R6 / R17 三条 think_tool reflection（共 ~3000 字符），其中：
- R6 已写："**ts-food-service** has the earliest errors / **ts-rabbitmq is unavailable** / Notification service has 'Failed to redeclare queue'"
- R17 已写："**ts-seat-service** has Error status / what's causing **ts-seat-service** to fail"

加上 `[B5 OBSERVED SERVICES]` 必然含 `ts-config-service`（R8-R10 trace queries 已触及但 reasoning 里 0 次提到）。

opus 的 mid intervention "**another service that may not be surfacing loudly in rankings**" + "**a service that should appear in the call path but doesn't show up**" 本质上就是利用了 `[B5 observed]` 与 `[B7 ranking + reasoning anchor]` 的不对称——**opus 不需要看到 GT 答案，它只需要看到"agent 还没 commit 的隐藏候选"**。

### Leakage 等级分级（基于 53 case 的实证）

| 等级 | 描述 | 示例 |
|---|---|---|
| 🔴 STRONG | advisor 直接复述 agent reasoning 的具体词 | case 281 "the **database-level errors you found**" 复用 agent "Duplicate entry on station_store_idx" |
| 🟠 MEDIUM | advisor 利用 `[B5/B7]` 不对称信号回写 silent candidate | case 1114 "another service that may not be surfacing loudly" |
| 🟡 MILD | advisor 复述 reasoning 概念但概括化 | case 1114 "showing connection failures" 概括 R17 "what's causing X to fail" |
| 🟢 NONE | advisor 只用维度库语言，不引用 reasoning | M7 "trajectory 里有一类数据你完全没用过" |

### 已审核的 case 必须加的 caveat

- **case 281** M6 承重 → 需重判：advisor 是否从 reasoning 里拿到 "Duplicate entry" / "database" 等词后回写？是的（已有 STRONG leakage）
- **case 807** M7 承重 → 需重判：advisor 是否看到 reasoning 里 agent 已经查过 metric 但 anchor 在 log？需查 v4 R20 之前的 reasoning_log
- **case 1114** M5 承重 → **降级为 MEDIUM leakage**：opus 看到了 `[B5]` 里 ts-config-service 没 anchor + reasoning 里 "what's causing ts-seat-service to fail"，回写 "silent dependency"

### 影响范围

**所有 53 case 的 mid + conc 干预都受这个 leakage 影响**。"M5/M6/M7/M8 承重" 这种判断**只在 leakage 程度低的子集上有意义**。

### 53 case 量化扫描必须做（在结案 12 case 后）

1. 对每条 intervention 文本 vs reasoning_log 跑词频对照（共现的具体词）
2. 标 STRONG / MEDIUM / MILD / NONE
3. 推算"真实独立维度承重"的 case 数（vs leakage-driven）
4. 如果 STRONG/MEDIUM > 50%，**v4 的"22.6% 翻盘率"需要再保守化**

### 暂存的 v4.1 改进 idea

- ⚪ **(a) 完全移除 reasoning 原文**：advisor 只看 intent_log + 行为统计 — 但干预可能太抽象
- ⚪ **(b) 移除 B5/B7/draft_root_causes 字段**：保留 reasoning_log 但不喂服务名列表 — 中度脱敏
- ⚪ **(c) Service-name redaction**：把 reasoning 里的具体服务名替换成 `<SVC_A>` `<SVC_B>`
- ⚪ **(d) 重新分工**：deficiency-detector 看完整 reasoning，intervention-generator 只看 deficiency 标签 + 维度库 — 跟 v3 双层架构思想一致
- ⭐ **(c+) 完全去掉 opus，单模型 qwen3.5 self-coaching**：opus 只用在 SQL→intent label，其他全部 qwen3.5 自反思。用户决策（2026-04-27）：**12 case 看完后实测 qwen3.5 在 intent labeling 上的准确率，若可用则连 opus 都不再需要**，整个 v4.1 单模型实现。

### 用户决策（2026-04-27）

**确定走方向**：方案 (c+) — 单模型 qwen3.5 self-coaching。

**12 case 看完后立即做的实验**：
1. 取已有的 opus intent labels（53 case × 平均 35 SQL/case ≈ 1800 条）作为 ground truth
2. 用 qwen3.5-plus 跑同一批 SQL 重新打标
3. 量化 qwen3.5 的 intent labeling 准确率（19 类多分类 accuracy / per-class F1）
4. 若准确率 ≥ ?%（阈值待定，可能 85%+），则 v4.1 完全去掉 opus，全部 qwen3.5

**审稿人辩护准备**：方案 (c+) 的 contribution 三件套——
1. D×R 失败归纳（105 case → M1-M8 维度卡片，经验贡献）
2. Checkpoint timing（query 37/44 数据驱动，时机贡献）
3. Self-coaching template（不引入外部 oracle，单模型可复现，架构贡献）

需要的 ablation：baseline / generic-reflection-at-checkpoint / dimension-cards-at-checkpoint —— 三组隔离维度卡片的贡献。

**优先级建议**：**(c+) > (d) > (b) > (c) > (a)**。(c+) 是审稿人攻击面最小、可复现性最强、方法论叙事最干净的方案。

---

## Case 1143 · `ts2-ts-food-service-container-kill-cqcxsh` ✅

**结果**：M7 mid 承重（runtime layer reflex），M5 secondary 有效（驱动 R31 选 silent service）。GT 信号非常强：ts-food-service container restart 0→1 + jvm.class.loaded 1.25→6705（5364×，JVM cold-start 指纹）+ container.cpu.time counter reset（568→129）+ 47 秒 trace silence gap @ 08:26:57-08:27:42。baseline 35 round 完全踩坑 T3 Noise-Anchor：把 RabbitMQ DNS 错误（normal 141 vs abnormal 109，chronic noise）当成 fault chain 起点。

**但 leakage 等级达到 EXTREME**——advisor mid 干预直接引用 agent R25 SQL 操作（`WHERE value != value` NaN check）+ R24 think 反思（"log says failure but trace says 200"）。这不是概念回写，是 SQL operation level 复述。

### 用户观察

#### 🔴🔴 O11 · advisor 复述 agent 具体 SQL operation（leakage 等级扩展为 EXTREME）

case 1143 mid 干预原文 vs agent reasoning 对照：

| 干预 phrase | agent 来源 | leakage |
|---|---|---|
| "You found **NaN values in duration metrics**" | R25 SQL `WHERE value != value` | 🔴🔴 EXTREME — operation level |
| "a **mismatch between what logs report (failures) and what traces show (200 responses)**" | R24 think 原文 | 🔴 STRONG |
| "container resource limits, JVM memory pressure, or network-level issues" | M7 卡片 | 🟡 MILD |
| "one of your candidate services doesn't appear in the current ranking at all" | [B5/B7] 不对称 | 🟠 MEDIUM |

**leakage 等级矩阵扩展**：

| 等级 | 描述 | 案例 |
|---|---|---|
| 🔴🔴 EXTREME | advisor 复述 agent 具体 SQL operation | case 1143 "NaN values in duration" |
| 🔴 STRONG | 直接复述 agent reasoning 具体词 | case 281 "database-level errors you found" / case 1143 "log/trace mismatch" |
| 🟠 MEDIUM | 利用 [B5/B7] 不对称信号回写 silent candidate | case 1114 "may not be surfacing loudly" |
| 🟡 MILD | 概括 reasoning 概念 | case 1114 "showing connection failures" / case 1143 "JVM memory pressure" |
| 🟢 NONE | 纯维度库语言 | M5 "absence ≠ healthy" / M7 "trajectory 里有一类数据" |

**对方案 (c+) 的影响**：case 1143 是当前最强的 leakage 论证案例。在审稿人眼中，case 1143 翻盘的 22.6% 的"贡献"几乎可以全部归因于 opus 把 agent 自己 R24 反思包装成 M7 干预——**没有维度卡片的独立贡献**。

#### 🟡 O12 · ts-ticket-office-service distractor 是反复出现的 trainticket benchmark 模式

case 1114 + case 1143 都遇到 ts-ticket-office-service 的 chronic 3 restarts distractor（且都在 abnormal 期 first sample 出现）。这是 trainticket 部署里 ts-ticket-office-service 长期处于 crash-loop 状态——**不是 fault-specific signal**。

**v4.1 数据预处理 idea**（暂存）：在 abnormal_metrics 里预先过滤跨 normal+abnormal 都恒定的 chronic anomalies（如 restart count 在两期都=3 的服务），减少 agent + advisor 都被误导的概率。这是**数据集 hygiene** 改进，不是 v4 框架改进。

### 案例特定要点

- M7 mid 真承重 + leakage 同时存在：trigger → R31 立即转 runtime metric → R32 在 ts-food-service 上找到 cpu=0.0 + restart 1。但 advisor prompt 已经把方向 amplify 出来——有/没有维度卡片的反事实无法区分
- M5 secondary 也有效：advisor 提示 "one service doesn't appear in ranking" 后 agent R31 直接选 ts-train-food-service（[B7] 里没出现）→ 这是 [B5/B7] 不对称的精确利用
- ts-ticket-office-service 在 R37 把 agent 短暂带歪（"earliest anomaly @ 08:26:56"），但 R39-R63 通过 "不在 foodservice 调用链" 排除掉
- ContainerKill 三件套指纹（restart=1 / jvm.class.loaded 5000+ / container.cpu.time counter reset）是 trainticket 数据集**最清晰**的故障类——v4 在这类信号上几乎不可能失败，包括 baseline 也大概率能解出，**baseline 失败原因是被 RabbitMQ chronic noise 锚定，不是数据缺信号**

---

## 待审核的 case 列表

| # | dataset_index | tier | theme | 承重维度 | 状态 |
|---|---:|---|---|---|---|
| 1 | 281 | ultra_hard | T2 Blame-the-Messenger | M6 | ✅ 完成 |
| 2 | 572 | stable | T4 Amplitude-Greed | — (API 降级) | ✅ 完成 |
| 3 | 807 | stable | T1 Silence-as-Health | M7 | ✅ 完成 |
| 4 | 1114 | ultra_hard | T1 Silence-as-Health | M5 | ✅ 完成 |
| 5 | 1143 | ultra_hard | T3 Noise-Anchor | M7 + leakage:EXTREME | ✅ 完成 |
| 6 | 1394 | ultra_hard | T1 Silence-as-Health | M7 | ⏳ 下一个 |
| 7 | 2390 | stable | T3 Noise-Anchor | M6 | pending |
| 8 | 2988 | stable | T5 Query-Blindness | M6 | pending |
| 9 | 3059 | stable | T3 Noise-Anchor | M6 | pending |
| 10 | 3716 | ultra_hard | T3 Noise-Anchor | M6 | pending |
| 11 | 4032 | stable | T1 Silence-as-Health | M1 | pending |
| 12 | 4353 | ultra_hard | T2 Blame-the-Messenger | M5 | pending |

---

## 18 个数据/维度盲区 not-saved case · 用户提示原则（2026-04-28，case 283 review 后）

四条普适性原则（适用于所有后续 case 分析、未来 v4.1 维度设计）：

### P1 · 候选服务必须验证它在根因路径上

**原则**：当 agent（或人）发现某个服务"看起来像 RC"时，必须验证它是否处于 GT 传播路径上（causal_graph 节点 + propagation chain），而不是仅凭它"信号最响"。

**Why**：在 cascade 类故障里（NetworkBandwidth / mysql 共享 infra / 底层网络故障），中下游 victim 的信号往往比 origin 更响（如 case 283 ts-consign-service NonUniqueResultException 352 行 vs ts-station-service 0 ERROR）。"信号最响"和"在根因路径上"是两件事。

**How to apply**：advisor 检测到 agent 锁定一个候选时，trigger 一条"路径验证"反思——`你的候选服务在 incident 描述里提到的 SLO 端点的调用链上吗？沿端点 trace 一路追到底，你的候选会出现吗？`

### P2 · 候选信号需做 chronic check（incident-only vs 长期常态）

**原则**：当 agent 选定某服务作 RC 时，它一定是基于某个具体症状（log error / 高 latency / restart）。这个症状必须做 chronic 验证——**同样的症状在 normal 期是否也存在 / 出现频率如何**。

**Why**：trainticket benchmark 自带大量 chronic noise（RabbitMQ UnknownHostException / "Order already exist" / "foodStoresListResult is null"），它们在 normal 期就有，在 abnormal 也有，但 agent 第一次看到 abnormal 数据就把它当 incident-specific 信号锚定。case 283 反例：consign-service NonUniqueResultException 是 incident-only（normal=0/abnormal=352）—— 这种**真正 incident-only**的信号也需要 P3（路径验证），单看 chronic check 不足以判断它是 origin 还是 victim。

**How to apply**：每次 agent 写出"X service has Y errors，所以它是 RC"的判断时，advisor 应反问——`Y 这个症状在 normal_logs / normal_traces 里出现多少次？如果 normal 也有大量出现，是 chronic noise；如果 normal 完全没有，仍要继续 P3 验证它是 origin 还是 race-condition artifact`。

### P3 · 调查路径要先建全局感知 + baseline 对比要有覆盖度

**原则**：在锚定单个服务前，先对**整条调查路径上的所有 service** 建立全面感知（trace count / latency / error rate / chronic-or-incident）。GT 在 SLO 路径上时，**从根因到 SLO 端点之间所有被 agent 调查过的节点都会呈现某种症状**——如果只有一个节点有症状，要么这个节点本身就是 RC，要么 agent 漏调查了路径上其他节点。

**Why**：case 283 的 baseline 在 R20 做过 normal vs abnormal 对比但**只对比了 4 个服务**（travel-plan / travel / preserve / ui-dashboard）—— 这正好是 chain 中段。如果当时把 baseline 扩到全部 30 个服务，会立刻看到 ts-station-service trace count -33% + 多服务 latency 系统级升高，浮现"chain 底部 + mysql 慢"的真信号。**baseline 对比的覆盖面 < 全服务的 1/3 就不算真做 baseline**。

**How to apply**：M6（baseline contrast）维度的 trigger 不能只看"agent 是否做过 baseline_compare 类 SQL"，还要计算 `covered_services_in_baseline / total_services` 比例；< 30% 时即使做过 baseline 也算 incomplete，应触发"扩 baseline 覆盖到所有服务"的反思。

### P4 · Metric 检查的触发条件需要改进

**原则**：M7 (Layer Coverage Reflex) 当前 trigger 太宽容——agent 跑过一次 `metric_scan`（哪怕 GROUP BY service_name 拿到一堆 NaN 就放弃）就算"已经查过 metric 层"。但很多关键信号（hubble HTTP p99 / jvm.system.cpu / container.cpu）需要**带具体 metric name 的精确查询**，而不是宽泛的 LIKE '%error%' / '%latency%'。

**Why**：case 283 baseline 在 R37 跑过一次 `metric LIKE '%error%' OR '%latency%' OR '%duration%'`，确实触及了 hubble metric，但 GROUP BY service_name 取 avg/max 时大量服务返回 NaN（hubble 不是每个服务都采集），agent 直接判 metric 维度无信号放弃。但 case 283 真正的 80x 信号在 `jvm.system.cpu.load_1m` 这种**特定 metric name**——keyword "latency/duration" 不匹配，agent 永远不会查到。

**How to apply**：M7 trigger 应升级为多维度——
- (a) 需要至少 **3 类 metric intent** 都被触发（`metric_scan + jvm_state + network_layer + container_resource` 中至少 3 个）才算 metric 层"覆盖到"
- (b) 检测到 metric_scan 但 limit/where filter 太宽（LIKE '%X%' OR ...）且后续没追问具体 metric → 算 metric 层"假动作"，仍然触发 M7

---

## Case 315 · `ts0-ts-travel-plan-service-response-delay-pfwcqk` · 启发（2026-04-28）

HTTPResponseDelay chaos 注入 605 ms 延迟在 caller (ts-travel-plan-service) → server (ts-train-service) 的调用对上。baseline / v4 均答错（baseline → ts-route-plan-service / v4 → ts-seat-service，都是 cascade victim）。

四条核心启发：

1. **HTTPResponseDelay / 网络层注入 chaos 的指纹是"client span 慢、server span 正常"的不对称**——单看 service-level avg 看不到，必须把同一个调用对的 client 端 span 和 server 端 span 拉出来直接比。当前 19 类 intent 不会主动引导做这种粒度的查询。

2. **"first ERROR timestamp + ERROR 里点名的对端 = RC"是错的启发式**：在 cascade 慢调用类故障里，第一个出现的 ERROR log（如 connection reset）是 caller 自己资源耗尽的二阶副作用，被点名的对端往往是 cascade victim 而非 origin。这个 fallacy 跨 case 反复出现（case 283 的 NonUniqueResultException 也是同款——一个看起来"信号最响"的 incident-only error 不一定在根因路径上）。

3. **被怀疑的服务必须做"自身故障证据"反向验证**：一个服务真的是 RC，它本地至少应该呈现某种症状（自己的 log error / 自己的 Error span / 自己的 restart / probe 失败 / heap 压力）。如果它完全 silent，"它太严重连 log 都没来得及写"是 confirmation bias，不是合理推论。这条是 P1 路径验证原则的具体化。

4. **agent 推理瑕疵（编 metric 编码、错读 phase=2.0 为 Failed）中间件不能直接修，但可以反向辅助**：advisor 检测到 agent 用某个 metric 数值做 RC 判据时，应自动反问"这个值在 normal vs abnormal 之间有变化吗"——case 315 phase 全程都是 2.0、normal 和 abnormal 各 1176 行完全相同，是最强的"这不是 incident signal"反证，但 agent 没主动验证。

---

## Case 323 · `ts0-ts-travel-plan-service-time-rjdx4x` · 启发（2026-04-28）

TimeSkew chaos（time_offset=-84s）注入到 ts-travel-plan-service 单一服务上。baseline / v4 都答 ts-route-service ❌（cascade 末端 victim）。GT 真信号：jvm.system.cpu.load_1m 11.85x + 端点 distribution 27x + trace count -88%（都在 ts-travel-plan-service 上）。baseline 被 cascade victim 的 queueSize=209 + db.client.connections.wait_time=272s 这种"4-5 倍其他服务"的极端 metric 锚定。

五条核心启发：

1. **`queueSize` / `pending_requests` / `db.connections.wait_time` 类 metric 的极端值有两种成因**：(a) 这个服务自己处理慢；(b) 这个服务被上游高频访问。case 323 是 (b) —— travel-plan-service 因为 TimeSkew 内部 deadline 错算导致疯狂 retry，把下游 route-service 的 queue 打爆。区分这两种成因必须做交叉验证：查这个服务自己的 per-request 内部 span duration distribution。如果内部处理时延不变，就是被 hammer，不是处理慢。

2. **Cascade 类故障的归因方向：trace 顶端的 application service 比中段/末端更可能是 origin**。中段/末端的 victim 因为接收 retry 风暴，会呈现非常显眼的"capacity"类 metric 极端值（queueSize / connection wait）；而顶端 origin 的真信号往往在 jvm/cpu/heap 这种"系统级 health"维度，且需要按 specific metric name 查。当前 19 类 intent 不会主动按"trace 顶端 vs 末端"做 RC 归因方向区分。

3. **Metric 全 NaN 是有信息量的信号，不能简单放弃**。case 323 的 hubble_http_request_duration 在 abnormal 期间完全 NaN —— 因为 hubble 采样依赖 wall clock 对齐时间桶，TimeSkew 让该 pod 的时钟回拨 84s → 数据落不进时间桶 → 全 NaN。"metric 消失"本身就是 TimeSkew 的指纹（同样适用于 pod down / collector 故障，三种成因都暗示这个 pod 自己有严重内部异常）。当 normal 期某 metric 正常采样 + abnormal 期突然全 NaN + 只在某具体 pod 上，这个 pod 几乎肯定是问题源。

4. **M6 (Baseline Contrast) 在 cascade 类故障上单独触发可能反向作用**。当 cascade 副作用的 metric 在 normal 期不存在（如 queueSize=209 这种 victim-specific 的 incident-only 信号），M6 的"incident-only = RC"反思反而加固对 victim 的锚定。M6 必须和"cascade 位置归因"维度联动才安全。

5. **TimeSkew 类故障的五件套指纹**：(a) 端点 duration 暴涨但无 Error status；(b) hubble HTTP 全 NaN（时间桶对不齐）；(c) jvm.system.cpu.load_1m + utilization 飙升（异常处理 + retry 烧 CPU，不是单纯阻塞）；(d) trace count 大跌（线程被 retry 占满 → 实际能接的新请求量下降）；(e) 全 silent on logs。这五件套组合可作为 TimeSkew 的特征指纹，用来与"网络层延迟"（HTTPResponseDelay 类）区分（后者通常 jvm cpu 不会飙升，因为 thread 是 wait IO 不烧 CPU）。

---

## Case 339 · `ts0-ts-travel-service-mysql-28wmss` · 启发（2026-04-28）

JVMMySQLLatency chaos（设计注入 3669 ms 延迟到 ts-travel-service 的 SELECT trip）— **实际未生效**。abnormal 期 `SELECT Trip` / `SELECT ts.trip` 的 max 仅 30-35 ms，p99 仅 3.5 ms，整个数据集没有任何 span 出现 3669 ms 量级 outlier。可能成因：Hibernate 二级缓存绕过 JDBC 层 / SQL pattern 不匹配 / ByteBuddy agent attach 失败。

启发：
1. **case 339 应归类为 `unsolvable:chaos-not-effective`**——不是 v4 框架盲区，是 chaos engine / dataset 的实现问题。这类 case 不应计入"22.6% 翻盘率"的分母（与 case 572 / 3114 同类）。
2. **识别 chaos-not-effective 的方法**：abnormal 期没有任何 service 的 metric ratio > 5x，且 chaos 设计的 latency_ms 在 trace duration distribution 上找不到对应密度的 outlier。
3. **新增 M16 · Chaos-Effectiveness Gate（设想）**：当全数据集最强 ratio < 5x 时，advisor 提示"信号在 noise floor，结论可信度低，建议回查 incident 描述端点的 ownership service 作保底"。

---

## Case 804 · `ts1-ts-train-service-pod-failure-5qwqdz` · 启发（2026-04-28）

PodFailure chaos 让 ts-train-service pod 不可达 4 分钟。baseline / v4 都答 ts-basic-service ❌（cascade 中段 victim，因为 basic 调 train 失败抛 SEVERE 503 log 278 行最响）。GT 真信号：ts-train-service trace -99.7% / log -99.7% / container.memory -99.9% / container.restarts 0→1。agent 在 R69-R70 实际**查到了** train-service silence 信号但没解读为 RC，仍然用 "most errors = RC" 做判据。

两条核心启发：

1. **缺乏 error message 关键词元认知**：高频 error message 的语义指向往往明确告诉你真凶在哪，但 agent 只看"谁报错最多"。需要把 error message → 因果指向预编码到 advisor 知识里：
   - `"upstream connect error" / "Connection refused" / "503 Service Unavailable: upstream"` → **报错的是 caller，真凶在它的 upstream**（必须查 caller 的下游服务是否 silent）
   - `"Connection reset by peer"` → **四种发起方**（server crash / server 主动关 / client buffer 满 / 中间层 RST），不能直接归因为 server 故障
   - `"NonUniqueResultException / Duplicate entry"` → **可能是上游慢导致的 retry race**（race-condition artifact 不是 origin）
   - `"OOMKilled / OutOfMemoryError / Heap space"` → **自身资源问题**（这才是合理归因到本服务）
   - `"UnknownHostException / DNS"` → **DNS / service discovery 故障**，可能在 service mesh / kube-dns 层
   advisor 应在 agent 用某个 error message 做 RC 判据时，按字典命中触发 message-specific 的反思维度。

2. **count=0 / silence 不一定是没问题的**：trainticket 的 PodFailure / NetworkBandwidth / DNS 类故障的 GT 信号往往是某 service 在 abnormal 期 trace/log count 跌到接近 0，但 agent 默认的 SQL 模式都是 `GROUP BY service ORDER BY count DESC`（loud 排序，silent 服务自动消失）。**count=0 = 服务死了 ≠ 服务没问题**。advisor 应在 agent 已查 ≥30 round 但还没做"全服务 normal vs abnormal count ratio 升序"对比时强制触发，直接给 agent 跑这个 SQL 的提示，浮现 ratio < 0.1 的服务作为优先 RC 候选。这能命中 PodFailure / 极端 NetworkBandwidth 类故障的核心信号。

---

## Case 860 · `ts1-ts-travel-service-response-replace-body-vzcxrp` · 启发（2026-04-28）

HTTPResponseReplaceBody chaos 把 ts-travel-service → ts-seat-service 调用的 response body 替换为 'z' 开头的非法 JSON。GT = travel-service + seat-service。baseline / v4 都答 ts-basic-service ❌。真信号：travel-service SEVERE log 1167 行同质 "JSON parse error: Unexpected character ('z' code 122)"——这是 chaos 直接指纹。chaos 引发 travel-plan-service 对 travel-service.queryInfo 端点 retry 47 次/请求，整个内部 chain（含 basic）被反复打爆。

四条核心启发：

1. **Error message 的内容分类比数量更关键**：1168 行 SEVERE log 中 1167 行是 "JSON parse error" + 1 行 "Connection reset"。baseline agent 把少数派的 "Connection reset" 当主因（看上去更"诊断性"）忽略了 1167 行同质 JSON parse error。**高频同质 error pattern 是 chaos 信号（fixed 输入被反复处理失败）；少数派 outlier 通常是 cascade 副作用**。advisor 应强制 agent 用 `GROUP BY message ORDER BY count DESC` 做 dedup 后再判断主导模式。

2. **Caller-side endpoint 失败的 retry 风暴会顺带打爆下游 chain 上所有节点**：在 trainticket 这种 microservice 架构下，一个 endpoint (如 travel-service.queryInfo) 的内部要顺序调用 8+ 个下游服务。当上游对这个 endpoint 做应用层 retry（Spring @Retryable / 业务循环）时，**每次 retry 都让 endpoint 完整跑一遍内部 chain**。chain 上每一个 child service 都被反复调，QPS 翻倍 + 排队延迟升高。case 860 实测：1 个 travelPlan/cheapest 请求触发 47 次 travel-service.queryInfo retry，basic-service 的 incoming 从 normal 319 涨到 abnormal 1191（**3.7x**，全部来自 travel-service）。

3. **Chain 上的"陪跑"victim 呈现 silent + high latency 是正常表征，不是 silent killer**：被 retry 风暴 hammer 的下游 chain 节点（如 case 860 的 basic-service / case 323 的 route-service）会同时呈现：(a) trace count 大涨（被多调）；(b) avg/p99 latency 升高（incoming 排队）；(c) **自己 log 全 INFO，trace status 全 Unset，没有任何 error 信号**（处理每个请求是健康的）。当前 baseline agent 把 (a)+(b)+(c) 误读为"silent killer：它在偷偷损坏 / 偷偷慢"，实际上 (c) 反过来证明它是 victim 不是 origin。**真正的 silent killer 应该呈现自己内部 span 的 per-request duration distribution 显著升高**，而不是 incoming 排队导致的 endpoint avg 升高。区分这两种"high latency"的方法：看内部 child span（这个 service 自己的代码逻辑或它调下游的耗时），不是只看 incoming endpoint 的总 duration。

4. **HTTPResponseReplaceBody 的特征指纹**：(a) caller 的 SEVERE log 里 N 行（数百-数千）**同质** JSON parse error / deserialization 异常，且 Unexpected character / token 完全相同（chaos 注入的 body 是固定字符串）；(b) caller→server 的 child span 数量增加（应用层 retry）；(c) server 自己的 server-side span 几乎正常（chaos 在 caller side sidecar 注入，server 不知情）；(d) 上游 endpoint trace count 大跌 + avg 大涨（retry 风暴）。这五件套与 HTTPResponseDelay（caller-side delay 但无 JSON parse error）和 PodFailure（503 connection refused 而非 JSON parse error）都可区分。

5. **必须看 log message 的关键内容信息，不能只看 count/level**：跨 case 反复出现的 fallacy——agent 用 `GROUP BY service_name, level COUNT(*)` 找到"哪个 service SEVERE 最多"就锚定 RC，从来不看 message 实际写了什么。但 message 内容才是 chaos 的直接指纹：
   - case 860 "Unexpected character ('z' code 122)" → HTTPResponseReplaceBody 注入 'z' 开头的固定坏 body
   - case 315 "503 Service Unavailable: upstream connect error" → 报错的是 caller，真凶在 upstream
   - case 804 "503 Service Unavailable: Connection refused" + 同一 503 提示 → 同上
   - case 283 "NonUniqueResultException" → 可能是 race condition，需要 chain overlap 验证
   advisor 应在 agent 用 ERROR/SEVERE 数量做 RC 判据时，强制要求先看 top-3 message 内容（用 GROUP BY message ORDER BY count DESC + 用 REGEXP_EXTRACT 抽取关键 token），再判断主导模式。这条原则横跨所有 chaos 类型有效。

---

## Case 1140 · `ts2-ts-food-service-bandwidth-b5qvk5` · 启发（2026-04-28）

NetworkBandwidth chaos 限制 ts-ui-dashboard → ts-food-service 方向带宽到 14 KB/s（极严苛）。GT = food-service + ui-dashboard。baseline / v4 都答 ts-consign-service ❌（被 incident-only NonUniqueResultException 176 行 SEVERE 锚定，但 consign-service 不在 chaos chain 上）。真信号：food-service jvm.system.cpu.load_1m 6.21x + hubble_http_request_duration_p95 5.53x；ui-dashboard 调 food 的具体端点 7-12x（service-level avg 只 1.7x 但单端点级极端）。

三条核心启发：

1. **网络层 chaos 的指纹常常在具体 span 而非 service-level avg**：service avg 会 wash out 单端点级的极端信号。case 1140 的 ts-ui-dashboard service-level avg 只升 1.7x（看上去不严重），但它调 food-service 的某些端点（`GET /foodservice/foods/.../Z1235`）升 **12.5x**。NetworkBandwidth / HTTPResponseDelay / DNSRandom 这些"调用对级"chaos 真信号必然在具体 span 维度。advisor 应强制 agent 当怀疑某 service 时，按 `(service_name, span_name) GROUP BY` 看 distribution，不要只用 service avg。

2. **根因必须在故障链路上——incident-only signal 也要做 chain overlap 验证再归因**：case 1140 ts-consign-service `NonUniqueResultException` 176 行（normal=0, abnormal=176）是完美的 incident-only 信号，但它**不在 chaos 因果链上**——chaos 加在 food-service↔ui-dashboard 上，consign-service 跟 food 业务流没直接关系。"incident-only" 不等于"在 RC 链路上"，可能是巧合的独立 race condition / 共有负载状态下的偶发 noise。在 commit 候选 RC 前必须验证：候选服务的异常 trace 是否与 incident 描述的 SLO 端点 trace 有 trace_id 重叠？如果完全不重叠，说明它跟主因果链脱节，应该 dismiss。这条对 trainticket 的 ts-consign-service NonUnique trap 特别有效（已在 case 283 / 339 / 1140 反复出现）。

3. **必须细看 metric——尤其是 jvm.system.cpu.load_1m 和 hubble_http_request_duration**：case 283 / 323 / 1140 反复出现同一个 fallacy——agent 跑过 `metric LIKE '%error%' OR '%latency%' OR '%duration%'` 之类的宽泛 metric 查询拿到一堆 NaN 就放弃 metric 维度。但 NetworkBandwidth / TimeSkew 这类 chaos 的真信号都在 jvm.system.cpu.load_1m（D-state thread 累积）+ hubble_http_request_duration_p95/p99（直接测网络层延迟）+ container.cpu.usage 这些**特定 metric name** 上。M7 (Layer Coverage Reflex) trigger 必须升级：不能只看 metric_scan 是否触发，要看具体 metric name 是否被查过——`jvm.system.cpu.load_1m / hubble_http_request_duration_p95 / container.cpu.usage / k8s.container.restarts` 这 4 个核心 metric 必须每个 case 强制查一次。

---

## Case 1421 · `ts2-ts-station-service-dns-nn49s2` · 启发（2026-04-28）

DNSRandom chaos 让 ts-station-service 解析 mysql 的 DNS 查询返回随机 IP。GT = station-service + mysql。baseline / v4 都答 ts-consign-service ❌（同 NonUnique trap，第 4 次反复出现）。真信号：station-service 的 `hubble_http_request_duration_p99_seconds` 8.9 ms → 285 ms（**32x**），是唯一直接信号。trace count -40% 跟全系统 -40% 一样所以不是特异性信号。application log 完全 silent on errors（DNS 失败被 JDBC driver 层吃掉）。

两条核心启发：

1. **必须查特殊的 metric——尤其是 hubble L7 网络监控类**：DNS / NetworkBandwidth / TimeSkew 这种"信号在网络层"的 chaos，application 层的 log/trace 几乎抓不到（DNS 失败被 driver 层 catch、trace span 在 connection 失败时不创建）。**唯一直接信号在 Cilium hubble 这种 L7 监控 metric** 上。但 hubble 类 metric 的 metric_name 很特殊（`hubble_http_request_duration_p99_seconds` / `hubble_http_request_duration_p95_seconds` / `hubble_dns_query_total` 等），不会被 `LIKE '%latency%'` 或 `LIKE '%duration%'` 这种宽泛模式自然命中（前者 keyword 是 `latency` 后者 metric 名里没有这词）。advisor 应维护"必查 metric 清单"包括 `jvm.system.cpu.load_1m / hubble_http_request_duration_p95 / hubble_http_request_duration_p99 / container.cpu.usage / k8s.container.restarts`，并强制 agent 每个 case 都用 specific metric_name 查询这些（不能用 LIKE 通配模糊查）。

2. **trace 完整性本身是信号**：当 chaos 在 connection / DNS / network 层时，trace span 在 connection 建立失败时不会被 OpenTelemetry SDK 完整创建——agent 看到的 trace 是"幸存者偏差版本"（只剩成功的请求），失败的 case 完全消失。这造成两种 trap：(a) 看 trace 排名时 GT 服务**因为大量失败请求 invisible 而排名下沉**（case 804 ts-train-service trace -99.7% / case 1421 trace -40% 跟全系统 -40% 一样不显眼）；(b) 看存活的 span 时 distribution 看上去几乎正常（case 1421 SELECT span normal 0.6 ms vs abnormal 0.8 ms 几乎一样，因为存活的都是 DNS 解析恰好命中的成功请求）。advisor 应在 agent 锁定候选时强制问"是否有大量请求在 connection 建立阶段就失败导致 trace 残缺？" → 反向触发 M9 (cross-service trace ratio sweep)。

---

## Case 1934 · `ts3-ts-order-service-pod-failure-7xsmwd` · 启发（2026-04-28）

PodFailure chaos 让 ts-order-service 不可达 4 分钟，与 case 804 同款。GT = order-service。baseline / v4 都答 ts-seat-service ❌（cascade 直接 caller，因为它调 order 失败抛 503 SEVERE）。v4 跑 113 round 仍然失败（mid 没触发，仅 conc 太晚）。order-service trace -99.8% / restarts 0→1 / page_faults -99.6%；多个业务端点（cancel/payment/preserve/inside-payment）trace 全 -100% silence。

三条核心启发：

1. **看到下游连接错误信息（503 upstream / Connection refused / Connection reset）时，必须追到 message 里提到的具体下游服务**：当 agent 锁定的候选 X 的 SEVERE/ERROR log 里明确包含 "upstream connect error" / "Connection refused" / "5xx from downstream" 等字样，**X 是在报告下游不可达，X 不是 RC**。advisor 必须强制 agent: (a) 解析 message 提取被指控的具体 downstream service hostname/IP；(b) 查这个 downstream 在 abnormal 期的 trace count / log count；(c) 如果 downstream 是 silent 的（ratio < 0.1），它才是 RC。case 1934 的 seat-service SEVERE 明确写"503 upstream connect error - Connection refused"，但 baseline 没追"upstream 是谁"——实际上 stack trace 或调用上下文能反推出是 order-service。

2. **对每个 RC 候选必须做 baseline 对比验证**：不是做过 1 次全局 normal vs abnormal 就够，而是对**当前候选服务**做专项 baseline 对比——它自己的 trace count / log count / metric / endpoint distribution 在 normal vs abnormal 期是什么变化？case 1934 / 804 baseline 失败的核心是 agent 锚定 seat-service / basic-service 后没回头查"这个候选自己在 normal 期是什么样"——如果查了会发现 seat-service trace count 也跌 -96%（说明它也是 victim 不是 origin）。advisor 必须在 agent commit 前强制触发"候选自身 baseline 对比"反思。

3. **多个独立业务端点同时 silence 时找"汇聚点"或"共同依赖点"**：当 cancel/payment/preserve/inside-payment 等业务端点同时跌 -100%，**这是 fan-out 模式的故障——它们一定有共同依赖在 chain 底部**。找汇聚点的方法：(a) 列出所有 silenced 服务的 normal 期 child span 调用关系；(b) 取交集——所有这些业务流的下游交集服务就是 RC 候选。case 1934 里 cancel/payment/preserve/inside-payment 的共同 child 调用只有 ts-order-service + mysql + ts-config-service 三个，**三选一就能命中 GT**。如果找不到共同依赖点，则进一步分类：哪些是级联（独立业务的连锁失效）/ 哪些是 chronic 自带噪声 / 哪些是 chaos 主链路上的——通过对比 normal 期是否也呈现同一种 silence 模式来区分。

---

## Case 2130 · `ts3-ts-station-service-return-4z45w8` · 启发（2026-04-28）

JVMReturn chaos on `StationApplication.main` —— **chaos 实际几乎未生效**（main 方法是 Spring Boot 启动入口，应用启动后 main 已返回，运行期 patch 它的 byte code 不会有业务效果）。归类为 `unsolvable:chaos-side-effect-only`，与 case 339 / 572 / 3114 同类。

数据上唯一信号：JVM agent attach 引发的 byte code redefinition 副作用（station-service jvm.cpu 2.82x、端点 ratio 1.5-2.9x、hubble HTTP 全 NaN——同 case 323 TimeSkew "metric 消失"指纹）。但 cascade 末端的 ts-route-service avg 30x + max 106 秒（排队 artifact），信号比 GT 强 100 倍——agent 必然被极端 outlier 锚定。

启发：
1. **JVMChaos on `main` method 的注入效果普遍弱**：trainticket 多个 case 都 inject 在 main 上，这类 case 应统一标记 unsolvable
2. **dataset 应在生成时验证 chaos 实际生效**（与 case 339 启发一致）
3. **case 2130 适合作 v4.1 反直觉 case 测试**：信号最强 ≠ RC，能否通过 M14 (cascade 位置归因) + M22 (弱信号+NaN 组合识别) + M23 (max vs distribution) 拆穿是关键检验点

---

## Case 2678 · `ts4-ts-seat-service-bandwidth-k2bwt2` · 启发（2026-04-28）

NetworkBandwidth chaos 限制 ts-seat-service ↔ ts-config-service 之间的网络带宽（828 KB/s + buffer 仅 1447 字节）。GT = seat-service + config-service。baseline / v4 都答 ts-travel2-service ❌（cascade 末端 victim，avg 63x 看上去最响）。

最干净的 chaos 指纹：seat→config 父子调用 child span count 从 2299 跌到 14（**-99.4%**）—— 这条调用边在 trainticket 是系统第二高频的 cross-service 调用（仅次于 loadgen→ui-dashboard），是 seat-service 业务逻辑的核心依赖。

三条核心启发：

1. **必须看选定的 RC 候选在调用树（trace）的位置**：如果它在调用树的末端或叶子节点，那它是被调方，不可能是 origin—— 真正的 origin 在它的下游或它本身的下游（如果它还调别的服务）。case 2678 的 ts-travel2-service 在调用树最末端（只调 seat-service），它的 63x avg 是等 seat 响应的累积时间。**advisor 必须在 agent commit 前强制做"调用树位置归因"**：候选服务自己的下游服务 trace count 是否 silent？如果是，那个下游才是真 RC。这是 P1 (路径验证原则) 的扩展。

2. **多个独立业务端点同时呈现共性问题（timeout / 全 silence）时，必须看 trace 调用树的汇聚点**：fan-out 类型的故障——cheapest/quickest/minStation/queryInfo/preserve 等独立业务都同时受影响，它们的调用链会汇聚到某个共同节点。case 2678 这些业务流的共同 child 全都包含 ts-seat-service（764+918+615 calls 来自 3 条不同业务流），seat-service 又共同调 ts-config-service（2299 calls）。**找汇聚点 = 取所有 affected 业务流的下游 child span 调用关系交集**。这与 case 1934 的 "find common dependency" 启发同源但更普适——case 2678 的汇聚点在调用树**中段**（不只是底部 mysql / config 这种 leaf）。

3. **span / 父子调用边的 count drop 在网络层 chaos 中是关键对比项**：NetworkBandwidth / DNSRandom / NetworkLoss 等"网络层 chaos"的最干净指纹是某条 (caller, callee) **父子调用边**的 child span count 极端下降（-90%+），不是单个 service 的 trace count 变化。这种 chaos 让对应的 HTTP 调用 connection 建立失败 → child span 没被 OpenTelemetry SDK 创建 → trace 里这条边几乎消失。**advisor 应主动跑 cross-service caller-callee edge ratio 对比 SQL**（前面提的 M24 维度），把所有 (caller, callee) 父子调用对的 normal/abnormal count ratio 升序排列，跌幅最大的那条边就是 chaos target——edge 两端的 service 都是 GT。这种"两端服务都 silent + 中间 edge 被切断"的模式是 case 1140/283/1421/2678 的共同指纹，比 service-level 信号都强。

---

## Case 2715 · `ts4-ts-station-service-bandwidth-nfljv5` · 启发（2026-04-28）

NetworkBandwidth chaos 限制 ts-station-service → ts-basic-service 应答方向（rate 165 KB/s, **limit 138 字节**）。GT = station-service + basic-service。baseline / v4 都答 ts-travel-service ❌（cascade 末端 victim avg 160x）。最干净指纹：(basic, station) caller-callee edge 1263→1 (-99.9%)。

三条核心启发：

1. **caller-callee edge ratio 是 NetworkBandwidth 类 chaos 的标准指纹**（与 case 2678 同款）：跑全 cross-service edge ratio 升序，跌幅最大的边两端就是 GT。

2. **NetworkBandwidth / NetworkLoss 类 chaos 必须跟 PodFailure / HTTPResponseDelay 区分**——三者表面都"导致服务 silence + cascade victim avg 暴涨"，但底层指纹完全不同：

| chaos 类型 | 标志性指纹 | 区分方法 |
|---|---|---|
| **PodFailure** (case 804/1934) | k8s.container.restarts 0→1 + container.memory.working_set 跌 99% | 看 k8s 元信息层（restart counter / pod 元信息） |
| **NetworkBandwidth** (case 1140/283/2678/2715) | (caller, callee) edge ratio < 0.01 + edge 两端 service 都 silent on errors | 看 caller-callee edge 分布对比 |
| **HTTPResponseDelay** (case 315) | caller client span 615ms vs server span 3.7ms 不对称 | 看同一调用对的 client vs server kind span 对比 |
| **HTTPResponseReplaceBody** (case 860) | caller log 1167+ 行同质 JSON parse error | 看 SEVERE log 的 message dedup 模式 |
| **JVMChaos / TimeSkew** (case 323) | jvm.system.cpu.load_1m 飙升 + hubble HTTP 全 NaN | 看 JVM metric + hubble metric NaN |

advisor 应用决策树根据上述指纹自动识别 chaos 类型，然后选对应维度的反思。

3. **TCP 双向流量机制让"单方向限速"实际效果是双向断连**：用户疑问"为什么限制 station→basic 方向，但 basic→station 调用也消失？"。原因：(a) HTTP 调用的 response 必须走 server→caller 方向，response 数据 packet 全被 drop；(b) `limit=138 字节`极小让连 HTTP response 的小数据包都过不去；(c) caller (basic) 等不到 response 抛 SocketTimeout，OpenTelemetry SDK 在长超时/失败的 client span 上不正常 export → trace 里 caller-callee edge 几乎消失；(d) 二阶效应：basic 的 thread pool 被卡死的 station 调用占满 → basic 自己的 incoming 也几乎消失（thread starvation cascade）。**advisor 看 NetworkBandwidth chaos 时应该把"两端服务都 silent + edge 几乎完全切断"当成标准模式**，不要因为 direction 字段的语义复杂化推断成"只一方有问题"。

---

## Case 2836 · `ts4-ts-travel2-service-response-replace-body-c5mklh` · 启发（2026-04-28）

HTTPResponseReplaceBody chaos 把 ts-travel2-service → ts-basic-service 调用的 response body 替换为非法 JSON。GT = travel2 + basic。baseline 答 config ❌ / v4 答 seat ❌（都没看 SEVERE log 内容）。chaos 直接证据：travel2-service abnormal SEVERE 363 行，**362 行（99.7%）是 "JSON parse error: Unexpected character ('z' code 122)"** 同质模式，与 case 860 完全一样。

两条核心启发：

1. **HTTPResponseReplaceBody 类指纹（case 860 + 2836 共同）**：
   - caller (chaos app) 的 abnormal SEVERE log 有 **N 行（数十-数千）同质** `JsonParseException` / `HttpMessageNotReadableException` / `Unexpected character` / 反序列化错
   - 错误的 character (`'z' code 122`) 完全相同——chaos 注入的 body 是固定字符串
   - **caller-callee edge child span 数不变或轻微增加**（connection 不断，只是 response 内容被篡改）
   - server (chaos target) 自己的 trace count / avg / log 完全正常
   - 这种 chaos 信号**只在 SEVERE log 的 message 内容里**——不在 service-level avg、不在 trace count、不在 metric。advisor 必须强制 dedup SEVERE log message。

2. **三类网络/HTTP chaos 的区分要点**（汇总 case 1140/283/2678/2715 vs case 804/1934 vs case 860/2836）：

| 维度 | NetworkBandwidth | PodFailure | HTTPResponseReplaceBody |
|---|---|---|---|
| chaos 物理位置 | tc qdisc on pod 网卡 | k8s pod metadata patched 不可达 | sidecar 拦截 response body |
| caller-callee edge ratio | **< 0.01**（边几乎被切断）| < 0.05（GT 服务为 caller 的 edge 跌） | **≈ 1.0**（不变或轻微+） |
| GT 服务 trace count | 大跌 -98%+（两端） | -99% (单端) | **几乎不变** |
| GT 服务 ERROR/SEVERE log | 全 silent (0 行) | server 全 silent / caller 抛 503 | **caller 抛大量同质 JsonParseException** |
| k8s.container.restarts | 0→0 | **0→1** | 0→0 |
| container.memory.working_set | 几乎不变 | **跌 -99%**（旧 pod 不上报）| 不变 |
| cascade victim avg ratio | 极强 (50-160x) | 中等 (caller 几百毫秒) | 中等-弱（取决于覆盖范围）|
| 信号最强位置 | (caller, callee) edge 维度 | k8s 元信息 + service trace count | SEVERE log message dedup |

advisor 的 chaos 类型识别决策树：先查 caller-callee edge ratio 是否极小（→ NetworkBandwidth），再查 k8s.container.restarts 是否 0→1（→ PodFailure），最后查 SEVERE log 是否有 N 行同质 JsonParseException（→ HTTPResponseReplaceBody）。三者诊断方法完全不同，不能用同一套维度 (M5 / M6 / M8) 通解。

---

## Case 3114 · `ts5-ts-preserve-service-pod-kill-5zcl7w` · 启发（2026-04-28）

PodKill chaos 让 ts-preserve-service pod 被 SIGKILL → 新 pod 启动（30-90s）→ 接管。GT = preserve-service。baseline 答 order ❌（chronic ERROR trap）/ v4 答 ui-dashboard ❌。真信号：preserve `jvm.system.cpu.load_1m` 14→283 (**19.7x**) + `container.cpu.usage` 0.086→0.728 (**8.4x**)——新 pod 启动期 JIT/Spring/积压请求三件事同时烧 CPU。

三条核心启发：

1. **必须查 specific metric_name 而不是宽泛 keyword**：case 3114 / 1140 / 283 / 323 反复出现同一种失败模式——agent 用 `metric LIKE '%cpu%'` / `LIKE '%latency%'` 这种宽泛模式查 metric，得到一堆 NaN 或弱结果就放弃。但真信号几乎都在以下 specific metric 上：`jvm.system.cpu.load_1m`（D-state thread + 烧 CPU 的混合）/ `container.cpu.usage`（实际容器 CPU）/ `hubble_http_request_duration_p95/p99`（L7 网络层延迟）/ `k8s.container.restarts`（重启计数）/ `container.memory.working_set`（实际内存占用）。advisor 应维护"必查 metric 清单"强制 agent 每个 case 跑 `WHERE metric IN (...)` 形式的 SQL，浮现 specific metric 维度的 ratio。

2. **PodChaos 三个子类（PodKill / PodFailure / ContainerKill）指纹完全不同，必须分类处理**：

| 维度 | PodKill (case 3114) | PodFailure (case 804/1934) | ContainerKill (case 1143) |
|---|---|---|---|
| 物理机制 | k8s API delete pod → SIGKILL | k8s metadata patched 不可达 | docker/containerd kill container |
| down time | 30-90s 后新 pod 起来 | 整个 4min 不可达 | 几秒重启 |
| trace count drop | -30~-50%（中度）| **-99%+（极端）** | 短暂跌后恢复 |
| caller-callee edge ratio | 0.3-0.6（中度） | **< 0.05（极端）** | 0.5-0.8 |
| **k8s.container.restarts** | **0→0（trap）**——新 pod 是全新 container 计数归零 | **0→1** | **0→1** |
| jvm.system.cpu.load_1m | **飙升 10-20x**（新 pod 启动烧 CPU）| 跌（pod idle）| 飙升（重启后类似 PodKill）|
| container.cpu.usage | **飙升 6-10x** | 跌至 0 | 飙升 |
| container.memory.working_set | 略降（新 pod 内存还没填）| **跌 -99%**（旧 pod 不上报） | 短暂跌后恢复 |
| 标志性指纹 | container.cpu 8x + jvm.load 20x + restart=0 | restart 0→1 + memory -99% + edge < 0.05 | restart 0→1 + jvm.class.loaded 5000+ + container.cpu.time counter reset |

advisor 知识库必须分别记录这三种指纹，不能用一个 "PodChaos" 维度通解。

3. **Chronic Noise 消除是必备前置步骤**：trainticket benchmark 自带大量 chronic noise，反复在多个 case 误导 agent：
   - `[create][Order Create Fail][Order already exist]`（normal 80 / abnormal 60，normal 更多）
   - `[getAllFood][Get the Get Food Request Failed]`（normal 235 / abnormal 165）
   - `[redeclare auto-delete queue]` (RabbitMQ, normal/abnormal 各 48)
   - `NonUniqueResultException on consign-service` (在多个 NetworkBandwidth case 里都偶发出现，跟 chaos 经常无因果)
   - `Connection refused to ts-rabbitmq` (UnknownHostException, 长期问题)
   
   advisor 必须强制 agent 在用任何 ERROR/SEVERE 信号做 RC 判据**之前**做 chronic check：(a) 跑 `SELECT count(*) FROM normal_logs WHERE message LIKE pattern`；(b) 比对 abnormal_logs 同 pattern 的 count；(c) **abnormal/normal ratio < 2x 的全部 dismiss**。这是 P2 chronic check 原则的具体执行方法。case 3114 baseline 失败的核心就是没做 chronic check，把 normal 80 / abnormal 60 的 chronic noise 当 incident-only signal。

---

## Case 3868 · `ts1-ts-config-service-latency-5kkcrc` · 启发（chaos 未生效，2026-04-28）

JVMLatency chaos 注入在 `ConfigController.deleteConfig` 方法上 + 601ms 延迟。**deleteConfig 在 trainticket 运行期完全不被调用**（normal/abnormal 期都 0 span），chaos 实际未生效。归类 `unsolvable:chaos-not-effective`。

JVMChaos 类未生效已观察到三个 case，加入此类：
- case 339: JVMMySQLLatency on `SELECT trip`（Hibernate 二级缓存绕过 JDBC 层）
- case 2130: JVMReturn on `StationApplication.main`（启动后不再调用）
- case 3868: JVMLatency on `deleteConfig`（只读业务不调用删除接口）

JVMChaos 类未生效的共同 fingerprint：
- 目标方法在 abnormal 期没有对应延迟暴涨的 span
- 全系统所有服务 ratio_avg 同质轻微变慢（1.3-1.6x），无强 outlier
- hubble HTTP 全 NaN（JVM agent attach 副作用）
- jvm.system.cpu.load_1m / utilization 仅 1.3-1.7x 弱信号
- baseline / v4 必然乱选（无强信号引导）

**dataset-level 修复建议**（与 case 339 启发一致）：trainticket benchmark 应在生成 JVMChaos 类 case 时做 effectiveness 验证——检查目标方法在 normal 期是否真有 span 出现 + abnormal 期是否有接近 latency_duration 的 span 延迟暴涨。未生效的 case 应标记 invalid 或排除出评估。

---

## Case 3878 · `ts1-ts-consign-service-time-hslmgs` · 启发（2026-04-28，TimeSkew 正向偏移）

TimeSkew chaos `time_offset=+336s` on ts-consign-service。GT = consign。baseline 答 seat ❌ / v4 答 route ❌。consign-service 在 abnormal 期 trace count **完全 0**（-100% silent）+ (ui-dashboard, consign-service) edge 620→0。

三条核心启发：

1. **TimeSkew 正向偏移 vs 负向偏移指纹不同**：
   - **负向偏移**（case 323，time_offset = -84s 回拨）：deadline 错算 → 大量 retry → JVM CPU 烧（jvm.system.cpu.load_1m 11.85x + endpoint duration 27x），GT 服务 trace count 中度跌（-88%）+ hubble HTTP 全 NaN
   - **正向偏移**（case 3878，time_offset = +336s 前进）：trace 时间戳跳到未来 → OpenTelemetry collector 拒绝 export + token validation 看上去 replay attack 拒绝 → GT 服务 trace count **完全 0（-100%）**，无 ERROR、无业务 trace、jvm.cpu 几乎不变
   advisor 不能用一个统一的 "TimeSkew 指纹" 通用——要先看 time_offset 符号。但 chaos 配置 advisor 看不到，**只能从数据反推**：jvm.cpu 大涨 → 负向；trace 完全 0 + jvm.cpu 不变 → 正向。

2. **trace count 完全 0 / -100% silent 必须和其他类型 chaos 区分**：多种 chaos 都呈现"GT trace count 大跌 silent"，但具体形态不同：

| chaos 类型 | trace count drop | jvm.cpu | restart | edge ratio | hubble |
|---|---|---|---|---|---|
| **TimeSkew 正向**（3878） | **-100%（完全 0）** | ~1.0x（不变） | 0→0 | (caller→GT) -100% | NaN |
| **TimeSkew 负向**（323） | -88% | **11.85x** | 0→0 | 中度 | NaN |
| **PodFailure**（804/1934） | -99% | **跌至 0**（pod idle） | **0→1** | < 0.05 | 不一定 |
| **PodKill**（3114） | -30~-50% | **20x（新 pod 烧 CPU）** | 0→0（trap）| 0.3-0.6 | 不一定 |
| **NetworkBandwidth 严苛**（2678/2715） | -98%（两端） | ~1.0x | 0→0 | < 0.01（关键指纹）| NaN |
| **DNSRandom**（1421） | -40%（混在系统级 -40%） | ~1.0x | 0→0 | edge 跌 | NaN |

advisor 决策树需要看多维度 + 跨多个 metric 综合判断，不能单看"trace count drop"就归因。case 3878 与 PodFailure 最容易混淆（都是 -99%+），区分点在 `k8s.container.restarts` (0→0 vs 0→1) + `container.memory.working_set` (不变 vs -99%)。

3. **【设计原则警告】不能在 advisor 知识库中硬编码具体服务名 / 具体故障 pattern**：之前我在 case 3878 启发里写了"trainticket 的 ts-consign-service 在多个 case 反复出现——case 283/339/1140 它是 chronic noise；case 3878 它是 chaos target。advisor 应记录这个" —— **这等于在 advisor 维度卡片里给 agent 答案**（"看到 consign-service 时优先怀疑它"）。这违反 v3 设计原则 #1："只做元认知，不泄漏信息——绝不提示具体该查哪个服务、哪张表、或答案方向"。

   正确的做法：把"chronic noise pattern"抽象化（如"高频 SEVERE log 中 abnormal/normal ratio < 2x 的全部 dismiss"），让 advisor 引导 agent 自己发现哪个具体服务是 chronic noise，而不是直接告诉它名字。

   后续所有维度卡片设计 / OBSERVATIONS 记录都要遵守这条 —— 抽象规则、抽象指纹、抽象阈值都可以写，**但不能写出具体的 trainticket service name / table name / metric 阈值具体值绑定到具体服务名**。这是审稿人会立刻挑出的"泄题嫌疑"。

---

## Case 4229 · `ts3-ts-basic-service-partition-w5hbjw` · 启发（2026-04-28，NetworkPartition）

NetworkPartition chaos drop ts-basic-service ↔ ts-travel-service 之间所有 packet。GT = basic + travel。baseline 答 route-plan ❌ / v4 答 travel2 ❌。GT 服务 service avg 反而**更快**（survivorship bias），但 jvm.system.cpu.load_1m 在 travel 上 **15.97x** 在 basic 上 **4.11x**——是真信号。

两条核心启发：

1. **必查 specific metric name 是反复出现的核心结论**（汇总 case 283 / 1140 / 323 / 3114 / 4229 共同）：trainticket 数据集里几乎所有 chaos 类型的真信号都在以下 specific metric 上：
   - `jvm.system.cpu.load_1m`（D-state thread + busy thread 综合，对 retry 风暴 + thread 阻塞最敏感）
   - `k8s.pod.cpu.usage` / `container.cpu.usage`（实际 CPU 用量）
   - `k8s.pod.cpu_limit_utilization`（CPU 接近 limit 的程度）
   - `hubble_http_request_duration_p95/p99`（L7 网络层延迟，但很多 chaos 期间会变 NaN）
   - `k8s.container.restarts`（Pod*Kill 类故障特征）
   - `container.memory.working_set`（PodFailure 类故障特征）
   
   agent 用 `metric LIKE '%cpu%'` / `LIKE '%latency%'` 这种宽泛 keyword 几乎都查不到——`jvm.system.cpu.load_1m` 字符串里没有 `cpu` 后接 `latency`，普通模糊匹配漏掉。advisor 应给一个**精确 metric 清单**让 agent 强制每个 case 都查，而不是依赖 agent 自己想到查什么。

2. **NetworkPartition vs NetworkBandwidth vs PodFailure 的 trace count drop 程度区分**（汇总 case 1140 / 283 / 2678 / 2715 / 4229 / 804 / 1934）：

| chaos 子类 | 配置极端度 | edge ratio | trace count drop on GT | service avg on GT |
|---|---|---|---|---|
| **NetworkBandwidth 极端**（limit<200 字节，rate KB 级） | 极端 | **< 0.01** | **-98%+（接近 0）** | 0.5-1.0x（残存太少看不准） |
| **NetworkBandwidth 中度**（limit/rate 大点） | 中度 | 0.1-0.3 | -50%-90% | 1-3x |
| **NetworkPartition**（iptables drop 全部） | 完全切断但有 timeout 时间 | **0.3-0.5** | -50%-65%（跟全系统一致） | **0.7-0.8x（反而更快，survivorship bias）**|
| **PodFailure**（pod 持续不可达 4min） | 完全 + 长时间 | < 0.05 | **-99%+** | 0.5-1.0x |
| **PodKill**（kill 后快速重启）| 暂时切断 + 重启 | 0.3-0.6 | -30%-50% | 弱信号 |

四种"切断式 chaos"虽然都让 GT 服务 trace 减少，但程度差异明确：
- 看到 trace -99%+ → PodFailure 或 NetworkBandwidth 极端
- 看到 trace -50%-65%（跟全系统一致） → NetworkPartition（区分点：jvm.cpu 暴涨 + hubble NaN）
- 看到 trace -30%-50% + 新 pod metric 飙升 → PodKill

**核心 trap**：**NetworkPartition 让 GT 服务 service avg 反而更快**（0.78x），因为失败 trace 没 export，残存的是没经过 chaos 路径的快请求。advisor 看到 "service avg < 1.0x（更快）" 时不能直接 dismiss——要看 trace count 是否大跌 + jvm.cpu 是否暴涨。这两个组合（avg 反而下降 + count 大跌 + cpu 暴涨）就是 NetworkPartition 的指纹。

---

## Case 4510 · `ts4-ts-route-plan-service-bandwidth-q5lcsx` · 启发（2026-04-28）

NetworkBandwidth chaos `direction='both'` on (route-plan, travel)，但 limit 配置较宽松（8519 字节，比 case 2715 的 138 字节宽松 60 倍）。GT = route-plan + travel。baseline / v4 都答 travel-plan-service ❌（v4 跑 121 round 仍 stuck）。

两条核心启发：

1. **specific metric 不是万能维度——chaos 配置弱化时 jvm.cpu 不暴涨**：case 4229 NetworkPartition jvm.cpu 15.97x、case 1140/283/3114 jvm.cpu 6-20x，但 case 4510 NetworkBandwidth 宽松配置下 jvm.cpu **几乎不变**（~1.0x）。原因：limit 8519 字节让大部分 HTTP response 能通过（典型 HTTP body 几百-几千字节），caller 不会陷入 retry 风暴 + thread 阻塞。

   **NetworkBandwidth 信号强度连续谱**（按 limit 配置区分）：
   | limit 配置 | edge ratio | service silence | jvm.cpu | 案例 |
   |---|---|---|---|---|
   | 极端 (< 200 字节) | < 0.01 | 全 service -98%+ | ~1.0x | case 2715 |
   | 偏紧 (200-2000 字节) | < 0.1 | 部分 -90% | 1.0-3x | case 2678 |
   | 中度 (2000-5000 字节) | 0.1-0.3 | -50%-80% | 3-15x | case 1140 / 283 |
   | 宽松 (> 5000 字节) | **0.08-0.15** | -75% (跟全系统一致) | **~1.0x（不变）** | case 4510 |
   
   advisor 不能假设所有 NetworkBandwidth 都呈现"jvm.cpu 暴涨"——宽松配置下唯一可靠指纹是 **caller-callee edge ratio**。

2. **trace count drop 跟全系统一致时单看 silence ranking 不够**：case 4510 的 GT 服务 trace 跌 -76%-82%，但全系统所有服务都跌 -75%-85%（系统级 throughput 下降）。silence ranking 升序排列时 GT 服务排不到 top（不极端）。这种情况必须用 **caller-callee edge ratio** 维度——edge 比 service 维度更细粒度，能区分"系统级 throughput 下降"和"特定调用边切断"。

   **silence ranking vs edge ratio 互补关系**：
   - 单服务 silence 极端（如 case 3878 trace=0）：silence ranking 即可
   - 调用边切断但服务不极端 silence（如 case 4510）：必须看 edge ratio
   - 两个都不极端（如 case 2130 chaos 失效）：归类 unsolvable

   advisor 的诊断决策必须**同时**跑 silence ranking + edge ratio，不能只用一种。

3. **caller-callee edge ratio 是网络层 chaos 类故障的核心维度**（汇总 case 1140/283/2678/2715/4229/4510 共同结论）：当 chaos 在网络层（NetworkBandwidth / NetworkPartition / DNSRandom 等）切断或降级某条具体调用边时，最直接最干净的指纹永远是这条 (caller, callee) 父子调用对的 child span count 大跌。当前 19 类 intent 没有引导 agent 跑这种维度的查询——`call_tree_build` 是最接近的但 advisor 维度库未关联到具体使用场景。**新增维度 M24 (Caller-Callee Edge Drop Detection)** 应作为 advisor 的"必查动作"之一，同 specific metric 清单一样无条件触发。SQL 模板：`WITH n_e AS (SELECT t2.service_name caller, t1.service_name callee, COUNT(*) n_c FROM normal_traces t1 JOIN normal_traces t2 ON t1.parent_span_id=t2.span_id WHERE t1.service_name != t2.service_name GROUP BY 1,2), a_e AS (...) SELECT n.caller, n.callee, n.n_c, a.a_c, a.a_c/n.n_c ratio FROM n_e LEFT JOIN a_e USING (caller, callee) WHERE n.n_c >= 50 ORDER BY ratio ASC LIMIT 10` → ratio 最低的几条边的两端就是 GT 候选。

---

# 12 个 saved case 标签重写（用 18 case 体系语言，2026-04-28）

**目的**：抛弃 M1-M8 维度卡片名，用具体行为描述 + 因果机制 + 失败模式标签来重新刻画 12 个翻盘 case。这套描述将作为 v4.1 失败模式归纳和元认知卡片重构的基础。

---

## Case 281 · `ts-station-food-service-stress` · JVMMemoryStress (heap, type=1)

**核心翻盘机制（什么真起作用）**：
- 引导 agent 做 normal vs abnormal **全服务 baseline 对比** → R32 首次跨进 normal_logs/normal_traces 表
- 浮现 incident-only signal：ts-station-food-service p90 latency normal 17ms → abnormal 1268ms（**端点 duration 分布对比，75x**）+ container restart 18s + Duplicate entry on station_store_idx（重启 retry 副作用）
- **chronic 排除**：dismiss baseline 锚定的 ts-food-service "Get Food Request Failed" 269 行（normal 期同样存在 ≈ chronic noise）

**baseline 失败模式**：T2 Blame-the-Messenger —— 把 chronic noise 服务的 ERROR 量当 RC 信号（loud victim 锚定）

**审稿人攻击面 / caveat**：
- 🔴 **STRONG leakage**：advisor "**the database-level errors you found**" 复述 agent reasoning 里的 "Duplicate entry on station_store_idx" 具体词
- 真翻盘 turn (R42 anchor flip 到 75x latency) 在 advisor 复述具体词之后——独立 v4 维度贡献无法证明

---

## Case 572 · `ts-food-service-response-patch-body` · HTTPResponsePatchBody

**核心翻盘机制**：
- **没有任何 v4 干预真起作用** —— mid 和 conc 都因 claude-opus-4-7 API 400 错误（"Invalid model"）降级，agent 没收到任何中间件信号
- 翻盘归因 **partial match 巧合**：v4 pred `[ts-food-service]` ∩ GT `[ts-food-service, ts-train-food-service]` ≠ ∅ → judge 算 correct
- 真因路径：agent 看到 ts-food-service "earliest error timestamp + UnknownHostException ts-rabbitmq"（chronic noise，normal 233 / abnormal 157）就锚定它，**完全没查 ts-train-food-service**

**chaos 类信号缺失**：HTTPResponsePatchBody 在 trainticket 几乎不留 incident-specific 信号（trace duration 不变、status_code 不变、application log 不变）—— 与 18 case 体系里的"chaos-未生效"虽然不同（chaos 物理上生效）但**信号在 noise floor**

**审稿人攻击面**：
- ⚠️ **API 降级** —— 这个 case 的"翻盘"不能算 v4 贡献
- ⚠️ **partial match 巧合** —— 不是真因果链得对
- 系统性问题：5/53 case 的 v4 表现被 API 错误拖累（mid 降级 4 个 + conc 降级 3 个）

---

## Case 807 · `ts-train-service-stress` · JVMCPUStress

**核心翻盘机制**：
- **specific metric**：advisor 引导 agent 转向 metric 层 → 浮现 jvm.system.cpu.utilization 92% spike + container restart @ 14:42:12
- 干预到 agent 真采纳之间存在**延迟（14 round）**——advisor 触发后到 agent 真切到 metric 层中间 14 round 在 trace+log 层徘徊

**baseline 失败模式**：T1 Silence-as-Health —— 锚定 ts-seat-service trace 排名第一（loud cascade victim），把 ts-train-service 的"silent on errors"当 healthy

**审稿人攻击面 / 中间件代码层面问题**（暂存，不参与轨迹失败模式归纳）：
- trigger 实现 vs 卡片描述不一致（metric_scan 在代码归 triage 但卡片归 runtime layer）
- advisor prompt 列具体层名（容器/JVM/网络）—— 脱敏 trade-off
- → **这两条留待后续中间件代码注意事项单独讨论**

---

## Case 1114 · `ts-config-service-stress` · JVMMemoryStress

**核心翻盘机制**：
- 引导 agent 跑**非常规 SQL**：从 normal_traces 父子关系找"该出现但没出现"的服务（**silent service ranking 维度**）
- agent R31 立即跑 `SELECT ... FROM normal_traces WHERE parent_span_id IN ... AND span_name='GET'`
- specific metric 次要支撑：container restart 0→1 + container CPU avg 0.77 比第二名 5x + jvm.system.cpu 2.34x + page_faults 2.95x + 端点 duration 分布偏移（5-50ms 桶 16x、>500ms 桶 23 条 vs normal 0）

**baseline 失败模式**：T1 Silence-as-Health 极端形态 —— 75 round 一次都没查 ts-config-service 自己的 metric/restart，全程锚 ts-seat-service 117 个 Error span（loud victim）

**审稿人攻击面 / caveat**：
- 🟠 **MEDIUM leakage**：advisor 利用 `[B5 OBSERVED SERVICES]` 与 `[B7 ranking]` 的不对称——它看到 R8-R10 trace queries 已触及 ts-config-service 但 reasoning 0 次提到，于是回写"another service that may not be surfacing loudly"。**advisor 不需要看到 GT，只需要看到 agent 还没 commit 的隐藏候选**
- 🟢 优点：silence/absence/should-appear-but-missing 概念语言**不依赖禁词**（O8 启发：比跨层查询/反事实卡片 trade-off 缓和），可以去掉 "originates" 词族而 actionability 不下降
- ⚠️ agent R82 用 "**500x increase!**" 错叙（实际 avg 3.7x，max 926ms 是单点 outlier）—— 信号强足以挽救，但弱信号 case 里这种 max-only 论证可能锚到 outlier

---

## Case 1143 · `ts-food-service-container-kill` · ContainerKill

**核心翻盘机制**：
- 引导 agent 跨层查 metric → R31 立即转 runtime metric → R32 在 ts-food-service 上找到 cpu=0.0 + restart 1
- **ContainerKill 三件套指纹**：container.restarts 0→1 + jvm.class.loaded 1.25→6705（**5364x，JVM cold-start 指纹**）+ container.cpu.time counter reset（568→129）+ 47 秒 trace silence gap @ 08:26:57-08:27:42
- **chronic 排除**：dismiss baseline 锚定的 RabbitMQ DNS UnknownHostException（normal 141 vs abnormal 109 = chronic）
- **distractor 排除**：ts-ticket-office-service 在 R37 短暂带歪（"earliest anomaly @ 08:26:56"），R39-R63 通过 "不在 foodservice 调用链" 排除掉

**baseline 失败模式**：T3 Noise-Anchor —— 把 RabbitMQ DNS chronic noise 当 fault chain 起点

**审稿人攻击面 / caveat**：
- 🔴🔴 **EXTREME leakage**（53 case 最严重）：
  - advisor "You found **NaN values in duration metrics**" 直接复述 agent R25 SQL `WHERE value != value` **operation level**
  - advisor "**mismatch between log/trace**" 直接复述 R24 think 原文（"log says failure but trace says 200"）
  - advisor "**container resource limits, JVM memory pressure, or network-level issues**" 列具体故障类
- **审稿人眼中**：case 1143 翻盘几乎全部归因于 advisor 把 agent R24/R25 的 reasoning 包装成干预 —— **没有维度卡片的独立贡献**
- ContainerKill 三件套是 trainticket 最清晰的故障类，**baseline 失败原因是 chronic 锚定不是数据缺信号**

---

## Case 1394 · `ts-seat-service-stress (getLeftTicketOfInterval)` · JVMMemoryStress mem_type=2 (direct memory)

**核心翻盘机制**：
- 引导 agent 跨层查 metric → 浮现 ts-seat-service jvm.cpu / container.cpu / 端点 getLeftTicketOfInterval span 暴涨
- specific metric 维度

**baseline 失败模式**：T1 Silence-as-Health —— 锚 ts-travel-service / ts-travel2-service（cascade 中段，loud avg），没查 seat-service 自己 metric

**chaos 隐蔽性**：mem_type=2 = direct memory，**比 heap 隐蔽**（不触发标准 OOMError 信号、heap dump 看不到、GC 日志不显著）

**审稿人攻击面**：（OBS 顶部无详细 leakage 分析，需要补查 reasoning_log vs intervention 的词频对照）

---

## Case 2390 · `ts-user-service-stress (InitUser.run)` · JVMMemoryStress mem_type=2

**核心翻盘机制**：
- baseline 对比浮现 incident-only signal
- **chronic 排除**：dismiss baseline 锚定的 ts-rabbitmq（DNS chronic noise，normal/abnormal 同级别）
- specific metric 次要支撑

**baseline 失败模式**：T3 Noise-Anchor —— RabbitMQ chronic 锚定（与 1143/3716 同款）

**chaos 部分生效风险**：注入在 `InitUser.run` —— **init 类方法可能仅启动调用一次**或被 Spring scheduled task 反复触发。需要 duckdb 验证 abnormal 期是否真有 InitUser.run 类 span 出现 + 延迟暴涨（与 case 339/2130/3868 同类风险）

---

## Case 2988 · `ts-basic-service-stress (queryForStationId)` · JVMCPUStress cpu_count=5

**核心翻盘机制**：
- baseline 对比 + 引导 agent 查 metric
- **specific metric 极强**：cpu_count=5 = 5 个 CPU 烧死循环 → ts-basic-service jvm.cpu / container.cpu 飙升
- queryForStationId span 慢

**baseline 失败模式**：T5 Query-Blindness —— baseline 跑过 query 但**解读错**（看到 ts-route-service trace duration outlier 误锚定它而非 GT）

---

## Case 3059 · `ts-order-service-corrupt` · NetworkCorrupt (corrupt=48%, both)

**核心翻盘机制**（应该用什么 vs 实际用了什么）：
- **真信号本应在 caller-callee edge ratio**（NetworkCorrupt 包损坏让 connection 不稳，调用边变化——同 case 1140/2678/2715/4229/4510 NetworkChaos 类标准指纹）
- 但 advisor 实际选了 baseline 对比浮现 incident-only signal —— 维度选择次优
- 翻盘归因 **partial match 巧合**：v4 选 ts-ui-dashboard，GT 是 [ts-order-service + ts-ui-dashboard] → judge 算 correct（命中 GT 之一）

**baseline 失败模式**：T3 Noise-Anchor —— 锚 ts-config-service（弱信号 + cascade 末端）

**审稿人攻击面 / caveat**：
- ⚠️ **conc 因 API 降级未触发**（同 572 同款 INVALID_MODEL_ID）—— mid 单独承担
- ⚠️ **partial match 巧合**：v4 没选到核心 GT (order-service)，只命中 cascade 受波及的 ui-dashboard

**中间件代码层面问题**（暂存，不参与轨迹失败模式归纳）：
- 干预输出中文（dimension_cards.py 中文模板问题）—— 留待后续中间件代码注意事项单独讨论

---

## Case 3716 · `ts-food-service-stress (home)` · JVMMemoryStress mem_type=2

**核心翻盘机制**：
- baseline 对比 + **chronic 排除**（baseline 锚 ts-rabbitmq）
- specific metric
- 但翻盘归因可疑：agent R67 think 完全**照抄** advisor 列出的 4 个故障类型，R68-R83 真去查这些 → **不是元认知贡献，是 advisor 直接喂答案**

**baseline 失败模式**：T3 Noise-Anchor（RabbitMQ chronic 锚定）

**中间件代码层面问题**（暂存，不参与轨迹失败模式归纳）：
- 🔴🔴 HARD violation：中文输出 + 服务名硬编码 + 故障机制名硬编码（OOMKilled / liveness probe 等）
- → 留待后续中间件代码注意事项单独讨论

---

## Case 4032 · `ts-auth-service-stress (getHello)` · JVMMemoryStress heap

**核心翻盘机制**：
- 引导 agent 反向思考"是不是 origin 在别处"（**反向因果方向提示**）
- specific metric (jvm/cpu)

**baseline 失败模式**：T1 Silence-as-Health —— 锚 ts-ui-dashboard（cascade 末端 victim）

**chaos 必然生效**：注入在 `getHello` 健康检查接口 —— **经常被调用**（健康检查频繁触发），chaos 必然生效。这与 case 339/2130/3868 形成对比（注入在不被调用的方法上）

**12 case 中独特性**：唯一靠"反向因果方向反思"承重的 case（其他都是 baseline 对比 / 跨层 metric / silent service ranking）

---

## Case 4353 · `ts-station-service-stress (queryForIdBatch)` · JVMMemoryStress heap

**核心翻盘机制**：
- 引导 agent 跑 normal_traces 父子关系 SQL 找 silent service（**silent service ranking 维度**，与 1114 同款）
- specific metric 次要支撑

**baseline 失败模式**：T2 Blame-the-Messenger —— 锚 ts-basic-service（cascade 中段 victim，agent 看 trace 排名）

**12 case 中独特性**：**最干净的 silence-driven 翻盘案例**——advisor 干预**无 secondary 维度**（单维度触发）+ 干预 prompt 本身 leakage 等级低（NONE-MILD）+ 没有 API 降级问题。如果要在 53 case 里找一个"维度卡片独立贡献"的强证据，case 4353 是最佳候选

---

## 12 case 标签矩阵（汇总）

| # | DI | chaos 类型 | 翻盘机制 | baseline 失败模式 | 评估 caveat | 中间件代码问题（暂存） |
|---|---|---|---|---|---|---|
| 1 | 281 | JVMMemoryStress (heap) | baseline 对比 + chronic 排除 + 端点 duration 分布 75x | loud victim 锚定 chronic | 🔴 STRONG leakage | — |
| 2 | 572 | HTTPResponsePatchBody | **无 v4 贡献**（API 降级 + partial match 巧合） | chronic noise 锚定 + 没查 GT 之一 | API 降级 / partial match | — |
| 3 | 807 | JVMCPUStress | specific metric | loud victim 锚定 | 干预延迟生效 14 round | trigger 实现/卡片不一致 + 列具体层名 |
| 4 | 1114 | JVMMemoryStress (heap) | silent service ranking + specific metric 次要 | loud victim 锚定 + 把 silent 当 healthy | 🟠 MEDIUM leakage ([B5/B7] 不对称) | — |
| 5 | 1143 | ContainerKill | specific metric + 三件套指纹 + chronic 排除 | chronic 锚定 (RabbitMQ DNS) | 🔴🔴 **EXTREME** leakage | — |
| 6 | 1394 | JVMMemoryStress (direct memory) | specific metric | loud victim 锚定 | 待补查 leakage | mem_type=2 比 heap 隐蔽 |
| 7 | 2390 | JVMMemoryStress (direct memory) | baseline 对比 + chronic 排除 | chronic 锚定 (RabbitMQ) | 待补查 leakage | InitUser.run 部分生效风险 |
| 8 | 2988 | JVMCPUStress (cpu_count=5) | baseline 对比 + specific metric | trace duration outlier 误锚 (T5 Query-Blindness) | 待补查 leakage | — |
| 9 | 3059 | NetworkCorrupt | **应用 caller-callee edge ratio**（实际 advisor 选 baseline 是次优）+ partial match | 弱信号锚定 cascade 末端 | conc API 降级 / partial match / 维度选择次优 | 中文输出 |
| 10 | 3716 | JVMMemoryStress (direct memory) | baseline 对比 + chronic 排除（但 advisor 直接喂答案）| chronic 锚定 (RabbitMQ) | advisor 喂答案不算元认知贡献 | HARD violation：中文 + 服务名/故障机制硬编码 |
| 11 | 4032 | JVMMemoryStress (heap) | 反向因果方向提示 + specific metric | loud cascade-末端 victim | 待补查 leakage | — |
| 12 | 4353 | JVMMemoryStress (heap) | silent service ranking | loud cascade-中段 victim | 🟢 NONE-MILD leakage（最干净） | — |

**矩阵列说明**：
- 翻盘机制：用 18 case 体系语言描述的具体行为标签
- 评估 caveat：影响"v4 贡献"统计的因素（API 降级、partial match、leakage 等级、维度选择次优、advisor 喂答案）—— 这些是失败模式归纳和评估方法论范畴
- 中间件代码问题：原则 4 违规、卡片模板语言、trigger 实现 bug —— 这些**留待后续单独讨论**，不参与失败模式归纳

---

# 12 saved case 的 agent 自助解决路径（不依赖中间件干预）

**目的**：从纯 agent 调查行为视角分析——如果 agent 不靠中间件，每个 case 应该跑什么 SQL / 看到什么具体线索才能找到 RC。这套路径是 v4.1 失败模式归纳的"正向参照"——失败 case 的盲点对应这里的"必查动作"。

---

## Case 281 · JVMMemoryStress (heap) on `ts-station-food-service`

**必查**：
1. **全服务 baseline 对比**：`SELECT service_name, COUNT(*), AVG(duration), normal vs abnormal ratio` 升序+降序
2. **chronic 排除**：对 baseline 里看到的高 ERROR 服务跑 `WHERE message LIKE pattern` 在 normal/abnormal 期分别计数
3. **端点级 duration 分布**：`SELECT span_name, MEDIAN/p90/p95 duration` GROUP BY service+span_name normal vs abnormal
4. **specific metric**：`WHERE metric='k8s.container.restarts' AND attr.k8s.pod.name LIKE 'ts-station-food-service%'`

**关键线索**：
- ts-food-service "Get Food Request Failed" normal 269 / abnormal 195（**normal 更多 = chronic noise，dismiss**）
- ts-station-food-service POST /stationfoodstores 端点 **p90: 17ms → 1268ms (75x)**
- ts-station-food-service container.restarts **0→1** + 18 秒 restart gap

---

## Case 572 · HTTPResponsePatchBody on `ts-food-service`

**必查**：
1. abnormal_logs WHERE service='ts-food-service' 看是否有"业务级 NULL 错误"（如 `foodStoresListResult is null`）
2. ts-food-service / ts-train-food-service 端点 trace status_code 分布
3. 端点 duration distribution（不只看 max，看 avg/p50/p95/p99）

**关键线索**：
- ⚠️ **没有强信号**：`foodStoresListResult is null` normal 15 vs abnormal 11（chronic noise，反而 normal 更多）
- 端点 status_code 全 Unset（无 Error）
- duration max 522ms 是单点 outlier，p95 几乎不变（**不能用 max 做 RC 判据**）

**结论**：HTTPResponsePatchBody 在 trainticket 几乎不留 incident-specific 信号。**agent 单独靠数据找不到 RC**——这个 case 翻盘是 partial match 巧合。

---

## Case 807 · JVMCPUStress on `ts-train-service`

**必查**：
1. **specific metric (强制清单)**：`WHERE metric IN ('jvm.system.cpu.utilization', 'jvm.system.cpu.load_1m', 'container.cpu.usage', 'k8s.container.restarts')` GROUP BY service ORDER BY abnormal/normal ratio DESC
2. ts-train-service 端点 (`GET /trainservice/trains/byName`) duration distribution
3. ts-train-service trace count + log count normal vs abnormal

**关键线索**：
- ts-train-service **`jvm.system.cpu.utilization`** 突变到 **92%** + restart @ 14:42:12
- trains/byName 端点 latency 整体偏移
- ts-train-service 自己 silent on errors（trace 排名不在前 5），但 metric 维度极强

---

## Case 1114 · JVMMemoryStress (heap) on `ts-config-service`

**必查**：
1. **silent service ranking**：列出每个服务 normal/abnormal **trace count ratio 升序**，浮现 silent 服务
2. **caller-callee edge ratio**：跑 `(parent service, child service)` 的 child span count normal vs abnormal
3. **specific metric (强制清单)** on top silent / top edge-drop 服务
4. **端点 duration 桶分布**对比（5-50ms / >500ms 各桶 normal vs abnormal）

**关键线索**：
- ts-config-service 在 abnormal trace 排名里被 silent 但被多个 caller 调用（normal_traces 看父子关系明确）
- ts-config-service **container.restarts 0→1** + container.cpu 排第一（avg 0.77，第二名 5x）+ jvm.system.cpu 2.34x + page_faults 2.95x
- 端点 5-50ms 桶 16x、>500ms 桶 normal 0 → abnormal 23 条
- ⚠️ 注意不要用 max 单值（max 926ms 是 outlier，真实 avg 仅 3.7x）

---

## Case 1143 · ContainerKill on `ts-food-service`

**必查**：
1. **specific metric (ContainerKill 必查指纹)**：`k8s.container.restarts` / `jvm.class.loaded` / `container.cpu.time`（counter 类）
2. **trace silence gap**：`SELECT MIN(time), MAX(time) FROM abnormal_traces WHERE service_name='ts-food-service' GROUP BY 时间窗`，找时间空洞
3. **chronic 排除**：RabbitMQ DNS 类错误 normal vs abnormal

**关键线索**（ContainerKill 三件套指纹）：
- `k8s.container.restarts` **0→1**
- `jvm.class.loaded` **1.25 → 6705 (5364x)** —— JVM cold-start 强指纹
- `container.cpu.time` counter **reset (568→129)** —— 进程重启的标志
- 47 秒 trace silence gap @ 08:26:57-08:27:42
- ts-rabbitmq UnknownHostException normal 141 / abnormal 109 → **chronic，dismiss**

---

## Case 1394 · JVMMemoryStress (direct memory) on `ts-seat-service.getLeftTicketOfInterval`

**必查**：
1. **specific metric (强制清单)** on ts-seat-service
2. SeatController.getLeftTicketOfInterval 这个具体 span_name 的 duration distribution
3. silent service ranking（这个 case agent 容易锚 cascade 中段的 ts-travel-service / ts-travel2-service）

**关键线索**：
- ts-seat-service `jvm.system.cpu.load_1m` / `container.cpu.usage` 飙升
- `SeatController.getLeftTicketOfInterval` span avg / p99 暴涨
- ⚠️ direct memory 的 chaos 不会触发 OOMError、heap dump 看不到、GC 日志不显著——**只能靠 jvm.cpu / container.cpu 这种宏观 metric 看到，靠 log 看不到**

---

## Case 2390 · JVMMemoryStress (direct memory) on `ts-user-service.InitUser.run`

**必查**：
1. **baseline 对比** + **chronic 排除**（RabbitMQ chronic）
2. **specific metric** on ts-user-service
3. abnormal_traces WHERE service='ts-user-service' 看是否真有 InitUser 类 span

**关键线索**：
- baseline 对比：ts-user-service 端点 duration / count 异常
- ts-rabbitmq chronic dismiss
- ts-user-service container.memory / jvm.cpu 异常
- ⚠️ **InitUser.run 是初始化方法**——理论上启动后不再调用。需要先验证 abnormal 期是否真有它的 span 出现 + 延迟暴涨；如果完全没有，chaos 部分生效，信号会很弱

---

## Case 2988 · JVMCPUStress (cpu_count=5) on `ts-basic-service.queryForStationId`

**必查**：
1. **specific metric** on ts-basic-service: `jvm.system.cpu.load_1m` / `container.cpu.usage`（cpu_count=5 信号极强）
2. baseline 对比 + queryForStationId span duration
3. ⚠️ **警惕 trace duration 排名 outlier**：ts-route-service 等 cascade 末端可能出现极端 outlier（**幸存者偏差** + 排队 artifact），不是 RC

**关键线索**：
- ts-basic-service `jvm.system.cpu.load_1m` 大涨（5 个 CPU 烧死循环）+ container.cpu.usage 显著升高
- queryForStationId 端点 latency 升高
- ⚠️ 不要被 ts-route-service 的 trace duration outlier 误导（典型 T5 Query-Blindness 陷阱）

---

## Case 3059 · NetworkCorrupt (corrupt=48%, both) on `ts-order-service ↔ ts-ui-dashboard`

**必查**：
1. **caller-callee edge ratio**：跑全 cross-service edge ratio 升序，看 `(ui-dashboard, order-service)` 边是否大跌
2. trace error / status_code 部分缺失模式（packet corruption 让某些 trace span 不完整）
3. order-service 与 ui-dashboard 之间的双向请求-响应是否对应不上

**关键线索**：
- `(ui-dashboard, order-service)` caller-callee edge child span count 大跌
- order-service 内部业务正常（自己 metric 没事），但与 ui-dashboard 通信失败/损坏
- ⚠️ NetworkCorrupt 的真信号在 edge 维度，不在 service-level avg

---

## Case 3716 · JVMMemoryStress (direct memory) on `ts-food-service.home`

**必查**（与 case 281 / 1143 同模板）：
1. **baseline 对比** + **chronic 排除**（RabbitMQ chronic dismiss）
2. **specific metric** on ts-food-service: container.restarts / jvm.cpu / container.cpu
3. FoodController.home 端点 duration distribution
4. `k8s.container.restarts` on ts-food-service

**关键线索**：
- ts-rabbitmq chronic dismiss
- ts-food-service container.cpu + jvm.cpu 飙升 + container.restarts 0→1
- home 端点 latency 暴涨
- ⚠️ direct memory 同 case 1394——只能靠 jvm/container metric 看到，log 不显著

---

## Case 4032 · JVMMemoryStress (heap) on `ts-auth-service.getHello`

**必查**：
1. **反向因果方向追踪**：baseline 看到 ts-ui-dashboard 端点慢但 ui-dashboard 自己 metric 正常 → 沿调用链向它的下游查
2. **specific metric** on auth 类服务（ts-ui-dashboard 调的所有下游）
3. AuthController.getHello 健康检查端点 latency

**关键线索**：
- ts-auth-service `jvm.system.cpu.load_1m` / `container.cpu.usage` 暴涨
- getHello 端点 latency 暴涨
- ⚠️ ui-dashboard 是 cascade 末端 victim，不要锚定它——回看它调的下游（auth / verification-code 等）哪个有 specific metric 异常

---

## Case 4353 · JVMMemoryStress (heap) on `ts-station-service.queryForIdBatch`

**必查**：
1. **silent service ranking**：跑 normal_traces 父子关系 SQL 找"该出现但没出现 / 该响应但响应少"的服务
2. **specific metric** on ts-station-service
3. queryForIdBatch span duration distribution

**关键线索**：
- normal 期 ts-station-service 被多个上游（ts-basic-service / ts-travel-service 等）频繁调用，abnormal 期对应 caller-callee edge 跌
- ts-station-service `jvm.system.cpu` / `container.cpu` 升高
- queryForIdBatch span duration 升高
- ⚠️ baseline 锚 ts-basic-service（cascade 中段 victim）—— basic-service 自己 jvm/cpu 正常 + 它的下游有真异常

---

## 12 case 必查动作汇总（按使用频率）

| 必查动作 | 涉及 case 数 | 关键线索类型 |
|---|---|---|
| **specific metric**（jvm.cpu / container.cpu / restarts / jvm.class.loaded / container.cpu.time / page_faults） | **11/12** | 数值 ratio (jvm.cpu 2-20x / restart 0→1 / page_faults 2-5x) |
| **chronic 排除**（normal vs abnormal log message count） | 4/12（281/1143/2390/3716）| normal ≥ abnormal 即 dismiss |
| **baseline 对比**（全服务 trace count + service avg ratio） | 6/12（281/2390/2988/3059/3716/4032）| 浮现 incident-only signal |
| **caller-callee edge ratio** | 1/12（3059）| edge ratio 大跌（NetworkChaos 类指纹）|
| **silent service ranking**（normal_traces 父子关系） | 2/12（1114/4353）| 该被调用但没被调用的服务 |
| **端点级 duration distribution**（不只看 service avg） | 6/12（281/807/1114/1394/2988/3716）| 单端点 ratio 远超 service-level ratio |
| **反向因果方向**（cascade 末端 victim 追上游） | 1/12（4032）| 末端服务 metric 正常但端点慢 |
| **trace silence gap 检测**（时间窗 trace 完全消失） | 1/12（1143 ContainerKill）| 47 秒空洞 |

**结论**：
- **specific metric (11/12)** 是最高频必查动作——agent 必须有 specific metric_name 清单（不是用 LIKE 通配模糊搜）
- **chronic 排除 + baseline 对比 + 端点级 duration** 是次高频，三者共同构成"基础调查工具箱"
- **caller-callee edge / silent service ranking / 反向因果** 是低频但**关键的 case-specific 维度**——某些 chaos 类型（NetworkChaos / cascade trap）只能靠这些维度命中
- **case 572 是 12 case 中唯一无解 case**（HTTPResponsePatchBody 在 trainticket 数据集信号在 noise floor，agent 单独无法找到 RC）

---

# Task 2 · 22 个 framework-internal not-saved case 失败模式诊断（2026-04-29 起）

**目的**：找 v4 中间件干预了但没翻盘的 case 的具体失败模式，提炼 v4.1 应增加的 advisor 维度。

剩余 case：33 / 99 / 156 / 579 / 784 / 1195 / 1218 / 1459 / 1495 / 1814 / 1846 / 1917 / 1948 / 2211 / 2253 / 2258 / 2713 / 3760 / 4081 / 4363 / 4375 / 4463 / 4617

---

## Case 99 · `ts0-ts-consign-price-service-stress-t67vtg` · JVMMemoryStress (mem_type=1, heap)

| 字段 | 值 |
|---|---|
| GT | `ts-consign-price-service` |
| theme / tier | T2_Blame-the-Messenger / stable |
| baseline pred | `ts-consign-service` ❌ (qpf=47) |
| v4 pred | `ts-consign-service` ❌ (qpf=53) |
| 干预 | mid M6+M5 @ R30 / conc M8 @ R48 |

### 调用树

```
loadgen → ts-ui-dashboard → ts-consign-service (PUT updateConsign)
                              └─ GET → ts-consign-price-service ◀── GT (chaos)
```

### duckdb 关键证据

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| GT `container.cpu.usage` | 0.0086 | **1.3224** | **153.82x** ⭐ |
| GT `k8s.pod.cpu.usage` | 0.0087 | 1.444 | 166.58x |
| GT `k8s.container.restarts` | 0 | **1** | trap→fire |
| GT log SEVERE 计数 | 0 | 0 | silent (JVM 卡住) |
| GT `GET /consignprice/...` 端点 p99 | 54.9ms | 873.3ms | 15.9x |
| caller→callee edge ratio (consign-service → consign-price-service) | 8 | 5 | **0.625** (top1 跌幅) |
| 上游 ts-consign-service service avg duration | 9.1ms | 491.3ms | 53.8x（loud victim） |
| 上游 ts-consign-service `GET` span avg | 45.0ms | 2920.1ms | 64.9x（被 sidecar timeout） |
| 上游 ts-consign-service log SEVERE 计数 | 0 | 23 | incident-only |

503 message body 原文：`upstream connect error or disconnect/reset before headers ... transport failure reason: delayed connect error: Connection refused` —— **是 envoy sidecar 报告的上游不可达**，发出方是 messenger 不是 RC。

### baseline 推理（47 round → ts-consign-service ❌）

R40 think 锚定"ts-consign-service: 69 error spans (vast majority)" → R47 think 加固"23x HTTP 503 + 23x HTTP 500" → FINAL commit。

**baseline 失败点**：
1. **503 message provenance 误读** —— 没读 message body 里的 `upstream connect error`
2. **loud victim 锚定** —— 抓 trace duration 53.8x 的 service，不沿父子关系下钻一跳
3. **没查任何 specific metric** —— 全程 trace+log 维度，从未查过 abnormal_metrics 中任何服务的 container.cpu / jvm.cpu / restarts
4. **没跑 caller-callee edge ratio** —— 没列出过任何父子边表

### v4 推理（53 round → ts-consign-service ❌）

| Round | 行为 |
|---|---|
| R1-R29 | 同 baseline 锚定 ts-consign-service |
| R30 mid M6+M5 | agent_response 空（无复述） |
| R31-R42 | 跑了 baseline 对比（normal 期 503/connection-refused/error 全表扫 → 0 命中），✅ 确认 incident-only，但 ❌ 加固了错锚点 |
| R44 think | "Only ts-consign-service has Error → confirms it as RC"（**confirmation bias**） |
| R48 FINAL #1 | commit ts-consign-service |
| R48→R49 conc M8 | "called service positive evidence?" → agent 复述："I don't have positive evidence identifying what service runs at 10.0.3.133:8080" 但**反演方向反了** |
| R50 think | "If ts-consign-service were healthy, would the 503 occur? Answer: No, because the error happens within ts-consign-service" —— 把 503 当 ts-consign-service 内部错误 |
| R51-R53 | 又 drill ts-consign-service GET span 几次 |
| FINAL #2 | ts-consign-service ❌ |

**v4 干预实际效果**：
- mid M6+M5：✅ 触发 baseline 对比 → ❌ 加固错锚（confirmation bias）。M5 silent service hint 抽象，agent 没去看哪个 metric silent。
- conc M8：理论命中（直接说"被调用服务有正向证据吗"）→ ❌ agent 反演方向反了 + 来得太晚（commit 后只剩 5 round）。
- 全程 0 次 `SELECT * FROM abnormal_metrics WHERE service_name='ts-consign-price-service'` —— 这一条 SQL 就能看到 container.cpu 153x 直接 commit GT。

### 失败模式

**主要**：F2 advisor 维度对但 reasoning 不动（confirmation bias 主导，mid + conc 都被吃掉）

**baseline 子模式**：503 message provenance 误读 + loud victim 锚定 + trace 中断点 fallacy

### 中间件如何提示能翻转（用户笔记 2026-04-29）

| 维度 | 触发条件 | 干预语 |
|---|---|---|
| **caller-callee edge ratio** | 候选服务 503/upstream-error log + has child GET/POST span | "你的候选服务报 503/upstream-error，这通常是它在调用某个下游时被拒绝。请跑 (caller, callee) 父子边 ratio 升序，跌幅最大的那条边的 callee 才是 RC，不是报错的 caller。" |
| **specific metric on downstream callee** | 同上 | "对你候选服务通过 GET/RPC 调用的所有下游服务，逐个查 abnormal_metrics 中的 container.cpu.usage / jvm.cpu / k8s.container.restarts。container.cpu 100x+ 或 restart 0→1 直接是 chaos target。" |
| **503 message provenance** | message LIKE '%upstream connect error%' OR '%Connection refused%' | "envoy sidecar 的 503 消息体写明 upstream connect error，发出请求的服务是 messenger，连接拒绝的目标 IP/host 才是 RC。请用 attr_destination_workload 或 trace span_name (GET/POST) 反查目标。" |
| **silent service ranking** | normal_traces 父子关系预期 | "对每条 normal_traces 父子边 (caller, callee)，比较 abnormal_traces 同样边的出现次数。出现次数最少（甚至 0）但 caller 仍频繁活动的 callee 就是 silent target。" |

### 中间件代码层面问题

- mid M6 触发太早（R30）—— 锚已稳定，baseline 对比反成"incident-only 加固器"
- conc M8 触发于 R48 FINAL 之后，commit 后只剩 5 round 不够换路径
- M8 文本太抽象（"反例隔离"），没指引"去查目标服务的 container.cpu / jvm.cpu"
- 卡片库未编码 503 message provenance 这条决定性指引

### 判断

- 数据完整性：✅
- chaos 生效：✅ 必然生效（注入在频繁调用的业务方法）
- 盲区类型：**(b) 框架盲区** —— 19 类 intent 缺"caller-callee edge"和"downstream metric drill"两个意图，advisor M6+M5+M8 抽象语言被 confirmation bias 吃掉
- 给 v4.1：(1) 503/upstream-error log 检测 → 强制具体 SQL 模板；(2) mid 触发前检测 anchor 稳定性，稳定时优先发 specific-metric 强查而非 baseline 对比；(3) conc 提前到 R30-R35

---

## Case 33 · `ts0-ts-auth-service-stress-nlpsfx` · JVMMemoryStress (mem_type=2, direct memory)

| 字段 | 值 |
|---|---|
| GT | `ts-auth-service` |
| theme / tier | T3_Noise-Anchor / stable |
| baseline pred | `ts-rabbitmq` ❌ (qpf=60) |
| v4 pred | `ts-ui-dashboard` ❌ (qpf=61) |
| 干预 | mid M6+M5 @ R30 / conc M8+M5 @ R52 |
| transition | wrong→wrong（**drift 到不同的错答案**） |

### chaos 机制

JVM direct memory stress on `JWTProvider.init`（Spring 启动初始化方法）。byte code 注入 → direct memory OOM → pod restart → init 再跑再被卡 → 反复重启。run-time 反复重启，但 init 方法只在启动期执行，业务路径上的 `POST /login` 重启完成后即恢复。**chaos 部分生效**（物理重启发生但业务 trace 不直接受影响）。

### 调用树

```
loadgen → ts-ui-dashboard (POST /login) → ts-auth-service (UserController.getToken) ◀── GT
                                              └─ ts-verification-code-service / DB
```

### 关键 duckdb 证据

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| GT `container.cpu.usage` | 0.3604 | **2.4605** | **6.83x** ⭐ |
| GT `k8s.pod.cpu.usage` | 0.4253 | 2.5039 | 5.89x |
| GT `jvm.cpu.recent_utilization` | 0.0034 | 0.0109 | 3.18x |
| GT `k8s.pod.memory.page_faults` | 158,253 | 451,687 | 2.85x |
| GT `k8s.container.restarts` | 0 | **1** | trap→fire |
| GT log SEVERE | 0 | 0 | silent on errors |
| GT trace count | 6120 | 4310 | 0.70x（重启期不上报） |
| GT service avg duration | 23.5ms | 25.5ms | 1.1x（**post-restart 看着正常**） |
| rabbitmq DNS error log | normal=380 | abnormal=317 | **normal > abnormal**（纯 chronic noise） |
| ts-ui-dashboard `POST /login` | ~95ms | 2.4-9.8s | 25-100x（loud entry victim） |
| ts-ui-dashboard error trace | 0 | 57 | incident-only |

### baseline 推理（60 round → ts-rabbitmq ❌）

R6 锚 ts-food-service 126 errors → R30+ 锁 `UnknownHostException: ts-rabbitmq` → R59 first-error timestamp 13:46:56 是 food-service rabbit ERROR → R60 commit ts-rabbitmq。

**baseline 失败点**：
1. **chronic noise 锚定**：rabbit DNS error normal=380 > abnormal=317，应直接 dismiss
2. **first-error timestamp fallacy**：first 是 chronic noise 不是事件起点
3. **没查任何 specific metric**：从未查过 ts-auth-service container.cpu / restarts

### v4 推理（61 round → ts-ui-dashboard ❌）

| Round | 行为 |
|---|---|
| R1-R29 | 同 baseline 锚定 rabbitmq DNS chronic |
| R30 mid M6+M5 | agent_response 空 |
| R31-R52 | ✅ chronic 排除生效（rabbit normal 也有）→ ❌ drift to ts-ui-dashboard 503（loud entry victim） |
| R52 think | "503 + 调用链中断在 ui-dashboard → ui-dashboard 是 RC" | F3 drift |
| FINAL #1 | ts-ui-dashboard |
| R52→R53 conc M8+M5 | "反例隔离 + silent != healthy" 抽象 |
| R55 SQL bug | 终于试图查 ts-auth-service：`WHERE service_name='ts-auth-service' AND metric LIKE '%cpu%' OR metric LIKE '%memory%' GROUP BY service` —— **AND/OR precedence 错**，结果返回 rabbitmq/ts-wait-order-service 的 memory，不含 auth-service |
| R57-R60 | 查 login trace：error trace 只含 loadgen+ui-dashboard | 加固 ui-dashboard |
| R61 think | counterfactual："error trace 不含 ts-auth-service → auth-service is demonstrably healthy" | **silence-as-health 反演** |
| FINAL #2 | ts-ui-dashboard ❌ |

**v4 干预实际效果**：
- mid M6+M5：✅ chronic 排除 → ❌ drift 到 ts-ui-dashboard
- conc M8+M5：M5 silent service 干预语反向解读，SQL precedence bug 让 specific metric 查询失败 + advisor 没纠正机会 → 维持错答案

### 失败模式

- baseline：**chronic noise 锚定** + **first-error timestamp fallacy**
- v4：**F3 agent drift 到另一个 noise** + **F2 confirmation bias**（M5 silent 反向解读）+ **silence-as-health fallacy** + **trace 中断点 fallacy**

### 中间件如何提示能翻转（用户笔记 2026-04-29）

| 维度 | 触发条件 | 干预语 |
|---|---|---|
| **chronic noise 排除（具体阈值）** | 候选服务的 error pattern 出现在 normal 期 | "把候选锚定的 error message 同时跑 `SELECT COUNT(*) FROM normal_logs WHERE message LIKE '%X%'` vs abnormal。若 normal/abnormal ratio < 2 或 normal 反而更多，立即 dismiss 该锚点。" |
| **specific metric SQL 模板（强制）** | 任何怀疑某服务时 | "查疑似服务的资源消耗：`SELECT metric, ROUND(AVG(value),4) FROM abnormal_metrics WHERE service_name='<X>' GROUP BY metric ORDER BY 2 DESC LIMIT 10`，对比 normal_metrics。container.cpu.usage 5x+ / restart 0→1 / page_faults 2x+ 直接是 chaos target。" |
| **silent-target test（不是 silent-as-health）** | trace 链断点处 | "调用链中断不一定是中断点服务故障。请查中断点服务和中断点之后应该被调用的下游服务的 metric。如果下游服务有 cpu 飙升 + restart 但 trace silent，那才是真 RC。沉默 != 健康。" |
| **restart counter 优先查** | 任何 cascade 起点判断 | "在锚定任何服务前，先跑 `SELECT service_name, MAX(value) FROM abnormal_metrics WHERE metric='k8s.container.restarts' GROUP BY service_name HAVING MAX(value) > 0`。restart 0→1 的服务直接是 chaos target，不需要其他证据。" |
| **SQL precedence guard** | agent 写的 SQL 含 `AND ... OR ...` 但没括号 | （元层面）advisor 可以提示"你刚才的 SQL `WHERE A AND B OR C` 等价于 `(A AND B) OR C`，请用 `WHERE A AND (B OR C)`，否则结果会包含所有 service" |

最有效组合：**全局 restart counter 扫描** —— 一条 SQL 直接定位到 ts-auth-service（restart 0→1 + cpu 6.83x）。

### 中间件代码层面问题

- mid 后没有 follow-up advisor 防止 drift（chronic 排除生效但 anchor 切到 cascade 上游 entry victim）
- conc M8+M5 文本太抽象，没有强制具体 SQL（restart counter / specific metric 模板）—— agent 反演方向反掉
- M5 secondary 在 mid 和 conc 都触发但 agent 都没去查 silent-on-metrics 的服务
- advisor 不感知 agent 的 SQL precedence bug

### 判断

- 数据完整性：✅
- chaos 生效：⚠️ 部分生效（pod 真重启 + container cpu 6.83x，但注入 init 方法让 trace 维度看着正常）
- 盲区类型：**(b) 框架盲区**
- 给 v4.1：(1) restart counter 扫描提到 mid 阶段最早触发；(2) M8 配 specific SQL 模板；(3) mid 后增加 anchor-stability monitor，drift 时 follow-up；(4) silent service 干预语用"查下游 metric"代替"silent != healthy"

---

## Case 156 · `ts0-ts-order-service-stress-cklk2p` · JVMMemoryStress (mem_type=2, direct memory)

| 字段 | 值 |
|---|---|
| GT | `ts-order-service` |
| theme / tier | T1_Silence-as-Health / **ultra_hard** |
| baseline pred | `ts-seat-service` ❌ (qpf=48) |
| v4 pred | `ts-seat-service` ❌ (qpf=62) |
| 干预 | mid M6+M5 @ R30 / conc M8 @ R49 |
| transition | wrong→wrong（同一错答案） |

### chaos 机制

JVM direct memory stress on `OrderController.saveOrderInfo`（订单写入方法，不是直接 endpoint）→ container CPU 7x + restart 0→1 + jvm.cpu 4.68x。但 trace 维度上 service avg 仅 3.3x（排第 5），被 cascade 上游 victim seat-service（8x）压住。**chaos 必然生效**（业务方法常调）。

### 调用树

```
loadgen → ts-ui-dashboard → ts-travel-plan-service → ts-route-plan-service → ts-travel-service
                                  ↓
                          ts-seat-service (POST /seats/...)
                              └─ ts-order-service (saveOrderInfo / order/tickets)  ◀── GT
```

### 关键 duckdb 证据

#### GT (ts-order-service) 指纹

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| `hubble_http_request_duration_p90_seconds` | 0.0172 | 0.3539 | **20.60x** |
| `k8s.pod.cpu.usage` | 0.2123 | 1.9916 | **9.38x** |
| `container.cpu.usage` | 0.2472 | 1.7696 | **7.16x** |
| `jvm.cpu.recent_utilization` | 0.0015 | 0.0071 | 4.68x |
| `k8s.pod.memory.page_faults` | 167,486 | 419,097 | 2.50x |
| `k8s.container.restarts` | 0 | **1** | trap→fire |
| trace count | 8282 | 3460 | 0.42x |
| service avg duration | 6.7ms | 21.8ms | 3.3x（**仅排第 5**） |

#### 误锚 ts-seat-service（loud cascade victim）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| service avg duration | 33.5ms | 267.3ms | **8.0x** ⭐ top1 |
| log SEVERE 计数 | 0 | **56** | incident-only |
| `jvm.system.cpu.load_1m` | 76.46 | 174.21 | 2.28x（system-wide） |
| `k8s.container.restarts` | 0 | 0 | 无 |
| hubble HTTP duration | NaN | NaN | 无 |

#### 503 message provenance

```
ts-seat-service SEVERE × 56:
"503 Service Unavailable: [upstream connect error ... immediate connect error:
 Cannot assign requested address | remote address:10.0.3.156:8080]"
```
ts-seat-service 是 messenger，10.0.3.156:8080 是 ts-order-service。

#### caller-callee edge

| caller | callee | n_c | a_c | ratio |
|---|---|---|---|---|
| **ts-seat-service → ts-order-service** | | **1005** | **409** | **0.407** ⭐ |

### baseline 推理（48 round → ts-seat-service ❌）

R34 锚 "ts-seat-service hubble HTTP p95 max 10s" → R37 加固 "350x degradation"（实际是 hubble cap 值 timeout）→ FINAL ts-seat-service。

**baseline 失败点**：loud victim 锚定 + **hubble metric cap 值误读**（10s = envoy timeout 上限，不是真实分布）+ 503 message provenance 未读 + 全局 restart counter 未跑

### v4 推理（62 round → ts-seat-service ❌）

| Round | 行为 |
|---|---|
| R1-R29 | 锚 ts-seat-service hubble |
| R30 mid M6+M5 | agent_response 完整复述："compare normal/abnormal, look for silent" |
| R31-R44 | ✅ baseline 对比：seat-service 56 SEVERE incident-only → ❌ 加固错锚 |
| R49 FINAL #1 | ts-seat-service |
| R49→R50 conc M8 | "counterfactual + connection refused points to unreachable upstream" |
| R50 think | agent 复述很到位："is something seat-service depends on broken?" 几乎抓到 |
| R55+ | 找 silent service：ts-cancel-service normal 63 entries / abnormal 0 → **silent target 选错**（cancel 与本案无关） |
| R60 think | "ts-cancel absent... but seat 56 SEVERE → seat is RC" |
| FINAL #2 | ts-seat-service ❌ |

**v4 干预实际效果**：
- mid M6+M5：✅ baseline 对比执行 → ❌ 加固错锚
- conc M8：✅ 概念命中（"upstream unreachable"）→ ❌ silent search 跑偏到无关 ts-cancel-service，没去查 seat-service 的 callee

### 失败模式

- baseline：**loud victim 锚定** + **hubble cap 值误读** + **503 message provenance 误读**
- v4：**F2 confirmation bias**（mid baseline 加固错锚）+ **silent target 选错**（conc 概念命中但实际查无关服务）

### 中间件如何提示能翻转（用户笔记 2026-04-29）

| 维度 | 触发条件 | 干预语 |
|---|---|---|
| **callee 排除验证（commit 前必跑）** ⭐ | 已锚定候选 RC，准备 commit | "在 commit 候选服务前，必须证明它是**最下游**的 RC。请跑：(a) 候选服务在 normal_traces 中的 direct callee 列表；(b) 对每个 callee 查 abnormal_metrics 的 container.cpu / restart / page_faults。如果任一 callee 有 cpu 5x+ / restart 0→1 / page_faults 2x+，那么真正 RC 在下面一层，候选只是 messenger。" |
| **direct callee drill** | 候选服务有 503/upstream-error log | "查你候选服务在 normal_traces 中的直接 callee（`SELECT t1.service_name FROM normal_traces t1 JOIN normal_traces t2 ON t1.parent_span_id=t2.span_id WHERE t2.service_name='<候选>'`），逐个查这些 callee 的 abnormal metric。**silent service 不是看全局缺失，是看 callee 缺失**。" |
| **caller-callee edge ratio 强制** | 候选服务报 503 + cascade chain 多层 victim | "跑全图父子边 ratio 升序，跌幅最大且 n_c ≥ 30 的边的 callee 就是 RC。本类故障 (caller, callee) edge 跌到 0.4 是典型指纹。" |
| **hubble metric cap 值识别** | hubble HTTP duration 多个分位都接近 10s | "hubble HTTP duration 在 envoy proxy 层 cap 值是 10s（timeout 上限）。p50/p90/p95 都接近 10s 不是真实严重度，是 timeout 全发生 —— 反而说明该服务的 callee 把它的请求挂死了，要查 callee 不是查它本身。" |
| **restart counter 全局扫描（强制 mid 触发）** | 任何 cascade chain ≥ 3 层 victim | "跑 `SELECT service_name, MAX(value) FROM abnormal_metrics WHERE metric='k8s.container.restarts' GROUP BY 1 HAVING MAX(value)>0`。restart 0→1 直接是 chaos target。" |

最有效组合：**callee 排除验证（commit 前必跑） + hubble cap 值识别** —— commit-gate 强制查 seat-service callee 看 ts-order-service container.cpu 7x + restart 0→1 直接翻盘。

### 中间件代码层面问题

- mid M6+M5 触发后 agent 真的去 baseline 对比，但卡片库未编码"56 SEVERE incident-only 是 messenger 还是 RC"判别 → baseline 反成加固器
- conc M8 文本"connection refused points to unreachable" agent 完整复述但**不知道怎么查** → silent search 跑偏到 cancel-service
- 卡片库未定义"找候选的 direct callee"+"callee 排除验证"两条精确动作 —— M5 太抽象
- hubble HTTP duration 10s cap 值在多个 case 误读，advisor 应识别这种 pattern

### 判断

- 数据完整性：✅
- chaos 生效：✅ 必然生效
- 盲区类型：**(b) 框架盲区** —— 19 类 intent 缺"候选服务的 direct callee drill"+"hubble cap 值识别"+"callee 排除验证（commit-gate）"三个意图
- 给 v4.1：(1) commit-gate 强制 callee 排除验证（"证明你的候选是最下游 RC"）；(2) M5 silent service 改写为"找候选的 direct callee 并逐个查 metric"；(3) hubble HTTP 多个分位都 10s cap 时识别为 timeout fallacy；(4) 503/upstream-error log 检测 → 必发 caller-callee edge + direct callee metric 模板

---

## Case 579 · `ts1-ts-inside-payment-service-stress-6qq6f6` · JVMMemoryStress (mem_type=2, direct memory)

| 字段 | 值 |
|---|---|
| GT | `ts-inside-payment-service` |
| theme / tier | T1_Silence-as-Health / stable |
| baseline pred | `ts-ui-dashboard` ❌ (qpf=42) |
| v4 pred | `ts-ui-dashboard` ❌ (qpf=58) |
| 干预 | mid M6+M5 @ R30 / conc M8+M5 @ R47 |
| transition | wrong→wrong |

### chaos 机制

JVM direct memory stress on `CookieUtil.getCookieByName`（每个 payment 请求都调用的 cookie 解析方法）→ 部分请求被卡 → pod restart 0→1 + container.cpu 19.98x。`POST /inside_pay_service/inside_payment` 在 ui-dashboard 端表现为 503。**chaos 必然生效**（cookie util 在请求路径上）。

### 调用树

```
loadgen → ts-ui-dashboard (POST /inside_pay_service/inside_payment)
            └─ ts-inside-payment-service (CookieUtil.getCookieByName + Payment)  ◀── GT
                 └─ ts-order-service (PaymentRepository / addMoney)
```

### 关键 duckdb 证据

#### GT (ts-inside-payment-service) 指纹

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| `k8s.pod.cpu.usage` | 0.0277 | 0.8649 | **31.17x** |
| `container.cpu.usage` | 0.0363 | 0.7247 | **19.98x** |
| `k8s.pod.memory.page_faults` | 152,989 | 463,847 | 3.03x |
| `k8s.container.restarts` | 0 | **1** | trap→fire |
| trace count | 560 | 502 | 0.90x（**未真正 silent**） |
| service avg duration | 28.9ms | 36.3ms | 1.3x（mild） |
| `AddMoneyRepository.findByUserId` 端点 avg | 3.0 | 65.0 | **21.4x** ⭐ |
| `Session.persist Payment` | 0.3 | 1.8 | 6.6x |
| `SELECT Money` | 2.6 | 15.7 | 6.1x |
| log SEVERE | 0 | 2 | incident-only（弱） |

#### 误锚 ts-ui-dashboard

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| `container.cpu.usage` | 0.0261 | 0.0285 | 1.09x |
| `k8s.container.restarts` | 0 | 0 | 无 |
| service avg duration | 103.1ms | 70.4ms | **0.7x（更快了）** |
| `POST /inside_pay_service` 503 在 ui-dashboard | 0 | 22 | incident-only |

ui-dashboard 自己 cpu/memory/restart 全正常 —— 它只是 envoy 报 503（upstream 不可达），是 messenger。

### baseline 推理（42 round → ts-ui-dashboard ❌）

R20 锚 22x HTTP 503 → R32 think 失败 trace 中 payment-service span 缺失 → R40 think "ts-ui-dashboard returns 503 without ever calling payment-service" → FINAL ts-ui-dashboard。

**baseline 失败点**：silence-as-health 反演 + **失败 trace 子集偏差**（只看 error trace 不看全部 trace）+ 没查 specific metric

### v4 推理（58 round → ts-ui-dashboard ❌）

| Round | 行为 |
|---|---|
| R1-R29 | 锚 ui-dashboard 503 + 失败 trace 中 payment span 缺失 |
| R30 mid M6+M5 | agent_response 完整复述："compare normal/abnormal, distinguish 'never called' vs 'stopped responding'" |
| R31-R47 | 跑了 normal vs abnormal：normal "always present" / abnormal "completely missing" → ❌ **反向解读**："ui-dashboard returns 503 WITHOUT ever calling payment-service. The failure happens BEFORE the downstream call" |
| R36 think | "payment-service hubble HTTP NaN → NaN typically means NO HTTP requests" | **NaN fallacy** |
| R47 FINAL #1 | ts-ui-dashboard |
| R47→R48 conc M8+M5 | "counterfactual + 'not appearing has 2 explanations'" |
| R55 think | 看到 trace `c31f2a77...` 中 payment-service 有 "Unset" span → 解读为 "payment-service is **working**!" | silence-as-health 直接 |
| R57 think | counterfactual："If ui-dashboard healthy → 不会 503 → ui-dashboard RC" | 反演反掉 |
| FINAL #2 | ts-ui-dashboard ❌ |

**v4 干预实际效果**：
- mid M6+M5：✅ baseline 对比执行 + agent 完整复述概念 → ❌ 实操时仍反向解读（normal 有 abnormal 没 → 解读为 ui-dashboard 没调过去）
- conc M8+M5：✅ 概念命中 → ❌ Unset span 强化 silence-as-health + counterfactual 反演反掉

### 失败模式

- baseline：**silence-as-health 反演** + **trace 中断点 fallacy** + **失败 trace 子集偏差**
- v4：**F2 confirmation bias**（mid 概念命中但实操反向）+ **NaN metric fallacy**（hubble NaN = 没请求 ≠ 无法响应）+ **counterfactual 反演**（M8 概念正确但反演方向反掉）

### 中间件如何提示能翻转（用户笔记 2026-04-29）

| 维度 | 触发条件 | 干预语 |
|---|---|---|
| **失败 trace vs 全部 trace 区分** ⭐ | agent 用"失败 trace 中 X 缺失"做证据 | "你用'失败 trace 中 X 服务缺失'做证据，但失败 trace 是 X crash 后的样本，X 当然不出现。请改查全部 trace 的服务出现频率：`SELECT service_name, COUNT(*) FROM abnormal_traces GROUP BY 1` vs normal_traces。若 X 在 abnormal 总体仍有 80%+ 出现，那是部分请求被吃掉，X 自己被 chaos 击中。" |
| **NaN metric 区分** | hubble HTTP duration NaN | "hubble HTTP duration NaN 有两种解释：(a) 没请求；(b) 服务无法响应所以 envoy 没记录到 response。请同时查该服务 container.cpu.usage / k8s.container.restarts。若 cpu 5x+ 或 restart 0→1，那是 (b)，服务正在被 chaos 击中。" |
| **callee 排除验证（commit 前必跑）** | 已锚定候选 RC | "commit 候选前必须证明它是最下游 RC。查候选服务在 normal_traces 中的 direct callee 列表 + 每个 callee 的 abnormal metric。任一 callee 有 cpu 5x / restart 0→1 / page_faults 2x+，候选只是 messenger。" |
| **counterfactual 双向检查** | M8 干预 | "counterfactual 不只问'候选 healthy 会怎样'，也要问'候选的下游 healthy 会怎样'。若下游 healthy 但候选仍 503，那候选是 RC；若下游 healthy 候选不再 503，那候选只是 messenger。" |
| **endpoint level distribution** | 候选服务 service avg ratio < 2x 但被锚定 | "service avg ratio 不足 2x 不是 RC 的强证据。改查端点级 distribution（按 span_name group by），找端点 avg 5x+ 或 p95 10x+ 的服务。某些 chaos 只让 1-2 个特定端点变慢（如 cookie util 类）。" |

最有效组合：**失败 trace vs 全部 trace 区分 + NaN metric 区分** —— 一次性破解 silence-as-health 和 NaN fallacy 两个误读源。

### 中间件代码层面问题

- mid M6+M5 文本说"distinguish never-called vs stopped-responding"，agent 完整复述但实操时仍走错 —— 卡片库没给 SQL 模板（如何用数据区分）
- conc M8+M5 提到"not appearing has 2 explanations"，agent 复述但反演方向反掉 —— counterfactual 双向没强制
- M5 silent service 在本 case 是 trap：GT 不是真 silent（560→502 = 90% 仍在），M5 反而误导

### 判断

- 数据完整性：✅
- chaos 生效：✅ 必然生效
- 盲区类型：**(b) 框架盲区**
- 给 v4.1：(1) M5 silent service 区分"全部 trace silent" vs "失败 trace 中 silent"；(2) NaN hubble 检测 + 引导查 container.cpu / restart；(3) M8 counterfactual 改双向；(4) commit-gate 强制全局 restart counter 扫描

---

## Case 784 · `ts1-ts-station-food-service-stress-rlvxhc` · JVMMemoryStress (mem_type=1, heap)

| 字段 | 值 |
|---|---|
| GT | `ts-station-food-service` |
| theme / tier | T2_Blame-the-Messenger / stable |
| baseline pred | `ts-food-service` ❌ (qpf=23) |
| v4 pred | `ts-food-service` ❌ (qpf=80) |
| 干预 | mid M6+M5 @ R30 / no conc |
| transition | wrong→wrong |

### chaos 机制

JVM heap memory stress on `StationFoodServiceImpl.listFoodStores`（被 ts-food-service 调用获取站点食品清单）→ container.cpu 29x + restart 0→1 + hubble HTTP p90 21x。ts-food-service 调用后等超时，cascade 上去 503/500。**chaos 必然生效**。

### 调用树

```
loadgen → ts-ui-dashboard → ts-food-service (getAllFood)
                                  └─ ts-station-food-service (listFoodStores)  ◀── GT
```

### 关键 duckdb 证据

#### GT (ts-station-food-service) 指纹

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| `container.cpu.usage` | 0.0271 | 0.8004 | **29.51x** ⭐⭐ |
| `k8s.pod.cpu.usage` | 0.0401 | 0.8766 | 21.85x |
| `hubble_http_request_duration_p90_seconds` | 0.0141 | 0.2986 | 21.14x |
| `k8s.pod.memory.page_faults` | 141,253 | 528,159 | 3.74x |
| `k8s.container.restarts`（pod-level） | 0 | **1** | trap→fire |
| service avg duration | 2.6ms | 19.6ms | 7.6x（**仅排第 2**） |

#### 误锚 ts-food-service（cascade upstream messenger）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| service avg duration | 15.4ms | 234.0ms | **15.2x** top1 |
| `hubble_http_request_duration_p50_seconds` | 0.0083 | 0.5947 | 71.23x |
| `container.cpu.usage` | - | - | **1.08x（几乎无）** |
| `k8s.container.restarts` | 0 | 0 | 无 |
| log SEVERE 计数 | **337** | 212 | **normal > abnormal** chronic noise |

ts-food-service cpu/memory/restart 全正常 —— hubble 71x 是因为它在等 station-food-service 超时。**它 SEVERE 日志 normal=337 abnormal=212**，纯 chronic noise。

> ⭐ **核心 insight（用户笔记 2026-04-29）**：trace/log 异常但 metric 全正常 → 必查它的下游。这是判别 messenger vs RC 的最直接标准。food-service trace status=Error 63 条 + hubble 71x（看着像 RC）但 container.cpu / restart / page_faults 全 ≈ 1x，决定性指向"它在等下游"。

#### chronic noise 验证

```
food-service 'reGetTrainFoodListResult Get the Get Food Request Failed!':
  normal_logs: 278 行 / abnormal_logs: 175 行  ← normal > abnormal
```

#### 全局 restart counter 扫描

```
ts-station-food-service-* : restart 0→1  ⭐ chaos target
ts-ticket-office-service-* : restart 0→3 (background)
```

### baseline 推理（23 round → ts-food-service ❌）

R23 锚 "food-service 191 ERROR logs" → R68 dismiss "station-food-service errors are 'Duplicate entry, isolated data issues'" → R74 commit。

**baseline 失败点**：chronic noise 锚定（food-service ERROR log normal 比 abnormal 多）+ trace Error count fallacy（cascade 上游累积更多 Error）+ dismiss-victim fallacy（把 GT 的 transaction 失败当孤立数据问题）+ 没查 metric/restart

### v4 推理（80 round → ts-food-service ❌）

| Round | 行为 |
|---|---|
| R1-R29 | 锚 ts-rabbitmq DNS chronic + food-service errors |
| R30 mid M6+M5 | agent_response 完整复述 |
| R31-R45 | ✅ 看到 food-service 63 Error abnormal vs 0 normal → 加固 food-service |
| R136 | "station-food-service root span errors" 误读为孤立 |
| R178 | ✅ 关键发现："station-food-service errors 和 food-service errors 在 SEPARATE traces (no intersection)" → 但没结合反思 |
| R199 | ✅ chronic check："reGetTrainFoodListResult exists in BOTH normal and abnormal logs" → 看到了但没 dismiss food-service |
| R253 FINAL | "food-service HIGH_ERROR_RATE (63 error traces)" | F2 confirmation bias |

**v4 干预实际效果**：
- mid M6+M5：✅ baseline 对比 + chronic check 都做了 → ❌ 都没转化为 dismiss 动作
- **80 round 内只触发 mid 干预，没有 conc** —— 干预 throttling 问题

### 失败模式

- baseline：**chronic noise 锚定** + **trace Error count fallacy**（cascade 上游累积 Error）+ **dismiss-victim fallacy**
- v4：**F2 confirmation bias**（chronic 看到了但没行动）+ **trace Error 优先级误读** + 无 conc 干预

### 中间件如何提示能翻转（用户笔记 2026-04-29）

| 维度 | 触发条件 | 干预语 |
|---|---|---|
| **trace/log 异常 + metric 全正常 → 查下游** ⭐ 新增 | 候选服务 trace status=Error 或 log SEVERE 非 0，但 container.cpu / restart / page_faults 全 < 2x | "你的候选服务 trace/log 看起来异常，但 container.cpu.usage / k8s.container.restarts / k8s.pod.memory.page_faults 都接近 normal —— 这说明候选自己没被资源压力击中，它的异常来自等待下游。**立即查它在 normal_traces 中的 direct callee 列表，并对每个 callee 查 metric**。" |
| **chronic check 发现后强制 dismiss** ⭐ | agent 的 think_tool 提到"X 的 ERROR 在 normal 也有" | "你刚发现 X 服务的 ERROR/SEVERE 在 normal 期也存在（normal=N, abnormal=M）。如果 normal/abnormal ratio < 2 或 normal 反而更多，**必须立即 dismiss X 作为 RC 候选，重新评估**。chronic check 不是看一眼就过，是必须改换 anchor。" |
| **trace Error count vs metric+restart 权重** | 多个候选都有 trace Error，但 metric+restart 只在一个上 | "trace status='Error' 数量在 cascade 中会累积到上游 victim（caller 等 callee 超时也会被标 Error）。**trace Error count 不能单独作为 RC 证据**。优先信号是 container.cpu 5x+ / restart 0→1 / page_faults 2x+ 这些只可能在 chaos target 出现的指标。" |
| **同 trace 否同因检查** | 多个候选服务都有 Error trace | "查多个候选的 Error trace 是否在同一批 trace_id 里。若 service A 的 Error trace 和 service B 的 Error trace **完全不重叠**，说明它们是两类独立问题（一个是 chaos target，另一个是 cascade victim 或 chronic）。重叠才说明是同一个 cascade。" |
| **callee 排除验证（commit 前必跑）** | 已锚定候选 RC | "commit 前必须查候选服务的 direct callee 的 metric。本 case：food-service 的 callee 是 station-food-service，station-food-service 有 container.cpu 29x + restart 0→1，说明 food-service 只是 messenger。" |

最有效组合：**trace/log 异常 + metric 全正常 → 查下游** + **全局 restart counter 扫描** —— 两条 SQL 直接定位 station-food-service。

### 中间件代码层面问题

- mid M6+M5 触发后 chronic check 实际做了（R199）但没强制 dismiss 动作 —— 卡片库需要"看到 chronic 必须切换 anchor"硬规则
- 80 round 中只触发 mid，无 conc —— 干预 throttling 太严
- M5 silent service 在本 case 是 trap（GT 不真 silent，trace 1117 行）
- agent 把 trace status='Error' 当作 RC 强证据但卡片库没解释 cascade Error 累积现象

### 判断

- 数据完整性：✅
- chaos 生效：✅ 必然生效
- 盲区类型：**(b) 框架盲区** —— chronic check 概念有但缺"强制 dismiss"动作；trace Error count fallacy 无 advisor 警告
- 给 v4.1：(1) "trace/log 异常 + metric 全正常 → 查下游"作为新 advisor 卡片；(2) 检测 think_tool 提到 chronic 后强制发 dismiss intervention；(3) trace status=Error 数量不允许作唯一 RC 证据；(4) 干预 throttling 放宽，每个 case 至少 mid+conc 各一次

---

## Case 1195 · `ts2-ts-order-other-service-stress-sv9xq6` · JVMMemoryStress (mem_type=1, heap)

| 字段 | 值 |
|---|---|
| GT | `ts-order-other-service` |
| theme / tier | T5_Query-Blindness / **ultra_hard** |
| baseline pred | `ts-security-service` ❌ (qpf=72) |
| v4 pred | `ts-security-service` ❌ (qpf=81) |
| 干预 | mid M6+M1 @ R30 / conc M8 @ R72 |
| transition | wrong→wrong |

### chaos 机制

JVM heap stress on `OrderOtherServiceImpl.getOrderById`（被 ts-security-service / ui-dashboard 调用获取订单详情）→ container.cpu 12.21x + restart 0→1 + hubble HTTP p95 43.13x。security-service 调 getOrderById 等超时 → 503。**chaos 必然生效**。

### 调用树

```
loadgen → ts-ui-dashboard (POST orderOther/refresh + 其他)
  ├─ ts-order-other-service (queryOrders / getOrderById)  ◀── GT
  └─ ts-security-service (orderCheck)
       ├─ ts-order-service (122/normal)
       └─ ts-order-other-service (122/normal)            ◀── GT (双源调用)
```

### 关键 duckdb 证据

#### GT (ts-order-other-service) 指纹

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| `hubble_http_request_duration_p95_seconds` | 0.0105 | 0.4528 | **43.13x** |
| `k8s.pod.cpu.usage` | 0.0929 | 1.3112 | **14.11x** |
| `container.cpu.usage` | 0.0932 | 1.1376 | **12.21x** |
| `k8s.pod.memory.page_faults` | 170,527 | 555,818 | 3.26x |
| `k8s.container.restarts` | 0 | **1** | trap→fire |
| service avg duration | 3.0 | 6.9 | 2.3x（仅排第 3） |

#### 误锚 ts-security-service（cascade upstream messenger）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| service avg duration | 10.3ms | 170.2ms | **16.6x** top1 |
| `hubble_http_request_duration_p50_seconds` | 0.0221 | 1.2757 | 57.78x |
| `hubble_http p90/p95/p99` | 0.x | **NaN** | timeout cap（同 case 156 模式） |
| `container.cpu.usage` | - | - | **~1x（无）** |
| `k8s.container.restarts` | 0 | 0 | 无 |
| log SEVERE 计数 | 0 | 12 | "503 upstream connect error" |

⭐ 同 case 784 模式：security-service trace/log 异常但 container.cpu / restart / page_faults 全正常 → 它在等下游。

#### 503 message provenance

```
"503 Service Unavailable: [upstream connect error ... Connection refused]"
```
security-service 是 messenger，"upstream" 是 ts-order-other-service。

#### 全局 restart counter 扫描

```
ts-order-other-service-* : restart 0→1  ⭐ chaos target
```

### baseline 推理（72 round → ts-security-service ❌）

锚 security-service 16.6x service avg + hubble p50 57x + 12 SEVERE 503 → commit。没查 callee 的 metric。

### v4 推理（81 round → ts-security-service ❌）

| Round | 行为 |
|---|---|
| R1-R29 | 锚 security-service 503 |
| R30 mid M6+M1 | agent_response 完整复述 |
| R31-R72 | ✅ baseline 对比 + chronic 排除（food-service rabbit）→ ❌ 加固 security-service |
| R139 | "security-service log 'upstream connect error' = security-service cannot connect to something" → 看到了 messenger 概念但没 act |
| R160 | "All deployments available=1.0, no pod down" → 没跑 restart counter |
| R220 | "ts-ui-dashboard doesn't appear in abnormal_logs at all" → 没意识到 ui-dashboard 也是 messenger |
| R229 timeline | "First security-service error 13:01:45 → confirms it's origin" | first-error fallacy |
| R232 FINAL #1 | ts-security-service |
| R72→R73 conc M8 | "503 without downstream vs 503 due to downstream - which?" |
| R255 | ✅ 看到："Traces with ONLY ui-dashboard errors (NO order-other-service spans)" → 接近真相 |
| R267 | 查 ui-dashboard metrics 正常 → 思考但没换 anchor |
| R270 FINAL #2 | ts-security-service ❌（**全程没查 security-service 的 callee metric**） |

**v4 干预实际效果**：
- mid M6+M1：✅ baseline 对比 + chronic 排除都做了 → ❌ 加固错锚
- conc M8：✅ 概念命中 + 真去看了 ui-dashboard metrics → ❌ **没去查 security-service 的 callee metric**

### 失败模式

- baseline：**503 message provenance 误读** + **loud victim 锚定** + **hubble p50 误读** + 没查 callee
- v4：**F2 confirmation bias**（mid 加固 + chronic 排除生效但 anchor 锁死）+ **direct callee drill 完全跳过** + **first-error timestamp fallacy**（13:01:45 锚 security-service）+ **conc M8 概念命中但行动缺位**

### 中间件如何提示能翻转（用户笔记 2026-04-29）

本 case 失败模式与之前 case 同根（messenger vs RC），所有关键维度已在前面 case 记录：

- ⭐ **trace/log 异常 + metric 全正常 → 查下游**（case 784）
- **direct callee drill**（case 156）
- **callee 排除验证（commit-gate）**（case 156）
- **503 message provenance**（case 99）
- **全局 restart counter 扫描**（case 33）
- **hubble 多分位 NaN 识别为 timeout cap**（case 156）

最有效组合：**callee 排除验证 + 全局 restart counter 扫描** —— 一次查 security-service 的两个 callee 的 metric，立即看到 order-other-service container.cpu 12x + restart 0→1 命中。

### 中间件代码层面问题

- mid M6+M1 触发后 baseline + chronic 都做了（42 round）但**没引导查 callee**
- conc M8 概念命中但**没强制 SQL 模板**，agent 复述后去查 ui-dashboard 而非 security-service 的 callee
- M1 secondary 选择不准 —— 应该用 M5 silent service（GT 在失败 trace 中 silent）
- 81 round 很长但方向不准 —— 干预次数足够，但缺"callee metric 强制 SQL"硬动作

### 判断

- 数据完整性：✅
- chaos 生效：✅ 必然生效
- 盲区类型：**(b) 框架盲区**（与 case 156/784 同根）
- 给 v4.1：(1) "trace/log 异常 + metric 全正常 → 查下游"卡片化为 mid 触发条件之一；(2) 503/connection refused log 检测 → 必发 callee metric drill SQL 模板；(3) ultra_hard tier mid 阶段强制查 restart counter；(4) M5 silent service 在 mid+M6 组合应 secondary 触发

---

## Case 1218 · `ts2-ts-order-service-stress-967z6d` · JVMMemoryStress (mem_type=1, heap, OrderInfo.enableBoughtDateQuery)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 1218 |
| GT 根因 | `ts-order-service` |
| theme | T4_Amplitude-Greed |
| tier | ultra_hard |
| baseline pred | `ts-seat-service` ❌ |
| v4 pred | `ts-seat-service` ❌（不变）|
| baseline qpf / v4 qpf | 57 / 60 |
| 干预 | mid M6+M5 (round 30) / conc M8+M3 (round 59) |
| transition | wrong → wrong |

### 2. GT 注入

```
fault_type: 28 = JVMMemoryStress
display_config:
  injection_point: ts-order-service / order.entity.OrderInfo / enableBoughtDateQuery
  mem_type: 1 (heap)
  duration: 4 min
ground_truth: container=ts-order-service, function=OrderInfo.enableBoughtDateQuery
```

`enableBoughtDateQuery` 是 `OrderInfo` entity 的 helper（看名字返回 boolean），trace 里完全没有此 span。chaosblade JVM agent attach + byte code 注入消耗 heap。

### 3. chaos 机制

heap stress 期望让 JVM heap 涨触发 GC/swap。但：
- 注入点是 entity 内部 helper，不在 trace hot path → 设计语义（method-level latency）无可观测信号
- byte code 注入本身的 CPU 副作用是主导信号：container.cpu 16.33x，cpu_limit_utilization 16.17x（接近打满）
- chaos blade attach 痕迹明显：container.filesystem.usage 466944 → 3080192（6.6x step jump at 15:35:08）
- 副作用足以引爆 OOM：filesystem 在 15:35:38 跌到 0 + restart counter 0→1
- 新 pod 启动期间不响应 → ts-seat-service 等上游全部报 503 Connection refused

### 4. 调用树（normal 期实测）

```
loadgenerator
  └─ ts-ui-dashboard
      ├─ ts-travel-plan-service
      │   └─ ts-route-plan-service
      │       └─ ts-travel-service
      │           └─ ts-seat-service          ← caller，47 SEVERE 报 503 Connection refused
      │               ├─ ts-config-service    ← callee
      │               ├─ ts-order-service     ◀── GT (chaos target，是 ts-seat-service 的 callee)
      │               └─ ts-order-other-service
      └─ POST /orderservice/order/refresh     ← 直接调 ts-order-service
```

ts-order-service 是 ts-seat-service 的 callee（normal 555 calls）。ts-seat-service 报 503 就是因为它调不到 GT。

### 5. 沿调用链从根因到 SLO

#### chaos 直接证据（GT = ts-order-service）

| metric | normal | abnormal | ratio |
|---|---|---|---|
| container.cpu.usage | 0.186 | 3.04 | **16.33x** |
| k8s.pod.cpu_limit_utilization | 0.05 | 0.80 | **16.17x** |
| jvm.cpu.recent_utilization | 0.0015 | 0.0154 | **10.09x** |
| k8s.pod.memory.page_faults | 162k | 593k | 3.65x |
| k8s.pod.memory.major_page_faults | 0 | 0.79 | NEW |
| **k8s.container.restarts** | 0 | 1 | **0→1**（OOM 触发 restart at 15:35:41）|
| memory.working_set | 8.0e8 | 7.59e8 | 0.95x（heap 没涨）|

时间线：
```
15:34:57  injection start
15:35:08  filesystem step jump 466944 → 3080192 (chaosblade attach)
15:35:33  attach 完成 byte code 在跑
15:35:37  ts-seat-service first 503 SEVERE
15:35:38  filesystem 跌到 0 (pod 被 OOM kill)
15:35:41  restart counter 0 → 1
```

GT 端点级（distribution，避免 service avg 被掩盖）：

| span_name | n_p50 | a_p50 | p50_ratio | a_max |
|---|---|---|---|---|
| OrderRepository.findByAccountIdAndTrainNumberAndTravelDate | 1.4ms | 20708ms | **14302x**（仅 1 次调用）| 20708ms |
| Transaction.commit | 1.1ms | 10.1ms | 9.2x（GC 压力征兆）| 121ms |
| OrderRepository.findById | 3.2ms | 46.3ms | 14.4x | 4383ms |
| Session.merge order.entity.Order | 0.4ms | 8.0ms | 18.1x | 70ms |
| OrderRepository.save | 2.4ms | 33.3ms | 13.6x | 142ms |
| SELECT ts.orders | 0.9ms | 2.1ms | 2.3x（hot path 反而轻微）| 20707ms |
| POST /api/v1/orderservice/order/refresh | 5.8ms | 2610ms | **453x** | 5168ms |

GT log 静默：normal 1163 INFO + 9 ERROR + 394 WARN → abnormal 105 INFO + 0 ERROR + 25 WARN（**-91% 量，0 SEVERE**）。

#### 上游 cascade victim（ts-seat-service，baseline/v4 anchor）

- specific metric 弱：jvm.system.cpu 1.61x，container 几乎不变
- 47 SEVERE log 全是 `503 Service Unavailable: upstream connect error... Connection refused`（normal 0 SEVERE）
- trace 362 spans 141 Error → 但都是因为 callee（GT）不响应而 propagate 上来的 5xx

#### SLO 末端

`loadgenerator HTTP POST /orderservice/order/refresh`: avg 52ms → 15884ms（307x），max 20004ms（loadgen 客户端 20s timeout 触顶），5/7 errors。

### 6. baseline 推理（57 round → ts-seat-service ❌）

| Round | 行为 | 关键决策 |
|---|---|---|
| R4-R8 | log scan | 47 SEVERE on ts-seat-service，503 Connection refused |
| R10 think | 双轨 | ts-seat-service + RabbitMQ ERROR |
| R37-R45 | 转 RabbitMQ DNS | 把 ts-notification/ts-delivery chronic ERROR 当 incident-onset |
| R42-R43 | 查 rabbitmq metric | rabbitmq 健康 → 排除 |
| R49 | trace error 排名 | ts-seat-service 141 errors / 362 spans 第一 → 加固 |
| 🔴 R55-R57 锚定 | first-error timestamp | dismiss RabbitMQ chronic 后，ts-seat-service 15:35:37 是"first new SEVERE" → RC |
| FINAL | commit | ts-seat-service ❌ |

**baseline 失败子模式**：
1. **503 message provenance 误读**：把 caller 报告 "Connection refused to upstream" 当 caller 是 RC
2. **trace error 排名锚定**：错率最高的是 cascade 中段服务
3. **chronic noise 排除后的 first-error fallacy**：first new SEVERE = ts-seat-service，但忽略 GT 在更早就开始静默
4. **没查 specific metric**：完全没查 container.cpu / jvm.cpu / restart counter
5. **没做 callee drill**：没沿 ts-seat-service → callee 反向查 latency
6. **silence-as-health**：GT log 量 -91% 且 0 SEVERE，agent 默认它健康

### 7. v4 推理（60 round → ts-seat-service ❌，干预 0 效果）

| Round | 行为 | 关键决策 |
|---|---|---|
| R1-R30 | 跟 baseline 几乎一样 | 已锚 ts-seat-service |
| 🚨 R30 mid M6+M5 | baseline + silent service | excerpt 显示立即做 baseline 对比 |
| R31-R34 | ✅ baseline 查询 | normal vs abnormal ERROR/SEVERE 对比 |
| R35 think | ✅ chronic dismiss | 排除 RabbitMQ。但 ts-seat-service 0 SEVERE in normal → 47 in abnormal **加固**而非松动 anchor |
| R36-R37 | 试图查调用关系 | 找到 ts-seat-service caller/callee |
| R53 | callee 列表 | ✅ ts-config-service(42), **ts-order-service(25)**, ts-order-other-service(14) |
| 🔴 R54 关键失误 | 看 callee status_code | 全 Unset → **silence-as-health 陷阱**：GT 端点慢但 status code 不标 Error，agent 当 callee 健康 |
| R56-R58 | timeline 加固 | dismiss chronic 后 ts-seat-service first-new-SEVERE → 加固 anchor |
| FINAL | commit | ts-seat-service ❌ |
| 🚨 R59 conc M8+M3 | counterfactual + causal direction | excerpt: 反向加固 |
| R60 think | counterfactual | "ts-seat-service callee → callers fail" → 反向加固，没问"如果我健康，自己为何报 503 connection refused" |
| FINAL 不变 | commit | ts-seat-service ❌ |

**v4 干预实际效果**：
- mid M6 baseline 对比 ✅ 跑了 → 但 ts-seat-service SEVERE 0→47 反向加固（没引导查 GT specific metric）
- mid M5 silent service ❌ 完全没生效（agent 不会主动跑"该出现但消失的服务"）
- conc M8 counterfactual ❌ 反向加固（callee 关系当成"我是 root，所以 caller 失败"）
- conc M3 causal direction ❌ 引用 parent_span_id 关系反而强化"ts-seat-service 是 leaf cause"的错觉

### 8. 失败模式诊断

| 失败链 | baseline | v4 |
|---|---|---|
| 锚点切换 | 一直锚 ts-seat-service（中途短暂转 RabbitMQ 又回） | 一直锚 ts-seat-service（mid 干预没动） |
| baseline 对比 | ❌ 没查 normal | ✅ 查了 → 反向加固 |
| chronic 排除 | ⚠️ 排除 RabbitMQ 但靠"timestamp 早" | ✅ 排除 RabbitMQ + ts-seat-service 0→47 加固 |
| specific metric (GT) | ❌ 没查 | ❌ 没查 |
| callee drill | ❌ 没查 | ⚠️ 查了 callee 列表但只看 status_code（全 Unset）→ silence-as-health |
| callee latency drill | ❌ 没查 | ❌ 没查（ts-order-service 端点 11867x 没看到） |
| restart counter 全局扫描 | ❌ 没查 | ❌ 没查 |
| counterfactual 双向 | ❌ 没做 | ❌ 单向加固（没反问 503 message provenance） |

**主要失败模式**：
- **F2 advisor 维度对但 reasoning 不动**（confirmation bias）：mid baseline 对比 ✅，但 anchor 不变
- **F5 conc 干预反向加固**：counterfactual 单向推理加固 ts-seat-service
- baseline 子模式：**503 message provenance 误读** + **trace Error 比例第一锚定** + **silence-as-health**（GT log -91%）+ **first-error timestamp fallacy**

### 9. 中间件如何提示能翻转

| 维度 | 触发条件 | 干预语 |
|---|---|---|
| **callee latency drill (强制)** | log SEVERE 含 "503/connection refused/upstream" | "your anchor is reporting upstream connection failure — drill into ITS callees' span-level p95 duration, not status_code (Unset ≠ healthy when latency is 20+ seconds)" |
| **specific metric 强制** | trace error 集中但 specific metric 未查 | "for any candidate, query container.cpu.usage + jvm.cpu.recent_utilization + page_faults — JVM stress chaos shows 5-20x ratios in these even when restart=0 and logs are silent" |
| **silence-as-health 反例** | candidate log 在 abnormal 大幅减少（-50% 以上）| "log volume dropped 91% on a candidate that's a callee — silence here means it can't respond, not that it's healthy" |
| **counterfactual 双向** | conc 阶段 anchor 是 caller-position（有 503 SEVERE）| "your candidate reports 'Connection refused to upstream X' — counterfactual: if it were healthy, would it still report Connection refused? No → look at X" |
| **restart counter 全局扫描** | ultra_hard tier mid 阶段 | 强制 SQL 模板：所有 pod 的 restart counter abnormal vs normal max 对比 |

最有效组合：**callee latency drill + specific metric 强制 + silence-as-health 反例** —— 三联会迫使 agent 跑 ts-order-service 端点级 duration（11867x）+ container.cpu（16x），翻盘到 GT。

### 10. 判断

- 数据完整性：✅ 完整
- chaos 生效：⚠️ 物理生效（attach 痕迹 + OOM restart + cpu 16x），但设计语义（method-level heap pressure）跟实际生效路径（byte code injection CPU 副作用为主）不一致
- 盲区类型：**(b) 框架盲区**（与 case 99/156/784/1195 同根，503 message provenance + silence-as-health 二联陷阱）
- 失败模式：F2（mid 维度对但 anchor 不动）+ F5（conc 反向加固）+ baseline 子模式 503 fallacy + first-error fallacy + silence-as-health
- 给 v4.1：(1) 503/connection refused log 检测 → 强制 callee 端点级 latency drill（不能只看 status_code）；(2) silence-as-health 反例：candidate log -50%+ 应作为 silent 信号；(3) specific metric 强制 SQL 模板（anchor + 1-跳 callees 一次性查 cpu/restart/page_faults）；(4) conc counterfactual 必须双向（"如果健康，503 怎么解释"）
- **GT 标注偏差**：causal_graph container 节点 state=`high_memory` 实测主导是 `high_cpu`（cpu 16.33x vs memory 1.10x，差一个数量级；mem_type=1 期望让 heap 涨但注入点是 entity helper 非 hot path，byte code 注入 CPU 副作用主导）；pod 节点 state 含 `healthy` 跟实测 restart 0→1 矛盾。service-level GT 仍正确，failure mode 分析不受影响

case 1218 完毕。

---

## Case 1459 · `ts2-ts-train-service-stress-qv9rrc` · JVMMemoryStress (mem_type=1, InitData.run)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| GT | `ts-train-service` |
| theme / tier | T2_Blame-the-Messenger / ultra_hard |
| baseline pred | `ts-basic-service` ❌ (qpf=33) |
| v4 pred | `ts-basic-service` ❌ (qpf=43, **conc 反向加固加深错觉**) |
| 干预 | mid M6+M5 @ R30 / conc M8 @ R37 |
| transition | wrong → wrong |

### 2. GT 注入

```
fault_type: 28 = JVMMemoryStress
display_config:
  app_name: ts-train-service
  injection_point: train.init.InitData.run
  mem_type: 1  # heap memory
ground_truth.service: [ts-train-service]
ground_truth.pod: [ts-train-service-7b65db49f4-h2pwx]
```

### 3. chaos 机制

`InitData.run` 是 init 方法。chaos 物理时间线（duckdb 直查 container.filesystem.usage）：
- 04:33:32 baseline filesystem 466944
- 04:33:37 step jump → 3080192（chaosblade JVM agent attach）
- 04:33:52 跌到 0（OOM kill）→ 04:33:57 起重建（restart counter 0→1）

byte code 注入副作用主导：container.cpu 20.39x（chaos 必然生效，仅副作用而非设计语义；端点级 distribution 中位数 1.1-1.6x 弱，avg 被 OOM 窗口 outlier 拉到 22-63x）。

### 4. 调用树（normal 期实测）

```
loadgen → ts-ui-dashboard
  ├─ ts-travel-plan-service (cheapest/quickest/minStation)
  │   └─ ts-route-plan-service
  │       └─ ts-travel-service (queryInfo)
  │           └─ ts-basic-service (queryForTravels)  ← caller，322 SEVERE 报 503
  │               ├─ ts-station-service (567/normal)
  │               ├─ ts-train-service (397/normal)   ◀── GT (chaos target，是 ts-basic-service 的 callee)
  │               └─ ts-route-service (397/normal)
  └─ POST /trainservice/trains  ← 直接调 GT
```

duckdb 验证：normal 中 ts-basic-service 调 ts-train-service 397 calls，是 GT 的主要 caller。

### 5. 关键 duckdb 证据

#### GT (ts-train-service) 指纹

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| **container.cpu.usage** | 0.119 | 2.42 | **20.39x** ⭐ |
| **k8s.pod.cpu_limit_utilization** | 0.023 | 0.51 | **22.07x** ⭐ |
| jvm.cpu.recent_utilization | 0.001 | 0.013 | 13.16x |
| jvm.system.cpu.load_1m | 12.4 | 80.8 | 6.52x |
| k8s.pod.memory.page_faults | 158k | 535k | 3.38x |
| **k8s.container.restarts (pod-level)** | 0 | 1 | **0→1** trap→fire |
| memory.working_set | 7.6e8 | 6.75e8 | 0.89x（反而下降）|
| trace count | 3662 | 1410 | 0.39x |
| **service avg duration** | 3.8 | 126.1 | **33.0x ⭐ top1** |
| **log INFO 量** | 708 | 315 | -55%（silence）|
| log SEVERE | 0 | 0 | silent on errors |

GT 端点 distribution（avg vs p50 分裂——OOM 窗口 outlier 拉飞 avg）：

| span_name | avg_ratio | p50_ratio | p95_ratio | a_max |
|---|---|---|---|---|
| TrainTypeRepository.findByName | 63.4x | 1.6x | 5.1x | 9390ms |
| GET /trainservice/trains | 42.1x | 1.6x | 41.4x | 12601ms |
| POST /trainservice/trains/byNames | 22.9x | 1.5x | 1.9x | 15537ms |
| TrainController.retrieveByName | 41.7x | 1.4x | 2.8x | 12231ms |

#### 误锚 ts-basic-service（cascade caller）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| service avg duration | 77.8 | 353.8 | 4.6x |
| trace error count | 0 | 966 | top1 |
| **log SEVERE** | 0 | **322** | incident-only "503 Connection refused" |
| container.cpu | - | - | 1x（无） |
| restart counter | 0 | 0 | 无 |

⭐ 跟 case 99/156/784/1195/1218 同模式：caller (basic-service) trace/log 异常但 specific metric 全正常 → 它在等 callee。

#### 503 message provenance

```
ts-basic-service SEVERE × 322:
"503 Service Unavailable: [upstream connect error or disconnect/reset before headers...
 transport failure reason: delayed connect error: Connection refused]"
```
"upstream" 是 ts-train-service / ts-route-service / ts-station-service 等 callee。GT 在其中。

#### 全局 restart counter 扫描

```
ts-train-service-7fd4bc4b9b-kzg8b : restart 0→1  ⭐ chaos target
（其他 pod 全 0）
```

### 6. baseline 推理（33 round → ts-basic-service ❌）

| Round | 行为 |
|---|---|
| R3-R5 | log scan → ts-basic-service 322 SEVERE 503 → 锚定（503 message provenance 误读）|
| R7-R8 | trace error 排名 ts-basic-service 966 第一 → 加固 |
| R10 think | trace 调用链 loadgen → ui → travel-plan → travel → basic，把 ts-basic-service 当 leaf cause（实际它还有下游 ts-train-service 等）|
| R11-R13 | 查 ts-basic-service metric（avg/max value）但没找到 cpu/restart 异常 → 没去查 callee |
| R32 think | final commit ts-basic-service ❌ |

baseline 失败子模式：503 message provenance 误读 + trace error 排名锚定 + cascade leaf 误判 + 没查 callee specific metric + silence-as-health（GT log -55%）

### 7. v4 推理（43 round → ts-basic-service ❌，**conc 反向加固加深错觉**）

| Round | 行为 |
|---|---|
| R1-R30 | 跟 baseline 类似，锚 ts-basic-service（503 + 966 errors）|
| R23 | 看 timeline → ts-train-service 04:36 才有 6 个 ERROR "Train already exists"（实际是 OOM 重启后 InitData 重新跑导致），但当 chronic noise 忽略 |
| 🚨 R30 mid M6+M5 | baseline + silent service，excerpt 立即做 baseline 对比 |
| R31-R36 | ✅ baseline 对比执行 → normal 0 errors → abnormal 966 errors → **加固** ts-basic-service |
| R37 think final | "Root cause: ts-basic-service. Baseline: 0→966 errors..." ❌ |
| 🚨 R37 conc M8 | counterfactual，excerpt 空但 agent 之后跑了 ts-train-service status check |
| R38-R42 | 查 ts-train-service trace status_code → 1410 spans **all Unset (0 errors)** → **silence-as-health 陷阱**（OpenTelemetry 默认 Unset 不算 Error，agent 当成"健康"）|
| 🔴 R43 反向加固 | counterfactual think: "ts-train-service is healthy (0 errors), ts-basic-service generates the 503 itself when its **internal calls fail (connection pool exhaustion, resource issues, or intermittent network problems)**" ❌❌ |
| FINAL | ts-basic-service ❌（v4 比 baseline **更确信**） |

v4 干预实际效果：
- mid M6 baseline 对比 ✅ 跑了 → 反向加固（同 case 1218 模式）
- mid M5 silent service ❌ 完全没生效
- conc M8 counterfactual ❌❌ **比 1218 更糟糕**：agent 显式查了 callee status_code（Unset）当 healthy → 反推 caller 自我归因（connection pool 耗尽）。silence-as-health + 自我归因双重陷阱

### 8. 失败模式

| 失败链 | baseline | v4 |
|---|---|---|
| 503 message provenance | ❌ | ❌ |
| direct callee drill (specific metric) | ❌ | ⚠️ 查了 callee status_code 但当 Unset=healthy |
| 全局 restart counter | ❌ | ❌ |
| trace/log 异常 + metric 正常 → 查下游 | ❌ | ❌ |
| silence-as-health | ❌ | ❌（且 conc 后强化）|

主要失败模式：
- baseline：**503 message provenance 误读** + cascade caller 锚定 + cascade leaf 误判 + 没查 callee + silence-as-health
- v4：**F2 confirmation bias**（mid baseline 反向加固） + **F5 conc 反向加固加深错觉**（counterfactual + callee status_code = Unset 当 healthy → 反推 caller 自我归因）

### 9. 中间件如何提示能翻转

跟 case 99/156/784/1195/1218 同根 messenger vs RC 模式，关键维度：
- ⭐ trace/log 异常 + metric 全正常 → 查下游（case 784 已记）
- direct callee drill（case 156 已记）
- callee 排除验证（commit-gate）（case 156 已记）
- 503 message provenance（case 99 已记）
- 全局 restart counter 扫描（case 33 已记）
- silence-as-health 反例（GT log -55% 信号）
- **新维度（case 1459 暴露）：callee status_code Unset ≠ healthy** —— 必须查 callee 的 latency p95/p99 + restart counter + container.cpu，不能看 status_code

最有效组合：**callee specific metric drill 强制 SQL 模板** + **conc counterfactual 双向校验**——一次查 ts-basic-service 三个 callee（ts-train/route/station-service）的 cpu/restart，立即看到 ts-train-service 命中。

### 10. 中间件代码层面问题

- mid M6+M5 触发后 baseline 对比 + chronic 排除都做了（执行 7 round），但**没引导查 callee specific metric**——卡片库缺少"503 + container.cpu 正常 = caller 在等 callee"硬规则
- conc M8 文本"503 是自身产生 vs 503 因下游失败"概念命中但**没强制 SQL 模板**（如查每个 callee 的 cpu/restart/page_faults） → agent 复述完去查了 ts-train-service 的 status_code（Unset 当 healthy）但没查 specific metric → **F5 反向加固加深错觉**
- M5 silent service 在 mid 没生效——GT log -55% 量+0 SEVERE 是典型 silent 信号，但 advisor 没引导 agent 跑"normal 父子关系找该出现但没出现的服务"
- 43 round 干预次数足够但 **conc 阶段成了反向加速器**——需要"反例是否完全 fit"的二次校验机制，否则 counterfactual 是把双刃剑

### 11. 判断

- 数据完整性：✅
- chaos 生效：⚠️ 物理生效（attach + OOM restart + cpu 20x），但设计语义（init 方法 method-level latency）跟实际生效路径（byte code injection CPU 副作用）不一致
- 盲区类型：**(b) 框架盲区**（与 case 99/156/784/1195/1218 同根，503 message provenance + silence-as-health + callee Unset 误读三联陷阱）
- 失败模式：F2（mid 维度对但 anchor 不动，反向加固）+ **F5 加深错觉版**（conc 反向加固反推 caller 自我归因）+ baseline 子模式 503 fallacy + silence-as-health + cascade caller 锚定
- 给 v4.1：(1) 503/Connection refused log → 强制 callee specific metric drill SQL 模板（不能只看 status_code）；(2) callee status_code = Unset 必须配合 latency p95/p99 + restart 验证；(3) **F5 conc 反向加固特别危险**——conc 阶段需要"反例是否完全 fit"二次校验机制；(4) silence-as-health 反例：candidate log -50%+ → silent 信号

### 12. causal_graph 正确性检验

⚠️ **GT 标注偏差**（service-level GT 仍正确）：
- L1 `container|ts-train-service` state=`high_memory` 错标——实测主导是 `high_cpu`（cpu 20.39x vs memory 0.89x，差两个数量级；mem_type=1 期望 heap stress 但 init 方法注入只触发 byte code CPU 副作用 + OOM trap）
- L2 `pod|ts-train-service-7fd4bc4b9b-kzg8b` state=`[high_cpu, high_gc_pressure, high_http_latency, healthy]`——`healthy` 跟实测 restart 0→1 矛盾；其他三项跟实测一致
- L4 ts-train-service span 状态 `high_avg_latency` 成立（avg ratio 22-63x），但 distribution p50_ratio 仅 1.1-1.6x（中位数轻微）—— OOM 窗口 outlier 拉飞 avg
- L5-7 cascade ts-basic-service / ui-dashboard / loadgen 节点 state（high_avg_latency / high_p99_latency / high_error_rate / timeout）跟实测一致
- 整体跟 case 1218 同模式（init/helper 方法 JVMMemoryStress → cpu 副作用主导 + memory 弱 + OOM trap），不影响 failure mode 分析

case 1459 完毕。

---

## Case 1495 · `ts2-ts-travel-plan-service-stress-ph59w4` · JVMMemoryStress (mem_type=1, TravelPlanController.home)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| GT | `ts-travel-plan-service` |
| theme / tier | T2_Blame-the-Messenger / stable |
| baseline pred | `ts-seat-service` ❌ (qpf=63) |
| v4 pred | `ts-seat-service` ❌ (qpf=82, **conc 反向加固**) |
| 干预 | mid M6+M5 @ R30 / conc M8+M5 @ R62 |
| transition | wrong → wrong |

### 2. GT 注入

```
fault_type: 28 = JVMMemoryStress
display_config:
  app_name: ts-travel-plan-service
  injection_point: travelplan.controller.TravelPlanController.home
  mem_type: 1  # heap memory
ground_truth.service: [ts-travel-plan-service]
ground_truth.pod: [ts-travel-plan-service-5b7bdc7c56-t7hjp]
```

### 3. chaos 机制

`TravelPlanController.home` 是 controller 入口方法（典型 GET / 健康检查路径，不在业务热路径）。chaos 物理时间线（duckdb 直查 container.filesystem.usage）：
- 05:46:03 baseline filesystem 466944
- 05:46:08 step jump → 3080192（chaosblade JVM agent attach）
- 05:46:23 跌到 0（OOM kill）→ 05:46:26 restart counter 0→1（新 pod 起来）

byte code 注入副作用：container.cpu 8.31x（比 case 1218 16x、1459 20x 弱，因为 home 方法调用更稀疏）；端点级 distribution p50_ratio 仅 0.9-2.1x（很弱），avg_ratio 也只 1.4-2.2x，但 max 触顶 3500-3970ms（OOM 重启窗口的请求被卡）。chaos 必然生效但端点级表现弱。

### 4. 调用树（normal 期实测）

```
loadgen → ts-ui-dashboard
  └─ ts-travel-plan-service (TravelPlanController.getByCheapest/quickest/minStation)  ◀── GT
       ├─ ts-seat-service (850/normal)             ← callee
       ├─ ts-train-service (425/normal)            ← callee
       └─ ts-route-plan-service (187/normal)       ← callee
```

duckdb 验证：normal 中 ts-travel-plan-service 调 ts-seat-service 850 calls。ts-seat-service 是 GT 的主要 callee。**注意调用方向反转**——这次 baseline 锚的不是 GT 的 caller（messenger 模式），而是 GT 的 callee（cascade 下游）。

### 5. 关键 duckdb 证据

#### GT (ts-travel-plan-service) 指纹

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| **container.cpu.usage** | 0.074 | 0.615 | **8.31x** ⭐ |
| **k8s.pod.cpu_limit_utilization** | 0.016 | 0.135 | **8.60x** ⭐ |
| k8s.pod.cpu.usage | 0.078 | 0.672 | 8.60x |
| k8s.pod.memory.page_faults | 141k | 532k | 3.76x |
| jvm.system.cpu.utilization | 0.07 | 0.15 | 2.18x |
| **k8s.container.restarts (pod-level)** | 0 | 1 | **0→1** trap→fire at 05:46:26 |
| memory.working_set | 7.21e8 | 8.25e8 | 1.14x（弱）|
| service avg duration | 146.5 | 264.7 | 1.8x（弱，全集群 1.7-2.2x 范围）|
| **trace status_code (abnormal)** | - | **all 1140 spans Unset** | **0 errors** |
| log SEVERE | 0 | 0 | silent on errors |

GT 端点 distribution（distribution 中位数几乎不变，仅 OOM 窗口 outlier）：

| span_name | n_p50 | a_p50 | p50_r | p95_r | a_max |
|---|---|---|---|---|---|
| TravelPlanController.getByCheapest | 456ms | 953ms | 2.1x | 3.1x | 2925ms |
| getByMinStation | 442ms | 425ms | **1.0x** | 3.3x | 3977ms |
| getByQuickest | 468ms | 428ms | **0.9x** | 2.7x | 3557ms |

#### 误锚 ts-seat-service（GT 的 callee）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| service avg duration | 15.6 | 28.3 | 1.8x（普通）|
| **trace error count** | 0 | **1** | **唯一一个 Error span** |
| **log SEVERE** | 0 | **0** | 没有 503 |
| jvm.system.cpu.load_1m | 7.6 | 82.1 | 10.84x（cascade 也压力大）|
| container.cpu | - | - | 1.65x（弱）|
| restart counter | 0 | 0 | 无 |
| trace span 总数 | 11887 | 6838 | 0.58x |

**关键**：ts-seat-service abnormal 期 6838 个 trace span 中**只有 1 个 Error**（错率 0.015%），那是 `SeatController.getLeftTicketOfInterval`，duration 180ms。这是 cascade artifact（OOM 窗口里偶发 timeout）。

#### 全局 SEVERE 分布

```
ts-food-service    ERROR  166  (chronic, normal=281)
ts-preserve-service ERROR  70  (chronic, normal=122)
ts-order-service   ERROR  70  (chronic, normal=122)
ts-notification    ERROR  48  (chronic)
ts-delivery        ERROR  48  (chronic)
ts-ui-dashboard    ERROR  18  (incident-only) ← 真信号但 ui-dashboard 是 root
```

整个 abnormal 期**没有 503 / Connection refused log**——跟 case 1218/1459 的"503 message provenance"模式不同。

#### 全局 restart counter 扫描

```
ts-voucher-service-cddcc88c5-gl25h          : restart 4 (chronic)
ts-ticket-office-service-6bf44d54b7-sdqd5   : restart 3 (chronic)
ts-travel-plan-service-69865d84f8-cx9vj     : restart 0→1  ⭐ chaos target (incident-onset)
```

只有 GT pod 有 incident-onset restart。

### 6. baseline 推理（63 round → ts-seat-service ❌）

| Round | 行为 |
|---|---|
| R3-R8 | log scan，看到 ui-dashboard 18 ERROR with 503 status for travelplan endpoints → 知道 SLO 违反在哪 |
| R9-R11 | 选定 trace `554ff68a8511a393c365cf2943ecc960`（其中一个 503 trace）作为研究样本 |
| R12-R20 | 在该 trace 中找 Error span → ts-seat-service 1 个 Error span（SeatController.getLeftTicketOfInterval, 180ms） |
| R21-R30 | 查 ts-seat-service trace + log → 没 ERROR/SEVERE → 但有"唯一的 Error span" |
| R30 think | 锚定 ts-seat-service：**"the only downstream service with Error status spans"** |
| R31-R55 | 反复确认 ts-seat-service 是 unique Error → 加固 |
| R55-R63 final | commit ts-seat-service ❌ |

**baseline 失败子模式**：
1. **Error span 唯一性陷阱**（max-only fallacy 反例）：6838 spans 中 1 个 Error 当 RC，错率 0.015% 也算"unique signal"
2. **status_code Unset 当 healthy**：ts-travel-plan-service 1140 spans 全 Unset → 当成 healthy（实际是 chaos byte code 让 cpu 烧但 controller 仍 graceful 响应，端点级 distribution 中位数不变只是 max 触顶）
3. **没查 specific metric**：完全没查 ts-travel-plan-service 的 container.cpu / restart / page_faults
4. **没查 GT pod restart 时间线**：错过 0→1 这个铁证
5. **trace error 排名 fallacy**：以为 trace error 只要不为 0 就是 RC，没考虑错率分母

### 7. v4 推理（82 round → ts-seat-service ❌，conc 反向加固）

| Round | 行为 |
|---|---|
| R1-R30 | 跟 baseline 一样：trace error 排名 → ts-seat-service 1 个 Error 唯一 → 锚定 |
| 🚨 R30 mid M6+M5 | baseline + silent service，excerpt 空 |
| R31-R55 | ✅ baseline 对比执行 → "ui-dashboard 0→18 errors, ts-seat-service 0→1 error, ts-travel-plan-service 0→0 errors all Unset" → **加固** ts-seat-service（"only downstream with new error"）|
| R55 think 关键 | "ts-seat-service has ONE span with Error... this is the only downstream service with Error spans" → 锁定 |
| R56-R62 | 试图查 seat-service metric（cpu / memory）→ 没找到异常（实际它本来就没问题） |
| R62 final commit #1 | ts-seat-service ❌ |
| 🚨 R62 conc M8+M5 | counterfactual + silent service |
| R63 think 反向加固 | excerpt: "Counterfactual: If ts-seat-service healthy, would 503s occur? ts-seat-service is the ONLY downstream with Error → if healthy, all upstream complete successfully" ❌❌ |
| R64-R81 | 反复查 trace call chain（试图理解 ts-route-plan-service / ts-travel-plan-service 关系）但**没去查 ts-travel-plan-service 的 specific metric** |
| R82 final commit #2 | ts-seat-service ❌（不变）|

**v4 干预实际效果**：
- mid M6 baseline 对比 ✅ 跑了 → 反向加固（同 case 1459 模式）
- mid M5 silent service ❌ 没生效（agent 不主动找"该出现但消失"，反而把 ts-travel-plan-service 的 status_code Unset 当 healthy）
- conc M8 counterfactual ❌ 反向加固（"only downstream with Error" → "if healthy, no 503"）
- conc M5 secondary silent service ❌ 也没生效——agent 看 trace call chain 看了半天但没去 metric 维度查 GT

### 8. 失败模式

| 失败链 | baseline | v4 |
|---|---|---|
| 503 message provenance | N/A（本案没 503 log） | N/A |
| Error span 唯一性陷阱 | ❌ 1 个 Error 当 RC | ❌ 同 |
| status_code Unset = healthy | ❌ 没查 GT specific metric | ❌ conc 后强化（"all Unset = healthy"） |
| direct callee/upstream drill (specific metric) | ❌ 没查 GT cpu/restart | ❌ 没查 |
| 全局 restart counter 扫描 | ❌ | ❌ |
| trace silence gap 检测 | ❌ | ❌ |
| counterfactual 双向 | ❌ | ❌ 单向加固 |

主要失败模式：
- baseline：**Error span 唯一性陷阱**（max-only fallacy 反例，1/6838 当 RC） + **status_code Unset 当 healthy**（GT 1140 spans all Unset 判 healthy）+ **没查 specific metric**
- v4：**F2 confirmation bias**（mid baseline 对比反向加固） + **F5 conc 反向加固**（counterfactual 锁死"unique Error = origin"逻辑）+ silence-as-health（GT trace 全 Unset 当 healthy）

跟 case 1459 关键区别：1459 是"503 + caller 锚定"模式，1495 是"trace error 唯一性 + callee 锚定"模式。但底层机制都是 **status_code Unset = healthy 陷阱 + 没查 specific metric**。

### 9. 中间件如何提示能翻转

需要的 advisor 维度（部分跟 1459 重复 + 1495 暴露的新维度）：
- **trace status_code Unset ≠ healthy 反例**（case 1459 已记，1495 加强：被锚服务 1/6838 错率也能误锚为 RC，必须配合 specific metric 验证）
- **Error span 唯一性反例**（case 1495 新维度）：1 个 Error span / 6000+ 总 spans 错率 0.015% 不能当 RC，必须看错率分母
- **specific metric 强制 SQL 模板**（case 33 已记）：anchor 服务和 candidate 服务都查 container.cpu / cpu_limit_utilization / page_faults / restart counter
- **全局 restart counter 扫描**（case 33 已记）：incident-onset restart 是最可靠的 GT 指纹之一
- **chaos 时间线对齐**（case 1495 新维度）：把 incident start time 跟 restart counter 跳变时刻对齐——本案 GT pod restart at 05:46:26，跟 incident_start (05:46) 完全吻合

最有效组合：**全局 restart counter 扫描 + specific metric 强制 SQL 模板** —— 一条查询 `MAX(value) FROM abnormal_metrics WHERE metric='k8s.container.restarts' AND value > 0 GROUP BY pod` 立即看到 ts-travel-plan-service-...-cx9vj restart 0→1，跟 incident 时间线对齐 → 直接命中 GT。

### 10. 中间件代码层面问题

- mid M6+M5 触发后 baseline 对比执行了 32 round 但**没引导查 specific metric**——卡片库缺少"trace error rate 极低（<1%）但仍当 RC = max-only fallacy"硬规则
- mid M5 silent service **完全没生效**——advisor 文本说 "absence of evidence isn't evidence of absence" 但没给 SQL 模板（"跑 normal_traces 父子关系找该出现但消失的服务"）
- conc M8 counterfactual 文本"only service showing a signal ≠ confirmed origin"概念命中，但 agent 复述完仍走"unique Error = origin"逻辑——advisor 缺少**"unique Error span 在低错率分母下不能当 RC"硬规则**
- conc M5 secondary silent service **跟 mid M5 一样没生效** —— v4 在 mid 和 conc 两次重复 M5 没用，说明 silent service 维度需要 SQL 模板而非概念提醒
- 82 round 干预次数足够但全程**没查 GT specific metric**——v4 advisor 缺少"任何 RC 候选都必须查 container.cpu / restart"硬规则

### 11. 判断

- 数据完整性：✅
- chaos 生效：⚠️ 物理生效（attach + OOM restart + cpu 8.31x），但设计语义（home controller method-level latency）跟实际生效路径（byte code injection CPU 副作用）不一致；端点级 p50 ratio 仅 0.9-2.1x（弱，被 OOM outlier 拉到 max 3-4s）
- 盲区类型：**(b) 框架盲区**（status_code Unset = healthy + Error span 唯一性陷阱 + 没查 specific metric 三联）
- 失败模式：**F2 confirmation bias**（mid baseline 反向加固） + **F5 conc 反向加固**（counterfactual 锁死"unique Error"逻辑）+ baseline 子模式 Error 唯一性陷阱 + silence-as-health（trace all Unset）
- 给 v4.1：(1) 任何"unique Error span"候选必须配合错率分母检查（< 1% 不能当 RC）；(2) **status_code Unset 强制不当 healthy**——必须查 candidate / anchor / 1-跳关联服务的 specific metric（cpu/restart/page_faults）；(3) **全局 restart counter 扫描**作为 mid 阶段强制查询模板（incident-onset restart 是最强 GT 指纹）；(4) chaos 时间线对齐——把 incident_start 跟 restart 跳变时刻对齐查询

### 12. causal_graph 正确性检验

⚠️ **GT 标注偏差**（service-level GT 仍正确）：
- L1 `container|ts-travel-plan-service` state=`[high_cpu, restarting, high_memory]`——`high_cpu` ✅（cpu 8.31x），`restarting` ✅（restart 0→1），`high_memory` ⚠️ 弱标（memory.working_set 1.14x，比 cpu 弱很多但比 case 1218/1459 的 memory 0.89-0.95x 略好）。比 1218/1459 标注准确度高（多了 `restarting`），但仍把 `high_memory` 列在主导信号里
- L2 `pod|ts-travel-plan-service-69865d84f8-cx9vj` state=`[high_cpu, high_gc_pressure, high_memory, healthy]`——`healthy` 跟实测 restart 0→1 矛盾（`healthy` + `high_cpu` + restart 0→1 同时存在是图模型多时刻合并产物，但仍是误导）
- L4 GT span 状态 `high_avg_latency`/`high_p99_latency` —— p50_ratio 仅 0.9-2.1x（中位数几乎不变）但 max 3-4s（outlier 拉飞），属于"max-driven 高分位标签"，distribution 角度看 high_avg_latency 弱标
- L5-7 cascade ts-ui-dashboard / loadgenerator 节点 `high_avg_latency` / `high_p99_latency` / `high_error_rate` / `timeout` 跟实测一致（ui-dashboard 18 errors / loadgen max 20s）
- 整体跟 case 1218/1459 同模式（init/controller helper 方法 JVMMemoryStress → cpu 副作用主导 + memory 弱 + OOM trap），不影响 failure mode 分析

case 1495 完毕。

---

## Case 1814 · `ts3-ts-basic-service-stress-p545b4` · JVMMemoryStress (mem_type=1, BasicController.queryForStationId)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| GT | `ts-basic-service` |
| theme / tier | T2_Blame-the-Messenger / stable |
| baseline pred | `ts-travel-service` ❌ (qpf=52) |
| v4 pred | `ts-travel-service` ❌ (qpf=77, **conc 命中真相后被 silence-as-health 反向加固**) |
| 干预 | mid M6+M5 @ R30 / conc M8+M5 @ R59 |
| transition | wrong → wrong |

### 2. GT 注入

```
fault_type: 28 = JVMMemoryStress
display_config:
  app_name: ts-basic-service
  injection_point: fdse.microservice.controller.BasicController.queryForStationId
  mem_type: 1  # heap memory
ground_truth.service: [ts-basic-service]
ground_truth.pod: [ts-basic-service-68f7cbd746-t686h]
start: 2025-08-10T16:34:54Z
```

`queryForStationId` 是 hot-path 业务方法（每次 travel/preserve 流程都会查），不是 init/helper。chaos 设计语义在这里**真生效**（不是单纯 byte code 注入副作用）。

### 3. chaos 机制

GT pod restart 0→1 + 端点级真变慢（不是仅 OOM 窗口 outlier）。chaosblade attach 物理时间线类似 1218/1459/1495，但因为 queryForStationId 是 hot path：
- container.cpu 3.52x（比 1218/1459/1495 弱因为方法 latency 主导而非 byte code 副作用主导）
- service avg ratio 2.0x（普通范围内，因为 chaos 让 latency 中度增加，没让端点完全卡死）

### 4. 调用树（normal 期实测）

```
loadgen → ts-ui-dashboard
  ├─ ts-preserve-service (preserve)
  │   └─ ts-travel-service (trip_detail)        ← caller，26 SEVERE 报 503
  │       └─ ts-basic-service (queryForTravels) ◀── GT (chaos target，是 ts-travel-service 的 callee)
  │            ├─ ts-station-service (1534/normal)
  │            ├─ ts-route-service (1071/normal)
  │            ├─ ts-train-service (1071/normal)
  │            └─ ts-price-service (845/normal)
```

duckdb 验证：normal 中 ts-travel-service 调 ts-basic-service 550 calls，ts-basic-service 是 GT 的主要 caller (along with ts-travel2-service 377)。

### 5. 关键 duckdb 证据

#### GT (ts-basic-service) 指纹

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| **container.cpu.usage** | 0.205 | 0.722 | **3.52x** |
| **k8s.pod.cpu_limit_utilization** | 0.041 | 0.165 | **4.01x** |
| jvm.system.cpu.load_1m | 17.7 | 48.9 | 2.76x |
| k8s.pod.memory.page_faults | 173k | 579k | 3.35x |
| **k8s.container.restarts (pod-level)** | 0 | 1 | **0→1** trap→fire |
| service avg duration | 18.2 | 36.1 | 2.0x（普通范围）|
| trace count | 6663 | 3996 | 0.60x |
| trace status_code (abnormal) | - | **all Unset** | 0 errors |
| **log SEVERE/ERROR** | 0 / 0 | **0 / 0** | silent on errors |

#### 误锚 ts-travel-service（GT 的 caller）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| service avg duration | 25.1 | 105.8 | 4.2x（top 2，仅次于 ts-preserve 6x）|
| trace error count | 0 | **78** | top1 |
| **log SEVERE** | 0 | **26** | incident-only "503 upstream connect error" |
| container.cpu | 0.181 | 0.214 | **1.18x（无）** |
| jvm.system.cpu.utilization | 0.036 | 0.092 | 2.56x（弱）|
| restart counter | 0 | 0 | 无 |
| hubble p50/p90/p95/p99 | 各 0.0x | 全 NaN | NaN（timeout cap）|

⭐ 跟 case 99/156/784/1195/1218/1459 同模式：caller (travel-service) trace/log 异常 + container.cpu 几乎正常 + restart 无 → 它在等 callee。

#### 503 message provenance

```
ts-travel-service SEVERE × 26:
"503 Service Unavailable: [upstream connect error or disconnect/reset before headers...
 transport failure reason: delayed connect error: Connection refused]"
```
"upstream" 是 ts-basic-service / ts-station-service / ts-route-service 等 callee。GT 在其中。

#### 全局 restart counter 扫描

```
ts-ticket-office-service-9c7b9d55b-wtrzd : restart 2 (chronic, 整段稳定)
ts-basic-service-6968d4ccd5-bgg4g        : restart 0→1  ⭐ chaos target (incident-onset)
```

只有 GT pod 有 incident-onset restart（其他 chronic）。

### 6. baseline 推理（52 round → ts-travel-service ❌）

| Round | 行为 |
|---|---|
| R5-R10 | trace error 排名 ts-travel-service 78 第一 → 锚定 |
| R12 think | confirmed by HTTP 500/503 + 3.9s latency → 加固 |
| R20-R28 | trace 调用链 loadgen → ui → preserve → travel → 看到 travel 是"leaf with errors" |
| R31 think | 转 RabbitMQ DNS（chronic noise 干扰） |
| R35 think | dismiss RabbitMQ chronic |
| R41 think | "ts-travel-service is showing errors, but I need to understand WHY. The database queries..." → **想 drill 但放弃** |
| R44-R49 | 反复查 trace span 但只查 travel 自己的 span，没查 callee（ts-basic-service） |
| R51-R52 timeline | loadgen vs travel timestamp 差 75ms → "loadgen span encompasses..." → 加固 cascade |
| FINAL | ts-travel-service ❌ |

baseline 失败子模式：**503 message provenance 误读** + cascade caller 锚定 + R41 想 drill 但放弃 + 没查 callee specific metric + first-error timestamp fallacy + silence-as-health（GT log 静默 + status_code Unset）

### 7. v4 推理（77 round → ts-travel-service ❌，**conc 命中真相后被 silence-as-health 杀回**）

| Round | 行为 |
|---|---|
| R1-R30 | 跟 baseline 一样：trace error 78 + 503 SEVERE → 锚 ts-travel-service |
| 🚨 R30 mid M6+M5 | baseline + silent service，excerpt 空 |
| R31-R55 | ✅ baseline 对比执行 → 加固 ts-travel-service（"26 SEVERE NEW, normal 0"）|
| R55 关键 | 看 ts-travel-service callee（ts-basic-service / ts-seat-service） status_code → **all Unset** |
| R56 think 🔴 | "ts-basic-service spans Unset (successful), ts-seat-service spans Unset (successful), but ts-travel-service has errors" → **silence-as-health 陷阱**：把 callee Unset 当 healthy → 反推 travel-service 是 RC |
| R57-R58 | 查 ts-travel-service hubble: p95 4.875s, p99 10s → 加固 |
| R59 final commit #1 | ts-travel-service ❌ |
| 🚨 R59 conc M8+M5 | counterfactual + silent service |
| 🟢 R60 think excerpt | "ts-travel-service might be a VICTIM, not the root cause! Some errors started BEFORE travel-service errors. Silent services: ts-ticket-office-service has restarts but doesn't appear in traces" → **真接近 GT！** |
| R61-R65 | 试图 follow up：查 ts-ticket-office-service trace（结果空） + 查 ts-preserve-service errors（"Order already exist"是 chronic）|
| 🔴 R66-R75 silence-as-health 杀回 | 重新锚回 travel-service：因为 callee status_code 全 Unset，travel-service 是"only service with Error" → counterfactual "if travel-service healthy, no 503" → ts-basic-service 标 HEALTHY in final graph |
| R75 think | "ts-travel-service is the ONLY service showing Error status (78 error spans). Error logs show: 503 Service Unavailable: upstream connect error..." → 看到 "upstream" 但**没去查 upstream 是谁** |
| R82 final commit #2 | ts-travel-service ❌（最终 graph 把 ts-basic-service 标 "HEALTHY"）|

**v4 干预实际效果**：
- mid M6 baseline 对比 ✅ 跑了 → 反向加固
- mid M5 silent service ❌ 没生效（agent 看 ts-ticket-office 静默以为是 chronic）
- conc M8 counterfactual 🟢 **R60 真命中"VICTIM"洞察**——这是 v4 最接近真相的瞬间
- 🔴 但 R65-R75 silence-as-health 杀回——agent 查 callee status_code 全 Unset → 逻辑反推"callee healthy → travel must be RC"
- conc M5 silent service ❌❌：agent 把 silent service 探针指向 ts-ticket-office（错的），不是 GT

### 8. 失败模式

| 失败链 | baseline | v4 |
|---|---|---|
| 503 message provenance | ❌ | ❌ |
| direct callee drill (specific metric) | ❌ | ❌（查了 status_code 但没查 cpu/restart） |
| 全局 restart counter | ❌ | ❌（agent 看 silent 选了 ts-ticket-office 而非全局扫描） |
| trace/log 异常 + metric 正常 → 查下游 | ❌ | ❌ |
| **counterfactual 真命中 victim 洞察** | ❌ | ✅ **R60** |
| **silence-as-health 杀回真命中洞察** | N/A | ❌❌ R66-R75 |
| status_code Unset = healthy | ❌ | ❌ 加固 |

主要失败模式：
- baseline：**503 message provenance 误读** + cascade caller 锚定 + R41 想 drill 但放弃 + silence-as-health
- v4：**F2** mid baseline 反向加固 + **F5 conc 命中-杀回模式（新变种）**：counterfactual 在 R60 命中 "ts-travel-service might be a VICTIM" 真相，但 silence-as-health 在 R66-R75 把它杀回——这是比 case 1218/1459/1495 更深刻的失败模式（victim 概念出现却被 silence-as-health 反例毁掉）

### 9. 中间件如何提示能翻转

跟 case 99/156/784/1195/1218/1459 同根 messenger vs RC 模式 + case 1814 暴露**新维度**：

- 已记录维度：trace/log 异常 + metric 全正常 → 查下游（case 784）/ direct callee drill（case 156）/ callee 排除验证 commit-gate（case 156）/ 503 message provenance（case 99）/ 全局 restart counter 扫描（case 33）/ silence-as-health 反例（case 1459）/ callee status_code Unset ≠ healthy（case 1459）
- **新维度（case 1814 暴露）：counterfactual 命中 victim 洞察后的"反例验证锁"**——当 counterfactual 真命中"我可能是 victim"时，agent 的下一步必须是**强制查 callee specific metric**（cpu / restart / page_faults），不能用 callee status_code 来"二次验证"。否则会被 silence-as-health 杀回

最有效组合：**全局 restart counter 扫描 + specific metric 强制 SQL**——一条查询立即看到 ts-basic-service-...-bgg4g restart 0→1 + container.cpu 3.52x，跟 incident_start 时间线对齐，直接命中 GT。

### 10. 中间件代码层面问题

- mid M5 silent service **完全没生效**——advisor 文本描述 "absence of evidence isn't evidence of absence"，但 agent 把 silent 探针指向 ts-ticket-office-service（chronic restart 干扰），没指向 GT
- conc M8 counterfactual **R60 命中真相**（"travel might be VICTIM"）——这是 v4 在 case 1814 中**最强的 advisor 效果**
- **但 conc M5 silent service 跟 silence-as-health 陷阱直接冲突**：agent 把 ts-basic-service status_code Unset = healthy 当成"non-silent reason 排除 callee"——advisor M5 文本鼓励 agent 找 silent service，但当 callee 不 silent（仍在产生 Unset spans）时，agent 反推它 healthy → counterfactual 锁死
- conc M5 应该改为：**"non-silent doesn't mean healthy—must query specific metric (cpu/restart) to confirm"**
- 77 round 干预次数足够，但**advisor 缺少"victim 洞察后必发 callee specific metric SQL 模板"**的硬规则——这是 F5 命中-杀回模式的根本原因

### 11. 判断

- 数据完整性：✅
- chaos 生效：✅ 必然生效（attach + OOM restart + cpu 3.52x；queryForStationId 是 hot path 方法，端点级 latency 真增加，比 1218/1459/1495 的 init/helper 注入更"干净"）
- 盲区类型：**(b) 框架盲区**（503 message provenance + silence-as-health + callee status_code Unset 误读 + counterfactual 命中-杀回 四联陷阱）
- 失败模式：F2（mid baseline 反向加固）+ **F5 命中-杀回新变种**（conc 真命中 victim 洞察后被 silence-as-health 杀回）+ baseline 子模式 503 fallacy + silence-as-health
- 给 v4.1：(1) **counterfactual victim 洞察后必发 callee specific metric SQL 强制模板**（不能用 status_code 二次验证）；(2) M5 silent service 探针不能指向"完全不出现的服务"（chronic restart pod 容易干扰），应指向"本来该出现但消失的"（normal_traces 父子关系挖空）；(3) **status_code Unset 强制不当 healthy**（同 1459/1495）；(4) **全局 restart counter 扫描**作为 mid 阶段强制 SQL（incident-onset restart vs chronic restart 对比）

### 12. causal_graph 正确性检验

⚠️ **GT 标注偏差**（service-level GT 仍正确）：
- L1 `container|ts-basic-service` state=`[high_cpu, restarting, high_memory]` —— `high_cpu` ✅（cpu 3.52x），`restarting` ✅（restart 0→1），`high_memory` ⚠️ 弱标（实测 memory 信号弱，主导仍是 cpu）。比 1218/1459 准确度高（含 restarting）
- L2 `pod|ts-basic-service-6968d4ccd5-bgg4g` state=`[high_memory, high_http_latency, high_gc_pressure, high_cpu, healthy, unknown]` —— `healthy` 跟 restart 0→1 矛盾（图模型多时刻合并产物，但仍误导）
- L4 GT span 状态 `high_avg_latency` / `high_p99_latency` / `injection_affected` —— hot-path 方法注入端点级真变慢（service avg 2.0x 不算特别强但稳定），标签成立
- L5-7 cascade ts-travel-service / ts-preserve-service / ts-ui-dashboard / loadgen 节点 `high_avg_latency` / `high_p99_latency` / `high_error_rate` / `timeout` 跟实测一致
- 整体跟 case 1218/1459/1495 同模式（container `high_memory` 弱标 + pod `healthy` 错标），但因为是 hot path 注入，端点级标签更准确

case 1814 完毕。

---

## Case 1846 · `ts3-ts-contacts-service-container-kill-s624d8` · ContainerKill (PodChaos)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| GT | `ts-contacts-service` |
| theme / tier | T8_Causal-Inversion / stable |
| baseline pred | `mysql` ❌ (qpf=63) |
| v4 pred | `mysql` ❌ (qpf=70) |
| 干预 | mid M5+M1 @ R30 / conc M8+M2 @ R58 |
| transition | wrong → wrong |

### 2. GT 注入

```
fault_type: 2 = ContainerKill (PodChaos)
display_config:
  app_label: ts-contacts-service
  container_name: ts-contacts-service
  pod_name: ts-contacts-service-658f5bc677-khmms
ground_truth.service: [ts-contacts-service]
ground_truth.pod: [ts-contacts-service-658f5bc677-khmms]
start: 2025-08-05T07:42:16Z (chaos kill 时刻)
end: 2025-08-05T07:46:16Z
```

跟之前 1218/1459/1495/1814 的 JVMMemoryStress 完全不同——这是 **ContainerKill**：直接杀 GT pod 的 container，触发 Kubernetes 重启。

### 3. chaos 机制

`kubectl container kill` → container 进程立即终止 → restart counter 0→1 → 新 container 启动（约 30-60s 冷启动）→ 这段 silence gap 内所有打到 GT pod 的请求 timeout 或 connection reset。

ContainerKill 标准指纹（参考 skill 的"chaos 指纹映射"）：
- restart 0→1 ✅
- trace 时间线 silence gap（chaos kill 后 trace 完全消失或骤减约 1 分钟）✅
- jvm.class.loaded 5000+x（JVM cold-start）→ 数据集**没有该 metric**，无法验证
- container.cpu.time counter reset → 数据集**也没有此 metric**

trace silence gap 时间线（duckdb 直查 abnormal_traces）：
```
07:42:00 → 37 spans     ← chaos kill 时刻 silence gap (chaos at 07:42:16)
07:43:00 → 461 spans    ← 新 pod 起来恢复
07:44:00 → 657 spans    ← 完全恢复
07:45:00 → 497 spans
07:46:00 → 165 spans    ← chaos 结束前后
```

### 4. 调用树（normal 期）

```
loadgen → ts-ui-dashboard
  ├─ GET /api/v1/contactservice/contacts/account/{accountId}
  │    └─ ts-contacts-service (ContactsController.findContactsByAccountId)  ◀── GT (chaos target)
  │         └─ mysql (SELECT ts.contacts)
  └─ POST /api/v1/preserveservice/preserve
       └─ ts-preserve-service → 多个 callee
```

GT 是 ts-contacts-service（被 ContainerKill），mysql 是它的 callee（数据库）。

### 5. 关键 duckdb 证据

#### GT (ts-contacts-service) ContainerKill 指纹

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| **hubble_http_request_duration_p95** | 0.011s | 0.581s | **52.53x** ⭐⭐⭐ |
| **hubble p90** | 0.009s | 0.462s | **49.18x** |
| **hubble p99** | 0.010s | 0.157s | **15.79x** |
| hubble p50 | 0.006s | 0.033s | 5.34x |
| **k8s.pod.cpu_limit_utilization** | 0.013 | 0.148 | **11.00x** |
| k8s.pod.cpu.usage | 0.067 | 0.740 | 11.00x |
| **container.cpu.usage** | 0.067 | 0.682 | **10.12x** |
| jvm.system.cpu.utilization | 0.036 | 0.124 | 3.46x |
| k8s.pod.memory.page_faults | 165k | 297k | 1.80x |
| **k8s.container.restarts (pod-level)** | 0 | 1 | **0→1** ⭐ |
| trace count | 3195 | 1817 | 0.57x |
| **trace silence gap** | - | 07:42:00 仅 37 spans | **silence pattern** ⭐ |
| service avg duration | 2.8 | 11.4 | 4.0x（top1）|

#### 误锚 mysql（GT 的 callee）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| **container.cpu.usage** | 0.049 | 0.033 | **0.67x（反而下降！）** |
| container.memory.page_faults | 134.7k | 145.6k | 1.08x（不变） |
| log ERROR (Aborted connection) | 0 | 10 | **incident-only** |

⚠️ **mysql metric 全正常 + 仅 10 个 "Aborted connection 225 to db" log** —— 这种 log 是 ts-contacts-service 被 kill 时 connection 被异常终止的 cascade artifact，不是 mysql 自身故障。

#### 全局 restart counter 扫描

```
ts-ticket-office-service-9c7b9d55b-cd7rg  : restart 3 (chronic, 整段稳定)
ts-voucher-service-c745bfccb-sglbc        : restart 1 (chronic 或中度)
ts-contacts-service-55cfbdfdc8-r94nd      : restart 0→1  ⭐ chaos target (incident-onset)
```

只有 GT pod 是 incident-onset restart——比 case 1218/1459/1814 同样的 chaos 物理铁证。

#### 全局 SEVERE/ERROR

```
ts-food-service       ERROR  168  (chronic, normal=319)
ts-preserve-service   ERROR  81   (chronic, normal=114)
ts-order-service      ERROR  81   (chronic, normal=114)
ts-notification       ERROR  48   (chronic)
ts-delivery           ERROR  48   (chronic)
ts-ui-dashboard       ERROR  20   (incident-only) ← 真信号但 ui-dashboard 是 root
```

**没有 503 / Connection refused log**。ts-ui-dashboard 20 ERROR 是 503 status code 但 SEVERE 内容跟 1218/1459/1814 不同（ContainerKill 期间 connection timeout 而非 caller 报告 upstream refused）。

### 6. baseline 推理（63 round → mysql ❌）

| Round | 行为 |
|---|---|
| R5-R10 | 看 ts-ui-dashboard 503 errors for contacts API 端点 |
| R12-R20 | 查 ts-contacts-service traces → 全 Unset (1817 spans) → "看着 healthy" |
| R20-R25 | 查 mysql logs → 看到 10 "Aborted connection" 错误 |
| R25 think 关键 | "ts-ui-dashboard 503 + MySQL Aborted connection errors" → **mysql 锚定**（log error → causal chain fallacy） |
| R30-R45 | 反复 confirm mysql ERROR + timeline (mysql 07:42:16.822 早 4s) |
| R50 think | "MySQL errors → cascade to RabbitMQ → cascade to contacts" causal chain → 加固 mysql |
| FINAL | mysql ❌ |

**baseline 失败子模式**：
1. **log error 时间线因果链 fallacy** —— mysql Aborted 早于 ui-dashboard 503 4s → 当 cause（实际是 ts-contacts-service 被 kill 时 connection 被异常终止的 cascade artifact）
2. **没查 GT (ts-contacts-service) specific metric** —— hubble p95 52.53x、container.cpu 10.12x、restart 0→1 这三个最强信号完全没看
3. **没查 mysql 自身 metric verification** —— mysql container.cpu 0.67x 反而下降（如果 mysql 是 RC，cpu 应该高），但 agent 没查
4. **没分析 trace silence gap** —— ts-contacts-service 07:42:00 仅 37 spans 是 ContainerKill 1-min gap，但 agent 没注意
5. **status_code Unset 当 healthy**（同 1495/1459 模式） —— ts-contacts-service 1817 spans 全 Unset → 当 healthy

### 7. v4 推理（70 round → mysql ❌）

| Round | 行为 |
|---|---|
| R1-R30 | 跟 baseline 类似锚 mysql（log error 时间线因果链） |
| 🚨 R30 mid M5+M1 | silent service + baseline，excerpt 空 |
| R31-R40 | ✅ baseline 对比执行 → "MySQL 0 normal vs 10 abnormal = NEW" → **加固 mysql**（incident-only 信号） |
| R32 silent service 探查 | "ts-ticket-office-service has 3 restarts but doesn't appear in traces" → 选错 silent 对象（chronic 干扰） |
| R45-R55 | 加固 causal chain "MySQL → RabbitMQ → contacts" |
| R58 final commit #1 | mysql ❌ |
| 🚨 R58 conc M8+M2 | counterfactual + chronic check |
| R60-R65 | ✅ chronic check 执行 → RabbitMQ ERROR 在 normal 也有 → dismiss RabbitMQ |
| R65 think 🔴 | "MySQL errors NEW (incident-only) vs RabbitMQ chronic (dismiss)" → 加固 mysql 因果链 |
| FINAL #2 | mysql ❌（不变，反而被 chronic check "正确"地排除 RabbitMQ 后更确信 mysql） |

**v4 干预实际效果**：
- mid M5 silent service ❌：探针指向 ts-ticket-office（chronic restart 干扰），没指向 GT silence gap（07:42:00 trace 骤减）
- mid M1 chronic check ✅：但只验证了 RabbitMQ，**没验证 mysql 是不是 chronic noise**——mysql 的 "Aborted connection 225 to db" 实际是 connection 被异常终止的常见 log，跟 mysql 自身故障无关
- conc M8 counterfactual ❌：单向加固"if mysql healthy, no Aborted connection cascade"，**没反向问"mysql 自身的 metric (cpu/memory) 跟 healthy 时差别如何"**
- conc M2 chronic check ✅：再次 dismiss RabbitMQ → 加固 mysql

### 8. 失败模式

| 失败链 | baseline | v4 |
|---|---|---|
| log error 时间线因果链 fallacy | ❌ | ❌ |
| 没查 GT (contacts-service) hubble p95 52.53x | ❌ | ❌ |
| 没查 GT restart 0→1 | ❌ | ❌ |
| 没查 GT trace silence gap | ❌ | ❌ |
| status_code Unset = healthy（GT spans 全 Unset） | ❌ | ❌ |
| 锚定候选 (mysql) 自身 metric verification | ❌ | ❌（mysql cpu 0.67x 反而下降，但 agent 没查） |
| chronic check 用错对象 | ❌ | ⚠️ 只查 RabbitMQ chronic，没查 mysql Aborted connection 是不是 chronic |
| counterfactual 双向 | ❌ | ❌ 单向加固 |

主要失败模式：
- baseline：**log error 时间线因果链 fallacy** + 没查 GT specific metric + status_code Unset 当 healthy + 没注意 trace silence gap
- v4：**F2 confirmation bias**（mid baseline 反向加固 mysql incident-only） + **F5 conc 反向加固**（chronic check 验证了正确的 chronic 但没验证 anchor 自身） + **chronic check 用错对象**（dismiss RabbitMQ ✅ 但 anchor 自身没查）

**新失败模式（case 1846 暴露）**：
- **log error 时间线因果链 fallacy（无 metric verification）**：log timestamp 顺序当因果链，没验证锚定服务自身的 specific metric。这跟 case 1218/1459/1814 的"503 message provenance"不同——503 是单条 log 误读，timeline causal chain 是多服务 log 时间排序当 cascade 顺序
- **chronic check 不对称**：advisor 让 agent 验证已知 chronic（RabbitMQ）但没引导 agent 验证**自己锚定的候选**是否也是 chronic 噪声。mysql "Aborted connection 225 to db" 实际是 connection 异常关闭的常见 ops log，trainticket 部署里很常见

### 9. 中间件如何提示能翻转

跟 case 99/156/784/1195/1218/1459/1814 同根 messenger vs RC 模式的关键维度都没用上 + case 1846 暴露**新维度**：

- 已记录：trace/log 异常 + metric 全正常 → 查下游（case 784）/ direct callee drill（case 156）/ callee 排除验证（case 156）/ 503 message provenance（case 99）/ 全局 restart counter 扫描（case 33）/ silence-as-health 反例（case 1459）/ callee status_code Unset ≠ healthy（case 1459）/ counterfactual victim 洞察后强制 callee specific metric（case 1814）
- **新维度（case 1846 暴露）：anchor 自身 specific metric verification 强制 SQL 模板**——任何"锚定候选"必须自己跑 container.cpu / restart / page_faults / hubble metric 验证一次，不能仅靠 log error 推理因果链。**mysql container.cpu 0.67x 反而下降是关键反例**，但 agent 全程没查这条
- **新维度（case 1846 暴露）：trace silence gap 检测**——chaos kill 类故障的标志是 trace 在 1 min 内骤减后恢复（07:42 仅 37 spans → 07:43 461 spans）。advisor 应触发 SQL 模板：每分钟分组 count traces by service_name，找最低谷
- **新维度（case 1846 暴露）：ContainerKill 三件套检测**——hubble_http_request_duration_p95 50x+ + restart 0→1 + trace silence gap 是 ContainerKill 标准指纹，应作为 advisor 维度优先候选

最有效组合：**全局 restart counter 扫描 + anchor 自身 specific metric verification** —— 一条查询立即看到 ts-contacts-service-...-r94nd restart 0→1，跟 incident_start (07:42:16) 时间线对齐 + mysql container.cpu 0.67x 反向加固"mysql 不是 RC"。

### 10. 中间件代码层面问题

- mid M5 silent service **没生效**——advisor 文本鼓励"找 silent service"但 agent 选了 ts-ticket-office-service（chronic restart 干扰），实际应该指向 GT pod 的 trace silence gap (07:42:00 trace 骤减) 或 GT pod 的 log -44%
- mid M1 chronic check **生效但用错对象**——dismiss RabbitMQ 是正确的，但 advisor 没引导 agent 验证 mysql 自身（"Aborted connection 225 to db" log 在 normal 期是 0 但跟 mysql 自身故障无关）
- conc M8 counterfactual **错误地加固 mysql**——单向推理 "if mysql healthy, no Aborted log cascade"，但实际 ts-contacts-service ContainerKill 时 mysql Aborted log 是必然产物，counterfactual 倒过来是真的（"if contacts-service not killed, no Aborted log"），advisor 没引导反向追查
- conc M2 chronic check **生效但同样用错对象**——再次 dismiss RabbitMQ，没验证 mysql 自身
- 70 round 干预次数足够但**advisor 缺少"anchor 自身 specific metric 强制 verification"硬规则**——这是 log timeline 因果链 fallacy 的根本反制
- **advisor 缺少 ContainerKill / PodChaos 类型的 chaos 指纹卡片**——hubble p95 50x+ 是 ContainerKill 最强指纹，advisor 应该 mid 阶段触发"hubble metric 强制查询模板"

### 11. 判断

- 数据完整性：✅
- chaos 生效：✅ 必然生效（ContainerKill 物理 kill container，restart 0→1 + trace silence gap + hubble p95 52x 三者一致）
- 盲区类型：**(b) 框架盲区**（log timeline 因果链 fallacy + status_code Unset 当 healthy + 没查 anchor 自身 metric verification + 没查 GT specific metric + chronic check 不对称 五联陷阱）
- 失败模式：F2（mid baseline 加固 mysql incident-only）+ **F5 conc 反向加固**（chronic check 用错对象，dismiss 干扰项后更确信错答案）+ baseline 子模式 log timeline 因果链 fallacy + status_code Unset = healthy
- 给 v4.1：(1) **anchor 自身 specific metric 强制 verification SQL 模板**（任何锚定候选必查 container.cpu / restart / page_faults / hubble，缺一不可）；(2) **trace silence gap 检测 SQL 模板**（每分钟分组 count traces by service_name，找最低谷或骤减）；(3) **ContainerKill / PodChaos 三件套指纹卡片**（hubble p95 50x+ + restart 0→1 + trace silence gap）；(4) **chronic check 必须双向**（验证已知 chronic 是必要 + 验证 anchor 候选自身是否 chronic 噪声）

### 12. causal_graph 正确性检验

✅ **节点核对基本通过**（比 case 1218/1459/1495/1814 准确）：
- L1 `container|ts-contacts-service` state=`[high_cpu, restarting]` —— `high_cpu` ✅（cpu 10.12x），`restarting` ✅（restart 0→1）；这次没误标 high_memory（实测 memory 仅 1.04x，确实弱）
- L2 `pod|ts-contacts-service-55cfbdfdc8-r94nd` state=`[high_cpu, healthy, high_gc_pressure, high_http_latency]` —— `high_cpu` ✅，`high_http_latency` ✅（hubble p95 52.53x），`high_gc_pressure` ⚠️ 没有 jvm.gc.duration metric 可验证；`healthy` 跟 restart 0→1 仍然矛盾（图模型多时刻合并产物）
- L4 GT span 状态 `high_avg_latency` / `high_p99_latency` / `injection_affected` / `missing_span` 跟实测一致（端点级 service avg 4.0x + hubble p99 15.79x）
- L5-7 cascade ts-ui-dashboard / loadgen / ts-preserve-service 节点 `high_avg_latency` / `high_p99_latency` / `high_error_rate` / `timeout` 跟实测一致
- 整体 ContainerKill 类型的 causal_graph 标注比 JVMMemoryStress 类型（1218/1459/1495/1814）准确得多——因为 `high_cpu`/`restarting` 直接反映 ContainerKill 物理本质，没有 mem_type=1 期望/实测错位

case 1846 完毕。

---

## Case 1917 · `ts3-ts-order-service-container-kill-gh2xcv` · ContainerKill (PodChaos)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| GT | `ts-order-service` |
| theme / tier | T1_Silence-as-Health / ultra_hard |
| baseline pred | `[ts-seat-service, ts-security-service]` ❌ (qpf=68) |
| v4 pred | `[ts-security-service, ts-seat-service]` ❌ (qpf=48，**双锚顺序换 + 仍错**) |
| 干预 | mid M6+M5 @ R30 / conc M8 @ R44 |
| transition | wrong → wrong |

### 2. GT 注入

```
fault_type: 2 = ContainerKill (PodChaos)
display_config:
  app_label: ts-order-service
  container_name: ts-order-service
  pod_name: ts-order-service-5bfb788b74-52nd2
ground_truth.service: [ts-order-service]
ground_truth.pod: [ts-order-service-5bfb788b74-52nd2]
start: 2025-08-05T08:43:20Z
end: 2025-08-05T08:47:20Z
```

跟 case 1846 同类型 ContainerKill，但 GT 不同（1846 是 ts-contacts-service，1917 是 ts-order-service）。

### 3. chaos 机制

ContainerKill 物理 kill GT pod 的 container → 重启 silence gap → 期间所有打到 GT 的请求 timeout 或 connection reset。

trace silence gap 时间线（duckdb 直查）：
```
08:44:00 → 338 spans     ← chaos 在 08:43:20 开始，08:44 是 silence gap 开始
08:45:00 → 2347 spans    ← 新 pod 起来恢复
08:46:00 → 3431 spans    ← 完全恢复
08:47:00 → 1111 spans    ← chaos 结束前后
```

### 4. 调用树（normal 期）

```
loadgen → ts-ui-dashboard
  ├─ POST /preserve
  │    └─ ts-preserve-service (preserve)
  │         ├─ ts-seat-service (seats)             ← anchor 1
  │         │    ├─ ts-order-service (122/normal) ◀── GT (chaos target)
  │         │    └─ ts-config-service
  │         └─ ts-security-service (orderCheck)    ← anchor 2
  │              ├─ ts-order-service (141/normal) ◀── GT (双源调用)
  │              └─ ts-order-other-service
  └─ POST /orderservice/order/refresh
       └─ ts-order-service (460/normal)            ◀── GT (直接被调)
```

**关键**：ts-seat-service 和 ts-security-service 两个 anchor 都是 GT 的 caller（normal: seat 调 order 2032 次，security 调 order 141 次）—— 经典 messenger vs RC 模式 + 双 caller 共享 callee（GT）。

### 5. 关键 duckdb 证据

#### GT (ts-order-service) ContainerKill 指纹

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| **container.cpu.usage** | 0.183 | 1.522 | **8.34x** ⭐ |
| **k8s.pod.cpu_limit_utilization** | 0.048 | 0.376 | **7.90x** ⭐ |
| jvm.system.cpu.load_1m | 18.4 | 113.0 | 6.16x |
| jvm.system.cpu.utilization | 0.079 | 0.409 | 5.20x |
| jvm.cpu.recent_utilization | 0.0014 | 0.0039 | 2.85x |
| k8s.pod.memory.page_faults | 166k | 284k | 1.71x |
| **k8s.container.restarts (pod-level)** | 0 | 1 | **0→1** ⭐ |
| hubble p50/p90/p95/p99 | 0.005-0.089s | 全 NaN | NaN（ContainerKill 期间请求未完成 HTTP 流程）|
| service avg duration | 3.0 | 11.5 | 3.9x（仅排第 2，被 ts-security-service 4.8x 超过）|
| trace count | 15508 | 7227 | 0.47x |
| **trace silence gap** | - | 08:44:00 仅 338 spans | **silence pattern** ⭐ |
| **log ERROR** | 86 | **53** | **abnormal 反而更少**（反常安静）|

#### 误锚 anchor 1: ts-seat-service（GT 的 caller）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| service avg duration | 13.8 | 47.0 | 3.4x（普通范围）|
| **trace error count** | 0 | **324** | top1（错率 4.9%）|
| **log SEVERE** | 0 | **108** | incident-only "503 upstream connect error" |
| jvm.system.cpu.load_1m | 18.1 | 130.8 | 7.23x（cascade 也压力大）|
| container.cpu | - | - | ~1x（无）|
| restart counter | 0 | 0 | 无 |
| hubble p50/p90/p95/p99 | 各 0.x | 全 NaN | NaN（timeout cap）|

#### 误锚 anchor 2: ts-security-service（GT 的 caller）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| service avg duration | 12.1 | 58.8 | **4.8x（top1，比 GT 还高）** |
| trace error count | 0 | 48 | 错率 6.4% |
| log SEVERE | 0 | 16 | incident-only |
| jvm.system.cpu.load_1m | 18.1 | 138.0 | 7.62x |
| container.cpu | - | - | ~1x（无） |
| restart counter | 0 | 0 | 无 |

⭐ 跟 case 99/156/784/1195/1218/1459/1814 同模式：caller (seat / security) trace/log 异常 + container.cpu 几乎正常 + restart 无 → 都在等 callee（GT）。

#### 503 message provenance

```
ts-seat-service SEVERE × 108: "503 Connection refused..."
ts-security-service SEVERE × 16: 同样 503 Connection refused
```
"upstream" 是 ts-order-service（chaos kill 时无法响应）。

#### 全局 restart counter 扫描

```
ts-ticket-office-service-9c7b9d55b-ftw24  : restart 2 (chronic)
ts-order-service-668587b48c-z7r6g         : restart 0→1  ⭐ chaos target (incident-onset)
```

只有 GT pod 是 incident-onset restart。

### 6. baseline 推理（68 round → [ts-seat-service, ts-security-service] ❌）

| Round | 行为 |
|---|---|
| R5-R10 | log scan → ts-seat-service 108 SEVERE = 503 Connection refused → 锚定 |
| R7-R8 | trace error 排名 ts-seat-service 324 + ts-security-service 48 → 双锚 |
| R10 think 关键 | "ts-seat-service has 108 SEVERE errors - all showing '503 Service Unavailable'" → 锚定 |
| R20-R30 | 反复确认 trace error 集中在 seat/security |
| R30 | trace 调用链分析 loadgen → ui → preserve → seat → 看到 seat 是 cascade 末端 |
| R40 | 加固"both are leaf services with errors" |
| 🔴 R44 关键 fallacy | think: "ts-seat-service is a leaf service (no downstream dependencies)" —— **完全错误！实际 seat 调 order 2032 次（normal）但 agent 凭印象判断没查 normal_traces 父子关系** |
| FINAL | [ts-seat-service, ts-security-service] ❌ |

**baseline 失败子模式**：
1. **503 message provenance 误读**（同 1218/1459/1814 模式）
2. **trace error 排名双锚**（seat 324 + security 48）
3. **leaf service 凭印象判断 fallacy**：agent 直接断言"seat is a leaf service"但没查 normal_traces 父子关系。实际 seat 和 security 都调 order-service（GT）
4. **没查 GT specific metric**（container.cpu 8.34x + restart 0→1 完全没查）
5. **没查 trace silence gap**（08:44:00 仅 338 spans 是 ContainerKill 标志）
6. **silence-as-health 极端版**：GT log abnormal 53 ERROR < normal 86 ERROR（反常安静），agent 看到 normal 反而更多就当 chronic dismiss

### 7. v4 推理（48 round → [ts-security-service, ts-seat-service] ❌，**F5 反向加固扩展双锚**）

| Round | 行为 |
|---|---|
| R1-R30 | 跟 baseline 类似锚 [seat, security] |
| 🚨 R30 mid M6+M5 | baseline + silent service，excerpt 复述了 baseline 对比 |
| R31-R44 | ✅ baseline 对比执行 → "seat 0→324 errors, security 0→48 errors" → **加固双锚** |
| R44 think 🔴 | "ts-seat-service is a leaf service (no downstream dependencies) - this is the key differentiator" —— **重复 baseline 同样的 leaf 判断错误！** |
| R44 final commit #1 | [ts-seat-service, ts-security-service] ❌ |
| 🚨 R44 conc M8 | counterfactual + leaf node observation |
| R45-R47 | 试图查 worker5 node 共享（但 metric query 没找到决定性） |
| 🔴 R48 think | "Mental Test: ts-security-service errors would still occur even if ts-seat-service healthy (independent failures). **Both services are independent leaf nodes with their own failure modes**" → **F5 反向加固**：counterfactual 让 agent 把单锚扩展成"两个 independent RC" |
| FINAL #2 | [ts-security-service, ts-seat-service] ❌（顺序反转，但**两个都加固**）|

**v4 干预实际效果**：
- mid M6 baseline 对比 ✅ 跑了 → 反向加固双锚
- mid M5 silent service ❌ 没生效（agent 没主动用 normal_traces 父子关系挖空，没意识到 ts-order-service 在 silence gap 中）
- conc M8 counterfactual + leaf node 观察 ❌❌ **F5 反向加固扩展版**：counterfactual 让 agent 把双锚扩展成"两个 independent leaf nodes"，比单锚错觉更深。advisor 文本说"two services as leaf nodes"无意中**强化**了错误的 leaf 判断

### 8. 失败模式

| 失败链 | baseline | v4 |
|---|---|---|
| 503 message provenance | ❌ | ❌ |
| **leaf service 凭印象判断 fallacy** | ❌ | ❌（被 advisor 文本"two services as leaf nodes"无意中强化）|
| direct callee drill | ❌（leaf 假设导致没做） | ❌ |
| 全局 restart counter 扫描 | ❌ | ❌ |
| trace silence gap 检测 | ❌ | ❌ |
| GT specific metric verification | ❌ | ❌ |
| silence-as-health 极端版（normal > abnormal ERROR）| ❌ | ❌ |
| counterfactual 双向 | ❌ | ❌ 单向加固扩展 |

主要失败模式：
- baseline：**leaf service 凭印象 fallacy**（不查 normal 父子关系就断言）+ **trace error 排名双锚** + 503 message provenance + 没查 GT specific metric + silence-as-health 极端版
- v4：**F2** mid baseline 反向加固双锚 + **F5 扩展加固版**（conc 把单锚扩展成两个 independent leaf nodes，比 case 1814 的命中-杀回更糟糕）

**新失败模式（case 1917 暴露）**：
- **leaf service 凭印象判断 fallacy**：agent 不查 normal_traces 父子关系就直接断言"X is a leaf service"，导致根本不会做 callee drill。这是 messenger 模式 + silence-as-health 之上的更基础认知错误
- **F5 扩展加固版**：counterfactual 让 agent 把单锚扩展成"两个 independent RC"，advisor 文本"two services as leaf nodes"反而强化错误的 leaf 假设
- **silence-as-health 极端版**：GT log abnormal (53) < normal (86) ERROR——这种"反常的安静"是 ContainerKill 让 GT 来不及生成 ERROR log，但 agent 看 normal 比 abnormal 多就当 chronic dismiss

### 9. 中间件如何提示能翻转

跟前面所有 messenger vs RC case 同根 + case 1917 暴露**新维度**：

- 已记录：trace/log 异常 + metric 全正常 → 查下游（case 784）/ direct callee drill（case 156）/ callee 排除验证（case 156）/ 503 message provenance（case 99）/ 全局 restart counter 扫描（case 33）/ silence-as-health 反例（case 1459）/ callee status_code Unset ≠ healthy（case 1459）/ counterfactual victim 洞察后强制 callee specific metric（case 1814）/ anchor 自身 metric verification（case 1846）/ trace silence gap 检测（case 1846）/ ContainerKill 三件套（case 1846）
- **新维度（case 1917 暴露）：leaf service 判断必须用 normal_traces 父子关系实查**——任何"X is a leaf service"断言必须配合 SQL `WITH s AS (SELECT span_id FROM normal_traces WHERE service_name='X') SELECT service_name, COUNT(*) FROM normal_traces WHERE parent_span_id IN s GROUP BY 1`。如果有非 X 自身的 callee → X 不是 leaf
- **新维度（case 1917 暴露）：silence-as-health 极端版 - normal > abnormal log ERROR**——GT 在 abnormal 期 ERROR 反而少（53 vs 86）是 ContainerKill 让 GT 来不及报错的特征。advisor 应该反向：abnormal log 量比 normal 显著减少（包括 ERROR 减少）的服务也是 silent 信号
- **新维度（case 1917 暴露）：双锚 + counterfactual 扩展加固反例**——当 agent 锚定多个候选时，conc counterfactual 必须强制收敛到单一真因（"is there a service whose failure explains BOTH anchors' errors?"），不能让 agent 把双锚扩展成"两个 independent RC"

最有效组合：**leaf service 验证 SQL + 全局 restart counter 扫描** —— 一条 SQL 立即看到 "ts-seat-service 调 ts-order-service 2032 次" 和 "ts-order-service-...-z7r6g restart 0→1"，破除 leaf 假设并指向 GT。

### 10. 中间件代码层面问题

- mid M5 silent service **没生效**——advisor 文本说"is there any service that should appear in the call chains you've traced but doesn't show up at all"，但 agent 没主动用 normal_traces 父子关系挖空 caller 的 callee。需要硬规则 SQL 模板（"对每个锚定候选，查它在 normal 时的 callee list，跟 abnormal 对比看哪些 callee 消失或骤减"）
- mid M6 baseline **反向加固双锚** —— 同 case 1218/1459/1814 模式
- conc M8 counterfactual 文本 **"two services appear as leaf nodes with independent error spikes"** ❌❌——这句话**反而强化**了错误的 leaf 判断！advisor 应该改为 "verify with normal_traces parent-child query whether your anchors are actually leaf services"
- conc M8 counterfactual 没引导收敛——"if your primary candidate were healthy, would the others still occur?" 让 agent 把双锚拆成"two independent RC"。应该改为"is there a SHARED downstream that explains BOTH"
- 48 round 干预次数偏少（比 case 1218 的 60 + 1459 的 43 + 1495 的 82 + 1814 的 77 + 1846 的 70），但**leaf service 假设让 agent 直接绕过 callee drill**——干预次数不是关键，关键是**没破除 leaf 错觉**

### 11. 判断

- 数据完整性：✅
- chaos 生效：✅ 必然生效（ContainerKill restart 0→1 + container.cpu 8.34x + trace silence gap）
- 盲区类型：**(b) 框架盲区**（leaf service 凭印象 fallacy + 503 message provenance + silence-as-health 极端版 + F5 扩展加固版 四联陷阱）
- 失败模式：F2（mid baseline 反向加固双锚）+ **F5 扩展加固版**（conc counterfactual 把双锚扩展成"two independent leaf RC"，advisor 文本"leaf nodes"无意中强化错误） + baseline 子模式 leaf service fallacy + 503 fallacy + silence-as-health 极端版
- 给 v4.1：(1) **leaf service 假设强制验证 SQL 模板**（任何锚定必须查 normal_traces 父子关系，不准凭印象）；(2) **conc counterfactual 必须收敛到单一 RC**（"is there a SHARED downstream that explains BOTH anchors"），不能让 agent 把双锚拆成 independent；(3) **silence-as-health 极端版检测**：abnormal log < normal log（包括 ERROR 减少）也是 silent 信号；(4) **conc M8 advisor 文本不能用 "leaf nodes" 作为既定事实**——应该让 agent 验证 leaf 假设是否成立

### 12. causal_graph 正确性检验

⚠️ **GT 标注偏差**（service-level GT 仍正确）：
- L1 `container|ts-order-service` state=`[high_cpu]` —— ✅ 简洁准确（cpu 8.34x），没误标 high_memory（实测 memory 仅 1.03x）。但**少标了 `restarting`**（restart 0→1 实际发生），跟 case 1846 比少了一个状态字段
- L2 `pod|ts-order-service-668587b48c-z7r6g` state=`[high_cpu, high_gc_pressure, high_memory, healthy]` —— `high_cpu` ✅，`high_memory` ⚠️ 弱标（memory 仅 1.03x）；`healthy` 跟 restart 0→1 矛盾（图模型多时刻合并产物）；`high_gc_pressure` 没 jvm.gc.duration 可验证
- L4 GT span 状态 `high_avg_latency` / `high_p99_latency` / `injection_affected` / `missing_span` —— hubble p50/p90/p95/p99 全 NaN（请求在 ContainerKill 期间未完成），avg 拉到 11.5ms（service avg ratio 3.9x），标签成立
- L5-7 cascade ts-seat-service / ts-security-service / ts-preserve-service / ui-dashboard / loadgen `high_avg_latency` / `high_p99_latency` / `high_error_rate` / `timeout` 跟实测一致
- 跟 case 1846 同 ContainerKill 类型，container 节点 state 比 JVMMemoryStress 类型（1218/1459/1495/1814）少 `high_memory` 误标，但仍漏标 `restarting`（1846 标了，1917 没标）。整体 ContainerKill 类 graph 标注比 JVMMemoryStress 类准但 case 间不一致

case 1917 完毕。

---

## Case 1948 · `ts3-ts-preserve-service-container-kill-k7k8g5` · ContainerKill (4s)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 1948 |
| GT 根因 | `ts-preserve-service` |
| theme | T3_Noise-Anchor |
| tier | stable |
| baseline pred | `ts-delivery-service` ❌ |
| v4 pred | `ts-ui-dashboard` ❌ |
| baseline qpf / v4 qpf | 43 / 50 |
| 干预 | mid M6+M5 (R30) / conc M8 (R48) |
| transition | wrong→wrong |

### 2. GT 注入

```
fault_type: 2 = ContainerKill (PodChaos)
display_config:
  duration: 4 s
  injection_point:
    app_label:      ts-preserve-service
    container_name: ts-preserve-service
    pod_name:       ts-preserve-service-7684df89bd-sk5cd
  namespace: ts
ground_truth:
  container/pod/service: ts-preserve-service
```

### 3. chaos 机制

ContainerKill 把 ts-preserve-service 的 container 杀掉 4 秒，让 k8s 自动重启它。物理上产生三个硬指纹：
1. **`k8s.container.restarts` 0 → 1**：唯一一个 abnormal 期新增 restart 的 pod（normal/abnormal 共存 ts-ticket-office-service 的 chronic 3-restart 不变）
2. **container/pod cpu 6.5–8.5x 飙升**：JVM cold-start 重新加载 class 阶段
3. **hubble_http_p50/p90/p95/p99 全部 NaN**：service mesh observe 不到任何 http 请求成功完成

trace 端的特点是 **survivorship bias**：4 秒短窗口里彻底死掉的请求**根本没 export trace**，重启后端点重新 200 OK。所以 `attr.http.response.status_code` 在 ts-preserve-service 上**全部 200**，503 只出现在它的 caller `ts-ui-dashboard` 上（ui-dashboard 调 preserve 失败转发的）。

### 4. 调用树（normal 期实测）

```
loadgenerator
  └─ ts-ui-dashboard
      └─ ts-preserve-service          ◀── GT (chaos target)
          ├─ ts-order-service
          ├─ ts-basic-service
          ├─ ts-travel-service
          ├─ ts-contacts-service
          ├─ ts-security-service
          ├─ ts-seat-service
          ├─ ts-assurance-service
          ├─ ts-food-service
          └─ ts-user-service
```

### 5. 沿调用链从根因到 SLO 的逐节点变化

#### chaos 直接证据（ts-preserve-service）

| 信号 | normal | abnormal | ratio |
|---|---|---|---|
| **k8s.container.restarts** (max) | 0 | **1** | 0→1 ✓ |
| container.cpu.usage | 0.058 | 0.488 | **8.45x** ✓ |
| k8s.pod.cpu.usage | 0.063 | 0.413 | **6.55x** ✓ |
| k8s.pod.cpu_limit_utilization | 0.013 | 0.083 | **6.55x** ✓ |
| jvm.system.cpu.utilization | 0.068 | 0.139 | 2.05x |
| k8s.pod.memory.page_faults | 1.37e5 | 2.55e5 | 1.86x |
| hubble_http_p50/p90/p95/p99 | 0.0065/0.0167/0.0279/0.0439 | **NaN/NaN/NaN/NaN** | service-mesh 全失活 ✓ |
| trace count | 1286 | 843 | 0.66x |
| log count | 2017 | 1326 | 0.66x |

trace timeline 实测有不连续 gap：01:22:09–10、01:22:23–26、01:23:02–03 等多次 2–4 秒空窗，跟 chaos 4 秒期 + restart 一致。

#### 上游 cascade victim（ts-ui-dashboard）

| 信号 | normal | abnormal | ratio |
|---|---|---|---|
| `POST /api/v1/preserveservice/preserve` count | 147 | 118 | 0.80x |
| 同端点 status_code = 503 | 0 | **17** (14.4% of 118) | new ✓ |
| 同端点 avg duration | ~3 ms | ~12 ms | 3.9x (实际 a_p95=3566ms) |

#### SLO 表现（loadgenerator）

| 信号 | normal | abnormal |
|---|---|---|
| `HTTP POST .../preserveservice/preserve` p95 | — | **5950 ms** |
| 同端点 max | — | **20 001 ms** (timeout) |

ts-ui-dashboard 收到 ts-preserve-service 不可达 → 返回 503 / 超时 → loadgenerator 端点 p95 接近 6 秒。

### 6. baseline 完整推理（无中间件）

baseline 跑 43 round → `ts-delivery-service` ❌

| Round 段 | 行为 | 关键决策 |
|---|---|---|
| R1–R10 | 数据探查 | 列 service、log/trace/metric schema |
| R13 | error 分布 | ts-food-service 202、ts-order-service 80、ts-preserve-service 80、**ts-delivery-service 48** |
| R28 | call chain | 识别 loadgen → ui-dashboard → ts-preserve-service |
| R40 | timeline first-error | 01:21:31.175 ts-delivery-service "Failed to check/redeclare auto-delete queue(s)" → **判定为 EARLIEST ERROR** |
| R46 | trace deep-dive | 看到 ts-ui-dashboard 503，但归因到"earliest error 比 ui-dashboard 早" |
| 🔴 R52 | 摇摆 | 一度想锚 ts-rabbitmq（broker 不可达） |
| 🔴 R63 | 锚定 | "**Root Cause: ts-delivery-service** (earliest error timestamp: 01:21:31.175)" |
| FINAL | commit | ts-delivery-service ❌ |

**baseline 失败子模式**：
1. **first-error timestamp fallacy** — 把"timeline 第一个 ERROR"当 RC（实际是 chronic queue 错误）
2. **chronic noise 锚定** — ts-delivery-service "Failed to redeclare auto-delete queue" 在 normal 47 / abnormal 48（几乎完全一样）+ trace count **0 / 0**（完全不在 trace 中）。是 100% chronic baseline noise，跟 chaos 完全无关
3. 没查 `k8s.container.restarts`、没查 hubble HTTP NaN、没查 ts-preserve-service container.cpu

### 7. v4 推理路径（有中间件）

v4 跑 50 round → `ts-ui-dashboard` ❌

| Round 段 | 行为 | 关键决策 |
|---|---|---|
| R1–R29 | 跟 baseline 几乎一样 | abnormal-only 视角，error 分布 + ts-food/order/preserve 同样的 chronic anchor 倾向 |
| 🚨 R30 mid M6+M5 | baseline contrast + silent service | agent_response：复述 + 真要去做对比 |
| R31–R42 | normal vs abnormal 对比 | 真做了，发现：trace status_code "Error" — normal=0, abnormal **只 ts-ui-dashboard 17 + loadgen 2** |
| R43 | think_tool | "ts-ui-dashboard 是 ONLY service with NEW errors in abnormal" |
| R44–R45 | container.cpu 检查 | 只查了 ts-ui-dashboard 自己的 metric（avg=0.030 看上去正常），**没查 ts-preserve-service container.cpu** |
| R46 | restart counter 全表扫 | 命中 GT smoking gun：**ts-preserve-service-5d979f4b55-n6ccw 1 restart (NEW)**，ts-ticket-office-service 3 restarts (chronic) |
| R47 | normal restart 对照 | 确认 ts-ticket-office 是 chronic、ts-preserve 是新增 |
| 🔴 R48 think_tool | **看到 GT 信号但忽略** | 原话："ts-preserve-service has 1 restart (new) ... but ts-ui-dashboard is the ONLY service with NEW errors" → 用 trace error 视角而非 restart 视角锚定 |
| 🚨 R48 conc M8 | counterfactual + cascade caller | 概念命中（"503 是否在更上游产生？"），但 advisor 文本只描述、没强制 SQL 模板 |
| R49 | counterfactual | "if ts-ui-dashboard healthy → 503 不会发生" → **加固 ts-ui-dashboard** |
| R50 | trace 链查询 | 看到 trace `13f0cda9...` 里 successful path: ui-dashboard(200) → preserve(200) → 下游 (200) → "preserve healthy" — **survivorship bias** |
| FINAL | commit | "**503 errors are generated BY ts-ui-dashboard, not propagated**" → ts-ui-dashboard ❌ |

**v4 干预实际效果**：
- mid M6 baseline contrast：✅ 成功 dismiss chronic noise（ts-food-service / ts-delivery-service / ts-order-service）
- mid M5 silent service：⚠️ 概念被 agent 内化为"找 NEW errors"，但 silent service 应配合 restart counter scan，agent 自发跑了但 commit 时没用
- conc M8 counterfactual：❌ **F5 反向加固** — counterfactual 让 agent 用"503 是 ui-dashboard 生成的"逻辑加固 ui-dashboard
- conc M8 cascade hint：❌ 概念命中（"503 是否更上游产生？"），但 advisor 没给"check 是否 child span 状态被父 span 503 mask"或"check restart counter on each child"的硬规则；agent 翻译为"trace 里 preserve 200 → preserve 健康"，掉进 survivorship bias

### 8. 失败模式诊断（baseline vs v4 对比）

| 失败链 | baseline | v4 |
|---|---|---|
| 锚点切换轨迹 | first-error fallacy → ts-delivery (chronic) | chronic dismiss ✓ → cascade caller ts-ui-dashboard (F4) |
| 真信号查没查 | ❌ 没查 restart / cpu / hubble | ✅ **查到 ts-preserve-service restart 0→1** 但 commit 时不锚 |
| chronic check | ❌ 没做 | ✅ 做了（这是 mid 真生效部分） |
| survivorship bias | — | ❌ 严重：拿"successful trace 里 preserve 返回 200"反证 preserve 健康 |
| specific metric | ❌ 没查 | ❌ 只查 ui-dashboard metric，没扩展到 preserve |

**主要失败模式**：
- F2 advisor 维度对但 reasoning 不动（看到 restart 0→1 不锚）
- F4 cascade 选错位置（选直接 caller ts-ui-dashboard 而非 ContainerKill 真目标 ts-preserve-service）
- F5 conc M8 counterfactual 反向加固
- baseline 子模式：first-error timestamp fallacy + chronic noise 锚定 + survivorship bias（v4 共享）

### 9. 中间件如何提示能翻转

| 维度 | 触发条件 | 干预语 |
|---|---|---|
| **restart-as-RC 强规则** | 任何服务 abnormal restart > normal restart 且 normal=0 → 必须把它当一级嫌疑（即使该服务 trace 全 200 / 没 SEVERE log） | "若发现某 pod abnormal 期新增 restart 而 normal 期为 0，无论它的 trace status / log level 看起来多正常，都要将它列为头号 RC 候选；transient chaos（短窗口 ContainerKill / PodKill）期间死掉的请求往往不会 export trace，trace 上的 200 不能反证健康。" |
| **survivorship-bias test** | conc 阶段，agent 用"some trace 在 X 服务返回 200" 反证 X 健康时触发 | "successful traces 只能证明 X 在那些被记录的时刻可服务，不能反证 chaos 窗口内 X 没死。请补查：(a) X 的 hubble_http_p50/p99 是否 NaN；(b) X 的 container.cpu / restart 是否突变；(c) X 的 trace 是否有秒级 gap；任一命中即推翻 healthy 判断。" |
| **transient-chaos fingerprint set** | 调查到 service mesh 上有 503 + 短期 throughput 下降 + 无明显 SEVERE log 时 | "短窗口 chaos（ContainerKill / PodKill / 短 NetworkPartition）三件套：(1) `k8s.container.restarts` 0→1 (2) container.cpu / pod.cpu 5–10x cold-start 飙升 (3) hubble_http quantile NaN。任一命中即定位真 RC 服务，503 caller 是 cascade victim。" |
| **cascade-direction inversion** | conc 阶段，agent 把"503 由 X 返回"当 X = RC 时触发 | "503 / 5xx 的 status_code = 报告者，未必 = 故障源。沿 X 的调用链向**下**逐个 child service 查 restart / hubble，找到第一个出现 transient-chaos 三件套的下游服务。" |

最有效组合：**restart-as-RC 强规则 + survivorship-bias test**。本 case agent 已经看到 restart 0→1 + ts-ticket-office chronic 的对比，缺的是"restart 0→1 必须直接锚定，不允许被 trace 200 否决"这一条硬规则。

### 10. 中间件代码层面问题

- **mid M6 卡片不含"restart counter scan"硬指引**：advisor 让 agent 做 baseline contrast，agent 自发去查了 restart 但是没把结果当一级证据
- **mid M5 silent-service 跟 restart 没显式联动**：M5 描述"absence of evidence isn't evidence of absence"，但没说"silent → 必查 restart / hubble NaN"
- **conc M8 counterfactual 是双刃剑**：当 agent 已锚错答案时，counterfactual 让它用"if X healthy → no symptom"加固自己；该 case 是典型 F5。conc 应在 counterfactual 前加 survivorship-bias 测试
- **conc M8 cascade hint 描述弱**：advisor 文本说"503 是否在更上游产生"，但 trainticket cascade direction 是 caller→callee（loadgen→ui-dashboard→preserve），advisor 没说清"沿调用链向哪个方向追"，agent 把"上游"理解成 loadgen 方向（实际是 ui-dashboard），错过 preserve 是 callee
- **没有 leakage**（advisor 文本不含 "ts-preserve-service" 或 "ContainerKill"）

### 11. 判断

- **数据是否完整**：✅（restart 0→1、container.cpu 8.45x、hubble NaN 都在 abnormal_metrics 里，agent 都查到了）
- **chaos 是否生效**：✅ 必然生效（ContainerKill 是物理 kill，restart counter 直接体现）
- **真假盲区分类**：(b) 框架盲区 — 不是数据问题，agent 真看到了 GT smoking gun（restart 0→1）但**判定逻辑用 trace status code 优先级压过了 restart counter**
- **失败模式归纳**：F2 + F4 + F5 + survivorship bias + first-error/chronic（baseline 子模式）
- **给 v4.1 的提示**：
  1. **加 restart-as-RC 强规则卡**：normal=0 + abnormal=1 是 ContainerKill / PodKill 的硬指纹，应作为不可被 trace 200 / log 静默否决的一级证据
  2. **conc M8 在 counterfactual 前先加 survivorship-bias 测试**：当 agent 用"成功 trace 链反证 X 健康"时强制查 hubble NaN / restart / trace gap
  3. **mid M5 silent-service 需联动具体 SQL 模板**：silent 表现的服务必查 (i) k8s.container.restarts 全表扫 (ii) hubble_http_pXX NaN (iii) container.cpu

### 12. causal_graph 正确性检验

- container|ts-preserve-service `high_cpu`：✓ container.cpu.usage 8.45x
- pod|...-5d979f4b55-n6ccw `high_cpu` ✓ / `high_http_latency` ✓ (p99 5926ms) / `high_memory` 弱（page_faults 1.86x、memory.available 1.01x，同列次要、不算错标）/ `high_gc_pressure` 无 `jvm.gc.*` 数据可验证 / `healthy` multi-snapshot 共存
- service|ts-preserve-service `unknown`（GT 标注预期）
- span|ts-preserve-service::PreserveController.preserve `missing_span`（trace timeline 多个秒级 gap ✓）/ `high_p99_latency`（p99 5921ms ✓）/ `injection_affected` ✓
- span|ts-ui-dashboard::POST .../preserveservice/preserve `high_avg_latency` ✓ (3.9x) / `high_error_rate` ✓ (17/118=14.4%, all 503)
- span|loadgenerator::HTTP POST .../preserveservice/preserve `timeout` ✓ (max 20s)

causal_graph 节点核对通过。

case 1948 完毕。

---

## Case 2211 · `ts3-ts-travel-service-container-kill-jctldw` · ContainerKill (4s)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 2211 |
| GT 根因 | `ts-travel-service` |
| theme | T2_Blame-the-Messenger |
| tier | stable |
| baseline pred | `ts-route-plan-service` ❌ |
| v4 pred | `ts-route-plan-service` ❌ |
| baseline qpf / v4 qpf | 67 / 69 |
| 干预 | mid M6+M5 (R30) / conc M8 (R68) |
| transition | wrong→wrong |

### 2. GT 注入

```
fault_type: 2 = ContainerKill (PodChaos)
display_config:
  duration: 4 s
  injection_point:
    app_label:      ts-travel-service
    container_name: ts-travel-service
    pod_name:       ts-travel-service-7f856dcb7b-crxhh   (注入定位)
ground_truth:
  container/service:  ts-travel-service
  pod:                ts-travel-service-7f856dcb7b-m5727 (注入后实际 pod replica)
```

### 3. chaos 机制

ContainerKill 把 `ts-travel-service` container 杀 4 秒 → k8s 重启。物理上跟 case 1948 同一指纹族（restart 0→1 + cold-start CPU 飙升 + hubble NaN）。

**这个 case 的特殊点**：`ts-travel-service` 是 trainticket 拓扑里的"中间层枢纽"，被 ts-route-plan / ts-food / ts-preserve / ts-ui-dashboard 等 4+ 个 caller 调。当它死掉，**最 vocal 的是 caller `ts-route-plan-service`**：它报 44 行 `503 Service Unavailable: [upstream connect error ... transport failure reason: delayed connect error: Connection refused]`。这种 sidecar/Envoy 风格的 503 包装让 agent 把 caller 当 RC（**Blame-the-Messenger**）。

### 4. 调用树（normal 期实测）

```
loadgenerator
  └─ ts-ui-dashboard
      ├─ ts-travel-plan-service
      │   └─ ts-route-plan-service     ← 唯一 SEVERE 服务（44 行 503 upstream connect error）
      │       └─ ts-travel-service     ◀── GT (chaos target, silent)
      │           ├─ ts-seat-service
      │           ├─ ts-basic-service
      │           └─ ts-route-service
      ├─ ts-travel-service             ← 也是直接 callee
      └─ ts-preserve-service
          └─ ts-travel-service          ← 也是直接 callee
```

`ts-travel-service` 的直接 caller（normal 期 trace 数）：
- ts-route-plan-service 388
- ts-food-service 140
- ts-ui-dashboard 129
- ts-preserve-service 120

### 5. 沿调用链从根因到 SLO 的逐节点变化

#### chaos 直接证据（ts-travel-service）

| 信号 | normal | abnormal | ratio |
|---|---|---|---|
| **k8s.container.restarts** (max) | 0 | **1** | 0→1 ✓ |
| container.cpu.usage | 0.177 | 0.967 | **5.46x** ✓ |
| k8s.pod.cpu.usage | 0.191 | 1.055 | **5.54x** ✓ |
| jvm.system.cpu.utilization | 0.061 | 0.205 | 3.36x |
| jvm.system.cpu.load_1m | 13.65 | 30.03 | 2.20x |
| k8s.pod.memory.page_faults | 1.70e5 | 3.16e5 | 1.86x |
| **hubble_http p50/p90/p95/p99** | 0.041 / 0.217 / 0.368 / 0.934 | **NaN/NaN/NaN/NaN** | service-mesh 全失活 ✓ |
| trace count | 6602 | 4395 | 0.67x |
| log SEVERE | 0 | 0 | — (silence-as-health 陷阱) |
| trace status_code Error | 0 | **0** | silence ✓ |

ts-travel-service trace timeline 在 22:16:02–08（约 7 秒）有显著 gap，跟 chaos 4s + restart cold-start 一致。

#### 上游 cascade victim（ts-route-plan-service —— Messenger）

| 信号 | normal | abnormal |
|---|---|---|
| log SEVERE | 0 | **44**（"503 upstream connect error / delayed connect error: Connection refused"，全部同质） |
| 直接 trace span 503 | 0 | 44 |
| 直接 trace span 500 | 0 | 36 + 8 = 44 |
| trace count | 1296 | 1010 (-22%) |
| status_code "Error" | 0 | 132 |
| caller-callee edge `route-plan→travel-service` | 388 | 249 (ratio 0.642，跟全局 chaos 0.67x 同量级，无突出 dropout) |

ts-route-plan-service 的 SEVERE 完整内容：
```
Servlet.service() ... 503 Service Unavailable: [upstream connect error or disconnect/reset
before headers. retried and the latest reset reason: remote connection failure,
transport failure reason: delayed connect error: Connection refused]
```
**关键**：log message **不含目标服务名**（只说 upstream），agent 必须靠 trace 调用链反推 target 是 ts-travel-service。

#### SLO 表现（loadgenerator）

ts-ui-dashboard 端点 timeout / 503 上传到 loadgenerator，端点 quickest/cheapest/minStation 都 high_p99_latency。多个 trip_detail / trips/left 端点 a_p99 2400ms+。

### 6. baseline 完整推理（无中间件）

baseline 跑 67 round → `ts-route-plan-service` ❌

| Round 段 | 行为 | 关键决策 |
|---|---|---|
| R1–R23 | 数据探查 + log error 排序 | 锁定 ts-route-plan-service 44 SEVERE = 唯一异常 |
| R32–R34 | trace 错误分布 | 132 Error spans on ts-route-plan-service（最多） |
| R47 | log message 提取 | "503 Service Unavailable: Connection refused" → 判 ts-route-plan-service 是 origin |
| R66–R68 | 调用链分析 | trace `6ff7...`：loadgen→ui-dashboard→travel-plan→route-plan(Error) → "error stops at ts-route-plan-service" |
| 🔴 R67 | first-error timestamp | ts-route-plan SEVERE 22:15:22 < ui-dashboard ERROR 22:15:25 < travel-plan SEVERE 22:15:33 → 锚定 |
| FINAL | commit | "First to fail + 132 Error spans + Connection refused 起源" → ts-route-plan-service ❌ |

**baseline 失败子模式**：
1. **503 message provenance 误读**：caller 报 "upstream Connection refused"，target 不是 logger 自己，但 agent 把它当 origin
2. **first-error timestamp fallacy**：cascade 上 caller 先报错 → 当 RC（实际是 callee 死了 caller 才有时间报错）
3. **loud victim / Blame-the-Messenger 锚定**：唯一 SEVERE 飙升 + 最多 Error spans → 锚定
4. **silence-as-health**：ts-travel-service trace 全 Unset、log 0 SEVERE → 当 healthy（实际 chaos 期间死掉的请求没 export）
5. 没查 ts-travel-service `k8s.container.restarts` / hubble HTTP / container.cpu

### 7. v4 推理路径（有中间件）

v4 跑 69 round → `ts-route-plan-service` ❌

| Round 段 | 行为 | 关键决策 |
|---|---|---|
| R1–R29 | 跟 baseline 几乎一样 | 锚定 ts-route-plan-service（132 Error spans + 503 Connection refused） |
| 🚨 R30 mid M6+M5 | baseline contrast + silent service | agent_response：复述 + "确认 ts-route-plan-service is anomalous" |
| R31–R56 | normal vs abnormal 对比 | 反而**强化了** route-plan 锚定（normal 0 → abnormal 132 Error spans） |
| R56 | 试图找 downstream | 注意到 ts-route-plan-service 调 ts-travel-service 的方法 `getTripFromHighSpeedTravelServive` 返回 `[Size:0]`（应用层观察） |
| R63 | trace count 对比 | route-plan 1296→1010 (-22%), travel-plan 1734→1103 (-37%) — 没注意到 **travel-service** 自己的 6602→4395 |
| 🔴 R64 | "Connection refused" target 自查 | SQL：`message LIKE '%Connection refused%' AND service_name != 'ts-route-plan-service'` → **空结果** → agent 推断 "Connection refused 只发生在 route-plan，所以是 origin"（**这是关键决定性误判**：connection refused 只会从 caller 端报告，callee 死掉时它自己根本不会有 connection refused log） |
| R66 | 加固 think_tool | "ts-route-plan-service is the origin" |
| R68 | first-error timestamp 对照 | route-plan 22:15:22 < ui-dashboard 22:15:25 → first-error fallacy 加固 |
| 🚨 R68 conc M8 | counterfactual | advisor 询问"if X healthy would symptoms still occur" |
| 🔴 R69 think_tool | 反向加固 | "If route-plan healthy → 整个调用链成功 + ts-travel-service downstream 看起来 healthy（trace 0 error + 仅 5 行 'Trip already exists'）" → **F5 加固** |
| FINAL | commit | "ts-travel-service is healthy → ts-route-plan-service 是 RC" ❌ |

**v4 干预实际效果**：
- mid M6 baseline contrast：❌ **反向加固** — 让 agent 用 normal/abnormal 对比加固 route-plan（132 Error vs 0 normal），跟原本错锚向相同
- mid M5 silent service：❌ 概念命中但应用错 — agent 把 silent 概念用在"哪些服务 silent on errors"上，没意识到 silent on errors 本身可能就是 chaos signature
- conc M8 counterfactual：❌ **F5 反向加固** — agent 通过反推"if route-plan healthy → travel-service 仍 healthy（trace 0 error）→ no symptom"加固 route-plan
- conc M8 cascade hint：❌ 概念命中（"503 是否更上游产生"）但 advisor 没说清"上游"是 caller 还是 callee，agent 把"上游"翻译为"loadgen 方向"

### 8. 失败模式诊断（baseline vs v4 对比）

| 失败链 | baseline | v4 |
|---|---|---|
| 锚点切换轨迹 | 一直锚 route-plan（503 + 132 Error + first-error） | 一直锚 route-plan（baseline contrast 加固 + counterfactual 加固） |
| 真信号查没查 | ❌ 全部没查 | ❌ 全部没查 ts-travel-service restart/hubble/cpu |
| Connection refused target 自查 | ❌ | ⚠️ 查了但用错（找其他服务 Connection refused log → 空 → 推 route-plan 是 origin；正确做法应该是查 ts-travel-service 的 restart/hubble） |
| silence-as-health | ❌ | ❌ 加重（counterfactual 用"travel-service trace 0 error"反证 healthy） |

**主要失败模式**：
- F2 advisor 维度对但 reasoning 不动（baseline contrast 让 agent 验证锚定，不是推翻）
- F5 conc M8 counterfactual 反向加固（典型 victim-cascade 模式）
- baseline 子模式：503 message provenance 误读 + first-error timestamp fallacy + Blame-the-Messenger + silence-as-health

跟 case 1948 高度相似（也是 ContainerKill → caller 503 cascade）。**唯一差异**：1948 agent 至少查了 restart counter 看到 GT 信号；2211 agent **从头到尾没查 ts-travel-service 自己的任何 metric**（包括 restart / cpu / hubble），完全停在调用链 caller 视角。

### 9. 中间件如何提示能翻转

| 维度 | 触发条件 | 干预语 |
|---|---|---|
| **Connection refused target tracking** | log/trace 出现 "Connection refused" / "upstream connect error" / "transport failure" | "Connection refused / upstream connect error 永远是 **caller 端**报告的；目标 callee 自己死掉时不会 log connection refused（它根本没收到连接）。请用调用链反推 target 是哪个 callee，然后**直接查 callee 自己**的 (a) `k8s.container.restarts` (b) hubble_http_pXX 是否 NaN (c) container.cpu / jvm.cpu。任一异常 → callee 是 RC，logger 是 messenger。" |
| **silence-as-health 反证强模板** | agent 用 "X 的 trace 全 Unset / log 0 SEVERE" 反证 X healthy | "trace status_code = Unset 和 log 无 SEVERE 不能反证 X 健康。短窗口 chaos 期间死掉的请求**不会** export trace、callee 端不会 log。请补查 X 自己的 (1) restart counter abnormal vs normal (2) hubble_http_pXX NaN 数 (3) container.cpu ratio (4) trace 是否有秒级 gap。任一异常 → 推翻 healthy 判断，X 即真 RC。" |
| **first-error timestamp 反规则** | cascade 模式下用 "X SEVERE 时间比 Y 早 → X 是 origin" | "短窗口 chaos 下，cascade caller 比真 RC 服务**先**有 SEVERE log（因为 caller 是 messenger，会 log 它对 callee 的连接失败；callee 自己死了不 log）。first-error timestamp 在 cascade-caller-vocal 模式下反向 — 必须用 callee 的 restart/hubble 替代 timestamp 排序。" |
| **counterfactual 双向 callee-side check** | conc 阶段，agent 用 "if X healthy → no symptom" 加固 X 时 | "counterfactual 必须双向：(a) 'if X healthy → no symptom' 只能验证 X 是 cascade 必经路径 (b) 还要做 'if X-的 callee 健康 → X 还会报错吗'。如果 X 报 connection refused 指向 callee Y，那么 'if Y healthy → X 不会有 connection refused log' 同样成立 → Y 才是真 RC。" |

最有效组合：**Connection refused target tracking + silence-as-health 反证强模板**。本 case agent 在 R64 已经主动想验证 connection refused target，但用错查询方向（找其他服务有没有该 log，应该查 connection refused 提到的 callee 自己的状态）。

### 10. 中间件代码层面问题

- **mid M6 baseline contrast 在 victim-cascade 模式下反向加固**：当 cascade caller vocal 而 callee silent 时，normal/abnormal 对比让 caller 的 132 vs 0 Error spans 反而成了"实锤"，强化 caller 锚定。M6 应配套 "silent service deep-check" 子规则。
- **conc M8 counterfactual 没区分 cascade 必经路径 vs 真 RC**：当 X 是 cascade 中间任一节点时，"if X healthy → no symptom" 都成立。M8 应增"if X 的 callee 健康 → X 还有 error 吗"双向检查。
- **mid M5 silent-service 缺联动 SQL 模板**：M5 描述"silent service 不一定 healthy"是抽象概念，没给"silent + restart 0→1 / hubble NaN / cpu 5x"的具体三件套查询。
- **R64 agent 自发 connection-refused 排查方向错**：advisor 应在出现 503 / connection refused / upstream connect error 时强制提示"查 connection refused 报告**指向**的服务"。
- **没有 leakage**

### 11. 判断

- **数据是否完整**：✅（restart 0→1、container.cpu 5.46x、hubble NaN 全在 abnormal_metrics 里）
- **chaos 是否生效**：✅ 必然生效（ContainerKill 物理 kill）
- **真假盲区分类**：(b) 框架盲区 — agent 完全没查 ts-travel-service 自己的 metric，停留在 caller-side 调用链分析。framework 没强制 "callee-side metric check on connection-refused log"
- **失败模式归纳**：F2 + F5 + 503 message provenance 误读 + first-error fallacy + silence-as-health + Blame-the-Messenger
- **给 v4.1 的提示**：
  1. **Connection refused / upstream connect error 触发强 callee-side metric check**：log / trace 有这类 message → 强制查 message 指向的 callee 的 restart / hubble / cpu，禁止只看 caller-side
  2. **counterfactual 升级为双向**：增加 "if callee Y healthy → X 还会有 connection refused 吗"，避免 cascade 中间节点被 F5 加固
  3. **silence-as-health 反证强模板**：trace 0 error + log 0 SEVERE 时强制查 restart/hubble/cpu，禁止单凭 trace status / log level 判 healthy

### 12. causal_graph 正确性检验

- container|ts-travel-service `high_cpu` ✓ container.cpu.usage 5.46x
- pod|...-56c9999f79-xwmb8 `high_cpu` ✓ / `high_memory` 弱（page_faults 1.86x、memory.available 1.02x，同列次要、不算错标）/ `high_gc_pressure` 无 jvm.gc.* 数据可验证 / `healthy` multi-snapshot 共存
- service|ts-travel-service `unknown`（GT 标注预期）
- ts-travel-service 多个 span `missing_span` ✓（trace timeline 22:16:02–08 多秒 gap）/ `injection_affected` ✓ / `high_p99_latency` ✓（trip_detail a_p99 2433ms、trips/left a_p99 2694ms、trip_detail r_avg 2.2x）
- ts-route-plan-service span `high_error_rate` ✓（503 44 行 + 500 44 行 ≈ 13% of 686）/ `high_p99_latency` ✓
- 上层 cascade ts-travel-plan-service / ts-ui-dashboard `high_p99_latency` 等 ✓
- loadgenerator 端点 `timeout` ✓

causal_graph 节点核对通过。

case 2211 完毕。

---

## Case 2253 · `ts3-ts-travel-service-stress-qscl29` · JVMMemoryStress (heap, mem_type=1, 4s)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 2253 |
| GT 根因 | `ts-travel-service` |
| theme | T2_Blame-the-Messenger |
| tier | **ultra_hard** |
| baseline pred | `ts-route-plan-service` ❌ |
| v4 pred | `ts-route-plan-service` ❌ |
| baseline qpf / v4 qpf | 48 / 70 |
| 干预 | mid M6+M5 (R30) / conc M8+M3 (R69) |
| transition | wrong→wrong |

### 2. GT 注入

```
fault_type: 28 = JVMMemoryStress (JVMChaos)
mem_type: 1 (heap memory stress)
duration: 4 s
display_config:
  injection_point:
    app_name:    ts-travel-service
    class_name:  travel.service.MyCallable
    method_name: MyCallable      ← 异步 Callable 的构造方法
ground_truth:
  service:  ts-travel-service
  metric:   memory
  function: travel.service.MyCallable.MyCallable
  pod:      ts-travel-service-7f856dcb7b-n6rh6  (注入定位)
```

### 3. chaos 机制

JVMMemoryStress 用 chaosblade 在 `MyCallable` 构造方法注入 byte code，每次调用都分配/占用大块 heap memory 4 秒。`MyCallable` 是 trainticket 内部跨服务异步处理的 callable 包装器，几乎所有跨服务调用都会经过它，所以 heap stress 不是单端点而是**整个 service 范围**慢化 + GC 压力。物理副作用：

1. byte code 注入消耗 CPU → container.cpu 7.6x、pod.cpu 9x
2. heap 分配 → page_faults 3.25x、jvm.system.cpu.load_1m 3.10x
3. heap 压力触发 OOM → **restart 0→1**（典型 JVMMemoryStress + 4 秒已经够触发 OOMKilled）
4. service mesh observe 失败 → **hubble_http p50/p90/p95/p99 全 NaN**
5. trace timeline **15:08:31 → 15:09:42 出现 72 秒 gap**（chaos 4 秒 + restart cold-start + 任务积压恢复）

跟 case 2211 ContainerKill 比较：
- 同：restart 0→1、cpu 飙升、hubble NaN、cascade caller `ts-route-plan-service` vocal
- 异：JVMMemoryStress 不是物理 kill 整个 container，service 在 chaos 解除后仍能服务剩余流量；service-level avg 只 1.17x（被 chaos 后正常请求稀释），仅 endpoint p99 / max 真异常。这让 agent 用 service avg 反证 healthy 的陷阱更深。

### 4. 调用树（normal 期实测）

```
loadgenerator
  └─ ts-ui-dashboard
      ├─ ts-travel-plan-service
      │   └─ ts-route-plan-service     ← 唯一 SEVERE 服务（9 行 503 upstream connect error）
      │       ├─ ts-travel-service     ◀── GT (chaos target, silent on errors)
      │       ├─ ts-travel2-service
      │       └─ ts-route-service
      ├─ ts-travel-service             ← 也是直接 callee（ui-dashboard → travel-service）
      └─ ts-preserve-service
          └─ ts-travel-service          ← 也是直接 callee
```

ts-travel-service 直接 caller (normal):
- ts-route-plan-service 408
- ts-food-service 153
- ts-ui-dashboard 145
- ts-preserve-service 127

### 5. 沿调用链从根因到 SLO 的逐节点变化

#### chaos 直接证据（ts-travel-service）

| 信号 | normal | abnormal | ratio |
|---|---|---|---|
| **k8s.container.restarts** (max) | 0 | **1** | 0→1 ✓ |
| k8s.pod.cpu.usage | 0.169 | 1.518 | **9.00x** ✓ |
| k8s.pod.cpu_limit_utilization | 0.034 | 0.304 | **9.00x** ✓ |
| container.cpu.usage | 0.169 | 1.283 | **7.59x** ✓ |
| **k8s.pod.memory.page_faults** | 1.71e5 | 5.57e5 | **3.25x** ✓ (heap stress 标志) |
| jvm.system.cpu.load_1m | 8.45 | 26.21 | 3.10x |
| queueSize | 23.6 | 44.7 | 1.89x (callable 积压) |
| jvm.cpu.recent_utilization | 0.0012 | 0.0018 | 1.50x |
| jvm.system.cpu.utilization | 0.080 | 0.067 | 0.83x（反向，cold-start 后短暂） |
| **hubble_http p50/p90/p95/p99** | 0.033/0.252/0.434/1.112 | **NaN/NaN/NaN/NaN** | service-mesh 全失活 ✓ |
| **trace count** | 7193 | 4300 | 0.60x |
| log SEVERE | 0 | 0 | silence-as-health 陷阱 |
| trace status_code Error | 0 | **0** | silence ✓ |
| **service avg duration** | 37 ms | 43 ms | **1.17x** ← 关键迷惑信号 |
| endpoint POST /trips/left a_p99 | — | **3158 ms** | endpoint p99 才反映真异常 |

#### 上游 cascade victim（ts-route-plan-service —— Messenger）

| 信号 | normal | abnormal |
|---|---|---|
| log SEVERE | 0 | **9**（"503 upstream connect error / Connection refused"）|
| trace status_code "Error" | 0 | 27 |
| trace count | 1348 | 950 (-30%) |
| service avg duration | 171 ms | 328 ms (1.91x) |
| caller-callee edge `route-plan→travel-service` | 408 | 269 (ratio 0.659，跟全局 0.6 一致，无突出 dropout) |

#### SLO 表现（loadgenerator）

ts-ui-dashboard 端点 timeout：
- ts-travel-plan-service::POST /minStation `timeout`
- loadgenerator::HTTP POST `.../travelPlan/minStation` `timeout`
- loadgenerator::HTTP POST `.../trips/left` `timeout`

### 6. baseline 完整推理（无中间件）

baseline 跑 48 round → `ts-route-plan-service` ❌

| Round 段 | 行为 | 关键决策 |
|---|---|---|
| R1–R14 | 数据探查 + log error 排序 | ts-food-service 169 ERROR 是 chronic noise，agent 没立刻锚 |
| R22 | trace 错误分布 | "ts-route-plan-service is the only service showing Error status (500/503)" |
| R32 | log 错误内容 | 提取"503 Service Unavailable: upstream connect error" |
| R44 | 调用链分析 | "loadgenerator → ui-dashboard → travel-plan → route-plan" |
| 🔴 R45 | think_tool 决定性误锚 | "**All downstream services called by ts-route-plan-service (ts-route-service, ts-travel-service, ts-travel2-service, ts-basic-service, ts-station-service, ts-train-service) return successfully**" → 显式列出 ts-travel-service "return successfully"，silence-as-health 闭环 |
| R47 | 看 trips/left trace | "ts-ui-dashboard 503 errors on `/trips/left` don't have any downstream services in the trace" → 发现 trace 在 ui-dashboard 断（实际是 ts-travel-service callee 死掉），但 agent 解读为 "These might be separate issues or trace data is incomplete" — **完全错读** |
| FINAL R48 | commit | "ts-route-plan-service is the only service showing Error / downstream all return successfully" → ts-route-plan-service ❌ |

**baseline 失败子模式**：
1. **silence-as-health 显式版**：agent 显式列举 ts-travel-service 在"return successfully" 列表里
2. **trace 中断点 fallacy**：trace 在 ui-dashboard 断（callee 死掉的硬指纹）被解读为"trace data incomplete / separate issues"
3. **503 message provenance 误读**（同 case 2211）
4. **loud victim 锚定**（"the only service with Error status"）
5. 没查 ts-travel-service `k8s.container.restarts` / hubble / cpu / page_faults

### 7. v4 推理路径（有中间件）

v4 跑 70 round → `ts-route-plan-service` ❌

| Round 段 | 行为 | 关键决策 |
|---|---|---|
| R1–R29 | 跟 baseline 同向 | 锚定 ts-route-plan-service（27 Error spans + 503 + 唯一 SEVERE）|
| 🚨 R30 mid M6+M5 | baseline contrast + silent service | agent 真做了 normal/abnormal 对比 |
| R31–R56 | normal vs abnormal 对比 | 反向加固：normal 0 Error → abnormal 27 Error spans on ts-route-plan-service |
| R57–R64 | service-level avg 对比 | **R63 查 ts-travel-service avg：normal 37ms / abnormal 43ms / count 7193→4300** |
| 🔴 R65 think_tool 决定性误锚 | "ts-route-plan-service avg 171→328ms (nearly 2x latency!), ts-travel-service avg 37→43ms (slight increase)" → 把 1.17x 当 healthy → 加固 ts-route-plan-service | **avg-only fallacy + survivorship bias** |
| R66–R68 | 反复看 status_code Unset on travel-plan / ui-dashboard / loadgenerator | 把 callee silence 当 healthy 累加证据 |
| R69 | think_tool | "Root Cause: ts-route-plan-service - HIGH_ERROR_RATE + HIGH_LATENCY (2x increase)" |
| 🚨 R69 conc M8+M3 | counterfactual + call direction verification | advisor 询问"if X healthy → no symptom" + "call direction trace-backed?" |
| 🔴 R70 think_tool | 反向加固 | "if ts-route-plan-service healthy → ts-travel-plan-service success / ui-dashboard no cascading / loadgen no timeout" + 用 trace parent_span_id 反推证 call direction → **F5 加固** |
| FINAL R70 | commit | "ts-route-plan-service is the only service showing Error / downstream travel-service avg 仅 slight increase / call direction confirmed" → ts-route-plan-service ❌ |

**v4 干预实际效果**：
- mid M6 baseline contrast：❌ **反向加固** — normal/abnormal 对比让 27 Error spans on route-plan 反而成"实锤"，跟 case 2211 同样陷阱
- mid M5 silent service：❌ 概念命中但应用错 — agent 没把 silent on errors 的 ts-travel-service 当 chaos signature，反而当 healthy 反证
- conc M8 counterfactual：❌ **F5 反向加固** — agent 推 "if route-plan healthy → no symptom" 加固 route-plan
- conc M3 call direction：❌ 反向加固 — agent 用 trace parent_span_id 反复验证 cascade direction "route-plan → 503 → travel-plan → ui-dashboard → loadgen"，加固 cascade 中间节点 route-plan，没追到真 RC（route-plan 的 callee = travel-service）

### 8. 失败模式诊断（baseline vs v4 对比）

| 失败链 | baseline | v4 |
|---|---|---|
| 锚点切换轨迹 | 一直锚 route-plan（唯一 Error + downstream healthy 反证） | 一直锚 route-plan（baseline contrast 加固 + avg 对比加固 + counterfactual 加固） |
| 真信号查没查 | ❌ 全部没查 | ❌ 全部没查 ts-travel-service restart/hubble/cpu/page_faults |
| service avg 反证 | ❌ 没主动查 ts-travel-service avg | ❌ **查了**（37→43ms 1.17x），用作"slight increase = healthy"反证 |
| endpoint p99 看了吗 | ❌ | ❌（如查 trips/left a_p99 3158ms 就该警惕）|
| trace 中断点解读 | ❌ "data incomplete / separate issues" | ❌ 同样 |
| Connection refused target 自查 | ❌ | ❌ |

**主要失败模式**：
- F2 advisor 维度对但 reasoning 不动（baseline contrast / silent / counterfactual / call direction 全被反向加固）
- F5 conc M8 counterfactual 反向加固 + M3 call direction 反向加固
- baseline 子模式：503 message provenance 误读 + silence-as-health（显式列举版）+ avg-only fallacy + trace 中断点 fallacy + Blame-the-Messenger

跟 case 2211 同主题（cascade-caller-vocal）但**比 2211 更难**：
- 2211 ContainerKill：service 整体死，trace silence 极端，端点 p99 有信号
- 2253 JVMMemoryStress heap：service 仅短暂死掉 + 整体仍服务剩余流量，**service avg 仅 1.17x 是反向陷阱**——agent 用它反证 healthy 比 2211 还有"实测数据"支撑
- 这是 ultra_hard 的根本原因：JVMMemoryStress 在 service-level avg 上几乎不可见，必须查 endpoint distribution + container metric

### 9. 中间件如何提示能翻转

| 维度 | 触发条件 | 干预语 |
|---|---|---|
| **avg-only fallacy 反规则** | agent 用 service-level avg ratio < 1.5x 反证 X healthy | "service-level avg 在短窗口 chaos（4-30 秒）下会被 chaos 解除后的正常请求**严重稀释**，不能反证 X 健康。avg ratio 1.1-1.3x 是 survivorship bias 的典型陷阱表现。请补查：(a) endpoint 级 p95/p99 distribution（ratio 经常 > 5x） (b) endpoint 的 max（chaos 期超时往往 > 3s） (c) trace timeline 是否有秒级 gap (d) container.cpu / restart counter / page_faults。任一异常 → 推翻 healthy 判断。" |
| **endpoint p99 强模板** | service avg 看似正常但下游有 cascade 503 / SEVERE 时 | "请查每个相关 service 的 **endpoint 级 distribution**：`SELECT span_name, AVG, p50, p95, p99, MAX FROM abnormal_traces WHERE service_name = X GROUP BY span_name`。若任一端点 p99 > 1s 且 ratio > 5x，X 即可疑；avg 不能掩盖 endpoint p99。" |
| **trace 中断点正解读** | trace 在 X 服务断（X 之后没 child span）但同 endpoint 有 successful trace 走到下游 | "trace 在 X 服务断 ≠ X 是 RC 也 ≠ data incomplete。常见因果：X 调下游 callee Y 时 Y 死了，X 没收到 Y 的 response，所以 trace 没 Y 的 span。请查 X 的 callee 列表中哪个服务 hubble NaN / restart 0→1 / cpu 飙升 — 该 callee 才是真 RC。" |
| **JVMMemoryStress 三件套** | service-level avg 仅 1.1-1.3x 但 cascade 上游有 503 时 | "JVMMemoryStress / 类似 chaos 下 service avg 失真，请直接查 X：(1) `k8s.pod.cpu.usage` ratio > 5x (heap stress byte code 注入) (2) `k8s.pod.memory.page_faults` ratio > 2x (3) `k8s.container.restarts` 0→1 (heap stress 触发 OOM) (4) `hubble_http_pXX` NaN。任两个命中 → X 是 JVMChaos 真 RC。" |
| **silence-as-health 升级强模板** | agent 在 reasoning 中显式说 "X return successfully / X is healthy / X downstream healthy" | "silence on errors 是 chaos signature 而非 healthy 证明。'X return successfully' 只来自存活 trace，chaos 期死掉的请求不进 trace。强制查 X 自己的 (1) restart 0→1 (2) hubble NaN (3) container.cpu 5x+ (4) trace 是否有秒级 gap (5) page_faults 2x+。任一异常 → X 即真 RC，不是健康。" |

最有效组合：**avg-only fallacy 反规则 + JVMMemoryStress 三件套 + endpoint p99 强模板**。本 case 决定性误判发生在 R65：agent 用 ts-travel-service avg 1.17x 反证 healthy，如果有 advisor 强制查 endpoint p99（POST /trips/left a_p99 3158ms）+ container.cpu (7.59x) + restart (0→1) 任一，就能立即翻转。

### 10. 中间件代码层面问题

- **mid M6 baseline contrast 在 victim-cascade-with-avg-mask 模式下严重反向加固**：agent 用对比让 route-plan 锚定更牢；M6 应配套 "JVMChaos avg-mask 反规则" 子卡
- **mid M5 silent-service 在 silence-as-health-explicit 模式下完全失效**：agent R45 显式列出 ts-travel-service 在"return successfully"，M5 文本"silent service might be invisible rather than clean"被 agent 内化为概念但没驱动具体 SQL
- **conc M8 counterfactual + M3 call direction 联手反向加固**：M3 让 agent 用 trace parent_span_id 反复确认 cascade direction，但 cascade direction 本身不能区分 RC 是 caller 还是 callee。M3 应改为"call direction 必须从 callee 视角双向验证"
- **没有 JVMMemoryStress / JVMChaos 类卡片**：v4 卡片库目前是通用 baseline-contrast / silent-service / counterfactual，缺 chaos-type-specific 指纹卡（JVMMemoryStress / NetworkPartition / TimeSkew 等）
- **没有 leakage**

### 11. 判断

- **数据是否完整**：✅（restart 0→1、container.cpu 7.59x、pod cpu 9x、page_faults 3.25x、hubble NaN 都在 abnormal_metrics 里）
- **chaos 是否生效**：✅ 必然生效（heap stress + 4s 触发 OOM + restart）
- **真假盲区分类**：(b) 框架盲区 — agent 完全没查 ts-travel-service 自己 metric；framework 缺 "JVMChaos avg-mask 反规则" 和 "endpoint p99 强模板"
- **失败模式归纳**：F2 + F5 (M8 + M3 双干预反向加固) + 503 message provenance + silence-as-health (显式版) + **avg-only fallacy** + trace 中断点 fallacy + Blame-the-Messenger
- **给 v4.1 的提示**：
  1. **avg-only fallacy 反规则**：service-level avg ratio 1.1-1.3x 不能反证 healthy（短窗口 chaos 下 avg 失真），必须查 endpoint p95/p99 + container metric
  2. **endpoint p99 强模板**：当 cascade 有 503 / SEVERE 时强制查每个相关 service 的 endpoint 级 distribution
  3. **JVMMemoryStress / JVMChaos 类卡片**：advisor 卡片库需增加 chaos-type-specific 指纹（pod.cpu 5x+ / page_faults 2x+ / restart 0→1 = heap stress）
  4. **trace 中断点正解读**：trace 在 X 断不是 X 是 RC，是 X 的 callee 死了；advisor 应触发"查 X callee 列表的 metric"

### 12. causal_graph 正确性检验

- container|ts-travel-service `high_cpu` ✓ container.cpu 7.59x、pod cpu 9x
- pod|...-56c9999f79-vnw2w `high_cpu` ✓ / `high_memory` ✓（page_faults 3.25x，heap stress 标志）/ `high_gc_pressure` 无 jvm.gc.* 直查数据但 jvm.system.cpu.load_1m 3.10x + heap stress 注入符合 GC 压力语义 / `healthy` multi-snapshot 共存
- service|ts-travel-service `unknown` ✓
- ts-travel-service 多个 span `missing_span` ✓（trace 15:08:31 → 15:09:42 共 72 秒 gap）/ `injection_affected` ✓ / `high_p99_latency` ✓（POST /trips/left a_p99 3158ms、trips/routes a_p99 1326ms、routes/{tripId} a_p99 533ms）/ `high_avg_latency` 在多个 endpoint 上成立（POST /trips/left ratio_avg 弱但 endpoint p99 强）
- ts-route-plan-service span `high_error_rate` ✓（503 + 500 共 27 Error spans）/ `high_p99_latency` + `high_avg_latency` ✓（service avg 1.91x）
- 上层 cascade ts-travel-plan-service / ts-ui-dashboard `high_p99_latency` 等 ✓
- loadgenerator 端点 `timeout` ✓（trips/left + minStation 端点）

causal_graph 节点核对通过。

case 2253 完毕。

---

## Case 2258 · `ts3-ts-travel2-service-container-kill-vt4nvr` · ContainerKill (4s)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 2258 |
| GT 根因 | `ts-travel2-service` |
| theme | T2_Blame-the-Messenger |
| tier | **ultra_hard** |
| baseline pred | `ts-route-plan-service` ❌ |
| v4 pred | `ts-route-plan-service` ❌ |
| baseline qpf / v4 qpf | 60 / 75 |
| 干预 | mid M6+M5 (R30) / conc M8+M3 (R56，**中文卡片**) |
| transition | wrong→wrong |

### 2. GT 注入

```
fault_type: 2 = ContainerKill (PodChaos)
duration: 4 s
display_config:
  injection_point:
    app_label:      ts-travel2-service
    container_name: ts-travel2-service
    pod_name:       ts-travel2-service-79fb6f545d-ndlnv (注入定位)
ground_truth:
  container/service: ts-travel2-service
  pod:               ts-travel2-service-79fb6f545d-b8pk9 (注入后实际 pod)
```

### 3. chaos 机制

ContainerKill 把 `ts-travel2-service` container 杀 4 秒。trainticket 同时存在 `ts-travel-service` 和 `ts-travel2-service` 两个相似但独立的服务（处理不同的 Trip 数据集），两个都被高频调用。chaos 打 ts-travel2-service 时：

1. service mesh 完全失活：hubble_http p50/p90/p95/p99 全 NaN
2. byte code cold-start：jvm.system.cpu.load_1m **9.40x**（比 case 1948/2211 都更猛）+ container.cpu **6.54x**
3. **restart 0→1** ✓
4. 整个 service 死掉 4 秒 → trace count 5106→2527（**0.50x 严重 dropout**）
5. cascade 上游 ts-route-plan-service 报 64 行 SEVERE "503 upstream connect error"（比 case 2253 的 9 行更 vocal，比 case 2211 的 44 行还多 → 这次 chaos 期间 cascade 暴露的请求数最多）

跟 case 2211（同 ContainerKill）的核心差异是：
- 2258 service avg ratio **2.53x**（不像 2211 弱信号）— 但 **avg 排名**里 ts-travel-plan-service 3.39x、ts-route-plan-service 2.65x 反而更高 → agent 把 ts-travel-plan / ts-route-plan 当 RC 候选
- 2258 trace count drop 0.50x，但全 cascade 都 ~0.5x（chaos 期 cascade 整体丢一半 trace）— ts-travel2-service 自己不突出

### 4. 调用树（normal 期实测）

```
loadgenerator
  └─ ts-ui-dashboard
      ├─ ts-travel-plan-service
      │   └─ ts-route-plan-service     ← 唯一 SEVERE 服务（64 行 503）
      │       ├─ ts-travel2-service    ◀── GT (chaos target, silent on errors)
      │       ├─ ts-travel-service
      │       └─ ts-route-service
      ├─ ts-travel2-service             ← 也是直接 callee
      └─ ts-travel-service              ← 同样直接 callee
```

### 5. 沿调用链从根因到 SLO 的逐节点变化

#### chaos 直接证据（ts-travel2-service）

| 信号 | normal | abnormal | ratio |
|---|---|---|---|
| **k8s.container.restarts** (max) | 0 | **1** | 0→1 ✓ |
| **jvm.system.cpu.load_1m** | 18.48 | 173.71 | **9.40x** ✓ |
| **jvm.system.cpu.utilization** | 0.057 | 0.391 | **6.92x** ✓ |
| **container.cpu.usage** | 0.113 | 0.740 | **6.54x** ✓ |
| k8s.pod.cpu.usage | 0.116 | 0.698 | 6.01x |
| k8s.pod.cpu_limit_utilization | 0.023 | 0.140 | 6.01x |
| k8s.pod.memory.page_faults | 1.70e5 | 2.98e5 | 1.75x |
| **hubble_http p50/p90/p95/p99** | 0.039/0.138/0.204/0.182 | **NaN/NaN/NaN/NaN** | service-mesh 全失活 ✓ |
| trace count | 5106 | 2527 | **0.50x** |
| log SEVERE | 0 | 0 | silence-as-health 陷阱 |
| service avg duration | 23.7 ms | 60.0 ms | **2.53x** ← avg 信号比 2253 强 |

#### 上游 cascade victim（ts-route-plan-service —— Messenger）

| 信号 | normal | abnormal |
|---|---|---|
| log SEVERE | 0 | **64**（"503 upstream connect error / Connection refused"，全部同质） |
| trace status_code "Error" | 0 | **192**（baseline 锚的"highest among all services"）|
| service avg duration | 115 ms | 305 ms (2.65x) |
| trace count | 1662 | 1162 (-30%) |

#### SLO 表现（loadgenerator）

ts-ui-dashboard 多个端点 503/timeout：
- POST `/travelPlan/cheapest` `timeout`
- POST `/travelPlan/minStation` `timeout`
- POST `/travel2service/trips/left` `timeout`

### 6. baseline 完整推理（无中间件）

baseline 跑 60 round → `ts-route-plan-service` ❌

| Round 段 | 行为 | 关键决策 |
|---|---|---|
| R1–R10 | 数据探查 | 从 incident 描述拿到受影响 endpoint 列表 |
| R23 | trace 错误分布 | "ts-route-plan-service: 192 errors (highest)" |
| R30 | trace `571fd5...` 调用链 | "loadgenerator → ui-dashboard → travel-plan → route-plan" |
| 🔴 R55 | trace 中断点正解读失败 | 看 `/travel2service/trips/left` trace："ts-travel2-service shows Unset status with 200 → working correctly" — silence-as-health |
| R56 | 锚定加固 | "ts-route-plan-service is the only service generating Error status responses" |
| R59 | first-error timestamp | route-plan 04:25:00.485 < travel-plan 04:25:33 → 锚定 |
| FINAL R60 | commit | "192 Error spans + 64 SEVERE 503 + first-to-fail" → ts-route-plan-service ❌ |

**baseline 失败子模式**：同 case 2211 / 2253 同主题
1. **503 message provenance 误读**
2. **first-error timestamp fallacy**
3. **silence-as-health**：ts-travel2-service trace Unset → 当 healthy
4. **loud victim 锚定**（192 Error spans）
5. 没查 ts-travel2-service `k8s.container.restarts` / hubble / cpu

### 7. v4 推理路径（有中间件）

v4 跑 75 round → `ts-route-plan-service` ❌

| Round 段 | 行为 | 关键决策 |
|---|---|---|
| R1–R29 | 跟 baseline 同向 | 锚 ts-route-plan-service（192 Error + 64 SEVERE 503） |
| 🚨 R30 mid M6+M5 | baseline contrast + silent service | agent_response_excerpt **(empty)** — agent 没立即 reflect 干预，直接跳到 SQL |
| R31–R55 | normal/abnormal 对比 | 反向加固：normal 0 Error → abnormal 192 Error spans on route-plan |
| R56 think_tool | "Root Cause: ts-route-plan-service" |
| 🚨 R56 conc M8+M3（**中文卡片**）| counterfactual + call direction verification | advisor 中文版："如果你的候选服务完全健康，你观察到的其他异常还会发生吗？...时间相近不等于因果方向已确定" |
| R57–R68 | counterfactual + call direction | agent 用 trace parent_span_id 反复确认 cascade direction，加固 route-plan |
| R69 query | 查 trace `d2716ad59b6eddabbdb917080d968e85` | **关键发现**：loadgen → ui-dashboard (Error) → **没有 ts-travel2-service span!** |
| 🟡 R70 think_tool | "**This is a critical finding!** ... NO ts-travel2-service span in this trace! loadgenerator → ts-ui-dashboard → (nothing further)" — agent 注意到 trace 中断点 |
| R71 query | 查 ts-travel2-service `k8s.deployment.available` → **1.0**（错 metric，不能反映 chaos）|
| R72 query | 查 ts-travel2-service `k8s.container.ready` → 空 |
| 🔴 R73 query | **`WHERE service_name='ts-travel2-service' AND metric LIKE '%restart%'`** → **空结果！** 关键: trainticket 数据里 `k8s.container.restarts` 的 `service_name` 字段是**空字符串**（不是服务名），必须用 `attr.k8s.pod.name LIKE 'ts-travel2-service%'` 过滤。agent 用 service_name 过滤 → 空 → 误判该服务"无 restart 记录" |
| R74 query | 查 ts-travel2-service log "Connection / refused / timeout" → 空（合理：callee 死了不会自己 log，但 agent 解读为"无 infrastructure failures"） |
| 🔴 R75 think_tool | "metrics show ts-travel2-service has k8s.deployment.available = 1.0 → deployment is available. No connection/refused/timeout errors in logs. **However, the trace evidence is compelling**" → 用错 metric (deployment.available) + 错 SQL（restart LIKE 空）反证 healthy → 加固 route-plan |
| FINAL R75 | commit | "192 Error spans + 64 SEVERE 503 + Connection refused 起源 + ts-travel2-service appears available" → ts-route-plan-service ❌ |

**v4 干预实际效果**：
- mid M6 baseline contrast：❌ **反向加固**（同 2211 / 2253）
- mid M5 silent service：❌ 概念命中但 agent 没把 ts-travel2-service silence 当 chaos signature
- conc M8+M3（中文版）：⭐ **部分起作用** — agent **真的去查了 ts-travel2-service 自己的 metric**（R71-R74），是这次 4 个 case 里**唯一一次** agent 主动 callee-side check
- 但 conc M8 致命缺陷：**没给 specific SQL 模板** → agent 用错 metric (deployment.available) + 错 schema (service_name 过滤 restart counter 失败) → 反向加固原锚定

### 8. 失败模式诊断（baseline vs v4 对比）

| 失败链 | baseline | v4 |
|---|---|---|
| 锚点切换轨迹 | 一直锚 route-plan | 一直锚 route-plan，但 R69-R74 一度怀疑 ts-travel2-service |
| trace 中断点解读 | ❌ "Unset = working correctly" | 🟡 注意到中断点（"NO ts-travel2-service span"），但用错 metric 反证 healthy |
| callee-side metric 自查 | ❌ 完全没查 | ✅ **真去查了 4 个 metric** (deployment.available / container.ready / restart LIKE / log Connection) |
| restart counter | ❌ 没查 | 🔴 **schema 知识缺失**：用 `service_name='ts-travel2-service' AND metric LIKE '%restart%'` 查（service_name 字段为空字符串，正确做法是 `attr.k8s.pod.name LIKE 'ts-travel2-service%'`） |
| container.cpu / hubble | ❌ 没查 | ❌ 没查（advisor 没指引） |

**主要失败模式**：
- F2 advisor 维度对但 reasoning 不动（mid M6 反向加固）
- F2 升级版 — **F2-schema-blind**：conc M8 让 agent 真去 callee-side 查，但 schema 知识缺失 + advisor 没给具体 SQL 模板 → agent 查不到关键 metric → 反向加固
- F5 conc M3 call direction 反向加固
- baseline 子模式：503 message provenance + first-error fallacy + silence-as-health + Blame-the-Messenger + trace 中断点 fallacy

跟 case 1948 / 2211 / 2253 都相关：
- 跟 1948 同 ContainerKill 但 1948 agent 至少看到 restart 0→1（用错 anchor 视角）；2258 agent 因为 schema 错完全没看到
- 跟 2211 同 cascade-caller-vocal 但 2258 v4 主动 callee-side 查（只因 SQL 错）
- 跟 2253 同 ultra_hard 但 2253 是 avg-mask，2258 是 trace 中断点信号被错读 + restart SQL schema 错

### 9. 中间件如何提示能翻转

| 维度 | 触发条件 | 干预语 |
|---|---|---|
| **restart counter SQL schema 强模板** | 任何时候 agent 想查 restart counter | "trainticket 数据里 `k8s.container.restarts` 的 `service_name` 字段是**空字符串**（k8s metadata 把 restarts 当 container-level 而非 service-level）。**禁止**用 `WHERE service_name='X'` 过滤；必须用：`SELECT attr.k8s.pod.name, MAX(value) FROM abnormal_metrics WHERE \"attr.k8s.pod.name\" LIKE 'X%' AND metric='k8s.container.restarts' GROUP BY 1`。同样原则适用于 hubble_http_pXX、k8s.deployment.* 等 cluster-level metric。" |
| **callee-side specific metric 强 SQL 模板** | conc M8 触发 callee-side check 时 | "callee 健康验证必须查这 4 个 specific metric（不要用 LIKE 模糊匹配，**逐个具体名字**直查）：(1) `metric='container.cpu.usage'` 看 ratio （2） `metric='k8s.pod.memory.page_faults'` 看 ratio （3） `metric='k8s.container.restarts'` 用 attr.k8s.pod.name 过滤 （4） `metric LIKE 'hubble_http%' AND value IS NULL OR ISNAN(value)` 看 NaN 数。任两个异常 → callee 是真 RC。" |
| **deployment.available 反规则** | agent 用 `k8s.deployment.available=1.0` 反证服务 healthy | "`k8s.deployment.available=1.0` 仅表示 deployment 控制器仍在线（该有的 pod 数已被调度），**不反映 container 内部的 chaos 状态**。短窗口 chaos 解除后 pod 一般还在跑，deployment.available 永远是 1.0。请用 container.cpu.usage 短期飙升 + restart 0→1 + hubble NaN 三件套替代该判据。" |
| **trace 中断点 + callee metric 联动** | trace 在 X 服务断（X 之后没 child span）时 | "trace 在 X 断 = X 调下游 callee Y 失败。立即查 X 的所有 callee 的 `attr.k8s.pod.name LIKE '<callee>%' AND metric='k8s.container.restarts'`（不用 service_name 过滤）+ `service_name='<callee>' AND metric='container.cpu.usage'`。任一异常的 callee 即真 RC。" |
| **callee 端 log 'Connection refused' 反规则** | agent 用 callee X 的 log 无 'Connection / refused / timeout' 反证 X healthy | "callee 自己死掉时**永远不会** log 'Connection refused'（它根本没收到请求所以无法 log）。'Connection refused' 只来自 caller 端（caller 在 socket 层失败时才 log）。callee log 无该 keyword 是 chaos 必然现象，不能反证 callee healthy。请改查 callee 的 container.cpu / restart / hubble。" |

最有效组合：**restart counter SQL schema 强模板 + callee-side specific metric 强 SQL 模板**。本 case agent 已经主动到 R71-R74 callee-side check 阶段，缺的是 advisor 给具体 metric 名 + 正确过滤字段。

### 10. 中间件代码层面问题

- **conc M8 给概念但不给 SQL**：M8 描述"if X healthy → no symptom"是抽象概念，本 case agent 真去做 callee-side check 但用错 metric (deployment.available)。M8 必须配套**具体 metric 清单 + 正确过滤字段**
- **mid M6 baseline contrast 在 cascade-caller-vocal 模式下三连反向加固（2211/2253/2258）**：M6 应配套"victim-cascade detection"子规则——若 abnormal Error spans 集中在一个 service 但其下游 silence on errors，强制查下游 callee metric
- **mid M5 silent-service 文本无效（4/4 case 全失败）**：M5 概念全部被 agent 内化为"找 NEW errors 的服务"，没驱动具体 SQL。M5 应触发硬模板"对每个 silent on errors 的服务运行 callee-side specific metric SQL"
- **conc M3 call direction 反向加固**：trace parent_span_id 验证 cascade direction 不能区分 RC 是 caller 还是 callee。M3 应改为"call direction 必须从 callee 视角双向验证：cascade 中每个节点都做 if-callee-healthy 反推"
- **mid 干预 agent_response_excerpt empty 缺乏强制 acknowledge**：本 case mid 后 agent 直接跳到 SQL 没 reflect 干预内容；中间件应有机制确保 agent 复述干预 + 计划具体 SQL
- **中文卡片混用**：conc M8+M3 是中文，mid M6+M5 是英文。混用让效果难评估
- **没有 leakage**

### 11. 判断

- **数据是否完整**：✅（restart 0→1、container.cpu 6.54x、jvm cpu 9.40x、hubble NaN 都在 abnormal_metrics 里）
- **chaos 是否生效**：✅ 必然生效（ContainerKill 物理 kill）
- **真假盲区分类**：(b) 框架盲区 + **(d) 中间件代码问题**（conc M8 让 agent 主动 callee-side check 但缺 SQL schema 知识 → schema-blind 反向加固）
- **失败模式归纳**：F2 升级版 (F2-schema-blind) + F5 + 503 message provenance + first-error fallacy + silence-as-health + trace 中断点 fallacy + Blame-the-Messenger + **deployment.available fallacy**
- **给 v4.1 的提示**：
  1. **restart counter SQL schema 强模板**：明确告诉 agent `k8s.container.restarts` 必须用 `attr.k8s.pod.name` 过滤，不是 service_name
  2. **callee-side specific metric 强 SQL 模板**：列出 4 个 metric（container.cpu / page_faults / restarts / hubble_http）+ 正确过滤字段
  3. **deployment.available 反规则**：避免 agent 用 deployment.available=1.0 反证 healthy
  4. **callee log 'Connection refused' 反规则**：callee 自己永远不会 log connection refused（没收到请求）
  5. **trace 中断点 + callee metric 联动**：trace 在 X 断 → 查 X 的 callee restart/cpu/hubble

### 12. causal_graph 正确性检验

- container|ts-travel2-service `high_cpu` ✓ container.cpu 6.54x
- pod|...-8557fd66df-kvg4k `high_cpu` ✓ / `high_memory` 弱（page_faults 1.75x、memory.available 1.04x，同列次要不算错）/ `high_gc_pressure` 无 jvm.gc.* 直查数据但 jvm.system.cpu.load_1m 9.40x 暗示 GC 压力 / `healthy` multi-snapshot 共存
- service|ts-travel2-service `unknown` ✓
- 多个 ts-travel2-service span `missing_span` ✓ / `injection_affected` ✓ / `high_avg_latency` ✓ (service avg 2.53x) / `high_p99_latency` ✓
- ts-route-plan-service / ts-travel-plan-service span `high_error_rate` ✓（503 + 500 错误集中在 routePlan/cheapest, /minStopStations, travelPlan/cheapest, travelPlan/minStation）
- 上层 cascade ts-ui-dashboard span `high_p99_latency` + 部分 `timeout` ✓
- loadgenerator 端点 `timeout` ✓（cheapest / minStation / trip2/trips/left）

causal_graph 节点核对通过。

case 2258 完毕。

---

## Case 2713 · `ts4-ts-security-service-stress-2q5qsb` · JVMMemoryStress (mem_type=1, SecurityServiceImpl.deleteSecurityConfig)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 2713 |
| GT | `ts-security-service` |
| theme / tier | T3_Noise-Anchor / stable |
| baseline pred | `ts-food-service` ❌ (qpf=82) |
| v4 pred | `ts-order-service` ❌ (qpf=61) |
| 干预 | mid M6+M5 @ R30 / conc M8+M3 @ R53 |
| transition | wrong → wrong |

### 2. GT 注入

```
fault_type: 28 = JVMMemoryStress
display_config:
  app_name: ts-security-service
  injection_point: security.service.SecurityServiceImpl.deleteSecurityConfig
  mem_type: 1  # heap memory
ground_truth.service: [ts-security-service]
ground_truth.pod:     [ts-security-service-6ccc7f574d-84jr4]  (注：causal_graph 记录 5fbb5c757b-f8s94，旧 pod)
ground_truth.metric:  [memory]
```

### 3. chaos 机制

`deleteSecurityConfig` 属于 admin/cleanup 路径，但 chaosblade JVM agent attach 时的 byte code 注入会污染整个 class loader 让所有 method 都受 GC pressure 影响。物理验证（duckdb 直查）：

- container.cpu.usage **51.6x**（0.05 → 2.58）—— 孤立 outlier，第二名 ts-train-food-service 仅 2.35x
- k8s.pod.cpu.usage **45.93x**, jvm.cpu.recent_utilization **32.84x**
- k8s.container.restarts: normal MAX=0 → abnormal MAX=1（in-place restart，pod 名 `5fbb5c757b-f8s94` 不变）
- container.memory.usage / rss / working_set **0.83-0.85x**（abnormal 期反而下降——heap stress 触发频繁 GC，RSS 被释放；这是 mem_type=1 区别于 OOM 的指纹）
- k8s.pod.memory.page_faults **3.33x** —— GC 频繁触发的次级证据

JVMMemoryStress (heap) 必然生效（trace count 1140 → 662，-42%；端点 avg 5.14x）。

### 4. 调用树（normal 期实测）

```
loadgen → ts-ui-dashboard (POST /api/v1/preserveservice/preserve)
  └─ ts-preserve-service (PreserveController.preserve)
      └─ ts-security-service (GET /api/v1/securityservice/securityConfigs/{accountId})  ◀── GT
          ├─ self (SELECT SecurityConfig / SecurityRepository.findByName)
          └─ ts-order-service / ts-order-other-service (GET .../order/security/...)  ← callee
```

duckdb 验证：normal 中 ts-preserve-service 调 ts-security-service 114 次；ts-security-service 调 ts-order-service 114 次。**v4 锚定的 ts-order-service 是 GT 的下游 callee**——cascade 方向反了。

### 5. 关键 duckdb 证据

#### GT (ts-security-service) 指纹

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| **container.cpu.usage** | 0.05 | 2.58 | **51.6x** ⭐ 孤立 outlier |
| **k8s.pod.cpu.usage** | 0.053 | 2.44 | **45.93x** |
| jvm.cpu.recent_utilization | 0.0004 | 0.0139 | 32.84x |
| jvm.system.cpu.utilization | 0.244 | 0.460 | 1.89x |
| k8s.pod.memory.page_faults | 159711 | 532614 | 3.33x |
| **k8s.container.restarts (pod-level)** | 0 | 1 | **0→1** in-place |
| container.memory.rss | 7.42e8 | 6.27e8 | **0.85x** GC reclaim |
| trace count | 1140 | 662 | **0.58x** 减半 |
| service avg duration (ms) | 12.3 | 63.0 | **5.14x** |
| trace status_code Error | 0 | 0 | **silent on errors** |
| log SEVERE | 0 | 0 | silent |

#### GT 端点级 duration distribution

| span_name | n_p50 | a_p50 | n_p99 | a_p99 | avg_ratio |
|---|---|---|---|---|---|
| GET /api/v1/securityservice/securityConfigs/{accountId} | 24.8 | 28.8 | **551** | **6914** | **5.35x** |
| SecurityController.check | 20.3 | 21.6 | 425 | **5048** | 4.88x |
| SecurityRepository.findByName | 2.0 | 2.3 | 12.8 | 64.3 | **17.94x** |
| SELECT SecurityConfig | 1.6 | 1.8 | 11.7 | 60.4 | **21.06x** |

p50 几乎不变（OK 路径仍然快），p99 飙到 5-7 秒（OOM/GC 窗口请求被卡）；avg_ratio 在 DB 层 21x 极端。

#### baseline 锚 ts-food-service

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| jvm.system.cpu.load_1m | 59.3 | 80.6 | 1.36x（cluster effect）|
| container.cpu | - | - | 未在 top 列表（< 1.4x）|
| **'Get the Get Food Request Failed' SEVERE** | **261** | **211** | **0.81x（chronic, abnormal 反而少）** |
| 'UnknownHostException: ts-rabbitmq' | 多 | 多 | chronic（baseline agent 自己也确认）|

#### v4 锚 ts-order-service

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| jvm.system.cpu.load_1m | 64.0 | 80.6 | 1.26x（cluster effect）|
| container.cpu | - | - | 未在 top（< 1.2x）|
| 'Order already exists' SEVERE | **63** | **52** | **0.83x（chronic, abnormal 反而少）** |
| service avg duration | 5.4 | 5.5 | **1.02x** 完全无变化 |

#### 全局 container.cpu.usage ratio（孤立性）

```
ts-security-service       51.60  ⭐ 唯一极端 outlier
ts-train-food-service      2.35
ts-inside-payment-service  2.11
ts-travel-plan-service     2.04
... 其余全 < 1.5x
```

第二名只有 2.35x，跟 GT 差 22 倍——这是教科书级 service-specific 信号。

#### 全局 503 / Connection refused 分布

```
ts-seat-service       2132  ← cascade 远端 victim
ts-ui-dashboard        134  ← SLO 末端
ts-preserve-service     40
```

ts-security-service 自己 0 个 503——**silent on errors**，但 trace count -42% + p99 12.5x 是真信号。

### 6. baseline 推理（82 round → ts-food-service ❌）

| Round 段 | 行为 |
|---|---|
| R1-R3 | log scan → 看到 ts-food-service 211 SEVERE "Get Food Request Failed" 高频 → 锚定 ts-food-service |
| R4-R5 | trace 看到 loadgen → ui-dashboard → preserve → order chain，开始转向 ts-order-service |
| R6-R7 | normal trace 也是 preserve → order，但开始锚 "Order already exists" |
| 🔴 R7 think 锚定 | "ts-order-service errors at 19:39:49.541, ts-preserve-service at 19:39:49.558 — 17ms 后" → **first-error timestamp fallacy**，锚 ts-order-service |
| R8-R9 | 但又看到 ts-food-service rabbitmq UnknownHostException 19:39:48.903 比 order 19:39:49.541 早 638ms → 切回 ts-food-service |
| R9 think | **chronic check 自己做了**："Normal logs 261, Abnormal 211. RabbitMQ errors are chronic, NOT incident-related" —— 但**矛盾地继续把 ts-food-service 当 RC** |
| R10-R30 | 反复 toggle ts-food / ts-order，最终回到 first-error timestamp 加固 |
| R82 final | commit `ts-food-service` ❌ |

**baseline 失败子模式**：
1. **first-error timestamp fallacy**：用 timeline 最早 SEVERE 推 RC（实际最早的就是 chronic noise）
2. **chronic noise 锚定**：自己 chronic check 都做了（normal 261 > abnormal 211 ratio 0.81x）仍然把它当 RC——chronic 排除规则没真正"acted on"
3. **silence-as-health**：ts-security-service 0 SEVERE → 完全没出现在候选名单中（agent 全程没查它）
4. **没查 specific metric**：integer 没有任何 query 涉及 container.cpu / k8s.container.restarts
5. **trace count 减半的服务没扫**：ts-security-service trace count 1140 → 662 (-42%) 是清晰信号但未被发现

### 7. v4 推理（61 round → ts-order-service ❌）

| Round 段 | 行为 |
|---|---|
| R1-R30 | 跟 baseline 类似：error count + first-error timestamp 锚 ts-order-service |
| 🚨 R30 mid M6+M5 | "baseline 对比 + silence ≠ health"。excerpt: "Critical Comparison Normal vs Abnormal" |
| R31 think 复述 | excerpt 详列 ERROR count diff: ts-preserve-service 0→117, ui-dashboard 0→39, loadgen 0→39, order "Order already exists" both periods → "chronic" → **执行了 baseline 对比但只对 ERROR count 维度**，没扩展到 trace count / duration / specific metric |
| R31-R47 | 围着 ts-preserve-service / ts-order-service / "Order already exists" 兜圈，反复查 trace span 关系 |
| R48 think | 试图理解 trace 中 missing span_id `361be4e88949deec` —— **这是 ts-security-service 的 GET span**（causal_graph 标 missing_span），但 agent 没把它跟 chaos 联系 |
| R49-R52 | 终于查 metric！但只查 `ts-order-service` (anchor-driven) + `queueSize`（RabbitMQ 维度）→ 没异常 |
| R53 think 总结 | 锁死 ts-order-service：first-error timestamp + Same OrderId → "definitive causality" |
| 🚨 R53 conc M8+M3 | "counterfactual + parent-child trace evidence"，excerpt 空 |
| R54-R60 | 跑了 trace span 关系（看了 missing span 361be4e88949deec 但**没查 service_name = '361be4e88949deec' 的来源**）|
| R61 think | excerpt: "Counterfactual: 如果 ts-order-service healthy, log timestamps 仍然 17ms order-first → causality 站立"——**反向加固**，没真正测试 candidate 健康假设 |
| R61 final | commit `ts-order-service` ❌ |

**v4 干预实际效果**：
- mid M6 baseline 对比 ⚠️ 部分执行（ERROR count 维度对比正确——发现 chronic）→ 但 anchor 没动，反而从 food → order 横切（依然在 cascade victim 群里）
- mid M5 silent service ❌ **没生效**——agent 认 silent = "ts-security-service 没 SEVERE = healthy"，没有反向"该出现却消失"的机制
- conc M8 counterfactual ❌ **反向加固**——agent 把 timestamp 17ms 当作 counterfactual 站立证据
- conc M3 secondary ❌ 几乎没生效

### 8. 失败模式

| 失败链 | baseline | v4 |
|---|---|---|
| chronic noise 锚定 | ❌ food rabbitmq | (mid 已经 dismissed food，但切到 order 仍是 chronic) |
| first-error timestamp fallacy | ❌ food 19:39:48 最早 | ❌ order 比 preserve 早 17ms |
| silence-as-health | ❌ GT silent on errors 完全没扫 | ❌ 同 + conc 后强化（"only candidate with timestamp evidence"）|
| 没查 specific metric | ❌ container.cpu / restart 全没查 | ❌ 仅查 anchor 自己的 metric (queueSize)，没全局扫 |
| trace count 减半未扫 | ❌ | ❌ ts-security-service count 1140→662 全程 invisible |
| F1 维度选错 | - | ⚠️ M6+M5 维度对（baseline + silence）但 sec=M5 没强制 silent service ranking |
| F2 confirmation bias | - | ❌ 复述 baseline 对比但 anchor 不动 |
| F4 cascade 选错位置 | - | ❌ 锚 GT 的 callee（ts-order-service 是 ts-security-service 的下游）|
| F5 conc 反向加固 | - | ❌ counterfactual 被 timestamp ordering 反向加固 |
| missing span 不疑 chaos | - | ❌ R48 看到 missing span_id 但没怀疑 chaos 副作用 |

主要失败模式：
- baseline：**chronic noise 锚定 + first-error timestamp fallacy + silence-as-health**（GT silent on errors 永不进候选名单）
- v4：**F2 confirmation bias**（mid baseline 对比仅做 ERROR count 子集，没扩展到 trace count / duration / specific metric）+ **F4 cascade 选错位置**（callee 方向：ts-order-service 是 GT 下游）+ **F5 conc 反向加固**（timestamp 17ms 当 counterfactual 站立证据）

跟 case 1218/1459/1495 共同点：JVMMemoryStress + silence-as-health + 没查 specific metric。差别：1218/1459 是 caller 方向锚定（messenger 模式），1495 是 callee 方向（unique Error span 陷阱），2713 也是 callee 方向但靠 first-error timestamp ordering。

### 9. 中间件如何提示能翻转

需要的 advisor 维度：
- **trace count -X% 排序**（新维度，case 2713 暴露）：在 baseline 对比阶段强制查 service-level trace count 比 ratio——ts-security-service 1140→662 (-42%) 立即定位（没出现在传统 ERROR 排名）
- **specific metric 强制 SQL 模板**（case 33/1495 已记 + 2713 加强）：必须查 *全局* container.cpu / k8s.container.restarts ratio 排序，而不是只查 anchor 自己——一条 `WITH n AS (SELECT service_name, AVG(value) FROM normal_metrics WHERE metric='container.cpu.usage' GROUP BY 1), a AS (...) SELECT service_name, ratio ORDER BY ratio DESC` 立即看到 ts-security-service 51.6x 孤立 outlier
- **全局 restart counter 扫描**（case 33/1495 已记 + 2713 加强）：incident-onset restart 0→1 的 pod 是最强 GT 指纹之一
- **first-error timestamp fallacy 警告**（case 1218 已记 + 2713 加强）：advisor 看到 agent 用 timestamp ordering 推 RC 时强制反例——"timestamp ordering 不构成 causality，需要 trace parent-child + GT 服务自身 specific metric ratio 验证"
- **callee verification commit-gate**（case 156 已记 + 2713 强化）：candidate 提名前强制查"如果 candidate 是 RC，它的 container.cpu / restart 是否升高"——ts-order-service container.cpu < 1.2x 就否决
- **missing span 当 chaos 副作用**（新维度，case 2713 暴露）：trace span chain 中 parent_span_id 找不到来源时，怀疑该 span 来自 missing/损坏的服务（chaos 让 span export 失败的指纹）
- **chronic check 强制 dismiss**（case 33/784 已记 + 2713 加强）：ratio < 1.0 的 SEVERE 必须从候选名单移除——agent 自己看到 ratio 0.81x 仍当 RC 是认知盲点

最有效组合：**全局 container.cpu ratio 排序 + 全局 restart counter 扫描** —— 两条 SQL 在 mid 阶段强制执行就能命中 51.6x outlier + 0→1 restart pod，case 2713 直接翻盘。

### 10. 中间件代码层面问题

- mid M6 baseline 对比 advisor 文本只说"compare normal vs abnormal"——agent 仅按 ERROR count 维度对比（部分对，发现 food chronic），但**没引导查 trace count diff / service-level duration ratio / container.cpu metric**，advisor 缺少 SQL 模板硬规则
- mid M5 silent service 文本概念正确（"silence ≠ health"）但**完全没触发**——advisor 没给"找全局 trace count 减半的服务"或"normal 里出现 abnormal 里消失的服务"SQL 模板，agent 把"silent on errors" 反向解释为 ts-preserve / ts-order 的潜在问题，跟 GT (ts-security) 无关
- conc M8 counterfactual 文本笼统——agent 把 17ms timestamp 当 counterfactual 站立，advisor 缺少**"timestamp ordering ≠ causality"硬规则 + callee specific metric 强制验证**
- conc M3 secondary（trace parent-child）触发了但 agent 看 missing span 不疑 chaos——advisor 缺少"missing span_id 来源 = 可能 chaos affected service"硬规则
- 61 round 干预次数足够但**全程没查 ts-security-service 任何维度**——v4 advisor 缺少"任何 service 都该被纳入候选名单"硬规则（silence-as-candidate-blackhole）
- post_intervention_tool_rounds=23（mid 后）+ 8（conc 后）说明 agent 听话执行，但**维度执行偏 narrow**（仅 ERROR count + trace span chain），需要 prescriptive SQL 而非 descriptive prompt

### 11. 判断

- 数据完整性：✅
- chaos 生效：✅ 必然生效（container.cpu 51.6x + restart 0→1 + p99 12.5x）
- 盲区类型：**(b) 框架盲区**（GT silent on errors → 永不进候选 + chronic check 不真正 act + 没查 specific metric）
- 失败模式：baseline = first-error timestamp fallacy + chronic noise 锚定（自己看到 chronic 仍锚） + silence-as-health；v4 = **F2 confirmation bias**（baseline 对比仅 ERROR count）+ **F4 callee 方向锚定** + **F5 conc 反向加固**（17ms 当 causality 站立）
- 给 v4.1：(1) **mid 强制全局 container.cpu / restart ratio 排序**——SQL 模板硬规则，扫出 51.6x 孤立 outlier；(2) **silence-as-candidate 反例**——agent 列候选必须包含"没 SEVERE 但 trace count 减半"服务；(3) **first-error timestamp 警告 + callee specific metric commit-gate**——agent 用 timestamp ordering 时强制反例 "callee container.cpu 是否升高"；(4) **missing span 当 chaos 副作用**——trace 中 parent_span_id 来源 missing 时怀疑 chaos affected service；(5) **chronic check act-on 强制**——ratio < 1.0 的 SEVERE 必须从候选移除（agent 自己确认 chronic 仍锚是 act-on 失败）

### 12. causal_graph 正确性检验

✅ **节点核对通过**：
- container|ts-security-service `[high_cpu, restarting]` → high_cpu ✅ (51.6x), restarting ✅ (k8s.container.restarts 0→1)
- pod|ts-security-service-5fbb5c757b-f8s94 `[high_http_latency, high_cpu, high_gc_pressure, healthy]` → high_http_latency ✅ (端点 p99 12.5x), high_cpu ✅ (jvm 32.84x), high_gc_pressure ✅ (page_faults 3.33x + RSS 0.85x GC reclaim 间接证据), healthy 多时刻合并不算错标
- span 层 GET securityConfigs / SecurityController.check / SecurityRepository.findByName / SELECT SecurityConfig 全部 high_avg_latency / high_p99_latency 跟实测 (ratio 5-21x, p99 60-7000ms) 一致
- cascade 节点 ts-preserve-service / ts-ui-dashboard / loadgenerator high_error_rate ✅ (37.9% error rate)
- 跟 case 1218/1459 不同，本案 causal_graph 没把 high_memory 误标为主导（mem_type=1 实际表现是 cpu 主导，causal_graph 也只标 high_cpu+restarting，正确反映 byte code 注入的 cpu 副作用 + restart 0→1 物理结果）

case 2713 完毕。

---

## Case 3760 · `ts0-ts-price-service-stress-n787pd` · JVMMemoryStress (mem_type=2 direct memory, PriceController.query)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 3760 |
| GT | `ts-price-service` |
| theme / tier | T2_Blame-the-Messenger / **ultra_hard** |
| baseline pred | `ts-basic-service` ❌ (qpf=51) |
| v4 pred | `ts-basic-service` ❌ (qpf=29) |
| 干预 | **mid 未触发**（agent R23 即 ready）/ conc M8+M2 @ R23 |
| transition | wrong → wrong |

### 2. GT 注入

```
fault_type: 28 = JVMMemoryStress
display_config:
  app_name: ts-price-service
  injection_point: price.controller.PriceController.query
  mem_type: 2  # direct memory (NOT heap)
ground_truth.service: [ts-price-service]
ground_truth.pod:     [ts-price-service-7494fb49fc-8rgwq]  (causal_graph 记录 dpjs9，新旧 pod 切换)
```

### 3. chaos 机制

`PriceController.query` 是核心查询入口（被 ts-basic-service 调 491 次/normal）。mem_type=2 direct memory（off-heap native memory）：byte code 注入污染 native memory pool，cpu 副作用强（21.51x）但 RSS/working_set 几乎不变（这是跟 mem_type=1 heap 的关键区别）。

物理验证：
- container.cpu.usage **21.51x**（0.16 → 3.45）—— 第二名 ts-basic 仅 1.99x
- jvm.cpu.recent_utilization **17.88x**
- k8s.container.restarts: 0 → 1（pod dpjs9 → 8rgwq 切换）
- container.memory.* / k8s.pod.memory.* **全 1.0-1.1x**（direct memory 不触发 heap GC，RSS 稳定）
- page_faults 2.83x

chaos 必然生效（cpu + restart + 端点 p99 60x）。

### 4. 调用树（normal 期实测）

```
loadgen → ts-ui-dashboard
  └─ ts-travel-plan-service / ts-travel2-service / ts-route-plan-service
      └─ ts-travel-service.queryInfo
          └─ ts-basic-service (BasicController.queryForTravels / queryForTravel)
              └─ ts-price-service.PriceController.query  ◀── GT
                  └─ self (PriceConfigRepository / SELECT PriceConfig)
```

duckdb 验证：normal 中 ts-basic-service 调 ts-price-service 491 次。**baseline/v4 锚定的 ts-basic-service 是 GT 的直接 caller**——经典 Blame the Messenger（Sender 锚定）。

### 5. 关键 duckdb 证据

#### GT (ts-price-service) 指纹

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| **container.cpu.usage** | 0.16 | 3.45 | **21.51x** ⭐ 孤立 outlier（第二名 ts-basic 1.99x）|
| k8s.pod.cpu.usage | 0.159 | 3.43 | 21.50x |
| **k8s.pod.cpu_limit_utilization** | 0.032 | 0.685 | 21.50x |
| **jvm.cpu.recent_utilization** | 0.0016 | 0.029 | 17.88x |
| jvm.system.cpu.utilization | 0.241 | 0.388 | 1.61x（pod-shared metric）|
| hubble_http_request_duration_p90 | 0.021 | 0.605 | **29.34x** ⭐ |
| k8s.pod.memory.page_faults | 149710 | 422941 | 2.83x |
| **k8s.container.restarts (pod-level)** | 0 | 1 | **0→1** at R+offset |
| container.memory.rss / working_set / available | - | - | **1.0-1.1x（mem_type=2 不变）** |
| trace count | 2455 | 722 | 0.29x（与全集群 0.27 同步缩量）|
| service avg duration | 16.2 | 60.4 | **3.74x（仅排第 9，被上游聚合掩盖）**|
| trace status_code Error | 0 | 0 | **silent on errors** |
| log SEVERE | 0 | **0**（仅 1 WARN）| silent |

#### GT 端点级 duration distribution

| span_name | n_p50 | a_p50 | n_p99 | a_p99 | avg_r |
|---|---|---|---|---|---|
| PriceConfigRepository.findByRouteIdAndTrainType | 2.4 | 3.3 | 15.6 | **514.4** | 8.82x |
| POST /api/v1/priceservice/prices/byRouteIdsAndTrainTypes | 6.6 | 11.0 | 44.4 | **2575.3** | 6.96x |
| GET /api/v1/priceservice/prices/{routeId}/{trainType} | 6.3 | 10.2 | 30.1 | **908.1** | 6.49x |
| PriceController.query | 4.5 | 6.8 | 31.0 | **1569.8** | 4.9x |
| SELECT ts.price_config | 1.0 | 1.1 | 9.2 | 2.8 | **0.14x（survivor bias）** |

p50 几乎不变，p99 飙到 514-2575ms（OOM/GC 窗口被卡）；但 service avg 仅 3.74x 排第 9。

#### baseline/v4 锚 ts-basic-service（GT 的 caller）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| service avg duration | 47.5 | 1122.6 | **23.62x（排第 2，"看起来惨"）**|
| trace error rate | **0%** | **25.51%（633/2481）** | **incident-only** |
| **log SEVERE** | **0** | **211**（207 个"503 Connection refused"）| **incident-only** |
| container.cpu | 0.267 | 0.531 | 1.99x（弱）|
| jvm.cpu | 0.0023 | 0.0038 | 1.65x（弱）|
| page_faults | 139170 | 157248 | 1.13x（弱）|
| restart counter | 0 | 0 | 无 |
| hubble_http_request_duration_p* | NaN | NaN | NaN（pod 间通信受影响指纹）|

**ts-basic-service 503 message 内容**（207 条相同 message + 4 条变体）:
```
Servlet.service() ... ServiceUnavailable: 503 Service Unavailable: 
[upstream connect error or disconnect/reset before headers. retried and the latest reset reason: 
remote connection failure, transport failure reason: delayed connect error: Connection refused]
```
+ 4 条带 IP：`Cannot assign requested address|remote address:10.0.5.211:8080`（**10.0.5.211 = ts-price-service IP**）

#### 全局 503 / connection refused 分布

```
ts-seat-service       437  ← cascade 远端 victim
ts-basic-service      211  ← caller 报告 callee（GT）不可达 ⭐
ts-route-plan-service   8
ts-travel2-service      8
ts-travel-plan-service  8
ts-travel-service       6
ts-price-service        1  ← GT 自己仅 1 条 503（silent）
```

#### 全局 restart counter 扫描（incident-onset 指纹）

```
ts-ticket-office-service-...-k5sxj    restart 2 (chronic, 不在事故链上)
ts-price-service-7494fb49fc-dpjs9     restart 1  ⭐ chaos target
```

只有 GT pod 有 incident-onset restart。

### 6. baseline 推理（51 round → ts-basic-service ❌）

| Round 段 | 行为 |
|---|---|
| R1-R3 | log SEVERE rank → ts-basic-service 211 errors, 503 Connection refused |
| 🔴 R3 锚定 | "ts-basic-service is trying to connect to something unavailable" → 锚 ts-basic-service（**没追问 unavailable target 是谁**）|
| R4-R5 | trace chain → loadgen → ui-dashboard → travel(2)/route → travel-service → basic-service |
| R6 think 关键 | excerpt: "Cannot assign requested address \| remote address: **10.0.5.211:8080**. This indicates ts-basic-service is trying to connect to IP 10.0.5.211:8080 but failing" → **看到 IP 但没反查服务名** |
| R7-R9 | 反复确认 ts-basic-service 是"原点"（normal=0 errors, abnormal=633 errors） |
| R9 think | normal vs abnormal trace error rate 对比 → "ts-basic-service incident-only" → 加固 |
| R10-R20 | 看 trace timeline 加固 |
| R20 think | timeline: "ts-basic-service first error 04:45:01" → 用 first-error timestamp 锚定 |
| R51 final | commit `ts-basic-service` ❌ |

**baseline 失败子模式**：
1. **503 message provenance 误读**（核心）：把 caller 视角的"upstream Connection refused"当成 caller 自己的问题
2. **IP 反查缺失**：R6 reflection 已经摘出 `10.0.5.211:8080`，但**没用 attr.k8s.pod.ip 反查这是 ts-price-service**
3. **没查 specific metric**：integer 没有任何 query 涉及 container.cpu / k8s.container.restarts 排序
4. **silence-as-health**：ts-price-service 0 SEVERE → 完全不在候选名单中
5. **first-error timestamp fallacy**：用 ts-basic-service 04:45:01 当 RC origin（实际是 caller 第一个 timeout 上报）

### 7. v4 推理（29 round → ts-basic-service ❌）

| Round 段 | 行为 |
|---|---|
| R1-R23 | 跟 baseline 几乎完全一致：锚 ts-basic-service（211 SEVERE 503）→ trace chain → first-error timestamp 加固 |
| R23 think 自我 final | excerpt: "ts-basic-service SEVERE 04:45:01.567, ts-travel-service 04:45:53.660 (52s LATER) → ts-basic-service is the origin" → **agent 自己宣告 ready commit** |
| R24 试图 final commit | 触发 conc M8+M2 干预（mid 因 round_count 23 < 30 **未触发**）|
| 🚨 R23 conc M8+M2（中文）| "反例隔离 + 候选是基础类服务，连接失败/503 是否常态" |
| R24 query | normal_logs ERROR rank by service —— ts-basic 不在内 |
| R25 query | normal_logs SEVERE messages → ts-food/notification 50/47（chronic 验证）|
| R26 query | normal_traces error_rate → 0 |
| R27 query | normal_logs ts-basic-service ERROR → empty |
| R28 query | normal_traces total count by service |
| R29 think 反向加固 | excerpt: "Question 1: 如果 ts-basic healthy, 其他异常还会有吗？In normal logs: ts-basic ZERO SEVERE, abnormal 211 → INCIDENT-ONLY signal → ts-basic 就是 RC" → **counterfactual 单向反向加固** |
| R29 final | commit `ts-basic-service` ❌（不变）|

**v4 干预实际效果**：
- mid 干预 **完全未触发**（agent R23 即 ready commit，比 round 30 阈值早）—— **结构性问题**：mid 触发时机错失整个 ultra_hard case
- conc M8 counterfactual ❌ **反向加固**——agent 把 "normal=0 SEVERE → incident-only" 当 counterfactual 站立（实际只验证了"基础数据是 incident-only"，没验证"如果 ts-basic healthy 其他异常是否消失"——后者需要查 ts-price-service specific metric）
- conc M2 secondary（chronic check 描述）❌ **概念命中但反向加固**——chronic check 跑了，发现 ts-basic-service incident-only → 反而强化锚定（chronic 在 503 message provenance 类 case 里没决策力）

### 8. 失败模式

| 失败链 | baseline | v4 |
|---|---|---|
| 503 message provenance 误读 | ❌ 把 caller 视角 timeout 当 caller 自身问题 | ❌ 同 |
| IP 反查缺失 | ❌ R6 看到 10.0.5.211:8080 没反查 | ❌（v4 没看 IP 这条线）|
| silence-as-health | ❌ GT 0 SEVERE / 0 trace errors → 不在候选 | ❌ 同 |
| 没查 specific metric | ❌ 全程没查 container.cpu / restart 排序 | ❌ 同 |
| first-error timestamp fallacy | ❌ ts-basic 04:45:01 当 origin | ❌ 同 + R23 reflection 加固 |
| F1 维度选错 | - | ⚠️ 没 mid 干预（结构性 miss）|
| F2 confirmation bias | - | ❌ counterfactual 单向"normal=0 = INCIDENT-ONLY = RC"|
| F5 conc 反向加固 | - | ❌ 6 round 全用来加固 |
| chronic check 没决策力 | - | ❌ ratio 0/211 反而加固 ts-basic |

主要失败模式：
- baseline：**503 message provenance 误读**（核心，同 case 99/1218/1459）+ **IP 反查缺失**（看到 10.0.5.211 没 dump pod 表）+ silence-as-health + first-error timestamp fallacy
- v4：**mid 未触发**（结构性 miss，ultra_hard case 23 round 就 ready）+ **F5 conc 反向加固**（counterfactual 单向 "incident-only = RC"）+ chronic check 误用（incident-only 在 503 provenance 模式下不是 RC 证据，是 caller 报告的 timeout）

跟 case 99/1218/1459 共同点：caller 503 + GT silent + 没查 specific metric。差别：3760 是 **mid 未触发**的极端版本——只剩 conc 6 round 而且反向加固。

### 9. 中间件如何提示能翻转

需要的 advisor 维度：
- **503 message provenance 反例 + IP 反查模板**（case 99/1218/1459 已记 + 3760 加强）：advisor 看到 agent 锚定服务有 207+ 条相同的"upstream Connection refused"或"remote address:IP:port"时强制查询模板：`SELECT DISTINCT service_name, "attr.k8s.pod.ip" FROM abnormal_traces WHERE "attr.k8s.pod.ip" LIKE '10.0.5.%'` 反查 IP 对应服务（10.0.5.211 → ts-price-service）
- **mid 触发时机调整**（case 3760 暴露的结构性问题）：mid 阶段不能只在 round_count >= 30 触发，应在"agent 第一次表达 ready/final/commit"时触发——case 3760 agent R23 think 已经宣告 ready 但 mid 未触发
- **specific metric 强制 SQL 模板**（case 33/1495/2713 已记 + 3760 加强）：在 mid（或 conc 之前）强制全局 container.cpu / restart ratio 排序，立即看到 ts-price-service 21.51x 孤立 outlier + restart 0→1 pod
- **counterfactual 双向**（新维度，case 3760 暴露）：M8 counterfactual 当前是单向"如果 candidate healthy, 其他异常会消失吗"，应改为双向：(a) 如果 candidate healthy 异常会消失吗；(b) 如果 candidate 自己是 RC, 它的 container.cpu / restart 是否升高 → 双向都通过才能 commit
- **chronic check 在 503 provenance 模式下失效警告**（新维度）：advisor 看到 chronic check 结果是"normal=0, abnormal=211 SEVERE 全 503 Connection refused"时**不能加固**该 candidate，应反向触发 IP 反查（caller 报 timeout 不能证明 caller 是 RC）
- **silence-as-candidate**（case 2713 已记 + 3760 加强）：所有 service 都进候选名单，不能因 0 SEVERE 排除——必须用 trace count diff / specific metric 维度过滤

最有效组合：**503 message provenance 反例 + IP 反查 + 全局 container.cpu 排序** —— 三步：(1) 看到 207 条同质 503 message 触发 IP 反查 → 10.0.5.211 = ts-price-service；(2) 全局 container.cpu ratio 排序看到 ts-price-service 21.51x 孤立；(3) 全局 restart 扫描看到 ts-price-service-...-dpjs9 restart 0→1。case 3760 直接翻盘。

### 10. 中间件代码层面问题

- **mid 未触发**（结构性问题）：v4 mid 触发条件是 round_count >= 30，但 ultra_hard case 3760 agent 仅 23 round 就宣告 ready commit，**mid 完全没机会干预**——结果干预总数从设计的 mid+conc 双重退化为 conc 单重，调控强度减半
- **conc M8 中文输出**：dimension_cards.py 模板国际化问题（同 case 1459 等已记），跟 prompt 主语言（英文）不一致可能让 agent 部分忽略
- **conc M8 counterfactual 单向**：advisor 文本"如果你的候选完全健康，你观察到的其他异常还会发生吗" → 这个问题本身**模糊**，agent 把它解读成"normal=0, abnormal=211 = INCIDENT-ONLY = causality"，反向加固。需要双向 prompt（"如果它是 RC, 它的 specific metric 应该升高"）
- **conc M2 secondary 描述错配**：M2 在卡片库通常是"service centrality"维度，但 advisor 文本（"它的这类错误在正常时段是否也存在"）实际是 M6 chronic check 范畴——secondary 维度选错或描述串台
- **conc 6 round 不够**：post_intervention_tool_rounds=6，全部用来跑 normal_logs/normal_traces ERROR count（chronic check），没查 specific metric——advisor 给 prompt 但没强制 SQL 模板
- **干预次数 1**：仅 conc 触发，比 v4 设计的 mid+conc 减半，调控时机错失关键

### 11. 判断

- 数据完整性：✅
- chaos 生效：✅ 必然生效（container.cpu 21.51x + restart 0→1 + p99 60x；mem_type=2 direct memory 比 mem_type=1 heap 表现 cpu 更强 memory 不变）
- 盲区类型：**(b) 框架盲区** + **(d) 中间件代码问题**双重——503 message provenance + mid 未触发结构性问题
- 失败模式：baseline = **503 message provenance 误读**（核心）+ IP 反查缺失 + silence-as-health + first-error timestamp fallacy；v4 = **mid 未触发**（结构性 miss）+ **F5 conc 反向加固**（counterfactual 单向 + chronic check 误用）
- 给 v4.1：(1) **mid 触发时机改为 "round_count >= 20 OR agent 表达 ready commit"**——case 3760 agent R23 ready 应触发 mid；(2) **503 message provenance 反例 + IP 反查 SQL 模板**——agent 锚定服务有 100+ 条同质"upstream Connection refused"时强制查 IP 对应服务；(3) **counterfactual 双向**——M8 改为"candidate healthy → 其他异常消失？" + "candidate is RC → specific metric 升高？"双向；(4) **chronic check 在 503 provenance 模式下失效警告**——503/Connection refused 类 SEVERE 不能用 incident-only 反向加固；(5) **mid 强制全局 container.cpu / restart ratio 排序**

### 12. causal_graph 正确性检验

⚠️ **GT 标注偏差**（service-level GT 仍正确，跟 case 1218/1459/1495 同模式 high_memory 误标）：
- container|ts-price-service `[high_cpu, restarting, high_memory]` —— high_cpu ✅ (21.51x)，restarting ✅ (0→1)，**high_memory ❌ 错标**：实测 container.memory.rss/working_set/available **全 1.0-1.1x**，mem_type=2 是 direct memory（off-heap），不增加 RSS，causal_graph 把 cpu 主导误标为 memory 主导
- pod|ts-price-service-7494fb49fc-dpjs9 `[high_memory, high_http_latency, high_gc_pressure, high_cpu, healthy]` —— high_memory ❌ 同上误标，high_http_latency ✅ (端点 p99 514-2575ms)，high_cpu ✅，high_gc_pressure ⚠️ 间接化牵强（mem_type=2 不触发 heap GC，cpu 17x 是 byte code 注入物理副作用而非 GC pressure），healthy 多时刻
- service|ts-price-service `[unknown]` —— 不评判
- span 层 missing_span / high_avg_latency / high_p99_latency 全 ✅（端点 p99 514-2575ms 完全支撑）
- cascade 节点 ts-basic-service / ts-travel-service / ts-ui-dashboard / loadgenerator 的 high_avg_latency / high_p99_latency / high_error_rate / timeout 全 ✅（cascade 上游 avg 13-23x，error rate 1-25%）
- 跟 case 1218/1459/1495 同模式：mem_type=2 direct memory case 实际是 cpu 主导，causal_graph 把它误标 high_memory（不影响 service-level GT 但影响 metric 维度归类）

case 3760 完毕。

---

## Case 4081 · `ts2-ts-order-other-service-container-kill-48rlds` · ContainerKill on ts-order-other-service

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 4081 |
| GT | `ts-order-other-service` |
| theme / tier | T2_Blame-the-Messenger / **ultra_hard** |
| baseline pred | `ts-seat-service` ❌ (qpf=59) |
| v4 pred | **`mysql`** ❌ (qpf=60，**drift 到非业务 service**) |
| 干预 | mid M6+M5 @ R30 / conc M8 @ R54 |
| transition | wrong → wrong（v4 drift 但仍错） |

### 2. GT 注入

```
fault_type: 2 = ContainerKill (PodChaos)
display_config:
  app_label: ts-order-other-service
  container_name: ts-order-other-service
  pod_name: ts-order-other-service-78c95666f-lzr8f  (注：实际数据中 pod 是 574d96b46c-z7bvj)
  duration: 4
ground_truth.service: [ts-order-other-service]
```

### 3. chaos 机制

ContainerKill 直接 SIGKILL 容器。物理时间线（duckdb 直查）：
- **03:13:24.404** mysql 看到 host **10.0.1.97** 的 10 个 connection 同时 abort（chaos 杀容器瞬间）
- **03:13:28.012** ts-seat-service 第一条 503（开始报 callee 不可达）
- 03:13:24 ~ 03:14:45 **silent gap ~86 秒**（容器死亡到新 trace export）
- **03:14:21.643** "Starting OrderOtherApplication v1.0 on ts-order-other-service-574d96b46c-z7bvj with PID 1" → cold-start
- 03:14:39 Tomcat 启动，03:14:50 ProtocolHandler ready
- 03:14:45 第一个 abnormal_trace 重新出现
- 03:17:23 abnormal 窗口结束，跟 chaos duration=4min 吻合

ContainerKill 必然生效（restart 0→1 + container.cpu 10x + 86s 完全 silent gap）。但跟 JVMMemoryStress 不同：jvm 维度反而下降（jvm.system.cpu.utilization 0.58x，因为 JVM 死了重启，cold-start 期 metric 上报间断）。

### 4. 调用树（normal 期实测）

```
loadgen → ts-ui-dashboard
  └─ ts-travel-plan-service / ts-travel2-service / ts-route-plan-service / ts-travel-service
      └─ ts-seat-service (SeatController.getLeftTicketOfInterval / POST /seats/left_tickets)
          └─ ts-order-other-service (OrderOtherController.getTicketListByDateAndTripId)  ◀── GT
              └─ self (OrderOtherRepository / SELECT Order)
              ↘ ts-security-service.SecurityController.check
```

duckdb 验证：normal 中 ts-seat-service 调 ts-order-other-service 304 次，ts-ui-dashboard 调 126 次，ts-security-service 调 41 次。**baseline 锚 ts-seat-service 是 GT 的直接 caller**——经典 Blame the Messenger。**v4 锚 mysql 是 GT 的下游数据存储**——drift 到完全错的"depth"。

### 5. 关键 duckdb 证据

#### GT (ts-order-other-service) 指纹

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| **container.cpu.usage** | 0.137 | 1.369 | **10.03x** ⭐ 孤立 outlier（第二名 ts-contacts 1.16x）|
| k8s.pod.cpu.usage | 0.141 | 1.385 | 9.83x |
| k8s.pod.cpu_limit_utilization | 0.028 | 0.277 | 9.83x |
| **k8s.container.restarts (pod-level)** | 0 | 1 | **0→1** ContainerKill 标志 |
| k8s.pod.memory.page_faults | 172617 | 293425 | 1.70x |
| jvm.system.cpu.load_1m | 31.4 | 24.1 | **0.77x（下降！）** |
| jvm.system.cpu.utilization | 0.18 | 0.10 | **0.58x（下降！）** |
| jvm.cpu.recent_utilization | 0.0 | 0.0 | 1.75x（接近零）|
| container.memory.* | - | - | **1.04x（基本不变）** |
| **trace count** | 2355 | 1866 | **0.79x**（不是完全 silent，因为 86s gap 后 pod 恢复仍有 export）|
| log SEVERE | 0 | 0 | silent on errors |
| **silent gap** | - | **86s** | 03:13:24→03:14:45 完全无 trace |

**ContainerKill vs JVMMemoryStress 关键差别**：jvm 维度反而下降（JVM 死了重启 cold-start 期 metric 上报间断），而 container.cpu 升 10x（包含整个容器生命周期 cpu time，cold-start 大量 class loading 计入）。

#### GT 端点级 duration distribution

| span_name | n_n | a_n | n_avg | a_avg | avg_r | n_p99 | a_p99 |
|---|---|---|---|---|---|---|---|
| GET /api/v1/orderOtherService/orderOther/security/{checkDate}/{accountId} | 41 | 18 | 6.1 | 45.9 | **7.57x** | 31.8 | **583.7** |
| OrderOtherController.securityInfoCheck | 41 | 18 | 4.4 | 10.9 | 2.45x | 27.0 | 97.9 |
| OrderOtherRepository.findByAccountId | 167 | 107 | 3.5 | 6.0 | 1.72x | 33.3 | 36.8 |
| POST /api/v1/orderOtherService/orderOther/tickets | 304 | 252 | 18.0 | 14.9 | **0.83x** | 44.6 | 129.9（survivor bias）|
| OrderOtherController.getTicketListByDateAndTripId | 304 | 252 | 16.7 | 10.7 | **0.64x** | 42.0 | 104.5 |
| OrderOtherRepository.findByTravelDateAndTrainNumber | 304 | 252 | 14.7 | 8.4 | **0.57x** | 39.1 | 101.8 |

主路径（getTicketListByDateAndTripId）avg 反而 0.57-0.83x（survivor bias——slow 请求在 silent gap 期间没 export）；security 子路径 avg 7.57x p99 18x（恢复后期被卡）。

#### baseline anchor: ts-seat-service（GT 的 caller）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| service avg duration | 32.7 | 180.7 | 5.52x |
| trace count | 2960 | 2270 | 0.77x |
| **trace error rate** | 0% | **2.5%（96 errors）** | incident-only |
| **log SEVERE** | 0 | **32**（29 条"503 Connection refused"+ 3 条带 IP 10.0.1.97）| **incident-only** |
| container.cpu | - | - | <1.2x |
| restart counter | 0 | 0 | 无 |

ts-seat-service 503 message 内容：
- 29 条："503 Service Unavailable: [upstream connect error... Connection refused]"
- 3 条："Cannot assign requested address|remote address:**10.0.1.97**:8080"

#### v4 anchor: mysql（drift 目标）

mysql logs（normal=0，**abnormal=10**）全是同样模式，时间集中在 **03:13:24.404** 一秒内：
```
2025-07-21T03:13:24.404251Z 120 [Note] Aborted connection 120 to db: 'ts' 
user: 'root' host: '10.0.1.97' (Got an error reading communication packets)
```
（10 条只是 connection ID 不同：120/118/117/115/114/113/112/111/110/27）

**关键解读**：mysql 是**被动**记录"客户端 host 10.0.1.97 突然断开"。10.0.1.97 = **ts-order-other-service pod IP**——chaos 杀容器瞬间，ts-order-other-service 与 mysql 的所有 10 个 HikariPool connection 同时被强制断开。

#### IP 反查关键证据

```
host 10.0.1.97 mentions in abnormal_logs:
  mysql:           10  (Aborted connection from 10.0.1.97)
  ts-seat-service:  3  (Cannot assign requested address|remote address:10.0.1.97:8080)
```

**10.0.1.97 = ts-order-other-service-574d96b46c-z7bvj pod IP**——同一个 IP 出现在 mysql 看到的"客户端断开"和 ts-seat-service 看到的"调不通的下游"两端，**完整证据闭环指向 ts-order-other-service**。

#### 全局 container.cpu.usage ratio（孤立性）

```
ts-order-other-service     10.03  ⭐ 唯一极端 outlier
ts-contacts-service         1.16
ts-execute-service          1.15
ts-avatar-service           1.14
... 其余全 <1.2x
```

第二名只有 1.16x——孤立教科书级。

#### 全局 restart counter 扫描

```
ts-ticket-office-service-...-r7d4f      restart 2  (chronic, 不在事故链)
ts-order-other-service-574d96b46c-z7bvj restart 1  ⭐ chaos target
```

只有 GT pod 有 incident-onset restart。

### 6. baseline 推理（59 round → ts-seat-service ❌）

| Round 段 | 行为 |
|---|---|
| R1-R3 | log SEVERE rank → ts-delivery/notification 48 each "Failed to redeclare queue" rabbitmq chronic |
| R4-R5 | trace chain `e505b038...` → loadgen → ui-dashboard → travel-plan → travel2 → seat |
| R6 think | "ts-seat-service 96 Error status, 503 Connection refused" → 锚 ts-seat-service |
| R7 think 关键 | excerpt: "ts-seat-service error: **'Cannot assign requested address \| remote address:10.0.1.97:8080'**" → 看到 IP 但**没反查** |
| R8-R20 | 加固 ts-seat-service "is the service with most errors" |
| R20+ | trace timeline analysis 加固 |
| R59 final | commit `ts-seat-service` ❌ |

**baseline 失败子模式**：
1. **503 message provenance 误读**（核心）：207 条同质 503，把 caller 视角 timeout 当 caller 自身问题
2. **IP 反查缺失**：R7 看到 10.0.1.97:8080 但没解析；3 条带 IP 的 message 没用 attr.k8s.pod.name 反查
3. **silence-as-health**：GT trace 0.79x（不算严重 silent）+ 0 SEVERE → 不在候选名单
4. **没查 specific metric**：完全没查 container.cpu / restart 排序
5. **restart 硬证据缺失**：log 里有 "Starting OrderOtherApplication" 但 baseline 没查

### 7. v4 推理（60 round → mysql ❌，drift）

| Round 段 | 行为 |
|---|---|
| R1-R30 | 跟 baseline 一样：锚 ts-seat-service 96 errors / 503 / 10.0.1.97（IP 没反查） |
| 🚨 R30 mid M6+M5 | "baseline 对比 + silent service" |
| R31 think 复述 | excerpt: "ts-seat-service is trying to call upstream that's unavailable" → **思路对了**（确实 caller 的 upstream 才是 RC），但 anchor 没切 |
| R32-R33 | list service normal vs abnormal → 两边都 "ts-order-other-service" 都在 → 误判"没有完全 silent 的服务"（实际 GT 86s silent gap 没被发现）|
| R34-R45 | 反复围 ts-seat-service 加固，看 trace chain |
| R46 query 关键 | excerpt: `Starting OrderOtherApplication v1.0 on ts-order-other-service-574d96b46c-z7bvj with PID 1` → **看到 restart 硬证据但完全没识别**（OrderOther 的 cold-start log 跟 chaos kill 是 1:1 对应） |
| R47 query | abnormal_logs service+level count → 看到 mysql 在异常 log 里（level=""）|
| R48 query mysql | 看到 10 条 "Aborted connection from host 10.0.1.97" |
| 🔴 R49 think BREAKTHROUGH | "**MySQL aborted connections at 03:13:24.404**, ts-seat-service starts receiving requests but can't connect to MySQL" → **因果倒置**：mysql aborted connection 是 client (10.0.1.97 = ts-order-other-service) 死亡的**结果**而非原因 |
| R50-R54 | 加固 mysql RC 假说 |
| R54 final commit #1 | mysql ❌ |
| 🚨 R54 conc M8 | "counterfactual + chronic check" |
| R55-R60 query | 比较 normal vs abnormal mysql logs（normal=0, abnormal=10）→ "mysql aborted connection incident-only" → 反向加固 |
| R60 final | commit `mysql` ❌（不变） |

**v4 干预实际效果**：
- mid M6 baseline 对比 ⚠️ 跑了（list services normal vs abnormal）→ 但因为 GT 不是完全 silent，没识别出 ts-order-other-service 异常
- mid M5 silent service ❌ **失效**：GT trace 0.79x 不算"完全 silent"，agent 没查 trace count diff 也没查 silent gap 时间窗
- conc M8 counterfactual ❌ **反向加固**：counterfactual 仅做 chronic check（mysql normal=0, abnormal=10）→ "incident-only = RC"
- **R46 restart 硬证据 miss**：agent 看到 "Starting OrderOtherApplication PID 1" 完全没识别为 ContainerKill 的 cold-start log
- **F3 drift**：v4 切了 anchor（seat → mysql）但选了完全错的"depth"——mysql 是 GT 的下游数据库，agent 越查越深进了死胡同

### 8. 失败模式

| 失败链 | baseline | v4 |
|---|---|---|
| 503 message provenance 误读 | ❌ ts-seat-service 503 当 caller 自身问题 | ⚠️ mid 后转向 upstream 思路对，但选错 |
| IP 反查缺失 | ❌ 10.0.1.97:8080 没反查 | ❌ mysql + ts-seat-service 都提 10.0.1.97 没反查 |
| silence-as-health | ❌ GT 0 SEVERE 不在候选 | ❌ GT 不算完全 silent → mid silent service 维度失效 |
| 没查 specific metric | ❌ container.cpu / restart 全没查 | ❌ 同 |
| restart 硬证据 miss | ❌ 没查 "Starting" log | ❌ R46 看到了但没识别 |
| 因果倒置（reverse causality） | - | ❌ **mysql 是 abort 受方而非主动方** |
| F1 维度选错 | - | ⚠️ mid M5 silent service 在"没完全 silent"的 case 下失效 |
| F2 confirmation bias | - | ⚠️ mid 启发了 upstream 思路但 anchor drift |
| F3 agent drift | - | ❌ seat → mysql（drift 到 GT 的下游而非上游真因）|
| F5 conc 反向加固 | - | ❌ chronic check normal=0, abnormal=10 反向加固 mysql |

主要失败模式：
- baseline：**503 message provenance + IP 反查缺失 + silence-as-health + restart log miss**（4 联）
- v4：**F3 drift 到错位的 depth**（seat → mysql，mysql 是 GT 的下游数据库）+ **因果倒置**（mysql aborted connection 是结果不是原因）+ mid silent service 在"非完全 silent" case 下失效 + R46 restart 硬证据 miss + F5 conc 反向加固

跟 case 99/1218/1459/3760 的"503 provenance + caller 锚定"链条共同，但 4081 多了一层：**v4 mid 启发了 "upstream 才是 RC" 思路但 drift 到 mysql（错位的下游 callee）**。这是 ContainerKill 跟 JVMMemoryStress 的区分点：ContainerKill 的次级证据（mysql aborted connection from client IP）让 agent 误读因果方向。

### 9. 中间件如何提示能翻转

需要的 advisor 维度：
- **IP 反查模板**（case 99/1218/1459/3760 已记 + 4081 加强）：当 abnormal_logs 中出现 `host 'X.X.X.X'` 或 `remote address:X.X.X.X:port` 时强制查询 `SELECT DISTINCT service_name, "attr.k8s.pod.name" FROM abnormal_traces WHERE "attr.k8s.pod.name" IN (SELECT pod FROM ... pod_ip='X.X.X.X')`——case 4081 中 mysql + ts-seat-service 都提到 10.0.1.97，反查就是 ts-order-other-service
- **restart log 强制扫描**（新维度，case 4081 暴露）：在 mid 阶段强制查 `SELECT service_name, time, message FROM abnormal_logs WHERE message LIKE '%Starting%Application%' OR message LIKE '%Started%' OR message LIKE '%PID 1%'`——任何"Starting Application v* PID 1"是 cold-start 硬证据，强烈指向 PodChaos/ContainerKill
- **silent gap 检测**（新维度，case 4081 暴露）：mid silent service 维度当前查"是否服务名缺席"，但 ContainerKill 不让服务彻底缺席（pod restart 后又有 trace），应改为查 trace 时间分布的 gap：`SELECT service_name, COUNT(*) FILTER (WHERE time BETWEEN incident_start AND incident_start+90s) FROM abnormal_traces GROUP BY 1 ORDER BY 2 ASC`—— gap > 60s 的服务是 PodChaos/ContainerKill 嫌疑
- **specific metric 强制 SQL 模板**（case 33/1495/2713/3760 已记 + 4081 加强）：mid 阶段全局 container.cpu / k8s.container.restarts ratio 排序——case 4081 立即看到 ts-order-other-service container.cpu 10.03x 孤立 outlier + restart 0→1
- **因果方向反例**（新维度，case 4081 暴露）：advisor 看到 agent 把"X 服务的 aborted connection from host Y"当成 X 是 RC 时强制反例——`Aborted connection from host` 表示 X **被动**接收 Y 的断开，应反查 host Y 对应的服务（IP 反查），而非锚定 X
- **counterfactual 双向**（case 3760 已记 + 4081 加强）：M8 改为双向"candidate healthy → 异常消失？" + "candidate is RC → container.cpu / restart 升高？"——case 4081 中 mysql container.cpu < 1.0x + restart=0，双向 commit-gate 立即否决

最有效组合：**restart log 扫描 + IP 反查 + silent gap 检测** —— 三步：
1. 全局扫"Starting Application PID 1" → 看到 ts-order-other-service 03:14:21 cold-start
2. 反查 10.0.1.97 → ts-order-other-service pod IP
3. silent gap 03:13:24→03:14:45 ~86s → ContainerKill 指纹

case 4081 直接翻盘。

### 10. 中间件代码层面问题

- mid M5 silent service 维度**在"非完全 silent"case 下失效**：advisor 文本只提"a service that's completely down might be absent from traces"，但 ContainerKill duration=4min 中只有 ~86s silent gap，pod restart 后又有 trace，agent list services 看到 ts-order-other-service 在 abnormal_traces 里 → 误判"没消失"。需要扩展为"trace 在某 60s+ 时间窗内消失"的 silent gap 检测
- mid M6 baseline 对比 advisor 文本指引正确（"compare against normal data"）但**没强制 specific metric 维度**——agent 跑了 list services 对比但没扩展到 container.cpu / restart counter ratio 排序
- conc M8 counterfactual **单向且 chronic-check-equivalent**：agent 把 "mysql normal=0, abnormal=10 = INCIDENT-ONLY = RC" 当 counterfactual 站立——同 case 3760 单向问题
- **缺少"Starting Application" 硬证据扫描**：v4 advisor 完全没引导 agent 查 application restart log，case 4081 有 5 条 cold-start 硬证据但 agent 全错过
- **缺少"因果方向"反例**：mysql aborted connection from <IP> 这种"被动断开"格式 advisor 没识别，agent 直接把它解读成 mysql 主动断开 = RC
- 干预次数 2 + post_intervention 24/6 round 都用上了，但**质量不够**——需要 prescriptive SQL 而非 descriptive prompt

### 11. 判断

- 数据完整性：✅
- chaos 生效：✅ 必然生效（restart 0→1 + container.cpu 10.03x + 86s silent gap + cold-start log）；ContainerKill 跟 JVMMemoryStress 的区别：jvm 维度反而下降，container 维度升高
- 盲区类型：**(b) 框架盲区**双重——(b1) silent service 维度在"非完全 silent"case 下失效；(b2) IP 反查 + restart log + 因果方向 全部缺失
- 失败模式：baseline = **503 provenance + IP 反查缺失 + silence-as-health + restart log miss**；v4 = **F3 drift 到错位 depth**（mysql 是 GT 下游数据库）+ **因果倒置**（aborted connection 受方当主动方）+ mid silent service 维度失效 + R46 restart 硬证据 miss + F5 conc 反向加固
- 给 v4.1：(1) **silent service 改为 silent gap 检测**——查 trace 在 60s+ 时间窗内消失；(2) **restart log 强制扫描**——`message LIKE '%Starting%Application%' OR '%PID 1%'`；(3) **IP 反查模板**（case 4081 中 mysql + ts-seat-service 都提 10.0.1.97 完整证据闭环）；(4) **因果方向反例**——`Aborted connection from host` 是被动接收，应反查 host；(5) **specific metric 强制全局 container.cpu / restart 排序**——孤立 10x outlier 立即命中

### 12. causal_graph 正确性检验

⚠️ **部分节点 state 错标**（service-level GT 仍正确，比 case 1218/1459/1495/3760 错标程度轻）：
- container|ts-order-other-service `[high_cpu]` —— ✅ 单标签准确（10.03x），跟 case 2713 一样 container 层正确
- pod|ts-order-other-service-574d96b46c-z7bvj `[high_memory, high_cpu, healthy, high_gc_pressure]` —— **high_memory ❌ 错标**（实测 container.memory.* 全 1.04x，ContainerKill 不影响 memory），high_cpu ✅，high_gc_pressure ⚠️ 间接化牵强（jvm.system.cpu.utilization 反而下降 0.58x，没有 GC pressure 实证），healthy 多时刻
- service|ts-order-other-service `[unknown]` —— 不评判
- span 层 missing_span ✅（86s silent gap 物理一致），high_avg_latency / high_p99_latency 部分正确：
  - GET securityConfigs avg 7.57x p99 18x ✅
  - findByTravelDateAndTrainNumber 实测 avg 0.57x（survivor bias）但仍标 high_p99_latency（p99 2.6x 弱标），属于"高分位边缘标"
  - getTicketListByDateAndTripId 主路径实测 avg 0.64x p99 2.5x，标 missing_span 准确（86s gap）但 high_p99_latency 弱
- cascade 节点 ts-seat-service / ts-travel(2)-service / ts-route-plan-service / ts-travel-plan-service / ts-ui-dashboard / loadgenerator 的 high_avg_latency / high_p99_latency / high_error_rate / timeout 全 ✅（ts-seat-service avg 5.52x，503 32 条）
- 跟 case 2713 模式相同（container 层单 high_cpu 标签准确），比 case 1218/1459/1495/3760 错标程度轻；pod 层 high_memory 同 mem_type=2 case 模式误标

case 4081 完毕。

---

## Case 4363 · `ts3-ts-train-food-service-stress-dqsrx2` · JVMMemoryStress (mem_type=2 direct memory, TrainFoodApplication.restTemplate)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 4363 |
| GT | `ts-train-food-service` |
| theme / tier | T3_Noise-Anchor / stable |
| baseline pred | `ts-rabbitmq` ❌ (qpf=37) |
| v4 pred | `ts-food-service` ❌ (qpf=85，**v4 切了 anchor 但仍错**) |
| 干预 | mid M6+M5 @ R30（中文）/ conc M8+M1 @ R73（中文）|
| transition | wrong → wrong（rabbitmq → food-service，noise-shift）|

### 2. GT 注入

```
fault_type: 28 = JVMMemoryStress
display_config:
  app_name: ts-train-food-service
  injection_point: trainFood.TrainFoodApplication.restTemplate  # @Bean RestTemplate 工厂方法（init-only）
  mem_type: 2  # direct memory
ground_truth.service: [ts-train-food-service]
ground_truth.pod:     [ts-train-food-service-565f7588ff-xx2b4]  (实际数据中是 5975fbbccb-46l5t)
```

### 3. chaos 机制

`TrainFoodApplication.restTemplate` 是 `@Bean RestTemplate` 工厂方法——只在 Spring 容器启动时被调用一次创建 singleton bean。byte code 注入此方法的副作用让整个 class loader 受 cpu 压力，但**业务热路径（TrainFoodController.getTrainFoodOfTrip）几乎不被影响**。

物理验证：
- container.cpu.usage **11.88x**（0.110 → 1.304）孤立 outlier（第二名 ts-food-service 仅 2.43x）
- k8s.pod.cpu_limit_utilization **14.81x**
- jvm.cpu.recent_utilization 1.73x（弱）
- jvm.system.cpu.* 没在 top metric 里出现（cpu 副作用主要在 container 维度）
- container.memory.* / k8s.pod.memory.* **全 1.0-1.09x**（mem_type=2 direct memory 不影响 RSS，跟 case 3760 同模式）
- **k8s.container.restarts 0 → 1**（pod 5975fbbccb-46l5t restart=1，K8s liveness probe 因 cpu 压力失败触发 restart）
- **04:05:40 "Starting TrainFoodApplication v1.0 PID 1"** cold-start log（同 case 4081 的"Starting Application"硬证据）
- **silent gap ~1m40s**（04:04 → 04:05:40 重启）

chaos 物理生效（cpu 11.88x + restart + cold-start log），但 **设计语义部分生效**：端点级 distribution 反向（0.17-0.53x，survivor bias 经典）—— init-only 方法的 chaos 跟 case 1495 同模式。

### 4. 调用树（normal 期实测）

```
loadgen → ts-ui-dashboard
  └─ ts-food-service.FoodController.getAllFood
      └─ ts-train-food-service.TrainFoodController.getTrainFoodOfTrip  ◀── GT
          └─ self (TrainFoodRepository.findByTripId / SELECT TrainFood / SELECT ts.train_food)
```

duckdb 验证：normal 中 ts-food-service 调 ts-train-food-service 85 次，abnormal 70 次 (edge ratio 0.82x，drop 18%)。**v4 锚 ts-food-service 是 GT 的直接 caller**——经典 Blame the Messenger（同 case 1218/1459/3760）。**baseline 锚 ts-rabbitmq 完全不在事故链上**（rabbitmq 是 chronic noise）。

### 5. 关键 duckdb 证据

#### GT (ts-train-food-service) 指纹

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| **container.cpu.usage** | 0.110 | 1.304 | **11.88x** ⭐ 孤立 outlier（第二名 2.43x）|
| k8s.pod.cpu.usage | 0.087 | 1.288 | 14.81x |
| k8s.pod.cpu_limit_utilization | 0.017 | 0.258 | 14.81x |
| jvm.cpu.recent_utilization | 0.001 | 0.001 | 1.73x（弱）|
| **hubble_http_request_duration_p99_seconds** | 0.036 | 0.692 | **19.0x**（p99 时段值，不是单点）|
| k8s.pod.memory.page_faults | 147043 | 419265 | **2.85x** |
| **k8s.container.restarts** | 0 | 1 | **0→1** at ~04:05:40 |
| container.memory.* / pod.memory.* | - | - | **1.00-1.09x（mem_type=2 不变）** |
| **trace count** | 466 | 476 | **1.02x（基本不变！）** |
| log SEVERE | 0 | **0**（120 INFO + 1 WARN）| **silent on errors** |

#### GT 端点级 duration distribution（survivor bias 经典）

| span_name | n_n | a_n | n_avg | a_avg | **avg_r** | n_p99 | a_p99 |
|---|---|---|---|---|---|---|---|
| SELECT ts.train_food_list | 41 | 34 | 2.2 | 2.3 | 1.04x | 22.9 | 27.2 |
| SELECT ts.train_food | 85 | 80 | 2.5 | 2.0 | 0.80x | 26.8 | 23.8 |
| GET /api/v1/trainfoodservice/trainfoods/{tripId} | 85 | 70 | 43.3 | 23.0 | **0.53x** | 470.5 | 233.4 |
| TrainFoodController.getTrainFoodOfTrip | 85 | 70 | 40.5 | 11.3 | **0.28x** | 465.4 | 59.2 |
| TrainFoodRepository.findByTripId | 85 | 75 | 37.1 | 9.2 | **0.25x** | 460.5 | 94.1 |
| SELECT TrainFood | 85 | 75 | 36.0 | 6.1 | **0.17x** | 453.8 | 48.5 |

主路径 avg 反而 0.17-0.53x！**survivor bias 经典**：被 chaos 卡住的 slow request 没成功 export，剩下的快路径被采样 → service avg 大幅"下降"。同时 p99 也不升（restart 短窗口外的请求都很快）。

#### baseline anchor: ts-rabbitmq（完全无信号）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| container.cpu | - | - | < 1.05x |
| k8s.pod.memory.page_faults | 246690 | 264673 | 1.07x |
| service avg duration | - | - | rabbitmq 不在 trace ratio 里 |
| **'ts-rabbitmq UnknownHostException' log** | **256** | **220** | **0.86x（chronic, abnormal 反而少）** |

baseline 锚 rabbitmq 完全是 first-error timestamp + UnknownHostException 字面意思，rabbitmq 自身指标无任何异常。

#### v4 anchor: ts-food-service（GT 的 caller）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| service avg duration | 41.7 | **493.6** | **11.84x（看起来最严重，blame the messenger）**|
| trace count | 657 | 504 | 0.77x |
| container.cpu | 0.040 | 0.097 | 2.43x |
| jvm.cpu.recent_utilization | 0.0003 | 0.0009 | 3.06x |
| hubble_http_request_duration_p* | 有值 | NaN | NaN（caller 视角连接失败指纹）|
| **log SEVERE** | **0** | **19**（503 Connection refused）| **incident-only** |
| log ERROR | 78 | 59 | 0.76x（chronic "Get Food Failed"）|
| restart counter | 0 | 0 | 无 |

food-service 503 message 内容（19 条同质）:
```
ServiceUnavailable: 503 Service Unavailable: 
[upstream connect error or disconnect/reset before headers... Connection refused]
```
**没带 IP**（generic "upstream"，**比 case 3760/4081 缺一条 IP 反查线索**）。

#### 全局 container.cpu.usage ratio（孤立性）

```
ts-train-food-service        11.88  ⭐ 唯一极端 outlier
ts-food-service               2.43
ts-payment-service            2.02
ts-train-service              1.80
ts-delivery-service           1.74
... 其余全 < 1.55x
```

#### 全局 restart counter 扫描

```
ts-ticket-office-service-...-s54hr  restart 3  (chronic, 不在事故链)
ts-train-food-service-5975fbbccb-46l5t  restart 1  ⭐ chaos target
ts-voucher-service-75f4db5b54-tczgg     restart 1  (chronic)
```

ts-train-food-service-46l5t 04:05:40 cold-start log + restart=1 双重指纹。

### 6. baseline 推理（37 round → ts-rabbitmq ❌）

| Round 段 | 行为 |
|---|---|
| R1-R3 | log SEVERE rank → ts-food-service 78 ERROR + ts-notification/ts-delivery 47 each "Failed to redeclare queue" → 锚 RabbitMQ chronic |
| R4-R8 | trace chain → ts-food-service Get Food Failed |
| 🔴 R8 think 锚定 | "First ERROR ts-food-service 04:04:16, ts-notification 04:04:18 → ts-food 是 origin"（first-error timestamp fallacy）+ 看到 `UnknownHostException: ts-rabbitmq` → 锚 RabbitMQ "DNS resolution failure" |
| R9-R15 | 加固 RabbitMQ "is unavailable" → "all errors stem from RabbitMQ" |
| R37 final | commit `ts-rabbitmq` ❌ |

**baseline 失败子模式**：
1. **first-error timestamp fallacy**：04:04:16 ts-food-service 第一条 ERROR 当 origin
2. **chronic noise 锚定**：UnknownHostException ts-rabbitmq normal=256 abnormal=220 是经典 chronic（agent 完全没做 chronic check）
3. **literal interpretation fallacy**：把 "UnknownHostException ts-rabbitmq" 字面理解为 RabbitMQ 不可达，没意识到这是 trainticket 数据集长期存在的 chronic DNS log（normal 期就有 256 条）
4. **silence-as-health**：GT 完全没出现在 baseline 候选名单
5. **没查 specific metric**：完全没查 container.cpu 排序

### 7. v4 推理（85 round → ts-food-service ❌）

| Round 段 | 行为 |
|---|---|
| R1-R30 | 跟 baseline 类似但锚定 ts-food-service 59 ERROR（first-error） |
| 🚨 R30 mid M6+M5（中文）| "baseline 对比 + silent service" |
| R31 think 关键 | excerpt: "Normal Traces NO Error / Abnormal ts-food-service 57 error spans" → **反向加固 ts-food-service**（incident-only = RC fallacy）|
| R36 think | "ts-food Error spans avg 3.68s" → 加固 |
| R44 think 关键 | excerpt: "**Missing ts-train-food-service in Failing Traces**: trace 2139559... 19 error spans, services present: loadgen, ui-dashboard, ts-food-service, **ts-train-food-service NOT present**" → **agent 识别了 GT 缺席但解读为 ts-food-service 内部失败**（"request never reached train-food"）|
| R49 think | "ts-food p99 latency: 04:04:15 0.25s → 04:05:15 **10.0s**" → 加固 caller |
| R53 think 重申 | "Missing ts-train-food-service" 维持解读 |
| 🔥 R54 query GT metric | `SELECT metric, AVG(value) FROM abnormal_metrics WHERE service_name='ts-train-food-service' GROUP BY metric LIMIT 20` → **关键 cpu 11.88x metric 因 LIMIT 20 + 无 ORDER BY ratio 被淹没** |
| R55 query GT normal metric | 同上 |
| R56 query GT hubble | "p99 0.04975s at 04:04:30" → 看到**单点低值** → 当 healthy（没看 distribution）|
| R59 think | "ts-food p99 10s peak" → 完全锁定 ts-food |
| R60 query GT span status | "ts-train-food span 全 Unset" → 当 healthy |
| R61-66 trace count | 476 vs 466 → "GT 流量 normal" → 加固 healthy 判断 |
| R73 final commit #1 | ts-food-service ❌ |
| 🚨 R73 conc M8+M1（中文）| "反例隔离 + 排名靠前不一定 RC" |
| R74-78 query | normal vs abnormal log error counts → ts-food incident-only 19 SEVERE → 反向加固 |
| R79-85 think | "ts-cancel-service Unset → 排除", "log error counts only ts-food incident-only" → 锁死 |
| R85 final | commit `ts-food-service` ❌（不变）|

**v4 干预实际效果**：
- mid M6 baseline 对比 ⚠️ 跑了 → 反向加固（normal=0, abnormal=57 = INCIDENT-ONLY）
- mid M5 silent service ⚠️ **触发了正确动作**：agent R44/R53 识别 "Missing ts-train-food in failing traces"，R54-65 **主动查 GT metric**——但因下面三联失败：
  1. **query 无 ORDER BY ratio**：LIMIT 20 让 container.cpu 11.88x 被淹没，agent 看到的 metric 列表里没 cpu
  2. **单点值判断 healthy**：hubble p99 0.05s 单点值 → "GT 看起来 normal"
  3. **status_code Unset 当 healthy**（同 case 1459/1495）：GT span 全 Unset → "GT healthy"
- conc M8 counterfactual ❌ 单向反向加固（normal=0 vs abnormal=19 = INCIDENT-ONLY = RC）
- conc M1 secondary 概念命中（"排名靠前不一定 RC"）但 agent 把 cancel-service 排除当成"反例验证通过"

### 8. 失败模式

| 失败链 | baseline | v4 |
|---|---|---|
| chronic noise 锚定 | ❌ rabbitmq UnknownHostException 256→220 | ✅ mid 后 dismiss rabbitmq |
| first-error timestamp fallacy | ❌ ts-food 04:04:16 当 origin | ❌ 同 + R44 加固 |
| 503 message provenance 误读 | - | ❌ ts-food 19 条 503 当 caller 自身 |
| silence-as-health | ❌ GT 完全不在候选 | ⚠️ **agent 主动查 GT metric 了但解读错** |
| 没查 specific metric (cpu/restart 排序) | ❌ | ❌（查了但 LIMIT 20 + 无 ORDER BY 淹没）|
| status_code Unset = healthy | ❌ | ❌ R60 加固 |
| **单点 metric 值当 distribution** | - | ❌ hubble p99 0.05s 单点当 healthy |
| **survivor bias 误读** | - | ❌ GT 端点 avg 0.17-0.53x agent 没怀疑反向 |
| F1 维度选错 | - | ⚠️ M5 silent service 触发查询动作但 query 形式错 |
| F2 confirmation bias | - | ❌ baseline 对比 + counterfactual 都反向加固 |
| F3 drift（rabbitmq → food） | - | ❌ noise-shift 而非真翻盘 |
| F5 conc 反向加固 | - | ❌ chronic check 误用（incident-only = RC）|

主要失败模式：
- baseline：**chronic noise 锚定（rabbitmq）+ first-error timestamp fallacy + literal "UnknownHostException" interpretation + silence-as-health + 没查 specific metric**
- v4：**F3 drift 到另一个 noise**（rabbitmq → food-service，仍是 caller 锚定）+ **F2 confirmation bias**（baseline 对比 + counterfactual 都反向加固）+ **关键新失败模式**：agent **主动查了 GT metric** 但因 query LIMIT 20 + 单点值 + Unset 三联误读 → "正确动作 + 错误解读"

跟前 4 个 case 比较的新维度：
- case 2713/3760/4081：agent 全程**没查** GT metric → silence-as-candidate 黑洞
- **case 4363：agent 查了 GT metric 但解读错** → **query 形式 fallacy**

### 9. 中间件如何提示能翻转

需要的 advisor 维度：
- **specific metric 强制 SQL 模板（升级版）**（case 33/1495/2713/3760/4081 已记 + 4363 加强）：仅"查 metric"不够，必须**强制 ORDER BY ratio DESC** 的 SQL 模板：
  ```sql
  WITH n AS (SELECT service_name, AVG(value) v FROM normal_metrics WHERE metric='container.cpu.usage' GROUP BY 1),
       a AS (SELECT service_name, AVG(value) v FROM abnormal_metrics WHERE metric='container.cpu.usage' GROUP BY 1)
  SELECT n.service_name, ROUND(a.v/NULLIF(n.v,0),2) ratio FROM n LEFT JOIN a USING (service_name) ORDER BY ratio DESC LIMIT 10
  ```
  case 4363 中 agent R54 查了 train-food metric 但 LIMIT 20 + 没 ORDER BY ratio 让 cpu 11.88x 被淹没——必须给完整 SQL 模板
- **distribution > 单点值规则**（新维度，case 4363 暴露）：advisor 看到 agent 用单时点 metric 值（"hubble p99 0.05s at 04:04:30 → healthy"）做判断时强制反例——必须看 abnormal 期 distribution（avg / p50 / p95 / p99 over time window），单点值不能当 healthy 证据
- **status_code Unset ≠ healthy 反例**（case 1459/1495 已记 + 4363 加强）：agent 看到 candidate trace span 全 Unset 时不能当 healthy 排除证据——必须配合 specific metric 验证
- **survivor bias 警告**（新维度，case 4363 暴露）：agent 看到 candidate service avg duration **下降**（ratio < 1.0）时不能当 healthy 证据——可能是失败请求没 export，剩下的快路径被采样；必须查 trace count 是否减少 + p99 distribution
- **chronic literal 反例**（新维度，case 4363 暴露 + case 1218/4081 已部分记）：advisor 看到"UnknownHostException ts-rabbitmq" / "DNS resolution failure" / "Connection refused" 类字面 ERROR 时强制 chronic check：normal 期同 message 的频率 → ratio < 1.5x 必须 dismiss
- **literal log message dismissal**（新维度）：trainticket 数据集长期存在的 chronic logs 应内置黑名单（rabbitmq UnknownHostException, ts-rabbitmq Name or service not known 等）—— advisor 看到 agent 锚 chronic message 时强制反向
- **Missing in failing trace 反向解读**（新维度，case 4363 暴露）：当 agent 识别"X service missing in failing traces"时，advisor 应强制反向假设——missing 可能是因为 X 是 RC（被 chaos 让 span 没 export 或 caller timeout 没继续调）而非"caller 内部失败"；强制配合 X 的 specific metric 验证
- **caller p99 飙升 ≠ caller 是 RC**（新维度，case 4363 暴露）：agent 看到 caller p99 飙升时不能加固 caller，应反向追问"caller 在等谁"——查 caller 调用链下游服务的 specific metric

最有效组合：**specific metric ORDER BY ratio 强制 SQL 模板 + Missing in failing trace 反向解读 + chronic literal 黑名单**——三步：
1. 全局 container.cpu ratio 排序立即看到 ts-train-food 11.88x 孤立
2. R44 "Missing ts-train-food in failing traces" 反向解读 → 强制查 ts-train-food cpu/restart
3. RabbitMQ UnknownHostException 字面 dismiss（chronic 黑名单）
case 4363 直接翻盘。

### 10. 中间件代码层面问题

- mid M5 silent service 触发了**正确的查询动作**（R44 识别 GT 缺席 + R54 查 GT metric）但**query 形式不够 prescriptive**：advisor 文本只说"沉默本身也是一种信号"，agent 用 LIMIT 20 + 没 ORDER BY ratio 的 query 错过 cpu 11.88x——必须给完整 SQL 模板
- mid M6 baseline 对比 ❌ **反向加固**（同 case 1459/1495/3760）：agent 把 normal=0/abnormal=57 当 incident-only RC，advisor 缺少"incident-only 在 caller-callee 模式下不证明 RC"硬规则
- conc M8 counterfactual ❌ 单向（同 case 3760/4081）：advisor 文本"如果候选健康，其他异常会消失吗" → agent 把 chronic check 当 counterfactual 站立
- conc M1 secondary（"排名靠前不一定 RC"）概念命中，但 agent 把 ts-cancel-service 排除当反例验证通过——M1 维度需要更具体的 SQL 模板（"全局 container.cpu / restart ratio 排序找排名外的孤立 outlier"）
- **中文输出**两次（mid + conc 都中文）：dimension_cards.py 模板国际化问题
- 干预次数 2 + post_intervention 43/12 round 都用上了，**质量不够**——agent 听话执行但 query 形式错位

### 11. 判断

- 数据完整性：✅
- chaos 生效：⚠️ 物理生效（container.cpu 11.88x + restart 0→1 + cold-start log + 1m40s silent gap），**设计语义部分生效**（restTemplate 是 init-only @Bean，端点 distribution 反向 0.17-0.53x survivor bias）；同 case 1495 模式
- 盲区类型：**(b) 框架盲区**（caller 锚定 + chronic literal + 单点 metric 解读 + status Unset = healthy 四联）+ **(d) 中间件代码问题**（query SQL 模板不够 prescriptive + 中文输出）
- 失败模式：baseline = **chronic noise 锚定（rabbitmq）+ first-error timestamp + literal "UnknownHostException"**；v4 = **F3 drift 到 noise**（rabbitmq → food-service，仍 caller）+ **F2 confirmation bias**（baseline 对比 + counterfactual 都反向加固）+ **关键新模式："正确动作 + 错误解读"**（agent 查了 GT metric 但 LIMIT 20 / 单点值 / Unset 三联误读）
- 给 v4.1：(1) **specific metric 强制 ORDER BY ratio SQL 模板**（不能只说"查 metric"）；(2) **distribution > 单点值规则**（agent 用单时点 hubble 0.05s 当 healthy 时强制反例）；(3) **survivor bias 警告**（service avg ratio < 1.0 不能当 healthy）；(4) **Missing in failing trace 反向解读**（强制查"missing 服务" specific metric）；(5) **chronic literal 黑名单**（rabbitmq UnknownHostException 等内置 dismiss）；(6) **caller p99 飙升 → 查 callee specific metric**（不加固 caller）

### 12. causal_graph 正确性检验

❌ **container 层节点 state 错标**（service-level GT 仍正确，但比 case 2713/4081 严重）：
- container|ts-train-food-service `[high_memory]` —— **single label 错标**：实测 container.memory.* **全 1.0-1.09x 不变**（mem_type=2 direct memory），实际主导是 container.cpu **11.88x**；causal_graph **完全漏掉 high_cpu** 且**漏掉 restarting**（实测 restart 0→1 + 04:05:40 cold-start log）；这是比 case 1218/1459/1495/3760/4081 更严重的错标——单标签且方向错
- pod|ts-train-food-service-5975fbbccb-46l5t `[high_memory, high_cpu, healthy, high_gc_pressure]` —— pod 层补回了 high_cpu ✅，但仍误标 high_memory ❌（同 case 1218/1459/1495/3760 mem_type=2 模式），high_gc_pressure ⚠️ 间接化牵强（jvm.cpu 1.73x 弱，无 GC 实证），healthy 多时刻
- service|ts-train-food-service `[unknown]` —— 不评判
- span 层 missing_span ✅（restart silent gap 物理一致），但**所有 GT span 全标 healthy + 没标 high_avg_latency / high_p99_latency**——这反而**正确反映**了端点 distribution 反向（avg 0.17-0.53x survivor bias，p99 不升）；causal_graph 在 span 层正确反映了"chaos 物理生效但端点表现弱"的实际情况
- cascade ts-food-service span `[high_avg_latency, high_p99_latency, high_error_rate, healthy]` ✅（avg 11.84x p99 10s 503 19）
- cascade ts-ui-dashboard / loadgenerator `[high_avg_latency, high_p99_latency, timeout, healthy]` ✅（avg 1.62x）
- **本案 causal_graph 错标程度排名**：container 层 single high_memory + 漏 high_cpu/restarting → 比 case 1218/1459/1495/3760 严重，比 case 2713/4081 严重；同 case 4081 模式（pod 层 high_memory 误标）但本案 container 层也错（case 4081 container 层 [high_cpu] 单标签是对的）

case 4363 完毕。

---

## Case 4375 · `ts3-ts-travel2-service-container-kill-72qrd2` · ContainerKill on ts-travel2-service

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 4375 |
| GT 根因 | `ts-travel2-service` |
| theme | T2_Blame-the-Messenger |
| tier | stable |
| baseline pred | `ts-route-plan-service` ❌ |
| v4 pred | `ts-ticket-office-service` ❌ |
| baseline qpf / v4 qpf | 51 / 97 |
| 干预 | mid M6+M7 @round 30 / conc M8+M5 @round 78 |
| transition | wrong → wrong（且 v4 mid 已命中 GT，conc 把它推走了） |

### 2. GT 注入

```
fault_type: 2 = ContainerKill (PodChaos)
display_config:
  duration: 4
  injection_point:
    app_label: ts-travel2-service
    container_name: ts-travel2-service
    pod_name: ts-travel2-service-85bd8b46-crdwh
  namespace: ts
ground_truth:
  service: [ts-travel2-service]
  container: [ts-travel2-service]
  pod: [ts-travel2-service-85bd8b46-crdwh]
```

### 3. chaos 机制

ContainerKill 把 ts-travel2-service 容器进程 SIGKILL，kubelet 重启容器（pod 不变名但 hash 变 — 注入 pod 是 `85bd8b46-crdwh`，重启后是 `8557fd66df-mqfrk`）。物理后果：
- **container.cpu.usage 6.52x、k8s.pod.cpu.usage 5.46x**：JVM cold-start CPU 飙升
- **k8s.pod.memory.page_faults 1.76x**：cold-start 大量 page in
- **container.memory.working_set 0.86x、queueSize 0.70x**：旧的 heap/queue 还没爬回去（计数器 reset）
- **restart counter 0→1**：标志性指纹
- **hubble HTTP p50/p95/p99 全 NaN**：流量短暂中断
- **jvm.system.cpu.load_1m 0.23x（28.67→6.71）**：1 分钟均值新 pod 还没爬到老值（重启反而显得"清闲"——容易 mask）

### 4. 调用树（normal 期实测）

```
loadgenerator
  └─ ts-ui-dashboard
      ├─ /api/v1/travelplanservice/travelPlan/minStation
      │   └─ ts-travel-plan-service
      │       └─ ts-route-plan-service
      │           └─ ts-route-service / ts-travel-service / [ts-travel2-service ◀ GT 间接被调]
      └─ /api/v1/travel2service/trips/left
          └─ ts-travel2-service          ◀── GT (chaos target)
              ├─ ts-route-service
              └─ Mongo SELECT ts.trip2 / Trip
```

### 5. 沿调用链从根因到 SLO 的逐节点变化

#### chaos 直接证据（ts-travel2-service 自己）

| 维度 | normal | abnormal | ratio | 含义 |
|---|---|---|---|---|
| restart counter (max) | 0 | 1 | — | ✅ ContainerKill 标志 |
| container.cpu.usage | 0.124 | 0.809 | **6.52x** | ✅ cold-start |
| k8s.pod.cpu.usage | 0.149 | 0.811 | 5.46x | ✅ |
| k8s.pod.memory.page_faults | 178k | 314k | 1.76x | ✅ cold-start page in |
| container.memory.working_set | 8.11e8 | 6.99e8 | 0.86x | ✅ heap reset 没爬回 |
| queueSize | 48.4 | 33.7 | 0.70x | ✅ |
| jvm.system.cpu.load_1m | 28.7 | 6.71 | 0.23x | ⚠️ 1 分钟均值反而下降 |
| hubble_http_request_duration_p50/p95/p99 | 0.064/0.32/0.84 | NaN | NaN | ✅ traffic 中断 |

#### 端点级 duration（GT 服务自己）

| span | n_avg | a_avg | ratio_avg | n_max | a_max |
|---|---|---|---|---|---|
| Travel2Controller.getTripsByRouteId | 4.4 | 21.6 | 4.9x | 17 | **560** |
| TripRepository.findAll | 3.8 | 17.7 | 4.7x | 30 | **1459** |
| POST /trips/routes | 6.1 | 24.2 | 4.0x | 25 | **563** |
| SELECT Trip | 2.7 | 7.5 | 2.8x | 820 | 1414 |
| TripRepository.findByTripId | 5.4 | 10.9 | 2.0x | 821 | 1615 |
| POST /trips/left | 177.4 | 154.3 | 0.9x | 2529 | 2850 |

注意：**service avg 反而下降 0.85x（幸存者偏差）**，因为大调用量端点 `/trips/left` ratio 0.9x 把均值压低；端点级 distribution 才暴露真信号。

#### 上游 cascade

| service | trace_count_ratio | duration_ratio | log_SEVERE_normal→abnormal |
|---|---|---|---|
| ts-travel-plan-service | 0.85 | **1.15x**（最高） | 4 SEVERE |
| ts-route-plan-service | n/a (calls go down) | n/a | **0 → 64 SEVERE**（503 Connection refused upstream） |
| ts-route-plan-service trace Error count | — | — | 192（最高） |

#### SLO 表现

loadgenerator HTTP `/travel2service/trips/left`: duration ratio 升高、status 出现 timeout（causal_graph "high_avg_latency, high_p99_latency, timeout"）。

#### caller-callee edge ratio（NetworkChaos 排除）

ts-route-plan-service → ts-travel2-service: 0.820（常规 cascade attenuation，**不是 NetworkChaos 的 <0.01**），证实是 ContainerKill 而非 NetworkBandwidth/NetworkPartition。

### 6. baseline 完整推理（无中间件）

baseline 51 round → `ts-route-plan-service` ❌

| Round 段 | 行为 | 关键决策 |
|---|---|---|
| R1-12 | schema discovery + abnormal log overview | 先看到 ts-food-service 210 ERROR、ts-order-service 89 ERROR、ts-preserve-service 89 ERROR |
| R13-25 | 看 trace error count 排名 | "ts-route-plan-service: 192 Error traces (highest)" |
| R26-38 | 跟一条 trace `a5da0514` | minStation 端点 → ts-route-plan-service Error |
| R39-44 | 看 ts-route-plan-service log | 64 条 SEVERE 全是 "503 Service Unavailable: upstream connect error... Connection refused" |
| R45-50 | timeline | ts-route-plan-service first SEVERE 23:02:45，ts-travel-plan-service first 23:02:58 |
| 🔴 R51 final | "Root Cause: `ts-route-plan-service`" | "has the most error traces (192) + first SEVERE 23:02:45 + 503 Connection refused" |

**baseline 失败子模式**：
1. **503 message provenance 误读**：把"上游报告 503 Connection refused"当 RC，没意识到这是 caller 在抱怨它的 downstream（ts-travel2-service）不可达
2. **first-error timestamp fallacy**：用 timeline 第一个 SEVERE 推 RC，但 first-error 服务通常是 cascade caller
3. **chaos 物理证据完全没查**：51 round 里**没查任何 service 的 metric**（restart counter / cpu / memory），停留在 trace + log 层

### 7. v4 推理路径（有中间件）

v4 97 round → `ts-ticket-office-service` ❌（**conc 干预把已命中 GT 的预测推走了**）

| Round 段 | 行为 | 关键决策 |
|---|---|---|
| R1-29 | 跟 baseline 几乎一样 | 锚 ts-route-plan-service + 503 message |
| 🚨 R30 mid M6+M7 | "do baseline contrast + check runtime metrics" | agent 复述："The advisor is correct. Compare abnormal vs normal logs + check metrics for resource issues" |
| R31-50 | baseline 对比 + metric 查询 | 浮现 chronic check（log dedup）+ 开始查 metric |
| R51-65 | 查 restart counter | "Container restarts detected: ts-ticket-office-service: 3 restarts (avg and max), ts-travel2-service: 1 restart" |
| R66-77 | 收口验证 | line 247 reflection：**"Root Cause: ts-travel2-service container restart"** ✅ |
| 🟢 R78 final #1 | msg_idx=157 commit | "Root Cause Service: `ts-travel2-service`" ✅（**这一步本来已经翻盘**） |
| 🚨 R78 conc M8+M5 | counterfactual + silence-as-health 反例 | 干预紧跟在 final #1 之后再触发 |
| R79 反思 | think_tool counterfactual | "If ts-travel2-service had NOT restarted, would errors still occur?... ts-travel2-service doesn't appear in this specific trace's downstream calls" |
| R80-92 | 重新看 trace + log + restart timeline | 发现 ts-route-plan-service first SEVERE 23:02:45 vs ts-travel2-service restart 23:02:46（差 1.28 秒）|
| R93 reflection | 🔴 锚点切换瞬间 | "ts-route-plan-service errors STARTED BEFORE ts-travel2-service began restarting!" |
| R94 | restart event 排序 query | 看到 ts-ticket-office-service value=3.0 在排序中 |
| R95 reflection | 把 restart=3 当 "highest" | "ts-ticket-office-service: 3 restarts (highest)" — **没意识到这是 normal 期就 =3 的 chronic baseline** |
| R96-97 | silence 验证 | ts-ticket-office-service 0 logs / 0 traces — 当成 silence-as-failed |
| 🔴 R97 final #2 | msg_idx=197 commit | "Root Cause: `ts-ticket-office-service` container instability (3 restarts) + Silent Failure (ZERO logs/traces)" ❌ |

**v4 干预实际效果**：
- mid M6+M7 ✅：成功引导查 baseline + runtime metric → 浮现 ts-travel2-service restart=1 + 一度命中 GT
- conc M8+M5 ❌：counterfactual + silence-as-health 反例**翻车**——agent 用 timestamp fallacy（1.28 秒差）推翻"travel2 是因"，又把 chronic restart=3 + silent service 当"hidden RC"

### 8. 失败模式诊断

| 失败链 | baseline | v4 |
|---|---|---|
| 锚点轨迹 | 一直锚 ts-route-plan-service（503 message） | route-plan → **travel2-service ✅** → ticket-office-service ❌ |
| chaos 物理证据 | ❌ 51 round 没查 metric | ✅ 查到 restart=1 但被 conc 推翻 |
| timestamp 推理 | first-error timestamp fallacy | first-error timestamp fallacy + 1.28 秒差当因果方向 |
| chronic check | 没做 | mid 后做了 log/metric chronic 但 **restart counter chronic 没做** —— ticket-office-service normal 期 restart=3，abnormal=3，不变 |
| silence 处理 | — | silence-as-health 反例**错向应用**：把 normal 期就完全 silent 的服务当"hidden RC" |

**主要失败模式**：
- baseline: **503 message provenance 误读** + **first-error timestamp fallacy**
- v4: **F5 conc 反向加固**（M8 counterfactual + M5 silence-as-health 把已命中的 GT 推到 phantom anchor）

### 9. 中间件如何提示能翻转（保住 mid 后已命中的 GT）

| 维度 | 触发条件 | 干预语 |
|---|---|---|
| **restart counter chronic check** | conc 阶段如果 agent 引用 "X 服务有 N restart" 作为依据，强制做 normal 期同样 query 验证是否 chronic baseline | "Before treating restart counter as event evidence, query the same metric in the normal window: if normal period also shows the same value, it's a chronic baseline (e.g., service deployed to a node that historically had N restarts), not an incident signal." |
| **timestamp granularity guard** | conc 阶段如果 agent 用 "first-error 在 restart 之前 N 秒" 推因果方向，提醒 metric scrape 后置性 | "Container restart counter is a post-event scrape metric — it can lag behind the actual SIGKILL by one scrape interval (10-30s). Sub-minute timestamp differences between log errors and restart counter increment do not establish causal direction; the chaos event itself can produce caller-side errors before the kubelet reports the restart." |
| **silence baseline test** | M5 silence-as-health 反例应用前，先验证 normal 期是否同样 silent | "Before treating silence as 'hidden failure', verify the service's normal-period footprint: if traces=0 AND logs=0 in normal window too, the service is simply not on the critical path of the load mix, not a silent crash victim." |
| **mid → conc soft-lock** | 当 mid 干预后 agent 已 commit 一个候选并写出物理证据（restart/cpu/memory ratio），conc 干预不应触发"全面颠覆"语气，而是"补充验证 + 同纬度对比" | conc 不再用 "before you commit, do counterfactual" 这种 invitation-to-flip 语气；改为 "you have physical evidence (restart=1, cpu 6.5x). Before committing, verify two things in parallel: (a) any other service shows comparable restart-counter increment relative to its own normal baseline, (b) the timing offset between caller errors and your candidate's restart is within scrape granularity." |

最有效组合：**restart counter chronic check + timestamp granularity guard** —— 直接斩断 "restart=3 highest + first-error before restart" 这两个错锚点。

### 10. 中间件代码层面问题

- **conc 干预 timing 严重**：v4 在 mid 后已经做对了（msg_idx=157 final 是 ts-travel2-service ✓），conc 立即在 round 78 触发，把已经收敛的正确预测重新打开。这是 **conc 触发条件 leakage**——应该有"如果 mid 后 agent 已经 commit 物理证据型 RC（具备 restart/specific-metric ratio）则跳过 conc"的护栏。
- **M8 counterfactual 卡片语气过强**：当前 conc M8 文本 "Before you commit, do one counterfactual pass" 是开放性 invitation-to-flip，没绑硬性的"counterfactual 必须用 normal-baseline 校准"的检查。agent 会自然滑向"如果我假设 candidate 没死会怎样"的弱 reasoning，而不是用 normal vs abnormal 数据反演。
- **M5 silence-as-health 卡片缺反例的反例**：当前 secondary M5 提醒 "silent ≠ healthy"，但没提醒 "silent in abnormal AND silent in normal = not on critical path"。这让 agent 把这条提示错向应用到 normal-period-silent 的服务上。
- **干预次数 2 + 维度 4 个**（M6/M7/M8/M5）足够，但 conc 维度选择是反向的——这个 case 应该在 conc 强化"physical evidence > timeline/silence reasoning"的优先级，而不是引导做 counterfactual。
- **mid → conc 之间 47 round 太长**：mid 在 round 30，conc 在 round 78，agent 中间已经收敛。如果 conc 触发条件考虑"距 mid 的 round 差 + agent 收敛信号（已写出 specific-metric ratio）"会更稳。

### 11. 判断

- **数据是否完整**：✅（restart 0→1 + container.cpu 6.52x + page_faults 1.76x + hubble NaN + 端点 distribution 4-5x，多重物理证据齐）
- **chaos 是否生效**：✅ 必然生效（ContainerKill 4 秒，物理 SIGKILL 直接观测到 restart 增量 + JVM cold-start 三件套）
- **真假盲区分类**：(b) **框架盲区** —— 数据齐、agent 也查到关键证据（v4 mid 后已命中 GT），但 conc 干预把它推走了。这是 v4 中间件代码层面 + advisor 维度策略的问题，不是数据/框架/chaos 问题。
- **失败模式归纳**：
  - baseline 失败模式：**503 message provenance 误读** + **first-error timestamp fallacy** + **不查 chaos 物理 metric**
  - v4 失败模式：**F5 conc 反向加固**（mid 已翻盘，conc 把它推回 phantom anchor）+ **chronic restart counter 当事件信号** + **silence-as-failed 错向应用到 normal-period-silent 服务**

- **给 v4.1 的提示**：
  1. **conc 应有"已收敛"短路**：如果 mid 后 agent 已写出 specific-metric ratio 型证据并 commit，conc 干预改为"轻量补强"语气（保护已正确的预测不被 counterfactual 颠覆），而非"重做 counterfactual"
  2. **restart counter / cpu spike 等"事件计数器型"信号**强制配套 normal-baseline 比对：abnormal 期看到 restart=N 不算证据，normal 期 restart<N 才算
  3. **silence-as-failed 反例必须双轨验证**：silent in abnormal && silent in normal → not on critical path（排除）；silent in abnormal && active in normal → 才是 hidden failure 候选
  4. **timestamp 因果方向规则**：post-event scrape metric（restart、page_faults、hubble NaN）的时间戳不能用来推因果方向，需用"chaos 注入时刻"或物理事件起点（log "Starting App"）

### 12. causal_graph 正确性检验

| 节点 | state | 实测 | 判定 |
|---|---|---|---|
| container\|ts-travel2-service | ["high_cpu"] | container.cpu.usage 6.52x | ✅ |
| pod\|ts-travel2-service-8557fd66df-mqfrk | ["high_cpu", "high_gc_pressure", "healthy"] | k8s.pod.cpu.usage 5.46x；jvm.system.cpu.utilization 1.08x（gc_pressure 弱但 cold-start 期 GC 物理上活跃，方向对）；healthy 是多时刻合并 | ✅（gc_pressure 证据偏弱但方向一致） |
| service\|ts-travel2-service | ["unknown"] | service avg 0.85x（幸存者偏差），service-level 看不出，标 unknown 合理 | ✅ |
| span\|ts-travel2-service::TripRepository.findByTripId | high_avg_latency / high_p99_latency | a/n=2.0x avg, max 821→1615 | ✅ |
| span\|ts-travel2-service::TripRepository.findAll | high_avg_latency / high_p99_latency | a/n=4.7x, max 30→1459 | ✅ |
| span\|ts-travel2-service::Travel2Controller.getTripsByRouteId | injection_affected / high_p99_latency | a/n=4.9x, max 17→560 | ✅ |
| span\|ts-route-plan-service::POST /minStopStations | high_error_rate | log 64 SEVERE + 192 trace Error | ✅ |
| span\|ts-travel-plan-service::POST /minStation | high_error_rate / high_avg_latency / high_p99_latency | trace count -15%, ratio_avg 1.15x，service-level 最高 | ✅ |
| span\|ts-ui-dashboard::POST /trips/left | high_error_rate / high_avg_latency / high_p99_latency | loadgen 端 timeout + ts-ui-dashboard log error | ✅ |
| span\|loadgenerator::HTTP POST /trips/left | high_avg_latency / high_p99_latency / timeout | loadgen 看到 timeout | ✅ |
| root_cause: container\|ts-travel2-service | ["unknown"] | root_cause 节点 state 固定为 unknown 占位（不是错标） | ✅ |

causal_graph 节点核对通过。

case 4375 完毕。

---

## Case 4463 · `ts4-ts-food-service-container-kill-lv5htg` · ContainerKill on ts-food-service · ⚠️ GT label 错配

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 4463 |
| 评测系统 GT 字段 | `ts-config-service` |
| **injection_point + causal_graph root_cause** | **`ts-food-service`** |
| theme | T2_Blame-the-Messenger |
| tier | ultra_hard |
| baseline pred | `ts-food-service` ❌（**实际跟 injection 一致**，但被评测判错） |
| v4 pred | `ts-ui-dashboard` ❌（cascade victim） |
| baseline qpf / v4 qpf | 59 / 81 |
| 干预 | mid M6+M5 @round 30 / conc M8+M2 @round 69 |
| transition | wrong → wrong（**evaluation label bug 类** —— 跟 case 339/2130/3868 同类） |

### 2. GT 注入

```
fault_type: 2 = ContainerKill (PodChaos)
display_config:
  duration: 4
  injection_point:
    app_label: ts-food-service           ← 注入点 = ts-food-service
    container_name: ts-food-service
    pod_name: ts-food-service-5fd45cf66d-nljst
  namespace: ts
ground_truth:
  service: [ts-config-service]           ← ❌ 跟 injection_point 矛盾
  container: [ts-config-service]
  pod: [ts-config-service-7c55667486-2h4vp]
```

**causal_graph.json** 7 个节点全部围绕 ts-food-service：
- root_cause: `container|ts-food-service`（**跟 injection_point 一致，但跟 ground_truth 字段矛盾**）
- 节点：`container|ts-food-service` → `pod|ts-food-service-64d454885b-5g46k` → `service|ts-food-service` → 端点 span → `span|ts-ui-dashboard::/foodservice/...` → `loadgenerator::HTTP /foodservice/...`
- **图里没有任何 ts-config-service 节点**

### 3. chaos 机制

ContainerKill 把 ts-food-service 容器进程 SIGKILL（4 秒），kubelet 重启容器（pod hash 从 `5fd45cf66d-nljst` 变成 `64d454885b-5g46k`）。物理后果：
- restart counter 0→1
- container.cpu.usage 9.20x（cold-start）
- k8s.pod.cpu.usage 10.81x
- k8s.pod.memory.page_faults 1.74x（cold-start page in）
- trace count 2405→1822（-24%）
- log count 2342→1923（-18%）

**ts-config-service 实测完全正常**（不是 chaos 间接级联目标）：

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| traces | 19086 | 19215 | 1.01x |
| logs | 7634 | 7686 | 1.01x |
| restart counter | 0 | 0 | — |
| 所有 metric 最高 ratio | filesystem.usage 1.59x（磁盘累积，非异常） | | |
| 任何 log 提到 "config-service" | 0 条 | 0 条 | — |

**结论：GT label 错配**——评测系统拿 `ts-config-service` 比对 agent 输出，但实际 chaos 注入点和 causal_graph root_cause 都指向 `ts-food-service`。

### 4. 调用树（normal 期实测）

```
loadgenerator
  └─ ts-ui-dashboard
      └─ /api/v1/foodservice/foods/{date}/{startStation}/{endStation}/{tripId}
          └─ ts-food-service                ◀── 注入点 + causal_graph root_cause
              ├─ ts-travel-service          (route info)
              └─ ts-station-food-service / ts-train-food-service  (foodstore data)
```

ts-config-service 是配置型服务，被多个服务依赖，但跟这次 chaos 调用链**无直接关系**（log 0 提及）。

### 5. 沿调用链从根因到 SLO 的逐节点变化

#### chaos 直接证据（ts-food-service 自己）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| restart counter (max) | 0 | 1 | ✅ ContainerKill 标志 |
| container.cpu.usage | 0.075 | 0.694 | **9.20x** |
| k8s.pod.cpu.usage | 0.074 | 0.801 | 10.81x |
| k8s.pod.memory.page_faults | 171k | 298k | 1.74x（cold-start page in） |
| jvm.cpu.recent_utilization | 6e-4 | 8e-4 | 1.37x |
| trace count | 2405 | 1822 | 0.76x |
| log count | 2342 | 1923 | 0.82x |
| log "Get Food Request Failed" count | 383 | 311 | **0.81x** ⚠️（chronic！） |

**关键陷阱**：业务层 ERROR log（"Get the Get Food Request Failed!" 调用 train-food-service 失败）在 normal/abnormal 都存在，**ratio 0.81 反而下降**——是 train-food-service 长期挂的 chronic noise，不是 chaos 信号。chaos 的真信号在 **container.cpu / restart / page_faults** 层。

#### ts-food-service 端点 duration

| span | 实测 |
|---|---|
| FoodController.getAllFood | causal_graph state: high_avg_latency / high_p99_latency / injection_affected ✓ |
| http.server.request.duration | normal max 0.3-0.4s → abnormal max 1.9s（baseline trajectory 实测）|

#### ts-ui-dashboard cascade（v4 锚定的"信号"）

- 224 ERROR logs in abnormal vs 0 in normal
- 全部是 Caddy reverseproxy: `"dial tcp 10.102.8.75:8080: connect: connection refused"` + 502 Bad Gateway
- 这是 cascade artifact：ts-ui-dashboard 调 ts-food-service 时碰到 ts-food-service 重启窗口连接失败 → 报 502

#### SLO 表现

loadgenerator HTTP `/foodservice/foods/...`: high_avg_latency / high_error_rate / high_p99_latency（causal_graph state）。

### 6. baseline 完整推理（无中间件）

baseline 59 round → `ts-food-service` ❌（评测系统判错，但实际跟 injection_point 一致）

| Round 段 | 行为 | 关键决策 |
|---|---|---|
| R1-12 | schema discovery | |
| R13-25 | 看 abnormal log error 排名 | "ts-food-service 311 errors (highest)" |
| R26-40 | 跟 trace `9870bf00...` | 调用链 loadgenerator → ts-ui-dashboard → ts-food-service → travel/station-food/train-food |
| R41-50 | 看 ts-food-service 异常 metric | http.server.request.duration: normal max 0.3-0.4s → abnormal max 1.9s |
| R51-58 | timeline analysis | ts-ui-dashboard first error 09:17:43，ts-food-service first error 09:18:34（51s 差）—— 但 baseline 仍把 ts-food-service 当 RC |
| 🟢 R59 final | "Root Cause: `ts-food-service`" | "311 errors highest + foodservice API endpoint internal failures + 1.9s latency" |

baseline 选了**按 injection + causal_graph 真实正确**的答案，但 evaluation 用 ground_truth.service = ts-config-service 比对，判 wrong。

### 7. v4 推理路径（有中间件）

v4 81 round → `ts-ui-dashboard` ❌

| Round 段 | 行为 | 关键决策 |
|---|---|---|
| R1-29 | 看 abnormal log + trace | ts-food-service 311 errors highest，ts-ui-dashboard 224 errors 也高 |
| 🚨 R30 mid M6+M5 | baseline contrast + silent service | agent_response_excerpt **空**（没 think_tool 复述） |
| R31-50 | baseline contrast | 🔴 **关键发现**：normal 期 ts-food-service 也有 383 errors → dismiss ts-food-service as chronic |
| R51-65 | 锚定 ts-ui-dashboard | "ts-ui-dashboard: 0 errors normal vs 224 abnormal —— THE key differentiator" + "dial tcp 10.102.8.75:8080: connection refused" + 502 Bad Gateway |
| 🟢 R69 final #1 | "Root Cause: `ts-ui-dashboard`" | 仅基于 log error count diff + connection refused 信号 |
| 🚨 R69 conc M8+M2 | counterfactual + chronic noise 区分 | agent_response_excerpt **空**（没复述） |
| R70-79 | counterfactual SQL | 查 ts-food-service trace count（1822 abnormal）+ 200 status traces 仍存在 |
| R80 reflection | "ts-food-service IS working in abnormal period (has HTTP 200)" | 强化"ts-food-service 没死，所以不是 RC" |
| 🔴 R81 final #2 | `ts-ui-dashboard` ❌ | "ts-ui-dashboard is the ONLY service with NEW errors" |

**v4 整个 81 round **没查任何 ts-food-service 的物理 metric**：
- container.cpu.usage（实测 9.20x）—— 没查
- k8s.container.restarts（实测 0→1）—— 没查
- k8s.pod.memory.page_faults（实测 1.74x）—— 没查

### 8. 失败模式诊断

| 失败链 | baseline | v4 |
|---|---|---|
| 锚定轨迹 | 一直锚 ts-food-service（log error count + 端点慢） | food-service → 中段 dismiss → ts-ui-dashboard |
| chronic check | 没做 | mid 后做了 → ✅ 发现 ts-food-service log 0.81x → ❌ 错误外推到"food-service 不是 RC" |
| 物理 metric | 没查 | 没查（关键：restart 0→1 / cpu 9.20x / page_faults 1.74x 全没查） |
| counterfactual | 没做 | 做了但用错维度——只看 trace count 和 status_code 200 还存在，没看 cpu/restart |

**v4 行为模式（不参与 failure mode 归纳，但记录供参考）**：
- **chronic-log dismiss 越权**：log "Get Food Request Failed" 是 chronic（normal 也有）→ 但这是 ts-food-service 调它的下游 train-food-service 的 caller-side error，跟 chaos 直接证据是不同维度。chronic 应当只 dismiss "看似异常的业务 ERROR log"，不应外推到"该服务整体不是 RC"。
- **cascade artifact 当独占信号**：ts-ui-dashboard "0→224 errors + connection refused" 看似 only-in-abnormal，但其实是 ts-ui-dashboard 调 ts-food-service 时碰到重启窗口报 502 —— **cascade 上游的 reverseproxy 报 connection refused 跟 chaos target 是 perfect cascade，agent 把 reverseproxy 错认为 origin**
- **counterfactual 用错维度**：用 "trace 200 status 还存在" 反证 ts-food-service "is working" —— ContainerKill 4 秒只在窄窗口杀容器，重启后 traces 当然继续，counterfactual 应该看 chaos 窗口的 metric spike

### 9. 中间件如何提示能翻转

⚠️ 由于 GT label 错配，对这个 case 来说**没有"翻转"概念**——baseline 已经按 injection + causal_graph 给出正确答案，v4 反而推走了。但若假设 evaluation label 是正确的（即真要选 ts-config-service），则：

| 维度 | 触发条件 | 干预语 |
|---|---|---|
| **chronic check 范围限定** | M6 baseline contrast 之后，agent 不应基于 log error ratio 0.81 就 dismiss 整个服务，应限定为 dismiss 业务层 ERROR message | "When normal/abnormal log error ratios are similar, dismiss the specific log message as chronic background — but do NOT extend that judgment to dismiss the entire service. The chaos signal may live in a different layer (container/restart/cpu) that you haven't queried yet." |
| **chaos 物理 metric 强制查询** | mid 阶段如果候选是 ContainerKill/PodChaos 类（trace 减少 + log 变少），强制查 `k8s.container.restarts` + `container.cpu.usage` + `page_faults` | "If your candidate shows trace_count or log_count reduction (silence pattern), query its container/pod metrics in parallel: restart counter, container.cpu.usage, k8s.pod.memory.page_faults. ContainerKill leaves restart=1 + cpu spike + page_faults bump as fingerprint." |
| **cascade reverseproxy 排除** | conc 阶段如果候选是 reverseproxy 类（ts-ui-dashboard/Caddy/sidecar）+ 错误是 "connection refused"，强制查 connection refused 的 target IP/port 对应服务 | "Reverse proxy 'connection refused' errors point to the upstream service that's unreachable — the proxy itself is not the origin. Resolve the target IP (e.g., 10.102.8.75:8080) to a service name and check its container/pod state during the same window." |

### 10. 中间件代码层面问题

- **agent_response_excerpt 两次都空**：mid 和 conc 干预后 agent 都没用 think_tool 复述，说明 advisor 文本可能 prompt-position 没让 agent 形成显式反思。需要中间件在干预后强制要求 think_tool 复述。
- **conc M8 counterfactual 让 agent 用错维度**：agent 把"trace 200 status 还存在"当 counterfactual 通过条件，但 ContainerKill 窄窗口注入根本不会让 traces 完全消失。M8 卡片应该更严格：counterfactual 必须用 chaos 窄窗口的 metric ratio（cpu/restart/page_faults），不能用 trace 残存。
- **M2 chronic noise 区分卡片**："One service being a chronic noisemaker doesn't automatically make another service the fault origin" 这句对 —— 但 agent 没 act on it，因为它已经在 mid 用 chronic 判断 dismiss 了 ts-food-service，然后用残存 cascade artifact 锚定 ts-ui-dashboard。M2 应当更早触发或者在 mid 就强调"chronic dismiss 仅限于该 log message，不能外推到整个服务"。

### 11. 判断

- **数据是否完整**：✅（ts-food-service 的 chaos 物理证据齐：restart 0→1 + cpu 9.20x + page_faults 1.74x + trace -24%）
- **chaos 是否生效**：✅ 必然生效（ContainerKill 4 秒物理 SIGKILL 命中）
- **真假盲区分类**：(c) **假盲区 / GT label 错配** —— 跟 case 339/2130/3868 同类。
  - injection_point = `ts-food-service` ✓
  - causal_graph root_cause = `container|ts-food-service` ✓
  - **但 ground_truth.service / correct_answer = `ts-config-service`** ❌（跟 injection 和 causal_graph 矛盾）
  - ts-config-service 实测完全正常（trace/log 1.0x、restart 0/0、log 0 提及 config-service）
- **失败模式归纳**：⚠️ **此 case 不计入 failure mode 归纳**，原因：
  - baseline 选 ts-food-service 实际是按 injection + causal_graph 正确的，但被评测系统判 wrong（label bug）
  - v4 drift 到 ts-ui-dashboard 虽是真实失败行为（chronic-log dismiss + cascade reverseproxy 锚定），但因 GT 本身错配，归纳意义降低
  - 仅记录 v4 行为模式供参考，不进入 v4.1 改进规则的统计
- **给 v4.1 的提示**：
  1. 此类 GT label 错配 case 应在 dataset 层面修复，不应当作 v4 中间件的失败案例进入训练/评估
  2. 但 v4 在此 case 暴露的两个真实问题仍可改进：(a) chronic-log dismiss 不能外推到整个服务、(b) ContainerKill/PodChaos 候选必须强制查 container/pod 物理 metric（restart + cpu + page_faults），不能只看 trace/log 计数

### 12. causal_graph 正确性检验

| 节点 | state | 实测 | 判定 |
|---|---|---|---|
| container\|ts-food-service | ["high_cpu"] | container.cpu.usage 9.20x | ✅ |
| pod\|ts-food-service-64d454885b-5g46k | ["high_cpu", "high_gc_pressure", "high_memory", "healthy"] | k8s.pod.cpu.usage 10.81x ✅；jvm.cpu.recent_utilization 1.37x（gc_pressure 弱但方向对，cold-start 期 GC 物理活跃）；**high_memory 标签证据弱**：working_set/rss 1.01x 几乎正常，page_faults 1.74x 是 cold-start page in 而非内存压力 ⚠️；healthy 多时刻合并 | ⚠️ high_memory 弱标 |
| service\|ts-food-service | ["unknown"] | service avg 看不出（端点级才显著） | ✅ |
| span\|ts-food-service::FoodController.getAllFood | high_avg_latency / high_p99_latency / injection_affected / missing_span | http.server.request.duration normal max 0.3-0.4s → abnormal max 1.9s；trace count -24% | ✅ |
| span\|ts-food-service::GET /api/v1/foodservice/foods/{...} | 同上 | 同上 | ✅ |
| span\|ts-ui-dashboard::/foodservice/foods/... | high_p99_latency / high_avg_latency | cascade 上游 224 errors + 502 | ✅ |
| span\|loadgenerator::HTTP /foodservice/foods/... | high_avg_latency / high_error_rate / high_p99_latency | SLO 端 timeout/502 | ✅ |
| root_cause: container\|ts-food-service | ["unknown"] | root_cause 节点 state 占位（不是错标） | ✅ |

**causal_graph 节点核对通过（service-level 跟 injection 一致），但 ground_truth.service / correct_answer 字段是 `ts-config-service` —— 跟 root_cause/injection_point 矛盾，是 dataset label bug**（chaos 339/2130/3868 类）。pod 节点 high_memory 是弱标，但因 cold-start 期 page_faults 物理上确实活跃，方向不算错；主导 metric 仍是 high_cpu，不属于 case 1218/1459 那种 "high_memory 实测 1.10x 但 high_cpu 16x" 的反向标签错。

case 4463 完毕。

---

**用户确认笔记**：此 case 打标错了（GT label 错配确认）。`ground_truth.service` 字段写 `ts-config-service` 是 dataset label bug，跟 injection_point + causal_graph root_cause = `container|ts-food-service` 矛盾。归入 chaos 339/2130/3868 类的 evaluation label 错配集合，**不参与 failure mode 归纳**。

---

## Case 4617 · `ts5-ts-cancel-service-stress-d8xbsn` · JVMCPUStress (cpu_count=8) on ts-cancel-service

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 4617 |
| GT 根因 | `ts-cancel-service` |
| theme | T3_Noise-Anchor |
| tier | ultra_hard |
| baseline pred | `ts-rabbitmq` ❌ |
| v4 pred | `mysql` ❌ |
| baseline qpf / v4 qpf | 40 / 68 |
| 干预 | mid M6+M7 @round 30 / conc M2+M8 @round 56 |
| transition | wrong → wrong（baseline chronic 锚定 → v4 chronic dismiss 后 drift to 量级太小的 mysql noise） |

### 2. GT 注入

```
fault_type: 27 = JVMCPUStress (JVMChaos)
display_config:
  cpu_count: 8                    ← 8 个 CPU 烧死循环
  duration: 4
  injection_point:
    app_name: ts-cancel-service
    class_name: cancel.service.CancelServiceImpl
    method_name: cancelFromOrder  ← 频繁方法
  namespace: ts
ground_truth:
  service: [ts-cancel-service]
  container: [ts-cancel-service]
  pod: [ts-cancel-service-6cb859955d-bk42f]
  metric: [cpu]
  function: [cancel.service.CancelServiceImpl.cancelFromOrder]
```

### 3. chaos 机制

JVMCPUStress 通过 byte-code 注入在 `cancelFromOrder` 方法触发 8 个 CPU 烧死循环（4 秒）。物理后果：
- container.cpu.usage 从 0.007 → 3.45（**496x**），cpu_limit_utilization 0.0014 → 0.674（near 1.0，**几乎打满 limit**）
- jvm.cpu.recent_utilization 0.0001 → 0.0316（**557x**）
- memory 1.02x（基本不变）—— 证实是 CPU 不是 memory
- restart 0/0（byte-code 注入不让进程死）
- ts-cancel-service abnormal 期 trace 9→0 / log 16→0（**完全 silent on critical path**：CPU 烧满让请求无法返回）
- 上游服务全部慢：ts-station-service 13.11x、ts-food-service 10.54x、ts-order-other 5.31x、ts-auth 3.56x、loadgenerator 3.31x（cancelFromOrder 阻塞调用链）

### 4. 调用树（normal 期实测）

ts-cancel-service 在 normal 期只 9 traces —— 是**低频路径**（cancel 操作不像查询那么频繁）。这是 chaos 难度的关键：

```
loadgenerator
  └─ ts-ui-dashboard
      ├─ /api/v1/cancelservice/cancel/{orderId}/{loginId}
      │   └─ ts-cancel-service::CancelController.cancelTicket  ◀── chaos 注入点
      └─ /api/v1/cancelservice/cancel/refound/{orderId}
          └─ ts-cancel-service::CancelController.calculate     ◀── chaos 注入点
```

由于 ts-cancel-service 是低频且 chaos 让它彻底 silent（trace 9→0），baseline 看 trace ranking 时它根本不出现，silence 容易被错误归因为 "loadgenerator 不调用了"。

### 5. 沿调用链从根因到 SLO 的逐节点变化

#### chaos 直接证据（ts-cancel-service 自己）

| 维度 | normal | abnormal | ratio | 含义 |
|---|---|---|---|---|
| traces | 9 | 0 | 0.00 | ✅ silent on critical path |
| logs | 16 | 0 | 0.00 | ✅ |
| container.cpu.usage | 0.007 | 3.450 | **496x** | ⭐ 主导 chaos 信号 |
| k8s.pod.cpu.usage | 0.007 | 3.370 | 475x | ⭐ |
| k8s.pod.cpu_limit_utilization | 0.0014 | 0.674 | 475x | ⭐ 几乎打满 limit |
| k8s.pod.cpu.node.utilization | 0.0001 | 0.026 | 476x | ⭐ |
| jvm.cpu.recent_utilization | 1e-4 | 0.032 | 557x | ⭐ JVM CPU |
| container.filesystem.usage | 4.67e5 | 3.01e6 | 6.46x | 副效应（JVM stress 期可能 dump） |
| container.memory.* (working_set/rss/usage) | 6.57e8 | 6.70e8 | 1.02x | ✅ memory 几乎不变（区分 CPUStress vs MemoryStress 关键） |
| restart counter | 0 | 0 | — | ✅ byte-code 注入不杀进程 |

#### 端点级 duration（GT 服务）

| span | n_n | a_n | n_avg | a_avg | n_max | a_max |
|---|---|---|---|---|---|---|
| GET /cancel/{orderId}/{loginId} | 1 | **0** | 49.5 | NaN | 50 | NaN |
| CancelController.calculate | 1 | **0** | 16.4 | NaN | 16 | NaN |
| CancelController.cancelTicket | 1 | **0** | 43.9 | NaN | 44 | NaN |
| GET /cancel/refound/{orderId} | 1 | **0** | 26.4 | NaN | 26 | NaN |

abnormal 端点全部 silent —— `causal_graph state` 标 `missing_span` ✓

#### 上游 cascade（service-level ratio_avg）

| service | n_n | a_n | ratio_count | n_avg | a_avg | ratio_avg |
|---|---|---|---|---|---|---|
| ts-station-service | 5692 | 2243 | 0.39 | 3.5 | 45.3 | **13.11x** |
| ts-food-service | 1290 | 492 | 0.38 | 33.2 | 350.3 | 10.54x |
| ts-order-other-service | 6800 | 2520 | 0.37 | 3.3 | 17.6 | 5.31x |
| ts-auth-service | 8620 | 2920 | 0.34 | 23.3 | 83.1 | 3.56x |
| loadgenerator | 5394 | 1855 | 0.34 | 72.8 | 240.6 | 3.31x |
| ts-ui-dashboard | 5394 | 1855 | 0.34 | 72.1 | 232.8 | 3.23x |

所有上游服务 trace count 同比降到 ~0.35-0.39（吞吐量整体掉 60%+），duration ratio 全面升高 —— cancelFromOrder CPU 烧满导致**大量调用阻塞排队**，间接传播到所有上游。

#### baseline 锚 ts-rabbitmq（chronic 验证）

| 维度 | normal | abnormal | ratio |
|---|---|---|---|
| log 含 rabbitmq/redeclare 关键词 | 304 | 226 | 0.74x |

**chronic！abnormal 反而比 normal 少**——RabbitMQ connection failures 是 trainticket 数据集长期存在的背景噪音。

#### v4 锚 mysql（量级验证）

| 维度 | normal | abnormal |
|---|---|---|
| log "mysql/MySQL/CommunicationsException" | 0 | 5 |

虽 only-in-abnormal，但 **5 条量级太小**——是 cascade artifact（上游服务因 CPU 阻塞导致 mysql HikariPool 偶发 timeout 触发 5 条 Aborted connection），不是 origin。

### 6. baseline 完整推理（无中间件）

baseline 40 round → `ts-rabbitmq` ❌

| Round 段 | 行为 | 关键决策 |
|---|---|---|
| R1-15 | abnormal log overview | 发现 ts-notification / ts-delivery 大量 "Failed to check/redeclare auto-delete queue(s)" + "Attempting to connect to: [ts-rabbitmq:5672]" |
| R16-30 | 锚定 RabbitMQ "unavailable" | 没做 normal 期对比，没查 RabbitMQ metric |
| R31-40 | timeline 整理 | 14:21:01 ts-order-service / preserve / food / notification 大量首发错误（实际是 cascade 同时触发） |
| 🔴 R40 final | "Root Cause: `ts-rabbitmq`" | "ts-rabbitmq cannot be reached + multiple services connection failures + Caused By: UnknownHostException: ts-rabbitmq" |

**baseline 失败子模式**：
1. **chronic noise 锚定**：RabbitMQ connection failure 是 trainticket 数据集长期 noise（normal 304 / abnormal 226，反而更少），baseline 没做 contrast 直接当 RC
2. **infrastructure scapegoat**：看到 multiple services 都报 RabbitMQ 错误就归因到共享 infra，但没看 RabbitMQ 自身的 metric/log 是否真有异常
3. **没扫任何 metric**：40 round 全在 log + trace 层，没碰过 container.cpu / restart / cpu_limit_utilization
4. **silent service signal 完全错过**：没看到 ts-cancel-service abnormal=0 traces 是教科书信号

### 7. v4 推理路径（有中间件）

v4 68 round → `mysql` ❌

| Round 段 | 行为 | 关键决策 |
|---|---|---|
| R1-29 | log/trace overview | line 92：💡 **"ts-cancel-service exists in normal traces but NOT in abnormal traces. This means... the cancel service endpoints are not being called at all - they're unavailable"** —— 信号被识别但 reasoning 滑到"loadgenerator 不调用" |
| 🚨 R30 mid M6+M7 | baseline contrast + runtime metric | agent 复述 ✅ "**CRITICAL FINDING: RabbitMQ errors appear in BOTH normal and abnormal logs. This is a chronic background condition, NOT the root cause**" + "I need to look at: Container/pod health metrics for ts-cancel-..."（**显式想查 cancel-service container metric！**） |
| R31-44 | 实际 SQL 路径 | 查了 `k8s.pod.phase`（线性扫所有服务）、log error count by service —— **但实际没去查 ts-cancel-service container.cpu.usage** |
| R45 reflection | line 148 | "ts-cancel-service exists in metrics (has CPU usage data) but NOT in abnormal traces" —— **再次确认有 CPU 数据，但没去 SELECT 实际值** |
| R46-51 | 看 service avg duration ranking | 看到 ts-route-plan-service avg 605ms / ts-travel-plan-service 572ms 是 abnormal 期最高（cascade 中段），但归因为"trace duration 整体升" |
| R52-55 | 转向 mysql | 偶遇 mysql `Aborted connection 219...Got an error reading communication packets` 5 条，立即锚定 |
| R56 reflection | "mysql is having network/communication issues with clients" | drift complete |
| 🟢 R56 final #1 | "Root Cause: mysql" ❌ | |
| 🚨 R56 conc M2+M8 | chronic noise 区分 + counterfactual | agent_response_excerpt **空** |
| R57-67 | 验证 mysql normal=0 / abnormal=5 | "**NO MySQL 'Aborted connection' errors in normal logs**" + 14:22:32 timeline → 当 incident-specific 通过 |
| R68 reflection | line 228 timeline | "MySQL Aborted connection errors started at 14:22:32 - about 1 minute 31 seconds later" —— **timestamp fallacy 反向应用**：把"晚于 incident start 1m 31s"当因果方向证据 |
| 🔴 R68 final #2 | `mysql` ❌ | "Incident-Specific Anomaly + Direct Causation" |

**v4 干预实际效果**：
- mid M6+M7 ✅✅：成功 dismiss RabbitMQ chronic + 显式想查 cancel-service container metric
- mid M7 落地失败 ❌：M7 secondary "runtime-layer signals" 提示对，agent 也复述了想查 cancel-service container metric，但**实际 SQL 路径没去 query ts-cancel-service container.cpu.usage**——agent 在 "k8s.pod.phase 线性扫" + "service log error count" 之间打转，离实际 specific metric 一步之遥但没迈过去
- conc M2+M8 ❌：counterfactual 通过条件设错 —— "mysql normal=0 / abnormal=5" + 时间序列上 14:22:32 出现，agent 当 incident-specific 通过；但量级 5 条不应作为独立证据

### 8. 失败模式诊断

| 失败链 | baseline | v4 |
|---|---|---|
| 锚点切换 | 一直锚 ts-rabbitmq（chronic infra） | 中段 dismiss RabbitMQ chronic ✅ → drift 到 mysql noise (5 条) |
| chronic check | 没做 | 做了 + 命中 RabbitMQ ✅，但**chronic 范围错应用**：dismiss 完后没回到 ts-cancel-service signal |
| silent service | 完全错过 | 识别 3 次（line 92/124/148）→ 解读为 "loadgenerator 不调用"，没识别为 silence 信号 |
| specific metric | 没扫 | M7 复述要查但**实际 SQL 没去**（绕了一圈但没 SELECT container.cpu.usage） |
| service ratio_avg ranking | 没扫 | 看到了但归因为"全面升"，没注意 ts-station 13x / ts-food 10x 是 cancelFromOrder 阻塞的 cascade 顶端 |

**主要失败模式**：
- baseline: **chronic noise 锚定** + **infrastructure scapegoat fallacy** + 不查 metric
- v4:
  - **F2** advisor 维度对但 reasoning 不动 — M7 runtime-layer 卡片对，agent 复述意图对，但 SQL 路径没落地到 ts-cancel-service container.cpu
  - **F3** agent drift to mysql noise — chronic dismiss RabbitMQ 后转向另一个 only-in-abnormal-but-tiny 信号
  - **silence-as-not-on-critical-path 错向解读** — silent ts-cancel-service abnormal=0 被解读为 "loadgenerator 不调用"，相当于 case 4375 silence-as-health 反例的镜像版（这次是 silence-as-uncalled，正确解读应是 silence-as-blocked-by-CPU-stress）

### 9. 中间件如何提示能翻转

| 维度 | 触发条件 | 干预语 |
|---|---|---|
| **silent service ranking 强 prompt** | mid 阶段如果 agent 注意到"X 服务 normal 期有 traces 但 abnormal 期 0 traces"，强制走 silent service 解读路径 | "When a service shifts from non-zero traces in normal to zero traces in abnormal (silence pattern), do NOT default to 'loadgenerator stopped calling it'. The loadgenerator's call mix is independent of the system state. Test three hypotheses: (a) the service is hung/blocked (CPU/memory exhaustion), (b) it's killed (PodChaos), (c) network partitioned. Verify by querying its container.cpu.usage and k8s.pod.cpu_limit_utilization in the abnormal window." |
| **specific metric 强制 SQL 模板** | mid M7 runtime-layer 引导后，如果 agent 复述"need to check container metrics for X" 但 N round 内没真去 SELECT，强制注入具体 SQL | "You stated you would check runtime metrics for `ts-cancel-service` but haven't queried them yet. Run this exact SQL: `SELECT metric, AVG(value) FROM abnormal_metrics WHERE service_name='ts-cancel-service' GROUP BY metric ORDER BY AVG(value) DESC LIMIT 20`. Then run the same on normal_metrics for comparison." |
| **noise 量级阈值** | conc 阶段如果 candidate 是基于 "abnormal=N small / normal=0" 信号，强制对比 chaos cascade 上游服务的同纬度信号 | "Your candidate is based on N=5 abnormal-only log lines. Before treating it as origin, ask: is this signal larger or smaller than the highest-anomaly-ratio service in this incident? Run service-level trace duration ratio ranking; the service with ratio_avg 10x+ relative to its own normal baseline is more likely the cascade head than a service with 5 only-in-abnormal logs." |
| **counterfactual 量级护栏** | M8 counterfactual 应用前，强制 candidate 异常信号 ≥ cascade 上游服务的最高 ratio | "Counterfactual passes only if your candidate's anomaly magnitude exceeds all downstream cascade victims. If a victim service shows ratio_avg 13x while your candidate shows N=5 log lines, the candidate is downstream of the real origin." |

最有效组合：**silent service ranking 强 prompt + specific metric 强制 SQL** —— 直接把 ts-cancel-service container.cpu.usage 496x 拉到 agent 视野。

### 10. 中间件代码层面问题

- **mid M7 落地失败**：M7 secondary "runtime-layer signals" 文字对，agent 也复述了要查 cancel-service container metric，但中间件没强制 follow-up SQL。卡片应该有 "if agent acknowledges intent X but next K rounds didn't execute SQL on X, re-prompt with literal SELECT template"。
- **conc M2 chronic 范围错应用引导**：M2 卡片说"a service being chronic noisemaker doesn't auto make another service the fault origin"——但 agent 已经把这个反过来用了，先 dismiss RabbitMQ 后立即去找另一个 only-in-abnormal 信号（mysql 5 条）当 origin，绕过了"先回到 silent service 信号"的路径。M2 应该直接说："after dismissing chronic noise, return to other anomaly dimensions you observed but haven't pursued — specifically silent services or specific-metric ratios — before chasing new only-in-abnormal log patterns."
- **conc M8 counterfactual 量级缺护栏**：counterfactual 通过条件没绑量级阈值，agent 用 "5 条 abnormal-only" 当通过证据。M8 应该要求 candidate 的 ratio 数量级要 dominate cascade victims（≥10x normal 自己 baseline）。
- **silent service signal 中间件没专门维度卡片**：v4 当前 8 维度里 M5 silent service 是 mid secondary，但 silent service 的解读路径"silent = blocked/killed/partitioned 三个假设并行"没有 explicit prompt。silence-as-uncalled 是 trainticket 低频服务（如 cancel-service normal=9 traces）的特殊陷阱，需要专门提示。
- **干预次数 2 + 维度 4 个**（M6/M7/M2/M8）方向都对，但**全部停在 advisor-level**，没有把"检查清单 → 必跑 SQL"绑死。

### 11. 判断

- **数据是否完整**：✅✅（container.cpu 496x + jvm.cpu 557x + cpu_limit_utilization 475x + memory 1.02x + trace 9→0 + service ratio 13x cascade，多重物理证据齐）
- **chaos 是否生效**：✅ 必然生效（cancelFromOrder 是频繁方法 + cpu_count=8 cpu 烧满 + cpu_limit_utilization 0.674 几乎打满 limit，都是教科书 JVMCPUStress 指纹）
- **真假盲区分类**：(b) **框架盲区** —— 数据齐、agent v4 mid 后明确想查 cancel-service container metric，但 19 类 intent 框架没把 "复述意图 → 必跑 SQL" 绑死，agent 在 specific metric 一步之遥处转身去抓 mysql noise 了。
- **失败模式归纳**：
  - baseline: **chronic noise 锚定**（ts-rabbitmq normal/abnormal ratio 0.74）+ **infrastructure scapegoat fallacy** + 不查 metric
  - v4: **F2** advisor 维度对但 SQL 不落地（M7 复述但没 SELECT）+ **F3** drift to mysql noise（5 条 only-in-abnormal log）+ **silence-as-uncalled 错向解读**

- **给 v4.1 的提示**：
  1. **silent service ranking 必须有专门维度卡片**：silence pattern → 三假设并行（hung/killed/partitioned）+ 强制查 container.cpu.usage / cpu_limit_utilization / restart counter
  2. **mid runtime-layer 落地保险**：agent 复述要查某服务 runtime metric 但 K round 没执行 → 中间件强制注入具体 SELECT 模板（见第 9 节）
  3. **conc counterfactual 量级护栏**：candidate 异常信号必须 ≥ 所有 cascade victim 的 max ratio_avg，量级太小（<10x）的 only-in-abnormal log 不能当独立证据
  4. **chronic dismiss 后路径引导**：M2 卡片应明确"after dismissing chronic noise, return to silent services / specific-metric ratios that were observed but not yet pursued"，避免 agent 滑向新的 only-in-abnormal noise

### 12. causal_graph 正确性检验

| 节点 | state | 实测 | 判定 |
|---|---|---|---|
| container\|ts-cancel-service | **["high_memory"]** | container.cpu.usage **496x**；container.memory 1.02x（基本不变） | ❌ **主导 metric 数量级反了**：该是 high_cpu，写成 high_memory（跟 case 1218/1459 同类反向标签错） |
| pod\|ts-cancel-service-5d6f598b75-ctdp8 | ["healthy", "high_memory", "high_cpu", "unknown"] | k8s.pod.cpu.usage 475x ✓ → high_cpu 标对；memory 1.02x → high_memory 标错；healthy 多时刻合并 | ⚠️ 部分错（high_cpu 对，high_memory 错；但因 high_cpu 也在列表里，agent 单纯读 pod state 还能命中） |
| service\|ts-cancel-service | ["unknown"] | abnormal trace=0/log=0，service-level signal 是"silent"而非具体 latency/error | ✅ unknown 占位合理 |
| span\|ts-cancel-service::CancelController.cancelTicket | missing_span / injection_affected | abnormal n=0 ✓ | ✅ |
| span\|ts-cancel-service::CancelController.calculate | missing_span / injection_affected | abnormal n=0 ✓ | ✅ |
| span\|ts-cancel-service::GET /cancel/{orderId}/{loginId} | missing_span / injection_affected | abnormal n=0 ✓ | ✅ |
| span\|ts-cancel-service::GET /cancel/refound/{orderId} | missing_span / injection_affected | abnormal n=0 ✓ | ✅ |
| span\|ts-ui-dashboard::GET /cancel/... | missing_span | abnormal n=0 ✓（dashboard 端也 silent，因为 cancel 调用阻塞） | ✅ |
| span\|loadgenerator::HTTP /cancel/... | missing_span | abnormal n=0 ✓ | ✅ |
| root_cause: container\|ts-cancel-service | ["unknown"] | root_cause 节点 state 占位 | ✅ |

⚠️ **container 节点 state 错标 high_memory（实测 1.02x）应是 high_cpu（实测 496x）—— 主导 metric 数量级反了**。但 service-level GT 仍正确（ts-cancel-service ✓），跟 case 1218/1459 同类（service-level GT 对、container/pod state 反向标签）。**case 仍可用于 failure mode 归纳**（agent 行为不依赖 causal_graph state 字段，依赖实测 parquet）。

case 4617 完毕。

---


# v4 Forensic 22 case 汇总（task 2 全部完成）

## A. 17 case 速查表

| # | case | chaos | tier | GT | baseline pred | v4 pred | transition | causal_graph 错标 |
|---|---|---|---|---|---|---|---|---|
| 1 | 1218 | JVMMemoryStress mem1 | ultra_hard | ts-order-service | ts-seat | ts-seat | wrong→wrong | container `high_memory` 错（应 high_cpu 16x）+ pod healthy 矛盾 restart 0→1 |
| 2 | 1459 | JVMMemoryStress mem1 | ultra_hard | ts-train-service | ts-basic | ts-basic | wrong→wrong | 同 1218 模式（cpu 20x 应 high_cpu）|
| 3 | 1495 | JVMMemoryStress mem1 | stable | ts-travel-plan-service | ts-seat | ts-seat | wrong→wrong | container `high_memory` 弱标（cpu 8.31x 主导）|
| 4 | 1814 | JVMMemoryStress mem1 (hot path) | stable | ts-basic-service | ts-travel | ts-travel | wrong→wrong（**conc 命中 victim 后被 silence-as-health 杀回**）| container `high_memory` 弱（cpu 3.52x 主导）|
| 5 | 1846 | ContainerKill | stable | ts-contacts-service | mysql | mysql | wrong→wrong | ✅ 通过（`[high_cpu, restarting]` 准确）|
| 6 | 1917 | ContainerKill | ultra_hard | ts-order-service | [seat, security] | [security, seat] | wrong→wrong（**双锚扩展加固**）| container 漏 `restarting` + pod healthy 矛盾 |
| 7 | 1948 | ContainerKill | stable | ts-preserve-service | ts-delivery | ts-ui-dashboard | wrong→wrong | ✅ 通过 |
| 8 | 2211 | ContainerKill | stable | ts-travel-service | ts-route-plan | ts-route-plan | wrong→wrong | ✅ 通过 |
| 9 | 2253 | JVMMemoryStress mem1 | ultra_hard | ts-travel-service | ts-route-plan | ts-route-plan | wrong→wrong | ✅ 通过 |
| 10 | 2258 | ContainerKill | ultra_hard | ts-travel2-service | ts-route-plan | ts-route-plan | wrong→wrong（**conc 中文卡片**）| ✅ 通过 |
| 11 | 2713 | JVMMemoryStress mem1 | stable | ts-security-service | ts-food | ts-order-service | wrong→wrong（v4 切 anchor 但仍错）| ✅ 通过（`[high_cpu, restarting]`）|
| 12 | 3760 | JVMMemoryStress **mem2** | ultra_hard | ts-price-service | ts-basic | ts-basic | wrong→wrong | container `high_memory` 错（mem_type=2 应 high_cpu 21x，memory 1.0x）|
| 13 | 4081 | ContainerKill | ultra_hard | ts-order-other-service | ts-seat | **mysql** | wrong→wrong（**v4 drift 到非业务 service**）| pod `high_memory` 弱标（轻于 1218/1459/3760）|
| 14 | 4363 | JVMMemoryStress **mem2** | stable | ts-train-food-service | ts-rabbitmq | ts-food | wrong→wrong（**v4 切 anchor 但仍错**）| ❌ container 单 `[high_memory]` + 漏 `high_cpu/restarting`（**最严重错标**）|
| 15 | 4375 | ContainerKill | stable | ts-travel2-service | ts-route-plan | ts-ticket-office-service | wrong→wrong（**v4 mid 已命中 GT，conc 推走**）| ✅ 通过 |
| 16 | 4463 | ContainerKill | ultra_hard | (评测) ts-config-service / (实际 injection) ts-food-service | ts-food-service | ts-ui-dashboard | **dataset label bug**（同 339/2130/3868 类）| ✅ 通过（state 跟 injection 一致，但评测系统 GT 字段错配）|
| 17 | 4617 | **JVMCPUStress (cpu_count=8)** | ultra_hard | ts-cancel-service | ts-rabbitmq | mysql | wrong→wrong（chronic dismiss 后 drift to noise）| container `high_memory` 错（应 high_cpu **496x**，memory 1.02x）|

## B. 跨 case 失败模式分布

### B.1 baseline 失败子模式频次（17 case）

| 失败子模式 | 命中 case | 频次 |
|---|---|---|
| **503 message provenance 误读**（caller 报 503 当 RC）| 1218 / 1459 / 1814 / 1917 / 2211 / 2253 / 4081 等 | 高频（~50%）|
| **trace error 排名锚定**（cascade caller error 数最多即锚）| 1218 / 1459 / 1495 / 1814 / 1917 / 2211 / 2253 等 | 高频（~60%）|
| **silence-as-health 标准版**（GT log/trace 静默当 healthy）| 1218 / 1459 / 1495 / 1814 / 1917 / 2713 / 4081 等 | 高频（~70%）|
| **silence-as-health 极端版**（abnormal ERROR < normal ERROR）| 1917 | 1 case（新模式）|
| **status_code Unset = healthy**（callee Unset 当 healthy 排除）| 1459 / 1495 / 1814 / 1917 / 1846 等 | 高频 |
| **没查 GT specific metric**（cpu/restart/page_faults 都没查）| 几乎所有 case | ~85% |
| **chronic noise 锚定**（rabbitmq DNS / Aborted connection 当 RC）| 1846 / 4363 / 4617 | 3 case |
| **log timeline 因果链 fallacy**（log timestamp 早 4s 当 cause）| 1846 | 1 case |
| **leaf service 凭印象判断 fallacy**（不查父子关系断言 leaf）| 1917 | 1 case |
| **first-error timestamp fallacy** | 1218 / 1459 / 1814 等 | 中频 |
| **survivor bias**（service avg 反而下降被锚为 healthy）| 4081 / 4363 / 1948 等 | 中频 |
| **Error span 唯一性陷阱**（1/6838 当 RC，错率分母没看）| 1495 | 1 case |

### B.2 v4 干预失败模式频次

| F 标签 | 描述 | 命中 case 数 |
|---|---|---|
| **F2 维度对但 reasoning 不动** | mid baseline 对比执行后反向加固原 anchor | ~12 case |
| **F5 conc 反向加固** | counterfactual 加固错答案 | ~10 case |
| **F5 命中-杀回**（新变种）| conc 真命中 victim 洞察后被 silence-as-health 杀回 | 1814 |
| **F5 扩展加固版**（新变种）| counterfactual 把单锚扩展成"两个 independent RC"| 1917 |
| **F5 加深错觉版**（新变种）| conc counterfactual 让 agent 反推 self-attribution 自我归因 | 1459 |
| **F3 drift 到另一个 noise** | mid 听话改方向但跳到另一个错答案 | 1948 / 4081 / 4617 |
| **mid 已命中 GT，conc 推走** | v4 一度想到 GT 但 conc 反向推走 | 4375 |

### B.3 chaos 类型分布

| chaos 类型 | case 数 | tier 分布 | wrong→wrong 率 |
|---|---|---|---|
| JVMMemoryStress mem_type=1 (heap) | 6 | stable 3 / ultra_hard 3 | 100% |
| JVMMemoryStress mem_type=2 (direct) | 2 | stable 1 / ultra_hard 1 | 100% |
| ContainerKill | 8 | stable 5 / ultra_hard 3 | 100% |
| JVMCPUStress (cpu_count=8) | 1 | ultra_hard | 100% |
| **总 wrong→wrong 率** | **17/17** | — | **100%** |

整 task 2 list 的 17 个 case 全部是 wrong→wrong（v4 干预未能翻盘）。

## C. causal_graph 标注质量分布

| 类别 | case 数 | 错标内容 |
|---|---|---|
| ✅ 全部通过 | 1846 / 1948 / 2211 / 2253 / 2258 / 2713 / 4375 | 7 case |
| ⚠️ 弱标 / 部分错（不影响 GT）| 1495 / 1814 / 4081 / 4463 | 4 case |
| ❌ container/pod 状态主导 metric 错标（high_memory 应 high_cpu）| 1218 / 1459 / 3760 / 4363 / 4617 | 5 case |
| ❌ dataset label bug（评测 GT 跟 injection 不一致）| 4463 | 1 case |
| ❌ container 漏标 `restarting` | 1917 | 1 case |

**模式**：
1. **JVMMemoryStress 类（mem1/mem2）100% container 状态错标 high_memory**——chaos 设计意图 mem_type 不影响实际生效路径（byte code injection 副作用是 cpu，不是 memory）。causal_graph 跟 chaos 设计意图绑定而不是跟实测信号绑定
2. **ContainerKill 类多数标注准确**——`[high_cpu, restarting]` 直接反映物理本质，没有 chaos 设计意图错位
3. **JVMCPUStress 类 (case 4617)** —— 标注仍误用 high_memory，跟 mem_type 类 case 同模式（数据集标注模板化错位）
4. **pod 节点 `healthy` 跟 restart 0→1 矛盾普遍存在**——是图模型多时刻状态合并产物，所有有 restart 的 case 都有这个共存

## D. 19 个 advisor 维度（来自 17 case 累积）

按发现顺序分组：

### D.1 messenger vs RC 模式（1218/1459/1814 等）
1. **trace/log 异常 + metric 全正常 → 查下游**（case 784 已记，1218+ 加强）
2. **direct callee drill**（case 156 已记）
3. **callee 排除验证 commit-gate**（case 156 已记）
4. **503 message provenance**（case 99 已记）
5. **counterfactual victim 洞察后强制 callee specific metric**（case 1814 新维度）

### D.2 silent / silence-as-health 反例
6. **silence-as-health 反例**（case 1459，GT log -55%）
7. **callee status_code Unset ≠ healthy**（case 1459，必须配 latency p95/p99 + restart + container.cpu）
8. **silence-as-health 极端版**（case 1917，abnormal ERROR < normal ERROR）

### D.3 specific metric 强制
9. **specific metric SQL 模板**（case 33 已记）
10. **anchor 自身 specific metric verification**（case 1846，mysql cpu 0.67x 反例）
11. **specific metric 强制 ORDER BY ratio DESC SQL 模板（升级版）**（case 4363 新维度）
12. **distribution > 单点值规则**（case 4363 新维度）

### D.4 ContainerKill / PodChaos 三件套（case 1846）
13. **trace silence gap 检测**
14. **全局 restart counter 扫描**（case 33 已记）
15. **ContainerKill 三件套**（hubble p95 50x+ + restart 0→1 + trace silence gap）

### D.5 chronic check 双向（case 1846/4363/4617）
16. **chronic literal 反例**（rabbitmq DNS / Connection refused 字面 ERROR 强制 chronic check）
17. **literal log message 内置黑名单**（trainticket 长期 chronic logs）

### D.6 collapse / reasoning 控制
18. **leaf service 凭印象判断必须 SQL 实查**（case 1917 新维度）
19. **双锚 + counterfactual 必须收敛单一 RC**（case 1917 新维度）

### D.7 survivor bias / 因果方向（case 1495/4363）
- **survivor bias 警告**（service avg 下降不能当 healthy）
- **caller p99 飙升 ≠ caller 是 RC**（应反向追问 caller 在等谁）
- **Missing in failing trace 反向解读**（missing 可能是 RC 而非 caller 内部失败）

## E. 中间件代码层面问题汇总

| 问题 | 命中 case | 影响 |
|---|---|---|
| mid M5 silent service 没生效（探针指错对象）| 1218 / 1459 / 1495 / 1814 / 1846 / 1917 | F2 反向加固 |
| mid M6 baseline 反向加固 anchor | 几乎所有 case | F2 普遍 |
| conc M8 counterfactual 反向加固 | 1218 / 1459 / 1495 / 1814 / 1917 / 1846 / 4081 等 | F5 普遍 |
| conc M5 silent service 反义化为"non-silent = healthy" | 1459 / 1814 / 1917 | silence-as-health 杀回 |
| conc 中文卡片（dimension_cards.py 模板）| 2258 / 部分 case | leakage / 一致性 |
| advisor 文本 "leaf nodes" 强化错误 leaf 假设 | 1917 | F5 扩展加固 |
| 4081 v4 drift to mysql（非业务 service） | 4081 | F3 |
| 4463 dataset label bug | 4463 | 评测系统 vs 实际 injection 错配 |
| advisor 缺少 "anchor 自身 specific metric verification" 硬规则 | 几乎所有 case | 普遍 |
| advisor 缺少 ORDER BY ratio DESC SQL 模板 | 4363 等 | distribution > 单点值 |

## F. 给 v4.1 的核心改进建议（按 case 频次降序）

| # | 改进项 | 来自 case |
|---|---|---|
| 1 | **anchor 自身 specific metric 强制 verification SQL 模板**（任何锚定必查 cpu/restart/page_faults/hubble，缺一不可）| 1846 + 普遍 |
| 2 | **callee specific metric drill 强制 SQL 模板**（503/Connection refused 时必发，不能仅看 status_code Unset）| 1459/1814/1917 等 |
| 3 | **leaf service 假设强制 normal_traces 父子关系实查 SQL** | 1917 |
| 4 | **conc counterfactual 必须收敛到单一 RC**（"is there a SHARED downstream that explains BOTH anchors"）| 1917 |
| 5 | **silence-as-health 反例**（abnormal log/trace 大幅减少 = silent 信号，不是 healthy）| 1459/1814/1917 |
| 6 | **trace silence gap 检测 SQL 模板**（每分钟分组 count traces 找最低谷）| 1846 |
| 7 | **ContainerKill / PodChaos 三件套指纹卡片** | 1846/1948/2211 等 |
| 8 | **specific metric 强制 ORDER BY ratio DESC SQL 模板**（升级版，避免被 LIMIT + 隐式排序淹没）| 4363 |
| 9 | **chronic check 双向**（验证 anchor 自身是否 chronic + 已知 chronic）| 1846/4363/4617 |
| 10 | **conc M8 advisor 文本不能用 "leaf nodes" 作为既定事实**——应让 agent 验证 leaf 假设 | 1917 |
| 11 | **survivor bias 警告**（service avg 下降不能当 healthy）| 4081/4363 |
| 12 | **中间件代码模板硬规则**：(a) 中文卡片消除（2258）(b) advisor 维度名/服务名硬编码消除 (c) leakage 等级控制 | 2258 + 普遍 |

## G. 评测系统 dataset label 问题

之前已知 case 339 / 2130 / 3868 是 chaos 注入伪故障（chaos blade attach 痕迹但设计语义未生效，SLO 真因跟 GT 无关）。现 task 2 又发现：
- **case 4463**：评测系统 GT 字段 `ts-config-service` 跟 `injection.json` + `causal_graph.json` 的 `ts-food-service` 矛盾——baseline 实际预测 ts-food-service（跟 injection 一致）但评测判错。**这是 dataset label bug，不能用于 failure mode 归纳**

## H. task 2 整体结论

1. **wrong→wrong 100% (17/17)**：v4 中间件 mid + conc 干预次数足够（30-100 round）但**全部失败**。advisor 卡片库存在系统性盲点
2. **失败模式高度收敛**：~70% case 同时命中 silence-as-health + 503 message provenance + 没查 GT specific metric 三联陷阱
3. **F5 conc 反向加固比 F2 mid confirmation bias 更危险**：counterfactual 不仅没翻盘，反而**深化错觉**（命中-杀回 / 扩展加固 / 自我归因变种）
4. **causal_graph 标注质量跟 chaos 类型强相关**：JVMMemoryStress 类全部 high_memory 错标（mem_type 设计意图 vs 实测路径错位），ContainerKill 类多数准确
5. **数据本身的 dataset label bug** 在 17 case 中存在 1 例（4463）——比例 ~6%，需独立标注不参与 failure mode 归纳

case 1218 - 4617 task 2 全部完毕。total: 17 case forensic writeup 完整。
