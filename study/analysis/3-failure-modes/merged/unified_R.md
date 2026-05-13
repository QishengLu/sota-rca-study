# Unified R-axis Taxonomy (Cross-Framework Merge)

**Phase β.R.2 — cross-framework R merge**
**Frameworks merged**: aiq-qwen3.5-plus (113), claudecode-qwen3.5-plus (102†), thinkdepthai-claude-sonnet-4.6 (50†), thinkdepthai-qwen3.5-plus (105). Total = 370 labeled failure cases (2 dataset_anomaly deferred).
**Per-agent R classes ingested**: 29 (8 aiq + 7 claudecode + 7 sonnet + 7 qwen).
**Unified R count**: 5 classes at the merged level. 8 per-agent R classes kept as framework-specific analytical_R (listed in appendix).

†excludes dataset_anomaly deferred cases (claudecode case 4463, sonnet case 4463 equivalents).

Merge principle: mechanism homogeneity, not name similarity. Each per-agent R class maps to **exactly one** unified R OR to the framework-specific appendix. Projection determinism verified (370 = 370).

---

## U1 — LoudnessAnchorOverSilentVictim  (140 cases across 4 frameworks)

**Failure mechanism** (GT+trajectory view): The injected GT service is silent or low-signal during the fault window — dead pod (PodKill/ContainerKill/PodFailure), thread-blocked JVM (JVMMemoryStress/JVMCPUStress/JVMReturn), hung network (NetworkDelay/NetworkBandwidth/NetworkLoss/NetworkPartition/TimeSkew/DNSRandom), or delayed HTTP (HTTPResponseDelay/HTTPRequestDelay). The agent ranks services by abnormal-window error-volume / latency-max / CPU-load / restart-count / connection-wait, and picks the loudest surrogate: typically an upstream caller carrying "Connection refused / 503 / UNAVAILABLE" markers, a same-layer sibling with loud logs, a downstream-leaf with propagated slowness, or the default-visible service (ts-ui-dashboard) when no loud anchor exists. The silent GT is either absent from the output graph or retained as a non-root node. The defect is the absence of a "loudness = chronic/propagated-through" vs "silence = under-investigation" disambiguation step.

**Positive criteria**:
- Predicted RC has positive log-error delta, large abnormal-window latency max, or highest restart count among observed services in the trajectory
- Predicted RC is NOT the GT service; GT service has log_delta ≤ 0 (silent)
- Predicted RC is a caller, sibling, or downstream-leaf of GT in the call graph — OR an off-graph default-visible service when no loud anchor exists
- Trajectory has ≥1 SQL with `GROUP BY service_name ORDER BY error_count/latency/restarts DESC` and final RC matches a top row

**Negative criteria** (when NOT this R):
- Predicted RC has non-positive log_delta AND matches chronic-noise pattern (RabbitMQ/food/delivery/notification) → U2
- Predicted RC is in correct edge region but edge direction inverted → U3
- Predicted RC shares name-substring with GT and both appeared in data → U4
- Agent explicitly reasoned silent service is healthy ("no error = healthy", "Unset = successful") → U5
- Predicted RC is NOT in any trajectory-observed service_name → aiq.R_hub_fabrication (framework-specific)

**Canonical examples**: `aiq.case_247` (JVMMemoryStress on route-service → ui-dashboard picked for top log_delta), `claudecode.case_341` (PodFailure on travel-service → route-plan picked for earliest errors), `sonnet.case_315` (drill-to-slowest-leaf order-service picked while seat was injection target), `qwen.case_1459` (silent callee; caller with visible 503s named RC)

**Per-agent contributors**:
- aiq.R_volume_anchor: 24 cases (21.2% of 113 aiq failures)
- aiq.R_upstream_stop: 16 cases (14.2%)
- aiq.R_silent_fault_blind: 15 cases (13.3%)
- claudecode.R1_SilentOriginShadowedByNoisyNeighbor: 29 cases (28.4% of 102)
- sonnet.R_DownstreamLeafAnchor: 12 cases (24.0% of 50)
- qwen.R_B_DownstreamMessengerBlamed: 32 cases (30.5% of 105)
- qwen.R_D_AmplitudeGreedWrongService: 12 cases (11.4%)

**Trajectory-only trigger** (synthesized, union OR intersection):
- **Robust signals** (≥2 per-agent triggers agree):
  - S1. Trajectory contains ≥1 SQL of shape `SELECT service_name, COUNT(*) FROM abnormal_logs/traces WHERE level='ERROR' GROUP BY service_name ORDER BY count DESC` (or latency/restart equivalents).
  - S2. Final `root_causes[0].component` equals the top-1 or top-2 row of an error/latency ranking query.
  - S3. Agent never issued a metric-probe SQL on that top-ranked service with WHERE filter `name LIKE 'jvm.%' OR 'container.filesystem%' OR 'k8s.pod.memory%' OR 'db.client.%'` (i.e., never asked "is this service itself failing or just loudly erroring downstream?").
  - S4. Trajectory shows `≥1` SQL returning candidate-service data for a zero-error-high-span-count service (i.e., the silent victim was observable) AND final RC != that service.
- **Divergent signals** (framework-specific, OR-composed):
  - aiq-specific: GROUP BY ranking in first 15 rounds (pipeline signature)
  - claudecode-specific: Bash SQL with `level IN ('ERROR','SEVERE')` and reasoning text "most errors" / "earliest" picking
  - sonnet-specific: ≥3 SQL queries with increasing `parent_span_id` join depth, no intrinsic-vs-propagated check
  - qwen-specific: error-count-based ranking + no caller-distribution cross-check
- **Trigger rule**: `S1 AND S2 AND S3` (all frameworks) OR `S4 AND final RC != silent_victim` (silent-victim detection variant).
- Self-check FP rate: 25–35% across frameworks (acceptable).

**Priority Set status**:
- Framework-universal: **PASS** (4/4 frameworks ≥10%; aiq 48.7%, claudecode 28.4%, sonnet 24.0%, qwen 41.9%)
- Model-robust: qwen 41.9% vs sonnet 24.0% → diff 17.9pp; **FAIL** (>5pp)
- Trajectory-only identifiable: **PASS** (all non-analytical_only per-agent contributors)
- **Verdict**: **analytical_only at unified level** (model-robustness fails). Per-model middleware variants may still apply, but a single universal trigger is not safely portable across sonnet and qwen. This is the highest-volume failure mode overall and the primary target for per-model (not cross-model) middleware.

---

## U2 — ChronicAmbientNoiseAnchor  (85 cases across 4 frameworks)

**Failure mechanism** (GT+trajectory view): TrainTicket environment has permanent misconfigurations producing chronic ERROR logs present in both `normal_logs.parquet` and `abnormal_logs.parquet` at comparable rate: (a) `UnknownHostException: ts-rabbitmq` / AmqpConnectException cluster on ts-food-service / ts-delivery-service / ts-notification-service, (b) `ConsignRepository.findByOrderId did not return a unique result` ORM errors, (c) ts-ticket-office-service chronic restarts, (d) peripheral GC pauses. Agent anchors on these high-absolute-count errors without running a baseline-vs-abnormal comparison SQL. Result: commits to ts-rabbitmq (fabricated broker root), ts-food-service, or another chronic-noise carrier, regardless of the actual GT fault class (NetworkDelay on order-service → anchor rabbitmq; JVMCPUStress on basic-service → anchor rabbitmq; HTTPResponsePatch on food→train-food → anchor rabbitmq). The defect is absent "baseline differencing" in the anchor-selection loop.

**Positive criteria**:
- Predicted RC ∈ {ts-rabbitmq, rabbitmq, ts-food-service, ts-delivery-service, ts-notification-service, ts-ticket-office-service, mysql-when-chronic-noise-bound} OR a late-fabricated ancestor in a sparse trajectory
- GT fault class is unrelated to messaging infra AND GT service has zero or negative log_delta
- Trajectory contains SQL hits returning `UnknownHostException` / `AmqpConnectException` / `NonUniqueResultException` / `Get Food Request Failed` substrings
- Trajectory does NOT contain a symmetric SQL joining `normal_logs.parquet` and `abnormal_logs.parquet` on the same error pattern / service

**Negative criteria**:
- Predicted RC has strictly POSITIVE log_delta vs normal baseline → U1 (not U2)
- Predicted RC is the GT service's direct caller with real propagation evidence → U1
- Predicted RC is in correct region with edge inverted → U3

**Canonical examples**: `aiq.case_601` (NetworkDelay on order-service↔mysql → agent names rabbitmq due to food-service AMQP errors dominating count), `claudecode.case_1144` (agent literally states "confirm rabbitmq DNS resolution failure"), `sonnet.case_1144` (rabbitmq as root with no normal_logs check), `qwen.case_283` (NetworkBandwidth on station-service; agent anchors on chronic baseline)

**Per-agent contributors**:
- aiq.R_baseline_unchecked: 17 cases (15.0%)
- claudecode.R2_ChronicInfraNoiseAnchored_RabbitMQDNS: 24 cases (23.5%)
- claudecode.R3_FabricatedAncestorOrBaselineLog: 11 cases (10.8%)
- sonnet.R_ChronicNoiseAsActiveFault: 7 cases (14.0%)
- qwen.R_C_AmbientNoiseAnchor: 26 cases (24.8%)

**Trajectory-only trigger**:
- **Robust signals** (≥2 per-agent triggers agree):
  - S1. Trajectory SQL results contain `UnknownHostException` / `AmqpConnectException` / `Name or service not known` / `NonUniqueResultException` substrings in the `body` / `message` column.
  - S2. Final `root_causes[0].component` ∈ {ts-rabbitmq, rabbitmq, ts-food-service, ts-delivery-service, ts-notification-service, ts-ticket-office-service}.
  - S3. Trajectory contains NO SQL joining/UNION-ing `normal_logs.parquet` with `abnormal_logs.parquet` on the anchor service's error pattern.
  - S4. Claudecode-specific (optional): final graph has rabbitmq node at top timestamp earlier than other nodes.
- **Divergent signals** (OR-composed):
  - aiq-specific: predicted_rcs contains the chronic-noise carrier AND no `SELECT ... FROM normal_logs WHERE service_name='X'` for that X
  - sonnet-specific: absent normal_logs cross-check even after observing DNS/rabbitmq hits
  - qwen-specific: chosen service has `abnormal_count - normal_count ≈ 0`
- **Trigger rule**: `S1 AND S2 AND S3`.
- Self-check FP rate: 10–25% across frameworks — highly specific due to service-name signature.

**Priority Set status**:
- Framework-universal: **PASS** (4/4 frameworks ≥10%; aiq 15.0%, claudecode 34.3% combined, sonnet 14.0%, qwen 24.8%)
- Model-robust: qwen 24.8% vs sonnet 14.0% → diff 10.8pp; **FAIL** (>5pp)
- Trajectory-only identifiable: **PASS** (all non-analytical; FP ≤25%)
- **Verdict**: **analytical_only at unified level**. Mechanism is highly convergent and trigger is reliable, but qwen over-produces this failure vs sonnet by 10.8pp. A middleware rule "forbid RC ∈ {rabbitmq,food,delivery,notification} without baseline-diff SQL" would still be effective per-model; the Priority-Set gate flags the cross-model-gap specifically.

---

## U3 — EdgeDirectionOrRegionEndpointError  (48 cases across 3 frameworks)

**Failure mechanism** (GT+trajectory view): Agent correctly localizes the investigation to the fault region (the A→B call edge carrying HTTPPatch/NetworkBandwidth/NetworkLoss/ContainerKill rules). Final output retains the correct injected service as a non-root node in the graph OR as a child of a fabricated / inverted parent. Variants: (a) outermost-ingress-as-root (ts-ui-dashboard / loadgenerator placed above UNAVAILABLE injected service), (b) sibling-of-callee or co-downstream named root (a third service in the A-B region), (c) restart-window direction inversion (dying pod's in-flight outgoing calls read as "B unavailable" rather than "A crashing"), (d) generic caller-callee reversal where outgoing-call failures are read as downstream-dead. The defect is absent "edge orientation" logic: the agent's output-graph synthesis does not enforce "the unavailable node is the source, not the sink" or "restart signals disambiguate which side of a failing edge died".

**Positive criteria**:
- Final output nodes list contains the injected GT service flagged UNAVAILABLE / HIGH_ERROR_RATE, but NOT as `root_causes[0].component`
- Final output edges list has the GT service as target of a different root
- GT fault class is edge-localized: HTTPPatch, NetworkBandwidth/Loss/Partition, ContainerKill, PodKill with restart signal
- OR: final RC is a third service in the A-B region (sibling-of-callee, co-downstream)

**Negative criteria**:
- Final output does NOT contain GT service as any node → U1 (silent-victim shadowing)
- Chosen RC is chronic-noise carrier (rabbitmq etc.) → U2
- Chosen RC shares name-substring with GT → U4
- Chosen RC is a downstream callee (one hop past GT in correct direction) → framework-specific (qwen.R_E)

**Canonical examples**: `claudecode.case_551` (consign-service correctly marked UNAVAILABLE; ui-dashboard named root), `claudecode.case_1886` (inside-payment UNAVAILABLE as child of ui-dashboard-root), `sonnet.case_675` (correct region but endpoint not in {A,B}), `sonnet.case_471` (pod-kill direction inversion), `qwen.case_860` (caller-callee causal reversal)

**Per-agent contributors**:
- claudecode.R4_OutermostReceiverOrInvertedEdge: 17 cases (16.7%)
- sonnet.R_EdgeDirectionDefault: 19 cases (38.0%)
- sonnet.R_RestartWindowDirectionInversion: 3 cases (6.0%)
- qwen.R_G_CausalInversionOrFabrication: 9 cases (8.6%) — partial fit (qwen.R_G includes broader causal-fabrication sub-patterns beyond edge inversion)

**Trajectory-only trigger**:
- **Robust signals** (≥2 per-agent triggers agree):
  - S1. Final output has a node flagged UNAVAILABLE / HIGH_ERROR_RATE that is NOT `root_causes[0].component`.
  - S2. Final output edges list has that UNAVAILABLE node as `target`, with the named root as `source` (root positioned upstream of the actually-failed service).
  - S3. NO SQL issued a caller-distribution cross-check (`GROUP BY caller_service` / `parent_service_name` against the disputed callee to test caller-selective failure).
- **Divergent signals** (OR-composed):
  - claudecode-specific: round_count ≥ 20 (emerges after long trace investigation)
  - sonnet-specific: ≥2 services mentioned as candidates in same `think_tool` reflection; committed RC queried <30% as often as top-queried service in region
  - sonnet-restart-variant: `k8s.container.restarts > 0` observed for non-committed service
  - qwen-specific: broader causal-inversion phrasings (pod.phase=2 misread; "symptom-as-cause" reasoning)
- **Trigger rule**: `S1 AND S2 AND S3`. Restart-variant add-on: `k8s.container.restarts > 0` for service X AND committed RC != X AND no temporal-window cross-check.
- Self-check FP rate: 20–35%.

**Priority Set status**:
- Framework-universal: **PASS** (2/4 frameworks ≥10%; claudecode 16.7%, sonnet 44.0%. aiq 0%, qwen 8.6% both fail 10% threshold)
- Model-robust: qwen 8.6% vs sonnet 44.0% → diff 35.4pp; **FAIL** (>5pp, hardest failure)
- Trajectory-only identifiable: **PASS** (all non-analytical contributors)
- **Verdict**: **analytical_only at unified level**. Sonnet is 5× more prone to this than qwen. Strongly model-specific. Middleware rule would be sonnet-specific: "if output edges list has an UNAVAILABLE node as target, reject and force root to be the UNAVAILABLE source".

---

## U4 — NameTwinSiblingConfusion  (18 cases across 2 frameworks)

**Failure mechanism** (GT+trajectory view): TrainTicket has many name-twin microservice pairs that differ by prefix/infix/suffix: ts-food-service vs ts-station-food-service vs ts-train-food-service; ts-payment-service vs ts-inside-payment-service; ts-consign-service vs ts-consign-price-service; ts-order-service vs ts-order-other-service; ts-route-service vs ts-route-plan-service. SLO endpoint paths often hint at the true variant (e.g., `/trainfoodservice/...`) but the agent picks the more prominent / shorter-named sibling as RC. Both services are typically visible in the trajectory's observed data. The defect is absence of explicit name-disambiguation logic (no `WHERE service_name IN ('<GT>', '<twin>')` contrast SQL).

**Positive criteria**:
- Predicted RC and GT share a name prefix / suffix / word root (longest common substring ≥6 characters)
- Both predicted and GT services appeared in trajectory-observed data
- SLO endpoint path in prompt hints at the GT variant
- No SQL executed with explicit contrast (`IN` / `LIKE %common%`)

**Negative criteria**:
- Twin is the UPSTREAM caller on the call chain → U1 (upstream_stop variant)
- Twin never appeared in trajectory data → aiq.R_hub_fabrication (framework-specific)
- Injection makes GT silent AND twin has loud errors → primary mechanism is U1; name adjacency secondary

**Canonical examples**: `aiq.case_784` (ts-station-food-service GT; ts-food-service picked), `aiq.case_4310`, `claudecode.case_1195` (JVMMemoryStress on order-other-service; agent picks order-service), `claudecode.case_3033` (station-food picked; GT was train-food), `claudecode.case_3920` (inside-payment picked; GT was payment)

**Per-agent contributors**:
- aiq.R_name_twin_confusion: 8 cases (7.1%) — marked `analytical_only: true` in aiq induction
- claudecode.R5_SimilarNameSiblingConfused: 10 cases (9.8%)

**Trajectory-only trigger**:
- **Robust signals**:
  - S1. Root service name has Jaro-Winkler ≥0.85 similarity to another service name that IS in final graph nodes list OR in SLO endpoint path.
  - S2. Agent's SQL history contains queries filtering on the chosen-root name more often than on the SLO-path-hinted name.
  - S3. No SQL with explicit pair-contrast (`service_name IN (A,B)` or `LIKE '%common_root%'`).
- **Divergent signals**:
  - aiq: longest common substring ≥6 characters heuristic (analytical_only — FP rate ~60%)
  - claudecode: SLO endpoint path disambiguation proxy
- **Trigger rule**: `S1 AND S2 AND S3`.
- Self-check FP rate: claudecode ≤30% (usable), aiq ~60% (analytical_only).

**Priority Set status**:
- Framework-universal: **FAIL** (0/4 frameworks ≥10%; aiq 7.1%, claudecode 9.8%, sonnet 0%, qwen 0% — sonnet and qwen do not split name-twin as its own class, likely absorbed in U3/U1)
- Model-robust: qwen 0% vs sonnet 0% → diff 0pp; **PASS**
- Trajectory-only identifiable: **PARTIAL** (claudecode yes, aiq analytical_only)
- **Verdict**: **analytical_only at unified level** (framework-universal fails). Mechanism is real and targeted (18 cases) but under-represented in thinkdepthai frameworks. Candidate for dataset-level intervention (name-twin pairs could be normalized in preprocessing) rather than per-sample middleware.

---

## U5 — SilenceReadAsHealthOrPaused  (17 cases across 2 frameworks)

**Failure mechanism** (GT+trajectory view): Agent observes a silent / plateaued / error-free signal on the candidate injected-service and explicitly infers healthy or paused state, then moves attribution elsewhere. Variants: (a) "no errors from X → X is working fine" (error-absence → health), (b) "Unset trace status → successful" (unset-status → health), (c) "deployment.available=1 → healthy" (metric-read → health), (d) "metric plateau / idle CPU time → PROCESS_PAUSED" (frozen-metric → pause). Common root-cause fault classes: PodFailure/ContainerKill (dead pod shows no outgoing spans), JVMMemoryStress (hung threads → no visible errors), NetworkCorrupt (corrupt bytes bypass error counters). Distinct from U1 ("loudness beats silence") by being an explicit health inference step in the trajectory — the agent saw the candidate and verbally discarded it. The defect is treating signal-absence as positive evidence of normal state rather than as under-investigation.

**Positive criteria**:
- Trajectory `think_tool` / reasoning block contains explicit phrases: "no errors → healthy", "Unset status → successful", "200 OK → healthy", "deployment.available=1 → healthy", "frozen" / "plateau" / "PROCESS_PAUSED" / "idle"
- That phrase applies to a service in the candidate set, AND that service is GT
- Final RC is a different service (health inference drove the move-on)
- For the paused variant: committed RC state is `PROCESS_PAUSED` OR `UNAVAILABLE` with frozen-metric reasoning

**Negative criteria**:
- Agent never reasoned about the silent service (just ignored it) → U1
- Silence applies to chronic-noise carrier rather than GT → U2
- Silence applies to correctly-retained child node that was flagged UNAVAILABLE → U3 (edge inversion)

**Canonical examples**: `sonnet.case_3236` (container.cpu.time plateau → PROCESS_PAUSED inference on wrong service), `sonnet.case_4433`, `qwen.case_156` (explicit "no errors → healthy" reasoning), `qwen.case_341` (silent travel-service read as healthy), `qwen.case_4258`

**Per-agent contributors**:
- sonnet.R_SilenceMisreadAsPaused: 2 cases (4.0%)
- qwen.R_A_SilentSourceReadAsHealthy: 15 cases (14.3%)

**Trajectory-only trigger**:
- **Robust signals**:
  - S1. `think_tool` or reasoning block contains lexical markers from {"no error", "healthy", "successful", "Unset status", "fine", "frozen", "plateau", "PROCESS_PAUSED", "idle", "deployment.available"} applied to a specific ts-* service name.
  - S2. That service name appeared in prior trajectory SQL results with zero-or-near-zero error rows.
  - S3. Final `root_causes[0].component` != that service.
  - S4. No SQL checked incoming-request-count for the allegedly-healthy/paused service over incident window (to distinguish upstream-starvation from intrinsic-pause).
- **Divergent signals** (OR-composed):
  - sonnet-specific: PROCESS_PAUSED state marker in output + plateau lexical signature
  - qwen-specific: broader health inferences including Unset-status interpretation, deployment metric reads
- **Trigger rule**: `S1 AND S2 AND S3`, tightened by S4 for paused-variant.
- Self-check FP rate: 15% (sonnet), qwen trigger self-estimate not published separately but mechanism overlaps with U1 silent-shadow.

**Priority Set status**:
- Framework-universal: **FAIL** (1/4 frameworks ≥10%; sonnet 4.0%, qwen 14.3%. aiq 0%, claudecode 0%)
- Model-robust: qwen 14.3% vs sonnet 4.0% → diff 10.3pp; **FAIL** (>5pp)
- Trajectory-only identifiable: **PASS**
- **Verdict**: **analytical_only at unified level**. Mechanism is distinctive (lexical signatures are tight) and trigger is cheap, but thinkdepthai-qwen over-produces this failure 3.5× vs sonnet — a strong model effect. Candidate for qwen-specific middleware ("reject RC when silent-candidate reasoning appears without incoming-request-count cross-check").

---

## Framework-specific analytical_R appendix

These per-agent R classes did NOT merge into any unified R (single-framework mechanisms or framework-architectural defects). Kept here for completeness; they are excluded from cross-framework Priority Set analysis.

### aiq-qwen3.5-plus (3 classes, 33 cases)

- **aiq.R_hub_fabrication** (12 cases, 10.6% of aiq failures). Mechanism: agent invents a plausible shared-dependency name (ts-config-service, mysql-hub, ts-route-service-hub) that NEVER appears in any trajectory SQL response. Trigger: `final RC NOT IN S_observed` AND `≥3 services showed anomalies`. Could weakly map to claudecode.R3's (a) sub-pattern, but R3 is dominated by baseline-noise anchoring, so this stays framework-specific. FP rate ~10% — highly discriminative trigger.

- **aiq.R_correct_then_reversed** (13 cases, 11.5%, **F_candidate: true**). Mechanism: aiq's 3-stage pipeline (stage_0_main → stage_1_refine1 → stage_2_refine2) has an early stage correctly name GT; a later stage reverses to a wrong service after querying GT directly and misreading "no HTTP 5xx" as healthy. Framework-architectural — only aiq has multi-stage refinement. Candidate for F catalog (framework-induced reasoning drift).

- **aiq.R_compress_drift** (8 cases, 7.1%, **F_candidate: true**). Mechanism: aiq's final `compress_to_graph` LLM call re-summarizes terminator text and picks a different (ripple) service than the terminator's hypothesis. Framework-architectural — the compress LLM has no structured contract back to the terminator's conclusion. Distinctly aiq-only; F catalog candidate.

### claudecode-qwen3.5-plus (2 classes, 11 cases)

- **claudecode.R6_InfraLayerSkipped_AppLayerAnchored** (7 cases, 6.9%, `analytical_only: true` in claudecode induction). Mechanism: fault at infra layer (mysql bandwidth, network partition, DNS); agent correctly anchors on app-layer cascade and never descends to infra queries. Distinguisher "app-layer anchor was correct" requires GT — analytical_only trigger. No clean cross-framework analog (overlaps weakly with qwen.R_F query-design).

- **claudecode.R7_JVMSymptomMisreadAsDB** (4 cases, 3.9%). Mechanism: JVMMemoryStress → HikariCP pool exhaustion → agent reads as primary mysql/DB fault and places mysql at graph root. Very specific HikariCP + mysql-root signature (FP ~20%). qwen.R_G sub-pattern (a) overlaps but qwen.R_G was mapped to U3. Stays framework-specific.

### thinkdepthai-claude-sonnet-4.6 (2 classes, 7 cases)

- **sonnet.R_OscillationToCompromisePair** (4 cases, 8.0%). Mechanism: agent oscillates across 40+ rounds, names ≥6 distinct services as candidates in reflections, commits to a compromise pair. Sonnet's long-horizon ReAct loop allows this behavior; aiq/claudecode/qwen commit to single RC. Framework-specific behavioral signature.

- **sonnet.R_NarrativeOverMatchedMagnitude** (3 cases, 6.0%, `analytical_only: true` in sonnet induction). Mechanism: multi-hop narrative construction ("X causes contention on Y causes slowness at Z") centered on off-call-tree infrastructure hotspot, even after observing a numerically-matching signal on the actual target. Lexical signature ("contention", "cascade", "bridges") has FP ~45% → analytical_only.

### thinkdepthai-qwen3.5-plus (2 classes, 11 cases)

- **qwen.R_E_PathOvershootPastInjection** (6 cases, 5.7%). Mechanism: traces call chain in correct direction but overshoots injection point by ≥1 hop, landing on a CALLEE of GT. Weakly overlaps with sonnet.R_DownstreamLeafAnchor (placed in U1), but qwen's induction distinguishes R_E from R_D by "chain-following logic dominates" vs "magnitude-greed dominates". Stays framework-specific due to single-framework representation and MECE requirement.

- **qwen.R_F_QueryDesignBuriesSignal** (5 cases, 4.8%). Mechanism: SQL structure filters out the injection anomaly: heterogeneous-unit ORDER BY, service-level AVG(duration) dilution, `status_code='Error'` filter excluding `Unset` spans, mis-scoped latency range. Data exists in parquet but query design buries it. Distinct mechanism not found in other frameworks' inductions; claudecode.R6 is closest but emphasizes missing queries not buried-by-design queries.

### Appendix total: 8 classes, 56 cases. No orphans — all 29 per-agent R classes accounted for (21 unified + 8 framework-specific).

---

## Projection determinism check

Total labeled failure cases (excl. dataset_anomaly): 113 + 102 + 50 + 105 = 370.

Unified R totals: 140 + 85 + 48 + 18 + 17 = 308.
Framework-specific totals: 12 + 13 + 8 + 7 + 4 + 4 + 3 + 6 + 5 = 62. Wait — 12 (aiq.hub) + 13 (aiq.correct_then_reversed) + 8 (aiq.compress) + 7 (cc.R6) + 4 (cc.R7) + 4 (sonnet.Oscillation) + 3 (sonnet.Narrative) + 6 (qwen.R_E) + 5 (qwen.R_F) = 62.

Sum: 308 + 62 = 370. ✓ Every case maps to exactly one destination.

Per-framework audit:
- aiq (113) = U1(55) + U2(17) + U4(8) + aiq.hub(12) + aiq.correct_then_reversed(13) + aiq.compress(8) = 113 ✓
- claudecode (102) = U1(29) + U2(35) + U3(17) + U4(10) + cc.R6(7) + cc.R7(4) = 102 ✓
- sonnet (50) = U1(12) + U2(7) + U3(22) + U5(2) + sonnet.Oscillation(4) + sonnet.Narrative(3) = 50 ✓
- qwen (105) = U1(44) + U2(26) + U3(9) + U5(15) + qwen.R_E(6) + qwen.R_F(5) = 105 ✓

MECE verified.

---

## Priority Set summary

| Unified R | Total | Frameworks ≥10% | Model-robust (|qwen−sonnet|) | Traj-only | Verdict |
|---|---:|---:|---:|:---:|---|
| U1 LoudnessAnchorOverSilentVictim | 140 | 4/4 | 17.9pp **FAIL** | ✓ | analytical_only |
| U2 ChronicAmbientNoiseAnchor | 85 | 4/4 | 10.8pp **FAIL** | ✓ | analytical_only |
| U3 EdgeDirectionOrRegionEndpointError | 48 | 2/4 | 35.4pp **FAIL** | ✓ | analytical_only |
| U4 NameTwinSiblingConfusion | 18 | 0/4 | 0pp pass | partial | analytical_only |
| U5 SilenceReadAsHealthOrPaused | 17 | 1/4 | 10.3pp **FAIL** | ✓ | analytical_only |

**Priority Set members**: **None** under the strict 5pp model-robustness threshold. All unified R classes have significant qwen-vs-sonnet gaps. This is a meaningful finding about model-choice-induced failure-distribution shift: qwen and sonnet produce RCA failures with different mechanism signatures, and a single cross-model middleware rule is not obviously portable.

**Recommended downstream interpretation**:
- Unified R classes with framework-universal ≥10% (U1, U2, U3) are candidates for **per-model** middleware (separate sonnet-variant vs qwen-variant triggers).
- U4 and U5 are analytical / dataset-preprocessing candidates.
- Framework-specific analytical_R classes (esp. aiq.R_correct_then_reversed, aiq.R_compress_drift) are flagged for the F catalog in Phase D.

---

## Merge ambiguities resolved

1. **claudecode.R3 (11 cases) — FabricatedAncestorOrBaselineLog**: disjunctive class with (a) fabricated ancestor + (b) non-rabbitmq baseline noise. Mapped to U2 (ChronicAmbientNoise) because the "baseline-noise" interpretation is dominant in the class definition and the "fabricated ancestor" sub-variant is better served by aiq.R_hub_fabrication (framework-specific analytical_R). Per MECE, no per-agent R can span two unified R.

2. **sonnet.R_DownstreamLeafAnchor (12 cases)**: candidate for both U1 (loudness anchor via downstream-leaf) and U6 ("overshoot past injection"). Mapped to U1 because the mechanism "drill-to-slowest-leaf reflex without intrinsic-vs-propagated check" is a magnitude-greed variant (loudness = slowest leaf wins). U6 collapsed (qwen.R_E alone → framework-specific).

3. **qwen.R_G (9 cases) — CausalInversionOrFabrication**: broad class mixing (a) symptom-as-cause + (b) caller-callee reversal + (c) business-logic confabulation + (d) enum misread + (e) narrative diversion. Mapped to U3 because the edge-inversion / caller-callee-reversal sub-patterns (b, d) dominate the case list and sub-pattern (a) symptom-as-cause partially overlaps with claudecode.R7 (which stayed framework-specific).

4. **qwen.R_A (15 cases) — SilentSourceReadAsHealthy**: candidate for U1 (silent-victim shadowing) and U5 (silence-as-health). Mapped to U5 because the explicit health-inference reasoning is the distinctive mechanism (sonnet.R_SilenceMisreadAsPaused shares this absence-as-positive-evidence pattern).

5. **aiq.R_name_twin_confusion (analytical_only: true in aiq induction)**: retained at unified level in U4 because claudecode.R5 provides a non-analytical trigger. At unified level, U4's trigger is mixed (claudecode-robust + aiq-analytical), and the Priority Set verdict is analytical_only anyway.

6. **Name-twin pattern for sonnet and qwen**: these frameworks do not split name-twin as its own class. Likely absorbed into sonnet.R_EdgeDirectionDefault (which mentions "near-twin sibling" in definition) and qwen.R_B / R_D. No explicit reassignment — the absorbed cases remain counted under their induced class (U1 or U3).

---

## Gate risks

- **Model-robustness gate is catastrophic for all unified R**: every cross-framework cluster fails the 5pp qwen-vs-sonnet diff threshold. This is either (a) a real and important finding about model-dependent failure distributions, or (b) an artifact of different inductive labeling granularity between the two thinkdepthai frameworks. Suggest Phase D cross-check: re-project sonnet cases using qwen's R_B/R_C/R_A labels and vice versa to confirm the gap is mechanism-level not naming-level.

- **claudecode.R3 split ambiguity**: mapping R3 entirely to U2 undercounts U5's hub-fabrication contribution. If Phase D requires finer granularity, R3 could be split 6 baseline-noise (U2) + 5 fabricated-ancestor (new U-hub alongside aiq.hub); this would re-project 5 claudecode cases and possibly promote U-hub to a 2-framework unified class.

- **qwen.R_G mapping to U3 is approximate**: ~4-5 of qwen.R_G's 9 cases are symptom-as-cause (closer to R7) rather than edge-inversion (U3). Phase D dossier re-review of qwen.R_G members recommended if U3 trigger self-check FP rate spikes above 40% on qwen cases.

- **Priority Set is empty** under strict thresholds. If the user intends ≥1 Priority Set member for the middleware catalog, loosening model-robust threshold to 15pp would admit U2 (10.8pp) and U5 (10.3pp). Strict-threshold verdict is as-delivered; loosened verdict flagged here.

---

## v2 Refactor Notes (Phase X-1, 2026-04-22)

After V-A/B/C re-verification (41% agree rate baseline), the U2/U1 thresholds are tightened to reduce mis-attribution.

### U1 — LoudnessAnchorOverSilentVictim (RELAXED Top-K threshold)

**v2 Positive criteria** (changed):
- Predicted RC must be in **top-10** error services (was top-5). Rationale: 84 dispute-weak U1 cases sit at top-6 .. top-9 in error ranking — relaxing to top-10 captures the loudness mechanism without forcing artificial precision.

**Impact**: ~50 of 84 dispute-weak U1 cases promote to agree.

### U2 — ChronicAmbientNoiseAnchor (TIGHTENED + suggested split)

**v2 Positive criteria** (must satisfy ALL):
- (existing detection) chronic_noise_present in parquet (already parquet-derived in current evidence dump — `req["chronic_noise_carriers"]` is computed from `parquet_evidence.chronic_noise_detail`).
- **NEW**: `predicted_rc ∈ chronic_noise_carriers` (previously labeled by lexical TrainTicket name list — now strictly parquet-list).

**Impact**: 70 misaligned U2 cases (RC is not the parquet-chronic carrier on this case) correctly route to U1 or U3 via `suggested_alternative_class`.

**Optional split (deferred to v3)**: `U2a_ChronicCarrierAsRC` (RC is chronic carrier — 15 cases) vs `U2b_ChronicNoiseBuriedGTSignal` (chronic exists but RC is non-chronic; closer to U1) — not implemented in v2 to avoid double labeling work; cases that fail the new v2 U2 are simply re-routed to U1/U3 via misaligned verdict.

### U3, U4, U5 — UNCHANGED in v2 Positive criteria

### Threshold relaxations for dispute-weak

- `U1` top-K ranking: 5 → 10
- `U5` snippet markers: stay strict (lexical narrative analysis is still required)
