# M9 — Investigation Stagnation

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-4 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | 372 case 中数量 |
|---|---|---|---:|
| **PD 层** | (无独立对应 PD) — M9 沿袭 v3 B1 维度，独立于 X-1..X-6 重构 | — | (v3 实测有效) |
| **R 层** | (相关) U1/U2 commit 之前的"重复探查同一服务" 阶段，常常是 stagnation | (背景) |
| **D 层** | (无关) | — |

**v3 实测有效性**：v3 在 thinkdepthai-qwen 105 case 上 B1 维度命中 14 case 全部翻盘（100%），是最高效的维度之一。但 v3 也发现 B1 与 B3 (Missing Baseline) 的自循环 bug——B3 引发 baseline 重复 → B1 又开火。**M9 在 v4 中已修这个 bug**：trigger 排除 baseline 类 intent。

**对应失败 case 数（M9 主问触发的初步估计）**：
- v3 实测 B1 命中 14 / 105 = 13.3%
- 跨 framework 估计：trigger 通用，命中率与 framework 的"轨迹长度"和"是否容易锁死单一服务"相关
- M9 主问的目标 case 池：~30-50 case 跨 4 framework

**Per-framework 估计**：
- thinkdepthai-qwen3.5-plus: ~14 case（v3 实测）
- thinkdepthai-claude-sonnet-4.6: ~10 case（sonnet 也容易锁死）
- aiq-qwen3.5-plus: ~5 case（aiq stage 切换会缓解 stagnation）
- claudecode-qwen3.5-plus: ~10 case

---

## Cognitive vocabulary

**这种认知模式是什么样**：

agent 在调查到某个阶段后**陷入"反复探查同一个服务"的循环**。最近 K 个 round 大部分（≥80%）SQL 都针对同一个 target service，意图类别也在重复（都是 latency_ranking 或都是 service_log_browse 等），但**没引入新的视角**——没换 target service，没换 intent 类别。这通常发生在：
- agent 已经倾向某个候选 RC，于是反复在该候选身上找证据
- agent 卡在"我应该再查一次确认一下"的犹豫里
- agent 把 round 浪费在同质化查询上，而不是横向探查别的可能性

**这不一定是 commit-前现象**——M9 可以在调查中期触发，提醒 agent "你正在打转，是不是该跳出来"。

**反思的认知动作**：让 agent 意识到自己**当前的查询模式是重复的、无新观察的**，反问"是不是该换个角度，或者该考虑其他候选？"——把"该查什么新东西"的决策权留给 agent。

**v4 修 v3 自循环 bug**：v3 B1 检测器把 baseline 类 intent 也当作"重复"——结果 B3 引导 agent 多做 baseline_contrast 时，B1 反而开火指责 agent "重复"。M9 的 trigger 排除 baseline 类 intent，**baseline 类查询的重复不算 stagnation**（因为 baseline 对比本身就需要多次查询不同服务/时段做对照）。

---

## Trigger abstract（运行时可观察）

```pseudo
trigger_M9(state) :=
  (LET K = 5   // 最近 K round
   LET recent_intents = state.intent_log[ last_K_rounds = K ]
                          WHERE intent NOT IN
                            { 'baseline_collect', 'baseline_contrast' }   // v4 修 v3 bug：排除 baseline
   LET unique_target_services = SET(intent.target_service FOR intent IN recent_intents)
   LET unique_intent_types    = SET(intent.intent_type FOR intent IN recent_intents)
   LET dominant_service       = MOST_COMMON(intent.target_service FOR intent IN recent_intents)
   LET dominant_service_share = COUNT(WHERE target_service == dominant_service) / LENGTH(recent_intents)

   IN
     LENGTH(recent_intents) >= 4   // 至少 4 个非-baseline intent 才能判断 stagnation
     AND dominant_service_share >= 0.80
     AND LENGTH(unique_intent_types) <= 2
     AND no_new_evidence_extracted_in_last_K_minus_1_rounds(state, K))
```

`no_new_evidence_extracted_in_last_K_minus_1_rounds()` 是辅助谓词：检查最近 K-1 个 round 的 SQL 结果是否引入了新的 service_name / 新的 error pattern / 新的 metric value 离群点。如果这些 round 的工具结果都和之前重复（agent 没看到新东西），返回 True。

**触发场景示例**：
- thinkdepthai (qwen)：最近 5 round 的 SQL 都是 `service_trace_scan` + `service_log_browse` 在 service S 上，且工具结果都是同样的 trace/log 列表（agent 在反复 confirm 自己的猜测）
- claudecode：最近 5 个 Bash tool call 都对 service X 做应用层 query，但结果重复

---

## Intervention pattern

### 主问（M9 作为 most_critical 时）

> **最近几轮你都在同一个服务上做同类查询，但好像没看到什么新东西。这种重复探查通常意味着两种可能：要么你已经有结论了只是在 confirm，要么你陷在了一个候选上没法跳出来。如果是后者——能不能换个角度？比如换一种 intent 类别，或者直接看一下你之前忽略的其他候选？**

**变体**：
- 变体 A（中期检查，agent 在调查阶段重复探查）：
  > "你最近几轮都在同一个服务上做差不多的查询，没看到新东西。是不是已经卡在这个候选上了？能不能换个角度——比如换一种数据视角，或者看一下你之前没专门探过的其他服务？"
- 变体 B（结论前检查，agent 即将提交但最近 round 一直在同一服务）：
  > "你最近几轮的探查都集中在同一个服务上，但没引入新观察。在最终提交之前请反问一次：这种重复是因为你已经确认了候选，还是因为你陷在一个方向上没换角度？如果是后者，提交前能不能补一次横向对比？"

### 次问（M9 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你最近几轮都在同一服务上重复同类查询，可以顺带反思一下：是不是该换个角度？"

**次问触发条件**：M9 作为次问被加入复合干预，**仅当** L2 对 M9 给出 `match_score ≥ 0.7`（即满足重复模式 + 无新观察 + 排除 baseline 后）。如果最近几轮 agent 已在多个服务/intent 类别间切换，L2 给 M9 低分，**不加 M9 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 用 intent 历史 + target_service 重复模式 + tool 结果新颖度，**不和** gt_services 比）
- [x] **Trigger 不含 SQL 字符串**（用 intent 抽象类别 + 谓词函数）
- [x] **Trigger 不含具体服务名**（dominant_service 是变量）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（用"同一个服务"、"其他候选"指代）
- [x] **Intervention 不含错误消息字串**（无）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（无方向性词；"换个角度"、"横向对比" 是认知词）
- [x] **Intervention 用反问 + 多种可能性句式**（"通常意味着两种可能：要么已经有结论了，要么陷在一个候选上没法跳出来"——经典两种可能；"如果是后者..."——开放分支引导）
- [x] **agent 可基于自身已做的动作自我修正**（"最近几轮你都在同一个服务上做同类查询"——直接引用 agent 行为）

**全部 9/9 ✓ → M9 卡片符合 v4 元认知设计原则**

**v3 bug 修复确认**：trigger 中明确排除 `baseline_collect` / `baseline_contrast`，避免 M6 引导 agent 做 baseline 时 M9 又开火指责"重复"。

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✓ 主问候选 | v3 实测 B1 命中 14 case 全翻盘，**最有效的 framework 之一** |
| thinkdepthai (claude-sonnet-4.6) | ✓ 主问候选 | sonnet 也容易锁死（v3 实测有效） |
| aiq (qwen3.5-plus) | ✓ 主问候选 | aiq 的 stage 切换在一定程度上缓解 stagnation；触发率较低但仍有用 |
| claudecode (qwen3.5-plus) | ✓ 主问候选 | trigger 通用 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

| Framework | failure case 总数 | M9 触发估计 | M9 翻盘期望（按 v3 实测 100% 类比，保守 60%） |
|---|---:|---:|---:|
| thinkdepthai-qwen3.5-plus | 105 | ~14（v3 实测）| **~8 case 翻盘** |
| thinkdepthai-claude-sonnet-4.6 | 50 | ~10 | ~6 case 翻盘 |
| aiq-qwen3.5-plus | 113 | ~5 | ~3 case 翻盘 |
| claudecode-qwen3.5-plus | 102 | ~10 | ~6 case 翻盘 |

**总翻盘期望**：~23 case 跨 4 framework。

**注意 v3 中 B1 的"misdirected" 现象**：v3 文档提到 B1 触发后 agent 有时只换了查询角度但没换 target service ("misdirected"——agent 表面响应但本质继续 stagnant)。v4 主问中明确"换一种 intent 类别，或者直接看一下你之前忽略的其他候选"——把"换角度"的两个具体方向都列出来，降低 misdirected 概率。

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **M6 (Baseline-Contrast Reflex)** | （v3 自循环 bug 现已修复）M6 引导 baseline 多次查询时，M9 不会触发因为 trigger 排除了 baseline 类 intent | 无冲突，trigger 已解耦 |
| **M1 (Loudness-Anchor)** | M9 在调查中期触发，M1 在 commit 前触发，时间序基本不重叠 | 时间序错开，可同时存在不同 check point |
| **M10 (Premature Commitment)** | 互斥：M10 要求 round count 短，M9 要求最近 K round 重复（必然 round 多）| 互斥，不会同时命中 |

---

## 实施备注

- **关键依赖**：
  - `no_new_evidence_extracted_in_last_K_minus_1_rounds()` 谓词需要 L1 在 intent 分类时附带提取 SQL 结果的"新颖度"（新出现的 service_name / 新的 error pattern / 离群 metric）
  - K 默认 5（最近 5 round），D-5/D-6/D-7 阶段可按 framework 调
- **离线重放验证**：在 372 已标注 case 上跑 trigger，统计 (precision, recall) 相对于"明显 stagnation" 的人工标注（v3 时已有 14 个标注 sample）

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-4 阶段输出）；修 v3 B1 自循环 bug（trigger 排除 baseline 类 intent）|
