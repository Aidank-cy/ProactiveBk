#!/usr/bin/env python3
"""Profile full SWE main transcripts for deterministic, format-diverse sampling.

This is read-only source inspection. It does not emit unified events or modify
the source; sample_1k.py consumes the resulting Parquet table.
"""
import collections
import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from swe_format import signature
from swe_chat_adapter import records
from swe_record_policy import CODEX_INJECTED_USER_TAGS, EXCLUDED_FORMATS


ROOT = Path(__file__).resolve().parents[1] / "SWE-Chat-filter"
OUTPUT = Path(__file__).resolve().parents[1] / "swe_sampling_profiles.parquet"
REPORT = Path(__file__).resolve().parents[1] / "swe_sampling_profile_report.json"
EXCLUDED = EXCLUDED_FORMATS | {"unclassified"}
FEATURES = ("multi_block", "thinking", "tool_call", "tool_result", "structured_output", "queue", "subagent_marker", "system_injection", "grouped_fields")


def inspect(path):
    found = set()
    record_count = invalid_lines = 0
    layout = None
    for _, r, record_format in records(path):
        record_count += 1
        layout = layout or record_format
        if record_format == "invalid_jsonl":
            invalid_lines += 1
            continue
        if not isinstance(r, dict):
            continue
        typ = r.get("type")
        event = r.get("event")
        loop_kind = event.get("type") if isinstance(event, dict) else None
        msg = r.get("message") if isinstance(r.get("message"), dict) else {}
        payload = r.get("payload") or r.get("item") or {}
        if not isinstance(payload, dict):
            payload = {}
        data = r.get("data") if isinstance(r.get("data"), dict) else {}
        update = (r.get("params") or {}).get("update") if isinstance(r.get("params"), dict) else {}
        if not isinstance(update, dict):
            update = {}
        blocks = msg.get("content") if isinstance(msg.get("content"), list) else payload.get("content")
        if not isinstance(blocks, list):
            blocks = []
        parts = r.get("parts") if isinstance(r.get("parts"), list) else []
        requests = data.get("toolRequests") if isinstance(data.get("toolRequests"), list) else []
        calls = r.get("toolCalls") if isinstance(r.get("toolCalls"), list) else []
        if max(len(blocks), len(parts), len(requests), len(calls)) > 1:
            found.add("multi_block")
        if parts or requests or calls or r.get("thoughts"):
            found.add("grouped_fields")
        block_types = {b.get("type") for b in blocks if isinstance(b, dict)}
        part_types = {p.get("type") for p in parts if isinstance(p, dict)}
        if block_types & {"thinking", "redacted_thinking", "think"} or "reasoning" in part_types or r.get("thoughts") or data.get("reasoningText") or payload.get("type") in ("reasoning", "agent_reasoning") or update.get("sessionUpdate") == "agent_thought_chunk" or loop_kind == "content.part" and isinstance(event.get("part"), dict) and event["part"].get("type") in ("think", "thinking"):
            found.add("thinking")
        if block_types & {"tool_use", "server_tool_use", "toolCall"} or "tool" in part_types or requests or calls or event == "PreToolUse" or typ == "tool.execution_start" or payload.get("type") in ("function_call", "custom_tool_call", "web_search_call", "tool_search_call") or update.get("sessionUpdate") == "tool_call" or loop_kind == "tool.call":
            found.add("tool_call")
        if block_types & {"tool_result", "advisor_tool_result"} or msg.get("role") in ("toolResult", "bashExecution") or event == "PostToolUse" or typ == "tool.execution_complete" or payload.get("type") in ("function_call_output", "custom_tool_call_output", "tool_search_output") or any(isinstance(p, dict) and p.get("type") == "tool" and isinstance(p.get("state"), dict) and p["state"].get("status") in ("completed", "error") for p in parts) or any(isinstance(c, dict) and any(k in c for k in ("result", "response", "error")) for c in calls) or update.get("sessionUpdate") == "tool_call_update" and update.get("status") in ("completed", "failed", "error") or loop_kind == "tool.result":
            found.add("tool_result")
        output_values = [b.get("content") for b in blocks if isinstance(b, dict) and b.get("type") in ("tool_result", "advisor_tool_result")]
        output_values += [p["state"].get("output") for p in parts if isinstance(p, dict) and p.get("type") == "tool" and isinstance(p.get("state"), dict)]
        output_values += [c.get("result", c.get("response", c.get("error"))) for c in calls if isinstance(c, dict)]
        output_values += [payload.get("output"), data.get("output"), update.get("rawOutput")]
        if any(isinstance(value, (dict, list)) for value in output_values):
            found.add("structured_output")
        if typ == "queue-operation":
            found.add("queue")
        if r.get("isSidechain") is True or data.get("type") == "agent_progress" or event in ("SubagentStart", "SubagentStop") or update.get("sessionUpdate") in ("subagent_spawned", "subagent_finished") or isinstance(loop_kind, str) and loop_kind.startswith("subagent."):
            found.add("subagent_marker")
        if r.get("isMeta") or msg.get("visibility") == "llm_only" or str(r.get("uuid") or "").startswith("context-"):
            found.add("system_injection")
        if typ == "response_item" and payload.get("type") == "message" and payload.get("role") == "user":
            text = "\n".join(str(b.get("text", "")) for b in blocks if isinstance(b, dict)).lstrip()
            if any(text.startswith(f"<{tag}>") or text.startswith(f"<{tag} ") for tag in CODEX_INJECTED_USER_TAGS):
                found.add("system_injection")
    return {"record_count": record_count, "invalid_jsonl_lines": invalid_lines, "layout": layout or "empty", **{name: name in found for name in FEATURES}}


def main():
    source_manifest = json.loads((ROOT / "filter_manifest.json").read_text())
    files = [p for folder in ("transcripts", "transcripts1") for p in sorted((ROOT / folder).glob("*.jsonl"))]
    rows = []
    families = collections.Counter()
    failures = []
    for index, path in enumerate(files, 1):
        family = signature(path)
        if family in EXCLUDED:
            continue
        try:
            profile = inspect(path)
        except Exception as exc:
            failures.append({"path": str(path.relative_to(ROOT)), "reason": type(exc).__name__, "detail": str(exc)[:200]})
            continue
        row = {"transcript_path": str(path.relative_to(ROOT)), "format_family": family,
               "file_size": path.stat().st_size, **profile}
        rows.append(row)
        families[family] += 1
        if index % 500 == 0:
            print(f"profiled {index}/{len(files)} files", flush=True)
    if failures:
        REPORT.write_text(json.dumps({"failures": failures}, ensure_ascii=False, indent=2) + "\n")
        raise RuntimeError(f"{len(failures)} SWE transcripts could not be profiled")
    schema = pa.schema([("transcript_path", pa.string()), ("format_family", pa.string()), ("file_size", pa.int64()),
                        ("record_count", pa.int64()), ("invalid_jsonl_lines", pa.int64()), ("layout", pa.string()),
                        *[(name, pa.bool_()) for name in FEATURES]])
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), OUTPUT.with_suffix(".parquet.tmp"), compression="zstd")
    OUTPUT.with_suffix(".parquet.tmp").replace(OUTPUT)
    report = {"source_revision": source_manifest["source_revision"],
              "filtered_source_manifest_sha256": hashlib.sha256((ROOT / "filter_manifest.json").read_bytes()).hexdigest(),
              "files_scanned": len(files),
              "main_files_profiled": len(rows), "format_counts": dict(sorted(families.items())),
              "feature_file_counts": {name: sum(row[name] for row in rows) for name in FEATURES},
              "agent_named_main_files_profiled": sum(Path(row["transcript_path"]).stem.startswith("agent-") for row in rows),
              "failed_files": 0}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
