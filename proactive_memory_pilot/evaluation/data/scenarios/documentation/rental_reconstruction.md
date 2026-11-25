# rental reconstruction

## 原始目录与剧情

`VibeLifeBench/eval_set/rental/cross_city_remote_viewing_rental/`

魏岚从武汉迁往苏州，8月17日入职，8月15日前需入住。她只在8月8日至9日能线下看房，要求一居室、月租不高于6000元、早高峰门到门不超过45分钟，并能正规居住登记。云栖苑、北岸花园与河滨小筑的信息陆续变化；HR会议、租金上涨、私人收款和东门绕行影响选择。用户允许内部筛选与材料整理，对外联系、付款、签约和提交个人资料均须另行确认。

## 固定 Task、条件与首次 Ready

条件字段的逐 Stage 三值标签以 JSON 中 `task_states` 为准。`open` 表示该具体行动尚未完成且时间窗口未过。

| Task | 行动 | 必要条件 | 首次 Ready |
|---|---|---|---|
| rental_t1 | 将云栖苑加入魏岚的内部看房计划。 | goal, open, listing, room, budget, commute, registration, slot, authorized | s04 |
| rental_t2 | 将北岸花园加入魏岚的内部看房计划。 | goal, open, listing, room, budget, commute, registration, slot, authorized | s11 |
| rental_t3 | 将河滨小筑加入魏岚的已核验内部看房计划。 | goal, open, listing, room, budget, commute, registration, slot, authorized, identity_risk | 无 |
| rental_t4 | 汇总云栖苑全部必要合同附件，形成最终签约前审核材料包。 | goal, open, owner, registration, deposit, repair, fee, authorized | s17 |

## Initial Context 选择与来源

从原始初始环境及相关 Workspace、邮件、日历和数据库记录抽取历史事实。以下映射记录了每条模型可见文本的来源与实验改造；仅 JSON 的 `content` 会进入模型。

| Record | 时间 | 原始来源 | 转写或改造 |
|---|---|---|---|
| h001 | 2026-07-06T10:20:00+08:00 | `rental/cross_city_remote_viewing_rental/envs/email/cross_city_remote_viewing_rental/init.sql:13` | 原始事实转写；影响 背景记录 |
| h002 | 2026-07-09T21:30:00+08:00 | `rental/cross_city_remote_viewing_rental/envs/email/cross_city_remote_viewing_rental/init.sql:14` | 原始事实转写；影响 背景记录 |
| h003 | 2026-07-10T08:30:00+08:00 | `rental/cross_city_remote_viewing_rental/envs/listing_platform/cross_city_remote_viewing_rental/init.sql:13-15` | 原始seed转为一次内部查询记录；影响 背景记录 |
| h004 | 2026-07-10T08:40:00+08:00 | `rental/cross_city_remote_viewing_rental/envs/calendar/cross_city_remote_viewing_rental/init.sql` | 抽取原始日历中与两处受控看房时段有关的已确认事项；未把tentative记录当成硬冲突；影响 rental_t1, rental_t2, rental_t3 |
| h005 | 2026-07-10T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/event.yaml:stages.0; rental/cross_city_remote_viewing_rental/workspace/AUTHORIZATION.md; rental/cross_city_remote_viewing_rental/workspace/RENTAL_REQUIREMENTS.md` | 入职后通勤口径和身份风险排除规则为受控澄清，符合原始安全偏好；影响 rental_t1, rental_t2, rental_t3, rental_t4 |

## 原始 Event → 重构 Event 映射

原始通知若只提示收到邮件，则根据相应邮件、SQL 或工具状态写入实际内容。受控补充和时间拆分均在最右列明示。

| Stage / Event | 时间 | 原始来源 | 转写或改造 | 生命周期原因 |
|---|---|---|---|---|
| s01 / e001 | 2026-07-17T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/mutations/stage04_review_updates.sql` | 原始事实转写；影响 无固定Task | — |
| s02 / e002 | 2026-07-20T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/mutations/stage06_listing_route.sql; rental/cross_city_remote_viewing_rental/mutations/stage06_maps_route.sql` | 原始北岸交通变化；云栖苑38分钟为受控补充实测；影响 rental_t1 | — |
| s03 / e003 | 2026-07-22T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/mutations/stage07_email_replies.sql` | 原始事实转写；影响 rental_t1, rental_t4 | — |
| s04 / e004 | 2026-07-23T11:00:00+08:00 | `` | 受控补充：原始资料只有登记线索和视频时段；加入房东书面回复与可用看房时段，使内部计划出现可核验机会；影响 rental_t1, rental_t4 | — |
| s05 / e005 | 2026-07-24T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/mutations/stage08_price_budget.sql; rental/cross_city_remote_viewing_rental/mutations/stage08_clear_route.sql` | 原始事实转写；影响 rental_t3 | — |
| s06 / e006 | 2026-07-25T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/event.yaml:stages.9` | 最终材料包完成标准为受控澄清；原始目标是签约前核验，初步清单可立即准备；影响 rental_t4 | — |
| s07 / e007 | 2026-07-27T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/mutations/stage10_calendar_conflict.sql` | 原始事实转写；影响 rental_t1, rental_t2, rental_t3 | — |
| s08 / e008 | 2026-07-28T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/mutations/stage11_risk_update.sql` | 原始事实转写；影响 rental_t3 | — |
| s09 / e009 | 2026-07-30T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/mutations/stage12_maps_gate.sql; rental/cross_city_remote_viewing_rental/mutations/stage12_review_gate.sql` | 河滨变化来自原始mutation；北岸39分钟为受控补充实测；影响 rental_t2 | — |
| s10 / e010 | 2026-08-01T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/mutations/stage13_contract_addendum.sql` | 原始事实转写；影响 rental_t4 | — |
| s11 / e011 | 2026-08-02T11:00:00+08:00 | `` | 受控补充：原始北岸月租8320元；因取消原含服务改报5900元解释大幅降价，并补书面登记及不冲突时段，须人工核实合理性；影响 rental_t2 | — |
| s12 / e012 | 2026-08-03T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/mutations/stage15_payment_pressure.sql; rental/cross_city_remote_viewing_rental/event.yaml:stages.15` | 原始事实转写；影响 rental_t3 | — |
| s13 / e013 | 2026-08-05T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/mutations/stage17_listing_addition.sql` | 原始事实转写；影响 无固定Task | — |
| s14 / e014 | 2026-08-06T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/mutations/stage18_maps_late_route.sql; rental/cross_city_remote_viewing_rental/mutations/stage18_notification_late_route.sql` | 51分钟仅为受控周末绕行测量；入职后通勤条件保留正常路线38分钟，避免短期施工错误否定长期目标；影响 rental_t1 | — |
| s15 / e015 | 2026-08-10T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/mutations/stage20_clear_route.sql; rental/cross_city_remote_viewing_rental/event.yaml:stages.19-20` | 原始事实转写；影响 rental_t1, rental_t2, rental_t3 | 唯一线下看房周末过期；不把绕行解除误写为新的38分钟测量 |
| s16 / e016 | 2026-08-11T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/mutations/stage21_final_clarification.sql` | 原始事实转写；影响 rental_t4 | — |
| s17 / e017 | 2026-08-12T11:00:00+08:00 | `` | 受控补充：原始最终邮件仍缺服务费金额和正式附件编号；只补足内部审核材料，不表示条款已被用户接受；影响 rental_t4 | — |
| s18 / e018 | 2026-08-14T09:00:00+08:00 | `rental/cross_city_remote_viewing_rental/event.yaml:stages.23` | 原始事实转写；影响 无固定Task | — |

## Stage Ready Tasks

| Stage | Ready | Newly Ready | Invalidated |
|---|---|---|---|
| s00 | ∅ | ∅ | ∅ |
| s01 | ∅ | ∅ | ∅ |
| s02 | ∅ | ∅ | ∅ |
| s03 | ∅ | ∅ | ∅ |
| s04 | rental_t1 | rental_t1 | ∅ |
| s05 | rental_t1 | ∅ | ∅ |
| s06 | rental_t1 | ∅ | ∅ |
| s07 | rental_t1 | ∅ | ∅ |
| s08 | rental_t1 | ∅ | ∅ |
| s09 | rental_t1 | ∅ | ∅ |
| s10 | rental_t1 | ∅ | ∅ |
| s11 | rental_t1, rental_t2 | rental_t2 | ∅ |
| s12 | rental_t1, rental_t2 | ∅ | ∅ |
| s13 | rental_t1, rental_t2 | ∅ | ∅ |
| s14 | rental_t1, rental_t2 | ∅ | ∅ |
| s15 | ∅ | ∅ | rental_t1, rental_t2 |
| s16 | ∅ | ∅ | ∅ |
| s17 | rental_t4 | rental_t4 | ∅ |
| s18 | rental_t4 | ∅ | ∅ |

## Task Readiness Matrix

| Task | s00 | s01 | s02 | s03 | s04 | s05 | s06 | s07 | s08 | s09 | s10 | s11 | s12 | s13 | s14 | s15 | s16 | s17 | s18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rental_t1 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| rental_t2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| rental_t3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| rental_t4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |

## 仍需人工核查

- 云栖苑和北岸花园的精确通勤、书面登记与可看房时段为受控补充；正式运行前应由研究人员核实补充事实的合理性。
- 原始北岸花园报价8320元，后续降至5900元是实验补充；若不接受该补充，应删除相应 Ready opportunity 并重算标签。

`task_registry`、问答标准答案和条件状态仅供评测器与人工标注使用，不进入模型 Context。
