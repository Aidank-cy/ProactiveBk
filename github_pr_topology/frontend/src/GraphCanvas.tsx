import { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import { Download, Expand, Focus, GitBranch, Minus, Plus, RotateCcw, Route } from 'lucide-react';
import type { GraphData, GraphEdge } from './api';

type Props = {
  data: GraphData | null;
  selectedId: string | null;
  onSelectNode: (id: string) => void;
  onSelectEdge: (edge: GraphEdge) => void;
  onExpand: () => void;
};

const colors: Record<string, string> = {
  ISSUE: '#4774c7', PULL_REQUEST: '#168b84', COMMIT: '#65707d',
  REVIEW: '#cf9036', FILE: '#8290a6', BOUNDARY: '#a5aab5',
};

export default function GraphCanvas({ data, selectedId, onSelectNode, onSelectEdge, onExpand }: Props) {
  const mount = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const pathPick = useRef(false);
  const pathStart = useRef<string | null>(null);
  const [layout, setLayout] = useState('cose');
  const [pathLabel, setPathLabel] = useState('查找路径');
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);

  useEffect(() => {
    if (!mount.current || !data) return;
    const elements: cytoscape.ElementDefinition[] = [
      ...data.nodes.map((node) => ({ data: { id: node.id, label: `${node.type === 'ISSUE' ? '议题' : node.type === 'PULL_REQUEST' ? 'PR' : node.type === 'COMMIT' ? '提交' : node.type === 'REVIEW' ? '审查' : '节点'} #${node.number}`.slice(0, 28), kind: node.type, seed: node.seed ? 'yes' : 'no', boundary: node.boundary ? 'yes' : 'no', title: node.title } })),
      ...data.edges.map((edge) => ({ data: { id: edge.id, source: edge.source, target: edge.target, relation: edge.relation_type, verification: edge.verification_status } })),
    ];
    const cy = cytoscape({
      container: mount.current,
      elements,
      style: [
        { selector: 'node', style: { 'background-color': '#8290a6', 'width': 22, 'height': 22, 'label': 'data(label)', 'font-family': 'Noto Sans CJK SC, PingFang SC, Microsoft YaHei, sans-serif', 'font-size': 10, 'color': '#263449', 'text-valign': 'bottom', 'text-margin-y': 7, 'text-background-color': '#ffffff', 'text-background-opacity': 0.86, 'text-background-padding': '2px', 'text-wrap': 'ellipsis', 'text-max-width': '115px', 'border-width': 2, 'border-color': '#ffffff', 'overlay-opacity': 0 } },
        ...Object.entries(colors).map(([kind, color]) => ({ selector: `node[kind = "${kind}"]`, style: { 'background-color': color } })),
        { selector: 'node[kind = "PULL_REQUEST"]', style: { shape: 'round-rectangle', width: 26, height: 21 } },
        { selector: 'node[kind = "COMMIT"]', style: { shape: 'diamond' } },
        { selector: 'node[kind = "REVIEW"]', style: { shape: 'hexagon' } },
        { selector: 'node[kind = "FILE"]', style: { shape: 'rectangle' } },
        { selector: 'node[boundary = "yes"]', style: { 'border-width': 2, 'border-style': 'dashed', 'border-color': '#596473' } },
        { selector: 'edge', style: { width: 1.5, 'line-color': '#a6b4c7', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#a6b4c7', 'arrow-scale': 0.65, 'curve-style': 'bezier', 'opacity': 0.82 } },
        { selector: 'edge[verification = "candidate"]', style: { 'line-style': 'dashed', 'line-color': '#b5a06a', 'target-arrow-color': '#b5a06a', opacity: 0.7 } },
        { selector: 'edge[verification = "derived"]', style: { 'line-style': 'dotted', 'line-color': '#8592a5', 'target-arrow-color': '#8592a5' } },
        { selector: '.dimmed', style: { opacity: 0.12 } },
        { selector: 'node.selected', style: { 'border-width': 4, 'border-color': '#ffce7a', 'z-index': 99 } },
        { selector: '.path', style: { 'line-color': '#e8843d', 'target-arrow-color': '#e8843d', 'background-color': '#e8843d', width: 4, opacity: 1, 'z-index': 90 } },
        { selector: 'node.compact', style: { 'label': '' } },
      ] as any,
      layout: { name: layout, animate: false, padding: 42 } as any,
      wheelSensitivity: 0.22,
      minZoom: 0.18,
      maxZoom: 3,
    });
    cyRef.current = cy;
    if (import.meta.env.DEV) (window as Window & { __topologyCy?: cytoscape.Core }).__topologyCy = cy;
    const updateCompact = () => cy.nodes().toggleClass('compact', cy.zoom() < 0.7);
    cy.on('zoom', updateCompact);
    cy.on('tap', 'node', (event) => {
      const node = event.target;
      const id = node.id();
      onSelectNode(id);
      if (pathPick.current) {
        if (!pathStart.current) {
          pathStart.current = id;
          setPathLabel('选择终点');
        } else {
          cy.elements().removeClass('path');
          const route = cy.elements().aStar({ root: cy.getElementById(pathStart.current), goal: node, directed: false });
          if (route.found) { route.path.addClass('path'); setPathLabel(`${route.distance} 步`); }
          else setPathLabel('未找到路径');
          pathPick.current = false;
          pathStart.current = null;
        }
      }
    });
    cy.on('tap', 'edge', (event) => {
      const hit = data.edges.find((edge) => edge.id === event.target.id());
      if (hit) onSelectEdge(hit);
    });
    cy.on('mouseover', 'node', (event) => {
      const node = event.target;
      const neighborhood = node.closedNeighborhood();
      cy.elements().not(neighborhood).addClass('dimmed');
      const position = event.renderedPosition || node.renderedPosition();
      setTip({ x: position.x + 18, y: position.y - 12, text: node.data('title') });
    });
    cy.on('mouseout', 'node', () => { cy.elements().removeClass('dimmed'); setTip(null); });
    cy.on('tap', (event) => { if (event.target === cy) setTip(null); });
    cy.ready(() => { cy.fit(undefined, 45); updateCompact(); });
    return () => { cy.stop(true); cy.destroy(); cyRef.current = null; if (import.meta.env.DEV) delete (window as Window & { __topologyCy?: cytoscape.Core }).__topologyCy; };
  }, [data, layout, onSelectNode, onSelectEdge]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().removeClass('selected');
    if (selectedId) cy.getElementById(selectedId).addClass('selected');
  }, [selectedId, data]);

  const fit = () => cyRef.current?.fit(undefined, 45);
  const download = () => {
    const cy = cyRef.current;
    if (!cy) return;
    const link = document.createElement('a');
    link.href = cy.png({ full: true, scale: 2, bg: '#ffffff' });
    link.download = '开发关系图.png';
    link.click();
  };
  const reset = () => { cyRef.current?.elements().removeClass('path dimmed'); cyRef.current?.layout({ name: layout, animate: false, padding: 42 } as any).run(); fit(); setPathLabel('查找路径'); pathPick.current = false; pathStart.current = null; };

  return <div className="graph-shell">
    <div className="graph-toolbar">
      <div className="toolbar-group"><span className="eyebrow">开发关系图</span><span className="toolbar-count">{data ? `${data.rendered_nodes} 个节点 · ${data.rendered_edges} 条关系` : '尚未加载关系图'}</span></div>
      <div className="toolbar-actions">
        <select aria-label="关系图布局" value={layout} onChange={(e) => setLayout(e.target.value)}><option value="cose">自然布局</option><option value="breadthfirst">层级布局</option><option value="circle">环形布局</option><option value="grid">网格布局</option></select>
        <button title="放大" aria-label="放大" onClick={() => cyRef.current?.zoom({ level: (cyRef.current?.zoom() || 1) * 1.25, renderedPosition: { x: (mount.current?.clientWidth || 0) / 2, y: (mount.current?.clientHeight || 0) / 2 } })}><Plus size={16} /></button>
        <button title="缩小" aria-label="缩小" onClick={() => cyRef.current?.zoom({ level: (cyRef.current?.zoom() || 1) / 1.25, renderedPosition: { x: (mount.current?.clientWidth || 0) / 2, y: (mount.current?.clientHeight || 0) / 2 } })}><Minus size={16} /></button>
        <button title="适应视图" aria-label="适应视图" onClick={fit}><Focus size={16} /></button>
        <button title="重置布局" aria-label="重置布局" onClick={reset}><RotateCcw size={16} /></button>
        <button title="扩展选中节点" aria-label="扩展选中节点" disabled={!selectedId} onClick={onExpand}><Expand size={16} /></button>
        <button title="高亮最短可见路径" className="path-button" onClick={() => { pathPick.current = true; pathStart.current = null; setPathLabel('选择起点'); }}><Route size={16} /><span>{pathLabel}</span></button>
        <button title="导出 PNG" aria-label="导出关系图图片" onClick={download}><Download size={16} /></button>
      </div>
    </div>
    <div className="graph-stage" ref={mount}>{tip && <div className="graph-tooltip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>}</div>
    {!data?.nodes.length && <div className="graph-empty"><GitBranch size={32} /><strong>{data ? "当前视图没有匹配节点" : "正在准备关系图数据"}</strong><span>{data ? "请选择较晚日期、其他分量，或清除筛选条件以查看证据。" : "请运行数据采集和建图脚本，然后刷新页面。"}</span></div>}
    <div className="graph-footer"><span><i className="legend-dot issue" /> Issue</span><span><i className="legend-dot pr" /> PR</span><span><i className="legend-dot commit" /> 提交</span><span><i className="legend-dot review" /> 审查</span><span><i className="legend-line" /> 已核实</span><span><i className="legend-line dashed" /> 候选关系</span></div>
  </div>;
}
