# per_case_analysis.md — thinkdepthai-claude-sonnet-4.6

3-block per-case analysis. Block 1 = GT reality (from injection.json + conclusion + causal_graph). Block 2 = agent trajectory (what it did, pivot round). Block 3 = divergence + proximate-cause phrase (plain language, **no theme names yet**).

---

## case_315 — HTTPResponseDelay @ ts-travel-plan-service→ts-train-service (605ms)

- **GT**: ts-travel-plan-service + ts-train-service. Injection delays the `/api/v1/trainservice/trains/byName/*` call from travel-plan to train service by 605ms. 15 propagation paths all originate at `service|ts-travel-plan-service`.
- **Agent (23 rounds, 932k tokens)**: Observed every travelplan endpoint 2–4x inflated, but also observed ts-order-service had a 90-second JVM GC stop-the-world pause (PROCESS_PAUSED), triggered HikariCP thread-starvation WARN, CPU spike 0.07→17.78 cores. Pivot **R9** ("ts-order-service had a 90-second database query timeout... this is likely the root cause"). R11–R23 spent entirely re-confirming the order-service GC narrative. Final: `ts-order-service [HIGH_GC_PRESSURE, PROCESS_PAUSED]`.
- **Divergence**: order-service's 90s GC pause is a real second-order symptom — backpressure from travel-plan-service blocking on a 605ms train call causes queue buildup in downstream order-service, which then GC-avalanches. Agent treated symptom-magnitude as causal priority. Never examined the travel-plan→train-service call explicitly; never considered that the GC pause could be a consequence of upstream queue backup rather than an independent infrastructure event.
- **Pivot round**: R9.
- **Proximate cause phrase**: *locked onto the loudest infrastructure hotspot (90s GC on a downstream service) without checking whether that hotspot was itself upstream of the injection target.*

---

## case_323 — TimeSkew @ ts-travel-plan-service pod (-84s clock offset)

- **GT**: ts-travel-plan-service. Fault is a pod clock offset of -84s. Propagation path shows travel-plan → ui-dashboard → loadgenerator; no downstream service is the injection target.
- **Agent (21 rounds, 818k tokens)**: Walked the latency call chain backward from SLO-violating travelplan endpoints → route-plan → travel → seat → config. Found a `SELECT Config` query at 3,435ms max (normal 1.4ms avg) inside ts-config-service. R17 CRITICAL FINDING: "ts-config-service HIGH_CPU load!" At **R20** noticed "ALL services show high CPU load – cluster-wide CPU pressure issue!" but still kept config-service as RC because it had the slowest observable DB query. Final: `ts-config-service [HIGH_LATENCY, HIGH_CPU]`.
- **Divergence**: TimeSkew has zero signature in latency/CPU/error-rate. The agent has no mental model that a fault can target a service without producing a latency/error signature at that service's own spans. Instead it assumes "SLO-violating endpoint must have slowest-leaf as RC" and drills until it finds one. It even overrode its own cluster-wide observation.
- **Pivot round**: R15 ("ts-config-service is the ROOT CAUSE").
- **Proximate cause phrase**: *drilled to slowest downstream leaf assuming the SLO-violation origin must be at a leaf of the call tree; couldn't model that the injection target itself can be symptom-silent.*

---

## case_339 — JVMMySQLLatency @ ts-travel-service→MySQL SELECT `trip` (3669ms)

- **GT**: ts-travel-service + mysql. JVM byteman-style hook in ts-travel-service delays every SELECT on table `trip` by 3669ms.
- **Agent (49 rounds, 3.4M tokens)**: Became entangled in three distinct noise issues at once: (a) ts-food-service UnknownHostException for ts-rabbitmq; (b) ts-consign-service 120 NonUniqueResultException SEVERE errors for a specific order ID (data integrity noise); (c) ts-order-service `findByTravelDateAndTrainNumber` max 3.70s. Oscillated between candidates for ~35 rounds, final merge was a compromise picking both **ts-consign-service** (for preserve-endpoint SLO) and **ts-order-service** (for travelplan-endpoint SLO). Never considered ts-travel-service itself despite its max POST span being 6.46s.
- **Divergence**: injection delay of 3669ms matches the `findByTravelDateAndTrainNumber` max of ~3.70s — but agent attributed it to ts-order-service (which shares the MySQL instance and saw collateral latency on its own queries). Misattributed the fault to the wrong JVM client of the same MySQL.
- **Pivot round**: ~R14 (first locking on order-service) + R48 (adding consign-service).
- **Proximate cause phrase**: *exhausted budget oscillating between multiple distinct environmental noises (rabbitmq DNS, consign duplicate records, order-service DB) and committed to a compromise multi-RC answer without testing which service hosted the JVM hook.*

---

## case_371 — HTTPRequestDelay @ ts-travel2-service→ts-seat-service (3512ms)

- **GT**: ts-travel2-service + ts-seat-service. Request-side HTTP delay on travel2's outgoing call to seat-service.
- **Agent (31 rounds, 1.7M tokens)**: Identified ts-travel2-service had `db.client.connections.use_time` = 3469ms (extremely close to the 3512ms injection value, the literal fault signature) and flagged travel2 with HIGH_ERROR_RATE. But then built an alternative narrative around "worker1 has system load 221 vs normal 7.3, and ts-basic-service lives on worker1, so connection reset from ts-travel2→ts-basic-service is the root". Pivot **~R22** (worker1 hotspot narrative). Final: `ts-basic-service [CONNECTION_RESET, HIGH_LATENCY]`.
- **Divergence**: the literal fault magnitude (~3.5s on travel2-service) was visible in the right metric but agent discounted it in favor of the more evocative "overloaded node + connection reset" story on an unrelated worker.
- **Pivot round**: R22 (worker1 overload hypothesis cemented).
- **Proximate cause phrase**: *preferred a coherent infrastructure-overload narrative on a bystander node over a numerically-matching fault-magnitude signal that pointed directly at the injection target.*

---

## case_471 — ContainerKill @ ts-assurance-service pod

- **GT**: ts-assurance-service. Pod is killed at 05:59:50, restarts by 05:59:56.
- **Agent (32 rounds, 1.3M tokens)**: Correctly detected at **R20**: "CRITICAL FINDING! ts-assurance-service pod has RESTARTED!" with k8s.container.restarts=1. But then at **R28** discovered MySQL logs show 10 simultaneous connection aborts from IP 10.0.5.85 at exactly 05:59:50 (same incident start). Concluded MySQL is the root cause and the assurance pod restart is a consequence (liveness probe failed because it couldn't reach MySQL). Final: `mysql [UNAVAILABLE]`, assurance-service downstream.
- **Divergence**: causal direction inverted. 10.0.5.85 was the assurance-service pod IP; when Chaos Mesh killed its container, those 10 MySQL connections from that pod were torn down, showing up as "connections aborted" in the MySQL log. The agent observed correlation in time (both at 05:59:50) and picked the more systemically-impactful candidate (MySQL) as cause rather than the narrower container-kill observation.
- **Pivot round**: R28 (MySQL-abort discovery) → R30 (commitment).
- **Proximate cause phrase**: *correctly spotted the container restart, then inverted causal direction when a correlated-in-time database signal appeared, preferring the broader infrastructure story over the narrower one already in hand.*

---

## case_572 — (fault type from dossier shows **HTTPResponseDelay-ish**; GT services `ts-food-service, ts-train-food-service`)

- **GT**: ts-food-service + ts-train-food-service. (Lookup: ts5-... datapack.)
- **Agent (~40 rounds)**: Focused on ts-order-service GC pressure (GC max 8.54s vs normal 2.89s) and ts-consign-service NonUniqueResultException data-integrity noise. Explicitly noted ts-cancel-service 1.2s GC at R37 then dismissed as "outlier". Final picked both `ts-order-service [HIGH_GC_PRESSURE]` + `ts-consign-service [HIGH_ERROR_RATE]` (dual compromise RC).
- **Divergence**: food-service / train-food-service were never considered despite being mentioned in A.5 error-log signatures. Agent treated the food-service DNS noise as environmental noise and ignored the hint. Instead preferred the loudest GC hotspot + loudest exception-throwing service as dual RC.
- **Pivot round**: R20-ish (locking on order-service GC).
- **Proximate cause phrase**: *latched onto the two loudest signatures (GC avalanche + stack-trace-throwing service) and treated the food-service errors as ambient noise, missing that they were the injection target.*

---

## case_675 — NetworkChaos / connection reset @ ts-route-plan-service→ts-travel-service and ts-travel2-service paths

- **GT**: ts-route-plan-service + ts-route-service.
- **Agent (many rounds)**: Found ts-route-plan-service has 1040 NullPointerExceptions and only 2 "Connection reset" log entries (Java log deduplication). All NPE sources are route-plan-service's code calling ts-travel-service/ts-travel2-service. Concluded the root cause is "ts-travel-service (and ts-travel2-service) dropping connections to ts-route-plan-service". Final: `ts-travel-service + ts-travel2-service [CONNECTION_RESET]`. 
- **Divergence**: ts-travel-service/ts-travel2-service are responding normally to OTHER callers (ts-ui-dashboard, ts-basic-service). The selective failure only on the ts-route-plan-service→ts-travel-service path implies the fault is injected at ts-route-plan-service's client-side (network chaos egress rule). Agent picked the callees (visible as "unreachable from one caller") rather than the caller hosting the network-chaos rule.
- **Pivot round**: mid-way, when the "1040 NPE / 2 CR logs" pattern was discovered.
- **Proximate cause phrase**: *observed selective connection-reset from a single caller, but attributed it to the two callees being unstable rather than recognizing that the caller was hosting an egress network-chaos rule.*

---

## case_1140 — (PodChaos/something on `ts-food-service` or `ts-ui-dashboard`; GT `ts-food-service, ts-ui-dashboard`)

- **GT**: ts-food-service + ts-ui-dashboard.
- **Agent (~38 rounds)**: Zeroed in on ts-seat-service (peak CPU 1.47 cores vs normal 0.32, peak utilization 29.5%, called by preserve-flow) and called out a suspicious 2.7s gap between seat-service sending and order-service receiving a request, theorizing "order-service HTTP thread pool full". At **R38** noticed ts-admin-order-service had +1233% CPU with zero HTTP traces (mysterious background batch). Ultimately picked `ts-seat-service [HIGH_CPU, HIGH_LATENCY]`. GT's food/ui-dashboard never touched.
- **Divergence**: food-service and ui-dashboard both had active anomalies but food-service's signature was masked by the ambient rabbitmq-DNS noise that always exists in this environment. ui-dashboard is a frontend proxy — agent never probes frontend layer for RC.
- **Pivot round**: R24-ish (committing to seat-service HIGH_CPU).
- **Proximate cause phrase**: *followed a CPU-hotspot on a mid-stack service while refusing to consider frontend (ui-dashboard) or persistently-noisy (food-service) candidates as RC.*

---

## case_1144 — (fault_type `ts-food-service`)

- **GT**: ts-food-service.
- **Agent**: Final picked `ts-rabbitmq [UNAVAILABLE]`. Saw the food/notification/delivery trio all reporting "Failed to check/redeclare auto-delete queue" + DNS UnknownHostException for ts-rabbitmq. Built a story where rabbitmq is down, which breaks food/notification/delivery, which cascades to preserve.
- **Divergence**: ts-rabbitmq is **never** a service that exists in this cluster — there is no DNS entry, there is no pod. The DNS failure is a permanent background artifact (three services are misconfigured to reach a nonexistent host). The agent interpreted a stable baseline misconfiguration as an active "service became unavailable" fault.
- **Pivot round**: early (rabbitmq hypothesis formed almost immediately when the DNS errors were seen).
- **Proximate cause phrase**: *interpreted a chronic-environmental DNS-noise signature (rabbitmq does not exist) as an active infrastructure outage and assigned it as the root cause.*

---

## case_1280 — (GT `ts-preserve-service`)

- **GT**: ts-preserve-service.
- **Agent**: Final picked `ts-rabbitmq [UNAVAILABLE]` with preserve-service as "KILLED" downstream. Same rabbitmq-DNS narrative as case_1144. Missed that ts-preserve-service was the one directly experiencing the injection (likely a pod kill or network chaos on preserve).
- **Divergence**: Same pattern as 1144 — ambient rabbitmq DNS noise assigned as RC, true injection target (preserve) seen as victim.
- **Pivot round**: early.
- **Proximate cause phrase**: *same as 1144: chronic rabbitmq-DNS noise adopted as RC, making the actual injection target look like a downstream victim.*

---

## case_1326 — HTTPResponseReplaceBody @ ts-route-plan-service→ts-travel2-service (replaces response body with garbage `nvpwzt`)

- **GT**: ts-route-plan-service + ts-travel2-service.
- **Agent (~41 rounds)**: Route-plan-service logs show 1103 SEVERE NPEs. Agent noted NO errors in ts-route-service, ts-travel-service, or ts-travel2-service (only INFO) and that Hubble records 27,894 HTTP requests to ts-route-service (vs ~200 trace spans). R41: "the corruption is happening at the TRANSPORT/NETWORK level or at a proxy layer, NOT within ts-route-service's application code." Final picked `ts-route-service` as RC.
- **Divergence**: the response corruption IS at the HTTP level, but the fault is injected at the **caller's** side (ts-route-plan-service intercepts the response when calling ts-travel2-service). Agent picked the wrong endpoint of the injected pair (route-service vs travel2-service) and even though route-service had no anomalies, still committed there.
- **Pivot round**: R41.
- **Proximate cause phrase**: *recognized that fault lived at the HTTP layer between services, but picked the wrong service on that edge — the one with higher traffic volume but no actual anomaly signature.*

---

## case_1421 — DNSRandom @ ts-station-service, domain=mysql

- **GT**: ts-station-service + mysql. Injects random DNS responses when ts-station-service tries to resolve `mysql`.
- **Agent**: Predicted `ts-config-service` as RC (another service with slow DB queries). Did not probe DNS, did not suspect DNS injection. Fell into the same config-service-as-slowest-leaf trap as case_323.
- **Divergence**: DNS-random fault produces intermittent connection failures / retries on ts-station-service's MySQL connections, manifesting as occasional spike latency on station-service's DB operations. Agent never inspected DNS-layer signals (it has no tool for that), drilled to slowest leaf instead.
- **Pivot round**: early.
- **Proximate cause phrase**: *drilled to slowest-DB-leaf service; has no cognitive model for DNS/network-layer faults so couldn't form a DNS hypothesis even with strong hints.*

---

## case_1484 — HTTPResponseDelay @ ts-travel-plan-service→ts-train-service (4221ms)

- **GT**: ts-travel-plan-service + ts-train-service. Nearly identical injection spec to case_315 (different magnitude).
- **Agent (~40 rounds)**: At R39 decomposed a 20-second travelplan trace and found ts-travel-plan-service → ts-seat-service `POST /seats/left_tickets` at 2867ms. Also noted travel-plan directly calls seat-service. Picked `ts-seat-service` as RC. Never noticed the intrinsic "travel-plan spends huge time waiting on its calls to train-service" (which would match injection).
- **Divergence**: same as 315 — but here agent zoomed on a different downstream (seat-service rather than order-service) based on which 2-3s outlier stood out in the specific trace sampled. Same underlying miss: didn't trace the `/trainservice/trains/byName/*` call.
- **Pivot round**: R39.
- **Proximate cause phrase**: *sampled one slow trace and picked whichever downstream leaf had the most-visible span — same drill-to-leaf pattern as case 315, just a different leaf.*

---

## case_1495 — JVMMemoryStress @ ts-travel-plan-service (controller method: `home`, mem_type=1 heap)

- **GT**: ts-travel-plan-service.
- **Agent (~42 rounds)**: Identified worker2 system load 82 vs normal 7.5 (→ 11x) hosting ts-seat-service. Called out the disproportion between "pods collectively use <1 core but system load is 82" — which is a good observation. Still picked `ts-seat-service` as RC based on "it has max CPU of 1.47 cores and lives on worker2". Never probed ts-travel-plan-service pod's memory, GC, or heap metrics despite JVMMemoryStress targeting travel-plan's JVM.
- **Divergence**: JVMMemoryStress intrinsically pressures the injected service's JVM, producing slow responses from travel-plan — indistinguishable from "downstream slow" in traces. Agent chose the downstream with the most infrastructure-level anomaly.
- **Pivot round**: R35-ish.
- **Proximate cause phrase**: *JVM-intrinsic faults look identical to "slow downstream" from trace perspective; agent has no protocol for attributing slowness to the service hosting the fault hook, so it consistently selects the slowest-downstream.*

---

## case_1862 — ContainerKill @ ts-food-service pod

- **GT**: ts-food-service.
- **Agent**: Picked `ts-rabbitmq [UNAVAILABLE]`. Again the rabbitmq DNS noise dominated. Missing: food-service pod restart signal.
- **Divergence**: food-service's own container restart is the ground truth, but its absence/partial-unavailability triggered the usual rabbitmq-DNS errors from other services, which agent picked as a stronger-looking unavailability signal.
- **Pivot round**: early.
- **Proximate cause phrase**: *ambient rabbitmq-DNS noise selected as RC whenever food-service is perturbed in any way, because the DNS signature is loud and unambiguous while the actual fault's signature is subtle.*

---

## case_1880 — HTTPResponseReplaceBody @ ts-food-service→ts-travel-service (response body corruption)

- **GT**: ts-food-service + ts-travel-service.
- **Agent**: Picked `ts-route-service` as RC. Essentially same pattern as case_1326 but shifted: ts-food-service calls ts-travel-service and gets body-corrupted response. Agent picked a neighbor on the call graph (route-service) that had high traffic but no actual anomaly.
- **Divergence**: fault lives on the ts-food-service→ts-travel-service edge. Agent picked a sibling service (route-service). Suggests when the agent can't localize to a specific service and sees high-traffic on an adjacent edge, it defaults to the high-traffic service as RC.
- **Pivot round**: similar to 1326.
- **Proximate cause phrase**: *picked a high-traffic sibling as RC under uncertainty rather than acknowledging the uncertainty; reflexive fallback to "highest-traffic-looking service on the adjacent edge."*

---

## case_1948 — ContainerKill @ ts-preserve-service pod

- **GT**: ts-preserve-service.
- **Agent**: Picked `ts-basic-service + ts-seat-service` as dual RC. Preserve was restarted during the incident window. During the pod restart, preserve couldn't reach downstream services, generating a cascade of error-rate spikes. Agent attributed the cascade to the two services preserve failed to reach rather than recognizing preserve itself was the one with intermittent availability.
- **Divergence**: container-kill → during the ~6–10s restart window, all in-flight calls from preserve fail; from trace perspective, preserve's own calls to basic-service/seat-service fail. Agent misreads "preserve's calls to X fail" as "X is unavailable" rather than "preserve is crashing during its calls".
- **Pivot round**: mid-way.
- **Proximate cause phrase**: *during a pod-restart window, misread failed outgoing calls as evidence that the callees were unavailable rather than the caller was crashing.*

---

## case_2011 — HTTPRequestAbort @ ts-route-plan-service→ts-travel2-service (connection abort on route path)

- **GT**: ts-route-plan-service + ts-travel2-service.
- **Agent**: Picked `ts-travel-service`. Same pattern as case_1326 / 1880 — picked wrong-service on the call edge.
- **Divergence**: HTTP request abort fault is injected at route-plan (caller side), affecting its calls to travel2. Agent swapped to a sibling (travel-service vs travel2-service).
- **Pivot round**: mid-way.
- **Proximate cause phrase**: *consistent inability to distinguish which side of an A→B edge hosts the chaos rule; defaults to sibling service under uncertainty.*

---

## case_2130 — JVMReturn @ ts-station-service (method `main`)

- **GT**: ts-station-service.
- **Agent**: Picked `ts-route-service` as RC. JVMReturn injects an early-return in a method, causing station-service's main flow to produce empty/invalid results. Downstream of station, route-service (which looks up routes) sees weirdness. Agent blamed route-service.
- **Divergence**: JVMReturn at station produces correct-looking but semantically-wrong outputs, which downstream services then struggle with. Agent can't distinguish "service X produces wrong output" from "service downstream-of-X is broken" because both show up as downstream errors.
- **Pivot round**: early, once route-service misbehavior was visible.
- **Proximate cause phrase**: *JVM-return injections produce silently-corrupted responses; agent can only detect the downstream confusion, not the source of the corruption.*

---

## case_2174 — JVMException @ ts-travel-plan-service (method `queryTrainTypeByName`)

- **GT**: ts-travel-plan-service.
- **Agent**: Picked `ts-route-plan-service`. JVMException throws an exception in travel-plan's `queryTrainTypeByName` method, causing travel-plan to fail requests. Agent observed route-plan having exception cascade (because travel-plan calls route-plan as part of its flow and fails mid-way, which route-plan sees as weird truncated requests).
- **Divergence**: same JVM-intrinsic-fault pattern as 1495, 2130. Injection target is symptom-silent at its own service boundary (it produces errors that look like its own controller is bad, but these are attributed to downstream).
- **Pivot round**: early.
- **Proximate cause phrase**: *JVM-exception at the injected service produces 500 responses; agent traces 500 to a downstream service that was called in the same trace, thinking "the one that errored is the culprit."*

---

## Batch-1 quick counts (preliminary phrases)

| phrase (preliminary) | case_ids |
|---|---|
| drill to slowest downstream leaf (JVM/Time/HTTPDelay intrinsic-at-caller) | 315, 323, 1484, 1495, 2130, 2174 |
| chronic rabbitmq-DNS noise adopted as RC | 1144, 1280, 1862 |
| wrong side of A→B edge under uncertainty | 1326, 1880, 2011, 675 |
| causal-direction inversion (cause and its consequence both observed, agent picks the bigger-scope consequence) | 471 |
| container-kill cascade misread (caller's failures attributed to callees) | 1948 |
| compromise multi-RC after round-budget exhaustion | 339, 572 |
| loudest infrastructure hotspot adopted without causal-direction check | 315, 371 |
| drill to unrelated-leaf through infrastructure noise | 1140, 1421 |

Some cases span multiple phrases; this grid is pre-clustering, not final. Taxonomy work lives in `taxonomy_working.md`.

---

## Batch 2 (cases 2183–3493)

## case_2183 — HTTPRequestDelay @ ts-travel-plan-service→ts-seat-service (2303ms)

- **GT**: ts-travel-plan-service + ts-seat-service. Fault delays every travel-plan→seat call.
- **Agent (28 rounds)**: Drill-to-leaf. Picked `ts-config-service` — picked the slowest DB query at a leaf.
- **Divergence**: Same as case 323/1495 — drilled past the injection-hosting service to a downstream DB leaf.
- **Proximate cause phrase**: *same as 323/1495: drilled to slowest-DB-leaf downstream when injection is request-delay at the caller.*

## case_2541 — JVMException @ ts-order-other-service (method `queryOrdersForRefresh`)

- **GT**: ts-order-other-service.
- **Agent (62 rounds, 2.7M tokens)**: Observed ts-order-other-service fails with RuntimeException on refresh endpoint (!) but then preferred a memory/GC narrative on ts-seat-service (memory growth from 0.75GB → 1.96GB). Final picked `ts-seat-service [HIGH_MEMORY, HIGH_GC_PRESSURE]`.
- **Divergence**: agent saw the directly-matching exception evidence (order-other's RuntimeException) but preferred a richer multi-turn infrastructure narrative on the memory-climbing neighbor.
- **Proximate cause phrase**: *saw the literal exception signal on the injection target but discounted it in favor of a more-elaborate memory-growth narrative on a neighboring service.*

## case_2584 — NetworkBandwidth @ ts-preserve-service→ts-travel-service

- **GT**: ts-preserve-service + ts-travel-service. Bandwidth limit on the link.
- **Agent (54 rounds, 4.96M tokens)**: Traced preserve's 20s hangs to "Step 3: Check tickets num" → travel-service call that hangs. But attributed the hang to ts-basic-service (which travel-service calls internally). Final picked `ts-basic-service`.
- **Divergence**: correctly found that preserve-requests hang at the travel-service boundary, then drilled one more step down into travel's internal call tree and picked basic-service. Classic T3 with T6 overtones.
- **Proximate cause phrase**: *drilled one layer past the actual bandwidth-limited edge to an internal downstream call that was slow-by-propagation only.*

## case_2597 — HTTPRequestDelay @ ts-preserve-service→ts-seat-service (3308ms)

- **GT**: ts-preserve-service + ts-seat-service.
- **Agent (39 rounds)**: Picked `rabbitmq`. Rabbitmq-DNS-noise narrative dominated despite the actual fault being a clean HTTP delay on preserve→seat.
- **Proximate cause phrase**: *chronic rabbitmq-DNS noise again; preserve-service involvement amplified the background errors from food/notification, agent picked the loudest one.*

## case_2616 — NetworkCorrupt @ ts-route-plan-service→ts-travel-plan-service

- **GT**: ts-route-plan-service + ts-travel-plan-service.
- **Agent (38 rounds)**: Picked `ts-seat-service`. Corrupted packets at route-plan→travel-plan produce garbled responses; seat-service is a downstream sibling of travel-plan that also showed elevated latency. Agent picked the sibling with the most CPU/latency signal.
- **Proximate cause phrase**: *when the fault is on edge A→B, agent reaches for a sibling of B as RC based on raw anomaly magnitude; no protocol for edge-side attribution.*

## case_2640 — HTTPResponseDelay @ ts-route-plan-service→ts-travel-service (3427ms)

- **GT**: ts-route-plan-service + ts-travel-service.
- **Agent (29 rounds)**: Picked `ts-route-service` — a sibling of travel-service (both called from route-plan). Drill-to-leaf on a plausible-looking adjacent service.
- **Proximate cause phrase**: *picked a sibling of the actual callee; could not distinguish route-service (downstream of route-plan) from travel-service (the other downstream of route-plan that hosts the injection).*

## case_2678 — NetworkBandwidth @ ts-seat-service→ts-config-service

- **GT**: ts-seat-service + ts-config-service.
- **Agent (32 rounds)**: Picked `ts-travel2-service`. Seat-service's bandwidth-limited config calls cascade through seat→travel/travel2/route-plan. Agent picked travel2 (a sibling of seat's caller).
- **Proximate cause phrase**: *when bandwidth-limit is on A→B, agent picks a sibling of A (not A itself) based on which sibling looks most infrastructurally-anomalous.*

## case_2682 — NetworkDelay @ ts-seat-service→ts-travel-plan-service

- **GT**: ts-seat-service + ts-travel-plan-service.
- **Agent (30 rounds)**: Picked `ts-route-service + ts-order-service` — dual compromise. Neither matches GT; agent landed on two services with visible latency but unrelated to the seat→travel-plan edge.
- **Proximate cause phrase**: *compromise-pair under edge-direction uncertainty; picked two unrelated hotspots rather than identifying either endpoint of the injected edge.*

## case_2715 — NetworkBandwidth @ ts-station-service→ts-basic-service

- **GT**: ts-station-service + ts-basic-service.
- **Agent (23 rounds)**: Picked `ts-travel-service`. Travel-service calls basic-service and sees elevated latency; agent picked the caller-of-the-callee.
- **Proximate cause phrase**: *wrong side of A→B edge again; picked a non-A, non-B service that observes the effect.*

## case_2748 — NetworkLoss @ ts-travel-plan-service→ts-ui-dashboard

- **GT**: ts-travel-plan-service + ts-ui-dashboard.
- **Agent (42 rounds, 2.9M tokens)**: Picked `ts-travel2-service`. Travel2 is a peer of travel-plan (both called by similar endpoints). Agent picked the peer with visible latency.
- **Proximate cause phrase**: *picked a peer/sibling when the fault was on a travel-plan→ui-dashboard egress edge; agent has no concept of egress-side egress-to-dashboard chaos.*

## case_2801 — HTTPResponseReplaceBody @ ts-travel-service→ts-basic-service

- **GT**: ts-travel-service + ts-basic-service.
- **Agent (47 rounds, 3.4M tokens)**: Picked `ts-cancel-service + ts-seat-service`. Neither on the injected edge. Compromise under exhaustion.
- **Proximate cause phrase**: *exhaustion compromise pair that does not intersect either endpoint of the injected edge.*

## case_2830 — HTTPRequestAbort @ ts-travel2-service→ts-seat-service

- **GT**: ts-travel2-service + ts-seat-service.
- **Agent (41 rounds, 2.5M tokens)**: Picked `ts-basic-service`. Same edge-confusion pattern.
- **Proximate cause phrase**: *same A→B edge pattern: picked a third service entirely.*

## case_2836 — HTTPResponseReplaceBody @ ts-travel2-service→ts-basic-service

- **GT**: ts-travel2-service + ts-basic-service.
- **Agent (28 rounds)**: Picked `ts-seat-service`.
- **Proximate cause phrase**: *yet another A→B edge case where agent picked a sibling.*

## case_3033 — HTTPResponseReplaceCode @ ts-food-service→ts-train-food-service

- **GT**: ts-food-service + ts-train-food-service.
- **Agent (46 rounds, 3.7M tokens)**: Picked `ts-seat-service`. Food/train-food chain masked by environmental rabbitmq-DNS noise, so agent drilled to a seat-service hotspot.
- **Proximate cause phrase**: *rabbitmq-DNS noise masked the food-service fault; agent defaulted to drilling to a visible downstream CPU hotspot.*

## case_3107 — JVMException @ ts-preserve-service (method `preserve`)

- **GT**: ts-preserve-service.
- **Agent (32 rounds)**: Picked `ts-rabbitmq`. JVM exception at preserve produces preserve failures → triggers food/notification/delivery retry storms → amplifies the rabbitmq-DNS noise → agent picks rabbitmq.
- **Proximate cause phrase**: *rabbitmq-DNS amplification pattern: when preserve-service fails for any reason, cascades amplify ambient DNS errors which agent picks as RC.*

## case_3112 — NetworkPartition @ ts-preserve-service→ts-seat-service

- **GT**: ts-preserve-service + ts-seat-service.
- **Agent (35 rounds)**: Picked `rabbitmq`. Same rabbitmq noise pattern as 3107.
- **Proximate cause phrase**: *same as 3107: preserve perturbation → rabbitmq-noise amplification → picked as RC.*

## case_3125 — HTTPResponseDelay @ ts-preserve-service→ts-security-service (4226ms)

- **GT**: ts-preserve-service + ts-security-service.
- **Agent (30 rounds)**: Picked `ts-price-service`. Drilled to a hotspot not on the preserve→security edge.
- **Proximate cause phrase**: *drilled to a non-adjacent hotspot; no attempt to trace back to preserve-service's outgoing security call specifically.*

## case_3236 — NetworkBandwidth @ ts-security-service→mysql

- **GT**: ts-security-service + mysql.
- **Agent (26 rounds)**: Picked `mysql-0` (pod name). Observed MySQL container.cpu.time frozen in repeating 10-15s windows and inferred PROCESS_PAUSED. Correct for one of two GT services, but: (a) used pod-level name `mysql-0` instead of service name `mysql`, (b) missed ts-security-service as co-RC, (c) inferred MySQL is paused but actually MySQL is bandwidth-starved of requests (silence, not pausing).
- **Divergence**: the reasoning is partially correct (mysql is part of GT) but fundamentally confused silence-from-bandwidth-starvation with process-paused. Judge rejected for exact-string mismatch.
- **Proximate cause phrase**: *interpreted traffic silence (caused by bandwidth limit on upstream caller) as a MySQL PROCESS_PAUSED signal; missed the security-service co-RC; pod-name vs service-name granularity issue.*

## case_3284 — NetworkDelay @ ts-travel-plan-service→ts-seat-service

- **GT**: ts-travel-plan-service + ts-seat-service.
- **Agent (58 rounds, 3.5M tokens)**: Picked `ts-config-service`. Another drill-to-leaf under exhaustion.
- **Proximate cause phrase**: *extended exhaustion (58 rounds) on an edge-faulted case; eventually picked a downstream DB-query hotspot.*

## case_3493 — HTTPResponseReplaceCode @ ts-security-service→ts-order-service

- **GT**: ts-security-service + ts-order-service.
- **Agent (26 rounds)**: Picked `ts-order-other-service`. A very-close sibling of order-service, also DB-backed; agent can't distinguish order-service from order-other-service in the call tree.
- **Proximate cause phrase*: *picked the near-twin sibling (order-other vs order); couldn't disambiguate between two near-identical services.*

---

## Batch 3 (cases 3554–4739)

## case_3554 — HTTPResponseAbort @ ts-travel-service→ts-basic-service

- **GT**: ts-travel-service + ts-basic-service.
- **Agent (43 rounds, 2.8M tokens)**: Picked `ts-admin-user-service` — a service NOT on any real call path for the SLO endpoints. Observed ts-admin-user-service had 107x CPU increase (0.008→0.859 cores max) and built a narrative around it: "admin-user-service high CPU → MySQL degradation → cascade". Never tested whether admin-user-service could actually be upstream of the travel-service SLO.
- **Divergence**: selected a completely-off-path service as RC purely on anomaly magnitude, with an infrastructure-contention narrative bridging the gap. Even more extreme than case 315's LoudestHotspot.
- **Proximate cause phrase**: *picked a fully off-path service with the loudest CPU spike and wove an infrastructure-contention narrative to connect it to the SLO; no causal validation against actual call graph.*

## case_3555 — HTTPResponseDelay @ ts-travel-service→ts-basic-service (1462ms)

- **GT**: ts-travel-service + ts-basic-service.
- **Agent (26 rounds)**: Picked `ts-seat-service`. Edge-confusion — picked a sibling of basic-service.
- **Proximate cause phrase**: *A→B edge pattern: picked sibling seat-service instead of injected edge endpoints.*

## case_3592 — HTTPResponseDelay @ ts-route-plan-service→ts-travel2-service (4548ms)

- **GT**: ts-route-plan-service + ts-travel2-service.
- **Agent (36 rounds)**: Picked `ts-travel-service`. A sibling of travel2 (both called from route-plan). Swapped travel-service in for travel2-service.
- **Proximate cause phrase**: *near-twin sibling confusion (travel vs travel2); agent can't tell which of the two is the actual callee.*

## case_3868 — JVMLatency @ ts-config-service (method `deleteConfig`)

- **GT**: ts-config-service.
- **Agent (39 rounds)**: Picked `ts-basic-service`. JVM-intrinsic fault pattern: config-service's slowness attributed to basic-service which calls config and also appears slow.
- **Proximate cause phrase**: *JVM-intrinsic slowness on config-service reads as "config's callers are slow"; agent picked a caller (basic-service).*

## case_4229 — NetworkPartition @ ts-basic-service→ts-travel-service

- **GT**: ts-basic-service + ts-travel-service.
- **Agent (48 rounds)**: Picked `ts-seat-service`.
- **Proximate cause phrase**: *A→B edge: picked seat-service sibling; same pattern.*

## case_4423 — NetworkBandwidth @ ts-basic-service→ts-preserve-service

- **GT**: ts-basic-service + ts-preserve-service. (Note: unusual direction — bandwidth-limit is on basic→preserve, but basic-service does not call preserve in normal topology; this is likely bandwidth limit on the REVERSE path — preserve to basic, with label convention switched.)
- **Agent (52 rounds, 3.7M tokens)**: Picked `ts-seat-service`. Under high exhaustion, defaulted to the most CPU-intensive visible service.
- **Proximate cause phrase**: *edge confusion + exhaustion; picked seat as the "most CPU-anomalous" default.*

## case_4433 — HTTPResponseReplaceCode @ ts-basic-service→ts-route-service

- **GT**: ts-basic-service + ts-route-service.
- **Agent (70 rounds, 3.8M tokens)**: Picked `ts-price-service`. Noted that ts-price-service had GET spans drop from 322→2 in abnormal period + its container CPU time was "frozen" (very slowly increasing). Inferred PROCESS_PAUSED. But actually price-service is just idle because its caller (basic) is failing upstream calls (due to the replaced-code fault on basic→route) and NOT invoking price-service.
- **Divergence**: similar to case 3236 (silence-misread) but in reverse direction: here agent saw a QUIET service and inferred it's paused, when it's just upstream-starved.
- **Proximate cause phrase**: *silence-means-paused inference applied to a quiet service; agent concluded price-service is PROCESS_PAUSED when it's just idle because its upstream (basic-service) is failing.*

## case_4463 — ContainerKill @ ts-food-service pod (NOTE: GT says ts-config-service, likely dataset labeling issue)

- **GT**: ts-config-service (per DB meta); datapack name says food-service.
- **Agent (33 rounds)**: Picked `ts-food-service`. Matches the datapack; does not match the DB meta.
- **Divergence**: this case is ambiguous — likely a dataset-labeling anomaly where the DB meta and the fault injection do not agree. From the agent's perspective the answer is reasonable (food-service pod was indeed killed). Mark as **dataset_anomaly** rather than a genuine agent error.
- **Proximate cause phrase**: *dataset labeling mismatch; agent's answer is consistent with the injection spec but inconsistent with the DB-stored GT.*

## case_4510 — NetworkBandwidth @ ts-route-plan-service→ts-travel-service

- **GT**: ts-route-plan-service + ts-travel-service.
- **Agent (36 rounds)**: Picked `ts-travel2-service`. Travel2-service is a peer of travel-service; agent picked the wrong twin.
- **Proximate cause phrase**: *travel / travel2 near-twin swap again.*

## case_4707 — HTTPResponseReplaceBody @ ts-seat-service→ts-order-other-service

- **GT**: ts-seat-service + ts-order-other-service.
- **Agent (36 rounds)**: Picked `rabbitmq + ts-order-service`. Rabbitmq-DNS amplification + order/order-other sibling confusion. Compromise dual-RC.
- **Proximate cause phrase**: *rabbitmq noise + order/order-other twin confusion combined into a two-RC answer.*

## case_4739 — ContainerKill @ ts-travel-plan-service pod

- **GT**: ts-travel-plan-service.
- **Agent (30 rounds)**: Picked `ts-basic-service`. During the travel-plan restart window, its outgoing calls fail; agent attributed the failures to the callees (one of which is basic-service).
- **Proximate cause phrase**: *restart-window inversion again: dead pod's failed outgoing calls misread as "callee is unavailable".*


