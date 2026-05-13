# D / R / PD Label Re-Verification — Mismatch Report

**Scope**: 4 frameworks × stratified random sample. Distinct cases verified: 122. Class-verifications: 153.
**Method**: three-way alignment (GT side + trajectory side + counterfactual parquet simulation). `agree` requires all three tests pass.
**Seed**: 20260422 (reproducible).

---

## 1. Summary tables

### 1.1 Per-axis verdict counts

| Axis | agree | dispute-weak | dispute-strong | fabricated | misaligned | redundant | unverifiable | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D | 25 | 9 | 1 | 0 | 0 | 0 | 0 | 35 |
| R | 25 | 10 | 0 | 0 | 8 | 0 | 9 | 52 |
| PD | 33 | 5 | 8 | 0 | 0 | 8 | 12 | 66 |

### 1.2 Per-class verdict breakdown

| Class | agree | dispute-weak | dispute-strong | fabricated | misaligned | redundant | unverifiable | Total | Non-agree rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D1 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0/5 (0%) |
| D2 | 4 | 1 | 0 | 0 | 0 | 0 | 0 | 5 | 1/5 (20%) |
| D3 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0/5 (0%) |
| D4 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0/5 (0%) |
| D5 | 0 | 4 | 1 | 0 | 0 | 0 | 0 | 5 | 5/5 (100%) |
| D6 | 4 | 1 | 0 | 0 | 0 | 0 | 0 | 5 | 1/5 (20%) |
| D7 | 2 | 3 | 0 | 0 | 0 | 0 | 0 | 5 | 3/5 (60%) |
| PD_ErrorOnlyFilterBias | 3 | 0 | 0 | 0 | 0 | 2 | 0 | 5 | 2/5 (40%) |
| PD_LateExplorationDegenerate | 2 | 3 | 0 | 0 | 0 | 0 | 0 | 5 | 3/5 (60%) |
| PD_MultiRCCompromise | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0/5 (0%) |
| PD_NamedCandidateNotIsolated | 1 | 0 | 4 | 0 | 0 | 0 | 0 | 5 | 4/5 (80%) |
| PD_NoBaselineContrast | 1 | 0 | 2 | 0 | 0 | 2 | 0 | 5 | 4/5 (80%) |
| PD_NoCallTreeBuild | 2 | 0 | 0 | 0 | 0 | 3 | 0 | 5 | 3/5 (60%) |
| PD_NoFaultLayerMetricProbe | 4 | 0 | 0 | 0 | 0 | 1 | 0 | 5 | 1/5 (20%) |
| PD_SurveyWithoutDrill | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0/5 (0%) |
| PD_TraceFollowAbsent | 4 | 0 | 1 | 0 | 0 | 0 | 0 | 5 | 1/5 (20%) |
| U1_LoudnessAnchorOverSilentVictim | 2 | 3 | 0 | 0 | 0 | 0 | 0 | 5 | 3/5 (60%) |
| U2_ChronicAmbientNoiseAnchor | 0 | 1 | 0 | 0 | 4 | 0 | 0 | 5 | 5/5 (100%) |
| U3_EdgeDirectionOrRegionEndpointError | 3 | 0 | 0 | 0 | 2 | 0 | 0 | 5 | 2/5 (40%) |
| U4_NameTwinSiblingConfusion | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0/5 (0%) |
| U5_SilenceReadAsHealthOrPaused | 2 | 1 | 0 | 0 | 2 | 0 | 0 | 5 | 3/5 (60%) |
| aiq.PD_CompressOverwritesTerminator | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 3 | 3/3 (100%) |
| aiq.PD_ReflectionStageWithoutNewProbe | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 3 | 3/3 (100%) |
| aiq.PD_StageEndsWithoutCommitment | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 3 | 3/3 (100%) |
| aiq.R_compress_drift | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 3 | 3/3 (100%) |
| aiq.R_correct_then_reversed | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 3 | 3/3 (100%) |
| aiq.R_hub_fabrication | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0/3 (0%) |
| claudecode.PD4_GTServiceNotTargetedWithWhere | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 3 | 1/3 (33%) |
| claudecode.R6_InfraLayerSkipped | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 3 | 2/3 (67%) |
| claudecode.R7_JVMSymptomMisreadAsDB | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0/3 (0%) |
| qwen.PD6_ServiceAvgNoSpanMaxDrill | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 3 | 2/3 (67%) |
| qwen.PD8_NoChronicityReasoning | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0/3 (0%) |
| qwen.R_E_PathOvershootPastInjection | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 3 | 1/3 (33%) |
| qwen.R_F_QueryDesignBuriesSignal | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 3 | 2/3 (67%) |
| sonnet.PD5_ThinkNarrationDominant | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 3 | 3/3 (100%) |
| sonnet.R_NarrativeOverMatchedMagnitude | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 3 | 3/3 (100%) |
| sonnet.R_OscillationToCompromisePair | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0/3 (0%) |

### 1.3 Per-framework bias check

| Framework | agree | dispute-weak | dispute-strong | fabricated | misaligned | redundant | unverifiable | Total | Non-agree % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aiq | 15 | 4 | 3 | 0 | 0 | 1 | 15 | 38 | 61% |
| claudecode | 26 | 5 | 3 | 0 | 1 | 3 | 0 | 38 | 32% |
| qwen | 20 | 11 | 0 | 0 | 6 | 4 | 0 | 41 | 51% |
| sonnet | 22 | 4 | 3 | 0 | 1 | 0 | 6 | 36 | 39% |

---

## 2. Per-class action recommendation

| Class | N | Non-agree | Action |
|---|---:|---:|---|
| D1 | 5 | 0 | OK |
| D2 | 5 | 1 | OK |
| D3 | 5 | 0 | OK |
| D4 | 5 | 0 | OK |
| D5 | 5 | 5 | likely mis-induced — re-run Phase α for this class |
| D6 | 5 | 1 | OK |
| D7 | 5 | 3 | review |
| PD_ErrorOnlyFilterBias | 5 | 2 | OK — add 3-way alignment guard to Positive criteria |
| PD_LateExplorationDegenerate | 5 | 3 | review |
| PD_MultiRCCompromise | 5 | 0 | OK |
| PD_NamedCandidateNotIsolated | 5 | 4 | likely mis-induced — re-run Phase α for this class |
| PD_NoBaselineContrast | 5 | 4 | likely mis-induced — re-run Phase α for this class — add 3-way alignment guard to Positive criteria |
| PD_NoCallTreeBuild | 5 | 3 | review — add 3-way alignment guard to Positive criteria |
| PD_NoFaultLayerMetricProbe | 5 | 1 | OK |
| PD_SurveyWithoutDrill | 5 | 0 | OK |
| PD_TraceFollowAbsent | 5 | 1 | OK |
| U1_LoudnessAnchorOverSilentVictim | 5 | 3 | review |
| U2_ChronicAmbientNoiseAnchor | 5 | 5 | likely mis-induced — re-run Phase α for this class — add 3-way alignment guard to Positive criteria |
| U3_EdgeDirectionOrRegionEndpointError | 5 | 2 | OK — add 3-way alignment guard to Positive criteria |
| U4_NameTwinSiblingConfusion | 5 | 0 | OK |
| U5_SilenceReadAsHealthOrPaused | 5 | 3 | review — add 3-way alignment guard to Positive criteria |
| aiq.PD_CompressOverwritesTerminator | 3 | 3 | small sample; consider widening |
| aiq.PD_ReflectionStageWithoutNewProbe | 3 | 3 | small sample; consider widening |
| aiq.PD_StageEndsWithoutCommitment | 3 | 3 | small sample; consider widening |
| aiq.R_compress_drift | 3 | 3 | small sample; consider widening |
| aiq.R_correct_then_reversed | 3 | 3 | small sample; consider widening |
| aiq.R_hub_fabrication | 3 | 0 | OK (small sample) |
| claudecode.PD4_GTServiceNotTargetedWithWhere | 3 | 1 | OK (small sample) |
| claudecode.R6_InfraLayerSkipped | 3 | 2 | small sample; consider widening |
| claudecode.R7_JVMSymptomMisreadAsDB | 3 | 0 | OK (small sample) |
| qwen.PD6_ServiceAvgNoSpanMaxDrill | 3 | 2 | small sample; consider widening |
| qwen.PD8_NoChronicityReasoning | 3 | 0 | OK (small sample) |
| qwen.R_E_PathOvershootPastInjection | 3 | 1 | OK (small sample) |
| qwen.R_F_QueryDesignBuriesSignal | 3 | 2 | small sample; consider widening |
| sonnet.PD5_ThinkNarrationDominant | 3 | 3 | small sample; consider widening |
| sonnet.R_NarrativeOverMatchedMagnitude | 3 | 3 | small sample; consider widening |
| sonnet.R_OscillationToCompromisePair | 3 | 0 | OK (small sample) |

---

## 3. Fabricated D obstacles

Cases where D label was claimed but agent never reached GT path (gt_touched=False AND gt_neighbors_touched=∅). The 'data obstacle' was never encountered — failure is on R/PD axis, not D.

*(none detected)*

---

## 4. Misaligned R attribution

Cases where R label was claimed but gt_required_capabilities suggests a different reasoning failure. The R's implied 'failed capability' doesn't match what the case actually required.

| Agent | Case | Class | Suggested alternative | Reason |
|---|---|---|---|---|
| claudecode | 1143 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 156 | U5_SilenceReadAsHealthOrPaused |  | U5 requires silent GT but GT has signal |
| qwen | 2092 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 2231 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 3114 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| qwen | 3868 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 807 | U5_SilenceReadAsHealthOrPaused |  | U5 requires silent GT but GT has signal |
| sonnet | 4739 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |

---

## 5. Redundant PD labels

Cases where PD was claimed but counterfactual shows the missing action would be a no-op. The action's precondition is absent (chronic noise absent for PD1, GT not upstream for PD2, etc.).

| Agent | Case | Class | Reason |
|---|---|---|---|
| aiq | 99 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| claudecode | 3920 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| claudecode | 4791 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| claudecode | 807 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 156 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 3552 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 4707 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponseReplaceBody |
| qwen | 864 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |

---

## 6. Dispute-strong details

### aiq.2130 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-route-service'] in WHERE filters ['ts-basic-service', 'ts-route-service', 'ts-travel-service', 'ts-travel-plan-service', 'ts-station-service', 'ts-preserve-service']
- **evidence**: `merged/verify_evidence/aiq_case_2130.yaml`

### aiq.4463 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-food-service'] in WHERE filters ['ts-ui-dashboard', 'ts-food-service', 'ts-travel-service', 'ts-route-service', 'ts-train-food-service', 'ts-station-food-service']
- **evidence**: `merged/verify_evidence/aiq_case_4463.yaml`

### aiq.572 — D5 (D)

- **positive_criteria**: FAIL (GT is loudest — no cascade decoy)
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: n/a
- **reason**: D5 requires cascade louder than GT but GT itself is top-ranked
- **evidence**: `merged/verify_evidence/aiq_case_572.yaml`

### claudecode.1371 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1371.yaml`

### claudecode.741 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_741.yaml`

### claudecode.864 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-travel-service', 'ts-route-service'] is in WHERE filters ['ts-travel-service', 'ts-basic-service', 'ts-travel-plan-service', 'ts-delivery-service', 'ts-route-plan-service', 'ts-notification-service', 'ts-seat-service']
- **evidence**: `merged/verify_evidence/claudecode_case_864.yaml`

### sonnet.1484 — PD_TraceFollowAbsent (PD)

- **positive_criteria**: FAIL (trace_follow fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD9 claims no trace_follow but substring audit shows one
- **evidence**: `merged/verify_evidence/sonnet_case_1484.yaml`

### sonnet.3493 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-order-other-service'] in WHERE filters ['ts-preserve-service', 'ts-security-service', 'ts-order-other-service']
- **evidence**: `merged/verify_evidence/sonnet_case_3493.yaml`

### sonnet.675 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-travel-service', 'ts-travel2-service'] in WHERE filters ['ts-route-plan-service', 'ts-travel-service', 'ts-travel2-service']
- **evidence**: `merged/verify_evidence/sonnet_case_675.yaml`


---

## 7. Unverifiable cases

- **Requires aiq 3-stage pipeline markers not present in evidenc**: aiq.156 (aiq.R_correct_then_reversed), aiq.2713 (aiq.R_correct_then_reversed), aiq.4801 (aiq.R_correct_then_reversed)
- **Requires aiq compress_to_graph stage analysis not in evidenc**: aiq.1886 (aiq.R_compress_drift), aiq.2769 (aiq.R_compress_drift), aiq.4832 (aiq.R_compress_drift)
- **Requires aiq 3-stage markers not in evidence dump**: aiq.2390 (aiq.PD_StageEndsWithoutCommitment), aiq.4032 (aiq.PD_StageEndsWithoutCommitment), aiq.4530 (aiq.PD_StageEndsWithoutCommitment)
- **Requires aiq compress_to_graph analysis not in evidence dump**: aiq.3600 (aiq.PD_CompressOverwritesTerminator), aiq.4832 (aiq.PD_CompressOverwritesTerminator), aiq.860 (aiq.PD_CompressOverwritesTerminator)
- **Requires aiq multi-stage probe analysis not in evidence dump**: aiq.3673 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.4054 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.4309 (aiq.PD_ReflectionStageWithoutNewProbe)
- **Requires think_tool invocation count not in evidence dump**: sonnet.1948 (sonnet.PD5_ThinkNarrationDominant), sonnet.2616 (sonnet.PD5_ThinkNarrationDominant), sonnet.4510 (sonnet.PD5_ThinkNarrationDominant)
- **Requires narrative-text lexical analysis not in evidence dum**: sonnet.2541 (sonnet.R_NarrativeOverMatchedMagnitude), sonnet.3554 (sonnet.R_NarrativeOverMatchedMagnitude), sonnet.371 (sonnet.R_NarrativeOverMatchedMagnitude)

---

## 8. Red-zone PD re-evaluation

Coupling-red PDs per taxonomy: PD_NamedCandidateNotIsolated (V_r=0.54), PD_MultiRCCompromise (V_r=0.76). Partition verdicts and check redundancy rate.

### PD_NamedCandidateNotIsolated — N=5

- agree: 1 (20%)
- redundant: 0 (0%)
- misaligned/fabricated (spillover): 0 (0%)
- **Recommendation**: keep as unified PD

### PD_MultiRCCompromise — N=5

- agree: 5 (100%)
- redundant: 0 (0%)
- misaligned/fabricated (spillover): 0 (0%)
- **Recommendation**: keep as unified PD

---

## 9. Evidence-extraction accuracy check (V-E meta-verification)

- Audited: 10 YAMLs (random sample, seed=20260422)
- Parquet re-run failures: 0
- Substring re-grep failures: 0
- Overall pass rate: 100%
- **Verdict**: PASS (≥80% threshold). Evidence dumps trustworthy.

---

## 10. Headline findings

- **Overall agree rate**: 83/153 (54%)
- **D axis**: 25/35 agree (71%)
- **R axis**: 25/52 agree (48%)
- **PD axis**: 33/66 agree (50%)

- **Fabricated D**: 0 (every fabricated means the D label is blaming data when the agent chose wrong path)
- **Misaligned R**: 8 (misattributed reasoning-defect class — GT didn't require the capability the R label blames)
- **Redundant PD**: 8 (PD label on cases where the missing action would change nothing)

> For per-case evidence see `merged/verify_evidence/<agent>_case_<id>.yaml`.
> For per-verdict row see `merged/verify_verdicts.jsonl`.
