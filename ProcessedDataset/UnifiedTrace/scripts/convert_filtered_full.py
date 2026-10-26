#!/usr/bin/env python3
"""Convert the three full filtered sources; never read unfiltered originals.

Use --limit-per-source only for a small smoke test. A limited output is marked
as such in its report and is not a full Unified Trace dataset.
"""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

from swe_format import signature
from unified_schema import EVENT_SCHEMA, TRACE_SCHEMA
from swe_chat_adapter import (
    convert as convert_swe,
    count_user_turns,
    main_agent_model_candidates,
    resolve_trace_model,
)
from trace_ids import trace_id as make_trace_id
from wildchat_adapter import convert_filtered_full as convert_wildchat_full


ROOT = Path(__file__).resolve().parents[3]
FILTERED = ROOT / "OriginalDataset-filter"


def manifest(directory):
    return json.loads((directory / "filter_manifest.json").read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit-per-source", type=int, default=None)
    args = parser.parse_args()
    if args.limit_per_source is not None and args.limit_per_source < 1:
        parser.error("--limit-per-source must be positive")
    output = args.output_dir.resolve()
    if output == FILTERED.resolve() or FILTERED.resolve() in output.parents:
        parser.error("output must be outside OriginalDataset-filter")
    output.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".unified-full-stage-", dir=output))
    names = ("traces.parquet", "events.parquet", "conversion_report.json", "schema_inspection.json")
    trace_count = Counter()
    event_count = Counter()
    model_resolution = Counter()
    format_count = Counter()
    parse_issue_count = Counter()
    trace_buffer = []
    event_buffer = []
    tw = pq.ParquetWriter(stage / "traces.parquet", TRACE_SCHEMA, compression="zstd")
    ew = pq.ParquetWriter(stage / "events.parquet", EVENT_SCHEMA, compression="zstd")

    def flush():
        if trace_buffer:
            tw.write_table(pa.Table.from_pylist(trace_buffer, schema=TRACE_SCHEMA))
            trace_buffer.clear()
        if event_buffer:
            ew.write_table(pa.Table.from_pylist(event_buffer, schema=EVENT_SCHEMA))
            event_buffer.clear()

    def add(trace, events):
        source = trace["source"]
        if trace["trace_id"] != make_trace_id(source, trace_count[source]):
            raise ValueError(f"nonsequential trace ID: {trace['trace_id']}")
        for ordinal, event in enumerate(events):
            if event["trace_id"] != trace["trace_id"] or event["event_id"] != ordinal:
                raise ValueError(f"nonsequential event in {trace['trace_id']}")
        trace_count[source] += 1
        event_count[source] += len(events)
        trace_buffer.append(trace)
        event_buffer.extend(events)
        if len(trace_buffer) >= 1000 or len(event_buffer) >= 10000:
            flush()

    try:
        for directory_name, source in (
            ("WildChat-1M-filter", "wildchat_1m"),
            ("WildChat-4.8M-filter", "wildchat_4_8m"),
        ):
            directory = FILTERED / directory_name
            source_manifest = manifest(directory)
            for trace, events in convert_wildchat_full(directory, source, args.limit_per_source):
                add(trace, events)
            expected = min(source_manifest["filtered_rows"], args.limit_per_source or source_manifest["filtered_rows"])
            if trace_count[source] != expected:
                raise ValueError(f"{source}: converted {trace_count[source]} rows, expected {expected}")
            print(source, trace_count[source], event_count[source], flush=True)

        swe = FILTERED / "SWE-Chat-filter"
        swe_manifest = manifest(swe)
        sessions = pq.read_table(swe / "sessions.parquet").to_pylist()
        logs = pq.read_table(swe / "session_logs.parquet").to_pylist()
        if len(sessions) != len(logs) or len(sessions) != swe_manifest["session_count"]:
            raise ValueError("filtered SWE Session/log counts differ from manifest")
        by_id = {row["session_id"]: row for row in sessions}
        if len(by_id) != len(sessions) or len({row["session_id"] for row in logs}) != len(logs):
            raise ValueError("duplicate SWE Session ID in filtered source")
        selected_logs = logs[: args.limit_per_source] if args.limit_per_source else logs
        for index, row in enumerate(selected_logs):
            sid = row["session_id"]
            path = row["transcript_path"]
            session = by_id.get(sid)
            if session is None or session["transcript_path"] != path:
                raise ValueError(f"filtered SWE Session/log mapping mismatch: {sid}")
            relative = Path(path or "")
            if not relative.parts or relative.is_absolute() or ".." in relative.parts or relative.parts[0] not in ("transcripts", "transcripts1"):
                raise ValueError(f"invalid filtered main transcript path: {path}")
            full_path = swe / relative
            if not full_path.is_file():
                raise ValueError(f"missing filtered main transcript: {full_path}")
            trace_id = make_trace_id("swe_chat", index)
            events, issues, _ = convert_swe(full_path, trace_id)
            parse_issue_count.update(issue.get("reason", "unknown") for issue in issues)
            source_format = signature(full_path)
            format_count[source_format] += 1
            models = main_agent_model_candidates(full_path, source_format)
            model, basis = resolve_trace_model(session.get("model"), models)
            model_resolution[basis] += 1
            trace = {
                "trace_id": trace_id,
                "source": "swe_chat",
                "source_id": sid,
                "query_type": None,
                "language": None,
                "model": model,
                "user_turn_count": count_user_turns(events, source_format),
            }
            add(trace, events)
            if (index + 1) % 1000 == 0:
                print("swe_chat", index + 1, event_count["swe_chat"], flush=True)
        if trace_count["swe_chat"] != len(selected_logs):
            raise ValueError("SWE conversion count differs from filtered Session count")
        flush()
    except Exception:
        tw.close()
        ew.close()
        shutil.rmtree(stage)
        raise
    tw.close()
    ew.close()
    report = {
        "input_scope": "filtered_full" if args.limit_per_source is None else "filtered_full_limited_smoke_test",
        "filtered_source_directory": str(FILTERED),
        "limit_per_source": args.limit_per_source,
        "source_trace_counts": dict(trace_count),
        "source_event_counts": dict(event_count),
        "swe_model_resolution": dict(model_resolution),
        "swe_format_counts": dict(format_count),
        "swe_parse_issue_counts": dict(parse_issue_count),
        "query_type_policy": "null for every trace",
    }
    inspection = {
        "input_scope": report["input_scope"],
        "filtered_source_manifests": {
            name: manifest(FILTERED / name)["source_revision"]
            for name in ("WildChat-1M-filter", "WildChat-4.8M-filter", "SWE-Chat-filter")
        },
        "swe_format_counts": dict(format_count),
    }
    (stage / "conversion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (stage / "schema_inspection.json").write_text(json.dumps(inspection, ensure_ascii=False, indent=2) + "\n")
    backup = Path(tempfile.mkdtemp(prefix=".unified-full-backup-", dir=output))
    previous = {name for name in names if (output / name).is_file()}
    try:
        for name in names:
            if name in previous:
                os.link(output / name, backup / name)
        for name in names:
            os.replace(stage / name, output / name)
    except Exception:
        for name in names:
            if (backup / name).is_file():
                os.replace(backup / name, output / name)
            elif name not in previous and (output / name).is_file():
                (output / name).unlink()
        raise
    finally:
        shutil.rmtree(backup)
        if stage.exists():
            shutil.rmtree(stage)
    print("conversion complete", dict(trace_count), dict(event_count), flush=True)


if __name__ == "__main__":
    main()
