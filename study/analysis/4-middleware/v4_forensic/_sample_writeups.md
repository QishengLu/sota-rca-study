# v4 元认知中间件 — Forensic 样例 writeup（2 个 case，请确认结构）

> **请你先 review 下面 2 个样例 case 的 writeup 结构**：1 个 wrong→correct（Task 1 风格），1 个 wrong→wrong（Task 2 风格）。结构 OK 我就按这个模板批量写完剩下 51 个；想调整请直接说。

下面用到的 Tag 字典（统一使用，避免歧义）：

| Tag | 含义 |
|---|---|
| `[Mx-helped]` | 该维度干预是承重的成功因素：agent 因此发起新查询/换新方向并最终走向正确答案 |
| `[Mx-supporting]` | 干预触发，agent 听进去做了相应动作，但不是承重的（如顺带发起一次 baseline 查询） |
| `[Mx-misdirected]` | 干预触发，agent 跟着走了，但走向另一个错答案 |
| `[Mx-fired-but-agent-stuck]` | 干预触发，agent 表面响应（写了 reflection），但 reasoning 没有真正改变 |
| `[Mx-shifted-wrong-answer]` | 干预改变了 agent 的预测，但从一个错答案变成另一个错答案 |
| `[agent-saw-correct-evidence-but-mis-attributed]` | agent 在 reasoning 里引用过 GT 服务，但最后挑了别的 |
| `[L1-sampling-perturbation]` | 怀疑翻盘是 sampling 噪声而非 MW 起作用（agent 没换查询/没换 reasoning，只是结论用词换了） |
| `[unsolvable:<reason>]` | 即使最理想的元认知干预也救不了（数据缺失/GT 信号在 parquet 里就找不到等） |

---

## 样例 1（wrong→correct, T2 Blame-the-Messenger 类）

### Case 281 · JVMChaos / JVMMemoryStress · `wrong→correct` · ultra_hard

**source**: `ts0-ts-station-food-service-stress-j5qdln`
**GT 根因**: `ts-station-food-service`（注入点：JVMMemoryStress on `food.controller.StationFoodController.home`，pre_duration 4 min）
**Theme**: T2_Blame-the-Messenger

**GT propagation**（来自 dossier_281.md）
- 故障注入：`ts-station-food-service` 内 JVM 内存压力（targeted method `StationFoodController.home`），symptoms = high_cpu + high_memory + restart
- 调用链：`loadgenerator → ts-ui-dashboard → ts-food-service → ts-station-food-service`
- 关键证据：`ts-station-food-service` p90 latency 0.017s → 1.268s（**75x**）；该服务在 incident 期间 **18s 重启**（normal 时段无重启）；`Duplicate entry` errors on `station_store_idx` 是恢复期 retry 副作用
- 受害者特征：`ts-food-service`（上游）报 `getFoodRequestFailed` + 503，是 chronic 现象；`ts-station-food-service` 自己在排名查询里 **不显眼**

**no-MW** (qpf=36, pred=`ts-food-service` ❌)
- phases 覆盖：trace_investigate ✓、log_investigate ✓、metric_diagnose △（碰过 hubble_http），baseline ✗
- 错误推理（最后 think_tool 反思）：
  > "ts-food-service is the ONLY service in the call chain showing Error status... ts-food-service shows 'Error' status with very high latency (3.5-4.2 seconds) ... All downstream services show 'Unset' status (healthy) ... loadgenerator shows 'Error' status (propagated from ts-food-service) ... Root Cause Service: ts-food-service"
- 失败模式：T2 Blame-the-Messenger — agent 把 loudest（log 里 ERROR 最多）的 `ts-food-service` 当根因；忽略 `ts-station-food-service` 的 Duplicate entry 数据库异常（agent 主动归类为 "separate database constraint violations, not related"）

**MW** (qpf=73, pred=`ts-station-food-service` ✓)
- 干预 1（mid @ qpf=30）：**M6（baseline-contrast reflex）primary + M5（silence ≠ health）secondary**
  - intervention 文：你跑了 30 round 全聚在 abnormal 窗口，baseline_intent_count=0；先做一次正常时段对比，看你看到的"异常"是不是 chronic 噪声 …… 也想想哪个服务**完全没**出现在排名里
  - agent 响应：
    > "I haven't compared abnormal data with normal baseline data ... I've been focused on ts-food-service because it's 'loudest' but that doesn't mean it's the root cause ... Let me do baseline comparisons now"
  - 后续动作：发起 normal vs abnormal 对比 → 发现 normal 时段 ts-food-service ERROR=269 是 chronic 的，但 ts-station-food-service p90 0.017→1.268s 是 incident-only → reasoning 转向 ts-station-food-service。**29 个 tool round 在 mid 之后，agent 真的回去查了**。
- 干预 2（conclusion @ qpf=59）：**M8（hypothesis-counterfactual）primary**
  - intervention 文：commit 前做一次反事实——如果你的候选健康，其他异常还会发生吗？另外 DB 错可能是外部因素的症状
  - agent 响应：做了 counterfactual + 又去查 ts-station-food-service 的 restart 历史 → 确认 18s restart 只在 abnormal 出现
  - 后续动作：14 个 tool round 验证，最终守住 ts-station-food-service

**承重分析**：
- **M6 是承重维度**——baseline 对比是这个 case 翻盘的因果起点：没有 baseline 对比，agent 看不见 ts-food-service 的 chronic ERROR 是 noise，也看不见 ts-station-food-service 的 75x latency 跳变。M6 触发后 agent 的查询模式发生了**真实的转向**（abnormal-only → normal vs abnormal 对比），不是表面响应。
- **M5 supporting**——agent 注意到了"哪些服务没出现"的提示但没用上（最终 RC 不是 silent service）；M5 在这个 case 里是 wasted secondary，但没有反作用。
- **M8 supporting**——counterfactual 让 agent 发现了 restart 这个最强证据，但即使没有 M8，M6 之后的 reasoning 已经倾向 ts-station-food-service；M8 把信心从 "倾向" 提到 "确认"。

**Tag**: `[M6-helped, M5-supporting, M8-supporting]` · `wrong→correct`

---

## 样例 2（wrong→wrong, T1 Silence-as-Health 类，但 MW 部分启动了）

### Case 156 · JVMChaos / JVMMemoryStress · `wrong→wrong` · ultra_hard

**source**: `ts0-ts-order-service-stress-cklk2p`
**GT 根因**: `ts-order-service`（注入点：JVMMemoryStress on order-service，spl=4，n_svc=13，n_edge=22）
**Theme**: T1_Silence-as-Health

**GT propagation**（推断自 baseline + v4 trajectory + theme）
- 故障注入：`ts-order-service` JVM 内存压力 → 服务内部缓慢/无响应；不报 ERROR 日志（被 OOM 直接吞）
- 关键证据：`ts-seat-service` 报 `503 Service Unavailable: upstream connect error... Connection refused to 10.0.3.156:8080` —— 这个 IP 即是不可达的 ts-order-service；ts-order-service 在 abnormal 数据里**几乎缺席**（21 行 normal ERROR vs abnormal 也 ~20 行，反而看不出突出）
- 受害者特征：ts-seat-service / ts-travel-plan-service / ts-route-plan-service / ts-travel-service 全部报 503/504，**call chain 越深越显眼**，但都是上游/下游的级联

**no-MW** (qpf=48, pred=`ts-seat-service` ❌)
- phases：trace ✓ / log ✓ / metric ✓（hubble_http p99=10s）/ baseline ✗
- 错误推理：
  > "ts-seat-service has the MOST errors (168 Error status codes) ... HTTP request duration p50/p90/p95/p99 all hitting 10 seconds ... Root Cause: ts-seat-service with HIGH_LATENCY"
- 失败模式：T1 Silence-as-Health — 真根因 ts-order-service 在排名查询里被 chronic noise 淹没；agent 把"call chain 末端 + loudest latency"当 RC

**MW** (qpf=62, pred=`ts-seat-service` ❌)
- 干预 1（mid @ qpf=30）：**M6 primary + M5 secondary**
  - agent 响应：
    > "The advisor is absolutely right ... I need to: (1) Compare abnormal vs normal traces (2) Check if ts-seat-service errors exist in normal conditions too (3) Look for services that appear in normal data but are missing/silent in abnormal data ... Let me do baseline comparisons now"
  - 后续动作（19 tool round）：
    1. baseline 对比成功 → 发现 ts-seat-service 56 SEVERE (abnormal) vs 0 (normal) ✓
    2. silent service 探查 → **发现 ts-cancel-service 在 abnormal 完全缺失** —— agent 注意到这个，但归类为"unrelated to incident endpoints"，错过了
    3. 还是漏看了 ts-order-service 的对比（因为 ts-order-service 不是 silent，只是 noise 等级被淹没）
- 干预 2（conclusion @ qpf=49）：**M8 primary**（特别强：明确指出"connection refused 是 upstream 的问题"）
  - intervention 文：do counterfactual + "the 'connection refused' pattern points to a service that is unreachable — is that because the candidate itself is broken, or because something it depends on is gone? Those are two different root causes"
  - agent 响应：
    > "The deeper question is: Is ts-seat-service itself broken, or is something it depends on broken? The error 'Connection refused to 10.0.3.156:8080' means ts-seat-service cannot reach a dependency. This could be: 1. A database 2. Another microservice not instrumented with traces 3. A cache or external service ... Let me check if ts-food-service might..."
  - **agent 看到了正解**："Connection refused to 10.0.3.156 → unreachable upstream microservice"——10.0.3.156 就是 ts-order-service 的 pod IP，这正是 GT。但 agent 没把"unreachable upstream microservice"反查到 ts-order-service。
  - 后续动作（13 tool round）：又回头看 trace → 重新论证 "if ts-seat-service were healthy, upstream services would NOT have errors" → 锁回 ts-seat-service。

**承重分析**：
- **M6 部分起作用**：agent 真做了 baseline 对比，发现 ts-seat-service 异常很显著（56 SEVERE vs 0），这反而**强化**了 agent 错误的 anchor —— baseline 对比把 ts-seat-service 的"异常"指标做成了硬证据。M6 工作了，但 baseline 对比本身在这个 case 里**会反噬**（victim service 的 503 也是 incident-only 的）。
- **M5 部分起作用，但 mis-attributed**：agent 找到了一个 silent service（ts-cancel-service），但这是无关 silent。GT 的 ts-order-service **不是 silent**——它在 normal 也有 21 ERROR，所以 M5 的 "absence from data" 检测维度对它不灵敏。
- **M8 fired but agent stuck**：M8 给出的反事实问句**已经几乎指向正解**——"connection refused 是上游 unreachable"——agent 也复述了这个判断，但没有把"unreachable upstream"翻译成"那个 unreachable 的服务才是 RC"，反而绕回 "if seat-service were healthy ... " 再次确认 ts-seat-service。这是经典的 R5 因果倒置：agent 把"victim 在 call chain 末端"当成了"upstream 的源头"。

**Tag**: `[M6-helped-but-reinforced-wrong-anchor, M5-misdirected, M8-fired-but-agent-stuck, agent-saw-correct-evidence-but-mis-attributed]` · `wrong→wrong`

**改进信号（feed v4.1）**：
- **M6 缺陷**：M6 prompt "what you're labeling abnormal might be chronic noise" 提示的是**虚假异常**方向；但 victim service 的"异常"是真的，只是因果逻辑上是受害而非源头。M6 没有覆盖"异常显著但因果上是 victim"。
- **M8 prompt 已经写得很好**——明确说了 "connection refused → unreachable upstream"——但 qwen3.5 没有把这个语义信号翻译成"切换 RC 候选"。这是 instruction-following 缺陷，不是 prompt 设计缺陷；要解决需要更强 trigger（例如检测 reasoning 里出现 "Connection refused / upstream / dependency / unreachable" 关键词时直接附加一句"那个 unreachable 的服务就是新候选"）。
