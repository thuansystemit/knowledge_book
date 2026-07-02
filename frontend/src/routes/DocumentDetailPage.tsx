import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  deleteJob, getJob, retryFailed, subscribeEvents,
  type JobDetail, type StageEvent,
} from '../api/jobs.api';
import { GraphView } from '../components/GraphView';
import { WorkflowStages } from '../components/WorkflowStages';
import { ChatTab } from '../components/ChatTab';
import { DocumentViewer } from '../components/DocumentViewer';

type Tab = 'brief' | 'graph' | 'chat' | 'document';

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'brief', label: 'Brief', icon: 'bi-card-text' },
  { key: 'graph', label: 'Concept graph', icon: 'bi-diagram-3' },
  { key: 'chat', label: 'Chat', icon: 'bi-chat-dots' },
  { key: 'document', label: 'Document', icon: 'bi-file-earmark-pdf' },
];

export function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [events, setEvents] = useState<StageEvent[]>([]);
  const [tab, setTab] = useState<Tab>('brief');
  const [notFound, setNotFound] = useState(false);
  const [busy, setBusy] = useState(false);
  const unsubRef = useRef<(() => void) | undefined>(undefined);

  const load = useCallback(() => {
    if (!id) return;
    let alive = true;
    unsubRef.current?.();
    getJob(id)
      .then((j) => {
        if (!alive) return;
        setJob(j);
        setEvents(j.events || []);
        if (j.status === 'running') {
          setEvents([]);
          subscribeEvents(id,
            (ev) => alive && setEvents((prev) => [...prev, ev]),
            () => { if (alive) getJob(id).then((jj) => alive && setJob(jj)); },
          ).then((fn) => { if (!alive) fn(); else unsubRef.current = fn; });
        }
      })
      .catch(() => alive && setNotFound(true));
    return () => { alive = false; };
  }, [id]);

  useEffect(() => {
    const cleanup = load();
    return () => { cleanup?.(); unsubRef.current?.(); };
  }, [load]);

  const onRetry = async () => {
    if (!id) return;
    setBusy(true);
    try { await retryFailed(id); load(); } finally { setBusy(false); }
  };
  const onDelete = async () => {
    if (!id || !confirm('Delete this document?')) return;
    await deleteJob(id);
    navigate('/documents', { replace: true });
  };

  if (notFound) return <p className="text-secondary">Document not found (or not yours).</p>;
  if (!job) return <p className="text-secondary">Loading…</p>;

  const g = job.graph;
  const brief = g?.brief;
  const running = job.status === 'running';
  const failedCount = g?.failed_chunks?.length ?? 0;

  return (
    <div>
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div>
          <Link to="/documents" className="text-decoration-none small text-secondary">
            <i className="bi bi-arrow-left me-1"></i>All documents
          </Link>
          <h1 className="h3 fw-bold mb-0 mt-1">{job.title}</h1>
        </div>
        <button className="btn btn-outline-danger btn-sm" onClick={onDelete}>
          <i className="bi bi-trash me-1"></i>Delete
        </button>
      </div>

      {running && (
        <div className="card border-0 shadow-sm rounded-4 mb-3">
          <div className="card-body">
            <h2 className="h6 fw-bold mb-3">Workflow</h2>
            <WorkflowStages events={events} />
          </div>
        </div>
      )}
      {job.status === 'error' && <div className="alert alert-danger">Extraction failed: {job.error}</div>}

      {!running && failedCount > 0 && (
        <div className="alert alert-warning d-flex align-items-center justify-content-between">
          <span><i className="bi bi-exclamation-triangle me-2"></i>{failedCount} chunk(s) failed — retry and merge them in.</span>
          <button className="btn btn-warning btn-sm" onClick={onRetry} disabled={busy}>
            {busy ? 'Retrying…' : `Retry ${failedCount} failed`}
          </button>
        </div>
      )}

      {g && (
        <>
          <div className="row g-3 mb-3">
            {[
              { label: 'Concepts', value: g.stats.node_count },
              { label: 'Relations', value: g.stats.edge_count },
              { label: 'PDF type', value: g.document?.pdf_type ?? '—' },
              { label: 'Chunks', value: g.document?.pages_chunked ?? '—' },
            ].map((s) => (
              <div className="col-6 col-md-3" key={s.label}>
                <div className="card border-0 shadow-sm rounded-4 h-100">
                  <div className="card-body py-3">
                    <div className="fs-3 fw-bold">{s.value}</div>
                    <div className="text-secondary small text-uppercase">{s.label}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <ul className="nav nav-pills gap-1 mb-3">
            {TABS.map((tb) => (
              <li className="nav-item" key={tb.key}>
                <button className={`nav-link ${tab === tb.key ? 'active' : 'text-secondary'}`}
                  onClick={() => setTab(tb.key)}>
                  <i className={`bi ${tb.icon} me-1`}></i>{tb.label}
                </button>
              </li>
            ))}
          </ul>

          <div className="card border-0 shadow-sm rounded-4">
            <div className="card-body p-4">
              {tab === 'brief' && (
                !brief ? <p className="text-secondary mb-0">No brief generated.</p> : (
                  <>
                    {brief.thesis && <p className="fs-5 fw-semibold">{brief.thesis}</p>}
                    <div className="row g-4">
                      {brief.core_concepts?.length ? (
                        <div className="col-md-6">
                          <h3 className="h6 text-uppercase text-secondary small">Core concepts</h3>
                          <ul className="mb-0">{brief.core_concepts.map((c) => <li key={c}>{c}</li>)}</ul>
                        </div>
                      ) : null}
                      {brief.key_principles?.length ? (
                        <div className="col-md-6">
                          <h3 className="h6 text-uppercase text-secondary small">Key principles</h3>
                          <ul className="mb-0">{brief.key_principles.map((p) => <li key={p}>{p}</li>)}</ul>
                        </div>
                      ) : null}
                    </div>
                    {brief.summary && <p className="text-body-secondary mt-4 mb-0" style={{ lineHeight: 1.7 }}>{brief.summary}</p>}
                  </>
                )
              )}
              {tab === 'graph' && (
                <>
                  <p className="text-secondary small mt-0">Click a node to inspect it.</p>
                  <GraphView graph={g} />
                </>
              )}
              {tab === 'chat' && <ChatTab jobId={job.job_id} graph={g} />}
              {tab === 'document' && (
                <>
                  <p className="text-secondary small mt-0">The original source — compare it against the Chat answers and citations.</p>
                  <DocumentViewer jobId={job.job_id} hasPdf={job.has_pdf} />
                </>
              )}
            </div>
          </div>

          {g.warnings?.length ? (
            <div className="alert alert-warning mt-3">{g.warnings.map((w, i) => <div key={i}>{w}</div>)}</div>
          ) : null}
        </>
      )}
    </div>
  );
}
