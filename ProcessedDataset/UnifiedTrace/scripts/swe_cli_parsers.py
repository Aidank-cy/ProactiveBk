"""CLI-specific parsers; each class handles one observed SWE source envelope."""

from swe_common import content, dumps, _parts
from swe_record_policy import (
    claude_human_user_record, claude_strip_auxiliary_prefix,
    codex_injected_user_content, codex_user_body_without_auxiliary,
    copilot_human_user_record, droid_injected_user_record, droid_reminder_block,
    kimi_duplicate_prompt_record, kimi_human_user_message,
    opencode_auxiliary_user_part, opencode_user_text_without_auxiliary,
    pi_human_user_message,
)


class BaseCliParser:
    """A stateless parser for one SWE CLI record format.

    Each parser returns ordered (role, event_type, content, visibility,
    source_id, metadata) tuples. The common converter assigns event IDs.
    """

    source_format = None

    def parse(self, record):
        raise NotImplementedError


class ClaudeParser(BaseCliParser):
    """Parse claude_tree source records using their native envelope."""

    source_format = "claude_tree"

    def parse(self, r):
        typ = r.get("type")
        sid = r.get("uuid")
        base = {
            "original_type": typ,
            "parent_uuid": r.get("parentUuid"),
            "is_sidechain": r.get("isSidechain"),
            "is_meta": r.get("isMeta"),
            "cwd": r.get("cwd"),
            "session_id": r.get("sessionId"),
            "request_id": r.get("requestId"),
        }
        if typ in ("assistant", "user", "tool_use", "tool_result") and isinstance(
            r.get("message"), dict
        ):
            message = r["message"]
            base["message_id"] = message.get("id")
            base["source_message_metadata"] = {k: v for k, v in message.items() if k != "content"}
            if typ in ("user", "tool_result"):
                co = message.get("content")
                human = claude_human_user_record(r)
                if r.get("_swe_chat_reconstruction"):
                    base["source_reconstruction"] = True
                if typ == "user" and not human:
                    # Metadata/context envelopes are not messages authored by the
                    # human, even though Claude stores them under type=user.
                    return []
                mixed_tool_feedback = isinstance(co, list) and any(
                    isinstance(b, dict) and b.get("type") in ("tool_result", "advisor_tool_result")
                    for b in co
                )
                if mixed_tool_feedback:
                    human = False
                if human:
                    if isinstance(co, list):
                        kept_blocks = []
                        indices = []
                        for index, block in enumerate(co):
                            if isinstance(block, dict) and isinstance(block.get("text"), str):
                                _, auxiliary = claude_strip_auxiliary_prefix(block["text"])
                                if auxiliary is not None:
                                    continue
                            kept_blocks.append(block)
                            indices.append(index)
                        out = _parts(kept_blocks, {**base, "user_block_indices": indices}, sid, True)
                    else:
                        body, auxiliary = claude_strip_auxiliary_prefix(co)
                        out = _parts(body, base, sid, True) if auxiliary is None and body is not None else []
                    out = [event for event in out if event[2] is not None and
                           (not isinstance(event[2], str) or event[2].strip())]
                else:
                    out = _parts(co, base, sid, False)
                if not human:
                    revised = []
                    for a, t, c, v, x, m in out:
                        if mixed_tool_feedback and m.get("original_block_type") == "text":
                            block = co[m["block_index"]]
                            text = block.get("text")
                            tool_reference = any(
                                isinstance(feedback, dict)
                                and isinstance(feedback.get("content"), list)
                                and any(
                                    isinstance(item, dict) and item.get("type") == "tool_reference"
                                    for item in feedback["content"]
                                )
                                for feedback in co
                            )
                            if text == "Tool loaded." and tool_reference:
                                revised.append(("system", "system_event", text, "environment", x,
                                                {**m, "tool_feedback_notice": True}))
                            else:
                                revised.append(("user", "user_message", content(text), "public", x,
                                                {**m, "mixed_tool_feedback_user_text": True}))
                        elif t in ("assistant_message", "user_message"):
                            revised.append(
                                (
                                    "system",
                                    "system_event",
                                    c,
                                    "environment",
                                    x,
                                    {**m, "source_role": "user", "system_injected": True},
                                )
                            )
                        else:
                            revised.append((a, t, c, v, x, m))
                    out = revised
                return out
            return _parts(message.get("content"), base, sid)
        if typ == "queue-operation":
            return [
                (
                    "system",
                    "queue_event",
                    content(r.get("content", r)),
                    "internal",
                    sid,
                    {**base, "operation": r.get("operation")},
                )
            ]
        return [
            (
                "system",
                "system_event" if typ == "system" else "metadata_event",
                dumps(r),
                "internal",
                sid,
                {**base, "unrecognized_or_supplementary": typ != "system"},
            )
        ]


class CodexParser(BaseCliParser):
    """Parse codex_rollout source records using their native envelope."""

    source_format = "codex_rollout"

    def parse(self, r, assistant_remaining=None):
        outer = r.get("type")
        p = r.get("payload") or r.get("item") or {}
        typ = p.get("type")
        sid = p.get("id")
        m = {
            "original_type": outer,
            "payload_type": typ,
            "call_id": p.get("call_id"),
            "tool_name": p.get("name"),
            "source_payload_metadata": {
                k: v
                for k, v in p.items()
                if k not in ("content", "arguments", "input", "output", "summary")
            },
        }
        if outer == "event_msg":
            if typ == "agent_reasoning" and p.get("text") is not None:
                return [
                    (
                        "assistant",
                        "assistant_thinking",
                        content(p["text"]),
                        "internal",
                        sid,
                        {**m, "event_msg_reasoning": True},
                    )
                ]
            if (
                typ == "agent_message"
                and isinstance(p.get("message"), str)
                and assistant_remaining is not None
            ):
                message = p["message"]
                if assistant_remaining[message] > 0:
                    assistant_remaining[message] -= 1
                else:
                    return [
                        (
                            "assistant",
                            "assistant_message",
                            message,
                            "public",
                            sid,
                            {**m, "unpaired_agent_message": True},
                        )
                    ]
        if outer == "response_item":
            if typ == "message":
                role = p.get("role")
                if role == "user":
                    blocks = p.get("content")
                    runtime_record = codex_injected_user_content(blocks)
                    if isinstance(blocks, list):
                        kept_blocks = []
                        indices = []
                        for index, block in enumerate(blocks):
                            body = (block.get("text") if isinstance(block, dict)
                                    and block.get("type") in ("text", "input_text", "output_text")
                                    and isinstance(block.get("text"), str)
                                    else dumps(block))
                            if codex_user_body_without_auxiliary(body, runtime_record) is None:
                                continue
                            kept_blocks.append(block)
                            indices.append(index)
                        return _parts(kept_blocks, {**m, "user_block_indices": indices}, sid, True)
                    body = codex_user_body_without_auxiliary(blocks, runtime_record)
                    return _parts(body, m, sid, True) if body is not None else []
                if role == "assistant":
                    return _parts(p.get("content"), m, sid)
                return [
                    (
                        "system",
                        "system_event",
                        content(p.get("content")),
                        "environment",
                        sid,
                        {**m, "source_role": role},
                    )
                ]
            if typ in ("function_call", "custom_tool_call"):
                return [
                    (
                        "assistant",
                        "tool_call",
                        content(p.get("arguments", p.get("input"))),
                        "environment",
                        sid,
                        m,
                    )
                ]
            if typ in ("function_call_output", "custom_tool_call_output"):
                return [("tool", "tool_result", content(p.get("output")), "environment", sid, m)]
            if typ == "reasoning":
                return [("assistant", "assistant_thinking", dumps(p), "internal", sid, m)]
            if typ in ("web_search_call", "tool_search_call"):
                return [("assistant", "tool_call", dumps(p), "environment", sid, m)]
            if typ == "tool_search_output":
                return [("tool", "tool_result", dumps(p), "environment", sid, m)]
        return [
            (
                "system",
                "metadata_event",
                dumps(r),
                "internal",
                sid,
                {**m, "unrecognized_or_supplementary": True},
            )
        ]


class OpenCodeParser(BaseCliParser):
    """Parse opencode_document source records using their native envelope."""

    source_format = "opencode_document"

    def parse(self, r):
        info = r.get("info") or {}
        role = info.get("role")
        base = {
            "original_type": "message",
            "message_id": info.get("id"),
            "source_role": role,
            "source_message_metadata": {
                k: v for k, v in info.items() if k not in ("summary", "outcome", "success")
            },
        }
        if role == "user":
            selected = []
            indices = []
            for index, part in enumerate(r.get("parts") or []):
                if opencode_auxiliary_user_part(part):
                    continue
                if part.get("type") == "text" and opencode_user_text_without_auxiliary(part.get("text")) is None:
                    continue
                selected.append(part)
                indices.append(index)
            if not selected:
                return []
            only = selected[0] if len(selected) == 1 else None
            body = only["text"] if isinstance(only, dict) and only.get("type") == "text" and isinstance(only.get("text"), str) else dumps(only) if only is not None else dumps(selected)
            return [("user", "user_message", body, "public", info.get("id"),
                     {**base, "user_part_indices": indices, "structured_user_attachment": any(
                         isinstance(part, dict) and part.get("type") == "file" for part in selected)})]
        out = []
        for part_index, part in enumerate(r.get("parts") or []):
            typ = part.get("type")
            m = {
                **base,
                "part_index": part_index,
                "original_part_type": typ,
                "part_id": part.get("id"),
                "call_id": part.get("callID"),
                "tool_name": part.get("tool"),
                "original_part_time": part.get("time"),
                "source_part_metadata": {
                    k: v for k, v in part.items() if k not in ("text", "state", "prompt", "content")
                },
            }
            sid = part.get("id")
            if typ == "text":
                out.append(
                    ("assistant", "assistant_message", content(part.get("text")), "public", sid, m)
                )
            elif typ == "reasoning":
                out.append(
                    (
                        "assistant",
                        "assistant_thinking",
                        content(part.get("text")),
                        "internal",
                        sid,
                        m,
                    )
                )
            elif typ == "tool":
                state = part.get("state") or {}
                m["tool_state_metadata"] = {
                    k: v for k, v in state.items() if k not in ("input", "output", "error")
                }
                out.append(
                    ("assistant", "tool_call", content(state.get("input")), "environment", sid, m)
                )
                if (
                    state.get("status") in ("completed", "error")
                    or "output" in state
                    or "error" in state
                ):
                    out.append(
                        (
                            "tool",
                            "tool_result",
                            content(state.get("output", state.get("error"))),
                            "environment",
                            sid,
                            {**m, "tool_status": state.get("status")},
                        )
                    )
            else:
                out.append(
                    (
                        "system",
                        "metadata_event",
                        dumps(part),
                        "internal",
                        sid,
                        {**m, "unrecognized_or_supplementary": True},
                    )
                )
        return out or [
            (
                "system",
                "metadata_event",
                dumps(r),
                "internal",
                info.get("id"),
                {**base, "empty_parts": True},
            )
        ]


class CursorParser(BaseCliParser):
    """Parse cursor_messages source records using their native envelope."""

    source_format = "cursor_messages"

    def parse(self, r):
        role = r.get("role")
        m = {"original_type": r.get("type") or role}
        if role in ("user", "assistant"):
            msg = r.get("message") or {}
            m["source_message_metadata"] = {k: v for k, v in msg.items() if k != "content"}
            out = _parts(msg.get("content"), m, r.get("id"), role == "user")
            return out
        return [("system", "metadata_event", dumps(r), "internal", r.get("id"), m)]


class GeminiParser(BaseCliParser):
    """Parse gemini_document source records using their native envelope."""

    source_format = "gemini_document"

    def parse(self, r):
        typ = r.get("type")
        m = {"original_type": typ, "model": r.get("model"), "tokens": r.get("tokens")}
        sid = r.get("id")
        out = []
        if typ == "user":
            return [("user", "user_message", content(r.get("content")), "public", sid, m)]
        if typ == "gemini":
            if r.get("content") is not None:
                out.append(
                    ("assistant", "assistant_message", content(r.get("content")), "public", sid, m)
                )
            for i, t in enumerate(r.get("thoughts") or []):
                out.append(
                    (
                        "assistant",
                        "assistant_thinking",
                        content(t),
                        "internal",
                        sid,
                        {**m, "thought_index": i},
                    )
                )
            calls = r.get("toolCalls") or []
            for i, t in enumerate(calls):
                tm = {
                    **m,
                    "tool_index": i,
                    "tool_name": t.get("name"),
                    "tool_call_id": t.get("id"),
                    "tool_status": t.get("status"),
                    "source_tool_metadata": {
                        k: v
                        for k, v in t.items()
                        if k not in ("args", "result", "response", "error", "resultDisplay")
                    },
                }
                out.append(
                    (
                        "assistant",
                        "tool_call",
                        content(t.get("args")),
                        "environment",
                        t.get("id"),
                        tm,
                    )
                )
            for i, t in enumerate(calls):
                if "result" in t or "response" in t or "error" in t:
                    tm = {
                        **m,
                        "tool_index": i,
                        "tool_name": t.get("name"),
                        "tool_call_id": t.get("id"),
                        "tool_status": t.get("status"),
                        "source_tool_metadata": {
                            k: v
                            for k, v in t.items()
                            if k not in ("args", "result", "response", "error", "resultDisplay")
                        },
                    }
                    result_payload = {
                        k: t[k]
                        for k in (
                            "result",
                            "response",
                            "error",
                            "resultDisplay",
                            "status",
                            "renderOutputAsMarkdown",
                        )
                        if k in t
                    }
                    out.append(
                        (
                            "tool",
                            "tool_result",
                            dumps(result_payload),
                            "environment",
                            t.get("id"),
                            tm,
                        )
                    )
            return out or [
                (
                    "system",
                    "metadata_event",
                    dumps(r),
                    "internal",
                    sid,
                    {**m, "empty_gemini_message": True},
                )
            ]
        return [
            (
                "system",
                "system_event" if typ in ("info", "warning") else "metadata_event",
                dumps(r),
                "internal",
                sid,
                m,
            )
        ]


class PiParser(BaseCliParser):
    """Parse pi_tree source records using their native envelope."""

    source_format = "pi_tree"

    def parse(self, r):
        typ = r.get("type")
        sid = r.get("id")
        m = {"original_type": typ, "parent_id": r.get("parentId")}
        if typ == "custom_message":
            return [
                (
                    "system",
                    "system_event",
                    content(r.get("content", r)),
                    "environment",
                    sid,
                    {**m, "custom_type": r.get("customType")},
                )
            ]
        if typ == "custom" and r.get("customType") == "tool_execution_start":
            return [
                (
                    "system",
                    "system_event",
                    content(r.get("data", r)),
                    "environment",
                    sid,
                    {
                        **m,
                        "tool_call_id": (r.get("data") or {}).get("toolCallId"),
                        "tool_name": (r.get("data") or {}).get("toolName"),
                    },
                )
            ]
        if typ == "message":
            msg = r.get("message") or {}
            role = msg.get("role")
            m["source_role"] = role
            m["source_message_metadata"] = {k: v for k, v in msg.items() if k != "content"}
            if role == "toolResult":
                return [
                    (
                        "tool",
                        "tool_result",
                        content(msg.get("content")),
                        "environment",
                        sid,
                        {
                            **m,
                            "tool_name": msg.get("toolName"),
                            "tool_call_id": msg.get("toolCallId"),
                        },
                    )
                ]
            if role == "bashExecution":
                return [("tool", "tool_result", content(msg), "environment", sid, m)]
            if role == "user" and not pi_human_user_message(msg):
                return []
            if role in ("user", "assistant"):
                return _parts(msg.get("content"), m, sid, role == "user")
        return [("system", "metadata_event", dumps(r), "internal", sid, m)]


class CopilotParser(BaseCliParser):
    """Parse copilot_events source records using their native envelope."""

    source_format = "copilot_events"

    def parse(self, r):
        typ = r.get("type")
        d = r.get("data") or {}
        sid = r.get("id")
        m = {
            "original_type": typ,
            "parent_id": r.get("parentId"),
            "tool_call_id": d.get("toolCallId"),
            "tool_name": d.get("toolName"),
            "source_data_metadata": {
                k: v
                for k, v in d.items()
                if k not in ("content", "reasoningText", "arguments", "output")
            },
        }
        if typ == "user.message":
            if not copilot_human_user_record(d):
                return []
            return [("user", "user_message", content(d.get("content")), "public", sid, m)]
        if typ == "assistant.message":
            out = []
            if d.get("content") is not None:
                out.append(
                    ("assistant", "assistant_message", content(d["content"]), "public", sid, m)
                )
            if d.get("reasoningText"):
                out.append(
                    (
                        "assistant",
                        "assistant_thinking",
                        content(d["reasoningText"]),
                        "internal",
                        sid,
                        m,
                    )
                )
            for i, t in enumerate(d.get("toolRequests") or []):
                request_meta = {
                    **m,
                    "request_index": i,
                    "tool_call_id": t.get("toolCallId"),
                    "tool_name": t.get("name", t.get("toolName")),
                }
                out.append(("assistant", "tool_call", content(t), "environment", sid, request_meta))
            return out or [("system", "metadata_event", dumps(r), "internal", sid, m)]
        if typ == "tool.execution_start":
            # The assistant.message.toolRequests entry is the call; this is its execution lifecycle record.
            return [
                (
                    "system",
                    "system_event",
                    dumps(d),
                    "environment",
                    sid,
                    {**m, "execution_start": True},
                )
            ]
        if typ == "tool.execution_complete":
            return [("tool", "tool_result", content(d), "environment", sid, m)]
        return [
            (
                "system",
                "system_event" if typ and typ.startswith("system.") else "metadata_event",
                dumps(r),
                "internal",
                sid,
                m,
            )
        ]


class KimiParser(BaseCliParser):
    """Parse kimi_wire source records using their native envelope."""

    source_format = "kimi_wire"

    def parse(self, r):
        typ = r.get("type")
        m = {"original_type": typ}
        sid = None
        if kimi_duplicate_prompt_record(r):
            return []
        if typ == "context.append_message":
            msg = r.get("message") or {}
            role = msg.get("role")
            sid = msg.get("id")
            origin = (msg.get("origin") or {}).get("kind")
            if role == "user" and kimi_human_user_message(msg):
                return _parts(msg.get("content"), {**m, "origin_kind": origin}, sid, True)
            if role == "user":
                # Injection/task messages are auxiliary context, not human input.
                return []
            return [
                ("system", "metadata_event", dumps(r), "internal", sid, {**m, "source_role": role})
            ]
        if typ == "context.append_loop_event":
            e = r.get("event") or {}
            kind = e.get("type")
            sid = e.get("uuid")
            m.update(
                {
                    "loop_event_type": kind,
                    "tool_call_id": e.get("toolCallId"),
                    "tool_name": e.get("name"),
                    "parent_uuid": e.get("parentUuid"),
                    "turn_id": e.get("turnId"),
                    "step": e.get("step"),
                    "step_uuid": e.get("stepUuid"),
                }
            )
            if kind == "tool.call":
                return [
                    (
                        "assistant",
                        "tool_call",
                        content(e.get("args", e.get("arguments", e.get("input", e)))),
                        "environment",
                        sid,
                        m,
                    )
                ]
            if kind == "tool.result":
                return [("tool", "tool_result", content(e.get("result")), "environment", sid, m)]
            if kind == "content.part":
                part = e.get("part") or {}
                pk = part.get("type")
                m["part_type"] = pk
                if pk in ("think", "thinking"):
                    return [
                        (
                            "assistant",
                            "assistant_thinking",
                            content(part.get("think", part.get("thinking"))),
                            "internal",
                            sid,
                            m,
                        )
                    ]
                if pk in ("text", "output_text"):
                    return [
                        (
                            "assistant",
                            "assistant_message",
                            content(part.get("text")),
                            "public",
                            sid,
                            m,
                        )
                    ]
            return [("system", "metadata_event", dumps(r), "internal", sid, m)]
        return [("system", "metadata_event", dumps(r), "internal", sid, m)]


class DroidParser(BaseCliParser):
    """Parse factory_droid source records using their native envelope."""

    source_format = "factory_droid"

    def parse(self, r):
        typ = r.get("type")
        sid = r.get("id")
        m = {"original_type": typ}
        if typ == "message":
            msg = r.get("message") or {}
            role = msg.get("role")
            visibility = msg.get("visibility")
            if role in ("user", "assistant"):
                blocks = msg.get("content") or []
                injected_context = role == "user" and droid_injected_user_record(
                    sid, blocks, visibility
                )
                tool_feedback = (
                    role == "user"
                    and isinstance(blocks, list)
                    and any(
                        isinstance(b, dict)
                        and b.get("type") in ("tool_result", "advisor_tool_result")
                        for b in blocks
                    )
                )
                human = (
                    role == "user"
                    and visibility != "llm_only"
                    and not injected_context
                    and not tool_feedback
                )
                if role == "user" and (visibility == "llm_only" or injected_context):
                    return []
                if human and isinstance(blocks, list):
                    indices = [index for index, block in enumerate(blocks)
                               if not droid_reminder_block(block)]
                    out = _parts([blocks[index] for index in indices],
                                 {**m, "user_block_indices": indices}, sid, True)
                else:
                    out = _parts(msg.get("content"), m, sid, human)
                if role == "user" and not human:
                    revised = []
                    for a, t, c, v, x, z in out:
                        if tool_feedback and z.get("original_block_type") == "text":
                            block = blocks[z["block_index"]]
                            revised.append(
                                (
                                    "system",
                                    "metadata_event",
                                    dumps({"source_role": "user", "block": block}),
                                    "internal",
                                    x,
                                    {**z, "ambiguous_mixed_tool_feedback_text": True},
                                )
                            )
                        elif t in ("assistant_message", "user_message"):
                            revised.append(
                                (
                                    "system",
                                    "system_event",
                                    c,
                                    "environment",
                                    x,
                                    {**z, "source_role": "user", "system_injected": True},
                                )
                            )
                        else:
                            revised.append((a, t, c, v, x, z))
                    return revised
                return out
        return [("system", "metadata_event", dumps(r), "internal", sid, m)]


class GrokParser(BaseCliParser):
    """Parse grok_hooks source records using their native envelope."""

    source_format = "grok_hooks"

    def parse(self, r):
        typ = r.get("event")
        m = {
            "original_type": typ,
            "tool_name": r.get("tool_name"),
            "tool_call_id": r.get("tool_use_id"),
        }
        sid = r.get("tool_use_id")
        if typ == "UserPromptSubmit":
            return [("user", "user_message", content(r.get("prompt")), "public", None, m)]
        if typ == "PreToolUse":
            return [("assistant", "tool_call", content(r.get("tool_input")), "environment", sid, m)]
        if typ == "PostToolUse":
            return [("tool", "tool_result", content(r.get("tool_response")), "environment", sid, m)]
        if (
            typ in ("Stop", "StopCancelled")
            and isinstance(r.get("last_assistant_message"), str)
            and r["last_assistant_message"]
        ):
            remaining = {k: v for k, v in r.items() if k != "last_assistant_message"}
            return [
                (
                    "assistant",
                    "assistant_message",
                    r["last_assistant_message"],
                    "public",
                    None,
                    {**m, "stop_message": True},
                ),
                ("system", "system_event", dumps(remaining), "environment", None, m),
            ]
        if typ in ("Notification", "Stop", "StopCancelled", "StopFailure"):
            return [("system", "system_event", dumps(r), "environment", sid, m)]
        return [("system", "metadata_event", dumps(r), "internal", sid, m)]


class RunnerParser(BaseCliParser):
    """Parse project_runner source records using their native envelope."""

    source_format = "project_runner"

    def parse(self, r):
        typ = r.get("type")
        m = {"original_type": typ}
        sid = r.get("id")
        if typ == "user":
            return [
                ("user", "user_message", content(r.get("text", r.get("message"))), "public", sid, m)
            ]
        if typ == "assistant":
            return [
                (
                    "assistant",
                    "assistant_message",
                    content(r.get("text", r.get("message"))),
                    "public",
                    sid,
                    m,
                )
            ]
        return [("system", "metadata_event", dumps(r), "internal", sid, m)]


class SimpleMessageParser(BaseCliParser):
    """Parse simple_message source records using their native envelope."""

    source_format = "simple_message"

    def parse(self, r):
        role = r.get("type")
        sid = r.get("id")
        if role in ("user", "assistant") and isinstance(r.get("message"), str):
            return [
                (
                    role,
                    "user_message" if role == "user" else "assistant_message",
                    r["message"],
                    "public",
                    sid,
                    {"original_type": role},
                )
            ]
        return [("system", "metadata_event", dumps(r), "internal", sid, {"original_type": role})]


class XaiParser(BaseCliParser):
    """Parse xai_session_update source records using their native envelope."""

    source_format = "xai_session_update"

    def parse(self, r):
        update = (r.get("params") or {}).get("update") or {}
        kind = update.get("sessionUpdate")
        source_id = ((r.get("params") or {}).get("_meta") or {}).get("eventId")
        meta = {
            "original_type": kind,
            "tool_call_id": update.get("toolCallId"),
            "method": r.get("method"),
        }
        payload = update.get("content")
        if isinstance(payload, dict) and payload.get("type") == "text":
            payload = payload.get("text")
        if kind == "user_message_chunk":
            return [
                (
                    "user",
                    "user_message",
                    content(payload),
                    "public",
                    source_id,
                    {**meta, "chunk": True},
                )
            ]
        if kind == "agent_message_chunk":
            return [
                (
                    "assistant",
                    "assistant_message",
                    content(payload),
                    "public",
                    source_id,
                    {**meta, "chunk": True},
                )
            ]
        if kind == "agent_thought_chunk":
            return [
                (
                    "assistant",
                    "assistant_thinking",
                    content(payload),
                    "internal",
                    source_id,
                    {**meta, "chunk": True},
                )
            ]
        if kind == "tool_call":
            return [
                (
                    "assistant",
                    "tool_call",
                    content(update.get("rawInput", update)),
                    "environment",
                    source_id,
                    meta,
                )
            ]
        if kind == "tool_call_update" and update.get("status") in ("completed", "failed", "error"):
            return [
                (
                    "tool",
                    "tool_result",
                    content(update.get("rawOutput", payload)),
                    "environment",
                    source_id,
                    meta,
                )
            ]
        if kind == "tool_call_update":
            return [("system", "system_event", dumps(update), "environment", source_id, meta)]
        return [
            (
                "system",
                (
                    "system_event"
                    if kind in ("hook_execution", "turn_completed", "task_completed")
                    else "metadata_event"
                ),
                dumps(r),
                (
                    "environment"
                    if kind in ("hook_execution", "turn_completed", "task_completed")
                    else "internal"
                ),
                source_id,
                meta,
            )
        ]


class RoleContentParser(BaseCliParser):
    """Parse a direct role/content message without inferring nested semantics."""

    source_format = "role_content"

    def parse(self, record):
        role = record.get("role")
        if role in ("user", "assistant") and "content" in record:
            event_type = "user_message" if role == "user" else "assistant_message"
            return [
                (
                    role,
                    event_type,
                    content(record.get("content")),
                    "public",
                    record.get("id"),
                    {"original_type": "role_content"},
                )
            ]
        return [
            (
                "system",
                "metadata_event",
                dumps(record),
                "internal",
                record.get("id"),
                {"unrecognized_format": self.source_format},
            )
        ]


PARSERS = {
    parser.source_format: parser
    for parser in (
        ClaudeParser(),
        CodexParser(),
        OpenCodeParser(),
        CursorParser(),
        GeminiParser(),
        PiParser(),
        CopilotParser(),
        KimiParser(),
        DroidParser(),
        GrokParser(),
        RunnerParser(),
        SimpleMessageParser(),
        XaiParser(),
        RoleContentParser(),
    )
}
