# M1 — Loudness-Anchor Self-check

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-1 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | 372 case 中数量 |
|---|---|---|---:|
| **R 层** | `U1_LoudnessAnchorOverSilentVictim` | agent 把 error count / latency / restart 排名最高的服务当 RC，但真正 RC 是 silent 的 | **140** |
| **PD 层** | `PD_NoFaultLayerMetricProbe` | agent 没查过与故障层匹配的运行时指标（jvm/k8s/db/网络）就 commit | **188**（涵盖更广）|
| **D 层** | D1 (VictimSilentOnPath) — **作为元认知"多种可能性"的素材**，非独立触发 | GT 服务在该数据集中 silent | (背景) |

**对应失败 case 数（M1 主问触发的初步估计）**：
- 严格交集 (U1 ∧ PD_NoFaultLayerMetricProbe)：~85 case（后续 Phase 8 离线重放精算）
- 宽松命中 (U1 单独)：140 case
- M1 主问的目标 case 池：U1 ∪ (PD_NoFaultLayerMetricProbe ∧ "agent 在 ranking 后短时间内 commit") — 估计 130-160 case

**Per-framework 分布**（来自 unified_R.md）：
- aiq-qwen3.5-plus: 55 / 113 = 48.7%
- claudecode-qwen3.5-plus: 29 / 102 = 28.4%
- thinkdepthai-claude-sonnet-4.6: 12 / 50 = 24.0%
- thinkdepthai-qwen3.5-plus: 44 / 105 = 41.9%

---

## Cognitive vocabulary

**这种认知模式是什么样**：

agent 在调查过程中很自然地做"按错误数/延迟/重启次数排序"这类排名查询，然后**把排名最高的服务当作根因候选**。这是一个 fast & frugal 启发式（"loudest = source"），在很多场景下确实能直接命中。但它的失败模式是：当真正的故障源是一个"silent victim"（死掉的 pod、卡住的 JVM、被网络隔离的服务）时，silent service 不会出现在 error count 排名前列，反而是它的上下游或同层会因连锁反应产生大量错误日志，agent 就被吸引到这些响亮的代位上。

**反思的认知动作**：commit 之前主动做一次"反向假设" — "**如果不是这个候选，会是什么？**"——这一步迫使 agent 跳出 ranking 视角，去考虑那些没出现在 ranking 顶部的可能性，包括"完全没在 ranking 里出现的服务"。

---

## Trigger abstract（运行时可观察）

```pseudo
// 谓词都来自 v4_principles.md 原则 2 的"允许使用"清单
//
// 上下文：在中期检查或结论前检查触发时调用此谓词

trigger_M1(state) :=
  (LET about_to_commit  = state.is_at_check_point AND state.draft_root_causes != []
   LET recent_intents   = state.intent_log[ last_K_rounds = 8 ]
   LET ranking_intents  = COUNT(recent_intents WHERE intent IN
                            { 'error_rate_scan', 'latency_ranking',
                              'throughput_compare', 'metric_scan' })
   LET candidate_RC     = state.draft_root_causes[0]   // 当前最可能 commit 的候选
   LET ranking_top_rows = state.last_ranking_query_results[:3]   // 最近 ranking SQL 的 top-3 行
   IN
     about_to_commit
     AND ranking_intents >= 2
     AND candidate_RC IN ranking_top_rows)
```

**触发场景示例**：
- thinkdepthai：agent 在 round 22 跑了 `error_rate_scan`，top-1 = "ts-X"，agent reasoning 段表达 "I'm leaning toward ts-X as root cause"，draft graph 已含 ts-X
- aiq：stage_0 末尾 terminator candidate 是某个出现在 stage_0 内 ranking 查询 top-2 的服务
- claudecode：agent 即将通过 compress 输出 RC，中期检查发现该 RC 来自 trajectory 中的 latency 排名

---

## Intervention pattern

按 v4 原则 4 的「1 主问 + 2~3 次问」复合结构生成：

### 主问（M1 作为 most_critical 时）— 强调主问，承担主要反思责任

> **你最近几轮一直在按错误数/延迟/排名查询数据，准备 commit 排名靠前的那个候选。排名靠前不一定就是故障来源——也可能是因为别的原因放大了它的错误。你能在确认前先反过来问一下：如果不是它，会是什么？哪些服务可能根本没出现在你的排名里？**

**变体**（L3 按上下文选其一）：
- 变体 A（中期检查，agent 还在调查阶段）：
  > "你最近几轮在做排名类查询，看上去要 commit 排名最高的那个。排名靠前不一定就是问题来源——也可能是因为别的原因放大了它的错误。在你确认之前，能不能反过来问一下：'如果不是这个，会是什么？我有没有可能漏看了某些根本没出现在排名顶部的服务？'"
- 变体 B（结论前检查，agent 即将提交）：
  > "你即将 commit 这个候选，它出现在了你之前的排名查询的顶部。在最终提交前请先做一次反向检查：这个候选的'排名高'是因为它本身故障，还是因为它和真正出问题的服务有关系导致它的错误也被放大？你能列出至少一个'被排名跳过的'候选并说为什么不选它吗？"

### 次问（M1 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你这次的候选是从排名查询顶部选的，可以顺带反问一下：排名靠前是因为它本身的问题，还是被别的因素放大了？"

**次问触发条件**：M1 作为次问被加入复合干预，**仅当** L2 对 M1 给出 `match_score ≥ 0.7`（即 L2 真的检测到当前 trajectory 满足 M1 的 trigger 条件）。如果 L2 给 M1 的分数 < 0.7，即使主问的卡片建议"M1 常常作为次问搭配"，**也不强行加 M1 次问**——这是 v4 原则 4 "次问不强行凑数" 的硬要求。

---

## 自检清单 — 为什么这是元认知

按 v4 原则审核（每条都要打勾才能通过 D-1 审核）：

- [x] **Trigger 不引用 GT 字段**（trigger 用 intent classifier 输出 + state.draft_root_causes + 最近 ranking SQL 结果，**不查询** fault_category / gt_services / chronic_noise_carriers）
- [x] **Trigger 不含 SQL 字符串**（用 intent 抽象类别 `error_rate_scan` / `latency_ranking` 等，不写 `SELECT service_name, COUNT(*)...`）
- [x] **Trigger 不含具体服务名**（`candidate_RC` 是变量，`ranking_top_rows` 也是变量）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无任何 `SELECT`/`FROM`/`WHERE`）
- [x] **Intervention 不含具体服务名**（无 `ts-rabbitmq` / `ts-food-service` 等，只用 "你的候选"、"排名靠前的那个"）
- [x] **Intervention 不含错误消息字串**（无 `UnknownHostException` 等）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（只用 "如果不是它"、"哪些服务"、"和真正出问题的服务有关系"）
- [x] **Intervention 用反问 + 多种可能性句式**（"也可能是因为别的原因放大了它的错误"、"如果不是它，会是什么"——开放问，不指定答案）
- [x] **agent 可基于自身已做的动作自我修正**（"你最近几轮一直在按错误数/延迟/排名查询" 引用了 agent 已做的 ranking 行为）

**全部 9/9 ✓ → M1 卡片符合 v4 元认知设计原则**

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✓ 主问候选 | 失败 case 中 41.9% 是 U1，最高发；中期检查时优先 |
| thinkdepthai (claude-sonnet-4.6) | ✓ 主问候选 | 失败 case 中 24.0% 是 U1 |
| aiq (qwen3.5-plus) | ✓ 主问候选 | 失败 case 中 48.7% 是 U1，最高发；介入点在 stage_0 末尾（中期）+ stage_2 reflect 后（结论前）|
| claudecode (qwen3.5-plus) | ✓ 主问候选 | 失败 case 中 28.4% 是 U1 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

基于 v3 实测数据外推（v3 在 thinkdepthai-qwen 105 case 上整体翻盘 49 case，其中 B3+B5+M1+M2 维度共贡献 26 个），M1 单独的预期翻盘：

| Framework | failure case 总数 | U1 占比 | M1 主问命中估计 | M1 翻盘期望（按 v3 类比 30% 的 M1 命中 → wrong→correct）|
|---|---:|---:|---:|---:|
| thinkdepthai-qwen3.5-plus | 105 | 41.9% | ~30 | **~9 case 翻盘** |
| thinkdepthai-claude-sonnet-4.6 | 50 | 24.0% | ~10 | ~3 case 翻盘 |
| aiq-qwen3.5-plus | 113 | 48.7% | ~40 | ~12 case 翻盘 |
| claudecode-qwen3.5-plus | 102 | 28.4% | ~22 | ~7 case 翻盘 |

**Phase 8 离线重放将给出精确数值。** 这里的估计基于"M1 主问命中 case 中 30% 翻盘"——v3 实测 B3 维度命中 14 case 全部翻盘（100%），B1 命中 14 全翻（100%），所以 30% 是保守下界。

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **M8 (Hypothesis-Counterfactual)** | 都关注 commit 前对候选的反向检查 | M1 偏 R 层（loudness 启发式批判，问"为什么是它"），M8 偏 PD 层（counterfactual 隔离漏做，问"抠掉它会怎样"）。**L2 同时命中时 M1 优先作为主问，M8 退为次问** |
| **M7 (Layer-Coverage Reflex)** | M1 触发时**经常**伴随 PD_NoFaultLayerMetricProbe 也命中（M1 来源就是 U1+PD3 的交集） | **L2 主+次结构**：主问 M1（reasoning 反思）；如果 L2 也给 M7 ≥ 0.7（即真的检测到运行时层 intent 缺失），加 M7 次问；如果 L2 给 M7 < 0.7（agent 已查过运行时层），**不加 M7 次问**——这是 v4 原则 4 的硬要求 |
| **M9 (Investigation Stagnation)** | M1 触发时 agent 可能也在重复 ranking 查询 | M1 关注"已经选好的候选"，M9 关注"还在重复探查"。两者目标 case 重叠少（agent 已 commit-ready vs agent 还在转圈），冲突低 |

---

## 实施备注（不在 D-1 范围）

- **L2 检测实现**：opus-4.7 prompt 接收 `recent_intents + draft_root_causes + ranking_top_rows`，判定 `M1_score ∈ [0, 1]`。M1_score ≥ 0.7 计入主问候选。
- **L3 干预生成**：opus-4.7 prompt 接收 M1 卡片的主问模板 + agent 实际状态变量（"最近 K 轮做了什么 ranking 查询"），生成具体 prompt。
- **离线重放验证**：在 372 已标注 case 上跑 trigger，统计 (precision, recall) 相对于 U1 标注。目标 precision ≥ 0.6, recall ≥ 0.5（plan Part E 验证要素 1）。

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-1 阶段输出） |
