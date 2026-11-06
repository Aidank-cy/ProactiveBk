"""Evidence-linked case selection and descriptive Markdown reporting."""
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PATTERN_LABELS = {
    'A_one_issue_one_pr': 'A · one Issue / one PR',
    'B_one_issue_multiple_prs': 'B · one Issue / multiple PRs',
    'C_multiple_issues_one_pr': 'C · multiple Issues / one PR',
    'D_explicit_pr_pr_reference': 'D · explicit PR reference',
    'E_pr_reference_chain': 'E · PR reference chain',
    'F_many_to_many_component': 'F · many-to-many component',
    'G_no_identifiable_issue_link': 'G · no observed Issue link',
    'H_shared_files_candidate': 'H · shared-file candidate',
}


def _clean(text, limit=180):
    text = ' '.join(str(text or '').split())
    return text[:limit] + ('…' if len(text) > limit else '')


def select_cases(builder, patterns, limit=15):
    nodes, edges = builder.nodes, builder.edges
    by_pr = defaultdict(list)
    for row in patterns.to_dict('records'):
        witnesses = json.loads(row['witness_ids'])
        for witness in witnesses:
            if witness in builder.seed_ids:
                by_pr[witness].append(row['pattern'])
    selected, used_repos, used_patterns = [], Counter(), Counter()
    candidates = sorted(builder.seed_ids)
    while candidates and len(selected) < limit:
        candidates.sort(key=lambda key: (
            -sum(6 if used_patterns[x] == 0 else 1 / (used_patterns[x] + 1) for x in sorted(set(by_pr[key]))),
            used_repos[nodes[key]['repo']],
            -len(builder.timelines.get(key, [])), key))
        key = candidates.pop(0)
        node = nodes[key]
        if not builder.timelines.get(key):
            continue
        direct = [e for e in edges if key in (e['source'], e['target']) and e['source'] in nodes and e['target'] in nodes and nodes[e['source']]['type'] in ('ISSUE', 'PULL_REQUEST', 'BOUNDARY') and nodes[e['target']]['type'] in ('ISSUE', 'PULL_REQUEST', 'BOUNDARY')]
        related = sorted({e['source'] if e['target'] == key else e['target'] for e in direct})
        related_issues = [n for n in related if nodes[n]['type'] == 'ISSUE']
        related_prs = [n for n in related if nodes[n]['type'] == 'PULL_REQUEST']
        verified = [e for e in direct if e['verification_status'] == 'verified']
        candidate = [e for e in direct if e['verification_status'] == 'candidate']
        internal = [e for e in edges if e['source'] == key and e['relation_type'] in ('PR_CONTAINS_COMMIT', 'PR_HAS_REVIEW', 'PR_MODIFIES_FILE')]
        events = builder.timelines.get(key, [])
        event_counts = Counter(event['event_type'] for event in events)
        evolution = (f"Opened {node.get('created_at') or 'date unknown'}; "
                     f"{event_counts.get('review', 0)} formal reviews, "
                     f"{event_counts.get('inline_review_comment', 0)} inline review comments, "
                     f"{event_counts.get('commit_authored', 0)} associated commits; "
                     f"state observed as {node.get('state') or 'unknown'}.")
        case = {
            'case_id': f'case-{len(selected)+1:02d}', 'repo': node['repo'], 'anchor_pr_id': key,
            'title': node['title'], 'pr_url': node['source_url'],
            'patterns': sorted(set(by_pr[key])) or ['G_no_identifiable_issue_link'],
            'summary': f"{len(related_issues)} observed Issue neighbors; {len(related_prs)} PR neighbors; {len(verified)} verified, {len(candidate)} candidate direct links.",
            'node_ids': [key, *related],
            'initial_request': {'title': node['title'], 'current_description_preview': _clean(node.get('description')), 'temporal_caveat': 'Current PR text may have been edited; no historical body version is asserted.'},
            'related_issues': [{'id': n, 'title': nodes[n]['title'], 'url': nodes[n]['source_url']} for n in related_issues],
            'related_prs': [{'id': n, 'title': nodes[n]['title'], 'url': nodes[n]['source_url']} for n in related_prs],
            'timeline': events,
            'development_evolution': evolution,
            'verified_relationships': verified, 'candidate_relationships': candidate,
            'code_changes': [{'type': e['relation_type'], 'summary': nodes[e['target']]['title'], 'url': e['evidence_url'], 'source_id': e['evidence_event_id']} for e in internal if e['relation_type'] in ('PR_CONTAINS_COMMIT', 'PR_MODIFIES_FILE')][:25],
            'human_feedback': [e for e in events if e['event_type'] in ('review', 'inline_review_comment', 'discussion_comment') and e['actor_type'] == 'human' and e['actor'] != node['metadata'].get('author')],
            'historical_evidence': {'base_sha': node['metadata'].get('base_sha'), 'head_sha_current': node['metadata'].get('head_sha'), 'timestamped_events': sum(bool(e.get('timestamp')) for e in events), 'code_visibility_caveat': 'Base/head SHAs identify versions but current API state does not establish the exact push time of each commit.'},
            'evidence_limitations': ['Current descriptions are not a historical snapshot.', 'Commit author dates do not establish push time.', 'Missing observed edges do not prove tasks are independent.'],
            'benchmark_relevance_note': 'Topology may support task-history research; intent inferability and benchmark suitability require separate human assessment.',
        }
        selected.append(case)
        used_repos[node['repo']] += 1
        used_patterns.update(set(case['patterns']))
    (builder.root / 'results/representative_cases.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2) + '\n')
    return selected


def _pct(n, d):
    return f'{n/d*100:.1f}% ({n}/{d})' if d else 'n/a (0/0)'


def _md_link(label, url):
    return f'[{_clean(label, 80)}]({url})' if url else _clean(label, 80)


def case_markdown(cases, nodes):
    lines = ['# Representative real development cases', '', 'These cases use actual collected GitHub records. They illustrate topology, not verified implicit intents. Current editable descriptions are not treated as historically available.', '']
    for case in cases:
        lines += [f"## {case['case_id']} · {_clean(case['title'], 100)}", '', f"**Repository:** {case['repo']} · **PR:** {_md_link(case['anchor_pr_id'], case['pr_url'])}", '', f"**Patterns:** {', '.join(PATTERN_LABELS.get(p,p) for p in case['patterns'])}", '', f"**Development request:** {_clean(case['initial_request']['title'])}. Current PR body preview: {_clean(case['initial_request']['current_description_preview'], 300) or 'unavailable'}. The body may have been edited.", '', '**Connected records:**', '']
        for item in (case['related_issues'] + case['related_prs']):
            lines.append(f"- {_md_link(item['id'] + ' · ' + _clean(item['title'], 90), item['url'])}")
        if not case['related_issues'] and not case['related_prs']:
            lines.append('- No direct Issue/PR link observed in the bounded collection.')
        lines += ['', '**Graph sketch (first eight direct observed neighbors):**', '', '```mermaid', 'graph LR']
        anchor = case['anchor_pr_id']
        lines.append(f'  A["PR #{anchor.rsplit("#",1)[-1]}"]')
        for idx, item in enumerate((case['related_issues'] + case['related_prs'])[:8]):
            label = ('Issue' if item in case['related_issues'] else 'PR') + ' #' + item['id'].rsplit('#',1)[-1]
            lines.append(f'  A --- N{idx}["{label}"]')
        lines += ['```', '', '**Chronological evidence:**', '']
        for event in case['timeline']:
            date = (event.get('timestamp') or 'time unknown')[:19]
            lines.append(f"- {date} · {event['event_type']} · {event.get('actor') or 'unknown'} · {_md_link(_clean(event.get('content') or event.get('source_id'), 110), event.get('source_url'))}")
        lines += ['', '**Explicit relationship evidence:**', '']
        for edge in case['verified_relationships']:
            lines.append(f"- {edge['relation_type']} · {_md_link(edge['evidence_type'], edge.get('evidence_url'))} · observed {edge.get('evidence_timestamp') or 'time unknown'}")
        if not case['verified_relationships']:
            lines.append('- No verified direct Issue/PR relation in the collected graph.')
        lines += ['', '**Candidate or inferred links:**', '']
        for edge in case['candidate_relationships']:
            lines.append(f"- {edge['relation_type']} · {edge['evidence_type']} · {_md_link('source', edge.get('evidence_url'))}; temporal status: {edge['temporal_status']}")
        if not case['candidate_relationships']:
            lines.append('- None observed.')
        lines += ['', f"**Code changes:** {len(case['code_changes'])} commit/file records shown; " + ', '.join(_md_link(_clean(x['summary'], 70), x['url']) for x in case['code_changes'][:5]) + '.', '', f"**Human feedback:** {len(case['human_feedback'])} non-author human discussion/review events shown; " + ', '.join(_md_link(x['event_type'], x.get('source_url')) for x in case['human_feedback'][:5]) + '.', '', f"**Task evolution:** {case['development_evolution']}", '', f"**Historical code evidence:** Base SHA `{case['historical_evidence']['base_sha'] or 'unavailable'}`; current head SHA `{case['historical_evidence']['head_sha_current'] or 'unavailable'}`. Exact commit visibility at an earlier cutoff remains uncertain unless independently supported.", '', '**Evidence limits:** References and shared files alone do not establish a dependency or causal sequence. Current bodies may have changed; commit push timing is often unknown.', '', f"**Future benchmark relevance:** {case['benchmark_relevance_note']}", '']
    return '\n'.join(lines) + '\n'


def generate_reports(builder, aggregate, repository_metrics, patterns, components, cases):
    root = builder.root
    report_dir = root / 'reports'; report_dir.mkdir(exist_ok=True)
    (report_dir / 'case_studies.md').write_text(case_markdown(cases, builder.nodes))
    quality = builder.collection
    random_n = aggregate['random_seed_prs']; random_linked = aggregate['random_seed_prs_with_explicit_issue_link']
    enriched_n = aggregate['enriched_seed_prs']; enriched_linked = aggregate['enriched_seed_prs_with_explicit_issue_link']
    pattern_counts = patterns.groupby('pattern').size().to_dict() if len(patterns) else {}
    selected = pd.read_csv(root / 'results/selected_repositories.csv').fillna('')
    sampled = pd.read_csv(root / 'results/sampled_prs.csv')
    truncated_frames = int(sampled.groupby('repo').frame_truncated.first().sum())
    selected_rows = []
    for row in selected.to_dict('records'):
        name = row['full_name']; m = repository_metrics.get(name, {})
        selected_rows.append(f"| {_md_link(name, 'https://github.com/'+name)} | {m.get('seed_prs',0)} | {m.get('issue_nodes',0)} | {m.get('seed_prs_with_explicit_issue_link',0)} | {m.get('component_counts',{}).get('verified_explicit',0)} |")
    lines = [
        '# GitHub development topology: exploratory pilot', '',
        f"Generated {datetime.now(timezone.utc).isoformat()} from locally cached GitHub API responses. This is a descriptive pilot, not a benchmark or causal study.", '',
        '## 1. Research objectives', '', 'Measure observable Issue–PR links, cross-PR references, connected groups, review structure and historical evidence limits. The questions RQ1–RQ8 in the project brief guide the analysis.', '',
        '## 2. Dataset and sampling methodology', '',
        'The existing 362-repository discovery inventory supplied the frame. The 318 license-verified candidates were eligible for this license-verified pilot. The 44 license-unverified candidates remain local in the prior experiment and were excluded from this collection pending authorization review. Eight repositories were selected with deterministic multi-metric strata (seed 20261106), preferring distinct owners. No language or domain filter was applied.', '',
        f'Per repository, 40 PRs were drawn uniformly from a bounded frame of up to 500 most recent PRs and 40 distinct PRs were prioritized for interaction signals. {truncated_frames}/{len(selected)} repository frames hit the 500-PR cap. Thus random proportions estimate only this recent bounded frame, not all historical PRs; enriched proportions are descriptive only. Expansions are excluded from PR prevalence denominators.', '',
        '## 3. Repository selection', '',
        '| Repository | Collected seed PRs | Issue nodes | Linked seed PRs | Verified components |', '|---|---:|---:|---:|---:|', *selected_rows, '',
        '## 4. GitHub collection methodology', '',
        'Official REST endpoints supplied PR records, issue resources, comments, reviews, review comments, commits, final changed-file lists and timeline events. GraphQL closingIssuesReferences supplied direct closing references. Pagination, persistent HTTP caching, retry/backoff and per-endpoint checkpoints were used. One-hop Issue/PR expansion is capped at 250 additional nodes per repository; boundary nodes preserve out-of-scope references.', '',
        '## 5. Graph schema', '',
        'Nodes are globally keyed by type, repository and number/SHA. Issue and PR numbers remain separate. Directed edges retain relationship type, source URL/ID, observed time where available, verification status and temporal status. COMMIT, REVIEW and FILE nodes are internal PR evidence and excluded from macro topology components.', '',
        '## 6. Relationship definitions', '',
        'Verified explicit: GitHub closing issue metadata and cross-reference timeline events. Derived: PRs sharing a verified Issue. Candidate: current editable text references or shared final-diff files. PR mentions do not prove dependency; temporal ordering and file overlap do not prove causality. Components ignore direction and include only local Issue/PR nodes and the relation subset stated below.', '',
        '## 7. Topology frequency statistics', '',
        f"Collected seed PRs: **{aggregate['seed_prs']}**; selected PRs: **640**; missing complete bundles: **{quality['seed_bundles_missing']}**. Local Issue nodes: **{aggregate['issue_nodes']}**; local PR nodes: **{aggregate['pr_nodes']}**; expanded Issue/PR nodes: **{aggregate['expanded_issue_pr_nodes']}**.", '',
        f"Verified Issue-linked seed PRs: **{_pct(aggregate['seed_prs_with_explicit_issue_link'], aggregate['seed_prs'])}**. Random subset: **{_pct(random_linked, random_n)}**; enriched subset: **{_pct(enriched_linked, enriched_n)}**. No observed explicit Issue link among **{aggregate['seed_prs_without_explicit_issue_link']}** collected seed PRs; this is not proof of independence.", '',
        f"Issues linked to exactly one PR: **{aggregate['issues_linked_to_one_pr']}**; to multiple PRs: **{aggregate['issues_linked_to_multiple_prs']}**. PRs linked to multiple Issues: **{aggregate['prs_linked_to_multiple_issues']}**. Explicit PR–PR pairs: **{aggregate['explicit_pr_pr_pairs']}**. Candidate dependency edges: **{aggregate['possible_pr_dependencies']}**.", '',
        '| Pattern | Observed matches |', '|---|---:|', *[f'| {PATTERN_LABELS[k]} | {v} |' for k,v in sorted(pattern_counts.items())], '',
        'Patterns may overlap, and their counts describe the expanded sample graph, not repository-wide prevalence.', '',
        'Observed independence is limited: a seed PR with no explicit Issue link may still belong to an unobserved task relation. Multi-PR Issues and longer PR-reference paths occur in the sampled graph; their frequencies above are graph counts, not repository population rates. The most frequent pattern below depends on expansion and sampling and is not a causal claim.', '',
        '| Verified seed PR degree | Count |', '|---:|---:|',
        *[f'| {degree} | {count} |' for degree,count in sorted(aggregate['verified_pr_degree_distribution'].items(), key=lambda x:int(x[0]))], '',
        '## 8. Connected component analysis', '',
        '| Scope | Components | Maximum degree | Average degree |', '|---|---:|---:|---:|',
        *[f"| {scope} | {m['connected_components']} | {m['max_degree']} | {m['average_degree']} |" for scope,m in aggregate['graph_scopes'].items()], '',
        'The verified scope uses only explicit Issue–PR, Issue–Issue and PR–PR edges. Derived adds shared-Issue PR edges. Candidate adds text references and shared-file hypotheses. All three are undirected projections for component counting; internal commits/reviews/files and boundary nodes are excluded. Components with one node include isolated PRs.', '',
        '| Creation month | Observed Issue/PR nodes |', '|---|---:|',
        *[f'| {month} | {count} |' for month,count in aggregate['issue_pr_activity_by_month'].items()], '',
        '## 9. Cross-PR relationship analysis', '',
        f"Observed explicit PR–PR pairs: {aggregate['explicit_pr_pr_pairs']} across the collected graph, including cross-repository/boundary references; {sum(v['explicit_pr_pr_pairs'] for v in repository_metrics.values())} are within a selected repository. Sharing an Issue is a derived structural connection, while shared final-diff files are candidate links; neither implies a dependency. PR reference chains are reference paths, not confirmed causal chains.", '',
        '## 10. Human feedback and code-change structure', '',
        f"PRs with at least two non-author human review records: {aggregate['prs_with_multiple_human_review_rounds']}/{aggregate['seed_prs']}. Reviews associated with at least two distinct commit SHAs: {aggregate['prs_with_reviews_on_multiple_commit_versions']}/{aggregate['seed_prs']}. PRs with a timestamped timeline commit event after non-author human feedback: {aggregate['prs_with_observable_feedback_followed_by_commit_event']}/{aggregate['seed_prs']}. Distinct review SHAs do not establish a post-feedback push; commit events provide a narrower observable signal, not causality.", '',
        '## 11. Representative examples', '',
        f"{len(cases)} real cases are documented in [case_studies.md](case_studies.md), with source URLs, graph sketches and chronological events.", '',
        '## 12. Main data-quality limitations', '',
        f"Missing seed bundles: {quality['seed_bundles_missing']}; endpoint failures: {quality['endpoint_errors']}; truncated endpoints: {quality['truncated_endpoints']}; expansion-truncated repositories: {', '.join(quality['truncated_repositories']) or 'none'}. Expanded neighbor endpoint errors: {quality['expanded_neighbor_endpoint_errors']}; unresolved neighbor nodes: {quality['unresolved_expanded_neighbor_nodes']}/{quality['expanded_neighbor_attempts']}; boundary nodes recorded: {quality['boundary_nodes_recorded']}.", '',
        f"Seed bundle completion: {_pct(quality['seed_bundles_found'], quality['seed_bundles_found']+quality['seed_bundles_missing'])}. Macro edges with uncertain observation time or undated evidence: {_pct(aggregate['data_quality_rates']['macro_edges_with_temporal_uncertainty'], aggregate['data_quality_rates']['macro_edge_count'])}.", '',
        'Current Issue and PR descriptions and review text may have been edited. GraphQL closing-reference metadata lacks a link creation time here. Commit author/committer dates are not push times. Cross-repository boundary nodes are not fully crawled. Parent/sub-issue and formal dependency metadata were not comprehensively collected, so those relation counts are lower bounds or unavailable. The bounded recent-PR frame limits prevalence claims. API responses and temporal annotations must be consulted before using any record as historical context.', '',
        '## 13. Implications for future PR sampling', '',
        'Review both random and interaction-enriched PRs. Consider explicit Issue links, cross-reference events, distinct reviewers, and observable revisions as prioritization signals; preserve simple and standalone PRs as baselines. Inspect multi-PR Issue components and reference chains manually before choosing benchmark trajectories.', '',
        '## 14. Implications for historical context reconstruction', '',
        'Prefer timestamped timeline/review events and identifiable commit SHAs. Hide current editable descriptions and undated relationships in historical time slices. No benchmark instance, Agent context, intent ground truth or rubric is created in this study.', '',
    ]
    (report_dir / 'topology_analysis.md').write_text('\n'.join(lines))
