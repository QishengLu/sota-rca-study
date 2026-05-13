# 2-by-framework/ — 按 agent 的失败分析工作区

每个 agent 一个独立工作区，对应 `failure_analysis_plan.md` Phase 1-6 （thinkdepthai-qwen）和 Phase 7.1-7.4 + 5-6（其他 3 agent）的产物。

## 当前进度

| Agent | Failed cases | 工作区 | Phase 1-4 | Phase 4b | Phase 5 | Phase 6 | Phase 6.5 D/R |
|---|---:|---|---|---|---|---|---|
| thinkdepthai-qwen3.5-plus | 105 | [`thinkdepthai-qwen3.5-plus/v2/`](thinkdepthai-qwen3.5-plus/v2/) | ✅ | ⬜ | ⬜ | ⬜ | ⬜（已有 D/R 原生标注，需补 dr_axis_mapping.md 格式化） |
| thinkdepthai-claude-sonnet-4.6 | 51 | [`thinkdepthai-claude-sonnet-4.6/v1/`](thinkdepthai-claude-sonnet-4.6/v1/) | ✅ | — | ⬜ | ⬜ | ⬜ |
| aiq-qwen3.5-plus | 113 | [`aiq-qwen3.5-plus/v1/`](aiq-qwen3.5-plus/v1/) | ✅ | — | ⬜ | ⬜ | ⬜ |
| claudecode-qwen3.5-plus | 103 | [`claudecode-qwen3.5-plus/v1/`](claudecode-qwen3.5-plus/v1/) | ✅ | — | ⬜ | ⬜ | ⬜ |

## 每个 agent 工作区的标准结构（Phase 1-6.5 完成后）

所有 dossier builder / adapter 代码统一在 `RCAgentEval/scripts/failure_analysis/` 下（不在 per-workspace 拷贝副本），workspace 下只放数据产物。

```
<agent>/
├── failed_cases.jsonl          # Phase 0 — 从 DB 导出的 failed_case 索引（dataset_index + fault_type + difficulty）
└── v1/ or v2/                  # 版本化工作区
    ├── README.md               # 本 workspace 的文件清单 + phase 对应
    ├── dossiers/
    │   ├── case_<idx>.md       # Phase 1 — per case dossier（Part A GT + Part B trajectory）
    │   └── ...
    ├── sample_batch_1.md       # Phase 2 — 15-case stratified 样本表（thinkdepthai-qwen only）
    ├── budget_log.md           # Phase 2+4 — 每 case 的 token/time 成本（thinkdepthai-qwen only）
    ├── per_case_analysis.md    # Phase 2+4 — 所有 case 的三段式分析（What really happened / What agent did / Divergence）
    ├── taxonomy_working.md     # Phase 3 — 迭代中的工作版 taxonomy（可选）
    ├── taxonomy.md             # Phase 3 冻结版 — theme 定义 + positive/negative criteria + canonical examples
    ├── progress.md             # Phase 4 — 每 case done / needs-review 状态（可选）
    ├── labels.jsonl            # Phase 4 — 每行 1 个 case 的 primary theme + pivot_round + proximate_cause + evidence
    ├── labels_aligned.jsonl    # Phase 4b — thinkdepthai-qwen only：统一 schema 的 labels
    ├── write_labels_to_db.py   # Phase 4/4b — 机械写 DB 的脚本（per-agent 因 exp_id 和 case 字段名不同而独立）
    ├── spot_check.md           # Phase 5 — user 抽查 20 case 的 Correct/Wrong/Ambiguous 标记
    ├── validation.md           # Phase 5 — 3 项检查的汇总（spot-check ≥85%、exhaustiveness ≤10%、χ² orthogonality）
    ├── behavior_failure_join.md    # Phase 6 — 6 张交叉表 + 统计测试 + 解读
    ├── behavior_failure_join.json  # Phase 6 — 机器可读的同内容
    ├── dr_d_categories.md      # Phase 6.5.a — 该 agent 独立归纳的 D 类别（definition + positive/negative criteria + cases）
    ├── dr_r_categories.md      # Phase 6.5.a — 该 agent 独立归纳的 R 类别（+ middleware trigger per R）
    ├── dr_labels.jsonl         # Phase 6.5.a — per-case (D_phrase, D_category, R_phrase, R_category)
    └── dr_cross_tab.md         # Phase 6.5.a — 该 agent 的 D × R 交叉表（per-agent 类别）
```

**代码解耦：**

```
RCAgentEval/scripts/failure_analysis/
├── build_dossiers.py                       # 主 dossier builder（thinkdepthai-qwen 默认）
├── dossier_adapters/
│   ├── aiq.py                              # aiq pipeline-stage-aware
│   ├── claudecode.py                       # claudecode Bash→DuckDB + [thinking] 解析
│   └── thinkdepthai_sonnet_trim_helper.py  # sonnet 专用 dossier 后处理
├── behavior_failure_join.py                # Phase 6 多 agent 版
├── validate.py                             # Phase 5 多 agent 版
├── align_thinkdepthai_qwen_schema.py       # Phase 4b 一次性迁移
├── cross_agent_compare.py                  # Phase 6.5 跨 agent 比较
└── write_labels_to_db.py                   # Phase 4 中央写 DB 脚本（优先使用；per-workspace 的副本是特殊 case schema）
```

## Sealing rule（Phase 7.3 历史规定）

每个 agent 在 **per-agent labeling** 阶段（Phase 1-4）独立工作，**不**读其他 agent 的 `taxonomy.md` 或 `per_case_analysis.md`。目的：避免把 thinkdepthai-qwen 的 R1-R7 套到 aiq/claudecode，遗漏 framework-specific 失败模式。

sealing rule 已经履行 —— 4 个 agent 的 per-agent taxonomy 都是独立产物，theme 命名各不相同（例如 aiq 的 `T5_ReflectionReversesCorrect` 是 aiq 独有）。

sealing 在 Phase 7.5 merge 时解除 —— 跨 agent 对比 themes 才用得到其他 agent 的 taxonomy。

## 与历史探索分析的解耦

本目录所有产物均为 `failure_analysis_plan.md` 定义的产物；**不**与任何历史分析（包括 thinkdepthai-qwen 早期的 151cases-*.md / 270cases-DR.md、claudecode 早期的 DR.md、1-cross-model-comparison/ 等）建立映射或沿用。历史分析已移到 [`../../../../exploration/`](../../../../exploration/) 只作为探索记录存档。
