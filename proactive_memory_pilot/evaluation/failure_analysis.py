"""Export paired cases without assigning causal explanations."""
import argparse
import json
from pathlib import Path
from .metrics import score
from .review import call_id
from .dataset_loader import load_dataset


def analyze(results, annotations, dataset):
    report = score(results, annotations, dataset)
    truth = {(s["scenario_id"], st["stage_id"]): (s, st) for s in load_dataset(dataset) for st in s["evaluations"]}
    cases = []
    for pair in report["paired"]:
        matching = [r for r in results if all(r.get(k) == pair[k] for k in
                    ("model_name", "scenario_id", "stage_id", "sample_id"))]
        m = pair["memory_correct"]
        r = pair["reactive_correct"]
        p = pair["proactive_correct"]
        category = ("missing_annotation" if None in (m, r, p) else
                    "memory_incorrect" if not m else
                    "reactive_incorrect" if not r else
                    "core_gap" if not p else "all_correct")
        scenario, stage = truth[(pair["scenario_id"], pair["stage_id"])]
        task = next(t for t in scenario["task_registry"] if t["task_id"] == pair["task_id"])
        cases.append({**pair, "category": category, "requests": matching if category == "core_gap" else None,
                      "ground_truth": {"ready_tasks": stage["ready_tasks"], "task": task,
                                       "memory_questions": [q for q in stage["memory_questions"] if pair["task_id"] in q["task_ids"]]}
                      if category == "core_gap" else None,
                      "annotations": [a for a in annotations if a["call_id"] in
                                      {call_id(x) for x in matching}]
                      if category == "core_gap" else None})
    false_positives = []
    valid_extras = []
    annotation_lookup = {a["call_id"]: a for a in annotations}
    for row in results:
        if row["evaluation_type"] != "proactive" or row["status"] != "ok":
            continue
        annotation = annotation_lookup.get(call_id(row), {})
        for match in annotation.get("matches", []):
            if match.get("match_status") in ("Not Ready", "Out of Scope", "Unsupported Task", "Duplicate"):
                false_positives.append({"model_name": row["model_name"], "scenario_id": row["scenario_id"],
                                        "stage_id": row["stage_id"], "sample_id": row["sample_id"],
                                        "prediction": row["parsed_response"]["actionable_tasks"][match["prediction_index"]],
                                        "annotation": match})
            if match.get("match_status") == "Valid Extra Task":
                valid_extras.append({"model_name": row["model_name"], "scenario_id": row["scenario_id"],
                                     "stage_id": row["stage_id"], "sample_id": row["sample_id"],
                                     "prediction": row["parsed_response"]["actionable_tasks"][match["prediction_index"]],
                                     "annotation": match})
    return {"cases": cases, "false_positives": false_positives, "valid_extra_tasks": valid_extras,
            "counts": {c: sum(x["category"] == c for x in cases) for c in
            ("missing_annotation", "memory_incorrect", "reactive_incorrect", "core_gap", "all_correct")}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True)
    p.add_argument("--annotations", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--output", default="outputs/reports/failure_analysis.json")
    a = p.parse_args()
    read = lambda path: [json.loads(x) for x in Path(path).read_text().splitlines()]
    report = analyze(read(a.results), read(a.annotations), a.dataset)
    path = Path(a.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
