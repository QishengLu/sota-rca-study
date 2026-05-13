#!/usr/bin/env bash
# ============================================================
# sota-rca-study one-shot installer
# Detects macOS (Darwin) / Linux, installs uv, pulls deps,
# downloads dataset placeholder, runs doctor check.
# ============================================================
set -euo pipefail

OS=$(uname -s)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cyan() { printf "\033[36m%s\033[0m\n" "$1"; }
green() { printf "\033[32m%s\033[0m\n" "$1"; }
red() { printf "\033[31m%s\033[0m\n" "$1"; }
yellow() { printf "\033[33m%s\033[0m\n" "$1"; }

cyan "==> sota-rca-study installer ($OS)"
cyan "    repo: $REPO_DIR"

# ---------- 1. Check / install uv ----------
if ! command -v uv >/dev/null 2>&1; then
    yellow "uv not found, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
green "uv $(uv --version)"

# ---------- 2. Check Python 3.12+ ----------
PY_VER=$(uv python find 3.12 2>/dev/null || echo "")
if [[ -z "$PY_VER" ]]; then
    yellow "Python 3.12 not found locally, uv will install..."
    uv python install 3.12
fi
green "Python: $(uv python find 3.12)"

# ---------- 3. Check Docker ----------
if ! command -v docker >/dev/null 2>&1; then
    red "docker not found"
    if [[ "$OS" == "Darwin" ]]; then
        yellow "Install Docker Desktop: https://www.docker.com/products/docker-desktop"
    else
        yellow "Install docker: https://docs.docker.com/engine/install/"
    fi
    exit 1
fi
green "docker $(docker --version | head -1)"

# ---------- 4. Check Node (for dashboard frontend) ----------
if ! command -v node >/dev/null 2>&1; then
    yellow "node not found (required for dashboard frontend)"
    if [[ "$OS" == "Darwin" ]]; then
        yellow "Install: brew install node@20  OR  nvm install 20"
    else
        yellow "Install: nvm install 20  OR  https://nodejs.org/en/download"
    fi
fi
green "node $(node --version 2>/dev/null || echo 'NOT INSTALLED')"

# ---------- 5. Sync Python deps ----------
cyan "==> uv sync (Python deps)"
cd "$REPO_DIR"
uv sync --all-extras

# ---------- 6. Submodule init (if .gitmodules has real URLs) ----------
if grep -q "^\[submodule" "$REPO_DIR/.gitmodules" 2>/dev/null; then
    cyan "==> Initializing submodules"
    git submodule update --init --recursive
else
    yellow "No active submodules in .gitmodules. Frameworks are local placeholders."
    yellow "After forking, edit .gitmodules and run: git submodule update --init"
fi

# ---------- 7. .env handling ----------
if [[ ! -f "$REPO_DIR/.env" ]]; then
    cyan "==> Creating .env from .env.example"
    cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
    yellow "    Edit .env to set API keys before running matrix experiments."
fi

# ---------- 8. PostgreSQL via docker compose ----------
cyan "==> Starting PostgreSQL (docker compose)"
docker compose -f "$REPO_DIR/infra/docker-compose.yml" up -d
sleep 3
docker exec sota-rca-pg pg_isready -U postgres >/dev/null 2>&1 && green "PG ready on localhost:${POSTGRES_PORT:-5433}" || red "PG not ready"

# ---------- 9. Claude Code CLI (optional, for claudecode framework) ----------
if ! command -v claude >/dev/null 2>&1; then
    yellow "Claude Code CLI not found (optional, only for 'claudecode' framework)"
    yellow "Install: npm install -g @anthropic-ai/claude-code-cli@latest"
fi

# ---------- 10. doctor check ----------
cyan "==> Running doctor.py"
uv run python "$REPO_DIR/infra/doctor.py" || yellow "doctor.py reported issues — review and fix"

green "==> Installation complete."
cat <<'TIPS'

Next steps:
  1. Edit .env to set API keys (at least one provider's key)
  2. Fork 6 agent repos and update .gitmodules with your URLs
  3. Run demo matrix:
       uv run python scripts/run_matrix.py configs/matrix/demo.yaml
  4. Open dashboard:
       uv run sota-rca dashboard --mode demo --port 8001
       open http://localhost:8001/?view=matrix

TIPS
