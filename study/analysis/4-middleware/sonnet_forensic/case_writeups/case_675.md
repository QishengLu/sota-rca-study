## Sonnet Case 675 · `ts1-ts-route-plan-service-request-replace-method-bn6rxm` · HTTPRequestReplaceMethod

### 1. 基本信息

| 字段 | 值 |
|---|---|
| dataset_index | 675 |
| GT 根因 | `ts-route-plan-service`, `ts-route-service` |
| sonnet pred | `ts-travel-service`, `ts-travel2-service` ❌ |
| sonnet rounds | 113（trajectory dump 显示 45 effective rounds） |
| qwen3.5 pred | `ts-route-plan-service` ✓（命中 GT 一半，漏 ts-route-service） |
| 共性错 | ❌ sonnet-specific (qwen3.5 corrected) |
| chaos type | HTTPRequestReplaceMethod (fault_type=12) |
| tier | stable |

### 2. GT 注入

```
fault_type: 12 = HTTPRequestReplaceMethod
display_config:
  injection_point:
    app_name: ts-route-plan-service        ◀── chaos 注入到此（client side）
    method: GET
    route: /api/v1/routeservice/routes/*
    server_address: ts-route-service       ◀── 被改 method 调用的目标 server
    server_port: 8080
  replace_method: OPTIONS                   ◀── GET 被改成 OPTIONS
  duration: 4
ground_truth:
  service: [ts-route-plan-service, ts-route-service]
```

### 3. chaos 机制

HTTPRequestReplaceMethod 在 ts-route-plan-service client 端拦截 `GET /api/v1/routeservice/routes/*` 请求，把 HTTP method 从 GET 替换为 **OPTIONS**。物理上：

- ts-route-service server 收到 OPTIONS 请求（不是 GET），按 Spring Boot CORS preflight 处理 → 返回**空 body** 或 **502 Bad Gateway**
- ts-route-plan-service 期待 GET response 的 JSON body 解析后处理 → 拿到 null body → **NullPointerException**
- caller 自身的 retry 逻辑触发 → minStopStations 端点反复重试 → 1040 NPE 累积

**关键 fingerprint**：
1. caller 端 1040 NPE（chaos 直接表征：null body 解析失败）
2. caller 端 2 个 502 Bad Gateway（chaos 偶尔返回的 server response 实际状态码）
3. caller 端 2 个 connection reset to travel/travel2（**偶发噪声**，跟 chaos 无关）
4. server 端（ts-route-service）trace 上完全看不到 OPTIONS 调用（trace SDK 通常只记 GET/POST 端点）→ ts-route-service 端点级 ratio 都 ≈ 1.0x
5. caller→server edge: route-plan → route-service 调用 count **140→1040 (7.43x retry)** 是 chaos 直接最强证据

GT 同时标 ts-route-plan-service（caller，retry burden 受害者 + 1040 NPE）+ ts-route-service（server，被改 method 的目标）。

### 4. 调用树（normal 期实测）

```
loadgenerator
  └─ ts-ui-dashboard (POST /travelplanservice/travelPlan/{minStation,cheapest,quickest})
      └─ ts-travel-plan-service
          └─ ts-route-plan-service ◀── GT (chaos 注入 client side)
              ├─ ts-route-service (GET /routes/*)            ◀── GT (chaos target server_address)
              ├─ ts-travel-service (POST /trips/left)        ◀── 旁观者 (sonnet 误锚)
              └─ ts-travel2-service (POST /trips/left)       ◀── 旁观者 (sonnet 误锚)
```

### 5. 关键 duckdb 证据

#### chaos 直接证据（service-level trace ratio）

| service | normal_n | abnormal_n | ratio_count | n_avg(ms) | a_avg(ms) | ratio_avg |
|---|---|---|---|---|---|---|
| ts-station-food-service | 824 | 252 | 0.31 | 4.7 | 65.8 | **14.1x** |
| ts-travel-plan-service | 1263 | 555 | 0.44 | 301.9 | 1701.1 | 5.6x |
| ts-ui-dashboard | 4407 | 1592 | 0.36 | 88.0 | 274.6 | 3.1x |
| ts-travel-service (sonnet 误锚) | 4694 | 1359 | 0.29 | 54.4 | 106.3 | 2.0x |
| ts-travel2-service (sonnet 误锚) | 3246 | 823 | 0.25 | 53.9 | 100.2 | 1.9x |
| **ts-route-service** (GT) | — | — | — | — | — | **不在前 18** ⭐ |
| **ts-route-plan-service** (GT) | — | — | — | — | — | **不在前 18** ⭐ |

**关键**：service-level ratio_avg 排序中 GT 双服务都不显眼。HTTPRequestReplaceMethod 的指纹分散在端点级 / edge ratio / log dedup，不是 service-level avg。

#### caller-callee edge ratio（决定性证据）

| caller | callee | normal_n | abnormal_n | ratio | 含义 |
|---|---|---|---|---|---|
| **ts-route-plan-service** | **ts-route-service** | 140 | **1040** | **7.429** ⭐⭐⭐ | retry burden — chaos 直接证据 |
| ts-route-plan-service | ts-route-plan-service (self) | 827 | 3298 | 3.988 | retry burden self |
| ts-route-plan-service | ts-travel-service | 297 | 69 | **0.232** | route-plan 调 travel 减少（cheapestRoute 失败次数变少） |
| ts-route-plan-service | ts-travel2-service | 258 | 65 | **0.252** | 同上 |

**chaos 物理直接证据**：注入边 `route-plan→route-service` 调用量从 140 涨到 1040 (7.43x)，因为 chaos 改 GET→OPTIONS 后 server 返回空响应，client NPE，retry minStopStations 端点 26.6x。同时 route-plan 调 travel/travel2 反而减少（cheapestRoute 整体业务失败导致下游业务调用减少）。

#### 端点级 (caller, callee.span_name) drill

| caller | callee.span_name | normal | abnormal | 含义 |
|---|---|---|---|---|
| ts-route-plan-service | ts-route-service `GET /api/v1/routeservice/routes` | 338 | 122 | server 看不到 OPTIONS（method 被改后绕过 GET 路由） |
| ts-route-plan-service | ts-route-service (any) | 140 | 1040 | retry 把整体调用 7.4x 放大 |

ts-route-service server 端 GET 端点 count 反而下降是因为 chaos 注入的 GET 请求都被改成 OPTIONS，没出现在 server 的 `GET /routes` span 里。这是 HTTPRequestReplaceMethod 的特殊指纹（跟 HTTPRequestAbort 不同）。

#### CPU 对比（GT vs 误锚 service）

| service | metric | n_avg | a_avg | a/n ratio | 解读 |
|---|---|---|---|---|---|
| **ts-route-plan-service** (GT-caller) | container.cpu.usage | 0.099 | **0.291** | **2.94x** ⭐ | retry burden 飙升 |
| **ts-route-plan-service** | jvm.cpu.recent_utilization | 0.0007 | 0.0026 | **3.71x** ⭐ | retry burden |
| **ts-route-service** (GT-server) | container.cpu.usage | 0.156 | **0.110** | **0.71x** ⭐ 反向下降 | OPTIONS 不算业务，server 处理量减少 |
| **ts-route-service** | jvm.cpu.recent_utilization | 0.0014 | 0.0011 | **0.79x** 反向下降 | 同上 |
| ts-travel-service (sonnet 误锚) | container.cpu.usage | 0.187 | **0.104** | **0.56x** 反向下降 | 完全反向 |
| ts-travel-service | jvm.cpu.recent_utilization | 0.0017 | 0.0011 | 0.65x 反向下降 | 同上 |
| ts-travel2-service (sonnet 误锚) | container.cpu.usage | 0.179 | **0.091** | **0.51x** 反向下降 | 完全反向 |

**关键**：sonnet 锚的 ts-travel/ts-travel2 在 abnormal 期 container.cpu.usage avg 反向下降到 0.51-0.56x（**远低于 normal**）—— 这是 chaos 没打到这两个服务的反向证据。但 sonnet 看到 max 1.156 / 0.99 当判据。

#### SEVERE log dedup by exception type（chaos provenance）

```
ts-route-plan-service SEVERE log dedup:
  NullPointerException:    1040    ⭐⭐⭐ chaos 直接表征（chaos 改 method → null body → NPE）
  502 Bad Gateway:            2    ⭐ chaos 偶发返回的 server response 状态码
  Connection reset:           2    （噪声 — 1 to travel + 1 to travel2，CPU spike 偶发 socket 失败）
```

**关键陷阱**：
1. 1040 NPE 的 message 内容 **不包含具体 service 名**（只写"NullPointerException with root cause"）
2. 2 个 connection reset 的 message 明写 `to ts-travel-service` / `to ts-travel2-service`
3. sonnet 的注意力被"频次小但归属信息明确"的 connection reset 吸走，而忽略了"频次大但归属信息缺失"的 NPE
4. 实际上 NPE 1040 才是 chaos 直接 fingerprint（chaos 改 method 后 null body 触发），connection reset 2 个是偶发噪声

#### chronic check

```
NullPointerException: normal 0 → abnormal 1040  （完全 incident-only）
502 Bad Gateway:      normal 0 → abnormal 2
Connection reset:     normal 0 → abnormal 2
```

#### route-plan-service 端点级 distribution（retry 指纹）

| span_name | n_count | a_count | n_avg | a_avg | ratio |
|---|---|---|---|---|---|
| RoutePlanController.getCheapestRoutes | 44 | 14 | 645.5 | 1513.8 | 2.35x |
| `POST /routePlan/cheapestRoute` | 44 | 14 | 647.7 | 1515.8 | 2.34x |
| `POST /routePlan/quickestRoute` | 49 | 22 | 605.6 | 899.6 | 1.49x |
| **`POST /routePlan/minStopStations`** | 39 | **1040** (26.6x) | 615.2 | **24.8** | **0.04x** |
| **RoutePlanController.getMinStopStations** | 39 | **1040** (26.6x) | 613.0 | **17.5** | **0.03x** |

minStopStations 端点 count 26.6x 增多 + avg latency 0.04x（fast-fail）= **典型 retry mode 指纹**：每次调用立即 NPE 失败 → caller retry → count 暴增。这是 HTTPRequestReplaceMethod / HTTPRequestAbort 类 chaos 在 caller 端的标准指纹。

#### restart counter

```
（无显著 restart；chaos 不杀容器）
```

### 6. sonnet 完整推理路径

sonnet 跑 45 effective round → `[ts-travel-service, ts-travel2-service] CONNECTION_RESET` ❌

| Round | 行为 | 关键决策 |
|---|---|---|
| R1-R5 | schema discovery + error span scan | 发现 ts-route-plan-service `POST /minStopStations` 1040/1040 errors HTTP 500 |
| R6-R10 | trace 链路追踪 | 发现 loadgenerator → ts-ui-dashboard → travel-plan → route-plan 调用链 |
| R11-R15 | route-plan SEVERE log | 看到 SEVERE log 含 "Connection reset to ts-travel-service" / "to ts-travel2-service" + NullPointerException |
| 🔴 R16 锚定瞬间 | think | "Connection reset when trying to POST to ts-travel-service and ts-travel2-service ... NullPointerException because travel didn't respond → travel/travel2 是 RC" |
| R17-R25 | 验证 ts-travel/ts-travel2 | 查 travel/travel2 ERROR log → **0 个**（反向证据 #1）；查 status_code → 全 Unset（反向证据 #2） |
| R26-R32 | metric 对比 | **R32 反思**："ts-travel-service abnormal CPU avg = 0.104 vs normal 0.187 — **actually LOWER**"（反向证据 #3 自己说的） |
| 🟡 R33 反向证据 dismiss | think | 但马上转 max："**However max is higher (1.156)** ... travel-service has CPU spike causing connection reset" — **用 max-only 合理化反向 avg** |
| R34-R40 | 加固 anchor | 查 GC pause、pod restart、hubble drops 反复合理化 ts-travel/ts-travel2，pod 没重启也无 GC 异常 |
| R41-R44 | 最终验证 | 查 caller distribution: ts-route-plan 调 travel 35 次成功 + 1040 错误 → sonnet 解为"35 successful + 1040 errors confirms travel under stress" |
| R45 FINAL | output | `[ts-travel-service, ts-travel2-service] CONNECTION_RESET` ❌ |

**sonnet 失败点**（去重独立化，每条独立可观测）：
1. **caller log "to X" 字面解读为 X = RC**（R16 think 原话："Connection reset when trying to POST to ts-travel-service and ts-travel2-service ... travel/travel2 are root cause"；caller 异常字符串里出现的下游服务名直接当 RC）
2. **NPE → "X 没响应" 因果链编造**（R16 "NullPointerException because when the travel didn't respond"；NPE 1040 实际是 chaos 改 method 后 server 返回空 body 直接产生的，不是 connection reset 间接导致；sonnet 把两件无关现象编成"travel 没响应 → NPE"因果链，加固对 travel 的锚定）
3. **反向 metric 信号被 max-only fallacy 覆盖**（R32 自己反思 "travel CPU avg 0.56x 反向下降"，R33 立即用 max 1.156 合理化为"travel has CPU spike causing reset"；正确解读是 avg 反向下降 = travel 调用减少 = travel 不是 RC）
4. **callee 没 ERROR log 不当反向排除证据**（R26 看到 "ts-travel/travel2 NO ERROR log only INFO"；正常应当反向证据排除候选，但 sonnet 用"server 不知道自己拒绝了 connection reset"合理化保留 anchor）
5. **没查 caller 自身 specific metric**（route-plan container.cpu.usage 2.94x、jvm.cpu.recent_utilization 3.7x — caller retry burden 是 chaos client-side 直接最强证据；sonnet 全程没对 route-plan 做 specific metric drill）
6. **没做 caller-callee edge ratio drill**（route-plan → 各下游 edge ratio 升序+降序双扫能立即看到 route-plan→route-service 140→1040 (7.43x retry)；sonnet 没跑 SQL 2 全表）
7. **anchor 锁死后过度 rationalize**（R16 锚 travel/travel2 后剩 30 round 反复用 GC histogram / pod restart / hubble drops 加固；R32 自己看到反向证据但 R33 立即转用 max 不回退；跨 case 4423/2011/675 重复出现的 sonnet fingerprint）

### 7. 跨模型快速结论

| 项 | sonnet | qwen3.5 |
|---|---|---|
| 最终 pred | `[ts-travel-service, ts-travel2-service] CONNECTION_RESET` ❌ | `ts-route-plan-service` HIGH_ERROR_RATE ✓（命中 GT 一半，漏 ts-route-service） |
| 决策风格 fingerprint | SEVERE log "Connection reset to X" 字面解读 → 把 X 当 RC + 编造 "NPE because X didn't respond" 因果链 → 反向 metric (avg 0.56x) 用 max-only 合理化 → callee 没 ERROR log 反向证据被"server 不报错"合理化掉 → anchor 锁死 | trace span `attr_status_code='Error'` 维度排序 → 锚 caller 自身（caller span 自身报错）→ 用"travel/travel2 没 ERROR log + status_code=Unset"反向排除 |
| 共性 vs sonnet-specific | **sonnet 特有为主**：caller log 字面解读 + max-only fallacy + 反向证据 dismiss + anchor 锁死后过度 rationalize（与 case 4423/2011 重复出现的 sonnet fingerprint 累积）。**两 model 共性**：没查 caller 自身 specific metric、没做 caller-callee edge ratio drill |

### 8. 失败模式（按失败池标签）

| 标签 | sonnet 本 case 表现 | qwen3.5 对应 |
|---|---|---|
| **A1** | R16 锚 travel/travel2 后 30 round 反复用 GC histogram / pod restart / hubble drops 加固，R32 看到反向证据 R33 立即转用 max 不回退 | qwen3.5 65 round 收敛快，没死撑 |
| **A3** | R32 看到 ts-travel CPU avg 0.56x 反向下降（distribution 全降），R33 立即用 max 1.156 合理化为 'travel has CPU spike' | nan |
| **A4** | R16 think 原话 'Connection reset when trying to POST to ts-travel-service ... travel/travel2 are root cause'——caller log 字面提及的下游服务名直接当 RC + NPE → 'X 没响应'编造因果链 | qwen3.5 用 attr_status_code='Error' trace 维度而非 log 字面 |
| **A9** | ts-travel/travel2 5 维度跟 RC 假设矛盾（NO ERROR log + status_code 全 Unset + trace count -76% + CPU avg 反向降 + 不在 chaos 边上），sonnet 仍锚 | qwen3.5 用 callee log+status 反向排除 ✓ |
| **B1** | (ts-route-plan, ts-route-service) edge 140→1040 retry burden 7.43x（最直接 chaos client-side 证据），没跑 | qwen3.5 同样没跑 |
| **B3** | ts-route-plan-service container.cpu 2.94x + jvm.cpu 3.7x（caller retry burden 标志），没用显式 list 查 | qwen3.5 间接靠 trace error 命中 |

**fingerprint**：sonnet = log 字面解读 'Connection reset to ts-X' 当 X=RC + max-only 反向 metric 合理化 + anchor 锁死 rationalize；qwen3.5 走 trace error 路径命中 GT 一半。**sonnet-specific 为主**。

### 9. 命中标签清单 + 最有效组合

**命中**：A1, A3, A4, A9, B1, B3

**最有效组合**：**A4 + A9 + B3**——A4 阻止 sonnet 把 caller log 字面提及的 callee 当 RC；A9 多维度反证排除 callee（NO ERROR + status Unset 是 victim 反证）；B3 specific metric 显式查 caller 自身 cpu 2.94x retry burden 直接证据。

### 10. 判断

- **数据是否完整**：✅ trace/log/metric 都有，HTTPRequestReplaceMethod 双 GT 指纹完整可见（caller CPU 2.94x、callee CPU 0.71x 反向下降、edge ratio 7.43x retry、NPE 1040 incident-only）
- **chaos 是否生效**：✅ 完全生效（route-plan→route-service 调用从 140 涨到 1040，1040 NPE 全 incident-only，loadgenerator cascade 整链 ratio 3.1x）
- **真假盲区分类**：**(b) 模型盲区**（数据信号充足，sonnet 自己被"caller log 字面字符串提及 victim 服务"+反向 metric dismiss + max-only fallacy 三连陷阱误导）
- **失败模式归纳**：connection reset message provenance 误读 + 反向证据 dismiss + max-only fallacy + 服务名相似性陷阱 + anchor 锁死后 rationalize（跨 case 4423/2011 + 1140 重复 sonnet fingerprint 累积）
- **共性 vs sonnet-specific**：**sonnet-specific failure**（qwen3.5 用 trace error 维度绕开了陷阱）；其中"connection reset message provenance 误读" + "anchor 锁死后 rationalize" 是 sonnet 跨多 case 重复 fingerprint
- **给 advisor 的提示**：
  1. caller SEVERE log 里 "Connection reset to X" 的 X 是 victim 不是 RC
  2. SEVERE log 必按 by-exception-type 频次密度优先于归属信息密度
  3. 候选服务 abnormal avg < normal 必须当反向证据采纳，不能用 max 合理化
  4. chaos `server_address` 字段必当 GT 候选首选
  5. caller-callee edge ratio drill 必查（retry burden 边 ratio > 5x）

### 11. causal_graph 正确性检验

causal_graph 节点核对：
- `service|ts-route-plan-service` state=["unknown"] → root_cause（GT 给定）✅
- `span|ts-route-plan-service::POST /minStopStations` state=["high_error_rate", "unknown"] → 实测 1040/1040 errors (100%) ✅
- `span|ts-travel-plan-service::TravelPlanController.getByMinStation` state=["high_avg_latency", "high_p99_latency"] → 实测 service avg 5.6x ✅
- `span|ts-travel-plan-service::POST /travelplanservice/travelPlan/minStation` state=["high_error_rate", "high_avg_latency", "high_p99_latency"] → 实测 a_avg 1701ms ratio 5.6x + 部分 trace 错误 ✅
- `span|ts-ui-dashboard::POST /travelplanservice/travelPlan/minStation` state=["timeout", "high_avg_latency", "high_p99_latency"] → 实测 a_avg 274ms ratio 3.1x + 部分 trace 20s timeout ✅

⚠️ **注意**：causal_graph 节点不包含 ts-route-service（GT 双服务之二）。chaos `server_address` 信息只在 injection.json 里有，causal_graph 没补全 server 端节点。这跟 case 2011 的 ts-travel2-service 缺失同病。**causal_graph 节点核对 service-level 主链通过**，但拓扑覆盖度对 HTTPRequestReplaceMethod 双 GT 类不完整（server 端节点缺失）。该 case 不计入 causal_graph 错标。

case 675 sonnet 完毕。
