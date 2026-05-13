# Reproduction Runbook

Step-by-step guide to reproduce all results from this study.

## Prerequisites

| Tool | Version | Mac install | Linux install |
|---|---|---|---|
| uv | ≥ 0.4 | `brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Docker | ≥ 24 | Docker Desktop | `sudo apt install docker.io docker-compose-plugin` |
| Node | ≥ 18 (only for dashboard) | `brew install node@20` or nvm | `nvm install 20` |
| Claude Code CLI | latest (only for claudecode framework) | `npm install -g @anthropic-ai/claude-code-cli` | same |
| git | ≥ 2.30 | preinstalled | `sudo apt install git` |

**API keys (you need at least 1)** — get from any LLM provider:
- Anthropic / shubiaobiao / Aliyun / OpenAI / Google / Moonshot / ZhipuAI / DeepSeek

## Step-by-step

### 1. Clone with submodules

```bash
git clone --recurse-submodules https://github.com/<org>/sota-rca-study
cd sota-rca-study
```

If you forgot `--recurse-submodules`:
```bash
git submodule update --init --recursive
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env: fill in at least one provider's API key + base URL if needed
```

### 3. Install

```bash
./infra/install.sh
# Auto-installs uv, syncs Python deps, starts PostgreSQL, runs doctor.py
```

### 4. Download dataset (4.13 GB)

```bash
uv run sota-rca data download --dataset ops-lite
# Cached to ~/.cache/sota-rca/ops-lite
# Auto-verifies sha256
```

### 5. Choose a recipe

**Recipe A — Demo (≤ 15 min, ≤ $1)**:
```bash
uv run python scripts/run_matrix.py configs/matrix/demo.yaml
bash scripts/post_matrix.sh $(cat results/matrix/LATEST)
uv run sota-rca dashboard --mode demo --port 8001 &
open http://localhost:8001/?view=matrix
```

**Recipe B — Full reproduction (~ 5 h, ~ $30)**:
```bash
uv run python scripts/run_matrix.py configs/matrix/full.yaml
bash scripts/post_matrix.sh $(cat results/matrix/LATEST)
uv run sota-rca dashboard --mode prod --port 8001 &
open http://localhost:8001/
```

**Recipe C — Custom experiment** (e.g. only thinkdepthai with 3 models):
```bash
# Edit configs/matrix/example.yaml — pick frameworks + models + subset
uv run python scripts/run_matrix.py configs/matrix/example.yaml
```

### 6. Resume an interrupted run

The orchestrator auto-resumes. Just re-run the same command. Samples with
`stage='judged'` are skipped, in-flight samples re-enter the queue.

### 7. Inspect results

```bash
# PostgreSQL
psql "$UTU_DB_URL" -c "
  SELECT exp_id, COUNT(*),
         SUM((correct)::int) AS n_correct,
         ROUND(AVG((correct)::int) * 100, 1) AS ac_at_1
  FROM evaluation_data WHERE stage = 'judged'
  GROUP BY exp_id ORDER BY ac_at_1 DESC;
"

# Or visit dashboard MatrixView
```

## Expected outcomes

For Recipe B (full):
- ~ 3000 evaluated samples (6 frameworks × 1 model × 500 each)
- AC@1 range: 30%-90% depending on framework × model combo
- Wall time: 3-6 hours
- Cost: $20-40 depending on model mix

Compare with `study/analysis/` reports — your dashboard's numbers should be within ±5% of the
frozen baseline numbers in `analysis/3-failure-modes/`.

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).
