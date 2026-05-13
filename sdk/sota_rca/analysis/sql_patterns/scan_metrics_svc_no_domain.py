#!/usr/bin/env python
"""Classify remaining pending METRICS SQLs with svc filter but NO metric domain keyword.

Rule: metric_scan (exploratory scan across all metric types for selected services)

Scope: abnormal_metrics / histogram / sum; no normal_*; no logs/traces.
Match: WHERE has service_name (=/IN/LIKE/!=/NOT IN), no metric domain keyword anywhere
in metric literals.
"""
import argparse
import json
import re
import sys
from collections import Counter

from sqlalchemy import create_engine, text
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session

sys.path.insert(0, str(__file__).rsplit("/scripts/", 1)[0])
from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402
from sota_rca.analysis.llm_intent_classifier import extract_sql_rounds  # noqa: E402
from sota_rca.analysis.trajectory_normalizer import normalize_by_agent  # noqa: E402

EXPS = [
    "thinkdepthai-claude-sonnet-4.6",
    "thinkdepthai-qwen3.5-plus",
    "aiq-qwen3.5-plus",
    "claudecode-qwen3.5-plus",
    "taskweaver-qwen3.5-plus",
]
DB_URL = "postgresql://postgres:postgres@localhost:5433/SOTA-Agents"
VOTE_KEYS = ["claude_opus_4_6", "gemini_3_1_pro_preview", "claude_opus_4_7_arbiter", "claude_opus_4_6_arbiter"]

DOMAIN_PAT = re.compile(
    r"\bJVM\b|\bGC\b|THREAD|HEAP|HIKARI|"
    r"\bDB\b|MYSQL|\bCONN\b|\bSQL\b|"
    r"HTTP|\bNET\b|NETWORK|\bTCP\b|HUBBLE|PACKET|\bDROP\b|LATENCY|DURATION|REQUEST|"
    r"CPU|MEMORY|\bMEM\b|OOM|FILESYSTEM|\bDISK\b|"
    r"RESTART|\bKILL\b|\bPHASE\b|READY|TERMINAT|EVICT|DEPLOY|\bPOD\b"
)


def extract_metric_lits(where: str) -> list[str]:
    lits: list[str] = []
    for m in re.finditer(r"\bMETRIC\s*(?:=|LIKE)\s*'([^']+)'", where):
        lits.append(m.group(1))
    for m in re.finditer(r"\bMETRIC\s+IN\s*\(([^)]+)\)", where):
        lits.extend(re.findall(r"'([^']+)'", m.group(1)))
    return lits


def classify(sql: str) -> tuple[str | None, str]:
    u = sql.upper()

    # FROM abnormal_metrics only
    has_ab_metric = bool(re.search(
        r"\b(?:FROM|JOIN)\s+[^;]{0,160}?ABNORMAL_METRICS(?:_HISTOGRAM|_SUM)?\b", u, re.DOTALL))
    has_bare = bool(re.search(r"\b(?:FROM|JOIN)\s+METRICS(?:_HISTOGRAM|_SUM)?\b", u))
    has_nm = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,160}?(?<!AB)NORMAL_METRICS", u, re.DOTALL))
    has_logs = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,160}?(?:AB)?NORMAL_LOGS\b|\b(?:FROM|JOIN)\s+LOGS\b", u, re.DOTALL))
    has_traces = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,160}?(?:AB)?NORMAL_TRACES\b|\b(?:FROM|JOIN)\s+TRACES\b", u, re.DOTALL))
    if has_nm:
        return None, "normal_metrics"
    if has_logs or has_traces:
        return None, "cross-modal"
    if not (has_ab_metric or has_bare):
        return None, "not metrics"

    # Replace quoted literal CONTENT with underscores (same length) to avoid
    # 'ts-order-...' triggering ORDER-BY early termination, while keeping positions.
    def _mask(m):
        return "'" + "_" * (len(m.group(0)) - 2) + "'"
    masked_u = re.sub(r"'[^']*'", _mask, u)
    wm = re.search(r"\bWHERE\b(.*?)(?:\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|\bUNION\b|\bHAVING\b|$)",
                   masked_u, re.DOTALL)
    if wm:
        w_start, w_end = wm.span(1)
        where = u[w_start:w_end]
    else:
        where = ""

    # Must have svc filter
    has_svc = bool(re.search(r"\bSERVICE_NAME\s*(=|IN|!=|<>|LIKE|\bNOT\s+IN\b)", where))
    if not has_svc:
        return None, "no service_name filter"

    # Skip if SELECT has MIN/MAX(time) → error_timeline territory
    sel_m = re.search(r"\bSELECT\b(.*?)\bFROM\b", u, re.DOTALL)
    if sel_m and re.search(r"(MIN|MAX)\s*\(\s*TIME", sel_m.group(1)):
        return None, "MIN/MAX(time) (error_timeline)"

    # Must have NO metric domain keyword (in metric literals or in any LIKE)
    lits = extract_metric_lits(where)
    if any(DOMAIN_PAT.search(l.upper()) for l in lits):
        return None, "has metric domain keyword in literal"
    # Also skip if any METRIC filter is present at all (even if keyword doesn't match domain)
    # — conservative: if agent specifies a metric explicitly, leave to manual
    if lits:
        return None, "has specific metric filter"

    return "metric_scan", "user_metrics_svc_no_domain"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    args = p.parse_args()

    eng = create_engine(DB_URL)
    total_pending = 0
    reject_counter: Counter = Counter()
    match_count = 0
    votes: Counter = Counter()
    examples: list[dict] = []
    staged: list[dict] = []

    with eng.connect() as c:
        for exp in EXPS:
            agent = exp.split("-", 1)[0]
            rows = c.execute(
                text("SELECT dataset_index, trajectories, meta FROM evaluation_data "
                     "WHERE exp_id=:e AND stage='judged'"),
                {"e": exp},
            ).fetchall()
            for idx, traj_raw, meta_raw in rows:
                traj = json.loads(traj_raw) if isinstance(traj_raw, str) else traj_raw
                meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
                if not traj or not meta:
                    continue
                finals = (meta.get("llm_intents") or {}).get("final", [])
                done = {(e["round"], e["sql_index"]) for e in finals}
                try:
                    rounds = extract_sql_rounds(normalize_by_agent(agent, traj))
                except Exception:
                    continue
                llm = meta.get("llm_intents") or {}

                def v_at(key, r, si):
                    for e in llm.get(key, []) or []:
                        if e.get("round") == r and e.get("sql_index") == si:
                            return e.get("intent")
                    return None

                for rnd in rounds:
                    for si0, sql in enumerate(rnd.queries):
                        si = si0 + 1
                        pos = (rnd.round_index, si)
                        if pos in done:
                            continue
                        total_pending += 1
                        intent, tag = classify(sql)
                        if intent is None:
                            reject_counter[tag] += 1
                            continue
                        match_count += 1
                        vv = {vk: v_at(vk, *pos) for vk in VOTE_KEYS}
                        for v in vv.values():
                            if v:
                                votes[v] += 1
                        if len(examples) < 8:
                            examples.append({"exp": exp, "idx": idx, "pos": pos, "sql": sql, "votes": vv})
                        staged.append({
                            "exp": exp, "idx": idx, "round": pos[0],
                            "sql_index": pos[1], "intent": intent, "rule": tag,
                        })

    print(f"Total pending scanned: {total_pending}")
    print(f"Matches: {match_count} → metric_scan")
    print(f"\nLLM vote distribution on matched:")
    for v, n in votes.most_common():
        print(f"  {v}: {n}")
    print(f"\nRejection reasons (top 8):")
    for r, n in reject_counter.most_common(8):
        print(f"  {r}: {n}")
    print(f"\n=== Sample matched (up to 8) ===")
    for i, ex in enumerate(examples, 1):
        print(f"\n--- [{i}] {ex['exp']} case={ex['idx']} r={ex['pos'][0]} si={ex['pos'][1]}")
        print(f"VOTES: {ex['votes']}")
        print(ex["sql"][:400])

    if not args.write:
        print("\n(dry-run — pass --write to commit.)")
        return

    per_sample: dict[tuple[str, int], list[dict]] = {}
    for s in staged:
        per_sample.setdefault((s["exp"], s["idx"]), []).append(
            {"round": s["round"], "sql_index": s["sql_index"], "intent": s["intent"], "rule": s["rule"]}
        )
    written = 0
    with Session(eng) as sess:
        for (exp, idx), new_entries in per_sample.items():
            row = sess.execute(
                text("SELECT id FROM evaluation_data WHERE exp_id=:e AND dataset_index=:i AND stage='judged'"),
                {"e": exp, "i": idx},
            ).first()
            if not row:
                continue
            obj = sess.get(EvaluationSample, row[0])
            if not obj:
                continue
            meta = dict(obj.meta or {})
            llm = dict(meta.get("llm_intents") or {})
            finals = list(llm.get("final") or [])
            existing = {(e["round"], e["sql_index"]) for e in finals}
            for ent in new_entries:
                if (ent["round"], ent["sql_index"]) in existing:
                    continue
                finals.append(ent)
                written += 1
            llm["final"] = finals
            meta["llm_intents"] = llm
            obj.meta = meta
            flag_modified(obj, "meta")
        sess.commit()
    print(f"Wrote {written} new final entries.")


if __name__ == "__main__":
    main()
