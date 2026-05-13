#!/bin/bash
# Quick case summary printer — extracts the high-signal sections from a dossier
# for batch-efficient analysis reading.
# Usage: ./case_summary.sh <case_idx>

CASE_IDX=$1
DOSSIER="/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/aiq-qwen3.5-plus/v1/dossiers/case_${CASE_IDX}.md"

if [ ! -f "$DOSSIER" ]; then
    echo "Dossier not found: $DOSSIER"
    exit 1
fi

echo "================================================================"
echo "CASE $CASE_IDX — compact summary"
echo "================================================================"
# Title line + metadata
head -8 "$DOSSIER"
echo ""
# A.1 injection spec
echo "--- A.1 Injection ---"
awk '/^### A.1 Injection spec/,/^### A.2/' "$DOSSIER" | head -40
# A.2 GT root causes
echo "--- A.2 GT root causes ---"
awk '/^### A.2 Ground-truth/,/^### A.3/' "$DOSSIER"
# A.3 root_causes field + service edges only (skip big node table)
echo "--- A.3 GT causal graph (root_causes + service edges) ---"
grep -E "^- root_causes:|^- alarm_nodes:|^\*\*Service-level|^- \`ts-" "$DOSSIER" | head -40
# A.5b log delta (error delta only)
echo "--- A.5b log delta (ERROR) ---"
awk '/^\*\*Per-service ERROR count delta/,/^\*\*Per-service log VOLUME/' "$DOSSIER" | head -30
# A.6 anomalous metrics (top 10)
echo "--- A.6 anomalous metrics (z>=3, top 10) ---"
awk '/^### A.6/,/^### A.7/' "$DOSSIER" | head -15
# A.7 k8s
echo "--- A.7 K8s state ---"
awk '/^### A.7/,/^### A.8/' "$DOSSIER"
# B.1 final answer
echo "--- B.1 Final answer ---"
awk '/^### B.1 Final answer/,/^### B.2/' "$DOSSIER" | head -30
# B.2 graph metrics
echo "--- B.2 Graph metrics diagnostic ---"
awk '/^### B.2/,/^### B.3/' "$DOSSIER"
# B.3 cost
echo "--- B.3 Cost signature ---"
awk '/^### B.3/,/^### B.4/' "$DOSSIER"
# B.4 pipeline summary
echo "--- B.4 Pipeline stages ---"
awk '/^### B.4/,/^### B.5/' "$DOSSIER"
# B.5 terminator conclusions (first 10 lines of each)
echo "--- B.5 Terminators (abbrev: title + first 30 lines) ---"
awk '/^#### Terminator/,/^### B.6/' "$DOSSIER" | awk '/^#### Terminator/{p=1; c=0} p{print; c++; if(c==30){p=0; print "..."}}'
