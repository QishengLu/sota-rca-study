# M10 — Premature Commitment

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-4 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | 372 case 中数量 |
|---|---|---|---:|
| **PD 层** | `PD_LateExplorationDegenerate` 反向 — 原 PD 关注"长跑跑偏"，M10 关注它的反面"过早收敛" | (反向引用) |
| **R 层** | (相关) `aiq.R_correct_then_reversed` — 在多 stage 框架里，对应"早期猜对了又翻车"的失败模式 | 13 (aiq) |
| **D 层** | (无关) | — |

**v3 实测背景**：v3 文档明确指出 105 failed case 中 **44 case (42%) 在 query 37 之前已经 conclusion**——v3 的中期检查点 [37, 44] 完全错过这部分。M10 是为这 42% "过早收敛" 设计的专项维度。

**对应失败 case 数（M10 主问触发的初步估计）**：
- v3 实测：~44 case 在 query 37 前 conclusion (thinkdepthai-qwen 上)
- M10 主问的目标 case 池：~80-100 case 跨 4 framework

**Per-framework 估计**：
- thinkdepthai-qwen3.5-plus: ~44 case（v3 实测）
- thinkdepthai-claude-sonnet-4.6: ~10 case（sonnet 平均 round 较高，过早收敛比例低）
- aiq-qwen3.5-plus: ~10 case（aiq stage 强制 3 阶段，过早收敛被 stage 结构吸收）
- claudecode-qwen3.5-plus: ~25 case（claudecode Bash 调用平均次数偏低）

---

## Cognitive vocabulary

**这种认知模式是什么样**：

agent 在调查很短时间内（远少于该 framework 同类任务的常见调查长度）就准备 commit RC。**这不一定是错的**——简单 case 确实可能短就足够。但失败模式是：agent 被一个早期信号锚住，没充分探查就 commit，结果错过了真正的故障源。典型场景：
- 第一个 SQL 看到某服务有几条 ERROR 日志，就 commit 它
- 浅层 trace 看到一个延迟尖峰，没深挖就 commit 上面的服务
- aiq stage_0 早期得到一个看起来 plausible 的 candidate，stage_1/stage_2 反思都没翻案（aiq.R_correct_then_reversed 的反面 — "early commit and never revised"）

**反思的认知动作**：让 agent 意识到"**你的调查比同类任务短很多，但你已经准备 commit**"，反问"**真的证据充分了，还是被早期信号锚住了？**"——给 agent 一个"再多想一步" 的机会。

**M10 与 M9 的区别**：M9 是"调查很多但全在打转"，M10 是"调查很少就要 commit"。两者互斥（不会同时触发）。

---

## Trigger abstract（运行时可观察）

```pseudo
trigger_M10(state, framework_priors) :=
  (LET about_to_commit = state.is_at_check_point AND state.draft_root_causes != []
   LET current_query_count = state.query_count   // 当前 case 的累计 SQL/tool call 数
   LET P25_threshold = framework_priors.failed_case_query_count_P25
                       // 该 framework 历史 failed case 的 query count P25
                       // ⚠ framework-级先验，不是当前 case 的 GT
   LET runtime_layer_intents = COUNT(state.intent_log WHERE intent IN
                                  { 'jvm_state', 'container_resource',
                                    'k8s_state', 'db_state', 'network_layer' })
   IN
     about_to_commit
     AND current_query_count < P25_threshold
     AND runtime_layer_intents == 0)
```

**关键依据 — `framework_priors.failed_case_query_count_P25`**：
- 该值是 framework 级行为先验（v4_principles.md 原则 2 已列入"允许使用"清单）
- 计算方法：从该 framework 的历史 failed case 池中算 query count P25
- 例：v3 实测 thinkdepthai-qwen failed case 中 42% 在 query 37 之前 conclusion → P25 大约在 25-30 之间，M10 trigger 用这个值
- 这个先验不是当前 case 的 GT（不知道当前 case 的对错），只是历史观测的统计

**触发场景示例**：
- thinkdepthai-qwen：query count = 18，准备 commit，但只查了应用层数据
- aiq：stage_0 第 8 round 就发出 terminator，stage_0 内 query count 远低于该 stage 的 P25
- claudecode：Bash tool call count = 12，准备 compress 提交，但没碰过基础设施层

---

## Intervention pattern

### 主问（M10 作为 most_critical 时）

> **你的调查到现在为止比同类任务的常见长度短很多，但你已经准备 commit 候选了。这有两种可能：要么这个 case 真的很简单证据已经充分，要么你被一个早期信号锚住了跳过了一些可能性。在 commit 之前能不能反问一下：你已有的证据真的能排除其他可能候选吗？或者还有哪些方向你还没探过？**

**变体**：
- 变体 A（中期检查，agent 调查很短就 about_to_commit）：
  > "你的调查时间相对来说比较短，但你已经倾向某个候选了。能不能反问一下：是这个 case 真的简单证据充分了，还是你被早期看到的信号锚住了，没充分探其他可能？"
- 变体 B（结论前检查，agent 即将提交但 query count 远低于 P25）：
  > "你即将提交，但你的整个调查长度比同类任务的常见长度短很多。在最终提交前请反问一次：这个 case 真的简单到你做的查询就够了，还是你跳过了一些值得探的方向？补一些查询能不能让你更确信？"

### 次问（M10 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你的调查长度相对短，可以顺带反问一下：证据真的充分了，还是被早期信号锚住了？"

**次问触发条件**：M10 作为次问被加入复合干预，**仅当** L2 对 M10 给出 `match_score ≥ 0.7`（即 about_to_commit + query count < P25 + 运行时层 intent = 0）。如果 query count 已超过 P25 或 agent 已查过运行时层，L2 给 M10 低分，**不加 M10 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 用 query_count + framework P25 先验 + intent 类别计数；framework P25 是历史行为统计，不是当前 case 的 GT）
- [x] **Trigger 不含 SQL 字符串**（用 intent 抽象类别 + count）
- [x] **Trigger 不含具体服务名**（trigger 是全局 query count + intent 类别计数）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（用"候选"、"其他可能候选"指代）
- [x] **Intervention 不含错误消息字串**（无）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（"被锚住"是认知词，不是拓扑方向；"其他方向" 指 intent / candidate 类别）
- [x] **Intervention 用反问 + 多种可能性句式**（"两种可能：要么 case 真简单要么被早期信号锚住"——经典两种可能；"补一些查询能不能让你更确信"——开放邀请）
- [x] **agent 可基于自身已做的动作自我修正**（"你的调查到现在为止比同类任务的常见长度短很多"——引用 agent 累计行为，对照 framework 先验）

**全部 9/9 ✓ → M10 卡片符合 v4 元认知设计原则**

**审核风险点 — framework 先验是否算 GT？**

v4 原则 2 明确列入"允许使用"清单：

> **Framework-级行为先验**：该 framework 历史 success / failure case 的 round count P25/P50/P75 — ❌ 不需要 GT（统计是先验，不是当前 case 的 GT）

理由：
- P25 是历史统计，不依赖当前 case 的对错标注
- 即使 P25 计算时用了 success vs failed 的对照，其值只是"该 framework 在这个数据集上的典型行为长度"
- 把它给 agent 看 = "你比同类任务短" — 这是行为对照，不是答案暗示
- 如果换数据集，P25 重算即可；不绑定 RCABench 特有领域知识

**判定**：通过。但若审核认为"failed case P25" 的计算依赖 GT 标注（要先知道哪些 case 是 failed），可改为**全 case query count P25**（success + failed 混合）——损失一定区分度但完全脱敏。建议保留 failed case P25 用法。

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✓ 主问候选 | v3 实测 42% case 过早收敛，**最高发** |
| thinkdepthai (claude-sonnet-4.6) | ✓ 主问候选 | 触发率较低（sonnet 平均 round 较高），但仍可启用 |
| aiq (qwen3.5-plus) | △ 选择性启用 | aiq 的 stage 结构强制至少 3 个 stage，过早收敛被结构吸收；M10 trigger 改在 stage_0 内部 query count 上判定（D-6 阶段细化）|
| claudecode (qwen3.5-plus) | ✓ 主问候选 | claudecode 平均 Bash count 较低，触发率中等 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

| Framework | failure case 总数 | M10 触发估计 | M10 翻盘期望（按 v3 conclusion check 救回模式类比 ~40%）|
|---|---:|---:|---:|
| thinkdepthai-qwen3.5-plus | 105 | ~44（v3 实测过早收敛）| **~17 case 翻盘** |
| thinkdepthai-claude-sonnet-4.6 | 50 | ~10 | ~4 case 翻盘 |
| aiq-qwen3.5-plus | 113 | ~10（stage_0 内部触发）| ~4 case 翻盘 |
| claudecode-qwen3.5-plus | 102 | ~25 | ~10 case 翻盘 |

**总翻盘期望**：~35 case 跨 4 framework。

**v3 实测对照**：v3 conclusion check 救回 21 case (silent process + conclusion=back_to_tools 的 9 + rewrite 的 12)。M10 是 v4 把这 21 case 的"过早收敛"专项化的对应维度，目标翻盘超过 v3。

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **M9 (Investigation Stagnation)** | **互斥**：M9 要求最近 K round 重复（必然 round 多），M10 要求 round 短 | 互斥，不会同时命中 |
| **M7 (Layer-Coverage Reflex)** | M10 触发时通常运行时层 intent = 0，所以 M7 也命中 | M10 关注调查长度过短，M7 关注层缺失。**L2 主+次结构典型**：M10 主（行为统计）+ M7 次（具体行动方向）|
| **M6 (Baseline-Contrast)** | M10 触发时通常 baseline_contrast 也缺失（agent 还没来得及做） | M6 关注时间维度，M10 关注长度维度。可同时命中 |
| **M1 (Loudness-Anchor)** | M10 触发场景里 candidate 经常是早期 ranking 看到的服务 | M1 关注 commit 时点 ranking 启发式，M10 关注调查长度。可同时命中，按 L2 score 选主 |

---

## 实施备注

- **关键依赖**：
  - `framework_priors.failed_case_query_count_P25` 需要每个 framework 单独算（D-5/D-6/D-7 阶段在适配层文档里给出具体值）
  - 当前 v4 原则 2 已允许使用 framework 级行为先验，但具体 P25 值的更新机制（每次新跑评测后是否重新计算）由 D-5+ 决定
- **trigger 阈值校准**：
  - 是否再加一个"hard floor"避免极短 case 误触？例如 query_count < 5 直接不触发（agent 还没查任何东西时不需要提醒"过早收敛"）
  - 当前 trigger 隐含 query_count >= 1（about_to_commit 必须有 draft_root_causes），但仍建议 D-5 加 hard floor（如 query_count >= 5）
- **离线重放验证**：在 372 已标注 case 上跑 trigger，统计 (precision, recall) 相对于"过早收敛" 的人工标注或 v3 实测的 44 case "qpf<37 提前收敛"

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-4 阶段输出）|
