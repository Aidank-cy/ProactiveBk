#!/usr/bin/env python3
"""Read-only identifier/content audit of the complete original datasets."""
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import multiprocessing
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[2] / "OriginalDataset"
OUTPUT = Path(__file__).resolve().parents[1] / "full_original_identifier_audit.json"
WILD = ("WildChat-1M", "WildChat-4.8M")


def wild_files(name):
    return sorted((ROOT / name / "data").glob("train-*.parquet"))


def hashes(name):
    result = Counter()
    for path in wild_files(name):
        for batch in pq.ParquetFile(path).iter_batches(batch_size=65536, columns=["conversation_hash"]):
            result.update(batch.column(0).to_pylist())
    return result


def content_digest(conversation):
    # Ignore timestamps, moderation, geography, and browser/IP metadata.
    messages = [(message.get("role"), message.get("content")) for message in (conversation or [])]
    encoded = json.dumps(messages, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).digest()


_TARGETS = set()
_DUPLICATES = set()


def init_content_worker(targets, duplicate_hashes):
    global _TARGETS, _DUPLICATES
    _TARGETS = targets
    _DUPLICATES = duplicate_hashes


def scan_content_file(path):
    first = {}
    duplicate_contents = defaultdict(Counter)
    processed = 0
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(batch_size=8192, columns=["conversation_hash", "conversation"]):
        values = batch.column(0).to_pylist()
        positions = [i for i, value in enumerate(values) if value in _TARGETS]
        if not positions:
            continue
        selected = batch.take(pa.array(positions, type=pa.int32())).to_pylist()
        for row in selected:
            key = row["conversation_hash"]
            digest = content_digest(row["conversation"])
            if key in _DUPLICATES:
                duplicate_contents[key][digest] += 1
            else:
                first[key] = digest
            processed += 1
    return first, dict(duplicate_contents), processed


def contents(name, duplicate_hashes, shared_hashes):
    targets = duplicate_hashes | shared_hashes
    first = {}
    duplicate_contents = defaultdict(Counter)
    processed = 0
    files = wild_files(name)
    with ProcessPoolExecutor(max_workers=8, mp_context=multiprocessing.get_context("spawn"),
                             initializer=init_content_worker, initargs=(targets, duplicate_hashes)) as executor:
        pending = {executor.submit(scan_content_file, path): path for path in files}
        for finished in as_completed(pending):
            path = pending[finished]
            file_first, file_duplicate, file_processed = finished.result()
            first.update(file_first)
            for key, variants in file_duplicate.items():
                duplicate_contents[key].update(variants)
            processed += file_processed
            print(name, path.name, "target rows processed", processed, "of", len(files), "files", flush=True)
    return first, duplicate_contents, processed


def digest_set(key, first, duplicate_contents):
    if key in duplicate_contents:
        return duplicate_contents[key].keys()
    return (first[key],)


def duplicate_metadata(name, duplicate_hashes):
    first = {}
    changed = set()
    changed_timestamp = set()
    changed_model = set()
    for path in wild_files(name):
        for batch in pq.ParquetFile(path).iter_batches(batch_size=65536, columns=["conversation_hash", "timestamp", "model"]):
            hashes = batch.column(0).to_pylist()
            timestamps = batch.column(1).to_pylist()
            models = batch.column(2).to_pylist()
            for key, timestamp, model in zip(hashes, timestamps, models):
                if key not in duplicate_hashes:
                    continue
                if key not in first:
                    first[key] = (timestamp, model)
                else:
                    original_timestamp, original_model = first[key]
                    if (timestamp, model) != (original_timestamp, original_model):
                        changed.add(key)
                    if timestamp != original_timestamp:
                        changed_timestamp.add(key)
                    if model != original_model:
                        changed_model.add(key)
    return {
        "duplicate_hash_groups_with_timestamp_or_model_difference": len(changed),
        "duplicate_hash_groups_with_timestamp_difference": len(changed_timestamp),
        "duplicate_hash_groups_with_model_difference": len(changed_model),
    }


def swe_ids():
    source = ROOT / "SWE-chat"
    counters = {}
    for name in ("sessions", "session_logs", "conversations"):
        counter = Counter()
        for batch in pq.ParquetFile(source / f"{name}.parquet").iter_batches(batch_size=262144, columns=["session_id"]):
            counter.update(batch.column(0).to_pylist())
        counters[name] = counter
    sessions, logs, conversations = (counters[name] for name in ("sessions", "session_logs", "conversations"))
    session_rows = pq.read_table(source / "sessions.parquet", columns=["session_id", "transcript_path"]).to_pylist()
    log_rows = pq.read_table(source / "session_logs.parquet", columns=["session_id", "transcript_path"]).to_pylist()
    session_paths = {row["session_id"]: row["transcript_path"] for row in session_rows}
    log_paths = {row["session_id"]: row["transcript_path"] for row in log_rows}
    nonempty_paths = [path for path in session_paths.values() if path]
    return {
        name: {
            "rows": sum(counter.values()),
            "distinct_session_ids": len(counter),
            "repeated_id_groups": sum(value > 1 for value in counter.values()),
            "rows_in_repeated_id_groups": sum(value for value in counter.values() if value > 1),
            "null_or_empty_rows": counter[None] + counter[""],
        }
        for name, counter in counters.items()
    } | {
        "sessions_and_logs_id_sets_equal": sessions.keys() == logs.keys(),
        "conversation_session_ids_missing_from_sessions": len(conversations.keys() - sessions.keys()),
        "session_log_transcript_path_mismatches": sum(session_paths[key] != log_paths[key] for key in session_paths.keys() & log_paths.keys()),
        "sessions_with_nonempty_transcript_path": len(nonempty_paths),
        "distinct_nonempty_transcript_paths": len(set(nonempty_paths)),
    }


def main():
    counts = {name: hashes(name) for name in WILD}
    shared = set(counts[WILD[0]]) & set(counts[WILD[1]])
    duplicates = {name: {key for key, count in counts[name].items() if count > 1} for name in WILD}
    first = {}
    content_counts = {}
    target_rows = {}
    for name in WILD:
        first[name], content_counts[name], target_rows[name] = contents(name, duplicates[name], shared)
    wild_report = {}
    for name in WILD:
        counter = counts[name]
        grouped = content_counts[name]
        pure = [key for key, variants in grouped.items() if len(variants) == 1]
        mixed = [key for key, variants in grouped.items() if len(variants) > 1]
        repeated_pairs = [(key, number) for key, variants in grouped.items() for number in variants.values() if number > 1]
        wild_report[name] = {
            "rows": sum(counter.values()),
            "distinct_conversation_hashes": len(counter),
            "missing_hash_rows": counter[None] + counter[""],
            "duplicate_hash_groups": len(duplicates[name]),
            "rows_in_duplicate_hash_groups": sum(counter[key] for key in duplicates[name]),
            "duplicate_hash_groups_one_role_content_sequence": len(pure),
            "rows_in_duplicate_hash_groups_one_role_content_sequence": sum(counter[key] for key in pure),
            "duplicate_hash_groups_multiple_role_content_sequences": len(mixed),
            "rows_in_duplicate_hash_groups_multiple_role_content_sequences": sum(counter[key] for key in mixed),
            "repeated_hash_and_content_subgroups": len(repeated_pairs),
            "rows_in_repeated_hash_and_content_subgroups": sum(number for _, number in repeated_pairs),
            "largest_hash_group_size": max(counter.values()),
            "mixed_hash_examples": [{"conversation_hash": key, "rows": counter[key], "distinct_role_content_sequences": len(grouped[key])} for key in sorted(mixed)[:10]],
            "target_rows_content_compared": target_rows[name],
            **duplicate_metadata(name, duplicates[name]),
        }
    same = any_overlap = no_overlap = 0
    for key in shared:
        a = set(digest_set(key, first[WILD[0]], content_counts[WILD[0]]))
        b = set(digest_set(key, first[WILD[1]], content_counts[WILD[1]]))
        if len(a) == len(b) == 1 and a == b:
            same += 1
        elif a & b:
            any_overlap += 1
        else:
            no_overlap += 1
    report = {
        "method": "Compare complete WildChat role/content message sequences; SHA-256 fingerprints are used only for equality grouping. Source files are read-only.",
        "wildchat": wild_report,
        "cross_wildchat": {
            "shared_conversation_hashes": len(shared),
            "shared_hashes_single_identical_role_content_sequence_in_both": same,
            "shared_hashes_some_role_content_overlap_but_variants": any_overlap,
            "shared_hashes_no_role_content_overlap": no_overlap,
            "wildchat_1m_rows_with_shared_hash": sum(counts[WILD[0]][key] for key in shared),
            "wildchat_4_8m_rows_with_shared_hash": sum(counts[WILD[1]][key] for key in shared),
        },
        "swe_chat": swe_ids(),
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
