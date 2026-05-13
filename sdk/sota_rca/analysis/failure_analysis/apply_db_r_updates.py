"""X-6.2: Apply R_relabel_db_queue.v3.jsonl to PostgreSQL DB.

For each row with action=relabel_class: set meta.failure_analysis.v1.R = new full class name
For each row with action=remove_label: set meta.failure_analysis.v1.R = null
Old value preserved at meta.failure_analysis.v1.R_v1_baseline for audit.

Skip rows with action=skip_human.

Idempotent via meta.failure_analysis.v1.R_v3_applied=True flag.
Atomic per-row UPDATE in a transaction.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
import subprocess

ROOT = Path("analysis/3-failure-modes/merged")
QUEUE = ROOT / "R_relabel_db_queue.v3.jsonl"
APPLIED_LOG = ROOT / "applied_db_r_updates.v3.jsonl"

# Agent → exp_id mapping
AGENT_EXP_MAP = {
    "aiq": "aiq-qwen3.5-plus",
    "claudecode": "claudecode-qwen3.5-plus",
    "sonnet": "thinkdepthai-claude-sonnet-4.6",
    "qwen": "thinkdepthai-qwen3.5-plus",
}

# U short → full
SHORT_TO_FULL = {
    "U1": "U1_LoudnessAnchorOverSilentVictim",
    "U2": "U2_ChronicAmbientNoiseAnchor",
    "U3": "U3_EdgeDirectionOrRegionEndpointError",
    "U4": "U4_NameTwinSiblingConfusion",
    "U5": "U5_SilenceReadAsHealthOrPaused",
}


def resolve(new_class: str | None) -> str | None:
    if not new_class:
        return None
    s = new_class.strip().split(" or ")[0].strip()
    if s in SHORT_TO_FULL:
        return SHORT_TO_FULL[s]
    if s in SHORT_TO_FULL.values():
        return s
    if s.startswith("aiq.") or s.startswith("claudecode.") or s.startswith("sonnet.") or s.startswith("qwen."):
        return s
    return None


def write_jsonl_append(path: Path, row: dict):
    with path.open("a") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()
        os.fsync(f.fileno())


def run_sql(sql: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["docker", "exec", "-i", "sota-agents-postgres",
         "psql", "-U", "postgres", "-d", "SOTA-Agents",
         "-v", "ON_ERROR_STOP=1", "-q", "-X", "-A", "-t",
         "-c", sql],
        capture_output=True, text=True, check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def esc(s: str) -> str:
    return s.replace("'", "''")


def main():
    rows = []
    with QUEUE.open() as f:
        for line in f:
            rows.append(json.loads(line))

    n_apply = 0
    n_skip = 0
    n_fail = 0
    n_already = 0
    if APPLIED_LOG.exists():
        APPLIED_LOG.unlink()

    for r in rows:
        action = r["action"]
        agent = r["agent"]
        cid = r["case_id"]
        exp_id = AGENT_EXP_MAP.get(agent)
        if not exp_id:
            continue
        if action == "skip_human":
            n_skip += 1
            continue

        if action == "relabel_class":
            new_full = resolve(r.get("new_class"))
            if not new_full:
                n_fail += 1
                write_jsonl_append(APPLIED_LOG, {**r, "_status": "fail_resolve"})
                continue
            sql = (
                "UPDATE evaluation_data SET meta = (("
                "  COALESCE(meta::jsonb, '{}'::jsonb)"
                "  || jsonb_build_object('failure_analysis',"
                "       COALESCE(meta::jsonb -> 'failure_analysis', '{}'::jsonb)"
                "       || jsonb_build_object('v1',"
                "            COALESCE(meta::jsonb -> 'failure_analysis' -> 'v1', '{}'::jsonb)"
                f"            || jsonb_build_object('R', '{esc(new_full)}'::text,"
                "                                  'R_v1_baseline', meta::jsonb -> 'failure_analysis' -> 'v1' -> 'R',"
                "                                  'R_v3_applied', true)"
                "          )"
                "     )"
                ")::text)::json "
                f"WHERE exp_id = '{esc(exp_id)}' AND dataset_index = {int(cid)} "
                "AND COALESCE((meta::jsonb -> 'failure_analysis' -> 'v1' ->> 'R_v3_applied')::boolean, false) = false "
                "RETURNING dataset_index;"
            )
        elif action == "remove_label":
            sql = (
                "UPDATE evaluation_data SET meta = (("
                "  COALESCE(meta::jsonb, '{}'::jsonb)"
                "  || jsonb_build_object('failure_analysis',"
                "       COALESCE(meta::jsonb -> 'failure_analysis', '{}'::jsonb)"
                "       || jsonb_build_object('v1',"
                "            COALESCE(meta::jsonb -> 'failure_analysis' -> 'v1', '{}'::jsonb)"
                "            || jsonb_build_object('R', null::jsonb,"
                "                                  'R_v1_baseline', meta::jsonb -> 'failure_analysis' -> 'v1' -> 'R',"
                "                                  'R_v3_applied', true)"
                "          )"
                "     )"
                ")::text)::json "
                f"WHERE exp_id = '{esc(exp_id)}' AND dataset_index = {int(cid)} "
                "AND COALESCE((meta::jsonb -> 'failure_analysis' -> 'v1' ->> 'R_v3_applied')::boolean, false) = false "
                "RETURNING dataset_index;"
            )
        else:
            continue

        rc, out = run_sql(sql)
        if rc != 0:
            n_fail += 1
            write_jsonl_append(APPLIED_LOG, {**r, "_status": "fail_sql", "_error": out[:300]})
            continue
        if not out.strip():
            n_already += 1
            write_jsonl_append(APPLIED_LOG, {**r, "_status": "already_or_not_found"})
            continue
        n_apply += 1
        write_jsonl_append(APPLIED_LOG, {**r, "_status": "applied", "_dataset_index": out.strip()})

    print(f"applied: {n_apply}; already_or_not_found: {n_already}; skip_human: {n_skip}; failed: {n_fail}")
    print(f"audit log: {APPLIED_LOG}")


if __name__ == "__main__":
    main()
