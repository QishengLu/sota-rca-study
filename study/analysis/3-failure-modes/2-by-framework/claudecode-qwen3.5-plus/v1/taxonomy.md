# claudecode-qwen3.5-plus — Failure Taxonomy v1 (FROZEN, rev 2026-04-17)

**Status**: frozen after full labeling + T6 rerun. Unclassified: 0/103 (0%).

**History**:
- 2026-04-16: initial 114-case labeling; 14 cases in T6 (RolloutAborted) were API-throttled mid-trajectory, no final answer.
- 2026-04-17: T6 cases rerun with concurrency=14 on standard DashScope endpoint. **11/14 flipped to correct**; 3 remain failures and were relabeled into their real reasoning theme (T2/T3/T7). T6 theme has 0 entries and is retained only as a historical marker.

## Headline numbers

- **AC@1 = 79.40% (397/500)** — up from 77.20% (before T6 rerun).
- Failure count: 103 (after removing 11 rerun-corrected cases from the v1 label set).

## Distribution (103 labeled failures)

| Theme | Count | Share |
|---|---|---|
| T2 BaselineNoiseAnchored | 37 | 35.9% |
| T1 SilentInjectionShadowed | 28 | 27.2% |
| T3 InvertedCausalEdge | 16 | 15.5% |
| T7 SimilarNameConfusion | 10 | 9.7% |
| T4 InfraLayerSkipped | 7 | 6.8% |
| T5 JVMMisreadAsDB | 4 | 3.9% |
| T8 DatasetMismatch _(dataset artifact)_ | 1 | 1.0% |
| _(T6 RolloutAborted — retired after rerun)_ | 0 | — |
| **Total** | **103** | **100%** |

## T6 Rerun Details (2026-04-17)

The 14 cases originally labeled T6 (API 429 throttling under Coding Plan hourly quota) were rerun on the standard DashScope Anthropic endpoint (`https://dashscope.aliyuncs.com/apps/anthropic`) with concurrency=14. Results:

| Case | Fault | Rerun result | New label |
|---|---|---|---|
| 1498 | NetworkBandwidth | ✓ correct | — |
| 1504 | NetworkDelay | ✓ correct | — |
| 1572 | HTTPResponseAbort | ✓ correct | — |
| 1733 | HTTPResponseReplaceBody | ✓ correct | — |
| 1798 | HTTPResponseReplaceBody | ✓ correct | — |
| 1811 | JVMReturn | ✓ correct | — |
| 1822 | NetworkCorrupt | ✓ correct | — |
| 1882 | HTTPResponseReplaceCode | ✓ correct | — |
| 2011 | HTTPRequestAbort | ✓ correct | — |
| 2419 | NetworkCorrupt | ✓ correct | — |
| 2500 | NetworkPartition | ✓ correct | — |
| **1686** | **JVMMemoryStress** | ✗ wrong | T2 (RabbitMQ DNS hallucinated) |
| **1875** | **HTTPResponseAbort** | ✗ wrong | T7 (station-food similar-name) |
| **1886** | **ContainerKill** | ✗ wrong | T3 (outermost error receiver named root) |

**Interpretation**: 11/14 (78.6%) recovery rate on the T6 rerun — close to the overall per-case baseline, confirming T6 was environmental. The 3 that remained wrong are distributed across three different reasoning themes (T2/T3/T7), all patterns already seen in the main study; no new theme emerged from the rerun.

## By fault category (103 failures)

| fault_category | n | Top theme(s) |
|---|---|---|
| JVMChaos | 35 | T1 (15), T2 (6), T3 (6), T7 (4), T5 (4) |
| NetworkChaos | 18 | T2 (9), T4 (6), T3 (2), T1 (1) |
| HTTPFault | 23 | T2 (13), T7 (6), T3 (2), T1 (2) |
| PodChaos | 27 | T1 (13), T2 (9), T3 (6), T8 (1) |

## Theme definitions

(unchanged from initial frozen version — see git history for full criteria)

### T1 — SilentInjectionShadowed
The injected service emits low/zero observable error output (hangs under memory/delay stress, or emits nothing because the pod is dead); the agent anchors on a noisier neighbor.

### T2 — BaselineNoiseAnchored
The agent hallucinates a root from a log signature that also appears in `normal_logs.parquet` at comparable frequency, or fabricates an upstream ancestor that does not exist in the GT-defined call graph. The canonical sub-signature is `UnknownHostException: ts-rabbitmq`. **Strongest claudecode-specific theme**.

### T3 — InvertedCausalEdge
Correct services are identified (matched in graph_metrics), but the edge direction is reversed and an upstream caller or outermost error receiver is named as root while the injected service sits as a child/cascade node.

### T4 — InfraLayerSkipped
Fault is at mysql/network/DNS infrastructure; agent stops at the first application-layer service showing novel errors and never queries lower-layer spans.

### T5 — JVMMisreadAsDB
JVM memory stress manifests as HikariCP/DB pool warnings; agent interprets these as a mysql/DB-server fault.

### T6 — RolloutAborted _(retired)_
API 429 mid-trajectory. Obsolete after rerun on standard endpoint.

### T7 — SimilarNameConfusion
Agent names a close-named sibling microservice as root (order vs order-other, food vs train-food vs station-food, route vs route-plan, payment vs inside-payment, consign vs consign-price).

### T8 — DatasetMismatch
Dataset GT label does not match the injection spec target service. Agent correctly followed the injection footprint but was marked as failure. Single occurrence (case 4463).

## Observations carried into merge

1. **T2 dominance strengthens**: after rerun, T2 share 35.9% (up from 31.6%). The RabbitMQ-DNS-noise pattern is the most consistent claudecode signature.
2. **T6 is gone**: the rerun confirms T6 was purely environmental. No need to treat this as a separate R class in the cross-framework merge.
3. **Rerun fix was cheap**: $13.78 total cost, 62 min wall clock at concurrency=14 on standard endpoint. Worth doing for any future runs that hit the Coding Plan hourly limit.
4. **Pivot rounds unchanged**: typical pivot/total ≈ 0.2-0.4. Once claudecode anchors on the wrong hypothesis in the first ~15 rounds, subsequent 30-70 rounds entrench rather than correct.

## Deferred to merge step

The cross-framework merge (`analysis/3-failure-modes/merged/`) happens AFTER aiq-qwen3.5-plus and thinkdepthai-claude-sonnet-4.6 independent taxonomies are frozen. Until then, this taxonomy stays in its own silo.
