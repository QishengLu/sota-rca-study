# thinkdepthai 失败 case 三分类清单

**生成日期**：2026-05-03
**Agent 框架**：thinkdepthai（Deep_Research）

## 集合定义

| 集合 | exp_id | 大小 | 定义 |
|---|---|---|---|
| qwen3.5-plus 固定失败 | `thinkdepthai-qwen3.5-plus-2026-02-15-mw-v4-run` | 53 | resample-1..4 中 ≥3/4 次错的 case（= v4 mw run 输入集） |
| claude-sonnet-4.6 失败 | `thinkdepthai-claude-sonnet-4.6` | 51 | stage='judged' 且 correct=false |

## 三分类汇总

| 分类 | 数量 | ★ 在 openrca2-lite-v2 中 |
|---|---|---|
| 两模型都失败 | 16 | 6 |
| 仅 qwen3.5-plus 失败 | 37 | 20 |
| 仅 sonnet-4.6 失败 | 35 | 14 |
| **总计** | **88** | **40** |

★ = 该 case 也存在于 openrca2-lite-v2 的 500 case 中。

## 1) 两个模型都失败 (16)

-   ts0-ts-travel-plan-service-response-delay-pfwcqk
-   ts0-ts-travel-plan-service-time-rjdx4x
- ★ ts0-ts-travel-service-mysql-28wmss
- ★ ts1-ts-config-service-latency-5kkcrc
- ★ ts1-ts-food-service-response-patch-body-qjhx5h
- ★ ts2-ts-food-service-bandwidth-b5qvk5
-   ts2-ts-station-service-dns-nn49s2
- ★ ts2-ts-travel-plan-service-stress-ph59w4
-   ts3-ts-basic-service-partition-w5hbjw
-   ts3-ts-preserve-service-container-kill-k7k8g5
-   ts3-ts-station-service-return-4z45w8
-   ts4-ts-food-service-container-kill-lv5htg
-   ts4-ts-route-plan-service-bandwidth-q5lcsx
-   ts4-ts-seat-service-bandwidth-k2bwt2
-   ts4-ts-station-service-bandwidth-nfljv5
- ★ ts4-ts-travel2-service-response-replace-body-c5mklh

## 2) 仅 qwen3.5-plus 失败 (37)

- ★ ts0-ts-auth-service-stress-nlpsfx
- ★ ts0-ts-consign-price-service-stress-t67vtg
-   ts0-ts-food-service-stress-xfwkgh
- ★ ts0-ts-order-service-stress-cklk2p
- ★ ts0-ts-price-service-stress-n787pd
- ★ ts0-ts-station-food-service-stress-j5qdln
- ★ ts0-ts-station-service-bandwidth-bp5k94
-   ts1-ts-consign-service-time-hslmgs
-   ts1-ts-inside-payment-service-stress-6qq6f6
-   ts1-ts-station-food-service-stress-rlvxhc
-   ts1-ts-train-service-pod-failure-5qwqdz
- ★ ts1-ts-train-service-stress-jfr96k
-   ts1-ts-travel-service-response-replace-body-vzcxrp
- ★ ts2-ts-auth-service-stress-lq54b9
-   ts2-ts-config-service-stress-j8gm95
-   ts2-ts-food-service-container-kill-cqcxsh
- ★ ts2-ts-order-other-service-container-kill-48rlds
- ★ ts2-ts-order-other-service-stress-sv9xq6
-   ts2-ts-order-service-stress-967z6d
-   ts2-ts-seat-service-stress-b7h7m9
-   ts2-ts-train-service-stress-qv9rrc
- ★ ts3-ts-basic-service-stress-p545b4
-   ts3-ts-contacts-service-container-kill-s624d8
-   ts3-ts-order-service-container-kill-gh2xcv
- ★ ts3-ts-order-service-pod-failure-7xsmwd
-   ts3-ts-station-service-stress-4wtfqh
- ★ ts3-ts-train-food-service-stress-dqsrx2
- ★ ts3-ts-travel-service-container-kill-jctldw
-   ts3-ts-travel-service-stress-qscl29
- ★ ts3-ts-travel2-service-container-kill-72qrd2
- ★ ts3-ts-travel2-service-container-kill-vt4nvr
- ★ ts3-ts-user-service-stress-7btwsk
-   ts4-ts-security-service-stress-2q5qsb
- ★ ts5-ts-basic-service-stress-zf2fd7
- ★ ts5-ts-cancel-service-stress-d8xbsn
- ★ ts5-ts-order-service-corrupt-bd4p5g
-   ts5-ts-preserve-service-pod-kill-5zcl7w

## 3) 仅 claude-sonnet-4.6 失败 (35)

-   ts0-ts-travel2-service-request-delay-lzpl9v
-   ts1-ts-assurance-service-container-kill-qw48fm
- ★ ts1-ts-route-plan-service-request-replace-method-bn6rxm
-   ts2-ts-food-service-container-kill-jhdf8g
- ★ ts2-ts-preserve-service-stress-s4zzmk
- ★ ts2-ts-route-plan-service-response-replace-body-dghfbk
-   ts2-ts-travel-plan-service-response-delay-chhzjz
-   ts3-ts-food-service-container-kill-g4zbt8
-   ts3-ts-food-service-response-replace-body-mn5pkz
-   ts3-ts-route-plan-service-request-abort-bm4p5w
- ★ ts3-ts-travel-plan-service-exception-zgsz8w
-   ts3-ts-travel-plan-service-request-delay-kxhn5n
-   ts4-ts-basic-service-bandwidth-fn4pnv
- ★ ts4-ts-basic-service-response-replace-code-hvsqnm
-   ts4-ts-order-other-service-exception-nh22zm
-   ts4-ts-preserve-service-bandwidth-f9jq67
-   ts4-ts-preserve-service-request-delay-lb48d2
-   ts4-ts-route-plan-service-corrupt-qgnf8n
-   ts4-ts-route-plan-service-response-delay-98r8wt
-   ts4-ts-seat-service-delay-ddn72q
-   ts4-ts-travel-plan-service-loss-ttgbmd
- ★ ts4-ts-travel-service-response-replace-body-vhbkq2
- ★ ts4-ts-travel2-service-request-abort-ttlcpg
- ★ ts5-ts-food-service-response-replace-code-f8pjnn
- ★ ts5-ts-preserve-service-exception-pfn7ml
-   ts5-ts-preserve-service-partition-dkhqzh
-   ts5-ts-preserve-service-response-delay-g8zznv
- ★ ts5-ts-seat-service-response-replace-body-cjm68r
- ★ ts5-ts-security-service-bandwidth-tmtfcl
-   ts5-ts-travel-plan-service-container-kill-4s877v
-   ts5-ts-travel-plan-service-delay-v5ptlf
- ★ ts6-ts-security-service-response-replace-code-nj74q4
-   ts7-ts-travel-service-response-abort-tx5942
- ★ ts7-ts-travel-service-response-delay-t48wrc
- ★ ts8-ts-route-plan-service-response-delay-64cl6j

---

## qwen3.5-plus resample ≥2/4 错（67 case）

定义：105 个 baseline 失败 case 中，4 次 resample 又有 ≥2 次错的。

- ★ ts0-ts-auth-service-stress-nlpsfx
- ★ ts0-ts-consign-price-service-stress-t67vtg
-   ts0-ts-food-service-stress-xfwkgh
- ★ ts0-ts-order-service-stress-cklk2p
- ★ ts0-ts-price-service-stress-n787pd
-   ts0-ts-seat-service-pod-failure-c87xdg
- ★ ts0-ts-station-food-service-stress-j5qdln
- ★ ts0-ts-station-service-bandwidth-bp5k94
-   ts0-ts-travel-plan-service-response-delay-pfwcqk
-   ts0-ts-travel-plan-service-time-rjdx4x
- ★ ts0-ts-travel-service-mysql-28wmss
-   ts0-ts-travel-service-pod-failure-cvrncg
- ★ ts1-ts-config-service-latency-5kkcrc
-   ts1-ts-consign-service-time-hslmgs
- ★ ts1-ts-food-service-response-patch-body-qjhx5h
-   ts1-ts-inside-payment-service-stress-6qq6f6
-   ts1-ts-seat-service-partition-gtmt4k
-   ts1-ts-station-food-service-stress-rlvxhc
-   ts1-ts-train-service-pod-failure-5qwqdz
- ★ ts1-ts-train-service-stress-jfr96k
-   ts1-ts-travel-service-response-replace-body-vzcxrp
- ★ ts2-ts-auth-service-stress-lq54b9
-   ts2-ts-config-service-stress-j8gm95
- ★ ts2-ts-food-service-bandwidth-b5qvk5
-   ts2-ts-food-service-container-kill-cqcxsh
- ★ ts2-ts-order-other-service-container-kill-48rlds
- ★ ts2-ts-order-other-service-stress-sv9xq6
-   ts2-ts-order-service-stress-967z6d
-   ts2-ts-seat-service-container-kill-pt6tdw
-   ts2-ts-seat-service-stress-b7h7m9
-   ts2-ts-station-service-dns-nn49s2
-   ts2-ts-train-food-service-container-kill-xxhlgq
-   ts2-ts-train-service-stress-qv9rrc
- ★ ts2-ts-travel-plan-service-stress-ph59w4
-   ts3-ts-basic-service-partition-w5hbjw
- ★ ts3-ts-basic-service-stress-p545b4
-   ts3-ts-contacts-service-container-kill-s624d8
-   ts3-ts-food-service-response-replace-body-mn5pkz
-   ts3-ts-order-service-container-kill-gh2xcv
- ★ ts3-ts-order-service-pod-failure-7xsmwd
-   ts3-ts-preserve-service-container-kill-k7k8g5
-   ts3-ts-station-service-return-4z45w8
-   ts3-ts-station-service-stress-4wtfqh
- ★ ts3-ts-train-food-service-stress-dqsrx2
- ★ ts3-ts-travel-service-container-kill-jctldw
- ★ ts3-ts-travel-service-request-delay-qhz8pd
-   ts3-ts-travel-service-stress-qscl29
- ★ ts3-ts-travel2-service-container-kill-72qrd2
- ★ ts3-ts-travel2-service-container-kill-vt4nvr
- ★ ts3-ts-user-service-stress-7btwsk
-   ts4-ts-food-service-container-kill-lv5htg
-   ts4-ts-route-plan-service-bandwidth-q5lcsx
-   ts4-ts-seat-service-bandwidth-k2bwt2
-   ts4-ts-seat-service-delay-ddn72q
-   ts4-ts-security-service-stress-2q5qsb
-   ts4-ts-station-service-bandwidth-nfljv5
-   ts4-ts-station-service-corrupt-j2zgbd
- ★ ts4-ts-travel2-service-response-replace-body-c5mklh
- ★ ts5-ts-basic-service-stress-zf2fd7
- ★ ts5-ts-cancel-service-stress-d8xbsn
- ★ ts5-ts-order-service-corrupt-bd4p5g
-   ts5-ts-preserve-service-pod-kill-5zcl7w
-   ts5-ts-preserve-service-response-delay-g8zznv
-   ts5-ts-seat-service-corrupt-v8cmmz
- ★ ts5-ts-seat-service-response-replace-body-cjm68r
- ★ ts5-ts-train-food-service-stress-2v2vmx
-   ts5-ts-travel-plan-service-bandwidth-w6w6c2

---

## 建议保留清单（qwen 105 ∪ sonnet 51 去重）

合计 134 个 case（qwen3.5-plus baseline 失败 105 + claude-sonnet-4.6 失败 51，去重后）。

-   ts0-mysql-container-kill-9t6n24
- ★ ts0-ts-auth-service-stress-nlpsfx
- ★ ts0-ts-consign-price-service-stress-t67vtg
-   ts0-ts-food-service-stress-xfwkgh
-   ts0-ts-order-other-service-corrupt-wkdp68
- ★ ts0-ts-order-service-stress-cklk2p
- ★ ts0-ts-price-service-stress-n787pd
- ★ ts0-ts-route-service-stress-kstvv2
-   ts0-ts-seat-service-pod-failure-c87xdg
- ★ ts0-ts-station-food-service-stress-j5qdln
- ★ ts0-ts-station-service-bandwidth-bp5k94
-   ts0-ts-travel-plan-service-response-delay-pfwcqk
-   ts0-ts-travel-plan-service-time-rjdx4x
- ★ ts0-ts-travel-service-mysql-28wmss
-   ts0-ts-travel-service-pod-failure-cvrncg
-   ts0-ts-travel2-service-request-delay-lzpl9v
-   ts1-ts-assurance-service-container-kill-qw48fm
- ★ ts1-ts-config-service-latency-5kkcrc
-   ts1-ts-consign-service-time-hslmgs
- ★ ts1-ts-food-service-response-patch-body-qjhx5h
-   ts1-ts-inside-payment-service-stress-6qq6f6
- ★ ts1-ts-payment-service-stress-5778hg
- ★ ts1-ts-route-plan-service-request-replace-method-bn6rxm
-   ts1-ts-seat-service-partition-gtmt4k
-   ts1-ts-station-food-service-pod-failure-td2qj4
-   ts1-ts-station-food-service-stress-rlvxhc
- ★ ts1-ts-station-service-delay-hwcd55
-   ts1-ts-train-service-pod-failure-5qwqdz
- ★ ts1-ts-train-service-stress-jfr96k
- ★ ts1-ts-travel-plan-service-return-kp5bqw
-   ts1-ts-travel-service-response-replace-body-vzcxrp
- ★ ts1-ts-travel-service-response-replace-code-w6jftp
- ★ ts2-ts-auth-service-stress-lq54b9
-   ts2-ts-config-service-stress-j8gm95
- ★ ts2-ts-consign-price-service-stress-7r95bt
- ★ ts2-ts-food-service-bandwidth-b5qvk5
-   ts2-ts-food-service-container-kill-cqcxsh
-   ts2-ts-food-service-container-kill-jhdf8g
-   ts2-ts-food-service-response-abort-5k6q44
- ★ ts2-ts-order-other-service-container-kill-48rlds
- ★ ts2-ts-order-other-service-stress-sv9xq6
-   ts2-ts-order-service-stress-967z6d
-   ts2-ts-preserve-service-request-replace-method-nsz4x4
- ★ ts2-ts-preserve-service-stress-s4zzmk
- ★ ts2-ts-route-plan-service-response-replace-body-dghfbk
- ★ ts2-ts-route-service-stress-f8d5js
-   ts2-ts-seat-service-container-kill-pt6tdw
-   ts2-ts-seat-service-stress-b7h7m9
-   ts2-ts-station-service-dns-nn49s2
-   ts2-ts-train-food-service-container-kill-xxhlgq
-   ts2-ts-train-service-stress-qv9rrc
-   ts2-ts-travel-plan-service-response-delay-chhzjz
- ★ ts2-ts-travel-plan-service-stress-ph59w4
-   ts2-ts-travel-service-request-delay-5hk27g
-   ts3-ts-basic-service-partition-w5hbjw
- ★ ts3-ts-basic-service-stress-p545b4
-   ts3-ts-contacts-service-container-kill-262mnp
-   ts3-ts-contacts-service-container-kill-s624d8
-   ts3-ts-food-service-container-kill-g4zbt8
-   ts3-ts-food-service-response-replace-body-mn5pkz
-   ts3-ts-order-service-container-kill-gh2xcv
- ★ ts3-ts-order-service-pod-failure-7xsmwd
-   ts3-ts-payment-service-container-kill-mfnjvp
- ★ ts3-ts-payment-service-stress-hndhvq
-   ts3-ts-preserve-service-container-kill-k7k8g5
-   ts3-ts-route-plan-service-request-abort-bm4p5w
-   ts3-ts-seat-service-request-replace-path-749bws
-   ts3-ts-station-service-return-4z45w8
-   ts3-ts-station-service-stress-4wtfqh
- ★ ts3-ts-train-food-service-stress-dqsrx2
- ★ ts3-ts-travel-plan-service-exception-zgsz8w
-   ts3-ts-travel-plan-service-request-delay-kxhn5n
- ★ ts3-ts-travel-service-container-kill-jctldw
- ★ ts3-ts-travel-service-request-delay-qhz8pd
-   ts3-ts-travel-service-stress-qscl29
- ★ ts3-ts-travel2-service-container-kill-72qrd2
- ★ ts3-ts-travel2-service-container-kill-vt4nvr
- ★ ts3-ts-travel2-service-response-abort-skwk69
- ★ ts3-ts-user-service-stress-7btwsk
-   ts4-ts-basic-service-bandwidth-fn4pnv
- ★ ts4-ts-basic-service-response-replace-code-hvsqnm
-   ts4-ts-food-service-container-kill-lv5htg
- ★ ts4-ts-food-service-corrupt-ccxs65
-   ts4-ts-order-other-service-exception-nh22zm
-   ts4-ts-preserve-service-bandwidth-f9jq67
-   ts4-ts-preserve-service-request-delay-lb48d2
-   ts4-ts-preserve-service-request-delay-v9bxvq
-   ts4-ts-route-plan-service-bandwidth-q5lcsx
-   ts4-ts-route-plan-service-corrupt-qgnf8n
-   ts4-ts-route-plan-service-response-delay-98r8wt
- ★ ts4-ts-route-plan-service-response-delay-c4j9pd
- ★ ts4-ts-route-plan-service-stress-wz6xpg
-   ts4-ts-seat-service-bandwidth-k2bwt2
-   ts4-ts-seat-service-delay-ddn72q
- ★ ts4-ts-seat-service-stress-sh4z62
-   ts4-ts-security-service-corrupt-9lndmd
-   ts4-ts-security-service-stress-2q5qsb
-   ts4-ts-station-service-bandwidth-nfljv5
-   ts4-ts-station-service-corrupt-j2zgbd
-   ts4-ts-travel-plan-service-loss-ttgbmd
- ★ ts4-ts-travel-service-response-replace-body-vhbkq2
- ★ ts4-ts-travel2-service-request-abort-ttlcpg
- ★ ts4-ts-travel2-service-response-replace-body-c5mklh
- ★ ts5-ts-basic-service-stress-zf2fd7
- ★ ts5-ts-cancel-service-stress-d8xbsn
- ★ ts5-ts-food-service-response-replace-code-f8pjnn
- ★ ts5-ts-order-service-corrupt-bd4p5g
- ★ ts5-ts-preserve-service-exception-pfn7ml
-   ts5-ts-preserve-service-partition-dkhqzh
-   ts5-ts-preserve-service-pod-kill-5zcl7w
-   ts5-ts-preserve-service-request-replace-path-5z54d6
-   ts5-ts-preserve-service-response-delay-g8zznv
-   ts5-ts-preserve-service-response-delay-wrbsmb
- ★ ts5-ts-price-service-container-kill-ncqc2p
-   ts5-ts-seat-service-corrupt-v8cmmz
-   ts5-ts-seat-service-loss-5kglkt
- ★ ts5-ts-seat-service-response-replace-body-cjm68r
- ★ ts5-ts-security-service-bandwidth-tmtfcl
- ★ ts5-ts-train-food-service-stress-2v2vmx
-   ts5-ts-travel-plan-service-bandwidth-w6w6c2
-   ts5-ts-travel-plan-service-container-kill-4s877v
-   ts5-ts-travel-plan-service-delay-v5ptlf
- ★ ts5-ts-travel2-service-response-delay-xtn266
-   ts5-ts-travel2-service-stress-v9ch2t
- ★ ts6-ts-security-service-response-replace-code-nj74q4
- ★ ts6-ts-station-service-stress-wl6rqj
- ★ ts7-ts-assurance-service-stress-lth6xq
-   ts7-ts-travel-service-loss-qpj4gj
-   ts7-ts-travel-service-response-abort-tx5942
- ★ ts7-ts-travel-service-response-delay-t48wrc
- ★ ts8-ts-route-plan-service-response-delay-64cl6j
-   ts8-ts-travel-service-corrupt-fsmp6c
- ★ ts9-mysql-delay-c8xxmb
- ★ ts9-ts-order-service-container-kill-bsh6lx
