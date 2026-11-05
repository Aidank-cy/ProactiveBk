"""Descriptive pilot tables and source-linked case studies."""
from __future__ import annotations

import json
import statistics
import math
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime, timezone


def mean(rows, key):
    values = [float(r[key]) for r in rows if r.get(key) is not None]
    return statistics.mean(values) if values else None


def fraction(rows, predicate):
    n = sum(bool(predicate(r)) for r in rows)
    total = len(rows)
    p = n / total if total else None
    if total:
        z = 1.96
        center = (p + z*z/(2*total)) / (1 + z*z/total)
        margin = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / (1 + z*z/total)
        interval = [max(0, center-margin), min(1, center+margin)]
    else:
        interval = None
    return {"numerator": n, "denominator": total, "proportion": p,
            "wilson_95_interval": interval}


def rank_correlation(pairs):
    """Descriptive Spearman correlation with average ranks for ties; no significance claim."""
    if len(pairs) < 3:
        return None
    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        output = [0.] * len(values)
        i = 0
        while i < len(order):
            j = i + 1
            while j < len(order) and values[order[j]] == values[order[i]]:
                j += 1
            for k in range(i, j):
                output[order[k]] = (i + j - 1) / 2
            i = j
        return output
    x, y = ranks([a for a, _ in pairs]), ranks([b for _, b in pairs])
    mx, my = statistics.mean(x), statistics.mean(y)
    denom = math.sqrt(sum((v-mx)**2 for v in x) * sum((v-my)**2 for v in y))
    return sum((a-mx)*(b-my) for a, b in zip(x, y)) / denom if denom else None


def distribution(rows, key):
    vals = [float(r[key]) for r in rows if r.get(key) is not None]
    return {"n": len(vals), "min": min(vals) if vals else None,
            "median": statistics.median(vals) if vals else None,
            "mean": statistics.mean(vals) if vals else None,
            "max": max(vals) if vals else None}


def build_statistics(repositories, sampled, features, cutoffs, frames):
    by_repo = defaultdict(list)
    by_group = defaultdict(list)
    assignment = {(r["repository"], r["number"]): r["sampling_group"] for r in sampled}
    for f in features:
        by_repo[f["repository"]].append(f)
        by_group[assignment.get((f["repository"], f["pr_number"]), "unknown")].append(f)
    repo_stats = []
    for repo in [r for r in repositories if r["selected"]]:
        rows = by_repo[repo["full_name"]]
        repo_stats.append({"repository": repo["full_name"], "stars": repo["stars"], "forks": repo["forks"],
                           "recent_merged_prs": repo["recent_merged_prs"], "sampled_prs": len(rows),
                           "avg_human_review_comments": mean(rows, "human_reviewer_comments"),
                           "avg_review_rounds": mean(rows, "review_rounds"),
                           "avg_commits": mean(rows, "commits"),
                           "substantive_later_feedback": fraction(rows, lambda x: x["later_human_requirements"]),
                           "feedback_followed_by_revision": fraction(rows, lambda x: x["feedback_to_revision_sequences"] > 0),
                           "possible_feedback_followed_by_revision": fraction(rows, lambda x: x["possible_feedback_to_revision_sequences"] > 0),
                           "candidate_cutoffs_per_pr": mean(rows, "valid_cutoff_candidates"),
                           "labels": {k: fraction(rows, lambda x, k=k: x["provisional_label"] == k)
                                      for k in "ABC"},
                           "reconstructable_cutoff": fraction(rows, lambda x: x["cutoff_code_state_recoverable"])})
    associations = {}
    for metric in ("stars", "forks", "recent_merged_prs"):
        pairs = [(r[metric], r["labels"]["A"]["proportion"] + r["labels"]["B"]["proportion"])
                 for r in repo_stats if r[metric] is not None and r["labels"]["A"]["proportion"] is not None]
        associations[metric] = {"repositories": len(pairs), "spearman_rho_descriptive": rank_correlation(pairs)}
    group_stats = {group: {"n": len(rows),
                           "A": fraction(rows, lambda x: x["provisional_label"] == "A"),
                           "A_or_B": fraction(rows, lambda x: x["provisional_label"] in "AB"),
                           "substantive_feedback": fraction(rows, lambda x: x["later_human_requirements"]),
                           "revision_after_feedback": fraction(rows, lambda x: x["feedback_to_revision_sequences"] > 0),
                           "possible_revision_after_feedback": fraction(rows, lambda x: x["possible_feedback_to_revision_sequences"] > 0)}
                   for group, rows in by_group.items()}
    funnel = [("sampled_prs", lambda x: True),
              ("meaningful_historical_context", lambda x: x["meaningful_history_before_feedback"]),
              ("substantive_later_human_feedback", lambda x: x["later_human_requirements"]),
              ("subsequent_code_revision", lambda x: x["feedback_to_revision_sequences"] > 0),
              ("identifiable_cutoff", lambda x: x["candidate_cutoff_identifiable"]),
              ("recoverable_historical_state", lambda x: x["cutoff_code_state_recoverable"]),
              ("plausible_implicit_intent", lambda x: x["future_requirement_linked_to_context"])]
    remaining = features
    funnel_rows = []
    for name, pred in funnel:
        remaining = [f for f in remaining if pred(f)]
        funnel_rows.append({"stage": name, "count": len(remaining), "initial_denominator": len(features)})
    possible_funnel = [f for f in features if f["meaningful_history_before_feedback"]
                       and f["later_human_requirements"] and f["possible_feedback_to_revision_sequences"] > 0
                       and f["candidate_cutoff_identifiable"] and f["cutoff_code_state_recoverable"]]
    return {"sample_size": len(features), "repository_statistics": repo_stats,
            "group_statistics": group_stats,
            "distributions": {key: distribution(features, key) for key in
                              ("human_reviewer_comments", "commits", "review_rounds",
                               "feedback_to_revision_sequences", "possible_feedback_to_revision_sequences",
                               "development_duration_days",
                               "candidate_future_intents", "valid_cutoff_candidates")},
            "selection_funnel": funnel_rows,
            "possible_revision_funnel_count": len(possible_funnel),
            "random_baseline": {"rich_context": fraction(by_group["random"], lambda x: x["meaningful_history_before_feedback"]),
                                "substantive_feedback": fraction(by_group["random"], lambda x: x["later_human_requirements"]),
                                "requirement_implementation_revision": fraction(by_group["random"], lambda x: x["feedback_to_revision_sequences"] > 0),
                                "possible_feedback_revision": fraction(by_group["random"], lambda x: x["possible_feedback_to_revision_sequences"] > 0),
                                "candidate_cutoff": fraction(by_group["random"], lambda x: x["candidate_cutoff_identifiable"]),
                                "A": fraction(by_group["random"], lambda x: x["provisional_label"] == "A")},
            "pr_sampling_frames": frames,
            "repository_metric_associations": associations,
            "interpretation": "All labels and feedback categories are provisional heuristics. Random rates apply only to sampled repositories and the stated API search frame. Enriched PRs are excluded from natural prevalence estimates."}


def write_reports(report_dir: Path, stats: dict, repositories: list, sampled: list,
                  features: list, cutoffs: list, raw_dir: Path, cfg: dict | None = None):
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# GitHub PR trajectory feasibility pilot", "",
             "All counts below are descriptive. Automatic labels are provisional and require human review.", "",
             f"Observation window: {(cfg or {}).get('observation_start', 'see config.yaml')} through {(cfg or {}).get('observation_end') or datetime.now(timezone.utc).date().isoformat()} (UTC). Seed: {(cfg or {}).get('seed', 'see config.yaml')}. Initial thresholds: stars ≥{(cfg or {}).get('stars_min', 500)}, forks ≥{(cfg or {}).get('forks_min', 50)}, pushed within {(cfg or {}).get('pushed_within_days', 180)} days.", "",
             "## Discovery and selection", "",
             "The official GitHub Search API was queried by star stratum without language, topic, or domain filters. "
             "The first configured pages sorted by API default relevance form a bounded convenience frame; this is not a random sample of all eligible GitHub repositories. "
             "Eligible candidates were shuffled using the configured seed, with distinct owners preferred. All returned candidates are in `results/repositories.csv`.", "",
             f"Candidate repositories retained: {len(repositories)}; selected: {sum(r['selected'] for r in repositories)}.", "",
             "## PR sampling", "",
             "Merged PRs in the observation window were enumerated using date-sharded Search API queries. "
             "Ten PRs per repository were sampled uniformly from that frame; another ten were chosen from a bounded high issue-comment pool by review comment count, commit count, then issue-comment count after excluding the random draw. "
             "Search shards and completeness flags are saved in `data/processed/pr_sampling_frames.json`. "
             "The GitHub Search API may omit results when `incomplete_results` is true; any such shard is marked incomplete.", "",
             "## Repository results", "",
             "| Repository | Stars | Forks | Recent merged PRs | Sampled | Human review comments / PR | Review rounds / PR | Commits / PR | A | B | C |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in stats["repository_statistics"]:
        labels = [row["labels"][k]["numerator"] for k in "ABC"]
        lines.append(f"| {row['repository']} | {row['stars']} | {row['forks']} | {row['recent_merged_prs']} | {row['sampled_prs']} | {row['avg_human_review_comments'] or 0:.2f} | {row['avg_review_rounds'] or 0:.2f} | {row['avg_commits'] or 0:.2f} | {labels[0]} | {labels[1]} | {labels[2]} |")
    lines.extend(["", "## Research questions and trajectory availability", "",
             "The following natural-prevalence estimates use only the random group. Numerators and denominators are shown because this pilot is small. `rich_context` requires at least one dated, unedited human comment before feedback or merge and at least one PR commit; this is a screening proxy, not a verified original task statement. `substantive_feedback` is an English-oriented heuristic after an identifiable code state.", ""])
    for key, value in stats["random_baseline"].items():
        lines.append(f"- {key}: {value['numerator']}/{value['denominator']} ({value['proportion']:.1%}); Wilson 95% interval {value['wilson_95_interval'][0]:.1%}–{value['wilson_95_interval'][1]:.1%}" if value["proportion"] is not None else f"- {key}: no observations")
    lines.extend(["", "## Selection funnel", ""])
    for stage in stats["selection_funnel"]:
        lines.append(f"- {stage['stage']}: {stage['count']}/{stage['initial_denominator']}")
    lines += ["", f"Alternative branch with a later review on a later commit (timing and causality uncertain): {stats['possible_revision_funnel_count']}/{stats['sample_size']}."]
    lines.extend(["", "## Random versus interaction-enriched", ""])
    for group, value in stats["group_statistics"].items():
        lines.append(f"- {group}: {value['n']} PRs; A={value['A']['numerator']}/{value['A']['denominator']}; A/B={value['A_or_B']['numerator']}/{value['A_or_B']['denominator']}; feedback={value['substantive_feedback']['numerator']}/{value['substantive_feedback']['denominator']}; feedback then verified revision={value['revision_after_feedback']['numerator']}/{value['revision_after_feedback']['denominator']}; possible later-review revision={value['possible_revision_after_feedback']['numerator']}/{value['possible_revision_after_feedback']['denominator']}.")
    lines.extend(["", "## PR-level distributions", ""])
    for key, value in stats["distributions"].items():
        lines.append(f"- {key}: n={value['n']}, median={value['median']}, mean={value['mean']}.")
    lines.extend(["", "## Repository metric associations", "",
                  "Descriptive Spearman correlations compare repository-level provisional A/B yield with metadata. With six selected repositories, these are unstable and have no causal interpretation.", ""])
    for metric, value in stats["repository_metric_associations"].items():
        lines.append(f"- {metric}: {value['repositories']} repositories; rho={value['spearman_rho_descriptive']}.")
    lines.extend(["", "## Data quality and interpretation", "",
                  "- Repository selection uses a bounded Search API frame. GitHub's ranking and search indexing affect coverage. Search query metadata and the complete returned candidate frame are retained.",
                  "- Current PR titles, descriptions, and linked issue bodies may have been edited. They are retained as raw evidence but excluded from verified earlier-context text.",
                  "- Commit author and committer times are never used as proof of push time. Revision counts rely on observable timeline commit events; the API may underreport these.",
                  "- In these responses, timeline `committed` entries lack event timestamps. Therefore zero verified post-feedback revisions means unavailable timing evidence, not proof that no code changed. A later review on a later PR commit is reported separately as a possible sequence.",
                  "- Review commit IDs identify reviewed code states. The exact moment just before review submission remains uncertain when no earlier visibility event exists.",
                  "- GitHub PR commit and file listing endpoints can cap results. Per-PR completeness flags compare retrieved lists with reported counts.",
                  "- Regex feedback categories and lexical inferability are unverified screening cues. Human annotation is needed before any benchmark intent is accepted.",
                  "- Feedback regexes are English oriented; non-English discussions may be missed. Repository selection itself has no language filter.",
                  "- Recent merged PR activity is computed only for evaluated repository candidates to bound API cost; unqueried candidates retain an explicit status.",
                  "- Stars, forks, and recent activity are described alongside yields. Six repositories cannot establish a reliable association or causality.",
                  "", "## Suggested next-stage selection criteria", "",
                  "Retain a random baseline; enrich separately using observable interaction counts. Favor repositories with complete historical PR frames, dated human task context, review-associated commits, and observable post-feedback revisions. Verify candidate cutoffs and implicit-intent inferability manually before benchmark construction.", ""])
    (report_dir / "feasibility_report.md").write_text("\n".join(lines))
    by_key = {(c["repository"], c["pr_number"]): c for c in cutoffs if c["best"]}
    ranked = sorted(features, key=lambda f: (f["provisional_label"] == "A", f["provisional_label"] == "B",
                                              f["human_reviewer_comments"]), reverse=True)[:10]
    cases = ["# Retrieved PR case studies", "", "These are original GitHub development records, not Agent interaction traces. Current titles and bodies may have been edited.", ""]
    for f in ranked:
        key = (f["repository"], f["pr_number"])
        c = by_key.get(key)
        owner, repo = f["repository"].split("/")
        raw_path = raw_dir / owner / repo / f"{f['pr_number']}.json"
        if not raw_path.exists():
            continue
        data = json.loads(raw_path.read_text())
        pr = data["pull"]
        cases += [f"## [{f['repository']}#{f['pr_number']}]({f['url']})", "",
                  f"- Original task candidate: {pr.get('title') or '(no title)'} (current title, temporal availability unverified).",
                  f"- Development history: opened {pr.get('created_at')}; {len(data['commits'])} commits; {len(data['reviews'])} formal reviews; merged {pr.get('merged_at')}."]
        event_path = Path(raw_dir).parent / "processed" / "events" / owner / repo / f"{f['pr_number']}.json"
        if event_path.exists():
            events = json.loads(event_path.read_text())
            cases.append("- Chronological evidence:")
            for event in [e for e in events if e["event_type"] in
                          {"pr_opened", "issue_comment", "review", "review_comment", "timeline_committed", "pr_merged"}][:12]:
                summary = " ".join(event["content"].split())[:160]
                cases.append(f"  - {event['timestamp']} {event['event_type']} by {event['actor'] or 'unknown'}: {summary or '(no stable text)'} ([source]({event['source_url'] or f['url']})).")
        if c:
            cases += [f"- Candidate cutoff: {c['cutoff_timestamp']}, commit `{c['commit_sha']}`; state evidence: {c['historical_state_confidence']}.",
                      f"- Explicit earlier requirements: {c['context_preview'] or '(no verified dated requirement text)' }",
                      f"- Later human feedback: {c['future_preview']} ([source]({c['future_source_url']})).",
                      f"- Potential implicit intent: {c['future_requirement_candidates'][0]['category']} (heuristic; inferability={c['contextual_inferability']}; relevance={c['action_relevance']}).",
                      f"- Later change evidence: verified={c['later_revision_sha'] or 'none'}; possible later-review commit={c['possible_later_revision_sha'] or 'none'} (causal timing unverified).",
                      f"- Cutoff state: recoverable by commit SHA; exact pre-review visibility may be uncertain."]
        else:
            cases += ["- Candidate cutoff: none supported by collected evidence.",
                      "- Explicit earlier requirements and later feedback: insufficient verified evidence.",
                      "- Potential implicit intent: none supported; cutoff code state unavailable."]
        cases += [f"- Provisional suitability: {f['provisional_label']}; reasons: {', '.join(f['reason_codes']) or 'all screening conditions passed' }.", ""]
    (report_dir / "case_studies.md").write_text("\n".join(cases))
