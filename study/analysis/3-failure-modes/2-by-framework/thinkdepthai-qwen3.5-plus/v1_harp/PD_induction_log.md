# PD Induction Log — thinkdepthai-qwen3.5-plus

Bottom-up process-defect induction over 105 failure cases. Triangulation across three sources: (i) labels.jsonl.proximate_cause/label (D and R fields ignored during induction), (ii) per_case_analysis.md divergence blocks, (iii) dossier raw trajectory (SQL + think_tool + intents from meta.llm_intents.final).

---

## 1. Triangulation inconsistencies

Zero cases required overriding (iii) with (i) or (ii). Disagreement pattern observed: (i) labels use single `proximate_cause` phrase while (ii) per_case_analysis offers multi-sentence narrative; these are complementary not contradictory. (iii) trajectory intents confirm action presence/absence numerically.

Five cases flagged for manual inspection during induction (each resolved by checking the raw.json):

| case | concern | resolution |
|---|---|---|
| 33 | proximate_cause says "anchored on pre-existing background error" — suggests chronicity reasoning present | Check think_tool: no keyword match → PD8 NOT fired (surprisingly the agent's think never explicitly considered "pre-existing"; the labeler's phrase reflects the behaviour observed externally). PD1 and PD2 fire. |
| 2988 | label says HeterogeneousMetricQuery buried CPU signal — unique pattern | Check intents: actually this is the ONE case with `baseline_contrast` fired (via explicit normal vs abnormal subquery on one metric). PD1 does NOT fire. PD6 fires (service-level AVG ranking). |
| 832 | reversed caller-callee causality — does it fit PD4? | Check trajectory: call_tree_build NOT fired; PD4 fires. PD8 fires (no chronicity narration). |
| 2700 | label says "equated no-error-code with healthy" | PD5 fires strongly (error-status filter used, no Unset probe). Also PD8 (no chronicity). |
| 2598 | "blamed order-rejector using business-logic narrative" — PD-adjacent but narrative is R-territory | PD1, PD2, PD5, PD6 fire. The narrative aspect belongs to R7 BusinessLogicNarrative; PD side is that seat-service latency metric was never probed. |

Triangulation-confirmed rate: 105/105 (all cases land on ≥2 PDs with signals visible in ≥2 of the three sources).

---

## 2. Fallback / empty-class cases

Empty allowed per protocol. Distribution of PDs per case:
- 0 PDs: **0 cases** (no case fell through all detectors)
- 2 PDs: 3 cases
- 3 PDs: 13 cases
- 4 PDs: 35 cases
- 5 PDs: 37 cases
- 6 PDs: 17 cases

The two-PD minimum reflects the universality of PD1 (104/105) and PD2 (98/105). Every failure case either skipped baseline_contrast or skipped JVM-family drill (or both) — which is consistent with the finding that the qwen agent's exploration intent set is narrow.

---

## 3. Rejected candidate PD classes

Classes drafted and rejected during the two self-reject passes.

### 3.1 PD_CommitWithoutPostVerify (draft → rejected)
**Criterion**: After the last think_tool declaring a root-cause hypothesis, no SQL filters on that service.
**Rejection reason**: Measured at 100/105 — too universal to be discriminative. The thinkdepthai prompt pushes the agent to output the graph immediately after a think_tool commitment. Post-commit verification essentially never happens structurally. Since the signal is saturated, it carries zero information for distinguishing failure modes. Absorbed into PD7 (which captures the richer tail-fixation pattern).

### 3.2 PD_AmplitudeSortDominance (draft → rejected)
**Criterion**: ≥60% of SQLs have `ORDER BY … DESC` on `AVG/MAX/COUNT`.
**Rejection reason**: This is a trajectory fingerprint, but the criterion description bleeds into R-territory ("greedy amplitude selection"). Concretely: saying "most queries rank by DESC" is nearly synonymous with R2 AmplitudeGreed at the reasoning level because thinkdepthai's prompt instructs `ORDER BY DESC LIMIT K` as the default shape. Fails Q2 of the self-check. The specific narrow form (PD6: service-level AVG without span-level MAX follow-up) is retained because it captures the qwen-specific dilution artefact rather than just "ordering by DESC."

### 3.3 PD_EarlyPivotLongValidation (draft → rejected)
**Criterion**: pivot_round ≤ 30% of total_rounds.
**Rejection reason**: Identified 24/105 cases, which is a reasonable density, but the criterion uses `pivot_round` which is a labeler-assigned annotation rather than an intrinsic trajectory property. Promoting this to a class would make PD detection depend on human labels, violating "trajectory-observable" strictly. A trajectory-only surrogate ("round of first `root cause` mention in think_tool") was spot-checked and gave a 20% disagreement with pivot_round — too noisy to standardise. Kept as folklore, not a class. (Note: PD7 also uses pivot_round but only as a segmentation boundary for a query-count criterion; the fixation pattern is robust to shifts of ±5 rounds in the pivot boundary.)

### 3.4 PD_SpeculativeCrossServiceLink (draft → rejected)
**Criterion**: think_tool asserts "service A depends on service B" without any prior SQL evidence of that link.
**Rejection reason**: Detected only 2 strong cases (3524, 2716 speculate ticket-office hosts rabbitmq). Below the 3-canonical-member threshold. More importantly, deciding "without prior SQL evidence" requires semantic parsing of think_tool text (what counts as evidence for A→B?), which breaks the boolean-detectable criterion. Left as a small failure-case annotation; not promoted.

### 3.5 PD_NoKeywordSearchOnObservedError (draft → rejected)
**Criterion**: think_tool mentions a specific error string but no SQL runs `WHERE message LIKE '%<string>%'` on both normal and abnormal logs.
**Rejection reason**: Overlaps heavily with PD1 at detection level. In 67/105 cases where the agent DID run keyword_search, the search was single-sided (abnormal only). That single-sidedness is the essence of PD1 (no baseline_contrast). Promoting a distinct PD would double-count.

### 3.6 PD_MaxIterationTruncation (draft → rejected)
**Criterion**: Trajectory ended at recursion_limit=100 without a committed RC.
**Rejection reason**: Zero cases match. Every failure case terminates with a committed (wrong) RC. This is a non-issue for thinkdepthai on this dataset.

---

## 4. MECE enforcement notes

### 4.1 PD2 vs PD3 overlap audit
PD2 (no JVM drill) ∧ PD3 (no container drill) co-occurs in 77/105 cases. `P(PD3 | PD2) = 77/98 = 78.6%`; `P(PD2 | PD3) = 77/84 = 91.7%`. The latter barely touches the 90% threshold from one direction. We keep both because:
- 21 cases have PD2 but not PD3 (agent DID probe container resource on some service)
- 7 cases have PD3 but not PD2 (agent DID probe JVM family on some service — though this is rare)
- The metric tables they probe live in distinct parquet files (JVM metrics in `*_metrics.parquet`, container metrics in `*_metrics_sum.parquet` and `*_metrics_histogram.parquet` for some columns)
- Their canonical fault-type correlates differ: PD2 is most damaging for JVMChaos family; PD3 is most damaging for PodChaos family

### 4.2 PD1 vs PD8 overlap audit
PD1 (104) ∩ PD8 (8) = 8 (every PD8 case is also PD1, since PD8 is a narrower think-level phenomenon). `P(PD1 | PD8) = 100%`. This does NOT trigger the 90% merge warning because we measure `P(class | other_class)` and PD1 has far more cases. `P(PD8 | PD1) = 7.7%`. Classes are distinct: PD1 is an action check (SQL); PD8 is a verbalisation check (think_tool text).

### 4.3 PD5 vs PD4 overlap audit
PD5 (73) ∩ PD4 (75) = 57. `P(PD4 | PD5) = 78%`, `P(PD5 | PD4) = 76%`. Below 90%. Distinct: PD5 is a query-filter complementarity issue; PD4 is a transitive-closure absence issue.

### 4.4 PD6 standalone audit
PD6 (18) — smallest "regular" class. Of the 18 members, 17 are also PD4 (no call_tree_build), but `P(PD4 | PD6) = 94%` looks like a merge warning. However, `P(PD6 | PD4) = 17/75 = 22.7%` — PD6 is a narrow sub-pattern. The merge rule is "no PD >90% co-occurrence with any D or R class"; PD cross-overlaps are permitted because multi-PD labelling of cases is the design. Leave PD6 distinct; it captures the qwen-specific AVG-ranking dilution which is the unique process marker of ~17% of failures.

---

## 5. Class density check

All 8 classes ≥ 3 canonical members. Smallest: PD8 = 8. Largest: PD1 = 104.

The large size of PD1-PD5 is informative, not a sign of over-broad criteria: the qwen3.5 agent has a characteristically narrow exploration repertoire (intents never touch baseline_contrast in 499/500 samples, jvm_state in 430/500, container_resource in 288/500). These are meaningful systemic process deficits, not artefacts of lax criteria. The saturation tells us *what the agent is doing*, not *nothing distinguishable*. Smaller classes (PD6/PD7/PD8) capture the finer-grained qwen-specific warping patterns.

---

## 6. Framework-specific scope rationale

Only **PD6_ServiceAvgNoSpanMaxDrill** is tagged `scope=framework_specific`. Justification:

- qwen3.5-plus defaults to `SELECT service_name, AVG(duration) ... GROUP BY service_name ORDER BY AVG DESC` as its first latency sort. This is a *model-behavioral* pattern tied to the qwen model's few-shot defaults. ClaudeCode/Opus traces use span-level drills earlier (per claudecode-qwen3.5-plus and thinkdepthai-claude-sonnet-4.6 dossiers). The absence of the span-level MAX follow-up is therefore idiosyncratic to the qwen backend inside thinkdepthai.
- The 17.1% rate among failures is non-trivial but not universal (qwen sometimes does run span drills).

The other seven PDs (PD1-PD5, PD7, PD8) are framework-agnostic in their definitions — the criteria (intent absence, error-status-filter-without-unset, tail-fixation, no-chronicity-token) are meaningful across any framework. They *may* have framework-specific rates, which is a cross-framework comparison question for Phase 7.5 merge, not a scope tag.

---

## 7. Co-occurrence with D and R frozen tables (orthogonality check)

Per D_projection_frozen.jsonl and R inferred from labels.jsonl:

- `P(D_class | PD)` >90% warnings: **none** across all 8 PDs × 7 D classes.
- `P(R_class | PD)` >90% warnings: **none** across all 8 PDs × 7 R classes.

Highest observed conditional: `P(D1_VictimSilentOnPath | PD2) = 36/98 = 36.7%`. Well below 90%. PDs are orthogonal to both D and R as designed.

---

## 8. Detection-method summary

- **Primary signal**: `meta.llm_intents.final` array (available in DB for 100% of qwen exp_id) — used for PD1, PD2, PD3, PD4.
- **Regex on concatenated trajectory SQL**: used for PD5, PD6.
- **Round segmentation + service-filter counter**: used for PD7.
- **Keyword scan on think_tool text**: used for PD8.

All detections are deterministic and reproducible from the raw JSON + DB view. No LLM-in-the-loop judgement was used in the final detection step (though meta.llm_intents itself was produced upstream by claude-opus-4-6 classifying individual SQLs).

---

## 9. Future work markers

- **PD_CommitWithoutPostVerify** (rejected §3.1): if future thinkdepthai prompt changes introduce post-commit verification loops, this could become a discriminative class.
- **PD_SpeculativeCrossServiceLink** (rejected §3.4): a semantic variant might be tractable with LLM-assisted detection. Deferred to Phase 7.5 cross-framework merge.
- **PD6 generalization**: consider promoting a cross-framework variant that is not tied to the specific AVG-ranking default — e.g. "first-ranked latency aggregate without drill-down on top-K winners".
