# travel reconstruction

## 原始目录与剧情

`VibeLifeBench/eval_set/travel/galapagos_no_us_transit/`

林乔与许闻赴厄瓜多尔参加加拉帕戈斯工作坊。出发、返程、8月17日18时登记、证件、预算及许闻晕船限制共同约束航班、住宿、岛上交通和活动。美国转机低价航班因签证不合规，非美国联程、可取消酒店与接送机会先后出现及失效。财务报销与私人支出需分开，票据最后到齐。

## 固定 Task、条件与首次 Ready

条件字段的逐 Stage 三值标签以 JSON 中 `task_states` 为准。`open` 表示该具体行动尚未完成且时间窗口未过。

| Task | 行动 | 必要条件 | 首次 Ready |
|---|---|---|---|
| travel_t1 | 为林乔和许闻预留符合条件的非美国转机国际往返航班。 | goal, open, inventory, transit, ticket, timing, budget, reversible, authorized | s07 |
| travel_t2 | 为林乔和许闻预留Jardin Tranquilo可免费取消的工作坊住宿。 | goal, open, dates, inventory, location, budget, cancellation, authorized | s08 |
| travel_t3 | 确定两人从Baltra机场到Puerto Ayora工作坊地点的认证接送方案。 | goal, open, arrival, route, vendor, cost, deadline, authorized | s15 |
| travel_t4 | 为许闻制定晕船限制下的Santa Cruz岸上活动方案。 | goal, open, time, conditions, option, comfort | s14 |
| travel_t5 | 整理林乔本次会议费用的最终报销材料包。 | goal, open, policy, settlement, receipts, trip_finished | s21 |

## Initial Context 选择与来源

从原始初始环境及相关 Workspace、邮件、日历和数据库记录抽取历史事实。以下映射记录了每条模型可见文本的来源与实验改造；仅 JSON 的 `content` 会进入模型。

| Record | 时间 | 原始来源 | 转写或改造 |
|---|---|---|---|
| h001 | 2026-07-24T09:10:00+08:00 | `travel/galapagos_no_us_transit/event.yaml:stages.0` | 原始事实转写 |
| h002 | 2026-07-24T09:18:00+08:00 | `travel/galapagos_no_us_transit/event.yaml:stages.0; travel/galapagos_no_us_transit/workspace/USER.md` | 原始事实转写 |
| h003 | 2026-07-24T09:25:00+08:00 | `travel/galapagos_no_us_transit/workspace/DOCUMENTS.md` | 原始事实转写 |

## 原始 Event → 重构 Event 映射

原始通知若只提示收到邮件，则根据相应邮件、SQL 或工具状态写入实际内容。受控补充和时间拆分均在最右列明示。

| Stage / Event | 时间 | 原始来源 | 转写或改造 | 生命周期原因 |
|---|---|---|---|---|
| s01 / e001 | 2026-07-25T11:30:00+08:00 | `travel/galapagos_no_us_transit/mutations/S01_workshop_calendar_publish.sql; travel/galapagos_no_us_transit/envs/maps/galapagos_no_us_transit/init.sql` | 原始事实转写 | — |
| s02 / e002 | 2026-07-26T20:05:00+08:00 | `travel/galapagos_no_us_transit/event.yaml:stages.2` | 原始事实转写 | — |
| s03 / e003 | 2026-07-27T09:20:00+08:00 | `travel/galapagos_no_us_transit/mutations/workspace/S03_DOCUMENTS.md` | 隐去证件号码、生日与联系人，保留过境判断事实 | — |
| s04 / e004 | 2026-07-27T10:00:00+08:00 | `travel/galapagos_no_us_transit/mutations/S03_organizer_logistics_packet.sql` | 原始事实转写 | — |
| s05 / e005 | 2026-07-28T13:05:00+08:00 | `travel/galapagos_no_us_transit/mutations/S04_us_route_fare_drop.sql; travel/galapagos_no_us_transit/event.yaml:stages.4` | 原始事实转写 | — |
| s06 / e006 | 2026-07-30T10:15:00+08:00 | `travel/galapagos_no_us_transit/envs/flight_booking/galapagos_no_us_transit/init.sql; travel/galapagos_no_us_transit/mutations/S06_flight_inventory_reprice.sql; travel/galapagos_no_us_transit/event.yaml:stages.6` | 将分散航段及库存合并为同次查询记录；未声称已出票 | — |
| s07 / e007 | 2026-07-31T10:00:00+08:00 | `` | 受控补充：原始逐段库存没有单票行李/组合价确认；补入书面报价以检验可执行预留与总预算 | — |
| s08 / e008 | 2026-07-31T19:10:00+08:00 | `travel/galapagos_no_us_transit/envs/hotel_booking/galapagos_no_us_transit/init.sql; travel/galapagos_no_us_transit/mutations/S07_hotel_inventory_refresh.sql` | 预算合计是按原始房价和受控航班报价计算的估算；接送费用此时仅预留预算，不代表报价已知 | — |
| s09 / e009 | 2026-08-01T11:00:00+08:00 | `travel/galapagos_no_us_transit/mutations/S08_weather_ash_advisory.sql; travel/galapagos_no_us_transit/mutations/S08_flight_quito_delay_risk.sql` | 原始事实转写 | — |
| s10 / e010 | 2026-08-02T18:00:00+08:00 | `travel/galapagos_no_us_transit/mutations/S09_airline_weather_waiver_email.sql` | 原始事实转写 | — |
| s11 / e011 | 2026-08-03T10:00:00+08:00 | `travel/galapagos_no_us_transit/mutations/S10_hotel_inventory_shift.sql; travel/galapagos_no_us_transit/envs/hotel_booking/galapagos_no_us_transit/init.sql` | 原始事实转写 | 指定可取消酒店房型售罄 |
| s12 / e012 | 2026-08-04T21:00:00+08:00 | `travel/galapagos_no_us_transit/mutations/S11_reimbursement_scope_email.sql; travel/galapagos_no_us_transit/event.yaml:stages.11` | 原始事实转写 | — |
| s13 / e013 | 2026-08-06T13:00:00+08:00 | `travel/galapagos_no_us_transit/mutations/S13_sea_condition_warning.sql; travel/galapagos_no_us_transit/event.yaml:stages.13` | 原始海况与晕船限制；具体8月19日下午活动需求为受控新增用户消息 | — |
| s14 / e014 | 2026-08-07T11:05:00+08:00 | `travel/galapagos_no_us_transit/mutations/S14_entry_fee_notice_email.sql; travel/galapagos_no_us_transit/envs/maps/galapagos_no_us_transit/init.sql` | 原始费用和陆地地点；8月19日下午开放及适宜天气为受控补充查询结果 | — |
| s15 / e015 | 2026-08-08T16:45:00+08:00 | `travel/galapagos_no_us_transit/mutations/S15_baltra_pickup_schedule_change.sql; travel/galapagos_no_us_transit/mutations/S23_receipt_bundle_email.sql` | 原始mutation只说明最晚接机提前，后期收据证明35美元/座；班次、当时可用座位和预计到达为受控补充，不将未来收据提前当作原始邮件 | — |
| s16 / e016 | 2026-08-10T09:35:00+08:00 | `travel/galapagos_no_us_transit/mutations/S17_payment_verification_email.sql` | 原始事实转写 | — |
| s17 / e017 | 2026-08-14T17:35:00+08:00 | `travel/galapagos_no_us_transit/mutations/S19_departure_delay_risk.sql; travel/galapagos_no_us_transit/event.yaml:stages.19` | 原始事实转写 | 航班预留机会过期；后续旅途状态为外部发生事实 |
| s18 / e018 | 2026-08-17T15:00:00-06:00 | `travel/galapagos_no_us_transit/mutations/S20_intransit_status_update.sql; travel/galapagos_no_us_transit/event.yaml:stages.21` | 原始跨日状态合并；不假设本实验模型执行了任何预订 | 固定日期接送方案过期 |
| s19 / e019 | 2026-08-20T09:00:00-06:00 | `travel/galapagos_no_us_transit/mutations/S22_workshop_schedule_shift_email.sql; travel/galapagos_no_us_transit/mutations/S22_marine_warning_upgrade.sql` | 原始事实转写 | 指定岸上活动时间已过 |
| s20 / e020 | 2026-08-24T10:00:00+08:00 | `travel/galapagos_no_us_transit/mutations/S23_receipt_bundle_email.sql` | 原始邮件多封合并；每人机票分项凭证被原邮件提及但未提供内容，保留为待核对，不擅自补充金额 | — |
| s21 / e021 | 2026-08-25T13:30:00+08:00 | `travel/galapagos_no_us_transit/event.yaml:stages.24` | 返沪与归档请求来自原始用户消息；每人740美元为受控补充，用以完成原始总额1480美元的拆分 | — |

## Stage Ready Tasks

| Stage | Ready | Newly Ready | Invalidated |
|---|---|---|---|
| s00 | ∅ | ∅ | ∅ |
| s01 | ∅ | ∅ | ∅ |
| s02 | ∅ | ∅ | ∅ |
| s03 | ∅ | ∅ | ∅ |
| s04 | ∅ | ∅ | ∅ |
| s05 | ∅ | ∅ | ∅ |
| s06 | ∅ | ∅ | ∅ |
| s07 | travel_t1 | travel_t1 | ∅ |
| s08 | travel_t1, travel_t2 | travel_t2 | ∅ |
| s09 | travel_t1, travel_t2 | ∅ | ∅ |
| s10 | travel_t1, travel_t2 | ∅ | ∅ |
| s11 | travel_t1 | ∅ | travel_t2 |
| s12 | travel_t1 | ∅ | ∅ |
| s13 | travel_t1 | ∅ | ∅ |
| s14 | travel_t1, travel_t4 | travel_t4 | ∅ |
| s15 | travel_t1, travel_t3, travel_t4 | travel_t3 | ∅ |
| s16 | travel_t1, travel_t3, travel_t4 | ∅ | ∅ |
| s17 | travel_t3, travel_t4 | ∅ | travel_t1 |
| s18 | travel_t4 | ∅ | travel_t3 |
| s19 | ∅ | ∅ | travel_t4 |
| s20 | ∅ | ∅ | ∅ |
| s21 | travel_t5 | travel_t5 | ∅ |

## Task Readiness Matrix

| Task | s00 | s01 | s02 | s03 | s04 | s05 | s06 | s07 | s08 | s09 | s10 | s11 | s12 | s13 | s14 | s15 | s16 | s17 | s18 | s19 | s20 | s21 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| travel_t1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| travel_t2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| travel_t3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| travel_t4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| travel_t5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |

## 仍需人工核查

- 非美国联程3180美元报价、8月19日陆地活动开放与天气、接送座位和班次、每人740美元机票分项为受控补充。
- 原始后期票据显示 Jardin Tranquilo 入住，但此前库存归零；原始资料未清晰说明是谁完成了外部订房。此处仅把早期可预留窗口作为实验机会，后期票据视为外部状态，需人工核对。
- 原始工作坊时间线与跨时区飞行资料存在跨日表述；模拟时间均带时区，登记和接送兼容性需人工复查。

`task_registry`、问答标准答案和条件状态仅供评测器与人工标注使用，不进入模型 Context。
