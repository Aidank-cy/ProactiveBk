"""Deterministic scoring from completed human labels only."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from .dataset_loader import load_dataset
from .review import call_id


def ratio(a, b):
    return None if b == 0 else a / b


def annotated_matches(row, ann):
    if row["status"] != "ok" or ann is None:
        return None
    predictions = row["parsed_response"]["actionable_tasks"]
    matches = ann.get("matches", [])
    if len(matches) != len(predictions) or any(m.get("match_status") is None for m in matches):
        return None
    if any(m["match_status"] == "Needs Review" for m in matches):
        return None
    ids = [m.get("matched_task_id") for m in matches if m["match_status"] == "Correct Match"]
    if len(ids) != len(set(ids)):
        raise ValueError("same task matched twice")
    return matches


def score(results, annotations, dataset):
    scenarios = load_dataset(dataset)
    ann = {a["call_id"]: a for a in annotations}
    rows = {(r["model_name"], r["scenario_id"], r["stage_id"], r["sample_id"],
             r["evaluation_type"], r["question_id"] or r["task_id"]): r for r in results}
    counts = defaultdict(int)
    paired = []
    per_scenario = defaultdict(lambda: defaultdict(int))
    for s in scenarios:
        tasks = {t["task_id"]: t for t in s["task_registry"]}
        for st in s["evaluations"]:
            base_keys = {(r["model_name"], r["sample_id"]) for r in results if r["scenario_id"] == s["scenario_id"] and r["stage_id"] == st["stage_id"]}
            for model, sample in base_keys:
                base = (model, s["scenario_id"], st["stage_id"], sample)
                proactive = rows.get((*base, "proactive", None))
                pm = annotated_matches(proactive, ann.get(call_id(proactive))) if proactive else None
                pids = {m["matched_task_id"] for m in pm if m["match_status"] == "Correct Match"} if pm is not None else None
                if pm is not None:
                    ready = set(st["ready_tasks"])
                    tp = len(pids & ready)
                    fp = len(pm) - tp
                    fn = len(ready - pids)
                    for k, n in (("tp", tp), ("fp", fp), ("fn", fn), ("duplicates", sum(m["match_status"] == "Duplicate" for m in pm)), ("predictions", len(pm))):
                        counts[k] += n
                        per_scenario[s["scenario_id"]][k] += n
                    counts["proactive_stages"] += 1
                    if not ready:
                        counts["empty_stages"] += 1
                        counts["empty_correct"] += not pm
                    for tid in st["newly_ready_tasks"]:
                        counts["newly_ready_total"] += 1
                        counts["newly_ready_identified"] += tid in pids
                for q in st["memory_questions"]:
                    r = rows.get((*base, "memory", q["question_id"]))
                    a = ann.get(call_id(r)) if r else None
                    if r and r["status"] == "ok" and a and isinstance(a.get("correct"), bool):
                        counts["memory_questions_scored"] += 1
                        counts["memory_questions_correct"] += a["correct"]
                    else:
                        counts["memory_questions_missing"] += 1
                for tid, task in tasks.items():
                    required = task["required_memory_facts"]
                    memory = []
                    for qid in required:
                        q = next((q for q in st["memory_questions"] if q["question_id"] == qid and tid in q["task_ids"]), None)
                        r = rows.get((*base, "memory", qid)) if q else None
                        a = ann.get(call_id(r)) if r else None
                        memory.append(a["correct"] if r and r["status"] == "ok" and a and isinstance(a.get("correct"), bool) else None)
                    m = all(memory) if required and None not in memory else None
                    counts["task_memory_scored" if m is not None else "task_memory_missing"] += 1
                    counts["task_memory_correct"] += m is True
                    reactive = rows.get((*base, "reactive", tid))
                    rm = annotated_matches(reactive, ann.get(call_id(reactive))) if reactive else None
                    ready = tid in st["ready_tasks"]
                    r_correct = None
                    if rm is not None:
                        predicted = len(rm) == 1 and rm[0]["match_status"] == "Correct Match" and rm[0]["matched_task_id"] == tid
                        empty = len(rm) == 0
                        r_correct = predicted if ready else empty
                        counts["reactive_total"] += 1
                        counts["reactive_correct"] += r_correct
                        counts["reactive_ready" if ready else "reactive_not_ready"] += 1
                        if predicted:
                            counts["reactive_tp" if ready else "reactive_fp"] += 1
                        elif empty:
                            counts["reactive_fn" if ready else "reactive_tn"] += 1
                        else:
                            counts["reactive_wrong_scope"] += 1
                            counts["reactive_fn" if ready else "reactive_fp"] += 1
                    if ready:
                        paired.append({"model_name": model, "scenario_id": s["scenario_id"], "stage_id": st["stage_id"],
                                       "task_id": tid, "sample_id": sample, "ground_truth_ready": True,
                                       "newly_ready": tid in st["newly_ready_tasks"], "memory_correct": m,
                                       "reactive_correct": r_correct, "proactive_correct": tid in pids if pids is not None else None})
    gap = [x for x in paired if x["memory_correct"] is True and x["reactive_correct"] is True and x["proactive_correct"] is not None]
    new_gap = [x for x in gap if x["newly_ready"]]
    precision = ratio(counts["tp"], counts["tp"] + counts["fp"])
    recall = ratio(counts["tp"], counts["tp"] + counts["fn"])
    rprecision = ratio(counts["reactive_tp"], counts["reactive_tp"] + counts["reactive_fp"])
    rrecall = ratio(counts["reactive_tp"], counts["reactive_ready"])
    rates = {"memory_question_accuracy": ratio(counts["memory_questions_correct"], counts["memory_questions_scored"]),
             "memory_task_accuracy": ratio(counts["task_memory_correct"], counts["task_memory_scored"]),
             "reactive_accuracy": ratio(counts["reactive_correct"], counts["reactive_total"]),
             "reactive_precision": rprecision, "reactive_recall": rrecall,
             "reactive_balanced_accuracy": None if not counts["reactive_ready"] or not counts["reactive_not_ready"] else
             (ratio(counts["reactive_tp"], counts["reactive_ready"]) + ratio(counts["reactive_tn"], counts["reactive_not_ready"])) / 2,
             "proactive_micro_precision": precision, "proactive_micro_recall": recall,
             "proactive_micro_f1": None if precision is None or recall is None or precision + recall == 0 else 2 * precision * recall / (precision + recall),
             "empty_stage_accuracy": ratio(counts["empty_correct"], counts["empty_stages"]),
             "duplicate_prediction_rate": ratio(counts["duplicates"], counts["predictions"]),
             "newly_ready_recall": ratio(counts["newly_ready_identified"], counts["newly_ready_total"])}
    def gap_report(items):
        numerator = sum(x["proactive_correct"] is False for x in items)
        return {"numerator": numerator, "denominator": len(items), "value": ratio(numerator, len(items))}
    scenario_reports = {}
    for name, v in per_scenario.items():
        sp = ratio(v["tp"], v["tp"] + v["fp"])
        sr = ratio(v["tp"], v["tp"] + v["fn"])
        scenario_reports[name] = {**v, "precision": sp, "recall": sr,
                                  "f1": None if sp is None or sr is None or sp + sr == 0 else 2*sp*sr/(sp+sr)}
    return {"counts": dict(counts), "rates": rates, "all_ready_proactive_gap": gap_report(gap),
            "newly_ready_proactive_gap": gap_report(new_gap), "per_scenario": scenario_reports,
            "paired": paired, "undefined_rule": "null when denominator is zero; missing and Needs Review excluded"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True)
    p.add_argument("--annotations", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--output", default="outputs/reports/metrics.json")
    a = p.parse_args()
    read = lambda path: [json.loads(x) for x in Path(path).read_text().splitlines()]
    report = score(read(a.results), read(a.annotations), a.dataset)
    path = Path(a.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k,v in report.items() if k != "paired"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
