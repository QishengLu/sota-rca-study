# A5 — Anti-Flipflop Reflex（aiq-特定，GT 脱敏版）

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-6 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | aiq 失败 case 中数量 |
|---|---|---|---:|
| **R 层（aiq-specific）** | `aiq.R_correct_then_reversed` | cross-stage 中 agent 曾选中一个候选、后来又否定、再后来又选回（或换成第三个）— **flipflop 模式** | **13 / 113** |
| **aiq v1 theme** | **T5 ReflectionReversesCorrect** | 原叙述聚焦"stage_0 correct → refine 推翻" | 13 case |

**v1 原叙述是 GT-entangled**（提到"correct"），A5 必须**GT 脱敏**——不依赖"哪个候选是对的"，只检测"多次切换 + 至少一次重返"的行为模式。

**对应失败 case 数**（A5 主问触发的初步估计）：
- 严格触发：cross-stage 候选切换 ≥ 2 次，且**至少一次**切换的目标是**更早 stage 曾经宣布过又被否过的**候选
- **A5 主问的目标 case 池：~10-13 case**（T5 的完整集合）

---

## Cognitive vocabulary

**这种认知模式是什么样**：

在 aiq 的多 stage 推理里，agent 的候选可能经历：
```
stage_0 选 S_A (terminator) → reflect 第 1 轮推翻选 S_B → reflect 第 2 轮又选回 S_A (或选 S_C)
                                                        ↑
                                                   这里就是 flipflop
```

flipflop 指**候选在多个 stage 间来回震荡**。其中特别危险的模式是：agent 曾经在某 stage 认真推过一个候选（"the evidence strongly suggests S_A"），下一 stage 看到一些反面信号（常见形态：S_A 的 HTTP 200 + 无错误日志，被 agent 误读为 "healthy"）就推翻选了别的，再下一 stage 又莫名其妙选回 S_A。

这种震荡通常意味着：
- agent 没有稳定的决策基准，在 reflect prompt 的引导下随波逐流
- agent 对 silent-signal 的误读（T4 SilentSignalMissed 常与 T5 共生）
- compress_to_graph 在几个候选间重新排序

A5 的失败后果：最终 commit 的候选**既不是有最多证据的那个，也不是 agent 认真推演过的那个**——是震荡里的"最后一站"。这比单纯"被 loudness 锚定"（M1）或"被 baseline 噪声锚定"（M2）更隐蔽，因为 agent 表面上在"不断更新信念"。

**反思的认知动作**：让 agent 意识到**自己在候选间震荡过**，反问"你已经否过这个候选又选回了它——你否它的时候和你再选它的时候，各自的依据是什么？这两次判断能同时成立吗？"——逼 agent 直面自己判断的不一致。

---

## Trigger abstract（运行时可观察）

```pseudo
trigger_A5(state) :=
  state.check_point == "conclusion"
  AND LET stage_terminators = [
         state.stage_0_terminator.root_cause_service,
         state.stage_1_refine_terminator.root_cause_service,   // 可能为 None 若 refine 没 terminator
         state.stage_2_refine_terminator.root_cause_service,
         state.compress_rc   // 最后一次 compress 输出
      ]  // 过滤掉 None 值
      LET switches = COUNT_ADJACENT_CHANGES(stage_terminators)
          // 相邻元素不同计 1 次切换；例如 [A, B, A] = 2 次切换

      LET returned_candidates = SET(
          c FOR i IN range(2, len(stage_terminators))
          WHERE c = stage_terminators[i]
                AND c IN stage_terminators[:i-1]   // 在更早 stage 出现过
                AND stage_terminators[i-1] != c    // 相邻不同（即"重返"）
      )

      IN
        switches >= 2
        AND LENGTH(returned_candidates) >= 1
```

**辅助约束**：
- 若 stage_terminators 中只有 1-2 个非 None 元素 → A5 不触发（没有足够 stage 数据判 flipflop）
- 若 switches ≥ 2 但没有"重返"（比如 A→B→C 三次都不同）→ A5 不触发，可能是 A2 的场景
- 若 compress_rc 与最后一个 refine_terminator 相同 → 只算 stage 切换，不额外计 compress 漂移

**触发场景示例**：
- stage_0 terminator = S_A，reflect_iter_1 terminator = S_B，reflect_iter_2 terminator = S_A（回到 S_A）→ switches=2, returned={S_A} → 命中
- stage_0 = S_A，reflect_iter_1 = S_B，reflect_iter_2 = S_C，compress = S_B（回到 S_B）→ switches=3, returned={S_B} → 命中
- stage_0 = S_A，reflect_iter_1 = S_A，reflect_iter_2 = S_A，compress = S_A → switches=0 → 不触发

---

## Intervention pattern

### 主问（A5 作为 most_critical 时）

> **你已经在几个候选之间换过好几次——其中有一个你曾经否过，现在又选回了它。你能不能把自己放到那两个时刻：否它的时候你看到的是什么信号？再选它的时候你看到的又是什么？这两次判断依据不同，说明其中有一次可能是误判——你现在的选择是基于新证据推翻了上次的否定，还是只是这一轮的信号把你拉回来了？**

**变体**：
- 变体 A（重返同一候选）：
  > "你刚选的这个候选，你在更早的阶段曾经否过它、又换到别的候选。现在你选回它——你能不能反问一次：当时否它是因为什么观察？现在选回它又基于什么新证据？如果这两次观察都是有道理的，为什么你的判断会来回变？"
- 变体 B（多次切换但重返已否候选）：
  > "你的候选在几个服务之间来回切换过，其中有一个你否过又选回了。来回切换通常意味着两种可能：要么你在逐步收敛、反复验证；要么你被不同阶段的 prompt 引导拉着走。在最终提交前能不能静下来审一次：每次切换的依据是什么？哪一次是最站得住脚的？"

### 次问（A5 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你的候选在多个阶段间来回切换过（有一次是重返之前否过的选择），可以顺带反思一下：每次判断的依据一致吗？"

**次问触发条件**：A5 作为次问被加入复合干预，**仅当** L2 对 A5 给出 `match_score ≥ 0.7`（即确实有 ≥ 2 次切换 + 至少 1 次重返）。若候选稳定或只有 1 次切换无重返，L2 给 A5 低分，**不加 A5 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 只看 agent 自己的 stage terminator 序列 + compress_rc，**不查询** gt_services；原 v1 叙述提到"correct" 已被 A5 去掉，trigger 不关心哪个候选是对的）
- [x] **Trigger 不含 SQL 字符串**（用 stage 切换序列 + 集合运算）
- [x] **Trigger 不含具体服务名**（stage_terminators 是变量列表）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（用"这个候选"、"那两个时刻"指代）
- [x] **Intervention 不含错误消息字串**（无）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（"切换"、"重返"、"收敛" 是决策过程动作，不是拓扑方向）
- [x] **Intervention 用反问 + 多种可能性句式**（"来回切换通常意味着两种可能：要么在逐步收敛、反复验证；要么被不同 prompt 拉着走"——经典两种可能并列；"这两次判断依据不同，说明其中有一次可能是误判"——开放可能性）
- [x] **agent 可基于自身已做的动作自我修正**（"你在更早的阶段否过它"、"现在你选回它"——引用 agent 自己的 stage 决策历史）

**全部 9/9 ✓ → A5 卡片符合 v4 元认知设计原则**

**重要审核点**：

1. **GT 脱敏成功？** ✓ 原 v1 T5 叙述是 "Reflection Reverses **Correct**"（依赖 GT 判断哪个是 correct）；A5 完全不用"correct"概念，只检测行为模式"切换 + 重返"。agent 重返的候选**可能是对的也可能是错的**——A5 只让 agent 反思决策一致性，不告诉答案
2. **"否它的时候" / "选回它的时候" 是否过于具体？** 不算——这是引用 agent 自己的 stage 决策历史，是元认知自检；**没有**泄露任何 GT 信息。agent 可以诚实回答"我否它是因为看到 HTTP 200，再选回它是因为看到 JVM 错误"——这种自检本身就是纠错

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✗ | 无 stage 概念；候选切换只存在 trajectory 内部，不能结构化检测 flipflop |
| thinkdepthai (claude-sonnet-4.6) | ✗ | 同上 |
| aiq (qwen3.5-plus) | ✓ 主问候选 | 5 阶段 + 2 次 reflect 提供天然 stage 序列；是 aiq v1 T5 (11.5%) 独有模式 |
| claudecode (qwen3.5-plus) | ✗ | 无 stage 概念 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

| Framework | failure case 总数 | A5 触发估计 | A5 翻盘期望（~40%）|
|---|---:|---:|---:|
| aiq-qwen3.5-plus | 113 | ~10-13 | **~5 case 翻盘** |

**总翻盘期望**：~5 case 跨 4 framework（仅 aiq）。

**为什么翻盘率 40%**：A5 主问让 agent 直面决策不一致，若 agent 回答"我否它是因为看到 HTTP 200 (silent) 以为 healthy，再选它是因为看到 JVM OOM"——agent 很可能意识到"HTTP 200 不代表 healthy"（M5 的认知），从而选择更合理的候选。若 agent 给不出两次决策的可区分依据，默认选"证据更充分的那次"通常是正确方向

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **A2 (Refinement-Without-New-Probe)** | A2 需要切换无新 probe；A5 需要 ≥2 次切换且重返 | 可同时命中；**A5 优先**（flipflop 比单次无依据切换更严重；A5 主 + A2 次是常见组合）|
| **A3 (Compress-Drift Self-check)** | A3 需要最终 compress vs terminator 不一致；A5 可能包含 A3（compress 相当于一次切换） | A5 语义更广：若 compress 切换恰好重返早期候选，A5 命中；若 compress 切换到全新候选，A3 命中。L2 按切换模式区分 |
| **M5 (Silence ≠ Health)** | A5 触发时常伴 M5——agent 否掉 GT 候选往往是因把 silence 读为 healthy | 同时命中时**A5 主 + M5 次**（A5 覆盖行为模式，M5 补上认知原因）|
| **M10 (Premature Commitment)** | 互斥：M10 要求 round 短；A5 要求多 stage 切换（必然 round 多）| 互斥，不会同时命中 |

---

## 实施备注

- **关键依赖**：
  - 中间件必须正确提取每个 stage 的 terminator：stage_0_main（data_research 末尾）、reflect_iter_1、reflect_iter_2、compress 输出
  - 注意 aiq 的 refine sub-loop 可能不显式出 terminator（最后一轮 sub-loop 可能仍在 tool_calls）；此时该 stage 的 terminator 记为 None，不参与切换计数
- **"重返" 的判定**：严格字符串相等；不做模糊匹配（Jaro-Winkler 不用）。若 stage_0 和 reflect_iter_2 的候选名是"名称相近但字面不同"的两个服务（例如复数 vs 单数、不同后缀），不算重返——这种场景由 M4 (SiblingTwin) 覆盖
- **compress_rc 多根因的处理**：只看 compress 输出的第一位 root cause，与 stage terminator 比较
- **A5 与 A2 的区分**：A2 只要"切换 + 无 probe" 就命中（可能只 1 次切换）；A5 要求 "≥2 次切换 + 至少 1 次重返"。A5 是 A2 的严格子集，但触发独立
- **离线重放验证**：在 113 aiq failed case 上跑 A5 trigger，统计 precision/recall 相对于 v1 T5 标注。预期 precision ≥ 0.85（结构化 trigger，假阳性率极低）

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-6 阶段输出）；GT 脱敏版（去掉 v1 T5 的 "Correct" 维度）|
