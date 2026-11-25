"""Fixed-data controls; these tests do not call a model API."""
import json
import os
from datetime import datetime
from collections import Counter
from pathlib import Path

import jsonschema
import pytest

from evaluation.context_builder import build_context
from evaluation.data.scenarios.materialize import BUILDERS, HERE, SOURCE
from evaluation.dataset_loader import load_dataset
from evaluation.integrity import check_pair
from evaluation.runner import requests_for
from evaluation.data.scenarios.materialize import statistics
from evaluation.data.scenarios.coupon_math import audit as coupon_audit
from evaluation.data.scenarios.grounding import grounded_stage


def test_generated_files_schema_sources_and_transitions():
    schema = json.loads((HERE.parent / "schema.json").read_text())
    scenarios = load_dataset(HERE / "all_scenarios.json")
    assert len(scenarios) == 4
    source_root = Path(os.environ.get("VIBELIFE_ROOT", HERE.parents[3] / "VibeLifeBench")) / "eval_set"
    for builder, scenario in zip(BUILDERS, scenarios):
        generated, audit = builder()
        assert generated == scenario
        assert generated == load_dataset(HERE / f"{scenario['scenario_id']}.json")[0]
        jsonschema.validate(generated, schema)
        assert len(scenario["events"]) + 1 == len(scenario["evaluations"])
        if source_root.exists():
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
    assert len(rows) == sum(statistics(s)["total_calls_per_model_sample"] for s in scenarios)
    assert len(rows) == 2923
    assert Counter(r["evaluation_type"] for r in rows) == {
        "memory": 2480, "reactive": 359, "proactive": 84}
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


def test_semantic_grounding_time_and_coupon_arithmetic():
    for builder in BUILDERS:
        scenario, metadata = builder()
        for stage, meta in zip(scenario["evaluations"], metadata["grounding"]):
            audit = grounded_stage(scenario, stage, meta)
            assert all(audit["tasks"][tid]["supporting_record_ids"] for tid in stage["ready_tasks"])
            assert all(set(entry["evidence_record_ids"]) <= {
                r.get("record_id", r.get("event_id")) for r in scenario["initial_context"] + scenario["events"][:int(stage["stage_id"][1:])]
            } for entry in audit["memory"].values())
            for expiry in meta["time_expirations"]:
                assert datetime.fromisoformat(meta["simulated_now"]) >= datetime.fromisoformat(expiry["cutoff"])
                assert stage["task_states"][expiry["task_id"]][expiry["condition"]] != "Satisfied"
    rental = load_dataset(HERE / "rental.json")[0]
    assert "rental_t1" in rental["evaluations"][14]["ready_tasks"]
    assert "rental_t1" not in rental["evaluations"][15]["ready_tasks"]
    travel = load_dataset(HERE / "travel.json")[0]
    assert "travel_t1" in travel["evaluations"][8]["ready_tasks"]
    assert "travel_t1" not in travel["evaluations"][9]["ready_tasks"]
    shopping = load_dataset(HERE / "shopping.json")[0]
    assert "shopping_t2" in shopping["evaluations"][14]["ready_tasks"]
    assert "shopping_t2" not in shopping["evaluations"][15]["ready_tasks"]
    assert "shopping_t1" not in shopping["evaluations"][16]["ready_tasks"]
    team = load_dataset(HERE / "team_building.json")[0]
    assert "team_t1" in team["evaluations"][16]["ready_tasks"]
    assert "team_t1" not in team["evaluations"][17]["ready_tasks"]
    plan = coupon_audit()
    assert plan["combination_count"] == 18
    assert plan["best"]["sku_ids"] == ["bsk_strr_a2", "bsk_strr_b2", "bsk_strr_c2"]
    assert plan["best"]["total_minor"] == 14630


def test_quoted_budget_and_rental_threshold_arithmetic():
    assert 3180 + 7 * 241 + 175 + 900 == 5942 < 6800
    assert 18000 + 3520 + 12800 + 11880 + 1760 == 47960 < 56000
    assert 5950 <= 6000 and 5900 <= 6000
    assert 38 <= 45 and 39 <= 45
    assert 51 > 45  # weekend detour is not the post-start daily route


def test_coupon_result_matches_original_mall_optimizer():
    source_root = Path(os.environ.get("VIBELIFE_ROOT", HERE.parents[3] / "VibeLifeBench"))
    if not source_root.exists():
        pytest.skip("local VibeLifeBench source absent")
    import sys
    from datetime import date
    sys.path.insert(0, str(source_root))
    from lib.ecommerce_cart_optimizer import optimal_cart_plans
    seed = source_root / "eval_set/shopping/baby_stroller_safety_standard_30d/envs/ecommerce/baby_stroller_safety_standard_30d/init.sql"
    original = optimal_cart_plans(seed, "bsk_strr_", date(2026, 6, 23))
    best = coupon_audit()["best"]
    assert original[0].total_minor == best["total_minor"]
    assert set(original[0].sku_ids) == set(best["sku_ids"])
    assert set(original[0].coupon_codes) == set(best["coupon_codes"])
