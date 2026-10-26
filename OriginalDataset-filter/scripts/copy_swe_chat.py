#!/usr/bin/env python3
"""Copy SWE-chat after verifying Session IDs are unique and metadata agrees.

Rows in conversations.parquet are interaction records, so repeated session_id
values there must be retained. All source files are read-only.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pyarrow.parquet as pq


def revision(source):
    path = source / ".cache/huggingface/download/README.md.metadata"
    return path.read_text(encoding="utf-8").splitlines()[0] if path.is_file() else None


def check_ids(source):
    sessions = pq.read_table(
        source / "sessions.parquet", columns=["session_id", "transcript_path"]
    ).to_pylist()
    logs = pq.read_table(
        source / "session_logs.parquet", columns=["session_id", "transcript_path"]
    ).to_pylist()
    for name, rows in (("sessions", sessions), ("session_logs", logs)):
        ids = [row["session_id"] for row in rows]
        if len(ids) != len(set(ids)) or any(not sid for sid in ids):
            raise ValueError(f"{name}: duplicate or empty session_id")
    session_paths = {row["session_id"]: row["transcript_path"] for row in sessions}
    log_paths = {row["session_id"]: row["transcript_path"] for row in logs}
    if session_paths != log_paths:
        raise ValueError(
            "sessions and session_logs do not have the same Session-to-transcript mapping"
        )
    paths = [path for path in session_paths.values() if path]
    if len(paths) != len(set(paths)):
        raise ValueError("multiple Sessions share one main transcript path")
    return len(sessions), len(paths)


def build(source, destination):
    if destination.exists():
        raise FileExistsError(destination)
    session_count, main_transcript_count = check_ids(source)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.build-", dir=destination.parent))
    print("copying SWE-chat", source, "->", stage, flush=True)
    subprocess.run(["rsync", "-a", "--", str(source) + "/", str(stage) + "/"], check=True)
    verification = subprocess.run(
        [
            "rsync",
            "-a",
            "--checksum",
            "--dry-run",
            "--itemize-changes",
            "--",
            str(source) + "/",
            str(stage) + "/",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    if verification.stdout.strip():
        raise ValueError(f"SWE-chat copy differs from original: {verification.stdout[:500]}")
    if check_ids(stage) != (session_count, main_transcript_count):
        raise ValueError("copied SWE-chat Session mapping differs from source")
    manifest = {
        "source_directory": str(source),
        "source_revision": revision(source),
        "deduplication_key": "session_id",
        "retention_policy": "initial byte-identical copy; empty-content filtering follows before publication",
        "session_count": session_count,
        "main_transcript_count": main_transcript_count,
        "removed_sessions": 0,
        "copy_verification": "rsync --checksum --dry-run produced no differences",
    }
    (stage / "filter_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    script_dir = Path(__file__).resolve().parent
    if not (script_dir / "filter_empty_swe_sessions.py").is_file():
        script_dir = script_dir.parent / "scripts"
    subprocess.run(
        [
            sys.executable,
            str(script_dir / "filter_empty_swe_sessions.py"),
            "--dataset",
            str(stage),
            "--discard-backup",
        ],
        check=True,
    )
    shutil.copy2(Path(__file__), stage / "copy_unique_sessions.py")
    stage.rename(destination)
    filtered_manifest = json.loads((destination / "filter_manifest.json").read_text())
    print(
        "complete",
        destination,
        "Sessions",
        filtered_manifest["session_count"],
        "removed",
        filtered_manifest["removed_sessions"],
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
