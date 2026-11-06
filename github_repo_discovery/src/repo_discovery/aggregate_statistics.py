import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from .discover_repositories import search_query, split_partition


def search_coverage(store, cfg):
    partitions = {r[0]: r[1] for r in store.db.execute("SELECT key,status FROM partitions")}
    missing = []
    def visit(start, end, lower, upper):
        key = search_query(start, end, lower, upper)
        status = partitions.get(key)
        if status == "complete":
            return
        if status == "split":
            for child in split_partition(start, end, lower, upper):
                visit(*child)
            return
        missing.append({"query": key, "status": status or "not_started"})
    visit(cfg["created_start"], cfg["created_end"], cfg["stars_min"], 1_000_000_000)
    return missing


def cohort_flags(created):
    d = date.fromisoformat(created[:10])
    return {
        "within_1_year": int(date(2025, 11, 1) <= d <= date(2026, 11, 1)),
        "within_2_years": int(date(2024, 11, 1) <= d <= date(2026, 11, 1)),
        "creation_cohort": "0-1 years" if d >= date(2025, 11, 1) else "1-2 years",
    }


def export(store, cfg, root, limited=False):
    root = Path(root)
    results = root / "results"
    results.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for row in store.rows():
        repo = json.loads(row["data"])
        records.append({
            "repository_id": row["id"], "full_name": repo["full_name"], "html_url": repo["html_url"],
            "created_at": repo["created_at"], "stars": repo["stargazers_count"], "forks": repo["forks_count"],
            "repository_size_kb": repo["size"], "total_pull_requests": row["pr_count"],
            "total_issues": row["issue_count"], "license_spdx": row["license_spdx"],
            "license_status": row["license_status"], "license_name": row["license_name"],
            "license_source_url": row["license_source_url"], "language": repo.get("language"),
            "archived": repo["archived"], "fork": repo["fork"], "default_branch": repo["default_branch"],
            "collection_timestamp": now, "error": row["error"], **cohort_flags(repo["created_at"]),
        })
    columns = ["repository_id", "full_name", "html_url", "created_at", "stars", "forks", "repository_size_kb", "total_pull_requests", "total_issues", "license_spdx", "license_status", "license_name", "license_source_url", "language", "archived", "fork", "default_branch", "collection_timestamp", "error", "within_1_year", "within_2_years", "creation_cohort"]
    frame = pd.DataFrame(records, columns=columns).sort_values(["created_at", "repository_id"])
    pr_ok = frame["total_pull_requests"].ge(cfg["pull_requests_min_inclusive"])
    issues_ok = frame["total_issues"].ge(cfg["issues_min_inclusive"])
    fork_ok = frame["forks"].ge(cfg["forks_min_inclusive"])
    license_ok = frame["license_status"].eq("verified")
    qualified = frame[pr_ok & issues_ok & fork_ok & license_ok].copy()
    excluded = frame[(frame["total_pull_requests"].notna() & ~pr_ok) | (frame["total_issues"].notna() & ~issues_ok) | ~fork_ok | (pr_ok & issues_ok & fork_ok & frame["license_status"].eq("non_osi"))].copy()
    pending = frame.drop(qualified.index.union(excluded.index)).copy()
    restricted = frame[pr_ok & issues_ok & fork_ok & frame["license_status"].isin(["missing", "unrecognized"])].copy()
    processing = pd.concat([qualified.assign(processing_track="license_verified", authorization_status="osi_license_detected", publication_gate="check_license_terms"), restricted.assign(processing_track="license_unverified", authorization_status="not_verified", publication_gate="written_permission_or_license_verification_required")]).sort_values(["created_at", "repository_id"])
    processing["authorization_evidence_url"] = ""
    processing["research_processing_plan"] = "same_repository_research_pipeline"
    for name, data in (("all_candidates", frame), ("qualified_repositories", qualified), ("excluded_repositories", excluded), ("pending_repositories", pending)):
        data.to_csv(results / f"{name}.csv", index=False)
    restricted_dir = results / "restricted"
    restricted_dir.mkdir(exist_ok=True)
    restricted.to_csv(restricted_dir / "repositories.csv", index=False)
    processing.to_csv(results / "processing_candidates.csv", index=False)
    years = range(int(cfg["created_start"][:4]), int(cfg["created_end"][:4]) + 1)
    year_counts = qualified.groupby(qualified["created_at"].str[:4]).size().to_dict()
    month_counts = qualified.groupby(qualified["created_at"].str[:7]).size().to_dict()
    yearly = pd.DataFrame([{"year": str(y), "count": int(year_counts.get(str(y), 0))} for y in years])
    monthly = pd.DataFrame([{"month": str(m), "count": int(month_counts.get(str(m), 0))} for m in pd.period_range(cfg["created_start"][:7], cfg["created_end"][:7], freq="M")])
    yearly.to_csv(results / "yearly_counts.csv", index=False)
    monthly.to_csv(results / "monthly_counts.csv", index=False)
    assert frame["repository_id"].is_unique and qualified["repository_id"].is_unique
    assert qualified["repository_id"].is_unique and restricted["repository_id"].is_unique
    assert set(qualified["repository_id"]).isdisjoint(set(restricted["repository_id"]))
    assert len(processing) == len(qualified) + len(restricted)
    assert processing.loc[processing["processing_track"].eq("license_unverified"), "publication_gate"].eq("written_permission_or_license_verification_required").all()
    assert processing.loc[processing["processing_track"].eq("license_unverified"), "authorization_status"].eq("not_verified").all()
    assert qualified["stars"].ge(cfg["stars_min"]).all()
    assert qualified["total_pull_requests"].ge(cfg["pull_requests_min_inclusive"]).all()
    assert qualified["total_issues"].ge(cfg["issues_min_inclusive"]).all()
    assert qualified["forks"].ge(cfg["forks_min_inclusive"]).all()
    assert qualified["license_status"].eq("verified").all()
    assert qualified[["created_at", "repository_id"]].apply(tuple, axis=1).tolist() == sorted(qualified[["created_at", "repository_id"]].apply(tuple, axis=1).tolist())
    assert int(yearly["count"].sum()) == int(monthly["count"].sum()) == len(qualified)
    missing = search_coverage(store, cfg)
    windows = {"last_1_year": int(qualified["within_1_year"].sum()), "last_2_years": int(qualified["within_2_years"].sum()), "last_5_years": None}
    cohorts = {"0-1 years": windows["last_1_year"], "1-2 years": len(qualified) - windows["last_1_year"]}
    assert sum(cohorts.values()) == windows["last_2_years"] == len(qualified)
    stages = [
        {"stage": "created_in_window_and_stars_at_least_1000", "verified_count": len(frame), "pending_count": len(missing)},
        {"stage": "pull_requests_at_least_500", "verified_count": int(pr_ok.sum()), "pending_count": int(frame["total_pull_requests"].isna().sum())},
        {"stage": "also_issues_at_least_500", "verified_count": int((pr_ok & issues_ok).sum()), "pending_count": int((pr_ok & frame["total_issues"].isna()).sum())},
        {"stage": "also_forks_at_least_500", "verified_count": int((pr_ok & issues_ok & fork_ok).sum()), "pending_count": int((fork_ok & (frame["total_pull_requests"].isna() | frame["total_issues"].isna())).sum())},
        {"stage": "also_osi_approved_license", "verified_count": len(qualified), "pending_count": len(pending)},
    ]
    pd.DataFrame(stages).to_csv(results / "stage_counts.csv", index=False)
    summary = {
        "generated_at": now, "created_start": cfg["created_start"], "created_end": cfg["created_end"],
        "thresholds": {"stars_min_inclusive": cfg["stars_min"], "pull_requests_min_inclusive": cfg["pull_requests_min_inclusive"], "issues_min_inclusive": cfg["issues_min_inclusive"], "forks_min_inclusive": cfg["forks_min_inclusive"], "license": "SPDX isOsiApproved=true"},
        "limited_mode": limited, "complete_and_verified": not limited and not missing and pending.empty,
        "discovery_coverage_complete": not missing, "incomplete_partitions": missing,
        "discovered_candidates": len(frame), "stages": stages, "verified_qualifying_count": len(qualified),
        "pending_count": len(pending), "excluded_count": len(excluded), "windows": windows, "cohorts": cohorts,
        "research_processing_candidates": len(processing), "license_verified_count": len(qualified),
        "license_unverified_restricted_count": len(restricted),
        "restricted_license_status_counts": {str(k): int(v) for k, v in restricted["license_status"].value_counts().items()},
        "unknown_pr_count": int(frame["total_pull_requests"].isna().sum()),
        "unknown_issue_count": int(frame["total_issues"].isna().sum()),
        "unknown_license": int((pr_ok & issues_ok & fork_ok & ~frame["license_status"].isin(["verified", "non_osi"])).sum()),
        "search_partitions": int(store.db.execute("SELECT COUNT(*) FROM partitions").fetchone()[0]),
    }
    (results / "summary_statistics.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return summary, qualified, pending
