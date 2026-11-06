# ProactiveBk

Scripts for downloading, filtering, sampling, and converting WildChat and SWE-Chat interaction records.

- `OriginalDataset/*.py`: source download and schema inspection.
- `OriginalDataset-filter/scripts/`: filtering and filter validation.
- `OriginalDataset-filter-1k/*.py`: deterministic sampling from filtered datasets.
- `ProcessedDataset/UnifiedTrace/scripts/`: Unified Trace conversion and validation.

Each stage's README documents its inputs and commands. Dataset files, samples, Parquet outputs, JSON reports, caches, and dataset-provided documentation are excluded from Git by the root `.gitignore` allowlist.

The main implementation problems, evidence, and resolutions are recorded in [PROJECT_HISTORY.md](PROJECT_HISTORY.md).

## GitHub research projects

- [Repository discovery](github_repo_discovery/README.md): repository selection pipeline and public results.
- [PR feasibility](github_pr_feasibility/README.md): PR trajectory feasibility pilot.
- [Development Graph Explorer](github_pr_topology/README.md): topology collection code and Chinese-language research dashboard. Its [public aggregate findings](github_pr_topology/PUBLIC_RESULTS.md) contain numeric results only; graph records, original PR text, and case details remain local pending release review.

## Git workflow

The remote `main` branch is the shared version. Before changing scripts, run `git pull --rebase origin main`. After checking `git status` and the staged file list, commit the code and run `git push origin main`. Raw and restricted generated data stays local; only explicitly reviewed public aggregate files are staged.
