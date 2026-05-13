# R-class Induction — thinkdepthai-qwen3.5-plus (v1_harp)

Induced **independently** from 105 failed cases in thinkdepthai-qwen3.5-plus (500-eval subset). Three-level triangulation: `labels.jsonl` proximate_cause × `per_case_analysis.md` × dossier Part A. v2's D/R labels explicitly ignored during extraction; cross-check appended at the end.

Pipeline: thinkdepthai is a single-agent ReAct loop with 40–85 effective rounds per case. Tool mix per case is stable: 1× `list_tables_in_directory`, 1× `get_schema`, 4–12× `think_tool`, 38–60× `query_parquet_files`.

## R-class definitions (7 classes, MECE, induced fresh)

### R_A — SilentSourceReadAsHealthy (N=15)

**Definition**: The injected service is silent — it produces `missing_span`, `Unset` trace status, or its log/span volume collapses. The agent **explicitly reasons** that the service is healthy from this absence ("no errors from X → X is working fine", "Unset status → successful", "surviving 200 OKs → healthy", "deployment.available=1 → healthy").

**Distinguishing boundary vs R_B**: The agent *saw* the candidate injected-service silence and drew a health inference. If the agent never queried the silent service at all and just blamed the messenger, that is R_B.

**Distinguishing boundary vs R_G**: R_A is the specific pattern "absence of error = health"; R_G is more general narrative reversal (e.g., "symptom is cause", "pod.phase=2 means Running", "business-logic explains infrastructure").

**Cases (15)**: 156, 341, 579, 804, 807, 1114, 1394, 2700, 3138, 3878, 3920, 4032, 4258, 4309, 4732

---

### R_B — DownstreamMessengerBlamed (N=32)

**Definition**: The agent picks the *downstream caller* that surfaces error logs (Connection refused / 502 / 503 / HTTP 500 / JSON parse errors) instead of the silent upstream service that actually caused those errors. The pattern is to rank by error-count or error-timestamp and choose the loudest/earliest service, without stepping one hop further up the dependency graph.

**Distinguishing boundary vs R_A**: R_B is about choosing the visible reporter; R_A is about explicitly reasoning the silent upstream is healthy. Many cases have both tendencies — R_A is tagged only when the "X is healthy" reasoning is explicit in the trajectory.

**Distinguishing boundary vs R_D**: R_D is magnitude-based selection *regardless of call direction* (biggest absolute number wins). R_B is specifically "wrong direction up the call chain" — the agent follows errors FORWARD instead of BACKWARD.

**Distinguishing boundary vs R_E**: R_E is over-tracing *past* the injection point. R_B is stopping *at* the downstream reporter and not tracing backward.

**Cases (32)**: 99, 247, 281, 784, 1218, 1371, 1435, 1459, 1814, 1917, 1934, 2211, 2253, 2258, 2678, 2836, 3393, 3524, 3592, 3760, 3776, 3955, 4081, 4151, 4311, 4353, 4375, 4510, 4530, 4707, 4758, 4893

---

### R_C — AmbientNoiseAnchor (N=26)

**Definition**: The agent commits to a service whose errors were **present in the normal (pre-fault) window** at comparable rate to the abnormal window. The anchor signal is pre-existing environmental noise (RabbitMQ UnknownHostException, AmqpConnectException queue redeclaration failures, ts-consign-service NonUniqueResultException, ts-ticket-office-service chronic restarts, single-bucket GC pause on peripheral service) that has no causal connection to the SLO-violating endpoints.

**Distinguishing boundary vs R_D**: R_C anchors on *environmentally chronic* signals; R_D anchors on *injection-induced* amplitude spikes that are real but on the wrong service. Rule: if the agent's conclusion service has non-zero normal-period errors with delta ≈ 0, it's R_C.

**Distinguishing boundary vs R_B**: R_C targets orthogonal services (RabbitMQ, ticket-office) that are not on the call chain at all. R_B targets services that ARE on the call chain but on the wrong (downstream) side.

**Cases (26)**: 33, 130, 283, 315, 1143, 1421, 1515, 1948, 2092, 2231, 2285, 2390, 2512, 2682, 2713, 2716, 3059, 3112, 3222, 3622, 3716, 3868, 4070, 4363, 4617, 4841

---

### R_D — AmplitudeGreedWrongService (N=12)

**Definition**: The agent selects root cause by picking the largest absolute-magnitude metric value: highest error count, highest raw latency max, highest CPU load, highest restart count, highest DB connection-pool wait. The candidate service *is* anomalous during the injection, but the anomaly is a downstream symptom or a noisy peripheral service, not the upstream origin.

**Distinguishing boundary vs R_C**: R_D's chosen service has a real injection-caused anomaly; R_C's chosen service has the same noise counts in normal and abnormal windows. Rule: `abnormal_metric_value - normal_metric_value` is large and non-zero for R_D.

**Distinguishing boundary vs R_B**: R_B frames the error as "connection failed, this service is at fault"; R_D frames it as "this number is the biggest, therefore this service". Both can overlap when the biggest-number service is also a downstream caller — we tag R_B when the reasoning is "caller failed to reach upstream" and R_D when the reasoning is "biggest latency/count wins".

**Cases (12)**: 323, 572, 755, 1140, 1495, 2130, 2715, 3120, 3219, 3605, 4055, 4229

---

### R_E — PathOvershootPastInjection (N=6)

**Definition**: The agent traces the call chain in the **correct direction** (upstream from where errors surface) but overshoots the injection point by one or more hops, landing on a downstream leaf that's either unrelated or a secondary consequence. Includes: following corrupted payload past the injection edge to the next service, tracing 502s past the delayed endpoint, fabricating a causal chain past the actual injection boundary, pursuing the highest-latency leaf past the throttled edge.

**Distinguishing boundary vs R_B**: R_E is direction-correct but distance-wrong; R_B is direction-wrong (stopped at the downstream reporter). Rule: R_E's chosen service is a CALLEE of the GT root-cause service; R_B's chosen service is a CALLER.

**Distinguishing boundary vs R_D**: R_E follows structural call-chain reasoning ("deeper is root"); R_D picks purely on amplitude. Overlap: case 3278 (pursued highest-latency leaf past injected service) has both components but is tagged R_E because the chain-following logic dominates.

**Cases (6)**: 1880, 2641, 3128, 3278, 3552, 4789

---

### R_F — QueryDesignBuriesSignal (N=5)

**Definition**: The agent issues a SQL query against the parquet tables whose **structure filters out the injection anomaly**: heterogeneous-unit ORDER BY (memory-bytes burying CPU-fractions), service-level AVG(duration) aggregation diluting narrow-span latency, `status_code='Error'` filter excluding `Unset` injection_affected spans, mis-scoped latency query picking up unrelated services. The data exists in the parquet files, but the query buries it.

**Distinguishing boundary vs R_A/R_B**: R_F is about query-design; R_A/R_B are about interpretation of query results. If the agent had issued a correctly-scoped query it would likely have avoided R_F. If the agent already had the right data and misread it, it's R_A/R_B/R_G.

**Cases (5)**: 339, 1195, 2988, 3125, 4519

---

### R_G — CausalInversionOrFabrication (N=9)

**Definition**: The agent produces a causal narrative that is internally consistent but structurally wrong. Sub-patterns:
(a) **Symptom-as-cause**: the injection's secondary effect (MySQL Aborted connections, "Table doesn't exist" errors on app services, 'Order already exists' retries) is treated as the primary cause.
(b) **Caller-callee reversal**: the caller's missing downstream is interpreted as the downstream being dead rather than the caller's URL being corrupt (JVMReturn case).
(c) **Business-logic confabulation**: application-level errors like "Order already exists" are woven into an end-to-end story that explains everything except the infrastructure truth.
(d) **Enum/phase misread**: pod.phase=2 read as "not running" when it's a normal enum value.
(e) **Narrative-choice diversion**: stopping at the visible injection target while ignoring a deeper GT dependency (e.g., case 4463).

**Distinguishing boundary vs R_A**: R_A is the narrow "absence of error = health" pattern. R_G is the broader class of causal reversals and fabricated chains that go beyond absence-inference.

**Cases (9)**: 832, 860, 864, 1254, 1846, 2598, 3114, 3673, 4463

---

## Distribution

| Class | Count | % of 105 |
|-------|------:|---------:|
| R_B — DownstreamMessengerBlamed          | 32 | 30.5% |
| R_C — AmbientNoiseAnchor                 | 26 | 24.8% |
| R_A — SilentSourceReadAsHealthy          | 15 | 14.3% |
| R_D — AmplitudeGreedWrongService         | 12 | 11.4% |
| R_G — CausalInversionOrFabrication       |  9 |  8.6% |
| R_E — PathOvershootPastInjection         |  6 |  5.7% |
| R_F — QueryDesignBuriesSignal            |  5 |  4.8% |

Three dominant classes (R_B + R_C + R_A) account for **73/105 = 69.5%** of failures.

## Dominance pattern

**R_B + R_A combined = 47/105 (44.8%)** — both are direct consequences of silent-kill faults (JVMMemoryStress, ContainerKill, PodFailure) where the injected service emits no errors and the agent must reason about absence. These two classes are the highest-value middleware targets.

**R_C = 24.8%** — all concentrated on errorless-network faults (NetworkCorrupt/Bandwidth/Delay/Loss/Partition/TimeSkew/DNSRandom) where the injection produces no ERROR logs and the environmental RabbitMQ DNS cluster becomes the default anchor.

## Trajectory-only trigger distillation per class

See `F_candidates.md` for explicit trigger formulas and self-check FP rate estimates.
