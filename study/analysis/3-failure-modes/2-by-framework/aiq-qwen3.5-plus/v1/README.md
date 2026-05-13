# aiq-qwen3.5-plus failure mode analysis (v1)

## Sealing rule (load-bearing)

**Do NOT open these files during labeling** until the aiq v1 taxonomy is frozen:

- `analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/taxonomy.md`
- `analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/per_case_analysis.md`
- `analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/taxonomy.md` (if present)
- `analysis/3-failure-modes/2-by-framework/thinkdepthai-claude-sonnet-4.6/v1/taxonomy.md` (if present)

The aiq taxonomy is derived from aiq's own failure phrases. Cross-framework merge happens later (Phase 7.5), with the thinkdepthai/claudecode taxonomies only unsealed at that point.

## Scope

- Framework: aiq (NVIDIA AIRA 5-stage LangGraph pipeline with 2 reflect iterations)
- Model: qwen3.5-plus (via 百炼 Coding Plan)
- exp_id: `aiq-qwen3.5-plus`
- Judged: 500, failed: 113 (AC@1 = 77.4%)
- Scope: ALL 113 failed cases, 3-block analysis per case, no sampling

## Pipeline context (relevant for per-case analysis)

```
generate_queries (1 LLM, invisible in trajectory)
  → data_research  (main sub-loop, max_rounds=60)
  → build_graph    (compress, 1 LLM, invisible)
  → reflect_on_graph (2 × refine sub-loops, max_rounds=15 each)
  → finalize_summary (0 LLM)
```

The trajectory only captures AIMessage + ToolMessage from the 3 sub-loops; HumanMessage injections (query, schema replay, "REFINE not overturn" instruction) are invisible.

Stage boundaries in the trajectory are detected by content-only assistant messages (tool_calls=[], content non-empty) — the natural "I'm done, here are findings" response terminating each sub-loop. Stages without a terminator hit max_rounds.

Empirical terminator distribution across 113 failed cases:
- 3 terminators (all stages concluded): 18 cases (16%)
- 2 terminators (one stage hit max_rounds): 52 cases (46%)
- 1 terminator (two stages hit max_rounds): 43 cases (38%)

## Workspace layout

```
aiq-qwen3.5-plus/
├── failed_cases.jsonl         # 113 failed cases exported from DB
├── build_dossier.py           # dossier builder (aiq adapter v2)
└── v1/
    ├── README.md              # this file
    ├── dossiers/              # case_<idx>.md per failed case
    │   └── index.md           # sortable list
    ├── per_case_analysis.md   # my rolling 3-block analyses
    ├── taxonomy_working.md    # working taxonomy (churns during labeling)
    ├── taxonomy.md            # FROZEN copy at the end
    └── labels.jsonl           # final labels mirror
```

## Methodology

Follows `failure_analysis_plan.md` Phase 7.2–7.3 with the aiq adapter v2 specified in Phase 7.1.

Per-case 3-block template (plain-language, no theme names during writing):

```
## case_<idx>  [fault_type / subtype]

### (1) What really happened
<GT-grounded, cite conclusion.csv spans or anomalous metrics>

### (2) What the agent did
<trajectory-grounded, cite round indices, note pipeline stage boundaries>

### (3) Divergence
- Pivot round: <round_idx>
- Pipeline stage at pivot: <stage_0_main | stage_1_refine1 | stage_2_refine2 | truncated>
- What agent should have observed: <GT evidence>
- What agent observed instead: <round-cited>
- Proximate cause (<6 words, causal error phrase): <...>

### (4) Behavioral overlay (passive context, not part of label)
- Intent at pivot round: <from llm_intents if available>
- Stage transition history: <terminator content summaries or truncation flags>
```

## Freeze condition

- All 113 cases have `primary` label.
- `unclassified` ≤ 5 cases (≤ 4.4%).
- Working taxonomy stops churning on the last batch of ~20.

After freeze: copy `taxonomy_working.md` → `taxonomy.md`, write `labels.jsonl`, and run DB write `meta.failure_analysis.v1.*`.
