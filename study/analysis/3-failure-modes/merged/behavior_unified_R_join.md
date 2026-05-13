# behavior_unified_R_join.md — R × trajectory-only signal cross-tabulation

**Phase G**: For each unified R (and framework-specific analytical_R), compute per-case averages of trajectory-only signals derived from `meta.llm_intents.claude_opus_4_6` + 5-stage mapping.

**Purpose**: empirical validation that the trigger signals used in `middleware_rules/U{1,2,3}.md` actually differ between R classes. Also: find hidden patterns (e.g., R classes with 100% baseline-check yet still failing → a different trigger is needed).

**Data source**: DB live computation, 370 cases labeled with both R and llm_intents.

---

## Signal definitions

| Signal | Formula | Allowed at runtime? |
|---|---|---|
| baseline_fired_pct | fraction of cases where `baseline_collect` OR `baseline_contrast` appeared ≥1 time in intent sequence | YES |
| avg_phase_cov | mean of `\|{triage, trace, log, metric, baseline} ∩ intents\|` / 5 per case | YES |
| avg_intent_count | mean SQL/tool-call count per case (proxy for trajectory length) | YES |
| same_intent_loop_ge4_pct | fraction of cases where max consecutive repeat of same intent ≥ 4 | YES |
| avg_modal | mean `\|{logs, traces, metrics}\|` data_types touched per case | YES |

All are trajectory-only (no GT dependency). Derivable from live `llm_intents` during inference (opus classifier runs per SQL).

---

## R × signal table

| R class | N | baseline% | avg_phase | avg_intents | loop≥4% | avg_modal |
|---|---:|---:|---:|---:|---:|---:|
| **U1 LoudnessAnchorOverSilentVictim** | 140 | 68.6% | 0.92 | 55.9 | 72.1% | 2.69 |
| **U2 ChronicAmbientNoiseAnchor** | 85 | 69.4% | 0.93 | 49.7 | 68.2% | 2.26 |
| **U3 EdgeDirectionOrRegionEndpointError** | 48 | 91.7% | 0.95 | 43.7 | 52.1% | 2.35 |
| **U4 NameTwinSiblingConfusion** | 18 | 83.3% | 0.94 | 62.7 | 61.1% | 2.06 |
| **U5 SilenceReadAsHealthOrPaused** | 17 | 76.5% | 0.94 | 42.8 | 64.7% | 3.00 |
| aiq.R_correct_then_reversed *(F2)* | 13 | 69.2% | 0.94 | 73.7 | 61.5% | 3.00 |
| aiq.R_hub_fabrication | 12 | 50.0% | 0.90 | 73.5 | 75.0% | 3.00 |
| aiq.R_compress_drift *(F1)* | 8 | 37.5% | 0.88 | 71.0 | 62.5% | 3.00 |
| claudecode.R6_InfraLayerSkipped *(analytical_only)* | 7 | 100.0% | 0.97 | 48.9 | 100.0% | 1.14 |
| qwen.R_E_PathOvershootPastInjection | 6 | 100.0% | 1.00 | 43.2 | 100.0% | 3.00 |
| qwen.R_F_QueryDesignBuriesSignal | 5 | 40.0% | 0.84 | 46.4 | 100.0% | 3.00 |
| claudecode.R7_JVMSymptomMisreadAsDB | 4 | 100.0% | 1.00 | 72.8 | 100.0% | 1.00 |
| sonnet.R_OscillationToCompromisePair | 4 | 100.0% | 1.00 | 37.8 | 50.0% | 3.00 |
| sonnet.R_NarrativeOverMatchedMagnitude *(analytical_only)* | 3 | 100.0% | 1.00 | 36.0 | 66.7% | 3.00 |

---

## Observations on trigger validity

### Observation 1: U2 (ChronicNoise) has 69.4% baseline-fired — **30% of U2 cases had baseline queries that did not save them**

The U2 rule card's trigger relies on `C3: NO SQL joining normal_logs with abnormal_logs` AND `C2: RC ∈ chronic-noise carriers`. The baseline-fired% of 69.4% means ~31% of U2 failures (26 cases) had **some** baseline intent fire but still missed the cross-check. Interpretation:
- `baseline_collect` (sole query of normal data) ≠ `baseline_contrast` (comparison of normal vs abnormal). Collecting without contrasting is insufficient.
- The `C3` check in U2's rule card correctly requires JOIN/UNION of normal+abnormal, not just baseline_collect existence. **Trigger design is correct.**

### Observation 2: U1 (LoudnessAnchor) has 68.6% baseline-fired — middleware must not gate on baseline-non-existence alone

Similar to U2: 68.6% baseline-fired means U1 triggers cannot rely on "baseline intent never fired" — they must rely on "baseline intent did not target the specific candidate". The U1 rule card's `C3` allows this via `phase_coverage < 3` OR `baseline intents absent`. OK.

### Observation 3: aiq.R_compress_drift + aiq.R_hub_fabrication both show **low baseline% (37.5%, 50%)** AND **high same-intent-loop% (62.5%, 75%)**

These are F-candidates / framework-specific. Their distinctive signal combo (low baseline + high loop) differs from U1/U2 and supports keeping them separate from unified R middleware triggers. The compress_drift case especially — at 37.5% baseline — reinforces the architectural-F classification (different behavior signature from unified R).

### Observation 4: claudecode.R6 + R7 + qwen.R_E + qwen.R_F all have **100% same-intent-loop**

Framework-specific classes with small N (≤7) all show consistent same-intent-loop patterns. This is potentially a useful signal, but the analytical_only or small-N status limits utility.

### Observation 5: U5 (SilenceAsHealth) has max avg_modal = 3.0 (all 3 data_types probed) yet still fails

U5 failures are not "forgot to look at metrics" — the agent DID touch metrics. The defect is lexical interpretation ("no errors → healthy"). This validates the U5 discussion: lexical signature (health-inference text) is the only discriminator, not coverage.

---

## Quality gate check

Per unified_R.md, Gate 3 requires: **trigger precision ≥ 0.6 AND recall ≥ 0.5 on labeled cases**. This cannot be computed without running the trigger formulas as executable rules. Phase 8 implementation plan:

1. Convert U1/U2/U3 rule-card trigger pseudocode into executable Python functions consuming `trajectory` + `llm_intents`.
2. Run over all 370 labeled cases.
3. Compute per-R: precision, recall, F1.
4. Update `middleware_rules/U{n}.md` if precision < 0.6 (tighten) or recall < 0.5 (loosen).

For now: the signal-difference observations above give qualitative evidence that U1/U2/U3 triggers distinguish their R classes from non-R classes (e.g., baseline% on non-R-labeled correct cases is likely near 95-100% — Phase 8 should measure).

---

## Connection to behavior fingerprint (not regenerated here)

Existing dashboard `analysis_cache.json` has:
- `phase_coverage` (8-dim fingerprint input) — same formula as above
- `evidence_utilization` (R→T round-level) — computed separately per exp_id
- `n-gram` over intent sequences
- `cost_metrics` (tokens, effective_rounds)

For full cross-framework R × fingerprint × intent × ngram view, rerun the Phase 6 `behavior_failure_join.py` with the new unified R labels on each exp_id. This was not performed in-scope for Phase G; it is a Phase 8 preparation task.
