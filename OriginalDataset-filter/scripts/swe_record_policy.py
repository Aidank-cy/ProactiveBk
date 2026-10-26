"""Source-record inclusion rules shared by SWE filtering and CLI conversion.

These predicates identify auxiliary records and injected user-role material.
They do not infer task outcomes or classify query types.
"""

EXCLUDED_FORMATS = {"zed_reconstruction", "empty_source_record", "unparsed_source_wrapper"}

CODEX_INJECTED_USER_TAGS = (
    "environment_context",
    "turn_aborted",
    "skill",
    "codex_internal_context",
    "recommended_plugins",
    "user_shell_command",
    "user_action",
    "subagent_notification",
    "task-notification",
    "command-name",
    "local-command-stdout",
)


def skip_supplementary_record(record):
    """Exclude source records explicitly attributed to a side branch."""
    if record.get("isSidechain") is True:
        return True
    if (record.get("type") == "custom_message"
            and str(record.get("customType") or "").startswith(("subagent-", "subagent_"))):
        return True
    if (
        record.get("type") == "progress"
        and isinstance(record.get("data"), dict)
        and record["data"].get("type") == "agent_progress"
    ):
        return True
    if record.get("event") in ("SubagentStart", "SubagentStop"):
        return True
    if (
        record.get("method") in ("session/update", "_x.ai/session/update")
        and isinstance(record.get("params"), dict)
        and (record["params"].get("update") or {}).get("sessionUpdate")
        in ("subagent_spawned", "subagent_finished")
    ):
        return True
    return False


def codex_injected_user_content(blocks):
    if not isinstance(blocks, list) or not blocks:
        return False
    return any(
        isinstance(block, dict)
        and isinstance(block.get("text"), str)
        and any(
            block["text"].lstrip().startswith(f"<{tag}>")
            or block["text"].lstrip().startswith(f"<{tag} ")
            for tag in CODEX_INJECTED_USER_TAGS
        ) or (
            isinstance(block, dict)
            and isinstance(block.get("text"), str)
            and block["text"].startswith("# AGENTS.md instructions for ")
            and block["text"].rstrip().endswith("</INSTRUCTIONS>")
        )
        for block in blocks
    )


def codex_user_body_without_auxiliary(body, runtime_record):
    if not isinstance(body, str):
        return body
    stripped = body.lstrip()
    for tag in CODEX_INJECTED_USER_TAGS:
        if stripped.startswith(f"<{tag}>") or stripped.startswith(f"<{tag} "):
            closing = f"</{tag}>"
            if closing in stripped:
                remaining = stripped.split(closing, 1)[1]
                # A tagged prefix followed by user text is an indivisible
                # source user body. Its author cannot be inferred from tags.
                return body if remaining.strip() else None
            return body
    if (runtime_record and stripped.startswith("# AGENTS.md instructions for ")
            and stripped.rstrip().endswith("</INSTRUCTIONS>")):
        return None
    return body


def opencode_user_text_without_auxiliary(body):
    if (
        not isinstance(body, str)
        or not body.startswith("<system-reminder>")
        or "</system-reminder>" not in body
    ):
        return body
    remaining = body.split("</system-reminder>", 1)[1]
    remaining = remaining.replace("<!-- OMO_INTERNAL_INITIATOR -->", "")
    return body if remaining.strip() else None


def claude_human_user_record(record):
    return (
        record.get("type") == "user"
        and not record.get("isMeta")
        and not record.get("isSidechain")
        and not str(record.get("uuid") or "").startswith("context-")
    )


def claude_strip_auxiliary_prefix(body):
    if not isinstance(body, str):
        return body, None
    for tag in ("system_instruction", "system-reminder"):
        opening = f"<{tag}>"
        closing = f"</{tag}>"
        if body.startswith(opening) and closing in body:
            remaining = body.split(closing, 1)[1]
            return (body, None) if remaining.strip() else (None, tag)
    return body, None


def opencode_auxiliary_user_part(part):
    return isinstance(part, dict) and part.get("type") in ("compaction", "agent")


def copilot_human_user_record(data):
    return data.get("source") in (None, "user", "human")


def pi_human_user_message(message):
    return message.get("attribution") in (None, "user", "human")


def kimi_human_user_message(message):
    return (message.get("origin") or {}).get("kind") == "user"


def kimi_duplicate_prompt_record(record):
    # The delivered prompt is repeated as context.append_message.
    return record.get("type") == "turn.prompt"


def droid_injected_user_record(source_id, blocks, visibility):
    return visibility == "llm_only" or (
        str(source_id or "").startswith("context-")
        and isinstance(blocks, list)
        and any(
            isinstance(block, dict)
            and isinstance(block.get("text"), str)
            and block["text"].startswith("<system-reminder>")
            for block in blocks
        )
    )


def droid_reminder_block(block):
    if not (
        isinstance(block, dict)
        and isinstance(block.get("text"), str)
        and block["text"].lstrip().startswith("<system-reminder>")
    ):
        return False
    text = block["text"].lstrip()
    if "</system-reminder>" not in text:
        return False
    return not text.split("</system-reminder>", 1)[1].strip()
