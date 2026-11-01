# 2026-11-01 Agent 真实行为审计

- [40 个任务的逐项审计报告](test/四组任务真实行为审计发现.md)
- [跨任务共性问题（原回答）](Agent真实行为共性问题.md)
- [轨迹索引](TRACE_INDEX.tsv)

轨迹来自本地四组时钟修复后的运行：VibeLifeBench old10/new10 各 10 题，以及 CLaw-Anything old10/new10 各 10 题。每题保留评测前端实际读取的主轨迹文件，原有目录结构保留在 `test/` 下。原始本地文件未修改。

公开仓库上传副本中，仅 `T05_T04_compile_q1_2026_emergency_response_best` 的主轨迹有 2 处 API key 值替换为 `[REDACTED_API_KEY]`；其他 39 份轨迹字节不变。审计报告和共性问题保留原文，因此其中的 `/home/hezd/...` 本地路径链接在 GitHub 网页上不会直接打开；可使用 `TRACE_INDEX.tsv` 找到仓库内相应轨迹。
