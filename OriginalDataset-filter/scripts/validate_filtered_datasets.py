#!/usr/bin/env python3
"""Check filtered source order, uniqueness, provenance, and SWE copy manifest."""
import json
from pathlib import Path

import pyarrow.parquet as pq

from filter_wildchat import has_interaction_content
from filter_empty_swe_sessions import has_interaction_content as swe_has_interaction_content, unmatched_tool_result_ids
from swe_chat_adapter import convert as swe_convert
from swe_format import signature
from swe_record_policy import EXCLUDED_FORMATS


ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "OriginalDataset"
FILTERED = ROOT / "OriginalDataset-filter"


def column_values(files, column):
    for path in files:
        for batch in pq.ParquetFile(path).iter_batches(batch_size=65536, columns=[column]):
            yield from batch.column(0).to_pylist()


def validate_wildchat(original_name, filtered_name):
    source = ORIGINAL / original_name
    target = FILTERED / filtered_name
    manifest = json.loads((target / "filter_manifest.json").read_text())
    source_files = sorted((source / "data").glob("train-*.parquet"))
    target_files = sorted((target / "data").glob("train-*.parquet"))
    if [p.name for p in source_files] != [p.name for p in target_files]:
        raise ValueError(f"{filtered_name}: shard names differ from original")
    for original, filtered in zip(source_files, target_files):
        if pq.ParquetFile(original).schema_arrow != pq.ParquetFile(filtered).schema_arrow:
            raise ValueError(f"{filtered_name}: schema differs in {original.name}")
    filtered_hashes = iter(column_values(target_files, "conversation_hash"))
    kept_indices = iter(
        column_values([target / "kept_original_indices.parquet"], "original_global_row_index")
    )
    seen = set()
    source_rows = kept_rows = empty_rows = duplicate_rows = 0
    for path in source_files:
        for batch in pq.ParquetFile(path).iter_batches(
            batch_size=8192, columns=["conversation_hash", "conversation"]
        ):
            hashes = batch.column(0).to_pylist()
            conversations = batch.column(1).to_pylist()
            for key, conversation in zip(hashes, conversations):
                original_index = source_rows
                source_rows += 1
                if not has_interaction_content(conversation):
                    empty_rows += 1
                    continue
                if key in seen:
                    duplicate_rows += 1
                    continue
                seen.add(key)
                observed = next(filtered_hashes)
                selected_index = next(kept_indices)
                if observed != key or selected_index != original_index:
                    raise ValueError(
                        f"{filtered_name}: first eligible occurrence mismatch at source row {original_index}"
                    )
                kept_rows += 1
    if next(filtered_hashes, None) is not None or next(kept_indices, None) is not None:
        raise ValueError(f"{filtered_name}: extra filtered rows or provenance indices")
    if (source_rows, kept_rows) != (manifest["source_rows"], manifest["filtered_rows"]):
        raise ValueError(f"{filtered_name}: manifest row counts differ")
    if empty_rows != manifest.get("removed_empty_content_rows", 0):
        raise ValueError(f"{filtered_name}: empty Conversation count differs from manifest")
    if duplicate_rows != manifest.get("removed_duplicate_rows", manifest["removed_rows"]):
        raise ValueError(f"{filtered_name}: duplicate count differs from manifest")
    return {
        "source_rows": source_rows,
        "filtered_rows": kept_rows,
        "removed_rows": source_rows - kept_rows,
        "empty_rows": empty_rows,
        "duplicate_rows": duplicate_rows,
        "unique_hashes": len(seen),
        "first_occurrence_and_provenance_verified": True,
    }


def main():
    result = {
        "WildChat-1M-filter": validate_wildchat("WildChat-1M", "WildChat-1M-filter"),
        "WildChat-4.8M-filter": validate_wildchat("WildChat-4.8M", "WildChat-4.8M-filter"),
    }
    swe = json.loads((FILTERED / "SWE-Chat-filter" / "filter_manifest.json").read_text())
    swe_dir = FILTERED / "SWE-Chat-filter"
    sessions = pq.read_table(
        swe_dir / "sessions.parquet", columns=["session_id", "transcript_path"]
    ).to_pylist()
    logs = pq.read_table(
        swe_dir / "session_logs.parquet", columns=["session_id", "transcript_path"]
    ).to_pylist()
    ids = [row["session_id"] for row in sessions]
    if (
        len(ids) != swe["session_count"]
        or len(ids) != len(set(ids))
        or {row["session_id"] for row in logs} != set(ids)
    ):
        raise ValueError("SWE filtered Session IDs or row counts differ from manifest")
    if len(ids) + swe["removed_sessions"] != 17968:
        raise ValueError("SWE kept and removed Session counts do not sum to original")
    removed_ids = {row["session_id"] for row in swe.get("removed_session_details", [])}
    if removed_ids & set(ids):
        raise ValueError("a removed SWE Session remains in sessions.parquet")
    agent_named_rows = [row for row in pq.read_table(
        ORIGINAL / "SWE-chat" / "session_logs.parquet", columns=["session_id", "transcript_path"]
    ).to_pylist() if row["session_id"].startswith("agent-") or (
        row["transcript_path"] and Path(row["transcript_path"]).stem.startswith("agent-")
    )]
    eligible_agent_named = set()
    for row in agent_named_rows:
        path = row["transcript_path"]
        transcript = ORIGINAL / "SWE-chat" / path if path else None
        if transcript is None or not transcript.is_file() or signature(transcript) in EXCLUDED_FORMATS | {"unclassified"}:
            continue
        events, _, _ = swe_convert(transcript, row["session_id"])
        if swe_has_interaction_content(events) and not unmatched_tool_result_ids(events):
            eligible_agent_named.add(row["session_id"])
    actual_agent_named = {row["session_id"] for row in agent_named_rows} & set(ids)
    if actual_agent_named != eligible_agent_named:
        raise ValueError("SWE agent-* Session retention differs from main-agent content eligibility")
    if any(
        not row["transcript_path"] or not (swe_dir / row["transcript_path"]).is_file()
        for row in logs
    ):
        raise ValueError("retained SWE Session has no readable main transcript")
    if len(logs) != swe["session_count"] or len(logs) != swe["main_transcript_count"]:
        raise ValueError("SWE session_logs or transcript count differs from manifest")
    original_swe = ORIGINAL / "SWE-chat"
    for name, removed_count in swe.get("removed_session_keyed_rows_by_table", {}).items():
        filtered_file = swe_dir / name
        original_file = original_swe / name
        if (
            pq.read_metadata(original_file).num_rows - removed_count
            != pq.read_metadata(filtered_file).num_rows
        ):
            raise ValueError(f"SWE {name}: removed row count differs from source")
        for batch in pq.ParquetFile(filtered_file).iter_batches(
            batch_size=65536, columns=["session_id"]
        ):
            if removed_ids.intersection(batch.column(0).to_pylist()):
                raise ValueError(f"SWE {name}: removed Session ID remains in table")
    result["SWE-Chat-filter"] = {
        "session_count": swe["session_count"],
        "removed_sessions": swe["removed_sessions"],
        "eligible_agent_named_sessions": len(eligible_agent_named),
        "copy_verification": swe["copy_verification"],
    }
    (FILTERED / "filter_validation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
