/** Only interface labels are translated; original GitHub evidence stays verbatim. */
export const relationLabels: Record<string, string> = {
  ISSUE_RESOLVED_BY_PR: 'PR 解决 Issue',
  ISSUE_REFERENCED_BY_PR: 'PR 引用了 Issue',
  ISSUE_REFERENCES_PR: 'Issue 引用了 PR',
  ISSUE_RELATES_TO_ISSUE: 'Issue 关联 Issue',
  PR_REFERENCES_PR: 'PR 引用了 PR',
  PR_DEPENDS_ON_PR: 'PR 可能依赖 PR',
  PR_PART_OF_SAME_ISSUE: 'PR 共享同一 Issue',
  PR_CONTAINS_COMMIT: 'PR 包含提交',
  PR_HAS_REVIEW: 'PR 收到审查',
  PR_MODIFIES_FILE: 'PR 修改文件',
  PR_REFERENCES_UNKNOWN: 'PR 引用了未知类型节点',
  POTENTIAL_CODE_OVERLAP: '可能修改相同文件',
};
export const evidenceLabels: Record<string, string> = {
  current_pr_text_reference: '当前 PR 文本中的引用',
  derived_shared_verified_issue: '由已核实的共同 Issue 推导',
  graphql_closing_issues: 'GitHub GraphQL 关闭 Issue 关系',
  rest_issue_timeline_cross_reference: 'Issue 时间线交叉引用',
  rest_timeline_cross_reference: 'PR 时间线交叉引用',
  rest_pr_commits: 'GitHub PR 提交列表',
  rest_pr_files_final_diff: 'GitHub PR 最终文件列表',
  rest_pr_reviews: 'GitHub PR 审查记录',
  shared_final_diff_files: '最终差异中的共同文件',
};
export const temporalLabels: Record<string, string> = {
  verified: '时间已核实',
  uncertain: '时间不确定',
  unknown: '时间未知',
  not_push_time: '作者时间不等于推送时间',
  event_time_known_text_history_unverified: '事件时间已知，文本版本未核实',
  commit_visibility_unknown: '提交可见时间未知',
  current_text_edited_possible: '当前文本可能已编辑',
  derived_from_explicit_links: '根据显式关系推导，出现时间未知',
  final_diff_only: '仅代表最终差异',
  overlap_time_unknown: '文件重叠时间未知',
  relationship_creation_unknown: '关系建立时间未知',
};
export const verificationLabels: Record<string, string> = {
  verified: '已核实', derived: '推导关系', candidate: '候选关系', unknown: '未知',
};
export const actorLabels: Record<string, string> = {
  human: '人工参与者', bot: '机器人', unknown: '身份未知',
};
export const eventLabels: Record<string, string> = {
  commit_authored: '提交已创建', discussion_comment: '讨论评论', inline_review_comment: '行内审查评论',
  pr_closed: 'PR 已关闭', pr_merged: 'PR 已合并', pr_opened: 'PR 已创建',
  ready_for_review: '准备接受审查', renamed: '标题已更改', review: '正式审查', review_requested: '请求审查',
};
export const patternLabels: Record<string, string> = {
  A_one_issue_one_pr: 'A：一个 Issue 对应一个 PR',
  B_one_issue_multiple_prs: 'B：一个 Issue 对应多个 PR',
  C_multiple_issues_one_pr: 'C：多个 Issue 对应一个 PR',
  D_explicit_pr_pr_reference: 'D：PR 之间有显式引用',
  E_pr_reference_chain: 'E：PR 引用链',
  F_many_to_many_component: 'F：多对多关系网络',
  G_no_identifiable_issue_link: 'G：未发现明确的 Issue 关联',
  H_shared_files_candidate: 'H：共同文件候选关系',
};
export const labelOrCode = (labels: Record<string, string>, value: string) => labels[value] || value.replaceAll('_', ' ');
export const stratumLabel = (value: unknown) => {
  const match = /^stars([01])_prs([01])_age([01])$/.exec(String(value || ''));
  if (!match) return '抽样仓库';
  return `星标${match[1] === '1' ? '较高' : '较低'} · PR ${match[2] === '1' ? '较多' : '较少'} · 创建${match[3] === '1' ? '较晚' : '较早'}`;
};
