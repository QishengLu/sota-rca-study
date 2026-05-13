# Per-Case Failure Analysis — thinkdepthai-qwen3.5-plus

Batch 1: 20 labeled cases + 3 unlabeled from original sample. 3-block format (no section 4).

---

## case_339  [JVMChaos / JVMMySQLLatency]

### (1) What really happened
A JVMMySQLLatency fault injected 3669ms latency on SELECT queries against the `trip` table in `ts-travel-service`. This caused `TripRepository.findAll`, `TripRepository.findByRouteId`, and related SELECT spans within ts-travel-service to become extremely slow. The latency propagated upward through the call chain: ts-travel-service → ts-route-plan-service → ts-travel-plan-service → ts-ui-dashboard, causing SLO violations on the `/travelPlan/minStation` and `/travelPlan/cheapest` endpoints. The `conclusion.csv` footprint shows `ts-travel-service` spans with `high_avg_latency` and `high_p99_latency` states, and the anomalous metrics confirm `ts-travel-service` had `container.filesystem.usage` spike (466KB→3MB) and `jvm.class.loaded` increase — consistent with stress from the injected DB latency.

### (2) What the agent did
The agent spent 52 rounds. At round 18, it ranked services by average span duration and saw ts-travel-plan-service (249ms) and ts-route-plan-service (228ms) at the top, while ts-travel-service appeared at only 42ms avg — the injection's effect was diluted across all ts-travel-service spans. At round 27, the agent found the smoking gun: `ts-travel-service` had the highest max `db.client.connections.use_time` at 6888ms, far above all other services. However, instead of drilling into ts-travel-service's internal DB query spans, the agent pivoted to checking whether ts-train-service was the root cause (red herring). By round 46, the agent was tracing individual call chains and concluded ts-route-plan-service was the root cause because it sat between the high-latency upstream and the low-latency downstream — a classic "stopped one hop short" error.

### (3) Divergence
- **Pivot round**: 27
- **What agent should have observed**: The 6888ms max `db.client.connections.use_time` for ts-travel-service was the largest DB latency signal across all services. Following this with a span-level query filtered to ts-travel-service (e.g. `WHERE service_name = 'ts-travel-service' AND span_name LIKE '%Trip%' ORDER BY duration DESC`) would have revealed multi-second SELECT Trip/TripRepository spans — directly pointing at the MySQL injection.
- **What agent observed instead**: The agent noted the 6888ms metric but immediately pivoted to the trace-level call chain analysis (round 27 think_tool). It compared service-level averages (42ms for ts-travel-service vs 228ms for ts-route-plan-service) and concluded ts-route-plan-service was the bottleneck — not recognizing that ts-travel-service's low average was an artifact of dilution across many fast non-trip spans.
- **Proximate cause**: dismissed DB latency signal for low-average service

---

## case_832  [JVMChaos / JVMReturn]

### (1) What really happened
A JVMReturn injection targeted `ts-travel-plan-service.TravelPlanServiceImpl.getServiceUrl()`, making the method return an invalid URL. This corrupted ts-travel-plan-service's ability to construct outbound HTTP requests to any downstream service. Every call to ts-route-plan-service, ts-travel-service, etc. failed with `java.lang.IllegalArgumentException: URI is not absolute`. The span footprint confirms: all 3 travelplanservice endpoints dropped from 100% success to 0-14% with ~20s latency (timeouts), and ts-travel-plan-service produced 1940 ERROR logs during the abnormal period (vs 0 normally). No downstream service had any abnormal telemetry because none were ever called.

### (2) What the agent did
Over 36 rounds, the agent discovered the "URI is not absolute" error in ts-travel-plan-service logs early (around round 8-12). By round 22, the agent compared normal vs abnormal traces and noticed ts-route-plan-service was completely absent from abnormal traces. The agent concluded: "ts-route-plan-service is completely missing from the traces — this is the root cause." It interpreted the missing telemetry as ts-route-plan-service being UNAVAILABLE, causing ts-travel-plan-service to fail. The remaining 14 rounds were spent confirming this hypothesis (checking k8s metrics, deployment status — which showed the deployment was actually up). The agent never revisited whether the error originated INSIDE ts-travel-plan-service itself.

### (3) Divergence
- **Pivot round**: 22
- **What agent should have observed**: The "URI is not absolute" exception occurs IN ts-travel-plan-service and is a java.lang.IllegalArgumentException — this is a local code error (malformed URL construction), not a network/connectivity error. If ts-route-plan-service were truly down, the error would be a connection timeout or connection refused, not an invalid URI. Furthermore, the k8s deployment showed ts-route-plan-service was actually running (available=1). The correct interpretation: ts-travel-plan-service's URL construction logic (getServiceUrl) was corrupted, so it never sent any request outward — explaining why downstream telemetry was absent.
- **What agent observed instead**: Saw missing traces for ts-route-plan-service and treated absence-of-telemetry as evidence-of-absence (the service being down), reversing the actual causality chain.
- **Proximate cause**: reversed caller-callee causality

---

## case_2988  [JVMChaos / JVMCPUStress]

### (1) What really happened
A JVMCPUStress injection targeted `ts-basic-service.BasicController.queryForStationId()`, spawning 5 CPU-intensive threads. This caused ts-basic-service's CPU to spike 20x (k8s.pod.cpu.usage: 0.24→4.58, jvm.cpu.time: 13.86→280.78). The `queryForStationId` method is called by `queryForTravel` and `queryForTravels`, which are the core endpoints called by ts-travel2-service, ts-travel-service, ts-route-plan-service, etc. The CPU starvation made these endpoints slow, propagating high latency up the call chain: ts-basic-service → ts-travel2-service → ts-route-plan-service → ts-travel-plan-service → ts-ui-dashboard. Span-level footprint shows BasicController.queryForTravel and BasicController.queryForTravels both had `injection_affected`, `high_avg_latency`, and `high_p99_latency` states.

### (2) What the agent did
Over 55 rounds, the agent traced the call chain and found slow DB queries in ts-route-service (RouteRepository.findByIds taking 3.65s). At round ~40, the agent queried CPU/memory metrics: `SELECT service_name, metric, AVG(value), MAX(value) FROM abnormal_metrics WHERE metric LIKE '%cpu%' OR metric LIKE '%memory%' ORDER BY max_value DESC LIMIT 30`. This returned memory metrics (GB-scale values) in all 30 slots; CPU metrics (sub-1.0 values for most services, ~4.58 for ts-basic-service) were never seen. The agent concluded at round 53: "the root cause is ts-route-service which has the slowest database queries." It correctly identified ts-basic-service was in the call chain but placed the root cause one hop deeper at ts-route-service, never having seen ts-basic-service's CPU anomaly.

### (3) Divergence
- **Pivot round**: 40 (the CPU/memory metric query that failed to surface the anomaly)
- **What agent should have observed**: A per-service CPU metric query (e.g. `WHERE metric LIKE '%cpu%' AND service_name = 'ts-basic-service'` or normalizing metrics before comparison) would have shown ts-basic-service CPU at 20x normal. The anomalous metrics table in the GT shows z-scores of 141 (jvm.cpu.time) and 38 (k8s.pod.cpu.usage) for ts-basic-service — the largest CPU z-scores of any service. Combining the CPU spike with the fact that ts-basic-service sits at the bottom of the call chain would identify it as the root cause.
- **What agent observed instead**: A single mixed-metric query where memory values (billions) dominated CPU values (fractions), effectively filtering out the CPU signal. The agent then focused on trace-level latency, found ts-route-service DB queries were slow (3.65s), and blamed ts-route-service — not recognizing that ts-route-service's DB queries might have been slow due to shared MySQL contention caused by ts-basic-service's CPU stress.
- **Proximate cause**: heterogeneous metric query buried CPU signal

---

## case_33  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress injection on `ts-auth-service.JWTProvider.init` (mem_type=2). The injection caused extreme JVM class-loading churn (`jvm.class.loaded`: 1.25→6593, z=5238), memory page faults (z=872M), and GC pressure leading to container restarts. The login endpoint (`POST /api/v1/users/login`) degraded from 122ms→672ms avg with timeouts. Container flagged `high_memory, high_cpu, restarting`; pod showed `high_gc_pressure`.

### (2) What the agent did
Over 60 rounds, the agent anchored on `ts-rabbitmq` at round 7 after seeing `UnknownHostException: ts-rabbitmq` in ts-food-service logs. This RabbitMQ DNS error is a pre-existing background condition (appears in both normal and abnormal periods). The agent spent 53 rounds trying to link RabbitMQ to the login endpoint failures. At round 40, it queried ts-auth-service container memory and found extreme max values (2.6GB RSS spike) but dismissed them because the average appeared normal. It never queried `jvm.class.loaded` or `jvm.gc` for ts-auth-service.

### (3) Divergence
- **Pivot round**: 7
- **What agent should have observed**: ts-auth-service `jvm.class.loaded` at z=5238 and `k8s.pod.memory.major_page_faults` at z=872M — the canonical JVMMemoryStress fingerprint. Round 40's memory spike data should have triggered a JVM-level drill-down.
- **What agent observed instead**: Anchored on a memorable error string ("UnknownHostException: ts-rabbitmq") from an unrelated service (ts-food-service), never connecting it to the failing login endpoint.
- **Proximate cause**: anchored on pre-existing background error

---

## case_156  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress injection on `ts-order-service.OrderController.saveOrderInfo` (mem_type=2). The injection caused `jvm.thread.count` to explode from 6.3→1618 (z=302), `jvm.class.loaded` from 1→6582, and memory page faults rose 44x. Container flagged `high_cpu, high_memory, high_gc_pressure`. Multiple ts-order-service spans went `missing_span` + `injection_affected` — the service was restarting under OOM pressure and couldn't emit telemetry.

### (2) What the agent did
Over 48 rounds, the agent focused on trace error counts. ts-seat-service had 168 error spans (the most visible), while ts-order-service spans were missing (not counted as errors). The agent concluded at round 39: "ts-seat-service is the deepest service in the chain with errors, therefore root cause." It saw ts-order-service's "Order already exist" errors at round 7 but dismissed them as "cascading side-effects." It never queried JVM or memory metrics for ts-order-service.

### (3) Divergence
- **Pivot round**: 39
- **What agent should have observed**: ts-order-service's spans were *missing* (not slow but absent) — the hallmark of JVMMemoryStress causing OOM thread stalls. `POST /api/v1/orderservice/order/refresh` had 32x latency ratio. JVM metrics showed the highest anomaly z-scores.
- **What agent observed instead**: Counted visible error spans; ts-seat-service had the most, so it became the root cause. Missing spans from ts-order-service were interpreted as "no problems" rather than "service unable to emit telemetry."
- **Proximate cause**: survivorship bias on visible error spans

---

## case_247  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress injection on `ts-route-service.RouteController.queryById`. Container flagged `high_cpu, high_memory, high_gc_pressure`. `jvm.class.loaded` jumped from 0.5→4996 (z=8652). ts-route-service lost 13,319 spans (largest absolute drop of any service) and its GET endpoint went from 26.67ms→633.9ms avg with `missing_span, injection_affected`.

### (2) What the agent did
Over 64 rounds, the agent noticed ts-basic-service had 11 HTTP 500 errors and "Connection refused" logs (SEVERE). At round 36, it correctly observed that traces for `/api/v1/routeservice/routes` contained only ts-ui-dashboard (ts-route-service produced no child spans). But instead of investigating why ts-route-service was silent, it pivoted to a different trace from the preserve booking flow and found ts-basic-service errors. By round 64, it committed to ts-basic-service as root cause.

### (3) Divergence
- **Pivot round**: 40
- **What agent should have observed**: ts-route-service's span count dropped by 13,319 — the largest drop of any service. Its `jvm.class.loaded` z=8652 was the single largest anomaly. The "Connection refused" in ts-basic-service was a *downstream symptom* of ts-route-service being unresponsive.
- **What agent observed instead**: Found ts-basic-service's "503 / Connection refused" logs and treated the downstream victim as the perpetrator. Never queried ts-route-service memory/JVM metrics.
- **Proximate cause**: blamed downstream victim of silent upstream

---

## case_807  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress injection on `ts-train-service.TrainType` constructor. Container flagged `high_memory, restarting, high_gc_pressure`. `jvm.class.loaded` jumped from 0.5→6529 (z=11308), `k8s.pod.memory.major_page_faults` from 0→0.91. ts-train-service GET endpoint showed `missing_span, high_p99_latency, injection_affected` — spans disappeared during the fault window due to container restart.

### (2) What the agent did
Over 53 rounds, the agent found ts-basic-service's "503 / Connection refused" SEVERE log at round 25 and correctly asked: "what service is ts-basic-service trying to connect to?" It identified that ts-basic-service calls ts-train-service (round 53 think). But then rationalized: "since we don't see errors from ts-train-service, ts-basic-service must be the root cause." The agent never queried ts-train-service JVM/memory metrics.

### (3) Divergence
- **Pivot round**: 25
- **What agent should have observed**: ts-train-service `jvm.class.loaded` z=11308 and `k8s.pod.memory.major_page_faults` 0→0.91 — the clearest JVM memory stress signals in the dataset. Missing spans from ts-train-service indicated container restart, not health.
- **What agent observed instead**: Treated missing telemetry as "no errors" rather than "service restarting and unable to emit telemetry." Anchored on ts-basic-service's SEVERE log noise.
- **Proximate cause**: missing telemetry read as health

---

## case_1394  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress injection on `ts-seat-service.SeatController.getLeftTicketOfInterval`. Container flagged `high_cpu, restarting, high_gc_pressure, high_memory`. `jvm.class.loaded` z=2390, `jvm.gc.duration` z=205 — the strongest JVM signals in the dataset for this case. The injection caused intermittent "Connection refused" errors when callers hit the restarting pod.

### (2) What the agent did
Over 60 rounds, the agent focused on ts-travel-service and ts-travel2-service which showed HTTP 500/503 error spans. At round 37-38, it discovered the call graph ts-travel-service → ts-seat-service (1228 normal calls, 555 abnormal) and queried ts-seat-service HTTP status — found 200s. Concluded ts-seat-service is "working" and locked onto ts-travel-service as root cause. Never queried ts-seat-service JVM metrics.

### (3) Divergence
- **Pivot round**: 38
- **What agent should have observed**: ts-seat-service was intermittently restarting — some calls hit a healthy pod (returning 200), others hit a crashed/restarting pod (Connection refused). `jvm.class.loaded` z=2390 and `jvm.gc.duration` z=205 directly pointed at ts-seat-service. The "Connection refused" errors in ts-travel-service were downstream symptoms.
- **What agent observed instead**: Found ts-seat-service returning 200 on some calls and concluded it was healthy, not recognizing that intermittent restarts produce mixed success/failure patterns.
- **Proximate cause**: intermittent health mistaken for full health

---

## case_2130  [JVMChaos / JVMReturn]

### (1) What really happened
JVMReturn injection on `ts-station-service.StationApplication.main`, forcing early return. This caused ts-station-service's `GET /api/v1/stationservice/stations/id/{stationNameForId}` to show `injection_affected, high_avg_latency, high_p99_latency`. Pod flagged `high_http_latency, high_cpu, high_gc_pressure`. `container.filesystem.usage` z-score astronomically high (2.5e15). The latency propagated through ts-basic-service → upstream services.

### (2) What the agent did
Over 52 rounds, at round 13 the agent examined a single error trace and found ts-route-service's `SELECT route` taking 106 seconds. It immediately formed the hypothesis that ts-route-service was the root cause and never revised it. At round 17, ts-station-service's `db.client.connections.use_time` appeared in results but the agent didn't investigate further.

### (3) Divergence
- **Pivot round**: 13
- **What agent should have observed**: The GT propagation chain was `ts-station-service → ts-basic-service → upstream`. ts-station-service spans carried `injection_affected` tags. Its filesystem z-score was orders of magnitude above all other services. The 106s ts-route-service query was a downstream cascade, not the origin.
- **What agent observed instead**: Anchored on the highest raw latency span in one trace (ts-route-service 106s DB query) without testing if it was a cascade from ts-station-service upstream.
- **Proximate cause**: anchored on single highest-latency span

---

## case_2390  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress injection on `ts-user-service.InitUser.run`. Container flagged `high_memory, high_cpu`. Metrics show `jvm.gc.duration` z=1.27B, `jvm.cpu.recent_utilization` z=1053, `k8s.pod.memory.page_faults` z=310, `container.filesystem.usage` z=207M — all pointing exclusively at ts-user-service. The `GET /api/v1/userservice/users/id/{userId}` endpoint went from 10ms→514ms avg with `missing_span, injection_affected`.

### (2) What the agent did
Over 48 rounds, the agent anchored on `ts-rabbitmq` at round 37 after finding "UnknownHostException: ts-rabbitmq" in ts-food-service logs. At round 41, it noted "ts-user-service metrics look healthy" and the userservice endpoint failure "might be separate" — but dismissed this doubt. RabbitMQ DNS errors appear in normal-period logs too (background condition). The agent never queried ts-user-service JVM or memory metrics.

### (3) Divergence
- **Pivot round**: 37
- **What agent should have observed**: ts-user-service had the most extreme z-score anomalies in the entire dataset: `jvm.gc.duration` z=1.27B, `jvm.cpu.recent_utilization` z=1053. A single JVM metric query for ts-user-service would have been conclusive.
- **What agent observed instead**: Anchored on textually prominent "UnknownHostException: ts-rabbitmq" from an unrelated service. Explicitly noted ts-user-service might be a separate issue but chose to subsume it under the RabbitMQ narrative.
- **Proximate cause**: anchored on pre-existing background error

---

## case_2988  [JVMChaos / JVMCPUStress]

*(already analyzed above)*

---

## case_755  [NetworkChaos / NetworkPartition]

### (1) What really happened
NetworkPartition between ts-seat-service → ts-travel2-service (direction=to). This caused ts-seat-service's `POST /api/v1/seatservice/seats/left_tickets` to show `timeout, injection_affected, high_avg_latency, high_p99_latency`. ts-travel2-service spans also carried `injection_affected`. The partition caused ts-seat-service to timeout when calling ts-travel2-service, propagating latency up through ts-travel-plan-service.

### (2) What the agent did
Over 47 rounds, the agent converged on ts-travel-plan-service around round 13 after seeing it had the highest client-side latency (max 86s). At round 24-30, it traced a specific span with 85.45s in ts-travel-plan-service whose only child was ts-seat-service at 17.7ms — a massive unexplained gap. The agent rationalized the gap as "network latency" or "connection pool exhaustion" rather than recognizing ts-seat-service as the degraded component. It never drilled into ts-seat-service's abnormal vs normal duration comparison.

### (3) Divergence
- **Pivot round**: 13
- **What agent should have observed**: ts-seat-service's `POST /api/v1/seatservice/seats/left_tickets` carried `injection_affected` + `timeout` flags in the GT. Its avg duration was 2x elevated and max jumped 8.5x (24s vs 2.8s). The 85s gap between ts-travel-plan-service and ts-seat-service's 17ms response was the timeout signal — ts-seat-service was the partition victim, not ts-travel-plan-service.
- **What agent observed instead**: Ranked services by absolute max latency; ts-travel-plan-service at 86s was the highest, so it became the root cause. Mistook the victim aggregating timed-out calls for the originator.
- **Proximate cause**: blamed latency aggregator not partition victim

---

## case_2682  [NetworkChaos / NetworkDelay]

### (1) What really happened
NetworkDelay injection from ts-seat-service → ts-travel-plan-service (1456ms latency + 280ms jitter). This caused `ts-travel-plan-service::TravelPlanController.getByQuickest` to go from ~380ms→20,414ms avg with `injection_affected, timeout`. ts-seat-service's `POST /api/v1/seatservice/seats/left_tickets` also showed `injection_affected, high_avg_latency, high_p99_latency`. All three travelPlan endpoints showed 30-40x latency multiplier.

### (2) What the agent did
Over 56 rounds, the agent anchored on ts-rabbitmq at round 7 (same "UnknownHostException" pattern) and ts-order-service. At round 11, it noticed ts-travel-plan-service had 20-second span durations but dismissed this as "cascading system stress" from the RabbitMQ outage. It never queried ts-seat-service latency directly. The RabbitMQ errors (affecting food/delivery/notification) are entirely orthogonal to the network-delay fault.

### (3) Divergence
- **Pivot round**: 7
- **What agent should have observed**: ts-travel-plan-service's 20s spans at round 11 were the direct symptom of the 1456ms network delay from ts-seat-service. Following the dependency chain upstream from ts-travel-plan-service to ts-seat-service would have found the injection. ts-seat-service span count dropped from 14,997→2,151 — a sharp signal.
- **What agent observed instead**: Anchored on RabbitMQ DNS errors (orthogonal infrastructure issue) and ts-order-service "Order already exists" errors. Never correlated the travelPlan latency with ts-seat-service.
- **Proximate cause**: anchored on pre-existing background error

---

## case_2700  [NetworkChaos / NetworkCorrupt]

### (1) What really happened
NetworkCorrupt (88% corruption) from ts-security-service → ts-preserve-service. This caused ts-security-service's `GET /api/v1/securityservice/securityConfigs/{accountId}` to show `injection_affected` with avg duration inflated from ~75ms→75 seconds. ts-preserve-service showed `high_error_rate, timeout, high_avg_latency, high_p99_latency`. The corruption degraded packets silently without producing application-level errors.

### (2) What the agent did
Over 51 rounds, at round 24 the agent queried ts-security-service spans and found avg_duration of 75 seconds on the securityConfigs endpoint — directly in the preserve call chain. But the `status_code=Unset` (not "Error") led the agent to dismiss this as "no error." At round 27, it found ts-ticket-office-service with 3 container restarts and anchored on this. By round 47, it committed to ts-ticket-office-service despite explicitly noting it "doesn't appear in the traces for the preserve endpoint."

### (3) Divergence
- **Pivot round**: 27
- **What agent should have observed**: The 75-second avg duration on ts-security-service's endpoint at round 24 was the direct evidence — a 1000x latency inflation. Comparing against normal baseline (<100ms) would have been conclusive. NetworkCorrupt manifests as latency/corruption, not HTTP errors.
- **What agent observed instead**: Equated `status_code=Unset` with "healthy," ignoring the extreme duration. Then anchored on ts-ticket-office-service restarts (unrelated infrastructure noise), committing despite zero evidence linking it to the failing preserve endpoint.
- **Proximate cause**: equated no-error-code with healthy service

---

## case_3868  [JVMChaos / JVMLatency]

### (1) What really happened
A JVMLatency injection targeted `ts-config-service.ConfigController.deleteConfig()` with 601ms latency. The injection spilled over to affect the GET endpoint (`/api/v1/configservice/configs/{configName}`) as well — marked `injection_affected`, `high_p99_latency` in the GT. Since ts-config-service is called by ts-seat-service to retrieve configuration, the added latency propagated through ts-seat-service → ts-travel-service/ts-travel2-service → ts-route-plan-service → ts-travel-plan-service → ts-ui-dashboard. The propagation chain had spl=5 with 10 services involved. Container-level metrics show ts-config-service pod had `high_memory` and `high_cpu` — consistent with JVM-level stress from the latency injection. The filesystem usage also spiked (466KB→3MB).

### (2) What the agent did
Over 67 rounds, the agent investigated the high-latency endpoints. At round ~30, it queried k8s container metrics and found `ts-ticket-office-service` had 3 container restarts — a conspicuous infrastructure signal. The agent spent subsequent rounds (30-65) trying to establish a connection between ts-ticket-office-service and the failing endpoints. At round 65, it committed to ts-ticket-office-service as root cause, even noting explicitly that "ts-ticket-office-service doesn't appear in the traces or logs" and calling it "a dependency that's not directly traced." The agent never investigated ts-config-service's latency despite ts-config-service appearing in multiple query results throughout the trajectory.

### (3) Divergence
- **Pivot round**: 30 (discovery of ts-ticket-office-service container restarts)
- **What agent should have observed**: ts-config-service's GET endpoint had elevated latency (high_p99_latency in GT). A per-service latency comparison (abnormal vs normal) for ts-config-service would have shown the latency injection effect. The propagation path ts-config-service → ts-seat-service → upstream was the actual causal chain. ts-ticket-office-service's 3 container restarts had no traceable connection to the SLO-violating endpoints.
- **What agent observed instead**: Found ts-ticket-office-service container restarts — a loud, visible anomaly — and anchored on it. Spent 35 rounds trying to validate this hypothesis despite zero evidence linking ts-ticket-office-service to the failing call chains. The agent acknowledged the link was unproven but committed to the hypothesis anyway.
- **Proximate cause**: anchored on unrelated infrastructure anomaly

---

## case_804  [PodChaos / PodFailure]

### (1) What really happened
PodFailure injection killed `ts-train-service` pod. The container's memory collapsed from 818MB→604KB (z=93.7), confirming the pod was destroyed. ts-train-service spans dropped from 5828→15 (a loss of 5813) with `missing_span, injection_affected` states. The `GET /api/v1/trainservice/trains` endpoint went from 37ms→20001ms (timeout) with 0% success rate. `jvm.class.loaded` spiked from near-zero to thousands, indicating JVM cold-start after restart.

### (2) What the agent did
Over 73 rounds, the agent focused on ts-basic-service (849 error spans, 278 SEVERE logs). At round 70, it found ts-train-service in traces and saw only 3 spans with "Unset" (successful) status. It concluded ts-train-service was healthy. At round 72, committed to ts-basic-service. It never queried ts-train-service container/pod metrics.

### (3) Divergence
- **Pivot round**: 72
- **What agent should have observed**: ts-train-service had only 15 spans in abnormal period vs 5828 normal — the 6th largest drop of any service. The 3 surviving "Unset" spans were pre-failure calls, not evidence of health. Container memory dropping to near-zero was conclusive.
- **What agent observed instead**: Found 3 healthy spans from ts-train-service and concluded it was working. Never noticed the dramatic span count collapse (the canonical PodFailure footprint).
- **Proximate cause**: survivorship bias on surviving spans

---

## case_1917  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on `ts-order-service` pod. All internal spans (`OrderRepository.save`, `SELECT ts.orders`, `Transaction.commit`) flagged `missing_span + injection_affected`. `jvm.class.loaded` jumped from 2→6533 (z=3999), signaling JVM cold-start after kill. `POST /api/v1/orderservice/order/refresh` showed 21x latency increase (19ms→414ms) and 47% success rate drop.

### (2) What the agent did
Over 68 rounds, the agent focused on ts-seat-service (324 error spans, most visible in the system) and ts-security-service (503 "Connection refused"). At round 28, it locked onto "the service with the most errors is the root cause." It saw 503 "Connection refused" errors but never traced upstream to find what ts-seat-service was calling that was dead. At round 64, it found SEVERE logs pointing to the seatservice path but misread the downstream victim as the origin.

### (3) Divergence
- **Pivot round**: 28
- **What agent should have observed**: ts-order-service internal spans all showed `missing_span + injection_affected`. `jvm.class.loaded` z=3999 was the clearest container-kill indicator. The "Connection refused" errors in downstream services were caused by ts-order-service being killed.
- **What agent observed instead**: Followed the noisiest error signal (downstream 503s accumulating in ts-seat-service). Never traced back to the quieter upstream culprit whose spans had gone missing.
- **Proximate cause**: survivorship bias on visible error counts

---

## case_2211  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on `ts-travel-service` container. All ts-travel-service spans showed `missing_span + injection_affected`. `jvm.class.loaded` z=6609 (0.5→6610) — extreme JVM restart signature. `container.cpu.time` dropped sharply (z=34, normal=577→abnormal=152 — CPU time plummeting because the container is dead). ts-route-plan-service received "Connection refused" when calling ts-travel-service.

### (2) What the agent did
Over 67 rounds, the agent found ts-route-plan-service had 132 error spans with "Connection refused" and 44 SEVERE logs. At round 60, the agent asked "why can't ts-route-plan-service reach ts-travel-service?" but answered wrong — attributed fault to ts-route-plan-service rather than to the unreachable ts-travel-service upstream. Explicitly noted ts-travel-service "has spans in the abnormal data (just not in the failing traces)" and dismissed this as "partially available."

### (3) Divergence
- **Pivot round**: 60
- **What agent should have observed**: ts-travel-service `jvm.class.loaded` z=6609 and `container.cpu.time` drop (z=34) were definitive container-kill signatures. The "Connection refused" in ts-route-plan-service was a downstream symptom.
- **What agent observed instead**: Treated ts-route-plan-service (the victim reporting "Connection refused") as the root cause, rather than the unreachable ts-travel-service whose container had been killed.
- **Proximate cause**: blamed downstream victim of silent upstream

---

## case_3114  [PodChaos / PodKill]

### (1) What really happened
PodKill on `ts-preserve-service` pod. `jvm.class.loaded` spiked from 0.5→5089 (z=8814) — pod restart signature. `container.cpu.time` dropped sharply (z=47). The `POST /api/v1/preserveservice/preserve` endpoint showed `missing_span, high_avg_latency, injection_affected`. 27 HTTP 502 errors appeared on the preserve endpoint (normal=0). Failed traces were truncated at ts-ui-dashboard with no ts-preserve-service spans.

### (2) What the agent did
Over 54 rounds, the agent found "Order already exists" errors in ts-order-service co-occurring with the preserve failures. At round 33, it correctly observed that 502-error traces contained *no ts-preserve-service spans at all* — directly indicating the pod was unavailable. But it attributed this to ts-preserve-service "being overwhelmed" by ts-order-service errors, constructing a plausible but wrong application-logic causal chain. Committed to ts-order-service at round 41.

### (3) Divergence
- **Pivot round**: 41
- **What agent should have observed**: ts-preserve-service `jvm.class.loaded` z=8814 and `container.cpu.time` drop (z=47) were canonical pod-kill signatures. Missing spans at round 33 directly indicated the pod was dead, not overwhelmed.
- **What agent observed instead**: Found application-level error messages ("Order already exists") and constructed a business-logic causal chain, while ignoring the infrastructure-layer signal (missing spans = killed pod).
- **Proximate cause**: application-logic narrative over infrastructure signal

---

## case_3138  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on `ts-price-service` container. `jvm.gc.duration` z=1.25M, `container.cpu.usage` +27x (z=34.77), `http.server.request.duration` z=241.79. Spans `POST /api/v1/priceservice/prices/byRouteIdsAndTrainTypes` and `PriceController.query` flagged `injection_affected, missing_span, high_avg_latency`. Propagation: ts-price-service → ts-basic-service (high_error_rate) → cascade.

### (2) What the agent did
Over 40 rounds, at round 17 the agent found "Connection refused" SEVERE error in ts-basic-service explicitly stating it cannot reach `http://ts-price-service:8080`. The agent correctly identified ts-price-service as unavailable and said **"this is the root cause."** But at round 36, after checking ts-price-service traces (Unset status) and logs (INFO only), it reversed course and decided ts-basic-service was the root cause "where the failure originates in the observable error chain."

### (3) Divergence
- **Pivot round**: 36 (reversal from correct to incorrect hypothesis)
- **What agent should have observed**: It had the right answer at round 17! ts-price-service's `missing_span + injection_affected` states and metric anomalies (cpu +27x, gc z=1.25M) confirmed the container kill. "Unset" trace status and absence of ERROR logs are expected for a killed container — it can't emit error telemetry if it's dead.
- **What agent observed instead**: Equated "no Error-status spans" and "no ERROR logs" from ts-price-service with health. Reversed its correct hypothesis because the killed service's silence was misread as absence of fault.
- **Proximate cause**: reversed correct hypothesis on silent-service evidence

---

## case_4375  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on `ts-travel2-service` container. All spans flagged `injection_affected + missing_span`. `jvm.class.loaded` spiked 1.25→6611 (z=3491). Pod showed `high_cpu + high_gc_pressure`. The `/api/v1/travel2service/trips/left` trace contained only `loadgenerator → ts-ui-dashboard` spans — ts-travel2-service was absent entirely (killed container).

### (2) What the agent did
Over 51 rounds, at round 24 the agent found 503 "Connection refused" in ts-route-plan-service logs and declared it a "Critical Finding." The trace for `travel2service/trips/left` showed only ts-ui-dashboard — ts-travel2-service was absent. But the agent framed this as "ts-ui-dashboard shows 503" rather than recognizing ts-travel2-service was unreachable. Committed to ts-route-plan-service at round 51 based on timestamp ordering.

### (3) Divergence
- **Pivot round**: 24
- **What agent should have observed**: ts-travel2-service absent from traces + `jvm.class.loaded` z=3491 = killed container. ts-route-plan-service's "Connection refused" was a downstream symptom of trying to call the dead ts-travel2-service.
- **What agent observed instead**: Treated ts-route-plan-service (the service reporting "Connection refused") as the autonomous failure origin rather than a victim propagating errors from a dead upstream.
- **Proximate cause**: blamed downstream victim of silent upstream

---

## case_4893  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on `ts-order-service` pod. Span count dropped by 1794 (largest single-service drop). Internal spans (`OrderController.queryOrdersForRefresh`, `OrderRepository.findByAccountId`) all `missing_span`. `jvm.class.count` collapsed from 19606→16276 (z≈4078) — mid-life pod restart. `POST /api/v1/orderservice/order/refresh` dropped to 47% success rate with 502 "Connection refused."

### (2) What the agent did
Over 50 rounds, the agent traced a single error trace in the travel/seat path, found ts-seat-service as the leaf error node (1030ms error duration), and committed at round 38. At round 44, it correctly identified two separate issues: "Issue 1: 502s for orderservice (ts-order-service unreachable)" and "Issue 2: 500s for travel (ts-seat-service root cause)." But it consciously chose Issue 2 as primary and downgraded ts-order-service to "secondary."

### (3) Divergence
- **Pivot round**: 38
- **What agent should have observed**: ts-order-service lost 1794 spans (largest single-service drop). Its internal spans showed `missing_span` — only possible if the service itself was killed. `jvm.class.count` collapse z≈4078 confirmed. The travel/seat 500s were a cascade from ts-order-service unavailability.
- **What agent observed instead**: The travel path produced loud, traceable 500s with a clear leaf node (ts-seat-service). The ts-order-service failure manifested as 502 "Connection refused" with no downstream trace spans — invisible to trace-centric reasoning.
- **Proximate cause**: salience bias toward traceable errors

---

## case_2231  [HTTPFault / HTTPRequestDelay]

### (1) What really happened
HTTPRequestDelay injected on ts-travel-service's outbound GET calls to ts-route-service (`/api/v1/routeservice/routes/*`) with 2297ms added delay. This caused ts-travel-service's `POST /api/v1/travelservice/trips/left` to show `high_avg_latency, high_p99_latency, high_error_rate (HTTP 500)`. ts-route-service's `hubble_http_request_duration_p95_seconds` z-score=361. ts-route-service span count dropped by 28,514.

### (2) What the agent did
Over 40 rounds, the agent anchored on ts-rabbitmq at round 6 after seeing `UnknownHostException: ts-rabbitmq` in ts-food-service logs. At rounds 8-11, it examined error spans and found ts-travel-service with HTTP 500 errors and traces showing 2.3s latency to ts-route-service. But it labeled these "cascading effects from RabbitMQ." The RabbitMQ errors were pre-existing (delivery-service errors: normal=48, abnormal=45 — nearly identical).

### (3) Divergence
- **Pivot round**: 6
- **What agent should have observed**: ts-travel-service→ts-route-service latency was the direct injection signal. RabbitMQ DNS errors (in food/delivery/notification) were orthogonal and pre-existing. A.5b error delta shows rabbitmq-related services had near-identical normal/abnormal error counts.
- **What agent observed instead**: Anchored on vivid "UnknownHostException" error string. Never queried ts-route-service latency metrics. Never compared RabbitMQ error counts between normal and abnormal periods.
- **Proximate cause**: anchored on pre-existing background error

---

## case_3120  [HTTPFault / HTTPRequestReplacePath]

### (1) What really happened
HTTPRequestReplacePath on `ts-preserve-service`'s POST to `/api/v1/travelservice/trip_detail`, redirecting to ts-travel-service with corrupted path. The preserve endpoint went to 0% success (abn_succ=0.0). Trace error spans: ts-preserve-service (306), ts-travel-service received 99 HTTP error responses. ts-preserve-service memory metrics showed z=18-28 across multiple dimensions.

### (2) What the agent did
Over 53 rounds, at round 43 the agent found a trace showing ts-travel-service calling ts-basic-service with 420s latency and committed to ts-basic-service as root cause. At round 49, it cited ts-basic-service's `jvm.system.cpu.load_1m` spike to 477.46 as confirmation. But `jvm.system.cpu.load_1m` is a system-wide metric, not service-specific. At round 52, it saw trace errors concentrated in ts-preserve-service and ts-ui-dashboard (not ts-basic-service) but didn't revise.

### (3) Divergence
- **Pivot round**: 43
- **What agent should have observed**: The 0% success rate on the preserve endpoint and "Connection reset" errors on ts-preserve-service's call to ts-travel-service were the direct fault mechanism. A.5c shows ts-travel-service received 99 HTTP errors — consistent with path replacement producing bad requests. ts-basic-service had no entries in the metric anomaly table.
- **What agent observed instead**: Latched onto the most dramatic numeric signal (420s span duration, 477 CPU load) from ts-basic-service rather than the structurally correct signal (path-replacement error at ts-preserve-service egress).
- **Proximate cause**: amplitude greed on largest numeric anomaly

---

## case_99  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress injection (mem_type=1) targeted `ts-consign-price-service.ConsignPriceServiceImpl.getPriceByWeightAndRegion`. The GT fingerprint shows explosive JVM class loading on ts-consign-price-service (`jvm.class.loaded` z=6462B, `jvm.cpu.time` z=740, `k8s.pod.cpu.usage` z=540, `k8s.pod.memory.page_faults` z=1133) with container states flagged `high_cpu, high_memory, restarting`. The span-level footprint shows the `HTTP PUT /consignservice/consigns` endpoint degraded (9030ms abnormal vs 100ms normal, 55% success). Errors propagated through ts-consign-service (69 error spans, 46 HTTP 5xx) up to ts-ui-dashboard/loadgenerator, but ts-consign-price-service itself emitted no 5xx traces — only the upstream caller ts-consign-service surfaced the failures.

### (2) What the agent did
Rounds 1-6 gathered schema and ran aggregate error queries. At Round 6, the agent pulled status-code counts and Round 7 queried Error-status trace rows, which returned exactly two services: ts-consign-service with 23×500, 23×503, 23×Error, and loadgenerator with 4 errors. The agent anchored on this result: ts-consign-service had the only HTTP-level error footprint and became the hypothesis. Subsequent rounds (8-47) drilled into ts-consign-service traces and its callers/callees without ever pivoting to query ts-consign-price-service's JVM metrics (`jvm.class.loaded`, `jvm.cpu.time`) or container restart state. The final predicted graph was `ts-consign-service → ts-ui-dashboard → loadgenerator`, missing the silent upstream ts-consign-price-service entirely.

### (3) Divergence
- **Pivot round**: 7
- **What agent should have observed**: ts-consign-price-service JVM anomalies (`jvm.class.loaded` z=6462B, `jvm.cpu.time` z=740, memory page_faults z=1133) and container state `high_cpu, high_memory, restarting` — the canonical JVMMemoryStress fingerprint on the injected service, which emits zero trace errors but is the parent of ts-consign-service in the call chain.
- **What agent observed instead**: Round 7 showed ts-consign-service as the only service with Error-status spans (69 error spans, HTTP 500/503); the agent anchored here as the visible error source.
- **Proximate cause**: blamed error-emitting caller not slow callee

---

## case_281  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress injection on `ts-station-food-service.StationFoodController.home` (mem_type=1). The GT propagation is `container|ts-station-food-service → ts-station-food-service → ts-food-service → ts-ui-dashboard → loadgenerator`; ts-station-food-service has `high_cpu, high_memory, high_gc_pressure`. The `HTTP GET /foodservice/foods/...` endpoint degraded from 47ms→477ms. The key structural quirk: ts-food-service is the public face of the food API and aggregates from ts-station-food-service; when the backend (station-food) stalls, ts-food-service surfaces voluminous `Get the Get Food Request Failed!` error logs even though ts-station-food-service is the actual root cause.

### (2) What the agent did
In Round 5 the agent queried top ERROR log messages grouped by service, which returned ts-food-service at the top with 69 occurrences of "Get the Get Food Request Failed!" plus RabbitMQ UnknownHostException errors. Round 6's think_tool declared: "ts-food-service has the most ERROR logs (164 total)" with the memorable "UnknownHostException: ts-rabbitmq" error, and concluded "ts-food-service is clearly the most affected." The hypothesis was set to ts-food-service at Round 6 and never seriously challenged. Subsequent rounds verified ts-food-service internal behavior rather than querying ts-station-food-service's JVM metrics or GC duration. The final graph was `ts-food-service → ts-ui-dashboard → loadgenerator`.

### (3) Divergence
- **Pivot round**: 6
- **What agent should have observed**: ts-station-food-service JVM memory-stress signature (the injected service) with `high_cpu, high_memory, high_gc_pressure` pod states; ts-food-service logs `foodStoresListResult is null` literally names the backend that returned null — station-food.
- **What agent observed instead**: Anchored on ts-food-service's 164 ERROR logs headlined by the "Get Food Request Failed" and RabbitMQ DNS errors (pre-existing environmental noise).
- **Proximate cause**: blamed high-error-count messenger not upstream

---

## case_784  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress on `ts-station-food-service.StationFoodServiceImpl.listFoodStores` (mem_type=1). Ground-truth root cause is ts-station-food-service; the public food endpoint `GET /foodservice/foods/...` is served by ts-food-service, which fan-outs to ts-station-food-service for store lookups. When station-food stalls under memory pressure, ts-food-service surfaces 500/503 errors while station-food itself produces no HTTP-level error traces.

### (2) What the agent did
Round 9 examined trace `b9e6717b8df2fbd34c96f742d48fd6d6` showing the call chain loadgenerator → ts-ui-dashboard → ts-food-service (Error spans, ~3.5s duration) → ts-train-food-service / ts-travel-service / ts-route-service (all "Unset" = healthy). The agent did not query ts-station-food-service directly in this trace sample. Round 10's think_tool concluded: "Only ts-food-service shows Error status with HTTP 500 and 503 responses. The error originates in ts-food-service itself, not from its dependencies." Hypothesis locked to ts-food-service. The agent treated the three healthy siblings it did query as "the complete dependency set" and never checked station-food-service's JVM metrics. Final answer: ts-food-service as root cause.

### (3) Divergence
- **Pivot round**: 10
- **What agent should have observed**: ts-station-food-service's JVMMemoryStress signature — it is a dependency of ts-food-service that the agent never queried. The agent sampled only 3 of ts-food-service's downstreams and missed station-food entirely.
- **What agent observed instead**: ts-food-service showing Error status while its sampled downstreams showed Unset, reading this as "error originates here."
- **Proximate cause**: blamed error-loud child missed silent upstream

---

## case_860  [HTTPFault / HTTPResponseReplaceBody]

### (1) What really happened
HTTPResponseReplaceBody (body_type=1) was injected on the route `ts-travel-service → POST /api/v1/seatservice/seats/left_tickets → ts-seat-service`, corrupting the JSON response body ts-seat-service returned to ts-travel-service. GT root-cause services are ts-travel-service and ts-seat-service (the edge is the fault). The victim, ts-travel-service, logged JSON parse errors ("Unexpected character 'z' (code 122)") and connection resets when processing the malformed ts-seat-service responses; ts-basic-service was a separate innocent caller that happened to emit "Connection reset" logs from ts-travel-service calls into basic-service's API — unrelated to the injection point.

### (2) What the agent did
Round 8 queried ts-travel-service SEVERE logs and saw two distinct patterns: (a) "I/O error on POST...http://ts-basic-service:8080/api/v1/basicservice/basic/travels: Connection reset" and (b) JSON parse errors "Unexpected character ('z' (code 122))". Round 9's think_tool latched onto the ts-basic-service string: "ts-travel-service is experiencing errors when calling ts-basic-service... This points to ts-basic-service as a potential root cause. The ts-travel-service is a victim trying to call ts-basic-service and failing." The agent conflated two unrelated error patterns — reading the JSON parse errors as originating from ts-basic-service instead of from ts-seat-service (which the injected route actually targeted). Final answer: ts-basic-service.

### (3) Divergence
- **Pivot round**: 9
- **What agent should have observed**: The JSON parse errors in ts-travel-service should have been traced to the `POST /api/v1/seatservice/seats/left_tickets` call to ts-seat-service (the injection route), not attributed to ts-basic-service. The body_type=1 signature was malformed JSON from seat-service.
- **What agent observed instead**: Misread the ts-travel-service log bundle as all pointing to ts-basic-service, anchoring on the memorable "Connection reset" phrase from a basicservice URL.
- **Proximate cause**: misread victim error log as upstream fault

---

## case_1371  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill targeted the ts-seat-service container (pod `ts-seat-service-5d77c89dc-6kl5m`). When the seat-service pod was killed, callers ts-travel-service and ts-travel2-service (which invoke `POST /seatservice/seats/left_tickets`) received 503 "upstream connect error... Connection refused" from Istio and propagated errors upward. ts-seat-service itself produced zero error traces (it was dead); ts-travel*-service produced the noisy error logs.

### (2) What the agent did
Across many rounds the agent surveyed errors and noted high SEVERE log counts for ts-travel2-service and ts-travel-service. At Round 77 the agent queried direct calls from ts-travel2-service and found that its downstream calls to ts-seat-service, ts-basic-service, ts-route-service returned 200 OK (only from the subset of traces where seat-service responded). Round 78's think_tool concluded: "ts-travel2-service has 165 Error spans... 503 Service Unavailable: Connection refused... Downstream services (ts-seat-service, ts-basic-service, ts-route-service) are healthy and responding with 200 OK." The agent inverted the reality — seat-service "healthy 200" traces were the survivorship subset; the 503s the agent attributed to ts-travel2-service originated from seat-service's dead pod refusing connections. Final answer: ts-travel2-service and ts-travel-service.

### (3) Divergence
- **Pivot round**: 78
- **What agent should have observed**: ts-seat-service pod restart/missing pod state — the killed container is invisible in trace data exactly because it was killed; absence of error traces from seat-service is the fingerprint, not proof of health.
- **What agent observed instead**: Sampled successful seat-service 200-OK spans and read "healthy," then attributed the upstream connect 503s to the callers ts-travel2-service/ts-travel-service as "common dependency failing."
- **Proximate cause**: blamed messengers carrying seat-service 503s

---

## case_1435  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on ts-train-food-service (pod `ts-train-food-service-7b67f6b66f-wlcg5`). The public endpoint `GET /foodservice/foods/...` goes loadgenerator → ts-ui-dashboard → ts-food-service → ts-train-food-service; when train-food was killed, ts-food-service's fan-out call failed and ts-food-service surfaced 500/503 errors with DNS-like errors ("UnknownHostException: ts-rabbitmq" was pre-existing noise). ts-train-food-service itself emitted no trace errors (pod dead).

### (2) What the agent did
Round 11 queried a specific error trace showing loadgenerator → ts-ui-dashboard → ts-food-service chain with all ts-food-service spans showing Error status. Round 12's think_tool concluded: "ts-food-service is the only service showing Error status codes (66 errors)... ts-food-service has errors about UnknownHostException: ts-rabbitmq... This indicates ts-food-service cannot resolve/connect to the RabbitMQ service. The evidence strongly points to ts-food-service as the root cause." The agent conflated two unrelated signals: the injection-caused 500/503 from train-food failures, and the pre-existing RabbitMQ DNS noise. It never queried ts-train-food-service (the actual killed target) directly. Final graph: ts-food-service → ts-ui-dashboard → loadgenerator.

### (3) Divergence
- **Pivot round**: 12
- **What agent should have observed**: ts-train-food-service pod-failure fingerprint (container not ready, absent trace spans during the injection window) — the child service that ts-food-service's `reGetTrainFoodListResult` log literally references.
- **What agent observed instead**: Anchored on ts-food-service's error logs and the memorable RabbitMQ UnknownHostException (pre-existing background noise unrelated to the injection).
- **Proximate cause**: messenger error logs blamed over upstream origin

---

## case_1459  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress on `ts-train-service.InitData.run` (mem_type=1). When ts-train-service stalls under memory pressure, callers like ts-basic-service — which calls train-service for train-type lookups — receive "Connection refused" / 503 from Istio because the sidecar delayed replies past its timeout. ts-basic-service then logged 322 SEVERE "503 Service Unavailable: upstream connect error... Connection refused" entries. ts-train-service itself emitted few visible errors.

### (2) What the agent did
Round 5 queried top ERROR/SEVERE logs and discovered ts-basic-service with 322 SEVERE "503... Connection refused" logs — by far the largest cluster. Round 6's think_tool: "ts-basic-service has 322 SEVERE errors... 'Connection refused'... This is a critical finding! The pattern suggests ts-basic-service is failing (503 errors), and other services that depend on it are experiencing cascading failures... The error message 'Connection refused' for ts-basic-service suggests it might be the root cause — the service itself is unavailable." The agent treated 503s logged BY ts-basic-service as 503s emitted BY ts-basic-service, reading the Envoy "upstream connect" error message backward. Final graph anchored on ts-basic-service as root.

### (3) Divergence
- **Pivot round**: 6
- **What agent should have observed**: ts-train-service memory-stress JVM fingerprint — train-service is the upstream target ts-basic-service was trying to reach and failed. The Envoy "upstream connect error" in basic-service's log actually names train-service as the unreachable upstream.
- **What agent observed instead**: Anchored on ts-basic-service's 322 SEVERE logs, reading "503 logged by basic-service" as "basic-service returning 503."
- **Proximate cause**: 503 errors in downstream blamed as origin

---

## case_1495  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress on `ts-travel-plan-service.TravelPlanController.home` (mem_type=1). The `POST /travelPlanService/travelPlan/minStation` endpoint degraded as travel-plan under memory pressure took ~4s per request. When travel-plan stalled, its fanned-out downstreams (ts-route-plan-service, ts-seat-service) surfaced spurious Error statuses because requests timed out at the travel-plan level. ts-travel-plan-service itself showed "Unset" status but catastrophic latency.

### (2) What the agent did
Round 10-11 queried a single trace and found ts-seat-service returning one Error span (SeatController.getLeftTicketOfInterval, ~180ms). The agent anchored on this Error-status marker. Subsequent rounds dove into ts-seat-service and ts-route-plan-service metrics, treating their derivative errors as primary, and mis-mapped the propagation path as seat-service → route-plan → travel-plan → ui-dashboard (inverting the true direction). The agent never probed travel-plan-service's JVM metrics or memory footprint despite it being the direct parent of the failing endpoint. Final graph reversed: `ts-seat-service → ts-route-plan-service → ts-travel-plan-service → ts-ui-dashboard`.

### (3) Divergence
- **Pivot round**: 11
- **What agent should have observed**: ts-travel-plan-service JVM memory pressure — it is the service whose controller method was injected and whose pod exhibits `high_cpu, high_memory, high_gc_pressure`.
- **What agent observed instead**: Latched onto a single Error-status span from ts-seat-service (the deepest Error marker in one trace) at Round 11.
- **Proximate cause**: single error span hijacked attribution

---

## case_1814  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress on `ts-basic-service.BasicController.queryForStationId` (mem_type=1). When basic-service stalls, ts-travel-service (which calls basic-service for travel lookups) surfaces 500/503 errors and SEVERE logs; preserve-service (calling travel-service) surfaces timeouts. Basic-service itself shows memory/JVM anomalies but few HTTP-level trace errors.

### (2) What the agent did
Round 49 drilled into a specific Error-status span in ts-travel-service (`TravelController.getTripAllDetailInfo`, duration ~3.8s). Round 50's think_tool synthesized: "ts-travel-service is the service with Error status codes... 78 error spans... ts-travel-service is the deepest service in the chain that's failing." The agent treated the loadgenerator → ui-dashboard → preserve-service → travel-service chain as complete, missing that travel-service's failing calls were reaching basic-service next. The RabbitMQ issue was explicitly dismissed as unrelated (correct), but the agent never stepped one level deeper to basic-service. Final answer: ts-travel-service.

### (3) Divergence
- **Pivot round**: 50
- **What agent should have observed**: ts-basic-service's JVM memory signature and basic-service's controller method `queryForStationId` being the actual injection point; travel-service's SEVERE logs would show calls into basic-service failing.
- **What agent observed instead**: Stopped at travel-service because it was "the deepest service showing errors" in the trace subset the agent sampled.
- **Proximate cause**: ts-travel-service reported 500s calling silent ts-basic-service

---

## case_2253  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress on `ts-travel-service.MyCallable.MyCallable` (mem_type=1). Travel-service is a dependency of route-plan-service, which aggregates route/travel data. When travel-service stalls, route-plan's aggregation requests fail, and route-plan logs 500/503. ts-travel-service emits few HTTP-level error traces; route-plan-service accumulates the bulk of visible errors.

### (2) What the agent did
Round 42 ran a join query comparing ts-route-plan-service Error traces with their upstream ts-travel-plan-service and ts-ui-dashboard spans, and found that even when route-plan had errors, the upstream services showed Unset/200 status. Round 43 think_tool: "In the traces where ts-route-plan-service has errors, the upstream services show 'Unset' status with 200 response codes." The agent read the structure upward (route-plan is deepest error-emitter of the upstream path) and hypothesised route-plan as root cause, not looking downward into ts-travel-service which route-plan calls. Final graph: ts-route-plan-service as root.

### (3) Divergence
- **Pivot round**: 43
- **What agent should have observed**: ts-travel-service JVM memory fingerprint — travel-service is a direct callee of route-plan-service; the GT propagation path is travel-service → route-plan-service → ….
- **What agent observed instead**: Fixed on route-plan-service as the "deepest error-emitter" without probing its own downstreams.
- **Proximate cause**: picked highest-error-count downstream reporter

---

## case_2258  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on ts-travel2-service (pod `ts-travel2-service-79fb6f545d-ndlnv`). When travel2-service's pod was killed, its caller ts-route-plan-service (which fans out `POST /travel2service/trips/...` calls) saw "503 Service Unavailable: upstream connect error... Connection refused" from Istio and accumulated 192 error spans plus 64 SEVERE logs. ts-travel2-service itself produced no error traces during the outage window.

### (2) What the agent did
Round 55 ran the error-count aggregation and found ts-route-plan-service dominant (192 errors) vs ts-travel-plan-service (12) vs ts-ui-dashboard (10). Round 56's think_tool: "ts-route-plan-service has the most errors (192)... showing 'Connection refused' errors in its SEVERE logs... ts-route-plan-service (ROOT CAUSE) → ts-travel-plan-service → ts-ui-dashboard → loadgenerator." The agent explicitly noted that ts-route-plan-service's downstreams (route-service, travel-service, travel2-service) "all show Unset/200 - working" — but sampled these from surviving traces, missing that travel2-service was killed and its absent traces meant dead, not healthy. Final answer: ts-route-plan-service.

### (3) Divergence
- **Pivot round**: 56
- **What agent should have observed**: ts-travel2-service pod-kill state — the killed pod's absence from trace data (not presence of 200-OK traces on surviving instances) is the signature.
- **What agent observed instead**: Anchored on ts-route-plan-service's 192 error spans and its SEVERE "Connection refused" logs as "first error-emitter."
- **Proximate cause**: blamed error-reporting hop not silent upstream

---

## case_2285  [HTTPFault / HTTPResponseAbort]

### (1) What really happened
HTTPResponseAbort injection on route `ts-travel2-service → POST /basicservice/basic/travel → ts-basic-service` — the proxy aborts responses from basic-service, causing travel2-service to see connection resets. Both ts-travel2-service and ts-basic-service are GT root-cause (travel2 is the caller-side victim, basic is the server-side origin of the aborted response). The first error at 11:24:03.639 is ts-travel2-service getting a connection reset from ts-seat-service (unrelated noise), then at 11:24:03.671 from ts-basic-service (the injection).

### (2) What the agent did
Across rounds the agent surveyed errors and built timelines. Round 48's think_tool laid out the order: "First error (11:24:03.639): ts-travel2-service gets Connection reset from ts-seat-service. Second error (11:24:03.671): ts-travel2-service gets Connection reset from ts-basic-service... The ts-seat-service error appears first (by 32ms), suggesting it might be the initial root cause." The agent picked the earliest-timestamp reset — from an unrelated seat-service blip — and anointed seat-service as root, missing that the injection specifically targeted the basic-service edge. Final answer: ts-seat-service.

### (3) Divergence
- **Pivot round**: 48
- **What agent should have observed**: The injection-specific `POST /basicservice/basic/travel` route — ts-travel2-service's connection reset from ts-basic-service is the targeted signature; the 32ms-earlier ts-seat-service reset is background noise from an independent request.
- **What agent observed instead**: Took the first-timestamp connection-reset (seat-service) as causal, ignoring which route-path the resets came from.
- **Proximate cause**: first connection-reset implicated innocent caller

---

## case_2678  [NetworkChaos / NetworkBandwidth]

### (1) What really happened
NetworkBandwidth injection throttled traffic from `ts-seat-service → ts-config-service` (rate=827703, buffer=1447, limit=262). When seat-service's config-service calls were bandwidth-choked, seat-service's DB connection pool exhausted (HikariCP) and seat-service stalled; downstream ts-travel2-service's seat-service calls timed out with HTTP 500. GT root causes: ts-seat-service + ts-config-service (the throttled edge).

### (2) What the agent did
Round 33 queried first-error timestamps per service: loadgenerator 22:07:06; travel-plan 22:10:11.468; route-plan 22:10:11.473; travel2 22:10:11.497. Round 34's think_tool: "The actual causal flow is from the deepest service (ts-travel2-service) upward... ts-travel2-service has the database connection pool exhaustion issue... Root cause is ts-travel2-service with database connection pool exhaustion (HikariCP timeout)." The agent misidentified which service had the connection pool issue — travel2-service was the caller reporting errors from seat-service calls, not the service with exhausted pool. Seat-service (the actual throttled node) and config-service (the throttle target) were never drilled. Final answer: ts-travel2-service.

### (3) Divergence
- **Pivot round**: 34
- **What agent should have observed**: ts-seat-service to ts-config-service bandwidth-throttled edge — seat-service would show HikariCP exhaustion in its own logs, not travel2-service's.
- **What agent observed instead**: Followed the trace chain to travel2-service and attributed pool exhaustion there, stopping at the deepest service with Error status traces.
- **Proximate cause**: followed DB errors to deepest trace node

---

## case_2836  [HTTPFault / HTTPResponseReplaceBody]

### (1) What really happened
HTTPResponseReplaceBody (body_type=1) on route `ts-travel2-service → POST /basicservice/basic/travels → ts-basic-service`. Travel2-service receives corrupted response bodies from basic-service and surfaces 500 errors; ts-basic-service itself shows no error traces. Downstream ts-seat-service and ts-config-service are completely uninvolved, but happen to show elevated latency as a side effect of travel2-service's retries saturating the mesh.

### (2) What the agent did
Round 31's think_tool: "ts-config-service shows extremely high latency: one request took 3.1 seconds... 234ms... Normal requests seem to be around 20-28ms... This confirms ts-config-service is the root cause of the high latency. The call chain is: ts-config-service (slow - 3+ seconds) ← ROOT CAUSE → ts-seat-service → ts-travel2-service → ts-ui-dashboard → loadgenerator." The agent chased the deepest service showing any latency anomaly and invented a causal chain inverting the actual call graph — config-service is called BY seat-service as a leaf, not upstream of travel2. Final answer: ts-config-service.

### (3) Divergence
- **Pivot round**: 31
- **What agent should have observed**: The injection route `ts-travel2-service → ts-basic-service` with body_type=1 — travel2-service would see JSON parse / malformed response symptoms directly attributable to basic-service.
- **What agent observed instead**: Anchored on config-service's 3.1-second latency tail as "extremely high," invented a dependency inversion to place config upstream of travel2.
- **Proximate cause**: blamed deep dependency latency not injected sender

---

## case_3393  [HTTPFault / HTTPResponseDelay]

### (1) What really happened
HTTPResponseDelay (delay=1896ms) injected on route `ts-travel2-service → GET /routeservice/routes/* → ts-route-service`. When travel2-service's route-service calls are delayed, travel2's upstream callers (route-plan, travel-plan) see timeouts and 500 errors. GT root causes: ts-travel2-service + ts-route-service (the delayed edge).

### (2) What the agent did
Round 12 pulled trace `66a0d701...` and observed loadgenerator → ui-dashboard → travel-plan → route-plan → travel2 / travel → basic, with ts-travel2-service at 25ms Error and ts-basic-service at 21ms "Unset" and ts-route-plan-service at Error status. The agent noted ts-travel2-service had Error status. Subsequent rounds drilled into basic-service and seat-service's metrics, eventually concluding that seat-service and basic-service must be the root cause because they appeared deepest with error-like signals. The actual injection target (ts-route-service) was never examined. Final answer: ts-basic-service, ts-seat-service.

### (3) Divergence
- **Pivot round**: 12
- **What agent should have observed**: The `GET /routeservice/routes/*` route was the specific injection target; travel2-service's error in Round 12 was from calling route-service with ~1.9s injected delay — one tool call down from where the agent stopped.
- **What agent observed instead**: Saw travel2-service Error status at Round 12 but chose to look "deeper" into basic-service and seat-service, conflating downstream timeouts with causation.
- **Proximate cause**: downstream callees blamed for caller reset

---

## case_3592  [HTTPFault / HTTPResponseDelay]

### (1) What really happened
HTTPResponseDelay (delay=4548ms) on route `ts-route-plan-service → POST /travel2service/trips/routes → ts-travel2-service`. Route-plan-service's travel2 calls were delayed nearly 4.5s, causing route-plan to time out and log 503s; ts-travel-plan-service then logs 503s calling route-plan. GT root causes: ts-route-plan-service + ts-travel2-service (the delayed edge).

### (2) What the agent did
Round 31's think_tool: "ts-route-plan-service logs show: 'I/O error on POST request for http://ts-travel-service:8080/api/v1/travelservice/trips/left: Connection reset'... ts-travel-service is experiencing connection resets (likely crashed, overloaded, or network issue)... ts-route-plan-service calls ts-travel-service and gets Connection reset → ts-route-plan-service fails... The root cause is ts-travel-service." The agent misread which upstream route was failing — the log line actually involves travel-service (unrelated background errors) while the injection was on the travel2-service route `/trips/routes`. Final answer: ts-travel-service.

### (3) Divergence
- **Pivot round**: 31
- **What agent should have observed**: The route-plan-service SEVERE logs should have been sorted by endpoint path — the `/travel2service/trips/routes` entries with ~4.5s timeouts are the injection-specific signature; the travel-service "Connection reset" is background from a different code path.
- **What agent observed instead**: Picked the first Connection-reset log it saw (travel-service) and declared it the origin.
- **Proximate cause**: error recipient blamed instead of injected delayer

---

## case_3673  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on the mysql pod (`mysql-0`). When mysql died, ts-auth-service's `auth_user` table lookups failed with "Table 'ts.auth_user' doesn't exist" — producing 2,694 application-layer ERROR logs. ts-train-service similarly hit "Table 'ts.train_type' doesn't exist" (35 errors). The sheer volume of auth-service errors swamped all other signals. mysql itself logged only a handful of "Aborted connection" entries (effectively silent).

### (2) What the agent did
Round 7's think_tool: "ts-auth-service has the highest error count (2,694 errors) with the message 'Table ts.auth_user doesn't exist' - This is a critical database issue! ts-train-service has 35 errors with 'Table ts.train_type doesn't exist'... The root cause appears to be database-related issues. The ts-auth-service is failing because the 'ts.auth_user' table doesn't exist. This is likely the root cause since it has the highest error count by far." The agent correctly identified the database substrate as the problem but blamed the application services that reported missing-table errors, not the database itself. mysql's state (killed pod) was never queried. Final answer: ts-train-service + ts-auth-service.

### (3) Divergence
- **Pivot round**: 7
- **What agent should have observed**: mysql pod status (killed, not running) during the injection window — the "Table doesn't exist" errors are a symptom of the MySQL process being down and the driver failing to reach it.
- **What agent observed instead**: Anchored on auth-service's 2,694 error count and read "missing table" literally as an application-level schema issue.
- **Proximate cause**: DB table errors blamed on app services

---

## case_3760  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress on `ts-price-service.PriceController.query` (mem_type=2). When price-service stalled, ts-basic-service (which invokes price-service during travel lookups) saw 503s and logged 633 SEVERE "Connection refused" entries. Downstream travel-service/travel2-service/preserve-service got 504 Gateway Timeouts from basic-service. Price-service itself emitted few HTTP errors.

### (2) What the agent did
Round 49's think_tool laid out the timeline: "ts-food-service - first error at 04:44:36 (earliest)... ts-basic-service - first error at 04:45:01... ts-travel-service - first error at 04:45:53... Looking at the error types: ts-food-service: RabbitMQ queue errors (different issue); ts-basic-service: 503 Service Unavailable with Connection refused; travel-*: 504 Gateway Timeout... The trace data clearly shows the call chain for these endpoints ends at ts-basic-service, and ts-basic-service is the service with the most errors (633) affecting the travel endpoints. The root cause for the travel endpoint SLO violations is ts-basic-service." The agent correctly isolated the RabbitMQ noise but then stopped at basic-service, which was the first error-reporter after the noise — missing that basic-service's Connection-refused errors name price-service as the unreachable upstream. Final answer: ts-basic-service.

### (3) Divergence
- **Pivot round**: 49
- **What agent should have observed**: ts-price-service JVM memory-stress signature (mem_type=2) — basic-service's 633 "Connection refused" SEVERE logs reference the upstream target, which is price-service on the travel lookup path.
- **What agent observed instead**: Anchored on basic-service as "first service with most travel-endpoint errors" once the food-service RabbitMQ noise was filtered out.
- **Proximate cause**: first downstream error reporter mistaken for origin

---

## case_3776  [PodChaos / PodFailure]

### (1) What really happened
PodFailure on ts-seat-service (pod `ts-seat-service-75676c6d97-8k8ck`) — the pod failed, not restarted. Callers ts-travel2-service and ts-travel-service, which invoke seat-service for left-ticket checks, received "upstream connect error... Connection refused" from Istio and logged 552 Error spans and 180 SEVERE entries on travel2. The dead seat-service emitted zero traces. ts-basic-service (a legitimate callee of travel2) was fully healthy.

### (2) What the agent did
Round 85's think_tool: "ts-travel2-service has the most error spans (552 Error spans)... 180 SEVERE log entries... is the most downstream service in the main call chain that shows errors... ts-basic-service (its downstream dependency) shows no errors... The error message says 'Connection refused' which suggests ts-travel2-service is trying to connect to something that's down... Given that ts-basic-service has ZERO error spans and ZERO error logs, it's unlikely to be the root cause. The most plausible explanation is that ts-travel2-service has some internal issue (perhaps related to connection pooling, thread exhaustion, or resource constraints)." The agent entertained the correct hypothesis (something seat-service-sized is down) but rejected it because the service it *happened* to query (basic-service) was healthy, ignoring that seat-service — the other callee — was uninvestigated. Final answer: ts-travel2-service + ts-travel-service.

### (3) Divergence
- **Pivot round**: 85
- **What agent should have observed**: ts-seat-service pod-failure state — the absence of seat-service spans during the injection window is the signature, and travel2-service's Connection-refused logs name seat-service as the target.
- **What agent observed instead**: Queried basic-service (healthy) and concluded "no upstream is down, must be travel2-service's internal issue." Seat-service was not one of the services the agent probed for pod health.
- **Proximate cause**: Connection-refused victims blamed not failed pod

---

## case_3955  [PodChaos / PodFailure]

### (1) What really happened
PodFailure on ts-station-food-service (pod `ts-station-food-service-8c666b479-c2j28`). The foodservice public endpoint calls ts-food-service → ts-station-food-service for store lookups. When station-food pod failed, ts-food-service surfaced 157 errors (127 SEVERE "503 upstream connect error... Connection refused" + 30 "Get Food Request Failed") and returned 503 to callers. Station-food-service emitted no traces. The agent did note a single ts-station-food-service container restart (correct signal) but failed to connect it.

### (2) What the agent did
Round 53's think_tool summarised: "ts-food-service has the most errors (157 total)... 127 SEVERE errors with '503 Service Unavailable: upstream connect error...Connection refused'... ts-train-food-service shows OK in traces... The root cause is likely ts-train-food-service being unavailable, causing ts-food-service to fail." The agent correctly noticed ts-station-food-service pod restart in the summary, but then chose ts-train-food-service as culprit because of a surface-level semantic match ("reGetTrainFoodListResult" phrase in food-service logs). The pod-restart evidence for station-food was explicitly in the agent's list but discarded. Final answer: ts-train-food-service.

### (3) Divergence
- **Pivot round**: 53
- **What agent should have observed**: The single ts-station-food-service container restart that the agent itself listed as evidence — pod-failure fingerprint on the injected service.
- **What agent observed instead**: Picked train-food-service based on the "reGetTrainFoodListResult" log phrase heuristic, even though train-food-service showed 200-OK traces.
- **Proximate cause**: victim caller mistaken for failed dependency

---

## case_4081  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on ts-order-other-service (pod `ts-order-other-service-78c95666f-lzr8f`). When order-other was killed, its callers (seat-service, which invokes `POST /orderOtherService/orderOther/...`) propagated errors upward. The trace chain loadgenerator → ui-dashboard → travel-plan → route-plan → travel2 → seat-service surfaces errors in seat-service because seat-service's order-other calls failed; seat-service itself was fine.

### (2) What the agent did
Round 14's think_tool: "Looking at the trace data, I can see the call chain: loadgenerator → ts-ui-dashboard → ts-travel-plan-service → ts-route-plan-service → ts-travel2-service → ts-seat-service... The errors appear in multiple services. The ts-seat-service has the most errors (96 Error status codes)... ts-seat-service spans have ~3-4 second durations." The agent treated seat-service as the deepest error-emitter in the sampled trace and anchored there, never stepping one hop further to order-other-service. ts-order-other-service's pod-kill state was outside the agent's sampled call path. Final answer: ts-seat-service.

### (3) Divergence
- **Pivot round**: 14
- **What agent should have observed**: ts-order-other-service container-kill state — it is called by seat-service in the real dependency graph and is a GT parent of the cascade.
- **What agent observed instead**: Stopped at seat-service as the deepest service with Error-status spans in the sampled trace.
- **Proximate cause**: deepest error node blamed over upstream killer

---

## case_4151  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress on `ts-route-service.RouteController.deleteRoute` (mem_type=1). Route-service is a callee of ts-route-plan-service (`GET /routeservice/routes/...` calls) and ts-travel-service (`GET /travelservice/routes/...`). When route-service stalled under memory pressure, both callers surfaced errors; in particular, travel-service handling `GET /travelservice/routes/{tripId}` failed because it delegates to route-service. Route-service itself emitted few trace errors.

### (2) What the agent did
Round 49's think_tool traced trace `65e7779651...`: loadgenerator → ui-dashboard → travel-plan-service → route-plan-service → ts-travel-service. "The error originates from ts-travel-service when it receives the GET request from ts-route-plan-service. The ts-travel-service is failing on 'GET /api/v1/travelservice/routes/{tripId}' endpoint... The ROOT CAUSE is ts-travel-service because: 1) It's the deepest service in the call chain showing errors; 2) The error spans in ts-travel-service are for GET /api/v1/travelservice/routes/{tripId}." The `/travelservice/routes/{tripId}` endpoint name literally references `routes` — which travel-service computes by calling route-service. The agent stopped one hop short. Final answer: ts-travel-service.

### (3) Divergence
- **Pivot round**: 49
- **What agent should have observed**: ts-route-service JVM memory fingerprint — travel-service's `/travelservice/routes/{tripId}` endpoint delegates to route-service, which is the injected target.
- **What agent observed instead**: Stopped at travel-service as "the deepest service in the call chain showing errors" without probing travel-service's own downstream route-service calls.
- **Proximate cause**: error-surfacing caller blamed over stressed dep

---

## case_4258  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on ts-contacts-service. The `GET /contactservice/contacts/account/{accountId}` endpoint is served by ts-ui-dashboard forwarding to ts-contacts-service. When contacts-service's container was killed, ui-dashboard's calls to it timed out (~3.5s) and surfaced 20 HTTP 503s. Contacts-service emitted no traces because the pod was down; ui-dashboard's own logs were access logs showing the 503 responses it issued.

### (2) What the agent did
Round 53's think_tool: "ts-ui-dashboard has only INFO level logs (1775), no ERROR logs in normal data. In abnormal: 1162 INFO + 20 ERROR logs — correspond to the 20 503 responses... ts-contacts-service is working fine (all 200 responses)... duration is consistently ~3.5 seconds, suggesting a timeout... the root cause is ts-ui-dashboard itself. It's returning 503 for some requests, possibly due to internal resource exhaustion, rate limiting, or a bug." The agent observed that ts-contacts-service had only 200-OK traces (survivorship bias — killed pod absent) and concluded contacts-service was "working fine," then blamed ts-ui-dashboard. Final answer: ts-ui-dashboard.

### (3) Divergence
- **Pivot round**: 53
- **What agent should have observed**: ts-contacts-service pod-kill state — the absence of contacts-service trace spans during the injection window, combined with ui-dashboard's 3.5s timeouts on contactservice URLs, is the fingerprint of a dead contacts pod.
- **What agent observed instead**: Read the surviving 200-OK traces as "contacts-service healthy" and blamed ui-dashboard as "returning 503 with no connectivity errors."
- **Proximate cause**: upstream 503s blamed dead container healthy

---

## case_4311  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress on `ts-payment-service.PaymentController.addMoney` (mem_type=2). Payment-service is called by ts-inside-payment-service via `POST /paymentservice/payment/...`. When payment-service stalled under memory pressure, inside-payment-service's calls received "503... delayed connect error: Connection refused" from Istio and logged the Envoy proxy error. Payment-service itself emitted few trace errors.

### (2) What the agent did
Round 33's think_tool: "ts-inside-payment-service is getting 503 'Service Unavailable' with 'Connection refused'... The error POST spans in ts-inside-payment-service have no child spans, meaning the call never reached ts-payment-service... ts-payment-service metrics show healthy (deployment available = 1.0, container ready = 1.0)... ts-payment-service traces all show 'Unset' status (successful). The issue is that ts-inside-payment-service cannot reliably connect to ts-payment-service. This is an Envoy proxy error... payment-service is being overloaded or the pod is being terminated." The agent correctly identified the connectivity direction (inside-payment → payment) and even named payment-service as "possibly overloaded," yet still labeled inside-payment-service as the root cause because payment-service's traces showed "Unset/healthy." Final answer: ts-inside-payment-service.

### (3) Divergence
- **Pivot round**: 33
- **What agent should have observed**: ts-payment-service JVM memory fingerprint — the Envoy "upstream connect error" inside-payment logs explicitly name payment-service as the target; "healthy metrics" at a coarse level doesn't rule out JVM GC pauses.
- **What agent observed instead**: Treated payment-service's 200-OK "Unset" traces (the surviving requests) as evidence of full health and blamed inside-payment-service as the error-reporter.
- **Proximate cause**: caller blamed for 503s from stressed payment

---

## case_4353  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress on `ts-station-service.StationServiceImpl.queryForIdBatch` (mem_type=1). Station-service is called by ts-basic-service during travel data lookups. When station-service stalled, basic-service's calls to it received 503 "Connection refused" and basic-service logged 240 Error-status traces. Downstream travel-service/travel2-service/preserve-service got 504 Gateway Timeouts from basic-service.

### (2) What the agent did
Round 52's think_tool compiled: "ts-basic-service is the FIRST service to show errors (first SEVERE at 01:58:07)... ts-travel-service/travel2-service: first errors at 01:59:04... ts-basic-service is returning 503 on its GET calls to downstream services... the issue appears to be within ts-basic-service itself — possibly a configuration issue, resource exhaustion, or network connectivity problem specific to ts-basic-service." The agent correctly identified basic-service's 503s as the first chronological anomaly but read "basic-service calling downstream and failing" as "basic-service is the problem" rather than "basic-service's downstream (station-service) is the problem." Final answer: ts-basic-service.

### (3) Divergence
- **Pivot round**: 52
- **What agent should have observed**: ts-station-service JVM memory fingerprint — basic-service's logs explicitly list its failing downstreams (route-service, config-service, station-service, train-service), and station-service was the injection target.
- **What agent observed instead**: Treated basic-service as root based on "highest error count (240) and earliest timestamp."
- **Proximate cause**: highest error count blamed not upstream injected

---

## case_4463  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill was applied to ts-food-service, but the true GT root cause (from DB meta) is ts-config-service — the injection triggered a cascading dependency failure where ts-config-service (which ts-food-service reads configuration from at startup) became unreachable/unresponsive for the food-service's restart cycle. Downstream: ui-dashboard saw 502 "connection refused" to food-service, and food-service's startup retries surfaced "Get Food Request Failed" + RabbitMQ errors.

### (2) What the agent did
Round 53's think_tool: "ts-food-service is the service with the most errors (311 ERROR logs)... ts-ui-dashboard shows 502 errors with 'connection refused' to 10.102.8.75:8080 — this is the ts-food-service IP... ui-dashboard errors start at 09:17:43 (connection refused), ts-food-service errors start at 09:18:34... ts-food-service shows HIGH_LATENCY (normal ~400ms, abnormal ~1900ms)... The evidence points to ts-food-service as the root cause." The agent correctly saw food-service being unreachable (matching the injected service), but missed the config-dependency layer — ts-food-service was actually killed BY the injection; the real root cause in the GT meta is ts-config-service which food-service depends on for bootstrap. Final answer: ts-food-service.

### (3) Divergence
- **Pivot round**: 53
- **What agent should have observed**: ts-config-service state during the injection window — the GT root cause is the config dependency, not the killed food-service itself.
- **What agent observed instead**: Stopped at the killed injection-target food-service based on its error-log volume and ui-dashboard's 502-refused signature.
- **Proximate cause**: stopped at injected service ignoring config dependency

---

## case_4707  [HTTPFault / HTTPResponseReplaceBody]

### (1) What really happened
HTTPResponseReplaceBody (body_type=1) on route `ts-seat-service → POST /orderOtherService/orderOther/* → ts-order-other-service`. Seat-service receives corrupted JSON bodies from order-other-service and logs JSON parse errors ("Unexpected character ('x')"). GT root causes: ts-seat-service + ts-order-other-service (the injected edge). ts-order-service is a separate peer that was NOT involved — but shares a similar name prefix.

### (2) What the agent did
Round 20's think_tool: "ts-seat-service logs reveal TWO types of errors: Connection reset when calling ts-order-service... JSON parse error when extracting response... ts-seat-service is calling ts-order-service and getting: Connection resets; Malformed JSON responses (starting with 'x' character - possibly an error page or garbage data). The chain is now clear: ts-order-service (ROOT CAUSE) → ts-seat-service → ts-travel2-service → ts-route-plan-service → ts-travel-plan-service → ts-ui-dashboard. ts-order-service is the origin of the failure." The agent misread log entries — seat-service was calling `ts-order-other-service` (the injected edge target), not `ts-order-service`. The URL string `order-other-service` contains "order-service" as a substring, and the agent elided the distinction. Final answer: ts-order-service.

### (3) Divergence
- **Pivot round**: 20
- **What agent should have observed**: The exact URL in seat-service SEVERE logs (`http://ts-order-service:8080/api/v1/orderservice/order/tickets` is one path; the injected path is `/api/v1/orderOtherService/orderOther/*` against ts-order-other-service). Seat-service has TWO sets of errors from two callees.
- **What agent observed instead**: Conflated order-service and order-other-service, read the "ts-order-service" prefix once and committed to it as the origin.
- **Proximate cause**: blamed upstream seat-service complained about

---

## case_4758  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress on `ts-travel2-service.TravelServiceImpl.getTripAllDetailInfo` (mem_type=2). Travel2-service stalled under memory pressure; its caller ts-route-plan-service attempted `POST /travel2service/trips/left` and `/trips/routes` and got "Connection refused" from Istio (proxy timing out on the stalled travel2 pod). Route-plan-service logged 40 SEVERE entries with "Connection refused" to travel2-service. Travel2-service itself showed few HTTP-level trace errors.

### (2) What the agent did
Round 32's think_tool: "ts-route-plan-service has 40 SEVERE errors with 'Connection refused' when calling http://ts-travel2-service:8080/api/v1/travel2service/trips/left and /trips/routes... ts-travel2-service shows 0 errors in traces, meaning it's working when it receives requests... The root cause service is ts-route-plan-service because: 1) It's the first service in the chain that shows errors (123 errors); 2) It cannot reach its dependency (ts-travel2-service); 3) The errors propagate from ts-route-plan-service → ts-travel-plan-service → ts-ui-dashboard." The agent explicitly saw that route-plan was reporting connection refused TO ts-travel2-service, noted that travel2-service appeared healthy in surviving traces, and then declared route-plan the root cause because "failures originate where observable in trace data." Final answer: ts-route-plan-service.

### (3) Divergence
- **Pivot round**: 32
- **What agent should have observed**: ts-travel2-service JVM memory-stress signature — route-plan's 40 SEVERE logs literally name travel2-service as the connection-refused target; absence of travel2 trace errors is the stalled-pod survivorship signature, not proof of health.
- **What agent observed instead**: Treated route-plan-service's "first error-emitter" status and travel2-service's "0 errors in surviving traces" as evidence that route-plan was the true origin.
- **Proximate cause**: blamed connection-refused reporter not refusing service

---
agentId: a34ea2ae813cd56a6 (use SendMessage with to: 'a34ea2ae813cd56a6' to continue this agent)
<usage>total_tokens: 166102
tool_uses: 26
duration_ms: 448290</usage>

## case_130  [NetworkChaos / NetworkCorrupt]

### (1) What really happened
NetworkCorrupt was injected between `ts-order-other-service` and `mysql` (corrupt=47%, correlation=82, direction=both). The fault manifested as massive DB round-trip degradation: `db.client.connections.wait_time` z=4449, `db.client.connections.use_time` z=270, and the `SELECT ts.orders_other` span showed latency ratio 797x abnormal-vs-normal. Order-other endpoints (`/api/v1/orderOtherService/orderOther/refresh`, `/tickets`, `/security/*`) all showed `high_avg_latency, high_p99_latency`, and only three Error-status spans existed in the whole window, all on loadgenerator calling order-other-service. Infrastructure signals (container high_gc_pressure, high_http_latency) confirmed ts-order-other-service as the epicenter.

### (2) What the agent did
Rounds 1-6 ran schema discovery and a generic abnormal_logs scan, sorted by count and then by earliest time. Round 6 surfaced pre-existing `ts-food-service` errors: `[AddFoodOrder][send delivery info to mq error][exception: org.springframework.amqp.AmqpConnectException]` and notification/delivery `Failed to check/redeclare auto-delete queue(s)`. At Round 7 the agent wrote: "The earliest errors are in ts-food-service related to RabbitMQ connection failures... Connection refused indicates the service cannot connect to a message queue" and committed to this hypothesis. The subsequent 34 rounds never drilled into ts-order-other-service's DB connection metrics or the SELECT-span latencies; the final causal graph hallucinated ts-food-service → ts-delivery/notification/preserve as the root-cause chain.

### (3) Divergence
- **Pivot round**: 7
- **What agent should have observed**: `ts-order-other-service` `db.client.connections.wait_time` z=4449 and the 797x latency ratio on `SELECT ts.orders_other` — the canonical signature of the mysql-bound NetworkCorrupt injection. The top-20 span footprint already showed `/orderOtherService/orderOther/refresh` at 904ms vs 11ms normal in Round 1's data.
- **What agent observed instead**: Anchored on the earliest-appearing RabbitMQ AmqpConnectException in ts-food-service logs (Round 6), which was pre-existing background noise unrelated to the injected endpoint.
- **Proximate cause**: anchored on RabbitMQ AmqpConnectException noise

---

## case_283  [NetworkChaos / NetworkBandwidth]

### (1) What really happened
NetworkBandwidth throttling was injected on `ts-station-service → mysql` traffic (rate=470142, limit=8404, buffer=6640, direction=from). This starved ts-station-service's DB connection to mysql, driving `hubble_http_request_duration_p99_seconds` on ts-station-service to z=358 (7.7ms→623ms). No direct log errors were emitted by ts-station-service because the fault was at the bandwidth/TC layer; the signal lived in HTTP duration histograms and span latency against the station endpoints. Pre-existing background noise dominated the logs: ts-consign-service had 352 SEVERE `query did not return a unique result: 2` (chronic NonUniqueResultException), plus the ambient RabbitMQ AmqpConnectException cluster on food/notification/delivery.

### (2) What the agent did
Rounds 1-5 did schema + log volume queries. At Round 6 the agent wrote: "The most critical error appears to be in ts-consign-service with the database NonUniqueResultException (352 occurrences). This could be the root cause" — anchoring on pure count. The agent never queried ts-station-service's HTTP duration percentile metrics or checked per-service span latency deltas for the injection window. Downstream rounds only validated that ts-consign-service appeared in the failing call chain, producing a final graph with `ts-consign-service → ts-ui-dashboard → loadgenerator` and no mention of ts-station-service or mysql.

### (3) Divergence
- **Pivot round**: 6
- **What agent should have observed**: ts-station-service `hubble_http_request_duration_p99_seconds` jumping from 7.7ms to 623ms (z=358) and the station-service span latency degradation — the specific bandwidth-throttle fingerprint on the injected source service.
- **What agent observed instead**: Latched on the 352-count SEVERE log pattern in ts-consign-service, which is a known chronic background anomaly unrelated to the bandwidth injection.
- **Proximate cause**: anchored on consign SEVERE error count

---

## case_315  [HTTPFault / HTTPResponseDelay]

### (1) What really happened
HTTPResponseDelay of 605ms was injected at `ts-travel-plan-service` on `GET /api/v1/trainservice/trains/byName/*` server-side (affecting the ts-train-service → ts-travel-plan-service response path). Downstream, ts-seat-service saw `http.server.request.duration` explode to z=1387 (19ms→7.5s) and `http.client.request.duration` to z=2732, and `ts-travel-service.db.client.connections.use_time` z=1173, indicating propagating connection-pool saturation from the delayed byName call. The fault was a pure latency signal on travel-plan-service's train-service-facing endpoint; no ERROR logs were emitted by GT services.

### (2) What the agent did
Rounds 1-6 surveyed the abnormal_logs volume. At Round 7 the agent concluded: "ts-food-service errors mention 'UnknownHostException: ts-rabbitmq' — this indicates a DNS/network issue connecting to RabbitMQ. This could be the root cause." It pursued this for 20+ rounds, then pivoted late to ts-route-plan-service based on trace-span latency but never identified ts-travel-plan-service/ts-train-service. Final output: `ts-route-plan-service` as RC, missing both GT services entirely.

### (3) Divergence
- **Pivot round**: 7
- **What agent should have observed**: The HTTP duration histogram anomalies centered on ts-seat-service/ts-travel-service (z=1387, 2732, 1173) indicating upstream latency propagation from the travel-plan-service byName endpoint, plus span latency on `RoutePlanController.getQuickestRoutes` and travel-plan-service endpoints.
- **What agent observed instead**: Anchored on ts-food-service `UnknownHostException: ts-rabbitmq` DNS errors in Round 7, pre-existing noise entirely unrelated to the HTTPResponseDelay injection.
- **Proximate cause**: anchored on RabbitMQ DNS errors

---

## case_323  [NetworkChaos / TimeSkew]

### (1) What really happened
TimeSkew injection on `ts-travel-plan-service` pod (time_offset=-84s) shifted clock backward by 84s, disrupting time-dependent logic. GT root-cause is ts-travel-plan-service alone. The signal was subtle: ts-order-other-service `jvm.gc.duration` z=2415 (0.25→2.66s) and broadly increased GC pressure across services as time-dependent caches and retries misbehaved. There were no prominent error logs tied directly to the skew — it was a diffuse downstream impact.

### (2) What the agent did
The agent ran 39 rounds exploring logs, traces, and metrics broadly. It identified ts-route-plan-service had 4.33s avg latency in histogram data. At Round 40 it wrote: "I found a critical clue! ts-route-service has a very high queueSize with avg 29.4 max 209. This is significantly higher than all other services" and committed to ts-route-service, treating the queueSize outlier as the smoking gun without considering that TimeSkew wouldn't present as queueSize growth and without ever querying ts-travel-plan-service clock-relative metrics. Final graph listed ts-route-service + ts-route-plan-service + ts-travel-plan-service with HIGH_LATENCY but ts-route-service as primary RC.

### (3) Divergence
- **Pivot round**: 40
- **What agent should have observed**: TimeSkew has no canonical metric fingerprint; the agent should have weighted the injection endpoint (the affected API is `travelPlanService`, and ts-travel-plan-service appeared in the endpoint prefix) over a queueSize outlier in a peripheral service.
- **What agent observed instead**: Anchored on ts-route-service `queueSize` max 209 at Round 40 — an outlier in a metric that doesn't correlate with time-skew faults.
- **Proximate cause**: anchored on ts-route-service queueSize outlier

---

## case_864  [HTTPFault / HTTPResponseReplaceCode]

### (1) What really happened
HTTPResponseReplaceCode injection on `ts-travel-service` rewrote `GET /api/v1/routeservice/routes/*` responses (affecting ts-travel-service's view of ts-route-service replies). GT services are ts-travel-service and ts-route-service. The anomaly expressed as downstream error-code mismatches and cascading 500s through ts-route-plan-service → ts-travel-plan-service. The data's `k8s.pod.phase=2` values do NOT mean "not running" — they are normal phase-enum values that happen to differ in steady state (pod phase encoding in OpenTelemetry includes multiple healthy values).

### (2) What the agent did
Through 48 rounds the agent gathered evidence and hypothesized ts-basic-service. At Round 49 it queried k8s.pod.phase, found several pods with phase=2, and wrote: "This is the smoking gun! ts-basic-service and ts-seat-service pods are not running (phase=2, which typically means Pending, Failed, or some non-Running state)." It misinterpreted the phase enum and built a final causal chain pointing at ts-basic-service as UNAVAILABLE. GT services ts-travel-service and ts-route-service never appeared in the final graph.

### (3) Divergence
- **Pivot round**: 49
- **What agent should have observed**: HTTP status-code anomalies on `ts-travel-service`'s calls to `/api/v1/routeservice/routes/*` — the specific injected endpoint. Pod phase values in OpenTelemetry are an enum where the same numeric value can persist across normal operation; a step-change in phase across the injection window, not the absolute value, is what matters.
- **What agent observed instead**: At Round 49 misread pod.phase=2 as non-Running across 5 pods, ignoring that this value was also present in the normal window baseline.
- **Proximate cause**: misread pod.phase=2 as not running

---

## case_1143  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill was injected on ts-food-service's JVM container (pod `ts-food-service-5fd45cf66d-nljst`). GT root cause is ts-food-service. The kill caused JVM restart churn: `jvm.class.loaded` on ts-food-service z=7001 (1.25→6705), container filesystem usage dropped to 428MB, and the killed container logged `UnknownHostException: ts-rabbitmq` as it came back up because startup retries hit DNS-lookup before the network reconciled. The RabbitMQ "failure" was a *symptom* of the food-service container being killed and restarting — not an infrastructure issue.

### (2) What the agent did
Rounds 1-6 surveyed logs. At Round 7 the agent wrote: "UnknownHostException: ts-rabbitmq error in ts-food-service suggests that the RabbitMQ service is unavailable or cannot be resolved. This could be the root cause affecting food-service operations." It then pursued ts-rabbitmq for the remaining rounds, concluding `ts-rabbitmq` was UNAVAILABLE despite the ts-food-service JVM class-load z-score being among the highest in the entire metrics parquet.

### (3) Divergence
- **Pivot round**: 7
- **What agent should have observed**: `ts-food-service.jvm.class.loaded` going from 1.25 to 6705 (z=7001) — the canonical JVM-container-restart fingerprint. The pod name `ts-food-service-5fd45cf66d-nljst` in the injection target should have been correlated with container metrics.
- **What agent observed instead**: At Round 7 anchored on `UnknownHostException: ts-rabbitmq` inside ts-food-service logs, which was DNS noise emitted during the container's post-kill restart sequence.
- **Proximate cause**: RabbitMQ DNS noise from killed JVM container

---

## case_1421  [NetworkChaos / DNSRandom]

### (1) What really happened
DNSRandom chaos was injected on `ts-station-service` targeting domain `mysql` — randomizing DNS lookups for mysql from ts-station-service's perspective. GT services: ts-station-service and mysql. The signature is ts-station-service DB-connection errors and latency on station endpoints, not broad RabbitMQ noise. Consign-service's 377 SEVERE `NonUniqueResultException` and food-service's RabbitMQ UnknownHostException were pre-existing background noise present in both normal and abnormal windows (normal errors: 596 vs abnormal: 235 per the log delta).

### (2) What the agent did
Rounds 1-6 did log aggregations. At Round 7: "ts-consign-service has 377 SEVERE errors... ts-food-service has 197 ERROR entries... UnknownHostException: ts-rabbitmq." The agent picked the loudest count (ts-consign-service) and cross-referenced it to the incident traces. Final answer: `ts-consign-service` HIGH_ERROR_RATE as root cause. The ts-station-service → mysql DNS-error pattern was never explicitly queried even though the injected domain was `mysql`.

### (3) Divergence
- **Pivot round**: 7
- **What agent should have observed**: ts-station-service logs mentioning mysql DNS or connection failures (`java.net.UnknownHostException: mysql`), and ts-station-service HTTP latency anomalies tied to the injection window.
- **What agent observed instead**: At Round 7 the agent anchored on the loudest error log (`ts-consign-service` 377 SEVERE) which is known chronic background noise, plus the RabbitMQ cluster.
- **Proximate cause**: loudest error log anchored to wrong service

---

## case_1515  [HTTPFault / HTTPRequestDelay]

### (1) What really happened
HTTPRequestDelay of 4765ms was injected at `ts-travel-service` on its outbound `POST /api/v1/seatservice/seats/left_tickets` calls to ts-seat-service. GT services: ts-travel-service and ts-seat-service. The signature was `ts-travel-service.db.client.connections.use_time` z=128 (166→7227) indicating connection-pool starvation from the 4.7s delay, plus `ts-order-service.hubble_http_request_duration_p95` z=129 and `ts-config-service.jvm.gc.duration` 3.34s. Pre-existing AmqpConnectException and "UnknownHostException: ts-rabbitmq" on food-service were unrelated chronic noise.

### (2) What the agent did
Rounds 1-5 surveyed volume. At Round 6 the agent wrote: "Critical Finding: The error `UnknownHostException: ts-rabbitmq: Name or service not known` in ts-food-service indicates a DNS resolution failure for the RabbitMQ service. This is likely the root cause." It never drilled into ts-travel-service's outbound timing or the `/seatservice/seats/left_tickets` span's latency. Final graph: `rabbitmq UNAVAILABLE` — missing both GT services.

### (3) Divergence
- **Pivot round**: 6
- **What agent should have observed**: `ts-travel-service.db.client.connections.use_time` at 7.2s (z=128) and the specific `POST /api/v1/seatservice/seats/left_tickets` span latency spike — the direct fingerprint of the request-delay injection.
- **What agent observed instead**: At Round 6 anchored on `UnknownHostException: ts-rabbitmq` in food-service logs as a "DNS resolution failure" root cause.
- **Proximate cause**: DNS error log anchored on RabbitMQ

---

## case_1948  [PodChaos / ContainerKill]

### (1) What really happened
ContainerKill on `ts-preserve-service` pod. GT root cause: ts-preserve-service. The signature was `ts-preserve-service.container.filesystem.usage` dropping from 466MB to 423MB (z=43861), indicating container restart. Preserve-service was the incident endpoint (affected API: `/api/v1/preserveservice/preserve`). The RabbitMQ-related errors in delivery/notification/food services were pre-existing and appeared in both normal and abnormal windows.

### (2) What the agent did
Through 33 rounds the agent gathered evidence. At Round 34, building a timeline: "ts-delivery-service 01:21:31.175 (EARLIEST)... ts-food-service... ts-notification-service... All three earliest failing services are related to RabbitMQ messaging infrastructure. Root Cause: RabbitMQ (ts-rabbitmq) becomes unavailable." The agent used "earliest error timestamp" as the key heuristic — but those RabbitMQ errors were chronic. Preserve-service's container kill (the actual injection) manifested on slightly different timing. Final: ts-delivery-service HIGH_ERROR_RATE as RC.

### (3) Divergence
- **Pivot round**: 34
- **What agent should have observed**: `ts-preserve-service.container.filesystem.usage` 43MB drop and the preserve-service container restart signature, directly tied to the incident endpoint `/api/v1/preserveservice/preserve`.
- **What agent observed instead**: At Round 34 treated "earliest-timestamp" RabbitMQ queue errors in delivery/notification as the root signal, ignoring that these errors persisted chronically in the system.
- **Proximate cause**: RabbitMQ DNS errors appeared earliest in timeline

---

## case_2092  [HTTPFault / HTTPRequestReplacePath]

### (1) What really happened
HTTPRequestReplacePath was injected at `ts-seat-service` rewriting outbound `POST /api/v1/orderservice/order/*` request paths. GT services: ts-seat-service and ts-order-service. The injection caused JVM class-loading churn on ts-route-plan-service z=21000 (14649→14670) and preserve-service z=20250 — as those services hit unexpected 404/500 responses on the rewritten paths and loaded exception-handling classes. Direct signature: path-rewrite-induced HTTP errors on the order-service endpoints.

### (2) What the agent did
Through 43 rounds the agent accumulated evidence. At Round 44: "Root Cause: ts-rabbitmq service is unavailable (DNS resolution failure - UnknownHostException). Impact Chain: ts-food-service... ts-delivery-service... ts-notification-service... ts-seat-service - Fails (04:49:34) with 403 Forbidden (likely cascading effect)." The agent noticed ts-seat-service 403s but dismissed them as "cascading" rather than injection-caused. Final RC: `ts-rabbitmq UNAVAILABLE`.

### (3) Divergence
- **Pivot round**: 44
- **What agent should have observed**: The 403 Forbidden on ts-seat-service was NOT cascading — it was the direct consequence of path rewriting causing auth-rejection on the rewritten `/api/v1/orderservice/order/*` paths. The jvm.class.loaded spikes on route-plan/preserve services indicated cascading exception handling from bad-path responses.
- **What agent observed instead**: At Round 44 UnknownHostException in food-service anchored the diagnosis to RabbitMQ; treated ts-seat-service's 403s as side-effects.
- **Proximate cause**: UnknownHostException anchored diagnosis to RabbitMQ

---

## case_2512  [NetworkChaos / NetworkCorrupt]

### (1) What really happened
NetworkCorrupt between ts-food-service and ts-station-food-service (corrupt=95%, direction=from). GT: ts-food-service and ts-station-food-service. The signature was massive latency on ts-food-service calls: `http.client.request.duration` z=1549 (0.016→20.8s) and `http.server.request.duration` z=1338 (0.033→38.2s) — the food-service span taking ~130s total with children completing in ms was the textbook "outbound call is corrupted, hanging at TCP layer" fingerprint. The station-food-service interaction was the exact injection point.

### (2) What the agent did
Rounds 1-10 gathered trace and log data. At Round 11 the agent made the critical inference: "ts-food-service POST span has duration 129s with children in ms — the POST span must be waiting for something else not captured as a trace child. From logs: send delivery info to mq error with UnknownHostException: ts-rabbitmq. Hypothesis: ts-food-service is trying to communicate with ts-rabbitmq (message queue). The DNS lookup for ts-rabbitmq is failing or timing out. This causes the POST operation to hang for ~130 seconds." The agent had the *correct observation* (food-service hangs on an outbound call) but attributed the hang to RabbitMQ DNS rather than the ts-station-food-service injection.

### (3) Divergence
- **Pivot round**: 11
- **What agent should have observed**: `ts-food-service → ts-station-food-service` trace-span latency (the station-food-service was explicitly in food-service's call chain per traces). The 130s hang on food-service's POST child span was the corruption signal at the station-food-service TCP connection.
- **What agent observed instead**: At Round 11 latched the 130s hang onto the `UnknownHostException: ts-rabbitmq` log line, treating RabbitMQ DNS as the answer.
- **Proximate cause**: latched onto RabbitMQ DNS error in logs

---

## case_2713  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress was injected on `ts-security-service.SecurityServiceImpl.deleteSecurityConfig` (mem_type=1). GT: ts-security-service. The signature was extreme: `ts-security-service.jvm.class.loaded` z=6526 (0→6526), `container.filesystem.usage` going 466MB→531MB, and `jvm.class.count` DROPPING from 19517 to 16546 (z=2971B) — the canonical JVM-under-memory-stress thrashing pattern where class unload/reload cycles fire rapidly. Preserve-service then cascaded with "Order already exists" as security-config-check calls timed out.

### (2) What the agent did
Through 79 rounds the agent ran elaborate analysis. At Round 80 final analysis: "EARLIEST error is ts-food-service's RabbitMQ UnknownHostException at 19:39:48.903. This is 638ms BEFORE ts-order-service's Order already exists error. RabbitMQ issue causes ts-food-service to fail, which may trigger retry logic. Retries cause duplicate order creation attempts. Root Cause Service: ts-food-service." The agent used earliest-timestamp heuristic as tiebreaker and picked ts-food-service despite security-service's extraordinary JVM metrics being in the data.

### (3) Divergence
- **Pivot round**: 80
- **What agent should have observed**: `ts-security-service.jvm.class.loaded` z=6526 and the paradoxical `jvm.class.count` drop from 19517→16546 — the exact JVMMemoryStress fingerprint, coincident with the deleteSecurityConfig call path that preserve-service invokes as part of order security checks.
- **What agent observed instead**: At Round 80 anchored on ts-food-service's RabbitMQ UnknownHostException at 19:39:48.903 as earliest-timestamp.
- **Proximate cause**: anchored on RabbitMQ DNS errors as earliest

---

## case_2716  [NetworkChaos / NetworkCorrupt]

### (1) What really happened
NetworkCorrupt between ts-station-service and ts-basic-service (corrupt=52%, correlation=26, direction=to). GT: ts-station-service and ts-basic-service. The signature was `ts-basic-service.http.server.request.duration` z=387 (31ms→1.25s) showing bad-packet-induced retries. `ts-ticket-office-service` was observed restarting (KILLED) during the window, but this was background infrastructure churn unrelated to the station↔basic corruption. The ts-news-service memory anomalies were also chronic noise.

### (2) What the agent did
Through 53 rounds the agent accumulated evidence. At Round 54: "While ts-food-service has the earliest error log entry, the errors are symptoms of a deeper issue. The ts-ticket-office-service container restarts indicate a fundamental infrastructure failure... Strongly suggests that ts-ticket-office-service failure is causing the RabbitMQ infrastructure to become unavailable, which then cascades." The agent built a speculative narrative that ts-ticket-office-service hosted RabbitMQ (no evidence of this) and declared it the infrastructure-level root cause.

### (3) Divergence
- **Pivot round**: 54
- **What agent should have observed**: `ts-basic-service.http.server.request.duration` z=387 and span-level corruption signatures on the ts-station-service → ts-basic-service edge. The ticket-office-service restart was coincident background churn, not causal.
- **What agent observed instead**: At Round 54 built a speculative causal chain from ts-ticket-office-service KILLED → RabbitMQ → downstream queue failures, despite zero evidence connecting ticket-office to RabbitMQ.
- **Proximate cause**: anchored on container restarts as infrastructure cause

---

## case_3059  [NetworkChaos / NetworkCorrupt]

### (1) What really happened
NetworkCorrupt between ts-order-service and ts-ui-dashboard (corrupt=48%, correlation=65, direction=both). GT: ts-order-service and ts-ui-dashboard. The signature was retries, GC pressure from retry-path exception handling (ts-order-other-service jvm.gc.duration 3.6s), and inside-payment-service queueSize 2.0. No direct trace-status errors because corruption caused TCP-level retransmits rather than application errors. ts-config-service showed a 3.49s GC pause but this was unrelated — it was a peripheral symptom.

### (2) What the agent did
Through 41 rounds the agent explored. At Round 42: "Looking at the histogram data: ts-config-service jvm.gc.duration min 3.492, max 3.492 (1 count). This is a 3.492 second GC pause! This is the root cause. The ts-config-service is experiencing long GC pauses." The agent anchored on a single-bucket GC pause outlier in ts-config-service (which was a single sample, not a pattern) and declared it the cause of cascading latency.

### (3) Divergence
- **Pivot round**: 42
- **What agent should have observed**: ts-order-service → ts-ui-dashboard span-level retry patterns and the inside-payment-service/security-service queueSize anomalies indicating back-pressure from the corrupted order-ui edge.
- **What agent observed instead**: At Round 42 anchored on a single-bucket 3.492s GC pause in ts-config-service — a peripheral service not on the injection path.
- **Proximate cause**: anchored on GC pause in unrelated service

---

## case_3112  [NetworkChaos / NetworkPartition]

### (1) What really happened
NetworkPartition between ts-preserve-service and ts-seat-service (direction=both). GT: ts-preserve-service and ts-seat-service. The signature was `ts-preserve-service.http.server.request.duration` z=421 (0.92→87s) — preserve-service hung waiting for partitioned seat-service calls, and widespread JVM CPU-utilization spikes (z=28, 27, 26 across wait-order/notification/food/inside-payment) as services piled up blocked threads. AmqpConnectException in food-service was pre-existing noise.

### (2) What the agent did
Through 36 rounds the agent analyzed. At Round 37: "ts-delivery-service and ts-notification-service only have ERROR logs (queue redeclaration failures) but no trace entries. This means they are likely background services... For the preserve endpoint incident: call chain loadgenerator → ts-ui-dashboard → ts-preserve-service → ts-food-service. ts-food-service fails with AMQP IOException when trying to send to MQ. This causes the preserve operation to fail... The root cause service is ts-food-service." The agent correctly identified preserve-service as the incident endpoint but misattributed preserve-service's failures to ts-food-service's AMQP errors rather than to the seat-service partition.

### (3) Divergence
- **Pivot round**: 37
- **What agent should have observed**: `ts-preserve-service.http.server.request.duration` jumping to 87s (z=421) — the partition-induced hang signature. Preserve-service's actual call chain for the failing endpoint includes ts-seat-service, not just ts-food-service.
- **What agent observed instead**: At Round 37 treated the preserve→food-service AMQP error as causal, despite AMQP errors being chronic and the 87s hang being partition-characteristic.
- **Proximate cause**: AMQP error noise misread as HTTP fault origin

---

## case_3222  [NetworkChaos / NetworkLoss]

### (1) What really happened
NetworkLoss between ts-seat-service and ts-order-other-service (loss=69%, correlation=49, direction=both). GT: ts-seat-service and ts-order-other-service. 69% packet loss caused TCP retransmits and connection pool exhaustion — specifically `ts-travel2-service.db.client.connections.pending_requests` z=1000 (0→1) and cascading HikariPool exhaustion on ts-travel2-service as a downstream symptom. The HikariPool exhaustion was a consequence, not the cause.

### (2) What the agent did
Through 36 rounds the agent probed. At Round 37: "ts-travel2-service has database connection pool exhaustion errors: 'HikariPool-1 - Connection is not available, request timed out after 30000ms'. This is the ROOT CAUSE! The HikariCP connection pool is exhausted." The agent anchored on a vivid, plausible-sounding error (HikariPool timeout) as root cause without asking *why* the pool was exhausted. Final RC: ts-travel2-service HIGH_ERROR_RATE.

### (3) Divergence
- **Pivot round**: 37
- **What agent should have observed**: Packet-loss signatures on the ts-seat-service → ts-order-other-service edge — span-level retransmit anomalies and `db.client.connections.pending_requests` on travel2 as *downstream* of loss, not origin.
- **What agent observed instead**: At Round 37 took the HikariPool exhaustion log at face value as "the root cause" without tracing upstream — classic local-failure anchoring.
- **Proximate cause**: HikariPool exhaustion noise anchored over loss

---

## case_3622  [NetworkChaos / NetworkDelay]

### (1) What really happened
NetworkDelay between mysql and ts-order-service (correlation=3, direction=both). GT: mysql and ts-order-service. The signature was `ts-order-service.db.client.connections.wait_time` z=1176 (0.4ms→772ms) and `db.client.connections.use_time` z=478 (7.3ms→1970ms) — textbook DB-latency starvation fingerprint. `http.server.request.duration` on ts-order-service at z=81 (25ms→4s) confirmed the order-service endpoint was the failing path. Inside-payment and seat-service showed secondary cascade.

### (2) What the agent did
Through 37 rounds. At Round 38: "First errors appear at 19:31:15.764 in ts-delivery-service - 'Attempting to connect to: [ts-rabbitmq:5672]', 'Failed to check/redeclare auto-delete queue(s)'. This is the earliest sign of trouble... Root Cause: ts-rabbitmq (DNS resolution failure / network unreachable)." The agent applied earliest-timestamp heuristic to ambient RabbitMQ errors again, completely missing that ts-order-service's DB-wait metric was 1976x normal.

### (3) Divergence
- **Pivot round**: 38
- **What agent should have observed**: `ts-order-service.db.client.connections.wait_time` at 772ms (z=1176) — the unmistakable mysql-delay fingerprint on the order-service → mysql connection.
- **What agent observed instead**: At Round 38 declared `ts-rabbitmq` DNS failure the root cause based on earliest-timestamp in delivery-service queue errors.
- **Proximate cause**: ambient RabbitMQ DNS errors drowned mysql signal

---

## case_3716  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress was injected on `ts-food-service.FoodController.home` (mem_type=2). GT: ts-food-service. The signature was `ts-food-service.container.filesystem.usage` z=294144B (466MB→761MB) — massive filesystem growth from JVM heap-dump / swap activity. The injected container then hit DNS resolution hiccups during pressure, producing `UnknownHostException: ts-rabbitmq` logs as a symptom of the stressed food-service container's network subsystem degrading.

### (2) What the agent did
Rounds 1-19 investigated. At Round 20: "Critical Finding: multiple services are failing to connect to ts-rabbitmq. This is a DNS resolution failure for the RabbitMQ service... ts-food-service has the most errors (256) - mainly 'Get the Get Food Request Failed!' and RabbitMQ connection issues... Key question: is ts-rabbitmq the root cause?" The agent saw the food-service error concentration (256 errors) but treated its DNS error as evidence of RabbitMQ infrastructure failure rather than of food-service being the injected target. Final: ts-rabbitmq UNAVAILABLE.

### (3) Divergence
- **Pivot round**: 20
- **What agent should have observed**: `ts-food-service.container.filesystem.usage` jumping 295MB (z=294144B) and the food-service JVM-stress fingerprint. The "UnknownHostException: ts-rabbitmq" was emitted BY the stressed food-service pod, pointing inward.
- **What agent observed instead**: At Round 20 interpreted ts-food-service DNS errors as evidence ts-rabbitmq was down, rather than as evidence food-service's JVM was thrashing.
- **Proximate cause**: JVM-stress MQ log noise anchored to RabbitMQ

---

## case_4070  [HTTPFault / HTTPResponseAbort]

### (1) What really happened
HTTPResponseAbort was injected at `ts-food-service` on outbound `GET /api/v1/trainfoodservice/trainfoods/*` — aborting ts-train-food-service responses to food-service. GT: ts-food-service and ts-train-food-service. The signature was `ts-food-service` logging "Unexpected end of file from server" when calling train-food-service (exactly what response-abort produces), while ts-train-food-service's own traces showed `Unset` status (successful processing) because the abort happened at the response send-back layer. Food-service also emitted RabbitMQ UnknownHostException as a side-effect.

### (2) What the agent did
Through 39 rounds the agent correctly identified: "ts-food-service starts getting 'Unexpected end of file from server' errors when calling ts-train-food-service... ts-train-food-service spans show 'Unset' status (successful completion). But ts-food-service is getting connection reset errors. This pattern typically indicates ts-train-food-service is processing requests successfully but the connection is being closed prematurely." At Round 40: "However, the MORE fundamental issue is the ts-rabbitmq DNS resolution failure. The UnknownHostException for ts-rabbitmq is the earliest error." The agent had the exact right trace-level observation then overrode it with earliest-timestamp DNS-error anchoring. Final: ts-rabbitmq.

### (3) Divergence
- **Pivot round**: 40
- **What agent should have observed**: The "Unexpected end of file from server" pattern in ts-food-service ↔ ts-train-food-service with train-food-service spans at `Unset` is the exact HTTPResponseAbort fingerprint — the agent SAW this but discarded it.
- **What agent observed instead**: At Round 40 reverted to ts-rabbitmq UnknownHostException as "earliest error" and committed to it despite the agent's own correct observation.
- **Proximate cause**: earliest DNS error noise anchored as cause

---

## case_4363  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress injected on `ts-train-food-service.TrainFoodApplication.restTemplate` (mem_type=2). GT: ts-train-food-service. The signature was extreme: `ts-train-food-service.container.filesystem.usage` z=341275 (466MB→808MB), `jvm.class.loaded` z=9715000 (0→9715) — enormous class-loading churn — and `jvm.class.count` DROPPING (19636→19395) the textbook memory-stress JVM thrashing pattern. Train-food-service's restTemplate method was specifically hit, causing downstream food-service to see intermittent failures and emit ambient RabbitMQ DNS noise.

### (2) What the agent did
Rounds 1-26 explored. At Round 27: "ts-rabbitmq service is unavailable - multiple services (ts-notification-service, ts-delivery-service, ts-food-service) are failing to connect to it with DNS resolution failures... But wait - the incident is about the foodservice API endpoint having SLO violations. The traces show that ts-food-service is returning errors. The root cause is that ts-rabbitmq is unavailable." The agent noted that train-food-service startup logs appeared at 04:05:40 (indicating restart) and the "intermittent failures" pattern, but dismissed train-food-service and picked ts-rabbitmq.

### (3) Divergence
- **Pivot round**: 27
- **What agent should have observed**: `ts-train-food-service.jvm.class.loaded` z=9715M and the class.count DROP from 19636→19395 (z=241B) — unmistakable JVM-memory-stress thrashing on the injected target. The startup logs at 04:05:40 the agent noted were the restart recovery from mem-stress.
- **What agent observed instead**: At Round 27 anchored on RabbitMQ DNS noise across delivery/notification/food services as the pervasive pattern.
- **Proximate cause**: rabbitmq DNS noise anchored away from injected

---

## case_4617  [JVMChaos / JVMCPUStress]

### (1) What really happened
JVMCPUStress injected on `ts-cancel-service.CancelServiceImpl.cancelFromOrder` (cpu_count=8). GT: ts-cancel-service. Signature: `ts-cancel-service.container.filesystem.usage` z=2547916B (466MB→3014MB), `jvm.class.loaded` z=35.75B (0→35.75) on cancel-service. The cancel-service got pegged at CPU under the stress, causing its cancelFromOrder method to hang. The incident endpoints involved cancel-service. Cancel spans should have shown extreme latency.

### (2) What the agent did
Through 34 rounds. At Round 35: "Root Cause: ts-rabbitmq is unavailable. The logs clearly show ts-notification-service and ts-delivery-service trying to connect to ts-rabbitmq:5672 but failing... ts-food-service has UnknownHostException: ts-rabbitmq: Name or service not known - DNS resolution failure. The root cause is ts-rabbitmq being unavailable - this is an infrastructure/service dependency issue." Despite the incident description mentioning cancel service, the agent explicitly acknowledged this then dismissed it: "The incident description mentions cancel service endpoints, but the actual root cause is the RabbitMQ infrastructure failure."

### (3) Divergence
- **Pivot round**: 35
- **What agent should have observed**: `ts-cancel-service.container.filesystem.usage` growing 2.5GB (z=2547916B) — a dramatic signal uniquely on cancel-service. Cancel-service cancelFromOrder span latency. The incident endpoints directly named cancel-service.
- **What agent observed instead**: At Round 35 acknowledged cancel-service was in the incident description then chose RabbitMQ anyway based on DNS-error pattern in food/notification/delivery.
- **Proximate cause**: anchored on RabbitMQ noise over cancel spans

---

## case_4841  [NetworkChaos / NetworkDelay]

### (1) What really happened
NetworkDelay between ts-station-service and mysql (correlation=82, direction=from). GT: ts-station-service and mysql. Signature: `ts-station-service.db.client.connections.wait_time` z=91387 (0.098→1335s) — one of the highest z-scores observed, plus `hubble_http_request_duration_p50_seconds` z=29596 (2.6ms→2.94s) and p90 z=11687 on ts-station-service. The station-service → mysql connection was directly affected. RabbitMQ DNS errors in food/notification/delivery were ambient background.

### (2) What the agent did
Through 23 rounds. At Round 24 final analysis: "ts-rabbitmq service is experiencing a DNS resolution failure. 'java.net.UnknownHostException: ts-rabbitmq: Name or service not known'. This means services cannot resolve the hostname ts-rabbitmq to an IP address... Root Cause: ts-rabbitmq (DNS_ERROR/UNAVAILABLE)." The agent stopped at the first clean-looking log pattern and never queried ts-station-service's extraordinary DB wait_time metric, which had an astronomical z=91387.

### (3) Divergence
- **Pivot round**: 24
- **What agent should have observed**: `ts-station-service.db.client.connections.wait_time` at 1335s (z=91387) — arguably the strongest fingerprint in the entire dossier, directly indicating mysql-bound connection delay from station-service.
- **What agent observed instead**: At Round 24 anchored on the `UnknownHostException: ts-rabbitmq` DNS pattern and declared ts-rabbitmq the infrastructure root cause.
- **Proximate cause**: RabbitMQ DNS noise over station-mysql delay

---

## case_341  [PodChaos / PodFailure]

### (1) What really happened
Pod-failure injection killed `ts-travel-service` (app_name: ts-travel-service, pod `ts-travel-service-6848b54676-98wth`). The pod went into restart loop, driving container memory usage from 797M→17M (z=158) and page faults z=49, so ts-travel-service spans (`POST /api/v1/travelservice/trips/left`, `TravelController.queryInfo`) simply stopped emitting (`missing_span, injection_affected`). Downstream callers of the missing service — ts-food-service (87 error spans), ts-route-plan-service (261 error spans with HTTP 503 "Connection refused") — were the visibly screaming victims. GT path: container|ts-travel-service → ts-travel-service → {ts-food-service, ts-route-plan-service, ts-travel-plan-service} → ts-ui-dashboard → loadgenerator.

### (2) What the agent did
Across 80 rounds the agent was drawn to the loudest downstream signals: ts-route-plan-service's 503 SEVERE log barrage and ts-food-service errors. At Round 67 it noticed ts-station-food-service was in the list of services "completely missing from abnormal_traces" alongside others. At Round 68 think_tool concluded: "ts-food-service started failing BEFORE ts-route-plan-service… ts-station-food-service is completely missing from abnormal_traces… root cause could be ts-station-food-service being down." It never interrogated ts-travel-service's own silence or its container restart metrics.

### (3) Divergence
- **Pivot round**: 68
- **What agent should have observed**: ts-travel-service container memory dropping 98% (z=158), page_faults z=49, and its spans flagged `injection_affected/missing_span` — the definitive PodFailure fingerprint on the actual GT service.
- **What agent observed instead**: applied the "silent service = root cause" heuristic to ts-station-food-service (a wholly unrelated absent service) while ignoring ts-travel-service's stronger silence signal (Round 68).
- **Proximate cause**: silence applied to wrong silent service

---

## case_572  [HTTPFault / HTTPResponsePatchBody]

### (1) What really happened
An HTTPResponsePatchBody fault corrupted response bodies from ts-train-food-service to ts-food-service on `GET /api/v1/trainfoodservice/trainfoods/*`. ts-food-service logged 139 "[getAllFood][reGetTrainFoodListResult][Get the Get Food Request Failed!]" entries plus 23 "send delivery info to mq error" entries. A coincidental, unrelated issue caused ts-consign-service to produce 366 Error-status spans (`ConsignRepository.findByOrderId` database contention) — this was pre-existing noise, NOT related to the injected food-service fault. GT path: ts-food-service/ts-train-food-service failure manifested primarily in ts-food-service logs, with propagation limited because food endpoints weren't the SLO-violating ones.

### (2) What the agent did
In 44 rounds the agent quickly latched onto the biggest raw error-span count. At Round 11 think_tool states verbatim: "ts-consign-service has the most Error status codes (366 errors)… This strongly suggests ts-consign-service is the root cause. The error count (366) matches the pattern we saw in logs (176 SEVERE errors…)." It then spent the remaining rounds rationalizing the consign-service hypothesis (DB issues) rather than examining the food-service log cluster or the `/trainfoodservice/trainfoods/*` injection vector.

### (3) Divergence
- **Pivot round**: 11
- **What agent should have observed**: The 139-count ts-food-service "Get Food Request Failed" error cluster pointing to corrupted trainfoods responses, plus the SLO endpoint mentioning food-service paths.
- **What agent observed instead**: ranked services by Error span count, picked the top (ts-consign-service 366 errors), anchored there from Round 11 onward.
- **Proximate cause**: picked highest raw error-span count service

---

## case_579  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress (mem_type=2) on `ts-inside-payment-service.CookieUtil.getCookieByName` drove jvm.class.loaded from 1.75→6592 (z=2972), page_faults z=604, filesystem.usage z=526, CPU z=210. The injected pod's spans went silent (`missing_span, injection_affected`) — that's why ts-inside-payment-service trace status shows "Unset" (no errors emitted because the method couldn't complete). ts-ui-dashboard faithfully returned HTTP 503 with 3.4–4.6s timeouts on `POST /api/v1/inside_pay_service/inside_payment` as the visible symptom. GT: container|ts-inside-payment-service → ts-inside-payment-service → ts-ui-dashboard → loadgenerator.

### (2) What the agent did
At Round 15 think_tool summarized: "Only ts-ui-dashboard (22 errors) and loadgenerator (4 errors) show attr_status_code='Error'. All other services show Unset status (which typically means no explicit error status was set)… ts-inside-payment-service: 2 ERROR logs… business logic errors, not infrastructure failures." It treated ts-inside-payment-service's Unset/near-silent state as health and concluded ts-ui-dashboard must be the root cause since that's where the 503s were actually rendered.

### (3) Divergence
- **Pivot round**: 15
- **What agent should have observed**: ts-inside-payment-service jvm.class.loaded spike 1.75→6592 (z=2972) + page_faults z=604 — the canonical JVM memory stress fingerprint, directly pointing at the injected service.
- **What agent observed instead**: read "Unset" trace status on the injected service as healthy (Round 15) and blamed ts-ui-dashboard, the span-boundary renderer of the 503.
- **Proximate cause**: injected service spans showed no Error status

---

## case_1114  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress (mem_type=2) on `ts-config-service.ConfigApplication.restTemplate` pushed jvm.class.loaded from 1.0→6477 (z=4579), page_faults z=165, filesystem.usage z=70T. ts-config-service calls were affected but the service returned successfully to most callers. The visible fallout landed on ts-seat-service which depends on ts-config-service for ticket-pool lookups: 117 error spans with HTTP 503 "upstream connect error… Connection refused" — because ts-seat-service's GET calls to ts-config-service timed out under GC pressure. GT propagation: container|ts-config-service → ts-config-service → ts-seat-service → {ts-travel-service, ts-travel-plan-service, ts-route-plan-service} → ts-ui-dashboard → loadgenerator.

### (2) What the agent did
At Round 73 the agent produced a "Final Analysis" think_tool: "ts-seat-service is the only service with Error status in traces (117 error spans)… ts-config-service shows NO errors in logs (0 ERROR level logs) and has 'Unset' status in traces, meaning it's working for other callers… ts-seat-service is trying to call ts-config-service but getting connection refused. However, ts-config-service is working fine for other services… ts-seat-service is the root cause because it's the first service in the chain showing Error status." The agent SAW the ts-seat→ts-config call-refused pattern but inverted causation.

### (3) Divergence
- **Pivot round**: 73
- **What agent should have observed**: ts-config-service jvm.class.loaded 1.0→6477 (z=4579) plus the "Connection refused" errors FROM callers TO ts-config-service pointing at it as the unresponsive origin.
- **What agent observed instead**: treated ts-config-service's Unset trace status as "working fine" and crowned ts-seat-service (the downstream victim rendering the 503s) as root cause (Round 73).
- **Proximate cause**: absence of error-status overrode causal trace

---

## case_1140  [NetworkChaos / NetworkBandwidth]

### (1) What really happened
NetworkBandwidth fault throttled traffic from ts-food-service to ts-ui-dashboard (rate=14664, limit=2596, direction=from). ts-food-service errors dropped because it simply couldn't get requests out, while ts-ui-dashboard saw new 503s (+10 errors). Coincidentally ts-consign-service had a background database issue ("query did not return a unique result") producing 176 SEVERE errors and 366 Error-status spans — a pre-existing noise pattern present in both normal and abnormal periods, unrelated to the network throttle. GT: ts-food-service / ts-ui-dashboard were the true victims of the bandwidth constraint.

### (2) What the agent did
At Round 9 think_tool declared: "ts-consign-service has 528 traces with status_code='Error' — by far the most errors… This strongly suggests ts-consign-service is the root cause. The error count (528) matches the pattern we saw in logs (176 SEVERE errors about 'query did not return a unique result')." The agent stopped at the amplitude peak and never checked which service was actually in the SLO-violating call path or whether the consign errors were pre-existing (normal_errors=0 but the SEVERE pattern was identical in normal logs).

### (3) Divergence
- **Pivot round**: 9
- **What agent should have observed**: ts-food-service's massive error-count DROP (−115, abnormal < normal — a sign of throttled throughput) combined with ts-ui-dashboard gaining 10 new 503 errors exactly during the injection window.
- **What agent observed instead**: selected ts-consign-service because it had the highest raw Error-status span count, ignoring call-path relevance (Round 9).
- **Proximate cause**: highest error count anchored to unrelated service

---

## case_1195  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress (mem_type=1) on `ts-order-other-service.OrderOtherServiceImpl.getOrderById` drove jvm.class.loaded 0.75→6506 (z=6794), page_faults z=189. ts-order-other-service slowed and began failing, which cascaded upstream through ts-preserve-service → ts-security-service (because ts-preserve-service's `GET /api/v1/securityservice/securityConfigs/{accountId}` call to ts-security-service timed out under pressure, producing 36 Error-status spans on ts-security-service). GT: ts-order-other-service is the origin; ts-security-service's 503 errors are a downstream cascade symptom.

### (2) What the agent did
At Round 10 the agent queried Error-status spans and found ts-security-service with 36 errors. Round 11 trace analysis showed ts-preserve-service calling ts-security-service returning 503. Subsequent rounds (16, 18, 35) dug into ts-security-service's "Connection refused" error and its downstream calls. The agent anchored on ts-security-service because it produced visible Error spans while ts-order-other-service (the true origin) showed only "Unset" trace status — no error propagation surfaced on the query the agent used (`attr_status_code='Error'`).

### (3) Divergence
- **Pivot round**: 10
- **What agent should have observed**: ts-order-other-service's z=6794 on jvm.class.loaded + z=189 page_faults, visible in the metrics query but buried under the error-status query; or queries aggregating by latency instead of by error status.
- **What agent observed instead**: filtered traces by `attr_status_code='Error'`, which excluded the injected service's (Unset-status) slow spans (Round 10), then anchored on ts-security-service which had 36 visible 503 errors.
- **Proximate cause**: error-span filter excluded JVM victim spans

---

## case_1218  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress (mem_type=1) on `ts-order-service.OrderInfo.enableBoughtDateQuery` caused jvm.class.loaded spike 1.75→4901 (z=2868), major_page_faults z=791M, filesystem.usage z=264T. ts-order-service's overloaded JVM caused its downstream dependencies (called via restTemplate) to time out. The visible error chain ran through ts-seat-service (47 new errors, 117 error spans with "503 Connection refused") and ts-travel-service (504 Gateway Timeout). Ts-order-service itself had 0 abnormal log errors because its JVM was too stressed to log. GT: container|ts-order-service is the injection origin.

### (2) What the agent did
At Round 54 the agent produced a sprawling timeline analysis and think_tool concluded: "ts-seat-service is showing errors, and the log message mentioned 'Connection refused'… The ts-seat-service is failing with 503 because it cannot connect to something upstream… The root cause for the SLO violations is ts-seat-service being unavailable (HIGH_ERROR_RATE, UNAVAILABLE)." It considered RabbitMQ and other candidates, noticed ts-seat-service had the loudest error signal, and anchored there while ts-order-service's silence was treated as non-signal.

### (3) Divergence
- **Pivot round**: 54
- **What agent should have observed**: ts-order-service jvm.class.loaded 1.75→4901 (z=2868), jvm.class.count DROP 19742→14420 (z=3548, major GC churn), major_page_faults z=791M — the definitive JVM-stress fingerprint on the injected service.
- **What agent observed instead**: anchored on ts-seat-service's visible 117 error spans and 503 Connection-refused messages (Round 54), treating it as the origin of the cascade.
- **Proximate cause**: anchored on highest error-count downstream victim

---

## case_1254  [HTTPFault / HTTPRequestReplaceMethod]

### (1) What really happened
HTTPRequestReplaceMethod rewrote POST→GET for requests from ts-preserve-service to ts-seat-service on `/api/v1/seatservice/seats`. Seat-service interpreted GET-with-body as malformed, causing ts-preserve-service to log 807 new errors (Δ +694) and generate 2418 Error-status spans. Business-level downstream effects: ts-order-service saw "Order already exists" (retries from preserve-service). GT: ts-preserve-service + ts-seat-service are the true injection victims; ts-order-service errors are secondary effects of preserve retries.

### (2) What the agent did
At Round 58 think_tool said: "ts-preserve-service has 2418 trace errors… ts-order-service has 0 trace errors (all spans have 'Unset' status), Only 1 log error, HTTP 200 responses. This means ts-order-service is functioning correctly from a system perspective — it's returning successful HTTP responses. The 'Order already exists' message is a business logic response, not a system failure… The root cause might be in ts-order-service — it's returning a business error that causes ts-preserve-service to fail." Despite ts-order-service having zero trace errors, the agent built a business-logic narrative ("order-rejector") and crowned it root cause.

### (3) Divergence
- **Pivot round**: 58
- **What agent should have observed**: ts-preserve-service had 2418 Error spans AND 807 log errors — it was the origin of the failure, not a victim. ts-seat-service's abnormal span drop and its role as the injection target were also visible in the log-delta table.
- **What agent observed instead**: read ts-order-service's HTTP-200 "Order already exists" as a healthy business rejection, treating zero trace errors there as proof of health (Round 58).
- **Proximate cause**: zero trace errors interpreted as healthy

---

## case_1846  [PodChaos / ContainerKill]

### (1) What really happened
Container-kill on ts-contacts-service pod `ts-contacts-service-658f5bc677-khmms`. The pod was killed and restarted, yielding jvm.class.loaded 1.25→6522 (z=4347) on restart, hubble_http_request_duration_p99 0.0099→0.157s (z=4950), p90 z=1611 — classic restart fingerprint. While the pod was down, MySQL logged 10 "Aborted connection" entries at 07:42:16.822 (the exact injection start) — these aborts are the SYMPTOM of ts-contacts-service's DB connections being terminated, not a cause. ts-ui-dashboard returned 20 new 503s on `/api/v1/contactservice/contacts/account/{accountId}`. GT: ts-contacts-service is the injection origin.

### (2) What the agent did
At Round 58 the agent built a timeline: "MySQL aborted connections start at 07:42:16.822 (very early); ts-contacts-service logs start at 07:42:44 (later)… The MySQL aborted connections could be causing ts-contacts-service to have high latency when querying the database, which causes ts-ui-dashboard to timeout and return 503." The agent saw MySQL's abort-connection log appearing FIRST chronologically and inverted cause/effect — the aborts are exactly what happens when a client pod is killed mid-query.

### (3) Divergence
- **Pivot round**: 58
- **What agent should have observed**: ts-contacts-service jvm.class.loaded z=4347 (restart indicator) + p99 latency z=4950 on the contacts service itself; the exact timestamp match between injection start (07:42:16Z) and MySQL aborts (07:42:16.822Z) indicating the DB reacting to a dead client, not causing failure.
- **What agent observed instead**: read MySQL's 10 aborted-connection entries as temporal cause (earliest logs), built the chain mysql → ts-contacts-service → ts-ui-dashboard (Round 58).
- **Proximate cause**: MySQL aborted-connection symptom read as cause

---

## case_1880  [HTTPFault / HTTPResponseReplaceBody]

### (1) What really happened
HTTPResponseReplaceBody corrupted response bodies on `GET /api/v1/travelservice/routes/*` from ts-food-service→ts-travel-service (body_type=1 — replace with junk token 'lwwqt8'). ts-travel-service returned HTTP 200 with corrupted JSON; ts-food-service failed to parse and logged +1158 errors (total 1412 abnormal vs 254 normal). Downstream, ts-food-service emitted 78 new 503s to ts-ui-dashboard. GT: ts-food-service + ts-travel-service (the route-serving edge, not ts-route-service itself).

### (2) What the agent did
At Round 60 think_tool declared: "ts-food-service: 2762 errors (most affected — but these are downstream effects); ts-route-service: 0 errors (but it's the ROOT CAUSE — returning malformed data)… The root cause service (ts-route-service) shows 0 errors in its spans because it's successfully returning HTTP 200 responses. However, the CONTENT of those responses is malformed (containing 'lwwqt8' instead of valid JSON)." The agent correctly identified the CORRUPTION PATTERN and direction of travel (malformed payload upstream) but traced ONE HOP TOO FAR — past ts-travel-service to ts-route-service, missing that the injection was on the route-lookup edge INTO ts-travel-service.

### (3) Divergence
- **Pivot round**: 60
- **What agent should have observed**: the injection target was `/api/v1/travelservice/routes/*` on ts-travel-service — the service that was returning corrupted JSON to ts-food-service. The 'lwwqt8' token appeared at the ts-food-service→ts-travel-service boundary, not further upstream.
- **What agent observed instead**: followed the corruption trail one hop past the injection point to ts-route-service as the "originator" of the bad data (Round 60).
- **Proximate cause**: followed corrupted payload one hop past injection

---

## case_1934  [PodChaos / PodFailure]

### (1) What really happened
PodFailure on ts-order-service (pod `ts-order-service-66c6db4f9d-rdp7v`). The pod went down; container.filesystem.usage plunged 466944→40088 (z=426T), p95 latency z=466. ts-order-service logs collapsed 2260→4. Upstream callers of ts-order-service couldn't complete their flows — ts-seat-service emitted 117 error spans (HTTP 503 Connection refused) because its seat-reservation workflow includes order lookups. GT: ts-order-service is the injection origin.

### (2) What the agent did
At Round 10 think_tool said: "ts-seat-service has 93 Error status spans — the highest among services with errors… ts-seat-service shows errors with 'POST /api/v1/seatservice/seats/left_tickets'… ts-seat-service is showing errors, and the log message mentioned 'Connection refused' — suggesting ts-seat-service cannot connect to something it depends on." It recognized ts-seat-service was a victim but subsequent rounds never re-examined the upstream ts-order-service silence; the agent finalized ts-seat-service as root cause ("HIGH_ERROR_RATE, UNAVAILABLE").

### (3) Divergence
- **Pivot round**: 10
- **What agent should have observed**: ts-order-service logs dropped 2260→4 (99.8% disappearance), filesystem.usage z=426T — the characteristic "pod disappeared" signature of the injection target.
- **What agent observed instead**: anchored on ts-seat-service's 93–117 visible error spans as highest error-count service (Round 10).
- **Proximate cause**: ts-seat-service had highest error span count

---

## case_2598  [HTTPFault / HTTPRequestDelay]

### (1) What really happened
HTTPRequestDelay (3066ms) on ts-preserve-service→ts-seat-service calls (`POST /api/v1/seatservice/seats`). The injected delay made preserve-service's seat-reservation step stretch so long that preserve retried, generating duplicate order-creation attempts. ts-order-service rejected duplicates with "Order already exists" (HTTP 200, business-level) — this is the DOWNSTREAM EFFECT of preserve's retry logic, not a root cause. GT: ts-preserve-service + ts-seat-service (the delayed call edge).

### (2) What the agent did
At Round 42 the agent traced the call and noted ts-order-service showed "Unset" status (HTTP succeeded) but logs said "Order already exists." Think_tool concluded: "ts-preserve-service is trying to create orders that already exist. This could be due to retry logic after timeouts or idempotency issues… For the preserve endpoint SLO violations, the root cause is ts-preserve-service is failing because ts-order-service rejects duplicate order creation." It then crowned ts-order-service as root cause via a business-logic narrative, completely missing the ts-seat-service latency (jvm.system.cpu.load_1m 10.16→202.5, z=57.83).

### (3) Divergence
- **Pivot round**: 42
- **What agent should have observed**: ts-seat-service jvm.system.cpu.load_1m z=57.83 (the service on the receiving end of the injected delay showing load spike); the 3066ms response-delay fingerprint in seat-service p99 latency; and that "Order already exists" is a CONSEQUENCE of preserve retrying after a timeout.
- **What agent observed instead**: built a coherent business-logic story ("preserve retries → order-service rejects duplicates → cascade") anchored on the quotable order-service error message (Round 42).
- **Proximate cause**: blamed order-rejector using business-logic narrative

---

## case_2641  [HTTPFault / HTTPResponseDelay]

### (1) What really happened
HTTPResponseDelay (4418ms) on `POST /api/v1/travelservice/trip_detail` from ts-route-plan-service→ts-travel-service. The injected delay caused ts-route-plan-service's downstream call to ts-travel-service to time out; ts-route-plan-service logged "Connection reset" and "502 Bad Gateway" (12 new errors), cascading through ts-travel-plan-service (14 errors) and ts-ui-dashboard (14 errors). GT: ts-route-plan-service + ts-travel-service (the delayed edge).

### (2) What the agent did
At Round 51 think_tool walked through evidence: "ts-route-plan-service has GET spans with 502 status code… 'Connection reset' when calling ts-travel-service and ts-travel2-service… ts-route-plan-service is receiving errors FROM downstream services, not generating them itself… The most likely scenario is that ts-route-service is experiencing issues (possibly intermittent unavailability), causing ts-route-plan-service to receive 502 errors." The agent invented a causal chain extending past the injection point (ts-travel-service) further downstream to ts-route-service, rationalizing the 502s by tracing GET patterns past the actual injection boundary.

### (3) Divergence
- **Pivot round**: 51
- **What agent should have observed**: The actual injection was `/api/v1/travelservice/trip_detail` (POST to ts-travel-service). The "Connection reset" messages in ts-route-plan-service were exactly the symptom of waiting too long on the delayed response from ts-travel-service.
- **What agent observed instead**: followed the call-chain one hop past ts-travel-service to ts-route-service as the 502-source (Round 51), crafting a plausible-sounding intermittent-unavailability narrative.
- **Proximate cause**: traced 502 one hop too far past injection

---

## case_2715  [NetworkChaos / NetworkBandwidth]

### (1) What really happened
NetworkBandwidth (rate=168909, buffer=6445, limit=138) throttled traffic from ts-station-service→ts-basic-service. ts-basic-service DB connection pool exhausted: db.client.connections.wait_time z=9141, http.server.request.duration z=50. ts-station-service's log volume collapsed 1263→19 (starved) while its few remaining requests were slow. Downstream ts-travel-service showed the most visible downstream symptom — 10 new errors, db.client.connections.pending_requests 0→0.75, and db.client.connections.use_time 0.61→7500s — because ts-travel-service accesses basic-service for route metadata. GT: ts-station-service + ts-basic-service (the throttled edge).

### (2) What the agent did
At Round 21 think_tool finalized: "ts-travel-service… First service to show errors (10:47:01.937); Errors are at the database level (JDBC connection pool exhaustion); All other services with errors are downstream callers of ts-travel-service." The agent saw the DB connection pool symptom on ts-travel-service (z=9141 equivalent) and anchored on the highest-amplitude DB metric, ignoring ts-station-service's log-volume collapse and the ts-basic-service metric anomalies.

### (3) Divergence
- **Pivot round**: 21
- **What agent should have observed**: ts-basic-service's DB wait-time z=9141 was the actual receiving end of the throttle; ts-station-service's log collapse 1263→19 indicated throttled upstream.
- **What agent observed instead**: picked ts-travel-service because its db.client.connections metrics were the most visibly extreme DB connection-pool symptom (Round 21).
- **Proximate cause**: picked most visible DB connection pool errors

---

## case_3125  [HTTPFault / HTTPResponseDelay]

### (1) What really happened
HTTPResponseDelay (4226ms) on `GET /api/v1/securityservice/securityConfigs/*` from ts-preserve-service→ts-security-service. The injection added 4.2s to every security-config call ts-preserve-service made, causing preserve endpoints to breach SLO. Ts-preserve-service generated 5 new ts-ui-dashboard 503s. GT: ts-preserve-service + ts-security-service (the delayed edge).

### (2) What the agent did
At Round 60 think_tool built an elaborate latency-path analysis: "ts-config-service has a max duration of 3042420157 ns (~3 seconds) for GET /api/v1/configservice/configs/{configName} — this is the highest latency at the bottom of the call chain… ts-seat-service calls ts-config-service and has a max duration of 3043201860 ns for GET spans — almost identical… The call chain is clear: ts-config-service → ts-seat-service → ts-travel-service → ts-route-plan-service → ts-travel-plan-service → ts-ui-dashboard → loadgenerator." The agent conflated ts-config-service (config lookups, separate endpoint) with the ts-security-service path, mis-scoping its latency query to include unrelated services.

### (3) Divergence
- **Pivot round**: 60
- **What agent should have observed**: ts-preserve-service http.server.request.duration 0.28→3.69 (z=40.18) — the exact ~3.6s injected delay fingerprint on the preserve side; and that the 4.2s latency was on `/securityservice/securityConfigs/*` (the injected route), not configservice.
- **What agent observed instead**: mis-scoped its query to a different config-service endpoint and fabricated a cascade chain through seat/travel/route-plan (Round 60).
- **Proximate cause**: mis-scoped latency query inflated config-service

---

## case_3128  [HTTPFault / HTTPResponseDelay]

### (1) What really happened
HTTPResponseDelay (4151ms) on `GET /api/v1/securityservice/securityConfigs/*` from ts-preserve-service→ts-security-service (same pattern as case_3125, different run). ts-preserve-service http.server.request.duration 0.28→3.69 (z=40.18). The delay injection caused preserve's outer span to fail with a POST Error (4.2ms tail). GT: ts-preserve-service + ts-security-service.

### (2) What the agent did
At Round 21 the agent analyzed a trace: "The GET span to ts-security-service has duration 4.1 seconds but the actual ts-security-service span only took 14ms. This suggests network latency or connection issues… The POST span with Error status (cdb5e712ebdf42dd) is a child of PreserveController.preserve… It seems to be calling ts-order-service based on the logs showing 'Order already exist' errors." The agent invented an `ts-order-service → ts-security-service → ts-preserve-service` chain (even though ts-order-service doesn't call ts-security-service) and anchored ts-order-service as root cause by stitching together "Order already exists" logs with the error POST.

### (3) Divergence
- **Pivot round**: 21
- **What agent should have observed**: The GET→ts-security-service 4.1s span was the exact injection fingerprint. The "Order already exist" logs were unrelated background noise from preserve's business-layer retry semantics.
- **What agent observed instead**: stitched ts-order-service into a contrived causal chain ts-order → ts-security → ts-preserve (Round 21) based on a misread POST error span.
- **Proximate cause**: invented causal chain past injection point

---

## case_3219  [NetworkChaos / NetworkCorrupt]

### (1) What really happened
NetworkCorrupt (corrupt=50, correlation=84, from ts-seat-service to ts-order-service). Packets between ts-seat-service and ts-order-service were corrupted, causing both services to retry heavily. ts-seat-service http.client.request.duration z=46, http.server.request.duration z=23. Upstream ts-travel-service waited on seat calls, producing visible DB connection exhaustion: db.client.connections.use_time jumped to 67.8s on ts-travel-service. GT: ts-seat-service + ts-order-service (the corrupted edge).

### (2) What the agent did
At Round 69 think_tool wrote: "ts-travel-service is experiencing severe database connection issues: db.client.connections.use_time: 67.8 seconds (abnormal) vs 2.5 seconds (normal) — a 27x increase; http.server.request.duration: 67.8 seconds max… No errors in ts-travel-service logs, just INFO messages — indicating the service is functioning but slow due to DB issues. Root Cause Service: ts-travel-service. The root cause is database connection pool exhaustion or slow database queries in ts-travel-service." The biggest-amplitude metric (27× DB use_time) won, displacing both the real injection target ts-seat-service and its endpoint ts-order-service.

### (3) Divergence
- **Pivot round**: 69
- **What agent should have observed**: ts-seat-service's http.client.request.duration z=46 — the direct victim of packet corruption on its outbound order-service calls.
- **What agent observed instead**: selected ts-travel-service because it had the biggest absolute DB metric spike (67.8s use_time, 27× normal) (Round 69).
- **Proximate cause**: DB connection metric displaced injected service

---

## case_3278  [NetworkChaos / NetworkBandwidth]

### (1) What really happened
NetworkBandwidth (rate=988864, buffer=636, limit=3035) throttled traffic between ts-travel-plan-service and ts-ui-dashboard in both directions. 22 traces timed out at ~20s on `/travelplanservice/travelPlan/{quickest,minStation,cheapest}`. Log volumes collapsed across all services (seat-service 14560→1654, basic-service 9177→822) because the travel-plan→dashboard throttle starved the workload. GT: ts-travel-plan-service + ts-ui-dashboard (the throttled edge).

### (2) What the agent did
At Round 54 think_tool stated: "ts-route-service shows the highest latency among downstream services (max 266ms for GET /api/v1/routeservice/routes); ts-route-service is called by multiple upstream services; The cumulative latency through the call chain causes the 20-second timeout at the loadgenerator level… The ts-route-service has high latency database queries (SELECT ts.route, SELECT ts.route_stations, SELECT ts.route_distances) which cascade up through the dependency chain." The agent traced past the injection boundary (ts-travel-plan-service ↔ ts-ui-dashboard), past ts-route-plan-service, all the way down to ts-route-service, building an increasingly deep chain anchored on "highest latency leaf."

### (3) Divergence
- **Pivot round**: 54
- **What agent should have observed**: The 20-second timeouts were at the ts-ui-dashboard edge — exactly where the bandwidth throttle was applied. ts-travel-plan-service log volume dropped 1104→133 showing the throttle's upstream effect.
- **What agent observed instead**: kept following the call-chain to a deeper "high-latency leaf" (ts-route-service's 266ms DB queries — normal-range) past the injected edge (Round 54).
- **Proximate cause**: pursued highest-latency leaf past injected service

---

## case_3524  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress (mem_type=2) on `ts-assurance-service.AssuranceApplication.restTemplate`. jvm.class.loaded 0→6467 (z=6467G), filesystem.usage z=289T. ts-assurance-service restarted once at 13:11:32. Unrelated background noise: ts-ticket-office-service had 2 container restarts at 13:11:02 (frequent background flapping, normal condition — no logs, no traces because this service has no production traffic). ts-ui-dashboard got "connection refused to 10.107.55.43:8080" (assurance's IP) — the direct symptom of the JVM-stressed assurance service. GT: ts-assurance-service.

### (2) What the agent did
At Round 37 think_tool summarized: "ts-ticket-office-service: First to restart (13:11:02), NO logs, NO traces — indicates complete service failure; ts-assurance-service: Starts restarting 30 seconds AFTER ts-ticket-office-service (13:11:32); ts-ui-dashboard: Gets connection refused errors to 10.107.55.43:8080 (the assurance service IP)… ts-ticket-office-service crashed first and took down ts-assurance-service with it (likely through a dependency)." The agent treated the silent ts-ticket-office-service (a service with no normal traffic — always silent) as the upstream root cause by earliest-restart timing.

### (3) Divergence
- **Pivot round**: 37
- **What agent should have observed**: ts-assurance-service jvm.class.loaded 0→6467 (z=6467G) + filesystem.usage z=289T + its own container restart — the canonical JVMMemoryStress fingerprint ON THE INJECTED SERVICE. ts-ticket-office-service's restarts and silence are background noise (common in this service).
- **What agent observed instead**: chose ts-ticket-office-service because it restarted 30 seconds earlier and had no spans — reading silence as complete failure (Round 37).
- **Proximate cause**: silent service inferred as upstream root cause

---

## case_3552  [NetworkChaos / NetworkLoss]

### (1) What really happened
NetworkLoss (loss=77, correlation=63) drops 77% of packets from ts-travel-service to ts-seat-service. ts-travel-service http.client.request.duration 0.037→32.67s (z=1011), db.client.connections.use_time z=485. Calls to seat-service kept timing out/retrying. ts-travel-service logged "Connection timed out" calling ts-seat-service. Cascade: travel-service slow → route-plan-service slow (http.client.request.duration 0.09→8.26s) → travel-plan-service/ui-dashboard. GT: ts-travel-service + ts-seat-service.

### (2) What the agent did
At Round 30 think_tool said: "ts-seat-service has high latency spans (~2.7s) in abnormal data; ts-travel-service logs show 'Connection timed out' when calling ts-seat-service; The call chain is: ts-ui-dashboard → ts-travel-plan-service → ts-route-plan-service → ts-travel-service → ts-basic-service → ts-seat-service… Let me check what ts-seat-service calls — it might be calling another service that's failing." The agent was actively tracing PAST the real injection edge (travel↔seat) into seat-service's downstream, eventually landing on ts-order-other-service as root cause through deeper tracing.

### (3) Divergence
- **Pivot round**: 30
- **What agent should have observed**: The "Connection timed out" logs were exactly the packet-loss symptom at the travel→seat boundary. ts-travel-service's own http.client.request.duration z=1011 was the direct packet-loss fingerprint.
- **What agent observed instead**: traced past ts-seat-service into its downstream dependencies (ts-order-service) and beyond, ending at ts-order-other-service (Round 30).
- **Proximate cause**: traced past injection through seat to order-other

---

## case_3605  [NetworkChaos / NetworkCorrupt]

### (1) What really happened
NetworkCorrupt (corrupt=91, correlation=29, both directions) between ts-travel-service and ts-seat-service. 91% packet corruption created massive retries; ts-travel-service http.client.request.duration z=79 (max 95s), 2.65s avg duration. The extreme amplitude fell on ts-travel-service's own spans because it was retrying both in and out. GT: ts-travel-service + ts-seat-service (corrupted edge).

### (2) What the agent did
At Round 22 think_tool declared: "ts-travel-service: avg_duration = 2.65 seconds, max_duration = 95 seconds! This is extremely high… The ts-travel-service has by far the highest average duration (2.65 seconds) and an extremely high max duration of 95 seconds! This is a strong indicator that ts-travel-service is the root cause of the latency issues." But as subsequent rounds progressed, the agent shifted to ts-basic-service because ts-basic-service was the common caller of ts-travel-service in their trace topology reading; final answer ts-basic-service, trumped by its amplitude-in-role.

### (3) Divergence
- **Pivot round**: 22
- **What agent should have observed**: ts-travel-service had the highest amplitude (95s max) AND the corruption injection was to/from ts-seat-service — those two together point exactly at the travel↔seat edge.
- **What agent observed instead**: at Round 22 picked the highest-amplitude span owner but later re-anchored to ts-basic-service as the "upstream" service on the call chain, finalizing on amplitude elsewhere.
- **Proximate cause**: highest-amplitude span owner selected

---

## case_3878  [NetworkChaos / TimeSkew]

### (1) What really happened
TimeSkew (time_offset=336s) on ts-consign-service pod. The clock skew broke time-dependent queries: ts-consign-service logs dropped 2813→0, errors dropped 512→0 (entirely absent from abnormal period because the service couldn't process anything while clock-confused). The SLO-violating endpoint was `/api/v1/consignservice/consigns/account/{id}` — a direct consign-service endpoint. Downstream symptoms landed on ts-seat-service/ts-travel-service/ts-travel-plan-service high latency (max 16-25s). GT: ts-consign-service.

### (2) What the agent did
At Round 66 think_tool concluded: "ts-travel-plan-service: max 25.6s, avg 595ms; ts-route-plan-service: max 24.6s; ts-seat-service: max 18.8s; Call Chain: loadgenerator → ts-ui-dashboard → ts-travel-plan-service → ts-route-plan-service → ts-travel-service → ts-seat-service; The GET operation in ts-seat-service (16-18s) is the bottleneck. Root Cause: ts-seat-service is the origin of the latency issue." The agent picked the deepest service in the latency chain, never connecting the SLO endpoint (`/consignservice/*`) to the silent ts-consign-service (log volume 2813→0).

### (3) Divergence
- **Pivot round**: 66
- **What agent should have observed**: ts-consign-service log volume 2813→0 (complete silence) — the classic TimeSkew effect on a time-query-heavy service; and the SLO endpoint explicitly being `/consignservice/consigns/account/{id}`.
- **What agent observed instead**: treated ts-consign-service's silence as healthy non-involvement, anchored on ts-seat-service's 18.8s latency as "deepest-in-chain bottleneck" (Round 66).
- **Proximate cause**: silent consign-service (time-skew) read as healthy

---

## case_3920  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress (mem_type=1) on `ts-payment-service.PaymentServiceImpl.pay`. ts-payment-service's pay method was memory-stressed; hubble_http_request_duration_p90 0.0235→0.137 (z=46 quadrillion), p95 z=761. The injected pay calls timed out. Downstream ts-inside-payment-service (which calls ts-payment-service) logged "503 Service Unavailable: upstream connect error" with 19 new errors — the visible cascade symptom. ts-payment-service itself stayed "Unset" in traces because its span simply hung. GT: ts-payment-service.

### (2) What the agent did
At Round 35 think_tool said: "Looking at ts-payment-service: All spans have status 'Unset' (no errors); HTTP response status code is 200 for the payment endpoint; ts-payment-service appears to be working correctly. So ts-payment-service is NOT the problem. The issue is specifically with ts-inside-payment-service… ts-inside-payment-service: 19 error traces with HTTP 500; 503 Service Unavailable: upstream connect error…Connection refused… The root cause is ts-inside-payment-service itself." The agent read payment-service's Unset status as healthy and blamed the visible-error service.

### (3) Divergence
- **Pivot round**: 35
- **What agent should have observed**: ts-payment-service hubble_http_request_duration_p90 z=46 quadrillion — an extreme latency signal on the injected service; the "upstream connect error" in ts-inside-payment-service points to ts-payment-service (its payment-processing upstream).
- **What agent observed instead**: read ts-payment-service's Unset trace status and HTTP 200 as health, anchored on ts-inside-payment-service's visible 503s (Round 35).
- **Proximate cause**: missing payment spans interpreted as health

---

## case_4032  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress (mem_type=1) on `ts-auth-service.AuthController.getHello`. jvm.class.loaded 0→6538 (z=6538G), jvm.class.count DROP 19885→19590 (z=294G), major_page_faults z=872M. ts-auth-service's `/api/v1/users/login` path slowed; ts-ui-dashboard returned 31 new 503s on the login endpoint when auth-service calls timed out. ts-auth-service's own log and trace volumes actually INCREASED (1729→1959 logs, normal because the service kept restarting — healthy deployment flag). GT: ts-auth-service.

### (2) What the agent did
At Round 62 think_tool said: "ts-ui-dashboard is returning 503 errors with ~3.5 second duration (timeout); When errors occur, ts-ui-dashboard does NOT call ts-auth-service (no child spans); ts-auth-service is healthy (deployment.available = 1.0, no ERROR logs, successful traces exist); The error is intermittent… The fact that only 7 out of 651 traces show errors (~1% error rate) suggests this is an intermittent issue. The root cause service is ts-ui-dashboard because it's the service returning 503 errors." The agent saw auth-service metrics as healthy (deployment.available=1) and anchored on ts-ui-dashboard, the 503-renderer.

### (3) Divergence
- **Pivot round**: 62
- **What agent should have observed**: ts-auth-service jvm.class.loaded 0→6538 (z=6538G) — extreme class-loading churn characteristic of memory stress injection.
- **What agent observed instead**: read ts-auth-service's deployment.available=1 and "successful traces exist" as healthy, anchored on ts-ui-dashboard as the 503-origin (Round 62).
- **Proximate cause**: healthy metrics on stressed service as health

---

## case_4055  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress (mem_type=2) on `ts-consign-price-service.ConsignPriceController.getPriceInfo`. Injection triggered mem-allocation pressure. ts-consign-price-service log volume rose 6→56, processedLogs z=26. Downstream ts-consign-service (which calls consign-price for pricing) generated 11 new errors, and ts-ui-dashboard's `PUT /api/v1/consignservice/consigns` saw new 503s. Background: ts-ticket-office-service had 3 container restarts (frequent normal flapping, not correlated with injection). GT: ts-consign-price-service.

### (2) What the agent did
At Round 56 think_tool said: "ts-ticket-office-service has 3 container restarts (highest among all services); ts-consign-price-service has 1 container restart; ts-voucher-service has 1 container restart… ts-consign-service is making an outbound HTTP GET call to another service; The target service is unavailable (Connection refused); Based on the service names and the fact that ts-ticket-office-service has the most restarts, it's likely that ts-consign-service depends on ts-ticket-office-service. The root cause is ts-ticket-office-service." The agent anchored on the highest restart-count service without checking whether ts-consign-service even calls ts-ticket-office-service.

### (3) Divergence
- **Pivot round**: 56
- **What agent should have observed**: ts-consign-price-service processedLogs z=26 + its log volume spike 6→56 + the SLO endpoint (`/consignservice/consigns`) logically depending on consign-price for pricing lookups.
- **What agent observed instead**: picked ts-ticket-office-service because it had the highest restart count without verifying call-path membership (Round 56).
- **Proximate cause**: highest restart-count picked without path check

---

## case_4229  [NetworkChaos / NetworkPartition]

### (1) What really happened
NetworkPartition (direction=to) isolated ts-basic-service from ts-travel-service. Ts-basic-service couldn't call travel-service, ts-travel-service couldn't receive. The upstream GC pressure fell on ts-route-plan-service (jvm.gc.duration 0.32→6.93s, 21× normal) and especially ts-travel-plan-service (0.44→12.16s, 27× normal) because they kept retrying through basic-service. MySQL log volume spiked 0→169 (connection churn from partition retries). GT: ts-basic-service + ts-travel-service (the partitioned edge).

### (2) What the agent did
At Round 35 think_tool wrote: "ts-travel-plan-service: avg_duration = 190ms… Normal: 185ms. Very similar!… The GC pressure in ts-route-plan-service (21x increase) is significant. Since ts-travel-plan-service calls ts-route-plan-service, if ts-route-plan-service is experiencing GC issues, it would cause ts-travel-plan-service to wait… I believe ts-route-plan-service is the ROOT CAUSE. Its GC issues cause it to respond slowly, which causes ts-travel-plan-service to wait and accumulate its own GC pressure." The agent picked the service with the largest GC-pressure z-score metric, ignoring that both ts-basic-service and ts-travel-service were the partitioned endpoints.

### (3) Divergence
- **Pivot round**: 35
- **What agent should have observed**: ts-basic-service filesystem.capacity anomaly + the partition on the `to ts-travel-service` direction — the two endpoint services were starved of each other.
- **What agent observed instead**: picked ts-route-plan-service because its GC-duration amplitude (21× increase) was higher than the injected services' metrics (Round 35).
- **Proximate cause**: downstream GC amplitude higher than injected

---

## case_4309  [PodChaos / ContainerKill]

### (1) What really happened
Container-kill on ts-payment-service container (pod `ts-payment-service-7648bd9bcd-jkq2w`). hubble_http_request_duration_p90 0.0235→0.879 (z=604 quadrillion), filesystem.usage dropped 466944→422058, jvm.class.count 19440→19545 (restart churn), queueSize 0→1.67. The pod restarted; while down, ts-inside-payment-service (payment-service caller) emitted 21 new errors + SEVERE 503 Connection-refused messages. Replacement pod metrics then appeared healthy, masking the kill. GT: ts-payment-service.

### (2) What the agent did
At Round 38 think_tool said: "ts-inside-payment-service is showing Error status codes (HTTP 500 and 503); The logs show '503 Service Unavailable: upstream connect error' with 'Connection refused'; ts-order-service appears healthy (Unset status in traces); ts-ui-dashboard shows Unset status (healthy)… The root cause appears to be ts-inside-payment-service itself — it's experiencing internal failures when processing the inside_payment requests. The 'Connection refused' error suggests it might be trying to reach some internal dependency." The agent crowned inside-payment-service as root cause because payment-service's replacement-pod metrics looked healthy by the time it looked.

### (3) Divergence
- **Pivot round**: 38
- **What agent should have observed**: ts-payment-service p90 latency z=604 quadrillion + queueSize 0→1.67 + the "upstream connect error" in inside-payment-service specifically referring to payment-service's IP:port.
- **What agent observed instead**: saw ts-payment-service's post-restart metrics as healthy and anchored on ts-inside-payment-service as the visible Error-status service (Round 38).
- **Proximate cause**: replacement pod metrics masked killed container

---

## case_4510  [NetworkChaos / NetworkBandwidth]

### (1) What really happened
NetworkBandwidth (rate=110548, buffer=1211, both directions) throttled traffic between ts-route-plan-service and ts-travel-service. Ts-travel-plan-service couldn't complete its route-planning calls; log volumes collapsed across the stack (ts-seat-service 12115→2279, basic-service 7833→1413, travel-service 5809→1166). Loadgenerator timed out at 20s; ts-travel-plan-service had fewer spans because requests couldn't reach it. GT: ts-route-plan-service + ts-travel-service (throttled edge).

### (2) What the agent did
At Round 50 think_tool wrote: "ts-travel-plan-service: MISSING (never receives request); ts-route-plan-service: MISSING (never receives request); Other downstream services appear but with normal durations… Root Cause: ts-travel-plan-service is UNAVAILABLE; The service is not responding to requests from ts-ui-dashboard; This causes a 20-second timeout at ts-ui-dashboard." The agent correctly spotted a missing-downstream-span pattern, but attributed it to ts-travel-plan-service being down rather than the bandwidth throttle between ts-route-plan and ts-travel-service further down.

### (3) Divergence
- **Pivot round**: 50
- **What agent should have observed**: The missing spans extended through ts-route-plan-service to ts-travel-service (the actually-throttled edge). ts-travel-plan-service log volume barely changed (945→141 was the same proportional drop as its peers).
- **What agent observed instead**: picked ts-travel-plan-service as "UNAVAILABLE" because it was the first missing-span node visible from the loadgenerator entry (Round 50), one hop short of the real boundary.
- **Proximate cause**: missing downstream span treated as service down

---

## case_4519  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress (mem_type=1) on `ts-route-plan-service.RoutePlanServiceImpl.searchQuickestResult`. filesystem.usage z=179T on route-plan-service. The stressed route-plan-service couldn't complete travel-plan queries properly, causing ts-travel-plan-service's `getByMinStation`, `getByQuickest`, `getByCheapest` methods to return HTTP 500 (39 new travel-plan errors, 39 new dashboard errors). GT: ts-route-plan-service.

### (2) What the agent did
At Round 46 think_tool declared: "Root Cause Service: ts-travel-plan-service; This service is failing when processing travel plan requests; Error occurs in methods: getByMinStation, getByQuickest, getByCheapest; Returns HTTP 500 status codes; In abnormal traces, it has 117 error spans out of 1840 total… Evidence: In all failing traces, only 3 services show Error status: ts-travel-plan-service, ts-ui-dashboard, loadgenerator; ts-travel-plan-service is the origin — it has no downstream service calls that are failing; All child spans of ts-travel-plan-service are also from ts-travel-plan-service itself (internal processing); No other services in the call chain show any errors (all show 'Unset' = success)." The agent's error-status-filter query buried ts-route-plan-service's (Unset-status) slow spans.

### (3) Divergence
- **Pivot round**: 46
- **What agent should have observed**: ts-route-plan-service filesystem.usage z=179T and jvm.class.count uptick (injection_affected); ts-travel-plan-service errors were children of travel-plan's POST spans that called down to ts-route-plan-service.
- **What agent observed instead**: the error-status query returned only 3 services (travel-plan, ui-dashboard, loadgenerator); Unset-status route-plan-service spans were excluded (Round 46).
- **Proximate cause**: error-status query buried injection_affected spans

---

## case_4530  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress (mem_type=1) on `ts-seat-service.SeatApplication.main`. filesystem.usage z=182T, jvm.class.loaded 1.0→4943. The injected seat-service failed to respond properly. Downstream: ts-travel2-service returned 166 internal error spans (83 HTTP 500) because travel2 calls seat; ts-travel-service 70 errors; ts-route-plan-service 53; ts-travel-plan-service 53; ts-ui-dashboard 118. GT: ts-seat-service (origin of the cascade via `POST /api/v1/seatservice/seats/left_tickets`).

### (2) What the agent did
At Round 55 think_tool said: "Root Cause Service: ts-travel2-service — Has the highest number of internal error spans (166); Returns HTTP 500 errors (83 occurrences); Error spans are leaf spans (no children), meaning errors originate within the service; Downstream calls from ts-travel2-service are successful (database, etc.)… ts-travel-service has 70 internal errors; ts-travel2-service has 166 internal errors. Both services have internal errors. But ts-travel2-service has more than double the errors." The agent picked the maximum-visible-error service and treated ts-seat-service as a silent non-participant.

### (3) Divergence
- **Pivot round**: 55
- **What agent should have observed**: ts-seat-service filesystem.usage z=182T + jvm.class.loaded 1.0→4943 (characteristic JVM memory-stress signature) + seat-service spans missing/slow as the upstream dependency travel2/travel are retrying against.
- **What agent observed instead**: anchored on ts-travel2-service with 166 error spans as highest internal error count (Round 55).
- **Proximate cause**: highest error-span count over missing-span origin

---

## case_4732  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress (mem_type=2) on `ts-train-food-service.TrainFoodController.home`. filesystem.usage z=180T, jvm.gc.duration 0.33→0.91s (z=583M). ts-train-food-service didn't respond properly to food-service's queries; ts-food-service logged +27 new errors "Get the Get Food Request Failed!" (because train-food responses were corrupted/missing), generated 396 Error-status spans. ts-train-food-service's own trace status stayed Unset (spans completed HTTP 200 but content was bad). GT: ts-train-food-service.

### (2) What the agent did
At Round 32 think_tool said: "In abnormal traces: ts-food-service has 396 spans with 'Error' status; ts-train-food-service only has 'Unset' status (no errors). This confirms that ts-food-service is the service experiencing errors, while its upstream dependency ts-train-food-service is working correctly… HTTP 500 errors originate from ts-food-service; ts-food-service logs show 'Get the Get Food Request Failed!' and 'foodStoresListResult is null'; ts-train-food-service is responding successfully (200 status codes, Unset trace status)." The agent read Unset trace status on ts-train-food-service as definitive health and crowned ts-food-service.

### (3) Divergence
- **Pivot round**: 32
- **What agent should have observed**: ts-train-food-service filesystem.usage z=180T and jvm.gc.duration 0.33→0.91s — clear memory-stress fingerprint; and that Unset trace status doesn't mean the response body is correct.
- **What agent observed instead**: read ts-train-food-service's Unset trace status as healthy (Round 32), anchored on ts-food-service which had the visible 396 Error spans.
- **Proximate cause**: Unset trace status interpreted as healthy

---

## case_4789  [JVMChaos / JVMMemoryStress]

### (1) What really happened
JVMMemoryStress (mem_type=2) on `ts-station-service.StationServiceImpl.delete`. filesystem.usage z=275T, jvm.class.loaded 0→6441 (z=6441G), jvm.class.count DROP 19590→19307 (z=282G — heavy GC churn). The station-service outages caused ts-basic-service to fail lookups (67 new ts-basic-service errors); ts-travel-service / ts-travel2-service / ts-route-plan-service / ts-travel-plan-service cascaded. MySQL logged 10 "Aborted connection" entries — the normal symptom of a killed JVM mid-query. GT: ts-station-service.

### (2) What the agent did
At Round 58 think_tool said: "Root Cause: mysql — Evidence: 'Aborted connection' errors with 'Got an error reading communication packets' only in abnormal logs (10 entries), not in normal logs (0 entries); This indicates MySQL is having connection issues, likely due to network problems or overload… Propagation: mysql → ts-basic-service → ts-travel-service / ts-travel2-service → ts-route-plan-service → ts-travel-plan-service → ts-ui-dashboard → loadgenerator." The agent followed the call chain all the way down to MySQL, past ts-station-service entirely, constructing a coherent-sounding DB-aborted-connection cascade narrative.

### (3) Divergence
- **Pivot round**: 58
- **What agent should have observed**: ts-station-service jvm.class.loaded 0→6441 (z=6441G) + jvm.class.count DROP 19590→19307 (z=282G) — definitive JVM memory-stress fingerprint. The MySQL aborts were SYMPTOMS of the stressed station-service's connections being terminated, not causes.
- **What agent observed instead**: followed the call chain past station-service all the way to MySQL, anchored on MySQL's aborted-connection log (Round 58).
- **Proximate cause**: followed call chain past injection to MySQL

---
agentId: a5073f4391756c95a (use SendMessage with to: 'a5073f4391756c95a' to continue this agent)
<usage>total_tokens: 249248
tool_uses: 54
duration_ms: 538800</usage>
