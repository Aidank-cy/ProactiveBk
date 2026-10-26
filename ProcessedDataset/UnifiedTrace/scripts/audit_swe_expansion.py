#!/usr/bin/env python3
"""Check that sampled SWE main records expand without block loss or reordering."""
import collections
import json
from pathlib import Path

from swe_format import signature
from swe_chat_adapter import convert, records, dumps
from swe_record_policy import (
    claude_human_user_record,
    codex_injected_user_content,
    codex_user_body_without_auxiliary,
    droid_injected_user_record,
    droid_reminder_block,
    opencode_auxiliary_user_part,
    opencode_user_text_without_auxiliary,
    pi_human_user_message,
    skip_supplementary_record,
)


ROOT = Path(__file__).resolve().parents[3] / "OriginalDataset-filter-1k" / "SWE-Chat-filter-1k"
OUTPUT = Path(__file__).resolve().parents[1] / "swe_expansion_audit.json"


def expected_blocks(fmt, raw):
    if not isinstance(raw, dict):
        return None
    if fmt in ("claude_tree", "cursor_messages", "pi_tree", "factory_droid"):
        msg = raw.get("message")
        if not isinstance(msg, dict):
            return None
        if fmt == "claude_tree" and raw.get("type") not in ("assistant", "user", "tool_use", "tool_result"):
            return None
        if fmt == "cursor_messages" and raw.get("role") not in ("assistant", "user"):
            return None
        if fmt in ("pi_tree", "factory_droid") and msg.get("role") not in ("assistant", "user"):
            return None
        blocks=msg.get("content")
        if not isinstance(blocks,list) or not blocks:return None
        if fmt=="claude_tree" and raw.get("type")=="user" and not claude_human_user_record(raw):
            return []
        if fmt=="pi_tree" and msg.get("role")=="user" and not pi_human_user_message(msg):
            return []
        if fmt=="factory_droid" and msg.get("role")=="user":
            if droid_injected_user_record(raw.get("id"),blocks,msg.get("visibility")):return []
            feedback=any(isinstance(block,dict) and block.get("type") in ("tool_result","advisor_tool_result") for block in blocks)
            if not feedback:
                return [i for i,block in enumerate(blocks) if not droid_reminder_block(block)]
        return list(range(len(blocks)))
    if fmt == "codex_rollout" and raw.get("type") == "response_item":
        pay = raw.get("payload") or raw.get("item") or {}
        if pay.get("type") == "message" and pay.get("role") in ("assistant", "user"):
            blocks=pay.get("content")
            if not isinstance(blocks,list) or not blocks:return None
            if pay.get("role")=="user":
                runtime=codex_injected_user_content(blocks)
                return [i for i,block in enumerate(blocks) if codex_user_body_without_auxiliary(
                    (block.get("text") if block.get("type") in ("text","input_text","output_text") and isinstance(block.get("text"),str)
                     else dumps(block)) if isinstance(block,dict) else block,runtime) is not None]
            return list(range(len(blocks)))
    if fmt == "opencode_document" and isinstance(raw.get("parts"), list) and raw["parts"]:
        user=(raw.get("info") or {}).get("role")=="user"
        return [i for i,part in enumerate(raw["parts"]) if not (user and isinstance(part,dict) and (
                opencode_auxiliary_user_part(part) or
                part.get("type")=="text" and opencode_user_text_without_auxiliary(part.get("text")) is None))]
    return None


def main():
    selected = json.loads((ROOT / "sample_manifest.json").read_text())["selected"]
    counts = collections.Counter()
    errors = []
    for item in selected:
        path = ROOT / item["transcript_path"]
        fmt = signature(path)
        raw = {index: record for index, record, _ in records(path)}
        events, issues, _ = convert(path, "audit")
        grouped = collections.defaultdict(list)
        grouped_events = collections.defaultdict(list)
        previous_raw = None
        for expected_id, event in enumerate(events):
            if event["event_id"] != expected_id:
                errors.append({"session_id": item["session_id"], "reason": "nonsequential_event_id", "event_id": event["event_id"]})
            meta = json.loads(event["metadata"])
            index = meta["raw_record_index"]
            if previous_raw is not None and index < previous_raw:
                errors.append({"session_id": item["session_id"], "reason": "raw_record_reordered", "raw_record_index": index})
            previous_raw = index
            grouped[index].append(meta)
            grouped_events[index].append(event)
        for index, record in raw.items():
            if isinstance(record, dict) and skip_supplementary_record(record):
                counts["explicit_subagent_records_skipped"] += 1
                if grouped.get(index):
                    errors.append({"session_id": item["session_id"], "reason": "subagent_record_emitted", "raw_record_index": index})
                continue
            expected_indices = expected_blocks(fmt, record)
            if expected_indices is None:
                continue
            counts["list_content_records"] += 1
            metas = grouped.get(index, [])
            observed = []
            for meta in metas:
                if "user_block_indices" in meta:
                    observed.extend(meta["user_block_indices"])
                elif "user_part_indices" in meta:
                    observed.extend(meta["user_part_indices"])
                else:
                    observed.append(meta.get("block_index", meta.get("part_index")))
            if observed != sorted(observed) or set(observed) != set(expected_indices):
                errors.append({"session_id": item["session_id"], "reason": "content_block_missing_or_reordered", "raw_record_index": index, "expected_indices": expected_indices[:30], "observed_indices": observed[:30]})
            if len(metas) > len(expected_indices):
                counts["split_content_records"] += 1
            counts["content_blocks_checked"] += len(expected_indices)
            for event, meta in zip(grouped_events.get(index, []), metas):
                user_indices = meta.get("user_block_indices", meta.get("user_part_indices"))
                if user_indices is None:
                    continue
                if "user_part_indices" in meta:
                    source_parts = record.get("parts") or []
                elif fmt == "codex_rollout":
                    source_parts = (record.get("payload") or record.get("item") or {}).get("content") or []
                else:
                    source_parts = (record.get("message") or {}).get("content") or []
                selected_parts = [source_parts[i] for i in user_indices]
                only = selected_parts[0] if len(selected_parts) == 1 else None
                expected_body = (
                    only["text"] if isinstance(only, dict) and only.get("type") in
                    ("text", "input_text", "output_text") and isinstance(only.get("text"), str)
                    else only if isinstance(only, str) else dumps(only) if len(selected_parts) == 1
                    else dumps(selected_parts)
                )
                counts["consolidated_user_messages_checked"] += 1
                if event["role"] != "user" or event["event_type"] != "user_message" or event["content"] != expected_body:
                    errors.append({"session_id": item["session_id"], "reason": "consolidated_user_content_differs",
                                   "raw_record_index": index})
        counts[f"sessions_{fmt}"] += 1
        counts["events_checked"] += len(events)
    report = {"sample_sessions": len(selected), "counts": dict(counts), "errors": errors[:100], "error_count": len(errors),
              "note": "Explicit source content lists are checked for block order and coverage. Grouped object fields without a source sequence are not asserted to be chronological."}
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"sample_sessions": len(selected), "counts": dict(counts), "error_count": len(errors)}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
