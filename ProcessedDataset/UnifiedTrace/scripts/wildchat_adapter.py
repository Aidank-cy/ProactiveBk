"""Conversion of WildChat conversations from sampled or filtered full sources."""

import json
from datetime import datetime

import pyarrow.parquet as pq

from trace_ids import trace_id as make_trace_id


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


class WildChatAdapter:
    """Convert sampled rows while retaining their manifest order."""

    SAFE_MESSAGE_FIELDS = (
        "turn_identifier",
        "redacted",
        "toxic",
        "language",
        "created",
        "openai_id",
        "token_counter",
        "system_fingerprint",
        "usage",
    )

    def __init__(self, directory, source):
        self.directory = directory
        self.source = source

    def message_event(self, trace_id, index, message):
        role = message.get("role")
        event_type = {"user": "user_message", "assistant": "assistant_message"}.get(
            role, "metadata_event"
        )
        safe = {
            key: message[key] for key in self.SAFE_MESSAGE_FIELDS if message.get(key) is not None
        }
        safe.update({"original_role": role, "raw_message_index": index})
        timestamp = message.get("timestamp")
        return {
            "trace_id": trace_id,
            "event_id": index,
            "source_event_id": str(message.get("openai_id")) if message.get("openai_id") else None,
            "role": role if role in ("user", "assistant") else "system",
            "event_type": event_type,
            "content": message.get("content"),
            "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            "visibility": "public" if role in ("user", "assistant") else "internal",
            "metadata": _json(safe),
        }

    def convert_row(self, local_index, row):
        trace_id = make_trace_id(self.source, local_index)
        events = [
            self.message_event(trace_id, i, message)
            for i, message in enumerate(row.get("conversation") or [])
        ]
        trace = {
            "trace_id": trace_id,
            "source": self.source,
            "source_id": row.get("conversation_hash"),
            "query_type": None,
            "language": row.get("language"),
            "model": row.get("model"),
            "user_turn_count": sum(e["event_type"] == "user_message" for e in events),
        }
        return trace, events

    def convert(self):
        manifest = json.loads((self.directory / "sample_manifest.json").read_text())
        table = pq.read_table(self.directory / "train.parquet")
        if len(manifest["selected"]) != table.num_rows:
            raise ValueError(f"{self.directory}: manifest/Parquet row count mismatch")
        for local_index, row in enumerate(table.to_pylist()):
            yield self.convert_row(local_index, row)

    def convert_filtered_full(self, limit=None):
        """Stream filtered shards in sorted shard-name and row order."""
        if self.directory.name not in ("WildChat-1M-filter", "WildChat-4.8M-filter"):
            raise ValueError(f"not a filtered full WildChat source: {self.directory}")
        files = sorted((self.directory / "data").glob("train-*.parquet"))
        if not files:
            raise ValueError(f"no filtered WildChat shards: {self.directory}")
        expected = json.loads((self.directory / "filter_manifest.json").read_text())["filtered_rows"]
        if sum(pq.ParquetFile(path).metadata.num_rows for path in files) != expected:
            raise ValueError(f"filtered row count differs from manifest: {self.directory}")
        index = 0
        for path in files:
            for batch in pq.ParquetFile(path).iter_batches(batch_size=256):
                for row in batch.to_pylist():
                    if limit is not None and index >= limit:
                        return
                    yield self.convert_row(index, row)
                    index += 1


def convert(directory, source):
    """Compatibility entry point used by the unified conversion pipeline."""
    yield from WildChatAdapter(directory, source).convert()


def convert_filtered_full(directory, source, limit=None):
    yield from WildChatAdapter(directory, source).convert_filtered_full(limit)
