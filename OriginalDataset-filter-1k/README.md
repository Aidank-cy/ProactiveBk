# Filtered 1k samples

Run `sample_1k.py` after the three directories under `../OriginalDataset-filter/`
have been built and validated. The default seed is 42. Each WildChat sample
contains 1,000 complete conversations from the independently deduplicated
source. Its manifest stores selected filtered row indices and their original
global row indices. The SWE sample contains 1,000 distinct Sessions, each
with its copied main transcript and available supplementary files.

Before sampling SWE, run `../OriginalDataset-filter/scripts/profile_swe_sampling.py`
to build a read-only structural profile of the full main transcript files. The
SWE sampler reads that profile and balances the 14 eligible CLI format families,
then covers different observed content structures and file sizes within each
family. The filtered source already excludes `agent-*` subagent Sessions; the
sample script checks that none remain. The sample script only selects,
copies, and validates source files; all event extraction is implemented under
`../ProcessedDataset/UnifiedTrace/scripts/`.

`sample_1k.py` is the command entry point. `sample_common.py` contains shared
provenance and manifest helpers; `sample_wildchat.py` and `sample_swe.py`
contain the dataset-specific sampling functions. These modules import only
code from this sample directory and read filtered datasets as input data.

The source datasets and their original versions are not modified by sampling.
