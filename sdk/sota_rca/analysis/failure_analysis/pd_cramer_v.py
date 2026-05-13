#!/usr/bin/env python
"""Compute Cramér's V between PD (multi-label) and D (single-label), and PD and R (single-label).

For each unified PD_x, build a 2x2 table:
    (PD_x in case) x (D_class == d_i for each d_i)
Aggregate across D classes via composite chi-square (PD_x in case) x D_class (k-way).
Similarly for R classes.

Inputs:
  --pd-projection  path to PD_projection.jsonl
  --d-projection   path to D_projection.jsonl (existing)
  --r-labels       path to R-labels source: parsed from DB (queried here) keyed by (exp_id, case_id)
                   If omitted, pulls R labels from meta.failure_analysis.v1.R in DB.

Outputs a markdown table to stdout and writes JSON to --out if given.
"""
import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, "RCAgentEval")
sys.path.insert(0, str(Path(__file__).parent))

from harp_config import DB_URL, FRAMEWORKS  # noqa: E402
from sqlmodel import Session, create_engine, select  # noqa: E402
from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402


def cramers_v(contingency: list[list[int]]) -> float:
    """Cramér's V from a contingency table (list of lists, rows×cols)."""
    n = sum(sum(row) for row in contingency)
    if n == 0:
        return 0.0
    rows = len(contingency)
    cols = len(contingency[0]) if rows else 0
    if rows < 2 or cols < 2:
        return 0.0
    row_tot = [sum(row) for row in contingency]
    col_tot = [sum(contingency[r][c] for r in range(rows)) for c in range(cols)]
    chi2 = 0.0
    for r in range(rows):
        for c in range(cols):
            expected = row_tot[r] * col_tot[c] / n
            if expected > 0:
                chi2 += (contingency[r][c] - expected) ** 2 / expected
    k = min(rows - 1, cols - 1)
    if k == 0:
        return 0.0
    return math.sqrt(chi2 / (n * k))


def load_pd_projection(path: Path) -> dict[tuple[str, int], list[str]]:
    """Return (agent, case_id) -> list of unified PD names."""
    out: dict[tuple[str, int], list[str]] = {}
    with path.open() as f:
        for line in f:
            r = json.loads(line)
            out[(r["agent"], int(r["case_id"]))] = list(r.get("process_defects", []))
    return out


def load_d_projection(path: Path) -> dict[tuple[str, int], str]:
    out: dict[tuple[str, int], str] = {}
    with path.open() as f:
        for line in f:
            r = json.loads(line)
            out[(r["agent"], int(r["case_id"]))] = r["d_class"]
    return out


def load_r_labels_from_db() -> dict[tuple[str, int], str]:
    out: dict[tuple[str, int], str] = {}
    engine = create_engine(DB_URL)
    with Session(engine) as s:
        for agent_key, (exp_id, *_) in FRAMEWORKS.items():
            stmt = select(EvaluationSample).where(
                EvaluationSample.exp_id == exp_id,
                EvaluationSample.correct == False,  # noqa: E712
                EvaluationSample.stage == "judged",
            )
            for sample in s.exec(stmt).all():
                meta = sample.meta or {}
                fa = meta.get("failure_analysis", {}) or {}
                v1 = fa.get("v1", {}) or {}
                r = v1.get("R") or v1.get("unified_R")
                if r:
                    out[(agent_key, sample.dataset_index)] = r
    return out


def build_contingency(
    pd_map: dict[tuple[str, int], list[str]],
    axis_map: dict[tuple[str, int], str],
    pd_name: str,
) -> tuple[list[list[int]], list[str]]:
    axis_classes = sorted({v for v in axis_map.values()})
    table = [[0] * len(axis_classes) for _ in range(2)]  # row 0 = no PD, row 1 = has PD
    for key in pd_map:
        if key not in axis_map:
            continue
        has_pd = pd_name in pd_map[key]
        ci = axis_classes.index(axis_map[key])
        table[int(has_pd)][ci] += 1
    return table, axis_classes


def all_pds(pd_map: dict[tuple[str, int], list[str]]) -> list[str]:
    names: set[str] = set()
    for v in pd_map.values():
        names.update(v)
    return sorted(names)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pd-projection", required=True, type=Path)
    ap.add_argument("--d-projection", type=Path, default=Path(
        "analysis/3-failure-modes/merged/D_projection.jsonl"))
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    pd_map = load_pd_projection(args.pd_projection)
    d_map = load_d_projection(args.d_projection)
    r_map = load_r_labels_from_db()
    pds = all_pds(pd_map)

    print(f"Loaded {len(pd_map)} PD rows, {len(d_map)} D rows, {len(r_map)} R rows")
    print(f"Unified PDs: {len(pds)}")

    rows_out: list[dict] = []
    print("\n| PD | count | Cramér V vs D | Cramér V vs R |")
    print("|---|---|---|---|")
    for pd_name in pds:
        d_ct, _ = build_contingency(pd_map, d_map, pd_name)
        r_ct, _ = build_contingency(pd_map, r_map, pd_name)
        v_d = cramers_v(d_ct)
        v_r = cramers_v(r_ct)
        count = sum(1 for v in pd_map.values() if pd_name in v)
        print(f"| {pd_name} | {count} | {v_d:.3f} | {v_r:.3f} |")
        rows_out.append({"pd": pd_name, "count": count, "v_d": v_d, "v_r": v_r})

    vs = [row["v_d"] for row in rows_out] + [row["v_r"] for row in rows_out]
    median = sorted(vs)[len(vs) // 2] if vs else 0.0
    red = [r for r in rows_out if r["v_d"] >= 0.50 or r["v_r"] >= 0.50]
    yellow = [r for r in rows_out if (0.30 <= r["v_d"] < 0.50) or (0.30 <= r["v_r"] < 0.50)]
    print(f"\nMedian V: {median:.3f}")
    print(f"Red-zone (V >= 0.50): {len(red)} -> {[r['pd'] for r in red]}")
    print(f"Yellow-zone (0.30-0.49): {len(yellow)} -> {[r['pd'] for r in yellow]}")

    if args.out:
        args.out.write_text(json.dumps(rows_out, indent=2))
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
