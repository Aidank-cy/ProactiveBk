import json
import heapq
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .github_client import GitHubClient

LOG = logging.getLogger(__name__)
REF = re.compile(r"(?<![\w/.-])(?:(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+))?#(?P<number>\d+)")
LOCAL = threading.local()


def _save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False))
    temp.replace(path)


def _client(root, cfg):
    if not hasattr(LOCAL, "client"):
        LOCAL.client = GitHubClient(root / ".cache/http", cfg["request_timeout_seconds"], cfg["max_retries"])
    return LOCAL.client


def _closing_issues(client, repo, number, max_pages=3):
    owner, name = repo.split("/", 1)
    nodes, cursor, truncated = [], None, False
    for _ in range(max_pages):
        after = f", after: {json.dumps(cursor)}" if cursor else ""
        query = f'query {{ repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{ pullRequest(number: {number}) {{ closingIssuesReferences(first: 50{after}) {{ totalCount pageInfo {{ hasNextPage endCursor }} nodes {{ id number title url repository {{ nameWithOwner }} }} }} }} }} }}'
        data = client.graphql(query)
        conn = ((data.get("repository") or {}).get("pullRequest") or {}).get("closingIssuesReferences") or {}
        nodes.extend(conn.get("nodes") or [])
        page = conn.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            return {"nodes": nodes, "total_count": conn.get("totalCount"), "truncated": False}
        cursor = page.get("endCursor")
        if not cursor:
            break
    truncated = True
    return {"nodes": nodes, "total_count": conn.get("totalCount"), "truncated": truncated}


def collect_pr_bundle(root, cfg, repo, number):
    path = root / "data/raw" / repo.replace("/", "__") / "prs" / f"{number}.json"
    bundle = json.loads(path.read_text()) if path.exists() else {"repo": repo, "number": int(number), "collected_at": datetime.now(timezone.utc).isoformat(), "data": {}, "coverage": {}, "errors": {}}
    client = _client(root, cfg)
    endpoints = {
        "pull": (f"repos/{repo}/pulls/{number}", None),
        "issue_resource": (f"repos/{repo}/issues/{number}", None),
        "issue_comments": (f"repos/{repo}/issues/{number}/comments", cfg["max_pages_per_endpoint"]),
        "reviews": (f"repos/{repo}/pulls/{number}/reviews", cfg["max_pages_per_endpoint"]),
        "review_comments": (f"repos/{repo}/pulls/{number}/comments", cfg["max_pages_per_endpoint"]),
        "commits": (f"repos/{repo}/pulls/{number}/commits", cfg["max_pages_per_endpoint"]),
        "files": (f"repos/{repo}/pulls/{number}/files", min(cfg["max_pages_per_endpoint"], (cfg["max_files_per_pr"] + 99) // 100)),
        "timeline": (f"repos/{repo}/issues/{number}/timeline", cfg["max_pages_per_endpoint"]),
    }
    for name, (endpoint, pages) in endpoints.items():
        if name in bundle["data"]:
            continue
        try:
            if pages is None:
                data, _ = client.get(endpoint)
                coverage = {"pages": 1, "truncated": False}
            else:
                data, truncated, page_count = client.paginate(endpoint, max_pages=pages)
                coverage = {"pages": page_count, "truncated": truncated}
            bundle["data"][name] = data
            bundle["coverage"][name] = coverage
            bundle["errors"].pop(name, None)
        except Exception as exc:
            bundle["errors"][name] = str(exc)
            LOG.error("pr_endpoint_failed repo=%s pr=%s endpoint=%s error=%s", repo, number, name, exc)
        _save(path, bundle)
    if "closing_issues" not in bundle["data"]:
        try:
            bundle["data"]["closing_issues"] = _closing_issues(client, repo, number)
            bundle["coverage"]["closing_issues"] = {"pages": None, "truncated": bundle["data"]["closing_issues"]["truncated"]}
            bundle["errors"].pop("closing_issues", None)
        except Exception as exc:
            bundle["errors"]["closing_issues"] = str(exc)
            LOG.error("closing_issues_failed repo=%s pr=%s error=%s", repo, number, exc)
        _save(path, bundle)
    return bundle


def _references(text, default_repo):
    found = []
    for match in REF.finditer(text or ""):
        repo = f"{match.group('owner')}/{match.group('repo')}" if match.group("owner") else default_repo
        found.append((repo, int(match.group("number"))))
    return found


def _timeline_sources(events, default_repo):
    found = []
    for event in events or []:
        if event.get("event") != "cross-referenced":
            continue
        source = (event.get("source") or {}).get("issue") or {}
        url = source.get("html_url") or ""
        parts = url.removeprefix("https://github.com/").split("/")
        if len(parts) >= 4 and parts[2] in ("issues", "pull") and parts[3].isdigit():
            found.append((f"{parts[0]}/{parts[1]}", int(parts[3]), "PULL_REQUEST" if parts[2] == "pull" or source.get("pull_request") else "ISSUE", event))
    return found


def _issue_bundle(root, cfg, repo, number):
    path = root / "data/raw" / repo.replace("/", "__") / "neighbors" / f"{number}.json"
    bundle = json.loads(path.read_text()) if path.exists() else {"repo": repo, "number": int(number), "data": {}, "coverage": {}, "errors": {}}
    client = _client(root, cfg)
    for name, endpoint, pages in (("issue", f"repos/{repo}/issues/{number}", None), ("comments", f"repos/{repo}/issues/{number}/comments", cfg["max_pages_per_endpoint"]), ("timeline", f"repos/{repo}/issues/{number}/timeline", cfg["max_pages_per_endpoint"])):
        if name == "issue" and "HTTP 404" in bundle["errors"].get("issue", ""):
            continue  # Permanent missing/deleted reference, already recorded.
        if name != "issue" and not bundle["data"].get("issue"):
            continue
        if name != "issue" and (bundle["data"].get("issue") or {}).get("pull_request"):
            continue  # Expanded PRs need identity and links; full internal history is for seeds.
        if name in bundle["data"]:
            continue
        try:
            if pages is None:
                value, _ = client.get(endpoint)
                coverage = {"pages": 1, "truncated": False}
            else:
                value, truncated, page_count = client.paginate(endpoint, max_pages=pages)
                coverage = {"pages": page_count, "truncated": truncated}
            bundle["data"][name] = value
            bundle["coverage"][name] = coverage
            bundle["errors"].pop(name, None)
        except Exception as exc:
            bundle["errors"][name] = str(exc)
        _save(path, bundle)
    return bundle


def collect_repository(root, cfg, repo, sampled):
    sample_numbers = sorted(int(x) for x in sampled.pr_number)
    bundles = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(collect_pr_bundle, root, cfg, repo, number): number for number in sample_numbers}
        for future in as_completed(futures):
            number = futures[future]
            try:
                bundles[number] = future.result()
            except Exception as exc:
                LOG.error("pr_bundle_failed repo=%s pr=%s error=%s", repo, number, exc)
            if len(bundles) % 10 == 0:
                LOG.info("seed_collection repo=%s done=%s total=%s", repo, len(bundles), len(sample_numbers))
    seeds = {(repo, n) for n in sample_numbers}
    expansion = {"repo": repo, "seed_pr_numbers": sample_numbers, "neighbors": [], "boundary_nodes": [], "truncated": False, "cap": cfg["max_expanded_issue_pr_nodes_per_repository"], "depth": cfg["expansion_depth"], "errors": []}
    queue = []
    for n, bundle in bundles.items():
        data = bundle.get("data", {})
        for issue in (data.get("closing_issues") or {}).get("nodes") or []:
            target_repo = (issue.get("repository") or {}).get("nameWithOwner") or repo
            queue.append((target_repo, int(issue["number"]), "ISSUE", "closing_issue_metadata", n))
        for source_repo, source_n, source_type, event in _timeline_sources(data.get("timeline"), repo):
            queue.append((source_repo, source_n, source_type, "timeline_cross_reference", n))
        pull = data.get("pull") or {}
        # Current text can have been edited. These are candidate neighbors only.
        for target_repo, target_n in _references((pull.get("title") or "") + "\n" + (pull.get("body") or ""), repo)[:cfg["max_neighbors_per_seed"]]:
            queue.append((target_repo, target_n, "UNKNOWN", "current_text_reference", n))
    priority = {"closing_issue_metadata": 0, "timeline_cross_reference": 1, "same_issue_cross_reference": 1, "current_text_reference": 2}
    heap = [(priority.get(reason, 3), target_repo, target_n, target_type, reason, seed_n) for target_repo, target_n, target_type, reason, seed_n in queue]
    heapq.heapify(heap)
    seen = set()
    while heap:
        _, target_repo, target_n, target_type, reason, seed_n = heapq.heappop(heap)
        key = (target_repo, target_n)
        if key in seeds or key in seen:
            continue
        seen.add(key)
        if len(expansion["neighbors"]) + len(expansion["boundary_nodes"]) >= cfg["max_expanded_issue_pr_nodes_per_repository"]:
            expansion["truncated"] = True
            expansion["unprocessed_reference_count_lower_bound"] = len(heap) + 1
            break
        if target_repo != repo:
            expansion["boundary_nodes"].append({"repo": target_repo, "number": target_n, "node_type": target_type, "source_seed_pr": seed_n, "reason": reason, "url": f"https://github.com/{target_repo}/issues/{target_n}"})
            continue
        expansion["neighbors"].append({"repo": repo, "number": target_n, "node_type": target_type, "source_seed_pr": seed_n, "reason": reason})
        neighbor = _issue_bundle(root, cfg, repo, target_n)
        if neighbor["errors"]:
            expansion["errors"].append({"number": target_n, "errors": neighbor["errors"]})
        # One hop from a linked Issue: include directly cross-referencing PRs,
        # but do not recursively expand those PRs.
        issue = (neighbor.get("data") or {}).get("issue") or {}
        if cfg["expansion_depth"] >= 1 and not issue.get("pull_request"):
            for source_repo, source_n, source_type, event in _timeline_sources((neighbor.get("data") or {}).get("timeline"), repo):
                if source_type == "PULL_REQUEST":
                    heapq.heappush(heap, (priority["same_issue_cross_reference"], source_repo, source_n, source_type, "same_issue_cross_reference", seed_n))
        _save(root / "data/processed" / repo.replace("/", "__") / "expansion.json", expansion)
    _save(root / "data/processed" / repo.replace("/", "__") / "expansion.json", expansion)
    return expansion


def collect_all(root, cfg):
    sampled = pd.read_csv(root / "results/sampled_prs.csv")
    for repo, group in sampled.groupby("repo", sort=True):
        LOG.info("collect_repository_start repo=%s seeds=%s", repo, len(group))
        collect_repository(root, cfg, repo, group)
        LOG.info("collect_repository_end repo=%s", repo)
