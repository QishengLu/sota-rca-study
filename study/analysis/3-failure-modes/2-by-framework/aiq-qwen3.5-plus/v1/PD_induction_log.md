# PD Induction Log — aiq-qwen3.5-plus

Process log for Phase PD-B induction. 113 labeled failure cases of `aiq-qwen3.5-plus`. Records triangulation issues, rejected candidate classes, merges, splits, and framework-specific scope decisions.

---

## Triangulation inconsistencies

None of the 113 cases produced disagreement across the three triangulation sources — (i) `labels.jsonl.evidence`, (ii) `per_case_analysis.md` Block (2)/(3), (iii) `dossiers/case_<idx>.md` Part B trajectory. For every case, the terminators field in labels.evidence, the "What the agent did" narrative, and the Part B stage markers agreed on:

- number of terminators produced
- services named at each terminator
- whether any stage was truncated
- which intents fired (as evidenced by the per-case analysis's citations of "log_top_pos", "z-metrics", "never queried X")

Confirmed = true for 113/113 cases.

---

## Fallback cases (final intent field missing)

The `meta.llm_intents.final` field was 100% populated for aiq-qwen3.5-plus (user-audited coverage). No case required fallback to `claude_opus_4_6`. None.

---

## Rejected candidate classes

Draft iterations went through two reject rounds before the final 8 classes settled. Each rejection logged with its reason.

### Rejection round 1

1. **PD_AnchoredOnLoudNoise** — ❌ REJECTED. Initial phrasing said "the agent anchored on the biggest log_top_pos entry". Discriminator Q1 failed: "anchored" is a reasoning verb. This is R U1 (LoudnessAnchorOverSilentVictim) described with process-flavor. The trajectory-observable part ("did only error_log_overview, no deep metric probe") was extracted into **PD_VolumeRankingWithoutDeepProbe**, which keeps only the pure action-inventory predicate.

2. **PD_IgnoredMissingSpanSignal** — ❌ REJECTED. Initial phrasing said "agent ignored missing-span signal despite PodFailure fault". Discriminator Q2 failed: "missing-span signal" is a description of the data state (spans are absent). The trajectory-observable part (no `container_resource` probe, no `k8s_state` probe for PodChaos) was absorbed into **PD_MetricLayerProbeAbsentForFaultCategory** (PodChaos variant). 5 cases with proximate_cause "missing-span signal ignored" now map cleanly to that class instead.

3. **PD_MistookContainerKillForBroker** — ❌ REJECTED. Initial phrasing said "agent mistook pod-kill for broker failure". Discriminator Q1 failed: "mistook" is a reasoning verb. This describes a reasoning conclusion (misattribution). Process action behind it: no jvm/k8s/container probe; named ts-rabbitmq without any SQL probing ts-rabbitmq-specific metrics. Absorbed into **PD_NamedRCWithoutTargetedProbe** + **PD_MetricLayerProbeAbsentForFaultCategory**.

4. **PD_LatencyIgnoredByErrorCountSearch** — ❌ REJECTED. Initial phrasing said "agent relied on error counts and missed latency signal". Discriminator Q2 failed: "missed latency signal" is a data phenomenon. The process core — "never ran `latency_ranking`, never ran metric-layer probes for latency-aware metrics" — is already captured in **PD_VolumeRankingWithoutDeepProbe** (log_overview fired + no deep metric probe).

### Rejection round 2

5. **PD_ReflectionReversesWithoutNewProbe** (separate class from PD_ReflectionReinforcesWithoutRevision) — ❌ REJECTED as SEPARATE class. The reversal and reinforcement patterns both share the same underlying process defect: the reflection stage ran to completion but without issuing any new targeted SQL for the candidate it committed to. Splitting them would create two classes with the same mechanism (redundant). MERGED into single **PD_ReflectionStageWithoutNewProbe** class. Reinforcement becomes a predicate sub-branch (distinct_terminator_services == 1); reversal becomes the other sub-branch (distinct > 1 AND new_candidate not newly probed). Both satisfy the same Positive criteria.

6. **PD_BaselineCompletelyAbsent** and **PD_BaselineContrastMissing** (two classes) — ❌ REJECTED as two classes. Initially split by whether baseline_collect fired at all (no_baseline=54) vs baseline_collect fired but not baseline_contrast (bc_only=58). Same underlying defect: the actual baseline-comparison action never happened. MERGED into single **PD_NoBaselineContrast** with two documented variants in the detection block. This keeps the class definition focused on what matters (contrast never done) while preserving the observable distinction.

### Retained but stress-tested

7. **PD_CompressOverwritesTerminator** — ⚠️ NEAR-REJECT. 100% co-occurrence with T8_CompressOverwritesTerminator (the aiq-specific theme), which caused concern about redundancy.  
   Resolution: T8 is a case-level *outcome* theme (describes what ended up in the final graph); PD_Compress is an *action-level* defect (describes what the compress step DID — emit a JSON whose root ≠ the terminator text). The predicate for T8 at labeling time was essentially the same trajectory signal the PD uses, which is why the overlap is 100%. They describe the same observable from two frames: T8 from the "what the wrong answer was" frame, PD from the "what action caused it" frame. Because the PD frame exposes a remediable process step (the compress layer), it is retained as its own class. Not folded into T8 because T-themes are the previous aiq-specific agent theme taxonomy and are not the PD axis.

   Additionally, the PD_Compress predicate does not reference R (reasoning) or D (data) at all — it's purely about the compress-action output. So it passes both discriminator tests cleanly.

---

## MECE enforcement (class definition level)

**Merges performed** (draft → final):
- `PD_BaselineCompletelyAbsent` + `PD_BaselineContrastMissing` → `PD_NoBaselineContrast` (merged because same missing-action; 54 + 58 cases; variants retained in detection block).
- `PD_ReflectionReinforcesWithoutRevision` + `PD_ReflectionReversesWithoutNewProbe` → `PD_ReflectionStageWithoutNewProbe` (merged; same mechanism — refine committed without new probe; distinct cases 36 + 12 ≈ 48).

**Splits performed**:
- None. All initially-split candidates either merged or remained as the same class.

**Overlap resolution**:
- PD_VolumeRankingWithoutDeepProbe and PD_MetricLayerProbeAbsentForFaultCategory both speak to "missing deep metrics". Kept separate because:
  - PD_VolumeRanking triggers on the combination "error_log_overview fired + NO deep metric at all". It captures the "stopped at log ranking" pattern regardless of fault category.
  - PD_MetricLayer triggers on the combination "fault category is JVM/Pod/Network-on-DB + specific pair of metric intents empty". It captures the fault-category-specific gap even when log_overview was never run.
  - At the DEFINITION level they are distinct predicates. At the CASE level they often co-occur (expected — when the agent did ranking without metrics and the fault category needed metrics, both fire).
- PD_NamedRCWithoutTargetedProbe and PD_VolumeRankingWithoutDeepProbe: different predicates (RC-specific vs global). Kept separate.
- PD_StageEndsWithoutCommitment and PD_ReflectionStageWithoutNewProbe: distinct. First is "stage produced no terminator". Second is "stage produced a terminator without new evidence". Mutually non-exclusive but definitionally different.

**Co-occurrence (quick sanity)**:
- PD_CompressOverwritesTerminator is 100% co-occurrent with T8 theme — expected, same predicate from different frames. NOT redundant with any R or D class (R themes U1-U5 concern reasoning mechanisms; none target the compress step).
- PD_NoBaselineContrast is 112/113 — near-universal. Not a discriminating predicate for aiq's failure set; it's a documentation of the pipeline's structural weakness. Kept.
- No PD-vs-D and PD-vs-R pairs exceed 90% — PD_NamedRCWithoutTargetedProbe has ~79% correlation with T3+T6+T7 (the three agent themes that produce RCs by synthesis), which is by design: the PD describes the action-level root of those theme patterns.

---

## Class density check (≥3 canonical case examples per class)

| Class | n | canonical examples in PD_inductive.md |
|---|---|---|
| PD_NoBaselineContrast | 112 | case_130, case_99, case_2211 (and 109 others) |
| PD_StageEndsWithoutCommitment | 108 | case_341, case_2130, case_1218 (and 105 others) |
| PD_NoCallTreeBuild | 66 | case_130, case_1504, case_710 (and 63 others) |
| PD_ReflectionStageWithoutNewProbe | 48 | case_99, case_601, case_2211 (and 45 others) |
| PD_MetricLayerProbeAbsentForFaultCategory | 40 | case_247, case_603, case_784 (and 37 others) |
| PD_NamedRCWithoutTargetedProbe | 37 | case_130, case_323, case_4073 (and 34 others) |
| PD_VolumeRankingWithoutDeepProbe | 24 | case_283, case_1421, case_3673 (and 21 others) |
| PD_CompressOverwritesTerminator | 8 | case_603, case_860, case_1886, case_3600 |

All classes have ≥3 canonical examples. Smallest class (PD_CompressOverwritesTerminator, n=8) exceeds the hard threshold with room to spare.

No merging or promotion needed on density grounds.

---

## Framework-specific scope decisions

Three classes tagged `scope=framework_specific`:

1. **PD_StageEndsWithoutCommitment** — relies on aiq's 3-stage refine pipeline structure. Unified frameworks (single-agent ReAct, flat-loop agents) don't have sub-stage termination semantics, so "at least one stage truncated" has no analog. The PD can still be re-expressed in unified frameworks as "agent hit max_rounds without producing a terminal output", but the 3-stage shape is unique.

2. **PD_ReflectionStageWithoutNewProbe** — requires at least 2 terminator events from distinct refine stages. Non-reflective frameworks produce a single final terminator and have no refinement step, so this PD does not apply.

3. **PD_CompressOverwritesTerminator** — requires a distinct `compress_to_graph` synthesis step between terminator and final JSON. aiq has this step; thinkdepthai/deerflow/Auto-Deep-Research emit the final JSON directly from the LLM without a separate structured-output compression. Cross-framework mapping at PD-C phase should mark this PD as not-applicable for those frameworks.

The remaining 5 classes (PD_NoBaselineContrast, PD_NoCallTreeBuild, PD_MetricLayerProbeAbsentForFaultCategory, PD_NamedRCWithoutTargetedProbe, PD_VolumeRankingWithoutDeepProbe) are `scope=unified` — the predicates depend only on the intent-list of SQLs and on fault_category metadata, which are available for every framework.

---

## Self-reflection — classes I am LEAST sure about

Ranking the 8 classes by my uncertainty for the PD-C reviewer's attention:

### High uncertainty — recommend focus

1. **PD_NamedRCWithoutTargetedProbe (n=37)** — Class membership is heuristic-based (uses primary theme T3/T6/T7 as proxy). A precise audit would parse every SQL's WHERE clause to confirm `service_name='<final-RC>'` is absent. I estimate 3-5 of the 37 cases may fail the strict predicate after SQL audit (cases where the agent did issue a probe but the proximate cause was still "hub hallucination" for other reasons). The class's principle is sound; the membership list may shrink slightly.

2. **PD_ReflectionStageWithoutNewProbe (n=48)** — Two sub-predicates (reinforcement vs reversal) were merged. Arguably the reversal sub-branch needs a stricter check: "did the new candidate appear in any stage-N+1 SQL BEFORE its terminator?". Some of the 12 reversal cases may have the agent running a new probe but interpreting its results wrongly — which would be R, not PD. My assignment defaults to "no new probe" based on the terminator size field (large terminator text doesn't guarantee new SQL beforehand), so this may over-include.

### Medium uncertainty

3. **PD_StageEndsWithoutCommitment (n=108)** — Very high coverage (96%). Raises the question: is "stage truncation" really a defect, or just a budget issue? In aiq specifically, the 3-stage budget (stage_0_main 3000 rounds, refine stages 2000 each) being hit suggests the agent could not converge. I treat non-convergence as a PD because it means the agent's exploration loop failed to reach a bounded conclusion — a process outcome. PD-C reviewer: consider whether this should be downgraded to a "framework structural fact" rather than a case-level PD.

4. **PD_CompressOverwritesTerminator (n=8)** — 100% co-occurrence with T8. I argued above it's retained because it describes a distinct action frame. PD-C reviewer: verify that T-axis and PD-axis are meant to be distinct in the project; if T and PD collapse, this class would be redundant. If T is considered legacy agent-theme and PD is the new axis, keep.

### Lower uncertainty

5. **PD_NoBaselineContrast (n=112)** — Essentially universal for aiq-qwen failures. Extremely clean predicate; just double-check the 1 exception (case_4519 — did run baseline_contrast but still failed on A5-upstream-stop).

6. **PD_NoCallTreeBuild (n=66)** — Clean predicate on intent fire.

7. **PD_MetricLayerProbeAbsentForFaultCategory (n=40)** — Fault-category-conditional predicate is very clean; membership is mechanical.

8. **PD_VolumeRankingWithoutDeepProbe (n=24)** — Clean predicate on intent fire combinations.

---

## Cross-axis co-occurrence note (for PD-C phase)

PD_NoBaselineContrast is 99.1% of failed cases. For the cross-framework phase, it's worth checking:
- What is the baseline_contrast rate among CORRECT cases for aiq?  
- If correct cases ALSO rarely use baseline_contrast, this PD is not a failure discriminator — it's just an aiq structural habit. If correct cases use it more often, it IS a defect driver.  

Similarly for PD_NoCallTreeBuild (66/113 = 58.4%). These two unified PDs need rate-of-use comparison on the positive (correct) set to decide whether they're discriminating vs. universal.

This data is easily fetchable — the DB has `meta.llm_intents.final` for correct cases too.
