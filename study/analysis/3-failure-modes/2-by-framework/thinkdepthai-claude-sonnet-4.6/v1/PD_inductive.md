# PD_inductive.md — thinkdepthai-claude-sonnet-4.6

Process-defect (PD) taxonomy induced from 51 failure cases (AC@1 89.8%; failures are the 51 incorrect cases out of 500). Each PD is a trajectory-observable, boolean-detectable action that is **missing** or **warped** — orthogonal to the R (reasoning) and D (data) axes.

| # | Class | n | Scope |
|---|---|---:|---|
| PD1 | BaselineContrastSkipped | 22 | shared |
| PD2 | CandidateNeverIsolatedByWhere | 31 | shared |
| PD3 | CallTreeBuildAbsent | 18 | shared |
| PD4 | BudgetExhaustCommit | 13 | shared |
| PD5 | ThinkNarrationDominant | 23 | framework_specific (sonnet + think_tool) |
| PD6 | CompromiseMultiRCOutput | 7 | shared |
| PD7 | TraceFollowAbsent | 6 | shared |

Coverage: 50/51 cases (98%) have ≥1 PD; only case 1495 has zero PDs (agent probed GT 7x but still committed to a neighbor — pure reasoning failure with adequate process).

Case 4463 is a dataset_anomaly; PD signals are still surfaced but `confirmed=false`.

---

## PD1 — BaselineContrastSkipped

### Self-check

- **Q1 (positive criteria reasoning-verb-free?):** "baseline_contrast intent count == 0" — no reasoning verb, pure action counter. Pass.
- **Q2 (detectable from trajectory alone?):** yes — count elements in `meta.llm_intents.final` where `intent == 'baseline_contrast'`. Pass.

### Definition

Agent never issued a SQL comparing abnormal-period vs normal-period numerics on any service, despite running a multi-round investigation. May or may not have called `baseline_collect` (collecting normal-period reference data), but never followed through with an explicit contrast query.

### Positive criteria

- `count(intent == 'baseline_contrast' in meta.llm_intents.final) == 0`

### Negative criteria (explicitly NOT this class)

- Agent ran `baseline_contrast` even once → not this PD, regardless of what the comparison found.
- Agent used informal memory comparison inside a `think_tool` narration without firing a baseline SQL → still NOT this PD (we do not read inside think_tool; the action we score is the SQL).

### Detection signals (trajectory-only)

- Primary: `sum(1 for s in meta.llm_intents.final if s['intent'] == 'baseline_contrast') == 0`
- Secondary (severity): ratio `baseline_collect / baseline_contrast` — if collect > 0 but contrast == 0, agent gathered reference data and never used it.

### Canonical example

`case_315` — 23 rounds, `baseline_collect` fired twice (rounds 13, 20) to pull normal-period numerics for order-service DB queries. No `baseline_contrast` SQL ever joined abnormal vs normal periods on the candidate services. Agent's conclusion "90-second DB timeout" was picked from the abnormal data alone with no statement of "normal was Xms, abnormal is 90000ms, delta 100000x".

### Members (22)

315, 323, 339, 471, 675, 1144, 1280, 1326, 1421, 1862, 2616, 2678, 2682, 2715, 2748, 2801, 3236, 3555, 3592, 4423, 4510, 4739

---

## PD2 — CandidateNeverIsolatedByWhere

### Self-check

- **Q1 (reasoning-verb-free?):** "service X was never the subject of a `WHERE service_name = '<X>'` SQL" — purely action-level query-pattern predicate. Pass.
- **Q2 (trajectory alone?):** yes — regex over tool-call arguments across all rounds. Pass.

### Definition

At least one service that was **implicated in the final GT set** was either (a) never the target of a dedicated `WHERE service_name = '<svc>'` SQL, or (b) touched exactly once as an incidental probe then abandoned without confirmation SQL. The defect is not about the conclusion; it is about never isolating the candidate in its own query.

> **Note on GT usage for detection.** The operational detector (trajectory-only) is: "counted distinct services that received ≥ 2 targeted WHERE-service_name probes; flag if < |gt_services|". Here, for each 51-case label-set analysis we use GT to identify which candidate was missed, but the trajectory-only check is "count of distinct services probed ≥2× ". Low counts (≤3) are a structural indicator regardless of GT.

### Positive criteria

- For each service s that appears in earlier findings (trace listings, error logs, anomaly tables): `count(SQL with 'service_name' = '<s>') == 0` **OR** `count == 1` with no follow-up SQL in subsequent rounds.

### Negative criteria

- Agent probed s ≥ 2× even if the conclusion is wrong → not this PD (service was isolated; the error lives in R or D).
- Probe used pod-name LIKE instead of service-name = → still counts as a probe (wide enough).

### Detection signals (trajectory-only)

- Primary: extract all `WHERE service_name = '<svc>'` literals and pod-name LIKE patterns across trajectory; build service→probe_count map.
- Flag when: set of mentioned services (union from SQL results, think_tool narrations) ⊃ set of probed services by ≥ 1.

### Canonical example

`case_572` — GT is `ts-food-service + ts-train-food-service`. Across 39 rounds and 32 SQL calls, agent ran zero SQLs with `WHERE service_name = 'ts-food-service'` or `WHERE service_name = 'ts-train-food-service'`. The food-service errors appeared in the rolled-up error-log overview, but the agent never zoomed in on food-service specifically with a targeted probe.

### Members (31)

315, 323, 572, 675, 1140, 1326, 1421, 1484, 1880, 2011, 2130, 2640, 2678, 2682, 2715, 2748, 2801, 2830, 2836, 3112, 3125, 3493, 3555, 3592, 3868, 4229, 4423, 4433, 4463, 4510, 4707

---

## PD3 — CallTreeBuildAbsent

### Self-check

- **Q1 (reasoning-verb-free?):** "agent did not invoke call_tree_build intent" — action absence. Pass.
- **Q2 (trajectory alone?):** yes. Pass.

### Definition

On an **edge-type fault** (HTTP*, Network*, NetworkBandwidth, NetworkPartition, HTTPResponseDelay, HTTPRequestAbort etc.), the agent never built a hierarchical call tree (parent-span → child-span chain) with a `call_tree_build` SQL. Without the call tree the agent cannot attribute slowness/errors to a specific caller→callee edge; it falls back to sibling-magnitude heuristics.

### Positive criteria

- fault_type ∈ {HTTP*, Network*, ContainerKill-with-downstream-cascade}
- AND `count(intent == 'call_tree_build' in meta.llm_intents.final) == 0`

### Negative criteria

- JVM-intrinsic or pure-pod-level faults (JVMMemoryStress, ContainerKill targeting a leaf) → edge-type check fails; not this PD.
- Agent issued `call_tree_build` even once, even if the output was ignored → not this PD.

### Detection signals (trajectory-only)

- Primary: `sum(1 for s in meta.llm_intents.final if s['intent'] == 'call_tree_build') == 0`
- Scope filter: predicted_root_causes include a service that pairs with another in `gt_services` on an HTTP/Network edge family (derived from dataset meta); this is proxied by fault_type class.

### Canonical example

`case_2011` — HTTPRequestAbort on `ts-route-plan-service → ts-travel2-service`. Across 47 rounds the agent did `trace_follow` twice and `service_trace_scan` twice, but never ran a `call_tree_build` query that would have shown the parent → child span structure on the `ts-route-plan-service → ts-travel2-service` edge. Picked `ts-travel-service` (the wrong twin of travel2).

### Members (18)

315, 371, 471, 2011, 2183, 2584, 2678, 2682, 2715, 2748, 3033, 3236, 3555, 3592, 4229, 4423, 4510, 4739

---

## PD4 — BudgetExhaustCommit

### Self-check

- **Q1 (reasoning-verb-free?):** "trajectory length ≥ 45 rounds and final commitment emerges at budget end". Action-count predicate. Pass.
- **Q2 (trajectory alone?):** yes — round count + position of the final commitment statement. Pass.

### Definition

Agent ran the trajectory to (near) the round-budget ceiling, and the final RC commitment emerges in the last few rounds without a late-stage pivot-retry SQL on an alternative hypothesis. The defect is **failure to decide inside budget** — not the choice of answer.

### Positive criteria

- `n_rounds ≥ 45`
- AND in the last third of rounds, no SQL introduces a service that had not already been probed (no fresh-candidate probes)

### Negative criteria

- Case concluded in ≤ 40 rounds, even with a wrong answer → not this PD.
- Long trajectory but agent explicitly pivoted to a new candidate in round N-5 and tested it with ≥2 new SQLs → not this PD.

### Detection signals (trajectory-only)

- Primary: count `## Round` markers in trajectory dump.
- Secondary: last_new_candidate_probe_round / total_rounds — flag when < 0.65.

### Canonical example

`case_4433` — 70 rounds (the longest), 53 intents. Agent first hypothesized `ts-price-service` around round 10; cycled through `call_tree_build` 9× over the next 50 rounds; committed to `ts-price-service` at round 66 with no pivot-retry SQL on an alternative (e.g. basic-service or route-service, the actual GT). The trajectory exhausted the token/round budget and delivered its first-formed hypothesis.

### Members (13)

339, 675, 1948, 2011, 2174, 2541, 2584, 2801, 3033, 3284, 4229, 4423, 4433

---

## PD5 — ThinkNarrationDominant  `scope=framework_specific`

### Self-check

- **Q1 (reasoning-verb-free?):** "think_tool fires on > 40% of rounds AND think_tool count ≥ 15" — pure action-counter predicate; does not inspect think_tool content. Pass.
- **Q2 (trajectory alone?):** yes. Pass.

### Framework-specific rationale

`thinkdepthai` is the only ReAct-style agent in this eval that wires `think_tool` as a first-class interleaved action between SQL rounds. Five other agents (Auto-Deep-Research, aiq, OpenRCA, mABC, DeepResearchAgent) also register `think_tool`, but only thinkdepthai's ReAct loop invokes it at this frequency (avg ≥ 0.4 of rounds on the failure subset). The PD captures the framework's tendency to spend think-rounds re-stating prior findings instead of branching to a new probe.

### Definition

On failure cases, `think_tool` invocations are the plurality action per round; successive think-rounds re-state prior numerics / hypotheses without producing a new WHERE clause or switching intent category in the subsequent SQL round.

### Positive criteria

- `think_tool_count ≥ 15`
- AND `think_tool_count / n_rounds > 0.40`

### Negative criteria

- Short trajectories (<20 rounds) where think_tool fires each round but is strictly setup → not this PD.
- think_tool fires but the immediately-following SQL uses a **new** WHERE service_name or new intent category → not this PD (think actually advanced the plan).

### Detection signals (trajectory-only)

- Primary: count "- think_tool:" occurrences per round in trajectory.
- Secondary: check for "new WHERE clause" in the SQL following each think_tool — a stricter variant of the same defect.

### Canonical example

`case_339` — 49 rounds, 24 think_tool invocations (49% of rounds). The think_tool rounds from R28 onward re-state "order-service SELECT Order is slow AND consign-service has NonUniqueResultException AND rabbitmq DNS is loud" without triggering a SQL that isolates any new candidate (such as `ts-travel-service`, the actual GT). Final answer merges two of the three noise sources into a dual-RC.

### Members (23)

339, 572, 1140, 1326, 1421, 1880, 1948, 2174, 2584, 2597, 2616, 2748, 2830, 3033, 3107, 3112, 3554, 3592, 3868, 4423, 4463, 4510, 4707

---

## PD6 — CompromiseMultiRCOutput

### Self-check

- **Q1 (reasoning-verb-free?):** "final answer root_causes list has length ≥ 2". Action-level output-shape predicate. Pass.
- **Q2 (trajectory alone?):** yes — last-round output. Pass.

### Definition

Final `root_causes` array contains two or more services — the agent never converged to a single commitment. Often a compromise between two loud-signal candidates.

### Positive criteria

- `len(final_answer.root_causes) ≥ 2` AND the services listed share **no edge** in the agent's own predicted causal graph (i.e. they are not a legitimate caller→callee pair, they are parallel compromises).

### Negative criteria

- Multi-RC is an edge fault where both endpoints are legitimately GT (e.g., GT = {preserve, seat}) and agent correctly picks both → not this PD. (Detector would check whether the two predicted RCs form an edge in predicted graph.)
- Single-RC even if wrong → not this PD.

### Detection signals (trajectory-only)

- Primary: parse final-answer JSON; count root_cause entries.
- Secondary: test whether the two RCs form an edge in predicted graph.

### Canonical example

`case_339` — final: `[ts-consign-service, ts-order-service]`. Both are noise-candidates; they do not form an edge in agent's predicted graph; agent produced a compromise dual answer after 49-round budget exhaustion.

### Members (7)

339, 572, 675, 1948, 2682, 2801, 4707

---

## PD7 — TraceFollowAbsent

### Self-check

- **Q1 (reasoning-verb-free?):** "trace_follow intent count == 0". Action counter. Pass.
- **Q2 (trajectory alone?):** yes. Pass.

### Definition

Agent never issued a `trace_follow` SQL that walks across a specific trace_id from one service's span to another. This is distinct from PD3 (call_tree_build) — PD3 builds the hierarchical structure of one trace, PD7 follows a specific request-ID thread across services. Absence of both leaves the agent with only aggregate latency rankings.

### Positive criteria

- `count(intent == 'trace_follow' in meta.llm_intents.final) == 0`
- AND total SQL count ≥ 20

### Negative criteria

- trace_follow fired even once → not this PD.
- Short trajectory with < 20 SQL calls (not enough signal) → out of scope.

### Detection signals (trajectory-only)

- Primary: intent counter.
- Secondary: whether SQL queries use `WHERE trace_id = '...'` or `WHERE trace_id IN (SELECT trace_id ...)` patterns.

### Canonical example

`case_1484` — HTTPResponseDelay at travel-plan → train-service. 39 rounds, 34 intents; `service_trace_scan` fired 2×, `call_tree_build` fired 2×, but `trace_follow` never. Agent never pinned down a specific slow trace_id and walked it through the call path; picked `ts-seat-service` because it had the most visible span in a single sampled trace.

### Members (6)

572, 1484, 2836, 3555, 3868, 4707

---

## Cross-check summary

- MECE at class level: all pairwise overlaps ≤ 55%. No class is a strict subset of another.
- Coverage: 50/51 cases have ≥ 1 PD. Only 1495 (JVM memory stress with adequate process) has zero PDs.
- D co-occurrence max: PD3 × D_edge_symmetric_ambiguity = 39%.  
- R co-occurrence max: PD3 × T3_EdgeCallerCalleeConfusion = 61% (high but < 90%; PD3 captures "never built the tree", T3 captures "picked wrong side" — different conceptual layers).

See `PD_induction_log.md` for rejected candidates, triangulation conflicts, and density enforcement notes.
