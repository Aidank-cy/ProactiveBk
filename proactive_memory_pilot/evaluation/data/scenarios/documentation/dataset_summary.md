# Fixed four-scenario dataset

All counts are derived from the fixed JSON. Initial and final-context tokens are **estimates** (UTF-8 bytes / 3), not API token usage. API calls assume one model and one sample; multiply by model and sample counts.

| Scenario | Events | Tasks | Unique memory Q | Memory calls | Reactive calls | Proactive calls | Total calls | Ready task-stage pairs | Newly ready | Empty stages | Invalidations | Initial tokens est. | Final tokens est. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rental | 18 | 4 | 31 | 553 | 70 | 19 | 642 | 17 | 3 | 6 | 2 | 373 | 1385 |
| travel | 23 | 5 | 31 | 674 | 106 | 24 | 804 | 12 | 5 | 16 | 4 | 177 | 2193 |
| shopping | 19 | 5 | 32 | 518 | 78 | 20 | 616 | 24 | 5 | 7 | 4 | 169 | 1489 |
| team_building | 20 | 5 | 35 | 735 | 105 | 21 | 861 | 19 | 5 | 10 | 4 | 167 | 1712 |

The four separate JSON files are the source for `all_scenarios.json`; regenerate with `python -m evaluation.data.scenarios.materialize`. Freeze both the builder and generated files before inference.
