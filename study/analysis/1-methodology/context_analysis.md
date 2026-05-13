# Agent Context Compression Analysis

> 分析 8 个 RCA Agent 原生框架中的上下文压缩能力，评估其对评测质量的潜在影响。

---

## Overview

| Agent | 框架 | 压缩类型 | 触发条件 | System Prompt 安全 |
|-------|------|---------|---------|-------------------|
| **Deep_Research** | LangGraph | 图节点压缩 | 每次执行结束 | ✅ 安全 |
| **DeerFlow v2** | LangGraph + Middleware | 中间件摘要 | token 数接近上限 | ✅ 安全（双重冗余） |
| **Auto-Deep-Research** | MetaChain + litellm | 后处理压缩 | 执行结束后 | ✅ 安全 |
| **TaskWeaver** | Microsoft TaskWeaver | 滚动摘要（最完善） | 每 5 轮自动触发 | ✅ 安全 |
| **DeepResearchAgent** | ToolCallingAgent v2.0 | 仅 JSON 修复 | 输出格式错误时 | N/A |
| **AIQ** | NVIDIA AIRA + LangGraph | 仅循环限制 | MAX_TOOL_ROUNDS=15 | N/A |
| **OpenRCA** | ReAct + IPython | 仅循环限制 | max_step=20, max_turn=5 | N/A |
| **mABC** | Multi-Agent Debate | 仅循环限制 | MAX_REACT_STEPS=8 | N/A |

**分类**：
- **有真正压缩能力**：Deep_Research, DeerFlow v2, Auto-Deep-Research, TaskWeaver
- **无压缩，靠轮次限制**：DeepResearchAgent, AIQ, OpenRCA, mABC

---

## 详细分析

### 1. Deep_Research (thinkdepthai)

**压缩机制**：LangGraph `compress_research` 节点

- **实现文件**：`Deep_Research/agent_runner.py` (lines 101-122)
- **触发时机**：调查阶段结束后，作为 LangGraph 图中的独立节点执行
- **压缩范围**：`state["researcher_messages"]`（全部对话历史）
- **压缩方式**：
  - 过滤掉 `think_tool` 结果，只保留实质性工具输出 + AI 响应
  - 使用独立的 `compress_research_system_prompt` 和 `compress_research_human_message` 调用 LLM
  - 输出写入 `state["compressed_research"]` 字段
  - LLM 调用参数：`max_tokens=32000`
- **System Prompt 安全性**：✅ 安全
  - System prompt 每次 LLM 调用时重新注入为 `SystemMessage`，不在 state 中
  - 压缩节点只处理 `researcher_messages`，不接触 system prompt
  - 工具描述和文件目录信息始终保留

**特点**：一次性压缩，不是滑动窗口。调查过程中 context 持续增长，只在最后生成因果图前压缩一次。

---

### 2. DeerFlow v2 (deerflow)

**压缩机制**：LangChain `SummarizationMiddleware`

- **实现文件**：`deer-flow-v2/backend/agent_runner.py` (lines 67-96), `src/agents/middlewares/`
- **触发时机**：token 数接近上限时自动触发（可配置）
- **压缩范围**：对话消息历史（user/assistant/tool messages）
- **压缩方式**：
  - 作为 middleware chain 的第 5 个中间件运行
  - 配置项（`config.yaml → summarization`）：
    - `enabled`：主开关
    - `trigger`：触发条件列表（tokens, messages, fraction of max）
    - `keep`：保留策略（如保留最近 N 条消息）
    - `trim_tokens_to_summarize`：压缩 prompt 的 token 限制
    - `summary_prompt`：自定义摘要模板
- **System Prompt 安全性**：✅ 安全（双重冗余）
  - System prompt 通过 `create_agent(system_prompt=...)` 持久化，middleware 不触及
  - **关键设计**：`data_dir` 同时写入 system_prompt 和 user_prompt
  - 代码注释明确写道：`"Append data_dir to BOTH system_prompt (survives summarization) and user_prompt"`
  - 即使 user_prompt 被摘要，system_prompt 中仍保留完整的目录信息

**特点**：最灵活的压缩机制，token 感知触发，可配置保留策略。开发者明确考虑了压缩安全性。

---

### 3. Auto-Deep-Research (auto_deep_research)

**压缩机制**：`compress_findings()` 函数

- **实现文件**：`Auto-Deep-Research/agent_runner.py` (lines 275-314)
- **触发时机**：MetaChain 执行完成后
- **压缩范围**：`response.messages`（对话历史）
- **压缩方式**：
  - 跳过 `think_tool` 的 "Reflection recorded:" 消息
  - 截断每条消息：assistant 3000 chars, user 2000 chars
  - 从过滤后的消息构建 `investigation_text`
  - 使用独立的 `compress_sp` + `compress_up` 调用 `litellm.completion()`
  - LLM 调用参数：`max_tokens=32000`
- **System Prompt 安全性**：✅ 安全
  - System prompt 是 Triage Agent 的 instructions 配置，不在 messages 列表中
  - 压缩只处理 `response.messages`，system prompt 从未进入压缩流程

**特点**：有消息截断（3000/2000 chars）+ LLM 摘要的双层压缩。截断可能丢失单条消息中的细节。

---

### 4. TaskWeaver (taskweaver)

**压缩机制**：`RoundCompressor` — 滚动摘要（最完善）

- **实现文件**：`TaskWeaver/taskweaver/memory/compression.py`
- **配置文件**：`taskweaver_config.json`
- **触发时机**：对话达到 `rounds_to_compress + rounds_to_retain`（默认 2+3=5 轮）
- **压缩范围**：旧对话轮次
- **压缩方式**：
  - **两阶段策略**：
    - `rounds_to_compress`（默认 2）：旧轮次通过 LLM 摘要
    - `rounds_to_retain`（默认 3）：最近轮次保留完整原文
  - 增量摘要：`PREVIOUS_SUMMARY` + 新轮次内容 → 更新后的摘要
  - 摘要结果存为 `ConversationSummary` + 提取的 `Variables`
  - 配置项：
    - `planner.prompt_compression: true`
    - `code_generator.prompt_compression: true`
    - `round_compressor.rounds_to_compress: 2`
    - `round_compressor.rounds_to_retain: 3`
- **System Prompt 安全性**：✅ 安全
  - System prompt 是 Planner 的 instruction template（临时 YAML 文件），框架级持久化
  - `RoundCompressor` 只压缩对话轮次（`post_list`），不触及 instruction template
  - 工具描述和目录信息始终保留

**特点**：唯一具备滑动窗口 + 增量摘要 + 变量提取的 agent。长对话中上下文管理最成熟。

---

### 5. DeepResearchAgent (deepresearchagent)

**无真正压缩**

- **实现文件**：`DeepResearchAgent/agent_runner.py` (lines 87-150)
- **有的功能**：
  - `strip_markdown_json()`：JSON 修复/截断，处理损坏的响应
  - 栈追踪式修复：跟踪 braces/brackets 嵌套来闭合不完整的 JSON
  - 5 次迭代裁剪循环寻找最后完整的 JSON 条目
- **循环限制**：`max_steps=50`（`configs/rca_agent.py`）
- **上下文管理**：依赖模型 context window 大小

---

### 6. AIQ (aiq)

**无压缩，多阶段 pipeline**

- **实现文件**：`aiq/agent_runner.py` (lines 250-301)
- **循环限制**：`MAX_TOOL_ROUNDS=15`
- **上下文管理**：
  - 多阶段 pipeline 天然分段：generate_queries → data_research → summarize → reflect → finalize
  - 每个阶段有独立的 summarization 节点，但这是功能性的（生成摘要），不是 context 管理
  - 15 轮工具调用限制有效控制 context 增长

---

### 7. OpenRCA (openrca)

**无压缩**

- **实现文件**：`OpenRCA/agent_runner.py`
- **循环限制**：`max_step=20`, `max_turn=5`（`control_loop()`）
- **上下文管理**：
  - stdout/stderr 重定向限制输出污染
  - Trajectory 提取为 code/result 对（比完整 messages 更轻量）
  - 依赖模型 context window

---

### 8. mABC (mabc)

**无压缩，结构性截断**

- **实现文件**：`mABC/agent_runner.py`
- **循环限制**：`MAX_REACT_STEPS=8`（每个 agent）
- **上下文管理**：
  - 两阶段设计：ProcessScheduler → SolutionEngineer（天然分段）
  - 多 agent debate 本身限制了单 agent 的对话长度
  - 最终输出通过 regex 从 LLM 响应中提取（隐式截断）

---

## System Prompt 安全性总结

所有 4 个有压缩能力的 agent 都**不会丢失 system prompt 中的工具/目录信息**：

| Agent | System Prompt 存储位置 | 压缩作用范围 | 保护机制 |
|-------|----------------------|-------------|---------|
| Deep_Research | 每次 LLM 调用重新注入 `SystemMessage` | 仅 `researcher_messages` | system prompt 不在 state 中 |
| DeerFlow v2 | `create_agent(system_prompt=...)` 持久化 | 仅对话消息 | data_dir 双写 system + user prompt |
| Auto-Deep-Research | Agent instructions 配置 | 仅 `response.messages` | system prompt 不在 messages 中 |
| TaskWeaver | Planner instruction template | 仅对话轮次 `post_list` | instruction template 框架级持久化 |

**根本原因**：这些框架都将 system prompt 和对话历史**分层存储**。压缩只作用于对话历史层，system prompt 作为框架配置层始终保留。

---

## 对评测质量的潜在影响

### 有压缩能力的 Agent

| 风险 | 说明 | 影响程度 |
|------|------|---------|
| 早期线索丢失 | TaskWeaver/DeerFlow 在 30+ 轮后可能摘要掉早期发现的关键服务信息 | 中 |
| 摘要质量依赖 LLM | 压缩本身是 LLM 调用，摘要可能遗漏重要细节 | 中 |
| 截断粒度 | Auto-Deep-Research 硬截断 3000 chars 可能丢失长工具输出中的关键数据 | 低-中 |

### 无压缩的 Agent

| 风险 | 说明 | 影响程度 |
|------|------|---------|
| Context window 溢出 | 复杂 case（30+ 轮）可能逼近 context 上限 | 中（claude-sonnet-4.6 context 足够大） |
| 轮次截断 | AIQ(15)/OpenRCA(20)/mABC(8) 可能在未完成调查时被强制终止 | 高（mABC 仅 8 步） |
| 注意力稀释 | 无压缩 = 全部历史消息都在 context 中，模型注意力可能被无关信息分散 | 低 |

### 与错误案例的关联

从 Batch #1 (thinkdepthai-claude-sonnet-4.6) 的 13 个错误案例看：
- 错误案例平均 **33.9 轮、1.80M tokens**（正确 28.3 轮、1.13M tokens）
- Deep_Research 的一次性压缩在调查阶段不生效 → 长轮次 case 中 context 持续增长
- 错误案例更多 `rt:no_data`（40.4% vs 32.9%）→ 大量空结果堆积在 context 中可能稀释注意力
- 这与"over-investigating in wrong direction"的 insight 一致：没有中间压缩来帮助 agent 反思和纠正方向
