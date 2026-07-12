import { api } from './client';

export interface ActivationStatus {
  viewed: boolean;
  rated: boolean;
  rating: 'up' | 'down' | null;
}

/** ACT-01: record that the Concept Map was viewed for this document. */
export async function recordView(jobId: string, sessionId?: string): Promise<void> {
  await api.post('/api/activation/view', { job_id: jobId, session_id: sessionId });
}

/** ACT-02: record the thumbs up/down rating on the concept list. */
export async function recordRating(jobId: string, rating: 'up' | 'down'): Promise<void> {
  await api.post('/api/activation/rate', { job_id: jobId, rating });
}

/** What the current user has already done on this doc (drives the prompt). */
export async function getActivationStatus(jobId: string): Promise<ActivationStatus> {
  const { data } = await api.get<ActivationStatus>(`/api/activation/status/${jobId}`);
  return data;
}

/** Paywall gate a conversion click can come from (PAY-06). */
export type UpgradeSource =
  | 'upload_limit' | 'concept_cap' | 'chapter_guide' | 'qa' | 'qa_weak'
  | 'export' | 'scanned' | 'credits' | 'other';

/** PAY-06: record that the user clicked an upgrade CTA (fire-and-forget). */
export async function trackUpgradeClick(source: UpgradeSource, jobId?: string): Promise<void> {
  try {
    await api.post('/api/activation/upgrade-click', { source, job_id: jobId ?? null });
  } catch {
    /* telemetry is best-effort — never block the upgrade navigation */
  }
}
