"""Audit a completed topology pilot without altering its data."""
import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def jsonl(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def validate(allow_partial=False):
    results = ROOT / 'results'
    selected = pd.read_csv(results / 'selected_repositories.csv')
    sampled = pd.read_csv(results / 'sampled_prs.csv')
    nodes = jsonl(results / 'graph_nodes.jsonl')
    edges = jsonl(results / 'graph_edges.jsonl')
    timelines = jsonl(results / 'pr_timelines.jsonl')
    metrics = json.loads((results / 'graph_metrics.json').read_text())
    cases = json.loads((results / 'representative_cases.json').read_text())
    patterns = pd.read_csv(results / 'topology_patterns.csv')
    components = pd.read_csv(results / 'connected_components.csv')
    assert len(selected) == 8 and len(sampled) == 640
    assert selected.repository_id.is_unique
    assert not sampled.duplicated(['repo', 'pr_number']).any()
    assert set(selected.processing_track) == {'license_verified'}
    assert sampled.groupby('repo').sampling_group.value_counts().eq(40).all()
    assert set(sampled.repo) == set(selected.full_name)
    node_ids = {node['id'] for node in nodes}
    assert len(node_ids) == len(nodes)
    assert all(edge['source'] in node_ids and edge['target'] in node_ids for edge in edges)
    assert len({edge['id'] for edge in edges}) == len(edges)
    assert all(edge['verification_status'] in ('verified', 'derived', 'candidate') for edge in edges)
    assert all(edge['confidence'] == edge['verification_status'] for edge in edges)
    assert all(edge.get('evidence_type') and edge.get('evidence_url') for edge in edges)
    assert all(t['pr_id'] in node_ids for t in timelines)
    assert metrics['aggregate']['seed_prs'] == len(timelines)
    assert metrics['aggregate']['seed_prs'] == metrics['aggregate']['random_seed_prs'] + metrics['aggregate']['enriched_seed_prs']
    assert len(cases) == 15 and len({c['case_id'] for c in cases}) == len(cases)
    assert all(c['anchor_pr_id'] in node_ids and c['anchor_pr_id'] in {t['pr_id'] for t in timelines} for c in cases)
    assert all(c['pr_url'].startswith('https://github.com/') for c in cases)
    assert all(set(json.loads(row['witness_ids'])) <= node_ids for _, row in patterns.iterrows())
    assert all(set(json.loads(row['node_ids'])) <= node_ids for _, row in components.iterrows())
    expected = 640
    found = metrics['aggregate']['seed_prs']
    if not allow_partial:
        assert found == expected, f'Collected {found}/{expected} seed PRs'
        assert metrics['aggregate']['collection_quality']['endpoint_errors'] == 0, 'Seed endpoint failures remain'
    inventory = ROOT.parent / 'github_repo_discovery/results/processing_candidates.csv'
    restricted = set(pd.read_csv(inventory).query("processing_track == 'license_unverified'").full_name) if inventory.exists() else set()
    restricted_boundary = sorted({node['repo'] for node in nodes if node.get('boundary') and node['repo'] in restricted})
    searchable = '\n'.join((results / name).read_text() for name in ('graph_nodes.jsonl', 'graph_edges.jsonl', 'representative_cases.json'))
    restricted_mentions = sorted(repo for repo in restricted if repo in searchable)
    audit = {'selected_repositories': len(selected), 'sampled_seed_prs': len(sampled), 'collected_seed_prs': found, 'graph_nodes': len(nodes), 'graph_edges': len(edges), 'case_count': len(cases), 'endpoint_errors': metrics['aggregate']['collection_quality']['endpoint_errors'], 'truncated_expansion_repositories': metrics['aggregate']['collection_quality']['truncated_repositories'], 'license_unverified_boundary_repositories_local_only': restricted_boundary, 'license_unverified_repository_mentions_local_only': restricted_mentions, 'complete_seed_collection': found == expected}
    (results / 'validation_summary.json').write_text(json.dumps(audit, indent=2) + '\n')
    return audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    print(json.dumps(validate(args.allow_partial), indent=2))
