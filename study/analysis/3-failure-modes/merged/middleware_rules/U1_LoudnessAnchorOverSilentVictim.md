# U1 — LoudnessAnchorOverSilentVictim  (⚠️ DEPRECATED)

> **⚠️ 本卡片已废弃，请勿使用。**
>
> **重定向到**：[`analysis/4-middleware/v4_dimensions/M1_loudness_anchor_selfcheck.md`](../../../4-middleware/v4_dimensions/M1_loudness_anchor_selfcheck.md)

---

## 为什么废弃

本卡片是 2026-04 早期 middleware_rules 三张卡的第一版，作为失败分析产物提供给 middleware 设计参考。后续 v4 元认知中间件设计（[plan](/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md)）明确将本卡片列为**反面教材**——它违反了 v4 的元认知设计原则：

1. **Trigger 含低层操作信号**：引用了具体 SQL 模板（`SELECT service_name, COUNT(*) FROM abnormal_logs ORDER BY ...`）和具体服务名（`ts-rabbitmq`、`ts-ui-dashboard`）——v4 要求 trigger 信号必须是框架无关的 intent 分类 + 结构属性
2. **Intervention 命令式 + 泄露答案**：写了"MANDATORY: 跑 `<具体 SQL>`"类指令，等于把答案分步喂给 agent，绕过推理过程
3. **Vocabulary 含 GT 方向概念**：使用"silent victim"、"downstream"、"upstream caller"等方向性概念——这些是 GT 概念，agent 在 RCA 任务里不应该提前知道；且 qwen / sonnet 在输出中用词不一致，会引入歧义
4. **无法泛化到新数据集**：SQL 模板 / 服务名硬编码让规则只在 RCABench 数据集上有效，换任何 RCA 任务都得重写

## v4 对应替代

**[M1 Loudness-Anchor Self-check](../../../4-middleware/v4_dimensions/M1_loudness_anchor_selfcheck.md)** 是本卡片在 v4 元认知维度库中的对应替代。核心差异：

| 层 | 本卡片（废弃） | M1（v4 替代） |
|---|---|---|
| Trigger | 具体 SQL 模板 + 服务名硬编码 + `chronic_noise_carriers` 等 GT-derived 量 | 19 类抽象 intent + 候选 RC 是否为 ranking SQL top 行（都是运行时可观察、不依赖 GT）|
| Intervention | 命令式 SQL："MANDATORY 跑这条 SQL 然后 UNION 对比" | 元认知反问："排名靠前不一定是故障来源——也可能是别的原因放大了它的错误。你能反过来问：如果不是它，会是什么？" |
| 方向词 | "silent victim"、"downstream" 等拓扑方向 | "另一个候选"、"另一种可能性"（认知词代替拓扑方向）|
| 泛化能力 | 仅 RCABench 有效 | 任何 RCA 任务通用 |

## 仅作历史参考：本卡片旧内容

本 git 仓库提交历史里可查看 2026-04-17 版本的完整原 U1 卡片（含具体 SQL 模板 / 服务名清单），作为 **v4 避免的低层化反面教材**参照。不再在本文件中保留原内容，以免后来的读者误把旧卡当作当前指南。

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| original | 2026-04-17 | 初版（含 SQL 模板 / 服务名硬编码）|
| deprecated | 2026-04-22 | 废弃并重定向到 v4 M1（D-8 阶段）|
