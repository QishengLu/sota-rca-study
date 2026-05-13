# Mac (Apple Silicon) Specific Notes

This repo has been written to work on both **Linux x86_64** and **macOS Apple Silicon (M1/M2/M3)**. Below are the Mac-specific knobs and the gotchas we know about.

## Quick start on Mac

```bash
# Prerequisites: Docker Desktop (with Rosetta enabled for x86 emulation),
# Homebrew, git
brew install node@20 tmux postgresql-client   # postgresql-client just for psql CLI

# Then standard install:
git clone --recurse-submodules <repo>
cd sota-rca-study
cp .env.example .env  # edit API keys
./infra/install.sh    # auto-detects Darwin
```

## PostgreSQL container on Apple Silicon

The `postgres:16-alpine` image has native arm64 builds — should work directly. If you hit `exec format error` or weird crashes:

1. Open Docker Desktop → Settings → General → enable **"Use Rosetta for x86/amd64 emulation on Apple Silicon"**
2. In `infra/docker-compose.yml`, uncomment the `platform: linux/amd64` line under the `postgres` service.

## Claude Code CLI (for `claudecode` framework)

```bash
npm install -g @anthropic-ai/claude-code-cli
claude --version  # verify
```

If `npm` is missing: `brew install node@20` then add to PATH:
```bash
echo 'export PATH="/opt/homebrew/opt/node@20/bin:$PATH"' >> ~/.zshrc
```

## tmux replacement

The original SOTA-agents used tmux + `watch` for orchestration. The new orchestrator (`scripts/run_matrix.py`) uses Python asyncio + rich, so **tmux is not required**. You can still optionally `brew install tmux` if you want to detach long runs.

## Performance note: dataset cache

Cache `~/.cache/sota-rca/ops-lite/` is ~4 GB. APFS handles this fine, but if you're on a Mac with limited free space, you can relocate the cache:

```bash
export HF_HOME=/Volumes/ExternalDrive/hf-cache
# Or override per-command:
uv run sota-rca data download --cache-dir /Volumes/ExternalDrive/ops-lite
```

## uv + Python 3.12

uv pre-built wheels exist for arm64 Mac. If you hit a wheel build error for a transitive dep:

```bash
# Fall back to source build (slower but works):
uv pip install --no-binary=:all: <problem-package>
```

The 6 agent submodules have their own Python version constraints (3.10-3.12). uv handles per-framework venvs automatically.

## Verified configurations

| Mac model | macOS | Python | Notes |
|---|---|---|---|
| M1 / M2 / M3 | 14+ | 3.12 | ✅ Expected to work (untested in CI) |
| Intel Mac | 13+ | 3.12 | ✅ Same as Linux x86_64 |

If you hit issues, please file an issue with output of `uv run python infra/doctor.py`.
