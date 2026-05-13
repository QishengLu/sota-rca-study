# claudecode-qwen3.5-plus — F_catalog.md (finalized per-framework architectural failures)

**Scope**: Failures that (a) are uniquely produced by Claude Code's architecture (Bash / Read / Grep tool layer, compress phase) and (b) cannot be repaired by a general metacognitive middleware.

**Verdict**: **EMPTY**. No F-class failures identified.

**Share**: 0 / 103 = 0.0%.

---

## Candidates evaluated and rejected

### T4 InfraLayerSkipped → kept in R (mapped to `claudecode.R6_InfraLayerSkipped_AppLayerAnchored`, `analytical_only: true`)

**Question**: Does Claude Code's file-read / Bash / DuckDB tool layer architecturally prevent infra-layer queries (mysql metrics / JVM introspection / network counters), forcing the agent to stop at app layer?

**Evidence** (from dossier case_283 NetworkBandwidth on station-service→mysql trajectory):
- Round 15: `SELECT metric, service_name FROM 'abnormal_metrics.parquet' WHERE metric LIKE '%latency%'` returned 25 rows including p99/p95 latency metrics — **full column access confirmed**.
- Round 27: `SELECT ... WHERE metric LIKE '%mysql%' OR '%db%' OR '%connection%'` returned 0 rows — not because of tool restriction but because the dataset does not expose mysql metrics under those keyword names.

The agent could have formulated more granular per-span queries (filtering on `service_name = 'ts-station-service'` + latency percentiles). The tool layer did not block anything. The failure was reasoning-layer (keyword choice, query-design sophistication), not architectural.

**Conclusion**: R6 stays in R axis, flagged `analytical_only` at unified level (insufficient trajectory-only signal to distinguish from R2/R3/R4 at inference time).

### Compress-phase drift → rejected as F

Inspected all 103 cases: no evidence that Claude Code's result-extraction phase overwrote agent reasoning. Final outputs uniformly reflect last-round agent reasoning.

### Long-trajectory degradation (≥60 rounds, 4 cases) → deferred

Could be a framework-exhaustion artifact but insufficient cases to conclude. Noted here for future re-examination; not promoted to F in v1.

---

## Summary

No F entries. All 103 labeled failures are in the cross-framework `unified_R` set (96 cases across U1–U5) or the `claudecode.*` framework-specific analytical_R appendix (R6=7, R7=4, with 1 dataset_anomaly deferred).
