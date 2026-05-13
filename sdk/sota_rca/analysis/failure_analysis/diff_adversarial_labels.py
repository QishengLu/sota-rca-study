#!/usr/bin/env python
"""Phase 5 — compare user-saved adversarial labels against DB primary labels.

Input (per agent): `<workspace>/adversarial_labels.jsonl` — user pastes Opus's
JSONL output here. One object per line:
  {"dataset_index": int, "primary": str, "pivot_round": int|null,
   "proximate_cause": str, "reasoning": str}

Output (per agent): `<workspace>/adversarial_disagreement.md` — only cases where
DB `meta.failure_analysis.v1.primary` ≠ adversarial `primary`. Side-by-side.

Usage:
    cd RCAgentEval
    uv run python scripts/failure_analysis/diff_adversarial_labels.py
    uv run python scripts/failure_analysis/diff_adversarial_labels.py --exp_id aiq-qwen3.5-plus
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from sqlmodel import Session, create_engine, select

REPO_ROOT = Path(__file__).resolve().parents[3]
RCABENCH_ROOT = REPO_ROOT / "RCAgentEval"
sys.path.insert(0, str(RCABENCH_ROOT))

from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = "postgresql://postgres:postgres@localhost:5433/SOTA-Agents"
AGENTS = {
    "thinkdepthai-qwen3.5-plus": "analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2",
    "thinkdepthai-claude-sonnet-4.6": "analysis/3-failure-modes/2-by-framework/thinkdepthai-claude-sonnet-4.6/v1",
    "aiq-qwen3.5-plus": "analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/v1",
    "claudecode-qwen3.5-plus": "analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1",
}


def load_adversarial(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    out: dict[int, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("```"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("skipped malformed line: %s", line[:80])
            continue
        idx = rec.get("dataset_index")
        if idx is not None:
            out[int(idx)] = rec
    return out


def diff_agent(session: Session, agent: str, workspace: Path) -> None:
    adv_path = workspace / "adversarial_labels.jsonl"
    if not adv_path.exists():
        logger.info("%s: %s not found, skipping", agent, adv_path)
        return
    adv = load_adversarial(adv_path)
    logger.info("%s: loaded %d adversarial labels", agent, len(adv))

    stmt = (
        select(EvaluationSample)
        .where(
            EvaluationSample.exp_id == agent,
            EvaluationSample.stage == "judged",
            EvaluationSample.correct == False,  # noqa: E712
        )
    )
    samples = session.exec(stmt).all()

    rows: list[dict] = []
    missing = []
    for s in samples:
        v1 = ((s.meta or {}).get("failure_analysis") or {}).get("v1") or {}
        mine = v1.get("primary")
        if not mine:
            continue
        a = adv.get(s.dataset_index)
        if not a:
            missing.append(s.dataset_index)
            continue
        theirs = a.get("primary")
        rows.append({
            "dataset_index": s.dataset_index,
            "mine": mine,
            "theirs": theirs,
            "my_pivot": v1.get("pivot_round"),
            "their_pivot": a.get("pivot_round"),
            "my_px": v1.get("proximate_cause") or "",
            "their_px": a.get("proximate_cause") or "",
            "their_reason": a.get("reasoning") or "",
            "agree": mine == theirs,
        })

    if not rows:
        logger.warning("%s: no overlap between DB labels and adversarial file", agent)
        return

    agree = sum(1 for r in rows if r["agree"])
    disagree = [r for r in rows if not r["agree"]]
    pct_agree = 100.0 * agree / len(rows)
    logger.info("%s: agreement %d/%d (%.1f%%); %d disagreements; %d missing from adv",
                agent, agree, len(rows), pct_agree, len(disagree), len(missing))

    out_path = workspace / "adversarial_disagreement.md"
    lines = [
        f"# Adversarial-relabel disagreements — {agent}",
        "",
        f"- DB labeler: first pass (me)",
        f"- Adversarial: Claude Opus 4.7 in a fresh session, saw taxonomy + dossiers only",
        f"- **Agreement: {agree}/{len(rows)} ({pct_agree:.1f}%)**",
        f"- Missing from adversarial file (Opus skipped or format error): {len(missing)}",
        "",
        f"## {len(disagree)} disagreement cases",
        "",
    ]
    disagree.sort(key=lambda r: (r["mine"], r["dataset_index"]))
    for r in disagree:
        lines += [
            f"### case_{r['dataset_index']}",
            "",
            f"| | primary | pivot | proximate_cause |",
            f"|---|---|---|---|",
            f"| **me** | `{r['mine']}` | {r['my_pivot']} | {r['my_px']} |",
            f"| **adv** | `{r['theirs']}` | {r['their_pivot']} | {r['their_px']} |",
            "",
            f"**adversarial reasoning:** {r['their_reason']}",
            "",
            "---",
            "",
        ]
    if missing:
        lines += [
            "## Missing from adversarial file",
            "",
            ", ".join(f"case_{i}" for i in missing[:50]),
            "",
            f"(showing first 50 of {len(missing)})" if len(missing) > 50 else "",
        ]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("%s: wrote %s", agent, out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=DEFAULT_DB_URL)
    parser.add_argument("--exp_id", action="append", default=None, help="Limit to one exp_id (repeatable)")
    args = parser.parse_args()

    exp_ids = args.exp_id or list(AGENTS.keys())
    engine = create_engine(args.db)
    with Session(engine) as session:
        for agent in exp_ids:
            diff_agent(session, agent, REPO_ROOT / AGENTS[agent])


if __name__ == "__main__":
    main()
