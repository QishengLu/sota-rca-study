#!/usr/bin/env python
"""Write R-axis labels to evaluation_data.meta.failure_analysis.v1.R
for all 4 exp_ids.

Reads:
  1. merged/R_merge_table.jsonl — {agent, per_agent_R, per_agent_count, unified_R, kind}
     kind ∈ {"unified", "framework_specific_analytical"}
  2. Each framework's R_phrases.jsonl — {case_id, r_phrase, ...}
     plus R_inductive.md for the per-agent R name → case_id membership list (parsed
     from **Members** lines).

Approach:
  Step 1: from per-agent R_inductive.md, build case_id → per_agent_R map.
  Step 2: from R_merge_table, build per_agent_R → unified_R map.
  Step 3: for each case, compute unified R = map.get(per_agent_R).
  Step 4: write meta.failure_analysis.v1.R, meta.failure_analysis.v1.per_agent_R,
          meta.failure_analysis.v1.unified_R_kind.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "RCAgentEval")

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402
from sqlmodel import Session, create_engine, select  # noqa: E402
from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from harp_config import DB_URL, FRAMEWORKS, R_MERGE_TABLE  # noqa: E402


CLASS_HEADER = re.compile(r"^##+\s+(?:aiq\.|claudecode\.)?R[\w_]*")

# Per-framework regexes for member-list lines.
# Formats observed:
#   aiq          : `**Members**: 247, 283, 572, ...`
#   claudecode   : `### Members (29)\ncase_ids: 33, 247, ...`
#   sonnet       : `**Member cases**: 675, 1326, ...` OR `**Cases (primary)**: ...`
#   qwen v1_harp : `**Cases (15)**: 156, 341, ...`
_MEMBER_PATTERNS = [
    re.compile(r"\*\*Members\*\*\s*:\s*([^\n]+)"),
    re.compile(r"\*\*Member cases\*\*\s*:\s*([^\n]+)"),
    re.compile(r"\*\*Cases[^*]*\*\*\s*:\s*([^\n]+)"),
    re.compile(r"^\s*case_ids\s*:\s*([^\n]+)", re.MULTILINE),
    re.compile(r"^\s*Cases\s*\(primary\)\s*:\s*([^\n]+)", re.MULTILINE),
]


def _normalize_cls_name(header: str) -> str:
    """Normalize header text to the per_agent_R name used in R_merge_table.jsonl.

    Handles:
      'aiq.R_volume_anchor  (24 cases)'                    → 'R_volume_anchor'
      'R_EdgeDirectionDefault — 19 cases (38%)'            → 'R_EdgeDirectionDefault'
      'R_A — SilentSourceReadAsHealthy (N=15)'             → 'R_A_SilentSourceReadAsHealthy'
      'R1 — SilentOriginShadowedByNoisyNeighbor (29 cases, 28.2%)' → 'R1_SilentOriginShadowedByNoisyNeighbor'
    """
    h = header.strip()
    # drop leading framework prefix
    h = re.sub(r"^(?:aiq|claudecode|sonnet|qwen)\.", "", h)
    # drop trailing parenthesized count/pct/N=...
    h = re.sub(r"\s*\([^)]*\)\s*$", "", h)
    # drop trailing " — 19 cases (…)", " — 19 cases, …"
    h = re.sub(r"\s*—\s*\d+\s*cases.*$", "", h, flags=re.IGNORECASE)
    # the " — " or " - " after an R_A / R1 is used as a separator; join with underscore
    h = re.sub(r"\s*[—-]\s*", "_", h)
    # collapse whitespace
    h = re.sub(r"\s+", "_", h.strip())
    # strip any trailing count text like "_24_cases" that slipped through
    h = re.sub(r"_?\d+_?cases?.*$", "", h, flags=re.IGNORECASE)
    return h.rstrip("_")


_R_CLASS_HEADER_RE = re.compile(
    r"^(#{2,6})\s+((?:aiq\.|claudecode\.|sonnet\.|qwen\.)?R[\w_]*[^\n]*)",
    re.MULTILINE,
)


def parse_per_agent_R_membership(inductive_md: Path) -> dict[int, str]:
    """Parse R_inductive.md to build case_id → per_agent_R_name map.

    Strategy: linearly walk the file; track the "current R class name" based on
    the most recent heading that looks like an R-class header; assign any
    Members/Member cases/Cases line to the current class.
    """
    text = inductive_md.read_text()
    mapping: dict[int, str] = {}
    current_cls: str | None = None

    # Pre-build merged pattern for member lines
    for line in text.splitlines():
        # detect R-class header
        header_match = re.match(r"^(#{2,6})\s+(.+)$", line)
        if header_match:
            raw_header = header_match.group(2).strip()
            # an R-class header contains an R identifier at the beginning (not inside
            # prose like "R-class definitions")
            # heuristic: starts with R followed by _, digit, or letter, AND not
            # followed by "-class" (dash hyphen)
            h_start = raw_header.split()[0] if raw_header else ""
            if (
                re.match(r"^(?:aiq\.|claudecode\.|sonnet\.|qwen\.)?R[\w_]*$", h_start.rstrip("."))
                or re.match(r"^(?:aiq\.|claudecode\.|sonnet\.|qwen\.)?R[\w_]*\b", h_start)
            ):
                if not re.search(r"\bR[- ]class\b", raw_header, re.IGNORECASE) and not raw_header.lower().startswith("r-class"):
                    current_cls = _normalize_cls_name(raw_header)
                    continue
                else:
                    current_cls = None
                    continue
            else:
                # other section header — do NOT reset current_cls if it is a subsection
                # (### Definition, ### Members) under the current R class
                if header_match.group(1) == "##" or header_match.group(1) == "#":
                    # top-level section header → reset
                    current_cls = None
                continue

        # try to match Members line
        if current_cls is None:
            continue
        for pat in _MEMBER_PATTERNS:
            m = pat.search(line)
            if m:
                ids = [int(x) for x in re.findall(r"\b(\d{2,6})\b", m.group(1))]
                for i in ids:
                    mapping[i] = current_cls
                break

    return mapping


def main(dry_run: bool) -> None:
    merge_rows = [json.loads(line) for line in R_MERGE_TABLE.open()]
    # build per_agent_R → (unified_R, kind)
    merge_map: dict[tuple[str, str], tuple[str, str]] = {}
    for m in merge_rows:
        key = (m["agent"], m["per_agent_R"])
        merge_map[key] = (m["unified_R"], m.get("kind", "unified"))

    engine = create_engine(DB_URL)
    totals = {}

    with Session(engine) as s:
        for agent_key, (exp_id, labels_path, _field, ws) in FRAMEWORKS.items():
            inductive = ws / "R_inductive.md"
            if not inductive.exists():
                print(f"[{agent_key}] MISSING R_inductive.md at {inductive} — skipping")
                continue
            case_to_R = parse_per_agent_R_membership(inductive)
            print(f"[{agent_key}] parsed {len(case_to_R)} case→R_class memberships from R_inductive.md")

            stmt = select(EvaluationSample).where(
                EvaluationSample.exp_id == exp_id,
                EvaluationSample.correct == False,  # noqa: E712
                EvaluationSample.stage == "judged",
            )
            samples = list(s.exec(stmt).all())
            updated = skipped_no_R = skipped_no_merge = 0
            for sample in samples:
                per_agent_R = case_to_R.get(sample.dataset_index)
                if not per_agent_R:
                    skipped_no_R += 1
                    continue
                merge_hit = merge_map.get((agent_key, per_agent_R))
                if not merge_hit:
                    # try match by stripping agent prefix from per_agent_R
                    merge_hit = merge_map.get((agent_key, per_agent_R.split(".", 1)[-1]))
                if not merge_hit:
                    skipped_no_merge += 1
                    continue
                unified_R, kind = merge_hit
                meta = sample.meta or {}
                fa = meta.setdefault("failure_analysis", {})
                v1 = fa.setdefault("v1", {})
                v1["R"] = unified_R
                v1["per_agent_R"] = per_agent_R
                v1["unified_R_kind"] = kind
                sample.meta = meta
                flag_modified(sample, "meta")
                updated += 1
            totals[agent_key] = (updated, skipped_no_R, skipped_no_merge)
            print(f"[{agent_key}] update={updated}, skip_no_R_in_inductive={skipped_no_R}, skip_no_merge_row={skipped_no_merge}")

        if not dry_run:
            s.commit()
            print("COMMITTED")
        else:
            print("DRY RUN (no commit)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
