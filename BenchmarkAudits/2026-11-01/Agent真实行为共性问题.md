这 40 个任务里，**最反复出现的是：Agent 已经拿到部分关键信息，却在执行动作或宣布结果前，没有把条件核对完整。** 具体表现有四种：

| 共性问题 | 轨迹里的具体行为 |
|---|---|
| **动作前没核清代价或前提** | `galapagos_no_us_transit` 看到新机票便宜 100 美元，就取消旧 HOLD；后来才发现取消费 165 美元，实际贵了约 65 美元。`arm_escrow_shortfall_reset_guard_30d` 明知还有自动扣款和待付款，仍新增手动还款，没先确保用户要求的“只付一次”。`baby_stroller_safety_standard_30d` 已知道旧车是新车安全未确认时的备用车，却在用户准备出售时没有提醒。[审计记录](/home/hezd/nfs_hzd/ProactiveBk/test/四组任务真实行为审计发现.md:11) |
| **把未经核实的数据用于后续判断** | `central_ac_install_30d` 把工具返回的 **21,600 分**当成 **21,600 元**，错误台账沿用到 Stage 5。`wheelchair_student_accessible_rental` 给六套房算一次性支出时漏掉首月租金。`civil_service_written_to_interview_audit` 没查消费记录，就写“已花 151 元、剩 649 元”，还据此缩小购买范围。`food_safety_dispute_33d` 用猜测的账户 ID 查不到收藏，就告诉用户“原来没有收藏”。[审计记录](/home/hezd/nfs_hzd/ProactiveBk/test/四组任务真实行为审计发现.md:9) |
| **前一阶段知道的约束，后一阶段没有用上** | 婴儿车任务中，Stage 16 提出“保留旧车作安全备用”，Stage 17 谈卖车时却只处理交易流程。`factory_visit_safety_day` 在 Stage 16 已记录有人需要英文安全须知，直到现场有人听不懂时才制作英文卡。`east_china_bereavement_docs_reissue` 改车票和路线时，没有先落实改道所依赖的苏州住宿，之后又把上海住宿记录断档称作“不急”。[审计记录](/home/hezd/nfs_hzd/ProactiveBk/test/四组任务真实行为审计发现.md:14) |
| **把“已申请、已配置、当前首选”说成“已完成、已验证、已确定”** | CLaw-Anything 场馆任务只得到邮件 `status: sent`，最终却称时段 **Booked**；上线窗口任务在 SRE 覆盖和 CDN 未落实时写 **Commit**；工作流任务只改了 cron、尚未观察新周日的运行，就称“没有重叠、运行正常”。VibeLifeBench 看房任务也把未来的地图预估标为“通勤实测”。[审计记录](/home/hezd/nfs_hzd/ProactiveBk/test/四组任务真实行为审计发现.md:17) |

还有一个贯穿多题的现象：**Agent 后来能发现并纠正错误，但发现得晚。** 金额单位到 Stage 6 才改、租房费用到 Stage 8 才重算、法律检索到 Stage 2 才找到正确账户、英文安全卡到现场才补。按我们约定的审计准则，后续纠正不抹去前面已经影响判断或操作的错误。[审计记录](/home/hezd/nfs_hzd/ProactiveBk/test/四组任务真实行为审计发现.md:9)

这些是**本轮轨迹中有证据的模式**，不能据此说所有未得分阶段都有同样问题。CLaw-Anything 另有一题检索到超时且没有最终答复，但其中同时有运行器的 1260 秒限制，不能单独归为 Agent 能力缺陷。[超时案例](/home/hezd/nfs_hzd/ProactiveBk/test/四组任务真实行为审计发现.md:23)
