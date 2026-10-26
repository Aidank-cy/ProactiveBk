# ProactiveBk

Scripts for downloading, filtering, sampling, and converting WildChat and SWE-Chat interaction records.

- `OriginalDataset/*.py`: source download and schema inspection.
- `OriginalDataset-filter/scripts/`: filtering and filter validation.
- `OriginalDataset-filter-1k/*.py`: deterministic sampling from filtered datasets.
- `ProcessedDataset/UnifiedTrace/scripts/`: Unified Trace conversion and validation.

Each stage's README documents its inputs and commands. Dataset files, samples, Parquet outputs, JSON reports, caches, and dataset-provided documentation are excluded from Git by the root `.gitignore` allowlist.

## Git workflow

The remote `main` branch is the shared version. Before changing scripts, run `git pull --rebase origin main`. After checking `git status` and the staged file list, commit the code and run `git push origin main`. Generated data stays local and is never staged.
