# Published pilot snapshot

This directory contains a GitHub PR feasibility study completed on 2026-11-05. The pilot sampled 120 merged PRs from six repositories: 60 uniform random draws and 60 interaction-enriched draws. Collection finished for all 120 PRs (`results/collection_status.json`).

Start with [`reports/feasibility_report.md`](reports/feasibility_report.md), then [`reports/case_studies.md`](reports/case_studies.md). Machine-readable summaries and the manual review queue are under `results/`; the complete returned repository candidate metadata is in `results/repositories.csv`.

The published snapshot excludes `data/raw/`, `data/processed/events/`, `.cache/`, and the historical `results/errors.jsonl` log. Those files are large or contain complete third-party API responses. Source PR and comment URLs are included in the published tables and case studies. To reproduce the collection, authenticate GitHub and run `python3 scripts/run_pilot.py` as described in `README.md`.

All intent categories and A/B/C labels are provisional heuristics. No candidate has been approved by manual review. A later review on a later commit is treated as a possible revision sequence, not proof of push timing or causality.
