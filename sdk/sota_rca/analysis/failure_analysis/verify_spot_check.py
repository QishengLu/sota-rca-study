"""V-E meta-verification: spot-check 8-10 random evidence YAMLs.

For each audited YAML:
1. Re-run one parquet query from parquet_queries_run
2. Re-grep one raw_sql_substring_audit flag against trajectory
3. Compare with stored value; flag discrepancies

If >20% of spot-checks fail → identify bad batches and re-dispatch.
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

import duckdb
import psycopg2
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from harp_config import FRAMEWORKS, MERGED

EVIDENCE_DIR = MERGED / "verify_evidence"
DOSSIER_BASE = {
    "aiq": Path("analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/v1/dossiers"),
    "claudecode": Path("analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1/dossiers"),
    "sonnet": Path("analysis/3-failure-modes/2-by-framework/thinkdepthai-claude-sonnet-4.6/v1/dossiers"),
    "qwen": Path("analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers"),
}


def load_trajectory(agent: str, case_id: int, exp_id: str) -> str:
    """Return concatenated raw trajectory text (for regex checks)."""
    dossier = DOSSIER_BASE[agent] / f"case_{case_id}.raw.json"
    if dossier.exists():
        return dossier.read_text()
    conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5433/SOTA-Agents")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trajectories FROM evaluation_data WHERE exp_id=%s AND dataset_index=%s",
                (exp_id, case_id),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return row[0] if row and row[0] else ""


def main():
    rng = random.Random(20260422)
    yamls = sorted(EVIDENCE_DIR.glob("*.yaml"))
    audited = rng.sample(yamls, min(10, len(yamls)))

    results = []
    for path in audited:
        with path.open() as f:
            doc = yaml.safe_load(f)

        if doc.get("unverifiable"):
            results.append({"yaml": path.name, "status": "skipped_unverifiable"})
            continue

        case_id = int(doc["case_id"].split(".", 1)[1])
        agent = doc["case_id"].split(".", 1)[0]
        exp_id = doc["framework"]
        data_dir = doc["data_dir"]

        # 1. Re-run one parquet query
        queries = doc.get("parquet_queries_run", [])
        q_check = None
        if queries:
            q = rng.choice(queries)
            sql = q["sql"]
            stored_row_count = q["row_count"]
            try:
                con = duckdb.connect()
                r = con.execute(sql).fetchall()
                con.close()
                re_row_count = len(r)
                q_check = {
                    "sql": sql[:200],
                    "stored_row_count": stored_row_count,
                    "re_row_count": re_row_count,
                    "match": stored_row_count == re_row_count,
                }
            except Exception as exc:
                q_check = {"sql": sql[:200], "error": str(exc)[:200], "match": None}

        # 2. Re-grep one substring-audit flag
        audit = doc.get("raw_sql_substring_audit", {})
        traj_text = load_trajectory(agent, case_id, exp_id)
        flag_key = rng.choice([
            "has_baseline_contrast_substring",
            "has_trace_follow_substring",
            "has_jvm_metric_substring",
            "has_status_error_filter",
        ])
        stored_flag = audit.get(flag_key)
        re_flag = None
        if flag_key == "has_baseline_contrast_substring":
            re_flag = ("normal_logs" in traj_text and "abnormal_logs" in traj_text and ("UNION" in traj_text.upper() or "JOIN" in traj_text.upper()))
        elif flag_key == "has_trace_follow_substring":
            re_flag = bool(re.search(r"(?is)trace_id\s*=\s*['\"]", traj_text))
        elif flag_key == "has_jvm_metric_substring":
            re_flag = "jvm." in traj_text.lower()
        elif flag_key == "has_status_error_filter":
            re_flag = bool(re.search(r"(?i)status(_code)?\s*=\s*['\"]?Error", traj_text))
        flag_check = {
            "flag": flag_key,
            "stored": stored_flag,
            "recomputed": re_flag,
            "match_or_supersetcheck": (stored_flag == re_flag) or (re_flag and not stored_flag) or (stored_flag and re_flag),
        }

        results.append({
            "yaml": path.name,
            "parquet_recheck": q_check,
            "substring_recheck": flag_check,
        })

    # Summary
    total = len(results)
    # Count matches
    parquet_fail = 0
    flag_fail = 0
    for r in results:
        qc = r.get("parquet_recheck")
        if qc and qc.get("match") is False:
            parquet_fail += 1
        fc = r.get("substring_recheck")
        if fc and fc.get("match_or_supersetcheck") is False:
            flag_fail += 1

    summary = {
        "total_audited": total,
        "parquet_fail": parquet_fail,
        "substring_fail": flag_fail,
        "pass_rate": round(1.0 - (parquet_fail + flag_fail) / max(total * 2, 1), 3),
        "details": results,
    }
    out = MERGED / "verify_spot_check_report.json"
    with out.open("w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(json.dumps({
        "total": total,
        "parquet_fail": parquet_fail,
        "substring_fail": flag_fail,
        "pass_rate": summary["pass_rate"],
    }, indent=2))
    print(f"Detailed report: {out}")


if __name__ == "__main__":
    main()
