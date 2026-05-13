# v4 aiq 适配层（qwen3.5-plus）

**Plan**: [/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md](/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**维度库**: [../v4_dimensions/](../v4_dimensions/)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-6 阶段）

---

## 适用 case

| Agent (exp_id) | failure case 数 | 备注 |
|---|---:|---|
| aiq-qwen3.5-plus | 113 | v1 failure_analysis 已冻结（AC@1 77.4%）；本次 v4 首次启用元认知中间件 |

**关键特性**：aiq 的 5 阶段 LangGraph pipeline（generate_queries → data_research → build_graph → reflect_on_graph (2 iters) → finalize_summary）**天然提供了 stage 边界这一结构化的介入点**。相较于 thinkdepthai / claudecode 的"ReAct 推理中插入"，aiq 可以在 stage 边界注入，agent 推理流被自然打断并切换到下一 stage。

---

## 三层管线（沿用 v3，L2/L3 合并）

```
stage_0 main 结束（data_research terminator）后：
  L1: SQL→intent batch 分类（19 类）                    [LLM: claude-opus-4-7]
      reasoning 提取（think_tool 反思 + assistant.content）
      R-T 利用率提取                                     [纯代码]
        ↓
  中期检查触发（全 case 全程仅 1 次）
  **介入点：stage_0_main terminator 之后 / build_graph 之前**
        ↓
  L2+L3 合并: 自主判断 + 干预生成                         [LLM: claude-opus-4-7 一次调用]
      → 输入: A1-A6 + B1-B2,B4-B7 + C1-C3（B3 缺；中期没 graph）
      → 输出 JSON: {triggered, primary, secondary, intervention_text, brief_reasoning}
        ↓
  Python 中间件: intervention_text → user-role message
      → **插入到 reflect_on_graph 第一次 run_refine_exploration 的 HumanMessage 头部**
        （或等价地，作为 refine 循环的额外 context 注入）

reflect_on_graph 第 1 次循环 → compress → reflect 第 2 次循环 → compress（最后一版 graph 已成型）:
  结论前检查触发（全 case 全程仅 1 次）
  **介入点：reflect_on_graph 第二次循环结束之后、finalize_summary 之前**
     已锁定，依据 aiq/agent_runner.py:652 (num_reflections=2 固定) + :732-737 (LangGraph 无条件顺序拓扑)
        ↓
  L2+L3 合并: 自主判断 + 干预生成                         [LLM: claude-opus-4-7 一次调用]
      → 输入: A1-A6 + B1-B2,B3,B4-B7 + C1-C3
        aiq 在此时 **独有** B3 draft graph（state["causal_graph"] 已由 compress_to_graph 成型）
      → 输出 JSON（同上）
        ↓
  Python 中间件: intervention_text → user-role message
      → **两种注入策略（D-6 审核后选一）**：
         策略 1（首选）：追加第 3 次 refine 循环，把 intervention 作为 HumanMessage 头部传入
         策略 2（次选）：finalize_summary 前额外调一次 compress_to_graph，
                        把 intervention 拼到 compress_user_prompt 末尾
      → 触发 agent 基于干预反思并可能修改 graph
```

### 层 vs 次（原则 5）
- **L1 / L2+L3 三层管线** → v3 三层架构 + L2/L3 合并为一次 opus-4.7 调用
- **中期检查次数** → 1 次（stage_0 末尾）
- **结论前检查次数** → 1 次（reflect 第二次循环后、finalize 前）
- **总干预次数** → ≤ 2

---

## 注入接口（aiq stage 钩子实现）

### 中期检查（stage_0_main terminator 之后）

aiq 的 data_research 节点 run_data_exploration sub-loop 结束后返回 findings + schema_messages；中间件作为 `data_research` 节点后的**后处理钩子**介入：

```python
# 伪代码示意：修改 agent_runner.py 的 data_research 节点
def data_research(state: RCAState, config: RunnableConfig) -> dict:
    findings, msgs = run_data_exploration(...)
    schema_msgs = extract_schema_messages(msgs)

    # [v4 新增] 中期检查钩子
    snapshot = build_trajectory_snapshot_aiq(
        intent_log=intent_log_from_msgs(msgs),
        reasoning=reasoning_from_msgs(msgs),
        check_point="mid",
        stage="post_stage_0"
    )
    response = call_opus47_with_v4_interface(snapshot, framework="aiq")
    extra_refine_hint = None
    if response["triggered"]:
        extra_refine_hint = response["intervention_text"]
        update_case_intervention_state(state.case_id, "mid", response)

    return {
        "data_research_results": [findings],
        "schema_messages": schema_msgs,
        "all_tool_messages": msgs,
        "_mid_check_intervention": extra_refine_hint,   # 传给 reflect_on_graph
    }
```

reflect_on_graph 在第 1 次 run_refine_exploration 的 messages 构造时，如果 `state["_mid_check_intervention"]` 非空，把它作为额外 HumanMessage 插入到 refine 指令之前（让 agent 先响应元认知反问，再做 STRENGTHEN refine）。

### 结论前检查（reflect_on_graph 第二次循环结束、finalize_summary 之前）

在 reflect_on_graph 节点末尾、return 之前介入：

```python
# 伪代码示意：修改 agent_runner.py 的 reflect_on_graph 节点
def reflect_on_graph(state: RCAState, config: RunnableConfig) -> dict:
    # ... 原有的 2 次循环逻辑（agent_runner.py:652-688）...
    for i in range(num_reflections):
        findings, msgs = run_refine_exploration(...)
        accumulated.append(findings)
        new_graph = compress_to_graph(...)
        if ...: graph = new_graph

    # [v4 新增] 结论前检查钩子（在第 2 次循环后、finalize 前）
    snapshot = build_trajectory_snapshot_aiq(
        intent_log=intent_log_from_all_msgs(all_msgs),
        reasoning=reasoning_from_all_msgs(all_msgs),
        draft_graph=graph,   # ★ aiq 独有：conclusion 时有 graph
        check_point="conclusion",
        stage="post_reflect_iter_2"
    )
    response = call_opus47_with_v4_interface(snapshot, framework="aiq")

    if response["triggered"]:
        update_case_intervention_state(state.case_id, "conclusion", response)
        # 注入策略 1（首选）：追加一次 extra refine 循环
        intervention_msgs = [HumanMessage(content=response["intervention_text"])]
        extra_findings, extra_msgs = run_refine_exploration(
            ...,
            current_graph=graph,
            extra_user_prompts=intervention_msgs,
            max_rounds=10,
        )
        all_msgs.extend(extra_msgs)
        if extra_findings:
            accumulated.append(extra_findings)
            new_graph = compress_to_graph(accumulated, compress_sp, compress_up)
            if new_graph.get("nodes") or new_graph.get("root_causes"):
                graph = new_graph

    return {
        "causal_graph": graph,
        "accumulated_findings": accumulated,
        "all_tool_messages": all_msgs,
    }
```

**关键**：aiq 是 3 个 framework 中唯一在 conclusion 时拿得到**结构化 draft graph** 的（state["causal_graph"] 已成型）。因此 A3 (Compress-Drift) / A4 (Hub-Fabrication) / M3 (Output-Graph Consistency) 在 aiq 上可以**双路 trigger**：reasoning 文本断言 + graph orphan/hub 检测。thinkdepthai 和 claudecode 在 conclusion 时只有 reasoning 文本可用。

---

## 启用维度子集（按原则 7 完整分配矩阵）

### 通用维度（M1-M10）的 aiq 适配

| 维度 | 中期 | 结论前 | aiq 上的调整 |
|------|:---:|:---:|---|
| M1 Loudness-Anchor | △ 备用 | ✅ 主用 | aiq T1 (ErrorVolumeAnchor) 21.2% — 对应 M1，结论前主用 |
| M2 Chronic-Noise Skepticism | △ 备用 | ✅ 主用 | aiq T3 (BaselineNoiseAnchored) 15.0%（TrainTicket 环境中某些服务常年有基线错误）— 对应 M2 |
| M3 Output-Graph Consistency | ✗ | △ **降权** | aiq 输出结构含 state 标记但比例较低；D-6 待确认降权到何种程度（初步：备用） |
| M4 Sibling-Disambiguation | △ 备用 | ✅ 主用 | aiq T7 (SimilarlyNamedServiceConfusion) 7.1% — 对应 M4 |
| M5 Silence ≠ Health | ✅ 可用 | ✅ 可用 | aiq T4 (SilentSignalMissed) 13.3% — 对应 M5；agent 常把 "no HTTP errors" 判为 healthy |
| M6 Baseline-Contrast Reflex | ✅ 主用 | △ 补救 | M2 触发场景里 agent 常没做 baseline；中期提醒越早越好 |
| M7 Layer-Coverage Reflex | ✅ 主用 | △ 补救 | aiq PD3 = 35.4%；中期主用 |
| M8 Hypothesis-Counterfactual | ✗ | ✅ 主用 | T6 (HallucinatedHub) 10.6% 里 agent 未对 hub 做隔离检验 — 对应 M8 |
| M9 Investigation Stagnation | ✅ 主用 | △ 补救 | aiq stage 切换一定程度缓解 stagnation，触发率较低（~5 case） |
| M10 Premature Commitment | △ **降权** | ✅ 主用 | aiq failed case 平均 round 较高（典型 3 个 terminator + 2 次 reflect），premature 场景少；仅当 stage_0 提前 terminator 时才触发中期 |

### aiq-特定维度（A1-A5）

对应 aiq v1 failure_analysis 的 8 个 theme 中 aiq-架构独有的 5 个模式：

| ID | 名称 | 来源（aiq v1 theme） | 卡片 |
|---|---|---|---|
| **A1** | Stage-Commitment Discipline | (PD_StageEndsWithoutCommitment 108 case；cross-stage 行为缺陷) | [A1_stage_commitment.md](A1_stage_commitment.md) |
| **A2** | Refinement-Without-New-Probe | (PD_ReflectionStageWithoutNewProbe 48 case) | [A2_refinement_without_new_probe.md](A2_refinement_without_new_probe.md) |
| **A3** | Compress-Drift Self-check | T8 CompressOverwritesTerminator 8 case + aiq.R_compress_drift ~16 case | [A3_compress_drift_selfcheck.md](A3_compress_drift_selfcheck.md) |
| **A4** | Hub-Fabrication Awareness | T6 HallucinatedHub 12 case | [A4_hub_fabrication_awareness.md](A4_hub_fabrication_awareness.md) |
| **A5** | Anti-Flipflop Reflex | T5 ReflectionReversesCorrect 13 case（候选在 stage 间被反复锁定/否定） | [A5_anti_flipflop_reflex.md](A5_anti_flipflop_reflex.md) |

**重要**：
- A1 / A4 在其他 framework 也存在（flat ReAct 也可能 hub-fabricate），但在 aiq 上有**独立的 cross-stage trigger 证据**，故作为 aiq-specific 列出
- A2 / A3 / A5 **严格 aiq-架构独有**——必须有 stage_{N} vs stage_{N+1} 切换或 terminator vs compress 对比才能触发
- T1 (ErrorVolumeAnchor) → M1；T2 (StoppedOneHopShortUpstream) → M4/M7 组合；T3 (BaselineNoiseAnchored) → M2；T4 (SilentSignalMissed) → M5；T7 (SimilarlyNamedServiceConfusion) → M4。故 aiq 不独立出这些通用 theme

### 中期检查的 L2 评估池

```
主用维度（opus-4.7 优先评估）：
  M6 (Baseline-Contrast Reflex)
  M7 (Layer-Coverage Reflex)
  M9 (Investigation Stagnation)
  A1 (Stage-Commitment Discipline)  ★ aiq-特定：stage_0 末尾 terminator 空缺是 stage 边界事件

备用维度（需更明确证据才上位作主问）：
  M1 (Loudness-Anchor Self-check)
  M2 (Chronic-Noise Skepticism)
  M4 (Sibling-Disambiguation Awareness)
  M5 (Silence ≠ Health)
  M10 (Premature Commitment) — 仅 stage_0 过早 terminator 时启用
  A4 (Hub-Fabrication Awareness) — stage_0 终确选若命中 hub 特征
```

### 结论前检查的 L2 评估池

```
主用维度（opus-4.7 优先评估）：
  M1 (Loudness-Anchor Self-check)
  M2 (Chronic-Noise Skepticism)
  M5 (Silence ≠ Health)
  M8 (Hypothesis-Counterfactual)
  M10 (Premature Commitment)
  A2 (Refinement-Without-New-Probe Reflection)  ★ aiq-特定
  A3 (Compress-Drift Self-check)                ★ aiq-特定
  A4 (Hub-Fabrication Awareness)                ★ aiq-特定（有 graph 才能充分判）
  A5 (Anti-Flipflop Reflex)                     ★ aiq-特定

备用维度（补救）：
  M3 (Output-Graph Internal Consistency) — aiq 降权，D-6 待确认
  M4 (Sibling-Disambiguation Awareness)
  M6 (Baseline-Contrast Reflex)
  M7 (Layer-Coverage Reflex)
```

### aiq 不启用的维度

- C2（claudecode 特有）— 不适用

### 维度优先级提示（给 opus-4.7 的 framework-specific hint）

中间件 system prompt 中在 A2/A3 池后追加 aiq-specific 提示：

```
[aiq-specific 提示]
- aiq-qwen3.5-plus failure taxonomy v1 highlights:
  T1 (ErrorVolumeAnchor) 21.2% 高发，对应 M1 — 结论前时 M1 命中优先
  T2 (StoppedOneHopShortUpstream) 14.2%，agent 正确追溯但停在 GT 一跳之外 —
     对应 M7 + M8 组合（不是单 M1，因为 agent 没被 loudness 锚定而是追溯不够深）
  T3 (BaselineNoiseAnchored) 15.0% — 对应 M2
  T4 (SilentSignalMissed) 13.3% — 对应 M5，典型症状 reasoning 文本含
     "no HTTP errors observed" / "status_code=Unset" 判为 healthy
  T5 (ReflectionReversesCorrect) 11.5% ★ aiq 独有：
     stage_0 正确 → reflect 推翻 → 对应 A5 主问；结论前检查时 A5 优先
  T6 (HallucinatedHub) 10.6% ★ 半-aiq-特色：
     对应 A4（结论前，有 draft graph 可判）
  T7 (SimilarlyNamedServiceConfusion) 7.1% — 对应 M4
  T8 (CompressOverwritesTerminator) 7.1% ★ 严格 aiq 独有：
     对应 A3；结论前 draft graph 与 stage terminator 对比才能触发
- terminator truncation 是 aiq baseline 行为（failed case 16% 全 3 terminator，correct
  case 20% 全 3 terminator），**不是**强失败信号；仅 stage_0 全空/service=None
  时才触发 A1 中期主问
- reflect 第二次循环后 draft graph **已经存在**（state["causal_graph"] 已由
  compress_to_graph 成型）——结论前 check 时 B3 字段必填
```

---

## opus-4.7 调用接口（应用 v4_principles.md 原则 7 完整规范）

### 输入信息清单（aiq 实例化）

#### 中期检查时（stage_0_main terminator 之后）

```yaml
# A 维度库（按 aiq × 中期 实例化）
A1_check_point: "mid"
A2_primary_pool: [M6, M7, M9, A1]
A3_secondary_pool: [M1, M2, M4, M5, M10, A4]
A4_dimension_cards: { M6: "...", M7: "...", M9: "...", A1: "...", M1: "...", ... }   # 关键段
A5_conflict_rules: |
  - M6 vs M2: 同时命中时 M2 优先作主问（R 层反思 > PD-pure 提醒）
  - A1 vs M10: 互斥（A1 = stage_0 无 terminator，M10 = premature commit；语义互斥）
  - M9 vs M10: 互斥
  - M1 vs M8: 同时命中时 M1 优先（loudness 反思 > counterfactual）
  - A4 vs M1: 同时命中时 A4 优先（hub-fabrication 比 loudness 更危险）
A6_intervention_rules: { v4 原则 4 八条干预守则 }

# B trajectory snapshot（stage_0 信息 only）
B1_intent_log: [(round, intent_type, target_service), ...]   # stage_0 内序列
B2_reasoning: { recent_5_rounds_full: "...", earlier_summary: "..." }
B4_where_filters: ["S1", "S2", ...]                          # 所有 WHERE service_name 集合
B5_observed_services: ["S1", "S2", ..., "S_X"]
B6_counts: { round_count: 8,   # aiq main loop 典型 ~8 轮
             tool_call_count: 14,
             stage_0_terminator: "<service_name>" or null,   # ★ aiq 特有
             stage_0_reached_max_rounds: true/false,         # ★ aiq 特有
             intent_type_counts: { error_log_overview: 6, baseline_contrast: 0, jvm_state: 0, ... } }
B7_ranking_top3: [...]
# B3 (draft graph) — 中期没有，不给

# C 上下文
C1_framework: "aiq-qwen3.5-plus"
C2_prior_intervention_history: { mid_check: null }   # 中期是首次 check point
C3_framework_priors: {
    failed_case_stage_0_round_count_P25: <待 D-7.5 算>,
    failed_case_total_round_count_P50: <待 D-7.5 算>,
    terminator_none_rate_in_failed: 0.08,   # v1 分析中 stage_0 空 terminator 在 failed case 的占比
    num_reflections_fixed: 2   # aiq 固定
}
```

#### 结论前检查时（reflect_on_graph 第 2 次循环后）

```yaml
# 大部分同中期，差异：
A1_check_point: "conclusion"
A2_primary_pool: [M1, M2, M5, M8, M10, A2, A3, A4, A5]
A3_secondary_pool: [M3, M4, M6, M7]

# B3 (draft graph) ★ aiq 独有：此时 state["causal_graph"] 已成型，可传
B3_draft_graph: {
    nodes: [{ name: "S1", state: "UNAVAILABLE" }, ...],
    edges: [{ from: "S1", to: "S2", label: "..." }, ...],
    root_causes: [{ service: "S_X", reason: "..." }, ...]
}

# 额外 aiq-特有 snapshot 字段
B8_stage_candidates: {
    stage_0_terminator: "<service_name>" or null,
    stage_1_refine_terminator: "<service_name>" or null,   # 若 refine 轮有 terminator
    stage_2_refine_terminator: "<service_name>" or null,
    compress_rc_latest: "<service_name from graph.root_causes[0]>"
}   # ★ 用于 A3 (terminator vs compress 对比) + A5 (stage 间 flipflop)

C2_prior_intervention_history: {
    mid_check: {
        triggered: true,
        primary: "A1",          # 或其他
        secondary: ["M6", "M7"],
        intervention_text: "本阶段你没收敛到任何候选——...",
        stage: "post_stage_0"
    }
}
```

### 输出格式

按 v4_principles.md 标准 JSON schema（同 thinkdepthai）：

```json
{
  "triggered": true,
  "primary_dimension": "A3",
  "secondary_dimensions": ["M1"],
  "intervention_text": "你的压缩输出图的根因和你最后一轮调查的 terminator 指向不同...\n\n另外你的候选在排名查询里排得很前——...",
  "brief_reasoning": "stage_2 terminator=X, compress graph.root_causes=[Y]，A3 命中；Y 恰好是最近几轮 ranking 查询的 top1，M1 次问命中"
}
```

---

## 期望 wrong→correct 翻盘贡献

基于 aiq v1 failure_analysis 的 theme 分布，按维度估计：

| 维度 | theme 对应 | case 数 | 翻盘率估计 | 翻盘 case 数 |
|---|---|---:|---:|---:|
| M1 | T1 ErrorVolumeAnchor | 24 | ~40% | ~10 |
| M2 | T3 BaselineNoiseAnchored | 17 | ~40% | ~7 |
| M4 | T7 SimilarlyNamedServiceConfusion | 8 | ~25% | ~2 |
| M5 | T4 SilentSignalMissed | 15 | ~40% | ~6 |
| M7 | (部分叠加 T1/T2) | ~30（去 M1 重叠后） | ~25% | ~7 |
| M8 | (叠加 T2/T6) | ~20 | ~20% | ~4 |
| A1 | PD_StageEndsWithoutCommitment 相关 | ~20（stage_0 空或 service=None）| ~30% | ~6 |
| A2 | PD_ReflectionStageWithoutNewProbe | 48 | ~20% | ~10 |
| A3 | T8 CompressOverwritesTerminator | 8 | ~40%（compress 可被提醒修正）| ~3 |
| A4 | T6 HallucinatedHub | 12 | ~35% | ~4 |
| A5 | T5 ReflectionReversesCorrect | 13 | ~40%（让 agent 意识到 flipflop）| ~5 |
| M9 | - | ~5 | ~60% | ~3 |
| M10 | - | ~5（stage_0 过早 terminator）| ~30% | ~2 |

**合计粗估（去重叠后）**：~50-60 case 翻盘 / 113 failed case = **44-53%**

**对照基线**：
- aiq-qwen3.5-plus v1 无元认知中间件 baseline AC@1 = 77.4%
- v4 目标：AC@1 提升到 ~85% (+7-8 个百分点)

---

## ✓ 中期检查点触发时机（D-7.5 已锁定）

**策略**：候选 A stage-边界变体 — `mid_check_trigger_position = "post_stage_0_main_terminator"`

**依据**（详见 [../v4_mid_check_strategy.md](../v4_mid_check_strategy.md)）：
- aiq effective_rounds 分布：failed P25=47, P50=54, P75=62, max=78；correct P25=43, P50=49, P75=57, max=80
- aiq failed 与 correct 分布几乎重合（P50 54 vs 49）——固定 `num_reflections=2` 让轨迹长度趋同；**round count 不是 aiq 失败的区分信号**
- 故 aiq 不选"round count P25"（候选 A 原版）而选 **stage 边界变体**
- stage_0_main 是主调查阶段，它结束后是"完成主查、即将反思"的窗口——恰好是元认知反问的天然时机

**具体触发点**：

```
aiq 的 data_research 节点 run_data_exploration sub-loop 结束后：
  if not state.mid_check_done:
    L2+L3 合并调用
    if response.triggered:
      intervention_text → 作为额外 HumanMessage
      插入到 reflect_on_graph 第 1 次 run_refine_exploration 的 messages 头部
```

**边界条件**：
- stage_0_main 跑到 max_rounds=60 仍未 terminator：触发 A1 主问（这是 A1 的核心 trigger 场景）
- stage_0_main 提前 terminator（~correct P25 = 43 round）：介入点同样在 terminator 后；此时 round count 已较多，主问倾向 M6/M7/M9/A1

---

## 必处理的 aiq-架构约束

### 约束 1 — num_reflections 固定为 2

- **位置**: `aiq/agent_runner.py:632` `num_reflections = config["configurable"].get("num_reflections", 2)`
- **影响**: aiq 每个 case 必然经历 2 次 reflect 循环，v4 结论前检查锁定在第 2 次循环结束后是**安全**的（不会错过 / 过早）
- **v4 处理**: 不需额外代码，依赖该固定值

### 约束 2 — finalize_summary 为透传节点（agent_runner.py:699-706）

- **症状**: finalize 节点只做 `json.dumps(causal_graph)`，不调 LLM，无法在此节点注入让 agent 反思
- **v4 处理**: 结论前检查必须在 reflect_on_graph **末尾**（而非 finalize 开头）注入，因为 finalize 无能力修改 graph

### 约束 3 — compress_to_graph 可能在 reflect 循环内多次调用（agent_runner.py:607/674）

- **症状**: 每次 reflect 循环里 findings 压缩一次，全程 compress 调用 ≥3 次
- **v4 处理**: 结论前检查**只在第 2 次 reflect 循环结束后的 compress 之后**介入一次；不重复。per-case 状态 `conclusion_check_triggered` 确保不重入

### 约束 4 — stage_0_main 最大 60 轮（data_research 节点 max_rounds=60）

- **影响**: 中期检查位置如选候选 A（stage_0 结束后），触发时机受 60 轮上限限制；若 stage_0 达 max_rounds 仍未 terminator，触发 A1 主问是合理的
- **v4 处理**: A1 trigger 包含 `stage_0_reached_max_rounds AND terminator_is_none`

---

## 验证（不在 D-6 范围）

D-7.5 完成 + 三 framework 适配层都定后，按 plan Part E 走：

1. **离线重放**: 在 113 已标注 failed case 上跑 v4 trigger，对比 v1 baseline 的 theme 标注（T1-T8 vs M1-M10/A1-A5）
2. **A/B 翻盘对照**: aiq-qwen3.5-plus 113 case 重跑 baseline vs MW-v4，目标 ≥ 30% 翻盘 = ~34 case
3. **success-case 回归测试**: 50 个 correct sample → 验证 correct → wrong ≤ 1
4. **策略 1 vs 策略 2 对比**: 结论前检查的两种注入策略（追加 refine vs 追加 compress）小样本 A/B（各 20 case）选更优解

---

## 关键文件路径索引

**v4 设计参考**：
- 设计原则: [../v4_principles.md](../v4_principles.md)
- 维度库: [../v4_dimensions/](../v4_dimensions/) (M1-M10 共 10 张卡)
- thinkdepthai 适配层参考: [../v4_thinkdepthai_qwen3.5_plus.md](../v4_thinkdepthai_qwen3.5_plus.md)

**aiq 本身**（v4 实施时 hook 点）：
- [aiq/agent_runner.py:516-611](../../aiq/agent_runner.py) — data_research 节点（中期检查插入点）
- [aiq/agent_runner.py:614-694](../../aiq/agent_runner.py) — reflect_on_graph 节点（结论前检查插入点）
- [aiq/agent_runner.py:697-706](../../aiq/agent_runner.py) — finalize_summary 节点（不介入）
- [aiq/CLAUDE.md](../../aiq/CLAUDE.md) — aiq 架构文档

**v1 failure_analysis 源数据**（本 README 引用的 theme 分布）：
- `/home/nn/.claude/projects/-home-nn-SOTA-agents/memory/failure_mode_aiq_v1.md` — 冻结 v1 分布
- `analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/v1/taxonomy.md` — 冻结 theme 定义
- DB: `meta.failure_analysis.v1` 在 113 个 incorrect 样本上

**待写**:
- [../v4_claudecode_qwen3.5_plus/](../v4_claudecode_qwen3.5_plus/) — D-7 阶段
- [../v4_mid_check_strategy.md](../v4_mid_check_strategy.md) — D-7.5 三 framework 中期触发统一决策

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-6 阶段输出）；中期检查倾向候选 A（stage_0 末尾）但 D-7.5 统一决策；结论前锁定 reflect 第 2 次循环后、finalize 前 |
