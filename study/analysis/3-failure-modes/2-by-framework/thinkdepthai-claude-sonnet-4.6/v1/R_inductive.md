# R_inductive.md — thinkdepthai-claude-sonnet-4.6 (v1)

Inductive R-class catalogue derived from 50 labeled failure cases (1 dataset_anomaly deferred). Each class: definition, load-bearing reasoning defect, member case count, and a **trajectory-only trigger formula** distilled from raw.json inspection.

All triggers use only signals observable from `tool_calls`, `think_tool` arguments, and round count — no `focus`, no `accuracy`, no GT comparisons. Triggers target Sonnet 4.6's ReAct tool-calling loop (`query_parquet_files` + `think_tool` + `list_tables_in_directory` + `get_schema`).

---

## R_EdgeDirectionDefault — 19 cases (38%)

- **Definition**: for faults injected at a specific A→B HTTP or network edge, agent localizes investigation to the correct edge region of the call graph but picks an endpoint that is not in {A, B}. Defaults include sibling-of-callee, near-twin sibling, co-downstream, and sometimes a third peer service entirely.
- **Load-bearing reasoning defect**: no algorithm to decide which side of an A→B edge hosts an egress chaos rule. Signals that would help (caller-selective failure pattern; whether the callee fails only when called from A) are sometimes observed but never used to flip attribution.
- **Member cases**: 675, 1326, 1880, 2011, 2616, 2640, 2678, 2715, 2748, 2830, 2836, 3033, 3125, 3493, 3555, 3592, 4229, 4423, 4510.
- **Trajectory-only trigger**:
  - `>= 2` distinct services mentioned as candidates in the same `think_tool` reflection (candidate set size >= 2)
  - AND the trajectory shows the investigation focused on a specific call-edge region (presence of `WHERE service_name IN (A, B)` or `parent_span_id` joins across 2-3 adjacent services across `>= 3` SQL queries)
  - AND final commit service is NOT the most-queried service in the trajectory (heuristic: committed RC was queried `< 30%` as often as the top-queried service in the edge region)
  - AND no explicit caller-distribution cross-check SQL was issued (no `GROUP BY caller_service` or `parent_service_name` query against the disputed callee)
- **Self-check FP risk**: Moderate. Many legitimate investigations look at a region of 2-3 services. The "did not issue caller-distribution check" signal is the discriminator; false-positive rate estimated ~30%. Keep as trajectory-fireable.

---

## R_DownstreamLeafAnchor — 12 cases (24%)

- **Definition**: for faults where the injection target's own spans look slow in a way indistinguishable from "downstream is slow" (JVM*, HTTPResponseDelay at caller, HTTPRequestDelay at caller, TimeSkew, DNSRandom), the agent traces the SLO violation backward through the call tree and commits to the leaf with the largest visible latency/DB-query max as RC, without protocol to distinguish intrinsic-slowness-at-X from slowness-propagated-through-X.
- **Load-bearing reasoning defect**: the drill-to-slowest-leaf reflex is applied without an intrinsic-vs-propagated disambiguation step. Even when no proper leaf matches the fault class (DNSRandom, ContainerKill on non-critical-path), the reflex still fires on an arbitrary slow leaf.
- **Member cases**: 315, 323, 1140, 1421, 1484, 1495, 2130, 2174, 2183, 2584, 3284, 3868.
- **Trajectory-only trigger**:
  - Trajectory shows `>= 3` SQL queries that drill progressively deeper on the call tree (`parent_span_id` joins with increasing depth, or successive `WHERE service_name = X` filters moving further from the SLO endpoint)
  - AND the committed RC is the service that appears in the deepest-tree-level query (leaf of the explored subtree)
  - AND NO SQL queried the committed RC's *own upstream call pattern* (no query like `SELECT * WHERE parent_service = committed_RC OR child_service = committed_RC` to ask "is this leaf's slowness caused by its own calls being slow, i.e., is the fault below the leaf or at the leaf?")
  - AND NO baseline-vs-abnormal ratio SQL that tests whether committed RC's *intrinsic* operations (non-network) are slow in isolation
- **Self-check FP risk**: Low-to-moderate. Drill-to-leaf is a legitimate strategy when correct; the "no intrinsic-vs-propagated check" is the key discriminator. FP estimated ~25%.

---

## R_ChronicNoiseAsActiveFault — 7 cases (14%)

- **Definition**: TrainTicket environment has a permanent misconfiguration where ts-food-service, ts-notification-service, ts-delivery-service all fail DNS resolution for `ts-rabbitmq` continuously. When any fault perturbs food-service or preserve-service (even on an unrelated dimension), retry cascades amplify this chronic signal. Agent interprets the loudest ambient signal as the active fault.
- **Load-bearing reasoning defect**: no concept of baseline-vs-changed. Every visible anomaly treated as new-and-causal. Loudness wins regardless of whether the signal is chronic or novel.
- **Member cases**: 1144, 1280, 1862, 2597, 3107, 3112, 4707.
- **Trajectory-only trigger**:
  - Trajectory contains `>= 1` SQL hit to `abnormal_logs` filtering on DNS/UnknownHostException/rabbitmq-related keywords
  - AND committed RC name is "rabbitmq" or similar infra-service that is the subject of the DNS errors
  - AND NO symmetric SQL against `normal_logs` for the same error pattern (no baseline comparison)
  - OR baseline comparison IS made but the agent's `think_tool` reflection still concludes the signal is "active" despite observing it in the normal period too
- **Self-check FP risk**: Very low — the lack of `normal_logs` cross-check for the chronic signal is almost diagnostic. FP estimated ~10%.

---

## R_OscillationToCompromisePair — 4 cases (8%)

- **Definition**: agent oscillates between multiple candidate RCs across many rounds (40+), burning abnormal token budget (2M+), and commits to a compromise *pair* of services at the end — typically one per SLO-violating endpoint. Neither paired candidate matches GT.
- **Load-bearing reasoning defect**: unable to prioritize among diverse anomaly sources; endorses whichever pair of hypotheses it most recently believed. The framework architecture (ReAct) could commit earlier but the reasoning layer does not prune hypotheses.
- **Member cases**: 339, 572, 2682, 2801.
- **Trajectory-only trigger**:
  - Round count `>= 40`
  - AND count of distinct service names mentioned in `think_tool` "root cause" claims `>= 6` across the trajectory (hypothesis-candidate set is wide and unstable)
  - AND final output contains `>= 2` services listed as root cause
  - AND hypothesis-candidate set did NOT monotonically narrow (last third of `think_tool` reflections still introduce new candidate services not named in the first third)
- **Self-check FP risk**: Moderate. Round count alone is not discriminative (cases 2541, 3284, 4433 exceed 40 rounds but commit to a single RC and belong to R_DownstreamLeafAnchor). The oscillation-breadth + pair-output conjunction is the key discriminator. FP estimated ~30%.
- **F-candidate check**: Measured hypothesis oscillation by counting distinct ts-X services in RC claims across `think_tool` thoughts. T6 cases: 339→14, 572→14, 2682→8, 2801→9. T1-long cases with similar round counts: 2541→4, 3284→5, 4433→7. The breadth difference (>2x) indicates oscillation is a behavioral choice, not a framework exhaustion artifact — the ReAct loop can commit at 60+ rounds when hypothesis set is narrow (see 2541). **Keeps as R, does not become F1.**

---

## R_NarrativeOverMatchedMagnitude — 3 cases (6%)

- **Definition**: constructs an internally-consistent multi-service causal story centered on the most striking infrastructure-level anomaly (worker-node CPU storm, memory climb, off-path CPU spike) and commits to that hotspot as RC even when a numerically-matching signal on the actual target has been observed. Distinct from DownstreamLeafAnchor because the picked RC is off-the-call-tree (infrastructure / shared-node / background batch).
- **Load-bearing reasoning defect**: infrastructure-level anomaly magnitude and narrative coherence preferred over quantitative fault-magnitude match. Uses shared-node / shared-infra as a "bridge" hypothesis.
- **Member cases**: 371, 2541, 3554.
- **Trajectory-only trigger**:
  - Trajectory contains a `think_tool` reflection that explicitly names a multi-hop narrative ("X causes contention on Y causes slowness at Z"; lexical markers: "contention", "cascade", "narrative", "explains", "bridges")
  - AND the committed RC's service name does NOT appear in the earliest 30% of `query_parquet_files` SQL (i.e., was not a candidate in the initial investigation)
  - AND the trajectory earlier observed a numerically-precise magnitude match on a different service (lexical markers in `think_tool`: "exactly", "matches the injection", specific millisecond or CPU-core number followed by service name that is NOT the committed RC)
- **Self-check FP risk**: High. The "multi-hop narrative" lexical signature is subjective. FP estimated ~45% — **mark as `analytical_only: true`**.

---

## R_RestartWindowDirectionInversion — 3 cases (6%)

- **Definition**: during a pod-kill window, the dying pod's in-flight outgoing calls fail, visible in traces as A→B edge failures originating from A. Agent reads "B is unavailable" rather than "A is crashing during its calls". Also covers case 471 where a correlated broader-scope signal (MySQL connection aborts caused by A's death) is adopted over the narrower sufficient pod-kill cause.
- **Load-bearing reasoning defect**: no cross-check of pod-restart signals (`k8s.container.restarts > 0`) against timing of failure spikes to attribute which side of a failed call was the source.
- **Member cases**: 471, 1948, 4739.
- **Trajectory-only trigger**:
  - Trajectory contains `>= 1` SQL that returned non-zero `k8s.container.restarts` or `max_restarts` field, OR a `think_tool` reflection containing "restart" / "RESTARTED" / "ContainerKill" / "pod was killed"
  - AND the committed RC service is NOT the service with the observed restart signal
  - AND NO SQL issued to check "during the restart window, what were the outgoing calls from the restarted pod?" (no query with `time BETWEEN restart_t0 AND restart_t1` AND `source_service = restarted_service`)
- **Self-check FP risk**: Low. The restart signal being observed-but-not-committed is a tight discriminator. FP estimated ~20%.

---

## R_SilenceMisreadAsPaused — 2 cases (4%)

- **Definition**: agent observes a service whose metrics (CPU time, network I/O) are plateaued or repeated-identical and infers PROCESS_PAUSED state. The silence is actually upstream-starvation (no-one-is-calling-it because its caller is broken) or bandwidth-starvation (it is not receiving requests because of an upstream chaos rule).
- **Load-bearing reasoning defect**: conflates "metric is silent" with "service is paused" without checking whether incoming request rate also dropped (which would indicate upstream-starvation, not process-pause).
- **Member cases**: 3236, 4433.
- **Trajectory-only trigger**:
  - `think_tool` reflection contains lexical markers: "frozen" / "PROCESS_PAUSED" / "plateau" / "not changing" / "idle" applied to container.cpu.time or a container metric
  - AND committed RC state is `PROCESS_PAUSED` or `UNAVAILABLE`
  - AND NO SQL issued to check incoming-request-count for the allegedly-paused service over the incident window (no `COUNT(*) ... WHERE service_name = paused_service_as_callee` to verify it is actually receiving requests and hanging rather than not receiving them)
- **Self-check FP risk**: Low. The lexical-signature + missing-inbound-check conjunction is tight. FP estimated ~15%.

---

## Summary table

| R class | count | share | trigger-fireable | analytical_only |
|---|---|---|---|---|
| R_EdgeDirectionDefault | 19 | 38% | yes | no |
| R_DownstreamLeafAnchor | 12 | 24% | yes | no |
| R_ChronicNoiseAsActiveFault | 7 | 14% | yes | no |
| R_OscillationToCompromisePair | 4 | 8% | yes | no |
| R_NarrativeOverMatchedMagnitude | 3 | 6% | no | **yes** |
| R_RestartWindowDirectionInversion | 3 | 6% | yes | no |
| R_SilenceMisreadAsPaused | 2 | 4% | yes | no |
| **Total** | **50** | **100%** | 6/7 | 1/7 |

Plus 1 DEFERRED dataset_anomaly (case 4463).

---

## MECE check

Each of the 50 classified cases has exactly one R_class. No "other" bucket. Edge-case disambiguations:

- Case 315 was tagged T1/T5 in v1 taxonomy; R-phrase assigns it to R_DownstreamLeafAnchor (T1) because the picked ts-order-service IS on the call-tree (downstream of seat of travel-plan). R_NarrativeOverMatchedMagnitude requires off-call-tree RC.
- Case 2541 (was T1/T6 secondary): the committed ts-seat-service is on the call graph and the defect is the discounting of directly-matching exception evidence in favor of an elaborate memory-growth narrative on a neighbor. Assigned to R_NarrativeOverMatchedMagnitude because the narrative-construction is the load-bearing defect (not drill-to-leaf).
- Case 1140 (was T7): reassigned to R_DownstreamLeafAnchor since T7's "drill to unrelated leaf" is a special case of the same drill-to-slowest-leaf reflex applied where no proper leaf exists.
- Case 1421 (was T7 secondary T1): same reassignment to R_DownstreamLeafAnchor.
- Case 471 (was T4/T5): reassigned to R_RestartWindowDirectionInversion because the primary defect is causal-direction inversion during a restart window; broadening to MySQL is a secondary consequence.
- Cases 3107, 3112, 4707 previously had T3 secondary: primary R_class = R_ChronicNoiseAsActiveFault since the committed RC is rabbitmq (the chronic-noise artifact), not an edge-endpoint.
- Case 3033 previously T3 primary / T2 secondary: kept as R_EdgeDirectionDefault because committed RC is ts-seat-service (a call-graph sibling of food-service's downstream), not rabbitmq.

No case straddles multiple classes in the classified set. MECE verified.
