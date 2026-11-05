"""Download all evidence used by the pilot; API responses are saved verbatim."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

LOG = logging.getLogger(__name__)


def collect_pr(client, repository: str, number: int, raw_dir: Path, cfg: dict):
    owner, repo = repository.split("/", 1)
    root = f"/repos/{owner}/{repo}"
    target = Path(raw_dir) / owner / repo / f"{number}.json"
    if target.exists():
        return json.loads(target.read_text())
    pr, _ = client.get(f"{root}/pulls/{number}")
    issue, _ = client.get(f"{root}/issues/{number}")
    data = {"repository": repository, "number": number, "pull": pr, "issue": issue,
            "issue_comments": list(client.pages(f"{root}/issues/{number}/comments")),
            "reviews": list(client.pages(f"{root}/pulls/{number}/reviews")),
            "review_comments": list(client.pages(f"{root}/pulls/{number}/comments")),
            "commits": list(client.pages(f"{root}/pulls/{number}/commits")),
            "files": list(client.pages(f"{root}/pulls/{number}/files")),
            "timeline": list(client.pages(f"{root}/issues/{number}/timeline")),
            "commit_details": {}, "linked_issues": [], "evidence_limits": {}}
    data["evidence_limits"] = {
        "commits_complete": len(data["commits"]) >= int(pr.get("commits") or 0),
        "files_complete": len(data["files"]) >= int(pr.get("changed_files") or 0),
        "reported_commits": pr.get("commits"), "reported_changed_files": pr.get("changed_files")}
    for commit in data["commits"]:
        sha = commit["sha"]
        detail, _ = client.get(f"{root}/commits/{sha}")
        data["commit_details"][sha] = detail
    linked = set()
    # Explicit closing keywords in the current body are recorded with temporal uncertainty.
    for match in re.finditer(r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b", pr.get("body") or ""):
        if int(match.group(1)) > 0:
            linked.add(int(match.group(1)))
    for event in data["timeline"]:
        if event.get("event") == "cross-referenced":
            source = (event.get("source") or {}).get("issue") or {}
            if source.get("repository_url", "").endswith("/" + repository) and source.get("number"):
                linked.add(int(source["number"]))
    linked.discard(number)
    for linked_number in sorted(linked)[:cfg["max_linked_issues_per_pr"]]:
        try:
            linked_issue, _ = client.get(f"{root}/issues/{linked_number}")
            comments = list(client.pages(f"{root}/issues/{linked_number}/comments"))
            data["linked_issues"].append({"issue": linked_issue, "comments": comments,
                                          "link_evidence": "current PR body closing reference or timeline cross-reference",
                                          "link_temporally_verified": False})
        except Exception as exc:
            LOG.warning("linked_issue_unavailable repository=%s pr=%s issue=%s error=%s",
                        repository, number, linked_number, exc)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False))
    temporary.replace(target)
    return data


def actor_type(user: dict | None) -> str:
    if not user:
        return "unknown"
    return "bot" if user.get("type") == "Bot" or (user.get("login") or "").endswith("[bot]") else "human"


def normalize_events(data: dict):
    """Normalize observed events; never infer a push time from commit author dates."""
    pr = data["pull"]
    events = []

    def add(kind, timestamp, user, content, source, source_id, *, sha=None, status="verified", extra=None):
        if not timestamp:
            return
        events.append({"event_id": f"{kind}:{source_id}", "event_type": kind,
                       "timestamp": timestamp, "actor": (user or {}).get("login"),
                       "actor_type": actor_type(user), "content": content or "",
                       "commit_sha": sha, "source_url": source, "source_id": str(source_id),
                       "evidence_status": status, **(extra or {})})

    add("pr_opened", pr["created_at"], pr.get("user"), "", pr["html_url"],
        pr["number"], extra={"title_current_only": pr.get("title") or "",
                             "description_current_only": pr.get("body") or ""})
    for item in data["issue_comments"]:
        add("issue_comment", item["created_at"], item.get("user"), item.get("body"), item["html_url"], item["id"],
            status="uncertain" if item.get("updated_at", item["created_at"]) > item["created_at"] else "verified",
            extra={"updated_at": item.get("updated_at"), "author_association": item.get("author_association")})
    for item in data["reviews"]:
        add("review", item.get("submitted_at"), item.get("user"), item.get("body"), item.get("html_url"),
            item["id"], sha=item.get("commit_id"), extra={"review_state": item.get("state"),
            "author_association": item.get("author_association")})
    for item in data["review_comments"]:
        add("review_comment", item["created_at"], item.get("user"), item.get("body"), item.get("html_url"),
            item["id"], sha=item.get("commit_id"),
            status="uncertain" if item.get("updated_at", item["created_at"]) > item["created_at"] else "verified",
            extra={"original_commit_sha": item.get("original_commit_id"),
            "reply_to_id": item.get("in_reply_to_id"), "updated_at": item.get("updated_at"),
            "author_association": item.get("author_association"), "path": item.get("path")})
    for item in data["timeline"]:
        kind = item.get("event")
        if kind in ("committed", "synchronize", "head_ref_force_pushed", "head_ref_restored",
                    "head_ref_deleted", "renamed", "connected", "disconnected", "cross-referenced"):
            add("timeline_" + kind, item.get("created_at"), item.get("actor"),
                item.get("commit_url") or item.get("url") or kind, item.get("url"),
                item.get("id", item.get("sha", kind)), sha=item.get("sha") or item.get("commit_id"),
                extra={"raw_event_type": kind})
    for item in data["linked_issues"]:
        issue = item["issue"]
        add("linked_issue_opened", issue["created_at"], issue.get("user"), issue.get("title"),
            issue["html_url"], issue["id"], status="uncertain",
            extra={"description_current_only": issue.get("body") or ""})
        for comment in item["comments"]:
            add("linked_issue_comment", comment["created_at"], comment.get("user"), comment.get("body"),
                comment["html_url"], comment["id"], status="uncertain")
    add("pr_merged", pr.get("merged_at"), pr.get("merged_by"), "", pr["html_url"],
        f"{pr['number']}:merge", sha=pr.get("merge_commit_sha"))
    events.sort(key=lambda e: (e["timestamp"], e["event_id"]))
    return events
