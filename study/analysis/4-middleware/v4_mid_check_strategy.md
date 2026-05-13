# v4 中期检查时机 — 三 framework 统一决策（D-7.5）

**Plan**: [/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md](/home/nn/.claude/plans/agent-thinkdepthai-high-level-high-leve-quiet-cascade.md)
**设计原则**: [v4_principles.md](v4_principles.md)（原则 6）
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-7.5 阶段）

---

## 文档目的

原则 6 列出中期检查点的三个候选策略 A/B/C，留到 D-5/D-6/D-7 实施阶段——现在三个 framework 适配层（thinkdepthai / aiq / claudecode）都已写完，本文档**统一决策每个 framework 选哪个策略 + 具体阈值**。

- 候选 A：P25 固定点（该 framework failed case 的 query/round count P25）
- 候选 B：动态触发（监听 reasoning 中近收敛信号）
- 候选 C：取消中期（只保留结论前，干预预算 0+1）

---

## 基础数据：effective_rounds 分布

从 PostgreSQL `meta.cost_metrics.effective_rounds` 字段算出（effective_rounds = 带 `tool_calls` 的 assistant 消息数，衡量 agent 推理轮数）。

### Failed case（v4 中期检查的目标人群）

| Framework | N | P25 | P50 | P75 | max |
|---|---:|---:|---:|---:|---:|
| thinkdepthai-qwen3.5-plus | 105 | 41 | 51 | 60 | 86 |
| thinkdepthai-claude-sonnet-4.6 | 51 | 30 | 36 | 44 | 70 |
| aiq-qwen3.5-plus | 113 | 47 | 54 | 62 | 78 |
| claudecode-qwen3.5-plus | 103 | 52 | 59 | 74 | 140 |

### Correct case（对照 — 成功 agent 的自然轨迹长度）

| Framework | N | P25 | P50 | P75 | max |
|---|---:|---:|---:|---:|---:|
| thinkdepthai-qwen3.5-plus | 395 | 32 | 42 | 52 | 91 |
| thinkdepthai-claude-sonnet-4.6 | 449 | 22 | 28 | 36 | 123 |
| aiq-qwen3.5-plus | 387 | 43 | 49 | 57 | 80 |
| claudecode-qwen3.5-plus | 397 | 41 | 49 | 60 | 104 |

### 关键观察

1. **thinkdepthai（qwen + sonnet）**：failed 比 correct 长（qwen: P50 51 vs 42；sonnet: P50 36 vs 28）——失败常伴长跑重复探查（对应 M9 模式）。中期介入窗口宽。
2. **aiq**：failed 与 correct 分布高度相似（P50 54 vs 49）——aiq 的固定 2 次 reflect 约束让轨迹长度趋同。这使得**round count 不是 aiq 失败的区分信号**；aiq 更适合 stage 边界策略（候选 A 的变体）。
3. **claudecode**：failed 与 correct 也相近（P50 59 vs 49）但 failed 有长尾（max 140 vs 104）。`claude -p` 一次性架构让中期介入实现成本高。

---

## 每 framework 决策

### thinkdepthai (qwen + sonnet) — 候选 A（correct-case P25 anchor）

**选择理由**：
- failed case 比 correct case 长 → 大部分 failed 在 correct P25 时仍在进行中，介入时机合理
- correct P25 代表"成功 agent 的自然 mid-investigation 时刻"——在此时介入相当于"告诉还在 mid 阶段的 failed agent 该反思了"
- 用 correct P25 而非 failed P25 作 anchor：failed P25 太晚（41/30），会错过本可以早期纠偏的 case
- 实现成本低：LangGraph 节点条件谓词，按 round count 判断

**具体阈值**：

| Framework | mid_check 触发 round | 剩余空间（failed P50 - 触发点）|
|---|:---:|---:|
| thinkdepthai-qwen3.5-plus | **round = 30**（对齐 correct P25=32 + 略早）| 51 - 30 = 21 round 剩余 |
| thinkdepthai-claude-sonnet-4.6 | **round = 22**（对齐 correct P25=22）| 36 - 22 = 14 round 剩余 |

**实施语义**：`state.round_count >= threshold AND not state.mid_check_done` 时触发；round 计数从 0 开始，取 `len(state.researcher_messages 中 AIMessage 带 tool_calls)`。

**为什么不是 failed P25（=41/30）**：failed P25 处 25% failed 已结束/接近结束，中期介入对这部分 case 已然来不及；correct P25 anchor 让介入早于大多数失败进入"难挽回"阶段。

**冲突检查**：
- 若 case 的 round count < 触发值就自然结束（比如 agent 提前 commit），中期检查**不触发**——由结论前检查（compress 之前）覆盖
- 若 case round count 远超触发值但仍在工作，中期只介入一次（per-case 状态记 `mid_check_done=true`）

---

### aiq (qwen) — 候选 A stage-边界变体（stage_0_main terminator 后）

**选择理由**：
- aiq 有天然的 stage 边界：stage_0_main → build_graph → reflect_on_graph (×2) → finalize
- round count 分布显示 aiq failed vs correct 几乎重合（P50 54 vs 49）——round 不是失败信号
- stage_0_main 是"主调查阶段"，在它结束后注入反思 prompt，恰是 "完成主查、即将反思" 的窗口
- 实现简单：在 agent_runner.py 的 data_research 节点 return 前插钩子（已在 [v4_aiq_qwen3.5_plus/README.md](v4_aiq_qwen3.5_plus/README.md) 详细设计）

**具体触发点**：

```
aiq 的 data_research 节点 run_data_exploration sub-loop 结束后：
  if state.mid_check not done:
    L1/L2/L3 合并调用 → 若 triggered，intervention 作为额外
                         HumanMessage 注入到 reflect_on_graph
                         第 1 次 run_refine_exploration 的 messages 头部
```

**边界条件**：
- stage_0_main 跑到 max_rounds=60 仍未 terminator：触发 A1 (Stage-Commitment Discipline) 主问 — 这是 A1 的核心 trigger 场景
- stage_0_main 提前 terminator（~P25 → round 47）：介入点同样在 terminator 后、build_graph 之前；此时 round count 已较多，主问倾向 M6/M7/M9/A1

**与 thinkdepthai 策略对比**：
- thinkdepthai 按 round count 固定阈值触发（candidate A 原版）
- aiq 按 stage 边界触发（candidate A stage-variant）——二者都是 candidate A 的两种实现

---

### claudecode (qwen) — 候选 C（取消中期检查，保留结论前）

**选择理由**：
- `claude -p` 一次性 prompt → 流式输出 → 进程结束的架构；中途注入需要 kill 进程 + `claude --resume <session_id> -p <intervention>` 多轮机制
- kill 进程可能丢 Claude Code 内部的 thinking / TODO 状态；--resume 的 session 持久化机制依赖 Claude Code 内部实现，跨版本不稳定
- failed vs correct 分布相似（P50 59 vs 49）——没有强 round-count 失败信号支持中期介入
- 结论前检查已有**天然注入窗口**（compress 调用前，是独立 Anthropic SDK LLM 调用）——实现成本低
- **v4 初次部署优先选简单方案**：取消中期（0 次）+ 结论前 1 次 = 总 1 次干预

**具体触发点**：无中期检查；结论前检查照原计划在 `_compress_to_json` 之前介入。

**代价**：
- 失去对 long-trajectory 失败（max 140 round）的中期纠偏能力
- 失去 C2 (Layer-Coverage) / M6 (Baseline) / M9 (Stagnation) 这三个"越早提醒越好"的维度的中期主用角色——这些维度降级为结论前**补救**角色（见 [v4_claudecode_qwen3.5_plus/README.md](v4_claudecode_qwen3.5_plus/README.md)）

**Phase 8 升级路径**（可选）：
- 若 claudecode v4 首次部署 AC@1 提升不及预期（< +5pp），可在 Phase 8 投入实现 kill + --resume 机制，升级为候选 A
- 需额外小样本 A/B（15 case）验证 kill + --resume 不会破坏 Claude Code 内部状态

---

## 决策汇总表

| Framework | 策略 | 触发点 | 总干预次数 | 实现复杂度 | 备注 |
|---|---|---|---:|---|---|
| thinkdepthai-qwen3.5-plus | 候选 A（correct-P25 anchor）| round == 30 | 1 中 + 1 结 = 2 | 低（LangGraph conditional edge）| failed 比 correct 长，介入时机安全 |
| thinkdepthai-claude-sonnet-4.6 | 候选 A（correct-P25 anchor）| round == 22 | 1 中 + 1 结 = 2 | 低（同上）| sonnet 轨迹更短，触发值相应前移 |
| aiq-qwen3.5-plus | 候选 A stage-变体 | stage_0_main terminator 之后 | 1 中 + 1 结 = 2 | 中（agent_runner.py 节点钩子）| 天然 stage 边界，无需算 round P25 |
| claudecode-qwen3.5-plus | 候选 C（取消中期）| — | 0 中 + 1 结 = 1 | 低（compress_up 注入）| `claude -p` 架构让中期介入太复杂 |

**总体设计权衡**：
- thinkdepthai / aiq：1+1 干预预算，较保守的高质量介入
- claudecode：0+1 干预预算，牺牲中期覆盖换实现简化 + 不破坏 Claude Code CLI 状态

---

## 回填到各适配层文档

按本决策更新：

### thinkdepthai
- [v4_thinkdepthai_qwen3.5_plus.md](v4_thinkdepthai_qwen3.5_plus.md) "⏸ 中期检查点触发时机" 节已留占位，D-7.5 回填值：
  - thinkdepthai-qwen3.5-plus: `mid_check_trigger_round_count = 30`
  - thinkdepthai-claude-sonnet-4.6: `mid_check_trigger_round_count = 22`

### aiq
- [v4_aiq_qwen3.5_plus/README.md](v4_aiq_qwen3.5_plus/README.md) "中期检查点触发时机" 节已倾向候选 A（stage_0 末尾），D-7.5 确认锁定：
  - `mid_check_trigger_position = "post_stage_0_main_terminator"`

### claudecode
- [v4_claudecode_qwen3.5_plus/README.md](v4_claudecode_qwen3.5_plus/README.md) "中期检查点触发时机" 节倾向候选 C，D-7.5 确认锁定：
  - `mid_check_enabled = false`（取消中期；总干预次数 = 1）

---

## 下游影响

### 原则 5 "总干预次数上限" 的修订

原原则 5 写"**总共 ≤ 2 次**"。claudecode 实际是 ≤ 1 次（0 中 + 1 结）。修订表述为：

> 每个 case 干预次数上限 = **中期 0 或 1 次 + 结论前 1 次**（总共 ≤ 2 次，按 framework 策略决定）。

### 启用维度矩阵调整（claudecode）

claudecode 的中期检查被取消 → 原中期主用维度（M6/M7/M9/C2）在 claudecode 上**全部降级为结论前补救**。已在 [v4_claudecode_qwen3.5_plus/README.md](v4_claudecode_qwen3.5_plus/README.md) 的 L2 评估池表格体现；无需再改。

### opus-4.7 调用接口

- thinkdepthai / aiq 中期调用时 C1_framework + check_point="mid" + A2 主用池 = 框架-specific 主用维度
- claudecode 无中期调用
- 结论前调用三 framework 统一

---

## 验证计划（Phase 8 实施时做）

1. **离线重放测 trigger 覆盖率**：
   - thinkdepthai-qwen：105 failed case 中，多少在 round 30 时还未 commit → 能被中期检查触及
   - 同理 sonnet / aiq / claudecode
2. **小样本 A/B（每 framework 15 case）**：
   - thinkdepthai：candidate A 触发 vs 不触发
   - aiq：stage 边界 vs 取消中期
   - claudecode：取消中期 vs 尝试 kill+--resume（若实现可行）
3. **成本度量**：
   - 中期 check 失败率（因 round 计数不准 / stage 边界提取错误导致的误触发）
   - 中期 check 误伤率（correct case 被误触发且变 wrong）

验证结果按 plan Part E 报告。

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-7.5 阶段输出）；三 framework 分别锁定：thinkdepthai = candidate A (round 30 / 22)，aiq = candidate A stage-变体 (post_stage_0_terminator)，claudecode = candidate C (取消中期) |
