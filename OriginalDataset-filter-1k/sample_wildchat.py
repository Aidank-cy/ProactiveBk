"""WildChat row validation and deterministic Conversation sampling."""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
import json
from pathlib import Path
import random
import shutil
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

from sample_common import HERE, SAMPLE_SIZE, write_manifest

def check_wildchat(source: Path, shard_count: int) -> tuple[list[Path], int]:
    data = source / "data"
    files = [data / f"train-{i:05d}-of-{shard_count:05d}.parquet" for i in range(shard_count)]
    missing = [path.name for path in files if not path.is_file()]
    if missing:
        raise RuntimeError(f"{source.name} 尚未下载完整：缺少 {len(missing)} 个 Parquet 分片，例如 {missing[:3]}")
    try:
        row_count = sum(pq.ParquetFile(path).metadata.num_rows for path in files)
    except Exception as exc:
        raise RuntimeError(f"{source.name} 的 Parquet 分片尚不能完整读取：{exc}") from exc
    expected_rows = json.loads((source / "filter_manifest.json").read_text())["filtered_rows"]
    if row_count != expected_rows:
        raise RuntimeError(
            f"{source.name} 行数为 {row_count}，预期 {expected_rows}；请确认下载版本和文件完整性"
        )
    return files, row_count

def sample_wildchat_rows(files: list[Path], total_rows: int, seed: int) -> tuple[pa.Table, list[int]]:
    rng = random.Random(seed)
    positions = rng.sample(range(total_rows), SAMPLE_SIZE)
    parquet_files = [pq.ParquetFile(path) for path in files]
    file_starts = [0]
    for parquet_file in parquet_files:
        file_starts.append(file_starts[-1] + parquet_file.metadata.num_rows)

    groups: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for global_index in positions:
        file_index = bisect_right(file_starts, global_index) - 1
        local_index = global_index - file_starts[file_index]
        parquet_file = parquet_files[file_index]
        group_start = 0
        for group_index in range(parquet_file.num_row_groups):
            group_rows = parquet_file.metadata.row_group(group_index).num_rows
            if local_index < group_start + group_rows:
                groups[(file_index, group_index)].append((global_index, local_index - group_start))
                break
            group_start += group_rows
        else:
            raise RuntimeError(f"找不到全局第 {global_index} 行对应的 Parquet row group")

    selected: dict[int, pa.Table] = {}
    for (file_index, group_index), entries in groups.items():
        # take() copies only the chosen rows, so whole row groups do not remain in memory.
        group = parquet_files[file_index].read_row_group(group_index)
        subset = group.take(pa.array([row_index for _, row_index in entries], type=pa.int64()))
        for offset, (global_index, _) in enumerate(entries):
            selected[global_index] = subset.slice(offset, 1)
    return pa.concat_tables([selected[index] for index in positions]), positions

def create_wildchat(source: Path, output_name: str, files: list[Path], total_rows: int, seed: int) -> None:
    destination = HERE / output_name
    stage = Path(tempfile.mkdtemp(prefix=f".{output_name}.", dir=HERE))
    try:
        table, positions = sample_wildchat_rows(files, total_rows, seed)
        assert table.num_rows == SAMPLE_SIZE
        pq.write_table(table, stage / "train.parquet", compression="zstd")
        original_indices = pq.read_table(source / "kept_original_indices.parquet").take(pa.array(positions, type=pa.int64()))
        write_manifest(stage, seed=seed, source=source, selected=positions,
                       selected_original_global_row_indices=original_indices.column("original_global_row_index").to_pylist(),
                       sampling_unit="filtered_conversation_row")
        stage.chmod(0o2775)
        stage.rename(destination)
        print(f"{output_name}: 已写入 {table.num_rows} 条完整对话 -> {destination}", flush=True)
    except Exception:
        shutil.rmtree(stage)
        raise
