#!/usr/bin/env python3
"""Compare SWE auxiliary event order and payloads against sampled main logs."""

import collections
import json
from pathlib import Path

from swe_chat_adapter import content, convert, dumps, records


ROOT = Path(__file__).resolve().parents[3] / "OriginalDataset-filter-1k" / "SWE-Chat-filter-1k"
AUXILIARY_TYPES = {"system_event", "metadata_event", "queue_event"}


def source_payloads(record, metadata):
    """Enumerate raw payloads an auxiliary event can faithfully carry."""
    if not isinstance(record, dict):
        return {content(record)}
    payloads = {dumps(record)}
    if "_unparsed_line" in record:
        payloads.add(record["_unparsed_line"])
    for key in ("content", "data"):
        if key in record:
            payloads.add(content(record[key]))
    message = record.get("message")
    if isinstance(message, dict):
        blocks = message.get("content")
        if blocks is not None:
            payloads.add(content(blocks))
        index = metadata.get("block_index")
        if isinstance(blocks, list) and isinstance(index, int) and index < len(blocks):
            block = blocks[index]
            payloads.add(content(block))
            if isinstance(block, dict) and "text" in block:
                payloads.add(content(block["text"]))
    payload = record.get("payload") or record.get("item")
    if isinstance(payload, dict) and "content" in payload:
        payloads.add(content(payload["content"]))
        blocks = payload["content"]
        index = metadata.get("block_index")
        if isinstance(blocks, list) and isinstance(index, int) and index < len(blocks):
            payloads.add(content(blocks[index]))
    parts = record.get("parts")
    index = metadata.get("part_index")
    if isinstance(parts, list) and isinstance(index, int) and index < len(parts):
        part = parts[index]
        payloads.add(content(part))
        if isinstance(part, dict) and "text" in part:
            payloads.add(content(part["text"]))
    update = (record.get("params") or {}).get("update")
    if isinstance(update, dict):
        payloads.add(dumps(update))
    if record.get("event") in ("Stop", "StopCancelled") and "last_assistant_message" in record:
        payloads.add(dumps({k: v for k, v in record.items() if k != "last_assistant_message"}))
    return payloads


def main():
    selected = json.loads((ROOT / "sample_manifest.json").read_text())["selected"]
    checked = collections.Counter()
    errors = []
    for item in selected:
        path = ROOT / item["transcript_path"]
        raw = {index: record for index, record, _ in records(path)}
        events, _, _ = convert(path, "audit")
        previous_raw = -1
        for expected_id, event in enumerate(events):
            metadata = json.loads(event["metadata"])
            index = metadata["raw_record_index"]
            if event["event_id"] != expected_id or index < previous_raw:
                errors.append({"session_id": item["session_id"], "event_id": event["event_id"],
                               "reason": "event_id_or_source_order"})
            previous_raw = index
            if event["event_type"] not in AUXILIARY_TYPES:
                continue
            checked[event["event_type"]] += 1
            if event["role"] != "system":
                errors.append({"session_id": item["session_id"], "event_id": event["event_id"],
                               "reason": "auxiliary_role"})
            if event["content"] not in source_payloads(raw[index], metadata):
                errors.append({"session_id": item["session_id"], "event_id": event["event_id"],
                               "reason": "auxiliary_content_not_in_source",
                               "format": item["format_family"],
                               "source_type": metadata.get("original_type")})
    result = {"sessions": len(selected), "checked": dict(checked),
              "error_count": len(errors), "errors": errors[:20]}
    print(json.dumps(result, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
