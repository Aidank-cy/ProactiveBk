"""Order source records and normalize SWE CLI records into unified events."""

import json
from collections import Counter

from swe_format import signature
from swe_common import content, dumps, records, _parts
from swe_cli_parsers import PARSERS
from swe_record_policy import EXCLUDED_FORMATS, skip_supplementary_record


def parse_record(source_format, record, ordinal, codex_assistant_remaining=None):
    """Return tuples (role, type, content, visibility, source_id, metadata)."""
    if not isinstance(record, dict):
        return [
            ("system", "metadata_event", content(record), "internal", None, {"unrecognized": True})
        ]
    if skip_supplementary_record(record):
        return []
    if "_unparsed_line" in record:
        return [
            (
                "system",
                "metadata_event",
                record["_unparsed_line"],
                "internal",
                None,
                {"parse_error": "invalid_jsonl"},
            )
        ]
    if "_document_metadata" in record:
        return [
            (
                "system",
                "metadata_event",
                dumps(record["_document_metadata"]),
                "internal",
                None,
                {"original_type": "document_metadata", "posthoc_fields_possible": True},
            )
        ]
    # Dispatch from the raw envelope. Session agent and model labels are never used here.
    if record.get("method") in ("session/update", "_x.ai/session/update") and isinstance(
        record.get("params"), dict
    ):
        return PARSERS["xai_session_update"].parse(record)
    if isinstance(record.get("info"), dict) and isinstance(record.get("parts"), list):
        return PARSERS["opencode_document"].parse(record)
    if record.get("type") in (
        "response_item",
        "event_msg",
        "turn_context",
        "session_meta",
        "world_state",
        "compacted",
    ) and ("payload" in record or "item" in record):
        return PARSERS["codex_rollout"].parse(record, codex_assistant_remaining)
    if (
        record.get("type", "").startswith(("assistant.", "user.", "tool.execution_", "session."))
        and "data" in record
    ):
        return PARSERS["copilot_events"].parse(record)
    if record.get("event") in (
        "SessionStart",
        "SessionEnd",
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "Stop",
        "StopCancelled",
        "StopFailure",
        "Notification",
        "SubagentStart",
        "SubagentStop",
        "PreCompact",
    ):
        return PARSERS["grok_hooks"].parse(record)
    if record.get("type") in ("context.append_message", "context.append_loop_event", "turn.prompt"):
        return PARSERS["kimi_wire"].parse(record)
    if record.get("type") == "gemini" or (
        record.get("type") == "user" and "content" in record and "id" in record
    ):
        return PARSERS["gemini_document"].parse(record)
    if record.get("role") in ("user", "assistant") and isinstance(record.get("message"), dict):
        return PARSERS["cursor_messages"].parse(record)
    if record.get("type") in ("user", "assistant", "tool_use", "tool_result") and isinstance(
        record.get("message"), dict
    ):
        return PARSERS["claude_tree"].parse(record)
    if record.get("type") in ("user", "assistant") and isinstance(record.get("message"), str):
        return PARSERS["simple_message"].parse(record)
    if record.get("type") in ("user", "assistant") and "text" in record:
        return PARSERS["project_runner"].parse(record)
    if (
        record.get("type") == "message"
        and isinstance(record.get("message"), dict)
        and record["message"].get("role")
    ):
        return (
            PARSERS["factory_droid"].parse(record)
            if source_format == "factory_droid"
            else PARSERS["pi_tree"].parse(record)
        )
    if (
        record.get("role") in ("user", "assistant")
        and "content" in record
        and "message" not in record
    ):
        return PARSERS["role_content"].parse(record)
    if source_format in PARSERS:
        parser = PARSERS[source_format]
        if source_format == "codex_rollout":
            return parser.parse(record, codex_assistant_remaining)
        return parser.parse(record)
    return [
        (
            "system",
            "metadata_event",
            dumps(record),
            "internal",
            record.get("id"),
            {"unrecognized_format": source_format},
        )
    ]


def convert(path, trace_id):
    events = []
    issues = []
    fmt = None
    source_format = signature(path)
    if source_format in EXCLUDED_FORMATS or source_format == "unclassified":
        raise ValueError(f"unsupported SWE main transcript format {source_format}: {path}")
    codex_assistant_remaining = None
    xai_seen_user_chunks = set()
    if source_format == "codex_rollout":
        codex_assistant_remaining = Counter()
        for _, record, _ in records(path):
            if not isinstance(record, dict) or record.get("type") != "response_item":
                continue
            payload = record.get("payload") or record.get("item") or {}
            if payload.get("type") == "message" and payload.get("role") == "assistant":
                for block in payload.get("content") or []:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "output_text"
                        and isinstance(block.get("text"), str)
                    ):
                        codex_assistant_remaining[block["text"]] += 1
    for ordinal, r, record_format in records(path):
        fmt = record_format if fmt is None else fmt
        if record_format == "invalid_jsonl":
            issues.append({"raw_record_index": ordinal, "reason": "invalid_jsonl"})
        parsed = parse_record(source_format, r, ordinal, codex_assistant_remaining)
        if source_format == "xai_session_update" and isinstance(r, dict):
            update = (r.get("params") or {}).get("update") or {}
            if update.get("sessionUpdate") == "user_message_chunk":
                prompt_index = (update.get("_meta") or {}).get("promptIndex")
                payload = update.get("content")
                chunk_key = dumps(payload)
                envelope_meta = (r.get("params") or {}).get("_meta") or {}
                group = (
                    ("prompt_index", prompt_index)
                    if prompt_index is not None
                    else ("timestamp", envelope_meta["agentTimestampMs"])
                    if envelope_meta.get("agentTimestampMs") is not None
                    else ("prompt_id", envelope_meta["promptId"])
                    if envelope_meta.get("promptId") is not None
                    else None
                )
                duplicate = group is not None and (group, chunk_key) in xai_seen_user_chunks
                if duplicate:
                    # The same source prompt block is retransmitted. It adds
                    # no interaction event and must not consume an event_id.
                    parsed = []
                else:
                    if group is not None:
                        xai_seen_user_chunks.add((group, chunk_key))
                    parsed = [
                        (
                            role,
                            typ,
                            body,
                            visibility,
                            sid,
                            {**metadata, "prompt_index": prompt_index},
                        )
                        for role, typ, body, visibility, sid, metadata in parsed
                    ]
        for role, typ, body, visibility, sid, metadata in parsed:
            # Preserve original order, including order of content blocks within a raw record.
            metadata = {**metadata, "raw_record_index": ordinal, "raw_format": record_format}
            timestamp = (
                (r.get("timestamp") or r.get("time") or r.get("ts"))
                if isinstance(r, dict)
                else None
            )
            if timestamp is None and isinstance(r, dict) and isinstance(r.get("info"), dict):
                timestamp = metadata.get("original_part_time") or (r["info"].get("time") or {}).get(
                    "created"
                )
            if isinstance(timestamp, (dict, list)):
                timestamp = dumps(timestamp)
            events.append(
                {
                    "trace_id": trace_id,
                    "event_id": len(events),
                    "source_event_id": str(sid) if sid is not None else None,
                    "role": role,
                    "event_type": typ,
                    "content": body,
                    "timestamp": str(timestamp) if timestamp is not None else None,
                    "visibility": visibility,
                    "metadata": dumps(metadata),
                }
            )
    return events, issues, fmt


def count_user_turns(events, source_format):
    """Count delivered source prompts, not normalized content blocks or retries."""
    turns = set()
    for event in events:
        if event["role"] != "user" or event["event_type"] != "user_message":
            continue
        meta = json.loads(event["metadata"])
        prompt_index = meta.get("prompt_index") if source_format == "xai_session_update" else None
        turns.add(
            ("prompt", prompt_index)
            if prompt_index is not None
            else ("record", meta["raw_record_index"])
        )
    return len(turns)


def main_agent_model_candidates(path, source_format):
    """Return model IDs explicitly attached to main-agent responses or turns.

    User settings, document headers, sidechains, and supplementary records are
    excluded. Callers use a fallback only when exactly one model is observed.
    """
    models = set()
    for _, record, _ in records(path):
        if not isinstance(record, dict) or skip_supplementary_record(record):
            continue
        kind = record.get("type")
        candidate = None
        if source_format == "claude_tree" and kind == "assistant":
            candidate = (record.get("message") or {}).get("model")
        elif source_format == "codex_rollout" and kind == "turn_context":
            candidate = (record.get("payload") or record.get("item") or {}).get("model")
        elif source_format == "gemini_document" and kind == "gemini":
            candidate = record.get("model")
        elif source_format == "opencode_document" and (record.get("info") or {}).get("role") == "assistant":
            info = record["info"]
            candidate = info.get("modelID") or info.get("model")
        elif source_format == "pi_tree" and kind == "message":
            message = record.get("message") or {}
            if message.get("role") == "assistant":
                candidate = message.get("model")
        elif source_format == "copilot_events" and kind == "assistant.message":
            candidate = (record.get("data") or {}).get("model")
        elif source_format == "project_runner" and kind == "assistant":
            candidate = record.get("model")
        if isinstance(candidate, dict):
            candidate = candidate.get("modelID") or candidate.get("id")
        if isinstance(candidate, str):
            candidate = candidate.strip()
            if candidate and candidate.lower() not in (
                "<synthetic>", "synthetic", "codex-auto-review", "auto", "auto-smart", "default"
            ):
                models.add(candidate)
    return models


def resolve_trace_model(session_model, main_log_models):
    """Choose a single actual model, or leave an ambiguous trace unlabeled."""
    if len(main_log_models) == 1:
        return next(iter(main_log_models)), "unique_main_log_model"
    if len(main_log_models) > 1:
        return None, "ambiguous_main_log_models"
    if isinstance(session_model, str) and session_model.strip() and session_model.strip().lower() not in (
        "auto", "auto-smart", "default"
    ):
        return session_model.strip(), "session_metadata_only"
    return None, "model_unavailable"
