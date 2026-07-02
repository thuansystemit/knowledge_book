import type { StageEvent } from '../api/jobs.api';

const STAGES: { key: string; label: string }[] = [
  { key: 'classify', label: 'Classify PDF (digital / scanned / hybrid)' },
  { key: 'extract_text', label: 'Extract text (OCR fallback for scans)' },
  { key: 'chunk', label: 'Chunk into sections' },
  { key: 'extract', label: 'Extract concepts + relations (LLM)' },
  { key: 'merge', label: 'Merge + deduplicate graph' },
  { key: 'brief', label: 'Synthesise executive Brief' },
];

export interface StageState {
  status: 'pending' | 'running' | 'done' | 'error';
  detail?: string; index?: number; total?: number;
}

export function reduceStages(events: StageEvent[]): Record<string, StageState> {
  const map: Record<string, StageState> = {};
  for (const s of STAGES) map[s.key] = { status: 'pending' };
  for (const ev of events) {
    if (ev.stage === 'done') continue;
    map[ev.stage] = { status: ev.status as StageState['status'], detail: ev.detail, index: ev.index, total: ev.total };
  }
  return map;
}

const ICON: Record<StageState['status'], string> = {
  pending: 'bi-circle text-secondary',
  running: 'bi-arrow-repeat text-primary',
  done: 'bi-check-circle-fill text-success',
  error: 'bi-x-circle-fill text-danger',
};

export function WorkflowStages({ events }: { events: StageEvent[] }) {
  const state = reduceStages(events);
  return (
    <ul className="list-group list-group-flush">
      {STAGES.map((s) => {
        const st = state[s.key];
        const pct = s.key === 'extract' && st.total ? Math.round((100 * (st.index ?? 0)) / st.total) : null;
        return (
          <li key={s.key} className="list-group-item d-flex align-items-center gap-2 px-0 border-0 py-1">
            <i className={`bi ${ICON[st.status]} stage-icon`}></i>
            <span>
              {s.label}
              {pct !== null && st.status === 'running' && (
                <span className="text-secondary small"> — {st.index}/{st.total} ({pct}%)</span>
              )}
              {st.detail && <span className="text-secondary small"> · {st.detail}</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
