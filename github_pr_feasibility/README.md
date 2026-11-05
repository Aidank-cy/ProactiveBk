# GitHub PR trajectory feasibility pilot

This independent project lives inside the existing `ProactiveBk` workspace. It studies whether GitHub PR histories can support a later proactive coding benchmark. It does not build an Agent harness, judge, rubric, or benchmark instances.

## Run

Requires Python 3.11+, `requests`, `PyYAML`, and `pytest` for tests.

```bash
cd /home/hezd/nfs_hzd/ProactiveBk/github_pr_feasibility
python3 -m pip install -e '.[dev]'
python3 -m pytest -q
export GITHUB_TOKEN=...  # or authenticate gh with: gh auth login -h github.com
python3 scripts/run_pilot.py --config config.yaml
# Rebuild tables and reports offline from already saved raw responses:
python3 scripts/run_pilot.py --analysis-only
```

Credentials are read from `GITHUB_TOKEN` or `gh auth token`; never put a token in `config.yaml` or `.env.example`. The script exits with code 2 and writes no empirical results when authentication is unavailable. A GitHub token with public repository read access is sufficient. The pilot can make thousands of API calls; the client honors rate limits and writes responses to `.cache/` to resume after interruption.

## Sampling design

The Search API supplies up to five pages of 100 repositories per star stratum by default. Its ranking and index are a bounded convenience frame, so the six repositories are **not** representative of all GitHub repositories. The entire returned candidate metadata is saved to `results/repositories.csv`; recent merged PR activity is queried only for candidates actually evaluated, with unqueried rows marked explicitly to bound API cost. Within each stratum, eligible candidates are shuffled with a fixed seed; distinct owners are preferred. Replacements and their reasons are recorded when a candidate has fewer than 20 merged PRs or an incomplete search frame.

Merged PRs are searched by merge date in the configured window. Date ranges are split recursively whenever search exceeds GitHub's 1,000-result limit. Each shard retains its count and completeness flag in `data/processed/pr_sampling_frames.json`. Ten PRs are uniform random draws from that frame. Ten more are chosen from a bounded high issue-comment pool by review comments, commits, then issue comments, after excluding the random draw. Random draw probabilities are recorded; enriched draw probabilities are unspecified. Natural prevalence estimates use only the random group.

## Evidence and limits

`data/raw/` contains complete REST responses per PR: metadata, issue comments, formal reviews, inline review comments, timeline events, commits, commit details and files, plus explicitly identifiable linked issues. `data/processed/events/` contains chronological normalized events. API request bodies are cached at `.cache/`; collection resumes by skipping completed PR files. Failures are appended to `results/errors.jsonl` and do not erase completed data.

Current PR titles, descriptions, and issue bodies might have changed. They are retained for audit but are not treated as verified text at a cutoff. Edited comments are marked uncertain. Commit author/committer dates do not establish push time. Review commit associations and timeline commit events support candidate code states; exact availability immediately before review can remain uncertain. Feedback categories, inferability, and A/B/C labels are exploratory heuristics, not ground truth. The manual review queue is the place to validate them.

Optional semantic assistance uses `llm_provider: openai_compatible` with `llm_endpoint`, `llm_model`, and `llm_api_key_env` in config. Only a candidate requirement and prior dated context are sent. The model never receives the full future trajectory or final implementation. Its output remains unverified and does not replace manual annotation.

GitHub timeline `committed` events can lack event timestamps. A later review on a later PR commit is counted separately as a **possible** feedback-to-revision sequence, with timing and causality unverified. A zero verified-revision count is therefore an evidence limit, not proof of no code changes.

## Outputs

The runner writes `results/repositories.csv`, `sampled_prs.csv`, `trajectory_features.csv`, `candidate_cutoffs.jsonl`, `candidate_intents.jsonl`, `feasibility_labels.csv`, `manual_review_queue.csv`, and `summary_statistics.json`. It also writes `reports/feasibility_report.md` and `case_studies.md` using retrieved PRs only. No case study or result is fabricated when API access is unavailable.
