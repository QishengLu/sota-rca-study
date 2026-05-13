# PD_induction_log.md — claudecode-qwen3.5-plus

Process-defect (PD) induction log for Phase PD-B.

## Triangulation sources

- (i) `labels.jsonl.proximate_cause` + `primary`/`secondary` theme  
- (ii) `per_case_analysis.md` Divergence block  
- (iii) `dossiers/case_<id>.md` Part B trajectory (SQL + intent list)  
- (iv) Postgres `meta.llm_intents.final` — 19-category intent sequence  

## Fallback cases

- **case_1837**: spec flagged as potentially needing `claude_opus_4_6` fallback. **Verified**: `meta.llm_intents.final` is populated (58 intents). No fallback needed. All 103 cases used `final` intents from PostgreSQL.

## Triangulation inconsistencies

None material. For all 103 cases, the three evidence sources agree on which actions were taken vs missed. Two light disagreements:

- **case_4463 (T8_DatasetMismatch)**: GT declares ts-config-service but injection_name is `ts-food-service-container-kill`. Labels primary = T8_DatasetMismatch (R-axis). The agent did probe ts-food-service by name; the failure is not a PD but a dataset mis-labeling. PD1 and PD2 still mechanically fire (no contrast; PodChaos missing k8s_state yes — agent did call k8s_state, so PD2 does not fire here).
- **case_3035 (T5_JVMMisreadAsDB)**: per_case_analysis says agent probed food-service by name (gt_probed=10). Triangulation consistent — agent did probe, PD4 correctly does not fire.

## Empty-PD cases

Cases with no PD firing (0 cases): none

These cases failed via pure R/D mechanisms (e.g., agent did all the process-correct things — baseline_contrast, fault-layer drill, call_tree_build, targeted WHERE probe — yet still reasoned to a wrong conclusion). Their R/D labels carry the full explanatory load.

## Rejected candidate PD classes

All rejections are logged with the 2-question discriminator that triggered them.

### Reject-1: "RunawayRoundsPastPivot" (>60 rounds continued)

- Intended meaning: agent ran 60+ rounds without converging.
- **Q2 test (data state?)**: Round count is not a defect per se — some cases need long investigations. The real defect is "kept issuing same-intent queries after pivot_round without plan change", which is harder to boolean-detect. Merging the productive aspect into PD3_TriageLoopWithoutDrill (which captures "kept surveying") yields a cleaner class.
- **Decision**: **Reject as standalone class.** Runaway length is a symptom, not the underlying process defect.
- Evidence: 43 cases have total_rounds > 60; 35 of those are already captured by PD3.

### Reject-2: "ExcessiveBaselineCollectLoop" (>15 baseline_collect calls)

- Intended meaning: agent looped on baseline_collect 15+ times without advancing.
- **Q1 test**: clean, action-based.
- **Q2 test**: clean, predicate on intent counts.
- Why still reject? **Subset of PD1_BaselineCollectedNotContrasted**. Of 11 cases with >15 baseline_collect and zero contrast, all 11 are already in PD1's 78 cases. Creating a "severe" sub-class for the same mechanism violates MECE at class-definition level (it would split by severity, not by defect type).
- **Decision**: **Reject as standalone class.** Absorbed into PD1 variant note.

### Reject-3: "SubagentSpawnWithoutFollow-up" (framework-specific to Claude Code)

- Intended meaning: agent spawned Task subagent but didn't fold its output into next-round planning.
- **Density check**: **zero** cases use Task/subagent spawns in this dataset. Claude Code CLI with qwen3.5-plus issues native Bash-only steps. Framework does not actually use the Task tool in these 103 failed trajectories.
- **Decision**: **Reject for zero density.** Not a PD that applies to this framework run.

### Reject-4: "ExplicitGTDismissal" (tagged GT as HEALTHY in final JSON)

- Intended meaning: agent explicitly marks the GT service as HEALTHY in the final answer node list.
- **Q1 test**: Borderline. "Explicit dismissal" uses "dismissed" which is a reasoning verb. This crosses into R-territory (agent interpreted a state as health).
- **Density check**: only 1 case (2489) has the GT labeled HEALTHY in final JSON. Density <3, below threshold.
- **Decision**: **Reject.** Q1 fails (reasoning verb) and density fails. Belongs to R-axis or noise.

### Reject-5: "SchemaDiscoveryOverlongOpening" (>8 rounds on schema)

- Intended meaning: agent spent >8 rounds on DESCRIBE/schema queries before any data probe.
- **Q1 test**: clean.
- **Q2 test**: clean.
- Why reject? **Schema discovery is explicitly instructed in the system prompt**. Long schema phases are protocol-compliant, not defective. Median is 4-6 rounds; outliers at 8+ rounds exist but follow-through behavior (whether they ever left schema mode) correlates more with PD3 than with a distinct PD.
- **Decision**: **Reject.** Not a defect (instructed behavior).

## MECE enforcement

- **Class definitions are MECE**: every PD is a predicate over disjoint intent/action patterns. No class definition is a rephrasing of another.
- **Cases are NOT MECE across classes**: a single case can fire PD1 + PD2 + PD4 + PD6 simultaneously. This is expected per the spec ("A case can have 0..N PDs").
- **Overlap analysis (pairwise)** — max observed = PD1 ∩ PD6 at 77% of min. Not a violation; they describe distinct actions (baseline-phase completion vs trace-depth exploration).

## Class density check

All 6 classes have ≥ 3 canonical cases in Members list:

| Class | Members count |
|-------|---------------|
| PD1_BaselineCollectedNotContrasted | 78 |
| PD4_GTServiceNotTargetedWithWhere | 63 |
| PD2_FaultLayerMetricProbeSkipped | 45 |
| PD6_CallTreeAbsentOrShallow | 43 |
| PD3_TriageLoopWithoutDrill | 35 |
| PD5_FinalRCNotGroundedByProbe | 13 |

## Framework-specific scope

All 6 PDs are `scope=core` — the intents and SQL-filter predicates they rely on are framework-agnostic (any agent using the 19-category intent vocabulary + SQL over parquet has these same observable behaviors). We considered two framework-specific candidates:

- **SubagentSpawnWithoutFollow-up** — rejected (zero density; claudecode-qwen3.5-plus in this run never spawned Task subagents).
- **CodingPlanTruncatedBeforeWhereClause** — considered but not induced; evidence was the same as PD4 (concluded without targeted probe). The coding-plan truncation is the cause of PD4, not a separate PD.

No framework-specific PDs in the final taxonomy.

## Self-reflection on weakest PDs

### Weakest: PD3_TriageLoopWithoutDrill

- **Why weak**: Hard-coded thresholds (`n_triage >= 15` AND `n_metric_drill <= 3`) are calibrated to this dataset's round-length distribution. Different agents with shorter trajectories would need adjusted thresholds.
- **Co-occurrence with PD1**: 71% of min — high because "triage-heavy without drill" implies "still in triage phase, never into baseline_contrast". Defensible because 10 PD3-only cases exist (agent ran baseline_contrast yet still triage-looped).
- **Improvement**: could switch to a ratio (n_triage / total_sql) with a density-normalized threshold. Kept absolute thresholds here for readability.

### Weakest: PD5_FinalRCNotGroundedByProbe

- **Why weak**: Density is only 13/103 (below 20% floor is a concern). 
- **Co-occurrence with T2_BaselineNoiseAnchored**: 85% (11/13). Comes close to the 90% tautology threshold.
- **Defense**: PD5 captures a discrete action (service-name probe absence) that is boolean-testable from SQL text alone; T2 is a reasoning conclusion. A regression test: among T2-labeled cases (33 total), only 33% (11) fire PD5 — demonstrating that T2 does not imply PD5 (most T2 cases still did some probing of the hallucinated RC, they just misinterpreted its results). So PD5 is a tighter, process-level filter inside the T2 population. Not a tautology.
- **Improvement**: broaden to include "final RC probed but never with latency/percentile filter" to raise density while keeping mechanism distinct from T2.

### Weakest: PD6_CallTreeAbsentOrShallow

- **Why weak**: Binary threshold (≤1 call_tree_build). Intent classifier rule `R0` is generous in labeling WITH RECURSIVE self-joins, so some "shallow" tree-build cases include 2-hop joins that are productive. False-negative risk.
- **Improvement**: post-hoc check SQL depth (does `WITH RECURSIVE` appear? count of recursive levels?) in `dossiers/*.md`. Did not implement because it requires per-SQL AST parsing.

## Summary

- **Final PD class count**: 6  
- **Confirmed cases**: 102/103 (all except empty-PD cases, which are explicitly marked `confirmed=false` only if zero phrases emitted)  
- **Empty-PD cases**: 0 (see list above)  
- **Unresolved cases**: 0 (every case's signals triangulate across all three sources)  
- **Rejected PD classes**: 5 (RunawayRoundsPastPivot, ExcessiveBaselineCollectLoop, SubagentSpawn, ExplicitGTDismissal, SchemaDiscoveryOverlong)
