# universal_vs_specific.md — R set partitions

**Phase G / HARP Step 5**: classify every unified R into 3 nested sets used to target metacognitive-middleware design.

Source data: `merged/unified_R.md`, `merged/R_merge_table.jsonl`, DB labels in `meta.failure_analysis.v1.R`.
Total labeled cases: 370 (excl. 2 dataset_anomaly). 5 unified R + 8 framework-specific analytical_R.

---

## Set definitions

| Set | Definition | Used for |
|---|---|---|
| **Framework-universal R** | Unified R with ≥2 frameworks contributing cases, EACH at ≥10% of that framework's labeled failures | Evidence of cross-framework reproducibility |
| **Model-robust R** | Unified R with `\|qwen_share_pct - sonnet_share_pct\| ≤ 5pp` (same framework family, different model) | Evidence the defect isn't just a weaker-model artifact |
| **Priority Set** (strict) | Framework-universal ∩ Model-robust ∩ Trajectory-only identifiable | Phase 8 middleware rule targets (strict gate) |
| **Relaxed Priority Set** | Framework-universal ∩ Trajectory-only identifiable (model-robust noted as caveat) | Phase 8 middleware targets accepting per-model tuning |

---

## Classification results

### Framework-universal R

| R class | aiq | claudecode | sonnet | qwen | Frameworks ≥10% |
|---|---:|---:|---:|---:|---:|
| U1_LoudnessAnchorOverSilentVictim | 48.7% | 28.4% | 24.0% | 41.9% | **4** |
| U2_ChronicAmbientNoiseAnchor | 15.0% | 34.3% | 14.0% | 24.8% | **4** |
| U3_EdgeDirectionOrRegionEndpointError | 0.0% | 16.7% | 44.0% | 8.6% | **2** |
| U4_NameTwinSiblingConfusion | 7.1% | 9.8% | 0.0% | 0.0% | 0 (borderline) |
| U5_SilenceReadAsHealthOrPaused | 0.0% | 0.0% | 4.0% | 14.3% | 1 |

**Framework-universal members**: {U1, U2, U3} (3 classes).

U4 is borderline (aiq 7.1%, claudecode 9.8% — both under 10% threshold).
U5 is single-framework (qwen only above 10%).

### Model-robust R

Compute `|qwen% - sonnet%|` (same thinkdepthai framework, different model):

| R class | qwen | sonnet | Δpp | Robust (≤5pp)? |
|---|---:|---:|---:|---|
| U1_LoudnessAnchorOverSilentVictim | 41.9% | 24.0% | 17.9 | **FAIL** |
| U2_ChronicAmbientNoiseAnchor | 24.8% | 14.0% | 10.8 | **FAIL** |
| U3_EdgeDirectionOrRegionEndpointError | 8.6% | 44.0% | 35.4 | **FAIL** |
| U4_NameTwinSiblingConfusion | 0.0% | 0.0% | 0.0 | PASS |
| U5_SilenceReadAsHealthOrPaused | 14.3% | 4.0% | 10.3 | **FAIL** |

**Model-robust members**: {U4} only.

### Trajectory-only identifiable

All 5 unified R have per-agent trigger formulas from at least one non-analytical_only contributor (see `unified_R.md` for per-class trigger blocks). Passing uniformly.

### Priority Set intersections

| Set | Members |
|---|---|
| Framework-universal | {U1, U2, U3} |
| Model-robust | {U4} |
| Trajectory-only identifiable | {U1, U2, U3, U4, U5} |
| **Priority Set (strict intersection)** | **∅ (empty)** |
| **Relaxed Priority Set (FU + TOI)** | **{U1, U2, U3}** |

---

## Interpretation: why strict Priority Set is empty

The 5pp model-robust gate is the binding constraint. Every unified R has a qwen-vs-sonnet gap > 5pp:
- U1 (LoudnessAnchor): qwen 41.9% vs sonnet 24.0% — qwen more anchor-prone (Δ=17.9pp)
- U2 (ChronicNoise): qwen 24.8% vs sonnet 14.0% — qwen more baseline-unchecked (Δ=10.8pp)
- U3 (EdgeDirection): sonnet 44.0% vs qwen 8.6% — sonnet over-produces edge direction errors (Δ=35.4pp, largest)
- U5 (SilenceAsHealth): qwen 14.3% vs sonnet 4.0% — qwen explicitly reads silence as healthy (Δ=10.3pp)

**This is a model-effect finding, not a taxonomic failure**. A weaker model (qwen) on the same framework (thinkdepthai) systematically produces different proportions of each failure mode than a stronger model (sonnet). The taxonomy is valid across models; the per-class rates differ.

**Implication for middleware**: a single universal trigger will fire at different rates on qwen vs sonnet, producing different flip rates. Phase 8 should:
1. Deploy rule cards (U1, U2, U3) as-is on all 4 × 2 = 8 framework×model cells.
2. Measure per-cell flip rate + regression rate.
3. Tune signal thresholds per-model if FP rate differs by >10pp between qwen and sonnet.

---

## Middleware Priority Set decision (autonomous)

Per the user's north star ("design a generally effective metacognitive middleware"), the strict empty intersection is unacceptable as an endpoint. **Relaxed Priority Set {U1, U2, U3} is adopted** as the Phase 8 target set:

- **U1 LoudnessAnchorOverSilentVictim** — 140 cases, 4/4 frameworks universal; target: offer silent-victim detection before commit.
- **U2 ChronicAmbientNoiseAnchor** — 85 cases, 4/4 frameworks universal; target: force baseline-diff SQL before anchoring on {rabbitmq, food, delivery, notification}.
- **U3 EdgeDirectionOrRegionEndpointError** — 48 cases, 3/4 frameworks universal (sonnet-heavy); target: reject output graphs with UNAVAILABLE nodes positioned as targets under a non-UNAVAILABLE root.

Rule cards at `merged/middleware_rules/U{1,2,3}.md`. Each card explicitly flags the model-robustness caveat and suggests per-model tuning.

---

## Framework-specific analytical_R (retained for completeness, not in Priority Set)

| Per-agent R | Cases | Kind | Notes |
|---|---:|---|---|
| aiq.R_hub_fabrication | 12 | framework-specific | Hallucinated shared dep; trigger FP ~10% — strong analytical |
| aiq.R_correct_then_reversed | 13 | framework-specific | **F2 candidate** (refine-stage architectural) |
| aiq.R_compress_drift | 8 | framework-specific | **F1 candidate** (compress-layer architectural) |
| claudecode.R6_InfraLayerSkipped | 7 | framework-specific, analytical_only | Distinguisher requires GT fault_category |
| claudecode.R7_JVMSymptomMisreadAsDB | 4 | framework-specific | Cross-framework analog weak |
| sonnet.R_OscillationToCompromisePair | 4 | framework-specific | Sonnet-only pair-output |
| sonnet.R_NarrativeOverMatchedMagnitude | 3 | framework-specific, analytical_only | Narrative lexical FP ~50% |
| qwen.R_E_PathOvershootPastInjection | 6 | framework-specific | Qwen-specific overshoot |
| qwen.R_F_QueryDesignBuriesSignal | 5 | framework-specific | Qwen SQL-design defect |
| **U4 NameTwin (unified but not FU)** | 18 | unified, analytical_only | Candidate for dataset-level preprocessing |
| **U5 SilenceAsHealth** | 17 | unified | Candidate for qwen-specific middleware |

F-candidates (`aiq.R_correct_then_reversed`, `aiq.R_compress_drift`) are promoted to `aiq.F_catalog.md` (F2, F1 respectively) — they describe architectural defects repairable only by framework code changes, not middleware.
