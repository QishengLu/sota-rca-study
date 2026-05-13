# dry_run/ — Phase 8.3 Offline 历史轨迹重放

对 3 个 DR 目标 agent 的所有 judged 轨迹（correct + failed，1500 条）做 offline 重放，记录每条规则会在哪些 case/round fire。

## 产物

| 文件 | 行格式 |
|---|---|
| `thinkdepthai-qwen3.5-plus.jsonl` | `{case_idx, R_rule, fire_round, original_label_if_failed, was_correct}` |
| `aiq-qwen3.5-plus.jsonl` | 同上 |
| `claudecode-qwen3.5-plus.jsonl` | 同上 |

## Sieve（进入 Phase 9 之前）

- `fire_rate_on_correct_without_target_R = P(fire | correct && not target_R)`
- **保留**：`fire_rate_on_correct_without_target_R ≤ 20%`
- **淘汰**：高于 20% → 触发过泛，直接放弃该规则

## 汇总报告（写入 `../part2_middleware_rules.md` §dry-run stats）

```
| Rule | Agent | Fires | On-correct fires | Target-R recall | Kept? |
|------|-------|------:|-----------------:|----------------:|-------|
| R1.yaml | thinkdepthai-qwen | 23 | 2 (9%) | 14/17 (82%) | ✅ |
| ...
```
