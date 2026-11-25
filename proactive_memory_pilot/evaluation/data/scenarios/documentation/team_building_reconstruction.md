# team_building reconstruction

## 原始目录与剧情

`VibeLifeBench/eval_set/team_building/factory_visit_safety_day/`

魏然为44人供应链团队组织上海至嘉兴工厂参访，预算上限56000元。包车、餐饮和保险需公司发票，人员有听力、晕车、粉尘及语言需求。工厂资质、PPE、餐饮、司机文件、异常个人收款账户、HR审批及用户授权陆续更新。活动开始后前期规划机会结束，结算材料在活动后到齐。

## 固定 Task、条件与首次 Ready

条件字段的逐 Stage 三值标签以 JSON 中 `task_states` 为准。`open` 表示该具体行动尚未完成且时间窗口未过。

| Task | 行动 | 必要条件 | 首次 Ready |
|---|---|---|---|
| team_t1 | 为魏然的44人团队预留嘉兴智造工厂7月21日可取消的参访名额。 | goal, open, count, capacity, security, ppe, special_needs, cancellation, budget, authorized | s15 |
| team_t2 | 确定沪嘉商务包车两台49座大巴的7月21日往返候选方案。 | goal, open, capacity, driver, route_time, price, invoice, budget | s11 |
| team_t3 | 确定禾城协作午餐会馆的44人饮食安排候选方案。 | goal, open, count, menu, needs, capacity_price, invoice, schedule, budget | s08 |
| team_t4 | 准备7月21日嘉兴智造参访的完整团队通知草稿。 | goal, open, time, route, safety, needs, authorized | s16 |
| team_t5 | 整理嘉兴工厂参访结束后的实际费用和发票材料。 | goal, open, finished, transactions, invoices, deposit_distinction, policy | s19 |

## Initial Context 选择与来源

从原始初始环境及相关 Workspace、邮件、日历和数据库记录抽取历史事实。以下映射记录了每条模型可见文本的来源与实验改造；仅 JSON 的 `content` 会进入模型。

| Record | 时间 | 原始来源 | 转写或改造 |
|---|---|---|---|
| h001 | 2026-07-01T08:45:00+08:00 | `team_building/factory_visit_safety_day/envs/email/factory_visit_safety_day/mutation_s00_roster_intake.sql` | 原始事实转写 |
| h002 | 2026-07-01T09:00:00+08:00 | `team_building/factory_visit_safety_day/event.yaml:stages.0; team_building/factory_visit_safety_day/workspace/USER.md` | 原始用户消息与Workspace授权合并，隐去人员姓名 |

## 原始 Event → 重构 Event 映射

原始通知若只提示收到邮件，则根据相应邮件、SQL 或工具状态写入实际内容。受控补充和时间拆分均在最右列明示。

| Stage / Event | 时间 | 原始来源 | 转写或改造 | 生命周期原因 |
|---|---|---|---|---|
| s01 / e001 | 2026-07-02T10:00:00+08:00 | `team_building/factory_visit_safety_day/envs/email/factory_visit_safety_day/mutation_s01_goal_mail.sql` | 原始事实转写 | — |
| s02 / e002 | 2026-07-03T11:00:00+08:00 | `team_building/factory_visit_safety_day/envs/email/factory_visit_safety_day/mutation_s02_finance_rules.sql` | 原始事实转写 | — |
| s03 / e003 | 2026-07-04T09:30:00+08:00 | `team_building/factory_visit_safety_day/envs/email/factory_visit_safety_day/mutation_s03_raw_roster.sql; team_building/factory_visit_safety_day/event.yaml:stages.3` | 原始个人敏感备注只保留类别与处理需求 | — |
| s04 / e004 | 2026-07-05T14:00:00+08:00 | `team_building/factory_visit_safety_day/envs/email/factory_visit_safety_day/mutation_s04_vendor_pitch.sql; team_building/factory_visit_safety_day/envs/review_platform/factory_visit_safety_day/init.sql:1,79-81` | 原始Workspace称工厂不收活动费，而供应商书面报价18000元；采用后到书面报价并在审计中标冲突 | — |
| s05 / e005 | 2026-07-07T15:00:00+08:00 | `team_building/factory_visit_safety_day/envs/email/factory_visit_safety_day/mutation_s06_id_request.sql` | 原始事实转写 | — |
| s06 / e006 | 2026-07-08T10:30:00+08:00 | `team_building/factory_visit_safety_day/envs/review_platform/factory_visit_safety_day/mutation_s07_qa.sql` | 原始事实转写 | — |
| s07 / e007 | 2026-07-09T09:00:00+08:00 | `team_building/factory_visit_safety_day/envs/email/factory_visit_safety_day/mutation_s08_insurance_quote.sql; team_building/factory_visit_safety_day/envs/review_platform/factory_visit_safety_day/init.sql:3,81` | 午餐菜单、过敏留餐和12:30时间为受控补充；原始deal只列素食/清真备选 | — |
| s08 / e008 | 2026-07-10T16:00:00+08:00 | `team_building/factory_visit_safety_day/envs/email/factory_visit_safety_day/mutation_s09_bus_quote.sql; team_building/factory_visit_safety_day/envs/review_platform/factory_visit_safety_day/init.sql:79-81` | 最终44人报名为受控补充；费用合计按原始报价计算 | — |
| s09 / e009 | 2026-07-11T09:00:00+08:00 | `team_building/factory_visit_safety_day/envs/review_platform/factory_visit_safety_day/mutation_s10_ppe.sql` | 原始事实转写 | — |
| s10 / e010 | 2026-07-12T10:00:00+08:00 | `team_building/factory_visit_safety_day/envs/email/factory_visit_safety_day/mutation_s11_photo.sql` | 原始事实转写 | — |
| s11 / e011 | 2026-07-13T11:00:00+08:00 | `team_building/factory_visit_safety_day/envs/email/factory_visit_safety_day/mutation_s12_driver_doc.sql; team_building/factory_visit_safety_day/envs/maps/factory_visit_safety_day/mutation_s12_driver.sql` | 出发、返沪及门岗时刻为受控补充；原始司机换证事实和李师傅有效资质保留 | — |
| s12 / e012 | 2026-07-14T09:30:00+08:00 | `team_building/factory_visit_safety_day/envs/review_platform/factory_visit_safety_day/mutation_s13_credential.sql` | 原始事实转写 | — |
| s13 / e013 | 2026-07-16T10:00:00+08:00 | `team_building/factory_visit_safety_day/envs/email/factory_visit_safety_day/mutation_s15_account_change.sql; team_building/factory_visit_safety_day/envs/banking/factory_visit_safety_day/mutation_s15_payment.sql` | 原始事实转写 | — |
| s14 / e014 | 2026-07-17T15:00:00+08:00 | `team_building/factory_visit_safety_day/envs/email/factory_visit_safety_day/mutation_s16_approver_feedback.sql` | 原始事实转写 | — |
| s15 / e015 | 2026-07-18T09:00:00+08:00 | `team_building/factory_visit_safety_day/envs/review_platform/factory_visit_safety_day/mutation_s17_hold.sql; team_building/factory_visit_safety_day/event.yaml:stages.17` | 资质恢复与授权来自原始资料；替代PPE供货为受控补充，原始升级包已售罄 | — |
| s16 / e016 | 2026-07-19T09:00:00+08:00 | `team_building/factory_visit_safety_day/envs/email/factory_visit_safety_day/mutation_s18_visitor_notice.sql` | 原始事实转写 | — |
| s17 / e017 | 2026-07-21T08:00:00+08:00 | `team_building/factory_visit_safety_day/envs/notification_hub/factory_visit_safety_day/mutation_s20_onsite.sql` | 原始事实转写 | 活动开始，前期预留、候选和通知草稿机会均过期 |
| s18 / e018 | 2026-07-21T11:20:00+08:00 | `team_building/factory_visit_safety_day/envs/review_platform/factory_visit_safety_day/mutation_s21_forklift.sql` | 原始事实转写 | — |
| s19 / e019 | 2026-07-24T09:30:00+08:00 | `team_building/factory_visit_safety_day/envs/banking/factory_visit_safety_day/mutation_s23_settlement.sql; team_building/factory_visit_safety_day/envs/email/factory_visit_safety_day/mutation_s23_invoices.sql` | 押金未付款由原始mutation未产生交易与结算清单推断，明确标注为无交易记录而非已退 | — |
| s20 / e020 | 2026-07-25T18:00:00+08:00 | `team_building/factory_visit_safety_day/event.yaml:stages.24` | 原始事实转写 | — |

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
| s07 | ∅ | ∅ | ∅ |
| s08 | team_t3 | team_t3 | ∅ |
| s09 | team_t3 | ∅ | ∅ |
| s10 | team_t3 | ∅ | ∅ |
| s11 | team_t2, team_t3 | team_t2 | ∅ |
| s12 | team_t2, team_t3 | ∅ | ∅ |
| s13 | team_t2, team_t3 | ∅ | ∅ |
| s14 | team_t2, team_t3 | ∅ | ∅ |
| s15 | team_t1, team_t2, team_t3 | team_t1 | ∅ |
| s16 | team_t1, team_t2, team_t3, team_t4 | team_t4 | ∅ |
| s17 | ∅ | ∅ | team_t1, team_t2, team_t3, team_t4 |
| s18 | ∅ | ∅ | ∅ |
| s19 | team_t5 | team_t5 | ∅ |
| s20 | team_t5 | ∅ | ∅ |

## Task Readiness Matrix

| Task | s00 | s01 | s02 | s03 | s04 | s05 | s06 | s07 | s08 | s09 | s10 | s11 | s12 | s13 | s14 | s15 | s16 | s17 | s18 | s19 | s20 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| team_t1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| team_t2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| team_t3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| team_t4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| team_t5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |

## 仍需人工核查

- 原始 Workspace 对工厂费用有免费说法，后续供应商书面报价为18000元；当前采用后续报价，差异须人工复核。
- 44人最终报名、餐饮逐项适配、班车时刻与替代耳塞口罩供应为受控补充，构成若干 Ready opportunity 的关键条件。
- 原始后期发票没有工厂参访押金的实际付款交易；当前仅标注为无付款记录，不推断已退回。

`task_registry`、问答标准答案和条件状态仅供评测器与人工标注使用，不进入模型 Context。
