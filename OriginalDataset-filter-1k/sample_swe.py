"""SWE Session validation, balanced sampling, and staged copy."""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import random
import shutil
import tempfile
import uuid

import pyarrow as pa
import pyarrow.parquet as pq

from sample_common import (
    HERE, SAMPLE_SIZE, SWE_OUTPUT, SWE_PROFILE, sha256_file,
    source_revision, valid_relative_path, write_manifest,
)

def check_swe(source: Path) -> tuple[pa.Table, pa.Table, list[str], dict]:
    logs_file = source / "session_logs.parquet"
    sessions_file = source / "sessions.parquet"
    tasks_file = source / "subagent_tasks.parquet"
    subagent_turns_file = source / "conversations_subagents.parquet"
    if any(not path.is_file() for path in (logs_file, sessions_file, tasks_file, subagent_turns_file)):
        raise RuntimeError("SWE-chat 尚未下载完整：缺少会话或子代理元数据 Parquet 文件")
    try:
        logs = pq.read_table(logs_file)
        sessions = pq.read_table(sessions_file)
        tasks = pq.read_table(tasks_file, columns=["transcript_path"])
        pq.ParquetFile(subagent_turns_file)
    except Exception as exc:
        raise RuntimeError(f"SWE-chat 元数据尚不能完整读取：{exc}") from exc
    filter_manifest = json.loads((source / "filter_manifest.json").read_text())
    expected_sessions = filter_manifest["session_count"]
    if logs.num_rows != expected_sessions or sessions.num_rows != expected_sessions:
        raise RuntimeError("SWE-chat 元数据行数与过滤清单不符，请确认过滤集完整")
    if not SWE_PROFILE.is_file():
        raise RuntimeError("缺少 SWE 主日志结构画像；先运行 OriginalDataset-filter/scripts/profile_swe_sampling.py")
    profile_by_path = {row["transcript_path"]: row for row in pq.read_table(SWE_PROFILE).to_pylist()}
    session_rows = sessions.to_pylist()
    log_rows = logs.to_pylist()
    paths = [row["transcript_path"] for row in log_rows]
    compact_paths = logs.column("compact_transcript_path").to_pylist()
    subagent_paths = tasks.column("transcript_path").to_pylist()
    unique_paths = sorted(set(path for path in paths if path))
    unique_compact = sorted(set(path for path in compact_paths if path))
    unique_subagent = sorted(set(path for path in subagent_paths if path))
    bad = [path for path in unique_compact if not valid_relative_path(path, "transcripts_compact")]
    bad += [path for path in unique_subagent if not valid_relative_path(path, "transcripts_subagent")]
    if bad:
        raise RuntimeError(f"SWE-chat 存在异常轨迹路径，例如 {bad[:3]}")
    missing = [path for path in unique_compact + unique_subagent if not (source / path).is_file()]
    if missing:
        raise RuntimeError(f"SWE-chat 尚未下载完整：缺少 {len(missing)} 个轨迹文件，例如 {missing[:3]}")
    session_by_id: dict[str, list[int]] = defaultdict(list)
    log_by_id: dict[str, list[int]] = defaultdict(list)
    path_to_ids: dict[str, set[str]] = defaultdict(set)
    for index, row in enumerate(session_rows):
        if isinstance(row["session_id"], str) and row["session_id"].strip():
            session_by_id[row["session_id"]].append(index)
    for index, row in enumerate(log_rows):
        if isinstance(row["session_id"], str) and row["session_id"].strip():
            log_by_id[row["session_id"]].append(index)
            if row["transcript_path"]:
                path_to_ids[row["transcript_path"]].add(row["session_id"])
    shared_paths = {path: sorted(ids) for path, ids in path_to_ids.items() if len(ids) > 1}
    errors = []
    eligible_ids = []
    for session_id in sorted(session_by_id):
        if len(session_by_id[session_id]) != 1 or len(log_by_id.get(session_id, [])) != 1:
            errors.append((session_id, "duplicate_or_missing_metadata_mapping"))
            continue
        session = session_rows[session_by_id[session_id][0]]
        log = log_rows[log_by_id[session_id][0]]
        path = log["transcript_path"]
        if not path:
            errors.append((session_id, "missing_transcript_path"))
            continue
        if session["transcript_path"] != path:
            errors.append((session_id, "disagreeing_transcript_paths"))
            continue
        if path in shared_paths:
            errors.append((session_id, "shared_transcript_path"))
            continue
        if not (valid_relative_path(path, "transcripts") or valid_relative_path(path, "transcripts1")):
            errors.append((session_id, "invalid_transcript_path"))
            continue
        try:
            with (source / path).open("rb") as handle:
                handle.read(1)
        except OSError:
            errors.append((session_id, "unreadable_transcript"))
            continue
        profile = profile_by_path.get(path)
        if profile is None:
            errors.append((session_id, "not_in_main_transcript_profile"))
            continue
        if profile["file_size"] != (source / path).stat().st_size:
            errors.append((session_id, "stale_transcript_profile"))
            continue
        eligible_ids.append(session_id)
    if errors or len(eligible_ids) != sessions.num_rows:
        raise RuntimeError(f"过滤后 SWE 来源仍有异常 Session；请在 OriginalDataset-filter 修复：{errors[:5]}")
    audit = {
        "source_session_rows": sessions.num_rows,
        "source_session_log_rows": logs.num_rows,
        "unique_main_transcript_paths": len(unique_paths),
        "unique_compact_transcript_paths": len(unique_compact),
        "unique_subagent_transcript_paths": len(unique_subagent),
        "unique_session_ids_in_sessions": len(session_by_id),
        "unique_session_ids_in_logs": len(log_by_id),
        "duplicate_session_ids_in_sessions": sum(len(v) > 1 for v in session_by_id.values()),
        "duplicate_session_ids_in_logs": sum(len(v) > 1 for v in log_by_id.values()),
        "shared_transcript_path_count": len(shared_paths),
        "shared_transcript_path_examples": [{"path": p, "session_ids": ids} for p, ids in list(shared_paths.items())[:10]],
        "excluded_session_counts": {},
        "eligibility_policy": "All Sessions in OriginalDataset-filter/SWE-Chat-filter are eligible; sampling validates source invariants and never excludes individual Sessions.",
    }
    if len(eligible_ids) < SAMPLE_SIZE:
        raise RuntimeError(f"SWE-chat 只有 {len(eligible_ids)} 个可用且无歧义的 Session，不能采样 {SAMPLE_SIZE} 个")
    return sessions, logs, eligible_ids, audit

def validate_swe_stage(stage: Path, source: Path, selected: list[dict], copied_paths: set[str]) -> None:
    manifest = json.loads((stage / "sample_manifest.json").read_text(encoding="utf-8"))
    session_ids = [item["session_id"] for item in selected]
    main_paths = [item["transcript_path"] for item in selected]
    if manifest["sampling_unit"] != "session_id" or manifest["selected"] != selected or len(selected) != SAMPLE_SIZE:
        raise RuntimeError("SWE-chat 暂存 manifest 与选中 Session 不一致")
    if manifest.get("filtered_source_manifest_sha256") != sha256_file(source / "filter_manifest.json"):
        raise RuntimeError("SWE-chat 暂存样本与过滤集清单不一致")
    if len(set(session_ids)) != SAMPLE_SIZE or len(set(main_paths)) != SAMPLE_SIZE:
        raise RuntimeError("SWE-chat 暂存样本的 Session ID 或主 transcript 路径不唯一")
    sessions = pq.read_table(stage / "sessions.parquet").to_pylist()
    logs = pq.read_table(stage / "session_logs.parquet").to_pylist()
    if len(sessions) != SAMPLE_SIZE or len(logs) != SAMPLE_SIZE:
        raise RuntimeError("SWE-chat 暂存的 sessions/session_logs 行数不为 1000")
    for index, item in enumerate(selected):
        if (sessions[index]["session_id"] != item["session_id"] or
            logs[index]["session_id"] != item["session_id"] or
            sessions[index]["transcript_path"] != item["transcript_path"] or
            logs[index]["transcript_path"] != item["transcript_path"] or
            logs[index]["compact_transcript_path"] != item["compact_transcript_path"]):
            raise RuntimeError(f"SWE-chat 暂存第 {index} 条 Session/Transcript 映射不一致")
    for path in sorted(copied_paths):
        if not (stage / path).is_file() or (stage / path).stat().st_size != (source / path).stat().st_size:
            raise RuntimeError(f"SWE-chat 暂存文件缺失或大小不一致：{path}")
        if sha256_file(stage / path) != sha256_file(source / path):
            raise RuntimeError(f"SWE-chat 暂存文件 SHA-256 不一致：{path}")

def choose_swe_sessions(source: Path, eligible_ids: list[str], sessions: pa.Table, logs: pa.Table, seed: int):
    """Balance CLI families, then cover observed structural variants within each."""
    report_path = SWE_PROFILE.with_name("swe_sampling_profile_report.json")
    if not SWE_PROFILE.is_file() or not report_path.is_file():
        raise RuntimeError("缺少 SWE 结构画像；先运行 OriginalDataset-filter/scripts/profile_swe_sampling.py")
    profile_report = json.loads(report_path.read_text())
    if (profile_report.get("source_revision") != source_revision(source)
            or profile_report.get("filtered_source_manifest_sha256") != sha256_file(source / "filter_manifest.json")
            or profile_report.get("failed_files")):
        raise RuntimeError("SWE 结构画像与当前来源版本不一致或生成失败")
    if profile_report.get("main_files_profiled") != len(eligible_ids):
        raise RuntimeError("SWE 结构画像文件数与可采样主 Session 数不一致")
    profile_by_path = {row["transcript_path"]: row for row in pq.read_table(SWE_PROFILE).to_pylist()}
    log_by_id = {row["session_id"]: row for row in logs.to_pylist()}
    agent_by_id = {row["session_id"]: (row.get("agent") or "unknown") for row in sessions.to_pylist()}
    by_family = defaultdict(list)
    feature_names = ("multi_block", "thinking", "tool_call", "tool_result", "structured_output", "queue", "subagent_marker", "system_injection", "grouped_fields")
    for session_id in eligible_ids:
        path = log_by_id[session_id]["transcript_path"]
        profile = profile_by_path.get(path)
        if profile is None or profile["file_size"] != (source / path).stat().st_size:
            raise RuntimeError(f"SWE 结构画像缺失或已过期：{path}")
        by_family[profile["format_family"]].append((session_id, profile))
    quotas = {family: 0 for family in sorted(by_family)}
    for _ in range(SAMPLE_SIZE):
        family = min((family for family in quotas if quotas[family] < len(by_family[family])),
                     key=lambda name: (quotas[name], name))
        quotas[family] += 1
    rng = random.Random(seed)
    chosen = []
    variant_by_id = {}
    for family in sorted(by_family):
        family_rows = by_family[family]
        size_bucket = {session_id: min(2, 3 * rank // len(family_rows))
                       for rank, (session_id, _) in enumerate(sorted(family_rows, key=lambda x: (x[1]["file_size"], x[0])))}
        buckets = defaultdict(list)
        for session_id, profile in family_rows:
            variant = agent_by_id[session_id] + ":" + profile["layout"] + ":" + str(size_bucket[session_id]) + ":" + "".join("1" if profile[name] else "0" for name in feature_names)
            buckets[variant].append(session_id)
            variant_by_id[session_id] = (family, variant)
        for ids in buckets.values():
            ids.sort()
            rng.shuffle(ids)
        family_picked = 0
        while family_picked < quotas[family]:
            variants = sorted(key for key, ids in buckets.items() if ids)
            if not variants:
                raise RuntimeError(f"SWE 格式 {family} 的候选 Session 不足")
            rng.shuffle(variants)
            for variant in variants:
                if family_picked >= quotas[family]:
                    break
                chosen.append(buckets[variant].pop())
                family_picked += 1
    rng.shuffle(chosen)
    if len(chosen) != SAMPLE_SIZE or len(set(chosen)) != SAMPLE_SIZE:
        raise RuntimeError("SWE 分层采样未生成 1000 个唯一 Session")
    coverage = {
        "sampled_feature_counts": {name: sum(profile_by_path[log_by_id[session_id]["transcript_path"]][name] for session_id in chosen)
                                   for name in feature_names},
        "sampled_structural_variant_counts": {family: len({variant_by_id[session_id][1] for session_id in chosen
                                                            if variant_by_id[session_id][0] == family})
                                              for family in sorted(by_family)},
    }
    return chosen, variant_by_id, quotas, feature_names, profile_report, coverage

def create_swe(source: Path, sessions: pa.Table, logs: pa.Table, eligible_ids: list[str], audit: dict,
               seed: int, overwrite: bool = False) -> Path | None:
    chosen_session_ids, variant_by_id, quotas, feature_names, profile_report, coverage = choose_swe_sessions(source, eligible_ids, sessions, logs, seed)
    session_index = {session_id: i for i, session_id in enumerate(sessions.column("session_id").to_pylist())}
    log_index = {session_id: i for i, session_id in enumerate(logs.column("session_id").to_pylist())}
    log_indices = [log_index[session_id] for session_id in chosen_session_ids]
    selected_logs = logs.take(pa.array(log_indices, type=pa.int64()))
    selected_sessions = sessions.take(pa.array([session_index[session_id] for session_id in chosen_session_ids], type=pa.int64()))
    chosen_paths = selected_logs.column("transcript_path").to_pylist()
    chosen_compact_paths = selected_logs.column("compact_transcript_path").to_pylist()
    chosen_id_set = set(chosen_session_ids)
    tasks = pq.read_table(source / "subagent_tasks.parquet")
    task_indices = [i for i, session_id in enumerate(tasks.column("session_id").to_pylist())
                    if session_id in chosen_id_set]
    selected_tasks = tasks.take(pa.array(task_indices, type=pa.int64()))
    subagent_paths = sorted(set(path for path in selected_tasks.column("transcript_path").to_pylist() if path))
    subagent_turns = pq.read_table(source / "conversations_subagents.parquet")
    turn_indices = [i for i, session_id in enumerate(subagent_turns.column("session_id").to_pylist())
                    if session_id in chosen_id_set]
    selected_subagent_turns = subagent_turns.take(pa.array(turn_indices, type=pa.int64()))

    destination = HERE / SWE_OUTPUT
    if destination.exists() and not overwrite:
        raise RuntimeError(f"输出目录已存在：{destination}；如需替换请使用 --only-swe --overwrite-swe")
    stage = Path(tempfile.mkdtemp(prefix=f".{SWE_OUTPUT}.", dir=HERE))
    backup = None
    try:
        copied_paths = set(chosen_paths + [path for path in chosen_compact_paths if path] + subagent_paths)
        for path in sorted(copied_paths):
            target = stage / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / path, target)
        pq.write_table(selected_logs, stage / "session_logs.parquet", compression="zstd")
        pq.write_table(selected_sessions, stage / "sessions.parquet", compression="zstd")
        pq.write_table(selected_tasks, stage / "subagent_tasks.parquet", compression="zstd")
        pq.write_table(selected_subagent_turns, stage / "conversations_subagents.parquet", compression="zstd")
        selected = [{"session_id": session_id, "transcript_path": path,
                     "compact_transcript_path": compact_path,
                     "format_family": variant_by_id[session_id][0],
                     "structural_variant": variant_by_id[session_id][1]}
                    for session_id, path, compact_path in zip(chosen_session_ids, chosen_paths, chosen_compact_paths)]
        write_manifest(
            stage,
            seed=seed,
            source=source,
            selected=selected,
            sampling_unit="session_id",
            eligible_session_count=len(eligible_ids),
            eligibility_audit=audit,
            sampling_strategy="balanced_cli_family_then_structural_variant_round_robin",
            sampling_profile=str(SWE_PROFILE),
            sampling_profile_sha256=sha256_file(SWE_PROFILE),
            sampling_profile_source_revision=profile_report["source_revision"],
            filtered_source_manifest_sha256=sha256_file(source / "filter_manifest.json"),
            sampled_format_quotas=quotas,
            structural_variant_features=list(feature_names),
            **coverage,
        )
        validate_swe_stage(stage, source, selected, copied_paths)
        for directory in [stage, *(path for path in stage.rglob("*") if path.is_dir())]:
            directory.chmod(0o2775)
        if destination.exists():
            backup = HERE / f".{SWE_OUTPUT}.backup-{uuid.uuid4().hex}"
            destination.rename(backup)
        try:
            stage.rename(destination)
        except Exception:
            if backup is not None:
                backup.rename(destination)
            raise
        print(f"{SWE_OUTPUT}: 已验证并复制 {len(chosen_paths)} 个唯一 Session 主轨迹 -> {destination}", flush=True)
        if backup is not None:
            print(f"旧样本暂存备份：{backup}", flush=True)
        return backup
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
