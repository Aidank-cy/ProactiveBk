"""Human-auditable condition → Memory fact → visible-record mapping."""
from __future__ import annotations

from datetime import datetime


def _rental(tid, code):
    common = {"goal": ["r_goal"], "open": [f"r_{code}_status"],
              "listing": [f"r_{code}_status"], "room": [f"r_{code}_type"],
              "budget": ["r_budget", f"r_{code}_price"],
              "commute": ["r_commute_limit", f"r_{code}_commute"],
              "registration": [f"r_{code}_reg"],
              "slot": ["r_weekend", "r_calendar", f"r_{code}_slot"],
              "authorized": ["r_auth"]}
    if code == "b":
        common["identity_risk"] = ["r_b_risk", "r_auth"]
    return common


CONDITION_QUESTIONS = {
    "rental_t1": _rental("rental_t1", "c"),
    "rental_t2": _rental("rental_t2", "a"),
    "rental_t3": _rental("rental_t3", "b"),
    "rental_t4": {"goal": ["r_contract_goal"], "open": ["r_contract_status"],
                  "owner": ["r_contract_owner"], "registration": ["r_c_reg"],
                  "deposit": ["r_contract_deposit"], "repair": ["r_contract_repair"],
                  "fee": ["r_contract_fee"], "authorized": ["r_auth"]},
    "travel_t1": {"goal": ["t_goal"], "open": ["t_flight_open"],
                  "inventory": ["t_flight_stock"], "transit": ["t_visa"],
                  "ticket": ["t_flight_ticket"],
                  "timing": ["t_dates", "t_deadline", "t_flight_time"],
                  "budget": ["t_budget", "t_flight_price", "t_hotel_price"],
                  "reversible": ["t_flight_hold"], "authorized": ["t_auth"]},
    "travel_t2": {"goal": ["t_goal"], "open": ["t_hotel_open"],
                  "dates": ["t_hotel_dates"], "inventory": ["t_hotel_stock"],
                  "location": ["t_hotel_place"],
                  "budget": ["t_budget", "t_flight_price", "t_hotel_price"],
                  "cancellation": ["t_hotel_cancel"], "authorized": ["t_auth"]},
    "travel_t3": {"goal": ["t_goal"], "open": ["t_transfer_open"],
                  "arrival": ["t_flight_time"], "route": ["t_transfer_route"],
                  "vendor": ["t_transfer_vendor"], "cost": ["t_transfer_cost"],
                  "deadline": ["t_deadline"], "authorized": ["t_auth"]},
    "travel_t4": {"goal": ["t_land_goal"], "open": ["t_land_open"],
                  "time": ["t_land_time"], "conditions": ["t_land_weather"],
                  "option": ["t_land_option"], "comfort": ["t_goal", "t_land_weather"]},
    "travel_t5": {"goal": ["t_goal"], "open": ["t_claim_return"],
                  "policy": ["t_claim_policy"], "settlement": ["t_claim_payment"],
                  "receipts": ["t_claim_receipts"], "trip_finished": ["t_claim_return"]},
    "shopping_t1": {"goal": ["s_ref_goal"], "open": ["s_ref_open"],
                    "case": ["s_ref_case"], "merchant_dispute": ["s_ref_case"],
                    "rule": ["s_ref_rule"], "photo": ["s_ref_photo"],
                    "video": ["s_ref_video"], "deadline": ["s_ref_rule"],
                    "authorized": ["s_auth"]},
    "shopping_t2": {"goal": ["s_sale_goal"], "open": ["s_sale_open"],
                    "listing": ["s_sale_listing"], "buyer": ["s_sale_buyer"],
                    "price": ["s_sale_price"], "time": ["s_sale_time"],
                    "platform": ["s_sale_platform"], "user_choice": ["s_sale_choice"]},
    "shopping_t3": {"goal": ["s_card_goal"], "open": ["s_card_status"],
                    "duplicate": ["s_card_pair"], "order_link": ["s_card_order"],
                    "documents": ["s_card_docs"], "authorized": ["s_auth"]},
    "shopping_t4": {"goal": ["s_stroller_goal"], "open": ["s_stroller_open"],
                    "batch": ["s_stroller_batch"], "official_policy": ["s_stroller_policy"],
                    "cost_cycle": ["s_stroller_cost"],
                    "travel_fit": ["s_stroller_travel", "s_deadline"],
                    "authorized": ["s_auth"]},
    "shopping_t5": {"goal": ["s_cart_goal"], "open": ["s_cart_status"],
                    "catalog": ["s_cart_catalog"], "stock": ["s_cart_stock"],
                    "coupon": ["s_cart_coupon"], "authorized": ["s_auth"]},
    "team_t1": {"goal": ["b_goal"], "open": ["b_factory_open"],
                "count": ["b_count"], "capacity": ["b_factory_stock"],
                "security": ["b_factory_security"], "ppe": ["b_factory_ppe"],
                "special_needs": ["b_factory_needs"],
                "cancellation": ["b_factory_cancel"], "hold_terms": ["b_factory_hold"],
                "budget": ["b_budget", "b_factory_quote", "b_bus_quote", "b_lunch_quote"],
                "authorized": ["b_auth"]},
    "team_t2": {"goal": ["b_goal"], "open": ["b_bus_open"],
                "capacity": ["b_count", "b_bus_quote"],
                "driver": ["b_bus_driver", "b_bus_needs"],
                "route_time": ["b_bus_schedule"], "price": ["b_bus_quote"],
                "invoice": ["b_bus_invoice"],
                "budget": ["b_budget", "b_factory_quote", "b_bus_quote", "b_lunch_quote"],
                "special_needs": ["b_bus_needs"]},
    "team_t3": {"goal": ["b_goal"], "open": ["b_lunch_open"],
                "count": ["b_count"], "menu": ["b_lunch_menu"],
                "needs": ["b_factory_needs", "b_lunch_menu"],
                "capacity_price": ["b_lunch_quote"], "invoice": ["b_lunch_invoice"],
                "schedule": ["b_lunch_time"],
                "budget": ["b_budget", "b_factory_quote", "b_bus_quote", "b_lunch_quote"]},
    "team_t4": {"goal": ["b_notice_goal"], "open": ["b_notice_open"],
                "time": ["b_notice_time"],
                "route": ["b_notice_route", "b_bus_schedule", "b_lunch_time"],
                "safety": ["b_notice_rules"], "needs": ["b_factory_needs"],
                "standing_language": ["b_notice_access"], "authorized": ["b_auth"]},
    "team_t5": {"goal": ["b_goal"], "open": ["b_finance_open"],
                "finished": ["b_finance_finished"], "transactions": ["b_finance_tx"],
                "invoices": ["b_finance_invoice", "b_bus_invoice", "b_lunch_invoice"],
                "other_costs_status": ["b_finance_other"], "policy": ["b_finance_rule"]},
}


def grounded_stage(scenario, stage, stage_meta):
    """Derive a reviewer-only evidence chain from currently visible records."""
    cutoff = int(stage["stage_id"][1:])
    visible = scenario["initial_context"] + scenario["events"][:cutoff]
    visible_ids = {r.get("record_id", r.get("event_id")) for r in visible}
    questions = {q["question_id"]: q for q in stage["memory_questions"]}
    output = {"stage_id": stage["stage_id"], "current_event_id": stage["after_event_id"],
              "current_event_content": scenario["events"][cutoff - 1]["content"] if cutoff else None,
              "simulated_now": stage_meta["simulated_now"],
              "active_user_goals": list(stage["reactive_questions"]),
              "ready_tasks": stage["ready_tasks"], "newly_ready_tasks": stage["newly_ready_tasks"],
              "tasks_leaving_ready": stage["invalidated_tasks"], "memory": {}, "tasks": {}}
    for qid, q in questions.items():
        ids = q["evidence_record_ids"]
        if not set(ids) <= visible_ids:
            raise ValueError(f"future evidence in {scenario['scenario_id']} {stage['stage_id']} {qid}")
        if q["ground_truth_answer"] != "unknown" and not ids:
            raise ValueError(f"ungrounded answer in {scenario['scenario_id']} {stage['stage_id']} {qid}")
        output["memory"][qid] = {"answer": q["ground_truth_answer"], "evidence_record_ids": ids}
    for task in scenario["task_registry"]:
        tid = task["task_id"]
        mapping = CONDITION_QUESTIONS[tid]
        if set(mapping) != set(task["conditions"]):
            raise ValueError(f"condition mapping incomplete: {tid}")
        if not set(qid for ids in mapping.values() for qid in ids) <= set(task["required_memory_facts"]):
            raise ValueError(f"required memory facts missing a condition: {tid}")
        active = tid in stage["reactive_questions"]
        conditions = {}
        for condition, qids in mapping.items():
            state = stage["task_states"][tid][condition]
            facts = {qid: questions[qid]["ground_truth_answer"] for qid in qids if qid in questions}
            ids = sorted({rid for qid in facts for rid in questions[qid]["evidence_record_ids"]})
            if active and state == "Satisfied" and (len(facts) != len(qids) or any(v == "unknown" for v in facts.values())):
                raise ValueError(f"satisfied condition lacks factual input: {tid} {stage['stage_id']} {condition}")
            conditions[condition] = {"state": state, "memory_question_ids": qids,
                                     "evidence_record_ids": ids,
                                     "explanation": ("Current visible facts: " + "; ".join(f"{k}={v}" for k, v in facts.items())) if facts else "Goal not yet active; no question exposed.",
                                     "missing_fact": " or ".join(qid for qid in qids if qid not in facts or facts[qid] == "unknown") if state == "Unknown" else None,
                                     "temporal_proof": [x for x in stage_meta["time_expirations"] if x["task_id"] == tid and x["condition"] == condition]}
        supporting = sorted({rid for x in conditions.values() if x["state"] == "Satisfied" for rid in x["evidence_record_ids"]})
        state_map = stage["task_states"][tid]
        constraints = [v for key, v in state_map.items() if key not in ("goal", "open", "authorized")]
        readiness_checks = {
            "goal_expressed": state_map.get("goal") == "Satisfied",
            "action_still_needed": state_map.get("open") == "Satisfied",
            "factual_inputs_known": all(v != "Unknown" for v in constraints),
            "constraints_satisfied": all(v == "Satisfied" for v in constraints),
            "authorization_in_scope": state_map.get("authorized") == "Satisfied" if "authorized" in state_map else None,
            "time_valid_by_stage_labels": all(state_map[key] == "Satisfied" for key in ("slot", "time", "deadline", "hold_terms", "travel_fit") if key in state_map),
            "gt_matches_condition_states": (tid in stage["ready_tasks"]) == all(v == "Satisfied" for v in state_map.values()),
        }
        output["tasks"][tid] = {"ready": tid in stage["ready_tasks"], "conditions": conditions,
                                "readiness_checks": readiness_checks,
                                "supporting_record_ids": supporting if tid in stage["ready_tasks"] else [],
                                "remaining_ambiguities": [f"{c}: {x['missing_fact'] or x['explanation']}" for c, x in conditions.items() if x["state"] == "Unknown"]}
        if not set(supporting) <= visible_ids:
            raise ValueError(f"future task evidence: {tid} {stage['stage_id']}")
    return output
