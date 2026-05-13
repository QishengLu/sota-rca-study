# U3 — EdgeDirectionOrRegionEndpointError  (⚠️ DEPRECATED)

> **⚠️ 本卡片已废弃，请勿使用。**
>
> **重定向到**：[`analysis/4-middleware/v4_dimensions/M3_output_graph_internal_consistency.md`](../../../4-middleware/v4_dimensions/M3_output_graph_internal_consistency.md)

---

## 为什么废弃

本卡片是 2026-04 早期 middleware_rules 三张卡的第三版。v4 元认知中间件设计（[plan](/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md)）明确将本卡片列为**反面教材**：

1. **Trigger 含具体 SQL 模板**：本卡片的边方向检测规则包含 `SELECT ... FROM call_tree ...` 类具体查询指令——违反 v4 原则 1（trigger 不含 SQL 字符串）
2. **Intervention 含拓扑方向词**：使用 "caller"、"callee"、"upstream"、"downstream" 等方向性概念——v4 要求用"另一个服务"、"相关的服务"等认知词代替拓扑方向
3. **依赖 region/endpoint 的专有领域概念**：region-endpoint 是 TrainTicket 场景特有的 HTTP 路径配置概念，无法迁移到其他 RCA 场景

## v4 对应替代

**[M3 Output-Graph Internal Consistency](../../../4-middleware/v4_dimensions/M3_output_graph_internal_consistency.md)** 是本卡片在 v4 元认知维度库中的对应替代。核心差异：

| 层 | 本卡片（废弃）| M3（v4 替代）|
|---|---|---|
| Trigger | 具体 SQL call-tree 查询 + region-endpoint 模板 | reasoning 文本断言（agent 自标某节点为 UNAVAILABLE/RESTARTING 但未列入 root_causes）— 不依赖结构化 graph，所有 framework 通用 |
| Intervention | "caller 应改为 callee" 类方向性指引 | 开放反问："被你自己标问题的节点没列入根因——这种判断的支撑证据是什么？" |
| 方向词 | upstream / downstream / caller / callee 拓扑方向 | "相关的服务"、"节点本身"等认知词 |
| 泛化能力 | 仅 TrainTicket HTTP 配置有效 | 任何 RCA 任务通用；基于 reasoning 文本而非图结构 |

## 仅作历史参考

本 git 仓库提交历史里可查看 2026-04-17 版本的完整原 U3 卡片（含具体 SQL 模板 / region-endpoint 配置词），作为 **v4 避免的低层化反面教材**参照。不再在本文件中保留原内容，以免后来的读者误把旧卡当作当前指南。

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| original | 2026-04-17 | 初版（含 SQL 模板 / 拓扑方向词 / region-endpoint 概念）|
| deprecated | 2026-04-22 | 废弃并重定向到 v4 M3（D-8 阶段）|
