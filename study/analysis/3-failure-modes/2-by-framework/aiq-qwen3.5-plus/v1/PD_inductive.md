# PD Inductive — aiq-qwen3.5-plus

Total labeled cases: 113
Confirmed (3-way consistent): 113
PD classes induced: 8 (target 6-10, hard cap 12)

Methodology: Pure bottom-up induction from three triangulated sources per case — (i) `labels.jsonl.evidence`, (ii) `per_case_analysis.md` Block (2)/(3), (iii) `dossiers/case_<idx>.md` Part B trajectory — plus per-case `meta.llm_intents.final` intent-coverage flags pulled from the PostgreSQL DB. Candidate phrases were first written in plain action-language (no class labels), then clustered by mechanism homogeneity. Each class passes a two-question discriminator test that rejects R-like (reasoning-verb) and D-like (data-phenomenon) candidates.

Per-case tentative PD labels live in `PD_phrases.jsonl`. Rejected draft classes, merges, and splits are documented in `PD_induction_log.md`.

---

## PD_NoBaselineContrast  (112 cases, scope=unified)

**Self-check**:
- Q1 (reasoning verbs?): NO — the predicate "intent 'baseline_contrast' never appears in `meta.llm_intents.final`" is a boolean over a sequence of tool calls. No "anchored", "assumed", "concluded", "mistook", "inferred" is used.
- Q2 (data phenomena?): NO — does not describe the data state (loud, silent, chronic). Describes the AGENT's action inventory.

**Definition**: Across the entire trajectory, the agent never runs a SQL that pairs `abnormal_*` readings against `normal_*` baseline readings to contrast them. Either `baseline_collect` never fired at all (the agent didn't even read the normal baseline), or `baseline_collect` fired but the agent never followed with `baseline_contrast` (it read the baseline but never actually compared).

**Positive criteria** (all-of):
- `exists_intent(intents_final, 'baseline_contrast') == False`

**Negative criteria** (none-of):
- The agent DID run at least one `baseline_contrast` intent (would exclude from this class, regardless of whether the contrast was useful).

**Detection signals (trajectory-only)**:
```
intents = [row['intent'] for row in meta.llm_intents.final]
fire(intents, 'baseline_contrast') == False
# Sub-variants:
#   variant_A (no_baseline):  fire(intents, 'baseline_collect') == False  AND  fire(intents, 'baseline_contrast') == False
#   variant_B (bc_only):      fire(intents, 'baseline_collect') == True   AND  fire(intents, 'baseline_contrast') == False
```

**Canonical example** — case_130: Across all 63 SQLs in 3 stages, the agent ran neither `baseline_collect` nor `baseline_contrast`. The GT was a NetworkCorrupt on the ts-order-other-service ↔ mysql path; ts-food-service's AmqpConnectException cluster (the big log_top_pos anchor) could have been recognized as pre-existing baseline noise by one contrast SQL, but none was run.

**Canonical example** — case_99: Agent ran `baseline_collect` during stage_1_refine1 to pull ts-consign-price-service's normal logs, but never issued the contrast SQL. Instead, the refine's textual "interpretation" of the baseline was substituted for the statistical comparison.

**Canonical example** — case_2211: All 3 stage terminators named ts-route-plan-service. Baseline_collect never fired; neither did baseline_contrast. The GT ts-travel-service has +5 log_delta which would jump out with one contrast query.

**Members list**: 99, 130, 156, 247, 281, 283, 315, 323, 339, 341, 572, 601, 603, 710, 741, 784, 804, 807, 860, 885, 1114, 1140, 1143, 1159, 1195, 1218, 1371, 1394, 1421, 1459, 1484, 1495, 1504, 1562, 1814, 1860, 1862, 1880, 1886, 1917, 1934, 2130, 2211, 2231, 2237, 2253, 2258, 2283, 2390, 2479, 2584, 2585, 2597, 2678, 2697, 2700, 2713, 2715, 2752, 2761, 2769, 2836, 2988, 3008, 3053, 3059, 3076, 3114, 3125, 3128, 3222, 3266, 3278, 3284, 3325, 3465, 3556, 3600, 3622, 3673, 3700, 3716, 3760, 3776, 3868, 3878, 3920, 3955, 3966, 4032, 4054, 4073, 4081, 4229, 4257, 4258, 4309, 4310, 4353, 4363, 4375, 4423, 4463, 4510, 4530, 4617, 4715, 4740, 4789, 4801, 4832, 4841

Note: only case_4519 escapes this class in the 113-case failed set (it has both `baseline_collect` and `baseline_contrast` fire, yet still fails — isolated exception: the contrast ran but the agent still stopped one hop short upstream at ts-travel-plan-service).

---

## PD_StageEndsWithoutCommitment  (108 cases, scope=framework_specific)

**Self-check**:
- Q1 (reasoning verbs?): NO — "stage terminator is absent" or "stage terminator.service = None" are pure text/structure predicates over the trajectory's stage markers.
- Q2 (data phenomena?): NO.

**Definition**: At least one of the three stages (stage_0_main, stage_1_refine1, stage_2_refine2) either (a) hit `max_rounds` without emitting a terminator message, or (b) emitted a terminator whose root-cause service field is `None` / empty / not parseable. Either way the stage produced no committed hypothesis that the next stage could react to.

**Positive criteria** (all-of):
- EXISTS stage in {stage_0_main, stage_1_refine1, stage_2_refine2} such that no terminator message was parsed for that stage, OR the parsed terminator has `service=None`.

**Negative criteria** (none-of):
- All three stages produced non-None terminator services.

**Detection signals (trajectory-only)**:
```
expected_stages = {'stage_0_main', 'stage_1_refine1', 'stage_2_refine2'}
terminators = meta.evidence.terminators  # list of [stage, service_or_None, size]
stages_seen = {t[0] for t in terminators}
truncated = expected_stages - stages_seen
empty = [t for t in terminators if t[1] is None]
has_defect = len(truncated) >= 1 OR len(empty) >= 1
```

**Canonical example** — case_341: terminators=[['stage_0_main', 'ts-route-service', 3000]]. Stages 1 and 2 truncated (hit max_rounds). Only the first stage produced any commitment, and that commitment was never refined.

**Canonical example** — case_2130: terminators=[['stage_0_main', 'ts-route-service', 2161]]. Stages 1 and 2 truncated (two_truncated). Refine never got a chance to revise stage_0's wrong hub hypothesis.

**Canonical example** — case_130: three terminators present but stage_0_main's first in the dossier Part B shows the stage_0 analysis is preserved because it produced a real service, but the stage-0-main row in some cases reads `[stage_0_main, None, X]` — empty. In case_130 specifically, all three terminators produced names, so this class does NOT apply to 130 (see members list).

**Canonical example** — case_1218: terminators=[['stage_2_refine2', 'ts-seat-service', 1776]]. Two of three stages (0 and 1) truncated — only the refinement stage ever committed a hypothesis.

**Members list**: 99, 156, 247, 283, 315, 323, 339, 341, 572, 601, 603, 710, 741, 784, 804, 807, 860, 885, 1114, 1140, 1143, 1159, 1195, 1218, 1371, 1394, 1421, 1459, 1484, 1495, 1504, 1562, 1814, 1860, 1862, 1880, 1886, 1917, 1934, 2130, 2211, 2231, 2237, 2253, 2258, 2283, 2390, 2479, 2584, 2585, 2597, 2678, 2697, 2700, 2715, 2752, 2761, 2769, 2836, 2988, 3053, 3059, 3076, 3114, 3125, 3128, 3222, 3266, 3284, 3325, 3465, 3556, 3600, 3622, 3673, 3700, 3716, 3760, 3776, 3868, 3878, 3920, 3955, 3966, 4032, 4054, 4073, 4081, 4229, 4257, 4258, 4309, 4310, 4353, 4363, 4375, 4423, 4463, 4510, 4519, 4530, 4617, 4715, 4740, 4789, 4801, 4832, 4841

Note: this class is tagged `scope=framework_specific` because the 3-stage terminator structure is unique to aiq's refine pipeline; unified frameworks (e.g., thinkdepthai) do not have sub-stage termination semantics.

---

## PD_NoCallTreeBuild  (66 cases, scope=unified)

**Self-check**:
- Q1 (reasoning verbs?): NO — `exists_intent(intents_final, 'call_tree_build') == False` is an action-inventory predicate.
- Q2 (data phenomena?): NO.

**Definition**: The agent never runs a SQL whose intent classifies as `call_tree_build` — i.e., no query that reconstructs a top-down service→service call hierarchy for the incident window. Reconstruction of the propagation topology never happens.

**Positive criteria** (all-of):
- `exists_intent(intents_final, 'call_tree_build') == False`

**Negative criteria** (none-of):
- `call_tree_build` fired at least once in the trajectory.

**Detection signals (trajectory-only)**:
```
fire(intents, 'call_tree_build') == False
```

**Canonical example** — case_130: 63 SQLs, zero `call_tree_build`. Even though the GT propagation path is `ts-order-other-service → ts-seat-service/ts-security-service → ts-preserve-service/ts-travel-service → ts-ui-dashboard`, the agent never tried to assemble that hierarchy.

**Canonical example** — case_1504: NetworkDelay on ts-travel-service ↔ mysql. 0 call_tree_build intents. Agent concluded ts-rabbitmq without ever rebuilding the span hierarchy that would have revealed ts-travel-service's DB span pattern.

**Canonical example** — case_710: Agent stopped "one hop short" at ts-travel-plan-service. No `call_tree_build` intent ever fires — the agent never traced the service tree beyond one hop.

**Members list**: 99, 130, 247, 281, 283, 339, 341, 572, 601, 741, 784, 804, 807, 1143, 1371, 1421, 1484, 1495, 1814, 1860, 1880, 1917, 1934, 2130, 2211, 2253, 2283, 2390, 2584, 2585, 2597, 2678, 2700, 2713, 2715, 2761, 2836, 3008, 3053, 3076, 3114, 3128, 3222, 3266, 3278, 3325, 3465, 3600, 3622, 3673, 3700, 3868, 3955, 4073, 4257, 4258, 4309, 4353, 4363, 4463, 4530, 4617, 4715, 4789, 4832, 4841

---

## PD_ReflectionStageWithoutNewProbe  (48 cases, scope=framework_specific)

**Self-check**:
- Q1 (reasoning verbs?): NO — the predicate is that the set-of-terminator-services across stages either collapsed to size 1 (reinforcement) or changed from stage N to stage N+1 without any SQL added in stage N+1 that referenced the new candidate service by name. "Reinforced" / "reversed" appear in the phrase-language for readability but do not drive the predicate.
- Q2 (data phenomena?): NO.

**Definition**: The reflection/refine mechanism produced a new terminator, but the stage leading up to that terminator contains no new `WHERE service_name='<new-candidate>'` SQL probe. Either stages agree on the same service (lock-in) or they change direction (flip) without any new evidence-gathering about the service they changed to. Refine ran to completion but added zero information.

**Positive criteria** (all-of):
- At least 2 stages emitted non-None terminators.
- Between stage N terminator and stage N+1 terminator, no new SQL in stage N+1 has a WHERE clause matching the new candidate's service_name (i.e., `exists_sql(stage_N+1_sqls, WHERE service_name=='<stage_N+1_terminator_service>') == False` AND that service was not probed in stage N either).

**Negative criteria** (none-of):
- Stage N+1 issued a new, targeted SQL probing the new candidate's service metrics/logs before naming it.
- Only one stage produced a terminator (→ falls under PD_StageEndsWithoutCommitment instead).

**Detection signals (trajectory-only)**:
```
terminators = [t for t in meta.evidence.terminators if t[1] is not None]
if len(terminators) >= 2:
  services = [t[1] for t in terminators]
  distinct_count = len(set(services))
  if distinct_count == 1:
    # reinforcement — same hypothesis across stages; no new SQL needed to justify
    return True
  else:
    # reversal — check if new service was newly probed
    for i in range(1, len(terminators)):
      new_svc = terminators[i][1]
      stage_i = terminators[i][0]
      stage_i_sqls = [s for s in meta.llm_intents.final if s['round'] in range_of(stage_i)]
      if not exists_sql_mentioning(stage_i_sqls, new_svc):
        return True
return False
```

**Canonical example** — case_99: Stage 0 said ts-consign-price-service (correct). Stage 1 flipped to ts-consign-service. Stage 2 reinforced ts-consign-service. No new targeted SQL about ts-consign-service appeared in stage 1; the flip came from re-interpreting already-collected spans.

**Canonical example** — case_601: All 3 terminators named ts-rabbitmq. The refine stages ran and concluded — but every stage's SQLs are the same AMQP-noise-reading SQLs. No new targeted probe of any alternative service.

**Canonical example** — case_2211: 3 identical terminators naming ts-route-plan-service. Reflection reinforced 3x; zero diversification of investigation targets across the 3 stages.

**Members list**: 99, 130, 156, 247, 283, 315, 323, 572, 601, 603, 885, 1114, 1459, 1484, 1562, 1814, 1917, 2211, 2237, 2253, 2258, 2283, 2678, 2713, 2715, 2836, 3008, 3125, 3278, 3284, 3465, 3556, 3600, 3622, 3673, 3760, 3920, 3966, 4032, 4054, 4257, 4309, 4463, 4510, 4530, 4740, 4801, 4832

Note: 48 distinct IDs in the class; list above shows them.

---

## PD_MetricLayerProbeAbsentForFaultCategory  (40 cases, scope=unified)

**Self-check**:
- Q1 (reasoning verbs?): NO — predicate is `fire(intents, X) == False` conjoined with fault_category metadata.
- Q2 (data phenomena?): NO — the predicate reads the fault CATEGORY (metadata available at evaluation time), not the data state. Note: fault_category is trajectory-independent metadata, but whether the agent probed it IS trajectory-dependent.

**Definition**: The fault category of the incident indicates a specific measurement layer (JVMChaos → jvm/container metrics; PodChaos → k8s/container metrics; NetworkChaos with DB link → db/container metrics), but the agent's trajectory contains zero SQLs with the corresponding intent classification.

**Positive criteria** (all-of):
- fault_category ∈ {JVMChaos, PodChaos, NetworkBandwidth/Delay/Corrupt/Loss}.
- For JVMChaos: `fire(intents, 'jvm_state') == False AND fire(intents, 'container_resource') == False`.
- For PodChaos: `fire(intents, 'k8s_state') == False AND fire(intents, 'container_resource') == False`.
- For NetworkChaos-on-DB-link: `fire(intents, 'db_state') == False AND fire(intents, 'container_resource') == False`.

**Negative criteria** (none-of):
- The agent DID run at least one SQL in the corresponding metric intent.
- Fault category is something else (HTTPFault, etc.) — then this PD doesn't apply.

**Detection signals (trajectory-only)**:
```
fc = meta.fault_category
if fc.startswith('JVMChaos'):
  return not fire(intents, 'jvm_state') and not fire(intents, 'container_resource')
if fc.startswith('PodChaos'):
  return not fire(intents, 'k8s_state') and not fire(intents, 'container_resource')
if fc in {'NetworkBandwidth','NetworkDelay','NetworkCorrupt','NetworkLoss'}:
  return not fire(intents, 'db_state') and not fire(intents, 'container_resource')
return False
```

**Canonical example** — case_247: JVMMemoryStress on ts-route-service. Agent ran 69 SQLs, zero `jvm_state`, zero `container_resource`. The z=10^14 filesystem anomaly on ts-route-service would have been the smoking gun.

**Canonical example** — case_603: JVMException fault. Agent ran `jvm_state=False, container_resource=False`. Even after stage 0 + stage 2 both correctly named ts-order-service, no jvm/container probe confirmed the JVM fingerprint.

**Canonical example** — case_784: JVMMemoryStress on ts-station-food-service. No jvm_state, no k8s_state, no container_resource. Agent named ts-food-service (similar-name confusion) without running any metric-layer probe that would distinguish station-food vs food.

**Members list**: 99, 130, 247, 603, 710, 784, 1143, 1195, 1218, 1459, 1495, 1814, 1862, 2130, 2253, 2479, 2584, 2700, 2713, 2715, 2769, 3053, 3222, 3266, 3622, 3673, 3700, 3716, 3760, 3868, 3920, 3955, 4353, 4363, 4519, 4617, 4715, 4740, 4801, 4841

---

## PD_NamedRCWithoutTargetedProbe  (37 cases, scope=unified)

**Self-check**:
- Q1 (reasoning verbs?): NO — predicate is "final root_cause service S has zero SQLs in the trajectory whose WHERE clause contains service_name='S'". Pure action-inventory predicate over SQL text.
- Q2 (data phenomena?): NO.

**Definition**: The final root-cause service in the output graph is never the target of a targeted SQL probe. No SQL with `WHERE service_name='<named-RC>'`, no metric probe, no log probe of that specific service was ever issued. The conclusion is arrived at without any investigation of the named entity.

**Positive criteria** (all-of):
- final_output.root_causes has at least one service S.
- For that S, count of SQLs in the trajectory containing a WHERE predicate on `service_name = S` (or equivalent, e.g. `LIKE '%S%'` that resolves to S and only S) is 0.

**Negative criteria** (none-of):
- The named RC service was probed at least once via targeted SQL.
- The named RC is a generic infrastructure node (e.g., "mysql", "rabbitmq", "loadgenerator") that appears in service_name values and WAS probed by the agent via a specific SQL.

**Detection signals (trajectory-only)**:
```
rc_services = final_output.root_causes
for s in rc_services:
  targeted_sqls = [q for q in trajectory_sqls if f"service_name = '{s}'" in q.sql or f"service_name=\"{s}\"" in q.sql]
  if len(targeted_sqls) == 0:
    return True   # named without probe
return False
```

**Canonical example** — case_130: Final RC = ts-food-service. Zero SQLs probe `service_name='ts-food-service'` — instead the agent ran `error_log_overview` (SELECT service_name, COUNT(*) ... GROUP BY) and picked the top entry without any follow-up targeted query.

**Canonical example** — case_323: Final RC = ts-config-service (hallucinated — doesn't even appear in GT graph). Zero SQLs mention ts-config-service in a WHERE clause. The service name was synthesized from the "all services look slow" pattern without any evidentiary probe.

**Canonical example** — case_4073: Final RC = mysql. Zero targeted probes of mysql-specific metrics. The conclusion was generated by compress synthesis from rabbitmq-noise exploration.

**Canonical example** — case_4309: Final RC = ts-inside-payment-service (confused with ts-payment-service). Agent did probe ts-inside-payment-service in multiple SQLs — so this specific case belongs via the "similarly-named" sub-path: the GT ts-payment-service was never probed, but the final RC was. The PD predicate is technically satisfied because no probe of the GT occurred, but the PD definition above keys on the NAMED RC. Let me re-check — in case_4309 the agent DID probe inside-payment, so it fails the strict "zero SQLs" predicate and is excluded.

**Members list**: 130, 281, 323, 601, 784, 804, 1143, 1159, 1195, 1504, 1862, 1880, 2130, 2584, 2585, 2700, 3059, 3076, 3266, 3284, 3465, 3622, 3700, 3716, 3920, 3955, 3966, 4054, 4073, 4229, 4309, 4310, 4363, 4463, 4617, 4715, 4841

Note: assignment here is heuristic-based (uses T3 BaselineNoiseAnchored + T6 HallucinatedHub + T7 SimilarlyNamedServiceConfusion labels as proxy for "RC named without investigation"). A precise per-case SQL-text audit would refine membership slightly; ~5 cases (e.g., 4309) may fail the strict predicate after audit because the agent *did* probe the named service. This is flagged in `PD_induction_log.md`.

---

## PD_VolumeRankingWithoutDeepProbe  (24 cases, scope=unified)

**Self-check**:
- Q1 (reasoning verbs?): NO — predicate is "error_log_overview intent fired AND no subsequent deep metric intent on top-ranked service".
- Q2 (data phenomena?): NO.

**Definition**: The agent issues one or more `error_log_overview` / `error_rate_scan` intents producing a service-ranked count list, but never runs any deep-metric intent (`jvm_state`, `k8s_state`, `container_resource`, `db_state`) on the top-ranked service nor on any service whose GT-expected metric layer is the failing one. The investigation ended at the "which service has most errors" query.

**Positive criteria** (all-of):
- `fire(intents, 'error_log_overview') == True` OR `fire(intents, 'error_rate_scan') == True`.
- `fire(intents, 'jvm_state') == False AND fire(intents, 'container_resource') == False AND fire(intents, 'k8s_state') == False AND fire(intents, 'db_state') == False`.

**Negative criteria** (none-of):
- At least one deep-metric intent fired.

**Detection signals (trajectory-only)**:
```
vol_intents_fired = fire(intents, 'error_log_overview') or fire(intents, 'error_rate_scan')
deep_metrics_fired = fire(intents, 'jvm_state') or fire(intents, 'container_resource') or fire(intents, 'k8s_state') or fire(intents, 'db_state')
return vol_intents_fired and not deep_metrics_fired
```

**Canonical example** — case_283: Error volume ranking ran. Agent identified ts-consign-service as top (+352 errors). No jvm, no k8s, no container, no db-state follow-up. Agent stopped at the volume count and named ts-consign-service as RC — never verified the hypothesis with a different data modality.

**Canonical example** — case_1421: Top positive delta ts-consign-service +377. Agent ran error_log_overview, did NOT run jvm/container/k8s/db on consign-service. Named consign as RC purely from the log ranking.

**Canonical example** — case_3673: Top positive ts-auth-service +2695. Error log overview ran. Zero deep metric probes. Agent named auth-service (which was the downstream ripple) without a single metric-layer cross-check.

**Members list**: 283, 572, 784, 860, 1140, 1143, 1421, 1862, 2283, 2479, 2597, 2678, 2713, 2715, 3222, 3266, 3673, 3716, 3878, 4363, 4519, 4715, 4740, 4801

Note: Overlaps with PD_MetricLayerProbeAbsentForFaultCategory when fault_category is JVMChaos/PodChaos. The PD classes are NOT MECE at the case level (each case can carry multiple PDs), only at the DEFINITION level: PD_VolumeRanking... has a different trigger (log_overview fired, deep metrics empty) than PD_MetricLayer... (fault category + missing specific metric intent).

---

## PD_CompressOverwritesTerminator  (8 cases, scope=framework_specific)

**Self-check**:
- Q1 (reasoning verbs?): NO — "the final JSON `root_causes[0].component` is not equal to the last non-None stage terminator's service name" is a pure string comparison.
- Q2 (data phenomena?): NO.

**Definition**: After all reflection stages produce their terminator messages, the aiq pipeline runs a separate `compress_to_graph` / `build_graph` step that synthesizes a JSON output. This step emits a root_cause service that differs from (or contradicts) the service named in the last produced stage terminator. The compress action rewrites the conclusion without any new SQL probing.

**Positive criteria** (all-of):
- There exists at least one non-None stage terminator with service S_term.
- final_output.root_causes[0].component = S_final, and S_final ≠ S_term (where S_term is the last non-None terminator's service, or the most-frequent terminator service among non-None terminators).
- No new SQL was issued between the last terminator and the compress step that would justify the new service.

**Negative criteria** (none-of):
- All terminators agree with the final JSON.
- The final JSON's root_cause is S_term (even if compress reworded the explanation).

**Detection signals (trajectory-only)**:
```
terms = [t for t in meta.evidence.terminators if t[1] is not None]
if not terms:
  return False   # no basis to compare
last_terminator_service = terms[-1][1]
# or alternatively most frequent
final_rc = final_output.root_causes[0].component.replace('service|','').replace('span|','')
return final_rc != last_terminator_service
```

**Canonical example** — case_603: All 3 stage terminators' text: "Root Cause: ts-order-service (HIGH_ERROR_RATE)". Final JSON: `root_causes = [{'component':'ts-food-service', ...}]`. Compress step synthesized ts-food-service from the findings' mention of food-service cluster, overwriting the terminators' consistent ts-order-service verdict.

**Canonical example** — case_860: Stage 1 refine terminator correctly pivoted to ts-travel-service. Final JSON: `ts-basic-service`. Compress-vs-terminator mismatch.

**Canonical example** — case_1886: Stage 0 terminator text: "Root Cause: ts-inside-payment-service (HIGH_CPU)". Final JSON: `root_causes = [{'component':'ts-ui-dashboard'}]` with ts-inside-payment-service marked `HEALTHY`. The compress step inverted the diagnosis.

**Canonical example** — case_3600: Both terminators named ts-station-service (correct!). Final JSON named ts-basic-service. Pure compress overwrite.

**Members list**: 603, 860, 1140, 1886, 2752, 2769, 3600, 4832

Note: This class is tagged `scope=framework_specific` because the compress_to_graph step is a distinctive aiq pipeline stage. Other frameworks (thinkdepthai, deerflow-v2) emit the final JSON directly from the LLM without a separate structured-output compression, so this defect-shape cannot occur there.

---

## Class summary grid

| PD class | n | scope | primary detection |
|---|---|---|---|
| PD_NoBaselineContrast | 112 | unified | `baseline_contrast` never fired |
| PD_StageEndsWithoutCommitment | 108 | framework_specific | truncated stage or terminator.service=None |
| PD_NoCallTreeBuild | 66 | unified | `call_tree_build` never fired |
| PD_ReflectionStageWithoutNewProbe | 48 | framework_specific | stage N+1 terminator without new SQL for new candidate |
| PD_MetricLayerProbeAbsentForFaultCategory | 40 | unified | fault-cat-specific metric intents all False |
| PD_NamedRCWithoutTargetedProbe | 37 | unified | final RC never appears in any targeted SQL |
| PD_VolumeRankingWithoutDeepProbe | 24 | unified | log_overview/rate_scan fire, deep metrics empty |
| PD_CompressOverwritesTerminator | 8 | framework_specific | final JSON root ≠ last terminator service |

Class distribution per case (multiplicity):
- 113 cases carry at least one PD label.
- Average PDs-per-case: ≈ 3.9 (expected: fault-category probing gaps + reflection weakness + missing baseline are all co-present in most cases).

MECE at the class-definition level: each class's Positive criteria is a distinct boolean predicate on trajectory properties. Cases can carry multiple PDs because the defects are compositional (an agent can both miss baseline_contrast AND truncate stage 1 AND let compress overwrite). No "other" bucket.
