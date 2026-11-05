# GitHub PR trajectory feasibility pilot

All counts below are descriptive. Automatic labels are provisional and require human review.

Observation window: 2024-01-01 through 2026-11-05 (UTC). Seed: 20261105. Initial thresholds: stars ≥500, forks ≥50, pushed within 180 days.

## Discovery and selection

The official GitHub Search API was queried by star stratum without language, topic, or domain filters. The first configured pages sorted by API default relevance form a bounded convenience frame; this is not a random sample of all eligible GitHub repositories. Eligible candidates were shuffled using the configured seed, with distinct owners preferred. All returned candidates are in `results/repositories.csv`.

Candidate repositories retained: 1500; selected: 6.

## PR sampling

Merged PRs in the observation window were enumerated using date-sharded Search API queries. Ten PRs per repository were sampled uniformly from that frame; another ten were chosen from a bounded high issue-comment pool by review comment count, commit count, then issue-comment count after excluding the random draw. Search shards and completeness flags are saved in `data/processed/pr_sampling_frames.json`. The GitHub Search API may omit results when `incomplete_results` is true; any such shard is marked incomplete.

## Repository results

| Repository | Stars | Forks | Recent merged PRs | Sampled | Human review comments / PR | Review rounds / PR | Commits / PR | A | B | C |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Relm4/Relm4 | 1991 | 106 | 18 | 20 | 2.60 | 1.15 | 3.20 | 0 | 8 | 12 |
| superdb/zui | 1982 | 135 | 0 | 20 | 2.80 | 1.20 | 8.70 | 0 | 6 | 14 |
| droidrun/mobilerun | 9959 | 1077 | 79 | 20 | 1.30 | 0.30 | 8.20 | 0 | 1 | 19 |
| firezone/firezone | 9168 | 466 | 1341 | 20 | 19.25 | 2.65 | 25.30 | 0 | 12 | 8 |
| openinterpreter/openinterpreter | 68792 | 5934 | 44 | 20 | 1.05 | 0.50 | 3.55 | 0 | 3 | 17 |
| chartjs/Chart.js | 67779 | 11957 | 15 | 20 | 3.50 | 1.75 | 3.15 | 0 | 7 | 13 |

## Research questions and trajectory availability

The following natural-prevalence estimates use only the random group. Numerators and denominators are shown because this pilot is small. `rich_context` requires at least one dated, unedited human comment before feedback or merge and at least one PR commit; this is a screening proxy, not a verified original task statement. `substantive_feedback` is an English-oriented heuristic after an identifiable code state.

- rich_context: 48/60 (80.0%); Wilson 95% interval 68.2%–88.2%
- substantive_feedback: 7/60 (11.7%); Wilson 95% interval 5.8%–22.2%
- requirement_implementation_revision: 0/60 (0.0%); Wilson 95% interval 0.0%–6.0%
- possible_feedback_revision: 1/60 (1.7%); Wilson 95% interval 0.3%–8.9%
- candidate_cutoff: 7/60 (11.7%); Wilson 95% interval 5.8%–22.2%
- A: 0/60 (0.0%); Wilson 95% interval 0.0%–6.0%

## Selection funnel

- sampled_prs: 120/120
- meaningful_historical_context: 105/120
- substantive_later_human_feedback: 35/120
- subsequent_code_revision: 0/120
- identifiable_cutoff: 0/120
- recoverable_historical_state: 0/120
- plausible_implicit_intent: 0/120

Alternative branch with a later review on a later commit (timing and causality uncertain): 12/120.

## Random versus interaction-enriched

- random: 60 PRs; A=0/60; A/B=7/60; feedback=7/60; feedback then verified revision=0/60; possible later-review revision=1/60.
- interaction_enriched: 60 PRs; A=0/60; A/B=30/60; feedback=30/60; feedback then verified revision=0/60; possible later-review revision=12/60.

## PR-level distributions

- human_reviewer_comments: n=120, median=1.0, mean=5.083333333333333.
- commits: n=120, median=3.0, mean=8.683333333333334.
- review_rounds: n=120, median=1.0, mean=1.2583333333333333.
- feedback_to_revision_sequences: n=120, median=0.0, mean=0.0.
- possible_feedback_to_revision_sequences: n=120, median=0.0, mean=0.38333333333333336.
- development_duration_days: n=120, median=1.97609375, mean=17.05225848765432.
- candidate_future_intents: n=120, median=0.0, mean=0.6666666666666666.
- valid_cutoff_candidates: n=120, median=0.0, mean=0.6666666666666666.

## Repository metric associations

Descriptive Spearman correlations compare repository-level provisional A/B yield with metadata. With six selected repositories, these are unstable and have no causal interpretation.

- stars: 6 repositories; rho=-0.37142857142857144.
- forks: 6 repositories; rho=-0.37142857142857144.
- recent_merged_prs: 6 repositories; rho=0.08571428571428572.

## Data quality and interpretation

- Repository selection uses a bounded Search API frame. GitHub's ranking and search indexing affect coverage. Search query metadata and the complete returned candidate frame are retained.
- Current PR titles, descriptions, and linked issue bodies may have been edited. They are retained as raw evidence but excluded from verified earlier-context text.
- Commit author and committer times are never used as proof of push time. Revision counts rely on observable timeline commit events; the API may underreport these.
- In these responses, timeline `committed` entries lack event timestamps. Therefore zero verified post-feedback revisions means unavailable timing evidence, not proof that no code changed. A later review on a later PR commit is reported separately as a possible sequence.
- Review commit IDs identify reviewed code states. The exact moment just before review submission remains uncertain when no earlier visibility event exists.
- GitHub PR commit and file listing endpoints can cap results. Per-PR completeness flags compare retrieved lists with reported counts.
- Regex feedback categories and lexical inferability are unverified screening cues. Human annotation is needed before any benchmark intent is accepted.
- Feedback regexes are English oriented; non-English discussions may be missed. Repository selection itself has no language filter.
- Recent merged PR activity is computed only for evaluated repository candidates to bound API cost; unqueried candidates retain an explicit status.
- Stars, forks, and recent activity are described alongside yields. Six repositories cannot establish a reliable association or causality.

## Suggested next-stage selection criteria

Retain a random baseline; enrich separately using observable interaction counts. Favor repositories with complete historical PR frames, dated human task context, review-associated commits, and observable post-feedback revisions. Verify candidate cutoffs and implicit-intent inferability manually before benchmark construction.
