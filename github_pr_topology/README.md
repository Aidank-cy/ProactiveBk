# GitHub Development Graph Explorer

An exploratory, local research application for inspecting evidence-backed Issue, PR, review and commit relationships. The frontend defaults to Chinese; original GitHub evidence remains in its source language. [Public aggregate findings](PUBLIC_RESULTS.md) are available without raw graph records. It does **not** construct benchmark tasks, intent labels, evaluation rubrics or an Agent harness.

## Data frame and release boundary

The existing `github_repo_discovery` inventory is reused. The local inventory has 362 candidates: 318 with detected license information and 44 whose status remains unverified. This pilot selects eight repositories deterministically from the 318 license-verified candidates (seed `20261106`); the 44 remain in the prior experiment and are not copied into this public-ready pilot. This is a processing decision, not a judgment of their research value. The original `RELEASE_POLICY.md` remains controlling. Detection of a license does not settle redistribution rights for Issue/PR prose or third-party content. Generated raw API responses, graph data, cases and reports remain local and ignored by Git until a separate release review.

`LOCAL_RESEARCH` serves the locally collected, lawfully processable data. `PUBLIC_RELEASE` validates that every selected repository has `processing_track=license_verified` before exporting; it creates an auditable manifest and copies only processed outputs to a specified directory. Neither mode pushes or publishes anything. These modes use the same graph and analysis code.

## Setup

Python 3.11+ and Node 20+ are required. Authentication uses `GITHUB_TOKEN`, `GH_TOKEN`, or an existing `gh auth login` session; no credential is stored in this project. If an inherited proxy fails for GitHub while direct access works, set `GITHUB_BYPASS_PROXY=1`. From `github_pr_topology/`:

```bash
python3 -m pip install -e '.[test]'
cd frontend && npm ci && cd ..
```

The system Node may be old; select a Node 20+ binary in `PATH` before running npm.

## Collection and analysis

```bash
python3 scripts/prepare_sample.py
python3 scripts/run_collection.py
python3 scripts/build_graph.py
python3 scripts/validate_outputs.py
```

Or run all three with `python3 scripts/run_pipeline.py`. HTTP responses are cached under `.cache/http`; each PR endpoint and neighbor bundle is checkpointed under `data/raw`, so rerunning collection resumes. The first script records `results/selected_repositories.csv` and `results/sampled_prs.csv`. The second uses official GitHub REST and GraphQL APIs. The third generates JSONL graph nodes/edges/timelines, metrics, patterns, connected components, 15 case candidates and Markdown reports.

The default PR sampling frame is the newest 500 PRs by creation date in the observation period (from 2024-11-01 through run date). Within this bounded frame, 40 PRs/repo are uniformly random and 40 distinct PRs/repo are interaction-enriched. The GitHub endpoint's next-page status and frame truncation are recorded. **Random-sample prevalence applies only to this bounded recent frame.** Expanded neighbors and enriched PRs must never be folded into that prevalence denominator.

A one-hop expansion follows closing Issue metadata, timeline cross-references and candidate references in current text. It is bounded at 250 additional Issue/PR nodes per repository. Cross-repository references become boundary nodes. The raw source and truncation metadata are preserved. Current descriptions are temporally uncertain; final diffs are not initial diffs; commit author dates are not push dates. The historical time slice conservatively hides current editable text, undated links, commits whose visibility is unknown, and final-file diffs.

## Run the web application

In separate terminals, from `github_pr_topology/`:

```bash
python3 -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8001
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to FastAPI. API endpoints: `/api/repositories`, `/api/graph`, `/api/graph/neighbors`, `/api/nodes/{id}`, `/api/pr/{owner}/{repo}/{number}`, `/api/statistics`, `/api/components`, `/api/cases`, `/api/cases/{id}`. The graph starts in a macro Issue/PR view, with commits, reviews and files in the detail view or optional node filter.

## Tests and build

```bash
python3 -m pytest -q
cd frontend && npm run build
```

Optional browser smoke test (when Chromium can be installed):

```bash
cd frontend && npm install --no-save playwright && npx playwright install chromium && cd ..
node tests/browser_smoke.cjs
```

The smoke test exercises repository switching, node selection, PR timeline and evidence, statistics, case navigation, historical slicing, and saves screenshots under the ignored `screenshots/` directory.

## Release export

```bash
python3 scripts/export_bundle.py --mode LOCAL_RESEARCH --output /tmp/topology-local-export
python3 scripts/export_bundle.py --mode PUBLIC_RELEASE --clearance-manifest /path/to/reviewed-clearance.json --output /tmp/topology-public-candidate
```

`PUBLIC_RELEASE` refuses to run until a reviewed clearance manifest lists the intended distribution, reviewer, review date, all eight repository names, and the exact approved files. It refuses nonverified-license tracks, checks approved files for license-unverified cross-repository boundary names, requires separate authorization evidence for any such names, omits raw caches, and writes a manifest. This command only creates a local export and never publishes it. Never place local-research exports or restricted content in a public frontend bundle. The Vite build contains application code only; it fetches graph data from the local API.

## Output and interpretation

- `results/graph_nodes.jsonl`, `graph_edges.jsonl`, `pr_timelines.jsonl`: typed graph and PR histories.
- `results/graph_metrics.json`, `topology_patterns.csv`, `connected_components.csv`: quantitative analysis.
- `results/representative_cases.json`: case detail backing the UI.
- `reports/topology_analysis.md`, `case_studies.md`: offline report and evidence-linked cases.

The verified macro graph uses only explicit Issue/PR metadata or timeline references. Derived edges connect PRs sharing a verified Issue. Candidate edges come from current text or shared final-diff files and do not imply dependency. Connected components ignore edge direction and exclude internal commit/review/file nodes and boundary nodes. Missing observed links are not evidence of independence. See the generated report for denominators, truncation and data-quality limitations.
