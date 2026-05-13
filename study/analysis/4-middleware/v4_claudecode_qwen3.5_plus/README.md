# v4 claudecode 适配层（qwen3.5-plus）

**Plan**: [/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md](/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**维度库**: [../v4_dimensions/](../v4_dimensions/)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-7 阶段）

---

## 适用 case

| Agent (exp_id) | failure case 数 | 备注 |
|---|---:|---|
| claudecode-qwen3.5-plus | 103 | v1 failure_analysis 已冻结（AC@1 79.4%，T6 已 retire，103 failed case）；本次 v4 首次启用元认知中间件 |

**关键特性**：claudecode 与其他 agent 的核心差异：
- 框架 = Claude Code CLI（`claude -p` subprocess），不是 Python SDK
- 工具 = 原生 Bash + Read（DuckDB 查询通过 Bash 运行），**不是**自定义 `query_parquet_files`
- 输出 = stream-json 事件流（assistant tool_use / user tool_result / result 最终总结）
- Prompt 注入 = 通过 Claude Code 的多轮对话支持（`claude -c` / `--resume`），或 stdin 重新启动

**与 thinkdepthai/aiq 的核心差异**：claudecode **没有显式结构化阶段**——它是 Claude Code CLI 内部一个 ReAct 式循环，中间件无法像 aiq 那样在 stage 边界介入。介入必须基于**工具调用计数**（Bash tool call count）来估计"调查进度"。

---

## 三层管线（沿用 v3 + L2/L3 合并）

```
Claude Code subprocess 启动后：
  监听 stream-json 事件 (stderr/stdout):
    assistant: { type: "tool_use", name: "Bash", input: "<command>" }
      ↓ 实时统计 Bash tool call count
      ↓ 实时累积 trajectory

  L1: Bash 命令 → SQL 提取 → 19 类 intent 分类          [LLM: claude-opus-4-7]
      Claude Code reasoning 提取（assistant.content text blocks）
      R-T 利用率提取                                    [纯代码]
        ↓
  中期检查触发（全 case 全程仅 1 次）
  **介入点：Bash tool call count 到达某个触发值**
     **触发值留空，D-7.5 三 framework 统一定**
        ↓
  L2+L3 合并: 自主判断 + 干预生成                       [LLM: claude-opus-4-7 一次调用]
      → 输入: A1-A6 + B1-B2,B4-B7 + C1-C3（B3 缺；中期没 graph）
      → 输出 JSON: {triggered, primary, secondary, intervention_text, brief_reasoning}
        ↓
  Python 中间件: intervention_text → user-role message
      → **注入策略**：通过 Claude Code 的 --resume 机制向对话追加一条 user message
        （具体实现见下"注入接口"节）

Claude Code 输出 result（stream-json type="result"）事件时：
  意味着 agent 已经 commit 最终答案（result_text）
  但此时介入"结论前"为时已晚——result 已经发出
  ↓
  **v4 结论前检查的替代方案**：在 compress 阶段之前介入
    L2+L3 合并 (同上)
      → 输入: A1-A6 + B1-B2,B4-B7 + C1-C3（B3 缺；claudecode 在 compress 前也没结构化 graph）
      → 注意：M3 走 reasoning 文本 trigger（参照 D-3 修订）
      ↓
    intervention_text → 拼入 compress_user_prompt 末尾
      → 让 compress 阶段的 LLM 在做最终 JSON 提取时"再审一次"
      → 若 agent 根据干预修改选择，compress 输出会反映出改正
```

### 层 vs 次（原则 5）
- **L1 / L2+L3 三层管线** → v3 三层架构 + L2/L3 合并为一次 opus-4.7 调用
- **中期检查次数** → 1 次（Bash count 到达触发值时）
- **结论前检查次数** → 1 次（Claude Code result 输出后、compress 调用前）
- **总干预次数** → ≤ 2

---

## 注入接口（Claude Code CLI 钩子实现）

### 中期检查（Bash tool call count 到达触发值时）

**核心挑战**：`claude -p` 是一次性 prompt → 流式输出模式；中途无法"暂停再给 message"。需要通过以下两种机制之一介入：

#### 机制 A（首选）— `--resume` 多轮对话

Claude Code CLI 支持 `claude --resume <session_id> -p <new_message>` 继续已有对话。中间件流程：

```python
# 伪代码示意
def run_claudecode_with_middleware(payload):
    session_id = generate_session_id()
    # 启动初始 claude -p，stream 模式监听输出
    proc = subprocess.Popen([
        "claude", "-p", user_prompt,
        "--session-id", session_id,
        "--output-format", "stream-json", "--verbose",
        "--allowedTools", "Bash(*)", "Read(*)",
    ], stdout=subprocess.PIPE, ...)

    bash_count = 0
    trajectory = []
    mid_check_done = False

    for event in parse_stream_events(proc.stdout):
        if event.type == "assistant" and event.has_tool_use("Bash"):
            bash_count += 1
            trajectory.append(event)

            if not mid_check_done and bash_count >= MID_CHECK_BASH_THRESHOLD:
                # [v4 新增] 中期检查钩子
                # 问题：当前 claude -p 进程还在跑，我们不能"暂停"它
                # 解决：等当前进程自然结束（或手动 kill 后），再用 --resume 继续
                snapshot = build_trajectory_snapshot_claudecode(
                    trajectory, check_point="mid"
                )
                response = call_opus47_with_v4_interface(snapshot, framework="claudecode")
                mid_check_done = True
                if response["triggered"]:
                    # 方案 A.1：kill 当前进程 → resume 时追加 intervention
                    proc.kill()
                    proc_resumed = subprocess.Popen([
                        "claude", "--resume", session_id,
                        "-p", response["intervention_text"],
                        "--output-format", "stream-json", "--verbose",
                    ], stdout=subprocess.PIPE, ...)
                    proc = proc_resumed  # 继续监听新进程
                    update_case_intervention_state(case_id, "mid", response)
        elif event.type == "result":
            break   # agent 已 commit
```

**方案 A.1 缺点**：kill subprocess 可能丢失 Claude Code 内部的 thinking / TODO 状态；--resume 的 session 状态依赖 Claude Code 内部持久化机制。

**方案 A.2（候选）**：不 kill 进程，等 claude -p 自然结束后（result 事件），**在 compress 之前**做"中期 + 结论前合并"检查——但这会违反 1+1 节制（变成 0+1）。需在 D-7.5 决策时评估。

#### 机制 B（备选）— 包装 Bash 工具为钩子

通过修改 Claude Code 的工具配置（`--allowedTools Bash(<custom wrapper>)` 或环境变量 hook），让 Bash 工具执行前调用一个 Python 钩子脚本。钩子脚本：
- 增加 bash_count
- 若 bash_count >= 触发值 且未介入过 → 在返回给 Claude Code 的 tool_result 前拼上 intervention text

**缺点**：把 intervention 塞进 tool_result 可能污染 Claude Code 对工具结果的解读；且 intervention 应该以 user-role 出现而不是 tool_result。

**v4 决策**：**首选机制 A.1**，D-7.5 决策时若 A.1 太复杂则降级为"取消中期检查"（候选 C），只保留结论前检查。

### 结论前检查（compress 调用前）

claudecode 的输出流水线是：Claude Code CLI result → L1/L2/L3 三层提取（见 ClaudeCode/CLAUDE.md）。v4 结论前检查介入**L2 compress 阶段之前**：

```python
# 伪代码示意：修改 agent_runner.py 的 main 流程
def extract_output(result_text, trajectory, compress_sp, compress_up):
    # L1: 直接 parse
    try:
        parsed = json.loads(strip_markdown_json(result_text))
        if "root_causes" in parsed or "nodes" in parsed:
            return parsed
    except: pass

    # [v4 新增] 结论前检查钩子（在 L2 compress 之前）
    snapshot = build_trajectory_snapshot_claudecode(
        trajectory, result_text=result_text, check_point="conclusion"
    )
    response = call_opus47_with_v4_interface(snapshot, framework="claudecode")

    conclusion_user_prompt = compress_up
    if response["triggered"]:
        update_case_intervention_state(case_id, "conclusion", response)
        # 把 intervention_text 拼到 compress 输入末尾
        conclusion_user_prompt = (
            compress_up + "\n\n---\n\n"
            + "[Investigation Advisor Note]:\n"
            + response["intervention_text"] + "\n"
            + "Please reconsider the final root cause based on this reflection, "
            + "and provide your final answer as the required JSON."
        )

    # L2: compress with potentially augmented prompt
    return _compress_to_json(
        result_text, trajectory, compress_sp, conclusion_user_prompt
    )
```

**关键设计**：L2 compress 已经是一个独立的 LLM 调用（Anthropic SDK → Coding Plan qwen3.5-plus），在它的 user_prompt 里追加 intervention 是最自然的注入位点。compress LLM 会同时看到：
- trajectory 摘要（最近 30 条）
- 最终 markdown 分析
- compress_up 原文
- intervention 附加文本

这让 compress LLM 扮演"带着反思做最终选择"的角色——如果 intervention 让它怀疑某个候选，它会在输出 JSON 时选择不同的 root_cause。

**与 aiq 结论前检查的对比**：
- aiq：有 draft graph 可传给 opus-4.7，可基于结构化输出 trigger；injection 通过追加 refine 循环或追加 compress 实现
- claudecode：**没有结构化 graph**，opus-4.7 仅基于 reasoning 文本 trigger；injection 直接改 compress 的 user_prompt

---

## 启用维度子集（按原则 7 完整分配矩阵）

### 通用维度（M1-M10）的 claudecode 适配

| 维度 | 中期 | 结论前 | claudecode 上的调整 |
|------|:---:|:---:|---|
| M1 Loudness-Anchor | △ 备用 | ✅ 主用 | 对应 v1 T1 SilentInjectionShadowed 27.2% — agent 被"最响亮的错误"锚定 |
| M2 Chronic-Noise Skepticism | △ 备用 | ✅ 主用 | 对应 v1 T2 BaselineNoiseAnchored 35.9%（claudecode 最高发；RabbitMQ DNS 噪声是标志性模式）|
| M3 Output-Graph Consistency | ✗ | ✅ 主用（reasoning 文本 trigger）| 对应 v1 T3 InvertedCausalEdge 15.5% — agent 输出图中因果方向错误 |
| M4 Sibling-Disambiguation | △ 备用 | ✅ 主用 | 对应 v1 T7 SimilarNameConfusion 9.7% — 名称相似服务混淆 |
| M5 Silence ≠ Health | ✅ 可用 | ✅ 可用 | 对应 v1 T1 SilentInjectionShadowed 的一部分（信号静默的真实 GT 被误读为 healthy）|
| M6 Baseline-Contrast Reflex | ✅ 主用 | △ 补救 | 与 T2 正交：中期提醒早做 baseline 可避免后来的 anchor |
| M7 Layer-Coverage Reflex | ✅ 主用（**被 C2 变体覆盖**）| △ 补救 | 对应 v1 T4 InfraLayerSkipped 6.8% + T5 JVMMisreadAsDB 3.9%（见 C2 卡）|
| M8 Hypothesis-Counterfactual | ✗ | ✅ 主用 | 原 claudecode.C1 (GT-Targeted-WHERE Reflex) 合并到 M8，参照 plan Part B.3 |
| M9 Investigation Stagnation | ✅ 主用 | △ 补救 | 通用模式，claudecode 的 Bash 循环也会陷入重复 |
| M10 Premature Commitment | △ 备用 | ✅ 主用 | claudecode 的 Bash count 分布可用于先验 |

### claudecode-特定维度（C2）

| ID | 名称 | 来源（claudecode v1） | 卡片 |
|---|---|---|---|
| **C2** | Layer-Coverage Reflex (claudecode 变体) | T4 InfraLayerSkipped 6.8% + T5 JVMMisreadAsDB 3.9%（合并，共 ~11 case） | [C2_layer_coverage_claudecode_variant.md](C2_layer_coverage_claudecode_variant.md) |

**参照 plan Part B.3 决策**：
- **C1**（GT-Targeted-WHERE Reflex，原 claudecode.PD4）→ **合并到 M8**，不独立成维度
- **C3**（JVM vs DB Disambiguation）→ 仅 4 case，数据量太小 → **并入 C2 的"看到'数据库'症状别急着下结论"提示词变体**，不独立成维度

**重要**：C2 是 M7 在 claudecode 上的**加强变体**——多一句"运行时层的问题有时会通过应用层（如连接池、超时）表现"的提示，补偿 claudecode 通过 Bash 提取 intent 的延迟。

### 中期检查的 L2 评估池

```
主用维度（opus-4.7 优先评估）：
  M6 (Baseline-Contrast Reflex)
  M7 (Layer-Coverage Reflex) — claudecode 上由 C2 变体覆盖
  M9 (Investigation Stagnation)
  C2 (Layer-Coverage claudecode 变体)  ★ claudecode-特定

备用维度（需更明确证据才上位作主问）：
  M1 (Loudness-Anchor Self-check)
  M2 (Chronic-Noise Skepticism)
  M4 (Sibling-Disambiguation Awareness)
  M5 (Silence ≠ Health)
  M10 (Premature Commitment) — 仅 Bash count < P25 时启用
```

### 结论前检查的 L2 评估池

```
主用维度（opus-4.7 优先评估）：
  M1 (Loudness-Anchor Self-check)
  M2 (Chronic-Noise Skepticism)  ★ claudecode 最高发模式
  M3 (Output-Graph Internal Consistency) — reasoning 文本 trigger
  M4 (Sibling-Disambiguation Awareness)
  M5 (Silence ≠ Health)
  M8 (Hypothesis-Counterfactual)
  M10 (Premature Commitment)

备用维度（补救）：
  M6 (Baseline-Contrast Reflex)
  M7 (Layer-Coverage Reflex)
  C2 (Layer-Coverage claudecode 变体) — 补救
  M9 (Investigation Stagnation)
```

### claudecode 不启用的维度

- A1-A5（aiq 特有）— 不适用

### 维度优先级提示（给 opus-4.7 的 framework-specific hint）

中间件 system prompt 中在 A2/A3 池后追加 claudecode-specific 提示：

```
[claudecode-specific 提示]
- claudecode-qwen3.5-plus failure taxonomy v1 highlights (103 failed cases):
  T2 (BaselineNoiseAnchored) 35.9% — 对应 M2；**claudecode 最高发模式**
     标志性：RabbitMQ DNS 类噪声日志出现在 normal_logs 和 abnormal_logs 同样频繁，
     agent 被这类"响亮但常年存在"的错误锚定
     结论前检查时 M2 命中应强优先
  T1 (SilentInjectionShadowed) 27.2% — 对应 M1 / M5 组合
     agent 被最响亮的错误锚定，忽略了真实 GT（后者在 abnormal 里信号 silent）
  T3 (InvertedCausalEdge) 15.5% — 对应 M3（reasoning 文本检测因果反转）
  T7 (SimilarNameConfusion) 9.7% — 对应 M4
  T4 (InfraLayerSkipped) 6.8% + T5 (JVMMisreadAsDB) 3.9% — 对应 C2
     agent 只查应用层 Bash 查询，没碰运行时层指标
     T5 特殊：agent 看到连接池 / 超时现象就诊断"数据库问题"，但真实 GT 是 JVM
- claudecode 通过 Bash 工具查询，intent 提取可能比 thinkdepthai/aiq 有延迟
  （Bash 命令多样，提取 SQL 需额外 parse）—— C2 的触发阈值在 M7 基础上调低
- reasoning 文本主要出现在 assistant.content text block（非 tool_use），
  M3 / M5 / M8 的 trigger 都依赖这个文本流
```

---

## opus-4.7 调用接口（应用 v4_principles.md 原则 7 完整规范）

### 输入信息清单（claudecode 实例化）

#### 中期检查时（Bash count 到达触发值时）

```yaml
# A 维度库（按 claudecode × 中期 实例化）
A1_check_point: "mid"
A2_primary_pool: [M6, M7, M9, C2]
A3_secondary_pool: [M1, M2, M4, M5, M10]
A4_dimension_cards: { M6: "...", M7: "...", M9: "...", C2: "...", ... }
A5_conflict_rules: |
  - M7 vs C2: C2 是 M7 在 claudecode 上的变体；同时命中时 C2 优先（更贴合 claudecode 特性）
  - M6 vs M2: 同时命中时 M2 优先作主问（R 层反思 > PD-pure 提醒）
  - M9 vs M10: 互斥（重复探查 → round 多 → 不会 premature）
  - M1 vs M8: 同时命中时 M1 优先
A6_intervention_rules: { v4 原则 4 八条干预守则 }

# B trajectory snapshot
B1_intent_log: [(round, intent_type, target_service), ...]   # 从 Bash 命令解析的 intent 序列
B2_reasoning: { recent_5_rounds_full: "...", earlier_summary: "..." }  # assistant.content text blocks
B4_where_filters: ["S1", "S2", ...]
B5_observed_services: ["S1", "S2", ..., "S_X"]
B6_counts: { bash_tool_call_count: 18,   # ★ claudecode 特有（替代 round_count）
             read_tool_call_count: 3,
             intent_type_counts: { error_log_overview: 8, baseline_contrast: 0, jvm_state: 0, ... } }
B7_ranking_top3: [...]
# B3 (draft graph) — 中期没有，不给

# C 上下文
C1_framework: "claudecode-qwen3.5-plus"
C2_prior_intervention_history: { mid_check: null }   # 中期是首次 check point
C3_framework_priors: {
    failed_case_bash_count_P25: <待 D-7.5 算>,
    failed_case_bash_count_P50: <待 D-7.5 算>,
    total_result_events_per_case: 1   # claudecode 每 case 一个 result
}
```

#### 结论前检查时（compress 调用前）

```yaml
# 大部分同中期，差异：
A1_check_point: "conclusion"
A2_primary_pool: [M1, M2, M3, M4, M5, M8, M10]
A3_secondary_pool: [M6, M7, C2, M9]

# B3 (draft graph) 仍不给（claudecode 在 compress 之前也没结构化 graph）
# M3 走 reasoning 文本 trigger

# 额外 claudecode-特有 snapshot 字段
B8_final_result_text: "<Claude Code 的 result 事件原文，可能是 markdown 或 JSON>"
   # ★ claudecode 特有：result 已出但还没 compress，这是最终决策的原文
   # M1/M2/M3/M5/M8 都可从此文本提取 agent 的候选与推理

C2_prior_intervention_history: {
    mid_check: {
        triggered: true,
        primary: "C2",   # 或其他
        secondary: ["M6"],
        intervention_text: "你查了大量应用层数据...",
        bash_count_at_trigger: 18
    }
}
```

### 输出格式

按 v4_principles.md 标准 JSON schema（同 thinkdepthai / aiq）：

```json
{
  "triggered": true,
  "primary_dimension": "M2",
  "secondary_dimensions": ["M5"],
  "intervention_text": "你看到的错误，有没有可能在没有故障时也是这样的？...\n\n另外你说某服务 normal 只因它没产生错误...",
  "brief_reasoning": "T2-style 模式：某基线噪声类错误被选作 RC，baseline_contrast=0；agent reasoning 文本含 'healthy' 推断一个信号静默的服务 → M5 次问"
}
```

---

## 期望 wrong→correct 翻盘贡献

基于 claudecode v1 failure_analysis 的 theme 分布，按维度估计：

| 维度 | theme 对应 | case 数 | 翻盘率估计 | 翻盘 case 数 |
|---|---|---:|---:|---:|
| M1 | T1 SilentInjectionShadowed 部分 | ~14（T1 的一半，另一半走 M5）| ~40% | ~6 |
| M2 | T2 BaselineNoiseAnchored | 37 | ~40%（最高发模式，干预价值大）| ~15 |
| M3 | T3 InvertedCausalEdge | 16 | ~25%（图方向错误较难纠）| ~4 |
| M4 | T7 SimilarNameConfusion | 10 | ~30% | ~3 |
| M5 | T1 SilentInjectionShadowed 部分 | ~14（另一半）| ~35% | ~5 |
| M6 | - | ~20（和 M2 重叠后净新增）| ~25% | ~5 |
| M7 / C2 | T4 InfraLayerSkipped + T5 JVMMisreadAsDB | 11 | ~40% | ~4 |
| M8 | (叠加 T1/T2/T4) | ~15 | ~20% | ~3 |
| M9 | - | ~8 | ~50% | ~4 |
| M10 | - | ~5 | ~30% | ~2 |

**合计粗估（去重叠后）**：~35-45 case 翻盘 / 103 failed case = **34-44%**

**对照基线**：
- claudecode-qwen3.5-plus v1 无元认知中间件 baseline AC@1 = 79.4%
- v4 目标：AC@1 提升到 ~86-89% (+7-10 个百分点)

**重点**：M2 (Chronic-Noise Skepticism) 单维度预期翻盘 15 case，是 claudecode 上最大的单点收益——因为 T2 BaselineNoiseAnchored 是该 framework 最高发模式 (35.9%)，M2 主问针对性强。

---

## ✓ 中期检查点触发时机（D-7.5 已锁定）

**策略**：候选 C — **取消中期检查**。`mid_check_enabled = false`

**依据**（详见 [../v4_mid_check_strategy.md](../v4_mid_check_strategy.md)）：
- claudecode effective_rounds 分布：failed P25=52, P50=59, P75=74, max=140；correct P25=41, P50=49, P75=60, max=104
- claudecode failed 与 correct 分布相似（P50 59 vs 49）——没有强 round-count 失败信号支持中期介入
- `claude -p` 一次性 prompt 架构让中期介入需要 kill 进程 + `claude --resume <session_id>` 多轮机制；kill 可能丢 Claude Code 内部的 thinking / TODO 状态；--resume 的 session 持久化机制依赖 Claude Code 内部实现，跨版本不稳定
- 结论前检查已有**天然注入窗口**（`_compress_to_json` 是独立 Anthropic SDK LLM 调用，在 compress_up 末尾拼 intervention 最自然）
- **v4 初次部署优先简单方案**：取消中期（0 次）+ 结论前 1 次 = 总 1 次干预

**代价**：
- 失去对 long-trajectory 失败（max 140 round）的中期纠偏能力
- 原中期主用维度（M6 / M7 / M9 / C2）在 claudecode 上**全部降级为结论前补救**——已在本 README "启用维度子集" 节的 L2 评估池表格体现

**Phase 8 升级路径**（可选）：
- 若 claudecode v4 首次部署 AC@1 提升不及预期（< +5pp），可在 Phase 8 投入实现 kill + `--resume` 机制，升级为候选 A（Bash count P25 固定点）
- 需额外小样本 A/B（15 case）验证 kill + --resume 不会破坏 Claude Code 内部状态

---

## 必处理的 claudecode-架构约束

### 约束 1 — `claude -p` 一次性模式

- **位置**: `ClaudeCode/agent_runner.py:22` CLAUDE_BIN + `claude -p` 调用
- **症状**: `claude -p` 接受一次 prompt，流式返回结果后进程结束；中途无法"暂停再追加消息"
- **v4 处理**: 需用 `claude --resume <session_id> -p <new_message>` 机制实现多轮；或取消中期（候选 C）

### 约束 2 — stream-json 事件流为 stderr/stdout

- **位置**: `ClaudeCode/agent_runner.py:parse_stream_events()`
- **影响**: 中间件必须实时 parse stream-json 来统计 Bash count，不能等到进程结束
- **v4 处理**: 中间件在主 Python 进程里监听 `proc.stdout`，每次 event 到达立即更新 counter

### 约束 3 — compress 阶段用 Anthropic SDK 直调 Coding Plan

- **位置**: `ClaudeCode/agent_runner.py:_compress_to_json`（L2 提取层）
- **症状**: compress 不走 Claude Code CLI，而是直接 Anthropic SDK。这是**天然的注入窗口**——结论前检查的 intervention 可直接拼到 compress 的 user_prompt
- **v4 处理**: 结论前检查的实现最简单——修改 `_compress_to_json` 调用点，在 compress_up 末尾拼 intervention_text（见上"注入接口"节）

### 约束 4 — Bash 命令需 parse 提取 SQL

- **症状**: claudecode 的 Bash 命令形态多样（`duckdb -c "SELECT ..."` / `python -c "..."` / `ls` 等）；L1 intent 分类需先从 Bash 命令中提取 SQL 字符串
- **v4 处理**: Bash 命令按规则提取 DuckDB/SQL 子串后交 opus-4.7 分类；非 SQL 类 Bash 命令（如 `ls`, `head`）不产生 intent；intent 提取延迟在 claudecode 上略高于其他 framework —— C2 的 app_count 触发阈值相应调低

---

## 验证（不在 D-7 范围）

D-7.5 完成 + 三 framework 适配层都定后，按 plan Part E 走：

1. **离线重放**: 在 103 已标注 failed case 上跑 v4 trigger，对比 v1 baseline 的 theme 标注（T1-T8 vs M1-M10/C2）
2. **A/B 翻盘对照**: claudecode-qwen3.5-plus 103 case 重跑 baseline vs MW-v4，目标翻盘 ≥ 30% = ~31 case
3. **success-case 回归测试**: 50 个 correct sample → 验证 correct → wrong ≤ 1
4. **机制 A vs 机制 B vs 机制 C** 对比: 小样本（各 15 case）A/B 对比三种中期介入机制，选最稳定者
5. **注入点位对比**: compress 之前注入 vs Claude Code --resume 注入：前者更易实现，但 agent 可能不会"回到"前一轮 reasoning；后者更自然但实现复杂

---

## 关键文件路径索引

**v4 设计参考**：
- 设计原则: [../v4_principles.md](../v4_principles.md)
- 维度库: [../v4_dimensions/](../v4_dimensions/) (M1-M10 共 10 张卡)
- thinkdepthai 适配层参考: [../v4_thinkdepthai_qwen3.5_plus.md](../v4_thinkdepthai_qwen3.5_plus.md)
- aiq 适配层参考: [../v4_aiq_qwen3.5_plus/README.md](../v4_aiq_qwen3.5_plus/README.md)

**claudecode 本身**（v4 实施时 hook 点）：
- [ClaudeCode/agent_runner.py:22](../../ClaudeCode/agent_runner.py) — CLAUDE_BIN 配置（可通过 `CLAUDE_BIN` 环境变量覆盖）
- [ClaudeCode/agent_runner.py 的 parse_stream_events 附近](../../ClaudeCode/agent_runner.py) — stream-json 监听（中期检查插入点）
- [ClaudeCode/agent_runner.py 的 _compress_to_json](../../ClaudeCode/agent_runner.py) — L2 compress（结论前检查插入点）
- [ClaudeCode/CLAUDE.md](../../ClaudeCode/CLAUDE.md) — claudecode 架构文档

**v1 failure_analysis 源数据**（本 README 引用的 theme 分布）：
- `/home/nn/.claude/projects/-home-nn-SOTA-agents/memory/failure_mode_claudecode_v1.md` — 冻结 v1 分布
- `analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/taxonomy.md` — 冻结 theme 定义
- DB: `meta.failure_analysis.v1` 在 103 个 incorrect 样本上

**待写**:
- [../v4_mid_check_strategy.md](../v4_mid_check_strategy.md) — D-7.5 三 framework 中期触发统一决策

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-7 阶段输出）；中期检查触发时机暂留空，D-7.5 统一决策（可能选候选 C 取消中期）；结论前检查锁定 compress 调用前（天然注入窗口）|
