# OpenRCA 接入指南 — SOTA-agents 评测流水线

## 架构概述

OpenRCA 是一个 **双层代码执行型 RCA Agent**：

```
Controller LLM（Administrator）
  │  接收任务目标，指令化分解推理步骤
  │  输出 JSON: { analysis, instruction, completed }
  ▼
Executor LLM（DevOps Assistant）
  │  将自然语言指令翻译为 Python 代码
  │  代码交由 IPython kernel 执行
  ▼
IPython Kernel（Stateful Python Environment）
  │  执行 pandas/DuckDB 代码，读取 parquet 数据
  │  返回执行结果（DataFrame, 数值, 字符串）
  ▼
Controller LLM 汇总结论
  │  选取候选服务列表中的根因组件
  ▼
输出 JSON: { "1": { "root cause component": "ts-auth-service", ... } }
```

与 thinkdepthai 的核心区别：
- **OpenRCA**: LLM 生成代码 → IPython 执行 → 结果反馈给 LLM
- **thinkdepthai**: LLM 直接调用 DuckDB tool → 工具返回结果给 LLM

---

## 文件结构

```
OpenRCA/
├── agent_runner.py              # ⭐ 流水线接口（stdin→stdout）
├── pyproject.toml               # uv 依赖管理
├── .env                         # API keys（kimi-k2）
├── rca/
│   ├── api_config.yaml          # LLM API 配置（被 agent_runner.py 覆盖）
│   ├── api_router.py            # LLM 调用路由（支持 OpenAI/Anthropic/AI）
│   └── baseline/rca_agent/
│       ├── rca_agent.py         # Agent 入口类
│       ├── controller.py        # ⭐ 控制循环（Controller LLM + 主流程）
│       ├── executor.py          # Executor LLM + IPython kernel 执行
│       └── prompt/
│           ├── agent_prompt.py  # Controller 规则（故障诊断工作流）
│           ├── basic_prompt_Bank.py     # 原始 Bank 数据的 schema+candidates
│           ├── basic_prompt_Market.py   # 原始 Market 数据的 schema+candidates
│           └── basic_prompt_Telecom.py  # 原始 Telecom 数据的 schema+candidates
└── docs/
    ├── integration_guide.md     # 本文件
    └── trajectory_analysis_sample1.md  # Sample 1 轨迹分析
```

---

## agent_runner.py 设计要点

### 动态 basic_prompt 构建

原始 OpenRCA 用固定的 `basic_prompt_Bank.py` 等文件描述数据 schema 和候选服务列表。
我们改为在运行时从 `data_dir` 动态构建：

```python
# Schema 描述 parquet 文件结构 → 告诉 Executor 如何读取数据
schema = _SCHEMA_TMPL.format(data_dir=data_dir)

# 候选服务列表 → 从 abnormal_metrics.parquet 动态提取 ts-* 服务名
cand = _get_service_candidates(data_dir)

bp.schema = schema + "\n" + cand   # 传给 Controller 的背景知识
bp.cand = cand                      # 传给最终 summary 步骤
```

### API 配置覆盖

原始 `api_router.py` 按 YAML > 环境变量 优先级加载配置。
我们在 import 后直接 patch 字典：

```python
from rca.api_router import configs
configs["SOURCE"] = "AI"
configs["MODEL"] = os.environ.get("OPENRCA_MODEL", "kimi-k2-0905-preview")
configs["API_KEY"] = os.environ.get("OPENAI_API_KEY", "")
configs["API_BASE"] = os.environ.get("OPENAI_BASE_URL", "https://api.moonshot.cn/v1")
```

### stdout 保护

IPython kernel 可能向 fd=1 写入数据，影响 RolloutRunner 的 JSON 解析。
我们在 main() 开始时用 `os.dup2` 将 fd=1 重定向到 fd=2（stderr），
最后通过保存的 fd 写入最终 JSON：

```python
_real_stdout_fd = os.dup(1)   # 保存真实 stdout
os.dup2(2, 1)                 # fd 1 → stderr（IPython 输出不污染 stdout）
# ... 运行 control_loop ...
os.write(_real_stdout_fd, json_line.encode())  # 最后写真实 stdout
```

### 输出格式

输出为 CausalGraph JSON（只有 root_causes，nodes/edges 为空列表）：

```json
{
  "output": "{\"nodes\": [], \"edges\": [], \"root_causes\": [{\"component\": \"ts-auth-service\", \"state\": []}]}",
  "trajectory": [
    {"role": "assistant", "content": "# Python code"},
    {"role": "tool", "content": "Execution result", "tool_call_id": "exec_0"}
  ]
}
```

---

## 运行流程

### 1. 准备 init DB

```bash
cd /home/nn/SOTA-agents/RolloutRunner

# 从 thinkdepthai-kimi-k2.db 复制样本，生成 openrca-kimi-k2.db（stage='init'）
uv run python scripts/create_openrca_init_db.py

# 可选：只准备前 N 条（调试）
uv run python scripts/create_openrca_init_db.py --limit 10
```

### 2. 冒烟测试

```bash
UTU_DB_URL=sqlite:////home/nn/SOTA-agents/RolloutRunner/openrca-kimi-k2.db \
  uv run python scripts/run_rollout.py \
    --agent openrca \
    --source_exp_id rollout_openrca \
    --limit 1
```

### 3. 全量运行

```bash
UTU_DB_URL=sqlite:////home/nn/SOTA-agents/RolloutRunner/openrca-kimi-k2.db \
  nohup python -u scripts/run_rollout.py \
    --agent openrca \
    --source_exp_id rollout_openrca \
  > openrca.log 2>&1 &

# 监控进度
tail -f openrca.log
sqlite3 openrca-kimi-k2.db "SELECT stage, COUNT(*) FROM evaluation_data GROUP BY stage"
```

### 4. 评分（AC@1）

```bash
# Step 1: cp DB 到 RCAgentEval
cp /home/nn/SOTA-agents/RolloutRunner/openrca-kimi-k2.db \
   /home/nn/SOTA-agents/RCAgentEval/

cd /home/nn/SOTA-agents/RCAgentEval

# Step 2: rollout → judged
sqlite3 openrca-kimi-k2.db "UPDATE evaluation_data SET stage='judged' WHERE stage='rollout'"

# Step 3: 填充 difficulty metadata（Dashboard 分布图需要）
# 参见 EVAL_RUNBOOK.md Step 7.5

# Step 4: 运行评分
UTU_DB_URL=sqlite:////home/nn/SOTA-agents/RCAgentEval/openrca-kimi-k2.db \
  uv run python scripts/rejudge_samples.py

# Step 5: 查看结果
sqlite3 openrca-kimi-k2.db \
  "SELECT correct, COUNT(*) FROM evaluation_data WHERE stage='judged' GROUP BY correct"
```

---

## 性能参数

| 参数 | 值 | 说明 |
|------|----|------|
| concurrency | 2 | 每个样本独立子进程，API rate limit 是瓶颈 |
| timeout | 900s | 单样本最多 20 步 × 2 次 LLM/步，留足余量 |
| max_step | 20 | Controller 最大指令轮数 |
| max_turn | 5 | Executor 单条指令最大重试次数 |
| 实测耗时 | ~600s/样本 | kimi-k2 推理较慢，有思考时间 |
| 预计全量时间 | ~8小时（concurrency=2） | 93 条剩余样本 |

---

## 已知问题

| 问题 | 原因 | 影响 |
|------|------|------|
| 阈值计算被污染 | `abnormal_*.parquet` 包含故障期数据，全局 P95 被抬高 | 小幅度异常（如 JVM 注入）检测不灵敏 |
| trace 调用方向理解错误 | Controller 规则对"下游"定义模糊 | 将入口服务（ts-ui-dashboard）误判为根因 |
| log 选择性分析 | 先确定嫌疑服务再看日志（证实偏差） | 只看了错误服务的日志 |
| 时间戳 hallucination | 第一步 LLM 汇总时报了错误年份 | 自动纠正，无实质影响 |

---

## 与 thinkdepthai 的对比

| 维度 | OpenRCA | thinkdepthai |
|------|---------|-------------|
| 数据访问方式 | LLM 写代码 → IPython 执行 | DuckDB 工具直接查询 |
| 推理透明度 | 高（每步 Python 代码可读） | 中（tool_call 参数可读） |
| 因果图输出 | ❌（只有 root cause 组件） | ✅（nodes + edges + root_causes） |
| 对小幅度异常的鲁棒性 | 较弱（阈值污染问题） | 较强 |
| 单样本耗时 | ~600s | ~200s |
| 评测指标 | AC@1 only | AC@1 + Node F1 + Edge F1 + RC F1 |
