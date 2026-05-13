## Sonnet Case 371 · `ts0-ts-travel2-service-request-delay-lzpl9v` · HTTPChaos / HTTPRequestDelay

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 371 |
| GT 根因 | `ts-travel2-service` + `ts-seat-service` |
| sonnet pred | `ts-basic-service` (CONNECTION_RESET + HIGH_LATENCY) ❌ |
| sonnet rounds | 31 |
| qwen3.5 pred | `ts-travel2-service` (HIGH_ERROR_RATE + CONNECTION_RESET) ✓（44 round） |
| **共性错** | ❌ sonnet-specific failure（qwen3.5 corrected this case）|
| chaos type | HTTPChaos / HTTPRequestDelay (3512ms) |
| tier | stable（GT travel2 自身有强直接信号：唯一 Error spans + 端点 avg 50x 暴涨；sonnet 倒在 connection reset message provenance 误读 + host-level metric 误读）|

### 2. GT 注入

```
fault_type: 7 (HTTPChaos)
display_config:
  injection_point:
    app_name: ts-travel2-service       ← chaos 注入位置
    method: POST
    route: /api/v1/seatservice/seats/left_tickets   ← 拦截这个路径
    server_address: ts-seat-service    ← 调用目标
    server_port: 8080
  delay_duration: 3512 ms              ← 每个 outgoing request 加 3.5s 延迟
  duration: 4 min
ground_truth:
  service: [ts-travel2-service, ts-seat-service]
  pod:     [ts-travel2-service-..., ts-seat-service-...]
```

### 3. chaos 机制

**chaos 物理机制**：在 ts-travel2-service pod 内 sidecar/agent 拦截 outgoing HTTP request，匹配 `POST http://ts-seat-service:8080/api/v1/seatservice/seats/left_tickets`，给每个匹配的 request 加 3512ms 延迟才放出去。

**预期因果链**：
1. travel2 controller 调 seat 的 `seats/left_tickets` 端点时，HTTP client 在本地被拦截阻塞 3.5 秒
2. travel2 controller 等 HTTP client 返回 → controller 自身 latency 暴涨（每次 +3.5s，多次累加）
3. travel2 持有的资源（thread pool / DB connection）被锁住 3.5s 不释放
4. 上游业务流（route-plan / travel-plan / ui-dashboard）调 travel2 的端点超时
5. 部分请求超过 client side timeout → 上游主动关 connection → travel2 真正发 request 时遇到 `Connection reset`（caller 自己的 socket 已被对方关）
6. cascade 末端：所有 travel/travel-plan 业务流 SLO 违规

**关键因果区分**：travel2 SEVERE log 报 `Connection reset on POST to ts-basic-service / ts-seat-service` —— 这是 **travel2 自己作为 caller，在尝试发 outgoing request 时遇到 socket reset**，不是 basic / seat 主动拒绝连接。chaos 让 travel2 上游 timeout → 上游关 socket → travel2 后续 syscall 看到 reset。这跟 503 message provenance 误读是同款陷阱（caller 报告 outgoing 失败 ≠ callee 主动失败）。

### 4. 调用树（normal 期实测）

```
loadgenerator
  └─ ts-ui-dashboard
      ├─ ts-travel2-service                          ◀── GT (chaos 注入 pod)
      │   ├─ ts-seat-service (POST seats/left_tickets) ◀── GT (chaos route target)
      │   ├─ ts-basic-service
      │   └─ ts-route-service
      └─ ts-travel-plan-service
          └─ ts-route-plan-service
              └─ ts-travel2-service ─────────────┘
```

### 5. 关键 duckdb 证据

#### chaos 直接证据 1：travel2 端点级 distribution（sonnet 完全没看）

| service.span_name | n_count | a_count | n_avg ms | a_avg ms | avg_r | a_p99 ms |
|---|---|---|---|---|---|---|
| ts-travel2-service::POST | 1025 | 180 | 40.7 | **2139.5** | **52.6x** ⭐ | 3789 |
| ts-travel2-service::Travel2Controller.getTripAllDetailInfo | 63 | 8 | 138.7 | **7147.8** | **51.5x** ⭐ | 7222 |
| ts-travel2-service::POST /api/v1/travel2service/trip_detail | 63 | 8 | 140.3 | **7149.3** | **51.0x** ⭐ | 7224 |
| ts-travel2-service::Travel2Controller.queryInfo | 272 | 56 | 142.5 | **5873.6** | **41.2x** ⭐ | 14778 |
| ts-travel2-service::POST /api/v1/travel2service/trips/left | 272 | 56 | 144.5 | **5876.0** | **40.7x** ⭐ | 14780 |
| ts-travel2-service::TripRepository.findAll | 272 | 56 | 4.9 | 8.7 | **1.8x** ✓ | 114 |
| ts-travel2-service::Transaction.commit | 272 | 56 | 0.6 | 1.1 | **1.7x** ✓ | 12 |

**关键不对称指纹**：travel2 的 controller / endpoint 暴涨 41-53x，**但内部 SQL/Repository span 几乎正常**（1.7-1.8x）。这意味着 chaos 不在 DB 层，而在 controller → outgoing HTTP 调用层（吻合 HTTPRequestDelay 机制）。

#### chaos 直接证据 2：status_code 分布（qwen3.5 用了，sonnet 没用）

| service | Unset (success) | Error |
|---|---|---|
| **ts-travel2-service** | 766 | **15** ⭐ 唯一有 Error 的服务 |
| ts-basic-service (sonnet 锚定) | **1109** | **0** ❌ 完全没 Error |
| ts-seat-service | **1949** | **0** ❌ 完全没 Error |
| ts-route-plan-service | 216 | 0 |
| ts-travel-plan-service | 276 | 0 |

**这是排除 basic / seat 是 RC 的强反向证据**：errors **originate** from travel2，downstream 全部是 Unset (success)。如果 basic / seat 真的在拒绝连接 / 故障，它们自己也会有 Error spans。sonnet 锚定 basic 但 basic 0 Error，**完全没 chaos 直接信号**。

#### sonnet 锚定的 service 实情（ts-basic-service）

| 信号 | 实测 | sonnet 解读 | 因果归因偏离 |
|---|---|---|---|
| service avg 19.0 → 27.7 ms (1.46x) | 弱信号，p99 62 → 173 (2.8x) | "basic-service has high latency" | basic 自己几乎正常；下游 cascade 末端通常受影响小，basic 是 GT travel2 的下游 |
| status_code 分布 | **0 Error / 1109 Unset** | sonnet 没查这个维度 | **完全没 Error 直接反证 basic 不可能是 RC** |
| log SEVERE/ERROR | **0 行** in both periods | sonnet 没查 basic 自己的 log | basic 自身完全 silent，不是故障源 |
| jvm.system.cpu.load_1m | normal 7.3 → abnormal 86.13 (max 221) | "node 过载，basic 在 worker1 这就是 RC" | jvm.system.cpu.load_1m **是 host-level metric**（pod 看到的是宿主 1 分钟负载），同 worker 的所有 pod 数值完全相同（worker1 = 86.13；worker2 = 92.12），不能作 pod-specific 信号 |
| GC pause max | normal 1.206s → abnormal 1.898s | "1.898s GC pause 很长" | normal 已经 1.2s，差别 0.7s 不算显著（< 2x），sonnet 自己 R30 也承认 "差别不算大" 但仍坚持 |

#### 因果归因偏离 2：host-level metric 误读

实测 jvm.system.cpu.load_1m 按 worker 节点聚类完全相同：

| worker | services on this worker | jvm.system.cpu.load_1m avg | max |
|---|---|---|---|
| worker2 | ts-admin-basic-info / ts-admin-order / ts-route-service / ts-preserve-other / ts-wait-order / ts-preserve / ts-security | **92.12** (完全相同) | 235.42 |
| worker1 | ts-travel-plan / ts-train / ts-basic / ts-travel / ts-food | **86.13** (完全相同) | 221.13 |

**这是 host-level metric 的清晰证据**：jvm.system.cpu.load_1m 是 JVM 报告的宿主机 1 分钟负载（不是 pod-level），同 worker 上所有 pod 看到的都是同一个数。sonnet 在 R20 自己注意到 "ts-basic-service 和 ts-travel-plan-service 数值完全相同" 但解读为 "they might be running on the SAME Kubernetes node"（**对了一半**：是同 node，但**没意识到这意味着 metric 本身是 host-level 的，不能作 pod-specific 推断**）。R23 又自问 "为什么 worker1 pod CPU 都低，但 system load 86-221？" 然后归因到 "I/O wait"——但这个**自己提出的反证已经否定了"node 过载"假设**，sonnet 仍坚持。

#### 因果归因偏离 3：connection reset message provenance 误读

travel2 SEVERE log：
```
"Servlet.service() ... threw exception ... ResourceAccessException:
 I/O error on POST request for 'http://ts-basic-service:8080/api/v1/basicservice/basic/travels':
 Connection reset; nested exception is java.net.SocketException: Connection reset"
（4 行，类似的还有调 ts-seat-service 的 4 行）
```

sonnet R15 think_tool 直接解读为：`"ts-travel2-service is failing because ts-basic-service is resetting connections!"` —— 把 caller 报告的 "我调 X 时遇到 connection reset" 误读为 "X 主动 reset"。

实际语义：travel2 作为 HTTP client 在调 basic 时，**它自己的 socket 收到 RST**。可能原因：
- chaos 让 travel2 outgoing HTTP request 阻塞 3.5s → 上游 (ui-dashboard) timeout 关 connection → 反向触发 travel2 → ui-dashboard 的回包失败
- 上游 timeout 后下次 socket 复用时被 reset
- 或 OS 网络栈在长 idle 后回收 socket

**关键判据**：basic 自己 0 Error / 0 SEVERE log（如果 basic 真的主动 reset，basic 的 server-side log 会有对应 server-side close 事件）。这跟 case 1934 的 503 message provenance 误读是同款陷阱。

#### 因果链一致性表

| 因果链环节 | 物理机制预期 | 实测验证 | 一致 |
|---|---|---|---|
| travel2 outgoing HTTP request 被加 3.5s 延迟 | travel2 自身 controller 的 endpoint avg 暴涨 ~3.5s+ 倍数 | endpoint avg 41-53x（normal 140 ms → abnormal 5874-7148 ms）✅ |
| chaos 不在 DB 层 | travel2 内部 SQL/Repository span 几乎正常 | TripRepository 1.8x, Transaction.commit 1.7x ✅ |
| travel2 自身的 outgoing 失败 | travel2 自己作为 client 报 connection reset | 4 SEVERE 行 ✅ |
| GT 下游服务 (basic/seat) 自身正常 | 0 Error spans + 0 SEVERE log | 实测 0/0 ✅ |
| errors originate from travel2 | travel2 是唯一有 Error spans 的服务 | 15 Error vs 其他全 Unset ✅ |
| chaos 不动 CPU/内存 | travel2 / basic / seat 的 container.cpu / memory ratio ≈ 1 | 实测 ≈ 1.0x（CPU 反而下降，因为 chaos 让流量降到 17-25%）✅ |

### 6. sonnet 完整推理路径

sonnet 跑 31 round → `ts-basic-service` CONNECTION_RESET + HIGH_LATENCY ❌

| Round | 行为 | 关键决策 |
|---|---|---|
| R1-3 | schema 探索 | — |
| R4-5 | trace error 概览 | 发现 ts-travel2-service 5 错误 + 高 latency endpoints |
| R6 think (msg=10) | 注意到 travel2 1.92% error rate（最高）+ travel-plan/route-plan 高 latency | "travel2 是关键候选" |
| R7-8 | 看 travel2 error 详情 | 发现 trace chain travel2→basic 调用链有 inner POST Error |
| R9 think (msg=17) | 看到 ts-notification AmqpConnectException Connection refused | "RabbitMQ 可能宕了" — 短暂误锚 |
| R10-11 | 查 travel2 SEVERE log | 发现 4 行 "Connection reset on POST to ts-basic-service" + 4 行 "Connection reset on POST to ts-seat-service" |
| 🔴 **R11 think (msg=22) 锚定** | "travel2 is failing because ts-basic-service is resetting connections!" | **connection reset message provenance 误读** —— 把 caller 报告的 outgoing 失败误读为 callee 主动 reset |
| R12-13 | 加固：trace chain travel2 → basic_service POST 调用 | 看到 trip_detail 调 basic 3568ms |
| R14-15 (msg=32) | 看各 service container.cpu | 发现所有 service CPU 反而下降（"奇怪" 但归因为 "service restart"，没考虑 chaos 让流量降）|
| R16-17 (msg=37) | 查 jvm.system.cpu.load_1m | 发现 ts-basic-service avg 86.13 max 221 |
| 🟡 R17 think | **注意到 ts-basic-service 跟 ts-travel-plan-service 数值完全相同** | 解读为 "they might be running on the SAME Kubernetes node"（**对了一半**：是同 node，但**没意识到 metric 是 host-level**）|
| R18-19 (msg=42) | 加固：worker1 pod 列表 + mysql 也在 worker1 | "worker1 node 过载是 RC" |
| 🟡 R21 think (msg=47) | **自问 "all worker1 pods CPU 都低，但 system load 86-221，怎么解释？"** | 自己提出反证（**这其实是 host-level metric 的标志**），但归因到 "I/O wait" 而**没否定 "node 过载" 假设** |
| R22-25 | 查 worker map + 各 pod 资源 | 加固 worker1 是 hot node 假说 |
| R26-27 | 查 GC histogram | basic max GC 1.898s vs normal 1.206s（差距 < 2x，弱）|
| R28-29 | trace chain dump 看 minStation 端点 | 看到 travel2 → basic 3568ms 累积 |
| R30 think (msg=68) | "basic-service is the bottleneck" | 加固 basic = RC |
| 🔴 FINAL | `ts-basic-service` CONNECTION_RESET + HIGH_LATENCY ❌ |

**sonnet 关键缺失行为**：

整个 31 round 中，sonnet **从未**：
- 查 status_code 分布（会立刻看到 basic / seat 全 Unset，0 Error）
- 查 ts-basic-service 自己的 SEVERE/ERROR log（实测 0 行，根本没 connection reset）
- 查 travel2 端点级 distribution（会看到 controller 41-53x vs 内部 SQL 1.7-1.8x 的不对称）
- 在 R17 注意到 host-level metric 反常时**反向验证**这个 metric 维度是不是 host-level（虽然 R21 自问反证但没听自己的）
- 在 R11 锚定 basic 时**先验证 basic 自己有没有 Error / SEVERE 证据**

### 7. 跨模型快速结论

| 项 | sonnet | qwen3.5 |
|---|---|---|
| 最终 pred | `ts-basic-service` CONNECTION_RESET + HIGH_LATENCY ❌（31 round） | `ts-travel2-service` HIGH_ERROR_RATE + CONNECTION_RESET ✓（44 round） |
| 决策风格 fingerprint | 看 caller log "Connection reset to X" 直接锚 X → host-level metric 86-221 错当 pod 个体信号加固 → 自己提出反证不听自己 | 用 status_code 分布反向排除（downstream 全 Unset / 0 Error）→ 锚 errors origin |
| 共性 vs sonnet-specific | 全 sonnet-specific failure（qwen3.5 在同 case 同 parquet 同 prompt 答对）；sonnet 倒在 caller log 字面解读 + host-level metric 维度混淆 + status_code 反向排除维度缺失 | |

### 8. 失败模式（用失败池标签）

| 标签 | 本 case 具体表现 | qwen3.5 对应 |
|---|---|---|
| **A4** | sonnet R11 把 travel2 SEVERE log "Connection reset on POST to ts-basic-service" 直接当 "basic 主动 reset"，锚 basic，但 basic 自己 0 SEVERE / 0 ERROR / 0 Error spans —— caller 报 outgoing 失败 ≠ callee 主动失败（503 message provenance 同款） | qwen3.5 正确识别 SEVERE 在 travel2 自己 log 里 = travel2 自己 outgoing 失败 |
| **A6** | sonnet 用 jvm.system.cpu.load_1m basic 86.13 max 221 当"basic 所在 node 过载"证据，但同 worker 所有 pod 数值完全相同（worker1 全 86.13、worker2 全 92.12）—— 这是 host-level metric 标志，sonnet R17 自己注意到反常但归因为 "same node" 没意识到维度问题 | qwen3.5 全程不依赖此 metric |
| **A2** | sonnet R21 自问 "all worker1 pods CPU 都低但 system load 86-221，怎么解释？"——这已是 host-level 假设的反证（pod CPU 低 = node 过载假设破产），但归因到 "I/O wait" 后仍坚持 basic = RC 假设，反证未驱动回退 | nan |
| **B5** | sonnet 31 round 没跑 `(service_name, attr.status_code) GROUP BY` SQL；实测 basic = 1109 Unset / 0 Error，seat = 1949 Unset / 0 Error，**只有 travel2 有 15 Error spans** —— errors originate from travel2 是直接证据 | qwen3.5 R1 think 明确写 "ts-travel2-service is the ONLY service showing Error status (15 errors)，downstream basic/seat 全 Unset" → 直接锚 travel2 |
| **B2** | sonnet 没按 (service_name, span_name) 看 travel2 端点 distribution；实测 travel2 controller endpoint (queryInfo / getTripAllDetailInfo / 端点级 POST) avg 41-53x 暴涨，**内部 SQL/Repository/Transaction span 仅 1.7-1.8x** —— 这种不对称直接指向 chaos 在 controller→outgoing HTTP 层 | qwen3.5 也没显式跑端点 distribution，但 status_code + log 语义已够定位 |

### 9. 失败池（17 条）使用规则

```
本 case 命中标签：A2, A4, A6, B2, B5
最有效组合：B5 + A4 + A6（status_code 反向排除 → log 语义方向反查 → host-level metric 维度校核）
- B5（status_code 反向排除）：起点。强制跑 status_code 分布 SQL 立刻看到 basic / seat 全 0 Error，锚定 basic 的核心假设被直接反证。
- A4（log 语义方向反查）：中间步骤。如果 sonnet 仍被 caller log 吸引，强制查 X 自己的 SEVERE/ERROR/Error spans，全 0 → log 报告者才是 RC。
- A6（host-level metric 校核）：保险。同 worker 所有 pod 数值完全相同 = host-level metric，不能作 pod 个体推断。
```

失败池本身定义在 skill 头部"失败池（17 条标签库）"section，所有 case 共享。

### 10. 判断

- **数据是否完整**：✅（status_code 分布 + 端点 distribution + log 语义信息齐全，qwen3.5 用同样数据答对了证明数据足够）
- **chaos 是否生效**：✅ 完全生效（travel2 endpoint avg 41-53x 暴涨，内部 SQL 不动 = HTTPRequestDelay 在 controller→outgoing HTTP 层的标准指纹）
- **真假盲区分类**：**(b) 框架/模型盲区**——数据足够，qwen3.5 用同 parquet 同 prompt 在 44 round 内答对，sonnet 31 round 倒在通用方法缺失（status_code 反向排除 + log 语义方向解析 + metric 维度校核）
- **失败模式归纳**：A（log 语义方向误读）+ B（host-level metric 误读）+ C（status_code 反向排除维度缺失）+ D（端点 distribution 不对称未查）
- **共性 vs sonnet-specific**：**全部 sonnet-specific failure**——qwen3.5 在同 case 上答对，证明这些不是模型无关的盲点而是 sonnet 自己的弱点
- **给 sonnet 中间件设计的提示**：C + A + B 三条组合（详见 Section 9）—— 反向排除 + 错误信息方向 + metric 维度校核 三条通用方法 sonnet 全缺，可单独建中间件维度

### 11. causal_graph 正确性检验

GT root_cause: `service|ts-travel2-service` (state: unknown)。
注：causal_graph **完全没标 injection_affected span**（spans 全空）—— GT 标注极简，只在 service-level 标 travel2 是 RC。

| 节点 | declared state | 实测 | 一致 |
|---|---|---|---|
| `service\|ts-travel2-service` | `[unknown]` | HTTPRequestDelay chaos 注入点（chaos 在 travel2 pod 内拦截 outgoing） | — (unknown 是占位) |
| 其他 spans | causal_graph 没标 | 实测 travel2 的 controller endpoint (queryInfo / getTripAllDetailInfo / POST trip_detail) avg 41-53x 暴涨，内部 SQL 1.7-1.8x | causal_graph 应该标 injection_affected on travel2 controller endpoints，但实际 0 个 affected span，**这是 causal_graph 标注稀疏问题**（不影响 service-level GT 正确性） |

causal_graph service-level GT (travel2) 跟实测 chaos 物理机制（HTTPRequestDelay on travel2→seat）一致。**case 371 适合用于 failure mode 归纳**。注：causal_graph 缺失 injection_affected span 标注，但这是数据集标注稀疏问题，不影响 sonnet 失败模式归纳——sonnet 错的不是因为标注稀疏，而是没用通用 SQL 反向排除 + log 语义方向解析。

case 371 sonnet 完毕。
