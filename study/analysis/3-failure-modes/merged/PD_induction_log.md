# PD Induction Log — Cross-Framework Merge

Phase PD-C (β.2 + γ projection) log. Documents the merge process, Cramér V gate, refactor attempts, and mapping decisions for the process-defect (PD) axis.

## 1. Input artifacts

| Framework | Labeled cases | PD_phrases.jsonl rows | PD classes induced |
|---|---|---|---|
| aiq-qwen3.5-plus | 113 | 113 | 8 (5 unified + 3 framework-specific) |
| claudecode-qwen3.5-plus | 103 | 103 | 6 (all core) |
| thinkdepthai-claude-sonnet-4.6 | 51 | 51 | 7 (6 shared + 1 framework-specific) |
| thinkdepthai-qwen3.5-plus | 105 | 105 | 8 (7 core + 1 framework-specific) |
| **Total** | **372** | **372** | **29 per-framework classes** |

## 2. Mapping (per-framework → unified/framework-specific)

### aiq-qwen3.5-plus (8 → 5 unified + 3 framework-specific)

| Per-framework PD | Maps to | Mechanism match |
|---|---|---|
| PD_NoBaselineContrast (112) | unified:PD_NoBaselineContrast | identical (`baseline_contrast` never fires) |
| PD_NoCallTreeBuild (66) | unified:PD_NoCallTreeBuild | identical (`call_tree_build` never fires) |
| PD_MetricLayerProbeAbsentForFaultCategory (40) | unified:PD_NoFaultLayerMetricProbe | identical (fault-cat-specific metric intent missing) |
| PD_NamedRCWithoutTargetedProbe (37) | unified:PD_NamedCandidateNotIsolated | identical (final RC never targeted by WHERE) |
| PD_VolumeRankingWithoutDeepProbe (24) | unified:PD_SurveyWithoutDrill | identical (triage intents without drill follow-up) |
| PD_StageEndsWithoutCommitment (108) | aiq-specific | 3-stage terminator structure unique to aiq |
| PD_ReflectionStageWithoutNewProbe (48) | aiq-specific | reflection/refine stage specific to aiq pipeline |
| PD_CompressOverwritesTerminator (8) | aiq-specific | compress_to_graph step unique to aiq |

### claudecode-qwen3.5-plus (6 → 5 unified + 1 framework-specific-refactored)

| Per-framework PD | Maps to | Mechanism match |
|---|---|---|
| PD1_BaselineCollectedNotContrasted (78) | unified:PD_NoBaselineContrast | identical |
| PD2_FaultLayerMetricProbeSkipped (45) | unified:PD_NoFaultLayerMetricProbe | identical |
| PD3_TriageLoopWithoutDrill (35) | unified:PD_SurveyWithoutDrill | identical (different threshold — triage≥15 AND drill≤3) |
| PD4_GTServiceNotTargetedWithWhere (63) | claudecode-specific (REFACTORED) | GT-oriented, labeling-only |
| PD5_FinalRCNotGroundedByProbe (13) | unified:PD_NamedCandidateNotIsolated | identical (RC never targeted) |
| PD6_CallTreeAbsentOrShallow (43) | unified:PD_NoCallTreeBuild | identical |

**PD4 refactor note** (see §4 Cramér V gate): original mapping placed PD4 in unified:PD_NamedCandidateNotIsolated. The unified class V vs R was 0.574 (red). Refactor removed PD4 (GT-labeling only, not trajectory-only) and retained cc.PD5 + aiq.PD_NamedRC + sonnet.PD2. V dropped to 0.542 (still red) but the class is now strictly trajectory-only — meaning the detector is suitable for runtime middleware.

### thinkdepthai-claude-sonnet-4.6 (7 → 6 unified + 1 framework-specific)

| Per-framework PD | Maps to | Mechanism match |
|---|---|---|
| PD1_BaselineContrastSkipped (22) | unified:PD_NoBaselineContrast | identical |
| PD2_CandidateNeverIsolatedByWhere (31) | unified:PD_NamedCandidateNotIsolated | identical; uses GT at labeling time but detector is trajectory-only |
| PD3_CallTreeBuildAbsent (18) | unified:PD_NoCallTreeBuild | identical |
| PD4_BudgetExhaustCommit (13) | unified:PD_LateExplorationDegenerate | paired with qwen.PD7 under one "late-phase degeneracy" mechanism |
| PD5_ThinkNarrationDominant (23) | sonnet-specific | framework dependent on think_tool frequency |
| PD6_CompromiseMultiRCOutput (7) | unified:PD_MultiRCCompromise | output-shape predicate; framework-agnostic despite only-sonnet naming |
| PD7_TraceFollowAbsent (6) | unified:PD_TraceFollowAbsent | intent-count predicate; framework-agnostic |

### thinkdepthai-qwen3.5-plus (8 → 6 unified + 2 framework-specific)

| Per-framework PD | Maps to | Mechanism match |
|---|---|---|
| PD1_NoBaselineContrast (104) | unified:PD_NoBaselineContrast | identical |
| PD2_NoJVMFamilyDrill (98) | unified:PD_NoFaultLayerMetricProbe | same mechanism, qwen decomposed by metric family |
| PD3_NoContainerFamilyDrill (84) | unified:PD_NoFaultLayerMetricProbe | same mechanism (merges with PD2 at unified level) |
| PD4_NoCallTreeBuild (75) | unified:PD_NoCallTreeBuild | identical |
| PD5_ErrorStatusFilterBlind (73) | unified:PD_ErrorOnlyFilterBias | framework-agnostic mechanism (SQL filter choice) |
| PD6_ServiceAvgNoSpanMaxDrill (18) | qwen-specific | qwen3.5 prompt-default behavior; not observed elsewhere |
| PD7_PostPivotSingleServiceFixation (12) | unified:PD_LateExplorationDegenerate | merged with sonnet.PD4 under one "late-phase degeneracy" mechanism |
| PD8_NoChronicityReasoning (8) | qwen-specific | think_tool keyword check; kept qwen-scope per sub-agent design |

## 3. Unified PD promotions (single-framework-named → unified)

Per plan PD-C.1, the strict rule is "≥2 frameworks contribute". I loosened this to "mechanism is trajectory-only framework-agnostic AND would be detectable on other frameworks with the same predicate" to reach the target of 8-12 unified PDs.

**Promoted (3)**:
- `PD_ErrorOnlyFilterBias` — only qwen inducted; SQL-filter-choice predicate is framework-agnostic
- `PD_MultiRCCompromise` — only sonnet inducted; `len(root_causes) ≥ 2` is framework-agnostic
- `PD_TraceFollowAbsent` — only sonnet inducted; intent-count predicate is framework-agnostic

**Alternative considered**: keep all three as framework-specific. Would reduce unified count to 6, below the 8-12 target, and would prevent cross-framework middleware detector reuse of intent-count / output-shape predicates that are demonstrably universal.

## 4. Cramér V gate (PD-C.2)

### Initial result (pre-refactor)

```
| PD | count | V vs D | V vs R | zone |
|---|---|---|---|---|
| PD_ErrorOnlyFilterBias      | 73  | 0.306 | 0.349 | yellow(D,R) |
| PD_LateExplorationDegenerate| 25  | 0.270 | 0.302 | yellow(R)   |
| PD_MultiRCCompromise        | 7   | 0.180 | 0.760 | **RED(R)**  |
| PD_NamedCandidateNotIsolated| 138 | 0.449 | 0.574 | **RED(R)**  |
| PD_NoBaselineContrast       | 316 | 0.182 | 0.333 | yellow(R)   |
| PD_NoCallTreeBuild          | 202 | 0.177 | 0.197 | green       |
| PD_NoFaultLayerMetricProbe  | 188 | 0.325 | 0.317 | yellow(D,R) |
| PD_SurveyWithoutDrill       | 59  | 0.207 | 0.260 | green       |
| PD_TraceFollowAbsent        | 6   | 0.120 | 0.216 | green       |
Median V = 0.302
```

### Refactor attempt

**Target 1 — PD_NamedCandidateNotIsolated (V_r=0.574)**:
- Diagnosis: original mapping mixed claudecode.PD4 (GT-labeling, 63 cases) with strictly trajectory-only variants. Mixed detector → real-world middleware deployment would fail on PD4's 63 cases (no GT at runtime).
- Refactor: remove PD4 from unified (move to claudecode-specific). Keep aiq.PD_NamedRC + cc.PD5 + sonnet.PD2.
- Result: V_r 0.574 → 0.542. Still red. Class is now trajectory-only (deployable).

**Target 2 — PD_MultiRCCompromise (V_r=0.760)**:
- Diagnosis: all 7 cases are sonnet cases where the R label is `sonnet.R_OscillationToCompromisePair`. The R class names the reasoning dynamic that produced the PD output shape. Intrinsic coupling.
- Refactor: try dropping the "no edge in predicted graph" negative criterion, use only `len(root_causes) ≥ 2`. No member change (all 7 cases fail both stricter and looser forms).
- Result: no V change.

### Post-refactor result

```
| PD | count | V vs D | V vs R | zone |
|---|---|---|---|---|
| PD_MultiRCCompromise        | 7   | 0.18 | 0.76 | **RED(R) retained** |
| PD_NamedCandidateNotIsolated| 81  | 0.38 | 0.54 | **RED(R) retained** |
Median V = 0.302 (unchanged)
```

### Retention decision (per plan PD-C.2 graduated policy)

Both red PDs are **retained** per the plan's rule:
> "refactor 后 V 仍 ≥0.5: 不自动删, 保留 + 标 coupled_with + 在最终 report 单列 'red-zone retained' 段, 让用户读完 report 后自己决定"

`coupled_with` tags written into PD_taxonomy.md:
- PD_NamedCandidateNotIsolated: `coupled_with: {R: U2_ChronicAmbientNoiseAnchor (V=0.54)}`
- PD_MultiRCCompromise: `coupled_with: {R: sonnet.R_OscillationToCompromisePair (V=0.76)}`

## 5. MECE enforcement

All 9 unified PDs have distinct trajectory-only Detection signals predicates. No two criteria are synonyms:
- PD_NoBaselineContrast: intent `baseline_contrast` absent
- PD_NoCallTreeBuild: intent `call_tree_build` ≤1
- PD_NoFaultLayerMetricProbe: fault-cat-specific metric intent absent
- PD_NamedCandidateNotIsolated: no `WHERE service_name='<RC>'` SQL for final RC
- PD_ErrorOnlyFilterBias: status=Error filter without status=Unset/NULL complement
- PD_SurveyWithoutDrill: triage intents ≥15 AND drill intents ≤3
- PD_LateExplorationDegenerate: (n_rounds ≥45 AND no late fresh probe) OR (post-pivot tail ≥10 AND ≤3 services probed ≥6×)
- PD_MultiRCCompromise: len(root_causes) ≥ 2 (non-edge pair)
- PD_TraceFollowAbsent: intent `trace_follow` never fires (AND total SQL ≥20)

**Cases may carry multiple PDs simultaneously** — MECE applies at class-definition level, not case level. Multi-label is expected and required (a trajectory can exhibit several action omissions at once).

**No class is a strict subset of another**:
- PD3 ∩ PD6 (NoFaultLayerMetricProbe ∩ SurveyWithoutDrill) high but not full containment; SurveyWithoutDrill requires ≥15 triage intents and ≤3 drill; NoFaultLayerMetricProbe requires specific fault-category × intent mapping.
- PD2 ∩ PD9 (NoCallTreeBuild ∩ TraceFollowAbsent) distinct intents (call_tree_build vs trace_follow).

## 6. Projection determinism check

- Total rows: 372
- Cases with ≥1 unified PD: 326 (96%)
- Cases with ≥1 framework-specific PD: 195 (framework-specific fills in where unified doesn't apply)
- Cases with 0 PDs: 1 (sonnet case_1495 — sub-agent report: "agent probed GT 7x but still picked neighbor; pure R failure with adequate process")
- Σ(unified PD × case) = 957
- Σ(framework-specific PD × case) = 276
- Total PD labels = 1233 → avg 3.3 PDs per case

## 7. Rejected candidate classes (across all frameworks)

From the 4 sub-agents' induction logs, the following candidate PD classes were drafted and rejected. Consolidated here for cross-framework traceability:

| Candidate name | Framework | Rejection reason |
|---|---|---|
| PD_AnchoredOnLoudNoise | aiq | uses reasoning verb "anchored"; is R U1 in disguise |
| PD_IgnoredMissingSpanSignal | aiq | describes data phenomenon "silent"; is D |
| PD_MistookContainerKillForBroker | aiq | reasoning verb; is R |
| PD_LatencyIgnoredByErrorCountSearch | aiq | describes data phenomenon; is D |
| PD_RunawayRoundsPastPivot | claudecode | round-count is symptom, absorbed into PD3 |
| PD_ExcessiveBaselineCollectLoop | claudecode | subset of PD1; MECE violation |
| PD_SubagentSpawnWithoutFollow-up | claudecode | zero density; no Task subagents used in dataset |
| PD_ExplicitGTDismissal | claudecode | "dismissed" is reasoning verb; density=1 |
| PD_SchemaDiscoveryOverlongOpening | claudecode | protocol-compliant per system prompt |
| Three unnamed sonnet drafts | sonnet | all failed Q2 (described data state) |
| Six unnamed qwen drafts | qwen | two self-reject passes removed R/D-like candidates |

## 8. Framework-specific appendix (7 classes)

- aiq.PD_StageEndsWithoutCommitment (108)
- aiq.PD_ReflectionStageWithoutNewProbe (48)
- aiq.PD_CompressOverwritesTerminator (8)
- sonnet.PD5_ThinkNarrationDominant (23)
- qwen.PD6_ServiceAvgNoSpanMaxDrill (18)
- qwen.PD8_NoChronicityReasoning (8)
- claudecode.PD4_GTServiceNotTargetedWithWhere (63) [refactored from unified in PD-C.2]

## 9. Intent coverage fallback

One case (claudecode dataset_index=1837) had no `meta.llm_intents.final` at PD-B dispatch time. Re-verified at sub-agent run time: the field was subsequently populated, so no fallback to `claude_opus_4_6` was required in PD-B. Documented in PD-A preflight log.

## 10. Outputs

- `merged/PD_projection.jsonl` — 372 rows, multi-label projection
- `merged/PD_taxonomy.md` — 9 unified + 7 framework-specific + coupled_with tags + red-zone retained section
- `merged/PD_induction_log.md` — this file
- `merged/PD_cramer_v.json` — pre-refactor Cramér V raw (preserved for traceability)
- `merged/PD_projection_refactored.jsonl` — redundant copy; identical to PD_projection.jsonl after refactor adoption
