# thinkdepthai-qwen3.5-plus — F_catalog.md (finalized per-framework architectural failures)

**Scope**: Failures produced by thinkdepthai's pipeline architecture (ReAct loop + reflection/refine stages) specific to qwen's reasoning behavior.

**Verdict**: **EMPTY**. No F-class failures identified.

**Share**: 0 / 105 = 0.0%.

---

## Candidates evaluated and rejected

The thinkdepthai-qwen3.5-plus framework is the same thinkdepthai ReAct + reflection pipeline as `thinkdepthai-claude-sonnet-4.6`. All 7 induced R classes (R_A..R_G) describe *model-side reasoning defects* in qwen's hypothesis-tracking, baseline comparison, and causal-chain reasoning — not pipeline-architectural issues.

**One weak candidate noted in Phase α**: a sub-pattern of R_F (QueryDesignBuriesSignal) where the agent filters SQL on `status_code='Error'` reinforced by schema description, burying the injection signal. This was evaluated as a reasoning defect (agent chose an over-narrow filter) rather than a framework constraint (the tool does not force this filter). **Not promoted to F.**

No cases of compress drift or refine-stage reversal at the architectural level — qwen's thinkdepthai pipeline uses single-pass ReAct termination + optional reflection, without the multi-stage refine layering that aiq has.

---

## Summary

No F entries. All 105 labeled failures are in the cross-framework `unified_R` set or the `qwen.*` framework-specific analytical_R appendix (R_E=6, R_F=5).

**Note**: qwen's 105 failures ARE the reason `unified_R` Priority Set is empty under strict 5pp model-robust threshold — qwen's higher failure volume and different failure distribution vs sonnet (same framework, different model) means every unified R exceeds the 5pp model-diff gate. This is a model-effect finding, not a framework-F failure.
