# aiq-qwen3.5-plus — working taxonomy (will churn during labeling)

This is the live scratch pad for aiq failure themes. Last refresh: after case batch 1 (21 cases).

## Rules

- **Do NOT consult thinkdepthai-qwen3.5-plus/v2/taxonomy.md or claudecode/v1/taxonomy.md during writing.** Merge happens later (Phase 7.5) after freeze.
- Theme names are picked fresh from aiq phrases. Avoid borrowing R1-R7 / T1-T8 labels from other agents.
- Every ~20 cases, pause to re-cluster accumulated proximate-cause phrases and update themes.
- A theme is retained only if it covers ≥ 3 cases. Merge/split as needed.

## Working themes (after batch 1 — PROVISIONAL)

### A1 — ErrorVolumeHeuristicAnchor
- **Definition**: Agent anchors on the service with the largest POSITIVE log_delta (new errors in abnormal window) as root cause, without checking whether that service is actually causally upstream of the fault or whether the errors are downstream ripples.
- **Positive criteria**: predicted RC service matches the top +log_delta entry; hypothesis stable across stages; no reflection-driven correction.
- **Negative criteria**: if predicted RC has negative log_delta (baseline noise), that's A2 not A1.
- **Canonical example**: case_247 (ts-ui-dashboard +15 top positive → predicted RC)
- **Current members**: 247, 283, 572, 807, 710 — 5 cases
- **aiq nuance**: reflection stages reinforce the initial anchor rather than correcting; compress step often outputs the same service as both stage_0 and stage_1 terminators.

### A2 — BaselineNoiseAnchored
- **Definition**: Agent anchors on a service whose errors are actually HIGHER in the normal baseline (negative log_delta), typically TrainTicket-specific environment noise (RabbitMQ AMQP, food-service cascade). Never checks baseline.
- **Positive criteria**: predicted RC in log_delta with negative or flat value; reflection reinforces; RabbitMQ/ts-food-service/ts-notification-service pattern frequent.
- **Negative criteria**: if predicted RC has positive log_delta, that's A1.
- **Canonical example**: case_130 (ts-food-service -205 log_delta → predicted RC)
- **Current members**: 130, 601, 804 — 3 cases
- **aiq nuance**: A2 frequently co-occurs with HallucinatedHub when the agent escalates from food-svc anchor to "rabbitmq is root" (281, 601, 804, 1159, 3716).

### A3 — ReflectionReversesCorrect
- **Definition**: Stage_0 correctly names the GT root-cause service; refine stages REVERSE the conclusion to a different (wrong) service, typically because querying the correct RC service directly shows no HTTP errors or status_code=Unset, which reflect interprets as "healthy".
- **Positive criteria**: `changed_across_stages=True` AND stage_0 hypothesis matches GT AND final prediction does not.
- **Negative criteria**: if stage_0 was already wrong, not A3.
- **Canonical example**: case_99 (stage_0 ts-consign-price-service correct → stage_1 reverses to ts-consign-service based on "no HTTP errors on price service = healthy")
- **Current members**: 99, 156 — 2 cases (watching; may merge with A4 after more data)
- **aiq nuance**: CORE aiq-specific failure pattern — the reflect node was designed to strengthen not overturn, but it actively overturns correct conclusions when the GT service's fault signature is silence (JVM stress → restart → no HTTP errors).

### A4 — MissingSignalIgnored
- **Definition**: GT fault produces "silence" rather than error count (PodFailure → missing spans; JVMLatency → latency without errors; HTTPResponseDelay → latency not 5xx). Agent has no positive log anchor and defaults to the service with the most visible error activity or uppermost service in chain.
- **Positive criteria**: GT log_err_rows empty or negative; GT metric anomaly list has strong z-scores on fault-appropriate metrics (filesystem, memory, latency) that agent never queried; predicted RC has positive log_delta on a service the agent saw errors for.
- **Negative criteria**: if GT service DID have positive log_delta and agent ignored it anyway, that's A1.
- **Canonical example**: case_741 (PodFailure → no logs → agent defaults to ts-ui-dashboard upstream; z=93 memory on GT ts-route-service never queried)
- **Current members**: 341, 741, 804, 885, 315 — 5 cases
- **aiq nuance**: pod_restarts / container.filesystem.usage z-scores available but agent's SQL in every stage is log- or trace-oriented; metric parquet barely touched.

### A5 — StoppedOneHopShort
- **Definition**: Agent correctly traces through the propagation chain and identifies A service in the chain, but stops at a service one (or more) layers UPSTREAM from GT RC, typically because that upstream has visible errors (503/timeout) while the deeper GT service is silent (restarting/missing-span).
- **Positive criteria**: predicted RC on propagation path; matched_services contains GT's upstream; missed_services contains GT itself or its container.
- **Negative criteria**: if predicted RC is completely off-path, that's A1/A2/A6.
- **Canonical example**: case_339 (GT ts-travel-service → predicted ts-travel-plan-service, one hop upstream)
- **Current members**: 339, 710 — 2 cases (watching)
- **aiq nuance**: JVM/Pod faults produce service-is-down pattern; upstream callers get 503s that are easier to anchor on than the silent downstream.

### A6 — HallucinatedHub
- **Definition**: Agent invents a shared "hub" service (config-service, rabbitmq) as root cause of a multi-service cascade, reasoning "since multiple services show latency/errors, a shared dependency must have failed".
- **Positive criteria**: predicted RC is a plausible shared dependency (config, db, broker) that is NOT in GT; propagation_path inclusion typically false.
- **Negative criteria**: if the "hub" is on the actual propagation path, not A6.
- **Canonical example**: case_323 (TimeSkew on ts-travel-plan-service → predicted ts-config-service as hub)
- **Current members**: 323, 601, 804, 281 — 4 cases
- **aiq nuance**: rabbitmq hallucinations are dominant (3 of 4 hub cases target rabbitmq); tight overlap with A2 baseline noise.

### A7 — CompressOverwritesRefine
- **Definition**: Terminator text of stage_1 or stage_2 correctly named GT service (or at least an on-path service), but the compress_to_graph step synthesized a DIFFERENT service into the final `root_causes` JSON.
- **Positive criteria**: most recent terminator hypothesis disagrees with final predicted_rcs; compress appears to have extracted the wrong service from findings.
- **Negative criteria**: if all terminators agreed with final prediction, not A7.
- **Canonical example**: case_603 (stage_0 + stage_2 terminators said ts-order-service → final JSON says ts-food-service)
- **Current members**: 603, 860 — 2 cases (watching — aiq-unique pattern)
- **aiq nuance**: This CANNOT exist in thinkdepthai (no separate compress node). Strictly pipeline-architecture-induced failure.

### A8 — ReflectionEscalatesToInfra
- **Definition**: Stage_0 anchored on an application-layer service with visible errors; refine stage PUSHES blame further down to an infrastructure component (broker, db, k8s), reasoning "if the service has connection errors, the infra must be failing".
- **Positive criteria**: `changed_across_stages=True` AND hypothesis migrates from application service → infrastructure component (rabbitmq, mysql).
- **Negative criteria**: if reflection stayed at service level, not A8.
- **Canonical example**: case_281 (stage_0 ts-food-service → stage_1+2 ts-rabbitmq with hallucinated DNS_ERROR state)
- **Current members**: 281 — 1 case so far (watching; need ≥3 to retain)

### A9 — NameConfusion  (maybe drop)
- **Definition**: Agent predicts a service with a similar name to GT (ts-food-service vs ts-station-food-service).
- **Current members**: 784 — 1 case (drop if doesn't grow)

## Current count summary
- A1 ErrorVolumeHeuristicAnchor: 5
- A2 BaselineNoiseAnchored: 3
- A3 ReflectionReversesCorrect: 2
- A4 MissingSignalIgnored: 5
- A5 StoppedOneHopShort: 2
- A6 HallucinatedHub: 4
- A7 CompressOverwritesRefine: 2
- A8 ReflectionEscalatesToInfra: 1
- A9 NameConfusion: 1

Many cases are currently under-covered (A3, A5, A7, A8, A9 all have <3 members). Expect consolidation after batch 2.

---

## Rolling phrase list (scratch)

| case | proximate_cause_phrase | candidate theme |
|---|---|---|
| 99 | reflection reversed correct conclusion | A3 |
| 130 | anchored on pre-existing RabbitMQ noise | A2 |
| 156 | reflection reversed correct conclusion | A3 |
| 247 | stopped at loudest upstream error volume | A1 |
| 281 | reflection escalated to hallucinated broker | A8 + A2 |
| 283 | largest error delta taken as cause | A1 |
| 315 | latency fault missed by error-count search | A4 |
| 323 | hub hallucinated for shared latency | A6 |
| 339 | stopped one hop short upstream | A5 |
| 341 | missing-span signal ignored | A4 |
| 572 | largest error delta taken as cause | A1 |
| 601 | anchored on pre-existing RabbitMQ noise | A2 + A6 |
| 603 | compress overwrote correct terminator hypothesis | A7 |
| 710 | stopped one hop short upstream | A5 (or A1 variant) |
| 741 | missing-span signal ignored | A4 |
| 784 | confused similarly-named service | A9 |
| 804 | anchored on pre-existing RabbitMQ noise | A2 + A6 |
| 807 | stopped at loudest upstream error volume | A1 |
| 860 | compress overwrote correct refine hypothesis | A7 |
| 885 | latency fault missed by error-count search | A4 |
