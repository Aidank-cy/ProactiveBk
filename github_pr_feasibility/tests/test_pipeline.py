"""Synthetic fixtures test research-critical sampling and chronology invariants."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pr_feasibility.analysis import extract
from pr_feasibility.collect import normalize_events
from pr_feasibility.discovery import sample_prs
from pr_feasibility.github_client import GitHubClient
from pr_feasibility.report import build_statistics, write_reports


CFG = {"seed": 42, "random_prs_per_repository": 10, "enriched_prs_per_repository": 10,
       "max_cutoffs_per_pr": 3}


def fixture(with_timeline=True):
    pr = {"number": 1, "html_url": "https://github.com/o/r/pull/1", "created_at": "2024-01-01T00:00:00Z",
          "merged_at": "2024-01-05T00:00:00Z", "title": "Add future secret constraint", "body": "future secret body",
          "user": {"login": "author", "type": "User"}, "changed_files": 1, "additions": 3, "deletions": 1,
          "merge_commit_sha": "merge", "merged_by": {"login": "maintainer", "type": "User"}}
    return {"repository": "o/r", "pull": pr, "issue_comments": [
        {"id": 10, "created_at": "2024-01-01T01:00:00Z", "updated_at": "2024-01-01T01:00:00Z",
         "user": {"login": "maintainer", "type": "User"}, "body": "Please support empty input in parser", "html_url": "https://github.com/o/r/issues/1#issuecomment-10"}],
        "reviews": [{"id": 20, "submitted_at": "2024-01-03T00:00:00Z", "user": {"login": "reviewer", "type": "User"},
                     "body": "Please also handle empty input in parser when null", "html_url": "https://github.com/o/r/pull/1#pullrequestreview-20",
                     "commit_id": "initial", "state": "CHANGES_REQUESTED"}],
        "review_comments": [], "commits": [{"sha": "initial"}, {"sha": "revision"}],
        "timeline": ([{"id": 30, "event": "committed", "created_at": "2024-01-04T00:00:00Z",
                       "sha": "revision", "actor": {"login": "author", "type": "User"}, "url": "https://api.github.com/e/30"}]
                     if with_timeline else []), "linked_issues": [], "files": [], "commit_details": {}}


def test_sampling_keeps_random_baseline_and_no_duplicates():
    items = [{"number": n, "html_url": f"https://github.com/o/r/pull/{n}", "comments": n} for n in range(1, 51)]
    first, problem = sample_prs(items, CFG, "o/r")
    second, _ = sample_prs(items, CFG, "o/r")
    assert not problem and first == second
    assert len({r["number"] for r in first}) == 20
    assert all(r["selection_probability"] == 0.2 for r in first if r["sampling_group"] == "random")
    assert all(r["selection_probability"] is None for r in first if r["sampling_group"] == "interaction_enriched")


def test_cutoff_excludes_current_pr_body_and_observes_actual_revision():
    data = fixture()
    events = normalize_events(data)
    features, cutoffs, _ = extract(data, events, CFG)
    assert features["feedback_to_revision_sequences"] == 1
    assert cutoffs[0]["commit_sha"] == "initial"
    assert cutoffs[0]["later_revision_sha"] == "revision"
    assert "future secret" not in cutoffs[0]["context_preview"]
    assert all("future secret" not in e["content"] for e in events if e["event_type"] == "pr_opened")


def test_commit_author_date_cannot_prove_revision():
    data = fixture(with_timeline=False)
    data["commits"][1]["commit"] = {"author": {"date": "2024-01-04T00:00:00Z"}}
    features, cutoffs, _ = extract(data, normalize_events(data), CFG)
    assert features["feedback_to_revision_sequences"] == 0
    assert cutoffs[0]["later_revision_sha"] is None


def test_later_review_commit_is_possible_not_verified_revision():
    data = fixture(with_timeline=False)
    data["reviews"].append({"id": 21, "submitted_at": "2024-01-04T00:00:00Z",
                            "user": {"login": "reviewer", "type": "User"}, "body": "Looks good now",
                            "html_url": "https://github.com/o/r/pull/1#pullrequestreview-21",
                            "commit_id": "revision", "state": "APPROVED"})
    features, cutoffs, _ = extract(data, normalize_events(data), CFG)
    assert features["feedback_to_revision_sequences"] == 0
    assert features["possible_feedback_to_revision_sequences"] == 1
    assert cutoffs[0]["possible_later_revision_sha"] == "revision"


def test_client_cache_resumes_without_network(tmp_path):
    client = GitHubClient("synthetic-token", tmp_path)
    class Response:
        status_code = 200
        headers = {}
        def json(self):
            return {"value": 1}
    calls = []
    def fake_get(*args, **kwargs):
        calls.append(args)
        return Response()
    client.session.get = fake_get
    assert client.get("/test")[0] == {"value": 1}
    assert client.get("/test")[1] is True
    assert len(calls) == 1


def test_synthetic_end_to_end_report_has_denominators_and_real_fixture_links(tmp_path):
    data = fixture()
    events = normalize_events(data)
    features, cutoffs, intents = extract(data, events, CFG)
    raw = tmp_path / "data" / "raw" / "o" / "r"
    raw.mkdir(parents=True)
    (raw / "1.json").write_text(json.dumps(data))
    processed = tmp_path / "data" / "processed" / "events" / "o" / "r"
    processed.mkdir(parents=True)
    (processed / "1.json").write_text(json.dumps(events))
    repos = [{"full_name": "o/r", "selected": True, "stars": 500,
              "forks": 50, "recent_merged_prs": 1}]
    sampled = [{"repository": "o/r", "number": 1, "sampling_group": "random"}]
    stats = build_statistics(repos, sampled, [features], cutoffs, {})
    write_reports(tmp_path / "reports", stats, repos, sampled, [features], cutoffs,
                  tmp_path / "data" / "raw")
    assert stats["random_baseline"]["candidate_cutoff"]["denominator"] == 1
    assert "github.com/o/r/pull/1" in (tmp_path / "reports" / "case_studies.md").read_text()
    assert "Wilson 95%" in (tmp_path / "reports" / "feasibility_report.md").read_text()
