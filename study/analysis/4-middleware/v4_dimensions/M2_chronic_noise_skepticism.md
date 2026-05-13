# M2 — Chronic-Noise Skepticism

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-1 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | 372 case 中数量 |
|---|---|---|---:|
| **R 层** | `U2_ChronicAmbientNoiseAnchor` | agent 把数据集中本来就长期存在的 chronic ERROR 日志（环境噪声）当作故障证据，commit 噪声所属的服务 | **85** |
| **PD 层** | `PD_NoBaselineContrast` | agent 全程从未做 normal vs abnormal 数据对比 | **316**（涵盖更广） |
| **D 层** | D3 (AmbientNoiseDominatesGT) — 作为 "你看到的错误可能本来就在" 的多种可能性素材，非独立触发 | 数据集本身有 chronic noise | (背景) |

**对应失败 case 数（M2 主问触发的初步估计）**：
- 严格交集 (U2 ∧ PD_NoBaselineContrast)：~70 case（U2 标注的子集，绝大多数 U2 case 都伴随 baseline 缺失）
- 宽松命中 (U2 单独)：85 case
- M2 主问的目标 case 池：~70-90 case

**Per-framework 分布**（来自 unified_R.md）：
- aiq-qwen3.5-plus: 17 / 113 = 15.0%
- claudecode-qwen3.5-plus: 35 / 102 = 34.3%（含 R2 ChronicInfraNoise 24 + R3 FabricatedAncestor 11）
- thinkdepthai-claude-sonnet-4.6: 7 / 50 = 14.0%
- thinkdepthai-qwen3.5-plus: 26 / 105 = 24.8%

---

## Cognitive vocabulary

**这种认知模式是什么样**：

任何长期运行的微服务环境都会产生**常态性的 ERROR 日志**——配置不到位的服务一直在报某类错误、某些 ORM 查询永远返回 NonUnique、某些消息队列 DNS 一直找不到。这些错误**在故障窗口和正常窗口出现频率几乎一致**，跟当前注入的故障无关。

agent 的失败模式是：因为这些 chronic error 在 abnormal 时段查询里**绝对量很大**（往往是 top 1-3），且消息内容看起来"很像故障"（DNS 查不到、连接池耗尽），agent 直接把它们当作根因证据，commit 这些 chronic noise 所属的服务，而不去查"这个服务在没故障时是不是也报这个错"。

**反思的认知动作**：commit 之前主动做一次"基线对照"——"**这个错误，没有故障时是不是也会出现？**"——这一步迫使 agent 把 abnormal 数据放到"和 normal 数据对比"的框架里看，而不是孤立地把"绝对量大"等同于"是当前故障"。

---

## Trigger abstract（运行时可观察）

```pseudo
trigger_M2(state) :=
  (LET about_to_commit          = state.is_at_check_point AND state.draft_root_causes != []
   LET baseline_intents_count   = COUNT(state.intent_log WHERE intent IN
                                    { 'baseline_collect', 'baseline_contrast' })
   LET abnormal_only_intents    = COUNT(state.intent_log WHERE intent IN
                                    { 'error_log_overview', 'service_error_log',
                                      'service_log_browse', 'keyword_search',
                                      'error_timeline', 'error_rate_scan' })
   LET candidate_RC             = state.draft_root_causes[0]
   LET candidate_RC_evidence    = state.findings_about[candidate_RC]   // agent 给该候选积累的证据
   LET evidence_only_from_abnormal = (candidate_RC_evidence.normal_window_check_count == 0)
   IN
     about_to_commit
     AND baseline_intents_count == 0
     AND abnormal_only_intents >= 5
     AND evidence_only_from_abnormal)
```

**触发场景示例**：
- thinkdepthai：agent 在 round 18 看到 abnormal_logs 里某服务有 138 条 ERROR，commit 它为 RC，但全程没跑过 normal_logs
- aiq：stage_0 完成 terminator 指向某服务，整个 stage_0 的 SQL 都是 `FROM abnormal_*`，从未 join/union normal
- claudecode：Bash 命令里全是 `query.sh abnormal_logs.parquet`，最后 commit RC 来自 abnormal logs 的 top error 服务

---

## Intervention pattern

按 v4 原则 4 的「1 主问 + 2~3 次问」复合结构生成：

### 主问（M2 作为 most_critical 时）

> **你看到了一些错误信号并基于它们准备 commit 一个候选——但你查的全是异常时段的数据，从来没对照过正常时段。你看到的这些错误，有没有可能在没有故障的时候本来也是这样？环境本身可能就有一些长期存在的报错，是配置问题或者历史遗留，跟当前的故障无关。在确认前你能不能想办法验证一下，这些错误到底是新出现的，还是一直都在？**

**变体**：
- 变体 A（中期检查）：
  > "你查了不少异常时段数据，但还没对照过正常时段。微服务环境很常见的情况是：某些错误是长期存在的（配置问题、历史遗留），不管有没有故障它们一直在报。你看到的'异常'有没有可能本身就是常态？在你继续推进之前，能不能想办法验证一下？"
- 变体 B（结论前检查）：
  > "你即将提交的候选，目前的证据都是从异常时段数据里来的。但有些错误其实是环境的长期常态，不是当前故障的产物。在最终提交前请反问一次：你看到的这些错误，没有故障时是不是也会出现？如果是，你的候选可能只是常态噪声的承担者，不是真正的故障源。"

### 次问（M2 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你的证据都来自异常时段查询，可以顺带想一下：这些信号在正常时段是不是也会出现？"

**次问触发条件**：M2 作为次问被加入复合干预，**仅当** L2 对 M2 给出 `match_score ≥ 0.7`（即 L2 真的检测到 baseline 类 intent 全程为 0、abnormal-only intent ≥ 5、候选证据从未对照 normal）。如果 agent 已经做过 baseline_contrast，L2 会给 M2 低分，那么即使主问卡片"建议"M2 作为常见搭配，**也不强行加 M2 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 用 intent 类别计数 + draft_root_causes + agent 自己累积的 findings 的"是否查过 normal"标记，**不查询** chronic_noise_carriers / parquet 算出来的 chronic 真值）
- [x] **Trigger 不含 SQL 字符串**（用 intent 抽象类别 `baseline_collect` / `baseline_contrast` / `error_log_overview` 等）
- [x] **Trigger 不含具体服务名**（`candidate_RC` 是变量；evidence 累积也是变量）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（无 ts-rabbitmq / ts-food-service 等；只用"你的候选"）
- [x] **Intervention 不含错误消息字串**（无 UnknownHostException / AmqpConnectException 等；用"长期存在的报错"、"环境的长期常态"等通用描述）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（只说"常态噪声的承担者"——这是相对中性的拟人化表达，不暗示拓扑方向）
- [x] **Intervention 用反问 + 多种可能性句式**（"有没有可能在没有故障的时候本来也是这样"、"是新出现的，还是一直都在"——开放对比，不指定答案）
- [x] **agent 可基于自身已做的动作自我修正**（"你查了不少异常时段数据"引用了 agent 实际的 query 行为）

**全部 9/9 ✓ → M2 卡片符合 v4 元认知设计原则**

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✓ 主问候选 | 24.8% U2，主要 framework 之一 |
| thinkdepthai (claude-sonnet-4.6) | ✓ 主问候选 | 14.0% U2 |
| aiq (qwen3.5-plus) | ✓ 主问候选 | 15.0% U2 |
| claudecode (qwen3.5-plus) | ✓ 主问候选 | 34.3% U2，**最高发**；中期检查时优先 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

| Framework | failure case 总数 | U2 占比 | M2 主问命中估计 | M2 翻盘期望（按 v3 B3 维度 100% 翻盘类比，保守按 50%）|
|---|---:|---:|---:|---:|
| thinkdepthai-qwen3.5-plus | 105 | 24.8% | ~22 | **~11 case 翻盘** |
| thinkdepthai-claude-sonnet-4.6 | 50 | 14.0% | ~7 | ~3 case 翻盘 |
| aiq-qwen3.5-plus | 113 | 15.0% | ~17 | ~8 case 翻盘 |
| claudecode-qwen3.5-plus | 102 | 34.3% | ~32 | **~16 case 翻盘** |

**为什么 M2 翻盘率估计较高（50%）**：v3 实测 B3 (Missing Baseline) 维度 14 case 命中全部翻盘（100%），M2 是 B3 在新 taxonomy 下的对应项，预期相近。但 M2 的触发条件比 B3 更严格（要求 commit 时刻而非中间触发），实际命中数会更少但 precision 更高。

**Phase 8 离线重放将给出精确数值。**

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **M6 (Baseline-Contrast Reflex)** | M6 是 PD-pure 检测（baseline_contrast intent = 0 即触发），M2 是 R 层（baseline 缺失 + commit 候选与噪声相关） | M6 触发条件比 M2 宽（不要求 commit 时刻，不要求候选与噪声相关）。**L2 同时命中时 M2 优先作为主问，M6 退为次问** |
| **M1 (Loudness-Anchor)** | 都可能在 agent 把 ranking top 当 RC 时触发 | M1 关注"启发式选了 ranking top"，M2 关注"对比 normal/abnormal"。L2 同时命中时按当前 trajectory 哪个失败模式更显著决定主问（如 ranking 类 intent ≥ baseline 类 intent 缺口 → M1 主；如 baseline 类 intent 缺口 ≥ ranking → M2 主）|
| **M8 (Hypothesis-Counterfactual)** | M8 关注"候选未被独立隔离" | 与 M2 在 commit 前都触发，但维度不同：M2 关注证据时间维度（normal vs abnormal），M8 关注证据隔离维度（独立 isolation 检验）。可同时命中，L2 选最 critical 作主问 |

---

## 实施备注

- **关键依赖**：L1 intent classifier 必须能识别 `baseline_collect` 和 `baseline_contrast` 两类意图。当前 19 类意图分类已包含这两类，准确率由 opus-4.7 保证（v4 原则 5 LLM 选型）
- **state.findings_about[] 数据结构**：需要在 L1 之外维护一个 per-candidate 的"normal-window 检验计数"。实施时由 L1 副作用更新（每次 intent 分类完成后顺便记录该 SQL 是否对当前 draft RC 做了 normal-window 查询）
- **离线重放验证**：在 372 已标注 case 上跑 trigger，统计 (precision, recall) 相对于 U2 标注

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-1 阶段输出） |
