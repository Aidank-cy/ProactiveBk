"""Read-only API for the local topology study."""
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


def _jsonl(path):
    if not path.exists():
        return []
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def _csv_records(path):
    if not path.exists():
        return []
    frame = pd.read_csv(path).astype(object)
    return frame.where(pd.notna(frame), None).to_dict('records')


class DataStore:
    def __init__(self, root):
        self.root = Path(root)
        self.refresh(force=True)

    def refresh(self, force=False):
        output = self.root / "results"
        watch = [output / name for name in ("graph_nodes.jsonl", "graph_edges.jsonl", "graph_metrics.json", "representative_cases.json", "pr_timelines.jsonl")]
        version = tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in watch)
        if not force and version == getattr(self, "version", None):
            return
        self.version = version
        self.nodes = {n["id"]: n for n in _jsonl(output / "graph_nodes.jsonl")}
        self.edges = _jsonl(output / "graph_edges.jsonl")
        self.timelines = {x["pr_id"]: x["events"] for x in _jsonl(output / "pr_timelines.jsonl")}
        self.metrics = _json(output / "graph_metrics.json", {"aggregate": {}, "repositories": {}})
        self.cases = _json(output / "representative_cases.json", [])
        self.components = _csv_records(output / "connected_components.csv")
        self.patterns = _csv_records(output / "topology_patterns.csv")
        self.repos = pd.read_csv(output / "selected_repositories.csv").fillna("").to_dict("records") if (output / "selected_repositories.csv").exists() else []
        self.by_node = defaultdict(list)
        for edge in self.edges:
            self.by_node[edge["source"]].append(edge)
            self.by_node[edge["target"]].append(edge)


def _parse_date(value, end_of_day=True):
    if not value:
        return None
    try:
        if len(value) == 10:
            value += "T23:59:59+00:00" if end_of_day else "T00:00:00+00:00"
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result
    except ValueError:
        raise HTTPException(400, "Invalid ISO timestamp")


def _public_node(node, as_of=None):
    result = dict(node)
    if as_of is not None and result.get("type") in ("ISSUE", "PULL_REQUEST"):
        result["title"] = f"{'PR' if result['type'] == 'PULL_REQUEST' else 'Issue'} #{result['number']}"
        result["description"] = None
        result["description_temporal_status"] = "hidden_in_time_slice_current_title_and_body_not_historically_verified"
    elif as_of is not None and result.get("type") == "REVIEW":
        result["description"] = None
        result["description_temporal_status"] = "hidden_in_time_slice_review_body_edit_history_unverified"
    return result


def _visible_node(node, as_of):
    if as_of is not None and node.get("type") in ("COMMIT", "FILE"):
        return False  # Commit author time and final-file diff do not establish visibility.
    when = _parse_date(node.get("created_at"))
    return as_of is None or when is None or when <= as_of


def _public_event(event, as_of=None):
    result = dict(event)
    if as_of is not None and result.get("event_type") in ("pr_opened", "discussion_comment", "review", "inline_review_comment"):
        result["content"] = None
        result["temporal_status"] = "event_time_known_text_history_unverified"
    return result


def _visible_edge(edge, as_of):
    when = _parse_date(edge.get("evidence_timestamp"))
    return as_of is None or when is not None and when <= as_of


def create_app(root=None):
    root = Path(root or os.environ.get("TOPOLOGY_DATA_ROOT") or Path(__file__).resolve().parents[2])
    store = DataStore(root)
    app = FastAPI(title="GitHub Development Graph Explorer", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["GET"], allow_headers=["*"])

    @app.get("/api/health")
    def health():
        store.refresh()
        return {"status": "ok", "repositories": len(store.repos), "nodes": len(store.nodes), "edges": len(store.edges)}

    @app.get("/api/repositories")
    def repositories():
        store.refresh()
        return [{**row, "metrics": store.metrics.get("repositories", {}).get(row["full_name"], {})} for row in store.repos]

    @app.get("/api/statistics")
    def statistics(repo: str | None = None):
        store.refresh()
        if repo:
            if repo not in store.metrics.get("repositories", {}):
                raise HTTPException(404, "Repository statistics unavailable")
            return {"repo": repo, "metrics": store.metrics["repositories"][repo], "aggregate": store.metrics.get("aggregate", {})}
        return store.metrics

    @app.get("/api/components")
    def components(repo: str | None = None, scope: str = "verified_explicit", limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
        store.refresh()
        rows = [r for r in store.components if r.get("scope") == scope and (repo is None or r.get("repo") == repo)]
        rows.sort(key=lambda r: (-int(r.get("size") or 0), r.get("component_id") or ""))
        return {"total": len(rows), "items": rows[offset:offset + limit]}

    @app.get("/api/graph")
    def graph(repo: str | None = None, scope: str = "verified_explicit", component_id: str | None = None, mode: str = "overview", as_of: str | None = None, since: str | None = None, node_types: str = "ISSUE,PULL_REQUEST,BOUNDARY", relation_types: str | None = None, sampling_group: str | None = None, search: str | None = None, focus_id: str | None = None, limit: int = Query(180, ge=1, le=500)):
        store.refresh()
        cutoff = _parse_date(as_of)
        start = _parse_date(since, end_of_day=False)
        type_set = set(node_types.split(","))
        relations = set(relation_types.split(",")) if relation_types else None
        allowed_status = {"verified"} if scope == "verified_explicit" else {"verified", "derived"} if scope == "derived" else {"verified", "derived", "candidate"}
        nodes = {key: value for key, value in store.nodes.items() if value["type"] in type_set and (repo is None or value["repo"] == repo or value.get("boundary")) and _visible_node(value, cutoff) and (start is None or _parse_date(value.get("created_at")) is None or _parse_date(value.get("created_at")) >= start)}
        if sampling_group:
            nodes = {key: value for key, value in nodes.items() if value["type"] != "PULL_REQUEST" or not value.get("seed") or value.get("metadata", {}).get("sampling_group") == sampling_group}
        if search:
            q = search.lower()
            hits = {key for key, value in nodes.items() if q in str(value.get("number", "")).lower() or q in (value.get("title") or "").lower()}
            keep = set(hits)
            for hit in hits:
                keep.update(edge["target"] if edge["source"] == hit else edge["source"] for edge in store.by_node[hit])
            nodes = {key: value for key, value in nodes.items() if key in keep}
        if component_id:
            component = next((x for x in store.components if x.get("component_id") == component_id), None)
            if component is None:
                raise HTTPException(404, "Component not found")
            allowed = set(json.loads(component["node_ids"]))
            nodes = {key: value for key, value in nodes.items() if key in allowed}
        if focus_id:
            if focus_id not in store.nodes:
                raise HTTPException(404, "Node not found")
            keep = {focus_id}
            for edge in store.by_node[focus_id]:
                keep.add(edge["source"])
                keep.add(edge["target"])
            nodes = {key: value for key, value in nodes.items() if key in keep}
        edges = [e for e in store.edges if e["source"] in nodes and e["target"] in nodes and e["verification_status"] in allowed_status and _visible_edge(e, cutoff) and (relations is None or e["relation_type"] in relations)]
        connected = {key for edge in edges for key in (edge["source"], edge["target"])}
        nodes = {key: value for key, value in nodes.items() if not value.get("boundary") or key in connected}
        total_matching_nodes = len(nodes)
        if mode == "overview" and not component_id and not focus_id and not search and len(nodes) > limit:
            degree = Counter()
            for e in edges:
                degree[e["source"]] += 1
                degree[e["target"]] += 1
            ordered = sorted(nodes, key=lambda key: (-degree[key], not nodes[key].get("seed"), key))
            nodes = {key: nodes[key] for key in ordered[:limit]}
            edges = [e for e in edges if e["source"] in nodes and e["target"] in nodes]
        elif len(nodes) > limit:
            nodes = dict(list(nodes.items())[:limit])
            edges = [e for e in edges if e["source"] in nodes and e["target"] in nodes]
        return {"nodes": [_public_node(n, cutoff) for n in nodes.values()], "edges": edges, "total_matching_nodes": total_matching_nodes, "rendered_nodes": len(nodes), "rendered_edges": len(edges), "truncated_for_display": total_matching_nodes > len(nodes), "scope": scope, "as_of": as_of, "time_slice_note": "Known later events, current editable text, undated links, commits with unverified visibility, and final file diffs are hidden." if as_of else None}

    @app.get("/api/graph/neighbors")
    def neighbors(node_id: str, depth: int = Query(1, ge=1, le=2), scope: str = "candidate", as_of: str | None = None):
        store.refresh()
        if node_id not in store.nodes:
            raise HTTPException(404, "Node not found")
        cutoff = _parse_date(as_of)
        if not _visible_node(store.nodes[node_id], cutoff):
            raise HTTPException(404, "Node did not exist at this date")
        allowed = {"verified"} if scope == "verified_explicit" else {"verified", "derived"} if scope == "derived" else {"verified", "derived", "candidate"}
        visited, frontier = {node_id}, {node_id}
        for _ in range(depth):
            next_frontier = set()
            for current in frontier:
                for edge in store.by_node[current]:
                    if edge["verification_status"] in allowed and _visible_edge(edge, cutoff):
                        next_frontier.update((edge["source"], edge["target"]))
            frontier = {n for n in next_frontier - visited if _visible_node(store.nodes[n], cutoff)}
            visited |= frontier
        return {"nodes": [_public_node(store.nodes[n], cutoff) for n in sorted(visited)], "edges": [e for e in store.edges if e["source"] in visited and e["target"] in visited and e["verification_status"] in allowed and _visible_edge(e, cutoff)]}

    @app.get("/api/nodes/{node_id:path}")
    def node_detail(node_id: str, as_of: str | None = None):
        store.refresh()
        key = unquote(node_id)
        if key not in store.nodes:
            raise HTTPException(404, "Node not found")
        cutoff = _parse_date(as_of)
        if not _visible_node(store.nodes[key], cutoff):
            raise HTTPException(404, "Node did not exist at this date")
        edges = [e for e in store.by_node[key] if _visible_edge(e, cutoff) and _visible_node(store.nodes[e["target"] if e["source"] == key else e["source"]], cutoff)]
        return {"node": _public_node(store.nodes[key], cutoff), "edges": edges, "connections": len({e["target"] if e["source"] == key else e["source"] for e in edges})}

    @app.get("/api/pr/{owner}/{name}/{number}")
    def pr_detail(owner: str, name: str, number: int, as_of: str | None = None):
        store.refresh()
        key = f"pull_request:{owner}/{name}#{number}"
        if key not in store.nodes:
            raise HTTPException(404, "PR not found")
        cutoff = _parse_date(as_of)
        if not _visible_node(store.nodes[key], cutoff):
            raise HTTPException(404, "PR did not exist at this date")
        events = [e for e in store.timelines.get(key, []) if cutoff is None or e.get("event_type") != "commit_authored" and _parse_date(e.get("timestamp")) is not None and _parse_date(e.get("timestamp")) <= cutoff]
        edges = [e for e in store.by_node[key] if _visible_edge(e, cutoff) and _visible_node(store.nodes[e["target"] if e["source"] == key else e["source"]], cutoff)]
        return {"pr": _public_node(store.nodes[key], cutoff), "timeline": [_public_event(e, cutoff) for e in events], "relationships": edges, "related_nodes": [_public_node(store.nodes[e["target"] if e["source"] == key else e["source"]], cutoff) for e in edges], "time_slice_note": "Commit author time does not prove push time; current or editable text hidden." if cutoff else None}

    @app.get("/api/cases")
    def cases(repo: str | None = None, pattern: str | None = None):
        store.refresh()
        items = [c for c in store.cases if (repo is None or c.get("repo") == repo) and (pattern is None or pattern in c.get("patterns", []))]
        return {"total": len(items), "items": items}

    @app.get("/api/cases/{case_id}")
    def case_detail(case_id: str):
        store.refresh()
        case = next((c for c in store.cases if c.get("case_id") == case_id), None)
        if case is None:
            raise HTTPException(404, "Case not found")
        return case

    return app


app = create_app()
