import { useEffect, useState } from 'react';
import { getMetrics, type Metrics } from '../../api/metrics.api';

function ms(v: number | null | undefined): string {
  if (v == null) return '—';
  return v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${v}ms`;
}

export function MetricsPage() {
  const [data, setData] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMetrics().then(setData).catch(() => setError('Could not load metrics.'));
  }, []);

  if (error) return <div className="alert alert-danger mt-3" role="alert">{error}</div>;
  if (!data) return (
    <div className="d-flex align-items-center gap-2 mt-4" style={{ color: 'var(--muted)', fontSize: '0.875rem' }}>
      <div className="spinner-border spinner-border-sm" role="status" style={{ color: 'var(--brand)' }}></div>
      Loading…
    </div>
  );

  const p = data.pipeline;
  const q = data.qa;
  const tile = (label: string, value: string, danger = false) => (
    <div className="col-6 col-md" key={label}>
      <div className="card h-100"><div className="card-body" style={{ padding: '1rem' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.03em' }}>{label}</div>
        <div style={{ fontSize: '1.4rem', fontWeight: 700, color: danger ? '#b91c1c' : 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      </div></div>
    </div>
  );

  return (
    <div>
      <div className="mb-4">
        <h1 className="page-title">Latency</h1>
        <p className="page-subtitle">Pipeline &amp; Q&amp;A response times (ACT-05 / ACT-07). Internal — not user-facing.</p>
      </div>

      {/* Pipeline */}
      <div className="section-heading mb-2">Pipeline (end-to-end)</div>
      {p.over_budget && (
        <div className="alert alert-warning" role="status" style={{ maxWidth: 960 }}>
          p90 pipeline time exceeds the scanned-doc budget ({ms(p.budget_scanned_ms)}).
        </div>
      )}
      <div className="row g-3 mb-2" style={{ maxWidth: 960 }}>
        {tile('Documents', String(p.count))}
        {tile('p50', ms(p.p50_ms))}
        {tile('p90', ms(p.p90_ms), !!(p.p90_ms && p.p90_ms > p.budget_scanned_ms))}
        {tile('max', ms(p.max_ms))}
        {tile('Budget (digital/scan)', `${ms(p.budget_digital_ms)} / ${ms(p.budget_scanned_ms)}`)}
      </div>
      {Object.keys(p.stage_p90_ms).length > 0 && (
        <div className="card mb-4" style={{ maxWidth: 960 }}>
          <div className="card-header"><div className="section-heading">Per-stage p90 (recent)</div></div>
          <div className="card-body p-0">
            <div className="table-responsive">
              <table className="table table-sm align-middle mb-0">
                <tbody>
                  {Object.entries(p.stage_p90_ms).map(([stage, v]) => (
                    <tr key={stage}>
                      <td className="ps-3" style={{ textTransform: 'capitalize' }}>{stage.replace(/_/g, ' ')}</td>
                      <td className="text-end pe-3" style={{ fontVariantNumeric: 'tabular-nums' }}>{ms(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Q&A */}
      <div className="section-heading mb-2">Q&amp;A answers</div>
      {q.over_budget && (
        <div className="alert alert-warning" role="status" style={{ maxWidth: 960 }}>
          Median Q&amp;A latency exceeds the {ms(q.budget_ms)} target.
        </div>
      )}
      <div className="row g-3" style={{ maxWidth: 960 }}>
        {tile('Questions', String(q.count))}
        {tile('median', ms(q.median_ms), !!(q.median_ms && q.median_ms > q.budget_ms))}
        {tile('p95', ms(q.p95_ms))}
        {tile('Target', ms(q.budget_ms))}
      </div>

      {p.count === 0 && q.count === 0 && (
        <div className="alert alert-info mt-4" role="status" style={{ maxWidth: 960 }}>
          No timing data yet — process a document and ask a question (data is recorded on new activity).
        </div>
      )}
    </div>
  );
}
