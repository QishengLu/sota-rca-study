# v4 元认知中间件 — 设计原则

**Plan**: [/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md](/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md)
**阶段**: D-0
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核

---

## 文档目的

本文档定义 v4 元认知中间件的**6 条设计原则**。所有 v4 维度卡片（M1..M10、A1..A5、C2）和适配层文档（thinkdepthai / aiq / claudecode）都必须遵守这些原则。原则是审核的标尺：任何后续维度卡片如果违反这些原则，应被退回。

---

## 原则 1 — 元认知 ≠ 低层操作

中间件的本质是**让 agent 反思自己的认知模式**，不是**告诉 agent 该跑什么命令**。

| 维度 | 元认知（v4 接受） | 低层操作（v4 拒绝） |
|---|---|---|
| **Trigger** 描述 | "agent 在 ranking 类 intent 后短时间内即将 commit"（intent 模式）| "trajectory 含 `SELECT service_name, COUNT(*) ... ORDER BY count DESC`"（具体 SQL）|
| **Intervention** 内容 | "排名靠前不一定就是故障来源，靠前可能是因为它本身故障，也可能是因为别的原因放大了它的错误。你能在确认前再做一次反向假设吗？"（开放性反思）| "MANDATORY: 跑 `SELECT service_name, COUNT(DISTINCT trace_id) FROM abnormal_traces ORDER BY 2 ASC LIMIT 10`"（操作指令）|
| **使用的词汇** | 认知词：anchor / commit / hypothesis / counterfactual / 反向假设 / 多种可能 / 另一种解释 | 领域词：ts-rabbitmq / abnormal_logs / parquet / WHERE / 上游 / 下游 / 受害者 / 故障源 |

**原因**：低层化的中间件等于把答案分步喂给 agent，绕过了 agent 自己推理的过程，无法泛化到新数据集，也无法判断 agent 的推理能力是否有真正提升。元认知化的中间件让 agent 自己得出结论，可移植到任何 RCA 任务和任何观测数据格式。

---

## 原则 2 — Trigger 信号必须是运行时可观测的 framework-agnostic 信号

中间件在 agent 推理过程中介入，**只能用 agent 在该时刻已经产生的信号**作为 trigger 输入。任何需要 GT、需要 offline 离线分析、需要事后人工标注的信号都**不能**用。

### 允许使用的信号（运行时可观察，不需要 GT）

| 信号类 | 说明 | 是否需 GT |
|---|---|---|
| **Intent classifier 输出**（19 类，已在 `meta.llm_intents.final` 中标注） | `baseline_contrast`、`call_tree_build`、`jvm_state`、`error_rate_scan` 等抽象意图类别 | ❌ 不需要 |
| **Trajectory 结构属性** | round count、tool_call count、phase 覆盖度（5 阶段触发数） | ❌ 不需要 |
| **Reasoning 文本特征** | think_tool 反思 / assistant.content 中的关键词频率、句法模式（不是错误消息字串） | ❌ 不需要 |
| **R-T 利用率**（round-level evidence 利用） | agent 在某 round 收到工具结果后下一 round 是否引用 | ❌ 不需要 |
| **Agent 自己产出的 draft graph 形状** | `len(root_causes)`、是否有节点被 agent 自己标记 UNAVAILABLE/RESTARTING 但未列入 RC | ❌ 不需要（只看 agent 自己的输出，不和 GT 比） |
| **字符串相似度**（Jaro-Winkler 等通用算法） | 比较 agent 输出 RC 与 trajectory 中其他出现过的服务名 | ❌ 不需要 |
| **Framework-级行为先验** | 该 framework 历史 success / failure case 的 round count P25/P50/P75 | ❌ 不需要（统计是先验，不是当前 case 的 GT） |

### 禁止使用的信号（需要 GT 或离线分析才有的信号）

| 信号 | 为什么不能用 |
|---|---|
| `cost_metrics`（开销） | 与失败模式无关 |
| 8-dim fingerprint 中的 `evidence`（除 R-T 利用率以外的）、`focus`、`accuracy`、`baseline` | 都需要 GT 比对才能算 |
| `fault_category` / `fault_type` | 是 GT 元数据，agent 在 RCA 任务里不应该提前知道 |
| `gt_services` / `chronic_noise_carriers` / `top_error_services` 等 parquet-derived 量 | 都来自 GT 标注或事后离线 query |
| 服务名硬编码列表（ts-rabbitmq / ts-food 等） | 领域知识，不能写进 trigger 或 intervention |
| SQL 字符串模板 / 错误消息字串列表 | 同上 |
| 上游/下游/源/汇/受害者/故障源 等方向性概念 | qwen 和 sonnet 在输出中用词不一致，会引入歧义；且这些是 GT 概念 |

**审核检查点**：每张维度卡片的 Trigger 字段中出现的所有谓词，必须能映射到"允许使用"表中的某一行；否则该 trigger 设计不合规。

---

## 原则 3 — 三层提炼到元认知

v4 维度库的源头是 X-1..X-6 重构后的 D / R / PD 三层失败分类（共 372 标注 case）。每个 v4 维度都对应到 D/R/PD 中的至少一类，但**提炼为元认知后必须脱去具体领域信息**。

### D 层（数据层挑战）→ 元认知警示型

D 描述"数据让任务变难的方式"。元认知化 = 提醒 agent **在某些观察形态下可能存在多种解释**，不要只取最直观的那个。

**例子**：
- **D 原描述**：D1 (VictimSilentOnPath) — GT 服务在排名查询里很低或缺失，因为它已经死掉/停止响应。
- **错误的元认知化**："当某服务在排名里很低时，它可能是受害者特征"——错误，因为"受害者"是 GT 概念，agent 不知道这个分类。
- **正确的元认知化**："当某个候选服务在排名查询里很低或缺失时，**不一定**意味着它健康，**也可能**意味着它停止工作了"——只列举多种可能性，不暗示哪个是对的。

### R 层（推理失败模式）→ 元认知反思型

R 描述"agent 推理出错的方式"。元认知化 = 把 R 类背后的认知偏差提炼为反思问句，让 agent 自检。

**例子**：
- **R 原描述**：U1 (LoudnessAnchorOverSilentVictim) — agent 把 error count 排名最高的服务当 RC，但真正 RC 是 silent 的。
- **错误的元认知化**："你选的是错的，真正的 RC 在另一个上游"——错误，告诉了答案位置。
- **正确的元认知化**："这个候选排名靠前是因为它故障，还是因为别的原因放大了它的错误？" ——只引导 agent 自检 anchor 假设，不告诉答案位置。

### PD 层（行为缺陷）→ 元认知遗漏检测型

PD 描述"agent 漏做的关键动作"。元认知化 = 在 trajectory 中检测某类动作未出现，提示 agent 反思动作选择。

**例子**：
- **PD 原描述**：PD_NoBaselineContrast — agent 从未对照 normal vs abnormal 数据。
- **错误的元认知化**："请运行 `SELECT * FROM normal_logs WHERE ...`"——错误，给了具体 SQL。
- **正确的元认知化**："你查了大量异常时段数据，但还没对照过正常时段。**有没有可能**你看到的'异常'本身在正常情况下也存在？"——只问反思问题，不指定 SQL。

---

## 原则 4 — 干预守则（继承 v3，加强）

每个 intervention 文本生成必须遵守以下硬规则：

### 不能做的事

1. **不能**告诉 agent 答案、根因服务、根因层级、故障类别
2. **不能**写出具体的表名、SQL 字符串、列名、metric 名
3. **不能**列出服务名、错误消息字串、领域专有名词
4. **不能**用方向性概念（上游/下游/源/汇/受害者/故障源/调用方/被调用方）—— 用 "另一个服务"、"另一种可能"、"相关的服务" 替代

### 应当做的事

5. **应当**让 agent 意识到自己刚刚做过什么动作 / 刚得到什么观察
6. **应当**用反问 + 多种可能性（"X 不一定是 Y，也可能是 Z 或 W"）的形式提出认知挑战
7. **应当**采用「主问 + 次问」复合结构（见下）
8. 引用 agent 实际做过的事（"你刚跑了 N 个排名查询" 可以，"你跑了 SELECT service_name ..." 不可以）

### 干预内容结构 — 1 主问 + 0~3 次问（v4 新增，区别于 v3）

v3 的干预是「围绕单一最关键维度提一个反思问题」。v4 允许复合，**但不强制复合**：

```
[主问] 1 个最关键维度的反思问题（按 L2 检测出的 most_critical 维度生成）
       ↓ 长度：2~3 句话，承担引导 agent 自检的主要责任
       ↓ **必有，永不省略**

[次问] 0~3 个相关维度的轻量提醒（按 L2 检测出的其他真实命中维度生成）
       ↓ 长度：每条 1 句话，作为"顺便也想想这些"
       ↓ 不要求 agent 直接响应，只在 reasoning 中顺带考虑
       ↓ **数量 = L2 真实命中的次级维度数量；不强行凑数**
       ↓ L2 只命中 1 个维度（即 N=1）时：干预只有主问，**0 次问**
       ↓ L2 命中 ≥2 个维度时：主问取 most_critical，次问 = 剩余命中（封顶 3）
```

### L2 命中判断的边界

L2 (claude-opus-4-7) 对每个维度独立给出 `match_score ∈ [0, 1]`。次问只采纳 `match_score ≥ 0.7` 的维度（高置信命中）；`< 0.7` 的维度即使排第二，也**不加为次问**。这是为了避免：
- L2 为"凑出 2-3 个次问"而强行从低分维度里选
- 弱命中维度的次问稀释主问的注意力
- 没真问题的维度被强加进 prompt

**例 1（中期检查 - L2 命中 M1=0.85, M6=0.78, M7=0.72，三个都 ≥0.7）**：

> 你最近几轮一直在看 error 排名，准备 commit 排名靠前的那个候选。**排名靠前不一定就是故障来源——也可能是因为别的原因放大了它的错误。你能在确认前先反过来问一下：如果不是它，会是什么？**
>
> 顺带你可以想一下：(a) 你查的都是异常时段数据，正常时段的同样数据你对照过吗？(b) 你定位到的候选服务，运行时层（容器/进程/网络）的指标你查过吗？

**例 2（中期检查 - L2 只命中 M1=0.85，其他维度都 < 0.7）**：

> 你最近几轮一直在看 error 排名，准备 commit 排名靠前的那个候选。**排名靠前不一定就是故障来源——也可能是因为别的原因放大了它的错误。你能在确认前先反过来问一下：如果不是它，会是什么？**

（**就到这里，没有次问**——因为 L2 没真检测到其他维度命中）

### 为什么不强制复合

- **强行凑次问 = 元认知噪声**：如果 L2 没真发现 baseline 缺失（agent 已对照过 normal），却强加一句"你查的都是异常时段数据..."，agent 可能反应"你说错了，我刚查过 normal_logs"，破坏中间件的可信度
- **简洁主问 > 杂乱复合**：单维度命中时只问一个问题更聚焦，agent 更容易行动
- **复合结构是机会，不是义务**：当 trajectory 真有多重盲点（这是 v3 实测中较常见的情况），复合干预能一次覆盖多个，提高翻盘率；但当只有一个盲点时，硬凑反而稀释

### 反例参照

老的 [merged/middleware_rules/U1*, U2*, U3*.md](../3-failure-modes/merged/middleware_rules/) 三张卡片是 v4 要明确避免的反面教材：含 SQL 模板、服务名硬编码、"MANDATORY 跑这条 SQL" 等命令式语言、"silent victim" / "downstream" 等 GT 方向性概念。

---

## 原则 5 — 干预节制（修订自 v3；D-7.5 framework-specific 放松）

每个 case 干预上限 = **中期 0 或 1 次 + 结论前 1 次**（**总共 ≤ 2 次**，按 framework 策略决定）。

D-7.5 决策后：thinkdepthai / aiq = 1 中 + 1 结；**claudecode = 0 中 + 1 结**（取消中期；详见 [v4_mid_check_strategy.md](v4_mid_check_strategy.md)）。

### 为什么修订（vs v3 的 3 中期 + 1 结论 = 4 次）

- v3 测了 105 case 发现 **42% (44/105) 的 case 在 query 37 之前已经 conclusion**——v3 的中期检查点 [37, 44] 完全错过这部分；
- 干预次数多 → 推理路径太长 → context 超限或 agent 注意力涣散；
- 单个 case 不需要四次干预，过多干预反而稀释每次的影响力。

### "层" vs "次" 概念明确

为避免混淆，v4 区分两个独立概念：

- **"层"** = 三层处理管线（intent 分类 / 缺陷检测 / 干预生成），是组件分工
- **"次"** = 一个 case 内触发干预的次数，是预算控制

| 概念 | v3 | v4 |
|---|---|---|
| **L1 / L2 / L3 三层管线** | 沿用 | 沿用（不变） |
| **中期检查次数** | 2 次（query 37 + query 44） | **1 次** |
| **结论前检查次数** | 1 次（compress 之前） | **1 次**（不变） |
| **总干预次数上限** | 3+1 = 4 次 | **1+1 = 2 次** |
| **同维度作为「主问」全程触发上限** | 1 次（不重复同盲点） | 1 次（不变） |
| **同维度作为「次问」是否计入上限** | （v3 无此概念） | **不计入**（次问是顺带提醒，不算独立触发） |

### 三层管线（v4 沿用 v3 架构 + 升级 LLM 选型 + L2/L3 合并为单次调用）

```
L1: SQL→intent batch 分类（19 类抽象意图）          [LLM: claude-opus-4-7]
R-T: round-level evidence 利用率提取                [纯代码，无 LLM]
        ↓
L2+L3 合并: 自主判断 + 干预生成（一次 LLM 调用）        [LLM: claude-opus-4-7]
       → 输入：维度库信息 (A1-A6) + trajectory snapshot (B1-B7) + 上下文 (C1-C3)
       → 输出 JSON：
            {
              "triggered": true | false,
              "reason_if_not_triggered": "...",
              "primary_dimension": "M1" | null,
              "secondary_dimensions": ["M6", "M7"] | [],
              "intervention_text": "已合成的主+次 prompt 文本，直接注入",
              "brief_reasoning": "为什么这么判，便于审计"
            }
        ↓
中间件 Python 层: 把 intervention_text 包成 HumanMessage / user-role message
                  → 追加到 agent 的对话历史末尾（state["researcher_messages"] / aiq stage 输入头部 / Claude Code stdin）
```

**v4 vs v3 关键差异**：
- v3 是 L1 分类、L2 缺陷检测、L3 干预生成**三次独立 LLM 调用**
- v4 把 L2+L3 合并为**一次调用**——opus-4.7 直接判命中维度 + 排序 + 写干预文本
- 不再用"打分 + 阈值"机制；opus-4.7 自主判断是否触发、主/次维度顺序、是否复合
- 详见原则 7

### LLM 选型说明（v4 决定）

| 组件 | v3 选型 | v4 选型 | 理由 |
|---|---|---|---|
| L1 intent 分类 | qwen 自身 | **claude-opus-4-7** (shubiaobiao API) | 元判断需要更强模型；qwen 对 19 类意图分类 + 元认知匹配的准确率不如 opus-4.7 |
| R-T 利用率提取 | qwen 自身 / 启发式 | **纯代码** | 这是结构遍历问题（"agent round N+1 是否引用了 round N 的工具结果"），不需要 LLM |
| L2+L3 合并 | qwen 自身（两次调用） | **claude-opus-4-7** (shubiaobiao API，一次调用) | 元认知判断 + 反思问句生成都需要严格遵守原则 4 的 8 条守则 |

**注意**：被中间件 prompt 化的 agent 本身（thinkdepthai/aiq/claudecode-qwen3.5-plus）保持原模型不变；只有中间件内部的 L1/L2+L3 用 opus-4.7。这避免了"用 opus-4.7 修 qwen 的失败"被等同于"opus-4.7 直接答题"的指控——agent 看到的只是中文反思问句，没有任何答案信息。

**API 配置**：环境变量 `MIDDLEWARE_LLM_API_KEY` + `MIDDLEWARE_LLM_BASE_URL=https://api.shubiaobiao.cn/v1` + `MIDDLEWARE_LLM_MODEL=claude-opus-4-7`。

### 两个独立的上下文流（v4 必须明确区分）

| 上下文流 | 谁负责维护 | 是否连续 | 作用 |
|---|---|---|---|
| **agent (qwen) 的推理上下文** | LangGraph `state["researcher_messages"]` (thinkdepthai) / aiq stage 内 message / Claude Code CLI 内部历史 | ✅ **完全连续，0 丢失** | agent 每次推理时看完整对话历史 + 中间件追加的 HumanMessage |
| **opus-4.7 (中间件 LLM) 的调用上下文** | **每次独立调用，无状态** | ✗ 无状态 | 每次 check point 时由 Python 层从 state 现读 trajectory snapshot 给 opus-4.7 |

**关键事实**：
- **agent 的推理不会因中间件介入而断开**——中间件只是在 agent 对话历史末尾追加一条 HumanMessage（包含 intervention_text）。下一轮 agent 看到的是 round 1 .. 当前 round 全部累积上下文 + 那条新追加的 message。
- **opus-4.7 是无状态的**——每次 check point（中期 / 结论前）都是独立 LLM call。两次 check point 之间通过 Python 层维护的 per-case 状态对象 + C2 字段实现"避免重复同维度"等连续性约束。

#### 跨 check point 状态：Python 层维护，通过 C2 字段传递

```python
class CaseInterventionState:
    mid_check_triggered: bool             # 中期是否触发过
    mid_check_primary: str | None         # 中期触发的主问维度（比如 "M1"）
    mid_check_secondary: list[str]        # 中期触发的次问维度
    mid_check_intervention_text: str      # 中期注入的完整 prompt 原文
    mid_check_round: int                  # 触发时的 round 号
    # (结论前 check 时 agent 已收到过 mid_check_intervention_text 的响应，
    #  agent 的响应会出现在 B2 reasoning 文本里)
```

结论前 check point 调用 opus-4.7 时，C2 字段填这个状态：

```json
"C2_prior_intervention_history": {
    "mid_check": {
        "primary": "M1",
        "secondary": ["M6"],
        "intervention_text": "你最近几轮一直在按错误数排名...",
        "round": 22
    }
}
```

opus-4.7 看到 C2 后能做：
1. **避免重复触发同维度**（v4 原则 5：同维度全程 1 次）—— 看到 "M1 已主问过" → 结论前不再选 M1 作主问
2. **判断前次干预是否生效**——看 B2 reasoning 里 agent 在 round 22 之后有无响应那段 intervention；如果没响应（agent 继续打转），可以更强力度提另一个维度
3. **避免"多次干预累积过重"**——看到之前已注入 intervention，结论前干预可以写得更 terse

**LLM 选型说明**（v4 决定）：

| 组件 | v3 选型 | v4 选型 | 理由 |
|---|---|---|---|
| L1 intent 分类 | qwen 自身 | **claude-opus-4-7** (shubiaobiao API) | 元判断需要更强模型；qwen 对 19 类意图分类 + 元认知匹配的准确率不如 opus-4.7 |
| R-T 利用率提取 | qwen 自身 / 启发式 | **纯代码** | 这是结构遍历问题（"agent round N+1 是否引用了 round N 的工具结果"），不需要 LLM |
| L2 缺陷检测 | qwen 自身 | **claude-opus-4-7** (shubiaobiao API) | 元认知判断的核心，准确率直接决定 trigger precision |
| L3 干预生成 | qwen 自身 | **claude-opus-4-7** (shubiaobiao API) | 反思问句生成需要严格遵守原则 4 的 8 条守则，opus-4.7 更稳 |

**注意**：被中间件 prompt 化的 agent 本身（thinkdepthai/aiq/claudecode-qwen3.5-plus）保持原模型不变；只有中间件内部的 L1/L2/L3 用 opus-4.7。这避免了"用 opus-4.7 修 qwen 的失败"被等同于"opus-4.7 直接答题"的指控——agent 看到的只是中文反思问句，没有任何答案信息。

**API 配置**：环境变量 `MIDDLEWARE_LLM_API_KEY` + `MIDDLEWARE_LLM_BASE_URL=https://api.shubiaobiao.cn/v1` + `MIDDLEWARE_LLM_MODEL=claude-opus-4-7`。

---

## 原则 6 — 中期检查点的校准方法

### 问题

v3 的中期检查点 [37, 44] 是从 success case 的 query count 分位选的精确率拐点，但 105 failed case 中 42% 在 query 37 之前已经 conclusion。这意味着**单一固定 query count** 不能同时覆盖"过早收敛"和"长跑跑偏"两种失败。

### v4 的中期检查点设计候选

实施时三选一并标明依据：

- **候选 A — 早期固定点**：把中期检查放在该 framework failed case 的 query count P25 处（覆盖早收敛长尾）。
  - 优点：实现简单，能覆盖早期收敛 case
  - 代价：对长跑型 case 来说时机偏早，agent 还没充分探查就被打断

- **候选 B — 动态触发**：监听 reasoning 文本中"I have sufficient evidence" / "the root cause is" 类近收敛信号，触发即检查（无固定 round 限制）。
  - 优点：适配不同长度轨迹
  - 代价：实现成本高，需要 reasoning 文本特征工程，可能在某些 case 误伤

- **候选 C — 回退结论检查**：取消独立中期检查，把整个干预预算合并到结论前（即 0 次中期 + 1 次结论）。
  - 优点：轨迹最短，干预最轻
  - 代价：失去对长跑跑偏 case 的中期纠偏能力

### Plan 阶段不锁死

A/B/C 三个候选都在 plan 中列出，最终选哪个 + 该 framework 的具体阈值留到 D-5 / D-6 / D-7 实施阶段——届时各 framework 重新统计 failed case 的 query/round count 分布后再定。**也可能不同 framework 选不同策略**（例如 thinkdepthai 选 A，aiq 用 stage 边界策略，claudecode 选 B 或 C）。

---

## 原则 7 — 维度按 check point 分配（主用/备用 → 提示词权重）

不是所有维度都适合在所有时机评估。本原则规定哪些维度在中期检查 vs 结论前检查时**主用**评估，哪些**备用**评估。

**v4 不用打分阈值机制**——而是把"主用 / 备用"作为给 opus-4.7 的提示词权重（在 L2+L3 合并 prompt 中明确告诉 LLM 该 check point 应优先评哪些维度），由 LLM 自主判断是否触发、主次顺序、是否复合。

### 分配的判定逻辑

| 维度类型 | 何时最有效 | 原因 |
|---|---|---|
| **行为遗漏型**（PD-pure：M6 / M7） | **中期主用**（结论前补救） | 越早提醒补做某类动作越好；结论前发现就 too late，agent 没时间补查 |
| **R 层反思型**（M1 / M2 / M5 / M8） | **结论前主用**（中期备用） | 反思 commit 前的认知偏差；agent 已有候选时反思才有意义 |
| **图结构自检型**（M3 / M4） | **结论前**（必须 graph 已成型） | graph 没生成前没法检查内部一致性 |
| **行为模式型**（M9 / M10） | M9 中期主用；M10 结论前主用 | M9 检测到打转立即介入；M10 trigger 含 about_to_commit |
| **多 stage 反射型**（aiq A2 / A3 / A5） | **结论前主用** | 必须 cross-stage 数据 / compress 输出已累积 |
| **stage 边界型**（aiq A1） | **stage_0 末尾的中期检查主用** | aiq 特有：stage_0 没 commit 是 stage 边界事件 |

### 主用 vs 备用：opus-4.7 prompt 中的权重提示

L2+L3 合并 prompt 给 opus-4.7 时，按 check point 分类列出维度池：

```
[本 check point 评估的维度池]

=== 主用维度（优先评估）===
M6 (Baseline-Contrast Reflex): {卡片关键段}
M7 (Layer-Coverage Reflex): {卡片关键段}
M9 (Investigation Stagnation): {卡片关键段}

=== 备用维度（需更明确证据才上位）===
M1 (Loudness-Anchor Self-check): {卡片关键段}
M2 (Chronic-Noise Skepticism): {卡片关键段}
M5 (Silence ≠ Health): {卡片关键段}
M10 (Premature Commitment): {卡片关键段}

=== 判断指引 ===
1. 默认聚焦"主用维度"是否命中。
2. "备用维度"在该 check point 时机上不太合适，需要 trajectory 中证据非常明确才考虑触发。
3. 如果某"备用维度"的命中证据明显强于所有"主用维度"，可以让备用维度作主问。
4. 任何维度未命中（证据不足）→ triggered=false。
5. 主问最多 1 个；次问 0~3 个；不强行复合。
```

这样既不会因为时机不适合就完全屏蔽某维度（例如 M2 在中期被 agent 锚定明显时仍可主问），又能保证默认情况下每个 check point 聚焦于其主用维度池。**判断完全由 opus-4.7 自主**——v4 不预设硬数字阈值。

### 中期检查的 L2 评估池（按 framework）

| Framework | 中期检查时 L2 评估的**主用**维度 | **备用** |
|---|---|---|
| thinkdepthai (qwen + sonnet) | M6, M7, M9 | M1, M2, M5, M10 |
| aiq (qwen) | M6, M7, M9, **A1** | M1, M2, M5, M10, A4 |
| claudecode (qwen) | M6, M7, M9, **C2** | M1, M2, M5, M10 |

### 结论前检查的 L2 评估池（按 framework）

| Framework | 结论前检查时 L2 评估的**主用**维度 | **备用** |
|---|---|---|
| thinkdepthai (qwen + sonnet) | M1, M2, M3, M4, M5, M8, M10 | M6, M7, M9 |
| aiq (qwen) | M1, M2, M5, M8, M10, **A2, A3, A4, A5** | M3 (待 D-6 确认 aiq 输出结构), M4, M6, M7 |
| claudecode (qwen) | M1, M2, M3, M4, M5, M8, M10 | M6, M7, **C2** (补救), M9 |

### 完整分配矩阵

| 维度 | 中期 | 结论前 | 备注 |
|------|:---:|:---:|---|
| M1 Loudness-Anchor | △ 备用 | ✅ 主用 | M1 trigger 含 about_to_commit |
| M2 Chronic-Noise Skepticism | △ 备用 | ✅ 主用 | 同 M1 |
| M3 Output-Graph Consistency | ✓ 主用（reasoning 文本） | ✅ 主用（reasoning + aiq 时 graph） | M3 D-3 修订：trigger 改为 reasoning 文本断言，所有 framework 通用 |
| M4 Sibling-Disambiguation | △ 备用 | ✅ 主用 | candidate 已倾向时才能查相似度 |
| M5 Silence ≠ Health | ✅ 可用 | ✅ 可用 | reasoning 中健康推断时即触发 |
| M6 Baseline-Contrast Reflex | ✅ **主用** | △ 补救 | 越早提醒越好 |
| M7 Layer-Coverage Reflex | ✅ **主用** | △ 补救 | 同 M6 |
| M8 Hypothesis-Counterfactual | ✗ | ✅ 主用 | candidate 已 draft 才能查 isolation 历史 |
| M9 Investigation Stagnation | ✅ **主用** | △ 补救 | 中期检测到打转立即介入 |
| M10 Premature Commitment | △ 仅 P25 满足时 | ✅ **主用** | trigger 含 about_to_commit |
| **A1** (aiq) Stage-Commitment | ✅ **主用**（stage_0 末尾） | ✗ | aiq 特有：stage 边界事件 |
| **A2** (aiq) Refinement-Without-New-Probe | ✗ | ✅ 主用 | 跨 stage 切换数据要等 stage_2 后 |
| **A3** (aiq) Compress-Drift | ✗ | ✅ 主用 | 必须 compress 已运行 |
| **A4** (aiq) Hub-Fabrication | △ 备用 | ✅ 主用 | 候选 draft 后才知道是否 hub |
| **A5** (aiq) Anti-Flipflop | ✗ | ✅ 主用 | 必须 cross-stage 数据已累积 |
| **C2** (claudecode) Layer-Coverage 变体 | ✅ 主用 | △ 补救 | 同 M7 |

**legend**：✅ 主用（opus-4.7 优先评估）；△ 备用（需更明确证据）；✗ 不评估

### 与原则 4 「1 主问 + 0~3 次问」的协同

opus-4.7 在某 check point 评估全维度池后，按原则 4 输出：
- **主问** = LLM 自主选定的 most_critical 维度（必须 triggered=true 才有；可以是主用也可以是备用）
- **次问** = LLM 自主选定的 0~3 个相关命中维度（不强行凑数，仅在 LLM 真的认为该维度有命中时加）
- **不触发** = LLM 判断没有任何维度命中达到干预的程度，输出 triggered=false

例：thinkdepthai 中期检查时，opus-4.7 看到 trajectory 后判断：
- M6 命中（baseline 缺失 + abnormal-only 多）
- M7 命中（运行时层 intent = 0）
- M1 命中得**比 M6/M7 都明显**（agent 即将 commit ranking top + reasoning 中表达"I'm leaning toward X"）
- M9 / M2 没明显证据

→ opus-4.7 输出 `{primary: "M1", secondary: ["M6", "M7"]}`——M1 虽然在中期是"备用"，但由于命中证据非常明显，opus-4.7 自主决定让它作主问。这种灵活性避免了硬阈值机制把真正关键的维度屏蔽掉。

---

## opus-4.7 调用接口设计（v4 标准）

### 输入信息清单（按 check point 区分）

opus-4.7 的 system prompt 由中间件 Python 层组装，包含三类信息：

#### Category A — 维度库信息（任何 check point 都给）

| ID | 信息 | 说明 |
|----|-----|----|
| A1 | 当前 check point 类型（中期 / 结论前） | 必须 |
| A2 | 该 check point × framework 的**主用维度池** | 见原则 7 完整分配矩阵 |
| A3 | 该 check point × framework 的**备用维度池** | 同 A2 |
| A4 | 候选维度的**关键段**（来源 mapping + Cognitive vocabulary + Trigger abstract 描述） | 不给完整卡片以节省 token |
| A5 | 维度间冲突规则（互斥 / 优先级，如 M1 优先于 M8、M9 vs M10 互斥） | 让 LLM 做主次排序时有依据 |
| A6 | v4 原则 4 干预守则（不能告答案、不能命 SQL、不用方向词 等 8 条） | L2+L3 合并一次调用，必须给 |

#### Category B — agent trajectory snapshot

中期 check point 时给：

| ID | 信息 | 说明 |
|----|-----|----|
| B1 | 完整 intent log（round, intent_type, target_service） | 核心信号 |
| B2 | reasoning 文本：**最近 5 round 原文** + **更早的摘要**（1-2 段） | 摘要由 L1 阶段代码预处理产出 |
| B4 | WHERE filter 历史（所有 service_name filter 的集合） | M8 / M4 必须 |
| B5 | Observed services（所有曾在 SQL 结果 / reasoning 中出现过的 service_name 集合） | M4 / A4 必须 |
| B6 | Round count + tool call count + 已触发 intent 类别统计 | M6 / M7 / M10 必须 |
| B7 | 最近 3 次 ranking 类 SQL 的 top-3 服务名 | M1 必须 |

结论前 check point 时**额外给**（仅 aiq）：

| ID | 信息 | 说明 |
|----|-----|----|
| B3 | **完整 draft graph**：nodes + state 标记 + root_causes 列表 | **仅 aiq 在 conclusion 时拿得到结构化 graph**（reflect_on_graph 内部已调过 compress_to_graph，state["causal_graph"] 已成型）；thinkdepthai/claudecode 在 conclusion (compress 之前) 时**没有结构化 graph**——M3 已 D-3 修订为基于 reasoning 文本检测，不需 B3 |

#### Category C — 上下文信息

| ID | 信息 | 说明 |
|----|-----|----|
| C1 | framework 名（thinkdepthai-qwen / aiq / claudecode）| 让 LLM 知道哪些 framework-specific 维度适用 |
| C2 | **本 case 之前的干预历史**（per-case 状态对象，详见原则 5 末尾的 CaseInterventionState）| 避免重复同盲点 + 判断前次干预是否生效 |
| C3 | framework 行为先验（failed case query count P25 等）| M10 必须 |

### 输出 JSON schema (v4 标准)

```json
{
  "triggered": true | false,
  "reason_if_not_triggered": "...",
  "primary_dimension": "M1" | null,
  "secondary_dimensions": ["M6", "M7"],
  "intervention_text": "...",
  "brief_reasoning": "..."
}
```

各字段：
- `triggered`：opus-4.7 自主判断该 check point 是否需要发出干预
- `reason_if_not_triggered`：若 false，说明为什么（"agent 已查 baseline 无 stagnation 模式无近 commit 信号"等）；便于离线审计
- `primary_dimension`：主问维度 ID（M1..M10 / A1..A5 / C2 之一）；triggered=false 时为 null
- `secondary_dimensions`：次问维度 ID 列表；可为空 `[]`
- `intervention_text`：已合成的主+次完整 prompt 文本，**直接拿来注入到 agent 输入**，无需后续二次加工
- `brief_reasoning`：opus-4.7 简短说明为什么这么判，1-3 句话；用于 Phase 8 离线审计

---

## 原则审核清单（用户审核 D-0 时打勾）

每条原则审核完成后打勾。如某条原则被否，需修订后重新审核。

- [ ] **原则 1**：元认知 vs 低层操作的对照足够清晰
- [ ] **原则 2**：允许/禁止信号清单覆盖完整且准确
- [ ] **原则 3**：D/R/PD 三层提炼路径清晰，例子说明力够强
- [ ] **原则 4**：干预守则的 "不能/应当" 列表没有遗漏，反例参照足够直接
- [ ] **原则 5**：层 vs 次区分明确，1+1 的合理性论证足够；两个上下文流（agent vs opus-4.7）区分明确；跨 check point 状态机制清楚
- [ ] **原则 6**：中期检查点 A/B/C 候选完整，"plan 阶段不锁死"的逻辑清楚
- [ ] **原则 7**：维度的中期/结论前分配合理；不用打分阈值改为 opus-4.7 自主判断的灵活性可接受
- [ ] **opus-4.7 调用接口**：信息清单 (A/B/C 三类) 完整；JSON schema 满足下游 L3 使用

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-0 阶段输出） |
| revision 2026-04-22 (D-3) | 2026-04-22 | 原则 5：增加"两个独立上下文流"说明 + opus-4.7 无状态调用机制 + 跨 check point 状态对象 (CaseInterventionState)；L2/L3 合并为单次 LLM 调用。原则 7：去掉打分阈值机制，改为 opus-4.7 自主判断；新增"opus-4.7 调用接口设计"节（信息清单 A/B/C 三类 + JSON schema 输出格式）。M3 卡片 trigger 改为 reasoning 文本断言（不依赖结构化 graph，所有 framework 通用；aiq 时可同时启用 graph orphans 检测）。 |
