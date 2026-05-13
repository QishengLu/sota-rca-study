"""V-D: Generate verify_mismatch_report.md from verify_verdicts.jsonl.

Required sections (per plan):
1. Summary table per axis + per class + per framework bias check
2. Per-class action recommendation
3. Fabricated D obstacles
4. Misaligned R attribution
5. Redundant PD labels
6. Every dispute-strong case in detail
7. Unverifiable cases list
8. Red-zone PD re-evaluation (PD4_NamedCandidateNotIsolated, PD8_MultiRCCompromise)
9. V-E evidence-extraction accuracy check
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harp_config import MERGED

VERDICTS = Path(os.environ.get("VERIFY_VERDICTS_PATH", MERGED / "verify_verdicts.jsonl"))
SAMPLES = MERGED / "verify_samples.jsonl"
SPOTCHECK = MERGED / "verify_spot_check_report.json"
OUT = Path(os.environ.get("VERIFY_REPORT_PATH", MERGED / "verify_mismatch_report.md"))


def main():
    verdicts = []
    with VERDICTS.open() as f:
        for line in f:
            verdicts.append(json.loads(line))

    # ---------- Summary ----------
    axis_counts = defaultdict(Counter)
    class_counts = defaultdict(Counter)
    framework_counts = defaultdict(Counter)
    for v in verdicts:
        axis_counts[v["axis"]][v["verdict"]] += 1
        class_counts[v["class"]][v["verdict"]] += 1
        framework_counts[v["agent"]][v["verdict"]] += 1

    verdict_types = ["agree", "dispute-weak", "dispute-strong", "fabricated", "misaligned", "redundant", "unverifiable"]

    lines = []
    lines.append("# D / R / PD Label Re-Verification — Mismatch Report")
    lines.append("")
    lines.append(f"**Scope**: 4 frameworks × ALL labeled failure cases. Distinct cases verified: {_distinct_cases(verdicts)}. Class-verifications (D + R + multi-PD per case): {len(verdicts)}.")
    lines.append("**Method**: three-way alignment (GT side + trajectory side + counterfactual parquet simulation). `agree` requires all three tests pass.")
    lines.append("**Corpus**: all 372 cases from `D_projection.jsonl` + `PD_projection.jsonl` + DB `meta.failure_analysis.v1.R`.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Summary tables")
    lines.append("")
    lines.append("### 1.1 Per-axis verdict counts")
    lines.append("")
    lines.append("| Axis | " + " | ".join(verdict_types) + " | Total |")
    lines.append("|---|" + "|".join(["---:"] * (len(verdict_types) + 1)) + "|")
    for ax in ("D", "R", "PD"):
        c = axis_counts[ax]
        total = sum(c.values())
        row = [ax] + [str(c.get(v, 0)) for v in verdict_types] + [str(total)]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    lines.append("### 1.2 Per-class verdict breakdown")
    lines.append("")
    lines.append("| Class | " + " | ".join(verdict_types) + " | Total | Non-agree rate |")
    lines.append("|---|" + "|".join(["---:"] * (len(verdict_types) + 2)) + "|")
    for cls in sorted(class_counts.keys()):
        c = class_counts[cls]
        total = sum(c.values())
        non_agree = total - c.get("agree", 0)
        rate = f"{non_agree}/{total} ({round(100 * non_agree / max(total, 1))}%)"
        row = [cls] + [str(c.get(v, 0)) for v in verdict_types] + [str(total), rate]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    lines.append("### 1.3 Per-framework bias check")
    lines.append("")
    lines.append("| Framework | " + " | ".join(verdict_types) + " | Total | Non-agree % |")
    lines.append("|---|" + "|".join(["---:"] * (len(verdict_types) + 2)) + "|")
    for fw in sorted(framework_counts.keys()):
        c = framework_counts[fw]
        total = sum(c.values())
        non_agree = total - c.get("agree", 0)
        row = [fw] + [str(c.get(v, 0)) for v in verdict_types] + [str(total), f"{round(100 * non_agree / max(total, 1))}%"]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # ---------- Per-class action recommendation ----------
    lines.append("---")
    lines.append("")
    lines.append("## 2. Per-class action recommendation")
    lines.append("")
    lines.append("| Class | N | Non-agree | Action |")
    lines.append("|---|---:|---:|---|")
    for cls in sorted(class_counts.keys()):
        c = class_counts[cls]
        total = sum(c.values())
        non_agree = total - c.get("agree", 0)
        rate = non_agree / max(total, 1)
        # If class is dominated by unverifiable (>=80%), report separately
        unver = c.get("unverifiable", 0)
        if total >= 5 and unver / total >= 0.8:
            action = f"unverifiable-by-evidence-dump ({unver}/{total}) — needs trajectory-text analysis beyond parquet"
        elif total < 5:
            action = "small class; insufficient N for verdict"
        else:
            # exclude unverifiable from denominator when computing non-agree rate
            judged_total = total - unver
            judged_non_agree = non_agree - unver
            adj_rate = judged_non_agree / max(judged_total, 1)
            if adj_rate <= 0.20:
                action = f"OK (≤20% non-agree among judged; N_judged={judged_total})"
            elif adj_rate <= 0.40:
                action = f"review (20-40% non-agree; N_judged={judged_total})"
            elif adj_rate <= 0.60:
                action = f"significant label noise — targeted relabel pass recommended (N_judged={judged_total})"
            else:
                action = f"likely mis-induced — re-run Phase α (N_judged={judged_total})"

        # extra flag if ≥15% cases are fabricated/misaligned/redundant
        flagged_bad = c.get("fabricated", 0) + c.get("misaligned", 0) + c.get("redundant", 0)
        if total >= 5 and flagged_bad / max(total - unver, 1) >= 0.15:
            action += " — add 3-way alignment guard to Positive criteria"

        lines.append(f"| {cls} | {total} | {non_agree} | {action} |")
    lines.append("")

    # ---------- Diagnostic sub-sections ----------
    lines.append("---")
    lines.append("")
    lines.append("## 3. Fabricated D obstacles")
    lines.append("")
    lines.append("Cases where D label was claimed but agent never reached GT path (gt_touched=False AND gt_neighbors_touched=∅). The 'data obstacle' was never encountered — failure is on R/PD axis, not D.")
    lines.append("")
    fabricated = [v for v in verdicts if v["verdict"] == "fabricated"]
    if fabricated:
        lines.append("| Agent | Case | Class | Suggested alternative | Reason |")
        lines.append("|---|---|---|---|---|")
        for v in fabricated:
            lines.append(f"| {v['agent']} | {v['case_id']} | {v['class']} | {v.get('suggested_alternative_class','')} | {_esc(v['reason'])} |")
    else:
        lines.append("*(none detected)*")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 4. Misaligned R attribution")
    lines.append("")
    lines.append("Cases where R label was claimed but gt_required_capabilities suggests a different reasoning failure. The R's implied 'failed capability' doesn't match what the case actually required.")
    lines.append("")
    misaligned = [v for v in verdicts if v["verdict"] == "misaligned"]
    if misaligned:
        lines.append("| Agent | Case | Class | Suggested alternative | Reason |")
        lines.append("|---|---|---|---|---|")
        for v in misaligned:
            lines.append(f"| {v['agent']} | {v['case_id']} | {v['class']} | {v.get('suggested_alternative_class','')} | {_esc(v['reason'])} |")
    else:
        lines.append("*(none detected)*")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 5. Redundant PD labels")
    lines.append("")
    lines.append("Cases where PD was claimed but counterfactual shows the missing action would be a no-op. The action's precondition is absent (chronic noise absent for PD1, GT not upstream for PD2, etc.).")
    lines.append("")
    redundant = [v for v in verdicts if v["verdict"] == "redundant"]
    if redundant:
        lines.append("| Agent | Case | Class | Reason |")
        lines.append("|---|---|---|---|")
        for v in redundant:
            lines.append(f"| {v['agent']} | {v['case_id']} | {v['class']} | {_esc(v['reason'])} |")
    else:
        lines.append("*(none detected)*")
    lines.append("")

    # ---------- Dispute-strong details ----------
    lines.append("---")
    lines.append("")
    lines.append("## 6. Dispute-strong details")
    lines.append("")
    ds = [v for v in verdicts if v["verdict"] == "dispute-strong"]
    if not ds:
        lines.append("*(none)*")
    else:
        for v in ds:
            lines.append(f"### {v['agent']}.{v['case_id']} — {v['class']} ({v['axis']})")
            lines.append("")
            lines.append(f"- **positive_criteria**: {v.get('positive_criteria_check','')}")
            lines.append(f"- **gt_required_capability**: {v.get('gt_required_capability_check','')}")
            lines.append(f"- **path_alignment**: {v.get('path_alignment_check','')}")
            lines.append(f"- **counterfactual**: {v.get('counterfactual_check','')}")
            lines.append(f"- **reason**: {v['reason']}")
            lines.append(f"- **evidence**: `merged/verify_evidence/{v['agent']}_case_{v['case_id']}.yaml`")
            lines.append("")
    lines.append("")

    # ---------- Unverifiable ----------
    lines.append("---")
    lines.append("")
    lines.append("## 7. Unverifiable cases")
    lines.append("")
    un = [v for v in verdicts if v["verdict"] == "unverifiable"]
    if un:
        by_reason = defaultdict(list)
        for v in un:
            by_reason[v["reason"][:60]].append(f"{v['agent']}.{v['case_id']} ({v['class']})")
        for reason, cases in by_reason.items():
            lines.append(f"- **{reason}**: {', '.join(cases[:20])}" + (f" …+{len(cases)-20}" if len(cases) > 20 else ""))
    else:
        lines.append("*(none)*")
    lines.append("")

    # ---------- Red-zone PD re-evaluation ----------
    lines.append("---")
    lines.append("")
    lines.append("## 8. Red-zone PD re-evaluation")
    lines.append("")
    lines.append("Coupling-red PDs per taxonomy: PD_NamedCandidateNotIsolated (V_r=0.54), PD_MultiRCCompromise (V_r=0.76). Partition verdicts and check redundancy rate.")
    lines.append("")
    for pd_cls in ("PD_NamedCandidateNotIsolated", "PD_MultiRCCompromise"):
        c = class_counts.get(pd_cls, Counter())
        total = sum(c.values())
        if total == 0:
            lines.append(f"### {pd_cls} — no verdicts")
            lines.append("")
            continue
        agree = c.get("agree", 0)
        red = c.get("redundant", 0)
        miss = c.get("misaligned", 0) + c.get("fabricated", 0)
        lines.append(f"### {pd_cls} — N={total}")
        lines.append("")
        lines.append(f"- agree: {agree} ({round(100 * agree / total)}%)")
        lines.append(f"- redundant: {red} ({round(100 * red / total)}%)")
        lines.append(f"- misaligned/fabricated (spillover): {miss} ({round(100 * miss / total)}%)")
        rate = red / total
        if rate >= 0.6:
            lines.append(f"- **Recommendation**: redundant-rate {round(100*rate)}% ≥ 60% → promote to R-derived PD note (do not keep at unified level)")
        elif rate >= 0.3:
            lines.append(f"- **Recommendation**: redundant-rate {round(100*rate)}% — borderline, consider tightening counterfactual precondition in Positive criteria")
        else:
            lines.append(f"- **Recommendation**: keep as unified PD")
        lines.append("")

    # ---------- V-E evidence-extraction accuracy ----------
    lines.append("---")
    lines.append("")
    lines.append("## 9. Evidence-extraction accuracy check (V-E meta-verification)")
    lines.append("")
    if SPOTCHECK.exists():
        with SPOTCHECK.open() as f:
            sp = json.load(f)
        lines.append(f"- Audited: {sp['total_audited']} YAMLs (random sample, seed=20260422)")
        lines.append(f"- Parquet re-run failures: {sp['parquet_fail']}")
        lines.append(f"- Substring re-grep failures: {sp['substring_fail']}")
        lines.append(f"- Overall pass rate: {round(sp['pass_rate']*100)}%")
        if sp["pass_rate"] >= 0.8:
            lines.append("- **Verdict**: PASS (≥80% threshold). Evidence dumps trustworthy.")
        else:
            lines.append("- **Verdict**: FAIL — re-dispatch V-B with tighter brief.")
    else:
        lines.append("*(spot-check report missing)*")
    lines.append("")

    # ---------- Headline findings ----------
    lines.append("---")
    lines.append("")
    lines.append("## 10. Headline findings")
    lines.append("")
    total_verd = len(verdicts)
    agree_total = sum(1 for v in verdicts if v["verdict"] == "agree")
    non_agree_total = total_verd - agree_total
    lines.append(f"- **Overall agree rate**: {agree_total}/{total_verd} ({round(100 * agree_total / total_verd)}%)")
    for ax in ("D", "R", "PD"):
        c = axis_counts[ax]
        tot = sum(c.values())
        ag = c.get("agree", 0)
        lines.append(f"- **{ax} axis**: {ag}/{tot} agree ({round(100 * ag / max(tot,1))}%)")
    lines.append("")
    lines.append("- **Fabricated D**: " + (str(len([v for v in verdicts if v['verdict']=='fabricated'])) + " (every fabricated means the D label is blaming data when the agent chose wrong path)"))
    lines.append("- **Misaligned R**: " + (str(len([v for v in verdicts if v['verdict']=='misaligned'])) + " (misattributed reasoning-defect class — GT didn't require the capability the R label blames)"))
    lines.append("- **Redundant PD**: " + (str(len([v for v in verdicts if v['verdict']=='redundant'])) + " (PD label on cases where the missing action would change nothing)"))
    lines.append("")
    lines.append("> For per-case evidence see `merged/verify_evidence/<agent>_case_<id>.yaml`.")
    lines.append("> For per-verdict row see `merged/verify_verdicts.jsonl`.")
    lines.append("")

    OUT.write_text("\n".join(lines))
    print(f"Wrote {OUT} ({len(lines)} lines)")


def _distinct_cases(verdicts: list[dict]) -> int:
    return len({(v["agent"], v["case_id"]) for v in verdicts})


def _esc(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")[:280]


if __name__ == "__main__":
    main()
