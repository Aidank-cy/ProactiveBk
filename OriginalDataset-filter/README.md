# Filtered original datasets

Each WildChat dataset first removes Conversations with no nonblank user or
assistant message content, then deduplicates independently by
`conversation_hash`. The first eligible row in sorted shard-name and row order
is retained, with every retained field unchanged. The Parquet shard names and
schemas match the source.
`kept_original_indices.parquet` maps each filtered row, in order, to its
original global row index. `filter_manifest.json` records counts and revision.

The SWE-chat Session tables have unique `session_id` values. The filter uses
its own format-specific CLI parser classes under `scripts/` to remove Sessions with no
extractable nonblank **main-agent** human, assistant, thinking, or tool content.
Claude `isSidechain` records do not qualify as main-agent content; Sessions
containing only sidechain records are classified as having no main-agent
interaction and removed by the same rule. `agent-*` Session IDs or main
transcript stems identify supplementary subagent Sessions and are removed
before main transcript inspection. Sessions
lacking a main transcript and uninterpretable source formats are also excluded.
The filter also removes an entire Session when a tool result has an ID but no
tool call with that ID exists in its parsed main-agent transcript. Matching is
by ID within the Session, independent of event order. Calls without results
and tool events without IDs do not trigger this rule.
The shared record policy also excludes explicitly marked subagent records
inside retained main logs, including Pi `custom_message` types beginning
`subagent-` or `subagent_`. Retained transcript files remain complete raw
copies; the record policy is applied when reading their events.
The filter removes their rows from Session-keyed Parquet
tables and their unreferenced transcript files. Repeated `session_id` values
in `conversations.parquet` are interaction records within a Session; rows for
retained Sessions remain. Supplementary tables without `session_id` remain
unchanged because checkpoint or repository records may be shared.

Build scripts are in `scripts/filter_wildchat.py` and
`scripts/copy_swe_chat.py`. The local `scripts/swe_format.py` detects formats;
`scripts/swe_common.py` reads transcripts and expands content blocks;
`scripts/swe_cli_parsers.py` holds one class per CLI family;
`scripts/swe_chat_adapter.py` dispatches records and normalizes events;
`scripts/swe_record_policy.py` defines record inclusion. They do not import code
from the sampler or UnifiedTrace directory. The parser and policy currently
match the local copies in UnifiedTrace; any future rule change must be applied
and compared in both directories. `scripts/profile_swe_sampling.py` creates the
format profile used by the separate 1k sampler. The SWE copy builder invokes
`scripts/filter_empty_swe_sessions.py` before publication; that script can
also update an existing filtered SWE copy with a rollback backup. Run
`scripts/validate_filtered_datasets.py` after building all three.
The original datasets are never modified.
