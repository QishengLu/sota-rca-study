#!/usr/bin/env python
"""Phase 5 — build per-agent adversarial-relabel prompts.

Each prompt is a self-contained instruction file that the user pastes into a
fresh Claude Code session (Opus 4.7). The new session has no context from this
one, so its label is truly independent. Cost: user's subscription quota.

Workflow:
  1. Run this script: produces 4 files `<workspace>/adversarial_prompt.md`.
  2. Open a FRESH Claude Code (VSCode plugin) conversation per agent.
  3. Paste the file's contents as the first message.
  4. Opus 4.7 reads taxonomy inline + opens each dossier via the Read tool,
     outputs one JSONL line per case at the end.
  5. Save its final JSONL block to `<workspace>/adversarial_labels.jsonl`.
  6. Run `diff_adversarial_labels.py` to produce `adversarial_disagreement.md`.

Output:
  analysis/3-failure-modes/2-by-framework/<agent>/<v>/adversarial_prompt.md
"""

from __future__ import annotations

import argparse
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

PROMPT_TEMPLATE = """\
# Adversarial failure-mode relabeling task — `{agent}`

You are acting as an **independent second labeler**. You do NOT have access to any
previous analysis or labels by anyone else. Your goal is to assign each failed
case to exactly one theme from the frozen taxonomy below, based only on:
  (a) the ground-truth side of the dossier (Part A)
  (b) the agent's trajectory side of the dossier (Part B)

Do not open or read any file that isn't explicitly listed in the "Cases to label"
section. In particular, do NOT read `per_case_analysis.md`, `labels.jsonl`,
`labels_aligned.jsonl`, `adversarial_prompt.md` itself after you've ingested it
(don't re-check instructions), or anything under `meta.failure_analysis` in DB —
those contain the first labeler's answers and would contaminate your independence.

---

## Fixed taxonomy for `{agent}`

(source: `{taxonomy_path}` — inlined below to lock the rubric in your context. Do NOT open the taxonomy file; the text below is authoritative.)

<<<TAXONOMY
{taxonomy_text}
TAXONOMY>>>

---

## Output file (save directly to disk — NO copy-paste needed)

You will write one JSON line per case into this exact absolute path:

```
{output_path}
```

**Save strategy — append incrementally, one line per case, RIGHT AFTER you finish that case.** This way if your context runs out mid-task, the work so far is persisted.

Use the Bash tool after each case:

```
echo '<JSON_LINE>' >> {output_path}
```

Where `<JSON_LINE>` is a single-line JSON object (no leading/trailing whitespace, no markdown fencing, must be valid JSON that passes `json.loads`). Use single quotes around the echo payload and escape internal single quotes as needed. A safer pattern if your `reasoning` field has quotes:

```
cat >> {output_path} <<'JSONL'
{{"dataset_index": 33, "primary": "T3_Noise-Anchor", "pivot_round": 5, "proximate_cause": "anchored on pre-existing RabbitMQ noise", "reasoning": "Part A shows JVMMemoryStress on ts-auth-service; agent's rounds 4-5 fixate on RabbitMQ DNS errors already present in normal-period logs, then reports ts-rabbitmq as root cause."}}
JSONL
```

One case = exactly one appended line. Do NOT prettify with multi-line JSON — one line per record.

**Before starting**, run this once to ensure the file exists and is empty (fresh start):
```
mkdir -p $(dirname {output_path}) && : > {output_path}
```

**After finishing all {n_cases} cases**, verify line count matches with:
```
wc -l {output_path}
```
Expected output: exactly `{n_cases} {output_path}`.

---

## JSON line schema (required fields, all lowercase keys)

- `dataset_index` (int) — from the case list below
- `primary` (str) — EXACT theme name from the taxonomy above, e.g. `T3_Noise-Anchor` for `{agent}` (not `T3` alone, not `Noise-Anchor` alone)
- `pivot_round` (int or null) — the single round where the agent most clearly diverged from reality
- `proximate_cause` (str, ≤10 words) — short phrase describing the divergence
- `reasoning` (str, 1–2 sentences) — grounded justification citing specific Part A facts AND specific Part B rounds/quotes

---

## Procedure per case

1. **Read** the dossier file (use the `Read` tool on the path given below).
2. Part A (GT reality): note the injection type, target service(s), key anomaly signals (z-scores, missing spans, error log patterns) — what the agent *should* have identified.
3. Part B (agent trajectory): scan rounds in order. Identify the single round where the agent's hypothesis most clearly diverged from Part A reality. This is `pivot_round`.
4. Pick the taxonomy theme whose positive criteria best fit this case's divergence pattern. Respect negative criteria. Do NOT hedge with "unclassified" unless no theme's positive criteria apply.
5. Write one JSON line using the schema above.
6. **Immediately append it to the output file** using Bash `cat >> ... <<'JSONL' ... JSONL`.
7. Move to the next case.

---

## Cases to label ({n_cases} total, process in ascending `dataset_index` order)

{case_list}

---

**Begin. For each case: Read dossier → decide → append one JSON line to `{output_path}` → next case. No batched end-of-response output. Use incremental appends so context-exhaustion doesn't lose work.**

When finished, respond with a one-line summary: `Done. Wrote <N> lines to <path>.`
"""


def build_prompt(agent: str, workspace: Path, failed_indices: list[int]) -> str:
    taxonomy_path = workspace / "taxonomy.md"
    taxonomy_text = taxonomy_path.read_text(encoding="utf-8") if taxonomy_path.exists() else "(taxonomy not found)"

    output_path = workspace / "adversarial_labels.jsonl"

    case_lines = []
    for idx in sorted(failed_indices):
        dossier_path = workspace / "dossiers" / f"case_{idx}.md"
        # absolute path so Opus can Read without cwd ambiguity
        case_lines.append(f"- dataset_index={idx}  dossier=`{dossier_path}`")
    case_list = "\n".join(case_lines)

    return PROMPT_TEMPLATE.format(
        agent=agent,
        taxonomy_path=taxonomy_path.relative_to(REPO_ROOT),
        taxonomy_text=taxonomy_text,
        n_cases=len(failed_indices),
        case_list=case_list,
        output_path=str(output_path),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=DEFAULT_DB_URL)
    args = parser.parse_args()

    engine = create_engine(args.db)
    with Session(engine) as session:
        for agent, rel_ws in AGENTS.items():
            ws = REPO_ROOT / rel_ws
            stmt = (
                select(EvaluationSample)
                .where(
                    EvaluationSample.exp_id == agent,
                    EvaluationSample.stage == "judged",
                    EvaluationSample.correct == False,  # noqa: E712
                )
            )
            samples = session.exec(stmt).all()
            failed_indices = [s.dataset_index for s in samples]
            prompt = build_prompt(agent, ws, failed_indices)
            out_path = ws / "adversarial_prompt.md"
            out_path.write_text(prompt, encoding="utf-8")
            logger.info("%s: %d cases -> %s (%.1f KB)",
                        agent, len(failed_indices), out_path,
                        out_path.stat().st_size / 1024)


if __name__ == "__main__":
    main()
