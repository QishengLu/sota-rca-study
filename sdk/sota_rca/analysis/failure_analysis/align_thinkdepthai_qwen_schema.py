#!/usr/bin/env python
"""Phase 4b — thinkdepthai-qwen3.5-plus schema alignment.

One-off migration that:
  1. Backs up the original `v2/labels.jsonl` to `v2/labels.jsonl.pre_4b_backup`.
  2. Emits `v2/labels_aligned.jsonl` with the unified 6-field schema used by the
     other three agents (primary / secondary / pivot_round / proximate_cause /
     evidence / labeler), resolving `label` (T1..T9) to `T<n>_<theme-name>` via
     the mapping table in `v2/taxonomy.md`.
  3. Overwrites `meta.failure_analysis.v1` on the 105 judged rows to match the
     aligned schema. Any pre-existing `R`, `D`, `T`, `gt_services`, `predicted`
     keys in v1 are dropped — Phase 6.5 will re-derive D/R per-case.
  4. Verifies 5 random rows round-trip (DB -> in-memory) for correctness.

The old `R`/`D` values (derived via T->R and fault_subtype->D lookup tables)
are preserved ONLY in the backup JSONL file for audit traceability.

Usage:
    cd RCAgentEval
    uv run python scripts/failure_analysis/align_thinkdepthai_qwen_schema.py
    # Custom paths / dry-run:
    uv run python scripts/failure_analysis/align_thinkdepthai_qwen_schema.py \\
        --labels /path/to/labels.jsonl \\
        --output /path/to/labels_aligned.jsonl \\
        --backup /path/to/labels.jsonl.pre_4b_backup \\
        --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import shutil
import sys
from pathlib import Path

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, create_engine, select

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# T-label -> canonical theme name, taken verbatim from
# analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/taxonomy.md
# (column "Theme name", pre-arrow short form; e.g. "Silence-as-Health" not "Absence-Inference").
T_TO_THEME_NAME: dict[str, str] = {
    "T1": "T1_Silence-as-Health",
    "T2": "T2_Blame-the-Messenger",
    "T3": "T3_Noise-Anchor",
    "T4": "T4_Amplitude-Greed",
    "T5": "T5_Query-Blindness",
    "T6": "T6_Path-Through",
    "T7": "T7_Business-Logic-Confabulation",
    "T8": "T8_Causal-Inversion",
    "T9": "T9_Over-Tracing",
}

DEFAULT_LABELER = "claude-opus-4.6-human-readthrough"
VERSION_KEY = "v1"
DEFAULT_EXP_ID = "thinkdepthai-qwen3.5-plus"
DEFAULT_DB_URL = "postgresql://postgres:postgres@localhost:5433/SOTA-Agents"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LABELS = (
    REPO_ROOT
    / "analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/labels.jsonl"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/labels_aligned.jsonl"
)
DEFAULT_BACKUP = (
    REPO_ROOT
    / "analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/labels.jsonl.pre_4b_backup"
)


def align_record(rec: dict, exp_id: str) -> dict:
    required = ("case", "label", "pivot_round", "proximate_cause")
    missing = [k for k in required if k not in rec]
    if missing:
        raise ValueError(f"Record case={rec.get('case')!r} missing fields: {missing}")

    t_label = rec["label"]
    if t_label not in T_TO_THEME_NAME:
        raise ValueError(f"Unknown T label {t_label!r} in case {rec['case']}")

    return {
        "dataset_index": int(rec["case"]),
        "exp_id": exp_id,
        "primary": T_TO_THEME_NAME[t_label],
        "secondary": [],
        "pivot_round": int(rec["pivot_round"]),
        "proximate_cause": rec["proximate_cause"],
        "evidence": "",
        "labeler": DEFAULT_LABELER,
    }


def backup_original(labels_path: Path, backup_path: Path) -> None:
    if backup_path.exists():
        logger.info("Backup already present at %s — leaving untouched", backup_path)
        return
    shutil.copy2(labels_path, backup_path)
    logger.info("Backed up original -> %s", backup_path)


def write_aligned_file(aligned: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in aligned)
    output_path.write_text(body + "\n", encoding="utf-8")
    logger.info("Wrote %d aligned records -> %s", len(aligned), output_path)


def db_write(records: list[dict], db_url: str, dry_run: bool) -> tuple[int, int]:
    engine = create_engine(db_url)
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
            if sample is None:
                logger.warning(
                    "No judged sample for exp_id=%s dataset_index=%d",
                    rec["exp_id"],
                    rec["dataset_index"],
                )
                missing += 1
                continue
            meta = sample.meta or {}
            fa = meta.get("failure_analysis") or {}
            # Overwrite v1 entirely — drops any old T/R/D/gt_services/predicted keys.
            fa[VERSION_KEY] = {
                "primary": rec["primary"],
                "secondary": rec["secondary"],
                "pivot_round": rec["pivot_round"],
                "proximate_cause": rec["proximate_cause"],
                "evidence": rec["evidence"],
                "labeler": rec["labeler"],
            }
            meta["failure_analysis"] = fa
            sample.meta = meta
            if not dry_run:
                flag_modified(sample, "meta")
                session.add(sample)
            updated += 1
        if not dry_run:
            session.commit()
    action = "would update" if dry_run else "updated"
    logger.info("DB %s %d rows (%d missing)", action, updated, missing)
    return updated, missing


def verify_sample(records: list[dict], db_url: str, n: int, seed: int) -> bool:
    rng = random.Random(seed)
    picks = rng.sample(records, min(n, len(records)))
    engine = create_engine(db_url)
    all_ok = True
    with Session(engine) as session:
        for rec in picks:
            stmt = select(EvaluationSample).where(
                EvaluationSample.exp_id == rec["exp_id"],
                EvaluationSample.dataset_index == rec["dataset_index"],
                EvaluationSample.stage == "judged",
            )
            sample = session.exec(stmt).first()
            fa = (sample.meta or {}).get("failure_analysis", {}).get(VERSION_KEY, {}) if sample else {}
            checks = {
                "primary_match": fa.get("primary") == rec["primary"],
                "secondary_empty": fa.get("secondary") == [],
                "pivot_round_match": fa.get("pivot_round") == rec["pivot_round"],
                "proximate_cause_match": fa.get("proximate_cause") == rec["proximate_cause"],
                "evidence_empty": fa.get("evidence") == "",
                "labeler_match": fa.get("labeler") == rec["labeler"],
                "R_dropped": "R" not in fa,
                "D_dropped": "D" not in fa,
                "T_dropped": "T" not in fa,
                "schema_size": len(fa) == 6,
            }
            failures = [k for k, v in checks.items() if not v]
            status = "OK" if not failures else "FAIL"
            all_ok = all_ok and not failures
            logger.info(
                "VERIFY idx=%s  %s  primary=%s  pivot=%s  fa_keys=%s%s",
                rec["dataset_index"],
                status,
                fa.get("primary"),
                fa.get("pivot_round"),
                sorted(fa.keys()),
                "" if not failures else f"  failed_checks={failures}",
            )
    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--backup", type=Path, default=DEFAULT_BACKUP)
    parser.add_argument("--exp_id", default=DEFAULT_EXP_ID)
    parser.add_argument("--db", default=DEFAULT_DB_URL)
    parser.add_argument("--dry-run", action="store_true", help="Skip DB writes")
    parser.add_argument("--verify-samples", type=int, default=5)
    parser.add_argument("--verify-seed", type=int, default=42)
    args = parser.parse_args()

    raw_lines = [
        line.strip()
        for line in args.labels.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    rows = [json.loads(line) for line in raw_lines]
    logger.info("Read %d records from %s", len(rows), args.labels)

    backup_original(args.labels, args.backup)

    aligned = [align_record(r, args.exp_id) for r in rows]
    logger.info("Aligned %d records (R/D dropped)", len(aligned))

    write_aligned_file(aligned, args.output)

    _, missing = db_write(aligned, args.db, args.dry_run)
    if missing:
        logger.warning("%d records had no matching judged sample", missing)

    if args.dry_run:
        logger.info("--dry-run set; skipping round-trip verification")
        return

    logger.info("Running round-trip verification on %d random samples...", args.verify_samples)
    ok = verify_sample(aligned, args.db, args.verify_samples, args.verify_seed)
    if not ok:
        logger.error("Verification FAILED — see per-row output above")
        sys.exit(2)
    logger.info("Verification OK")


if __name__ == "__main__":
    main()
