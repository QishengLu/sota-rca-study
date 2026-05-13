"""One-time extraction: build per-case JSON cache for MW vs w/o MW analysis.

Pulls baseline (`thinkdepthai-qwen3.5-plus`) and MW (`thinkdepthai-qwen3.5-plus-mw-v3`)
records for the 105 MW dataset_indexes, joins with on-disk injection.json /
causal_graph.json, and writes one cache file per case to ./mw_vs_womw_cache/.

Run once:
    cd RCAgentEval && uv run python scripts/mw_vs_womw_extract.py

Output: scripts/mw_vs_womw_cache/<dataset_index>.json (105 files)
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(str(Path(__file__).resolve().parents[5]))
EVAL_ROOT = REPO_ROOT / "RCAgentEval"
sys.path.insert(0, str(EVAL_ROOT))

os.environ.setdefault(
    "UTU_DB_URL",
    "postgresql://postgres:postgres@localhost:5433/SOTA-Agents",
)

from sqlalchemy import create_engine, text  # noqa: E402

from sota_rca.analysis.extractor import classify_intent  # noqa: E402

CACHE_DIR = EVAL_ROOT / "scripts" / "mw_vs_womw_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BASELINE_EXP = "thinkdepthai-qwen3.5-plus"
MW_EXP = "thinkdepthai-qwen3.5-plus-mw-v3"

PHASE_MAP = {
    "latency_ranking": "triage", "throughput_compare": "triage",
    "error_rate_scan": "triage", "error_log_overview": "triage",
    "metric_scan": "triage",
    "service_trace_scan": "trace", "trace_follow": "trace",
    "call_tree_build": "trace",
    "service_error_log": "log", "service_log_browse": "log",
    "keyword_search": "log", "error_timeline": "log",
    "container_resource": "metric", "jvm_state": "metric",
    "network_layer": "metric", "k8s_state": "metric", "db_state": "metric",
    "baseline_collect": "baseline", "baseline_contrast": "baseline",
}
ALL_PHASES = {"triage", "trace", "log", "metric", "baseline"}

ADVISOR_PROC_RE = re.compile(r"\[Investigation Advisor\s*[—\-]\s*([A-Z]\d|M\d)\]")
ADVISOR_CONC_RE = re.compile(r"\[Investigation Advisor\s*[—\-]\s*Pre-Conclusion Review\]")
TS_SVC_RE = re.compile(r"\bts-[a-z][a-z0-9\-]*[a-z0-9]\b", re.IGNORECASE)


# ── Helpers ──────────────────────────────────────────────────────────────────


def parse_json_field(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def extract_services_from_sql(sql: str) -> list[str]:
    if not sql:
        return []
    found = set()
    for m in TS_SVC_RE.findall(sql.lower()):
        found.add(m)
    return sorted(found)


def derive_data_dir(source: str, baseline_meta: dict) -> Path:
    sdd = baseline_meta.get("source_data_dir") if baseline_meta else None
    if sdd and Path(sdd).exists():
        return Path(sdd)
    return REPO_ROOT / "RCAgentEval" / "data" / source / "converted"


def load_gt(data_dir: Path, baseline_meta: dict) -> dict:
    gt: dict = {
        "injection": {},
        "rc_service": [],
        "rc_pod": [],
        "rc_container": [],
        "rc_function": [],
        "rc_metric": [],
        "fault_type_int": None,
        "propagation": {"nodes": [], "edges": []},
        "data_dir_exists": data_dir.exists(),
        "data_dir": str(data_dir),
    }

    inj_path = data_dir / "injection.json"
    if inj_path.exists():
        try:
            inj = json.loads(inj_path.read_text())
            gt["injection"] = {
                "injection_name": inj.get("injection_name"),
                "fault_type": inj.get("fault_type"),
                "start_time": inj.get("start_time"),
                "end_time": inj.get("end_time"),
                "display_config": inj.get("display_config"),
            }
            ground = inj.get("ground_truth") or {}
            gt["rc_service"] = ground.get("service") or []
            gt["rc_pod"] = ground.get("pod") or []
            gt["rc_container"] = ground.get("container") or []
            gt["rc_function"] = ground.get("function") or []
            gt["rc_metric"] = ground.get("metric") or []
            gt["fault_type_int"] = inj.get("fault_type")
        except Exception as exc:  # noqa: BLE001
            gt["injection_error"] = str(exc)

    cg_path = data_dir / "causal_graph.json"
    if cg_path.exists():
        try:
            cg = json.loads(cg_path.read_text())
            nodes = cg.get("nodes") or []
            edges = cg.get("edges") or []
            simplified_nodes = []
            for n in nodes:
                simplified_nodes.append({
                    "component": n.get("component"),
                    "state": n.get("state") or [],
                })
            simplified_edges = []
            for e in edges:
                simplified_edges.append({
                    "source": e.get("source"),
                    "target": e.get("target"),
                })
            gt["propagation"]["nodes"] = simplified_nodes
            gt["propagation"]["edges"] = simplified_edges
            gt["propagation"]["root_causes"] = cg.get("root_causes") or []
        except Exception as exc:  # noqa: BLE001
            gt["causal_graph_error"] = str(exc)

    if not gt["rc_service"]:
        bgt = (baseline_meta or {}).get("ground_truth") or {}
        if isinstance(bgt, dict):
            gt["rc_service"] = bgt.get("service") or []
            gt["rc_pod"] = gt["rc_pod"] or bgt.get("pod") or []
            gt["rc_container"] = gt["rc_container"] or bgt.get("container") or []
            gt["rc_function"] = gt["rc_function"] or bgt.get("function") or []
            gt["rc_metric"] = gt["rc_metric"] or bgt.get("metric") or []

    return gt


def normalize_traj_message(m: dict) -> dict:
    """Normalize one trajectory message to {role, content, tool_calls}."""
    role = m.get("role") or m.get("type") or "unknown"
    content = m.get("content") or ""
    if not isinstance(content, str):
        try:
            content = json.dumps(content)
        except Exception:  # noqa: BLE001
            content = str(content)

    tcs_out: list[dict] = []
    for tc in m.get("tool_calls") or []:
        if not isinstance(tc, dict):
            continue
        if "function" in tc and isinstance(tc["function"], dict):
            name = tc["function"].get("name", "")
            args_raw = tc["function"].get("arguments", "")
        else:
            name = tc.get("name", "")
            args_raw = tc.get("args") or tc.get("arguments") or ""
        args: dict
        if isinstance(args_raw, dict):
            args = args_raw
        else:
            try:
                args = json.loads(args_raw) if args_raw else {}
            except (json.JSONDecodeError, TypeError):
                args = {"_raw": str(args_raw)[:200]}
        tcs_out.append({"name": name, "args": args})
    return {"role": role, "content": content, "tool_calls": tcs_out}


def detect_conclusion_check(msgs: list[dict]) -> dict:
    """Detect the (invisible) pre-conclusion HumanMessage injection.

    The conclusion check fires when agent first produces an assistant message with
    no tool_calls. It mutates state via a buggy LangGraph conditional edge, so the
    HumanMessage never appears in the trajectory — but the next llm_call IS invoked
    and produces a NEW assistant message reading the (in-memory) intervention. The
    signature is: msg[i].role=='assistant' AND not msg[i].tool_calls AND
    msg[i+1].role=='assistant'. Two follow-up modes:
      - 'rewrite':       msg[i+1] also has no tool_calls (agent ignored the prompt)
      - 'back_to_tools': msg[i+1] has tool_calls (agent took the prompt seriously)

    Per-case at most 1 (state.conclusion_checked flag).
    """
    out = {
        "triggered": False,
        "loopback_index": None,
        "mode": None,
        "distance_from_end": None,
        "response_excerpt": None,
        "post_intervention_tool_rounds": 0,
    }
    n = len(msgs)
    for i in range(n - 1):
        mi = msgs[i]
        mj = msgs[i + 1]
        if (mi.get("role") == "assistant" and not mi.get("tool_calls")
                and mj.get("role") == "assistant"):
            out["triggered"] = True
            out["loopback_index"] = i
            out["distance_from_end"] = (n - 1) - i
            if mj.get("tool_calls"):
                out["mode"] = "back_to_tools"
                # Count tool rounds between intervention and final conclude
                rounds = 0
                for k in range(i + 1, n):
                    if msgs[k].get("role") == "assistant" and msgs[k].get("tool_calls"):
                        rounds += 1
                out["post_intervention_tool_rounds"] = rounds
            else:
                out["mode"] = "rewrite"
            out["response_excerpt"] = (mj.get("content") or "")[:500]
            break
    return out


def analyze_trajectory(raw_traj: Any) -> dict:
    """Return per-run analysis: intents, phases, services, reasoning, advisors."""
    traj = parse_json_field(raw_traj) or []
    out: dict = {
        "n_messages": len(traj),
        "n_assistant": 0,
        "n_tool": 0,
        "n_user": 0,
        "n_qpf": 0,
        "n_think": 0,
        "intents": [],
        "intent_counts": {},
        "phases_visited": [],
        "phases_missing": [],
        "services_investigated": [],
        "reasoning_excerpts": [],
        "advisors": [],
        "qpf_to_advisor_distance": [],
        "first_qpf_data_dir": None,
    }

    msgs = [normalize_traj_message(m) if isinstance(m, dict) else {"role": "?", "content": "", "tool_calls": []} for m in traj]

    qpf_global_idx = 0
    services: set[str] = set()
    intents: list[dict] = []
    reasoning: list[str] = []
    advisors: list[dict] = []

    for i, m in enumerate(msgs):
        role = m["role"]
        content = m["content"]
        if role == "assistant":
            out["n_assistant"] += 1
        elif role == "tool":
            out["n_tool"] += 1
        elif role == "user":
            out["n_user"] += 1

        # Detect Investigation Advisor injection (always under role=user)
        if role == "user" and "Investigation Advisor" in content:
            mt = ADVISOR_PROC_RE.search(content)
            if mt:
                did = mt.group(1)
                phase = "process"
            elif ADVISOR_CONC_RE.search(content):
                did = "PRECONC"
                phase = "conclusion"
            else:
                did = "?"
                phase = "unknown"
            advisors.append({
                "msg_index": i,
                "deficiency": did,
                "phase": phase,
                "qpf_at_inject": qpf_global_idx,
                "prompt_excerpt": content[:400],
            })

        # Walk this message's tool_calls
        for tc in m["tool_calls"]:
            name = tc["name"]
            args = tc["args"]
            if name == "query_parquet_files":
                out["n_qpf"] += 1
                qpf_global_idx += 1
                sql = args.get("query", "") if isinstance(args, dict) else ""
                intent = classify_intent("query_parquet_files", sql)
                if intent != "discovery":
                    intents.append({
                        "qpf_index": qpf_global_idx,
                        "intent": intent,
                        "phase": PHASE_MAP.get(intent, "unknown"),
                        "services": extract_services_from_sql(sql),
                        "sql_excerpt": sql[:160],
                    })
                services.update(extract_services_from_sql(sql))
            elif name == "think_tool":
                out["n_think"] += 1
                refl = args.get("reflection", "") if isinstance(args, dict) else ""
                if refl:
                    reasoning.append(refl[:300])
            elif name == "list_tables_in_directory" and out["first_qpf_data_dir"] is None:
                d = args.get("directory") if isinstance(args, dict) else None
                if d:
                    out["first_qpf_data_dir"] = d

    # Aggregate
    intent_counts: dict[str, int] = {}
    for i in intents:
        intent_counts[i["intent"]] = intent_counts.get(i["intent"], 0) + 1
    phases = {i["phase"] for i in intents if i["phase"] != "unknown"}

    out["intents"] = intents
    out["intent_counts"] = intent_counts
    out["phases_visited"] = sorted(phases)
    out["phases_missing"] = sorted(ALL_PHASES - phases)
    out["services_investigated"] = sorted(services)
    out["reasoning_excerpts"] = reasoning[-8:]  # last 8 reflections (most relevant to conclusion)
    out["advisors"] = advisors
    out["conclusion_check"] = detect_conclusion_check(msgs)

    return out


def derive_predicted_rc(meta: dict, response_str: str) -> dict:
    """Best-effort root cause extraction from causal_graph_evaluation or response JSON."""
    out = {"root_cause_services": [], "judge_correct": None, "judge_reasoning": None}
    cge = (meta or {}).get("causal_graph_evaluation") or {}
    if isinstance(cge, dict):
        rcs = cge.get("root_cause_services")
        if isinstance(rcs, list):
            out["root_cause_services"] = rcs
        out["judge_correct"] = cge.get("correct")
        out["judge_reasoning"] = (cge.get("reasoning") or "")[:400]
    if not out["root_cause_services"] and response_str:
        try:
            resp = json.loads(response_str)
            rc = resp.get("root_causes") or []
            if isinstance(rc, list):
                out["root_cause_services"] = [
                    (r.get("component") if isinstance(r, dict) else str(r))
                    for r in rc
                ]
        except (json.JSONDecodeError, TypeError):
            pass
    return out


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    engine = create_engine(os.environ["UTU_DB_URL"])
    written = 0
    skipped = 0

    with engine.connect() as conn:
        # Pull all 105 MW rows
        mw_rows = conn.execute(text("""
            SELECT dataset_index, source, correct, response, meta, trajectories,
                   time_cost
            FROM evaluation_data
            WHERE exp_id = :exp
            ORDER BY dataset_index
        """), {"exp": MW_EXP}).fetchall()

        print(f"[mw] {len(mw_rows)} rows", file=sys.stderr)

        for mw in mw_rows:
            di = mw[0]
            source = mw[1]
            mw_correct = bool(mw[2])
            mw_resp = mw[3] or ""
            mw_meta = parse_json_field(mw[4]) or {}
            mw_traj_raw = mw[5]
            mw_time = mw[6]

            base = conn.execute(text("""
                SELECT correct, response, meta, trajectories, time_cost
                FROM evaluation_data
                WHERE exp_id = :exp AND dataset_index = :di
            """), {"exp": BASELINE_EXP, "di": di}).fetchone()

            if base is None:
                print(f"[skip] dataset_index={di} not in baseline", file=sys.stderr)
                skipped += 1
                continue

            base_correct = bool(base[0])
            base_resp = base[1] or ""
            base_meta = parse_json_field(base[2]) or {}
            base_traj_raw = base[3]
            base_time = base[4]

            # Difficulty: prefer MW, fallback to baseline (covers the 6 NULL-on-MW cases)
            difficulty = (mw_meta.get("difficulty") or {}).copy()
            if not difficulty:
                difficulty = (base_meta.get("difficulty") or {}).copy()

            data_dir = derive_data_dir(source, base_meta)
            gt = load_gt(data_dir, base_meta)

            transition = (
                "wrong→correct" if (not base_correct and mw_correct)
                else "wrong→wrong" if (not base_correct and not mw_correct)
                else "correct→wrong" if (base_correct and not mw_correct)
                else "correct→correct"
            )

            no_mw = analyze_trajectory(base_traj_raw)
            mw_run = analyze_trajectory(mw_traj_raw)

            no_mw["predicted"] = derive_predicted_rc(base_meta, base_resp)
            mw_run["predicted"] = derive_predicted_rc(mw_meta, mw_resp)
            no_mw["correct"] = base_correct
            mw_run["correct"] = mw_correct
            no_mw["time_cost"] = base_time
            mw_run["time_cost"] = mw_time

            cache_obj = {
                "dataset_index": di,
                "source": source,
                "transition": transition,
                "fault_category": difficulty.get("fault_category"),
                "fault_type": difficulty.get("fault_type"),
                "difficulty": difficulty,
                "gt": gt,
                "no_mw": no_mw,
                "mw": mw_run,
            }

            out_path = CACHE_DIR / f"{di}.json"
            out_path.write_text(json.dumps(cache_obj, ensure_ascii=False, indent=2))
            written += 1

    print(f"[done] wrote={written} skipped={skipped} -> {CACHE_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
