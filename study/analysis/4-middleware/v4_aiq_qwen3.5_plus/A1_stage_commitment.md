# A1 — Stage-Commitment Discipline（aiq-特定）

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-6 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | aiq 失败 case 中数量 |
|---|---|---|---:|
| **PD 层（aiq-specific）** | `aiq.PD_StageEndsWithoutCommitment` | 某 stage 结束时**没有输出候选服务**或 terminator 的 `root_cause_service=None` | **108 / 113** 标注触及（含次级） |
| **R 层（相关）** | (背景) 常与 T4 SilentSignalMissed 共现——agent 在 stage_0 没选出候选，reflect 阶段也无基准可强化 | (背景) |

**对应失败 case 数**（A1 主问触发的初步估计）：
- aiq 113 failed case 中 stage_0 全 3 terminator 但 root_cause_service=None 的 case：~20 个
- 加上 stage_0 到 max_rounds=60 仍无 terminator 的 case：~5 个
- **A1 主问的目标 case 池：~20-25 case**（严格筛选：仅 stage_0 既未收敛又未指向任何候选）

**为什么 108 case 不是全部目标**：
- v1 taxonomy 中 108 是"**触及**该模式"的宽口径；严格触发 A1 主问（stage_0 无候选）是窄口径
- 失败 case 里只有 1 个 terminator truncated（2 个缺失）的 case 多（38%），但这些 case 常在 stage_0 就选出候选，不是 A1 目标
- A1 只针对"真空白"的 stage_0 — 这是 aiq 特有的 stage 边界事件

---

## Cognitive vocabulary

**这种认知模式是什么样**：

aiq 是 5 阶段流水线（generate_queries → data_research → build_graph → reflect_on_graph → finalize_summary）。正常情况下，主调查阶段（data_research）结束时 agent 应该已经**从调查发现中收敛到一个或多个候选服务**——通过 terminator 机制，agent 显式在 think_tool 里宣布"I am terminating with root cause X"。

A1 的失败模式是：**主调查阶段结束时 agent 没有收敛到任何候选**。可能是：
- stage_0 跑到 max_rounds=60 仍在继续探索，没出 terminator
- stage_0 有 terminator 但 `root_cause_service=None`（agent 宣布结束但没指定候选）
- terminator 指向一个通用名词（"the system"）而非具体服务

这会导致 reflect_on_graph 阶段**从空白反推**：没有 baseline candidate 可 STRENGTHEN，reflect 只能从零重来。aiq 的 reflect 设计是"锦上添花不是推翻"，但在 stage_0 空白时 reflect 反而容易 hallucinate 一个候选（T6 HallucinatedHub 常常与此共生）。

**反思的认知动作**：让 agent 意识到**本阶段的主调查没有形成可交接的候选**，反问"如果现在让我从已有观察里挑一个最可能的候选，我会挑谁？为什么不挑别的？"——逼 agent 在 stage 边界做一次"出牌"，即使只是暂定。

---

## Trigger abstract（运行时可观察）

```pseudo
trigger_A1(state) :=
  state.current_stage == "post_stage_0"
  AND (
    // 场景 a：stage_0 达 max_rounds 仍未出 terminator
    (state.stage_0_reached_max_rounds == true
     AND state.stage_0_terminator IS NULL)
    OR
    // 场景 b：stage_0 有 terminator 但没指定候选服务
    (state.stage_0_terminator IS NOT NULL
     AND state.stage_0_terminator.root_cause_service IS NULL)
    OR
    // 场景 c：terminator 指向通用名词（非具体服务名）
    (state.stage_0_terminator IS NOT NULL
     AND state.stage_0_terminator.root_cause_service IN
         { 'the system', 'unknown', 'general', 'multiple services', 'cascading' }
     AND state.stage_0_terminator.root_cause_service NOT IN state.observed_services)
  )
```

**辅助谓词**：
- `observed_services`：整个 stage_0 trajectory 中出现过的所有具体服务名（WHERE filter / SQL result 列 / reasoning 文本）。用于判断 terminator 是否指向具体候选
- **排除 baseline 类 terminator**：若 stage_0 最后一次 terminator 宣布的是"没有观察到异常"（场景 c 的特殊情况），也触发 A1

**触发场景示例**：
- stage_0 跑了 60 轮 tool calls，最后一条 assistant message 仍有 tool_calls 字段 → 场景 a
- stage_0 第 30 轮 think_tool 反思说 "I have gathered sufficient evidence, I am terminating. The investigation suggests cascading failures but I cannot pinpoint a specific root cause" → 场景 c

---

## Intervention pattern

### 主问（A1 作为 most_critical 时）

> **你刚结束了主调查阶段，但看起来你还没选出一个明确的候选服务——要么还在继续查，要么提到了"多个"或"难以确定"这样的表述。下一阶段要从空白反推会非常困难。在继续之前请反问一次：如果现在只能挑一个最可能的候选，你会挑谁？为什么是它而不是别的？哪些证据让你倾向它？**

**变体**：
- 变体 A（场景 a：跑到 max_rounds 仍无 terminator）：
  > "你的主调查阶段已经跑了很多轮，但还没宣布终止。是不是在几个可能性之间来回摇摆？能不能先强制自己出一个候选——即使只是暂定——然后在下一阶段再验证？"
- 变体 B（场景 b/c：terminator 指向空或通用名词）：
  > "你主调查结束时说 root cause 是 [null / 'the system' / 类似措辞]，这对下一阶段的反推没有帮助。能不能挑一个你查到的具体服务作为暂定候选？这个选择不是最终答案，只是为了让下一阶段有东西可验证。"

### 次问（A1 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外本阶段你没收敛到具体候选，下阶段会很难推进——能不能先暂定一个最可能的服务？"

**次问触发条件**：A1 作为次问被加入复合干预，**仅当** L2 对 A1 给出 `match_score ≥ 0.7`（即 stage_0 确实无 terminator 或 terminator service 为 None/通用名词）。若 stage_0 terminator 已指向具体服务，L2 给 A1 低分，**不加 A1 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 只用 stage_0_terminator 的 agent 自己宣布内容 + observed_services 字符串集合，**不查询** gt_services / fault_category）
- [x] **Trigger 不含 SQL 字符串**（trigger 用 stage 边界事件 + terminator schema 字段判断）
- [x] **Trigger 不含具体服务名**（场景 c 的"通用名词"列表是**通用短语**，不是 RCABench 特有服务）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（用"具体候选"、"哪个服务"指代）
- [x] **Intervention 不含错误消息字串**（无）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（"暂定候选"、"出一个候选" 是认知 / 决策动作，不是拓扑方向）
- [x] **Intervention 用反问 + 多种可能性句式**（"要么还在继续查，要么提到了'多个'或'难以确定'"——两种模式并列；"是不是在几个可能性之间来回摇摆？"——开放反问）
- [x] **agent 可基于自身已做的动作自我修正**（"你刚结束了主调查阶段"、"你查到的具体服务"——引用 agent 自己的调查行为）

**全部 9/9 ✓ → A1 卡片符合 v4 元认知设计原则**

**重要审核点**：

1. **"暂定候选"是否暗示答案？** 不暗示——主问要求 agent **自己从已查到的服务里挑**，不给任何服务名、不给层级、不给方向。这相当于"强制 agent 出牌"，是元认知决策训练，不是答案注入
2. **场景 c 的"通用名词"列表（'the system' / 'unknown' 等）是否引入领域偏见？** 不引入——这些都是**agent 自己产出的文本**中可能出现的通用表述，检测它们是识别 "agent 说了但没真正选"，不是 RCABench 特有词

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✗ | 无 stage 概念；等价场景（ReAct 循环结束无候选）落在 M9/M10 |
| thinkdepthai (claude-sonnet-4.6) | ✗ | 同上 |
| aiq (qwen3.5-plus) | ✓ 主问候选 | stage_0 末尾中期主用维度 |
| claudecode (qwen3.5-plus) | ✗ | 无 stage 概念；等价场景落在 M9 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

| Framework | failure case 总数 | A1 触发估计 | A1 翻盘期望（保守 30%，因 A1 只是"提醒出牌"，后续还得靠其他维度）|
|---|---:|---:|---:|
| aiq-qwen3.5-plus | 113 | ~20 | **~6 case 翻盘** |

**总翻盘期望**：~6 case 跨 4 framework（仅 aiq）。

**为什么翻盘率低于 M1/M2**：A1 只是"推 agent 出牌"——agent 出完牌后仍可能出错。A1 的主要价值是**把 B 类失败转换为 A/C 类失败**：原本 stage_0 空白 → reflect hallucinate → 错误；A1 后 stage_0 有暂定候选 → reflect 可验证 → 可能修正。翻盘链路较长，保守估 30%。

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **M10 (Premature Commitment)** | 互斥：M10 要求 round 短就 commit；A1 要求 stage_0 无 commit | 互斥，不会同时命中（触发场景完全相反）|
| **M9 (Investigation Stagnation)** | A1 的场景 a（跑到 max_rounds 无 terminator）可能和 M9（重复探查）共现 | 同时命中时 A1 优先（stage 边界事件 > 重复模式）；M9 退次问 |
| **A4 (Hub-Fabrication)** | A1 的场景 c（terminator 通用名词）之后常被 A4 覆盖——agent 后续 hallucinate 一个 hub | 时序：A1 在 stage_0 末尾触发，A4 在 conclusion 时触发；不冲突（不同 check point）|
| **M6 / M7** | A1 触发时 agent 可能 baseline / layer 也未覆盖 | L2 可同时给 M6/M7 次问；A1 主问 + M6/M7 次问是常见组合 |

---

## 实施备注

- **关键依赖**：
  - aiq 必须正确提取 **stage_0_terminator** 语义。aiq agent_runner.py 的 data_research 节点 think_tool 机制支持 terminator 消息，需要在中间件中解析 terminator 的 `root_cause_service` 字段
  - `observed_services` 集合需要 L1 从 stage_0 的 SQL 结果 / reasoning 中提取所有具体服务名
- **terminator 语义准确性**：v1 failure_analysis 中 "1 terminator (2 truncated)" case 占 38%，这些 case 的 terminator **提供了有效候选**，**不**触发 A1。A1 只针对"真空白" terminator（None / 通用名词）
- **场景 c 的通用名词列表**可扩展：D-6 审核阶段可加"cascading"、"infrastructure"、"platform"、"cluster-wide"等。列表本身**不依赖 RCABench 数据集**，是通用 RCA 任务的"模糊答案"词集合
- **离线重放验证**：在 113 aiq failed case 上跑 A1 trigger，统计 precision/recall 相对于 v1 theme T6/T8 + "terminator=None"标注。预期 precision ≥ 0.7

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-6 阶段输出）|
