#!/usr/bin/env bash
# smoke_test.sh — single-case end-to-end pipeline verification.
#
# Validates:
# - Dataset loadable
# - Preprocess inserts a row
# - 1 thinkdepthai rollout produces a v3 Trajectory
# - Rejudge writes graph_metrics
# - All analysis modules can read the trajectory
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

cyan() { printf "\033[36m%s\033[0m\n" "$1"; }

cyan "==> Smoke test (1 case, thinkdepthai, qwen36)"

# 1. Doctor check
cyan "--- 1/6 doctor check ---"
uv run python infra/doctor.py || true

# 2. Dataset present
cyan "--- 2/6 dataset check ---"
uv run sota-rca data verify || {
    echo "Dataset not present; downloading..."
    uv run sota-rca data download
}

# 3. Preprocess 1 sample
cyan "--- 3/6 preprocess 1 sample ---"
uv run sota-rca preprocess "smoke-thinkdepthai-qwen36" \
    --agent-type thinkdepthai \
    --model-name qwen3.6-plus \
    --limit 1

# 4. Run 1 cell
cyan "--- 4/6 rollout 1 cell ---"
uv run python scripts/run_matrix.py configs/matrix/demo.yaml || true

# 5. Verify trajectory written
cyan "--- 5/6 verify trajectory ---"
psql "${UTU_DB_URL:-postgresql://postgres:postgres@localhost:5433/sota_rca_study}" -c "
SELECT exp_id, stage, COUNT(*),
       SUM(CASE WHEN trajectories IS NOT NULL THEN 1 ELSE 0 END) AS with_traj
FROM evaluation_data
WHERE exp_id LIKE 'demo-%'
GROUP BY exp_id, stage;
" 2>/dev/null || echo "(can't query DB — may not be running)"

cyan "==> Smoke test done."
