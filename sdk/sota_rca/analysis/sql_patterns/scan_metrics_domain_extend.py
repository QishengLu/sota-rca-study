#!/usr/bin/env python
"""Extend metric-domain classification to remaining pending METRICS SQLs.

Rules (priority order, first match):
  1. metric LIKE contains cpu/memory/disk/filesystem/oom  → container_resource [user_metrics_cpu_mem]
  2. metric LIKE contains jvm/gc/thread/heap/hikari       → jvm_state         [user_metrics_jvm]
  3. metric LIKE contains http/tcp/net/hubble/packet/
     drop/latency/duration/request                        → network_layer    [user_metrics_network]
  4. metric LIKE contains restart/kill/pod/phase/ready/
     terminat/evict/deploy                                → k8s_state        [user_metrics_k8s]
  5. metric LIKE contains db/mysql/conn/sql               → db_state         [user_metrics_db]
  6. svc= but metric no domain (SKIP, leave pending)      — needs manual
  7. no svc, no domain keyword                            → metric_scan      [user_metrics_scan]

Applies to abnormal_metrics / abnormal_metrics_histogram / abnormal_metrics_sum.
Skips normal_metrics (baseline territory — already handled).
Also skips cross-modal and if multiple domain keywords match across families
(mixed-domain is left pending).
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

# Per-literal domain match (priority order, first match wins within a single literal).
# This handles cases like "jvm.cpu.X" → jvm (not container), "k8s.pod.cpu.X" → container (CPU is primary).
DOMAINS = [
    ("jvm_state", "user_metrics_jvm",
     r"\bJVM\b|\bGC\b|THREAD|HEAP|HIKARI"),
    ("db_state", "user_metrics_db",
     r"\bDB\b|MYSQL|\bCONN\b|\bSQL\b"),
    ("network_layer", "user_metrics_network",
     r"HTTP|\bNET\b|NETWORK|\bTCP\b|HUBBLE|PACKET|\bDROP\b|LATENCY|DURATION|REQUEST"),
    ("container_resource", "user_metrics_cpu_mem",
     r"CPU|MEMORY|\bMEM\b|OOM|FILESYSTEM|\bDISK\b"),
    ("k8s_state", "user_metrics_k8s",
     r"RESTART|\bKILL\b|\bPHASE\b|READY|TERMINAT|EVICT|DEPLOY|\bPOD\b"),
]


def domain_of_literal(lit: str) -> str | None:
    """Return the highest-priority domain matched by one metric literal."""
    lit_up = lit.upper()
    for dom, _tag, pat in DOMAINS:
        if re.search(pat, lit_up):
            return dom
    return None


def extract_metric_literals(where: str) -> list[str]:
    """Return all metric literal strings referenced via metric = 'X' or LIKE '%X%'."""
    lits: list[str] = []
    for m in re.finditer(r"\bMETRIC\s*(?:=|IN|LIKE)\s*(\(|['\"])", where):
        # Simple extract: find quoted literals after match
        pass
    # Simpler: extract any quoted literal appearing right after METRIC op
    for m in re.finditer(r"\bMETRIC\s*(?:=|LIKE)\s*'([^']+)'", where):
        lits.append(m.group(1))
    for m in re.finditer(r"\bMETRIC\s+IN\s*\(([^)]+)\)", where):
        inner = m.group(1)
        for lit in re.findall(r"'([^']+)'", inner):
            lits.append(lit)
    return lits


def classify(sql: str) -> tuple[str | None, str]:
    u = sql.upper()

    # Scope: abnormal_metrics / histogram / sum only (no normal_, no logs, no traces)
    has_ab_metric = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,160}?ABNORMAL_METRICS(?:_HISTOGRAM|_SUM)?\b", u, re.DOTALL))
    has_bare_metric = bool(re.search(r"\b(?:FROM|JOIN)\s+METRICS(?:_HISTOGRAM|_SUM)?\b", u))
    has_nm_metric = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,160}?(?<!AB)NORMAL_METRICS", u, re.DOTALL))
    has_logs = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,160}?(?:AB)?NORMAL_LOGS\b|\b(?:FROM|JOIN)\s+LOGS\b", u, re.DOTALL))
    has_traces = bool(re.search(r"\b(?:FROM|JOIN)\s+[^;]{0,160}?(?:AB)?NORMAL_TRACES\b|\b(?:FROM|JOIN)\s+TRACES\b", u, re.DOTALL))

    if has_nm_metric:
        return None, "normal_metrics (baseline)"
    if has_logs or has_traces:
        return None, "cross-modal"
    if not (has_ab_metric or has_bare_metric):
        return None, "not metrics"

    wm = re.search(r"\bWHERE\b(.*?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|\bUNION\b|\bHAVING\b|$)",
                   u, re.DOTALL)
    where = wm.group(1) if wm else ""

    has_svc = bool(re.search(r"\bSERVICE_NAME\s*(=|IN|!=|<>|LIKE|\bNOT\s+IN\b)", where))

    # Extract metric literals
    metric_lits = extract_metric_literals(where)
    # Also check ATTR_K8S_* (implicit k8s context)
    has_attr_k8s = "ATTR_K8S" in u and not metric_lits
    # hubble / attr_workload
    has_hubble = "HUBBLE" in u or "ATTR_DESTINATION_WORKLOAD" in u or "ATTR_SOURCE_WORKLOAD" in u

    # Check error tagging — if error keyword present, metric_scan (mixed-signal)
    has_error_tag = bool(re.search(r"%ERROR%|%FAIL%|%5XX%|%4XX%", " ".join(metric_lits).upper()))

    # Per-literal domain match (priority within each literal)
    per_lit_doms: list[str | None] = [domain_of_literal(lit) for lit in metric_lits]
    dom_counts = Counter(d for d in per_lit_doms if d is not None)

    # If hubble/attr_workload without metric literal → network_layer
    if not metric_lits and has_hubble:
        return "network_layer", "user_metrics_network_hubble"

    # Error tag in metric literal → metric_scan (mixed-signal)
    if has_error_tag:
        return "metric_scan", "user_metrics_error_tag"

    # Domain by majority voting across literals
    if dom_counts:
        top_two = dom_counts.most_common(2)
        if len(top_two) == 1:
            # Single domain across all literals
            dom = top_two[0][0]
            tag = next(t for d, t, _ in DOMAINS if d == dom)
            return dom, tag
        (top_dom, top_n), (_, second_n) = top_two
        # Strict majority (>50%) wins; tie → metric_scan
        if top_n > second_n and top_n / len(metric_lits) > 0.5:
            tag = next(t for d, t, _ in DOMAINS if d == top_dom)
            return top_dom, tag + "_majority"
        # Tie or no clear majority → mixed → metric_scan
        return "metric_scan", "user_metrics_mixed_domain"

    # No domain match
    # No svc= and no domain → metric_scan (rule 7)
    if not has_svc:
        return "metric_scan", "user_metrics_scan"

    # svc= but no domain → skip (rule 6, user rejected)
    return None, "svc= but no metric domain (manual review)"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    args = p.parse_args()

    eng = create_engine(DB_URL)
    total_pending = 0
    reject_counter: Counter = Counter()
    rule_counter: Counter = Counter()
    intent_counter: Counter = Counter()
    votes_by_rule: dict[str, Counter] = {}
    examples: dict[str, list[dict]] = {}
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
                    norm = normalize_by_agent(agent, traj)
                    rounds = extract_sql_rounds(norm)
                except Exception:
                    continue
                llm = meta.get("llm_intents") or {}

                def vote_at(key, r, si):
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
                        rule_counter[tag] += 1
                        intent_counter[intent] += 1
                        votes = {vk: vote_at(vk, *pos) for vk in VOTE_KEYS}
                        votes_by_rule.setdefault(tag, Counter())
                        for v in votes.values():
                            if v:
                                votes_by_rule[tag][v] += 1
                        examples.setdefault(tag, [])
                        if len(examples[tag]) < 3:
                            examples[tag].append(
                                {"exp": exp, "idx": idx, "pos": pos, "sql": sql, "votes": votes}
                            )
                        staged.append({
                            "exp": exp, "idx": idx, "round": pos[0],
                            "sql_index": pos[1], "intent": intent, "rule": tag,
                        })

    print(f"Total pending scanned: {total_pending}")
    print(f"\nMatches by rule → intent:")
    for tag, n in rule_counter.most_common():
        sample_intent = next((s["intent"] for s in staged if s["rule"] == tag), "?")
        print(f"  {tag:<35} → {sample_intent:<22} {n:>4}")
    print(f"\nAggregated by intent:")
    for i, n in intent_counter.most_common():
        print(f"  {i}: {n}")
    print(f"\nRejection reasons (top 10):")
    for r, n in reject_counter.most_common(10):
        print(f"  {r}: {n}")
    print(f"\nLLM vote distribution per rule:")
    for tag, cnt in votes_by_rule.items():
        top = dict(cnt.most_common(5))
        print(f"  [{tag}]: {top}")
    for tag, exs in examples.items():
        print(f"\n=== Sample [{tag}] (up to 3) ===")
        for i, ex in enumerate(exs, 1):
            print(f"\n--- [{i}] {ex['exp']} case={ex['idx']} r={ex['pos'][0]} si={ex['pos'][1]}")
            print(f"VOTES: {ex['votes']}")
            print(ex["sql"][:350])

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
