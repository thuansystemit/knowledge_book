import { api } from './client';

export interface CostRow {
  job_id: string;
  title: string;
  cost_usd: number;
  cap_pct: number | null;
  warn: boolean;
  by_stage: Record<string, number> | null;
}
export interface CostSummary {
  documents: number;
  total_usd: number;
  avg_usd: number;
  max_usd: number;
  cap_usd: number;
  warn_threshold_usd: number | null;
  near_cap_count: number;
  top: CostRow[];
}

/** Admin-only per-document cost telemetry (EXT-02 / ACT-04). */
export async function getCosts(): Promise<CostSummary> {
  const { data } = await api.get<CostSummary>('/api/admin/costs');
  return data;
}
