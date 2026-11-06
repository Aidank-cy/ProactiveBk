# GitHub repository discovery

This independent project discovers public GitHub repositories created **2024-11-01 through 2026-11-01 inclusive (UTC)** and applies the current staged criteria:

1. At least 1,000 stars.
2. At least 500 pull requests of all states and at least 500 issues. GraphQL `issues.totalCount` excludes pull requests.
3. At least 500 forks.
4. A GitHub-detected SPDX license marked `isOsiApproved=true` by the pinned SPDX license list.

Language, topic, domain, fork status, archive status and activity are not mandatory filters. Contributor count and source LOC are outside this current screening round. All mutable metadata is observed when collected, not as of the creation-date cutoff.

## Run

```bash
python3 -m pip install -e '.[test]'
python3 -m pytest -q
python3 scripts/run_discovery.py
```

Set `GITHUB_TOKEN`, `GH_TOKEN`, or authenticate with `gh auth login`. The run stores an HTTP cache, pinned SPDX license list and SQLite checkpoint in `.cache/`. Rerunning resumes completed search partitions and checks. `--report-only` regenerates results. `--limited N` processes at most N candidates per check stage and labels results incomplete. `--skip-discovery` checks already discovered candidates without searching.

The search recursively partitions dates and then stars until each complete query has no more than 1,000 hits. It has bounded parallelism across partitions and pages. Repository IDs are deduplicated. GraphQL batches issue and PR counts; REST repository metadata verifies current license detection. The SPDX license list is pinned by Git blob SHA in `config.yaml`. Unknown API responses, missing license detection and unrecognized license identifiers remain pending. Numerical thresholds and worker counts are configurable in `config.yaml`.

Local outputs include `results/all_candidates.csv`, `qualified_repositories.csv`, `excluded_repositories.csv`, `pending_repositories.csv`, `processing_candidates.csv`, `restricted/repositories.csv`, stage and date counts, summary JSON, and the report. The public repository includes only the licensed repository list, aggregate counts, code and report. License-unverified repository-level records are gitignored. See [RELEASE_POLICY.md](RELEASE_POLICY.md) before publishing downstream artifacts. Counts are verified lower bounds until search coverage and all checks are complete. Five-year counts are not measured under the revised two-year scope.
