# Adversarial failure-mode relabeling task — `claudecode-qwen3.5-plus`

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

## Fixed taxonomy for `claudecode-qwen3.5-plus`

(source: `analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/taxonomy.md` — inlined below to lock the rubric in your context. Do NOT open the taxonomy file; the text below is authoritative.)

<<<TAXONOMY
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

TAXONOMY>>>

---

## Output file (save directly to disk — NO copy-paste needed)

You will write one JSON line per case into this exact absolute path:

```
/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/adversarial_labels.jsonl
```

**Save strategy — append incrementally, one line per case, RIGHT AFTER you finish that case.** This way if your context runs out mid-task, the work so far is persisted.

Use the Bash tool after each case:

```
echo '<JSON_LINE>' >> /home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/adversarial_labels.jsonl
```

Where `<JSON_LINE>` is a single-line JSON object (no leading/trailing whitespace, no markdown fencing, must be valid JSON that passes `json.loads`). Use single quotes around the echo payload and escape internal single quotes as needed. A safer pattern if your `reasoning` field has quotes:

```
cat >> /home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/adversarial_labels.jsonl <<'JSONL'
{"dataset_index": 33, "primary": "T3_Noise-Anchor", "pivot_round": 5, "proximate_cause": "anchored on pre-existing RabbitMQ noise", "reasoning": "Part A shows JVMMemoryStress on ts-auth-service; agent's rounds 4-5 fixate on RabbitMQ DNS errors already present in normal-period logs, then reports ts-rabbitmq as root cause."}
JSONL
```

One case = exactly one appended line. Do NOT prettify with multi-line JSON — one line per record.

**Before starting**, run this once to ensure the file exists and is empty (fresh start):
```
mkdir -p $(dirname /home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/adversarial_labels.jsonl) && : > /home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/adversarial_labels.jsonl
```

**After finishing all 103 cases**, verify line count matches with:
```
wc -l /home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/adversarial_labels.jsonl
```
Expected output: exactly `103 /home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/adversarial_labels.jsonl`.

---

## JSON line schema (required fields, all lowercase keys)

- `dataset_index` (int) — from the case list below
- `primary` (str) — EXACT theme name from the taxonomy above, e.g. `T3_Noise-Anchor` for `claudecode-qwen3.5-plus` (not `T3` alone, not `Noise-Anchor` alone)
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

## Cases to label (103 total, process in ascending `dataset_index` order)

- dataset_index=33  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_33.md`
- dataset_index=156  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_156.md`
- dataset_index=247  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_247.md`
- dataset_index=281  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_281.md`
- dataset_index=283  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_283.md`
- dataset_index=315  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_315.md`
- dataset_index=323  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_323.md`
- dataset_index=339  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_339.md`
- dataset_index=341  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_341.md`
- dataset_index=551  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_551.md`
- dataset_index=572  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_572.md`
- dataset_index=710  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_710.md`
- dataset_index=741  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_741.md`
- dataset_index=755  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_755.md`
- dataset_index=762  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_762.md`
- dataset_index=804  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_804.md`
- dataset_index=807  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_807.md`
- dataset_index=864  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_864.md`
- dataset_index=1004  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1004.md`
- dataset_index=1114  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1114.md`
- dataset_index=1118  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1118.md`
- dataset_index=1140  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1140.md`
- dataset_index=1143  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1143.md`
- dataset_index=1144  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1144.md`
- dataset_index=1159  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1159.md`
- dataset_index=1195  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1195.md`
- dataset_index=1218  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1218.md`
- dataset_index=1280  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1280.md`
- dataset_index=1371  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1371.md`
- dataset_index=1394  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1394.md`
- dataset_index=1421  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1421.md`
- dataset_index=1435  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1435.md`
- dataset_index=1459  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1459.md`
- dataset_index=1484  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1484.md`
- dataset_index=1495  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1495.md`
- dataset_index=1686  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1686.md`
- dataset_index=1814  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1814.md`
- dataset_index=1837  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1837.md`
- dataset_index=1862  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1862.md`
- dataset_index=1875  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1875.md`
- dataset_index=1880  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1880.md`
- dataset_index=1886  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1886.md`
- dataset_index=1917  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1917.md`
- dataset_index=1934  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1934.md`
- dataset_index=1948  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_1948.md`
- dataset_index=2130  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2130.md`
- dataset_index=2211  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2211.md`
- dataset_index=2231  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2231.md`
- dataset_index=2235  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2235.md`
- dataset_index=2245  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2245.md`
- dataset_index=2253  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2253.md`
- dataset_index=2258  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2258.md`
- dataset_index=2390  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2390.md`
- dataset_index=2489  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2489.md`
- dataset_index=2512  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2512.md`
- dataset_index=2585  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2585.md`
- dataset_index=2641  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2641.md`
- dataset_index=2647  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2647.md`
- dataset_index=2678  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2678.md`
- dataset_index=2694  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2694.md`
- dataset_index=2697  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2697.md`
- dataset_index=2715  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2715.md`
- dataset_index=2716  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2716.md`
- dataset_index=2808  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2808.md`
- dataset_index=2988  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_2988.md`
- dataset_index=3033  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3033.md`
- dataset_index=3035  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3035.md`
- dataset_index=3040  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3040.md`
- dataset_index=3041  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3041.md`
- dataset_index=3050  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3050.md`
- dataset_index=3053  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3053.md`
- dataset_index=3076  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3076.md`
- dataset_index=3114  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3114.md`
- dataset_index=3128  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3128.md`
- dataset_index=3159  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3159.md`
- dataset_index=3222  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3222.md`
- dataset_index=3324  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3324.md`
- dataset_index=3391  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3391.md`
- dataset_index=3555  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3555.md`
- dataset_index=3622  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3622.md`
- dataset_index=3700  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3700.md`
- dataset_index=3716  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3716.md`
- dataset_index=3760  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3760.md`
- dataset_index=3776  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3776.md`
- dataset_index=3868  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3868.md`
- dataset_index=3920  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3920.md`
- dataset_index=3966  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_3966.md`
- dataset_index=4054  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4054.md`
- dataset_index=4055  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4055.md`
- dataset_index=4081  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4081.md`
- dataset_index=4229  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4229.md`
- dataset_index=4258  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4258.md`
- dataset_index=4353  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4353.md`
- dataset_index=4363  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4363.md`
- dataset_index=4375  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4375.md`
- dataset_index=4423  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4423.md`
- dataset_index=4463  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4463.md`
- dataset_index=4510  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4510.md`
- dataset_index=4517  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4517.md`
- dataset_index=4789  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4789.md`
- dataset_index=4791  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4791.md`
- dataset_index=4823  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4823.md`
- dataset_index=4832  dossier=`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers/case_4832.md`

---

**Begin. For each case: Read dossier → decide → append one JSON line to `/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/adversarial_labels.jsonl` → next case. No batched end-of-response output. Use incremental appends so context-exhaustion doesn't lose work.**

When finished, respond with a one-line summary: `Done. Wrote <N> lines to <path>.`
