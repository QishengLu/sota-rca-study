# Failure Taxonomy — thinkdepthai-qwen3.5-plus

Induced from 105 failed cases (out of 500 evaluated). Two orthogonal dimensions:
- **D** (Data challenge): what property of the telemetry makes the fault hard to find. Observable from GT + dossier Part A.
- **R** (Reasoning defect): what error the agent committed. Observable from trajectory alone — drives metacognitive middleware.

Only **R** is actionable at inference time; **D** is for statistical analysis of which challenges cause which errors.

---

## D Dimension — Data-Layer Challenge

### D1: Silent-Kill

**Definition**: The fault kills or restarts the container/process. The injected service *cannot* emit its own failure telemetry — it produces `missing_span` or a dramatic span-count drop, not ERROR-status spans.

**Fault types**: JVMMemoryStress, ContainerKill, PodFailure, PodKill

**Telemetry signature**: Injected service's spans disappear or drop to near-zero. Downstream callers report `Connection refused`, 502, or timeout. No ERROR spans from the injected service itself.

**Count**: 55/105 (52%)

---

### D2: Errorless-Network

**Definition**: The fault degrades the network at infrastructure level. All symptoms manifest as latency elevation, partial packet loss, or silent corruption — NOT as HTTP error codes in application-layer traces.

**Fault types**: NetworkCorrupt, NetworkBandwidth, NetworkDelay, NetworkLoss, NetworkPartition, TimeSkew, DNSRandom

**Telemetry signature**: Elevated p95/avg latency on affected service spans. status_code=Unset or normal. No application-level ERROR logs from the injected path.

**Count**: 24/105 (23%)

---

### D3: Silent-Corruption

**Definition**: The fault replaces or patches HTTP request/response bodies, status codes, methods, or paths — or manipulates JVM method return values. The service remains nominally healthy (no restarts, no error codes); wrong data propagates silently downstream.

**Fault types**: HTTPResponseReplaceBody, HTTPResponsePatchBody, HTTPResponseReplaceCode, HTTPRequestReplaceMethod, HTTPRequestReplacePath, JVMReturn

**Telemetry signature**: Service spans show normal status and latency. Downstream services fail with business-logic errors (wrong data format, assertion failures) rather than infrastructure errors.

**Count**: 11/105 (10%)

---

### D4: Delay-Abort

**Definition**: The fault injects latency or aborts HTTP responses. The injected service is alive and emits spans, but with extreme latency or connection drops. Downstream callers report timeouts.

**Fault types**: HTTPResponseDelay, HTTPRequestDelay, HTTPResponseAbort

**Telemetry signature**: Injected service spans present but with p95/avg duration >> normal. Downstream services report timeout errors (504, client-side timeout). The injected service is NOT silent.

**Count**: 11/105 (10%)

---

### D5: Diluted-Signal

**Definition**: The fault affects a narrow subsystem (a specific DB query type, JVM heap allocation, CPU thread). The anomaly appears only in targeted span types but is diluted when aggregated across all span types for the service.

**Fault types**: JVMMySQLLatency, JVMCPUStress, JVMLatency

**Telemetry signature**: Service-level average latency looks normal; per-span-type breakout reveals one outlier span type with 10-100× elevated latency. Aggregate-level queries miss the signal entirely.

**Count**: 4/105 (4%)

---

## R Dimension — Reasoning Defect

Only **R** is detectable from the agent's trajectory without GT. These categories define what a metacognitive middleware should watch for and intervene on.

### R1: Absence-Inference

**Definition**: Agent interprets the *absence* of error telemetry as positive evidence of health. Fails to distinguish "no errors because healthy" from "no errors because silenced." May explicitly reason "service X shows no errors, so it is healthy" — when X has zero surviving spans.

**Positive criteria**: Agent observes missing/sparse spans from a service AND concludes that service is healthy. The service is actually dead or restarting.

**Negative criteria**: NOT this if the agent simply never queried the service. Must have seen evidence of silence and drawn the wrong conclusion.

**Middleware trigger**: Agent issues a "no errors from X" conclusion while service X has <10% of expected span count OR has `missing_span` flag.

**Cases**: 17 (T1)

| case | fault_type | specific variant |
|---|---|---|
| 807 | JVMMemoryStress | missing telemetry read as health — ts-train-service had 0 error spans because it was restarting |
| 156 | JVMMemoryStress | survivorship bias on visible error spans — ts-order-service spans were missing |
| 804 | PodFailure | 3 surviving "Unset" spans from ts-train-service read as healthy |
| 3138 | ContainerKill | reversed correct hypothesis on silence — had the right answer, then saw "no errors" and flipped |
| 579 | JVMMemoryStress | injected service spans showed no Error status, concluded healthy |
| 1394 | JVMMemoryStress | intermittent health (some 200s during restart cycle) mistaken for full health |
| 1917 | ContainerKill | ts-seat-service had most errors because ts-order-service was silent-dead |

---

### R2: Propagation-Follow

**Definition**: Agent follows error signals FORWARD — to the service that *reports* errors (503, Connection refused, HTTP 500) — rather than BACKWARD to the upstream service that *caused* the error by being unreachable or broken.

**Positive criteria**: Agent identifies a service with "Connection refused" or high error count and blames it as root cause. GT shows this service was calling a dead/injected upstream.

**Negative criteria**: NOT this if the agent never reached the error-reporting service. Must have chosen the messenger over the origin.

**Middleware trigger**: Agent selects a service whose dominant errors are `Connection refused`, 502, or 503 — these are caller-side symptoms, not origin symptoms.

**Cases**: 33 (T2)

| case | fault_type | specific variant |
|---|---|---|
| 247 | JVMMemoryStress | ts-basic-service "Connection refused" blamed; ts-route-service was the dead upstream |
| 2211 | ContainerKill | ts-route-plan-service "Connection refused" blamed; ts-travel-service was the killed container |
| 4375 | ContainerKill | ts-route-plan-service "Connection refused" blamed; ts-travel2-service was killed |
| 832 | JVMReturn | reversed caller-callee causality — blamed missing ts-route-plan-service |
| 4893 | ContainerKill | salience bias — ts-seat-service had traceable 500s, ts-order-service had untraceable 502s |

---

### R3: Spurious-Anchor

**Definition**: Agent fixates on a prominent but causally irrelevant signal — typically a pre-existing error (RabbitMQ DNS, unrelated container restarts, constant SEVERE counts) — and commits to it as root cause without verifying causal connection to the SLO violations.

**Positive criteria**: The anchoring signal is demonstrably NOT caused by the injection (same counts in normal/abnormal periods, or no trace connection to failing endpoints).

**Negative criteria**: NOT this if the anchoring signal is related to the fault but misinterpreted. The signal must be genuinely irrelevant.

**Middleware trigger**: Agent's conclusion service appears in normal-period error counts at comparable rate to abnormal period; no dependency path from conclusion service to the SLO-violating endpoints.

**Cases**: 27 (T3)

| case | fault_type | specific anchor |
|---|---|---|
| 33 | JVMMemoryStress | RabbitMQ DNS "UnknownHostException" (pre-existing in ts-food-service) |
| 2390 | JVMMemoryStress | RabbitMQ DNS "UnknownHostException" (same pattern) |
| 2682 | NetworkDelay | RabbitMQ DNS + ts-order-service "Order already exists" (both pre-existing) |
| 2231 | HTTPRequestDelay | RabbitMQ DNS (normal errors=48, abnormal=45 — identical) |
| 3868 | JVMLatency | ts-ticket-office-service container restarts (unrelated to failing endpoints) |

---

### R4: Magnitude-Bias

**Definition**: Agent equates "biggest number" with "root cause" — selects the candidate with the largest absolute anomaly (latency value, error count, CPU spike, span duration) regardless of causal position in the dependency chain or whether the anomaly correlates with the SLO violations.

**Positive criteria**: Agent explicitly selects a service because it has the highest metric value. GT shows a different service with a smaller but causally upstream anomaly.

**Negative criteria**: NOT this if the agent's error is structural (R2, R6) rather than magnitude-driven. Must show "I picked X because its number was biggest."

**Middleware trigger**: Agent cites absolute-max metric values when selecting root cause, without normalizing against baseline or verifying causal relevance.

**Cases**: 14 (T4)

| case | fault_type | specific variant |
|---|---|---|
| 2130 | JVMReturn | anchored on ts-route-service 106s DB query (single extreme span), missed ts-station-service upstream |
| 3120 | HTTPRequestReplacePath | anchored on ts-basic-service 420s span + 477 CPU load, missed ts-preserve-service path corruption |
| 755 | NetworkPartition | blamed latency aggregator — ts-travel-plan-service aggregated timed-out calls |
| 3114 | PodKill | "Order already exists" errors constructed into business-logic narrative over infrastructure signal |

---

### R5: Tool-Misuse

**Definition**: The agent's SQL query design prevents the actual anomaly from surfacing. Mixed metric units in a single ORDER BY, over-aggregation across span types, or LIMIT truncation buries the signal. The data exists in the parquet files but the query filters it out.

**Positive criteria**: Dossier Part A confirms the anomaly is present in data. Agent issued a query that should have found it but the query structure buried it.

**Negative criteria**: NOT this if the agent simply never queried the relevant data. Must show the query was issued but designed wrong.

**Middleware trigger**: Agent uses `ORDER BY max_value DESC` across heterogeneous metrics, or uses service-level AVG(duration) when the fault affects only specific span types.

**Cases**: 5 (T5)

| case | fault_type | specific variant |
|---|---|---|
| 339 | JVMMySQLLatency | dismissed ts-travel-service DB latency (6888ms) because service-level avg was only 42ms (diluted) |
| 2988 | JVMCPUStress | mixed-metric query returned memory (GB) in all 30 LIMIT slots, buried CPU (fractions) |

---

### R6: Causal-Overreach

**Definition**: Agent traces the dependency chain in the correct general direction but overshoots the injection point — attributing fault to a service that aggregates the symptoms of the true root cause, or following a corrupted data trail past where the corruption was injected.

**Positive criteria**: Agent's conclusion is a downstream *effect* of the true root cause, reachable via the correct dependency path but one or more hops too far.

**Negative criteria**: NOT this if the agent went in the wrong direction (R2). The overreach must be *past* the correct root cause, not toward the wrong service entirely.

**Middleware trigger**: Agent's conclusion service receives calls FROM the GT root cause service — i.e., the conclusion is a downstream consequence of the real fault.

**Cases**: 6 (T6 × 2, T9 × 4)

| case | fault_type | specific variant |
|---|---|---|
| 1880 | HTTPResponseReplaceBody | followed ts-food-service corrupted payload downstream past ts-train-food-service injection |
| 755 | NetworkPartition | blamed ts-travel-plan-service (aggregated timeouts) over ts-seat-service (partitioned) |

---

### R7: Narrative-Confabulation

**Definition**: Agent constructs a coherent but factually wrong causal narrative — either by weaving business-logic patterns (application-level errors) into a story that ignores infrastructure signals, or by reversing the actual cause-effect relationship between two correctly-identified services.

**Positive criteria**: Agent's reasoning produces an internally consistent story that explains the observed errors, but the story is wrong (wrong root cause, wrong mechanism).

**Negative criteria**: NOT this if the agent just picked the wrong service for lack of evidence. Must show a fabricated causal chain that sounds plausible.

**Middleware trigger**: Agent conclusion is supported only by application-layer business errors (wrong status codes, business logic errors) while infrastructure signals (latency, span counts, pod restarts) are present but unused.

**Cases**: 3 (T7 × 2, T8 × 1)

| case | fault_type | specific variant |
|---|---|---|
| 3114 | PodKill | "Order already exists" errors explained as application bug, ignored pod kill signal |
| 2682 | NetworkDelay | wove RabbitMQ + "Order already exists" into false end-to-end business narrative |

---

## D × R Cross-tabulation

|       | R1  | R2  | R3  | R4  | R5  | R6  | R7  | Total |
|-------|-----|-----|-----|-----|-----|-----|-----|-------|
| D1    | 14  | 25  |  7  |  4  |  2  |  1  |  2  |  55   |
| D2    |  2  |  1  | 12  |  7  |  0  |  2  |  0  |  24   |
| D3    |  1  |  4  |  2  |  3  |  0  |  1  |  0  |  11   |
| D4    |  0  |  3  |  4  |  0  |  1  |  2  |  1  |  11   |
| D5    |  0  |  0  |  2  |  0  |  2  |  0  |  0  |   4   |
| **Total** | **17** | **33** | **27** | **14** | **5** | **6** | **3** | **105** |

**Key conditional patterns** (dominant R per D):

| D | Most likely R | % | Interpretation |
|---|--------------|---|----------------|
| D1 (Silent-Kill) | R2 | 45% | Silent service → agent blames downstream messenger |
| D1 (Silent-Kill) | R1 | 25% | Silent service → agent treats silence as health |
| D2 (Errorless-Network) | R3 | 50% | No clear signal → agent anchors on environmental noise |
| D2 (Errorless-Network) | R4 | 29% | No clear signal → agent picks loudest latency |
| D5 (Diluted-Signal) | R5 | 50% | Narrow signal → agent's aggregate query buries it |

**Middleware insight**: R2 and R1 are the dominant failure modes (50/105 = 48%), both driven heavily by D1 (Silent-Kill) faults. A middleware that detects "agent is concluding about a service with missing telemetry" would catch ~40% of all failures.

---

## T-label to R-label mapping

| T label | R label | Theme name |
|---------|---------|-----------|
| T1 | R1 | Silence-as-Health → Absence-Inference |
| T2 | R2 | Blame-the-Messenger → Propagation-Follow |
| T3 | R3 | Noise-Anchor → Spurious-Anchor |
| T4 | R4 | Amplitude-Greed → Magnitude-Bias |
| T5 | R5 | Query-Blindness → Tool-Misuse |
| T6 | R6 | Path-Through → Causal-Overreach |
| T7 | R7 | Business-Logic-Confabulation → Narrative-Confabulation |
| T8 | R7 | Causal-Inversion → Narrative-Confabulation |
| T9 | R6 | Over-Tracing → Causal-Overreach |

---

## Saturation status

- 105/105 cases labeled
- Last 10 cases introduced 0 new T or R categories → **saturated**
- T6 (2 cases) and T8 (1 case) are thin — may merge into R6/R7 with more data
- R6 (6 cases) is heterogeneous (HTTP body vs. latency aggregation) — may split with data from other agents
- D3 and D4 are both size-11 with different R profiles — worth keeping separate

## Open questions for multi-agent extension

1. **R2 boundary with R6**: When agent follows error propagation forward AND overshoots, which is primary? Rule: R2 if agent blamed the *reporter* of errors; R6 if agent blamed a *correct-direction* downstream service.
2. **D3 vs D4 co-occurrence**: Some HTTP faults combine body corruption + delay. Single D label assigned by dominant fault mechanism in the injection spec.
3. **T10 (Call-Direction-Reversal)**: Proposed in analysis but found insufficient distinct cases. Merged into R2. Revisit if more agents show this pattern.
