#!/usr/bin/env python3
"""Inspect real local WildChat and SWE-chat parquet files without loading whole datasets.

Install: pip install pyarrow
Run: python inspect_original_trace_schema.py --root /home/data/hzd/ProactiveBk/OriginalDataset
Optional: --show-content to include short raw text previews in the report.
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq
except ImportError:
    sys.exit("pyarrow is required: pip install pyarrow")


def find_one(root, name, path_hint=None):
    files = sorted(root.rglob(name))
    if path_hint:
        hinted = [p for p in files if path_hint.lower() in str(p).lower()]
        if hinted:
            files = hinted
    return files[0] if files else None


def first_record(path):
    if not path:
        return None
    for batch in pq.ParquetFile(path).iter_batches(batch_size=1):
        values = batch.to_pylist()
        if values:
            return values[0]
    return None


def preview_content(value, allow_text):
    if value is None:
        return {"length": 0, "preview": None}
    text = str(value)
    return {"length": len(text), "preview": text[:160] if allow_text else "[hidden; use --show-content]"}


def compact_record(rec, allow_text, keys):
    if rec is None:
        return None
    obj = {}
    for key in keys:
        if key not in rec:
            continue
        val = rec[key]
        if key in {"content", "tool_input_json", "summary_intent", "summary_outcome"}:
            obj[key] = preview_content(val, allow_text)
        elif key in {"hashed_ip", "header", "user_id", "owner_id"}:
            continue
        else:
            obj[key] = val
    return obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/home/data/hzd/ProactiveBk/OriginalDataset")
    ap.add_argument("--show-content", action="store_true")
    ap.add_argument("--out", default="original_trace_schema_report.json")
    args = ap.parse_args()
    root = Path(args.root)
    if not root.exists():
        sys.exit(f"Data directory not found: {root}")

    out = {"root": str(root), "file_schema": {}, "samples": {}, "warnings": []}
    wild = find_one(root, "train-*.parquet", "wildchat")
    if wild is None:
        wild = find_one(root, "*.parquet", "wildchat")
    if wild:
        out["file_schema"]["wildchat"] = {"path": str(wild), "arrow_schema": str(pq.read_schema(wild))}
        row = first_record(wild)
        if row:
            out["samples"]["wildchat"] = {
                "top_level_field_names": list(row.keys()),
                "metadata": compact_record(row, args.show_content,
                    ["conversation_hash", "model", "timestamp", "turn", "language", "toxic", "redacted"]),
                "messages": [compact_record(m, args.show_content,
                    ["role", "turn_identifier", "content", "timestamp", "created", "language", "redacted", "toxic", "openai_id", "token_counter", "temperature", "top_p"])
                    for m in (row.get("conversation") or [])[:6]],
                "nested_message_field_names": list((row.get("conversation") or [{}])[0].keys())
            }
    else:
        out["warnings"].append("WildChat parquet not found under the root")

    conv = find_one(root, "conversations.parquet", "swe")
    sessions = find_one(root, "sessions.parquet", "swe")
    logs = find_one(root, "session_logs.parquet", "swe")
    for label, path in [("swe_conversations", conv), ("swe_sessions", sessions), ("swe_session_logs", logs)]:
        if path:
            out["file_schema"][label] = {"path": str(path), "arrow_schema": str(pq.read_schema(path))}
        else:
            out["warnings"].append(label + " not found")

    if conv:
        row = first_record(conv)
        if row:
            sess_id = row.get("session_id")
            out["samples"]["swe_first_conversation_row"] = compact_record(row, args.show_content,
                ["turn_id", "session_id", "turn_number", "conversation_turn_number", "role", "turn_type", "is_conversational", "content", "model", "timestamp", "tool_name", "tool_call_id", "tool_input_json", "prompt_intent", "prompt_pushback", "queue_op_subtype", "source_entry_uuid", "response_id", "content_block_index"])
            selected = ["session_id", "turn_number", "role", "turn_type", "content", "tool_name", "tool_call_id", "is_conversational"]
            available = set(pq.read_schema(conv).names)
            selected = [c for c in selected if c in available]
            events = []
            try:
                scanner = ds.dataset(str(conv), format="parquet").scanner(
                    columns=selected, filter=ds.field("session_id") == sess_id, batch_size=1024
                )
                for batch in scanner.to_batches():
                    for ev in batch.to_pylist():
                        events.append(compact_record(ev, args.show_content, selected))
                events.sort(key=lambda ev: (ev.get("turn_number") if ev.get("turn_number") is not None else -1))
                out["samples"]["swe_first_session_events"] = {
                    "session_id": sess_id, "matched_events": len(events), "first_16_events": events[:16]
                }
            except Exception as e:
                out["warnings"].append("Unable to scan one SWE session: " + repr(e))
    if sessions:
        row = first_record(sessions)
        out["samples"]["swe_first_session_metadata"] = compact_record(row, args.show_content,
            ["session_id", "repo_id", "agent", "model", "created_at", "turn_count", "prompt_count", "tool_call_count", "session_success", "summary_intent", "summary_outcome", "summary_open_items", "transcript_path"])
    if logs:
        row = first_record(logs)
        out["samples"]["swe_first_session_log_pointer"] = compact_record(row, args.show_content,
            ["session_id", "transcript_path", "compact_transcript_path"])

    out_path = Path(args.out)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {out_path.resolve()}")
    for key, v in out["file_schema"].items():
        print(f"{key}: {v['path']}")
    if out["warnings"]:
        print("Warnings:")
        for w in out["warnings"]:
            print(" -", w)


if __name__ == "__main__":
    main()
