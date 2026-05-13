#!/usr/bin/env bash
# post_matrix.sh — judge + analyze + cache refresh after a matrix run.
#
# Usage:
#   bash scripts/post_matrix.sh <run_id>
#
# Expects:
#   - results/matrix/<run_id>/manifest.json exists
#   - PostgreSQL is running with samples in stage='rollout' for each exp_id
set -euo pipefail

RUN_ID="${1:-}"
if [[ -z "$RUN_ID" ]]; then
    echo "Usage: $0 <run_id>"
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$REPO_ROOT/results/matrix/$RUN_ID/manifest.json"

if [[ ! -f "$MANIFEST" ]]; then
    echo "Manifest not found: $MANIFEST"
    exit 1
fi

# Extract all exp_ids from manifest
EXP_IDS=$(python3 -c "
import json, sys
with open('$MANIFEST') as f:
    m = json.load(f)
for c in m.get('cells', []):
    if c.get('status') in ('done', 'partial_ok'):
        print(c['exp_id'])
")

echo "==> Post-matrix pipeline for run_id=$RUN_ID"
echo "    Exp IDs to process: $(echo "$EXP_IDS" | wc -l)"

cd "$REPO_ROOT"

# 1. Rejudge each exp_id (idempotent — only re-judges stage='rollout' samples)
echo "==> Step 1/4: rejudge"
for eid in $EXP_IDS; do
    echo "  rejudge $eid"
    uv run sota-rca rejudge "$eid" || echo "    (rejudge failed for $eid, continuing)"
done

# 2. Intent classification (LLM-based, requires UTU_LLM_* env)
echo "==> Step 2/4: intent classify"
for eid in $EXP_IDS; do
    echo "  classify $eid"
    uv run python -m sota_rca.analysis.scripts.classify_intents --exp_id "$eid" 2>/dev/null \
        || echo "    (intent classify skipped/failed for $eid)"
done

# 3. Refresh dashboard cache (matrix-aware)
echo "==> Step 3/4: refresh dashboard cache"
PORT="${DASHBOARD_PORT:-8001}"
if curl -fsS "http://localhost:$PORT/api/v1/health" >/dev/null 2>&1; then
    curl -fsS -X POST "http://localhost:$PORT/api/v1/analysis/refresh" -d "{\"run_id\":\"$RUN_ID\"}" || true
else
    echo "    Dashboard not running on $PORT; cache will rebuild on next launch"
fi

# 4. Print summary URL
echo "==> Done."
echo "    View results: http://localhost:$PORT/?run_id=$RUN_ID&view=matrix"
echo "    Manifest:     $MANIFEST"
