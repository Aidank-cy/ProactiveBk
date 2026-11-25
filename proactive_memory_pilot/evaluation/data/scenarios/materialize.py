"""Generate the fixed four-scenario dataset and its human audit documents."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .build_scenarios import rental, travel, shopping, team_building

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
        "原始后期票据显示 Jardin Tranquilo 入住，但此前库存归零；原始资料未清晰说明是谁完成了外部订房。此处仅把早期可预留窗口作为实验机会，后期票据视为外部状态，需人工核对。",
        "原始工作坊时间线与跨时区飞行资料存在跨日表述；模拟时间均带时区，登记和接送兼容性需人工复查。",
    ],
    "shopping": [
        "平台介入所需照片、视频、平台规则、推车精确批次、买家最后确认及信用卡订单对应凭证有受控补充；需研究人员核实。",
        "购物车最优组合按当前三类原厂商品和既有券规则计算；如平台实际叠加规则不同，应重新计算价格及 Ready 标签。",
    ],
    "team_building": [
        "原始 Workspace 对工厂费用有免费说法，后续供应商书面报价为18000元；当前采用后续报价，差异须人工复核。",
        "44人最终报名、餐饮逐项适配、班车时刻与替代耳塞口罩供应为受控补充，构成若干 Ready opportunity 的关键条件。",
        "原始后期发票没有工厂参访押金的实际付款交易；当前仅标注为无付款记录，不推断已退回。",
    ],
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
        lines.append(f"| {model['record_id']} | {model['timestamp']} | `{origin}` | {source['adaptation']} |")
    lines += ["", "## 原始 Event → 重构 Event 映射", "",
              "原始通知若只提示收到邮件，则根据相应邮件、SQL 或工具状态写入实际内容。受控补充和时间拆分均在最右列明示。", "",
              "| Stage / Event | 时间 | 原始来源 | 转写或改造 | 生命周期原因 |", "|---|---|---|---|---|"]
    for i, e in enumerate(audit["events"], 1):
        origin = "; ".join(e["origin"])
        lines.append(f"| s{i:02d} / {e['event_id']} | {e['timestamp']} | `{origin}` | {e['adaptation']} | {e['lifecycle_reason'] or '—'} |")
    lines += ["", "## Stage Ready Tasks", "", "| Stage | Ready | Newly Ready | Invalidated |", "|---|---|---|---|"]
    for s in stages:
        lines.append(f"| {s['stage_id']} | {', '.join(s['ready_tasks']) or '∅'} | {', '.join(s['newly_ready_tasks']) or '∅'} | {', '.join(s['invalidated_tasks']) or '∅'} |")
    lines += ["", "## Task Readiness Matrix", "", matrix(scenario), "",
              "## 仍需人工核查", ""]
    lines += [f"- {issue}" for issue in ISSUES[sid]]
    lines += ["", "`task_registry`、问答标准答案和条件状态仅供评测器与人工标注使用，不进入模型 Context。", ""]
    return "\n".join(lines)


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
    stats = {s["scenario_id"]: statistics(s) for s in scenarios}
    lines = ["# Fixed four-scenario dataset", "",
             "All counts are derived from the fixed JSON. Initial-context tokens are **estimates** (UTF-8 bytes / 3), not API token usage. API calls assume one model and one sample; multiply by model and sample counts.", "",
             "| Scenario | Events | Tasks | Unique memory Q | Memory calls | Reactive calls | Proactive calls | Total calls | Ready task-stage pairs | Newly ready | Empty stages | Invalidations | Initial tokens est. |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    keys = ("events", "tasks", "unique_memory_questions", "stage_memory_calls", "stage_reactive_calls", "proactive_calls", "total_calls_per_model_sample", "ready_task_stage_pairs", "newly_ready_opportunities", "empty_stages", "invalidations", "initial_context_tokens_estimate")
    for sid, d in stats.items():
        lines.append("| " + sid + " | " + " | ".join(str(d[k]) for k in keys) + " |")
    lines += ["", "The four separate JSON files are the source for `all_scenarios.json`; regenerate with `python -m evaluation.data.scenarios.materialize`. Freeze both the builder and generated files before inference.", ""]
    outputs[DOC / "dataset_summary.md"] = "\n".join(lines)
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
