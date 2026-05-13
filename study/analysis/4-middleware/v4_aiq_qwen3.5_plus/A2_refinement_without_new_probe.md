# A2 — Refinement-Without-New-Probe Reflection（aiq-特定）

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-6 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | aiq 失败 case 中数量 |
|---|---|---|---:|
| **PD 层（aiq-specific）** | `aiq.PD_ReflectionStageWithoutNewProbe` | reflect_on_graph 阶段切换了候选但该阶段 trajectory 内**没有新的独立隔离查询**来支撑切换 | **48 / 113** |
| **R 层（相关）** | T5 ReflectionReversesCorrect（背景）— 当候选切换是"反转正确答案"时，A5 覆盖；A2 是更广的"无证据切换" | (背景) |

**对应失败 case 数**（A2 主问触发的初步估计）：
- 严格触发：stage_{N+1} terminator 候选 ≠ stage_{N}，且 stage_{N+1} trajectory 无针对新候选的独立 WHERE/LIKE/ILIKE 过滤查询
- 48 case 是宽口径；A2 主问的目标 case 池：~40-48 case

---

## Cognitive vocabulary

**这种认知模式是什么样**：

aiq 的 reflect_on_graph 节点设计初衷是"锦上添花不推翻"（STRENGTHEN not overturn，见 aiq/CLAUDE.md）——每次 refine sub-loop 应该在**当前 graph 的基础上补强弱点**，而不是从头换一个候选。

A2 的失败模式是：reflect 阶段输出了**不同的 terminator 候选**，但该阶段的 refine sub-loop trajectory 里**没有针对新候选的独立调查**——没有 WHERE service_name = '<new candidate>' 的 SQL，没有专门查新候选的 log/trace，没有 metric 查询。agent **换了候选但没做功**，切换的依据往往是：
- reflect 的 system prompt 中有"look for the MOST LIKELY root cause"类引导
- LLM 在没新证据时凭"感觉"重选
- compress_to_graph 输出了与 terminator 不同的 root_causes（与 A3 相关但时序不同）

这会导致 agent 在多个候选间无依据漂移，最终 compress 选的可能不是最有证据的那个。

**反思的认知动作**：让 agent 意识到**切换候选需要新证据支撑**，反问"你换到了一个新候选，但这一阶段你专门查过它吗？如果没有，切换是基于什么判断？"——不告诉 agent 切回旧候选，只让 agent 自检切换的理由。

---

## Trigger abstract（运行时可观察）

```pseudo
trigger_A2(state) :=
  state.check_point == "conclusion"
  AND LET prev_candidate = state.stage_N_terminator.root_cause_service
      // stage_N 可以是 stage_0_main 或任意 reflect 轮
      LET curr_candidate = state.stage_{N+1}.root_cause_service
                         // 或 compress 输出的 graph.root_causes[0].service
      IN
        prev_candidate IS NOT NULL
        AND curr_candidate IS NOT NULL
        AND prev_candidate != curr_candidate
        AND NOT exists_independent_probe_in_stage(state, stage_{N+1}, curr_candidate)

exists_independent_probe_in_stage(state, stage, candidate) :=
  EXISTS intent IN state.intent_log[stage]
    WHERE intent.target_service == candidate
      AND intent.intent_type IN {
            'service_error_log',
            'service_log_browse',
            'service_trace_scan',
            'trace_follow',
            'call_tree_build',
            'jvm_state',
            'container_resource',
            'k8s_state',
            'db_state',
            'network_layer'
          }
      // 即 stage_{N+1} 内有针对新候选的具体 WHERE-filter 类查询
```

**关键约束**：
- `exists_independent_probe_in_stage` 检测的是**针对新候选的独立隔离查询**——排名类查询（error_rate_scan / latency_ranking / throughput_compare）**不算**独立隔离，因为它们是全服务扫描，不是对新候选的针对性查证
- stage_{N+1} 可以是 reflect 第 1 轮 / reflect 第 2 轮 / compress 输出；多 stage 切换时取**最后一次切换**判 A2

**触发场景示例**：
- stage_0 terminator 候选 = S_A，reflect 第 1 轮后 compress 输出 root_causes = [S_B]，但 reflect 第 1 轮的 trajectory 里**没有** `WHERE service_name = 'S_B'` 类查询（只有排名查询或对 S_A 的追查）→ A2 命中
- reflect 第 2 轮后 compress 输出 = S_C（第三个候选），但 reflect 第 2 轮只做了 "look for anomalies" 类泛查，没针对 S_C 的独立查询 → A2 命中

---

## Intervention pattern

### 主问（A2 作为 most_critical 时）

> **你的最新候选和你早些阶段宣布的候选不是同一个——你换过选择了。但这一阶段里你似乎没有专门去查过这个新候选：没有针对它的独立查询、没有专门看过它的日志或指标。切换是基于什么判断？如果这一阶段还没对新候选做过独立验证，你现在的选择到底是有新证据，还是只是又一次猜测？**

**变体**：
- 变体 A（reflect 阶段切换候选，trajectory 无新探查）：
  > "你换到了一个新候选，但这一 refine 阶段里你没有对它做过专门的独立查询。你的切换是因为你看到了什么新证据，还是因为这个候选在你之前的某个 ranking 里出现过？如果没新证据支撑，切换前能不能先查一下新候选本身？"
- 变体 B（compress 输出与上一 stage terminator 不同，且中间无针对性查询）：
  > "你最后压缩的根因和你上一阶段宣布的终止候选不一样。这中间你有没有专门去查过这个新候选的证据？如果这个切换是 compress 阶段自己做的选择而不是基于新查询，能不能反问一次：你真的有足够证据支撑这个新选择吗？"

### 次问（A2 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你的候选在阶段之间切换过但没专门查过新候选，可以顺带反思一下：切换的依据是什么？"

**次问触发条件**：A2 作为次问被加入复合干预，**仅当** L2 对 A2 给出 `match_score ≥ 0.7`（即真切候选切换 + 真无针对性查询）。若 stage 间候选未切换，或切换时有独立隔离查询，L2 给 A2 低分，**不加 A2 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 完全基于 agent 自己产出的 stage terminator 内容 + intent_log 结构，**不查询** gt_services / fault_category）
- [x] **Trigger 不含 SQL 字符串**（用 intent 抽象类别 + stage 边界事件）
- [x] **Trigger 不含具体服务名**（prev_candidate / curr_candidate 是变量）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（用"新候选"、"这个候选"指代）
- [x] **Intervention 不含错误消息字串**（无）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（"切换"、"新证据"是认知 / 决策动作，不是拓扑方向）
- [x] **Intervention 用反问 + 多种可能性句式**（"切换是因为你看到了什么新证据，还是因为这个候选在之前的 ranking 里出现过？"——经典两种可能并列；"真的有足够证据支撑，还是只是又一次猜测？"——开放反问）
- [x] **agent 可基于自身已做的动作自我修正**（"你换到了一个新候选"、"这一阶段里你没有对它做过专门查询"——引用 agent 自己的 stage 切换 + 查询行为）

**全部 9/9 ✓ → A2 卡片符合 v4 元认知设计原则**

**重要审核点**：

1. **"切换"/"新候选" 措辞是否暗示答案？** 不暗示——主问只问"切换是否有证据支撑"，**不告诉** agent 应该切回旧候选还是保留新候选。这是让 agent 自检决策过程，不是注入答案
2. **trigger 的 "independent probe" 定义是否 domain-agnostic？** 是——`intent_type` 集合是 v4 原则 2 允许使用的 19 类抽象意图，不涉及任何 RCABench 特有 schema

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✗ | 无 stage 概念；候选切换只存在于 compress_research 这一步，trajectory 本身是单一线程 |
| thinkdepthai (claude-sonnet-4.6) | ✗ | 同上 |
| aiq (qwen3.5-plus) | ✓ 主问候选 | 5 阶段 + 2 次 reflect，cross-stage 候选切换是 aiq 独有现象 |
| claudecode (qwen3.5-plus) | ✗ | 无 stage 概念 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

| Framework | failure case 总数 | A2 触发估计 | A2 翻盘期望（保守 20%，因 A2 触发时 agent 已漂移，回拉难度大）|
|---|---:|---:|---:|
| aiq-qwen3.5-plus | 113 | ~40 | **~8 case 翻盘** |

**总翻盘期望**：~8 case 跨 4 framework（仅 aiq）。

**为什么翻盘率低**：
- 触发点在 conclusion 阶段，agent 已经跑完 2 次 reflect，修改 graph 成本高
- A2 主问让 agent 反思"切换是否有依据"，agent 可能回答"我有理由"然后继续——即使理由不充分
- 翻盘依赖注入策略：若策略 1（追加第 3 次 refine 循环）能让 agent 专门去查新候选，翻盘率更高

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **A3 (Compress-Drift Self-check)** | 相邻但不同：A2 是"reflect 切换无依据"，A3 是"compress 输出与 terminator 不一致"。A3 可视为 A2 的特例（compress 是特殊的"阶段"） | L2 消歧：若切换发生在 reflect 的 refine sub-loop 内部（compress 之前），触发 A2；若切换仅发生在 compress 输出 vs 最后 stage terminator 对比，触发 A3 |
| **A5 (Anti-Flipflop Reflex)** | A5 需要 **≥2 次切换**且新候选在更早 stage 已被否过；A2 只要 1 次无依据切换即命中 | 同时命中时 A5 优先（flipflop 比单次无依据切换更显著）|
| **M8 (Hypothesis-Counterfactual)** | M8 问"commit 前有没有隔离验证候选"，A2 问"切换候选时有没有验证新候选"；两者可同时命中 | 可同时主/次问；M8 是 commit 前通用检查，A2 是 aiq cross-stage 特化 |

---

## 实施备注

- **关键依赖**：
  - aiq 必须正确提取每个 stage（stage_0_main + 2 次 reflect + compress 输出）的 **terminator** 候选。若框架未显式记录每 stage 边界的 terminator，需要中间件从 all_tool_messages 中按 stage 时序切分
  - intent_log 需要按 stage 分段（stage_0 内的 intent / reflect_iter_1 内的 intent / reflect_iter_2 内的 intent）
- **"independent probe" 阈值**：当前定义要求 stage_{N+1} 内至少有 **1 次** 针对新候选的 WHERE-filter 类查询。D-6 审核可调：改为 ≥ 2 次（更严格）或改为"任何提及新候选的查询"（更宽松）。初步 1 次
- **compress 切换作为特例**：若 reflect 内部切换都有 probe 但 compress 输出又变了，这是 A3 而非 A2。L2 消歧时按"切换位置"区分
- **离线重放验证**：在 113 aiq failed case 上跑 A2 trigger，统计 precision/recall 相对于 v1 PD_ReflectionStageWithoutNewProbe 标注

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-6 阶段输出）|
