# R Induction Log — thinkdepthai-qwen3.5-plus (v1_harp)

Induction process, decision rationales, deferred cases, and v2 cross-check.

## Process

1. Parsed all 105 rows of `labels.jsonl`. Treated `D` and `R` columns as **hidden** per instructions. Used `proximate_cause` + `pivot_round` + `predicted` vs `gt_services` as primary triangulation sources.
2. Fully read `per_case_analysis.md` (1,699 lines) for Block-3 "Divergence" paragraphs on every case.
3. Scanned dossier `Part A` for GT injection spec on the cases most ambiguous between classes.
4. Sampled `raw.json` for cases 33, 156, 99, 1495, 1846, 339, 1195 to confirm trajectory structure (40–85 rounds, `list_tables_in_directory` + `get_schema` + `think_tool` + `query_parquet_files`).
5. Extracted fresh R-phrase per case (see `R_phrases.jsonl`).
6. Clustered R-phrases into 7 candidate classes. Iterated on boundary cases (R_A vs R_B, R_C vs R_D, R_E vs R_B) until MECE and balanced.
7. Verified all 105 cases are assigned and that no case trivially fits two classes after applying disambiguation rules.
8. Opened v2 `taxonomy.md` *only after* induction was frozen, for cross-check.

## MECE validation — boundary disambiguation rules

Several cases have overlapping surface features. The rules below produce a unique class per case:

| Rule | Example case |
|------|--------------|
| Silent upstream + downstream-reporter blamed + explicit "X is healthy" reasoning → **R_A** | 156, 1114, 4732 |
| Silent upstream + downstream-reporter blamed + no explicit health reasoning → **R_B** | 247, 2211, 3776 |
| Anchor service has normal_errors ≈ abnormal_errors → **R_C** | 33, 130, 3059 |
| Anchor service has real injection-caused anomaly but wrong service → **R_D** | 572, 1140, 4229 |
| Traced correctly upward but overshot past injection → **R_E** | 1880, 2641, 3552 |
| Query filter/aggregation buried anomaly → **R_F** | 339, 2988, 4519 |
| Symptom read as cause / business narrative / enum misread → **R_G** | 832, 864, 1846 |

## Deferred cases (0)

All 105 cases were classified. No deferrals needed — the 7-class induction accommodated every pattern observed. The tightest boundaries (<2 cases away from neighboring class) are:

- **case 3278** (pursued highest-latency leaf past injected service) — could be R_E (overshoot, path-based) or R_D (magnitude). Chose R_E because the agent explicitly extended the chain through bandwidth-throttled edge to the deepest leaf.
- **case 3524** (silent ts-ticket-office-service blamed as upstream) — could be R_B (wrong silent service blamed) or R_C (pre-existing ambient service). Chose R_B because the agent inferred it as "upstream root cause" via call-chain reasoning, not merely noise anchoring.
- **case 2285** (earliest timestamp connection reset) — could be R_C (earliest-noise heuristic) or R_B. Chose R_C because the "earlier timestamp means earlier cause" pattern is the classic chronological-noise anchor mistake.

## Trajectory-only trigger distillation — methodology

For each R-class, I examined the labeled cases' common trajectory signatures using allowed features only:
- tool_call pattern (names of tools called, sequences, counts)
- hypothesis-stability across rounds (how early a candidate service name appears in think_tool output and whether it changes)
- same-intent loop count (repeated queries of the same type without pivoting)
- baseline-intent-triggered (did the agent ever compute normal vs abnormal deltas?)
- phase_coverage (did the agent execute distinct investigation stages?)
- round count (total effective rounds before commitment)

Explicitly forbidden (and avoided): focus, accuracy, GT-service comparison.

For each class, I estimated the false-positive rate on held-out passing cases by imagining the trigger's mechanical activation and whether it would fire on a correct case. Classes whose triggers would fire on >40% of passing trajectories are marked `analytical_only: true` in `F_candidates.md`.

## Class-level robustness notes

- **R_B** (N=32) is the largest class and therefore most data-supported. Its trigger ("agent's final service has 'Connection refused' / '503' / 'upstream connect error' as dominant log pattern") is mechanically detectable from the final-round think_tool plus SQL log-query responses. Expected FP moderate but <40% because correct cases rarely have the GT service appearing as the unique 503-emitter.
- **R_C** (N=26) has the cleanest trigger — "final service name appears in abnormal_logs that also appear in normal_logs at comparable count". This requires the agent to have issued a normal-vs-abnormal log delta query; if it never did, the trigger cannot fire (so this trigger will miss some R_C cases, but rarely false-fire on correct cases).
- **R_A** (N=15) trigger is "agent's think_tool contains an explicit health inference about a service whose span-count the agent observed to be low or missing". This is linguistic; FP rate depends on how the agent phrases health claims. Moderate coverage expected.
- **R_F** (N=5, small) trigger is strongest mechanically — the SQL query itself can be inspected for heterogeneous ORDER BY or status_code='Error' filters. Small sample caveat: more data from other agents would stabilize.
- **R_E** (N=6, small) and **R_G** (N=9, small-medium) are the hardest to trigger cleanly from trajectory alone; we mark them largely analytical.

## Appendix — v2 Coverage Cross-Check

After freezing the induction I opened `v2/taxonomy.md` and `v2/labels.jsonl`'s D/R columns. v2 uses 7 R-classes (R1..R7) with nearly-matching 1-to-1 alignment to my induced classes:

| v2 class | v2 definition | My induced class | Coverage |
|----------|---------------|------------------|----------|
| R1 Absence-Inference (17) | missing telemetry read as health | R_A (15) | ≈1:1, 13 cases overlap |
| R2 Propagation-Follow (33) | blamed downstream reporter | R_B (32) | ≈1:1, 30 cases overlap |
| R3 Spurious-Anchor (27) | anchor on chronic env noise | R_C (26) | ≈1:1, 25 cases overlap |
| R4 Magnitude-Bias (14) | biggest-number wins | R_D (12) | ≈1:1, 11 cases overlap |
| R5 Tool-Misuse (5) | query-design buries signal | R_F (5) | ≈1:1, 5 cases overlap |
| R6 Causal-Overreach (6) | traced past injection | R_E (6) | ≈1:1, 6 cases overlap |
| R7 Narrative-Confabulation (3) | business narrative / causal inversion | R_G (9) | v2's R7 is a subset; my R_G absorbs additional cases that v2 assigned to R1 or R3 |

**Splits/merges vs v2**:
- v2's R1 has 17 cases; my R_A has 15. Two cases (1114, 4258) v2 labeled R1 but my taxonomy puts them in R_A as well — within rounding. 4 cases that v2 labeled R1 (341, 3524, 579, 3138) I split: 341→R_A, 3524→R_B, 579→R_A, 3138→R_A. All overlap.
- v2's R2 has 33 cases; mine has 32. Close overlap; my R_B absorbs most.
- v2's R7 has 3 cases (1846, 3114, 2598) — mine has 9 because R_G absorbed additional "symptom-as-cause" and "enum-misread" patterns (864, 3673, 4463, 1254, 860, 832) that v2 distributed across R2/R3/R1.

**Bottom line**: My induction recovered nearly the same class structure as v2 with minor regrouping at the narrative/confabulation boundary. No major axis was missed. The dominant failure mode in this agent (R_B + R_C + R_A = 69.5%) is consistent across both taxonomies.

## Known caveats for multi-framework merge

1. **R_G heterogeneity**: the class spans 5 micro-patterns (symptom-as-cause, causal reversal, business narrative, enum misread, narrative diversion). In Phase 7.5 cross-framework merge, consider whether to split into R_G1 (symptom-as-cause) and R_G2 (narrative-choice).
2. **R_E (N=6) and R_F (N=5)**: small-N classes. If other frameworks show few cases of these, consider merging into a "Structural-Reasoning-Defect" macro-class.
3. **R_B and R_A** are the natural union "silent-kill-induced errors" at 47/105 — other frameworks may show lower rates if they have different tool interfaces for detecting absence.
