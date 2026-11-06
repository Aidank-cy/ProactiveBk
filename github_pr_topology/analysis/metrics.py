"""Topology metrics with explicit graph scope and denominators."""
import json
from collections import Counter, defaultdict
from datetime import datetime

import networkx as nx
import pandas as pd

EXPLICIT_TYPES = {"ISSUE_RESOLVED_BY_PR", "ISSUE_REFERENCED_BY_PR", "ISSUE_REFERENCES_PR", "PR_REFERENCES_PR", "ISSUE_RELATES_TO_ISSUE", "PR_DEPENDS_ON_PR"}
MACRO_TYPES = {"ISSUE", "PULL_REQUEST"}


def _date(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def graph_view(nodes, edges, scope, repo=None):
    graph = nx.Graph()
    for node in nodes.values():
        if node["type"] in MACRO_TYPES and not node.get("boundary") and (repo is None or node["repo"] == repo):
            graph.add_node(node["id"])
    for edge in edges:
        if edge["source"] not in graph or edge["target"] not in graph:
            continue
        status = edge["verification_status"]
        allowed = status == "verified" and edge["relation_type"] in EXPLICIT_TYPES
        if scope in ("derived", "candidate"):
            allowed |= status == "derived"
        if scope == "candidate":
            allowed |= status == "candidate"
        if allowed:
            graph.add_edge(edge["source"], edge["target"])
    return graph


def _component_rows(nodes, graph, repo, scope):
    groups = sorted(nx.connected_components(graph), key=lambda group: (-len(group), min(group)))
    rows = []
    for idx, group in enumerate(groups, 1):
        dates = [_date(nodes[n].get("created_at")) for n in group]
        dates = [x for x in dates if x is not None]
        rows.append({"component_id": f"{repo or 'aggregate'}:{scope}:{idx}", "repo": repo or "aggregate", "scope": scope, "size": len(group), "issues": sum(nodes[n]["type"] == "ISSUE" for n in group), "pull_requests": sum(nodes[n]["type"] == "PULL_REQUEST" for n in group), "seed_prs": sum(bool(nodes[n].get("seed")) for n in group), "span_days_known_timestamps": round((max(dates) - min(dates)).total_seconds() / 86400, 2) if len(dates) >= 2 else None, "node_ids": json.dumps(sorted(group))})
    return rows


def analyze(builder):
    nodes, edges = builder.nodes, builder.edges
    repos = sorted(builder.sampled_repos)
    all_components, all_patterns = [], []
    repository_metrics = {}
    relation_counts = Counter(e["relation_type"] for e in edges)
    explicit_issues = defaultdict(set)
    explicit_prs = defaultdict(set)
    pr_pr_pairs = set()
    possible_dependencies = set()
    for edge in edges:
        source, target = nodes[edge["source"]], nodes[edge["target"]]
        pair_types = {source["type"], target["type"]}
        if edge["verification_status"] == "verified" and pair_types == {"ISSUE", "PULL_REQUEST"} and edge["relation_type"] in EXPLICIT_TYPES:
            issue_id = source["id"] if source["type"] == "ISSUE" else target["id"]
            pr_id = source["id"] if source["type"] == "PULL_REQUEST" else target["id"]
            explicit_issues[issue_id].add(pr_id)
            explicit_prs[pr_id].add(issue_id)
        if pair_types == {"PULL_REQUEST"} and edge["relation_type"] in {"PR_REFERENCES_PR", "PR_DEPENDS_ON_PR"} and edge["verification_status"] == "verified":
            pr_pr_pairs.add(tuple(sorted((source["id"], target["id"]))))
        if edge["relation_type"] == "PR_DEPENDS_ON_PR" and edge["verification_status"] == "candidate":
            possible_dependencies.add(tuple(sorted((source["id"], target["id"]))))
    for repo in repos:
        seed_ids = sorted(n for n in builder.seed_ids if nodes[n]["repo"] == repo)
        local_issue_ids = {n for n, v in nodes.items() if v["repo"] == repo and v["type"] == "ISSUE" and not v.get("boundary")}
        local_pr_ids = {n for n, v in nodes.items() if v["repo"] == repo and v["type"] == "PULL_REQUEST" and not v.get("boundary")}
        views = {scope: graph_view(nodes, edges, scope, repo) for scope in ("verified_explicit", "derived", "candidate")}
        for scope, graph in views.items():
            all_components.extend(_component_rows(nodes, graph, repo, scope))
        explicit_graph = views["verified_explicit"]
        issue_degrees = {n: len(explicit_issues[n]) for n in local_issue_ids}
        pr_degrees = {n: len(explicit_prs[n]) for n in local_pr_ids}
        repo_pr_pairs = {pair for pair in pr_pr_pairs if nodes[pair[0]]["repo"] == repo and nodes[pair[1]]["repo"] == repo}
        # Patterns overlap by design. Each row carries the exact matching witness.
        for issue, degree in sorted(issue_degrees.items()):
            if degree == 1:
                all_patterns.append({"repo": repo, "pattern": "A_one_issue_one_pr", "anchor_id": issue, "witness_ids": json.dumps([issue, *sorted(explicit_issues[issue])]), "evidence_class": "verified_graph"})
            elif degree >= 2:
                all_patterns.append({"repo": repo, "pattern": "B_one_issue_multiple_prs", "anchor_id": issue, "witness_ids": json.dumps([issue, *sorted(explicit_issues[issue])]), "evidence_class": "verified_graph"})
        for pr, degree in sorted(pr_degrees.items()):
            if degree >= 2:
                all_patterns.append({"repo": repo, "pattern": "C_multiple_issues_one_pr", "anchor_id": pr, "witness_ids": json.dumps([pr, *sorted(explicit_prs[pr])]), "evidence_class": "verified_graph"})
        for left, right in sorted(repo_pr_pairs):
            all_patterns.append({"repo": repo, "pattern": "D_explicit_pr_pr_reference", "anchor_id": left, "witness_ids": json.dumps([left, right]), "evidence_class": "verified_reference_not_dependency"})
        pr_directed = nx.DiGraph()
        for edge in edges:
            if edge["verification_status"] == "verified" and edge["relation_type"] in ("PR_REFERENCES_PR", "PR_DEPENDS_ON_PR") and edge["source"] in local_pr_ids and edge["target"] in local_pr_ids:
                pr_directed.add_edge(edge["source"], edge["target"])
        chain_found = False
        for first, middle in pr_directed.edges():
            for last in pr_directed.successors(middle):
                if last != first:
                    path = [first, middle, last]
                    all_patterns.append({"repo": repo, "pattern": "E_pr_reference_chain", "anchor_id": first, "witness_ids": json.dumps(path), "evidence_class": "verified_references_not_causality"})
                    chain_found = True
                    break
            if chain_found:
                break
        for row in _component_rows(nodes, explicit_graph, repo, "verified_explicit"):
            ids = json.loads(row["node_ids"])
            if row["issues"] >= 2 and row["pull_requests"] >= 2 and sum(bool(explicit_prs[n]) for n in ids if nodes[n]["type"] == "PULL_REQUEST") >= 2:
                all_patterns.append({"repo": repo, "pattern": "F_many_to_many_component", "anchor_id": ids[0], "witness_ids": row["node_ids"], "evidence_class": "verified_graph"})
        for pr in seed_ids:
            if not explicit_prs[pr]:
                all_patterns.append({"repo": repo, "pattern": "G_no_identifiable_issue_link", "anchor_id": pr, "witness_ids": json.dumps([pr]), "evidence_class": "absence_in_observed_graph"})
        for edge in edges:
            if edge["relation_type"] == "POTENTIAL_CODE_OVERLAP" and nodes[edge["source"]]["repo"] == repo:
                all_patterns.append({"repo": repo, "pattern": "H_shared_files_candidate", "anchor_id": edge["source"], "witness_ids": json.dumps([edge["source"], edge["target"]]), "evidence_class": "candidate_not_dependency"})
        human_rounds, review_version_changes, feedback_followed_by_commit_event = 0, 0, 0
        for pr in seed_ids:
            reviews = [n for n in nodes.values() if n["type"] == "REVIEW" and n["repo"] == repo and n["metadata"].get("pr_number") == nodes[pr]["number"] and n["metadata"].get("actor_type") == "human" and n["metadata"].get("author") != nodes[pr]["metadata"].get("author")]
            if len(reviews) >= 2:
                human_rounds += 1
            commits = {n["metadata"].get("commit_id") for n in reviews if n["metadata"].get("commit_id")}
            if len(commits) >= 2:
                review_version_changes += 1
            events = builder.timelines.get(pr, [])
            author = nodes[pr]["metadata"].get("author")
            feedback_dates = [_date(e.get("timestamp")) for e in events if e.get("event_type") in ("review", "inline_review_comment", "discussion_comment") and e.get("actor_type") == "human" and e.get("actor") != author]
            commit_event_dates = [_date(e.get("timestamp")) for e in events if e.get("event_type") == "committed"]
            if any(feedback and commit and commit > feedback for feedback in feedback_dates for commit in commit_event_dates):
                feedback_followed_by_commit_event += 1
        degrees = [degree for _, degree in explicit_graph.degree()]
        repository_metrics[repo] = {"seed_prs": len(seed_ids), "random_seed_prs": sum(nodes[n]["metadata"].get("sampling_group") == "random" for n in seed_ids), "enriched_seed_prs": sum(nodes[n]["metadata"].get("sampling_group") == "interaction_enriched" for n in seed_ids), "expanded_issue_pr_nodes": len(local_issue_ids | local_pr_ids) - len(seed_ids), "issue_nodes": len(local_issue_ids), "pr_nodes": len(local_pr_ids), "seed_prs_with_explicit_issue_link": sum(bool(explicit_prs[n]) for n in seed_ids), "random_prs_with_explicit_issue_link": sum(bool(explicit_prs[n]) and nodes[n]["metadata"].get("sampling_group") == "random" for n in seed_ids), "enriched_prs_with_explicit_issue_link": sum(bool(explicit_prs[n]) and nodes[n]["metadata"].get("sampling_group") == "interaction_enriched" for n in seed_ids), "issues_linked_to_one_pr": sum(d == 1 for d in issue_degrees.values()), "issues_linked_to_multiple_prs": sum(d >= 2 for d in issue_degrees.values()), "prs_linked_to_multiple_issues": sum(d >= 2 for d in pr_degrees.values()), "explicit_pr_pr_pairs": len(repo_pr_pairs), "possible_pr_dependencies": sum(nodes[a]["repo"] == repo for a, b in possible_dependencies), "isolated_seed_prs": sum(explicit_graph.degree(n) == 0 for n in seed_ids), "max_degree": max(degrees, default=0), "average_degree": round(sum(degrees) / len(degrees), 3) if degrees else 0, "component_counts": {scope: nx.number_connected_components(graph) for scope, graph in views.items()}, "component_size_distribution": {scope: dict(Counter(len(c) for c in nx.connected_components(graph))) for scope, graph in views.items()}, "prs_with_multiple_human_review_rounds": human_rounds, "prs_with_reviews_on_multiple_commit_versions": review_version_changes, "prs_with_observable_feedback_followed_by_commit_event": feedback_followed_by_commit_event, "coverage_note": "Review commit version differences do not prove post-feedback push timing."}
    aggregate_views = {scope: graph_view(nodes, edges, scope) for scope in ("verified_explicit", "derived", "candidate")}
    aggregate = {"repositories": len(repos), "seed_prs": len(builder.seed_ids), "issue_nodes": sum(n["type"] == "ISSUE" and not n.get("boundary") for n in nodes.values()), "pr_nodes": sum(n["type"] == "PULL_REQUEST" and not n.get("boundary") for n in nodes.values()), "expanded_issue_pr_nodes": sum(v["expanded_issue_pr_nodes"] for v in repository_metrics.values()), "seed_prs_with_explicit_issue_link": sum(bool(explicit_prs[n]) for n in builder.seed_ids), "seed_prs_without_explicit_issue_link": sum(not explicit_prs[n] for n in builder.seed_ids), "random_seed_prs": sum(v["random_seed_prs"] for v in repository_metrics.values()), "random_seed_prs_with_explicit_issue_link": sum(v["random_prs_with_explicit_issue_link"] for v in repository_metrics.values()), "enriched_seed_prs": sum(v["enriched_seed_prs"] for v in repository_metrics.values()), "enriched_seed_prs_with_explicit_issue_link": sum(v["enriched_prs_with_explicit_issue_link"] for v in repository_metrics.values()), "issues_linked_to_one_pr": sum(v["issues_linked_to_one_pr"] for v in repository_metrics.values()), "issues_linked_to_multiple_prs": sum(v["issues_linked_to_multiple_prs"] for v in repository_metrics.values()), "prs_linked_to_multiple_issues": sum(v["prs_linked_to_multiple_issues"] for v in repository_metrics.values()), "explicit_pr_pr_pairs": len(pr_pr_pairs), "possible_pr_dependencies": len(possible_dependencies), "isolated_seed_prs": sum(v["isolated_seed_prs"] for v in repository_metrics.values()), "prs_with_multiple_human_review_rounds": sum(v["prs_with_multiple_human_review_rounds"] for v in repository_metrics.values()), "prs_with_reviews_on_multiple_commit_versions": sum(v["prs_with_reviews_on_multiple_commit_versions"] for v in repository_metrics.values()), "prs_with_observable_feedback_followed_by_commit_event": sum(v["prs_with_observable_feedback_followed_by_commit_event"] for v in repository_metrics.values()), "relationship_type_distribution": dict(relation_counts), "graph_scopes": {scope: {"connected_components": nx.number_connected_components(graph), "component_size_distribution": dict(Counter(len(c) for c in nx.connected_components(graph))), "max_degree": max((d for _, d in graph.degree()), default=0), "average_degree": round(sum(d for _, d in graph.degree()) / len(graph), 3) if graph else 0} for scope, graph in aggregate_views.items()}, "collection_quality": builder.collection, "denominator_note": "Random PR prevalence uses only random seed PRs within the bounded recent-PR frame. Enriched PRs are descriptive. Expanded neighbors are not added to prevalence denominators."}
    aggregate["verified_pr_degree_distribution"] = dict(sorted(Counter(aggregate_views["verified_explicit"].degree(pr) for pr in builder.seed_ids).items()))
    aggregate["issue_pr_activity_by_month"] = dict(sorted(Counter((n.get("created_at") or "")[:7] for n in nodes.values() if n["type"] in MACRO_TYPES and n.get("created_at") and not n.get("boundary")).items()))
    aggregate["pattern_distribution"] = dict(Counter(row["pattern"] for row in all_patterns))
    macro_edges = [edge for edge in edges if nodes[edge["source"]]["type"] in MACRO_TYPES and nodes[edge["target"]]["type"] in MACRO_TYPES]
    temporal_uncertain = sum(edge.get("temporal_status") != "verified" or not edge.get("evidence_timestamp") for edge in macro_edges)
    selected_total = builder.collection["seed_bundles_found"] + builder.collection["seed_bundles_missing"]
    aggregate["data_quality_rates"] = {
        "collected_seed_prs": builder.collection["seed_bundles_found"],
        "selected_seed_prs": selected_total,
        "seed_bundle_completion_rate": round(builder.collection["seed_bundles_found"] / selected_total, 4) if selected_total else None,
        "macro_edges_with_temporal_uncertainty": temporal_uncertain,
        "macro_edge_count": len(macro_edges),
        "macro_edge_temporal_uncertainty_rate": round(temporal_uncertain / len(macro_edges), 4) if macro_edges else None,
        "unresolved_expanded_neighbor_nodes": builder.collection["unresolved_expanded_neighbor_nodes"],
        "expanded_neighbor_attempts": builder.collection["expanded_neighbor_attempts"],
    }
    all_components.extend(_component_rows(nodes, aggregate_views["verified_explicit"], None, "verified_explicit"))
    patterns = pd.DataFrame(all_patterns, columns=["repo", "pattern", "anchor_id", "witness_ids", "evidence_class"])
    components = pd.DataFrame(all_components)
    out = builder.root / "results"
    patterns.to_csv(out / "topology_patterns.csv", index=False)
    components.to_csv(out / "connected_components.csv", index=False)
    (out / "graph_metrics.json").write_text(json.dumps({"aggregate": aggregate, "repositories": repository_metrics}, indent=2, ensure_ascii=False) + "\n")
    return aggregate, repository_metrics, patterns, components
