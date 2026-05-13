# CLAUDE.md — OpenRCA

双层代码执行式 RCA agent。不同于 tool-calling 范式，OpenRCA 让 LLM 生成 Python 代码并在 IPython kernel 中执行，形成 LLM↔数据 的反馈循环。

---

## 架构

- **框架**: 自定义 Controller-Executor 双层循环（非 LangGraph/LangChain）
- **模型**: OpenAI SDK（claude-sonnet-4-6 via shubiaobiao API）
- **执行模型**: 有状态 IPython kernel（变量跨步骤保留）

### 双层 LLM 分工

| 层 | 角色 | 输入 | 输出 |
|----|------|------|------|
| Controller | Administrator（分解任务） | 目标 + schema + 候选服务 | `{"analysis", "instruction", "completed"}` |
| Executor | DevOps Assistant（写代码） | Controller 的自然语言指令 | Python 代码块 |

循环流程: Controller 出指令 → Executor 写代码 → IPython 执行 → 结果返回 Controller → 下一步指令

---

## 入口文件

| 文件 | 用途 |
|------|------|
| `agent_runner.py` | RolloutRunner 统一接口（stdin/stdout） |
| `rca/baseline/rca_agent/controller.py` | 主控制循环 |
| `rca/baseline/rca_agent/executor.py` | 代码生成 + 执行 |
| `rca/baseline/rca_agent/prompt/agent_prompt.py` | RCA 4 阶段工作流规则 |
| `rca/api_router.py` | LLM API 抽象层 |

---

## agent_runner.py 工作流程

1. **stdout 隔离**: `os.dup2()` 重定向 fd，防止 IPython/pandas 输出污染 stdout
2. 接收 stdin JSON（question, system_prompt, user_prompt, data_dir）
3. **动态 Prompt 构建**:
   - `_SCHEMA_TMPL`: 描述 parquet 表结构和列名
   - `_get_service_candidates()`: 从 abnormal_metrics.parquet 提取 `ts-*` 服务名
   - `_build_objective()`: 解析问题 + 从 env.json 提取异常时间窗口
4. 运行 `control_loop()`（Controller-Executor 循环）
5. **根因解析**: 先尝试 JSON parse，降级到 regex `\bts-[a-z][a-z0-9-]*service\b`
6. 输出 stdout JSON（output, trajectory, usage）

---

## 工具

**无显式 tool 注册**。OpenRCA 通过代码执行隐式访问数据：

```python
# Executor 生成的典型代码
import pandas as pd
df = pd.read_parquet("/path/to/abnormal_traces.parquet")
result = df.groupby("service_name").agg({"duration": "mean"}).sort_values("duration", ascending=False)
```

所有数据操作通过 pandas + pyarrow 在 IPython kernel 中完成。

---

## RCA 4 阶段工作流

1. **Preprocess**: 读取 schema，计算全局阈值
2. **Anomaly Detection**: 基于 P95 阈值识别异常
3. **Fault Identification**: 定位故障服务
4. **Root Cause Localization**: 确定根因

---

## 循环限制

| 参数 | 值 |
|------|---|
| max_step | 20 |
| max_turn | 5 |
| Executor 重试 | 2 次/指令 |
| 单次结果 token 限制 | 16,384 |
| DataFrame 截断 | >10 行时告警 |

---

## 特殊处理

| 项目 | 说明 |
|------|------|
| stdout 隔离 | `os.dup2()` 保存真实 fd，IPython 输出重定向到 stderr |
| think_tool | 不需要（代码生成本身就是隐式推理） |
| UsageTracker | install_openai_hooks()（OpenAI SDK） |
| 输出格式 | 只返回 root_causes，不构建完整 nodes/edges 图 |
| Trajectory 转换 | code → `{"role":"assistant"}`, result → `{"role":"tool"}` |

---

## 环境

```bash
cd /home/nn/SOTA-agents/OpenRCA
uv run python agent_runner.py  # stdin/stdout 接口
```

- Python 3.11+，uv 管理（也可 pip）
- 依赖: openai, pandas, pyarrow, ipython, loguru

### .env 配置

```bash
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.shubiaobiao.cn/v1
OPENRCA_MODEL=claude-sonnet-4-6
```

---

## 已知问题

- **偶尔超时**: 复杂 case 的 Controller-Executor 循环可能超过 900s
- **无图结构输出**: 只返回 root_causes component 列表，edge/node F1 无法计算
- **代码执行失败**: Executor 生成的代码偶尔语法错误，重试 2 次后跳过

---

## RolloutRunner 配置

```yaml
# RolloutRunner/configs/agents/openrca.yaml
name: openrca
cmd: ["uv", "run", "python", "agent_runner.py"]
cwd: /home/nn/SOTA-agents/OpenRCA
exp_id: openrca-claude-sonnet-4.6
agent_type: openrca
concurrency: 5
timeout: 600
```
