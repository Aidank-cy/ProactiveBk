# 项目问题记录

截至 2026-10-26。本文记录本项目从原始数据下载到过滤、抽样、Unified Trace 转换及 Git 发布期间，实际遇到的较难问题、核查依据和解决方式。数字代表当前本机数据版本；早期样本或解析器的统计不能与当前数字直接比较。原始数据、样本和转换结果均保留在本地，不属于本 Git 仓库。

## 1. 大量原始文件的下载与续传

**问题。** SWE-Chat 含大量 transcript 文件和数 GB 的 Parquet 文件。另一台挂载相同 NFS 目录的机器下载时，`commits.parquet` 的 HTTP 连接出现 `IncompleteRead` / `ChunkedEncodingError`，导致一次 `hf download` 中止。WildChat 的两个版本也需要分别下载；只看某个进程结束，不能证明所有文件完整。

**处理。** 使用 Hugging Face 下载缓存中的 `.incomplete` 文件续传，并通过共享 NFS 检查文件、大小及下载状态；网络慢时曾改用代理。两台机器不应同时写同一批 SWE-Chat 目标文件。代理账号和密码不写入脚本、文档或 Git。最终处理以本地已下载文件为输入，不从远端文档猜测格式。

## 2. 抽样单位曾选错

**问题。** 最初 SWE 1k 按 `transcript_path` 抽取，路径与 Session 的对应关系需要额外验证。一个完整 Conversation 与一个 SWE Session 也不是相同的原始存储单位。

**处理。** 改为按唯一 `session_id` 抽样，并检查 `sessions.parquet`、`session_logs.parquet`、主 transcript 路径的一对一关系。使用固定 seed 42，先写临时目录、验证 1,000 个不同 Session 及完整文件副本，再替换旧样本。WildChat 仍按完整 Conversation 抽样；SWE 另按 CLI 格式及内容结构分层，使小样本覆盖罕见格式。当前可抽样 SWE Session 为 **17,671**，1k 样本覆盖 **14** 种格式。实现见 `OriginalDataset-filter-1k/sample_*.py`。

## 3. 重复记录与空记录不能混为一谈

**问题。** WildChat 的 `conversation_hash` 相同不意味着整行元数据逐字段相同；两个 WildChat 版本也可能重叠。SWE 的 Session 标识与日志路径要分别检查。部分 SWE Session 只有系统、元数据或子 Agent 内容，看似有日志，实际没有可提取的主 Agent 交互。

**处理。** 两个 WildChat 数据集各自在 `OriginalDataset-filter/scripts/filter_wildchat.py` 中先排除无交互内容的 Conversation，再按 `conversation_hash` 保留首个合格记录；不跨数据集去重。原始字段和顺序保留，`kept_original_indices.parquet` 记录来源行。当前 WildChat-1M 为 **837,989 → 826,319** 行，WildChat-4.8M 为 **3,199,860 → 2,869,082** 行；名称中的“1M/4.8M”不应替代实际行数。SWE 过滤按主日志的可提取交互判断，排除缺失路径、无法解释的格式、独立 `agent-*` 子 Agent Session 及只有补充记录的 Session。完整过滤集与原始源文件分开保存。

## 4. SWE-Chat 不是一种通用 JSONL 格式

**问题。** 同样的 `.jsonl` 扩展名下可能是逐行记录，也可能是一个 JSON 文档；不同 CLI 对用户正文、思考、工具调用和结果使用不同的层级与字段。`sessions.parquet.agent` 标签可能标错，不能决定解析器。`transcripts/` 与 `transcripts1/` 都可能存放主日志；compact 和 subagent 文件不能替代主日志。

**处理。** 对真实文件做结构画像，当前识别 14 个格式族：`claude_tree`、`codex_rollout`、`copilot_events`、`cursor_messages`、`factory_droid`、`gemini_document`、`grok_hooks`、`kimi_wire`、`opencode_document`、`pi_tree`、`project_runner`、`role_content`、`simple_message`、`xai_session_update`。解析器由**原始记录结构**选择，每个 CLI 有自己的类。主 Agent 事件只从主 transcript 提取；compact、subagent transcript 和事后结果摘要不并入主时间线。未知记录或确实损坏的 JSONL 行以可检查的事件形式保留，不臆造语义。代码见两处各自独立的 `swe_format.py`、`swe_cli_parsers.py`、`swe_chat_adapter.py`。

## 5. 用户正文、工具协议和子 Agent 边界

**问题。** 真正的用户文本可能粘贴工具调用、工具结果、系统提示词等看似有结构的内容；若按文本标签继续拆，会凭空产生工具事件。另一方面，Claude 等 CLI 的一条协议记录可能真的含有多个结构化内容块。主日志中还可能混入 sidechain 或子 Agent 通知。

**处理。** 已确认的真人正文无论包含什么标签，都只形成**一个** `user_message`；协议层独立的思考、工具输入和结果才拆成相应事件。对同一原始记录按既定字段顺序处理正文、思考、工具调用、工具结果；记录之间保持主日志顺序，记录内保留内容块顺序。xAI 的同组重复用户片段只计一次；OpenCode 的用户 `text`/`file` 部分按一个用户消息保留。过滤侧及转换侧的本地 `swe_record_policy.py` 排除明确标记的 sidechain、子 Agent 活动及已识别的运行时注入。来源没有明确作者标记的极少数包装内容仍可能有归属歧义，需回看原始记录。

## 6. Unified Trace 字段逐步收敛

**问题。** 早期设计中的 `event_count`、`is_partial_trace`、`source_metadata`、事件时间戳、来源事件 ID 和事件元数据增加了语义歧义或冗余；原始数据也没有基准所需的七类 Query Type 标签。`prompt_intent` 等来源注释不等于该分类。

**处理。** 当前 `traces.parquet` 仅有 `trace_id`、`source`、`source_id`、`query_type`、`language`、`model`、`user_turn_count`；`events.parquet` 仅有 `trace_id`、`event_id`、`role`、`event_type`、`content`、`visibility`。全部 `query_type` 为 null，后续单独分类。WildChat 一行 Conversation 对应一条 Trace；SWE 一个主 Session 对应一条 Trace。`event_id` 从 0 开始，按主日志记录顺序及同一记录内内容块顺序连续编号。SWE 的 `user_turn_count` 只统计可确认的真人用户轮次。Trace ID 使用来源名前缀和七位序号，例如 `WildChat_4_8M_0000001`；来源 ID 不用 hash 假定全局唯一。需要工具 ID 等来源细节时，应查本地原始 transcript 和转换报告，而非假定精简后的 Parquet 仍有这些列。

## 7. 工具调用与结果不一定一一配对

**问题。** 早期 1k 样本有 **58 个**带 ID 的工具结果在同一主轨迹找不到调用（集中在 4 条 SWE Session），以及 **639 个**调用 ID 找不到结果。核查原始文件发现，55 个缺调用的结果集中在一条 Codex 日志，另外 3 个分属 Claude 日志；对应的结构化调用记录在主日志中确实不存在。原始、过滤后和样本的这 4 个文件当时逐字节相同，说明缺口不是过滤或抽样造成的。

**处理。** 保留“有调用、无结果”的记录，因为取消、结束或来源记录方式都可能造成此情况，不能伪造结果。后来在 `OriginalDataset-filter/scripts/filter_empty_swe_sessions.py` 增加规则：若**有 ID 的工具结果**在同一主 Agent 日志中没有同 ID 工具调用，则排除整个 Session；无 ID 的事件不因这条规则被删除。全量 SWE 过滤集因此新增排除 **41 条 Session、99 个此类结果 ID**（40 条 Claude、1 条 Codex），保留 **17,671** 条 Session。重新抽样及转换后，1k 输出中无匹配调用的结果 ID 为 **0**；仍有 **611 个**无结果的调用 ID，另外有 **4 个**结果在原始顺序中早于同 ID 调用。这些是不同统计口径，不应混称为“转换失败”。当前统计以 `conversion_report.json` 为准。

## 8. 代码重组时需要证明行为不变

**问题。** 过滤代码曾跨目录导入转换代码，SWE 多种 CLI 逻辑集中在长文件中，难以独立调试；简单地让重构后的代码“能运行”不足以证明事件内容和顺序未改变。

**处理。** filter、sample、UnifiedTrace 各自只导入本目录代码；SWE 按公共内容块处理、CLI 类和事件转换拆分。过滤与转换各自保存本地解析模块，重组时对应模块逐字节相同。重构前后用固定样本比对抽样 Session、解析审计和四个 UnifiedTrace 产物的 SHA-256；在未改变过滤规则的那轮重构中，四个产物逐字节相同。随后新增工具结果过滤规则，重新生成的数据**预期发生变化**，应以新规则下的验证结果判断，不能要求与旧产物哈希相同。

## 9. 当前验证与发布状态

- 完整过滤集验证通过：两个 WildChat 数据集的首个合格 hash、来源行映射和行数一致；SWE 从 **17,968** 条中累计排除 **297** 条，保留 **17,671** 条 Session，关联表与文件映射一致。排除原因分别为无主 Agent 交互 91、缺主 transcript 路径 149、无法解释格式 4、独立子 Agent Session 12、工具结果 ID 无对应调用 41。
- SWE 结构画像覆盖全部 **17,671** 个保留的主 transcript，14 种格式，失败文件数为 0。
- 重新抽取的 SWE 1k 有 1,000 个不同 Session；按新过滤规则复查，新增应排除数为 0。
- 当前 UnifiedTrace 验证通过：WildChat-1M **1,000 Trace / 4,808 Event**；WildChat-4.8M **1,000 / 3,630**；SWE **1,000 / 362,965**。3,000 条 Trace 的 `query_type` 全为 null。
- GitHub CLI 起初没有登录，第一次设备授权码过期；重新发起设备登录后，才创建并推送公开仓库。仓库只提交脚本和项目文档。根目录 `.gitignore` 使用白名单排除原始数据、过滤数据、1k 样本、Parquet 输出、JSON 报告与缓存。公开远端 `main` 是代码共享版本；未来改动按 `git pull --rebase origin main` → 修改并核查暂存文件 → `git commit` → `git push origin main` 更新。

以上数字来自当前本地的 `OriginalDataset-filter/*/filter_manifest.json`、`OriginalDataset-filter/filter_validation.json`、`OriginalDataset-filter-1k/SWE-Chat-filter-1k/sample_manifest.json` 和 `ProcessedDataset/UnifiedTrace/conversion_report.json`。这些报告本身含数据来源细节，因此未上传 Git。
