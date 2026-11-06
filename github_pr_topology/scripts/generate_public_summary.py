"""Export aggregate numeric pilot findings without copied GitHub prose or graph records."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'results'


def main() -> None:
    with (RESULTS / 'selected_repositories.csv').open(newline='') as handle:
        selected = list(csv.DictReader(handle))
    if not selected or any(row['processing_track'] != 'license_verified' for row in selected):
        raise ValueError('Public aggregate export requires license-verified seed repositories only')
    metrics = json.loads((RESULTS / 'graph_metrics.json').read_text())['aggregate']
    quality = json.loads((RESULTS / 'collection_quality.json').read_text())
    validation = json.loads((RESULTS / 'validation_summary.json').read_text())
    numeric = lambda source, keys: {key: source[key] for key in keys if isinstance(source.get(key), (int, float))}
    public = {
        'scope': 'Aggregate facts from the bounded topology pilot; no node, edge, PR text, or third-party prose',
        'repository_count': len(selected),
        'seed_sampling': numeric(metrics, [
            'seed_prs', 'random_seed_prs', 'enriched_seed_prs',
            'seed_prs_with_explicit_issue_link', 'seed_prs_without_explicit_issue_link',
            'random_seed_prs_with_explicit_issue_link', 'enriched_seed_prs_with_explicit_issue_link',
        ]),
        'graph_counts': numeric(metrics, [
            'issue_nodes', 'pr_nodes', 'expanded_issue_pr_nodes',
            'issues_linked_to_one_pr', 'issues_linked_to_multiple_prs',
            'prs_linked_to_multiple_issues', 'explicit_pr_pr_pairs',
            'possible_pr_dependencies', 'isolated_seed_prs',
            'prs_with_multiple_human_review_rounds',
            'prs_with_reviews_on_multiple_commit_versions',
            'prs_with_observable_feedback_followed_by_commit_event',
        ]),
        'graph_scopes': {scope: numeric(metrics['graph_scopes'][scope],
            ['connected_components', 'max_degree', 'average_degree'])
            for scope in ('verified_explicit', 'derived', 'candidate')},
        'pattern_counts': {key: value for key, value in metrics['pattern_distribution'].items()
                           if isinstance(value, int)},
        'collection_completeness': {
            **numeric(validation, ['selected_repositories', 'sampled_seed_prs', 'collected_seed_prs',
                                     'graph_nodes', 'graph_edges', 'case_count', 'endpoint_errors']),
            **numeric(quality, ['seed_bundles_missing', 'truncated_endpoints',
                                 'expanded_neighbor_attempts', 'expanded_neighbor_endpoint_errors',
                                 'boundary_nodes_recorded', 'unresolved_expanded_neighbor_nodes']),
            'truncated_repository_count': len(quality['truncated_repositories']),
            'complete_seed_collection': bool(validation['complete_seed_collection']),
        },
        'temporal_uncertainty': numeric(metrics['data_quality_rates'],
            ['macro_edges_with_temporal_uncertainty', 'macro_edge_count',
             'macro_edge_temporal_uncertainty_rate']),
        'limitations': [
            'Random PR prevalence applies only to the newest 500 PRs per repository in the observation window.',
            'Interaction-enriched PRs and expanded neighbors are not an unbiased prevalence sample.',
            'Some neighbor expansion endpoints failed or were truncated.',
            'Current editable text and commit author times do not establish historical visibility.',
            'Aggregate topology patterns may overlap and are not causal claims.',
        ],
    }
    out = RESULTS / 'public_aggregate_statistics.json'
    out.write_text(json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    assert not any(name in out.read_text() for name in validation.get('license_unverified_repository_mentions_local_only', []))
    seed = public['seed_sampling']
    count = public['graph_counts']
    complete = public['collection_completeness']
    pct = lambda a, b: f'{100 * a / b:.1f}%' if b else '—'
    lines = [
        '# GitHub 开发关系拓扑试点：公开汇总', '',
        '本文件只包含聚合计数和研究方法，不包含第三方 Issue/PR 原文、节点、边、案例轨迹或受限仓库名称。详细研究数据仍按 `RELEASE_POLICY.md` 留在本地。', '',
        '## 研究范围', '',
        f'- 从许可证信息已核实的候选清单中分层抽取 {len(selected)} 个仓库。',
        f'- 共采集 {seed["seed_prs"]} 个种子 PR：随机组 {seed["random_seed_prs"]} 个，互动增强组 {seed["enriched_seed_prs"]} 个。',
        '- 随机组的抽样框限于每个仓库观察期内最近 500 个 PR。下述比例不能代表全 GitHub。', '',
        '## 主要结果', '',
        '| 指标 | 观察值 |', '|---|---:|',
        f'| 随机组明确关联 Issue 的种子 PR | {seed["random_seed_prs_with_explicit_issue_link"]} / {seed["random_seed_prs"]}（{pct(seed["random_seed_prs_with_explicit_issue_link"], seed["random_seed_prs"])}） |',
        f'| 互动增强组明确关联 Issue 的种子 PR | {seed["enriched_seed_prs_with_explicit_issue_link"]} / {seed["enriched_seed_prs"]}（{pct(seed["enriched_seed_prs_with_explicit_issue_link"], seed["enriched_seed_prs"])}） |',
        f'| 未观察到明确 Issue 关联的种子 PR | {seed["seed_prs_without_explicit_issue_link"]} / {seed["seed_prs"]} |',
        f'| 扩展关系图中的 Issue/PR 节点 | {count["expanded_issue_pr_nodes"]} |',
        f'| 关联多个 PR 的 Issue | {count["issues_linked_to_multiple_prs"]} |',
        f'| 关联多个 Issue 的 PR | {count["prs_linked_to_multiple_issues"]} |',
        f'| 显式关联的 PR 对 | {count["explicit_pr_pr_pairs"]} |',
        f'| 已核实显式图的连通分量 | {public["graph_scopes"]["verified_explicit"]["connected_components"]} |',
        f'| 生成的本地案例 | {complete["case_count"]}（未公开明细） |', '',
        '## 完整性与限制', '',
        f'- 种子 PR 采集：{complete["collected_seed_prs"]} / {complete["sampled_seed_prs"]}；种子端点错误 {complete["endpoint_errors"]}。',
        f'- 邻居扩展端点错误 {complete["expanded_neighbor_endpoint_errors"]}，未解析邻居节点 {complete["unresolved_expanded_neighbor_nodes"]}，扩展截断仓库 {complete["truncated_repository_count"]}。因此扩展图统计不是完整全量。',
        f'- 宏观关系中时间不确定的边：{public["temporal_uncertainty"]["macro_edges_with_temporal_uncertainty"]} / {public["temporal_uncertainty"]["macro_edge_count"]}。',
        '- 互动增强组不能用于估计自然发生率。未发现明确关联也不能证明任务独立。当前可编辑文本与提交作者时间不能证明某一历史时点的信息可见性。',
        '- 拓扑模式可能重叠；这些结果是描述性观察，不支持因果结论。', '',
        '机器可读数值见 [`results/public_aggregate_statistics.json`](results/public_aggregate_statistics.json)。使用 `python3 scripts/generate_public_summary.py` 可从本地完整结果重新生成。',
    ]
    (ROOT / 'PUBLIC_RESULTS.md').write_text('\n'.join(lines) + '\n')
    print(f'Wrote {out} and {ROOT / "PUBLIC_RESULTS.md"}')


if __name__ == '__main__':
    main()
