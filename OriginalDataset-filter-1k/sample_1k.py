#!/usr/bin/env python3
"""Sample 1,000 WildChat conversations and 1,000 SWE-chat Sessions from filtered sources.

Run after all three downloads finish:
    /home/hezd/anaconda3/envs/eval_model/bin/python sample_1k.py

Resample only SWE-chat after its source download is complete:
    /home/hezd/anaconda3/envs/eval_model/bin/python sample_1k.py --only-swe --overwrite-swe --seed 42

The random seed defaults to 42 and can be changed with --seed. The source
revisions are pinned in sample_common.py: the same seed and the same filtered-source
manifest and structural profile select the same traces.
"""
from __future__ import annotations

import argparse
import sys

from sample_common import (
    HERE, SOURCES, WILDCHAT, SWE_SOURCE, SWE_OUTPUT, EXPECTED_REVISIONS,
    check_revision, source_revision, valid_relative_path, write_manifest, sha256_file,
)
from sample_wildchat import check_wildchat, sample_wildchat_rows, create_wildchat
from sample_swe import check_swe, validate_swe_stage, choose_swe_sessions, create_swe


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed", type=int, default=42,
        help="随机种子；默认 42",
    )
    parser.add_argument("--only-swe", action="store_true", help="仅按 Session ID 重新采样 SWE-chat，不读取或改写 WildChat 样本")
    parser.add_argument("--overwrite-swe", action="store_true", help="验证暂存样本后替换现有 SWE-Chat-filter-1k，并保留旧目录备份")
    args = parser.parse_args()
    seed = args.seed
    print(f"随机种子 {seed}", flush=True)

    try:
        if args.overwrite_swe and not args.only_swe:
            raise RuntimeError("--overwrite-swe 必须与 --only-swe 一起使用")
        output_names = [SWE_OUTPUT] if args.only_swe else [entry[1] for entry in WILDCHAT] + [SWE_OUTPUT]
        for output_name in output_names:
            if output_name == SWE_OUTPUT and args.overwrite_swe:
                continue
            if (HERE / output_name).exists():
                raise RuntimeError(f"输出目录已存在：{HERE / output_name}；请先检查现有结果")
        for name in ([SWE_SOURCE] if args.only_swe else EXPECTED_REVISIONS):
            check_revision(SOURCES / name)
        wildchat_inputs = [] if args.only_swe else [
            (SOURCES / name, output, *check_wildchat(SOURCES / name, shards))
            for name, output, shards in WILDCHAT]
        swe_source = SOURCES / SWE_SOURCE
        swe_sessions, swe_logs, eligible_ids, audit = check_swe(swe_source)
        print(f"SWE-chat 可用且无歧义的 Session：{len(eligible_ids)}；排除统计：{audit['excluded_session_counts']}", flush=True)
        for source, output_name, files, total_rows in wildchat_inputs:
            create_wildchat(source, output_name, files, total_rows, seed)
        create_swe(swe_source, swe_sessions, swe_logs, eligible_ids, audit, seed, overwrite=args.overwrite_swe)
    except (OSError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
