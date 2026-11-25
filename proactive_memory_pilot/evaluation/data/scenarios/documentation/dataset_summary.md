# Fixed four-scenario dataset

All counts are derived from the fixed JSON. Initial-context tokens are **estimates** (UTF-8 bytes / 3), not API token usage. API calls assume one model and one sample; multiply by model and sample counts.

| Scenario | Events | Tasks | Unique memory Q | Memory calls | Reactive calls | Proactive calls | Total calls | Ready task-stage pairs | Newly ready | Empty stages | Invalidations | Initial tokens est. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rental | 18 | 4 | 30 | 534 | 70 | 19 | 623 | 16 | 3 | 6 | 2 | 286 |
| travel | 21 | 5 | 31 | 617 | 97 | 22 | 736 | 22 | 5 | 9 | 4 | 177 |
| shopping | 18 | 5 | 33 | 499 | 73 | 19 | 591 | 25 | 5 | 7 | 3 | 169 |
| team_building | 20 | 5 | 30 | 555 | 90 | 21 | 666 | 20 | 5 | 10 | 4 | 167 |

The four separate JSON files are the source for `all_scenarios.json`; regenerate with `python -m evaluation.data.scenarios.materialize`. Freeze both the builder and generated files before inference.
