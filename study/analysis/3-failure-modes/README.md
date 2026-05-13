# 3-failure-modes/ — failure_analysis_plan 主工作区

本目录汇集 4 个已标注 agent 的失败分析产物 + 跨 agent 对比 + 合并 + middleware。

## 子目录

| 子目录 | Phase | 内容 |
|---|---|---|
| [`2-by-framework/`](2-by-framework/) | 1-6 / 7.1-7.4 | 每个 agent 独立工作区（dossier、taxonomy、labels、Phase 5-6 per-agent 产物） |
| [`cross-agent/`](cross-agent/) | 6.5 | 跨 agent 并排对比 + D/R 轴签汇总 |
| [`merged/`](merged/) | 7.5-7.6 | 跨框架合并 → unified R + 分布表 |
| [`middleware_A/`](middleware_A/) | 8-10 | Middleware 规则设计、dry-run、A/B 验证、最终 4 份报告 |

## 工作流依赖

```
Phase 1-4 (done)
    ↓
Phase 4b (thinkdepthai-qwen schema align)
    ↓
Phase 5 (per-agent validation) × 4   →   Phase 6 (per-agent join) × 4
                                                ↓
                                         Phase 6.5.a (per-agent 独立 D/R 归纳) × 4
                                                ↓
                                         Phase 6.5.b (cross-agent 对比)
                                                ↓
                                         Phase 7.5 (merge → unified R)
                                                ↓
                                         Phase 7.6 (DB write unified R)
                                                ↓
                                         Phase 8 (middleware rules + dry-run)
                                                ↓
                                         Phase 9 (A/B live validation)
                                                ↓
                                         Phase 10 (final reports)
```

## 关键 gate 说明

- **Phase 5 gate（per agent）**：user spot-check 20 cases ≥85% + exhaustiveness ≤10% + χ² orthogonality 报告 → 签收 `<agent>/validation.md` 后该 agent 才能进 Phase 6
- **Phase 6.5 gate**：4 agent 的 behavior-failure join 都由用户签收后，才产出跨 agent 5 份产物；然后用户签收 cross-agent 后才进 Phase 7.5
- **Phase 7.7 gate**：user 签收 merged/unified_R.md + middleware priority set 后才进 Phase 8
- **Phase 8 gate**：leakage audit + dry-run firing stats 签收后才进 Phase 9
- **Phase 9 acceptance**：per-agent regression_rate ≤ 5% 且 net_ΔAC@1 > 0（95% CI 排除 0）
