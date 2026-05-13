# merged/ — Phase 7.5-7.6 跨框架合并

**前置**：Phase 6.5 的 5 份跨 agent 产物签收 + 4 个 per-agent taxonomy 冻结。

**目的**：把 4 个独立 taxonomy 合并成**统一 R set**（unified R），给 Phase 8 middleware 设计提供可操作目标。

## 产物

| 文件 | 内容 | Phase |
|---|---|---|
| `theme_grid.md` | 4 agent × (4 agent) 的 pairwise theme 关系矩阵：每对 themes 标记 {identical, overlap, subset, superset, orthogonal, unique} | 7.5.1 |
| `unified_R.md` | 合并后的 unified R 定义（保留 ≥2 agent 共享机制的 R；framework-unique 放附录） | 7.5.2 |
| `labels_unified.jsonl` | 每个 case 的 unified R 标签（从 per-agent primary theme 通过 merge table 映射） | 7.5.3 |
| `distributions.md` | Unified R × agent 的失败占比表 + universal R set + model-robust R set + middleware priority set | 7.5.5 |

## 关键 set 定义

| Set | 定义 | 用途 |
|---|---|---|
| **Framework-universal R** | Unified R 在 {thinkdepthai-qwen, aiq-qwen, claudecode-qwen} 中 ≥2 个 agent 出现且占比 ≥10% | 证明"跨框架重现" |
| **Model-robust R** | Unified R 在 thinkdepthai-qwen vs thinkdepthai-sonnet4.6 的占比差 ≤5pp | 证明"不被换更强模型消除" |
| **Middleware priority set** | Framework-universal ∩ Model-robust | Phase 8 的 middleware 规则必须针对的 R 类 |

## 执行约束

- **Unclassified 审计**：unified R set 必须覆盖每 agent 的 ≥85% 标注 case，否则拒绝合并
- **Sealing unsealed**：Phase 7.5 是 per-agent taxonomy **首次被共读** 的时刻 —— Phase 6.5 的 `lightweight_axis_labels.md` 已给出初步指引，但最终 pairwise 对比由分析员逐对读 theme 定义 + canonical example 决定

## DB 写入（Phase 7.6）

合并完成后，对 4 exp_id 的所有已标注 rows 追加：
- `meta.failure_analysis.v1.unified_R` — 映射后的统一 R
- `meta.failure_analysis.v1.D` — 按 fault_type 查表（其他 3 agent 在 Phase 6.5 已写过，这里核验）

per-agent `primary` theme **保留不动**，unified_R 是附加列。
