"""Lightweight fallback for rca_metrics when aegis v3 is not installed.

Only used during scaffolding/tests. Production uses v3's evaluation module.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CausalGraph:
    nodes: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)
    root_causes: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, s: str | dict) -> "CausalGraph":
        if isinstance(s, str):
            try:
                d = json.loads(s)
            except json.JSONDecodeError:
                d = {}
        else:
            d = s
        return cls(
            nodes=d.get("nodes", []),
            edges=d.get("edges", []),
            root_causes=d.get("root_causes", []),
        )

    def to_node_keys(self) -> set:
        return {(n.get("component", ""), n.get("state", "")) for n in self.nodes}

    def to_edge_keys(self) -> set:
        return {(e.get("from", ""), e.get("to", "")) for e in self.edges}


def _f1(pred: set, gold: set) -> dict[str, float]:
    if not pred and not gold:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    tp = len(pred & gold)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": p, "recall": r, "f1": f}


def evaluate_graphs(*, pred: CausalGraph, gold: CausalGraph) -> dict[str, Any]:
    """Compute node / edge / RC F1 (best-effort fallback).

    Real v3 implementation does much more (LLM semantic matching etc.).
    """
    n = _f1(pred.to_node_keys(), gold.to_node_keys())
    e = _f1(pred.to_edge_keys(), gold.to_edge_keys())
    rc_pred = set(pred.root_causes)
    rc_gold = set(gold.root_causes)
    rc = _f1(rc_pred, rc_gold)
    return {
        "node_f1": n["f1"],
        "node_precision": n["precision"],
        "node_recall": n["recall"],
        "edge_f1": e["f1"],
        "edge_precision": e["precision"],
        "edge_recall": e["recall"],
        "rc_f1": rc["f1"],
        "rc_precision": rc["precision"],
        "rc_recall": rc["recall"],
    }
