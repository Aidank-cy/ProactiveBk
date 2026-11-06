"""Evidence-backed graph construction from saved GitHub API bundles."""
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from collector.collect import _references, _timeline_sources

LOG = logging.getLogger(__name__)
EXPLICIT = {"ISSUE_RESOLVED_BY_PR", "ISSUE_REFERENCED_BY_PR", "ISSUE_REFERENCES_PR", "PR_REFERENCES_PR", "ISSUE_RELATES_TO_ISSUE", "PR_DEPENDS_ON_PR"}
DEPENDENCY = re.compile(r"(?i)\b(?:depends? on|blocked by|requires)\s+(?:(?:[\w.-]+/[\w.-]+)?#\d+)")


def node_id(kind, repo, number):
    return f"{kind.lower()}:{repo}#{number}"


def actor_type(user):
    if not user:
        return "unknown"
    login = user.get("login") or ""
    return "bot" if user.get("type") == "Bot" or login.endswith("[bot]") else "human"


class GraphBuilder:
    def __init__(self, root, cfg):
        self.root, self.cfg = Path(root), cfg
        self.nodes = {}
        self.edges = []
        self.edge_keys = set()
        self.timelines = {}
        self.files_by_pr = defaultdict(set)
        self.issues_by_pr = defaultdict(set)
        self.seed_ids = set()
        self.collection = {"seed_bundles_found": 0, "seed_bundles_missing": 0, "endpoint_errors": 0, "truncated_endpoints": 0, "truncated_repositories": [], "expanded_neighbor_attempts": 0, "expanded_neighbor_endpoint_errors": 0, "boundary_nodes_recorded": 0, "unresolved_expanded_neighbor_nodes": 0, "temporal_uncertainty_notes": ["Current Issue and PR descriptions may have been edited.", "Commit author/committer times do not prove push time.", "Closing issue reference creation time is not exposed by this collection."]}

    def add_node(self, kind, repo, number, **fields):
        key = node_id(kind, repo, number)
        base = {"id": key, "type": kind, "repo": repo, "number": number, "title": fields.get("title") or f"{kind.replace('_', ' ').title()} #{number}", "created_at": fields.get("created_at"), "updated_at": fields.get("updated_at"), "state": fields.get("state"), "source_url": fields.get("source_url"), "description": fields.get("description"), "description_temporal_status": fields.get("description_temporal_status", "uncertain"), "metadata": fields.get("metadata") or {}, "seed": fields.get("seed", False), "boundary": fields.get("boundary", False), "collection_timestamp": fields.get("collection_timestamp")}
        if key in self.nodes:
            existing = self.nodes[key]
            for name, value in base.items():
                if value is not None and (existing.get(name) is None or name in ("seed", "boundary") and value):
                    existing[name] = value
            existing["metadata"].update(base["metadata"])
        else:
            self.nodes[key] = base
        return key

    def add_edge(self, source, target, relation_type, evidence_type, evidence_url, evidence_event_id=None, evidence_timestamp=None, verification_status="verified", temporal_status="unknown", content=None, supporting_urls=None):
        if source not in self.nodes or target not in self.nodes:
            raise ValueError("Edge endpoint missing")
        key = (source, target, relation_type, evidence_type, str(evidence_event_id))
        if key in self.edge_keys:
            return
        self.edge_keys.add(key)
        self.edges.append({"id": f"e{len(self.edges)+1}", "source": source, "target": target, "relation_type": relation_type, "evidence_type": evidence_type, "evidence_url": evidence_url, "supporting_urls": supporting_urls or [], "evidence_event_id": evidence_event_id, "evidence_timestamp": evidence_timestamp, "confidence": verification_status, "verification_status": verification_status, "temporal_status": temporal_status, "content": content})

    def _issue_node(self, repo, issue, collected_at=None):
        kind = "PULL_REQUEST" if issue.get("pull_request") else "ISSUE"
        number = issue.get("number")
        return self.add_node(kind, repo, number, title=issue.get("title"), created_at=issue.get("created_at"), updated_at=issue.get("updated_at"), state=issue.get("state"), source_url=issue.get("html_url"), description=issue.get("body"), description_temporal_status="current_text_edited_possible", metadata={"author": (issue.get("user") or {}).get("login"), "labels": [x.get("name") for x in issue.get("labels") or []]}, collection_timestamp=collected_at)

    def _timeline_event(self, event_type, timestamp, actor, content, source_url, source_id, temporal_status="verified", commit_sha=None, actor_kind="unknown"):
        return {"event_type": event_type, "timestamp": timestamp, "actor": actor, "actor_type": actor_kind, "content": content, "source_url": source_url, "source_id": source_id, "temporal_status": temporal_status, "commit_sha": commit_sha}

    def _build_pr(self, repo, number, sample, bundle):
        data = bundle.get("data") or {}
        pull = data.get("pull") or {}
        issue_resource = data.get("issue_resource") or {}
        pr_key = self.add_node("PULL_REQUEST", repo, number, title=pull.get("title"), created_at=pull.get("created_at") or sample.get("created_at"), updated_at=pull.get("updated_at"), state="merged" if pull.get("merged_at") else pull.get("state"), source_url=pull.get("html_url") or sample.get("pr_url"), description=pull.get("body"), description_temporal_status="current_text_edited_possible", metadata={"author": (pull.get("user") or {}).get("login"), "base_sha": ((pull.get("base") or {}).get("sha")), "head_sha": ((pull.get("head") or {}).get("sha")), "merged_at": pull.get("merged_at"), "closed_at": pull.get("closed_at"), "sampling_group": sample.get("sampling_group"), "additions": pull.get("additions"), "deletions": pull.get("deletions"), "changed_files": pull.get("changed_files"), "labels": [x.get("name") for x in issue_resource.get("labels") or []], "api_errors": bundle.get("errors") or {}, "api_coverage": bundle.get("coverage") or {}}, seed=True, collection_timestamp=bundle.get("collected_at"))
        self.seed_ids.add(pr_key)
        events = [self._timeline_event("pr_opened", pull.get("created_at"), (pull.get("user") or {}).get("login"), pull.get("title"), pull.get("html_url"), pull.get("id"), actor_kind=actor_type(pull.get("user")))]
        if pull.get("merged_at"):
            events.append(self._timeline_event("pr_merged", pull["merged_at"], None, None, pull.get("html_url"), pull.get("merge_commit_sha")))
        elif pull.get("closed_at"):
            events.append(self._timeline_event("pr_closed", pull["closed_at"], None, None, pull.get("html_url"), pull.get("id")))
        for comment in data.get("issue_comments") or []:
            events.append(self._timeline_event("discussion_comment", comment.get("created_at"), (comment.get("user") or {}).get("login"), comment.get("body"), comment.get("html_url"), comment.get("id"), actor_kind=actor_type(comment.get("user"))))
        for review in data.get("reviews") or []:
            review_id = review.get("id")
            review_key = self.add_node("REVIEW", repo, f"{number}:{review_id}", title=f"Review: {review.get('state')}", created_at=review.get("submitted_at"), state=review.get("state"), source_url=review.get("html_url"), description=review.get("body"), description_temporal_status="review_body_edited_possible", metadata={"author": (review.get("user") or {}).get("login"), "actor_type": actor_type(review.get("user")), "commit_id": review.get("commit_id"), "pr_number": number}, collection_timestamp=bundle.get("collected_at"))
            self.add_edge(pr_key, review_key, "PR_HAS_REVIEW", "rest_pr_reviews", review.get("html_url") or pull.get("html_url"), review_id, review.get("submitted_at"), temporal_status="verified")
            events.append(self._timeline_event("review", review.get("submitted_at"), (review.get("user") or {}).get("login"), review.get("body") or review.get("state"), review.get("html_url"), review_id, commit_sha=review.get("commit_id"), actor_kind=actor_type(review.get("user"))))
        for comment in data.get("review_comments") or []:
            events.append(self._timeline_event("inline_review_comment", comment.get("created_at"), (comment.get("user") or {}).get("login"), comment.get("body"), comment.get("html_url"), comment.get("id"), commit_sha=comment.get("commit_id"), actor_kind=actor_type(comment.get("user"))))
        for commit in data.get("commits") or []:
            sha = commit.get("sha")
            if not sha:
                continue
            info = commit.get("commit") or {}
            author = info.get("author") or {}
            commit_key = self.add_node("COMMIT", repo, sha, title=(info.get("message") or "").splitlines()[0][:120], created_at=author.get("date"), source_url=commit.get("html_url"), description=info.get("message"), description_temporal_status="commit_message_versioned", metadata={"author": author.get("name"), "author_timestamp": author.get("date"), "committer_timestamp": (info.get("committer") or {}).get("date"), "timestamp_is_push_time": False, "pr_number": number}, collection_timestamp=bundle.get("collected_at"))
            self.add_edge(pr_key, commit_key, "PR_CONTAINS_COMMIT", "rest_pr_commits", commit.get("html_url"), sha, None, temporal_status="commit_visibility_unknown")
            events.append(self._timeline_event("commit_authored", author.get("date"), author.get("name"), info.get("message"), commit.get("html_url"), sha, temporal_status="not_push_time", commit_sha=sha))
        for file in data.get("files") or []:
            filename = file.get("filename")
            if not filename:
                continue
            file_key = self.add_node("FILE", repo, filename, title=filename, source_url=file.get("blob_url") or pull.get("html_url"), metadata={"path": filename})
            self.add_edge(pr_key, file_key, "PR_MODIFIES_FILE", "rest_pr_files_final_diff", file.get("blob_url") or (pull.get("html_url") or "") + "/files", filename, None, temporal_status="final_diff_only")
            self.files_by_pr[pr_key].add(filename)
        for event in data.get("timeline") or []:
            if event.get("event") == "cross-referenced":
                for source_repo, source_n, source_type, source_event in _timeline_sources([event], repo):
                    source_key = self._source_node(source_repo, source_n, source_type, event)
                    relation = "ISSUE_REFERENCES_PR" if source_type == "ISSUE" else "PR_REFERENCES_PR"
                    self.add_edge(source_key, pr_key, relation, "rest_timeline_cross_reference", event.get("url") or pull.get("html_url"), event.get("id"), event.get("created_at"), temporal_status="verified", content=event.get("body"))
            elif event.get("event") in ("connected", "disconnected"):
                # Preserve raw event in the bundle; the REST payload is not always
                # sufficient to identify both endpoints, so no edge is invented.
                pass
            if event.get("created_at") and event.get("event") in ("committed", "renamed", "ready_for_review", "review_requested"):
                events.append(self._timeline_event(event["event"], event["created_at"], (event.get("actor") or {}).get("login"), None, event.get("url"), event.get("id"), actor_kind=actor_type(event.get("actor"))))
        for issue in (data.get("closing_issues") or {}).get("nodes") or []:
            issue_repo = (issue.get("repository") or {}).get("nameWithOwner") or repo
            issue_key = self.add_node("ISSUE", issue_repo, issue["number"], title=issue.get("title"), source_url=issue.get("url"), boundary=issue_repo != repo)
            self.add_edge(issue_key, pr_key, "ISSUE_RESOLVED_BY_PR", "graphql_closing_issues", issue.get("url") or pull.get("html_url"), issue.get("id"), None, temporal_status="relationship_creation_unknown")
        current_text = (pull.get("title") or "") + "\n" + (pull.get("body") or "")
        dependency_refs = {ref for match in DEPENDENCY.finditer(current_text) for ref in _references(match.group(0), repo)}
        for target_repo, target_n in _references(current_text, repo)[:self.cfg["max_neighbors_per_seed"]]:
            if target_repo == repo and target_n == number:
                continue
            target_key = self._resolve_reference(target_repo, target_n)
            target_type = self.nodes[target_key]["type"]
            relation = "PR_DEPENDS_ON_PR" if target_type == "PULL_REQUEST" and (target_repo, target_n) in dependency_refs else "PR_REFERENCES_PR" if target_type == "PULL_REQUEST" else "ISSUE_REFERENCED_BY_PR" if target_type == "ISSUE" else "PR_REFERENCES_UNKNOWN"
            self.add_edge(target_key if target_type == "ISSUE" else pr_key, pr_key if target_type == "ISSUE" else target_key, relation, "current_pr_text_reference", pull.get("html_url"), f"{number}:{target_repo}#{target_n}", None, verification_status="candidate", temporal_status="current_text_edited_possible")
        events.sort(key=lambda x: (x.get("timestamp") or "9999", x["event_type"]))
        self.timelines[pr_key] = events
        self.collection["seed_bundles_found"] += 1
        self.collection["endpoint_errors"] += len(bundle.get("errors") or {})
        self.collection["truncated_endpoints"] += sum(bool(v.get("truncated")) for v in (bundle.get("coverage") or {}).values())

    def _source_node(self, repo, number, kind, event):
        source = ((event.get("source") or {}).get("issue") or {})
        return self.add_node(kind, repo, number, title=source.get("title"), created_at=source.get("created_at"), source_url=source.get("html_url"), boundary=repo not in self.sampled_repos)

    def _resolve_reference(self, repo, number):
        if repo in self.sampled_repos:
            path = self.root / "data/raw" / repo.replace("/", "__") / "neighbors" / f"{number}.json"
            if path.exists():
                issue = (json.loads(path.read_text()).get("data") or {}).get("issue") or {}
                if issue:
                    return self._issue_node(repo, issue)
            for kind in ("ISSUE", "PULL_REQUEST"):
                key = node_id(kind, repo, number)
                if key in self.nodes:
                    return key
        return self.add_node("BOUNDARY", repo, number, source_url=f"https://github.com/{repo}/issues/{number}", boundary=True, metadata={"node_type_uncertain": True})

    def _build_neighbor(self, repo, path):
        bundle = json.loads(path.read_text())
        data = bundle.get("data") or {}
        issue = data.get("issue") or {}
        if not issue:
            return
        key = self._issue_node(repo, issue)
        if issue.get("pull_request"):
            return
        for event in data.get("timeline") or []:
            for source_repo, source_n, source_type, source_event in _timeline_sources([event], repo):
                source_key = self._source_node(source_repo, source_n, source_type, event)
                relation = "ISSUE_REFERENCED_BY_PR" if source_type == "PULL_REQUEST" else "ISSUE_RELATES_TO_ISSUE"
                self.add_edge(key if source_type == "PULL_REQUEST" else source_key, source_key if source_type == "PULL_REQUEST" else key, relation, "rest_issue_timeline_cross_reference", event.get("url") or issue.get("html_url"), event.get("id"), event.get("created_at"), temporal_status="verified")

    def _derived_and_candidates(self):
        issue_to_prs = defaultdict(set)
        for edge in self.edges:
            if edge["verification_status"] != "verified":
                continue
            source_type = self.nodes[edge["source"]]["type"]
            target_type = self.nodes[edge["target"]]["type"]
            if source_type == "ISSUE" and target_type == "PULL_REQUEST":
                issue_to_prs[edge["source"]].add(edge["target"])
            elif source_type == "PULL_REQUEST" and target_type == "ISSUE":
                issue_to_prs[edge["target"]].add(edge["source"])
        for issue, prs in issue_to_prs.items():
            ordered = sorted(prs)
            for i, left in enumerate(ordered):
                for right in ordered[i+1:]:
                    self.add_edge(left, right, "PR_PART_OF_SAME_ISSUE", "derived_shared_verified_issue", self.nodes[issue].get("source_url"), issue, None, verification_status="derived", temporal_status="derived_from_explicit_links")
        by_repo = defaultdict(list)
        for pr in self.seed_ids:
            by_repo[self.nodes[pr]["repo"]].append(pr)
        for repo in sorted(by_repo):
            prs = by_repo[repo]
            added = 0
            for i, left in enumerate(sorted(prs)):
                for right in sorted(prs)[i+1:]:
                    common = self.files_by_pr[left] & self.files_by_pr[right]
                    if len(common) < 2:
                        continue
                    if added >= 500:
                        break
                    self.add_edge(left, right, "POTENTIAL_CODE_OVERLAP", "shared_final_diff_files", self.nodes[left].get("source_url"), ",".join(sorted(common)[:3]), None, verification_status="candidate", temporal_status="overlap_time_unknown", content=f"Shared changed files: {', '.join(sorted(common)[:5])}. This does not prove task relation or dependency.", supporting_urls=[self.nodes[left].get("source_url"), self.nodes[right].get("source_url")])
                    added += 1

    def build(self):
        sampled = pd.read_csv(self.root / "results/sampled_prs.csv")
        self.sampled_repos = set(sampled.repo)
        # Declare all sampled PR identities before resolving text references.
        # Otherwise a reference to a later seed becomes a spurious boundary node.
        for record in sampled.to_dict("records"):
            bundle_path = self.root / "data/raw" / record["repo"].replace("/", "__") / "prs" / f"{int(record['pr_number'])}.json"
            if not bundle_path.exists():
                continue
            self.add_node("PULL_REQUEST", record["repo"], int(record["pr_number"]),
                          title=record.get("title"), created_at=record.get("created_at"),
                          source_url=record.get("pr_url"),
                          metadata={"sampling_group": record.get("sampling_group")}, seed=True)
        for record in sampled.to_dict("records"):
            repo, number = record["repo"], int(record["pr_number"])
            path = self.root / "data/raw" / repo.replace("/", "__") / "prs" / f"{number}.json"
            if path.exists():
                self._build_pr(repo, number, record, json.loads(path.read_text()))
            else:
                self.collection["seed_bundles_missing"] += 1
        for repo in sorted(self.sampled_repos):
            neighbor_dir = self.root / "data/raw" / repo.replace("/", "__") / "neighbors"
            for path in sorted(neighbor_dir.glob("*.json")) if neighbor_dir.exists() else []:
                self._build_neighbor(repo, path)
            expansion_path = self.root / "data/processed" / repo.replace("/", "__") / "expansion.json"
            if expansion_path.exists():
                expansion = json.loads(expansion_path.read_text())
                self.collection["expanded_neighbor_attempts"] += len(expansion.get("neighbors") or [])
                self.collection["boundary_nodes_recorded"] += len(expansion.get("boundary_nodes") or [])
                self.collection["expanded_neighbor_endpoint_errors"] += sum(len(item.get("errors") or {}) for item in expansion.get("errors") or [])
                self.collection["unresolved_expanded_neighbor_nodes"] += sum(node_id("ISSUE", repo, x["number"]) not in self.nodes and node_id("PULL_REQUEST", repo, x["number"]) not in self.nodes for x in expansion.get("neighbors") or [])
                if expansion.get("truncated"):
                    self.collection["truncated_repositories"].append(repo)
                for boundary in expansion.get("boundary_nodes") or []:
                    self.add_node("BOUNDARY", boundary["repo"], boundary["number"], source_url=boundary.get("url"), boundary=True, metadata={"node_type_hint": boundary.get("node_type")})
        self._derived_and_candidates()
        output = self.root / "results"
        output.mkdir(exist_ok=True)
        for name, values in (("graph_nodes.jsonl", self.nodes.values()), ("graph_edges.jsonl", self.edges), ("pr_timelines.jsonl", ({"pr_id": k, "events": v} for k, v in self.timelines.items()))):
            (output / name).write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values))
        (output / "collection_quality.json").write_text(json.dumps(self.collection, indent=2) + "\n")
        LOG.info("graph_built nodes=%s edges=%s seed=%s", len(self.nodes), len(self.edges), len(self.seed_ids))
        return self
