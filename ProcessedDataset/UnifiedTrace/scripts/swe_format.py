"""Identify a SWE CLI transcript family from its source envelope."""
import json
import re

def signature(path):
    header = ""
    with path.open(encoding="utf-8", errors="replace") as stream:
        for _ in range(80):
            line = stream.readline()
            if not line:
                break
            if len(header) < 16384:
                header += line[:16384 - len(header)]
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            typ = record.get("type")
            msg = record.get("message")
            # Complete JSON documents use a messages array. Inspect its actual
            # entries before the header fallback: Gemini's later "info" records
            # can otherwise make a Gemini document look like OpenCode.
            document_messages = record.get("messages")
            if isinstance(document_messages, list) and document_messages:
                first_message = next((item for item in document_messages if isinstance(item, dict)), None)
                if first_message is not None:
                    if isinstance(first_message.get("info"), dict) and isinstance(first_message.get("parts"), list):
                        return "opencode_document"
                    if first_message.get("type") in ("user", "gemini", "info", "warning") and "id" in first_message:
                        return "gemini_document"
            if record.get("method") in ("session/update", "_x.ai/session/update"):
                return "xai_session_update"
            if record.get("event") in ("SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "StopCancelled", "StopFailure", "Notification", "SubagentStart", "SubagentStop", "PreCompact"):
                return "grok_hooks"
            if typ in ("response_item", "event_msg", "turn_context", "session_meta") and ("payload" in record or "item" in record):
                return "codex_rollout"
            if typ in ("session.start", "assistant.message", "tool.execution_start") and "data" in record:
                return "copilot_events"
            if typ in ("turn.prompt", "context.append_loop_event", "profile.bind"):
                return "kimi_wire"
            if typ == "session_start" and "version" in record:
                return "factory_droid"
            if typ == "session" and "repo_path" in record and "metadata" in record:
                return "project_runner"
            if typ == "session" and ("version" in record or "cwd" in record):
                return "pi_tree"
            if typ == "title" and "updatedAt" in record:
                return "pi_tree"
            if typ == "gemini" or (typ == "user" and "content" in record and "id" in record):
                return "gemini_document"
            if record.get("role") in ("user", "assistant") and isinstance(msg, dict):
                return "cursor_messages"
            if typ in ("user", "assistant", "tool_use", "tool_result") and isinstance(msg, dict):
                return "zed_reconstruction" if "_swe_chat_reconstruction" in record else "claude_tree"
            if typ in ("user", "assistant") and isinstance(msg, str):
                return "simple_message"
            if typ in ("user", "assistant") and "text" in record:
                return "project_runner"
            if typ == "message" and isinstance(msg, dict) and "role" in msg:
                return "pi_tree"
            if "info" in record and ("messages" in record or "parts" in record):
                return "opencode_document"
            if record.get("role") in ("user", "assistant") and "content" in record:
                return "role_content"
            if typ == "queue-operation" or typ in ("progress", "summary", "file-history-snapshot") and ("parentUuid" in record or "leafUuid" in record):
                return "claude_tree"
            if typ in ("pr-link", "custom-title", "agent-name", "ai-title") and "sessionId" in record:
                return "claude_tree"
    # Pretty-printed JSON documents often have no complete object in the first 80 lines.
    # Pretty-printed documents do not yield a complete JSON object from any
    # individual line. Their *top-level* first key identifies the envelope;
    # searching for "info" anywhere can match a later Gemini info message.
    if re.match(r'\s*\{\s*"sessionId"\s*:', header):
        return "gemini_document"
    if re.match(r'\s*\{\s*"info"\s*:', header):
        return "opencode_document"
    if '"_swe_chat_unparsed"' in header:
        return "unparsed_source_wrapper"
    if not header.strip() or header.strip() == "{}":
        return "empty_source_record"
    return "unclassified"


