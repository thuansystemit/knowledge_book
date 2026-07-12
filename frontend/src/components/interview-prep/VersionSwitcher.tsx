import type { VersionMeta } from '../../api/interview-prep.api';

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function label(v: VersionMeta): string {
  const parts = [`v${v.version}`];
  if (v.is_current) parts.push('Current');
  if (v.status === 'error') parts.push('Failed');
  else if (v.status !== 'done') parts.push(v.status);
  parts.push(fmtDate(v.generated_at ?? v.created_at));
  if (v.status === 'done') parts.push(`${v.question_count} Qs`);
  if (v.cost_usd != null) parts.push(`$${v.cost_usd.toFixed(2)}`);
  return parts.join(' · ');
}

/** Controlled dropdown to switch between prep-plan versions. */
export function VersionSwitcher({
  versions, selectedId, onChange,
}: {
  versions: VersionMeta[];
  selectedId: string;
  onChange: (id: string) => void;
}) {
  if (versions.length < 2) return null;
  return (
    <div className="d-flex align-items-center gap-2 mb-3">
      <label htmlFor="prep-version" className="mb-0" style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
        <i className="bi bi-clock-history me-1" aria-hidden="true" />Version
      </label>
      <select
        id="prep-version"
        className="form-select form-select-sm"
        style={{ maxWidth: 320 }}
        value={selectedId}
        onChange={(e) => onChange(e.target.value)}
      >
        {versions.map((v) => (
          <option key={v.id} value={v.id}>{label(v)}</option>
        ))}
      </select>
    </div>
  );
}
