# Process-Defect (PD) Taxonomy — Cross-Framework Merge

**Phase PD-C (β.2 + γ)** — cross-framework process-defect merge. Complement to D (data obstacles) and R (reasoning mechanisms), covers "trajectory-observable action defects" that are independent of D and R.

**Frameworks merged**: aiq-qwen3.5-plus (113), claudecode-qwen3.5-plus (103), thinkdepthai-claude-sonnet-4.6 (51), thinkdepthai-qwen3.5-plus (105). **Total = 372 labeled failure cases** (includes 2 dataset_anomaly cases deferred by R axis).

**Per-agent PD classes ingested**: 29 (8 aiq + 6 claudecode + 7 sonnet + 8 qwen).

**Unified PD count**: **9 classes**. **Framework-specific (appendix)**: 7 classes.

Merge principle: mechanism homogeneity, not name similarity. Each per-agent PD class maps to exactly one unified PD OR to the framework-specific appendix. PDs are multi-label (0..N per case); MECE applies to class definitions, not cases.

---

## Coupling summary (Cramér's V vs D and R)

| PD | count | V vs D | V vs R | zone |
|---|---|---|---|---|
| PD_NoBaselineContrast | 316 | 0.18 | 0.33 | yellow (R) |
| PD_NoCallTreeBuild | 202 | 0.18 | 0.20 | green |
| PD_NoFaultLayerMetricProbe | 188 | 0.33 | 0.32 | yellow (D,R) |
| PD_NamedCandidateNotIsolated | 81 | 0.38 | 0.54 | **red (R)** retained |
| PD_ErrorOnlyFilterBias | 73 | 0.31 | 0.35 | yellow (D,R) |
| PD_SurveyWithoutDrill | 59 | 0.21 | 0.26 | green |
| PD_LateExplorationDegenerate | 25 | 0.27 | 0.30 | yellow (R) borderline |
| PD_MultiRCCompromise | 7 | 0.18 | 0.76 | **red (R)** retained |
| PD_TraceFollowAbsent | 6 | 0.12 | 0.22 | green |

**Median V = 0.30** — passes the orthogonality target (plan required median < 0.30 or else recluster; at 0.30 boundary the taxonomy is retained per plan's "若中位数 ≥0.30 且 >1/3 红区 → recluster" rule: only 2 of 9 (22%) are red, below 1/3 threshold, so individual red-zone handling applies, not recluster).

---

## Unified PDs (N=9)

### PD_NoBaselineContrast (316 cases, scope=unified, 4/4 frameworks)

**Failure mechanism**: The agent never issues a SQL query that pairs `abnormal_*` readings with `normal_*` baseline readings to contrast them. Either `baseline_collect` never fires at all (the agent doesn't read the normal baseline), or `baseline_collect` fires but the agent never follows with `baseline_contrast` (it reads the baseline but never compares). The defect is absent "baseline differencing" in the hypothesis-gate step.

**Detection signals (trajectory-only)**:
```
intents_final = [row['intent'] for row in meta.llm_intents.final]
fire(intents_final, 'baseline_contrast') == False
```

**Coupled_with**: `U1_LoudnessAnchorOverSilentVictim` (39% of PD members carry U1), `D_victim_silent_on_path` (40%). Real mechanism link but distinct axis: PD describes the missing SQL query shape; U1/D1 describe the reasoning conclusion and data state. V vs R = 0.33 (yellow).

**Per-framework members**: aiq(112), claudecode(78), sonnet(22), qwen(104). Denominator proportions: aiq 99%, claudecode 76%, sonnet 43%, qwen 99%. This is the most ubiquitous PD in the failure pool.

---

### PD_NoCallTreeBuild (202 cases, scope=unified, 4/4 frameworks)

**Failure mechanism**: The agent never (or exactly once) runs a SQL whose intent classifies as `call_tree_build` — no query reconstructs a top-down service→service call hierarchy for the incident window. Reconstruction of propagation topology never happens. Detectable via intent classification or SQL regex `WITH RECURSIVE.*parent_span_id`.

**Detection signals**:
```
count(intents_final, 'call_tree_build') <= 1
```
(aiq/qwen/sonnet use == 0; claudecode uses <=1; unified adopts the more lenient <=1 threshold.)

**Coupled_with**: `U1_LoudnessAnchorOverSilentVictim` (37%), `D_victim_silent_on_path` (39%). V vs D = 0.18, V vs R = 0.20 — **green zone**, best-orthogonal PD.

**Per-framework members**: aiq(66), claudecode(43), sonnet(18), qwen(75).

---

### PD_NoFaultLayerMetricProbe (188 cases, scope=unified, 3/4 frameworks + cross-applicable)

**Failure mechanism**: The fault category of the incident indicates a specific measurement layer — JVMChaos → `jvm_state`/`container_resource`; PodChaos → `k8s_state`/`container_resource`; NetworkChaos-on-DB → `db_state`/`container_resource` — but the agent's trajectory contains zero SQLs classified to the corresponding metric intent. The layer whose signature matches the injection type is skipped entirely.

**Detection signals**:
```
if fc.startswith('JVMChaos'):
    return not fire(intents,'jvm_state') and not fire(intents,'container_resource')
if fc.startswith('PodChaos'):
    return not fire(intents,'k8s_state') and not fire(intents,'container_resource')
if fc in {'NetworkBandwidth','NetworkDelay','NetworkCorrupt','NetworkLoss'}:
    return not fire(intents,'db_state') and not fire(intents,'container_resource')
return False
```
(qwen sub-agent split the predicate into `NoJVMFamilyDrill` and `NoContainerFamilyDrill` without the fault-category gate; both map here.)

**Coupled_with**: `U1_LoudnessAnchorOverSilentVictim` (40%), `D_victim_silent_on_path` (50% — strong; silent-victim faults heavily correlate with skipped metric-layer probes). V vs D = 0.33, V vs R = 0.32 — **yellow** both axes.

**Per-framework members**: aiq(40), claudecode(45), qwen(103). Sonnet did not induce this class explicitly, but the predicate can be applied post-hoc on sonnet's trajectories (the mechanism is framework-agnostic; sonnet's failure pool has lower incidence likely due to higher overall accuracy and sonnet's think_tool narrating fault-category reasoning explicitly).

---

### PD_NamedCandidateNotIsolated (81 cases, scope=unified, 3/4 frameworks)  **[RED-ZONE RETAINED]**

**Failure mechanism**: The final root-cause service in the output graph is never the target of a dedicated, targeted SQL probe. No SQL with `WHERE service_name='<named-RC>'`, no targeted metric probe, no targeted log probe was ever issued. The conclusion is arrived at without any investigation of the named entity.

**Detection signals**:
```
rc_services = final_output.root_causes
for s in rc_services:
    targeted = [q for q in trajectory_sqls if f"service_name = '{s}'" in q.sql]
    if len(targeted) == 0:
        return True
return False
```

**Coupled_with**: `U2_ChronicAmbientNoiseAnchor` (37% of PD members). **V vs R = 0.54 (red).**

**Red-zone handling (per plan PD-C.2)**:
1. **Refactor attempted**: original mapping included claudecode.PD4_GTServiceNotTargetedWithWhere (63 cases) using GT labels. Refactored to exclude GT-oriented variant (moved to framework-specific), reducing V_r from 0.574 → 0.542. Tighter, still red.
2. **Retention decision**: **KEEP**. Rationale — the PD is a genuine trajectory-observable process deficit; the R coupling reflects that chronic-noise anchoring and volume-ranking behaviours structurally co-occur with commit-without-probe (both are "shortcut" forms). But distinct axes: PD is an action omission (no WHERE probe), R is a reasoning heuristic (anchor on loud). User-audit candidates: see "Red-zone retained" section at bottom of report.

**Per-framework members**: aiq(37), claudecode(13), sonnet(31). qwen did not induce an equivalent class as a top-level PD, but claudecode's PD4 (GT-oriented, 63 cases) is retained as framework-specific.

---

### PD_ErrorOnlyFilterBias (73 cases, scope=unified, 1 framework named + mechanism-agnostic)

**Failure mechanism**: The agent issues at least one SQL filtering on `status_code='Error'` (or equivalent) but never issues a complementary query probing `status='Unset'`, `status IS NULL`, or `missing_span`. The agent's view of "problems" is exclusively error-status spans, blinding it to stalled/silent/injected-but-successful-looking victims.

**Detection signals**:
```
has_error_filter = any('status(_code)?.*=.*Error' in q.sql for q in trajectory_sqls)
has_unset_filter = any(
    'status(_code)?.*=.*Unset' in q.sql
    or 'status.*IS NULL' in q.sql
    or 'missing_span' in q.sql
    for q in trajectory_sqls
)
return has_error_filter and not has_unset_filter
```

**Coupled_with**: Top D = `D_cross_layer_signal_gap` (derived from coupling detail), top R = `U1_LoudnessAnchorOverSilentVictim`. V_d = 0.31, V_r = 0.35 — **yellow** both axes.

**Per-framework members**: qwen(73). Only qwen's sub-agent inducted this class; mechanism is genuinely framework-agnostic (any agent using DuckDB over parquets can exhibit it). Kept as unified for cross-framework middleware deployment.

---

### PD_SurveyWithoutDrill (59 cases, scope=unified, 2/4 frameworks)

**Failure mechanism**: The agent issues one or more triage-level intents (`error_log_overview`, `error_rate_scan`, `latency_ranking`, `throughput_compare`, `metric_scan`) producing service-ranked count lists, but never runs any deep-metric intent (`jvm_state`, `k8s_state`, `container_resource`, `db_state`) or runs at most a trivial count (≤3). Investigation stops at "which service has most errors/slowest latency" — no modality cross-check.

**Detection signals** (claudecode threshold):
```
TRIAGE = {'latency_ranking','throughput_compare','error_rate_scan','error_log_overview','metric_scan'}
DRILL  = {'container_resource','jvm_state','network_layer','k8s_state','db_state'}
n_tr = count(intents, TRIAGE)
n_dr = count(intents, DRILL)
return n_tr >= 15 and n_dr <= 3
```

**Coupled_with**: `U1_LoudnessAnchorOverSilentVictim` (32%), `U2_ChronicAmbientNoiseAnchor` (25%), `D_victim_silent_on_path` (42%). V = 0.21/0.26 — **green**.

**Per-framework members**: aiq(24, `PD_VolumeRankingWithoutDeepProbe`), claudecode(35, `PD3_TriageLoopWithoutDrill`). Sonnet + qwen sub-agents didn't induce this; mechanism applies but the cases overlap heavily with PD_NoFaultLayerMetricProbe in those frameworks.

---

### PD_LateExplorationDegenerate (25 cases, scope=unified, 2/4 frameworks)

**Failure mechanism**: Either (a) the agent ran the trajectory to near the round-budget ceiling (≥45 rounds) and the final commitment emerges in the last few rounds without a late-stage pivot-retry SQL on an alternative hypothesis (sonnet's `BudgetExhaustCommit`), OR (b) after the pivot round, the tail of the trajectory (≥10 rounds) is dominated by a single service — one service in ≥6 WHERE filters, ≤3 distinct services probed (qwen's `PostPivotSingleServiceFixation`). Both describe "late-phase exploration degeneracy": the agent stops exploring and starts looping.

**Detection signals** (merged predicate, OR of two sub-predicates):
```
n_rounds >= 45
  AND no SQL in last third of rounds introduces a service not already probed
OR
(total_rounds - pivot_round) >= 10
  AND max(count per service_filter in tail) >= 6
  AND |distinct services probed in tail| <= 3
```

**Coupled_with**: borderline yellow (V_r=0.30). Modest coupling with `sonnet.R_OscillationToCompromisePair` + `U1` + `U2`. Retained as distinct process mechanism.

**Per-framework members**: sonnet(13, `PD4_BudgetExhaustCommit`), qwen(12, `PD7_PostPivotSingleServiceFixation`).

---

### PD_MultiRCCompromise (7 cases, scope=unified, 1 framework named + mechanism-agnostic)  **[RED-ZONE RETAINED]**

**Failure mechanism**: The final `root_causes` array contains two or more services that do not form a legitimate caller→callee pair in the predicted causal graph. The agent never converges to a single commitment — typically a compromise between two loud-signal candidates after budget exhaustion.

**Detection signals**:
```
len(final_output.root_causes) >= 2
AND the services listed do NOT form an edge in agent's predicted graph
```

**Coupled_with**: `sonnet.R_OscillationToCompromisePair` (57%). **V vs R = 0.76 (red).**

**Red-zone handling**:
1. **Refactor attempt**: removing the "no edge" negative criterion gives a strictly len(root_causes)≥2 predicate, but that predicate's members are the same 7 cases (no edge pairs in the small failure pool). No change in V.
2. **Retention decision**: **KEEP**. The R coupling is with a framework-specific sonnet R class that describes the **reasoning dynamic** ("oscillated"); the PD describes the **output shape** ("final array length"). Distinct axes. Both axes are kept for the same failure pattern because they provide orthogonal detection signals (R requires labeler reasoning-trace analysis; PD requires only the final JSON).

**Per-framework members**: sonnet(7, `PD6_CompromiseMultiRCOutput`). Mechanism is framework-agnostic (any JSON-emitting agent can emit multi-RC); only sonnet had 7 cases in its failure pool. Retained as unified for middleware applicability.

---

### PD_TraceFollowAbsent (6 cases, scope=unified, 1 framework named + mechanism-agnostic)

**Failure mechanism**: The agent never issues a `trace_follow` SQL that walks a specific trace_id from one service's span to another across services. This is distinct from `call_tree_build` (which reconstructs hierarchy within one trace) — `trace_follow` follows a specific request-ID thread across services. Absence of both leaves the agent with only aggregate latency rankings.

**Detection signals**:
```
count(intents_final, 'trace_follow') == 0
AND total SQL count >= 20  (excludes short trajectories)
```

**Coupled_with**: spread across multiple R classes; V = 0.12/0.22 — **green**.

**Per-framework members**: sonnet(6, `PD7_TraceFollowAbsent`). Mechanism is framework-agnostic.

---

## Framework-specific PDs (appendix, N=7)

These PDs are retained at framework-scope because the mechanism depends on framework-specific structure (multi-stage pipelines, compress stages, think_tool patterns) or because the predicate is labeling-only (requires GT knowledge).

### aiq.PD_StageEndsWithoutCommitment (108 cases)
At least one of aiq's three reflection stages (`stage_0_main`, `stage_1_refine1`, `stage_2_refine2`) either hit `max_rounds` without emitting a terminator, or emitted one with `service=None`. Stage produced no committed hypothesis for the next stage to react to.

### aiq.PD_ReflectionStageWithoutNewProbe (48 cases)
The reflection/refine mechanism produced a new terminator, but the stage leading up to that terminator contains no new `WHERE service_name='<new-candidate>'` SQL probe. Either reinforced (all stages agree) or flipped without evidentiary support. Requires multi-stage pipeline structure.

### aiq.PD_CompressOverwritesTerminator (8 cases)
After all reflection stages produce their terminator messages, aiq's `compress_to_graph` step synthesizes a JSON output whose root_cause differs from the last produced stage terminator's service. Compress rewrites the conclusion without new SQL. Unique to aiq's compress pipeline stage.

### sonnet.PD5_ThinkNarrationDominant (23 cases)
`think_tool` invocations are ≥40% of rounds AND `think_tool` count ≥15, AND the immediately-following SQL does not use a new WHERE clause. Captures thinkdepthai+sonnet's tendency to spend think-rounds re-stating prior numerics instead of branching to a new probe.

### qwen.PD6_ServiceAvgNoSpanMaxDrill (18 cases)
Agent used `SELECT service_name, AVG(duration) GROUP BY service_name ORDER BY AVG DESC` (service-level AVG ranking) without any span-level `MAX(duration)` follow-up. Pattern specific to qwen3.5's default query shape. Dilutes span-level signals.

### qwen.PD8_NoChronicityReasoning (8 cases)
No `think_tool` invocation contains any chronicity keyword (`background`, `pre-existing`, `chronic`, `vs normal`, `baseline`, `ambient`, `not new`). Agent never verbalized "is this error also present in the normal window?" — a think_tool-text keyword check specific to frameworks that visibly narrate hypotheses.

### claudecode.PD4_GTServiceNotTargetedWithWhere (63 cases)  
[**Refactored from unified to framework-specific in PD-C.2**]
No SQL used `WHERE service_name='<gt_root_cause_service>'` across the trajectory. Since GT knowledge is labeling-time only, this PD cannot serve as a runtime middleware detector — it is retained as an analytical PD for claudecode failure classification. Corresponds to claudecode's original PD4 class.

---

## Red-zone retained (user-audit section)

Per plan PD-C.2, red-zone PDs (V ≥ 0.50 after refactor) are NOT auto-deleted. Instead, listed here for user review:

### PD_NamedCandidateNotIsolated — V vs R = 0.54 after refactor

**Coupled R class**: `U2_ChronicAmbientNoiseAnchor` (37% of PD members).

**Canonical retained cases**:
- aiq case_130: predicted RC `ts-food-service`, zero SQLs with `WHERE service_name='ts-food-service'`; anchored from error-volume aggregation only (chronic RabbitMQ noise).
- aiq case_323: predicted RC `ts-config-service` (hallucinated); never appears in any WHERE filter.
- claudecode case_2231: predicted `ts-basic-service`, zero probes. Named from error-count aggregations.
- sonnet case_572: GT is `ts-food-service + ts-train-food-service`; across 39 rounds zero targeted probes of either.
- qwen — not in this PD (qwen did not induce an equivalent).

**Retention rationale**: the action omission ("no WHERE probe on named RC") is observable independently of the reasoning conclusion. An agent can exhibit U2 (chronic noise anchor) AND probe the RC carefully by name — these are separable mechanisms. The high V reflects a strong behavioural correlation, not an identity.

### PD_MultiRCCompromise — V vs R = 0.76

**Coupled R class**: `sonnet.R_OscillationToCompromisePair` (57%).

**Canonical retained cases**:
- sonnet case_339: final `[ts-consign-service, ts-order-service]` — dual compromise after 49-round budget.
- sonnet case_572: multi-RC output with twin-service confusion.
- sonnet case_675: 2-RC output; oscillated before committing both.
- sonnet case_1948: budget exhaustion + multi-RC.
- sonnet case_2682: compromise between two noise candidates.

**Retention rationale**: the PD is a **pure output-shape** defect (`len(root_causes) ≥ 2`); the R class is a **reasoning trajectory** defect (oscillation). Orthogonal axes. The PD detection needs only the final JSON; the R detection needs full trajectory + labeler analysis. Both are useful for middleware: PD as a cheap final-step gate, R as a failure-mode classifier.

---

## Projection determinism check

```
Σ(case count per unified PD) = 316+202+188+81+73+59+25+7+6 = 957
Σ(case count per framework-specific PD) = 108+63+48+23+18+8+8 = 276
Σ(PDs per case across 372 cases)         = 957 + 276 = 1233

Average PDs per case = 1233 / 372 = 3.3 (median ~3)
Cases with 0 PDs (empty): 1 (sonnet case_1495, pure reasoning failure with adequate process)
Cases with 1+ unified PDs: 371/372 = 99.7%
```

All 372 cases map to a finite set of unified + framework-specific PDs; no "other" bucket.

---

## Unified PD list (quick reference)

| ID | Name | Count | V_d | V_r | Status |
|----|------|-------|-----|-----|--------|
| PD1 | PD_NoBaselineContrast | 316 | 0.18 | 0.33 | yellow(R), kept |
| PD2 | PD_NoCallTreeBuild | 202 | 0.18 | 0.20 | green |
| PD3 | PD_NoFaultLayerMetricProbe | 188 | 0.33 | 0.32 | yellow(D,R), kept |
| PD4 | PD_NamedCandidateNotIsolated | 81 | 0.38 | 0.54 | **red(R), retained** |
| PD5 | PD_ErrorOnlyFilterBias | 73 | 0.31 | 0.35 | yellow(D,R), kept |
| PD6 | PD_SurveyWithoutDrill | 59 | 0.21 | 0.26 | green |
| PD7 | PD_LateExplorationDegenerate | 25 | 0.27 | 0.30 | yellow(R, borderline) |
| PD8 | PD_MultiRCCompromise | 7 | 0.18 | 0.76 | **red(R), retained** |
| PD9 | PD_TraceFollowAbsent | 6 | 0.12 | 0.22 | green |

Framework-specific (7): `aiq.PD_StageEndsWithoutCommitment`, `aiq.PD_ReflectionStageWithoutNewProbe`, `aiq.PD_CompressOverwritesTerminator`, `sonnet.PD5_ThinkNarrationDominant`, `qwen.PD6_ServiceAvgNoSpanMaxDrill`, `qwen.PD8_NoChronicityReasoning`, `claudecode.PD4_GTServiceNotTargetedWithWhere`.

---

## v2 Refactor Notes (Phase X-1, 2026-04-22) — Detection ∧ Counterfactual conjunction

Bucket D analysis (312/1155 non-agree are PD redundancy issues) revealed a structural issue: the v1 PD axis encodes only the **Detection** signal ("action X was not performed") and not the **Counterfactual relevance** ("action X would have helped on THIS case"). The two are orthogonal. To fix, every unified PD's v2 Positive criteria require BOTH conditions.

### v2 Positive criteria (changed)

| PD | v1 Positive (Detection only) | v2 Positive (Detection ∧ Counterfactual) |
|----|------------------------------|------------------------------------------|
| `PD_NoBaselineContrast` | `baseline_contrast` intent absent | AND `chronic_noise_present=True` (parquet) AND (`predicted_rc ∈ carriers` OR `top-3 error service ∈ carriers`) |
| `PD_NoCallTreeBuild` | `call_tree_build` intent absent | AND GT is upstream (causal_graph) of ≥1 service the agent filtered on |
| `PD_NoFaultLayerMetricProbe` | fault-category-specific layer not probed | AND fault-type has a non-`none` `required_metric_layer` (gates the whole predicate) AND `gt_metric_anomaly_exists_in_parquet=True` |
| `PD_ErrorOnlyFilterBias` | has_error_filter AND not has_unset_filter | AND `gt_is_silent=True` (i.e. unset filter would actually help) |
| `PD_NamedCandidateNotIsolated` | RC not in WHERE filters | AND counterfactual `if_isolated_predicted_rc_show_healthy` returns ≥1 healthy service (i.e. the missing probe would change conclusion) |

### Implementation in adjudicator (verify_adjudicate.py)

The v1 adjudicator already encodes the counterfactual checks (`PD1_baseline_contrast.if_run_would_reveal`, `PD2_call_tree_build.gt_is_upstream_of_agent_focus`, `PD3.gt_metric_anomaly_exists_in_parquet`, `PD4.if_isolated_predicted_rc_show_healthy`) but reports failed counterfactuals as `redundant` rather than as label-removal recommendations. Under v2, `redundant` verdicts are explicitly downstream-actionable: each implies the case should NOT carry the PD label under tightened Positive criteria.

### Expected projection-level impact

| PD | v1 redundant N | v2 expected redundant N | Action |
|----|---------------:|------------------------:|--------|
| PD_NoBaselineContrast | 198 | ~10 | Bulk-remove redundant labels via relabel_queue |
| PD_NoCallTreeBuild | 79 | ~5 | Bulk-remove |
| PD_ErrorOnlyFilterBias | 35 | ~3 | Bulk-remove |
| PD_NoFaultLayerMetricProbe (layer=none) | 20 | 0 | Already gated; bulk-remove |

**Net taxonomy structure change**: PD class names retained (no new PD classes added); Positive criteria tightened (counterfactual gate added). This is a pure rule refactor, not a re-induction.

### What remains framework-specific

aiq stage / sonnet think_tool / aiq compress PDs (`aiq.PD_StageEndsWithoutCommitment`, `aiq.PD_ReflectionStageWithoutNewProbe`, `aiq.PD_CompressOverwritesTerminator`, `sonnet.PD5_ThinkNarrationDominant`, `aiq.R_compress_drift`, `aiq.R_correct_then_reversed`, `sonnet.R_NarrativeOverMatchedMagnitude`) remain unverifiable until a trajectory-text-aware extractor is added (see Bucket C in Part 4 of the diagnostic plan). 211 cases continue to receive `unverifiable` verdict in v2; not addressed in this phase.
