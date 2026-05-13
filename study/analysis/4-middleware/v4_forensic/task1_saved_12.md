# v4 元认知中间件 — Task 1：12 个 wrong→correct case 的 forensic 归因

**目的**：判断这 12 个翻盘是 MW 起作用还是 sampling 巧合。每个 case 给出（GT 真相 / baseline 错误推理 / v4 干预 + agent 响应 / 承重维度判断 / Tag）。

**数据范围**：53-case 稳定失败集（k=5 baseline 中至少 4 次错），其中 12 个 wrong→correct，21% 在 ultra_hard slice (5/5 fail) 上。

**目录**

| # | dataset_index | tier | theme | n_interv | 承重维度 | 类别 |
|---|---:|---|---|---:|---|---|
| 1 | 281 | ultra_hard | T2 Blame-the-Messenger | 2 | M6 | MW-helped |
| 2 | 572 | stable | T4 Amplitude-Greed | 0 | — | sampling-perturbation |
| 3 | 807 | stable | T1 Silence-as-Health | 2 | M7 | MW-helped |
| 4 | 1114 | ultra_hard | T1 Silence-as-Health | 2 | M5 | MW-helped |
| 5 | 1143 | ultra_hard | T3 Noise-Anchor | 2 | M7 | MW-helped |
| 6 | 1394 | ultra_hard | T1 Silence-as-Health | 2 | M7 | MW-helped |
| 7 | 2390 | stable | T3 Noise-Anchor | 2 | M6 | MW-helped |
| 8 | 2988 | stable | T5 Query-Blindness | 2 | M6 | MW-helped |
| 9 | 3059 | stable | T3 Noise-Anchor | 1 | M6 | MW-helped |
| 10 | 3716 | ultra_hard | T3 Noise-Anchor | 2 | M6 | MW-helped |
| 11 | 4032 | stable | T1 Silence-as-Health | 2 | M1 | MW-helped |
| 12 | 4353 | ultra_hard | T2 Blame-the-Messenger | 2 | M5 | MW-helped |

**净 MW 翻盘 = 11/12（91.7%）**，1 个 case (572) 完全没触发 MW，可能是 sampling 巧合。

Tag 字典见 [_sample_writeups.md](_sample_writeups.md) 顶部。

---

## 1. Case 281 · JVMChaos / JVMMemoryStress · `wrong→correct` · ultra_hard

**source**: `ts0-ts-station-food-service-stress-j5qdln` · **GT 根因**: `ts-station-food-service` · **Theme**: T2 Blame-the-Messenger

**GT propagation**
- 故障注入：`ts-station-food-service` 内 JVM 内存压力（targeted method `StationFoodController.home`）
- 调用链：`loadgenerator → ts-ui-dashboard → ts-food-service → ts-station-food-service`
- 关键证据：`ts-station-food-service` p90 latency 0.017s → 1.268s（**75x**）；该服务在 incident 期间 **18s 重启**；`Duplicate entry on station_store_idx` 是恢复期 retry 副作用
- 受害者特征：`ts-food-service` 报 `getFoodRequestFailed` + 503，是 chronic 现象；GT 服务在排名查询里**不显眼**

**no-MW** (qpf=36, pred=`ts-food-service` ❌)
- 错误推理（最后 think_tool 反思）：
  > "ts-food-service is the ONLY service in the call chain showing Error status... shows 'Error' status with very high latency (3.5-4.2 seconds) ... All downstream services show 'Unset' status (healthy) ... Root Cause Service: ts-food-service"
- 失败模式：T2 — agent 把 loudest（log 里 ERROR 最多）的 `ts-food-service` 当根因；主动把 `ts-station-food-service` 的 Duplicate entry 归类为 "separate, not related"

**MW** (qpf=73, pred=`ts-station-food-service` ✓)
- 干预 1（mid @ qpf=30）：**M6 primary + M5 secondary**
  - agent 响应（reflection）："I haven't compared abnormal data with normal baseline data ... I've been focused on ts-food-service because it's 'loudest' but that doesn't mean it's the root cause ... Let me do baseline comparisons now"
  - 后续 29 round：发起 normal vs abnormal 对比 → 发现 ts-food-service ERROR=269 in normal (chronic)，但 ts-station-food-service p90 0.017→1.268s 是 incident-only → reasoning 转向 GT
- 干预 2（conclusion @ qpf=59）：**M8 primary**
  - agent 响应：做反事实 → 发现 `ts-station-food-service` 18s 重启只在 abnormal 出现 → 守住 GT

**承重分析**：**M6 是承重维度**——baseline 对比是这个 case 翻盘的因果起点：没有 baseline 对比，agent 看不见 ts-food-service 的 chronic ERROR 是 noise，也看不见 GT 的 75x latency 跳变。M6 触发后 agent 的查询模式**真实转向**（abnormal-only → normal vs abnormal 对比）。M8 把"倾向"提到"确认"——supporting 但非承重。

**Tag**: `[M6-helped, M5-supporting, M8-supporting]` · `wrong→correct`

---

## 2. Case 572 · HTTPFault / HTTPResponsePatchBody · `wrong→correct` · stable

**source**: `ts1-ts-food-service-response-patch-body-qjhx5h` · **GT 根因**: `ts-food-service`, `ts-train-food-service` · **Theme**: T4 Amplitude-Greed

**GT propagation**
- 故障注入：HTTP response body patch 在 `ts-food-service` ↔ `ts-train-food-service` 链路
- 关键证据：`ts-food-service` 是错误链最早源头（first error 18:12:49，比 ts-consign-service 早 ~2 分钟）；其错误是 `UnknownHostException: ts-rabbitmq` (downstream MQ 故障下放线索)
- baseline 把 ts-consign-service 当根因（最大错误数 366），但 ts-consign-service 的错误 18:14:42 比 ts-food-service 晚

**no-MW** (qpf=44, pred=`ts-consign-service` ❌)
- 错误推理：
  > "ts-consign-service has the most errors (366 error spans out of 1122) ... errors are in ConsignRepository.findByOrderId database query ... loadgenerator → ts-ui-dashboard → ts-consign-service ... it's experiencing severe latency"
- 注意：baseline **的确**做了 timeline 分析并看到 ts-food-service 18:12:49 早于 ts-consign-service 18:14:42，但仍归到 ts-consign-service 因为 "its database errors are independent"
- 失败模式：T4 — 用 error 体量（366）压倒早期时间证据

**MW** (qpf=40, pred=`ts-food-service` ✓, **n_interventions=0**)
- v4 advisor **完全没触发**（mid 和 conclusion 都返回 `triggered=false`）
- agent 这次自己跑了 timeline 分析，结论变成 "ts-food-service first error at 18:12:49.176 is the EARLIEST" → 选了 ts-food-service
- 没有 advisor 介入，唯一不同就是 sampling

**承重分析**：**这个翻盘很可能是 L1 sampling 噪声**。该 case 是 stable 类（FFFPF，p_fail=0.8），意味着 5 个 baseline 重采样里有 1 个曾经答对过——v4 这一跑碰巧落在了"对的那 20%"分布。MW 没起作用（advisor 看了 trajectory 觉得 agent 没问题，没触发）。

**Tag**: `[no-MW-fired, L1-sampling-perturbation]` · `wrong→correct`

**改进信号**：advisor 在 mid-check 时看到 trajectory 已经包含 timeline 分析，可能判断"agent 已经在做正确的工作"——这是合理的；但 advisor 没意识到 baseline 在做完 timeline 后会再次被 noise 锚定。**v4.1 可考虑**：mid-check 时若 trajectory 包含早期 candidate 但又有 loud noise candidate，主动注入 M1（loudness-anchor 反思）。

---

## 3. Case 807 · JVMChaos / JVMMemoryStress · `wrong→correct` · stable

**source**: `ts1-ts-train-service-stress-jfr96k` · **GT 根因**: `ts-train-service` · **Theme**: T1 Silence-as-Health

**GT propagation**
- 故障注入：`ts-train-service` JVM 内存压力 → CPU 飙到 92% → 触发 container restart
- 调用链：`loadgenerator → ts-ui-dashboard → ts-train-service`（trains 端点）
- 关键证据：ts-train-service 的 spans **从 14:42:10 完全消失**（normal 时段每 20s 有 227 个 span）；同时 k8s.container.restarts 从 0 跳到 1 at 14:42:12；92% CPU 是触发 OOMKill 的根因
- 隐藏特征：trains 端点的 503 trace 里 **完全没有 ts-train-service span**（请求根本没到达），baseline 容易误判为"上游问题"

**no-MW** (qpf=53, pred=`ts-basic-service` ❌)
- 错误推理：
  > "ts-basic-service has SEVERE errors with: '503 Service Unavailable: upstream connect error... Connection refused' ... ts-basic-service is trying to connect to an upstream service that is refusing connections ... Root Cause: ts-basic-service"
- 失败模式：T1 Silence-as-Health — GT 服务（ts-train-service）silent 了，agent 把次最显眼的 ts-basic-service（在另一个 endpoint 上有错）当 RC

**MW** (qpf=82, pred=`ts-train-service` ✓)
- 干预 1（mid @ qpf=30）：**M6 primary + M7 secondary**
  - agent reflection（无显式 think_tool 输出，但后续 31 round 行为）：
    1. baseline 对比 → 发现 trains 端点 503 是 incident-only
    2. **运行时层补查**（M7 提示）→ 查 `k8s.pod.cpu_limit_utilization` → 发现 ts-train-service CPU 92% 飙升
    3. 又查 trace 发现 ts-train-service spans 从 14:42:10 消失
- 干预 2（conclusion @ qpf=61）：**M8 primary**
  - intervention 文：'span 缺失'有多种解释：服务过载来不及记录 vs 请求根本没到达 → agent 区分了这两种
  - agent 后续 21 round → 找到 container restart 时间戳 14:42:12 → 闭环

**承重分析**：**M7 是承重维度**——M6 单独不够，因为 baseline 对比已经在 baseline 推理里隐含做了（agent 知道 503 是 incident-only），但 baseline 的解读是"upstream connection refused = upstream 服务的问题"。**M7 强制补查运行时层**，agent 才查到 CPU 92% 和 container.restarts 这些关键信号。M6 做了 supporting（强化 abnormal-only 的判断），M8 做了 supporting（让 agent 区分 silent 的两种成因）。

**Tag**: `[M7-helped, M6-supporting, M8-supporting]` · `wrong→correct`

---

## 4. Case 1114 · JVMChaos / JVMMemoryStress · `wrong→correct` · ultra_hard

**source**: `ts2-ts-config-service-stress-j8gm95` · **GT 根因**: `ts-config-service` · **Theme**: T1 Silence-as-Health

**GT propagation**
- 故障注入：`ts-config-service` 受 JVM 压力 → restart at 04:25:16，500x latency 跳变
- 关键证据：normal 时段 ts-config-service 0 restart；abnormal 时段 1 restart；normal latency 1.8ms vs abnormal 926ms (500x)；ts-seat-service 收到的"Connection refused"是因为它在调 ts-config-service
- ts-ticket-office-service 在 normal/abnormal 都有 3 restart（chronic noise，不是 RC）

**no-MW** (qpf=75, pred=`ts-seat-service` ❌)
- 错误推理：
  > "ts-seat-service is the ONLY service with Error status codes (117 error spans) ... HTTP 503 'upstream connect error... Connection refused' ... agent 注意到正解信号：'ts-seat-service's GET calls normally have ts-config-service as child spans' ... but ts-config-service shows NO errors ... 'It's working fine for other callers' ... 最后 commit 到 ts-seat-service"
- 失败模式：T1 — GT 服务 ts-config-service 自己**没报错**（restart 期间太短 + 其他 caller 还能成功），baseline 把它的"无错误"误读为"健康"

**MW** (qpf=82, pred=`ts-config-service` ✓)
- 干预 1（mid @ qpf=30）：**M5 primary + M1 secondary**
  - intervention 文聚焦于"connection refused 指向 dependency，那个 dependency 可能 silent 而非 healthy"——非常精准
  - 后续 48 round：agent 重新审视 ts-config-service trace，注意到 latency spike (926ms vs normal 3ms)；查 `k8s.container.restarts` → 发现 ts-config-service 04:25:16 restart；又查 ts-ticket-office-service 也有 restart 但是 chronic
- 干预 2（conclusion @ qpf=78）：**M8 primary + M2 secondary**
  - agent 响应（已附在 cache 中）：完整执行 baseline 对比（normal vs abnormal restart count + latency）→ ts-ticket-office-service 是 chronic（M2 提示），ts-config-service 是 incident-only → 闭环
- 后续 4 round 走 compress

**承重分析**：**M5 是承重维度**——agent 在 baseline 推理里**已经看到了正解的轮廓**（"normally ts-seat-service calls ts-config-service"），但被 ts-config-service 的"0 ERROR logs"误导成"它 healthy"。M5 的 intervention 文恰好打在"silent ≠ healthy"这个具体盲点上，agent 立即重审 ts-config-service。M2 的 chronic-noise 提示是 supporting：让 agent 不被 ts-ticket-office-service 的 chronic restart 误导。M8 supporting。

**Tag**: `[M5-helped, M1-supporting, M8-supporting, M2-supporting]` · `wrong→correct`

---

## 5. Case 1143 · PodChaos / ContainerKill · `wrong→correct` · ultra_hard

**source**: `ts2-ts-food-service-container-kill-cqcxsh` · **GT 根因**: `ts-food-service` · **Theme**: T3 Noise-Anchor

**GT propagation**
- 故障注入：`ts-food-service` 容器被 kill → restart at 08:27:06；恢复期间整体不可达 10s
- 关键证据：ts-ui-dashboard 503 from 08:26:57（10s before ts-food-service log first error）→ 因为 ts-food-service 这段时间不可达；ts-ticket-office-service 在 normal/abnormal 都有 3 restart（chronic noise）；ts-rabbitmq DNS error 是 ts-food-service 重启后的副作用
- 隐藏特征：log 上看 RabbitMQ DNS error 最早，agent 容易锚定 ts-rabbitmq

**no-MW** (qpf=35, pred=`ts-rabbitmq` ❌)
- 错误推理：
  > "Multiple services failing to connect to ts-rabbitmq with 'UnknownHostException: ts-rabbitmq' ... earliest error timestamps converge on ts-rabbitmq DNS issue ... Root Cause: ts-rabbitmq is unavailable"
- 失败模式：T3 Noise-Anchor — chronic ts-rabbitmq 错误最显眼，agent 锚定它

**MW** (qpf=74, pred=`ts-food-service` ✓)
- 干预 1（mid @ qpf=30）：**M7 primary + M5 secondary**
  - intervention：runtime layer 没查 + silence ≠ healthy
  - 后续 34 round：agent 查 `k8s.container.restarts` → 发现 ts-ticket-office-service 3 restart + ts-food-service 1 restart，并做 baseline 对比验证 ts-food-service restart 是 incident-only
- 干预 2（conclusion @ qpf=64）：**M8 primary + M5 secondary**
  - agent 响应：reconsider timeline → 发现 ts-ui-dashboard 503 在 08:26:57 比 ts-food-service log 第一个错（08:27:44）早 47s → 找到 ts-food-service 在那段时间根本没 trace（silent）
- 后续 10 round 验证

**承重分析**：**M7 是承重维度**——baseline 完全没碰运行时层（k8s.container.restarts 是从未查过的指标）。M7 打开了"runtime layer"这个新查询空间，agent 才发现 container restart。M8 supporting：让 agent 区分 ts-food-service 在 silent 时间段的两种成因（来不及记录 vs 没收到请求）。M5 secondary 在 mid 起到了"silent service 也是信号"的承重作用。

**Tag**: `[M7-helped, M5-supporting, M8-supporting]` · `wrong→correct`

---

## 6. Case 1394 · JVMChaos / JVMMemoryStress · `wrong→correct` · ultra_hard

**source**: `ts2-ts-seat-service-stress-b7h7m9` · **GT 根因**: `ts-seat-service` · **Theme**: T1 Silence-as-Health

**GT propagation**
- 故障注入：`ts-seat-service` JVM 压力 → CPU 飙到 4.86 (avg 1.0 vs normal 0.25 = 4x) → 拒绝连接
- 关键证据：ts-seat-service container.cpu.usage **avg 0.25→1.0 (400% 升)**, max 0.36→4.86 (13x)；ts-travel-service / ts-travel2-service 都在调 ts-seat-service 时收到 503 "Connection refused"
- 隐藏特征：ts-seat-service **0 ERROR logs**（CPU 100% 时太忙记不了 log）+ **0 trace errors**（拒连接前就死了）

**no-MW** (qpf=60, pred=`ts-travel-service, ts-travel2-service` ❌)
- 错误推理：
  > "ts-travel-service has 63 errors (most), ts-travel2-service 39 errors ... 503 Connection refused on outbound calls ... Root Cause: ts-travel-service / ts-travel2-service experiencing connection failures"
- 失败模式：T1 — GT 服务 silent，agent 把多个 victim 当 RC

**MW** (qpf=60, pred=`ts-seat-service` ✓)
- 干预 1（mid @ qpf=30）：**M7 primary + M5 secondary**
  - 后续 24 round：agent 查 ts-seat-service container.cpu.usage → **直接 nail 到 4.86 spike** → "ts-seat-service CPU spiked from 0.25 to 1.0 (400%)"
  - 同时 M5 secondary 提示了"silent != healthy"，让 agent 没被 ts-seat-service 的 0 ERROR 迷惑
- 干预 2（conclusion @ qpf=54）：**M8 primary + M2 secondary**
  - intervention 关键句："the CPU spike — is this pattern unique to incident window, or chronic?"
  - 后续 6 round：做 baseline 对比验证 normal CPU avg 0.25 vs abnormal avg 1.0 = incident-only

**承重分析**：**M7 是承重维度**——baseline 已经做了 trace 分析，知道 ts-seat-service 在 call chain 上，但把它当作"被调用的健康下游"。M7 让 agent 查 ts-seat-service 自己的 CPU → 直接发现 4x 飙升。M5 supporting（让 agent 不被 0 ERROR 误导），M2 supporting（chronic 验证）。

**Tag**: `[M7-helped, M5-supporting, M8-supporting, M2-supporting]` · `wrong→correct`

---

## 7. Case 2390 · JVMChaos / JVMMemoryStress · `wrong→correct` · stable

**source**: `ts3-ts-user-service-stress-7btwsk` · **GT 根因**: `ts-user-service` · **Theme**: T3 Noise-Anchor

**GT propagation**
- 故障注入：`ts-user-service` JVM 压力 → DB query latency 5ms→29ms (avg 6x), max 380ms→2380ms (6x)
- 关键证据：ts-user-service GET 端点 normal avg 5.2ms / abnormal 29ms；UserController.getUserByUserId normal max 36ms / abnormal max 2.36s；trace status 是 "Unset"（不报 error，但 latency 严重劣化）
- 隐藏特征：ts-rabbitmq DNS 错误 + RabbitMQ queue errors 是 chronic noise

**no-MW** (qpf=48, pred=`rabbitmq` ❌)
- 错误推理：
  > "UnknownHostException: ts-rabbitmq affecting ts-food-service, ts-delivery-service, ts-notification-service ... Root Cause: ts-rabbitmq DNS resolution failure ... ts-user-service appears healthy"
- 失败模式：T3 Noise-Anchor — chronic rabbitmq 报错最显眼

**MW** (qpf=66, pred=`ts-user-service` ✓)
- 干预 1（mid @ qpf=30）：**M6 primary + M5 secondary**
  - agent 响应（cache 中已附）："ts-user-service GET endpoint: avg 5.2ms→29ms, max 380ms→**2.38 seconds** ... massive latency increase from ~5ms to ~29ms"
  - 后续 26 round：完整 latency 对比 + 找出问题在 DB query 层
- 干预 2（conclusion @ qpf=56）：**M8 primary + M3 secondary**
  - M3 supporting（causal direction sanity check）

**承重分析**：**M6 是承重维度**——这个 case 的 GT 信号（latency 6x 升）只能通过 baseline 对比看到。agent 在 baseline 推理里都没做对比，因此被 chronic rabbitmq 锚定。M6 直接打开了 ts-user-service 的 latency 真相。M8 + M3 是 supporting（让 agent 在 commit 前过一遍因果链合理性）。

**Tag**: `[M6-helped, M5-supporting, M8-supporting, M3-supporting]` · `wrong→correct`

---

## 8. Case 2988 · JVMChaos / JVMCPUStress · `wrong→correct` · stable

**source**: `ts5-ts-basic-service-stress-zf2fd7` · **GT 根因**: `ts-basic-service` · **Theme**: T5 Query-Blindness

**GT propagation**
- 故障注入：`ts-basic-service` CPU 压力 → POST /basic/travel latency 37ms→74ms (100% 升), POST /basic/travels 33ms→57ms (73% 升)
- 关键证据：ts-basic-service 是 ts-travel-service / ts-travel2-service 的共同下游；它的 latency 翻倍传递到所有上游链路
- 干扰：chronic rabbitmq、chronic Order-already-exists、ts-route-service 单 trace 看 3.65s 但不是稳态

**no-MW** (qpf=55, pred=`ts-route-service` ❌)
- 错误推理：
  > "ts-route-service has slowest DB queries (RouteRepository.findByIds taking 3.65s) ... Root Cause: ts-route-service due to slow DB queries"
- 失败模式：T5 Query-Blindness — agent 看到单个 trace 的 3.65s 极值就锚定，没看 chronic vs incident-only

**MW** (qpf=71, pred=`ts-basic-service` ✓)
- 干预 1（mid @ qpf=30）：**M6 primary + M5 secondary**
  - agent 响应（cache 中已附完整对比）：发现 ts-rabbitmq errors / Order-already-exists 在 normal 也有 → 都是 chronic noise；filter 掉 noise 后 incident-only 信号在 ts-basic-service 的 latency 升 73-105%
- 干预 2（conclusion @ qpf=67）：**M8 primary**
  - agent 响应：counterfactual 验证 ts-basic-service 是上游汇聚点（ts-travel-service / ts-travel2-service 都调它）

**承重分析**：**M6 是承重维度**——这个 case 干扰极多（rabbitmq DNS、order-already-exists、单 trace 3.65s 极值），baseline 不做 chronic vs incident 对比就**完全分不出 noise vs signal**。M6 一发，agent 立即识别多类 chronic 噪声，焦点收回 ts-basic-service。

**Tag**: `[M6-helped, M5-supporting, M8-supporting]` · `wrong→correct`

---

## 9. Case 3059 · NetworkChaos / NetworkCorrupt · `wrong→correct` · stable

**source**: `ts5-ts-order-service-corrupt-bd4p5g` · **GT 根因**: `ts-order-service`, `ts-ui-dashboard` · **Theme**: T3 Noise-Anchor

**GT propagation**
- 故障注入：网络层 corrupt（partition 类）于 ts-order-service ↔ ts-ui-dashboard
- 关键证据：ts-ui-dashboard log 报 "dial tcp 10.102.32.107:8080: i/o timeout"（10.102.32.107 是 ts-order-service IP）；error trace 只有 2 个 span（loadgenerator + ts-ui-dashboard），下游被切断
- 干扰：chronic ts-rabbitmq、chronic ts-ticket-office-service 重启、JVM GC 多服务 >2s（chronic）

**no-MW** (qpf=46, pred=`ts-config-service` ❌)
- 错误推理：
  > "ts-seat-service → ts-config-service in trace shows 3.49s duration ... ts-config-service has JVM CPU load 419 ... GC pauses up to 3.5s ... Root Cause: ts-config-service JVM GC pressure"
- 失败模式：T3 Noise-Anchor — chronic JVM GC 在多服务上都有，agent 锚定其中一个

**MW** (qpf=54, pred=`ts-ui-dashboard` ✓ — partial GT match)
- 干预 1（mid @ qpf=30）：**M6 primary + M5 secondary**（中文版）
  - agent 自检 latency / restart 是否 chronic → 发现 ts-ticket-office-service restart 在 normal/abnormal 都有，是 chronic；ts-rabbitmq DNS 也是 chronic；GC pauses 多服务都有 chronic
  - filter 掉 noise 后 → 找到 ts-ui-dashboard "i/o timeout to 10.102.32.107:8080" 是 incident-only
- 干预 2：**advisor 在 conclusion 时返回 triggered=false**——因为 agent 已闭环
- 后续 24 round 走 compress

**承重分析**：**M6 是承重维度**——这个 case 的 chronic noise 极厚（多种 chronic GC + restart + DNS），M6 让 agent 系统性 filter 掉。注意：v4 advisor 在 conclusion 时**主动判断 agent 已经做对了不需介入**——这是 v4 自主判断机制起作用的证据。

**Tag**: `[M6-helped, M5-supporting, conclusion-skipped-by-advisor]` · `wrong→correct`

---

## 10. Case 3716 · JVMChaos / JVMMemoryStress · `wrong→correct` · ultra_hard

**source**: `ts0-ts-food-service-stress-xfwkgh` · **GT 根因**: `ts-food-service` · **Theme**: T3 Noise-Anchor

**GT propagation**
- 故障注入：`ts-food-service` JVM 内存压力 → 22 次 container restart（normal 时段 0 次）
- 关键证据：ts-food-service abnormal restart count 22 vs normal 0；memory 24%→81%→9%（restart 周期）；ts-ui-dashboard 503 traces 里 ts-food-service span 缺失
- 干扰：ts-rabbitmq DNS error / ts-ticket-office-service 24 次 chronic restart / "Order already exists" chronic

**no-MW** (qpf=49, pred=`ts-rabbitmq` ❌)
- 错误推理：典型 T3 — RabbitMQ DNS error 最响 → 锚定它
- 失败模式：T3 Noise-Anchor

**MW** (qpf=82, pred=`ts-food-service` ✓)
- 干预 1（mid @ qpf=30）：**M6 primary + M5 secondary**（中文版）
  - agent 响应：识别 rabbitmq error 在 normal 也有 → chronic noise；进一步对比 → ts-food-service abnormal 22 restart vs normal 0 restart = incident-only
- 干预 2（conclusion @ qpf=66）：**M8 primary**（中文版）
  - intervention 强调"重启不一定是原因，可能是结果（OOM/liveness probe/dependency 故障）"
  - agent 响应：查 ts-food-service memory → 81% spike → 推断 OOMKilled
  - 又查 counterfactual：trace 里 ts-ui-dashboard 503 的同时 ts-food-service status=Unset(200) → 一些 503 来自 dashboard 重试机制 → 验证 ts-food-service 失活窗口

**承重分析**：**M6 是承重维度**——chronic ts-rabbitmq 锚定是这个 case 的核心失败模式，M6 直接破解。M8 supporting（让 agent 区分 restart 是因还是果，避免错把 chronic restarts 当 RC）。

**Tag**: `[M6-helped, M5-supporting, M8-supporting]` · `wrong→correct`

---

## 11. Case 4032 · JVMChaos / JVMMemoryStress · `wrong→correct` · stable

**source**: `ts2-ts-auth-service-stress-lq54b9` · **GT 根因**: `ts-auth-service` · **Theme**: T1 Silence-as-Health

**GT propagation**
- 故障注入：`ts-auth-service` JVM 压力 → CPU 32% avg, **98% max** vs 其他服务都 < 3.5%
- 关键证据：login 端点 normal 95-104ms / abnormal 3500-3800ms；error trace 里 ts-auth-service span 缺失（被 ts-ui-dashboard 提前 timeout）；ts-auth-service log 完全无 ERROR
- 隐藏特征：ts-auth-service silent（log 0 ERROR + error trace 里 span 缺失），baseline 把 ts-ui-dashboard（有 ERROR）当 RC

**no-MW** (qpf=63, pred=`ts-ui-dashboard` ❌)
- 错误推理：
  > "ts-ui-dashboard returns 503 errors with ~3.5s timeout ... When errors occur, ts-ui-dashboard does NOT call ts-auth-service ... ts-auth-service is healthy (deployment.available=1.0, no ERROR logs)"
- 失败模式：T1 Silence-as-Health — 经典误判：把"无 ERROR + span 缺失"当作"健康"

**MW** (qpf=59, pred=`ts-auth-service` ✓)
- 干预 1（mid @ qpf=30）：**M1 primary + M5 secondary**
  - intervention：loudest 不一定是 origin，silent 不一定是 healthy
  - agent 响应（cache 中已附）："ts-ui-dashboard shows 503 errors but might be a VICTIM, not the root cause ... ts-ui-dashboard is failing BEFORE it can call ts-auth-service ... ts-auth-service is so slow/unresponsive that ts-ui-dashboard times out"
  - 后续 23 round：查 ts-auth-service CPU → **32% avg, 98% max** → 直接 nail 到 GT
- 干预 2（conclusion @ qpf=53）：**M8 primary**
  - agent 做 counterfactual 验证

**承重分析**：**M1 是承重维度**——这个 case 是经典 victim-vs-origin 案例。M1 prompt 里的"loudest 可能是 victim"和 M5 的"silent 不等于 healthy"恰好同时打在 baseline 的两个盲点上，agent 立即从 victim 推到 origin。**注意 M1 + M5 是组合承重**（缺一会失败：M1 单独让 agent 知道 ts-ui-dashboard 是 victim 但找不到方向；M5 单独让 agent 怀疑 silent service 但不知道是哪个）。

**Tag**: `[M1-helped, M5-helped, M8-supporting]` · `wrong→correct`

---

## 12. Case 4353 · JVMChaos / JVMMemoryStress · `wrong→correct` · ultra_hard

**source**: `ts3-ts-station-service-stress-4wtfqh` · **GT 根因**: `ts-station-service` · **Theme**: T2 Blame-the-Messenger

**GT propagation**
- 故障注入：`ts-station-service` JVM 压力 → memory 79% → OOM → `k8s.deployment.available` 从 1→0 持续 10s（01:58:06 → 01:58:16）
- 关键证据：ts-station-service deployment.available=0 是这个 case 唯一的"smoking gun"信号；ts-basic-service 在调它时收到 503 "Connection refused"（victim）
- 隐藏特征：GT 在 trace 里 silent（unavailable 期间根本不响应），仅在 metrics 层留下 deployment.available=0 信号

**no-MW** (qpf=54, pred=`ts-basic-service` ❌)
- 错误推理：
  > "ts-basic-service has 240 error spans, 503 'Connection refused' on GET calls to upstream ... earliest error 01:58:07 ... Root Cause: ts-basic-service"
- 失败模式：T2 Blame-the-Messenger — 把报 503 的 victim service 当 RC

**MW** (qpf=73, pred=`ts-station-service` ✓)
- 干预 1（mid @ qpf=30）：**M5 primary**（**唯一 case 是单维度 M5 主问，无 secondary**）
  - intervention 文非常精准："the thing it's trying to reach isn't showing up in your data at all. That absence isn't necessarily a sign of health"
  - 后续 33 round：agent 查每个 ts-basic-service 调用的下游 → 发现 ts-station-service `k8s.deployment.available=0.0` at 01:58:06 → nail GT
- 干预 2（conclusion @ qpf=63）：**M8 primary**
  - intervention 文（中文版）：候选服务的不可用窗口很短，是这类故障的典型模式还是另一更上游问题？
  - agent 响应：查 ts-station-service memory spike 79% → 推断 OOM 是直接原因

**承重分析**：**M5 是承重维度**——这个 case 的 GT 信号（deployment.available=0）只有"对 silent service 主动反查"才能找到。M5 intervention 直接告诉 agent"那个你尝试 reach 的 service 在数据里缺失，先检查它"——agent 立即回去查每个被调用的下游。M5 没有 secondary，但这反而让主问更聚焦——这是 v4 "1 主问 + 0~3 次问"机制的优秀实例。

**Tag**: `[M5-helped, M8-supporting]` · `wrong→correct`

---

## 综合判断（Task 1 conclusion）

**12 个翻盘里**：
- **11 个是 MW 真实承重**（M6×6, M7×3, M5×2, M1×1）—— 干预触发后 agent 的查询模式发生**结构性转向**，新查询揭示了 baseline 推理里完全缺失的关键证据（如 baseline 对比、运行时层、silent service 自查）
- **1 个 (case 572) 是 sampling 巧合** —— v4 advisor 完全没触发，agent 自己跑出对答案的 timeline 推理

**11 个 MW 承重 case 里没有任何"agent 没换查询、只是结论用词换了"的情况**（即没有 `[L1-sampling-perturbation]` tag），因此 22.6% 的翻盘率不是 sampling 噪声放大——这是真实的 MW 干预效果。

**M-code 承重次数（小计）**：

| 维度 | 承重次数 | 比例 |
|---|---:|---:|
| M6 (Baseline-Contrast) | 6 | 50% |
| M7 (Layer-Coverage) | 3 | 25% |
| M5 (Silence ≠ Health) | 2 | 17%（另有多次 supporting） |
| M1 (Loudness-Anchor) | 1 | 8% |
| M8 (Hypothesis-Counterfactual) | 0 | (但 supporting in 10/12) |
| M2/M3/M4/M9/M10 | 0 | — |

**M8 的角色**：M8 在 conclusion check 里 fired 47 次，但承重 0 次。它的作用更接近"安全网"——让 agent 把 mid-check 已经发现的东西巩固一遍。**对 wrong→correct 的因果链而言，关键转向都发生在 mid-check（M6/M7/M5/M1）**。

**M2/M3/M4/M9/M10 在 12 个 case 里完全未承重**——说明：
- M3/M4 在 thinkdepthai 上很难触发（图结构 / sibling 类问题在 qwen 输出里不显著）
- M9 (stagnation) 没救活任何 case（说明 thinkdepthai 卡住时 → 无解）
- M10 (premature-commitment) 在 mid-check 时机上太晚（agent 已经 commit 了候选）

**给 v4.1 的提示**（详见 final_summary.md）：
1. M6 + M7 + M5 是高效维度，应保留
2. M1 在 mid 时机表现强（case 4032），值得在 mid 池里更主动评估
3. M2/M3/M4/M10 在 thinkdepthai-qwen 上要么不触发要么不承重——可能需要更精确的 trigger 或考虑下放优先级
