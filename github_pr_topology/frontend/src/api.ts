export type GraphNode = {
  id: string; type: string; repo: string; number: string | number; title: string;
  created_at?: string; updated_at?: string; state?: string; source_url?: string;
  description?: string; description_temporal_status?: string; metadata: Record<string, unknown>;
  seed?: boolean; boundary?: boolean;
};
export type GraphEdge = {
  id: string; source: string; target: string; relation_type: string; evidence_type: string;
  evidence_url?: string; supporting_urls?: string[]; evidence_event_id?: string | number; evidence_timestamp?: string;
  confidence: string; verification_status: string; temporal_status: string; content?: string;
};
export type GraphData = { nodes: GraphNode[]; edges: GraphEdge[]; total_matching_nodes: number; rendered_nodes: number; rendered_edges: number; truncated_for_display: boolean; scope: string; as_of?: string; time_slice_note?: string };
export type Repo = { full_name: string; stars: number; total_pull_requests: number; total_issues: number; created_at: string; metrics?: Record<string, unknown>; [key: string]: unknown };
export type TimelineEvent = { event_type: string; timestamp?: string; actor?: string; actor_type: string; content?: string; source_url?: string; source_id?: string | number; temporal_status: string; commit_sha?: string };
export type PRDetail = { pr: GraphNode; timeline: TimelineEvent[]; relationships: GraphEdge[]; related_nodes: GraphNode[]; time_slice_note?: string };
export type Case = { case_id: string; repo: string; anchor_pr_id: string; title: string; patterns: string[]; summary: string; node_ids: string[]; [key: string]: unknown };

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`请求失败（HTTP ${response.status}）`);
  return response.json() as Promise<T>;
}

export function url(path: string, args: Record<string, string | number | boolean | undefined | null>) {
  const query = new URLSearchParams();
  Object.entries(args).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== '') query.set(key, String(value)); });
  return `${path}?${query.toString()}`;
}
