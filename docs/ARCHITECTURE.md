# Architecture

## Three-layer design

```
┌─────────────────────────────────────────────────────────────┐
│                    sota_rca SDK (this repo)                  │
│   matrix · runner · analysis · eval · prompts · dashboard    │
└─────────────────────────┬───────────────────────────────────┘
                          │ depends on
                          ▼
┌─────────────────────────────────────────────────────────────┐
│             aegis v3 (rcabench_platform, pinned)             │
│   BaseAgent · CausalGraph · rca_metrics · datasets · CLI     │
└─────────────────────────┬───────────────────────────────────┘
                          │ registers via entry-point
                          ▼
┌─────────────────────────────────────────────────────────────┐
│         frameworks/<name>/ × 6 (RCA agent submodules)        │
│   thinkdepthai · aiq · taskweaver · openrca · claudecode · mabc │
└─────────────────────────────────────────────────────────────┘
```

## Data flow

```
ops-lite (HF dataset)
  ↓ load
  manifest.jsonl + cases/{name}/{*.parquet, injection.json, ...}
  ↓ preprocess
  EvaluationSample(stage='init', exp_id, dataset_index)
  ↓ rollout (Agent.run per sample)
  EvaluationSample(stage='rollout', trajectories: Trajectory.to_json(), response)
  ↓ judge (rca_metrics)
  EvaluationSample(stage='judged', meta.graph_metrics.primary, correct)
  ↓ post-analysis
  meta.llm_intents · meta.failure_analysis · meta.cost_metrics
  ↓ dashboard cache
  analysis_cache.json (or demo_cache.json)
  ↓ React frontend
  Overview · MatrixView · CaseDetail
```

## Matrix experiment flow

```
configs/matrix/<file>.yaml + configs/models/catalog.yaml
  ↓ run_matrix.py
  expand cells: [(framework, model, subset)]
  ↓ asyncio.Semaphore(cell_concurrency)
  for each cell:
    ↓ build env: UTU_LLM_MODEL/BASE_URL/API_KEY + shim
    ↓ subprocess (uv run -m <framework>.agents.eval_agent)
    ↓ AIMD adaptive concurrency (slow-start 1 → up to N)
    write to PG evaluation_data(exp_id=...)
  ↓ post_matrix.sh
  rejudge + intent + transitions + cache refresh
  ↓ dashboard
```

## Key invariants

1. **Single Trajectory schema** — all 6 agents output the same `Trajectory(agent_trajectories=[...])` object; downstream analysis code is framework-agnostic.
2. **No hardcoded base_url / model_name in agent code** — UTU_LLM_* env is the single source of truth.
3. **DB schema follows aegis v3** — no custom tables; we extend via `meta` JSONB.
4. **Prompt is bit-identical across agents** — mirrors ThinkDepthAI's `rca.yaml`.
5. **Tools are the only thing that varies** — each framework keeps its native tool implementation (DuckDB / IPython / Bash) but exposes the same logical operations (list_tables / get_schema / query / think).
