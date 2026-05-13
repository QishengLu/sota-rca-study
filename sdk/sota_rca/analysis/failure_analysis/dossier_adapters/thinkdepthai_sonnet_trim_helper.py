#!/usr/bin/env python3
"""
Extract a trimmed per-case view from a full dossier.
Keeps: A.1-A.3 (injection + GT), A.6 key metrics (top 10 z-score),
A.8 propagation (first path), A.10 summary, B.0 prompt, B.1 final answer,
B.2 graph metrics, B.3 cost, all think_tool reflections with round context.

Usage:
    python extract_trimmed.py case_<idx>.md > /tmp/trimmed.md
"""
import sys
import re
import json
from pathlib import Path


def extract(path: Path) -> str:
    raw = path.read_text()
    lines = raw.split("\n")

    # Find section line numbers
    sections = {}
    for i, ln in enumerate(lines):
        if ln.startswith("### A.") or ln.startswith("## Part") or ln.startswith("### B.") or ln.startswith("#### Round"):
            sections[i] = ln

    # Simple slicer helper
    def slice_by_headers(start_header_prefix, stop_header_prefixes):
        start = None
        for i, ln in enumerate(lines):
            if ln.startswith(start_header_prefix):
                start = i
                break
        if start is None:
            return ""
        end = len(lines)
        for i in range(start + 1, len(lines)):
            if any(lines[i].startswith(p) for p in stop_header_prefixes):
                end = i
                break
        return "\n".join(lines[start:end])

    out = []
    # Header
    out.append(lines[0])  # title
    out.append("")
    # Basic meta (lines 2-7)
    for ln in lines[1:10]:
        if ln.startswith("- "):
            out.append(ln)

    # A.1 injection
    out.append("")
    out.append(slice_by_headers("### A.1 Injection spec", ["### A.2"]))

    # A.2 GT root cause
    out.append(slice_by_headers("### A.2", ["### A.3"]))

    # A.3 causal graph root_causes/alarm line
    a3 = slice_by_headers("### A.3", ["### A.4"])
    a3_lines = a3.split("\n")
    # Keep only the header + nodes count + root_causes + service propagation section
    keep_a3 = []
    in_prop = False
    for ln in a3_lines:
        if ln.startswith("### A.3"): keep_a3.append(ln); continue
        if ln.startswith("- nodes:"): keep_a3.append(ln); continue
        if ln.startswith("- root_causes:"): keep_a3.append(ln); continue
        if ln.startswith("- alarm_nodes:"): continue  # too long
        if "propagation chain" in ln: in_prop = True
        if in_prop: keep_a3.append(ln)
    out.append("\n".join(keep_a3))

    # A.5b log delta (per-service VOLUME delta is useful)
    out.append(slice_by_headers("### A.5b", ["### A.5c"]))

    # A.6 top 10 anomalous metrics only
    a6 = slice_by_headers("### A.6", ["### A.7"])
    a6_lines = a6.split("\n")
    header_end = 0
    data_rows = []
    for i, ln in enumerate(a6_lines):
        if ln.startswith("|---|"):
            header_end = i + 1
        elif header_end and ln.startswith("|"):
            data_rows.append(ln)
    out.append("\n".join(a6_lines[:header_end] + data_rows[:15]))

    # A.8 first propagation path only
    a8 = slice_by_headers("### A.8", ["### A.9"])
    a8_lines = a8.split("\n")
    keep_a8 = []
    path_count = 0
    for ln in a8_lines:
        if ln.startswith("**Path"):
            path_count += 1
            if path_count > 2:
                break
        keep_a8.append(ln)
    out.append("\n".join(keep_a8))

    # A.9 abnormal nodes + top propagation patterns (trimmed to 10)
    a9 = slice_by_headers("### A.9", ["### A.10"])
    a9_lines = a9.split("\n")
    keep_a9 = []
    in_edges = False
    edge_count = 0
    for ln in a9_lines:
        if "Propagation patterns" in ln:
            in_edges = True
        if in_edges and ln.startswith("|") and not ln.startswith("|---") and "src" not in ln and "---" not in ln:
            edge_count += 1
            if edge_count > 10:
                continue
        keep_a9.append(ln)
    out.append("\n".join(keep_a9))

    # A.10 observability
    out.append(slice_by_headers("### A.10", ["## Part B"]))

    # B.0 prompt
    out.append(slice_by_headers("### B.0", ["### B.1"]))

    # B.1 final answer
    out.append(slice_by_headers("### B.1", ["### B.2"]))

    # B.2 graph metrics
    out.append(slice_by_headers("### B.2", ["### B.3"]))

    # B.3 cost
    out.append(slice_by_headers("### B.3", ["### B.4"]))

    # Extract all think_tool reflections across all rounds
    out.append("")
    out.append("## THINK_TOOL REFLECTIONS (all rounds, condensed)")
    out.append("")
    round_idx = None
    for i, ln in enumerate(lines):
        m = re.match(r"#### Round (\d+)", ln)
        if m:
            round_idx = int(m.group(1))
        if ln.strip() == "- think_tool:":
            # Collect the following indented "  > " block
            j = i + 1
            block = [f"### R{round_idx} think_tool"]
            while j < len(lines) and (lines[j].startswith("  >") or lines[j].startswith("  ") or lines[j].strip() == "" or lines[j].startswith("  {")):
                if lines[j].startswith("  >"):
                    block.append(lines[j][4:])  # strip "  > "
                elif lines[j].startswith("  {"):
                    break  # hit tool args dict; stop
                else:
                    # stop on blank that ends the reflection block
                    if lines[j].strip() == "" and len(block) > 1:
                        break
                j += 1
            out.append("\n".join(block))
            out.append("")

    return "\n".join(out)


if __name__ == "__main__":
    p = Path(sys.argv[1])
    sys.stdout.write(extract(p))
