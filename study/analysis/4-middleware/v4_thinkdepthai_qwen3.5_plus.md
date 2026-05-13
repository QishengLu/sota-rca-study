# v4 thinkdepthai 适配层（qwen3.5-plus + claude-sonnet-4.6）

**Plan**: [/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md](/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md)
**设计原则**: [v4_principles.md](v4_principles.md)
**维度库**: [v4_dimensions/](v4_dimensions/)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-5 阶段）

---

## 适用 case

| Agent (exp_id) | failure case 数 | 备注 |
|---|---:|---|
| thinkdepthai-qwen3.5-plus | 105 | v3 实测 baseline 49/105 = 46.7% 翻盘 |
| thinkdepthai-claude-sonnet-4.6 | 51 | 无 v3 baseline；v4 首次启用 |

**共用同一适配层**：两者都基于 LangGraph + ReAct + think_tool 架构，注入机制一致；差异仅在维度启用子集的优先级（如 M3 在 sonnet 上 U3=44% 最高发，应被 opus-4.7 优先识别）。

---

## 三层管线（沿用 v3，L2/L3 合并）

```
agent.tool_node 后：
  L1: SQL→intent batch 分类（19 类抽象意图）              [LLM: claude-opus-4-7]
      reasoning 提取（think_tool 反思 / assistant.content）
      R-T 利用率提取                                       [纯代码]
        ↓
  中期检查触发（全 case 全程仅 1 次，触发时机⏸ 见末尾"中期检查点"小节）
        ↓
  L2+L3 合并: 自主判断 + 干预生成                          [LLM: claude-opus-4-7 一次调用]
      → 输入: A1-A6 + B1-B2,B4-B7 + C1-C3 (B3 缺；中期没 graph)
      → 输出: JSON {triggered, primary, secondary, intervention_text, brief_reasoning}
        ↓
  Python 中间件: intervention_text → HumanMessage → state["researcher_messages"]
      → LangGraph add_messages reducer 追加到对话末尾
      → 下一轮 llm_call 节点 agent 看到完整历史 + 末尾的 intervention

agent.compress_research 前（结论前 check point）：
  pre_conclusion_check_node (新增节点，修 v3 Bug 1)
        ↓
  L2+L3 合并 (同上)
      → 输入: A1-A6 + B1-B2,B4-B7 + C1-C3
      → 注意 B3 (draft graph) 在 thinkdepthai 此时**没有结构化 graph**
        因为 compress_research 还没运行。M3 走 reasoning 文本 trigger（D-3 修订）
        ↓
  intervention_text → HumanMessage → state["researcher_messages"]
        ↓
  loopback 到 llm_call (让 agent 响应干预后再决定是否进 compress)
```

### 层 vs 次（沿原则 5）
- **L1 / L2+L3 三层管线** → v3 三层架构 + L2/L3 合并为一次 opus-4.7 调用
- **中期检查次数** → 1 次（v3 是 2 次）
- **结论前检查次数** → 1 次（不变）
- **总干预次数** → ≤ 2

---

## 注入接口（LangGraph 节点级实现）

### 中期检查（在 tool_node → llm_call 之间）

中期触发逻辑作为 `should_check_mid` 谓词，由代码判断；触发时调 `mid_check_node`，节点 return value 走 LangGraph reducer：

```python
# 伪代码示意
def mid_check_node(state: ResearcherState):
    snapshot = build_trajectory_snapshot(state, check_point="mid")
    response = call_opus47_with_v4_interface(snapshot, framework="thinkdepthai")
    if not response["triggered"]:
        return {}   # 不注入任何 message
    intervention_msg = HumanMessage(content=response["intervention_text"])
    # 更新 per-case 状态
    update_case_intervention_state(state.case_id, "mid", response)
    return {"researcher_messages": [intervention_msg]}   # 走 reducer 追加
```

### 结论前检查（修 v3 Bug 1：从 conditional edge 改为真节点）

```python
# v3 (有 Bug 1):
def should_continue_mw(state):
    if state["researcher_messages"][-1].tool_calls:
        return "tool_node"
    intervention = pipeline.check_before_conclusion()
    if intervention:
        state["researcher_messages"].append(HumanMessage(...))   # ← BUG: mutate state
        return "llm_call"
    return "compress_research"

# v4 (修复版):
def pre_conclusion_check_node(state: ResearcherState):
    snapshot = build_trajectory_snapshot(state, check_point="conclusion")
    response = call_opus47_with_v4_interface(snapshot, framework="thinkdepthai")
    if not response["triggered"]:
        return {}
    intervention_msg = HumanMessage(content=response["intervention_text"])
    update_case_intervention_state(state.case_id, "conclusion", response)
    return {"researcher_messages": [intervention_msg]}

def should_continue_mw_v4(state):
    if state["researcher_messages"][-1].tool_calls:
        return "tool_node"
    return "pre_conclusion_check"

def after_pre_conclusion(state):
    last = state["researcher_messages"][-1]
    if isinstance(last, HumanMessage) and "Investigation Advisor" in last.content:
        return "llm_call"   # 有干预，回 llm_call 让 agent 响应
    return "compress_research"   # 无干预，进 compress

builder.add_node("pre_conclusion_check", pre_conclusion_check_node)
builder.add_conditional_edges("llm_call", should_continue_mw_v4, {...})
builder.add_conditional_edges("pre_conclusion_check", after_pre_conclusion, {...})
```

---

## 必修 v3 的三个 bug（D-5 阶段列出，由 Phase 8 实施修）

### Bug 1 — `should_continue_mw` 在 conditional edge mutate state

- **位置**: `Deep_Research/agent_runner.py:174-181`
- **症状**: conclusion check 注入的 HumanMessage 不经过 LangGraph add_messages reducer，trajectory 序列化看不到，无法离线审计
- **v4 修复**: 见上面 `pre_conclusion_check_node` 真节点设计

### Bug 2 — `_run_conclusion_cycle` 死代码

- **位置**: `Deep_Research/middleware/pipeline.py:193-212`
- **症状**: v3 conclusion check 直接返回硬编码的 `_CONCLUSION_PROMPT`，从不调用 ConclusionDetector / L3 generator
- **v4 修复**: v4 用 opus-4.7 一次调用替代整个 v3 detector + generator 链路；`_run_conclusion_cycle` 整体替换为 `pre_conclusion_check_node` + `call_opus47_with_v4_interface`

### Bug 3 — v3 检查点 [37, 44] 错过 42% 早收敛 case

- **症状**: 105 case 中 44 case (42%) 在 query 37 之前已 conclusion，v3 中期检查根本没触发
- **v4 修复方向**: 修订原则 5 改为 1+1 干预节制；中期触发时机 D-7.5 阶段统一定（候选 A: framework P25 / B: 动态触发 / C: 取消中期）

---

## 启用维度子集（按原则 7 完整分配矩阵）

### 中期检查的 L2 评估池

```
主用维度（opus-4.7 优先评估）：
  M6 (Baseline-Contrast Reflex)
  M7 (Layer-Coverage Reflex)
  M9 (Investigation Stagnation)

备用维度（需更明确证据才上位作主问）：
  M1 (Loudness-Anchor Self-check)
  M2 (Chronic-Noise Skepticism)
  M3 (Output-Graph Internal Consistency) — 走 reasoning 文本 trigger
  M4 (Sibling-Disambiguation Awareness)
  M5 (Silence ≠ Health)
  M10 (Premature Commitment) — 仅 query_count < P25 时启用
```

### 结论前检查的 L2 评估池

```
主用维度（opus-4.7 优先评估）：
  M1 (Loudness-Anchor Self-check)
  M2 (Chronic-Noise Skepticism)
  M3 (Output-Graph Internal Consistency) — 走 reasoning 文本 trigger
  M4 (Sibling-Disambiguation Awareness)
  M5 (Silence ≠ Health)
  M8 (Hypothesis-Counterfactual)
  M10 (Premature Commitment)

备用维度（补救）：
  M6 (Baseline-Contrast Reflex)
  M7 (Layer-Coverage Reflex)
  M9 (Investigation Stagnation)
```

### thinkdepthai 不启用的维度

- A1-A5（aiq 特有）— 不适用
- C2（claudecode 特有）— 不适用

### 维度优先级提示（给 opus-4.7 的 framework-specific hint）

中间件 system prompt 中在 A2/A3 池后追加 thinkdepthai-specific 提示：

```
[thinkdepthai-specific 提示]
- thinkdepthai-qwen3.5-plus: U1 (LoudnessAnchor) 和 U2 (ChronicNoise)
  在 v1 失败标注中分别占 41.9% 和 24.8%，是高发模式；评估时优先看 M1/M2 的命中
- thinkdepthai-claude-sonnet-4.6: U3 (EdgeDirection) 占 44.0% 最高发；评估时优先看 M3 的命中
- M5 (Silence-as-Health) 在 thinkdepthai-qwen 上 U5 占 16.2%，是该 framework 独特高发的维度，
  其他 framework 接近 0%；reasoning 文本中含健康推断词时强烈考虑 M5
```

---

## opus-4.7 调用接口（应用 v4_principles.md 原则 7 完整规范）

### 输入信息清单（thinkdepthai 实例化）

#### 中期检查时

```yaml
# A 维度库（按 thinkdepthai × 中期 实例化）
A1_check_point: "mid"
A2_primary_pool: [M6, M7, M9]
A3_secondary_pool: [M1, M2, M3, M4, M5, M10]
A4_dimension_cards: { M6: "...", M7: "...", M9: "...", M1: "...", ... }   # 关键段
A5_conflict_rules: |
  - M6 vs M2: 同时命中时 M2 优先作主问（R 层反思 > PD-pure 提醒）
  - M9 vs M10: 互斥（重复探查 → round 多 → 不会 premature）
  - M1 vs M8: 同时命中时 M1 优先（loudness 反思 > counterfactual）
  - 等等
A6_intervention_rules: { v4 原则 4 八条干预守则 }

# B trajectory snapshot
B1_intent_log: [(round, intent_type, target_service), ...]   # 完整序列
B2_reasoning: { recent_5_rounds_full: "...", earlier_summary: "..." }
B4_where_filters: ["S1", "S2", ...]                          # 所有 WHERE service_name 集合
B5_observed_services: ["S1", "S2", ..., "S_X"]               # 所有出现过的服务名
B6_counts: { round_count: 22, tool_call_count: 28,
             intent_type_counts: { error_log_overview: 8, baseline_contrast: 0, jvm_state: 0, ... } }
B7_ranking_top3: [
  { round: 12, intent: "error_rate_scan", top3: ["S_A", "S_B", "S_C"] },
  { round: 18, intent: "latency_ranking", top3: ["S_A", "S_D", "S_E"] },
  { round: 21, intent: "error_rate_scan", top3: ["S_A", "S_F", "S_G"] }
]
# B3 (draft graph) — 中期没有，不给

# C 上下文
C1_framework: "thinkdepthai-qwen3.5-plus"   # 或 "thinkdepthai-claude-sonnet-4.6"
C2_prior_intervention_history: { mid_check: null }   # 中期是首次 check point，无之前历史
C3_framework_priors: {
    failed_case_query_count_P25: <待 D-7.5 算>,
    failed_case_query_count_P50: <待 D-7.5 算>
}
```

#### 结论前检查时

```yaml
# 大部分同中期，差异：
A1_check_point: "conclusion"
A2_primary_pool: [M1, M2, M3, M4, M5, M8, M10]
A3_secondary_pool: [M6, M7, M9]

# B3 仍不给（thinkdepthai 在 compress 之前没结构化 graph）
# M3 走 reasoning 文本 trigger（D-3 修订）

C2_prior_intervention_history: {
    mid_check: {
        triggered: true,
        primary: "M1",
        secondary: ["M6"],
        intervention_text: "你最近几轮一直在按错误数排名...",
        round: 22
    }
}   # 若中期触发过则填上；否则 mid_check: null
```

### 输出格式

按 v4_principles.md 标准 JSON schema：

```json
{
  "triggered": true,
  "primary_dimension": "M2",
  "secondary_dimensions": ["M7"],
  "intervention_text": "你即将提交根因，但你的整个调查过程没做过一次正常时段 vs 异常时段的对比...\n\n另外你的查询都集中在应用层...",
  "brief_reasoning": "agent 即将 commit S_A，trajectory 中 baseline_contrast=0 + abnormal_only_intents=14，且未碰运行时层；M2 主、M7 次"
}
```

---

## 期望 wrong→correct 翻盘贡献

基于 v3 实测 + D-1..D-4 累积维度估计：

| Framework | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 | M9 | M10 | 合计（去重叠粗估） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| thinkdepthai-qwen3.5-plus | ~9 | ~11 | ~3 | ~1 | ~7 | ~20 | ~12 | ~7 | ~8 | ~17 | **~50-60** |
| thinkdepthai-claude-sonnet-4.6 | ~3 | ~3 | ~9 | ~1 | ~1 | ~5 | ~4 | ~7 | ~6 | ~4 | **~20-30** |

**两个 thinkdepthai exp_id 合计 wrong→correct 翻盘期望: ~70-90 case 跨 156 failed case (45-58%)**。

对照基线：
- v3 实测 thinkdepthai-qwen 105 case 翻 49 (46.7%) — v4 应能维持或边际提升（修 Bug + 加 M5/M7/M8/M10/M3 新维度）
- thinkdepthai-sonnet 51 case 无 v3 baseline，v4 首跑目标 ≥ 30% (~15 case)

---

## ✓ 中期检查点触发时机（D-7.5 已锁定）

**策略**：候选 A（correct-case P25 anchor）

**依据**（详见 [v4_mid_check_strategy.md](v4_mid_check_strategy.md)）：
- effective_rounds 分布（来自 `meta.cost_metrics.effective_rounds`）：
  - thinkdepthai-qwen failed: P25=41, P50=51, P75=60, max=86
  - thinkdepthai-qwen correct: P25=32, P50=42, P75=52, max=91
  - thinkdepthai-sonnet failed: P25=30, P50=36, P75=44, max=70
  - thinkdepthai-sonnet correct: P25=22, P50=28, P75=36, max=123
- thinkdepthai 的 failed case 比 correct 更长（P50 51 vs 42 / 36 vs 28）——失败常伴长跑重复探查（M9 模式）
- 用 **correct case P25 作 anchor**（而非 failed P25）：correct P25 代表"成功 agent 的自然 mid-investigation 时刻"，对 failed case 介入恰好 early enough 能纠偏

**具体阈值**：

| Framework | `mid_check_trigger_round_count` | 剩余空间（failed P50 - 触发点）|
|---|:---:|---:|
| thinkdepthai-qwen3.5-plus | **30**（对齐 correct P25=32 + 略早）| 51 - 30 = 21 round 剩余 |
| thinkdepthai-claude-sonnet-4.6 | **22**（对齐 correct P25=22）| 36 - 22 = 14 round 剩余 |

**实施语义**：`state.round_count >= threshold AND not state.mid_check_done` 时触发；round 计数 = `len(带 tool_calls 的 AIMessage)`。若 case 在触发值前自然 commit，中期不触发（由结论前检查覆盖）。

---

## 验证（不在 D-5 范围）

D-7.5 完成 + 三 framework 适配层都定后，按 plan Part E 走：

1. **离线重放**: 在 156 已标注 case 上跑 v4 trigger，对比 v1 baseline 的失败模式标注
2. **A/B 翻盘对照**: thinkdepthai-qwen3.5-plus 105 case 重跑 baseline vs MW-v4，对照 v3 49/105 = 46.7%
3. **success-case 回归测试**: 50 个 success sample（v3 没跑过）→ 验证 correct → wrong ≤ 1
4. **thinkdepthai-sonnet 首测**: 51 case 跑 baseline vs MW-v4，目标翻盘 ≥ 15 (30%)

---

## 关键文件路径索引

**v4 设计参考**：
- 设计原则: [v4_principles.md](v4_principles.md)
- 维度库: [v4_dimensions/](v4_dimensions/) (M1-M10 共 10 张卡)

**v3 实现参考（v4 复用 + 修 bug）**：
- [Deep_Research/middleware/CLAUDE.md](../../Deep_Research/middleware/CLAUDE.md) — v3 设计文档 + 已知 bug
- [Deep_Research/middleware/pipeline.py](../../Deep_Research/middleware/pipeline.py) — L1/L2/L3 三层管线
- [Deep_Research/middleware/state.py](../../Deep_Research/middleware/state.py) — investigation 状态追踪
- [Deep_Research/agent_runner.py](../../Deep_Research/agent_runner.py) — LangGraph 节点定义（含 Bug 1 修复点）

**待写**:
- [v4_aiq_qwen3.5_plus/](v4_aiq_qwen3.5_plus/) — D-6 阶段
- [v4_claudecode_qwen3.5_plus/](v4_claudecode_qwen3.5_plus/) — D-7 阶段
- [v4_mid_check_strategy.md](v4_mid_check_strategy.md) — D-7.5 三 framework 中期触发统一决策

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-5 阶段输出）；中期检查触发时机暂留空，D-7.5 统一决策 |
