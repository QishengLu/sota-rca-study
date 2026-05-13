# Setup Inputs — 等你填完，我一口气把剩下都做完

填好后，回复"开始"或把这个文件填好的内容贴给我。**所有空缺都需要填**（除非标 optional）。

---

## 1. 6 个 fork 后的 agent GitHub URL（必填）

把每个 agent 上游仓 fork 到你能 push 的 GitHub org/账号下，然后填这里。
URL 格式：`https://github.com/<你的-org>/<repo-name>.git`

```
thinkdepthai = 
aiq          = 
taskweaver   = 
openrca      = 
claudecode   = 
mabc         = 
```

每个仓 fork 后**保持原状即可**（我会拷贝当前 frameworks/ 下的修改上传到这些 fork）。

---

## 2. sota-rca-study 主仓 GitHub URL（必填）

在 GitHub 新建一个空 repo（private 或 public 都行），格式：
```
sota_rca_study_repo = 
```

例如：`https://github.com/yourname/sota-rca-study.git`

**注意**：不要勾选"Add README"或"Add .gitignore"，让仓库初始为空（避免跟我本地的 2 个 commit 冲突）。

---

## 3. aegis v3 commit pin hash（必填）

去 https://github.com/OperationsPAI/aegis/commits/main 选一个看起来稳定的 commit（建议最近 1-2 周内的）。

```
aegis_commit_hash = 
```

例如：`a3f5b2c1d`（短哈希）或完整 40 字符。

**Optional**：如果想 vendored 离线副本而非 git 依赖，告诉我，我会改成本地 path 形式。

---

## 4. LLM Provider API Keys（至少填 1 个，多多益善）

写法：`<env_var_name>=<key_value>`。

**建议至少填 2 个**：1 个国内（qwen / glm / kimi / deepseek）+ 1 个国外（claude / openai / gemini），方便横向对比。

```
# Anthropic 系（shubiaobiao proxy 给 claude-sonnet-4-6 / opus-4-7）
SHUBIAOBIAO_API_KEY = 

# OpenAI 官方（gpt-4.5 / gpt-4o / o1）
OPENAI_API_KEY = 

# 阿里云通义（qwen3.6-plus / qwen3.5-plus）
DASHSCOPE_API_KEY = 

# 智谱 GLM
ZHIPU_API_KEY = 

# Moonshot Kimi
MOONSHOT_API_KEY = 

# DeepSeek
DEEPSEEK_API_KEY = 

# Google Gemini
GOOGLE_API_KEY = 

# ClaudeCode 框架专用（Aliyun Coding Plan Anthropic 端点）
ANTHROPIC_API_KEY = 
ANTHROPIC_BASE_URL = 
```

填一个或多个都行。**没填的 alias 会被自动跳过**（不阻塞其他 model 跑）。

---

## 5. ops-lite 数据集（必填一个选项）

**选项 A**：让我用 `huggingface_hub` 帮你下载到 `~/.cache/sota-rca/ops-lite`（4.13 GB，需要你的 HF token）：

```
HF_TOKEN = 
```

**选项 B**：你已经下载到某个目录，告诉我路径：

```
ops_lite_local_path = 
```

例如：`/home/nn/datasets/ops-lite/`

**选项 C**：用 HuggingFace 国内 mirror（hf-mirror.com）下载，无需 token：

```
use_hf_mirror = yes
```

---

## 6. Mac 笔记本同步（optional）

如果你之后要从这台 Linux 服务器把仓同步到 Mac，我可以加：
- `scripts/sync_to_mac.sh`（rsync 命令模板）
- Mac 上的 Docker Desktop 配置说明

填 Mac 主机名 / 用户名（optional）：
```
mac_ssh_target = 
```

例如：`nn@my-mac.local`

---

## 7. 其它选项（optional）

```
# 主仓 push 到 GitHub 后是否设为 public
make_public = no/yes

# 你想给合作者预置哪些 model 在 demo.yaml 的默认列表里
# (从 catalog.yaml 选 alias，逗号分隔)
demo_default_models = sonnet46, qwen36

# 你想 demo 默认包含哪些 framework
demo_default_frameworks = thinkdepthai, aiq
```

---

## 完成后

填好所有 **必填** 项后回复"开始"或者把填好的内容贴给我，我会一口气做完以下事：

1. uv sync（初始化 Python 环境 + 生成 uv.lock）
2. pyproject.toml 接入 aegis v3 pin commit
3. .env 写入 API keys + 端口避免冲突（POSTGRES_PORT=5434, DASHBOARD_PORT=8002）
4. .gitmodules 填入 6 个 fork URL + `git submodule add` × 6
5. 把当前 `frameworks/<name>/` 下的本地修改 push 到对应的 6 个 fork
6. mabc/agent_runner.py 接入 data_adapter.py
7. 6 agent 内部 base_url / model 硬编码替换成 UTU_LLM_* env
8. ops-lite 数据集下载 + 校验
9. PG 启动（端口 5434）+ DB schema 初始化
10. dashboard frontend npm install + npm run build
11. 1 case 端到端 dry-run（不调 LLM；纯管道验证）
12. （如果填了 API key）1 case 真实 smoke（消耗 ~$0.05）
13. `git remote add origin <你的主仓URL> + git push -u origin main`
14. 更新 README / REPRODUCTION 反映完成状态

预估耗时 ~45-60 min（数据集下载占大头）。

---

## 不知道某项？

- **不知道哪个 aegis commit 选**：填 `aegis_commit_hash = HEAD` — 我会用当前 main 最新 commit
- **暂时没所有 API key**：填能填的就行，其它留空
- **不知道是否要 push 到 GitHub**：填 `sota_rca_study_repo = SKIP` — 我跳过这步，留作本地
- **不要数据集了**：填 `ops_lite_local_path = SKIP` — 我跳过数据下载步骤，6 个 agent 仍可注册和被发现，只是不能真跑 case
