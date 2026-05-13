# A4 — Hub-Fabrication Awareness（aiq-特定，半通用）

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-6 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | aiq 失败 case 中数量 |
|---|---|---|---:|
| **R 层（aiq-specific）** | `aiq.R_hub_fabrication` | 候选服务名在 trajectory 任何 SQL 结果或 reasoning 推理中**都没出现过**，是 compress 或 reflect 步骤在没证据的情况下"发明"出来的 | **12 / 113** |
| **aiq v1 theme** | **T6 HallucinatedHub** | 同上，v1 冻结 12 case | (同上) |

**对应失败 case 数**（A4 主问触发的初步估计）：
- 严格触发：draft_graph.root_causes[0] 的 service 名在整个 trajectory 的 observed_services 集合里**完全缺失**
- 或者出现过但仅出现在某条 schema 列举（agent 未独立查过该服务）
- **A4 主问的目标 case 池：~10-15 case**

**为什么作为 aiq-特定维度**（虽然其他 framework 也可能 hub-fabricate）：
- aiq 的 compress_to_graph 在 LLM 综合累积 findings 时有**独特的"发明 hub 候选"的倾向**：compress prompt 鼓励 LLM "identify the most likely root cause"，LLM 在无强证据时倾向选"看起来连接很多的中间件" (config-service / gateway / mysql)
- 其他 framework（ReAct）也有类似失败，但不像 aiq 那样**可以结构化检测**（aiq 有 draft_graph 明确列 root_causes，可与 observed_services 对比；ReAct 的候选只出现在 reasoning 文本里，检测需 NER）

---

## Cognitive vocabulary

**这种认知模式是什么样**：

在 RCA 任务里，如果多个服务看起来都有异常，LLM 很容易产生"**它们背后有一个共同 hub 在作祟**"的假设——比如 "configuration service" / "database" / "message queue" / "load balancer" 这类基础设施组件。这种假设本身不错误，但要求**agent 真正查过**该 hub 的证据。

A4 的失败模式是：agent 的 compress 步骤输出了一个 hub 服务作为根因，但该 hub 服务名**在整个 trajectory 里从未出现过**——没查过它的日志、没看过它的 trace、没在任何 SQL 结果里看到它、甚至 reasoning 里也只是**合理推测**（"there might be a config issue")。这是一种 LLM 幻觉：为解释"多个服务异常"而发明一个方便的解释。

**反思的认知动作**：让 agent 意识到**这个候选从未被直接观察过**，反问"这个服务名你是从哪里知道的？是你查到的，还是你为了解释现象而推断出来的？"——逼 agent 自检证据来源，避免幻觉固化。

---

## Trigger abstract（运行时可观察）

```pseudo
trigger_A4(state) :=
  state.check_point == "conclusion"
  AND LET rc_candidate = state.draft_graph.root_causes[0].service
      LET observed = state.observed_services   // trajectory 中出现过的所有具体服务名集合
      IN
        rc_candidate IS NOT NULL
        AND (
          // 场景 a：rc_candidate 完全不在 observed_services
          rc_candidate NOT IN observed
          OR
          // 场景 b：rc_candidate 只出现在 schema 列举（list_tables_in_directory 的输出），
          //         但没有任何 SQL 用 WHERE service_name = rc_candidate 或 SQL 结果返回包含该服务名
          (rc_candidate IN observed
           AND rc_candidate NOT IN services_with_independent_query(state))
        )

services_with_independent_query(state) :=
  SET(intent.target_service
      FOR intent IN state.intent_log
      WHERE intent.intent_type IN {
              'service_error_log', 'service_log_browse', 'service_trace_scan',
              'trace_follow', 'jvm_state', 'container_resource',
              'k8s_state', 'db_state', 'network_layer'
            })
  // 即任何被 WHERE service = X 或针对性查过的服务
```

**辅助约束**：
- **schema 列举不算证据**：parquet schema 中的 service_name 列表仅是 agent 发现"有哪些服务"的元数据，不算 agent 独立查过该服务
- **ranking 类查询结果含该服务也不算独立查证**：如果 rc_candidate 只作为 `error_rate_scan` 的 top-N 结果出现（不是被单独 WHERE 过滤查询过），也可能触发 A4 的场景 b

**触发场景示例**：
- 整个 trajectory 都在查 S_A / S_B / S_C 三个服务的 log 和 trace，compress 输出 root_causes = [{service: "config-service"}]，但 config-service 在 observed_services 里完全没有 → 场景 a
- trajectory 的 list_tables 列出了 30 个服务名包含 "gateway-service"，agent 从没专门查过 gateway，最终 compress 把 gateway 作根因 → 场景 b

---

## Intervention pattern

### 主问（A4 作为 most_critical 时）

> **你最终选的这个候选服务在你整个调查过程里好像**没被你专门查过**——它不在你查过的具体服务列表里，也没有针对它的独立查询。这个名字你是从哪里得知的？是从调查中逐步发现的，还是为了解释你看到的多个异常而推断出来的？如果是后者，你有没有想过先去查一下这个候选的直接证据，而不是把它当作"最可能的解释"？**

**变体**：
- 变体 A（场景 a：完全不在 observed_services）：
  > "你最终的根因候选，在你调查过的服务里**完全找不到**——你没查过它的日志、trace 或指标。这个名字你是怎么想到的？是基础设施里必然存在的服务你凭经验推断的，还是你实际查到了它的异常？在 commit 之前，能不能补查一下这个候选的直接证据？"
- 变体 B（场景 b：只在 schema 列举中出现）：
  > "你最终的根因候选出现在服务列表里，但你没针对它做过独立查询——你没专门查过它的日志、trace 或指标。你选它是基于什么证据？它只是一个'看起来合理的中间件'，还是你在某处看到了它的异常？"

### 次问（A4 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你最终的候选服务在调查过程里没被专门查过，可以顺带反思一下：这个候选是查到的还是推断的？"

**次问触发条件**：A4 作为次问被加入复合干预，**仅当** L2 对 A4 给出 `match_score ≥ 0.7`（即 rc_candidate 确实不在 observed_services 或无独立查询）。若 rc_candidate 已被针对性查过，L2 给 A4 低分，**不加 A4 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 只用 agent 自己查过的 observed_services + intent_log，**不查询** gt_services / fault_category）
- [x] **Trigger 不含 SQL 字符串**（用 intent 抽象类别集合 + service 名称集合对比）
- [x] **Trigger 不含具体服务名**（rc_candidate / observed_services 都是变量）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（用"这个候选"、"这个名字"指代）
- [x] **Intervention 不含错误消息字串**（无）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（"推断"、"查到的"是证据来源描述，不是拓扑方向）
- [x] **Intervention 用反问 + 多种可能性句式**（"是从调查中逐步发现的，还是为了解释异常而推断出来的？"——两种可能并列；"基础设施里必然存在的服务你凭经验推断的，还是你实际查到了它的异常？"——两种情况并列）
- [x] **agent 可基于自身已做的动作自我修正**（"你调查过的服务"、"你没专门查过它"——引用 agent 自己的查询行为）

**全部 9/9 ✓ → A4 卡片符合 v4 元认知设计原则**

**重要审核点**：

1. **"基础设施里必然存在的服务"是否暗示 RCA 答案在基础设施层？** 不算——这句是**描述 agent 可能的幻觉方式**（agent 可能凭"RCA 任务里总会有 config/mysql/gateway"的经验推断），引导 agent 自检是否陷入这种模式。不告诉 agent 答案不在基础设施层
2. **主问问"这个名字你是从哪里得知的"是否过于"责问"？** 不算——是让 agent 反思**证据来源链**：从观察到的 → OK；从推断的 → 需补证据。这是元认知自检，不是对 agent 的指控

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✗（可扩展为 M11）| 也有 hub-fabrication 问题但结构化 trigger 难（无 draft_graph）；v4 不启用，由 M8 的 reasoning 文本 trigger 部分覆盖 |
| thinkdepthai (claude-sonnet-4.6) | ✗ | 同上 |
| aiq (qwen3.5-plus) | ✓ 主问候选 | aiq 有 draft_graph 便于 trigger，v1 T6 高发（10.6%）|
| claudecode (qwen3.5-plus) | ✗ | 无结构化输出可检测 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

| Framework | failure case 总数 | A4 触发估计 | A4 翻盘期望（保守 35%，因 agent 意识到幻觉候选容易改正）|
|---|---:|---:|---:|
| aiq-qwen3.5-plus | 113 | ~12-15 | **~4 case 翻盘** |

**总翻盘期望**：~4 case 跨 4 framework（仅 aiq）。

**为什么翻盘率 35%**：A4 主问直接质疑"候选是否有证据来源"，agent 若反思后意识到是幻觉，会倾向回到 observed_services 里有证据的候选。但 agent 也可能 defensive 继续坚持"we have reason to believe this is the hub"——这时 A4 无翻盘

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **A3 (Compress-Drift Self-check)** | A4 的典型场景常同时满足 A3（compress 输出 != terminator）| 同时命中时 **A4 优先**（hub-fabrication 比单纯 compress-drift 更严重；A4 主 + A3 次）|
| **M1 (Loudness-Anchor)** | 互斥：M1 要求候选是 ranking 查询的 top 行（有数据基础）；A4 要求候选从未被查过（无数据基础） | 互斥，基本不会同时命中 |
| **M8 (Hypothesis-Counterfactual)** | M8 问"commit 前有没有隔离验证"，A4 问"候选是否在 observed_services"。A4 比 M8 更严格（观测 vs 隔离验证的区别）| 同时命中时 A4 优先（A4 是 M8 的严格版）|
| **M2 (Chronic-Noise Skepticism)** | 若 rc_candidate 是某类已知基线噪声载体服务（agent 查过，出现在 observed_services），A4 不命中，M2 命中 | 不冲突，trigger 语义不同 |

---

## 实施备注

- **关键依赖**：
  - aiq 必须在中间件层维护 `observed_services` 集合：遍历整个 all_tool_messages，收集所有 SQL 结果行中的 service_name 列 + 所有 reasoning 文本中提到的具体服务名 + 所有 WHERE filter 中的服务名
  - 该集合应在每次 state 更新时重算（或增量维护）
- **"schema 列举"的排除**：list_tables_in_directory 的结果也含服务名，需**不**算入 observed_services。区分方式：结果包含元数据（parquet 文件列表）vs 实际 SQL query 结果
- **候选名模糊匹配**：若 rc_candidate = "gateway-service" 而 observed = ["api-gateway"]，字面不同。当前 trigger 严格匹配；D-6 可考虑加入 Jaro-Winkler 相似度 ≥ 0.85 作为"变相出现"（但这与 M4 SibilingTwin 有重叠，D-6 审核时讨论）
- **离线重放验证**：在 113 aiq failed case 上跑 A4 trigger，统计 precision/recall 相对于 v1 T6 标注。预期 precision ≥ 0.75，recall ≥ 0.7

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-6 阶段输出）|
