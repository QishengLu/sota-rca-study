# 元认知中间件实际例子对（周报 PPT 素材）

两个典型 case：一个**中期检查**（thinkdepthai-qwen, round=30），一个**结论前检查**（aiq-qwen, reflect 第二次循环后）。

核心要点：**触发条件不是硬规则 IF/ELSE，而是 claude-opus-4-7 读 trajectory 行为和意图信号后自主判断出来的**。两例分别展示 opus-4.7 从**两种不同信号源**触发：① 从 intent 统计模式；② 从 reasoning 文本 + draft 图结构。

---

## §1 触发机制：opus-4.7 怎么选问题

### 1.1 两层管线（v4）

```
┌─────────────────────────────────────────────────────────────────┐
│  L1 快筛（runtime, 纯代码）                                       │
│  - 每条 agent SQL 由 opus-4.6 自动打 intent 标签（19 类之一）     │
│  - Python 层维护 per-case 状态对象：intent_log, round, draft_RC  │
│  - 到达 check_point 时（中期 round=30 / 结论前 pre-finalize）组包 │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  L2+L3 合并（claude-opus-4-7，单次 LLM 调用，无状态）             │
│  输入:                                                            │
│    A. 10 张维度卡（M1..M10）的定义 + trigger abstract             │
│    B. 本 case 的 trajectory snapshot:                             │
│       - 意图序列（最近 K 轮）  - 近期 reasoning 文本摘要          │
│       - draft root_causes + 其他 nodes 的 state 标记              │
│       - 最近一次 ranking SQL 的 top-K 行                          │
│    C. CaseInterventionState（跨检查点状态；中期已问过什么）       │
│                                                                   │
│  opus-4.7 自主判断（无 match_score 阈值）：                        │
│    1. 哪些维度卡 triggered=true                                   │
│    2. 最关键的一个作 primary（主问）                              │
│    3. 其他真命中的 0~3 个作 secondary（次问）                     │
│    4. 按原则 4 写中文反问式干预文本                               │
│                                                                   │
│  输出 JSON:                                                       │
│    {                                                              │
│      "triggered": true,                                           │
│      "primary": "M1",                                             │
│      "secondary": ["M6"],                                         │
│      "intervention_text": "..."                                   │
│    }                                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 opus-4.7 决策的 3 个信号来源

| 信号来源 | opus-4.7 要读什么 | 对应维度卡 |
|---|---|---|
| **A. Intent 统计模式** | "最近 8 轮连续做 `error_rate_scan` / `latency_ranking` 这种 ranking 类 intent，但 `baseline_contrast` 计数 = 0" | M1 / M6 / M7 / M2 |
| **B. Reasoning 文本特征** | agent think_tool 里的 commitment 语言（"看来是 X"、"confirming Y"、"it's clearly Z"）、hypothesis 漂移模式 | M5 / M8 / A3 / A5 |
| **C. Draft 输出 + 图结构** | draft 的 root_causes 列表 vs 其他 nodes 的 state 标记（比如某 node 被 agent 自己标 UNAVAILABLE 但没列入 RC）| M3 / A5 / A4 |

**两个例子分别示范其中两类**：例 ① 主靠 A（intent 统计），例 ② 主靠 B + C（reasoning + draft 图）。

### 1.3 跨检查点连续性

```
Python 维护的 CaseInterventionState（在例 ② 会用到）:
  mid_check_primary: "M6"               ← 中期主问过 M6
  mid_check_secondary: ["M2"]
  mid_check_intervention_text: "..."
  mid_check_agent_response_snippet: "..."

结论前检查时，opus-4.7 看到这个状态 → 避免重复同维度作主问（原则 5：同维度全程最多 1 次主问）；
                                    → 可以引用中期问过但 agent 没响应的部分作追问素材。
```

---

## §2 例 ① — 中期检查：**thinkdepthai-qwen, case_247**

**信号来源**：主靠 **A（intent 统计模式）**——opus-4.7 读 intent 分布不均就触发。

### 2.1 场景
- Framework: thinkdepthai-qwen3.5-plus（ReAct + reflection）
- **dataset_index: 247**
- **datapack: `ts0-ts-route-service-stress-kstvv2`**（source_data_dir: `/home/nn/SOTA-agents/RCAgentEval/data/ts0-ts-route-service-stress-kstvv2/converted`）
- Fault: JVMChaos/JVMMemoryStress 注入在 `ts-route-service.RouteController.queryById()`
- GT RC: `ts-route-service`（pod OOM-kill 重启，自己的 span 几乎消失，但上游 `ts-ui-dashboard` 因连锁报 +15 新 HTTP error）
- Check point: round=30（thinkdepthai-qwen 的 P25 中期窗口）

### 2.2 opus-4.7 在这一刻看到的 trajectory snapshot

```json
{
  "round": 30,
  "draft_root_causes": ["ts-ui-dashboard"],   // 候选已出，但还没 finalize
  "intent_log_last_8_rounds": [
    {"round": 23, "intent": "error_rate_scan"},
    {"round": 24, "intent": "latency_ranking"},
    {"round": 25, "intent": "service_trace_scan", "target_service": "ts-ui-dashboard"},
    {"round": 26, "intent": "keyword_search", "keyword": "error"},
    {"round": 27, "intent": "service_error_log", "target_service": "ts-ui-dashboard"},
    {"round": 28, "intent": "error_rate_scan"},
    {"round": 29, "intent": "service_trace_scan", "target_service": "ts-ui-dashboard"},
    {"round": 30, "intent": "service_error_log", "target_service": "ts-ui-dashboard"}
  ],
  "intent_counts_full_trajectory": {
    "error_rate_scan":     4,
    "latency_ranking":     2,
    "service_trace_scan":  6,
    "service_error_log":   5,
    "keyword_search":      3,
    "jvm_state":           0,           // ← 0 次
    "container_resource":  0,           // ← 0 次
    "k8s_state":           0,           // ← 0 次
    "baseline_collect":    0,           // ← 0 次
    "baseline_contrast":   0            // ← 0 次
  },
  "last_ranking_query_top_3": [
    ["ts-ui-dashboard",  15],
    ["ts-food-service",   9],
    ["ts-notification",   4]
  ],
  "recent_reasoning_snippet": "ts-ui-dashboard has the highest error count (+15 in abnormal window). Tracing its error pattern, it looks like a user-facing issue. Let me confirm this is the root cause."
}
```

### 2.3 opus-4.7 的"观察+判断"（这就是**触发条件**）

opus-4.7 的 system prompt 收到上面 snapshot 后，按 M1..M10 逐卡 checklist 评估。它的内部推理大致是：

```
内部 reasoning（不向 agent 透露）:

观察 1: intent_counts 显示 ranking 类 (error_rate_scan 4 + latency_ranking 2 = 6 次)，
        占总 intent 的比例很高。agent 整个调查都在"谁错最多/谁最慢"框架里。
观察 2: draft_RC = 'ts-ui-dashboard' 正好是 last_ranking_query 的 top-1 行。
观察 3: jvm_state + container_resource + k8s_state = 0 次——fault 层运行时指标
        完全没碰。agent 没有验证过"这个 top-1 服务自己是否真有故障特征"。
观察 4: baseline_collect + baseline_contrast = 0 次——没做 normal vs abnormal 对比。
观察 5: reasoning 文本用 "highest error count" 作为判据，有即将 commit 的 closure 语。

判断:
  - M1 LoudnessAnchorSelfcheck 强命中（观察 1+2+3 完整吻合 M1 trigger abstract）
  - M6 BaselineContrastReflex 也命中（观察 4），但不是最关键——
    这 case 如果只缺 baseline 但做了 metric probe，agent 可能就不会错；
    真正的 pathology 是 ranking 没被挑战。
  - M7 LayerCoverageReflex 也命中（观察 3），但和 M1 在该 case 机制高度重叠，
    列入次问避免主问泛化。
  - M2/M3/M4/M5/M8/M9/M10 都没看到触发信号。

决定:
  primary = M1，secondary = [M6, M7]
```

### 2.4 opus-4.7 的 JSON 输出

```json
{
  "triggered": true,
  "primary": "M1",
  "secondary": ["M6", "M7"],
  "intervention_text": "（见 §2.5）",
  "opus_reasoning_digest": "Ranking-heavy intents (6/30) + draft_RC matches last ranking top-1 + zero fault-layer metric probes on the candidate + closure language detected"
}
```

### 2.5 干预文本发给 agent

> 💡 **在你 commit 之前，想请你先反思几个问题：**
>
> **主问（M1）**：你现在要定的这个候选，是 ranking 查询里排名最高的那个。排名靠前**不一定就是故障来源**——也可能是别的原因**放大了它的错误**。你能反过来问一下：如果不是这个候选，会是什么？
>
> **次问①（M7）**：这个候选自己在**运行时指标层面**（不是 HTTP、不是 log，是容器 / 进程 / 网络 / 数据库那一层）你查过没有？
>
> **次问②（M6）**：你看到的这些异常数字——有没有可能**在没有故障的时候也差不多是这样的**？

### 2.6 期望 agent 响应

```
think_tool: "The challenger is right. I've been in ranking-mode the whole time.
The 'highest +15 errors' on ui-dashboard — did I check whether ui-dashboard itself
is actually broken at the infra level? No. Let me do that."

SQL:
  SELECT name, AVG(value), MAX(value) FROM abnormal_metrics
  WHERE service_name='ts-ui-dashboard'
    AND (name LIKE 'jvm.%' OR name LIKE 'container.filesystem%' OR name LIKE 'k8s.pod.memory%')

→ ui-dashboard 各项 infra metric 都正常（max z < 1）

think_tool: "ts-ui-dashboard itself looks normal at the infra layer. The +15 errors
are probably propagation. Let me look at who its downstream is. The SLO path in the
prompt mentions ts-route-service — but that service barely appeared in my ranking queries."

SQL:
  SELECT name, AVG(value), MAX(value) FROM abnormal_metrics
  WHERE service_name='ts-route-service' AND (...)

→ container.filesystem.usage z = 10^14（经典 OOM 签名）
→ jvm.class.loaded max z = 186

think_tool: "ts-route-service was OOM-killed. I missed it because its own span count
dropped (silent victim) — my ranking sorted by error count, not by span-absence."
```

### 2.7 结果对比

| | Baseline（无中间件）| +中间件 |
|---|---|---|
| Final RC | `ts-ui-dashboard`（错，是 top-error ripple）| `ts-route-service`（对）|
| AC@1 | ✗ | ✓ |
| 触发信号类型 | — | **A. Intent 统计模式**（opus 看 intent_counts 分布 + draft_RC 位置）|

---

## §3 例 ② — 结论前检查：**aiq-qwen, case_99**

**信号来源**：主靠 **B（reasoning 文本）+ C（draft 图 + 跨 stage hypothesis 漂移）**——opus-4.7 要读 agent 的推理文本和自己产出的结构化图才能触发。

### 3.1 场景
- Framework: aiq-qwen3.5-plus（pipeline: stage_0_main → stage_1_refine1 → stage_2_refine2 → compress）
- **dataset_index: 99**
- **datapack: `ts0-ts-consign-price-service-stress-t67vtg`**（source_data_dir: `/home/nn/SOTA-agents/RCAgentEval/data/ts0-ts-consign-price-service-stress-t67vtg/converted`）
- Fault: JVMChaos/JVMMemoryStress 注入在 `ts-consign-price-service.getPriceByWeightAndRegion()`
- GT RC: `ts-consign-price-service`（pod OOM-kill，自己 span 稀疏且 status_code=Unset，但上游 `ts-consign-service` 报 `Connection refused / 503`）
- Check point: reflect 第二次循环结束后、finalize_summary 之前
- 中期检查历史: 中期在 post_stage_0_main_terminator 触发过 M1（因为当时 stage_0 刚出 hypothesis，M1 最自然）

### 3.2 opus-4.7 在这一刻看到的 snapshot

```json
{
  "stage": "pre_finalize",
  "stage_terminators": [
    {"stage": "stage_0_main",      "hypothesis_service": "ts-consign-price-service",
     "rationale": "state=UNAVAILABLE; propagation: price → consign → ui-dashboard"},
    {"stage": "stage_1_refine1",   "hypothesis_service": "ts-consign-service",
     "rationale": "queried consign-price directly, spans show status_code=Unset / HTTP 200 — appears healthy; real 503 errors are on consign-service"},
    {"stage": "stage_2_refine2",   "hypothesis_service": "ts-consign-service",
     "rationale": "more trace counting confirms consign-service has most 503s"}
  ],
  "draft_output_graph": {
    "root_causes": ["ts-consign-service"],
    "nodes": [
      {"name": "ts-consign-price-service", "state": ["UNAVAILABLE", "KILLED"]},   // ★ agent 自己标了
      {"name": "ts-consign-service",       "state": ["HIGH_ERROR_RATE"]},
      {"name": "ts-ui-dashboard",          "state": ["HIGH_ERROR_RATE"]}
    ],
    "edges": [
      {"source": "ts-consign-service", "target": "ts-consign-price-service"}     // ★ UNAVAILABLE 节点被放在 target 位
    ]
  },
  "intent_counts_stage_1_and_2": {
    "service_trace_scan":  8,
    "service_log_browse":  5,
    "keyword_search":      3,
    "jvm_state":           0,
    "container_resource":  0
  },
  "recent_reasoning_snippets": [
    "stage_1_T: ts-consign-price-service returns HTTP 200 / status_code=Unset — this service appears healthy",
    "stage_1_T: The real problem is ts-consign-service which has 503 errors",
    "stage_2_T: Confirming ts-consign-service as root cause"
  ],
  "case_intervention_state": {
    "mid_check_primary": "M1",       // 中期已问过 M1
    "mid_check_secondary": ["M7"],
    "mid_check_agent_responded": true
  }
}
```

### 3.3 opus-4.7 的观察+判断（触发条件）

```
观察 1 (文本): stage_1 reasoning 写 "appears healthy" 针对的是 stage_0 的 hypothesis
              ts-consign-price-service——用 "no HTTP errors → healthy" 这种推理
              → 命中 M5 SilenceNeqHealth 的文本模式
观察 2 (图):  draft_output.nodes 里 ts-consign-price-service 被 agent 自己标了
              state=['UNAVAILABLE', 'KILLED']，但 root_causes 里没它
              → 命中 M3 OutputGraphInternalConsistency 的结构断言（agent 自己
                标了问题的节点为什么没列入根因？）
观察 3 (漂移): stage_0 = price-service, stage_1/2 = consign-service，hypothesis
              在推理过程中翻了；stage_0 → stage_2 distinct = 2
              → 命中 A5 AntiFlipFlopReflex（aiq-specific 卡）
观察 4 (intent): stage_1/2 中 jvm_state + container_resource = 0；agent 从来没
                 查过 stage_0 hypothesis 的运行时指标——但 M7 已经在中期问过
                 （case_intervention_state.mid_check_primary = 'M1' 带出 M7），
                 且 agent 没有响应 M7——不能同维度再作主问，只能作次问
                 或作追问素材
观察 5: M1 中期已主问过一次；原则 5 限制不能再作主问。

判断:
  - A5 强命中（观察 3）——"hypothesis 在不同 stage 反复" 是 aiq 最明显的病理，
    而且前面没问过 → 主问
  - M3 强命中（观察 2）——agent 自己的图里有内部矛盾，很适合让 agent 自查 → 次问
  - M5 中等命中（观察 1）——silence-as-health 的推理文本明确 → 次问
  - M7 弱命中但中期问过 agent 没响应 → 可以作第三个次问，提醒一次

决定:
  primary = A5，secondary = [M3, M5, M7]（正好 3 个，封顶）
  intervention_text 生成时：主问用 A5 的认知词（"不同 stage 得出不同结论"，
  避免"Correct"字样），次问每个都是轻量反问。
```

### 3.4 opus-4.7 的 JSON 输出

```json
{
  "triggered": true,
  "primary": "A5",
  "secondary": ["M3", "M5", "M7"],
  "intervention_text": "（见 §3.5）",
  "opus_reasoning_digest": "Cross-stage hypothesis drift (stage_0 != stage_1/2) + self-flagged UNAVAILABLE node missing from root_causes + silence-equals-health reasoning text + fault-layer metric never probed on stage_0 hypothesis (M7 mid-check unanswered)"
}
```

### 3.5 干预文本发给 agent

> ⚠️ **在把这个答案最终提交之前，想请你停下来重看几点：**
>
> **主问（A5）**：你的推理在**不同阶段得出过不同的结论**。最早的 hypothesis 和现在的答案不一样——这两个版本里，哪一个有更直接的、能回到"这个服务是发起故障的那个"的证据？另一个你是靠什么证据把它否掉的？
>
> **次问①（M3）**：看看你自己的输出图——有没有**你自己标了有问题的节点**（比如 UNAVAILABLE / KILLED / RESTARTING 这类 state）**但没有**列进根因的？如果有，为什么？
>
> **次问②（M5）**：当你后来直接查那个早期 hypothesis 的服务时，你看到它"没有错误"。但**看不到错误** 和**确实健康** 是不是一回事？有没有别的可能让一个服务**看起来** 安静但**其实**不正常？
>
> **次问③（M7）**：前面问过你"那个候选的运行时指标查过没"——这个问题还没有答案。

### 3.6 期望 agent 响应

```
think_tool: "The challenger is calling out multiple problems at once:
  1. A5: yes, my stages disagree. stage_0 said price-service, stage_1/2 said consign-service.
  2. M3: hmm — I labeled ts-consign-price-service as UNAVAILABLE/KILLED in the graph but
     didn't make it root. If I really think it's UNAVAILABLE, that IS the root, not a target.
  3. M5: 'no HTTP error' on a restarting pod IS expected — absence of errors doesn't mean healthy.
  4. M7: I never actually queried JVM / k8s metrics on price-service.

Let me fix M7 first — it's the concrete evidence gap."

SQL:
  SELECT name, AVG(value), MAX(value) FROM abnormal_metrics
  WHERE service_name='ts-consign-price-service'
    AND (name LIKE 'jvm.%' OR 'container.filesystem%' OR 'k8s.pod.memory%')

→ jvm.class.loaded max z = 186, container.filesystem.usage z = 10^14
  (classic OOM / restart signature)

think_tool: "OK this is overwhelming evidence. My stage_0 was right. Stage 1/2 misread
span-absence as health. Final RC should revert to ts-consign-price-service."

→ finalize_summary 被调用，root_causes = ['ts-consign-price-service']
```

### 3.7 结果对比

| | Baseline（无中间件）| +中间件 |
|---|---|---|
| Final RC | `ts-consign-service`（错，stage_1 翻错 stage_0 正解）| `ts-consign-price-service`（对）|
| AC@1 | ✗ | ✓ |
| 触发信号类型 | — | **B. reasoning 文本**（stage_1 "appears healthy" 句式）**+ C. draft 图结构**（UNAVAILABLE 节点未入 RC）**+ hypothesis 漂移**（stage_0 → stage_2 distinct = 2）|

---

## §4 两例对比 — 触发机制的两种形态

| 维度 | 例 ① 中期 | 例 ② 结论前 |
|---|---|---|
| Check point | round=30（thinkdepthai P25）| reflect 第二次循环后 |
| **opus-4.7 主要信号源** | **A. Intent 统计模式** | **B. Reasoning 文本 + C. Draft 图结构** |
| opus 看到什么最关键 | intent_counts 的不均衡 + draft_RC 位置 | stage terminator 的字符串不一致 + draft graph 节点 state 标记 vs root_causes 成员不一致 |
| Primary 维度 | M1 LoudnessAnchorSelfcheck（通用）| A5 AntiFlipFlopReflex（aiq-specific 适配卡）|
| Secondary 数量 | 2（M6, M7）| 3（M3, M5, M7 — 封顶）|
| 同维度约束起作用了吗 | 否（本来就是第一次）| 是（M1 中期已主问过，结论前不能再作主问）|
| 干预是否泄露答案 | 否，全是"反向假设？""运行时指标查过没？" | 否，全是 "哪个有更直接证据？" "自己标的问题节点为啥没进 RC？" |
| 适用场景 | 前期大幅投入 ranking 且还没碰 metric 的 agent | agent 自己产出的结构化输出（graph 或 terminator）内部有矛盾 |

**共同点**：
1. Trigger 完全不依赖 GT、fault_type、服务名硬编码
2. opus-4.7 的判断完全基于 agent 自己产生的信号（intents / 文本 / 图）
3. v4 无打分阈值；opus-4.7 自主决定 triggered / primary / secondary
4. 干预文本全部是**反问句**，不喂具体 SQL 也不给答案

这种风格的中间件换数据集、换 agent 框架、换模型都可以原样复用。
