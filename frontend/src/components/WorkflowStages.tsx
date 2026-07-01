import type { StageEvent } from '../api/jobs.api';

// The fixed pipeline order (app/pipeline.py). The live events drive each row's
// status; this gives the user the whole workflow at a glance from the start.
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

const ICON: Record<StageState['status'], string> = {
  pending: '○',
  running: '◐',
  done: '●',
  error: '✕',
};

export function WorkflowStages({ events }: { events: StageEvent[] }) {
  const state = reduceStages(events);
  return (
    <ol className="stages">
      {STAGES.map((s) => {
        const st = state[s.key];
        const pct =
          s.key === 'extract' && st.total
            ? Math.round((100 * (st.index ?? 0)) / st.total)
            : null;
        return (
          <li key={s.key} className={`stage stage-${st.status}`}>
            <span className="stage-icon">{ICON[st.status]}</span>
            <span className="stage-label">
              {s.label}
              {pct !== null && st.status === 'running' && (
                <span className="stage-prog"> — {st.index}/{st.total} ({pct}%)</span>
              )}
              {st.detail && <span className="stage-detail"> · {st.detail}</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
