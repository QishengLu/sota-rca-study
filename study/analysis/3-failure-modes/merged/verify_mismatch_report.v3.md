# D / R / PD Label Re-Verification — Mismatch Report

**Scope**: 4 frameworks × ALL labeled failure cases. Distinct cases verified: 372. Class-verifications (D + R + multi-PD per case): 1359.
**Method**: three-way alignment (GT side + trajectory side + counterfactual parquet simulation). `agree` requires all three tests pass.
**Corpus**: all 372 cases from `D_projection.jsonl` + `PD_projection.jsonl` + DB `meta.failure_analysis.v1.R`.

---

## 1. Summary tables

### 1.1 Per-axis verdict counts

| Axis | agree | dispute-weak | dispute-strong | fabricated | misaligned | redundant | unverifiable | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D | 214 | 101 | 0 | 0 | 0 | 0 | 0 | 315 |
| R | 157 | 145 | 0 | 0 | 36 | 0 | 24 | 362 |
| PD | 469 | 26 | 0 | 0 | 0 | 0 | 187 | 682 |

### 1.2 Per-class verdict breakdown

| Class | agree | dispute-weak | dispute-strong | fabricated | misaligned | redundant | unverifiable | Total | Non-agree rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D1 | 77 | 23 | 0 | 0 | 0 | 0 | 0 | 100 | 23/100 (23%) |
| D2 | 40 | 19 | 0 | 0 | 0 | 0 | 0 | 59 | 19/59 (32%) |
| D3 | 31 | 19 | 0 | 0 | 0 | 0 | 0 | 50 | 19/50 (38%) |
| D4 | 36 | 0 | 0 | 0 | 0 | 0 | 0 | 36 | 0/36 (0%) |
| D5 | 2 | 28 | 0 | 0 | 0 | 0 | 0 | 30 | 28/30 (93%) |
| D6 | 21 | 2 | 0 | 0 | 0 | 0 | 0 | 23 | 2/23 (9%) |
| D7 | 7 | 10 | 0 | 0 | 0 | 0 | 0 | 17 | 10/17 (59%) |
| PD_ErrorOnlyFilterBias | 38 | 0 | 0 | 0 | 0 | 0 | 0 | 38 | 0/38 (0%) |
| PD_LateExplorationDegenerate | 14 | 11 | 0 | 0 | 0 | 0 | 0 | 25 | 11/25 (44%) |
| PD_MultiRCCompromise | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 0/7 (0%) |
| PD_NamedCandidateNotIsolated | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 11 | 0/11 (0%) |
| PD_NoBaselineContrast | 36 | 0 | 0 | 0 | 0 | 0 | 0 | 36 | 0/36 (0%) |
| PD_NoCallTreeBuild | 109 | 0 | 0 | 0 | 0 | 0 | 0 | 109 | 0/109 (0%) |
| PD_NoFaultLayerMetricProbe | 153 | 0 | 0 | 0 | 0 | 0 | 0 | 153 | 0/153 (0%) |
| PD_SurveyWithoutDrill | 55 | 4 | 0 | 0 | 0 | 0 | 0 | 59 | 4/59 (7%) |
| PD_TraceFollowAbsent | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0/5 (0%) |
| U1_LoudnessAnchorOverSilentVictim | 69 | 122 | 0 | 0 | 27 | 0 | 0 | 218 | 149/218 (68%) |
| U2_ChronicAmbientNoiseAnchor | 13 | 5 | 0 | 0 | 9 | 0 | 0 | 27 | 14/27 (52%) |
| U3_EdgeDirectionOrRegionEndpointError | 28 | 0 | 0 | 0 | 0 | 0 | 0 | 28 | 0/28 (0%) |
| U4_NameTwinSiblingConfusion | 17 | 1 | 0 | 0 | 0 | 0 | 0 | 18 | 1/18 (6%) |
| U5_SilenceReadAsHealthOrPaused | 4 | 5 | 0 | 0 | 0 | 0 | 0 | 9 | 5/9 (56%) |
| aiq.PD_CompressOverwritesTerminator | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 8 | 8/8 (100%) |
| aiq.PD_ReflectionStageWithoutNewProbe | 0 | 0 | 0 | 0 | 0 | 0 | 48 | 48 | 48/48 (100%) |
| aiq.PD_StageEndsWithoutCommitment | 0 | 0 | 0 | 0 | 0 | 0 | 108 | 108 | 108/108 (100%) |
| aiq.R_compress_drift | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 8 | 8/8 (100%) |
| aiq.R_correct_then_reversed | 0 | 0 | 0 | 0 | 0 | 0 | 13 | 13 | 13/13 (100%) |
| aiq.R_hub_fabrication | 11 | 1 | 0 | 0 | 0 | 0 | 0 | 12 | 1/12 (8%) |
| claudecode.PD4_GTServiceNotTargetedWithWhere | 26 | 0 | 0 | 0 | 0 | 0 | 0 | 26 | 0/26 (0%) |
| claudecode.R6_InfraLayerSkipped | 2 | 5 | 0 | 0 | 0 | 0 | 0 | 7 | 5/7 (71%) |
| claudecode.R7_JVMSymptomMisreadAsDB | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0/4 (0%) |
| qwen.PD6_ServiceAvgNoSpanMaxDrill | 7 | 11 | 0 | 0 | 0 | 0 | 0 | 18 | 11/18 (61%) |
| qwen.PD8_NoChronicityReasoning | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0/8 (0%) |
| qwen.R_E_PathOvershootPastInjection | 5 | 1 | 0 | 0 | 0 | 0 | 0 | 6 | 1/6 (17%) |
| qwen.R_F_QueryDesignBuriesSignal | 1 | 4 | 0 | 0 | 0 | 0 | 0 | 5 | 4/5 (80%) |
| sonnet.PD5_ThinkNarrationDominant | 0 | 0 | 0 | 0 | 0 | 0 | 23 | 23 | 23/23 (100%) |
| sonnet.R_NarrativeOverMatchedMagnitude | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 3 | 3/3 (100%) |
| sonnet.R_OscillationToCompromisePair | 3 | 1 | 0 | 0 | 0 | 0 | 0 | 4 | 1/4 (25%) |

### 1.3 Per-framework bias check

| Framework | agree | dispute-weak | dispute-strong | fabricated | misaligned | redundant | unverifiable | Total | Non-agree % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aiq | 220 | 77 | 0 | 0 | 8 | 0 | 185 | 490 | 55% |
| claudecode | 234 | 76 | 0 | 0 | 12 | 0 | 0 | 322 | 27% |
| qwen | 298 | 83 | 0 | 0 | 10 | 0 | 0 | 391 | 24% |
| sonnet | 88 | 36 | 0 | 0 | 6 | 0 | 26 | 156 | 44% |

---

## 2. Per-class action recommendation

| Class | N | Non-agree | Action |
|---|---:|---:|---|
| D1 | 100 | 23 | review (20-40% non-agree; N_judged=100) |
| D2 | 59 | 19 | review (20-40% non-agree; N_judged=59) |
| D3 | 50 | 19 | review (20-40% non-agree; N_judged=50) |
| D4 | 36 | 0 | OK (≤20% non-agree among judged; N_judged=36) |
| D5 | 30 | 28 | likely mis-induced — re-run Phase α (N_judged=30) |
| D6 | 23 | 2 | OK (≤20% non-agree among judged; N_judged=23) |
| D7 | 17 | 10 | significant label noise — targeted relabel pass recommended (N_judged=17) |
| PD_ErrorOnlyFilterBias | 38 | 0 | OK (≤20% non-agree among judged; N_judged=38) |
| PD_LateExplorationDegenerate | 25 | 11 | significant label noise — targeted relabel pass recommended (N_judged=25) |
| PD_MultiRCCompromise | 7 | 0 | OK (≤20% non-agree among judged; N_judged=7) |
| PD_NamedCandidateNotIsolated | 11 | 0 | OK (≤20% non-agree among judged; N_judged=11) |
| PD_NoBaselineContrast | 36 | 0 | OK (≤20% non-agree among judged; N_judged=36) |
| PD_NoCallTreeBuild | 109 | 0 | OK (≤20% non-agree among judged; N_judged=109) |
| PD_NoFaultLayerMetricProbe | 153 | 0 | OK (≤20% non-agree among judged; N_judged=153) |
| PD_SurveyWithoutDrill | 59 | 4 | OK (≤20% non-agree among judged; N_judged=59) |
| PD_TraceFollowAbsent | 5 | 0 | OK (≤20% non-agree among judged; N_judged=5) |
| U1_LoudnessAnchorOverSilentVictim | 218 | 149 | likely mis-induced — re-run Phase α (N_judged=218) |
| U2_ChronicAmbientNoiseAnchor | 27 | 14 | significant label noise — targeted relabel pass recommended (N_judged=27) — add 3-way alignment guard to Positive criteria |
| U3_EdgeDirectionOrRegionEndpointError | 28 | 0 | OK (≤20% non-agree among judged; N_judged=28) |
| U4_NameTwinSiblingConfusion | 18 | 1 | OK (≤20% non-agree among judged; N_judged=18) |
| U5_SilenceReadAsHealthOrPaused | 9 | 5 | significant label noise — targeted relabel pass recommended (N_judged=9) |
| aiq.PD_CompressOverwritesTerminator | 8 | 8 | unverifiable-by-evidence-dump (8/8) — needs trajectory-text analysis beyond parquet |
| aiq.PD_ReflectionStageWithoutNewProbe | 48 | 48 | unverifiable-by-evidence-dump (48/48) — needs trajectory-text analysis beyond parquet |
| aiq.PD_StageEndsWithoutCommitment | 108 | 108 | unverifiable-by-evidence-dump (108/108) — needs trajectory-text analysis beyond parquet |
| aiq.R_compress_drift | 8 | 8 | unverifiable-by-evidence-dump (8/8) — needs trajectory-text analysis beyond parquet |
| aiq.R_correct_then_reversed | 13 | 13 | unverifiable-by-evidence-dump (13/13) — needs trajectory-text analysis beyond parquet |
| aiq.R_hub_fabrication | 12 | 1 | OK (≤20% non-agree among judged; N_judged=12) |
| claudecode.PD4_GTServiceNotTargetedWithWhere | 26 | 0 | OK (≤20% non-agree among judged; N_judged=26) |
| claudecode.R6_InfraLayerSkipped | 7 | 5 | likely mis-induced — re-run Phase α (N_judged=7) |
| claudecode.R7_JVMSymptomMisreadAsDB | 4 | 0 | small class; insufficient N for verdict |
| qwen.PD6_ServiceAvgNoSpanMaxDrill | 18 | 11 | likely mis-induced — re-run Phase α (N_judged=18) |
| qwen.PD8_NoChronicityReasoning | 8 | 0 | OK (≤20% non-agree among judged; N_judged=8) |
| qwen.R_E_PathOvershootPastInjection | 6 | 1 | OK (≤20% non-agree among judged; N_judged=6) |
| qwen.R_F_QueryDesignBuriesSignal | 5 | 4 | likely mis-induced — re-run Phase α (N_judged=5) |
| sonnet.PD5_ThinkNarrationDominant | 23 | 23 | unverifiable-by-evidence-dump (23/23) — needs trajectory-text analysis beyond parquet |
| sonnet.R_NarrativeOverMatchedMagnitude | 3 | 3 | small class; insufficient N for verdict |
| sonnet.R_OscillationToCompromisePair | 4 | 1 | small class; insufficient N for verdict |

---

## 3. Fabricated D obstacles

Cases where D label was claimed but agent never reached GT path (gt_touched=False AND gt_neighbors_touched=∅). The 'data obstacle' was never encountered — failure is on R/PD axis, not D.

*(none detected)*

---

## 4. Misaligned R attribution

Cases where R label was claimed but gt_required_capabilities suggests a different reasoning failure. The R's implied 'failed capability' doesn't match what the case actually required.

| Agent | Case | Class | Suggested alternative | Reason |
|---|---|---|---|---|
| aiq | 1143 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| aiq | 1159 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| aiq | 1862 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| aiq | 2237 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| aiq | 2836 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| aiq | 3076 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| aiq | 3716 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| aiq | 572 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 1140 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| claudecode | 1143 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| claudecode | 1144 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| claudecode | 1159 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| claudecode | 1837 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| claudecode | 1862 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| claudecode | 1948 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| claudecode | 2235 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| claudecode | 3076 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| claudecode | 3716 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| claudecode | 572 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| claudecode | 864 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| qwen | 1140 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 1143 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| qwen | 2092 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| qwen | 2285 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| qwen | 2836 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 3120 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 3716 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| qwen | 4070 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| qwen | 572 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 832 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| sonnet | 1140 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| sonnet | 1144 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| sonnet | 1862 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| sonnet | 2174 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| sonnet | 2597 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| sonnet | 3107 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |

---

## 5. Redundant PD labels

Cases where PD was claimed but counterfactual shows the missing action would be a no-op. The action's precondition is absent (chronic noise absent for PD1, GT not upstream for PD2, etc.).

*(none detected)*

---

## 6. Dispute-strong details

*(none)*

---

## 7. Unverifiable cases

- **Requires aiq multi-stage probe analysis not in evidence dump**: aiq.1114 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.130 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.1459 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.1484 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.156 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.1562 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.1814 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.1917 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.2211 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.2237 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.2253 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.2258 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.2283 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.247 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.2678 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.2713 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.2715 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.283 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.2836 (aiq.PD_ReflectionStageWithoutNewProbe), aiq.3008 (aiq.PD_ReflectionStageWithoutNewProbe) …+28
- **Requires aiq 3-stage markers not in evidence dump**: aiq.1114 (aiq.PD_StageEndsWithoutCommitment), aiq.1140 (aiq.PD_StageEndsWithoutCommitment), aiq.1143 (aiq.PD_StageEndsWithoutCommitment), aiq.1159 (aiq.PD_StageEndsWithoutCommitment), aiq.1195 (aiq.PD_StageEndsWithoutCommitment), aiq.1218 (aiq.PD_StageEndsWithoutCommitment), aiq.1371 (aiq.PD_StageEndsWithoutCommitment), aiq.1394 (aiq.PD_StageEndsWithoutCommitment), aiq.1421 (aiq.PD_StageEndsWithoutCommitment), aiq.1459 (aiq.PD_StageEndsWithoutCommitment), aiq.1484 (aiq.PD_StageEndsWithoutCommitment), aiq.1495 (aiq.PD_StageEndsWithoutCommitment), aiq.1504 (aiq.PD_StageEndsWithoutCommitment), aiq.156 (aiq.PD_StageEndsWithoutCommitment), aiq.1562 (aiq.PD_StageEndsWithoutCommitment), aiq.1814 (aiq.PD_StageEndsWithoutCommitment), aiq.1860 (aiq.PD_StageEndsWithoutCommitment), aiq.1862 (aiq.PD_StageEndsWithoutCommitment), aiq.1880 (aiq.PD_StageEndsWithoutCommitment), aiq.1886 (aiq.PD_StageEndsWithoutCommitment) …+88
- **Requires aiq compress_to_graph analysis not in evidence dump**: aiq.1140 (aiq.PD_CompressOverwritesTerminator), aiq.1886 (aiq.PD_CompressOverwritesTerminator), aiq.2752 (aiq.PD_CompressOverwritesTerminator), aiq.2769 (aiq.PD_CompressOverwritesTerminator), aiq.3600 (aiq.PD_CompressOverwritesTerminator), aiq.4832 (aiq.PD_CompressOverwritesTerminator), aiq.603 (aiq.PD_CompressOverwritesTerminator), aiq.860 (aiq.PD_CompressOverwritesTerminator)
- **Requires aiq compress_to_graph stage analysis not in evidenc**: aiq.1140 (aiq.R_compress_drift), aiq.1886 (aiq.R_compress_drift), aiq.2752 (aiq.R_compress_drift), aiq.2769 (aiq.R_compress_drift), aiq.3600 (aiq.R_compress_drift), aiq.4832 (aiq.R_compress_drift), aiq.603 (aiq.R_compress_drift), aiq.860 (aiq.R_compress_drift)
- **Requires aiq 3-stage pipeline markers not present in evidenc**: aiq.156 (aiq.R_correct_then_reversed), aiq.1814 (aiq.R_correct_then_reversed), aiq.2283 (aiq.R_correct_then_reversed), aiq.2713 (aiq.R_correct_then_reversed), aiq.3008 (aiq.R_correct_then_reversed), aiq.3125 (aiq.R_correct_then_reversed), aiq.3278 (aiq.R_correct_then_reversed), aiq.3556 (aiq.R_correct_then_reversed), aiq.4257 (aiq.R_correct_then_reversed), aiq.4530 (aiq.R_correct_then_reversed), aiq.4740 (aiq.R_correct_then_reversed), aiq.4801 (aiq.R_correct_then_reversed), aiq.99 (aiq.R_correct_then_reversed)
- **Requires think_tool invocation count not in evidence dump**: sonnet.1140 (sonnet.PD5_ThinkNarrationDominant), sonnet.1326 (sonnet.PD5_ThinkNarrationDominant), sonnet.1421 (sonnet.PD5_ThinkNarrationDominant), sonnet.1880 (sonnet.PD5_ThinkNarrationDominant), sonnet.1948 (sonnet.PD5_ThinkNarrationDominant), sonnet.2174 (sonnet.PD5_ThinkNarrationDominant), sonnet.2584 (sonnet.PD5_ThinkNarrationDominant), sonnet.2597 (sonnet.PD5_ThinkNarrationDominant), sonnet.2616 (sonnet.PD5_ThinkNarrationDominant), sonnet.2748 (sonnet.PD5_ThinkNarrationDominant), sonnet.2830 (sonnet.PD5_ThinkNarrationDominant), sonnet.3033 (sonnet.PD5_ThinkNarrationDominant), sonnet.3107 (sonnet.PD5_ThinkNarrationDominant), sonnet.3112 (sonnet.PD5_ThinkNarrationDominant), sonnet.339 (sonnet.PD5_ThinkNarrationDominant), sonnet.3554 (sonnet.PD5_ThinkNarrationDominant), sonnet.3592 (sonnet.PD5_ThinkNarrationDominant), sonnet.3868 (sonnet.PD5_ThinkNarrationDominant), sonnet.4423 (sonnet.PD5_ThinkNarrationDominant), sonnet.4463 (sonnet.PD5_ThinkNarrationDominant) …+3
- **Requires narrative-text lexical analysis not in evidence dum**: sonnet.2541 (sonnet.R_NarrativeOverMatchedMagnitude), sonnet.3554 (sonnet.R_NarrativeOverMatchedMagnitude), sonnet.371 (sonnet.R_NarrativeOverMatchedMagnitude)

---

## 8. Red-zone PD re-evaluation

Coupling-red PDs per taxonomy: PD_NamedCandidateNotIsolated (V_r=0.54), PD_MultiRCCompromise (V_r=0.76). Partition verdicts and check redundancy rate.

### PD_NamedCandidateNotIsolated — N=11

- agree: 11 (100%)
- redundant: 0 (0%)
- misaligned/fabricated (spillover): 0 (0%)
- **Recommendation**: keep as unified PD

### PD_MultiRCCompromise — N=7

- agree: 7 (100%)
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

- **Overall agree rate**: 840/1359 (62%)
- **D axis**: 214/315 agree (68%)
- **R axis**: 157/362 agree (43%)
- **PD axis**: 469/682 agree (69%)

- **Fabricated D**: 0 (every fabricated means the D label is blaming data when the agent chose wrong path)
- **Misaligned R**: 36 (misattributed reasoning-defect class — GT didn't require the capability the R label blames)
- **Redundant PD**: 0 (PD label on cases where the missing action would change nothing)

> For per-case evidence see `merged/verify_evidence/<agent>_case_<id>.yaml`.
> For per-verdict row see `merged/verify_verdicts.jsonl`.
