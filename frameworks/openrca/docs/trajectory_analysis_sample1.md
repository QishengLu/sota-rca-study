# OpenRCA 轨迹分析 — Sample 1 (ts-auth-service JVMException)

## 基本信息

| 字段 | 值 |
|------|---|
| 样本 ID | 1 |
| 故障注入 | JVMException at `ts-auth-service::TokenServiceImpl.getServiceUrl` |
| 正确答案 | `ts-auth-service` |
| OpenRCA 预测 | `ts-ui-dashboard` ❌ |
| 耗时 | 612 秒 (~10 min) |
| 模型 | kimi-k2-0905-preview |
| 推理步骤 | 6 步代码执行 |

---

## 推理轨迹逐步分析

### Step 1 — 数据探索 & 时序初始化

**执行内容：**
- 加载 `env.json` 获取故障窗口时间戳
- 加载 `abnormal_metrics.parquet`，探索可用 metric-service 组合
- 查找 login/auth 相关 metric

**关键发现：**
- 故障窗口：2025-08-21 12:15:16 → 12:19:14（约4分钟，UTC+8）
- 共 228 个 metric-service 组合可用
- 认证流相关服务有完整监控：ts-auth-service, ts-user-service, ts-gateway-service, ts-security-service, ts-ui-dashboard

**问题：** 第一次汇总时误报了时间（2024-12-19），后续步骤自行纠正（说明执行结果与 LLM 解读存在 hallucination 风险）

---

### Step 2 — Metric 类型枚举

**执行内容：**
- 枚举所有 metric 名称，归类
- 确定可用于性能分析的关键 metric

**关键发现：**
```
HTTP 延迟 metric（4个）：
  hubble_http_request_duration_p50/p90/p95/p99_seconds

资源 metric（25个）：
  container.cpu.usage, container.memory.rss/usage/available/working_set
  jvm.cpu.recent_utilization, jvm.system.cpu.utilization/load_1m
  k8s.container.cpu_limit, container.memory.major_page_faults
```
- 故障窗口内 p50 约 1.65s, p90 约 2.67s（整体延迟偏高）

---

### Step 3 — 计算全局阈值（正确执行 OpenRCA 方法论）

**执行内容：**
- 遵循 OpenRCA 规则："先用全量数据算全局 P95/P99 阈值，再过滤故障时段做异常检测"
- 对每个 service × metric 组合计算 P95, P99, mean, std

**关键阈值发现：**
```
ts-auth-service  hubble_http_request_duration_p95_seconds  P95 = 0.005s
ts-auth-service  hubble_http_request_duration_p99_seconds  P99 = 0.005s
ts-gateway-service / ts-user-service / ts-security-service  P95 = 0.005s
```
- 正常情况下各认证服务 HTTP P95 极低（~5ms），说明正常状态响应非常快
- Container CPU P95 范围：0.5% ~ 5.3%

---

### Step 4 — 异常检测（接近正确但被低估）

**执行内容：**
- 将故障窗口内的 metric 值与全局 P95 阈值对比
- 找出超阈值的 service-metric 组合

**关键发现：**
```
ts-auth-service  hubble_http_request_duration_p95_seconds
  故障窗口值: 0.2488s  vs  全局P95阈值: 0.2486s  → 超阈值 1.0008×

ts-auth-service  hubble_http_request_duration_p90_seconds
  故障窗口值: 0.2373s  vs  全局P95阈值: 0.2370s  → 超阈值 1.0005×

ts-auth-service  hubble_http_request_duration_p50_seconds
  故障窗口值: 0.160s   vs  全局P95阈值: 0.157s   → 超阈值 1.016×
```

**Controller 的判断：** ts-auth-service 是 "primary candidate"，但超阈值幅度极小（1.0x）→ 认为"可疑但不显著"，决定继续用 trace 验证

> **⚠️ 关键偏差点 #1**：
> ts-auth-service 的 HTTP 延迟从 ~5ms（正常）暴增到 ~248ms（故障），**实际超阈值 50 倍**。
> 但由于全局阈值是用了包含故障期数据的完整 parquet 计算的（而非只用正常期），全局 P95 被"污染"抬高，
> 导致超阈值比率看起来只有 1.001×，完全掩盖了真实异常幅度。

---

### Step 5 — Trace 分析（推理错误的转折点）

**执行内容：**
- 加载 `abnormal_traces.parquet`，过滤 login 相关 trace
- 分析调用链结构和耗时

**发现的调用链：**
```
loadgenerator
  └─► ts-ui-dashboard  POST /api/v1/users/login   (入口)
        └─► ts-auth-service  POST /api/v1/users/login  (被调用)
```

- 27 条 login trace，24 条耗时 >1s
- 1 条 HTTP 500 响应
- 响应时间 30ms ~ 223ms 剧烈波动

**Controller 的判断：**
> "The most downstream service in the call chain is ts-ui-dashboard, which handles the final `/api/v1/users/login` endpoint."

> **⚠️ 关键错误 #2（推理逻辑错误）**：
> OpenRCA 的规则是"找调用链中最下游的 **有故障** 的服务"（faulty service）。
> 但这里 Controller 把"调用链中出现的最后一个服务"误解为"最下游"。
>
> 实际调用方向：ts-ui-dashboard **调用** ts-auth-service（ts-auth-service 是更下游的）
> 正确逻辑：ts-auth-service 出现 JVM 异常 → 请求失败 → ts-ui-dashboard 收到错误 → 产生 ERROR 日志
> 错误判断：把 ts-ui-dashboard 的错误日志当做"它是根因"

---

### Step 6 — Log 分析（错误路径被强化）

**执行内容：**
- 加载 `abnormal_logs.parquet`，只分析 ts-ui-dashboard 的日志

**发现：**
- 193 条日志，其中 125 条 ERROR（65%）
- 所有 ERROR 都是 login 相关
- 从故障窗口开始 4 秒内 (04:15:20) 就出现错误

**Controller 最终判断：**
> "ts-ui-dashboard is experiencing widespread operational failures → root cause = ts-ui-dashboard"

> **⚠️ 关键错误 #3（幸存者偏差）**：
> 只分析了 ts-ui-dashboard 的日志，没有去看 ts-auth-service 的日志（其中包含 JVM exception 栈）。
> ts-ui-dashboard 的大量 ERROR 是 **因** ts-auth-service 调用失败产生的**次级症状**，不是根因。

---

## 误判根本原因总结

```
根本原因链（实际）：
  [注入] JVMException at ts-auth-service::TokenServiceImpl
      │
      ▼
  ts-auth-service 处理 login 请求时抛异常 → HTTP 延迟暴增 (~5ms → ~248ms)
      │
      ▼
  ts-ui-dashboard 调用 ts-auth-service 超时/失败 → 返回 HTTP 500
      │
      ▼
  用户侧 SLO 违规（login endpoint 不可用）
```

OpenRCA 的推理失误在于：
1. **阈值污染**：全局 P95 阈值包含了故障期数据，掩盖了 ts-auth-service 延迟暴增的幅度
2. **trace 分析方向错误**：把调用链的"入口服务"误认为"最下游服务"
3. **log 选择性分析**：只看了 ts-ui-dashboard 的日志（错误的服务），漏掉了 ts-auth-service 的 JVM 栈

---

## 对 Prompt 改进的建议

| 问题 | 建议改进 |
|------|---------|
| 全局阈值被故障期污染 | 明确指示优先用 `normal_*.parquet` 计算基线阈值 |
| trace 调用方向理解错误 | 补充 prompt："ts-ui-dashboard → ts-auth-service 表示 ui-dashboard **调用** auth-service，auth-service 是被调用的下游服务" |
| 只看了错误服务的 log | 规则中加："metric 异常最显著的服务优先分析日志" |

---

## 与 thinkdepthai 的预期对比

thinkdepthai (kimi-k2) 在这条样本上正确预测了 `ts-auth-service`，说明：
- thinkdepthai 的 DuckDB 查询 + 因果图推理能更准确识别直接故障服务
- OpenRCA 的代码执行路径更透明可观察，但对"最下游有故障服务"的判断规则在异常幅度小时容易失效
