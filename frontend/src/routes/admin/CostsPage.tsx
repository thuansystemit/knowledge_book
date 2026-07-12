import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getCosts, type CostSummary } from '../../api/costs.api';

function usd(v: number): string {
  return `$${v < 1 ? v.toFixed(4) : v.toFixed(2)}`;
}

export function CostsPage() {
  const [data, setData] = useState<CostSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCosts().then(setData).catch(() => setError('Could not load cost telemetry.'));
  }, []);

  if (error) return <div className="alert alert-danger mt-3" role="alert">{error}</div>;
  if (!data) return (
    <div className="d-flex align-items-center gap-2 mt-4" style={{ color: 'var(--muted)', fontSize: '0.875rem' }}>
      <div className="spinner-border spinner-border-sm" role="status" style={{ color: 'var(--brand)' }}></div>
      Loading…
    </div>
  );

  const overCap = data.cap_usd > 0 && data.max_usd > data.cap_usd;
  const stats = [
    { label: 'Documents costed', value: String(data.documents) },
    { label: 'Total spend', value: usd(data.total_usd) },
    { label: 'Avg / document', value: usd(data.avg_usd) },
    { label: 'Max / document', value: usd(data.max_usd) },
    { label: 'Cap / document', value: data.cap_usd > 0 ? usd(data.cap_usd) : 'off' },
    ...(data.cap_usd > 0
      ? [{ label: 'Near cap (≥80%)', value: String(data.near_cap_count) }]
      : []),
  ];

  return (
    <div>
      <div className="mb-4">
        <h1 className="page-title">Cost telemetry</h1>
        <p className="page-subtitle">Estimated per-document LLM cost (EXT-02). Internal — not shown to users.</p>
      </div>

      {data.documents === 0 && (
        <div className="alert alert-info" role="status" style={{ maxWidth: 720 }}>
          No documents have recorded a cost yet. Costs are recorded on new extractions;
          local models (Ollama) are free, so run one with a cloud model to see spend here.
        </div>
      )}

      {/* Stat tiles */}
      <div className="row g-3 mb-4" style={{ maxWidth: 960 }}>
        {stats.map((s) => (
          <div key={s.label} className="col-6 col-md">
            <div className="card h-100"><div className="card-body" style={{ padding: '1rem' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.03em' }}>{s.label}</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{s.value}</div>
            </div></div>
          </div>
        ))}
      </div>

      {overCap && (
        <div className="alert alert-warning" role="status" style={{ maxWidth: 960 }}>
          A document exceeded the ${data.cap_usd.toFixed(2)} cap. New over-budget jobs abort with <code>cost_cap</code>.
        </div>
      )}

      {/* Top costly documents */}
      {data.top.length > 0 && (
        <div className="card" style={{ maxWidth: 960 }}>
          <div className="card-header"><div className="section-heading">Most expensive documents</div></div>
          <div className="card-body p-0">
            <div className="table-responsive">
              <table className="table table-hover align-middle mb-0">
                <thead className="table-light">
                  <tr><th className="ps-3">Document</th><th className="text-end pe-3">Cost</th></tr>
                </thead>
                <tbody>
                  {data.top.map((r) => (
                    <tr key={r.job_id}>
                      <td className="ps-3">
                        <Link to={`/documents/${r.job_id}`} style={{ fontWeight: 500 }}>{r.title}</Link>
                        {r.by_stage && Object.keys(r.by_stage).length > 0 && (
                          <div style={{ fontSize: '0.72rem', color: 'var(--muted)', fontVariantNumeric: 'tabular-nums' }}>
                            {Object.entries(r.by_stage).map(([s, v]) => `${s} ${usd(v)}`).join(' · ')}
                          </div>
                        )}
                      </td>
                      <td className="text-end pe-3" style={{ fontVariantNumeric: 'tabular-nums' }}>
                        {usd(r.cost_usd)}
                        {r.warn && r.cap_pct != null && (
                          <span className="badge bg-warning text-dark ms-2" title="≥80% of the per-document cap">
                            {Math.round(r.cap_pct * 100)}% of cap
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
