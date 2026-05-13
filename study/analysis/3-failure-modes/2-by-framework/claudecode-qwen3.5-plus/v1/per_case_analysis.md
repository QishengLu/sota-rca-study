# claudecode-qwen3.5-plus — Per-Case Failure Analysis

Independent emergent taxonomy build. Workspace sealed from thinkdepthai v2 artifacts until claudecode taxonomy is frozen.

Format per case:

```
## case_<idx>  [fault_type / subtype]

### (1) What really happened
<2-4 sentences grounded in Part A>

### (2) What the agent did
<2-4 sentences grounded in Part B, cite round indices>

### (3) Divergence
- Pivot round: <N>
- Missed signal: <GT evidence the agent failed to use>
- Agent saw instead: <round-cited observation that anchored wrong conclusion>
- Proximate cause (<6 words, causal): <short phrase>
```

Rules during per-case analysis:
- No theme names (no R1/R2/..., no borrowed thinkdepthai labels).
- Only the proximate-cause phrase in block (3).
- Primary label assignment happens in a final pass after all 114 cases have phrases.

---

## case_33  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress injected on `ts-auth-service` class `auth.security.jwt.JWTProvider.init`. Login path is loadgen → ts-ui-dashboard → ts-verification-code-service → ts-auth-service; JWTProvider's init stalled under memory pressure so `/api/v1/users/login` p99 blew from 0.51s to 20.0s (conclusion.csv: +0.6s avg, success 1.00→0.97). Because requests hung before ts-auth-service could emit its own span, abnormal traces contained only loadgen → ts-ui-dashboard entries.

### (2) What the agent did
Rounds 1-6: schema discovery. Rounds 7-13: found ts-ui-dashboard had 57 ERROR logs (503s) and reached from loadgen. Rounds 14-27: read the 503 message bodies, noticed Envoy/Caddy X-Envoy-Upstream-Service-Time 3-9s. Round 30: observed that failing traces contain no ts-auth-service span and inferred "ts-auth-service is NOT being called at all". Rounds 37-39: confirmed ts-auth-service reports 0 errors. Rounds 40-48: doubled down on "ts-ui-dashboard is failing BEFORE it can make any downstream calls" and attributed root cause to ts-ui-dashboard/proxy. Round 50: wrote final answer naming ts-ui-dashboard + loadgenerator.

### (3) Divergence
- Pivot round: 30
- Missed signal: absence of downstream child spans under a 503-timing-out parent is the signature of a hung downstream, not of an upstream-origin failure. ts-auth-service's zero-error count is consistent with requests that never completed far enough to produce an error span.
- Agent saw instead: failing traces have only loadgen → ts-ui-dashboard spans; ts-auth-service shows no errors in abnormal_traces.
- Proximate cause: **missing child span misread as upstream origin**

## case_156  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress injected on `ts-order-service` class `order.controller.OrderController.saveOrderInfo`. Order-save calls from ts-preserve-service / ts-travel-plan-service / ts-travel-service timed out, so order-refresh p99 jumped 0.43→20.0s (+success 1.00→0.96) and several upstream chains (travelPlan/minStation +2.4s, cheapest +1.1s) surfaced latency. The ts-order-service instance went effectively unavailable mid-window.

### (2) What the agent did
Rounds 1-4: schema discovery + cross-service error counts. Round 5: saw ts-food-service=101 errs (dismissed), ts-seat-service=56, ts-order-service=20; immediately narrowed to seat-service. Rounds 6-16: deep-dove seat-service logs/traces, noted "SocketException / RejectedExecutionException" patterns. Rounds 17-27: built call-chain view, placed ts-seat-service as parent of ts-order-service / ts-config-service / ts-order-other-service. Round 28: briefly doubted "loadgen and travel-plan errors arrived before seat's" but discarded the observation. Round 31: final verification on seat-service timestamps, emitted 12-node graph with `root_causes=[ts-seat-service]` and an edge seat→order reversing the actual causal flow.

### (3) Divergence
- Pivot round: 5
- Missed signal: ts-order-service also appeared in the error-count list (20 errs) and sits downstream of ts-preserve / ts-travel-plan in TrainTicket topology. Its "UNAVAILABLE" status at identical start timestamp is consistent with the origin, not with cascade.
- Agent saw instead: ts-seat-service had second-highest error count plus earliest SEVERE log; anchored on it and built a call-graph that put seat above order.
- Proximate cause: **anchored on highest-rank error service as root**

## case_247  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress injected on `ts-route-service` class `route.controller.RouteController.queryById`. The single SLO-violated endpoint is `/api/v1/routeservice/routes` (p99 0.23→20s). Conclusion top-1 is the routes span +0.6s. ts-route-service had 17280 spans (the highest in the dataset) but zero Error status codes — its methods simply hung under memory pressure.

### (2) What the agent did
Round 5-6: counted error_status rows per service — basic=33, ui-dashboard=15, loadgen=10. Round 7 reasoning explicitly noted "ts-route-service has 17280 spans with 0 errors" and dismissed it; chose ts-basic-service. Rounds 8-20: read basic-service's "503 Connection refused / upstream connect error" logs and built a call chain basic → travel → food → ui-dashboard. Rounds 21-58: tried to explain early ts-food-service errors as unrelated noise, verified timestamps. Final answer named ts-basic-service as root, fabricated edges upstream into travel/food/ui-dashboard. The SLO endpoint (routes) was never investigated.

### (3) Divergence
- Pivot round: 7
- Missed signal: route-service's enormous span volume combined with a 20s p99 on its own endpoint is the direct footprint of the fault; zero Error status simply meant requests hung before completing with an error.
- Agent saw instead: basic-service had 33 error rows and "503 Connection refused" log messages, the largest error_status concentration.
- Proximate cause: **zero-error latency-only victim dismissed**

## case_281  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress injected on `ts-station-food-service` method `StationFoodController.home`. ts-food-service calls station-food-service.home(); under memory pressure, station-food requests hung, so food-service's first-visible symptoms were its own "Get Food Request Failed!" log lines and RabbitMQ retry churn. SLO violated on `/foodservice/foods/...` p99 0.55→20s. GT timeline: station-food is silent origin, food-service is noisy caller.

### (2) What the agent did
Rounds 1-8: schema + cross-service error counts. Round 10-11: fixed on ts-food-service because it had the loudest error log ("Get the Get Food Request Failed!") and RabbitMQ DNS errors. Rounds 12-22: elaborated a fan-out chain food → ui-dashboard, food → delivery, food → notification, food → station-food, food → train-food. Rounds 23-33: brief mention of station-food-service but left it as a fan-out child of food-service. Final answer: root_causes=[ts-food-service] at timestamp 1724054988, with station-food-service listed as a downstream HIGH_ERROR_RATE node at a later timestamp.

### (3) Divergence
- Pivot round: 10
- Missed signal: the earliest-first-error reasoning used only log/trace error counts, which show the caller first because the callee is hung, not erroring. The SLO-violated endpoint is explicitly `foodservice/foods/.../{tripId}` which flows through station-food.home.
- Agent saw instead: food-service had the loudest log lines plus RabbitMQ failures.
- Proximate cause: **noisy caller shadowed silent injected callee**

## case_283  [NetworkChaos / NetworkBandwidth]

### (1) What really happened
NetworkBandwidth limit injected on the ts-station-service → mysql link (rate=470142, limit=8404, direction=from). Station-service's DB queries slowed dramatically, causing `/consignservice/consigns/order/{id}` avg latency 0.012→6.0s (success 1.00→0.70). Root lies in a two-node object: ts-station-service's upstream DB call path, with mysql as the congested endpoint.

### (2) What the agent did
Rounds 1-14: cataloged error counts across services. Agent noticed ts-food-service had high error counts and at round 16 checked whether they were baseline noise — correctly dismissed (round 567 reasoning). Rounds 17-22: switched to ts-consign-service because it had 5xx errors that did NOT appear in normal traces. Rounds 23-27: followed ts-consign-service's trace parents up to ts-ui-dashboard; never queried mysql/DB metrics, never examined ts-station-service span latency. Final answer: 3-node graph consign → ui-dashboard → loadgen with root=ts-consign-service. Missed station-service, basic-service, travel/preserve/route-plan, and the entire mysql dimension.

### (3) Divergence
- Pivot round: 17
- Missed signal: station-service SQL span latency, mysql connection / bandwidth metrics, and the fact that consign-service's 5xx errors trace back to a slow station-service DB fetch.
- Agent saw instead: consign-service had 5xx errors absent in normal traces, so it looked like a clean novel signal.
- Proximate cause: **stopped at first novel-error service, skipped DB/network layer**

## case_315  [HTTPFault / HTTPResponseDelay]

### (1) What really happened
HTTP response delay (605ms) injected on ts-travel-plan-service's outbound call to ts-train-service on route `/api/v1/trainservice/trains/byName/*`. The slow dependency made travel-plan endpoints (minStation avg 0.56→1.98s, cheapest 0.51→1.86s) breach SLO. GT pair: ts-travel-plan-service (the caller experiencing the delay) + ts-train-service (the target of the delay).

### (2) What the agent did
Rounds 1-15: schema + error surveys, detected ts-seat-service as an error-heavy service. Rounds 20-30: built a call chain where ts-seat-service was placed upstream of ts-travel-service and ts-travel-plan-service, treating their failures as propagation from seat. Rounds 40-56: verified seat had the latest timestamp progression and concluded seat → travel → travel-plan. Final: root_causes=[ts-seat-service], edges seat → travel, seat → travel-plan. ts-train-service never appeared in the output even though the injection route explicitly targets it.

### (3) Divergence
- Pivot round: 20
- Missed signal: the SLO endpoints are the travelPlan/* endpoints; the injection name/route explicitly references `trainservice/trains/byName`, which is the callee of travel-plan. Seat-service sits on a different call path (ticket booking), not on the travelPlan/minStation chain.
- Agent saw instead: seat-service had high error counts and a trace where it fanned out into travel-plan and travel services, which looked like top-of-chain propagation.
- Proximate cause: **edge direction inverted, symptom placed as origin**

## case_323  [NetworkChaos / TimeSkew]

### (1) What really happened
Clock skew injected on `ts-travel-plan-service` pod `ts-travel-plan-service-b8f74cc87-4n29n` (time_offset=-84s). The 84-second clock drift caused travelPlan/quickest and /cheapest endpoints to degrade (avg 0.54→3.96s / 0.53→2.50s, success 1.00→0.88), likely via cache TTL / token expiry / trace-correlation breakage downstream.

### (2) What the agent did
Rounds 1-12: surveyed error counts and found ts-notification-service / ts-delivery-service / ts-food-service with "RabbitMQ connection" errors. Rounds 13-20: anchored on "ts-rabbitmq is UNAVAILABLE" as the origin because notification/delivery/food were all RabbitMQ consumers. Rounds 21-24: slotted ts-travel-plan-service as a HIGH_LATENCY downstream node and pushed ts-rabbitmq to the root. Final: root_causes=[ts-rabbitmq]. Clock-skew semantics never considered; metric / tracing timestamp anomalies never cross-checked between pods.

### (3) Divergence
- Pivot round: 15
- Missed signal: the SLO-violated endpoints are the travelPlan/* endpoints on travel-plan-service, and the k8s/env data pinpoints a specific pod. Time-skew as a fault class doesn't show up as errors but as timestamp drift between this pod and others.
- Agent saw instead: notification/delivery/food's RabbitMQ failures, which cascaded into a phantom rabbitmq root.
- Proximate cause: **attributed to shared messaging infra, missed clock-skew dimension**

## case_339  [JVMChaos / JVMMySQLLatency]

### (1) What really happened
JVMMySQLLatency injected on ts-travel-service's SELECT queries on the `trip` table (latency_ms=3669). Travel-service DB reads slowed by ~3.7s, cascading through preserve/travel-plan/route-plan that depend on trip data; consignservice/consigns/order/{id} avg latency 0.018→3.35s.

### (2) What the agent did
Rounds 1-18: cataloged error counts. Rounds 19-28: identified ts-consign-service 5xx errors as novel vs. normal baseline, anchored there. Rounds 29-36: followed consign's parents to ui-dashboard / loadgen, produced a 3-node graph. Never queried mysql metrics, trip-table spans, or ts-travel-service SELECT latency.

### (3) Divergence
- Pivot round: 20
- Missed signal: the SLO endpoint is consigns/order which flows through travel-service, and the fault dimension is DB-latency; trip-table SELECT spans with elevated duration are the direct footprint.
- Agent saw instead: consign-service had 5xx errors that didn't appear in normal baseline.
- Proximate cause: **stopped at first novel-error service, skipped DB/latency dimension**

## case_341  [PodChaos / PodFailure]

### (1) What really happened
Pod failure injected on `ts-travel-service` (whole pod down for 4 minutes). travelPlan/cheapest avg 0.34→20s, foodservice/foods p99 0.37→18.9s — every caller of travel-service degraded.

### (2) What the agent did
Rounds 1-20: surveyed cross-service error rates, found ts-route-plan-service and ts-travel-plan-service as heaviest error producers. Rounds 21-32: built a chain with ts-route-plan-service on top, marked ts-travel-service absent from final output. Rounds 33-37: noted travel-service had missing spans but interpreted as "downstream unavailable so route-plan couldn't call it" — never elevated travel-service to root. Final: root_causes=[ts-route-plan-service].

### (3) Divergence
- Pivot round: 22
- Missed signal: a pod failure produces no spans for the dead service; its upstream callers (route-plan, travel-plan) show the cascade. Combined with 4-min gap in travel-service traces and k8s.json pod restart data, travel-service is the clear origin.
- Agent saw instead: route-plan-service had earliest-timestamp errors because it was the first caller to notice travel-service was down.
- Proximate cause: **caller-of-dead-pod promoted to root instead of dead pod**

## case_551  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on `ts-consign-service` pod. The account-consigns endpoint p99 jumped to 8.4s (success 1.00→0.88). Consign-service went UNAVAILABLE for the injection window.

### (2) What the agent did
Rounds 1-25: surveyed error patterns; correctly noted ts-consign-service was unresponsive. Rounds 26-40: produced a 2-node graph ui-dashboard → consign-service with consign marked UNAVAILABLE. Rounds 41-43: chose root_causes=[ts-ui-dashboard] on the reasoning that ui-dashboard's HIGH_ERROR_RATE was the "loadgen-facing" failure.

### (3) Divergence
- Pivot round: 40
- Missed signal: an UNAVAILABLE downstream that ui-dashboard depends on is the root; the upstream merely carries the error.
- Agent saw instead: the outward-facing HIGH_ERROR_RATE at ui-dashboard.
- Proximate cause: **correct node identified, outermost error receiver labeled root**

## case_572  [HTTPFault / HTTPResponsePatchBody]

### (1) What really happened
HTTPResponsePatchBody injected on ts-food-service's outbound call to ts-train-food-service (route `/api/v1/trainfoodservice/trainfoods/*`). Response bodies patched to invalid/empty, so food-service's consumer logic raised "Get Food Request Failed!" exceptions; consignservice/consigns/order/{id} degraded 0.016→2.87s (success 1.00→0.86).

### (2) What the agent did
Rounds 1-14: surveyed error logs, noted RabbitMQ DNS-related messages in ts-food-service, ts-notification-service, ts-delivery-service. Rounds 15-20: anchored on "ts-rabbitmq UNAVAILABLE, causing cascade". Final: 7-node graph with root=ts-rabbitmq; the actual HTTP response-patch fault between food-service and train-food-service never identified. train-food-service hallucinated absent from graph; food-service present but as cascade node.

### (3) Divergence
- Pivot round: 15
- Missed signal: the RabbitMQ "Name or service not known" DNS errors appear in normal_logs too (baseline noise). The true signal is the corrupted response bodies on trainfoodservice/* route — visible as malformed responses in food-service logs.
- Agent saw instead: RabbitMQ errors across multiple services that looked like a shared-infra failure.
- Proximate cause: **baseline-noise RabbitMQ errors hallucinated as root infra failure**

## case_710  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-route-plan-service method `RoutePlanServiceImpl.getStationList`. travel-plan calls route-plan for station lookup; memory pressure made getStationList hang, so travelPlan/quickest avg 0.65→2.05s, travelPlan/cheapest 0.65→4.67s (success 1.00→0.88).

### (2) What the agent did
Rounds 1-22: error surveys across services; found ts-travel-plan-service had cascading errors on the travelPlan endpoints. Rounds 23-35: focused entirely on ts-travel-plan-service internals, never drilled into its callees. Rounds 36-38: concluded root=ts-travel-plan-service. ts-route-plan-service not queried beyond a passing mention; its span duration and memory metrics never examined.

### (3) Divergence
- Pivot round: 22
- Missed signal: travelPlan endpoints depend on route-plan's getStationList; the SLO latency is consistent with a hung callee, not a travel-plan internal issue.
- Agent saw instead: travel-plan-service had the highest error-rate spans on its own outward endpoints.
- Proximate cause: **noisy caller anchored, silent callee unqueried**

## case_741  [PodChaos / PodFailure]

### (1) What really happened
Pod failure on ts-route-service. The only SLO endpoint is /routeservice/routes with avg 0.04→19.2s and success 1.00→0.04 (96% failure). route-service stopped responding for 4 minutes; ui-dashboard returned 503 on every /routes request.

### (2) What the agent did
Rounds 1-18: surveyed error counts; noted ts-ui-dashboard 503s + ts-food-service baseline "Get Food Request Failed" (correctly dismissed as noise). Rounds 19-30: established ts-ui-dashboard's 503s are the distinguishing signal. Rounds 31-38: wrote "evidence points to ts-ui-dashboard as root cause. The service is returning 503 errors but the downstream services are healthy". Final: 2-node graph ui-dashboard → loadgen, root=ts-ui-dashboard. ts-route-service never appears despite being the explicit SLO endpoint's target service.

### (3) Divergence
- Pivot round: 24
- Missed signal: "downstream services are healthy" misread absence-of-spans-from-dead-route-service as health; the /routeservice/routes endpoint is route-service's own endpoint — the 96% success drop is on route-service.
- Agent saw instead: ui-dashboard 503 error logs, and no visible errors on named downstream services.
- Proximate cause: **dead-pod's silence read as health, front-end 503 claimed as root**

## case_755  [NetworkChaos / NetworkPartition]

### (1) What really happened
Network partition from ts-seat-service to ts-travel2-service (direction=to). Seat-service's calls to travel2 hung; travel2 shows 88-second span durations in abnormal traces. order-refresh p99 0.43→20s.

### (2) What the agent did
Rounds 1-18: surveyed cross-service errors. Round 22: noticed ts-travel2-service had a single 88-second span ("very high latency"). Rounds 23-35: despite that signal, built a chain order → seat → travel → route-plan → travel-plan → ui-dashboard and declared ts-order-service the top. Rounds 36-44: confirmed causal direction by time ordering; travel2-service never made it into the final graph.

### (3) Divergence
- Pivot round: 23
- Missed signal: the 88-second latency on ts-travel2-service directly observed at round 22 is the clearest evidence of the partition; combined with seat-service being the partition source, the pair is the root.
- Agent saw instead: a long caller chain where order-service appeared at the furthest upstream position.
- Proximate cause: **recognized anomaly dropped in favor of upstream-most chain node**

## case_762  [HTTPFault / HTTPResponseDelay]

### (1) What really happened
HTTPResponseDelay (1680ms) injected on ts-seat-service's outbound call to ts-order-service via route `/api/v1/orderservice/order/*`. Seat-service's POST-order dependency slowed; travelPlan/cheapest avg 0.67→8.69s (success 1.00→0.67), travelservice/trips/left avg 0.20→4.63s.

### (2) What the agent did
Rounds 1-25: error count surveys across 9 services. Rounds 26-35: caught "UnknownHostException: ts-rabbitmq: Name or service not known" errors in notification/delivery/food logs. Rounds 36-55: elaborated rabbitmq as root with cascade through notification/delivery/food, then seat/order/preserve. Rounds 56-65: compiled final answer with root=ts-rabbitmq, hallucinated 5 unrelated services, missed travel-service + route-plan-service.

### (3) Divergence
- Pivot round: 30
- Missed signal: the injection route `/orderservice/order/*` and the specific SLO on travelPlan + trips/left are consistent with a delay between seat-service and its order-service callee. RabbitMQ DNS errors exist in normal_logs at the same frequency.
- Agent saw instead: RabbitMQ DNS failures that clustered across three RabbitMQ-consumer services.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure**

## case_804  [PodChaos / PodFailure]

### (1) What really happened
Pod failure on ts-train-service. /trainservice/trains avg 0.04→20s with success 1.00→0.00, and /travelPlan/minStation success 0.98→0.00 — train-service stopped responding entirely. All travelPlan endpoints that eventually hit train-service failed.

### (2) What the agent did
Rounds 1-16: surveyed error logs; noticed ts-basic-service had HIGH_ERROR_RATE + UNAVAILABLE markers on its own DB calls. Rounds 17-24: built a graph basic → travel/travel2 → route-plan → travel-plan → ui-dashboard. Rounds 25-26: concluded basic as root. ts-train-service never queried despite the SLO endpoint explicitly being its own `/trainservice/trains`.

### (3) Divergence
- Pivot round: 16
- Missed signal: the dead pod produces no spans; /trainservice/trains 100% failure is a direct footprint of train-service being down.
- Agent saw instead: ts-basic-service's database-connection errors (which are themselves caused by basic-service failing to reach train-service for data).
- Proximate cause: **caller-of-dead-pod promoted, dead pod unqueried**

## case_807  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-train-service class `TrainType.TrainType` (constructor). /trainservice/trains p99 0.17→20s. train-service's trains endpoint hung under memory pressure, cascading into basic-service (which calls train-service).

### (2) What the agent did
Rounds 1-25: standard error + schema surveys. Rounds 26-40: found ts-train-service had slow HTTP spans and HikariCP connection-pool warnings. Rounds 41-49: interpreted the HikariCP warnings as MySQL connection pool exhaustion, added mysql to graph as root, marked train-service as HIGH_ERROR_RATE node downstream of mysql.

### (3) Divergence
- Pivot round: 35
- Missed signal: JVM memory stress causes thread-pool/GC issues, which secondarily manifest as pool-exhausted DB client warnings. The primary signal is the 20s p99 on train-service's own endpoint and memory/GC metrics on the train-service pod.
- Agent saw instead: HikariCP "pool" warnings in train-service logs, which it interpreted as a mysql problem.
- Proximate cause: **JVM memory symptom misread as DB pool exhaustion**

## case_864  [HTTPFault / HTTPResponseReplaceCode]

### (1) What really happened
HTTPResponseReplaceCode fault on ts-travel-service's outbound call to ts-route-service at route `/api/v1/routeservice/routes/*`, replacing status_code with 7 (non-standard). travel-service's callers (travelPlan/cheapest) saw success 1.00→0.80, foods endpoint p99 up to 20s.

### (2) What the agent did
Rounds 1-16: error surveys. Rounds 17-25: saw RabbitMQ DNS errors in notification/delivery/food + travel-service "CONNECTION_RESET" errors. Rounds 26-27: emitted root=ts-rabbitmq with sprawling graph hallucinating basic/delivery/notification/seat/route-service/rabbitmq nodes. Missed ts-ui-dashboard.

### (3) Divergence
- Pivot round: 20
- Missed signal: the injection route pinpoints travel-service → route-service; ts-travel-service's CONNECTION_RESET errors on /routeservice/routes/* requests are the direct footprint of status_code replacement.
- Agent saw instead: RabbitMQ DNS errors in baseline-noise services.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure**

## case_1004  [NetworkChaos / NetworkDelay]

### (1) What really happened
Network delay (latency=164ms, jitter=943, correlation=35) injected on the mysql → ts-route-service link. route-service's DB reads slowed; /routeservice/routes avg 0.017→9.05s, travelPlan/quickest avg 0.42→15.4s. Two-node root object: mysql (source of delay) + ts-route-service (target).

### (2) What the agent did
Rounds 1-12: error + schema surveys. Rounds 13-20: noticed RabbitMQ DNS errors and declared "CPU and memory metrics look normal - no resource exhaustion issues. The root cause is clearly the ts-rabbitmq unavailability". Rounds 21-25: wrote a 15-node graph with rabbitmq at top, everything else marked HIGH_LATENCY. Missed the mysql/network dimension entirely.

### (3) Divergence
- Pivot round: 15
- Missed signal: the SLO on /routeservice/routes with 526% latency change is route-service-local. Combined with mysql-latency metrics on route-service's DB spans, the delay between mysql and route-service is direct.
- Agent saw instead: the same RabbitMQ DNS baseline-noise pattern.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure**

## case_1114  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-config-service class `ConfigApplication.restTemplate`. config-service's RestTemplate bean is reused across its outbound HTTP clients; memory pressure slowed every outbound call. Many services that fetch config (or are down-propagated from config-dependent paths) saw latency spikes; travelservice/trips/left p99 0.50→20s.

### (2) What the agent did
Rounds 1-11: surveyed errors. Rounds 12-16: focused on ts-seat-service which showed the highest error rate among named services. Rounds 17-19: built a cascade seat → travel/travel2/preserve → route-plan → travel-plan → ui-dashboard, selected root=ts-seat-service. ts-config-service entirely absent from output.

### (3) Divergence
- Pivot round: 13
- Missed signal: config-service is a middleware that nearly all other services depend on; the cascade pattern (every service HIGH_LATENCY simultaneously) is the signature of a shared-dependency failure, not a seat-service origin.
- Agent saw instead: seat-service had the noisiest individual error counts in the cascade.
- Proximate cause: **anchored on noisiest cascade node, missed shared-dependency**

## case_1118  [PodChaos / ContainerKill]

### (1) What really happened
Container kill on ts-consign-service pod. /consignservice/consigns/account/{id} p95 0.017→19.7s, p99 20.0s. consign-service became UNAVAILABLE for 4 minutes.

### (2) What the agent did
Rounds 1-14: error surveys, observed ts-notification / delivery / food DNS errors for ts-rabbitmq. Rounds 15-25: built cascade rabbitmq → notification/delivery/food, plus food → ui-dashboard. Rounds 26-29: concluded root=ts-rabbitmq, 5-node graph, consign-service absent.

### (3) Divergence
- Pivot round: 15
- Missed signal: the SLO endpoint is `/consignservice/*` and consign-service is absent from abnormal traces during the window — a dead-pod footprint.
- Agent saw instead: RabbitMQ DNS errors in baseline-noise services.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_1118)

## case_1140  [NetworkChaos / NetworkBandwidth]

### (1) What really happened
Network bandwidth limit injected on the ts-food-service → ts-ui-dashboard link (rate=14664, limit=2596). food-service responses throttled; /consignservice/consigns/order/{id} avg 0.012→4.45s, /travelservice/trips/left p99 1.13→6.64s.

### (2) What the agent did
Rounds 1-10: surveyed errors, caught a "ConsignRepository.findByOrderId: query did not return a unique result" exception in consign-service. Rounds 11-17: declared "the root cause is in ts-consign-service at the ConsignRepository.findByOrderId layer, where a database query returns non-unique results". Final: 3-node graph consign → ui-dashboard → loadgen, root=consign-service. food-service never touched; bandwidth metrics never queried.

### (3) Divergence
- Pivot round: 10
- Missed signal: the findByOrderId exception appears in normal_logs at the same frequency — baseline noise. The fault is bandwidth throttling between food-service and ui-dashboard; network-metric / egress-bytes data on food-service's outbound link is the direct footprint.
- Agent saw instead: an ORM-level non-unique-result exception that read like a concrete bug.
- Proximate cause: **baseline-noise ORM exception hallucinated as root**

## case_1143  [PodChaos / ContainerKill]

### (1) What really happened
Container kill on ts-food-service pod. /foodservice/foods/... p99 0.21→20s, travelPlan/minStation p95 0.91→7.30s. food-service gone for 4 minutes; cascade via preserve-service and order-service.

### (2) What the agent did
Rounds 1-11: surveyed errors. Rounds 12-18: RabbitMQ DNS errors anchored as root. Rounds 19-23: built rabbitmq → notification/delivery/food cascade; food-service present as downstream node but not root. Final: root=ts-rabbitmq.

### (3) Divergence
- Pivot round: 13
- Missed signal: the SLO endpoint is /foodservice/*, food-service pod absent from abnormal traces for the window.
- Agent saw instead: RabbitMQ DNS baseline-noise errors.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_1143)

## case_1144  [PodChaos / ContainerKill]

### (1) What really happened
Container kill on ts-food-service pod (different pod ID than 1143 but same fault). /foodservice/foods/... p99 0.35→20s.

### (2) What the agent did
Round 425 reasoning confirms agent's commitment: "confirm the root cause is the ts-rabbitmq DNS resolution failure". Rounds 1-27: survey → RabbitMQ DNS anchor → 8-node graph with ts-rabbitmq UNAVAILABLE+DNS_ERROR at top. food-service HIGH_ERROR_RATE downstream.

### (3) Divergence
- Pivot round: 14
- Missed signal: same as c1143 — food-service container kill, missing spans, direct SLO on its own endpoint.
- Agent saw instead: RabbitMQ DNS errors.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_1144)

## case_1159  [HTTPFault / HTTPResponseDelay]

### (1) What really happened
HTTPResponseDelay (4724ms) on ts-food-service's outbound call to ts-train-food-service at `/api/v1/trainfoodservice/trainfoods/*`. /foodservice/foods/... avg 0.03→5.02s, p99 0.18→15.15s.

### (2) What the agent did
Rounds 1-14: surveys. Rounds 15-20: RabbitMQ DNS anchor. Rounds 21-24: 7-node graph with rabbitmq at top; food-service present as cascade node with HIGH_ERROR_RATE.

### (3) Divergence
- Pivot round: 15
- Missed signal: the injection route pinpoints food → train-food; train-food-service is absent from the agent's graph.
- Agent saw instead: RabbitMQ DNS baseline noise.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_1159)

## case_1195  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-order-other-service class `OrderOtherServiceImpl.getOrderById`. /orderOtherService/orderOther/refresh p99 0.026→20s.

### (2) What the agent did
Rounds 1-30: surveys; found 500 errors with "Order already exists" in ts-order-service logs. Rounds 31-41: concluded root=ts-order-service. ts-order-other-service present in nodes (matched) but labeled as cascade downstream of ts-order-service.

### (3) Divergence
- Pivot round: 30
- Missed signal: the SLO is on `/orderOtherService/*` (a distinct endpoint from `/orderService/*`); ts-order-other-service is a separate microservice.
- Agent saw instead: ts-order-service had visible "Order already exists" 500 errors, likely baseline.
- Proximate cause: **similar-name service confused, wrong variant named root**

## case_1218  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-order-service class `OrderInfo.enableBoughtDateQuery`. travelPlan/minStation avg 0.99→20s.

### (2) What the agent did
Rounds 1-22: surveys. Rounds 23-30: noted HikariCP pool warnings on ts-seat-service, interpreted them as "mysql UNAVAILABLE" and placed mysql at graph root. Rounds 31-34: final graph with mysql UNAVAILABLE at top, seat-service UNAVAILABLE cascade, and travel/travel2/travel-plan HIGH_ERROR_RATE downstream. ts-order-service entirely absent.

### (3) Divergence
- Pivot round: 27
- Missed signal: the SLO endpoints involve travelPlan/minStation which calls into order/seat flows. OrderInfo.enableBoughtDateQuery memory stress makes order-related queries hang.
- Agent saw instead: HikariCP pool warnings misread as DB-server failure.
- Proximate cause: **JVM memory symptom misread as DB pool exhaustion** (case_1218)

## case_1280  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-preserve-service class `PreserveServiceImpl.preserve`. /preserveservice/preserve p95 0.89→18.5s.

### (2) What the agent did
Rounds 1-12: surveys. Round 18: agent explicitly noted "RabbitMQ issues exist in BOTH normal and abnormal data. So the ts-rabbitmq DNS issue is a pre-existing condition, not the root cause" — correctly dismissed. Rounds 19-25: chose ts-order-service as root (order is a sibling to preserve in the booking flow). Rounds 26-27: DESPITE the earlier dismissal, included ts-rabbitmq UNAVAILABLE as a co-root in the final output alongside ts-order-service.

### (3) Divergence
- Pivot round: 20
- Missed signal: preserve-service's own endpoint is the SLO violator, and preserve.preserve method's memory stress is on preserve itself. order-service was not injected.
- Agent saw instead: ts-order-service had 500 errors on order-save endpoints (cascading from preserve hanging in preserve() which then times out the order-save call).
- Proximate cause: **dismissed baseline noise re-included in final root list**

## case_1371  [PodChaos / ContainerKill]

### (1) What really happened
Container kill on ts-seat-service pod. /travel2service/trips/left p99 0.84→16.2s. seat-service dead 4 minutes; travel/travel2/route-plan/travel-plan (all callers) cascade.

### (2) What the agent did
Rounds 1-40: surveys, noted 500/503 across travel/travel2/route-plan. Rounds 41-55: identified ts-travel2-service as having the earliest 500s, elected root. Rounds 56-60: final graph with travel2 at top, seat-service absent.

### (3) Divergence
- Pivot round: 42
- Missed signal: seat-service pod gap + the fact that travel2 only fails when calling seat-service for ticket availability.
- Agent saw instead: travel2's 500 errors appeared the earliest among visible-error services.
- Proximate cause: **dead-pod silence, earliest-error caller named root**

## case_1394  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-seat-service class `SeatController.getLeftTicketOfInterval`. travelPlan/minStation p95 0.91→7.0s. seat-service ticket-interval query hangs.

### (2) What the agent did
Rounds 1-20: surveys. Rounds 21-30: focused on ts-travel-service / ts-travel2-service 500 errors; determined they were UNAVAILABLE. Rounds 31-33: final root=[travel-service, travel2-service]. seat-service absent.

### (3) Divergence
- Pivot round: 22
- Missed signal: seat-service's SeatController is the injected method; travel-service/travel2 call seat for ticket queries which hang, causing their UNAVAILABLE status.
- Agent saw instead: travel/travel2 had the heaviest error concentrations in the trace data.
- Proximate cause: **silent-under-stress injected service shadowed by heaviest-error callers**

## case_1421  [NetworkChaos / DNSRandom]

### (1) What really happened
DNS Random fault on ts-station-service's resolution of `mysql` domain. station-service's DB connections randomly fail to resolve mysql hostname; /consignservice/consigns/order/{id} avg 0.011→5.46s (success 1.00→0.73).

### (2) What the agent did
Rounds 1-25: surveys, identified ts-consign-service as having the largest error concentration. Rounds 26-35: built 10-node HIGH_LATENCY graph with consign at top, ui-dashboard in the middle fanning out to travel/route/preserve. Rounds 36-39: final root=ts-consign-service. station-service absent; mysql absent; DNS dimension never probed.

### (3) Divergence
- Pivot round: 24
- Missed signal: DNS errors in station-service logs or failed connections to mysql hostname resolve — the direct footprint.
- Agent saw instead: consign-service had the heaviest visible errors from the cascade.
- Proximate cause: **DNS/infra layer skipped, first application-layer error-rich service anchored**

## case_1435  [PodChaos / ContainerKill]

### (1) What really happened
Container kill on ts-train-food-service. /foodservice/foods/... p99 0.27→20s. food-service calls train-food for food-ordering on trains; train-food pod dead 4 minutes → food-service's SEVERE "Connection refused" errors.

### (2) What the agent did
Rounds 1-28: surveys, saw ts-food-service SEVERE "Connection refused" as the most prominent signal. Rounds 29-34: built 2-node graph food → ui-dashboard with root=ts-food-service. train-food-service never queried or added.

### (3) Divergence
- Pivot round: 14
- Missed signal: food-service's "Connection refused" target is train-food-service (it's the one refusing connections because its pod is dead).
- Agent saw instead: food-service was the service logging the error messages.
- Proximate cause: **caller-of-dead-pod promoted, dead pod unqueried** (case_1435)

## case_1459  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-train-service class `InitData.run` (startup data initializer). train-service is used by travel/travel2/basic services to resolve train info; memory pressure on init causes its queries to hang. travelPlan/quickest success 1.00→0.83.

### (2) What the agent did
Rounds 1-13: surveys. Rounds 14-18: built a chain basic → travel/travel2 → route-plan → travel-plan → ui-dashboard, root=ts-basic-service with HIGH_CPU. train-service entirely absent.

### (3) Divergence
- Pivot round: 12
- Missed signal: InitData.run is train-service's own method; memory stress there would stall train-data lookups that basic/travel depend on.
- Agent saw instead: ts-basic-service's HIGH_CPU (a secondary symptom from retrying train-service calls).
- Proximate cause: **caller's secondary CPU spike promoted, dead/silent callee unqueried**

## case_1484  [HTTPFault / HTTPResponseDelay]

### (1) What really happened
HTTPResponseDelay (4221ms) on ts-travel-plan-service's outbound call to ts-train-service. travelPlan/quickest avg 0.41→9.22s, p95 19.96s. Same pattern as c315, c323 but longer delay.

### (2) What the agent did
Rounds 1-25: surveys; noticed rabbitmq-related errors in delivery/notification/food. Rounds 26-35: anchored on ts-delivery-service as root (different from usual rabbitmq anchor but similar mechanism). Rounds 36-37: final graph with delivery at top, travel-plan as cascade, train-service absent.

### (3) Divergence
- Pivot round: 28
- Missed signal: the injection explicitly names the travel-plan → train-service route; delivery-service is on a different call path (notification/messaging).
- Agent saw instead: delivery-service had baseline rabbitmq-related errors, miscast as novel signal.
- Proximate cause: **baseline messaging-error service hallucinated as root**

## case_1495  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-travel-plan-service class `TravelPlanController.home`. travelPlan/minStation p95 0.90→16.08s. The injected service IS travel-plan-service.

### (2) What the agent did
Rounds 1-50: very long exploration (73 rounds total); surveyed multiple services. Rounds 51-60: selected ts-seat-service as root based on trace chains seat → route-plan → travel-plan. Rounds 61-73: final graph with seat at top, travel-plan as middle node. travel-plan-service itself matched as node but not as root.

### (3) Divergence
- Pivot round: 51
- Missed signal: travel-plan-service's own controller method is injected; its span latency on travelPlan/minStation is the direct footprint.
- Agent saw instead: seat-service had higher visible error rate and sat upstream in the call graph built by the agent.
- Proximate cause: **inverted chain upstream, injected service left as middle node**

## case_1814  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-basic-service class `BasicController.queryForStationId`. basic-service is the station-name resolver for many upstream services; memory pressure hangs its queries.

### (2) What the agent did
Rounds 1-38: surveys, focused on ts-travel-service having HIGH_ERROR_RATE + HIGH_LATENCY. Rounds 39-47: chose ts-travel-service as root with basic-service as a HIGH_LATENCY child node. basic-service present in graph (matched) but not as root.

### (3) Divergence
- Pivot round: 28
- Missed signal: queryForStationId is basic-service's own method; travel-service fails because its station-name lookups to basic-service hang.
- Agent saw instead: travel-service's HIGH_ERROR_RATE dominated the visible signal.
- Proximate cause: **injected service retained as child node, noisy caller named root**

## case_1837  [JVMChaos / JVMException]

### (1) What really happened
JVMException injected on ts-consign-service class `ConsignServiceImpl.queryByOrderId` (exception_opt=1 — throws a Java exception). consign's queryByOrderId raises exceptions on every call during the window.

### (2) What the agent did
Dossier reports 0 rounds — the trajectory was unusual. The final answer is a 2-node graph ui-dashboard → consign-service, root=ts-ui-dashboard. consign-service matched as node but not as root.

### (3) Divergence
- Pivot round: 0 (minimal trajectory)
- Missed signal: consign-service exceptions on queryByOrderId are the direct signal.
- Agent saw instead: ui-dashboard HIGH_ERROR_RATE at outer layer.
- Proximate cause: **outermost error receiver labeled root, exception-emitting service left as child**

## case_1862  [PodChaos / ContainerKill]

### (1) What really happened
Container kill on ts-food-service pod. /foodservice/* endpoint down.

### (2) What the agent did
Rounds 1-35: surveys. Rounds 36-40: RabbitMQ DNS anchor. Final: 7-node graph, root=ts-rabbitmq UNAVAILABLE. Food-service present as HIGH_ERROR_RATE downstream.

### (3) Divergence
- Pivot round: 20
- Missed signal: food-service pod kill, its span absence, direct SLO on its own endpoint.
- Agent saw instead: RabbitMQ DNS baseline noise.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_1862)

## case_1880  [HTTPFault / HTTPResponseReplaceBody]

### (1) What really happened
HTTPResponseReplaceBody on ts-food-service's outbound call to ts-travel-service route `/api/v1/travelservice/routes/*`. food-service received corrupted travel-service responses.

### (2) What the agent did
Rounds 1-24: surveys, noted corrupted response body patterns in food-service logs. Rounds 25-31: picked ts-train-food-service as root with evidence string "train_food_list query spike (118→1380), corrupted response body with token 'lwwqt8'". train-food-service is fabricated — it's not even in the GT pair.

### (3) Divergence
- Pivot round: 25
- Missed signal: the injection route is `travelservice/routes/*`, pointing to food→travel, not food→train-food.
- Agent saw instead: a spike in train_food_list queries that it interpreted as related.
- Proximate cause: **similar-name sibling service hallucinated as root** (case_1880)

## case_1917  [PodChaos / ContainerKill]

### (1) What really happened
Container kill on ts-order-service pod. order-service becomes unavailable.

### (2) What the agent did
Rounds 1-43: surveys across 11 services. Rounds 44-57: anchored on ts-seat-service with HIGH_ERROR_RATE; built chain seat → preserve → security / seat → travel, root=ts-seat-service. order-service absent.

### (3) Divergence
- Pivot round: 30
- Missed signal: order-service pod gap + explicit dependency of preserve → order in the booking path.
- Agent saw instead: seat-service had earliest-error timestamp among visible-error services.
- Proximate cause: **dead-pod silent, earliest-error caller named root**

## case_1934  [PodChaos / PodFailure]

### (1) What really happened
Pod failure on ts-order-service. 78-round investigation, biggest spl (5), 13 services affected.

### (2) What the agent did
Rounds 1-60: extensive surveys; noted ts-seat-service having HIGH_ERROR_RATE + HIGH_LATENCY. Rounds 61-78: built a large graph with seat at top, travel/travel-plan as TIMEOUT downstream, hallucinated route-service + train-service. root=ts-seat-service. order-service absent entirely.

### (3) Divergence
- Pivot round: 35
- Missed signal: order-service pod gap.
- Agent saw instead: seat-service HIGH_ERROR_RATE + HIGH_LATENCY as earliest visible signal.
- Proximate cause: **dead-pod silent, earliest-error caller named root**

## case_1948  [PodChaos / ContainerKill]

### (1) What really happened
Container kill on ts-preserve-service pod. /preserveservice/preserve unavailable.

### (2) What the agent did
Rounds 1-45: surveys. Rounds 46-56: picked ts-ui-dashboard as root with preserve-service as HIGH_LATENCY child; hallucinated ts-order-service as a second downstream node.

### (3) Divergence
- Pivot round: 40
- Missed signal: preserve-service's UNAVAILABLE status and the dead-pod gap.
- Agent saw instead: ui-dashboard had the outward-facing HIGH_ERROR_RATE + HIGH_LATENCY.
- Proximate cause: **outermost error receiver labeled root, dead pod named as child**

## case_2130  [JVMChaos / JVMReturn]

### (1) What really happened
JVMReturn on ts-station-service class `StationApplication.main` (return_type=1, return_value_opt=0 — early-return from main). station-service effectively crashes / returns early from its main application loop; many services that call station-service for station data hang.

### (2) What the agent did
Rounds 1-18: surveys, TIMEOUT patterns across basic/travel/route-plan/travel-plan. Rounds 19-25: built a large graph with ts-route-service (hallucinated) as the top node, basic/travel/route-plan/travel-plan all TIMEOUT, root=ts-route-service. station-service absent.

### (3) Divergence
- Pivot round: 18
- Missed signal: station-service's complete absence of successful spans in the window (it's stuck in main()'s early-return state). Hallucinating ts-route-service in place of ts-station-service suggests agent confused the two.
- Agent saw instead: a general cascade of TIMEOUT across route/basic/travel services.
- Proximate cause: **dead injected service replaced with hallucinated sibling as root**

## case_2211  [PodChaos / ContainerKill]

### (1) What really happened
Container kill on ts-travel-service pod. travel-service unresponsive.

### (2) What the agent did
Rounds 1-35: surveys. Rounds 36-47: picked ts-route-plan-service as root, built chain route-plan → travel-plan → ui-dashboard. travel-service absent (dead pod).

### (3) Divergence
- Pivot round: 30
- Missed signal: travel-service pod gap.
- Agent saw instead: route-plan-service had earliest HIGH_ERROR_RATE + UNAVAILABLE markers because it calls travel-service.
- Proximate cause: **caller-of-dead-pod promoted, dead pod unqueried** (case_2211)

## case_2231  [HTTPFault / HTTPRequestDelay]

### (1) What really happened
HTTPRequestDelay (2297ms) on ts-travel-service's request to ts-route-service at `/api/v1/routeservice/routes/*`. travel-service's route-lookup calls delayed.

### (2) What the agent did
Rounds 1-30: surveys. Rounds 31-38: picked ts-basic-service (hallucinated) as root, placed travel-service as a middle node with HIGH_ERROR_RATE. route-service absent.

### (3) Divergence
- Pivot round: 26
- Missed signal: travel → route-service edge delay is the direct footprint.
- Agent saw instead: a cascade where basic-service happened to be at the top of a fabricated call chain.
- Proximate cause: **injected service kept as middle, fabricated ancestor named root**

## case_2235  [HTTPFault / HTTPRequestReplaceMethod]

### (1) What really happened
HTTP method replacement (POST → PATCH) on ts-travel-service's request to ts-seat-service at `/api/v1/seatservice/seats/left_tickets`. seat-service rejects the malformed PATCH, travel-service errors out.

### (2) What the agent did
Rounds 1-20: surveys, noted travel-service as HIGH_ERROR_RATE. Rounds 21-28: placed basic-service (hallucinated) as top of chain, travel-service as middle, root=basic. seat-service absent entirely.

### (3) Divergence
- Pivot round: 20
- Missed signal: the PATCH method anomaly on travel → seat calls is the direct footprint.
- Agent saw instead: a generic error cascade anchored on a fabricated basic-service top.
- Proximate cause: **fabricated ancestor named root, injected pair unmapped**

## case_2245  [HTTPFault / HTTPResponseReplaceCode]

### (1) What really happened
HTTPResponseReplaceCode (status_code=5) on ts-travel-service's call to ts-basic-service route `/basicservice/basic/travels`. Sprawling travel-path cascade.

### (2) What the agent did
Rounds 1-30: extensive surveys across 10 services. Rounds 31-39: output a 10-node sprawling graph with ts-route-plan-service as root (HIGH_ERROR_RATE + HIGH_LATENCY), travel-service and basic-service both present as children with HIGH_LATENCY. Hallucinated 5 extra services as HIGH_LATENCY nodes.

### (3) Divergence
- Pivot round: 28
- Missed signal: the basic → travel injection-pair is explicit in the route.
- Agent saw instead: route-plan-service had earliest HIGH_ERROR_RATE + HIGH_LATENCY.
- Proximate cause: **earliest-error upstream caller named root, sprawling graph dilutes pair**

## case_2253  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-travel-service class `MyCallable.MyCallable` (constructor). travel-service's async callables hang.

### (2) What the agent did
Rounds 1-30: surveys. Rounds 31-46: picked ts-route-plan-service as root with HIGH_ERROR_RATE; travel-service absent.

### (3) Divergence
- Pivot round: 30
- Missed signal: travel-service's silent under-memory-stress state.
- Agent saw instead: route-plan-service had the heaviest error rate among visible callers of travel-service.
- Proximate cause: **silent-under-stress injected service shadowed by heaviest-error callers**

## case_2258  [PodChaos / ContainerKill]

### (1) What really happened
Container kill on ts-travel2-service pod.

### (2) What the agent did
Rounds 1-30: surveys. Rounds 31-40: picked ts-route-plan-service as root + UNAVAILABLE, travel2 absent.

### (3) Divergence
- Pivot round: 28
- Missed signal: travel2-service pod kill with span absence.
- Agent saw instead: route-plan-service's UNAVAILABLE status (caused by inability to call travel2).
- Proximate cause: **caller-of-dead-pod promoted, dead pod unqueried** (case_2258)

## case_2390  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVM memory stress on ts-user-service class `InitUser.run`. User-init hangs; userservice/users/id/{userId} p99 0.04→20s.

### (2) What the agent did
Rounds 1-18: surveys, focused on ts-ui-dashboard 503 errors. Rounds 19-21: minimal 2-node graph ui-dashboard → loadgen, root=ts-ui-dashboard. user-service absent.

### (3) Divergence
- Pivot round: 12
- Missed signal: SLO is explicitly on userservice/*; user-service's init is the injected method.
- Agent saw instead: ui-dashboard's 503 on its own endpoint.
- Proximate cause: **dead-pod silence read as health, front-end 503 claimed as root**

## case_2489  [NetworkChaos / NetworkBandwidth]

### (1) What really happened
Network bandwidth limit on ts-consign-service → ts-ui-dashboard response link (direction=to, rate=723212, limit=1785). consign responses throttled.

### (2) What the agent did
Rounds 1-13: surveys. Rounds 14-19: picked ts-food-service as root, labeled ts-consign-service explicitly as "HEALTHY" in the final graph despite its being the GT. Hallucinated 5 other services.

### (3) Divergence
- Pivot round: 12
- Missed signal: consign → ui-dashboard bandwidth throttling; consign's outbound spans show reduced byte throughput.
- Agent saw instead: food-service had heavier visible errors and labeled consign as HEALTHY.
- Proximate cause: **injected service explicitly dismissed as healthy, baseline-noise service named root**

## case_2512  [NetworkChaos / NetworkCorrupt]

### (1) What really happened
Network corruption (corrupt=95, direction=from) on ts-food-service → ts-station-food-service. food-service's outbound packets 95% corrupted.

### (2) What the agent did
Rounds 1-15: surveys. Rounds 16-20: RabbitMQ DNS anchor. Final: 6-node graph with rabbitmq UNAVAILABLE at top, food-service HIGH_ERROR_RATE downstream. station-food-service absent.

### (3) Divergence
- Pivot round: 14
- Missed signal: food → station-food network corruption; the corrupt outbound spans.
- Agent saw instead: RabbitMQ DNS baseline noise.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_2512)

## case_2585  [PodChaos / ContainerKill]

### (1) Reality
Container kill on ts-preserve-service. preserve unresponsive.

### (2) Agent
36 rounds; picked ts-order-service as root, preserve-service matched as cascade node.

### (3) Divergence
- Pivot round: ~25
- Proximate cause: **order caller named root, dead pod retained as child**

## case_2641  [HTTPFault / HTTPResponseDelay]

### (1) Reality
HTTPResponseDelay (4418ms) on ts-route-plan-service → ts-travel-service at `/travelservice/trip_detail`.

### (2) Agent
34 rounds; hallucinated 4 services (basic/train/travel/travel2). Placed ts-train-service at top of chain. route-plan-service matched but not root.

### (3) Divergence
- Pivot round: ~22
- Proximate cause: **fabricated train-service ancestor named root, injection pair unmapped**

## case_2647  [HTTPFault / HTTPResponsePatchBody]

### (1) Reality
HTTPResponsePatchBody on ts-route-plan-service → ts-travel2-service `/travel2service/trips/left`.

### (2) Agent
35 rounds; picked ts-travel-service (hallucinated, not in GT pair) as root. route-plan-service matched but not root.

### (3) Divergence
- Pivot round: ~24
- Proximate cause: **hallucinated sibling named root, injection pair unmapped**

## case_2678  [NetworkChaos / NetworkBandwidth]

### (1) Reality
NetworkBandwidth (rate=827703, limit=262) on ts-seat-service → ts-config-service.

### (2) Agent
21 rounds; picked ts-travel2-service as root with heavy TIMEOUT. Missed seat + config + travel-service + preserve.

### (3) Divergence
- Pivot round: ~15
- Proximate cause: **earliest-timeout downstream chosen, infra pair skipped**

## case_2694  [HTTPFault / HTTPResponseDelay]

### (1) Reality
HTTPResponseDelay (2361ms) on ts-seat-service → ts-config-service at `/configservice/configs/DirectTicketAllocationProportion`.

### (2) Agent
27 rounds; built 8-node graph with ts-order-service + ts-order-other-service at top (both hallucinated in that role) marked UNAVAILABLE. seat-service matched as CONNECTION_RESET node but not root.

### (3) Divergence
- Pivot round: ~20
- Proximate cause: **hallucinated upstream pair named root, seat→config edge unmapped**

## case_2697  [JVMChaos / JVMMemoryStress]

### (1) Reality
JVM memory stress on ts-seat-service class `SeatApplication.restTemplate`.

### (2) Agent
56 rounds; picked ts-food-service as root (not explicitly rabbitmq, but same cascade pattern with delivery/notification hallucinated). seat-service absent.

### (3) Divergence
- Pivot round: ~25
- Proximate cause: **noisy food/delivery cascade hallucinated, silent seat unqueried**

## case_2715  [NetworkChaos / NetworkBandwidth]

### (1) Reality
NetworkBandwidth (rate=168909, limit=138) on ts-station-service → ts-basic-service.

### (2) Agent
22 rounds; picked ts-travel-service as root. station + basic missed.

### (3) Divergence
- Pivot round: ~15
- Proximate cause: **noisy caller chain anchored, infra bandwidth pair skipped**

## case_2716  [NetworkChaos / NetworkCorrupt]

### (1) Reality
Network corruption (corrupt=52, direction=to) on ts-station-service → ts-basic-service.

### (2) Agent
28 rounds; RabbitMQ DNS anchor with 11-node sprawl. station-service missed.

### (3) Divergence
- Pivot round: ~18
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_2716)

## case_2808  [JVMChaos / JVMMemoryStress]

### (1) Reality
JVM memory stress on ts-travel-service class `TravelController.retrieve`.

### (2) Agent
35 rounds; picked ts-route-plan-service as root. travel missing.

### (3) Divergence
- Pivot round: ~24
- Proximate cause: **caller anchored, silent-under-stress injected service unqueried**

## case_2988  [JVMChaos / JVMCPUStress]

### (1) Reality
JVM CPU stress (cpu_count=5) on ts-basic-service class `BasicController.queryForStationId`. Basic becomes CPU-bound; callers hang waiting for station lookups.

### (2) Agent
20 rounds; picked ts-rabbitmq as root with 12-node sprawl. basic-service absent.

### (3) Divergence
- Pivot round: ~15
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_2988)

## case_3033  [HTTPFault / HTTPResponseReplaceCode]

### (1) Reality
HTTPResponseReplaceCode (status_code=6) on ts-food-service → ts-train-food-service at `/trainfoodservice/trainfoods/*`.

### (2) Agent
57 rounds; picked ts-station-food-service as root (hallucinated — station-food is a sibling variant to train-food). train-food-service not in graph.

### (3) Divergence
- Pivot round: ~30
- Proximate cause: **similar-name sibling (station-food) hallucinated, train-food missed**

## case_3035  [JVMChaos / JVMMemoryStress]

### (1) Reality
JVM memory stress on ts-food-service class `FoodServiceImpl.deleteFoodOrder`.

### (2) Agent
29 rounds; picked mysql as root with food-service as HIGH_ERROR_RATE downstream; hallucinated 4 services including rabbitmq UNAVAILABLE.

### (3) Divergence
- Pivot round: ~20
- Proximate cause: **JVM memory symptom misread as DB pool exhaustion** (case_3035)

## case_3040  [PodChaos / ContainerKill]
GT: ts-order-other-service. Agent: 35 rounds, picked a matched caller (seat/preserve chain) as root. order-other missing. Pivot ~20.
- Proximate cause: **dead-pod silence, earliest-error caller named root** (case_3040)

## case_3041  [NetworkChaos / NetworkDelay]
GT: ts-order-other-service + ts-seat-service. Agent: 19 rounds, rabbitmq sprawl. Missed order-other + seat + security.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_3041)

## case_3050  [JVMChaos / JVMMemoryStress]
GT: ts-order-other-service. Agent: 51 rounds, order-other matched as node, but also hallucinated food/delivery/notification/order — picked one of them as root. Baseline-noise cascade.
- Proximate cause: **baseline-noise cascade hallucinated as root, injected service kept as child**

## case_3053  [JVMChaos / JVMMemoryStress]
GT: ts-order-other-service. Agent: 40 rounds, picked ts-seat-service as root; order-other missed.
- Proximate cause: **silent-under-stress injected service shadowed by heaviest-error callers** (case_3053)

## case_3076  [NetworkChaos / NetworkPartition]
GT: ts-order-service + ts-ui-dashboard. Agent: 35 rounds, rabbitmq sprawl, order-service matched as node but rabbitmq named root.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_3076)

## case_3114  [PodChaos / PodKill]
GT: ts-preserve-service. Agent: 40 rounds, rabbitmq as root, preserve matched as child.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_3114)

## case_3128  [HTTPFault / HTTPResponseDelay]
GT: ts-preserve-service + ts-security-service. Agent: 33 rounds, picked ts-order-service (hallucinated) as HIGH_ERROR_RATE+HIGH_CPU root. preserve matched but not root.
- Proximate cause: **hallucinated caller named root, injection pair left as cascade**

## case_3159  [HTTPFault / HTTPRequestDelay]
GT: ts-route-plan-service + ts-travel-service. Agent: 31 rounds, picked ts-route-service (hallucinated — confused with route-plan) as root.
- Proximate cause: **similar-name sibling (route-service) hallucinated, injection pair unmapped**

## case_3222  [NetworkChaos / NetworkLoss]
GT: ts-seat-service + ts-order-other-service. Agent: 19 rounds, picked ts-travel2-service. Missed travel-service; seat-service matched as cascade node.
- Proximate cause: **caller chain anchored, network-loss pair unqueried**

## case_3324  [PodChaos / ContainerKill]
GT: ts-travel-service. Agent: 82 rounds (longest so far!), picked ts-route-plan-service as root. travel-service missing (dead pod).
- Proximate cause: **caller-of-dead-pod promoted, dead pod unqueried** (case_3324)

## case_3391  [HTTPFault / HTTPResponseDelay]
GT: ts-travel2-service + ts-route-service. Agent: 42 rounds, picked ts-basic-service as root (hallucinated, HIGH_CPU+HIGH_LATENCY). travel2 matched but not root.
- Proximate cause: **hallucinated ancestor named root, injection pair left as cascade**

## case_3555  [HTTPFault / HTTPResponseDelay]
GT: ts-travel-service + ts-basic-service. Agent: 50 rounds, rabbitmq-family sprawl with travel-service matched but not root.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_3555)

## case_3622  [NetworkChaos / NetworkDelay]
GT: mysql + ts-order-service. Agent 27r, rabbitmq root, missed 9 services including order.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_3622)

## case_3700  [JVMChaos / JVMMemoryStress]
GT: ts-config-service. Agent 43r, ts-seat-service root (hallucinated via cascade). config missing.
- Proximate cause: **noisiest cascade node anchored, shared-dependency missed** (case_3700)

## case_3716  [JVMChaos / JVMMemoryStress]
GT: ts-food-service. Agent 33r, rabbitmq root. food matched but not root.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_3716)

## case_3760  [JVMChaos / JVMMemoryStress]
GT: ts-price-service. Agent 46r, ts-basic-service root. price missing (price is callee of basic, silent under stress).
- Proximate cause: **noisy caller anchored, silent callee (price) unqueried**

## case_3776  [PodChaos / PodFailure]
GT: ts-seat-service. Agent 54r, ts-travel2-service root. seat missing (dead pod).
- Proximate cause: **caller-of-dead-pod promoted, dead pod unqueried** (case_3776)

## case_3868  [JVMChaos / JVMLatency]
GT: ts-config-service. Agent 54r, ts-order-service (hallucinated) as root. config missing.
- Proximate cause: **hallucinated caller named root, silent shared-dependency missed**

## case_3920  [JVMChaos / JVMMemoryStress]
GT: ts-payment-service. Agent 33r, ts-inside-payment-service (similar name) as root; payment also matched but not as primary root.
- Proximate cause: **similar-name service confused, wrong variant named root** (case_3920)

## case_3966  [PodChaos / ContainerKill]
GT: ts-train-food-service. Agent 28r, rabbitmq root; train-food missing.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_3966)

## case_4054  [PodChaos / ContainerKill]
GT: ts-consign-price-service. Agent 27r, rabbitmq root; consign-price missing (consign matched, but consign ≠ consign-price).
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_4054)

## case_4055  [JVMChaos / JVMMemoryStress]
GT: ts-consign-price-service. Agent 34r, ts-consign-service (similar name) as root. consign-price missing.
- Proximate cause: **similar-name service confused, wrong variant named root** (case_4055)

## case_4081  [PodChaos / ContainerKill]
GT: ts-order-other-service. Agent 29r, ts-seat-service root; order-other missing (dead pod).
- Proximate cause: **dead-pod silence, earliest-error caller named root** (case_4081)

## case_4229  [NetworkChaos / NetworkPartition]
GT: ts-basic-service + ts-travel-service. Agent 36r, rabbitmq UNAVAILABLE+DNS_ERROR root. matched=[] — agent output contains none of the actually-affected services.
- Proximate cause: **RabbitMQ DNS noise hallucinated, entire cascade hallucinated** (case_4229, extreme variant)

## case_4258  [PodChaos / ContainerKill]
GT: ts-contacts-service. Agent 28r, ts-order-service (hallucinated) as root; contacts matched but not root.
- Proximate cause: **order caller named root, dead pod retained as child** (case_4258)

## case_4353  [JVMChaos / JVMMemoryStress]
GT: ts-station-service. Agent 62r, ts-basic-service root + UNAVAILABLE; station missing.
- Proximate cause: **noisy caller anchored, silent-under-stress station unqueried**

## case_4363  [JVMChaos / JVMMemoryStress]
GT: ts-train-food-service. Agent 31r, ts-food-service root; train-food missing. T1 + similar-name adjacency.
- Proximate cause: **noisy caller (food) anchored, silent callee (train-food) unqueried**

## case_4375  [PodChaos / ContainerKill]
GT: ts-travel2-service. Agent 33r, ts-route-plan-service root; travel2 missing (dead pod).
- Proximate cause: **caller-of-dead-pod promoted, dead pod unqueried** (case_4375)

## case_4423  [NetworkChaos / NetworkBandwidth]
GT: ts-basic-service + ts-preserve-service. Agent 51r, ts-ui-dashboard root with only ui matched; hallucinated delivery/food/notification. Extreme miss.
- Proximate cause: **outermost error receiver named root, infra bandwidth pair unqueried**

## case_4463  [PodChaos / ContainerKill — GT metadata mismatch]
GT declares ts-config-service but injection_name is `ts-food-service-container-kill`. Agent's root=ts-food-service with UNAVAILABLE — matches the injection name, not the GT label. Likely dataset-side GT mislabeling. Judge marked as failure because of config vs food service mismatch.
- Proximate cause: **dataset GT/injection name mismatch, agent followed injection footprint**

## case_4510  [NetworkChaos / NetworkBandwidth]
GT: ts-route-plan-service + ts-travel-service. Agent 42r, ts-travel-plan-service UNAVAILABLE as root; route-plan missing.
- Proximate cause: **downstream UNAVAILABLE named root, route-plan→travel pair unqueried**

## case_4517  [HTTPFault / HTTPResponseReplaceCode]
GT: ts-route-plan-service + ts-travel2-service. Agent 45r, ts-route-service (hallucinated, similar name) as root.
- Proximate cause: **similar-name sibling (route-service) hallucinated, injection pair unmapped**

## case_4789  [JVMChaos / JVMMemoryStress]
GT: ts-station-service. Agent 43r, ts-basic-service root; station missing.
- Proximate cause: **noisy caller (basic) anchored, silent-under-stress station unqueried**

## case_4791  [PodChaos / ContainerKill]
GT: ts-assurance-service. Agent 45r, rabbitmq + 10 hallucinated services (admin-basic-info, admin-route, delivery, food, notification, order, payment, rebook, travel-plan, rabbitmq); assurance matched as cascade node.
- Proximate cause: **RabbitMQ DNS noise hallucinated, extreme graph inflation** (case_4791)

## case_4823  [PodChaos / PodFailure]
GT: ts-preserve-service. Agent 26r, rabbitmq root; preserve matched as child.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_4823)

## case_4832  [JVMChaos / JVMMemoryStress]
GT: ts-consign-service. Agent 82r (longest in dataset), mysql root; consign matched as child but not root.
- Proximate cause: **JVM memory symptom misread as DB pool exhaustion** (case_4832)


## case_1686  [JVMChaos / JVMMemoryStress]  (rerun 2026-04-17)

### (1) What really happened
JVM memory stress on ts-user-service class `UserServiceImpl.getServiceUrl`. /userservice/users/id/{userId} p99 0.04→20s. user-service's URL-lookup method hangs under memory pressure; callers stall.

### (2) What the agent did
45 rounds. Picked up RabbitMQ DNS errors in delivery/notification/food as anchor. Emitted a 6-node graph with ts-rabbitmq UNAVAILABLE+DNS_ERROR at top, food → preserve → ui-dashboard chain. ts-user-service entirely absent.

### (3) Divergence
- Pivot round: ~18
- Missed signal: SLO explicitly on `/userservice/*`; user-service's own endpoint is the direct footprint. RabbitMQ errors are baseline noise.
- Agent saw instead: the recurring RabbitMQ DNS cluster.
- Proximate cause: **RabbitMQ DNS noise hallucinated as root infra failure** (case_1686 rerun)

## case_1875  [HTTPFault / HTTPResponseAbort]  (rerun 2026-04-17)

### (1) What really happened
HTTPResponseAbort on ts-food-service's outbound call to ts-travel-service at `/api/v1/travelservice/routes/*`. food-service's travel lookups abort; /foodservice/foods/... avg 0.03→7.42s, success 1.00→0.63.

### (2) What the agent did
18 rounds. Picked ts-station-food-service (a close-named sibling of food/train-food) as root, marked it UNAVAILABLE. travel-service missing from graph; hallucinated delivery + notification + station-food.

### (3) Divergence
- Pivot round: ~12
- Missed signal: the injection route is `travelservice/routes/*`; travel-service should be the callee-half of the GT pair.
- Agent saw instead: station-food-service's baseline errors plus food/station-food naming adjacency.
- Proximate cause: **similar-name sibling (station-food) hallucinated, travel pair missed** (case_1875 rerun)

## case_1886  [PodChaos / ContainerKill]  (rerun 2026-04-17)

### (1) What really happened
Container kill on ts-inside-payment-service pod. /inside_pay_service/inside_payment avg 0.13→3.53s, success 1.00→0.72. inside-payment unavailable 4 minutes.

### (2) What the agent did
39 rounds. Correctly identified ts-inside-payment-service as UNAVAILABLE and placed it in the graph. BUT then attached it downstream of ts-ui-dashboard and named ts-ui-dashboard as the root cause. 7-node sprawl with ui-dashboard at top fanning out to inside-payment, cancel, verification-code, notification, order, seat. Hallucinated 4 extra services.

### (3) Divergence
- Pivot round: ~28
- Missed signal: UNAVAILABLE downstream + 72% success rate on its own endpoint is the direct root-cause signature; ui-dashboard is merely the ingress that surfaces the error.
- Agent saw instead: ui-dashboard's 503s on inside-payment endpoint plus a broader cascade.
- Proximate cause: **correct node identified, outermost error receiver labeled root** (case_1886 rerun)
