# thinkdepthai-qwen3.5-plus v2 — workspace README

Part I of `failure_analysis_plan.md` 的首个 per-agent 失败分析工作区。版本为 v2（v1 是更早的探索分析，已移至 [`../../../../exploration/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/`](../../../../exploration/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/)，不再引用）。

## 基本信息

- **Agent**: thinkdepthai (Deep_Research, LangGraph 单 agent ReAct loop)
- **Model**: qwen3.5-plus
- **Total samples (judged)**: 500
- **Failed cases (correct=false)**: 105（AC@1 = 79.0%）
- **Dossier builder**: `RCAgentEval/scripts/failure_analysis/build_dossiers.py`（主脚本；thinkdepthai 的拓扑就是主脚本默认处理的 case，不需要独立 adapter）

## 文件清单

| 文件 | Phase | 含义 |
|---|---|---|
| `dossiers/case_<idx>.md` (+ `.raw.json`) | 1 | 105 个 failed case 的 GT-side + agent-side dossier |
| `sample_batch_1.md` | 2 | 15-case stratified batch 的抽样清单（Phase 2 专属） |
| `budget_log.md` | 2+4 | 每 case 的 token/wall-time 成本记录（Phase 2 instrumentation） |
| `per_case_analysis.md` | 2+4 | 全部 105 case 的三段式分析（What really happened / What agent did / Divergence） |
| `taxonomy.md` | 3 (frozen) | T1-T9 themes + D1-D5 data challenges + R1-R7 reasoning defects + T→R mapping + D×R 交叉表 |
| `labels.jsonl` | 4 | 105 行原始 schema：`{case, label, D, R, pivot_round, proximate_cause, fault_type, gt_services, predicted}` |
| `labels_R.jsonl` | 4 | R-only 的 label 导出（便于快速按 R 维度查询） |
| `labels_aligned.jsonl` | 4b | 🆕 Phase 4b 产物：对齐 `primary/secondary/pivot_round/proximate_cause/evidence/labeler` —— **R 和 D 字段从 labels.jsonl 丢弃**（原 R/D 是 T→R 映射 + fault_subtype 查表推出来的，不是 per-case 归纳，不能复用。Phase 6.5.a 重新做 per-case D/R） |
| `labels.jsonl.pre_4b_backup` | 4b | 🆕 Phase 4b 备份：保留 Phase 4 的原始 labels.jsonl（含老的 label/R/D）仅作为 audit trail |
| `write_labels_to_db.py` | 4 / 4b | 写 DB meta.failure_analysis.v1.* 脚本 |
| `spot_check.md` | 5 | 🆕 Phase 5 user 抽查 20 cases 的 Correct/Wrong/Ambiguous 标记 |
| `validation.md` | 5 | 🆕 Phase 5 三项检查（spot check ≥85%、exhaustiveness ≤10%、χ² orthogonality） |
| `behavior_failure_join.{md,json}` | 6 | 🆕 6 张行为-失败交叉表 + 统计测试 + 负结果小节 |
| `dr_d_categories.md` | 6.5.a | 🆕 **Per-case 独立归纳**的 D 类别（不复用 taxonomy.md 的老 D1-D5，完全重做） |
| `dr_r_categories.md` | 6.5.a | 🆕 **Per-case 独立归纳**的 R 类别 + middleware trigger（不复用 taxonomy.md 的老 R1-R7，完全重做） |
| `dr_labels.jsonl` | 6.5.a | 🆕 每 case 的 (D_phrase, D_category, R_phrase, R_category) |
| `dr_cross_tab.md` | 6.5.a | 🆕 D × R 交叉表（基于新归纳的 per-agent 类别） |

🆕 = 待产出。

## Phase 0 索引

Root 层 [`../failed_cases.jsonl`](../failed_cases.jsonl)（105 行）是 Phase 0 从 DB 导出的 failed_case 索引，每行含 `dataset_index` + `fault_category` / `fault_type` / `spl` / `n_svc` / `n_edge` / `root_cause_service`。

## 方法论

- 通用 D/R 方法论：[`../../../../1-methodology/DR_axis_labeling.md`](../../../../1-methodology/DR_axis_labeling.md)
- 计划源：[`../../../../../failure_analysis_plan.md`](../../../../../failure_analysis_plan.md)

## 当前状态

- Phase 1-4 ✅ 完成（2026-04-16）
- Phase 4b ⬜ pending（schema 对齐）
- Phase 5 ⬜ pending（user spot check 尚未进行）
- Phase 6 ⬜ pending（behavior_failure_join 待运行）
- Phase 6.5 ⬜ pending（D/R 轴签 formalization）
