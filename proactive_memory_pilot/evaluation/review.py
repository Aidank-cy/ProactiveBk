"""Prepare blinded annotation templates. Fill labels manually; no LLM judge."""
import argparse
import json
from pathlib import Path
from .dataset_loader import load_dataset


def call_id(row):
    import hashlib
    fields = [row.get(k) for k in ("run_id", "model_name", "scenario_id", "stage_id", "evaluation_type", "question_id", "task_id", "sample_id")]
    return hashlib.sha256(json.dumps(fields).encode()).hexdigest()[:20]


def make_review(results, dataset):
    lookup = {(s["scenario_id"], st["stage_id"]): (s, st) for s in load_dataset(dataset) for st in s["evaluations"]}
    out = []
    latest = {call_id(row): row for row in results}
    for row in latest.values():
        s, st = lookup[(row["scenario_id"], row["stage_id"])]
        common = {"call_id": call_id(row), "scenario_id": row["scenario_id"], "stage_id": row["stage_id"],
                  "evaluation_type": row["evaluation_type"], "status": row["status"]}
        if row["evaluation_type"] == "memory":
            q = next(q for q in st["memory_questions"] if q["question_id"] == row["question_id"])
            out.append({**common, "question_id": q["question_id"], "question": q["question"],
                        "task_ids": q["task_ids"], "ground_truth_answer": q["ground_truth_answer"],
                        "model_answer": (row.get("parsed_response") or {}).get("answer"),
                        "correct": None, "comment": ""})
        else:
            tasks = [{k: t[k] for k in ("task_id", "description", "matching_guidelines")} for t in s["task_registry"]]
            predictions = (row.get("parsed_response") or {}).get("actionable_tasks", [])
            out.append({**common, "task_id": row["task_id"], "ready_tasks": st["ready_tasks"],
                        "task_registry": tasks, "predictions": predictions,
                        "matches": [{"prediction_index": i, "matched_task_id": None, "match_status": None,
                                     "evidence_correct": None, "comment": ""} for i in range(len(predictions))],
                        "comment": ""})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--output", default="outputs/human_annotations/review.jsonl")
    a = p.parse_args()
    rows = [json.loads(x) for x in Path(a.results).read_text().splitlines()]
    review = make_review(rows, a.dataset)
    path = Path(a.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in review))
    print(f"Wrote {len(review)} blinded records to {path}")


if __name__ == "__main__":
    main()
