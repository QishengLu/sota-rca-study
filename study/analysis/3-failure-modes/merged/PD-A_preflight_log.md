# PD-A Pre-flight Log

Date: 2026-04-22
Executor: HARP orchestrator (auto mode)

## 1. Intent coverage check

Query: count of `meta.llm_intents.final` vs `meta.llm_intents.claude_opus_4_6` per exp_id.

| exp_id | with_final | with_opus | failed_judged | total | final coverage of total |
|---|---|---|---|---|---|
| aiq-qwen3.5-plus | 500 | 500 | 113 | 500 | 100.0% |
| claudecode-qwen3.5-plus | 498 | 500 | 103 | 500 | 99.6% |
| thinkdepthai-claude-sonnet-4.6 | 500 | 500 | 51 | 500 | 100.0% |
| thinkdepthai-qwen3.5-plus | 500 | 500 | 105 | 500 | 100.0% |

**Result**: All ≥95% threshold met. Sub-agents instructed to prefer `meta.llm_intents.final`.

### Fallback cases

- **claudecode-qwen3.5-plus dataset_index=1837**: missing `final` but has `claude_opus_4_6`. This case IS in the labeled failure set. Instruction to claudecode sub-agent: for case_id=1837 only, fallback to `claude_opus_4_6` and note in `PD_induction_log.md`.

Total labeled case count verified: 113 + 103 + 51 + 105 = **372 rows** in labels.jsonl (2 dataset_anomaly excluded by R merge → 370 R-labeled cases contribute to PD induction).

## 2. D/R frozen references copy

`D_projection.jsonl` (372 rows) and `R_merge_table.jsonl` (29 rows) copied as `*_frozen.jsonl` into each per-framework workspace:
- `analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/v1/`
- `analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/`
- `analysis/3-failure-modes/2-by-framework/thinkdepthai-claude-sonnet-4.6/v1/`
- `analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v1_harp/`

These are frozen references for end-of-induction self-check ("is this PD just R or D in disguise?"). **Not used as decision input.**

## 3. Dossier path check

| framework | labels | dossier MD | dossier raw.json |
|---|---|---|---|
| aiq | 113 | 113 | 113 |
| claudecode | 103 | 114 | 0 (raw omitted by builder) |
| sonnet | 51 | 51 | 51 |
| qwen (v2/) | 105 | 105 | 105 |

claudecode has only `.md` dossiers (raw.json missing by prior builder config); the MD files already contain Part B trajectory blocks so sub-agent can triangulate without raw.json.

## 4. Outputs to sub-agents

Path layout:
- aiq → data `aiq-qwen3.5-plus/v1/`, output `aiq-qwen3.5-plus/v1/`
- claudecode → data `claudecode-qwen3.5-plus/v1/`, output `claudecode-qwen3.5-plus/v1/`
- sonnet → data `thinkdepthai-claude-sonnet-4.6/v1/`, output `thinkdepthai-claude-sonnet-4.6/v1/`
- qwen → data `thinkdepthai-qwen3.5-plus/v2/`, output `thinkdepthai-qwen3.5-plus/v1_harp/`

All 4 sub-agents will write 3 files each: `PD_phrases.jsonl`, `PD_inductive.md`, `PD_induction_log.md`.

## 5. Frozen per-framework case counts

- aiq = 113 labeled failure cases
- claudecode = 103 labeled failure cases
- sonnet = 51 labeled failure cases
- qwen = 105 labeled failure cases (data source = v2/)
- **Total = 372** (2 dataset_anomaly cases excluded from R axis, but still appear in D labels; PD induction operates over full 372 for full coverage).

Per plan, PD induction pool is 370 R-labeled failure cases. Sub-agents may produce empty PD lists for the 2 dataset_anomaly cases (qwen case 4463 equivalent etc.) and tag them confidence=low.
