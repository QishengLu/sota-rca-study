# rules/ — Phase 8.1 Middleware 规则 YAML

每个 target R 一个 YAML 文件，命名 `R<id>.yaml`（如 `R1.yaml`、`R2.yaml`）。

## Schema

```yaml
target_R: R<id>                          # 规则针对的 unified R 编号（来自 merged/unified_R.md）
r_name: <R-name>                         # 人类可读名，如 "Absence-Inference"
trigger_condition:                       # 触发条件（trajectory-only；读 agent 轨迹即可）
  type: regex | feature_match | custom
  pattern: |-
    <具体模式，例如 regex over think_tool text 或 tool_call arguments>
  scope: per_round | per_case            # 每轮检查 vs 每 case 检查一次
intervention_prompt: |-                  # 注入 prompt（fixed string，非 GT 相关）
  <prompt 文本>
activation_round: <int | "any">          # 何时注入（通常是触发后的下一轮）
origin_row: <Phase-6-or-6.5-or-7.5 表格行 citation>  # 规则的统计出处
expected_fire_rate:                      # 从 dry-run 得来的上限（phase 8.3 校准后填）
  correct_cases: <% ≤ 20%>
  target_R_failed_cases: <% ≥ 80%>
```

## 准则（再强调）

- **Non-leaking**：prompt 中**绝不**出现 service name / fault type / pod name / 时间窗
- **Trajectory-only triggers**：condition 只读 agent 的 think_tool / tool_call 内容
- **Statistically grounded**：`origin_row` 必须指向一个具体的 Phase 6 / 6.5 / 7.5 表格 cell 或 finding
- **Filtered by dry-run**：进入 Phase 9 之前，`expected_fire_rate.correct_cases ≤ 20%` 必须满足

## 示例（plan 给出的 R1 草稿）

```yaml
target_R: R1
r_name: Absence-Inference
trigger_condition:
  type: custom
  pattern: |
    agent concluded "service X healthy" / "no errors from X" / "X is fine"
    AND service X's span_count in current query scope < 10% of expected
    OR agent saw missing_span flag for X
  scope: per_round
intervention_prompt: |
  Before concluding this service is healthy, check whether its span count
  for this window matches baseline. A service with <10% expected spans may
  be silenced, not healthy.
activation_round: next_round_after_trigger
origin_row: "Phase 6.5 framework_invariants.md §§Absence-of-error → health finding"
```
