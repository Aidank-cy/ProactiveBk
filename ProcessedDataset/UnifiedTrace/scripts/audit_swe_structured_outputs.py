#!/usr/bin/env python3
"""Compare sampled structured tool payloads with their original main records."""
import collections
import json
from pathlib import Path

from swe_format import signature
from swe_chat_adapter import convert, records


ROOT = Path(__file__).resolve().parents[3] / "OriginalDataset-filter-1k" / "SWE-Chat-filter-1k"
OUTPUT = Path(__file__).resolve().parents[1] / "swe_structured_output_audit.json"


def content_matches(actual, expected):
    if isinstance(expected, str) or expected is None:
        return actual == expected
    try:
        return json.loads(actual) == expected
    except (TypeError, ValueError):
        return False


def main():
    selected = json.loads((ROOT / "sample_manifest.json").read_text())["selected"]
    checked = collections.Counter()
    errors = []
    for item in selected:
        path = ROOT / item["transcript_path"]
        fmt = signature(path)
        raw = {index: record for index, record, _ in records(path)}
        events, _, _ = convert(path, "audit")
        for event in events:
            if event["event_type"] not in ("tool_call", "tool_result"):
                continue
            meta = json.loads(event["metadata"])
            record = raw[meta["raw_record_index"]]
            if not isinstance(record, dict):
                continue
            expected = None
            rule = None
            if fmt in ("claude_tree", "cursor_messages", "factory_droid", "pi_tree") and meta.get("block_index") is not None:
                blocks = (record.get("message") or {}).get("content")
                if isinstance(blocks, list) and meta["block_index"] < len(blocks):
                    block = blocks[meta["block_index"]]
                    if isinstance(block, dict):
                        expected = block.get("input", block.get("arguments", block)) if event["event_type"] == "tool_call" else block.get("content", block)
                        rule = fmt + "_block"
            elif fmt == "pi_tree" and (record.get("message") or {}).get("role") == "toolResult":
                expected = record["message"].get("content"); rule = "pi_tool_result"
            elif fmt == "codex_rollout" and record.get("type") == "response_item":
                payload = record.get("payload") or record.get("item") or {}
                kind = payload.get("type")
                if kind in ("function_call", "custom_tool_call"):
                    expected = payload.get("arguments", payload.get("input")); rule = "codex_call"
                elif kind in ("function_call_output", "custom_tool_call_output"):
                    expected = payload.get("output"); rule = "codex_result"
            elif fmt == "opencode_document" and meta.get("part_index") is not None:
                parts = record.get("parts") or []
                if meta["part_index"] < len(parts):
                    part = parts[meta["part_index"]]
                    if isinstance(part, dict) and part.get("type") == "tool":
                        state = part.get("state") or {}
                        expected = state.get("input") if event["event_type"] == "tool_call" else state.get("output", state.get("error"))
                        rule = "opencode_tool_state"
            elif record.get("type") == "gemini" and meta.get("tool_index") is not None:
                calls = record.get("toolCalls") or []
                if meta["tool_index"] < len(calls):
                    call = calls[meta["tool_index"]]
                    if event["event_type"] == "tool_call":
                        expected = call.get("args"); rule = "gemini_call"
                    else:
                        expected = {k: call[k] for k in ("result", "response", "error", "resultDisplay", "status", "renderOutputAsMarkdown") if k in call}
                        rule = "gemini_result"
            elif fmt == "copilot_events":
                data = record.get("data") or {}
                if event["event_type"] == "tool_call" and meta.get("request_index") is not None:
                    expected = (data.get("toolRequests") or [])[meta["request_index"]]; rule = "copilot_request"
                elif record.get("type") == "tool.execution_complete":
                    expected = data; rule = "copilot_result"
            elif fmt == "grok_hooks":
                if record.get("event") == "PreToolUse":
                    expected = record.get("tool_input"); rule = "grok_call"
                elif record.get("event") == "PostToolUse":
                    expected = record.get("tool_response"); rule = "grok_result"
            elif fmt == "kimi_wire" and record.get("type") == "context.append_loop_event":
                loop = record.get("event") or {}
                if loop.get("type") == "tool.call":
                    expected = loop.get("args", loop.get("arguments", loop.get("input", loop))); rule = "kimi_call"
                elif loop.get("type") == "tool.result":
                    expected = loop.get("result"); rule = "kimi_result"
            elif fmt == "xai_session_update":
                update = (record.get("params") or {}).get("update") or {}
                if update.get("sessionUpdate") == "tool_call":
                    expected = update.get("rawInput", update); rule = "xai_call"
                elif update.get("sessionUpdate") == "tool_call_update" and update.get("status") in ("completed", "failed", "error"):
                    payload = update.get("content")
                    if isinstance(payload, dict) and payload.get("type") == "text":
                        payload = payload.get("text")
                    expected = update.get("rawOutput", payload); rule = "xai_result"
            if rule is None:
                continue
            checked[rule] += 1
            if not content_matches(event["content"], expected):
                errors.append({"session_id": item["session_id"], "raw_record_index": meta["raw_record_index"],
                               "event_id": event["event_id"], "rule": rule})
    report = {"sample_sessions": len(selected), "checked": dict(checked), "errors": errors[:100], "error_count": len(errors),
              "scope": "Main transcript structured tool inputs and outputs across all sampled CLI formats with tool events"}
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"checked": dict(checked), "error_count": len(errors)}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
