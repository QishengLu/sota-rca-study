# taxonomy_working.md — thinkdepthai-claude-sonnet-4.6

Rolling document. Re-clustered after each 20-case batch. Frozen only when all 51 cases are labeled and unclassified ≤ 5%.

## Status

- **All 51 cases analyzed** in `per_case_analysis.md`.
- Taxonomy re-clustered once (after batch 1, 7 themes). Second re-clustering here (after all 51 cases): **8 themes + 1 dataset-anomaly bucket**.
- Unclassified: **0 / 51** (≤ 5% target met).
- 1 case (4463) is a dataset-labeling anomaly, not a genuine agent error.
- **Ready for freeze** pending user review.

## Themes (stable v1 — 8 themes)

### T1 — SlowestLeafAnchoring (11 cases, 22%)

- **Definition**: traces the SLO violation backward through the call tree and commits to the *leaf* with the largest visible anomaly (slowest span, biggest latency, largest DB-query max) as RC, without checking whether that leaf's slowness is intrinsic vs. propagated from even-further-upstream.
- **Common trigger fault types**: HTTPResponseDelay-at-caller, HTTPRequestDelay-at-caller, JVM* (Stress, Exception, Return, Latency, MemoryStress), TimeSkew. All of these make the injection target's own spans slow in a way indistinguishable from "downstream is slow".
- **Load-bearing reasoning defect**: the agent lacks a protocol to distinguish "service X is slow because its logic is slow" (fault intrinsic to X) from "service X is slow because its downstream is slow" (fault is below X). Both look identical from the trace.
- **Cases (primary)**: 315, 323, 1484, 1495, 2130, 2174, 2183, 2541, 3125, 3284, 3868.
- **Positive criteria**: (a) fault type produces intrinsic slowness at the injected service; (b) agent's final RC is a service downstream of GT on the call tree; (c) agent's narrative centers on that leaf's observable latency signature.
- **Negative criteria** (not T1): the picked RC is (i) off-the-call-tree entirely (T5/T7), (ii) on a sibling of the injected edge rather than a leaf (T3), (iii) selected via cascaded-chronic-noise-amplification (T2).

### T2 — ChronicNoiseAsRC (7 cases, 14%)

- **Definition**: the TrainTicket environment has a permanent misconfiguration — ts-food-service, ts-notification-service, ts-delivery-service all try to reach `ts-rabbitmq` which has no DNS entry. This produces ambient UnknownHostException errors at all times. Whenever any fault perturbs food-service or preserve-service (even on an unrelated dimension), retry cascades amplify this signal, and the agent selects `ts-rabbitmq [UNAVAILABLE]` as RC.
- **Load-bearing reasoning defect**: no concept of baseline vs. changed — every visible anomaly treated as something that happened *now*. Loudness wins regardless of whether the signal is chronic.
- **Cases (primary)**: 1144, 1280, 1862, 2597, 3107, 3112, 4707.
- **Environment-specificity note**: the rabbitmq signature is a TrainTicket artifact. The *reasoning defect* (mistaking chronic-noise for active-fault) is general and should appear in other frameworks under different ambient signals.
- **Positive criteria**: (a) agent's final RC is `ts-rabbitmq` or similar baseline-noise artifact; (b) trajectory shows DNS/connection errors from food/notification/delivery services to ts-rabbitmq; (c) actual GT is NOT rabbitmq.
- **Negative criteria**: cases where rabbitmq IS the actual fault target (none in this dataset) or cases where the rabbitmq signal is a true secondary effect of the real fault.

### T3 — EdgeCallerCalleeConfusion (19 cases, 37%)

- **Definition**: for faults injected at a specific A→B HTTP or network edge (HTTPResponseReplaceBody, HTTPRequestAbort, HTTPResponseDelay on a named route, NetworkBandwidth, NetworkLoss, NetworkPartition, NetworkCorrupt, NetworkDelay, HTTPResponseReplaceCode), the agent correctly localizes the problem to an edge in the call graph but picks the wrong endpoint. Defaults under uncertainty include:
  - Sibling-of-callee (C instead of B, when A calls both B and C).
  - Near-twin sibling (travel-service vs travel2-service; order-service vs order-other-service).
  - A third service entirely, typically downstream of B.
  - Very rarely: A's caller (upstream of A).
- **Load-bearing reasoning defect**: no algorithm for deciding which side of an A→B edge hosts an egress chaos rule. Signals that would help (e.g., "does B fail only when called from A? or from everyone?") are sometimes observed (case 675 explicitly noted this) but not used to pivot the conclusion.
- **Cases (primary)**: 675, 1326, 1880, 2011, 2584, 2616, 2640, 2678, 2715, 2748, 2830, 2836, 3033, 3493, 3555, 3592, 4229, 4423, 4510.
- **Positive criteria**: (a) actual fault is on an A→B edge; (b) agent's final RC is not in {A, B}; (c) agent did investigate the right region of the call graph.
- **Negative criteria**: compromise pairs (T6), completely-off-path picks (T5), chronic-noise picks (T2).

### T4 — RestartWindowInversion (3 cases, 6%)

- **Definition**: when a pod is killed and restarts (PodChaos/ContainerKill, or natural crash), during the ~5–10s restart window its in-flight outgoing calls all fail. Trace shows "A→B edge failing, originating from A". Agent reads "B is unavailable" rather than "A is crashing during its calls". In some cases (471), even after observing A's pod restart directly, a correlated broader-scope signal (MySQL connection aborts caused by A's death) is adopted as RC.
- **Load-bearing reasoning defect**: no cross-check of pod-restart signals (k8s.container.restarts > 0) against timing of failure spikes to attribute which side of a failed call was the source.
- **Cases (primary)**: 471, 1948, 4739.
- **Positive criteria**: (a) GT is PodChaos/ContainerKill; (b) agent's final RC is a service that the killed pod was calling during the restart window, OR a service whose visible failures are downstream effects of the kill.

### T5 — LoudestHotspotNarrative (2 cases, 4%)

- **Definition**: constructs an internally-consistent multi-service causal story centered on the most striking infrastructure-level anomaly (90s GC pause, worker-node CPU storm, MySQL connection floods, off-path service CPU spike) and commits to that hotspot as RC. Distinct from T1/T7 in that the picked RC is off-the-call-tree (an infrastructure service, a background batch, a worker-node shared service) rather than a leaf on the SLO endpoint's call tree.
- **Load-bearing reasoning defect**: infrastructure-level anomaly magnitude preferred over call-graph causality. Uses shared-node / shared-infra as the "bridge" in the narrative.
- **Cases (primary)**: 371, 3554.
- **Edge case**: 315 picks ts-order-service which IS on the call tree (it's a downstream of seat-service which is downstream of travel-plan); the picked RC is not the leaf, but it's also not off-tree. Close call. Assigned to T1 with T5 as secondary.
- **Positive criteria**: (a) picked RC has the most dramatic infrastructure-level anomaly (GC max, CPU spike, etc.); (b) picked RC is NOT on the direct call path from loadgenerator to the SLO-violating endpoint.

### T6 — ExhaustionWithoutCommitment (4 cases, 8%)

- **Definition**: agent oscillates between multiple candidate RCs across many rounds (40+), burns abnormal token budget (2M+), and commits to a compromise *pair* of candidates at the end — typically one per SLO-violating endpoint if the prompt lists two endpoints. Neither of the paired candidates matches GT in the committed cases.
- **Load-bearing reasoning defect**: unable to prioritize among diverse anomaly sources (rabbitmq noise + multiple service hotspots + multiple DB queries + multiple GC spikes). The agent endorses whichever pair of hypotheses it most recently believed.
- **Cases (primary)**: 339, 572, 2682, 2801.
- **Positive criteria**: (a) round count > 40 AND tokens > 2M; (b) final answer is a pair of services, neither matching GT; (c) trajectory shows multiple hypothesis pivots.
- **Observation**: highly correlated with NetworkChaos or compound-fault cases where multiple services show simultaneous anomalies. Round-count / token-count alone are not reliable predictors — T1 cases 2541 (62 rounds) and 3284 (58 rounds) also exceed these thresholds but commit to a single RC, so belong to T1 not T6.

### T7 — DrillToUnrelatedLeaf (2 cases, 4%)

- **Definition**: for fault types without a direct latency/error signature on any call-tree service (ContainerKill on a non-critical-path service, DNSRandom), the agent still executes the drill-to-slowest-leaf reflex and picks a service that appears slow in its own dimension but is causally unrelated to the fault.
- **Relationship to T1**: same cognitive reflex (drill-to-slowest-leaf), but applied where no leaf is actually caused by the injection. T1 is selecting the wrong leaf when there IS one; T7 is fabricating a leaf when there is none.
- **Load-bearing reasoning defect**: no protocol to match the picked RC's state to the fault-type class. If the fault type is "DNS random responses", the RC should have DNS-related symptoms; the agent doesn't enforce this.
- **Cases (primary)**: 1140, 1421.
- **Decision to keep separate from T1**: preserved as a distinct theme because middleware intervention is different — T1 needs "pause before concluding at the leaf, check if the latency is intrinsic"; T7 needs "match fault-type signature to RC symptom class".

### T8 — SilenceMisreadAsPause (2 cases, 4%)

- **Definition**: observes a service whose metrics (CPU time, network I/O, memory) are not changing and infers PROCESS_PAUSED state. In some cases (3236) this is actually correct for the wrong reason; in others (4433) the service is merely idle because its upstream callers are failing, not because it's paused.
- **Load-bearing reasoning defect**: conflates "metric is silent" with "service is paused", without checking whether the silence is upstream-starvation (no-one-is-calling-it) vs. process-pause (it-can't-respond).
- **Cases (primary)**: 3236 (mysql-0 picked; MySQL actually is bandwidth-starved not paused, agent got lucky on the label), 4433 (ts-price-service picked; it's idle because ts-basic-service is broken upstream).
- **Positive criteria**: (a) agent explicitly reasons about frozen CPU time or repeated identical metric values; (b) final RC has PROCESS_PAUSED or UNAVAILABLE state; (c) the "paused" signal was in reality a silence artifact.

## Special bucket: dataset_anomaly (1 case)

- **Case 4463**: datapack `ts-food-service-container-kill` but DB meta `ground_truth.service = ts-config-service`. Agent predicted `ts-food-service`, matching datapack but not DB meta. Marked as dataset_anomaly — not a genuine agent failure.

## Final primary distribution (51 cases)

| theme | count | share | cases |
|---|---|---|---|
| T3 EdgeCallerCalleeConfusion | 19 | 37% | 675, 1326, 1880, 2011, 2584, 2616, 2640, 2678, 2715, 2748, 2830, 2836, 3033, 3493, 3555, 3592, 4229, 4423, 4510 |
| T1 SlowestLeafAnchoring | 11 | 22% | 315, 323, 1484, 1495, 2130, 2174, 2183, 2541, 3125, 3284, 3868 |
| T2 ChronicNoiseAsRC | 7 | 14% | 1144, 1280, 1862, 2597, 3107, 3112, 4707 |
| T6 ExhaustionWithoutCommitment | 4 | 8% | 339, 572, 2682, 2801 |
| T4 RestartWindowInversion | 3 | 6% | 471, 1948, 4739 |
| T5 LoudestHotspotNarrative | 2 | 4% | 371, 3554 |
| T7 DrillToUnrelatedLeaf | 2 | 4% | 1140, 1421 |
| T8 SilenceMisreadAsPause | 2 | 4% | 3236, 4433 |
| dataset_anomaly | 1 | 2% | 4463 |
| **Total** | **51** | **100%** | |

## Secondary-theme tagging (where applicable)

| case | primary | secondary |
|---|---|---|
| 315 | T1 | T5 |
| 339 | T6 | T2 |
| 471 | T4 | T5 |
| 572 | T6 | T2 |
| 1421 | T7 | T1 |
| 1862 | T2 | T4 |
| 2541 | T1 | T6 |
| 2584 | T3 | T6 |
| 2682 | T6 | T3 |
| 2801 | T6 | T3 |
| 3033 | T3 | T2 |
| 3284 | T1 | T6 |
| 3554 | T5 | T6 |
| 4423 | T3 | T6 |
| 4433 | T8 | T6 |
| 4707 | T2 | T3 |

## Freezing criteria check

- [x] All 51 failed cases have been analyzed.
- [x] Each case has a `primary` assignment.
- [x] Unclassified ≤ 5% (0 / 51 = 0%).
- [x] Every theme has at least 2 supporting cases (T5, T7, T8 have 2 each; borderline but distinct).
- [x] Each theme has positive and negative criteria, load-bearing defect stated, at least one canonical case.
- [x] Secondary tagging captures cross-theme overlap without merging.

**Ready to copy → `taxonomy.md`**.

## Observations for cross-framework merge

When unsealing thinkdepthai-qwen's taxonomy at the merge step, compare:
1. Does T1 (SlowestLeafAnchoring) appear in qwen? Hypothesis: yes, this is probably the framework's dominant mode regardless of model.
2. Does T2 (rabbitmq noise) appear in qwen? Hypothesis: yes, because same environment. The question is whether it has the same **share** (~14%). If much lower in qwen, suggests sonnet is MORE susceptible to chronic-noise adoption than qwen.
3. T3 (EdgeCallerCalleeConfusion) — does qwen show the same 37% dominance? If yes, edge-attribution is a framework-universal defect. If no, sonnet uniquely fails on edge attribution (maybe because sonnet's exploration is broader, hitting more neighbors it can't disambiguate).
4. T4 (RestartWindowInversion) — is this specific to sonnet's richer causal reasoning? A simpler model might not *even notice* the restart event and just pick a downstream.
5. T8 (SilenceMisreadAsPause) — does this require sophisticated metric-reading that only sonnet attempts? If qwen never reasons about frozen CPU time at all, T8 would be sonnet-specific.
6. **Model-robust set** = themes whose share is within ±5pp between sonnet and qwen — candidate for cross-model middleware priority.
