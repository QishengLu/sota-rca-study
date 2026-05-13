## Sonnet Case 471 · `ts1-ts-assurance-service-container-kill-qw48fm` · ContainerKill

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 471 |
| GT 根因 | `ts-assurance-service` |
| sonnet pred | `None` ❌（提取为 None，judged=False；最终 response 指向 MySQL） |
| sonnet rounds | 32（tool_call rounds） |
| qwen3.5 pred | `None` ✓（judged=True） |
| **共性错** | ❌ sonnet-specific failure（不在 53 case 列表） |
| chaos type | ContainerKill (fault_type=2) |
| tier | stable |

### 2. GT 注入

```
fault_type: 2 = ContainerKill
display_config:
  injection_point:
    app_label:       ts-assurance-service
    container_name:  ts-assurance-service
    pod_name:        ts-assurance-service-79876db68f-7vpcj
  namespace: ts
  duration: 4

ground_truth:
  service:   [ts-assurance-service]
  container: [ts-assurance-service]
  pod:       [ts-assurance-service-79876db68f-7vpcj]
```

### 3. chaos 机制

ContainerKill 向 ts-assurance-service 容器发送 kill -9 信号，容器进程瞬间终止。进程死亡导致所有持有的 TCP 连接（包括到 MySQL 的若干活跃连接）被操作系统以 TCP RST 方式关闭。MySQL 服务端观察到来自 IP 10.0.5.85（即 ts-assurance-service pod）的连接异常断开，记录 "Aborted connection… Got an error reading communication packets"——这是 **MySQL 服务端报告 client-side 进程死亡的日志**，不是 MySQL 自身故障。

K8s 检测到容器进程退出后拉起重启，k8s.container.restarts 从 0 升到 1。重启期间（约 1 分钟）ts-assurance-service 无法接收请求：trace count 降至正常期 47%（ratio_count=0.47），现有请求的平均延迟升至正常期 7.1 倍，CPU 在 JVM 重启预热阶段飙升（avg 16.65x，cpu_limit_utilization max=0.87）。hubble p95 在重启期间变为 NaN（cilium 无可用端点，网络层无数据）。

下游传播：ts-ui-dashboard 的 assurance 接口出现 20 条 503 Error（avg 3544ms）；ts-preserve-service 在调用 ts-assurance-service 时因连接中断产生 "Order already exist" 类重试错误。

### 4. 调用树（normal 期实测）

```
loadgenerator
  └─ ts-ui-dashboard
      ├─ GET /api/v1/assuranceservice/assurances/types
      │   └─ ts-assurance-service                   ◀── GT (ContainerKill target)
      │       └─ MySQL (内部 DB 调用)
      └─ POST /api/v1/preserveservice/preserve
          └─ ts-preserve-service
              └─ ts-assurance-service               ◀── 同一 GT
```

### 5. 关键 duckdb 证据

#### chaos 直接证据（GT 服务 ts-assurance-service）

| 指标 | normal | abnormal | ratio | 说明 |
|---|---|---|---|---|
| trace count | 764 | 356 | 0.47× | 重启期间接收请求降半 |
| avg duration (ms) | 3.3 | 23.2 | **7.1×** | 最高 ratio_avg，全局第一 |
| Transaction.commit avg (ms) | 1.4 | 85.4 | **59.7×** | 重启恢复期 DB 事务延迟 |
| k8s.container.restarts | 0 | **1** | — | ⭐ ContainerKill 直接指纹 |
| container.cpu.usage avg | 0.032 | 0.53 | **16.65×** | JVM 重启预热飙升 |
| cpu_limit_utilization max | 0.029 | **0.87** | — | 最高接近饱和 |
| hubble_p95_seconds | 0.016s | **NaN** | — | 重启期无 cilium 数据 |

#### MySQL "Aborted connection" 实情

| | 值 |
|---|---|
| normal 期 MySQL 异常日志 | 0 条 |
| abnormal 期 MySQL "Aborted connection" | **10 条**，同一时刻 (05:59:50.200xxx)，同一 host IP 10.0.5.85 |
| 含义 | MySQL **服务端**记录 client（ts-assurance-service pod at 10.0.5.85）在连接被 kill 后 TCP 连接异常断开；不是 MySQL 自身通信故障 |
| 因果方向 | ContainerKill(ts-assurance-service) → 进程死亡 → TCP RST → MySQL log（downstream 结果）|

#### ts-ui-dashboard 503 错误（downstream 受害者）

| span_name | status | http_code | cnt | avg_ms |
|---|---|---|---|---|
| GET /assuranceservice/assurances/types | Error | 503 | 20 | 3544.5 |
| GET /assuranceservice/assurances/types | Unset | 200 | 93 | 89.1 |

### 6. sonnet 完整推理路径

sonnet 跑 32 round → 最终 response 归因 MySQL database disruption ❌

| Round | 行为 | 关键决策 |
|---|---|---|
| R1–R3 | list_tables + get_schema + think | 规划：assurance 和 preserve 两条 SLO 路径 |
| R4–R8 | 查 abnormal_traces + normal_traces 端点 | 发现 ts-ui-dashboard 20 条 503，ts-preserve-service 高延迟 |
| R9–R11 | think + normal baseline 对比 | 发现 ts-travel-service avg 2105ms (suspect), ts-seat-service 高 |
| R12–R13 | 查 ts-assurance-service + 全局 log level | assurance 无 ERROR，其他服务有 ERROR |
| R14–R17 | 查 preserve/food/delivery/order/order-other WARN/ERROR | "Order already exist" 是重试，ts-seat "No content" |
| R18–R19 | 查 metric list + hubble_drop_total + **k8s.container.restarts** | **发现 ts-assurance-service restart=1** ⭐ |
| 🟡 R20 | think | "**EXCELLENT!** ts-assurance-service pod restarted (max=1) explains 503 errors" → 但接着注意到"pod already recovered (k8s.container.ready=1)" |
| R21–R22 | 查 assurance pod 详细 metric 时序 | 看到某采样点 cpu_limit_utilization=0.04 → "CPU is normal (0.04)"；结论"pod restarted but **CPU usage is normal, already recovered**" |
| R23–R24 | 查 JVM GC histogram | GC max 5.7ms，排除 GC 原因 |
| R25–R26 | 查 hubble p95/p99 | 全部 NaN → 认为 hubble 无用 |
| R27 | 查 MySQL 日志 + DB connection wait | 看到 MySQL 10 条 "Aborted connection from 10.0.5.85" |
| 🔴 R28 | think | "**CRITICAL FINDING!** MySQL simultaneously aborted 10+ connections at exactly 05:59:50…This is a MySQL disruption event" → **完全锚定 MySQL 为根因** |
| R29–R30 | 查 normal DB wait 对比 | ts-assurance DB wait 44% 增加（477ms→690ms），认为"confirms MySQL disruption cascaded" |
| R31–R32 | 查 error timeline + network errors | 构建因果链："MySQL drops → preserve errors → assurance restart → 503s" |
| **FINAL** | response | "Root Cause: **MySQL database disruption** at 05:59:50… invalidated all services' DB connection pools" |

**sonnet 失败点**：
1. R20–22：发现 restart=1 强证据，但用"恢复后单点 CPU 0.04 = already recovered"否定了它的根因地位，强证据未 sticky
2. R28：MySQL "Got an error reading communication packets" 被字面解读为 MySQL 自身通信故障（"MySQL disruption"），而非 MySQL 服务端记录 client-side 进程死亡后的连接断开
3. R32：构建**倒置因果链**（MySQL drops → assurance restart），实际方向相反（ContainerKill → 进程死亡 → 连接 RST → MySQL log）

### 7. 跨模型快速结论（一行一项）

| 项 | sonnet | qwen3.5 |
|---|---|---|
| 最终 pred | `None`（MySQL disruption）❌ | `None`（正确）✓ |
| 决策风格 fingerprint | 找到直接 kill 指纹（restart=1）后被下游日志噪声吸引，构建倒置因果链锚定 MySQL | nan |
| 共性 vs sonnet-specific | sonnet-specific（qwen3.5 答对）| |

### 8. 失败模式（用失败池标签）

| 标签 | 本 case 具体表现 | qwen3.5 对应 |
|---|---|---|
| **A11** | MySQL "Got an error reading communication packets" 是 MySQL 服务端记录 client-side 连接异常断开（ts-assurance-service pod kill-9 后 TCP RST，10.0.5.85→MySQL，0 条 normal 期 chronic）；sonnet 将其字面读为 MySQL 自身通信故障，称 "MySQL disruption event"，以此作为根因 | nan |
| **A2** | Round 20 已发现 restart=1（⭐ ContainerKill 一次性 latch 指纹），Round 22 用恢复后单点采样 cpu_limit_utilization=0.04 得出"already recovered"，restart 证据未被 sticky；Round 28 MySQL 假说完全覆盖了原有强证据，最终 response 丢弃了 restart=1 | nan |

### 9. 失败池使用规则

```
本 case 命中标签：A11, A2
最有效组合：A11 + A2（log 字面语义反向归因 + 强证据 sticky 缺失）
```

A11 处理方式：MySQL "Got an error reading communication packets" 是 MySQL 服务端报告 client-side 断开，不是 MySQL 自身故障。中间件维度：候选 "MySQL 故障" 时，必须先查 MySQL 日志中中断连接来自哪个 host IP，再比对该 IP 对应的 pod 是否有 restart counter 异常或 container kill 信号；若 host IP 对应的 pod 有 restart=1，则该日志是 kill downstream log，MySQL 不是 RC。

A2 处理方式：restart=1 是一次性 latch（kill 发生后 counter 永远 ≥1，无法"恢复归零"），应作为 sticky 强证据不可被后续"pod already recovered"采样点否定。中间件维度：发现 restart counter ≥1 后，立即标记为"kill fingerprint confirmed"，后续任何 "CPU normal / memory normal / pod ready" 单点证据不得用于否定 restart 事实。

### 10. 判断

- **数据是否完整**：✅ k8s.container.restarts、CPU ratio、hubble NaN、MySQL 日志全部可查
- **chaos 是否生效**：✅ restart=1 明确，CPU 16.65x，hubble NaN，trace count 降至 47%
- **真假盲区分类**：**(b) 框架/模型盲区** — 数据有充分信号（restart=1 全局唯一且 SQL 1 ratio_avg 第一），sonnet 在 R20 已找到正确答案，但被 MySQL downstream log 的语义反向解读带偏
- **失败模式归纳**：A11（MySQL 服务端 log 字面语义反向归因 → 倒置因果链）+ A2（restart=1 强证据被恢复期单点采样否定，未 sticky，后被 MySQL 假说覆盖）
- **共性 vs sonnet-specific**：sonnet-specific（qwen3.5 正确）——qwen3.5 在类似 ContainerKill case 中能识别 restart=1 为直接根因；sonnet 在本 case 中"找到了但放弃了"
- **给 sonnet 中间件设计的提示**：A11 + A2 两条组合——(1) MySQL 服务端 "Aborted connection" log 反查 host IP → 匹配 pod restart 进行 kill attribution，(2) restart counter ≥1 标记为 sticky kill fingerprint，后续 CPU/memory/ready 恢复采样不得否定 restart 事实

### 11. causal_graph 正确性检验

关键节点核对：

| 节点 | graph state | 实测 | 核对 |
|---|---|---|---|
| container\|ts-assurance-service | high_cpu | avg ratio 16.65x，max 0.87 cpu_limit | ✅ |
| pod\|ts-assurance-service-f648b466d-fjlvz | high_cpu, high_memory, high_http_latency | CPU 16.65x ✅；memory page_faults 1.79x（轻微偏高）；high_http_latency 通过 trace avg 7.1x 体现 ✅ | ✅ |
| span\|ts-assurance-service 各 endpoint | high_avg_latency, missing_span, injection_affected | Transaction.commit ratio 59.7x，endpoint cnt_ratio 0.27（非 types 端点大幅减少）✅ | ✅ |
| span\|ts-ui-dashboard::GET /assurances/types | high_error_rate | 20/113=17.7% Error (503) ✅ | ✅ |
| span\|loadgenerator | timeout | 4 spans with 20s timeout ✅ | ✅ |

causal_graph 节点核对通过，high_gc_pressure 在 pod 节点标注但 GC max=5.7ms（minor 级别），可能是图模型多时刻合并产物，不影响 service-level GT 判断。

case 471 sonnet 完毕。
