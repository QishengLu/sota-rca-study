# D/R 轴签方法论 — failure_analysis_plan Phase 6.5

> **修订（2026-04-21）**：早期版本错误地把 D 写成 `fault_subtype → D` 查表、R 写成 `T → R` 函数。这等于把 D 退化成"故障分类"、R 退化成"theme 的同义词"，无法解释"同一 fault_type 下 agent 有时做对有时做错"的事实，也无法为中间件提供 per-case 的精确触发信号。此文档现版是 **per-case 归纳**方法论。

## 核心原则

**每个失败 case 都是因为两个相对独立的原因失败：**

1. **D (Dataset 难点)**：这个 case 的**数据**上有什么特征把 agent 难住了？
   —— 不是"JVMMemoryStress"；**是**"silent upstream + loud downstream 造成反向追溯困难"。
2. **R (Reasoning 能力缺陷)**：agent 在这个 case 的**轨迹**里展现了什么推理习惯导致错？
   —— 不是"T3 Noise-Anchor 主题"；**是**"看到 RabbitMQ 错误立即锚定，没做时间对齐"。

**D 和 R 都必须从每个 case 的 dossier 读出来再归纳，不可以从 fault_type 或 theme 反推。**

**跨 agent 独立归纳：** 4 个 agent 各自做自己的 D 分类和 R 分类，不共用 rubric；Phase 7.5 merge 时才 pairwise 比对。

---

## 为什么查表/映射方法不行

**反例（用户举的）：** 同一个 agent × 同一个 fault_type，有时做对有时做错。如果 D 只是 fault_type 查表，那 D 就不是"失败原因"，只是"故障分类"。设计出来的中间件如果按 D 触发，会命中本来做对的 case，造成 regression。

**实际需要：** D 必须揭示"这个 case 里 *具体什么* 把 agent 难住了"，这个"具体什么"在 correct case 里就没有或 agent 绕过了。只有这样，基于 D 设计的中间件才不会误伤 correct case。

同理 R：不能直接说"这个 case 是 T3（Noise-Anchor 主题），所以 R=R3"。如果两个 T3 case 的轨迹表现不同（一个是"看到 RabbitMQ 就锚定"，另一个是"基线 CPU 高就锚定"），它们的 R 应该分别归纳，可能落在不同 R 类或者同 R 类但 trigger signature 不同。

---

## 方法流程（per-agent 独立执行）

### Phase 1：Per-case D-phrase 和 R-phrase

对该 agent 的每个 failed case：

**素材来源：** 已有的 `v1/per_case_analysis.md`（或 v2 for thinkdepthai-qwen），它的三段式里：
- §(1) What really happened —— 提炼 D-phrase 的来源（GT / telemetry 上真实发生的事）
- §(2) What agent did —— 提炼 R-phrase 的来源（agent 轨迹展现的推理模式）
- §(3) Divergence + proximate cause —— D 与 R 的 convergence 点

**写 D-phrase（<20 词）：** 这个 case 的**数据**难在哪。Grounded 在可观测痕迹：specific span、specific metric z-score、specific log 线索、missing data 等。

> 举例：
> - "silent upstream (ts-X: 0 spans) with loud downstream (ts-Y: 'Connection refused' ×50)"
> - "RabbitMQ DNS AmqpConnectException pre-existing in both normal and abnormal periods, count nearly identical"
> - "service-level avg latency normal but trip SELECT span duration 100× normal, buried in 95% of other span types"

**写 R-phrase（<20 词）：** agent 的**推理**哪里错了。Grounded 在特定轮的 think_tool 文本或 SQL：

> 举例：
> - "blamed error-emitting downstream (ts-Y) without checking if it's a messenger of upstream failure"
> - "anchored on RabbitMQ DNS at round 4, never re-evaluated despite conclusion.csv showing no correlation"
> - "queried aggregated metric across all services with one ORDER BY duration, ignoring per-span-type breakdown"

### Phase 2：Per-agent 独立聚类

把该 agent 所有 case 的 D-phrase 聚类成 D 类别（D1, D2, ...）；R-phrase 聚类成 R 类别（R1, R2, ...）。**不参考其他 agent 的 D/R 类别**（sealing rule 延续 plan §7.3）。

每个 D/R 类别写：
- **Name**：短标签（≤6 词）
- **Definition**：一句话描述该类的本质特征
- **Positive criteria**：哪些 D-phrase / R-phrase 应该归入此类
- **Negative criteria**：看起来像但不应归入的情况
- **Middleware trigger（仅 R）**：轨迹中能检测此 R 的 pattern（只读 agent 的 think_tool / tool_call，不依赖 GT）
- **Cases**：该类下的 case_idx 清单

产出两份文档：
- `<agent_workspace>/dr_d_categories.md`
- `<agent_workspace>/dr_r_categories.md`

### Phase 3：Per-case 双标签写回

每个 case 得到 `(D_i, R_i)` 两个独立标签，写到 DB 的 `meta.failure_analysis.v1.D` 和 `meta.failure_analysis.v1.R`（D_i / R_i 的值是 per-agent 的 D/R 类别名，例如 aiq 的 `D1_silent_upstream`、claudecode 的 `R2_blame_loudest_caller`）。

### Phase 4：Per-agent D × R 交叉表

```markdown
## <agent> D × R Cross-tabulation

|       | R1  | R2  | R3  | ...  | Total |
|-------|-----|-----|-----|------|-------|
| D1    | 14  | 25  |  7  | ...  |   55  |
| D2    |  2  |  1  | 12  | ...  |   24  |
| ...
```

产出 `<agent_workspace>/dr_cross_tab.md`。

---

## 约束与避坑

1. **Per-case inductive，不用 rubric**：thinkdepthai-qwen v2 里存在的 `D1-D5` 和 `R1-R7` 分类是老方法论的遗留，**不作为起始 rubric 给其他 agent 参考**。其他 3 个 agent 从零开始独立归纳；thinkdepthai-qwen 的 D/R 也在 Phase 6.5 **重新做一次 per-case 归纳**（可能最终类别相同或类似，但推导过程独立）。
2. **D 和 R 在逻辑上正交**：D 讲"数据挑战"，R 讲"推理缺陷"。一个 case 的 D_i 和 R_i 不应该互相推导（如果完全推导，说明其中之一是冗余的）。
3. **Middleware trigger 只用 R**：D 依赖 GT-side 信息（正常 vs 异常基线、conclusion.csv 等），**运行时不可用**。D 是分析维度，R 是中间件依据。
4. **"新分类 vs 沿用"门槛**：如果该 agent 出现的模式在 per-case 独立归纳时和历史其他 agent 类别本质相同，归入时可以起一个形近名字，但**Phase 7.5 merge 时再正式对齐**，不在 Phase 6.5 期间偷跑 cross-agent 对比。
5. **Phase 7.5 merge 的产物**：从 4 个 per-agent 的 D 集合和 R 集合 pairwise 比对 → 统一 D 集合、统一 R 集合、universal D/R 子集。不要求 4 agent 的 D/R 完全一致。
