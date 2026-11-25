# shopping reconstruction

## 原始目录与剧情

`VibeLifeBench/eval_set/shopping/baby_stroller_safety_standard_30d/`

阎婷同时处理新推车安全、婴儿床配件退货、旧推车出售。后续发生两次疑似重复扣费、买家要求平台外定金、品牌召回信息和新的原厂配件采购需求。7月15日家庭出行是安全处理期限；平台担保和付款授权限制交易方式。平台与银行随后独立处理部分事项。

## 固定 Task、条件与首次 Ready

条件字段的逐 Stage 三值标签以 JSON 中 `task_states` 为准。`open` 表示该具体行动尚未完成且时间窗口未过。

| Task | 行动 | 必要条件 | 首次 Ready |
|---|---|---|---|
| shopping_t1 | 为ord_strr_0002婴儿床配件退货申请平台介入。 | goal, open, case, merchant_dispute, rule, photo, video, deadline, authorized | s13 |
| shopping_t2 | 准备旧GlideBaby S3推车与已确认买家的平台担保交易方案。 | goal, open, listing, buyer, price, time, platform, user_choice | s14 |
| shopping_t3 | 准备BABYJOGGER US重复扣费的信用卡争议材料。 | goal, open, duplicate, order_link, documents, authorized | s10 |
| shopping_t4 | 确定新GlideBaby S5推车在7月15日出行前的安全处理方案。 | goal, open, batch, official_policy, cost_cycle, travel_fit, authorized | s13 |
| shopping_t5 | 选出配件A、配件B和耗材C的最低到手价原厂组合并加入购物车。 | goal, open, catalog, stock, coupon, authorized | s07 |

## Initial Context 选择与来源

从原始初始环境及相关 Workspace、邮件、日历和数据库记录抽取历史事实。以下映射记录了每条模型可见文本的来源与实验改造；仅 JSON 的 `content` 会进入模型。

| Record | 时间 | 原始来源 | 转写或改造 |
|---|---|---|---|
| h001 | 2026-06-14T20:10:00+08:00 | `shopping/baby_stroller_safety_standard_30d/envs/ecommerce/baby_stroller_safety_standard_30d/init.sql:1025-1034; shopping/baby_stroller_safety_standard_30d/envs/listing_platform/baby_stroller_safety_standard_30d/init.sql:4` | 原始事实转写；影响 shopping_t1, shopping_t2, shopping_t4 |
| h002 | 2026-06-15T09:00:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.0; shopping/baby_stroller_safety_standard_30d/workspace/USER.md` | 原始消息与Workspace授权合并，不提前引入后续信用卡争议和配件采购目标；影响 shopping_t1, shopping_t2, shopping_t4 |

## 原始 Event → 重构 Event 映射

原始通知若只提示收到邮件，则根据相应邮件、SQL 或工具状态写入实际内容。受控补充和时间拆分均在最右列明示。

| Stage / Event | 时间 | 原始来源 | 转写或改造 | 生命周期原因 |
|---|---|---|---|---|
| s01 / e001 | 2026-06-16T10:00:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.2` | 原始事实转写；影响 无固定Task | — |
| s02 / e002 | 2026-06-17T14:05:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.3` | 原始内联mutation值转写；影响 shopping_t1 | — |
| s03 / e003 | 2026-06-18T18:20:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.4` | 删除钓鱼链接，保留风险事实；影响 无固定Task | — |
| s04 / e004 | 2026-06-20T11:20:00+08:00 | `shopping/baby_stroller_safety_standard_30d/envs/credit_card/baby_stroller_safety_standard_30d/init.sql:7; shopping/baby_stroller_safety_standard_30d/event.yaml:stages.6` | 原始事实转写；影响 shopping_t3 | — |
| s05 / e005 | 2026-06-21T15:05:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.7` | 原始事实转写；影响 shopping_t2 | — |
| s06 / e006 | 2026-06-22T15:00:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.8` | 原始事实转写；影响 shopping_t5 | — |
| s07 / e007 | 2026-06-23T13:05:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.9; shopping/baby_stroller_safety_standard_30d/envs/ecommerce/baby_stroller_safety_standard_30d/init.sql:15-36; shopping/baby_stroller_safety_standard_30d/envs/ecommerce/baby_stroller_safety_standard_30d/init.sql:1022-1024` | SKU和券来自原始seed；独立原价基数及取整由商城服务代码核实后转为可见规则；删除错误的最优答案；影响 shopping_t1, shopping_t5 | — |
| s08 / e008 | 2026-06-24T09:05:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.10` | 原始事实转写；影响 shopping_t3 | — |
| s09 / e009 | 2026-06-25T10:00:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.11; shopping/baby_stroller_safety_standard_30d/envs/notification_hub/baby_stroller_safety_standard_30d/init.sql:10-12` | 原始事实转写；影响 shopping_t4 | — |
| s10 / e010 | 2026-06-26T16:20:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.12; shopping/baby_stroller_safety_standard_30d/envs/email/baby_stroller_safety_standard_30d/init.sql; shopping/baby_stroller_safety_standard_30d/envs/credit_card/baby_stroller_safety_standard_30d/init.sql:7` | 买家平台外邮件为原始内联mutation；海外遮阳棚订单号和账单截图关联为受控补充，原始seed缺此凭证；影响 shopping_t2, shopping_t3 | — |
| s11 / e011 | 2026-06-30T10:05:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.14` | 原始事实转写；影响 shopping_t3 | 信用卡争议材料准备机会因外部受理而结束 |
| s12 / e012 | 2026-07-02T09:00:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.15` | 平台规则、照片与具体申请授权为受控澄清，区别于初始通用授权限制；影响 shopping_t1, shopping_t2, shopping_t3, shopping_t4, shopping_t5 | — |
| s13 / e013 | 2026-07-04T10:00:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.16; shopping/baby_stroller_safety_standard_30d/envs/notification_hub/baby_stroller_safety_standard_30d/init.sql:10-12` | 视频、批次、个案加急换新及加固周期为受控补充；明确一般两周与个案加急不矛盾，退货替代品时间仍未知；影响 shopping_t1, shopping_t4 | — |
| s14 / e014 | 2026-07-06T14:00:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.17; shopping/baby_stroller_safety_standard_30d/envs/listing_platform/baby_stroller_safety_standard_30d/init.sql:4` | 用户选择来自原始消息；买家接受原价、时间和担保为受控补充；影响 shopping_t2 | — |
| s15 / e015 | 2026-07-08T18:05:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.18` | 旧交易时段失效由当前模拟时间计算，不假设7月11日已完成交易；影响 shopping_t2, shopping_t3 | 旧推车具体交易时段已过，不能沿用原方案 |
| s16 / e016 | 2026-07-09T08:30:00+08:00 | `` | 受控外部完成事件：补齐7月10日获批之前的申请生命周期，不把申请归因于评测模型；影响 shopping_t1 | 用户外部提交平台介入申请 |
| s17 / e017 | 2026-07-10T11:05:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.19` | 原始事实转写；影响 shopping_t1 | 退货平台介入已由外部完成 |
| s18 / e018 | 2026-07-11T16:05:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.20` | 金额沿用挂牌价与受控买家确认；重新约定时间为受控补充，解释7月6日旧时段失效后仍在7月11日外部成交；不归因于评测模型；影响 shopping_t2 | 旧推车交易已由外部完成 |
| s19 / e019 | 2026-07-14T10:00:00+08:00 | `shopping/baby_stroller_safety_standard_30d/event.yaml:stages.23` | 换新完成状态为受控澄清，不推断已经交付或可赶上7月15日出行；影响 shopping_t4 | — |

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
| s07 | shopping_t5 | shopping_t5 | ∅ |
| s08 | shopping_t5 | ∅ | ∅ |
| s09 | shopping_t5 | ∅ | ∅ |
| s10 | shopping_t3, shopping_t5 | shopping_t3 | ∅ |
| s11 | shopping_t5 | ∅ | shopping_t3 |
| s12 | shopping_t5 | ∅ | ∅ |
| s13 | shopping_t1, shopping_t4, shopping_t5 | shopping_t1, shopping_t4 | ∅ |
| s14 | shopping_t1, shopping_t2, shopping_t4, shopping_t5 | shopping_t2 | ∅ |
| s15 | shopping_t1, shopping_t4, shopping_t5 | ∅ | shopping_t2 |
| s16 | shopping_t4, shopping_t5 | ∅ | shopping_t1 |
| s17 | shopping_t4, shopping_t5 | ∅ | ∅ |
| s18 | shopping_t4, shopping_t5 | ∅ | ∅ |
| s19 | shopping_t5 | ∅ | shopping_t4 |

## Task Readiness Matrix

| Task | s00 | s01 | s02 | s03 | s04 | s05 | s06 | s07 | s08 | s09 | s10 | s11 | s12 | s13 | s14 | s15 | s16 | s17 | s18 | s19 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| shopping_t1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| shopping_t2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| shopping_t3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| shopping_t4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 0 |
| shopping_t5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

## 仍需人工核查

- 平台介入所需照片、视频、平台规则、推车精确批次、买家最后确认及信用卡订单对应凭证有受控补充；需研究人员核实。
- 购物车最低价已按原始商城服务代码核验为146.30元；若未来平台实现改变券规则，须重新计算。

`task_registry`、问答标准答案和条件状态仅供评测器与人工标注使用，不进入模型 Context。
