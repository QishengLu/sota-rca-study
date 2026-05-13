#!/usr/bin/env bash
# clone_agents.sh — fallback submodule sync.
#
# Use this if `.gitmodules` URLs are filled in and you want to
# (re-)initialize all 6 agent submodules.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if ! grep -q "^\[submodule" .gitmodules 2>/dev/null; then
    cat <<'EOF'
.gitmodules has no active entries.

You need to fork 6 agent repos to your GitHub org first:
  - thinkdepthai: fork LGU-SE-Internal/ThinkDepthAI
  - aiq:          fork (NVIDIA AIRA upstream)
  - taskweaver:   fork microsoft/TaskWeaver
  - openrca:      fork (Fudan OpenRCA upstream)
  - claudecode:   fork (your own ClaudeCode repo)
  - mabc:         fork (mABC EMNLP 2024 upstream)

Then edit .gitmodules to point to your forks, e.g.:
  [submodule "frameworks/thinkdepthai"]
      path = frameworks/thinkdepthai
      url = https://github.com/<your-org>/ThinkDepthAI.git
      branch = main

Finally, run this script again.
EOF
    exit 0
fi

git submodule sync
git submodule update --init --recursive

echo "==> All submodules synced"
git submodule status
