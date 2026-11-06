import json
from pathlib import Path

from fastapi.testclient import TestClient

from analysis.build_graph import GraphBuilder, node_id
from analysis.metrics import analyze, graph_view
from backend.app.main import create_app, _csv_records
from collector.collect import _references, _timeline_sources
from scripts import export_bundle


def test_number_namespace_and_multiedges(tmp_path):
    builder = GraphBuilder(tmp_path, {})
    issue = builder.add_node('ISSUE', 'o/r', 7, title='issue')
    pr = builder.add_node('PULL_REQUEST', 'o/r', 7, title='pr')
    assert issue != pr
    builder.add_edge(issue, pr, 'ISSUE_RESOLVED_BY_PR', 'graphql_closing_issues', 'https://github.com/o/r/issues/7', 11)
    builder.add_edge(issue, pr, 'ISSUE_REFERENCED_BY_PR', 'rest_timeline_cross_reference', 'https://github.com/o/r/issues/7', 12)
    assert len(builder.edges) == 2
    assert graph_view(builder.nodes, builder.edges, 'verified_explicit').number_of_edges() == 1


def test_multi_pr_multi_issue_cycle_external_and_standalone(tmp_path):
    builder = GraphBuilder(tmp_path, {})
    builder.sampled_repos = {'o/r'}
    i1, i2 = (builder.add_node('ISSUE', 'o/r', n) for n in (1, 2))
    p1, p2, p3 = (builder.add_node('PULL_REQUEST', 'o/r', n, seed=True, metadata={'sampling_group': 'random'}) for n in (10, 11, 12))
    builder.seed_ids = {p1, p2, p3}
    for issue, pr in ((i1, p1), (i1, p2), (i2, p1)):
        builder.add_edge(issue, pr, 'ISSUE_RESOLVED_BY_PR', 'graphql_closing_issues', 'https://github.com/o/r/issues/1')
    builder.add_edge(p1, p2, 'PR_REFERENCES_PR', 'rest_timeline_cross_reference', 'https://github.com/o/r/pull/10', 9)
    builder.add_edge(p2, p1, 'PR_REFERENCES_PR', 'rest_timeline_cross_reference', 'https://github.com/o/r/pull/11', 10)
    external = builder.add_node('BOUNDARY', 'other/repo', 3, boundary=True)
    builder.add_edge(p1, external, 'PR_REFERENCES_UNKNOWN', 'current_pr_text_reference', 'https://github.com/o/r/pull/10', 11, verification_status='candidate')
    assert _references('see other/repo#3 and #9', 'o/r') == [('other/repo', 3), ('o/r', 9)]
    assert graph_view(builder.nodes, builder.edges, 'verified_explicit').degree(p3) == 0
    assert graph_view(builder.nodes, builder.edges, 'verified_explicit').number_of_nodes() == 5  # boundary excluded
    (tmp_path / 'results').mkdir()
    _, metrics, patterns, _ = analyze(builder)
    m = metrics['o/r']
    assert m['issues_linked_to_multiple_prs'] == 1
    assert m['prs_linked_to_multiple_issues'] == 1
    assert m['explicit_pr_pr_pairs'] == 1  # reciprocal references deduplicated as a pair
    assert m['isolated_seed_prs'] == 1
    assert {'B_one_issue_multiple_prs', 'C_multiple_issues_one_pr', 'D_explicit_pr_pr_reference', 'G_no_identifiable_issue_link'} <= set(patterns.pattern)


def test_timeline_source_type_and_edit_uncertainty(tmp_path):
    event = {'event': 'cross-referenced', 'id': 20, 'created_at': '2025-01-02T00:00:00Z', 'source': {'issue': {'html_url': 'https://github.com/other/repo/pull/8', 'pull_request': {'url': 'x'}}}}
    assert _timeline_sources([event], 'o/r')[0][:3] == ('other/repo', 8, 'PULL_REQUEST')
    results = tmp_path / 'results'; results.mkdir()
    node = {'id': node_id('PULL_REQUEST', 'o/r', 1), 'type': 'PULL_REQUEST', 'repo': 'o/r', 'number': 1, 'title': 'Current edited title', 'created_at': '2025-01-01T00:00:00Z', 'description': 'Edited later', 'description_temporal_status': 'current_text_edited_possible', 'metadata': {}}
    (results / 'graph_nodes.jsonl').write_text(json.dumps(node) + '\n')
    (results / 'graph_edges.jsonl').write_text(json.dumps({'id':'e1','source':node['id'],'target':node['id'],'relation_type':'PR_REFERENCES_PR','verification_status':'candidate','evidence_timestamp':None})+'\n')
    (results / 'pr_timelines.jsonl').write_text(json.dumps({'pr_id': node['id'], 'events': [{'event_type':'pr_opened','timestamp':'2025-01-01T00:00:00Z','content':'Editable text','source_url':'https://github.com/o/r/pull/1'}, {'event_type':'commit_authored','timestamp':'2025-01-01T00:00:01Z','content':'commit'}]})+'\n')
    client = TestClient(create_app(tmp_path))
    response = client.get('/api/pr/o/r/1?as_of=2025-01-02').json()
    assert response['pr']['description'] is None
    assert response['pr']['title'] == 'PR #1'
    assert response['relationships'] == []
    assert len(response['timeline']) == 1
    assert response['timeline'][0]['content'] is None
    assert client.get('/api/pr/o/r/1?as_of=2024-12-31').status_code == 404


def test_component_csv_unknown_span_is_json_safe(tmp_path):
    path = tmp_path / 'connected_components.csv'
    path.write_text('component_id,repo,scope,size,span_days_known_timestamps,node_ids\n'
                    'x,o/r,verified_explicit,1,,"[""issue:o/r#1""]"\n')
    rows = _csv_records(path)
    assert rows[0]['span_days_known_timestamps'] is None
    assert json.dumps(rows, allow_nan=False)


def test_public_export_requires_recorded_clearance(tmp_path, monkeypatch):
    project = tmp_path / 'github_pr_topology'
    (project / 'results').mkdir(parents=True)
    (project / 'results/selected_repositories.csv').write_text('full_name,processing_track,license_spdx\no/r,license_verified,MIT\n')
    monkeypatch.setattr(export_bundle, 'ROOT', project)
    try:
        export_bundle.export('PUBLIC_RELEASE', tmp_path / 'out')
    except ValueError as exc:
        assert 'clearance manifest' in str(exc)
    else:
        raise AssertionError('Unreviewed public export was permitted')
    assert not (tmp_path / 'out').exists()
    (tmp_path / 'github_repo_discovery/results').mkdir(parents=True)
    (tmp_path / 'github_repo_discovery/results/processing_candidates.csv').write_text('full_name,processing_track\nrestricted/repo,license_unverified\n')
    (project / 'results/graph_nodes.jsonl').write_text('{"repo":"restricted/repo"}\n')
    clearance = tmp_path / 'clearance.json'
    clearance.write_text(json.dumps({'reviewer':'researcher', 'reviewed_at':'2026-11-06', 'intended_distribution':'public', 'repositories':['o/r'], 'approved_files':['results/graph_nodes.jsonl']}))
    try:
        export_bundle.export('PUBLIC_RELEASE', tmp_path / 'out', clearance)
    except ValueError as exc:
        assert 'boundary repositories' in str(exc)
    else:
        raise AssertionError('Restricted boundary record was exported')
    assert not (tmp_path / 'out').exists()
