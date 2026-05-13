# cross-agent/ — Phase 6.5 跨 agent 对比（pre-merge）

**前置**：4 个 agent 的 Phase 5 validation.md 签收 + Phase 6 behavior_failure_join.{md,json} 产出 + **Phase 6.5.a 的 per-agent D/R categories 完成**。

**目的**：在 Phase 7.5 合并成 unified R 之前，先做一轮 side-by-side 对比，保留各 agent 的 native 分类命名，找出：
- 跨 agent 重现的模式（→ universal D / R 候选）
- 单 agent 独有的模式（→ framework-specific，Phase 7.5 merge 时单独保留）
- 跨模型鲁棒性（thinkdepthai qwen vs sonnet4.6）

**Phase 6.5 拆成两个子阶段：**

- **6.5.a（per-agent 独立 D/R 归纳）**：4 个 agent 各自独立做 per-case D-phrase / R-phrase + 聚类 + DB 写入。产物放各自 workspace，见 [`../2-by-framework/README.md`](../2-by-framework/README.md)。方法论见 [`../../1-methodology/DR_axis_labeling.md`](../../1-methodology/DR_axis_labeling.md)。
- **6.5.b（跨 agent 对比，本目录）**：在 4 个 agent 的 6.5.a 完成后，生成 5 份对比产物。

## 本目录的 5 份产物（6.5.b）

| 文件 | 内容 |
|---|---|
| `side_by_side_tables.md` | 6 张 Phase 6 交叉表 × 4 agent 的 4-panel 并排呈现（各 agent 用自己的 theme 命名） |
| `framework_invariants.md` | 至少在 3/4 agent 中重现的信号清单 — universal R 候选 |
| `framework_specificity.md` | 只在 1-2 agent 出现的信号 — framework-specific appendix 候选 |
| `model_robustness.md` | thinkdepthai qwen vs sonnet-4.6 跨模型对比 — model-robust R set 候选 |
| `cross_agent_dr_comparison.md` | 4 agent 的 per-agent D 集合和 R 集合并排（不 merge，留给 Phase 7.5） |

**产出脚本**：`RCAgentEval/scripts/failure_analysis/cross_agent_compare.py`（输入：4 个 `behavior_failure_join.json` + 4 组 `dr_{d,r}_categories.md`；输出：上述 5 份 markdown）。

**Gate to exit 6.5**：用户签收 5 份产物 + 所有 agent 的 per-agent D/R categories，并确认 `framework_invariants.md` 中的 universal 信号足够说服人进入 Phase 7.5 merge。
