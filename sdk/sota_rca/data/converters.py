"""Universal Trajectory converter — OpenAI-flat → v3 Trajectory.

All 6 framework adapters use this. Each framework's legacy agent_runner.py
already produces OpenAI flat messages (`[{role, content, tool_calls, ...}]`).
This helper wraps them into v3 `Trajectory(agent_trajectories=[...])` with
proper Turn boundaries.

For multi-agent frameworks (mabc), see split_multi_agent_messages() which
detects sub-agent boundaries via heuristics (or explicit markers) and emits
nested AgentTrajectories with SubAgentCall links.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Lazy import of v3 schema with local-dataclass fallback
try:
    from rcabench_platform.v3.sdk.llm_eval.trajectory.schema import (  # type: ignore
        Trajectory, AgentTrajectory, Turn, Message, ToolCall, SubAgentCall,
    )
    _V3 = True
except ImportError:
    _V3 = False
    from .trajectory import (  # type: ignore
        Trajectory, AgentTrajectory, Turn, Message, ToolCall, SubAgentCall,
    )


# ============================================================
# Helper: convert one OpenAI flat message dict -> v3 Message
# ============================================================

def openai_message_to_v3(m: dict) -> Message:
    """Convert a single OpenAI-style message dict to v3 Message."""
    role = m.get("role", "user")
    content = m.get("content", "")
    if content is None:
        content = ""
    elif isinstance(content, list):
        # Multimodal/structured content → concatenate text blocks
        parts = []
        for blk in content:
            if isinstance(blk, dict):
                t = blk.get("text") or blk.get("content") or ""
                if t:
                    parts.append(t)
            elif isinstance(blk, str):
                parts.append(blk)
        content = "\n".join(parts)
    else:
        content = str(content)

    tcs: list[ToolCall] | None = None
    if m.get("tool_calls"):
        tcs = []
        for t in m["tool_calls"]:
            if "function" in t:
                tcs.append(ToolCall(
                    id=t.get("id", ""),
                    name=t["function"].get("name", ""),
                    arguments=t["function"].get("arguments", "") or "",
                ))
            else:
                args = t.get("arguments", "")
                if not isinstance(args, str):
                    args = json.dumps(args, ensure_ascii=False)
                tcs.append(ToolCall(
                    id=t.get("id", ""),
                    name=t.get("name", ""),
                    arguments=args,
                ))

    return Message(
        role=role,
        content=content,
        tool_calls=tcs,
        tool_call_id=m.get("tool_call_id"),
        name=m.get("name"),
    )


# ============================================================
# Single-agent: flat messages → Trajectory(1 AgentTrajectory)
# ============================================================

def build_single_agent_trajectory(
    messages: Iterable[dict],
    *,
    agent_name: str,
    system_prompt: str = "",
    turn_strategy: str = "by_user_or_system",
    token_count_per_turn: list[int] | None = None,
    metadata: dict | None = None,
) -> Trajectory:
    """Build a single-agent Trajectory from a flat list of OpenAI messages.

    Args:
        messages: list of {role, content, tool_calls, tool_call_id, name}
        agent_name: e.g. "thinkdepthai"
        system_prompt: extracted system prompt (will also appear in messages
                       if role='system' is present in input)
        turn_strategy: how to split messages into Turns:
            - "single_turn":          everything in one Turn
            - "by_user_or_system":    new Turn at each user/system message
                                      (mirrors ThinkDepthAI converters)
        token_count_per_turn: optional pre-computed token counts per turn

    Returns:
        Trajectory with one AgentTrajectory (sub_agent_call_id=None)
    """
    msgs = [openai_message_to_v3(m) for m in messages]

    turns: list[Turn] = []
    if turn_strategy == "single_turn":
        turns = [Turn(messages=msgs, token_count=None)]
    else:  # by_user_or_system
        current: list[Message] = []
        for m in msgs:
            if m.role in ("user", "system") and current:
                turns.append(Turn(messages=current, token_count=None))
                current = [m]
            else:
                current.append(m)
        if current:
            turns.append(Turn(messages=current, token_count=None))

    # Attach token_counts if provided
    if token_count_per_turn:
        for i, t in enumerate(turns):
            if i < len(token_count_per_turn):
                t.token_count = token_count_per_turn[i]

    at = AgentTrajectory(
        agent_name=agent_name,
        system_prompt=system_prompt,
        turns=turns,
        sub_agent_call_id=None,
    )
    traj = Trajectory(agent_trajectories=[at])
    if metadata:
        traj.metadata = metadata
    return traj


# ============================================================
# Multi-agent: flat messages → Trajectory(main + sub-agents)
# ============================================================

def build_multi_agent_trajectory(
    *,
    main_agent_name: str,
    main_messages: list[dict],
    sub_agents: list[dict],
    system_prompt: str = "",
    metadata: dict | None = None,
) -> Trajectory:
    """Build a multi-agent v3 Trajectory.

    Args:
        main_agent_name: e.g. "ProcessScheduler"
        main_messages: flat messages for the main agent (with sub_agent_calls
                       embedded as ToolCall-style entries that we'll lift up)
        sub_agents: list of dicts: {
            "task_id":    str (e.g. "task_1"),
            "agent_name": str (e.g. "DataDetective"),
            "instructions": str,
            "messages":   list of OpenAI-flat dicts (own ReAct loop)
        }

    The main agent's `sub_agent_calls` Messages are auto-emitted at the right
    place if main_messages contains assistant entries with a 'sub_agent_calls'
    field. Otherwise, sub_agent_calls are appended at the end of the first
    Turn that doesn't already have any.
    """
    main_msgs = []
    pending_sub_calls = [
        SubAgentCall(id=s["task_id"], name=s["agent_name"], instructions=s["instructions"])
        for s in sub_agents
    ]
    sub_calls_attached = False

    for m in main_messages:
        v3msg = openai_message_to_v3(m)
        if m.get("sub_agent_calls") and isinstance(m["sub_agent_calls"], list):
            v3msg.sub_agent_calls = [
                SubAgentCall(
                    id=c["id"], name=c["name"], instructions=c.get("instructions", "")
                ) for c in m["sub_agent_calls"]
            ]
            sub_calls_attached = True
        elif not sub_calls_attached and v3msg.role == "assistant" and pending_sub_calls:
            v3msg.sub_agent_calls = pending_sub_calls
            sub_calls_attached = True
        main_msgs.append(v3msg)

    if not sub_calls_attached and pending_sub_calls:
        # Inject a synthetic dispatch message at the start
        dispatch = Message(
            role="assistant",
            content=f"Dispatching {len(pending_sub_calls)} sub-agents.",
            sub_agent_calls=pending_sub_calls,
        )
        main_msgs.insert(0, dispatch)

    agents = [AgentTrajectory(
        agent_name=main_agent_name,
        system_prompt=system_prompt,
        turns=[Turn(messages=main_msgs, token_count=None)],
        sub_agent_call_id=None,
    )]

    for s in sub_agents:
        sub_msgs = [openai_message_to_v3(m) for m in s.get("messages", [])]
        agents.append(AgentTrajectory(
            agent_name=s["agent_name"],
            system_prompt=s.get("system_prompt", ""),
            turns=[Turn(messages=sub_msgs, token_count=None)],
            sub_agent_call_id=s["task_id"],
        ))

    traj = Trajectory(agent_trajectories=agents)
    if metadata:
        traj.metadata = metadata
    return traj


# ============================================================
# LangChain-specific (for thinkdepthai/aiq) — wraps v3 helper if available
# ============================================================

def langchain_messages_to_v3(
    lc_messages: list[Any],
    *,
    agent_name: str,
    system_prompt: str = "",
) -> Trajectory:
    """Convert LangChain BaseMessage list to v3 Trajectory.

    Uses aegis v3's TrajectoryConverter if installed; otherwise falls back
    to a local converter.
    """
    try:
        from rcabench_platform.v3.sdk.llm_eval.trajectory.converter import (  # type: ignore
            TrajectoryConverter,
        )
        at = TrajectoryConverter.from_langchain_messages(
            lc_messages, agent_name=agent_name, system_prompt=system_prompt
        )
        return Trajectory(agent_trajectories=[at])
    except ImportError:
        # Fallback: convert via OpenAI flat
        flat = _langchain_to_openai_flat(lc_messages)
        return build_single_agent_trajectory(
            flat, agent_name=agent_name, system_prompt=system_prompt
        )


def _langchain_to_openai_flat(lc_messages: list[Any]) -> list[dict]:
    """Best-effort LangChain BaseMessage → OpenAI flat dict converter."""
    out: list[dict] = []
    for m in lc_messages:
        cls = type(m).__name__
        if cls in ("SystemMessage", "SystemMessagePromptTemplate"):
            role = "system"
        elif cls in ("HumanMessage",):
            role = "user"
        elif cls in ("AIMessage", "AIMessageChunk"):
            role = "assistant"
        elif cls in ("ToolMessage", "FunctionMessage"):
            role = "tool"
        else:
            role = "user"

        content = getattr(m, "content", "")
        d: dict = {"role": role, "content": content}

        tcs = getattr(m, "tool_calls", None) or []
        if tcs:
            d["tool_calls"] = [
                {"id": t.get("id", ""), "function": {
                    "name": t.get("name", ""),
                    "arguments": (
                        t.get("args", t.get("arguments", ""))
                        if isinstance(t.get("args", t.get("arguments", "")), str)
                        else json.dumps(t.get("args", t.get("arguments", {})), ensure_ascii=False)
                    ),
                }} for t in tcs
            ]
        if hasattr(m, "tool_call_id") and m.tool_call_id:
            d["tool_call_id"] = m.tool_call_id
        out.append(d)
    return out
