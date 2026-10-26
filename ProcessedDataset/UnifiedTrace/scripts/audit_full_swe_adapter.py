#!/usr/bin/env python3
"""Read-only conversion audit of every available SWE main transcript file.

This checks parser coverage and event order without producing a full dataset or
reading compact/subagent transcript directories.
"""
import collections
import json
import os
from pathlib import Path

from swe_format import signature
from swe_chat_adapter import EXCLUDED_FORMATS, convert, skip_supplementary_record


ROOT = Path(__file__).resolve().parents[3] / "OriginalDataset-filter" / "SWE-Chat-filter"
OUTPUT = Path(os.environ.get("UNIFIED_AUDIT_OUTPUT", Path(__file__).resolve().parents[1] / "full_swe_adapter_audit.json"))


def main():
    files = [p for folder in ("transcripts", "transcripts1") for p in sorted((ROOT / folder).glob("*.jsonl"))]
    formats = collections.Counter()
    event_types = collections.defaultdict(collections.Counter)
    failures = []
    invalid_lines = collections.Counter()
    multi_record_files = collections.Counter()
    ignored_subagent_files = collections.Counter()
    for index, path in enumerate(files, 1):
        fmt = signature(path)
        formats[fmt] += 1
        if fmt in EXCLUDED_FORMATS or fmt == "unclassified":
            failures.append({"path": str(path.relative_to(ROOT)), "format": fmt, "reason": "unsupported_filtered_source_format"})
            continue
        try:
            events, issues, _ = convert(path, "audit")
            if not events:
                failures.append({"path": str(path.relative_to(ROOT)), "format": fmt, "reason": "zero_events"})
                continue
            last_raw = None
            last_block = None
            seen_raw = collections.Counter()
            for expected, event in enumerate(events):
                if event["event_id"] != expected:
                    raise ValueError(f"event_id {event['event_id']} expected {expected}")
                meta = json.loads(event["metadata"])
                raw = meta.get("raw_record_index")
                block = meta.get("block_index")
                if raw is not None:
                    if last_raw is not None and raw < last_raw:
                        raise ValueError(f"raw order reversed at {raw}")
                    if raw == last_raw and block is not None and last_block is not None and block < last_block:
                        raise ValueError(f"block order reversed at {raw}:{block}")
                    seen_raw[raw] += 1
                    last_raw, last_block = raw, block
                event_types[fmt][event["event_type"]] += 1
            if any(count > 1 for count in seen_raw.values()):
                multi_record_files[fmt] += 1
            invalid_lines[fmt] += sum(issue.get("reason") == "invalid_jsonl" for issue in issues)
            # Count only clearly labelled subagent records. They are excluded
            # by the adapter and never enter the event sequence.
            if fmt in ("claude_tree", "grok_hooks", "xai_session_update"):
                from swe_chat_adapter import records
                n = 0
                for _, record, _ in records(path):
                    if not isinstance(record, dict):
                        continue
                    if skip_supplementary_record(record):
                        n += 1
                if n:
                    ignored_subagent_files[fmt] += 1
        except Exception as exc:
            failures.append({"path": str(path.relative_to(ROOT)), "format": fmt, "reason": type(exc).__name__, "detail": str(exc)[:300]})
        if index % 500 == 0:
            print(f"audited {index}/{len(files)} files; failures={len(failures)}", flush=True)
    report = {
        "scope": "all original main transcript files in filtered SWE-chat transcripts/ and transcripts1/ only",
        "files": len(files),
        "format_counts": dict(sorted(formats.items())),
        "event_type_counts_by_format": {k: dict(v) for k, v in sorted(event_types.items())},
        "files_with_multievent_raw_records_by_format": dict(sorted(multi_record_files.items())),
        "files_with_explicit_subagent_records_ignored_by_format": dict(sorted(ignored_subagent_files.items())),
        "invalid_jsonl_lines_by_format": dict(sorted(invalid_lines.items())),
        "failures": failures,
        "failure_count": len(failures),
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("files", "format_counts", "failure_count", "invalid_jsonl_lines_by_format")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
