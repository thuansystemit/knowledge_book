import { api, API_URL } from './client';

// ---- Types mirroring the backend graph (app/graph_builder.py) --------------
export interface SourceRef { chapter: string; page_start: number; page_end: number; }
export interface GraphNode {
  id: string; name: string; type: string; definition: string;
  confidence: number; source_refs: SourceRef[];
}
export interface GraphEdge {
  source: string; target: string; type: string; confidence: number; evidence: string;
}
export interface Brief {
  thesis?: string; core_concepts?: string[]; key_principles?: string[];
  audience?: string; summary?: string;
}
export interface Graph {
  nodes: GraphNode[]; edges: GraphEdge[];
  stats: { node_count: number; edge_count: number };
  document?: { title: string; pdf_type: string; pages_chunked: number };
  warnings?: string[]; brief?: Brief | null;
  failed_chunks?: unknown[];
}
export interface JobSummary {
  job_id: string; title: string; status: string;
  node_count: number | null; edge_count: number | null; created_at: string | null;
}
export interface JobDetail {
  job_id: string; title: string; status: string; error: string | null;
  events: StageEvent[]; graph: Graph | null;
}
export interface StageEvent {
  stage: string; status: string; detail?: string; index?: number; total?: number;
}

export async function listJobs() {
  const { data } = await api.get<JobSummary[]>('/api/jobs');
  return data;
}

export async function getJob(jobId: string) {
  const { data } = await api.get<JobDetail>(`/api/jobs/${jobId}`);
  return data;
}

export async function createJob(file: File) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<{ job_id: string; title: string }>('/api/jobs', form);
  return data;
}

/** Re-extract the failed chunks and merge them into the existing graph. */
export async function retryFailed(jobId: string) {
  const { data } = await api.post<{ job_id: string; retrying: number }>(
    `/api/jobs/${jobId}/retry-failed`,
  );
  return data;
}

export async function deleteJob(jobId: string) {
  await api.delete(`/api/jobs/${jobId}`);
}

/** Fetch a 60s stream token, then open an authenticated SSE connection. */
export async function subscribeEvents(
  jobId: string,
  onEvent: (ev: StageEvent) => void,
  onEnd: () => void,
): Promise<() => void> {
  const { data } = await api.post<{ token: string }>(`/api/jobs/${jobId}/stream-token`);
  const es = new EventSource(`${API_URL}/api/jobs/${jobId}/events?t=${encodeURIComponent(data.token)}`);
  es.onmessage = (m) => {
    try { onEvent(JSON.parse(m.data) as StageEvent); } catch { /* ignore */ }
  };
  const end = () => { es.close(); onEnd(); };
  es.addEventListener('end', end);
  es.onerror = end;
  return () => es.close();
}
