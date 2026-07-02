import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listJobs, type JobSummary } from '../api/jobs.api';
import { listCategories, type Category } from '../api/categories.api';

const BADGE: Record<string, string> = {
  running: 'text-bg-primary', done: 'text-bg-success', error: 'text-bg-danger',
};

export function DocumentsPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [cats, setCats] = useState<Category[]>([]);
  const [category, setCategory] = useState<string>('');

  useEffect(() => { listCategories().then(setCats).catch(() => {}); }, []);

  useEffect(() => {
    let alive = true;
    const load = () => listJobs(category || undefined).then((j) => alive && setJobs(j)).finally(() => alive && setLoading(false));
    load();
    const t = setInterval(load, 4000);
    return () => { alive = false; clearInterval(t); };
  }, [category]);

  return (
    <div>
      <div className="d-flex align-items-center justify-content-between mb-4">
        <h1 className="h3 fw-bold mb-0">Documents</h1>
        <div className="d-flex gap-2">
          {cats.length > 0 && (
            <select className="form-select" style={{ width: 200 }} value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All categories</option>
              {cats.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.doc_count})</option>)}
            </select>
          )}
          <Link to="/documents/new" className="btn btn-primary">
            <i className="bi bi-plus-lg me-1"></i>New extraction
          </Link>
        </div>
      </div>

      {loading ? (
        <p className="text-secondary">Loading…</p>
      ) : jobs.length === 0 ? (
        <div className="card border-0 shadow-sm rounded-4">
          <div className="card-body text-center py-5">
            <i className="bi bi-folder2-open fs-1 text-secondary opacity-50"></i>
            <p className="text-secondary mt-3 mb-3">No documents yet.</p>
            <Link to="/documents/new" className="btn btn-primary">Upload your first PDF</Link>
          </div>
        </div>
      ) : (
        <div className="card border-0 shadow-sm rounded-4">
          <div className="table-responsive">
            <table className="table table-hover align-middle mb-0">
              <thead className="table-light">
                <tr className="small text-secondary text-uppercase">
                  <th className="ps-4">Title</th><th>Status</th><th>Concepts</th>
                  <th>Relations</th><th className="pe-4">Created</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.job_id}>
                    <td className="ps-4 fw-semibold">
                      <Link to={`/documents/${j.job_id}`} className="text-decoration-none">
                        <i className="bi bi-file-earmark-text me-2 text-secondary"></i>{j.title}
                      </Link>
                    </td>
                    <td><span className={`badge ${BADGE[j.status] ?? 'text-bg-secondary'} text-capitalize`}>{j.status}</span></td>
                    <td>{j.node_count ?? '—'}</td>
                    <td>{j.edge_count ?? '—'}</td>
                    <td className="pe-4 text-secondary small">{j.created_at ? new Date(j.created_at).toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
