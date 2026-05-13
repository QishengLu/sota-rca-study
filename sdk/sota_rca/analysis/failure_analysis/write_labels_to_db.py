#!/usr/bin/env python
"""Phase 4 — Mechanical DB writeback of failure-mode labels.

Reads a flat JSONL (one record per case) and writes into
`meta.failure_analysis.v1` using SQLAlchemy `flag_modified` (critical — otherwise
JSON column mutations are silently dropped on commit).

Input JSONL schema (one object per line):
    {
      "dataset_index": 4032,
      "exp_id": "thinkdepthai-qwen3.5-plus",
      "primary": "stopped_at_loudest_caller",
      "secondary": ["missed_missing_span"],
      "pivot_round": 12,
      "evidence": "Round 12 think_tool: 'ts-basic-service has 278 SEVERE errors...'",
      "labeler": "claude-opus-4.6-human-readthrough",
      "notes": ""
    }

Only the five required fields (dataset_index, exp_id, primary, pivot_round, evidence)
must be present. secondary/labeler/notes default to sensible values.

Usage:
    cd RCAgentEval
    uv run python scripts/failure_analysis/write_labels_to_db.py \\
        --db postgresql://postgres:postgres@localhost:5433/SOTA-Agents \\
        --labels analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/labels.jsonl

    # Dry run (no writes)
    uv run python scripts/failure_analysis/write_labels_to_db.py \\
        --db postgresql://postgres:postgres@localhost:5433/SOTA-Agents \\
        --labels labels.jsonl --dry-run

    # Dump DB labels back to a JSONL (round-trip verification)
    uv run python scripts/failure_analysis/write_labels_to_db.py \\
        --db postgresql://postgres:postgres@localhost:5433/SOTA-Agents \\
        --exp_id thinkdepthai-qwen3.5-plus \\
        --dump /tmp/labels_roundtrip.jsonl
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, create_engine, select

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_LABELER = "claude-opus-4.6-human-readthrough"
VERSION_KEY = "v1"


def get_engine(db_url: str):
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(db_url, connect_args=connect_args)


def validate_record(rec: dict, line_no: int) -> tuple[bool, str]:
    required = ("dataset_index", "exp_id", "primary", "pivot_round", "evidence")
    for k in required:
        if k not in rec:
            return False, f"line {line_no}: missing required field `{k}`"
    if not isinstance(rec["dataset_index"], int):
        return False, f"line {line_no}: dataset_index must be int, got {type(rec['dataset_index']).__name__}"
    if not isinstance(rec["pivot_round"], int):
        return False, f"line {line_no}: pivot_round must be int"
    if not isinstance(rec["primary"], str) or not rec["primary"]:
        return False, f"line {line_no}: primary must be non-empty string"
    if "secondary" in rec and not isinstance(rec["secondary"], list):
        return False, f"line {line_no}: secondary must be list"
    return True, ""


def run_write(args) -> None:
    lines = Path(args.labels).read_text(encoding="utf-8").splitlines()
    records: list[dict] = []
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.error("line %d: bad JSON: %s", i, exc)
            sys.exit(1)
        ok, msg = validate_record(rec, i)
        if not ok:
            logger.error(msg)
            sys.exit(1)
        records.append(rec)
    logger.info("Validated %d label records", len(records))

    if args.dry_run:
        logger.info("--dry-run set, skipping DB writes")
        return

    engine = get_engine(args.db)
    updated = 0
    missing = 0
    with Session(engine) as session:
        for rec in records:
            stmt = select(EvaluationSample).where(
                EvaluationSample.exp_id == rec["exp_id"],
                EvaluationSample.dataset_index == rec["dataset_index"],
                EvaluationSample.stage == "judged",
            )
            sample = session.exec(stmt).first()
            if not sample:
                logger.warning("no judged sample for exp_id=%s idx=%d", rec["exp_id"], rec["dataset_index"])
                missing += 1
                continue
            meta = sample.meta or {}
            fa = meta.get("failure_analysis") or {}
            fa[VERSION_KEY] = {
                "primary": rec["primary"],
                "secondary": rec.get("secondary") or [],
                "pivot_round": rec["pivot_round"],
                "evidence": rec["evidence"],
                "labeler": rec.get("labeler", DEFAULT_LABELER),
                "notes": rec.get("notes", ""),
            }
            meta["failure_analysis"] = fa
            sample.meta = meta
            flag_modified(sample, "meta")  # critical for JSON column
            session.add(sample)
            updated += 1
        session.commit()
    logger.info("Done: wrote %d labels, %d samples missing", updated, missing)


def run_dump(args) -> None:
    engine = get_engine(args.db)
    out_lines: list[str] = []
    with Session(engine) as session:
        stmt = select(EvaluationSample).where(
            EvaluationSample.exp_id == args.exp_id,
            EvaluationSample.stage == "judged",
        )
        for sample in session.exec(stmt).all():
            meta = sample.meta or {}
            fa = (meta.get("failure_analysis") or {}).get(VERSION_KEY)
            if not fa:
                continue
            out = {
                "dataset_index": sample.dataset_index,
                "exp_id": sample.exp_id,
                "primary": fa.get("primary"),
                "secondary": fa.get("secondary") or [],
                "pivot_round": fa.get("pivot_round"),
                "evidence": fa.get("evidence"),
                "labeler": fa.get("labeler"),
                "notes": fa.get("notes", ""),
            }
            out_lines.append(json.dumps(out, ensure_ascii=False))
    out_lines.sort()  # deterministic for byte-identical round-trip
    Path(args.dump).write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")
    logger.info("Dumped %d labels to %s", len(out_lines), args.dump)


def main():
    p = argparse.ArgumentParser(description="Phase 4 — DB writeback for failure-mode labels")
    p.add_argument("--db", required=True)
    p.add_argument("--labels", help="Input JSONL file (write mode)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--dump", help="Dump DB labels to a JSONL file (read mode)")
    p.add_argument("--exp_id", default="thinkdepthai-qwen3.5-plus", help="Used in --dump mode")
    args = p.parse_args()

    if args.dump:
        run_dump(args)
    elif args.labels:
        run_write(args)
    else:
        p.error("Specify either --labels <file> (write) or --dump <file> (read)")


if __name__ == "__main__":
    main()
