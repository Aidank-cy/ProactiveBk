#!/usr/bin/env python3
"""Remove invalid SWE main Sessions before sampling or Unified Trace conversion.

Use the local CLI parsers with the same source-format rules as conversion.
The original dataset is never modified. The filtered
directory is replaced only after its staged copy and metadata pass validation.
"""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
from swe_format import signature
from swe_chat_adapter import convert
from swe_record_policy import EXCLUDED_FORMATS


INTERACTION_TYPES = {
    "user_message",
    "assistant_message",
    "assistant_thinking",
    "tool_call",
    "tool_result",
}


def has_interaction_content(events):
    """Ignore lifecycle/metadata-only records and blank interaction payloads."""
    return any(
        event["event_type"] in INTERACTION_TYPES
        and event["content"] is not None
        and bool(str(event["content"]).strip())
        for event in events
    )


def unmatched_tool_result_ids(events):
    """Find result IDs without a call ID in the same parsed main-agent transcript."""
    calls = set()
    results = set()
    for event in events:
        if event["event_type"] not in ("tool_call", "tool_result"):
            continue
        metadata = json.loads(event["metadata"])
        call_id = metadata.get("tool_call_id") or metadata.get("call_id")
        if not call_id:
            continue
        if event["event_type"] == "tool_call":
            calls.add(call_id)
        else:
            results.add(call_id)
    return sorted(results - calls)


def inspect_sessions(dataset):
    sessions = pq.read_table(
        dataset / "sessions.parquet", columns=["session_id", "transcript_path"]
    )
    logs = pq.read_table(
        dataset / "session_logs.parquet",
        columns=["session_id", "transcript_path", "compact_transcript_path"],
    )
    session_rows = sessions.to_pylist()
    log_rows = logs.to_pylist()
    session_ids = [row["session_id"] for row in session_rows]
    log_ids = [row["session_id"] for row in log_rows]
    if (
        len(session_ids) != len(set(session_ids))
        or set(session_ids) != set(log_ids)
        or len(log_ids) != len(set(log_ids))
    ):
        raise ValueError("SWE Session and log IDs must be unique and identical before filtering")
    session_by_id = {row["session_id"]: row for row in session_rows}
    removed = {}
    format_counts = Counter()
    for index, row in enumerate(log_rows, 1):
        sid = row["session_id"]
        path = row["transcript_path"]
        if session_by_id[sid]["transcript_path"] != path:
            raise ValueError(f"Session/log transcript path mismatch: {sid}")
        if not path:
            removed[sid] = {"reason": "missing_main_transcript_path", "transcript_path": path}
            continue
        relative = Path(path)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0] not in ("transcripts", "transcripts1")
        ):
            raise ValueError(f"unsafe main transcript path: {path}")
        source = dataset / relative
        if not source.is_file():
            removed[sid] = {"reason": "missing_main_transcript_file", "transcript_path": path}
            continue
        fmt = signature(source)
        format_counts[fmt] += 1
        if fmt in EXCLUDED_FORMATS or fmt == "unclassified":
            removed[sid] = {
                "reason": "uninterpretable_main_transcript",
                "format": fmt,
                "transcript_path": path,
            }
            continue
        events, issues, _ = convert(source, sid)
        main_content = has_interaction_content(events)
        if not main_content:
            removed[sid] = {
                "reason": "no_main_agent_interaction_content",
                "format": fmt,
                "transcript_path": path,
                "event_count": len(events),
                "parse_issues": issues[:10],
            }
        else:
            unmatched_results = unmatched_tool_result_ids(events)
            if unmatched_results:
                removed[sid] = {
                    "reason": "unmatched_tool_result_ids",
                    "format": fmt,
                    "transcript_path": path,
                    "unmatched_tool_result_count": len(unmatched_results),
                    "unmatched_tool_result_ids": unmatched_results,
                    "parse_issues": issues[:10],
                }
        if index % 1000 == 0:
            print(f"inspected {index}/{len(log_rows)} Sessions; removed={len(removed)}", flush=True)
    return removed, dict(format_counts), log_rows


def session_keyed_tables(dataset):
    return [
        path
        for path in sorted(dataset.glob("*.parquet"))
        if "session_id" in pq.ParquetFile(path).schema_arrow.names
    ]


def rewrite_table_if_needed(stage_file, removed_ids):
    parquet = pq.ParquetFile(stage_file)
    id_array = pa.array(sorted(removed_ids), type=pa.string())
    has_removed = any(
        pc.any(pc.is_in(batch.column(0), value_set=id_array)).as_py()
        for batch in parquet.iter_batches(batch_size=65536, columns=["session_id"])
    )
    if not has_removed:
        return 0
    temp = stage_file.with_name(stage_file.name + ".filtered.tmp")
    writer = pq.ParquetWriter(temp, parquet.schema_arrow, compression="zstd")
    kept = 0
    try:
        for batch in parquet.iter_batches(batch_size=8192):
            ids = batch.column(parquet.schema_arrow.get_field_index("session_id"))
            filtered = batch.filter(pc.invert(pc.is_in(ids, value_set=id_array)))
            if filtered.num_rows:
                writer.write_table(pa.Table.from_batches([filtered], schema=parquet.schema_arrow))
            kept += filtered.num_rows
    finally:
        writer.close()
    os.replace(temp, stage_file)
    return parquet.metadata.num_rows - kept


def remove_orphaned_transcripts(stage, removed, logs, tasks):
    retained_main = {
        row["transcript_path"]
        for row in logs
        if row["session_id"] not in removed and row["transcript_path"]
    }
    retained_compact = {
        row["compact_transcript_path"]
        for row in logs
        if row["session_id"] not in removed and row["compact_transcript_path"]
    }
    candidate_main = {
        row["transcript_path"]
        for row in logs
        if row["session_id"] in removed and row["transcript_path"]
    }
    candidate_compact = {
        row["compact_transcript_path"]
        for row in logs
        if row["session_id"] in removed and row["compact_transcript_path"]
    }
    retained_subagent = {
        row["transcript_path"]
        for row in tasks
        if row["session_id"] not in removed and row["transcript_path"]
    }
    candidate_subagent = {
        row["transcript_path"]
        for row in tasks
        if row["session_id"] in removed and row["transcript_path"]
    }
    removed_files = []
    for relative in sorted(
        (candidate_main - retained_main)
        | (candidate_compact - retained_compact)
        | (candidate_subagent - retained_subagent)
    ):
        path = Path(relative)
        if (
            path.is_absolute()
            or ".." in path.parts
            or path.parts[0]
            not in ("transcripts", "transcripts1", "transcripts_compact", "transcripts_subagent")
        ):
            raise ValueError(f"unsafe transcript path: {relative}")
        target = stage / path
        if target.is_file():
            target.unlink()
            removed_files.append(relative)
    return removed_files


def apply_filter(dataset, keep_backup=True):
    dataset = dataset.resolve()
    removed, formats, log_rows = inspect_sessions(dataset)
    old_manifest = json.loads((dataset / "filter_manifest.json").read_text())
    tasks = pq.read_table(
        dataset / "subagent_tasks.parquet", columns=["session_id", "transcript_path"]
    ).to_pylist()
    if not removed:
        print("no SWE Sessions require filtering", flush=True)
        return None
    print(
        "removed Sessions by reason:",
        dict(Counter(item["reason"] for item in removed.values())),
        flush=True,
    )
    stage = Path(tempfile.mkdtemp(prefix=f".{dataset.name}.filtered-", dir=dataset.parent))
    backup = dataset.parent / f".{dataset.name}.backup-before-quality-filter-{uuid.uuid4().hex}"
    try:
        # Hard links keep the 44 GB source copy unchanged and avoid another full copy.
        # Every modified Parquet and manifest is written to a new inode first.
        shutil.copytree(dataset, stage, dirs_exist_ok=True, copy_function=os.link, symlinks=True)
        table_removals = {}
        for path in session_keyed_tables(stage):
            count = rewrite_table_if_needed(path, set(removed))
            table_removals[path.name] = count
            print(f"filtered {path.name}: {count} rows", flush=True)
        removed_files = remove_orphaned_transcripts(stage, removed, log_rows, tasks)
        old_reasons = Counter(old_manifest.get("removed_session_reasons", {}))
        old_reasons.update(item["reason"] for item in removed.values())
        old_table_removals = Counter(old_manifest.get("removed_session_keyed_rows_by_table", {}))
        old_table_removals.update(table_removals)
        manifest = {
            **old_manifest,
            "retention_policy": "unique Session ID and nonblank extractable main-agent interaction content in its main transcript; remove Sessions with no main transcript, no main-agent interaction, uninterpretable main format, or a tool result ID without a matching tool call ID in the same main transcript; agent- names alone are not exclusion evidence",
            "empty_content_policy": "same CLI-specific source parser as UnifiedTrace; lifecycle, metadata, and sidechain-only records do not qualify as main-agent interaction content",
            "session_count": pq.ParquetFile(stage / "sessions.parquet").metadata.num_rows,
            "main_transcript_count": sum(
                1 for row in log_rows if row["session_id"] not in removed and row["transcript_path"]
            ),
            "removed_sessions": old_manifest.get("removed_sessions", 0) + len(removed),
            "removed_empty_or_uninterpretable_sessions": old_manifest.get("removed_empty_or_uninterpretable_sessions", 0) + sum(
                item["reason"] in ("no_main_agent_interaction_content", "uninterpretable_main_transcript")
                for item in removed.values()
            ),
            "removed_session_reasons": dict(old_reasons),
            "removed_session_details": old_manifest.get("removed_session_details", []) + [
                {"session_id": sid, **details} for sid, details in sorted(removed.items())
            ],
            "removed_session_keyed_rows_by_table": dict(old_table_removals),
            "removed_transcript_files": old_manifest.get("removed_transcript_files", []) + removed_files,
            "inspected_format_counts": formats,
            "copy_verification": old_manifest.get("copy_verification", "")
            + "; filtered stage validated against retained Session IDs",
        }
        temp_manifest = stage / "filter_manifest.json.tmp"
        temp_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        os.replace(temp_manifest, stage / "filter_manifest.json")
        if (
            pq.ParquetFile(stage / "session_logs.parquet").metadata.num_rows
            != manifest["session_count"]
        ):
            raise ValueError("filtered Session and log row counts differ")
        for row in pq.read_table(
            stage / "session_logs.parquet", columns=["session_id", "transcript_path"]
        ).to_pylist():
            if row["session_id"] in removed or not (stage / row["transcript_path"]).is_file():
                raise ValueError(f"retained Session mapping invalid: {row['session_id']}")
        dataset.rename(backup)
        try:
            stage.rename(dataset)
        except Exception:
            backup.rename(dataset)
            raise
        if not keep_backup:
            shutil.rmtree(backup)
            backup = None
        print(
            f"published filtered SWE dataset: {manifest['session_count']} Sessions, removed {len(removed)}",
            flush=True,
        )
        return backup
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "OriginalDataset-filter" / "SWE-Chat-filter"
    )
    parser.add_argument(
        "--discard-backup",
        action="store_true",
        help="Only for a disposable build staging directory",
    )
    args = parser.parse_args()
    apply_filter(args.dataset, keep_backup=not args.discard_backup)
