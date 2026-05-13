# V4 vs V3 vs LOCAL — 28 case 实际传播路径对比

v4 数据集（`anon-ops/openrca2-lite-v4`）在同 500 case 上用更新版 reasoner（rcabench-platform commit `9b6661dac`）重生成 causal_graph。本文档对比 V4 / V3 / LOCAL 三者，标注 V4 漏掉的真实传播路径节点。

## 标注约定

- ⚠️  = LOCAL 有 / V4 漏 / 在实际 cascade 上（**V4 真漏**）
- ✗  = LOCAL 有 / V4 漏 / 不在 cascade（V4 漏对了）
- ✓  = V4 包含
- 🆕  = V4 比 V3 新增的节点（V3 没有，V4 有）
- ➖  = V4 比 V3 删掉的节点（V3 有，V4 没了）
- [RC] = root cause service

---

## 总表（按 V4 真漏数倒排）

| # | case | fault | RC | cascade | L | V3 | V4 | **V4真漏** | V4 真漏 services |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| 1 | `ts2-ts-order-other-service-container-kill-48rlds` | ContainerKill | `ts-order-other-service` | 22 | 11 | 8 | 2 | **8** | `loadgenerator`, `ts-preserve-service`, `ts-route-plan-service`, `ts-seat-service`, `ts-security-service`, `ts-travel-plan-service`, `ts-travel-service`, `ts-travel2-service` |
| 2 | `ts3-ts-basic-service-partition-w5hbjw` | NetworkPartition | `ts-basic-service` | 21 | 7 | 7 | 5 | **6** | `loadgenerator`, `ts-basic-service`, `ts-route-plan-service`, `ts-travel-plan-service`, `ts-travel2-service`, `ts-ui-dashboard` |
| 3 | `ts4-ts-order-other-service-exception-nh22zm` | JVMException | `ts-order-other-service` | 21 | 11 | 7 | 4 | **6** | `loadgenerator`, `ts-preserve-service`, `ts-route-plan-service`, `ts-security-service`, `ts-travel-service`, `ts-travel2-service` |
| 4 | `ts0-ts-travel-service-mysql-28wmss` | JVMMySQLLatency | `ts-travel-service` | 23 | 6 | 4 | 1 | **5** | `loadgenerator`, `ts-preserve-service`, `ts-route-plan-service`, `ts-travel-plan-service`, `ts-ui-dashboard` |
| 5 | `ts0-ts-station-service-bandwidth-bp5k94` | NetworkBandwidth | `ts-station-service` | 21 | 9 | 5 | 5 | **4** | `loadgenerator`, `ts-route-plan-service`, `ts-travel-plan-service`, `ts-travel2-service` |
| 6 | `ts3-ts-order-service-container-kill-gh2xcv` | ContainerKill | `ts-order-service` | 24 | 11 | 6 | 6 | **4** | `loadgenerator`, `ts-route-plan-service`, `ts-security-service`, `ts-travel2-service` |
| 7 | `ts3-ts-travel-service-container-kill-jctldw` | ContainerKill | `ts-travel-service` | 23 | 7 | 5 | 2 | **4** | `loadgenerator`, `ts-preserve-service`, `ts-route-plan-service`, `ts-travel-plan-service` |
| 8 | `ts2-ts-seat-service-stress-b7h7m9` | JVMMemoryStress | `ts-seat-service` | 21 | 9 | 7 | 6 | **3** | `loadgenerator`, `ts-route-plan-service`, `ts-travel2-service` |
| 9 | `ts2-ts-station-service-dns-nn49s2` | DNSRandom | `ts-station-service` | 21 | 9 | 13 | 13 | **2** | `loadgenerator`, `ts-route-plan-service` |
| 10 | `ts3-ts-basic-service-stress-p545b4` | JVMMemoryStress | `ts-basic-service` | 21 | 9 | 7 | 7 | **2** | `loadgenerator`, `ts-preserve-service` |
| 11 | `ts4-ts-seat-service-delay-ddn72q` | NetworkDelay | `ts-seat-service` | 21 | 8 | 7 | 6 | **2** | `loadgenerator`, `ts-preserve-service` |
| 12 | `ts4-ts-station-service-bandwidth-nfljv5` | NetworkBandwidth | `ts-station-service` | 17 | 9 | 7 | 7 | **2** | `loadgenerator`, `ts-preserve-service` |
| 13 | `ts0-ts-travel-plan-service-response-delay-pfwcqk` | HTTPResponseDelay | `ts-travel-plan-service` | 15 | 3 | 2 | 2 | **1** | `loadgenerator` |
| 14 | `ts0-ts-travel2-service-request-delay-lzpl9v` | HTTPRequestDelay | `ts-travel2-service` | 15 | 5 | 4 | 4 | **1** | `loadgenerator` |
| 15 | `ts1-ts-station-food-service-stress-rlvxhc` | JVMMemoryStress | `ts-station-food-service` | 7 | 5 | 15 | 12 | **1** | `loadgenerator` |
| 16 | `ts1-ts-train-service-pod-failure-5qwqdz` | PodFailure | `ts-train-service` | 13 | 10 | 6 | 6 | **1** | `ts-route-plan-service` |
| 17 | `ts2-ts-travel-plan-service-response-delay-chhzjz` | HTTPResponseDelay | `ts-travel-plan-service` | 15 | 3 | 2 | 2 | **1** | `loadgenerator` |
| 18 | `ts3-ts-order-service-pod-failure-7xsmwd` | PodFailure | `ts-order-service` | 3 | 13 | 7 | 7 | **1** | `loadgenerator` |
| 19 | `ts3-ts-preserve-service-container-kill-k7k8g5` | ContainerKill | `ts-preserve-service` | 18 | 4 | 2 | 2 | **1** | `loadgenerator` |
| 20 | `ts3-ts-travel-plan-service-exception-zgsz8w` | JVMException | `ts-travel-plan-service` | 15 | 4 | 2 | 2 | **1** | `loadgenerator` |
| 21 | `ts3-ts-travel-plan-service-request-delay-kxhn5n` | HTTPRequestDelay | `ts-travel-plan-service` | 15 | 3 | 2 | 2 | **1** | `loadgenerator` |
| 22 | `ts3-ts-travel2-service-container-kill-72qrd2` | ContainerKill | `ts-travel2-service` | 15 | 6 | 4 | 4 | **1** | `loadgenerator` |
| 23 | `ts3-ts-travel2-service-container-kill-vt4nvr` | ContainerKill | `ts-travel2-service` | 15 | 6 | 4 | 4 | **1** | `loadgenerator` |
| 24 | `ts4-ts-route-plan-service-bandwidth-q5lcsx` | NetworkBandwidth | `ts-route-plan-service` | 15 | 4 | 5 | 4 | **1** | `loadgenerator` |
| 25 | `ts4-ts-seat-service-bandwidth-k2bwt2` | NetworkBandwidth | `ts-seat-service` | 15 | 8 | 7 | 7 | **1** | `loadgenerator` |
| 26 | `ts5-ts-preserve-service-partition-dkhqzh` | NetworkPartition | `ts-preserve-service` | 18 | 3 | 4 | 4 | **1** | `loadgenerator` |
| 27 | `ts5-ts-travel-plan-service-delay-v5ptlf` | NetworkDelay | `ts-travel-plan-service` | 15 | 3 | 6 | 6 | **1** | `loadgenerator` |
| 28 | `ts7-ts-travel-service-response-delay-t48wrc` | HTTPResponseDelay | `ts-travel-service` | 23 | 5 | 4 | 4 | **1** | `loadgenerator` |

## V4 vs V3 真漏数对比

| 指标 | V3 | V4 | Δ |
|---|---:|---:|---:|
| 真漏总数（含 loadgen） | 46 | 64 | +18 |
| 真漏（**排除 loadgen**） | 19 | 37 | **+18** |
| 受真漏影响 case 数 | 11 | 13 | |

**结论**：V4 比 V3 真漏服务数**翻了将近一倍**——更窄、更保守，但牺牲了真实路径覆盖。

## 高频被漏的真路径服务（非 loadgen）

| 服务 | V3 漏 | V4 漏 | Δ |
|---|---:|---:|---:|
| `ts-route-plan-service` | 8 | 10 | +2 |
| `ts-preserve-service` | 3 | 7 | +4 |
| `ts-travel2-service` | 4 | 6 | +2 |
| `ts-travel-plan-service` | 2 | 5 | +3 |
| `ts-security-service` | 1 | 3 | +2 |
| `ts-travel-service` | 0 | 2 | +2 |
| `ts-ui-dashboard` | 0 | 2 | +2 |
| `ts-basic-service` | 1 | 1 | 0 |
| `ts-seat-service` | 0 | 1 | +1 |

---

## 每 case 详情

### Case 1: `ts2-ts-order-other-service-container-kill-48rlds`

- RC: `ts-order-other-service` | cascade=22 | L=11 V3=8 V4=2 | V4真漏=8
- V4 删掉 (vs V3): `ts-preserve-service`, `ts-seat-service`, `ts-security-service`, `ts-travel-plan-service`, `ts-travel-service`, `ts-travel2-service`

```
L0: ts-order-other-service[RC]
L1: ts-execute-service | ts-seat-service⚠️ | ts-security-service⚠️ | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-config-service | ts-order-service | ts-preserve-service⚠️ | ts-travel-plan-service⚠️ | ts-travel-service⚠️ | ts-travel2-service⚠️
L3: ts-assurance-service | ts-basic-service | ts-contacts-service | ts-food-service | ts-route-plan-service⚠️ | ts-route-service | ts-train-service | ts-user-service
L4: ts-price-service | ts-station-service
```

**V4 漏的真路径节点**: `loadgenerator`, `ts-preserve-service`, `ts-route-plan-service`, `ts-seat-service`, `ts-security-service`, `ts-travel-plan-service`, `ts-travel-service`, `ts-travel2-service`
**V4 漏对了**: `ts-order-other-service-574d96b46c-z7bvj`

---

### Case 2: `ts3-ts-basic-service-partition-w5hbjw`

- RC: `ts-basic-service` | cascade=21 | L=7 V3=7 V4=5 | V4真漏=6
- V4 删掉 (vs V3): `ts-order-other-service`, `ts-ui-dashboard`

```
L0: ts-basic-service[RC]
L1: ts-preserve-service | ts-price-service✓ | ts-route-service | ts-station-service | ts-train-service | ts-travel-service✓ | ts-travel2-service⚠️
L2: ts-assurance-service | ts-contacts-service | ts-food-service | ts-order-service✓ | ts-route-plan-service⚠️ | ts-seat-service | ts-security-service | ts-travel-plan-service⚠️ | ts-ui-dashboard⚠️ | ts-user-service
L3: loadgenerator⚠️ | ts-config-service | ts-order-other-service
```

**V4 漏的真路径节点**: `loadgenerator`, `ts-basic-service`, `ts-route-plan-service`, `ts-travel-plan-service`, `ts-travel2-service`, `ts-ui-dashboard`

---

### Case 3: `ts4-ts-order-other-service-exception-nh22zm`

- RC: `ts-order-other-service` | cascade=21 | L=11 V3=7 V4=4 | V4真漏=6
- V4 删掉 (vs V3): `ts-preserve-service`, `ts-security-service`, `ts-travel-service`

```
L0: ts-order-other-service[RC]
L1: ts-seat-service✓ | ts-security-service⚠️ | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-config-service | ts-order-service | ts-preserve-service⚠️ | ts-travel-plan-service✓ | ts-travel-service⚠️ | ts-travel2-service⚠️
L3: ts-assurance-service | ts-basic-service | ts-contacts-service | ts-food-service | ts-route-plan-service⚠️ | ts-route-service | ts-train-service | ts-user-service
L4: ts-price-service | ts-station-service
```

**V4 漏的真路径节点**: `loadgenerator`, `ts-preserve-service`, `ts-route-plan-service`, `ts-security-service`, `ts-travel-service`, `ts-travel2-service`
**V4 漏对了**: `ts-order-other-service-5d6878687f-ng8q7`

---

### Case 4: `ts0-ts-travel-service-mysql-28wmss`

- RC: `ts-travel-service` | cascade=23 | L=6 V3=4 V4=1 | V4真漏=5
- V4 删掉 (vs V3): `ts-route-plan-service`, `ts-travel-plan-service`, `ts-ui-dashboard`

```
L0: ts-travel-service[RC]
L1: ts-basic-service | ts-food-service | ts-preserve-service⚠️ | ts-route-plan-service⚠️ | ts-route-service | ts-seat-service | ts-ui-dashboard⚠️
L2: loadgenerator⚠️ | ts-assurance-service | ts-config-service | ts-contacts-service | ts-order-other-service | ts-order-service | ts-price-service | ts-security-service | ts-station-food-service | ts-station-service | ts-train-food-service | ts-train-service | ts-travel-plan-service⚠️ | ts-travel2-service | ts-user-service
```

**V4 漏的真路径节点**: `loadgenerator`, `ts-preserve-service`, `ts-route-plan-service`, `ts-travel-plan-service`, `ts-ui-dashboard`

---

### Case 5: `ts0-ts-station-service-bandwidth-bp5k94`

- RC: `ts-station-service` | cascade=21 | L=9 V3=5 V4=5 | V4真漏=4

```
L0: ts-station-service[RC]
L1: ts-basic-service✓
L2: ts-preserve-service✓ | ts-price-service | ts-route-service | ts-train-service | ts-travel-service✓ | ts-travel2-service⚠️
L3: ts-assurance-service | ts-contacts-service | ts-food-service | ts-order-service | ts-route-plan-service⚠️ | ts-seat-service | ts-security-service | ts-travel-plan-service⚠️ | ts-ui-dashboard✓ | ts-user-service
L4: loadgenerator⚠️ | ts-config-service | ts-order-other-service
```

**V4 漏的真路径节点**: `loadgenerator`, `ts-route-plan-service`, `ts-travel-plan-service`, `ts-travel2-service`

---

### Case 6: `ts3-ts-order-service-container-kill-gh2xcv`

- RC: `ts-order-service` | cascade=24 | L=11 V3=6 V4=6 | V4真漏=4

```
L0: ts-order-service[RC]
L1: ts-cancel-service | ts-inside-payment-service | ts-preserve-service✓ | ts-seat-service✓ | ts-security-service⚠️ | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-assurance-service | ts-basic-service | ts-config-service | ts-contacts-service | ts-food-service | ts-order-other-service | ts-payment-service | ts-travel-plan-service✓ | ts-travel-service✓ | ts-travel2-service⚠️ | ts-user-service
L3: ts-price-service | ts-route-plan-service⚠️ | ts-route-service | ts-station-service | ts-train-service
```

**V4 漏的真路径节点**: `loadgenerator`, `ts-route-plan-service`, `ts-security-service`, `ts-travel2-service`
**V4 漏对了**: `ts-order-service-668587b48c-z7r6g`

---

### Case 7: `ts3-ts-travel-service-container-kill-jctldw`

- RC: `ts-travel-service` | cascade=23 | L=7 V3=5 V4=2 | V4真漏=4
- V4 删掉 (vs V3): `ts-preserve-service`, `ts-route-plan-service`, `ts-travel-plan-service`

```
L0: ts-travel-service[RC]
L1: ts-basic-service | ts-food-service | ts-preserve-service⚠️ | ts-route-plan-service⚠️ | ts-route-service | ts-seat-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-assurance-service | ts-config-service | ts-contacts-service | ts-order-other-service | ts-order-service | ts-price-service | ts-security-service | ts-station-food-service | ts-station-service | ts-train-food-service | ts-train-service | ts-travel-plan-service⚠️ | ts-travel2-service | ts-user-service
```

**V4 漏的真路径节点**: `loadgenerator`, `ts-preserve-service`, `ts-route-plan-service`, `ts-travel-plan-service`
**V4 漏对了**: `ts-travel-service-56c9999f79-xwmb8`

---

### Case 8: `ts2-ts-seat-service-stress-b7h7m9`

- RC: `ts-seat-service` | cascade=21 | L=9 V3=7 V4=6 | V4真漏=3
- V4 删掉 (vs V3): `ts-travel2-service`

```
L0: ts-seat-service[RC]
L1: ts-config-service | ts-order-other-service | ts-order-service | ts-preserve-service✓ | ts-travel-plan-service✓ | ts-travel-service✓ | ts-travel2-service⚠️
L2: ts-assurance-service | ts-basic-service | ts-contacts-service | ts-food-service | ts-route-plan-service⚠️ | ts-route-service | ts-security-service | ts-train-service | ts-ui-dashboard✓ | ts-user-service
L3: loadgenerator⚠️ | ts-price-service | ts-station-service
```

**V4 漏的真路径节点**: `loadgenerator`, `ts-route-plan-service`, `ts-travel2-service`

---

### Case 9: `ts2-ts-station-service-dns-nn49s2`

- RC: `ts-station-service` | cascade=21 | L=9 V3=13 V4=13 | V4真漏=2

```
L0: ts-station-service[RC]
L1: ts-basic-service✓
L2: ts-preserve-service✓ | ts-price-service | ts-route-service | ts-train-service | ts-travel-service✓ | ts-travel2-service✓
L3: ts-assurance-service✓ | ts-contacts-service✓ | ts-food-service✓ | ts-order-service | ts-route-plan-service⚠️ | ts-seat-service✓ | ts-security-service | ts-travel-plan-service✓ | ts-ui-dashboard✓ | ts-user-service
L4: loadgenerator⚠️ | ts-config-service✓ | ts-order-other-service
```

**V4 漏的真路径节点**: `loadgenerator`, `ts-route-plan-service`

---

### Case 10: `ts3-ts-basic-service-stress-p545b4`

- RC: `ts-basic-service` | cascade=21 | L=9 V3=7 V4=7 | V4真漏=2

```
L0: ts-basic-service[RC]
L1: ts-preserve-service⚠️ | ts-price-service | ts-route-service | ts-station-service | ts-train-service | ts-travel-service✓ | ts-travel2-service✓
L2: ts-assurance-service | ts-contacts-service | ts-food-service | ts-order-service | ts-route-plan-service✓ | ts-seat-service | ts-security-service | ts-travel-plan-service✓ | ts-ui-dashboard✓ | ts-user-service
L3: loadgenerator⚠️ | ts-config-service | ts-order-other-service
```

**V4 漏的真路径节点**: `loadgenerator`, `ts-preserve-service`

---

### Case 11: `ts4-ts-seat-service-delay-ddn72q`

- RC: `ts-seat-service` | cascade=21 | L=8 V3=7 V4=6 | V4真漏=2
- V4 删掉 (vs V3): `ts-preserve-service`

```
L0: ts-seat-service[RC]
L1: ts-config-service | ts-order-other-service | ts-order-service | ts-preserve-service⚠️ | ts-travel-plan-service✓ | ts-travel-service✓ | ts-travel2-service✓
L2: ts-assurance-service | ts-basic-service | ts-contacts-service | ts-food-service | ts-route-plan-service✓ | ts-route-service | ts-security-service | ts-train-service | ts-ui-dashboard✓ | ts-user-service
L3: loadgenerator⚠️ | ts-price-service | ts-station-service
```

**V4 漏的真路径节点**: `loadgenerator`, `ts-preserve-service`

---

### Case 12: `ts4-ts-station-service-bandwidth-nfljv5`

- RC: `ts-station-service` | cascade=17 | L=9 V3=7 V4=7 | V4真漏=2

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
⚠ disconnected: loadgenerator, ts-ui-dashboard
```

**V4 漏的真路径节点**: `loadgenerator`, `ts-preserve-service`

---

### Case 13: `ts0-ts-travel-plan-service-response-delay-pfwcqk`

- RC: `ts-travel-plan-service` | cascade=15 | L=3 V3=2 V4=2 | V4真漏=1

```
L0: ts-travel-plan-service[RC]
L1: ts-route-plan-service | ts-seat-service | ts-train-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-basic-service | ts-config-service | ts-order-other-service | ts-order-service | ts-route-service | ts-travel-service | ts-travel2-service
L3: ts-price-service | ts-station-service
```

**V4 漏的真路径节点**: `loadgenerator`

---

### Case 14: `ts0-ts-travel2-service-request-delay-lzpl9v`

- RC: `ts-travel2-service` | cascade=15 | L=5 V3=4 V4=4 | V4真漏=1

```
L0: ts-travel2-service[RC]
L1: ts-basic-service | ts-route-plan-service✓ | ts-route-service | ts-seat-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-config-service | ts-order-other-service | ts-order-service | ts-price-service | ts-station-service | ts-train-service | ts-travel-plan-service✓ | ts-travel-service
```

**V4 漏的真路径节点**: `loadgenerator`

---

### Case 15: `ts1-ts-station-food-service-stress-rlvxhc`

- RC: `ts-station-food-service` | cascade=7 | L=5 V3=15 V4=12 | V4真漏=1
- V4 删掉 (vs V3): `ts-preserve-service`, `ts-travel2-service`, `ts-user-service`

```
L0: ts-station-food-service[RC]
L1: ts-food-service✓
L2: ts-train-food-service✓ | ts-travel-service✓ | ts-ui-dashboard✓
L3: loadgenerator⚠️ | ts-route-service✓
```

**V4 漏的真路径节点**: `loadgenerator`

---

### Case 16: `ts1-ts-train-service-pod-failure-5qwqdz`

- RC: `ts-train-service` | cascade=13 | L=10 V3=6 V4=6 | V4真漏=1

```
L0: ts-train-service[RC]
L1: ts-basic-service✓ | ts-travel-plan-service✓
L2: ts-price-service | ts-route-plan-service⚠️ | ts-route-service | ts-seat-service | ts-station-service | ts-travel-service✓ | ts-travel2-service✓
L3: ts-config-service | ts-order-other-service | ts-order-service
```

**V4 漏的真路径节点**: `ts-route-plan-service`
**V4 漏对了**: `loadgenerator`, `ts-preserve-service`, `ts-train-service-6854555655-4gmbw`

---

### Case 17: `ts2-ts-travel-plan-service-response-delay-chhzjz`

- RC: `ts-travel-plan-service` | cascade=15 | L=3 V3=2 V4=2 | V4真漏=1

```
L0: ts-travel-plan-service[RC]
L1: ts-route-plan-service | ts-seat-service | ts-train-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-basic-service | ts-config-service | ts-order-other-service | ts-order-service | ts-route-service | ts-travel-service | ts-travel2-service
L3: ts-price-service | ts-station-service
```

**V4 漏的真路径节点**: `loadgenerator`

---

### Case 18: `ts3-ts-order-service-pod-failure-7xsmwd`

- RC: `ts-order-service` | cascade=3 | L=13 V3=7 V4=7 | V4真漏=1

```
L0: ts-order-service[RC]
L1: ts-ui-dashboard✓
L2: loadgenerator⚠️
```

**V4 漏的真路径节点**: `loadgenerator`
**V4 漏对了**: `ts-order-service-6f4cfb5df7-27ppv`, `ts-route-plan-service`, `ts-travel-plan-service`, `ts-travel-service`, `ts-travel2-service`

---

### Case 19: `ts3-ts-preserve-service-container-kill-k7k8g5`

- RC: `ts-preserve-service` | cascade=18 | L=4 V3=2 V4=2 | V4真漏=1

```
L0: ts-preserve-service[RC]
L1: ts-assurance-service | ts-basic-service | ts-contacts-service | ts-food-service | ts-order-service | ts-seat-service | ts-security-service | ts-travel-service | ts-ui-dashboard✓ | ts-user-service
L2: loadgenerator⚠️ | ts-config-service | ts-order-other-service | ts-price-service | ts-route-service | ts-station-service | ts-train-service
```

**V4 漏的真路径节点**: `loadgenerator`
**V4 漏对了**: `ts-preserve-service-5d979f4b55-n6ccw`

---

### Case 20: `ts3-ts-travel-plan-service-exception-zgsz8w`

- RC: `ts-travel-plan-service` | cascade=15 | L=4 V3=2 V4=2 | V4真漏=1

```
L0: ts-travel-plan-service[RC]
L1: ts-route-plan-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-route-service | ts-travel-service | ts-travel2-service
L3: ts-basic-service | ts-seat-service
L4: ts-config-service | ts-order-other-service | ts-order-service | ts-price-service | ts-station-service | ts-train-service
```

**V4 漏的真路径节点**: `loadgenerator`
**V4 漏对了**: `ts-travel-plan-service-b49559b55-dnjp9`

---

### Case 21: `ts3-ts-travel-plan-service-request-delay-kxhn5n`

- RC: `ts-travel-plan-service` | cascade=15 | L=3 V3=2 V4=2 | V4真漏=1

```
L0: ts-travel-plan-service[RC]
L1: ts-route-plan-service | ts-seat-service | ts-train-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-basic-service | ts-config-service | ts-order-other-service | ts-order-service | ts-route-service | ts-travel-service | ts-travel2-service
L3: ts-price-service | ts-station-service
```

**V4 漏的真路径节点**: `loadgenerator`

---

### Case 22: `ts3-ts-travel2-service-container-kill-72qrd2`

- RC: `ts-travel2-service` | cascade=15 | L=6 V3=4 V4=4 | V4真漏=1

```
L0: ts-travel2-service[RC]
L1: ts-basic-service | ts-route-plan-service✓ | ts-route-service | ts-seat-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-config-service | ts-order-other-service | ts-order-service | ts-price-service | ts-station-service | ts-train-service | ts-travel-plan-service✓ | ts-travel-service
```

**V4 漏的真路径节点**: `loadgenerator`
**V4 漏对了**: `ts-travel2-service-8557fd66df-mqfrk`

---

### Case 23: `ts3-ts-travel2-service-container-kill-vt4nvr`

- RC: `ts-travel2-service` | cascade=15 | L=6 V3=4 V4=4 | V4真漏=1

```
L0: ts-travel2-service[RC]
L1: ts-basic-service | ts-route-plan-service✓ | ts-route-service | ts-seat-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-config-service | ts-order-other-service | ts-order-service | ts-price-service | ts-station-service | ts-train-service | ts-travel-plan-service✓ | ts-travel-service
```

**V4 漏的真路径节点**: `loadgenerator`
**V4 漏对了**: `ts-travel2-service-8557fd66df-kvg4k`

---

### Case 24: `ts4-ts-route-plan-service-bandwidth-q5lcsx`

- RC: `ts-route-plan-service` | cascade=15 | L=4 V3=5 V4=4 | V4真漏=1
- V4 删掉 (vs V3): `ts-food-service`

```
L0: ts-route-plan-service[RC]
L1: ts-route-service | ts-travel-plan-service✓ | ts-travel-service✓ | ts-travel2-service
L2: ts-basic-service | ts-seat-service | ts-train-service | ts-ui-dashboard✓
L3: loadgenerator⚠️ | ts-config-service | ts-order-other-service | ts-order-service | ts-price-service | ts-station-service
```

**V4 漏的真路径节点**: `loadgenerator`

---

### Case 25: `ts4-ts-seat-service-bandwidth-k2bwt2`

- RC: `ts-seat-service` | cascade=15 | L=8 V3=7 V4=7 | V4真漏=1

```
L0: ts-seat-service[RC]
L1: ts-config-service✓ | ts-order-other-service | ts-order-service | ts-travel-plan-service✓ | ts-travel-service✓ | ts-travel2-service✓
L2: ts-basic-service | ts-route-plan-service✓ | ts-route-service | ts-train-service
L3: ts-price-service | ts-station-service
⚠ disconnected: loadgenerator, ts-ui-dashboard
```

**V4 漏的真路径节点**: `loadgenerator`
**V4 漏对了**: `ts-preserve-service`

---

### Case 26: `ts5-ts-preserve-service-partition-dkhqzh`

- RC: `ts-preserve-service` | cascade=18 | L=3 V3=4 V4=4 | V4真漏=1

```
L0: ts-preserve-service[RC]
L1: ts-assurance-service | ts-basic-service | ts-contacts-service | ts-food-service | ts-order-service | ts-security-service | ts-travel-service✓ | ts-ui-dashboard✓ | ts-user-service
L2: loadgenerator⚠️ | ts-order-other-service | ts-price-service | ts-route-service | ts-seat-service✓ | ts-station-service | ts-train-service
L3: ts-config-service
```

**V4 漏的真路径节点**: `loadgenerator`

---

### Case 27: `ts5-ts-travel-plan-service-delay-v5ptlf`

- RC: `ts-travel-plan-service` | cascade=15 | L=3 V3=6 V4=6 | V4真漏=1

```
L0: ts-travel-plan-service[RC]
L1: ts-route-plan-service✓ | ts-seat-service✓ | ts-train-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-basic-service | ts-config-service | ts-order-other-service | ts-order-service | ts-route-service | ts-travel-service✓ | ts-travel2-service✓
L3: ts-price-service | ts-station-service
```

**V4 漏的真路径节点**: `loadgenerator`

---

### Case 28: `ts7-ts-travel-service-response-delay-t48wrc`

- RC: `ts-travel-service` | cascade=23 | L=5 V3=4 V4=4 | V4真漏=1

```
L0: ts-travel-service[RC]
L1: ts-basic-service | ts-food-service | ts-preserve-service | ts-route-plan-service✓ | ts-route-service | ts-seat-service | ts-ui-dashboard✓
L2: loadgenerator⚠️ | ts-assurance-service | ts-config-service | ts-contacts-service | ts-order-other-service | ts-order-service | ts-price-service | ts-security-service | ts-station-food-service | ts-station-service | ts-train-food-service | ts-train-service | ts-travel-plan-service✓ | ts-travel2-service | ts-user-service
```

**V4 漏的真路径节点**: `loadgenerator`

---

