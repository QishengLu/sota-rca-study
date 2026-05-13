## Sonnet Case 323 · `ts0-ts-travel-plan-service-time-rjdx4x` · TimeSkew (负向 -84s)

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 323 |
| GT 根因 | `ts-travel-plan-service` |
| sonnet pred | `ts-config-service` ❌ |
| sonnet rounds | 21 (effective tool rounds) |
| qwen3.5 pred | `ts-route-service` ❌ |
| **共性错** | ✅ 在 53 case 列表（两 model 各自锚到不同 victim） |
| chaos type | TimeChaos (fault_type=16, time_offset=-84s) |
| tier | stable |

### 2. GT 注入

```
fault_type: 16 = TimeChaos
display_config:
  injection_point: { app_label: ts-travel-plan-service,
                     pod_name: ts-travel-plan-service-b8f74cc87-4n29n }
  duration: 4 (min)
  time_offset: -84  (clock 回拨 84 秒)
ground_truth: service=[ts-travel-plan-service]
```

### 3. chaos 机制

TimeChaos 通过 chaos-mesh 在目标 pod 内 syscall 拦截 `clock_gettime` / `gettimeofday`，把返回的时间向**过去**偏移 84 秒（仅在该 pod 内可见，host clock 不变）。后果：
- pod 内 JVM 看到的 `System.currentTimeMillis()` 比真实时间早 84s → 各种基于 wall clock 的 deadline / timeout / cache TTL 计算错乱（认为请求已超时 / 缓存已过期）→ 大量 retry + 资源回收循环 → JVM CPU 烧高
- pod 内 OTel SDK / hubble eBPF 在采样时打的时间戳会落到很旧的时间桶，与采集端的真实 wall clock 桶对不齐 → hubble metric 全 NaN
- pod 自己 server-side span 处理的内部 latency 没变（chaos 没动 syscall I/O 时间），但 endpoint wallclock 量到的 duration 暴涨（deadline retry + GC stalls）

预期因果链：travel-plan-service pod 内时钟回拨 → 内部 deadline / TTL 错算 → JVM thread 反复 retry → jvm.system.cpu.load_1m 飙升 + endpoint duration 27x + hubble NaN + trace count -88%（线程被 retry 占满，新请求 admit 不进来）。

### 4. 调用树（normal 期实测）

```
loadgenerator
  └─ ts-ui-dashboard
      ├─ POST /travelPlan/cheapest    ──┐
      ├─ POST /travelPlan/quickest    ──┼─→ ts-travel-plan-service          ◀── GT (chaos)
      └─ POST /travelPlan/minStation  ──┘     └─ ts-route-plan-service       (cascade victim)
                                              └─ ts-travel-service / ts-seat-service / ts-config-service
                                                                              (chain 上多 hop callee, 全部排队 victim)
```

### 5. 关键 duckdb 证据

#### chaos 直接证据（GT 服务 ts-travel-plan-service）

| 信号 | normal | abnormal | ratio |
|---|---|---|---|
| trace count | 912 | 108 | **0.12** (-88%) |
| service-level avg duration (ms) | 185.6 | 2164 | **11.7x** |
| endpoint `quickest` avg (ms) | 543.4 | 14800.7 | **27.2x** |
| endpoint `minStation` avg (ms) | 769.8 | 7946.3 | **10.3x** |
| endpoint `cheapest` avg (ms) | 573.3 | 4922.5 | **8.6x** |
| `jvm.system.cpu.load_1m` | 43.3 | 513.3 | **11.85x** |
| `jvm.system.cpu.utilization` | 0.089 | 0.694 | **7.79x** |
| `hubble_http_request_duration_p95` | 0.83 | NaN | (TimeSkew 指纹) |
| `hubble_http_request_duration_p99` | 0.86 | NaN | (TimeSkew 指纹) |

→ TimeSkew 五件套齐全：endpoint 暴涨 + hubble NaN + jvm.cpu.load_1m 飙 + trace count 大跌 + log silent on errors。**ts-travel-plan-service 在 service-level ratio_avg 排名第一（11.7x）+ ratio_count 倒数第一（0.12）**——baseline 全表 cross-rank 一眼可见。

#### 误锚 service 实情（ts-config-service）

| 信号 | normal | abnormal | ratio |
|---|---|---|---|
| trace count | 5350 | 2040 | 0.38（系统普遍 -60%） |
| service-level avg duration | 2.4 | 17.6 | 7.3x（cascade 中段排队） |
| `jvm.system.cpu.load_1m` (worker5) | 27.6 | 411.5 | 14.91x |
| `container.cpu.usage` | 0.086 | 0.118 | **1.38x**（pod 自己几乎不烧 CPU） |
| `jvm.cpu.recent_utilization` | — | — | (类似 normal) |

→ `container.cpu.usage` ratio 仅 1.38x = **config-service 这个 pod 自己的 CPU 没饱和**。jvm.system.cpu.load_1m 飙到 411 是 host-level（worker node）信号，**不是 pod-level**。

#### host-level metric 反证（A6 决定性证据）

`jvm.system.cpu.load_1m` 按 (service, worker_node) 分桶：

| service | node | avg | max |
|---|---|---|---|
| **ts-travel-plan-service** | worker5 | **513.3** | 861.25 |
| ts-travel2-service | worker5 | 411.6 | 896.53 |
| ts-wait-order-service | worker5 | 411.5 | 861.25 |
| **ts-config-service** | worker5 | **411.5** | 861.25 |
| ts-station-food-service | worker6 | 357.8 | 738.5 |
| ts-execute-service | worker1 | 337.9 | 727.15 |
| ts-admin-order-service | worker1 | 337.9 | 727.15 |

→ worker5 上四个 pod 的 jvm.system.cpu.load_1m **数值精确相同**（411.5 / 861.25）= host-level metric 的决定性指纹。worker1 / worker6 上多个 pod 也分别相同。这强烈证明这个 metric 是 worker node 整体负载（系统级 load average），不是单 pod 信号。**而且：travel-plan-service 在 worker5 上 avg=513 高于 config-service 的 411**——sonnet 自己列出的 reflection 已经看到这个数字，但仍然锚 config-service。

### 6. sonnet 完整推理路径

sonnet 跑 21 round → `ts-config-service` ❌

| Round | 行为 | 关键决策 |
|---|---|---|
| R1-R3 | schema discovery + 端点级 trace 扫描 | 看到 quickest/minStation/cheapest 端点 27x / 10x / 8x，方向**正确**指向 ts-travel-plan-service 端点 |
| R4-R5 | normal vs abnormal endpoint compare | 明确得到 "27x increase!" 的结论，写在 think_tool 里 |
| R6-R7 | 顺 trace 往下游钻 | 转向看 ts-route-plan-service / ts-travel-service / ts-seat-service 下游 |
| R8-R9 | 单 trace deep dive (longest quickest) | 列出 trace 中 ts-config-service GET /api/v1/configservice/... 慢 spans |
| 🔴 R10 锚定瞬间 | think | "ts-config-service: SELECT Config avg 1.4ms→17.8ms (12x)... Now I have very clear evidence" — 把 cascade 链上的 config 慢当成 origin |
| R11-R13 | 查 config-service 自身 metric | jvm.system.cpu.load_1m 27.6→411.5 (15x) → think_tool 标 "CRITICAL FINDING" |
| 🟡 R14 反证检测 | 自查全 service 的 jvm.system.cpu.load_1m + worker_node | 看到 "ALL services show high CPU load - cluster-wide issue"，并列出 **ts-travel-plan-service avg 513 max 861 (worker5)** + ts-config-service avg 411 max 861 (worker5) |
| 🔴 R15-R20 反证后没回退 | think | 承认 cluster-wide 但**仍然**锚 config-service。理由（self-reflection 原话）："config is critical infra service that everyone depends on" — 用语义先验取代了实测：travel-plan-service 在同一 worker 上 jvm.cpu **更高**且 service ratio **更高** |
| R21 FINAL | 输出 | "Root Cause: ts-config-service experiencing HIGH CPU pressure on worker5 node" |

**sonnet 失败点**：
1. R10 把 cascade 链上 config-service 的 SELECT Config 12x 当 origin（端点 ratio 锚定，没问"chaos 物理机制能否解释 SELECT 慢"）
2. R14 已有强反证（同 worker5 上 4 个 pod 的 jvm.system.cpu.load_1m 数值精确相同 = host-level；travel-plan-service 在同 host 上 avg 513 反而**更高**），但没回退
3. 没查 `container.cpu.usage`（pod-level）：实测 config-service 1.38x，travel-plan-service 信息没查 — 否则 pod-level 与 host-level 反差立现
4. 没识别 hubble HTTP 在 GT 上 abnormal 期全 NaN 这个 TimeSkew 指纹
5. 没回到第一轮 service-level ratio_avg 排序（GT 排第一 11.7x，且 ratio_count 0.12 倒数第一）做交叉

### 7. 跨模型快速结论

| 项 | sonnet | qwen3.5 |
|---|---|---|
| 最终 pred | `ts-config-service` ❌ | `ts-route-service` ❌ |
| 锚定锚点 | jvm.system.cpu.load_1m 411.5 (15x) on config（实为 worker5 host-level） | queueSize=209 + db.client.connections.wait_time=272s on ts-route-service（cascade 末端 victim 的排队 metric） |
| 决策风格 fingerprint | 跑了 host-level 拆分**看到了反证**（同 worker 上多 pod 数值相同 + GT 在同 host 反而更高）但语义先验（"config is critical infra"）压倒实测 | 没拆 host-level；被 cascade 末端 capacity-类 metric 极端值锚定，把 victim queue 升高读成 origin 处理慢 |
| 共性 vs sonnet-specific | **共性**：都把 cascade 中段/末端 victim 当 origin；都没识别 TimeSkew 五件套（hubble NaN + jvm.cpu 飙 + endpoint 暴涨 + trace 跌 + log silent）。**sonnet-specific**：sonnet 自己跑了 host-level 反证查询且看到反证仍不回退（A2 反证不回退 + A6 host vs pod 误读）；qwen3.5 是根本没查 host-level 拆分 | |

### 8. 失败模式（用失败池标签）

| 标签 | 本 case 具体表现 | qwen3.5 对应 |
|---|---|---|
| **A6** | sonnet R14 看到 worker5 上 4 个 pod 的 jvm.system.cpu.load_1m 数值精确相同（avg 411.5、max 861.25 完全一致），自己已写 "ALL services show high CPU load - cluster-wide issue"，但仍把 411.5 这个 host-level 数值当 config-service 自身 pod 信号锚定 | nan（qwen3.5 没跑 host-level 拆分，没暴露此失败模式） |
| **A2** | sonnet R14 已检测到反证（同 host 上 GT travel-plan-service avg 513 反而**更高**于 config 的 411），但 R15-R20 用"config is critical infra"语义先验压实测，没强制重跑 baseline 三件 SQL 也没让强反证 sticky | qwen3.5 没明确反证回退失败（其失败在前置 SQL 漏跑） |
| **A3** | sonnet 用 jvm.system.cpu.load_1m 单一 metric 15x ratio 锚 config，没并查 `container.cpu.usage`（pod-level，实测 config 仅 1.38x）+ baseline 全表绝对值排名（实测 GT travel-plan-service 在同一 metric + 同一 host 上更高） | qwen3.5 用 queueSize / connection wait_time 单一 capacity metric 极端值锚 route-service，没区分"自己慢"vs"被 hammer" |
| **B3** | sonnet 没显式 list 查 `container.cpu.usage` / `jvm.cpu.recent_utilization` 这两个 pod-level 指标（与 host-level jvm.system.* 是 A6 反证的关键对照）—— 否则一查即知 config pod 本身只 1.38x，不是 origin | qwen3.5 同样没分 pod-level vs host-level metric 查 |
| **B9** | sonnet 没回到 service-level baseline cross-rank：实测 ts-travel-plan-service ratio_avg 11.7x（全表第一）+ ratio_count 0.12（全表倒数第一），baseline 双扫直指 GT。sonnet 在 R3 看过部分排名但没用作 R14 反证 sticky 锚点 | qwen3.5 同样没坚持 baseline cross-rank（被 cascade victim 的极端 capacity-metric 拉走） |

**新模式提案**：暂无。本 case 全部命中现有 17 条标签（A6 / A2 / A3 / B3 / B9）。

### 9. 失败池（17 条）使用规则

```
本 case 命中标签：A2, A3, A6, B3, B9
最有效组合：A6 + B3 + A2
  - B3 强制查 pod-level container.cpu.usage / jvm.cpu.recent_utilization → 暴露 config pod 自己只 1.38x
  - A6 host vs pod 区分规则：worker5 上多个 pod 在 jvm.system.cpu.load_1m 数值相同 → 自动判定 host-level，不归属任一 pod
  - A2 反证强制回退：当前锚 config-service 已被 host-level 反证否决 → 强制重跑 baseline cross-rank（B9） → 浮现 GT travel-plan-service ratio_avg 11.7x + ratio_count 0.12
```

### 10. 判断

- **数据是否完整**：✅ TimeSkew 指纹完整，host-level vs pod-level metric 都齐全
- **chaos 是否生效**：✅ TimeSkew 五件套齐全（endpoint 27x / hubble NaN / jvm.cpu 11.85x / trace 0.12 / log silent on errors）
- **真假盲区分类**：(b) 框架/模型盲区。数据完整且信号清晰（GT 在 ratio_avg + ratio_count 双扫第一），sonnet 已查到反证但被语义先验压制
- **失败模式归纳**：A6（host-level metric 误读为 pod-level）+ A2（强反证后未回退，"config is critical infra" 语义先验压实测）+ A3（单一 metric ratio 锚定无 pod-level 对照）+ B3（pod-level container.cpu.usage 漏查）+ B9（baseline cross-rank 漏回看）
- **共性 vs sonnet-specific**：
  - **共性**（两 model 共偏离）：都没识别 TimeSkew 五件套作为 chaos 类型先验；都把 cascade 链上某个非 origin 节点（config 中段 / route 末端）当 origin
  - **sonnet-specific**：sonnet 实际**跑出了** host-level vs pod-level 拆分查询并看到反证（同 worker 多 pod 数值相同 + GT 在同 host 反而更高），但语义先验压实测（A2 + A6 联合失败）。qwen3.5 是根本没跑这层，属于"信息没拿到"，sonnet 是"信息拿到了但被推翻"——sonnet 的失败更"高级"也更危险，因为反证查询本身已经做对了
- **给 sonnet 中间件设计的提示**：A6 + B3 + A2 三条组合（详见 Section 9），核心是用 pod-level 物理指标（container.cpu.usage / jvm.cpu.recent_utilization）作为 host-level 信号（jvm.system.cpu.load_1m）的强制对照，并把已检测到的反证升格为不可被语义先验否决的 sticky 反证

### 11. causal_graph 正确性检验

causal_graph 节点核对通过：root_cause `service|ts-travel-plan-service` + 4 个 endpoint 节点（cheapest / quickest / minStation 各对应的 controller + POST endpoint）全部标 `injection_affected` + `high_avg_latency` + `high_p99_latency`，与 duckdb 实测端点 ratio 8.6-27.2x 一致。`healthy` 跟异常状态共存属于多时刻合并产物。
