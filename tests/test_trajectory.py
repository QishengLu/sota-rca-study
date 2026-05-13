"""Tests for v3 Trajectory helpers using mock fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sota_rca.data.trajectory import (
    iter_messages,
    iter_messages_with_context,
    count_effective_rounds,
    count_tool_calls,
    aggregate_token_count,
    wrap_openai_flat_to_v3,
    get_main_agent,
    iter_sub_agent_trajectories,
    iter_main_agent_turns,
    Trajectory,
    AgentTrajectory,
    Turn,
    Message,
    ToolCall,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_traj_from_json(name: str) -> Trajectory:
    """Load a fixture into a Trajectory object (using local dataclasses)."""
    with open(FIXTURES / name) as f:
        data = json.load(f)

    agents = []
    for at_d in data.get("agent_trajectories", []):
        turns = []
        for turn_d in at_d.get("turns", []):
            messages = []
            for msg_d in turn_d.get("messages", []):
                tcs = None
                if msg_d.get("tool_calls"):
                    tcs = [
                        ToolCall(
                            id=t.get("id", ""),
                            name=t.get("name", ""),
                            arguments=t.get("arguments", ""),
                        )
                        for t in msg_d["tool_calls"]
                    ]
                messages.append(Message(
                    role=msg_d.get("role", "user"),
                    content=str(msg_d.get("content", "")),
                    tool_calls=tcs,
                    tool_call_id=msg_d.get("tool_call_id"),
                ))
            turns.append(Turn(messages=messages, token_count=turn_d.get("token_count")))
        agents.append(AgentTrajectory(
            agent_name=at_d.get("agent_name", ""),
            system_prompt=at_d.get("system_prompt", ""),
            turns=turns,
            sub_agent_call_id=at_d.get("sub_agent_call_id"),
        ))
    return Trajectory(agent_trajectories=agents)


def test_iter_messages_single_agent():
    traj = _load_traj_from_json("mock_trajectory.json")
    msgs = list(iter_messages(traj))
    assert len(msgs) > 5
    roles = [m.role for m in msgs]
    assert "user" in roles
    assert "assistant" in roles
    assert "tool" in roles


def test_iter_messages_with_context_preserves_order():
    traj = _load_traj_from_json("mock_trajectory.json")
    ctxs = list(iter_messages_with_context(traj))
    global_idxs = [c.global_idx for c in ctxs]
    assert global_idxs == sorted(global_idxs)


def test_count_effective_rounds():
    traj = _load_traj_from_json("mock_trajectory.json")
    n = count_effective_rounds(traj)
    assert n >= 1


def test_count_tool_calls():
    traj = _load_traj_from_json("mock_trajectory.json")
    n = count_tool_calls(traj)
    assert n >= 3


def test_aggregate_token_count():
    traj = _load_traj_from_json("mock_trajectory.json")
    t = aggregate_token_count(traj)
    assert t > 0


def test_multi_agent_trajectory():
    """Multi-agent fixture has main + 2 sub-agents."""
    traj = _load_traj_from_json("mock_trajectory_multi_agent.json")
    assert len(traj.agent_trajectories) == 3
    main = get_main_agent(traj)
    assert main is not None
    assert main.sub_agent_call_id is None
    subs = list(iter_sub_agent_trajectories(traj))
    assert len(subs) == 2
    assert {a.sub_agent_call_id for a in subs} == {"task_1", "task_2"}


def test_multi_agent_iter_preserves_walk_order():
    """All sub-agent messages should be reachable via iter_messages."""
    traj = _load_traj_from_json("mock_trajectory_multi_agent.json")
    all_ctxs = list(iter_messages_with_context(traj))
    # Should walk main first, then sub-agents
    main_idxs = [c.global_idx for c in all_ctxs if c.trajectory_id == "main"]
    sub_idxs = [c.global_idx for c in all_ctxs if c.trajectory_id != "main"]
    if main_idxs and sub_idxs:
        assert max(main_idxs) < min(sub_idxs)


def test_wrap_openai_flat():
    flat = [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "Q"},
        {"role": "assistant", "content": "thinking...", "tool_calls": [
            {"id": "x", "function": {"name": "f", "arguments": "{}"}}
        ]},
        {"role": "tool", "tool_call_id": "x", "content": "result"},
    ]
    traj = wrap_openai_flat_to_v3(flat, agent_name="legacy")
    assert len(traj.agent_trajectories) == 1
    msgs = list(iter_messages(traj))
    assert len(msgs) == 4
    assistant = next(m for m in msgs if m.role == "assistant")
    assert assistant.tool_calls
    assert assistant.tool_calls[0].name == "f"
