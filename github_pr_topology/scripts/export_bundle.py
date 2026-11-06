"""Audited local export modes; never push or publish automatically."""
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULT_FILES = ['selected_repositories.csv', 'sampled_prs.csv', 'graph_nodes.jsonl', 'graph_edges.jsonl', 'pr_timelines.jsonl', 'graph_metrics.json', 'topology_patterns.csv', 'connected_components.csv', 'representative_cases.json', 'collection_quality.json', 'validation_summary.json']
REPORT_FILES = ['topology_analysis.md', 'case_studies.md']
ALLOWED = {f'results/{name}' for name in RESULT_FILES} | {f'reports/{name}' for name in REPORT_FILES}


def export(mode, output, clearance_manifest=None):
    if mode not in ('LOCAL_RESEARCH', 'PUBLIC_RELEASE'):
        raise ValueError('Unknown export mode')
    selected = pd.read_csv(ROOT / 'results/selected_repositories.csv').fillna('')
    tracks = set(selected.processing_track)
    review = None
    if mode == 'PUBLIC_RELEASE':
        if tracks != {'license_verified'}:
            raise ValueError(f'PUBLIC_RELEASE refused: nonverified tracks {tracks}')
        if not clearance_manifest:
            raise ValueError('PUBLIC_RELEASE requires a reviewed clearance manifest for the intended distribution')
        review = json.loads(Path(clearance_manifest).read_text())
        required = {'reviewer', 'reviewed_at', 'intended_distribution', 'repositories', 'approved_files'}
        if not required <= set(review) or not all(review.get(field) for field in required):
            raise ValueError(f'Clearance manifest lacks required fields: {sorted(required - set(review))}')
        if set(review['repositories']) != set(selected.full_name):
            raise ValueError('Clearance repository set must exactly match the selected pilot')
        files = set(review['approved_files'])
        if not files or not files <= ALLOWED:
            raise ValueError('Clearance approved_files contains no valid files or names outside the export allowlist')
        inventory = ROOT.parent / 'github_repo_discovery/results/processing_candidates.csv'
        if not inventory.exists():
            raise ValueError('PUBLIC_RELEASE cannot audit unverified boundary repositories: local candidate inventory missing')
        restricted = set(pd.read_csv(inventory).query("processing_track == 'license_unverified'").full_name)
        unapproved_boundary = set()
        authorized_boundary = set(review.get('authorized_boundary_repositories') or [])
        evidence = review.get('boundary_authorization_evidence') or {}
        if any(not evidence.get(repo) for repo in authorized_boundary):
            raise ValueError('Every authorized boundary repository needs authorization evidence in the clearance manifest')
        for name in files:
            source = ROOT / name
            if source.exists():
                content = source.read_text(errors='ignore')
                unapproved_boundary.update(repo for repo in restricted - authorized_boundary if repo in content)
        if unapproved_boundary:
            raise ValueError(f'PUBLIC_RELEASE refused: {len(unapproved_boundary)} license-unverified boundary repositories appear in approved files without separate authorization')
    else:
        files = ALLOWED
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory must be empty')
    output.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in sorted(files):
        source = ROOT / name
        if not source.exists():
            raise ValueError(f'Approved file is missing: {name}')
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(name)
    manifest = {
        'mode': mode, 'created_at': datetime.now(timezone.utc).isoformat(),
        'repository_count': len(selected), 'processing_tracks': sorted(tracks),
        'repository_license_evidence': [{'full_name': row['full_name'], 'license_spdx': row.get('license_spdx'), 'license_source_url': row.get('license_source_url'), 'authorization_status': row.get('authorization_status')} for row in selected.to_dict('records')],
        'files': copied, 'clearance': review, 'publication_status': 'locally_exported_after_recorded_review' if review else 'local_only',
        'raw_api_cache_included': False, 'automatic_publication': False,
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['LOCAL_RESEARCH', 'PUBLIC_RELEASE'], required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--clearance-manifest', help='Required for PUBLIC_RELEASE; explicit reviewed files and repository permissions')
    args = parser.parse_args()
    print(json.dumps(export(args.mode, args.output, args.clearance_manifest), indent=2))
