# 原始数据导航指南 — 每一类信息在哪里看最高效

**目的**：当你想深入研究某个 case 的全部原始信息时，按下面 5 大类一一对应去看。
**示例 case**：281（GT=ts-station-food-service，wrong→correct，M6+M5 mid + M8 conc）。所有路径以这个 case 为例。

---

## 0. 三个关键标识（先记住这套对应关系）

| 标识 | case 281 实际值 |
|---|---|
| `dataset_index` | **281** |
| `source` 名（注入名）| `ts0-ts-station-food-service-stress-j5qdln` |
| `datapack` 名（agent 看到的目录）| `data_412b5c95` |
| baseline `exp_id` | `thinkdepthai-qwen3.5-plus` |
| v4 `exp_id` | `thinkdepthai-qwen3.5-plus-2026-02-15-mw-v4-run` |

查任意 case 的对应关系：

```bash
UTU_DB_URL="postgresql://postgres:postgres@localhost:5433/SOTA-Agents" \
uv run --project RCAgentEval python -c "
import os, json, re
from sqlalchemy import create_engine, text
e = create_engine(os.environ['UTU_DB_URL'])
DI = 281  # 改成你想看的 dataset_index
with e.connect() as c:
    r = c.execute(text(\"SELECT source, meta::text, augmented_question, correct_answer FROM evaluation_data WHERE exp_id='thinkdepthai-qwen3.5-plus' AND dataset_index=:d\"), {'d': DI}).fetchone()
    meta = json.loads(r[1])
    print('source:', r[0])                                    # 注入名
    print('source_data_dir:', meta.get('source_data_dir'))    # 完整原始数据
    m = re.search(r'stored in[:\s]+\`([^\`]+)\`', r[2])
    print('agent_data_dir:', m.group(1) if m else None)       # symlink 后 agent 实际跑 SQL 的目录
    print('GT:', r[3])
"
```

---

## 1. GT 注入信息 → `injection.json`

**位置**：`/home/nn/SOTA-agents/RCAgentEval/data/<source>/converted/injection.json`

case 281 例子：

```bash
cat /home/nn/SOTA-agents/RCAgentEval/data/ts0-ts-station-food-service-stress-j5qdln/converted/injection.json
```

**关键字段**：
- `display_config` → 故障的人话描述（duration、injection_point.{app_name, class_name, method_name}、mem_type 等）
- `start_time` / `end_time` → 故障窗口时间戳（供你拿这些时间去 trajectory 里对账）
- `pre_duration` → 故障前正常运行多少分钟（normal_logs 那段）
- `ground_truth.{container, function, metric, pod, service, span}` → 6 维 GT
- `fault_type` → 数字编码（28 = JVMMemoryStress；完整编码表见 `RolloutRunner/configs/...`）

case 281 的 ground_truth：
```json
{
  "container": ["ts-station-food-service"],
  "function": ["food.controller.StationFoodController.home"],  ← 注入到了哪个具体方法
  "metric": ["memory"],
  "pod": ["ts-station-food-service-8c666b479-pd5f7"],
  "service": ["ts-station-food-service"]
}
```

---

## 2. 根因传播状态 → `causal_graph.json` + dossier `.md`

### 2A · 原始 propagation graph：`causal_graph.json`

**位置**：`<source_data_dir>/causal_graph.json`

```bash
cat /home/nn/SOTA-agents/RCAgentEval/data/ts0-ts-station-food-service-stress-j5qdln/converted/causal_graph.json
```

**结构**：
- `nodes[]` — 每个节点是一个组件（container/pod/service/span），含 `state[]` 列出该组件**应该**呈现什么状态（high_cpu / restarting / missing_span / high_avg_latency 等）
- `raw_edges` 或 `edges[]` — 组件之间的 propagation 边
- `root_causes[]` — 根因节点列表

case 281 的 root cause node：
```json
{"timestamp": null, "component": "container|ts-station-food-service", "state": ["unknown"]}
```

**关键观察方式**：找 state 含 `injection_affected` 的 span 节点 — 这些是**直接受注入影响**的位置，是 agent 应该查到的最强信号。case 281 里 `span|ts-station-food-service::StationFoodController.getFoodStoresByStationNames` 等 5 个 span 都有 `injection_affected`。

### 2B · 已经做好的人类可读总结：dossier

**位置**：`/home/nn/SOTA-agents/analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_<DI>.md`

case 281 例子：[dossiers/case_281.md](../3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_281.md)

dossier 提供：
- A.1 注入 spec（display_config 解码后）
- A.2 GT 服务列表
- A.3 GT causal graph 表格化（每个组件 → expected_states）
- A.4 Span footprint top 20（abn_succ vs norm_succ vs abn_ms vs norm_ms — 数字化"哪些 span 真的劣化了"）
- B 部分（baseline agent 推理失败模式）

dossier 是**最快读懂 GT 应该是什么样的入口**，比 raw `causal_graph.json` 直接看快 10 倍。

---

## 3. agent 实际看到的数据 → parquet 文件

**位置**：`<source_data_dir>/` 或 agent 实际查询的 `<agent_data_dir>/`（symlink 等价）

agent 跑的所有 SQL 都打在这 9 个 parquet 上：

| 文件 | 内容 |
|---|---|
| `abnormal_logs.parquet` / `normal_logs.parquet` | log 行（time, trace_id, level, service_name, message） |
| `abnormal_traces.parquet` / `normal_traces.parquet` | trace span（time, trace_id, span_id, parent_span_id, service_name, span_name, duration, attr_status_code, attr_http_*） |
| `abnormal_metrics.parquet` / `normal_metrics.parquet` | metric 时间序列（time, metric, value, service_name, k8s 元信息） |
| `abnormal_metrics_histogram.parquet` / `normal_metrics_histogram.parquet` | histogram 类（latency p50/p90/p99） |
| `abnormal_metrics_sum.parquet` / `normal_metrics_sum.parquet` | counter 类 |
| `conclusion.parquet` | 生成数据集时的统计（不是 agent 数据）|

要看 case 281 的注入时间窗口内的事件：

```bash
# 最快方式：用 duckdb（agent 也用它）查任意 SQL
cd /home/nn/SOTA-agents/RCAgentEval/data/ts0-ts-station-food-service-stress-j5qdln/converted

uv run python -c "
import duckdb
con = duckdb.connect()
con.execute(\"CREATE VIEW abnormal_logs AS SELECT * FROM read_parquet('abnormal_logs.parquet')\")
con.execute(\"CREATE VIEW normal_logs AS SELECT * FROM read_parquet('normal_logs.parquet')\")
# 任意 SQL，模拟 agent 视角
df = con.execute(\"SELECT service_name, level, COUNT(*) FROM abnormal_logs GROUP BY 1,2 ORDER BY 3 DESC LIMIT 10\").fetchdf()
print(df)
"
```

---

## 4. 完整轨迹（baseline 错的 + v4 修复的）→ DB `trajectories` 列

### 4A · 直接用我刚写的 dump 工具（**推荐这个，不要肉眼看 raw JSON**）

```bash
cd /home/nn/SOTA-agents
UTU_DB_URL="postgresql://postgres:postgres@localhost:5433/SOTA-Agents" \
  uv run --project RCAgentEval python analysis/4-middleware/v4_forensic/dump_trajectory.py \
  thinkdepthai-qwen3.5-plus 281 > /tmp/case281_baseline.txt

UTU_DB_URL="postgresql://postgres:postgres@localhost:5433/SOTA-Agents" \
  uv run --project RCAgentEval python analysis/4-middleware/v4_forensic/dump_trajectory.py \
  thinkdepthai-qwen3.5-plus-2026-02-15-mw-v4-run 281 > /tmp/case281_v4.txt
```

输出格式：
```
[Round 30] (msg_idx=58) assistant  tools=['query_parquet_files']
    [query_parquet_files] query: SELECT time, service_name, level, message FROM abnormal_logs ...
  ↳ tool result (?): [   {"time": "...", "service_name": "ts-food-service", "level": "ERROR", ...

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!! [v4 干预 #1] msg_idx=60  之前 round_count=30
!!! phase=mid  primary=M6  secondary=M5
!!! ↓ 完整干预文 ↓
[Investigation Advisor — v4] phase=mid primary=M6 secondary=M5 ...
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

[Round 31] (msg_idx=61) assistant  tools=['think_tool']
    [think_tool] reflection: The investigation advisor raises critical points:  1. I haven't compared abnormal data with normal baseline data ...
```

**特性**：
- 每个 assistant turn = "Round N"，明确编号
- 干预用 `!` 框起来，前后清楚知道在哪个 round 之间插入
- 每个 SQL / reflection 都打印（截断到 200-300 字）
- 加 `--full` 参数可看完整内容（不截断）

### 4B · raw JSON（如果你想自己处理）

```bash
UTU_DB_URL="postgresql://postgres:postgres@localhost:5433/SOTA-Agents" \
uv run --project RCAgentEval python -c "
import os, json
from sqlalchemy import create_engine, text
e = create_engine(os.environ['UTU_DB_URL'])
with e.connect() as c:
    raw = c.execute(text('SELECT trajectories::text FROM evaluation_data WHERE exp_id=:e AND dataset_index=:d'), {'e': 'thinkdepthai-qwen3.5-plus-2026-02-15-mw-v4-run', 'd': 281}).scalar()
print(raw[:5000])  # 或保存到文件后用 jq
"
```

trajectory 是一个 list of dict，每个 dict 是 OpenAI role 格式：
- `{"role": "assistant", "content": "...", "tool_calls": [{"function": {"name": "...", "arguments": "..."}}]}` — agent 一轮思考 + 工具调用
- `{"role": "tool", "content": "...", "tool_call_id": "..."}` — 工具返回值
- `{"role": "user", "content": "[Investigation Advisor — v4] ..."}` — **v4 干预**（这是 v4 区别于 v3 的关键，v3 conclusion 干预看不到）

### 4C · 已经在缓存里的关键摘要

```bash
cat /home/nn/SOTA-agents/analysis/4-middleware/v4_forensic/cache/281.json
```

包含：
- `gt` / `baseline.{predicted_rc, n_qpf, reasoning_excerpts}` / `v4.{predicted_rc, n_qpf, interventions[], final_reasoning_excerpts}`
- `interventions[].{phase, primary, secondary, round_at_inject, intervention_text, agent_response_excerpt, post_intervention_tool_rounds}`

如果你只想知道某个 case "干预之后 agent 立刻说了什么"，看缓存的 `agent_response_excerpt` 最快。

---

## 5. 中间件在哪个 turn 真起作用 → 三步定位法

不是看一个数字。**起作用 = 干预触发后 → think_tool 反思 → 新查询模式 → 关键发现**这条因果链是否成立。

### Step 1：找干预的 round 边界

dump 工具在干预前后清楚标了 round count。case 281：

```
[Round 30] ts-food-service ERROR 时间排序  ← 干预前最后一轮，agent 在 commit ts-food-service
!!! 干预 #1 msg_idx=60  之前 round_count=30
!!! phase=mid primary=M6 secondary=M5
[Round 31] think_tool: "I haven't compared baseline ... 'loudest' doesn't mean root cause"
[Round 32] SELECT * FROM normal_logs ...  ← 全程第一次查 normal!
[Round 36] think_tool: "Normal traces ZERO errors. Abnormal: ts-food 69, ts-station-food 27"
[Round 42] think_tool: "ts-station-food p90 0.017→1.268s, 75x增"  ← anchor-flip
```

**结论**：mid M6 在 Round 31 (think_tool 自检) 触发反思，Round 32 (首次 normal_logs) 触发新查询模式，Round 42 (think_tool 发现 75x latency) **anchor 真正翻转**。所以 **承重 turn = Round 32 → Round 42 这段窗口**，不是单一 turn。

### Step 2：判断"承重"vs"supporting"vs"无效"vs"misdirected"

| 现象 | 判定 |
|---|---|
| 干预后 agent 立刻 think_tool 复述干预要点 + 紧跟着发起**新维度的查询**（baseline 对比 / runtime metric / silent service 探查 / sibling check）+ 最终 RC 翻转 | **承重** |
| agent 复述了干预要点 + 做了相应查询，但只起到验证已有候选的作用，最终 RC 没改变 | **supporting** |
| agent 没复述（reflection 空，或 think_tool 没出现），post 几个 round 直接进 compress | **无效** |
| agent 复述了，做了新查询，但走向了**另一个错答案** | **misdirected** |
| agent 复述了，但接下来用 counterfactual 得出"是的，候选健康下其他错确实不会发生" → 加固原候选 | **counterfactual-reinforced** |

判定字段对应在哪：

| 字段 | 在哪查 |
|---|---|
| 干预前后 round 边界 | dump 工具的 `[Round N]` 数字 |
| 干预后第一个 think_tool | dump 中干预 `!!!` 后第一个 `tools=['think_tool']` |
| 是否换查询维度 | 干预后 N 个 round 内 SQL 涉及的表（normal_* vs abnormal_*）/ metric 名（http vs jvm vs k8s）|
| 关键 anchor-flip 证据 | think_tool reflection 含 "X 倍 / spike / restart / silent" 等关键词 |
| 最终 RC | DB `correct_answer` vs `meta.causal_graph_evaluation.root_cause_services` |

### Step 3：对照 baseline 同一 round 范围在做什么

case 281 baseline 在 round 30-42 区间在做什么？

```
[Round 30-36] 都在 abnormal_traces 里查 ts-food-service 的 child spans
[Round 37+] reasoning 锁定 ts-food-service: "the only service in call chain showing Error"
```

baseline **从未跨进 normal_* 表**——这是 v4 mid M6 的因果价值所在。

---

## 6. 五大类信息一表速查

| # | 想看的信息 | 最快路径 | 文件/工具 |
|---|---|---|---|
| 1 | 注入 GT（具体打到哪个方法）| `cat injection.json` | `<source_data_dir>/injection.json` |
| 2 | GT 传播图（每个组件应该呈现什么状态）| `cat dossier_<DI>.md` | `analysis/3-failure-modes/.../dossiers/case_<DI>.md` |
| 2.alt | 原始 propagation 数据 | `cat causal_graph.json` | `<source_data_dir>/causal_graph.json` |
| 3 | agent 实际看到的数据（自己查 SQL）| `duckdb` on parquet | `<source_data_dir>/abnormal_*.parquet` 等 |
| 4 | baseline 错的完整轨迹 | dump 工具 → /tmp/case_baseline.txt | `dump_trajectory.py thinkdepthai-qwen3.5-plus <DI>` |
| 4 | v4 修复的完整轨迹（含干预点）| dump 工具 → /tmp/case_v4.txt | `dump_trajectory.py thinkdepthai-qwen3.5-plus-2026-02-15-mw-v4-run <DI>` |
| 4.alt | 干预 + 响应的精炼摘要 | `cat cache/<DI>.json` | `analysis/4-middleware/v4_forensic/cache/<DI>.json` |
| 5 | 干预在哪个 turn 起作用 | dump 工具找 `!!! 干预` 标记 + 后续 think_tool round + 看是否换 SQL 维度 | `/tmp/case<DI>_v4.txt` |

---

## 7. 已经为 case 281 准备好的文件（你直接打开就行）

```
/tmp/case281_baseline.txt     # baseline 轨迹（121 行，36 round，无干预）
/tmp/case281_v4.txt           # v4 轨迹（251 行，60 round，2 个干预 !!! 标记）
analysis/4-middleware/v4_forensic/cache/281.json  # 缓存摘要
analysis/3-failure-modes/2-by-framework/thinkdepthai-qwen3.5-plus/v2/dossiers/case_281.md  # GT dossier
data/ts0-ts-station-food-service-stress-j5qdln/converted/injection.json   # 原始注入
data/ts0-ts-station-food-service-stress-j5qdln/converted/causal_graph.json # 原始 propagation
```

打开 `/tmp/case281_v4.txt`：
- 干预 #1 在文件第 99-103 行（`!!! [v4 干预 #1] msg_idx=60`，对应 Round 30 → Round 31 之间）
- 干预 #2 在文件第 197 行（`!!! [v4 干预 #2] msg_idx=120`，对应 Round 59 → Round 60 之间）

要换其他 case，把 dump 命令的 `281` 改成你想看的 dataset_index 即可。12 个 saved 推荐 deep dive 的：
- **281** — M6 承重，T2 经典（已准备）
- **1114** — M5+M1 承重，silent restart 类（最有意思）
- **1394** — M7 承重，runtime CPU spike 找出 GT
- **4032** — M1+M5 同时承重，victim-vs-origin 分诊
- **4353** — M5 单独承重（无 secondary）的清流案例

要批量生成 12 个 saved 的 dump：

```bash
for di in 281 572 807 1114 1143 1394 2390 2988 3059 3716 4032 4353; do
  UTU_DB_URL="postgresql://postgres:postgres@localhost:5433/SOTA-Agents" \
    uv run --project RCAgentEval python analysis/4-middleware/v4_forensic/dump_trajectory.py \
    thinkdepthai-qwen3.5-plus $di > /tmp/case${di}_baseline.txt
  UTU_DB_URL="postgresql://postgres:postgres@localhost:5433/SOTA-Agents" \
    uv run --project RCAgentEval python analysis/4-middleware/v4_forensic/dump_trajectory.py \
    thinkdepthai-qwen3.5-plus-2026-02-15-mw-v4-run $di > /tmp/case${di}_v4.txt
done
```
