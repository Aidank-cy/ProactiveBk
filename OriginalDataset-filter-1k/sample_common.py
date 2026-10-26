"""Shared constants and provenance checks for the local 1k sampler."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = HERE.parent / "OriginalDataset-filter"
SAMPLE_SIZE = 1_000
WILDCHAT = (
    ("WildChat-1M-filter", "WildChat-1M-filter-1k", 14),
    ("WildChat-4.8M-filter", "WildChat-4.8M-filter-1k", 86),
)
SWE_SOURCE = "SWE-Chat-filter"
SWE_OUTPUT = "SWE-Chat-filter-1k"
SWE_PROFILE = HERE.parent / "OriginalDataset-filter" / "swe_sampling_profiles.parquet"
EXPECTED_REVISIONS = {
    "WildChat-1M-filter": "7d6490e462285cf85d91eabea0f9a954fbddcd1f",
    "WildChat-4.8M-filter": "c827c6df8fcf008219ffaffa4d1dd77491099367",
    "SWE-Chat-filter": "202b071f18e03c79df5a7287565ce2ebc5ee7756",
}

def source_revision(source: Path) -> str | None:
    filter_manifest = source / "filter_manifest.json"
    if filter_manifest.is_file():
        return json.loads(filter_manifest.read_text(encoding="utf-8"))["source_revision"]
    metadata = source / ".cache/huggingface/download/README.md.metadata"
    if metadata.is_file():
        return metadata.read_text(encoding="utf-8").splitlines()[0]
    return None

def check_revision(source: Path) -> None:
    actual = source_revision(source)
    expected = EXPECTED_REVISIONS[source.name]
    if actual != expected:
        raise RuntimeError(
            f"{source.name} 版本为 {actual!r}，预期 {expected}；无法保证相同 seed 抽到相同轨迹"
        )

def valid_relative_path(path: str | None, parent: str) -> bool:
    if not path:
        return False
    parts = Path(path).parts
    return bool(parts and not Path(path).is_absolute() and ".." not in parts and parts[0] == parent)

def write_manifest(destination: Path, *, seed: int, source: Path, selected: list, **extra) -> None:
    payload = {
        "seed": seed,
        "source_directory": str(source),
        "source_revision": source_revision(source),
        "sample_size": len(selected),
        "selected": selected,
        **extra,
    }
    (destination / "sample_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
