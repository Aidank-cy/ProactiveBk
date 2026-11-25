"""Fixed-data controls; these tests do not call a model API."""
import json
from collections import Counter
from pathlib import Path

import jsonschema
import pytest

from evaluation.context_builder import build_context
from evaluation.data.scenarios.materialize import BUILDERS, HERE, SOURCE
from evaluation.dataset_loader import load_dataset
from evaluation.integrity import check_pair
from evaluation.runner import requests_for


def test_generated_files_schema_sources_and_transitions():
    schema = json.loads((HERE.parent / "schema.json").read_text())
    scenarios = load_dataset(HERE / "all_scenarios.json")
    assert len(scenarios) == 4
    source_root = HERE.parents[3] / "VibeLifeBench" / "eval_set"
    for builder, scenario in zip(BUILDERS, scenarios):
        generated, audit = builder()
        assert generated == scenario
        assert generated == load_dataset(HERE / f"{scenario['scenario_id']}.json")[0]
        jsonschema.validate(generated, schema)
        assert len(scenario["events"]) + 1 == len(scenario["evaluations"])
        assert all((source_root / ref.split(":")[0]).exists()
                   for item in audit["initial"] + audit["events"] for ref in item["origin"])
        for event in scenario["events"]:
            assert not any(label in event["content"] for label in
                           ('"task_registry"', 'ready_tasks', 'newly_ready_tasks', 'ground_truth_answer'))
        previous = set()
        for stage in scenario["evaluations"]:
            ready = set(stage["ready_tasks"])
            assert set(stage["newly_ready_tasks"]) == ready - previous
            assert set(stage["invalidated_tasks"]) == previous - ready
            previous = ready
    assert {s["scenario_id"] for s in scenarios} == set(SOURCE)


def test_all_requests_share_stage_context_and_have_no_future_event():
    scenarios = load_dataset(HERE / "all_scenarios.json")
    config = {"models": ["mock/toy"], "num_samples": 1,
              "model_parameters": {"temperature": 0, "top_p": None,
                                   "max_output_tokens": 1024, "seed": None}}
    rows = list(requests_for(scenarios, config))
    assert len(rows) == 2616
    assert Counter(r["evaluation_type"] for r in rows) == {
        "memory": 2205, "reactive": 330, "proactive": 81}
    check_pair([{**r, "model_parameters": config["model_parameters"]} for r in rows])
    for scenario in scenarios:
        by_stage = [r for r in rows if r["scenario_id"] == scenario["scenario_id"]]
        for stage in scenario["evaluations"]:
            scoped = [r for r in by_stage if r["stage_id"] == stage["stage_id"]]
            context, digest = build_context(scenario, stage)
            assert {r["context_hash"] for r in scoped} == {digest}
            assert all(r["shared_context"] == context for r in scoped)
            assert all(len(r["input_messages"]) == 2 for r in scoped)
            assert all(r["task_id"] is None for r in scoped if r["evaluation_type"] == "proactive")
            assert all("task_registry" not in r["input_prompt"] for r in scoped)
            assert len(context["records"]) == len(scenario["initial_context"]) + int(stage["stage_id"][1:])


def test_loader_rejects_bidirectional_readiness_violation(tmp_path):
    scenario = json.loads((HERE / "rental.json").read_text())
    stage = scenario["evaluations"][4]
    assert "rental_t1" in stage["ready_tasks"]
    stage["ready_tasks"].remove("rental_t1")
    stage["newly_ready_tasks"].remove("rental_t1")
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(scenario))
    with pytest.raises(ValueError, match="ready tasks and condition states disagree"):
        load_dataset(path)
