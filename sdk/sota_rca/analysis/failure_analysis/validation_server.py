#!/usr/bin/env python
"""Phase 5 — tiny local server that persists validation verdicts to disk.

Serves:
  GET  /                         validation_worksheet.html
  GET  /api/verdicts?agent=<id>  returns {dataset_index: record} for that agent
  POST /api/verdict              body {agent, dataset_index, verdict, checks, note}
                                 upserts that case's record; rewrites the agent's
                                 `<workspace>/spot_check.jsonl` atomically
  GET  /api/stats                summary counts across all 4 agents

Storage: one JSONL file per labeled agent at
  analysis/3-failure-modes/2-by-framework/<agent>/<v>/spot_check.jsonl
Each line = one complete JSON record for one dataset_index (latest-wins).

Usage:
  cd RCAgentEval
  uv run python scripts/failure_analysis/validation_server.py
  # then open http://localhost:8790 in a browser
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[3]

AGENT_WORKSPACES = {
    "thinkdepthai-qwen3.5-plus": REPO_ROOT / "analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2",
    "thinkdepthai-claude-sonnet-4.6": REPO_ROOT / "analysis/3-failure-modes/2-by-framework/thinkdepthai-claude-sonnet-4.6/v1",
    "aiq-qwen3.5-plus": REPO_ROOT / "analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/v1",
    "claudecode-qwen3.5-plus": REPO_ROOT / "analysis/3-failure-modes/2-by-framework/claudecode-qwen3.5-plus/v1",
}
HTML_PATH = REPO_ROOT / "analysis/3-failure-modes/_cache/validation_worksheet.html"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ── in-memory state, loaded from disk at startup ─────────────────────────────

class Store:
    """Per-agent map of dataset_index -> record. Thread-safe upsert+flush."""

    def __init__(self):
        self._state: dict[str, dict[int, dict]] = {a: {} for a in AGENT_WORKSPACES}
        self._locks: dict[str, Lock] = {a: Lock() for a in AGENT_WORKSPACES}
        self._load_all()

    def _file(self, agent: str) -> Path:
        ws = AGENT_WORKSPACES[agent]
        return ws / "spot_check.jsonl"

    def _load_all(self) -> None:
        for agent, ws in AGENT_WORKSPACES.items():
            p = self._file(agent)
            if not p.exists():
                continue
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    rec = json.loads(line)
                    idx = int(rec["dataset_index"])
                    self._state[agent][idx] = rec
                except (json.JSONDecodeError, KeyError, ValueError) as exc:
                    logger.warning("skipped malformed line in %s: %s", p, exc)
            logger.info("%s: loaded %d existing verdicts from %s",
                        agent, len(self._state[agent]), p)

    def get(self, agent: str) -> dict[int, dict]:
        return self._state.get(agent, {})

    def upsert(self, agent: str, record: dict) -> dict:
        if agent not in self._state:
            raise ValueError(f"unknown agent: {agent}")
        idx = int(record["dataset_index"])
        record["agent"] = agent
        record["ts"] = int(time.time())
        with self._locks[agent]:
            self._state[agent][idx] = record
            self._flush(agent)
        return record

    def _flush(self, agent: str) -> None:
        """Atomic write-out of the agent's JSONL file."""
        path = self._file(agent)
        path.parent.mkdir(parents=True, exist_ok=True)
        records = sorted(self._state[agent].values(), key=lambda r: int(r["dataset_index"]))
        body = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
        with NamedTemporaryFile(
            "w", encoding="utf-8",
            delete=False,
            dir=str(path.parent),
            prefix=".tmp_spot_check_",
            suffix=".jsonl",
        ) as tmp:
            tmp.write(body + ("\n" if body else ""))
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, path)

    def stats(self) -> dict[str, dict]:
        out = {}
        for agent, cases in self._state.items():
            verdicts = [r.get("verdict") for r in cases.values() if r.get("verdict")]
            out[agent] = {
                "total_with_record": len(cases),
                "verified": len(verdicts),
                "correct": verdicts.count("Correct"),
                "wrong": verdicts.count("Wrong"),
                "ambiguous": verdicts.count("Ambiguous"),
                "file": str(self._file(agent).relative_to(REPO_ROOT)),
            }
        return out


# ── FastAPI app ──────────────────────────────────────────────────────────────

class VerdictBody(BaseModel):
    agent: str
    dataset_index: int
    verdict: Optional[str] = None
    checks: Optional[dict] = None
    note: Optional[str] = None
    primary: Optional[str] = None
    conf_tier: Optional[str] = None


app = FastAPI(title="validation-worksheet-server")
store = Store()


@app.get("/")
def index():
    if not HTML_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{HTML_PATH} not found. Run build_validation_worksheet.py first.",
        )
    return FileResponse(
        HTML_PATH,
        media_type="text/html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/api/verdicts")
def get_verdicts(agent: str):
    if agent not in AGENT_WORKSPACES:
        raise HTTPException(404, f"unknown agent: {agent}")
    # Return {dataset_index: record}
    out = {str(idx): rec for idx, rec in store.get(agent).items()}
    return JSONResponse(out)


@app.post("/api/verdict")
async def post_verdict(body: VerdictBody, request: Request):
    if body.agent not in AGENT_WORKSPACES:
        raise HTTPException(404, f"unknown agent: {body.agent}")
    record = body.model_dump(exclude_none=False)
    saved = store.upsert(body.agent, record)
    # Log terse line so user sees progress in terminal
    vstr = saved.get("verdict") or "-"
    logger.info("SAVED  %s  case_%-5s  verdict=%s", body.agent, body.dataset_index, vstr)
    return {"ok": True, "ts": saved["ts"]}


@app.get("/api/stats")
def get_stats():
    return store.stats()


@app.get("/api/health")
def health():
    return {"ok": True, "agents": list(AGENT_WORKSPACES)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 5 validation-worksheet server")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    import uvicorn
    logger.info("serving http://%s:%d  (open in browser)", args.host, args.port)
    logger.info("HTML: %s", HTML_PATH)
    logger.info("Per-agent spot_check.jsonl files:")
    for agent, ws in AGENT_WORKSPACES.items():
        p = ws / "spot_check.jsonl"
        logger.info("  %s -> %s", agent, p)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
