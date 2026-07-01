import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listJobs, type JobSummary } from '../api/jobs.api';

const STATUS_CLASS: Record<string, string> = {
  running: 'badge-run', done: 'badge-done', error: 'badge-err',
};

export function DocumentsPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = () => listJobs().then((j) => alive && setJobs(j)).finally(() => alive && setLoading(false));
    load();
    // light polling so running jobs update their status/counts
    const t = setInterval(load, 4000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  return (
    <div>
      <div className="page-head">
        <h1>Documents</h1>
        <Link to="/documents/new" className="btn">New extraction</Link>
      </div>

      {loading ? (
        <p className="muted">Loading…</p>
      ) : jobs.length === 0 ? (
        <p className="muted">No documents yet. Click <strong>New extraction</strong> to upload a PDF.</p>
      ) : (
        <table className="tbl">
          <thead>
            <tr><th>Title</th><th>Status</th><th>Concepts</th><th>Relations</th><th>Created</th></tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.job_id}>
                <td><Link to={`/documents/${j.job_id}`}>{j.title}</Link></td>
                <td><span className={`badge ${STATUS_CLASS[j.status] ?? ''}`}>{j.status}</span></td>
                <td>{j.node_count ?? '—'}</td>
                <td>{j.edge_count ?? '—'}</td>
                <td className="muted">{j.created_at ? new Date(j.created_at).toLocaleString() : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
