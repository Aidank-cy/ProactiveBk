"""Raw SWE transcript reading and loss-aware content-block helpers."""

import json


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def content(value):
    return value if isinstance(value, str) or value is None else dumps(value)


def records(path):
    """Yield (ordinal, object, format); invalid JSONL lines retain their exact text."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        document = json.loads(raw)
    except json.JSONDecodeError:
        # JSONL records are separated by LF. splitlines() also splits U+2028/U+2029
        # inside valid JSON string content, which falsely marks those records invalid.
        for n, line in enumerate(raw.split("\n")):
            if not line.strip():
                continue
            try:
                yield n, json.loads(line), "jsonl"
            except json.JSONDecodeError:
                yield n, {"_unparsed_line": line}, "invalid_jsonl"
    else:
        if isinstance(document, dict) and isinstance(document.get("messages"), list):
            # Top-level session metadata is not a conversation event.
            for n, item in enumerate(document["messages"]):
                yield n, item, "json_document"
        elif isinstance(document, list):
            for n, item in enumerate(document):
                yield n, item, "json_array"
        else:
            yield 0, document, "json_document"


def _parts(parts, base_meta, source_id, is_human=False):
    if is_human and isinstance(parts, list):
        # One source human message is one unified event. Preserve heterogeneous
        # text/attachment/protocol-looking blocks together in source order.
        if not parts:
            return []
        only = parts[0] if len(parts) == 1 else None
        body = (
            only["text"]
            if isinstance(only, dict)
            and only.get("type") in ("text", "input_text", "output_text")
            and isinstance(only.get("text"), str)
            else content(only) if len(parts) == 1 and not isinstance(only, dict)
            else dumps(only) if len(parts) == 1
            else dumps(parts)
        )
        return [("user", "user_message", body, "public", source_id,
                 {**base_meta, "user_block_indices": base_meta.get("user_block_indices", list(range(len(parts))))})]
    if not isinstance(parts, list):
        if is_human and parts is None:
            return []
        return [
            (
                "user" if is_human else "assistant",
                "user_message" if is_human else "assistant_message",
                content(parts),
                "public",
                source_id,
                base_meta,
            )
        ]
    if not parts:
        if is_human:
            return []
        return [
            (
                "system",
                "metadata_event",
                "[]",
                "internal",
                source_id,
                {**base_meta, "empty_content_blocks": True},
            )
        ]
    out = []
    for i, block in enumerate(parts):
        m = {**base_meta, "block_index": i}
        if not isinstance(block, dict):
            out.append(
                (
                    "user" if is_human else "assistant",
                    "user_message" if is_human else "assistant_message",
                    content(block),
                    "public",
                    source_id,
                    m,
                )
            )
            continue
        kind = block.get("type")
        m["original_block_type"] = kind
        m.update(
            {
                k: v
                for k, v in block.items()
                if k not in ("text", "thinking", "content", "input", "output", "source", "data")
            }
        )
        if kind in ("tool_use", "server_tool_use", "toolCall"):
            m["tool_name"] = block.get("name")
            m["tool_call_id"] = block.get("id")
            out.append(
                (
                    "assistant",
                    "tool_call",
                    content(block.get("input", block.get("arguments", block))),
                    "environment",
                    source_id,
                    m,
                )
            )
        elif kind in ("tool_result", "advisor_tool_result"):
            m["tool_call_id"] = block.get("tool_use_id")
            out.append(
                (
                    "tool",
                    "tool_result",
                    content(block.get("content", block)),
                    "environment",
                    source_id,
                    m,
                )
            )
        elif kind in ("thinking", "redacted_thinking", "think"):
            out.append(
                (
                    "assistant",
                    "assistant_thinking",
                    content(block.get("thinking", block.get("think", block))),
                    "internal",
                    source_id,
                    m,
                )
            )
        elif kind in ("text", "input_text", "output_text"):
            out.append(
                (
                    "user" if is_human else "assistant",
                    "user_message" if is_human else "assistant_message",
                    content(block.get("text")),
                    "public",
                    source_id,
                    m,
                )
            )
        elif kind == "image":
            out.append(
                (
                    "user" if is_human else "assistant",
                    "user_message" if is_human else "assistant_message",
                    dumps(block),
                    "public",
                    source_id,
                    m,
                )
            )
        else:
            out.append(
                (
                    "system",
                    "metadata_event",
                    dumps(block),
                    "internal",
                    source_id,
                    {**m, "unrecognized_block": True},
                )
            )
    return out
