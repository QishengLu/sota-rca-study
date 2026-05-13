# thinkdepthai-claude-sonnet-4.6 — Failure Mode Analysis v1

## What this is

Independent failure-mode taxonomy for the `thinkdepthai-claude-sonnet-4.6` experiment.

**Ablation axis**: same LangGraph ReAct framework + same prompt as `thinkdepthai-qwen3.5-plus`; only the model changed (qwen3.5-plus → claude-sonnet-4.6). The purpose is to surface which reasoning defects get auto-repaired by a stronger model vs. which residualize.

## Scope

- exp_id: `thinkdepthai-claude-sonnet-4.6`
- Total samples: 500
- Failed cases (judged, correct=false): **51**
- Method: 3-block per-case analysis (what really happened / what agent did / divergence + proximate_cause phrase), full-population labeling, rolling taxonomy every 20 cases.

## Sealing rule (load-bearing)

The following sibling files **MUST NOT be read** by the analyst during per-case analysis or taxonomy derivation:

- `../thinkdepthai-qwen3.5-plus/v2/taxonomy.md`
- `../thinkdepthai-qwen3.5-plus/v2/per_case_analysis.md`
- `../thinkdepthai-qwen3.5-plus/v2/labels.jsonl`
- `../thinkdepthai-qwen3.5-plus/v2/labels_R.jsonl`
- `../claudecode-qwen3.5-plus/**` (not this ablation)

Rationale: the qwen ablation shares framework + prompt with this experiment; reading its R1–R7 during labeling forces force-fit into familiar buckets. Sonnet-4.6 may express a disjoint (or partially disjoint) defect set (e.g., fewer R1 locking errors but new "quantum of doubt" over-caution). These must be allowed to emerge from phrases, not borrowed.

The taxonomy seal is unblocked only at the Phase 7.5 cross-framework merge step (done in a separate session, not here).

## Workflow

1. Export `failed_cases.jsonl` from DB (51 rows).
2. Build one dossier per failed case (GT side + full agent trajectory with think_tool reflections + SQL).
3. Per case, write a 3-block analysis into `per_case_analysis.md`:
   - **What really happened** — grounded in `injection.json` + `causal_graph.json` + `conclusion.csv`.
   - **What agent did** — round-by-round, naming the pivot round where reasoning diverged.
   - **Proximate cause phrase** — 1 short plain-language phrase, no theme names.
4. After every 20 cases, pause and update `taxonomy_working.md`: recluster phrases, merge/split themes.
5. After all 51 cases labeled with phrases, do a final pass to assign `primary` (+ optional `secondary`) theme to each case. Unclassified ≤ 5% target.
6. Freeze `taxonomy_working.md` → `taxonomy.md`, write labels to DB (`meta.failure_analysis.v1.{primary, secondary, pivot_round, proximate_cause}`).

## No LLM labeling

All labels are written by me (Claude, the analyst) reading each dossier. No LLM scripting layer converts free-form trajectories into theme assignments.

## Framework notes (thinkdepthai trajectory structure)

- Tool set: `list_tables_in_directory`, `get_schema`, `query_parquet_files`, `think_tool`.
- SQL lives in `tool_calls[i].function.arguments.query` (structured JSON).
- Reasoning lives in `think_tool` tool-call `arguments.reflection` — not in `assistant.content`.
- Only the final `compress_research` message has substantive `assistant.content`.
- Rounds are flat ReAct loops (no pipeline stages).
