# C2 — Layer-Coverage Reflex（claudecode 变体）

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**基础维度**: [M7 Layer-Coverage Reflex](../v4_dimensions/M7_layer_coverage_reflex.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-7 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | claudecode 失败 case 中数量 |
|---|---|---|---:|
| **claudecode v1 theme** | **T4 InfraLayerSkipped** | agent 只查应用层 Bash 查询，没碰过运行时层指标 | **7 / 103 (6.8%)** |
| **claudecode v1 theme** | **T5 JVMMisreadAsDB** | agent 看到连接池 / 超时现象就诊断"数据库问题"，但真实故障在 JVM 层 | **4 / 103 (3.9%)** |
| **（已合并到 C2 的变体提示）** | 原 C3 JVM vs DB Disambiguation | 单独卡片数据量太小（4 case）| 并入 C2 变体提示 |

**C2 vs M7 的关系**：
- C2 是 M7 在 claudecode 上的**加强变体**——基础 trigger 与 M7 相同，但**阈值调低**（claudecode 的 Bash intent 提取有延迟）+ 额外一段提示词应对 T5 模式（"数据库症状可能不是数据库的问题"）
- **共享 M7 trigger 骨架**：应用层 intent ≥ N + 运行时层 intent = 0
- **claudecode-specific 调整**：
  - 阈值 `app_count >= 6`（M7 是 8）——claudecode 的 Bash 命令多样，部分 Bash 不走 DuckDB（如 `head`, `cat`, 元数据查询），L1 能分类到 19 类 intent 的比例较低，所以真实 query 数乘以折扣系数
  - 干预文本多一句"运行时层问题有时通过应用层（如连接池、超时）表现"——对应 T5 误诊模式

**对应失败 case 数**（C2 主问触发的初步估计）：
- 严格触发（M7 trigger + claudecode 阈值）：~11-15 case（T4 + T5 全覆盖）
- **C2 主问的目标 case 池：~10-12 case**

---

## Cognitive vocabulary

**这种认知模式是什么样**：

claudecode 通过 Bash 工具跑 DuckDB 查询 parquet 文件。和 thinkdepthai/aiq 类似，claudecode 的失败模式 T4 InfraLayerSkipped 是**只查应用层数据就 commit**——agent 跑了几十个 `duckdb -c "SELECT ... FROM abnormal_logs WHERE ..."` 类查询，锁定某个应用层最响亮的服务。**没查过运行时层**——没跑过 `SELECT ... FROM abnormal_metrics WHERE name LIKE 'jvm.%'` 或 container/k8s 相关表。

**T5 JVMMisreadAsDB 的特殊模式**：agent 看到应用层现象（连接池耗尽 / 超时 / 请求堆积）就诊断"这是数据库问题"——直觉上看 DB 指标，但真实 GT 是 JVM（OOM / GC 压力导致 app 无法向 DB 写入，**现象**看起来像 DB 慢但**真正的问题所在**在 JVM）。agent 被"直觉关联"带偏：连接池症状 = DB 问题。

**C2 的加强**：在基础 M7 的"你没碰运行时层" 之外，加一句针对 T5 的提醒——**应用层观察到的某些现象（连接池、超时、重试）可能是其他层问题的二次表现，不一定是该层本身有问题**。让 agent 意识到"连接池症状"不必然等于"数据库问题"，可能是 JVM / 网络 / 容器的二次表现。

**反思的认知动作**：
- 基础部分（继承 M7）：让 agent 意识到自己只查了应用层，反问"在 commit 之前你确定问题一定不在那些没查过的层？"
- 变体加强（C2 特有）：让 agent 意识到"某应用层症状"和"该层是故障本身"不是同一件事——应用层看到的是否是其他层问题的**二次表现**？

---

## Trigger abstract（运行时可观察）

```pseudo
trigger_C2(state) :=
  // 基础 trigger：与 M7 相同但阈值调低
  (LET app_layer_intents = { 'error_log_overview', 'service_error_log',
                             'service_log_browse', 'keyword_search',
                             'error_timeline', 'error_rate_scan',
                             'latency_ranking', 'throughput_compare',
                             'service_trace_scan', 'trace_follow',
                             'call_tree_build' }
   LET runtime_layer_intents = { 'jvm_state', 'container_resource',
                                 'k8s_state', 'db_state', 'network_layer',
                                 'metric_scan' }
   LET app_count     = COUNT(state.intent_log WHERE intent IN app_layer_intents)
   LET runtime_count = COUNT(state.intent_log WHERE intent IN runtime_layer_intents)
   IN
     app_count >= 6      // ★ 阈值 6（M7 是 8），适配 claudecode Bash intent 提取延迟
     AND runtime_count == 0)

  // T5-specific enhancement（额外 signal）：
  //   reasoning 文本含应用层关联到特定"直觉层"的推断（如连接池 → 数据库）
  //   这个 signal 不是独立 trigger，而是让 L2 给 C2 更高的 match_score
```

**辅助 signal（L2 评估 C2 match_score 时额外考虑）**：
- reasoning 文本中含"connection pool" / "timeout" / "retry" / "database slow" 等词 → 提高 C2 置信度（T5 模式特征）
- reasoning 文本 "the database is the bottleneck" / "I think this is a DB issue" 但 trajectory 中 db_state intent = 0 → 强化 C2 T5 变体

**触发场景示例**：
- claudecode 的 Bash 命令都是 `duckdb ... abnormal_logs WHERE service = ...`，从未跑过 jvm / container / k8s 类查询 → 基础 C2 命中
- reasoning 中 agent 写 "I see connection pool exhaustion, this is a database issue"，但 trajectory 里 runtime intent = 0 → C2 T5 变体特别命中

---

## Intervention pattern

### 主问（C2 作为 most_critical 时）

> **你查了大量应用层的数据（错误日志、trace、延迟），但你还没碰过运行时层的指标（容器、进程、网络、数据库等）。在你 commit 之前，你确定问题一定不在那些没查过的层？应用层看到的现象有时只是其他层问题的二次表现——比如连接池、超时、重试这些症状，表面看像应用层或数据层的问题，但真正出问题的可能是 JVM、容器或网络层。值得在确认前补一些运行时层的查询。**

**变体**：
- 变体 A（中期检查，基础 T4 模式）：
  > "你查了不少应用层的数据，但还没碰过运行时层（容器/进程/网络/数据库等）的指标。应用层的现象有时只是其他层故障的二次表现。在你继续推进之前，能不能补一些运行时层的查询，看看那些层是不是有更明显的信号？"
- 变体 B（中期/结论前，T5 JVM-misread 特定模式）：
  > "你看到了一些应用层症状（连接池 / 超时 / 慢响应），准备把这归结为某一层的问题——但这些症状不一定意味着该层就是真正有问题的那一层。同样的现象也可能是进程在另一层（比如 JVM 堆栈压力、GC 停顿）被卡住导致的二次表现。在最终判断前能不能补一些其他层的指标，看看真正有问题的是不是你直觉判断的那一层？"
- 变体 C（结论前检查，agent 即将提交但全程没查运行时层）：
  > "你即将提交根因，但你的整个调查只覆盖了应用层数据，没看过运行时层的指标。应用层的现象有时是其他层问题的二次表现。在最终提交前请确认：你是基于完整的层覆盖做的判断，还是可能漏掉了在其他层才能看出的信号？"

### 次问（C2 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你的查询都集中在应用层（通过 Bash + DuckDB），可以顺带补一些运行时层的查询——你看到的应用层现象可能是其他层问题的二次表现。"

**次问触发条件**：C2 作为次问被加入复合干预，**仅当** L2 对 C2 给出 `match_score ≥ 0.7`（即应用层 intent ≥ 6 + 运行时层 intent = 0）。若 agent 已查过任何运行时层 intent，L2 给 C2 低分，**不加 C2 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 完全基于 intent 类别计数，**不查询** fault_category / fault_type / required_metric_layer）
- [x] **Trigger 不含 SQL 字符串**（用 intent 抽象类别）
- [x] **Trigger 不含具体服务名**（trigger 是全局 intent 计数，不涉及具体服务）
- [x] **Intervention 不含 SQL 字符串**（主问/次问/变体全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（无）
- [x] **Intervention 不含错误消息字串**（"connection pool" / "timeout" / "retry" 是**通用 RCA 术语**，不是 RCABench 特有错误消息字串；是层次概念词，不是数据字符串）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（用"真正有问题的那一层"、"二次表现"等认知描述代替拓扑方向）
- [x] **Intervention 用反问 + 多种可能性句式**（"这些症状不一定意味着该层就是真正有问题的那一层。同样的现象也可能是进程在另一层被卡住导致的二次表现" ——经典两种可能并列；"你是基于完整的层覆盖做的判断，还是可能漏掉了..."——开放对比）
- [x] **agent 可基于自身已做的动作自我修正**（"你查了大量应用层的数据"、"你看到了一些应用层症状" ——引用 agent 自己的 query / 推理行为）

**全部 9/9 ✓ → C2 卡片符合 v4 元认知设计原则**

**重要审核点**：

1. **"连接池 / 超时 / 重试"是否暴露答案层级？** 不暴露——这三个词是 **RCA 任务通用层次 vocabulary**（任何 RCA 资料都会提到这些症状），不是 RCABench 特有提示。让 agent 看到这三个词会让它反思"我是不是把症状当故障本身了"——这是元认知自检，不是答案注入
2. **T5 变体是否过于具体？** 变体 B 提到 "JVM 堆栈压力、GC 停顿"。这是"可能的其他层"的例子，用于让 agent 意识"不是只有数据层"。不指定 GT 是哪一层——只列出可能性供 agent 自检。若审核认为过于具体，可改为"比如进程层 / 基础设施层"的抽象表述
3. **为何 claudecode 需要变体而其他 framework 用 M7 就够？** v1 T5 JVMMisreadAsDB (3.9%) 是 claudecode 独有的误诊模式（其他 framework 没有该 theme 或命中极少）。加入 T5 提示词变体**专门针对该模式**，避免 M7 只给"你没查运行时层"的通用提示让 agent 跳过这个陷阱

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✗ | 用 M7 基础版（thinkdepthai 无 T5 误诊模式）|
| thinkdepthai (claude-sonnet-4.6) | ✗ | 同上 |
| aiq (qwen3.5-plus) | ✗ | 用 M7 基础版（aiq 无 T5 误诊模式）|
| claudecode (qwen3.5-plus) | ✓ 主问候选 | 中期主用维度；阈值调低 + T5 变体提示 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

| Framework | failure case 总数 | C2 触发估计 | C2 翻盘期望（~40%）|
|---|---:|---:|---:|
| claudecode-qwen3.5-plus | 103 | ~11-15（T4+T5）| **~4-6 case 翻盘** |

**总翻盘期望**：~4-6 case 跨 4 framework（仅 claudecode）。

**为什么翻盘率 40%**（略高于 M7 的 25%）：
- C2 的 T5 变体明确指出"应用层症状可能是其他层二次表现"——对 T5 模式有针对性
- 但实际翻盘依赖 agent 真的去查其他层——若中期介入时 claudecode 采用候选 C（取消中期）策略，C2 只能在 compress 前介入，agent 已无新查机会，翻盘率会显著下降（此时 C2 的价值主要是让 compress 阶段的 LLM 在最终 JSON 提取时更谨慎）

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **M7 (Layer-Coverage Reflex 基础版)** | C2 和 M7 trigger 完全重叠；claudecode 上**只启用 C2**，不启用 M7 | claudecode 的 L2 评估池中 M7 不出现，只有 C2；其他 framework 只有 M7，不出现 C2 |
| **M1 (Loudness-Anchor)** | C2 触发场景里 agent 常被应用层响亮的错误锚定 | 两者**互补**：M1 主 + C2 次是 claudecode 常见复合干预 |
| **M6 (Baseline-Contrast)** | C2 触发场景里 agent 通常也没做 baseline | M6 关注时间维度（normal vs abnormal），C2 关注层维度。维度正交，可同时命中 |
| **M2 (Chronic-Noise Skepticism)** | C2 触发场景可能伴 baseline 噪声问题（如 RabbitMQ DNS）| M2 关注 baseline 缺失 + 噪声 anchor；C2 关注层覆盖。两者正交，可同时命中 |

---

## 实施备注

- **关键依赖**：
  - L1 必须从 claudecode 的 Bash 命令中正确提取 DuckDB SQL 子串，再按 19 类意图分类。Bash 命令形态包括：
    - `duckdb -c "SELECT ... FROM abnormal_logs ..."`
    - `duckdb /path/to/file.parquet "SELECT ..."`
    - `python -c "import duckdb; ..."`
    - 非 SQL 类（`ls`, `head`, `cat`）→ 不产生 intent
  - Bash 提取 SQL 的 precision 不要求 100%——少量漏提取意味着 app_count 略低估，这是阈值 6 的设计冗余
- **阈值 `app_count >= 6`**：
  - 基于 v1 claudecode 103 failed case 的平均 Bash tool call count（未来 D-7.5 会重算）
  - 过低（≤ 4）会误伤刚开始的 case；过高（≥ 10）会漏掉 short-trajectory 失败
  - D-7.5 阶段可根据实际 Bash count 分布 + T4/T5 case 的 app_count 统计微调
- **T5 提示的展开时机**：变体 B 的"连接池 / 超时 / 重试"提示只在 L2 检测到 reasoning 文本含这类词时生效；否则用变体 A（更 generic）或变体 C（结论前通用）
- **离线重放验证**：在 103 claudecode failed case 上跑 C2 trigger，统计 precision/recall 相对于 v1 T4 + T5 标注

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-7 阶段输出）；C2 作为 M7 在 claudecode 上的加强变体（阈值调低 + T5 误诊提示）；原 C3 JVM-vs-DB 并入 C2 变体提示 |
