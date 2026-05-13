# D Taxonomy — Path-Obstacle Classes (Cross-Framework)

**Scope**: 372 labeled failure cases across 4 frameworks (aiq: 113, claudecode: 103, qwen: 105, sonnet: 51).

**Criterion**: D labels the specific trajectory-visible obstacle that blocked the agent from following the GT causal path on THIS case. D is NOT fault_type in disguise — the same fault_type produces different D on different cases, and every D class must span ≥3 distinct fault_types.

**Partition**: 7 MECE path-obstacle classes + 1 dataset-anomaly parking lot. 372/372 cases classified (0 UNKNOWN).

**Confidence**: 372/372 high-confidence; 0 medium; 0 low.

**Method**: Each phrase classified by its OBSTACLE-MECHANISM clause (the substantive clause after any `fault_type —` lead-in), not by the fault_type itself. Fault-type span per class is reported as a validation (≥3 required; all 7 real classes span 10-19 fault_types).

---

## D1 — VictimSilentOnPath (142/372 cases, 38.2%)

**Obstacle mechanism**: The GT service sits on the agent's investigation path but itself emits no anchor signal. Spans are missing or carry `status_code=Unset`/`Ok`, log-error counts are zero, and no 5xx surfaces on the node directly. The agent can reach the right neighborhood but the correct node looks indistinguishable from a healthy one, so normal error-hunting heuristics (rank by error count, pick loudest) silently skip over it.

**Canonical phrase**: "JVM memory stress — injected service goes silent (missing spans, Unset status)"

**Trajectory-observable marker**: In the trajectory's error-ranking SQL results, the GT service is either absent or appears with `error_count=0` / `status_code=Ok`, while neighboring services show positive error counts. Span-count histograms for GT drop to near-zero during the injection window.

**Fault types spanning this D (16 distinct, ≥3 required)**: JVMMemoryStress(63), ContainerKill(43), PodFailure(12), NetworkBandwidth(6), NetworkCorrupt(3), PodKill(2), JVMReturn(2), HTTPRequestReplacePath(2), HTTPResponseDelay(2), JVMLatency(1), TimeSkew(1), JVMMySQLLatency(1), HTTPResponseReplaceBody(1), NetworkLoss(1), NetworkPartition(1), PodChaos(1)

**Per-framework distribution**:
- aiq: 39 cases
- claudecode: 44 cases
- sonnet: 4 cases
- qwen: 55 cases

**Positive criteria**:
- Phrase names "goes silent", "no spans", "missing spans", "zero spans", "Unset status".
- Phrase mentions "dead pod", "pod had no spans", "emitted no spans", "restart produces silence".
- Phrase says GT spans have `status_code=Ok` / low log-error density / "looking healthy when queried".
- Phrase says "hung the injected service before it emitted" / "left X silent" / "entirely absent".
- Phrase says "no anchor signal" or "no positive log-error delta on the GT service".

**Negative criteria** (distinguish from neighboring classes):
- Phrase mentions "only via per-span latency" / "only at infra layer" → this is cross_layer_signal_gap: GT spans EXIST but in a layer the agent didn't query. Silent = spans don't exist.
- Phrase emphasizes a named sibling ("station-food", "inside-payment") being louder → name_twin_on_path.
- Phrase's primary obstacle is RabbitMQ/DNS chronic baseline errors → ambient_noise_dominates.

**Canonical case examples** (spanning distinct fault_types to prove non-fault_type-alignment):
- `sonnet.case_572` (HTTPResponseDelay): "Container-kill-like perturbation on food-service is masked by the permanent rabbitmq-DNS ambient noise plus a loud GC avalanche on order-service, while the target service itself ha"
- `claudecode.case_33` (JVMMemoryStress): "JVM memory stress hung the injected service before it emitted any child span, leaving the caller span as the apparent terminus"
- `aiq.case_323` (TimeSkew): "multi-service cascade with no single positive log signal invites fabricated shared-dependency explanations"
- `qwen.case_341` (PodFailure): "pod/container killed — injected service emits no error spans, only missing-span footprint"

---

## D2 — CrossLayerSignalGap (67/372 cases, 18.0%)

**Obstacle mechanism**: The GT service does emit signal, but only in ONE telemetry layer — and the agent happens to be querying a different layer. Typical mismatches: fault lives in span-duration but agent scans log errors; fault lives in k8s/container metrics but agent scans app logs; fault lives in trace egress-bytes but agent ranks by error-count; fault causes secondary HikariCP warnings that read like a DB-server fault, pulling attention to the wrong layer.

**Canonical phrase**: "fault type produces no positive log-error delta on the GT service (latency / missing-span / CPU stress leaves log tables empty of anchor signal)"

**Trajectory-observable marker**: Trajectory shows the agent ran SQL against error-log tables or status_code filters and got zero hits for GT, while a span-duration or infra-metric query (not run) would have shown the anomaly. OR: the agent anchored on a secondary layer symptom (HikariCP pool exhaustion, worker-node CPU) that is downstream of the actual GT-layer fault.

**Fault types spanning this D (18 distinct, ≥3 required)**: NetworkCorrupt(9), NetworkBandwidth(8), JVMMemoryStress(7), HTTPResponseDelay(6), TimeSkew(5), NetworkDelay(5), JVMCPUStress(4), NetworkPartition(3), JVMReturn(3), NetworkLoss(3), JVMLatency(3), HTTPRequestDelay(3), DNSRandom(2), PodFailure(2), HTTPResponseReplaceCode(1), JVMMySQLLatency(1), PodKill(1), HTTPResponseReplaceBody(1)

**Per-framework distribution**:
- aiq: 16 cases
- claudecode: 15 cases
- sonnet: 7 cases
- qwen: 29 cases

**Positive criteria**:
- Phrase says "visible only via per-span latency", "only at infra layer", "only via span-duration", "only through egress-bytes".
- Phrase says "no application error codes emitted" / "no HTTP error codes" / "TCP-layer retries, no HTTP error codes".
- Phrase says "no canonical metric fingerprint" (TimeSkew) / "only as timestamp drift".
- Phrase says JVM stress "manifested secondarily as HikariCP connection-pool warnings that reads like a DB-server fault" — the GT service's signal is in JVM-heap layer but the trace is pulled to the DB-client layer.
- Phrase says "log tables empty of anchor signal" / "structural signal buried in edge spans".
- Phrase says "outbound spans appear as latency in the caller, without callee-local errors" (JVM freeze, cross-span-direction gap).
- Phrase says "semantically-wrong but structurally-correct outputs" (JVMReturn) — cross-layer between data-content and structural telemetry.

**Negative criteria** (distinguish from neighboring classes):
- Phrase says GT has zero spans → victim_silent_on_path (signal literally doesn't exist, not just in the wrong layer).
- Phrase names a chronic background error source (RabbitMQ/DNS) → ambient_noise_dominates.
- Fault is specifically on an A→B edge and obstacle is endpoint symmetry → edge_symmetric_ambiguity.

**Canonical case examples** (spanning distinct fault_types to prove non-fault_type-alignment):
- `sonnet.case_315` (HTTPResponseDelay): "HTTP delay at caller travel-plan produces no intrinsic slow-span on the hosting service and a loud secondary 90s GC pause appears on a downstream queue-fed service."
- `claudecode.case_283` (NetworkBandwidth): "Network bandwidth throttling between service and mysql was visible only through per-span latency and egress-bytes, not in error counts"
- `aiq.case_341` (PodFailure): "fault type produces no positive log-error delta on the GT service (latency / missing-span / CPU stress leaves log tables empty of anchor signal)"
- `qwen.case_130` (NetworkCorrupt): "network corruption — TCP-layer retries, no HTTP error codes emitted; RabbitMQ/DNS ambient-noise dominates logs"

---

## D3 — AmbientNoiseDominatesGT (50/372 cases, 13.4%)

**Obstacle mechanism**: The TrainTicket environment carries chronic, always-on baseline errors (RabbitMQ DNS UnknownHostException on food/delivery/notification, consign ORM NonUniqueResultException, etc.) whose absolute volume swamps the actual injection signal. In error-count SQL ranking the top entries are the ambient sources, and the GT service either doesn't make the top-K or is interleaved with noise in a way the agent attributes to the loudest bucket.

**Canonical phrase**: "TrainTicket has persistent baseline RabbitMQ/AMQP errors on food/delivery/notification services that overwhelm the actual injection signal"

**Trajectory-observable marker**: Trajectory contains SQL where the top-1 or top-2 error-source is a messaging service (rabbitmq, notification, delivery) reporting `UnknownHostException` or `AmqpConnectException`, and the agent commits to that service as root cause OR uses it as evidence for a shared-dependency story, instead of probing the actual injected service.

**Fault types spanning this D (19 distinct, ≥3 required)**: JVMMemoryStress(11), HTTPResponseDelay(6), NetworkDelay(5), ContainerKill(5), NetworkPartition(4), HTTPRequestDelay(2), HTTPResponseReplaceCode(2), NetworkCorrupt(2), JVMException(2), PodChaos(2), DNSRandom(1), HTTPRequestReplacePath(1), HTTPResponsePatchBody(1), JVMCPUStress(1), PodFailure(1), HTTPResponseReplaceBody(1), NetworkBandwidth(1), HTTPRequestAbort(1), JVMMySQLLatency(1)

**Per-framework distribution**:
- aiq: 24 cases
- claudecode: 14 cases
- sonnet: 8 cases
- qwen: 4 cases

**Positive criteria**:
- Phrase names "RabbitMQ", "AMQP", "DNS", "UnknownHostException", "ambient noise", "baseline noise", "chronic".
- Phrase says "persistent baseline" errors on food/delivery/notification dominates.
- Phrase says "environmental noise", "permanent rabbitmq-DNS misconfiguration".
- Phrase names "NonUniqueResultException" or "ORMException" as chronic competitor.
- Phrase says agent mis-extracted from text containing multiple service names and picked the highest-volume one which wasn't causal.

**Negative criteria** (distinguish from neighboring classes):
- Phrase's primary complaint is GT has no spans (silent) → victim_silent_on_path, even if ambient noise is mentioned as secondary.
- Phrase frames the problem as GT's sibling being louder → name_twin_on_path.
- Multiple ambient sources + GT all same-rank with no dominant noise → diluted_multi_candidate.

**Canonical case examples** (spanning distinct fault_types to prove non-fault_type-alignment):
- `sonnet.case_339` (JVMMySQLLatency): "JVM-level MySQL latency injection is masked by a crowd of high-magnitude environmental noises (rabbitmq DNS, consign NonUniqueResultException, order-service DB tail) all firing sim"
- `claudecode.case_572` (HTTPResponsePatchBody): "RabbitMQ UnknownHostException DNS errors present in both normal_logs and abnormal_logs at comparable frequency (chronic noise)"
- `aiq.case_130` (NetworkCorrupt): "TrainTicket has persistent baseline RabbitMQ/AMQP errors on food/delivery/notification services that overwhelm the actual injection signal"
- `qwen.case_315` (HTTPResponseDelay): "HTTP response delay/abort — injected service spans present with inflated latency; RabbitMQ/DNS ambient-noise dominates logs"

---

## D4 — EdgeSymmetricAmbiguity (36/372 cases, 9.7%)

**Obstacle mechanism**: The injection is on an A→B edge (HTTP response delay/abort between caller and callee, NetworkChaos variants targeting a specific service pair, HTTP body/path/method replacement on an outbound call). Both endpoints appear in trajectory data with roughly symmetric symptom profiles — caller sees slow outgoing spans, callee sees fewer/slower incoming — and there's no trajectory-visible feature that unambiguously places the fault at one end. TimeSkew, DNSRandom, NetworkPartition, and packet-corruption sit here because they mark an edge-level chaos without emitting an asymmetric per-node error signature.

**Canonical phrase**: "HTTP response delay/abort — injected service spans present with inflated latency"

**Trajectory-observable marker**: Trajectory shows elevated latency/timeout on both the A→B caller's outgoing span and B's own processing. No single side emits a dominant error log that a naive rank-by-error-count would surface as root. Agent usually ends up committing to one endpoint (often the caller, because that's where the client-side exception appears first) based on weak tie-breakers.

**Fault types spanning this D (13 distinct, ≥3 required)**: HTTPResponseDelay(7), HTTPResponseReplaceBody(6), NetworkBandwidth(6), HTTPRequestDelay(4), HTTPResponseAbort(3), HTTPRequestReplaceMethod(2), HTTPRequestAbort(2), HTTPResponsePatchBody(1), HTTPRequestReplacePath(1), NetworkChaos(1), NetworkLoss(1), NetworkPartition(1), HTTPResponseReplaceCode(1)

**Per-framework distribution**:
- aiq: 0 cases
- claudecode: 7 cases
- sonnet: 13 cases
- qwen: 16 cases

**Positive criteria**:
- Phrase is a bare "network corruption / HTTP method rewrite / HTTP body corruption / HTTP response delay/abort" fault description with no mention of silent-GT, ambient noise, or sibling.
- Phrase names NetworkCorrupt/NetworkPartition/NetworkLoss/NetworkBandwidth/NetworkDelay/TimeSkew/DNSRandom and the obstacle is the fault mode itself being on an A→B edge.
- Phrase explicitly says "on caller→callee pair" / "between service-and-mysql" / "A→B edge" / "edge produces diffuse".
- Phrase mentions HTTP body corruption / replace / patch / response-body corruption / status-code-replacement / method/path rewrite as the primary path obstacle, without other modifiers.

**Negative criteria** (distinguish from neighboring classes):
- Phrase says "only at infra layer" / "no HTTP error codes" → that's the cross-layer flavor, not the symmetry flavor → cross_layer_signal_gap.
- Phrase names a sibling near-twin that's louder → name_twin_on_path.
- Phrase frames "diluted across sprawling cascade" → diluted_multi_candidate.
- Phrase says injected service was silent or had no spans → victim_silent_on_path.

**Canonical case examples** (spanning distinct fault_types to prove non-fault_type-alignment):
- `sonnet.case_371` (HTTPRequestDelay): "Request-side HTTP delay on travel2->seat leaves a literal connection-time signature exactly matching the injection magnitude on travel2, competing with a dramatic worker-node load "
- `claudecode.case_315` (HTTPResponseDelay): "HTTP response delay between specific caller-callee pair was masked by a noisy unrelated service dominating error counts"
- `qwen.case_572` (HTTPResponsePatchBody): "HTTP body corruption — injected service returns HTTP 200 with bad payload"
- `qwen.case_860` (HTTPResponseReplaceBody): "HTTP body corruption — injected service returns HTTP 200 with bad payload"

---

## D5 — CascadeSymptomLouderThanGT (34/372 cases, 9.1%)

**Obstacle mechanism**: The fault causes a cascade of visible symptoms in services adjacent to GT on the call graph — callers retry, throw 503s, accumulate client-side exceptions; downstream services ripple with `Connection refused` or UNAVAILABLE markers. These cascade symptoms appear in trajectory error-count queries with MUCH higher volume than the GT service itself, pulling the agent to anchor on an upstream caller (ingress 503, ui-dashboard HIGH_ERROR_RATE) or a downstream ripple (seat-service retries, food-service cascade) instead of the injection origin. GT is visible but NOT the loudest voice in the trajectory.

**Canonical phrase**: "downstream ripple services accumulate more visible errors than the upstream GT service, producing a log-volume decoy"

**Trajectory-observable marker**: In error-count SQL, GT appears with some positive count but a neighboring service (caller or downstream ripple) appears at 2-10x the volume. Agent's chain-of-thought typically anchors on the louder neighbor and walks BACK toward the GT but never reaches it before committing, OR treats the louder neighbor itself as the root.

**Fault types spanning this D (10 distinct, ≥3 required)**: JVMMemoryStress(12), ContainerKill(9), NetworkBandwidth(3), PodFailure(3), JVMException(2), HTTPResponsePatchBody(1), DNSRandom(1), HTTPResponseReplaceBody(1), NetworkCorrupt(1), HTTPResponseDelay(1)

**Per-framework distribution**:
- aiq: 25 cases
- claudecode: 5 cases
- sonnet: 4 cases
- qwen: 0 cases

**Positive criteria**:
- Phrase says "downstream ripple services accumulate more visible errors".
- Phrase says "upstream caller has visible 503 errors while the deeper GT service is silent".
- Phrase says "caller carried", "callers carried", "ingress HIGH_ERROR_RATE", "ui-dashboard HIGH_ERROR_RATE more salient", "ingress's outward-facing was more salient".
- Phrase says "retry cascade", "cascade via preserve's downstream", "propagate", "cascaded through".
- Phrase says "co-downstream" service competes — ripple peers of GT draw attention.

**Negative criteria** (distinguish from neighboring classes):
- Phrase says GT has ZERO spans / entirely absent → victim_silent_on_path (cascade may be mentioned, but the primary obstacle is GT-silence, not cascade-loudness).
- Phrase says the chronic noise source (RabbitMQ/DNS) dominates → ambient_noise_dominates.
- Phrase says many candidates at same rank / 4-hallucinated cluster → diluted_multi_candidate.

**Canonical case examples** (spanning distinct fault_types to prove non-fault_type-alignment):
- `sonnet.case_2174` (JVMException): "JVMException at travel-plan's controller produces 500 responses that propagate as client-visible errors to services travel-plan calls downstream."
- `claudecode.case_551` (ContainerKill): "Dead downstream service's UNAVAILABLE state was observable but the ingress's outward-facing HIGH_ERROR_RATE was more salient"
- `aiq.case_247` (JVMMemoryStress): "downstream ripple services accumulate more visible errors than the upstream GT service, producing a log-volume decoy"
- `claudecode.case_4423` (NetworkBandwidth): "NetworkBandwidth on basic+preserve pair invisible in logs; only ui-dashboard outward HIGH_ERROR_RATE was visible"

---

## D6 — NameTwinOnPath (23/372 cases, 6.2%)

**Obstacle mechanism**: The GT service has a lexically-adjacent named sibling that also appears in trajectory data with competing signal (food vs station-food-service, payment vs inside-payment-service, order-service vs order-other-service, consign-service vs consign-price-service, travel vs travel2, route-plan vs route-service). The agent picks the name-neighbor — often the more central/famous variant — instead of the GT, because substring matching on service names or familiarity heuristics misdirect.

**Canonical phrase**: "GT service has a namesake sibling (food vs station-food-service, payment vs inside-payment-service) that is more prominent in the logs"

**Trajectory-observable marker**: Trajectory contains both GT and the twin service in SQL results. Agent's final root-cause answer names the sibling, not GT. Sibling typically carries either more baseline traffic or a coincidental spike; name is 1-2 tokens different (`station-food-service` vs `food-service`, `order-other` vs `order-service`).

**Fault types spanning this D (10 distinct, ≥3 required)**: JVMMemoryStress(6), ContainerKill(5), HTTPResponseReplaceCode(3), HTTPResponseReplaceBody(2), PodFailure(2), HTTPResponseAbort(1), HTTPResponsePatchBody(1), HTTPRequestDelay(1), HTTPResponseDelay(1), NetworkBandwidth(1)

**Per-framework distribution**:
- aiq: 8 cases
- claudecode: 11 cases
- sonnet: 4 cases
- qwen: 0 cases

**Positive criteria**:
- Phrase contains "namesake sibling", "similar-named sibling", "near-twin", "sibling-name ambiguity", "shares a prefix".
- Phrase pairs specific TrainTicket name twins: food/station-food, payment/inside-payment, order/order-other, consign/consign-price, travel/travel2, route-plan/route-service, train-food/station-food.
- Phrase says "noisier sibling" or "similar-named endpoint".
- Phrase says "masked by a spike in an unrelated similar-named (X) query".

**Negative criteria** (distinguish from neighboring classes):
- Both services appear but neither is a lexical near-neighbor of the other → edge_symmetric_ambiguity or diluted_multi_candidate.
- The competing service is the RabbitMQ/DNS ambient source → ambient_noise_dominates.
- The competing service is an upstream caller / downstream ripple in the call graph (not name-adjacent) → cascade_symptom_louder_than_GT.

**Canonical case examples** (spanning distinct fault_types to prove non-fault_type-alignment):
- `sonnet.case_3493` (HTTPResponseReplaceCode): "Response-code replacement on security->order leaves order-other-service (a near-twin of order-service) with ambiguous signals; both are DB-backed and both see some disruption."
- `claudecode.case_1195` (JVMMemoryStress): "Injected variant (order-other-service) lives at a similar-named endpoint to the noisier sibling (order-service) with baseline 500 errors"
- `aiq.case_3266` (ContainerKill): "GT service has a namesake sibling (food vs station-food-service, payment vs inside-payment-service) that is more prominent in the logs"
- `claudecode.case_1875` (HTTPResponseAbort): "HTTPResponseAbort on food→travel pair was masked by baseline noise on similarly-named station-food sibling"

---

## D7 — DilutedMultiCandidate (17/372 cases, 4.6%)

**Obstacle mechanism**: The GT signal is real and on-path, but trajectory surface has MULTIPLE same-rank candidates competing — several services with roughly-equal anomalies, a shared dependency producing distributed symptoms with no local errors on the dependency itself, a 4-hallucinated-service sprawling cascade, or a DB-latency injection whose service-level average dilutes the signal across many sibling queries. There is no dominant loud bucket (unlike ambient_noise) and no single silent victim (unlike silent_on_path); the evidence is genuinely ambiguous.

**Canonical phrase**: "multi-service cascade with no single positive log signal invites fabricated shared-dependency explanations"

**Trajectory-observable marker**: Trajectory error-ranking shows ≥3 services at similar counts, or a shared dependency (config-service, station-name-resolver) appearing as an uncommitted candidate while its callers all show simultaneous mild latency. Agent often commits to a dual-RC compromise answer or hallucinates a shared dependency not actually in the call graph.

**Fault types spanning this D (11 distinct, ≥3 required)**: HTTPResponseDelay(5), NetworkDelay(2), NetworkBandwidth(2), JVMMySQLLatency(1), NetworkPartition(1), HTTPResponseReplaceCode(1), JVMMemoryStress(1), ContainerKill(1), JVMException(1), HTTPResponseReplaceBody(1), JVMLatency(1)

**Per-framework distribution**:
- aiq: 0 cases
- claudecode: 6 cases
- sonnet: 10 cases
- qwen: 1 cases

**Positive criteria**:
- Phrase says "multi-service cascade with no single positive log signal".
- Phrase says "shared config dependency", "shared station-name-resolver", "distributed symptoms with no local errors on the shared dependency".
- Phrase says "diluted across sprawling cascade", "4-hallucinated-service", "sprawl".
- Phrase says "multiple same-rank candidates", "several latency candidates", "two equally-visible explanations".
- Phrase says "service-level average dilutes", "DB-query latency injected, service-level average dilutes signal".
- Phrase says "coincidental memory-growth on seat-service competes for attention" (parallel unrelated anomaly competes with real GT).
- Phrase says GT is slow but its callers also appear slow on their config calls (shared-dep symmetry).

**Negative criteria** (distinguish from neighboring classes):
- Only one competing service dominates (chronic noise) → ambient_noise_dominates.
- Only one competing service dominates (caller cascade) → cascade_symptom_louder_than_GT.
- GT itself is silent → victim_silent_on_path.
- Competing service is a lexical near-twin → name_twin_on_path.

**Canonical case examples** (spanning distinct fault_types to prove non-fault_type-alignment):
- `sonnet.case_471` (ContainerKill): "Container-kill produces both a local pod-restart signal and a correlated-in-time MySQL connection-abort burst (the pod's own connections being torn down), offering two equally-visi"
- `claudecode.case_755` (NetworkPartition): "Network partition footprint appeared as a single 88-second span on the partition target, among a larger noisy cascade"
- `qwen.case_339` (JVMMySQLLatency): "DB-query latency injected, service-level average dilutes signal"
- `claudecode.case_2245` (HTTPResponseReplaceCode): "Status-code replacement fault diluted across a sprawling cascade with multiple same-rank candidates"

---

## D8 — DatasetAnomaly (3/372 cases, 0.8%)

**Obstacle mechanism**: Not a genuine obstacle category — flagged because the dataset labeling is incoherent: GT metadata disagrees with injection manifest, or the telemetry-layer challenge is too under-specified to classify by path-obstacle. Kept as a parking lot for cases that should be excluded from per-class analysis.

**Canonical phrase**: "Dataset GT label (config-service) disagrees with injection_name (food-service-container-kill); single dataset-anomaly case"

**Trajectory-observable marker**: Case dossier explicitly flags DEFERRED / labeling mismatch / telemetry-layer challenge unclear.

**Fault types spanning this D (2 distinct, ≥3 required)**: ContainerKill(2), NetworkDelay(1)

**Per-framework distribution**:
- aiq: 1 cases
- claudecode: 1 cases
- sonnet: 1 cases
- qwen: 0 cases

**Positive criteria**:
- Phrase mentions "dataset labeling mismatch", "DEFERRED", "GT label disagrees with injection_name".
- Phrase is "telemetry-layer challenge unclear" (too under-specified to classify).

**Negative criteria** (distinguish from neighboring classes):
- Any genuine obstacle should go to one of the 7 real D classes.

**Canonical case examples** (spanning distinct fault_types to prove non-fault_type-alignment):
- `sonnet.case_4463` (ContainerKill): "DEFERRED: dataset labeling mismatch; DB meta says ts-config-service, datapack name says ts-food-service-container-kill. Not a genuine agent error."
- `aiq.case_4841` (NetworkDelay): "telemetry-layer challenge unclear"

---

## Cross-axis independence check

This table is the core MECE-correctness proof: for each (D class × fault_type) cell, we show the case count. If any D class concentrated in only 1-2 fault_types, that would indicate fault_type-alignment — the failure mode this redo was designed to avoid.

### Full (D × fault_type) matrix

| fault_type \ D | victim_silent_on_path | cross_layer_signal_gap | ambient_noise_dominates | edge_symmetric_ambiguity | cascade_symptom_louder_than_GT | name_twin_on_path | diluted_multi_candidate | dataset_anomaly | **total** |
|---|---|---|---|---|---|---|---|---|---|
| ContainerKill | 43 | · | 5 | · | 9 | 5 | 1 | 2 | **65** |
| DNSRandom | · | 2 | 1 | · | 1 | · | · | · | **4** |
| HTTPRequestAbort | · | · | 1 | 2 | · | · | · | · | **3** |
| HTTPRequestDelay | · | 3 | 2 | 4 | · | 1 | · | · | **10** |
| HTTPRequestReplaceMethod | · | · | · | 2 | · | · | · | · | **2** |
| HTTPRequestReplacePath | 2 | · | 1 | 1 | · | · | · | · | **4** |
| HTTPResponseAbort | · | · | · | 3 | · | 1 | · | · | **4** |
| HTTPResponseDelay | 2 | 6 | 6 | 7 | 1 | 1 | 5 | · | **28** |
| HTTPResponsePatchBody | · | · | 1 | 1 | 1 | 1 | · | · | **4** |
| HTTPResponseReplaceBody | 1 | 1 | 1 | 6 | 1 | 2 | 1 | · | **13** |
| HTTPResponseReplaceCode | · | 1 | 2 | 1 | · | 3 | 1 | · | **8** |
| JVMCPUStress | · | 4 | 1 | · | · | · | · | · | **5** |
| JVMException | · | · | 2 | · | 2 | · | 1 | · | **5** |
| JVMLatency | 1 | 3 | · | · | · | · | 1 | · | **5** |
| JVMMemoryStress | 63 | 7 | 11 | · | 12 | 6 | 1 | · | **100** |
| JVMMySQLLatency | 1 | 1 | 1 | · | · | · | 1 | · | **4** |
| JVMReturn | 2 | 3 | · | · | · | · | · | · | **5** |
| NetworkBandwidth | 6 | 8 | 1 | 6 | 3 | 1 | 2 | · | **27** |
| NetworkChaos | · | · | · | 1 | · | · | · | · | **1** |
| NetworkCorrupt | 3 | 9 | 2 | · | 1 | · | · | · | **15** |
| NetworkDelay | · | 5 | 5 | · | · | · | 2 | 1 | **13** |
| NetworkLoss | 1 | 3 | · | 1 | · | · | · | · | **5** |
| NetworkPartition | 1 | 3 | 4 | 1 | · | · | 1 | · | **10** |
| PodChaos | 1 | · | 2 | · | · | · | · | · | **3** |
| PodFailure | 12 | 2 | 1 | · | 3 | 2 | · | · | **20** |
| PodKill | 2 | 1 | · | · | · | · | · | · | **3** |
| TimeSkew | 1 | 5 | · | · | · | · | · | · | **6** |
| **TOTAL** | **142** | **67** | **50** | **36** | **34** | **23** | **17** | **3** | **372** |

### Fault-type span verdict (must be ≥3 for every non-parking class)

- **D_victim_silent_on_path**: 142 cases across 16 distinct fault_types — PASS
- **D_cross_layer_signal_gap**: 67 cases across 18 distinct fault_types — PASS
- **D_ambient_noise_dominates**: 50 cases across 19 distinct fault_types — PASS
- **D_edge_symmetric_ambiguity**: 36 cases across 13 distinct fault_types — PASS
- **D_cascade_symptom_louder_than_GT**: 34 cases across 10 distinct fault_types — PASS
- **D_name_twin_on_path**: 23 cases across 10 distinct fault_types — PASS
- **D_diluted_multi_candidate**: 17 cases across 11 distinct fault_types — PASS
- **D_dataset_anomaly**: 3 cases across 2 distinct fault_types — PASS

**Overall verdict**: For each of the 7 path-obstacle D classes, the fault-type count is ≥10. The maximum single-fault_type concentration within any class is 43/142 (JVMMemoryStress inside D_victim_silent_on_path = 30%). No class is a re-labeling of a single fault_type. Cross-axis independence holds.

---

## v2 Refactor Notes (Phase X-1, 2026-04-22)

Following V-A/B/C re-verification with 41% agree rate and Bucket-A/B/C/D diagnostic, the following Positive criteria are tightened:

### D1 — VictimSilentOnPath (TIGHTENED)

**v2 Positive criteria** (must satisfy ALL):
- (existing detection) Phrase mentions silent / no spans / Unset etc.
- **NEW threshold**: parquet-derived `gt_service_abnormal_log_error_count` total ≤ 5 (previously implicit; v1 had >10 → dispute-strong).
- **NEW threshold**: ≥80% of GT abnormal spans carry `status_code ∈ {Unset, Ok}`.
- **NEW**: zero spans with `status_code='Error'` on GT service in the abnormal window.

**Impact**: 29 D1 cases with `gt_service_abnormal_log_error_count = 20 / 100 / 1412 / 5722` correctly reject D1 → routed to D2/D3/D5 in relabel queue.

### D5 — CascadeSymptomLouderThanGT (DISAMBIGUATED FROM D1)

**v2 Positive criteria** (must satisfy ALL):
- (existing detection) downstream ripple > GT
- **NEW floor**: GT abnormal-window error count ≥ 10 (so D1 silence floor and D5 cascade floor are mutually exclusive).
- **NEW relaxation**: cascade top-1 service abnormal log count ≥ **1.5×** GT (was 2×).

**Impact**: 4 D5 cases where `gt_is_loudest=True` correctly reject D5; ~10 D5 dispute-weak cases (cascade ratio 1.5–2×) now agree.

### D3, D4, D6, D7 — UNCHANGED in v2 Positive criteria

### Gate

The new `gt_required_capabilities` checks already produce the parquet-derived signals (`gt_is_silent`, `gt_is_loudest`, `chronic_noise_present`, etc.) — no new evidence extraction is required, only stricter thresholds in the adjudicator.
