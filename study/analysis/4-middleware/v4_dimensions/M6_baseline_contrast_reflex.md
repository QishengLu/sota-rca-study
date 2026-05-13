# M6 — Baseline-Contrast Reflex

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-3 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | 372 case 中数量 |
|---|---|---|---:|
| **PD 层** | `PD_NoBaselineContrast` | `baseline_contrast` intent 全程为 0；agent 从未把 normal vs abnormal 数据放到一起对比 | **316** |
| **R 层** | (相关) U2 ChronicAmbientNoiseAnchor — M6 是该 R 类的 **PD 检测对应物** | (背景) |
| **D 层** | (相关) D3 AmbientNoiseDominatesGT — 数据形态背景 | (背景) |

**对应失败 case 数（M6 主问触发的初步估计）**：
- 严格按 PD trigger（baseline_contrast intent 全程 0 + abnormal-数据 intent ≥10）：~316 case 中大部分（PD 触发率高）
- M6 主问的目标 case 池：~250-300 case（**v4 维度库中触发率最高**）

**Per-framework 分布**（来自 PD_taxonomy.md）：
- aiq-qwen3.5-plus: 112 / 113 = 99.1%
- claudecode-qwen3.5-plus: 78 / 102 = 76.5%
- thinkdepthai-claude-sonnet-4.6: 22 / 51 = 43.1%
- thinkdepthai-qwen3.5-plus: 104 / 105 = 99.0%

**注意**：M6 触发率极高（aiq + qwen 接近 100%）。这是好事也是坏事：
- 好：很容易命中
- 坏：和 M2 严重重叠，需要靠 L2 消歧规则避免重复干预

---

## Cognitive vocabulary

**这种认知模式是什么样**：

agent 在调查阶段大量查询 abnormal 时段的数据（abnormal_logs / abnormal_traces / abnormal_metrics），但**全程从未明确把同样的查询应用在 normal 时段并做对比**。这导致 agent 看到的"异常"其实可能是"该环境的常态"——它没法区分"这个错误是因为故障注入产生的"vs "这个错误本来就一直存在"。

**注意 M6 vs M2 的本质区别**：
- **M6** 是**纯行为遗漏检测**：只要 baseline_contrast intent = 0 + abnormal-数据 intent ≥ 阈值即触发；不关心 agent 选了什么候选
- **M2** 是**R 层失败模式**：在 M6 触发的基础上 + 候选 RC 与 chronic noise 模式相关 + about_to_commit 时刻

也就是说：**M6 触发条件比 M2 宽**。当 L2 给 M6 高分但给 M2 低分时（agent 没做 baseline 对比，但候选不是 chronic 类服务），干预内容应该是 M6 的版本（提醒"做基线对比"），而不是 M2 的版本（提醒"chronic noise 可能是常态"）。

**反思的认知动作**：让 agent 意识到自己**全程没做基线对比**这件事本身。这是一个**轻量行为提醒**，不是深度反思——只问"你查了大量异常时段数据，但还没对照过正常时段，是不是该补一下？"

---

## Trigger abstract（运行时可观察）

```pseudo
trigger_M6(state) :=
  (LET baseline_intents_count = COUNT(state.intent_log WHERE intent IN
                                  { 'baseline_collect', 'baseline_contrast' })
   LET abnormal_data_intents  = COUNT(state.intent_log WHERE intent IN
                                  { 'error_log_overview', 'service_error_log',
                                    'service_log_browse', 'keyword_search',
                                    'error_timeline', 'error_rate_scan',
                                    'latency_ranking', 'service_trace_scan',
                                    'metric_scan', 'jvm_state', 'k8s_state',
                                    'container_resource', 'db_state',
                                    'network_layer', 'trace_follow', 'call_tree_build' }
                                AND query_target_window == 'abnormal')
   IN
     baseline_intents_count == 0
     AND abnormal_data_intents >= 10)
```

**触发场景示例**：
- 任何 framework：trajectory 里大量查 abnormal_logs / abnormal_traces / abnormal_metrics 但从未跑 normal_* 表的对比查询
- 触发不要求 about_to_commit；可以在中期检查时随时触发

**注意 M6 触发与 M2 触发的差异**：M6 不要求 candidate 与 chronic noise 相关（M2 要求）；M6 不要求 about_to_commit（M2 要求）。所以 M6 的触发场景**包含**了 M2 的触发场景。

---

## Intervention pattern

### 主问（M6 作为 most_critical 时）

> **你查了不少异常时段的数据，但还没对照过正常时段。微服务环境很常见的情况是：某些数据上的"异常"其实是长期常态，不是当前故障的产物。在你继续推进之前，能不能想办法补一次基线对比？这能帮你把"真的异常"和"环境本来就有的常态"分开。**

**变体**：
- 变体 A（中期检查，agent 还在调查阶段）：
  > "你已经查了不少异常时段的数据，但还没对照过正常时段。能不能补一次基线对比，把'真的异常'和'环境本来就有的常态'分开？这是排除常态噪声的标准做法。"
- 变体 B（结论前检查，agent 即将提交但全程没做 baseline）：
  > "你即将提交根因，但你的整个调查过程没做过一次正常时段 vs 异常时段的对比。在最终提交前请补一次基线对比，确认你看到的异常信号确实是当前故障引起的，而不是环境本来就有的。"

### 次问（M6 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你全程没做过基线对比，可以顺带补一次，把'真的异常'和'环境本来就有的常态'分开。"

**次问触发条件**：M6 作为次问被加入复合干预，**仅当** L2 对 M6 给出 `match_score ≥ 0.7`（即 baseline 类 intent 全程为 0 + abnormal-数据 intent ≥ 10）。如果 agent 已做过 baseline_contrast，L2 给 M6 低分，**不加 M6 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 用 intent 类别计数，**不和** chronic_noise_carriers / parquet 算出来的 chronic 真值比）
- [x] **Trigger 不含 SQL 字符串**（用 intent 抽象类别）
- [x] **Trigger 不含具体服务名**（trigger 是全局 intent 计数，不涉及具体服务）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（无）
- [x] **Intervention 不含错误消息字串**（无）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（只用"基线对比"、"常态"等中性词）
- [x] **Intervention 用反问 + 多种可能性句式**（"能不能补一次基线对比"——开放邀请；"把'真的异常'和'环境本来就有的常态'分开"——多种可能性）
- [x] **agent 可基于自身已做的动作自我修正**（"你查了不少异常时段的数据"引用 agent 自己的 query 行为）

**全部 9/9 ✓ → M6 卡片符合 v4 元认知设计原则**

**审核风险点**：M6 是不是太"轻"了？只是提醒做 baseline_contrast，没有更深的反思引导。

我的判断：**M6 故意保持轻量**。它是 PD-pure 维度，针对 agent 完全没做基线对比这件事本身做提醒。深度反思（"chronic noise 可能是 RC 的承担者"）由 M2 承担。M6 = 行动提醒，M2 = 推理反思。L2 通过给 M2 vs M6 不同的 match_score 决定哪个作主问。

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✓ 主问候选 | 99% PD1，**几乎全 case 触发**；优先作次问搭配 |
| thinkdepthai (claude-sonnet-4.6) | ✓ 主问候选 | 43% PD1，sonnet 比 qwen 自觉做 baseline 多 |
| aiq (qwen3.5-plus) | ✓ 主问候选 | 99% PD1，**几乎全 case 触发** |
| claudecode (qwen3.5-plus) | ✓ 主问候选 | 76% PD1 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

**M6 触发率极高，但翻盘贡献和 M2 重叠很大**——精确归因需要 L2 消歧规则后的实测：

| Framework | failure case 总数 | PD1 占比 | M6 主问命中估计（去掉与 M2 重叠后）| M6 翻盘期望（按 v3 B3 维度类比，~30%）|
|---|---:|---:|---:|---:|
| thinkdepthai-qwen3.5-plus | 105 | 99% | ~70（去 M2 重叠的 22 后） | ~20 case 翻盘 |
| thinkdepthai-claude-sonnet-4.6 | 50 | 43% | ~15 | ~5 case 翻盘 |
| aiq-qwen3.5-plus | 113 | 99% | ~95（去 M2 重叠的 17 后）| ~28 case 翻盘 |
| claudecode-qwen3.5-plus | 102 | 76% | ~45（去 M2 重叠的 32 后）| ~13 case 翻盘 |

**总翻盘期望**：~65 case 跨 4 framework（**v4 维度库中翻盘期望最高的之一**）。但需注意：M6 翻盘很大程度上是 v3 B3 维度的延续（v3 实测 B3 命中 14/14 全翻盘），所以这里数字是基于 v3 实绩外推。

**Phase 8 离线重放将给出精确数值。**

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **M2 (Chronic-Noise Skepticism)** | 严重重叠：M2 触发条件（baseline 缺失 + 候选与 chronic 相关 + about_to_commit）是 M6 触发条件（baseline 缺失 + abnormal 数据多）的子集 | **L2 消歧规则**：当两者都命中时，**M2 优先作主问**（更深度的反思），M6 退为次问。M2 没命中但 M6 命中时（即 baseline 缺失但候选不在 chronic 服务名册），M6 作主问 |
| **M9 (Investigation Stagnation)** | M6 触发时 agent 可能也在重复查同类 abnormal 数据 → M9 也可能命中 | M9 关注重复模式，M6 关注 baseline 缺失。两者关注不同侧面，可同时命中 |

---

## 实施备注

- **关键依赖**：
  - L1 必须能区分 SQL 是 normal 时段查询还是 abnormal 时段查询（通过 SQL 字符串中的 `FROM normal_*` vs `FROM abnormal_*` 模式 / SQL 时间范围参数）
  - 触发不需要 about_to_commit 状态，可在中期检查的任意时点触发
- **L2 vs M2 消歧 prompt**：opus-4.7 prompt 应明确："如果 candidate 与 chronic noise 模式相关 → M2 高分，M6 中分；如果 candidate 与 chronic 无关但 baseline 缺失 → M6 高分，M2 低分"
- **离线重放验证**：在 372 已标注 case 上跑 trigger，统计 (precision, recall) 相对于 PD_NoBaselineContrast 标注

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-3 阶段输出） |
