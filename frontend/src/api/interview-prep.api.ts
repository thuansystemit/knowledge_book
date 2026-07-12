import { api, API_URL } from './client';

export type Track = 'junior_backend' | 'senior_backend' | 'system_design';
export type PrepStatus = 'pending' | 'generating' | 'done' | 'error';
export type Difficulty = 'easy' | 'medium' | 'hard';

export const TRACKS: { id: Track; label: string; blurb: string }[] = [
  { id: 'junior_backend', label: 'Junior Backend',
    blurb: 'Fundamentals: HTTP/REST, CRUD, SQL, auth, containers.' },
  { id: 'senior_backend', label: 'Senior Backend',
    blurb: 'Trade-offs: scaling, caching, messaging, observability.' },
  { id: 'system_design', label: 'System Design',
    blurb: 'Architecture: capacity, sharding, consistency, bottlenecks.' },
];

export interface StudyStep {
  order: number;
  topic: string;
  description: string;
  time_estimate_hours: number | null;
  source_docs: string[];
}

export interface CorpusCoverage {
  total_docs_scanned: number;
  topics_with_coverage: number;
  topics_without_coverage: string[];
}

export interface PlanData {
  track: Track;
  generated_at: string;
  model: string | null;
  corpus_coverage: CorpusCoverage;
  study_path: StudyStep[];
  checklist: Record<string, string[]>;
}

export interface PrepPlan {
  id: string;
  track: Track;
  status: PrepStatus;
  version: number;
  is_current: boolean;
  error: string | null;
  category_ids: string[] | null;
  plan_data: PlanData | null;
  model: string | null;
  cost_usd: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface VersionMeta {
  id: string;
  version: number;
  is_current: boolean;
  status: PrepStatus;
  model: string | null;
  cost_usd: number | null;
  question_count: number;
  generated_at: string | null;
  created_at: string | null;
  error: string | null;
}

export interface VersionList {
  track: Track;
  versions: VersionMeta[];
}

export interface PrepQuestion {
  id: string;
  topic: string;
  question: string;
  model_answer: string;
  difficulty: Difficulty;
  citations: string[] | null;
  sort_order: number;
}

export type PrepPlanDetail = PrepPlan & { questions: PrepQuestion[] };

export interface PrepEvent {
  stage: string;
  status?: PrepStatus;
  detail?: string;
}

export async function listPlans() {
  const { data } = await api.get<{ plans: PrepPlan[] }>('/api/interview-prep');
  return data.plans;
}

export async function createPlan(track: Track) {
  const { data } = await api.post<PrepPlan>('/api/interview-prep', { track });
  return data;
}

export async function getPlan(planId: string) {
  const { data } = await api.get<PrepPlanDetail>(`/api/interview-prep/${planId}`);
  return data;
}

export async function regeneratePlan(planId: string) {
  const { data } = await api.post<PrepPlan>(`/api/interview-prep/${planId}/regenerate`);
  return data;
}

export async function deletePlan(planId: string) {
  const { data } = await api.delete<{ ok: boolean; new_current_id: string | null }>(
    `/api/interview-prep/${planId}`,
  );
  return data;
}

export async function listVersions(planId: string) {
  const { data } = await api.get<VersionList>(`/api/interview-prep/${planId}/versions`);
  return data;
}

export async function pinVersion(planId: string) {
  const { data } = await api.post<PrepPlanDetail>(`/api/interview-prep/${planId}/pin`);
  return data;
}

async function getStreamToken(planId: string) {
  const { data } = await api.post<{ token: string }>(
    `/api/interview-prep/${planId}/stream-token`,
  );
  return data.token;
}

/**
 * Subscribe to a plan's generation progress. Fetches a short-lived stream token
 * (EventSource can't send Authorization headers), then opens the SSE stream.
 * Returns an unsubscribe fn. `onDone` fires on the terminal `done`/`error` frame
 * or the `end` event.
 */
export function subscribePrepStream(
  planId: string,
  onEvent: (e: PrepEvent) => void,
  onDone: (status: PrepStatus) => void,
  onError: (msg: string) => void,
): () => void {
  let es: EventSource | null = null;
  let closed = false;
  let lastStatus: PrepStatus = 'generating';

  getStreamToken(planId)
    .then((token) => {
      if (closed) return;
      es = new EventSource(
        `${API_URL}/api/interview-prep/${planId}/events?t=${encodeURIComponent(token)}`,
      );
      es.onmessage = (m) => {
        try {
          const d: PrepEvent = JSON.parse(m.data);
          onEvent(d);
          if (d.status) lastStatus = d.status;
          if (d.stage === 'done') onDone(d.status ?? 'done');
        } catch {
          /* ignore malformed frame */
        }
      };
      es.addEventListener('end', () => { onDone(lastStatus); es?.close(); });
      es.onerror = () => { es?.close(); };
    })
    .catch((err) => onError(String(err?.message ?? err)));

  return () => { closed = true; es?.close(); };
}
