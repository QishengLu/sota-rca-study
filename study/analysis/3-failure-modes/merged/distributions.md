# distributions.md — D × R heatmap, F × framework, analytical-only R (v2, path-obstacle D)

**Phase G revised**: D axis redefined as path-obstacle (not fault_type). All 4 frameworks' D × R heatmaps rebuilt on 370 cases (excl. 2 R-deferred dataset_anomaly).


## aiq  (total: 113)

D \ R | U1_LoudnessAnchorOverSilentVictim | U2_ChronicAmbientNoiseAnchor | U4_NameTwinSiblingConfusion | aiq.R_compress_drift | aiq.R_correct_then_reversed | aiq.R_hub_fabrication | row tot |
---|---:|---:|---:|---:|---:|---:|---:|
D_victim_silent_on_path | 16 | — | — | — | 13 | 10 | **39** |
D_cross_layer_signal_gap | 14 | — | — | — | — | 2 | **16** |
D_ambient_noise_dominates | — | 16 | — | 8 | — | — | **24** |
D_cascade_symptom_louder_than_GT | 25 | — | — | — | — | — | **25** |
D_name_twin_on_path | — | — | 8 | — | — | — | **8** |
D_dataset_anomaly | — | 1 | — | — | — | — | **1** |

## claudecode  (total: 102)

D \ R | U1_LoudnessAnchorOverSilentVictim | U2_ChronicAmbientNoiseAnchor | U3_EdgeDirectionOrRegionEndpointError | U4_NameTwinSiblingConfusion | claudecode.R6_InfraLayerSkipped | claudecode.R7_JVMSymptomMisreadAsDB | row tot |
---|---:|---:|---:|---:|---:|---:|---:|
D_victim_silent_on_path | 25 | 10 | 8 | 1 | — | — | **44** |
D_cross_layer_signal_gap | 1 | 5 | 1 | — | 4 | 4 | **15** |
D_ambient_noise_dominates | — | 14 | — | — | — | — | **14** |
D_edge_symmetric_ambiguity | — | 3 | 2 | — | 2 | — | **7** |
D_cascade_symptom_louder_than_GT | 1 | — | 3 | — | 1 | — | **5** |
D_name_twin_on_path | 1 | 1 | — | 9 | — | — | **11** |
D_diluted_multi_candidate | 1 | 2 | 3 | — | — | — | **6** |

## sonnet  (total: 50)

D \ R | U1_LoudnessAnchorOverSilentVictim | U2_ChronicAmbientNoiseAnchor | U3_EdgeDirectionOrRegionEndpointError | U5_SilenceReadAsHealthOrPaused | sonnet.R_NarrativeOverMatchedMagnitude | sonnet.R_OscillationToCompromisePair | row tot |
---|---:|---:|---:|---:|---:|---:|---:|
D_victim_silent_on_path | 1 | — | 2 | — | — | 1 | **4** |
D_cross_layer_signal_gap | 6 | — | 1 | — | — | — | **7** |
D_ambient_noise_dominates | — | 6 | 1 | — | — | 1 | **8** |
D_edge_symmetric_ambiguity | 1 | — | 8 | 2 | 2 | — | **13** |
D_cascade_symptom_louder_than_GT | 2 | — | 2 | — | — | — | **4** |
D_name_twin_on_path | — | 1 | 3 | — | — | — | **4** |
D_diluted_multi_candidate | 2 | — | 5 | — | 1 | 2 | **10** |

## qwen  (total: 105)

D \ R | U1_LoudnessAnchorOverSilentVictim | U2_ChronicAmbientNoiseAnchor | U3_EdgeDirectionOrRegionEndpointError | U5_SilenceReadAsHealthOrPaused | qwen.R_E_PathOvershootPastInjection | qwen.R_F_QueryDesignBuriesSignal | row tot |
---|---:|---:|---:|---:|---:|---:|---:|
D_victim_silent_on_path | 28 | 7 | 4 | 13 | 1 | 2 | **55** |
D_cross_layer_signal_gap | 10 | 12 | 2 | 2 | 2 | 1 | **29** |
D_ambient_noise_dominates | — | 4 | — | — | — | — | **4** |
D_edge_symmetric_ambiguity | 6 | 3 | 3 | — | 3 | 1 | **16** |
D_diluted_multi_candidate | — | — | — | — | — | 1 | **1** |

## F distribution per framework

| Framework | F1 | F2 | Total F | % of labeled |
|---|---:|---:|---:|---:|
| aiq | 8 | 13 | 21 | 18.6% |
| claudecode | 0 | 0 | 0 | 0% |
| sonnet | 0 | 0 | 0 | 0% |
| qwen | 0 | 0 | 0 | 0% |

## analytical_only R classes

| R class | Level | Reason |
|---|---|---|
| aiq.R_name_twin_confusion | per-agent | Trajectory-only distillation FP rate ~60% |
| claudecode.R6_InfraLayerSkipped | framework-specific | Distinguisher requires GT fault_category |
| sonnet.R_NarrativeOverMatchedMagnitude | per-agent | Lexical FP ~50% |
| U4_NameTwinSiblingConfusion | unified | Framework-universal FAIL (only claudecode ≥10%) |

## Unified R × framework shares (%)

| Unified R | aiq | claudecode | sonnet | qwen | Priority gate |
|---|---:|---:|---:|---:|---|
| U1_LoudnessAnchorOverSilentVictim | 48.7% | 28.4% | 24.0% | 41.9% | FU PASS (4/4), MR FAIL (17.9pp) |
| U2_ChronicAmbientNoiseAnchor | 15.0% | 34.3% | 14.0% | 24.8% | FU PASS (4/4), MR FAIL (10.8pp) |
| U3_EdgeDirectionOrRegionEndpointError | 0.0% | 16.7% | 44.0% | 8.6% | FU PASS (2/4), MR FAIL (35.4pp) |
| U4_NameTwinSiblingConfusion | 7.1% | 9.8% | 0.0% | 0.0% | FU FAIL, MR PASS (0pp) |
| U5_SilenceReadAsHealthOrPaused | 0.0% | 0.0% | 4.0% | 14.3% | FU FAIL, MR FAIL (10.3pp) |

## Headline D × R insights (pooled across 4 frameworks)

Top 10 (D, R) pairs by pooled case count:

| D × R | N |
|---|---:|
| D_victim_silent_on_path × U1_LoudnessAnchorOverSilentVictim | 70 |
| D_ambient_noise_dominates × U2_ChronicAmbientNoiseAnchor | 40 |
| D_cross_layer_signal_gap × U1_LoudnessAnchorOverSilentVictim | 31 |
| D_cascade_symptom_louder_than_GT × U1_LoudnessAnchorOverSilentVictim | 28 |
| D_name_twin_on_path × U4_NameTwinSiblingConfusion | 17 |
| D_cross_layer_signal_gap × U2_ChronicAmbientNoiseAnchor | 17 |
| D_victim_silent_on_path × U2_ChronicAmbientNoiseAnchor | 17 |
| D_victim_silent_on_path × U3_EdgeDirectionOrRegionEndpointError | 14 |
| D_victim_silent_on_path × aiq.R_correct_then_reversed | 13 |
| D_edge_symmetric_ambiguity × U3_EdgeDirectionOrRegionEndpointError | 13 |