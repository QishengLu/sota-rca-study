# induction_log.md — Consolidated per-case triangulation + gate verification

**Phase G**: cross-reference per-framework and per-axis induction logs. Single source for case-level deferred status + quality-gate verdicts.

---

## Per-framework triangulation summary

Each framework's sub-agent executed **three-level triangulation** per labeled case:
1. `labels.jsonl` evidence field
2. `per_case_analysis.md` `## case_{id}` section
3. `dossiers/case_{id}.md` (Part A GT reality)

| Framework | Labeled | Triangulated | Deferred | Deferral reason |
|---|---:|---:|---:|---|
| aiq-qwen3.5-plus | 113 | 113 (100%) | 0 | — |
| claudecode-qwen3.5-plus | 103 | 102 (99.0%) | 1 (case 4463) | dataset_anomaly (GT/injection mismatch) |
| thinkdepthai-claude-sonnet-4.6 | 51 | 50 (98.0%) | 1 (case 4463) | dataset_anomaly (same 4463) |
| thinkdepthai-qwen3.5-plus | 105 | 105 (100%) | 0 | — |
| **Total** | **372** | **370 (99.5%)** | **2 (0.5%)** | dataset_anomaly only |

**Gate 1 (triangulation ≥95%, deferred <5%): PASS** — 99.5% triangulated, 0.5% deferred.

Detailed per-case logs:
- aiq: `analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/v1/R_induction_log.md`
- claudecode: `analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/R_induction_log.md`
- sonnet: `analysis/3-failure-modes/2-by-framework/thinkdepthai-claude-sonnet-4.6/v1/R_induction_log.md`
- qwen: `analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v1_harp/R_induction_log.md`
- D axis: `analysis/3-failure-modes/merged/D_induction_log.md`

---

## Deferred cases (with reasons)

| case_id | Framework | R deferral reason | D assignment |
|---|---|---|---|
| 4463 | claudecode | dataset_anomaly — DB meta `ts-config-service` vs datapack `ts-food-service-container-kill` | D2 (low confidence) |
| 4463 | sonnet | same (equivalent) dataset_anomaly | D7 (low confidence) |

Both cases received a D label (low-confidence, per D_induction_log.md) but no R label — they are NOT reasoning defects; they are ground-truth inconsistencies in the dataset itself.

---

## MECE verification

### D axis (7 path-obstacle classes + 1 dataset-anomaly parking) — **v2 revision**

**Revision note (2026-04-21)**: the initial D taxonomy was rejected because its classes collapsed to `fault_type` buckets (D1 = all JVMChaos/ContainerKill cases). The user's criterion is: "D labels the path-obstacle that actually blocked the agent on THIS case; same fault_type yields different D on different cases." Taxonomy rebuilt under this corrected criterion. 195/372 (52%) case labels changed from v1 to v2.

| Class | Count | Cases per framework | Fault-types spanned |
|---|---:|---|---:|
| D_victim_silent_on_path | 142 | aiq 39 / cc 44 / sonnet 4 / qwen 55 | 16 |
| D_cross_layer_signal_gap | 67 | aiq 16 / cc 15 / sonnet 7 / qwen 29 | 18 |
| D_ambient_noise_dominates | 50 | aiq 24 / cc 14 / sonnet 8 / qwen 4 | 19 |
| D_edge_symmetric_ambiguity | 36 | aiq 0 / cc 7 / sonnet 13 / qwen 16 | 13 |
| D_cascade_symptom_louder_than_GT | 34 | aiq 25 / cc 5 / sonnet 4 / qwen 0 | 10 |
| D_name_twin_on_path | 23 | aiq 8 / cc 11 / sonnet 4 / qwen 0 | 10 |
| D_diluted_multi_candidate | 17 | aiq 0 / cc 6 / sonnet 10 / qwen 1 | 11 |
| D_dataset_anomaly (parking) | 3 | aiq 1 / cc 1 / sonnet 1 / qwen 0 | 2 |
| **Total** | **372** | Σ=372, 0 overlap | — |

**Anti-alignment validation (critical for this axis)**: each real D class spans 10-19 fault_types. Inverting the table: every top fault_type spans 5-7 D classes:
- JVMMemoryStress: 6 D classes (not just "silent")
- ContainerKill: 6 D classes
- NetworkBandwidth / HTTPResponseDelay / HTTPResponseReplaceBody: all 7 D classes each
- NetworkPartition: 5 D classes

This proves D is genuinely a path-obstacle axis, not a fault_type re-label.

### R axis (5 unified + 8 framework-specific)

- **Unified R**: 5 classes, 308 cases pooled. MECE within unified set verified by projection determinism.
- **Framework-specific analytical_R**: 8 classes, 62 cases. Each per-agent R maps to exactly one unified R OR one framework-specific class.
- **Projection determinism**: every labeled case (370) projects to exactly one of the 13 R destinations.

**Gate 6 (MECE) for each axis: PASS**
**Gate 7 (Projection determinism): PASS** — D: 372/372, R: 370/370.

### Per-agent R MECE (prior to cross-framework merge)

Verified by each per-agent sub-agent in Phase B:
- aiq: 8 classes, 113/113 exclusive
- claudecode: 7 classes, 102/102 exclusive (1 deferred)
- sonnet: 7 classes, 50/50 exclusive (1 deferred)
- qwen: 7 classes, 105/105 exclusive

---

## Quality gate summary

| Gate | Criterion | Status | Notes |
|---|---|---|---|
| 1 | Triangulation ≥95%; deferred <5% | **PASS** | 99.5% / 0.5% |
| 2 | D class count ∈ [5, 8], R class count ∈ [5, 10] | **PASS** | D=8, R_unified=5 |
| 3 | Priority-set R precision ≥0.6 AND recall ≥0.5 | **DEFERRED** | Strict priority set = empty; relaxed set {U1,U2,U3} requires Phase 8 executable trigger implementation to measure |
| 4 | No GT-required signal in middleware_rules triggers | **PASS** | U1/U2/U3 rule cards audited; no GT fields in trigger formulas |
| 5 | F entries do not appear in middleware_rules | **PASS** | aiq.F1/F2 are in `aiq-qwen3.5-plus/v1/F_catalog.md`, NOT in `merged/middleware_rules/` |
| 6 | MECE — every phrase exactly one class, every phrase has a class, no "other" bucket | **PASS** | Verified for D, per-agent R, and unified R |
| 7 | Projection determinism — every case → 1 D + 1 R (or fw-specific) | **PASS** | D: 372/372, R: 370/370 |

**Gate 3 is the single deferred gate**. The strict 3-condition priority set is empty (model-robust 5pp gate fails for all unified R because of the substantial qwen-vs-sonnet gap). The relaxed set {U1, U2, U3} was adopted for middleware rule cards per the user's north star; precision/recall for those triggers must be measured in Phase 8 by implementing the trigger pseudocode as executable Python and running over the 370 labeled cases.

---

## D axis revision delta (v1 → v2, 2026-04-21)

**Trigger**: user review flagged that v1 D classes were fault_type buckets with `Fault types: X, Y, Z` under each class — this collapsed the intended "path-obstacle" axis into an "injection-type" axis.

**Fix**: re-clustered the 372 D-phrases by OBSTACLE MECHANISM (clause after "fault_type —" lead-in). Required each class to span ≥3 fault_types. Result: 7 path-obstacle classes + 1 anomaly parking.

**Delta summary**:
- v1 D1_silent_victim (160) → split: most to D_victim_silent_on_path (142) and D_cross_layer_signal_gap (where signal existed in non-log layers, e.g., JVM CPU stress on a named service).
- v1 D2_errorless_network (55) → decomposed across D_cross_layer_signal_gap, D_edge_symmetric_ambiguity, D_victim_silent_on_path, D_ambient_noise_dominates depending on per-case obstacle.
- v1 D3_silent_corruption (31) → split across D_cross_layer_signal_gap, D_edge_symmetric_ambiguity, D_diluted_multi_candidate, D_name_twin_on_path.
- v1 D4_delay_abort (35) → split across D_edge_symmetric_ambiguity, D_cross_layer_signal_gap, D_victim_silent_on_path, etc.
- v1 D6_baseline_noise → renamed 1-to-1 to D_ambient_noise_dominates (this was already path-obstacle phrased in v1).
- v1 D7_cascade_decoy (49) → split across D_cascade_symptom_louder_than_GT (34) and reassignments.
- v1 D8_sibling_ambig → renamed 1-to-1 to D_name_twin_on_path.

**Total reclassifications**: 195/372 (52%). DB `meta.failure_analysis.v1.D` rewritten.

**New anti-alignment check**: none of the 7 real D classes is dominated by one fault_type. Max single-fault_type share is JVMMemoryStress in D_victim_silent_on_path = 63/142 = 44% — but JVMMemoryStress itself also appears in 5 other D classes, confirming the axis is not JVMMemoryStress = silent_on_path.

---

## Decisions that required autonomous judgment (logged here for audit)

1. **Qwen has no v1; v2 was used as data source**, output directed to new folder `thinkdepthai-qwen3.5-plus/v1_harp/`. v2's D1..D5 / R1..R7 definitions were NOT copied as seed; only consulted as a coverage cross-check at the end. Result: 6 of qwen's 7 new R classes have ≥5 case overlap with v2's R1-R6; minor divergence at the narrative-confabulation boundary (qwen.R_G absorbs what v2 split between R1/R3).

2. **Priority Set relaxation**: strict 3-condition gate produces empty set because all unified R fail the 5pp model-robust condition (qwen vs sonnet gap ≥ 10pp for every class). Autonomous decision: adopt **relaxed priority set** (framework-universal + trajectory-only) = {U1, U2, U3} and document model-robustness as per-model tuning caveat within each rule card. This honors the user's north star ("design a generally effective middleware") without quietly subverting the strict gate.

3. **F candidate assignments**:
   - aiq.R_compress_drift → F1 (compress-layer architectural). Kept out of unified R and middleware.
   - aiq.R_correct_then_reversed → F2 (refine-stage architectural). Kept out of unified R and middleware.
   - claudecode.T4 InfraLayerSkipped → rejected as F (tool layer doesn't block; reasoning defect). Kept as framework-specific analytical_R6.
   - sonnet.T6 ExhaustionWithoutCommitment → rejected as F (ReAct loop demonstrably commits at high rounds when hypothesis-breadth is narrow; pair-output is reasoning choice). Kept as framework-specific R.
   - qwen: no F candidates (thinkdepthai-qwen is thinkdepthai ReAct pipeline, same as sonnet — failures are model-side).

4. **U4 NameTwinSiblingConfusion** classified as `analytical_only` at unified level: only 2 frameworks contribute (aiq 7.1%, claudecode 9.8%), both under the 10% framework-universal threshold. Mechanism is real but under-represented in thinkdepthai frameworks. Flagged as candidate for dataset-level intervention (preprocessing) rather than middleware.

5. **Dataset_anomaly (case 4463)**: not labeled R for claudecode/sonnet, but assigned D (low confidence) because the data-challenge axis still applies to the telemetry content even when the GT label itself is corrupt. Separate from R because no reasoning defect can be inferred when GT is inconsistent.

---

## v2 coverage cross-check (qwen-specific)

qwen agent compared its 7 new R classes against v2's 7 R classes and found:
- Near 1:1 overlap on 6 of 7 (R_A↔R1 13/17, R_B↔R2 30/33, R_C↔R3 25/27, R_D↔R4 11/14, R_F↔R5 5/5, R_E↔R6 6/6).
- qwen.R_G (9 cases, CausalInversion) is the new class — absorbs "symptom-as-cause" patterns that v2 distributed across R1/R3.
- v2's D coverage is fully preserved in new D taxonomy (all 105 qwen cases route identically).

No axis was missed by the new induction. The main value-add over v2: **4-framework pooling** exposes U3 (EdgeDirection) and U4 (NameTwin) as cross-framework classes that v2's single-agent scope could not identify.
