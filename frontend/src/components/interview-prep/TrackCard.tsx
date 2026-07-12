import type { PrepPlan, PrepStatus, Track } from '../../api/interview-prep.api';

const STATUS_BADGE: Record<PrepStatus, { label: string; cls: string }> = {
  pending: { label: 'Queued', cls: 'bg-secondary' },
  generating: { label: 'Generating…', cls: 'bg-info text-dark' },
  done: { label: 'Ready', cls: 'bg-success' },
  error: { label: 'Failed', cls: 'bg-danger' },
};

export function TrackCard({
  track, label, blurb, plan, busy, onGenerate, onView,
}: {
  track: Track;
  label: string;
  blurb: string;
  plan: PrepPlan | undefined;
  busy: boolean;
  onGenerate: (track: Track) => void;
  onView: (plan: PrepPlan) => void;
}) {
  const status = plan?.status;
  const badge = status ? STATUS_BADGE[status] : null;
  const ready = status === 'done';
  const active = status === 'pending' || status === 'generating';
  const failed = status === 'error';

  return (
    <div className="card h-100" style={{ border: '1px solid var(--border)' }}>
      <div className="card-body d-flex flex-column">
        <div className="d-flex align-items-center justify-content-between">
          <h5 className="mb-0" style={{ color: 'var(--ink)' }}>{label}</h5>
          {badge && (
            <span className={`badge ${badge.cls}`}>
              {ready && plan ? `v${plan.version} · ` : ''}{badge.label}
            </span>
          )}
        </div>
        <p className="mt-2 mb-3" style={{ fontSize: '0.875rem', color: 'var(--muted)', flex: 1 }}>
          {blurb}
        </p>

        <div className="d-flex gap-2">
          {ready ? (
            <>
              <button className="btn btn-primary btn-sm flex-grow-1" onClick={() => plan && onView(plan)}>
                View plan
              </button>
              <button
                className="btn btn-outline-secondary btn-sm"
                onClick={() => onGenerate(track)}
                disabled={busy}
                title="Regenerate from your latest documents"
              >
                <i className="bi bi-arrow-repeat" aria-hidden="true" />
              </button>
            </>
          ) : (
            <button
              className="btn btn-primary btn-sm w-100"
              onClick={() => (active && plan ? onView(plan) : onGenerate(track))}
              disabled={busy}
            >
              {active ? 'View progress' : failed ? 'Try again' : 'Generate plan'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
