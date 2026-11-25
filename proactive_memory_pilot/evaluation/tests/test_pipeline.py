import json
from pathlib import Path
import pytest

from evaluation.context_builder import build_context
from evaluation.dataset_loader import load_dataset
from evaluation.metrics import score
from evaluation.review import call_id, make_review
from evaluation.runner import run
from evaluation.integrity import check_pair, check_request


def fixture(tmp_path):
    tasks = [
        {"task_id": "t1", "description": "Place blue token in box A.", "goal": "Sort blue token",
         "conditions": ["authorized", "available"], "required_memory_facts": ["a1", "v1"],
         "matching_guidelines": "Must specify blue token and box A."},
        {"task_id": "t2", "description": "Place red token in box B.", "goal": "Sort red token",
         "conditions": ["authorized", "available"], "required_memory_facts": ["a2", "v2"],
         "matching_guidelines": "Must specify red token and box B."},
    ]
    events = [
        {"event_id": "e1", "timestamp": "2026-01-02T00:00:00Z", "source": "toy", "content": "Both tokens are now available; user authorizes placing both."},
        {"event_id": "e2", "timestamp": "2026-01-03T00:00:00Z", "source": "toy", "content": "Blue token placement is canceled."},
        {"event_id": "e3", "timestamp": "2026-01-04T00:00:00Z", "source": "toy", "content": "Red token placement is canceled."},
    ]
    stages = []
    for i in range(4):
        active = ["t1", "t2"] if i == 1 else ["t2"] if i == 2 else []
        qs = []
        for n in (1, 2):
            for prefix, phrase in (("a", "authorized"), ("v", "available")):
                qid = f"{prefix}{n}"
                qs.append({"question_id": qid, "question": f"Is token {n} {phrase}?",
                           "task_ids": [f"t{n}"], "ground_truth_answer": "yes" if f"t{n}" in active else
                           "unknown" if i == 0 and prefix == "v" else "no"})
        stages.append({"stage_id": f"s{i}", "after_event_id": None if i == 0 else events[i-1]["event_id"],
                       "memory_questions": qs, "reactive_questions": ["t1", "t2"], "ready_tasks": active,
                       "newly_ready_tasks": ["t1", "t2"] if i == 1 else [],
                       "invalidated_tasks": ["t1"] if i == 2 else ["t2"] if i == 3 else [],
                       "task_states": {t: {"authorized": "Satisfied" if t in active else "Unsatisfied",
                                           "available": "Satisfied" if t in active else "Unknown"} for t in ("t1", "t2")}})
    data = {"scenario_id": "toy", "initial_context": [{"record_id": "h0", "timestamp": "2026-01-01T00:00:00Z",
            "source": "toy", "content": "User wants blue token in box A and red token in box B once authorized and available."}],
            "events": events, "task_registry": tasks, "evaluations": stages}
    path = tmp_path / "toy.json"
    path.write_text(json.dumps(data))
    config = tmp_path / "config.yaml"
    config.write_text("models: [mock/toy]\nmodels_config_path: /dev/null\nnum_samples: 1\nconcurrency: 2\nretry: 0\n")
    return path, config


def mock(req, config):
    stage = req["stage_id"]
    if req["evaluation_type"] == "memory":
        tid = "t" + req["question_id"][-1]
        answer = "yes" if stage == "s1" or stage == "s2" and tid == "t2" else \
                 "unknown" if stage == "s0" and req["question_id"].startswith("v") else "no"
        raw = json.dumps({"answer": answer, "evidence": []})
    elif req["evaluation_type"] == "reactive":
        tid = req["task_id"]
        ready = (stage == "s1") or (stage == "s2" and tid == "t2")
        raw = json.dumps({"actionable_tasks": [{"description": "Place blue token in box A." if tid == "t1" else "Place red token in box B.", "evidence": []}] if ready else []})
    else:
        tasks = []
        if stage in ("s1", "s2"):
            tasks = [{"description": "Place red token in box B.", "evidence": []}]
        if stage == "s1":
            tasks += [{"description": "Place red token in box B.", "evidence": []},
                      {"description": "Place green token in box C.", "evidence": []}]
        raw = json.dumps({"actionable_tasks": tasks})
    return {"raw_response": raw, "input_tokens": 10, "output_tokens": 10, "harness_version": "mock"}


def labels(results, dataset):
    review = make_review(results, dataset)
    for a in review:
        if a["evaluation_type"] == "memory":
            a["correct"] = a["model_answer"] == a["ground_truth_answer"]
        else:
            for match, pred in zip(a["matches"], a["predictions"]):
                desc = pred["description"]
                if "green" in desc:
                    match.update(match_status="Unsupported Task")
                else:
                    tid = "t1" if "blue" in desc else "t2"
                    prior = any(m["matched_task_id"] == tid for m in a["matches"] if m is not match)
                    match.update(matched_task_id=tid, match_status="Duplicate" if prior else "Correct Match")
    return review


def test_pipeline(tmp_path):
    dataset, config = fixture(tmp_path)
    s = load_dataset(dataset)[0]
    assert len(build_context(s, s["evaluations"][0])[0]["records"]) == 1
    dry = run(config, dataset, dry_run=True)
    assert len(dry) == 4 * (4 + 2 + 1)
    assert all("task_registry" not in r["input_prompt"] for r in dry)
    assert all("e3" not in r["input_prompt"] for r in dry if r["stage_id"] != "s3")
    output = tmp_path / "raw.jsonl"
    rows = run(config, dataset, output=output, adapter=mock)
    assert len(rows) == 28
    assert len(run(config, dataset, output=output, resume=True, adapter=mock)) == 28
    report = score(rows, labels(rows, dataset), dataset)
    assert report["all_ready_proactive_gap"] == {"numerator": 1, "denominator": 3, "value": 1/3}
    assert report["newly_ready_proactive_gap"] == {"numerator": 1, "denominator": 2, "value": .5}
    assert report["counts"]["duplicates"] == 1
    assert report["counts"]["fp"] == 2
    assert report["rates"]["proactive_micro_recall"] == 2/3
    annotations = labels(rows, dataset)
    annotations[0]["correct"] = None
    incomplete = score(rows, annotations, dataset)
    assert incomplete["counts"]["memory_questions_missing"] == 1


def test_failures_and_zero_denominator(tmp_path):
    dataset, config = fixture(tmp_path)
    def broken(req, cfg):
        if req["evaluation_type"] == "memory":
            raise RuntimeError("api down")
        return {"raw_response": "not json", "harness_version": "mock"}
    rows = run(config, dataset, output=tmp_path / "raw.jsonl", adapter=broken)
    assert {r["status"] for r in rows} == {"api_error", "parsing_failure"}
    report = score(rows, [], dataset)
    assert report["rates"]["proactive_micro_precision"] is None
    assert report["all_ready_proactive_gap"]["value"] is None


def test_integrity_controls(tmp_path):
    dataset, config = fixture(tmp_path)
    scenario = load_dataset(dataset)[0]
    requests = run(config, dataset, dry_run=True)
    stage0 = scenario["evaluations"][0]
    req = next(r for r in requests if r["stage_id"] == "s0" and r["evaluation_type"] == "proactive")
    assert "Place blue token in box A." not in req["input_prompt"]
    assert "e1" not in req["input_prompt"]
    altered = {**req, "shared_context": {**req["shared_context"], "records": req["shared_context"]["records"] +
                 [{"record_id": "e1", "timestamp": "2026-01-02T00:00:00Z", "source": "toy", "content": "future"}]}}
    with pytest.raises(ValueError):
        check_request(altered, scenario, stage0)
    paired = [{**r, "model_parameters": {"temperature": 0}} for r in requests if r["stage_id"] == "s0"]
    paired[-1]["model_parameters"] = {"temperature": 1}
    with pytest.raises(ValueError):
        check_pair(paired)


def test_valid_extra_and_combined_task_prediction(tmp_path):
    dataset, config = fixture(tmp_path)
    rows = run(config, dataset, output=tmp_path / "raw.jsonl", adapter=mock)
    target = next(r for r in rows if r["stage_id"] == "s1" and r["evaluation_type"] == "proactive")
    target["parsed_response"]["actionable_tasks"] = [
        {"description": "Place blue token in box A and red token in box B.", "evidence": []},
        {"description": "Warn user about a separate valid issue.", "evidence": []}]
    annotations = labels(rows, dataset)
    ann = next(a for a in annotations if a["call_id"] == call_id(target))
    ann["matches"] = [
        {"prediction_index": 0, "matched_task_id": "t1", "match_status": "Correct Match"},
        {"prediction_index": 0, "matched_task_id": "t2", "match_status": "Correct Match"},
        {"prediction_index": 1, "matched_task_id": None, "match_status": "Valid Extra Task"}]
    report = score(rows, annotations, dataset)
    assert report["counts"]["valid_extra_tasks"] == 1
    assert report["counts"]["tp"] == 3
    assert report["counts"]["fp"] == 0
    assert report["rates"]["proactive_micro_precision"] == 1
    assert report["rates"]["proactive_open_precision"] == 1
