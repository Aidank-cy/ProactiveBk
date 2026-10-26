#!/usr/bin/env python3
"""Inventory every original SWE main transcript by its observed record envelope.

Reads only the header/first records of each original file. It never writes to the
source dataset or treats the Session agent label as the file format.
"""
import collections
import json
from pathlib import Path

import pyarrow.parquet as pq
from swe_format import signature
from swe_record_policy import EXCLUDED_FORMATS


ROOT = Path(__file__).resolve().parents[2] / "OriginalDataset" / "SWE-chat"
OUTPUT = Path(__file__).resolve().parents[1] / "full_swe_format_audit.json"


def main():
    sessions = pq.read_table(ROOT / "sessions.parquet", columns=["agent", "transcript_path"]).to_pylist()
    labels = collections.defaultdict(collections.Counter)
    for row in sessions:
        if row["transcript_path"]:
            labels[row["transcript_path"]][row["agent"] or "unknown"] += 1
    counts = collections.Counter()
    by_label = collections.defaultdict(collections.Counter)
    exceptions = []
    paths = [p for dirname in ("transcripts", "transcripts1") for p in sorted((ROOT / dirname).glob("*.jsonl"))]
    for path in paths:
        relative = str(path.relative_to(ROOT))
        fmt = signature(path)
        counts[fmt] += 1
        for label, number in labels[relative].items():
            by_label[fmt][label] += number
        if fmt in ("unparsed_source_wrapper", "empty_source_record", "unclassified"):
            exceptions.append({"path": relative, "format": fmt, "agent_labels": dict(labels[relative])})
    recognized = {k: v for k, v in counts.items() if k not in ("unparsed_source_wrapper", "empty_source_record", "unclassified")}
    excluded = EXCLUDED_FORMATS
    sampled_root = Path(__file__).resolve().parents[2] / "OriginalDataset-filter-1k" / "SWE-Chat-filter-1k"
    selected = json.loads((sampled_root / "sample_manifest.json").read_text())["selected"]
    sampled = collections.Counter(signature(sampled_root / row["transcript_path"]) for row in selected)
    report = {
        "scope": "all main raw files in OriginalDataset/SWE-chat/transcripts and transcripts1",
        "method": "observed structural envelope from first 80 lines; agent label is not used to choose format",
        "session_rows": len(sessions),
        "main_transcript_files": len(paths),
        "recognized_format_family_count": len(recognized),
        "recognized_format_family_file_counts": dict(sorted(recognized.items())),
        "eligible_format_family_count": len(set(recognized) - excluded),
        "excluded_main_format_counts": {k: counts[k] for k in sorted(excluded)},
        "sampled_main_format_counts": dict(sorted(sampled.items())),
        "format_families_absent_from_1k_sample": sorted(set(recognized) - set(sampled)),
        "noninterpretable_file_counts": {k: counts[k] for k in ("unparsed_source_wrapper", "empty_source_record", "unclassified")},
        "session_agent_labels_by_format": {k: dict(v) for k, v in sorted(by_label.items())},
        "noninterpretable_files": exceptions,
        "note": "A structural family groups compatible record envelopes; some families have minor version variants. Header inspection cannot prove every later record in a file has the same structure.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("session_rows", "main_transcript_files", "recognized_format_family_count", "eligible_format_family_count", "recognized_format_family_file_counts", "sampled_main_format_counts", "format_families_absent_from_1k_sample", "noninterpretable_file_counts")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
