# middleware_A/ — Phase 8-10 Middleware 设计 + A/B 验证 + 最终报告

**A-scheme**：针对 Phase 7.5 产出的 **middleware priority set**（framework-universal ∩ model-robust），在 3 个 DR 目标 agent（thinkdepthai-qwen、aiq-qwen、claudecode-qwen）上做 offline + live 的 middleware 验证。

## 目录结构

```
middleware_A/
├── README.md                        # 本文件
├── rules/                           # Phase 8 — 每个 target R 一个 YAML 规则文件
│   ├── R<id>.yaml                   #   包含 trigger_condition / intervention_prompt / activation_round / origin_row
│   └── ...
├── audit_report.md                  # Phase 8 — leakage audit：规则中不得出现 service/fault/pod/time 字符串
├── dry_run/                         # Phase 8 — 在历史轨迹上 offline 重放 fire 次数
│   ├── thinkdepthai-qwen3.5-plus.jsonl
│   ├── aiq-qwen3.5-plus.jsonl
│   └── claudecode-qwen3.5-plus.jsonl
├── regression_set_<agent>.jsonl     # Phase 9.2 — 分层抽样的 correct-case 回归集
├── part2_universal_R.md             # Phase 10.1 — universal R set 最终版 + 跨 agent 分布
├── part2_middleware_rules.md        # Phase 10.2 — 冻结规则集 + origin-row 引用 + leakage + dry-run 统计
├── part2_validation.md              # Phase 10.3 — recovery/regression/net-Δ 表 + R-specific 拆分 + 6-agent AC@1 context chart
└── part2_narrative.md               # Phase 10.4 — 文章叙事主线
```

## Phase 进度

| Phase | 工作 | 产物 |
|---|---|---|
| 8.1 | Per-R 规则 + prompt 设计 | `rules/R<id>.yaml` |
| 8.2 | Leakage audit | `audit_report.md` |
| 8.3 | Offline dry-run on 3 agent ×（correct + failed）= 1500 historical trajectories | `dry_run/<agent>.jsonl` |
| 8.Gate | User 签收 leakage pass + dry-run stats | — |
| 9.1 | Failure-case recovery test（treatment group）| DB 新 exp_id `<agent>-middleware-v1` |
| 9.2 | Correct-case regression test（分层抽样 60-80 cases/agent）| `regression_set_<agent>.jsonl` |
| 9.3 | Net Δ AC@1 计算（per agent + 95% bootstrap CI）| 进入 `part2_validation.md` |
| 9.4 | Baseline context re-run（openrca/mabc/taskweaver 不加 middleware）| 进入 6-agent AC@1 chart |
| 9.5 | Optional 单 baseline（openrca）robustness 测试 | 进入 `part2_validation.md` |
| 10 | 四份最终报告 + dashboard 集成（optional） | `part2_*.md` |

## Design principles（load-bearing，plan §Part II）

- **Non-leaking**：规则 prompt 是 fixed string，无 service/fault/pod/time 替换，leakage_audit.py 自动扫描
- **Trajectory-only triggers**：触发条件只读 agent 的轨迹，不读 GT / batch / conclusion.csv
- **Statistically grounded**：每条规则引用 Phase 6 或 Phase 7.5 的具体 table row 作为依据 — 无"手搓规则"
- **Offline dry-run first**：规则在 1500 条历史轨迹上先过 fire-rate sieve，fire-on-correct 超过 20% 的直接淘汰
- **Per-R A/B evaluation**：验收标准是 `recovery_rate_R<x>`，不止是 overall AC@1 提升
- **Closed loop**：若 Phase 6/7 声称"信号 S 导致 R-theme X"且在 A/B 提升了 R-theme X 的 recovery，则因果声明成立；否则框架降级为 descriptive-only

## Acceptance criteria（plan §Phase 9 acceptance + Gate 11）

- 每个 target agent：`regression_rate ≤ 5%` AND `net_Δ_AC@1 > 0`（95% CI 排除 0）
- 没有单一 R 规则贡献 >50% 的 regression
- **Closed-loop check**：至少 1 个 R-theme 有 signature → rule → A/B recovery 完整链；否则 `part2_narrative.md` 中标记框架为 descriptive-only

## 相关外部代码

middleware 相关脚本位于 `../../../../RCAgentEval/scripts/failure_analysis/`（或 `middleware_A/`，见 plan 的 New Code 清单）：
- `audit_leakage.py` — 规则安全扫描
- `dry_run.py` — 历史轨迹 offline 重放
- `sample_regression_set.py` — correct case 分层抽样
- `runner.py` — agent + middleware rollout（复用 RolloutRunner）
- `compute_metrics.py` — recovery / regression / net-Δ 统计
