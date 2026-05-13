# 实验运行与监控手册

## 启动实验

```bash
# 前置：确保 PostgreSQL 已启动
cd /home/nn/SOTA-agents/RCAgentEval/docker && docker compose up -d

# 前置：为每个 agent 生成 init 样本（只需做一次）
cd /home/nn/SOTA-agents/RCAgentEval
export UTU_DB_URL="postgresql://postgres:postgres@localhost:5433/SOTA-Agents"
for agent in thinkdepthai deerflow auto_deep_research deepresearchagent aiq taskweaver openrca mabc; do
    uv run python scripts/preprocess_only.py --exp_id "${agent}-claude-sonnet-4.6"
done

# 启动实验（自动进入 tmux 界面）
bash /home/nn/SOTA-agents/RolloutRunner/launch_eval.sh
```

运行后会直接进入 tmux 界面，看到 runner window 的实验日志。

---

## 离开与恢复

| 操作 | 命令 |
|------|------|
| 离开 tmux（实验继续跑） | `Ctrl+b` 然后 `d`，或直接输入 `tmux detach` |
| 直接关 SSH 窗口 | 实验**不会中断**，tmux server 独立运行 |
| 重新 SSH 后恢复监控 | `tmux attach -t eval` |
| 切换到监控 window | tmux 内 `Ctrl+b` 然后 `1`，或 `tmux select-window -t eval:monitor` |
| 切换回 runner window | tmux 内 `Ctrl+b` 然后 `0`，或 `tmux select-window -t eval:runner` |

> **⚠️ VS Code 终端用户注意**：VS Code 会拦截 `Ctrl+b`（用于切换侧边栏），导致 tmux 前缀键失效。解决方法：
>
> **方法一（推荐）**：禁用 VS Code 对终端的 `Ctrl+b` 拦截。按 `Ctrl+Shift+P` → `Open Keyboard Shortcuts (JSON)`，添加：
> ```json
> { "key": "ctrl+b", "command": "-workbench.action.toggleSidebarVisibility", "when": "terminalFocus" }
> ```
>
> **方法二**：改用命令行操作代替快捷键：
> ```bash
> tmux detach                          # 代替 Ctrl+b d
> tmux select-window -t eval:runner    # 代替 Ctrl+b 0
> tmux select-window -t eval:monitor   # 代替 Ctrl+b 1
> tmux next-window -t eval             # 代替 Ctrl+b n
> ```
>
> **方法三**：用系统终端（MobaXTerm / iTerm2 / Terminal.app）直接 SSH，不受 VS Code 拦截影响。

---

## 确认实验还在跑

```bash
# 方法1：重进 tmux 看实时日志（最直观）
tmux attach -t eval

# 方法2：查进程
ps aux | grep run_rollout

# 方法3：看某个 agent 的日志文件
tail -f /home/nn/SOTA-agents/RolloutRunner/logs/thinkdepthai-4.6.log

# 方法4：查 DB 进度（每个 exp_id 的完成数量）
psql "postgresql://postgres:postgres@localhost:5433/SOTA-Agents" \
  -c "SELECT exp_id, stage, COUNT(*) as cnt FROM evaluation_data GROUP BY exp_id, stage ORDER BY exp_id, stage"
```

---

## 实验日志格式

**agent 切换时（bash echo）：**
```
========================================
=== AGENT: thinkdepthai
=== START: 2026-03-15 10:00:00
========================================
...
=== DONE: thinkdepthai at 2026-03-15 14:23:00 ===
```

**每条样本完成时（run_rollout.py）：**
```
Progress: 42/500 (ok=41, fail=1) | sample=1234 tokens=45,231(actual) rounds=8 cost=$0.1823 time=307.2s
```

**AIMD 并发调整时：**
```
[AIMD] Starting with capacity=1, max=5
[AIMD] Concurrency ↑ 2 (backoff=5s)    ← 每 10 次成功 +1
[AIMD] Concurrency ↓ 2 → 1 (backoff=5s) ← 失败后减半
```

**agent 完成汇总：**
```
Results: success=487, failure=13
Total tokens: 22,615,432 (actual=487, estimated=0)
Total cost: $89.2341 USD
Total time: 15138.0s  Avg time: 31.1s/sample
```

---

## 常见操作

```bash
# 调整某 agent 的并发上限（对当前 agent 的下一轮生效）
vim /home/nn/SOTA-agents/RolloutRunner/configs/agents/thinkdepthai.yaml
# 修改 concurrency: 5 → 8

# 某 agent 中途失败后手动补跑（自动跳过已完成样本）
cd /home/nn/SOTA-agents/RolloutRunner
export UTU_DB_URL="postgresql://postgres:postgres@localhost:5433/SOTA-Agents"
uv run python scripts/run_rollout.py --agent thinkdepthai --source_exp_id thinkdepthai-claude-sonnet-4.6

# 查看所有 tmux session
tmux ls

# 彻底停止实验
tmux kill-session -t eval
```

---

## 实验顺序（串行）

```
1. thinkdepthai
2. deerflow
3. auto_deep_research
4. deepresearchagent
5. aiq
6. taskweaver
7. openrca
8. mabc
```

修改顺序：编辑 `RolloutRunner/run_eval_sequential.sh` 第 11 行的 `AGENTS` 数组。
