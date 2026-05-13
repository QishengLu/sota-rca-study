"""Generate weekly-report (zhoubao) friendly charts for MW analysis.

Outputs to zhoubao/<date>/:
  02_mw_item_helped_vs_fired.png  - horizontal bar chart, MW item 承重次数 vs 触发次数
  03_intervention_coverage.png    - stacked bar of intervention coverage by transition
  04_failure_modes_pie.png        - pie chart of wrong→wrong failure modes

Run: uv run python scripts/mw_vs_womw_zhoubao_charts.py [YYYY-MM-DD]
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# Register CJK font so 中文 labels render correctly
for path in (
    "/home/nn/.local/share/fonts/LXGWWenKai-Regular.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
):
    if os.path.exists(path):
        font_manager.fontManager.addfont(path)
        break

plt.rcParams["font.sans-serif"] = ["LXGW WenKai", "WenQuanYi Zen Hei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

CACHE_DIR = Path("RCAgentEval/scripts/mw_vs_womw_cache")
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-04-14"
OUT_DIR = Path(f"zhoubao/{DATE}")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Hand-attributed load-bearing case lists from analysis/4-middleware/MW-vs-w_o-MW.md C.4
LOAD_BEARING = {
    "B3": ["99", "315", "1114", "2092", "2682", "3393", "4055", "4258", "4707"],
    "B5": ["1846", "1880", "1948", "2285", "2716", "3278"],
    "M2": ["2512", "3059", "3125", "3716", "4032"],
    "B1": ["2700", "2713", "4151", "4789", "4893"],
    "M1": ["807", "3955"],
    "B2": ["3524"],
}


def load_cache():
    cases = []
    for f in sorted(CACHE_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        cases.append(json.loads(f.read_text()))
    return cases


def chart_2_mw_item_helped_vs_fired(cases):
    """Horizontal bar: total fires vs load-bearing helps for each MW item."""
    fires = defaultdict(int)
    for o in cases:
        for a in o["mw"]["advisors"]:
            fires[a["deficiency"]] += 1

    items = ["B3", "B5", "M2", "B1", "M1", "B2"]
    helped = [len(LOAD_BEARING[k]) for k in items]
    fired = [fires[k] for k in items]
    rates = [h / f * 100 if f > 0 else 0 for h, f in zip(helped, fired)]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    y = list(range(len(items)))
    width = 0.4
    b1 = ax.barh([i + width / 2 for i in y], fired, width,
                 label="触发总次数", color="#A0A0A0")
    b2 = ax.barh([i - width / 2 for i in y], helped, width,
                 label="承重次数 (wrong→correct)", color="#54A24B")

    for i, (h, f, r) in enumerate(zip(helped, fired, rates)):
        ax.text(f + 0.5, i + width / 2, f"{f}", va="center", fontsize=9)
        ax.text(h + 0.5, i - width / 2, f"{h} ({r:.0f}%)", va="center",
                fontsize=9, color="#2A6B33")

    ax.set_yticks(y)
    ax.set_yticklabels([
        f"B3 缺基线", f"B5 上游盲区", f"M2 共享组件", f"B1 调查停滞",
        f"M1 缺因果方向", f"B2 模态不全",
    ])
    ax.invert_yaxis()
    ax.set_xlabel("次数 (105 case 全样本)")
    ax.set_title("MW 元认知条目：触发次数 vs 承重次数（按承重率排序）", fontsize=12)
    ax.legend(loc="lower right", fontsize=10)
    ax.set_xlim(0, max(fired) + 8)
    ax.grid(axis="x", linestyle=":", alpha=0.5)

    plt.tight_layout()
    out = OUT_DIR / "02_mw_item_helped_vs_fired.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


def chart_3_intervention_coverage(cases):
    """Stacked bar: P+C / C-only-back_to_tools / C-only-rewrite per transition."""
    counts = {
        "wrong→correct": {"P+C": 0, "C-back_to_tools": 0, "C-rewrite": 0},
        "wrong→wrong": {"P+C": 0, "C-back_to_tools": 0, "C-rewrite": 0},
    }
    for o in cases:
        t = o["transition"]
        if t not in counts:
            continue
        has_proc = bool(o["mw"]["advisors"])
        cc = o["mw"]["conclusion_check"]
        if has_proc:
            counts[t]["P+C"] += 1
        elif cc.get("mode") == "back_to_tools":
            counts[t]["C-back_to_tools"] += 1
        else:
            counts[t]["C-rewrite"] += 1

    labels = list(counts.keys())
    pc = [counts[l]["P+C"] for l in labels]
    bt = [counts[l]["C-back_to_tools"] for l in labels]
    rw = [counts[l]["C-rewrite"] for l in labels]

    fig, ax = plt.subplots(figsize=(8, 5))
    x = list(range(len(labels)))
    b1 = ax.bar(x, pc, label="Process+Conclusion 双触发", color="#54A24B")
    b2 = ax.bar(x, bt, bottom=pc, label="仅 Conclusion (back_to_tools)", color="#4C78A8")
    b3 = ax.bar(x, rw, bottom=[a + b for a, b in zip(pc, bt)],
                label="仅 Conclusion (rewrite)", color="#F58518")

    for i in range(len(labels)):
        total = pc[i] + bt[i] + rw[i]
        ax.text(i, total + 1, f"{total}", ha="center", fontsize=10, fontweight="bold")
        if pc[i] > 0:
            ax.text(i, pc[i] / 2, f"{pc[i]}", ha="center", va="center",
                    color="white", fontsize=10)
        if bt[i] > 0:
            ax.text(i, pc[i] + bt[i] / 2, f"{bt[i]}", ha="center", va="center",
                    color="white", fontsize=10)
        if rw[i] > 0:
            ax.text(i, pc[i] + bt[i] + rw[i] / 2, f"{rw[i]}", ha="center", va="center",
                    color="white", fontsize=10)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Case 数")
    ax.set_title("MW 干预覆盖：105 个 case 按 transition × 干预触发类型", fontsize=12)
    ax.legend(loc="upper right", fontsize=9)
    ax.set_ylim(0, max(pc[i] + bt[i] + rw[i] for i in range(2)) + 8)

    plt.tight_layout()
    out = OUT_DIR / "03_intervention_coverage.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


def chart_4_failure_modes_pie(cases):
    """Pie of wrong→wrong failure mode categories."""
    # From hand-counted batch summaries:
    #   process-silent (qpf<37) + conclusion no effect: case lists from each batch
    #   MW fired but agent stuck (R6/R5/R7): hand counted
    #   MW shifted to another wrong answer: hand counted
    silent_cases = {  # qpf<37 + conclusion no effect
        "156", "281", "283", "339", "860", "1140", "1143", "1254", "1421",
        "2130", "2258", "2598", "2715", "2836", "3219", "3222", "3592",
        "3622", "4081", "4363", "4617", "4732"
    }
    stuck_cases = {  # MW fired but agent stuck
        "247", "579", "804", "1218", "1394", "1459", "1814", "1917", "2211",
        "2253", "2598", "3776", "4353", "4375", "4463", "4758", "1495", "3878"
    }
    shifted_cases = {  # MW shifted to another wrong answer
        "33", "323", "341", "755", "1195", "1934", "2231", "2390", "2988",
        "3605", "3868", "3920", "4229", "4510"
    }
    # Note: 2598 appears in both silent and stuck — it's actually MW fired w/ B3+M1 but qpf=60; correct bucket is stuck

    # Recount from cache to be authoritative
    silent, stuck, shifted, other = 0, 0, 0, 0
    for o in cases:
        if o["transition"] != "wrong→wrong":
            continue
        di = str(o["dataset_index"])
        if di in silent_cases and not o["mw"]["advisors"]:
            silent += 1
        elif di in shifted_cases:
            shifted += 1
        elif di in stuck_cases:
            stuck += 1
        else:
            other += 1

    labels = [
        f"qpf<37 早期收敛\nMW 没机会触发",
        f"MW 触发但 agent\n死锁原答案",
        f"MW 推到另一个\n错答案 (misdirected)",
    ]
    sizes = [silent, stuck, shifted]
    colors = ["#A0A0A0", "#E45756", "#F58518"]

    fig, ax = plt.subplots(figsize=(8.5, 6))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors,
        autopct=lambda pct: f"{int(round(pct * sum(sizes) / 100))} ({pct:.0f}%)",
        startangle=90, textprops={"fontsize": 10},
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontweight("bold")
    ax.set_title(
        f"56 个 wrong→wrong case 的失败模式分布\n（不含 {other} 个边界 case）",
        fontsize=12
    )
    plt.tight_layout()
    out = OUT_DIR / "04_failure_modes_pie.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}  (sum={sum(sizes)}, edge={other})")


def main():
    cases = load_cache()
    print(f"loaded {len(cases)} cases for date={DATE}")
    chart_2_mw_item_helped_vs_fired(cases)
    chart_3_intervention_coverage(cases)
    chart_4_failure_modes_pie(cases)
    print(f"\nAll charts written to {OUT_DIR}")


if __name__ == "__main__":
    main()
