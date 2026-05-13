# M3 — Output-Graph Internal Consistency

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22 (D-3 修订：trigger 改为 reasoning 文本断言，不依赖结构化 graph)
**审核状态**: ⏳ 待审核（D-2 阶段）

---

## ⚠ 重要修订（D-3 阶段，2026-04-22）

**原 trigger 设计依赖结构化 `draft_graph`**——但 thinkdepthai 和 claudecode 的结构化 causal_graph 只在 `compress_research` / compress 之后才生成；**conclusion 检查点（在 compress 之前）拿不到结构化图**，所以原设计在这两个 framework 上不可用。

**修订方案**：M3 trigger 改为基于 **reasoning 文本断言** 的检测——agent 在对话历史中用文本表达了某服务的"问题状态"（"X is UNAVAILABLE" / "Y is failing" 等），但 reasoning 中可推断的候选 RC 不是该服务。

这保留了 M3 的认知本质（agent 自我矛盾：自己说某服务出问题却不选它作 RC），且适用于所有 framework（reasoning 文本任何阶段都可读）。aiq 的 conclusion 检查点恰好在 reflect_on_graph 之后（此时 `state["causal_graph"]` 已成型），**可同时启用 reasoning 文本检测 + 结构化 graph 检测两路 trigger**。

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | 372 case 中数量 |
|---|---|---|---:|
| **R 层** | `U3_EdgeDirectionOrRegionEndpointError` | agent 正确定位到故障区域，但输出图里把真正出问题的服务放成了某个根因的 child node 而非 root，或者把方向搞反了 | **48** |
| **PD 层** | `PD_NoCallTreeBuild` | agent 全程没构建 call tree（recursive CTE / parent_span_id 自连接）来理清调用链层级 | **202**（涵盖更广） |
| **D 层** | 无独立来源；M3 关注的是 agent 输出本身的一致性，与数据形态独立 | — | (无) |

**对应失败 case 数（M3 主问触发的初步估计）**：
- 严格交集 (U3 ∧ PD_NoCallTreeBuild)：~25 case
- 宽松命中 (U3 单独)：48 case
- M3 主问的目标 case 池：~30-50 case

**Per-framework 分布**（来自 unified_R.md）：
- aiq-qwen3.5-plus: 0 / 113 = 0%
- claudecode-qwen3.5-plus: 17 / 102 = 16.7%
- thinkdepthai-claude-sonnet-4.6: 22 / 50 = 44.0%（**最高发**）
- thinkdepthai-qwen3.5-plus: 9 / 105 = 8.6%

**Framework 启用注意**：aiq 输出格式是 `causal_graph` 字典，不一定有 UNAVAILABLE 这种节点状态标签——D-6 阶段需确认 aiq 的 graph 节点是否有等价的"agent 自标问题"字段；如无则 M3 在 aiq 不启用。claudecode 和 thinkdepthai 都有节点状态字段，可启用。

---

## Cognitive vocabulary

**这种认知模式是什么样**：

agent 在调查阶段生成了一份候选服务列表，并在最后输出一个 `causal_graph`，graph 里每个节点带有 agent 自己赋的状态标记（UNAVAILABLE / RESTARTING / HIGH_ERROR_RATE 等）和 root_causes 列表。失败模式是**输出图自身存在内部不一致**：agent 在某个节点上明确标了"出问题"（UNAVAILABLE），却没把它列进 root_causes，反而把它放在另一个 root_cause 节点的下面（作为子节点）。

这通常发生在：
- 真正的故障节点信号偏弱（被 silent / 被 chronic noise 盖住），agent 选了一个"症状响亮"的节点当 root
- 但 agent 自己在调查时对该故障节点的观察导致它给出了 UNAVAILABLE 标记
- 提交时没有反向核对："**我自己标了问题的节点，为什么不是根因？**"

**反思的认知动作**：commit 之前主动核对自己的输出图——"**我在某个节点上标了 UNAVAILABLE/RESTARTING，但它不在我的根因列表里，这种判断的支撑证据是什么？**"——这是一个纯内部一致性检查，**不和 GT 比**，agent 完全可以基于自己的输出回答。

---

## Trigger abstract（运行时可观察 — D-3 修订版）

**通用 trigger（所有 framework）— 基于 reasoning 文本断言**：

```pseudo
trigger_M3_text(state) :=
  (LET problem_keywords = { 'UNAVAILABLE', 'RESTARTING', 'HIGH_ERROR_RATE',
                            'KILLED', 'UNHEALTHY', 'INJECTION_AFFECTED',
                            'down', 'crashed', 'failing', 'unreachable',
                            '不可用', '崩溃', '故障', '异常' }
   LET reasoning_text = state.reasoning_log[ last_K_rounds = 8 ]
   LET service_status_assertions = EXTRACT_PATTERNS(
        reasoning_text,
        pattern = "<service_name> + (is|appears|seems|被|状态|出现) + <problem_keyword>"
   )
   //  service_status_assertions 是 [(service_name, assertion_text)] 列表
   //  示例：("S_X", "S_X appears UNAVAILABLE due to pod kill")

   LET candidate_RC_inferred = INFER_CANDIDATE_RC_FROM_REASONING(reasoning_text)
                                // 从 reasoning 推断 agent 倾向的候选（可为 None；opus-4.7 判断）
   LET orphan_assertions = [
        (svc, txt) FOR (svc, txt) IN service_status_assertions
        WHERE svc != candidate_RC_inferred
   ]
   IN
     LENGTH(orphan_assertions) >= 1
     AND candidate_RC_inferred IS NOT None)
```

**附加 trigger（仅 aiq，conclusion 检查点时）— 基于结构化 graph orphans**：

```pseudo
trigger_M3_graph(state) :=
  (LET problem_marks = { 'UNAVAILABLE', 'RESTARTING', 'HIGH_ERROR_RATE',
                         'KILLED', 'UNHEALTHY', 'INJECTION_AFFECTED' }
   LET nodes_self_flagged = [
        n FOR n IN state.causal_graph.nodes
        WHERE n.state IN problem_marks OR n.flag IN problem_marks
   ]
   LET orphans = [
        n FOR n IN nodes_self_flagged
        WHERE n.name NOT IN state.causal_graph.root_causes
   ]
   IN LENGTH(orphans) >= 1)
```

**触发场景示例（reasoning 文本检测）**：
- thinkdepthai-sonnet：think_tool 反思中出现 "service X looks UNAVAILABLE based on the trace pattern"，但 reasoning 同段中表达的候选 RC 是 service Y
- claudecode：agent 在 Bash 命令注释或后续 message 中写 "S is unreachable"，但准备 commit 的候选不是 S
- aiq：stage_2 reflect 中提到 "service Z is failing"，但 stage_2 terminator 指向另一个服务

**触发场景示例（aiq 结构化 graph 检测）**：
- aiq reflect_on_graph 第 2 次循环结束时，`state["causal_graph"]` 中存在 `state="UNAVAILABLE"` 的节点不在 root_causes 列表里

---

## Intervention pattern

按 v4 原则 4 的「1 主问 + 0~3 次问」复合结构生成：

### 主问（M3 作为 most_critical 时）

> **你的输出图里有节点你自己标了 UNAVAILABLE 或 RESTARTING（或类似的"明显有问题"的状态），但你没把它列入根因。这种"我标了问题但它不是根因"的判断需要支撑证据：你能解释为什么这些节点不是根因吗？被你自己标问题的节点——不一定就是被另一个根因连累的，也可能它本身就是问题来源。**

**变体**：
- 变体 A（结论前检查，agent 即将提交）：
  > "你即将提交的输出图里，有节点被你自己标了'明显有问题'状态（UNAVAILABLE/RESTARTING 之类），但它不在根因列表里。在最终提交前请反问一次：你自己都标了'有问题'的节点，凭什么排除它做根因？它不一定是被另一个根因连累的，也可能它本身就是问题来源。能不能列出至少一条证据说明它确实只是被影响而不是源头？"
- 变体 B（中期检查，agent 还在调查阶段，draft graph 已成型）：
  > "你的当前 draft 输出图里，有节点你标了'明显有问题'但没列入根因。在你继续推进之前，能不能想一下：这种状态的节点凭什么不是根因？你的判断需要支撑证据。"

### 次问（M3 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你的输出图里有自标 UNAVAILABLE/RESTARTING 的非根因节点，可以顺带核对一下：它真的只是被影响吗？"

**次问触发条件**：M3 作为次问被加入复合干预，**仅当** L2 对 M3 给出 `match_score ≥ 0.7`（即 L2 真的检测到 draft graph 里存在自标问题的非根因节点）。如果 graph 里所有自标问题节点都已在 root_causes 里，L2 给低分，**不加 M3 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 完全基于 agent 自己的 reasoning 文本 + 结构化 graph（aiq 时），**不和** `gt_services` 比，**不查询** fault_category）
- [x] **Trigger 不含 SQL 字符串**（reasoning 文本 pattern 匹配 + 结构遍历）
- [x] **Trigger 不含具体服务名**（`service_status_assertions` 和 `orphan_assertions` 都是变量列表；problem_keywords 是通用问题状态词不是数据集服务名）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（用"节点"、"它"指代）
- [x] **Intervention 不含错误消息字串**（无 UnknownHostException 等）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（只用"被另一个根因连累"、"它本身就是问题来源"——这两个词组虽接近"源"，但表述是开放性"不一定是 X，也可能是 Y"，没暗示哪个对，且引用的是 agent 自己的图布置而非真实拓扑方向）
- [x] **Intervention 用反问 + 多种可能性句式**（"不一定就是被另一个根因连累的，也可能它本身就是问题来源"——开放对比）
- [x] **agent 可基于自身已做的动作自我修正**（"你的输出图里有节点你自己标了 UNAVAILABLE..."引用 agent 自己的 draft 输出）

**全部 9/9 ✓ → M3 卡片符合 v4 元认知设计原则**

**审核风险点**："被另一个根因连累" / "它本身就是问题来源" 这两个词是否触红线？我的判断是不触：
- 没用"上游"/"下游"/"源"/"汇"等拓扑方向词
- 用"另一个根因"指代不明确，让 agent 自己想是哪个
- 用"问题来源"是认知词（不是 GT 概念词；agent 可以理解为"故障的诱因"而非"call graph 的源点"）
- 仍是开放性"不一定...也可能..."句式，不指定答案

如审核认为仍有方向性暗示，可改成更中性："这种状态的节点凭什么不是根因？你的判断需要支撑证据。"——但这削弱了"反向假设"的引导力。建议保留当前表述，等 D-2 审核明确意见。

---

## 适用 framework

| Framework | 启用 | trigger 类型 | 备注 |
|---|:---:|---|---|
| thinkdepthai (qwen3.5-plus) | ✓ 主问候选 | reasoning 文本检测 | 8.6% U3，可启用；触发率不高 |
| thinkdepthai (claude-sonnet-4.6) | ✓ 主问候选 | reasoning 文本检测 | 44.0% U3，**最高发**；结论前检查时优先 |
| aiq (qwen3.5-plus) | ✓ 主问候选 | **reasoning + 结构化 graph 双路** | aiq 中 U3=0 但 conclusion 时有结构化 graph，可同时用两路 trigger 提高 recall |
| claudecode (qwen3.5-plus) | ✓ 主问候选 | reasoning 文本检测 | 16.7% U3，可启用 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

| Framework | failure case 总数 | U3 占比 | M3 主问命中估计 | M3 翻盘期望（按 30-50% 翻盘率） |
|---|---:|---:|---:|---:|
| thinkdepthai-qwen3.5-plus | 105 | 8.6% | ~9 | ~3-4 case 翻盘 |
| thinkdepthai-claude-sonnet-4.6 | 50 | 44.0% | ~22 | **~7-11 case 翻盘** |
| aiq-qwen3.5-plus | 113 | 0% | 0 | 0 |
| claudecode-qwen3.5-plus | 102 | 16.7% | ~17 | ~5-8 case 翻盘 |

**Phase 8 离线重放将给出精确数值。**

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **M8 (Hypothesis-Counterfactual)** | M3 触发时通常 PD_NamedCandidateNotIsolated 也命中（agent 没把自标 UNAVAILABLE 节点单独 isolate 检验过）| **L2 主+次条件**：主问 M3（输出图一致性反思），如 L2 也给 M8 ≥ 0.7 加 M8 次问 |
| **M1 (Loudness-Anchor)** | M3 触发时 agent 选的 root 经常是"症状响亮"的节点 | M1 关注 commit 时点的 ranking 启发式，M3 关注 commit 时点的输出图自检。可同时命中，按 L2 score 选主 |

---

## 实施备注

- **关键依赖**：每个 framework 的 `draft_graph` 节点必须有 `state` / `flag` 这类"agent 自标"字段。thinkdepthai 和 claudecode 都有；aiq 待 D-6 确认
- **L2 prompt 设计**：opus-4.7 接收 `draft_graph.nodes` + `draft_root_causes`，判定是否存在 orphans（自标问题但不在 root_causes），给 `M3_score ∈ [0, 1]`
- **离线重放验证**：在 372 已标注 case 上跑 trigger，统计 (precision, recall) 相对于 U3 标注

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-2 阶段输出） |
