# 周报：RCA Agent 评测 → 失败分析 → 元认知中间件 (2026-04-22)

**逻辑主线**: 跑 agent → 量准确率 → 打行为意图 → 归纳失败模式 → 设计中间件 → 验证闭环

---

## 1. 根因定位 & 准确率（一笔带过）

4 个 Deep Research Agent × 500 case × RCABench 数据集共享 PostgreSQL。

| Agent | 框架范式 | 模型 | AC@1 | Failure N |
|---|---|---|---:|---:|
| thinkdepthai-sonnet | 单 agent ReAct + 反思 | claude-sonnet-4.6 | **89.8%** | 51 |
| claudecode | Claude Code CLI + Bash/DuckDB | qwen3.5-plus | 79.4% | 103 |
| aiq | Pipeline（stage₀/refine×2/compress） | qwen3.5-plus | 77.4% | 113 |
| thinkdepthai-qwen | 单 agent ReAct + 反思 | qwen3.5-plus | ~79.0% | 105 |

共 **372 failure case** 进入失败分析标注。

---

## 2. 轨迹行为意图打标（一笔带过）

每条 trajectory 的每条 SQL 独立打 **19 类意图** + **3 类数据源**（logs/traces/metrics）：

- 19 类按 5 认知阶段聚合：`triage` / `trace_investigate` / `log_investigate` / `metric_diagnose` / `baseline`
- Opus-4.6 自动打 → 人工 check → 存 `meta.llm_intents.final`
- 覆盖率 100%（4 exp_id × 500 case）
- 用途：① 行为指纹雷达（8 维） ② n-gram / transition 分析 ③ **元认知 middleware 的 trigger 输入**

---

## 3. 失败模式分析（**重点**）

### 3.1 设计思路：4 轴正交

目的是让**不同性质的失败**各归其位，为中间件设计提供**可落位的目标**。

```
   D (数据障碍)  +  R (推理机制)  +  PD (过程缺陷)  +  F (框架架构)
   ────────────    ─────────────    ─────────────    ────────────
   数据集的锅       agent 动作的锅    agent 漏动作      框架代码的锅
   单标签           单标签            多标签 (0..N)     per-framework
   case-by-case     case-by-case      case-by-case      per-framework
```

**正交性硬要求**：每轴在每 case 独立判定，不能互相换皮。
- D ≠ fault_type（修正过一次：旧 D 按 JVM/Pod/Network 分桶是错的；新 D 按"路径哪个点被挡住"分）
- R ≠ D 的结果（noise 数据配 noise-anchor 推理是两个独立判断）
- PD ≠ R 缺动作（U1 anchor 是 R 动作错；PD_NoBaselineContrast 是缺 baseline_contrast 这一步，可能和 U1/U2/U5 共存）
- F ≠ 通用 R（aiq 的 compress/refine 只能改代码，不是 middleware 能救）

---

### 3.2 D 轴 — 数据障碍（7 类 + 1 parking，372 case 全覆盖）

**判据**: 每 case 真实 GT 路径上，agent 被数据集的哪个点卡住。每类跨 10-19 个 fault_type（证明不是 fault_type 换皮）。

| # | 名字 | N | 代表障碍 |
|---|---|---:|---|
| D1 | **VictimSilentOnPath** | 142 | GT 节点本身不发信号（spans 消失 / status=Unset / error=0）|
| D2 | **CrossLayerSignalGap** | 67 | GT 信号只在一层可见（JVM metric）,agent 查另一层 |
| D3 | **AmbientNoiseDominates** | 50 | GT-邻近服务的 chronic noise 压过 GT（rabbitmq DNS）|
| D4 | **EdgeSymmetricAmbiguity** | 36 | A→B edge 注入，两端对称可见 |
| D5 | **CascadeSymptomLouderThanGT** | 34 | 下游 ripple 的 error_count 超过 GT |
| D6 | **NameTwinOnPath** | 23 | GT 有命名孪生抢眼球（food vs station-food）|
| D7 | **DilutedMultiCandidate** | 17 | 注入窗口窄 / 冷门服务，信号被 normal 稀释 |

---

### 3.3 R 轴 — agent 推理机制（5 unified + 8 framework-specific）

**判据**: agent 做了什么错动作（anchor / infer / reverse / confuse）。跨框架合并时按"机制同质"。

**Unified R**（≥2 framework 贡献）：

| # | 名字 | N | 机制一句话 |
|---|---|---:|---|
| **U1** | LoudnessAnchorOverSilentVictim | 140 | 按 error_count / latency / restart 排名选 top，不做因果验证 |
| **U2** | ChronicAmbientNoiseAnchor | 85 | 看绝对错误量，不做 normal-vs-abnormal baseline diff |
| **U3** | EdgeDirectionOrRegionEndpointError | 48 | 找对了 A→B edge 区域但选错端点/方向 |
| **U4** | NameTwinSiblingConfusion | 18 | 没做名字消歧 SQL，命名最显眼的同族为 RC |
| **U5** | SilenceReadAsHealthOrPaused | 17 | 显式把"no error"读成"healthy" |

**Framework-specific 8 类（不跨）**：aiq.R_hub_fabrication(12), aiq.R_correct_then_reversed(13, F2 候选), aiq.R_compress_drift(8, F1 候选), claudecode.R6_InfraLayerSkipped(7, analytical_only), claudecode.R7_JVMSymptomMisreadAsDB(4), sonnet.R_OscillationToCompromisePair(4), sonnet.R_NarrativeOverMatchedMagnitude(3), qwen.R_E_PathOvershoot(6), qwen.R_F_QueryDesignBuriesSignal(5)

---

### 3.4 PD 轴 — 过程缺陷（多标签，9 unified + 7 framework-specific）

**判据**: agent 在 trajectory 里**漏做了**哪个过程动作。multi-label 因为一个 case 可以同时缺多个步骤。

**Unified PD**（跨框架通用）:

| PD | N | 含义 | V vs R | V vs D | 耦合情况 |
|---|---:|---|---:|---:|---|
| **PD_NoBaselineContrast** | 316 | 没做 normal vs abnormal 对比 SQL | 0.33 | 0.18 | 黄区 (R) |
| **PD_NoCallTreeBuild** | 202 | 没重构 service→service 调用层级 | 0.20 | 0.18 | **绿** |
| **PD_NoFaultLayerMetricProbe** | 188 | 该查 jvm/k8s/db/网络层时没查 | 0.32 | 0.33 | 黄 (D,R) |
| **PD_NamedCandidateNotIsolated** | 81 | 候选 RC 从未被单服务 WHERE 隔离查询 | **0.54** | 0.38 | 红 (R) 保留 |
| **PD_ErrorOnlyFilterBias** | 73 | 只按 error 过滤，漏 latency/jvm/memory | 0.35 | 0.31 | 黄 (D,R) |
| **PD_SurveyWithoutDrill** | 59 | 做了 scan 但没 drill 到具体 span | 0.26 | 0.21 | **绿** |
| **PD_LateExplorationDegenerate** | 25 | 后期探索反而降级收敛 | 0.30 | 0.27 | 黄边缘 |
| **PD_MultiRCCompromise** | 7 | 同时命名多个 RC 妥协 | **0.76** | 0.18 | 红 (R) 保留 |
| **PD_TraceFollowAbsent** | 6 | 从未 trace_follow 单次请求 | 0.22 | 0.12 | **绿** |

**正交性体检**: 中位数 V = 0.30，2/9 红区（<1/3 上限），未触发 recluster。红区 PD 保留因其机制是真正的过程动作，和 R 的高耦合是**真实因果链接**（"跳过 baseline → 必然 anchor noise"），不是换皮。

---

### 3.5 F 轴 — 框架架构失败（per-framework，不跨）

| Framework | F | 机制 | Cases |
|---|---|---|---:|
| **aiq** | F1 CompressDrift | compress LLM 覆盖 terminator 结论，文本显眼度压过 | 8 |
| **aiq** | F2 RefineStageReversesCorrect | refine stage 把 "silent pod = 健康" 当证据反推 stage_0 正解 | 13 |
| claudecode | (空) | — | 0 |
| sonnet | (空) | — | 0 |
| qwen | (空) | — | 0 |

**F 共占 aiq 失败 21/113 = 18.6%**，这部分必须改框架代码，middleware 无效 → 明确排除在中间件目标外。

---

## 4. 中间件设计（**重点**）

### 4.1 v4 元认知中间件 6 条设计原则

| # | 原则 | 反面教材 |
|---|---|---|
| 1 | **元认知 ≠ 低层操作** | ❌ "MANDATORY: 跑 `SELECT ... GROUP BY service_name`" （把答案喂步骤）|
| 2 | **Trigger 必须运行时可观测 framework-agnostic** | ❌ 用 `chronic_noise_carriers=['ts-rabbitmq',...]` GT-derived 硬编码 |
| 3 | **Vocabulary 用认知词不用拓扑词** | ❌ "caller/callee/upstream/downstream/silent victim" → ✅ "另一个候选 / 另一种可能" |
| 4 | **干预内容 = 1 主问 + 0~3 次问，开放反问不命令** | ❌ "先查 normal_logs 看 ts-rabbitmq" → ✅ "你看到的错误，有没有可能没有故障时也是这样的？"|
| 5 | **3 层管线合并到 L1 快筛 + 单次 LLM 调用（L2/L3 合并）** | opus-4.7 自主判断 triggered/primary/secondary/intervention_text，无评分阈值 |
| 6 | **Framework-specific 适配层自带 pipeline-specific 卡** | aiq 的 A1-A5 用 stage terminator 概念；通用层 M1-M10 不用 |

### 4.2 通用维度 M1–M10（跨 3 framework 复用）

每张卡片固定包含：`来源 mapping（D/R/PD）` → `Cognitive vocabulary` → `Trigger abstract(伪代码)` → `Intervention text(主问+次问)` → `9 项自检`

| Card | 对应 R/PD | 机制要让 agent 反思的是 | 翻盘期望 |
|---|---|---|---:|
| **M1** LoudnessAnchorSelfcheck | U1 + PD_NoFaultLayerMetricProbe | "排名靠前 ≠ 故障来源，反向假设" | ~31 case |
| **M2** ChronicNoiseSkepticism | U2 + PD_NoBaselineContrast | "这错误在没故障时也有吗" | ~38 |
| **M3** OutputGraphInternalConsistency | U3 变体 | "自己标了问题的节点为啥没进 RC" | 跨 framework |
| **M4** SiblingDisambiguation | U4 | "有没有近名服务也匹配路径" | ~7-9 |
| **M5** SilenceNeqHealth | U5 | "看不到错误 ≠ 一定健康" | ~7（qwen 主）|
| **M6** BaselineContrastReflex | PD_NoBaselineContrast 独立触发 | 触发率最高 **~316 case** |
| **M7** LayerCoverageReflex | PD_NoFaultLayerMetricProbe | "故障层的运行时指标查过吗"（GT 脱敏：不依赖 fault_category）|
| **M8** HypothesisCounterfactual | U1 变体 + PD | "candidate 反事实验证" |
| **M9** InvestigationStagnation | 沿袭 v3 B1（14/14 全翻盘） | 同 intent 重复循环检测 |
| **M10** PrematureCommitment | v3 "qpf<37 提前收敛" 42% case | 基于 framework round count P25 先验 |

**M9 ↔ M10 互斥** 防重复干预；**M6+M2 / M7+M1 / M8+M1** 要 L2 消歧规则。

### 4.3 框架特有适配层

| Framework | 适配卡 | 触发时机 | 总干预次数 |
|---|---|---|---:|
| **thinkdepthai** (qwen + sonnet 共用) | 无新卡，复用 M1-M10 | 中期 `round=30`(qwen) / `22`(sonnet) + 结论前 | 1 中 + 1 终 |
| **aiq** | A1-A5（5 卡）+ M1-M10 | 中期 `post_stage_0_main_terminator` + 结论前 `reflect 第二次循环结束、finalize 之前` | 1 中 + 1 终 |
| **claudecode** | C2（M7 加强变体，阈值 6）+ M1-M10 | 中期取消 + 结论前 `compress 调用前` | 0 中 + 1 终 |

**aiq 的 A 卡**（针对其 pipeline 特性）：
- A1 StageCommitment, A2 RefinementWithoutNewProbe, A3 CompressDriftSelfcheck, A4 HubFabricationAwareness, A5 AntiFlipFlopReflex
- **A3/A5 对应原 F1/F2**（compress drift / correct-then-reversed）—— 把"框架架构失败"也纳入元认知反思范围（即使不能彻底修复，至少让 agent 警觉）

**claudecode 的 C2**：M7 的 claudecode 变体，阈值 6 vs 通用 8，并加 T5 "JVM 被误读成 DB" 提示（claudecode 上 DuckDB 语言特点导致 JVM metric 常被漏）

### 4.4 Trigger / Intervention 风格示例（M1）

```
Trigger (伪代码，运行时信号):
  about_to_commit
  AND count(ranking intents in last 8 rounds) ≥ 2
  AND candidate_RC ∈ last_ranking_query.top_3_rows

Intervention (主问):
  "排名靠前不一定就是故障来源——也可能是别的原因放大了它的错误。
   你能反过来问：如果不是这个候选，会是什么？"

Intervention (次问, 0-3 条, 按 L2 match_score ≥ 0.7 加):
  - "有没有候选完全没在 ranking 顶部但可能更相关？"
  - "这个候选的下游/同层指标你查过吗？"
```

### 4.5 期望翻盘

| Framework | 预期翻盘 case / total failed | 占比 |
|---|---|---:|
| thinkdepthai (qwen+sonnet) | 70-90 / 156 | 45-58% |
| aiq | 50-60 / 113 | 44-53% |
| claudecode | 35-45 / 103 | 34-44% |
| **合计** | **155-195 / 372** | **42-52%** |

---

## 5. 验证闭环（一笔带过）

### 5.1 离线 label 自洽性 re-verification（已完成）

D / R / PD 标签经 v1 → v2 → v3 → v4 四轮 pipeline：X-1 taxonomy 收紧 → X-2 adjudicator 重写 → X-3 rerun → X-4 queue → X-5 apply relabel → X-6 DB 更新 & final VC。

| Stage | Agree (mechanical) | Agree (judged) |
|---|---:|---:|
| v1 baseline | 53.7% | 46.4% |
| v4 final | **95.9%** | **73.2%** |

超过 plan 验收阈值 90%。

### 5.2 Middleware 在线 A/B 验证（**Phase 8，待做**）

- 每 framework 同 case baseline vs middleware 两次 rollout
- Gate: regression_rate ≤ 5% 且 net_ΔAC@1 > 0（95% CI 排除 0）
- 离线触发 precision / recall 用 `PD_projection.jsonl` 查表做初筛（Gate 3）
- 预计新增 AC@1：+9% ~ +14%（155-195 翻盘 / 2000 rollout）

---

## 附录：关键产物路径

| 类别 | 路径 |
|---|---|
| D / R / PD / F taxonomy | `analysis/3-failure-modes/merged/{D,unified_R,PD}_taxonomy.md` + 各 framework `v1/F_catalog.md` |
| 4 framework 归纳工作区 | `analysis/3-failure-modes/2-by-framework/{aiq-qwen3.5-plus,claudecode-qwen3.5-plus,thinkdepthai-claude-sonnet-4.6,thinkdepthai-qwen3.5-plus}/v{1,1_harp,2}/` |
| v4 设计原则 | `analysis/4-middleware/v4_principles.md` |
| v4 10 通用维度卡 | `analysis/4-middleware/v4_dimensions/M{1..10}*.md` |
| v4 aiq 适配层 | `analysis/4-middleware/v4_aiq_qwen3.5_plus/{README,A1..A5}.md` |
| v4 claudecode 适配层 | `analysis/4-middleware/v4_claudecode_qwen3.5_plus/{README,C2}.md` |
| v4 thinkdepthai 适配层 | `analysis/4-middleware/v4_thinkdepthai_qwen3.5_plus.md` |
| 中期检查策略 | `analysis/4-middleware/v4_mid_check_strategy.md` |
| 验证闭环报告 | `analysis/3-failure-modes/merged/verify_mismatch_report.final.md` |
