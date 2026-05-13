# aiq-qwen3.5-plus — F_catalog.md (finalized per-framework architectural failures)

**Scope**: Failures that (a) are uniquely produced by aiq's pipeline architecture (compress layer + multi-stage refine) and (b) cannot be repaired by a general metacognitive middleware bolted on top of the framework. These cases are excluded from the cross-framework `unified_R` set and from the `middleware_rules/` priority set.

**Namespace**: aiq.F1, aiq.F2. Not merged with other frameworks' F namespaces.

**Combined share**: 21 / 113 = 18.6% of aiq failures are architectural-F, not reasoning-R.

---

## aiq.F1 — CompressDrift  (8 cases, 7.1%)

**Mechanism (aiq-architectural)**:
aiq's pipeline ends with a `compress_to_graph` LLM call that free-form summarizes terminator + reflection text into a structured causal-graph JSON. The compress layer has no contract stating "the last terminator's hypothesis is authoritative"; it picks the most textually-prominent service name rather than the terminator's actual conclusion. Case 603 is canonical: terminators converged on `ts-order-service`, but compress output named `ts-food-service` because food-service dominated the accumulated text as RabbitMQ-noise context.

**Why this is F (not R)**:
- The defect lives in post-reasoning output extraction, not in the reasoning itself.
- A middleware that observes the trajectory cannot alter compress output (compress commits directly to DB).
- The mechanism cannot manifest in frameworks without a compress-layer (thinkdepthai ReAct terminator, deerflow finalize tool, claudecode final assistant message).

**Repair path (framework code change)**:
1. Pass the last terminator's `hypothesis_service` as an authoritative input to compress; constrain compress to fill the graph *around* it.
2. Add post-compress consistency check: if compress output's `root_causes` disagrees with last terminator, re-prompt compress with the terminator's conclusion.
3. OR remove compress, have each terminator emit structured JSON directly.

**Case references**: 603 (canonical), 860, 1140, 1886, 2752, 2769, 3600, 4832.

---

## aiq.F2 — RefineStageReversesCorrect  (13 cases, 11.5%)

**Mechanism (aiq-architectural)**:
aiq's refine stages (stage_1_refine1 / stage_2_refine2) run *fresh* 20-round investigations taking the prior stage's terminator text as input. The refine stage typically begins by querying the prior hypothesis's service directly, observes mostly `status_code=Ok` and HTTP 200 spans (because the failing pod is restarting, not erroring), and interprets the silence as "healthy" — reversing a correct stage_0 hypothesis. Case 99 is canonical: stage_0 correctly named `ts-consign-price-service` → stage_1 refine queried it, saw HTTP 200 + INFO logs → reversed to `ts-consign-service` where the visible 503 cascade was.

**Why this is F (not R)**:
- The refine stage's mandate ("refine the initial hypothesis") lacks the constraint "stage_0 must be explicitly refuted by positive evidence of a different service's fault".
- A middleware at the agent level cannot modify the refine-stage system prompt or tool policy.
- In single-pass frameworks (thinkdepthai ReAct, claudecode), all evidence accumulates in one turn context — systematic stage-to-stage reversal is rare.

**Repair path (framework code change)**:
1. Amend refine-stage prompt: "To disagree with stage_0 you must produce positive evidence that a *different* service is the primary fault — not merely absence of errors on the stage_0 candidate."
2. Add a restart-signature rule: missing-spans + `status_code=Unset` on the stage_0 candidate → *positive* evidence for stage_0, not negative.
3. Require refine to query JVM / k8s / memory metrics on the stage_0 candidate before it can terminate with a different hypothesis.

**Case references**: 99 (canonical), 156, 1814, 2283, 2713, 3008, 3125, 3278, 3556, 4257, 4530, 4740, 4801.

---

## Summary table

| F code | Name | Count | Share | Middleware-fixable? |
|---|---|---:|---:|---|
| F1 | CompressDrift | 8 | 7.1% | NO (compress code change) |
| F2 | RefineStageReversesCorrect | 13 | 11.5% | NO (refine prompt/tools) |
| **Total F** | | **21** | **18.6%** | |

**Non-F failures (92/113 = 81.4%)** are general reasoning defects classifiable in the cross-framework `unified_R` set — see `merged/unified_R.md`.
