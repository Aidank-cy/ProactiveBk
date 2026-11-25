"""Dataset validation; labels stay outside model-visible context."""
import json
from datetime import datetime
from pathlib import Path


def load_dataset(path):
    data = json.loads(Path(path).read_text())
    scenarios = data if isinstance(data, list) else data.get("scenarios", [data])
    for s in scenarios:
        for key in ("scenario_id", "initial_context", "events", "task_registry", "evaluations"):
            if key not in s:
                raise ValueError(f"scenario missing {key}")
        event_ids = [e["event_id"] for e in s["events"]]
        record_ids = [r["record_id"] for r in s["initial_context"]]
        task_ids = {t["task_id"] for t in s["task_registry"]}
        if len(event_ids) != len(set(event_ids)) or len(task_ids) != len(s["task_registry"]) or len(record_ids + event_ids) != len(set(record_ids + event_ids)):
            raise ValueError("duplicate record, event, or task ID")
        timestamps = [r["timestamp"] for r in s["initial_context"]] + [e["timestamp"] for e in s["events"]]
        parsed_times = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in timestamps]
        if any(t.tzinfo is None for t in parsed_times) or parsed_times != sorted(parsed_times):
            raise ValueError("timestamps must be timezone-aware and chronological")
        previous = set()
        for i, stage in enumerate(s["evaluations"]):
            for key in ("stage_id", "after_event_id", "memory_questions", "reactive_questions",
                        "ready_tasks", "newly_ready_tasks", "invalidated_tasks", "task_states"):
                if key not in stage:
                    raise ValueError(f"stage {i} missing {key}")
            expected = None if i == 0 else event_ids[i - 1]
            if stage["after_event_id"] != expected:
                raise ValueError("stages must be stage 0 then one per event in event order")
            ready = set(stage["ready_tasks"])
            if not ready <= task_ids or not set(stage["newly_ready_tasks"]) <= ready:
                raise ValueError("unknown or inconsistent ready task")
            if set(stage["newly_ready_tasks"]) != ready - previous:
                raise ValueError("newly_ready_tasks must equal transitions to ready")
            if not set(stage["invalidated_tasks"]) <= previous - ready:
                raise ValueError("invalidated_tasks must leave ready set")
            for t in s["task_registry"]:
                state = stage["task_states"].get(t["task_id"])
                if not state or not all(v in ("Satisfied", "Unsatisfied", "Unknown") for v in state.values()):
                    raise ValueError("each task needs condition states")
                if t["task_id"] in ready and (set(state) != set(t["conditions"]) or any(v != "Satisfied" for v in state.values())):
                    raise ValueError("ready task has incomplete conditions")
            for q in stage["memory_questions"]:
                if not set(q["task_ids"]) <= task_ids or not q.get("question_id") or not q.get("question") or "ground_truth_answer" not in q:
                    raise ValueError("invalid memory question")
            if not set(stage["reactive_questions"]) <= task_ids:
                raise ValueError("unknown reactive task")
            previous = ready
        if len(s["evaluations"]) != len(event_ids) + 1:
            raise ValueError("one evaluation stage is required per event, plus stage 0")
    return scenarios
