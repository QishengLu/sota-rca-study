# PD_induction_log.md — thinkdepthai-claude-sonnet-4.6

Process-defect (PD) induction trace. 51 cases, bottom-up, two draft-rejections.

---

## Triangulation inconsistencies

Per-case triangulation was done from three sources:

- (i) `labels.jsonl` — proximate_cause + primary/secondary
- (ii) `per_case_analysis.md` — structured narrative with divergence block
- (iii) dossier trajectory + intent sequence + targeted-probe counts

Cases with **inconsistency** between sources (confirmed=false) — one case:

- `case_4463` (dataset_anomaly) — labels.jsonl marks `dataset_anomaly`; per_case_analysis.md confirms GT ≠ injection spec; dossier trajectory is coherent for the injection spec. Agent answer `ts-food-service` matches datapack but not DB meta. PD signals still extracted (PD1, PD2, PD5 fire) but case flagged `confirmed=false` because the failure is not process-originated.

No other triangulation conflicts: for every other case, all three sources agree on the observed behaviour, and the PD signals derived from (iii) align with the narrative in (ii).

---

## Fallback cases

None. LLM-intent coverage on `thinkdepthai-claude-sonnet-4.6` exp_id is 100% (51/51), no need to fall back to rule-based `classify_intent()`.

---

## Rejected candidate classes

### Draft-1 candidates, rejected

1. **`NetworkLayerProbeAbsent`** (n=2 cases: 1862, 3112) — for DNS/rabbitmq-family faults that never triggered a `network_layer` intent. **Rejected: density too low** (< 3 cases). The underlying phenomenon is subsumed under PD2 (candidate not isolated) when rabbitmq appears in findings but is not probed with targeted SQL on its own errors.

2. **`SchemaDiscoveryThenCommit`** — agent does `list_tables` / `get_schema` extensively in rounds 1-3 then commits after minimal SQL. **Rejected: not detectable from `meta.llm_intents.final`** because schema_discovery and think_tool are excluded from intent coverage per `intention_category.md`. Could only be detected from raw tool_calls; scope creep.

3. **`PremCommitBeforeBudgetHalf`** (n=0 with strict thresholds) — first "ROOT CAUSE IS X" think_tool statement appears before round N/2 AND fewer than 3 SQL rounds after commitment test an alternative. **Rejected: zero members** with strict threshold (`first_commit / total ≤ 0.60 AND sql_rounds_after ≤ 3 AND tail_rounds ≥ 3`). Relaxing the threshold produces n ≈ 28 but then it becomes the default ReAct pattern, not a defect. Dropped.

4. **`PodNameConfusionInOutput`** (n=1: 3236) — agent outputs a pod-suffix identifier (`mysql-0`) instead of a service name (`mysql`). **Rejected: density too low**. Captured instead under PD2's "exactly one targeted probe" subtype.

5. **`LowIntentDiversity`** (n=0 at threshold uniq_intents ≤ 7 AND nI ≥ 25) — wanted to catch "repertoire stuck in a narrow band". **Rejected: no cases pass strict threshold**, and the phenomenon is captured by PD2 ("candidate never isolated" → narrow WHERE coverage) and PD5 (think_tool repetition).

6. **`PredictedRCNotConfirmationProbed`** — predicted RC service has zero `WHERE service_name = '<pred>'` after the last pivot. **Rejected: can't separate from baseline ReAct cadence** — many agents commit via think_tool without a final confirmation SQL (that's how the framework loop ends). Would flood with false positives.

### Draft-2 candidates, rejected

7. **`ProbeScopeNarrow`** (n=32: set of services with ≥ 2 WHERE probes ≤ 3) — overlap with PD2 = 69% (22/32). **Rejected: insufficient MECE separation** from PD2; they capture the same underlying "narrow coverage" phenomenon at different angles. Kept PD2 as the more specific class (references specific candidate services mentioned in earlier findings).

8. **`TailConfirmationHeavy`** — pivot_round at label / n_rounds > 0.40 with no new hypothesis after. **Rejected: only 12 cases have pivot_round labelled**; can't build a reliable class without broader manual pivot annotation.

9. **`HighThinkNarration but split into sonnet/qwen/claudecode variants`** — PD5 could be further split by per-agent think_tool patterns. **Rejected: this file is framework-specific to thinkdepthai-claude-sonnet-4.6; no need to split.** Tagged `scope=framework_specific` for Phase 7.5 cross-framework merge.

10. **`SiblingNeverDisambiguatedByPair`** — agent picked X when GT was sibling Y; expected a `WHERE service_name IN ('X','Y')` comparative SQL. **Rejected: requires knowledge of the twin pair which is not purely trajectory-detectable.** A restrictive trajectory-only version ("agent never ran a multi-service WHERE IN (...) query covering 2+ mentioned candidates") has n=7, but overlaps >80% with PD2 → folded into PD2.

### D/R-contaminated candidates, rejected

11. **`AnchoredOnLoudSignal`** — "agent committed to the loudest anomaly without testing". **Rejected: this is R, not PD.** "Committed" and "anchored" are reasoning verbs. Equivalent to U1_LoudnessAnchorOverSilentVictim / T1_SlowestLeafAnchoring / T5_LoudestHotspotNarrative.

12. **`DiscardedContradictingEvidence`** — agent saw a fault-magnitude signal matching injection but chose a different candidate. **Rejected: R.** The action of running the probe was correct; the defect is reasoning (case 371 literally had the 3469ms signal in-hand but preferred worker-1 narrative; see dossier).

13. **`MissingSpanIgnored`** — agent saw `missing_span` but committed elsewhere. **Rejected: D+R mixed.** Missing-span is a data state; ignoring it is R.

### Final rejection round

- After Draft 2 (5 classes: PD1–PD5), recomputed coverage → 3 cases unflagged (371, 1495, 2183). Expanded class set to 7 by including PD6 (multi-RC output, 7 members) and PD7 (trace_follow absent, 6 members). Final coverage 50/51. Accepted.

---

## MECE enforcement

- Every pairwise overlap rechecked: see `PD_inductive.md` "Cross-check summary". Max 55% (PD1 × PD3). No class is a strict subset.
- PD6 × PD4 = 31% (4 cases share) — both classes characterize "failure to decide", but:
  - PD4 is about **runtime duration** (trajectory length)
  - PD6 is about **output shape** (multi-entry RC array)
  - Case 572 is in PD6 but not PD4 (39 rounds, under budget cap, still emitted multi-RC)
  - Case 2174 is in PD4 but not PD6 (69 rounds, single-RC output)
  - The two are conceptually distinct and both can fire independently.

- PD3 × PD7 = 6% (1 case shared: 3555). Both relate to call-path exploration but target different query primitives. MECE-distinct.

---

## Class density check

- **All 7 classes ≥ 3 members** (min = PD7 with 6).
- Unflagged: 1 case (1495). Acceptable — the case is a pure reasoning failure with adequate process (probed GT 7×, still committed to neighbor based on node-load signal).
- Weakest density: PD7 (n=6) and PD6 (n=7). Both are retained because:
  - They describe distinct, trajectory-observable actions not covered by larger classes.
  - Raising threshold to absorb them into neighbors would break MECE (PD7 cases include 1484, 3868 — these are NOT in PD3 because call_tree_build fired; the missing action is trace_follow specifically).

---

## Framework-specific scope rationale

- **PD5 (ThinkNarrationDominant)** tagged `scope=framework_specific`.
- Why: `think_tool` is an interleaved action specific to ReAct-style agents with explicit think-action split. thinkdepthai wires it as a first-class intent between SQL rounds; on failure cases the think_tool_count/n_rounds ratio exceeds 0.40 on 23/51 cases.
- Other frameworks in the suite:
  - Auto-Deep-Research / aiq / OpenRCA / mABC / DeepResearchAgent all have think_tool registered but their loops do not interleave it at comparable frequency on failure cases (based on cross-framework intent analysis in `intention_category.md`).
  - deer-flow-v2 / TaskWeaver / ClaudeCode explicitly filter think_tool out of the shared prompt — no think_tool at all.
- Consequence: PD5's signal (high think_ratio without new WHERE branches) cannot be computed meaningfully on think_tool-free frameworks. Kept framework-specific to avoid polluting the cross-framework merge.

The other 6 classes are shared — all rely on intent-category presence/absence or trajectory length, which every framework produces.

---

## Detection-code sketch (for downstream tooling)

```python
def detect_PDs(case):
    intents = case['meta']['llm_intents']['final']
    counts = Counter(i['intent'] for i in intents)
    n_rounds = case['trajectory'].rounds
    tt_count = count_think_tool(case['trajectory'])
    probes = count_service_name_where_probes(case['trajectory'])  # {svc: count}
    final_rcs = case['final_answer']['root_causes']
    fault_type = case['meta']['fault_type']
    
    pds = []
    if counts.get('baseline_contrast', 0) == 0:
        pds.append('PD1_BaselineContrastSkipped')
    # PD2 requires knowing which services were "candidate" — use union of services mentioned in SQL results / error logs
    mentioned = set(get_mentioned_services(case['trajectory']))
    probed = {s for s, c in probes.items() if c >= 2}
    if mentioned - probed - {s for s, c in probes.items() if c == 1}:
        pds.append('PD2_CandidateNeverIsolatedByWhere')
    if is_edge_fault(fault_type) and counts.get('call_tree_build', 0) == 0:
        pds.append('PD3_CallTreeBuildAbsent')
    if n_rounds >= 45:
        pds.append('PD4_BudgetExhaustCommit')
    if tt_count >= 15 and tt_count / max(n_rounds, 1) > 0.40:
        pds.append('PD5_ThinkNarrationDominant')
    if len(final_rcs) >= 2:
        pds.append('PD6_CompromiseMultiRCOutput')
    if counts.get('trace_follow', 0) == 0 and len(intents) >= 20:
        pds.append('PD7_TraceFollowAbsent')
    return pds
```

---

## Self-check vs frozen D and R tables

Co-occurrence of each PD with the frozen sonnet D projection and T1-T8 primary R labels was computed in the induction pipeline. No PD exceeded 90% co-occurrence with any D or R class:

- Max PD × D: PD3 × D_edge_symmetric_ambiguity = 39% (7/18)
- Max PD × R: PD3 × T3_EdgeCallerCalleeConfusion = 61% (11/18)

PD3's elevated correlation with T3 is expected (edge-fault cases tend to both produce T3 reasoning errors and expose the call_tree_build absence), but the two remain distinct conceptual layers: PD3 is the missing action, T3 is the resulting mis-attribution. PD3 fires on 7 cases where T3 does NOT (471/T4, 3033/T3-secondary, 3236/T8, 3555/T3 only for 3555 actually, 4423/T3 with secondary T6, 4510/T3-only, 4739/T4). Confirms MECE at the analytical-layer level.
