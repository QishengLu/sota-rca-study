#!/usr/bin/env python
"""PD-C.2 red-zone refactor attempt.

Strategy:
1. Split U_NamedCandidateNotIsolated into trajectory-only vs GT-oriented variants:
   - Keep cc.PD5 + aiq.PD_NamedRC + sn.PD2 as U_NamedCandidateNotIsolated (trajectory-only)
   - Move cc.PD4_GTServiceNotTargetedWithWhere to framework_specific claudecode (GT-dependent).
2. PD_MultiRCCompromise cannot be refactored (definition already trajectory-only).

Recompute Cramér V after refactor.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harp_config import DB_URL, FRAMEWORKS  # noqa: E402


def cramers_v(contingency: list[list[int]]) -> float:
    n = sum(sum(row) for row in contingency)
    if n == 0:
        return 0.0
    rows = len(contingency)
    cols = len(contingency[0]) if rows else 0
    if rows < 2 or cols < 2:
        return 0.0
    row_tot = [sum(row) for row in contingency]
    col_tot = [sum(contingency[r][c] for r in range(rows)) for c in range(cols)]
    chi2 = 0.0
    for r in range(rows):
        for c in range(cols):
            expected = row_tot[r] * col_tot[c] / n
            if expected > 0:
                chi2 += (contingency[r][c] - expected) ** 2 / expected
    k = min(rows - 1, cols - 1)
    if k == 0:
        return 0.0
    return math.sqrt(chi2 / (n * k))


# Load projection with refactored mapping in-memory (PD_projection.jsonl is original).
proj_path = Path("analysis/3-failure-modes/merged/PD_projection.jsonl")
d_path = Path("analysis/3-failure-modes/merged/D_projection.jsonl")

rows = [json.loads(l) for l in proj_path.open()]
d_rows = [json.loads(l) for l in d_path.open()]
d_map = {(r["agent"], int(r["case_id"])): r["d_class"] for r in d_rows}


# Get R labels from DB
from sqlmodel import Session, create_engine, select  # noqa: E402

sys.path.insert(0, "RCAgentEval")
from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402

engine = create_engine(DB_URL)
r_map: dict[tuple[str, int], str] = {}
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
            r = v1.get("R") or v1.get("unified_R")
            if r:
                r_map[(agent_key, sample.dataset_index)] = r


# Refactor: for each row, re-compute process_defects + framework_specific.
# Rule: keep U_NamedCandidateNotIsolated only if the case has aiq.PD_NamedRC, cc.PD5,
# or sonnet.PD2. If case only has cc.PD4 (GT-oriented labeling-only), move to
# framework_specific "claudecode.PD4_GTServiceNotTargetedWithWhere".

# To do this, we need the per-agent tentative_classes. Reload from PD_phrases.jsonl.
PHRASE_FILES = {
    "aiq": Path("analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/v1/PD_phrases.jsonl"),
    "claudecode": Path(
        "analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/PD_phrases.jsonl"),
    "sonnet": Path(
        "analysis/3-failure-modes/2-by-framework/thinkdepthai-claude-sonnet-4.6/v1/PD_phrases.jsonl"),
    "qwen": Path(
        "analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v1_harp/PD_phrases.jsonl"),
}

tentative_map: dict[tuple[str, int], list[str]] = {}
for agent_key, path in PHRASE_FILES.items():
    for line in path.open():
        r = json.loads(line)
        tentative_map[(agent_key, int(r["case_id"]))] = r.get("tentative_classes", [])


def refactored_process_defects(agent: str, case_id: int) -> tuple[list[str], list[str]]:
    """Return (unified, framework_specific) for refactored mapping."""
    tentative = tentative_map.get((agent, case_id), [])
    unified: set[str] = set()
    fw: set[str] = set()
    # Refactored mapping: cc.PD4 → framework_specific
    for tc in tentative:
        if agent == "aiq":
            if tc == "PD_NoBaselineContrast":
                unified.add("PD_NoBaselineContrast")
            elif tc == "PD_NoCallTreeBuild":
                unified.add("PD_NoCallTreeBuild")
            elif tc == "PD_MetricLayerProbeAbsentForFaultCategory":
                unified.add("PD_NoFaultLayerMetricProbe")
            elif tc == "PD_NamedRCWithoutTargetedProbe":
                unified.add("PD_NamedCandidateNotIsolated")
            elif tc == "PD_VolumeRankingWithoutDeepProbe":
                unified.add("PD_SurveyWithoutDrill")
            elif tc in {"PD_StageEndsWithoutCommitment", "PD_ReflectionStageWithoutNewProbe",
                         "PD_CompressOverwritesTerminator"}:
                fw.add(f"aiq.{tc}")
        elif agent == "claudecode":
            if tc == "PD1_BaselineCollectedNotContrasted":
                unified.add("PD_NoBaselineContrast")
            elif tc == "PD2_FaultLayerMetricProbeSkipped":
                unified.add("PD_NoFaultLayerMetricProbe")
            elif tc == "PD3_TriageLoopWithoutDrill":
                unified.add("PD_SurveyWithoutDrill")
            elif tc == "PD4_GTServiceNotTargetedWithWhere":
                # REFACTOR: GT-oriented, move to framework_specific
                fw.add("claudecode.PD4_GTServiceNotTargetedWithWhere")
            elif tc == "PD5_FinalRCNotGroundedByProbe":
                unified.add("PD_NamedCandidateNotIsolated")
            elif tc == "PD6_CallTreeAbsentOrShallow":
                unified.add("PD_NoCallTreeBuild")
        elif agent == "sonnet":
            # normalize various forms
            t = tc.replace("PD1_", "PD1:").replace("PD2_", "PD2:").replace("PD3_", "PD3:") \
                .replace("PD4_", "PD4:").replace("PD5_", "PD5:").replace("PD6_", "PD6:") \
                .replace("PD7_", "PD7:")
            if t.startswith("PD1"):
                unified.add("PD_NoBaselineContrast")
            elif t.startswith("PD2"):
                unified.add("PD_NamedCandidateNotIsolated")
            elif t.startswith("PD3"):
                unified.add("PD_NoCallTreeBuild")
            elif t.startswith("PD4"):
                unified.add("PD_LateExplorationDegenerate")
            elif t.startswith("PD5"):
                fw.add("sonnet.PD5_ThinkNarrationDominant")
            elif t.startswith("PD6"):
                unified.add("PD_MultiRCCompromise")
            elif t.startswith("PD7"):
                unified.add("PD_TraceFollowAbsent")
        elif agent == "qwen":
            if tc == "PD1_NoBaselineContrast":
                unified.add("PD_NoBaselineContrast")
            elif tc in {"PD2_NoJVMFamilyDrill", "PD3_NoContainerFamilyDrill"}:
                unified.add("PD_NoFaultLayerMetricProbe")
            elif tc == "PD4_NoCallTreeBuild":
                unified.add("PD_NoCallTreeBuild")
            elif tc == "PD5_ErrorStatusFilterBlind":
                unified.add("PD_ErrorOnlyFilterBias")
            elif tc == "PD6_ServiceAvgNoSpanMaxDrill":
                fw.add("qwen.PD6_ServiceAvgNoSpanMaxDrill")
            elif tc == "PD7_PostPivotSingleServiceFixation":
                unified.add("PD_LateExplorationDegenerate")
            elif tc == "PD8_NoChronicityReasoning":
                fw.add("qwen.PD8_NoChronicityReasoning")
    return sorted(unified), sorted(fw)


# Build refactored projection and compute V
refactored_rows: list[dict] = []
for r in rows:
    agent = r["agent"]
    case_id = int(r["case_id"])
    new_unified, new_fw = refactored_process_defects(agent, case_id)
    new_row = dict(r)
    new_row["process_defects"] = new_unified
    new_row["framework_specific"] = new_fw
    refactored_rows.append(new_row)

# Cramér V on refactored
from collections import Counter

pd_names = sorted({pd for row in refactored_rows for pd in row["process_defects"]})

def contingency(rows, axis_map, pd_name):
    axis_classes = sorted({v for v in axis_map.values()})
    table = [[0] * len(axis_classes) for _ in range(2)]
    for row in rows:
        key = (row["agent"], int(row["case_id"]))
        if key not in axis_map:
            continue
        has_pd = pd_name in row["process_defects"]
        ci = axis_classes.index(axis_map[key])
        table[int(has_pd)][ci] += 1
    return table


print(f"\n=== AFTER REFACTOR — {len(pd_names)} unified PDs ===")
print("| PD | count | V vs D | V vs R |")
print("|---|---|---|---|")
rows_out = []
for pd_name in pd_names:
    d_ct = contingency(refactored_rows, d_map, pd_name)
    r_ct = contingency(refactored_rows, r_map, pd_name)
    v_d = cramers_v(d_ct)
    v_r = cramers_v(r_ct)
    count = sum(1 for row in refactored_rows if pd_name in row["process_defects"])
    rows_out.append((pd_name, count, v_d, v_r))
    print(f"| {pd_name} | {count} | {v_d:.3f} | {v_r:.3f} |")

vs = [x[2] for x in rows_out] + [x[3] for x in rows_out]
median = sorted(vs)[len(vs)//2]
print(f"\nMedian V: {median:.3f}")
red = [x for x in rows_out if x[2] >= 0.50 or x[3] >= 0.50]
yellow = [x for x in rows_out if (0.30 <= x[2] < 0.50) or (0.30 <= x[3] < 0.50)]
print(f"Red-zone (V >= 0.50): {[x[0] for x in red]}")
print(f"Yellow-zone (0.30-0.49): {[x[0] for x in yellow]}")

# Write refactored projection to a separate file for comparison
out_path = Path("analysis/3-failure-modes/merged/PD_projection_refactored.jsonl")
with out_path.open("w") as f:
    for row in refactored_rows:
        f.write(json.dumps(row) + "\n")
print(f"\nWrote refactored projection: {out_path}")
