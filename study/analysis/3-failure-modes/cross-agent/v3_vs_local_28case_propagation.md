# V3 vs LOCAL — 28 case 实际传播路径对比

基于 trace parquet 直接构建的实际 cascade（按 trace_id 聚合包含 RC 服务的所有 trace），对比 V3 GT 与 LOCAL GT 的服务级差异。

## 标注约定

- ⚠️  = LOCAL 有 / V3 漏 / 且确实在实际 cascade 路径上（**真漏**）
- ✗  = LOCAL 有 / V3 漏 / 但不在实际 cascade（V3 漏对了）
- ✓  = V3 包含 + 在 cascade 上
- [RC] = root cause service

**cascade 定义**：所有 abnormal_traces 中 trace_id 包含 RC 服务的 trace 涉及的服务集合。

---

## 总表（按真漏数倒排）

| # | case | fault_type | RC | cascade | L | V | L−V | **真漏数** | 真漏 services |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| 1 | `ts3-ts-basic-service-partition-w5hbjw` | NetworkPartition | `ts-basic-service` | 21 | 7 | 7 | 5 | **5** | `loadgenerator`, `ts-basic-service`, `ts-route-plan-service`, `ts-travel-plan-service`, `ts-travel2-service` |
| 2 | `ts0-ts-station-service-bandwidth-bp5k94` | NetworkBandwidth | `ts-station-service` | 21 | 9 | 5 | 4 | **4** | `loadgenerator`, `ts-route-plan-service`, `ts-travel-plan-service`, `ts-travel2-service` |
| 3 | `ts3-ts-order-service-container-kill-gh2xcv` | ContainerKill | `ts-order-service` | 24 | 11 | 6 | 5 | **4** | `loadgenerator`, `ts-route-plan-service`, `ts-security-service`, `ts-travel2-service` |
| 4 | `ts4-ts-order-other-service-exception-nh22zm` | JVMException | `ts-order-other-service` | 21 | 11 | 7 | 4 | **3** | `loadgenerator`, `ts-route-plan-service`, `ts-travel2-service` |
| 5 | `ts0-ts-travel-service-mysql-28wmss` | JVMMySQLLatency | `ts-travel-service` | 23 | 6 | 4 | 2 | **2** | `loadgenerator`, `ts-preserve-service` |
| 6 | `ts2-ts-order-other-service-container-kill-48rlds` | ContainerKill | `ts-order-other-service` | 22 | 11 | 8 | 3 | **2** | `loadgenerator`, `ts-route-plan-service` |
| 7 | `ts2-ts-seat-service-stress-b7h7m9` | JVMMemoryStress | `ts-seat-service` | 21 | 9 | 7 | 2 | **2** | `loadgenerator`, `ts-route-plan-service` |
| 8 | `ts2-ts-station-service-dns-nn49s2` | DNSRandom | `ts-station-service` | 21 | 9 | 13 | 2 | **2** | `loadgenerator`, `ts-route-plan-service` |
| 9 | `ts3-ts-basic-service-stress-p545b4` | JVMMemoryStress | `ts-basic-service` | 21 | 9 | 7 | 2 | **2** | `loadgenerator`, `ts-preserve-service` |
| 10 | `ts4-ts-station-service-bandwidth-nfljv5` | NetworkBandwidth | `ts-station-service` | 17 | 9 | 7 | 2 | **2** | `loadgenerator`, `ts-preserve-service` |
| 11 | `ts0-ts-travel-plan-service-response-delay-pfwcqk` | HTTPResponseDelay | `ts-travel-plan-service` | 15 | 3 | 2 | 1 | **1** | `loadgenerator` |
| 12 | `ts0-ts-travel2-service-request-delay-lzpl9v` | HTTPRequestDelay | `ts-travel2-service` | 15 | 5 | 4 | 1 | **1** | `loadgenerator` |
| 13 | `ts1-ts-station-food-service-stress-rlvxhc` | JVMMemoryStress | `ts-station-food-service` | 7 | 5 | 15 | 1 | **1** | `loadgenerator` |
| 14 | `ts1-ts-train-service-pod-failure-5qwqdz` | PodFailure | `ts-train-service` | 13 | 10 | 6 | 4 | **1** | `ts-route-plan-service` |
| 15 | `ts2-ts-travel-plan-service-response-delay-chhzjz` | HTTPResponseDelay | `ts-travel-plan-service` | 15 | 3 | 2 | 1 | **1** | `loadgenerator` |
| 16 | `ts3-ts-order-service-pod-failure-7xsmwd` | PodFailure | `ts-order-service` | 3 | 13 | 7 | 6 | **1** | `loadgenerator` |
| 17 | `ts3-ts-preserve-service-container-kill-k7k8g5` | ContainerKill | `ts-preserve-service` | 18 | 4 | 2 | 2 | **1** | `loadgenerator` |
| 18 | `ts3-ts-travel-plan-service-exception-zgsz8w` | JVMException | `ts-travel-plan-service` | 15 | 4 | 2 | 2 | **1** | `loadgenerator` |
| 19 | `ts3-ts-travel-plan-service-request-delay-kxhn5n` | HTTPRequestDelay | `ts-travel-plan-service` | 15 | 3 | 2 | 1 | **1** | `loadgenerator` |
| 20 | `ts3-ts-travel-service-container-kill-jctldw` | ContainerKill | `ts-travel-service` | 23 | 7 | 5 | 2 | **1** | `loadgenerator` |
| 21 | `ts3-ts-travel2-service-container-kill-72qrd2` | ContainerKill | `ts-travel2-service` | 15 | 6 | 4 | 2 | **1** | `loadgenerator` |
| 22 | `ts3-ts-travel2-service-container-kill-vt4nvr` | ContainerKill | `ts-travel2-service` | 15 | 6 | 4 | 2 | **1** | `loadgenerator` |
| 23 | `ts4-ts-route-plan-service-bandwidth-q5lcsx` | NetworkBandwidth | `ts-route-plan-service` | 15 | 4 | 5 | 1 | **1** | `loadgenerator` |
| 24 | `ts4-ts-seat-service-bandwidth-k2bwt2` | NetworkBandwidth | `ts-seat-service` | 15 | 8 | 7 | 2 | **1** | `loadgenerator` |
| 25 | `ts4-ts-seat-service-delay-ddn72q` | NetworkDelay | `ts-seat-service` | 21 | 8 | 7 | 1 | **1** | `loadgenerator` |
| 26 | `ts5-ts-preserve-service-partition-dkhqzh` | NetworkPartition | `ts-preserve-service` | 18 | 3 | 4 | 1 | **1** | `loadgenerator` |
| 27 | `ts5-ts-travel-plan-service-delay-v5ptlf` | NetworkDelay | `ts-travel-plan-service` | 15 | 3 | 6 | 1 | **1** | `loadgenerator` |
| 28 | `ts7-ts-travel-service-response-delay-t48wrc` | HTTPResponseDelay | `ts-travel-service` | 23 | 5 | 4 | 1 | **1** | `loadgenerator` |

**汇总**: V3 比 LOCAL 少 63 个服务实例；其中 **46 个 (73%) 在实际 cascade 路径上属真漏**；17 个不在 cascade 内（V3 过滤对了）。

**排除 loadgenerator 后**（V3 设计上不打 loadgen 节点）：
- V3 真漏（不含 loadgen） = **19 个 service-instance** 跨 28 case
- 受影响 case 数 = **11 / 28**（其余 case V3 完全 cover 了真路径）

**高频被漏的真路径服务**（非 loadgen）:

| 服务 | 被漏次数 / 28 case |
|---|---:|
| `ts-route-plan-service` | 8 |
| `ts-travel2-service` | 4 |
| `ts-preserve-service` | 3 |
| `ts-travel-plan-service` | 2 |
| `ts-basic-service` | 1 |
| `ts-security-service` | 1 |

---

## 每 case 详情

## Case 1: `ts3-ts-basic-service-partition-w5hbjw`

- **RC**: `ts-basic-service`
- **cascade 服务数**: 21
- **LOCAL 服务**: 12, **V3 服务**: 7, **L−V**: 5
- **真漏 (在 cascade 上)**: 5

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-basic-service[RC]
L1: ts-preserve-service | ts-price-service✓ | ts-route-service | ts-station-service | ts-train-service | ts-travel-service✓ | ts-travel2-service⚠️
L2: ts-assurance-service | ts-contacts-service | ts-food-service | ts-order-service✓ | ts-route-plan-service⚠️ | ts-seat-service | ts-security-service | ts-travel-plan-service⚠️ | ts-ui-dashboard✓ | ts-user-service
L3: loadgenerator⚠️ | ts-config-service | ts-order-other-service✓
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service⚠️ → ts-price-service✓
ts-basic-service⚠️ → ts-route-service
ts-basic-service⚠️ → ts-station-service
ts-basic-service⚠️ → ts-train-service
ts-preserve-service → ts-assurance-service
ts-preserve-service → ts-basic-service⚠️
ts-preserve-service → ts-contacts-service
ts-preserve-service → ts-food-service
ts-preserve-service → ts-order-service✓
ts-preserve-service → ts-seat-service
ts-preserve-service → ts-security-service
... +23 more edges
```

**V3 漏的真路径节点**: `loadgenerator`, `ts-basic-service`, `ts-route-plan-service`, `ts-travel-plan-service`, `ts-travel2-service`

---

## Case 2: `ts0-ts-station-service-bandwidth-bp5k94`

- **RC**: `ts-station-service`
- **cascade 服务数**: 21
- **LOCAL 服务**: 9, **V3 服务**: 5, **L−V**: 4
- **真漏 (在 cascade 上)**: 4

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-station-service[RC]
L1: ts-basic-service✓
L2: ts-preserve-service✓ | ts-price-service | ts-route-service | ts-train-service | ts-travel-service✓ | ts-travel2-service⚠️
L3: ts-assurance-service | ts-contacts-service | ts-food-service | ts-order-service | ts-route-plan-service⚠️ | ts-seat-service | ts-security-service | ts-travel-plan-service⚠️ | ts-ui-dashboard✓ | ts-user-service
L4: loadgenerator⚠️ | ts-config-service | ts-order-other-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service✓ → ts-price-service
ts-basic-service✓ → ts-route-service
ts-basic-service✓ → ts-station-service✓
ts-basic-service✓ → ts-train-service
ts-preserve-service✓ → ts-assurance-service
ts-preserve-service✓ → ts-basic-service✓
ts-preserve-service✓ → ts-contacts-service
ts-preserve-service✓ → ts-food-service
ts-preserve-service✓ → ts-order-service
ts-preserve-service✓ → ts-seat-service
ts-preserve-service✓ → ts-security-service
... +23 more edges
```

**V3 漏的真路径节点**: `loadgenerator`, `ts-route-plan-service`, `ts-travel-plan-service`, `ts-travel2-service`

---

## Case 3: `ts3-ts-order-service-container-kill-gh2xcv`

- **RC**: `ts-order-service`
- **cascade 服务数**: 24
- **LOCAL 服务**: 11, **V3 服务**: 6, **L−V**: 5
- **真漏 (在 cascade 上)**: 4

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-order-service[RC]
L1: ts-cancel-service | ts-inside-payment-service | ts-preserve-service✓ | ts-seat-service✓ | ts-security-service⚠️ | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-assurance-service | ts-basic-service | ts-config-service | ts-contacts-service | ts-food-service | ts-order-other-service | ts-payment-service | ts-travel-plan-service✓ | ts-travel-service✓ | ts-travel2-service⚠️ | ts-user-service
L3: ts-price-service | ts-route-plan-service⚠️ | ts-route-service | ts-station-service | ts-train-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-cancel-service → ts-inside-payment-service
ts-cancel-service → ts-order-service✓
ts-cancel-service → ts-user-service
ts-inside-payment-service → ts-order-service✓
ts-inside-payment-service → ts-payment-service
ts-preserve-service✓ → ts-assurance-service
ts-preserve-service✓ → ts-basic-service
... +30 more edges
```

**V3 漏的真路径节点**: `loadgenerator`, `ts-route-plan-service`, `ts-security-service`, `ts-travel2-service`

**V3 漏对了（不在 cascade）**: `ts-order-service-668587b48c-z7r6g`

---

## Case 4: `ts4-ts-order-other-service-exception-nh22zm`

- **RC**: `ts-order-other-service`
- **cascade 服务数**: 21
- **LOCAL 服务**: 11, **V3 服务**: 7, **L−V**: 4
- **真漏 (在 cascade 上)**: 3

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-order-other-service[RC]
L1: ts-seat-service✓ | ts-security-service✓ | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-config-service | ts-order-service | ts-preserve-service✓ | ts-travel-plan-service✓ | ts-travel-service✓ | ts-travel2-service⚠️
L3: ts-assurance-service | ts-basic-service | ts-contacts-service | ts-food-service | ts-route-plan-service⚠️ | ts-route-service | ts-train-service | ts-user-service
L4: ts-price-service | ts-station-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-preserve-service✓ → ts-assurance-service
ts-preserve-service✓ → ts-basic-service
ts-preserve-service✓ → ts-contacts-service
ts-preserve-service✓ → ts-food-service
ts-preserve-service✓ → ts-order-service
ts-preserve-service✓ → ts-seat-service✓
ts-preserve-service✓ → ts-security-service✓
... +23 more edges
```

**V3 漏的真路径节点**: `loadgenerator`, `ts-route-plan-service`, `ts-travel2-service`

**V3 漏对了（不在 cascade）**: `ts-order-other-service-5d6878687f-ng8q7`

---

## Case 5: `ts0-ts-travel-service-mysql-28wmss`

- **RC**: `ts-travel-service`
- **cascade 服务数**: 23
- **LOCAL 服务**: 6, **V3 服务**: 4, **L−V**: 2
- **真漏 (在 cascade 上)**: 2

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-travel-service[RC]
L1: ts-basic-service | ts-food-service | ts-preserve-service⚠️ | ts-route-plan-service✓ | ts-route-service | ts-seat-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-assurance-service | ts-config-service | ts-contacts-service | ts-order-other-service | ts-order-service | ts-price-service | ts-security-service | ts-station-food-service | ts-station-service | ts-train-food-service | ts-train-service | ts-travel-plan-service✓ | ts-travel2-service | ts-user-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-food-service → ts-station-food-service
ts-food-service → ts-train-food-service
ts-food-service → ts-travel-service✓
ts-preserve-service⚠️ → ts-assurance-service
ts-preserve-service⚠️ → ts-basic-service
ts-preserve-service⚠️ → ts-contacts-service
ts-preserve-service⚠️ → ts-food-service
... +26 more edges
```

**V3 漏的真路径节点**: `loadgenerator`, `ts-preserve-service`

---

## Case 6: `ts2-ts-order-other-service-container-kill-48rlds`

- **RC**: `ts-order-other-service`
- **cascade 服务数**: 22
- **LOCAL 服务**: 11, **V3 服务**: 8, **L−V**: 3
- **真漏 (在 cascade 上)**: 2

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-order-other-service[RC]
L1: ts-execute-service | ts-seat-service✓ | ts-security-service✓ | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-config-service | ts-order-service | ts-preserve-service✓ | ts-travel-plan-service✓ | ts-travel-service✓ | ts-travel2-service✓
L3: ts-assurance-service | ts-basic-service | ts-contacts-service | ts-food-service | ts-route-plan-service⚠️ | ts-route-service | ts-train-service | ts-user-service
L4: ts-price-service | ts-station-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-execute-service → ts-order-other-service✓
ts-execute-service → ts-order-service
ts-preserve-service✓ → ts-assurance-service
ts-preserve-service✓ → ts-basic-service
ts-preserve-service✓ → ts-contacts-service
ts-preserve-service✓ → ts-food-service
ts-preserve-service✓ → ts-order-service
... +26 more edges
```

**V3 漏的真路径节点**: `loadgenerator`, `ts-route-plan-service`

**V3 漏对了（不在 cascade）**: `ts-order-other-service-574d96b46c-z7bvj`

---

## Case 7: `ts2-ts-seat-service-stress-b7h7m9`

- **RC**: `ts-seat-service`
- **cascade 服务数**: 21
- **LOCAL 服务**: 9, **V3 服务**: 7, **L−V**: 2
- **真漏 (在 cascade 上)**: 2

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-seat-service[RC]
L1: ts-config-service | ts-order-other-service | ts-order-service | ts-preserve-service✓ | ts-travel-plan-service✓ | ts-travel-service✓ | ts-travel2-service✓
L2: ts-assurance-service | ts-basic-service | ts-contacts-service | ts-food-service | ts-route-plan-service⚠️ | ts-route-service | ts-security-service | ts-train-service | ts-ui-dashboard✓ | ts-user-service
L3: loadgenerator⚠️ | ts-price-service | ts-station-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-preserve-service✓ → ts-assurance-service
ts-preserve-service✓ → ts-basic-service
ts-preserve-service✓ → ts-contacts-service
ts-preserve-service✓ → ts-food-service
ts-preserve-service✓ → ts-order-service
ts-preserve-service✓ → ts-seat-service✓
ts-preserve-service✓ → ts-security-service
... +23 more edges
```

**V3 漏的真路径节点**: `loadgenerator`, `ts-route-plan-service`

---

## Case 8: `ts2-ts-station-service-dns-nn49s2`

- **RC**: `ts-station-service`
- **cascade 服务数**: 21
- **LOCAL 服务**: 15, **V3 服务**: 13, **L−V**: 2
- **真漏 (在 cascade 上)**: 2

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-station-service[RC]
L1: ts-basic-service✓
L2: ts-preserve-service✓ | ts-price-service | ts-route-service | ts-train-service | ts-travel-service✓ | ts-travel2-service✓
L3: ts-assurance-service✓ | ts-contacts-service✓ | ts-food-service✓ | ts-order-service | ts-route-plan-service⚠️ | ts-seat-service✓ | ts-security-service | ts-travel-plan-service✓ | ts-ui-dashboard✓ | ts-user-service
L4: loadgenerator⚠️ | ts-config-service✓ | ts-order-other-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service✓ → ts-price-service
ts-basic-service✓ → ts-route-service
ts-basic-service✓ → ts-station-service✓
ts-basic-service✓ → ts-train-service
ts-preserve-service✓ → ts-assurance-service✓
ts-preserve-service✓ → ts-basic-service✓
ts-preserve-service✓ → ts-contacts-service✓
ts-preserve-service✓ → ts-food-service✓
ts-preserve-service✓ → ts-order-service
ts-preserve-service✓ → ts-seat-service✓
ts-preserve-service✓ → ts-security-service
... +23 more edges
```

**V3 漏的真路径节点**: `loadgenerator`, `ts-route-plan-service`

---

## Case 9: `ts3-ts-basic-service-stress-p545b4`

- **RC**: `ts-basic-service`
- **cascade 服务数**: 21
- **LOCAL 服务**: 9, **V3 服务**: 7, **L−V**: 2
- **真漏 (在 cascade 上)**: 2

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-basic-service[RC]
L1: ts-preserve-service⚠️ | ts-price-service | ts-route-service | ts-station-service | ts-train-service | ts-travel-service✓ | ts-travel2-service✓
L2: ts-assurance-service | ts-contacts-service | ts-food-service | ts-order-service | ts-route-plan-service✓ | ts-seat-service | ts-security-service | ts-travel-plan-service✓ | ts-ui-dashboard✓ | ts-user-service
L3: loadgenerator⚠️ | ts-config-service | ts-order-other-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service✓ → ts-price-service
ts-basic-service✓ → ts-route-service
ts-basic-service✓ → ts-station-service
ts-basic-service✓ → ts-train-service
ts-preserve-service⚠️ → ts-assurance-service
ts-preserve-service⚠️ → ts-basic-service✓
ts-preserve-service⚠️ → ts-contacts-service
ts-preserve-service⚠️ → ts-food-service
ts-preserve-service⚠️ → ts-order-service
ts-preserve-service⚠️ → ts-seat-service
ts-preserve-service⚠️ → ts-security-service
... +23 more edges
```

**V3 漏的真路径节点**: `loadgenerator`, `ts-preserve-service`

---

## Case 10: `ts4-ts-station-service-bandwidth-nfljv5`

- **RC**: `ts-station-service`
- **cascade 服务数**: 17
- **LOCAL 服务**: 9, **V3 服务**: 7, **L−V**: 2
- **真漏 (在 cascade 上)**: 2

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-station-service[RC]
L1: ts-basic-service✓
L2: ts-route-service | ts-train-service | ts-travel2-service✓
L3: ts-route-plan-service✓ | ts-travel-plan-service✓ | ts-travel-service✓
L4: ts-seat-service
L5: ts-config-service | ts-order-service
L6: ts-security-service
L7: ts-order-other-service | ts-preserve-service⚠️
L8: ts-contacts-service
⚠ 不可达 RC 的 cascade 服务: loadgenerator, ts-ui-dashboard
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service✓ → ts-route-service
ts-basic-service✓ → ts-station-service✓
ts-basic-service✓ → ts-train-service
ts-preserve-service⚠️ → ts-contacts-service
ts-preserve-service⚠️ → ts-security-service
ts-route-plan-service✓ → ts-route-service
ts-route-plan-service✓ → ts-travel-service✓
ts-route-plan-service✓ → ts-travel2-service✓
ts-seat-service → ts-config-service
ts-seat-service → ts-order-service
ts-security-service → ts-order-other-service
... +6 more edges
```

**V3 漏的真路径节点**: `loadgenerator`, `ts-preserve-service`

---

## Case 11: `ts0-ts-travel-plan-service-response-delay-pfwcqk`

- **RC**: `ts-travel-plan-service`
- **cascade 服务数**: 15
- **LOCAL 服务**: 3, **V3 服务**: 2, **L−V**: 1
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-travel-plan-service[RC]
L1: ts-route-plan-service | ts-seat-service | ts-train-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-basic-service | ts-config-service | ts-order-other-service | ts-order-service | ts-route-service | ts-travel-service | ts-travel2-service
L3: ts-price-service | ts-station-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-route-plan-service → ts-route-service
ts-route-plan-service → ts-travel-service
ts-route-plan-service → ts-travel2-service
ts-seat-service → ts-config-service
ts-seat-service → ts-order-other-service
ts-seat-service → ts-order-service
ts-travel-plan-service✓ → ts-route-plan-service
... +9 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

---

## Case 12: `ts0-ts-travel2-service-request-delay-lzpl9v`

- **RC**: `ts-travel2-service`
- **cascade 服务数**: 15
- **LOCAL 服务**: 5, **V3 服务**: 4, **L−V**: 1
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-travel2-service[RC]
L1: ts-basic-service | ts-route-plan-service✓ | ts-route-service | ts-seat-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-config-service | ts-order-other-service | ts-order-service | ts-price-service | ts-station-service | ts-train-service | ts-travel-plan-service✓ | ts-travel-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-route-plan-service✓ → ts-route-service
ts-route-plan-service✓ → ts-travel-service
ts-route-plan-service✓ → ts-travel2-service✓
ts-seat-service → ts-config-service
ts-seat-service → ts-order-other-service
ts-seat-service → ts-order-service
ts-travel-plan-service✓ → ts-route-plan-service✓
... +10 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

---

## Case 13: `ts1-ts-station-food-service-stress-rlvxhc`

- **RC**: `ts-station-food-service`
- **cascade 服务数**: 7
- **LOCAL 服务**: 16, **V3 服务**: 15, **L−V**: 1
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-station-food-service[RC]
L1: ts-food-service✓
L2: ts-train-food-service✓ | ts-travel-service✓ | ts-ui-dashboard✓
L3: loadgenerator⚠️ | ts-route-service✓
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-food-service✓ → ts-station-food-service✓
ts-food-service✓ → ts-train-food-service✓
ts-food-service✓ → ts-travel-service✓
ts-travel-service✓ → ts-route-service✓
ts-ui-dashboard✓ → ts-food-service✓
```

**V3 漏的真路径节点**: `loadgenerator`

---

## Case 14: `ts1-ts-train-service-pod-failure-5qwqdz`

- **RC**: `ts-train-service`
- **cascade 服务数**: 13
- **LOCAL 服务**: 10, **V3 服务**: 6, **L−V**: 4
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-train-service[RC]
L1: ts-basic-service✓ | ts-travel-plan-service✓
L2: ts-price-service | ts-route-plan-service⚠️ | ts-route-service | ts-seat-service | ts-station-service | ts-travel-service✓ | ts-travel2-service✓
L3: ts-config-service | ts-order-other-service | ts-order-service
```

**主要 caller→callee 边**

```
ts-basic-service✓ → ts-price-service
ts-basic-service✓ → ts-route-service
ts-basic-service✓ → ts-station-service
ts-basic-service✓ → ts-train-service✓
ts-route-plan-service⚠️ → ts-route-service
ts-route-plan-service⚠️ → ts-travel-service✓
ts-route-plan-service⚠️ → ts-travel2-service✓
ts-seat-service → ts-config-service
ts-seat-service → ts-order-other-service
ts-seat-service → ts-order-service
ts-travel-plan-service✓ → ts-route-plan-service⚠️
ts-travel-plan-service✓ → ts-seat-service
... +4 more edges
```

**V3 漏的真路径节点**: `ts-route-plan-service`

**V3 漏对了（不在 cascade）**: `loadgenerator`, `ts-preserve-service`, `ts-train-service-6854555655-4gmbw`

---

## Case 15: `ts2-ts-travel-plan-service-response-delay-chhzjz`

- **RC**: `ts-travel-plan-service`
- **cascade 服务数**: 15
- **LOCAL 服务**: 3, **V3 服务**: 2, **L−V**: 1
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-travel-plan-service[RC]
L1: ts-route-plan-service | ts-seat-service | ts-train-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-basic-service | ts-config-service | ts-order-other-service | ts-order-service | ts-route-service | ts-travel-service | ts-travel2-service
L3: ts-price-service | ts-station-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-route-plan-service → ts-route-service
ts-route-plan-service → ts-travel-service
ts-route-plan-service → ts-travel2-service
ts-seat-service → ts-config-service
ts-seat-service → ts-order-other-service
ts-seat-service → ts-order-service
ts-travel-plan-service✓ → ts-route-plan-service
... +9 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

---

## Case 16: `ts3-ts-order-service-pod-failure-7xsmwd`

- **RC**: `ts-order-service`
- **cascade 服务数**: 3
- **LOCAL 服务**: 13, **V3 服务**: 7, **L−V**: 6
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-order-service[RC]
L1: ts-ui-dashboard✓
L2: loadgenerator⚠️
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-ui-dashboard✓ → ts-order-service✓
```

**V3 漏的真路径节点**: `loadgenerator`

**V3 漏对了（不在 cascade）**: `ts-order-service-6f4cfb5df7-27ppv`, `ts-route-plan-service`, `ts-travel-plan-service`, `ts-travel-service`, `ts-travel2-service`

---

## Case 17: `ts3-ts-preserve-service-container-kill-k7k8g5`

- **RC**: `ts-preserve-service`
- **cascade 服务数**: 18
- **LOCAL 服务**: 4, **V3 服务**: 2, **L−V**: 2
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-preserve-service[RC]
L1: ts-assurance-service | ts-basic-service | ts-contacts-service | ts-food-service | ts-order-service | ts-seat-service | ts-security-service | ts-travel-service | ts-ui-dashboard✓ | ts-user-service
L2: loadgenerator⚠️ | ts-config-service | ts-order-other-service | ts-price-service | ts-route-service | ts-station-service | ts-train-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-preserve-service✓ → ts-assurance-service
ts-preserve-service✓ → ts-basic-service
ts-preserve-service✓ → ts-contacts-service
ts-preserve-service✓ → ts-food-service
ts-preserve-service✓ → ts-order-service
ts-preserve-service✓ → ts-seat-service
ts-preserve-service✓ → ts-security-service
... +9 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

**V3 漏对了（不在 cascade）**: `ts-preserve-service-5d979f4b55-n6ccw`

---

## Case 18: `ts3-ts-travel-plan-service-exception-zgsz8w`

- **RC**: `ts-travel-plan-service`
- **cascade 服务数**: 15
- **LOCAL 服务**: 4, **V3 服务**: 2, **L−V**: 2
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-travel-plan-service[RC]
L1: ts-route-plan-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-route-service | ts-travel-service | ts-travel2-service
L3: ts-basic-service | ts-seat-service
L4: ts-config-service | ts-order-other-service | ts-order-service | ts-price-service | ts-station-service | ts-train-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-route-plan-service → ts-route-service
ts-route-plan-service → ts-travel-service
ts-route-plan-service → ts-travel2-service
ts-seat-service → ts-config-service
ts-seat-service → ts-order-other-service
ts-seat-service → ts-order-service
ts-travel-plan-service✓ → ts-route-plan-service
... +7 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

**V3 漏对了（不在 cascade）**: `ts-travel-plan-service-b49559b55-dnjp9`

---

## Case 19: `ts3-ts-travel-plan-service-request-delay-kxhn5n`

- **RC**: `ts-travel-plan-service`
- **cascade 服务数**: 15
- **LOCAL 服务**: 3, **V3 服务**: 2, **L−V**: 1
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-travel-plan-service[RC]
L1: ts-route-plan-service | ts-seat-service | ts-train-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-basic-service | ts-config-service | ts-order-other-service | ts-order-service | ts-route-service | ts-travel-service | ts-travel2-service
L3: ts-price-service | ts-station-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-route-plan-service → ts-route-service
ts-route-plan-service → ts-travel-service
ts-route-plan-service → ts-travel2-service
ts-seat-service → ts-config-service
ts-seat-service → ts-order-other-service
ts-seat-service → ts-order-service
ts-travel-plan-service✓ → ts-route-plan-service
... +9 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

---

## Case 20: `ts3-ts-travel-service-container-kill-jctldw`

- **RC**: `ts-travel-service`
- **cascade 服务数**: 23
- **LOCAL 服务**: 7, **V3 服务**: 5, **L−V**: 2
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-travel-service[RC]
L1: ts-basic-service | ts-food-service | ts-preserve-service✓ | ts-route-plan-service✓ | ts-route-service | ts-seat-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-assurance-service | ts-config-service | ts-contacts-service | ts-order-other-service | ts-order-service | ts-price-service | ts-security-service | ts-station-food-service | ts-station-service | ts-train-food-service | ts-train-service | ts-travel-plan-service✓ | ts-travel2-service | ts-user-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-food-service → ts-station-food-service
ts-food-service → ts-train-food-service
ts-food-service → ts-travel-service✓
ts-preserve-service✓ → ts-assurance-service
ts-preserve-service✓ → ts-basic-service
ts-preserve-service✓ → ts-contacts-service
ts-preserve-service✓ → ts-food-service
... +26 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

**V3 漏对了（不在 cascade）**: `ts-travel-service-56c9999f79-xwmb8`

---

## Case 21: `ts3-ts-travel2-service-container-kill-72qrd2`

- **RC**: `ts-travel2-service`
- **cascade 服务数**: 15
- **LOCAL 服务**: 6, **V3 服务**: 4, **L−V**: 2
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-travel2-service[RC]
L1: ts-basic-service | ts-route-plan-service✓ | ts-route-service | ts-seat-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-config-service | ts-order-other-service | ts-order-service | ts-price-service | ts-station-service | ts-train-service | ts-travel-plan-service✓ | ts-travel-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-route-plan-service✓ → ts-route-service
ts-route-plan-service✓ → ts-travel-service
ts-route-plan-service✓ → ts-travel2-service✓
ts-seat-service → ts-config-service
ts-seat-service → ts-order-other-service
ts-seat-service → ts-order-service
ts-travel-plan-service✓ → ts-route-plan-service✓
... +10 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

**V3 漏对了（不在 cascade）**: `ts-travel2-service-8557fd66df-mqfrk`

---

## Case 22: `ts3-ts-travel2-service-container-kill-vt4nvr`

- **RC**: `ts-travel2-service`
- **cascade 服务数**: 15
- **LOCAL 服务**: 6, **V3 服务**: 4, **L−V**: 2
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-travel2-service[RC]
L1: ts-basic-service | ts-route-plan-service✓ | ts-route-service | ts-seat-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-config-service | ts-order-other-service | ts-order-service | ts-price-service | ts-station-service | ts-train-service | ts-travel-plan-service✓ | ts-travel-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-route-plan-service✓ → ts-route-service
ts-route-plan-service✓ → ts-travel-service
ts-route-plan-service✓ → ts-travel2-service✓
ts-seat-service → ts-config-service
ts-seat-service → ts-order-other-service
ts-seat-service → ts-order-service
ts-travel-plan-service✓ → ts-route-plan-service✓
... +10 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

**V3 漏对了（不在 cascade）**: `ts-travel2-service-8557fd66df-kvg4k`

---

## Case 23: `ts4-ts-route-plan-service-bandwidth-q5lcsx`

- **RC**: `ts-route-plan-service`
- **cascade 服务数**: 15
- **LOCAL 服务**: 6, **V3 服务**: 5, **L−V**: 1
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-route-plan-service[RC]
L1: ts-route-service | ts-travel-plan-service✓ | ts-travel-service✓ | ts-travel2-service
L2: ts-basic-service | ts-seat-service | ts-train-service | ts-ui-dashboard✓
L3: loadgenerator⚠️ | ts-config-service | ts-order-other-service | ts-order-service | ts-price-service | ts-station-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-route-plan-service✓ → ts-route-service
ts-route-plan-service✓ → ts-travel-service✓
ts-route-plan-service✓ → ts-travel2-service
ts-seat-service → ts-config-service
ts-seat-service → ts-order-other-service
ts-seat-service → ts-order-service
ts-travel-plan-service✓ → ts-route-plan-service✓
... +9 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

---

## Case 24: `ts4-ts-seat-service-bandwidth-k2bwt2`

- **RC**: `ts-seat-service`
- **cascade 服务数**: 15
- **LOCAL 服务**: 9, **V3 服务**: 7, **L−V**: 2
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-seat-service[RC]
L1: ts-config-service✓ | ts-order-other-service | ts-order-service | ts-travel-plan-service✓ | ts-travel-service✓ | ts-travel2-service✓
L2: ts-basic-service | ts-route-plan-service✓ | ts-route-service | ts-train-service
L3: ts-price-service | ts-station-service
⚠ 不可达 RC 的 cascade 服务: loadgenerator, ts-ui-dashboard
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-route-plan-service✓ → ts-route-service
ts-route-plan-service✓ → ts-travel-service✓
ts-route-plan-service✓ → ts-travel2-service✓
ts-seat-service✓ → ts-config-service✓
ts-seat-service✓ → ts-order-other-service
ts-seat-service✓ → ts-order-service
ts-travel-plan-service✓ → ts-route-plan-service✓
... +8 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

**V3 漏对了（不在 cascade）**: `ts-preserve-service`

---

## Case 25: `ts4-ts-seat-service-delay-ddn72q`

- **RC**: `ts-seat-service`
- **cascade 服务数**: 21
- **LOCAL 服务**: 8, **V3 服务**: 7, **L−V**: 1
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-seat-service[RC]
L1: ts-config-service | ts-order-other-service | ts-order-service | ts-preserve-service✓ | ts-travel-plan-service✓ | ts-travel-service✓ | ts-travel2-service✓
L2: ts-assurance-service | ts-basic-service | ts-contacts-service | ts-food-service | ts-route-plan-service✓ | ts-route-service | ts-security-service | ts-train-service | ts-ui-dashboard✓ | ts-user-service
L3: loadgenerator⚠️ | ts-price-service | ts-station-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-preserve-service✓ → ts-assurance-service
ts-preserve-service✓ → ts-basic-service
ts-preserve-service✓ → ts-contacts-service
ts-preserve-service✓ → ts-food-service
ts-preserve-service✓ → ts-order-service
ts-preserve-service✓ → ts-seat-service✓
ts-preserve-service✓ → ts-security-service
... +23 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

---

## Case 26: `ts5-ts-preserve-service-partition-dkhqzh`

- **RC**: `ts-preserve-service`
- **cascade 服务数**: 18
- **LOCAL 服务**: 5, **V3 服务**: 4, **L−V**: 1
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-preserve-service[RC]
L1: ts-assurance-service | ts-basic-service | ts-contacts-service | ts-food-service | ts-order-service | ts-security-service | ts-travel-service✓ | ts-ui-dashboard✓ | ts-user-service
L2: loadgenerator⚠️ | ts-order-other-service | ts-price-service | ts-route-service | ts-seat-service✓ | ts-station-service | ts-train-service
L3: ts-config-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-preserve-service✓ → ts-assurance-service
ts-preserve-service✓ → ts-basic-service
ts-preserve-service✓ → ts-contacts-service
ts-preserve-service✓ → ts-food-service
ts-preserve-service✓ → ts-order-service
ts-preserve-service✓ → ts-security-service
ts-preserve-service✓ → ts-travel-service✓
... +8 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

---

## Case 27: `ts5-ts-travel-plan-service-delay-v5ptlf`

- **RC**: `ts-travel-plan-service`
- **cascade 服务数**: 15
- **LOCAL 服务**: 7, **V3 服务**: 6, **L−V**: 1
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-travel-plan-service[RC]
L1: ts-route-plan-service✓ | ts-seat-service✓ | ts-train-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-basic-service | ts-config-service | ts-order-other-service | ts-order-service | ts-route-service | ts-travel-service✓ | ts-travel2-service✓
L3: ts-price-service | ts-station-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-route-plan-service✓ → ts-route-service
ts-route-plan-service✓ → ts-travel-service✓
ts-route-plan-service✓ → ts-travel2-service✓
ts-seat-service✓ → ts-config-service
ts-seat-service✓ → ts-order-other-service
ts-seat-service✓ → ts-order-service
ts-travel-plan-service✓ → ts-route-plan-service✓
... +9 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

---

## Case 28: `ts7-ts-travel-service-response-delay-t48wrc`

- **RC**: `ts-travel-service`
- **cascade 服务数**: 23
- **LOCAL 服务**: 5, **V3 服务**: 4, **L−V**: 1
- **真漏 (在 cascade 上)**: 1

### 实际传播路径（trace 聚合，按 BFS 层）

```
L0: ts-travel-service[RC]
L1: ts-basic-service | ts-food-service | ts-preserve-service | ts-route-plan-service✓ | ts-route-service | ts-seat-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-assurance-service | ts-config-service | ts-contacts-service | ts-order-other-service | ts-order-service | ts-price-service | ts-security-service | ts-station-food-service | ts-station-service | ts-train-food-service | ts-train-service | ts-travel-plan-service✓ | ts-travel2-service | ts-user-service
```

**主要 caller→callee 边**

```
loadgenerator⚠️ → ts-ui-dashboard✓
ts-basic-service → ts-price-service
ts-basic-service → ts-route-service
ts-basic-service → ts-station-service
ts-basic-service → ts-train-service
ts-food-service → ts-station-food-service
ts-food-service → ts-train-food-service
ts-food-service → ts-travel-service✓
ts-preserve-service → ts-assurance-service
ts-preserve-service → ts-basic-service
ts-preserve-service → ts-contacts-service
ts-preserve-service → ts-food-service
... +26 more edges
```

**V3 漏的真路径节点**: `loadgenerator`

---

