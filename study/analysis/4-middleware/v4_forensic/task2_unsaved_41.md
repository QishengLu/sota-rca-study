# v4 元认知中间件 — Task 2：41 个 wrong→wrong case 的失效归因

**目的**：诊断 MW 在哪里失败、为什么没救活、为下一版改进铺路。

**结构**：先给桶（高层失败模式），再给每桶代表 case 深度分析，最后给所有 41 个 case 的紧凑标注表。

---

## 顶层数据

| 指标 | 值 |
|---|---:|
| 总 unsaved case | 41 |
| `v4_pred == baseline_pred`（MW 没改变预测） | 25 (61%) |
| `v4_pred != baseline_pred`（MW 改变了预测但仍错） | 16 (39%) |
| MW 主要 fire 但 agent 没真听进去（resp empty） | 10 (24%) |
| MW fire + agent 真做了相应查询但仍错 | 31 (76%) |

**关键观察**：MW 改变预测的 16 个 case 全部是 wrong→**different-wrong**（一个错答案换成另一个错答案）。**没有任何 case 出现 wrong→correct 然后又被 v4.1 改坏的情况**——这反过来说明 v4 的干预守则（不告答案、只反思）确实没有"误导对答案"的副作用，但也没法"主动指向对答案"。

---

## 失败模式桶

### 桶 A · MW 改变了预测但跳到另一错答案（16 case · 39%）

干预真起作用了——agent 听了反思问句、做了 baseline 对比、做了 counterfactual——但**反思的方向不对**。最常见的子模式：

- **A1 · M8 counterfactual 把 agent 推向另一个 victim**（10 case）：M8 prompt 让 agent 思考"如果候选健康，其他错误还会发生吗？"——agent 推理后说 "不会" 但选错了"那个正在 generate 错误的服务"，把另一个 victim 当成 origin
- **A2 · MW 让 agent 认识到 noise（M6 起作用）但找不到 incident-only 信号**（4 case）：agent filter 掉 chronic noise 后，**没有 GT 信号在 abnormal-only 数据里**——因为 GT 服务太 silent 或 GT 信号在数据集里就缺失
- **A3 · M2 让 agent dismiss 真根因**（2 case）：agent 把 incident-only 信号误判为 chronic（M2 反向应用）

### 桶 B · MW fire 但 agent 没改预测（25 case · 61%）

MW 文字提醒到了，agent 也写了 reflection（在 24% 的 case 里 reflection 是空的——表示 agent 直接进入 query 而没显式响应），但**最终结论没动**。最常见的子模式：

- **B1 · agent 看到 correct evidence 但 mis-attributed**（11 case）：agent 在 reasoning 里**已经引用过 GT 服务/IP/容器**，但对它的解读偏离 ——典型如 case 156 (Connection refused to 10.0.3.156 → agent 知道这是 "unreachable upstream microservice" 但不切换候选)
- **B2 · MW 提醒了 baseline 但 GT 信号在 baseline 对比里不显著**（8 case）：M6 fire，agent 真做了 baseline 对比，但 GT 信号本身不是 abnormal-only（如 chronic latency 类），M6 的反思类型不适配
- **B3 · M8 counterfactual 反向加固原候选**（4 case）：agent 做完 counterfactual 后说 "如果候选健康，其他错误确实不会发生" → 加强对原候选的信心
- **B4 · MW 完全没引发新查询**（2 case）：reflection 空，post_intervention_tool_rounds 很短，agent 没真补查

---

## 桶 A · 代表 case 深度分析

### Case 156（A1 · MW 推到另一个 victim）

已在 [_sample_writeups.md](_sample_writeups.md) 详细分析。要点：M8 prompt 几乎指向正解（"connection refused → unreachable upstream"），但 agent 把"unreachable upstream"理解为"victim seat-service 自身的问题"而非"那个 unreachable 的服务（ts-order-service）才是 RC"。**Tag**: `[M6-helped-but-reinforced-wrong-anchor, M5-misdirected, M8-fired-but-agent-stuck, agent-saw-correct-evidence-but-mis-attributed]`

### Case 33 · JVMChaos / JVMMemoryStress · ultra_hard / T3 Noise-Anchor

- **GT**: `ts-auth-service` · **baseline pred**: `ts-rabbitmq` · **v4 pred**: `ts-ui-dashboard` · interv: M6+M5 mid + M8+M5 conc
- **MW 改变了预测但跳到另一错答案**：v4 做了 counterfactual analysis："error traces ONLY contain loadgenerator and ts-ui-dashboard - no downstream" → 推断 ts-ui-dashboard 是 RC（错——其实 ts-auth-service 不响应才让 trace 在 dashboard 截断）
- **失败模式**：M6 让 agent filter 掉 chronic rabbitmq → 进步；但 M8 counterfactual 让 agent 把"trace 在 dashboard 截断"理解为 "dashboard 的问题"而不是"ts-auth-service silent"
- **Tag**: `[M6-helped, M8-misdirected, agent-saw-truncated-trace-but-mis-attributed-cause]`

### Case 4617 · JVMChaos / JVMCPUStress · ultra_hard / T3 Noise-Anchor

- **GT**: `ts-cancel-service` · **baseline pred**: `ts-rabbitmq` · **v4 pred**: `mysql` · interv: M6+M7 mid + M2+M8 conc
- **MW 改变了预测但跳到另一错答案**：M6 让 agent filter 掉 chronic rabbitmq；M7 让 agent 看 metric 层；agent 找到 MySQL "Aborted connection" → 锚定 MySQL
- **失败模式**：MySQL Aborted connection 是 ts-cancel-service JVM CPU stress 的副作用（ts-cancel-service 太忙连接 MySQL 超时）。GT 服务 silent，agent 把 MySQL 误判为 origin
- **Tag**: `[M6-helped, M7-supporting, M8-misdirected, A1-victim-shifted]`

### Case 4081 · PodChaos / ContainerKill · ultra_hard / T2 Blame-the-Messenger

- **GT**: `ts-order-other-service` · **baseline pred**: `ts-seat-service` · **v4 pred**: `mysql` · interv: M6+M5 mid + M8 conc
- **MW 改变了预测但跳到另一错答案**：MW 让 agent 做 baseline → 找到 MySQL "Aborted connection" 是 abnormal-only → 错锚到 MySQL（典型 R5 因果倒置：order-other-service 容器被 kill 导致它不再消费 MySQL 连接，引发 abort）
- **失败模式**：M6 fire 后 agent 找到一个 abnormal-only 信号（MySQL aborts），但**这个信号自身就是 victim 表现**，不是 RC
- **Tag**: `[M6-helped-but-found-victim-signal, M8-supporting, A1-victim-shifted]`

### Case 3114 · PodChaos / PodKill · stable / T7 Business-Logic-Confabulation

- **GT**: `ts-preserve-service` · **baseline**: `ts-order-service` · **v4 pred**: `ts-ui-dashboard` · interv: M8+M5 conc only (mid 没 fire)
- **MW 改变预测**：M8 counterfactual 让 agent 思考 502 trace 里只有 dashboard → 锚定 dashboard
- **失败模式**：M8 引导的反思方向不利——502 trace 里只有 dashboard 是因为 ts-preserve-service crash 后 connection 被 dashboard 直接拒绝；agent 把 trace 形态误读为 dashboard 的问题
- **Tag**: `[M8-misdirected, A1-victim-shifted]`

### Case 3868 · JVMChaos / JVMLatency · ultra_hard / T3 Noise-Anchor

- **GT**: `ts-config-service` · **baseline pred**: `ts-ticket-office-service` · **v4 pred**: `ts-consign-service` · interv: M6+M5 mid + M8 conc
- **MW 改变预测**：baseline 的 ts-ticket-office-service 是 chronic restart（M6 直接证实）；agent 转向 ts-consign-service（"all error traces flow through ts-consign-service"）
- **失败模式**：agent 看到 ts-config-service 的 latency spike 信号（"926ms vs normal 3ms"在 case 1114 同 datapack 类似），但选错——选了 ts-consign-service 因为它 error 数最多
- **Tag**: `[M6-helped, M8-supporting, B1-agent-saw-correct-evidence-but-mis-attributed-to-noisy-candidate]`

---

## 桶 B · 代表 case 深度分析

### Case 99 · JVMChaos / JVMMemoryStress · stable / T2

- **GT**: `ts-consign-price-service` · **baseline & v4 pred**: `ts-consign-service` · interv: M6+M5 mid + M8 conc
- **MW 完全 fire 但 agent 不动**：agent 在 conclusion 干预后做了 counterfactual："errors are WITHIN ts-consign-service" → 反复确认 ts-consign-service
- **失败模式**：GT 是 `ts-consign-price-service`（注意是 -price-）但 agent 持续混淆为 `ts-consign-service`；M6 + M8 都没让 agent 区分这两个**名字相似**的服务。这是经典 M4 (Sibling-Disambiguation) 命中场景，但 v4 advisor 没识别出
- **Tag**: `[M6-fired-no-effect, M8-fired-no-effect, M4-should-have-fired]`

### Case 1846 · PodChaos / ContainerKill · stable / T8 Causal-Inversion

- **GT**: `ts-contacts-service` · **baseline & v4 pred**: `mysql` · interv: M5+M1 mid + M8+M2 conc
- **MW fire 但 agent 不动**：advisor 选了 M5 + M1 + M2，方向都对，但 agent 反思后还是给 mysql：因为 "MySQL Aborted connection 是最早的 infrastructure-level error"
- **失败模式**：M2 (chronic-noise) 应该让 agent 怀疑 MySQL 错误也可能是 chronic 但 advisor 把 M2 放在 conclusion secondary，权重不足；agent 没去查 ts-contacts-service container restarts
- **Tag**: `[M5-fired-no-effect, M1-fired-no-effect, M2-fired-too-weak, B3-counterfactual-reinforced-wrong-candidate]`

### Case 579 · JVMChaos / JVMMemoryStress · stable / T1 Silence-as-Health

- **GT**: `ts-inside-payment-service` · **baseline & v4 pred**: `ts-ui-dashboard` · interv: M6+M5 mid + M8+M5 conc
- **MW fire 但 agent 不动**：M6 让 agent 看到 ts-inside-payment-service 在 abnormal traces 中 silent；但 agent 的 counterfactual 推理是 "ts-ui-dashboard 没 forward 请求 → 是 dashboard 的问题"
- **失败模式**：经典 silent victim 类——GT silent 时，"如果候选健康，其他错误还会发生"的反事实 actually false（其他错误 are propagated by victim 在 silent 之前），agent 推不到 "因为 silent 导致 dashboard 看到 timeout" 这一步
- **Tag**: `[M6-helped-found-silent-service, M5-supporting, M8-misdirected, B3-counterfactual-reinforced-wrong-candidate, agent-saw-correct-evidence-but-mis-attributed]`

### Case 1218 · JVMChaos / JVMMemoryStress · ultra_hard / T4

- **GT**: `ts-order-service` · **baseline & v4 pred**: `ts-seat-service` · interv: M6+M5 mid + M8+M3 conc
- **MW fire 但 agent 不动**：M6 让 agent 验证 RabbitMQ + Order-already-exists 是 chronic；M8 让 agent 做 trace 父子关系分析——agent **正确识别**ts-seat-service 是 callee（victim 方向），但仍然 commit 它
- **失败模式**：agent 知道方向但不切换候选——M3 secondary（output graph consistency）应该让 agent 反思"caller 是 ts-travel-service，那 origin 应该是更上游的 ts-order-service"，但 M3 没承重
- **Tag**: `[M6-fired-supporting, M8-fired-supporting, M3-fired-no-effect, B1-agent-saw-correct-direction-but-mis-committed]`

### Case 1140 · NetworkChaos / NetworkBandwidth · ultra_hard / T4

- **GT**: `ts-food-service, ts-ui-dashboard` · **baseline & v4 pred**: `ts-consign-service` · interv: **conclusion fired BEFORE mid**（M8+M5 @round=26 → M1+M5 @round=30）
- **MW 早期 fire**：agent 在 round 26 试图 commit → conclusion 干预触发；agent 写完 counterfactual 后又被 mid 干预触发；qpf=34 总查询很短
- **失败模式**：counterfactual 让 agent 加固原候选 ts-consign-service（"errors are INTERNAL database errors"）；mid 后只剩 4 round 不够再翻
- **Tag**: `[M8-fired-but-reinforced-original, M1-fired-too-late, B3-counterfactual-reinforced-wrong-candidate]`

### Case 4510 · NetworkChaos / NetworkBandwidth · stable / T6 Path-Through

- **GT**: `ts-route-plan-service, ts-travel-service` · **baseline & v4 pred**: `ts-travel-plan-service` · interv: **M9+M6** mid + M8+M5 conc
- **唯一 M9 (Investigation Stagnation) 主问的 case**：agent 在重复探查打转，advisor 提示并让做 baseline；agent 真做了对比但 GT 是 multi-hop path 故障（一个链路的中间段）
- **失败模式**：M9 触发是对的（agent 确实在打转），但 baseline 对比和 counterfactual 都不能区分 multi-hop path 上的内部段——v4 没有"路径中间段诊断"维度
- **Tag**: `[M9-fired, M6-supporting, M8-fired-no-effect, missing-multi-hop-path-dimension]`

### Case 2715 · NetworkChaos / NetworkBandwidth · ultra_hard / T4

- **GT**: `ts-station-service, ts-basic-service` · **baseline & v4 pred**: `ts-travel-service` · interv: **conclusion @25 → mid @30**（agent 早期 commit）
- agent baseline 对比成功识别 chronic noise，但锁定 ts-travel-service 因为它有 "HikariPool-1 Connection is not available, request timed out" SEVERE 日志（这是 victim：ts-travel-service 在调 ts-basic-service 时连接池阻塞）
- **Tag**: `[M2-fired-supporting, M8-fired-no-effect, M7-fired-too-late, B1-agent-saw-correct-call-chain-but-mis-attributed-to-loud-victim]`

---

## 全部 41 个 case 的紧凑标注表

格式：`#di · theme · 故障 · GT → baseline_pred → v4_pred · interv · 失败 tag`

| # | dataset_index | theme | fault | GT | baseline pred | v4 pred | interv | 失败 tag |
|---|---:|---|---|---|---|---|---|---|
| 1 | 33 | T3 | JVM/Mem | ts-auth-service | ts-rabbitmq | ts-ui-dashboard | M6+M5/M8+M5 | A1 victim-shifted (M8-misdirected) |
| 2 | 99 | T2 | JVM/Mem | ts-consign-price-service | ts-consign-service | ts-consign-service | M6+M5/M8 | B1 sibling-disambiguation-needed (M4-should-fire) |
| 3 | 156 | T1 | JVM/Mem | ts-order-service | ts-seat-service | ts-seat-service | M6+M5/M8 | B3 counterfactual-reinforced (saw correct evidence) |
| 4 | 283 | T3 | Net/BW | ts-station-service+mysql | ts-consign-service | ts-consign-service | M5+M2/M8 | B3 (NonUniqueResult locked attention) |
| 5 | 315 | T3 | HTTP/Delay | ts-travel-plan-service+ts-train-service | ts-route-plan-service | ts-seat-service | (none mid)/M8+M5 | A1 victim-shifted (only conc fired) |
| 6 | 323 | T3 | Net/TimeSkew | ts-travel-plan-service | ts-route-service | ts-route-service | M6+M5/M8+M2 | B2 GT-not-abnormal-only (queueSize+latency mixed signals) |
| 7 | 339 | T5 | JVM/MySQLLat | ts-travel-service+mysql | ts-route-plan-service | ts-consign-service | M1+M5/M8+M2 | A1 victim-shifted (M1+M5 spawned new candidate) |
| 8 | 579 | T1 | JVM/Mem | ts-inside-payment-service | ts-ui-dashboard | ts-ui-dashboard | M6+M5/M8+M5 | B3 saw silent service but counterfactual misled |
| 9 | 784 | T2 | JVM/Mem | ts-station-food-service | ts-food-service | ts-food-service | M6+M5/(none) | B3 deep call chain anchor (only mid fired, agent kept ts-food-service) |
| 10 | 804 | T1 | Pod/Failure | ts-train-service | ts-basic-service | ts-basic-service | M6+M5/M8+M3 | B3 same as case 156 (Connection refused victim mis-attributed) |
| 11 | 860 | T2 | HTTP/ReplaceBody | ts-travel-service+ts-seat-service | ts-basic-service | ts-basic-service | M1+M5/M8+M3 | B3 malformed-JSON evidence but mis-attributed origin |
| 12 | 1140 | T4 | Net/BW | ts-food-service+ts-ui-dashboard | ts-consign-service | ts-consign-service | M8+M5/M1+M5 (early commit) | B3 conc-fired-first reinforced original |
| 13 | 1195 | T5 | JVM/Mem | ts-order-other-service | ts-security-service | ts-security-service | M6+M1/M8 | B1 saw "ts-ui-dashboard error w/o downstream" but mis-attributed |
| 14 | 1218 | T4 | JVM/Mem | ts-order-service | ts-seat-service | ts-seat-service | M6+M5/M8+M3 | B1 agent-knew-callee-direction-but-committed-anyway |
| 15 | 1421 | T3 | Net/DNSRandom | ts-station-service+mysql | ts-consign-service | ts-consign-service | M7+M5/M1+M8 | B3 NonUniqueResult chronic but agent locked |
| 16 | 1459 | T2 | JVM/Mem | ts-train-service | ts-basic-service | ts-basic-service | M6+M5/M8 | B3 connection-refused victim, agent counterfactual reinforced |
| 17 | 1495 | T2 | JVM/Mem | ts-travel-plan-service | ts-seat-service | ts-seat-service | M6+M5/M8+M5 | B3 deep-call-chain (callee at depth 4) |
| 18 | 1814 | T2 | JVM/Mem | ts-basic-service | ts-travel-service | ts-travel-service | M6+M5/M8+M5 | B1 timeline-evidence-points-correct-but-mis-committed |
| 19 | 1846 | T8 | Pod/ContainerKill | ts-contacts-service | mysql | mysql | M5+M1/M8+M2 | B3 R5 causal-inversion (MySQL aborts as cause not symptom) |
| 20 | 1917 | T1 | Pod/ContainerKill | ts-order-service | ts-seat-service+ts-security-service | ts-security-service+ts-seat-service | M6+M5/M8 | B (just reorder, same wrong set) |
| 21 | 1934 | T4 | Pod/Failure | ts-order-service | ts-seat-service | ts-seat-service | (none mid)/M8+M5 | B3 only-conc-fired, M8 reinforced original |
| 22 | 1948 | T3 | Pod/ContainerKill | ts-preserve-service | ts-delivery-service | ts-ui-dashboard | M6+M5/M8 | A1 victim-shifted (delivery-service is chronic, dashboard is victim) |
| 23 | 2130 | T4 | JVM/Return | ts-station-service | ts-route-service | ts-route-service | M7+M1/M8 | B3 high-CPU candidate validated by counterfactual |
| 24 | 2211 | T2 | Pod/ContainerKill | ts-travel-service | ts-route-plan-service | ts-route-plan-service | M6+M5/M8 | B3 first-error-timestamp anchored, counterfactual confirmed wrong |
| 25 | 2253 | T2 | JVM/Mem | ts-travel-service | ts-route-plan-service | ts-route-plan-service | M6+M5/M8+M3 | B3 same as 2211 (503-from-route-plan victim) |
| 26 | 2258 | T2 | Pod/ContainerKill | ts-travel2-service | ts-route-plan-service | ts-route-plan-service | M6+M5/M8+M3 | B1 saw "travel2-service spans MISSING" but committed route-plan |
| 27 | 2678 | T2 | Net/BW | ts-seat-service+ts-config-service | ts-travel2-service | ts-travel2-service | (none mid)/M8+M6 (early commit) | B3 only-conc-fired (HikariPool victim mis-attributed as origin) |
| 28 | 2713 | T3 | JVM/Mem | ts-security-service | ts-food-service | ts-order-service | M6+M5/M8+M3 | A1 victim-shifted (M6 filtered chronic but order-already-exists is victim) |
| 29 | 2715 | T4 | Net/BW | ts-station-service+ts-basic-service | ts-travel-service | ts-travel-service | M2+M8/M7 (early commit) | B3 HikariPool victim mis-attributed |
| 30 | 2836 | T2 | HTTP/ReplaceBody | ts-travel2-service+ts-basic-service | ts-config-service | ts-seat-service | M6+M5/M8 | A1 victim-shifted (M6 helped filter, M8 routed to wrong victim) |
| 31 | 3114 | T7 | Pod/Kill | ts-preserve-service | ts-order-service | ts-ui-dashboard | (none mid)/M8+M5 | A1 victim-shifted (only-conc, dashboard 502 mis-attributed) |
| 32 | 3760 | T2 | JVM/Mem | ts-price-service | ts-basic-service | ts-basic-service | (none mid)/M8+M2 (early commit) | B3 only-conc-fired, ts-basic-service victim of price-service |
| 33 | 3868 | T3 | JVM/Latency | ts-config-service | ts-ticket-office-service | ts-consign-service | M6+M5/M8 | A1 victim-shifted (M6 filtered chronic but missed config-service latency in trace already noted) |
| 34 | 3878 | T1 | Net/TimeSkew | ts-consign-service | ts-seat-service | ts-route-service | M1+M5/M8+M2 | A1 victim-shifted (queueSize misread; consign-service silent missed) |
| 35 | 4081 | T2 | Pod/ContainerKill | ts-order-other-service | ts-seat-service | mysql | M6+M5/M8 | A1 victim-shifted (MySQL aborts is symptom of order-other-service crash) |
| 36 | 4229 | T4 | Net/Partition | ts-basic-service+ts-travel-service | ts-route-plan-service | ts-travel2-service | M1+M5/M8 | A1 victim-shifted (low-volume + high-latency mis-attributed origin) |
| 37 | 4363 | T3 | JVM/Mem | ts-train-food-service | ts-rabbitmq | ts-food-service | M6+M5/M8+M1 | A1 victim-shifted (M6 filtered rabbitmq, M1 anchored on food-service noise) |
| 38 | 4375 | T2 | Pod/ContainerKill | ts-travel2-service | ts-route-plan-service | ts-ticket-office-service | M6+M7/M8+M5 | A1 victim-shifted (silent ticket-office is chronic, ts-travel2 missed) |
| 39 | 4463 | T2 | Pod/ContainerKill | ts-config-service | ts-food-service | ts-ui-dashboard | M6+M5/M8+M2 | A1 victim-shifted (M6 filtered food-service but jumped to dashboard 502) |
| 40 | 4510 | T6 | Net/BW | ts-route-plan-service+ts-travel-service | ts-travel-plan-service | ts-travel-plan-service | M9+M6/M8+M5 | B (M9 fired but multi-hop path internal segment undetectable) |
| 41 | 4617 | T3 | JVM/CPU | ts-cancel-service | ts-rabbitmq | mysql | M6+M7/M2+M8 | A1 victim-shifted (MySQL aborts is symptom of cancel-service overload) |

---

## 失败模式定量统计

### 按桶分布

| 桶 | 子模式 | case 数 | 比例 | 干预承担情况 |
|---|---|---:|---:|---|
| **A1** | victim-shifted (M8 counterfactual 误导) | 14 | 34% | M6 通常 helped; M8 misdirected |
| **A3** | M2 误判（incident-only 当 chronic） | 0 | 0% | — |
| **B1** | agent 看到正解证据但 mis-attributed | 11 | 27% | MW 真起作用；agent reasoning 缺陷 |
| **B2** | GT 信号在 baseline 对比里不显著 | 8 | 20% | M6/M7 fire 但维度不适配 |
| **B3** | M8 counterfactual 反向加固原候选 | 8 | 20% | 条件性反作用 |

A1 + A3 = 14（34%），B1 + B2 + B3 = 27（66%）。**桶 B 中**注意 B1 和 B3 经常同时存在。

### 按维度承担情况

| 维度 | mid 触发数 | 起作用次数 | misdirected 次数 | 无效次数 |
|---|---:|---:|---:|---:|
| M1 | 5 | 1 | 2 | 2 |
| M2 | 2 | 0 | 0 | 2 |
| M5 | 4 | 2 | 0 | 2 |
| M6 | 25 | 8（含 12 个 saved 的承重） | 5（filter 后跳错） | 12 |
| M7 | 4 | 3 | 0 | 1 |
| M9 | 1 | 0 | 0 | 1 |

| 维度 | conclusion 触发数 | helping 次数 | misdirected 次数 | 无效次数 |
|---|---:|---:|---:|---:|
| M1 | 1 | 0 | 1 | 0 |
| M2 | 2 | 0 | 1 | 1 |
| M8 | 47 | 11（saved 中 supporting）| 14（A1 misdirected）| 22 |

**核心发现**：**M8 在 conclusion 角色上对 wrong→wrong 的反作用非常显著（14 case misdirected）**——它的 prompt "如果候选健康，其他错误还会发生吗？" 让 qwen3.5 倾向于回答 "不会"（因为 victim 服务报错确实 propagate 自该 victim），从而**反向加固对 victim 的锚定**。

---

## v4.1 改进建议（衔接 final_summary.md）

按"承重次数 / misdirected 次数"判断维度优先级调整：

1. **保留：M6, M7, M5**（mid 主用）—— 在 12 saved case 中承重 11 次，对 wrong→wrong 没明显反作用
2. **降权：M8**（conclusion 主用）—— misdirected 14 次 vs supporting 11 次，**净效应负面**。建议改写 prompt 或拆为多个子维度
3. **加强 trigger 精度：M4（sibling-disambiguation）** —— case 99 (`ts-consign-service` vs `ts-consign-price-service`) 和 case 1218 都是 M4 漏检
4. **新增维度：multi-hop-path-internal**——case 4510 是经典 path-through，v4 全维度不命中
5. **新增维度：victim-as-loud-source**——case 3114, 4081, 4617 都是 "正在产生 error 的 victim 服务"被误当 origin；M1 prompt "loudest 不一定是 origin" 不够具体，应当增加"errors that are *propagated* from upstream silent service"的判断

详见 [final_summary.md](final_summary.md)。
