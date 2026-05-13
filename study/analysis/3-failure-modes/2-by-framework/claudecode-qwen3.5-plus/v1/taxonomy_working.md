# claudecode-qwen3.5-plus — Working Taxonomy (scratchpad)

**Status**: unfrozen. Last updated after batch 2 (40 cases). Moderate churn in T1–T3; T2 sharpened.

## Methodology

- Source: proximate-cause phrases in `per_case_analysis.md`.
- Clustering is by shared causal mechanism, not surface wording.
- Each theme has name, 1-sentence definition, positive criteria, negative criteria, canonical example(s).
- Themes can be split, merged, renamed, retired across batches.

Names are picked fresh per claudecode — no reuse of thinkdepthai R-names. Cross-framework alignment happens only in the separate merge step.

## Running phrase list (batches 1–2, cases 1–40)

| # | case | fault | proximate cause phrase |
|---|---|---|---|
| 1 | 33 | JVMMemoryStress | missing child span misread as upstream origin |
| 2 | 156 | JVMMemoryStress | anchored on highest-rank error service as root |
| 3 | 247 | JVMMemoryStress | zero-error latency-only victim dismissed |
| 4 | 281 | JVMMemoryStress | noisy caller shadowed silent injected callee |
| 5 | 283 | NetworkBandwidth | stopped at first novel-error service, skipped DB/network layer |
| 6 | 315 | HTTPResponseDelay | edge direction inverted, symptom placed as origin |
| 7 | 323 | TimeSkew | attributed to shared messaging infra, missed clock-skew dimension |
| 8 | 339 | JVMMySQLLatency | stopped at first novel-error service, skipped DB/latency dimension |
| 9 | 341 | PodFailure | caller-of-dead-pod promoted to root instead of dead pod |
| 10 | 551 | ContainerKill | correct node identified, outermost error receiver labeled root |
| 11 | 572 | HTTPResponsePatchBody | baseline-noise RabbitMQ errors hallucinated as root infra failure |
| 12 | 710 | JVMMemoryStress | noisy caller anchored, silent callee unqueried |
| 13 | 741 | PodFailure | dead-pod silence read as health, front-end 503 claimed as root |
| 14 | 755 | NetworkPartition | recognized anomaly dropped in favor of upstream-most chain node |
| 15 | 762 | HTTPResponseDelay | RabbitMQ DNS noise hallucinated as root infra failure |
| 16 | 804 | PodFailure | caller-of-dead-pod promoted, dead pod unqueried |
| 17 | 807 | JVMMemoryStress | JVM memory symptom misread as DB pool exhaustion |
| 18 | 864 | HTTPResponseReplaceCode | RabbitMQ DNS noise hallucinated as root infra failure |
| 19 | 1004 | NetworkDelay | RabbitMQ DNS noise hallucinated as root infra failure |
| 20 | 1114 | JVMMemoryStress | anchored on noisiest cascade node, missed shared-dependency |
| 21 | 1118 | ContainerKill | RabbitMQ DNS noise hallucinated as root infra failure |
| 22 | 1140 | NetworkBandwidth | baseline-noise ORM exception hallucinated as root |
| 23 | 1143 | ContainerKill | RabbitMQ DNS noise hallucinated as root infra failure |
| 24 | 1144 | ContainerKill | RabbitMQ DNS noise hallucinated as root infra failure |
| 25 | 1159 | HTTPResponseDelay | RabbitMQ DNS noise hallucinated as root infra failure |
| 26 | 1195 | JVMMemoryStress | similar-name service confused, wrong variant named root |
| 27 | 1218 | JVMMemoryStress | JVM memory symptom misread as DB pool exhaustion |
| 28 | 1280 | JVMMemoryStress | dismissed baseline noise re-included in final root list |
| 29 | 1371 | ContainerKill | dead-pod silence, earliest-error caller named root |
| 30 | 1394 | JVMMemoryStress | silent-under-stress injected service shadowed by heaviest-error callers |
| 31 | 1421 | DNSRandom | DNS/infra layer skipped, first application-layer error-rich service anchored |
| 32 | 1435 | ContainerKill | caller-of-dead-pod promoted, dead pod unqueried |
| 33 | 1459 | JVMMemoryStress | caller's secondary CPU spike promoted, dead/silent callee unqueried |
| 34 | 1484 | HTTPResponseDelay | baseline messaging-error service hallucinated as root |
| 35 | 1495 | JVMMemoryStress | inverted chain upstream, injected service left as middle node |
| 36 | 1498 | NetworkBandwidth | rollout aborted by API rate-limit, no final answer |
| 37 | 1504 | NetworkDelay | rollout aborted by API rate-limit, no final answer |
| 38 | 1572 | HTTPResponseAbort | rollout aborted by API rate-limit, no final answer |
| 39 | 1686 | JVMMemoryStress | rollout aborted by API rate-limit, no final answer |
| 40 | 1733 | HTTPResponseReplaceBody | rollout aborted by API rate-limit, no final answer |

## Tentative themes (batch 2)

### T1 — SilentInjectionShadowed
**Definition**: the injected service produces low/zero observable error output (hangs under memory/delay stress, or emits nothing because the pod is dead); the agent anchors on a noisier neighbor (caller, cascade-downstream, or outermost front-end) and presents it as the root.
**Positive criteria**:
- GT service is missing from agent's final graph OR present as a downstream/bystander node (not root_causes).
- Agent's reasoning cites "X has higher error count / loudest logs" as the rationale for picking X.
- GT fault is memory stress, pod failure, container kill, HTTP delay, or anything that manifests as slowness / absence rather than explicit errors.
**Negative criteria**:
- If agent attributes to a non-existent infra service (rabbitmq) rather than a real neighbor, that's T2, not T1.
- If agent correctly identifies the service but assigns wrong direction in call graph, that's T3.
**Canonical cases**: 33, 247, 281, 341, 710, 741, 804, 1371, 1394, 1435, 1459.
**Approximate share (batches 1–2)**: ~27% (11/40).

### T2 — BaselineNoiseAnchored (renamed from RabbitMQPhantomRoot; scope widened)
**Definition**: agent hallucinates a root cause from a log/trace signature that is present in `normal_logs.parquet` at comparable frequency (baseline noise), rather than from an incident-specific footprint. The canonical signature is "UnknownHostException: ts-rabbitmq" but the theme now also includes baseline ORM exceptions, delivery-service rabbitmq-consumer errors, etc.
**Positive criteria**:
- Agent's `root_causes` or sprawling graph contains a service that is NOT the injected target.
- Agent's trajectory cites a specific error signature that appears in BOTH abnormal and normal logs at similar frequency — OR the agent dismisses it as baseline then re-includes it anyway.
- Agent hallucinates ≥ 2 services in its graph (hallucinated list length ≥ 2).
**Negative criteria**:
- If hallucination count is low (≤ 1) and the main error is reasonable direction-confusion, that's T3.
- If the baseline service dismissed the noise but still picked wrong root elsewhere, it's T1/T3 — not T2.
**Canonical cases**: 323, 572, 762, 864, 1004, 1118, 1143, 1144, 1159, 1140, 1484, 1280 (partial).
**Approximate share**: ~30% (12/40). **Strongest recurring theme, highly claudecode-specific.**
- Sub-pattern 2a (RabbitMQ DNS): 9/12 cases literally cite the UnknownHostException string.
- Sub-pattern 2b (other baseline noise): 1140 (ORM), 1484 (delivery noise), 1280 (dismissed but re-included).

### T3 — InvertedCausalEdge
**Definition**: agent identifies the correct services but constructs a call graph where the direction of dependency is reversed, promoting a downstream-caller or front-end error-receiver to root while the actual injected service sits as a child or cascade node.
**Positive criteria**:
- GT service is present in the agent's graph (matched), but not in `root_causes`.
- Agent's edge list has the GT service as target of an edge whose source is the claimed root.
**Negative criteria**:
- If GT service is absent entirely from the graph, it's T1.
- If the root is a phantom / hallucinated service, it's T2.
**Canonical cases**: 156, 315, 551, 755, 1495.
**Approximate share**: ~12% (5/40).

### T4 — InfraLayerSkipped
**Definition**: the fault is at the mysql/network/DNS infrastructure layer; agent stops at the first application-layer service showing novel errors and never queries DB metrics, network metrics, or lower-layer spans. Combined with T2 in several cases (agent attributes to RabbitMQ after skipping DB).
**Positive criteria**:
- GT contains `mysql`, a network-layer source/target, or a DNS injection target.
- Agent's final graph contains no DB/network/DNS node.
- Agent's trajectory either never queries mysql/network metrics OR cites "no resource exhaustion" to dismiss them.
**Negative criteria**:
- If the agent DOES misread DB metrics (e.g., picks wrong DB pool from JVM-induced warnings), it's T5.
**Canonical cases**: 283, 339, 1421 (DNS).
**Approximate share**: ~7% (3/40).

### T5 — JVMMisreadAsDB
**Definition**: JVM memory stress on an application service manifests as secondary HikariCP/DB pool warnings; agent interprets the DB-client warnings as a mysql/DB-server fault. Specific enough not to collapse into T4.
**Positive criteria**:
- GT is a JVM memory stress on an app service.
- Agent's root is `mysql` and the app service is marked as HIGH_ERROR_RATE downstream of mysql.
**Canonical cases**: 807, 1218.
**Approximate share**: ~5% (2/40).

### T6 — RolloutAborted (new, batch 2)
**Definition**: agent's rollout was terminated mid-trajectory by an API 429 "quota exceeded" throttling response from the LLM provider. No final answer / graph is emitted. This is an **infrastructure failure of the rollout system, not an agent reasoning failure**. Tracked separately so the taxonomy does not misattribute these to cognitive errors.
**Positive criteria**:
- Dossier B.1 contains "API Error: 429 ... throttling ... quota exceeded".
- `graph_metrics not available`.
- total_rounds typically 5-25 (cut short).
**Canonical cases**: 1498, 1504, 1572, 1686, 1733.
**Approximate share**: ~12% (5/40).
**Note**: this is environmental; merge-step should flag these as excluded from reasoning-pattern analysis.

### T7 — SimilarNameConfusion (new, batch 2)
**Definition**: agent confuses two similarly-named but distinct microservices, naming a close-sibling variant as root instead of the injected service.
**Positive criteria**:
- Both the GT service and the claimed-root service have similar names (e.g., `ts-order-other-service` vs `ts-order-service`; `ts-food-service` vs `ts-train-food-service`).
- The claimed-root service has its own baseline-noise errors.
**Canonical cases**: 1195 (order-other confused with order).
**Approximate share**: 2.5% (1/40). Too small to commit; watch in batches 3-4.

## Overlap notes (batches 1–2)

- Several cases live on theme boundaries (c551: T1∨T3; c807/1218: T1∨T5; c755: T1∨T3; c1114: T1; c1140: T1∨T2; c1280: T2∨T3).
- Primary label assignment happens in the final pass, not now.
- T1 still the largest true-reasoning-error cluster if we exclude T6.
- T2 is by far the strongest **claudecode-specific** signature: 12/40 = 30%. Once T6 is excluded, it's 12/35 = 34%.
- T4 (infra-layer-skipped) is small so far but fault distribution matters: the bulk of JVM memory stress cases are in T1; infra-layer cases are mostly T4+T2 combined.

## Change log

| Batch | Cases analyzed | Action |
|---|---|---|
| 1 | 1–20 | Five tentative themes T1–T5. Strongest: T1 (45%), T2 (25%). |
| 2 | 21–40 | Widened T2 (baseline noise beyond RabbitMQ). Added T6 (rollout aborted) + T7 (similar-name confusion). T2 now 30% — dominant signature. |
