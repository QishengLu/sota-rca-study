"""V3 Trajectory helpers — bridge between v3 nested schema and study analysis.

Two consumption modes:
1. iter_messages(traj) / iter_messages_with_context(traj) — flatten across
   agent_trajectories + turns, preserve time order. For modules that don't
   need turn/agent boundaries (ngram, intent_classify, fault_propagation).

2. Direct read of `traj.agent_trajectories[].turns[]` — for modules that
   NEED turn/agent edges (transitions, markov, pooled_delta, radar, viz).
   See sdk/sota_rca/analysis/transitions.py for an example.

Plus: wrap_openai_flat_to_v3(messages) helper for legacy data migration.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

# Lazy import of v3 schema so this module can be imported even before
# rcabench-platform is installed (e.g. during scaffolding tests).
try:
    from rcabench_platform.v3.sdk.llm_eval.trajectory.schema import (  # type: ignore
        Trajectory, AgentTrajectory, Turn, Message, ToolCall, SubAgentCall,
    )
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
    # Mock minimal dataclasses for type-checking + offline tests
    @dataclass
    class ToolCall:
        id: str = ""
        name: str = ""
        arguments: str = ""

    @dataclass
    class SubAgentCall:
        id: str = ""
        name: str = ""
        instructions: str = ""

    @dataclass
    class Message:
        role: str = "user"
        content: str = ""
        tool_calls: list[ToolCall] | None = None
        tool_call_id: str | None = None
        sub_agent_calls: list[SubAgentCall] | None = None
        sub_agent_call_id: str | None = None
        name: str | None = None

    @dataclass
    class Turn:
        messages: list[Message] = field(default_factory=list)
        token_count: int | None = None

    @dataclass
    class AgentTrajectory:
        agent_name: str = ""
        system_prompt: str = ""
        turns: list[Turn] = field(default_factory=list)
        sub_agent_call_id: str | None = None

        @property
        def trajectory_id(self) -> str:
            return self.sub_agent_call_id or "main"

    @dataclass
    class Trajectory:
        agent_trajectories: list[AgentTrajectory] = field(default_factory=list)
        reward: float | None = None
        correct: bool | None = None
        metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MessageContext:
    """Context wrapper around a Message, providing turn/agent info."""
    message: Message
    agent_name: str
    trajectory_id: str         # "main" or sub-agent task_id
    turn_idx: int              # 0-indexed within this agent_trajectory
    global_idx: int            # 0-indexed across the whole trajectory (time order)
    sub_agent_call_id: str | None = None


# ============================================================
# Public iteration API
# ============================================================

def iter_messages(traj: Trajectory) -> Iterator[Message]:
    """Yield all messages across all agent_trajectories and turns, in time order.

    For sub-agent-aware code, use iter_messages_with_context() instead.
    """
    for _, msg in _walk_messages(traj):
        yield msg


def iter_messages_with_context(traj: Trajectory) -> Iterator[MessageContext]:
    """Yield (message + context) tuples, preserving time order across the trajectory."""
    for ctx, msg in _walk_messages(traj):
        yield MessageContext(message=msg, **ctx)


def _walk_messages(traj: Trajectory) -> Iterator[tuple[dict, Message]]:
    """Internal: walk trajectory in time order, yielding (context_dict, message)."""
    global_idx = 0
    # Walk main agent first (trajectory_id="main"), then sub-agents in declaration order
    # (mirrors what aegis v3 produces — main is always agent_trajectories[0])
    for at in traj.agent_trajectories:
        traj_id = at.sub_agent_call_id or "main"
        for turn_idx, turn in enumerate(at.turns):
            for msg in turn.messages:
                ctx = dict(
                    agent_name=at.agent_name,
                    trajectory_id=traj_id,
                    turn_idx=turn_idx,
                    global_idx=global_idx,
                    sub_agent_call_id=at.sub_agent_call_id,
                )
                yield ctx, msg
                global_idx += 1


# ============================================================
# Turn-level / agent-level access (for behavior transition modules)
# ============================================================

def iter_main_agent_turns(traj: Trajectory) -> Iterator[tuple[int, Turn]]:
    """Yield (turn_idx, Turn) of main agent only."""
    main = next((at for at in traj.agent_trajectories if at.sub_agent_call_id is None), None)
    if main is None:
        return
    for idx, turn in enumerate(main.turns):
        yield idx, turn


def iter_sub_agent_trajectories(traj: Trajectory) -> Iterator[AgentTrajectory]:
    """Yield only sub-agent AgentTrajectories."""
    for at in traj.agent_trajectories:
        if at.sub_agent_call_id is not None:
            yield at


def get_main_agent(traj: Trajectory) -> AgentTrajectory | None:
    """Return the main AgentTrajectory (sub_agent_call_id is None), or None if missing."""
    return next((at for at in traj.agent_trajectories if at.sub_agent_call_id is None), None)


def aggregate_token_count(traj: Trajectory) -> int:
    """Sum Turn.token_count across all turns of all agents."""
    return sum(
        (turn.token_count or 0)
        for at in traj.agent_trajectories
        for turn in at.turns
    )


def count_tool_calls(traj: Trajectory) -> int:
    """Count total tool calls across all agents."""
    n = 0
    for at in traj.agent_trajectories:
        for turn in at.turns:
            for msg in turn.messages:
                if msg.tool_calls:
                    n += len(msg.tool_calls)
    return n


def count_effective_rounds(traj: Trajectory) -> int:
    """Effective rounds = number of assistant messages with tool_calls.

    This is the "interaction depth" metric for cost_metrics.
    """
    n = 0
    for at in traj.agent_trajectories:
        for turn in at.turns:
            for msg in turn.messages:
                if msg.role == "assistant" and msg.tool_calls:
                    n += 1
    return n


# ============================================================
# Legacy → V3 wrapping
# ============================================================

def wrap_openai_flat_to_v3(
    messages: list[dict],
    *,
    agent_name: str = "unknown",
    system_prompt: str = "",
) -> Trajectory:
    """Wrap a legacy OpenAI-flat trajectory (list of {role, content, tool_calls})
    into a v3 Trajectory single AgentTrajectory single Turn.

    Used for migrating historical data from old SOTA-agents PG dump.
    Sub-agent information is lost in flat format.
    """
    v3_messages = []
    for m in messages:
        tc = None
        if m.get("tool_calls"):
            tc = [
                ToolCall(
                    id=t.get("id", ""),
                    name=t.get("function", {}).get("name", "") if "function" in t else t.get("name", ""),
                    arguments=(
                        t.get("function", {}).get("arguments", "")
                        if "function" in t
                        else (t.get("arguments", "") if isinstance(t.get("arguments"), str)
                              else json.dumps(t.get("arguments", {})))
                    ),
                )
                for t in m["tool_calls"]
            ]
        v3_messages.append(
            Message(
                role=m.get("role", "user"),
                content=str(m.get("content", "")),
                tool_calls=tc,
                tool_call_id=m.get("tool_call_id"),
                name=m.get("name"),
            )
        )

    return Trajectory(
        agent_trajectories=[
            AgentTrajectory(
                agent_name=agent_name,
                system_prompt=system_prompt,
                turns=[Turn(messages=v3_messages, token_count=None)],
                sub_agent_call_id=None,
            )
        ]
    )


# ============================================================
# Round ↔ Turn conversion (compat with old round-based analyses)
# ============================================================

def turn_to_round_idx(turn_idx: int) -> int:
    """Convenience: in study analyses, old 'round' concept is now 'Turn'.

    Direct identity mapping. Kept as a function so call sites stay searchable
    if the mapping ever needs adjustment (e.g. if a v3 Turn ends up being
    larger or smaller than a SOTA-agents 'round').
    """
    return turn_idx
