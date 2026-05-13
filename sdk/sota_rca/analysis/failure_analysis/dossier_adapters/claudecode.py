"""Build sample dossiers for claudecode-qwen3.5-plus failed cases.

Round definition (per user 2026-04-16):
    A round = one assistant turn that issues tool calls + all corresponding tool results.
    Each tool call within a round is a numbered step, labeled in issue order.
    Any reasoning messages (pure [thinking] content, no tool_calls) preceding
    the tool-issuing assistant message are attached to that round as 'reasoning_before'.

Adapter v3 (claudecode):
    SQL extraction: regex over Bash command arg for `duckdb ... "SQL"` / `'SQL'`.
    Reasoning extraction: [thinking] blocks inside assistant content strings.
"""
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("UTU_DB_URL", "postgresql://postgres:postgres@localhost:5433/SOTA-Agents")
sys.path.insert(0, "RCAgentEval")

import duckdb
import sqlmodel
from sqlalchemy import text
from sota_rca.runner._fallback_db import EvaluationSample  # was: from utu.db.eval_datapoint import DatasetSample, EvaluationSample
from sota_rca.utils.sqlmodel_utils import SQLModelUtils

OUT_DIR = Path("analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Quoting scheme for `duckdb -c "..."` — outer quote is typically " and inner SQL
# literals use '. Match the OUTER quote type and capture until the matching one.
DUCKDB_SQL_DQ_RE = re.compile(r'duckdb\b[^"\n]*?-c\s+"((?:\\"|[^"])+)"', re.DOTALL)
DUCKDB_SQL_SQ_RE = re.compile(r"duckdb\b[^'\n]*?-c\s+'((?:\\'|[^'])+)'", re.DOTALL)
THINKING_RE = re.compile(r"\[thinking\]\s*(.+?)(?=\n\s*\n|\Z)", re.DOTALL)


def extract_sql_from_bash(bash_args: str) -> str | None:
    """Extract the SQL string inside a `duckdb ... "SQL"` command.

    Handles both double-quoted and single-quoted outer SQL and preserves
    inner quotes of the opposite type (e.g. `'Error'` inside a "..." command).
    """
    try:
        obj = json.loads(bash_args) if bash_args.startswith("{") else None
    except Exception:
        obj = None
    cmd = (obj or {}).get("command", bash_args) if obj else bash_args
    if "duckdb" not in cmd.lower():
        return None
    m = DUCKDB_SQL_DQ_RE.search(cmd) or DUCKDB_SQL_SQ_RE.search(cmd)
    if not m:
        return None
    sql = m.group(1)
    # Un-escape the outer quote character
    sql = sql.replace('\\"', '"').replace("\\'", "'").strip()
    return sql


def extract_services_from_sql(sql: str) -> list[str]:
    """Find service names referenced in WHERE/LIKE/FROM clauses."""
    if not sql:
        return []
    services = set()
    for m in re.finditer(r"service_name\s*=\s*'([^']+)'", sql):
        services.add(m.group(1))
    for m in re.finditer(r"service_name\s+LIKE\s+'%([^%']+)%'", sql):
        services.add(m.group(1))
    for m in re.finditer(r"'(ts-[a-z0-9-]+(?:-service)?)'", sql):
        services.add(m.group(1))
    return sorted(s for s in services if s.startswith("ts-") or s == "mysql")


def extract_thinking(content: str) -> str | None:
    if not content or "[thinking]" not in content:
        return None
    matches = THINKING_RE.findall(content)
    return "\n\n".join(m.strip() for m in matches) if matches else None


def _extract_step(tc: dict, step_idx: int) -> dict:
    fn = tc.get("function") or {}
    name = fn.get("name") or tc.get("name", "?")
    args_raw = fn.get("arguments") or tc.get("arguments") or ""
    if isinstance(args_raw, dict):
        args_str = json.dumps(args_raw, ensure_ascii=False)
    else:
        args_str = str(args_raw)
    sql = extract_sql_from_bash(args_str) if name == "Bash" else None
    services = extract_services_from_sql(sql) if sql else []
    return {
        "step": step_idx,
        "tool": name,
        "args_raw": args_str[:800],
        "sql": sql,
        "services": services,
    }


def group_into_rounds(traj: list[dict]) -> list[dict]:
    """Group messages into rounds per user's definition.

    One round = all consecutive tool invocations (possibly spread across multiple
    assistant messages, each with one or more tool_calls) + all their tool results.
    Any reasoning messages preceding this block attach as 'reasoning_before'.
    Steps inside a round are numbered in issue order across all tool_calls.
    """
    rounds: list[dict] = []
    pending_reasoning: list[str] = []
    pending_transition: list[str] = []
    pending_inline_reasoning: list[str] = []
    i = 0
    while i < len(traj):
        msg = traj[i]
        if not isinstance(msg, dict):
            i += 1
            continue
        role = msg.get("role")
        tcs = msg.get("tool_calls") or []
        content = msg.get("content") or ""

        if role == "assistant" and not tcs:
            thinking = extract_thinking(content) if isinstance(content, str) else None
            if thinking:
                pending_reasoning.append(thinking)
            elif isinstance(content, str) and content.strip():
                pending_transition.append(content.strip()[:500])
            i += 1
            continue

        if role == "assistant" and tcs:
            # Start of a round — collect all consecutive assistant+tool_calls messages
            steps: list[dict] = []
            step_idx = 0
            j = i
            while j < len(traj):
                m2 = traj[j]
                if not isinstance(m2, dict):
                    j += 1; continue
                if m2.get("role") != "assistant":
                    break
                m2_tcs = m2.get("tool_calls") or []
                if not m2_tcs:
                    # Inline reasoning interleaved between tool_calls in the same round
                    m2_content = m2.get("content") or ""
                    thinking = extract_thinking(m2_content) if isinstance(m2_content, str) else None
                    if thinking:
                        pending_inline_reasoning.append(thinking)
                    elif isinstance(m2_content, str) and m2_content.strip():
                        pending_inline_reasoning.append(m2_content.strip()[:300])
                    j += 1
                    continue
                m2_content = m2.get("content") or ""
                inline = extract_thinking(m2_content) if isinstance(m2_content, str) else None
                if inline:
                    pending_inline_reasoning.append(inline)
                for tc in m2_tcs:
                    step_idx += 1
                    steps.append(_extract_step(tc, step_idx))
                j += 1

            # Collect all consecutive tool messages
            tool_results = []
            while j < len(traj):
                m3 = traj[j]
                if not isinstance(m3, dict):
                    j += 1; continue
                if m3.get("role") != "tool":
                    break
                tc_id = m3.get("tool_call_id") or ""
                raw = str(m3.get("content") or "")
                tool_results.append({
                    "tool_call_id": tc_id,
                    "content_preview": raw[:800],
                    "len": len(raw),
                })
                j += 1

            rounds.append({
                "round_index": len(rounds) + 1,
                "reasoning_before": "\n\n".join(pending_reasoning) if pending_reasoning else None,
                "transition_text": " | ".join(pending_transition) if pending_transition else None,
                "inline_reasoning": "\n".join(pending_inline_reasoning) if pending_inline_reasoning else None,
                "steps": steps,
                "tool_results": tool_results,
            })
            pending_reasoning = []
            pending_transition = []
            pending_inline_reasoning = []
            i = j
            continue
        i += 1
    return rounds


def gt_summary(data_dir: Path) -> dict:
    """Extract injection + conclusion summary from the per-case data dir."""
    out: dict = {"data_dir": str(data_dir)}
    inj_path = data_dir / "injection.json"
    if inj_path.exists():
        out["injection"] = json.loads(inj_path.read_text())
    # conclusion.parquet → rank spans by (1 - AbnormalSuccRate) and latency delta
    conc_path = data_dir / "conclusion.parquet"
    if conc_path.exists():
        con = duckdb.connect()
        try:
            df = con.execute(f"""
                SELECT * FROM '{conc_path}'
                ORDER BY COALESCE(AbnormalAvgDuration, 0) - COALESCE(NormalAvgDuration, 0) DESC
                LIMIT 20
            """).fetch_df()
            out["conclusion_top20"] = df.to_dict(orient="records")
        except Exception as e:
            out["conclusion_error"] = str(e)
        finally:
            con.close()
    causal_path = data_dir / "causal_graph.json"
    if causal_path.exists():
        try:
            out["causal_graph"] = json.loads(causal_path.read_text())
        except Exception as e:
            out["causal_graph_error"] = str(e)
    return out


def build_dossier(eval_s: EvaluationSample, data_s: DatasetSample | None) -> str:
    dataset_index = eval_s.dataset_index
    aug = eval_s.augmented_question or ""
    m = re.search(r"stored in[:\s]+[\'\"`]?([^\s\'\"`]+)", aug)
    data_dir = Path(m.group(1)) if m else None

    # === Part A — GT reality ===
    dmeta = (data_s.meta if data_s else {}) or {}
    diff = dmeta.get("difficulty", {}) or {}
    fault_type = diff.get("fault_type", "?")
    fault_category = diff.get("fault_category", "?")
    spl = diff.get("spl", "?")
    n_svc = diff.get("n_svc", "?")
    n_edge = diff.get("n_edge", "?")
    gt_services_list = dmeta.get("ground_truth") or dmeta.get("gt_services") or []
    gt_rc = ", ".join(gt_services_list) if gt_services_list else "?"

    gt = gt_summary(data_dir) if data_dir and data_dir.exists() else {}
    inj = gt.get("injection") or {}

    lines = []
    lines.append(f"# case_{dataset_index} — {fault_category} / {fault_type}")
    lines.append("")
    lines.append(f"- dataset_index: **{dataset_index}**")
    lines.append(f"- exp_id: claudecode-qwen3.5-plus")
    lines.append(f"- data_dir: `{data_dir}`")
    lines.append(f"- spl={spl}  n_svc={n_svc}  n_edge={n_edge}")
    lines.append(f"- gt_root_cause_service: **{gt_rc}**")
    lines.append("")
    lines.append("## Part A — GT reality")
    lines.append("")
    lines.append("### A.1 Injection spec")
    if inj:
        for key in (
            "fault_type", "injection_name", "start_time", "end_time",
            "pre_duration", "display_config", "gt_services", "gt_pods",
            "gt_functions", "gt_metrics",
        ):
            if key in inj:
                lines.append(f"- **{key}**: `{inj[key]}`")
    else:
        lines.append("- (injection.json not found)")
    lines.append("")
    lines.append("### A.1b API SLO reports (from DB meta — what agent is told)")
    api_reports = dmeta.get("api_reports") or []
    if api_reports:
        for r in api_reports:
            lines.append(f"- {r}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("### A.2 Conclusion top-20 spans by latency delta")
    top20 = gt.get("conclusion_top20") or []
    if top20:
        lines.append("")
        lines.append("| span | NormalAvgDur | AbnormalAvgDur | Δ(ms) | NormalSucc% | AbnormalSucc% |")
        lines.append("|---|---|---|---|---|---|")
        for row in top20[:20]:
            span_name = row.get("SpanName") or row.get("Operation") or row.get("Span") or row.get("span") or "?"
            n_avg = row.get("NormalAvgDuration") or 0
            a_avg = row.get("AbnormalAvgDuration") or 0
            delta = (a_avg or 0) - (n_avg or 0)
            n_succ = row.get("NormalSuccRate") or 0
            a_succ = row.get("AbnormalSuccRate") or 0
            lines.append(f"| `{str(span_name)[:80]}` | {n_avg:.1f} | {a_avg:.1f} | {delta:+.1f} | {n_succ:.2f} | {a_succ:.2f} |")
    else:
        lines.append("- (conclusion.parquet not available)")
    lines.append("")

    # === Part B — Agent trajectory ===
    lines.append("## Part B — Agent trajectory")
    lines.append("")
    lines.append("### B.0 Prompt received by agent (first 1200 chars)")
    lines.append("```")
    lines.append((eval_s.augmented_question or "")[:1200])
    lines.append("```")
    lines.append("")
    lines.append("### B.1 Final answer")
    resp = eval_s.response or ""
    lines.append("```json")
    lines.append(resp[:1500])
    lines.append("```")
    lines.append("")
    lines.append("### B.2 Graph metrics diagnostic")
    gm = (eval_s.meta or {}).get("graph_metrics", {}).get("primary", {})
    diag = (eval_s.meta or {}).get("graph_metrics", {}).get("diagnostic", {})
    if diag:
        lines.append(f"- matched: {diag.get('matched_services', [])}")
        lines.append(f"- missed: {diag.get('missed_services', [])}")
        lines.append(f"- hallucinated: {diag.get('hallucinated_services', [])}")
    elif gm:
        lines.append(f"- (graph_metrics.primary) node_f1={gm.get('node_f1')}, edge_f1={gm.get('edge_f1')}, rc_f1={gm.get('rc_f1')}")
    else:
        lines.append("- (graph_metrics not available)")
    lines.append("")
    lines.append("### B.3 Cost signature")
    cost = (eval_s.meta or {}).get("cost_metrics", {}) if eval_s.meta else {}
    lines.append(f"- effective_rounds: {cost.get('effective_rounds', '?')}")
    lines.append(f"- total_tokens: {cost.get('total_tokens', '?')}")
    lines.append(f"- time_cost: {cost.get('time_cost', '?')}s")
    lines.append("")

    # Parse trajectory into rounds
    traj_raw = eval_s.trajectories
    if not traj_raw:
        lines.append("### B.4 trajectory: (empty)")
        return "\n".join(lines)
    traj = traj_raw if isinstance(traj_raw, list) else json.loads(traj_raw)
    rounds = group_into_rounds(traj)

    lines.append(f"### B.4 Round-by-round trajectory")
    lines.append(f"- total rounds: {len(rounds)}")
    lines.append("")
    for rd in rounds:
        lines.append(f"#### Round {rd['round_index']}")
        if rd["reasoning_before"]:
            lines.append(f"- **reasoning_before** (from preceding [thinking] blocks):")
            for line in rd["reasoning_before"].splitlines():
                lines.append(f"  > {line}")
        if rd["transition_text"]:
            lines.append(f"- **transition_text**: {rd['transition_text'][:400]}")
        if rd["inline_reasoning"]:
            lines.append(f"- **inline_reasoning**: {rd['inline_reasoning'][:400]}")
        for step in rd["steps"]:
            svc = ", ".join(step["services"]) if step["services"] else "-"
            lines.append(f"- **step {step['step']}** `{step['tool']}` services=[{svc}]")
            if step["sql"]:
                lines.append(f"  - sql:")
                lines.append(f"    ```sql")
                for sl in step["sql"][:1200].splitlines():
                    lines.append(f"    {sl}")
                lines.append(f"    ```")
            else:
                lines.append(f"  - args_preview: `{step['args_raw'][:200]}`")
        for k, tr in enumerate(rd["tool_results"], start=1):
            preview = tr["content_preview"].replace("\n", " ")[:300]
            lines.append(f"  - result[{k}] ({tr['len']} chars): `{preview}...`")
        lines.append("")
    return "\n".join(lines)


def _load_all_failed_indexes() -> list[int]:
    import json
    p = Path(__file__).parent / "failed_cases.jsonl"
    idxs = []
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            idxs.append(int(json.loads(line)["dataset_index"]))
    return idxs


def main():
    import os
    only = os.environ.get("ONLY_IDX")
    if only:
        sample_indexes = [int(x) for x in only.split(",") if x.strip()]
    else:
        sample_indexes = _load_all_failed_indexes()
    print(f"building {len(sample_indexes)} dossier(s)")
    skip_existing = os.environ.get("SKIP_EXISTING", "1") != "0"
    ok = skipped = missing = 0
    with SQLModelUtils.create_session() as s:
        for idx in sample_indexes:
            out = OUT_DIR / f"case_{idx}.md"
            if skip_existing and out.exists():
                skipped += 1
                continue
            eval_s = s.exec(sqlmodel.select(EvaluationSample).where(
                EvaluationSample.exp_id == "claudecode-qwen3.5-plus",
                EvaluationSample.dataset_index == idx,
            )).first()
            if not eval_s:
                print(f"case {idx}: not found"); missing += 1; continue
            data_s = s.exec(sqlmodel.select(DatasetSample).where(
                DatasetSample.index == idx,
            )).first()
            dossier = build_dossier(eval_s, data_s)
            out.write_text(dossier)
            ok += 1
            print(f"case {idx}: wrote {out.name} ({len(dossier)} chars, {len(dossier.splitlines())} lines)")
    print(f"done: wrote={ok} skipped={skipped} missing={missing}")


if __name__ == "__main__":
    main()
