import type { StageEvent } from '../api/jobs.api';

const STAGES: { key: string; label: string }[] = [
  { key: 'classify',     label: 'Classify PDF (digital / scanned / hybrid)' },
  { key: 'extract_text', label: 'Extract text (OCR fallback for scans)' },
  { key: 'chunk',        label: 'Chunk into sections' },
  { key: 'extract',      label: 'Extract concepts + relations (LLM)' },
  { key: 'merge',        label: 'Merge + deduplicate graph' },
  { key: 'brief',        label: 'Synthesise executive brief' },
];

export interface StageState {
  status: 'pending' | 'running' | 'done' | 'error';
  detail?: string;
  index?: number;
  total?: number;
}

export function reduceStages(events: StageEvent[]): Record<string, StageState> {
  const map: Record<string, StageState> = {};
  for (const s of STAGES) map[s.key] = { status: 'pending' };
  for (const ev of events) {
    if (ev.stage === 'done') continue;
    map[ev.stage] = {
      status: ev.status as StageState['status'],
      detail: ev.detail,
      index: ev.index,
      total: ev.total,
    };
  }
  return map;
}

const ICON: Record<StageState['status'], { cls: string; color: string }> = {
  pending: { cls: 'bi-circle',             color: 'var(--muted)' },
  running: { cls: 'bi-arrow-repeat',       color: 'var(--brand)' },
  done:    { cls: 'bi-check-circle-fill',  color: '#16a34a' },
  error:   { cls: 'bi-x-circle-fill',      color: '#dc2626' },
};

export function WorkflowStages({ events }: { events: StageEvent[] }) {
  const state = reduceStages(events);

  return (
    <div className="workflow-stages">
      {STAGES.map((s) => {
        const st = state[s.key];
        const icon = ICON[st.status];
        const pct = s.key === 'extract' && st.total
          ? Math.round((100 * (st.index ?? 0)) / st.total)
          : null;

        return (
          <div key={s.key} className="stage-item">
            <span className="stage-icon">
              <i className={`bi ${icon.cls}`} style={{ color: icon.color }}></i>
            </span>
            <div className="stage-label">
              <span>{s.label}</span>
              {st.detail && (
                <span style={{ color: 'var(--muted)', fontSize: '0.8125rem' }}> · {st.detail}</span>
              )}
              {pct !== null && st.status === 'running' && (
                <div className="stage-progress">
                  <div className="stage-progress-bar">
                    <div className="stage-progress-fill" style={{ width: `${pct}%` }}></div>
                  </div>
                  <span>{st.index}/{st.total} ({pct}%)</span>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
