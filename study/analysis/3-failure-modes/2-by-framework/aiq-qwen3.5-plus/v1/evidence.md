# Case evidence — aiq-qwen3.5-plus (113 failed cases)


## HTTPFault (15 cases)

### case_315  [HTTPFault/HTTPResponseDelay]  spl=2 n_svc=3
- gt: ['ts-travel-plan-service', 'ts-train-service']
- pred: ['ts-seat-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['travelplanservice', 'uidashboard'] missed=[] hallucinated=['seatservice', 'travelservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-order-service', 2010), ('stage_1_refine1', 'ts-order-service', 3335)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-seat-service', 1), ('ts-travel-service', 1), ('ts-travel-plan-service', 2)]
- log err_delta top-: [('ts-food-service', -178), ('ts-order-service', -29), ('ts-preserve-service', -29)]
- gt log_err_rows: [('ts-travel-plan-service', 0, 2, 2)]
- gt metric anomalies (4/60 total): [('ts-train-service', 'processedLogs', 20.140314482198654), ('ts-travel-plan-service', 'http.server.request.duration', 13.052222565727861), ('ts-train-service', 'processedSpans', 10.626742553635129)]

### case_572  [HTTPFault/HTTPResponsePatchBody]  spl=3 n_svc=4
- gt: ['ts-food-service', 'ts-train-food-service']
- pred: ['ts-consign-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['uidashboard'] missed=['foodservice', 'preserveservice'] hallucinated=['consignservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-consign-service', 2760), ('stage_2_refine2', 'ts-consign-service', 2754)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-consign-service', 122)]
- log err_delta top-: [('ts-food-service', -49), ('ts-order-service', -13), ('ts-preserve-service', -13), ('ts-delivery-service', -1), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-food-service', 281, 232, -49)]
- gt metric anomalies (4/60 total): [('ts-train-food-service', 'jvm.gc.duration', 1122999999.9999998), ('ts-train-food-service', 'jvm.class.count', 499999999.99999994), ('ts-train-food-service', 'jvm.class.loaded', 249999999.99999997)]

### case_860  [HTTPFault/HTTPResponseReplaceBody]  spl=2 n_svc=7
- gt: ['ts-travel-service', 'ts-seat-service']
- pred: ['ts-basic-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['preserveservice', 'routeplanservice', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['foodservice'] hallucinated=['basicservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-basic-service', 2763), ('stage_1_refine1', 'ts-travel-service', 3394)]  changed_across_stages=True
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-travel-plan-service', 8), ('ts-ui-dashboard', 10), ('ts-route-plan-service', 56), ('ts-travel-service', 1168)]
- log err_delta top-: [('ts-food-service', -165), ('ts-order-service', -43), ('ts-preserve-service', -40), ('ts-inside-payment-service', -1)]
- gt log_err_rows: [('ts-travel-service', 0, 1168, 1168)]
- gt metric anomalies (16/60 total): [('ts-travel-service', 'jvm.class.count', 20250000000.0), ('ts-travel-service', 'jvm.class.loaded', 5750000000.0), ('ts-travel-service', 'k8s.pod.filesystem.usage', 21.843073813604732)]

### case_1159  [HTTPFault/HTTPResponseDelay]  spl=2 n_svc=4
- gt: ['ts-food-service', 'ts-train-food-service']
- pred: ['ts-rabbitmq']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['foodservice'] missed=['preserveservice', 'uidashboard'] hallucinated=['deliveryservice', 'notificationservice', 'rabbitmq']
- terminators (2/3 one_truncated): [('stage_0_main', None, 2704), ('stage_1_refine1', 'ts-rabbitmq', 2262)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -315), ('ts-order-service', -71), ('ts-preserve-service', -71), ('ts-inside-payment-service', -1)]
- gt log_err_rows: [('ts-food-service', 367, 52, -315)]
- gt metric anomalies (8/60 total): [('ts-train-food-service', 'jvm.class.count', 750000000.0), ('ts-train-food-service', 'jvm.class.loaded', 249999999.99999997), ('ts-food-service', 'http.client.request.duration', 197.61341692653238)]

### case_1484  [HTTPFault/HTTPResponseDelay]  spl=2 n_svc=3
- gt: ['ts-travel-plan-service', 'ts-train-service']
- pred: ['ts-route-plan-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['travelplanservice', 'uidashboard'] missed=[] hallucinated=['routeplanservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-route-plan-service', 1815), ('stage_2_refine2', 'ts-route-plan-service', 2764)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-delivery-service', 1), ('ts-travel-plan-service', 1)]
- log err_delta top-: [('ts-food-service', -291), ('ts-order-service', -73), ('ts-preserve-service', -73)]
- gt log_err_rows: [('ts-travel-plan-service', 0, 1, 1)]
- gt metric anomalies (4/60 total): [('ts-train-service', 'jvm.class.loaded', 499999999.99999994), ('ts-travel-plan-service', 'http.server.request.duration', 113.04452053728359), ('ts-travel-plan-service', 'jvm.system.cpu.utilization', 19.361349064856466)]

### case_1880  [HTTPFault/HTTPResponseReplaceBody]  spl=2 n_svc=4
- gt: ['ts-food-service', 'ts-travel-service']
- pred: ['ts-route-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['foodservice', 'uidashboard'] missed=['preserveservice'] hallucinated=['routeservice']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-route-service', 1753)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-ui-dashboard', 78), ('ts-food-service', 1158)]
- log err_delta top-: [('ts-order-service', -72), ('ts-preserve-service', -72)]
- gt log_err_rows: [('ts-food-service', 254, 1412, 1158)]
- gt metric anomalies (31/60 total): [('ts-food-service', 'jvm.cpu.time', 153.55605632819197), ('ts-food-service', 'jvm.cpu.recent_utilization', 149.79318858273365), ('ts-food-service', 'k8s.pod.filesystem.usage', 145.89730422380754)]

### case_2231  [HTTPFault/HTTPRequestDelay]  spl=2 n_svc=7
- gt: ['ts-travel-service', 'ts-route-service']
- pred: ['ts-route-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['foodservice', 'preserveservice', 'routeplanservice', 'travelplanservice', 'travelservice', 'uidashboard'] missed=[] hallucinated=['basicservice', 'deliveryservice', 'notificationservice', 'seatservice']
- terminators (2/3 one_truncated): [('stage_0_main', None, 2772), ('stage_1_refine1', 'ts-route-plan-service', 3304)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-travel-service', 2)]
- log err_delta top-: [('ts-food-service', -283), ('ts-order-service', -92), ('ts-preserve-service', -92), ('ts-delivery-service', -3), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-travel-service', 0, 2, 2)]
- gt metric anomalies (3/60 total): [('ts-route-service', 'hubble_http_request_duration_p95_seconds', 361.7600114651519), ('ts-travel-service', 'db.client.connections.use_time', 216.2427511509664), ('ts-travel-service', 'jvm.system.cpu.utilization', 139.40093006228238)]

### case_2237  [HTTPFault/HTTPRequestReplacePath]  spl=2 n_svc=7
- gt: ['ts-travel-service', 'ts-route-service']
- pred: ['ts-route-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['foodservice', 'routeplanservice', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['preserveservice'] hallucinated=['routeservice']
- terminators (3/3 all_concluded): [('stage_0_main', None, 1897), ('stage_1_refine1', 'ts-route-plan-service', 3215), ('stage_1_refine1', 'ts-route-plan-service', 3828)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-travel-plan-service', 3), ('ts-route-plan-service', 53), ('ts-travel-service', 1509)]
- log err_delta top-: [('ts-food-service', -111), ('ts-order-service', -21), ('ts-preserve-service', -21), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-travel-service', 0, 1509, 1509)]
- gt metric anomalies (15/60 total): [('ts-route-service', 'processedLogs', 63.30400054005276), ('ts-travel-service', 'k8s.pod.filesystem.usage', 35.520545451641944), ('ts-travel-service', 'processedSpans', 18.516855255650185)]

### case_2283  [HTTPFault/HTTPRequestReplacePath]  spl=4 n_svc=5
- gt: ['ts-travel2-service', 'ts-basic-service']
- pred: ['ts-route-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travelplanservice', 'uidashboard'] missed=['travel2service'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-basic-service', 2028), ('stage_1_refine1', 'ts-route-plan-service', 2737)]  changed_across_stages=True
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-travel-plan-service', 21), ('ts-route-plan-service', 357), ('ts-travel2-service', 5722)]
- log err_delta top-: [('ts-food-service', -185), ('ts-order-service', -32), ('ts-preserve-service', -32)]
- gt log_err_rows: [('ts-travel2-service', 0, 5722, 5722)]
- gt metric anomalies (28/60 total): [('ts-travel2-service', 'jvm.class.count', 42250000000.0), ('ts-travel2-service', 'k8s.pod.filesystem.usage', 66.1720110924426), ('ts-travel2-service', 'processedSpans', 37.88524854106772)]

### case_2597  [HTTPFault/HTTPRequestDelay]  spl=2 n_svc=3
- gt: ['ts-preserve-service', 'ts-seat-service']
- pred: ['ts-order-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['preserveservice', 'uidashboard'] missed=[] hallucinated=['orderservice']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-order-service', 2125)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-ui-dashboard', 10)]
- log err_delta top-: [('ts-food-service', -72), ('ts-order-service', -20), ('ts-preserve-service', -14), ('ts-delivery-service', -1)]
- gt log_err_rows: [('ts-preserve-service', 69, 55, -14)]
- gt metric anomalies (16/60 total): [('ts-preserve-service', 'jvm.class.count', 29.877876430576723), ('ts-preserve-service', 'k8s.pod.filesystem.available', 9.31429227221774), ('ts-preserve-service', 'container.filesystem.available', 9.307486579650911)]

### case_2752  [HTTPFault/HTTPRequestAbort]  spl=2 n_svc=3
- gt: ['ts-travel-plan-service', 'ts-seat-service']
- pred: ['ts-route-plan-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['travelplanservice', 'uidashboard'] missed=[] hallucinated=['routeplanservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-route-plan-service', 1358), ('stage_1_refine1', 'ts-seat-service', 2650)]  changed_across_stages=True
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-travel-plan-service', 82), ('ts-ui-dashboard', 84)]
- log err_delta top-: [('ts-food-service', -47), ('ts-order-service', -6), ('ts-preserve-service', -6), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-travel-plan-service', 0, 82, 82)]
- gt metric anomalies (3/60 total): [('ts-travel-plan-service', 'queueSize', 1999999999.9999998), ('ts-travel-plan-service', 'jvm.class.count', 32.47595264193122), ('ts-travel-plan-service', 'k8s.pod.filesystem.usage', 24.417204535266293)]

### case_2761  [HTTPFault/HTTPResponseDelay]  spl=2 n_svc=3
- gt: ['ts-travel-plan-service', 'ts-train-service']
- pred: ['ts-route-plan-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['travelplanservice', 'uidashboard'] missed=[] hallucinated=['routeplanservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-route-plan-service', 1821), ('stage_2_refine2', None, 3118)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-travel-plan-service', 3), ('ts-ui-dashboard', 5)]
- log err_delta top-: [('ts-food-service', -285), ('ts-order-service', -83), ('ts-preserve-service', -83), ('ts-inside-payment-service', -1), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-travel-plan-service', 0, 3, 3)]
- gt metric anomalies (8/60 total): [('ts-travel-plan-service', 'http.server.request.duration', 79.132665382139), ('ts-travel-plan-service', 'jvm.system.cpu.utilization', 23.399573858967962), ('ts-train-service', 'db.client.connections.wait_time', 19.030501901840235)]

### case_2836  [HTTPFault/HTTPResponseReplaceBody]  spl=2 n_svc=5
- gt: ['ts-travel2-service', 'ts-basic-service']
- pred: ['ts-seat-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['routeplanservice', 'travel2service', 'travelplanservice', 'uidashboard'] missed=[] hallucinated=['seatservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-seat-service', 2697), ('stage_2_refine2', 'ts-seat-service', 3425)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-order-service', 5), ('ts-preserve-service', 5), ('ts-route-plan-service', 183), ('ts-travel-plan-service', 183), ('ts-travel2-service', 363)]
- log err_delta top-: [('ts-food-service', -286), ('ts-inside-payment-service', -1), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-travel2-service', 0, 363, 363)]
- gt metric anomalies (5/60 total): [('ts-basic-service', 'jvm.cpu.recent_utilization', 11.836265237333512), ('ts-travel2-service', 'k8s.pod.filesystem.usage', 11.833752886379804), ('ts-basic-service', 'jvm.cpu.time', 11.446311813432438)]

### case_3125  [HTTPFault/HTTPResponseDelay]  spl=2 n_svc=3
- gt: ['ts-preserve-service', 'ts-security-service']
- pred: ['ts-order-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['preserveservice', 'uidashboard'] missed=[] hallucinated=['orderservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-preserve-service', 2033), ('stage_1_refine1', 'ts-order-service', 2575)]  changed_across_stages=True
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-notification-service', 1), ('ts-ui-dashboard', 5)]
- log err_delta top-: [('ts-food-service', -292), ('ts-order-service', -63), ('ts-preserve-service', -60)]
- gt log_err_rows: [('ts-preserve-service', 114, 54, -60)]
- gt metric anomalies (8/60 total): [('ts-security-service', 'jvm.class.count', 1250000000.0), ('ts-security-service', 'jvm.class.loaded', 499999999.99999994), ('ts-security-service', 'jvm.gc.duration', 48999999.999999985)]

### case_3128  [HTTPFault/HTTPResponseDelay]  spl=2 n_svc=3
- gt: ['ts-preserve-service', 'ts-security-service']
- pred: ['ts-order-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['preserveservice', 'uidashboard'] missed=[] hallucinated=['orderservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-order-service', 1669), ('stage_1_refine1', None, 2437)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-ui-dashboard', 10)]
- log err_delta top-: [('ts-food-service', -214), ('ts-order-service', -56), ('ts-preserve-service', -50), ('ts-inside-payment-service', -1), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-preserve-service', 108, 58, -50)]
- gt metric anomalies (9/60 total): [('ts-security-service', 'jvm.gc.duration', 4000000.0000000033), ('ts-preserve-service', 'http.server.request.duration', 40.17647118158479), ('ts-preserve-service', 'jvm.class.count', 30.743901834361555)]


## JVMChaos (42 cases)

### case_99  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=5
- gt: ['ts-consign-price-service']  gt_fn: ['consignprice.service.ConsignPriceServiceImpl.getPriceByWeightAndRegion']
- pred: ['ts-consign-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['consignservice', 'uidashboard'] missed=['consignpriceservice', 'container|tsconsignpriceservice'] hallucinated=[]
- terminators (3/3 all_concluded): [('stage_0_main', None, 886), ('stage_1_refine1', 'ts-consign-service', 2507), ('stage_2_refine2', 'ts-consign-service', 3031)]  changed_across_stages=False
- log err_delta top+: [('ts-order-service', 22), ('ts-preserve-service', 22), ('ts-consign-service', 23), ('ts-food-service', 30)]
- log err_delta top-: [('ts-inside-payment-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (26/60 total): [('ts-consign-price-service', 'k8s.pod.filesystem.usage', 31658666666666.625), ('ts-consign-price-service', 'container.filesystem.usage', 16213333333333.312), ('ts-consign-price-service', 'jvm.class.loaded', 6462666666666.667)]

### case_156  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=13
- gt: ['ts-order-service']  gt_fn: ['order.controller.OrderController.saveOrderInfo']
- pred: ['ts-seat-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'seatservice', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['cancelservice', 'container|tsorderservice', 'insidepaymentservice', 'orderservice', 'preserveservice', 'securityservice', 'travel2service'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-order-service', 1718), ('stage_1_refine1', 'ts-seat-service', 3556)]  changed_across_stages=True
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-inside-payment-service', 1), ('ts-route-plan-service', 2), ('ts-travel-service', 2), ('ts-travel-plan-service', 3), ('ts-seat-service', 56)]
- log err_delta top-: [('ts-food-service', -79), ('ts-notification-service', -1), ('ts-preserve-service', -1), ('ts-order-service', -1)]
- gt log_err_rows: [('ts-order-service', 21, 20, -1)]
- gt metric anomalies (23/60 total): [('ts-order-service', 'container.filesystem.usage', 592438468085106.4), ('ts-order-service', 'jvm.class.loaded', 6581666666666.667), ('ts-order-service', 'jvm.class.count', 709.9178473598196)]

### case_247  [JVMChaos/JVMMemoryStress]  spl=3 n_svc=4
- gt: ['ts-route-service']  gt_fn: ['route.controller.RouteController.queryById']
- pred: ['ts-ui-dashboard']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeservice', 'uidashboard'] missed=['container|tsrouteservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-ui-dashboard', 1209), ('stage_1_refine1', 'ts-ui-dashboard', 2879)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-inside-payment-service', 1), ('ts-travel-service', 1), ('ts-basic-service', 11), ('ts-ui-dashboard', 15)]
- log err_delta top-: [('ts-food-service', -134), ('ts-order-service', -18), ('ts-preserve-service', -18), ('ts-delivery-service', -2), ('ts-notification-service', -2)]
- gt log_err_rows: []
- gt metric anomalies (13/60 total): [('ts-route-service', 'container.filesystem.usage', 450364952380952.4), ('ts-route-service', 'jvm.class.loaded', 8652.459809210328), ('ts-route-service', 'k8s.pod.memory.page_faults', 185.80207452865665)]

### case_281  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=5
- gt: ['ts-station-food-service']  gt_fn: ['food.controller.StationFoodController.home']
- pred: ['ts-rabbitmq']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['foodservice', 'uidashboard'] missed=['container|tsstationfoodservice', 'stationfoodservice'] hallucinated=['deliveryservice', 'notificationservice', 'rabbitmq']
- terminators (3/3 all_concluded): [('stage_0_main', 'ts-food-service', 8756), ('stage_2_refine2', 'ts-rabbitmq', 2609), ('stage_1_refine1', 'ts-rabbitmq', 3677)]  changed_across_stages=True
- log err_delta top+: [('ts-station-food-service', 9)]
- log err_delta top-: [('ts-food-service', -82), ('ts-order-service', -28), ('ts-preserve-service', -28), ('ts-inside-payment-service', -1), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-station-food-service', 0, 9, 9)]
- gt metric anomalies (24/60 total): [('ts-station-food-service', 'container.filesystem.usage', 70826666666666.62), ('ts-station-food-service', 'jvm.class.loaded', 6566666666666.667), ('ts-station-food-service', 'jvm.class.count', 18333333333.33212)]

### case_339  [JVMChaos/JVMMySQLLatency]  spl=3 n_svc=6
- gt: ['ts-travel-service', 'mysql']
- pred: ['ts-travel-plan-service', 'ts-preserve-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['preserveservice', 'routeplanservice', 'travelplanservice', 'travelservice', 'uidashboard'] missed=[] hallucinated=['basicservice', 'seatservice', 'travel2service']
- terminators (2/3 one_truncated): [('stage_0_main', None, 1620), ('stage_1_refine1', 'ts-travel-plan-service', 3934)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-ui-dashboard', 7), ('ts-preserve-service', 18), ('ts-order-service', 18), ('ts-consign-service', 120)]
- log err_delta top-: [('ts-food-service', -30)]
- gt log_err_rows: []
- gt metric anomalies (16/60 total): [('ts-travel-service', 'container.filesystem.usage', 2613248000000000.0), ('ts-travel-service', 'jvm.class.count', 191250000000.0), ('ts-travel-service', 'jvm.class.loaded', 48250000000.0)]

### case_603  [JVMChaos/JVMException]  spl=4 n_svc=6
- gt: ['ts-order-service']  gt_fn: ['order.entity.OrderInfo.setLoginId']
- pred: ['ts-food-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['uidashboard'] missed=['cancelservice', 'container|tsorderservice', 'insidepaymentservice', 'orderservice'] hallucinated=['deliveryservice', 'foodservice', 'notificationservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-order-service', 1696), ('stage_2_refine2', 'ts-order-service', 3163)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-order-service', 79), ('ts-preserve-service', 79), ('ts-food-service', 153)]
- log err_delta top-: [('ts-delivery-service', -1), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-order-service', 41, 120, 79)]
- gt metric anomalies (16/60 total): [('ts-order-service', 'jvm.class.count', 116.8237538931033), ('ts-order-service', 'jvm.class.loaded', 44.090815370097204), ('ts-order-service', 'k8s.pod.memory.page_faults', 9.623570732108647)]

### case_710  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=5
- gt: ['ts-route-plan-service']  gt_fn: ['plan.service.RoutePlanServiceImpl.getStationList']
- pred: ['ts-travel-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['travelplanservice', 'uidashboard'] missed=['container|tsrouteplanservice', 'routeplanservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-travel-plan-service', 1291)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-travel-plan-service', 23)]
- log err_delta top-: [('ts-food-service', -196), ('ts-order-service', -54), ('ts-preserve-service', -54), ('ts-notification-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (19/60 total): [('ts-route-plan-service', 'container.filesystem.usage', 16732595744680.846), ('ts-route-plan-service', 'jvm.class.loaded', 8524.28804945023), ('ts-route-plan-service', 'k8s.pod.memory.page_faults', 300.76632829646286)]

### case_784  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=5
- gt: ['ts-station-food-service']  gt_fn: ['food.service.StationFoodServiceImpl.listFoodStores']
- pred: ['ts-food-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['foodservice', 'stationfoodservice', 'uidashboard'] missed=['container|tsstationfoodservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', None, 884), ('stage_1_refine1', 'ts-food-service', 3721)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-inside-payment-service', 1), ('ts-station-food-service', 9)]
- log err_delta top-: [('ts-food-service', -125), ('ts-order-service', -10), ('ts-preserve-service', -10)]
- gt log_err_rows: [('ts-station-food-service', 0, 9, 9)]
- gt metric anomalies (16/60 total): [('ts-station-food-service', 'container.filesystem.usage', 134997333333333.36), ('ts-station-food-service', 'jvm.class.loaded', 6563666666666.667), ('ts-station-food-service', 'jvm.class.count', 14333333333.332119)]

### case_807  [JVMChaos/JVMMemoryStress]  spl=3 n_svc=4
- gt: ['ts-train-service']  gt_fn: ['train.entity.TrainType.TrainType']
- pred: ['ts-ui-dashboard']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['trainservice', 'uidashboard'] missed=['container|tstrainservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-ui-dashboard', 1767)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-inside-payment-service', 1), ('ts-basic-service', 3), ('ts-train-service', 6), ('ts-food-service', 14), ('ts-ui-dashboard', 20)]
- log err_delta top-: []
- gt log_err_rows: [('ts-train-service', 0, 6, 6)]
- gt metric anomalies (11/60 total): [('ts-train-service', 'container.filesystem.usage', 82268595744680.84), ('ts-train-service', 'k8s.pod.memory.major_page_faults', 914893617.0212765), ('ts-train-service', 'jvm.class.loaded', 11308.848397751795)]

### case_885  [JVMChaos/JVMLatency]  spl=3 n_svc=6
- gt: ['ts-travel2-service']  gt_fn: ['travel2.service.TravelServiceImpl.getServiceUrl']
- pred: ['ts-route-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travel2service', 'travelplanservice', 'uidashboard'] missed=['container|tstravel2service'] hallucinated=[]
- terminators (3/3 all_concluded): [('stage_0_main', 'ts-route-plan-service', 3983), ('stage_1_refine1', 'ts-route-plan-service', 2951), ('stage_1_refine1', 'ts-route-plan-service', 3341)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -264), ('ts-order-service', -80), ('ts-preserve-service', -80), ('ts-inside-payment-service', -1), ('ts-notification-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (6/60 total): [('ts-travel2-service', 'container.filesystem.usage', 2613248000000000.0), ('ts-travel2-service', 'jvm.class.count', 134749999999.99998), ('ts-travel2-service', 'db.client.connections.use_time', 91.25213890173374)]

### case_1114  [JVMChaos/JVMMemoryStress]  spl=5 n_svc=10
- gt: ['ts-config-service']  gt_fn: ['config.ConfigApplication.restTemplate']
- pred: ['ts-seat-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'seatservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['configservice', 'container|tsconfigservice', 'preserveservice'] hallucinated=['basicservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-seat-service', 3010), ('stage_2_refine2', 'ts-seat-service', 2614)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-seat-service', 39)]
- log err_delta top-: [('ts-food-service', -205), ('ts-order-service', -47), ('ts-preserve-service', -47), ('ts-inside-payment-service', -2), ('ts-notification-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (8/60 total): [('ts-config-service', 'container.filesystem.usage', 70826666666666.62), ('ts-config-service', 'jvm.class.loaded', 4579.459217224477), ('ts-config-service', 'k8s.pod.memory.page_faults', 165.63466610938656)]

### case_1195  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=9
- gt: ['ts-order-other-service']  gt_fn: ['other.service.OrderOtherServiceImpl.getOrderById']
- pred: ['ts-delivery-service', 'ts-food-service', 'ts-notification-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['orderotherservice', 'uidashboard'] missed=['container|tsorderotherservice', 'routeplanservice', 'seatservice', 'travel2service', 'travelplanservice', 'travelservice'] hallucinated=['deliveryservice', 'foodservice', 'notificationservice', 'orderservice', 'preserveservice', 'securityservice']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-rabbitmq', 3004)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-security-service', 12)]
- log err_delta top-: [('ts-food-service', -100), ('ts-order-service', -21), ('ts-preserve-service', -21), ('ts-inside-payment-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (23/60 total): [('ts-order-other-service', 'container.filesystem.usage', 68778666666666.625), ('ts-order-other-service', 'jvm.class.loaded', 6794.860183746731), ('ts-order-other-service', 'k8s.pod.memory.page_faults', 189.8957741743562)]

### case_1218  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=12
- gt: ['ts-order-service']  gt_fn: ['order.entity.OrderInfo.enableBoughtDateQuery']
- pred: ['ts-seat-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'seatservice', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['cancelservice', 'container|tsorderservice', 'orderservice', 'preserveservice', 'securityservice', 'travel2service'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_2_refine2', 'ts-seat-service', 1776)]  changed_across_stages=False
- truncated: ['stage_0_main', 'stage_1_refine1']
- log err_delta top+: [('ts-route-plan-service', 2), ('ts-travel-plan-service', 2), ('ts-travel-service', 3), ('ts-ui-dashboard', 24), ('ts-seat-service', 47)]
- log err_delta top-: [('ts-food-service', -97), ('ts-order-service', -9), ('ts-preserve-service', -9), ('ts-delivery-service', -1), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-order-service', 9, 0, -9)]
- gt metric anomalies (9/60 total): [('ts-order-service', 'container.filesystem.usage', 264191999999999.97), ('ts-order-service', 'k8s.pod.memory.major_page_faults', 791666666.6666666), ('ts-order-service', 'jvm.class.count', 3548.2777777765823)]

### case_1394  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=9
- gt: ['ts-seat-service']  gt_fn: ['seat.controller.SeatController.getLeftTicketOfInterval']
- pred: ['ts-travel-service', 'ts-travel2-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['container|tsseatservice', 'preserveservice', 'seatservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-travel2-service', 2353), ('stage_1_refine1', 'ts-travel-service', 2348)]  changed_across_stages=True
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-travel-plan-service', 1), ('ts-travel2-service', 13), ('ts-travel-service', 21)]
- log err_delta top-: [('ts-food-service', -146), ('ts-order-service', -44), ('ts-preserve-service', -44), ('ts-delivery-service', -1), ('ts-notification-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (4/60 total): [('ts-seat-service', 'container.filesystem.usage', 263935999999999.97), ('ts-seat-service', 'jvm.class.loaded', 2390.4731440792434), ('ts-seat-service', 'jvm.gc.duration', 204.99180402073898)]

### case_1459  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=10
- gt: ['ts-train-service']  gt_fn: ['train.init.InitData.run']
- pred: ['ts-basic-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['basicservice', 'routeplanservice', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['container|tstrainservice', 'preserveservice', 'trainservice', 'travel2service'] hallucinated=[]
- terminators (3/3 all_concluded): [('stage_0_main', None, 1242), ('stage_2_refine2', 'ts-basic-service', 2960), ('stage_2_refine2', 'ts-basic-service', 3109)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-route-plan-service', 3), ('ts-travel2-service', 3), ('ts-travel-plan-service', 4), ('ts-train-service', 6), ('ts-travel-service', 16)]
- log err_delta top-: [('ts-food-service', -90), ('ts-order-service', -5), ('ts-preserve-service', -5), ('ts-delivery-service', -1)]
- gt log_err_rows: [('ts-train-service', 0, 6, 6)]
- gt metric anomalies (13/60 total): [('ts-train-service', 'container.filesystem.usage', 117825361702127.61), ('ts-train-service', 'jvm.class.count', 2489333333333.332), ('ts-train-service', 'k8s.pod.memory.major_page_faults', 914893617.0212765)]

### case_1495  [JVMChaos/JVMMemoryStress]  spl=3 n_svc=4
- gt: ['ts-travel-plan-service']  gt_fn: ['travelplan.controller.TravelPlanController.home']
- pred: ['ts-seat-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['travelplanservice', 'uidashboard'] missed=['container|tstravelplanservice'] hallucinated=['routeplanservice', 'seatservice']
- terminators (1/3 two_truncated): [('stage_0_main', None, 686)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-notification-service', 1), ('ts-ui-dashboard', 18)]
- log err_delta top-: [('ts-food-service', -115), ('ts-order-service', -52), ('ts-preserve-service', -52)]
- gt log_err_rows: []
- gt metric anomalies (13/60 total): [('ts-travel-plan-service', 'container.filesystem.usage', 119466666666666.62), ('ts-travel-plan-service', 'jvm.class.loaded', 3832.0588221824923), ('ts-travel-plan-service', 'k8s.pod.memory.page_faults', 81.38664729474691)]

### case_1814  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=9
- gt: ['ts-basic-service']  gt_fn: ['fdse.microservice.controller.BasicController.queryForStationId']
- pred: ['ts-travel-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['preserveservice', 'travelservice', 'uidashboard'] missed=['basicservice', 'container|tsbasicservice', 'routeplanservice', 'travel2service', 'travelplanservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-basic-service', 1808), ('stage_1_refine1', 'ts-travel-service', 2366)]  changed_across_stages=True
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-travel-service', 26)]
- log err_delta top-: [('ts-food-service', -147), ('ts-order-service', -21), ('ts-preserve-service', -21), ('ts-inside-payment-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (5/60 total): [('ts-basic-service', 'container.filesystem.usage', 82268595744680.84), ('ts-basic-service', 'jvm.class.loaded', 3850.9073411340346), ('ts-basic-service', 'jvm.cpu.time', 53.078651531117885)]

### case_1860  [JVMChaos/JVMMemoryStress]  spl=3 n_svc=4
- gt: ['ts-contacts-service']  gt_fn: ['contacts.controller.ContactsController.createNewContactsAdmin']
- pred: ['ts-ui-dashboard']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['uidashboard'] missed=['contactsservice', 'container|tscontactsservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', None, 527), ('stage_2_refine2', 'ts-ui-dashboard', 3416)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-ui-dashboard', 22)]
- log err_delta top-: [('ts-food-service', -137), ('ts-order-service', -13), ('ts-preserve-service', -13)]
- gt log_err_rows: []
- gt metric anomalies (16/60 total): [('ts-contacts-service', 'container.filesystem.usage', 141824000000000.0), ('ts-contacts-service', 'jvm.class.loaded', 6815.57542480546), ('ts-contacts-service', 'hubble_http_request_duration_p90_seconds', 931.7534853424974)]

### case_2130  [JVMChaos/JVMReturn]  spl=5 n_svc=10
- gt: ['ts-station-service']  gt_fn: ['fdse.microservice.StationApplication.main']
- pred: ['ts-route-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['basicservice', 'preserveservice', 'routeplanservice', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['container|tsstationservice', 'stationservice', 'travel2service'] hallucinated=['routeservice']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-route-service', 2161)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -204), ('ts-order-service', -20), ('ts-preserve-service', -20), ('ts-notification-service', -5), ('ts-inside-payment-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (5/60 total): [('ts-station-service', 'container.filesystem.usage', 2504362666666666.5), ('ts-station-service', 'hubble_http_request_duration_p90_seconds', 313.2544183212797), ('ts-station-service', 'jvm.class.count', 235.50000000014282)]

### case_2253  [JVMChaos/JVMMemoryStress]  spl=3 n_svc=6
- gt: ['ts-travel-service']  gt_fn: ['travel.service.MyCallable.MyCallable']
- pred: ['ts-route-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travelplanservice', 'uidashboard'] missed=['container|tstravelservice', 'travelservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-route-plan-service', 2261), ('stage_2_refine2', 'ts-route-plan-service', 3107)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-travel-service', 5), ('ts-route-plan-service', 9)]
- log err_delta top-: [('ts-food-service', -105), ('ts-order-service', -32), ('ts-preserve-service', -32)]
- gt log_err_rows: [('ts-travel-service', 0, 5, 5)]
- gt metric anomalies (22/60 total): [('ts-travel-service', 'container.filesystem.usage', 118871148936170.27), ('ts-travel-service', 'jvm.class.loaded', 6895.825224201036), ('ts-travel-service', 'k8s.pod.memory.page_faults', 77.86100761056544)]

### case_2390  [JVMChaos/JVMMemoryStress]  spl=3 n_svc=5
- gt: ['ts-user-service']  gt_fn: ['user.init.InitUser.run']
- pred: ['ts-ui-dashboard']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['cancelservice', 'uidashboard', 'userservice'] missed=['container|tsuserservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', None, 2547)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-ui-dashboard', 47)]
- log err_delta top-: [('ts-food-service', -86), ('ts-order-service', -13), ('ts-preserve-service', -13)]
- gt log_err_rows: []
- gt metric anomalies (30/60 total): [('ts-user-service', 'container.filesystem.usage', 207701333333333.34), ('ts-user-service', 'jvm.gc.duration', 1272336507.9365075), ('ts-user-service', 'jvm.class.loaded', 11154.118525608976)]

### case_2697  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=9
- gt: ['ts-seat-service']  gt_fn: ['seat.SeatApplication.restTemplate']
- pred: ['ts-travel-service', 'ts-travel2-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['container|tsseatservice', 'preserveservice', 'seatservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-travel2-service', 2393)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-travel-service', 45), ('ts-route-plan-service', 84), ('ts-travel-plan-service', 84), ('ts-travel2-service', 98), ('ts-ui-dashboard', 144)]
- log err_delta top-: [('ts-food-service', -222), ('ts-order-service', -37), ('ts-preserve-service', -36)]
- gt log_err_rows: []
- gt metric anomalies (6/60 total): [('ts-seat-service', 'container.filesystem.usage', 116736000000000.0), ('ts-seat-service', 'jvm.class.loaded', 2090.1859307545774), ('ts-seat-service', 'k8s.pod.memory.page_faults', 123.9252188387585)]

### case_2713  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=5
- gt: ['ts-security-service']  gt_fn: ['security.service.SecurityServiceImpl.deleteSecurityConfig']
- pred: ['ts-preserve-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['preserveservice', 'uidashboard'] missed=['container|tssecurityservice', 'securityservice'] hallucinated=[]
- terminators (3/3 all_concluded): [('stage_0_main', 'ts-order-service', 2429), ('stage_1_refine1', 'ts-preserve-service', 2965), ('stage_2_refine2', 'ts-preserve-service', 2937)]  changed_across_stages=True
- log err_delta top+: [('ts-preserve-service', 28), ('ts-ui-dashboard', 38)]
- log err_delta top-: [('ts-food-service', -50), ('ts-order-service', -11), ('ts-notification-service', -1), ('ts-consign-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (26/60 total): [('ts-security-service', 'container.filesystem.usage', 64682666666666.625), ('ts-security-service', 'jvm.class.loaded', 6526666666666.667), ('ts-security-service', 'jvm.class.count', 2971000000000.0)]

### case_2769  [JVMChaos/JVMMemoryStress]  spl=3 n_svc=4
- gt: ['ts-travel-plan-service']  gt_fn: ['travelplan.service.TravelPlanServiceImpl.getRoutePlanResultQuickest']
- pred: ['ts-route-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['travelplanservice', 'uidashboard'] missed=['container|tstravelplanservice'] hallucinated=['routeplanservice', 'routeservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-travel-plan-service', 1623), ('stage_2_refine2', None, 3058)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-delivery-service', 1), ('ts-notification-service', 1), ('ts-order-service', 1), ('ts-preserve-service', 1), ('ts-ui-dashboard', 113)]
- log err_delta top-: [('ts-food-service', -6), ('ts-consign-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (18/60 total): [('ts-travel-plan-service', 'container.filesystem.usage', 70826666666666.62), ('ts-travel-plan-service', 'jvm.class.loaded', 2073.464734424476), ('ts-travel-plan-service', 'k8s.pod.memory.page_faults', 216.7834324196488)]

### case_2988  [JVMChaos/JVMCPUStress]  spl=4 n_svc=9
- gt: ['ts-basic-service']  gt_fn: ['fdse.microservice.controller.BasicController.queryForStationId']
- pred: ['ts-order-service', 'ts-seat-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['preserveservice', 'routeplanservice', 'travel2service', 'travelplanservice', 'uidashboard'] missed=['basicservice', 'container|tsbasicservice', 'travelservice'] hallucinated=['orderservice', 'seatservice']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-order-service', 2477)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-consign-service', 1)]
- log err_delta top-: [('ts-food-service', -89), ('ts-order-service', -26), ('ts-preserve-service', -26), ('ts-inside-payment-service', -1), ('ts-notification-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (11/60 total): [('ts-basic-service', 'container.filesystem.usage', 2613248000000000.0), ('ts-basic-service', 'jvm.cpu.time', 141.45473441474567), ('ts-basic-service', 'jvm.cpu.recent_utilization', 136.7886659010223)]

### case_3053  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=11
- gt: ['ts-order-other-service']  gt_fn: ['other.service.OrderOtherServiceImpl.getServiceUrl']
- pred: ['ts-seat-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['orderotherservice', 'preserveservice', 'routeplanservice', 'seatservice', 'securityservice', 'travel2service', 'travelplanservice', 'uidashboard'] missed=['container|tsorderotherservice', 'travelservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-seat-service', 2322)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-delivery-service', 1), ('ts-inside-payment-service', 1), ('ts-notification-service', 1), ('ts-preserve-service', 13), ('ts-security-service', 25)]
- log err_delta top-: [('ts-food-service', -109), ('ts-order-service', -12), ('ts-consign-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (10/60 total): [('ts-order-other-service', 'container.filesystem.usage', 81222808510638.3), ('ts-order-other-service', 'jvm.class.loaded', 4626.363967043185), ('ts-order-other-service', 'k8s.pod.memory.page_faults', 177.03493146042828)]

### case_3556  [JVMChaos/JVMMemoryStress]  spl=3 n_svc=6
- gt: ['ts-travel2-service']  gt_fn: ['travel2.service.TravelServiceImpl.getTrainTypeByTripId']
- pred: ['ts-route-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travelplanservice', 'uidashboard'] missed=['container|tstravel2service', 'travel2service'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-travel2-service', 2330), ('stage_1_refine1', 'ts-route-plan-service', 2756)]  changed_across_stages=True
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-order-service', 4), ('ts-preserve-service', 4), ('ts-travel2-service', 5), ('ts-route-plan-service', 20), ('ts-travel-plan-service', 20)]
- log err_delta top-: [('ts-food-service', -22), ('ts-delivery-service', -1), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-travel2-service', 0, 5, 5)]
- gt metric anomalies (11/60 total): [('ts-travel2-service', 'container.filesystem.usage', 213514893617021.25), ('ts-travel2-service', 'k8s.deployment.available', 41666666.66666663), ('ts-travel2-service', 'jvm.class.loaded', 2060.1970806283102)]

### case_3600  [JVMChaos/JVMMemoryStress]  spl=5 n_svc=9
- gt: ['ts-station-service']  gt_fn: ['fdse.microservice.service.StationServiceImpl.exist']
- pred: ['ts-basic-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['basicservice', 'routeplanservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['container|tsstationservice', 'stationservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-station-service', 2549), ('stage_1_refine1', 'ts-station-service', 3382)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-preserve-service', 9), ('ts-order-service', 9), ('ts-station-service', 13), ('ts-travel2-service', 28), ('ts-travel-plan-service', 29)]
- log err_delta top-: [('ts-delivery-service', -1)]
- gt log_err_rows: [('ts-station-service', 0, 13, 13)]
- gt metric anomalies (17/60 total): [('ts-station-service', 'container.filesystem.usage', 73728000000000.0), ('ts-station-service', 'k8s.pod.memory.page_faults', 262.0676869981652), ('ts-station-service', 'container.cpu.time', 52.40111417456525)]

### case_3700  [JVMChaos/JVMMemoryStress]  spl=5 n_svc=9
- gt: ['ts-config-service']  gt_fn: ['config.controller.ConfigController.home']
- pred: ['ts-ticket-office-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['seatservice', 'travel2service', 'uidashboard'] missed=['configservice', 'container|tsconfigservice', 'routeplanservice', 'travelplanservice', 'travelservice'] hallucinated=['ticketofficeservice']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-ticket-office-service', 1696)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-delivery-service', 1), ('ts-inside-payment-service', 1), ('ts-order-service', 29), ('ts-preserve-service', 29), ('ts-seat-service', 40)]
- log err_delta top-: [('ts-food-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (11/60 total): [('ts-config-service', 'container.filesystem.usage', 70826666666666.62), ('ts-config-service', 'jvm.class.loaded', 11207.23475037442), ('ts-config-service', 'k8s.pod.memory.page_faults', 567.1633870109622)]

### case_3716  [JVMChaos/JVMMemoryStress]  spl=3 n_svc=5
- gt: ['ts-food-service']  gt_fn: ['foodsearch.controller.FoodController.home']
- pred: ['ts-rabbitmq']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['foodservice', 'preserveservice', 'uidashboard'] missed=['container|tsfoodservice'] hallucinated=['deliveryservice', 'notificationservice', 'rabbitmq']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-rabbitmq', 1786)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-ui-dashboard', 22)]
- log err_delta top-: [('ts-food-service', -78), ('ts-order-service', -7), ('ts-preserve-service', -6), ('ts-delivery-service', -1)]
- gt log_err_rows: [('ts-food-service', 334, 256, -78)]
- gt metric anomalies (21/60 total): [('ts-food-service', 'container.filesystem.usage', 294144000000000.0), ('ts-food-service', 'jvm.class.loaded', 13408.5), ('ts-food-service', 'k8s.pod.memory.page_faults', 334.69508229965425)]

### case_3760  [JVMChaos/JVMMemoryStress]  spl=5 n_svc=9
- gt: ['ts-price-service']  gt_fn: ['price.controller.PriceController.query']
- pred: ['ts-basic-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['basicservice', 'routeplanservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['container|tspriceservice', 'priceservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-basic-service', 2709), ('stage_2_refine2', 'ts-basic-service', 3175)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-travel-service', 6), ('ts-travel-plan-service', 8), ('ts-route-plan-service', 8), ('ts-travel2-service', 8), ('ts-basic-service', 211)]
- log err_delta top-: [('ts-food-service', -162), ('ts-order-service', -20), ('ts-preserve-service', -20), ('ts-delivery-service', -1), ('ts-notification-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (19/60 total): [('ts-price-service', 'container.filesystem.usage', 102487148936170.27), ('ts-price-service', 'jvm.class.count', 7062333333333.334), ('ts-price-service', 'jvm.class.loaded', 6526666666666.667)]

### case_3868  [JVMChaos/JVMLatency]  spl=5 n_svc=10
- gt: ['ts-config-service']  gt_fn: ['config.controller.ConfigController.deleteConfig']
- pred: ['ts-consign-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['uidashboard'] missed=['configservice', 'container|tsconfigservice', 'preserveservice', 'routeplanservice', 'seatservice', 'travel2service', 'travelplanservice', 'travelservice'] hallucinated=['consignservice']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-consign-service', 1737)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-delivery-service', 1), ('ts-ui-dashboard', 9), ('ts-consign-service', 168)]
- log err_delta top-: [('ts-food-service', -106), ('ts-order-service', -4), ('ts-preserve-service', -4)]
- gt log_err_rows: []
- gt metric anomalies (6/60 total): [('ts-config-service', 'container.filesystem.usage', 2558805333333333.5), ('ts-config-service', 'jvm.class.count', 129.24999999996083), ('ts-config-service', 'jvm.class.loaded', 28.14582562299426)]

### case_3920  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=5
- gt: ['ts-payment-service']  gt_fn: ['com.trainticket.service.PaymentServiceImpl.pay']
- pred: ['ts-inside-payment-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['insidepaymentservice', 'uidashboard'] missed=['container|tspaymentservice', 'paymentservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-inside-payment-service', 1536), ('stage_2_refine2', 'ts-inside-payment-service', 3152)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-payment-service', 1), ('ts-inside-payment-service', 19), ('ts-preserve-service', 54), ('ts-order-service', 54), ('ts-food-service', 72)]
- log err_delta top-: []
- gt log_err_rows: [('ts-payment-service', 0, 1, 1)]
- gt metric anomalies (17/60 total): [('ts-payment-service', 'hubble_http_request_duration_p90_seconds', 4.630555327993138e+16), ('ts-payment-service', 'container.filesystem.usage', 70826666666666.62), ('ts-payment-service', 'hubble_http_request_duration_p95_seconds', 761299999.9999995)]

### case_4032  [JVMChaos/JVMMemoryStress]  spl=3 n_svc=4
- gt: ['ts-auth-service']  gt_fn: ['auth.controller.AuthController.getHello']
- pred: ['ts-ui-dashboard']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['uidashboard'] missed=['authservice', 'container|tsauthservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-ui-dashboard', 1868), ('stage_2_refine2', 'ts-ui-dashboard', 2539)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-order-service', 12), ('ts-preserve-service', 12), ('ts-ui-dashboard', 31)]
- log err_delta top-: [('ts-food-service', -5), ('ts-delivery-service', -1), ('ts-inside-payment-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (12/60 total): [('ts-auth-service', 'container.filesystem.usage', 165582978723404.22), ('ts-auth-service', 'jvm.class.loaded', 6538666666666.667), ('ts-auth-service', 'jvm.class.count', 294333333333.3321)]

### case_4353  [JVMChaos/JVMMemoryStress]  spl=5 n_svc=10
- gt: ['ts-station-service']  gt_fn: ['fdse.microservice.service.StationServiceImpl.queryForIdBatch']
- pred: ['ts-basic-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['basicservice', 'preserveservice', 'travel2service', 'travelservice', 'uidashboard'] missed=['container|tsstationservice', 'routeplanservice', 'stationservice', 'travelplanservice'] hallucinated=['mysql']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-basic-service', 2644)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-travel-service', 1), ('ts-travel2-service', 1), ('ts-station-service', 13), ('ts-basic-service', 80)]
- log err_delta top-: [('ts-food-service', -162), ('ts-order-service', -34), ('ts-preserve-service', -33), ('ts-delivery-service', -1), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-station-service', 0, 13, 13)]
- gt metric anomalies (18/60 total): [('ts-station-service', 'container.filesystem.usage', 164537191489361.7), ('ts-station-service', 'jvm.class.count', 185666666666.66788), ('ts-station-service', 'k8s.pod.memory.major_page_faults', 851063829.787234)]

### case_4363  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=5
- gt: ['ts-train-food-service']  gt_fn: ['trainFood.TrainFoodApplication.restTemplate']
- pred: ['ts-rabbitmq']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['foodservice', 'uidashboard'] missed=['container|tstrainfoodservice', 'trainfoodservice'] hallucinated=['deliveryservice', 'notificationservice', 'rabbitmq']
- terminators (2/3 one_truncated): [('stage_0_main', None, 2621), ('stage_2_refine2', 'ts-rabbitmq', 3182)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-order-service', 4), ('ts-preserve-service', 4)]
- log err_delta top-: [('ts-delivery-service', -1), ('ts-notification-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (17/60 total): [('ts-train-food-service', 'container.filesystem.usage', 341275234042553.2), ('ts-train-food-service', 'jvm.class.loaded', 9715000000000.0), ('ts-train-food-service', 'jvm.class.count', 241000000000.0)]

### case_4519  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=5
- gt: ['ts-route-plan-service']  gt_fn: ['plan.service.RoutePlanServiceImpl.searchQuickestResult']
- pred: ['ts-travel-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travelplanservice', 'uidashboard'] missed=['container|tsrouteplanservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-travel-plan-service', 1819)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-food-service', 16), ('ts-order-service', 29), ('ts-preserve-service', 29), ('ts-travel-plan-service', 39), ('ts-ui-dashboard', 39)]
- log err_delta top-: [('ts-inside-payment-service', -2), ('ts-delivery-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (17/60 total): [('ts-route-plan-service', 'container.filesystem.usage', 179712000000000.0), ('ts-route-plan-service', 'jvm.class.loaded', 8524.86539971942), ('ts-route-plan-service', 'k8s.pod.memory.page_faults', 216.79508929591088)]

### case_4530  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=8
- gt: ['ts-seat-service']  gt_fn: ['seat.SeatApplication.main']
- pred: ['ts-travel2-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travel2service', 'travelplanservice', 'uidashboard'] missed=['container|tsseatservice', 'seatservice', 'travelservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-seat-service', 2136), ('stage_2_refine2', 'ts-travel2-service', 3959)]  changed_across_stages=True
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-delivery-service', 1), ('ts-notification-service', 1), ('ts-order-service', 17), ('ts-preserve-service', 17), ('ts-travel-service', 35)]
- log err_delta top-: []
- gt log_err_rows: []
- gt metric anomalies (12/60 total): [('ts-seat-service', 'container.filesystem.usage', 182613333333333.38), ('ts-seat-service', 'jvm.class.count', 18333333333.33394), ('ts-seat-service', 'jvm.class.loaded', 2471.1666666666665)]

### case_4617  [JVMChaos/JVMCPUStress]  spl=3 n_svc=4
- gt: ['ts-cancel-service']  gt_fn: ['cancel.service.CancelServiceImpl.cancelFromOrder']
- pred: ['mysql']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['cancelservice', 'uidashboard'] missed=['container|tscancelservice'] hallucinated=['basicservice', 'configservice', 'deliveryservice', 'foodservice', 'mysql', 'notificationservice', 'orderservice', 'preserveservice', 'routeplanservice', 'routeservice', 'seatservice', 'stationservice', 'travelplanservice', 'travelservice']
- terminators (1/3 two_truncated): [('stage_0_main', None, 3846)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -140), ('ts-order-service', -58), ('ts-preserve-service', -58), ('ts-delivery-service', -14), ('ts-notification-service', -8)]
- gt log_err_rows: []
- gt metric anomalies (3/60 total): [('ts-cancel-service', 'container.filesystem.usage', 2547916799999999.5), ('ts-cancel-service', 'jvm.class.count', 141250000000.0), ('ts-cancel-service', 'jvm.class.loaded', 35750000000.0)]

### case_4715  [JVMChaos/JVMMemoryStress]  spl=4 n_svc=5
- gt: ['ts-station-food-service']  gt_fn: ['food.controller.StationFoodController.getFoodStoresOfStation']
- pred: ['ts-rabbitmq']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['foodservice', 'uidashboard'] missed=['container|tsstationfoodservice', 'stationfoodservice'] hallucinated=['deliveryservice', 'notificationservice', 'rabbitmq']
- terminators (2/3 one_truncated): [('stage_0_main', None, 1425), ('stage_2_refine2', 'ts-rabbitmq', 3081)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-food-service', 2), ('ts-station-food-service', 9), ('ts-ui-dashboard', 39)]
- log err_delta top-: [('ts-preserve-service', -22), ('ts-order-service', -22), ('ts-notification-service', -1), ('ts-inside-payment-service', -1)]
- gt log_err_rows: [('ts-station-food-service', 0, 9, 9)]
- gt metric anomalies (19/60 total): [('ts-station-food-service', 'container.filesystem.usage', 196864000000000.0), ('ts-station-food-service', 'jvm.class.loaded', 6560333333333.333), ('ts-station-food-service', 'jvm.class.count', 31666666666.667877)]

### case_4789  [JVMChaos/JVMMemoryStress]  spl=5 n_svc=9
- gt: ['ts-station-service']  gt_fn: ['fdse.microservice.service.StationServiceImpl.delete']
- pred: ['ts-route-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['basicservice', 'routeplanservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['container|tsstationservice', 'stationservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', None, 1517)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-order-service', 1), ('ts-preserve-service', 1), ('ts-station-service', 13), ('ts-route-plan-service', 28), ('ts-travel-plan-service', 28)]
- log err_delta top-: [('ts-food-service', -41), ('ts-delivery-service', -1)]
- gt log_err_rows: [('ts-station-service', 0, 13, 13)]
- gt metric anomalies (15/60 total): [('ts-station-service', 'container.filesystem.usage', 275739234042553.22), ('ts-station-service', 'jvm.class.loaded', 6441333333333.333), ('ts-station-service', 'jvm.class.count', 282333333333.3321)]

### case_4832  [JVMChaos/JVMMemoryStress]  spl=1 n_svc=4
- gt: ['ts-consign-service']  gt_fn: ['consign.entity.GetPriceDomain.GetPriceDomain']
- pred: ['ts-ui-dashboard']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['uidashboard'] missed=['consignservice', 'span|http get http://tsuidashboard:8080/api/v1/consignservice/consigns/account/{id}', 'span|http put http://tsuidashboard:8080/api/v1/consignservice/consigns'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-consign-service', 1743), ('stage_1_refine1', 'ts-consign-service', 3081)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-order-service', 7), ('ts-preserve-service', 7)]
- log err_delta top-: [('ts-food-service', -124), ('ts-delivery-service', -1), ('ts-inside-payment-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (29/60 total): [('ts-consign-service', 'container.filesystem.usage', 179712000000000.0), ('ts-consign-service', 'jvm.class.count', 306333333333.3321), ('ts-consign-service', 'jvm.gc.duration', 487160714.28571427)]


## NetworkChaos (24 cases)

### case_130  [NetworkChaos/NetworkCorrupt]  spl=3 n_svc=10
- gt: ['ts-order-other-service', 'mysql']
- pred: ['ts-food-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['preserveservice'] missed=['orderotherservice', 'routeplanservice', 'seatservice', 'securityservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] hallucinated=['deliveryservice', 'foodservice', 'notificationservice', 'orderservice']
- terminators (3/3 all_concluded): [('stage_0_main', 'ts-food-service', 2264), ('stage_1_refine1', 'ts-food-service', 2846), ('stage_2_refine2', 'ts-food-service', 3447)]  changed_across_stages=False
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -205), ('ts-order-service', -78), ('ts-preserve-service', -78)]
- gt log_err_rows: []
- gt metric anomalies (8/60 total): [('ts-order-other-service', 'db.client.connections.wait_time', 4449.159755176518), ('ts-order-other-service', 'db.client.connections.use_time', 270.92231426056003), ('ts-order-other-service', 'hubble_http_request_duration_p95_seconds', 98.90015634836358)]

### case_283  [NetworkChaos/NetworkBandwidth]  spl=4 n_svc=9
- gt: ['ts-station-service', 'mysql']
- pred: ['ts-consign-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['uidashboard'] missed=['basicservice', 'preserveservice', 'routeplanservice', 'stationservice', 'travel2service', 'travelplanservice', 'travelservice'] hallucinated=['consignservice']
- terminators (3/3 all_concluded): [('stage_0_main', 'ts-consign-service', 1660), ('stage_2_refine2', 'ts-consign-service', 2276), ('stage_2_refine2', 'ts-consign-service', 3032)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-ui-dashboard', 20), ('ts-consign-service', 352)]
- log err_delta top-: [('ts-food-service', -107), ('ts-order-service', -3), ('ts-preserve-service', -3)]
- gt log_err_rows: []
- gt metric anomalies (4/60 total): [('ts-station-service', 'hubble_http_request_duration_p99_seconds', 358.1535991672066), ('ts-station-service', 'jvm.gc.duration', 103.50022971481944), ('ts-station-service', 'hubble_http_request_duration_p50_seconds', 11.904242668647763)]

### case_323  [NetworkChaos/TimeSkew]  spl=2 n_svc=3
- gt: ['ts-travel-plan-service']
- pred: ['ts-config-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['travelplanservice', 'uidashboard'] missed=[] hallucinated=['configservice', 'routeplanservice', 'seatservice', 'travel2service', 'travelservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-config-service', 2265), ('stage_1_refine1', 'ts-config-service', 5270)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -105)]
- gt log_err_rows: []
- gt metric anomalies (0/60 total): []

### case_601  [NetworkChaos/NetworkDelay]  spl=3 n_svc=12
- gt: ['ts-order-service', 'mysql']
- pred: ['ts-rabbitmq']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['insidepaymentservice', 'orderservice', 'preserveservice', 'routeplanservice', 'seatservice', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['cancelservice', 'securityservice', 'travel2service'] hallucinated=['deliveryservice', 'notificationservice', 'rabbitmq']
- terminators (3/3 all_concluded): [('stage_0_main', 'ts-rabbitmq', 2908), ('stage_2_refine2', 'ts-rabbitmq', 2406), ('stage_2_refine2', 'ts-rabbitmq', 4147)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-notification-service', 1), ('ts-delivery-service', 1)]
- log err_delta top-: [('ts-food-service', -194), ('ts-order-service', -48), ('ts-preserve-service', -48)]
- gt log_err_rows: [('ts-order-service', 49, 1, -48)]
- gt metric anomalies (5/60 total): [('ts-order-service', 'db.client.connections.wait_time', 3653.518221399923), ('ts-order-service', 'hubble_http_request_duration_p50_seconds', 540.2555140252425), ('ts-order-service', 'db.client.connections.use_time', 138.91477629811115)]

### case_1140  [NetworkChaos/NetworkBandwidth]  spl=3 n_svc=4
- gt: ['ts-food-service', 'ts-ui-dashboard']
- pred: ['rabbitmq']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['foodservice', 'preserveservice', 'uidashboard'] missed=[] hallucinated=['consignservice', 'deliveryservice', 'notificationservice', 'rabbitmq']
- terminators (2/3 one_truncated): [('stage_0_main', None, 3307), ('stage_2_refine2', 'ts-food-service', 4059)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-notification-service', 1), ('ts-ui-dashboard', 10), ('ts-consign-service', 176)]
- log err_delta top-: [('ts-food-service', -115), ('ts-order-service', -10), ('ts-preserve-service', -10)]
- gt log_err_rows: [('ts-food-service', 280, 165, -115), ('ts-ui-dashboard', 0, 10, 10)]
- gt metric anomalies (0/60 total): []

### case_1421  [NetworkChaos/DNSRandom]  spl=4 n_svc=9
- gt: ['ts-station-service', 'mysql']
- pred: ['ts-consign-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['uidashboard'] missed=['basicservice', 'preserveservice', 'routeplanservice', 'stationservice', 'travel2service', 'travelplanservice', 'travelservice'] hallucinated=['consignservice']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-consign-service', 1546)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-ui-dashboard', 22), ('ts-consign-service', 377)]
- log err_delta top-: [('ts-food-service', -171), ('ts-order-service', -16), ('ts-preserve-service', -16)]
- gt log_err_rows: []
- gt metric anomalies (4/60 total): [('ts-station-service', 'container.filesystem.usage', 4010666666666.686), ('ts-station-service', 'jvm.class.count', 1999999999.9999998), ('ts-station-service', 'hubble_http_request_duration_p99_seconds', 513.3178553117187)]

### case_1504  [NetworkChaos/NetworkDelay]  spl=2 n_svc=7
- gt: ['ts-travel-service', 'mysql']
- pred: ['rabbitmq']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['foodservice', 'routeplanservice', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['preserveservice'] hallucinated=['deliveryservice', 'notificationservice', 'rabbitmq']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-rabbitmq', 3132), ('stage_2_refine2', None, 3364)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-delivery-service', 1)]
- log err_delta top-: [('ts-food-service', -270), ('ts-order-service', -85), ('ts-preserve-service', -85), ('ts-inside-payment-service', -2), ('ts-notification-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (6/60 total): [('ts-travel-service', 'db.client.connections.wait_time', 5020.804800595149), ('ts-travel-service', 'hubble_http_request_duration_p50_seconds', 102.21760519414302), ('ts-travel-service', 'db.client.connections.use_time', 83.737046685734)]

### case_2584  [NetworkChaos/NetworkBandwidth]  spl=2 n_svc=3
- gt: ['ts-preserve-service', 'ts-travel-service']
- pred: ['ts-order-other-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['preserveservice', 'uidashboard'] missed=[] hallucinated=['orderotherservice', 'securityservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-security-service', 2214), ('stage_1_refine1', 'ts-order-other-service', 2670)]  changed_across_stages=True
- truncated: ['stage_2_refine2']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -253), ('ts-order-service', -106), ('ts-preserve-service', -106), ('ts-consign-service', -2), ('ts-ui-dashboard', -2)]
- gt log_err_rows: [('ts-preserve-service', 107, 1, -106)]
- gt metric anomalies (2/60 total): [('ts-travel-service', 'container.filesystem.available', 10.366326134513397), ('ts-travel-service', 'k8s.pod.filesystem.available', 10.3546191534449)]

### case_2678  [NetworkChaos/NetworkBandwidth]  spl=3 n_svc=8
- gt: ['ts-seat-service', 'ts-config-service']
- pred: ['ts-travel2-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travel2service', 'travelplanservice'] missed=['preserveservice', 'seatservice', 'travelservice', 'uidashboard'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-travel2-service', 1968), ('stage_2_refine2', 'ts-travel2-service', 3346)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-route-plan-service', 2), ('ts-travel-plan-service', 2), ('ts-travel2-service', 4)]
- log err_delta top-: [('ts-food-service', -258), ('ts-order-service', -73), ('ts-preserve-service', -73), ('ts-inside-payment-service', -2)]
- gt log_err_rows: []
- gt metric anomalies (0/60 total): []

### case_2700  [NetworkChaos/NetworkCorrupt]  spl=3 n_svc=4
- gt: ['ts-security-service', 'ts-preserve-service']
- pred: ['ts-order-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['preserveservice', 'uidashboard'] missed=['securityservice'] hallucinated=['orderservice']
- terminators (1/3 two_truncated): [('stage_0_main', None, 869)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -193), ('ts-order-service', -73), ('ts-preserve-service', -72)]
- gt log_err_rows: [('ts-preserve-service', 82, 10, -72)]
- gt metric anomalies (5/60 total): [('ts-security-service', 'jvm.gc.duration', 663000000.0), ('ts-preserve-service', 'http.server.request.duration', 191.95783874972102), ('ts-preserve-service', 'http.client.request.duration', 16.653127517375882)]

### case_2715  [NetworkChaos/NetworkBandwidth]  spl=4 n_svc=9
- gt: ['ts-station-service', 'ts-basic-service']
- pred: ['ts-travel-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['basicservice', 'preserveservice', 'stationservice', 'travel2service'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-travel-service', 2043), ('stage_2_refine2', 'ts-travel-service', 2221)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-route-plan-service', 2), ('ts-travel-plan-service', 2), ('ts-travel-service', 10)]
- log err_delta top-: [('ts-food-service', -236), ('ts-order-service', -103), ('ts-preserve-service', -103), ('ts-inside-payment-service', -2)]
- gt log_err_rows: []
- gt metric anomalies (0/60 total): []

### case_3008  [NetworkChaos/NetworkCorrupt]  spl=3 n_svc=4
- gt: ['ts-contacts-service', 'ts-preserve-service']
- pred: ['ts-order-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['preserveservice', 'uidashboard'] missed=['contactsservice'] hallucinated=['orderservice']
- terminators (3/3 all_concluded): [('stage_0_main', 'ts-order-service', 1949), ('stage_1_refine1', 'ts-preserve-service', 1706), ('stage_2_refine2', 'ts-order-service', 2688)]  changed_across_stages=True
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -197), ('ts-order-service', -79), ('ts-preserve-service', -79)]
- gt log_err_rows: [('ts-preserve-service', 104, 25, -79)]
- gt metric anomalies (7/60 total): [('ts-contacts-service', 'jvm.gc.duration', 576000000.0), ('ts-preserve-service', 'http.server.request.duration', 41.628648644964656), ('ts-preserve-service', 'http.client.request.duration', 17.08249942576095)]

### case_3059  [NetworkChaos/NetworkCorrupt]  spl=3 n_svc=10
- gt: ['ts-order-service', 'ts-ui-dashboard']
- pred: ['rabbitmq']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['orderservice', 'preserveservice', 'routeplanservice', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['seatservice', 'securityservice', 'travel2service'] hallucinated=['deliveryservice', 'foodservice', 'notificationservice', 'rabbitmq']
- terminators (2/3 one_truncated): [('stage_0_main', None, 2616), ('stage_2_refine2', None, 4010)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-order-service', 4), ('ts-preserve-service', 4), ('ts-ui-dashboard', 4)]
- log err_delta top-: [('ts-food-service', -65), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-order-service', 8, 12, 4), ('ts-ui-dashboard', 0, 4, 4)]
- gt metric anomalies (0/60 total): []

### case_3076  [NetworkChaos/NetworkPartition]  spl=3 n_svc=10
- gt: ['ts-order-service', 'ts-ui-dashboard']
- pred: ['ts-rabbitmq']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['orderservice', 'uidashboard'] missed=['cancelservice', 'insidepaymentservice', 'routeplanservice', 'seatservice', 'travel2service', 'travelplanservice', 'travelservice'] hallucinated=['deliveryservice', 'foodservice', 'notificationservice', 'preserveservice', 'rabbitmq']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-rabbitmq', 1816)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-ui-dashboard', 98)]
- log err_delta top-: [('ts-food-service', -84), ('ts-order-service', -2), ('ts-preserve-service', -2), ('ts-delivery-service', -1)]
- gt log_err_rows: [('ts-order-service', 5, 3, -2), ('ts-ui-dashboard', 0, 98, 98)]
- gt metric anomalies (1/60 total): [('ts-order-service', 'db.client.connections.use_time', 6.234445443218307)]

### case_3222  [NetworkChaos/NetworkLoss]  spl=3 n_svc=7
- gt: ['ts-seat-service', 'ts-order-other-service']
- pred: ['ts-travel2-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'seatservice', 'travel2service', 'travelplanservice', 'uidashboard'] missed=['travelservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-travel2-service', 4416)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-route-plan-service', 4), ('ts-travel-plan-service', 4), ('ts-seat-service', 6), ('ts-travel2-service', 12)]
- log err_delta top-: [('ts-food-service', -259), ('ts-order-service', -78), ('ts-preserve-service', -78)]
- gt log_err_rows: [('ts-seat-service', 0, 6, 6)]
- gt metric anomalies (5/60 total): [('ts-seat-service', 'http.client.request.duration', 3412.708538505329), ('ts-seat-service', 'http.server.request.duration', 1848.072526287994), ('ts-order-other-service', 'jvm.system.cpu.load_1m', 36.9269065064329)]

### case_3278  [NetworkChaos/NetworkBandwidth]  spl=2 n_svc=3
- gt: ['ts-travel-plan-service', 'ts-ui-dashboard']
- pred: ['ts-route-plan-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['travelplanservice', 'uidashboard'] missed=[] hallucinated=['routeplanservice']
- terminators (3/3 all_concluded): [('stage_0_main', 'ts-ui-dashboard', 1173), ('stage_1_refine1', 'ts-route-plan-service', 3141), ('stage_2_refine2', 'ts-route-plan-service', 3409)]  changed_across_stages=True
- log err_delta top+: [('ts-delivery-service', 1)]
- log err_delta top-: [('ts-food-service', -266), ('ts-order-service', -93), ('ts-preserve-service', -93), ('ts-inside-payment-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (4/60 total): [('ts-ui-dashboard', 'container.cpu.usage', 3.8679215519870223), ('ts-ui-dashboard', 'k8s.pod.cpu_limit_utilization', 3.5928883895737176), ('ts-ui-dashboard', 'k8s.pod.cpu.node.utilization', 3.5928883895737163)]

### case_3284  [NetworkChaos/NetworkDelay]  spl=2 n_svc=3
- gt: ['ts-travel-plan-service', 'ts-seat-service']
- pred: ['ts-route-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['travelplanservice', 'uidashboard'] missed=[] hallucinated=['routeplanservice', 'routeservice']
- terminators (3/3 all_concluded): [('stage_0_main', 'ts-route-service', 2850), ('stage_2_refine2', 'ts-route-service', 2051), ('stage_2_refine2', 'ts-route-service', 2151)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -207), ('ts-order-service', -74), ('ts-preserve-service', -74), ('ts-delivery-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (3/60 total): [('ts-travel-plan-service', 'jvm.class.count', 249999999.99999997), ('ts-travel-plan-service', 'jvm.class.loaded', 249999999.99999997), ('ts-travel-plan-service', 'http.server.request.duration', 17.725699495160303)]

### case_3465  [NetworkChaos/NetworkCorrupt]  spl=3 n_svc=8
- gt: ['ts-basic-service', 'ts-price-service']
- pred: ['ts-route-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['basicservice', 'routeplanservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['preserveservice'] hallucinated=['priceservice', 'routeservice', 'stationservice', 'trainservice']
- terminators (2/3 one_truncated): [('stage_1_refine1', 'ts-route-plan-service', 2213), ('stage_1_refine1', 'ts-route-plan-service', 3674)]  changed_across_stages=False
- truncated: ['stage_0_main', 'stage_2_refine2']
- log err_delta top+: [('ts-notification-service', 1)]
- log err_delta top-: [('ts-food-service', -124), ('ts-order-service', -12), ('ts-preserve-service', -12), ('ts-delivery-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (6/60 total): [('ts-basic-service', 'http.client.request.duration', 63.531619063682136), ('ts-basic-service', 'http.server.request.duration', 23.4793791434349), ('ts-basic-service', 'k8s.pod.filesystem.available', 11.15999832587197)]

### case_3622  [NetworkChaos/NetworkDelay]  spl=3 n_svc=12
- gt: ['mysql', 'ts-order-service']
- pred: ['ts-rabbitmq']  on_propagation_path=False  hallucination=True
- diagnostic: matched=[] missed=['cancelservice', 'insidepaymentservice', 'orderservice', 'preserveservice', 'routeplanservice', 'seatservice', 'securityservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] hallucinated=['deliveryservice', 'foodservice', 'notificationservice', 'rabbitmq']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-rabbitmq', 3387), ('stage_2_refine2', 'ts-rabbitmq', 3065)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -96), ('ts-order-service', -15), ('ts-preserve-service', -15), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-order-service', 17, 2, -15)]
- gt metric anomalies (5/60 total): [('ts-order-service', 'db.client.connections.wait_time', 1176.3392621501894), ('ts-order-service', 'db.client.connections.use_time', 478.58556486722557), ('ts-order-service', 'http.server.request.duration', 81.40749783104734)]

### case_3878  [NetworkChaos/TimeSkew]  spl=2 n_svc=3
- gt: ['ts-consign-service']
- pred: ['ts-ui-dashboard']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['uidashboard'] missed=['consignservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-ui-dashboard', 2440)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-inside-payment-service', 1)]
- log err_delta top-: [('ts-consign-service', -512), ('ts-food-service', -139), ('ts-preserve-service', -24), ('ts-order-service', -24), ('ts-delivery-service', -3)]
- gt log_err_rows: [('ts-consign-service', 512, 0, -512)]
- gt metric anomalies (0/60 total): []

### case_4229  [NetworkChaos/NetworkPartition]  spl=5 n_svc=7
- gt: ['ts-basic-service', 'ts-travel-service']
- pred: ['ts-route-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travel2service', 'travelplanservice', 'uidashboard'] missed=['basicservice', 'travelservice'] hallucinated=['seatservice']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-route-plan-service', 1808)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-inside-payment-service', 1), ('ts-payment-service', 1)]
- log err_delta top-: [('ts-food-service', -173), ('ts-order-service', -35), ('ts-preserve-service', -35), ('ts-notification-service', -22), ('ts-delivery-service', -16)]
- gt log_err_rows: []
- gt metric anomalies (4/60 total): [('ts-basic-service', 'k8s.pod.filesystem.capacity', 1.6777215999999998e+16), ('ts-basic-service', 'container.filesystem.capacity', 1.6777215999999998e+16), ('ts-travel-service', 'k8s.pod.filesystem.capacity', 1.641249391304016e+16)]

### case_4423  [NetworkChaos/NetworkBandwidth]  spl=3 n_svc=5
- gt: ['ts-basic-service', 'ts-preserve-service']
- pred: ['ts-ui-dashboard']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['uidashboard'] missed=['basicservice', 'preserveservice', 'travelservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-ui-dashboard', 1250)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -338), ('ts-order-service', -104), ('ts-preserve-service', -104)]
- gt log_err_rows: [('ts-preserve-service', 104, 0, -104)]
- gt metric anomalies (2/60 total): [('ts-preserve-service', 'processedSpans', 4.996553575612947), ('ts-preserve-service', 'container.filesystem.available', 4.841146778363312)]

### case_4510  [NetworkChaos/NetworkBandwidth]  spl=3 n_svc=4
- gt: ['ts-route-plan-service', 'ts-travel-service']
- pred: ['ts-travel-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['travelplanservice', 'uidashboard'] missed=['routeplanservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-travel-plan-service', 1754), ('stage_1_refine1', 'ts-travel-plan-service', 2431)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -163), ('ts-order-service', -95), ('ts-preserve-service', -95)]
- gt log_err_rows: []
- gt metric anomalies (2/60 total): [('ts-route-plan-service', 'jvm.class.loaded', 750000000.0), ('ts-route-plan-service', 'jvm.class.count', 750000000.0)]

### case_4841  [NetworkChaos/NetworkDelay]  spl=5 n_svc=14
- gt: ['ts-station-service', 'mysql']
- pred: ['ts-food-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['preserveservice'] missed=['basicservice', 'routeplanservice', 'span|http post http://tsuidashboard:8080/api/v1/preserveservice/preserve', 'span|http post http://tsuidashboard:8080/api/v1/travel2service/trips/left', 'span|http post http://tsuidashboard:8080/api/v1/travelplanservice/travelplan/cheapest', 'span|http post http://tsuidashboard:8080/api/v1/travelplanservice/travelplan/minstation', 'span|http post http://tsuidashboard:8080/api/v1/travelplanservice/travelplan/quickest', 'span|http post http://tsuidashboard:8080/api/v1/travelservice/trips/left', 'stationservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] hallucinated=['deliveryservice', 'foodservice', 'notificationservice', 'orderservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-rabbitmq', 1736), ('stage_1_refine1', 'ts-food-service', 2947)]  changed_across_stages=True
- truncated: ['stage_2_refine2']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -293), ('ts-order-service', -97), ('ts-preserve-service', -97), ('ts-inside-payment-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (7/60 total): [('ts-station-service', 'db.client.connections.wait_time', 91387.54001839629), ('ts-station-service', 'hubble_http_request_duration_p50_seconds', 29596.948487335365), ('ts-station-service', 'hubble_http_request_duration_p90_seconds', 11687.991947766881)]


## PodChaos (32 cases)

### case_341  [PodChaos/PodFailure]  spl=3 n_svc=7
- gt: ['ts-travel-service']
- pred: ['ts-route-plan-service', 'ts-food-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['foodservice', 'routeplanservice', 'travelplanservice', 'uidashboard'] missed=['container|tstravelservice', 'travelservice'] hallucinated=['routeservice', 'trainfoodservice']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-route-service', 3000)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-notification-service', 1), ('ts-travel-plan-service', 5), ('ts-ui-dashboard', 21), ('ts-route-plan-service', 86)]
- log err_delta top-: [('ts-food-service', -134), ('ts-order-service', -34), ('ts-preserve-service', -34)]
- gt log_err_rows: []
- gt metric anomalies (13/60 total): [('ts-travel-service', 'container.filesystem.usage', 417962666666666.7), ('ts-travel-service', 'container.memory.working_set', 158.11560267417502), ('ts-travel-service', 'container.memory.usage', 157.96570296304102)]

### case_741  [PodChaos/PodFailure]  spl=5 n_svc=9
- gt: ['ts-route-service']
- pred: ['ts-ui-dashboard']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeservice', 'uidashboard'] missed=['basicservice', 'container|tsrouteservice', 'routeplanservice', 'travel2service', 'travelplanservice', 'travelservice'] hallucinated=['deliveryservice', 'notificationservice']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-ui-dashboard', 1924)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -214), ('ts-order-service', -53), ('ts-preserve-service', -53)]
- gt log_err_rows: []
- gt metric anomalies (14/60 total): [('ts-route-service', 'container.filesystem.usage', 426837333333333.3), ('ts-route-service', 'k8s.pod.memory.rss', 93.07917534417354), ('ts-route-service', 'k8s.pod.memory.node.utilization', 92.79153435119832)]

### case_804  [PodChaos/PodFailure]  spl=4 n_svc=10
- gt: ['ts-train-service']
- pred: ['rabbitmq']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['basicservice', 'routeplanservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['container|tstrainservice', 'preserveservice', 'trainservice'] hallucinated=['deliveryservice', 'notificationservice', 'rabbitmq']
- terminators (2/3 one_truncated): [('stage_0_main', None, 2855), ('stage_2_refine2', 'ts-delivery-service', 2246)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-delivery-service', 1), ('ts-travel2-service', 5), ('ts-travel-service', 9), ('ts-route-plan-service', 12), ('ts-travel-plan-service', 13)]
- log err_delta top-: [('ts-food-service', -216), ('ts-order-service', -48), ('ts-preserve-service', -48), ('ts-notification-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (15/60 total): [('ts-train-service', 'container.filesystem.usage', 426855489361702.06), ('ts-train-service', 'container.memory.usage', 93.77937338324392), ('ts-train-service', 'container.memory.available', 93.73522531540442)]

### case_1143  [PodChaos/ContainerKill]  spl=3 n_svc=5
- gt: ['ts-food-service']
- pred: ['ts-rabbitmq']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['foodservice', 'uidashboard'] missed=['container|tsfoodservice', 'preserveservice'] hallucinated=['deliveryservice', 'notificationservice', 'rabbitmq']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-rabbitmq', 2229)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-ui-dashboard', 23)]
- log err_delta top-: [('ts-food-service', -202), ('ts-order-service', -27), ('ts-preserve-service', -27)]
- gt log_err_rows: [('ts-food-service', 341, 139, -202)]
- gt metric anomalies (8/60 total): [('ts-food-service', 'container.filesystem.usage', 38058666666666.69), ('ts-food-service', 'jvm.class.loaded', 7001.838516678055), ('ts-food-service', 'db.client.connections.use_time', 144.76805374254826)]

### case_1371  [PodChaos/ContainerKill]  spl=4 n_svc=9
- gt: ['ts-seat-service']
- pred: ['ts-travel2-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['preserveservice', 'routeplanservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['container|tsseatservice', 'seatservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-travel2-service', 2087)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-route-plan-service', 2), ('ts-travel-plan-service', 3), ('ts-travel-service', 33), ('ts-travel2-service', 55)]
- log err_delta top-: [('ts-food-service', -187), ('ts-order-service', -32), ('ts-preserve-service', -31)]
- gt log_err_rows: []
- gt metric anomalies (4/60 total): [('ts-seat-service', 'container.filesystem.usage', 54784000000000.0), ('ts-seat-service', 'jvm.class.loaded', 2068.983838155586), ('ts-seat-service', 'jvm.class.count', 447.5000000000271)]

### case_1562  [PodChaos/PodFailure]  spl=3 n_svc=6
- gt: ['ts-travel2-service']
- pred: ['ts-route-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travelplanservice', 'uidashboard'] missed=['container|tstravel2service', 'travel2service'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-route-plan-service', 2025), ('stage_2_refine2', 'ts-route-plan-service', 3261)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-travel-plan-service', 3), ('ts-ui-dashboard', 30), ('ts-route-plan-service', 52)]
- log err_delta top-: [('ts-food-service', -77), ('ts-order-service', -16), ('ts-preserve-service', -16), ('ts-notification-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (13/60 total): [('ts-travel2-service', 'container.filesystem.usage', 426837333333333.3), ('ts-travel2-service', 'container.memory.rss', 192.16578913086954), ('ts-travel2-service', 'container.memory.usage', 191.82300328948125)]

### case_1862  [PodChaos/ContainerKill]  spl=3 n_svc=5
- gt: ['ts-food-service']
- pred: ['ts-rabbitmq']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['foodservice', 'uidashboard'] missed=['container|tsfoodservice', 'preserveservice'] hallucinated=['deliveryservice', 'notificationservice', 'rabbitmq']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-rabbitmq', 2479)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-ui-dashboard', 20)]
- log err_delta top-: [('ts-food-service', -172), ('ts-order-service', -21), ('ts-preserve-service', -21)]
- gt log_err_rows: [('ts-food-service', 328, 156, -172)]
- gt metric anomalies (5/60 total): [('ts-food-service', 'container.filesystem.usage', 44885333333333.31), ('ts-food-service', 'jvm.class.loaded', 7003.927448549524), ('ts-food-service', 'jvm.class.count', 69.2068156566277)]

### case_1886  [PodChaos/ContainerKill]  spl=3 n_svc=5
- gt: ['ts-inside-payment-service']
- pred: ['ts-ui-dashboard']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['cancelservice', 'insidepaymentservice', 'uidashboard'] missed=['container|tsinsidepaymentservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-inside-payment-service', 1957)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-cancel-service', 2), ('ts-inside-payment-service', 2), ('ts-ui-dashboard', 82)]
- log err_delta top-: [('ts-food-service', -106), ('ts-order-service', -19), ('ts-preserve-service', -19), ('ts-notification-service', -1)]
- gt log_err_rows: [('ts-inside-payment-service', 0, 2, 2)]
- gt metric anomalies (17/60 total): [('ts-inside-payment-service', 'container.filesystem.usage', 44885333333333.31), ('ts-inside-payment-service', 'jvm.gc.duration', 351517241.37931037), ('ts-inside-payment-service', 'jvm.class.loaded', 4655.591047332228)]

### case_1917  [PodChaos/ContainerKill]  spl=4 n_svc=11
- gt: ['ts-order-service']
- pred: ['ts-seat-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['preserveservice', 'seatservice', 'securityservice', 'travelservice', 'uidashboard'] missed=['container|tsorderservice', 'orderservice', 'routeplanservice', 'travel2service', 'travelplanservice'] hallucinated=[]
- terminators (3/3 all_concluded): [('stage_0_main', 'ts-seat-service', 2304), ('stage_2_refine2', 'ts-seat-service', 3337), ('stage_2_refine2', 'ts-seat-service', 4240)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-inside-payment-service', 1), ('ts-travel-service', 5), ('ts-security-service', 16), ('ts-seat-service', 108), ('ts-ui-dashboard', 123)]
- log err_delta top-: [('ts-food-service', -177), ('ts-order-service', -33), ('ts-preserve-service', -31)]
- gt log_err_rows: [('ts-order-service', 86, 53, -33)]
- gt metric anomalies (13/60 total): [('ts-order-service', 'container.filesystem.usage', 48640000000000.0), ('ts-order-service', 'jvm.class.loaded', 3999.404377529234), ('ts-order-service', 'jvm.class.count', 386.5000000000651)]

### case_1934  [PodChaos/PodFailure]  spl=4 n_svc=13
- gt: ['ts-order-service']
- pred: ['ts-seat-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'seatservice', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['cancelservice', 'container|tsorderservice', 'insidepaymentservice', 'orderservice', 'preserveservice', 'securityservice', 'travel2service'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-seat-service', 1780)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-route-plan-service', 1), ('ts-travel-plan-service', 1), ('ts-travel-service', 1), ('ts-seat-service', 29), ('ts-ui-dashboard', 45)]
- log err_delta top-: [('ts-food-service', -164), ('ts-order-service', -15), ('ts-preserve-service', -15)]
- gt log_err_rows: [('ts-order-service', 15, 0, -15)]
- gt metric anomalies (16/60 total): [('ts-order-service', 'container.filesystem.usage', 426855489361702.06), ('ts-order-service', 'hubble_http_request_duration_p95_seconds', 466.71876059965075), ('ts-order-service', 'hubble_http_request_duration_p50_seconds', 184.18393546147348)]

### case_2211  [PodChaos/ContainerKill]  spl=3 n_svc=7
- gt: ['ts-travel-service']
- pred: ['ts-route-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travelplanservice', 'uidashboard'] missed=['container|tstravelservice', 'preserveservice', 'travelservice'] hallucinated=[]
- terminators (3/3 all_concluded): [('stage_0_main', 'ts-route-plan-service', 2132), ('stage_2_refine2', 'ts-route-plan-service', 2833), ('stage_2_refine2', 'ts-route-plan-service', 2951)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-notification-service', 1), ('ts-inside-payment-service', 1), ('ts-travel-plan-service', 2), ('ts-travel-service', 5), ('ts-ui-dashboard', 15)]
- log err_delta top-: [('ts-food-service', -121), ('ts-order-service', -8), ('ts-preserve-service', -8)]
- gt log_err_rows: [('ts-travel-service', 0, 5, 5)]
- gt metric anomalies (7/60 total): [('ts-travel-service', 'container.filesystem.usage', 44885333333333.31), ('ts-travel-service', 'jvm.class.loaded', 6609.5), ('ts-travel-service', 'jvm.class.count', 69.16666666666788)]

### case_2258  [PodChaos/ContainerKill]  spl=3 n_svc=6
- gt: ['ts-travel2-service']
- pred: ['ts-route-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travelplanservice', 'uidashboard'] missed=['container|tstravel2service', 'travel2service'] hallucinated=[]
- terminators (3/3 all_concluded): [('stage_0_main', 'ts-route-plan-service', 1384), ('stage_2_refine2', 'ts-route-plan-service', 3179), ('stage_2_refine2', 'ts-route-plan-service', 2921)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-travel-plan-service', 4), ('ts-travel2-service', 5), ('ts-ui-dashboard', 10), ('ts-route-plan-service', 64)]
- log err_delta top-: [('ts-food-service', -170), ('ts-order-service', -44), ('ts-preserve-service', -44)]
- gt log_err_rows: [('ts-travel2-service', 0, 5, 5)]
- gt metric anomalies (4/60 total): [('ts-travel2-service', 'container.filesystem.usage', 28330666666666.684), ('ts-travel2-service', 'jvm.class.loaded', 2777.8056166905644), ('ts-travel2-service', 'jvm.class.count', 157.83333333343148)]

### case_2479  [PodChaos/ContainerKill]  spl=5 n_svc=10
- gt: ['ts-config-service']
- pred: ['ts-seat-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['preserveservice', 'routeplanservice', 'seatservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['configservice', 'container|tsconfigservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-seat-service', 3315)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-route-plan-service', 54), ('ts-travel-plan-service', 54), ('ts-travel-service', 56), ('ts-travel2-service', 60), ('ts-seat-service', 116)]
- log err_delta top-: [('ts-food-service', -192), ('ts-order-service', -35), ('ts-preserve-service', -34), ('ts-inside-payment-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (11/60 total): [('ts-config-service', 'container.filesystem.usage', 38058666666666.69), ('ts-config-service', 'jvm.class.loaded', 5115.4101896030525), ('ts-config-service', 'jvm.system.cpu.utilization', 136.64568439990762)]

### case_2585  [PodChaos/ContainerKill]  spl=3 n_svc=4
- gt: ['ts-preserve-service']
- pred: ['ts-route-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['preserveservice', 'uidashboard'] missed=['container|tspreserveservice'] hallucinated=['basicservice', 'routeservice']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-route-service', 2180)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-consign-service', 3), ('ts-ui-dashboard', 59)]
- log err_delta top-: [('ts-food-service', -155), ('ts-preserve-service', -5), ('ts-order-service', -4), ('ts-inside-payment-service', -2)]
- gt log_err_rows: [('ts-preserve-service', 105, 100, -5)]
- gt metric anomalies (6/60 total): [('ts-preserve-service', 'container.filesystem.usage', 46762666666666.68), ('ts-preserve-service', 'jvm.class.loaded', 8824.510189428835), ('ts-preserve-service', 'k8s.pod.memory.page_faults', 87.29902009188487)]

### case_3114  [PodChaos/PodKill]  spl=3 n_svc=4
- gt: ['ts-preserve-service']
- pred: ['ts-order-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['preserveservice', 'uidashboard'] missed=['container|tspreserveservice'] hallucinated=['orderservice']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-ui-dashboard', 922)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -29), ('ts-order-service', -20), ('ts-preserve-service', -20)]
- gt log_err_rows: [('ts-preserve-service', 80, 60, -20)]
- gt metric anomalies (13/60 total): [('ts-preserve-service', 'container.filesystem.usage', 28330666666666.684), ('ts-preserve-service', 'jvm.class.loaded', 8814.695234852612), ('ts-preserve-service', 'jvm.class.count', 174.07110616075136)]

### case_3266  [PodChaos/ContainerKill]  spl=4 n_svc=10
- gt: ['ts-train-service']
- pred: ['ts-route-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['basicservice', 'routeplanservice', 'trainservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['container|tstrainservice', 'preserveservice'] hallucinated=['routeservice']
- terminators (1/3 two_truncated): [('stage_0_main', None, 1651)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-train-service', 6), ('ts-travel2-service', 16), ('ts-travel-service', 51), ('ts-basic-service', 67), ('ts-route-plan-service', 67)]
- log err_delta top-: [('ts-food-service', -188), ('ts-order-service', -37), ('ts-preserve-service', -37), ('ts-inside-payment-service', -1)]
- gt log_err_rows: [('ts-train-service', 0, 6, 6)]
- gt metric anomalies (7/60 total): [('ts-train-service', 'container.filesystem.usage', 28330666666666.684), ('ts-train-service', 'jvm.class.loaded', 6521.833333333333), ('ts-train-service', 'container.cpu.time', 58.556652664010564)]

### case_3325  [PodChaos/ContainerKill]  spl=3 n_svc=7
- gt: ['ts-travel-service']
- pred: ['ts-route-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travelplanservice', 'uidashboard'] missed=['container|tstravelservice', 'preserveservice', 'travelservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', None, 906)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-order-service', 2), ('ts-preserve-service', 2), ('ts-travel-service', 5), ('ts-route-plan-service', 80), ('ts-travel-plan-service', 80)]
- log err_delta top-: [('ts-food-service', -59)]
- gt log_err_rows: [('ts-travel-service', 0, 5, 5)]
- gt metric anomalies (11/60 total): [('ts-travel-service', 'container.filesystem.usage', 28330666666666.684), ('ts-travel-service', 'k8s.deployment.available', 41666666.66666663), ('ts-travel-service', 'jvm.class.loaded', 6599.166666666667)]

### case_3673  [PodChaos/ContainerKill]  spl=2 n_svc=4
- gt: ['mysql']
- pred: ['ts-train-service', 'ts-auth-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['uidashboard'] missed=['span|http post http://tsuidashboard:8080/api/v1/travelplanservice/travelplan/minstation', 'span|http post http://tsuidashboard:8080/api/v1/travelplanservice/travelplan/quickest', 'travelplanservice'] hallucinated=['authservice', 'trainservice', 'verificationcodeservice']
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-auth-service', 1892), ('stage_1_refine1', 'ts-auth-service', 3014)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-ui-dashboard', 2), ('ts-train-service', 71), ('ts-auth-service', 2695)]
- log err_delta top-: [('ts-food-service', -310), ('ts-order-service', -115), ('ts-preserve-service', -115), ('ts-inside-payment-service', -3)]
- gt log_err_rows: []
- gt metric anomalies (10/60 total): [('mysql', 'k8s.pod.filesystem.usage', 23617361702127.656), ('mysql', 'container.filesystem.usage', 697191489361.6995), ('mysql', 'k8s.statefulset.ready_pods', 41666666.66666663)]

### case_3776  [PodChaos/PodFailure]  spl=4 n_svc=9
- gt: ['ts-seat-service']
- pred: ['ts-travel2-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travel2service', 'travelplanservice', 'travelservice', 'uidashboard'] missed=['container|tsseatservice', 'preserveservice', 'seatservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', None, 956)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-route-plan-service', 13), ('ts-travel-plan-service', 13), ('ts-travel-service', 93), ('ts-travel2-service', 180)]
- log err_delta top-: [('ts-food-service', -199), ('ts-order-service', -60), ('ts-preserve-service', -60), ('ts-inside-payment-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (13/60 total): [('ts-seat-service', 'container.filesystem.usage', 425984000000000.0), ('ts-seat-service', 'container.memory.rss', 142.03885682849292), ('ts-seat-service', 'container.memory.usage', 140.65884814612144)]

### case_3955  [PodChaos/PodFailure]  spl=4 n_svc=5
- gt: ['ts-station-food-service']
- pred: ['ts-food-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['foodservice', 'uidashboard'] missed=['container|tsstationfoodservice', 'stationfoodservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-food-service', 1782)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -70), ('ts-order-service', -44), ('ts-preserve-service', -44), ('ts-delivery-service', -1), ('ts-inside-payment-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (18/60 total): [('ts-station-food-service', 'container.filesystem.usage', 426837333333333.3), ('ts-station-food-service', 'container.memory.usage', 427.30780330738077), ('ts-station-food-service', 'container.memory.working_set', 427.09802548793965)]

### case_3966  [PodChaos/ContainerKill]  spl=4 n_svc=5
- gt: ['ts-train-food-service']
- pred: ['ts-food-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['foodservice', 'uidashboard'] missed=['container|tstrainfoodservice', 'trainfoodservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-food-service', 1503), ('stage_2_refine2', 'ts-food-service', 2909)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: []
- log err_delta top-: [('ts-food-service', -63), ('ts-order-service', -3), ('ts-preserve-service', -3)]
- gt log_err_rows: []
- gt metric anomalies (27/60 total): [('ts-train-food-service', 'container.filesystem.usage', 51029333333333.31), ('ts-train-food-service', 'jvm.gc.duration', 3379166666.666667), ('ts-train-food-service', 'db.client.connections.use_time', 847.8182492571648)]

### case_4054  [PodChaos/ContainerKill]  spl=4 n_svc=5
- gt: ['ts-consign-price-service']
- pred: ['ts-consign-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['consignservice', 'uidashboard'] missed=['consignpriceservice', 'container|tsconsignpriceservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-consign-service', 13160), ('stage_1_refine1', 'ts-consign-service', 2609)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-consign-service', 18)]
- log err_delta top-: [('ts-food-service', -114), ('ts-order-service', -37), ('ts-preserve-service', -37), ('ts-inside-payment-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (25/60 total): [('ts-consign-price-service', 'container.filesystem.usage', 44885333333333.31), ('ts-consign-price-service', 'jvm.class.loaded', 6480333333333.333), ('ts-consign-price-service', 'jvm.class.count', 118000000000.0)]

### case_4073  [PodChaos/ContainerKill]  spl=3 n_svc=4
- gt: ['ts-inside-payment-service']
- pred: ['mysql']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['insidepaymentservice', 'uidashboard'] missed=['container|tsinsidepaymentservice'] hallucinated=['mysql']
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-ui-dashboard', 1647)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-ui-dashboard', 110)]
- log err_delta top-: [('ts-food-service', -197), ('ts-order-service', -29), ('ts-preserve-service', -29)]
- gt log_err_rows: []
- gt metric anomalies (6/60 total): [('ts-inside-payment-service', 'container.filesystem.usage', 35157333333333.312), ('ts-inside-payment-service', 'jvm.gc.duration', 99655172.41379312), ('ts-inside-payment-service', 'jvm.class.loaded', 5698.158481767012)]

### case_4081  [PodChaos/ContainerKill]  spl=4 n_svc=11
- gt: ['ts-order-other-service']
- pred: ['ts-seat-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'seatservice', 'travel2service', 'travelplanservice', 'uidashboard'] missed=['container|tsorderotherservice', 'orderotherservice', 'preserveservice', 'securityservice', 'travelservice'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-seat-service', 3396)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-route-plan-service', 1), ('ts-travel-plan-service', 1), ('ts-travel2-service', 2), ('ts-ui-dashboard', 10), ('ts-seat-service', 32)]
- log err_delta top-: [('ts-food-service', -28), ('ts-order-service', -4), ('ts-preserve-service', -4)]
- gt log_err_rows: []
- gt metric anomalies (18/60 total): [('ts-order-other-service', 'container.filesystem.usage', 57685333333333.31), ('ts-order-other-service', 'jvm.class.loaded', 12985.5), ('ts-order-other-service', 'jvm.class.count', 1921.1666666666642)]

### case_4257  [PodChaos/PodFailure]  spl=4 n_svc=5
- gt: ['ts-consign-price-service']
- pred: ['ts-consign-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['consignservice', 'uidashboard'] missed=['consignpriceservice', 'container|tsconsignpriceservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-consign-price-service', 1885), ('stage_2_refine2', 'ts-consign-service', 3362)]  changed_across_stages=True
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-consign-service', 45)]
- log err_delta top-: [('ts-food-service', -95), ('ts-order-service', -9), ('ts-preserve-service', -9), ('ts-notification-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (17/60 total): [('ts-consign-price-service', 'container.filesystem.usage', 425984000000000.0), ('ts-consign-price-service', 'hubble_http_request_duration_p95_seconds', 174964285.7142857), ('ts-consign-price-service', 'container.memory.usage', 1687.3589630499519)]

### case_4258  [PodChaos/ContainerKill]  spl=3 n_svc=5
- gt: ['ts-contacts-service']
- pred: ['ts-ui-dashboard']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['uidashboard'] missed=['contactsservice', 'container|tscontactsservice', 'preserveservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-ui-dashboard', 1912), ('stage_1_refine1', None, 2401)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-ui-dashboard', 20)]
- log err_delta top-: [('ts-food-service', -50), ('ts-order-service', -1), ('ts-preserve-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (23/60 total): [('ts-contacts-service', 'container.filesystem.usage', 48981333333333.31), ('ts-contacts-service', 'jvm.class.loaded', 6470333333333.333), ('ts-contacts-service', 'jvm.class.count', 2579000000000.0)]

### case_4309  [PodChaos/ContainerKill]  spl=4 n_svc=5
- gt: ['ts-payment-service']
- pred: ['ts-inside-payment-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['insidepaymentservice', 'uidashboard'] missed=['container|tspaymentservice', 'paymentservice'] hallucinated=[]
- terminators (3/3 all_concluded): [('stage_0_main', 'ts-inside-payment-service', 1930), ('stage_2_refine2', 'ts-inside-payment-service', 2542), ('stage_2_refine2', 'ts-inside-payment-service', 3297)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-payment-service', 1), ('ts-notification-service', 1), ('ts-inside-payment-service', 17)]
- log err_delta top-: [('ts-food-service', -157), ('ts-order-service', -16), ('ts-preserve-service', -16)]
- gt log_err_rows: [('ts-payment-service', 0, 1, 1)]
- gt metric anomalies (14/60 total): [('ts-payment-service', 'hubble_http_request_duration_p90_seconds', 6.041743472129994e+17), ('ts-payment-service', 'container.filesystem.usage', 44885333333333.31), ('ts-payment-service', 'jvm.class.count', 105000000000.0)]

### case_4310  [PodChaos/PodFailure]  spl=4 n_svc=5
- gt: ['ts-payment-service']
- pred: ['ts-inside-payment-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['insidepaymentservice', 'uidashboard'] missed=['container|tspaymentservice', 'paymentservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', None, 876), ('stage_1_refine1', None, 2312)]  changed_across_stages=False
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-inside-payment-service', 503)]
- log err_delta top-: [('ts-food-service', -314), ('ts-order-service', -74), ('ts-preserve-service', -74)]
- gt log_err_rows: []
- gt metric anomalies (17/60 total): [('ts-payment-service', 'hubble_http_request_duration_p90_seconds', 8.019689809146498e+16), ('ts-payment-service', 'container.filesystem.usage', 426837333333333.3), ('ts-payment-service', 'hubble_http_request_duration_p95_seconds', 210806645.4640747)]

### case_4375  [PodChaos/ContainerKill]  spl=3 n_svc=6
- gt: ['ts-travel2-service']
- pred: ['ts-route-plan-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['routeplanservice', 'travelplanservice', 'uidashboard'] missed=['container|tstravel2service', 'travel2service'] hallucinated=[]
- terminators (1/3 two_truncated): [('stage_0_main', 'ts-route-plan-service', 1424)]  changed_across_stages=False
- truncated: ['stage_1_refine1', 'stage_2_refine2']
- log err_delta top+: [('ts-travel-plan-service', 4), ('ts-travel2-service', 5), ('ts-order-service', 8), ('ts-preserve-service', 8), ('ts-ui-dashboard', 11)]
- log err_delta top-: [('ts-food-service', -21), ('ts-delivery-service', -1)]
- gt log_err_rows: [('ts-travel2-service', 0, 5, 5)]
- gt metric anomalies (17/60 total): [('ts-travel2-service', 'container.filesystem.usage', 38058666666666.69), ('ts-travel2-service', 'jvm.class.loaded', 3491.9123170327402), ('ts-travel2-service', 'jvm.class.count', 113.44932789565829)]

### case_4463  [PodChaos/ContainerKill]  spl=3 n_svc=4
- gt: ['ts-config-service']
- pred: ['ts-food-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['foodservice', 'uidashboard'] missed=['container|tsfoodservice'] hallucinated=[]
- terminators (3/3 all_concluded): [('stage_0_main', 'ts-food-service', 1368), ('stage_2_refine2', 'ts-food-service', 2998), ('stage_2_refine2', 'ts-food-service', 4125)]  changed_across_stages=False
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-ui-dashboard', 224)]
- log err_delta top-: [('ts-food-service', -72), ('ts-order-service', -7), ('ts-preserve-service', -7)]
- gt log_err_rows: []
- gt metric anomalies (0/60 total): []

### case_4740  [PodChaos/ContainerKill]  spl=3 n_svc=4
- gt: ['ts-travel-plan-service']
- pred: ['ts-travel-service']  on_propagation_path=False  hallucination=True
- diagnostic: matched=['travelplanservice', 'uidashboard'] missed=['container|tstravelplanservice'] hallucinated=['basicservice', 'routeplanservice', 'travelservice']
- terminators (3/3 all_concluded): [('stage_0_main', None, 1052), ('stage_2_refine2', 'ts-basic-service', 3085), ('stage_2_refine2', 'ts-travel-service', 3492)]  changed_across_stages=True
- truncated: ['stage_1_refine1']
- log err_delta top+: [('ts-food-service', 4), ('ts-order-service', 6), ('ts-preserve-service', 6), ('ts-ui-dashboard', 38)]
- log err_delta top-: [('ts-notification-service', -1)]
- gt log_err_rows: []
- gt metric anomalies (11/60 total): [('ts-travel-plan-service', 'container.filesystem.usage', 36181333333333.31), ('ts-travel-plan-service', 'jvm.gc.duration', 366906249.99999994), ('ts-travel-plan-service', 'jvm.class.loaded', 5108.744008159842)]

### case_4801  [PodChaos/ContainerKill]  spl=4 n_svc=5
- gt: ['ts-security-service']
- pred: ['ts-preserve-service']  on_propagation_path=True  hallucination=True
- diagnostic: matched=['preserveservice', 'uidashboard'] missed=['container|tssecurityservice', 'securityservice'] hallucinated=[]
- terminators (2/3 one_truncated): [('stage_0_main', 'ts-order-service', 2083), ('stage_1_refine1', 'ts-preserve-service', 3144)]  changed_across_stages=True
- truncated: ['stage_2_refine2']
- log err_delta top+: [('ts-order-service', 1), ('ts-ui-dashboard', 29), ('ts-preserve-service', 30)]
- log err_delta top-: [('ts-food-service', -3)]
- gt log_err_rows: []
- gt metric anomalies (24/60 total): [('ts-security-service', 'container.filesystem.usage', 36181333333333.31), ('ts-security-service', 'jvm.class.count', 266999999999.99997), ('ts-security-service', 'queueSize', 1666666666.6666667)]

