"""
node_investigation.py — 提取 agent 每步调查的节点，与 ground truth 比对

query_intent 分类（query_parquet_files 未指定节点的原因）：
  - node_filter   : WHERE service_name = '...'，精确锁定节点
  - edge_traversal: 查 abnormal_edges/nodes，看服务间关系（用边列而非 service_name）
  - aggregated    : 查 conclusion/summary，读预计算摘要
  - exploration   : SELECT * / DISTINCT，广播扫描，尚未锁定节点
  - no_sql        : get_schema / list_tables，无 SQL
"""

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlmodel import Session, create_engine, select

from sota_rca.runner._fallback_db import EvaluationSample

DB_PATH = "sqlite:///RCAgentEval/thinkdepthai_init.db"
SERVICE_PREFIX = "ts-"


# ── 节点提取 ──────────────────────────────────────────────────────────────────

def extract_nodes_from_sql(sql: str) -> tuple[list[str], str]:
    """
    从 SQL 语句里提取服务节点，同时返回查询意图类型。

    返回: (nodes, query_intent)
    """
    if not sql:
        return [], "no_sql"

    sql_lower = sql.lower()

    # 类型 A：精确节点过滤（WHERE service_name = 'ts-xxx'）
    nodes = []
    for m in re.finditer(r"service_name\s*=\s*['\"]([^'\"]+)['\"]", sql, re.IGNORECASE):
        val = m.group(1)
        if val.startswith(SERVICE_PREFIX) or val.startswith("loadgenerator"):
            nodes.append(val)
    for m in re.finditer(r"service_name\s+IN\s*\(([^)]+)\)", sql, re.IGNORECASE):
        for val in re.split(r"[,\s]+", m.group(1)):
            val = val.strip("'\" ")
            if val.startswith(SERVICE_PREFIX) or val.startswith("loadgenerator"):
                nodes.append(val)
    if nodes:
        return list(dict.fromkeys(nodes)), "node_filter"

    # 类型 B：图结构查询（abnormal_edges / abnormal_nodes）
    if any(t in sql_lower for t in ("abnormal_edges", "abnormal_nodes", "abnormal_connection")):
        # 有时边查询里也有字面量过滤，如 WHERE src_name = 'ts-xxx'
        literals = re.findall(r"['\"](" + SERVICE_PREFIX + r"[a-z0-9-]+)['\"]", sql)
        return list(dict.fromkeys(literals)), "edge_traversal"

    # 类型 C：预聚合摘要
    if any(t in sql_lower for t in ("conclusion", "summary")):
        return [], "aggregated"

    # 类型 D：广播探索
    return [], "exploration"


def extract_nodes_from_content(content: str) -> list[str]:
    """从 result 内容里提取出现的服务名。"""
    pattern = r'"service_name"\s*:\s*"([^"]+)"'
    nodes = re.findall(pattern, content)
    bare = re.findall(r'\bts-[a-z0-9-]+\b', content)
    all_nodes = nodes + bare
    return list(dict.fromkeys(n for n in all_nodes if n.startswith(SERVICE_PREFIX)))


def get_data_type(tool: str, args: dict) -> str:
    if tool == "list_tables_in_directory":
        return "discovery"
    target = args.get("parquet_file") or args.get("parquet_files") or ""
    for keyword in ("traces", "logs", "metrics", "connection", "conclusion"):
        if keyword in target:
            return keyword
    return "unknown"


# ── 数据结构 ──────────────────────────────────────────────────────────────────

@dataclass
class Step:
    step_index: int
    msg_index: int
    tool: str
    data_type: str
    query_intent: str         # node_filter / edge_traversal / aggregated / exploration / no_sql
    action_nodes: list[str]   # 从 SQL 提取
    result_nodes: list[str]   # 从 result 内容提取
    hit_gt_in_action: bool
    hit_gt_in_result: bool
    sql: str
    result_preview: str


# ── 分析 ──────────────────────────────────────────────────────────────────────

def analyze_sample(sample: EvaluationSample) -> tuple[list[Step], list[str]]:
    traj = json.loads(sample.trajectories or "[]")
    gt_nodes = [n.strip() for n in (sample.correct_answer or "").split(",") if n.strip()]

    results_by_id: dict[str, str] = {}
    for msg in traj:
        if msg.get("role") == "tool":
            results_by_id[msg["tool_call_id"]] = str(msg.get("content") or "")

    def normalize(n):
        return n.lower().replace("ts-", "").replace("-", "")

    gt_normalized = {normalize(n) for n in gt_nodes}

    steps, step_idx = [], 1
    for msg_idx, msg in enumerate(traj):
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls", []):
            tool_name = tc["function"]["name"]
            if tool_name == "think_tool":
                continue
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}

            sql = args.get("query", "")
            result_content = results_by_id.get(tc["id"], "")
            action_nodes, query_intent = extract_nodes_from_sql(sql)
            result_nodes = extract_nodes_from_content(result_content)

            hit_action = any(normalize(n) in gt_normalized for n in action_nodes)
            hit_result = any(normalize(n) in gt_normalized for n in result_nodes)

            steps.append(Step(
                step_index=step_idx,
                msg_index=msg_idx,
                tool=tool_name,
                data_type=get_data_type(tool_name, args),
                query_intent=query_intent,
                action_nodes=action_nodes,
                result_nodes=result_nodes,
                hit_gt_in_action=hit_action,
                hit_gt_in_result=hit_result,
                sql=sql,
                result_preview=result_content[:200],
            ))
            step_idx += 1

    return steps, gt_nodes


# ── 打印 ──────────────────────────────────────────────────────────────────────

INTENT_LABEL = {
    "node_filter":    "🎯节点过滤",
    "edge_traversal": "🕸️ 图结构",
    "aggregated":     "📊预聚合",
    "exploration":    "🔍广播探索",
    "no_sql":         "📂文件操作",
}


def print_investigation_timeline(sample: EvaluationSample, steps: list[Step], gt_nodes: list[str]):
    print(f"\n{'=' * 90}")
    print(f"Sample {sample.id}  correct={sample.correct}  GT: {gt_nodes}")
    print(f"{'=' * 90}")
    print(f"{'#':>3}  {'工具':<28}  {'数据类型':<10}  {'查询意图':<12}  {'调查节点':<40}  GT")
    print(f"{'─'*3}  {'─'*28}  {'─'*10}  {'─'*12}  {'─'*40}  {'─'*4}")

    for s in steps:
        nodes_str = ", ".join(s.action_nodes) if s.action_nodes else "—"
        hit_str = "✅" if s.hit_gt_in_action else ("⚡" if s.hit_gt_in_result else "")
        intent = INTENT_LABEL.get(s.query_intent, s.query_intent)
        print(f"{s.step_index:>3}  {s.tool:<28}  {s.data_type:<10}  {intent:<12}  {nodes_str:<40}  {hit_str}")

    # 各意图类型统计
    from collections import Counter
    intent_counts = Counter(s.query_intent for s in steps)
    print(f"\n  查询意图分布: " + "  ".join(f"{INTENT_LABEL.get(k,k)}×{v}" for k, v in intent_counts.items()))

    first_hit = next((s.step_index for s in steps if s.hit_gt_in_action), None)
    total_gt = sum(1 for s in steps if s.hit_gt_in_action)
    print(f"  首次命中 GT: 第{first_hit}步" if first_hit else "  未命中 GT 节点")
    print(f"  命中 GT 步数: {total_gt}/{len(steps)}")

    # 节点调查路径
    node_steps = [(s.step_index, s.action_nodes, s.data_type, s.query_intent)
                  for s in steps if s.action_nodes]
    if node_steps:
        print(f"\n  节点调查路径:")
        for idx, (i, nodes, dtype, intent) in enumerate(node_steps):
            gt_mark = "✅" if any(n in gt_nodes for n in nodes) else ""
            arrow = "→ " if idx > 0 else "   "
            print(f"    {arrow}#{i} [{dtype}/{INTENT_LABEL.get(intent,intent)}] {', '.join(nodes)} {gt_mark}")


def export_json(sample: EvaluationSample, steps: list[Step], gt_nodes: list[str]) -> dict:
    from collections import Counter
    intent_counts = Counter(s.query_intent for s in steps)
    return {
        "sample_id": sample.id,
        "source": sample.source,
        "correct": sample.correct,
        "ground_truth_nodes": gt_nodes,
        "steps": [
            {
                "step_index": s.step_index,
                "tool": s.tool,
                "data_type": s.data_type,
                "query_intent": s.query_intent,
                "action_investigated_nodes": s.action_nodes,
                "result_appeared_nodes": s.result_nodes,
                "hit_gt_in_action": s.hit_gt_in_action,
                "hit_gt_in_result": s.hit_gt_in_result,
                "sql": s.sql,
            }
            for s in steps
        ],
        "summary": {
            "total_steps": len(steps),
            "intent_distribution": dict(intent_counts),
            "steps_hit_gt": sum(1 for s in steps if s.hit_gt_in_action),
            "first_gt_hit_step": next((s.step_index for s in steps if s.hit_gt_in_action), None),
        },
    }


# ── 入口 ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample_id", type=int, default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--export", type=str, default=None)
    args = parser.parse_args()

    engine = create_engine(DB_PATH)
    with Session(engine) as s:
        if args.all:
            samples = list(s.exec(
                select(EvaluationSample).where(EvaluationSample.stage == "judged")
            ).all())
        else:
            sid = args.sample_id or 1
            samples = [s.get(EvaluationSample, sid)]

    all_export = []
    for sample in samples:
        steps, gt_nodes = analyze_sample(sample)
        print_investigation_timeline(sample, steps, gt_nodes)
        if args.export:
            all_export.append(export_json(sample, steps, gt_nodes))

    if args.export:
        path = Path(args.export)
        data = all_export[0] if len(all_export) == 1 else all_export
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已导出: {path}")


if __name__ == "__main__":
    main()
