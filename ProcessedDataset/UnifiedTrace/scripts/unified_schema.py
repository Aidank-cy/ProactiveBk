"""Parquet schemas shared by sampled and full filtered UnifiedTrace conversion."""

import pyarrow as pa


TRACE_SCHEMA = pa.schema([(x, t) for x, t in [
    ("trace_id", pa.string()), ("source", pa.string()), ("source_id", pa.string()),
    ("query_type", pa.string()), ("language", pa.string()), ("model", pa.string()),
    ("user_turn_count", pa.int64()),
]])

EVENT_SCHEMA = pa.schema([(x, t) for x, t in [
    ("trace_id", pa.string()), ("event_id", pa.int64()), ("role", pa.string()),
    ("event_type", pa.string()), ("content", pa.large_string()),
    ("visibility", pa.string()),
]])
