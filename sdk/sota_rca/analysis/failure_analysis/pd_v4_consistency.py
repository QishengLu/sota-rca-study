#!/usr/bin/env python
"""V.4 rule-card consistency check.

For each R = U1 / U2 / U3 labeled case:
- Check whether the PDs referenced in that rule's §2 trigger block are in
  the case's meta.failure_analysis.v1.process_defects array.
- Report match rate per rule; flag if match rate < 70%.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harp_config import DB_URL, FRAMEWORKS  # noqa: E402

sys.path.insert(0, "RCAgentEval")
from sqlmodel import Session, create_engine, select  # noqa: E402
from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402


# PDs referenced in each rule card §2 after rewrite
RULE_PDS: dict[str, list[str]] = {
    "U1_LoudnessAnchorOverSilentVictim": [
        "PD_NoFaultLayerMetricProbe",
        "PD_NoBaselineContrast",
        "PD_NamedCandidateNotIsolated",
        "PD_SurveyWithoutDrill",
    ],
    "U2_ChronicAmbientNoiseAnchor": [
        "PD_NoBaselineContrast",
    ],
    "U3_EdgeDirectionOrRegionEndpointError": [
        "PD_NoCallTreeBuild",
        "PD_NamedCandidateNotIsolated",
    ],
}


def main() -> None:
    engine = create_engine(DB_URL)
    per_rule_stats: dict[str, Counter[str]] = {k: Counter() for k in RULE_PDS}
    per_rule_cases: dict[str, int] = {k: 0 for k in RULE_PDS}
    per_rule_any_match: dict[str, int] = {k: 0 for k in RULE_PDS}

    with Session(engine) as s:
        for agent_key, (exp_id, *_) in FRAMEWORKS.items():
            stmt = select(EvaluationSample).where(
                EvaluationSample.exp_id == exp_id,
                EvaluationSample.correct == False,  # noqa: E712
                EvaluationSample.stage == "judged",
            )
            for sample in s.exec(stmt).all():
                meta = sample.meta or {}
                v1 = (meta.get("failure_analysis") or {}).get("v1") or {}
                r_label = v1.get("R") or v1.get("unified_R")
                if r_label not in RULE_PDS:
                    continue
                pds = set(v1.get("process_defects") or [])
                per_rule_cases[r_label] += 1
                matched_any = False
                for pd in RULE_PDS[r_label]:
                    if pd in pds:
                        per_rule_stats[r_label][pd] += 1
                        matched_any = True
                if matched_any:
                    per_rule_any_match[r_label] += 1

    print("V.4 Rule-card consistency check")
    print("===============================")
    for rule, referenced_pds in RULE_PDS.items():
        total = per_rule_cases[rule]
        any_match = per_rule_any_match[rule]
        print(f"\n## {rule} (n={total} labeled cases)")
        print(f"  Cases where ≥1 referenced PD is in process_defects: {any_match}/{total} "
              f"({100*any_match/total:.1f}%)")
        print("  Per-PD match counts:")
        for pd in referenced_pds:
            ct = per_rule_stats[rule][pd]
            pct = 100 * ct / total if total else 0
            flag = " ⚠ <70%" if pct < 70 else ""
            print(f"    {pd}: {ct} ({pct:.1f}%){flag}")


if __name__ == "__main__":
    main()
