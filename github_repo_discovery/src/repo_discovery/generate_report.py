from datetime import datetime, timezone
from pathlib import Path


def generate_report(summary, qualified, pending, root):
    root = Path(root)
    results = root / "results"
    lines = [
        "# GitHub repository discovery report", "",
        f"Generated: {summary['generated_at']}", "",
        "## Scope and definition", "",
        f"Public repositories created {summary['created_start']} through {summary['created_end']} inclusive (UTC), with stars ≥1,000, all-state pull requests ≥500, issues ≥500 (issues exclude PRs), forks ≥500, and a GitHub-detected SPDX license whose SPDX list record has `isOsiApproved=true`. Language, topic, domain, archive status and fork status are descriptive only. Stars, issue/PR counts, forks and license are observed when collected, not as of 2026-11-01.", "",
        "## Completeness", "",
        f"Search coverage complete: **{summary['discovery_coverage_complete']}**. Entire study complete and verified: **{summary['complete_and_verified']}**. Limited mode: **{summary['limited_mode']}**.", "",
        f"Search candidates observed so far: **{summary['discovered_candidates']}**. Verified qualifying: **{summary['verified_qualifying_count']}**. Pending: **{summary['pending_count']}**. Excluded: **{summary['excluded_count']}**. A partial count is a verified lower bound, never a global total.", "",
        f"There are **{summary['research_processing_candidates']}** numeric-threshold candidates for future research processing: **{summary['license_verified_count']}** with OSI-approved license detection and **{summary['license_unverified_restricted_count']}** with unverified license status. The latter group is held locally and must not be included in a public benchmark release without a verified license or written authorization. This is a publication gate, not a conclusion that internal code copying or modification is legally permitted.", "",
        "## Stage funnel", "", "| Stage | Verified passing | Pending checks |", "|---|---:|---:|",
    ]
    for stage in summary["stages"]:
        lines.append(f"| {stage['stage']} | {stage['verified_count']} | {stage['pending_count']} |")
    lines += ["", "Machine-readable funnel: [stage_counts.csv](../results/stage_counts.csv).", "", "## Creation-date counts", "",
              f"- Last 1 year (2025-11-01 through 2026-11-01): **{summary['windows']['last_1_year']}** verified.",
              f"- Last 2 years (2024-11-01 through 2026-11-01): **{summary['windows']['last_2_years']}** verified.",
              "- Last 5 years: **not measured** in the revised two-year scope.", "",
              f"Non-overlapping cohorts: 0–1 years {summary['cohorts']['0-1 years']}; 1–2 years {summary['cohorts']['1-2 years']}. Their sum equals the two-year verified count.", "",
              "Year and month CSVs include zero-count periods: [yearly_counts.csv](../results/yearly_counts.csv), [monthly_counts.csv](../results/monthly_counts.csv).", ""]
    for name in ("yearly", "monthly"):
        lines += [f"### {name.title()}", "", "```csv", (results / f"{name}_counts.csv").read_text().strip(), "```", ""]
    lines += ["## Qualified repositories", "", "Full table: [qualified_repositories.csv](../results/qualified_repositories.csv).", "", "| Repository | Created UTC | Stars | Issues | PRs | Forks | SPDX license |", "|---|---:|---:|---:|---:|---:|---|"]
    for _, r in qualified.iterrows():
        lines.append(f"| [{r['full_name']}]({r['html_url']}) | {r['created_at'][:10]} | {int(r['stars'])} | {int(r['total_issues'])} | {int(r['total_pull_requests'])} | {int(r['forks'])} | {r['license_spdx']} |")
    lines += ["", "## Descriptive statistics", ""]
    if len(qualified):
        for col in ("stars", "forks", "total_issues", "total_pull_requests"):
            values = qualified[col].astype(float)
            lines.append(f"- {col}: median {values.median():.0f}, min {values.min():.0f}, max {values.max():.0f}, p90 {values.quantile(.9):.0f}.")
        ages = qualified["created_at"].map(lambda x: (datetime.now(timezone.utc) - datetime.fromisoformat(x.replace("Z", "+00:00"))).total_seconds() / 86400 / 365.25)
        lines.append(f"- Age at report generation: median {ages.median():.2f} years, min {ages.min():.2f}, max {ages.max():.2f}, p90 {ages.quantile(.9):.2f}.")
        lines.append("- Largest PR counts: " + ", ".join(f"{r['full_name']} ({int(r['total_pull_requests'])})" for _, r in qualified.nlargest(5, "total_pull_requests").iterrows()) + ".")
    lines += ["", "## Audit and limitations", "",
              f"- Search partitions unresolved: {len(summary['incomplete_partitions'])}.",
              f"- Candidate repositories with unknown PR count: {summary['unknown_pr_count']}.",
              f"- Candidate repositories with unknown issue count: {summary['unknown_issue_count']}.",
              f"- Repositories passing numeric thresholds with unknown license status: {summary['unknown_license']}.",
              f"- Pending repositories: {len(pending)}. Repository-level pending records are held locally and omitted from this public report.", "",
              "A missing GitHub-detected license or an unrecognized SPDX identifier remains pending because detection alone cannot rule out a valid license. The SPDX license list blob SHA is saved in the summary. GitHub Search is a live index, not an atomic snapshot; search movement and delayed indexing can affect full enumeration. The REST and GraphQL HTTP cache and SQLite checkpoint support resumption.", "",
              "## Stage timing", "", "Wall-clock timings for this invocation: " + ", ".join(f"{k}: {v:.1f}s" for k, v in summary.get("stage_seconds", {}).items()) + ".", ""]
    output = root / "reports/repository_discovery_report.md"
    output.parent.mkdir(exist_ok=True)
    output.write_text("\n".join(lines))
