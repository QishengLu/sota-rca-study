# qwen3.5-plus thinkdepthai · Baseline 失败模式分类池

基于 53 case forensic 分析（OBSERVATIONS.md）归纳。只分析不加中间件的 baseline 轨迹失败。

后续需与 19 类行为意图模式（intention_category.md）结合分析。

---

## A 类（做错了什么 — 做了错误的归因动作）

| ID | 失败模式根因 | 导致 | 典型 case |
|---|---|---|---|
| **A1** | **级联噪声服务锚定**：把 abnormal 期 trace count 最高 / error 最多的服务当 RC，不追溯为何它噪声最大 | RC 锁定在 cascade 中段/末端 victim，chaos target 被排除 | 1917, 1948, 2211, 2253, 3760, 1814, 579 |
| **A2** | **503 / "Connection refused" 消息来源方向误读**：把 caller 日志中的 "failed to connect to X" 解读为 X 的故障，未独立验证 X 自身信号 | RC 锁定在 caller 报告对象（X），而非 chaos target | 99, 4375 |
| **A3** | **Chronic noise 当 incident-specific 信号**：把 normal 期同样存在的 ERROR 模式当作 incident 专属信号，未做 normal vs abnormal ratio 对比 | 长期背景噪声（RabbitMQ/DNS 等）被当 RC，占据候选池 | 4617, 2713, 2836 |
| **A4** | **服务沉默当 health 或 uninvolvement 证明**：把 trace count ≈ 0 / 无 ERROR 解读为"健康"（variant-a）或"不在调用链"（variant-b），不追溯沉默原因 | 因 chaos 而沉默的真 RC 被从候选池中排除 | 4617(b), PodChaos cases(a) |
| **A5** | **First-visible error timestamp 当因果起点**：以时间线最早出现的 ERROR 所在服务作为 RC anchor，混淆"时序第一"和"因果第一" | RC 锁定在 cascade 最上游 reporter，而非 chaos target | 4375 |
| **A6** | **Service-level avg wash-out / 幸存者偏差**：service avg ratio ≈ 1.0 时判定服务正常，未识别信号被掩盖：failed trace 未 export（幸存者偏差），或高延迟端点被大量快端点稀释 | 实际受 chaos 影响的服务因 avg 看似正常而被排除 | 1495, PodKill cases |
| **A7** | **Metric 语义 / domain 误读**：hubble 10s 时间窗 cap / deployment.available / jvm.system.cpu.load_1m 等未区分语义域（host-level vs pod-level, counter vs gauge） | metric 值被错误解读，对服务状态的判断（健康/异常）方向相反 | metric-heavy cases |
| **A8** | **多 caller 收敛 → 共同 target 归因不验证**：多个服务日志均指向同一 target 失败 → 认定 target 是 RC，未独立验证 target 自身 metric / restart / container resource | RC 锁定在多 caller 集中报告的服务，chaos target 无法浮现 | 4617, 2836 |

**定义边界**：
- A3 ≠ A8：A3 是单一 error pattern 的 chronicity 检测缺失；A8 是多 caller 收敛创造假"证据权重"。可共存但根因不同（4617 同时触发 A3 + A8）
- A4 ≠ A6：A4 是 data completely absent（trace count = 0）；A6 是 data present but misleading distribution

---

## B 类（没做什么 — 应该跑但没跑的关键 SQL）

| ID | 失败模式根因 | 做了可以获得 | 典型 case |
|---|---|---|---|
| **B1** | **Caller-callee 父子 span count edge ratio drop SQL 未跑** | NetworkChaos 决定性指纹：两端服务调用量暴跌（ratio < 0.1），直接定位 chaos 注入边的两侧服务 | 33, 784, 1195 |
| **B2** | **Specific metric by explicit name list 未查** | JVMChaos / ContainerKill 直接证据：`container.cpu.usage` / `k8s.container.restarts` / `jvm.cpu.recent_utilization` / `jvm.system.cpu.load_1m` 等，区分 chaos target 和 cascade victim | 156, 1218, 1459 |
| **B3** | **端点级 (service, span_name) duration distribution SQL 未跑** | 被 service avg 掩盖的高延迟端点信号，ratio 可达 5-20x，是 service-level avg 弱时的补充定位 | A6 相关 cases |
| **B4** | **候选 service 直接验证 SQL 未跑即 commit** | 假设的数据实证（restart count / trace count / specific metric），阻止纯凭 log 推断提交错误结论；含 commit 前对 alternative candidates 的 dismiss SQL | 多数 not-saved cases |
| **B5** | **全局 service-level baseline cross-scan 未跑** | 全局 ratio_avg 高和 ratio_count 低的双向排名，避免 silent RC（-99% trace）和 loud victim 双向漏检 | PodChaos / silence RC cases |
| **B6** | **Trace silence gap / count 断崖检测未做** | PodFailure / ContainerKill 核心 fingerprint：GT service abnormal trace count 接近 0，silence 本身就是最强 RC 信号 | PodChaos, ContainerKill cases |
| **B7** | **SEVERE log by message dedup SQL 未跑** | HTTPResponseReplaceBody 同质 exception 集中模式（N 行 JsonParseException 指向同一 URL），精确定位 chaos 路径 | HTTPResponseReplaceBody cases |

---

## C 类（agent 行为 / 认知层面问题）

| ID | 问题 | 具体表现 | 导致 |
|---|---|---|---|
| **C1** | **锚定后 rationalization loop** | 候选 RC 确定后，后续 round 不再真正测试假设，全用于寻找支持性证据；反证被解释掉而非触发重评 | 错误 RC 随轮次累积加固，翻转成本呈指数增长 |
| **C2** | **指令遵从缺口** | System prompt 明确要求的分析步骤（baseline 对比、specific metric 查询）在 agent 自认"已有结论"时被系统性跳过，而非偶发遗漏 | B 类缺失行为的根本来源：不是不知道要做，而是自判"不必要" |
| **C3** | **定性证据当 commit 充分条件** | 仅凭 log message 语义 / trace 排名 pattern 就输出 RC，未要求 duckdb 定量实证即视为"结论确定" | 结论建立在推断而非数据上；所有 A 类错误都因此无法被 SQL 纠正 |
| **C4** | **Investigation 过早收窄** | 看到第一个明显信号即深挖该 service，跳过全局视野建立阶段；investigation 结构从"广→窄→验证"退化为"直接窄→加固" | 全局候选池不完整，silent RC 和 ratio_count 极低的服务不进入视野 |
| **C5** | **Chaos 物理机制推理缺位** | 发现统计异常即归因，不问"此 chaos 类型物理上能产生这个信号吗"；把 cascade artifact / chronic noise 的统计 outlier 当 chaos 直接作用证据 | A 类归因错误的认知根因：统计相关被当因果，chaos 因果链从未被主动构建 |

**三表关系**（C 是 A/B 的元层解释）：
- C1 → 解释为什么 A 类错误跨多轮持续
- C2 → 解释 B 类缺失的系统性根因
- C3 → 解释 B4 反复出现的认知来源
- C4 → 解释 B5 的行为来源
- C5 → 解释 A1 / A2 / A3 / A8 的认知共因

---

## D 类（数据难点 — 数据本身的结构性困难）

不是 agent 推理能力问题，是即使推理正确也难以从数据层面定位 RC 的客观挑战。

| ID | 难点 | 机制 | 对应 A/B |
|---|---|---|---|
| **D1** | **级联信号放大**：RC 服务自身信号弱，上游 caller 积累的 error / retry 比 RC 本身更显著 | chaos 注入 RC 后，所有调用它的服务开始 retry / timeout，error 在 caller 端放大；RC 自身反而因请求失败而 trace count 下降 | A1, B5 |
| **D2** | **Trace export 失败导致幸存者偏差**：chaos 导致部分请求失败，失败请求的 trace 未 export，residual 均为成功快路径 | PodKill / ContainerKill 后新 pod 启动期间，请求失败但 span 未 export；service avg 由幸存 trace 计算，反映不出问题 | A6, B3 |
| **D3** | **RC 服务完全静默**：chaos 使 RC 无法产生任何 trace / log，absence of data 是最强信号但最难被发现 | PodFailure / JVMCPUStress 极端情况下 RC pod crash 或线程全阻塞，trace export 停止；数据层面 RC 服务"消失" | A4, B6 |
| **D4** | **Chronic noise 与 incident 信号共存**：normal 期已存在的 error 在 abnormal 期继续存在，淹没 incident-specific 信号 | RabbitMQ / DNS 等基础设施的连接错误与业务 chaos 信号混合，统计上无法直接区分 | A3 |
| **D5** | **Metric 聚合层级歧义**：同类指标在不同聚合层级（pod / container / host / cluster）含义不同，数值范围和解读规则各异 | hubble metrics 按 10s 窗口聚合；jvm.system.cpu.load_1m 是 worker node 级而非 pod 级；deployment.available 反映期望值偏差不是 pod 数 | A7 |

---

## E 类（推理难点 — 因果推断过程的内在困难）

即使 agent 执行了正确的 SQL，从数据到 RC 的因果推断本身存在的困难。

| ID | 难点 | 机制 | 对应 A/B/C |
|---|---|---|---|
| **E1** | **报告者 vs 责任方方向辨别**：error log 的 subject 是 reporter（caller），object 才是受影响方（可能是 RC），但两者混淆需要拓扑知识 | "ts-A failed to connect to ts-B" 是 ts-A 的日志，表达的是 ts-A→ts-B 这条边的状态；RC 可能是 ts-B，也可能是更下游，需要从 ts-B 自身 metric 独立确认 | A2, C5 |
| **E2** | **时序 vs 因果方向**：cascade 中 caller 先于 RC 可见错误（caller 先发现 downstream 不可达），时间线第一不等于因果链起点 | SLO 层最先报告降级，但它是 cascade 末端；RC 的 chaos 注入可能比 first-visible error 更早，且在 trace 层不可见 | A5, C5 |
| **E3** | **静默方向判断**：服务无 trace 可能是"没被调用"（正常），也可能是"被调用但无法响应/export"（chaos），需要结合调用拓扑和 restart 信号区分 | 调用链中 ts-A → ts-B，若 ts-B 无 abnormal trace：可能是 ts-A 调用失败（B 未收到），可能是 B crash（B 收到但不能处理），可能是正常路径不走这条边 | A4, E3 本身需要拓扑验证 |
| **E4** | **Chaos 物理机制 → 预期信号 推断链**：不同 chaos 类型在数据层产生不同 fingerprint，需要从 chaos 机制反向推导哪些 metric / trace pattern 是预期信号，哪些是 cascade artifact | NetworkBandwidth 让 edge ratio 暴跌但不一定让单 service avg 显著升高；JVMCPUStress 让 container.cpu 飙升但 service trace count 可能下降；不理解物理机制就无法区分直接信号和级联噪声 | C5, A1, A3 |
| **E5** | **多维证据一致性校验**：单一维度（trace / log / metric 之一）的信号不足以确认 RC，但跨维度综合推断的认知负担大，容易在某维度"找到"支持就停止 | RC 的确认需要 trace count drop + specific metric spike + restart 计数 + 调用链位置 四维交叉；任一单维信号都可能是 false positive | C3, B4 |

---

## 特殊 case 归类备注

| Case | 归类 | 说明 |
|---|---|---|
| 4375 | A2 + A5 | 503 provenance 误读 + first-error timestamp 因果推断 |
| 4463 | **排除** | dataset label bug（correct_answer 与 injection_point 矛盾） |
| 4617 | A3 + A4(b) + A8 + B4 | chronic noise + silence-as-uncalled + 多 caller 收敛归因 + 无直接验证 SQL |

---

## TODO

- [ ] 将 A/B/C/D/E 模式与 19 类行为意图（intention_category.md）对应分析：哪些意图类型对应哪些失败模式，哪些意图类型缺失导致哪些 D/E 难点被暴露
- [ ] 统计每个 A/B label 在 53 cases 中的覆盖频次
- [ ] 基于 C 类认知问题 + D/E 难点设计新中间件提示维度
