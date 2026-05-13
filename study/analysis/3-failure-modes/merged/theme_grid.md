# Theme Grid — Pairwise R-class Relationship Matrix (4 Frameworks)

4×4 matrix of cross-framework theme relationships. Rows and columns indexed by the 4 frameworks. Each off-diagonal cell lists the R-pairs across those two frameworks and tags the relationship as one of: `identical` (same mechanism, same scope), `overlap` (partial mechanism match), `subset/superset` (one contains the other), `orthogonal` (no mechanism overlap), `unique` (no counterpart in the other framework). Diagonal cells describe intra-framework theme structure.

Legend for relationship tags:
- **identical**: mechanism definition and case scope converge (both define the same reasoning defect, both trigger on the same fault-class signatures)
- **overlap**: mechanism definitions share ≥60% criteria but one framework's class is broader or narrower on some dimension
- **subset** / **superset**: one framework's class is strictly contained in the other's scope
- **orthogonal**: mechanisms address different defect axes; no case-level overlap expected
- **unique**: the per-agent R class has no counterpart in the paired framework (the paired framework either absorbs these cases into another class or does not produce this failure mode)

Framework abbreviations: **A** = aiq-qwen3.5-plus, **C** = claudecode-qwen3.5-plus, **S** = thinkdepthai-claude-sonnet-4.6, **Q** = thinkdepthai-qwen3.5-plus.

---

## Diagonal — intra-framework theme structure

### A × A (aiq-qwen3.5-plus, 8 classes, 113 cases)
Class topology: 3 classes in the silent-victim/loudness cluster (R_volume_anchor 24 + R_upstream_stop 16 + R_silent_fault_blind 15 = 55 cases, 48.7%), 1 chronic-noise class (R_baseline_unchecked 17, 15.0%), 1 hub-fabrication (R_hub_fabrication 12, 10.6%), 1 name-twin (R_name_twin 8, analytical), and 2 framework-architectural classes (R_correct_then_reversed 13 + R_compress_drift 8 = 21 cases, 18.6%). Unique structural feature: the 3 silent-victim sub-classes are distinguished by *which surrogate* the agent picks (caller-surrogate vs downstream-volume vs default-when-no-anchor), a granularity other frameworks did not split.

### C × C (claudecode-qwen3.5-plus, 7 classes, 102 cases)
Class topology: 1 silent-shadow class (R1, 29 cases, 28.4%), 2 chronic-noise variants (R2_RabbitMQ 24 + R3_nonRabbitMQ 11 = 35 cases, 34.3%), 1 edge-inversion (R4, 17 cases, 16.7%), 1 name-twin (R5, 10 cases, 9.8%), 2 infra-layer mis-handling (R6 7 + R7 4 = 11, 10.8%). Unique structural feature: explicit split of chronic-noise into RabbitMQ-specific (R2) vs non-RabbitMQ (R3), and explicit recognition of the "HikariCP misread as mysql" pattern (R7). Highest share of edge-inversion cases among the frameworks that track it.

### S × S (thinkdepthai-claude-sonnet-4.6, 7 classes, 50 cases)
Class topology: 1 edge-direction dominant (R_EdgeDirectionDefault 19, 38.0%), 1 downstream-leaf (R_DownstreamLeafAnchor 12, 24.0%), 1 chronic-noise (R_ChronicNoiseAsActiveFault 7, 14.0%), 1 oscillation (R_Oscillation 4, 8.0%), 3 small long-tail (R_Narrative 3, R_RestartDirection 3, R_SilencePaused 2). Unique structural feature: highest share of edge-inversion in the cohort (38%) — sonnet's long-horizon ReAct loop gravitates toward graph-synthesis errors more than anchor-selection errors. Oscillation class (4 cases) is unique to sonnet — a multi-RC-compromise output mode unobserved elsewhere.

### Q × Q (thinkdepthai-qwen3.5-plus, 7 classes, 105 cases)
Class topology: 1 downstream-caller-blamed (R_B, 32 cases, 30.5%), 1 ambient-noise (R_C, 26 cases, 24.8%), 1 silent-as-healthy (R_A, 15 cases, 14.3%), 1 amplitude-greed (R_D, 12 cases, 11.4%), 1 causal-inversion-mixed (R_G, 9 cases, 8.6%), 1 path-overshoot (R_E, 6 cases, 5.7%), 1 query-design (R_F, 5 cases, 4.8%). Unique structural feature: explicit R_A class isolating health-inference-from-silence (15 cases) that sonnet barely sees (2 cases) and aiq/claudecode absorb into other classes. Also unique: R_F (query-design-buries-signal) isolating SQL-structural-defects from result-interpretation-defects.

---

## Off-diagonal cells (pairwise relationships)

### A × C (aiq ↔ claudecode)

| aiq class | claudecode class | relationship |
|---|---|---|
| R_volume_anchor (24) + R_upstream_stop (16) + R_silent_fault_blind (15) | R1_SilentOriginShadowedByNoisyNeighbor (29) | **superset (aiq) / subset (claudecode)**: aiq splits silent-victim/loudness into 3 sub-classes by surrogate type (volume-top vs caller-stop vs default-when-blind); claudecode merges them into R1 under a single silent-origin framing. Mechanism homogeneous; all 3 aiq classes and claudecode.R1 → unified U1. |
| R_baseline_unchecked (17) | R2_ChronicInfraNoiseAnchored_RabbitMQDNS (24) | **identical on RabbitMQ variant**: both specifically enumerate RabbitMQ/food/delivery/notification as chronic-noise carriers and trigger on absent baseline-vs-abnormal SQL. |
| R_baseline_unchecked (17) | R3_FabricatedAncestorOrBaselineLog (11) | **overlap**: R3's "non-RabbitMQ baseline-noise" sub-variant (ORM NonUniqueResult, etc.) maps to aiq.R_baseline_unchecked mechanism; R3's "fabricated ancestor" sub-variant is closer to aiq.R_hub_fabrication. |
| R_hub_fabrication (12) | R3_FabricatedAncestorOrBaselineLog (partial, 11) | **partial overlap**: R3's (a) fabricated-ancestor cases share the "final RC ∉ S_observed" signature; however R3 is dominantly baseline-noise and per MECE maps to U2, so R_hub_fabrication stays framework-specific. |
| R_name_twin_confusion (8, analytical) | R5_SimilarNameSiblingConfused (10) | **identical**: both enumerate the same TrainTicket name-twin pairs (food/station-food, payment/inside-payment, order/order-other, route/route-plan, consign/consign-price) as the defect target. aiq's trigger is analytical_only; claudecode's is non-analytical (SLO path disambiguation). |
| R_correct_then_reversed (13) | — | **unique (A)**: multi-stage-pipeline-architectural. Claudecode's single-pass Bash+DuckDB loop has no refine stage. |
| R_compress_drift (8) | — | **unique (A)**: aiq's compress_to_graph LLM call has no claudecode analog. |
| — | R6_InfraLayerSkipped (7, analytical) | **unique (C)**: no aiq analog; aiq's silent-fault-blind absorbs similar "no metric probe" cases but under U1 framing, not infra-specific. |
| — | R7_JVMSymptomMisreadAsDB (4) | **unique (C)**: HikariCP-misread pattern not isolated by aiq. |

### A × S (aiq ↔ sonnet)

| aiq class | sonnet class | relationship |
|---|---|---|
| R_volume_anchor (24) + R_silent_fault_blind (15) | R_DownstreamLeafAnchor (12) | **overlap**: aiq's "picks top error-volume regardless of direction" and sonnet's "drills to slowest leaf" share the loudness-beats-intrinsic-slowness defect. Both → U1. Sonnet's class centers on latency-trace-backward cases; aiq's on log-error-volume cases. |
| R_upstream_stop (16) | R_DownstreamLeafAnchor (12) | **orthogonal**: aiq.R_upstream_stop picks UPSTREAM caller of GT; sonnet.R_DownstreamLeafAnchor picks DOWNSTREAM leaf beyond GT. Both merged into U1 but via different surrogate-picking mechanisms. |
| R_upstream_stop (16) | R_EdgeDirectionDefault (19) | **overlap**: both involve "correct region, wrong endpoint" but aiq.R_upstream_stop is specifically 1-hop-upstream-of-GT while sonnet.R_EdgeDirectionDefault is any non-{A,B} endpoint in region. |
| R_baseline_unchecked (17) | R_ChronicNoiseAsActiveFault (7) | **identical**: both define the defect as "no normal_logs cross-check" and target RabbitMQ/food cluster. |
| R_name_twin_confusion (8, analytical) | — | **unique (A)**: sonnet absorbs name-twin into R_EdgeDirectionDefault's "near-twin sibling" sub-variant rather than splitting it out. |
| R_hub_fabrication (12) | — | **unique (A)**: sonnet does not enumerate a "hallucinated service never appears in queries" class; such cases likely fall into sonnet.R_EdgeDirectionDefault or R_NarrativeOverMatchedMagnitude. |
| R_correct_then_reversed (13) | — | **unique (A)**: no refinement stage in sonnet. |
| R_compress_drift (8) | — | **unique (A)**: no compress layer in sonnet. |
| — | R_OscillationToCompromisePair (4) | **unique (S)**: sonnet's ReAct loop produces multi-RC outputs; aiq's compress-to-single-RC architecture forecloses this mode. |
| — | R_NarrativeOverMatchedMagnitude (3, analytical) | **unique (S)**: infrastructure-level multi-hop narrative construction is a sonnet-long-horizon behavior. |
| — | R_RestartWindowDirectionInversion (3) | **unique (S)**: pod-kill-edge direction inversion not isolated in aiq induction (likely absorbed into R_upstream_stop or R_hub_fabrication). |
| — | R_SilenceMisreadAsPaused (2) | **unique (S)** vs aiq — but **overlap** with qwen.R_A. |

### A × Q (aiq ↔ qwen)

| aiq class | qwen class | relationship |
|---|---|---|
| R_volume_anchor (24) | R_B_DownstreamMessengerBlamed (32) | **overlap**: aiq's top-error-volume picking and qwen's "downstream caller blamed" share the loudness-anchor mechanism. Qwen.R_B specifically requires caller-of-GT; aiq.R_volume_anchor is direction-agnostic. |
| R_volume_anchor (24) | R_D_AmplitudeGreedWrongService (12) | **overlap**: both defined as "biggest-absolute-number wins". Qwen.R_D explicitly disambiguates from qwen.R_B by boundary "R_D is magnitude-based regardless of direction". aiq.R_volume_anchor pattern closer to R_D than R_B. |
| R_upstream_stop (16) | R_B_DownstreamMessengerBlamed (32) | **identical on caller-of-GT subset**: qwen.R_B's definition explicitly includes "one hop further up the dependency graph" as the missing step. aiq.R_upstream_stop's mechanism matches. |
| R_silent_fault_blind (15) | R_B (32) + R_A (15) | **overlap**: aiq's "no loud anchor → default to visible" splits in qwen into R_B (blame visible caller) vs R_A (explicit health inference). Both downstream-of-aiq-silent-fault-blind mechanisms. |
| R_baseline_unchecked (17) | R_C_AmbientNoiseAnchor (26) | **identical**: both defined as anchor on errors present in both normal and abnormal windows; both enumerate RabbitMQ cluster + non-RabbitMQ baseline noise. |
| R_name_twin_confusion (8, analytical) | — | **unique (A)**: qwen does not split name-twin (absorbed into R_B or R_G). |
| R_hub_fabrication (12) | R_G_CausalInversionOrFabrication (9, partial) | **overlap (weak)**: qwen.R_G's (e) "narrative-choice diversion" sub-pattern occasionally produces fabricated-hub outputs, but R_G's dominant mechanism is caller-callee reversal. |
| R_correct_then_reversed (13) | — | **unique (A)**: qwen is single-pass ReAct, no refinement. |
| R_compress_drift (8) | — | **unique (A)**: no compress layer in qwen. |
| — | R_A_SilentSourceReadAsHealthy (15) | **unique (Q)** vs aiq — aiq's R_silent_fault_blind covers blindness-to-silence-as-fault-source, but not explicit health-inference-from-silence. |
| — | R_E_PathOvershootPastInjection (6) | **unique (Q)**: aiq does not enumerate direction-correct-distance-wrong cases (absorbed in R_upstream_stop as overshoot variants). |
| — | R_F_QueryDesignBuriesSignal (5) | **unique (Q)**: aiq does not separate query-structural-defects from result-interpretation-defects. |
| — | R_G_CausalInversionOrFabrication (9) | **overlap** with aiq.R_hub_fabrication on (e) narrative-diversion sub-pattern only. |

### C × S (claudecode ↔ sonnet)

| claudecode class | sonnet class | relationship |
|---|---|---|
| R1_SilentOriginShadowedByNoisyNeighbor (29) | R_DownstreamLeafAnchor (12) | **overlap**: both center on "silent injection target + agent picks loud surrogate". Claudecode.R1 is broader (picks caller OR sibling OR any loud service); sonnet.R_DownstreamLeafAnchor specifically picks downstream leaf. Both → U1. |
| R1 (29) | R_EdgeDirectionDefault (19) | **overlap**: some R1 cases where the agent keeps the correct node as child under a fabricated root look like R_EdgeDirectionDefault; disambiguation is based on whether the GT service appears in final output (R_EdgeDirectionDefault) or is absent (R1). |
| R2_ChronicInfraNoiseAnchored_RabbitMQDNS (24) + R3_FabricatedAncestorOrBaselineLog (11) | R_ChronicNoiseAsActiveFault (7) | **superset (C) / subset (S)**: both target rabbitmq-noise anchoring. Claudecode splits RabbitMQ-specific from non-RabbitMQ-baseline variants; sonnet does not split. All → U2. |
| R4_OutermostReceiverOrInvertedEdge (17) | R_EdgeDirectionDefault (19) | **identical**: both define the defect as "correct node identified, edge direction reversed, outermost ingress / region-sibling picked as root". Canonical examples in both track the same ui-dashboard-as-root pattern. |
| R4 (17) | R_RestartWindowDirectionInversion (3) | **subset (S) / superset (C)**: sonnet's restart-window is a specific sub-case of R4's direction inversion, namely during pod-kill windows. |
| R5_SimilarNameSiblingConfused (10) | R_EdgeDirectionDefault (partial, 19) | **overlap**: sonnet's R_EdgeDirectionDefault explicitly mentions "near-twin sibling" as a variant. Maybe 2-4 of sonnet's R_EdgeDirectionDefault cases would be R5 in claudecode's taxonomy. |
| R6_InfraLayerSkipped_AppLayerAnchored (7, analytical) | — | **unique (C)**: sonnet does not isolate app-vs-infra-layer-skip as its own defect (likely absorbed in R_DownstreamLeafAnchor when the leaf is app-layer). |
| R7_JVMSymptomMisreadAsDB (4) | — | **unique (C)**: sonnet does not isolate HikariCP-misread pattern. Possibly absorbed in R_NarrativeOverMatchedMagnitude as "mysql-narrative construction". |
| — | R_OscillationToCompromisePair (4) | **unique (S)**: claudecode commits to single RC (framework-architectural difference). |
| — | R_NarrativeOverMatchedMagnitude (3, analytical) | **unique (S)**: claudecode does not construct multi-hop narratives at sonnet's scale. |
| — | R_SilenceMisreadAsPaused (2) | **unique (S)** vs claudecode (but overlaps with qwen.R_A). |

### C × Q (claudecode ↔ qwen)

| claudecode class | qwen class | relationship |
|---|---|---|
| R1_SilentOriginShadowedByNoisyNeighbor (29) | R_B_DownstreamMessengerBlamed (32) | **identical**: both target silent injection + noisy-caller picking. Case lists largely converge on PodKill/JVM/ContainerKill faults. Both → U1. |
| R1 (29) | R_A_SilentSourceReadAsHealthy (15) | **overlap**: claudecode.R1 includes cases where agent silently moves past the silent service; qwen.R_A requires explicit health-inference reasoning. Qwen.R_A is narrower, more discriminated. |
| R1 (29) | R_D_AmplitudeGreedWrongService (12) | **overlap**: R1's "picks noisier neighbor" and R_D's "biggest magnitude wins" share the loudness anchor. Both → U1. |
| R2_ChronicInfraNoiseAnchored_RabbitMQDNS (24) + R3 (11) | R_C_AmbientNoiseAnchor (26) | **identical**: both define defect as anchor on chronic-noise signals; both enumerate RabbitMQ/food/notification + non-RabbitMQ-baseline. Qwen does not split the two; claudecode does. Both → U2. |
| R4_OutermostReceiverOrInvertedEdge (17) | R_G_CausalInversionOrFabrication (9) | **overlap**: qwen.R_G's (b) "caller-callee reversal" and R4's "edge direction reversed" share the mechanism. Qwen.R_G is broader (also includes symptom-as-cause, enum-misread). |
| R5_SimilarNameSiblingConfused (10) | — | **unique (C)**: qwen does not split name-twin; likely absorbed into R_B or R_D. |
| R6_InfraLayerSkipped (7, analytical) | R_F_QueryDesignBuriesSignal (5) | **overlap**: claudecode.R6 emphasizes missing queries on infra; qwen.R_F emphasizes mis-designed queries that dilute signal. Both about SQL-construction defects for infra signals, but different mechanisms — claudecode says "never ran it", qwen says "ran it wrong". Both kept framework-specific. |
| R7_JVMSymptomMisreadAsDB (4) | R_G_CausalInversionOrFabrication (partial, 9) | **overlap**: qwen.R_G's (a) "symptom-as-cause (MySQL Aborted connections)" sub-pattern is the R7 mechanism. Qwen.R_G mapped to U3 for dominant mechanism; R7 stays framework-specific. |
| — | R_E_PathOvershootPastInjection (6) | **unique (Q)**: claudecode does not enumerate direction-correct-distance-wrong cases explicitly (absorbed in R1 or R4). |

### S × Q (sonnet ↔ qwen)

This is the most informative pair — both run the same agent (thinkdepthai) with different models (Claude Sonnet 4.6 vs qwen3.5-plus). Differences here isolate model effects from framework effects.

| sonnet class | qwen class | relationship |
|---|---|---|
| R_EdgeDirectionDefault (19, 38%) | R_G_CausalInversionOrFabrication (9, 8.6%) | **overlap**: both cover caller-callee direction errors. Sonnet's class is 4.4× more prevalent — strong model effect (sonnet over-produces region-endpoint errors). |
| R_DownstreamLeafAnchor (12, 24%) | R_B (32, 30.5%) + R_D (12, 11.4%) + R_E (6, 5.7%) | **overlap**: sonnet's drill-to-leaf absorbs several qwen classes. Qwen's finer decomposition distinguishes magnitude-greed (R_D), caller-blamed (R_B), and overshoot (R_E). Sonnet does not split. |
| R_ChronicNoiseAsActiveFault (7, 14%) | R_C_AmbientNoiseAnchor (26, 24.8%) | **identical mechanism**, different prevalence. Qwen over-produces this 1.8× vs sonnet. |
| R_SilenceMisreadAsPaused (2, 4%) | R_A_SilentSourceReadAsHealthy (15, 14.3%) | **overlap** on the broader "silence → health/pause inference" mechanism. Qwen.R_A is 7.5× more prevalent — the strongest per-class model-effect observed. Qwen explicitly reasons "absence of error = health"; sonnet rarely does (2 cases). |
| R_OscillationToCompromisePair (4, 8%) | — | **unique (S)**: qwen commits to single RC. Sonnet's longer context + stronger hypothesis-generation → multi-RC compromise outputs. |
| R_NarrativeOverMatchedMagnitude (3, 6%) | — | **unique (S)**: multi-hop narrative construction is a sonnet behavior; qwen rarely builds this kind of infrastructure-level story. |
| R_RestartWindowDirectionInversion (3, 6%) | — | **unique (S)**: qwen does not isolate this; absorbed into R_B or R_G. |
| — | R_F_QueryDesignBuriesSignal (5, 4.8%) | **unique (Q)**: sonnet's query design is generally more careful; qwen produces heterogeneous-unit ORDER BY, AVG dilution errors that sonnet does not. |

**Summary of model-effect signals (S vs Q)**:
- Sonnet dominates: edge-direction errors, oscillation, narrative construction (behaviors enabled by longer reasoning horizon).
- Qwen dominates: chronic-noise anchoring, silence-as-health, query-design-buries-signal, silent-victim-shadowing (behaviors reflecting shallower-reasoning / rushed-anchor-selection).
- This asymmetry is why the Priority Set is empty under strict model-robust (≤5pp) threshold: every mechanism has a model-skew.

---

## Cross-framework summary statistics

| Framework | Unique-to-framework R classes | Shared-with-≥2-others | % failures in framework-specific |
|---|---:|---:|---:|
| aiq | 3 (R_hub, R_correct_reversed, R_compress) | 5 (U1 via 3 classes, U2, U4) | 29.2% (33/113) |
| claudecode | 2 (R6, R7) | 5 (U1, U2 via 2 classes, U3, U4) | 10.8% (11/102) |
| sonnet | 2 (R_Oscillation, R_Narrative) | 5 (U1, U2, U3 via 2 classes, U5) | 14.0% (7/50) |
| qwen | 2 (R_E, R_F) | 5 (U1 via 3 classes, U2, U3, U5) | 10.5% (11/105) |

aiq has the highest framework-specific share (29.2%), driven by its multi-stage pipeline architecture (R_correct_reversed + R_compress_drift). The other three frameworks all sit around 10-14% framework-specific, indicating most failures are mechanism-convergent across frameworks even when prevalence shifts.

---

## Diagonal intra-framework observations

- **aiq's 3-way split of silent-victim cluster** (volume_anchor / upstream_stop / silent_fault_blind) is the finest-grained loudness-anchor taxonomy across the 4 frameworks. Phase D could consider back-porting this 3-way split into the unified U1 definition if per-model middleware variants benefit from finer triggers.

- **sonnet's edge-direction dominance (38% of failures)** is the highest single-class share across all frameworks. Sonnet's long-horizon ReAct loop produces more graph-synthesis errors than anchor-selection errors. Per-model middleware targeting sonnet should prioritize edge-orientation enforcement.

- **qwen's chronic-noise + silent-as-health share** (24.8% + 14.3% = 39.1%) indicates qwen's failure profile is shifted toward baseline-anchor and silence-misreading. Per-model middleware targeting qwen should prioritize baseline-diff SQL enforcement and silent-candidate explicit-probe rules.

- **claudecode's R6+R7 pair (11 cases, 10.8%)** is the only framework with infra-layer-specific defect classes. The Bash+DuckDB tool access (versus LangChain-structured tools in aiq / sonnet / qwen) enables claudecode to query any parquet column, so infra-layer defects are reasoning rather than tool-access defects — making them valid R (not F).
