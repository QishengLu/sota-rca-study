# F_candidates.md — thinkdepthai-claude-sonnet-4.6 (v1)

Framework-level (architectural) failure candidates for sonnet. F-classes describe defects that are inherent to the framework's loop structure / commitment mechanism, NOT defects the agent's reasoning could have avoided inside the same framework.

## Single candidate examined

### T6 ExhaustionWithoutCommitment → F1?

v1 taxonomy theme T6: agent oscillates across many candidate RCs across 40+ rounds (burning 2M+ tokens) and commits to a compromise *pair* of services that does not match GT.

**Hypothesis A (architectural F1)**: sonnet's ReAct loop, when the candidate-set is too large, never converges — the framework does not force a commitment, so the model keeps exploring until it blurts out a compromise.

**Hypothesis B (reasoning defect R)**: the ReAct loop CAN commit at 40+ rounds (demonstrated by other long-round cases); the oscillation-to-pair is a reasoning-layer choice, not a framework-imposed outcome.

**Evidence collected (raw.json inspection):**

Hypothesis-breadth measurement: count distinct ts-X service names appearing in root-cause claims across all `think_tool` reflections in each trajectory.

| case | round count | distinct services in RC claims | committed RC count | tag |
|---|---|---|---|---|
| 339 | 49 | 14 | pair (2) | T6 |
| 572 | 39 | 14 | pair (2) | T6 |
| 2682 | 30 | 8 | pair (2) | T6 |
| 2801 | 47 | 9 | pair (2) | T6 |
| 2541 | 62 | 4 | single | T1 |
| 3284 | 58 | 5 | single | T1 |
| 4433 | 70 | 7 | single | T1 |
| 1144 | 23 | 9 | single | T2 |
| 2715 | 23 | 7 | single | T3 |
| 3493 | 26 | 6 | single | T3 |

**Interpretation:**
- T6 cases separate from T1-long cases at comparable or smaller round counts by a ~2x hypothesis-breadth factor (8-14 vs 4-7).
- 2541 at 62 rounds commits to a single RC with only 4 distinct candidates — proves the ReAct loop can and does commit at high round counts when hypothesis space is narrow.
- 2682 at just 30 rounds commits to a compromise pair — proves the pair-output is not triggered by exhaustion thresholds.

**Conclusion**: The framework does not structurally cause the pair-output. The oscillation-to-pair behavior is a reasoning-level choice the model makes when it cannot prioritize among diverse candidates. This is a reasoning defect, classifiable into R.

**Decision: T6 → R (as `R_OscillationToCompromisePair`). No F1 for sonnet.**

## No other F candidates identified

- The remaining 6 R classes (Edge, Leaf, Noise, Narrative, Restart, Silence) all describe reasoning errors observable inside a working ReAct loop, not framework defects.
- Sonnet's ReAct loop does not produce structurally-broken trajectories (no stuck-at-tool, no infinite-regress, no pre-commit cutoff). All 51 trajectories complete with a committed RC and a coherent if-wrong reasoning trail.
- If sonnet had systematic tool-call misuse (e.g., always querying the wrong table for a fault class) it would be F-eligible. No such pattern observed.

## Re-open criteria

Reconsider T6 as F1 if, in cross-framework merge:
- Other frameworks (qwen, claudecode, aiq) also exhibit T6-like oscillation-to-compromise-pair in a structurally-similar way.
- The pair-output is shared across multiple frameworks despite different loop architectures (would hint at a meta-level prompt/format artifact rather than per-model reasoning).
- Hypothesis-breadth metric shows similar 2x separation in multiple frameworks → suggests a universal commitment-threshold defect that could be addressed at harness level.
