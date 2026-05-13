# Adversarial failure-mode relabeling task — `thinkdepthai-qwen3.5-plus`

You are acting as an **independent second labeler**. You do NOT have access to any
previous analysis or labels by anyone else. Your goal is to assign each failed
case to exactly one theme from the frozen taxonomy below, based only on:
  (a) the ground-truth side of the dossier (Part A)
  (b) the agent's trajectory side of the dossier (Part B)

Do not open or read any file that isn't explicitly listed in the "Cases to label"
section. In particular, do NOT read `per_case_analysis.md`, `labels.jsonl`,
`labels_aligned.jsonl`, `adversarial_prompt.md` itself after you've ingested it
(don't re-check instructions), or anything under `meta.failure_analysis` in DB —
those contain the first labeler's answers and would contaminate your independence.

---

## Fixed taxonomy for `thinkdepthai-qwen3.5-plus`

(source: `analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/taxonomy.md` — inlined below to lock the rubric in your context. Do NOT open the taxonomy file; the text below is authoritative.)

<<<TAXONOMY
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

TAXONOMY>>>

---

## Output file (save directly to disk — NO copy-paste needed)

You will write one JSON line per case into this exact absolute path:

```
/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/adversarial_labels.jsonl
```

**Save strategy — append incrementally, one line per case, RIGHT AFTER you finish that case.** This way if your context runs out mid-task, the work so far is persisted.

Use the Bash tool after each case:

```
echo '<JSON_LINE>' >> /home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/adversarial_labels.jsonl
```

Where `<JSON_LINE>` is a single-line JSON object (no leading/trailing whitespace, no markdown fencing, must be valid JSON that passes `json.loads`). Use single quotes around the echo payload and escape internal single quotes as needed. A safer pattern if your `reasoning` field has quotes:

```
cat >> /home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/adversarial_labels.jsonl <<'JSONL'
{"dataset_index": 33, "primary": "T3_Noise-Anchor", "pivot_round": 5, "proximate_cause": "anchored on pre-existing RabbitMQ noise", "reasoning": "Part A shows JVMMemoryStress on ts-auth-service; agent's rounds 4-5 fixate on RabbitMQ DNS errors already present in normal-period logs, then reports ts-rabbitmq as root cause."}
JSONL
```

One case = exactly one appended line. Do NOT prettify with multi-line JSON — one line per record.

**Before starting**, run this once to ensure the file exists and is empty (fresh start):
```
mkdir -p $(dirname /home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/adversarial_labels.jsonl) && : > /home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/adversarial_labels.jsonl
```

**After finishing all 105 cases**, verify line count matches with:
```
wc -l /home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/adversarial_labels.jsonl
```
Expected output: exactly `105 /home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/adversarial_labels.jsonl`.

---

## JSON line schema (required fields, all lowercase keys)

- `dataset_index` (int) — from the case list below
- `primary` (str) — EXACT theme name from the taxonomy above, e.g. `T3_Noise-Anchor` for `thinkdepthai-qwen3.5-plus` (not `T3` alone, not `Noise-Anchor` alone)
- `pivot_round` (int or null) — the single round where the agent most clearly diverged from reality
- `proximate_cause` (str, ≤10 words) — short phrase describing the divergence
- `reasoning` (str, 1–2 sentences) — grounded justification citing specific Part A facts AND specific Part B rounds/quotes

---

## Procedure per case

1. **Read** the dossier file (use the `Read` tool on the path given below).
2. Part A (GT reality): note the injection type, target service(s), key anomaly signals (z-scores, missing spans, error log patterns) — what the agent *should* have identified.
3. Part B (agent trajectory): scan rounds in order. Identify the single round where the agent's hypothesis most clearly diverged from Part A reality. This is `pivot_round`.
4. Pick the taxonomy theme whose positive criteria best fit this case's divergence pattern. Respect negative criteria. Do NOT hedge with "unclassified" unless no theme's positive criteria apply.
5. Write one JSON line using the schema above.
6. **Immediately append it to the output file** using Bash `cat >> ... <<'JSONL' ... JSONL`.
7. Move to the next case.

---

## Cases to label (105 total, process in ascending `dataset_index` order)

- dataset_index=33  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_33.md`
- dataset_index=99  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_99.md`
- dataset_index=130  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_130.md`
- dataset_index=156  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_156.md`
- dataset_index=247  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_247.md`
- dataset_index=281  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_281.md`
- dataset_index=283  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_283.md`
- dataset_index=315  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_315.md`
- dataset_index=323  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_323.md`
- dataset_index=339  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_339.md`
- dataset_index=341  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_341.md`
- dataset_index=572  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_572.md`
- dataset_index=579  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_579.md`
- dataset_index=755  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_755.md`
- dataset_index=784  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_784.md`
- dataset_index=804  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_804.md`
- dataset_index=807  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_807.md`
- dataset_index=832  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_832.md`
- dataset_index=860  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_860.md`
- dataset_index=864  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_864.md`
- dataset_index=1114  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1114.md`
- dataset_index=1140  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1140.md`
- dataset_index=1143  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1143.md`
- dataset_index=1195  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1195.md`
- dataset_index=1218  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1218.md`
- dataset_index=1254  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1254.md`
- dataset_index=1371  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1371.md`
- dataset_index=1394  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1394.md`
- dataset_index=1421  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1421.md`
- dataset_index=1435  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1435.md`
- dataset_index=1459  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1459.md`
- dataset_index=1495  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1495.md`
- dataset_index=1515  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1515.md`
- dataset_index=1814  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1814.md`
- dataset_index=1846  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1846.md`
- dataset_index=1880  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1880.md`
- dataset_index=1917  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1917.md`
- dataset_index=1934  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1934.md`
- dataset_index=1948  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_1948.md`
- dataset_index=2092  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2092.md`
- dataset_index=2130  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2130.md`
- dataset_index=2211  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2211.md`
- dataset_index=2231  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2231.md`
- dataset_index=2253  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2253.md`
- dataset_index=2258  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2258.md`
- dataset_index=2285  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2285.md`
- dataset_index=2390  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2390.md`
- dataset_index=2512  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2512.md`
- dataset_index=2598  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2598.md`
- dataset_index=2641  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2641.md`
- dataset_index=2678  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2678.md`
- dataset_index=2682  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2682.md`
- dataset_index=2700  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2700.md`
- dataset_index=2713  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2713.md`
- dataset_index=2715  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2715.md`
- dataset_index=2716  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2716.md`
- dataset_index=2836  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2836.md`
- dataset_index=2988  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_2988.md`
- dataset_index=3059  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3059.md`
- dataset_index=3112  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3112.md`
- dataset_index=3114  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3114.md`
- dataset_index=3120  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3120.md`
- dataset_index=3125  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3125.md`
- dataset_index=3128  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3128.md`
- dataset_index=3138  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3138.md`
- dataset_index=3219  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3219.md`
- dataset_index=3222  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3222.md`
- dataset_index=3278  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3278.md`
- dataset_index=3393  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3393.md`
- dataset_index=3524  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3524.md`
- dataset_index=3552  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3552.md`
- dataset_index=3592  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3592.md`
- dataset_index=3605  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3605.md`
- dataset_index=3622  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3622.md`
- dataset_index=3673  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3673.md`
- dataset_index=3716  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3716.md`
- dataset_index=3760  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3760.md`
- dataset_index=3776  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3776.md`
- dataset_index=3868  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3868.md`
- dataset_index=3878  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3878.md`
- dataset_index=3920  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3920.md`
- dataset_index=3955  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_3955.md`
- dataset_index=4032  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4032.md`
- dataset_index=4055  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4055.md`
- dataset_index=4070  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4070.md`
- dataset_index=4081  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4081.md`
- dataset_index=4151  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4151.md`
- dataset_index=4229  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4229.md`
- dataset_index=4258  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4258.md`
- dataset_index=4309  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4309.md`
- dataset_index=4311  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4311.md`
- dataset_index=4353  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4353.md`
- dataset_index=4363  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4363.md`
- dataset_index=4375  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4375.md`
- dataset_index=4463  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4463.md`
- dataset_index=4510  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4510.md`
- dataset_index=4519  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4519.md`
- dataset_index=4530  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4530.md`
- dataset_index=4617  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4617.md`
- dataset_index=4707  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4707.md`
- dataset_index=4732  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4732.md`
- dataset_index=4758  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4758.md`
- dataset_index=4789  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4789.md`
- dataset_index=4841  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4841.md`
- dataset_index=4893  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_4893.md`

---

**Begin. For each case: Read dossier → decide → append one JSON line to `/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/adversarial_labels.jsonl` → next case. No batched end-of-response output. Use incremental appends so context-exhaustion doesn't lose work.**

When finished, respond with a one-line summary: `Done. Wrote <N> lines to <path>.`
