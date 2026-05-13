# k=5 Paired Resampling — thinkdepthai-qwen3.5-plus

**Generated**: 2026-04-24
**Purpose**: Filter baseline single-run "failed" pool down to a noise-robust stable failure set
for Phase 9 middleware validation.

---

## Methodology

For each of the 105 cases that `thinkdepthai-qwen3.5-plus` failed in its single baseline run,
4 additional independent rollouts were collected (k=5 total: 1 baseline + 4 resamples).

- **Model**: `qwen3.5-plus` (alias) — verified byte-equivalent to `qwen3.5-plus-2026-02-15`
  snapshot via deterministic prompt comparison on 2026-04-24 (alias was pinned to 2026-02-15
  during the entire experiment window). DB exp_id and `model_name` column are stored under
  the snapshot name for paper-table convenience; `meta.cost_metrics.model` records the
  alias for audit trail.
- **API**: Alibaba DashScope (`https://dashscope.aliyuncs.com/compatible-mode/v1`),
  standard tier (5M TPM / 30k RPM on alias).
- **Temperature**: agent default (`temperature=0` in `Deep_Research/model_factory.py`).
  LLM-side determinism still imperfect due to GPU/batching, hence resampling produces
  meaningful variance.
- **Resample exp_ids**:
  - `thinkdepthai-qwen3.5-plus-2026-02-15-resample-1`
  - `thinkdepthai-qwen3.5-plus-2026-02-15-resample-2`
  - `thinkdepthai-qwen3.5-plus-2026-02-15-resample-3`
  - `thinkdepthai-qwen3.5-plus-2026-02-15-resample-4`
- **Per-resample AC@1 on the 105 baseline-failed pool**: 44.8% / 41.9% / 46.7% / 41.9%

## Schema (`stable_failure_set_k5.jsonl`)

| Field | Type | Description |
|---|---|---|
| `dataset_index` | int | RCAbench dataset index |
| `case_name` | str | RCAbench case identifier (e.g. `ts0-ts-order-service-stress-cklk2p`) — encodes target service + fault type + run id |
| `datapack` | str | Telemetry parquet bundle (e.g. `data_96d68293`); rooted under `RCAgentEval/eval-data/<exp_id>/` |
| `primary_theme` | str | v1 frozen taxonomy theme (T1..T8 from `meta.failure_analysis.v1.primary`) |
| `fault_category` | str | HTTPFault / NetworkChaos / JVMChaos / PodChaos |
| `fault_type` | str | concrete fault subtype |
| `spl` | int | shortest-path-length difficulty proxy |
| `root_cause_service` | str | GT root cause service name |
| `r1`..`r4` | "P"/"F" | per-resample outcome (P=correct, F=fail) |
| `baseline_outcome` | "F" | always F (these are baseline-failed cases) |
| `full_sequence` | str | "F<r1><r2><r3><r4>" e.g. "FFFFP" |
| `fails_5` | int | total fail count out of 5 (baseline + 4 resamples) |
| `p_fail` | float | `fails_5 / 5` ∈ {0.2, 0.4, 0.6, 0.8, 1.0} |
| `tier` | str | `ultra_hard` (1.0) / `stable` (0.8) / `borderline` (0.6) / `noise` (0.4) / `lucky_baseline` (0.2) |

## Aggregate distribution

| Tier | p_fail | Cases | Cumulative ≥ tier |
|---|---:|---:|---:|
| ultra_hard | 1.0 | 29 | 29 |
| stable | 0.8 | 24 | **53** |
| borderline | 0.6 | 14 | 67 |
| noise | 0.4 | 20 | 87 |
| lucky_baseline | 0.2 | 18 | 105 |

**Recommended Phase 9 stable failure set**: `p_fail ≥ 0.8` → **53 cases** (cumulative
through `stable` tier). Looser cut at `p_fail ≥ 0.6` → 67 cases also defensible.

## Theme distribution within p_fail ≥ 0.8 (53 cases)

| Theme | Stable count | Of which p_fail=1.0 |
|---|---:|---:|
| T2_Blame-the-Messenger | 17 | 10 |
| T3_Noise-Anchor | 14 | 8 |
| T1_Silence-as-Health | 9 | 5 |
| T4_Amplitude-Greed | 7 | 5 |
| T5_Query-Blindness | 3 | 1 |
| T6_Path-Through | 1 | 0 |
| T7_Business-Logic-Confabulation | 1 | 0 |
| T8_Causal-Inversion | 1 | 0 |

T1+T2+T3+T4 alone account for **47/53 = 89%** of stable failures, all of which have
direct or near-direct mappings to v4 metacognitive dimensions (M1, M2, M5, M8).

## Reproducing this dataset

```bash
# Per-tier filter
jq -c 'select(.p_fail >= 0.8)' stable_failure_set_k5.jsonl   # 53 cases
jq -c 'select(.p_fail == 1.0)' stable_failure_set_k5.jsonl   # 29 ultra-hard

# Per-theme filter
jq -c 'select(.primary_theme == "T2_Blame-the-Messenger" and .p_fail >= 0.8)' \
  stable_failure_set_k5.jsonl
```
