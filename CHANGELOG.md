# Changelog

## [0.1.0] — 2026-05-13 (initial scaffold)

### Added
- WP1: Repository scaffolding (pyproject.toml uv workspace, docker-compose, install.sh, doctor.py)
- WP2: SDK core (`sdk/sota_rca/`): trajectory helpers, model_env, tracker, matrix, manifest, eval pipeline
- WP3: 6 agent submodule placeholders with per-agent ADAPTER_TODO.md (thinkdepthai, aiq, taskweaver, openrca, claudecode, mabc)
- WP4: 65 analysis modules migrated from utu/eval/analysis + RCAgentEval/scripts (n-gram, transitions, markov, intent, failure mode, trajectory viz)
- WP5: FastAPI dashboard backend (4 routes) + React frontend (38 TS/TSX) migrated; utu.* imports rewritten to sota_rca.*
- WP6: scripts/run_matrix.py (asyncio orchestrator) + post_matrix.sh + smoke_test.sh + clone_agents.sh
- WP8: study/analysis/ artifacts (5362 line markdown + parquet) migrated
- 12-model catalog (configs/models/catalog.yaml): sonnet46/opus47/haiku45/gemini31pro/gpt45/gpt4o/o1/qwen36/qwen35/glm51/kimi-k2/deepseek-v3
- Matrix yaml templates: demo, example, full
- Documentation: README, REPRODUCTION, REFERENCE, ARCHITECTURE, ADDING_FRAMEWORK, ADDING_MODEL, TROUBLESHOOTING, SESSIONS

### Known limitations / next sessions
- Per-agent ADAPTER work (writing eval_agent.py + converters.py + entry-point) — deferred to per-agent sessions
- aegis v3 vendored dependency pin commit hash — placeholder; user to fill after they decide which v3 commit to lock
- 6 git submodule URLs — placeholders in .gitmodules; user to fill after forking
- frontend `MatrixView.tsx` and `/api/v1/matrix/{run_id}` endpoint — to add in WP5 follow-up
- Mac M-series PostgreSQL Rosetta verification — pending physical test
