"""
extract_triplets.py — 从 EvaluationSample trajectory 中提取 Thought-Action-Result 三元组

三元组结构：
  - THOUGHT: think_tool 的 reflection 内容（显式思考）
  - ACTION:  紧跟 think_tool 之后的工具调用（或无 think_tool 时的独立调用）
  - RESULT:  对应的 tool 返回结果

内部分析维度（每个三元组内）:
  - thought_action_consistency: thought 提到的意图与 action 调用的工具/参数是否一致
  - action_result_alignment: result 是否是 action 的正常响应（无报错）

外部分析维度（相邻三元组间）:
  - thought_chain: 上一 thought 和下一 thought 是否都在推进对同一问题的理解
  - result_progression: 上一 result 和下一 result 是否形成递进关系
  - result_to_thought: 上一 result 是否直接驱动了下一 thought 的提问方向
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# 添加 RCAgentEval 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlmodel import Session, create_engine

from sota_rca.runner._fallback_db import EvaluationSample

DB_PATH = "sqlite:///RCAgentEval/thinkdepthai_init.db"


# ── 数据结构 ──────────────────────────────────────────────────────────────────

@dataclass
class Action:
    tool_name: str
    arguments: dict
    tool_call_id: str


@dataclass
class Result:
    content: str
    tool_call_id: str
    is_error: bool = False


@dataclass
class Triplet:
    index: int                        # 三元组序号（从 1 开始）
    thought: Optional[str]            # think_tool reflection，无则为 None
    action: Action
    result: Result

    def has_thought(self) -> bool:
        return self.thought is not None

    def is_error_result(self) -> bool:
        return self.result.is_error


# ── 解析轨迹 ──────────────────────────────────────────────────────────────────

def parse_trajectory(raw: list[dict]) -> list[Triplet]:
    """
    将原始 OpenAI 格式消息列表解析为 Thought-Action-Result 三元组列表。

    规则：
    - think_tool 调用 → 作为下一个真实工具调用的 thought
    - 非 think_tool 工具调用 → ACTION
    - role=tool → RESULT，通过 tool_call_id 与 ACTION 匹配
    - role=assistant 且无 tool_calls 且 content 非空 → 最终输出，不进入三元组
    """
    # 先建立 tool_call_id → result 的映射
    results_by_id: dict[str, Result] = {}
    for msg in raw:
        if msg.get("role") == "tool":
            content = str(msg.get("content") or "")
            is_error = "error" in content.lower() and (
                "Error" in content or '"error"' in content
            )
            results_by_id[msg["tool_call_id"]] = Result(
                content=content,
                tool_call_id=msg["tool_call_id"],
                is_error=is_error,
            )

    triplets: list[Triplet] = []
    pending_thought: Optional[str] = None
    triplet_idx = 1

    for msg in raw:
        if msg.get("role") != "assistant":
            continue

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            continue  # 最终文字输出，跳过

        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args = {"raw": tc["function"]["arguments"]}
            call_id = tc["id"]

            if tool_name == "think_tool":
                # think_tool = 显式 thought，暂存
                pending_thought = args.get("reflection", "")
                # think_tool 本身也有 result（"Reflection recorded: ..."），但不计入三元组
            else:
                # 真实 ACTION
                action = Action(
                    tool_name=tool_name,
                    arguments=args,
                    tool_call_id=call_id,
                )
                result = results_by_id.get(call_id, Result(
                    content="[RESULT NOT FOUND]",
                    tool_call_id=call_id,
                    is_error=True,
                ))
                triplets.append(Triplet(
                    index=triplet_idx,
                    thought=pending_thought,
                    action=action,
                    result=result,
                ))
                triplet_idx += 1
                pending_thought = None  # thought 已消费

    return triplets


# ── 打印 ──────────────────────────────────────────────────────────────────────

def _truncate(text: str, max_len: int = 300) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n  ... [截断，共 {len(text)} 字符]"


def print_triplets(triplets: list[Triplet], sample_id: int, full: bool = False):
    max_len = 99999 if full else 400

    print(f"\n{'=' * 80}")
    print(f"Sample {sample_id}  |  共 {len(triplets)} 个三元组")
    print(f"{'=' * 80}")

    for t in triplets:
        print(f"\n{'─' * 60}")
        print(f"三元组 #{t.index}")
        print(f"{'─' * 60}")

        # THOUGHT
        if t.thought:
            print(f"\n【THOUGHT】")
            print(_truncate(t.thought, max_len))
        else:
            print(f"\n【THOUGHT】(无显式思考，直接行动)")

        # ACTION
        print(f"\n【ACTION】  工具: {t.action.tool_name}")
        args_str = json.dumps(t.action.arguments, ensure_ascii=False, indent=2)
        print(_truncate(args_str, max_len))

        # RESULT
        status = "❌ ERROR" if t.result.is_error else "✅ OK"
        print(f"\n【RESULT】  {status}")
        print(_truncate(t.result.content, max_len))


# ── 三元组分析 ────────────────────────────────────────────────────────────────

def analyze_triplets(triplets: list[Triplet]) -> dict:
    """
    生成内部 + 外部分析报告。
    返回结构化分析字典，可用于进一步处理。
    """
    analysis = {
        "sample_stats": {
            "total_triplets": len(triplets),
            "with_explicit_thought": sum(1 for t in triplets if t.has_thought()),
            "error_results": sum(1 for t in triplets if t.is_error_result()),
        },
        "internal": [],   # 每个三元组的内部分析
        "external": [],   # 相邻三元组的外部分析
    }

    # 内部分析
    for t in triplets:
        internal = {
            "triplet_index": t.index,
            "tool": t.action.tool_name,
            "has_thought": t.has_thought(),
            "result_ok": not t.result.is_error,
            # 原始内容（供 LLM 进一步分析）
            "thought_text": t.thought or "",
            "action_args": t.action.arguments,
            "result_text": t.result.content,
        }
        analysis["internal"].append(internal)

    # 外部分析（相邻对）
    for i in range(len(triplets) - 1):
        cur = triplets[i]
        nxt = triplets[i + 1]
        external = {
            "pair": (cur.index, nxt.index),
            # 维度 1：上一 thought → 下一 thought（是否都针对 ground truth 节点推理）
            "prev_thought": cur.thought or "",
            "next_thought": nxt.thought or "",
            # 维度 2：上一 result → 下一 result（是否递进）
            "prev_result": cur.result.content,
            "next_result": nxt.result.content,
            # 维度 3：上一 result → 下一 thought（是否衔接）
            # prev_result 与 next_thought 同上字段，可直接用
        }
        analysis["external"].append(external)

    return analysis


def print_analysis(analysis: dict):
    stats = analysis["sample_stats"]
    print(f"\n{'=' * 80}")
    print("三元组统计")
    print(f"{'=' * 80}")
    print(f"  总三元组数:     {stats['total_triplets']}")
    print(f"  有显式 thought: {stats['with_explicit_thought']}")
    print(f"  工具调用报错:   {stats['error_results']}")

    print(f"\n{'=' * 80}")
    print("内部分析（Thought-Action-Result 一致性）")
    print(f"{'=' * 80}")
    for item in analysis["internal"]:
        thought_flag = "有" if item["has_thought"] else "无"
        result_flag = "✅" if item["result_ok"] else "❌"
        print(f"  #{item['triplet_index']:02d}  {item['tool']:<30}  thought={thought_flag}  result={result_flag}")

    print(f"\n{'=' * 80}")
    print("外部分析（相邻三元组衔接）")
    print(f"{'=' * 80}")
    for ext in analysis["external"]:
        i, j = ext["pair"]
        print(f"\n  ── 三元组 #{i} → #{j} ──")
        if ext["prev_thought"] and ext["next_thought"]:
            print(f"  [thought链]")
            print(f"    #{i} thought: {ext['prev_thought'][:150]}")
            print(f"    #{j} thought: {ext['next_thought'][:150]}")
        if ext["prev_result"]:
            print(f"  [result→thought衔接]")
            print(f"    #{i} result:  {ext['prev_result'][:100]}")
            print(f"    #{j} thought: {ext['next_thought'][:100]}")


# ── 导出 JSON（供外部分析工具使用）─────────────────────────────────────────

def export_triplets_json(
    sample_id: int,
    triplets: list[Triplet],
    output_path: Optional[str] = None,
) -> str:
    data = {
        "sample_id": sample_id,
        "triplets": [
            {
                "index": t.index,
                "thought": t.thought,
                "action": {
                    "tool_name": t.action.tool_name,
                    "arguments": t.action.arguments,
                },
                "result": {
                    "content": t.result.content,
                    "is_error": t.result.is_error,
                },
            }
            for t in triplets
        ],
    }
    json_str = json.dumps(data, ensure_ascii=False, indent=2)

    if output_path:
        Path(output_path).write_text(json_str, encoding="utf-8")
        print(f"已导出到: {output_path}")

    return json_str


# ── 主入口 ────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="提取并分析 Thought-Action-Result 三元组")
    parser.add_argument("--sample_id", type=int, default=1, help="EvaluationSample ID")
    parser.add_argument("--full", action="store_true", help="显示完整内容（不截断）")
    parser.add_argument("--export", type=str, default=None, help="导出 JSON 到文件")
    parser.add_argument("--all", action="store_true", help="分析所有 judged 样本")
    args = parser.parse_args()

    engine = create_engine(DB_PATH)

    with Session(engine) as s:
        if args.all:
            from sqlmodel import select
            samples = list(s.exec(
                select(EvaluationSample).where(EvaluationSample.stage == "judged")
            ).all())
        else:
            samples = [s.get(EvaluationSample, args.sample_id)]
            if not samples[0]:
                print(f"Sample {args.sample_id} not found")
                return

    for sample in samples:
        traj = json.loads(sample.trajectories or "[]")
        triplets = parse_trajectory(traj)

        print_triplets(triplets, sample.id, full=args.full)

        analysis = analyze_triplets(triplets)
        print_analysis(analysis)

        if args.export:
            path = args.export if len(samples) == 1 else args.export.replace(".json", f"_s{sample.id}.json")
            export_triplets_json(sample.id, triplets, output_path=path)


if __name__ == "__main__":
    main()
