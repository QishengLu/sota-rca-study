# Batch 1 — All 20 failed cases with llm_intents labels

Revised: analyze all cases that already have LLM intent labels, instead of stratified 15.

## Distribution

| fault_category | population (105) | labeled (20) |
|---|---|---|
| JVMChaos | 39 | 8 |
| PodChaos | 22 | 7 |
| NetworkChaos | 23 | 3 |
| HTTPFault | 20 | 2 |
| **Total** | **105** | **20** |

## Cases

| # | dataset_index | fault_category | fault_type | n_svc | spl | rounds |
|---|---|---|---|---|---|---|
| 1 | 33 | JVMChaos | JVMMemoryStress | 4 | 3 | 60 |
| 2 | 156 | JVMChaos | JVMMemoryStress | 13 | 4 | 48 |
| 3 | 247 | JVMChaos | JVMMemoryStress | 4 | 3 | 64 |
| 4 | 807 | JVMChaos | JVMMemoryStress | 4 | 3 | 53 |
| 5 | 1394 | JVMChaos | JVMMemoryStress | 9 | 4 | 60 |
| 6 | 2130 | JVMChaos | JVMReturn | 10 | 5 | 52 |
| 7 | 2390 | JVMChaos | JVMMemoryStress | 5 | 3 | 48 |
| 8 | 2988 | JVMChaos | JVMCPUStress | 9 | 4 | 55 |
| 9 | 755 | NetworkChaos | NetworkPartition | 7 | 3 | 47 |
| 10 | 2682 | NetworkChaos | NetworkDelay | 8 | 3 | 56 |
| 11 | 2700 | NetworkChaos | NetworkCorrupt | 4 | 3 | 51 |
| 12 | 804 | PodChaos | PodFailure | 10 | 4 | 73 |
| 13 | 1917 | PodChaos | ContainerKill | 11 | 4 | 68 |
| 14 | 2211 | PodChaos | ContainerKill | 7 | 3 | 67 |
| 15 | 3114 | PodChaos | PodKill | 4 | 3 | 54 |
| 16 | 3138 | PodChaos | ContainerKill | 10 | 5 | 40 |
| 17 | 4375 | PodChaos | ContainerKill | 6 | 3 | 51 |
| 18 | 4893 | PodChaos | ContainerKill | 13 | 3 | 50 |
| 19 | 2231 | HTTPFault | HTTPRequestDelay | 7 | 2 | 40 |
| 20 | 3120 | HTTPFault | HTTPRequestReplacePath | 3 | 2 | 53 |

## Also analyzed (no intent labels, from original sample)

| dataset_index | fault_category | fault_type | notes |
|---|---|---|---|
| 339 | JVMChaos | JVMMySQLLatency | analysis complete, no intents |
| 832 | JVMChaos | JVMReturn | analysis complete, no intents |
| 3868 | JVMChaos | JVMLatency | analysis complete, no intents |
