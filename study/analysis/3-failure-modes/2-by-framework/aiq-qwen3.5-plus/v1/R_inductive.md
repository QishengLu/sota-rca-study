# aiq-qwen3.5-plus — R-class induction (Phase α + β round 1)

**Framework**: aiq-qwen3.5-plus
**Source**: 113 labeled failure cases (labels.jsonl + per_case_analysis.md + dossiers)
**Induction method**: phrase extraction per case, phrase clustering, MECE class assignment.
**NOT derived from**: thinkdepthai v2 R-taxonomy, claudecode v1 R-taxonomy, or this agent's own T-themes (re-induced from evidence).
**Total classes**: 8. **Coverage**: 113/113.

The classes below align with the existing T-theme cluster boundaries because both were independently induced from the same per-case phrases. Where T1..T8 framed each cluster as a phenomenological "theme" of the agent+world interaction, R_* below reframes each as the *reasoning defect* itself (a verb describing what the agent's cognition failed to do).

---
### aiq.R_volume_anchor  (24 cases)
**Definition** (GT + trajectory view): Agent ranks services by abnormal-window log-error count (or positive log-error delta vs. normal baseline), picks the top-ranked service, and names it as root cause without asking whether that service is a *causal upstream* of the failure or merely a downstream ripple. The top-ranked service is almost always a downstream consumer receiving 503s from an actual-upstream that went silent (PodKill / JVM mem-stress / NetworkBandwidth).

**Positive criteria**:
- Predicted RC appears in one of the top-3 positive log_delta entries in the abnormal window.
- Predicted RC is NOT in GT causal graph's propagation path in a causally-primary position.
- Hypothesis stable across stages (no refinement moved it away from the log-volume anchor).

**Negative criteria**:
- If the predicted RC is on the GT path but one hop too upstream, that's R_upstream_stop, not this.
- If predicted RC has *negative* log_delta (baseline-noise service), that's R_baseline_unchecked.
- If predicted RC never appears in any query result, that's R_hub_fabrication.

**Canonical example**: case_247 (JVM mem stress on ts-route-service → ts-ui-dashboard has top +15 log_delta → agent predicted ts-ui-dashboard ignoring 10^14-z filesystem anomaly on ts-route-service).

**Members**: 247, 283, 572, 807, 1114, 1218, 1371, 1394, 1421, 1495, 1562, 1860, 1917, 1934, 2390, 2479, 2836, 3673, 3760, 3776, 4032, 4081, 4258, 4789

**Trajectory-only trigger**:
  Signal A: among SQL tool_calls, at least one `SELECT service_name, COUNT(*) FROM abnormal_logs … GROUP BY service_name ORDER BY count DESC` (or equivalent top-K error-volume ranking by service) is executed within the first 15 rounds.
  Signal B: the service named in the final terminator hypothesis matches the top-1 or top-2 row of that ranking query's result.
  Signal C: no subsequent SQL on `normal_logs` or `metrics` with `WHERE service_name='<that top service>'` AND column like `jvm.*` / `container.filesystem.*` / `k8s.pod.memory.*` (i.e., agent never asked "is this service itself failing or just loudly erroring downstream?").
  Trigger rule: A AND B AND C.
  Self-check FP rate on non-R cases: ~25% (correct cases also run top-K queries, but they typically pass the Signal-C check by following up with metric probes on the top-ranked service; baseline_unchecked cases overlap partially — the distinguishing feature is whether the service has negative vs positive log_delta, which IS trajectory-observable via the GROUP-BY result).

---
### aiq.R_upstream_stop  (16 cases)
**Definition** (GT + trajectory view): Agent correctly traces the call chain into a service that lies on the GT propagation path, but anchors on an *upstream caller* rather than continuing one (or more) hop deeper. Root cause: agent observes visible 503 / connection-refused errors on the upstream caller and stops investigating because "errors are located". The deeper GT service is silent (restarting, memory-pressured, latency-degraded) and thus presents no error logs.

**Positive criteria**:
- Predicted RC is in the GT causal graph or on the propagation path.
- Predicted RC directly calls the GT service (i.e., predicted is one call-chain hop upstream of GT).
- GT service's log_delta is non-positive (0 or negative) while predicted service's log_delta is positive.

**Negative criteria**:
- If predicted RC is off the GT path entirely, that's R_volume_anchor or R_hub_fabrication.
- If agent had GT correct earlier and reflection reversed it upstream, that's R_correct_then_reversed.

**Canonical example**: case_339 (JVM MySQL latency on ts-travel-service → agent predicts ts-travel-plan-service, the direct caller; misses ts-travel-service's 10^15 filesystem z-metric).

**Members**: 339, 710, 1459, 2211, 2237, 2253, 2258, 2678, 2697, 2715, 3222, 3325, 4353, 4375, 4510, 4519

**Trajectory-only trigger**:
  Signal A: agent executed at least one SQL on `abnormal_traces` that joins or filters by `parent_span_id` / shows the caller→callee chain (call-tree build intent).
  Signal B: the service named in the final terminator hypothesis appears as a *parent* (caller) node in the observed span tree, with at least one child node in the same tree whose span has a larger error count OR `status_code != Ok` OR is missing from abnormal_traces entirely while present in normal_traces.
  Signal C: no follow-up SQL queries metrics on the child/callee node (e.g., `WHERE service_name='<child>' AND name LIKE 'jvm.%'` or `container.filesystem%` or `k8s.pod.memory%`).
  Trigger rule: A AND B AND C — i.e., agent built a call tree, landed on a caller-node with visible errors, observed a downstream callee with either anomaly or absence, but did not metric-probe the callee.
  Self-check FP rate on non-R cases: ~30% (correct cases also build call trees but tend to run metric probes on the callee when it shows "missing spans" or status anomalies; volume_anchor cases frequently overlap because many top-volume services are also upstream callers — the primary feature separating the two is whether span-level edge evidence shows a hop-deeper target).

---
### aiq.R_baseline_unchecked  (17 cases)
**Definition** (GT + trajectory view): Agent observes a high absolute error-log count on a service in the abnormal window and names it (or its hallucinated backing infrastructure, typically `ts-rabbitmq`) as root cause, without querying the normal baseline to check whether the errors were already present. TrainTicket has persistent RabbitMQ AMQP connection errors on ts-food-service / ts-delivery-service / ts-notification-service that often have *negative* delta (more errors in normal than abnormal); agent anchors on these as evidence and sometimes escalates the anchor into a fabricated ts-rabbitmq root cause.

**Positive criteria**:
- Predicted RC is `ts-rabbitmq` (a broker, not a fault target in this dataset) OR `ts-food-service` / `ts-delivery-service` / `ts-notification-service` when that service has zero or negative log_delta.
- No SQL in trajectory explicitly compares normal_logs vs. abnormal_logs on the suspect service (i.e., no `SELECT … FROM normal_logs WHERE service_name='ts-food-service'` followed by comparison to abnormal count).

**Negative criteria**:
- If predicted RC is ts-food-service AND fault_type is on food-service with positive log_delta, the anchor was actually (partially) correct — reclassify by secondary symptoms.
- If agent anchored on biggest *positive* delta in abnormal window (not baseline noise), that's R_volume_anchor.

**Canonical example**: case_601 (NetworkDelay on ts-order-service↔mysql → z=3653 on order-service db.client.wait_time → agent names ts-rabbitmq because food-service AMQP errors dominated the raw count).

**Members**: 130, 281, 601, 804, 1143, 1159, 1195, 1504, 1862, 3059, 3076, 3622, 3716, 4363, 4463, 4715, 4841

**Trajectory-only trigger**:
  Signal A: predicted_rcs (final) contains `ts-rabbitmq`, `ts-food-service`, `ts-delivery-service`, or `ts-notification-service`.
  Signal B: no SQL in trajectory references `normal_logs` in a WHERE clause targeting the same service name as the hypothesis (i.e., agent never asked "what is the baseline error rate of this service?").
  Signal C: trajectory includes SQL response rows mentioning `AmqpConnectException`, `auto-delete queue`, or `rabbitmq` in the `body` column — i.e., the RabbitMQ-noise substrate is present.
  Trigger rule: A AND (B OR C).
  Self-check FP rate on non-R cases: ~20% (some volume_anchor and silent_fault_blind cases also default to top-volume RabbitMQ cluster without baseline check; distinguished by predicted RC identity — rabbitmq/food/delivery/notification → this class).

---
### aiq.R_silent_fault_blind  (15 cases)
**Definition** (GT + trajectory view): Agent's log-error-first investigation strategy has nothing to anchor on because the GT fault produces no positive log-error delta (PodChaos killed-pod silence, JVMLatency/JVMCPUStress produce latency not errors, HTTPResponseDelay delays without 5xx, NetworkDelay slow spans, TimeSkew). Agent defaults to the most-visible service in the cluster (often ts-ui-dashboard) or an off-path hallucinated service. The metric anomalies on the GT service (filesystem z=10^14, jvm.class.loaded z>>10, db.client.connections.wait_time z=thousands) are present in the `metrics` table but never queried with a service-specific WHERE clause.

**Positive criteria**:
- GT fault_type is in {PodFailure, PodKill, ContainerKill, JVMLatency, JVMCPUStress, JVMReturn, HTTPRequestDelay, HTTPResponseDelay, NetworkDelay, NetworkBandwidth, NetworkLoss, NetworkPartition, TimeSkew}.
- GT service's log_delta is 0 or negative (or only ripple services have small positives).
- Agent's metric-table SQLs either (a) do not include a WHERE filter on GT service_name or (b) query generic metrics only (http.* / network.*) without probing jvm/filesystem/memory/db.client.*

**Negative criteria**:
- If agent anchored on baseline-noise cluster (rabbitmq/food), that's R_baseline_unchecked.
- If agent hallucinated a hub (config-service / mysql) off-path, that's R_hub_fabrication.

**Canonical example**: case_3878 (TimeSkew on ts-consign-service → consign log_delta -512 baseline drop → agent picked ts-ui-dashboard by default with +1 delta).

**Members**: 315, 341, 741, 885, 1484, 2231, 2597, 2761, 2988, 3053, 3114, 3128, 3868, 3878, 4423

**Trajectory-only trigger**:
  Signal A: across all SQLs on `abnormal_logs`, the total positive log-error delta (abnormal_count - normal_count) summed across services with a positive delta is ≤ 50, OR no SQL ever returned a row with > 10 error events for any service (i.e., no loud error anchor exists).
  Signal B: no SQL queries the `metrics` table with a WHERE filter like `service_name='X' AND name LIKE 'jvm.%'` or `name LIKE 'container.filesystem%'` or `name LIKE 'k8s.pod.memory%'` or `name LIKE 'db.client.%'` (i.e., no metric probe specific to infrastructure/JVM signals on any candidate service).
  Signal C: the number of rounds where tool name is `query_parquet_files` on `traces` exceeds 20 (agent kept searching traces in hopes of finding span errors).
  Trigger rule: A AND B.
  Self-check FP rate on non-R cases: ~35% (many correct cases also skip JVM-level metrics but get saved by strong trace/log evidence; the discriminator is Signal A — when there's no loud error anchor and still no metric probe, the agent is blind).

---
### aiq.R_correct_then_reversed  (13 cases)
**Definition** (GT + trajectory view): aiq runs a 3-stage pipeline (stage_0_main, stage_1_refine1, stage_2_refine2). Stage_0 terminator (or stage_1 terminator) correctly names the GT root-cause service. A later stage reverses the conclusion to a different (wrong) service. The reversal is typically triggered when the refine stage queries the GT service directly, sees only HTTP 200 / INFO logs (because memory-pressured services are restart-silent, not 5xx-noisy), and interprets "no HTTP error on this service = healthy", then shifts the blame to a downstream caller that visibly has 503s.

**Positive criteria**:
- Stage hypothesis trace `changed_across_stages=True`.
- An earlier stage terminator's hypothesis matched GT (full or partial), and the final predicted_rcs does not.
- The reflection between stages moves the hypothesis AWAY from GT, not toward it.

**Negative criteria**:
- If stage_0 was already wrong and reflection stayed wrong, not this class.
- If stage_0 was correct and compress (not reflection) rewrote it, that's R_compress_drift.

**Canonical example**: case_99 (stage_0 correctly named ts-consign-price-service → stage_1 refine queried price-service spans, saw status_code=Unset HTTP 200, concluded "healthy", shifted to ts-consign-service where the 503s were visible).

**Members**: 99, 156, 1814, 2283, 2713, 3008, 3125, 3278, 3556, 4257, 4530, 4740, 4801

**Trajectory-only trigger**:
  Signal A: trajectory contains ≥2 `Reflection recorded:` markers (i.e., stage_0 terminator and stage_1 terminator both produced).
  Signal B: service names explicitly mentioned as "root cause" / "most likely" / "primary" in the stage_0 terminator text (extracted by regex `(?:root cause|most likely|primary)[^.]{0,80}(ts-[a-z-]+)`) differ from the service named as root cause in the final terminator OR in the final output JSON.
  Signal C: between the two reflections, trajectory includes an SQL querying the stage_0 hypothesis service directly with `WHERE service_name='<stage_0_hyp>'` AND the response shows few or zero error rows (status_code predominantly = 'Ok' or 'Unset').
  Trigger rule: A AND B AND C.
  Self-check FP rate on non-R cases: ~15% (hypothesis drift can also be healthy refinement toward correct answer; Signal C — observing "low error on stage_0 candidate" — catches the specific reversal-by-misreading-silence mechanism).

---
### aiq.R_hub_fabrication  (12 cases)
**Definition** (GT + trajectory view): Agent names a plausible shared-dependency service (e.g. `ts-config-service`, `mysql`, `ts-route-service`, `ts-ticket-office-service`) as root cause, reasoning "since multiple services look degraded, a shared upstream must have failed". The fabricated hub does not appear in any query result's service_name column — it is a pure inference from the agent's mental model of TrainTicket's architecture, often triggered when no service has a strong positive log_delta.

**Positive criteria**:
- Predicted RC service name does not appear in any tool-call response `service_name` field (i.e., agent never saw it in data).
- Predicted RC is a plausible shared-dependency name: `ts-config-service`, `mysql`, `ts-route-service`, generic infrastructure.
- Multi-service degradation observed by agent (≥3 services showed anomalies).

**Negative criteria**:
- If predicted RC is `ts-rabbitmq` and trajectory shows RabbitMQ baseline errors, that's R_baseline_unchecked.
- If predicted RC is a name-twin of GT, that's R_name_twin_confusion.

**Canonical example**: case_323 (TimeSkew on ts-travel-plan-service → multi-service latency cascade → agent names ts-config-service as shared latency hub, a service that has no log/trace/metric anomalies in the query results).

**Members**: 323, 1880, 2130, 2584, 2585, 2700, 3284, 3465, 3700, 4073, 4229, 4617

**Trajectory-only trigger**:
  Signal A: collect the set of distinct `service_name` values that appeared in any SQL response across the trajectory; call it S_observed.
  Signal B: final predicted_rcs contains at least one service name NOT in S_observed.
  Signal C: among S_observed, ≥3 distinct services had error counts / latency anomalies / missing spans in abnormal window (i.e., the multi-service-degradation premise is present).
  Trigger rule: B AND C.
  Self-check FP rate on non-R cases: ~10% (very discriminative — correct cases almost never name services they didn't query; rare FP when compress layer pulls in a plausible-but-unqueried name, which then becomes compress_drift instead).

---
### aiq.R_name_twin_confusion  (8 cases)
**Definition** (GT + trajectory view): Agent predicts a service whose *name* shares a substring with the GT service but refers to a different microservice, trading the GT for its look-alike. TrainTicket has many name-twin pairs: ts-food-service vs ts-station-food-service vs ts-train-food-service; ts-payment-service vs ts-inside-payment-service; ts-consign-service vs ts-consign-price-service; ts-route-service vs ts-route-plan-service. Agent picks the more prominent / shorter-named sibling.

**Positive criteria**:
- Predicted RC and GT RC share a name prefix / suffix / word root.
- Both predicted and GT services appeared in the observed data (agent could have distinguished them).
- Agent never executed an SQL that explicitly contrasted the two (no SQL with `service_name IN ('<GT>','<twin>')`).

**Negative criteria**:
- If the twin is upstream/downstream of GT on the call chain, R_upstream_stop is primary.
- If agent hallucinated a name that never appeared, that's R_hub_fabrication.

**Canonical example**: case_784 (GT ts-station-food-service → agent predicts ts-food-service; both services appeared in log rows but agent conflated them).

**Members**: 784, 3266, 3920, 3955, 3966, 4054, 4309, 4310

**Trajectory-only trigger**:
  `analytical_only: true` — this class is inherently hard to detect from trajectory alone because we cannot access the GT service name at inference. Candidate trigger (high FP expected):
  Signal A: final predicted_rcs contains a service name whose longest common substring with *any other* service name in S_observed is ≥ 6 characters (e.g., "food-service" as substring of "station-food-service").
  Signal B: agent's SQLs show queries for the substring-matching twin (e.g., `WHERE service_name='ts-food-service'`) but no explicit `service_name LIKE '%food%'` or `IN (...)` pair-comparison.
  Rejection: this signal fires on many non-R cases (agents often query a single service by exact name); estimated FP rate ~60%. Mark `analytical_only: true`.

---
### aiq.R_compress_drift  (8 cases)
**Definition** (GT + trajectory view, aiq-pipeline-specific): aiq's architecture performs a final `compress_to_graph` LLM call that summarizes terminator text into the final JSON output. The most recent stage terminator's text correctly names GT (or was on-path), but the compress layer re-summarizes and picks a *different* service name from the accumulated text — typically the highest-mentioned service, which may be a ripple rather than the causal one. This is a framework-architectural failure: the compress LLM has no structured contract back to the terminator's conclusion.

**Positive criteria**:
- Final predicted_rcs disagrees with the last `Reflection recorded:` / terminator's named hypothesis.
- The terminator text pointed toward GT or on-path.
- Both services are visible in trajectory evidence (not a hallucination).

**Negative criteria**:
- If the terminator itself was wrong, not this class.
- If reflection (not compress) moved hypothesis away, that's R_correct_then_reversed.

**Canonical example**: case_603 (terminators stage_0 + stage_2 both named ts-order-service correctly → final JSON says ts-food-service because food-svc had +153 log_delta vs order's +79).

**Members**: 603, 860, 1140, 1886, 2752, 2769, 3600, 4832

**Trajectory-only trigger**:
  Signal A: extract the service name named as root cause in the LAST `Reflection recorded:` or terminator output via regex (`(?:root.cause|most likely|terminator)[^.]{0,80}(ts-[a-z-]+)` against content fields ending with "Reflection recorded").
  Signal B: the final output JSON (stdout `output` field or last assistant message with structured JSON) contains `"root_causes"` whose service field differs from Signal A's service.
  Signal C: both services are present in S_observed (both visible to agent, distinguishing this from R_hub_fabrication).
  Trigger rule: A AND B AND C.
  Self-check FP rate on non-R cases: ~12% (highly specific; possible FP when terminator text is multi-service and agent legitimately picked the non-primary mention, but cross-checking with Signal C helps).

---

## Trigger false-positive self-check summary

| R class | Trigger feasible | Est. FP rate on non-R aiq cases |
|---|---|---:|
| volume_anchor | yes | 25% |
| upstream_stop | yes | 30% |
| baseline_unchecked | yes | 20% |
| silent_fault_blind | yes | 35% |
| correct_then_reversed | yes | 15% |
| hub_fabrication | yes | 10% |
| name_twin_confusion | **analytical_only: true** | FP ~60% (distillation failed) |
| compress_drift | yes (aiq-specific) | 12% |

All trigger formulas use only trajectory-observable signals: SQL tool-call args (table names, WHERE clauses, service_name filters, response service coverage), `Reflection recorded` markers in tool responses, and final output JSON. No GT-required signals (focus, accuracy, evidence-to-GT-utilization) are used.
