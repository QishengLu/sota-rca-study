## Sonnet Case 572 · `ts1-ts-food-service-response-patch-body-qjhx5h` · HTTPResponsePatchBody

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 572 |
| GT 根因 | `ts-food-service`, `ts-train-food-service` |
| sonnet pred | `ts-order-service` (HIGH_GC_PRESSURE) + `ts-consign-service` (HIGH_ERROR_RATE) ❌ |
| sonnet rounds | 39 |
| qwen3.5 pred | `ts-consign-service` (HIGH_ERROR_RATE + HIGH_LATENCY) ❌ |
| **共性错** | ✅ 在 53 case 列表（HTTPResponsePatchBody noise-floor case，qwen v4 翻盘是 partial match 巧合） |
| chaos type | HTTPResponsePatchBody (fault_type=10) |
| tier | ultra_hard / unsolvable-noise-floor |

### 2. GT 注入

```
fault_type: 10 = HTTPResponsePatchBody
display_config:
  duration: 4 min
  injection_point:
    app_name: ts-food-service                         ← chaos 注入在 caller 侧
    method: GET
    route: /api/v1/trainfoodservice/trainfoods/*       ← 仅这条 route 被 patch
    server_address: ts-train-food-service              ← callee
    server_port: 8080
ground_truth:
  service: [ts-food-service, ts-train-food-service]
```

### 3. chaos 机制

HTTPResponsePatchBody 与 case 860 的 ResponseReplaceBody 不同：**Patch 是局部修改 response body 的某些字段**（非整体替换），通常对 JSON 结构不破坏（不会触发 JsonParseException）。被 patch 的字段值发生静默改变，下游业务逻辑接收到"语义改变"的数据。

**与 ResponseReplaceBody 信号差异（决定本 case 不可解性）：**
- ResponseReplaceBody（case 860）：caller log 1167 行同质 `JsonParseException Unexpected character ('z' code 122)` → 直接指纹
- ResponsePatchBody（case 572）：caller log **零** JSON parse error，trace duration 不变（caller GET p50: 9.2ms → 8.9ms），status_code Error rate 不变（1/301 端点错率，几乎是 normal level），callee server span 完全不变（ts-train-food-service avg 2.7 → 2.8ms）

trainticket 的 ts-food-service `getAllFood` 业务逻辑容错性强：即使 train food 数据被 patch，FoodController 多半返回 200 OK 加默认值或 fallback。chaos 物理上生效但**应用层信号在 noise floor**——按 OBSERVATIONS 是 53 case 中唯一无解 case。

### 4. 调用树（normal 期实测）

```
loadgenerator → ts-ui-dashboard → ts-travel-plan-service → ts-food-service   ◀── RC (chaos injected, caller-side)
                                                                └─ GET → ts-train-food-service /trainfoods/*  ◀── RC (response patched)

并行业务流（与 chaos chain 无 trace_id 重叠）：
loadgenerator → ts-ui-dashboard → ts-order-service / ts-consign-service / ...
```

### 5. 关键 duckdb 证据

#### chaos 直接证据 — 全维度 noise floor

| 维度 | normal | abnormal | ratio | 评价 |
|---|---|---|---|---|
| ts-food-service service-level avg | 19.3ms | 24.9ms | 1.3x | 跟系统级整体降速一致 |
| ts-food-service `GET` client span p50 | 9.2ms | 8.9ms | 0.97x | **不变** |
| ts-food-service `GET` p95 / max | 19.6 / 634ms | 30.9 / 1448ms | 1.6x / 2.3x | max-only outlier |
| ts-food-service `GET /foods/{date}/{...}/{tripId}` p50 | 15.2ms | 14.8ms | 0.97x | 不变 |
| ts-food-service Error span 数 | 0 | **1** | incident-only 但仅 1 例 | |
| ts-train-food-service trace count | 1974 | 1609 | 0.81x | 跟系统级 0.7-0.85 一致 |
| ts-train-food-service avg | 2.7ms | 2.8ms | 1.04x | **完全不变** |
| ts-food-service "Get the Get Food Request Failed" | 231 | 208 | 0.90x | **chronic（abnormal 反而少）** |
| ts-food-service "UnknownHostException" | 50 | 23 | 0.46x | **chronic** |
| ts-food-service "rabbitmq" | 100 | 46 | 0.46x | **chronic** |
| ts-food-service "JSON parse error" | 0 | 0 | - | 无（与 ReplaceBody 不同） |

**结论**：chaos 物理上生效但应用层无可识别信号。caller-callee 双面对比（B7）也找不到不对称（duration 都不变）。

#### 误锚 service 1: ts-consign-service（A8 chain-out + A11 race semantic）

| 维度 | normal | abnormal | 评价 |
|---|---|---|---|
| GET /consigns/order/{id} spans | 29 | 128 | abnormal 涨 4.4x |
| GET /consigns/order/{id} Error spans | **0** | **122** | **真 incident-only 信号（95.3% err rate）** |
| SEVERE log "NonUniqueResultException" | **0** | **122** | **真 incident-only** |

ts-consign-service NonUniqueResultException 是真的 incident-only 信号，但：
1. **不在 chaos chain 上**：chaos 在 ts-food-service ↔ ts-train-food-service 边，ts-consign-service 在 order 处理流程，跟 food endpoint trace 无 trace_id 重叠（A8）
2. **错误语义指向反**：NonUniqueResultException 是上游并发 retry/race 形成的 DB 行级竞争 artifact（同 case 283/1140/3716 反复出现），caller 端并发 update 同一行才是因果起点；不是 ts-consign-service 自身 DB integrity 故障（A11）

#### 误锚 service 2: ts-order-service（A3 max-only GC pause）

| 维度 | normal | abnormal | ratio | 评价 |
|---|---|---|---|---|
| jvm.gc.duration（sum 字段） avg_gc_sum | 1.94s | 3.51s | 1.81x | 中度 |
| max_gc_sum | 2.89s | **8.86s** | 3.07x | sonnet 锚的"3x 极端 GC" |
| max single GC pause | 2.89s | 8.54s | 2.95x | 单点 max outlier |
| service-level avg | 4.5ms | 8.5ms | 1.9x | 轻微 |

ts-order-service avg GC duration 仅 1.81x（中度），max single GC 8.54s 是单点 outlier；max GC 3x 不足以判定 RC，且 chaos 物理机制（HTTPResponsePatchBody on food chain）不能直接引起 ts-order-service GC 压力。

#### service-level top by ratio_avg

| service | ratio_avg | 说明 |
|---|---|---|
| ts-cancel-service | 6.6x | 仅 18 spans — 小基数 outlier |
| ts-order-service | 1.9x | sonnet 锚定（HIGH_GC_PRESSURE） |
| ts-consign-price-service | 1.5x | |
| ts-travel2-service | 1.5x | |
| ts-food-service | **1.3x** | **GT 但仅排第 8，跟 ts-ui-dashboard / ts-travel-service 同级** |

GT 的 ts-food-service 在 service-level top 中**完全不显眼**——ratio 1.3x 跟系统降速一致，无差别。

### 6. sonnet 完整推理路径

sonnet 跑 39 round → `ts-order-service + ts-consign-service` ❌

| Round | 行为 | 关键决策 |
|---|---|---|
| R1-R3 | schema + 计划 | 标准 |
| R4-R5 | service-level error scan | ts-consign-service 10.87% error rate (122 errors)；GET /consigns/order/{id} 95.31% err rate |
| 🔴 R6-R7 锚定起点 | think | "ts-consign-service NonUniqueResultException = DB integrity issue"——A11 字面解读 |
| R8-R9 | ts-food-service ERROR/SEVERE log | 看到 "Get the Get Food Request Failed" + UnknownHostException ts-rabbitmq + Connection reset；**判定为 chronic-looking → dismiss**（chronic 判定本身正确，但 dismiss 后未做 ts-food-service 端点级 incident-only drill） |
| R10-R12 | ts-route-plan-service / basic-service / travel-plan p99 distribution | "ts-route-plan-service POST cheapestRoute avg 606ms max 2962ms"——cascade 高 latency 链路漫游 |
| R13-R20 | basic / travel / preserve service 调用链 | 跟随 cascade 高 latency 节点 |
| 🔴 R21-R23 第二锚定形成 | p99 latency cross-rank | "ts-order-service avg 1.0s **max 9.875s** ← HIGHEST!"——max-only fallacy |
| R24-R28 | ts-order-service GC metrics 深挖 | "max GC pause **8.54s** vs normal 2.89s (3x)"——A3 max-only GC pause 锚定 |
| R29-R34 | OrderRepository.findByAccountId max 8544ms 时间戳关联 | 用单 trace 的 max 8.5s 与 GC max 8.5s 时间戳关联，确认"GC stop-the-world 是 RC" |
| R35-R38 | ts-cancel-service / consign-service 验证 | ts-preserve-service 不调 ts-consign-service（确认拓扑），但**未质疑 ts-consign-service 是否在 chaos chain 上** |
| FINAL | 输出 ts-order-service (HIGH_GC_PRESSURE) + ts-consign-service (HIGH_ERROR_RATE) | 全程未深查 ts-food-service 端点级 / ts-train-food-service 任何信号 |

**sonnet 失败点**：
1. R7 把 ts-consign-service NonUniqueResultException 字面解读为 "DB integrity issue"，未做 race-condition 反向追溯（A11）
2. ts-consign-service 95% error rate 真信号但跟 chaos chain 无 trace_id 重叠（A8）——sonnet 未做 chain overlap 验证
3. ts-order-service GC max 8.54s 是 max-only outlier（A3）；avg GC 仅 1.81x，不足以锚定为极端 GC 压力 RC
4. 全程未查 ts-train-food-service（chaos 直接 callee）任何信号，未做 ts-food-service 端点级 incident-only drill（虽然 drill 也找不到强信号，但过程缺失）

### 7. 跨模型快速结论

| 项 | sonnet | qwen3.5 |
|---|---|---|
| 最终 pred | `ts-order-service` + `ts-consign-service` ❌ | `ts-consign-service` ❌ |
| 决策风格 fingerprint | NonUnique 字面 + GC max-only outlier 双锚定 | NonUnique 单锚定 |
| 共性 vs sonnet-specific | **共性**：两模型都把 ts-consign-service NonUniqueResultException 错读为 RC（A11 + A8）；sonnet 额外加上 ts-order-service GC max-only（A3 sonnet-specific extension） | qwen3.5 v4 翻盘是 partial match 巧合（v4 选了 ts-food-service 但 advisor 干预因 API 400 全部降级未生效，per OBSERVATIONS） |

### 8. 失败模式

| 标签 | 本 case 具体表现 | qwen3.5 对应 |
|---|---|---|
| **A11** | sonnet 把 ts-consign-service `NonUniqueResultException`（122 incident-only）字面解读为 "DB integrity issue" 当 RC（HIGH_ERROR_RATE state）；NonUniqueResultException 因果上是上游并发 retry/race 形成的 DB 行级竞争 artifact——caller 端并发 update 同一行才是因果起点（同 case 283/1140/3716 反复出现），ts-consign-service 不是因果起点；sonnet 未沿因果链反向追溯 | qwen3.5 同款 A11，把 NonUnique 当 RC |
| **A8** | ts-consign-service 95% Error rate（122/128 spans）是真 incident-only 信号，但**跟 chaos chain 无 trace_id 重叠**：chaos 在 ts-food-service ↔ ts-train-food-service 边（food endpoint），ts-consign-service 在 order processing flow，两者业务流分离；sonnet 未做 chain overlap 验证就锚定 | qwen3.5 同款 A8 |
| **A3** | sonnet 锚 ts-order-service HIGH_GC_PRESSURE：max single GC pause 8.54s vs normal 2.89s（3x max-only），但 avg GC sum 仅 1.81x（中度，1.94→3.51s）；distribution 不支持极端 GC 压力；chaos 物理机制（response body patch on food chain）不能直接引起 ts-order-service GC 飙升——这是 cascade 副作用单点 outlier 被错当 origin | qwen3.5 仅锚 ts-consign-service，未涉及 ts-order-service GC max-only（sonnet-specific 第二锚定） |

### 9. 失败池使用规则

```
本 case 命中标签：A3, A8, A11

最有效组合（理论上的 — 实际是 noise-floor，组合也未必能挽救）：
  - A11（错误信息因果归属反查）：NonUniqueResultException 必须沿因果链反向问"哪个 caller 并发 update 同一行" 而不是 dismiss 为 DB 故障
  - A8（chain overlap 必查）：候选 service trace 必须跟 incident description 端点 trace 有 trace_id 重叠才能锚定
  - A3（distribution 反证）：max-only outlier（GC max 8.54s）必跑 avg/p50/p95 反证

辅助：B5（端点 status_code Error 分布 SQL）—— 跑 (service, span_name, status_code) 时确实会浮现 ts-food-service 1/301 = 0.3% Error rate；但跟 ts-consign-service 95% 比是 weak signal，noise floor 性质决定再多 SQL 也难以决定性指向 ts-food-service

本 case 关键认知：在 noise floor case 上，所有 A/B 组合的"挽救"都低概率。HTTPResponsePatchBody 类故障的可解性需要 chaos 类型先验知识或更细粒度的"业务语义层信号"（如 response body diff、调用方 fallback 行为分析），这超出当前 19 类 intent + duckdb tool 能力范围。
```

### 10. 判断

- **数据是否完整**：⚠️ 部分——chaos 类型决定数据层无可识别 incident-specific 信号，trace 时长 / status / log 全维度 noise floor
- **chaos 是否生效**：✅ 物理生效（response body 被 patch），但应用层 fallback 让信号沉到 noise floor
- **真假盲区分类**：**(a) 数据真盲区 + (b) 框架盲区双重**——
  - (a) 主导：HTTPResponsePatchBody 在 trainticket 数据集天然信号在 noise floor，按 OBSERVATIONS 是 53 case 中唯一无解 case
  - (b) 次要：sonnet 在 noise floor 下被 cascade 假信号（NonUnique + GC max-only）误导，未做 chain overlap 反证
- **失败模式归纳**：A11（NonUnique 字面误读）+ A8（chain overlap 未查）+ A3（GC max-only 锚定）。三条都是"在没有真信号的情况下被假信号牵引"的具体表现
- **共性 vs sonnet-specific**：A11 + A8 是两模型共性盲区（qwen3.5 baseline 同款锚 ts-consign-service NonUnique）；**A3（GC max-only on ts-order-service）是 sonnet-specific 第二锚定**——qwen3.5 没追这条
- **给 sonnet 中间件设计的提示**：A11 + A8 + A3 联动可能挽救一部分误锚，但本 case 主因是数据真盲区——任何中间件维度都无法在 noise floor 上构造正确锚定。这条 case 应归入 `unsolvable:noise-floor`，不计入失败模式归纳的核心样本
- **注释**：HTTPResponsePatchBody 类 chaos 在评测集设计层面是问题——业务层 fallback 设计让 chaos 失去观测性。建议 53 case 体系中将本 case 标记为 unsolvable

### 11. causal_graph 正确性检验

GT causal_graph root_cause = `service|ts-food-service` (state: "unknown")。

逐节点验证（抽样）：
- ts-food-service 端点 state high_avg_latency 等 → 实测 service-level ratio 1.3x，端点 ratio 1.05-1.6x（与 high_avg_latency 一致但极轻）⚠️
- ts-train-food-service 不在 causal_graph nodes（与 case 315/1484/2640 同结构）
- causal_graph 标注的 high_avg_latency state 在 noise floor 程度上"勉强成立"，但跟 ts-cancel-service 6.6x、ts-order-service 1.9x 比，ts-food-service 1.3x 的 high_avg_latency 标注其实是 GT-driven 标注（不是从 metric 阈值推出）

整体节点核对：state list 跟实测 metric 一致性较弱（noise floor 下任何阈值判据都接近 baseline）。**不计入"错标"**（因为 chaos 类型决定信号弱），但本 case 不能用于 failure mode 归纳的 ground-truth 校核——其 GT 在数据上几乎不可达。

case 572 sonnet 完毕。
