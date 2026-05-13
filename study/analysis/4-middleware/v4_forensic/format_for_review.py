"""
Format a case's baseline + v4 trajectories side-by-side as a single markdown for review.
Shows full SQL / full think_tool / clear intervention markers / key-turn highlights.

Usage:
    UTU_DB_URL=postgresql://... python format_for_review.py <dataset_index> [output.md]
"""
import os, sys, json, re
from sqlalchemy import create_engine, text

ADV_RE = re.compile(r"\[Investigation Advisor\s*[—\-]\s*v4\]\s*phase=(\w+)\s+primary=(\w+)(?:\s+secondary=(\S+))?", re.IGNORECASE)

BASELINE_EXP = "thinkdepthai-qwen3.5-plus"
V4_EXP = "thinkdepthai-qwen3.5-plus-2026-02-15-mw-v4-run"


def fetch(eng, exp_id, di):
    with eng.connect() as c:
        r = c.execute(text(
            "SELECT trajectories::text, response, correct, correct_answer, source, meta::text "
            "FROM evaluation_data WHERE exp_id=:e AND dataset_index=:d"
        ), {"e": exp_id, "d": di}).fetchone()
        if not r:
            return None
        return {
            "traj": json.loads(r[0]) if r[0] else [],
            "response": r[1],
            "correct": r[2],
            "gt": r[3],
            "source": r[4],
            "meta": json.loads(r[5]) if r[5] else {},
        }


def parse_args(args_str):
    if isinstance(args_str, dict):
        return args_str
    if not args_str:
        return {}
    try:
        return json.loads(args_str)
    except Exception:
        return {"_raw": args_str}


def render_assistant_round(round_num, msg_idx, msg):
    out = [f"### Round {round_num}  (msg #{msg_idx})\n"]
    for tc in msg.get("tool_calls", []) or []:
        fname = tc.get("function", {}).get("name", "?")
        args = parse_args(tc.get("function", {}).get("arguments", ""))
        if fname == "query_parquet_files":
            sql = args.get("sql") or args.get("query") or "?"
            out.append(f"**🔧 query_parquet_files**\n\n```sql\n{sql}\n```\n")
        elif fname == "think_tool":
            reflection = args.get("reflection", "")
            out.append(f"**💭 think_tool reflection**\n\n> {reflection.replace(chr(10), chr(10) + '> ')}\n")
        elif fname in ("list_tables", "list_tables_in_directory"):
            d = args.get("directory", "")
            d_short = d.split("/")[-1] if d else ""
            out.append(f"**🔧 {fname}**: `…/{d_short}`\n")
        elif fname == "get_schema":
            pf = args.get("parquet_files", "") or args.get("table_name", "")
            if isinstance(pf, str) and pf.startswith("["):
                try:
                    pf_list = json.loads(pf)
                    n = len(pf_list)
                    names = [p.split("/")[-1] for p in pf_list[:3]]
                    out.append(f"**🔧 get_schema** (查 {n} 个文件: {', '.join(names)}{'...' if n > 3 else ''})\n")
                except Exception:
                    out.append(f"**🔧 get_schema**: `{str(pf)[:200]}`\n")
            else:
                out.append(f"**🔧 get_schema**: `{pf}`\n")
        else:
            out.append(f"**🔧 {fname}**\n\n```json\n{json.dumps(args, indent=2, ensure_ascii=False)[:1500]}\n```\n")
    return "\n".join(out)


def render_tool_result(msg, max_chars=600):
    content = msg.get("content") or ""
    snippet = content[:max_chars] + ("..." if len(content) > max_chars else "")
    return f"  ↳ **tool result**: `{snippet}`\n"


def render_intervention(msg, idx, round_count):
    content = msg.get("content") or ""
    match = ADV_RE.search(content)
    phase = match.group(1) if match else "?"
    primary = match.group(2) if match else "?"
    secondary = match.group(3) if match else "[]"
    body = ADV_RE.sub("", content, count=1).strip()
    return f"""
---

## 🚨 v4 干预触发  ·  msg #{idx}  ·  之前已完成 {round_count} round

| 字段 | 值 |
|---|---|
| **phase** | `{phase}` |
| **primary 维度** | `{primary}` |
| **secondary 维度** | `{secondary}` |

**完整干预文**：

> {body.replace(chr(10), chr(10) + '> ')}

---
"""


def render_final_assistant(msg, idx):
    content = msg.get("content") or ""
    return f"\n### 📌 最终回答  (msg #{idx})\n\n```\n{content[:3000]}\n```\n"


def render_trajectory(traj, label, with_interventions=False):
    out = [f"\n# {label}\n\n_共 {len(traj)} 条消息_\n"]
    round_num = 0
    interv_count = 0
    for i, m in enumerate(traj):
        role = m.get("role") or m.get("type", "?")
        content = m.get("content") or ""
        tc = m.get("tool_calls") or []
        is_intervention = role == "user" and "Investigation Advisor" in content
        if is_intervention:
            interv_count += 1
            out.append(render_intervention(m, i, round_num))
            continue
        if role == "assistant" and tc:
            round_num += 1
            out.append(render_assistant_round(round_num, i, m))
        elif role == "tool":
            out.append(render_tool_result(m))
        elif role == "assistant":
            out.append(render_final_assistant(m, i))
        elif role == "user" and i == 0:
            out.append(f"\n### 📥 初始任务  (msg #{i})\n\n> {content[:500].replace(chr(10), chr(10) + '> ')}\n")
    return "\n".join(out), round_num, interv_count


def main():
    di = int(sys.argv[1])
    out_path = sys.argv[2] if len(sys.argv) > 2 else f"/tmp/case{di}_review.md"

    eng = create_engine(os.environ["UTU_DB_URL"])
    bl = fetch(eng, BASELINE_EXP, di)
    v4 = fetch(eng, V4_EXP, di)

    if not bl or not v4:
        print(f"Missing record. baseline={bool(bl)} v4={bool(v4)}")
        sys.exit(1)

    diff = (bl["meta"].get("difficulty") or {})

    # 抽出 baseline 和 v4 的 predicted RC
    def get_pred(d):
        cge = (d["meta"].get("causal_graph_evaluation") or {}).get("root_cause_services")
        return cge or "(see response)"

    bl_pred = get_pred(bl)
    v4_pred = get_pred(v4)

    bl_md, bl_rounds, _ = render_trajectory(bl["traj"], f"📕 BASELINE (no MW)  ·  exp_id=`{BASELINE_EXP}`")
    v4_md, v4_rounds, v4_intervs = render_trajectory(v4["traj"], f"📗 v4 (with middleware)  ·  exp_id=`{V4_EXP}`")

    header = f"""# Case {di} 完整轨迹对照  ·  baseline vs v4 中间件

## 0. 基本信息

| 字段 | 值 |
|---|---|
| **dataset_index** | {di} |
| **source** | `{bl['source']}` |
| **GT 根因** | `{bl['gt']}` |
| **fault** | {diff.get('fault_category')} / {diff.get('fault_type')} |
| **spl / n_svc / n_edge** | {diff.get('spl')} / {diff.get('n_svc')} / {diff.get('n_edge')} |

## 1. 结果对比

| | baseline | v4 |
|---|---|---|
| **predicted RC** | `{bl_pred}` | `{v4_pred}` |
| **是否正确** | {'✅' if bl['correct'] else '❌'} {bl['correct']} | {'✅' if v4['correct'] else '❌'} {v4['correct']} |
| **总 round 数** | {bl_rounds} | {v4_rounds} |
| **干预次数** | 0 | {v4_intervs} |
| **消息总数** | {len(bl['traj'])} | {len(v4['traj'])} |

---
"""

    full = header + bl_md + "\n\n---\n" + v4_md
    with open(out_path, "w") as f:
        f.write(full)
    print(f"written: {out_path}  ({len(full)} chars)")


if __name__ == "__main__":
    main()
