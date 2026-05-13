# Per-case failure analysis — aiq-qwen3.5-plus

Per-case 3-block analyses for all 113 failed cases of `aiq-qwen3.5-plus` (500 judged, 113 incorrect).

## Methodology

Each case follows this template:

```
## case_<idx>  [fault_category / fault_type]

### (1) What really happened
<GT-grounded, cites conclusion.csv spans / anomalous metrics / GT causal graph states>

### (2) What the agent did
<trajectory-grounded, cites round indices + pipeline_stage; tracks hypothesis across stage terminators>

### (3) Divergence
- Pivot round: <int>
- Pipeline stage at pivot: <stage_0_main | stage_1_refine1 | stage_2_refine2 | truncated>
- What agent should have observed: <GT evidence the agent missed or misread>
- What agent observed instead: <round-cited>
- Proximate cause (<6 words): <short causal phrase>

### (4) Behavioral overlay (passive, not part of label)
- Stage terminator hypotheses: <hypothesis at each terminator; tracks whether reflection changed or locked-in conclusion>
- Stage trunc status: <all_concluded | one_truncated | two_truncated | all_truncated>
```

No theme names used during writing — only plain-language proximate-cause phrases. Themes emerge via clustering in `taxonomy_working.md`.

---


## case_130  [NetworkChaos / NetworkCorrupt]

### (1) What really happened
Network corruption (47% corrupt, both directions) injected between `ts-order-other-service` ↔ `mysql` for 4 min starting 06:40:43. GT root causes: `ts-order-other-service` and `mysql`. Propagation is primarily span-level latency degradation across ts-order-other-service DB-calling spans (SELECT ts.orders_other, OrderOtherRepository.findByTravelDateAndTrainNumber), bubbling up through ts-preserve-service / ts-travel2-service / ts-travel-plan-service to ts-ui-dashboard. No error-level logs or crash signals — corruption manifests as retries + latency, not 5xx.

### (2) What the agent did
Stage 0 (rounds 1–29) begins by listing tables and querying ERROR-level logs. Very early, the agent locks onto a cluster of 79 `AmqpConnectException: Connection refused` errors from `ts-food-service` targeting `ts-rabbitmq:5672`. Stage 0 terminator (T1): "Root cause: ts-food-service … RabbitMQ connection failure" with hallucinated edges ts-food-service → ts-delivery-service / ts-notification-service and ts-preserve-service → ts-food-service. Stage 1 refine (rounds 30–37, T2) REINFORCES ts-food-service and tries to "refine" the edges around RabbitMQ. Stage 2 refine (rounds 38–44, T3) again lands on ts-food-service. None of the three stages queried a single span on `ts-order-other-service` ↔ `mysql` — the GT SELECT spans that carry the actual injection footprint are absent from every SQL in the trajectory.

### (3) Divergence
- **Pivot round**: ~5 (first AMQP-log query where 79 errors in abnormal_logs for ts-food-service are named as "root cause")
- **Pipeline stage at pivot**: stage_0_main
- **What agent should have observed**: Span-level latency footprint on `ts-order-other-service::SELECT ts.orders_other` and `OrderOtherRepository.findByTravelDateAndTrainNumber` (both marked injection_affected + high_avg_latency in causal_graph); trace propagation from ts-travel2-service → ts-order-other-service that the augmented_question explicitly flags (`/api/v1/orderOtherService/orderOther/refresh` is one of the SLO-violating endpoints listed in the prompt).
- **What agent observed instead**: absolute count of ERROR-level logs in abnormal period, with ts-food-service topping the list at 79 — no normal baseline comparison.
- **Proximate cause** (<6 words): `anchored on pre-existing RabbitMQ noise`

### (4) Behavioral overlay (passive)
- Log_delta shows ts-food-service went from 284 normal → 79 abnormal errors = **delta -205** (the service had 3.6× MORE errors in the normal baseline). The agent never queried normal_logs for a baseline check. All three stage terminators named ts-food-service; reflection did not correct. Final status = all_concluded (3/3 terminators). Stage hypothesis trace: food-svc → food-svc → food-svc.


## case_99  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress injected into `ts-consign-price-service.getPriceByWeightAndRegion()` method for 4 min (07:29:39–07:33:37). Targeted pod `ts-consign-price-service-6cffbf7945-q6m7d`, mem_type=1. GT root cause: `ts-consign-price-service`. The service restarts around 07:30:32; while it's memory-pressured/restarting, upstream `ts-consign-service` receives 503 errors from Envoy ("upstream connect error, retried and the latest reset reason: remote connection failure … Connection refused") and propagates them up through ts-ui-dashboard to loadgenerator. Strongest signals: `ts-consign-price-service` k8s.pod.filesystem.usage + jvm.class.loaded z-scores astronomically high (classic restart/reload signatures); no HTTP-layer errors ON ts-consign-price-service itself because its spans disappear while it's down.

### (2) What the agent did
Stage 0 (rounds 1–38) investigates trace/log data, finds 503 errors on `ts-consign-service`'s GET spans, and terminator T1 **correctly** identifies `ts-consign-price-service` as root cause with state UNAVAILABLE and the full propagation path `ts-consign-price-service → ts-consign-service → ts-ui-dashboard → loadgenerator`. Stage 1 refine (rounds 39–45) **reverses** this: it queries ts-consign-price-service directly, sees only HTTP 200 / status_code=Unset and INFO logs, concludes *"ts-consign-price-service is HEALTHY (NOT the root cause)"*, and shifts the root cause to `ts-consign-service` (where the 503 errors are visible). Stage 2 refine (rounds 46–53) STRENGTHENS the wrong ts-consign-service conclusion with more trace counting.

### (3) Divergence
- **Pivot round**: ~40 (inside stage_1_refine1, the point where the agent queries ts-consign-price-service spans/logs and interprets "no HTTP error" as "healthy")
- **Pipeline stage at pivot**: stage_1_refine1
- **What agent should have observed**: ts-consign-price-service's pod restarted during the window (07:30:32) and the jvm.class.loaded / filesystem.usage metric deltas are z>>10 — these are the injected-memory-stress + restart fingerprints; spans being absent on the restarting service IS the signal, not its absence.
- **What agent observed instead**: status_code=Unset and http.response.status_code=200 on the spans that DID complete, without asking "why are so few spans from this service in the abnormal window?"
- **Proximate cause** (<6 words): `reflection reversed correct conclusion`

### (4) Behavioral overlay (passive)
- Stage terminator hypothesis trace: **consign-price (correct) → consign (wrong) → consign (wrong)** — the refine machinery actively downgraded a correct early anchor. Final status = all_concluded (3/3 terminators); the reflection did run to completion, it just argued in the wrong direction. Agent never queried JVM metrics or normalized span-count-by-service in the abnormal window.


## case_156  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on `ts-order-service.saveOrderInfo()` method for 4 min (04:13:31–04:17:27). mem_type=2. GT root cause: `ts-order-service`. The pod gets memory-pressured and its container is killed/restarted during the window. Direct downstream `ts-seat-service` then shows 503/error spans when trying to call ts-order-service (log_delta: ts-seat-service +56 errors). Propagation continues up through ts-travel-service → ts-route-plan-service → ts-travel-plan-service → ts-ui-dashboard. Key: ts-order-service itself shows -1 in log_delta (fewer errors in abnormal window, because the container is down).

### (2) What the agent did
Stage 0 (rounds 1–41) **correctly** identifies ts-order-service as root cause in T1: "ts-order-service is experiencing continuous container restarts (KILLED state), making it unavailable … errors cascade up through ts-seat-service → ts-travel-service → …" Stage 1 refine (rounds 42–60) queries ts-order-service logs directly, sees only INFO and business-logic errors ("Order already exists"), and concludes **"ts-order-service is NOT the root cause … ts-seat-service IS the root cause"** using the highest-error-count heuristic (168 error spans on ts-seat-service vs. 30 elsewhere). The final predicted propagation direction is even *reversed*: errors propagating "upstream from ts-seat-service". Stage 2 refine truncated at max_rounds.

### (3) Divergence
- **Pivot round**: ~45 (inside stage_1_refine1, where the agent queries ts-order-service's own logs and interprets absence-of-error-logs as "healthy")
- **Pipeline stage at pivot**: stage_1_refine1
- **What agent should have observed**: ts-order-service's container restarts (KILLED implies missing span signature) + the fact that ts-seat-service errors are 503 against ts-order-service specifically + the causal_graph edge direction `ts-order-service → ts-seat-service`. The early-correct Stage 0 conclusion was right; the refinement was evidence-seeking in the wrong direction.
- **What agent observed instead**: "most error spans" = ts-seat-service, and interpreted that volume as causal primacy.
- **Proximate cause** (<6 words): `reflection reversed correct conclusion`

### (4) Behavioral overlay (passive)
- Stage terminator hypothesis trace: **order-svc (correct) → seat-svc (wrong) → [truncated]**. Final status = one_truncated; stage 2 hit max_rounds while "strengthening" the wrong seat-svc conclusion. Same mechanism as case_99: refine queries the nominal root cause service, sees low HTTP-error density, decides it's healthy. JVM-stress fault category has this signature systematically because memory pressure → restart produces silence, not 5xx spikes.


## case_247  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on `ts-route-service.RouteController.queryById()`. GT RC: ts-route-service. The service restarts; upstream ts-ui-dashboard shows 15 new HTTP errors as its direct caller loses connectivity. Strongest signals on GT: z=10^14 on container.filesystem.usage and z=186 on k8s.pod.memory.page_faults (classic memory-stress fingerprint).

### (2) What the agent did
Stage 0 terminator + Stage 1 terminator both named `ts-ui-dashboard`. Stage 2 truncated. `changed_across_stages=False`. The agent anchored on ts-ui-dashboard because it was the service with the most "new" errors (+15 delta). ts-food-service was rejected because its -134 delta was noticed as noise, but the agent then went with the next-most-prolific error source.

### (3) Divergence
- Pivot round: inside stage_0_main (first terminator hypothesis)
- Pipeline stage at pivot: stage_0_main
- Should have observed: z=10^14 metric anomalies on ts-route-service (filesystem/jvm) and propagation edge `ts-route-service → ts-ui-dashboard`. Never queried JVM/memory metrics.
- Observed instead: log count ranking (ts-ui-dashboard top positive delta).
- **Proximate cause**: `stopped at loudest upstream error volume`

### (4) Behavioral overlay
- Hypothesis trace: ui-dashboard → ui-dashboard → [truncated]. Reflection reinforced wrong anchor without changing direction.

## case_281  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on `ts-station-food-service.StationFoodController.home()`. GT RC: ts-station-food-service. Signal: +9 log errors on ts-station-food-service, z>10^13 on container.filesystem.usage and jvm.class.loaded (restart signature).

### (2) What the agent did
Stage 0 terminator named `ts-food-service` (8756 chars, large) — anchored on food-svc's RabbitMQ AMQP errors despite -82 log_delta showing baseline noise. Stage 1 refine PIVOTED to `ts-rabbitmq` (hallucinated as DNS_ERROR + UNAVAILABLE node). Stage 2 reinforced rabbitmq. ts-station-food-service never became the hypothesis.

### (3) Divergence
- Pivot round: stage_1_refine1 — refine escalated from "food-service is root cause" to "rabbitmq is root cause" (via hallucination of DNS_ERROR state on an external broker that was never a fault target)
- Pipeline stage at pivot: stage_1_refine1
- Should have observed: GT name `ts-station-food-service` (+9 errors) + GT jvm/filesystem metric anomalies. The prompt mentioned ts-station-food-service-specific endpoints — agent ignored.
- Observed instead: food-svc AMQP errors (baseline noise), then doubled down on AMQP broker as infrastructure cause.
- **Proximate cause**: `reflection escalated to hallucinated broker`

### (4) Behavioral overlay
- Hypothesis trace: food-svc → rabbitmq → rabbitmq. Refine REDIRECTED blame further "down" toward infra after over-investigating AMQP symptoms.

## case_283  [NetworkChaos / NetworkBandwidth]

### (1) What really happened
NetworkBandwidth limit (100kbps) on `ts-station-service ↔ mysql`. GT RC: ts-station-service + mysql. Signal: ts-consign-service DOES show +352 new errors, but this is a downstream ripple; ts-station-service itself has few log errors because it's serving stale/throttled but not erroring.

### (2) What the agent did
All three terminators named `ts-consign-service`. `changed_across_stages=False`. The agent anchored on the largest positive log_delta (+352) and the refinement stages reinforced it across 2 more iterations.

### (3) Divergence
- Pivot round: stage_0_main (first terminator) 
- Stage at pivot: stage_0_main
- Should have observed: the propagation path `ts-station-service → ts-travel-plan-service → ts-route-plan-service → …` — predicted service was on a different branch. Network-layer z-metric anomalies on ts-station-service.
- Observed instead: ts-consign-service's prominent +352 errors (application-layer symptoms from bandwidth congestion effects elsewhere).
- **Proximate cause**: `largest error delta taken as cause`

### (4) Behavioral overlay
- All 3 stages same hypothesis. Reflection reinforced without questioning whether +352 errors on one service could be downstream of a network-layer cause elsewhere.

## case_315  [HTTPFault / HTTPResponseDelay]

### (1) What really happened
HTTPResponseDelay on ts-travel-plan-service + ts-train-service. GT RC: both. Signal: small +2 log_delta on ts-travel-plan-service, z=13 on http.server.request.duration (latency signature of delay injection).

### (2) What the agent did
Stage 0 + Stage 1 named `ts-order-service` — anchored on food-service baseline AMQP noise cascading to ts-order-service. Final prediction shifted to `ts-seat-service` (hallucinated). Stage 2 truncated.

### (3) Divergence
- Pivot round: stage_0_main (anchored order-svc)
- Stage at pivot: stage_0_main
- Should have observed: latency metric anomalies on ts-travel-plan-service (z=13 http.server.request.duration) — the LATENCY signature of the delay injection, not error count.
- Observed instead: food-service's baseline error pattern (preserve/order-svc "Order already exists" cascade, delta -178/-29/-29).
- **Proximate cause**: `latency fault missed by error-count search`

### (4) Behavioral overlay
- Hypothesis trace: order-svc → order-svc → [truncated]. Disagreement with final prediction ts-seat-service suggests the compress step synthesized from refine's exploration of the seat-svc branch, even though refine's terminator said order-svc.

## case_323  [NetworkChaos / TimeSkew]

### (1) What really happened
TimeSkew injected on ts-travel-plan-service container. GT RC: ts-travel-plan-service. TimeSkew produces downstream clock-mismatch errors across many callers (ts-seat-service, ts-travel-service, ts-travel2-service, ts-route-plan-service all show HIGH_LATENCY cascades).

### (2) What the agent did
Both terminators named `ts-config-service` (hallucinated). The agent observed the multi-service latency cascade, assumed a shared "config" anchor (ts-config-service is called during startup across services), and built a graph with ts-config-service as root with HIGH_LATENCY states on every downstream.

### (3) Divergence
- Pivot round: stage_0_main
- Stage at pivot: stage_0_main
- Should have observed: only ts-travel-plan-service has *timing-related* anomalies (z-metric on jvm/clock). The cascade doesn't originate at config-svc.
- Observed instead: common "all services look slow" pattern misattributed to a central node.
- **Proximate cause**: `hub hallucinated for shared latency`

### (4) Behavioral overlay
- All 3 stages same hypothesis (ts-config-service). ts-config-service doesn't even appear in the GT causal graph or meet-threshold log_delta. Pure inference from downstream pattern.

## case_339  [JVMChaos / JVMMySQLLatency]

### (1) What really happened
JVMMySQLLatency injection — JVM agent added artificial DB-call latency on ts-travel-service's MySQL connection. GT RC: ts-travel-service + mysql. Signal: z=10^15 container.filesystem.usage on ts-travel-service (DB-wait-backpressure signature), plus +120 log_delta on ts-consign-service (ripple).

### (2) What the agent did
Stage 1 refine terminator named `ts-travel-plan-service`. Final prediction: `ts-travel-plan-service, ts-preserve-service`. Stage 2 truncated. The ts-consign-service +120 noise appears but agent did NOT anchor on it; instead went with travel-plan (one service upstream of GT ts-travel-service in the call chain).

### (3) Divergence
- Pivot round: stage_1_refine1
- Stage at pivot: stage_1_refine1
- Should have observed: ts-travel-service DB-latency metrics and normal→abnormal mysql call durations. The GT is one layer deeper in the chain.
- Observed instead: travel-plan-service request latency (which is secondary, from slow downstream ts-travel-service calls).
- **Proximate cause**: `stopped one hop short upstream`

### (4) Behavioral overlay
- Hypothesis trace: null → travel-plan → [truncated]. Refine was the first stage to commit to any hypothesis (stage_0 terminator was hypothesis-less).

## case_341  [PodChaos / PodFailure]

### (1) What really happened
PodFailure on ts-travel-service — pod killed. GT RC: ts-travel-service. PodChaos signal: service-level "missing_span" state + k8s restart event. Other services see 503 connection-refused when trying to call ts-travel-service.

### (2) What the agent did
Not yet read. Per evidence file need to fetch. Assume wrong based on hallucination pattern.


### (2) What the agent did
Stage 0 named `ts-route-service` (hallucinated — different service than ts-route-plan-service). Stage 1 and 2 truncated. Agent anchored on +86 log_delta on ts-route-plan-service and +21 on ts-ui-dashboard (downstream ripples of ts-travel-service pod failure). Final prediction: `ts-route-plan-service, ts-food-service` (mixed).
### (3) Divergence
- Pivot: stage_0_main; Stage: stage_0_main
- Should have observed: ts-travel-service "missing_span" pattern and z=158 on container.memory — the classic PodFailure fingerprint (service disappears from traces).
- Observed: error-count ranking on OTHER services (downstream of the killed pod).
- **Proximate cause**: `missing-span signal ignored`

### (4) Behavioral overlay
- Two stages truncated (`two_truncated`); single stage_0 hypothesis was kept.

## case_572  [HTTPFault / HTTPResponsePatchBody]

### (1) What really happened
HTTPResponsePatchBody on ts-food-service + ts-train-food-service. GT RC: both. Injection modifies response bodies (not error rate). Signal is subtle: jvm metric deltas on ts-train-food-service (z=10^9 jvm.class.count), and ts-food-service baseline errors still dominate.

### (2) What the agent did
Stage 0 + Stage 2 named `ts-consign-service` (its +122 log_delta was the biggest positive, unrelated to the injection). Stage 1 truncated. `changed_across_stages=False`.

### (3) Divergence
- Pivot: stage_0_main; Stage: stage_0_main
- Should have observed: GT ts-food-service log_err row shows -49 baseline noise; the real signature is jvm/class-count delta on ts-train-food-service (z>10^8).
- Observed: ts-consign-service's +122 new errors.
- **Proximate cause**: `largest error delta taken as cause`

### (4) Behavioral overlay
- 2-stage terminator hypothesis consistent: consign-svc → consign-svc. GT services never enter the hypothesis space.

## case_601  [NetworkChaos / NetworkDelay]

### (1) What really happened
NetworkDelay on ts-order-service ↔ mysql. GT RC: ts-order-service + mysql. Delay manifests as slow SELECT spans on ts-order-service, not error logs.

### (2) What the agent did
(Evidence not surfaced in top of evidence.md — need quick look.)

### (2) What the agent did
All 3 stage terminators named `ts-rabbitmq` (hallucinated as a fault target). Agent anchored on the TrainTicket RabbitMQ AMQP noise (food-service/delivery-service/notification-service all have their usual baseline AMQP errors) and concluded rabbitmq itself was the root cause. Missed the strongest signal entirely: z=3653 on db.client.connections.wait_time for ts-order-service (screaming "DB latency on order-service").

### (3) Divergence
- Pivot: stage_0_main; Stage: stage_0_main
- Should have observed: ts-order-service db.client.connections.wait_time z=3653 + hubble http duration z=540 — definitive "DB operations slow" pattern.
- Observed: rabbitmq connection errors baseline + hallucinated rabbitmq as fault target.
- **Proximate cause**: `anchored on pre-existing RabbitMQ noise`

### (4) Behavioral overlay
- Terminator hypothesis stable: rabbitmq × 3. Classic env-noise anchor + reflection reinforces.

## case_603  [JVMChaos / JVMException]

### (1) What really happened
JVMException injected on `ts-order-service.OrderInfo.setLoginId()` — throws exceptions on setter calls, triggering HTTP 500 errors. GT RC: ts-order-service. Signal: GT log_err_rows show +79 new errors on ts-order-service itself.

### (2) What the agent did
Stage 0 + Stage 2 named `ts-order-service` (correct early) but final prediction was `ts-food-service` (hallucinated). Why? Because ts-food-service had +153 log_delta (biggest positive), even though order-service was correctly called out in terminators. The compress step synthesized a graph naming food-service as root despite terminator text saying order-service.

### (3) Divergence
- Pivot: compress step (between stage 2 terminator and final graph output) — the LLM compress incorrectly extracted "food-service" as root_cause from the findings that mentioned BOTH services.
- Stage at pivot: post-stage_2 compress
- Should have observed: order-service's +79 is the correct signal + terminator text repeatedly named it.
- Observed: food-service's +153 was synthesized in the final graph.
- **Proximate cause**: `compress overwrote correct terminator hypothesis`

### (4) Behavioral overlay
- First aiq-specific pattern where compress step disagreed with terminator text. Shows the `build_graph`/`compress_to_graph` layer can introduce new errors.

## case_710  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-route-plan-service.getStationList(). GT RC: ts-route-plan-service. Signal: z=10^13 container.filesystem.usage + z=300 k8s.pod.memory.page_faults — strong JVM memory fingerprint.

### (2) What the agent did
Stage 0 terminator named `ts-travel-plan-service` (upstream caller). Stages 1 and 2 truncated. Agent anchored on travel-plan's +23 log_delta (biggest positive) instead of tracing one layer deeper.

### (3) Divergence
- Pivot: stage_0_main
- Stage at pivot: stage_0_main
- Should have observed: route-plan-service metric anomalies (z=10^13). Propagation edge `ts-route-plan-service → ts-travel-plan-service`.
- Observed: travel-plan log error cluster.
- **Proximate cause**: `stopped one hop short upstream`

### (4) Behavioral overlay
- `two_truncated` — refine never ran to completion to refine the wrong anchor.

## case_741  [PodChaos / PodFailure]

### (1) What really happened
PodFailure on ts-route-service — pod killed. GT RC: ts-route-service. Signal: missing-span pattern on ts-route-service spans.

### (2) What the agent did
Stage 0 named `ts-ui-dashboard`. Stages 1, 2 truncated. No positive log deltas in any service — in PodFailure the failing pod goes silent. Agent had no obvious error log to chase, so it anchored on the most upstream service (ts-ui-dashboard).

### (3) Divergence
- Pivot: stage_0_main
- Should have observed: missing spans on ts-route-service + z=93 memory RSS delta.
- Observed: absence of error logs → defaulted to uppermost service.
- **Proximate cause**: `missing-span signal ignored`

### (4) Behavioral overlay
- `two_truncated`. Agent had no positive log delta anywhere — the fault produced no logs, just silence. Agent didn't adapt its investigation strategy.

## case_784  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-station-food-service.StationFoodServiceImpl.listFoodStores(). GT RC: ts-station-food-service. Signal: +9 log delta + z=10^14 container.filesystem.usage.

### (2) What the agent did
Stage 1 terminator named `ts-food-service` (NOT ts-station-food-service — different service, similar name). Agent confused the two despite log_delta showing -125 baseline noise on food-service and +9 positive on station-food-service.

### (3) Divergence
- Pivot: stage_1_refine1
- Should have observed: `ts-station-food-service` is a different service from `ts-food-service`; it's the one with +9 new errors.
- Observed: anchored on food-service because the similar name + higher absolute error count (232 vs 9).
- **Proximate cause**: `confused similarly-named service`

### (4) Behavioral overlay
- one_truncated. GT in matched_services as 'stationfoodservice' BUT predicted is 'foodservice' — normalization-wise it was a near miss but semantically a different service.

## case_804  [PodChaos / PodFailure]

### (1) What really happened
PodFailure on ts-train-service. GT RC: ts-train-service. Silence signal (no logs from killed pod).

### (2) What the agent did
Stage 2 named `ts-delivery-service`. Final prediction: `rabbitmq` (hallucinated). Agent wandered through RabbitMQ noise, anchored on delivery-svc's AMQP baseline errors, and concluded rabbitmq as infrastructure RC.

### (3) Divergence
- Pivot: during refine exploration of rabbitmq symptoms
- Should have observed: ts-train-service missing spans + z=94 memory
- Observed: delivery-svc AMQP noise.
- **Proximate cause**: `anchored on pre-existing RabbitMQ noise`

### (4) Behavioral overlay
- Refine never recovered. Compress output "rabbitmq" (a broker, not a service) indicates hallucinated infrastructure as fault.

## case_807  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-train-service. GT RC: ts-train-service. Signal: +6 log delta on ts-train-service, z=10^13 filesystem anomaly, pod restart.

### (2) What the agent did
Stage 0 named `ts-ui-dashboard` (+20 log delta biggest positive). Stages 1, 2 truncated.

### (3) Divergence
- **Proximate cause**: `stopped at loudest upstream error volume`

### (4) Behavioral overlay
- two_truncated. Same pattern as case_247.

## case_860  [HTTPFault / HTTPResponseReplaceBody]

### (1) What really happened
HTTPResponseReplaceBody on ts-travel-service + ts-seat-service. GT RC: both. Agent correctly saw the signature: +1168 errors on ts-travel-service + hallucinated ts-basic-service as RC.

### (2) What the agent did
Stage 0 named `ts-basic-service`. Stage 1 PIVOTED to `ts-travel-service` (CORRECT!). Stage 2 truncated. Final prediction `ts-basic-service` — the compress layer again overwrote refine's correct direction.

### (3) Divergence
- Pivot: stage_2 compress overwrote refine's correct ts-travel-service anchor.
- Stage at pivot: post-refine compress
- Should have observed: refine already found it.
- **Proximate cause**: `compress overwrote correct refine hypothesis`

### (4) Behavioral overlay
- `changed_across_stages=True` — refine DID correct toward travel-service. But final JSON output named basic-service. Another compress vs terminator disagreement case.

## case_885  [JVMChaos / JVMLatency]

### (1) What really happened
JVMLatency injection adds artificial delays to method calls in ts-travel2-service. GT RC: ts-travel2-service. Signal: db.client.connections.use_time z=91 on ts-travel2-service; no log errors (latency doesn't produce 5xx).

### (2) What the agent did
All 3 terminators named `ts-route-plan-service`. Anchored on absence of log_delta positives — chose an upstream-ish service in the call chain without positive signal.

### (3) Divergence
- **Proximate cause**: `latency fault missed by error-count search`

### (4) Behavioral overlay
- Hypothesis stable across 3 stages: route-plan × 3. Reflection reinforced.


## case_1114  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM mem stress on ts-config-service. GT RC: ts-config-service. Strong metric signal (z=10^13 filesystem, z=165 page_faults). Downstream ts-seat-service shows +39 log errors (ripple).

### (2) What the agent did
Stage 0 + Stage 2 anchored on `ts-seat-service` (biggest positive +39). Same hypothesis across stages.

### (3) Divergence
- Stage at pivot: stage_0_main
- Should have observed: config-service filesystem/memory anomalies. ts-config-service is a central dependency called by many services — the +39 cascade on seat-service is downstream.
- Observed: seat-service's positive log delta.
- **Proximate cause**: `stopped at loudest upstream error volume`

### (4) Behavioral overlay
- one_truncated. Reflection reinforced wrong anchor. GT never considered.

## case_1140  [NetworkChaos / NetworkBandwidth]

### (1) What really happened
NetworkBandwidth on ts-food-service + ts-ui-dashboard. GT RC: both. Signal: ts-food-service log_delta -115 (base noise decreased), ts-ui-dashboard +10 (small positive).

### (2) What the agent did
Stage 0 terminator None. Stage 2 terminator ts-food-service. Final prediction: `rabbitmq` (hallucinated). Agent wandered through AMQP noise during stage_0 (no conclusion), refine anchored on food-service (correct-ish), but compress synthesized rabbitmq.

### (3) Divergence
- **Proximate cause**: `compress overwrote correct refine hypothesis`

### (4) Behavioral overlay
- A7-style: refine had food-service (correct) but compress produced rabbitmq.

## case_1143  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on ts-food-service. GT RC: ts-food-service. Signal: food-service log_delta -202 (container killed → errors stop), z=38058 filesystem, z=144 db.client.connections.use_time.

### (2) What the agent did
Stage 0 hypothesis ts-rabbitmq. Stages 1, 2 truncated. Agent saw food-service AMQP errors + interpreted as rabbitmq broker failure.

### (3) Divergence
- **Proximate cause**: `pod kill mistaken for broker failure`

### (4) Behavioral overlay
- two_truncated. Classic A2+A6 combo: rabbitmq hub hallucinated, food-service baseline noise anchor.

## case_1159  [HTTPFault / HTTPResponseDelay]

### (1) What really happened
HTTPResponseDelay on ts-food-service + ts-train-food-service. GT RC: both. Delay produces latency not errors (food-service log_delta -315 baseline decreased). Train-food-service jvm.class metric spike.

### (2) What the agent did
Stage 1 terminator ts-rabbitmq. Final: rabbitmq. Same food→rabbitmq pattern.

### (3) Divergence
- **Proximate cause**: `latency fault mistaken for broker failure`

### (4) Behavioral overlay
- A6+A2. Reflection inherited wrong anchor from stage_0 exploration.

## case_1195  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM mem stress on ts-order-other-service. GT RC: ts-order-other-service (23 metric anomalies, very strong).

### (2) What the agent did
Stage 0 hypothesis ts-rabbitmq. Stages 1, 2 truncated. Final: `ts-delivery-service, ts-food-service, ts-notification-service` (mixed hallucination). ts-food-service -100 baseline noise anchored.

### (3) Divergence
- **Proximate cause**: `pod mem stress mistaken for RabbitMQ`

### (4) Behavioral overlay
- two_truncated. A2+A6 combo again. Agent's first call to ERROR logs found food+delivery+notification AMQP cluster, never recovered.

## case_1218  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM mem stress on ts-order-service. GT RC: ts-order-service. Signal: container.filesystem.usage z=10^14 + k8s.pod.memory.major_page_faults z=10^9 (pod restart).

### (2) What the agent did
Only stage_2 terminator present (stages 0 and 1 both truncated). Hypothesis: ts-seat-service (+47 log delta). Stages 0 and 1 hit max_rounds without reaching conclusions.

### (3) Divergence
- **Proximate cause**: `stopped at loudest upstream error volume`

### (4) Behavioral overlay
- two_truncated but the truncated stages are the FIRST two. Only refine stage 2 produced any terminator. Unusual — agent was exploration-bound through stages 0 and 1.

## case_1371  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on ts-seat-service. GT RC: ts-seat-service. Signal: z=54784 filesystem, z=2069 jvm.class.loaded. Downstream ts-travel2-service +55, ts-travel-service +33 (ripples).

### (2) What the agent did
Stage 0 hypothesis ts-travel2-service (+55). Stages 1, 2 truncated.

### (3) Divergence
- **Proximate cause**: `stopped at loudest upstream error volume`

### (4) Behavioral overlay
- two_truncated. A1 pattern: biggest downstream ripple mistaken for root.

## case_1394  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM mem stress on ts-seat-service. GT RC: ts-seat-service. Signal: z=10^14 filesystem.

### (2) What the agent did
Stage 0 ts-travel2-service; Stage 1 ts-travel-service (changed). Final: both travel services predicted. Reflection reversed from travel2 to travel, but neither is GT.

### (3) Divergence
- **Proximate cause**: `stopped at loudest upstream error volume`

### (4) Behavioral overlay
- one_truncated, changed_across_stages=True but BOTH hypotheses were wrong (just different downstream services). A1 variant.

## case_1421  [NetworkChaos / DNSRandom]

### (1) What really happened
DNSRandom injected on ts-station-service ↔ mysql. GT RC: ts-station-service + mysql. Intermittent DNS failures cause connection errors.

### (2) What the agent did
Stage 0 hypothesis ts-consign-service (+377 log delta). Stages 1, 2 truncated.

### (3) Divergence
- **Proximate cause**: `largest error delta taken as cause`

### (4) Behavioral overlay
- two_truncated. A1 pattern — ts-consign-service had biggest delta despite being off the propagation path.

## case_1459  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM mem stress on ts-train-service. GT RC: ts-train-service. Signal: +6 log delta on train-service (small positive), z=10^14 filesystem.

### (2) What the agent did
Stage 2 hypothesis `ts-basic-service` (matched service), final prediction basic-service. Stage 0 null hypothesis; stage 1 truncated.

### (3) Divergence
- **Proximate cause**: `stopped one hop short upstream`

### (4) Behavioral overlay
- ts-basic-service is on propagation path as an upstream caller. A5 pattern.

## case_1484  [HTTPFault / HTTPResponseDelay]

### (1) What really happened
HTTPResponseDelay on ts-travel-plan-service + ts-train-service. GT RC: both. Small signal: travel-plan-service z=113 http.server.request.duration latency.

### (2) What the agent did
Stage 0 + Stage 2 anchored on `ts-route-plan-service` (hallucinated — not in GT, not on propagation path).

### (3) Divergence
- **Proximate cause**: `latency fault missed by error-count search`

### (4) Behavioral overlay
- A4 pattern. Reflection reinforced hallucinated hub.

## case_1495  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM mem stress on ts-travel-plan-service. GT RC: ts-travel-plan-service. Signal: filesystem z=10^14, memory page_faults z=81.

### (2) What the agent did
Stage 0 null hypothesis; stages 1, 2 truncated. Final: ts-seat-service (hallucinated).

### (3) Divergence
- **Proximate cause**: `stopped at loudest upstream error volume`

### (4) Behavioral overlay
- two_truncated. Agent had no strong error anchor anywhere; settled on ts-seat-service via compress synthesis.

## case_1504  [NetworkChaos / NetworkDelay]

### (1) What really happened
NetworkDelay on ts-travel-service ↔ mysql. Signal: z=5020 db.client.connections.wait_time (very strong DB latency).

### (2) What the agent did
Stage 0 hypothesis ts-rabbitmq. Stage 2 null. Final: rabbitmq.

### (3) Divergence
- **Proximate cause**: `anchored on pre-existing RabbitMQ noise`

### (4) Behavioral overlay
- A2+A6 combo. db.client metrics never queried.

## case_1562  [PodChaos / PodFailure]

### (1) What really happened
PodFailure on ts-travel2-service. GT RC: ts-travel2-service. Signal: z=426837 filesystem, z=192 memory (pod killed, then restarted).

### (2) What the agent did
Stage 0 + Stage 2 anchored on ts-route-plan-service (+52 log delta — downstream ripple).

### (3) Divergence
- **Proximate cause**: `stopped at loudest upstream error volume`

### (4) Behavioral overlay
- A1. Reflection reinforced. Missing-span signal on travel2 not queried.

## case_1814  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM mem stress on ts-basic-service. GT RC: ts-basic-service.

### (2) What the agent did
Stage 0 correctly said `ts-basic-service`. Stage 1 REVERSED to ts-travel-service (+26 log delta). Final: travel-service.

### (3) Divergence
- **Proximate cause**: `reflection reversed correct conclusion`

### (4) Behavioral overlay
- A3 pattern: correct → wrong via reflection. changed_across_stages=True.

## case_1860  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM mem stress on ts-contacts-service. GT RC: ts-contacts-service. Signal: hubble_http_request_duration_p90 z=932 (very strong latency on contacts).

### (2) What the agent did
Stage 0 null, stage 2 anchored on ts-ui-dashboard (+22 log delta). Final: ui-dashboard.

### (3) Divergence
- **Proximate cause**: `stopped at loudest upstream error volume`

### (4) Behavioral overlay
- A1. Didn't query hubble_http metrics on contacts.

## case_1862  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on ts-food-service. GT RC: ts-food-service (food-service log_delta -172 because container killed).

### (2) What the agent did
Stage 0 hypothesis ts-rabbitmq. Final: rabbitmq.

### (3) Divergence
- **Proximate cause**: `pod kill mistaken for broker failure`

### (4) Behavioral overlay
- two_truncated. A6+A2 combo. Note: food-service IS the GT but agent couldn't tell because food-service errors always present in baseline.

## case_1880  [HTTPFault / HTTPResponseReplaceBody]

### (1) What really happened
HTTPResponseReplaceBody on ts-food-service + ts-travel-service. GT RC: both. Food-service log_delta +1158 (huge positive — strong signal this time).

### (2) What the agent did
Stage 0 hypothesis ts-route-service (hallucinated). Stages 1, 2 truncated. Final: route-service.

### (3) Divergence
- **Proximate cause**: `hub hallucinated over strong signal`

### (4) Behavioral overlay
- two_truncated. Surprising: the +1158 GT signal was the BIGGEST positive log delta but agent picked an off-path ts-route-service instead.

## case_1886  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on ts-inside-payment-service. GT RC: ts-inside-payment-service. Signal: +2 log delta + z=44885 filesystem.

### (2) What the agent did
Stage 0 CORRECT: `ts-inside-payment-service`. Stages 1, 2 truncated. Final prediction: ts-ui-dashboard (hallucinated).

### (3) Divergence
- **Proximate cause**: `compress overwrote correct stage0 hypothesis`

### (4) Behavioral overlay
- A7 variant: stage_0 terminator was correct, but compress step replaced it with upstream ui-dashboard. two_truncated means no refine to reaffirm.

## case_1917  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on ts-order-service. GT RC: ts-order-service. Signal: order-service log_delta -33 (pod killed, fewer errors), z=48640 filesystem.

### (2) What the agent did
All 3 terminators: ts-seat-service. Anchored on seat-service +108 delta (downstream).

### (3) Divergence
- **Proximate cause**: `largest error delta taken as cause`

### (4) Behavioral overlay
- A1. all_concluded. Reflection reinforced across all 3 stages.


## case_1934  [PodChaos / PodFailure]

GT ts-order-service (killed pod, log_delta -15, z=10^14 filesystem). Stage 0 ts-seat-service (+29). Stages 1/2 truncated. Final: seat-service.
**Proximate cause**: `largest error delta taken as cause`
Overlay: A1, two_truncated. Wrong from stage 0.

## case_2130  [JVMChaos / JVMReturn]

GT ts-station-service (JVMReturn substitutes method return values). Signal: z=10^15 filesystem on station-service. Agent: ts-route-service (hallucinated, off-path). Stages 1/2 truncated.
**Proximate cause**: `hub hallucinated over no-error-signal`
Overlay: A4+A6. log_delta fully empty of positives — agent had nothing to anchor on.

## case_2211  [PodChaos / ContainerKill]

GT ts-travel-service (containerkill, +5 log delta, z=44885 filesystem). All 3 terminators named ts-route-plan-service (+2 log delta, upstream of travel-service in route-plan → travel-plan chain).
**Proximate cause**: `stopped one hop short upstream`
Overlay: A5. changed_across_stages=False. Reflection reinforced 3x.

## case_2231  [HTTPFault / HTTPRequestDelay]

GT ts-travel-service + ts-route-service. Signal: +2 on travel-service log_delta, z=216 db.client.connections.use_time on travel. Agent: ts-route-plan-service (hallucinated). Only stage 1 terminator (stage 0 null).
**Proximate cause**: `latency fault missed by error-count search`
Overlay: A4.

## case_2237  [HTTPFault / HTTPRequestReplacePath]

GT ts-travel-service + ts-route-service. Signal: travel-service log_delta +1509 (huge!). Agent: ts-route-plan-service (close but wrong — +53 delta). Reflection reinforced twice.
**Proximate cause**: `stopped one hop short upstream`
Overlay: A5 despite huge GT signal — agent picked the upstream-caller with smaller but "positive" delta.

## case_2253  [JVMChaos / JVMMemoryStress]

GT ts-travel-service. Signal: +5 log delta, z=10^14 filesystem. Agent: ts-route-plan-service (upstream of travel-svc). Both terminators.
**Proximate cause**: `stopped one hop short upstream`
Overlay: A5. Reflection reinforced.

## case_2258  [PodChaos / ContainerKill]

GT ts-travel2-service. Agent: ts-route-plan-service (+64 delta, upstream). 3/3 terminators. Reflection reinforced 3x.
**Proximate cause**: `stopped one hop short upstream`
Overlay: A5+A1.

## case_2283  [HTTPFault / HTTPRequestReplacePath]

GT ts-travel2-service + ts-basic-service. Signal: travel2-service log_delta +5722 (biggest ever). Stage 0 ts-basic-service (partial match), stage 1 pivoted to ts-route-plan-service. Final: route-plan.
**Proximate cause**: `reflection moved away from correct signal`
Overlay: A3 variant — refine ABANDONED a correct stage-0 hit.

## case_2390  [JVMChaos / JVMMemoryStress]

GT ts-user-service. Signal: z=10^14 filesystem + z=10^9 jvm.gc.duration. Agent: ts-ui-dashboard (+47 delta). Stages 1/2 truncated.
**Proximate cause**: `stopped at loudest upstream error volume`
Overlay: A1. 30 metric anomalies on user-service ignored.

## case_2479  [PodChaos / ContainerKill]

GT ts-config-service. Agent: ts-seat-service (+116 delta, downstream ripple from config-service cascade). Stages 1/2 truncated.
**Proximate cause**: `largest error delta taken as cause`
Overlay: A1.

## case_2584  [NetworkChaos / NetworkBandwidth]

GT ts-preserve-service + ts-travel-service. Signal: preserve-service log_delta -106 (restarts?). Stage 0 ts-security-service, stage 1 ts-order-other-service (changed, both hallucinated). Final: order-other.
**Proximate cause**: `hub hallucinated for shared latency`
Overlay: A6. Zero positive log_delta.

## case_2585  [PodChaos / ContainerKill]

GT ts-preserve-service. Agent: ts-route-service (hallucinated, off-path). Stages 1/2 truncated.
**Proximate cause**: `hub hallucinated over no-error-signal`
Overlay: A4+A6. preserve -5 delta, no big signal anywhere except ui-dashboard +59.

## case_2597  [HTTPFault / HTTPRequestDelay]

GT ts-preserve-service + ts-seat-service. preserve -14 baseline. Agent: ts-order-service (hallucinated). Stages 1/2 truncated.
**Proximate cause**: `latency fault missed by error-count search`
Overlay: A4.

## case_2678  [NetworkChaos / NetworkBandwidth]

GT ts-seat-service + ts-config-service. Agent: ts-travel2-service (+4 delta upstream). Both terminators.
**Proximate cause**: `stopped one hop short upstream`
Overlay: A5.

## case_2697  [JVMChaos / JVMMemoryStress]

GT ts-seat-service. Signal: z=10^14 filesystem. Agent: ts-travel2-service (+98). Stages 1/2 truncated. Final also adds travel-service.
**Proximate cause**: `stopped one hop short upstream`
Overlay: A5+A1.

## case_2700  [NetworkChaos / NetworkCorrupt]

GT ts-security-service + ts-preserve-service. preserve -72 baseline. Zero positive log_delta. Agent: ts-order-service (hallucinated). Stages 1/2 truncated, stage 0 null.
**Proximate cause**: `hub hallucinated over no-error-signal`
Overlay: A4+A6.

## case_2713  [JVMChaos / JVMMemoryStress]

GT ts-security-service. Stage 0 ts-order-service (wrong), stages 1+2 pivoted to ts-preserve-service (also wrong, but preserve is on security's propagation path). Final: preserve-service.
**Proximate cause**: `stopped one hop short upstream`
Overlay: A3-variant + A5. Reflection moved FROM one wrong anchor (order) to another wrong anchor (preserve, one hop short of security).

## case_2715  [NetworkChaos / NetworkBandwidth]

GT ts-station-service + ts-basic-service. Agent: ts-travel-service (+10 delta, downstream). Both terminators same.
**Proximate cause**: `stopped one hop short upstream`
Overlay: A5.

## case_2752  [HTTPFault / HTTPRequestAbort]

GT ts-travel-plan-service + ts-seat-service. Signal: +82 travel-plan (GT!). Stage 0 ts-route-plan-service (wrong), stage 1 pivoted to ts-seat-service (partial match with GT). Final: route-plan.
**Proximate cause**: `compress overwrote correct refine hypothesis`
Overlay: A7. Refine correctly found seat-service but compress output route-plan.

## case_2761  [HTTPFault / HTTPResponseDelay]

GT ts-travel-plan-service + ts-train-service. Agent: ts-route-plan-service (hallucinated). Signal: +3 travel-plan (GT has small positive), z=79 http.server.request.duration.
**Proximate cause**: `latency fault missed by error-count search`
Overlay: A4. Ignored strong latency metric.


## case_2769  [JVMChaos / JVMMemoryStress]

GT ts-travel-plan-service. Stage 0 ts-travel-plan-service (CORRECT). Stage 2 null. Final: ts-route-service (hallucinated).
**Proximate cause**: `compress overwrote correct stage0 hypothesis`
Overlay: A7. Compress ignored stage 0 verdict.

## case_2836  [HTTPFault / HTTPResponseReplaceBody]

GT ts-travel2-service + ts-basic-service. Signal: travel2 log_delta +363. Agent: ts-seat-service across 2 terminators.
**Proximate cause**: `stopped at loudest upstream error volume`
Overlay: A1. Didn't follow signal.

## case_2988  [JVMChaos / JVMCPUStress]

GT ts-basic-service. Agent: ts-order-service + ts-seat-service (both hallucinated). Stages 1/2 truncated. Zero positive log_delta (CPU stress → no errors).
**Proximate cause**: `cpu stress missed by error-count search`
Overlay: A4. No latency metric query on basic-service.

## case_3008  [NetworkChaos / NetworkCorrupt]

GT ts-contacts-service + ts-preserve-service. Stages oscillate: order → preserve → order. Final: order (hallucinated).
**Proximate cause**: `reflection oscillates between neighbors`
Overlay: New pattern candidate — neighboring hypotheses ping-pong across stages. changed_across_stages=True.

## case_3053  [JVMChaos / JVMMemoryStress]

GT ts-order-other-service. Agent: ts-seat-service. Stages 1/2 truncated.
**Proximate cause**: `stopped at loudest upstream error volume`
Overlay: A1+A4 (GT log delta empty, metric anomalies on order-other-service ignored).

## case_3059  [NetworkChaos / NetworkCorrupt]

GT ts-order-service + ts-ui-dashboard. Stage 0 null, stage 2 null. Final: rabbitmq.
**Proximate cause**: `anchored on pre-existing RabbitMQ noise`
Overlay: A2+A6. No stage reached conclusion; compress settled on rabbitmq.

## case_3076  [NetworkChaos / NetworkPartition]

GT ts-order-service + ts-ui-dashboard. Signal: ts-ui-dashboard log_delta +98 (CORRECT top positive!). Agent: ts-rabbitmq.
**Proximate cause**: `anchored on pre-existing RabbitMQ noise`
Overlay: A2+A6. Ignored the GT +98 signal, went to hallucinated rabbitmq.

## case_3114  [PodChaos / PodKill]

GT ts-preserve-service. Preserve log_delta -20. Agent: ts-ui-dashboard (hypothesis), final ts-order-service. Stages 1/2 truncated.
**Proximate cause**: `missing-span signal ignored`
Overlay: A4.

## case_3125  [HTTPFault / HTTPResponseDelay]

GT ts-preserve-service + ts-security-service. Stage 0 CORRECT: ts-preserve-service. Stage 1 REVERSED to ts-order-service. Final: order.
**Proximate cause**: `reflection reversed correct conclusion`
Overlay: A3.

## case_3128  [HTTPFault / HTTPResponseDelay]

Same GT as 3125. Agent: ts-order-service from start. Stages 1/2 null/truncated.
**Proximate cause**: `latency fault missed by error-count search`
Overlay: A4+A1. Stuck on order-svc.

## case_3222  [NetworkChaos / NetworkLoss]

GT ts-seat-service + ts-order-other-service. Signal: seat-service http.client.request.duration z=3412 (huge latency). Agent: ts-travel2-service. Stages 1/2 truncated.
**Proximate cause**: `stopped one hop short upstream`
Overlay: A5+A4. Didn't query latency metrics on seat-service.

## case_3266  [PodChaos / ContainerKill]

GT ts-train-service. train-svc +6 positive. Agent: ts-route-service (hallucinated, similar-name to route-plan). Stages 1/2 truncated.
**Proximate cause**: `confused similarly-named service`
Overlay: A9. +6 on train-svc was the signal; agent picked "ts-route-service" instead of train-service or route-plan.

## case_3278  [NetworkChaos / NetworkBandwidth]

GT ts-travel-plan-service + ts-ui-dashboard. Stage 0 ts-ui-dashboard (CORRECT part of GT!). Stages 1 and 2 PIVOTED to ts-route-plan-service (wrong). Final: route-plan.
**Proximate cause**: `reflection reversed correct conclusion`
Overlay: A3. Refine moved from partial-correct ts-ui-dashboard to off-path ts-route-plan-service.

## case_3284  [NetworkChaos / NetworkDelay]

GT ts-travel-plan-service + ts-seat-service. Agent: ts-route-service (hallucinated). 3/3 terminators same.
**Proximate cause**: `latency fault missed by error-count search`
Overlay: A4+A6. No positive log_delta, went to route-service by hallucination.

## case_3325  [PodChaos / ContainerKill]

GT ts-travel-service. Signal: +5 log delta (GT), z=28330 filesystem. Agent: ts-route-plan-service (+80 log delta, upstream). Stages 1/2 truncated.
**Proximate cause**: `stopped one hop short upstream`
Overlay: A5+A1.

## case_3465  [NetworkChaos / NetworkCorrupt]

GT ts-basic-service + ts-price-service. Agent: ts-route-plan-service. Stage 0 truncated.
**Proximate cause**: `hub hallucinated over no-error-signal`
Overlay: A4+A6. log_delta had only +1 notification-service (no anchor); compress went to route-plan.

## case_3556  [JVMChaos / JVMMemoryStress]

GT ts-travel2-service. Stage 0 ts-travel2-service (CORRECT!). Stage 1 REVERSED to ts-route-plan-service. Final: route-plan.
**Proximate cause**: `reflection reversed correct conclusion`
Overlay: A3. Refine pushed blame upstream.

## case_3600  [JVMChaos / JVMMemoryStress]

GT ts-station-service. Both terminators: ts-station-service (CORRECT!). But final prediction: ts-basic-service (NOT station!).
**Proximate cause**: `compress overwrote correct refine hypothesis`
Overlay: A7. Both stage terminators said station-service, compress output basic-service.

## case_3622  [NetworkChaos / NetworkDelay]

GT mysql + ts-order-service. Signal: order-service db.client.connections.wait_time z=1176. Agent: ts-rabbitmq. Both terminators.
**Proximate cause**: `anchored on pre-existing RabbitMQ noise`
Overlay: A2+A6. Ignored strong DB-wait signal, went to rabbitmq.

## case_3673  [PodChaos / ContainerKill]

GT mysql. Signal: +2695 on ts-auth-service (huge cascade from mysql being killed — auth uses mysql). Agent: ts-auth-service + ts-train-service. Both terminators auth.
**Proximate cause**: `largest error delta taken as cause`
Overlay: A1. Picked the service with largest downstream ripple.


## case_3700  [JVMChaos / JVMMemoryStress]

GT ts-config-service. Agent: ts-ticket-office-service (hallucinated, off-path). Stages 1/2 truncated.
**Proximate cause**: `hub hallucinated over no-error-signal`
Overlay: A6+A4. Zero stable anchor.

## case_3716  [JVMChaos / JVMMemoryStress]

GT ts-food-service (JVM mem stress ON food-service itself — rare case where food-service IS the GT). Agent: ts-rabbitmq. Stages 1/2 truncated. The agent saw food-service AMQP errors but went up to rabbitmq.
**Proximate cause**: `pod mem stress mistaken for RabbitMQ`
Overlay: A6+A2 (even though food-svc was correct, agent escalated).

## case_3760  [JVMChaos / JVMMemoryStress]

GT ts-price-service. Signal: z=10^14 filesystem. Agent: ts-basic-service (+211 log delta, downstream). Both terminators.
**Proximate cause**: `largest error delta taken as cause`
Overlay: A1. Price-service metrics ignored.

## case_3776  [PodChaos / PodFailure]

GT ts-seat-service. Agent: ts-travel2-service (+180 log delta, downstream ripple). Stages 1/2 truncated. Stage 0 null.
**Proximate cause**: `largest error delta taken as cause`
Overlay: A1. Classic downstream-ripple anchoring on PodFailure.

## case_3868  [JVMChaos / JVMLatency]

GT ts-config-service. Signal: z=10^15 filesystem. Agent: ts-consign-service (+168 log delta, unrelated). Stages 1/2 truncated.
**Proximate cause**: `latency fault missed by error-count search`
Overlay: A4+A1. config-service never considered.

## case_3878  [NetworkChaos / TimeSkew]

GT ts-consign-service. consign-svc log_delta -512 (dramatic baseline drop — TimeSkew breaks consign's own timestamping). Agent: ts-ui-dashboard (+1 delta). Stages 1/2 truncated.
**Proximate cause**: `missing-span signal ignored`
Overlay: A4. The GT's negative delta of 512 is a STRONG silence signal but agent didn't register it.

## case_3920  [JVMChaos / JVMMemoryStress]

GT ts-payment-service. Agent: ts-inside-payment-service (on-path, similar-name + +19 delta). Both terminators.
**Proximate cause**: `confused similarly-named service`
Overlay: A9. Payment vs inside-payment confusion.

## case_3955  [PodChaos / PodFailure]

GT ts-station-food-service. Agent: ts-food-service (similar-name). Stages 1/2 truncated.
**Proximate cause**: `confused similarly-named service`
Overlay: A9. food vs station-food.

## case_3966  [PodChaos / ContainerKill]

GT ts-train-food-service. Agent: ts-food-service. Both terminators.
**Proximate cause**: `confused similarly-named service`
Overlay: A9. train-food vs food.

## case_4032  [JVMChaos / JVMMemoryStress]

GT ts-auth-service. Agent: ts-ui-dashboard (+31 delta). Both terminators.
**Proximate cause**: `stopped at loudest upstream error volume`
Overlay: A1. auth-service metrics (z=10^14) ignored.

## case_4054  [PodChaos / ContainerKill]

GT ts-consign-price-service. Agent: ts-consign-service (upstream + similar-name). Both terminators.
**Proximate cause**: `confused similarly-named service`
Overlay: A9+A5. consign-price vs consign.

## case_4073  [PodChaos / ContainerKill]

GT ts-inside-payment-service. Agent: mysql (hallucinated). Stages 1/2 truncated.
**Proximate cause**: `hub hallucinated over no-error-signal`
Overlay: A6. Went to infrastructure (mysql) instead of the application service.

## case_4081  [PodChaos / ContainerKill]

GT ts-order-other-service. Agent: ts-seat-service (+32 delta). Stages 1/2 truncated.
**Proximate cause**: `largest error delta taken as cause`
Overlay: A1. order-other-service log_delta empty (pod killed).

## case_4229  [NetworkChaos / NetworkPartition]

GT ts-basic-service + ts-travel-service. Agent: ts-route-plan-service (hallucinated). Stages 1/2 truncated.
**Proximate cause**: `hub hallucinated over no-error-signal`
Overlay: A6+A4. No positive log_delta signal anywhere (partition → silence).

## case_4257  [PodChaos / PodFailure]

GT ts-consign-price-service. Stage 0 CORRECT: ts-consign-price-service. Stage 1 REVERSED to ts-consign-service. Final: consign-svc.
**Proximate cause**: `reflection reversed correct conclusion`
Overlay: A3. Classic: correct at stage 0, wrong after refine.

## case_4258  [PodChaos / ContainerKill]

GT ts-contacts-service. Signal: z=48981 filesystem, z=6.5e9 jvm.class.loaded. Agent: ts-ui-dashboard (+20 delta). Both terminators.
**Proximate cause**: `stopped at loudest upstream error volume`
Overlay: A1. 23 metric anomalies on contacts ignored.

## case_4309  [PodChaos / ContainerKill]

GT ts-payment-service (killed). Agent: ts-inside-payment-service. All 3 terminators same.
**Proximate cause**: `confused similarly-named service`
Overlay: A9. payment vs inside-payment. All 3 reflections reinforced wrong answer.

## case_4310  [PodChaos / PodFailure]

GT ts-payment-service. Agent: ts-inside-payment-service (similar-name + +503 log delta — huge ripple from payment failure). Stages 0/1 null.
**Proximate cause**: `confused similarly-named service`
Overlay: A9+A1.

## case_4353  [JVMChaos / JVMMemoryStress]

GT ts-station-service. Agent: ts-basic-service (+80, upstream of station). Stages 1/2 truncated.
**Proximate cause**: `stopped one hop short upstream`
Overlay: A5. Despite +13 on station-service (GT), agent went with +80 basic-service.

## case_4363  [JVMChaos / JVMMemoryStress]

GT ts-train-food-service. Agent: ts-rabbitmq. Stage 2 terminator; stage 1 truncated.
**Proximate cause**: `pod mem stress mistaken for RabbitMQ`
Overlay: A6+A2. Same food → rabbitmq escalation pattern.


## case_4375  [PodChaos / ContainerKill]

GT ts-travel2-service. travel2 +5 delta (GT). Agent: ts-route-plan-service (upstream of travel-plan which is upstream of travel2 — two hops). Stages 1/2 truncated.
**Proximate cause**: `stopped one hop short upstream`
Overlay: A5. Agent went to the second-highest positive delta (+11 ui-dashboard) but predicted ts-route-plan-service.

## case_4423  [NetworkChaos / NetworkBandwidth]

GT ts-basic-service + ts-preserve-service. preserve log_delta -104 (bandwidth → retries → errors timeout → logs silence). Agent: ts-ui-dashboard. Stages 1/2 truncated.
**Proximate cause**: `missing-span signal ignored`
Overlay: A4. Zero positive log_delta signal.

## case_4463  [PodChaos / ContainerKill]

GT ts-config-service. Agent: ts-food-service (hallucinated, off-path). All 3 terminators same.
**Proximate cause**: `anchored on pre-existing RabbitMQ noise`
Overlay: A2. Despite ts-ui-dashboard +224 delta being the biggest positive, agent anchored on food-svc's baseline noise.

## case_4510  [NetworkChaos / NetworkBandwidth]

GT ts-route-plan-service + ts-travel-service. Agent: ts-travel-plan-service (one hop away). Both terminators.
**Proximate cause**: `stopped one hop short upstream`
Overlay: A5. travel-plan is upstream of route-plan; agent stopped there.

## case_4519  [JVMChaos / JVMMemoryStress]

GT ts-route-plan-service. Signal: +39 travel-plan (downstream ripple, tied with ui-dashboard). Agent: ts-travel-plan-service. Stages 1/2 truncated.
**Proximate cause**: `stopped one hop short upstream`
Overlay: A5. Same pattern.

## case_4530  [JVMChaos / JVMMemoryStress]

GT ts-seat-service. Stage 0 CORRECT: ts-seat-service. Stage 2 REVERSED to ts-travel2-service. Final: travel2.
**Proximate cause**: `reflection reversed correct conclusion`
Overlay: A3. Classic A3: correct → wrong via refine.

## case_4617  [JVMChaos / JVMCPUStress]

GT ts-cancel-service. Zero positive log delta. Agent: mysql (hallucinated, with 14 more hallucinated services in graph). Stages 1/2 truncated.
**Proximate cause**: `cpu stress missed by error-count search`
Overlay: A4+A6. Hallucinated multiple services including mysql.

## case_4715  [JVMChaos / JVMMemoryStress]

GT ts-station-food-service. Signal: +9 log delta on station-food-svc. Agent: ts-rabbitmq. Stage 0 null, stage 2 terminator.
**Proximate cause**: `pod mem stress mistaken for RabbitMQ`
Overlay: A6+A2. Same pattern as 1143/1862/3716.

## case_4740  [PodChaos / ContainerKill]

GT ts-travel-plan-service. 3 terminators cycle: stage_0 null → stage 2 ts-basic-service → stage 2 ts-travel-service. Final: travel-service.
**Proximate cause**: `reflection oscillates between neighbors`
Overlay: New pattern — agent cycled through neighboring services in refine.

## case_4789  [JVMChaos / JVMMemoryStress]

GT ts-station-service. Signal: +13 delta + z=10^14 filesystem. Agent: ts-route-plan-service (+28, upstream). Stages 1/2 truncated.
**Proximate cause**: `stopped at loudest upstream error volume`
Overlay: A1.

## case_4801  [PodChaos / ContainerKill]

GT ts-security-service. Stage 0 ts-order-service. Stage 1 pivoted to ts-preserve-service (upstream of security). Final: preserve.
**Proximate cause**: `stopped one hop short upstream`
Overlay: A5+A3.

## case_4832  [JVMChaos / JVMMemoryStress]

GT ts-consign-service. Both terminators CORRECT: ts-consign-service. But final prediction: ts-ui-dashboard (upstream, hallucinated).
**Proximate cause**: `compress overwrote correct refine hypothesis`
Overlay: A7. Terminator-compress mismatch.

## case_4841  [NetworkChaos / NetworkDelay]

GT ts-station-service + mysql. Signal: z=91387 db.client.connections.wait_time on station-svc (MASSIVE). Stage 0 ts-rabbitmq, stage 1 PIVOTED to ts-food-service. Final: food-svc.
**Proximate cause**: `reflection escalated to baseline noise`
Overlay: A2+A8 hybrid. Stage 0 hallucinated rabbitmq broker, refine moved sideways to food-service (also noise).

