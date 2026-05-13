# Reference — Differences vs aegis v3 upstream

This repo is built on top of [aegis v3 `rcabench-platform`](https://github.com/OperationsPAI/aegis).
The study-specific additions are documented here.

## What we use from aegis v3 (unchanged)

- `BaseAgent` SDK contract (`run(incident, data_dir, **kwargs) -> AgentResult`)
- `Trajectory / AgentTrajectory / Turn / Message / ToolCall / SubAgentCall` schema
- `CausalGraph` data model
- `evaluation/rca_metrics.py` — node / edge / RC F1 computation
- `EvaluationSample` table + `evaluation_rollout_stats` token tracking
- CLI: `rca eval batch`, `rca llm-eval run/judge/stat`
- Setuptools entry-point registration mechanism

## What we add on top (this repo's contribution)

### A. Study analyses (NOT in v3)

| Module | Purpose | Location |
|---|---|---|
| **Step Transition (R→T)** | Round-level evidence utilization 4-class | `sdk/sota_rca/analysis/transitions.py` |
| **N-gram** | 2-5 gram patterns, cross-model heatmap, correct/incorrect comparison | `sdk/sota_rca/analysis/ngram.py` |
| **5-stage Markov** | 19 intent → 5 phase transition matrix | `sdk/sota_rca/analysis/markov.py` |
| **Method 2 Pooled Δ** | Multi-experiment weighted pooling | `sdk/sota_rca/analysis/pooled_delta.py` |
| **Transitions cache** | Offline parquet for dashboard | `sdk/sota_rca/analysis/transitions_cache.py` |
| **19 Intent classification** | LLM-labeled SQL intent | `sdk/sota_rca/analysis/intent_classify.py` |
| **8-dim Radar fingerprint** | cost/multimodal/evidence/depth/focus/phase_coverage/accuracy/baseline | `sdk/sota_rca/analysis/radar.py` |
| **D×R Failure mode** | Failure dossier + verification + taxonomy | `sdk/sota_rca/analysis/failure_tag.py` |
| **Trajectory visualization** | One-stroke HUD HTML | `sdk/sota_rca/analysis/trajectory_viz.py` |

### B. Cost Metrics (extending v3's `EvaluationRolloutStats`)

v3 stores precise `input_tokens / output_tokens / cache_hit_tokens / cache_write_tokens / n_llm_calls`.
We add `actual` vs `estimated` flag + `effective_rounds` via
`AgentResult.metadata['cost_metrics']` JSON (consumed by dashboard).

### C. UsageTracker (multi-provider auto-hook)

`sdk/sota_rca/tracker.py` monkey-patches OpenAI / Anthropic / litellm / Google
SDKs to intercept actual usage. Falls back to character-based estimation when
SDK is bypassed (e.g. some LangChain paths).

### D. Multi-model × multi-framework matrix orchestrator

v3 has `experiments/batch.py` for per-algorithm batching but no leaderboard /
cross-model sweeps. We add:
- `scripts/run_matrix.py` — asyncio cells, AIMD per cell, resume
- `configs/matrix/*.yaml` — declarative matrix configs
- `configs/models/catalog.yaml` — pre-configured 12-model catalog
- `scripts/post_matrix.sh` — auto-judge + analyze + cache refresh

### E. Dashboard (React + FastAPI)

v3 ships only basic HTML + WebSocket. We bring a full React app with:
- Overview page (transitions / markov / ngram / radar / intent heatmap / modality)
- Comparison page (model × model side-by-side)
- Case detail (per-sample trajectory drill-down)
- **MatrixView** — framework × model heatmap (Accuracy / Cost / Radar)

### F. Reproducibility tooling

- `infra/install.sh` — cross-platform (Mac M-series + Linux x86_64)
- `infra/doctor.py` — environment self-check
- `infra/docker-compose.yml` — PostgreSQL with configurable port + multi-arch image
- `.env.example` with 8+ API key slots

## Trajectory schema differences

| Aspect | aegis v3 | sota-rca-study (this repo) |
|---|---|---|
| Agent.run signature | `async run(incident, data_dir, **kwargs)` | **same** |
| Trajectory schema | `Trajectory(agent_trajectories=[AgentTrajectory(turns=[Turn(messages=[...])])])` | **same** |
| Single agent | Flat: 1 `AgentTrajectory` with `turns` | **same** |
| Multi agent | Multiple `AgentTrajectory` linked via `SubAgentCall.id ↔ sub_agent_call_id` | **same** |
| Consumption helpers | None provided | `sdk/sota_rca/data/trajectory.py` — `iter_messages()` / `iter_messages_with_context()` for flat consumers |

## Prompt schema

All 6 agents share one prompt yaml structure, **bit-identical to ThinkDepthAI**:

```
src/<agent_pkg>/prompts/agents/langgraph/rca.yaml
  RCA_ANALYSIS_SP    # system prompt for investigation
  RCA_ANALYSIS_UP    # user prompt for investigation  
  COMPRESS_FINDINGS_SP  # system prompt for synthesis
  COMPRESS_FINDINGS_UP  # user prompt for synthesis
```

Placeholders: `{date}` `{incident_description}` `{agent_contract}` (latter
injected from `rcabench_platform.v3.sdk.evaluation.v2.get_agent_contract_prompt()`).

## Environment contract

`UTU_LLM_{TYPE,MODEL,BASE_URL,API_KEY}` is the canonical model configuration
contract (inherited from ThinkDepthAI). All 6 agents read these env vars; the
orchestrator writes them per-cell based on `configs/models/catalog.yaml` alias.

Legacy `OPENAI_*` / `ANTHROPIC_*` / `GOOGLE_*` env vars are written as compatibility
shims by the orchestrator, but no agent code should read them directly.
