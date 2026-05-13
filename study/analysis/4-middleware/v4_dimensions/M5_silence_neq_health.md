# M5 — Silence ≠ Health

**速查表**: [README.md](README.md)
**设计原则**: [../v4_principles.md](../v4_principles.md)
**版本**: v4-draft 2026-04-22
**审核状态**: ⏳ 待审核（D-2 阶段）

---

## 来源 mapping

| 标注体系 | 类别 | 描述 | 372 case 中数量 |
|---|---|---|---:|
| **R 层** | `U5_SilenceReadAsHealthOrPaused` | agent 看到某服务的"零错误/Unset 状态/没活动"信号，明确推断该服务"健康"或"被暂停"，从而把它从候选里排除——但实际上该服务是死掉/被卡住/被网络隔离 | **17** |
| **R 层** | (历史) v3 中间件的 M3 维度 (Absence ≠ Health) — v4 中用 M5 取代 | 同上 | (sonnet 单一框架经验) |
| **D 层** | D1 (VictimSilentOnPath) — 数据形态背景：silent 服务可能就是 GT，作为"也可能没在工作"素材 | (背景) |

**对应失败 case 数（M5 主问触发的初步估计）**：
- 宽松命中 (U5 单独)：17 case
- M5 主问的目标 case 池：~15-25 case

**Per-framework 分布**（来自 unified_R.md）：
- aiq-qwen3.5-plus: 0 / 113 = 0%
- claudecode-qwen3.5-plus: 0 / 102 = 0%
- thinkdepthai-claude-sonnet-4.6: 0 / 50 = 0%
- thinkdepthai-qwen3.5-plus: 17 / 105 = 16.2%（**唯一 framework**）

**Framework 启用注意**：U5 标注里只在 qwen 出现是因为 qwen 推理常显式表达"X is healthy because no errors"这种文本特征明显的判断。其他 framework 可能也犯类似错误但被吸收到 U1 (silent victim shadowing) 里。M5 trigger 是文本特征 + 行为缺失，跨 framework 通用，全启用但翻盘期望主要在 qwen。

---

## Cognitive vocabulary

**这种认知模式是什么样**：

agent 在调查中查到某服务的数据：error count = 0 / 几乎所有 trace 都是 status_code='Unset' / 没有 latency 异常 / 没有 metric 突起。agent 的 reasoning 段（think_tool 反思 / assistant.content）出现一种**显式健康推断**：
- "This service shows no errors, so it appears healthy"
- "Status is Unset, indicating successful execution"
- "The service is fine"
- "PROCESS_PAUSED, deployment is healthy"
- "This service is idle / frozen"

这个推断**本身是合理的启发式**——绝大多数情况下"无错误"≈"工作正常"。但失败模式是：当真正的故障是"该服务被杀掉了 / 进程卡死 / 网络断了导致请求都不到达 / 上层断流不再调用它"时，"零错误"恰恰是"它没在工作"的指纹，不是健康指纹。

agent 把"零错误"等同于"健康"，于是把这个候选从根因列表里**主动排除**，转向其他响亮的候选——就这样错过了真正的故障源。

**反思的认知动作**：当 agent 用"零错误/Unset"作为排除某候选的依据时，主动反问"**它真的在正常工作，还是它根本没有在工作？**"——这个反问区分了两种"零错误"：（a）正常处理但没事故的零错误（健康）vs（b）压根没收到请求 / 没启动 / 卡死的零错误（异常）。

---

## Trigger abstract（运行时可观察）

```pseudo
trigger_M5(state) :=
  (LET health_inference_keywords = {
        "no error", "no errors", "healthy", "successful",
        "fine", "idle", "paused", "frozen", "plateau",
        "PROCESS_PAUSED", "deployment.available",
        "appears healthy", "looking healthy", "正常", "健康"
   }
   LET reasoning_text = state.reasoning_log[ last_K_rounds = 6 ]
   LET health_assertions = EXTRACT_PATTERNS(
        reasoning_text,
        pattern = "<service_name> + (is|appears|looks|seems) + <health_keyword>"
   )
   //  health_assertions 是 [(service_name, assertion_text)] 列表
   //  示例：("S_X", "S_X appears healthy because no errors")

   LET problematic_assertions = []
   FOR EACH (service, assertion) IN health_assertions:
        LET activity_check_count = COUNT(state.intent_log
            WHERE target_service == service
            AND intent IN { 'throughput_compare', 'latency_ranking',
                            'service_trace_scan' }   // 检查活动度的 intent
            AND occurred_after(assertion.timestamp))
        IF activity_check_count == 0:
            APPEND problematic_assertions <- (service, assertion)

   IN LENGTH(problematic_assertions) >= 1)
```

**触发场景示例**：
- thinkdepthai (qwen)：think_tool 反思中出现 "ts-X shows no errors, appears healthy"，但 agent 之前没对 ts-X 跑过 `throughput_compare` 或 `service_trace_scan`（即没验证 ts-X 是否还在接收请求）
- claudecode：reasoning 段写 "service S looks fine, status is Unset", 但没查 S 的 incoming traffic
- aiq：stage_0 reasoning 中显式排除某服务因为 "no error logs"

---

## Intervention pattern

### 主问（M5 作为 most_critical 时）

> **你刚说某个服务"正常"或"健康"，依据是它没产生错误。但这个判断有可能错——它也可能根本没在工作（被卡住、被停掉、停止接收请求了）。"零错误"既可能是"它在正常处理且没遇到事故"，也可能是"它根本没收到请求所以没机会出错"。在你把这个服务从候选里排除前，能不能先确认它确实有正常的活动迹象？**

**变体**：
- 变体 A（中期检查，agent 刚做出健康推断准备转向别处）：
  > "你刚才推断某个服务正常/健康，依据是它没产生错误。但'零错误'本身不能区分两种情况：(a) 这个服务在正常工作但没出问题，或者 (b) 这个服务根本没在工作所以没机会出错。在你把它从候选里排除之前，能不能先看看它是不是还在接收请求/产生 trace？"
- 变体 B（结论前检查，agent 即将提交但 root_causes 没有那个被推断"健康"的服务）：
  > "你即将提交的根因列表里，没有你之前推断为'健康'的某个服务。但你的'健康'判断只基于'没错误'，没验证它是不是还在工作。在最终提交前请确认：你排除的那个服务，是真的在正常运行，还是它可能根本没活动？"

### 次问（M5 作为次级命中、其他维度作主问时）— 长度限制 1 句

> "另外你之前用'没错误'排除了某个服务，可以顺带核对一下：它是真的在正常工作，还是根本没在工作？"

**次问触发条件**：M5 作为次问被加入复合干预，**仅当** L2 对 M5 给出 `match_score ≥ 0.7`（即 L2 真的从 reasoning 文本里检测到健康推断 + 该服务无活动度验证）。如果 reasoning 中没有显式健康推断，L2 给低分，**不加 M5 次问**。

---

## 自检清单 — 为什么这是元认知

- [x] **Trigger 不引用 GT 字段**（trigger 用 reasoning 文本特征 + intent 历史，**不和** `gt_services` 比，**不查询** GT 是不是 silent）
- [x] **Trigger 不含 SQL 字符串**（用 intent 抽象类别 + 文本 pattern matching）
- [x] **Trigger 不含具体服务名**（health_assertions 中的 service_name 是变量；keyword 列表是通用英文/中文健康词，不是领域错误消息字串）
- [x] **Intervention 不含 SQL 字符串**（主问/次问全文无 SELECT/FROM/WHERE）
- [x] **Intervention 不含具体服务名**（用"某个服务"、"它"指代）
- [x] **Intervention 不含错误消息字串**（无 UnknownHostException 等；keyword 是通用健康词，不是领域错误消息）
- [x] **Intervention 不含上游/下游/源/汇/受害者等方向性词**（用"被卡住"、"被停掉"、"停止接收请求"、"没在工作"——这些是描述服务自身状态的中性词，不是拓扑方向词）
- [x] **Intervention 用反问 + 多种可能性句式**（"既可能是 X，也可能是 Y"——经典开放对比）
- [x] **agent 可基于自身已做的动作自我修正**（"你刚说某个服务'正常'或'健康'"——直接引用 agent 的 reasoning 文本）

**全部 9/9 ✓ → M5 卡片符合 v4 元认知设计原则**

**审核风险点**：
1. **关键词列表是否暗示答案**？keyword 都是 agent reasoning 中可能出现的"健康判断词"，不是数据集特有的服务名/错误消息。M5 用这些词检测"agent 做出了健康推断"这件事本身，不告诉 agent "你应该选哪个"。**判定**：不暗示答案。
2. **"停止接收请求 / 上游断流"是否是方向性词**？"上游断流"我没用——主问改成"停止接收请求"是中性的（描述服务状态而非方向）。**判定**：通过。
3. **跨 framework 启用是否合理**？U5 标注只在 qwen，但 trigger 是文本特征+行为缺失，aiq/claudecode/sonnet 都可能犯类似错误（只是没被独立标注为 U5）。trigger 通用启用，期望翻盘主要在 qwen 但其他 framework 偶尔受益。**判定**：合理。

---

## 适用 framework

| Framework | 启用 | 备注 |
|---|:---:|---|
| thinkdepthai (qwen3.5-plus) | ✓ 主问候选 | 16.2% U5，**唯一显式标注 framework**；中期检查时优先 |
| thinkdepthai (claude-sonnet-4.6) | ✓ 主问候选 | 0% U5，但 trigger 通用可能捕捉到 |
| aiq (qwen3.5-plus) | ✓ 主问候选 | 0% U5，但 stage_0 reasoning 可能含健康推断 |
| claudecode (qwen3.5-plus) | ✓ 主问候选 | 0% U5，但 reasoning 段可能含健康推断 |

---

## 期望 wrong→correct 翻盘贡献（初步估计）

| Framework | failure case 总数 | U5 占比 | M5 主问命中估计 | M5 翻盘期望（按 40% 翻盘率） |
|---|---:|---:|---:|---:|
| thinkdepthai-qwen3.5-plus | 105 | 16.2% | ~17 | **~7 case 翻盘** |
| thinkdepthai-claude-sonnet-4.6 | 50 | 0% | ~2（隐含 case） | ~1 case 翻盘 |
| aiq-qwen3.5-plus | 113 | 0% | ~3 | ~1 case 翻盘 |
| claudecode-qwen3.5-plus | 102 | 0% | ~3 | ~1 case 翻盘 |

**总翻盘期望**：~10 case 跨 4 framework，主要集中在 thinkdepthai-qwen。

---

## 与其他维度的潜在冲突

| 冲突维度 | 冲突场景 | L2 消歧规则 |
|---|---|---|
| **M1 (Loudness-Anchor)** | M5 触发时 agent 通常已选了一个响亮的非 silent 服务作 RC | M1 关注"为什么选了响亮的"，M5 关注"为什么排除了 silent 的"。两者互补，可同时命中（L2 选最 critical 作主问，另一个作次问）|
| **M3 (Output-Graph Consistency)** | M5 触发时被 agent 推断为"健康"的服务通常不在 root_causes 里（被显式排除） | M3 关注 graph 内部一致性（自标 problem 的非 root），M5 关注健康推断本身。可同时命中 |
| **M9 (Investigation Stagnation)** | M5 触发后 agent 可能转向别处不再调查被排除的服务 → 可能进入对其他候选的反复探查 → 触发 M9 | 不同 trajectory 阶段，时间序不重叠 |

---

## 实施备注

- **关键依赖**：
  - L1 必须解析 reasoning 文本（think_tool 反思 + assistant.content），不只是 SQL
  - 文本 pattern matching 用正则 + opus-4.7 LLM 二级判定（避免简单关键词误伤）
  - "活动度检查 intent" 的定义：`throughput_compare` / `service_trace_scan` / `latency_ranking` 都算（这些 intent 的结果能反映服务是否在产生 trace/请求/活动）
- **trigger 阈值校准**：keyword 列表 D-2 审核可增减；目前包含中英文健康词。当前 keyword 偏向 qwen 风格，aiq/claudecode/sonnet 上可能 recall 偏低
- **离线重放验证**：在 372 已标注 case 上跑 trigger，统计 (precision, recall) 相对于 U5 标注（thinkdepthai-qwen 上 recall 有意义；其他 framework 由于 U5=0 只看 precision）

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| draft 2026-04-22 | 2026-04-22 | 初版（D-2 阶段输出） |
