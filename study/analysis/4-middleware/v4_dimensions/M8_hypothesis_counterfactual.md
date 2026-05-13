# M8 — Hypothesis-Counterfactual

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-3 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | 372 case 中数量 |
|---|---|---|---:|
| **PD 层** | `PD_NamedCandidateNotIsolated` | 候选 RC 从未在任何独立隔离查询中被单独检验过——agent 知道某些候选名字但从未做 `WHERE service_name='<候选>'` 类查询 | **81** |
| **R 层** | (相关) U1/U2/U5 综合 — counterfactual 缺失常导致 commit 错误候选 | (背景) |
| **D 层** | (背景) D1/D3/D5 — 数据形态背景 |  (背景) |

**对应失败 case 数（M8 主问触发的初步估计）**：
- 严格按 PD trigger（候选 RC 从未在独立 isolation intent 中出现）：~80-100 case
- M8 主问的目标 case 池：~50-80 case（去掉与 M1/M3 重叠后）

**Per-framework 分布**（来自 PD_taxonomy.md）：
- aiq-qwen3.5-plus: 37 / 113 = 32.7%
- claudecode-qwen3.5-plus: 13 / 102 = 12.7%（含 framework-specific PD4 = 63 case，部分等价于 M8）
- thinkdepthai-claude-sonnet-4.6: 31 / 51 = 60.8%
- thinkdepthai-qwen3.5-plus: 未独立 induced

**PD_NamedCandidateNotIsolated** 是 v1 中标记 red zone (V_r=0.54) 的维度，与 R 层强相关——M8 把这种相关性用元认知的方式利用：与其禁用 PD，不如在干预里直接利用"漏 isolation"和"R 层失败"的耦合。

---

## Cognitive vocabulary

**这种认知模式是什么样**：

agent 在调查中通过聚合查询（GROUP BY service_name 类）汇总观察到很多服务，最后选了某个服务作 candidate RC。但**从未对这个具体候选单独跑过隔离查询**（`WHERE service_name='<candidate>'` 类），也没做过反事实检验（"如果排除这个候选，剩下的证据还能解释观察吗？"）。

这是 RCA 推理中最经典的认知盲点之一：**汇总数据 ≠ 候选独立证据**。一个服务可能在汇总排名里靠前是因为它和真正的故障源有调用关系，而不是因为它本身有问题。隔离查询和反事实检验是 disambiguate 这两种可能性的标准手段。

**反思的认知动作**：commit 之前主动做反事实检验——"**如果把这个候选从图里抠掉，剩下的证据还能解释你看到的现象吗？**"——这一步迫使 agent 把 candidate 当作可证伪假设而非已 commit 结论。

---

## Trigger abstract（运行时可观察）

```pseudo
trigger_M8(state) :=
  (LET about_to_commit          = state.is_at_check_point AND state.draft_root_causes != []
   LET candidate_RC             = state.draft_root_causes[0]
   LET isolation_intents_for_RC = COUNT(state.intent_log WHERE
        target_service == candidate_RC
        AND intent IN { 'service_trace_scan', 'service_log_browse',
                        'service_error_log', 'baseline_collect',
                        'jvm_state', 'container_resource', 'k8s_state',
                        'db_state', 'network_layer' }
        AND has_explicit_where_clause_on(target_service)   // 即 WHERE service_name='<RC>'
   )
   IN
     about_to_commit
     AND isolation_intents_for_RC == 0)
```

**触发场景示例**：
- aiq：stage_2 terminator 指向 `S_X`，但 trajectory 里所有针对 `S_X` 的查询都是聚合查询（GROUP BY），从未单独做 `WHERE service_name='S_X'` 类隔离
- thinkdepthai-sonnet：compress 之前 root_causes = `[S_Y]`，但 `S_Y` 从未在 SQL WHERE 子句中作为 explicit filter 出现
- claudecode：commit 前 RC 被 `agent_runner.py` parse 出，对照 trajectory 中的 SQL 字串，发现 RC 名字从未出现在任何 SQL 的 service_name='X' filter 里

---

## Intervention pattern

### 主问（M8 作为 most_critical 时）

> **你即将 commit 的候选，从你做的查询历史看，似乎从来没被你单独隔离检验过——你看到它的所有数据都是汇总查询的结果。如果把这个候选从图里抠掉，剩下的证据还能解释你看到的现象吗？这是反事实检验：能确认候选是真正的故障源还是只是和故障源相关的旁观者。**

**变体**：
- 变体 A（结论前检查，agent 即将提交）：
  > "你即将提交的候选，从你的查询历史看，从来没被你单独隔离过——你看到它的所有数据都来自聚合查询。在最终提交前请反问一次：如果把这个候选从图里抠掉，剩下的证据还能解释你看到的现象吗？这能区分'真正的故障源'和'只是和故障源相关的旁观者'。"
- 变体 B（中期检查，agent 已倾向某候选但还没 commit）：
  > "你目前倾向的候选，到现在为止没被你单独隔离查询过——你的判断都来自汇总数据。在你继续往这个方向走之前，能不能做一次反事实检验：抠掉这个候选，剩下的证据是否仍然合理？"

### 次问（M8 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你的候选从未被单独隔离查询过，可以顺带做一次反事实检验：抠掉它后剩下的证据还合理吗？"

**次问触发条件**：M8 作为次问被加入复合干预，**仅当** L2 对 M8 给出 `match_score ≥ 0.7`（即候选 RC 从未在任何 isolation intent 中被单独 filter）。如果 agent 已对候选做过 isolation 查询，L2 给 M8 低分，**不加 M8 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 用 candidate_RC（agent 自己 draft）+ intent 历史 + WHERE clause 解析，**不和** gt_services 比）
- [x] **Trigger 不含 SQL 字符串**（用 intent 抽象类别 + `has_explicit_where_clause_on()` 谓词；这个谓词内部解析 SQL 但不写 SQL 模板）
- [x] **Trigger 不含具体服务名**（candidate_RC 是变量）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（用"候选"、"它"指代）
- [x] **Intervention 不含错误消息字串**（无）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（"故障源" 是认知词不是拓扑方向词；"旁观者" 是认知比喻——区分"真正出问题"vs"间接相关"）
- [x] **Intervention 用反问 + 多种可能性句式**（"如果把这个候选从图里抠掉..."——经典反事实假设；"真正的故障源还是只是和故障源相关的旁观者"——多种可能对比）
- [x] **agent 可基于自身已做的动作自我修正**（"从你的查询历史看，从来没被你单独隔离过"——引用 agent 自己的 SQL 历史）

**全部 9/9 ✓ → M8 卡片符合 v4 元认知设计原则**

**审核风险点**：
1. **"故障源 vs 旁观者"措辞**：用了"故障源"——这是认知词（"故障的诱因"），不是拓扑方向词。"旁观者"是反概念（中性）。**判定**：通过。但若审核认为"源"概念仍有暗示，可改成"真正出问题的服务还是只是和它有关系的服务"——更冗长但完全无方向性。
2. **"反事实检验"是否暗示具体方法**：主问中提到"反事实检验：抠掉候选看剩余证据"——这是一种推理方法的描述，不是 SQL/操作指令。agent 可以通过 reasoning 进行（"如果不是它，证据还能解释吗"），也可以通过查询新数据进行——决策权在 agent。**判定**：通过。

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✓ 主问候选 | 未独立 induced PD4，但 trigger 通用可启用 |
| thinkdepthai (claude-sonnet-4.6) | ✓ 主问候选 | **60.8% PD4，最高发**；结论前检查时优先 |
| aiq (qwen3.5-plus) | ✓ 主问候选 | 32.7% PD4 |
| claudecode (qwen3.5-plus) | ✓ 主问候选 | 12.7% PD4 + 63 case framework-specific PD4_GTServiceNotTargetedWithWhere 的部分子集（M8 已合并这部分逻辑）|

---

## 期望 wrong→correct 翻盘贡献（初步估计）

| Framework | failure case 总数 | M8 主问命中估计 | M8 翻盘期望（按 v3 类比 ~30%）|
|---|---:|---:|---:|
| thinkdepthai-qwen3.5-plus | 105 | ~25 | ~7 case 翻盘 |
| thinkdepthai-claude-sonnet-4.6 | 50 | ~25（60% 触发率，去重叠后）| ~7 case 翻盘 |
| aiq-qwen3.5-plus | 113 | ~30 | ~9 case 翻盘 |
| claudecode-qwen3.5-plus | 102 | ~30（含 framework PD4 子集）| ~9 case 翻盘 |

**总翻盘期望**：~32 case 跨 4 framework。

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **M1 (Loudness-Anchor)** | M8 触发场景里 candidate RC 经常是 ranking top（即同时触发 M1） | M1 关注"为什么选了 ranking top"，M8 关注"候选未隔离检验"。按 v4 原则 4，**L2 同时命中时 M1 优先作主问，M8 退为次问** |
| **M3 (Output-Graph Consistency)** | M8 候选未隔离 + M3 graph 内部不一致经常共现 | M3 关注 graph 内部一致性，M8 关注 candidate 的反事实检验。可同时命中，按 L2 score 选主 |
| **M4 (Sibling-Disambiguation)** | M8 触发 + 候选名与另一服务相似时也触发 M4 | 维度正交（M8 关注 isolation，M4 关注 sibling），可同时命中 |
| **M2 (Chronic-Noise Skepticism)** | 重叠场景：候选未 isolation + 候选与 chronic noise 相关 → M2 + M8 都命中 | M2 偏 R 层（chronic 模式判别），M8 偏 PD 层（isolation 缺失）。L2 同时命中时按 candidate 是否真在 chronic 服务名册决定主问（在 → M2 主；不在但 isolation 缺失 → M8 主）|

---

## 实施备注

- **关键依赖**：
  - SQL WHERE clause 解析：需要 L1 在 intent 分类时附带提取 WHERE 子句中的 service_name filter（用 sqlparse 库或正则）
  - candidate_RC 的"未被隔离"需要遍历整个 trajectory 的 SQL，不只是最近 K round
- **L2 vs M1 消歧 prompt**：opus-4.7 prompt 应明确："如果 candidate 在 ranking top → M1 主 + M8 次（按 v4 原则）；如果 candidate 不在 ranking 但 isolation 缺失 → M8 主"
- **离线重放验证**：在 372 已标注 case 上跑 trigger，统计 (precision, recall) 相对于 PD_NamedCandidateNotIsolated 标注

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-3 阶段输出） |
