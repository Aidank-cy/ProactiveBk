import base64
import json

from repo_discovery.aggregate_statistics import cohort_flags, export, search_coverage
from repo_discovery.discover_repositories import search_query, split_partition
from repo_discovery.filter_repositories import count_issues_and_prs, load_osi_license_ids, verify_licenses
from repo_discovery.store import Store


CFG = {"created_start": "2024-11-01", "created_end": "2026-11-01", "stars_min": 1000, "pull_requests_min_inclusive": 500, "issues_min_inclusive": 500, "forks_min_inclusive": 500, "graphql_batch_size": 50}


def repo(repo_id=1, forks=501):
    return {"id": repo_id, "node_id": f"node-{repo_id}", "full_name": f"a/b{repo_id}", "html_url": f"https://github.com/a/b{repo_id}", "created_at": "2025-11-01T00:00:00Z", "stargazers_count": 1000, "forks_count": forks, "size": 10, "language": "Python", "archived": False, "fork": False, "default_branch": "main"}


def test_partition_nonoverlap():
    assert split_partition("2024-01-01", "2024-01-04", 1000, 1001) == [("2024-01-01", "2024-01-02", 1000, 1001), ("2024-01-03", "2024-01-04", 1000, 1001)]
    assert split_partition("2024-01-01", "2024-01-01", 1000, 1001) == [("2024-01-01", "2024-01-01", 1000, 1000), ("2024-01-01", "2024-01-01", 1001, 1001)]


def test_cohorts():
    assert cohort_flags("2025-11-01T00:00:00Z")["creation_cohort"] == "0-1 years"
    assert cohort_flags("2025-10-31T23:59:59Z")["creation_cohort"] == "1-2 years"


def test_coverage_detects_missing_child(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    root = search_query(CFG["created_start"], CFG["created_end"], CFG["stars_min"], 1_000_000_000)
    store.partition(root, CFG["created_start"], CFG["created_end"], CFG["stars_min"], 1_000_000_000, 2000, False, "split")
    assert len(search_coverage(store, CFG)) == 2


def test_thresholds_and_order(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.add_repos([repo(1), repo(2, forks=500), repo(3, forks=499)])
    store.update(1, pr_count=501, issue_count=501, license_status="verified", license_spdx="MIT")
    store.update(2, pr_count=501, issue_count=501, license_status="verified", license_spdx="MIT")
    store.update(3, pr_count=501, issue_count=501, license_status="verified", license_spdx="MIT")
    summary, qualified, pending = export(store, CFG, tmp_path, limited=True)
    assert qualified["repository_id"].tolist() == [1, 2]
    assert len(pending) == 0
    assert summary["stages"][3]["verified_count"] == 2
    assert summary["windows"] == {"last_1_year": 2, "last_2_years": 2, "last_5_years": None}


def test_pr_issues_and_forks_exactly_500_included(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.add_repos([repo(forks=500)])
    store.update(1, pr_count=500, issue_count=500, license_status="verified", license_spdx="MIT")
    summary, qualified, pending = export(store, CFG, tmp_path, limited=True)
    assert len(qualified) == 1 and len(pending) == 0
    assert summary["excluded_count"] == 0


def test_unverified_license_stays_in_processing_but_out_of_public_list(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.add_repos([repo(1), repo(2)])
    store.update(1, pr_count=501, issue_count=501, license_status="verified", license_spdx="MIT")
    store.update(2, pr_count=501, issue_count=501, license_status="unrecognized", license_spdx="NOASSERTION")
    summary, qualified, pending = export(store, CFG, tmp_path, limited=True)
    import pandas as pd
    processing = pd.read_csv(tmp_path / "results/processing_candidates.csv")
    restricted = pd.read_csv(tmp_path / "results/restricted/repositories.csv")
    assert qualified["repository_id"].tolist() == [1]
    assert restricted["repository_id"].tolist() == [2]
    assert len(processing) == 2
    assert processing.loc[processing.repository_id.eq(2), "publication_gate"].item() == "written_permission_or_license_verification_required"
    assert summary["license_unverified_restricted_count"] == 1
    assert len(pending) == 1


def test_graphql_issues_separate_from_prs(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.add_repos([repo()])
    class Client:
        def graphql(self, query):
            assert "pullRequests" in query and "issues" in query
            return {"r0": {"pullRequests": {"totalCount": 602}, "issues": {"totalCount": 701}}}
    count_issues_and_prs(Client(), store, CFG)
    row = next(store.rows())
    assert (row["pr_count"], row["issue_count"]) == (602, 701)


def test_osi_license_check(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.add_repos([repo()])
    store.update(1, pr_count=501, issue_count=501)
    license_data = {"licenses": [{"licenseId": "MIT", "isOsiApproved": True}, {"licenseId": "Foo", "isOsiApproved": False}]}
    encoded = base64.b64encode(json.dumps(license_data).encode()).decode()
    class Client:
        def get(self, path):
            if "spdx" in path:
                return {"encoding": "base64", "sha": "abc", "content": encoded}, {}
            return {"license": {"spdx_id": "MIT", "name": "MIT License", "url": "https://api.github.com/licenses/mit"}}, {}
    ids, sha = load_osi_license_ids(Client(), tmp_path)
    assert ids == {"MIT"} and sha == "abc"
    verify_licenses(Client(), store, CFG, tmp_path)
    assert next(store.rows())["license_status"] == "verified"
