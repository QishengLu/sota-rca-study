# v4 元认知维度库 — 速查表

**Plan**: [/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md](/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22

---

## 维度库概览

10 个**框架无关**的元认知维度，从 D / R / PD 三层失败分类提炼。每个维度独立审核（独立卡片）。

中间件 L2 层用 claude-opus-4-7 对每个维度独立给出 `match_score ∈ [0, 1]`：
- 主问 = match_score 最高且 ≥ 0.7 的维度（如全维度都 < 0.7 则**整个干预不触发**）
- 次问 = 剩余 match_score ≥ 0.7 的维度（封顶 3 个；**可能为 0**）

L3 层按维度卡片的 `intervention pattern` 模板生成最终干预 prompt。**次问不强制凑数**：L2 只检测到 1 个高置信命中时，干预只有主问。

---

## 速查表

| ID | 名称 | 来源（D/R/PD） | 触发抽象（运行时可观察） | 主问句模板 | 卡片 |
|----|------|---------------|------------------------|-----------|------|
| **M1** | Loudness-Anchor Self-check | U1 + PD_NoFaultLayerMetricProbe | 即将 commit + 最近 K round 触发 ranking 类 intent + 候选 RC 是 ranking SQL 的 top 行 | "排名靠前不一定是故障来源——也可能是别的原因放大了它的错误。你能反过来问：如果不是它，会是什么？" | [M1.md](M1_loudness_anchor_selfcheck.md) |
| **M2** | Chronic-Noise Skepticism | U2 + PD_NoBaselineContrast | 即将 commit + `baseline_contrast` intent 全程 0 | "你看到的错误，有没有可能在没有故障时也是这样的？" | [M2.md](M2_chronic_noise_skepticism.md) |
| **M3** | Output-Graph Internal Consistency | U3 + PD_NoCallTreeBuild | draft 输出图含 agent 自标 UNAVAILABLE/RESTARTING 节点但不在 root_causes | "被你自己标问题的节点没列入根因——这种判断的支撑证据是什么？" | M3.md (D-2) |
| **M4** | Sibling-Disambiguation Awareness | U4 (无对应 PD，新增) | 候选 RC 与某 trajectory 出现过的服务名相似度 ≥0.85 + 无显式名称对比 intent | "你的候选服务名和另一个出现过的服务很相近——会不会混了名字相似的两个？" | M4.md (D-2) |
| **M5** | Silence ≠ Health | U5 + 现 v3 M3 | reasoning 文本含健康类推断词 + 该服务从未被独立检验过其活动度 | "除了'没错误'之外你看到它有正常活动迹象吗？它有没有可能根本没在工作？" | M5.md (D-2) |
| **M6** | Baseline-Contrast Reflex | PD_NoBaselineContrast 直接 | abnormal-数据 intent ≥10 次 + baseline-类 intent 全程 0 | "你查了大量异常时段数据，但还没对照过正常时段——你看到的'异常'本身在正常时段会不会也是这样？" | M6.md (D-3) |
| **M7** | Layer-Coverage Reflex | PD_NoFaultLayerMetricProbe (GT-脱敏) | 应用层 intent ≥N + 运行时层 intent 全部为 0 | "你查了大量应用层数据，但还没碰过运行时层。你确定问题一定不在那些层？" | M7.md (D-3) |
| **M8** | Hypothesis-Counterfactual | U1/U2/U5 综合 + PD_NamedCandidateNotIsolated | 即将 commit + 候选 RC 从未在独立隔离 intent 中被单独检验 | "如果把这个候选从图里抠掉，剩下的证据还能解释你看到的现象吗？" | M8.md (D-3) |
| **M9** | Investigation Stagnation | 沿袭 v3 B1（独立于 D/R/PD 重构）| 最近 K round ≥80% intent 全在同一服务上重复 + K-1 个 round 没新 intent 类别 | "最近几轮你都在同一服务上重复，没看到新东西——是不是该换角度？" | M9.md (D-4) |
| **M10** | Premature Commitment | PD_LateExplorationDegenerate 反向 + R_correct_then_reversed 提示 | round count 显著低于 framework failed case 的 P25 + 无运行时层 intent | "你的调查比同类任务短很多就要 commit——真的证据充分了，还是被早期信号锚住了？" | M10.md (D-4) |

---

## 维度间关系图

```
                     [PD 层 — 行为遗漏检测]
                     M6 (Baseline)    M7 (Layer)    M9 (Stagnation)
                          ↓               ↓               ↓
                          └─ 主问 → ┐    └─ 主问 →┐    └─ 主问 → ┐
                                    │             │              │
[R 层 — 推理反思]                   ↓             ↓              ↓
M1 (LoudnessAnchor) ──主问──────→ commit-时 ─────→ commit-前 ─→ 任意时刻
M2 (ChronicNoise)   ──主问──────→ commit-时
M3 (OutputGraph)    ──主问──────→ commit-前
M4 (SiblingTwin)    ──主问──────→ commit-前
M5 (SilenceHealth)  ──主问──────→ 任意时刻
M8 (Counterfactual) ──主问──────→ commit-前
M10 (Premature)     ──主问──────→ commit-时

[D 层 — 数据警示] (融合在 R 层维度的"多种可能性"句式中，无独立维度)
D1 silence → M5 主问句中体现
D3 chronic → M2 主问句中体现
```

**冲突候选**（实施 L2 时需消歧）：
- **M1 vs M8** — 都关注 commit 前对候选的反向检查；M1 偏 R 层（loudness 启发式批判），M8 偏 PD 层（counterfactual 隔离漏做）。L2 同时命中时 M1 优先作为主问。
- **M2 vs M6** — M6 是 PD-pure 检测（baseline_contrast intent = 0 即触发），M2 是 R 层（baseline 缺失 + commit 候选与噪声相关）。L2 同时命中时 M2 优先作为主问，M6 退为次问。
- **M5 vs M10** — M10 是行为统计（round 短），M5 是文本特征（健康推断词）。两者基本不重叠，可同时主问/次问。
- **M9 vs M10** — M9 是"重复但无进展"，M10 是"过短就 commit"。互斥（重复探查 → 必然 round 多 → 不会触发 M10）。

---

## 适用 framework × 维度矩阵（含 check point 分配）

详见 [../v4_principles.md 原则 7](../v4_principles.md)。这里给一张速查矩阵：每个维度在每个 framework 上的启用状态 + check point 角色（中期主用 / 中期备用 / 结论前主用 / 结论前备用 / 不评估）。

| 维度 | thinkdepthai (qwen+sonnet) | aiq (qwen) | claudecode (qwen) | 中期主/备 | 结论前主/备 |
|------|:---:|:---:|:---:|:---:|:---:|
| M1 | ✓ | ✓ | ✓ | △ 备用 | ✅ 主用 |
| M2 | ✓ | ✓ | ✓ | △ 备用 | ✅ 主用 |
| M3 | ✓ | △ 待 D-6 确认 | ✓ | ✗ | ✅ 主用 |
| M4 | ✓ | ✓ | ✓ | △ 备用 | ✅ 主用 |
| M5 | ✓ | ✓ | ✓ | ✅ 可用 | ✅ 可用 |
| M6 | ✓ | ✓ | ✓ | ✅ **主用** | △ 补救 |
| M7 | ✓ | ✓ | ✓ | ✅ **主用** | △ 补救 |
| M8 | ✓ | ✓ | ✓ | ✗ | ✅ 主用 |
| M9 | ✓ | ✓ | ✓ | ✅ **主用** | △ 补救 |
| M10 | ✓ | △ aiq 触发率低 | ✓ | △ 仅 P25 满足时 | ✅ **主用** |
| **A1** (aiq 特有) | — | ✅ stage_0 末尾主用 | — | ✅ **主用** | ✗ |
| **A2** (aiq 特有) | — | ✓ | — | ✗ | ✅ 主用 |
| **A3** (aiq 特有) | — | ✓ | — | ✗ | ✅ 主用 |
| **A4** (aiq 特有) | — | ✓ | — | △ 备用 | ✅ 主用 |
| **A5** (aiq 特有) | — | ✓ | — | ✗ | ✅ 主用 |
| **C2** (claudecode 特有) | — | — | ✓ | ✅ 主用 | △ 补救 |

**legend**：
- 启用：✓ 启用；△ 降权或选择性启用；✗ 不启用
- check point：✅ 主用（阈值 ≥ 0.7）；△ 备用（阈值 ≥ 0.85）；✗ 不评估

---

## 中期 / 结论前 L2 评估池（按 framework 速查）

### 中期检查（每 framework 一次，全 case 全程仅 1 次）

| Framework | L2 评估的**主用**维度 | **备用** |
|---|---|---|
| thinkdepthai (qwen + sonnet) | M6, M7, M9 | M1, M2, M4, M5, M10 |
| aiq (qwen) | M6, M7, M9, **A1** | M1, M2, M4, M5, M10, A4 |
| claudecode (qwen) | M6, M7, M9, **C2** | M1, M2, M4, M5, M10 |

### 结论前检查（每 framework 一次，全 case 全程仅 1 次）

| Framework | L2 评估的**主用**维度 | **备用** |
|---|---|---|
| thinkdepthai (qwen + sonnet) | M1, M2, M3, M4, M5, M8, M10 | M6, M7, M9 |
| aiq (qwen) | M1, M2, M5, M8, M10, **A2, A3, A4, A5** | M3 (待 D-6 确认), M4, M6, M7 |
| claudecode (qwen) | M1, M2, M3, M4, M5, M8, M10 | M6, M7, **C2** (补救), M9 |

---

## 卡片审核进度

| 卡片 | 阶段 | 状态 |
|---|---|---|
| M1 | D-1 | ✅ 已写，⏳ 待审核 |
| M2 | D-1 | ✅ 已写，⏳ 待审核 |
| M3 | D-2 | ✅ 已写，⏳ 待审核 |
| M4 | D-2 | ✅ 已写，⏳ 待审核 |
| M5 | D-2 | ✅ 已写，⏳ 待审核 |
| M6 | D-3 | ✅ 已写，⏳ 待审核 |
| M7 | D-3 | ✅ 已写，⏳ 待审核 |
| M8 | D-3 | ✅ 已写，⏳ 待审核 |
| M9 | D-4 | ✅ 已写，⏳ 待审核 |
| M10 | D-4 | ✅ 已写，⏳ 待审核 |
