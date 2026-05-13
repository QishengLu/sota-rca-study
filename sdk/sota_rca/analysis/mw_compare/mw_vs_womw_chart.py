"""Chart A: fault-category accuracy bar chart for MW vs w/o MW analysis.

Three bars per category:
  - baseline-500: full baseline accuracy
  - baseline-105: baseline accuracy restricted to MW subset (apples-to-apples; should be 0%)
  - MW-105: MW accuracy on the same 105 cases

Output: zhoubao/<DATE>/01_accuracy_by_fault.png

Run: uv run python scripts/mw_vs_womw_chart.py [YYYY-MM-DD]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

for path in (
    str(Path.home() / ".local" / "share" / "fonts" / "LXGWWenKai-Regular.ttf"),
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
):
    if os.path.exists(path):
        font_manager.fontManager.addfont(path)
        break
plt.rcParams["font.sans-serif"] = ["LXGW WenKai", "WenQuanYi Zen Hei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
from sqlalchemy import create_engine, text

os.environ.setdefault(
    "UTU_DB_URL",
    "postgresql://postgres:postgres@localhost:5433/SOTA-Agents",
)

BASELINE_EXP = "thinkdepthai-qwen3.5-plus"
MW_EXP = "thinkdepthai-qwen3.5-plus-mw-v3"
CACHE_DIR = Path("RCAgentEval/scripts/mw_vs_womw_cache")
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-04-14"
OUT_DIR = Path(f"zhoubao/{DATE}")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT = OUT_DIR / "01_accuracy_by_fault.png"

CATEGORIES = ["HTTPFault", "NetworkChaos", "JVMChaos", "PodChaos"]


def main() -> None:
    engine = create_engine(os.environ["UTU_DB_URL"])

    # baseline-500: by fault category
    base500 = {c: {"total": 0, "correct": 0} for c in CATEGORIES}
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT meta->'difficulty'->>'fault_category' AS cat, correct
            FROM evaluation_data
            WHERE exp_id = :exp AND stage = 'judged'
        """), {"exp": BASELINE_EXP}).fetchall()
    for cat, correct in rows:
        if cat in base500:
            base500[cat]["total"] += 1
            if correct:
                base500[cat]["correct"] += 1

    # baseline-105 and mw-105 from cache (with NULL-fallback applied)
    base105 = {c: {"total": 0, "correct": 0} for c in CATEGORIES}
    mw105 = {c: {"total": 0, "correct": 0} for c in CATEGORIES}
    for f in sorted(CACHE_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        o = json.loads(f.read_text())
        cat = o.get("fault_category")
        if cat not in CATEGORIES:
            # apply source-name fallback
            src = (o.get("source") or "").lower()
            if any(k in src for k in ("loss", "corrupt", "delay", "partition", "bandwidth", "dns")):
                cat = "NetworkChaos"
            elif "stress" in src:
                cat = "JVMChaos"
            else:
                continue
        base105[cat]["total"] += 1
        if o["no_mw"]["correct"]:
            base105[cat]["correct"] += 1
        mw105[cat]["total"] += 1
        if o["mw"]["correct"]:
            mw105[cat]["correct"] += 1

    # Build chart
    fig, ax = plt.subplots(figsize=(11, 6.5))
    x = list(range(len(CATEGORIES)))
    width = 0.27

    def acc(d, c):
        t = d[c]["total"]
        return (d[c]["correct"] / t * 100) if t > 0 else 0

    base500_pct = [acc(base500, c) for c in CATEGORIES]
    base105_pct = [acc(base105, c) for c in CATEGORIES]
    mw105_pct = [acc(mw105, c) for c in CATEGORIES]

    b1 = ax.bar([i - width for i in x], base500_pct, width,
                label=f"baseline-500 (n=500)", color="#4C78A8")
    b2 = ax.bar(x, base105_pct, width,
                label=f"baseline-105 (apples-to-apples, n=105)", color="#F58518")
    b3 = ax.bar([i + width for i in x], mw105_pct, width,
                label=f"MW-105 (n=105)", color="#54A24B")

    # Annotate counts
    for bar, data, total_dict in [(b1, base500, base500), (b2, base105, base105), (b3, mw105, mw105)]:
        for i, rect in enumerate(bar):
            cat = CATEGORIES[i]
            n = total_dict[cat]["correct"]
            t = total_dict[cat]["total"]
            ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 1.0,
                    f"{n}/{t}", ha="center", va="bottom", fontsize=8.5)

    ax.set_xticks(x)
    ax.set_xticklabels(CATEGORIES)
    ax.set_ylabel("Accuracy (%)")
    ax.set_title(
        "thinkdepthai qwen3.5-plus: MW vs no-MW accuracy by fault category\n"
        "(baseline-105 ≈ 0% by construction — MW set sampled from baseline failures)",
        fontsize=11
    )
    ax.set_ylim(0, 100)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", linestyle=":", alpha=0.5)

    # Footer summary
    base500_total = sum(d["total"] for d in base500.values())
    base500_correct = sum(d["correct"] for d in base500.values())
    mw_total = sum(d["total"] for d in mw105.values())
    mw_correct = sum(d["correct"] for d in mw105.values())
    fig.text(0.5, -0.02,
             f"Overall: baseline-500 {base500_correct}/{base500_total} = {base500_correct/base500_total*100:.1f}% · "
             f"MW-105 {mw_correct}/{mw_total} = {mw_correct/mw_total*100:.1f}% · "
             f"49 wrong→correct, 0 regressions, 56 wrong→wrong",
             ha="center", fontsize=9, style="italic", color="#444")

    plt.tight_layout()
    plt.savefig(OUTPUT, dpi=150, bbox_inches="tight")
    print(f"Wrote {OUTPUT}")

    # Also print numbers
    print("\nBar chart data:")
    for c in CATEGORIES:
        print(f"  {c}: baseline-500={base500_pct[c == c and CATEGORIES.index(c)]:.1f}% "
              f"({base500[c]['correct']}/{base500[c]['total']}), "
              f"baseline-105={base105_pct[CATEGORIES.index(c)]:.1f}% "
              f"({base105[c]['correct']}/{base105[c]['total']}), "
              f"MW-105={mw105_pct[CATEGORIES.index(c)]:.1f}% "
              f"({mw105[c]['correct']}/{mw105[c]['total']})")


if __name__ == "__main__":
    main()
