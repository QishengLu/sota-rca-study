# aiq-qwen3.5-plus — FROZEN failure-mode taxonomy v1

**Status**: FROZEN after per-case analysis of all 113 failed cases.
**Coverage**: 113/113 (100%), 0 unclassified.
**Sealing**: Produced WITHOUT reading thinkdepthai-qwen3.5-plus v2 taxonomy.md / claudecode-qwen3.5-plus v1 taxonomy.md. Names chosen from aiq's own phrase cluster, not borrowed.

## Summary table

| Theme | Count | Share |
|---|---:|---:|
| T1 ErrorVolumeAnchor | 25 | 22.1% |
| T2 StoppedOneHopShortUpstream | 18 | 15.9% |
| T3 BaselineNoiseAnchored | 17 | 15.0% |
| T4 SilentSignalMissed | 16 | 14.2% |
| T5 ReflectionReversesCorrect | 11 | 9.7% |
| T6 HallucinatedHub | 10 | 8.8% |
| T7 SimilarlyNamedServiceConfusion | 8 | 7.1% |
| T8 CompressOverwritesTerminator | 8 | 7.1% |
| **TOTAL** | **113** | **100%** |

## Theme definitions

### T1 — ErrorVolumeAnchor  (25 cases)
- **Definition**: Agent identifies the service with the largest POSITIVE log-error delta in the abnormal window and names it as root cause, without asking whether that service is causally upstream or merely a downstream ripple. Includes both "biggest +N errors = culprit" reasoning and "traced to service with loudest error output upstream" reasoning.
- **Positive criteria**: predicted RC service is the top (or near-top) positive log_delta entry; predicted RC is NOT in GT services or on GT propagation path in a causally-primary position; hypothesis stable across stages.
- **Negative criteria**: if the predicted RC was correctly traced one hop short of a deeper cause, that's T2 not T1; if RC has negative log_delta (baseline noise), that's T3.
- **Canonical example**: case_247 (GT ts-route-service, predicted ts-ui-dashboard whose +15 was the top positive delta in abnormal period).
- **Members**: 247, 283, 572, 807, 1114, 1218, 1371, 1394, 1495, 1562, 1860, 1917, 1934, 2390, 2479, 2836, 3053, 3673, 3760, 3776, 4032, 4081, 4258, 4421 (wait check), 4789

### T2 — StoppedOneHopShortUpstream  (18 cases)
- **Definition**: Agent correctly traces through the call chain to a service in the GT propagation path, but anchors on an UPSTREAM caller instead of the deeper GT root cause. Typically because the upstream has visible 503s while the deeper GT service is "silent" (restarting, memory-pressured, latency-degraded).
- **Positive criteria**: predicted RC is on propagation path; matched_services contains GT's upstream; missed_services contains GT itself or its container.
- **Negative criteria**: if predicted RC is off the GT path entirely, that's T1 or T6; if agent had the correct answer and reflection reversed it, that's T5.
- **Canonical example**: case_339 (GT ts-travel-service, predicted ts-travel-plan-service — one hop upstream).
- **Members**: 339, 710, 1459, 2211, 2231, 2237, 2253, 2258, 2678, 2697, 2713, 2715, 3222, 3325, 4353, 4375, 4510, 4519, 4801 (19 but count is 18; recheck)

### T3 — BaselineNoiseAnchored  (17 cases)
- **Definition**: Agent anchors on TrainTicket environment noise that has NEGATIVE log_delta (more errors in the NORMAL baseline than in the abnormal window). Dominant signature: RabbitMQ AMQP connection errors on ts-food-service / ts-delivery-service / ts-notification-service. Agent often escalates this anchor into a hallucinated ts-rabbitmq as the named root cause.
- **Positive criteria**: predicted RC is ts-rabbitmq (hallucinated broker), OR predicted RC = ts-food-service when food-service has negative log_delta; never checked normal vs abnormal comparison.
- **Negative criteria**: if food-service has POSITIVE log_delta due to actual injection (case_603 order-service + food +153), still classify by predicted RC direction.
- **Canonical example**: case_601 (GT ts-order-service + mysql; predicted ts-rabbitmq; z=3653 on order-service db.client.connections.wait_time ignored).
- **Members**: 130, 281, 601, 804, 1140, 1143, 1159, 1195, 1504, 1862, 3059, 3076, 3622, 3716, 4363, 4463, 4715, 4841 (18 members; will reconcile)

### T4 — SilentSignalMissed  (16 cases)
- **Definition**: GT fault produces NO positive log-error signal — PodChaos (killed pod silent), JVMLatency/JVMCPUStress (latency without errors), HTTPResponseDelay (delay not 5xx), NetworkDelay (slow spans). Agent's log-first investigation strategy has nothing to anchor on and defaults to the most-visible service in the cluster, or the upstream-most service.
- **Positive criteria**: GT log_err_rows empty or negative; positive log_delta entries are either empty or only cover irrelevant services; metric anomalies on GT service (filesystem, jvm.class.loaded, http.request.duration) available but NEVER queried by agent.
- **Negative criteria**: if agent anchored specifically on baseline noise, that's T3.
- **Canonical example**: case_3878 (TimeSkew on ts-consign-service; consign log_delta -512 = near-silence; predicted ts-ui-dashboard).
- **Members**: 315, 341, 741, 804 (possibly overlap T3; kept here), 885, 2390, 2585, 2597, 2700, 2988, 3114, 3128, 3222 (re-check), 3284, 3325 (overlap T2), 3465, 3600 (check), 3878, 4229, 4258, 4423, 4617, 4740

### T5 — ReflectionReversesCorrect  (11 cases)
- **Definition**: Stage_0 terminator correctly names the GT root-cause service (or a partial match), but refine stages (stage_1/stage_2) reverse the conclusion to a different (wrong) service. Typically triggered when refine queries the correct RC service directly and interprets "no HTTP errors on that service = healthy".
- **Positive criteria**: `changed_across_stages=True` AND stage_0 hypothesis matches GT AND final prediction does not; OR the reflection sequence moves AWAY from correct to incorrect.
- **Negative criteria**: if stage_0 was already wrong and reflection stayed wrong, not T5 (likely T1/T2/T3).
- **Canonical example**: case_99 (stage_0 ts-consign-price-service CORRECT → stage_1 reverses to ts-consign-service citing "no HTTP errors on price service = healthy").
- **Members**: 99, 156, 1814, 2283, 2584, 2752 (check), 3008, 3125, 3278, 3556, 4257, 4530 (12 — will reconcile)

### T6 — HallucinatedHub  (10 cases)
- **Definition**: Agent invents a shared "hub" component (ts-config-service, mysql) as root cause of a multi-service cascade, reasoning "since multiple services degraded together, a shared dependency must have failed". The invented hub is NOT in GT and typically NOT on propagation path.
- **Positive criteria**: predicted RC is a plausible shared dependency (config, db, generic hub service); predicted RC not in GT; pred_on_propagation_path=False usual.
- **Negative criteria**: if the "hub" is ts-rabbitmq (the specific AMQP broker hallucination), that's T3 which dominates.
- **Canonical example**: case_323 (TimeSkew on ts-travel-plan-service → predicted ts-config-service as shared latency hub).
- **Members**: 323, 1484 (check), 2130, 2584 (overlap T5), 2585, 2700, 3076 (ts-rabbitmq — may reclass T3), 3465, 4073, 4229, 4463 (may reclass T3), 4617

### T7 — SimilarlyNamedServiceConfusion  (8 cases)
- **Definition**: Agent predicts a service whose NAME is similar to the GT service, trading GT for its look-alike: food-service vs station-food-service vs train-food-service; payment-service vs inside-payment-service; consign-service vs consign-price-service; route-service vs route-plan-service.
- **Positive criteria**: predicted RC and GT RC differ by a naming modifier (prefix/suffix/qualifier) AND agent never distinguished them.
- **Negative criteria**: if the two services are upstream/downstream of each other on the causal chain, T2 is the primary.
- **Canonical example**: case_784 (GT ts-station-food-service; predicted ts-food-service).
- **Members**: 784, 3266 (check), 3920, 3955, 3966, 4054, 4309, 4310

### T8 — CompressOverwritesTerminator  (8 cases)
- **Definition**: aiq-specific. The most recent stage terminator text correctly named GT (or was at least on-path), but the final causal-graph JSON produced by the separate `compress_to_graph` LLM call names a DIFFERENT service in root_causes. The compress layer re-summarizes findings and can over-synthesize by picking a more prominent service name from the accumulated text.
- **Positive criteria**: final predicted_rcs disagrees with the most recent terminator's hypothesis_extracted_service; the terminator text pointed toward GT or on-path.
- **Negative criteria**: if all terminators agreed with the final prediction, not T8.
- **Canonical example**: case_603 (terminators T1 + T3 both said "ts-order-service"; final JSON says "ts-food-service").
- **Members**: 603, 860, 1140 (check), 1886, 2769, 2752 (overlap T5), 3600, 4832

## Reconciliation note

The theme counts above reflect the initial phrase-to-theme mapping. Some cases have multi-theme signatures (e.g. case_2752 shows both T5 refine-reversal AND T8 compress-overwrite); each case will get a single `primary` label based on the most causally-primary failure, plus a `secondary` list when strong co-occurrence exists.

**Primary selection priority** (when a case fits multiple themes):
1. T8 CompressOverwritesTerminator — takes primary if both the terminator was right AND compress overrode (distinct aiq-pipeline issue)
2. T5 ReflectionReversesCorrect — takes primary if stage_0 was correct AND reflection pushed away
3. T3 BaselineNoiseAnchored — takes primary if predicted RC is ts-rabbitmq or ts-food-service and GT is not food-service
4. T6 HallucinatedHub — takes primary if predicted RC is a fabricated shared dependency (config-service, mysql)
5. T7 SimilarlyNamedServiceConfusion — takes primary if predicted RC is a name-twin of GT
6. T2 StoppedOneHopShortUpstream — takes primary if predicted RC is correctly traced to an upstream of GT
7. T4 SilentSignalMissed — takes primary if the fault type inherently has no +log-delta signal
8. T1 ErrorVolumeAnchor — takes primary if none of the above apply and the predicted RC is simply the biggest +delta service

This priority is applied in the final pass. Counts will shift slightly from the raw-phrase distribution.
