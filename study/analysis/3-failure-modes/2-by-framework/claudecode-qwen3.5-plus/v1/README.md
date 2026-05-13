# claudecode-qwen3.5-plus v1 — Failure Analysis Workspace

## Status

- Rollout + judge: ✅ complete (500 samples, 386 correct, 114 failed → 77.2% AC@1)
- Failure-mode labeling: 🔲 not yet started (this directory is the workspace)

## Scope — Independent emergent taxonomy (NOT re-using thinkdepthai's D×R)

This is the key methodological rule: **build claudecode's own failure taxonomy from its own 114 cases**, using the same 3-block per-case analysis process, but without anchoring on thinkdepthai's R1-R7. The merge / comparison happens only after all 3 agents (thinkdepthai, aiq, claudecode) have independent taxonomies.

Why: if I start by labeling claudecode cases with thinkdepthai's R1-R7, I will unconsciously force-fit — every "missing spans led to wrong conclusion" gets called R1 regardless of whether the claudecode trajectory has the same divergence structure. The thinkdepthai taxonomy stays offline during claudecode labeling.

Reference docs:
- **Methodology** (same 3-block rule): `/home/nn/SOTA-agents/failure_analysis_plan.md` (Phases 1–3 as method, Phase 7 as cross-framework scope)
- Thinkdepthai taxonomy (**do not open until claudecode taxonomy is frozen**): `/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/taxonomy.md`
- Thinkdepthai per-case analyses (**do not read during labeling**): `/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/per_case_analysis.md`

The thinkdepthai artifacts exist as a sealed box — referenced only after `v1/taxonomy.md` here is finalized, to produce a comparison mapping.

## Failed cases

`../failed_cases.jsonl` — 114 rows, schema:
```
{dataset_index, fault_type, fault_category, spl, n_svc, n_edge, root_cause_service}
```

### Distribution

| fault_category | n |
|---|---|
| JVMChaos | 37 |
| PodChaos | 29 |
| HTTPFault | 25 |
| NetworkChaos | 23 |
| **Total** | **114** |

### Top fault types

JVMMemoryStress=31, ContainerKill=22, HTTPResponseDelay=9, NetworkBandwidth=8, PodFailure=6, HTTPResponseReplaceCode=5, NetworkPartition=4, NetworkDelay=4, NetworkCorrupt=4, HTTPResponseReplaceBody=3, (others <3)

## Trajectory-format quirks (claudecode-specific)

Unlike thinkdepthai (which uses `query_parquet_files` tool directly), claudecode issues SQL via `Bash(duckdb -c "...")`. Key differences:

| Aspect | thinkdepthai | claudecode |
|---|---|---|
| Tool name | `query_parquet_files` | `Bash` (+ rare `Write`, `Read`) |
| SQL location | `tool_calls[i].arguments.query` | inside `Bash.command`, regex extract |
| Reasoning | `think_tool` tool call | `[thinking] ...` block in assistant content |
| Trajectory length | ~50 rounds median | 47-50 rounds median (per new round definition) |
| Tool_call fan-out | 1 per assistant msg | often 3-6 parallel Bash in one message |

### Round definition (user-agreed 2026-04-16)

A **round** = all consecutive tool invocations (across possibly multiple assistant msgs, each with ≥1 tool_call) + all their corresponding tool results.
- Steps inside a round are numbered in issue order across all tool_calls in that round.
- Preceding pure-reasoning assistant messages attach to the round as `reasoning_before`.
- Plain-text transition messages attach as `transition_text`.
- Inline reasoning between tool_calls attaches as `inline_reasoning`.

### Dossier builder

`../build_sample_dossier.py` — adapter v3 implementation. Key extraction patterns:

```python
# SQL extraction (outer-quote aware)
DUCKDB_SQL_DQ_RE = re.compile(r'duckdb\b[^"\n]*?-c\s+"((?:\\"|[^"])+)"', re.DOTALL)
DUCKDB_SQL_SQ_RE = re.compile(r"duckdb\b[^'\n]*?-c\s+'((?:\\'|[^'])+)'", re.DOTALL)

# Reasoning extraction
THINKING_RE = re.compile(r"\[thinking\]\s*(.+?)(?=\n\s*\n|\Z)", re.DOTALL)
```

## Sample dossiers built (format reference only)

Two representative cases pre-built as templates:

| File | case | fault | fault_category | rounds | GT RC | Predicted |
|---|---|---|---|---|---|---|
| `dossiers/case_33.md` | 33 | JVMMemoryStress | JVMChaos | 50 | ts-auth-service | ts-ui-dashboard |
| `dossiers/case_2211.md` | 2211 | ContainerKill | PodChaos | 47 | ts-travel-service | ts-route-plan-service |

**Purpose**: verify the dossier builder produces a readable format. They are NOT pre-labeled case studies, and no R-label hint should be carried forward — the first step of labeling is to read them fresh and describe the divergence in your own words.

## Workflow (independent taxonomy build — ALL 114 cases, no early freeze)

**Scope rule (load-bearing)**: every one of the 114 failed cases gets a full 3-block analysis + a proximate-cause phrase. The taxonomy is an evolving working document throughout labeling — it is NOT frozen at a sampled saturation batch. The final freeze happens only after all 114 cases have phrases assigned AND the taxonomy stops changing across the last few cases.

No sampling. No saturation early-stop. No per-agent budget cap.

### Step 1 — Build all 114 dossiers

```bash
# Edit sample_indexes in build_sample_dossier.py main() to the full list
#   of 114 dataset_indexes from failed_cases.jsonl.
UTU_DB_URL="postgresql://postgres:postgres@localhost:5433/SOTA-Agents" \
  uv run python build_sample_dossier.py
```

Output: `v1/dossiers/case_<idx>.md` × 114.

### Step 2 — Per-case analysis on all 114 cases (continuous)

Read cases in a sensible order (e.g., sorted by `fault_category` then `dataset_index`, or fully random-shuffled once for coverage). For EACH of the 114 cases, write a 3-block analysis into `v1/per_case_analysis.md`:

```
## case_<idx>  [fault_type / subtype]

### (1) What really happened
<2-4 sentences grounded in Part A: injection target + conclusion.parquet evidence>

### (2) What the agent did
<2-4 sentences grounded in Part B: hypothesis trajectory, key round numbers>

### (3) Divergence
- Pivot round: <N>
- Missed signal: <specific GT evidence the agent failed to use>
- Agent saw instead: <round-cited observation that anchored the wrong conclusion>
- Proximate cause (<6 words, causal phrasing): <short phrase>
```

**No theme names** (no R1/R2/..., no T1/T2/..., no borrowed thinkdepthai labels) during per-case analysis. Just the proximate-cause phrase in block (3).

### Step 3 — Working taxonomy (evolves throughout Step 2)

Alongside the per-case analyses, maintain `v1/taxonomy_working.md` as a growing scratchpad. Every ~20 cases, pause briefly to:
- Re-read the accumulated proximate-cause phrases.
- Cluster them into tentative themes.
- Update positive/negative criteria where a cluster's scope has shifted.
- Add new themes when a phrase doesn't fit any existing cluster.
- Split or merge themes as necessary.

The working taxonomy is expected to churn heavily in the first 40–60 cases and stabilize in the last 20–30. Do not declare the taxonomy frozen prematurely — new cases can always introduce new themes or force redefinition of existing ones.

### Step 4 — Final pass: assign primary labels to all 114

Only after Step 2 completes on all 114 cases, do one more pass through `v1/per_case_analysis.md` and assign a `primary` theme to each case using the current `v1/taxonomy_working.md`. Unclassifiable cases get `primary: "unclassified"` and trigger a final taxonomy edit (split an existing theme, add a new one, or accept permanently unclassifiable).

Write `v1/labels.jsonl`:

```json
{"case": <idx>, "fault_type": ..., "gt_services": [...], "predicted": [...],
 "pivot_round": <N>, "proximate_cause": "<phrase>", "primary": "<theme_name>",
 "secondary": []}
```

Target: `unclassified` count ≤ 5% (≤ 6 of 114). If higher, taxonomy needs more revision — do NOT freeze yet.

### Step 5 — Freeze taxonomy

Copy `v1/taxonomy_working.md` → `v1/taxonomy.md` and mark it frozen. This is the point where:
- The taxonomy definitions, positive/negative criteria, and canonical examples are locked.
- Any changes after freeze require an explicit version bump (e.g., `v2/taxonomy.md`).

### Step 6 — DB write

`meta.failure_analysis.v1.{primary, secondary, pivot_round, proximate_cause}` on all 114 rows for `exp_id='claudecode-qwen3.5-plus'`. Use `flag_modified(sample, "meta")`.

### Step 7 — (later, cross-session) Merge

Produces a separate artifact `analysis/3-failure-modes/merged/cross_framework_taxonomy.md` comparing thinkdepthai vs claudecode vs aiq themes. This merge step is NOT done in the claudecode session — it happens only after all three independent taxonomies exist.

## Observations that MAY or MAY NOT become claudecode-specific themes

Do NOT pre-assume these are themes — they are things to watch for and may or may not survive the clustering. Listed so the new session has them in scope:

- **Parallel query dilution**: claudecode sends 5-10 parallel Bash/DuckDB in one round. Sometimes the critical result is buried among 9 irrelevant ones.
- **Output inflation**: claudecode sometimes emits multiple nodes in final answer without narrowing to a single root_cause. This may be an output-format artifact, not a reasoning error — decide case-by-case.
- **Exit-code retry loops**: DuckDB syntax errors trigger Bash exit 1, agent retries. Count as failure mode only if retries never surface the true signal.
- **Schema-first paralysis**: claudecode always queries DESCRIBE on all 10 parquet files first. In ~4-5 round cases this eats 30-40% of the rounds before any analysis starts. Is this a time-budget issue or a reasoning issue?

## Gotchas

- **DB column**: trajectory lives in `trajectories` (plural), not `trajectory`.
- **data_dir extraction**: `data_dir` parsed from `augmented_question` regex `stored in[:\s]+['"`]?([^\s'"`]+)`.
- **GT parsing**: root cause is in `DatasetSample.meta.ground_truth` (list of services), not under `difficulty`.
- **conclusion.parquet columns**: `SpanName, AbnormalAvgDuration, NormalAvgDuration, AbnormalSuccRate, NormalSuccRate, AbnormalP90/P95/P99, NormalP90/P95/P99, Issues`.
