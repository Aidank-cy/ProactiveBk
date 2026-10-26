#!/usr/bin/env python3
"""Build one WildChat copy deduplicated by hash with empty Conversations removed.

The first row in shard-name / row order wins. Source files are read-only.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq


def revision(source):
    path = source / ".cache/huggingface/download/README.md.metadata"
    return path.read_text(encoding="utf-8").splitlines()[0] if path.is_file() else None


def has_interaction_content(conversation):
    """A Conversation needs at least one nonblank human or assistant message."""
    return any(
        isinstance(message, dict)
        and message.get("role") in ("user", "assistant")
        and isinstance(message.get("content"), str)
        and bool(message["content"].strip())
        for message in (conversation or [])
    )


def build(source, destination, expected_shards, expected_rows, expected_unique):
    files = sorted((source / "data").glob("train-*.parquet"))
    if len(files) != expected_shards:
        raise ValueError(f"{source}: found {len(files)} shards, expected {expected_shards}")
    if destination.exists():
        raise FileExistsError(destination)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.build-", dir=destination.parent))
    (stage / "data").mkdir()
    for path in source.iterdir():
        if path.is_file():
            shutil.copy2(path, stage / path.name)
    index_schema = pa.schema([("original_global_row_index", pa.int64())])
    index_writer = pq.ParquetWriter(
        stage / "kept_original_indices.parquet", index_schema, compression="zstd"
    )
    seen = set()
    all_hashes = set()
    source_rows = kept_rows = duplicate_rows = empty_rows = 0
    per_shard = []
    source_schema = None
    try:
        for path in files:
            parquet = pq.ParquetFile(path)
            schema = parquet.schema_arrow
            if source_schema is None:
                source_schema = schema
            elif schema != source_schema:
                raise ValueError(f"schema differs between WildChat shards: {path}")
            writer = pq.ParquetWriter(stage / "data" / path.name, schema, compression="zstd")
            shard_source = shard_kept = 0
            try:
                for batch in parquet.iter_batches(batch_size=32768):
                    hashes = batch.column(schema.get_field_index("conversation_hash")).to_pylist()
                    conversations = batch.column(schema.get_field_index("conversation")).to_pylist()
                    mask = []
                    indices = []
                    for offset, key in enumerate(hashes):
                        if not isinstance(key, str) or not key:
                            raise ValueError(
                                f"missing conversation_hash at source row {source_rows + offset}"
                            )
                        all_hashes.add(key)
                        has_content = has_interaction_content(conversations[offset])
                        keep = has_content and key not in seen
                        mask.append(keep)
                        if keep:
                            seen.add(key)
                            indices.append(source_rows + offset)
                        elif not has_content:
                            empty_rows += 1
                        else:
                            duplicate_rows += 1
                    if indices:
                        selected = batch.filter(pa.array(mask, type=pa.bool_()))
                        writer.write_table(pa.Table.from_batches([selected], schema=schema))
                        index_writer.write_table(
                            pa.table(
                                {"original_global_row_index": pa.array(indices, type=pa.int64())},
                                schema=index_schema,
                            )
                        )
                    n = len(hashes)
                    source_rows += n
                    kept_rows += len(indices)
                    shard_source += n
                    shard_kept += len(indices)
            finally:
                writer.close()
            per_shard.append(
                {"file": path.name, "source_rows": shard_source, "kept_rows": shard_kept}
            )
            print(path.name, "source", shard_source, "kept", shard_kept, flush=True)
    finally:
        index_writer.close()
    if (source_rows, len(all_hashes)) != (expected_rows, expected_unique):
        raise ValueError(
            f"unexpected counts: source={source_rows}, distinct_hashes={len(all_hashes)}"
        )
    if source_rows != kept_rows + duplicate_rows + empty_rows:
        raise ValueError("WildChat kept, duplicate, and empty row counts do not sum to source rows")
    if pq.read_metadata(stage / "kept_original_indices.parquet").num_rows != kept_rows:
        raise ValueError("provenance index count mismatch")
    for item in per_shard:
        if pq.read_metadata(stage / "data" / item["file"]).num_rows != item["kept_rows"]:
            raise ValueError(f"filtered shard count mismatch: {item['file']}")
    manifest = {
        "source_directory": str(source),
        "source_revision": revision(source),
        "deduplication_key": "conversation_hash",
        "retention_policy": "remove Conversations with no nonblank user/assistant content, then keep the first eligible row per conversation_hash in sorted shard-name and row order",
        "empty_content_policy": "at least one user or assistant message with nonblank string content",
        "source_rows": source_rows,
        "filtered_rows": kept_rows,
        "removed_rows": duplicate_rows + empty_rows,
        "removed_duplicate_rows": duplicate_rows,
        "removed_empty_content_rows": empty_rows,
        "source_shards": len(files),
        "shards": per_shard,
        "original_index_mapping": "kept_original_indices.parquet row i gives the original global row index of filtered row i",
    }
    (stage / "filter_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copy2(Path(__file__), stage / "deduplicate.py")
    for directory in [stage, *(path for path in stage.rglob("*") if path.is_dir())]:
        directory.chmod(0o2775)
    stage.rename(destination)
    print("complete", destination, "rows", kept_rows, "removed", duplicate_rows, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-shards", type=int, required=True)
    parser.add_argument("--expected-rows", type=int, required=True)
    parser.add_argument("--expected-unique", type=int, required=True)
    args = parser.parse_args()
    build(args.source, args.output, args.expected_shards, args.expected_rows, args.expected_unique)
