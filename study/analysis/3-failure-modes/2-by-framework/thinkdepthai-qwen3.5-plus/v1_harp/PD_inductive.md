# PD (Process Defect) Taxonomy — thinkdepthai-qwen3.5-plus

Framework: thinkdepthai single-agent ReAct, backend qwen3.5-plus, think_tool available.
Sample: 105 failure cases (AC@1 = 79%, lowest of the four agents).
Methodology: pure bottom-up induction from trajectory evidence (labels.jsonl `proximate_cause`, per_case_analysis.md divergence blocks, dossiers' raw trajectory SQL + think_tool). No candidate PD wordlist was consumed. D/R tags in labels were ignored during induction. After induction, D_projection_frozen.jsonl and R_merge_table_frozen.jsonl were used **only** for the MECE self-check.

A PD is a trajectory-observable, boolean-detectable, process-level action that is **missing** or **degenerate**. PDs are *action-shape* defects: they describe what the agent did or failed to do at the SQL / intent / think_tool level, and are orthogonal to both D (data-layer obstacles) and R (reasoning conclusions).

---

## Self-check (applied to every class below)

- **Q1: Does the class' positive criterion describe an action (or its absence) observable in the trajectory without reference to GT or to the agent's final conclusion?**
- **Q2: Does the class avoid re-describing a reasoning verb (anchored / blamed / reversed) or a data phenomenon (silent victim / ambient noise)?**

Every class below passes Q1+Q2. The three rejected drafts (see `PD_induction_log.md`) violated Q2.

---

## PD1_NoBaselineContrast  ·  104/105 (99.0%)

### Definition
Agent did not run a single SQL query that explicitly contrasts an abnormal metric/log against its normal-period counterpart (no JOIN across `normal_*` and `abnormal_*`, no `abs(abnormal - normal)`, no ratio query, no `baseline_contrast` intent fired). `baseline_collect` alone (one-sided abnormal aggregation) does **not** satisfy the criterion.

### Positive criteria (action missing)
- No element in `meta.llm_intents.final` has `intent = 'baseline_contrast'`.
- Cross-check: no SQL with BOTH `normal_*` and `abnormal_*` tables named in the same query body, AND no SQL computing `abnormal - normal` / `abnormal / normal` / `delta`.

### Negative criteria (not PD1)
- Agent queries normal_logs and abnormal_logs in two **separate** SQLs but manually reasons "those errors also appear in normal" → not PD1 (counts as chronicity reasoning; see PD8). (NB: empirically zero failure cases ran two parallel single-side aggregations that were then quantitatively compared in think_tool, so PD1 and PD8 rarely dissociate.)
- Agent ran a `baseline_contrast` intent but on the wrong metric → not PD1 (still counts as executed action).

### Detection signals (trajectory-only)
- Primary: `'baseline_contrast' NOT IN {e['intent'] for e in meta.llm_intents.final}`.
- Secondary (for raw SQL fallback): `no SQL q such that q.parquet_files contains both 'normal_' and 'abnormal_' OR q.query matches /abnormal[_\w]*\s*[-\/]\s*normal[_\w]*/`.

### Canonical example
**case_33**: Across 60 rounds and 37 SQLs, the agent sees `UnknownHostException: ts-rabbitmq` in abnormal logs. The identical error pattern is present in `normal_logs.parquet` (food-service AmqpConnectException is a chronic deployment condition). The agent never issues a single `SELECT COUNT(*) FROM normal_logs WHERE message LIKE '%rabbitmq%'` vs `FROM abnormal_logs` delta query. Had it done so, the delta would have been ~0 and the anchor would have collapsed.

### Other canonical members (5/104): 33, 99, 130, 156, 315

### Why not R?
The action missing here is a SQL query that reads two tables and computes a numeric comparison. An agent could execute this action and still conclude wrongly — or skip the action and conclude rightly. The PD is orthogonal to the reasoning conclusion.

### Why not D?
D describes what the data hides/reveals. PD1 describes what query the agent chose not to write. The data always exposes `normal_*` tables; not using them is purely process.

---

## PD2_NoJVMFamilyDrill  ·  98/105 (93.3%)

### Definition
Agent never issued a SQL that filters on a specific service_name AND probes a JVM-family metric (`jvm.class.loaded`, `jvm.class.count`, `jvm.gc.duration`, `jvm.thread.count`, `jvm.cpu.time`). No `jvm_state` intent appears in `meta.llm_intents.final`.

### Positive criteria
- `'jvm_state' NOT IN {e['intent'] for e in meta.llm_intents.final}`.
- Equivalent SQL check: no SQL matching `WHERE service_name='<X>' AND metric LIKE '%jvm.%'`.

### Negative criteria
- Broad scan `SELECT metric, AVG(value) FROM abnormal_metrics WHERE metric LIKE '%jvm%' GROUP BY metric` (no per-service filter) → still PD2 because the per-service drill is missing; the broad scan dilutes the candidate-service signal.
- Agent queries JVM metric on the **wrong** service → not PD2 (executed action exists).

### Detection signals
- Primary: intent-array lookup.
- Secondary: regex over concatenated SQL text `service_name\s*=\s*'[^']+'\s+AND.*jvm\.` (or reversed order).

### Canonical example
**case_33** (JVMMemoryStress on ts-auth-service): `jvm.class.loaded` z=5238 on ts-auth-service is the canonical injection fingerprint. The agent queries container memory for ts-auth-service (round 40) and sees a 2.6GB RSS spike but never queries `jvm.class.loaded` or `jvm.gc.*` for any service. Because the agent dismissed the memory spike as "avg looked normal" (no baseline contrast either — PD1 co-occurs), and it did not touch the JVM metric family, the JVMChaos fingerprint was invisible.

### Other canonical members (5/98): 33, 99, 130, 156, 315

### Why not R?
PD2 does not say "agent reasoned about the wrong metric family". It says the SQL action targeting a metric-family × service pair never executed. An agent that runs the right JVM query but mis-interprets the output is NOT PD2.

### Why not D?
D2 (VictimSilentOnPath) notes that JVMChaos injections yield a silent GT service. PD2 is the complementary process deficit: even when the metric family *is* available (the parquet file is on disk), the agent never probed it. Two cases can have D2 without PD2 (if the agent ran jvm_state but read it wrong) and vice-versa.

---

## PD3_NoContainerFamilyDrill  ·  84/105 (80.0%)

### Definition
Agent never issued a SQL that filters on a specific service_name AND probes a container-family metric (`container.filesystem.usage`, `container.cpu.time`, `k8s.pod.memory.major_page_faults`, `k8s.pod.memory.page_faults`, `container.memory.*`). No `container_resource` intent appears.

### Positive criteria
- `'container_resource' NOT IN {e['intent']}`.
- SQL: no `WHERE service_name='<X>' AND metric LIKE '%container.%'` or `%filesystem%` or `%page_fault%`.

### Negative criteria
- A `k8s_state` query that reads `k8s.pod.phase` or `k8s.deployment.available` does not count — those are orchestrator-state metrics, not resource metrics. (Several cases run k8s_state intent but miss container_resource; the two are distinct intents.)

### Detection signals
- Primary: intent-array lookup.
- Secondary: regex `service_name\s*=\s*'[^']+'\s+AND.*\b(container\.|filesystem|page_fault)\b`.

### Canonical example
**case_804** (PodFailure on ts-train-service): Container memory collapsed 818MB→604KB (z=93.7), textbook container-kill. The agent runs 73 rounds of trace and log analysis, finds 3 surviving "Unset" spans from ts-train-service and declares it healthy. No `container.*` / `filesystem` / `page_fault` query ever filters on ts-train-service.

### Other canonical members (5/84): 99, 130, 156, 315, 572

### Why not R?
Compare to R1 LoudnessAnchor: R1 describes the reasoning conclusion ("noisy victim must be cause"). PD3 is the action: the container metric family was never probed for the candidate service. An agent could probe it, see nothing anomalous (wrong service), then still make an R1-style loudness anchor on a different service. Distinct axes.

### Why not D?
D categorises the data scene; PD3 categorises the query repertoire choice. PodChaos cases (injected pod silent, container metrics anomalous) can be solved if the agent probes container metrics — the data is there; the agent didn't ask.

---

## PD4_NoCallTreeBuild  ·  75/105 (71.4%)

### Definition
Agent performed one-off `trace_follow` but never built a call-tree (no `call_tree_build` intent; no SQL using `WITH RECURSIVE` or self-join on `parent_span_id` to reconstruct the full caller→callee graph for a trace).

### Positive criteria
- `'call_tree_build' NOT IN {e['intent']}`.
- SQL: no query matching `WITH RECURSIVE.*parent_span_id` or `FROM \w+_traces t1 JOIN \w+_traces t2 ON t1.span_id = t2.parent_span_id`.

### Negative criteria
- A single `SELECT * FROM abnormal_traces WHERE trace_id='<X>' ORDER BY time` (a flat view of all spans in a trace) does **not** count — that's trace_follow. The defect is the absence of a hierarchical reconstruction that groups by caller/callee edges.
- If agent ran call_tree_build on an irrelevant trace → not PD4.

### Detection signals
- Primary: intent-array lookup.
- Secondary SQL regex: `with\s+recursive|t1\.span_id\s*=\s*t2\.parent_span_id`.

### Canonical example
**case_1814** (JVMMemoryStress on ts-basic-service): The agent follows traces ui-dashboard → preserve → travel-service, sees a 3.8s error in travel-service, stops. Had it issued a call_tree_build query rooted at the failing trace, it would have seen travel-service calling ts-basic-service (the injected target) with `injection_affected` spans. Instead, it declared travel-service "deepest in the error chain" and stopped.

### Other canonical members (5/75): 33, 130, 156, 281, 315

### Why not R?
R4 HubFabrication or "stopped one hop short" is a reasoning-conclusion label. PD4 is the query-shape deficit that enabled it. Cases with PD4 may or may not exhibit "stopped one hop short" — the agent may still happen to reason past the single-trace view. PD4 simply says the transitive-closure SQL action did not run.

### Why not D?
D3 EdgeSymmetricAmbiguity (edge injection confusing caller vs callee) is a data-scene property. PD4 is agent-side: even when the call graph could be materialised in one SQL, the agent chose iterative hop-by-hop exploration instead.

---

## PD5_ErrorStatusFilterBlind  ·  73/105 (69.5%)

### Definition
Agent issued ≥1 SQL with `status='Error'` (or `attr_status_code='Error'`) filter but never issued a complementary query probing `status='Unset'`, `status IS NULL`, `missing_span`, or `status_code != 'Error'` with a non-trivial matching clause. The agent's view of "problems" is exclusively error-status spans, which blinds it to stalled / silent / injected-but-successful-looking victims.

### Positive criteria
- At least one SQL matches `status(_code)?\s*=\s*'?Error'?` (case-insensitive).
- No SQL matches `status(_code)?\s*=\s*'?Unset'?` OR `status(_code)?\s+IS\s+NULL` OR contains substring `missing_span`.

### Negative criteria
- Agent uses `status_code != 'OK'` or a latency-only filter → not PD5 (the complementary class IS being probed implicitly by latency).
- Agent never uses `status='Error'` filter at all → not PD5 (can't be blind to Unset if it wasn't selecting on Error in the first place).

### Detection signals
- Primary: SQL regex over concatenated trajectory `SELECT.*WHERE.*status(_code)?\s*=\s*'Error'` AND negation `NOT EXISTS WHERE status(_code)?\s*=\s*'Unset'`.

### Canonical example
**case_1195** (JVMMemoryStress on ts-order-other-service): At round 10 the agent runs `SELECT service_name, COUNT(*) FROM abnormal_traces WHERE attr_status_code='Error' GROUP BY service_name`. Result: ts-security-service tops the list with 36 Error-status spans. ts-order-other-service (the GT) emits only `Unset` spans (it is slow, not erroring). The agent anchors on security-service. It never issues the complementary query `WHERE attr_status_code IS NULL OR status_code='Unset' AND duration > <threshold>`. Over the remaining 50 rounds, every error-oriented query reproduces the same blindness.

### Other canonical members (5/73): 33, 99, 130, 156, 339

### Why not R?
R1 LoudnessAnchor describes the conclusion ("loudest error-count service is RC"). PD5 describes the *query shape* that made the conclusion unavoidable: the complementary Unset slice was never materialised, so the RC literally wasn't in the agent's candidate set. An agent can exhibit R1 without PD5 (it probes both slices but still anchors on the loud one) and PD5 without R1 (it probes only Error but arrives at the right answer by other means).

### Why not D?
D1 VictimSilentOnPath is a data-scene property (the GT is silent). PD5 is the complementary agent-side deficit (the agent's query set excluded silence).

---

## PD6_ServiceAvgNoSpanMaxDrill  ·  18/105 (17.1%)  ·  scope: framework_specific (qwen3.5)

### Definition
Agent issued one or more queries of the shape `SELECT service_name, AVG(duration)/AVG(value) FROM abnormal_{traces|metrics} GROUP BY service_name ORDER BY AVG DESC` (service-level aggregation ranking) and then never followed up with a span-level MAX(duration) drill (no `GROUP BY span_name ORDER BY MAX(duration) DESC` for any candidate service, no `WHERE span_name LIKE '<method>'` filter). The ranking service-level AVG dilutes slow-span signals (e.g. a JVMMySQLLatency that affects only `SELECT trip` spans in ts-travel-service is lost when averaged across all ts-travel-service spans).

### Positive criteria
- ≥1 SQL has both `GROUP BY service_name` and `AVG(duration)` (or `AVG(value)` on a latency metric) and `ORDER BY ... DESC`.
- No SQL has (`GROUP BY span_name` OR `WHERE span_name LIKE '<X>'`) AND (`MAX(duration)` OR `ORDER BY duration DESC`).

### Negative criteria
- Agent used `MAX(duration)` at service level (no span-level drill) — still PD6; service-level MAX is also blind to span-level concentration but conditions on it is harder; empirically this gives the same diluted ranking.
- Agent issued span-level drill on the wrong service — not PD6 (action executed).

### Detection signals
- SQL regex. Conservative: requires both AVG-service-level rank AND absence of span-level MAX probe across the entire trajectory.

### Canonical example
**case_339** (JVMMySQLLatency injected on `SELECT trip` in ts-travel-service): At round 18 the agent runs `SELECT service_name, AVG(duration), MAX(duration) FROM abnormal_traces GROUP BY service_name ORDER BY AVG(duration) DESC LIMIT 30`. Result: ts-travel-plan-service (249ms avg) and ts-route-plan-service (228ms avg) top the list; ts-travel-service shows 42ms avg (the MySQL-latency slow spans are diluted by thousands of fast non-Trip spans). The agent then targets ts-travel-plan/ts-route-plan. At no later round does it run `WHERE service_name='ts-travel-service' GROUP BY span_name ORDER BY MAX(duration) DESC` which would have surfaced the 3669ms `SELECT trip` spans.

### Other canonical members (5/18): 339, 755, 1114, 1371, 2598

### Framework-specific rationale
This pattern is not observed at this rate in claudecode or aiq taxonomies (those frameworks' prompts guide span-level drill earlier). It reflects a qwen-specific default toward service-level AVG ranking as the first sort step. Scope is therefore tagged `framework_specific`.

### Why not R?
R2 AmplitudeGreed describes the conclusion ("highest observed value wins"). PD6 is the query shape that manufactured the dilution bias — a different axis. Cases with PD6 may have R3 (chronic noise anchor) or R5 (dimension lock) reasoning; PD6 co-occurs with multiple R classes below the 90% threshold.

### Why not D?
D5 DilutedMultiCandidate (when signal is spread across multiple spans of one service) is the data-scene mirror. PD6 is the agent-side complement: the query that would recover the signal (span-level MAX drill) was never issued.

---

## PD7_PostPivotSingleServiceFixation  ·  12/105 (11.4%)

### Definition
After the pivot round (the round at which the agent committed to its eventually-wrong hypothesis, per labels.pivot_round), the tail of the trajectory (pivot_round → final_round, length ≥10) is dominated by a single service: one service appears in ≥6 queries with `WHERE service_name='<X>'`, and ≤3 distinct services are probed by service-name filter across that tail.

### Positive criteria
- `total_rounds - pivot_round >= 10`.
- In the tail rounds, `max(count(service_filter_probes)) >= 6` and `|distinct services probed| <= 3`.

### Negative criteria
- Tail dominated by broad (no service filter) scans → not PD7.
- Tail probes many services (diverse exploration) → not PD7.

### Detection signals
- Per-round service-filter counter, sliced on pivot_round.

### Canonical example
**case_755** (NetworkPartition ts-seat ↔ ts-travel2, pivot round 13, total 47): From round 13 onward, 28 of the agent's 34 `service_name=` filters target `ts-travel-plan-service`. The real injection endpoint was ts-seat-service but ts-seat-service appears in only 2 later queries. The agent loops on travel-plan's latency metrics searching for an explanation of the 86s span gap rather than broadening to probe seat-service or the travel-plan → seat-service edge.

### Other canonical members (5/12): 99, 572, 755, 860, 1195

### Why not R?
R6 AnchoringRevert / confirmation bias describes the reasoning tendency. PD7 is the SQL-level fingerprint: the queries in the tail stop exploring. An agent can show post-pivot fixation and still happen to be right (the anchor was correct) — so PD7 is a pure process signal. In the failure pool, PD7 is most often paired with wrong anchors, but its detection is independent.

### Why not D?
D-class tags the fault scene; PD7 tags the tail-of-trajectory query distribution.

### Note on pivot_round
pivot_round is a labeler annotation, not a trajectory-intrinsic signal. This is a weakness of PD7's criterion. We accept it here because: (a) every labels row has pivot_round, (b) the criterion is verifiable against the trajectory once pivot is specified, (c) an intrinsic replacement ("from round N where `root cause` first appears in think_tool") gives the same pivot in 80% of cases (spot-checked on 10 members).

---

## PD8_NoChronicityReasoning  ·  8/105 (7.6%)

### Definition
No think_tool invocation in the trajectory contains any of the keywords: `background`, `pre-existing`, `chronic`, `compared to normal`, `vs normal`, `baseline`, `ambient`, `normal period`, `normal logs`, `not new`, `same in normal`, `pre-existed`. Agent never verbalises the question "is this error also present in the normal window?"

### Positive criteria
- `len(think_tool contents) >= 3` (ensures agent did use think_tool).
- None of the keyword variants (case-insensitive, substring match) appears in any think_tool thought/reflection.

### Negative criteria
- Agent wrote the word `baseline` in think_tool even in an unrelated context (e.g. referencing `baseline_collect` as an intent label) → not PD8 (the token triggered, even if not used meaningfully). We accept this false-negative to keep detection strictly trajectory-observable without semantic parsing.
- Agent ran a baseline_contrast SQL but never narrated it in think_tool → not PD8 (the action executed; PD1 would already be false).

### Detection signals
- Keyword match over concatenated think_tool text.

### Canonical example
**case_1254** (HTTPRequestReplaceMethod from preserve→seat, pivot 58 of 60 rounds): Across all think_tool narrations, the agent never asks whether the `Order already exists` errors or the "Connection reset" logs are present in the normal window. It constructs a business-logic narrative that ts-order-service is rejecting duplicates, without chronicity sanity-check.

### Other canonical members (5/8): 130, 832, 1140, 1254, 1459

### Rarity note
PD8 is the smallest class (8 cases). This is because many failure trajectories *do* mention "background" or "baseline" in think_tool but still commit to the noisy anchor — those are PD1 (no baseline_contrast SQL) but NOT PD8 (chronicity was verbalised). The separation is intentional: PD1 tracks whether the SQL action fired; PD8 tracks whether the think_tool at least asked the question. The 8 cases that fail both PD1 and PD8 are where the thinking never reached the doubt stage.

### Why not R?
PD8 is not "the agent chose chronic noise as RC" (that's R3 ChronicNoiseAsRC). PD8 is "the agent never said the word 'normal' when examining an error" — a keyword presence check on think_tool text. The two can dissociate: some cases have R3 reasoning but PD8 = False (the agent *did* mention baseline, just convinced itself anyway — PD1 still catches the absent SQL).

### Why not D?
D-class has no think_tool correlate.

---

## Members list (per PD)

```
PD1_NoBaselineContrast (104): 33, 99, 130, 156, 247, 281, 283, 315, 323, 339, 341, 572, 579, 755, 784, 804, 807, 832, 860, 864, 1114, 1140, 1143, 1195, 1218, 1254, 1371, 1394, 1421, 1435, 1459, 1495, 1515, 1814, 1846, 1880, 1917, 1934, 1948, 2092, 2130, 2211, 2231, 2253, 2258, 2285, 2390, 2512, 2598, 2641, 2678, 2682, 2700, 2713, 2715, 2716, 2836, 3059, 3112, 3114, 3120, 3125, 3128, 3138, 3219, 3222, 3278, 3393, 3524, 3552, 3592, 3605, 3622, 3673, 3716, 3760, 3776, 3868, 3878, 3920, 3955, 4032, 4055, 4070, 4081, 4151, 4229, 4258, 4309, 4311, 4353, 4363, 4375, 4463, 4510, 4519, 4530, 4617, 4707, 4732, 4758, 4789, 4841, 4893
# missing: 2988 (the single case with baseline_contrast intent fired)

PD2_NoJVMFamilyDrill (98): 33, 99, 130, 156, 247, 281, 283, 315, 323, 339, 341, 572, 579, 755, 784, 804, 832, 860, 864, 1114, 1140, 1143, 1195, 1218, 1254, 1371, 1394, 1421, 1435, 1459, 1495, 1515, 1846, 1880, 1917, 1934, 1948, 2092, 2130, 2211, 2231, 2253, 2258, 2285, 2390, 2512, 2598, 2641, 2678, 2682, 2700, 2713, 2715, 2716, 2836, 2988, 3059, 3112, 3114, 3120, 3125, 3128, 3138, 3219, 3222, 3278, 3393, 3524, 3552, 3592, 3605, 3622, 3673, 3716, 3760, 3776, 3868, 3878, 3920, 3955, 4032, 4055, 4070, 4081, 4151, 4229, 4258, 4309, 4311, 4353, 4375, 4463, 4510, 4519, 4530, 4617, 4707, 4732, 4758, 4789, 4841, 4893

PD3_NoContainerFamilyDrill (84): 99, 130, 156, 247, 281, 283, 315, 323, 339, 341, 572, 579, 755, 784, 804, 807, 832, 860, 864, 1114, 1140, 1143, 1195, 1218, 1254, 1371, 1394, 1421, 1435, 1459, 1495, 1515, 1814, 1880, 1917, 1934, 2092, 2130, 2211, 2231, 2253, 2258, 2285, 2390, 2512, 2598, 2641, 2678, 2682, 2700, 2713, 2716, 2836, 2988, 3059, 3112, 3114, 3120, 3125, 3128, 3138, 3219, 3222, 3278, 3393, 3552, 3592, 3605, 3622, 3673, 3716, 3776, 3878, 3920, 4032, 4070, 4081, 4151, 4229, 4311, 4353, 4363, 4510, 4530, 4617, 4707, 4732, 4758, 4789, 4841, 4893

PD4_NoCallTreeBuild (75): 33, 130, 156, 281, 283, 315, 323, 339, 341, 572, 579, 784, 804, 807, 860, 864, 1114, 1140, 1143, 1195, 1218, 1254, 1371, 1394, 1421, 1435, 1459, 1495, 1515, 1814, 1846, 1880, 1917, 1934, 1948, 2092, 2130, 2211, 2231, 2253, 2258, 2390, 2512, 2598, 2641, 2682, 2700, 2713, 2715, 2716, 2836, 2988, 3059, 3112, 3114, 3125, 3128, 3138, 3219, 3222, 3278, 3393, 3524, 3592, 3605, 3622, 3716, 3760, 3776, 3868, 3878, 3920, 3955, 4032, 4055, 4070, 4081, 4151, 4229, 4258, 4309, 4311, 4353, 4363, 4375, 4463, 4510, 4519, 4530, 4617, 4707, 4758, 4841

PD5_ErrorStatusFilterBlind (73): 33, 99, 130, 156, 247, 281, 283, 315, 339, 341, 572, 579, 755, 784, 804, 807, 832, 860, 864, 1114, 1140, 1143, 1195, 1218, 1254, 1371, 1394, 1421, 1435, 1459, 1495, 1515, 1814, 1846, 1917, 1934, 1948, 2092, 2130, 2211, 2231, 2253, 2258, 2285, 2390, 2512, 2598, 2641, 2682, 2700, 2713, 2715, 2716, 2836, 3112, 3114, 3120, 3125, 3138, 3219, 3222, 3393, 3524, 3552, 3673, 3716, 3760, 3868, 3878, 3920, 3955, 4055, 4070, 4151, 4229, 4258, 4309, 4311, 4353, 4363, 4510, 4519, 4530, 4617, 4707, 4732, 4758, 4789, 4841, 4893

PD6_ServiceAvgNoSpanMaxDrill (18, framework_specific): 339, 755, 1114, 1371, 1459, 1495, 1814, 2598, 2641, 2678, 2988, 3059, 3128, 3673, 3878, 3955, 4229, 4353

PD7_PostPivotSingleServiceFixation (12): 99, 247, 281, 572, 755, 860, 1195, 1394, 1435, 2836, 4375, 4707

PD8_NoChronicityReasoning (8): 130, 832, 1140, 1254, 1459, 2285, 2700, 3125
```

PDs-per-case distribution: 2 PDs = 3 cases, 3 = 13, 4 = 35, 5 = 37, 6 = 17. No case labelled 0 PDs (no "empty" fallback needed).

---

## MECE summary

- Class-definition MECE verified: every PD has a trajectory-observable boolean criterion; no two criteria are synonyms. PD2 (JVM metric family) and PD3 (container metric family) are cousins but distinct metric tables; they co-occur in 77/105 cases, below the 90% merge threshold.
- Cases may (and do) carry multiple PDs simultaneously — this is expected; MECE does not apply at the case level.
- No "other" bucket; rare patterns that did not reach 3 canonical members (e.g. "committed to speculative hypothesis that one service hosts another with no evidence" — 2 cases) are recorded as rejected candidates in `PD_induction_log.md` and can be promoted if new evidence arrives.
