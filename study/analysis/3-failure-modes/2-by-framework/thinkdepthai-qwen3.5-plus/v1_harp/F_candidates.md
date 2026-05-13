# F Candidates — thinkdepthai-qwen3.5-plus (v1_harp)

Trajectory-only trigger formulas per R-class. Each trigger uses only allowed features:
- tool_call pattern (names, sequences)
- hypothesis-stability across rounds (candidate service name mentioned in think_tool, and whether it changes)
- same-intent loop count (repeated queries of same schema)
- baseline-intent-triggered (did the agent query normal vs abnormal delta?)
- phase_coverage (distinct investigation stages visited)
- round count

Forbidden: GT comparison, accuracy, focus (GT/all services).

thinkdepthai tool fingerprint: `list_tables_in_directory` (1×), `get_schema` (1×), `think_tool` (4–12×), `query_parquet_files` (38–60×), final answer as last assistant message. Think_tool content is free-form — can be linguistically mined for hypothesis-stability.

---

## F_R_B — DownstreamMessengerBlamed (N=32)

**Trigger formula**:

```
Final-round think_tool OR final assistant message contains root-cause service X.
X is mentioned as subject of phrases matching:
  "{X} (has|had|shows|returned|emitted) (the most|highest) (errors|SEVERE|500|503|error spans)"
  OR "{X} is the (deepest|first) service (in the chain|showing) errors"
  OR "{X} cannot (connect|reach) (to|) {other_service}"
  OR "{X} is experiencing (connection refused|503|upstream connect error)"
AND any SQL response referenced in the last 10 rounds shows X's logs contain
"(Connection refused|upstream connect error|delayed connect error|503)" as dominant log pattern.
AND no think_tool entry after the first X-mention considers "(is the service {X} is trying to reach) down or restarting".
```

**Self-check FP rate**: ~25–35% (moderate). A correct case where the GT service itself emits Connection-refused logs (e.g., when a service legitimately fails while calling a reachable peer) would false-fire. But in RCA evals these are rare — correct cases usually have the GT emitting high-latency spans or stack-trace exceptions, not the downstream-reporter pattern.

**Detectability**: HIGH — mechanical regex on think_tool and SQL responses.

`analytical_only: false`

---

## F_R_C — AmbientNoiseAnchor (N=26)

**Trigger formula**:

```
Final answer identifies root cause as service X where X ∈ {ts-rabbitmq, ts-food-service,
  ts-delivery-service, ts-notification-service, ts-consign-service, ts-ticket-office-service,
  ts-config-service} AND the dominant evidence in the final think_tool is:
  "(UnknownHostException|AmqpConnectException|NonUniqueResultException|
    queue redeclaration|DNS resolution|container restart|GC pause)"
AND the agent DID NOT issue a SQL query comparing normal vs abnormal error counts
  for service X (no query referencing both the normal-period time window and abnormal-period time window,
  OR no query grouping by (service, period) on the log table).
AND X is NOT explicitly named in the incident description / augmented_question.
```

**Self-check FP rate**: ~15–25% (low-moderate). The whitelist of "chronic noise services" is very specific to this TrainTicket dataset. A correct case where ts-rabbitmq or ts-consign-service was the actual GT could false-fire, but those would need to be verified as injection-caused (with delta query, which the trigger already requires absence of).

**Detectability**: HIGH — final-service name intersected with chronic-noise set + absence of baseline-delta query.

`analytical_only: false`

---

## F_R_A — SilentSourceReadAsHealthy (N=15)

**Trigger formula**:

```
Any think_tool in rounds > round_count*0.5 contains the pattern:
  "{X} (shows|has|is) (Unset|no errors|0 errors|healthy|working fine|working correctly)"
  OR "{X} metrics (look healthy|are normal|show no anomaly)"
  OR "{X} (is NOT the problem|is not the issue)"
  OR "surviving (spans|traces) show (healthy|200 OK|successful)"
AND in the same case, at least one SQL response for span_count-by-service shows
  X has span_count << expected (X's abnormal span count < 0.1 × normal span count)
  OR X appears in an earlier SQL response with missing_span or injection_affected flag.
AND X is not the final selected root cause.
```

**Self-check FP rate**: ~20–30%. Agents sometimes correctly exonerate a peripheral service based on "no errors" without drawing the wrong overall conclusion. The trigger's conjunction with "X has missing_span or dramatic span-count drop" tightens this.

**Detectability**: MEDIUM-HIGH — linguistic pattern detection in think_tool plus SQL result inspection.

`analytical_only: false`

---

## F_R_D — AmplitudeGreedWrongService (N=12)

**Trigger formula**:

```
Final think_tool justification for root cause X explicitly cites an absolute-maximum
metric value, i.e. one of the patterns:
  "{X} has the (highest|most|largest) (error count|latency|duration|CPU|restart count|spans)"
  OR "(N) (errors|seconds|spans) in {X} — this is (the highest|extremely high)"
  OR "{X} at (N)s (is|was) the (biggest|largest|highest)"
AND the agent did NOT issue a normal-vs-abnormal delta query on metric M for service X.
AND the incident description endpoint prefix does NOT match X's endpoint prefix.
```

**Self-check FP rate**: ~30–40%. Magnitude citations are common in think_tool on correct cases too — the GT service often HAS the highest metric. The trigger relies on the "no baseline delta" conjunct, which is a soft filter. Borderline analytical_only.

**Detectability**: MEDIUM — explicit magnitude reasoning is detectable but common.

`analytical_only: false` (just barely — monitor FP rate with larger samples)

---

## F_R_G — CausalInversionOrFabrication (N=9)

**Trigger formula** (heuristic bundle):

```
Final answer X is reached via reasoning that contains ONE OR MORE of:
  (a) "(Aborted connection|Table doesn't exist|Order already exist|query did not return)
       → {X}" — app-layer symptom treated as cause
  (b) "{X} was (missing|not in traces) → {X} is (the upstream cause|unavailable)"
       paired with a different silent-service that has stronger metric signals
  (c) "(phase=2|container restart|deployment.available=0) → {X} is down"
       without inspecting whether that enum value persisted in the normal period
  (d) "Because {X} rejected (the order|the request), {upstream} retried"
       — business-logic chain built as root cause
```

**Self-check FP rate**: ~45–60%. The patterns are subtle and linguistic; a correct case with legitimate application-layer reasoning (e.g., actual "table doesn't exist" being the real problem) would false-fire. The 5 micro-patterns are not easily unified into a single discriminative trigger.

**Detectability**: LOW — patterns are linguistic and heterogeneous.

`analytical_only: true`

---

## F_R_E — PathOvershootPastInjection (N=6)

**Trigger formula**:

```
Think_tool output in final round contains a causal chain of the form
  "{upstream} → {mid} → {leaf}" with len(chain) ≥ 3
AND the final answer is leaf (the deepest service mentioned).
AND one or more intermediate services in the chain was at some point in earlier
think_tool flagged as "Error status", "slow", or "anomalous".
AND the agent explicitly says "(deeper|deepest|root is at the bottom|root is furthest down)"
OR "(let me check what {mid} calls)".
```

**Self-check FP rate**: ~35–50%. Tracing deeper is a legitimate RCA heuristic. Correct cases often end with the deepest anomalous service. The trigger is too weak to discriminate.

**Detectability**: LOW-MEDIUM — the "deeper = root" pattern is common in correct reasoning too.

`analytical_only: true`

---

## F_R_F — QueryDesignBuriesSignal (N=5)

**Trigger formula**:

```
Any SQL in the trajectory matches one of:
  (a) "ORDER BY (max_value|max|avg|value) DESC" without WHERE-clause filtering on metric name
      (i.e., a heterogeneous-metric query across metrics with different units)
  (b) "WHERE (attr_status_code|status_code) = 'Error'" as the primary filter
      on trace/span queries (excludes Unset-status injection_affected spans)
  (c) Service-level AVG(duration) without GROUP BY span_name
      (when the fault affects only specific span types)
AND the final answer misses a service that would have surfaced had the query been
    correctly scoped (hard to detect without GT; detectable via trajectory by
    noticing the query returned <30 rows but the agent then concluded without
    pivoting the query).
```

**Self-check FP rate**: ~20–30% for parts (a) and (b); part (c) is harder. Part (a) and (b) are mechanically detectable SQL patterns — correct agents sometimes use these filters too, but typically pivot after seeing the result. The key conjunct is "agent concluded without requerying", which is a trajectory-observable.

**Detectability**: MEDIUM-HIGH for SQL pattern parts; the "no requery" conjunct is easy.

`analytical_only: false`

---

## Summary

| Class | N | FP rate estimate | analytical_only | Detection difficulty |
|-------|--:|-----------------:|:---------------:|:--------------------:|
| R_B | 32 | 25–35% | false | easy |
| R_C | 26 | 15–25% | false | easy |
| R_A | 15 | 20–30% | false | medium |
| R_D | 12 | 30–40% | false | medium |
| R_F |  5 | 20–30% | false | medium |
| R_G |  9 | 45–60% | **true** | hard |
| R_E |  6 | 35–50% | **true** | hard |

**Middleware priority**: R_B + R_C + R_A (73 cases, 69.5% coverage, all with viable triggers) are the clear highest-ROI intervention targets.

---

## Framework-architectural F-candidates (likely empty)

Per instructions, thinkdepthai is a ReAct pipeline shared across qwen3.5-plus and claude-sonnet-4.6. qwen is the model-side variant. Framework-architectural failures (failures tied to thinkdepthai's ReAct/reflection/refine stages rather than to qwen's reasoning) are the candidates for F entries.

**Evaluation of each R class for framework-architectural mechanism**:

- **R_A, R_B, R_D, R_G**: these are reasoning defects of the LLM in any framework — model-side. No F candidate.
- **R_C (AmbientNoiseAnchor)**: is the "anchor on the loudest log" pattern structural to thinkdepthai? The framework does NOT have a reflection stage that re-evaluates anchors, which could argue it's framework-architectural. But the same pattern appears in AIQ and OpenRCA without reflection too — it's model-side. No F candidate.
- **R_E (PathOvershootPastInjection)**: the "deeper = root" pattern could plausibly be amplified by thinkdepthai's lack of injection-point awareness in its prompt template. But this is still LLM-reasoning driven. No F candidate.
- **R_F (QueryDesignBuriesSignal)**: the query-design failures are tied to how thinkdepthai surfaces the parquet schema — the agent gets schema via `get_schema` once and then assumes column semantics. The `status_code='Error'` filter mistake (missing Unset-status injection_affected spans) may be partially framework-architectural because the schema description in thinkdepthai's prompt emphasizes `status_code` as the primary health indicator. **Weak F candidate: R_F_sub_statuscode** — but the specific prompt content is model-driven and the error reasoning is too, so this is borderline. Not promoted.

**Conclusion**: No strong F candidates for thinkdepthai-qwen3.5-plus. The weak candidate R_F_sub_statuscode is documented here for cross-framework review but should not be added to `F_candidates`.

Expected: framework-architectural F candidates will emerge more clearly for agents with distinctive pipelines (aiq's reflection/compress stage, ClaudeCode's claude-code tooling) rather than for thinkdepthai's plain ReAct.
