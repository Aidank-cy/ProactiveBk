"""Generate the fixed four-scenario dataset and its human audit documents."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .build_scenarios import rental, travel, shopping, team_building
from .grounding import grounded_stage
from .coupon_math import audit as coupon_audit

HERE = Path(__file__).resolve().parent
DOC = HERE / "documentation"
BUILDERS = (rental, travel, shopping, team_building)
SOURCE = {
    "rental": "rental/cross_city_remote_viewing_rental",
    "travel": "travel/galapagos_no_us_transit",
    "shopping": "shopping/baby_stroller_safety_standard_30d",
    "team_building": "team_building/factory_visit_safety_day",
}
STORIES = {
    "rental": "魏岚从武汉迁往苏州，8月17日入职，8月15日前需入住。她只在8月8日至9日能线下看房，要求一居室、月租不高于6000元、早高峰门到门不超过45分钟，并能正规居住登记。云栖苑、北岸花园与河滨小筑的信息陆续变化；HR会议、租金上涨、私人收款和东门绕行影响选择。用户允许内部筛选与材料整理，对外联系、付款、签约和提交个人资料均须另行确认。",
    "travel": "林乔与许闻赴厄瓜多尔参加加拉帕戈斯工作坊。出发、返程、8月17日18时登记、证件、预算及许闻晕船限制共同约束航班、住宿、岛上交通和活动。美国转机低价航班因签证不合规，非美国联程、可取消酒店与接送机会先后出现及失效。财务报销与私人支出需分开，票据最后到齐。",
    "shopping": "阎婷同时处理新推车安全、婴儿床配件退货、旧推车出售。后续发生两次疑似重复扣费、买家要求平台外定金、品牌召回信息和新的原厂配件采购需求。7月15日家庭出行是安全处理期限；平台担保和付款授权限制交易方式。平台与银行随后独立处理部分事项。",
    "team_building": "魏然为44人供应链团队组织上海至嘉兴工厂参访，预算上限56000元。包车、餐饮和保险需公司发票，人员有听力、晕车、粉尘及语言需求。工厂资质、PPE、餐饮、司机文件、异常个人收款账户、HR审批及用户授权陆续更新。活动开始后前期规划机会结束，结算材料在活动后到齐。",
}
ISSUES = {
    "rental": [
        "云栖苑和北岸花园的精确通勤、书面登记与可看房时段为受控补充；正式运行前应由研究人员核实补充事实的合理性。",
        "原始北岸花园报价8320元，后续降至5900元是实验补充；若不接受该补充，应删除相应 Ready opportunity 并重算标签。",
    ],
    "travel": [
        "非美国联程3180美元报价、8月19日陆地活动开放与天气、接送座位和班次、每人740美元机票分项为受控补充。",
        "8月2日用户外部订房、8月11日外部出票为受控补充，解释后续账单；原始资料未明确执行者，需研究人员确认这种修订口径。",
        "原始8月17日抵达叙述与8月16日入岛及接送收据相冲突；当前以带日期收据为准，研究人员须裁定。",
    ],
    "shopping": [
        "平台介入所需照片、视频、平台规则、推车精确批次、买家最后确认及信用卡订单对应凭证有受控补充；需研究人员核实。",
        "购物车最低价已按原始商城服务代码核验为146.30元；若未来平台实现改变券规则，须重新计算。",
    ],
    "team_building": [
        "原始 Workspace 对工厂费用有免费说法，后续供应商书面报价为18000元；当前采用后续报价，差异须人工复核。",
        "44人最终报名、餐饮逐项适配、班车时刻与替代耳塞口罩供应为受控补充，构成若干 Ready opportunity 的关键条件。",
        "免押金临时hold、第二司机资质、英语及特殊需求安排为受控补充；原始后期未给工厂、PPE和押金交易，当前只列待确认，不推断已支付或退回。",
    ],
}
INITIAL_IMPACT = {
    "rental": {"h004": "rental_t1, rental_t2, rental_t3", "h005": "rental_t1, rental_t2, rental_t3, rental_t4"},
    "travel": {"h001": "travel_t1, travel_t2, travel_t3, travel_t5", "h002": "travel_t4, travel_t5"},
    "shopping": {"h001": "shopping_t1, shopping_t2, shopping_t4", "h002": "shopping_t1, shopping_t2, shopping_t4"},
    "team_building": {"h001": "team_t1, team_t2, team_t3", "h002": "team_t1, team_t2, team_t3, team_t4, team_t5"},
}


def dump(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def matrix(scenario):
    stages = scenario["evaluations"]
    head = "| Task | " + " | ".join(x["stage_id"] for x in stages) + " |"
    separator = "|---|" + "---|" * len(stages)
    rows = []
    for task in scenario["task_registry"]:
        tid = task["task_id"]
        rows.append("| " + tid + " | " + " | ".join("1" if tid in s["ready_tasks"] else "0" for s in stages) + " |")
    return "\n".join((head, separator, *rows))


def statistics(scenario):
    stages = scenario["evaluations"]
    memory = sum(len(x["memory_questions"]) for x in stages)
    reactive = sum(len(x["reactive_questions"]) for x in stages)
    return {
        "initial_context_tokens_estimate": round(sum(len(x["content"].encode("utf-8")) for x in scenario["initial_context"]) / 3),
        "final_context_tokens_estimate": round(sum(len(x["content"].encode("utf-8")) for x in scenario["initial_context"] + scenario["events"]) / 3),
        "events": len(scenario["events"]),
        "tasks": len(scenario["task_registry"]),
        "unique_memory_questions": len({q["question_id"] for s in stages for q in s["memory_questions"]}),
        "stage_memory_calls": memory,
        "stage_reactive_calls": reactive,
        "proactive_calls": len(stages),
        "total_calls_per_model_sample": memory + reactive + len(stages),
        "ready_task_stage_pairs": sum(len(s["ready_tasks"]) for s in stages),
        "newly_ready_opportunities": sum(len(s["newly_ready_tasks"]) for s in stages),
        "empty_stages": sum(not s["ready_tasks"] for s in stages),
        "invalidations": sum(len(s["invalidated_tasks"]) for s in stages),
    }


def reconstruction(scenario, audit):
    sid = scenario["scenario_id"]
    stages = scenario["evaluations"]
    lines = [f"# {sid} reconstruction", "", "## 原始目录与剧情", "",
             f"`VibeLifeBench/eval_set/{SOURCE[sid]}/`", "", STORIES[sid], "",
             "## 固定 Task、条件与首次 Ready", "",
             "条件字段的逐 Stage 三值标签以 JSON 中 `task_states` 为准。`open` 表示该具体行动尚未完成且时间窗口未过。", "",
             "| Task | 行动 | 必要条件 | 首次 Ready |", "|---|---|---|---|"]
    for t in scenario["task_registry"]:
        first = next((s["stage_id"] for s in stages if t["task_id"] in s["newly_ready_tasks"]), "无")
        lines.append(f"| {t['task_id']} | {t['description']} | {', '.join(t['conditions'])} | {first} |")
    lines += ["", "## Initial Context 选择与来源", "",
              "从原始初始环境及相关 Workspace、邮件、日历和数据库记录抽取历史事实。以下映射记录了每条模型可见文本的来源与实验改造；仅 JSON 的 `content` 会进入模型。", "",
              "| Record | 时间 | 原始来源 | 转写或改造 |", "|---|---|---|---|"]
    for model, source in zip(scenario["initial_context"], audit["initial"]):
        origin = "; ".join(source["origin"])
        impact = INITIAL_IMPACT.get(sid, {}).get(model["record_id"], "背景记录")
        lines.append(f"| {model['record_id']} | {model['timestamp']} | `{origin}` | {source['adaptation']}；影响 {impact} |")
    lines += ["", "## 原始 Event → 重构 Event 映射", "",
              "原始通知若只提示收到邮件，则根据相应邮件、SQL 或工具状态写入实际内容。受控补充和时间拆分均在最右列明示。", "",
              "| Stage / Event | 时间 | 原始来源 | 转写或改造 | 生命周期原因 |", "|---|---|---|---|---|"]
    for i, e in enumerate(audit["events"], 1):
        origin = "; ".join(e["origin"])
        lines.append(f"| s{i:02d} / {e['event_id']} | {e['timestamp']} | `{origin}` | {e['adaptation']}；影响 {', '.join(e['affected_tasks']) or '无固定Task'} | {e['lifecycle_reason'] or '—'} |")
    lines += ["", "## Stage Ready Tasks", "", "| Stage | Ready | Newly Ready | Invalidated |", "|---|---|---|---|"]
    for s in stages:
        lines.append(f"| {s['stage_id']} | {', '.join(s['ready_tasks']) or '∅'} | {', '.join(s['newly_ready_tasks']) or '∅'} | {', '.join(s['invalidated_tasks']) or '∅'} |")
    lines += ["", "## Task Readiness Matrix", "", matrix(scenario), "",
              "## 仍需人工核查", ""]
    lines += [f"- {issue}" for issue in ISSUES[sid]]
    lines += ["", "`task_registry`、问答标准答案和条件状态仅供评测器与人工标注使用，不进入模型 Context。", ""]
    return "\n".join(lines)


def semantic_report(items, outputs):
    lines = ["# Semantic audit report", "",
             "Each row refers to a reviewer-only `*_semantic_audit.json` file. Those files give every Memory answer and visible-record evidence, condition-to-question mapping, time cutoff, Ready support, and missing fact. This trace supports manual review; it does not prove the business truth of a controlled addition.", ""]
    for scenario, _ in items:
        sid = scenario["scenario_id"]
        stages = outputs[DOC / f"{sid}_semantic_audit.json"]["stages"]
        lines += [f"## {sid}", "", "| Stage | Event | Simulated time | Active goals | Changed facts | Changed conditions | Ready | New | Leaving | Ready evidence | Unknown conditions |",
                  "|---|---|---|---|---|---|---|---|---|---|---:|"]
        for st in stages:
            support = sorted({rid for task in st["tasks"].values() if task["ready"] for rid in task["supporting_record_ids"]})
            unknown = sum(len(task["remaining_ambiguities"]) for task in st["tasks"].values())
            values = (st["stage_id"], st["current_event_id"] or "—", st["simulated_now"],
                      ", ".join(st["active_user_goals"]) or "∅", ", ".join(st["changed_facts"]) or "∅",
                      ", ".join(st["changed_task_conditions"]) or "∅", ", ".join(st["ready_tasks"]) or "∅",
                      ", ".join(st["newly_ready_tasks"]) or "∅", ", ".join(st["tasks_leaving_ready"]) or "∅",
                      ", ".join(support) or "∅", str(unknown))
            lines.append("| " + " | ".join(values) + " |")
        lines += ["", "### Task transition audit", ""]
        for task in scenario["task_registry"]:
            tid = task["task_id"]
            first = next((i for i, st in enumerate(stages) if tid in st["newly_ready_tasks"]), None)
            if first is None:
                lines.append(f"- `{tid}`: never Ready; see Unknown and Unsatisfied condition evidence in the JSON audit.")
            else:
                before = stages[first - 1]["stage_id"] if first else "—"
                continued = [st["stage_id"] for st in stages if tid in st["ready_tasks"]]
                leaving = [st["stage_id"] for st in stages if tid in st["tasks_leaving_ready"]]
                lines.append(f"- `{tid}`: preceding {before}; first Ready {stages[first]['stage_id']}; Ready at {', '.join(continued)}; leaves at {', '.join(leaving) or '—'}.")
        lines.append("")
    return "\n".join(lines)


def change_log():
    return "\n".join([
        "# Dataset change log: semantic repair", "",
        "Every controlled addition is also recorded beside its initial record or event in the reconstruction documents, with source paths and affected fixed Tasks. No evaluation model produced these changes.", "",
        "| Scenario | Earlier data | Repair and GT effect |", "|---|---|---|",
        "| Rental | Weekend-only east-gate detour incorrectly invalidated long-term commute; calendar conflicts omitted; contract Task read as early checklist. | Explicit post-start daily commute criterion, visible calendar extract, temporary 51-minute detour separate from 38-minute daily route; T1 remains Ready until viewing window ends. T4 explicitly requires the final attachment package. North quote and slot supplements are explained. |",
        "| Travel | 3180-dollar quote reused for days, hotel sold out despite final stay, August 17 arrival contradicted August 16 receipts, holds conflated with payments. | Quote and seat guarantee expires August 1 at 00:55; flight becomes Ready only in the valid quote window. User externally books hotel before public sellout and confirms 1480-dollar airfare August 11. Actual arrival aligns to August 16 receipts. Bank hold, declined charge, settlement and release request remain distinct. |",
        "| Shopping | 163.40 was called the optimal cart; Memory asked optimization; old sale time and platform intervention application remained actionable after they expired or completed. | Mall rules are exposed as raw facts; deterministic enumeration gives A-standard/B-single/C-single at 146.30. Optimization answer is removed from Memory and Event. Sale time expires and user externally submits platform intervention; specific authorization updates Memory. |",
        "| Team building | Notice time leaked future 09:00 detail; one bus driver verified; risky paid reservation called cancellable; final archive omitted factory/PPE status. | Notice time appears only in final visitor email. Both drivers, vehicles and accommodations are stated. User-authorized zero-deposit temporary hold has a deadline while personal payment risk remains. Final task is a dated status-and-missing-evidence package. |",
        "", "## Key event and GT comparison", "",
        "Stage IDs after an inserted event are intentionally renumbered; compare event content and timestamps when reviewing the old and new JSON.", "",
        "| Scenario | Earlier key label/content | Repaired key label/content |", "|---|---|---|",
        "| Rental | S14 weekend east-gate 51 minutes made rental_t1 commute Unsatisfied and removed it from Ready. | S14 distinguishes temporary viewing-weekend detour from post-start daily 38-minute route; rental_t1 remains Ready. Both viewing Tasks leave Ready when their dated slots pass at S15. |",
        "| Travel | S07 3180-dollar airfare immediately marked budget Satisfied and stayed Ready across ten days. | S07 airfare budget Unknown; S08 exposes lodging and cost bounds while the quote is valid, making travel_t1 Ready. S09 simulated time passes the fare cutoff and t1 leaves Ready; hotel budget becomes Unknown until external booking removes the reservation Task. |",
        "| Travel | August 17 arrival and August 16 receipts coexisted; hotel showed sold out before a later stay bill; holds and settlement were mixed. | A dated user external booking precedes public stock zero, external ticket confirmation precedes travel, and actual island arrival is August 16. The bank hold, 24-dollar decline, August 11 settlement, and hotel release request each have separate Event facts and Memory GT. |",
        "| Shopping | S07 Event and Memory GT asserted A-economy/B-single/C-three-pack at 163.40 was optimal; S15 sale plan kept Ready after July 6 17:00. | S07 exposes only SKU and coupon inputs. Independent 18-combination enumeration yields A-standard/B-single/C-single at 146.30 in hidden audit. Sale time expires before the July 8 Stage; intervention application is marked externally submitted before approval. |",
        "| Team building | S11 Memory GT already gave 09:00 safety briefing, and S15 marked a costly reservation Ready despite personal-account risk. | S11 says briefing time Unknown; S16 visitor notice gives 09:00 and special handling. Only the zero-deposit, loss-free temporary hold becomes Ready at S16; its offer expires before the next Stage. |",
        "", "## Final pilot fact and matching repair", "",
        "This pass corrects reference answers and recognition criteria without changing the four fixed scenarios, 19 tasks, or event counts. The hotel-date correction moves one condition transition from Travel S04 to S08; first Ready stages remain unchanged.", "",
        "| Scenario and field | Earlier GT or rule | Repaired GT or rule |", "|---|---|---|",
        "| Travel S04 `t_hotel_dates` | Full August 16–23 stay and seven nights before the hotel dates were visible. | Only August 16 evening arrival advice is known; full dates first appear with the S08 hotel offer. Evidence changes from e004 to e008 for the full dates. |",
        "| Travel S06 `t_flight_stock` | Every segment has at least three seats. | Some segments have three seats; availability of two seats on every leg remains Unknown until S07 confirms two seats. |",
        "| Travel S17 `t_flight_hold` | Airline seat hold lasts 72 hours. | Airline temporarily holds two seats but gives no hold expiry; 72 hours is the bank payment-confirmation deadline. |",
        "| Travel S20 `t_claim_payment` | $70 transfer marked paid after service use. | Service used, payment unconfirmed until S22 receipt states $70 settled. |",
        "| Travel `travel_t4` | Seasickness preference was in context but lacked its own Memory question. | `t_land_comfort` asks for Xu Wen's seasickness and long-speedboat limit, grounded in h002 and required by the task. |",
        "| Team S00–S14 `b_notice_goal` | Claimed a July 18 second authorization before it occurred. | Only July 1 permission to prepare internal drafts, grounded in h002; S15 update uses e015. |",
        "| Team S06–S07 `b_lunch_quote` | S06 prematurely stated the 11880-yuan offer; S07 asserted unsupported 70-person capacity. | S06 records settlement rule while price and capacity are unknown; S07 states 11880 yuan and confirmed accommodation of 44 people. |",
        "| All 19 Matching Guidelines | Some demanded a complete plan or exact SKU, coupon, price and reference wording. | Recognition of the specified actionable user goal is enough; output need not solve the task. Wrong object, violated constraints or unauthorized execution remain non-matches. |",
        "", "Automated tests check provenance structure, time cutoffs and generated consistency. Researchers must still adjudicate controlled supplements and unresolved business ambiguities before scored model inference.", ""])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated files differ")
    args = parser.parse_args()
    items = [builder() for builder in BUILDERS]
    scenarios = [s for s, _ in items]
    outputs = {HERE / f"{s['scenario_id']}.json": s for s in scenarios}
    outputs[HERE / "all_scenarios.json"] = {"scenarios": scenarios}
    for s, audit in items:
        outputs[DOC / f"{s['scenario_id']}_reconstruction.md"] = reconstruction(s, audit)
        grounded = []
        for index, (stage, meta) in enumerate(zip(s["evaluations"], audit["grounding"])):
            item = grounded_stage(s, stage, meta)
            event = audit["events"][index - 1] if index else None
            item["changed_facts"] = event["changed_facts"] if event else {}
            item["changed_task_conditions"] = event["changed_conditions"] if event else {}
            item["lifecycle_reason"] = event["lifecycle_reason"] if event else ""
            grounded.append(item)
        outputs[DOC / f"{s['scenario_id']}_semantic_audit.json"] = {"scenario_id": s["scenario_id"], "stages": grounded}
    stats = {s["scenario_id"]: statistics(s) for s in scenarios}
    lines = ["# Fixed four-scenario dataset", "",
             "All counts are derived from the fixed JSON. Initial and final-context tokens are **estimates** (UTF-8 bytes / 3), not API token usage. API calls assume one model and one sample; multiply by model and sample counts.", "",
             "| Scenario | Events | Tasks | Unique memory Q | Memory calls | Reactive calls | Proactive calls | Total calls | Ready task-stage pairs | Newly ready | Empty stages | Invalidations | Initial tokens est. | Final tokens est. |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    keys = ("events", "tasks", "unique_memory_questions", "stage_memory_calls", "stage_reactive_calls", "proactive_calls", "total_calls_per_model_sample", "ready_task_stage_pairs", "newly_ready_opportunities", "empty_stages", "invalidations", "initial_context_tokens_estimate", "final_context_tokens_estimate")
    for sid, d in stats.items():
        lines.append("| " + sid + " | " + " | ".join(str(d[k]) for k in keys) + " |")
    lines += ["", "The four separate JSON files are the source for `all_scenarios.json`; regenerate with `python -m evaluation.data.scenarios.materialize`. Freeze both the builder and generated files before inference.", ""]
    outputs[DOC / "dataset_summary.md"] = "\n".join(lines)
    outputs[DOC / "semantic_audit_report.md"] = semantic_report(items, outputs)
    outputs[DOC / "dataset_change_log.md"] = change_log()
    outputs[DOC / "shopping_coupon_audit.json"] = coupon_audit()
    if args.check:
        mismatches = [str(p) for p, value in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != (json.dumps(value, ensure_ascii=False, indent=2) + "\n" if not isinstance(value, str) else value)]
        if mismatches:
            raise SystemExit("stale generated files: " + ", ".join(mismatches))
    else:
        for path, value in outputs.items():
            if isinstance(value, str):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value, encoding="utf-8")
            else:
                dump(path, value)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
