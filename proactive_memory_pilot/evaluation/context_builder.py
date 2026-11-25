"""Deterministic, stage limited history construction."""
import hashlib
import json


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_context(scenario, stage):
    events = scenario["events"]
    cutoff = -1 if stage["after_event_id"] is None else next(
        i for i, e in enumerate(events) if e["event_id"] == stage["after_event_id"])
    records = []
    for r in scenario["initial_context"]:
        records.append({k: r[k] for k in ("record_id", "timestamp", "source", "content")})
    for e in events[:cutoff + 1]:
        records.append({"record_id": e["event_id"], **{k: e[k] for k in ("timestamp", "source", "content")}})
    now = records[-1]["timestamp"] if records else stage.get("timestamp")
    if not now:
        raise ValueError("stage requires simulated time")
    context = {"simulated_now": now, "records": records}
    return context, hashlib.sha256(canonical(context).encode()).hexdigest()
