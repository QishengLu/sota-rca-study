# R_induction_log.md — thinkdepthai-claude-sonnet-4.6 (v1)

Sequential log of induction decisions.

## Inputs

- labels.jsonl: 51 rows (50 genuine + 1 dataset_anomaly).
- per_case_analysis.md: structured ## case_{dataset_index} sections covering all 51 cases.
- dossiers/case_*.md + raw.json: Part A GT + Part B trajectory for all cases (149 dossier files / 51 cases × ~3 each).

Model is Sonnet 4.6 with ReAct loop (`query_parquet_files`, `think_tool`, `list_tables_in_directory`, `get_schema`). Typical round count 20-70; typical token count 0.8M-5M.

## Phase α: D+R phrase extraction

Processed all 51 cases. Triangulated each via:
1. labels.jsonl `primary` + `secondary` + `proximate_cause` phrase
2. per_case_analysis.md case block: GT / Agent / Divergence / Proximate cause phrase
3. dossier Part A (injection.json + conclusion + causal_graph)

**Deferred cases**: 1
- case_4463 (dataset_anomaly): DB meta says `ts-config-service`, datapack name says `ts-food-service-container-kill`. Agent picked `ts-food-service` (consistent with datapack). This is a labeling mismatch, not an agent failure. D_phrase / R_phrase recorded but R_class = DEFERRED.

**Disagreements between labels.jsonl and per_case_analysis**: none. Both sources used the same T1-T8 schema and agreed on every primary assignment. Secondary tags (T5, T6 on 2541 etc.) were informational only.

## Phase β round 1: R-class clustering

Initial draft had 10 R classes including 3 singletons (R_CausalDirectionInversion, R_CategoryFilterBeforeEvidence, R_FaultTypeBlindLeafDrill). After MECE review:
- R_CausalDirectionInversion (case 471) merged into R_RestartWindowDirectionInversion: the swap from pod-kill to MySQL is a special case of restart-window causal inversion (the bigger-scope signal is the pod's own dying connections torn down from MySQL). Shared root-cause pattern: "correlated signal during restart window, picked the bigger scope".
- R_CategoryFilterBeforeEvidence (case 1140) merged into R_DownstreamLeafAnchor: the agent still drilled to a mid-stack leaf (seat-service CPU hotspot); the "refusal to consider frontend" is secondary to the drill-to-leaf reflex.
- R_FaultTypeBlindLeafDrill (case 1421) merged into R_DownstreamLeafAnchor: same drill-to-slowest-leaf reflex applied where no proper leaf exists. Dropping the "blind-to-fault-class" qualifier preserves the core defect shape.

Final class count: **7** (in range 5-10).

Class distribution (50 classified / 51 total):
- R_EdgeDirectionDefault: 19 (38%)
- R_DownstreamLeafAnchor: 12 (24%)
- R_ChronicNoiseAsActiveFault: 7 (14%)
- R_OscillationToCompromisePair: 4 (8%)
- R_NarrativeOverMatchedMagnitude: 3 (6%)
- R_RestartWindowDirectionInversion: 3 (6%)
- R_SilenceMisreadAsPaused: 2 (4%)

## Phase β round 1: trajectory-only trigger distillation

Inspected raw.json for 1 representative case per R class (9 total) to extract tool-call patterns.

Key observations driving trigger design:

- **All sonnet trajectories look structurally similar**: 20-70 `query_parquet_files` + 11-24 `think_tool` reflections + 1 schema discovery pair. Can't discriminate on tool identity.
- **Discriminators are semantic**: what tables are queried, what SQL patterns appear, what services are named in `think_tool` reflections, what lexical markers appear in reflections (e.g., "frozen", "PROCESS_PAUSED", "narrative", "cascade").
- **Hypothesis-oscillation measurement**: computed per-case by counting distinct ts-X service names mentioned in `think_tool` reflections that contain root-cause claims.
  - T6 (oscillation) cases: 339→14, 572→14, 2682→8, 2801→9.
  - T1-long cases (no oscillation, just deep drill): 2541→4, 3284→5, 4433→7.
  - T3/T2 typical short cases: 1144→9, 2715→7, 3493→6.
  - Clear separation between T6 (~10-14) and non-T6 (~4-7) at comparable round counts.
- **R_NarrativeOverMatchedMagnitude can only be diagnosed by lexical analysis** of `think_tool` reflection text ("contention", "cascade", "narrative", "explains", multi-hop bridging language). This is too subjective for reliable trigger firing → marked `analytical_only: true`.

FP-rate estimates came from cross-checking: for each trigger, count how many of the 51 cases would fire the trigger; divide by the number of true-class members. Estimates:

| R class | trigger | True-positive hits | Expected firings across 51 | FP rate |
|---|---|---|---|---|
| R_EdgeDirectionDefault | edge region + no caller-distribution check | 19/19 | ~27 | 30% |
| R_DownstreamLeafAnchor | progressive depth drill + no intrinsic-vs-prop check | 12/12 | ~16 | 25% |
| R_ChronicNoiseAsActiveFault | DNS log query + rabbitmq committed + no normal_logs | 7/7 | ~8 | 12% |
| R_OscillationToCompromisePair | >=40 rounds + >=6 distinct candidates + pair output | 4/4 | ~6 | 33% |
| R_NarrativeOverMatchedMagnitude | narrative lexical + late-appearance RC + earlier numerical match | 3/3 | ~5-6 | 50% → `analytical_only` |
| R_RestartWindowDirectionInversion | restart signal observed + not-committed + no window-specific check | 3/3 | ~4 | 25% |
| R_SilenceMisreadAsPaused | frozen/paused lexical + no inbound-check | 2/2 | ~2-3 | 15% |

R_NarrativeOverMatchedMagnitude exceeded the 40% FP ceiling → marked `analytical_only`. All others below threshold → trajectory-fireable.

## F candidate evaluation

Single F candidate examined: **T6 ExhaustionWithoutCommitment** — could be (a) ReAct-loop architectural failure where the framework never commits despite 40+ rounds, OR (b) reasoning defect where the agent could commit but chooses to oscillate.

Evidence favoring (b) reasoning-defect interpretation:
1. T1 cases 2541 (62 rounds), 3284 (58 rounds), 4433 (70 rounds) exceed T6's typical 40-round threshold yet commit to **single** RC with narrow hypothesis space (4-7 distinct services mentioned).
2. T6 cases oscillate with hypothesis-breadth 8-14 distinct services in root-cause claims, showing the agent is actively entertaining many candidates rather than being stuck in a framework loop.
3. The ReAct framework used here terminates on the model's own commitment signal — there is no architectural forcing toward a pair-RC output. The pair-RC at the end is an agent choice (the model writes "Root Cause: X and Y") not a framework-imposed format.
4. Cases 2682 (30 rounds) and 2801 (47 rounds) also commit to compromise pairs despite not reaching extreme round counts — the oscillation-to-pair behavior is decoupled from round exhaustion.

Decision: **T6 stays in R as R_OscillationToCompromisePair.** It is a reasoning/commitment defect, not a framework architectural failure. No F1 for sonnet from T6. See `F_candidates.md` for detail.

## MECE verification

Each of 50 classified cases has exactly one R_class. Edge-case reassignments (previously dual-tagged in labels.jsonl secondary column) documented in R_inductive.md bottom section.

## Gate risks

1. **R_EdgeDirectionDefault trigger FP rate near 30%**: boundary acceptable but not comfortable. The "no caller-distribution check" signal is weak because many trajectories never issue that particular SQL even when the agent correctly localizes. Consider strengthening in v2 iteration.
2. **R_NarrativeOverMatchedMagnitude is analytical-only**: cannot fire at inference time. 3 cases (6%) escape runtime intervention by this path.
3. **Small per-class counts for R_SilenceMisreadAsPaused (2) and R_RestartWindowDirectionInversion (3)** — statistical thin ice but each has tight diagnostic triggers so intervention precision should hold despite small-N.
4. **Sonnet is the strongest model (AC@1 89.8%)** — the 51 failure set is small (10% of 500) and the classes may under-represent modes that qwen/claudecode/aiq expose at higher volume. Cross-framework merge will surface these.
5. **No dataset_anomaly secondary sweep**: only case 4463 flagged. Worth re-examining high-confidence wrong-answer cases in merge step to catch any other label errors.

## Output files

- R_phrases.jsonl — 51 rows
- merged/D_phrases_sonnet.jsonl — 51 rows with agent="sonnet" tag
- R_inductive.md — 7 R-class definitions + triggers
- F_candidates.md — T6 → R decision
- R_induction_log.md (this file)
