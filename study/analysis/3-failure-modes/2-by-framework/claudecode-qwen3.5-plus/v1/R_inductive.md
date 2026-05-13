# claudecode-qwen3.5-plus — Inductive R-class Taxonomy (round 1)

Framework: claudecode-qwen3.5-plus (Claude Code CLI with Bash/DuckDB over parquet; qwen3.5-plus backend)
Total labeled failures: 103
AC@1 reference: 79.4%
Derivation basis: 103 R-phrases in `R_phrases.jsonl`, triangulated against `labels.jsonl` + `per_case_analysis.md` (dossiers confirmed for 4 sampled cases: 283, 341, 807, 1195).
NO v2 seed was consulted.

## Distribution

| R class | Count | Share | Gloss |
|---|---|---|---|
| R1 SilentOriginShadowedByNoisyNeighbor | 29 | 28.2% | Silent/dead injected service; noisier caller or sibling named root |
| R2 ChronicInfraNoiseAnchored_RabbitMQDNS | 24 | 23.3% | Anchored on `UnknownHostException: ts-rabbitmq` cluster present in normal_logs |
| R3 FabricatedAncestorOrBaselineLog | 11 | 10.7% | Non-RabbitMQ baseline-noise or invented upstream ancestor named root |
| R4 OutermostReceiverOrInvertedEdge | 17 | 16.5% | Correct node identified but edge inverted / ingress named root |
| R5 SimilarNameSiblingConfused | 10 | 9.7% | Close-named microservice variant named root |
| R6 InfraLayerSkipped_AppLayerAnchored | 7 | 6.8% | Stopped at first app-layer novel-error service, never queried mysql/net/DNS layer |
| R7 JVMSymptomMisreadAsDB | 4 | 3.9% | HikariCP/connection-pool warnings interpreted as a mysql fault |
| (deferred: dataset_anomaly) | 1 | 1.0% | case 4463 — GT/injection-name mismatch |

Sum of R1–R7 = 102 (MECE, 1 deferred case → F / dataset-filter candidate).

---

## R1 — SilentOriginShadowedByNoisyNeighbor (29 cases, 28.2%)

### Definition
The injected service is effectively silent during the window — either because a pod is dead (no spans), or because a thread-blocking fault (JVM memory / network partition / response-delay) causes requests to hang without completing. The agent anchors on a noisier neighbor (usually an upstream caller carrying 'Connection refused' / 'HIGH_ERROR_RATE' / 'UNAVAILABLE' markers, or a same-layer sibling with loud logs) and names it root. The silent origin is either entirely absent from the output graph or retained as a cascade child.

### Positive examples (canonical)
- **case_341 (PodFailure on travel-service)**: dead pod, 0 spans; agent picked route-plan-service because its errors appeared 'earliest'. Dossier confirms matched=['route-plan-service'], travel-service missed.
- **case_1394 (JVMMemoryStress on seat-service SeatController.getLeftTicketOfInterval)**: silent callee; agent picked travel-service + travel2-service as root, seat absent.
- **case_247 (JVMMemoryStress on route-service queryById)**: 17,280 spans with 0 errors — explicitly *dismissed* at round 7 because of zero error status; agent chose basic-service for its 33 visible error rows.

### Negative examples (NOT R1)
- **case_572** — silent food→train-food fault EXISTS, but agent anchored on RabbitMQ DNS errors (a separate baseline-noise signature), not on a noisier caller of train-food → R2, not R1.
- **case_1886** — inside-payment-service was correctly marked UNAVAILABLE (not 'silent' or shadowed); agent inverted the edge to ingress → R4.
- **case_1195** — payload variant (order-other vs order) → R5 naming confusion dominates over silent-origin pattern.

### Canonical member distinguisher
R1 is the defect specifically triggered when the GT injection makes the target silent (dead pod, hung thread, response-delay) AND the agent names a different service whose error surface is loud.

### Members (29)
case_ids: 33, 247, 281, 341, 710, 804, 1371, 1394, 1435, 1459, 1917, 1934, 2211, 2253, 2258, 2697, 2808, 3040, 3053, 3324, 3700, 3760, 3776, 3868, 4081, 4353, 4363, 4375, 4789

### Trajectory-only trigger
```
FIRE when ALL of:
  (a) round_count >= 10
  (b) effective_rounds vs tool_calls: agent issued >= 3 SQL queries of the form
      `GROUP BY service_name ... WHERE level IN ('ERROR','SEVERE')` or
      `GROUP BY service_name, "attr.status_code"` — and picked a candidate from the top row
  (c) the candidate service named in final root_causes is NOT the one with zero-error-high-span-count
      (equivalent: agent never issued a query of shape
      `SELECT service_name, COUNT(*) FROM abnormal_traces WHERE "attr.status_code" = 'Unset' GROUP BY service_name ORDER BY COUNT(*) DESC`
      OR never issued a query that filters on span duration/latency without filtering on error status)
  (d) agent performed <= 1 `Read`/`Bash` query explicitly targeting span-duration of a 'healthy-looking' (error=0) service

Evidence shape from claudecode trajectory:
  - Round N has Bash tool_call with DuckDB SQL containing "level IN ('ERROR'" or "'Error'"
  - Round N+1..N+3 contains reasoning text like "let me focus on <X> because it has the most errors"
  - Final output's root_causes[0].component == that <X>

Forbidden (GT-required): comparison of agent's root vs GT service name.
```
**Self-check FP rate**: estimated ≤35% on non-R1 failures.
- FP on R4 InvertedEdge: some R4 cases ALSO anchor on error-count ranking (e.g., 156, 2245) — but R4 distinguisher is that the chosen top is upstream in the call graph, not simply a noisy caller. Trigger fires on both, causing ≈ 6/17 R4 cases to also flag → rough FP ≈ 35%.
- FP on R5: usually R5 picks a similar-named variant rather than a higher-error one, so low overlap.
- Acceptable within ≤40% threshold.
**analytical_only**: false.

---

## R2 — ChronicInfraNoiseAnchored_RabbitMQDNS (24 cases, 23.3%)

### Definition
The agent hallucinates a root from the RabbitMQ `UnknownHostException: ts-rabbitmq: Name or service not known` log cluster. The key feature is that this error appears in **both** `normal_logs.parquet` and `abnormal_logs.parquet` at comparable frequency — it is chronic background noise, not a novel signal. The agent either: (a) never cross-checks normal vs abnormal, or (b) dismisses the noise in one round and re-includes it as root in a later round (e.g., case_1280).

### Positive examples (canonical)
- **case_1144**: agent reasoning literally states "confirm the root cause is the ts-rabbitmq DNS resolution failure"; final graph has ts-rabbitmq at top with UNAVAILABLE + DNS_ERROR markers.
- **case_572**: RabbitMQ noise named root while GT was an HTTPResponsePatchBody on food→train-food.
- **case_4229** (extreme variant): matched=[] entirely — agent's graph contains no actually-affected services, fully hallucinated cascade with rabbitmq on top.

### Negative examples (NOT R2)
- **case_2988 JVMCPUStress on basic-service**: also uses rabbitmq as root, but underlying fault is CPU stress — still R2 because the reasoning mechanism is RabbitMQ-DNS noise anchoring (fault type doesn't matter).
- **case_1484**: baseline *messaging-error* anchor BUT agent named delivery-service rather than rabbitmq → R3 (hallucinated-ancestor/non-rabbitmq baseline).
- **case_3391**: fabricated basic-service as root → R3 (no rabbitmq).

### Members (24)
case_ids: 572, 762, 864, 1004, 1118, 1143, 1144, 1159, 1686, 1862, 2512, 2716, 2988, 3041, 3076, 3114, 3555, 3622, 3716, 3966, 4054, 4229, 4791, 4823

### Trajectory-only trigger
```
FIRE when ALL of:
  (a) agent issued a Bash SQL containing 'service_name = ' AND ('ts-rabbitmq' OR 'rabbitmq')
      OR a Bash SQL with message filter containing 'UnknownHostException' / 'Name or service not known'
  (b) agent did NOT issue a comparison query of the shape
      `SELECT message, COUNT(*) FROM 'normal_logs.parquet' WHERE ... UNION SELECT message, COUNT(*) FROM 'abnormal_logs.parquet' WHERE ...`
      OR did issue such a query but still named rabbitmq in root_causes
  (c) final output's root_causes contains 'ts-rabbitmq' OR 'rabbitmq'
      OR the output's nodes list has 'ts-rabbitmq' with state including 'UNAVAILABLE'/'DNS_ERROR' marked as the graph's top

Evidence shape (from claudecode trajectories):
  - In ~15 rounds, a Bash SQL surfaces UnknownHostException hits (≥100 rows) → anchored in 2-3 subsequent reasoning turns
  - Final graph has rabbitmq node at top timestamp earlier than others
```
**Self-check FP rate**: ≤20%. The rabbitmq-root final-answer signature is highly specific. Rare overlap with R3 (case_1280 — dismissed-then-reincluded; still flags R2 correctly).
**analytical_only**: false.

---

## R3 — FabricatedAncestorOrBaselineLog (11 cases, 10.7%)

### Definition
A non-RabbitMQ variant of baseline-noise anchoring. The agent either:
(a) fabricates an upstream ancestor that does not exist in the GT call graph (e.g., basic-service, train-service at top of a travel-plan cascade), OR
(b) anchors on a non-RabbitMQ baseline-noise log signature (ORM NonUniqueResultException, ts-food-service 'Get Food Request Failed', baseline messaging errors) that also appears in `normal_logs.parquet`.

### Positive examples (canonical)
- **case_1140**: "ConsignRepository.findByOrderId did not return a unique result" — baseline ORM error present in normal_logs; network-bandwidth dimension never probed.
- **case_2641**: hallucinated train-service as top-of-chain; actual injection was route-plan→travel HTTP delay.
- **case_2489**: consign-service (the actual GT) explicitly marked HEALTHY in final graph; food-service named root.

### Negative examples (NOT R3)
- **case_572** — rabbitmq-family baseline → R2.
- **case_2245** — sprawling graph with route-plan-service on top, but route-plan-service IS a valid node in the GT call graph; miscategorization as top vs middle → R4.

### Members (11)
case_ids: 323, 1140, 1280, 1484, 2231, 2235, 2489, 2641, 2694, 3050, 3391

### Trajectory-only trigger
```
FIRE when ALL of:
  (a) final output's root_causes[0].component matches a service that appears in <10% of the agent's
      pre-final-reasoning turns (indicating it was a late-emerging or fabricated anchor)
  (b) root_cause service does NOT equal the service with highest span count in the agent's
      trace-count Bash queries
  (c) no trigger for R2 (no rabbitmq / UnknownHostException anchor)
  (d) agent issued <2 Bash SQLs joining `normal_logs.parquet` and `abnormal_logs.parquet`
      to differentiate baseline from novel

Alternative stronger signal: the agent's final graph has a `parent → child` edge where the parent
service appears in final reasoning <3 times and the child appears >8 times — suggests the parent
was fabricated late.
```
**Self-check FP rate**: ≤40%. Overlap with R4 (late-fabricated ancestor can also be 'outermost receiver'). Clean R4 is "correct node retained as child with edge inverted"; R3 is "parent-service invented from thin air". Rule (a) + (b) separates.
**analytical_only**: false (but borderline — the "late-emerging" check requires trajectory round-level analysis).

---

## R4 — OutermostReceiverOrInvertedEdge (17 cases, 16.5%)

### Definition
The correct injected service is identified AND placed in the output graph (matched), but the edge direction is reversed. The agent names one of the following as root instead of the matched service:
- the outermost ingress (ts-ui-dashboard, loadgenerator) receiving the observed errors
- the upstream-most caller in a fabricated chain, with the matched service kept as a middle/child node
- a correctly-UNAVAILABLE dead pod kept as child under a fabricated 'root' caller

### Positive examples (canonical)
- **case_551**: consign-service correctly marked UNAVAILABLE in graph; ui-dashboard named root because it is "loadgen-facing". Two-node graph ui→consign with root=ui.
- **case_1886 (rerun)**: inside-payment-service correctly identified and marked UNAVAILABLE; then placed downstream of ui-dashboard in a 7-node sprawl, root=ui.
- **case_1814**: basic-service (injection target) present as HIGH_LATENCY child; travel-service (noisy caller) named root.

### Negative examples (NOT R4)
- **case_247** — route-service (injection) not even in final graph → R1 (silent origin shadowed), not R4.
- **case_2231** — travel-service present as middle, but the root was a **fabricated** basic-service that doesn't match the GT pair → R3.

### Members (17)
case_ids: 156, 315, 551, 741, 755, 1114, 1495, 1814, 1837, 1886, 1948, 2245, 2390, 2585, 3128, 4258, 4510

### Trajectory-only trigger
```
FIRE when ALL of:
  (a) final output's nodes list contains a service flagged UNAVAILABLE or HIGH_ERROR_RATE
      that is NOT the same as root_causes[0].component
  (b) final output's edges list has this UNAVAILABLE service as a `target` of the root
      (edge.source == root AND edge.target == unavailable_candidate), indicating agent placed
      root upstream of the unavailable service
  (c) round_count >= 20 (R4 typically emerges after long trace-chain investigation)

Equivalent strong signal: the final root's `state` is either ['HIGH_ERROR_RATE'] alone
(no UNAVAILABLE) while some other node has ['UNAVAILABLE'].
```
**Self-check FP rate**: ≤35%. Rule (a)+(b) misses R4 cases where the injected service is left as middle node of a longer chain (e.g., 1495). Adding "final graph contains the injection-pair service as a non-root node" would tighten, but per self-check 35% is acceptable.
**analytical_only**: false.

---

## R5 — SimilarNameSiblingConfused (10 cases, 9.7%)

### Definition
The agent names a close-named microservice variant as root when the injected service is a sibling. Canonical name pairs observed in claudecode failures:
- order-service vs ts-order-other-service
- food-service vs ts-station-food-service vs ts-train-food-service
- route-service vs ts-route-plan-service
- payment-service vs ts-inside-payment-service
- consign-service vs ts-consign-price-service
- travel-service vs ts-travel2-service (less frequent; usually R4 inversion)

### Positive examples (canonical)
- **case_1195 (JVMMemoryStress on order-other-service OrderOtherServiceImpl.getOrderById)**: agent picked order-service because it had visible 500 "Order already exists" errors; SLO explicitly on `/orderOtherService/*` route.
- **case_3033**: station-food-service picked; GT was train-food-service on injection route `/trainfoodservice/trainfoods/*`.
- **case_3920**: inside-payment-service picked; GT was payment-service.

### Negative examples (NOT R5)
- **case_4363 (JVMMemoryStress on train-food-service)**: food-service picked. There IS naming adjacency, BUT the primary mechanism is silent callee + noisy caller (food has HIGH_ERROR_RATE, train-food silent) → R1.
- **case_1435 (ContainerKill on train-food)**: food-service has "Connection refused" on its outbound → R1 (dead-pod's silence + caller-promoted), not R5 (train-food naming adjacency is secondary).

### Members (10)
case_ids: 1195, 1875, 1880, 2130, 2647, 3033, 3159, 3920, 4055, 4517

### Trajectory-only trigger
```
FIRE when ALL of:
  (a) final output's root_causes[0].component is similar-named to the SLO endpoint path
      (e.g., root=ts-order-service but SLO path contains `orderOtherService`; or
       root=ts-route-service but prompt mentions `/travelservice/` and agent issues
       queries touching route-plan-service traces)
  (b) agent's Bash SQL history contains queries filtering on the actual-injection-service
      name fewer times than queries filtering on the chosen-root's name

Service-name-similarity proxy (prompt-only):
  - Compute Jaro-Winkler similarity between root_causes[0].component and each service
    mentioned in prompt SLO endpoints. If >0.85 to a service that is NOT the chosen root,
    and that other service appears in final graph nodes list, flag R5.
```
**Self-check FP rate**: ≤30%. Rule (a) is a strong signal. The SLO endpoint naming typically disambiguates.
**analytical_only**: false.

---

## R6 — InfraLayerSkipped_AppLayerAnchored (7 cases, 6.8%)

### Definition
The fault is at the infrastructure layer (mysql bandwidth/latency, network partition/bandwidth/DNS, inter-service bandwidth limit). The agent stops at the first application-layer service showing novel errors in abnormal_logs, names it root, and never issues queries against mysql/network/DNS dimensions. Distinguisher from R3: R6 cases have a correctly-identified app-layer cascade, but the agent fails to descend to infra; R3 cases have the app-layer root itself hallucinated.

### Positive examples (canonical)
- **case_283**: NetworkBandwidth on station-service→mysql. Agent picked consign-service (first app-layer novel-error signal). Dossier round 27: agent queried `metric LIKE '%db%' OR '%mysql%' OR '%connection%'` → 0 rows → concluded "no DB issues" and stayed at app layer.
- **case_1421 (DNSRandom on station→mysql resolution)**: consign-service picked; DNS dimension never probed.
- **case_2678**: NetworkBandwidth on seat→config; agent picked travel2-service (earliest TIMEOUT).

### Negative examples (NOT R6)
- **case_1004**: NetworkDelay on mysql→route-service, but agent anchored on RabbitMQ DNS → R2.
- **case_323**: clock skew (infra-layer fault) and agent picked rabbitmq → R2 dominates.
- **case_4423**: ui-dashboard named root with only ui matched → R4 (outermost receiver).

### F-CANDIDATE ASSESSMENT — T4 → **stays R6 (R class)**, NOT F
Evidence from dossier case_283 (rounds 15-27):
- Round 15: agent issued `SELECT metric, service_name, AVG(value) FROM 'abnormal_metrics.parquet' WHERE metric LIKE '%latency%'` → got rows back (travel2 p99 1.37s, order p99 0.91s, seat p99 0.90s etc).
- Round 27: agent issued `WHERE metric LIKE '%db%' OR '%database%' OR '%mysql%' OR '%connection%'` → 0 rows.
- Claude Code's Bash+DuckDB tool IS capable of querying any parquet column; the 0-row result was because the dataset's metric rows don't use 'mysql'/'connection' naming. Agent could have queried span-duration on mysql-targeted spans, per-span latency by span_name, egress/ingress bytes — but chose not to.

**Decision**: T4 is a reasoning defect (inadequate query formulation / failure to descend query granularity), not an architectural tool-layer limit. The Bash tool can access all parquet files without restriction. **R6 stays in R.**

### Members (7)
case_ids: 283, 339, 1421, 2678, 2715, 3222, 4423

### Trajectory-only trigger
```
FIRE when ALL of:
  (a) SLO endpoint prompt keywords include 'network' / 'mysql' / 'dns' / 'bandwidth' / 'partition' / 'loss' / 'corrupt' / 'delay'
      (derivable from fault_type metadata only during inference — if inference time has only prompt,
       substitute: agent's final root is an app-layer service (matches `ts-*-service`) but NOT mysql / no edge to mysql)
  (b) agent's Bash SQL history contains >=5 queries grouped by service_name but <=2 queries
      targeting mysql-related span names, network-metric keywords, or per-link byte counters
  (c) final root_causes is an app-layer service; `mysql` does not appear as a node anywhere in the output

Equivalent strong signal: count of tool_calls where SQL contains ('mysql' OR 'db_' OR 'bytes_' OR 'network' OR 'dns') < 2
while total SQL tool_calls > 15.
```
**Self-check FP rate**: ≤40%. Most non-R6 claudecode failures also don't query mysql (R2 goes rabbitmq, R1 stays in app layer). Distinguisher is stricter: R6 cases have the agent CORRECTLY anchor on an app-layer cascade but skip infra — this cannot be detected from trajectory alone without knowing GT is infra.
**analytical_only**: **true** — the distinguisher "app-layer anchor was correct" requires GT. Without GT, the trigger conflates with R2/R3/R4.

---

## R7 — JVMSymptomMisreadAsDB (4 cases, 3.9%)

### Definition
JVM memory stress on a Java service produces secondary HikariCP / DB-connection-pool warnings (because the hung JVM threads keep connections open and exhaust the pool). The agent reads these pool warnings as a primary mysql / DB-server fault and places mysql at the graph root. Cases confined to JVMMemoryStress fault type.

### Positive examples (canonical)
- **case_807 (JVMMemoryStress on train-service TrainType constructor)**: final graph mysql→train-service→ui-dashboard, root=mysql. Dossier B.1 confirms.
- **case_1218 (JVMMemoryStress on order-service OrderInfo.enableBoughtDateQuery)**: final graph has mysql UNAVAILABLE at top, seat-service UNAVAILABLE cascade; order-service entirely absent.
- **case_4832 (JVMMemoryStress on consign-service)**: 82-round exploration; mysql named root; consign matched as child.

### Negative examples (NOT R7)
- **case_283**: agent's reasoning mentions mysql but for network-bandwidth dimension; mysql not named root → R6.
- **case_1004**: rabbitmq root, mysql ignored → R2.

### Members (4)
case_ids: 807, 1218, 3035, 4832

### Trajectory-only trigger
```
FIRE when ALL of:
  (a) agent's Bash SQL history contains query results mentioning 'HikariCP' / 'hikari' /
      'connection pool' / 'pool exhaust'
  (b) final output's root_causes[0].component == 'mysql'
  (c) agent's final output's nodes list contains a Java service (ts-*-service) that was
      injected on a JVM-related method per its prompt/SLO context
      (inference-time proxy: fault_category == 'JVMChaos' — but this requires metadata;
       trajectory-only proxy: agent's SQL queried JVM metrics keywords ('jvm_', 'heap_', 'gc_')
       AND found elevated values)

Equivalent strong signal: 'HikariCP' appears in a Bash-result round AND 'mysql' appears in
final root_causes.
```
**Self-check FP rate**: ≤20%. Very specific signature (HikariCP + mysql-root combination). Low overlap with other classes.
**analytical_only**: false.

---

## Deferred / Excluded (1 case)

- **case_4463 (ContainerKill — GT metadata mismatch)**: dataset's injection_name is `ts-food-service-container-kill` but GT label says ts-config-service. Agent correctly picked food-service matching the injection footprint. Per dossier: matched=['food-service'], judge marked failure due to GT mismatch. **Moved to F_candidates.md as dataset_anomaly** — not a reasoning defect.

## Gate-risk & analytical-only summary

| R class | trigger self-check FP | analytical_only |
|---|---|---|
| R1 | ~35% | false |
| R2 | ~20% | false |
| R3 | ~40% | false (borderline) |
| R4 | ~35% | false |
| R5 | ~30% | false |
| R6 | ~40% | **true** (requires GT to disambiguate from R2/R3/R4) |
| R7 | ~20% | false |

Five of seven triggers are usable at inference time without GT. R6 requires either GT or the fault-category metadata (which IS in the prompt for some agents — need merge-step cross-framework check). R3 borderline but acceptable.
