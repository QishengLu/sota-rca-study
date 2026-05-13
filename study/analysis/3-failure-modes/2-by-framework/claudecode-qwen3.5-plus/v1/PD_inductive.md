# PD_inductive.md — claudecode-qwen3.5-plus Process-Defect Taxonomy (v1)

Framework: claudecode-qwen3.5-plus (Claude Code CLI orchestrating qwen3.5-plus as the coding-plan model; agent has native Bash/Read tools, no Task/subagent spawns observed in this dataset, no think_tool, uses DuckDB over parquet files).

Induced strictly bottom-up from 103 labeled failure cases in `labels.jsonl`. PD classes define **trajectory-observable action defects** (missing or degenerate SQL / intent / round-structure behavior), independent of D (data-layer obstacle) and R (reasoning mechanism) axes.

Total classes: **6** (within target 6-10; hard cap 12).

Empty-PD cases (failed but no PD triggered): see PD_induction_log.md. Cases can have 0..N PDs (MECE applies to class definitions, not to cases).

---

## PD1_BaselineCollectedNotContrasted

**Scope**: core

### Self-check
- **Q1 (reasoning verb?)**: Definition uses "ran", "called", "collected" — SQL intent actions. No "anchored", "concluded", "assumed", "inferred". Pass.
- **Q2 (data state?)**: Definition refers to SQL intents `baseline_collect` and `baseline_contrast` — not to "loud", "silent", "noisy". Pass.

### Definition
Agent issued one or more `baseline_collect` intents (SQL queries against `normal_*.parquet` to establish baseline distributions) but never issued a `baseline_contrast` intent (SQL joining normal vs abnormal or computing a normal-vs-abnormal delta). The normal-window data is collected but never used to rule in/out abnormality.

### Positive criteria
`count(intent=="baseline_collect") >= 1` AND `count(intent=="baseline_contrast") == 0`.

### Negative criteria
- A single SQL that SELECTs from `normal_*.parquet` AND `abnormal_*.parquet` with a JOIN or UNION on service_name is `baseline_contrast` → disqualifies.
- If agent ran zero baseline_collect and zero baseline_contrast (pure fire-from-abnormal-only), this PD does **not** fire (different omission; not this class).

### Detection signals (trajectory-only)
```python
intents = meta.llm_intents.final  # list of {round, intent, ...}
bc = sum(1 for i in intents if i["intent"] == "baseline_collect")
bx = sum(1 for i in intents if i["intent"] == "baseline_contrast")
PD1_fires = (bc >= 1) and (bx == 0)
```

### Canonical example
**case_33** (JVMMemoryStress on ts-auth-service): intents include 22 baseline_collect calls (rounds 2, 3, 4, 5, 6, 33, 42, 44, 55, 60, 61, 62, 64, 65, 68, 70, 72, 75, 79, 81, 83) and **zero** baseline_contrast. Agent kept re-collecting normal-window snapshots but never produced a delta. Concluded on ts-ui-dashboard from abnormal-side error rates alone.

### Members (78)
33, 156, 247, 281, 283, 315, 710, 741, 755, 762, 804, 807, 864, 1114, 1118, 1140, 1143, 1195, 1280, 1371, 1394, 1421, 1435, 1484, 1495, 1686, 1814, 1862, 1880, 1917, 1934, 1948, 2130, 2211, 2231, 2235, 2245, 2258, 2512, 2585, 2678, 2694, 2715, 2716, 2808, 2988, 3033, 3040, 3050, 3053, 3076, 3114, 3128, 3159, 3222, 3324, 3391, 3622, 3700, 3716, 3760, 3776, 3920, 3966, 4054, 4055, 4081, 4229, 4258, 4353, 4363, 4423, 4463, 4517, 4789, 4791, 4823, 4832

---

## PD2_FaultLayerMetricProbeSkipped

**Scope**: core

### Self-check
- **Q1**: "probe skipped" — action never happened. No reasoning verb. Pass.
- **Q2**: Predicate on intent categories, not data state. Pass.

### Definition
Fault category implies a specific metric layer that should be probed (JVMChaos → `jvm_state`; NetworkChaos → `network_layer`; PodChaos → `k8s_state`), but the trajectory's 19-category intent sequence contains **zero** SQL with that layer's signature. The agent skipped the metric layer whose signature matches the injection type.

### Positive criteria
For each fault-category → expected-intent pair:
- `fault_category == "JVMChaos"` AND `count(intent=="jvm_state") == 0` → fires
- `fault_category == "NetworkChaos"` AND `count(intent=="network_layer") == 0` → fires
- `fault_category == "PodChaos"` AND `count(intent=="k8s_state") == 0` → fires

HTTPFault is excluded (no single expected metric layer). `DBState` as secondary is not required.

### Negative criteria
- Fires ONCE per case; not cumulative.
- If agent ran the expected intent even with wrong service filter, this PD does not fire (parameter-wise mis-probe is R-class, not PD).

### Detection signals (trajectory-only)
```python
MAP = {"JVMChaos": "jvm_state", "NetworkChaos": "network_layer", "PodChaos": "k8s_state"}
cat = case.fault_category
expected = MAP.get(cat)
if expected:
    PD2_fires = not any(i["intent"] == expected for i in intents)
```

### Canonical example
**case_33** (JVMMemoryStress on ts-auth-service): GT fault is JVM memory pressure on `JWTProvider.init`. Expected intent is `jvm_state` (e.g., SELECT ... WHERE metric LIKE 'jvm.memory.%'). Across 83 rounds, **zero** jvm_state intents. Agent only used `container_resource` and `metric_scan` generically. Canonical also: **case_710, case_2130** (JVMReturn on ts-station-service, zero jvm_state).

### Members (45)
33, 156, 247, 281, 339, 710, 741, 804, 807, 1004, 1114, 1140, 1143, 1144, 1195, 1218, 1280, 1394, 1459, 1495, 1686, 1814, 1837, 1917, 1948, 2130, 2253, 2258, 2390, 2678, 2988, 3035, 3041, 3053, 3222, 3700, 3716, 3760, 3868, 3920, 4054, 4055, 4353, 4363, 4375

---

## PD3_TriageLoopWithoutDrill

**Scope**: core

### Self-check
- **Q1**: "looped", "kept surveying" describe action cadence, not conclusions. Pass.
- **Q2**: Counts triage-category intents, not data loudness. Pass.

### Definition
Agent spent ≥15 SQL in the triage phase (`latency_ranking`, `throughput_compare`, `error_rate_scan`, `error_log_overview`, `metric_scan`) while issuing ≤3 metric-drill SQL (`container_resource`, `jvm_state`, `network_layer`, `k8s_state`, `db_state`). The ratio shows the agent kept surveying the landscape without pivoting into targeted component probes.

### Positive criteria
`n_triage >= 15` AND `n_metric_drill <= 3`.

### Negative criteria
- Not the same as PD1: a case can run baseline_contrast but still triage-loop.
- If total SQL < 10, thresholds do not apply (short trajectories excluded).

### Detection signals
```python
TRIAGE = ["latency_ranking", "throughput_compare", "error_rate_scan", "error_log_overview", "metric_scan"]
DRILL  = ["container_resource", "jvm_state", "network_layer", "k8s_state", "db_state"]
n_tr = sum(1 for i in intents if i["intent"] in TRIAGE)
n_dr = sum(1 for i in intents if i["intent"] in DRILL)
PD3_fires = n_tr >= 15 and n_dr <= 3
```

### Canonical example
**case_247** (route-service JVMMemoryStress): 96 rounds, triage SQL = 21 (error_log_overview 6, error_rate_scan 4, metric_scan 4, latency_ranking 4, throughput_compare 3) but metric-drill SQL = 3 (only). Agent kept ranking services and counting errors instead of probing JVM / container metrics of the silent victim. **case_3324** (ContainerKill): 95-round trajectory with 31 triage intents and 3 metric-drill intents.

### Members (35)
33, 156, 572, 741, 804, 1004, 1114, 1143, 1218, 1435, 1814, 1875, 1880, 1886, 1948, 2130, 2235, 2245, 2258, 2390, 2512, 2585, 2647, 3035, 3041, 3053, 3622, 3716, 4055, 4229, 4258, 4353, 4363, 4375, 4791

---

## PD4_GTServiceNotTargetedWithWhere

**Scope**: core

### Self-check
- **Q1**: "never issued WHERE service_name='<GT>'" — SQL predicate absence. No reasoning verb. Pass.
- **Q2**: Refers to SQL parameter (service_name filter), not data content. Pass.

### Definition
Across the full trajectory, no SQL statement used `WHERE service_name = '<gt_root_cause_service>'` (or equivalent IN-clause including the GT). The agent never issued a direct, by-name probe of the service the GT blames, before emitting its final answer.

### Positive criteria
`count(SQL where regex matches "service_name\s*=\s*'<GT>'") == 0`.
If GT is multi-part (e.g., "ts-station-service, mysql"), **all** GT entities must be absent from any single-service WHERE filter.

### Negative criteria
- GT appearing as a row in a `GROUP BY service_name` result set does NOT satisfy the probe requirement (that's survey, not targeted probe).
- GT appearing only in `service_name IN (...)` with 10+ other services also counts as survey, not targeted probe — but we allow IN-clause of ≤5 elements as a targeted probe.

### Detection signals
```python
# simplified: scan SQL text for WHERE service_name = 'GT' across trajectory
pat = rf"service_name\s*=\s*'{re.escape(gt)}'"
PD4_fires = not re.search(pat, trajectory_full_text, re.IGNORECASE)
```

### Canonical example
**case_156** (JVMChaos ts-order-service): 52-round trajectory; zero SQL filters by `service_name='ts-order-service'`. Agent aggregated error counts, picked the loudest, wrote seat-service as root. The GT was mentioned only in a GROUP BY result row. **case_283, case_315** also hit this.

### Members (63)
156, 283, 315, 339, 341, 572, 755, 762, 804, 864, 1004, 1114, 1140, 1159, 1218, 1394, 1421, 1459, 1484, 1837, 1875, 1880, 2130, 2231, 2235, 2245, 2258, 2489, 2512, 2641, 2647, 2678, 2694, 2697, 2715, 2716, 2988, 3033, 3040, 3041, 3053, 3076, 3128, 3159, 3222, 3324, 3391, 3555, 3622, 3700, 3760, 3776, 3868, 4054, 4081, 4229, 4353, 4375, 4423, 4463, 4510, 4517, 4789

---

## PD5_FinalRCNotGroundedByProbe

**Scope**: core

### Self-check
- **Q1**: "final RC not grounded by probe" — action (probing the named RC) never happened. No reasoning verb. Pass.
- **Q2**: Predicate on whether SQL filters mention the RC; not on data being silent/noisy. Pass.

### Definition
The service name(s) the agent placed in `root_causes` of its final JSON answer never appear as a WHERE-service-name filter anywhere in the trajectory. The final conclusion was emitted without ever targeted-probing the named culprit.

### Positive criteria
For each service `rc` in `final_answer.root_causes[*].component`:
- `count(SQL with WHERE service_name='<rc>') == 0` → PD5 fires.
Fires if any one final_rc is ungrounded.

### Negative criteria
- If final_rcs is empty, PD5 does not fire.
- If `rc` appears ONLY in a GROUP BY result table but never in a WHERE filter, PD5 fires (grouping is not targeted probing).

### Detection signals
```python
for rc in final_answer.get("root_causes", []):
    name = rc.get("component")
    if name and not re.search(rf"service_name\s*=\s*'{re.escape(name)}'", trajectory_text, re.IGNORECASE):
        PD5_fires = True
        break
```

### Canonical example
**case_2231** (HTTPRequestDelay on ts-travel → ts-route): agent emitted `root_causes=[ts-basic-service]` in round 38 final JSON, yet `WHERE service_name='ts-basic-service'` filter appears zero times in any of the 61-round trajectory's SQL. ts-basic-service was named from error-count aggregations only. Similar: **case_2130** (final RC ts-route-service, ungrounded by any service-filter probe), **case_1880** (final RC ts-train-food-service, never probed by name).

### Members (13)
323, 339, 1118, 1159, 1280, 1686, 1837, 1862, 2512, 3622, 3716, 3966, 4229

---

## PD6_CallTreeAbsentOrShallow

**Scope**: core

### Self-check
- **Q1**: "never issued call_tree_build" — intent absence. No reasoning verb. Pass.
- **Q2**: Counts a specific intent's occurrence, not data span properties. Pass.

### Definition
Agent issued **zero** `call_tree_build` intents (no multi-hop parent_span_id recursive join over traces), OR issued ≤1 `call_tree_build` intent across the full trajectory. The agent did not reconstruct the multi-hop causal chain from trace parent/child links.

### Positive criteria
`count(intent=="call_tree_build") <= 1`.

### Negative criteria
- Running `trace_follow` on a single trace_id without recursive parent expansion is not `call_tree_build`.
- If `call_tree_build` fired ≥2 times, PD6 does not fire, regardless of depth reached.

### Detection signals
```python
n_ct = sum(1 for i in intents if i["intent"] == "call_tree_build")
PD6_fires = n_ct <= 1
```

### Canonical example
**case_281** (station-food JVMMemoryStress): 52 rounds, **zero** call_tree_build SQL. Agent only ran `service_trace_scan` (flat service-level counts) and `trace_follow` (single-trace walks). No WITH RECURSIVE or self-join for parent-child expansion. Result: fan-out chain food → station-food was flipped (called positioned as parent). **case_1004, case_2489** also have zero call_tree_build.

### Members (43)
281, 551, 762, 807, 864, 1004, 1118, 1143, 1144, 1195, 1814, 1837, 1862, 1880, 1886, 1948, 2211, 2258, 2390, 2489, 2512, 2585, 2647, 2694, 2716, 3033, 3035, 3050, 3076, 3222, 3716, 3776, 3920, 3966, 4054, 4229, 4363, 4375, 4517, 4789, 4791, 4823, 4832

---

## Cross-class guard rail

- **No PD should co-occur with any R-theme at >90%**. Max observed: PD5 ↔ T2_BaselineNoiseAnchored = 85% (11/13). Rationale: hallucinated-RC cases are strongly attracted to baseline-noise themes because "the service I invented is the one that dominates the loud noise". Still mechanism-distinct: PD5 describes an action omission, T2 describes a reasoning anchor.
- **No PD ⊂ another PD**. PD1 ∩ PD6 = 77% is the highest pair (agents that don't run contrast also often don't build call trees), but distinct actions on distinct intents.
- **HTTPFault** cases are excluded from PD2 (no single expected metric layer for HTTP-level faults).

---

## Summary table

| Class | Density (of 103) | Scope |
|-------|------------------|-------|
| PD1_BaselineCollectedNotContrasted | 78 (76%) | core |
| PD4_GTServiceNotTargetedWithWhere | 63 (61%) | core |
| PD2_FaultLayerMetricProbeSkipped | 45 (44%) | core |
| PD6_CallTreeAbsentOrShallow | 43 (42%) | core |
| PD3_TriageLoopWithoutDrill | 35 (34%) | core |
| PD5_FinalRCNotGroundedByProbe | 13 (13%) | core |

Cases with empty PD list: **0** (these cases fail purely via R/D mechanisms with no process-side omission detected).
