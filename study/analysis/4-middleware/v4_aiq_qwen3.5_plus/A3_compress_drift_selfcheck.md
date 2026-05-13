# A3 — Compress-Drift Self-check（aiq-特定）

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-6 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | aiq 失败 case 中数量 |
|---|---|---|---:|
| **PD 层（aiq-specific）** | `aiq.PD_CompressOverwritesTerminator` | compress_to_graph 节点产出的 `root_causes` 与最后 stage terminator 宣布的候选**不一致** | (背景数量) |
| **R 层（aiq-specific）** | `aiq.R_compress_drift` | 同上但从 R 层视角：压缩 LLM 在没有新证据时"帮忙整理"了一个不同的根因 | (相关) |
| **aiq v1 theme** | **T8 CompressOverwritesTerminator** | aiq-架构独有失败模式，v1 冻结分析 | **8 / 113** |

**对应失败 case 数**（A3 主问触发的初步估计）：
- 严格触发：最后 stage（reflect 第 2 轮或 stage_0 无 reflect 的情况）terminator 候选 ≠ compress 输出的 graph.root_causes[0]
- 加上 terminator 候选**不在** graph.root_causes 列表里的 case：~16 个
- **A3 主问的目标 case 池：~12-16 case**

**为什么 v1 T8 只 8 case 但 A3 覆盖面更大**：
- T8 是"精准识别"——完全不同候选；A3 更宽口径——包括"候选在 root_causes 但不是第一位" / "候选不在 root_causes"
- aiq 的 compress_to_graph 每次 reflect 循环都调（全程 ≥3 次），最后一次 compress 漂移最容易发生

---

## Cognitive vocabulary

**这种认知模式是什么样**：

aiq 的 reflect_on_graph 节点里，每次 refine sub-loop 结束后，`compress_to_graph(accumulated_findings, compress_sp, compress_up)` 把累积的 findings 文本压缩成结构化 CausalGraph JSON（nodes + edges + root_causes）。compress 的 prompt 指令是"提取最可能的根因"——但在 aiq 的反思型架构里，refine sub-loop 的 terminator 已经**明确宣布了候选**（think_tool 里写 "I am terminating with root_cause=X"），然后 compress LLM 基于全部 findings 又做一次独立判断，**有时会输出与 terminator 不同的 root_causes**。

这种漂移的常见原因：
- compress prompt 看的是**累积 findings 文本**（含全部 stage），而 terminator 是**最新 stage 的结论**——两者视角不同
- compress LLM 在没有"stage terminator 权威"概念的情况下，会从全部 findings 中重选
- findings 中某个更早 stage 提到过一个 hub 服务（"config-service may affect all"），compress 可能把 hub 放到 root_causes 顶部（与 A4 HallucinatedHub 共生）

A3 的失败后果：agent 在 trajectory 中已经收敛到候选 X，但 final output 是 Y——**用户看到的答案不是 agent 推理出的答案**，这是 aiq pipeline 的"闭环失灵"。

**反思的认知动作**：让 agent 意识到**最终输出的根因和最后一轮调查的候选不一致**，反问"这种改变是基于新依据，还是只是压缩步骤自己做了选择？"——触发 agent 回到 terminator 候选或显式说明为什么要改。

---

## Trigger abstract（运行时可观察）

```pseudo
trigger_A3(state) :=
  state.check_point == "conclusion"
  AND LET last_terminator = state.last_stage_terminator.root_cause_service
          // 最后一个宣布了具体候选的 stage terminator（stage_0 或 reflect 轮）
      LET compress_rc = state.draft_graph.root_causes[0].service
          // 最新 compress 输出的第一位 root cause
      IN
        last_terminator IS NOT NULL
        AND compress_rc IS NOT NULL
        AND (
          // 场景 a：完全不同候选
          last_terminator != compress_rc
          OR
          // 场景 b：terminator 候选不在 compress 输出的 root_causes 列表里
          (last_terminator NOT IN state.draft_graph.root_causes[*].service)
        )
```

**辅助约束**：
- 若 last_terminator 本身是通用名词（"the system"）→ 已由 A1 处理，A3 不再触发
- 若 compress_rc 为 None（compress 失败降级）→ A3 不触发，需要其他维度覆盖

**触发场景示例**：
- reflect 第 2 轮 terminator 说 "root_cause=S_A"，compress 输出 graph.root_causes = [{service: "S_B", ...}] → 场景 a
- reflect 第 2 轮 terminator = S_A，compress 输出 root_causes = [S_C, S_D]，S_A 完全不在列表 → 场景 b
- reflect 第 2 轮 terminator = S_A，compress 输出 root_causes = [S_B, S_A, S_C]，S_A 被压到次级 → 场景 a（第一位是 S_B）

---

## Intervention pattern

### 主问（A3 作为 most_critical 时）

> **你压缩产生的根因图把一个和你最后调查阶段不同的服务放在了最前面。这种改变可能有新的依据——压缩步骤综合了全部调查发现，看到了某些你最后阶段没突出的线索；也可能是压缩自己做了一次独立选择而不是忠于你最新的调查结论。如果是后者，这个切换没有经过你主动验证，你愿意接受它作为最终答案吗？还是想回到你最后调查阶段宣布的候选？**

**变体**：
- 变体 A（场景 a：完全不同候选）：
  > "你最后调查阶段说 root cause 是一个服务，但压缩输出指向了另一个——两个不同的答案。你能不能反问：这次压缩是综合了新依据得出的改判，还是只是压缩步骤自己重新排序了？如果没专门为这个切换补证据，你信哪个？"
- 变体 B（场景 b：terminator 候选不在 compress 列表）：
  > "你最后调查阶段宣布的候选，在你最终压缩的根因列表里不见了。你能不能反问：是压缩步骤综合了更多证据决定剔除它，还是它只是在压缩时被无意地过滤掉了？如果是后者，这个遗漏是否应该纠正？"

### 次问（A3 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你的最终输出根因和最后调查阶段宣布的候选不同，可以顺带反思一下：这次切换是基于新依据还是压缩自己的选择？"

**次问触发条件**：A3 作为次问被加入复合干预，**仅当** L2 对 A3 给出 `match_score ≥ 0.7`（即 terminator vs compress_rc 确实不一致）。若 last_terminator == compress_rc，L2 给 A3 低分（接近 0），**不加 A3 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 只看 agent 自己产出的 terminator 文本 + agent 自己压缩的 graph.root_causes，**不查询** gt_services / fault_category）
- [x] **Trigger 不含 SQL 字符串**（用 stage schema 字段对比）
- [x] **Trigger 不含具体服务名**（last_terminator / compress_rc 是变量）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（用"一个服务"、"另一个"指代）
- [x] **Intervention 不含错误消息字串**（无）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（"压缩"、"切换"是过程动作，不是拓扑方向）
- [x] **Intervention 用反问 + 多种可能性句式**（"可能有新的依据……也可能是压缩自己做了一次独立选择"——经典两种可能并列；"是前者还是后者？"）
- [x] **agent 可基于自身已做的动作自我修正**（"你压缩产生的根因图"、"你最后调查阶段"——引用 agent 自己的 pipeline 步骤）

**全部 9/9 ✓ → A3 卡片符合 v4 元认知设计原则**

**重要审核点**：

1. **提到"压缩"是否暴露了 aiq 内部术语？** 不算——compress 是 aiq agent 自己在 system prompt 和 reasoning 中使用的词（compress_to_graph 函数名、compress_sp/compress_up prompt 名）；agent 能理解"压缩输出"指什么。这是和 agent 共享的框架词汇，不是 GT 信息
2. **"回到你最后调查阶段宣布的候选" 是否告诉 agent 切回？** 不告诉——主问用反问"你愿意接受它作为最终答案吗？还是想回到你最后调查阶段宣布的候选？" 给 agent 两个选项，让 agent 自己选；不强制回到哪个

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✗ | 无独立 compress 阶段（compress_research 只对 trajectory 压缩，不重选候选）|
| thinkdepthai (claude-sonnet-4.6) | ✗ | 同上 |
| aiq (qwen3.5-plus) | ✓ 主问候选 | compress_to_graph 在 reflect 循环里反复调，漂移是 aiq 架构独有 |
| claudecode (qwen3.5-plus) | ✗ | Claude Code 的 compress 是 trajectory 总结，不重选候选 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

| Framework | failure case 总数 | A3 触发估计 | A3 翻盘期望（~40%，因 agent 一旦意识到漂移可直接回到 terminator 候选）|
|---|---:|---:|---:|
| aiq-qwen3.5-plus | 113 | ~12-16 | **~5 case 翻盘** |

**总翻盘期望**：~5 case 跨 4 framework（仅 aiq）。

**为什么翻盘率 40%（高于 A2 的 20%）**：A3 主问明确指出"你最终输出和你调查结论不一致"，agent 容易在反思中选择"我相信我的调查"——触发回到 terminator 候选。但翻盘需要注入策略能让 graph 真正被改写；若只是让 agent 反思但无法改 graph，实际翻盘率会更低。策略 1（追加第 3 次 refine）或策略 2（追加 compress + 新指令）都可让 agent 改 graph

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **A2 (Refinement-Without-New-Probe)** | A2 是"reflect 内切换无依据"，A3 是"compress 输出 vs terminator 不一致"。A3 是 A2 的 compress-边界特例 | L2 消歧：切换在 reflect 内部 → A2；切换在 compress 输出 → A3 |
| **A4 (Hub-Fabrication Awareness)** | A4 的典型场景是 compress 输出了一个 hub 服务（"config-service"）作为根因 — 如果该 hub 不是 last_terminator，会同时触发 A3 + A4 | 同时命中时 A4 优先（hub-fabrication 比单纯 compress-drift 更危险；A4 主 + A3 次）|
| **A5 (Anti-Flipflop Reflex)** | A5 需要多次切换 + 重返旧候选；A3 只看最终一次不一致 | 语义不同：A5 关注 flipflop 模式，A3 关注最终一致性；两者**可以同时命中**互不冲突 |
| **M1 (Loudness-Anchor Self-check)** | 若 compress 输出的候选恰好是某 ranking 查询的 top1（即 compress 被 loudness 锚定）| 同时命中时 A3 优先（pipeline 闭环失灵 > loudness 问题；A3 主 + M1 次）|

---

## 实施备注

- **关键依赖**：
  - aiq 必须正确提取"最后一个 stage terminator"。从 all_tool_messages 反向找最后一条含 think_tool 且显式 terminator 的消息
  - `draft_graph.root_causes` 字段在 reflect 第 2 次循环结束后必可用（state["causal_graph"] 已由 compress_to_graph 成型）
- **root_causes 多根因的处理**：若 compress 输出多个 root_causes，A3 只看第一位 vs terminator。若 terminator 在列表但非首位，当作场景 a（首位 != terminator）触发
- **compress 失败降级的处理**：若 compress_to_graph 3 次重试都失败 → draft_graph.root_causes 可能为空 → A3 不触发（跳过该维度，让其他维度处理）
- **"新依据" vs "自己选择" 的判定在 agent 侧完成**：L2 不去代 agent 判断哪种情况，主问让 agent 自检
- **离线重放验证**：在 113 aiq failed case 上跑 A3 trigger，统计 precision/recall 相对于 v1 T8 + R_compress_drift 标注。预期 precision ≥ 0.8（结构化 trigger，假阳性率低）

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-6 阶段输出）|
