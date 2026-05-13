# D / R / PD Label Re-Verification — Mismatch Report

**Scope**: 4 frameworks × ALL labeled failure cases. Distinct cases verified: 372. Class-verifications (D + R + multi-PD per case): 1972.
**Method**: three-way alignment (GT side + trajectory side + counterfactual parquet simulation). `agree` requires all three tests pass.
**Corpus**: all 372 cases from `D_projection.jsonl` + `PD_projection.jsonl` + DB `meta.failure_analysis.v1.R`.

---

## 1. Summary tables

### 1.1 Per-axis verdict counts

| Axis | agree | dispute-weak | dispute-strong | fabricated | misaligned | redundant | unverifiable | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D | 214 | 101 | 43 | 11 | 0 | 0 | 0 | 369 |
| R | 145 | 91 | 0 | 0 | 110 | 0 | 24 | 370 |
| PD | 469 | 26 | 219 | 0 | 0 | 332 | 187 | 1233 |

### 1.2 Per-class verdict breakdown

| Class | agree | dispute-weak | dispute-strong | fabricated | misaligned | redundant | unverifiable | Total | Non-agree rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D1 | 77 | 23 | 39 | 3 | 0 | 0 | 0 | 142 | 65/142 (46%) |
| D2 | 40 | 19 | 0 | 8 | 0 | 0 | 0 | 67 | 27/67 (40%) |
| D3 | 31 | 19 | 0 | 0 | 0 | 0 | 0 | 50 | 19/50 (38%) |
| D4 | 36 | 0 | 0 | 0 | 0 | 0 | 0 | 36 | 0/36 (0%) |
| D5 | 2 | 28 | 4 | 0 | 0 | 0 | 0 | 34 | 32/34 (94%) |
| D6 | 21 | 2 | 0 | 0 | 0 | 0 | 0 | 23 | 2/23 (9%) |
| D7 | 7 | 10 | 0 | 0 | 0 | 0 | 0 | 17 | 10/17 (59%) |
| PD_ErrorOnlyFilterBias | 38 | 0 | 0 | 0 | 0 | 35 | 0 | 73 | 35/73 (48%) |
| PD_LateExplorationDegenerate | 14 | 11 | 0 | 0 | 0 | 0 | 0 | 25 | 11/25 (44%) |
| PD_MultiRCCompromise | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 0/7 (0%) |
| PD_NamedCandidateNotIsolated | 11 | 0 | 70 | 0 | 0 | 0 | 0 | 81 | 70/81 (86%) |
| PD_NoBaselineContrast | 36 | 0 | 82 | 0 | 0 | 198 | 0 | 316 | 280/316 (89%) |
| PD_NoCallTreeBuild | 109 | 0 | 14 | 0 | 0 | 79 | 0 | 202 | 93/202 (46%) |
| PD_NoFaultLayerMetricProbe | 153 | 0 | 15 | 0 | 0 | 20 | 0 | 188 | 35/188 (19%) |
| PD_SurveyWithoutDrill | 55 | 4 | 0 | 0 | 0 | 0 | 0 | 59 | 4/59 (7%) |
| PD_TraceFollowAbsent | 5 | 0 | 1 | 0 | 0 | 0 | 0 | 6 | 1/6 (17%) |
| U1_LoudnessAnchorOverSilentVictim | 60 | 68 | 0 | 0 | 12 | 0 | 0 | 140 | 80/140 (57%) |
| U2_ChronicAmbientNoiseAnchor | 10 | 5 | 0 | 0 | 70 | 0 | 0 | 85 | 75/85 (88%) |
| U3_EdgeDirectionOrRegionEndpointError | 28 | 0 | 0 | 0 | 20 | 0 | 0 | 48 | 20/48 (42%) |
| U4_NameTwinSiblingConfusion | 17 | 1 | 0 | 0 | 0 | 0 | 0 | 18 | 1/18 (6%) |
| U5_SilenceReadAsHealthOrPaused | 4 | 5 | 0 | 0 | 8 | 0 | 0 | 17 | 13/17 (76%) |
| aiq.PD_CompressOverwritesTerminator | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 8 | 8/8 (100%) |
| aiq.PD_ReflectionStageWithoutNewProbe | 0 | 0 | 0 | 0 | 0 | 0 | 48 | 48 | 48/48 (100%) |
| aiq.PD_StageEndsWithoutCommitment | 0 | 0 | 0 | 0 | 0 | 0 | 108 | 108 | 108/108 (100%) |
| aiq.R_compress_drift | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 8 | 8/8 (100%) |
| aiq.R_correct_then_reversed | 0 | 0 | 0 | 0 | 0 | 0 | 13 | 13 | 13/13 (100%) |
| aiq.R_hub_fabrication | 11 | 1 | 0 | 0 | 0 | 0 | 0 | 12 | 1/12 (8%) |
| claudecode.PD4_GTServiceNotTargetedWithWhere | 26 | 0 | 37 | 0 | 0 | 0 | 0 | 63 | 37/63 (59%) |
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
| aiq | 218 | 69 | 54 | 0 | 18 | 124 | 185 | 668 | 67% |
| claudecode | 229 | 51 | 143 | 4 | 42 | 12 | 0 | 481 | 52% |
| qwen | 293 | 67 | 24 | 6 | 37 | 176 | 0 | 603 | 51% |
| sonnet | 88 | 31 | 41 | 1 | 13 | 20 | 26 | 220 | 60% |

---

## 2. Per-class action recommendation

| Class | N | Non-agree | Action |
|---|---:|---:|---|
| D1 | 142 | 65 | significant label noise — targeted relabel pass recommended (N_judged=142) |
| D2 | 67 | 27 | significant label noise — targeted relabel pass recommended (N_judged=67) |
| D3 | 50 | 19 | review (20-40% non-agree; N_judged=50) |
| D4 | 36 | 0 | OK (≤20% non-agree among judged; N_judged=36) |
| D5 | 34 | 32 | likely mis-induced — re-run Phase α (N_judged=34) |
| D6 | 23 | 2 | OK (≤20% non-agree among judged; N_judged=23) |
| D7 | 17 | 10 | significant label noise — targeted relabel pass recommended (N_judged=17) |
| PD_ErrorOnlyFilterBias | 73 | 35 | significant label noise — targeted relabel pass recommended (N_judged=73) — add 3-way alignment guard to Positive criteria |
| PD_LateExplorationDegenerate | 25 | 11 | significant label noise — targeted relabel pass recommended (N_judged=25) |
| PD_MultiRCCompromise | 7 | 0 | OK (≤20% non-agree among judged; N_judged=7) |
| PD_NamedCandidateNotIsolated | 81 | 70 | likely mis-induced — re-run Phase α (N_judged=81) |
| PD_NoBaselineContrast | 316 | 280 | likely mis-induced — re-run Phase α (N_judged=316) — add 3-way alignment guard to Positive criteria |
| PD_NoCallTreeBuild | 202 | 93 | significant label noise — targeted relabel pass recommended (N_judged=202) — add 3-way alignment guard to Positive criteria |
| PD_NoFaultLayerMetricProbe | 188 | 35 | OK (≤20% non-agree among judged; N_judged=188) |
| PD_SurveyWithoutDrill | 59 | 4 | OK (≤20% non-agree among judged; N_judged=59) |
| PD_TraceFollowAbsent | 6 | 1 | OK (≤20% non-agree among judged; N_judged=6) |
| U1_LoudnessAnchorOverSilentVictim | 140 | 80 | significant label noise — targeted relabel pass recommended (N_judged=140) |
| U2_ChronicAmbientNoiseAnchor | 85 | 75 | likely mis-induced — re-run Phase α (N_judged=85) — add 3-way alignment guard to Positive criteria |
| U3_EdgeDirectionOrRegionEndpointError | 48 | 20 | significant label noise — targeted relabel pass recommended (N_judged=48) — add 3-way alignment guard to Positive criteria |
| U4_NameTwinSiblingConfusion | 18 | 1 | OK (≤20% non-agree among judged; N_judged=18) |
| U5_SilenceReadAsHealthOrPaused | 17 | 13 | likely mis-induced — re-run Phase α (N_judged=17) — add 3-way alignment guard to Positive criteria |
| aiq.PD_CompressOverwritesTerminator | 8 | 8 | unverifiable-by-evidence-dump (8/8) — needs trajectory-text analysis beyond parquet |
| aiq.PD_ReflectionStageWithoutNewProbe | 48 | 48 | unverifiable-by-evidence-dump (48/48) — needs trajectory-text analysis beyond parquet |
| aiq.PD_StageEndsWithoutCommitment | 108 | 108 | unverifiable-by-evidence-dump (108/108) — needs trajectory-text analysis beyond parquet |
| aiq.R_compress_drift | 8 | 8 | unverifiable-by-evidence-dump (8/8) — needs trajectory-text analysis beyond parquet |
| aiq.R_correct_then_reversed | 13 | 13 | unverifiable-by-evidence-dump (13/13) — needs trajectory-text analysis beyond parquet |
| aiq.R_hub_fabrication | 12 | 1 | OK (≤20% non-agree among judged; N_judged=12) |
| claudecode.PD4_GTServiceNotTargetedWithWhere | 63 | 37 | significant label noise — targeted relabel pass recommended (N_judged=63) |
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

| Agent | Case | Class | Suggested alternative | Reason |
|---|---|---|---|---|
| claudecode | 1004 | D2 |  | D2 Positive ok but agent never reached GT path |
| claudecode | 283 | D2 |  | D2 Positive ok but agent never reached GT path |
| claudecode | 339 | D2 |  | D2 Positive ok but agent never reached GT path |
| claudecode | 3868 | D1 | PD_NamedCandidateNotIsolated | D1 Positive ok but agent never reached GT path |
| qwen | 2130 | D2 |  | D2 Positive ok but agent never reached GT path |
| qwen | 283 | D2 |  | D2 Positive ok but agent never reached GT path |
| qwen | 3622 | D2 |  | D2 Positive ok but agent never reached GT path |
| qwen | 3673 | D1 | PD_NamedCandidateNotIsolated | D1 Positive ok but agent never reached GT path |
| qwen | 4463 | D1 | PD_NamedCandidateNotIsolated | D1 Positive ok but agent never reached GT path |
| qwen | 4841 | D2 |  | D2 Positive ok but agent never reached GT path |
| sonnet | 323 | D2 |  | D2 Positive ok but agent never reached GT path |

---

## 4. Misaligned R attribution

Cases where R label was claimed but gt_required_capabilities suggests a different reasoning failure. The R's implied 'failed capability' doesn't match what the case actually required.

| Agent | Case | Class | Suggested alternative | Reason |
|---|---|---|---|---|
| aiq | 1143 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| aiq | 1159 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| aiq | 1504 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| aiq | 1862 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| aiq | 2237 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| aiq | 2597 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| aiq | 281 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| aiq | 2836 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| aiq | 3059 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| aiq | 3076 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| aiq | 3128 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| aiq | 3622 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| aiq | 3716 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| aiq | 4363 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| aiq | 4715 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| aiq | 572 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| aiq | 601 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| aiq | 804 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 1004 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 1114 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| claudecode | 1118 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 1140 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 1143 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 1144 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 1159 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 1495 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| claudecode | 156 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| claudecode | 1686 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 1814 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| claudecode | 1837 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| claudecode | 1862 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 1886 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| claudecode | 1948 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| claudecode | 2231 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 2235 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 2390 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| claudecode | 2512 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 2585 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| claudecode | 2641 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 2716 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 2988 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 3041 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 3076 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 3114 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 323 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 3391 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 3555 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 3622 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 3716 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 3966 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 4054 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 4229 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 4258 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| claudecode | 4791 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 4823 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 551 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| claudecode | 572 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 741 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| claudecode | 762 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| claudecode | 864 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 1140 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| qwen | 1143 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 1421 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 1515 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 156 | U5_SilenceReadAsHealthOrPaused |  | U5 requires silent GT but GT has signal |
| qwen | 1846 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| qwen | 2092 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 2231 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 2285 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 2390 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 2512 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 2700 | U5_SilenceReadAsHealthOrPaused |  | U5 requires silent GT but GT has signal |
| qwen | 2716 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 283 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 2836 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| qwen | 3059 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 3114 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| qwen | 3120 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| qwen | 315 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 3222 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 33 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 3622 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 3673 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| qwen | 3716 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 3868 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 3920 | U5_SilenceReadAsHealthOrPaused |  | U5 requires silent GT but GT has signal |
| qwen | 4070 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 4309 | U5_SilenceReadAsHealthOrPaused |  | U5 requires silent GT but GT has signal |
| qwen | 4363 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 4463 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| qwen | 4617 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 4707 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| qwen | 4841 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| qwen | 572 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| qwen | 579 | U5_SilenceReadAsHealthOrPaused |  | U5 requires silent GT but GT has signal |
| qwen | 807 | U5_SilenceReadAsHealthOrPaused |  | U5 requires silent GT but GT has signal |
| qwen | 832 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| sonnet | 1140 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| sonnet | 1144 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| sonnet | 1280 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| sonnet | 1862 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| sonnet | 1948 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| sonnet | 2174 | U1_LoudnessAnchorOverSilentVictim | U2 or U3 | U1 requires silent victim but GT is loudest — misattribution |
| sonnet | 2597 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| sonnet | 3107 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| sonnet | 3112 | U2_ChronicAmbientNoiseAnchor | U1 or U3 | U2 requires RC=chronic carrier; agent picked non-chronic |
| sonnet | 3236 | U5_SilenceReadAsHealthOrPaused |  | U5 requires silent GT but GT has signal |
| sonnet | 4433 | U5_SilenceReadAsHealthOrPaused |  | U5 requires silent GT but GT has signal |
| sonnet | 471 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |
| sonnet | 4739 | U3_EdgeDirectionOrRegionEndpointError | U1 or U2 | U3 requires edge fault but fault is not edge-level |

---

## 5. Redundant PD labels

Cases where PD was claimed but counterfactual shows the missing action would be a no-op. The action's precondition is absent (chronic noise absent for PD1, GT not upstream for PD2, etc.).

| Agent | Case | Class | Reason |
|---|---|---|---|
| aiq | 1114 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1140 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1143 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1159 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1218 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 130 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 1371 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1421 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 1459 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1484 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1495 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1504 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 156 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1562 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1814 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1860 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1860 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 1862 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1880 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1886 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1917 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 1917 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 1934 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 2130 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2130 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 2211 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2231 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2237 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2253 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2258 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2283 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2390 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2390 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 247 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 247 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 2479 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2584 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2585 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2678 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2697 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2715 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2752 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2761 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 2769 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 281 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 281 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 283 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 283 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 2836 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3053 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3053 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 3059 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3076 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3222 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 323 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3266 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3266 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 3278 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3284 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3325 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3465 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3556 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3600 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3600 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 3622 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3622 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 3673 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3673 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 3700 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3700 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 3716 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3760 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3776 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3868 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3868 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 3878 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3920 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 3955 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 4032 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4054 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4073 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4081 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4229 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4257 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4257 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 4258 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4258 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 4309 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4309 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 4310 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4353 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4353 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 4363 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4363 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 4375 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4423 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4463 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 4510 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4530 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4617 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4617 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 4715 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4715 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 4740 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4789 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4789 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 4801 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4832 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 4841 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 572 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 601 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 601 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 710 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 741 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 741 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 784 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 804 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 804 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 807 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 807 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| aiq | 860 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 885 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 99 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| aiq | 99 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| claudecode | 1195 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| claudecode | 1837 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| claudecode | 2390 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| claudecode | 281 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| claudecode | 3920 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| claudecode | 3966 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| claudecode | 4054 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| claudecode | 4363 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| claudecode | 4789 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| claudecode | 4791 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| claudecode | 4823 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| claudecode | 807 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 1140 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 1140 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1143 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 1143 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1195 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1195 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 1218 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1254 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPRequestReplaceMethod |
| qwen | 130 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 1371 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1394 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1421 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1435 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 1459 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1459 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 1495 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1515 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 1515 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1515 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPRequestDelay |
| qwen | 156 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 156 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 156 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 1814 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1846 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1846 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 1880 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1880 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponseReplaceBody |
| qwen | 1917 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1917 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 1934 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 1934 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 1948 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 2092 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 2092 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2092 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPRequestReplacePath |
| qwen | 2130 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2130 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 2211 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 2211 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2231 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 2231 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2231 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPRequestDelay |
| qwen | 2253 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 2253 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2258 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 2258 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2285 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 2285 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2285 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponseAbort |
| qwen | 2390 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2390 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 247 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2512 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 2512 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2598 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 2598 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPRequestDelay |
| qwen | 2641 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 2641 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2641 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponseDelay |
| qwen | 2678 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2700 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2715 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2716 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 281 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 281 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 283 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 283 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 2836 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 2836 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 2836 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponseReplaceBody |
| qwen | 2988 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3059 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 3059 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3114 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 3120 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3120 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPRequestReplacePath |
| qwen | 3125 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 3125 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3125 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponseDelay |
| qwen | 3128 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 3128 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponseDelay |
| qwen | 3138 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3138 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 315 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 315 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponseDelay |
| qwen | 3219 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 3219 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3222 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 3222 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 323 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3278 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 33 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 339 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3393 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3393 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponseDelay |
| qwen | 341 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3524 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3552 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 3552 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3592 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 3592 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3592 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponseDelay |
| qwen | 3605 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3622 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3622 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 3673 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3673 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 3716 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 3716 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3760 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3760 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 3776 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3868 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3868 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 3878 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3878 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 3920 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 3920 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3920 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 3955 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 3955 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 4032 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4055 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4070 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 4070 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4070 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponseAbort |
| qwen | 4081 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4081 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 4151 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4151 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 4229 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4258 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4309 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 4309 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4309 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 4311 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 4311 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4311 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 4353 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 4353 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4353 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 4363 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4363 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 4375 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4463 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 4510 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4519 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4530 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4617 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4617 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 4707 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 4707 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponseReplaceBody |
| qwen | 4758 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4789 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4841 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 4841 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 4893 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 4893 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 572 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 572 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponsePatchBody |
| qwen | 579 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 755 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 784 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 784 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 804 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 807 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 807 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 832 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 832 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| qwen | 860 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 860 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 860 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponseReplaceBody |
| qwen | 864 | PD_ErrorOnlyFilterBias | PD5 fires but GT has error signal — unset filter wouldn't help |
| qwen | 864 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| qwen | 864 | PD_NoFaultLayerMetricProbe | PD3: no specific metric layer required for fault_type=HTTPResponseReplaceCode |
| qwen | 99 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 1144 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 1280 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 1326 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 1421 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 1862 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 2616 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 2678 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 2715 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 2748 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 2801 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 323 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 3236 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 3555 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 3592 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 4423 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 4510 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 471 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 471 | PD_NoCallTreeBuild | PD2 fires but GT is not upstream — call_tree wouldn't surface it |
| sonnet | 4739 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |
| sonnet | 675 | PD_NoBaselineContrast | PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity |

---

## 6. Dispute-strong details

### aiq.1143 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-rabbitmq'] in WHERE filters ['ts-food-service', 'ts-rabbitmq', 'ts-ui-dashboard', 'ts-delivery-service', 'ts-notification-service', 'ts-train-food-service', 'ts-preserve-service', 'ts-station-food-service']
- **evidence**: `merged/verify_evidence/aiq_case_1143.yaml`

### aiq.1159 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-rabbitmq'] in WHERE filters ['rabbitmq', 'ts-ui-dashboard', 'ts-food-service', 'ts-rabbitmq', 'ts-delivery-service', 'ts-notification-service']
- **evidence**: `merged/verify_evidence/aiq_case_1159.yaml`

### aiq.1195 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-food-service', 'ts-delivery-service', 'ts-notification-service'] in WHERE filters ['ts-security-service', 'ts-order-service', 'ts-order-other-service', 'ts-ui-dashboard', 'ts-food-service', 'ts-travel-plan-service', 'ts-travel2-service', 'ts-travel-service', 'ts-seat-service', 'ts-route-service', 'ts-config-service', 'ts-delivery-service', 'ts-notification-service']
- **evidence**: `merged/verify_evidence/aiq_case_1195.yaml`

### aiq.130 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-food-service'] in WHERE filters ['ts-preserve-service', 'ts-food-service', 'ts-delivery-service', 'ts-notification-service', 'ts-ui-dashboard', 'ts-order-service', 'ts-travel-service', 'ts-order-other-service', 'ts-travel-plan-service', 'ts-preserve-other-service']
- **evidence**: `merged/verify_evidence/aiq_case_130.yaml`

### aiq.1394 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/aiq_case_1394.yaml`

### aiq.1421 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/aiq_case_1421.yaml`

### aiq.1459 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=6>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/aiq_case_1459.yaml`

### aiq.1504 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['rabbitmq'] in WHERE filters ['rabbitmq', 'mysql', 'ts-food-service', 'ts-delivery-service', 'ts-notification-service', 'ts-travel-plan-service', 'ts-route-plan-service', 'ts-travel-service', 'foodservice', 'travelservice', 'ts-ui-dashboard', 'ts-preserve-service', 'preserveservice', 'travelplanservice']
- **evidence**: `merged/verify_evidence/aiq_case_1504.yaml`

### aiq.156 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=20>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/aiq_case_156.yaml`

### aiq.1862 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-rabbitmq'] in WHERE filters ['ts-food-service', 'ts-train-food-service', 'ts-preserve-service', 'ts-rabbitmq', 'rabbitmq', 'ts-delivery-service', 'ts-notification-service', 'ts-ui-dashboard', 'ts-food-delivery-service', 'ts-station-food-service']
- **evidence**: `merged/verify_evidence/aiq_case_1862.yaml`

### aiq.1880 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=1412>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/aiq_case_1880.yaml`

### aiq.1880 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-route-service'] in WHERE filters ['ts-route-service', 'ts-food-service', 'ts-ui-dashboard']
- **evidence**: `merged/verify_evidence/aiq_case_1880.yaml`

### aiq.1934 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/aiq_case_1934.yaml`

### aiq.2130 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-route-service'] in WHERE filters ['ts-basic-service', 'ts-route-service', 'ts-station-service', 'ts-preserve-service', 'ts-travel-service', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/aiq_case_2130.yaml`

### aiq.2237 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=1509>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/aiq_case_2237.yaml`

### aiq.2283 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=5722>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/aiq_case_2283.yaml`

### aiq.2584 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-order-other-service'] in WHERE filters ['ts-ui-dashboard', 'ts-preserve-service', 'ts-security-service', 'ts-order-other-service', 'ts-travel-service', 'ts-order-service']
- **evidence**: `merged/verify_evidence/aiq_case_2584.yaml`

### aiq.2585 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=100>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/aiq_case_2585.yaml`

### aiq.2585 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-route-service'] in WHERE filters ['ts-ui-dashboard', 'ts-preserve-service', 'ts-order-service', 'ts-basic-service', 'ts-route-service', 'ts-travel-service', 'loadgenerator']
- **evidence**: `merged/verify_evidence/aiq_case_2585.yaml`

### aiq.2700 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=10>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/aiq_case_2700.yaml`

### aiq.2700 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-order-service'] in WHERE filters ['ts-preserve-service', 'ts-order-service', 'ts-order-other-service', 'ts-security-service', 'loadgenerator', 'ts-ui-dashboard', 'ts-preserve-other-service']
- **evidence**: `merged/verify_evidence/aiq_case_2700.yaml`

### aiq.281 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-rabbitmq'] in WHERE filters ['ts-food-service', 'rabbitmq', 'ts-station-food-service', 'ts-rabbitmq', 'ts-notification-service', 'ts-ui-dashboard', 'ts-delivery-service', 'loadgenerator']
- **evidence**: `merged/verify_evidence/aiq_case_281.yaml`

### aiq.2836 — D5 (D)

- **positive_criteria**: FAIL (GT is loudest — no cascade decoy)
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: n/a
- **reason**: D5 requires cascade louder than GT but GT itself is top-ranked
- **evidence**: `merged/verify_evidence/aiq_case_2836.yaml`

### aiq.3008 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=25>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/aiq_case_3008.yaml`

### aiq.3059 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['rabbitmq'] in WHERE filters ['ts-travel-plan-service', 'ts-ui-dashboard', 'ts-basic-service', 'rabbitmq', 'ts-notification-service', 'ts-food-service', 'ts-delivery-service', 'ts-order-service', 'ts-preserve-service', 'ts-travel-service']
- **evidence**: `merged/verify_evidence/aiq_case_3059.yaml`

### aiq.3076 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-rabbitmq'] in WHERE filters ['ts-ui-dashboard', 'ts-order-service', 'ts-rabbitmq', 'ts-food-service', 'ts-delivery-service', 'ts-notification-service']
- **evidence**: `merged/verify_evidence/aiq_case_3076.yaml`

### aiq.3125 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=54>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/aiq_case_3125.yaml`

### aiq.315 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/aiq_case_315.yaml`

### aiq.3222 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=6>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/aiq_case_3222.yaml`

### aiq.3222 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed network/db)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has network/db metric in SQL substrings
- **evidence**: `merged/verify_evidence/aiq_case_3222.yaml`

### aiq.323 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-config-service'] in WHERE filters ['ts-travel-plan-service', 'ts-route-plan-service', 'ts-config-service', 'ts-seat-service', 'ts-ui-dashboard']
- **evidence**: `merged/verify_evidence/aiq_case_323.yaml`

### aiq.3284 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-route-service'] in WHERE filters ['ts-travel-plan-service', 'ts-route-service', 'ts-route-plan-service', 'ts-ui-dashboard', 'ts-basic-service', 'ts-travel-service']
- **evidence**: `merged/verify_evidence/aiq_case_3284.yaml`

### aiq.3465 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-route-plan-service'] in WHERE filters ['ts-travel-plan-service', 'ts-travel2-service', 'ts-route-plan-service', 'ts-basic-service', 'ts-price-service', 'ts-seat-service', 'ts-ui-dashboard', 'ts-station-service', 'ts-preserve-service', 'ts-delivery-service', 'ts-travel-service', 'ts-notification-service', 'ts-train-service', 'ts-route-service', 'ts-food-service']
- **evidence**: `merged/verify_evidence/aiq_case_3465.yaml`

### aiq.3622 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-rabbitmq'] in WHERE filters ['ts-food-service', 'ts-travel-plan-service', 'ts-rabbitmq', 'rabbitmq', 'ts-delivery-service', 'ts-notification-service']
- **evidence**: `merged/verify_evidence/aiq_case_3622.yaml`

### aiq.3700 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-ticket-office-service'] in WHERE filters ['ts-seat-service', 'ts-order-service', 'ts-ticket-office-service', 'ts-route-service', 'ts-route-plan-service', 'ts-ui-dashboard', 'ts-travel2-service', 'ts-basic-service', 'ts-travel-service', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/aiq_case_3700.yaml`

### aiq.3716 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-rabbitmq'] in WHERE filters ['ts-food-service', 'ts-rabbitmq', 'ts-preserve-service', 'ts-ui-dashboard', 'ts-delivery-service', 'ts-notification-service']
- **evidence**: `merged/verify_evidence/aiq_case_3716.yaml`

### aiq.3920 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-inside-payment-service'] in WHERE filters ['ts-inside-payment-service', 'ts-payment-service', 'loadgenerator', 'ts-order-service', 'ts-ui-dashboard']
- **evidence**: `merged/verify_evidence/aiq_case_3920.yaml`

### aiq.3955 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-food-service'] in WHERE filters ['ts-ui-dashboard', 'ts-food-service', 'ts-train-food-service', 'loadgenerator', 'ts-travel-service', 'ts-route-service']
- **evidence**: `merged/verify_evidence/aiq_case_3955.yaml`

### aiq.3966 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-food-service'] in WHERE filters ['ts-food-service', 'ts-train-food-service', 'ts-station-food-service', 'loadgenerator', 'ts-order-service', 'ts-ui-dashboard', 'ts-preserve-service', 'ts-delivery-service', 'ts-notification-service']
- **evidence**: `merged/verify_evidence/aiq_case_3966.yaml`

### aiq.4054 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-consign-service'] in WHERE filters ['ts-consign-service', 'ts-delivery-service', 'ts-food-service', 'ts-consign-price-service', 'ts-order-service']
- **evidence**: `merged/verify_evidence/aiq_case_4054.yaml`

### aiq.4073 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['mysql'] in WHERE filters ['ts-inside-payment-service', 'ts-ui-dashboard', 'mysql', 'ts-food-service', 'ts-order-service', 'ts-payment-service']
- **evidence**: `merged/verify_evidence/aiq_case_4073.yaml`

### aiq.4229 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-route-plan-service'] in WHERE filters ['ts-route-plan-service', 'ts-travel-plan-service', 'ts-ui-dashboard', 'ts-seat-service', 'ts-travel2-service']
- **evidence**: `merged/verify_evidence/aiq_case_4229.yaml`

### aiq.4309 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-inside-payment-service'] in WHERE filters ['ts-inside-payment-service', 'ts-order-service', 'ts-food-service', 'ts-payment-service', 'loadgenerator', 'ts-ui-dashboard']
- **evidence**: `merged/verify_evidence/aiq_case_4309.yaml`

### aiq.4310 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-inside-payment-service'] in WHERE filters ['ts-inside-payment-service', 'ts-payment-service', 'ts-ui-dashboard']
- **evidence**: `merged/verify_evidence/aiq_case_4310.yaml`

### aiq.4353 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=13>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/aiq_case_4353.yaml`

### aiq.4363 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-rabbitmq'] in WHERE filters ['ts-food-service', 'rabbitmq', 'ts-rabbitmq', 'ts-notification-service', 'ts-station-food-service', 'ts-order-service', 'ts-ui-dashboard', 'ts-train-food-service', 'ts-preserve-service', 'ts-delivery-service']
- **evidence**: `merged/verify_evidence/aiq_case_4363.yaml`

### aiq.4463 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-food-service'] in WHERE filters ['ts-ui-dashboard', 'ts-food-service', 'ts-train-food-service', 'ts-travel-service', 'ts-route-service', 'ts-station-food-service']
- **evidence**: `merged/verify_evidence/aiq_case_4463.yaml`

### aiq.4617 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['mysql'] in WHERE filters ['ts-station-service', 'ts-cancel-service', 'ts-ui-dashboard', 'mysql']
- **evidence**: `merged/verify_evidence/aiq_case_4617.yaml`

### aiq.4715 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-rabbitmq'] in WHERE filters ['ts-food-service', 'ts-rabbitmq', 'ts-delivery-service', 'ts-notification-service', 'foodservice', 'ts-ui-dashboard']
- **evidence**: `merged/verify_evidence/aiq_case_4715.yaml`

### aiq.4841 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-food-service'] in WHERE filters ['ts-food-service', 'ts-preserve-service', 'ts-ticket-office-service', 'rabbitmq', 'ts-order-service', 'travelservice', 'ts-travel2-service', 'travel2service', 'ts-delivery-service', 'ts-notification-service', 'ts-travel-service', 'preserveservice', 'ts-travel-plan-service', 'travelplanservice']
- **evidence**: `merged/verify_evidence/aiq_case_4841.yaml`

### aiq.572 — D5 (D)

- **positive_criteria**: FAIL (GT is loudest — no cascade decoy)
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: n/a
- **reason**: D5 requires cascade louder than GT but GT itself is top-ranked
- **evidence**: `merged/verify_evidence/aiq_case_572.yaml`

### aiq.601 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-rabbitmq'] in WHERE filters ['ts-basic-service', 'ts-route-plan-service', 'ts-rabbitmq', 'ts-delivery-service', 'ts-notification-service', 'ts-travel-service', 'ts-order-service', 'ts-seat-service']
- **evidence**: `merged/verify_evidence/aiq_case_601.yaml`

### aiq.784 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-food-service'] in WHERE filters ['ts-station-food-service', 'ts-ui-dashboard', 'ts-food-service', 'ts-train-food-service', 'loadgenerator']
- **evidence**: `merged/verify_evidence/aiq_case_784.yaml`

### aiq.804 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['rabbitmq'] in WHERE filters ['ts-ui-dashboard', 'ts-basic-service', 'loadgenerator', 'rabbitmq', 'ts-travel-plan-service', 'ts-route-plan-service', 'ts-travel2-service', 'ts-price-service', 'ts-route-service', 'ts-train-service', 'travelservice', 'ts-station-service', 'ts-delivery-service', 'ts-notification-service', 'trainservice', 'ts-travel-service', 'preserveservice', 'travelplanservice']
- **evidence**: `merged/verify_evidence/aiq_case_804.yaml`

### claudecode.1004 — PD_NoCallTreeBuild (PD)

- **positive_criteria**: FAIL (call_tree_build fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join
- **evidence**: `merged/verify_evidence/claudecode_case_1004.yaml`

### claudecode.1114 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1114.yaml`

### claudecode.1114 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-config-service'] is in WHERE filters ['ts-food-service', 'ts-seat-service', 'ts-route-plan-service', 'loadgenerator', 'ts-order-service', 'ts-config-service', 'ts-ui-dashboard', 'ts-travel-service', 'ts-order-other-service', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/claudecode_case_1114.yaml`

### claudecode.1118 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1118.yaml`

### claudecode.1140 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1140.yaml`

### claudecode.1140 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-food-service', 'ts-ui-dashboard'] is in WHERE filters ['ts-consign-service', 'ts-ui-dashboard']
- **evidence**: `merged/verify_evidence/claudecode_case_1140.yaml`

### claudecode.1143 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=139>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/claudecode_case_1143.yaml`

### claudecode.1143 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1143.yaml`

### claudecode.1144 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=184>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/claudecode_case_1144.yaml`

### claudecode.1159 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-food-service', 'ts-train-food-service'] is in WHERE filters ['ts-food-service', 'ts-notification-service', 'ts-delivery-service', 'ts-preserve-service', 'ts-ui-dashboard', 'ts-order-service']
- **evidence**: `merged/verify_evidence/claudecode_case_1159.yaml`

### claudecode.1195 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1195.yaml`

### claudecode.1218 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-order-service'] is in WHERE filters ['ts-seat-service', 'mysql', 'ts-order-other-service', 'ts-order-service', 'ts-config-service']
- **evidence**: `merged/verify_evidence/claudecode_case_1218.yaml`

### claudecode.1280 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-order-service', 'ts-rabbitmq'] in WHERE filters ['ts-food-service', 'ts-preserve-service', 'ts-order-service']
- **evidence**: `merged/verify_evidence/claudecode_case_1280.yaml`

### claudecode.1280 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1280.yaml`

### claudecode.1371 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1371.yaml`

### claudecode.1394 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1394.yaml`

### claudecode.1394 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed jvm)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has jvm metric in SQL substrings
- **evidence**: `merged/verify_evidence/claudecode_case_1394.yaml`

### claudecode.1421 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1421.yaml`

### claudecode.1435 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1435.yaml`

### claudecode.1459 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=6>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/claudecode_case_1459.yaml`

### claudecode.1459 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed jvm)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has jvm metric in SQL substrings
- **evidence**: `merged/verify_evidence/claudecode_case_1459.yaml`

### claudecode.1484 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1484.yaml`

### claudecode.1484 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-travel-plan-service', 'ts-train-service'] is in WHERE filters ['ts-travel-plan-service', 'ts-route-plan-service', 'ts-travel2-service', 'ts-seat-service', 'ts-delivery-service', 'ts-notification-service', 'ts-order-service', 'ts-basic-service']
- **evidence**: `merged/verify_evidence/claudecode_case_1484.yaml`

### claudecode.1495 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1495.yaml`

### claudecode.156 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=20>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/claudecode_case_156.yaml`

### claudecode.156 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_156.yaml`

### claudecode.156 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-order-service'] is in WHERE filters ['ts-seat-service', 'ts-ui-dashboard', 'loadgenerator', 'ts-travel-plan-service', 'ts-inside-payment-service', 'ts-preserve-service', 'ts-order-service', 'ts-config-service', 'ts-order-other-service', 'ts-cancel-service']
- **evidence**: `merged/verify_evidence/claudecode_case_156.yaml`

### claudecode.1686 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1686.yaml`

### claudecode.1814 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1814.yaml`

### claudecode.1837 — D5 (D)

- **positive_criteria**: FAIL (GT is loudest — no cascade decoy)
- **gt_required_capability**: FAIL
- **path_alignment**: FAIL
- **counterfactual**: n/a
- **reason**: D5 requires cascade louder than GT but GT itself is top-ranked
- **evidence**: `merged/verify_evidence/claudecode_case_1837.yaml`

### claudecode.1862 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=156>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/claudecode_case_1862.yaml`

### claudecode.1862 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1862.yaml`

### claudecode.1875 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-food-service', 'ts-travel-service'] is in WHERE filters ['ts-food-service', 'ts-station-food-service', 'ts-notification-service', 'ts-delivery-service', 'rabbitmq', 'ts-ui-dashboard', 'ts-travel-service']
- **evidence**: `merged/verify_evidence/claudecode_case_1875.yaml`

### claudecode.1880 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1880.yaml`

### claudecode.1880 — PD_NoCallTreeBuild (PD)

- **positive_criteria**: FAIL (call_tree_build fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join
- **evidence**: `merged/verify_evidence/claudecode_case_1880.yaml`

### claudecode.1880 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-food-service', 'ts-travel-service'] is in WHERE filters ['ts-train-food-service', 'ts-route-service', 'ts-travel-service', 'ts-food-service']
- **evidence**: `merged/verify_evidence/claudecode_case_1880.yaml`

### claudecode.1886 — PD_NoCallTreeBuild (PD)

- **positive_criteria**: FAIL (call_tree_build fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join
- **evidence**: `merged/verify_evidence/claudecode_case_1886.yaml`

### claudecode.1917 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=53>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/claudecode_case_1917.yaml`

### claudecode.1917 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1917.yaml`

### claudecode.1934 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1934.yaml`

### claudecode.1948 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=80>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/claudecode_case_1948.yaml`

### claudecode.1948 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_1948.yaml`

### claudecode.1948 — PD_NoCallTreeBuild (PD)

- **positive_criteria**: FAIL (call_tree_build fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join
- **evidence**: `merged/verify_evidence/claudecode_case_1948.yaml`

### claudecode.2130 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_2130.yaml`

### claudecode.2211 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_2211.yaml`

### claudecode.2231 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_2231.yaml`

### claudecode.2231 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-travel-service', 'ts-route-service'] is in WHERE filters ['ts-travel-service', 'ts-basic-service', 'ts-seat-service', 'rabbitmq', 'ts-food-service', 'ts-train-food-service']
- **evidence**: `merged/verify_evidence/claudecode_case_2231.yaml`

### claudecode.2235 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_2235.yaml`

### claudecode.2235 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-travel-service', 'ts-seat-service'] is in WHERE filters ['ts-seat-service', 'ts-travel-service', 'ts-basic-service', 'ts-route-plan-service', 'ts-preserve-service', 'ts-station-service', 'ts-ui-dashboard', 'ts-price-service', 'ts-train-service', 'ts-travel-plan-service', 'ts-route-service']
- **evidence**: `merged/verify_evidence/claudecode_case_2235.yaml`

### claudecode.2245 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_2245.yaml`

### claudecode.2245 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-travel-service', 'ts-basic-service'] is in WHERE filters ['ts-route-plan-service', 'ts-basic-service', 'ts-travel-service', 'ts-route-service', 'ts-travel-plan-service', 'ts-notification-service', 'ts-food-service', 'ts-delivery-service', 'ts-station-service', 'ts-travel2-service']
- **evidence**: `merged/verify_evidence/claudecode_case_2245.yaml`

### claudecode.2258 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_2258.yaml`

### claudecode.2258 — PD_NoCallTreeBuild (PD)

- **positive_criteria**: FAIL (call_tree_build fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join
- **evidence**: `merged/verify_evidence/claudecode_case_2258.yaml`

### claudecode.2258 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-travel2-service'] is in WHERE filters ['ts-route-plan-service', 'ts-order-service', 'ts-ui-dashboard', 'ts-travel2-service', 'ts-travel-service', 'ts-travel-plan-service', 'ts-route-service']
- **evidence**: `merged/verify_evidence/claudecode_case_2258.yaml`

### claudecode.247 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_247.yaml`

### claudecode.2489 — PD_NoCallTreeBuild (PD)

- **positive_criteria**: FAIL (call_tree_build fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join
- **evidence**: `merged/verify_evidence/claudecode_case_2489.yaml`

### claudecode.2489 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-consign-service', 'ts-ui-dashboard'] is in WHERE filters ['ts-consign-service', 'ts-ui-dashboard', 'ts-food-service', 'ts-contacts-service']
- **evidence**: `merged/verify_evidence/claudecode_case_2489.yaml`

### claudecode.2512 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-rabbitmq'] in WHERE filters ['ts-food-service', 'ts-delivery-service', 'ts-notification-service', 'ts-rabbitmq']
- **evidence**: `merged/verify_evidence/claudecode_case_2512.yaml`

### claudecode.2512 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_2512.yaml`

### claudecode.2512 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-food-service', 'ts-station-food-service'] is in WHERE filters ['ts-food-service', 'ts-delivery-service', 'ts-notification-service', 'ts-rabbitmq']
- **evidence**: `merged/verify_evidence/claudecode_case_2512.yaml`

### claudecode.2585 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=100>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/claudecode_case_2585.yaml`

### claudecode.2585 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_2585.yaml`

### claudecode.2641 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-route-plan-service', 'ts-travel-service'] is in WHERE filters ['ts-route-plan-service', 'ts-route-service', 'ts-basic-service', 'ts-train-service', 'ts-travel-service', 'ts-travel2-service', 'ts-seat-service', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/claudecode_case_2641.yaml`

### claudecode.2647 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-route-plan-service', 'ts-travel2-service'] is in WHERE filters ['ts-route-plan-service', 'ts-travel-service', 'ts-travel2-service', 'ts-ui-dashboard', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/claudecode_case_2647.yaml`

### claudecode.2678 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_2678.yaml`

### claudecode.2678 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-seat-service', 'ts-config-service'] is in WHERE filters ['ts-travel2-service', 'ts-route-service', 'ts-seat-service', 'ts-basic-service']
- **evidence**: `merged/verify_evidence/claudecode_case_2678.yaml`

### claudecode.2694 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_2694.yaml`

### claudecode.2694 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-seat-service', 'ts-config-service'] is in WHERE filters ['ts-seat-service', 'ts-travel2-service', 'ts-route-plan-service', 'ts-order-other-service', 'ts-order-service', 'ts-ui-dashboard', 'ts-travel-service', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/claudecode_case_2694.yaml`

### claudecode.2715 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_2715.yaml`

### claudecode.2716 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_2716.yaml`

### claudecode.2808 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_2808.yaml`

### claudecode.281 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=9>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/claudecode_case_281.yaml`

### claudecode.281 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_281.yaml`

### claudecode.283 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_283.yaml`

### claudecode.2988 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_2988.yaml`

### claudecode.3033 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3033.yaml`

### claudecode.3033 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-food-service', 'ts-train-food-service'] is in WHERE filters ['ts-food-service', 'ts-station-food-service', 'ts-train-food-service', 'ts-ui-dashboard']
- **evidence**: `merged/verify_evidence/claudecode_case_3033.yaml`

### claudecode.3040 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3040.yaml`

### claudecode.3050 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3050.yaml`

### claudecode.3050 — PD_NoCallTreeBuild (PD)

- **positive_criteria**: FAIL (call_tree_build fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join
- **evidence**: `merged/verify_evidence/claudecode_case_3050.yaml`

### claudecode.3053 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3053.yaml`

### claudecode.3053 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-order-other-service'] is in WHERE filters ['ts-ui-dashboard', 'ts-security-service', 'ts-seat-service', 'ts-basic-service', 'ts-travel2-service', 'ts-route-plan-service', 'ts-route-service', 'ts-order-service', 'ts-config-service', 'ts-order-other-service', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/claudecode_case_3053.yaml`

### claudecode.3076 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3076.yaml`

### claudecode.3076 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-order-service', 'ts-ui-dashboard'] is in WHERE filters ['ts-seat-service', 'ts-route-plan-service', 'rabbitmq', 'ts-ui-dashboard', 'ts-order-service', 'ts-preserve-service', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/claudecode_case_3076.yaml`

### claudecode.3114 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=60>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/claudecode_case_3114.yaml`

### claudecode.3114 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3114.yaml`

### claudecode.3128 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3128.yaml`

### claudecode.3128 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-preserve-service', 'ts-security-service'] is in WHERE filters ['ts-route-service', 'ts-preserve-service', 'ts-food-service', 'ts-train-food-service', 'ts-order-service', 'ts-ui-dashboard', 'ts-travel-service', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/claudecode_case_3128.yaml`

### claudecode.315 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_315.yaml`

### claudecode.315 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-travel-plan-service', 'ts-train-service'] is in WHERE filters ['ts-seat-service', 'ts-config-service', 'ts-travel-plan-service', 'ts-route-plan-service', 'ts-travel-service', 'ts-delivery-service', 'mysql']
- **evidence**: `merged/verify_evidence/claudecode_case_315.yaml`

### claudecode.3159 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3159.yaml`

### claudecode.3159 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-route-plan-service', 'ts-travel-service'] is in WHERE filters ['ts-food-service', 'ts-route-plan-service', 'ts-travel-plan-service', 'ts-route-service', 'ts-ui-dashboard']
- **evidence**: `merged/verify_evidence/claudecode_case_3159.yaml`

### claudecode.3222 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3222.yaml`

### claudecode.3222 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed network/db)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has network/db metric in SQL substrings
- **evidence**: `merged/verify_evidence/claudecode_case_3222.yaml`

### claudecode.33 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_33.yaml`

### claudecode.3324 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3324.yaml`

### claudecode.3391 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3391.yaml`

### claudecode.3391 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-travel2-service', 'ts-route-service'] is in WHERE filters ['ts-route-plan-service', 'ts-travel2-service', 'ts-basic-service', 'ts-seat-service']
- **evidence**: `merged/verify_evidence/claudecode_case_3391.yaml`

### claudecode.341 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-travel-service'] is in WHERE filters ['ts-route-service', 'ts-route-plan-service', 'ts-notification-service', 'ts-delivery-service', 'ts-food-service', 'ts-ui-dashboard', 'ts-travel2-service', 'ts-travel-service', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/claudecode_case_341.yaml`

### claudecode.3555 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-travel-service', 'ts-basic-service'] is in WHERE filters ['ts-travel-service', 'ts-seat-service', 'ts-food-service', 'ts-notification-service', 'ts-delivery-service', 'rabbitmq', 'ts-preserve-service', 'ts-order-service', 'mysql']
- **evidence**: `merged/verify_evidence/claudecode_case_3555.yaml`

### claudecode.3622 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-rabbitmq'] in WHERE filters ['ts-delivery-service', 'ts-notification-service', 'ts-food-service', 'ts-rabbitmq']
- **evidence**: `merged/verify_evidence/claudecode_case_3622.yaml`

### claudecode.3622 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3622.yaml`

### claudecode.3700 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3700.yaml`

### claudecode.3700 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-config-service'] is in WHERE filters ['ts-ui-dashboard', 'ts-seat-service', 'ts-travel-plan-service', 'ts-route-plan-service', 'ts-order-service', 'ts-config-service', 'ts-travel2-service', 'ts-travel-service', 'ts-order-other-service']
- **evidence**: `merged/verify_evidence/claudecode_case_3700.yaml`

### claudecode.3716 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3716.yaml`

### claudecode.3760 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3760.yaml`

### claudecode.3760 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed jvm)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has jvm metric in SQL substrings
- **evidence**: `merged/verify_evidence/claudecode_case_3760.yaml`

### claudecode.3776 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3776.yaml`

### claudecode.3920 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3920.yaml`

### claudecode.3966 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_3966.yaml`

### claudecode.4054 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_4054.yaml`

### claudecode.4055 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_4055.yaml`

### claudecode.4081 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_4081.yaml`

### claudecode.4229 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_4229.yaml`

### claudecode.4258 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_4258.yaml`

### claudecode.4353 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=13>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/claudecode_case_4353.yaml`

### claudecode.4353 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_4353.yaml`

### claudecode.4353 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-station-service'] is in WHERE filters ['ts-basic-service', 'ts-travel-service', 'ts-config-service', 'ts-train-service', 'ts-station-service']
- **evidence**: `merged/verify_evidence/claudecode_case_4353.yaml`

### claudecode.4363 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_4363.yaml`

### claudecode.4375 — PD_NoCallTreeBuild (PD)

- **positive_criteria**: FAIL (call_tree_build fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join
- **evidence**: `merged/verify_evidence/claudecode_case_4375.yaml`

### claudecode.4375 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-travel2-service'] is in WHERE filters ['ts-route-plan-service', 'ts-basic-service', 'ts-route-service', 'ts-order-service', 'ts-ui-dashboard', 'ts-travel2-service', 'ts-preserve-service', 'ts-travel-service', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/claudecode_case_4375.yaml`

### claudecode.4423 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_4423.yaml`

### claudecode.4423 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-basic-service', 'ts-preserve-service'] is in WHERE filters ['ts-preserve-service', 'ts-ui-dashboard', 'ts-food-service', 'ts-payment-service', 'ts-consign-price-service', 'ts-inside-payment-service']
- **evidence**: `merged/verify_evidence/claudecode_case_4423.yaml`

### claudecode.4463 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_4463.yaml`

### claudecode.4510 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-route-plan-service', 'ts-travel-service'] is in WHERE filters ['ts-travel-plan-service', 'ts-route-plan-service', 'ts-ui-dashboard', 'ts-travel2-service', 'ts-travel-service']
- **evidence**: `merged/verify_evidence/claudecode_case_4510.yaml`

### claudecode.4517 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_4517.yaml`

### claudecode.4517 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-route-plan-service', 'ts-travel2-service'] is in WHERE filters ['ts-food-service', 'ts-order-service', 'ts-route-plan-service', 'ts-route-service', 'ts-travel-service', 'ts-travel-plan-service', 'ts-ui-dashboard']
- **evidence**: `merged/verify_evidence/claudecode_case_4517.yaml`

### claudecode.4789 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=13>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/claudecode_case_4789.yaml`

### claudecode.4789 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_4789.yaml`

### claudecode.4791 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_4791.yaml`

### claudecode.4823 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_4823.yaml`

### claudecode.4832 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_4832.yaml`

### claudecode.572 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-food-service', 'ts-train-food-service'] is in WHERE filters ['ts-station-food-service', 'ts-order-service', 'ts-consign-service', 'ts-preserve-service', 'ts-ui-dashboard', 'ts-travel-plan-service', 'ts-food-service']
- **evidence**: `merged/verify_evidence/claudecode_case_572.yaml`

### claudecode.710 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_710.yaml`

### claudecode.741 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_741.yaml`

### claudecode.755 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_755.yaml`

### claudecode.755 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-seat-service', 'ts-travel2-service'] is in WHERE filters ['ts-travel-plan-service', 'rabbitmq', 'ts-seat-service', 'ts-order-service', 'ts-route-plan-service', 'ts-travel2-service', 'ts-travel-service']
- **evidence**: `merged/verify_evidence/claudecode_case_755.yaml`

### claudecode.762 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_762.yaml`

### claudecode.762 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-seat-service', 'ts-order-service'] is in WHERE filters ['ts-seat-service', 'ts-food-service', 'ts-train-food-service', 'ts-order-service']
- **evidence**: `merged/verify_evidence/claudecode_case_762.yaml`

### claudecode.804 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_804.yaml`

### claudecode.807 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_807.yaml`

### claudecode.864 — PD_NoBaselineContrast (PD)

- **positive_criteria**: FAIL (baseline_contrast fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD1 claims no baseline_contrast but substring audit shows agent did it
- **evidence**: `merged/verify_evidence/claudecode_case_864.yaml`

### claudecode.864 — claudecode.PD4_GTServiceNotTargetedWithWhere (PD)

- **positive_criteria**: FAIL (GT in WHERE)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: GT ['ts-travel-service', 'ts-route-service'] is in WHERE filters ['ts-travel-service', 'ts-basic-service', 'ts-travel-plan-service', 'ts-route-plan-service', 'ts-seat-service', 'ts-delivery-service', 'ts-notification-service']
- **evidence**: `merged/verify_evidence/claudecode_case_864.yaml`

### qwen.1143 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=139>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/qwen_case_1143.yaml`

### qwen.1371 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed k8s/container)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has k8s/container metric in SQL substrings
- **evidence**: `merged/verify_evidence/qwen_case_1371.yaml`

### qwen.1459 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=6>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/qwen_case_1459.yaml`

### qwen.156 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=20>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/qwen_case_156.yaml`

### qwen.1917 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=53>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/qwen_case_1917.yaml`

### qwen.1934 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed k8s/container)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has k8s/container metric in SQL substrings
- **evidence**: `merged/verify_evidence/qwen_case_1934.yaml`

### qwen.1948 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=80>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/qwen_case_1948.yaml`

### qwen.2258 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed k8s/container)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has k8s/container metric in SQL substrings
- **evidence**: `merged/verify_evidence/qwen_case_2258.yaml`

### qwen.2641 — PD_NoCallTreeBuild (PD)

- **positive_criteria**: FAIL (call_tree_build fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join
- **evidence**: `merged/verify_evidence/qwen_case_2641.yaml`

### qwen.2678 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed network/db)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has network/db metric in SQL substrings
- **evidence**: `merged/verify_evidence/qwen_case_2678.yaml`

### qwen.281 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=9>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/qwen_case_281.yaml`

### qwen.3114 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=60>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/qwen_case_3114.yaml`

### qwen.341 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed k8s/container)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has k8s/container metric in SQL substrings
- **evidence**: `merged/verify_evidence/qwen_case_341.yaml`

### qwen.3716 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=256>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/qwen_case_3716.yaml`

### qwen.3955 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed k8s/container)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has k8s/container metric in SQL substrings
- **evidence**: `merged/verify_evidence/qwen_case_3955.yaml`

### qwen.4081 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed k8s/container)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has k8s/container metric in SQL substrings
- **evidence**: `merged/verify_evidence/qwen_case_4081.yaml`

### qwen.4258 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed k8s/container)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has k8s/container metric in SQL substrings
- **evidence**: `merged/verify_evidence/qwen_case_4258.yaml`

### qwen.4309 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed k8s/container)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has k8s/container metric in SQL substrings
- **evidence**: `merged/verify_evidence/qwen_case_4309.yaml`

### qwen.4353 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=13>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/qwen_case_4353.yaml`

### qwen.4789 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=13>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/qwen_case_4789.yaml`

### qwen.4893 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=7>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/qwen_case_4893.yaml`

### qwen.784 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=9>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/qwen_case_784.yaml`

### qwen.804 — PD_NoFaultLayerMetricProbe (PD)

- **positive_criteria**: FAIL (agent probed k8s/container)
- **gt_required_capability**: pass
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD3 fires but agent has k8s/container metric in SQL substrings
- **evidence**: `merged/verify_evidence/qwen_case_804.yaml`

### qwen.807 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=6>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/qwen_case_807.yaml`

### sonnet.1140 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: FAIL
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=175>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/sonnet_case_1140.yaml`

### sonnet.1140 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-seat-service'] in WHERE filters ['ts-consign-service', 'ts-order-service', 'ts-travel-service', 'ts-seat-service', 'ts-admin-order-service', 'ts-security-service', 'ts-preserve-service']
- **evidence**: `merged/verify_evidence/sonnet_case_1140.yaml`

### sonnet.1326 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-route-service'] in WHERE filters ['ts-route-plan-service', 'ts-travel-plan-service', 'ts-travel-service', 'ts-route-service', 'ts-travel2-service']
- **evidence**: `merged/verify_evidence/sonnet_case_1326.yaml`

### sonnet.1421 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-config-service'] in WHERE filters ['ts-seat-service', 'ts-preserveservice', 'ts-route-plan-service', 'ts-travelservice', 'ts-travel2service', 'ts-config-service', 'ts-station-service', 'ts-travel2-service', 'ts-travelplanservice', 'ts-preserve-service', 'ts-consign-service', 'ts-basic-service', 'ts-price-service', 'ts-travel-service', 'ts-travel-plan-service', 'ts-route-service']
- **evidence**: `merged/verify_evidence/sonnet_case_1421.yaml`

### sonnet.1484 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-seat-service'] in WHERE filters ['ts-travel-plan-service', 'ts-route-plan-service', 'ts-seat-service', 'ts-travel-service', 'ts-cancel-service']
- **evidence**: `merged/verify_evidence/sonnet_case_1484.yaml`

### sonnet.1484 — PD_TraceFollowAbsent (PD)

- **positive_criteria**: FAIL (trace_follow fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD9 claims no trace_follow but substring audit shows one
- **evidence**: `merged/verify_evidence/sonnet_case_1484.yaml`

### sonnet.1880 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-route-service'] in WHERE filters ['ts-food-service', 'ts-train-food-service', 'ts-route-service', 'loadgenerator', 'ts-assurance-service', 'ts-inside-payment-service', 'ts-preserve-service', 'ts-consign-service', 'ts-train-service', 'ts-cancel-service']
- **evidence**: `merged/verify_evidence/sonnet_case_1880.yaml`

### sonnet.1948 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=80>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/sonnet_case_1948.yaml`

### sonnet.2011 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-travel-service'] in WHERE filters ['ts-route-plan-service', 'ts-travel-service', 'ts-travel-plan-service', 'ts-travel2-service']
- **evidence**: `merged/verify_evidence/sonnet_case_2011.yaml`

### sonnet.2130 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-route-service'] in WHERE filters ['ts-route-service', 'mysql']
- **evidence**: `merged/verify_evidence/sonnet_case_2130.yaml`

### sonnet.2174 — D5 (D)

- **positive_criteria**: FAIL (GT is loudest — no cascade decoy)
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: n/a
- **reason**: D5 requires cascade louder than GT but GT itself is top-ranked
- **evidence**: `merged/verify_evidence/sonnet_case_2174.yaml`

### sonnet.2584 — PD_NoCallTreeBuild (PD)

- **positive_criteria**: FAIL (call_tree_build fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join
- **evidence**: `merged/verify_evidence/sonnet_case_2584.yaml`

### sonnet.2640 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-route-service'] in WHERE filters ['ts-route-plan-service', 'ts-travel-plan-service', 'ts-route-service', 'ts-ui-dashboard']
- **evidence**: `merged/verify_evidence/sonnet_case_2640.yaml`

### sonnet.2678 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-travel2-service'] in WHERE filters ['ts-travel2-service', 'ts-travel-service', 'ts-route-plan-service', 'ts-order-service', 'ts-seat-service', 'ts-preserve-service', 'ts-order-other-service', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/sonnet_case_2678.yaml`

### sonnet.2678 — PD_NoCallTreeBuild (PD)

- **positive_criteria**: FAIL (call_tree_build fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join
- **evidence**: `merged/verify_evidence/sonnet_case_2678.yaml`

### sonnet.2682 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-route-service', 'ts-order-service'] in WHERE filters ['ts-travel-plan-service', 'ts-route-plan-service', 'ts-route-service', 'ts-preserve-service', 'ts-travel2-service', 'ts-delivery-service', 'ts-notification-service']
- **evidence**: `merged/verify_evidence/sonnet_case_2682.yaml`

### sonnet.2715 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-travel-service'] in WHERE filters ['ts-route-plan-service', 'ts-travel-plan-service', 'ts-travel-service']
- **evidence**: `merged/verify_evidence/sonnet_case_2715.yaml`

### sonnet.2748 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-travel2-service'] in WHERE filters ['ts-travel-plan-service', 'ts-travel2-service', 'ts-ui-dashboard', 'ts-route-plan-service', 'loadgenerator', 'ts-travel-service']
- **evidence**: `merged/verify_evidence/sonnet_case_2748.yaml`

### sonnet.2801 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-seat-service', 'ts-cancel-service'] in WHERE filters ['ts-travel-service', 'ts-ui-dashboard', 'ts-seat-service']
- **evidence**: `merged/verify_evidence/sonnet_case_2801.yaml`

### sonnet.2830 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-basic-service'] in WHERE filters ['ts-route-plan-service', 'ts-travel2-service', 'ts-basic-service', 'ts-seat-service', 'ts-travel-service', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/sonnet_case_2830.yaml`

### sonnet.2836 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-seat-service'] in WHERE filters ['ts-travel2-service', 'ts-seat-service', 'ts-travel-service', 'ts-route-plan-service', 'ts-ui-dashboard', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/sonnet_case_2836.yaml`

### sonnet.3112 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['rabbitmq'] in WHERE filters ['ts-preserve-service', 'rabbitmq', 'ts-food-service', 'ts-delivery-service', 'ts-notification-service']
- **evidence**: `merged/verify_evidence/sonnet_case_3112.yaml`

### sonnet.3125 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-price-service'] in WHERE filters ['ts-preserve-service', 'mysql', 'ts-price-service', 'ts-route-plan-service', 'ts-order-service', 'ts-config-service', 'ts-consign-service', 'ts-delivery-service', 'ts-notification-service', 'ts-basic-service', 'ts-travel-service', 'ts-train-service', 'ts-cancel-service', 'ts-travel-plan-service', 'ts-route-service', 'ts-food-service']
- **evidence**: `merged/verify_evidence/sonnet_case_3125.yaml`

### sonnet.315 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-order-service'] in WHERE filters ['ts-seat-service', 'ts-route-plan-service', 'ts-order-service', 'ts-cancel-service', 'ts-assurance-service']
- **evidence**: `merged/verify_evidence/sonnet_case_315.yaml`

### sonnet.323 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-config-service'] in WHERE filters ['ts-config-service', 'ts-route-plan-service', 'ts-seat-service', 'ts-travel2-service', 'ts-basic-service', 'ts-travel-service', 'ts-price-service', 'ts-train-service', 'ts-route-service']
- **evidence**: `merged/verify_evidence/sonnet_case_323.yaml`

### sonnet.3493 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-order-other-service'] in WHERE filters ['ts-preserve-service', 'ts-security-service', 'ts-order-other-service']
- **evidence**: `merged/verify_evidence/sonnet_case_3493.yaml`

### sonnet.3555 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-seat-service'] in WHERE filters ['ts-seat-service', 'ts-cancel-service', 'ts-route-plan-service', 'ts-order-service', 'ts-preserve-service', 'ts-consign-service', 'ts-basic-service', 'ts-travel-service', 'ts-travel-plan-service', 'ts-route-service']
- **evidence**: `merged/verify_evidence/sonnet_case_3555.yaml`

### sonnet.3592 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-travel-service'] in WHERE filters ['ts-travel-service', 'ts-route-plan-service', 'ts-ui-dashboard', 'ts-travel2-service', 'ts-travel-plan-service', 'ts-route-service']
- **evidence**: `merged/verify_evidence/sonnet_case_3592.yaml`

### sonnet.371 — PD_NoCallTreeBuild (PD)

- **positive_criteria**: FAIL (call_tree_build fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join
- **evidence**: `merged/verify_evidence/sonnet_case_371.yaml`

### sonnet.3868 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-basic-service'] in WHERE filters ['ts-consign-service', 'ts-travel-plan-service', 'ts-route-plan-service', 'ts-travel-service', 'ts-basic-service', 'ts-food-service', 'ts-preserve-service', 'ts-order-service', 'ts-order-other-service', 'ts-delivery-service', 'ts-price-service', 'ts-verification-code-service', 'ts-train-service', 'ts-notification-service', 'ts-route-service']
- **evidence**: `merged/verify_evidence/sonnet_case_3868.yaml`

### sonnet.4229 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-seat-service'] in WHERE filters ['ts-travel-plan-service', 'ts-route-plan-service', 'ts-config-service', 'ts-seat-service', 'ts-travel2-service', 'ts-price-service', 'ts-basic-service', 'ts-travel-service']
- **evidence**: `merged/verify_evidence/sonnet_case_4229.yaml`

### sonnet.4229 — PD_NoCallTreeBuild (PD)

- **positive_criteria**: FAIL (call_tree_build fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join
- **evidence**: `merged/verify_evidence/sonnet_case_4229.yaml`

### sonnet.4423 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-seat-service'] in WHERE filters ['loadgenerator', 'ts-preserve-service', 'ts-seat-service', 'mysql', 'ts-ui-dashboard']
- **evidence**: `merged/verify_evidence/sonnet_case_4423.yaml`

### sonnet.4423 — PD_NoCallTreeBuild (PD)

- **positive_criteria**: FAIL (call_tree_build fired)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join
- **evidence**: `merged/verify_evidence/sonnet_case_4423.yaml`

### sonnet.4433 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-price-service'] in WHERE filters ['loadgenerator', 'ts-basic-service', 'ts-food-service', 'ts-ui-dashboard', 'ts-price-service', 'ts-travel2-service', 'ts-travel-service']
- **evidence**: `merged/verify_evidence/sonnet_case_4433.yaml`

### sonnet.4463 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-food-service'] in WHERE filters ['ts-food-service']
- **evidence**: `merged/verify_evidence/sonnet_case_4463.yaml`

### sonnet.4510 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-travel2-service'] in WHERE filters ['loadgenerator', 'ts-route-plan-service', 'ts-travel2-service', 'ts-basic-service', 'ts-travel-service', 'ts-travel-plan-service']
- **evidence**: `merged/verify_evidence/sonnet_case_4510.yaml`

### sonnet.4707 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-order-service', 'rabbitmq'] in WHERE filters ['ts-order-service', 'ts-seat-service', 'ts-food-service', 'ts-route-plan-service', 'ts-travel2-service', 'ts-preserve-service', 'ts-delivery-service', 'ts-notification-service', 'ts-travel-plan-service', 'rabbitmq']
- **evidence**: `merged/verify_evidence/sonnet_case_4707.yaml`

### sonnet.572 — D1 (D)

- **positive_criteria**: FAIL
- **gt_required_capability**: FAIL
- **path_alignment**: pass
- **counterfactual**: pass
- **reason**: D1 claims GT silent but gt_service_abnormal_log_error_count=232>5 (v2 threshold)
- **evidence**: `merged/verify_evidence/sonnet_case_572.yaml`

### sonnet.572 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-order-service', 'ts-consign-service'] in WHERE filters ['ts-consign-service', 'ts-route-plan-service', 'ts-travel-service', 'ts-order-service', 'ts-basic-service', 'ts-price-service', 'ts-seat-service', 'ts-preserve-service', 'ts-cancel-service', 'ts-travel2-service', 'ts-order-other-service', 'ts-travel-plan-service', 'ts-route-service']
- **evidence**: `merged/verify_evidence/sonnet_case_572.yaml`

### sonnet.675 — PD_NamedCandidateNotIsolated (PD)

- **positive_criteria**: FAIL (RC appears in WHERE filter)
- **gt_required_capability**: n/a
- **path_alignment**: n/a
- **counterfactual**: n/a
- **reason**: PD4 claims RC not isolated but ['ts-travel-service', 'ts-travel2-service'] in WHERE filters ['ts-route-plan-service', 'ts-travel-service', 'ts-travel2-service']
- **evidence**: `merged/verify_evidence/sonnet_case_675.yaml`


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

### PD_NamedCandidateNotIsolated — N=81

- agree: 11 (14%)
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

- **Overall agree rate**: 828/1972 (42%)
- **D axis**: 214/369 agree (58%)
- **R axis**: 145/370 agree (39%)
- **PD axis**: 469/1233 agree (38%)

- **Fabricated D**: 11 (every fabricated means the D label is blaming data when the agent chose wrong path)
- **Misaligned R**: 110 (misattributed reasoning-defect class — GT didn't require the capability the R label blames)
- **Redundant PD**: 332 (PD label on cases where the missing action would change nothing)

> For per-case evidence see `merged/verify_evidence/<agent>_case_<id>.yaml`.
> For per-verdict row see `merged/verify_verdicts.jsonl`.
