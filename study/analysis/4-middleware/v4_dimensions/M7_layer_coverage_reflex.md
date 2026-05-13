# M7 — Layer-Coverage Reflex

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-3 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | 372 case 中数量 |
|---|---|---|---:|
| **PD 层** | `PD_NoFaultLayerMetricProbe` | （原 PD 定义依赖 fault_category；M7 已 **GT 脱敏**为纯行为统计）agent 全程没查过任何运行时层指标（jvm/container/k8s/db/network），但应用层 intent 大量触发 | **188** |
| **R 层** | (相关) U1 LoudnessAnchorOverSilentVictim — 无运行时层指标信号常导致 agent 锚定应用层最响亮的服务 | (背景) |

**对应失败 case 数（M7 主问触发的初步估计）**：
- 严格按 GT 脱敏的 v4 trigger（应用层 intent ≥ N + 运行时层 intent = 0）：~150-180 case
- M7 主问的目标 case 池：~150 case（去掉与 M1 重叠的部分）

**Per-framework 分布**（来自 PD_taxonomy.md）：
- aiq-qwen3.5-plus: 40 / 113 = 35.4%
- claudecode-qwen3.5-plus: 45 / 102 = 44.1%
- thinkdepthai-claude-sonnet-4.6: 未独立 induced，但 v4 trigger 通用可适用
- thinkdepthai-qwen3.5-plus: 103 / 105 = 98.1%

---

## Cognitive vocabulary

**这种认知模式是什么样**：

RCA 任务里通常有多层信号：**应用层**（HTTP error logs、service traces、span latency）和**运行时层**（JVM heap / GC、container CPU/memory、k8s pod state、DB connection pool、network L4 metrics）。当故障是基础设施级（pod 被 kill、JVM OOM、网络丢包等），**应用层只能看到二次症状**（请求失败、延迟升高），但**真正的故障指纹在运行时层**。

agent 的失败模式是：**只查应用层数据就 commit**。它跑了几十个 error_log / latency_ranking 类查询，找到了某个看起来"很有问题"的服务，commit 了。**但它从未查过运行时层指标**——所以它看不到该候选其实只是被 OOM 的 pod 拖慢的下游受害者，真正的故障在运行时层完全不同的位置。

**M7 的 GT 脱敏关键**：原 PD 检测用 fault_category mapping（"如果 fault_category=JVMChaos → 应该查 jvm_state"）—— 这依赖 GT。**v4 不能用 fault_category**。M7 改为纯行为统计触发：**只看 agent 已查的 intent 类别构成**——应用层 intent 有 N 个，运行时层 intent = 0 个，就触发，**不告诉 agent 是哪一层**，让 agent 自己判断。

**反思的认知动作**：让 agent 意识到自己**只在一个数据层探查**这件事，反问"在 commit 之前你确定问题一定不在那些没查过的层？"——把"补哪些层的查询"的决策权留给 agent 自己。

---

## Trigger abstract（运行时可观察）

```pseudo
trigger_M7(state) :=
  (LET app_layer_intents = { 'error_log_overview', 'service_error_log',
                             'service_log_browse', 'keyword_search',
                             'error_timeline', 'error_rate_scan',
                             'latency_ranking', 'throughput_compare',
                             'service_trace_scan', 'trace_follow',
                             'call_tree_build' }
   LET runtime_layer_intents = { 'jvm_state', 'container_resource',
                                 'k8s_state', 'db_state', 'network_layer',
                                 'metric_scan' }   // metric_scan 是泛指标 scan
   LET app_count     = COUNT(state.intent_log WHERE intent IN app_layer_intents)
   LET runtime_count = COUNT(state.intent_log WHERE intent IN runtime_layer_intents)
   IN
     app_count >= 8
     AND runtime_count == 0)
```

**触发场景示例**：
- thinkdepthai-qwen：trajectory 里几十个 SQL 都是 `FROM abnormal_logs / abnormal_traces`，从没跑过 `FROM abnormal_metrics WHERE name LIKE 'jvm.%'` / 任何 metric 表
- claudecode：Bash 命令全是 query app-level 数据，从未通过 Bash 跑过 metrics/容器状态查询
- aiq：stage_0 全部 SQL 都在 application 层，stage_1/stage_2 也没补运行时层

---

## Intervention pattern

### 主问（M7 作为 most_critical 时）

> **你查了大量应用层的数据（错误日志、trace、延迟），但你还没碰过运行时层的指标（容器、进程、网络等）。在你 commit 之前，你确定问题一定不在那些没查过的层？应用层看到的现象有时只是其他层问题的二次症状——值得在确认前补一些运行时层的查询。**

**变体**：
- 变体 A（中期检查，agent 还在调查阶段但已大量查应用层）：
  > "你查了不少应用层的数据，但还没碰过运行时层（容器/进程/网络等）的指标。应用层的'问题'有时只是其他层故障的二次表现。在你继续推进之前，能不能补一些运行时层的查询，看看那些层是不是有更明显的信号？"
- 变体 B（结论前检查，agent 即将提交但全程没查运行时层）：
  > "你即将提交根因，但你的整个调查只覆盖了应用层数据，没看过运行时层的指标。在最终提交前请确认：你是基于完整的层覆盖做的判断，还是可能漏掉了在其他层才能看出的信号？"

### 次问（M7 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你的查询都集中在应用层，可以顺带补一些运行时层（容器/进程/网络）的查询，避免漏看其他层的信号。"

**次问触发条件**：M7 作为次问被加入复合干预，**仅当** L2 对 M7 给出 `match_score ≥ 0.7`（即应用层 intent ≥ 8 + 运行时层 intent = 0）。如果 agent 已查过任何运行时层 intent，L2 给 M7 低分，**不加 M7 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 完全基于 intent 类别计数，**不查询** fault_category / fault_type / required_metric_layer）
- [x] **Trigger 不含 SQL 字符串**（用 intent 抽象类别）
- [x] **Trigger 不含具体服务名**（trigger 是全局 intent 计数，不涉及具体服务）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（无）
- [x] **Intervention 不含错误消息字串**（无）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（用"二次症状"是认知词，不是拓扑方向）
- [x] **Intervention 用反问 + 多种可能性句式**（"应用层看到的现象有时只是其他层问题的二次症状"——开放可能性；"是基于完整的层覆盖做的判断，还是可能漏掉了..."——开放对比）
- [x] **agent 可基于自身已做的动作自我修正**（"你查了大量应用层的数据"引用 agent 自己的 query 行为）

**全部 9/9 ✓ → M7 卡片符合 v4 元认知设计原则**

**重要审核点**：

1. **GT 脱敏成功？** ✓ 原 PD 用 fault_category mapping（"JVMChaos → jvm_state"），M7 完全不用，只用应用层 vs 运行时层 intent 计数。Trigger 不告诉 agent 该查哪层（"运行时层"是泛指容器/进程/网络/数据库的统称，不是具体哪一层），让 agent 自己判断。
2. **"运行时层"列表是否引导答案？** Intervention 中列了"容器、进程、网络、数据库"作为括号内例子。这是引导吗？我的判断：**不算引导**——这些都是 RCA 任务中的标准层级名称（任何 RCA 资料都会列这些），不是 RCABench 数据集特有的指针。但若审核认为"列出层级清单"也算暗示，可改成只说"运行时层"不展开例子——但会降低 agent 对该建议的可执行性。

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✓ 主问候选 | 98% PD3，**几乎全 case 触发** |
| thinkdepthai (claude-sonnet-4.6) | ✓ 主问候选 | 未独立 induced，但 v4 trigger 通用可适用 |
| aiq (qwen3.5-plus) | ✓ 主问候选 | 35% PD3 |
| claudecode (qwen3.5-plus) | ✓ 主问候选 | 44% PD3 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

| Framework | failure case 总数 | PD3 占比 | M7 主问命中估计（去掉与 M1 重叠后）| M7 翻盘期望（按 v3 类比 ~25% 翻盘率）|
|---|---:|---:|---:|---:|
| thinkdepthai-qwen3.5-plus | 105 | 98% | ~50（去 M1 重叠后）| ~12 case 翻盘 |
| thinkdepthai-claude-sonnet-4.6 | 50 | (待统计) | ~15 | ~4 case 翻盘 |
| aiq-qwen3.5-plus | 113 | 35% | ~30 | ~7 case 翻盘 |
| claudecode-qwen3.5-plus | 102 | 44% | ~35 | ~9 case 翻盘 |

**总翻盘期望**：~32 case 跨 4 framework。

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **M1 (Loudness-Anchor)** | M7 触发场景里 agent 经常已经选了应用层最响亮的服务作 RC | M1 关注 commit 时点的 ranking 启发式，M7 关注全程层覆盖。两者**互补**：M1 主+M7 次是 v4 复合干预最常见的组合（v3 实测 B3+M1 翻盘最多）|
| **M6 (Baseline-Contrast)** | M7 触发场景里 agent 通常也没做 baseline | M6 关注时间维度（normal vs abnormal），M7 关注层维度。维度正交，可同时命中 |
| **M9 (Investigation Stagnation)** | M7 触发时 agent 可能在应用层重复查询 → M9 也可能命中 | M9 关注重复模式，M7 关注层缺失。可同时命中 |

---

## 实施备注

- **关键依赖**：
  - L1 必须正确分类 19 类意图，特别是区分 `metric_scan`（泛指标 scan）vs `error_log_overview`（应用层 log）。当前 19 类意图分类已包含必要的细分，准确率由 opus-4.7 保证
  - 阈值 `app_count >= 8` 是 v4 经验值，D-3 审核可调；过低会误伤刚开始调查的 case，过高会漏掉短轨迹的失败
- **GT 脱敏代价**：v4 M7 不告诉 agent "应该查哪一层"，所以 agent 收到提醒后需要自己判断要查哪层。这可能导致 agent 选错层（例如 fault 是 JVM 但 agent 选了去查 k8s）。**优化方向**：D-3 审核可考虑加入"次级判断"——让 L2 在给 M7 高分时，根据 application-level 数据中的间接线索（如 timeout error 暗示网络/数据库；OOM 错误暗示 JVM；503 暗示 pod）给 L3 prompt 一些上下文，让 L3 生成的 intervention 包含"看起来更可能是 X 层" 的弱提示。但这接近"暗示答案"，**当前 v4 选择保守路线：完全让 agent 判断**
- **离线重放验证**：在 372 已标注 case 上跑 trigger，统计 (precision, recall) 相对于 PD_NoFaultLayerMetricProbe 标注

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-3 阶段输出） |
