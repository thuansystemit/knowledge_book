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
import { useAuthStore } from '../store/authStore';
import { getApiError } from '../lib/utils';

type Tab = 'brief' | 'graph' | 'chat' | 'document';

const TABS: { key: Tab; label: string }[] = [
  { key: 'brief',    label: 'Brief'         },
  { key: 'graph',    label: 'Knowledge graph' },
  { key: 'chat',     label: 'Chat'           },
  { key: 'document', label: 'Document'       },
];

export function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const [job, setJob] = useState<JobDetail | null>(null);
  const [events, setEvents] = useState<StageEvent[]>([]);
  const [tab, setTab] = useState<Tab>('brief');
  const [notFound, setNotFound] = useState(false);
  const [busy, setBusy] = useState(false);
  const [graphMode, setGraphMode] = useState<'graph' | 'list'>('graph');
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
    try {
      await deleteJob(id);
      navigate('/documents', { replace: true });
    } catch (e: unknown) {
      alert(getApiError(e, 'Failed to delete document'));
    }
  };

  if (notFound) return (
    <div className="empty-state">
      <i className="bi bi-file-earmark-x empty-state-icon"></i>
      <div className="empty-state-title">Document not found</div>
      <div className="empty-state-text">
        This document doesn't exist or you don't have access to it.
      </div>
      <Link to="/documents" className="btn btn-primary btn-sm">
        Back to documents
      </Link>
    </div>
  );

  if (!job) return (
    <div
      className="d-flex align-items-center gap-2 mt-4"
      style={{ color: 'var(--muted)', fontSize: '0.875rem' }}
    >
      <div
        className="spinner-border spinner-border-sm"
        role="status"
        style={{ color: 'var(--brand)' }}
      ></div>
      Loading…
    </div>
  );

  const g = job.graph;
  const brief = g?.brief;
  const running = job.status === 'running';
  const failedCount = g?.failed_chunks?.length ?? 0;
  // Mirror backend `_owned_job`: only the owner or an admin may delete. Viewers
  // never own documents, so they never see the Delete action.
  const canDelete = currentUser?.role === 'admin' || job.user_id === currentUser?.id;

  return (
    <div>
      {/* ── Page header ── */}
      <div className="d-flex align-items-start justify-content-between mb-4">
        <div>
          <Link to="/documents" className="back-link">
            <i className="bi bi-arrow-left"></i>All documents
          </Link>
          {/* Serif title */}
          <h1 className="page-title">{job.title}</h1>
        </div>
        {canDelete && (
          <button className="btn btn-outline-danger btn-sm flex-shrink-0" onClick={onDelete}>
            <i className="bi bi-trash me-1"></i>Delete
          </button>
        )}
      </div>

      {/* ── Workflow (running only) ── */}
      {running && (
        <div className="card mb-3">
          <div className="card-body">
            <p className="section-heading mb-3">
              <i className="bi bi-cpu me-2" style={{ color: 'var(--brand)' }}></i>
              Extraction in progress
            </p>
            <WorkflowStages events={events} />
          </div>
        </div>
      )}

      {/* ── Error banner ── */}
      {job.status === 'error' && (
        <div className="alert alert-danger mb-3" role="alert">
          <i className="bi bi-x-circle me-2"></i>
          Extraction failed: {job.error}
        </div>
      )}

      {/* ── Partial failure ── */}
      {!running && failedCount > 0 && (
        <div
          className="alert alert-warning d-flex align-items-center justify-content-between mb-3"
          role="alert"
        >
          <span>
            <i className="bi bi-exclamation-triangle me-2"></i>
            {failedCount} chunk{failedCount > 1 ? 's' : ''} failed — retry to merge them in.
          </span>
          <button
            className="btn btn-sm btn-warning ms-3"
            onClick={onRetry}
            disabled={busy}
          >
            {busy ? 'Retrying…' : `Retry ${failedCount} failed`}
          </button>
        </div>
      )}

      {g && (
        <>
          {/* ── Stat row ── */}
          <div className="row g-3 mb-4">
            {[
              { label: 'Concepts',  value: g.stats.node_count },
              { label: 'Relations', value: g.stats.edge_count },
              { label: 'PDF type',  value: g.document?.pdf_type ?? '—' },
              { label: 'Chunks',    value: g.document?.pages_chunked ?? '—' },
            ].map((s) => (
              <div className="col-6 col-md-3" key={s.label}>
                <div className="stat-card">
                  <div className="stat-value">{s.value}</div>
                  <div className="stat-label">{s.label}</div>
                </div>
              </div>
            ))}
          </div>

          {/* ── Tabs ── */}
          <ul className="nav nav-pills gap-1 mb-3" role="tablist">
            {TABS.map((tb) => (
              <li className="nav-item" key={tb.key}>
                <button
                  className={`nav-link${tab === tb.key ? ' active' : ''}`}
                  onClick={() => setTab(tb.key)}
                  role="tab"
                  aria-selected={tab === tb.key}
                >
                  {tb.label}
                </button>
              </li>
            ))}
          </ul>

          {/* ── Tab panels ── */}
          <div className="card">
            <div className="card-body" style={{ padding: '1.5rem' }}>
              {/* ── Brief tab — thesis + findings in right-rail layout ── */}
              {tab === 'brief' && (
                !brief ? (
                  <div className="empty-state" style={{ padding: '2rem 1rem' }}>
                    <i className="bi bi-card-text empty-state-icon"></i>
                    <div className="empty-state-title">No brief generated</div>
                  </div>
                ) : (
                  <div className="d-flex gap-4">
                    {/* Main column */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {brief.thesis && (
                        <p
                          style={{
                            fontSize: '1rem',
                            fontWeight: 600,
                            color: 'var(--ink)',
                            lineHeight: 1.5,
                            marginBottom: '1.5rem',
                          }}
                        >
                          {brief.thesis}
                        </p>
                      )}
                      <div className="row g-4">
                        {brief.core_concepts?.length ? (
                          <div className="col-md-6">
                            <div className="brief-section-label">Core concepts</div>
                            <ul className="brief-list">
                              {brief.core_concepts.map((c) => <li key={c}>{c}</li>)}
                            </ul>
                          </div>
                        ) : null}
                        {brief.key_principles?.length ? (
                          <div className="col-md-6">
                            <div className="brief-section-label">Key principles</div>
                            <ul className="brief-list">
                              {brief.key_principles.map((p) => <li key={p}>{p}</li>)}
                            </ul>
                          </div>
                        ) : null}
                      </div>
                      {brief.summary && (
                        <p
                          style={{
                            color: 'var(--muted)',
                            lineHeight: 1.75,
                            fontSize: '0.9375rem',
                            marginTop: '1.25rem',
                            marginBottom: 0,
                          }}
                        >
                          {brief.summary}
                        </p>
                      )}
                    </div>

                    {/* Right rail — key findings */}
                    {(brief.core_concepts?.length || brief.key_principles?.length) ? (
                      <div
                        className="findings-rail d-none d-md-block"
                        style={{
                          borderLeft: '1px solid var(--border)',
                          paddingLeft: '1.5rem',
                          minWidth: 200,
                          maxWidth: 240,
                        }}
                      >
                        <div className="findings-rail-title">Key findings</div>
                        {[
                          ...(brief.core_concepts ?? []).slice(0, 3),
                          ...(brief.key_principles ?? []).slice(0, 2),
                        ].map((item) => (
                          <div key={item} className="findings-rail-item">{item}</div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                )
              )}

              {/* ── Graph tab with Graph/List toggle ── */}
              {tab === 'graph' && (
                <>
                  <div className="d-flex align-items-center justify-content-between mb-3">
                    <p style={{ fontSize: '0.8125rem', color: 'var(--muted)', margin: 0 }}>
                      Click a node to inspect it.
                    </p>
                    {/* Segmented Graph/List toggle */}
                    <div className="graph-toggle" role="group" aria-label="View mode">
                      <button
                        className={`graph-toggle-btn${graphMode === 'graph' ? ' active' : ''}`}
                        onClick={() => setGraphMode('graph')}
                        aria-pressed={graphMode === 'graph'}
                      >
                        Graph
                      </button>
                      <button
                        className={`graph-toggle-btn${graphMode === 'list' ? ' active' : ''}`}
                        onClick={() => setGraphMode('list')}
                        aria-pressed={graphMode === 'list'}
                      >
                        List
                      </button>
                    </div>
                  </div>

                  {graphMode === 'graph' ? (
                    <GraphView graph={g} />
                  ) : (
                    /* List view — nodes as a table */
                    <div className="table-responsive">
                      <table className="table table-hover align-middle mb-0">
                        <thead className="table-light">
                          <tr>
                            <th className="ps-3">Concept</th>
                            <th>Type</th>
                            <th>Confidence</th>
                          </tr>
                        </thead>
                        <tbody>
                          {g.nodes.map((n) => (
                            <tr key={n.id}>
                              <td className="ps-3" style={{ fontWeight: 500, color: 'var(--ink)' }}>
                                {n.name}
                              </td>
                              <td>
                                <span className="badge text-bg-secondary">{n.type}</span>
                              </td>
                              <td style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--muted)' }}>
                                {n.confidence != null ? `${Math.round(n.confidence * 100)}%` : '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}

              {/* ── Chat tab ── */}
              {tab === 'chat' && <ChatTab jobId={job.job_id} graph={g} />}

              {/* ── Document tab with right-rail key findings ── */}
              {tab === 'document' && (
                <div className="d-flex gap-4">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p
                      style={{
                        fontSize: '0.8125rem',
                        color: 'var(--muted)',
                        marginBottom: '0.75rem',
                      }}
                    >
                      The original source — compare it against Chat answers and citations.
                    </p>
                    <DocumentViewer jobId={job.job_id} hasPdf={job.has_pdf} />
                  </div>

                  {/* Right rail */}
                  {brief && (brief.core_concepts?.length || brief.key_principles?.length) ? (
                    <div
                      className="findings-rail d-none d-lg-block"
                      style={{
                        borderLeft: '1px solid var(--border)',
                        paddingLeft: '1.5rem',
                        minWidth: 200,
                        maxWidth: 240,
                        flexShrink: 0,
                      }}
                    >
                      <div className="findings-rail-title">Key findings</div>
                      {[
                        ...(brief.core_concepts ?? []).slice(0, 3),
                        ...(brief.key_principles ?? []).slice(0, 2),
                      ].map((item) => (
                        <div key={item} className="findings-rail-item">{item}</div>
                      ))}
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          </div>

          {g.warnings?.length ? (
            <div className="alert alert-warning mt-3" role="alert">
              {g.warnings.map((w, i) => <div key={i}>{w}</div>)}
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
