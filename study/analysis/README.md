# analysis/ — Plan-scoped analysis artifacts

本目录只保留 [`failure_analysis_plan.md`](../failure_analysis_plan.md) 定义的产物。历史探索产物（151cases/270cases、cross-model diff、老 middleware、Phase 10 以前的 reports 等）已移到 [`../exploration/`](../exploration/)。

## 目录概览

```
analysis/
├── 1-methodology/                 # 通用方法论参考（意图分类、SQL patterns、D/R 轴签等）
├── 2-trajectories/                # [壳] 按需保留的 trajectory 观察（plan 目前不产出于此）
├── 3-failure-modes/               # failure_analysis_plan 的主要工作区
│   ├── 2-by-framework/            # Phase 1-6 / 7.1-7.4：每个 agent 独立工作区
│   │   ├── thinkdepthai-qwen3.5-plus/v2/
│   │   ├── thinkdepthai-claude-sonnet-4.6/v1/
│   │   ├── aiq-qwen3.5-plus/v1/
│   │   └── claudecode-qwen3.5-plus/v1/
│   ├── cross-agent/               # Phase 6.5：跨 agent 并排对比 + lightweight axis labels
│   ├── merged/                    # Phase 7.5：跨框架合并 → unified R
│   └── middleware_A/              # Phase 8-10：middleware 设计 + 验证 + 最终报告
├── 4-middleware/                  # [壳] 老 middleware 已移走；plan 的 middleware 输出在 3-failure-modes/middleware_A/
├── 5-reports/                     # [壳] plan 的最终报告是 part2_narrative.md 等（位于 middleware_A/）
└── 6-planning/                    # [壳] 计划文档统一在仓库根 `failure_analysis_plan.md`
```

## 按 Phase 快速跳转

| Phase | 产物位置 | 状态 |
|---|---|---|
| Phase 1 Dossier builder | `3-failure-modes/2-by-framework/<agent>/<v>/dossiers/case_<idx>.md` | ✅ 4 agent 都做完 |
| Phase 2 Batch 1 sample | `3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/sample_batch_1.md` | ✅ |
| Phase 3 Taxonomy 冻结 | `3-failure-modes/2-by-framework/<agent>/<v>/taxonomy.md` | ✅ 4 agent 都冻结 |
| Phase 4 Tail labeling + DB | `3-failure-modes/2-by-framework/<agent>/<v>/labels.jsonl` + DB `meta.failure_analysis.v1.*` | ✅ |
| **Phase 4b** thinkdepthai-qwen schema 对齐 | `3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/labels_aligned.jsonl` | ✅ 2026-04-21 |
| **Phase 5** Per-agent validation | `3-failure-modes/2-by-framework/<agent>/<v>/{spot_check,validation}.md` | ⬜ 4 agent 各一份 |
| **Phase 6 prereq** Per-case transitions parquet (5 agent 含 taskweaver) | `3-failure-modes/_cache/transitions_per_case.parquet` | ⬜ 一次性 ~10 min |
| **Phase 6** Per-agent behavior × primary join | `3-failure-modes/2-by-framework/<agent>/<v>/behavior_failure_join.{md,json}` | ⬜ 4 agent 各一份 |
| **Phase 6.5.a** Per-agent 独立 D/R 归纳 | per-agent `{dr_d_categories,dr_r_categories,dr_labels.jsonl,dr_cross_tab}.md` | ⬜ |
| **Phase 6.5.b** Cross-agent 对比 | `3-failure-modes/cross-agent/` 5 份产物 | ⬜ |
| **Phase 6.6** Per-agent behavior × R re-join | `3-failure-modes/2-by-framework/<agent>/<v>/behavior_R_join.{md,json}` | ⬜ 4 agent 各一份 |
| **Phase 7.5** Cross-framework merge → unified R | `3-failure-modes/merged/{theme_grid, unified_R, labels_unified, distributions}.md` | ⬜ |
| **Phase 7.5.c** Cross-framework behavior × unified_R join | `3-failure-modes/merged/behavior_unified_R_join.{md,json}` | ⬜ |
| Phase 7.6 Unified R DB 写入 | DB `meta.failure_analysis.v1.{unified_R, D}` | ⬜ |
| Phase 8 Middleware 规则 + dry-run（rule `origin_row` 引 7.5.c 显著 cell）| `3-failure-modes/middleware_A/rules/` + `middleware_A/dry_run/` | ⬜ |
| Phase 9 A/B validation | `3-failure-modes/middleware_A/regression_set_*.jsonl` + DB new exp_ids | ⬜ |
| Phase 10 最终报告 | `3-failure-modes/middleware_A/part2_{universal_R,middleware_rules,validation,narrative}.md` | ⬜ |

## Methodology 参考

所有方法论文档集中在 [`1-methodology/`](1-methodology/)：

- [intention_category.md](1-methodology/intention_category.md) — 19 类意图分类（SQL 级）
- [sql_patterns.md](1-methodology/sql_patterns.md) — SQL fingerprint + pattern 归纳
- [context_analysis.md](1-methodology/context_analysis.md) — trajectory context 抽取规则
- [parquet.md](1-methodology/parquet.md) — GT side parquet schema
- [DR_axis_labeling.md](1-methodology/DR_axis_labeling.md) — **Phase 6.5 D/R 轴签方法论**（给其他 3 agent 复用 thinkdepthai-qwen 的 D×R 分类方法）
- [agent_prompt_example.md](1-methodology/agent_prompt_example.md) — agent prompt 示例
- [inspect.md](1-methodology/inspect.md) — 调试/检查流程

## 相关外部位置

- 计划源文档：[`../failure_analysis_plan.md`](../failure_analysis_plan.md)
- 历史探索产物：[`../exploration/`](../exploration/)
- Dashboard + metrics 计算代码：[`../RCAgentEval/scripts/dashboard/`](../RCAgentEval/scripts/dashboard/)
- failure_analysis scripts：[`../RCAgentEval/scripts/failure_analysis/`](../RCAgentEval/scripts/failure_analysis/)
