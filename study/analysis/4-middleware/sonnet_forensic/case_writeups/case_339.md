## Sonnet Case 339 · `ts0-ts-travel-service-mysql-28wmss` · JVMMySQLLatency (未生效)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 339 |
| GT 根因 | `ts-travel-service, mysql` |
| sonnet pred | `ts-consign-service` ❌ |
| sonnet rounds | 49 (effective tool rounds) |
| qwen3.5 pred | `ts-consign-service` ❌ |
| **共性错** | ✅ 在 53 case 列表（两 model 都中 NonUnique trap） |
| chaos type | JVMMySQLLatency (fault_type=29, latency_ms=3669, target=ts-travel-service.SELECT trip) |
| tier | unsolvable (chaos 未生效) |

### 2. GT 注入

```
fault_type: 29 = JVMMySQLLatency
display_config:
  injection_point: { app_name: ts-travel-service, db_name: ts,
                     operation_type: SELECT, table_name: trip }
  latency_ms: 3669    (单 SQL 注入 3669ms 延迟)
  duration: 4 (min)
ground_truth: service=[ts-travel-service, mysql],
              span=[ts-travel-service, mysql]
```

### 3. chaos 机制

JVMMySQLLatency 通过 ChaosBlade JVM agent (ByteBuddy) 在 ts-travel-service 进程内 attach，拦截 JDBC 层对 `ts.trip` 表的 SELECT 操作，在调用链上注入 3669ms sleep。预期因果链：
- ts-travel-service 内 `TripRepository.findAll` / `findByRouteId` / `findByTripId` 任何走 SELECT trip 的 SQL → 3669ms 延迟
- 父 endpoint `POST /trips/left`、`POST /trips/routes`、`POST /trip_detail` 等 wallclock 应飙高数倍
- 上游 ts-travel-plan-service / ts-route-plan-service / ts-ui-dashboard cascade victim

**实测：chaos 未生效**——abnormal 期 `SELECT Trip` max 仅 34.77ms / `SELECT ts.trip` max 仅 30.24ms，全数据集没有任何 span 出现 3669ms 量级 outlier。`trips/left` endpoint avg 217.7ms（abnormal）vs 259.8ms（normal），**反而更快**。可能成因：Hibernate 二级缓存绕过 JDBC 层 / SQL pattern 不匹配 / ByteBuddy agent attach 失败。

### 4. 调用树（normal 期实测）

```
loadgenerator
  └─ ts-ui-dashboard
      ├─ POST /travelPlan/minStation ──→ ts-travel-plan-service ──→ ts-route-plan-service
      │                                                              └─ ts-travel-service /trips/left  ◀── chaos target (未生效)
      │                                                                  └─ TripRepository.findAll → SELECT Trip / SELECT ts.trip
      └─ POST /preserve              ──→ ts-preserve-service     ──→ (其他服务)
      └─ GET  /consigns/order/{id}   ──→ ts-consign-service       ◀── sonnet 锚定（chain 外）
```

### 5. 关键 duckdb 证据

#### chaos 未生效证据（ground truth 信号缺失）

| 信号 | normal | abnormal | ratio | 说明 |
|---|---|---|---|---|
| `SELECT Trip` count | 869 | 786 | 0.90 | 调用次数几乎不变 |
| `SELECT Trip` avg / p50 / p95 / max (ms) | 1.04 / 1.0 / 1.53 / 24.28 | 1.35 / 1.22 / 1.88 / 34.77 | 1.30x / 1.22x / 1.23x / 1.43x | **远低于 3669ms 量级** |
| `SELECT ts.trip` max (ms) | 22.24 | 30.24 | 1.36x | 同上 |
| `trips/left` endpoint avg (ms) | 259.8 | 217.7 | **0.84x** | abnormal 反而更快 |
| 全数据集最大 single span (除 loadgen 包络) (ms) | — | 10598 (travelPlan/minStation) | — | 顶端最大 10.6 秒，无 3669ms 量级 SQL outlier |

→ 核心结论：**chaos 物理上未注入成功**。GT service ts-travel-service 上没有任何 chaos 直接证据信号；mysql 也没有 trace（mysql 只在 client SQL span 中出现，无 server-side trace）。

#### service-level ratio (全数据集 noise floor)

| service | ratio_avg | ratio_count | 说明 |
|---|---|---|---|
| ts-consign-service | 1.94 | 1.98 | 唯一 ratio_avg > 1.5 的 service，但 trace count **abnormal 反而更多** |
| ts-consign-price-service | 1.33 | 0.50 | |
| ts-station-food-service | 1.31 | 0.98 | |
| ts-station-service | 1.25 | 0.92 | |
| 其他 | 1.0-1.17 | ~0.95 | noise floor |

→ 全表 ratio_avg < 2x，符合 chaos-not-effective 的"信号在 noise floor"指纹。

#### 误锚 service 实情（ts-consign-service）

| 信号 | normal | abnormal | ratio |
|---|---|---|---|
| SEVERE log: `NonUniqueResultException` | 0 | 120 | incident-only ✓ |
| endpoint `GET /consigns/order/{id}` avg (ms) | 10.5 | 102.5 | 9.74x |
| `ConsignController.findByOrderId` avg (ms) | 6.3 | 30.4 | 4.84x |
| `container.cpu.usage` (max cores) | 0.041 / 0.24 | 0.214 / 2.29 | avg 5.2x, max 9.5x |
| `jvm.cpu.recent_utilization` (avg) | 0.0 | 0.001 | (近零) |
| `jvm.system.cpu.load_1m` | 111.3 | 46.1 | **0.41x** (abnormal 反而 _下降_) |

→ NonUnique 是 application-level race（duplicate consign records for order `8cf803f9-...`），跟 chaos target SELECT trip 物理上无关。consign-service 不在 chaos 因果链上：sonnet 没做 chain overlap 验证（consign 业务流跟 travelPlan/minStation 无 trace_id 重叠）。`container.cpu.usage` max 2.29 cores 是 NonUnique exception stack trace 反复抛出 + retry busy loop 的副作用，不是 origin 信号。

### 6. sonnet 完整推理路径

sonnet 跑 49 round → `ts-consign-service` ❌

| Round | 行为 | 关键决策 |
|---|---|---|
| R1-R6 | log/trace overview | 看到 ts-food-service 有 209 ERROR (ts-rabbitmq UnknownHostException — chronic 跟本 case 无关)，ts-travel-plan-service endpoint max 10.58s（cascade 末端 outlier） |
| R7-R10 | endpoint compare normal vs abnormal | 发现 ts-travel-plan-service avg 没大变（0.74→0.85），决定深挖具体 trace |
| R11-R15 | 单 trace deep dive | 顺 cascade 走，看 ts-travel-service trips/left 6.4s、ts-route-plan-service 10.07s |
| R16-R20 | hubble + JVM GC + DB pool 探查 | 看到 hubble HTTP NaN（弃），DB pool pending=0（弃），GC duration 微变（弃） |
| R21-R25 | container.cpu.usage 排序 | 看到 ts-consign-service abnormal max 2.29 cores（"top CPU spike"）→ 第一次注意到 consign |
| R26-R30 | host-level jvm.system.cpu.load_1m by node | 自查 consign 在 worker4，order-service 在 worker5（不同 node）— 排除 cross-pod 物理争抢假说 |
| R31-R40 | 各 worker node 系统 load 对比 | 看到 worker3 (含 travel-plan / preserve) abnormal load 比 normal 高 (45→65)，但没回到 ts-travel-service 自己 |
| R41-R45 | 锁定 consign | 查 consign endpoint /consigns/order/{id} avg 10.5→102.5 (9.7x)；查 consign log → 找到 120 SEVERE NonUniqueResultException |
| 🔴 R46 锚定 | think | "ROOT CAUSE 1: ts-consign-service — 120 SEVERE NonUniqueResultException + max 2.29 cores + endpoint 9.7x" |
| R47-R49 FINAL | 输出 | "Primary Root Cause: ts-consign-service" |

**sonnet 失败点**：
1. **没识别 chaos-not-effective**：abnormal 期全数据集最大 SQL span 仅 34ms，全表 ratio_avg max 1.94（noise floor）— 这是 chaos 未生效的强指纹，sonnet 没把"全表无强 ratio"当反向信号
2. **NonUnique trap 锚定**：normal=0 abnormal=120 的 incident-only 信号是真实的，但 consign-service 不在 chaos 因果链上（业务流跟 travelPlan/preserve 无重叠）
3. **没做 chain overlap**：consign 出现的 trace 跟 incident 描述端点（travelPlan/minStation 等）的 trace_id 是否重叠 — 没查
4. **`container.cpu.usage` max 2.29 cores 单点锚定**：没并查 `jvm.cpu.recent_utilization`（abnormal 仍接近 0）+ `jvm.system.cpu.load_1m`（abnormal 反而**下降** 0.41x）— 三个 CPU 维度方向矛盾，sonnet 只用其中一个
5. **chronic check 不对称**：sonnet 验证了别人（food-service rabbitmq UnknownHost 是 chronic），但没验证自己锚定的 consign cpu 信号是不是 NonUnique 自身导致的副作用（应反查"为什么有 NonUnique → 因为 race condition → 跟 chaos target 关系？"）

### 7. 跨模型快速结论

| 项 | sonnet | qwen3.5 |
|---|---|---|
| 最终 pred | `ts-consign-service` ❌ | `ts-consign-service` ❌ |
| 锚定锚点 | NonUniqueResultException 120 + container.cpu.usage max 2.29 cores | NonUniqueResultException + queueSize 类极端 capacity metric |
| 决策风格 fingerprint | 跑了 host-level 拆分（worker4/5 不同 node）但只用来排除 cross-pod 物理争抢，没回到 service-level baseline 检查"全表无强 ratio = chaos 未生效"；锚 cpu max-only outlier 没并查 jvm.cpu.recent_utilization 反向信号 | 同样被 NonUnique incident-only 锚定，没做 chain overlap |
| 共性 vs sonnet-specific | **完全共性**：同 NonUnique trap（已在 case 283/339/1140/1421 反复出现）；都没识别 chaos-not-effective（全表 ratio_avg 都 < 2x 是 chaos 未生效的强指纹）。**sonnet-specific**：sonnet 跑了 host-level 反证（worker4/5 不同 node 排除）但用错了方向；qwen3.5 没跑这层 | |

### 8. 失败模式（用失败池标签）

| 标签 | 本 case 具体表现 | qwen3.5 对应 |
|---|---|---|
| **A8** | sonnet 锚 ts-consign-service，没验证 chain overlap：consign 业务流（GET /consigns/order/{id}）跟 incident 描述端点（travelPlan/minStation, preserve）无 trace_id 重叠。consign 不在 chaos chain 上 | 同失败：qwen3.5 也锚 consign 没验证 chain overlap |
| **A3** | sonnet 用 `container.cpu.usage` max=2.29 cores 单点 outlier 锚定 consign，没并查 `jvm.cpu.recent_utilization`（abnormal 仍 0.001 ≈ 零）+ `jvm.system.cpu.load_1m`（abnormal 0.41x **下降**）— 三个 CPU 维度方向矛盾应触发 dismiss | qwen3.5 锚 capacity metric 类似失败 |
| **A11** | sonnet 把 NonUniqueResultException 字面读为"consign service 故障"，但 NonUnique 是 application-level race condition（duplicate row in DB），caller-观察现象本身不能直接归因为 callee 故障；sonnet 没沿"为什么 race → 是否上游高频访问 / chaos 引发 retry race"反向追溯（且本 case chaos 物理未生效，根本不应有 retry 风暴） | 同失败 |
| **B9** | sonnet 没充分用 baseline cross-rank：实测全表 ratio_avg max 仅 1.94（consign）+ ratio_count 全部接近 1.0，**整个数据集没有任何 ratio_avg > 5x 的 service** — 这是 chaos-not-effective 的强指纹，sonnet 没识别"signal in noise floor"应对应 chaos 未生效 | qwen3.5 同样未识别 |
| **新模式: chaos-effectiveness gate 缺失** | sonnet 未识别"全数据集没有任何 SQL span 接近 chaos 设计 latency 量级（3669ms）+ 全表 ratio_avg max < 2x"= chaos 物理未生效。chaos 失效时所有"显眼"信号必然是 incident-period 内独立 race / 共有 noise，强行归因必导致锚 chain 外 victim | 同失败：qwen3.5 也未识别 |

**新模式提案**：A11 的扩展 / 独立的"chaos-effectiveness gate"——当全表 ratio_avg max < 2x 且全数据集 trace duration 找不到接近 chaos 设计 latency 量级的 outlier 时，应判 chaos-not-effective，结论可信度降级，避免锚 chain 外 incident-period race。是否纳入失败池请用户确认。

### 9. 失败池（17 条）使用规则

```
本 case 命中标签：A3, A8, A11, B9, 新模式(chaos-effectiveness gate)
最有效组合：B9 + A8
  - B9 强制 baseline cross-rank：发现全表 ratio_avg max 1.94 + 没任何 service ratio > 5x → 触发 chaos-effectiveness gate（新模式），结论可信度降级
  - A8 chain overlap 必查：consign trace 跟 incident 描述端点（travelPlan/minStation, preserve）无 trace_id 重叠 → 直接 dismiss consign 候选
```

### 10. 判断

- **数据是否完整**：✅（abnormal 期数据完整，但 chaos 物理未生效导致信号缺失）
- **chaos 是否生效**：❌ **未生效**。SELECT Trip / SELECT ts.trip max 仅 30-35ms（设计 3669ms），全表 ratio_avg max 1.94（noise floor）
- **真假盲区分类**：(c) chaos 未生效。本 case 应归为 `unsolvable:chaos-not-effective`，跟 case 572 / 3114 / qwen3.5 OBSERVATIONS 标的同类
- **失败模式归纳**：A8（chain overlap 缺失）+ A3（CPU 三维度方向矛盾仍单维度锚定）+ A11（NonUnique 字面语义当 callee 故障，未沿 race 因果反向追溯）+ B9（baseline cross-rank 漏识别 noise floor）+ 新模式（chaos-effectiveness gate 缺失）
- **共性 vs sonnet-specific**：
  - **完全共性**：sonnet 跟 qwen3.5 同答 consign-service，同被 NonUnique trap 抓走（已是 case 283/339/1140/1421 反复出现的跨 model 通用盲区）
  - **sonnet-specific**：sonnet 多跑了 worker-node 物理拓扑拆分，但用来"排除 cross-pod 物理争抢"而非"baseline cross-rank 反查 chaos-effectiveness"，方向用错；qwen3.5 没跑这层但失败结论一样
- **给 sonnet 中间件设计的提示**：B9 + A8 + chaos-effectiveness gate 三条组合（详见 Section 9）。核心：当全表 baseline cross-rank 暴露"signal 在 noise floor"时，应触发 chaos-not-effective gate（结论可信度降级 + 回查 incident 描述端点 ownership service 作保底候选），而不是被 incident-period 内独立 race / 共有 noise（如 NonUnique）拉走

### 11. causal_graph 正确性检验

⚠️ causal_graph root_cause = `service|ts-travel-service`，但 31 个 span 节点中 ts-travel-service 自己的 SQL span（`SELECT Trip`、`SELECT ts.trip`、`TripRepository.findByRouteId/findByTripId`、`Transaction.commit`）全部标 `["unknown", "healthy"]`，**只有间接的 `findAll` / `getTripAllDetailInfo` / `trips/left` / `trip_detail` 端点标 `high_avg_latency`**。这跟 duckdb 实测一致：chaos 物理未生效，SELECT 层无信号。但端点 wallclock 仍呈现 `high_avg_latency` 标签是图模型在多时刻合并产物——实测 trips/left abnormal avg=217ms 反而**比 normal 259ms 还低**，所以"end-point high_avg_latency" state 在本 case 也不准。

→ 本 case `service-level GT` 跟实测真因脱节（chaos 没生效，没有真因）。**该 case 不应用于 failure mode 归纳**——任何归因都是错的，无法判 sonnet 是"框架盲区"还是"数据真盲区"，应归到 `unsolvable:chaos-not-effective` 桶。
