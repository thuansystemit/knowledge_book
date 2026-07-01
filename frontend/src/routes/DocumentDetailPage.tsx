import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  deleteJob, getJob, retryFailed, subscribeEvents,
  type JobDetail, type StageEvent,
} from '../api/jobs.api';
import { GraphView } from '../components/GraphView';
import { WorkflowStages } from '../components/WorkflowStages';
import { ChatTab } from '../components/ChatTab';

type Tab = 'brief' | 'graph' | 'chat';

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
          // Re-attach to the live stream; the server replays full history, so
          // progress is restored across refreshes and after a retry kicks off.
          setEvents([]);
          subscribeEvents(
            id,
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

  if (notFound) return <p className="muted">Document not found (or not yours).</p>;
  if (!job) return <p className="muted">Loading…</p>;

  const g = job.graph;
  const brief = g?.brief;
  const running = job.status === 'running';
  const failedCount = (g?.failed_chunks?.length ?? 0);

  return (
    <div>
      <div className="page-head">
        <h1>{job.title}</h1>
        <div className="head-actions">
          <Link to="/documents" className="link">← All documents</Link>
          <button className="btn-ghost danger" onClick={onDelete}>Delete</button>
        </div>
      </div>

      {running && (
        <div className="panel">
          <h2>Workflow</h2>
          <WorkflowStages events={events} />
        </div>
      )}
      {job.status === 'error' && <div className="panel err">Extraction failed: {job.error}</div>}

      {!running && failedCount > 0 && (
        <div className="panel warn retry-bar">
          <span>⚠ {failedCount} chunk(s) failed extraction — you can retry just those and merge them in.</span>
          <button className="btn" onClick={onRetry} disabled={busy}>
            {busy ? 'Retrying…' : `Retry ${failedCount} failed`}
          </button>
        </div>
      )}

      {g && (
        <>
          <div className="stats-row panel">
            <Stat label="Concepts" value={g.stats.node_count} />
            <Stat label="Relations" value={g.stats.edge_count} />
            <Stat label="PDF type" value={g.document?.pdf_type ?? '—'} />
            <Stat label="Chunks" value={g.document?.pages_chunked ?? '—'} />
          </div>

          <div className="tabs">
            <button className={tab === 'brief' ? 'active' : ''} onClick={() => setTab('brief')}>Brief</button>
            <button className={tab === 'graph' ? 'active' : ''} onClick={() => setTab('graph')}>Concept graph</button>
            <button className={tab === 'chat' ? 'active' : ''} onClick={() => setTab('chat')}>Chat</button>
          </div>

          {tab === 'brief' && (
            <div className="panel">
              {!brief ? <p className="muted">No brief generated.</p> : (
                <>
                  {brief.thesis && <p className="thesis">{brief.thesis}</p>}
                  <div className="brief-grid">
                    {brief.core_concepts?.length ? (
                      <div><h3>Core concepts</h3><ul>{brief.core_concepts.map((c) => <li key={c}>{c}</li>)}</ul></div>
                    ) : null}
                    {brief.key_principles?.length ? (
                      <div><h3>Key principles</h3><ul>{brief.key_principles.map((p) => <li key={p}>{p}</li>)}</ul></div>
                    ) : null}
                  </div>
                  {brief.summary && <p className="summary">{brief.summary}</p>}
                </>
              )}
            </div>
          )}
          {tab === 'graph' && (
            <div className="panel">
              <p className="muted" style={{ marginTop: 0 }}>Click a node to inspect it.</p>
              <GraphView graph={g} />
            </div>
          )}
          {tab === 'chat' && (
            <div className="panel">
              <ChatTab jobId={job.job_id} graph={g} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="stat">
      <div className="stat-val">{value}</div>
      <div className="stat-lbl">{label}</div>
    </div>
  );
}
