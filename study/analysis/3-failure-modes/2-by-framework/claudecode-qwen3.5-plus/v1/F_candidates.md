# F-candidates — claudecode-qwen3.5-plus round 1

This document records framework-level (F) vs reasoning-level (R) candidates identified during inductive round 1.

Per the gate spec: F class = architectural constraint of the framework that makes a failure inevitable or nearly so, independent of reasoning quality. R class = reasoning defect that a better-reasoning agent on the same framework could avoid.

---

## F candidate #1: T4 InfraLayerSkipped — **VERDICT: KEEP IN R (→ R6)**

### The question
Does Claude Code's file-read / Bash / DuckDB tool layer architecturally prevent infra-layer queries (mysql metrics / JVM introspection / network counters), forcing the agent to stop at app layer?

### Evidence from dossier case_283 (NetworkBandwidth on station-service → mysql)

Trajectory rounds 15, 27 demonstrate that Claude Code CAN query any parquet column without restriction:

**Round 15** issued:
```sql
SELECT metric, service_name, AVG(value) as avg_val, MAX(value) as max_val
FROM 'abnormal_metrics.parquet'
WHERE metric LIKE '%latency%' OR metric LIKE '%duration%' OR metric LIKE '%http%'
GROUP BY metric, service_name
HAVING AVG(value) > 0 AND NOT ISNAN(AVG(value))
ORDER BY avg_val DESC
LIMIT 25;
```
→ Got 25 rows including travel2/p99 1.37s, seat/p99 0.90s, station-service/p99 0.62s, ui-dashboard/p95 0.52s. Latency data was fully accessible.

**Round 27** issued:
```sql
SELECT metric, service_name, AVG(value) as avg_val, MAX(value) as max_val
FROM 'abnormal_metrics.parquet'
WHERE metric LIKE '%db%' OR metric LIKE '%database%' OR metric LIKE '%mysql%' OR metric LIKE '%connection%'
GROUP BY metric, service_name
HAVING AVG(value) > 0 AND NOT ISNAN(AVG(value))
ORDER BY service_name, avg_val DESC
LIMIT 20;
```
→ 0 rows returned. NOT because Bash/DuckDB can't read mysql data, but because the dataset does not use those keyword names for its mysql-related metrics. The agent could have:
- Queried span_name LIKE '%mysql%' on abnormal_traces
- Queried per-span duration by parent_service_name='ts-station-service' and child span_name pattern
- Queried egress-bytes / ingress-bytes counters (if available)
- Examined abnormal_traces where parent_service was station-service and child was mysql

None of these were attempted. The agent's reasoning simply concluded "no DB issues visible" and stayed at app layer.

### Verdict: T4 is a **reasoning defect (R6)**, NOT an architectural constraint.

Bash+DuckDB gives unrestricted access to all 10 parquet files. The failure is "agent doesn't know how to formulate granular per-span / per-link / per-byte-counter queries", not "Claude Code can't access infra data". A smarter prompt or self-reflection mechanism could change this behavior within the current tool layer.

**Action**: Keep R6 as a reasoning R-class. No F1 demotion.

Members (same as R6): 283, 339, 1421, 2678, 2715, 3222, 4423 (7 cases, 6.8%).

---

## F candidate #2: Compress-phase overwriting correct reasoning — **VERDICT: NOT A FACTOR**

### The question
Claude Code has a compress LLM phase that extracts final JSON from the Claude Code trajectory. Does this phase ever overwrite correct mid-trajectory reasoning with a wrong root cause?

### Evidence
- None of the 103 per_case_analysis entries reference a compress/extract phase that flipped reasoning.
- In every case, final output's root_causes reflects the agent's last-round reasoning conclusion (agreed across all four verified dossiers: 283, 341, 807, 1195).
- In case_1280, the compress correctly captured the agent's contradictory final reasoning ("rabbitmq is pre-existing" earlier + "include rabbitmq as co-root" later) — that is a reasoning inconsistency (R3), not a compress artifact.
- case_1837 has 0-round trajectory (minimal reasoning) with correct compress extraction of the shallow reasoning — framework behaved correctly.

### Verdict: compress is **not** currently contributing to any of the 103 failures. No F2 candidate.

---

## F candidate #3: Long trajectory degradation (>60 rounds) — **DEFERRED TO MERGE STEP**

### Observation
6 cases have >=60 rounds before arriving at a wrong answer:
- case_1495: 73 rounds (JVMMemoryStress on travel-plan) → R4
- case_3324: 82 rounds (PodChaos ContainerKill on travel) → R1
- case_4353: 62 rounds (JVMMemoryStress on station) → R1
- case_4832: 82 rounds (JVMMemoryStress on consign) → R7

These are all still classifiable as R-class defects (the final answer follows from reasoning, not tool-layer exhaustion). But the "long trajectory with entrenched wrong hypothesis" pattern may emerge as an F candidate when compared against other frameworks. Deferred to cross-framework merge step.

---

## Dataset-anomaly candidates (not F, but excluded from R)

### case_4463 — GT/injection-name mismatch (single occurrence)
- GT label: `ts-config-service`
- injection_name: `ts-food-service-container-kill`
- Agent output: root=ts-food-service (matches the injection footprint)
- Judge marked failure due to label mismatch — but the agent correctly identified the injected service.

**This is a dataset labeling inconsistency, not an agent defect.** Flagged for dataset-filter or data-cleaning at merge step.

---

## Summary of F decisions for round 1

| Candidate | Verdict | Notes |
|---|---|---|
| F1: T4 infra-layer as tool-layer constraint | **Rejected** → R6 | Bash+DuckDB has full parquet access; reasoning defect |
| F2: Compress phase overwriting reasoning | **Rejected** | Not observed in any of 103 cases |
| F3: Long-trajectory degradation | **Deferred** to merge | May emerge cross-framework |
| Dataset anomaly (case_4463) | **Excluded** from R | Single case, dataset-labeling issue |

Result: zero F classes introduced at round 1 for claudecode-qwen3.5-plus. All 102 non-dataset-anomaly failures remain R-class.
