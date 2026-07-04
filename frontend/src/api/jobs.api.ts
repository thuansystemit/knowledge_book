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
export interface Paywall { capped: boolean; concepts_shown: number; concepts_total: number; }
export interface Graph {
  nodes: GraphNode[]; edges: GraphEdge[];
  stats: { node_count: number; edge_count: number };
  document?: { title: string; pdf_type: string; pages_chunked: number };
  warnings?: string[]; brief?: Brief | null;
  failed_chunks?: unknown[];
  paywall?: Paywall;   // set when the Free tier caps the concept map (PAY-01)
  cost?: { calls: number; input_tokens: number; output_tokens: number; usd: number };  // EXT-02
  ocr_quality?: {      // OCR confidence gate (ING-06)
    ocr_used: boolean; mean_confidence?: number | null; low_confidence?: boolean;
    low_pages?: number[]; threshold?: number;
  };
  chapter_guide?: ChapterGuideEntry[];   // OUT-03
  chapter_guide_locked?: boolean;        // withheld on the Free tier (PAY-01)
}

export interface ConceptRef { id: string; name: string; }
export interface ChapterGuideEntry {
  chapter: string;
  summary: string;
  concepts_introduced: ConceptRef[];
  prerequisites: ConceptRef[];
}
export interface JobSummary {
  job_id: string; title: string; status: string;
  node_count: number | null; edge_count: number | null; created_at: string | null;
}
export interface JobDetail {
  job_id: string; title: string; status: string; error: string | null;
  events: StageEvent[]; graph: Graph | null; has_pdf?: boolean;
  user_id?: string;   // owner — used to gate the Delete action (owner or admin)
}
export interface StageEvent {
  stage: string; status: string; detail?: string; index?: number; total?: number;
}

export async function listJobs(categoryId?: string) {
  const { data } = await api.get<JobSummary[]>('/api/jobs', {
    params: categoryId ? { category_id: categoryId } : {},
  });
  return data;
}

export async function getJob(jobId: string) {
  const { data } = await api.get<JobDetail>(`/api/jobs/${jobId}`);
  return data;
}

export async function createJob(file: File, model?: string, categoryId?: string) {
  const form = new FormData();
  form.append('file', file);
  if (model) form.append('model', model);
  if (categoryId) form.append('category_id', categoryId);
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

/** Fetch the stored source PDF (with auth) and return an object URL for viewing.
 * Caller must URL.revokeObjectURL when done. */
export async function fetchPdfObjectUrl(jobId: string): Promise<string> {
  const res = await api.get(`/api/jobs/${jobId}/pdf`, { responseType: 'blob' });
  return URL.createObjectURL(res.data as Blob);
}

/** Download the document's outputs as Markdown or JSON (OUT-06, Pro/Scholar). */
export async function exportJob(jobId: string, fmt: 'md' | 'json'): Promise<void> {
  const res = await api.get(`/api/jobs/${jobId}/export`, { params: { fmt }, responseType: 'blob' });
  const url = URL.createObjectURL(res.data as Blob);
  const cd = (res.headers['content-disposition'] as string) || '';
  const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? `document.${fmt}`;
  const a = document.createElement('a');
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
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
