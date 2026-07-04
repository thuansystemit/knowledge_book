import { api } from './client';

export interface Metrics {
  pipeline: {
    count: number;
    p50_ms: number | null; p90_ms: number | null; max_ms: number | null;
    budget_digital_ms: number; budget_scanned_ms: number;
    over_budget: boolean;
    stage_p90_ms: Record<string, number>;
  };
  qa: {
    count: number;
    median_ms: number | null; p95_ms: number | null;
    budget_ms: number; over_budget: boolean;
  };
  ocr: {
    count: number;
    median: number | null;
    threshold: number;
    low_confidence: number;
    low_confidence_rate: number | null;
    histogram: Record<string, number>;
  };
}

/** Admin-only latency observability (ACT-05 pipeline + ACT-07 Q&A). */
export async function getMetrics(): Promise<Metrics> {
  const { data } = await api.get<Metrics>('/api/admin/metrics');
  return data;
}
