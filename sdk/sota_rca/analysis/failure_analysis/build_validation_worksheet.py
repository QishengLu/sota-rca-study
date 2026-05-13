#!/usr/bin/env python
"""Phase 5 — build a single interactive HTML validation worksheet.

Covers the 4 labeled DR agents (372 failed cases total). One HTML file with:
- Agent dropdown (switch between the 4 agents)
- Cases ordered by self_confidence ASC (most risky first; user reads straight through)
- Per-case card with 7 sections:
    0. My claim (primary / pivot_round / proximate_cause)
    1. GT snapshot (from dossier §A)
    2. Trajectory at pivot±3 (from dossier §B excerpt)
    3. Behavioral signature from transitions_per_case.parquet at pivot±3
    4. My 3-block analysis (from per_case_analysis.md)
    5. Taxonomy positive/negative criteria for the claimed theme
    6. Checkboxes + verdict dropdown + optional note
- localStorage auto-save ("validation_v1:<agent>:<dataset_index>")
- Filter: all / low-conf / medium+low / unverified / disagreements
- Export JSONL button (per agent AND combined)
- Keyboard nav: j/k prev/next card, 1=Correct 2=Wrong 3=Ambiguous, ?=help

Output: analysis/3-failure-modes/_cache/validation_worksheet.html

Usage:
    cd RCAgentEval
    uv run python scripts/failure_analysis/build_validation_worksheet.py
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from html import escape
from pathlib import Path

import pandas as pd
from sqlmodel import Session, create_engine, select

REPO_ROOT = Path(__file__).resolve().parents[3]
RCABENCH_ROOT = REPO_ROOT / "RCAgentEval"
sys.path.insert(0, str(RCABENCH_ROOT))

from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = "postgresql://postgres:postgres@localhost:5433/SOTA-Agents"
DEFAULT_PARQUET = REPO_ROOT / "analysis" / "3-failure-modes" / "_cache" / "transitions_per_case.parquet"
DEFAULT_OUT = REPO_ROOT / "analysis" / "3-failure-modes" / "_cache" / "validation_worksheet.html"

AGENTS = {
    "thinkdepthai-qwen3.5-plus": "analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2",
    "thinkdepthai-claude-sonnet-4.6": "analysis/3-failure-modes/2-by-framework/thinkdepthai-claude-sonnet-4.6/v1",
    "aiq-qwen3.5-plus": "analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/v1",
    "claudecode-qwen3.5-plus": "analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1",
}

SHARP_VERBS = {
    "anchored", "locked", "blamed", "ignored", "misread", "reversed", "confabulated",
    "overreached", "mis-ranked", "fixated", "committed", "flipped", "overwrote",
    "hallucinated", "jumped", "conflated", "mislabeled", "over-indexed", "shadowed",
    "dismissed", "over-aggregated", "stopped", "truncated", "drilled", "stuck",
}


# ─── self_confidence heuristic ───────────────────────────────────────────────

def score_confidence(primary: str | None, pivot: int | None, proximate: str, evidence: str) -> tuple[int, list[str]]:
    """Return (score, tags). Higher = more confident. Tiered later."""
    score = 0
    tags: list[str] = []

    if primary == "unclassified" or not primary:
        return -3, ["no_primary"]

    ev = (evidence or "").strip()
    px = (proximate or "").strip()

    if re.search(r"\bround\s*\d+|\br\d+\b|\bturn\s*\d+", ev, flags=re.I):
        score += 2
        tags.append("ev_cites_round")
    if re.search(r"['\"`]([^'\"`\n]{8,})['\"`]", ev):
        score += 2
        tags.append("ev_has_quote")
    if len(ev) >= 120:
        score += 1
        tags.append("ev_long")
    elif len(ev) < 30:
        score -= 1
        tags.append("ev_short")

    px_words = [w.lower().strip(".,;:") for w in px.split()]
    if any(w in SHARP_VERBS for w in px_words):
        score += 1
        tags.append("px_sharp_verb")
    if len(px_words) < 4:
        score -= 1
        tags.append("px_too_short")
    if len(px_words) > 18:
        score -= 1
        tags.append("px_verbose")

    if pivot is not None:
        score += 1
        tags.append("has_pivot")
    else:
        tags.append("no_pivot")

    return score, tags


def tier_of(score: int) -> str:
    """Legacy absolute tiering — kept for fallback only; real tiering is per-agent below."""
    if score <= 1:
        return "low"
    if score <= 3:
        return "medium"
    return "high"


def per_agent_percentile_tier(cases: list[dict]) -> None:
    """Assign conf_tier by within-agent percentile rank of conf_score.

    Bottom 33% of that agent's cases → 'low'
    Middle 34% → 'medium'
    Top 33% → 'high'

    This normalizes across agents with different label-schema history
    (e.g. thinkdepthai-qwen has universally empty evidence field due to
    Phase 4b schema alignment, which otherwise biases the absolute tiering).
    """
    if not cases:
        return
    n = len(cases)
    sorted_idx = sorted(range(n), key=lambda i: cases[i]["conf_score"])
    lo_cutoff = n // 3
    hi_cutoff = 2 * n // 3
    for rank, i in enumerate(sorted_idx):
        if rank < lo_cutoff:
            cases[i]["conf_tier"] = "low"
        elif rank < hi_cutoff:
            cases[i]["conf_tier"] = "medium"
        else:
            cases[i]["conf_tier"] = "high"
        cases[i]["conf_rank"] = rank + 1
        cases[i]["conf_total"] = n


# ─── per_case_analysis.md parser ────────────────────────────────────────────

CASE_HEADER_RE = re.compile(r"^##\s+case[_\s]+(\d+)\b", re.IGNORECASE)


def parse_per_case(md_path: Path) -> dict[int, str]:
    """Return {dataset_index -> full section markdown (including header)}."""
    out: dict[int, str] = {}
    if not md_path.exists():
        return out
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    cur_idx: int | None = None
    cur: list[str] = []
    for line in lines:
        m = CASE_HEADER_RE.match(line)
        if m:
            if cur_idx is not None:
                out[cur_idx] = "\n".join(cur).rstrip()
            cur_idx = int(m.group(1))
            cur = [line]
        else:
            if cur_idx is not None:
                cur.append(line)
    if cur_idx is not None:
        out[cur_idx] = "\n".join(cur).rstrip()
    # Filter out the literal template header `case_<idx>` if present
    out.pop(0, None)
    return out


# ─── dossier excerpt extractor ───────────────────────────────────────────────

def read_dossier(dossier_dir: Path, idx: int) -> str:
    p = dossier_dir / f"case_{idx}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def excerpt_dossier_A(dossier: str) -> str:
    """Pull GT section (§A) from dossier. Falls back to first 2000 chars if §A not found."""
    if not dossier:
        return ""
    m = re.search(r"##\s*Part\s*A[^\n]*\n(.+?)(?=^##\s*Part\s*B|\Z)", dossier, flags=re.S | re.M | re.I)
    if m:
        return m.group(0).strip()[:5000]
    return dossier[:3000]


def excerpt_dossier_B_pivot(dossier: str, pivot: int | None) -> str:
    """Pull trajectory excerpt around pivot. Looks for 'Round N' markers, grabs ±3 rounds."""
    if not dossier:
        return "(no dossier body)"
    # Find §B start
    m = re.search(r"##\s*Part\s*B[^\n]*\n", dossier, flags=re.I)
    body = dossier[m.end():] if m else dossier
    if pivot is None:
        return body[:4000]
    # Each round section is typically delimited by `### Round N` or `**Round N**` or similar
    round_starts = []
    for mm in re.finditer(r"(?m)^#{2,4}\s*Round\s+(\d+)|^\*\*Round\s+(\d+)\*\*", body, flags=re.I):
        rnum = int(mm.group(1) or mm.group(2))
        round_starts.append((rnum, mm.start()))
    if not round_starts:
        return body[:4000]
    # Build index
    round_starts.sort(key=lambda x: x[1])
    first_keep = max(1, pivot - 3)
    last_keep = pivot + 3
    kept_start = None
    kept_end = None
    for rnum, pos in round_starts:
        if rnum >= first_keep and kept_start is None:
            kept_start = pos
        if rnum <= last_keep:
            kept_end = pos  # will extend to end of its section via next round
    if kept_start is None:
        return body[:4000]
    # kept_end extends to NEXT round after last_keep
    end_pos = len(body)
    for rnum, pos in round_starts:
        if rnum > last_keep:
            end_pos = pos
            break
    return body[kept_start:end_pos].strip()[:6000]


# ─── taxonomy.md → theme definition extractor ────────────────────────────────

THEME_HEADER_RE = re.compile(r"^###\s+(T\d+)(?:\s*[—\-:]\s*([^\n]+))?", re.MULTILINE)


def parse_taxonomy(md_path: Path) -> dict[str, str]:
    """Return {T-label -> full theme block (definition + criteria)}."""
    out: dict[str, str] = {}
    if not md_path.exists():
        return out
    text = md_path.read_text(encoding="utf-8")
    matches = list(THEME_HEADER_RE.finditer(text))
    for i, m in enumerate(matches):
        t_label = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # trim at next section that's clearly a separate thematic chunk (## level)
        block = text[start:end].strip()
        # cap size
        out[t_label] = block[:5000]
    return out


def taxonomy_block_for(primary: str, taxonomy: dict[str, str]) -> str:
    """primary like 'T3_Noise-Anchor' -> find T3 block."""
    if not primary:
        return "(no primary)"
    m = re.match(r"(T\d+)", primary)
    if not m:
        return "(primary format unrecognized)"
    t_label = m.group(1)
    return taxonomy.get(t_label, f"(no taxonomy block for {t_label})")


# ─── transitions around pivot (from parquet) ─────────────────────────────────

def transitions_pivot_window(df: pd.DataFrame, exp_id: str, idx: int, pivot: int | None) -> list[dict]:
    sub = df[(df.exp_id == exp_id) & (df.dataset_index == idx)]
    if sub.empty:
        return []
    if pivot is None:
        rows = sub.sort_values("transition_idx").head(15)
    else:
        lo, hi = pivot - 3, pivot + 3
        rows = sub[(sub.round_from >= lo - 1) & (sub.round_to <= hi + 1)].sort_values("transition_idx")
        if rows.empty:
            rows = sub.sort_values("transition_idx").head(10)
    return rows.to_dict("records")


# ─── build case payload ──────────────────────────────────────────────────────

def build_agent_payload(
    session: Session,
    agent: str,
    workspace: Path,
    transitions_df: pd.DataFrame,
) -> list[dict]:
    per_case = parse_per_case(workspace / "per_case_analysis.md")
    taxonomy = parse_taxonomy(workspace / "taxonomy.md")
    dossier_dir = workspace / "dossiers"

    stmt = (
        select(EvaluationSample)
        .where(
            EvaluationSample.exp_id == agent,
            EvaluationSample.stage == "judged",
            EvaluationSample.correct == False,  # noqa: E712
        )
    )
    samples = session.exec(stmt).all()
    logger.info("  %s: %d failed cases", agent, len(samples))

    cases: list[dict] = []
    missing_per_case = 0
    missing_v1 = 0
    for sample in samples:
        meta = sample.meta or {}
        v1 = (meta.get("failure_analysis") or {}).get("v1") or {}
        if not v1.get("primary"):
            missing_v1 += 1
            continue

        idx = sample.dataset_index
        primary = v1.get("primary")
        secondary = v1.get("secondary") or []
        pivot = v1.get("pivot_round")
        proximate = v1.get("proximate_cause") or ""
        evidence = v1.get("evidence") or ""
        labeler = v1.get("labeler") or ""

        score, tags = score_confidence(primary, pivot, proximate, evidence)
        tier = tier_of(score)

        dossier = read_dossier(dossier_dir, idx)
        if not dossier:
            dossier_A = "(dossier file not found)"
            dossier_B = ""
        else:
            dossier_A = excerpt_dossier_A(dossier)
            dossier_B = excerpt_dossier_B_pivot(dossier, pivot)

        per_case_text = per_case.get(idx)
        if not per_case_text:
            missing_per_case += 1
            per_case_text = (
                "(This case was fast-pass labeled — no long-form 3-block analysis written.\n"
                "The label (primary / pivot_round / proximate_cause) is still in §0 above.\n"
                "Validate by directly comparing §1 GT + §2 Trajectory + §3 Transitions against §5 Taxonomy criteria.)"
            )

        tax_block = taxonomy_block_for(primary, taxonomy)
        trans_rows = transitions_pivot_window(transitions_df, agent, idx, pivot)

        difficulty = (meta.get("difficulty") or {})
        cases.append({
            "agent": agent,
            "dataset_index": idx,
            "primary": primary,
            "secondary": secondary,
            "pivot_round": pivot,
            "proximate_cause": proximate,
            "evidence": evidence,
            "labeler": labeler,
            "conf_score": score,
            "conf_tier": tier,
            "conf_tags": tags,
            "fault_type": difficulty.get("fault_type"),
            "fault_category": difficulty.get("fault_category"),
            "root_cause_service": difficulty.get("root_cause_service") or (meta.get("ground_truth") or [None])[0],
            "spl": difficulty.get("spl"),
            "n_svc": difficulty.get("n_svc"),
            "n_edge": difficulty.get("n_edge"),
            "datapack_name": meta.get("datapack_name"),
            "dossier_A": dossier_A,
            "dossier_B_pivot": dossier_B,
            "transitions": trans_rows,
            "per_case_analysis": per_case_text,
            "taxonomy_block": tax_block,
        })
    logger.info("  %s: payload %d cases  (missing_v1=%d missing_per_case=%d)",
                agent, len(cases), missing_v1, missing_per_case)

    # Re-tier per-agent (percentile within this agent's cases)
    per_agent_percentile_tier(cases)
    # Sort by conf_score ASC, then dataset_index ASC — within-agent worst-first
    cases.sort(key=lambda c: (c["conf_score"], c["dataset_index"]))
    return cases


# ─── HTML rendering ──────────────────────────────────────────────────────────

HTML_HEAD = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Failure-mode validation worksheet</title>
<style>
  :root { --bg:#fafbfc; --fg:#0b1221; --card:#fff; --border:#d0d7de; --muted:#656d76;
          --low:#d1242f; --mid:#bf8700; --high:#1a7f37; --accent:#0969da;
          --pivot:#fff8c5; --correct:#dafbe1; --wrong:#ffebe9; --ambig:#fff1e5; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
         background: var(--bg); color: var(--fg); margin: 0; padding: 0; font-size: 14px; }
  header { position: sticky; top: 0; background: var(--card); border-bottom: 1px solid var(--border);
           padding: 10px 18px; z-index: 100; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
  header label { font-size: 12px; color: var(--muted); }
  header select, header input { padding: 4px 8px; border: 1px solid var(--border); border-radius: 5px; }
  header button { padding: 5px 12px; border: 1px solid var(--border); border-radius: 5px;
                  background: var(--card); cursor: pointer; font-weight: 600; }
  header button:hover { background: #f1f3f5; }
  #save-status { font-size: 12px; padding: 3px 10px; border-radius: 4px; }
  #save-status.idle { background: #eef2f5; color: var(--muted); }
  #save-status.ok { background: #dcfce7; color: #166534; }
  #save-status.saving { background: #fef3c7; color: #854d0e; }
  #save-status.err { background: #ffe4e6; color: #9f1239; }
  #progress { flex: 1; display: flex; align-items: center; gap: 8px; justify-content: flex-end; }
  #progress-bar { width: 160px; height: 8px; background: #eee; border-radius: 4px; overflow: hidden; }
  #progress-fill { height: 100%; background: var(--high); transition: width 0.2s; }
  main { max-width: 1100px; margin: 0 auto; padding: 18px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 8px;
          margin-bottom: 18px; padding: 14px 18px; }
  .card.low { border-left: 4px solid var(--low); }
  .card.medium { border-left: 4px solid var(--mid); }
  .card.high { border-left: 4px solid var(--high); }
  .card.verdict-Correct { background: var(--correct); }
  .card.verdict-Wrong { background: var(--wrong); }
  .card.verdict-Ambiguous { background: var(--ambig); }
  .card h2 { margin: 0 0 4px; font-size: 16px; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px;
          background: #eef2f5; color: var(--muted); margin-right: 6px; }
  .pill.low { background: #ffe4e6; color: #9f1239; }
  .pill.medium { background: #fef3c7; color: #854d0e; }
  .pill.high { background: #dcfce7; color: #166534; }
  .pill.disagree { background: #fde68a; color: #92400e; }
  .section { margin-top: 12px; padding: 10px 12px; background: #f7f9fc; border-radius: 6px; }
  .section h3 { margin: 0 0 6px; font-size: 13px; color: var(--muted); text-transform: uppercase;
                letter-spacing: 0.03em; font-weight: 600; }
  .section.claim { background: #eef6ff; }
  .section.gt { background: #f0f9ee; }
  .section.traj { background: #fff7ed; }
  .section.trans { background: #f8f4ff; }
  .section.myanalysis { background: #f7f9fc; }
  .section.taxonomy { background: #fff0f6; }
  .section.verdict { background: #f4f4f5; border: 1px dashed var(--border); }
  pre { white-space: pre-wrap; word-wrap: break-word; font-family: ui-monospace, Menlo, monospace;
        font-size: 12px; margin: 0; line-height: 1.45; }
  table.trans { border-collapse: collapse; font-family: ui-monospace, Menlo, monospace; font-size: 12px; }
  table.trans th, table.trans td { border: 1px solid var(--border); padding: 3px 8px; text-align: left; }
  table.trans tr.pivot { background: var(--pivot); font-weight: 600; }
  .checks label { display: block; margin: 4px 0; font-size: 13px; cursor: pointer; }
  .checks input { margin-right: 6px; }
  .verdict-row { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; margin-top: 10px; }
  .verdict-row select { padding: 5px 10px; border: 1px solid var(--border); border-radius: 5px; font-size: 13px; }
  .verdict-row textarea { flex: 1; min-width: 300px; padding: 6px 10px; border: 1px solid var(--border);
                          border-radius: 5px; font-size: 12px; font-family: inherit; resize: vertical; min-height: 28px; }
  details summary { cursor: pointer; color: var(--accent); font-size: 12px; padding: 2px 0; }
  #help-modal { position: fixed; top: 10%; left: 50%; transform: translateX(-50%); background: var(--card);
                border: 1px solid var(--border); border-radius: 8px; padding: 20px 28px; max-width: 520px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.1); z-index: 200; display: none; }
  #help-modal.show { display: block; }
  kbd { background: #eee; padding: 1px 6px; border-radius: 3px; font-family: ui-monospace, Menlo, monospace;
        font-size: 11px; border: 1px solid var(--border); }
  .muted { color: var(--muted); font-size: 12px; }
  .badge-tier { font-weight: 600; font-size: 11px; padding: 2px 6px; border-radius: 4px; }
  .badge-tier.low { background: var(--low); color: white; }
  .badge-tier.medium { background: var(--mid); color: white; }
  .badge-tier.high { background: var(--high); color: white; }
  .disagree-badge { background: #fde68a; color: #92400e; padding: 2px 6px; border-radius: 4px; font-weight: 600; }
</style>
</head>
<body>
<header>
  <strong>Validation worksheet</strong>
  <label>Agent: <select id="agent-select"></select></label>
  <label>Filter:
    <select id="filter-select">
      <option value="all">All</option>
      <option value="unverified">Unverified only</option>
      <option value="low">Low-conf only</option>
      <option value="lowmed">Low + Medium</option>
      <option value="disagreements">Disagreements only</option>
      <option value="marked-wrong">Marked Wrong</option>
    </select>
  </label>
  <button id="export-btn">Export JSONL</button>
  <button id="help-btn">?</button>
  <span id="save-status" class="idle" title="Autosave status — saves to disk via local server">server: checking…</span>
  <div id="progress">
    <span id="progress-text" class="muted">0 / 0</span>
    <div id="progress-bar"><div id="progress-fill" style="width:0%"></div></div>
  </div>
</header>
<main id="cards"></main>
<div id="help-modal">
  <h3>Keyboard shortcuts</h3>
  <p><kbd>j</kbd> / <kbd>k</kbd> — next / prev card &nbsp;|&nbsp;
     <kbd>1</kbd> — mark Correct &nbsp;
     <kbd>2</kbd> — Wrong &nbsp;
     <kbd>3</kbd> — Ambiguous &nbsp;
     <kbd>0</kbd> — clear verdict</p>
  <p><kbd>e</kbd> — expand/collapse current card &nbsp;|&nbsp;
     <kbd>Esc</kbd> / <kbd>?</kbd> — close help</p>
  <p class="muted">Verdicts persist in browser localStorage (key: <code>validation_v1:&lt;agent&gt;:&lt;idx&gt;</code>).
     Export writes one JSONL per loaded agent to your Downloads folder.</p>
  <p class="muted">Disagreement flag 🚩 appears when a case is listed in the agent's
     <code>adversarial_disagreement.md</code>. Import that list by dropping the file on this page.</p>
  <button onclick="document.getElementById('help-modal').classList.remove('show')">close</button>
</div>
<script>
const DATA = __DATA__;
const STORAGE_VERSION = "v1";
function storageKey(agent, idx) { return `validation_${STORAGE_VERSION}:${agent}:${idx}`; }

let currentAgent = Object.keys(DATA)[0];
let currentFilter = "all";
let focusedCardIdx = null;
// Server-side state cache: {agent: {idx: record}}
const SERVER_STATE = {};
for (const a of Object.keys(DATA)) SERVER_STATE[a] = {};
let SERVER_ONLINE = false;

function setSaveStatus(kind, text) {
  const el = document.getElementById('save-status');
  if (!el) return;
  el.className = kind;
  el.textContent = text;
}

// ── server sync ─────────────────────────────────────────────────────────────
async function hydrateFromServer() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) throw new Error('health ' + res.status);
    SERVER_ONLINE = true;
    setSaveStatus('ok', 'server: connected (autosaving)');
    // Pull verdicts for all agents
    for (const agent of Object.keys(DATA)) {
      try {
        const r = await fetch(`/api/verdicts?agent=${encodeURIComponent(agent)}`);
        if (!r.ok) continue;
        const map = await r.json();
        for (const [idx, rec] of Object.entries(map)) {
          SERVER_STATE[agent][idx] = rec;
          // mirror into localStorage so stateLoad() works without extra branching
          localStorage.setItem(storageKey(agent, parseInt(idx)), JSON.stringify(rec));
        }
      } catch (e) { /* ignore one-agent failures */ }
    }
  } catch (e) {
    SERVER_ONLINE = false;
    setSaveStatus('err', 'server: OFFLINE (localStorage-only; run validation_server.py)');
  }
}

async function postVerdict(agent, idx) {
  if (!SERVER_ONLINE) return; // silently no-op
  const rec = loadState(agent, idx);
  rec.dataset_index = idx;
  rec.agent = agent;
  // attach identifying metadata for easy grepping server-side
  const list = DATA[agent] || [];
  const c = list.find(x => x.dataset_index === idx);
  if (c) {
    rec.primary = c.primary;
    rec.conf_tier = c.conf_tier;
  }
  setSaveStatus('saving', 'server: saving…');
  try {
    const r = await fetch('/api/verdict', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(rec),
    });
    if (!r.ok) throw new Error('POST ' + r.status);
    setSaveStatus('ok', 'server: saved');
  } catch (e) {
    setSaveStatus('err', 'server: save failed (kept in localStorage)');
  }
}

function loadState(agent, idx) {
  try { return JSON.parse(localStorage.getItem(storageKey(agent, idx))) || {}; }
  catch(e) { return {}; }
}
function saveState(agent, idx, state) {
  localStorage.setItem(storageKey(agent, idx), JSON.stringify(state));
  updateProgress();
  // fire-and-forget server sync
  postVerdict(agent, idx);
}

function renderTransitions(trans, pivot) {
  if (!trans || trans.length === 0) return '<div class="muted">(no transitions)</div>';
  let html = '<table class="trans"><thead><tr>' +
    '<th>r_from</th><th>r_to</th><th>label</th><th>rt</th>' +
    '<th>prev_svc_on_gt</th><th>next_svc_on_gt</th><th>dist</th></tr></thead><tbody>';
  for (const t of trans) {
    const isPivot = pivot != null && (t.round_from === pivot || t.round_to === pivot);
    const dist = (t.prev_dist ?? '-') + '→' + (t.next_dist ?? '-');
    html += `<tr class="${isPivot ? 'pivot' : ''}">` +
      `<td>${t.round_from}</td><td>${t.round_to}</td>` +
      `<td>${t.label}</td><td>${t.rt_utilization}</td>` +
      `<td>${t.prev_services_on_gt || '·'}</td>` +
      `<td>${t.next_services_on_gt || '·'}</td>` +
      `<td>${dist}</td></tr>`;
  }
  html += '</tbody></table>';
  return html;
}

function caseCard(c, idxInList) {
  const state = loadState(c.agent, c.dataset_index);
  const verdictCls = state.verdict ? `verdict-${state.verdict}` : '';
  const disagreeBadge = c.disagreement_primary
    ? `<span class="disagree-badge" title="Adversarial LLM picked: ${c.disagreement_primary}">🚩 disagree</span>` : '';
  const sec = (cls, title, bodyHtml) =>
    `<div class="section ${cls}"><h3>${title}</h3>${bodyHtml}</div>`;
  const pre = (text) => `<pre>${escapeHtml(text || '')}</pre>`;

  return `<div class="card ${c.conf_tier} ${verdictCls}" id="card-${idxInList}" data-idx="${idxInList}">
    <h2>case_${c.dataset_index}
      <span class="badge-tier ${c.conf_tier}">${c.conf_tier.toUpperCase()} conf · rank ${c.conf_rank}/${c.conf_total}</span>
      ${disagreeBadge}
    </h2>
    <div class="muted">
      ${c.fault_category || '?'} / ${c.fault_type || '?'} &nbsp;•&nbsp;
      spl=${c.spl ?? '?'} n_svc=${c.n_svc ?? '?'} n_edge=${c.n_edge ?? '?'} &nbsp;•&nbsp;
      GT root: ${c.root_cause_service || '?'} &nbsp;•&nbsp;
      <span class="muted">tags: ${(c.conf_tags||[]).join(', ')}</span>
    </div>

    ${sec('claim', '0. MY CLAIM (5 sec)', `
      <div><b>primary:</b> ${c.primary}</div>
      <div><b>pivot_round:</b> ${c.pivot_round ?? '(none)'}</div>
      <div><b>proximate_cause:</b> <i>${escapeHtml(c.proximate_cause)}</i></div>
      ${c.evidence ? `<details><summary>evidence snippet</summary>${pre(c.evidence)}</details>` : ''}
    `)}

    ${sec('gt', '1. GT FACTS (30 sec) — read BEFORE my analysis', pre(c.dossier_A))}

    ${sec('traj', '2. TRAJECTORY at pivot±3 (60 sec)', pre(c.dossier_B_pivot))}

    ${sec('trans', '3. BEHAVIORAL SIGNATURE at pivot±3 (transition labels)',
      renderTransitions(c.transitions, c.pivot_round))}

    ${sec('myanalysis', '4. MY 3-BLOCK ANALYSIS (compare to 1/2/3)', pre(c.per_case_analysis))}

    ${sec('taxonomy', '5. TAXONOMY criteria for ' + c.primary, pre(c.taxonomy_block))}

    <div class="section verdict">
      <h3>6. VERDICT (your call)</h3>
      <div class="checks">
        ${checkboxRow(c.agent, c.dataset_index, state, 'gt_match', '(1) GT matches my §1 "what really happened"?')}
        ${checkboxRow(c.agent, c.dataset_index, state, 'traj_match', '(2) Trajectory matches my §2 "what agent did"?')}
        ${checkboxRow(c.agent, c.dataset_index, state, 'pivot_match', 'pivot_round is accurate (±1 ok)?')}
        ${checkboxRow(c.agent, c.dataset_index, state, 'theme_match', 'primary fits (5) positive criteria, avoids negatives?')}
        ${checkboxRow(c.agent, c.dataset_index, state, 'px_specific', 'proximate_cause is specific (not "failed/wrong")?')}
      </div>
      <div class="verdict-row">
        <select onchange="setVerdict('${c.agent}', ${c.dataset_index}, this.value, ${idxInList})">
          <option value="" ${!state.verdict ? 'selected' : ''}>— verdict —</option>
          <option value="Correct" ${state.verdict === 'Correct' ? 'selected' : ''}>✓ Correct</option>
          <option value="Wrong" ${state.verdict === 'Wrong' ? 'selected' : ''}>✗ Wrong</option>
          <option value="Ambiguous" ${state.verdict === 'Ambiguous' ? 'selected' : ''}>? Ambiguous</option>
        </select>
        <textarea placeholder="optional note (why wrong? suggested primary?)"
                  oninput="setNote('${c.agent}', ${c.dataset_index}, this.value)">${escapeHtml(state.note || '')}</textarea>
      </div>
    </div>
  </div>`;
}

function checkboxRow(agent, idx, state, key, label) {
  const checked = state.checks && state.checks[key] ? 'checked' : '';
  return `<label><input type="checkbox" ${checked}
    onchange="toggleCheck('${agent}', ${idx}, '${key}', this.checked)"> ${label}</label>`;
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function toggleCheck(agent, idx, key, val) {
  const st = loadState(agent, idx);
  if (!st.checks) st.checks = {};
  st.checks[key] = val;
  st.ts = Date.now();
  saveState(agent, idx, st);
}
function setVerdict(agent, idx, verdict, idxInList) {
  const st = loadState(agent, idx);
  st.verdict = verdict || null;
  st.ts = Date.now();
  saveState(agent, idx, st);
  const card = document.getElementById('card-' + idxInList);
  card.classList.remove('verdict-Correct', 'verdict-Wrong', 'verdict-Ambiguous');
  if (verdict) card.classList.add('verdict-' + verdict);
  if (currentFilter !== 'all') render();
}
function setNote(agent, idx, note) {
  const st = loadState(agent, idx);
  st.note = note;
  st.ts = Date.now();
  saveState(agent, idx, st);
}

function filterCase(c) {
  const st = loadState(c.agent, c.dataset_index);
  switch (currentFilter) {
    case 'all': return true;
    case 'unverified': return !st.verdict;
    case 'low': return c.conf_tier === 'low';
    case 'lowmed': return c.conf_tier !== 'high';
    case 'disagreements': return !!c.disagreement_primary;
    case 'marked-wrong': return st.verdict === 'Wrong';
  }
  return true;
}

function render() {
  const list = DATA[currentAgent] || [];
  const visible = list.filter(filterCase);
  const main = document.getElementById('cards');
  main.innerHTML = visible.map((c, i) => caseCard(c, i)).join('');
  updateProgress();
}

function updateProgress() {
  const list = DATA[currentAgent] || [];
  const done = list.filter(c => {
    const st = loadState(c.agent, c.dataset_index);
    return !!st.verdict;
  }).length;
  document.getElementById('progress-text').textContent = `${done} / ${list.length}`;
  const pct = list.length ? (done / list.length * 100) : 0;
  document.getElementById('progress-fill').style.width = pct + '%';
}

function exportJsonl() {
  const list = DATA[currentAgent] || [];
  const lines = [];
  for (const c of list) {
    const st = loadState(c.agent, c.dataset_index);
    if (!st.verdict && !st.note && !(st.checks && Object.keys(st.checks).length)) continue;
    lines.push(JSON.stringify({
      agent: c.agent,
      dataset_index: c.dataset_index,
      primary: c.primary,
      conf_tier: c.conf_tier,
      verdict: st.verdict || null,
      note: st.note || "",
      checks: st.checks || {},
      ts: st.ts || null,
      adversarial_primary: c.disagreement_primary || null
    }));
  }
  if (!lines.length) {
    alert('No verdicts recorded for ' + currentAgent); return;
  }
  const blob = new Blob([lines.join('\\n') + '\\n'], { type: 'application/jsonl' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `spot_check_${currentAgent}.jsonl`;
  document.body.appendChild(a); a.click(); a.remove();
}

// ── agent dropdown setup
const sel = document.getElementById('agent-select');
for (const a of Object.keys(DATA)) {
  const opt = document.createElement('option');
  opt.value = a; opt.textContent = `${a}  (${DATA[a].length} cases)`;
  sel.appendChild(opt);
}
sel.value = currentAgent;
sel.onchange = () => { currentAgent = sel.value; render(); };
document.getElementById('filter-select').onchange = (e) => { currentFilter = e.target.value; render(); };
document.getElementById('export-btn').onclick = exportJsonl;
document.getElementById('help-btn').onclick = () => document.getElementById('help-modal').classList.toggle('show');

// ── keyboard nav
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
  const cards = document.querySelectorAll('.card');
  if (e.key === 'Escape' || e.key === '?') {
    document.getElementById('help-modal').classList.toggle('show'); return;
  }
  if (!cards.length) return;
  if (focusedCardIdx === null) focusedCardIdx = 0;
  if (e.key === 'j') { focusedCardIdx = Math.min(focusedCardIdx + 1, cards.length - 1); scrollTo(cards[focusedCardIdx]); }
  else if (e.key === 'k') { focusedCardIdx = Math.max(focusedCardIdx - 1, 0); scrollTo(cards[focusedCardIdx]); }
  else if (e.key === '1' || e.key === '2' || e.key === '3' || e.key === '0') {
    const card = cards[focusedCardIdx];
    if (!card) return;
    const verdictMap = { '1': 'Correct', '2': 'Wrong', '3': 'Ambiguous', '0': '' };
    const verdict = verdictMap[e.key];
    const selectEl = card.querySelector('.verdict-row select');
    selectEl.value = verdict;
    selectEl.dispatchEvent(new Event('change'));
  }
});
function scrollTo(el) { el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  el.style.outline = '2px solid var(--accent)'; setTimeout(() => el.style.outline = '', 800); }

// Hydrate from server BEFORE first render so existing verdicts paint correctly
(async () => {
  await hydrateFromServer();
  render();
})();
</script>
</body>
</html>
"""


def render_html(payload: dict[str, list[dict]], out_path: Path) -> None:
    # Try to load adversarial disagreements if present, to set disagreement_primary field
    for agent, cases in payload.items():
        ws = REPO_ROOT / AGENTS[agent]
        dis_file = ws / "adversarial_disagreement.md"
        if dis_file.exists():
            text = dis_file.read_text(encoding="utf-8")
            # format: lines like `case_<idx>: mine=<T> vs adv=<T> ...`
            for m in re.finditer(r"case_(\d+).*?adv\s*=\s*(T\d+[_A-Za-z\-]*)", text):
                idx = int(m.group(1))
                adv_t = m.group(2)
                for c in cases:
                    if c["dataset_index"] == idx:
                        c["disagreement_primary"] = adv_t
                        break

    data_json = json.dumps(payload, ensure_ascii=False, default=str)
    html = HTML_HEAD.replace("__DATA__", data_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    size_mb = out_path.stat().st_size / 1024 / 1024
    logger.info("wrote %s (%.2f MB)", out_path, size_mb)


# ─── main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=DEFAULT_DB_URL)
    parser.add_argument("--parquet", type=Path, default=DEFAULT_PARQUET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    assert args.parquet.exists(), f"transitions parquet not found: {args.parquet}"
    transitions_df = pd.read_parquet(args.parquet)
    logger.info("loaded transitions parquet (%d rows)", len(transitions_df))

    engine = create_engine(args.db)
    payload: dict[str, list[dict]] = {}
    with Session(engine) as session:
        for agent, rel_ws in AGENTS.items():
            ws = REPO_ROOT / rel_ws
            payload[agent] = build_agent_payload(session, agent, ws, transitions_df)

    total = sum(len(v) for v in payload.values())
    logger.info("total cases embedded: %d", total)

    render_html(payload, args.output)
    logger.info("next: open file://%s in a browser", args.output.resolve())


if __name__ == "__main__":
    main()
