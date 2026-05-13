"""
v4 forensic extraction: per-case JSON cache for the 53 stable failure cases.

For each dataset_index, joins:
  - GT (rc_service, propagation, fault) from baseline meta + difficulty
  - baseline trajectory: predicted RC + last 8 think_tool reflections
  - v4 trajectory: predicted RC + parsed interventions (mid + conclusion) +
    agent's response after each intervention (next think_tool reflection / next assistant content)
  - transition: wrong->correct or wrong->wrong

Cache schema written to cache/<dataset_index>.json:
  {
    "dataset_index", "tier", "primary_theme", "case_name", "datapack",
    "fault_category", "fault_type", "spl",
    "transition": "wrong->correct" | "wrong->wrong",
    "gt": {
        "rc_service": [...], "rc_pod": [...], "rc_function": [...], "rc_metric": [...],
        "propagation": {"nodes": [...], "edges": [...], "root_causes": [...]}
    },
    "baseline": {
        "predicted_rc": [...], "n_qpf": int, "correct": false,
        "reasoning_excerpts": [str x ~6, last think_tool reflections]
    },
    "v4": {
        "predicted_rc": [...], "n_qpf": int, "correct": bool,
        "interventions": [
            {
                "phase": "mid"|"conclusion",
                "primary": "Mx",
                "secondary": ["Mx", ...],
                "round_at_inject": int,         # round count of agent BEFORE intervention
                "intervention_text": str (full),
                "agent_response_excerpt": str  # next assistant content / next reflection (truncated)
            }, ...
        ],
        "post_mid_tool_rounds": int,
        "post_conclusion_tool_rounds": int,
        "final_reasoning_excerpts": [str x ~6, last think_tool reflections in v4 trajectory]
    }
  }
"""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("UTU_DB_URL", "postgresql://postgres:postgres@localhost:5433/SOTA-Agents")
from sqlalchemy import create_engine, text  # noqa: E402

ROOT = Path("/home/nn/SOTA-agents")
STABLE_SET = ROOT / "analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/k5_resample/stable_failure_set_k5.jsonl"
CACHE_DIR = ROOT / "analysis/4-middleware/v4_forensic/cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BASELINE_EXP = "thinkdepthai-qwen3.5-plus"
V4_EXP = "thinkdepthai-qwen3.5-plus-2026-02-15-mw-v4-run"

ADV_RE = re.compile(
    r"\[Investigation Advisor\s*[—\-]\s*v4\]\s*phase=(\w+)\s+primary=(\w+)(?:\s+secondary=(\S+))?",
    re.IGNORECASE,
)


def get_correct_answer_payload(raw_meta: dict, correct_answer: str | None) -> dict:
    diff = raw_meta.get("difficulty") or {}
    rc_service = []
    if correct_answer:
        # correct_answer can be a string like "ts-order-service" or comma-separated
        rc_service = [s.strip() for s in correct_answer.split(",") if s.strip()]
    return {
        "rc_service": rc_service,
        "fault_category": diff.get("fault_category"),
        "fault_type": diff.get("fault_type"),
        "spl": diff.get("spl"),
        "n_svc": diff.get("n_svc"),
        "n_edge": diff.get("n_edge"),
    }


def parse_predicted_rc(meta: dict, response_str: str) -> list[str]:
    cge = (meta or {}).get("causal_graph_evaluation") or {}
    rc = cge.get("root_cause_services")
    if rc:
        return rc
    try:
        resp = json.loads(response_str) if isinstance(response_str, str) else (response_str or {})
        rcs = resp.get("root_causes", [])
        out = []
        for r in rcs:
            comp = r.get("component") if isinstance(r, dict) else None
            if comp:
                # parse "container|ts-foo" -> "ts-foo"
                if "|" in comp:
                    out.append(comp.split("|", 1)[1])
                else:
                    out.append(comp)
        return out
    except Exception:
        return []


def count_rounds_with_tool_calls(traj: list[dict]) -> int:
    return sum(1 for m in traj if m.get("role") == "assistant" and m.get("tool_calls"))


def extract_think_reflections(traj: list[dict], limit: int = 6) -> list[str]:
    """Find tool messages whose content starts with 'Reflection recorded:' (think_tool output)."""
    refs = []
    for m in traj:
        if m.get("role") == "tool":
            c = m.get("content") or ""
            if c.startswith("Reflection recorded:"):
                # Grab the full reflection (often multi-line; cap at ~600 chars)
                refs.append(c.replace("Reflection recorded:", "").strip()[:600])
    return refs[-limit:]


def parse_v4_interventions(traj: list[dict]) -> list[dict]:
    """Find user-role messages with [Investigation Advisor — v4] markers."""
    out = []
    for i, m in enumerate(traj):
        if m.get("role") != "user":
            continue
        content = m.get("content") or ""
        match = ADV_RE.search(content)
        if not match:
            continue
        phase = match.group(1).lower()
        primary = match.group(2)
        sec_raw = match.group(3) or ""
        # secondary may be "[M5,M6]" or "M5" or "[]" or "None"
        secondary = []
        if sec_raw and sec_raw not in ("[]", "None", "none", "null"):
            sec_raw_clean = sec_raw.strip("[]")
            secondary = [s.strip() for s in sec_raw_clean.split(",") if s.strip()]
        # Round count up to (not including) this user message
        rounds_before = sum(
            1 for k in range(i) if traj[k].get("role") == "assistant" and traj[k].get("tool_calls")
        )
        # Find next think reflection / assistant content after this intervention (within next 10 messages)
        agent_response = ""
        for j in range(i + 1, min(i + 12, len(traj))):
            mj = traj[j]
            if mj.get("role") == "tool":
                c = mj.get("content") or ""
                if c.startswith("Reflection recorded:"):
                    agent_response = c.replace("Reflection recorded:", "").strip()[:800]
                    break
            elif mj.get("role") == "assistant" and not mj.get("tool_calls") and (mj.get("content") or "").strip():
                agent_response = (mj.get("content") or "").strip()[:800]
                break
        # Tool rounds after this intervention
        post_tool_rounds = sum(
            1 for k in range(i + 1, len(traj))
            if traj[k].get("role") == "assistant" and traj[k].get("tool_calls")
        )
        out.append({
            "phase": phase,
            "primary": primary,
            "secondary": secondary,
            "round_at_inject": rounds_before,
            "intervention_text": content,
            "agent_response_excerpt": agent_response,
            "post_intervention_tool_rounds": post_tool_rounds,
            "_msg_index": i,
        })
    return out


def main():
    rows = [json.loads(l) for l in STABLE_SET.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(rows)} stable failure cases", flush=True)

    eng = create_engine(os.environ["UTU_DB_URL"])
    with eng.connect() as c:
        # Pre-fetch all baseline + v4 records to avoid 53*2 round-trips
        idx_list = [r["dataset_index"] for r in rows]

        baseline_rows = c.execute(text("""
            SELECT dataset_index, correct, response, meta::text, trajectories::text, correct_answer
            FROM evaluation_data WHERE exp_id=:e AND dataset_index = ANY(:idx)
        """), {"e": BASELINE_EXP, "idx": idx_list}).fetchall()
        v4_rows = c.execute(text("""
            SELECT dataset_index, correct, response, meta::text, trajectories::text, correct_answer
            FROM evaluation_data WHERE exp_id=:e AND dataset_index = ANY(:idx)
        """), {"e": V4_EXP, "idx": idx_list}).fetchall()

    bmap = {r[0]: r for r in baseline_rows}
    vmap = {r[0]: r for r in v4_rows}
    print(f"Baseline records: {len(bmap)}, v4 records: {len(vmap)}", flush=True)

    written = 0
    skipped = []
    for row in rows:
        di = row["dataset_index"]
        bl = bmap.get(di)
        v4 = vmap.get(di)
        if not bl or not v4:
            skipped.append((di, "missing baseline" if not bl else "missing v4"))
            continue

        bl_meta = json.loads(bl[3]) if bl[3] else {}
        v4_meta = json.loads(v4[3]) if v4[3] else {}
        bl_traj = json.loads(bl[4]) if bl[4] else []
        v4_traj = json.loads(v4[4]) if v4[4] else []

        gt = get_correct_answer_payload(bl_meta, bl[5])

        bl_pred = parse_predicted_rc(bl_meta, bl[2])
        v4_pred = parse_predicted_rc(v4_meta, v4[2])

        v4_interv = parse_v4_interventions(v4_traj)

        # Fix per-intervention post_tool_rounds: should be tool rounds BETWEEN this intervention
        # and the next intervention (or end of trajectory)
        for k, intv in enumerate(v4_interv):
            this_idx = intv["_msg_index"]
            next_idx = v4_interv[k + 1]["_msg_index"] if k + 1 < len(v4_interv) else len(v4_traj)
            tool_rounds = sum(
                1 for j in range(this_idx + 1, next_idx)
                if v4_traj[j].get("role") == "assistant" and v4_traj[j].get("tool_calls")
            )
            intv["post_intervention_tool_rounds"] = tool_rounds
            intv.pop("_msg_index", None)

        out = {
            "dataset_index": di,
            "tier": row.get("tier"),
            "primary_theme": row.get("primary_theme"),
            "case_name": row.get("case_name"),
            "datapack": row.get("datapack"),
            "fault_category": row.get("fault_category"),
            "fault_type": row.get("fault_type"),
            "spl": row.get("spl"),
            "transition": "wrong->correct" if v4[1] else "wrong->wrong",
            "gt": gt,
            "baseline": {
                "predicted_rc": bl_pred,
                "n_qpf": count_rounds_with_tool_calls(bl_traj),
                "correct": bool(bl[1]),
                "reasoning_excerpts": extract_think_reflections(bl_traj, limit=8),
            },
            "v4": {
                "predicted_rc": v4_pred,
                "n_qpf": count_rounds_with_tool_calls(v4_traj),
                "correct": bool(v4[1]),
                "interventions": v4_interv,
                "n_interventions": len(v4_interv),
                "final_reasoning_excerpts": extract_think_reflections(v4_traj, limit=8),
            },
        }
        (CACHE_DIR / f"{di}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
        written += 1

    print(f"\nWrote {written} cache files to {CACHE_DIR}", flush=True)
    if skipped:
        print(f"Skipped {len(skipped)}:", skipped, flush=True)


if __name__ == "__main__":
    main()
