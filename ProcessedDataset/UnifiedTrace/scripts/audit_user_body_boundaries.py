#!/usr/bin/env python3
"""Check that user bodies are not reinterpreted as assistant/tool events."""
import collections
import json
from pathlib import Path
import tempfile

from swe_format import signature
from swe_chat_adapter import convert, count_user_turns, parse_record, records


ROOT = Path(__file__).resolve().parents[3] / "OriginalDataset-filter-1k" / "SWE-Chat-filter-1k"
OUTPUT = Path(__file__).resolve().parents[1] / "swe_user_body_audit.json"


def source_string_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from source_string_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from source_string_values(child)


def user_body_record(fmt, row):
    if not isinstance(row, dict):
        return False
    typ = row.get("type")
    message = row.get("message") if isinstance(row.get("message"), dict) else {}
    if fmt == "claude_tree":
        blocks = message.get("content")
        feedback = isinstance(blocks, list) and any(
            isinstance(part, dict) and part.get("type") in ("tool_result", "advisor_tool_result")
            for part in blocks)
        return typ == "user" and not row.get("isMeta") and not row.get("isSidechain") and not str(row.get("uuid") or "").startswith("context-") and not feedback
    if fmt == "codex_rollout":
        payload = row.get("payload") or row.get("item") or {}
        return typ == "response_item" and payload.get("type") == "message" and payload.get("role") == "user"
    if fmt == "cursor_messages":
        return row.get("role") == "user" and bool(message)
    if fmt == "pi_tree":
        return typ == "message" and message.get("role") == "user" and message.get("attribution") in (None,"user","human")
    if fmt == "factory_droid":
        blocks = message.get("content") or []
        injected = str(row.get("id") or "").startswith("context-") and isinstance(blocks, list) and any(
            isinstance(part, dict) and str(part.get("text") or "").startswith("<system-reminder>") for part in blocks)
        feedback = isinstance(blocks, list) and any(
            isinstance(part, dict) and part.get("type") in ("tool_result", "advisor_tool_result") for part in blocks)
        return typ == "message" and message.get("role") == "user" and message.get("visibility") != "llm_only" and not injected and not feedback
    if fmt == "opencode_document":
        return (row.get("info") or {}).get("role") == "user"
    if fmt == "gemini_document":
        return typ == "user"
    if fmt == "copilot_events":
        return typ == "user.message" and (row.get("data") or {}).get("source") in (None, "user", "human")
    if fmt == "kimi_wire":
        return typ == "context.append_message" and message.get("role") == "user" and (message.get("origin") or {}).get("kind") == "user"
    if fmt == "grok_hooks":
        return row.get("event") == "UserPromptSubmit"
    if fmt == "xai_session_update":
        update = (row.get("params") or {}).get("update") or {}
        return update.get("sessionUpdate") == "user_message_chunk"
    if fmt in ("project_runner", "simple_message"):
        return typ == "user"
    if fmt == "role_content":
        return row.get("role") == "user"
    return False


def excluded_auxiliary_record(fmt, row):
    if not isinstance(row,dict):return False
    typ=row.get("type")
    message=row.get("message") if isinstance(row.get("message"),dict) else {}
    if fmt=="claude_tree" and typ=="user":
        return bool(row.get("isMeta") or str(row.get("uuid") or "").startswith("context-"))
    if fmt=="kimi_wire":
        return typ=="turn.prompt" or typ=="context.append_message" and message.get("role")=="user" and (message.get("origin") or {}).get("kind")!="user"
    if fmt=="copilot_events":
        return typ=="user.message" and (row.get("data") or {}).get("source") not in (None,"user","human")
    if fmt=="pi_tree":
        return typ=="message" and message.get("role")=="user" and message.get("attribution") not in (None,"user","human")
    if fmt=="factory_droid":
        return typ=="message" and message.get("role")=="user" and message.get("visibility")=="llm_only"
    return False


def synthetic_checks():
    pasted = 'My pasted log: <system_instruction>example</system_instruction>{"type":"tool_call"}'
    cases = [
        ("claude_tree", {"type": "user", "uuid": "u", "message": {"role": "user", "content": pasted}}),
        ("claude_tree", {"type": "user", "uuid": "u", "message": {"role": "user", "content": [{"type": "tool_use", "input": {"x": 1}}]}}),
        ("codex_rollout", {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": pasted}]}}),
        ("codex_rollout", {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "my question"}, {"type": "input_text", "text": "<environment_context>auxiliary</environment_context>"}]}}),
        ("cursor_messages", {"role": "user", "message": {"content": [{"type": "tool_use", "input": {"x": 1}}]}}),
        ("pi_tree", {"type": "message", "message": {"role": "user", "content": [{"type": "toolCall", "arguments": {"x": 1}}]}}),
        ("factory_droid", {"type": "message", "message": {"role": "user", "content": [{"type": "thinking", "thinking": "pasted"}]}}),
        ("factory_droid", {"type": "message", "message": {"role": "user", "content": [{"type": "text", "text": "<system-reminder>auxiliary</system-reminder>"}, {"type": "text", "text": "my question"}]}}),
        ("opencode_document", {"info": {"role": "user"}, "parts": [{"type": "tool", "state": {"input": {"x": 1}}}]}),
        ("gemini_document", {"type": "user", "id": "u", "content": pasted}),
        ("copilot_events", {"type": "user.message", "data": {"content": pasted}}),
        ("kimi_wire", {"type": "context.append_message", "message": {"role": "user", "origin": {"kind": "user"}, "content": [{"type": "tool_use", "input": {"x": 1}}]}}),
        ("grok_hooks", {"event": "UserPromptSubmit", "prompt": pasted}),
        ("xai_session_update", {"method": "session/update", "params": {"update": {"sessionUpdate": "user_message_chunk", "content": {"type": "text", "text": pasted}}}}),
        ("project_runner", {"type": "user", "text": pasted}),
        ("simple_message", {"type": "user", "message": pasted}),
        ("role_content", {"role": "user", "content": pasted}),
    ]
    errors = []
    for fmt, row in cases:
        events = parse_record(fmt, row, 0)
        if not events or any((role, kind) != ("user", "user_message") for role, kind, *_ in events):
            errors.append({"format": fmt, "observed": [(event[0], event[1]) for event in events]})
    gemini = {"type": "gemini", "content": "body", "thoughts": ["think"],
              "toolCalls": [{"id": "a", "args": 1, "result": "A"}, {"id": "b", "args": 2, "result": "B"}]}
    expected = ["assistant_message", "assistant_thinking", "tool_call", "tool_call", "tool_result", "tool_result"]
    observed = [event[1] for event in parse_record("gemini_document", gemini, 0)]
    if observed != expected:
        errors.append({"format": "gemini_document", "expected_order": expected, "observed_order": observed})
    copilot = {"type": "assistant.message", "data": {"content": "body", "reasoningText": "think",
               "toolRequests": [{"toolCallId": "a"}, {"toolCallId": "b"}]}}
    expected = ["assistant_message", "assistant_thinking", "tool_call", "tool_call"]
    observed = [event[1] for event in parse_record("copilot_events", copilot, 0)]
    if observed != expected:
        errors.append({"format": "copilot_events", "expected_order": expected, "observed_order": observed})
    source_marked = [
        ("claude_tree", {"type": "user", "uuid": "u", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "ok"}]}}, "tool_result"),
        ("factory_droid", {"type": "message", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "ok"}]}}, "tool_result"),
        ("kimi_wire", {"type": "context.append_message", "message": {"role": "user", "origin": {"kind": "injection"}, "content": [{"type": "text", "text": "context"}]}}, None),
        ("copilot_events", {"type": "user.message", "data": {"source": "system", "content": "context"}}, None),
        ("pi_tree", {"type": "message", "message": {"role": "user", "attribution": "agent", "content": [{"type": "text", "text": "context"}]}}, None),
        ("codex_rollout", {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "<skill>auxiliary</skill>"}]}}, None),
        ("codex_rollout", {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "# AGENTS.md instructions for /repo\n<INSTRUCTIONS>\ncontext\n</INSTRUCTIONS>"}]}}, None),
        ("claude_tree", {"type": "user", "uuid": "u", "isMeta": True, "message": {"role": "user", "content": "auxiliary"}}, None),
        ("factory_droid", {"type": "message", "message": {"role": "user", "visibility": "llm_only", "content": [{"type": "text", "text": "auxiliary"}]}}, None),
        ("factory_droid", {"type": "message", "message": {"role": "user", "content": [{"type": "text", "text": "<system-reminder>auxiliary</system-reminder>"}]}}, None),
        ("opencode_document", {"info": {"role": "user"}, "parts": [{"type": "compaction", "text": "auxiliary"}]}, None),
        ("opencode_document", {"info": {"role": "user"}, "parts": [{"type": "text", "text": "<system-reminder>auxiliary</system-reminder>\n<!-- OMO_INTERNAL_INITIATOR -->"}]}, None),
    ]
    for fmt, row, expected_type in source_marked:
        observed = [event[1] for event in parse_record(fmt, row, 0)]
        if observed != ([] if expected_type is None else [expected_type]):
            errors.append({"format": fmt, "expected_source_marked_type": expected_type, "observed": observed})
    claude_mixed = {"type":"user","uuid":"u","message":{"role":"user",
                    "content":"<system_instruction>auxiliary</system_instruction>my question"}}
    observed = parse_record("claude_tree", claude_mixed, 0)
    if len(observed)!=1 or (observed[0][0],observed[0][1],observed[0][2]) != ("user","user_message",claude_mixed["message"]["content"]):
        errors.append({"format":"claude_tree","reason":"mixed_user_body_changed"})
    opencode_mixed={"info":{"role":"user"},"parts":[{"type":"text",
                    "text":"<system-reminder>auxiliary</system-reminder>my question"}]}
    observed=parse_record("opencode_document",opencode_mixed,0)
    if len(observed)!=1 or (observed[0][0],observed[0][1],observed[0][2]) != ("user","user_message",opencode_mixed["parts"][0]["text"]):
        errors.append({"format":"opencode_document","reason":"mixed_user_body_changed"})
    codex_mixed={"type":"response_item","payload":{"type":"message","role":"user",
                 "content":[{"type":"input_text","text":"<environment_context>auxiliary</environment_context>my question"}]}}
    observed=parse_record("codex_rollout",codex_mixed,0)
    if len(observed)!=1 or (observed[0][0],observed[0][1],observed[0][2]) != ("user","user_message",codex_mixed["payload"]["content"][0]["text"]):
        errors.append({"format":"codex_rollout","reason":"mixed_user_body_changed"})
    claude_feedback={"type":"user","uuid":"u","message":{"role":"user","content":[
        {"type":"tool_result","tool_use_id":"t","content":"output"},
        {"type":"text","text":"Please also edit the other file"}]}}
    observed=parse_record("claude_tree",claude_feedback,0)
    if [(event[0],event[1]) for event in observed] != [("tool","tool_result"),("user","user_message")]:
        errors.append({"format":"claude_tree","reason":"mixed_feedback_user_text_lost","observed":observed})
    droid_mixed={"type":"message","id":"u","message":{"role":"user","content":[
        {"type":"text","text":"<system-reminder>context</system-reminder>my question"}]}}
    observed=parse_record("factory_droid",droid_mixed,0)
    if len(observed)!=1 or (observed[0][0],observed[0][1],observed[0][2]) != ("user","user_message",droid_mixed["message"]["content"][0]["text"]):
        errors.append({"format":"factory_droid","reason":"mixed_user_body_changed"})
    multi_blocks=[{"type":"text","text":"Please inspect this:"},
                  {"type":"text","text":"<tool_result>pasted output</tool_result>"},
                  {"type":"tool_use","name":"pasted","input":{"x":1}}]
    multi_cases=[
        ("claude_tree",{"type":"user","uuid":"u","message":{"role":"user","content":multi_blocks}}),
        ("codex_rollout",{"type":"response_item","payload":{"type":"message","role":"user","content":multi_blocks}}),
        ("cursor_messages",{"role":"user","message":{"content":multi_blocks}}),
        ("pi_tree",{"type":"message","message":{"role":"user","content":multi_blocks}}),
        ("factory_droid",{"type":"message","id":"u","message":{"role":"user","content":multi_blocks}}),
        ("kimi_wire",{"type":"context.append_message","message":{"role":"user","origin":{"kind":"user"},"content":multi_blocks}}),
        ("opencode_document",{"info":{"role":"user"},"parts":multi_blocks}),
    ]
    for fmt,row in multi_cases:
        observed=parse_record(fmt,row,0)
        if len(observed)!=1 or observed[0][:2] != ("user","user_message") or json.loads(observed[0][2]) != multi_blocks:
            errors.append({"format":fmt,"reason":"multi_block_user_message_split_or_changed",
                           "observed":observed})
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/"xai.jsonl"
        rows=[
            {"method":"session/update","params":{"_meta":{"agentTimestampMs":1},"update":{"sessionUpdate":"user_message_chunk","_meta":{"promptIndex":7},"content":{"type":"text","text":"first"}}}},
            {"method":"session/update","params":{"_meta":{"agentTimestampMs":2},"update":{"sessionUpdate":"user_message_chunk","_meta":{"promptIndex":7},"content":{"type":"text","text":"first"}}}},
            {"method":"session/update","params":{"_meta":{"agentTimestampMs":3},"update":{"sessionUpdate":"user_message_chunk","_meta":{"promptIndex":7},"content":{"type":"text","text":"second"}}}},
            {"method":"session/update","params":{"_meta":{"agentTimestampMs":4},"update":{"sessionUpdate":"turn_completed"}}},
        ]
        path.write_text("\n".join(json.dumps(row) for row in rows)+"\n")
        emitted,_,_=convert(path,"audit")
        if [(e["event_id"],e["event_type"],e["content"]) for e in emitted] != [
            (0,"user_message","first"),(1,"user_message","second"),(2,"system_event",json.dumps(rows[3],ensure_ascii=False,sort_keys=True))
        ] or count_user_turns(emitted,"xai_session_update") != 1:
            errors.append({"format":"xai_session_update","reason":"duplicate_chunk_created_event_or_wrong_order"})
    return len(cases) + 8 + len(source_marked) + len(multi_cases), errors


def main():
    selected = json.loads((ROOT / "sample_manifest.json").read_text())["selected"]
    checked = collections.Counter()
    errors = []
    for item in selected:
        path = ROOT / item["transcript_path"]
        fmt = signature(path)
        raw = {index: row for index, row, _ in records(path)}
        events, _, _ = convert(path, "audit")
        by_raw = collections.defaultdict(list)
        for event in events:
            by_raw[json.loads(event["metadata"])["raw_record_index"]].append(event)
        seen_xai_chunks = set()
        for index, row in raw.items():
            if fmt == "xai_session_update" and isinstance(row, dict):
                params = row.get("params") or {}
                update = params.get("update") or {}
                if update.get("sessionUpdate") == "user_message_chunk":
                    prompt_index = (update.get("_meta") or {}).get("promptIndex")
                    envelope = params.get("_meta") or {}
                    group = (("prompt_index", prompt_index) if prompt_index is not None
                             else ("timestamp", envelope["agentTimestampMs"])
                             if envelope.get("agentTimestampMs") is not None
                             else ("prompt_id", envelope["promptId"])
                             if envelope.get("promptId") is not None else None)
                    key = (group, json.dumps(update.get("content"), ensure_ascii=False, sort_keys=True))
                    if group is not None and key in seen_xai_chunks:
                        checked["xai_duplicate_source_chunks_dropped"] += 1
                        if by_raw[index]:
                            errors.append({"session_id": item["session_id"], "raw_record_index": index,
                                           "format": fmt, "reason": "duplicate_xai_chunk_emitted"})
                    elif group is not None:
                        seen_xai_chunks.add(key)
            if excluded_auxiliary_record(fmt,row):
                checked[f"excluded_auxiliary_{fmt}"]+=1
                if by_raw[index]:
                    errors.append({"session_id":item["session_id"],"raw_record_index":index,
                                   "format":fmt,"reason":"auxiliary_record_emitted"})
            if fmt == "gemini_document" and isinstance(row, dict) and row.get("type") == "gemini":
                calls = row.get("toolCalls") or []
                expected = (["assistant_message"] if row.get("content") is not None else [])
                expected += ["assistant_thinking"] * len(row.get("thoughts") or [])
                expected += ["tool_call"] * len(calls)
                expected += ["tool_result"] * sum(any(key in call for key in ("result", "response", "error")) for call in calls)
                if not expected:
                    expected = ["metadata_event"]
                observed = [event["event_type"] for event in by_raw[index]]
                checked["gemini_grouped_records"] += 1
                if observed != expected:
                    errors.append({"session_id": item["session_id"], "raw_record_index": index,
                                   "format": fmt, "expected_order": expected, "observed_order": observed})
            if fmt == "copilot_events" and isinstance(row, dict) and row.get("type") == "assistant.message":
                data = row.get("data") or {}
                expected = (["assistant_message"] if data.get("content") is not None else [])
                expected += (["assistant_thinking"] if data.get("reasoningText") else [])
                expected += ["tool_call"] * len(data.get("toolRequests") or [])
                if not expected:
                    expected = ["metadata_event"]
                observed = [event["event_type"] for event in by_raw[index]]
                checked["copilot_grouped_records"] += 1
                if observed != expected:
                    errors.append({"session_id": item["session_id"], "raw_record_index": index,
                                   "format": fmt, "expected_order": expected, "observed_order": observed})
            if fmt == "claude_tree" and isinstance(row, dict) and row.get("type") == "user":
                blocks = (row.get("message") or {}).get("content")
                if isinstance(blocks, list) and any(
                    isinstance(part, dict) and part.get("type") == "tool_result" for part in blocks
                ):
                    for block_index, part in enumerate(blocks):
                        if not isinstance(part, dict) or part.get("type") != "text":
                            continue
                        text = part.get("text")
                        has_tool_reference = any(
                            isinstance(feedback, dict)
                            and isinstance(feedback.get("content"), list)
                            and any(isinstance(ref, dict) and ref.get("type") == "tool_reference"
                                    for ref in feedback["content"])
                            for feedback in blocks
                        )
                        expected = ("system", "system_event") if text == "Tool loaded." and has_tool_reference else ("user", "user_message")
                        matching = [event for event in by_raw[index] if json.loads(event["metadata"]).get("block_index") == block_index]
                        checked["claude_mixed_feedback_text_blocks"] += 1
                        if len(matching) != 1 or (matching[0]["role"], matching[0]["event_type"]) != expected or matching[0]["content"] != text:
                            errors.append({"session_id": item["session_id"], "raw_record_index": index,
                                           "format": fmt, "reason": "mixed_feedback_text_misclassified",
                                           "block_index": block_index, "expected": expected})
            if not user_body_record(fmt, row):
                continue
            checked[fmt] += 1
            raw_strings = set(source_string_values(row))
            for event in by_raw[index]:
                # Exact duplicate xAI source chunks remain inspectable metadata.
                if (event["role"], event["event_type"]) not in (("user", "user_message"), ("system", "metadata_event")):
                    errors.append({"session_id": item["session_id"], "raw_record_index": index,
                                   "format": fmt, "role": event["role"], "event_type": event["event_type"]})
                if event["event_type"] == "user_message" and isinstance(event["content"], str):
                    try:
                        structured = isinstance(json.loads(event["content"]), (dict, list))
                    except (ValueError, TypeError):
                        structured = False
                    if not structured:
                        checked["exact_user_text_blocks"] += 1
                        if event["content"] not in raw_strings:
                            errors.append({"session_id": item["session_id"], "raw_record_index": index,
                                           "format": fmt, "reason": "user_text_differs_from_source"})
    synthetic_count, synthetic_errors = synthetic_checks()
    errors.extend(synthetic_errors)
    report = {"sample_sessions": len(selected), "source_user_records_checked_by_format": dict(checked),
              "synthetic_cases_checked": synthetic_count, "error_count": len(errors), "errors": errors[:100]}
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("source_user_records_checked_by_format", "synthetic_cases_checked", "error_count")}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
