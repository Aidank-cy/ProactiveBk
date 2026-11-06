import { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, ArrowRight, BookOpen, CalendarDays, CheckCircle2, ChevronRight, CircleHelp, Clock3, ExternalLink, FileCode2, Filter, GitCommitHorizontal, GitFork, GitMerge, Layers3, Link2, Moon, Network, Search, ShieldCheck, Sparkles, Sun, Workflow, X } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import GraphCanvas from './GraphCanvas';
import { getJson, url } from './api';
import type { Case, GraphData, GraphEdge, GraphNode, PRDetail, Repo } from './api';
import { actorLabels, eventLabels, evidenceLabels, labelOrCode, patternLabels, relationLabels, stratumLabel, temporalLabels, verificationLabels } from './labels';

type Section = '关系图探索' | '仓库概览' | '拓扑统计' | '案例研究' | '研究方法';
const SECTIONS: Section[] = ['关系图探索', '仓库概览', '拓扑统计', '案例研究', '研究方法'];
const TYPE_OPTIONS = ['ISSUE', 'PULL_REQUEST', 'COMMIT', 'REVIEW', 'FILE', 'BOUNDARY'];
const TYPE_LABEL: Record<string, string> = { ISSUE: '议题', PULL_REQUEST: '拉取请求', COMMIT: '提交', REVIEW: '审查', FILE: '文件', BOUNDARY: '边界节点' };
const RELATION_OPTIONS: Record<string, string | undefined> = {
  '全部关系': undefined,
  'Issue 与 PR': 'ISSUE_RESOLVED_BY_PR,ISSUE_REFERENCED_BY_PR,ISSUE_REFERENCES_PR',
  'PR 与 PR': 'PR_REFERENCES_PR,PR_DEPENDS_ON_PR,PR_PART_OF_SAME_ISSUE',
  '可能的代码重叠': 'POTENTIAL_CODE_OVERLAP',
  'PR 内部证据': 'PR_CONTAINS_COMMIT,PR_HAS_REVIEW,PR_MODIFIES_FILE',
};
const number = (value: unknown) => typeof value === 'number' ? value : Number(value || 0);
const pct = (n: number, d: number) => d ? `${(100 * n / d).toFixed(1)}%` : '—';
const dateLabel = (value?: string) => value ? new Date(value).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' }) : '日期未知';
const short = (value?: string, n = 240) => value ? value.length > n ? `${value.slice(0, n)}…` : value : '暂无文本。';
const caseSummary = (item: Case) => {
  const count = (key: string) => Array.isArray(item[key]) ? (item[key] as unknown[]).length : 0;
  return `关联 ${count('related_issues')} 个 Issue、${count('related_prs')} 个 PR；${count('verified_relationships')} 条已核实关系、${count('candidate_relationships')} 条候选关系。`;
};

function StatCard({ label, value, note, icon: Icon }: { label: string; value: string | number; note?: string; icon: React.ComponentType<{ size?: number }>; }) {
  return <div className="stat-card"><div className="stat-icon"><Icon size={18} /></div><div><span className="stat-label">{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div></div>;
}

function EvidenceList({ edges, nodeId, onSelect }: { edges: GraphEdge[]; nodeId?: string; onSelect?: (id: string) => void; }) {
  if (!edges.length) return <div className="quiet-note">已收集的关系图中暂无关联证据。</div>;
  return <div className="evidence-list">{edges.slice(0, 30).map((edge) => {
    const other = edge.source === nodeId ? edge.target : edge.source;
    return <div className="evidence-row" key={edge.id}>
      <span className={`evidence-mark ${edge.verification_status}`} />
      <div className="evidence-copy"><strong>{labelOrCode(relationLabels, edge.relation_type)}</strong><span>{labelOrCode(verificationLabels, edge.verification_status)} · {labelOrCode(evidenceLabels, edge.evidence_type)}</span><span className="evidence-temporal">时间：{labelOrCode(temporalLabels, edge.temporal_status)}</span>{edge.content && <p>{short(edge.content, 160)}</p>}{nodeId && <button className="text-button" onClick={() => onSelect?.(other)}>{other}<ChevronRight size={13} /></button>}</div>
      {edge.evidence_url && <a className="icon-link" href={edge.evidence_url} target="_blank" rel="noreferrer" aria-label="打开原始证据"><ExternalLink size={15} /></a>}{edge.supporting_urls?.filter((link) => link && link !== edge.evidence_url).map((link) => <a className="icon-link" href={link} key={link} target="_blank" rel="noreferrer" aria-label="打开补充证据"><ExternalLink size={15} /></a>)}
    </div>;
  })}</div>;
}

function Timeline({ detail, onCommit }: { detail: PRDetail; onCommit: (sha: string) => void; }) {
  if (!detail.timeline.length) return <div className="quiet-note">尚未获取到该 PR 的时间线事件。</div>;
  return <div className="timeline">{detail.timeline.map((event, index) => <div className="timeline-item" key={`${event.source_id || index}:${index}`}>
    <div className={`timeline-dot ${event.actor_type === 'bot' ? 'bot' : ''}`} />
    <div className="timeline-body"><div className="timeline-head"><strong>{labelOrCode(eventLabels, event.event_type)}</strong><time>{dateLabel(event.timestamp)}</time></div>
      <div className="timeline-meta">{event.actor || 'GitHub 事件'} · {labelOrCode(actorLabels, event.actor_type)}{event.temporal_status !== 'verified' && <span className="uncertain-tag">{labelOrCode(temporalLabels, event.temporal_status)}</span>}</div>
      {event.content && <p>{short(event.content, 360)}</p>}
      <div className="timeline-actions">{event.commit_sha && <button onClick={() => onCommit(event.commit_sha!)}><GitCommitHorizontal size={13} /> {event.commit_sha.slice(0, 8)}</button>}{event.source_url && <a href={event.source_url} target="_blank" rel="noreferrer">查看证据 <ExternalLink size={12} /></a>}</div>
    </div>
  </div>)}</div>;
}

function DetailPanel({ node, edges, pr, edge, connections, asOf, onSelectNode, onClose }: { node: GraphNode | null; edges: GraphEdge[]; pr: PRDetail | null; edge: GraphEdge | null; connections: number; asOf: string; onSelectNode: (id: string) => void; onClose: () => void; }) {
  const [tab, setTab] = useState<'overview' | 'timeline' | 'evidence'>('overview');
  useEffect(() => setTab('overview'), [node?.id]);
  if (edge) return <aside className="details-panel"><div className="panel-title"><span className="eyebrow">关系证据</span><button aria-label="关闭" onClick={onClose}><X size={16} /></button></div><h2>{labelOrCode(relationLabels, edge.relation_type)}</h2><div className="pill-row"><span className={`status-pill ${edge.verification_status}`}>{labelOrCode(verificationLabels, edge.verification_status)}</span><span className="status-pill neutral">{labelOrCode(temporalLabels, edge.temporal_status)}</span></div><p className="detail-description">{edge.content || '请查看原始来源以了解这条关系。'}</p><div className="detail-section"><span className="eyebrow">来源</span><button className="node-link" onClick={() => onSelectNode(edge.source)}>{edge.source}</button><span className="eyebrow">目标</span><button className="node-link" onClick={() => onSelectNode(edge.target)}>{edge.target}</button></div>{edge.evidence_url && <a className="primary-link" href={edge.evidence_url} target="_blank" rel="noreferrer">打开原始证据 <ExternalLink size={15} /></a>}</aside>;
  if (!node) return <aside className="details-panel details-empty"><div className="empty-orb"><Network size={27} /></div><h2>探索证据</h2><p>选择 Issue 或 PR，查看上下文、关联关系及 GitHub 原始来源。</p><div className="detail-guide"><div><span>01</span> 选择关系图中的节点</div><div><span>02</span> 查看关联证据</div><div><span>03</span> 打开 PR 时间线</div></div></aside>;
  const relatedIssues = pr?.related_nodes.filter((n) => n.type === 'ISSUE') || [];
  const relatedPRs = pr?.related_nodes.filter((n) => n.type === 'PULL_REQUEST') || [];
  const reviews = pr?.related_nodes.filter((n) => n.type === 'REVIEW') || [];
  const commits = pr?.related_nodes.filter((n) => n.type === 'COMMIT') || [];
  const files = pr?.related_nodes.filter((n) => n.type === 'FILE') || [];
  return <aside className="details-panel"><div className="panel-title"><span className="eyebrow">节点详情</span><button aria-label="关闭" onClick={onClose}><X size={16} /></button></div><div className="node-heading"><span className={`node-type-badge ${node.type.toLowerCase()}`}>{TYPE_LABEL[node.type] || node.type}</span><span className="mono">#{node.number}</span></div><h2>{node.title}</h2><div className="detail-meta"><span>{node.repo}</span><span>创建于 {dateLabel(node.created_at)}</span><span>{connections} 条连接</span></div>{node.source_url && <a className="primary-link" href={node.source_url} target="_blank" rel="noreferrer">在 GitHub 打开 <ExternalLink size={15} /></a>}
    {asOf && <div className="time-warning"><Clock3 size={15} /> 历史视图会隐藏当前可编辑文本和无日期的关系。</div>}
    <div className="detail-tabs"><button className={tab === 'overview' ? 'active' : ''} onClick={() => setTab('overview')}>概览</button><button className={tab === 'timeline' ? 'active' : ''} disabled={!pr} onClick={() => setTab('timeline')}>时间线</button><button className={tab === 'evidence' ? 'active' : ''} onClick={() => setTab('evidence')}>证据</button></div>
    {tab === 'overview' && <div className="detail-scroll"><div className="detail-section"><span className="eyebrow">描述</span><p className="detail-description">{node.description ? short(node.description, 900) : asOf ? '历史视图中已隐藏当前文本。' : '暂无描述。'}</p></div>{pr && <><div className="mini-metrics"><div><strong>{relatedIssues.length}</strong><span>议题</span></div><div><strong>{relatedPRs.length}</strong><span>相关 PR</span></div><div><strong>{reviews.length}</strong><span>审查</span></div><div><strong>{commits.length}</strong><span>提交</span></div></div><div className="detail-section"><span className="eyebrow">相关 Issue 与 PR</span>{[...relatedIssues, ...relatedPRs].slice(0, 18).map((n) => <button className="related-node" key={n.id} onClick={() => onSelectNode(n.id)}><span className={`mini-dot ${n.type.toLowerCase()}`} /><span>{short(n.title, 52)}</span><ChevronRight size={14} /></button>)}{!relatedIssues.length && !relatedPRs.length && <p className="quiet-note">收集到的关系图中未发现明确关联的节点。</p>}</div><div className="detail-section"><span className="eyebrow">人工审查与代码</span><p className="quiet-note">{reviews.filter((n) => n.metadata?.actor_type === 'human').length} 条人工审查记录 · {commits.length} 个关联提交 · 当前 PR 差异涉及 {files.length} 个文件。</p>{files.slice(0, 8).map((n) => <div className="file-row" key={n.id}><FileCode2 size={13} /> {n.title}</div>)}</div></>}</div>}
    {tab === 'timeline' && pr && <div className="detail-scroll"><div className="time-warning"><Clock3 size={15} /> 提交作者时间不等于推送时间；可编辑文本可能在事件发生后发生变化。</div><Timeline detail={pr} onCommit={(sha) => onSelectNode(`commit:${node.repo}#${sha}`)} /></div>}
    {tab === 'evidence' && <div className="detail-scroll"><EvidenceList edges={edges} nodeId={node.id} onSelect={onSelectNode} /></div>}
  </aside>;
}

function Charts({ stats, repo }: { stats: any; repo: string; }) {
  const aggregate = stats?.aggregate || {};
  const current = stats?.repositories?.[repo] || {};
  const relationRows = Object.entries(aggregate.relationship_type_distribution || {}).map(([name, value]) => ({ name: labelOrCode(relationLabels, name), count: number(value) })).sort((a, b) => b.count - a.count).slice(0, 12);
  const sizeRows = Object.entries(aggregate.graph_scopes?.verified_explicit?.component_size_distribution || {}).map(([size, count]) => ({ size, count: number(count) })).sort((a, b) => number(a.size) - number(b.size)).slice(0, 18);
  const patternRows = Object.entries(aggregate.pattern_distribution || {}).map(([name, value]) => ({ name: name.slice(0, 1), count: number(value) })).sort((a, b) => a.name.localeCompare(b.name));
  const degreeRows = Object.entries(aggregate.verified_pr_degree_distribution || {}).map(([degree, value]) => ({ degree, count: number(value) })).sort((a, b) => number(a.degree) - number(b.degree)).slice(0, 16);
  const activityRows = Object.entries(aggregate.issue_pr_activity_by_month || {}).map(([month, value]) => ({ month, count: number(value) })).slice(-18);
  const comparison = Object.entries(stats?.repositories || {}).map(([name, value]) => ({ name: name.split('/')[1], linked: number((value as any).seed_prs_with_explicit_issue_link), seed: number((value as any).seed_prs), components: number((value as any).component_counts?.verified_explicit) }));
  return <section className="page-content"><div className="page-heading"><div><span className="eyebrow">结构分析</span><h1>拓扑统计</h1><p>分别统计已核实、推导和候选关系，避免混淆不同证据层级。</p></div><span className="data-badge"><CheckCircle2 size={15} /> 可追溯的统计指标</span></div><div className="stat-grid four"><StatCard label="种子 PR" value={number(aggregate.seed_prs)} note="随机抽样 + 互动增强抽样" icon={GitMerge} /><StatCard label="Issue 节点" value={number(aggregate.issue_nodes)} note="扩展关系图" icon={CircleHelp} /><StatCard label="明确关联" value={pct(number(aggregate.seed_prs_with_explicit_issue_link), number(aggregate.seed_prs))} note={`${number(aggregate.seed_prs_with_explicit_issue_link)} / ${number(aggregate.seed_prs)} 个种子 PR`} icon={Link2} /><StatCard label="连通分量" value={number(aggregate.graph_scopes?.verified_explicit?.connected_components)} note="忽略方向" icon={Layers3} /></div><div className="chart-grid"><div className="chart-card"><div className="card-heading"><h3>关系类型</h3><p>包含 PR 内部证据在内的全部关系类型。</p></div><div className="chart-box"><ResponsiveContainer width="100%" height="100%"><BarChart data={relationRows} layout="vertical" margin={{ left: 0, right: 25, top: 8, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e6eaf0" /><XAxis type="number" tickLine={false} axisLine={false} /><YAxis dataKey="name" type="category" width={180} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} /><Tooltip /><Bar isAnimationActive={false} dataKey="count" name="数量" fill="#168b84" radius={[0, 4, 4, 0]} /></BarChart></ResponsiveContainer></div></div><div className="chart-card"><div className="card-heading"><h3>连通分量规模</h3><p>已核实的 Issue 与 PR 关系图，包含孤立节点。</p></div><div className="chart-box"><ResponsiveContainer width="100%" height="100%"><BarChart data={sizeRows}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e6eaf0" /><XAxis dataKey="size" tickLine={false} axisLine={false} /><YAxis tickLine={false} axisLine={false} /><Tooltip /><Bar isAnimationActive={false} dataKey="count" name="数量" fill="#4774c7" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></div><div className="chart-card wide"><div className="card-heading"><h3>仓库对比</h3><p>观察到 Issue 关联的种子 PR；互动增强样本仅供描述。</p></div><div className="chart-box"><ResponsiveContainer width="100%" height="100%"><BarChart data={comparison}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e6eaf0" /><XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-18} textAnchor="end" height={52} /><YAxis tickLine={false} axisLine={false} /><Tooltip /><Legend /><Bar isAnimationActive={false} dataKey="linked" name="已关联 Issue 的种子 PR" fill="#168b84" radius={[4, 4, 0, 0]} /><Bar isAnimationActive={false} dataKey="seed" name="全部种子 PR" fill="#cbd9e6" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></div></div><div className="chart-grid"><div className="chart-card"><div className="card-heading"><h3>拓扑模式</h3><p>模式 A 至 H 可能重叠；计数基于扩展关系图。</p></div><div className="chart-box"><ResponsiveContainer width="100%" height="100%"><BarChart data={patternRows}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e6eaf0" /><XAxis dataKey="name" /><YAxis /><Tooltip /><Bar isAnimationActive={false} dataKey="count" name="数量" fill="#6e86b5" radius={[4,4,0,0]} /></BarChart></ResponsiveContainer></div></div><div className="chart-card"><div className="card-heading"><h3>种子 PR 度数</h3><p>已核实的 Issue 与 PR 关系图，包含度数为零的节点。</p></div><div className="chart-box"><ResponsiveContainer width="100%" height="100%"><BarChart data={degreeRows}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e6eaf0" /><XAxis dataKey="degree" /><YAxis /><Tooltip /><Bar isAnimationActive={false} dataKey="count" name="数量" fill="#c68c55" radius={[4,4,0,0]} /></BarChart></ResponsiveContainer></div></div><div className="chart-card wide"><div className="card-heading"><h3>Issue 与 PR 月度创建量</h3><p>收集到的关系图中创建时间已知的记录。</p></div><div className="chart-box"><ResponsiveContainer width="100%" height="100%"><BarChart data={activityRows}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e6eaf0" /><XAxis dataKey="month" tick={{fontSize:9}} angle={-35} textAnchor="end" height={60} /><YAxis /><Tooltip /><Bar isAnimationActive={false} dataKey="count" name="数量" fill="#168b84" radius={[4,4,0,0]} /></BarChart></ResponsiveContainer></div></div></div><div className="method-note"><ShieldCheck size={18} /><div><strong>结果解读范围</strong><p>随机 PR 的比例只使用各仓库随机样本作为分母。未发现明确关联，不能据此断定开发任务彼此独立。</p></div></div>{current.seed_prs !== undefined && <div className="chart-card compact"><h3>{repo}</h3><p>{number(current.seed_prs)} 个种子 PR · {number(current.expanded_issue_pr_nodes)} 个扩展 Issue/PR 节点 · {number(current.issues_linked_to_multiple_prs)} 个 Issue 关联多个 PR。</p></div>}</section>;
}

export default function App() {
  const [section, setSection] = useState<Section>('关系图探索');
  const [repos, setRepos] = useState<Repo[]>([]);
  const [repo, setRepo] = useState('');
  const [stats, setStats] = useState<any>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [components, setComponents] = useState<any[]>([]);
  const [componentId, setComponentId] = useState('');
  const [mode, setMode] = useState<'overview' | 'focused'>('focused');
  const [focusId, setFocusId] = useState('');
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [nodeTypes, setNodeTypes] = useState(['ISSUE', 'PULL_REQUEST', 'BOUNDARY']);
  const [verifiedOnly, setVerifiedOnly] = useState(true);
  const [showCandidates, setShowCandidates] = useState(false);
  const [relationGroup, setRelationGroup] = useState('全部关系');
  const [samplingGroup, setSamplingGroup] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [asOf, setAsOf] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdges, setSelectedEdges] = useState<GraphEdge[]>([]);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [prDetail, setPrDetail] = useState<PRDetail | null>(null);
  const [connections, setConnections] = useState(0);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const scope = verifiedOnly ? 'verified_explicit' : showCandidates ? 'candidate' : 'derived';

  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  useEffect(() => { if (asOf) { setComponentId(''); setMode('overview'); } }, [asOf]);
  useEffect(() => { const timer = setTimeout(() => setSearch(searchInput.trim()), 300); return () => clearTimeout(timer); }, [searchInput]);
  useEffect(() => {
    getJson<Repo[]>('/api/repositories').then((items) => { setRepos(items); if (items.length) setRepo(items.find((item) => number(item.metrics?.seed_prs) > 0)?.full_name || items[0].full_name); }).catch((e) => setError(`仓库数据不可用： ${e.message}`));
    getJson<any>('/api/statistics').then(setStats).catch(() => undefined);
    getJson<{ items: Case[] }>('/api/cases').then((data) => setCases(data.items)).catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!repo) return;
    getJson<{ items: any[] }>(url('/api/components', { repo, scope: 'verified_explicit', limit: 100 })).then((response) => {
      setComponents(response.items);
      if (!focusId && !asOf) setComponentId(response.items.find((c) => c.size > 1)?.component_id || '');
    }).catch(() => setComponents([]));
  }, [repo, focusId, asOf]);
  useEffect(() => {
    if (!repo || section !== '关系图探索') return;
    let cancelled = false;
    setGraphLoading(true);
    const route = url('/api/graph', { repo, scope, component_id: mode === 'focused' ? componentId || undefined : undefined, mode, as_of: asOf || undefined, since: fromDate || undefined, node_types: nodeTypes.join(','), relation_types: RELATION_OPTIONS[relationGroup], sampling_group: samplingGroup || undefined, search: search || undefined, focus_id: focusId || undefined, limit: 180 });
    getJson<GraphData>(route).then((result) => { if (!cancelled) { setGraphData(result); setError(''); } }).catch((e) => { if (!cancelled) setError(`关系图请求失败： ${e.message}`); }).finally(() => { if (!cancelled) setGraphLoading(false); });
    return () => { cancelled = true; };
  }, [repo, scope, componentId, mode, asOf, fromDate, nodeTypes, relationGroup, samplingGroup, search, focusId, section]);
  useEffect(() => {
    if (!selectedId) { setSelectedNode(null); setSelectedEdges([]); setPrDetail(null); return; }
    let cancelled = false;
    setSelectedNode(null);
    setSelectedEdges([]);
    setPrDetail(null);
    getJson<{ node: GraphNode; edges: GraphEdge[]; connections: number }>(url(`/api/nodes/${encodeURIComponent(selectedId)}`, { as_of: asOf || undefined })).then((result) => {
      if (cancelled) return;
      setSelectedNode(result.node); setSelectedEdges(result.edges); setConnections(result.connections);
      if (result.node.type === 'PULL_REQUEST') {
        getJson<PRDetail>(url(`/api/pr/${result.node.repo}/${result.node.number}`, { as_of: asOf || undefined })).then((detail) => { if (!cancelled) setPrDetail(detail); }).catch(() => { if (!cancelled) setPrDetail(null); });
      } else setPrDetail(null);
    }).catch(() => { if (!cancelled) { setSelectedNode(null); setPrDetail(null); } });
    return () => { cancelled = true; };
  }, [selectedId, asOf]);

  const onSelectNode = useCallback((id: string) => { setSelectedId(id); setSelectedEdge(null); }, []);
  const onSelectEdge = useCallback((edge: GraphEdge) => { setSelectedEdge(edge); setSelectedId(null); }, []);
  const onExpand = useCallback(() => {
    if (!selectedId) return;
    getJson<{ nodes: GraphNode[]; edges: GraphEdge[] }>(url('/api/graph/neighbors', { node_id: selectedId, depth: 1, scope, as_of: asOf || undefined })).then((extra) => setGraphData((current) => {
      if (!current) return current;
      const nodes = new Map([...current.nodes, ...extra.nodes].map((n) => [n.id, n]));
      const edges = new Map([...current.edges, ...extra.edges].map((e) => [e.id, e]));
      return { ...current, nodes: [...nodes.values()], edges: [...edges.values()], rendered_nodes: nodes.size, rendered_edges: edges.size };
    })).catch((e) => setError(e.message));
  }, [selectedId, scope, asOf]);
  const chooseRepo = (name: string) => { setRepo(name); setSelectedId(null); setSelectedEdge(null); setFocusId(''); setComponentId(''); setMode(asOf ? 'overview' : 'focused'); };
  const openCase = (item: Case) => { setSection('关系图探索'); setRepo(item.repo); setFocusId(item.anchor_pr_id); setComponentId(''); setMode('focused'); setSelectedId(item.anchor_pr_id); setSelectedEdge(null); setAsOf(''); };
  const toggleType = (type: string) => setNodeTypes((current) => current.includes(type) ? current.filter((x) => x !== type) : [...current, type]);
  const currentRepo = repos.find((r) => r.full_name === repo);
  const currentMetrics = stats?.repositories?.[repo] || {};
  const caseCounts = useMemo(() => Object.entries(cases.reduce<Record<string, number>>((acc, item) => { item.patterns?.forEach((p) => acc[p] = (acc[p] || 0) + 1); return acc; }, {})).sort((a, b) => b[1] - a[1]), [cases]);

  return <div className="app-shell"><header className="topbar"><div className="brand"><div className="brand-mark"><Workflow size={21} strokeWidth={2.2} /></div><div><strong>GitHub 开发关系图谱探索器</strong><span>主动编码智能体基准研究</span></div></div><nav className="topnav">{SECTIONS.map((item) => <button key={item} className={section === item ? 'active' : ''} onClick={() => setSection(item)}>{item}</button>)}</nav><div className="topbar-right"><span className="research-pill"><span className="live-dot" /> 试点研究</span><button className="theme-button" title="切换配色主题" aria-label="切换配色主题" onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>{theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}</button></div></header>
    {error && <div className="error-banner"><CircleHelp size={16} /> {error}<button onClick={() => setError('')}><X size={16} /></button></div>}
    {section === '关系图探索' && <main className="explorer"><aside className="controls-panel"><div className="controls-intro"><span className="eyebrow">探索工作台</span><h1>探索开发任务如何关联</h1><p>查看 Issue、PR 与代码审查之间的证据。</p></div><div className="control-scroll"><div className="control-group"><label htmlFor="repo-select">仓库</label><select id="repo-select" value={repo} onChange={(e) => chooseRepo(e.target.value)}>{repos.map((item) => <option key={item.full_name} value={item.full_name}>{item.full_name}</option>)}</select>{currentRepo && <div className="repo-footnote"><span><Sparkles size={13} /> {number(currentRepo.stars).toLocaleString()} 星标</span><span><GitFork size={13} /> {number(currentRepo.forks).toLocaleString()} Fork</span></div>}</div><div className="control-group"><label htmlFor="graph-search">查找任务</label><div className="search-field"><Search size={16} /><input id="graph-search" placeholder="输入 Issue / PR 编号或标题" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} />{searchInput && <button onClick={() => setSearchInput('')} aria-label="清除搜索"><X size={14} /></button>}</div></div><div className="control-group"><div className="control-label-row"><label>关系图视图</label><Filter size={14} /></div><div className="segmented"><button className={mode === 'focused' ? 'active' : ''} onClick={() => { setMode('focused'); setFocusId(''); setComponentId(components.find((c) => c.size > 1)?.component_id || ''); }}>聚焦</button><button className={mode === 'overview' ? 'active' : ''} onClick={() => { setMode('overview'); setComponentId(''); setFocusId(''); }}>概览</button></div>{mode === 'focused' && !asOf && <select aria-label="连通分量" value={componentId} onChange={(e) => { setComponentId(e.target.value); setFocusId(''); }}><option value="">全部可见节点</option>{components.filter((c) => c.size > 1).slice(0, 40).map((c) => <option key={c.component_id} value={c.component_id}>分量 {c.component_id.split(':').at(-1)} · {c.size} 个节点</option>)}</select>}</div><div className="control-group"><label>节点类型</label><div className="type-pills">{TYPE_OPTIONS.map((type) => <button key={type} className={nodeTypes.includes(type) ? 'on' : ''} onClick={() => toggleType(type)}><span className={`mini-dot ${type.toLowerCase()}`} /> {TYPE_LABEL[type]}</button>)}</div></div><div className="control-group"><label htmlFor="relation-select">关系类型</label><select id="relation-select" value={relationGroup} onChange={(e) => setRelationGroup(e.target.value)}>{Object.keys(RELATION_OPTIONS).map((value) => <option key={value}>{value}</option>)}</select><div className="toggle-row"><span>仅显示已核实关系</span><input type="checkbox" checked={verifiedOnly} onChange={(e) => setVerifiedOnly(e.target.checked)} /></div><div className="toggle-row"><span>显示候选关系</span><input type="checkbox" checked={showCandidates} disabled={verifiedOnly} onChange={(e) => setShowCandidates(e.target.checked)} /></div></div><div className="control-group"><label htmlFor="sample-group">抽样分组</label><select id="sample-group" value={samplingGroup} onChange={(e) => setSamplingGroup(e.target.value)}><option value="">全部种子 PR</option><option value="random">随机基线样本</option><option value="interaction_enriched">互动增强样本</option></select></div><div className="control-group"><label>时间范围与历史快照</label><div className="date-stack"><span>起始日期 <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} /></span><span>截至日期 <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></span></div>{asOf && <button className="clear-link" onClick={() => setAsOf('')}>清除历史快照</button>}</div></div><div className="controls-footer"><ShieldCheck size={15} /> 已核实、推导和候选关系分别呈现。</div></aside>
      <div className="workspace-main"><div className="workspace-head"><div><span className="eyebrow">当前仓库</span><h2>{repo || '请选择仓库'}</h2><p>从开发需求到代码审查，每条关系都有来源可查。</p></div><span className="frame-chip">{graphLoading ? '正在加载关系图…' : mode === 'focused' ? '聚焦分量' : '仓库概览'}</span></div>{!asOf && <div className="stat-grid"><StatCard label="种子 PR" value={number(currentMetrics.seed_prs)} note="40 个随机样本 + 40 个互动增强样本" icon={GitMerge} /><StatCard label="Issue 节点" value={number(currentMetrics.issue_nodes)} note="扩展的相邻节点" icon={CircleHelp} /><StatCard label="明确关联" value={number(currentMetrics.seed_prs_with_explicit_issue_link)} note={`${pct(number(currentMetrics.seed_prs_with_explicit_issue_link), number(currentMetrics.seed_prs))}，基于种子 PR`} icon={Link2} /><StatCard label="连通分量" value={number(currentMetrics.component_counts?.verified_explicit)} note="已核实关系图" icon={Layers3} /></div>}{graphData?.time_slice_note && <div className="time-banner"><CalendarDays size={16} /> 历史快照仅显示截至所选日期可确认存在的事件与关系；可编辑文本及时间未核实的证据已隐藏。</div>}{graphData?.truncated_for_display && <div className="graph-notice"><Activity size={14} /> 显示匹配的 {graphData.total_matching_nodes} 个节点中的 {graphData.rendered_nodes} 个。请选择连通分量或搜索以缩小范围。</div>}<GraphCanvas data={graphData} selectedId={selectedId} onSelectNode={onSelectNode} onSelectEdge={onSelectEdge} onExpand={onExpand} /></div>
      <DetailPanel node={selectedNode} edges={selectedEdges} pr={prDetail} edge={selectedEdge} connections={connections} asOf={asOf} onSelectNode={onSelectNode} onClose={() => { setSelectedId(null); setSelectedEdge(null); }} /></main>}
    {section === '仓库概览' && <section className="page-content"><div className="page-heading"><div><span className="eyebrow">试点仓库</span><h1>仓库概览</h1><p>从已核实许可证的候选仓库中，按固定随机种子抽取 8 个仓库。</p></div><span className="data-badge"><GitFork size={15} /> 已选 {repos.length} 个</span></div><div className="overview-grid">{repos.map((item) => <button className="repo-card" key={item.full_name} onClick={() => { chooseRepo(item.full_name); setSection('关系图探索'); }}><span className="eyebrow">{stratumLabel(item.target_stratum)}</span><h3>{item.full_name}</h3><p>创建于 {dateLabel(item.created_at)}</p><div className="repo-stats"><span>{number(item.stars).toLocaleString()} 星标</span><span>{number(item.total_pull_requests).toLocaleString()} 个 PR</span><span>{number(item.total_issues).toLocaleString()} 个 Issue</span></div><span className="open-card">探索关系图 <ArrowRight size={15} /></span></button>)}</div><div className="method-note"><ShieldCheck size={18} /><div><strong>抽样与发布</strong><p>仓库标识、星标、PR 数、Issue 数、创建时间与活跃度用于确定性分层。44 个许可证状态未核实的候选仓库暂不纳入公开试点，待授权核查。</p></div></div></section>}
    {section === '拓扑统计' && <Charts stats={stats} repo={repo} />}
    {section === '案例研究' && <section className="page-content"><div className="page-heading"><div><span className="eyebrow">真实开发轨迹</span><h1>代表性案例</h1><p>案例展示观察到的完整开发轨迹，包括后续事件。打开案例会清除历史快照并聚焦相关子图。</p></div><span className="data-badge"><BookOpen size={15} /> {cases.length} 个案例</span></div><div className="case-summary">{caseCounts.slice(0, 6).map(([name, count]) => <span key={name}>{labelOrCode(patternLabels, name)} <strong>{count}</strong></span>)}</div>{cases.length ? <div className="case-grid">{cases.map((item) => <button className="case-card" key={item.case_id} onClick={() => openCase(item)}><span className="case-number">{item.case_id}</span><span className="eyebrow">{item.repo}</span><h3>{item.title}</h3><p>{caseSummary(item)}</p><div className="case-tags">{item.patterns?.slice(0, 2).map((p) => <span key={p}>{labelOrCode(patternLabels, p)}</span>)}</div><span className="open-card">打开子图 <ArrowRight size={15} /></span></button>)}</div> : <div className="page-empty"><BookOpen size={34} /><h2>案例正在生成</h2><p>真实数据采集完成后，这里将显示有证据支持的案例。</p></div>}</section>}
    {section === '研究方法' && <section className="page-content methodology"><div className="page-heading"><div><span className="eyebrow">研究设计</span><h1>研究方法</h1><p>试点研究如何区分观察证据、图结构和假设。</p></div></div><div className="method-grid"><article><span className="method-index">01</span><h3>仓库与 PR 抽样</h3><p>从许可证已核实的仓库清单中，按确定性平衡分层选取 8 个仓库。每个仓库在限定的近期范围内抽取 40 个随机 PR 和 40 个互动增强 PR。随机组比例只使用随机组分母。</p></article><article><span className="method-index">02</span><h3>证据等级</h3><p>已核实关系来自 GitHub 关系元数据或带时间戳的时间线事件。推导关系来自已核实的图路径，例如两个 PR 关联同一个 Issue。候选关系来自当前文本或共同文件，不计为已确认的依赖。</p></article><article><span className="method-index">03</span><h3>一跳扩展</h3><p>每个仓库最多扩展 250 个节点，从种子 PR 获取直接关联的 Issue、被引用的 PR，以及同一 Issue 关联的其他 PR。跨仓库引用保留为边界节点，并记录截断情况。</p></article><article><span className="method-index">04</span><h3>历史可见性</h3><p>历史快照会隐藏当前可编辑描述、无日期关系、可见时间未核实的提交，以及最终文件差异。提交作者时间不能证明推送时间，事件文本也可能被编辑。</p></article><article><span className="method-index">05</span><h3>关系图指标</h3><p>连通分量忽略边的方向，仅使用 Issue 和 PR 节点。分别比较已核实、结构推导及包含候选关系的图。孤立种子 PR 仍计入分母。</p></article><article><span className="method-index">06</span><h3>发布边界</h3><p>本地候选清单包含 44 个许可证状态未核实的仓库。此前端不包含其复制代码或衍生数据。公开发布相关仓库研究材料前需完成授权审查。</p></article></div><div className="method-note"><ShieldCheck size={18} /><div><strong>研究范围</strong><p>此界面用于研究真实 GitHub 开发关系，不构造基准实例、不推断意图真值，也不评估智能体。</p></div></div></section>}
    <footer className="app-footer"><span>GitHub 开发关系图谱探索器 · 探索性研究</span><span>研究中的原始 GitHub 证据均保留来源链接。</span></footer>
  </div>;
}
