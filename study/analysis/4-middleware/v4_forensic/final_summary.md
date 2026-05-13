# v4 元认知中间件 — Forensic 总结 + v4.1 改进路线图

**输入**：53 个稳定失败 case（baseline k=5 中至少 4 次错），其中 29 个 ultra_hard（5/5 全错）。
**v4 实测结果**：12/53 = 22.6% 翻盘，21% 在 ultra_hard slice 上。

**Task 1 结论**：12 个翻盘里 11 个是 MW 真承重（M6×6, M7×3, M5×2, M1×1），1 个是 sampling 巧合（case 572，advisor 没触发任何干预）。**没有 sampling 噪声放大的迹象** —— 22.6% 是真实效果。

**Task 2 结论**：41 个未救里，A1 victim-shifted（M8 counterfactual 把 agent 推到另一个 victim）占 34%；B1 agent-saw-correct-evidence-but-mis-attributed 占 27%；B3 counterfactual 反向加固原候选占 20%。**M8 在 conclusion 角色上 misdirected 14 次 vs helping 11 次，净效应负面。**

详见 [task1_saved_12.md](task1_saved_12.md) 和 [task2_unsaved_41.md](task2_unsaved_41.md)。

---

## 1. 维度承担效果总表

53 case × 干预触发次数（mid 47 次 / conclusion 50 次）。"承重"指该 case 翻盘的因果起点；"supporting"指附加帮助；"misdirected"指干预后 agent 走向另一错答案；"无效"指干预 fire 但 agent 行为没变。

### Mid-check 维度（thinkdepthai-qwen 主用池：M6/M7/M9 + 备用 M1/M2/M5/M10）

| 维度 | mid 触发 | 救活承重 | 救活 supporting | misdirected | 无效 | 净效用 |
|---|---:|---:|---:|---:|---:|---|
| **M6** Baseline-Contrast | 31 | 6 | 5 | 5 | 15 | **+** 主力维度 |
| **M7** Layer-Coverage | 5 | 3 | 0 | 0 | 2 | **+** 高效，触发偏少 |
| **M5** Silence ≠ Health | 4 | 2 | 0 | 0 | 2 | **+** 高效（作主问） |
| **M1** Loudness-Anchor | 6 | 1 | 1 | 2 | 2 | 中性 |
| **M9** Stagnation | 1 | 0 | 0 | 0 | 1 | 0 触发太少 |

**Mid-check secondary 池命中分布**：M5 secondary 出现 27 次（次问主力）；M2 secondary 出现 6 次；M3 secondary 4 次；其余 ≤ 2 次。

### Conclusion-check 维度（thinkdepthai-qwen 主用池：M1/M2/M3/M4/M5/M8/M10 + 备用 M6/M7/M9）

| 维度 | conc 触发 | 救活承重 | 救活 supporting | misdirected | 无效 | 净效用 |
|---|---:|---:|---:|---:|---:|---|
| **M8** Hypothesis-Counterfactual | 47 | 0 | 11 | 14 | 22 | **−** 净反作用 |
| **M2** Chronic-Noise Skepticism | 2 | 0 | 0 | 1 | 1 | 0 触发太少 |
| **M1** Loudness-Anchor | 1 | 0 | 0 | 1 | 0 | 0 触发太少 |

**Conclusion-check secondary 命中分布**：M5 出现 11 次；M3 出现 5 次；M2 出现 4 次；其他 ≤ 2 次。

### 完全没承重的维度

| 维度 | 触发情况 | 原因推测 |
|---|---|---|
| **M3** Output-Graph Consistency | secondary 4 次（mid + conc）；从未主问 | thinkdepthai 在 compress 之前没有结构化 graph，reasoning 文本检测可能不准 |
| **M4** Sibling-Disambiguation | 0 次主问 | trigger 应包含名字相似（Levenshtein/Jaro-Winkler）但 v4 未配置触发条件 |
| **M9** Stagnation | 1 次主问（case 4510 失败）| trigger 信号"重复探查"难以离散判定 |
| **M10** Premature Commitment | 0 次主问 | thinkdepthai-qwen mid threshold=30 已过 P25=32，M10 应该是早期介入但实际 fire 不到 |

---

## 2. 关键洞察

### 洞察 1：M8 counterfactual 是把双刃剑

**支持的证据**：M8 在 wrong→wrong 中 misdirected 14 次（A1 桶的核心成因）。M8 prompt "如果候选完全健康，其他异常还会发生吗？" 在 victim-as-RC 场景下**反向加固**——qwen 推理"如果 victim 健康，那 cascade 错确实不会发生"是符合逻辑的（victim 服务的下游 503 propagation 在 victim 健康时确实会停），但这个推理只能确认 victim 是 cascade 链上的一环，**不能区分 victim vs origin**。

**对照**：在 wrong→correct 的 12 个 case 里，M8 担任 supporting 11 次（never 承重）。承重作用都来自 mid-check 的 M6/M7/M5/M1。

**结论**：**M8 prompt 设计的根本缺陷**——"counterfactual 如果候选健康"无法区分 victim vs origin。对应原则 1 的元认知反思在这个角度下是空操作。

### 洞察 2：M6 baseline-contrast 是绝对主力

**支持证据**：12 个 saved 中 6 个由 M6 承重（50%）；mid 触发 31 次（66% 的 mid-check）；在 wrong→wrong 中也起到 supporting 作用（filter 掉 chronic noise 让 agent 至少不被表层 RabbitMQ DNS 等误导）。

**结论**：**M6 是 thinkdepthai-qwen 上最稳定有效的元认知反思维度**——baseline 对比这个动作本身极强普适性。建议：
- v4.1 即使 trigger 信号微弱也优先 fire M6
- 中期 mid-check 主用池里 M6 应保持最高优先级

### 洞察 3：M7 layer-coverage 在运行时层故障上致命承重

**支持证据**：3 个 saved 案例（807 ts-train-service CPU 92%, 1143 container restart, 1394 CPU 4.86 spike）全靠 M7 引导查 k8s/container/JVM 指标；这些信号 baseline 完全不会主动查。

**结论**：M7 prompt 击中 thinkdepthai-qwen 的固定查询模板（traces+logs+metrics 中 metrics 用得最少），是 framework-specific 的"行为遗漏型"补救。**M7 触发偏少（仅 5 次）**——可考虑放宽 trigger（如检测 "intent_log 中 metric_diagnose 类 < 阈值" 时强 fire）。

### 洞察 4：M5 silence ≠ health 在 silent-victim 类故障上承重

**支持证据**：case 1114 ts-config-service silent restart 和 case 4353 ts-station-service deployment.available=0 都是 M5 单独承重。

**结论**：**M5 trigger 应在 reasoning 文本含 "no errors / healthy / appears fine / 0 ERROR logs" 时强 fire**。当前 v4 触发不够频繁（仅 4 次主问，主要是次问 27 次）。

### 洞察 5：维度工作但 reasoning 缺陷不可补救（B1）

**支持证据**：11 个 case（27%）属于 "agent 在 reasoning 里已经引用过 GT 服务/IP 或正确方向，但选错"——典型如 case 156（"connection refused to 10.0.3.156" → 知道是 unreachable upstream microservice 但不切换候选），case 1218（agent 知道 ts-seat-service 是 callee 但仍 commit），case 2258（agent 看到 "travel2-service spans MISSING"），case 1814（agent 看到 timeline 早期错误来自 chronic 但仍选 ts-travel-service）。

**结论**：**这是 instruction-following 缺陷，不是 prompt 设计缺陷**。改 prompt 收益不大；v4.1 可考虑：
- 在 conclusion 干预里加入"如果你刚才在 reasoning 里提到了某个服务但没列入 RC，是否应该把它列入？"这种**自我引用反思**
- 或者在 mid 干预后做"提示：你现在的候选列表是 X；trajectory 中你提到过 Y 但未列入——这是有意为之吗？"

### 洞察 6：M3/M4 在 thinkdepthai-qwen 上失能

**支持证据**：M3（output-graph consistency）触发 9 次都是 secondary、never 承重；M4（sibling disambiguation）从未主问。case 99（`ts-consign-service` vs `ts-consign-price-service`）是 M4 经典命中场景但 v4 没识别；case 1218、2258 是 M3 应该 fire 的（agent 自己 reasoning 里讲清了 caller-callee 但还选 callee）。

**结论**：**M3/M4 trigger 离散信号设计不足**：
- M4 trigger 应基于 "agent 输出 RC 与 trajectory 出现过的服务名 Levenshtein < 3" 强 fire（这是 v4 原则 2 中允许的"字符串相似度"信号）
- M3 trigger 应基于 reasoning 文本中"caller-callee 方向词"+"agent RC 是 callee 服务"组合检测

---

## 3. v4.1 改进路线图

按优先级排序（impact / effort 比）。

### 高优先级 P0

**P0-1 · 改写 M8 prompt 的 counterfactual 角度**（impact: −14 misdirected case → 净 +0 至 +5 翻盘）

当前 M8 prompt：
> "if your candidate were completely healthy, would the other anomalies still occur? If yes, victim; if no, origin."

问题：qwen 几乎总能回答 "no"（因为 cascade 错误确实由 victim 链路传出），所以加固 victim 锚定。

建议改写：
```
"在你 commit 前，再做一个反向问询：你看到的这个'最响亮的错误'，
它产生的具体内容（如 503/Connection refused/database error）描述的是
**这个服务自己出问题**还是**它在尝试某个动作时遇到问题**？
- 'ConsignRepository.findByOrderId 抛 NonUniqueResultException' 是它自己的内部错误
- '503 Connection refused to 10.0.x.y' 是它在调外部时遇到问题——那个被调的服务可能是 RC

如果你的候选错误是后者，请重新审视 trajectory 中是否有'被调用但消失'的服务。"
```

这个改写**直接给 agent 区分 internal-error vs external-call-failed 的二分**，避免空泛的 counterfactual。

**P0-2 · 新增 M11（victim-vs-origin 分诊）维度**（impact: 5+ A1 case 可救）

trigger：reasoning 文本含 "Connection refused / upstream / dial tcp / 不可达 / unreachable" 类关键词
intervention：明确反思"这个不可达的上游服务是不是你的真正候选"

把 victim-shifted 这个 v4 主要失败模式作为独立维度处理。

### 中优先级 P1

**P1-1 · M4 (Sibling-Disambiguation) trigger 启用**（impact: 1-2 case，包括 case 99）

trigger：agent 输出 RC 服务 vs trajectory 出现服务的 Levenshtein 距离 < 3
intervention：列出相似服务对，让 agent 反思

**P1-2 · M3 (Output-Graph Consistency) trigger 升级**（impact: 2-3 case）

trigger：agent 在 reasoning 文本中明确说 "calls X" 或 "X calls our candidate"，且候选是被调用方（callee）
intervention：让 agent 反思 caller 是不是更上游的 RC 候选

**P1-3 · M5 trigger 放宽**（impact: 1-2 case）

trigger：reasoning 含 "no errors / healthy / appears fine / 0 ERROR" 时强 fire（不仅仅是次问）

### 低优先级 P2

**P2-1 · M9 (Stagnation) trigger 设计**（current: 仅触发 1 次，承重 0 次）

考虑通过 "intent_log 出现重复 query type ≥ 5 次" 强 fire；或者放弃这个维度（在 thinkdepthai 上 ROI 太低）

**P2-2 · M10 (Premature Commitment) trigger 设计**

thinkdepthai-qwen mid threshold=30，对应 correct case P25=32。M10 应该在 round_count < 25 时 fire，但目前没看到任何 fire。建议在中期 check point 时增加 round_count < P25 的 hard fire 条件。

**P2-3 · 新增 multi-hop-path-internal 维度**（impact: 1 case，case 4510）

trigger：reasoning 文本中提到 ≥ 4 跳的 call chain，且候选在中间段
intervention：让 agent 反思中间段是否本身有问题

### 维度去除候选

**M9 + M10**：在 thinkdepthai-qwen 上承重 0 次，可考虑暂停启用（节省 LLM 调用 token）

---

## 4. 数据可视化建议

### 4.1 维度承担柱状图（应放进总报告）

```
M6 ████████████████████████████████ 31 (6 helped, 5 supporting, 5 misdirected, 15 inert)
M7 █████ 5 (3 helped)
M5 █████ 4+27sec (2 helped, 0 misdirected)
M1 ██████ 6 (1 helped, 2 misdirected)
M8 ████████████████████████████████████████████████ 47 (0 helped, 11 supp, 14 misdirected, 22 inert)
M9 █ 1 (0 helped)
```

### 4.2 失败模式漏斗

```
53 cases (k=5 stable failure)
  → 12 saved (22.6%)
      ├─ 11 MW-helped (M6×6, M7×3, M5×2, M1×1)
      └─ 1 sampling-perturbation (case 572, no MW fire)
  → 41 unsaved (77.4%)
      ├─ 14 A1 victim-shifted (M8 counterfactual misdirected)
      ├─ 11 B1 saw-correct-evidence (instruction-following gap)
      ├─ 8 B3 counterfactual-reinforced-original
      ├─ 8 B2 GT-not-abnormal-only
      └─ — sampling-failure
```

### 4.3 跨 theme 翻盘率

| Theme | 总 case | saved | 救活率 | 主要承重维度 |
|---|---:|---:|---:|---|
| T1 Silence-as-Health | 9 | 4 | 44% | M5, M7, M1 |
| T3 Noise-Anchor | 14 | 4 | 29% | M6 |
| T2 Blame-the-Messenger | 17 | 2 | 12% | M6, M5 |
| T4 Amplitude-Greed | 7 | 1 | 14% | (sampling) |
| T5 Query-Blindness | 3 | 1 | 33% | M6 |
| T6/T7/T8 | 3 | 0 | 0% | — |

**关键观察**：
- T1 (Silence-as-Health) 救活率最高（44%），符合预期——M5/M7 设计正是针对这类
- T2 (Blame-the-Messenger) 救活率最低（12%）—— A1 victim-shifted 大本营，需要 P0-1 + P0-2 重点解决
- T6/T7/T8（path-through、business-logic、causal-inversion）零救活——这三类需要新维度

---

## 5. 总结

**v4 在硬核稳定失败集（baseline k=5 中 80%+ fail）上达成 22.6% 净翻盘**，全部由元认知 mid-check 干预承担（M6/M7/M5/M1），无 sampling 噪声放大。这验证了 v4 的核心设计假设："1 主问 + 0~3 次问"的复合元认知干预 + LLM-as-advisor 自主判断机制有效。

**主要失败模式集中在 M8 conclusion counterfactual 的反向作用**（34% A1 victim-shifted），其次是 agent instruction-following 缺陷（27% B1）。前者是 prompt 设计问题，可通过 P0-1（重写 M8）和 P0-2（新增 M11 victim-vs-origin 维度）解决；后者是 agent 自身能力上限，难以纯靠 prompt 解决。

**给 thinkdepthai-qwen3.5-plus 框架的最终结论**：
- v4 把硬核 case AC@1 从 0% 拉到 22.6%（净 +22.6%）
- v4.1 关键改进项：改写 M8（P0-1）+ 新增 M11（P0-2）+ 启用 M3/M4 trigger（P1-1, P1-2）
- 改进后预期：在同 53 case 集上 35-45% 翻盘（额外救 7-12 个 A1 case + 1-2 个 sibling case）

---

## 附：关键文件

- 提取脚本：[extract.py](extract.py)
- Per-case JSON 缓存（53 个）：[cache/](cache/)
- 12 个救回 case 详分析：[task1_saved_12.md](task1_saved_12.md)
- 41 个未救 case 失效归因：[task2_unsaved_41.md](task2_unsaved_41.md)
- 样例 writeup（结构演示）：[_sample_writeups.md](_sample_writeups.md)

数据 exp_id：
- baseline 单跑：`thinkdepthai-qwen3.5-plus`（500 case，judged）
- baseline k=4 重采样：`thinkdepthai-qwen3.5-plus-2026-02-15-resample-{1,2,3,4}`
- v4 干预：`thinkdepthai-qwen3.5-plus-2026-02-15-mw-v4-run`（53 case，judged）
