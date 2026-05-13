# Changelog

## [0.1.0] — 2026-05-13 (initial scaffold + WP completion)

### Added — Repository (WP1)
- pyproject.toml uv workspace
- infra/{install.sh (Mac+Linux), docker-compose.yml (multi-arch), doctor.py, .env.example}
- README, REPRODUCTION, REFERENCE, CHANGELOG, LICENSE
- docs/{ARCHITECTURE, ADDING_FRAMEWORK, ADDING_MODEL, TROUBLESHOOTING, SESSIONS, MAC_NOTES}
- 12-model catalog (configs/models/catalog.yaml)
- 3 matrix yaml templates: demo, example, full

### Added — SDK Core (WP2)
- `sota_rca/data/trajectory.py` — v3 Trajectory helpers (iter_messages, wrap_openai_flat_to_v3, multi-agent walk)
- `sota_rca/data/converters.py` — universal OpenAI-flat → v3 Trajectory (single + multi-agent)
- `sota_rca/data/ops_lite.py` — HF dataset loader with sha256 verify
- `sota_rca/data/incident_synth.py` — manifest fields → free-text incident_description
- `sota_rca/tracker.py` — UsageTracker with auto_install() multi-provider
- `sota_rca/model_env.py` — UTU_LLM_* env contract + provider shims
- `sota_rca/matrix.py` + `manifest.py` — matrix config loader and run tracking
- `sota_rca/legacy_agent.py` — LegacySubprocessAgent (aegis v3 BaseAgent wrapper)
- `sota_rca/framework_base.py` — common helpers
- `sota_rca/prompts/{manager.py, rca.yaml}` — canonical 4-key prompt (bit-identical to ThinkDepthAI)
- `sota_rca/eval/{preprocess, rejudge, difficulty, rca_metrics_fallback}.py`
- `sota_rca/cli.py` — `sota-rca` CLI entry point
- `sota_rca/runner/{runner, db_writer, _fallback_db}.py` (from RolloutRunner)

### Added — 6 Agent Mirrors (WP3)
For each of `thinkdepthai`, `aiq`, `taskweaver`, `openrca`, `claudecode`, `mabc`:
- `frameworks/<name>/src/<pkg>/prompts/agents/langgraph/rca.yaml` — bit-identical to ThinkDepthAI
- `frameworks/<name>/src/<pkg>/prompts/manager.py`
- `frameworks/<name>/src/<pkg>/agents/eval_agent.py` — aegis v3 BaseAgent subclass via LegacySubprocessAgent
- `frameworks/<name>/pyproject_sota_rca.toml` — entry-point snippet
- `frameworks/<name>/ADAPTER_TODO.md` — per-agent migration guide
- 6 entry-points registered in root pyproject.toml
- Old `/home/nn/SOTA-agents/RolloutRunner` UsageTracker hooks in agent_runner.py replaced with `from sota_rca.tracker import auto_install`

### Added — mabc Data Adapter (WP3.6)
- `frameworks/mabc/data_adapter.py` — ops-lite parquet → mabc JSON layout
- `frameworks/mabc/DATA_ADAPTER.md` — usage docs
- Handles both lowercase ops-lite OTel schema and legacy PascalCase

### Added — Analysis Modules (WP4)
- 65 analysis modules migrated from utu/eval/analysis + RCAgentEval/scripts
- All `utu.*` imports rewritten to `sota_rca.*` via bulk sed
- Core modules: ngram, transitions (R→T 4-class), markov (5-stage), pooled_delta, transitions_cache, intent_classify, radar
- Failure mode: 36-file `failure_analysis/` ecosystem (build_dossiers, verify_adjudicate, label_*, pd_*, etc.)
- Trajectory visualization (viz_trajectory.py)
- Middleware compare scripts (with `Path.home()` instead of `/home/nn` font path)
- SQL pattern mining scripts

### Added — Dashboard (WP5)
- FastAPI backend with all original routes preserved + new `/api/v1/matrix/{run_id}` endpoint
- React frontend (39 TS/TSX files) + new `MatrixView.tsx` (framework × model heatmap)
- `App.tsx` routing extended with `/matrix` and `/matrix/:runId`
- `analysis_cache.json` + `demo_cache.json` preserved

### Added — Orchestrator (WP6)
- `scripts/run_matrix.py` — asyncio cells + AIMD inside each cell
- `scripts/post_matrix.sh` — judge + intent + cache refresh pipeline
- `scripts/smoke_test.sh` — single-case end-to-end verification
- `scripts/clone_agents.sh` — submodule sync helper

### Added — Study Artifacts (WP8)
- `study/analysis/` — 153MB of methodology / trajectories / failure-modes / middleware / reports / planning

### Tests
- 2 test files: `test_smoke_imports.py`, `test_trajectory.py` (17 tests, all passing)
- 2 mock fixtures: single-agent + multi-agent v3 Trajectory examples

### Fixed
- `datetime.UTC` → `timezone.utc` (Python 3.10 compat)
- `load_catalog()` default path bug (used `parent.parent.parent.parent` instead of `parents[2]`)
- Same path bug in 3 places in cli.py
- 6 agent_runner.py: replaced hardcoded `/home/nn/SOTA-agents/RolloutRunner` tracker imports with `sota_rca.tracker.auto_install`

### Known limitations
- `.gitmodules` URLs are placeholders (user must fork 6 agent repos)
- aegis v3 commit pin not yet set (placeholder in pyproject.toml)
- Mac M-series physical verification pending
- Per-agent ADAPTER_TODO refinement (specifically: framework-internal `base_url` hardcoded replacements) — partial; main tracker hook done, agent-specific quirks remain in each `agent_runner.py`
