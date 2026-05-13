#!/usr/bin/env python
"""Phase 1 — Dossier builder for failure-mode analysis (no interpretation).

Per failed case, produces:
  1. case_<idx>.md  — readable dossier (Part A: GT reality + Part B: agent trajectory)
  2. case_<idx>.raw.json — full raw trajectory for drill-down

The builder never interprets. It only reads and formats.

Usage:
    cd RCAgentEval
    uv run python scripts/failure_analysis/build_dossiers.py \\
        --db postgresql://postgres:postgres@localhost:5433/SOTA-Agents \\
        --exp_id thinkdepthai-qwen3.5-plus \\
        --out_dir analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers

    # Smoke test with 3 cases
    uv run python scripts/failure_analysis/build_dossiers.py \\
        --db postgresql://postgres:postgres@localhost:5433/SOTA-Agents \\
        --exp_id thinkdepthai-qwen3.5-plus \\
        --out_dir /tmp/dossier-test --limit 3
"""

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from sqlmodel import Session, create_engine, select

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sota_rca.runner._fallback_db import EvaluationSample  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────

INTENT_MODEL_KEY = "claude_opus_4_6"

STAGE_BY_INTENT = {
    "latency_ranking": "T", "throughput_compare": "T", "error_rate_scan": "T",
    "error_log_overview": "T", "metric_scan": "T",
    "service_trace_scan": "V", "trace_follow": "V", "call_tree_build": "V",
    "service_error_log": "L", "service_log_browse": "L", "keyword_search": "L",
    "error_timeline": "L",
    "container_resource": "M", "jvm_state": "M", "network_layer": "M",
    "k8s_state": "M", "db_state": "M",
    "baseline_collect": "B", "baseline_contrast": "B",
}

SERVICE_RE = re.compile(r"ts-[a-z0-9\-]+")
ERROR_RE = re.compile(r"\b(5\d\d|error|refused|timeout|exception|connection reset|upstream connect|OOM|OutOfMemory|killed|restarting|CrashLoopBackOff)\b", re.IGNORECASE)
HYP_PATTERNS = [
    re.compile(r"root cause[^\n]{0,40}?(?:is|=|:)[^\n]{0,20}?(ts-[a-z0-9\-]+)", re.IGNORECASE),
    re.compile(r"(ts-[a-z0-9\-]+)\s+is\s+the\s+(?:root cause|origin|culprit)", re.IGNORECASE),
    re.compile(r"conclude[^\n]{0,30}?(ts-[a-z0-9\-]+)", re.IGNORECASE),
    re.compile(r"identified\s+(ts-[a-z0-9\-]+)\s+as", re.IGNORECASE),
]
SEVERE_LEVELS = {"ERROR", "SEVERE", "FATAL", "CRITICAL"}

TOOL_RESULT_DISPLAY_LIMIT = 2000  # chars in markdown per tool result


# ── Generic loaders ─────────────────────────────────────────────────────────


def find_source_dir(meta: dict) -> Path | None:
    src = meta.get("source_data_dir")
    if not src:
        return None
    p = Path(src)
    return p if p.exists() else None


def load_json_safe(path: Path) -> dict | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("load_json_safe %s: %s", path, exc)
        return None


def load_parquet_safe(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception as exc:  # noqa: BLE001
        logger.debug("load_parquet_safe %s: %s", path, exc)
        return None


def _as_float(v: Any) -> float | None:
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def _as_float_ms(v: Any) -> float | None:
    f = _as_float(v)
    return round(f * 1000.0, 2) if f is not None else None


# ── Part A loaders: GT data ─────────────────────────────────────────────────


def load_injection_full(src_dir: Path) -> dict:
    """Load injection from both converted dir and parent. Return merged human-readable spec."""
    result: dict[str, Any] = {}
    # Parent dir has richer format (display_config, ground_truth with function/metric)
    parent_inj = load_json_safe(src_dir.parent / "injection.json") if src_dir else None
    conv_inj = load_json_safe(src_dir / "injection.json") if src_dir else None
    inj = parent_inj or conv_inj
    if not inj:
        return {}
    result["fault_type_raw"] = inj.get("fault_type")
    result["start_time"] = inj.get("start_time")
    result["end_time"] = inj.get("end_time")
    result["pre_duration"] = inj.get("pre_duration")
    result["injection_name"] = inj.get("injection_name") or inj.get("name")
    # display_config — human-readable injection params (parent format)
    dc = inj.get("display_config")
    if isinstance(dc, str):
        try:
            dc = json.loads(dc)
        except json.JSONDecodeError:
            pass
    result["display_config"] = dc if isinstance(dc, dict) else None
    # ground_truth with function / metric (parent format)
    gt = inj.get("ground_truth")
    if isinstance(gt, dict):
        result["gt_services"] = gt.get("service") or []
        result["gt_pods"] = gt.get("pod") or []
        result["gt_containers"] = gt.get("container") or []
        result["gt_functions"] = gt.get("function") or []
        result["gt_metrics"] = gt.get("metric") or []
        result["gt_spans"] = gt.get("span") or []
    elif isinstance(gt, list):
        # Converted format: list of entries
        all_svcs, all_pods = [], []
        for entry in gt:
            if isinstance(entry, dict):
                all_svcs.extend(entry.get("service") or [])
                all_pods.extend(entry.get("pod") or [])
        result["gt_services"] = all_svcs
        result["gt_pods"] = all_pods
        result["gt_containers"] = []
        result["gt_functions"] = []
        result["gt_metrics"] = []
        result["gt_spans"] = []
    # engine_config (raw, for reference)
    ec = inj.get("engine_config")
    if isinstance(ec, str):
        try:
            ec = json.loads(ec)
        except json.JSONDecodeError:
            pass
    result["engine_config"] = ec
    return result


def load_causal_graph_full(src_dir: Path) -> dict:
    """Load causal_graph.json and extract per-node states + service-level edges."""
    cg = load_json_safe(src_dir / "causal_graph.json") if src_dir else None
    if not cg:
        return {}
    c2s = cg.get("component_to_service") or {}
    # Nodes with states
    nodes = []
    for n in cg.get("nodes") or []:
        if isinstance(n, dict):
            comp = n.get("component", "")
            svc = c2s.get(comp, comp)
            nodes.append({
                "component": comp,
                "service": svc,
                "state": n.get("state") or [],
            })
    # Edges — span level
    raw_edges = cg.get("edges") or []
    # Service-level rollup
    svc_edges: set[tuple[str, str]] = set()
    for e in raw_edges:
        src_comp = e.get("source", "") if isinstance(e, dict) else (e[0] if isinstance(e, (list, tuple)) else "")
        tgt_comp = e.get("target", "") if isinstance(e, dict) else (e[1] if isinstance(e, (list, tuple)) and len(e) >= 2 else "")
        src_svc = c2s.get(src_comp, src_comp)
        tgt_svc = c2s.get(tgt_comp, tgt_comp)
        if src_svc != tgt_svc:
            svc_edges.add((src_svc, tgt_svc))
    return {
        "nodes": nodes,
        "root_causes": cg.get("root_causes") or [],
        "alarm_nodes": cg.get("alarm_nodes") or [],
        "raw_edges_count": len(raw_edges),
        "service_edges": sorted(svc_edges),
        "component_to_service": c2s,
    }


def load_k8s_summary(src_dir: Path, target_services: list[str]) -> list[dict]:
    """Extract pod restart counts and events from k8s.json for target + related services."""
    k8s_path = src_dir.parent / "k8s.json" if src_dir else None
    if not k8s_path or not k8s_path.exists():
        return []
    try:
        k8s = json.loads(k8s_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out: list[dict] = []
    # k8s.json can be list of items or dict with "items"
    items = k8s if isinstance(k8s, list) else (k8s.get("items") or [])
    target_set = {s.lower() for s in target_services}
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind", "")
        metadata = item.get("metadata") or {}
        name = metadata.get("name", "")
        ns = metadata.get("namespace", "")
        # Match by service name substring
        svc_match = any(t in name.lower() for t in target_set) if target_set else False
        if not svc_match:
            continue
        status = item.get("status") or {}
        # Pods — restart count
        if kind == "Pod" or "containerStatuses" in status:
            cs_list = status.get("containerStatuses") or []
            for cs in cs_list:
                if isinstance(cs, dict):
                    out.append({
                        "kind": "Pod",
                        "name": name,
                        "namespace": ns,
                        "container": cs.get("name", ""),
                        "restartCount": cs.get("restartCount", 0),
                        "ready": cs.get("ready"),
                        "state": list((cs.get("state") or {}).keys()),
                    })
        # Events
        if kind == "Event" or item.get("reason"):
            out.append({
                "kind": "Event",
                "name": name,
                "reason": item.get("reason", ""),
                "message": str(item.get("message", ""))[:300],
                "count": item.get("count"),
            })
    return out[:50]  # Cap for sanity


def log_delta_per_service(src_dir: Path) -> dict:
    """Compare abnormal vs normal logs: per-service total volume delta + error count delta.
    Returns {'volume_delta': [...], 'error_delta': [...], 'total_abn_errors': N, 'total_nor_errors': N}
    Sorted by delta (ascending = biggest decrease first, i.e. services that went silent)."""
    abn = load_parquet_safe(src_dir / "abnormal_logs.parquet")
    nor = load_parquet_safe(src_dir / "normal_logs.parquet")
    if abn is None or nor is None:
        return {}
    svc_col = "service_name"
    lvl_col = "level"
    error_levels = {"ERROR", "SEVERE", "FATAL", "CRITICAL"}
    # Volume delta
    abn_vol = abn.groupby(svc_col).size()
    nor_vol = nor.groupby(svc_col).size()
    vol_delta = (abn_vol.subtract(nor_vol, fill_value=0)).sort_values()
    volume_rows = [
        {"service": svc, "normal": int(nor_vol.get(svc, 0)), "abnormal": int(abn_vol.get(svc, 0)),
         "delta": int(d)}
        for svc, d in vol_delta.items() if d != 0
    ]
    # Error delta
    abn_err = abn[abn[lvl_col].astype(str).str.upper().isin(error_levels)].groupby(svc_col).size()
    nor_err = nor[nor[lvl_col].astype(str).str.upper().isin(error_levels)].groupby(svc_col).size()
    err_delta = (abn_err.subtract(nor_err, fill_value=0)).sort_values()
    error_rows = [
        {"service": svc, "normal_errors": int(nor_err.get(svc, 0)),
         "abnormal_errors": int(abn_err.get(svc, 0)), "delta": int(d)}
        for svc, d in err_delta.items() if d != 0
    ]
    return {
        "volume_delta": volume_rows,
        "error_delta": error_rows,
        "total_abn_errors": int(abn_err.sum()),
        "total_nor_errors": int(nor_err.sum()),
    }


def trace_delta_per_service(src_dir: Path) -> dict:
    """Compare abnormal vs normal traces: per-service span count delta + error span delta.
    Returns {'span_delta': [...], 'error_span_delta': {...}, 'http_error_delta': {...}}"""
    abn = load_parquet_safe(src_dir / "abnormal_traces.parquet")
    nor = load_parquet_safe(src_dir / "normal_traces.parquet")
    if abn is None or nor is None:
        return {}
    svc_col = "service_name"
    # Span volume delta
    abn_cnt = abn.groupby(svc_col).size()
    nor_cnt = nor.groupby(svc_col).size()
    span_delta = (abn_cnt.subtract(nor_cnt, fill_value=0)).sort_values()
    span_rows = [
        {"service": svc, "normal_spans": int(nor_cnt.get(svc, 0)),
         "abnormal_spans": int(abn_cnt.get(svc, 0)), "delta": int(d)}
        for svc, d in span_delta.items() if d != 0
    ]
    # Error span delta (status_code = "Error")
    status_col = "attr.status_code"
    error_span_info: dict[str, Any] = {}
    if status_col in abn.columns:
        abn_errs = abn[abn[status_col] == "Error"]
        nor_errs = nor[nor[status_col] == "Error"]
        error_span_info["abnormal_error_spans"] = int(len(abn_errs))
        error_span_info["normal_error_spans"] = int(len(nor_errs))
        if len(abn_errs) > 0:
            error_span_info["error_by_service"] = abn_errs.groupby(svc_col).size().sort_values(ascending=False).head(10).to_dict()
    # HTTP error delta (status >= 400)
    http_col = "attr.http.response.status_code"
    http_info: dict[str, Any] = {}
    if http_col in abn.columns:
        abn_http = abn[abn[http_col].fillna(0).astype(float) >= 400]
        nor_http = nor[nor[http_col].fillna(0).astype(float) >= 400]
        http_info["abnormal_http_errors"] = int(len(abn_http))
        http_info["normal_http_errors"] = int(len(nor_http))
        if len(abn_http) > 0:
            http_info["by_service"] = abn_http.groupby(svc_col).size().sort_values(ascending=False).head(10).to_dict()
    return {
        "span_delta": span_rows,
        "error_span": error_span_info,
        "http_error": http_info,
    }


def load_result_json(src_dir: Path) -> dict:
    """Load result.json — the most detailed GT propagation data (paths with states, edges, timing)."""
    rj = load_json_safe(src_dir / "result.json") if src_dir else None
    if not rj:
        return {}
    out: dict[str, Any] = {
        "case_name": rj.get("case_name"),
        "injection_nodes": rj.get("injection_nodes") or [],
    }
    pr = rj.get("propagation_result") or {}
    out["injection_states"] = pr.get("injection_states") or []
    paths_raw = pr.get("paths") or []
    paths = []
    for p in paths_raw:
        if not isinstance(p, dict):
            continue
        paths.append({
            "node_ids": p.get("nodes") or [],
            "states": p.get("states") or [],
            "edges": p.get("edges") or [],
            "propagation_delays": p.get("propagation_delays") or [],
            "confidence": p.get("confidence"),
        })
    out["paths"] = paths
    return out


def load_abnormal_connection(src_dir: Path) -> dict:
    """Load abnormal_connection/ dir data (pod-level states + propagation patterns). Not all cases have this."""
    ac_dir = src_dir / "abnormal_connection" if src_dir else None
    if not ac_dir or not ac_dir.exists():
        return {}
    out: dict[str, Any] = {}
    nodes_df = load_parquet_safe(ac_dir / "abnormal_nodes.parquet")
    if nodes_df is not None and not nodes_df.empty:
        out["nodes"] = [
            {"node_name": str(row.get("node_name", "")), "kind": str(row.get("node_kind", "")),
             "state": str(row.get("state", "")), "uniq_name": str(row.get("uniq_name", ""))}
            for _, row in nodes_df.iterrows()
        ]
    patterns_df = load_parquet_safe(ac_dir / "propagation_patterns.parquet")
    if patterns_df is not None and not patterns_df.empty:
        # Only include rows with actual metric data
        cols_to_check = ["abnormal_avg_latency", "abnormal_error_rate", "latency_increase_ratio", "error_rate_delta"]
        has_data = patterns_df.dropna(subset=[c for c in cols_to_check if c in patterns_df.columns], how="all")
        rows = []
        for _, row in has_data.iterrows():
            rows.append({
                "src": str(row.get("src_name", "")), "dst": str(row.get("dst_name", "")),
                "pattern": str(row.get("pattern_type", "")),
                "dst_state": str(row.get("dst_state", "")),
                "latency_ratio": _as_float(row.get("latency_increase_ratio")),
                "error_delta": _as_float(row.get("error_rate_delta")),
            })
        if rows:
            out["propagation_patterns"] = rows
    return out


def load_conclusion(src_dir: Path) -> pd.DataFrame | None:
    for p in [src_dir / "conclusion.parquet", src_dir.parent / "conclusion.parquet",
              src_dir / "conclusion.csv", src_dir.parent / "conclusion.csv"]:
        if p is not None and p.exists():
            try:
                return pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)
            except Exception:  # noqa: BLE001
                continue
    return None


def top_anomalous_spans(conclusion_df: pd.DataFrame, n: int = 20) -> list[dict]:
    if conclusion_df is None or conclusion_df.empty:
        return []
    df = conclusion_df.copy()
    for col in ("AbnormalSuccRate", "NormalSuccRate", "AbnormalAvgDuration", "NormalAvgDuration"):
        if col not in df.columns:
            df[col] = None
    df["succ_drop"] = df["NormalSuccRate"].astype(float, errors="ignore") - df["AbnormalSuccRate"].astype(float, errors="ignore")
    try:
        df["latency_ratio"] = df["AbnormalAvgDuration"].astype(float) / df["NormalAvgDuration"].astype(float).clip(lower=1e-9)
    except Exception:  # noqa: BLE001
        df["latency_ratio"] = 1.0
    df["score"] = df["succ_drop"].fillna(0).clip(lower=0) * 10 + (df["latency_ratio"].fillna(1) - 1).clip(lower=0)
    df = df.sort_values("score", ascending=False).head(n)
    return [
        {
            "span": str(row.get("SpanName", "")),
            "abnormal_succ_rate": _as_float(row.get("AbnormalSuccRate")),
            "normal_succ_rate": _as_float(row.get("NormalSuccRate")),
            "abnormal_avg_ms": _as_float_ms(row.get("AbnormalAvgDuration")),
            "normal_avg_ms": _as_float_ms(row.get("NormalAvgDuration")),
        }
        for _, row in df.iterrows()
    ]


def top_error_logs(src_dir: Path, n: int = 20) -> list[dict]:
    df = load_parquet_safe(src_dir / "abnormal_logs.parquet")
    if df is None or df.empty:
        return []
    level_col = next((c for c in df.columns if c.lower() in {"level", "severity"}), None)
    msg_col = next((c for c in df.columns if c.lower() in {"message", "body", "msg", "content"}), None)
    svc_col = next((c for c in df.columns if c.lower() in {"service", "servicename", "service_name"}), None)
    if msg_col is None:
        return []
    mask = pd.Series(False, index=df.index)
    if level_col is not None:
        mask = mask | df[level_col].astype(str).str.upper().isin(SEVERE_LEVELS)
    mask = mask | df[msg_col].astype(str).str.contains(r"\b(5\d\d|error|refused|timeout|exception)\b", case=False, regex=True, na=False)
    err = df[mask]
    if err.empty:
        return []
    sig = err[msg_col].astype(str).str.replace(r"\d+", "#", regex=True).str[:120]
    grouped = err.assign(_sig=sig).groupby("_sig").size().sort_values(ascending=False).head(n)
    out = []
    for sig_val, count in grouped.items():
        rec: dict[str, Any] = {"signature": sig_val, "count": int(count)}
        if svc_col is not None:
            services = err[err[msg_col].astype(str).str.replace(r"\d+", "#", regex=True).str[:120] == sig_val][
                svc_col
            ].dropna().unique().tolist()[:5]
            rec["services"] = services
        out.append(rec)
    return out


def _zscore_one_parquet(abn_path: Path, nor_path: Path, val_col_name: str = "value",
                        z_threshold: float = 3.0, top_k: int = 30, source_label: str = "") -> list[dict]:
    """Generic z-score comparison between abnormal and normal metric parquets."""
    abn = load_parquet_safe(abn_path)
    nor = load_parquet_safe(nor_path)
    if abn is None or nor is None or abn.empty or nor.empty:
        return []
    svc_col = next((c for c in abn.columns if c.lower() in {"service", "servicename", "service_name"}), None)
    name_col = next((c for c in abn.columns if c.lower() in {"metric", "metricname", "metric_name", "name"}), None)
    val_col = next((c for c in abn.columns if c.lower() in {val_col_name, "value", "val"}), None)
    if name_col is None or val_col is None:
        return []
    keys = [c for c in (svc_col, name_col) if c is not None]
    try:
        nor_g = nor.groupby(keys)[val_col].agg(["mean", "std"]).reset_index()
        abn_g = abn.groupby(keys)[val_col].mean().reset_index().rename(columns={val_col: "abn_mean"})
        m = abn_g.merge(nor_g, on=keys, how="inner")
    except Exception:  # noqa: BLE001
        return []
    m["std"] = m["std"].replace(0, pd.NA).fillna(1e-9)
    m["z"] = (m["abn_mean"] - m["mean"]).abs() / m["std"]
    m = m[m["z"] >= z_threshold].sort_values("z", ascending=False).head(top_k)
    return [
        {"service": str(row[svc_col]) if svc_col else None, "metric": str(row[name_col]),
         "normal_mean": _as_float(row["mean"]), "abnormal_mean": _as_float(row["abn_mean"]),
         "z": _as_float(row["z"]), "source": source_label}
        for _, row in m.iterrows()
    ]


def _zscore_histogram(abn_path: Path, nor_path: Path, z_threshold: float = 3.0, top_k: int = 20) -> list[dict]:
    """Z-score for histogram metrics — compare count and sum (mean = sum/count)."""
    abn = load_parquet_safe(abn_path)
    nor = load_parquet_safe(nor_path)
    if abn is None or nor is None or abn.empty or nor.empty:
        return []
    svc_col = next((c for c in abn.columns if c.lower() in {"service", "servicename", "service_name"}), None)
    name_col = next((c for c in abn.columns if c.lower() in {"metric", "metricname", "metric_name", "name"}), None)
    if name_col is None or "count" not in abn.columns or "sum" not in abn.columns:
        return []
    keys = [c for c in (svc_col, name_col) if c is not None]
    # Derive mean duration = sum / count
    for df in (abn, nor):
        df["_avg"] = df["sum"] / df["count"].clip(lower=1)
    try:
        nor_g = nor.groupby(keys)["_avg"].agg(["mean", "std"]).reset_index()
        abn_g = abn.groupby(keys)["_avg"].mean().reset_index().rename(columns={"_avg": "abn_mean"})
        m = abn_g.merge(nor_g, on=keys, how="inner")
    except Exception:  # noqa: BLE001
        return []
    m["std"] = m["std"].replace(0, pd.NA).fillna(1e-9)
    m["z"] = (m["abn_mean"] - m["mean"]).abs() / m["std"]
    m = m[m["z"] >= z_threshold].sort_values("z", ascending=False).head(top_k)
    return [
        {"service": str(row[svc_col]) if svc_col else None, "metric": str(row[name_col]),
         "normal_mean": _as_float(row["mean"]), "abnormal_mean": _as_float(row["abn_mean"]),
         "z": _as_float(row["z"]), "source": "histogram"}
        for _, row in m.iterrows()
    ]


def zscore_anomalous_metrics(src_dir: Path, z_threshold: float = 3.0, top_k: int = 30) -> list[dict]:
    """Compare normal vs abnormal across ALL three metric parquets: gauge, sum, histogram."""
    results: list[dict] = []
    # Gauge metrics (container.cpu.usage, jvm.cpu, hubble_http_request_duration_p*, ...)
    results.extend(_zscore_one_parquet(
        src_dir / "abnormal_metrics.parquet", src_dir / "normal_metrics.parquet",
        z_threshold=z_threshold, top_k=top_k, source_label="gauge"))
    # Sum/counter metrics (hubble_drop_total, k8s.pod.network.errors, hubble_tcp_flags_total, ...)
    results.extend(_zscore_one_parquet(
        src_dir / "abnormal_metrics_sum.parquet", src_dir / "normal_metrics_sum.parquet",
        z_threshold=z_threshold, top_k=top_k, source_label="sum"))
    # Histogram metrics (http.server.request.duration, jvm.gc.duration, ...)
    results.extend(_zscore_histogram(
        src_dir / "abnormal_metrics_histogram.parquet", src_dir / "normal_metrics_histogram.parquet",
        z_threshold=z_threshold, top_k=top_k // 2))
    # Sort all by z descending, keep top_k overall
    results.sort(key=lambda x: -(x.get("z") or 0))
    return results[:top_k]


# ── Part B: trajectory parsing ──────────────────────────────────────────────


@dataclass
class ToolResultParsed:
    raw: str  # full text (written to companion JSON)
    display: str  # truncated for markdown
    row_count: int | None = None
    error_snippets: list[str] = field(default_factory=list)  # matched error patterns
    services_mentioned: list[str] = field(default_factory=list)


@dataclass
class Round:
    index: int  # 1-based
    think: str | None = None
    tools: list[dict] = field(default_factory=list)  # {name, args_full, services}
    results: list[ToolResultParsed] = field(default_factory=list)


def _msg_content_text(msg: dict) -> str:
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                t = item.get("text") or item.get("content") or ""
                parts.append(str(t))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return ""


def _extract_think_text(arg_str: str) -> str | None:
    try:
        obj = json.loads(arg_str)
        if isinstance(obj, dict):
            for k in ("thought", "text", "content", "reflection"):
                if k in obj and obj[k]:
                    return str(obj[k])
    except json.JSONDecodeError:
        pass
    return arg_str[:2000] if arg_str else None


def _parse_tool_result(content: str) -> ToolResultParsed:
    raw = content.strip()
    display = raw[:TOOL_RESULT_DISPLAY_LIMIT]
    if len(raw) > TOOL_RESULT_DISPLAY_LIMIT:
        display += f"\n... ({len(raw)} chars total, truncated)"
    # Row count heuristic: count newlines in tabular-looking results
    lines = raw.splitlines()
    row_count = len(lines) - 1 if len(lines) > 2 else None  # subtract header
    # Error snippets: first 5 unique error patterns
    error_snippets = sorted(set(m.group(0) for m in ERROR_RE.finditer(raw)))[:5]
    # Services mentioned
    services_mentioned = sorted(set(SERVICE_RE.findall(raw)))
    return ToolResultParsed(
        raw=raw, display=display, row_count=row_count,
        error_snippets=error_snippets, services_mentioned=services_mentioned,
    )


def parse_trajectory(traj_str: str | None) -> list[Round]:
    if not traj_str:
        return []
    try:
        traj = json.loads(traj_str)
    except json.JSONDecodeError:
        return []
    rounds: list[Round] = []
    idx = 0
    pending_think = None
    for msg in traj:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        if role == "assistant":
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                content = _msg_content_text(msg)
                if content:
                    pending_think = content
                continue
            idx += 1
            r = Round(index=idx, think=pending_think)
            pending_think = None
            for tc in tool_calls:
                fn = (tc.get("function") or {}) if isinstance(tc, dict) else {}
                name = fn.get("name", "")
                arg_str = fn.get("arguments", "") or ""
                if name == "think_tool":
                    think_text = _extract_think_text(arg_str)
                    r.think = (r.think or "") + ("\n" if r.think else "") + (think_text or "")
                    continue
                services = sorted(set(SERVICE_RE.findall(arg_str)))
                r.tools.append({"name": name, "args_full": arg_str, "services": services})
            rounds.append(r)
        elif role == "tool":
            if rounds:
                content = _msg_content_text(msg)
                if content:
                    rounds[-1].results.append(_parse_tool_result(content))
    return rounds


def extract_hypothesis(think_text: str | None) -> str | None:
    if not think_text:
        return None
    for pat in HYP_PATTERNS:
        m = pat.search(think_text)
        if m:
            return m.group(1)
    return None


# ── Intent overlay ─────────────────────────────────────────────────────────


def intent_overlay(meta: dict) -> dict[int, list[dict]]:
    llm_intents = (meta or {}).get("llm_intents", {}) or {}
    entries = llm_intents.get(INTENT_MODEL_KEY) or []
    out: dict[int, list[dict]] = {}
    for e in entries:
        if isinstance(e, dict) and e.get("round") is not None:
            out.setdefault(int(e["round"]), []).append(
                {"intent": e.get("intent", ""), "data_type": e.get("data_type", "")}
            )
    return out


def round_stage_tag(intents_this_round: list[dict]) -> str:
    if not intents_this_round:
        return "-"
    tags = [STAGE_BY_INTENT.get(i.get("intent", ""), "-") for i in intents_this_round]
    return max(set(tags), key=tags.count)


# ── Dossier rendering ───────────────────────────────────────────────────────


def render_dossier(d: dict) -> str:
    meta: dict = d["meta"] or {}
    diff = meta.get("difficulty", {}) or {}
    gt_svcs = meta.get("ground_truth") or []
    gm = (meta.get("graph_metrics") or {}).get("diagnostic", {}) or {}
    cm = meta.get("cost_metrics") or {}
    cge = meta.get("causal_graph_evaluation") or {}
    inj = d["injection_full"]
    cg = d["causal_graph_full"]
    k8s = d["k8s_summary"]
    spans = d["spans"]
    errors = d["errors"]
    zmetrics = d["zmetrics"]
    rounds: list[Round] = d["rounds"]
    intent_by_round = d["intent_by_round"]

    L: list[str] = []
    dsi = d["dataset_index"]
    ft = diff.get("fault_type", "?")
    fc = diff.get("fault_category", "?")
    L.append(f"# case_{dsi} — {fc} / {ft}")
    L.append("")
    L.append(f"- dataset_index: **{dsi}**")
    L.append(f"- exp_id: {d['exp_id']}")
    L.append(f"- datapack: `{meta.get('datapack_name', '?')}`")
    L.append(f"- source_data_dir: `{d['src_dir']}`")
    L.append(f"- spl={diff.get('spl')}  n_svc={diff.get('n_svc')}  n_edge={diff.get('n_edge')}")
    L.append("")

    # ── PART A ──
    L.append("## Part A — GT reality (what actually happened)")
    L.append("")

    # A.1 Injection spec (full)
    L.append("### A.1 Injection spec")
    if inj:
        L.append(f"- fault_type_raw: `{inj.get('fault_type_raw')}`")
        L.append(f"- injection_name: `{inj.get('injection_name')}`")
        L.append(f"- start_time: `{inj.get('start_time')}`")
        L.append(f"- end_time: `{inj.get('end_time')}`")
        L.append(f"- pre_duration: {inj.get('pre_duration')} min")
        dc = inj.get("display_config")
        if dc:
            L.append("- **display_config** (human-readable injection params):")
            for k, v in dc.items():
                L.append(f"  - {k}: `{v}`")
        L.append(f"- gt_services: {inj.get('gt_services')}")
        L.append(f"- gt_pods: {inj.get('gt_pods')}")
        gf = inj.get("gt_functions")
        if gf:
            L.append(f"- **gt_functions** (targeted method): {gf}")
        gmet = inj.get("gt_metrics")
        if gmet:
            L.append(f"- **gt_metrics** (targeted metric dimension): {gmet}")
    else:
        L.append("- injection.json not found")
    L.append("")

    # A.2 GT root-cause services
    L.append("### A.2 Ground-truth root-cause services (from DB meta)")
    for s in gt_svcs:
        L.append(f"- `{s}`")
    if not gt_svcs:
        L.append("- (none)")
    L.append("")

    # A.3 GT causal graph — nodes with states + service-level propagation
    L.append("### A.3 GT causal graph")
    if cg:
        L.append(f"- nodes: {len(cg.get('nodes', []))},  raw_edges: {cg.get('raw_edges_count', 0)}")
        L.append(f"- root_causes: {cg.get('root_causes')}")
        L.append(f"- alarm_nodes: {cg.get('alarm_nodes')}")
        L.append("")
        nodes = cg.get("nodes") or []
        if nodes:
            L.append("**Per-node expected states** (what anomalies SHOULD be visible):")
            L.append("")
            L.append("| component | service | expected_states |")
            L.append("|---|---|---|")
            for n in nodes:
                L.append(f"| `{n['component']}` | `{n['service']}` | {n['state']} |")
            L.append("")
        se = cg.get("service_edges") or []
        if se:
            L.append("**Service-level propagation chain** (rolled up from span edges):")
            L.append("")
            for src, tgt in se:
                L.append(f"- `{src}` → `{tgt}`")
            L.append("")
    else:
        L.append("- causal_graph.json not found")
        L.append("")

    # A.4 Span-level footprint
    L.append("### A.4 Span-level footprint (top 20)")
    if spans:
        L.append("| span | abn_succ | norm_succ | abn_ms | norm_ms |")
        L.append("|---|---|---|---|---|")
        for s in spans:
            L.append(f"| `{s['span'][:80]}` | {s['abnormal_succ_rate']} | {s['normal_succ_rate']} | {s['abnormal_avg_ms']} | {s['normal_avg_ms']} |")
    else:
        L.append("- conclusion data not available")
    L.append("")

    # A.5a Error log signatures (absolute, for reference)
    L.append("### A.5a Top error log signatures (abnormal period)")
    if errors:
        for e in errors:
            svc = e.get("services", [])
            L.append(f"- ({e['count']}) `{e['signature']}`" + (f"  — {svc}" if svc else ""))
    else:
        L.append("- no error logs found")
    L.append("")

    # A.5b Log delta (abnormal vs normal — the REAL signal)
    ld = d["log_delta"]
    L.append("### A.5b Log delta (abnormal vs normal period)")
    if ld:
        L.append(f"- total errors: normal={ld.get('total_nor_errors', '?')}, abnormal={ld.get('total_abn_errors', '?')}")
        L.append("")
        err_d = ld.get("error_delta") or []
        if err_d:
            L.append("**Per-service ERROR count delta:**")
            L.append("")
            L.append("| service | normal_errors | abnormal_errors | delta |")
            L.append("|---|---|---|---|")
            for row in err_d:
                L.append(f"| `{row['service']}` | {row['normal_errors']} | {row['abnormal_errors']} | {row['delta']:+d} |")
            L.append("")
        vol_d = ld.get("volume_delta") or []
        if vol_d:
            L.append("**Per-service log VOLUME delta:**")
            L.append("")
            L.append("| service | normal_total | abnormal_total | delta |")
            L.append("|---|---|---|---|")
            for row in vol_d:
                L.append(f"| `{row['service']}` | {row['normal']} | {row['abnormal']} | {row['delta']:+d} |")
            L.append("")
    else:
        L.append("- normal_logs not available for comparison")
    L.append("")

    # A.5c Trace delta (abnormal vs normal)
    td = d["trace_delta"]
    L.append("### A.5c Trace span delta (abnormal vs normal period)")
    if td:
        es = td.get("error_span") or {}
        if es:
            L.append(f"- Error spans: normal={es.get('normal_error_spans', 0)}, abnormal={es.get('abnormal_error_spans', 0)}")
            if es.get("error_by_service"):
                L.append(f"- Error spans by service: {es['error_by_service']}")
        hi = td.get("http_error") or {}
        if hi:
            L.append(f"- HTTP 4xx/5xx responses: normal={hi.get('normal_http_errors', 0)}, abnormal={hi.get('abnormal_http_errors', 0)}")
            if hi.get("by_service"):
                L.append(f"- HTTP errors by service: {hi['by_service']}")
        L.append("")
        span_d = td.get("span_delta") or []
        if span_d:
            L.append("**Per-service span count delta:**")
            L.append("")
            L.append("| service | normal_spans | abnormal_spans | delta |")
            L.append("|---|---|---|---|")
            for row in span_d:
                L.append(f"| `{row['service']}` | {row['normal_spans']} | {row['abnormal_spans']} | {row['delta']:+d} |")
            L.append("")
    else:
        L.append("- normal_traces not available for comparison")
    L.append("")

    # A.6 Anomalous metrics (gauge + sum + histogram)
    L.append("### A.6 Anomalous metrics (|z| ≥ 3, across gauge/sum/histogram parquets)")
    if zmetrics:
        L.append("| service | metric | normal | abnormal | z | source |")
        L.append("|---|---|---|---|---|---|")
        for m in zmetrics:
            z_val = m['z']
            z_str = f"{z_val:.2f}" if z_val is not None else "?"
            L.append(f"| {m['service']} | {m['metric']} | {m['normal_mean']} | {m['abnormal_mean']} | {z_str} | {m.get('source', '')} |")
    else:
        L.append("- no metrics exceeding threshold in any of the 3 metric parquets")
    L.append("")

    # A.7 k8s pod / event summary
    L.append("### A.7 K8s state (pods & events for GT-related services)")
    if k8s:
        for item in k8s:
            if item.get("kind") == "Pod":
                L.append(f"- Pod `{item['name']}` container=`{item.get('container')}` restartCount={item.get('restartCount')} ready={item.get('ready')} state={item.get('state')}")
            elif item.get("kind") == "Event":
                L.append(f"- Event `{item['name']}` reason={item.get('reason')} count={item.get('count')}: {item.get('message', '')[:200]}")
    else:
        L.append("- k8s.json not found or no matching entries")
    L.append("")

    # A.8 result.json propagation paths (most detailed GT propagation)
    rj = d["result_json"]
    L.append("### A.8 GT propagation paths (from result.json)")
    if rj and rj.get("paths"):
        L.append(f"- injection_nodes: {rj.get('injection_nodes')}")
        L.append(f"- injection_states: {rj.get('injection_states')}")
        L.append(f"- propagation paths: {len(rj['paths'])}")
        L.append("")
        for pi, path in enumerate(rj["paths"][:5], 1):
            L.append(f"**Path {pi}** (confidence={path.get('confidence')})")
            L.append("")
            states = path.get("states") or []
            edges = path.get("edges") or []
            delays = path.get("propagation_delays") or []
            L.append("| step | node_id | states | edge_to_next | delay(s) |")
            L.append("|---|---|---|---|---|")
            for si, node_id in enumerate(path.get("node_ids") or []):
                st = states[si] if si < len(states) else []
                edge = edges[si] if si < len(edges) else ""
                delay = delays[si] if si < len(delays) else ""
                L.append(f"| {si} | {node_id} | {st} | {edge} | {delay} |")
            L.append("")
    else:
        L.append("- result.json not found or no propagation paths")
    L.append("")

    # A.9 abnormal_connection (pod-level topology + propagation patterns)
    ac = d["abnormal_connection"]
    L.append("### A.9 Infrastructure topology (from abnormal_connection/)")
    if ac:
        ac_nodes = ac.get("nodes") or []
        if ac_nodes:
            L.append(f"**Abnormal nodes** ({len(ac_nodes)} pods/components with anomalies):")
            L.append("")
            L.append("| kind | name | state |")
            L.append("|---|---|---|")
            for n in ac_nodes:
                L.append(f"| {n['kind']} | `{n['node_name']}` | {n['state']} |")
            L.append("")
        pp = ac.get("propagation_patterns") or []
        if pp:
            L.append(f"**Propagation patterns** ({len(pp)} edges with metric data):")
            L.append("")
            L.append("| src → dst | pattern | dst_state | latency_ratio | error_delta |")
            L.append("|---|---|---|---|---|")
            for p in pp:
                L.append(f"| `{p['src']}` → `{p['dst']}` | {p['pattern']} | {p['dst_state']} | {p['latency_ratio']} | {p['error_delta']} |")
            L.append("")
    else:
        L.append("- abnormal_connection/ not available for this case")
    L.append("")

    # A.10 Signal observability flags
    L.append("### A.10 Signal observability summary")
    L.append("")
    L.append("Does the available observability data contain the PRIMARY fault signal for this fault type?")
    L.append("")
    has_error_logs = len(errors) > 0
    has_metric_anomaly = len(zmetrics) > 0
    has_span_anomaly = len(spans) > 0
    has_k8s_restart = any(item.get("restartCount", 0) > 0 for item in k8s if item.get("kind") == "Pod")
    L.append(f"- error logs (ERROR/SEVERE in abnormal period): {'yes' if has_error_logs else 'no'}")
    L.append(f"- metric anomalies (z>3 across gauge/sum/histogram): {'yes' if has_metric_anomaly else 'no'}")
    L.append(f"- span success/latency anomalies (conclusion): {'yes' if has_span_anomaly else 'no'}")
    L.append(f"- k8s pod restarts (restartCount>0): {'yes' if has_k8s_restart else 'no'}")
    L.append(f"- result.json propagation paths: {'yes' if rj and rj.get('paths') else 'no'}")
    L.append(f"- abnormal_connection data: {'yes' if ac else 'no'}")
    ld_info = d["log_delta"]
    td_info = d["trace_delta"]
    if ld_info:
        L.append(f"- log delta available (normal vs abnormal): yes")
    if td_info:
        L.append(f"- trace delta available (normal vs abnormal): yes")
    L.append("")

    # ── PART B ──
    L.append("## Part B — Agent trajectory (what the agent did)")
    L.append("")

    # B.0 What the agent was asked (augmented_question)
    aq = d.get("augmented_question") or ""
    if aq:
        L.append("### B.0 Prompt received by agent (augmented_question)")
        L.append("```")
        L.append(aq)
        L.append("```")
        L.append("")

    # B.1 Final answer + full predicted causal graph
    L.append("### B.1 Final answer")
    pred_rc = cge.get("root_cause_services") or []
    L.append(f"- predicted root_cause_services: {pred_rc}")
    L.append(f"- judged correct: {cge.get('correct')}")
    if cge.get("reasoning"):
        L.append(f"- judge reasoning: {cge['reasoning']}")
    L.append("")
    resp_json = d.get("response_json")
    if resp_json:
        L.append("**Agent's full predicted causal graph:**")
        L.append("")
        # Nodes predicted by agent
        pred_nodes = resp_json.get("nodes") or []
        if pred_nodes:
            L.append("| component | state | timestamp |")
            L.append("|---|---|---|")
            for pn in pred_nodes:
                if isinstance(pn, dict):
                    L.append(f"| `{pn.get('component', '?')}` | {pn.get('state', [])} | {pn.get('timestamp', '')} |")
            L.append("")
        # Edges predicted by agent
        pred_edges = resp_json.get("edges") or []
        if pred_edges:
            L.append(f"Predicted edges ({len(pred_edges)}):")
            L.append("")
            for pe in pred_edges[:30]:
                if isinstance(pe, dict):
                    L.append(f"- `{pe.get('source', '?')}` → `{pe.get('target', '?')}`")
            if len(pred_edges) > 30:
                L.append(f"- ... ({len(pred_edges)} total)")
            L.append("")
        # Root causes predicted by agent
        pred_rcs = resp_json.get("root_causes") or []
        if pred_rcs:
            L.append(f"Predicted root_causes: {pred_rcs}")
            L.append("")
    L.append("")

    # B.2 Graph metrics diagnostic
    L.append("### B.2 Graph metrics diagnostic")
    L.append(f"- matched_services: {gm.get('matched_services') or []}")
    L.append(f"- missed_services: {gm.get('missed_services') or []}")
    L.append(f"- hallucinated_services: {gm.get('hallucinated_services') or []}")
    L.append(f"- matched_service_edges: {gm.get('matched_service_edges') or []}")
    L.append(f"- missed_service_edges: {gm.get('missed_service_edges') or []}")
    L.append(f"- hallucinated_service_edges: {gm.get('hallucinated_service_edges') or []}")
    L.append("")

    # B.3 Cost
    L.append("### B.3 Cost signature")
    L.append(f"- effective_rounds: {cm.get('effective_rounds')}")
    L.append(f"- total_tokens: {cm.get('total_tokens')}")
    L.append(f"- time_cost: {cm.get('time_cost')}")
    L.append(f"- model: {cm.get('model')}")
    L.append("")

    # B.4 Full trajectory
    L.append("### B.4 Full round-by-round trajectory")
    L.append(f"- total rounds: {len(rounds)}")
    L.append(f"- (raw trajectory JSON: `case_{dsi}.raw.json`)")
    L.append("")
    for r in rounds:
        hyp = extract_hypothesis(r.think)
        intents_r = intent_by_round.get(r.index, [])
        stage = round_stage_tag(intents_r)
        intent_tags = [f"{i.get('intent', '')}({i.get('data_type', '')})" for i in intents_r]

        L.append(f"#### Round {r.index}  [stage={stage}]")
        if hyp:
            L.append(f"- **hypothesis_at_round**: `{hyp}`")
        if intent_tags:
            L.append(f"- intents: {intent_tags}")
        # Think tool
        if r.think:
            L.append("- think_tool:")
            for line in r.think.strip().splitlines():
                L.append(f"  > {line}")
        # Tool calls — full args
        for i, t in enumerate(r.tools, 1):
            L.append(f"- tool[{i}] `{t['name']}` services={t['services']}")
            L.append(f"  ```")
            L.append(f"  {t['args_full']}")
            L.append(f"  ```")
        # Tool results — 2000 chars + structured extraction
        for j, tr in enumerate(r.results, 1):
            L.append(f"- result[{j}]:")
            if tr.error_snippets:
                L.append(f"  - **error_keywords**: {tr.error_snippets}")
            if tr.services_mentioned:
                L.append(f"  - **services_in_result**: {tr.services_mentioned}")
            if tr.row_count is not None and tr.row_count > 0:
                L.append(f"  - rows: ~{tr.row_count}")
            L.append(f"  ```")
            for line in tr.display.splitlines():
                L.append(f"  {line}")
            L.append(f"  ```")
        L.append("")

    # Footer for analyst
    L.append("---")
    L.append("")
    L.append("## Analyst section (fill during Phase 2)")
    L.append("")
    L.append("- **pivot_round**: <int>")
    L.append("- **proximate_cause** (short phrase): ")
    L.append("")

    return "\n".join(L)


# ── Main loop ──────────────────────────────────────────────────────────────


def get_engine(db_url: str):
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(db_url, connect_args=connect_args)


def iter_failed_cases(engine, exp_id: str, limit: int | None):
    with Session(engine) as session:
        stmt = select(EvaluationSample).where(
            EvaluationSample.exp_id == exp_id,
            EvaluationSample.correct == False,  # noqa: E712
            EvaluationSample.stage == "judged",
        )
        samples = session.exec(stmt).all()
    samples.sort(key=lambda s: s.dataset_index or 0)
    if limit:
        samples = samples[:limit]
    return samples


def build_one(sample: EvaluationSample) -> dict:
    meta = sample.meta or {}
    src_dir = find_source_dir(meta)
    gt_svcs = meta.get("ground_truth") or []

    inj_full = load_injection_full(src_dir) if src_dir else {}
    cg_full = load_causal_graph_full(src_dir) if src_dir else {}
    # For k8s: use GT services + injection services as search targets
    k8s_targets = list(set(gt_svcs + (inj_full.get("gt_services") or [])))
    k8s_summary = load_k8s_summary(src_dir, k8s_targets) if src_dir else []
    result_json = load_result_json(src_dir) if src_dir else {}
    abn_conn = load_abnormal_connection(src_dir) if src_dir else {}
    log_delta = log_delta_per_service(src_dir) if src_dir else {}
    trace_delta = trace_delta_per_service(src_dir) if src_dir else {}
    conclusion_df = load_conclusion(src_dir) if src_dir else None
    spans = top_anomalous_spans(conclusion_df) if conclusion_df is not None else []
    errors = top_error_logs(src_dir) if src_dir else []
    zmetrics = zscore_anomalous_metrics(src_dir) if src_dir else []
    rounds = parse_trajectory(sample.trajectories)
    intent_by_round = intent_overlay(meta)

    # Parse response JSON (agent's predicted causal graph)
    response_json = None
    if sample.response:
        try:
            response_json = json.loads(sample.response)
        except json.JSONDecodeError:
            pass

    return {
        "dataset_index": sample.dataset_index,
        "exp_id": sample.exp_id,
        "meta": meta,
        "src_dir": src_dir,
        "injection_full": inj_full,
        "causal_graph_full": cg_full,
        "k8s_summary": k8s_summary,
        "spans": spans,
        "errors": errors,
        "zmetrics": zmetrics,
        "rounds": rounds,
        "intent_by_round": intent_by_round,
        "log_delta": log_delta,
        "trace_delta": trace_delta,
        "raw_trajectory": sample.trajectories,
        "augmented_question": sample.augmented_question,
        "response_json": response_json,
        "result_json": result_json,
        "abnormal_connection": abn_conn,
    }


def write_index(out_dir: Path, rows: list[dict]) -> None:
    L = ["# Dossier index", ""]
    L.append(f"- total: {len(rows)}")
    L.append("")
    L.append("| dataset_index | fault_category | fault_type | n_svc | spl | has_src | rounds | file |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        d = (r["meta"].get("difficulty") or {})
        fc = d.get("fault_category", "?")
        ft = d.get("fault_type", "?")
        n_svc = d.get("n_svc", "?")
        spl = d.get("spl", "?")
        has_src = "yes" if r["src_dir"] else "no"
        nr = len(r["rounds"])
        dsi = r["dataset_index"]
        L.append(f"| {dsi} | {fc} | {ft} | {n_svc} | {spl} | {has_src} | {nr} | [case_{dsi}.md](case_{dsi}.md) |")
    (out_dir / "index.md").write_text("\n".join(L), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description="Phase 1 — failure-mode dossier builder (deterministic)")
    p.add_argument("--db", required=True, help="DB URL")
    p.add_argument("--exp_id", default="thinkdepthai-qwen3.5-plus")
    p.add_argument("--out_dir", required=True, help="Output directory for case_<idx>.md files")
    p.add_argument("--limit", type=int, default=None, help="Process only first N failed cases")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    engine = get_engine(args.db)
    samples = iter_failed_cases(engine, args.exp_id, args.limit)
    logger.info("Building dossiers for %d failed cases (exp_id=%s)", len(samples), args.exp_id)

    rows: list[dict] = []
    for i, s in enumerate(samples, 1):
        row = build_one(s)
        # Write markdown dossier
        md = render_dossier(row)
        md_path = out_dir / f"case_{s.dataset_index}.md"
        md_path.write_text(md, encoding="utf-8")
        # Write raw trajectory JSON companion (for drill-down)
        raw_path = out_dir / f"case_{s.dataset_index}.raw.json"
        raw_path.write_text(row.get("raw_trajectory") or "[]", encoding="utf-8")
        rows.append(row)
        logger.info("[%d/%d] wrote %s  rounds=%d src=%s",
                    i, len(samples), md_path.name, len(row["rounds"]), row["src_dir"])

    write_index(out_dir, rows)
    logger.info("Done. Index at %s", out_dir / "index.md")


if __name__ == "__main__":
    main()
