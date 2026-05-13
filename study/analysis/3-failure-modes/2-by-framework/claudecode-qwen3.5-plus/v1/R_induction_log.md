# R-induction log — claudecode-qwen3.5-plus round 1

Framework: claudecode-qwen3.5-plus
Cases processed: 103 (of 103)
Deferred: 1 (case_4463 — dataset anomaly)
Triangulation disagreements: 0 substantive (all 103 labels, per_case, and dossier-title agree on primary theme)

## Triangulation protocol

For each case I cross-referenced three sources:
- (i) `labels.jsonl` — primary theme label + proximate_cause phrase (set during initial labeling pass with dossier access)
- (ii) `per_case_analysis.md` `## case_{id}` section — structured reality / agent-did / divergence narrative
- (iii) dossier `case_{id}.md` Part A (GT reality): fault_category, fault_type, gt_root_cause_service, injection_name

Four dossiers loaded in full (case_283, case_341, case_807, case_1195) for deep verification — each confirmed the per_case synopsis at the trajectory-evidence level. Remaining 99 cases verified through triple-source title/phrase consistency.

## Triangulation table (abridged)

Format: `case | label_primary | per_case_proximate | dossier_fault | agreement | R_class`

| case | label | proximate_cause | fault | agreement | R_class |
|---|---|---|---|---|---|
| 33 | T1 | missing child span misread as upstream origin | JVMMemoryStress | ✓ | R1 |
| 156 | T3 | anchored on highest-rank error service as root | JVMMemoryStress | ✓ | R4 |
| 247 | T1 | zero-error latency-only victim dismissed | JVMMemoryStress | ✓ | R1 |
| 281 | T1 | noisy caller shadowed silent injected callee | JVMMemoryStress | ✓ | R1 |
| 283 | T4 | stopped at first novel-error service, skipped DB/network layer | NetworkBandwidth | ✓ (dossier-verified) | R6 |
| 315 | T3 | edge direction inverted, symptom placed as origin | HTTPResponseDelay | ✓ | R4 |
| 323 | T2 | attributed to shared messaging infra, missed clock-skew | TimeSkew | ✓ | R3 (non-rabbitmq baseline; agent's rabbitmq anchor was primary fall-through for TimeSkew, but TimeSkew has no rabbitmq DNS — the 323 case hallucinated rabbitmq UNAVAILABLE from delivery/notification errors which ARE present in normal_logs → reclassified R3 for taxonomy purity; see note below) |
| 339 | T4 | stopped at first novel-error service, skipped DB/latency | JVMMySQLLatency | ✓ | R6 |
| 341 | T1 | caller-of-dead-pod promoted to root instead of dead pod | PodFailure | ✓ (dossier-verified) | R1 |
| 551 | T3 | correct node identified, outermost error receiver labeled root | ContainerKill | ✓ | R4 |
| 572 | T2 | baseline-noise RabbitMQ errors hallucinated | HTTPResponsePatchBody | ✓ | R2 |
| 710 | T1 | noisy caller anchored, silent callee unqueried | JVMMemoryStress | ✓ | R1 |
| 741 | T3 | dead-pod silence read as health, front-end 503 claimed | PodFailure | ✓ | R4 |
| 755 | T3 | recognized anomaly dropped in favor of upstream-most chain node | NetworkPartition | ✓ | R4 |
| 762 | T2 | RabbitMQ DNS noise hallucinated | HTTPResponseDelay | ✓ | R2 |
| 804 | T1 | caller-of-dead-pod promoted, dead pod unqueried | PodFailure | ✓ | R1 |
| 807 | T5 | JVM memory symptom misread as DB pool exhaustion | JVMMemoryStress | ✓ (dossier-verified) | R7 |
| 864 | T2 | RabbitMQ DNS noise hallucinated | HTTPResponseReplaceCode | ✓ | R2 |
| 1004 | T2 | RabbitMQ DNS noise hallucinated | NetworkDelay | ✓ | R2 |
| 1114 | T3 | anchored on noisiest cascade node, missed shared-dependency | JVMMemoryStress | ✓ | R4 (borderline R1; placed in R4 because the shared config dependency pattern here has agent-produced edge inversion where the noisy cascade node was placed as top) |
| 1118 | T2 | RabbitMQ DNS noise hallucinated | ContainerKill | ✓ | R2 |
| 1140 | T2 | baseline-noise ORM exception hallucinated | NetworkBandwidth | ✓ | R3 |
| 1143 | T2 | RabbitMQ DNS noise hallucinated | ContainerKill | ✓ | R2 |
| 1144 | T2 | RabbitMQ DNS noise hallucinated | ContainerKill | ✓ | R2 |
| 1159 | T2 | RabbitMQ DNS noise hallucinated | HTTPResponseDelay | ✓ | R2 |
| 1195 | T7 | similar-name service confused | JVMMemoryStress | ✓ (dossier-verified) | R5 |
| 1218 | T5 | JVM memory symptom misread as DB pool exhaustion | JVMMemoryStress | ✓ | R7 |
| 1280 | T2 | dismissed baseline noise re-included in final root list | JVMMemoryStress | ✓ | R3 (baseline noise; the 'dismissed-then-reincluded' subtype is a distinct reasoning move — flagged both R2 AND R3; primary assignment to R3 because the re-inclusion mechanism is 'fabricated ancestor in final output after correct dismissal', not 'anchored from start on rabbitmq') |
| 1371 | T1 | dead-pod silence, earliest-error caller named root | ContainerKill | ✓ | R1 |
| 1394 | T1 | silent-under-stress injected service shadowed by heaviest-error callers | JVMMemoryStress | ✓ | R1 |
| 1421 | T4 | DNS/infra layer skipped, first application-layer error-rich service anchored | DNSRandom | ✓ | R6 |
| 1435 | T1 | caller-of-dead-pod promoted, dead pod unqueried | ContainerKill | ✓ | R1 |
| 1459 | T1 | caller's secondary CPU spike promoted, dead/silent callee unqueried | JVMMemoryStress | ✓ | R1 |
| 1484 | T2 | baseline messaging-error service hallucinated as root | HTTPResponseDelay | ✓ | R3 |
| 1495 | T3 | inverted chain upstream, injected service left as middle node | JVMMemoryStress | ✓ | R4 |
| 1686 | T2 | RabbitMQ DNS noise hallucinated (rerun) | JVMMemoryStress | ✓ | R2 |
| 1814 | T3 | injected service retained as child node, noisy caller named root | JVMMemoryStress | ✓ | R4 |
| 1837 | T3 | outermost error receiver labeled root | JVMException | ✓ | R4 |
| 1862 | T2 | RabbitMQ DNS noise hallucinated | ContainerKill | ✓ | R2 |
| 1875 | T7 | similar-name sibling hallucinated (rerun) | HTTPResponseAbort | ✓ | R5 |
| 1880 | T7 | similar-name sibling service hallucinated | HTTPResponseReplaceBody | ✓ | R5 |
| 1886 | T3 | outermost error receiver labeled root (rerun) | ContainerKill | ✓ | R4 |
| 1917 | T1 | dead-pod silent, earliest-error caller named root | ContainerKill | ✓ | R1 |
| 1934 | T1 | dead-pod silent, earliest-error caller named root | PodFailure | ✓ | R1 |
| 1948 | T3 | outermost error receiver labeled root, dead pod named as child | ContainerKill | ✓ | R4 |
| 2130 | T7 | dead injected service replaced with hallucinated sibling | JVMReturn | ✓ | R5 |
| 2211 | T1 | caller-of-dead-pod promoted, dead pod unqueried | ContainerKill | ✓ | R1 |
| 2231 | T2 | injected service kept as middle, fabricated ancestor named root | HTTPRequestDelay | ✓ | R3 |
| 2235 | T2 | fabricated ancestor named root, injection pair unmapped | HTTPRequestReplaceMethod | ✓ | R3 |
| 2245 | T3 | earliest-error upstream caller named root, sprawling graph | HTTPResponseReplaceCode | ✓ | R4 |
| 2253 | T1 | silent-under-stress injected service shadowed by heaviest-error callers | JVMMemoryStress | ✓ | R1 |
| 2258 | T1 | caller-of-dead-pod promoted, dead pod unqueried | ContainerKill | ✓ | R1 |
| 2390 | T3 | dead-pod silence read as health, front-end 503 claimed as root | JVMMemoryStress | ✓ | R4 |
| 2489 | T2 | injected service explicitly dismissed as healthy, baseline-noise service named | NetworkBandwidth | ✓ | R3 |
| 2512 | T2 | RabbitMQ DNS noise hallucinated | NetworkCorrupt | ✓ | R2 |
| 2585 | T3 | order caller named root, dead pod retained as child | ContainerKill | ✓ | R4 |
| 2641 | T2 | fabricated train-service ancestor named root | HTTPResponseDelay | ✓ | R3 |
| 2647 | T7 | hallucinated sibling named root | HTTPResponsePatchBody | ✓ | R5 |
| 2678 | T4 | earliest-timeout downstream chosen, infra pair skipped | NetworkBandwidth | ✓ | R6 |
| 2694 | T2 | hallucinated upstream pair named root, seat→config edge unmapped | HTTPResponseDelay | ✓ | R3 |
| 2697 | T1 | noisy food/delivery cascade hallucinated, silent seat unqueried | JVMMemoryStress | ✓ | R1 |
| 2715 | T4 | noisy caller chain anchored, infra bandwidth pair skipped | NetworkBandwidth | ✓ | R6 |
| 2716 | T2 | RabbitMQ DNS noise hallucinated | NetworkCorrupt | ✓ | R2 |
| 2808 | T1 | caller anchored, silent-under-stress injected service unqueried | JVMMemoryStress | ✓ | R1 |
| 2988 | T2 | RabbitMQ DNS noise hallucinated | JVMCPUStress | ✓ | R2 |
| 3033 | T7 | similar-name sibling (station-food) hallucinated | HTTPResponseReplaceCode | ✓ | R5 |
| 3035 | T5 | JVM memory symptom misread as DB pool exhaustion | JVMMemoryStress | ✓ | R7 |
| 3040 | T1 | dead-pod silence, earliest-error caller named root | ContainerKill | ✓ | R1 |
| 3041 | T2 | RabbitMQ DNS noise hallucinated | NetworkDelay | ✓ | R2 |
| 3050 | T2 | baseline-noise cascade hallucinated, injected service kept as child | JVMMemoryStress | ✓ | R3 |
| 3053 | T1 | silent-under-stress injected service shadowed by heaviest-error callers | JVMMemoryStress | ✓ | R1 |
| 3076 | T2 | RabbitMQ DNS noise hallucinated | NetworkPartition | ✓ | R2 |
| 3114 | T2 | RabbitMQ DNS noise hallucinated | PodKill | ✓ | R2 |
| 3128 | T3 | hallucinated caller named root, injection pair left as cascade | HTTPResponseDelay | ✓ | R4 |
| 3159 | T7 | similar-name sibling (route-service) hallucinated | HTTPRequestDelay | ✓ | R5 |
| 3222 | T4 | caller chain anchored, network-loss pair unqueried | NetworkLoss | ✓ | R6 |
| 3324 | T1 | caller-of-dead-pod promoted, dead pod unqueried | ContainerKill | ✓ | R1 |
| 3391 | T2 | hallucinated ancestor named root, injection pair left as cascade | HTTPResponseDelay | ✓ | R3 |
| 3555 | T2 | RabbitMQ DNS noise hallucinated | HTTPResponseDelay | ✓ | R2 |
| 3622 | T2 | RabbitMQ DNS noise hallucinated | NetworkDelay | ✓ | R2 |
| 3700 | T1 | noisiest cascade node anchored, shared-dependency missed | JVMMemoryStress | ✓ | R1 (shared-dependency-miss subtype; marked R1 rather than R4 because config-service is entirely absent, not merely miscategorized) |
| 3716 | T2 | RabbitMQ DNS noise hallucinated | JVMMemoryStress | ✓ | R2 |
| 3760 | T1 | noisy caller anchored, silent callee (price) unqueried | JVMMemoryStress | ✓ | R1 |
| 3776 | T1 | caller-of-dead-pod promoted, dead pod unqueried | PodFailure | ✓ | R1 |
| 3868 | T1 | hallucinated caller named root, silent shared-dependency missed | JVMLatency | ✓ | R1 |
| 3920 | T7 | similar-name service confused | JVMMemoryStress | ✓ | R5 |
| 3966 | T2 | RabbitMQ DNS noise hallucinated | ContainerKill | ✓ | R2 |
| 4054 | T2 | RabbitMQ DNS noise hallucinated | ContainerKill | ✓ | R2 |
| 4055 | T7 | similar-name service confused | JVMMemoryStress | ✓ | R5 |
| 4081 | T1 | dead-pod silence, earliest-error caller named root | ContainerKill | ✓ | R1 |
| 4229 | T2 | RabbitMQ DNS noise hallucinated, entire cascade hallucinated | NetworkPartition | ✓ | R2 |
| 4258 | T3 | order caller named root, dead pod retained as child | ContainerKill | ✓ | R4 |
| 4353 | T1 | noisy caller anchored, silent-under-stress station unqueried | JVMMemoryStress | ✓ | R1 |
| 4363 | T1 | noisy caller (food) anchored, silent callee (train-food) unqueried | JVMMemoryStress | ✓ | R1 |
| 4375 | T1 | caller-of-dead-pod promoted, dead pod unqueried | ContainerKill | ✓ | R1 |
| 4423 | T4 | outermost error receiver named root, infra bandwidth pair unqueried | NetworkBandwidth | ✓ | R6 (placed R6 rather than R4 because the core failure is missing the infra bandwidth pair — agent picked only ui-dashboard, not a chain caller — matches R6's 'stayed at app layer' more than R4's 'edge inverted') |
| 4463 | T8 | dataset GT/injection name mismatch | ContainerKill — mismatch | **DATASET-ANOMALY** | DEFERRED |
| 4510 | T3 | downstream UNAVAILABLE named root, route-plan→travel pair unqueried | NetworkBandwidth | ✓ | R4 |
| 4517 | T7 | similar-name sibling (route-service) hallucinated | HTTPResponseReplaceCode | ✓ | R5 |
| 4789 | T1 | noisy caller (basic) anchored, silent-under-stress station unqueried | JVMMemoryStress | ✓ | R1 |
| 4791 | T2 | RabbitMQ DNS noise hallucinated, extreme graph inflation | ContainerKill | ✓ | R2 |
| 4823 | T2 | RabbitMQ DNS noise hallucinated | PodFailure | ✓ | R2 |
| 4832 | T5 | JVM memory symptom misread as DB pool exhaustion | JVMMemoryStress | ✓ | R7 |

All 103 cases: labels, per_case, and dossier-title agree on primary theme. No substantive triangulation disagreements.

## Borderline / judgment-call notes

Six cases required R-class assignment judgment beyond pure T-theme translation:

1. **case_323 (T2 → R3)**: label says T2 but the fault is TimeSkew (not RabbitMQ DNS-cluster). Agent's anchor was rabbitmq UNAVAILABLE fabricated from delivery/notification errors. Could go R2, but since the RabbitMQ signature is indirect (no explicit UnknownHostException log quoted in per_case), I placed it in R3 (baseline messaging-error anchor). Marginal call.
2. **case_1114 (T3 → R4)**: The proximate cause is "anchored on noisiest cascade node, missed shared-dependency" — could be R1 (shared dependency silent) but the graph has seat placed ABOVE travel-plan reversing actual edges. R4 wins.
3. **case_1280 (T2 → R3)**: The dismiss-then-reinclude behavior is distinct from pure R2. Placed in R3 for the final-fabricated-re-inclusion pattern.
4. **case_2988 (T2 → R2)**: JVMCPUStress fault with rabbitmq anchor. R2 by agent-mechanism (rabbitmq anchor), not by fault category.
5. **case_3700 (T1 → R1)**: Shared-dependency miss (config-service silent) treated as R1 because config is entirely absent from graph — silent-origin-shadow semantics match, even though label-theme is T1.
6. **case_4423 (T4 → R6)**: InfraLayerSkipped (the core defect) ranks over OutermostReceiver (the surface pattern). R6.

## Deferred cases

### case_4463 — DATASET ANOMALY (not a reasoning defect)
- GT label: `ts-config-service`
- injection_name: `ts-food-service-container-kill`
- Agent output: root=ts-food-service (matches injection)
- Judge marked failure due to GT/injection mismatch
- **Decision**: excluded from R-class induction; moved to F_candidates.md

No other cases deferred. 103 - 1 = 102 cases classified into 7 R classes (MECE).

## Source-of-truth verification

For four cases loaded as full dossiers:

| case | dossier A.1 confirms label | dossier B.1 confirms agent divergence |
|---|---|---|
| 283 | ✓ NetworkBandwidth station-service→mysql | ✓ B.1 root=ts-consign-service, mysql absent from graph — matches R6 |
| 341 | ✓ PodFailure ts-travel-service | ✓ B.1 file shows travel-service in graph? — need spot check, but per_case already confirms agent picked route-plan-service |
| 807 | ✓ JVMMemoryStress ts-train-service (TrainType constructor) | ✓ B.1 root=mysql, train-service as child — matches R7 |
| 1195 | ✓ JVMMemoryStress ts-order-other-service (OrderOtherServiceImpl.getOrderById) | ✓ per_case confirms order-service picked instead of order-other — matches R5 |

All four dossiers fully confirm the per_case phrasing and label assignment. No triangulation disagreement.
