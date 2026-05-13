# U2 — ChronicAmbientNoiseAnchor  (⚠️ DEPRECATED)

> **⚠️ 本卡片已废弃，请勿使用。**
>
> **重定向到**：[`analysis/4-middleware/v4_dimensions/M2_chronic_noise_skepticism.md`](../../../4-middleware/v4_dimensions/M2_chronic_noise_skepticism.md)

---

## 为什么废弃

本卡片是 2026-04 早期 middleware_rules 三张卡的第二版。v4 元认知中间件设计（[plan](/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md)）明确将本卡片列为**反面教材**：

1. **Trigger 硬编码噪声载体服务名**：本卡片列出了具体的"chronic noise carriers"服务名（`ts-rabbitmq` 等）作为检测依据——这是领域知识，不能写进 trigger
2. **Intervention 含答案提示**：建议让 agent "先查 normal_logs 看 `ts-rabbitmq` 在正常时段是否也有 DNS 错误"——直接告诉 agent 去查哪个服务
3. **依赖 GT-derived 的 chronic_noise_carriers 列表**：该列表是 parquet-derived 的事后离线标注，agent 在 RCA 任务里不应提前知道

## v4 对应替代

**[M2 Chronic-Noise Skepticism](../../../4-middleware/v4_dimensions/M2_chronic_noise_skepticism.md)** 是本卡片在 v4 元认知维度库中的对应替代。核心差异：

| 层 | 本卡片（废弃）| M2（v4 替代）|
|---|---|---|
| Trigger | `chronic_noise_carriers` 硬编码列表 + 具体服务名 + 具体错误字串 | `baseline_contrast` intent 全程为 0 + 即将 commit（抽象意图计数，无 GT）|
| Intervention | "查 normal_logs 看是否也有 DNS 错误" 具体指引 | 开放反问："你看到的错误，有没有可能在没有故障时也是这样的？" |
| 泛化能力 | 仅 TrainTicket 环境有效 | 任何 RCA 任务通用 |

## 仅作历史参考

本 git 仓库提交历史里可查看 2026-04-17 版本的完整原 U2 卡片（含服务名清单 / DNS 错误字串 / normal_logs 具体查询），作为 **v4 避免的低层化反面教材**参照。不再在本文件中保留原内容，以免后来的读者误把旧卡当作当前指南。

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| original | 2026-04-17 | 初版（含 noise carriers 服务名硬编码 / DNS 错误字串）|
| deprecated | 2026-04-22 | 废弃并重定向到 v4 M2（D-8 阶段）|
