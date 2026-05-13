"""X-5/X-6: Apply relabel queue mechanically + re-run V-C judges → produce v3 verdicts.

Algorithm for each (agent, case_id, class) in relabel_queue.v2.jsonl:
  - action=remove_label  → DROP this verdict row from v3 pool entirely
  - action=relabel_class → CHANGE class to new_class; re-judge with appropriate axis judge fn
  - action=skip_human    → keep original verdict from v2 (mark `human_pending=True`)

For verdicts not in the queue (i.e. agree / unverifiable) → keep original v2 verdict.

Inputs: verify_verdicts.v2.jsonl, relabel_queue.v2.jsonl, verify_evidence/*.yaml
Output: verify_verdicts.v3.jsonl, applied_relabels.v3.jsonl (audit), verify_mismatch_report.v3.md
"""
from __future__ import annotations
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
import yaml

ROOT = Path("analysis/3-failure-modes/merged")
EVIDENCE_DIR = ROOT / "verify_evidence"
V2_VERDICTS = ROOT / "verify_verdicts.v2.jsonl"
QUEUE = ROOT / "relabel_queue.v2.jsonl"

V3_VERDICTS = Path(os.environ.get("V3_VERDICTS_PATH", ROOT / "verify_verdicts.v3.jsonl"))
APPLIED_AUDIT = Path(os.environ.get("APPLIED_AUDIT_PATH", ROOT / "applied_relabels.v3.jsonl"))

sys.path.insert(0, str(Path(__file__).parent))
import importlib.util
_spec = importlib.util.spec_from_file_location("verify_adjudicate", str(Path(__file__).parent / "verify_adjudicate.py"))
adj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adj)


def load_yaml_for_case(agent: str, case_id: int) -> dict | None:
    p = EVIDENCE_DIR / f"{agent}_case_{case_id}.yaml"
    if not p.exists():
        return None
    with p.open() as f:
        return yaml.safe_load(f)


def judge_for_class(cls: str, doc: dict) -> dict:
    axis = adj.classify_axis(cls)
    if axis == "D":
        return adj.judge_d(cls, doc)
    if axis == "R":
        return adj.judge_r(cls, doc)
    if axis == "PD":
        return adj.judge_pd(cls, doc)
    return {"verdict": "unverifiable", "reason": f"unknown axis for {cls}"}


def main():
    # Load v2 verdicts
    v2 = []
    with V2_VERDICTS.open() as f:
        for line in f:
            v2.append(json.loads(line))
    print(f"v2 verdicts: {len(v2)}")

    # Load queue, index by (agent, case_id, class)
    queue: dict[tuple, dict] = {}
    with QUEUE.open() as f:
        for line in f:
            r = json.loads(line)
            queue[(r["agent"], r["case_id"], r["class"])] = r

    # For each v2 verdict, apply queue action
    out_rows = []
    audit_rows = []
    counts = Counter()
    yaml_cache: dict[tuple, dict] = {}

    for v in v2:
        key = (v["agent"], v["case_id"], v["class"])
        action_row = queue.get(key)
        if action_row is None:
            # Either agree or unverifiable - keep as-is
            out_rows.append({**v, "_v3_action": "kept"})
            counts[("kept", v.get("verdict"))] += 1
            continue

        action = action_row.get("action")
        if action == "remove_label":
            audit_rows.append({**action_row, "_op": "removed"})
            counts[("remove_label", v.get("verdict"))] += 1
            # do not add to v3
            continue
        if action == "skip_human":
            out_rows.append({**v, "_v3_action": "skip_human", "_human_pending": True})
            counts[("skip_human", v.get("verdict"))] += 1
            continue
        if action == "relabel_class":
            new_cls = action_row.get("new_class") or ""
            # If new_cls is e.g. "U1 or U3" - pick first option
            new_cls_parsed = new_cls.split(" or ")[0].strip()
            # Some R suggestions are not full class names — map U1 → U1_LoudnessAnchorOverSilentVictim
            cls_full = _resolve_class(new_cls_parsed, v["class"])
            if cls_full is None:
                # Fall back to remove_label
                audit_rows.append({**action_row, "_op": "removed_unresolved", "tried": new_cls_parsed})
                counts[("relabel_unresolved", v.get("verdict"))] += 1
                continue
            # Re-judge with new class
            cache_key = (v["agent"], v["case_id"])
            doc = yaml_cache.get(cache_key)
            if doc is None:
                doc = load_yaml_for_case(v["agent"], v["case_id"])
                yaml_cache[cache_key] = doc
            if doc is None:
                # YAML missing - keep original
                out_rows.append({**v, "_v3_action": "yaml_missing"})
                counts[("yaml_missing", v.get("verdict"))] += 1
                continue
            new_axis = adj.classify_axis(cls_full)
            new_verdict = judge_for_class(cls_full, doc)
            new_row = {
                "agent": v["agent"],
                "case_id": v["case_id"],
                "class": cls_full,
                "axis": new_axis,
                **new_verdict,
                "_v3_action": "relabeled",
                "_v3_from_class": v["class"],
            }
            out_rows.append(new_row)
            audit_rows.append({**action_row, "_op": "relabeled", "from_class": v["class"], "to_class": cls_full,
                               "new_verdict": new_verdict.get("verdict")})
            counts[("relabel_class", new_verdict.get("verdict"))] += 1
            continue
        # unknown action
        out_rows.append({**v, "_v3_action": "unknown_action"})
        counts[("unknown_action", v.get("verdict"))] += 1

    # Write outputs (atomic via temp+rename)
    _write_jsonl(V3_VERDICTS, out_rows)
    _write_jsonl(APPLIED_AUDIT, audit_rows)

    # Stats
    n_v3 = len(out_rows)
    n_v3_agree = sum(1 for r in out_rows if r.get("verdict") == "agree")
    print(f"v3 pool size: {n_v3}")
    print(f"v3 agree: {n_v3_agree} ({100*n_v3_agree/max(n_v3,1):.1f}%)")
    print()
    by_action = Counter()
    by_action_verdict = Counter()
    for r in out_rows:
        a = r.get("_v3_action", "?")
        by_action[a] += 1
        by_action_verdict[(a, r.get("verdict"))] += 1
    print("v3 rows by _v3_action:")
    for k, v in by_action.most_common():
        print(f"  {k}: {v}")
    print()
    print("Top transitions (v2_action, new_verdict):")
    for k, v in counts.most_common(20):
        print(f"  {k}: {v}")


def _resolve_class(short_or_full: str, original_cls: str) -> str | None:
    """Map a short class hint (e.g. 'U1', 'U2 or U3') to a full class name."""
    if not short_or_full:
        return None
    s = short_or_full.strip()
    # If already full - return
    full_class_names = {
        "U1": "U1_LoudnessAnchorOverSilentVictim",
        "U2": "U2_ChronicAmbientNoiseAnchor",
        "U3": "U3_EdgeDirectionOrRegionEndpointError",
        "U4": "U4_NameTwinSiblingConfusion",
        "U5": "U5_SilenceReadAsHealthOrPaused",
        "D1": "D1", "D2": "D2", "D3": "D3", "D4": "D4", "D5": "D5", "D6": "D6", "D7": "D7",
    }
    if s.startswith("U") and len(s) <= 3:
        return full_class_names.get(s)
    if s.startswith("D") and len(s) <= 3:
        return full_class_names.get(s, s)
    if s in full_class_names.values():
        return s
    if s.startswith("PD_") or s.startswith("aiq.") or s.startswith("claudecode.") or s.startswith("sonnet.") or s.startswith("qwen."):
        return s
    return None


def _write_jsonl(path: Path, rows: list[dict]):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
            f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


if __name__ == "__main__":
    main()
