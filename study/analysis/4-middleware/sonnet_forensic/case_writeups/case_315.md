## Sonnet Case 315 · `ts0-ts-travel-plan-service-response-delay-pfwcqk` · HTTPResponseDelay

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 315 |
| GT 根因 | `ts-travel-plan-service`, `ts-train-service` |
| sonnet pred | `ts-order-service` ❌ |
| sonnet rounds | 23 |
| qwen3.5 pred | `ts-route-plan-service` ❌ |
| **共性错** | ✅ 在 53 case 列表 |
| chaos type | HTTPResponseDelay (fault_type=8) |
| tier | ultra_hard |

### 2. GT 注入

```
fault_type: 8 = HTTPResponseDelay
display_config:
  delay_duration: 605 ms
  duration: 4 min
  injection_point:
    app_name: ts-travel-plan-service   ← chaos 注入在 caller 侧
    method: GET
    route: /api/v1/trainservice/trains/byName/*
    server_address: ts-train-service   ← 被 delay 的 response 来自 ts-train-service
    server_port: 8080
ground_truth:
  service: [ts-travel-plan-service, ts-train-service]
```

### 3. chaos 机制

HTTPResponseDelay 在 **ts-travel-plan-service 进程内（caller-side sidecar）**拦截其对 `ts-train-service:8080/api/v1/trainservice/trains/byName/*` 的 GET 响应，注入 605ms 人工延迟。chaos 在 **response 返回到 caller 侧时**才生效：
- ts-train-service 本身处理完全正常（server-side span 不感知 delay）
- delay 体现在 ts-travel-plan-service 的 outbound CLIENT span 里（caller wallclock = server span + 605ms）

ts-travel-plan-service 的三类 plan 端点（quickest/cheapest/minStation）各需多次调用 ts-train-service GET `/byName/*`，每次延迟 605ms。正常时单端点 500ms，注入后膨胀到 1600-2000ms。积压最终引发 cascade：ts-travel-plan-service → ts-seat-service → ts-order-service 全链积压，ts-order-service JVM 在 17:41:07 进入 90s GC pause（CPU 飙至 17.8 cores，随后跌至 ~0）。

### 4. 调用树（normal 期实测）

```
loadgenerator
  └─ ts-ui-dashboard
      └─ ts-travel-plan-service          ◀── RC (chaos injected, caller-side)
          ├─ ts-train-service (409 calls) ◀── RC (response delayed 605ms)
          ├─ ts-seat-service (818 calls)
          │   └─ ts-order-service
          └─ ts-route-plan-service (191 calls)
```

### 5. 关键 duckdb 证据

#### chaos 直接证据（B7 关键双面指纹）

| 维度 | 端点 / span | normal | abnormal | ratio |
|---|---|---|---|---|
| ts-travel-plan-service `GET` client span avg | outbound GET to ts-train-service | 6.4ms | **615.2ms** | **96x** |
| ts-travel-plan-service `GET` client span p50 | 同上 | 6.3ms | 613.5ms | 97x |
| ts-travel-plan-service `GET` client span p95 | 同上 | 8.1ms | 616.7ms | 76x |
| ts-train-service `GET /byName/{name}` server avg | byName 端点 server-side | 3.8ms | **3.7ms** | **1.0x** |
| ts-train-service `GET /byName/{name}` server p95 | 同上 | 5.2ms | 5.0ms | 1.0x |

**结论**：caller-side 96x + callee-side 1.0x → 经典 HTTPResponseDelay caller-side 注入双面指纹（delay 在 caller 进程内插入，server 完全不感知）。

#### ts-travel-plan-service 三端点 distribution

| 端点 | normal avg | abnormal avg | ratio |
|---|---|---|---|
| quickest | 476.7ms | 1662.8ms | 3.5x |
| cheapest | 508.8ms | 1853.2ms | 3.6x |
| minStation | 557.9ms | 1966.7ms | 3.5x |

service-level avg 仅 3.7x（被大量其他 span 稀释），B2 端点级 drill 才显现 GET client span 96x。

#### 误锚 service (ts-order-service) 实情

| metric | normal avg / p50 / p95 | abnormal avg / p50 / p95 | chaos 可解释性 |
|---|---|---|---|
| container.cpu.usage | 0.176 / 0.18 / 0.289 cores | 1.526 / **0.073** / 13.462 / max 17.781 cores | ❌ HTTPResponseDelay 不直接引起 CPU spike |
| jvm.system.cpu.load_1m | 5.38 | 6.64 (1.23x) | - |
| k8s.container.restarts | NULL | NULL | 无重启 |
| hubble_http_request_duration_p95 | 11.3ms | **NaN** (abnormal 期全 NaN) | ts-order-service 在 GC pause 期间停止接收 HTTP |

**注**：ts-order-service CPU spike 时间线为 17:41:07 飙至 17.781 → 17:41:17 → 17:41:22 开始回落（5.442）→ 17:41:37 跌至 0.001（90s GC pause）→ 17:42:42 恢复至 0.13。这是积压请求→连接池耗尽→JVM GC 压力→CPU spike 的级联二阶副作用，不是 chaos 注入点。

### 6. sonnet 完整推理路径

sonnet 跑 23 round → `ts-order-service` ❌

| Round | 行为 | 关键决策 |
|---|---|---|
| R1-R2 | list_tables + get_schema | 标准发现 |
| R3 | think | 制定调查计划，以 traces 为主 |
| R4 | service-level error rate + log level 扫描 | ts-travel-plan-service 2 errors (0.24%) - 被 dismiss 为"低错误率" |
| R5 | think | 仅注意 ts-seat-service/ts-travel-service 少量 ERROR；未 drill ts-travel-plan-service |
| R6 | 长 span 查询 (>5s) + ERROR/WARN logs | ts-order-service POST /refresh 90s；ts-travel-plan-service SEVERE "Connection reset to ts-route-plan-service" |
| R7 | think | 注意到 ts-travel-plan-service SEVERE log 指向 ts-route-plan-service；同时 ts-seat-service 504→ts-order-service 60s；**未 drill ts-travel-plan-service 端点分布** |
| R8-R11 | ts-seat-service → ts-order-service 调用链深挖 | 沿 cascade 链往下走，逐步聚焦 ts-order-service |
| R12-R13 | ts-assurance-service（healthy），ts-route-plan-service metrics | 注意到 ts-route-plan-service minStopStations 9.4s |
| R14-R15 | ts-route-plan-service trace + ts-order-service pod 查询 | **R15 think**：怀疑 ts-route-plan-service 和 ts-order-service |
| 🔴 R17 锚定 | think | "**ts-order-service CPU SPIKE: 17.781 EXTREME (53-250x normal!)**" → 立刻锁定 ts-order-service |
| R18-R19 | 验证 CPU：normal 0.06-0.33 → abnormal 17.78 | 确认 CPU 240x 数值 |
| R20-R21 | JVM GC metrics + CPU 时间线 | G1 Young GC 90.664s；CPU 时间线 0.073→17.781→0.001；**判断 GC stop-the-world** |
| R22-R23 | ts-order-service ERROR logs → HikariPool starvation | "Thread starvation or clock leap detected (delta=1m42s)" → **"definitive smoking gun"** |

**sonnet 失败点**：
1. ts-travel-plan-service 仅看 service-level avg（3.7x），未 drill 端点级分布（GET client span 96x 始终未发现）
2. 全程未查 ts-train-service（chaos 的直接对象）
3. ts-order-service CPU 17.78 cores（3 个时间点峰值）被当作因果起点而非 cascade 终点
4. HikariPool starvation log 被字面解读为"GC=RC 证据"，未追溯"为何 GC 压力来自哪里"

### 7. 跨模型快速结论（一行一项）

| 项 | sonnet | qwen3.5 |
|---|---|---|
| 最终 pred | `ts-order-service` ❌ | `ts-route-plan-service` ❌ |
| 决策风格 fingerprint | 沿 cascade 链追到最下游的极端 metric outlier（CPU 240x + GC 90s），用 log 字面语义确认 | service-level latency outlier 驱动（ts-route-plan-service minStopStations 9.4s highest abs） |
| 共性 vs sonnet-specific | **共性盲区**：两者都未做 ts-travel-plan-service 端点级 drill（B2）和 ts-train-service 双面 span 对比（B7）；**sonnet-specific**：sonnet 更深追 cascade 链至 ts-order-service，锚定极端 metric outlier（A3）后被 A11 log 语义确认巩固 | |

### 8. 失败模式

| 标签 | 本 case 具体表现 | qwen3.5 对应 |
|---|---|---|
| **A3** | sonnet 锚 ts-order-service CPU spike：3 个时间点 17.781 cores（avg 8.69x，但 p50=0.073 正常，p95=13.5x）；chaos 物理机制是 ts-travel-plan-service 接收 ts-train-service 响应时 caller-side 延迟 605ms，不能直接引起 ts-order-service CPU 飙升；sonnet 未问"此 spike 在 chaos 因果链哪一环" | qwen3.5 未锚 ts-order-service，转而锚 ts-route-plan-service latency outlier（9.4s），同样是 cascade victim，不同锚点 |
| **A11** | sonnet 把 HikariPool "Thread starvation... delta=1m42s" + G1 GC 90s 当 RC 确认"smoking gun"；实为 cascade 积压（ts-seat-service 60s 阻塞 → ts-order-service 连接池耗尽 → GC 压力 → CPU spike）的二阶副作用；"资源池 starvation = 资源故障起点"是错误因果归因，真因果链方向反了 | qwen3.5 未查 ts-order-service JVM metric，不涉及 A11 |
| **B2** | ts-travel-plan-service 端点级 distribution 未跑：`GET` client span normal avg 6.4ms → abnormal 615.2ms（96x，p50=613ms）直接是 chaos 指纹，被 service-level avg 3.7x wash out；sonnet 只看了 service-level avg 和 >5s 长 span 过滤（GET span 615ms 未触发此阈值） | qwen3.5 同样未做 ts-travel-plan-service 端点级 drill（共性盲区） |
| **B7** | caller-callee 双面 span 对比全程未做：ts-travel-plan-service GET client 615ms vs ts-train-service GET /byName/{name} server 3.7ms（166x 不对称）是 HTTPResponseDelay caller-side 注入的决定性双面指纹；sonnet 全程未查 ts-train-service 任何 span | qwen3.5 同样未查 ts-train-service（共性盲区） |

### 9. 失败池使用规则

```
本 case 命中标签：A3, A11, B2, B7

最有效组合：B2 + B7
  - B2（ts-travel-plan-service 端点级 drill）→ 发现 GET client span 96x
  - B7（双面 span 对比）→ ts-train-service server span 1.0x，确认 caller-side 注入
  - 两步合并即完整复原 HTTPResponseDelay caller-side 指纹
  
辅助：A3（要求 metric outlier 反查 chaos 因果链）→ ts-order-service CPU spike 不在 chaos 因果链上，dismiss
      A11（资源池 starvation ≠ 故障起点，需逆向追溯）
```

### 10. 判断

- **数据是否完整**：✅ ts-travel-plan-service 端点级 + ts-train-service server span 信号清晰，双面指纹完整
- **chaos 是否生效**：✅ ts-travel-plan-service GET client span 96x（615ms vs 6.4ms normal）直接可见
- **真假盲区分类**：(b) 框架/模型盲区——数据完整，但 sonnet 和 qwen3.5 都未做 B2/B7 这两步查询，始终停在 service-level avg 层次
- **失败模式归纳**：B2 + B7（端点级和双面 span 查询缺失 → 无法发现 caller-side 96x 指纹）+ A3 + A11（cascade 末端极端 metric + log 字面语义组合锚定误导）
- **共性 vs sonnet-specific**：B2 + B7 是两模型共性盲区；A3 + A11 是 sonnet-specific（sonnet 更深追 cascade 链，最终被 ts-order-service GC 极端信号锁死）
- **给 sonnet 中间件设计的提示**：B2 + B7 联动（当 service-level avg 中等但 travel-plan 类服务慢时，强制做端点级 drill + caller-callee 双面 span 对比）；A3 辅助（extreme metric outlier 触发时，自动反问"chaos 物理机制能否解释此 outlier"，ts-order-service CPU spike 在 HTTPResponseDelay 因果链上不可达）

### 11. causal_graph 正确性检验

GT causal_graph root_cause = ts-travel-plan-service（state: "unknown"）。注意：causal_graph 未收录 ts-train-service 为 root_cause 节点，但 ground_truth.service 列表包含 ts-train-service。

逐节点验证：
- `ts-travel-plan-service` spans（quickest/cheapest/minStation）state: high_avg_latency + high_p99_latency → 实测 3.5x avg ✅（service-level avg；端点级 3.5x，GET span 96x，但图 node 是 service-level）
- `ts-travel-plan-service::BasicErrorController.error` state: high_error_rate → 实测有 2 行 SEVERE log（Connection reset）✅
- ts-ui-dashboard travelplan 端点 state: high_avg_latency + high_p99_latency → 实测 loadgenerator→ts-ui-dashboard ratio 2.8x avg ✅
- `ts-ui-dashboard::POST /api/v1/orderservice/order/refresh` state: timeout → ts-order-service 有 90s timeout span ✅
- `ts-ui-dashboard::POST /api/v1/travelservice/trips/left` state: timeout → ts-travel-service ratio 6.1x ✅

causal_graph 节点核对基本通过，但 causal_graph 未完整表达"ts-train-service 是 chaos 直接注入对象"——root_cause 只列 ts-travel-plan-service（接收延迟的一侧），GT evaluation 把 ts-train-service 也列为 service，但 causal_graph 无 ts-train-service 节点。这是 eval GT 设计层面的注释，不影响失败模式归纳。

case 315 sonnet 完毕。
