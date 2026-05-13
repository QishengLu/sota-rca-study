# aiq-qwen3.5-plus — Framework-specific F candidates (Phase α + β round 1)

Candidates below are R classes whose mechanism is tied to aiq's *pipeline architecture* and would require framework code changes (not a general middleware) to repair. They are unlikely to have direct analogs in single-ReAct frameworks (thinkdepthai), tool-calling frameworks (deerflow), or code-execution frameworks (claudecode), because those frameworks do not have the same terminator/refine/compress layering.

---

## F1 — R_compress_drift  (8/113 cases, 7.1%)

**Candidate source**: T8 CompressOverwritesTerminator from taxonomy.md (explicitly labeled "aiq-specific" in the existing taxonomy).

**Mechanism (framework-specific)**:
aiq's pipeline has a `compress_to_graph` LLM call at the tail of each run, which summarizes the accumulated terminator text into a structured causal-graph JSON. This final LLM call operates as a free-form summarizer over a large text buffer containing:
- stage_0_main terminator text
- stage_1_refine1 terminator text
- stage_2_refine2 terminator text
- intermediate "Reflection recorded" texts

Because the compress LLM has no structured contract saying "the last terminator's hypothesis is authoritative", it frequently picks the service name that is *most textually prominent* across the accumulated text rather than the one the terminator concluded with. In case_603 the compress layer named `ts-food-service` because food-service was mentioned many times (as RabbitMQ noise context) even though terminators repeatedly concluded `ts-order-service` was the root cause.

This mechanism cannot manifest in frameworks that emit the final answer directly from the last reasoning step (thinkdepthai's ReAct terminator) or from a structured tool call (deerflow's finalize tool), because there is no compress-layer summarizer between the reasoning termination and the output.

**Repair path (framework code change, not middleware)**:
1. Change `compress_to_graph` from free-form JSON generation to **structured extraction from the terminator**: pass ONLY the last terminator's hypothesis service(s) as the authoritative root-cause set, and use the compress LLM only to fill in the causal-graph nodes/edges *around* that pre-committed root cause.
2. OR add a post-compress consistency check: compare the compress output's `root_causes` to the last terminator's extracted service name; if they disagree, re-prompt the compress layer with "The final terminator concluded X; re-emit the graph rooted at X."
3. OR remove the compress layer entirely and have each stage terminator produce the structured JSON directly, consolidating across stages with a merge-on-agreement rule.

All three options require edits to `aiq/runners/*.py` and the stage-orchestration logic. A trajectory-post-processor middleware cannot repair this because the compress output has already been committed to the DB by the time middleware would see it; the middleware would be detecting-not-preventing.

**Case references**: 603 (canonical), 860, 1140, 1886, 2752, 2769, 3600, 4832.

---

## F2 — R_correct_then_reversed (reflection-induced reversal)  (13/113 cases, 11.5%)

**Candidate source**: T5 ReflectionReversesCorrect from taxonomy.md. Not labeled aiq-specific in taxonomy but the *mechanism* depends on aiq's multi-stage refine pipeline where each refine stage independently re-runs investigation. In single-pass frameworks, reflection is not a separate re-investigation loop — it is in-turn introspection that rarely reverses conclusions because the same evidence is already in context.

**Mechanism (framework-specific)**:
aiq's refine stages work as follows:
1. Stage_0 completes with a terminator naming a root-cause service.
2. Stage_1 refine1 receives the stage_0 terminator text as input, then runs a *fresh* 20-round investigation "to refine the initial hypothesis."
3. The refine stage typically begins by querying the stage_0 hypothesis service directly (`WHERE service_name='<hyp>'`).
4. For silent-fault types (JVM memory stress, ContainerKill, NetworkDelay), this query shows mostly `status_code=Ok`, HTTP 200, and INFO logs — because the failing pod is *restarting*, not *erroring*.
5. The refine stage interprets this as "the stage_0 candidate is actually healthy" and shifts blame to the next service in the call chain that does have visible errors — which is a *downstream* service receiving 503s from the killed upstream.

This is a framework-pipeline issue because the refine stage:
- does not have a constraint that says "stage_0 must be explicitly refuted, not just 'look healthy'";
- over-weights HTTP-200 span observations as evidence of health;
- has no access to a "restart signature detector" that would flag "missing spans + status_code=Unset = failing pod, not healthy one".

In non-pipeline frameworks, the agent accumulates evidence in one pass; refinement happens through iterative tool calls in the same conversation, making systematic reversal much rarer.

**Repair path (framework code change)**:
1. Modify the refine-stage prompt to explicitly require: "To disagree with stage_0, you must find evidence that positively identifies a DIFFERENT service's primary fault — not merely absence of errors on the stage_0 candidate."
2. Add a "restart signature" rule: if the stage_0 candidate service has missing spans OR status_code=Unset as a substantial fraction of its abnormal-window spans, treat that as *positive* evidence for the stage_0 hypothesis, not negative.
3. Change the refine-stage tool set so that querying GT-candidate metrics (jvm.class.loaded, container.filesystem.usage, k8s.pod.memory.*) is *required* before the refine can terminate with a different hypothesis.

These require changes to the aiq stage-orchestration code and the per-stage system prompt; a middleware bolted on top cannot alter the refine loop's internal decision rule.

**Case references**: 99 (canonical), 156, 1814, 2283, 2713, 3008, 3125, 3278, 3556, 4257, 4530, 4740, 4801.

---

## Non-F candidates (present in other frameworks; fixable via general middleware or data-layer augmentation)

- **R_volume_anchor** (24 cases): anchoring on top-volume error service. Present in all agents; fixable via a general "baseline-comparison middleware" that pre-computes log_delta = abnormal − normal and forbids anchoring on services with negative delta.
- **R_upstream_stop** (16 cases): stopping at upstream caller. Present across agents; fixable via a "one-hop-deeper probe" middleware that injects a mandatory downstream-callee check before terminator commits.
- **R_baseline_unchecked** (17 cases): RabbitMQ noise anchoring. Present across agents; fixable via a "known-noise-service blocklist" preprocessor.
- **R_silent_fault_blind** (15 cases): log-first blindness to latency faults. Present across agents; fixable by expanding the prompt/tool set to mandate metric-table probes when log_delta is empty.
- **R_hub_fabrication** (12 cases): fabricating config-service/mysql hubs. Present across agents; fixable via a post-hoc "service name is in S_observed" validation middleware.
- **R_name_twin_confusion** (8 cases): food vs station-food. Present across agents; fixable via a service-name disambiguation middleware (e.g., trainticket-service-resolver skill).

---

## Summary

| F id | Class | Count | aiq-specific? | Middleware-fixable? |
|---|---|---:|---|---|
| F1 | R_compress_drift | 8 | YES (compress layer only in aiq) | NO (requires compress code change) |
| F2 | R_correct_then_reversed | 13 | YES (refine-stage re-investigation only in aiq) | NO (requires refine prompt/tool-set change) |

**Combined aiq-specific failure share**: 21/113 = 18.6% of all failure cases are mechanistically tied to aiq's pipeline architecture (compress layer + refine stages) and would require framework code changes to repair.
