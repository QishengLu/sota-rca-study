# Multi-Session Work Log

For parallel development across multiple Claude Code sessions.

## Work Packages (WP) and ownership

| WP | Owner | Status | Blocker |
|---|---|---|---|
| WP1 — Scaffolding | Session A | ✅ Done | — |
| WP2 — SDK Core | Session A | 🚧 In progress | — |
| WP3.1 — thinkdepthai integration | Session A | 🚧 In progress | — |
| WP3.2 — aiq mirror | Session B | ⏳ Pending | WP2 done |
| WP3.3 — taskweaver mirror | Session B | ⏳ Pending | WP2 done |
| WP3.4 — openrca mirror | Session C | ⏳ Pending | WP2 done |
| WP3.5 — claudecode mirror | Session C | ⏳ Pending | WP2 done |
| WP3.6 — mabc mirror + dataset adapt | Session D | ⏳ Pending | WP2 done |
| WP4a — Behavior transitions (5件套) | Session E | ⏳ Pending | WP2 + mock_trajectory fixture |
| WP4b — Other analysis | Session E | ⏳ Pending | WP4a |
| WP5 — Dashboard | Session F | ⏳ Pending | WP2 + mock fixture |
| WP6 — Matrix orchestrator | Session A | ⏳ Pending | WP2 |
| WP7 — Cross-platform verify | Session A | ⏳ Pending | All WP3-6 |
| WP8 — Study artifact migration | Session F | ⏳ Pending | WP1 |
| WP9 — Release | Session A | ⏳ Pending | WP7 |

## Coordination rules

1. Each session works on its own feature branch: `wp-N-<owner>`
2. PR to `main` when WP done
3. Append a 5-line progress entry below for each session-day
4. Mock fixture (`tests/fixtures/mock_trajectory.json`) is the contract: don't break it without coordinating

## Progress log

### Session A — Day 0 (initial scaffolding)

- WP1 done: pyproject, docker-compose, install.sh, doctor.py, README/REPRODUCTION/REFERENCE, docs/*, configs/models + matrix
- WP2 starting: trajectory helpers, ops-lite loader, UsageTracker, model_env
