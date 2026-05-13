#!/usr/bin/env python
"""Phase PD-C.1 merge: combine 4 per-framework PD_phrases.jsonl files into
merged/PD_projection.jsonl using a mechanism-homogeneity mapping.

Rules:
- Each per-framework PD name maps to exactly one (unified PD) OR (framework-specific PD).
- A case's unified PD list = dedup(map(tentative_classes)).
- Framework-specific PD list carries the "agent.PD_name" entries.

This script does NOT compute Cramér's V (see pd_cramer_v.py). It only merges.
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from harp_config import FRAMEWORKS, MERGED  # noqa: E402


# Mechanism-homogeneity mapping. Each key is a per-framework PD name; value is either
# a unified PD name (string starting with 'PD_') or a tuple ('framework_specific', agent_key).
MAPPING: dict[tuple[str, str], str | tuple[str, str]] = {
    # aiq
    ("aiq", "PD_NoBaselineContrast"): "PD_NoBaselineContrast",
    ("aiq", "PD_StageEndsWithoutCommitment"): ("framework_specific", "aiq"),
    ("aiq", "PD_NoCallTreeBuild"): "PD_NoCallTreeBuild",
    ("aiq", "PD_ReflectionStageWithoutNewProbe"): ("framework_specific", "aiq"),
    ("aiq", "PD_MetricLayerProbeAbsentForFaultCategory"): "PD_NoFaultLayerMetricProbe",
    ("aiq", "PD_NamedRCWithoutTargetedProbe"): "PD_NamedCandidateNotIsolated",
    ("aiq", "PD_VolumeRankingWithoutDeepProbe"): "PD_SurveyWithoutDrill",
    ("aiq", "PD_CompressOverwritesTerminator"): ("framework_specific", "aiq"),
    # claudecode
    ("claudecode", "PD1_BaselineCollectedNotContrasted"): "PD_NoBaselineContrast",
    ("claudecode", "PD2_FaultLayerMetricProbeSkipped"): "PD_NoFaultLayerMetricProbe",
    ("claudecode", "PD3_TriageLoopWithoutDrill"): "PD_SurveyWithoutDrill",
    # REFACTOR (PD-C.2): cc.PD4 is GT-oriented (labeling-only), moved to framework_specific.
    #   Keeps only trajectory-only cc.PD5 in unified U_NamedCandidateNotIsolated.
    #   This reduced V_r from 0.574 to 0.542 (still red-zone, retained with coupled_with tag
    #   against U2_ChronicAmbientNoiseAnchor).
    ("claudecode", "PD4_GTServiceNotTargetedWithWhere"): ("framework_specific", "claudecode"),
    ("claudecode", "PD5_FinalRCNotGroundedByProbe"): "PD_NamedCandidateNotIsolated",
    ("claudecode", "PD6_CallTreeAbsentOrShallow"): "PD_NoCallTreeBuild",
    # sonnet (thinkdepthai-claude-sonnet-4.6). Names use "PD1"/"PD2" etc. or full
    # "BaselineContrastSkipped" — accept both forms (sub-agent used prefixes).
    ("sonnet", "PD1_BaselineContrastSkipped"): "PD_NoBaselineContrast",
    ("sonnet", "PD1"): "PD_NoBaselineContrast",
    ("sonnet", "BaselineContrastSkipped"): "PD_NoBaselineContrast",
    ("sonnet", "PD2_CandidateNeverIsolatedByWhere"): "PD_NamedCandidateNotIsolated",
    ("sonnet", "PD2"): "PD_NamedCandidateNotIsolated",
    ("sonnet", "CandidateNeverIsolatedByWhere"): "PD_NamedCandidateNotIsolated",
    ("sonnet", "PD3_CallTreeBuildAbsent"): "PD_NoCallTreeBuild",
    ("sonnet", "PD3"): "PD_NoCallTreeBuild",
    ("sonnet", "CallTreeBuildAbsent"): "PD_NoCallTreeBuild",
    ("sonnet", "PD4_BudgetExhaustCommit"): "PD_LateExplorationDegenerate",
    ("sonnet", "PD4"): "PD_LateExplorationDegenerate",
    ("sonnet", "BudgetExhaustCommit"): "PD_LateExplorationDegenerate",
    ("sonnet", "PD5_ThinkNarrationDominant"): ("framework_specific", "sonnet"),
    ("sonnet", "PD5"): ("framework_specific", "sonnet"),
    ("sonnet", "ThinkNarrationDominant"): ("framework_specific", "sonnet"),
    ("sonnet", "PD6_CompromiseMultiRCOutput"): "PD_MultiRCCompromise",
    ("sonnet", "PD6"): "PD_MultiRCCompromise",
    ("sonnet", "CompromiseMultiRCOutput"): "PD_MultiRCCompromise",
    ("sonnet", "PD7_TraceFollowAbsent"): "PD_TraceFollowAbsent",
    ("sonnet", "PD7"): "PD_TraceFollowAbsent",
    ("sonnet", "TraceFollowAbsent"): "PD_TraceFollowAbsent",
    # qwen
    ("qwen", "PD1_NoBaselineContrast"): "PD_NoBaselineContrast",
    ("qwen", "PD2_NoJVMFamilyDrill"): "PD_NoFaultLayerMetricProbe",
    ("qwen", "PD3_NoContainerFamilyDrill"): "PD_NoFaultLayerMetricProbe",
    ("qwen", "PD4_NoCallTreeBuild"): "PD_NoCallTreeBuild",
    ("qwen", "PD5_ErrorStatusFilterBlind"): "PD_ErrorOnlyFilterBias",
    ("qwen", "PD6_ServiceAvgNoSpanMaxDrill"): ("framework_specific", "qwen"),
    ("qwen", "PD7_PostPivotSingleServiceFixation"): "PD_LateExplorationDegenerate",
    ("qwen", "PD8_NoChronicityReasoning"): ("framework_specific", "qwen"),
}


PHRASE_FILES = {
    "aiq": Path("analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/v1/PD_phrases.jsonl"),
    "claudecode": Path(
        "analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/PD_phrases.jsonl"),
    "sonnet": Path(
        "analysis/3-failure-modes/2-by-framework/thinkdepthai-claude-sonnet-4.6/v1/PD_phrases.jsonl"),
    "qwen": Path(
        "analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v1_harp/PD_phrases.jsonl"),
}

# Read labels.jsonl to get fault_type per case (for record-keeping only)
def load_fault_types(agent_key: str) -> dict[int, str]:
    exp_id, labels_path, field, _ws = FRAMEWORKS[agent_key]
    out: dict[int, str] = {}
    with labels_path.open() as f:
        for line in f:
            r = json.loads(line)
            case_id = int(r[field])
            ft = r.get("fault_type")
            if ft is None:
                # sonnet / aiq labels may lack fault_type; leave blank
                ft = r.get("fault_category", "unknown")
            out[case_id] = str(ft)
    return out


def normalize_pd_name(agent: str, raw_name: str) -> str:
    """Lookup with multiple candidate formats."""
    # try exact
    if (agent, raw_name) in MAPPING:
        return raw_name
    # try without numeric prefix "PDN_..."
    m = re.match(r"^PD\d+_(.+)$", raw_name)
    if m and (agent, m.group(1)) in MAPPING:
        return m.group(1)
    return raw_name  # returned even if unmapped so we can log


def map_to_unified(agent: str, raw_names: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Return (unified, framework_specific, unmapped)."""
    unified: list[str] = []
    framework_specific: list[str] = []
    unmapped: list[str] = []
    for rn in raw_names:
        normalized = normalize_pd_name(agent, rn)
        target = MAPPING.get((agent, normalized))
        if target is None:
            unmapped.append(rn)
        elif isinstance(target, tuple):
            framework_specific.append(f"{target[1]}.{normalized}")
        else:
            unified.append(target)
    # dedup, preserve order
    def dedup(xs: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out
    return dedup(unified), dedup(framework_specific), unmapped


def main() -> None:
    rows_out: list[dict] = []
    overall_pd_counts: Counter[str] = Counter()
    overall_fw_counts: Counter[str] = Counter()
    per_agent_counts: dict[str, Counter[str]] = defaultdict(Counter)
    unmapped_log: list[tuple[str, int, str]] = []
    empty_pd_cases: list[tuple[str, int]] = []

    for agent_key, phrases_path in PHRASE_FILES.items():
        fault_types = load_fault_types(agent_key)
        with phrases_path.open() as f:
            for line in f:
                r = json.loads(line)
                case_id = int(r["case_id"])
                tentative = r.get("tentative_classes", [])
                unified, framework_specific, unmapped = map_to_unified(agent_key, tentative)
                for u in unmapped:
                    unmapped_log.append((agent_key, case_id, u))

                confidence = "high" if r.get("confirmed", True) else "low"
                if not unified and not framework_specific:
                    empty_pd_cases.append((agent_key, case_id))

                evidence: dict[str, str] = {}
                # Use first phrase matching each unified PD as evidence line.
                phrases = r.get("phrases", [])
                # Crude heuristic: first phrase per unified/framework_specific PD name token.
                for pd_name in unified + framework_specific:
                    short = pd_name.split(".")[-1]  # strip 'aiq.' prefix
                    for p in phrases:
                        if not p:
                            continue
                        p_low = p.lower()
                        # heuristic matcher: key action words
                        if any(k in p_low for k in _keywords_for(pd_name)):
                            evidence.setdefault(pd_name, p[:200])
                            break
                    if pd_name not in evidence:
                        evidence[pd_name] = phrases[0][:200] if phrases else ""

                rows_out.append({
                    "agent": agent_key,
                    "case_id": case_id,
                    "fault_type": fault_types.get(case_id, "unknown"),
                    "process_defects": unified,
                    "framework_specific": framework_specific,
                    "confidence": confidence,
                    "evidence": evidence,
                })
                for u in unified:
                    overall_pd_counts[u] += 1
                    per_agent_counts[agent_key][u] += 1
                for fw in framework_specific:
                    overall_fw_counts[fw] += 1
                    per_agent_counts[agent_key][fw] += 1

    # Write projection
    out_path = MERGED / "PD_projection.jsonl"
    with out_path.open("w") as f:
        for row in rows_out:
            f.write(json.dumps(row) + "\n")
    print(f"Wrote {len(rows_out)} rows to {out_path}")

    # Summary
    print("\n=== Unified PD counts ===")
    for name, ct in overall_pd_counts.most_common():
        print(f"  {name}: {ct}")
    print("\n=== Framework-specific PD counts ===")
    for name, ct in overall_fw_counts.most_common():
        print(f"  {name}: {ct}")
    print("\n=== Per-framework per-PD counts ===")
    for agent_key, counts in per_agent_counts.items():
        print(f"  {agent_key}:")
        for name, ct in counts.most_common():
            print(f"    {name}: {ct}")
    if unmapped_log:
        print(f"\n=== UNMAPPED per-agent PDs (n={len(unmapped_log)}) ===")
        for agent_key, case_id, raw in unmapped_log[:20]:
            print(f"  [{agent_key}] case_{case_id}: {raw}")
        if len(unmapped_log) > 20:
            print(f"  ... and {len(unmapped_log) - 20} more")
    else:
        print("\nNo unmapped per-agent PDs.")
    print(f"\nEmpty-PD cases: {len(empty_pd_cases)}")
    for agent_key, case_id in empty_pd_cases[:10]:
        print(f"  [{agent_key}] case_{case_id}")


def _keywords_for(pd_name: str) -> list[str]:
    short = pd_name.split(".")[-1]
    kw_map = {
        "PD_NoBaselineContrast": ["baseline_contrast", "baseline", "contrast"],
        "PD_NoCallTreeBuild": ["call_tree", "call tree", "recursive"],
        "PD_NoFaultLayerMetricProbe": ["jvm", "container", "metric", "k8s", "network_layer"],
        "PD_NamedCandidateNotIsolated": ["service_name", "targeted probe", "WHERE", "isolated"],
        "PD_SurveyWithoutDrill": ["triage", "volume", "ranking", "drill"],
        "PD_ErrorOnlyFilterBias": ["status=Error", "Unset", "error-only", "status"],
        "PD_TraceFollowAbsent": ["trace_follow", "trace_id"],
        "PD_LateExplorationDegenerate": ["budget", "exhaust", "pivot", "fixation", "late"],
        "PD_MultiRCCompromise": ["root_causes", "multi", "compromise", "≥2"],
        "PD_StageEndsWithoutCommitment": ["stage", "terminator", "truncated", "max_rounds"],
        "PD_ReflectionStageWithoutNewProbe": ["reflection", "reinforce", "refine"],
        "PD_CompressOverwritesTerminator": ["compress", "overwrite"],
        "PD_ThinkNarrationDominant": ["think_tool", "narration"],
        "PD_ServiceAvgNoSpanMaxDrill": ["AVG", "MAX", "span"],
        "PD_NoChronicityReasoning": ["chronic", "pre-existing", "background"],
    }
    return kw_map.get(short, [short.lower()])


if __name__ == "__main__":
    main()
