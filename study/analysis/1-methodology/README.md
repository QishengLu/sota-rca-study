# 1. Methodology — 方法论与参考资料

定义评测框架的"测什么、怎么测"——分类法、行为意图体系、agent 上下文压缩分析、底层数据格式参考。这一层是项目内最稳定的部分，不随实验数据变化而变化。

## 文件清单

| 文件 | 用途 |
|---|---|
| [intention_category.md](intention_category.md) | **19 类排障意图分类体系**——agent 行为分类的核心定义，按 5 阶段（triage / trace_investigate / log_investigate / metric_diagnose / baseline）聚合。RCAgentEval 的 Markov / N-gram 分析全部基于这套定义。 |
| [sql_patterns.md](sql_patterns.md) | troubleshooting intent 集（SQL 模式层面）——和 19 意图分类配套使用，给出每类意图的典型 SQL pattern。 |
| [context_analysis.md](context_analysis.md) | Agent context compression 分析——研究 agent 在长上下文里如何压缩历史信息以及压缩对推理质量的影响。 |
| [parquet.md](parquet.md) | TrainTicket parquet 数据表格式说明——logs/traces/metrics 三大类 parquet 的字段定义、类型、时间戳含义。所有 agent 必须依赖这份文档查询。 |
| [agent_prompt_example.md](agent_prompt_example.md) | Agent 完整输入消息示例（case 14929 / ts-consign-service）——展示一个 case 注入 agent 时的完整 system + user prompt 长什么样。 |
| [inspect.md](inspect.md) | 实验运行与监控手册——`launch_eval.sh` / tmux / 断点恢复 / DB 进度查询的实操指南。 |
