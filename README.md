# sota-rca-study

> Reproducibility artifact for a study on Root Cause Analysis (RCA) agents.
> Evaluates **6 RCA agent frameworks × multiple base models** on the
> [`anon-ops/ops-lite`](https://huggingface.co/datasets/anon-ops/ops-lite) microservices
> incident dataset. Built on top of [aegis v3
> (`rcabench-platform`)](https://github.com/OperationsPAI/aegis).

---

## Quick Start — 8 steps to a demo dashboard (≤ 30 min, < $1)

```bash
# 1. Clone (with submodules)
git clone --recurse-submodules <repo-url> sota-rca-study && cd sota-rca-study

# 2. Configure API keys
cp .env.example .env  # fill in at least ONE provider key (SHUBIAOBIAO_API_KEY etc.)

# 3. Cross-platform install (auto-detects Mac/Linux)
./infra/install.sh

# 4. Start PostgreSQL + download dataset
docker compose -f infra/docker-compose.yml up -d
uv run sota-rca data download --dataset ops-lite

# 5. Run demo matrix experiment (2 frameworks × 2 models × 20 samples ≈ $0.6 / 12 min)
uv run python scripts/run_matrix.py configs/matrix/demo.yaml

# 6. Post-process: judge + intent classify + cache refresh
bash scripts/post_matrix.sh $(cat results/matrix/LATEST)

# 7. Launch dashboard
uv run sota-rca dashboard --mode demo --port 8001 &

# 8. Open in browser
open http://localhost:8001/?view=matrix
```

---

## What's inside

| Layer | Component | Description |
|---|---|---|
| **Framework base** | `rcabench-platform v3` (vendored) | Agent SDK, CausalGraph schema, evaluation metrics, CLI |
| **6 RCA agents** (submodules) | `thinkdepthai`, `aiq`, `taskweaver`, `openrca`, `claudecode`, `mabc` | Each mirrors ThinkDepthAI template: prompt yaml + eval_agent + trajectory converter + entry-point |
| **Study SDK** (`sdk/sota_rca/`) | Behavior transition, N-gram, Markov, Radar, Failure mode, Cost metrics | Self-developed analyses on top of v3 Trajectory |
| **Dashboard** (`dashboard/`) | FastAPI backend + React frontend | Horizontal model × framework comparison, drill-down to single cases |
| **Matrix orchestrator** (`scripts/run_matrix.py`) | asyncio cells + AIMD concurrency | One YAML → N×M cells, resume-able, failure-tolerant |

### Supported base models (12 pre-configured, `configs/models/catalog.yaml`)

`claude-sonnet-4-6` · `claude-opus-4-7` · `claude-haiku-4-5` · `gemini-3.1-pro` ·
`gpt-4.5` · `gpt-4o` · `o1` · `qwen3.6-plus` · `qwen3.5-plus` · `glm-5.1` ·
`kimi-k2` · `deepseek-v3`

Add a new model = append one entry to `catalog.yaml`. No code changes.

### Supported frameworks (6 agents)

| Framework | Paradigm | Trajectory shape |
|---|---|---|
| **thinkdepthai** | LangGraph single-agent ReAct (3 nodes) | flat |
| **aiq** | NVIDIA AIRA 5-stage pipeline | flat |
| **taskweaver** | Microsoft TaskWeaver (Planner + CodeInterpreter) | flat (custom converter) |
| **openrca** | Custom dual-layer (Controller + Executor) | flat (custom converter) |
| **claudecode** | Claude Code CLI subprocess (stream-json) | flat (custom converter) |
| **mabc** | Multi-agent voting (ProcessScheduler + 6 experts) | **nested** (SubAgentCall) |

Add a new framework: write a 30-line adapter following `docs/ADDING_FRAMEWORK.md`.

---

## Documentation

- [REPRODUCTION.md](REPRODUCTION.md) — Full reproduction runbook (Mac + Linux, demo + full)
- [REFERENCE.md](REFERENCE.md) — Differences vs aegis v3 upstream
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Three-layer architecture
- [docs/ADDING_FRAMEWORK.md](docs/ADDING_FRAMEWORK.md) — Add a new RCA agent
- [docs/ADDING_MODEL.md](docs/ADDING_MODEL.md) — Add a new LLM provider
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — Common issues
- [docs/SESSIONS.md](docs/SESSIONS.md) — Multi-session parallel work log

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Citation

```bibtex
@misc{sota-rca-study-2026,
  title = {RCA Agent Comparative Study: Framework × Model Matrix on ops-lite},
  author = {sota-rca-study contributors},
  year = {2026},
  url = {https://github.com/<org>/sota-rca-study}
}
```
