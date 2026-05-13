"""Loader for v4 M-card content (analysis/4-middleware/v4_dimensions/M*.md).

Extracts the fields opus-4.7 needs for each dimension: short tagline,
trigger abstract, intervention pattern, conflict rules. Cards are read once
on init and cached.

Falls back to hard-coded summaries if the cards directory is missing
(e.g. running outside the SOTA-agents repo).
"""

from __future__ import annotations

import re
from pathlib import Path


# Hard-coded summaries — always available, used as fallback or override.
# Source: analysis/4-middleware/v4_dimensions/<id>_*.md (frozen 2026-04-22).
HARDCODED_SUMMARIES: dict[str, dict[str, str]] = {
    "M1": {
        "name": "Loudness-Anchor Self-check",
        "tagline": "排名靠前的候选不一定是故障来源——也可能是因为别的原因放大了它的错误。",
        "trigger": (
            "agent 即将 commit + 最近 ≥2 次 ranking 类查询 (error_rate_scan, latency_ranking, "
            "throughput_compare, metric_scan) + draft_root_cause 出现在最近 ranking top-3 中"
        ),
        "intervention_template": (
            "你最近几轮在做排名类查询，准备 commit 排名靠前的那个候选。"
            "排名靠前不一定就是故障来源——也可能是因为别的原因放大了它的错误。"
            "你能在确认前先反过来问一下：如果不是它，会是什么？"
            "哪些服务可能根本没出现在你的排名里？"
        ),
        "conflict": "M1 vs M8 同时命中时 M1 优先；M1 vs M7 经常同时命中（M1 主问 + M7 次问，仅当 M7 真的命中）",
    },
    "M2": {
        "name": "Chronic-Noise Skepticism",
        "tagline": "常年异常 ≠ 当前事故的根因。",
        "trigger": (
            "draft_root_cause 是某个共享/基础设施类服务 + agent 未做 baseline_contrast，"
            "或 reasoning 中含 'shared/database/queue/gateway' 类描述"
        ),
        "intervention_template": (
            "你的候选是一个共享/基础设施类服务。在确认前先问一下："
            "这种异常是否在正常时段也存在？如果在 baseline 中也常见，那它更像是常态噪声"
            "而不是当前事故的来源。你做过正常 vs 异常时段的对照吗？"
        ),
        "conflict": "M2 vs M6（baseline 缺）经常同时命中——M2 作主问时 M6 退为次问",
    },
    "M3": {
        "name": "Output-Graph Internal Consistency",
        "tagline": "你输出图里的方向和实际调用拓扑要自洽。",
        "trigger": (
            "agent 在 reasoning 文本中断言 'X 调用 Y' 或 'X 影响 Y' 但 trajectory 中没有"
            "相应 trace_follow / call_tree_build 证据；或 draft graph 内某节点既被列为 RC "
            "又同时被标 UNAVAILABLE/RESTARTING 但没在 root_causes 列表中"
        ),
        "intervention_template": (
            "你在推理中断言了 X 影响 Y 的方向。在确定前先核对一下："
            "你的调用关系断言有 trace 数据支撑吗（service_trace_scan / call_tree_build）？"
            "还是只是从 error 时间顺序推断的？错误时间相近不等于因果方向已确定。"
        ),
        "conflict": "M3 在 thinkdepthai 走 reasoning 文本 trigger（不依赖结构化 graph）",
    },
    "M4": {
        "name": "Sibling-Disambiguation",
        "tagline": "相似服务名容易认错；候选有相似兄弟时要做字符串相似度核对。",
        "trigger": (
            "draft_root_cause 与 observed_services 中至少一个其他服务在 Jaro-Winkler 相似度 > 0.85"
        ),
        "intervention_template": (
            "你的候选服务名和 trajectory 中另一个服务名非常相似。"
            "在最终提交前请直接核对一下，别错把相似名当成同一个服务。"
        ),
        "conflict": "通常和 M1 / M5 不冲突",
    },
    "M5": {
        "name": "Silence ≠ Health",
        "tagline": "某服务在排名/数据里不出现，不一定就健康——也可能是它停了。",
        "trigger": (
            "agent reasoning 中含 'X is healthy / X 没有问题 / X 没出现异常' 类断言，"
            "或 agent 排除某服务的理由是 'no data found' 而非 'positive evidence of health'"
        ),
        "intervention_template": (
            "你似乎根据某服务'没出现在异常数据里'判定它健康。"
            "但'没数据'有多种可能：这服务可能根本不在请求路径上（最常见），"
            "也可能它已经死掉/停止响应所以才不报数据。"
            "你能列出至少一条这服务'确实健康'的正向证据吗（比如 metrics 正常、日志正常）？"
        ),
        "conflict": "thinkdepthai-qwen 上 U5 占 16.2%，是该 framework 独特高发维度",
    },
    "M6": {
        "name": "Baseline-Contrast Reflex",
        "tagline": "如果你只看了异常时段数据，先反问：正常时段同样的数据长什么样？",
        "trigger": (
            "round_count >= 检查阈值 + baseline_intent_count == 0 + agent 已查 ≥10 次"
            "abnormal_* 类 SQL"
        ),
        "intervention_template": (
            "你查了大量异常时段数据，但还没对照过正常时段。有没有可能你看到的'异常'本身"
            "在正常情况下也存在？在 commit 前先做一次 baseline 对照吧。"
        ),
        "conflict": "M6 vs M2 — baseline 缺失时往往先抓住 noisy candidate；M6 先暴露问题",
    },
    "M7": {
        "name": "Layer-Coverage Reflex",
        "tagline": "你定位到候选后，运行时层（容器/JVM/网络/k8s/db）的指标查过吗？",
        "trigger": (
            "draft_root_cause 已存在 + runtime_layer_intent_count == 0 "
            "(没碰任何 container/jvm/network/k8s/db 指标)"
        ),
        "intervention_template": (
            "你定位到了候选服务，但运行时层指标还没查过。"
            "在 commit 前看一眼候选服务的 JVM / 容器 / 网络指标——"
            "可能正常应用层日志看不出原因，但运行时层有明确异常。"
        ),
        "conflict": "M7 经常作 M1 主问的次问",
    },
    "M8": {
        "name": "Hypothesis-Counterfactual",
        "tagline": "Commit 前做一次反例隔离：抠掉它，其他异常会不会自动消失？",
        "trigger": (
            "draft_root_cause 已存在 + reasoning 中没有 'if X were healthy' / "
            "'抠掉 X' / counterfactual 类语言"
        ),
        "intervention_template": (
            "在最终提交前做一次反例隔离：如果你的候选 X 完全健康，"
            "其他你看到的异常还会发生吗？如果会，那 X 可能只是受连累者，不是源头；"
            "如果不会，那 X 的 RC 嫌疑更可信。"
        ),
        "conflict": "M8 vs M1 — M1 优先（M8 退次问）",
    },
    "M9": {
        "name": "Investigation Stagnation",
        "tagline": "你已经查了同类查询很多次，看到一样的东西——是时候换个角度。",
        "trigger": (
            "round_count >= 中期阈值 + 最近 8 round 中 ≥6 round 是同一类 intent 重复"
        ),
        "intervention_template": (
            "你最近几轮一直在重复同一类查询，得到的信息没什么新增。"
            "考虑换个角度——比如看不同的数据模态（traces vs logs vs metrics）"
            "或者先做 baseline 对照看看你抓的'异常'在正常时段是不是也存在。"
        ),
        "conflict": "M9 vs M10 互斥（重复探查 → round 多 → 不会 premature）",
    },
    "M10": {
        "name": "Premature Commitment",
        "tagline": "在大部分成功 case 才刚开始的时间点就要 commit，可能查得太浅。",
        "trigger": (
            "agent 即将 commit (no tool_calls) + round_count < framework_correct_P25 + "
            "intent 多样性低 (<3 个不同的 intent type)"
        ),
        "intervention_template": (
            "你看上去要在这里收尾，但和这个 framework 上'成功 case'的典型推理深度比，"
            "你的查询面相当窄。在最终 commit 前可以再做一次：(a) 你看过哪些数据模态，"
            "(b) 你的候选有 baseline 对比吗？两个问题都满足后再下结论也不迟。"
        ),
        "conflict": "M10 vs M9 互斥",
    },
}


# Optional fields like ``M3 trigger conditions for graph orphans`` may live in
# the markdown card; we extract them lazily.

_TAGLINE_RE = re.compile(r"^\s*\*\*?(?:速查表|tagline|描述)\*\*?:?\s*(.+?)$", re.MULTILINE | re.IGNORECASE)


class DimensionCardLibrary:
    """Lookup of M-card summaries usable inside opus-4.7 prompts."""

    def __init__(self, cards_dir: Path | None = None):
        self.cards_dir = cards_dir
        self._cache: dict[str, dict[str, str]] = dict(HARDCODED_SUMMARIES)
        # If a cards directory is supplied, attempt to override summaries
        # with the latest authoritative content. Failures fall back silently.
        if cards_dir is not None and cards_dir.is_dir():
            self._load_from_disk(cards_dir)

    def _load_from_disk(self, cards_dir: Path) -> None:
        for path in cards_dir.glob("M*_*.md"):
            stem = path.stem  # e.g. "M1_loudness_anchor_selfcheck"
            mid = stem.split("_", 1)[0]
            if mid not in self._cache:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            # We do NOT overwrite the curated tagline / template here —
            # that text is more carefully tuned for the prompt budget.
            # We just stash the raw card so a downstream caller may include
            # extra detail if desired.
            self._cache[mid]["raw_card_excerpt"] = text[:2500]

    def get(self, mid: str) -> dict[str, str]:
        return dict(self._cache.get(mid, {}))

    def render_for_prompt(self, mid: str, role: str = "primary") -> str:
        """Render a single dimension into the L2+L3 system prompt.

        role: "primary" (full template) or "secondary" (tagline only).
        """
        d = self.get(mid)
        if not d:
            return f"{mid}: (unknown dimension)"
        head = f"{mid} ({d.get('name', '?')}): {d.get('tagline', '')}"
        if role == "secondary":
            return head
        return (
            f"{head}\n"
            f"  trigger: {d.get('trigger', '?')}\n"
            f"  template: {d.get('intervention_template', '?')}\n"
            f"  conflict: {d.get('conflict', '?')}"
        )
