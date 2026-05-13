"""V-C: Orchestrator adjudication with 3-way alignment.

Reads merged/verify_evidence/*.yaml and applies taxonomy Positive criteria + 3-way alignment.
Appends verdicts incrementally to merged/verify_verdicts.jsonl.
Idempotent: dedupes by (agent, case_id, class) — pending set derived from existing rows.

v2 (2026-04-22, Phase X-2 of Part 7 plan): tightened thresholds + Detection∧Counterfactual conjunction
for PD axis. See merged/D_taxonomy.md / unified_R.md / PD_taxonomy.md "v2 Refactor Notes" sections.
Output paths overridable via env vars VERIFY_VERDICTS_PATH, VERIFY_STATE_PATH for v2/v3/v4 versioning.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from harp_config import MERGED

EVIDENCE_DIR = MERGED / "verify_evidence"
VERDICTS_PATH = Path(os.environ.get("VERIFY_VERDICTS_PATH", MERGED / "verify_verdicts.jsonl"))
STATE_PATH = Path(os.environ.get("VERIFY_STATE_PATH", MERGED / "verify_state.json"))


def load_existing_verdicts() -> set[tuple[str, int, str]]:
    seen: set[tuple[str, int, str]] = set()
    if not VERDICTS_PATH.exists():
        return seen
    with VERDICTS_PATH.open() as f:
        for line in f:
            try:
                r = json.loads(line)
                seen.add((r["agent"], int(r["case_id"]), r["class"]))
            except Exception:
                pass
    return seen


def append_verdict(row: dict):
    with VERDICTS_PATH.open("a") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()
        os.fsync(f.fileno())


def atomic_write_state(state: dict):
    tmp = STATE_PATH.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_PATH)


# ---------- Verdict logic -------------------------------------------------

def judge_d(cls: str, y: dict) -> dict:
    """Apply D-axis rules with 3-way alignment."""
    req = y.get("gt_required_capabilities", {})
    pa = y.get("path_alignment", {})
    cf = y.get("counterfactual", {})
    pq = y.get("parquet_evidence", {})
    gt = y.get("gt_from_injection_json", {})
    audit = y.get("raw_sql_substring_audit", {})
    predicted = y.get("agent_predicted", {}).get("root_causes", [])
    gt_services = gt.get("gt_services", []) or []
    ft = gt.get("fault_type") or ""

    gt_touched = pa.get("gt_touched_in_trajectory", False)
    neighbors_touched = pa.get("gt_neighbors_touched", {}) or {}
    path_ok = gt_touched or len(neighbors_touched) >= 1
    structural = cf.get("D_obstacle_is_structural", True)

    # --- D1 VictimSilentOnPath (v2: tightened threshold 10→5 + status_code zero-error check) ---
    if cls == "D1":
        gt_err = pq.get("gt_service_abnormal_log_error_count", {}) or {}
        gt_status = pq.get("gt_service_status_code_distribution", {}) or {}
        total_gt_err = sum(gt_err.values()) if gt_err else 0
        # v2: dispute-strong if GT has more than 5 errors (was 10)
        if total_gt_err > 5:
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": "FAIL",
                    "gt_required_capability_check": "FAIL",
                    "path_alignment_check": "pass" if path_ok else "FAIL",
                    "counterfactual_check": "pass" if structural else "FAIL",
                    "reason": f"D1 claims GT silent but gt_service_abnormal_log_error_count={total_gt_err}>5 (v2 threshold)",
                    "suggested_alternative_class": "D5 or D2"}
        # v2: also reject D1 if GT has any Error-status spans (not just unset/ok)
        gt_error_spans = 0
        for _svc, _dist in (gt_status.items() if isinstance(gt_status, dict) else []):
            if isinstance(_dist, dict):
                gt_error_spans += int(_dist.get("Error", 0) or 0)
        if gt_error_spans > 0:
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": f"FAIL (status=Error spans on GT={gt_error_spans})",
                    "gt_required_capability_check": "FAIL",
                    "path_alignment_check": "pass" if path_ok else "FAIL",
                    "counterfactual_check": "pass" if structural else "FAIL",
                    "reason": f"D1 v2 requires zero Error-status spans on GT but found {gt_error_spans}",
                    "suggested_alternative_class": "D2 or D3"}
        pos_ok = req.get("gt_is_silent", False)
        if not pos_ok:
            return {"verdict": "dispute-weak",
                    "positive_criteria_check": "FAIL (gt_is_silent=False)",
                    "gt_required_capability_check": "FAIL",
                    "path_alignment_check": "pass" if path_ok else "FAIL",
                    "counterfactual_check": "pass" if structural else "FAIL",
                    "reason": f"D1 requires gt_is_silent=True but GT has signal (status/logs={gt_status},{gt_err})"}
        if not path_ok:
            return {"verdict": "fabricated",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": f"FAIL (gt_touched=False, neighbors_touched={list(neighbors_touched.keys())})",
                    "counterfactual_check": "pass" if structural else "FAIL",
                    "reason": "D1 Positive ok but agent never reached GT path",
                    "suggested_alternative_class": "PD_NamedCandidateNotIsolated"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass (gt_is_silent=True)",
                "path_alignment_check": f"pass (gt_touched={gt_touched}, neighbors={list(neighbors_touched.keys())})",
                "counterfactual_check": "pass (structural silence)",
                "reason": "D1: GT silent, agent reached path, silence is structural"}

    # --- D2 CrossLayerSignalGap ---
    if cls == "D2":
        layer = req.get("required_metric_layer", "none") or "none"
        layer_has_key = {
            "jvm": "has_jvm_metric_substring",
            "k8s/container": "has_k8s_metric_substring",
            "network/db": "has_db_metric_substring",
        }.get(layer)
        agent_probed_layer = audit.get(layer_has_key, False) if layer_has_key else None
        if layer == "none":
            return {"verdict": "dispute-weak",
                    "positive_criteria_check": "FAIL (no specific layer required)",
                    "gt_required_capability_check": "FAIL",
                    "path_alignment_check": "pass" if path_ok else "FAIL",
                    "counterfactual_check": "n/a",
                    "reason": f"D2 requires cross-layer gap but fault_type={ft} has no layer requirement"}
        if agent_probed_layer:
            return {"verdict": "dispute-weak",
                    "positive_criteria_check": f"FAIL (agent DID probe {layer})",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "pass" if path_ok else "FAIL",
                    "counterfactual_check": "n/a",
                    "reason": f"D2 alleges agent skipped {layer} probe, but has_{layer_has_key}=True"}
        if not path_ok:
            return {"verdict": "fabricated",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": f"FAIL (gt_touched=False)",
                    "counterfactual_check": "pass",
                    "reason": "D2 Positive ok but agent never reached GT path"}
        return {"verdict": "agree",
                "positive_criteria_check": f"pass (agent skipped {layer} layer)",
                "gt_required_capability_check": f"pass (fault requires {layer})",
                "path_alignment_check": "pass",
                "counterfactual_check": "pass",
                "reason": f"D2: {layer}-layer fault, agent used different-layer SQLs"}

    # --- D3 AmbientNoiseDominatesGT ---
    if cls == "D3":
        chronic = req.get("chronic_noise_present", False)
        carriers = req.get("chronic_noise_carriers", []) or []
        rc_is_carrier = any(s in carriers for s in predicted)
        # top-1 in abnormal logs
        top_err = pq.get("top_error_services_abnormal_logs", []) or []
        top1 = top_err[0]["service"] if top_err else ""
        top1_is_carrier = top1 in carriers
        if not chronic:
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": "FAIL (no chronic_noise_present)",
                    "gt_required_capability_check": "FAIL",
                    "path_alignment_check": "pass" if path_ok else "FAIL",
                    "counterfactual_check": "n/a",
                    "reason": "D3 requires chronic ambient noise but none detected in parquet"}
        if not (rc_is_carrier or top1_is_carrier):
            return {"verdict": "dispute-weak",
                    "positive_criteria_check": "pass (chronic present)",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "pass" if path_ok else "FAIL",
                    "counterfactual_check": f"predicted_rc={predicted} not in carriers={carriers}",
                    "reason": "D3: chronic noise exists, but agent RC didn't anchor on it"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": f"pass (carriers={carriers})",
                "path_alignment_check": "pass",
                "counterfactual_check": f"pass (top1={top1} is carrier; rc_is_carrier={rc_is_carrier})",
                "reason": "D3: chronic noise dominated, RC anchored on chronic"}

    # --- D4 EdgeSymmetricAmbiguity ---
    if cls == "D4":
        is_edge = req.get("gt_path_is_edge_fault", False)
        if not is_edge:
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": f"FAIL (fault_type={ft} is not edge-level)",
                    "gt_required_capability_check": "FAIL",
                    "path_alignment_check": "pass" if path_ok else "FAIL",
                    "counterfactual_check": "n/a",
                    "reason": f"D4 requires edge fault but {ft} is not in edge-fault set"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass (edge fault)",
                "path_alignment_check": "pass" if path_ok else "FAIL",
                "counterfactual_check": "pass",
                "reason": f"D4: edge fault {ft}, agent faced A->B symmetry"}

    # --- D5 CascadeSymptomLouderThanGT (v2: cascade ratio 2x→1.5x; GT err floor ≥10 disambiguates from D1) ---
    if cls == "D5":
        top_err = pq.get("top_error_services_abnormal_logs", []) or []
        top1 = top_err[0] if top_err else None
        gt_err_total = sum((pq.get("gt_service_abnormal_log_error_count", {}) or {}).values())
        is_loudest = req.get("gt_is_loudest", False)
        # v2: relaxed cascade ratio 2x → 1.5x AND GT err floor ≥ 10 (mutual exclusivity with D1 silence)
        cascade_louder = (top1 is not None and top1.get("service") not in gt_services and
                          top1.get("count", 0) > gt_err_total * 1.5 and gt_err_total >= 10)
        if is_loudest:
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": "FAIL (GT is loudest — no cascade decoy)",
                    "gt_required_capability_check": "FAIL",
                    "path_alignment_check": "pass" if path_ok else "FAIL",
                    "counterfactual_check": "n/a",
                    "reason": "D5 requires cascade louder than GT but GT itself is top-ranked",
                    "suggested_alternative_class": "D2 or D3"}
        if not cascade_louder:
            return {"verdict": "dispute-weak",
                    "positive_criteria_check": "FAIL (no clear cascade louder pattern)",
                    "gt_required_capability_check": "partial",
                    "path_alignment_check": "pass" if path_ok else "FAIL",
                    "counterfactual_check": "partial",
                    "reason": f"D5 v2: top1={top1}, gt_err_total={gt_err_total} — no 1.5x cascade or gt_err<10"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass",
                "path_alignment_check": "pass" if path_ok else "FAIL",
                "counterfactual_check": "pass",
                "reason": f"D5: top1={top1['service']} ({top1['count']}) >> GT ({gt_err_total})"}

    # --- D6 NameTwinOnPath ---
    if cls == "D6":
        has_twin = req.get("gt_has_name_twin", False)
        twins = req.get("name_twin_candidates", []) or []
        rc_is_twin = any(rc in twins for rc in predicted)
        if not has_twin:
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": "FAIL (no name-twin exists)",
                    "gt_required_capability_check": "FAIL",
                    "path_alignment_check": "pass" if path_ok else "FAIL",
                    "counterfactual_check": "n/a",
                    "reason": "D6 requires name-twin but none found"}
        if not rc_is_twin:
            return {"verdict": "dispute-weak",
                    "positive_criteria_check": "pass (twin exists)",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "pass" if path_ok else "FAIL",
                    "counterfactual_check": f"FAIL (predicted={predicted} not in twins={twins})",
                    "reason": "D6: twin exists but agent RC is not the twin"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass",
                "path_alignment_check": "pass" if path_ok else "FAIL",
                "counterfactual_check": "pass",
                "reason": f"D6: RC {predicted} is twin of GT {gt_services}"}

    # --- D7 DilutedMultiCandidate ---
    if cls == "D7":
        top_err = pq.get("top_error_services_abnormal_logs", []) or []
        if len(top_err) >= 3:
            vals = [x.get("count", 0) for x in top_err[:5]]
            if vals and vals[0] > 0:
                # diluted if top3 are within 2x of each other
                diluted = all(v >= vals[0] / 2 for v in vals[:3])
            else:
                diluted = False
        else:
            diluted = False
        if not diluted:
            return {"verdict": "dispute-weak",
                    "positive_criteria_check": "FAIL (no dilution pattern)",
                    "gt_required_capability_check": "FAIL",
                    "path_alignment_check": "pass" if path_ok else "FAIL",
                    "counterfactual_check": "n/a",
                    "reason": f"D7: top-3 service error counts don't show dilution pattern: {[x.get('service') + '=' + str(x.get('count')) for x in top_err[:3]]}"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass",
                "path_alignment_check": "pass" if path_ok else "FAIL",
                "counterfactual_check": "pass",
                "reason": f"D7: top-3 similar counts {[x.get('count') for x in top_err[:3]]}"}

    return {"verdict": "unverifiable", "reason": f"Unknown D class: {cls}"}


def judge_r(cls: str, y: dict) -> dict:
    req = y.get("gt_required_capabilities", {})
    cf = y.get("counterfactual", {})
    r_cf = cf.get("R_correct_heuristic_would_reach_gt", {}) or {}
    pq = y.get("parquet_evidence", {})
    audit = y.get("raw_sql_substring_audit", {})
    pa = y.get("path_alignment", {})
    gt = y.get("gt_from_injection_json", {})
    predicted = y.get("agent_predicted", {}).get("root_causes", [])
    gt_services = gt.get("gt_services", []) or []
    ft = gt.get("fault_type") or ""
    snippets = y.get("trajectory_reasoning_snippets", []) or []
    snip_text = " ".join(s.get("text", "") for s in snippets).lower()

    gt_is_silent = req.get("gt_is_silent", False)
    gt_is_loudest = req.get("gt_is_loudest", False)
    gt_has_twin = req.get("gt_has_name_twin", False)
    twins = req.get("name_twin_candidates", []) or []
    gt_is_edge = req.get("gt_path_is_edge_fault", False)

    # U1 LoudnessAnchorOverSilentVictim (v2: top-5 → top-10)
    if cls == "U1_LoudnessAnchorOverSilentVictim":
        # Positive: predicted RC has loud errors, GT silent; RC != GT
        rc_not_gt = not any(rc in gt_services for rc in predicted)
        top_err = pq.get("top_error_services_abnormal_logs", []) or []
        rc_is_loud = any(rc in [x["service"] for x in top_err[:10]] for rc in predicted)
        if not rc_not_gt:
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": "FAIL (RC = GT)",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": "U1 requires RC != GT but they match"}
        if gt_is_loudest:
            return {"verdict": "misaligned",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "FAIL (gt_is_loudest=True — loudness-anchor was CORRECT heuristic)",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": f"FAIL (if_loudness_applied={r_cf.get('if_loudness_applied')})",
                    "reason": "U1 requires silent victim but GT is loudest — misattribution",
                    "suggested_alternative_class": "U2 or U3"}
        if not gt_is_silent:
            return {"verdict": "dispute-weak",
                    "positive_criteria_check": "partial",
                    "gt_required_capability_check": "FAIL (gt_is_silent=False)",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "partial",
                    "reason": "U1 requires silent GT; GT has some signal"}
        if not rc_is_loud:
            return {"verdict": "dispute-weak",
                    "positive_criteria_check": "FAIL (RC not in top-10 loud)",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": f"U1 v2: predicted RC {predicted} is not in top-10 error services"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass (GT silent)",
                "path_alignment_check": "pass",
                "counterfactual_check": "pass",
                "reason": "U1: silent GT + loud surrogate RC"}

    # U2 ChronicAmbientNoiseAnchor
    if cls == "U2_ChronicAmbientNoiseAnchor":
        chronic = req.get("chronic_noise_present", False)
        carriers = req.get("chronic_noise_carriers", []) or []
        rc_is_chronic = any(rc in carriers for rc in predicted)
        if not chronic:
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": "FAIL (no chronic noise)",
                    "gt_required_capability_check": "FAIL",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": "U2 requires chronic noise carriers but none detected"}
        if not rc_is_chronic:
            return {"verdict": "misaligned",
                    "positive_criteria_check": "FAIL (RC not chronic carrier)",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": f"FAIL (predicted={predicted} not in carriers={carriers})",
                    "reason": "U2 requires RC=chronic carrier; agent picked non-chronic",
                    "suggested_alternative_class": "U1 or U3"}
        # Verify agent did NOT do baseline contrast
        if audit.get("has_baseline_contrast_substring", False):
            return {"verdict": "dispute-weak",
                    "positive_criteria_check": "partial (agent did baseline contrast)",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "partial",
                    "reason": "U2 Positive says NO baseline_contrast but agent ran one"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass",
                "path_alignment_check": "pass",
                "counterfactual_check": "pass",
                "reason": f"U2: chronic carriers={carriers}, RC={predicted}"}

    # U3 EdgeDirectionOrRegionEndpointError
    if cls == "U3_EdgeDirectionOrRegionEndpointError":
        if not gt_is_edge:
            return {"verdict": "misaligned",
                    "positive_criteria_check": "FAIL",
                    "gt_required_capability_check": f"FAIL (fault_type={ft} is not edge-level)",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": "U3 requires edge fault but fault is not edge-level",
                    "suggested_alternative_class": "U1 or U2"}
        # Edge direction reasoning would reach GT?
        edge_reachable = r_cf.get("if_edge_direction_applied")
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass (edge fault)",
                "path_alignment_check": "pass",
                "counterfactual_check": f"pass (if_edge_direction_applied={edge_reachable})",
                "reason": f"U3: edge fault {ft}, agent missed direction"}

    # U4 NameTwinSiblingConfusion
    if cls == "U4_NameTwinSiblingConfusion":
        if not gt_has_twin:
            return {"verdict": "misaligned",
                    "positive_criteria_check": "FAIL",
                    "gt_required_capability_check": "FAIL (no name-twin)",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": "U4 requires name-twin but GT has no twin in observed services"}
        rc_is_twin = any(rc in twins for rc in predicted)
        if not rc_is_twin:
            return {"verdict": "dispute-weak",
                    "positive_criteria_check": "partial",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": f"FAIL (RC {predicted} not a twin of GT)",
                    "reason": "U4: twin exists but agent RC is not the twin"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass (twin exists)",
                "path_alignment_check": "pass",
                "counterfactual_check": "pass",
                "reason": f"U4: RC {predicted} is twin of GT {gt_services}"}

    # U5 SilenceReadAsHealthOrPaused
    if cls == "U5_SilenceReadAsHealthOrPaused":
        if not gt_is_silent:
            return {"verdict": "misaligned",
                    "positive_criteria_check": "FAIL",
                    "gt_required_capability_check": "FAIL (GT not silent — no silence to misread)",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": "U5 requires silent GT but GT has signal"}
        # Explicit health-inference in snippets
        markers = ["no error", "healthy", "successful", "unset status", "fine", "frozen",
                   "plateau", "process_paused", "idle", "deployment.available"]
        has_marker = any(m in snip_text for m in markers)
        if not has_marker:
            return {"verdict": "dispute-weak",
                    "positive_criteria_check": "FAIL (no explicit health-inference text)",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": "U5 requires explicit 'silent=healthy' reasoning; none found in snippets"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass",
                "path_alignment_check": "pass",
                "counterfactual_check": "pass",
                "reason": "U5: silent GT + explicit health inference in reasoning"}

    # --- Framework-specific R ---
    if cls == "aiq.R_hub_fabrication":
        # RC not in any observed service
        # observed from parquet top_error + top_error_span + etc.
        observed = set()
        for x in pq.get("top_error_services_abnormal_logs", []) or []: observed.add(x.get("service"))
        for x in pq.get("top_error_services_normal_logs", []) or []: observed.add(x.get("service"))
        for x in pq.get("top_error_span_services", []) or []: observed.add(x.get("service"))
        rc_all_unobserved = all(rc not in observed for rc in predicted) if predicted else False
        if rc_all_unobserved:
            return {"verdict": "agree",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "pass",
                    "counterfactual_check": "pass",
                    "reason": f"RC {predicted} not in observed services"}
        return {"verdict": "dispute-weak",
                "positive_criteria_check": "FAIL (RC is in observed)",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": f"hub_fabrication requires unobserved RC but {predicted} in observed"}

    if cls == "aiq.R_correct_then_reversed":
        # requires multi-stage; not easy to verify without stage markers
        return {"verdict": "unverifiable",
                "positive_criteria_check": "n/a",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": "Requires aiq 3-stage pipeline markers not present in evidence dump"}

    if cls == "aiq.R_compress_drift":
        return {"verdict": "unverifiable",
                "positive_criteria_check": "n/a",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": "Requires aiq compress_to_graph stage analysis not in evidence dump"}

    if cls == "claudecode.R6_InfraLayerSkipped":
        cat = gt.get("fault_category") or ""
        # infra-ish: Pod/Network with DB target or similar
        infra_like = cat in ("PodChaos", "NetworkChaos")
        layer_skipped = not (audit.get("has_k8s_metric_substring") or audit.get("has_db_metric_substring") or audit.get("has_container_metric_substring"))
        if infra_like and layer_skipped:
            return {"verdict": "agree",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "pass",
                    "counterfactual_check": "pass",
                    "reason": "infra fault but no infra-layer metric probed"}
        return {"verdict": "dispute-weak",
                "positive_criteria_check": "FAIL" if not infra_like else "pass",
                "gt_required_capability_check": "partial",
                "path_alignment_check": "n/a",
                "counterfactual_check": "partial",
                "reason": f"infra_like={infra_like}, layer_skipped={layer_skipped}"}

    if cls == "claudecode.R7_JVMSymptomMisreadAsDB":
        cat = gt.get("fault_category") or ""
        is_jvm = cat == "JVMChaos"
        rc_has_db = any("mysql" in rc.lower() or "db" in rc.lower() for rc in predicted)
        if is_jvm and rc_has_db:
            return {"verdict": "agree",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "pass",
                    "counterfactual_check": "pass",
                    "reason": f"JVM fault, RC={predicted} is DB-named"}
        return {"verdict": "dispute-weak",
                "positive_criteria_check": "FAIL",
                "gt_required_capability_check": "partial",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": f"is_jvm={is_jvm}, rc_has_db={rc_has_db}"}

    if cls == "sonnet.R_OscillationToCompromisePair":
        # multi-RC compromise + long trajectory
        multi = len(predicted) >= 2
        n_sql = y.get("raw_sql_count_total", 0)
        if multi and n_sql >= 30:
            return {"verdict": "agree",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": f"multi-RC={predicted}, n_sql={n_sql}"}
        return {"verdict": "dispute-weak",
                "positive_criteria_check": "FAIL",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": f"multi={multi}, n_sql={n_sql}"}

    if cls == "sonnet.R_NarrativeOverMatchedMagnitude":
        return {"verdict": "unverifiable",
                "positive_criteria_check": "n/a",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": "Requires narrative-text lexical analysis not in evidence dump"}

    if cls == "qwen.R_E_PathOvershootPastInjection":
        # RC is 1+ hop downstream of GT
        # Use gt_parent_child_pairs from parquet_evidence
        pairs = pq.get("gt_parent_child_pairs", []) or []
        rc_downstream = any(
            p in gt_services and c in predicted and c not in gt_services
            for (p, c) in pairs
        )
        if rc_downstream:
            return {"verdict": "agree",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "pass",
                    "counterfactual_check": "pass",
                    "reason": f"RC {predicted} is downstream of GT"}
        return {"verdict": "dispute-weak",
                "positive_criteria_check": "FAIL",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": f"No parent-child pair showing RC downstream of GT"}

    if cls == "qwen.R_F_QueryDesignBuriesSignal":
        # heuristic: SQLs use AVG at service level for a fault that requires span-level probing
        joined_sql = "\n".join(y.get("raw_sql_list_sample") or [])
        has_service_avg = bool(re.search(r"(?is)AVG\s*\(\s*duration\s*\).*?GROUP BY\s+service_name", joined_sql))
        has_span_max = bool(re.search(r"(?is)(MAX|QUANTILE).*?duration.*?GROUP BY\s+span_name", joined_sql))
        if has_service_avg and not has_span_max:
            return {"verdict": "agree",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "pass",
                    "reason": "service-level AVG query w/o span-level MAX — buries signal"}
        return {"verdict": "dispute-weak",
                "positive_criteria_check": f"service_avg={has_service_avg}, span_max={has_span_max}",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": "Query design doesn't match expected pattern"}

    return {"verdict": "unverifiable", "reason": f"Unknown R class: {cls}"}


def judge_pd(cls: str, y: dict) -> dict:
    cf = y.get("counterfactual", {})
    audit = y.get("raw_sql_substring_audit", {})
    pa = y.get("path_alignment", {})
    req = y.get("gt_required_capabilities", {})
    pq = y.get("parquet_evidence", {})
    gt = y.get("gt_from_injection_json", {})
    predicted = y.get("agent_predicted", {}).get("root_causes", [])
    gt_services = gt.get("gt_services", []) or []
    ft = gt.get("fault_type") or ""
    cat = gt.get("fault_category") or ""
    snippets = y.get("trajectory_reasoning_snippets", []) or []
    snip_text = " ".join(s.get("text", "") for s in snippets).lower()
    svc_filters = audit.get("where_service_name_filters", []) or []

    # PD1 NoBaselineContrast
    if cls == "PD_NoBaselineContrast":
        fired = audit.get("has_baseline_contrast_substring", False)
        if fired:
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": "FAIL (baseline_contrast fired)",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": "PD1 claims no baseline_contrast but substring audit shows agent did it"}
        pd1 = cf.get("PD1_baseline_contrast", {}) or {}
        if_run = pd1.get("if_run_would_reveal", False)
        chronic_in_data = pd1.get("chronic_noise_in_data", False)
        rc_chronic = pd1.get("predicted_rc_is_chronic_carrier", False)
        if not chronic_in_data:
            return {"verdict": "redundant",
                    "positive_criteria_check": "pass (no baseline_contrast)",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "FAIL (no chronic noise — baseline_contrast would be no-op)",
                    "reason": "PD1 fires but no chronic noise in data — action would change nothing"}
        if not if_run:
            return {"verdict": "redundant",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "FAIL (if_run_would_reveal=False)",
                    "reason": "PD1 fires but running baseline_contrast on predicted RC would not reveal chronicity"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass (chronic in data)",
                "path_alignment_check": "n/a",
                "counterfactual_check": f"pass (rc_chronic={rc_chronic}, would reveal)",
                "reason": "PD1: no baseline_contrast; chronic data present; action would matter"}

    # PD2 NoCallTreeBuild
    if cls == "PD_NoCallTreeBuild":
        fired = audit.get("has_call_tree_build_substring", False)
        if fired:
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": "FAIL (call_tree_build fired)",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": "PD2 claims no call_tree_build but substring shows recursive CTE or parent_span_id join"}
        pd2 = cf.get("PD2_call_tree_build", {}) or {}
        gt_upstream = pd2.get("gt_is_upstream_of_agent_focus")
        if gt_upstream is False:
            return {"verdict": "redundant",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "FAIL (GT not upstream of focus)",
                    "reason": "PD2 fires but GT is not upstream — call_tree wouldn't surface it"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass",
                "path_alignment_check": "n/a",
                "counterfactual_check": f"pass (gt_is_upstream={gt_upstream})",
                "reason": "PD2: no call_tree_build; GT upstream of focus"}

    # PD3 NoFaultLayerMetricProbe
    if cls == "PD_NoFaultLayerMetricProbe":
        layer = req.get("required_metric_layer", "none") or "none"
        layer_has_key = {
            "jvm": "has_jvm_metric_substring",
            "k8s/container": "has_k8s_metric_substring",
            "network/db": "has_db_metric_substring",
        }.get(layer)
        probed = audit.get(layer_has_key, False) if layer_has_key else False
        if layer == "none":
            return {"verdict": "redundant",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "FAIL (no required layer)",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "FAIL",
                    "reason": f"PD3: no specific metric layer required for fault_type={ft}"}
        if probed:
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": f"FAIL (agent probed {layer})",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": f"PD3 fires but agent has {layer} metric in SQL substrings"}
        pd3 = cf.get("PD3_fault_layer_metric_probe", {}) or {}
        anomaly_exists = pd3.get("gt_metric_anomaly_exists_in_parquet")
        if anomaly_exists is False:
            return {"verdict": "redundant",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "FAIL (no metric anomaly in parquet)",
                    "reason": "PD3 fires but GT metric has no parquet signal — probing wouldn't help"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass",
                "path_alignment_check": "n/a",
                "counterfactual_check": f"pass (anomaly_exists={anomaly_exists})",
                "reason": f"PD3: {layer} layer not probed; anomaly exists in parquet"}

    # PD4 NamedCandidateNotIsolated
    if cls == "PD_NamedCandidateNotIsolated":
        rc_isolated = any(rc in svc_filters for rc in predicted)
        if rc_isolated:
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": "FAIL (RC appears in WHERE filter)",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": f"PD4 claims RC not isolated but {predicted} in WHERE filters {svc_filters}"}
        pd4 = cf.get("PD4_named_candidate_not_isolated", {}) or {}
        healthy = pd4.get("if_isolated_predicted_rc_show_healthy", {}) or {}
        any_healthy = any(v for v in healthy.values()) if healthy else False
        if any_healthy:
            return {"verdict": "agree",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "pass",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": f"pass (would show healthy: {healthy})",
                    "reason": "PD4: RC not probed; isolated probe would show RC is healthy → agent would reject it"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass",
                "path_alignment_check": "n/a",
                "counterfactual_check": "partial",
                "reason": f"PD4: RC {predicted} not in WHERE filters; isolation would add targeted evidence"}

    # PD5 ErrorOnlyFilterBias
    if cls == "PD_ErrorOnlyFilterBias":
        has_err = audit.get("has_status_error_filter", False)
        has_unset = audit.get("has_status_unset_filter", False)
        if not (has_err and not has_unset):
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": "FAIL",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": f"PD5 requires Error-only filter; has_err={has_err}, has_unset={has_unset}"}
        gt_silent = req.get("gt_is_silent", False)
        if not gt_silent:
            return {"verdict": "redundant",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "FAIL (GT has signal — unset filter unnecessary)",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "FAIL",
                    "reason": "PD5 fires but GT has error signal — unset filter wouldn't help"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "pass (GT silent)",
                "path_alignment_check": "n/a",
                "counterfactual_check": "pass",
                "reason": "PD5: Error-only filter blinds agent to silent GT"}

    # PD6 SurveyWithoutDrill
    if cls == "PD_SurveyWithoutDrill":
        # Approximate: has_jvm/container/k8s/db_metric all False, but has_status_error + many WHERE filters
        drill_count = sum([audit.get(f"has_{k}_metric_substring", False) for k in ("jvm","container","k8s","db")])
        if drill_count <= 1:
            return {"verdict": "agree",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "partial",
                    "reason": f"PD6: only {drill_count} drill layers probed"}
        return {"verdict": "dispute-weak",
                "positive_criteria_check": "partial",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": f"drill_count={drill_count} — agent did drill"}

    # PD7 LateExplorationDegenerate
    if cls == "PD_LateExplorationDegenerate":
        n_sql = y.get("raw_sql_count_total", 0)
        if n_sql >= 40:
            return {"verdict": "agree",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": f"n_sql={n_sql} >= 40, late-phase degeneracy plausible"}
        return {"verdict": "dispute-weak",
                "positive_criteria_check": "FAIL",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": f"n_sql={n_sql} < 40"}

    # PD8 MultiRCCompromise
    if cls == "PD_MultiRCCompromise":
        if len(predicted) >= 2:
            return {"verdict": "agree",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": f"len(root_causes)={len(predicted)}"}
        return {"verdict": "dispute-strong",
                "positive_criteria_check": "FAIL",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": f"len(root_causes)={len(predicted)} < 2"}

    # PD9 TraceFollowAbsent
    if cls == "PD_TraceFollowAbsent":
        tf = audit.get("has_trace_follow_substring", False)
        if tf:
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": "FAIL (trace_follow fired)",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": "PD9 claims no trace_follow but substring audit shows one"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass (no trace_follow)",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "partial",
                "reason": f"PD9: no trace_follow SQL in {y.get('raw_sql_count_total', 0)} SQLs"}

    # --- Framework-specific PDs ---
    if cls == "aiq.PD_StageEndsWithoutCommitment":
        return {"verdict": "unverifiable",
                "positive_criteria_check": "n/a",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": "Requires aiq 3-stage markers not in evidence dump"}

    if cls == "aiq.PD_ReflectionStageWithoutNewProbe":
        return {"verdict": "unverifiable",
                "positive_criteria_check": "n/a",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": "Requires aiq multi-stage probe analysis not in evidence dump"}

    if cls == "aiq.PD_CompressOverwritesTerminator":
        return {"verdict": "unverifiable",
                "positive_criteria_check": "n/a",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": "Requires aiq compress_to_graph analysis not in evidence dump"}

    if cls == "sonnet.PD5_ThinkNarrationDominant":
        return {"verdict": "unverifiable",
                "positive_criteria_check": "n/a",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": "Requires think_tool invocation count not in evidence dump"}

    if cls == "qwen.PD6_ServiceAvgNoSpanMaxDrill":
        joined_sql = "\n".join(y.get("raw_sql_list_sample") or [])
        has_svc_avg = bool(re.search(r"(?is)AVG\s*\(\s*duration\s*\).*?GROUP BY\s+service_name", joined_sql))
        has_span_max = bool(re.search(r"(?is)(MAX|QUANTILE).*?duration.*?GROUP BY\s+span_name", joined_sql))
        if has_svc_avg and not has_span_max:
            return {"verdict": "agree",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "partial",
                    "reason": "Service-level AVG without span-level MAX"}
        return {"verdict": "dispute-weak",
                "positive_criteria_check": f"svc_avg={has_svc_avg}, span_max={has_span_max}",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": "No service-AVG / span-MAX pattern match"}

    if cls == "qwen.PD8_NoChronicityReasoning":
        keywords = ["background", "pre-existing", "chronic", "vs normal", "baseline", "ambient", "not new"]
        has_chronicity = any(k in snip_text for k in keywords)
        if not has_chronicity:
            return {"verdict": "agree",
                    "positive_criteria_check": "pass",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "partial",
                    "reason": "No chronicity keyword in reasoning snippets"}
        return {"verdict": "dispute-strong",
                "positive_criteria_check": "FAIL",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "n/a",
                "reason": "Reasoning contains chronicity keywords"}

    if cls == "claudecode.PD4_GTServiceNotTargetedWithWhere":
        gt_in_filters = any(svc in svc_filters for svc in gt_services)
        if gt_in_filters:
            return {"verdict": "dispute-strong",
                    "positive_criteria_check": "FAIL (GT in WHERE)",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": f"GT {gt_services} is in WHERE filters {svc_filters}"}
        return {"verdict": "agree",
                "positive_criteria_check": "pass",
                "gt_required_capability_check": "n/a",
                "path_alignment_check": "n/a",
                "counterfactual_check": "partial",
                "reason": f"GT {gt_services} not in WHERE filters {svc_filters}"}

    return {"verdict": "unverifiable", "reason": f"Unknown PD class: {cls}"}


def classify_axis(cls: str) -> str:
    if cls.startswith("D") and len(cls) <= 3:
        return "D"
    if cls.startswith("U") or cls.startswith("aiq.R_") or cls.startswith("claudecode.R") or cls.startswith("sonnet.R_") or cls.startswith("qwen.R_"):
        return "R"
    if cls.startswith("PD_") or cls.startswith("aiq.PD") or cls.startswith("claudecode.PD") or cls.startswith("sonnet.PD") or cls.startswith("qwen.PD"):
        return "PD"
    return "unknown"


def main():
    seen = load_existing_verdicts()
    print(f"Resuming from {len(seen)} existing verdicts")

    # Load state
    if STATE_PATH.exists():
        with STATE_PATH.open() as f:
            state = json.load(f)
    else:
        state = {"v_c_progress": {"total": 0, "done": 0, "last_case": None}}

    total = 0
    new = 0
    for yaml_path in sorted(EVIDENCE_DIR.glob("*.yaml")):
        with yaml_path.open() as f:
            doc = yaml.safe_load(f)
        if doc.get("unverifiable"):
            # write unverifiable verdicts for all classes
            agent = doc["case_id"].split(".", 1)[0]
            case_id = int(doc["case_id"].split(".", 1)[1])
            for cls in doc.get("classes_to_verify", []):
                total += 1
                if (agent, case_id, cls) in seen:
                    continue
                append_verdict({
                    "agent": agent,
                    "case_id": case_id,
                    "class": cls,
                    "verdict": "unverifiable",
                    "positive_criteria_check": "n/a",
                    "gt_required_capability_check": "n/a",
                    "path_alignment_check": "n/a",
                    "counterfactual_check": "n/a",
                    "reason": doc.get("reason", "unverifiable YAML"),
                })
                seen.add((agent, case_id, cls))
                new += 1
            continue

        agent = doc["case_id"].split(".", 1)[0]
        case_id = int(doc["case_id"].split(".", 1)[1])

        for cls in doc.get("classes_to_verify", []):
            total += 1
            key = (agent, case_id, cls)
            if key in seen:
                continue
            axis = classify_axis(cls)
            if axis == "D":
                verdict = judge_d(cls, doc)
            elif axis == "R":
                verdict = judge_r(cls, doc)
            elif axis == "PD":
                verdict = judge_pd(cls, doc)
            else:
                verdict = {"verdict": "unverifiable", "reason": f"Unknown axis for class {cls}"}
            row = {"agent": agent, "case_id": case_id, "class": cls, "axis": axis, **verdict}
            append_verdict(row)
            seen.add(key)
            new += 1
            if new % 10 == 0:
                state["v_c_progress"] = {"total": total, "done": len(seen), "last_case": f"{agent}.{case_id}"}
                atomic_write_state(state)

    state["v_c_progress"] = {"total": total, "done": len(seen), "last_case": None}
    atomic_write_state(state)
    print(f"Total slots: {total}, new verdicts this run: {new}, total verdicts: {len(seen)}")


if __name__ == "__main__":
    main()
