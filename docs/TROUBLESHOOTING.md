# Troubleshooting

## Install issues

### `uv: command not found`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

### `docker compose` not recognized (old syntax)

You're on legacy docker-compose. Either upgrade Docker or use:
```bash
docker-compose -f infra/docker-compose.yml up -d
```

### Apple Silicon: PostgreSQL container fails to start

The default `postgres:16-alpine` image has arm64 builds, but if you hit `exec format error`, force amd64 + Rosetta:

Edit `infra/docker-compose.yml`:
```yaml
services:
  postgres:
    platform: linux/amd64   # uncomment
    image: postgres:16-alpine
```

Then in Docker Desktop → Settings → General, ensure "Use Rosetta for x86/amd64 emulation on Apple Silicon" is enabled.

## Runtime issues

### `UTU_LLM_API_KEY not set`

Edit `.env`:
```
UTU_LLM_API_KEY=sk-xxx
UTU_LLM_BASE_URL=https://api.your-provider.com/v1
UTU_LLM_MODEL=claude-sonnet-4-6
```

Or, if using the matrix orchestrator, set the per-provider key (e.g. `SHUBIAOBIAO_API_KEY`) instead. The orchestrator writes `UTU_LLM_*` per cell.

### `Trajectory not appearing in dashboard`

Check stages:
```bash
psql "$UTU_DB_URL" -c "SELECT exp_id, stage, COUNT(*) FROM evaluation_data GROUP BY 1,2;"
```

- `init` only → rollout didn't run
- `rollout` only → judge didn't run; run `bash scripts/post_matrix.sh <run_id>`
- `judged` but dashboard empty → cache stale; `curl -X POST http://localhost:8001/api/v1/analysis/refresh`

### Tool calls hitting rate limit

Reduce concurrency in matrix yaml:
```yaml
execution:
  cell_concurrency: 1
  rollout_concurrency_max: 2
```

### claudecode framework: `claude: command not found`

```bash
npm install -g @anthropic-ai/claude-code-cli@latest
```

If npm is missing:
- Mac: `brew install node@20`
- Linux: `nvm install 20`

### Dataset download stuck / slow

Use HuggingFace mirror (China):
```
HF_ENDPOINT=https://hf-mirror.com uv run sota-rca data download --dataset ops-lite
```

### Out of memory on dashboard cache rebuild

The full cache is ~ 700 MB. Either:
- Use demo mode: `--mode demo`
- Build cache lazily: skip `auto_refresh_cache: true` in matrix post

## Submodule issues

### Submodule URL is wrong

Edit `.gitmodules`, then:
```bash
git submodule sync
git submodule update --init --recursive
```

### Submodule is empty after clone

You forgot `--recurse-submodules`. Fix:
```bash
git submodule update --init --recursive
```

### `frameworks/<name>/` is not a submodule yet (initial state)

Some frameworks may be local placeholders until you fork the upstream. See `docs/ADDING_FRAMEWORK.md` for migration steps.
