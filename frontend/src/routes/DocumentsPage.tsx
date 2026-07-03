import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listJobs, type JobSummary } from '../api/jobs.api';
import { listCategories } from '../api/categories.api';
import { useAsync } from '../hooks/useAsync';
import { Select } from '../components/Select';
import { canUpload } from '../lib/constants';
import { useAuthStore } from '../store/authStore';

/** Returns a progress percentage 0-100 from whatever the backend provides. */
function pct(j: JobSummary): number | null {
  // JobSummary may carry a progress field — use it if present
  const p = (j as JobSummary & { progress?: number }).progress;
  return typeof p === 'number' ? Math.round(p * 100) : null;
}

export function DocumentsPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState<string>('');
  const mayUpload = canUpload(useAuthStore((s) => s.user?.role));

  const { data: cats } = useAsync(listCategories);

  useEffect(() => {
    let alive = true;
    const load = () =>
      listJobs(category || undefined)
        .then((j) => { if (alive) setJobs(j); })
        .finally(() => { if (alive) setLoading(false); });

    load();
    const t = setInterval(load, 4000);
    return () => { alive = false; clearInterval(t); };
  }, [category]);

  // Prefer the first "done" job that has a graph for the key-findings callout
  const doneWithGraph = jobs.find(
    (j) => j.status === 'done' && (j.node_count ?? 0) > 0,
  );

  const count = jobs.length;

  return (
    <div>
      {/* ── Header row ── */}
      <div className="d-flex align-items-center justify-content-between mb-4" style={{ gap: '1rem' }}>
        <h1 className="page-title">
          {loading
            ? 'Documents'
            : count > 0
            ? `Processing ${count} document${count === 1 ? '' : 's'}`
            : 'Documents'}
        </h1>
        <div className="d-flex gap-2 align-items-center flex-shrink-0">
          {cats && cats.length > 0 && (
            <Select
              value={category}
              onChange={setCategory}
              options={[
                { value: '', label: 'All categories' },
                ...cats.map((c) => ({ value: c.id, label: `${c.name} (${c.doc_count})` })),
              ]}
              width={200}
              ariaLabel="Filter by category"
            />
          )}
          {mayUpload && (
            <Link to="/documents/new" className="btn btn-primary">
              Upload
            </Link>
          )}
        </div>
      </div>

      {/* ── Content ── */}
      {loading ? (
        <div
          className="d-flex align-items-center gap-2"
          style={{ color: 'var(--muted)', fontSize: '0.875rem' }}
        >
          <div
            className="spinner-border spinner-border-sm"
            role="status"
            style={{ color: 'var(--brand)' }}
          ></div>
          Loading…
        </div>
      ) : jobs.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <i className="bi bi-archive empty-state-icon"></i>
            <div className="empty-state-title">Your archive is empty</div>
            <div className="empty-state-text">
              {category
                ? 'No documents in this category.'
                : mayUpload
                ? 'Upload a document to start building your archive.'
                : 'No documents have been shared with you yet.'}
            </div>
            {!category && mayUpload && (
              <Link to="/documents/new" className="btn btn-primary btn-sm">
                Add to archive
              </Link>
            )}
          </div>
        </div>
      ) : (
        <>
          {/* Document card list */}
          <div className="card">
            {jobs.map((j, idx) => {
              const progress = pct(j);
              const isLast = idx === jobs.length - 1;

              return (
                <div
                  key={j.job_id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '1rem 1.5rem',
                    borderBottom: isLast ? 'none' : '1px solid var(--border)',
                    gap: '1rem',
                  }}
                >
                  {/* Left: filename + sub-status */}
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <Link
                      to={`/documents/${j.job_id}`}
                      style={{
                        fontWeight: 600,
                        fontSize: '0.9375rem',
                        color: 'var(--ink)',
                        display: 'block',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {j.title}
                    </Link>
                    <span style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>
                      {j.status === 'running'
                        ? 'Extracting knowledge graph…'
                        : j.status === 'done'
                        ? `${j.node_count ?? 0} concepts · ${j.edge_count ?? 0} relations`
                        : j.status === 'error'
                        ? 'Extraction failed'
                        : 'Queued'}
                    </span>
                  </div>

                  {/* Right: status indicator */}
                  <div
                    style={{
                      flexShrink: 0,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                    }}
                  >
                    {j.status === 'done' && (
                      <span className="doc-status-done">Done</span>
                    )}
                    {j.status === 'running' && (
                      <>
                        <div className="doc-progress-bar">
                          <div
                            className="doc-progress-fill"
                            style={{ width: `${progress ?? 50}%` }}
                          ></div>
                        </div>
                        <span className="doc-status-pct">
                          {progress !== null ? `${progress}%` : '…'}
                        </span>
                      </>
                    )}
                    {j.status === 'error' && (
                      <span style={{ color: '#dc2626', fontSize: '0.875rem', fontWeight: 600 }}>
                        Error
                      </span>
                    )}
                    {j.status !== 'done' && j.status !== 'running' && j.status !== 'error' && (
                      <span className="doc-status-queued">Queued</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Key findings callout — show for the most recent done document */}
          {doneWithGraph && (
            <div className="finding-callout">
              <div className="finding-callout-title">
                Key findings extracted —{' '}
                <span className="finding-callout-filename">{doneWithGraph.title}</span>
              </div>
              <div style={{ fontSize: '0.875rem', color: 'var(--body)', lineHeight: 1.7 }}>
                <Link to={`/documents/${doneWithGraph.job_id}`} style={{ color: 'var(--body)' }}>
                  <i className="bi bi-arrow-right-circle me-2" style={{ color: 'var(--brand)' }}></i>
                  View {doneWithGraph.node_count} concepts and{' '}
                  {doneWithGraph.edge_count} relations extracted from this document.
                </Link>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
