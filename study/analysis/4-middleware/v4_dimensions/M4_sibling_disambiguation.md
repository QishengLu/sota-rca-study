# M4 — Sibling-Disambiguation Awareness

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-2 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | 372 case 中数量 |
|---|---|---|---:|
| **R 层** | `U4_NameTwinSiblingConfusion` | agent 选了一个名字与另一个出现过的服务非常相似的服务作 RC（如 ts-food-service vs ts-station-food-service），且没做名称对比验证 | **18** |
| **PD 层** | 无对应 PD（v4 新增维度，未在原 PD taxonomy 中独立成类） | — | (无) |
| **D 层** | D6 (NameTwinOnPath) — 数据集中本来就存在 name twin 服务对，作为"多种可能性"素材 | (背景) |

**对应失败 case 数（M4 主问触发的初步估计）**：
- 宽松命中 (U4 单独)：18 case
- M4 主问的目标 case 池：~15-25 case（U4 + 部分 U3 中 sibling-of-callee 类型）

**Per-framework 分布**（来自 unified_R.md）：
- aiq-qwen3.5-plus: 8 / 113 = 7.1%（标记为 analytical_only：FP 率较高）
- claudecode-qwen3.5-plus: 10 / 102 = 9.8%
- thinkdepthai-claude-sonnet-4.6: 0 / 50 = 0%
- thinkdepthai-qwen3.5-plus: 0 / 105 = 0%

**Framework 启用注意**：U4 在 thinkdepthai 上为 0，可能不是 thinkdepthai 不犯这种错，而是 sonnet/qwen 把它归到了 U1 (loudness-anchor) 或 U3 (edge-direction) 里——M4 trigger 是字符串相似度，跨 framework 通用，可全 framework 启用。

---

## Cognitive vocabulary

**这种认知模式是什么样**：

很多微服务项目里有名字非常相似的服务对（differ by prefix/infix/suffix 一两个 token）：
- `service-X` vs `inside-service-X`
- `order-X` vs `order-X-other`
- `route-X-A` vs `route-X-B`

agent 在调查中可能同时遇到这两个服务，但**最终选了名字里更短/更熟悉/更"像主名"的那个**作为 RC，而真正的故障在另一个变体上。这是 substring-matching 启发式失败的典型案例：agent 看到候选名字里有"food"，就和数据里所有带"food"的服务做模糊关联，但忽略了"station-food"和"food"是两个完全不同的服务。

**反思的认知动作**：commit 之前主动检查"**我的候选名字和另一个我见过的服务很像，是不是混了？**"——这一步不需要 agent 知道哪个对，只需要意识到"存在歧义" 并主动 disambiguate。

---

## Trigger abstract（运行时可观察）

```pseudo
trigger_M4(state) :=
  (LET about_to_commit       = state.is_at_check_point AND state.draft_root_causes != []
   LET candidate_RC          = state.draft_root_causes[0]
   LET observed_services     = state.observed_service_names   // trajectory 中所有出现过的 service_name
                                                              // 来自 SQL 结果、reasoning 引用、tool output
   LET similar_others        = [
        s FOR s IN observed_services
        WHERE s != candidate_RC
        AND jaro_winkler_similarity(candidate_RC, s) >= 0.85
   ]
   LET disambiguation_intents = COUNT(state.intent_log WHERE
        intent IN { 'service_trace_scan', 'service_log_browse',
                    'service_error_log', 'baseline_collect' }
        AND target_services_count >= 2   // 同一 SQL 同时查多个服务名
        AND { candidate_RC, similar_others[0] } SUBSET_OF target_services
   )
   IN
     about_to_commit
     AND LENGTH(similar_others) >= 1
     AND disambiguation_intents == 0)
```

**触发场景示例**：
- aiq：candidate = `S1`，trajectory 中也出现过 `prefix-S1` 和 `S1-suffix`，agent 从未做 `WHERE service_name IN (S1, prefix-S1)` 类对比查询
- claudecode：agent 选了 `service-main`，但 trajectory 中也提到 `service-main-other`，没显式 contrast
- thinkdepthai：相似度 trigger 命中，但需要 reasoning 文本中 agent 不曾明确区分过这两个名字

---

## Intervention pattern

### 主问（M4 作为 most_critical 时）

> **你即将选的候选，名字和另一个出现在你查询数据中的服务非常相像（只差几个字符）。这种相似的服务名容易被混淆——你的判断是基于哪些证据明确属于这一个而不是另一个？你做过把两个名字相似的服务并排对比的查询吗？**

**变体**：
- 变体 A（结论前检查，agent 即将提交）：
  > "你即将提交的候选服务名，和另一个出现过的服务名只差几个字符，非常容易混淆。在最终提交前请反问一次：你的证据是确实针对这一个，还是可能把两个名字相近的服务的数据混在一起了？能不能用一次明确把两个名字并排查询的对比验证一下？"
- 变体 B（中期检查，agent 还在调查阶段但已倾向某候选）：
  > "你目前倾向的候选，名字和另一个你见过的服务很像。在你继续往这个方向走之前，能不能先把两个名字相近的服务并排对比一次，确认你的证据确实属于这一个？"

### 次问（M4 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你的候选名字和另一个出现过的服务很相近，可以顺带做一次明确的对比，避免混淆。"

**次问触发条件**：M4 作为次问被加入复合干预，**仅当** L2 对 M4 给出 `match_score ≥ 0.7`（即 L2 真的检测到候选名与另一服务名 Jaro-Winkler ≥ 0.85 + 无显式 disambiguation intent）。如果 candidate 没有 similar sibling 在 trajectory 中出现，**不加 M4 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 用 `observed_service_names`（agent 自己的 SQL 历史）+ `candidate_RC`（agent 自己的 draft）+ Jaro-Winkler（通用算法），**不和** `gt_services` 比，**不查询** name twin GT 列表）
- [x] **Trigger 不含 SQL 字符串**（用 intent 抽象类别 + target_services_count 字段访问）
- [x] **Trigger 不含具体服务名**（`candidate_RC`、`similar_others` 都是变量；Jaro-Winkler 是函数调用）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（无 `ts-food-service` / `ts-station-food-service` 等具体 twin 对；只用"另一个出现过的服务"、"名字相近的服务"）
- [x] **Intervention 不含错误消息字串**（无）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（无方向性概念；只用"对比"、"并排查询"、"混淆"）
- [x] **Intervention 用反问 + 多种可能性句式**（"是基于哪些证据明确属于这一个而不是另一个"、"可能把两个名字相近的服务的数据混在一起了"）
- [x] **agent 可基于自身已做的动作自我修正**（"你即将选的候选，名字和另一个出现在你查询数据中的服务非常相像"——引用 agent 自己的 trajectory observations）

**全部 9/9 ✓ → M4 卡片符合 v4 元认知设计原则**

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✓ 主问候选 | 标注中 0% U4，但实测可能存在被归入 U1/U3 的 case；通用 trigger 全 framework 启用 |
| thinkdepthai (claude-sonnet-4.6) | ✓ 主问候选 | 同上 |
| aiq (qwen3.5-plus) | ✓ 主问候选 | 7.1% U4（FP 率 60%，需 D-6 阶段额外校准 trigger 阈值）|
| claudecode (qwen3.5-plus) | ✓ 主问候选 | 9.8% U4 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

| Framework | failure case 总数 | U4 占比 | M4 主问命中估计 | M4 翻盘期望（按 30% 翻盘率，因 U4 标注 FP 率较高） |
|---|---:|---:|---:|---:|
| thinkdepthai-qwen3.5-plus | 105 | 0% | ~5（被 U1/U3 吸收的隐含 case） | ~1-2 case 翻盘 |
| thinkdepthai-claude-sonnet-4.6 | 50 | 0% | ~3 | ~1 case 翻盘 |
| aiq-qwen3.5-plus | 113 | 7.1% | ~8 | ~2-3 case 翻盘 |
| claudecode-qwen3.5-plus | 102 | 9.8% | ~10 | ~3 case 翻盘 |

**总翻盘期望**：~7-9 case 跨 4 framework。M4 是 v4 维度库中翻盘期望最低的之一，因为 U4 整体 N 小（18 case）。但其 trigger 通用性强（字符串相似度 + intent 缺失），适合作为 commit-前检查的"轻量补检"。

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **M8 (Hypothesis-Counterfactual)** | M4 触发时通常 PD_NamedCandidateNotIsolated 也命中（candidate 没被独立隔离 = 也没被 disambiguate） | M4 关注名字相似 + 缺 contrast；M8 关注 candidate 独立检验。可同时命中，L2 选 most_critical |
| **M1 (Loudness-Anchor)** | M4 case 中 candidate 不一定是 ranking top（可能 agent 因为 substring 联想选的）| 互不冲突，可同时命中 |

---

## 实施备注

- **关键依赖**：
  - 字符串相似度算法：用 `python-Levenshtein` 或 `jellyfish` 库的 Jaro-Winkler；阈值 0.85 是 v3 经验值，D-2 审核可调
  - `state.observed_service_names`：所有 trajectory 中出现过的 service_name，需要在 L1 副作用中累积（每次 SQL 结果解析时把 service_name 列入这个集合）
- **trigger 阈值校准**：aiq 标注里 U4 FP 率 60%，意味着原 R 标注的相似度判断不准；M4 用 Jaro-Winkler ≥ 0.85 是较严的阈值，可能 recall 偏低但 precision 较好。D-6 阶段可以试 ≥ 0.80 看 recall 提升幅度
- **离线重放验证**：在 372 已标注 case 上跑 trigger，统计 (precision, recall) 相对于 U4 标注。注意 U4 在 thinkdepthai 标注 = 0，所以 thinkdepthai 上 recall 无意义；只看 aiq + claudecode

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-2 阶段输出） |
