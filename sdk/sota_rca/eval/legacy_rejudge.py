#!/usr/bin/env python
"""Rejudge all samples in rollout stage with updated evaluation logic."""

import asyncio
import json
from pathlib import Path

from sqlmodel import select

from sota_rca.db import DatasetSample, EvaluationSample
from sota_rca.eval.data.causal_graph import CausalEdge, CausalGraph, CausalNode, parse_timestamp
from sota_rca.eval.data.rca_metrics import evaluate_graphs
from sota_rca.utils.sqlmodel_utils import SQLModelUtils


def normalize_service_name(service_name: str) -> str:
    """Normalize service name for comparison."""
    normalized = service_name.strip().lower()
    if normalized.startswith("ts-"):
        normalized = normalized[3:]
    return normalized.replace("-", "")


def parse_causal_graph(response: str):
    """Parse CausalGraph from JSON response."""
    if not response:
        return None, "Empty response"

    try:
        parsed_json = json.loads(response)
    except json.JSONDecodeError as e:
        return None, f"JSON decode error: {str(e)}"

    try:
        nodes = []
        for node_data in parsed_json.get("nodes", []):
            state = node_data.get("state", [])
            if isinstance(state, list):
                state = frozenset(state)
            elif isinstance(state, str):
                state = frozenset([state])
            else:
                state = frozenset()

            node = CausalNode(
                component=node_data.get("component", ""),
                state=state,
                timestamp=parse_timestamp(node_data.get("timestamp")),
            )
            nodes.append(node)

        edges = []
        for edge_data in parsed_json.get("edges", []):
            edge = CausalEdge(
                source=edge_data.get("source", ""),
                target=edge_data.get("target", ""),
            )
            edges.append(edge)

        root_causes = []
        for rc_data in parsed_json.get("root_causes", []):
            state = rc_data.get("state", [])
            if isinstance(state, list):
                state = frozenset(state)
            elif isinstance(state, str):
                state = frozenset([state])
            else:
                state = frozenset()

            rc = CausalNode(
                component=rc_data.get("component", ""),
                state=state,
                timestamp=parse_timestamp(rc_data.get("timestamp")),
            )
            root_causes.append(rc)

        component_to_service = parsed_json.get("component_to_service", {})

        graph = CausalGraph(
            nodes=nodes,
            edges=edges,
            root_causes=root_causes,
            component_to_service=component_to_service,
        )

        return graph, None

    except Exception as e:
        return None, f"Error parsing CausalGraph: {str(e)}"


def _get_data_dir(sample, session) -> Path | None:
    """Resolve data directory for a sample via DatasetSample."""
    stmt = select(DatasetSample).where(
        DatasetSample.dataset == sample.dataset,
        DatasetSample.source == sample.source,
    )
    dataset_sample = session.exec(stmt).first()
    if not dataset_sample or not dataset_sample.meta or "source_data_dir" not in dataset_sample.meta:
        return None
    return Path(dataset_sample.meta["source_data_dir"]).expanduser()


def load_gt_root_cause_services(sample, session) -> set[str] | None:
    """Load ground truth root cause services from injection.json."""
    data_dir = _get_data_dir(sample, session)
    if not data_dir:
        return None
    injection_path = data_dir / "injection.json"
    if not injection_path.exists():
        return None
    try:
        with open(injection_path) as f:
            injection = json.load(f)
        services = injection.get("ground_truth", {}).get("service", [])
        return set(services) if services else None
    except Exception:
        return None


def load_gt_causal_graph(sample, session):
    """Load ground truth CausalGraph from DatasetSample."""
    data_dir = _get_data_dir(sample, session)
    if not data_dir:
        return None

    gt_path = data_dir / "causal_graph.json"

    if not gt_path.exists():
        return None

    try:
        with open(gt_path) as f:
            parsed_json = json.load(f)

        nodes = []
        for node_data in parsed_json.get("nodes", []):
            state = node_data.get("state", [])
            if isinstance(state, list):
                state = frozenset(state)
            elif isinstance(state, str):
                state = frozenset([state])
            else:
                state = frozenset()

            node = CausalNode(
                component=node_data.get("component", ""),
                state=state,
                timestamp=parse_timestamp(node_data.get("timestamp")),
            )
            nodes.append(node)

        edges = []
        for edge_data in parsed_json.get("edges", []):
            edge = CausalEdge(
                source=edge_data.get("source", ""),
                target=edge_data.get("target", ""),
            )
            edges.append(edge)

        root_causes = []
        for rc_data in parsed_json.get("root_causes", []):
            state = rc_data.get("state", [])
            if isinstance(state, list):
                state = frozenset(state)
            elif isinstance(state, str):
                state = frozenset([state])
            else:
                state = frozenset()

            rc = CausalNode(
                component=rc_data.get("component", ""),
                state=state,
                timestamp=parse_timestamp(rc_data.get("timestamp")),
            )
            root_causes.append(rc)

        # Parse alarm_nodes
        alarm_nodes = []
        for alarm_data in parsed_json.get("alarm_nodes", []):
            state = alarm_data.get("state", [])
            if isinstance(state, list):
                state = frozenset(state)
            elif isinstance(state, str):
                state = frozenset([state])
            else:
                state = frozenset()

            alarm = CausalNode(
                component=alarm_data.get("component", ""),
                state=state,
                timestamp=parse_timestamp(alarm_data.get("timestamp")),
            )
            alarm_nodes.append(alarm)

        component_to_service = parsed_json.get("component_to_service", {})

        return CausalGraph(
            nodes=nodes,
            edges=edges,
            root_causes=root_causes,
            alarm_nodes=alarm_nodes,
            component_to_service=component_to_service,
        )

    except Exception:
        return None


def evaluate_causal_graph(agent_graph, correct_answer):
    """Evaluate CausalGraph with fixed logic."""
    evaluation_details = {
        "correct": False,
        "root_cause_services": [],
        "reasoning": None,
    }

    score = 0.0

    if not agent_graph:
        evaluation_details["reasoning"] = "Failed to parse CausalGraph"
        return score, evaluation_details

    score += 0.1

    root_cause_services = agent_graph.get_root_cause_services()
    evaluation_details["root_cause_services"] = list(root_cause_services)

    if not root_cause_services:
        evaluation_details["reasoning"] = "No root causes identified in graph"
        return score, evaluation_details

    # Normalize correct answers
    correct_answers = [ans.strip() for ans in correct_answer.split(",")]
    normalized_correct = {normalize_service_name(ans) for ans in correct_answers}

    # Normalize agent root causes
    normalized_agent = {normalize_service_name(rc) for rc in root_cause_services}

    # Exact set matching (after normalization)
    matched = normalized_agent & normalized_correct

    if matched:
        score += 1.0
        evaluation_details["correct"] = True
        evaluation_details["reasoning"] = f"Root cause services matched: {matched}"
    else:
        evaluation_details["reasoning"] = (
            f"Root cause services {list(root_cause_services)} do not match correct answer(s): {correct_answers}"
        )

    return score, evaluation_details


async def rejudge_all(exp_id: str | None = None):
    session = SQLModelUtils.create_session()

    stmt = select(EvaluationSample).where(
        EvaluationSample.stage.in_(["rollout", "judged"])
    )
    if exp_id:
        stmt = stmt.where(EvaluationSample.exp_id == exp_id)
    samples = session.exec(stmt).all()

    filter_msg = f" (exp_id={exp_id})" if exp_id else ""
    print(f"Found {len(samples)} samples to judge{filter_msg}\n")

    if not samples:
        print("No samples to rejudge")
        session.close()
        return

    for i, sample in enumerate(samples, 1):
        print(f"[{i}/{len(samples)}] Judging sample {sample.id} (exp_id: {sample.exp_id})")

        try:
            response = sample.response or ""
            correct_answer = sample.correct_answer or ""

            # Parse agent graph
            agent_graph, parse_error = parse_causal_graph(response)

            # Evaluate with fixed logic
            score, evaluation_details = evaluate_causal_graph(agent_graph, correct_answer)

            # Load GT and compute metrics
            gt_graph = load_gt_causal_graph(sample, session)
            gt_root_cause_services = load_gt_root_cause_services(sample, session)
            if agent_graph and gt_graph:
                # Check if GT has alarm_nodes before computing metrics
                if not gt_graph.get_alarm_services():
                    data_dir = _get_data_dir(sample, session)
                    print(f"  ⚠ Warning: GT data missing alarm_nodes (sample: {sample.source}, path: {data_dir})")

                graph_result = await evaluate_graphs(
                    agent_graph, gt_graph, gt_root_cause_services=gt_root_cause_services
                )

                if isinstance(sample.meta, dict):
                    meta = dict(sample.meta)
                else:
                    meta = {}

                meta["graph_metrics"] = graph_result.model_dump()
                meta["causal_graph_evaluation"] = evaluation_details
                meta["parse_error"] = parse_error

                sample.meta = meta

            # Update sample
            sample.correct = evaluation_details.get("correct", False)
            sample.confidence = score
            sample.reasoning = evaluation_details.get("reasoning", None)
            sample.stage = "judged"

            session.add(sample)
            session.commit()

            print(f"  ✓ Correct: {sample.correct}, Score: {score:.2f}")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            session.rollback()

    session.close()
    print("\n✓ Rejudging complete")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--exp_id", type=str, default=None, help="只 rejudge 指定 exp_id 的样本")
    args = parser.parse_args()
    asyncio.run(rejudge_all(exp_id=args.exp_id))
