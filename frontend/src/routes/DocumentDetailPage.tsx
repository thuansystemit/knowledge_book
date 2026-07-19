import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  deleteJob, exportJob, getJob, reprocessJob, retryFailed, subscribeEvents,
  type JobDetail, type StageEvent,
} from '../api/jobs.api';
import { GraphView } from '../components/GraphView';
import { WorkflowStages } from '../components/WorkflowStages';
import { ChatTab } from '../components/ChatTab';
import { DocumentViewer } from '../components/DocumentViewer';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { useAuthStore } from '../store/authStore';
import { getApiError } from '../lib/utils';
import { getActivationStatus, recordRating, recordView, trackUpgradeClick } from '../api/activation.api';
import { UpgradePrompt } from '../components/UpgradePrompt';

type Tab = 'brief' | 'graph' | 'chapters' | 'chat' | 'document';

const TABS: { key: Tab; label: string }[] = [
  { key: 'brief',    label: 'Brief'         },
  { key: 'graph',    label: 'Knowledge graph' },
  { key: 'chapters', label: 'Chapter guide' },
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
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [reprocessDialogOpen, setReprocessDialogOpen] = useState(false);
  const [reprocessBusy, setReprocessBusy] = useState(false);
  const unsubRef = useRef<(() => void) | undefined>(undefined);

  // Activation instrumentation (ACT-01/02): one session id per visit, fire the
  // Concept-Map view event once, and track whether the user has rated.
  const sessionIdRef = useRef<string>('');
  if (!sessionIdRef.current) sessionIdRef.current = crypto.randomUUID();
  const viewFiredRef = useRef(false);
  const [rated, setRated] = useState<boolean | null>(null);
  const [ratingBusy, setRatingBusy] = useState(false);

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

  // Fire the Concept-Map view event once the graph is ready, and load whether
  // the user has already rated (to show/hide the thumbs prompt). ACT-01/02.
  useEffect(() => {
    if (!id || viewFiredRef.current) return;
    if (job?.status === 'done' && job.graph) {
      viewFiredRef.current = true;
      recordView(id, sessionIdRef.current).catch(() => {});
      getActivationStatus(id).then((s) => setRated(s.rated)).catch(() => setRated(false));
    }
  }, [id, job?.status, job?.graph]);

  const onRate = async (rating: 'up' | 'down') => {
    if (!id) return;
    setRatingBusy(true);
    try { await recordRating(id, rating); setRated(true); }
    finally { setRatingBusy(false); }
  };

  const onRetry = async () => {
    if (!id) return;
    setBusy(true);
    try { await retryFailed(id); load(); } finally { setBusy(false); }
  };

  /** Opens the confirm dialog — the actual deletion runs in confirmDelete. */
  const onDelete = () => setDeleteDialogOpen(true);

  const confirmDelete = async () => {
    if (!id) return;
    setDeleteBusy(true);
    try {
      await deleteJob(id);
      navigate('/documents', { replace: true });
    } catch (e: unknown) {
      setDeleteDialogOpen(false);
      alert(getApiError(e, 'Failed to delete document'));
    } finally {
      setDeleteBusy(false);
    }
  };

  /** Re-process (OUT-07): re-run the full extraction, replacing the outputs. */
  const onReprocessClick = () => setReprocessDialogOpen(true);
  const confirmReprocess = async () => {
    if (!id) return;
    setReprocessBusy(true);
    try {
      await reprocessJob(id);
      setReprocessDialogOpen(false);
      load();   // job is now 'running' — the workflow SSE takes over
    } catch (e: unknown) {
      setReprocessDialogOpen(false);
      alert(getApiError(e, 'Failed to re-process document'));
    } finally {
      setReprocessBusy(false);
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
  // Export is a Pro/Scholar feature (OUT-06); admins too.
  const canExport = currentUser?.role === 'admin'
    || currentUser?.plan === 'pro' || currentUser?.plan === 'scholar';
  const onExport = (fmt: 'md' | 'json') => {
    if (id) exportJob(id, fmt).catch(() => {});
  };

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
        <div className="d-flex gap-2 flex-shrink-0">
          {canExport && g && (
            <div className="btn-group">
              <button className="btn btn-outline-secondary btn-sm" onClick={() => onExport('md')}>
                <i className="bi bi-download me-1"></i>Markdown
              </button>
              <button className="btn btn-outline-secondary btn-sm" onClick={() => onExport('json')}>
                JSON
              </button>
            </div>
          )}
          {!canExport && g && (
            /* PAY-06: Free users see a specific, tracked export upgrade affordance */
            <Link
              to="/billing"
              onClick={() => void trackUpgradeClick('export', id)}
              className="btn btn-outline-secondary btn-sm"
              title="Export (Markdown/JSON) is a Pro feature"
            >
              <i className="bi bi-download me-1" aria-hidden="true"></i>Export
              <span className="badge bg-warning text-dark ms-1">Pro</span>
            </Link>
          )}
          {canDelete && (
            <button className="btn btn-outline-secondary btn-sm" onClick={onReprocessClick}
                    disabled={running} title="Re-run extraction on the source PDF">
              <i className="bi bi-arrow-clockwise me-1"></i>Re-process
            </button>
          )}
          {canDelete && (
            <button className="btn btn-outline-danger btn-sm" onClick={onDelete}>
              <i className="bi bi-trash me-1"></i>Delete
            </button>
          )}
        </div>
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
          {/* OCR quality gate (ING-06 / OCRQ-05).
              Two distinct signals:
              - low_confidence: the document is substantially scanned AND the mean
                confidence is below threshold -> strong warning, content is suspect.
              - otherwise, if OCR ran on a few pages of a mostly born-digital PDF
                (low_pages present but not flagged low_confidence) -> soft,
                page-scoped note; the bulk of the text came from a clean text layer. */}
          {g.ocr_quality?.low_confidence ? (
            <div className="alert alert-warning d-flex align-items-start gap-2 mb-4" role="alert">
              <i className="bi bi-exclamation-triangle-fill" aria-hidden="true" style={{ marginTop: 2 }} />
              <div>
                <strong>Low scan quality.</strong> This document was read by OCR at{' '}
                {g.ocr_quality.mean_confidence}% average confidence
                {g.ocr_quality.low_pages?.length ? ` on ${g.ocr_quality.low_pages.length} page(s)` : ''}.
                Concepts and answers may contain recognition errors — verify against the source PDF.
              </div>
            </div>
          ) : g.ocr_quality?.ocr_used && (g.ocr_quality.low_pages?.length ?? 0) > 0 ? (
            <div className="alert alert-info d-flex align-items-start gap-2 mb-4" role="alert">
              <i className="bi bi-info-circle-fill" aria-hidden="true" style={{ marginTop: 2 }} />
              <div>
                <strong>OCR used on {g.ocr_quality.low_pages!.length} page(s).</strong> Most of this
                document was read directly from its digital text layer; a few low-text pages fell
                back to OCR. Content is generally reliable — if a specific concept looks off, check
                those page(s) against the source PDF.
              </div>
            </div>
          ) : null}

          {/* ── Stat row ── */}
          <div className="row g-3 mb-4">
            {[
              { label: 'Concepts',  value: g.stats.node_count },
              { label: 'Relations', value: g.stats.edge_count },
              { label: 'PDF type',  value: g.document?.pdf_type ?? '—' },
              { label: 'Chunks',    value: g.document?.pages_chunked ?? '—' },
              // Admin-only LLM cost (EXT-02) — internal ops signal, not user-facing.
              ...(currentUser?.role === 'admin' && g.cost
                ? [{ label: 'Cost (LLM)', value: `$${g.cost.usd < 1 ? g.cost.usd.toFixed(4) : g.cost.usd.toFixed(2)}` }]
                : []),
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

                  {/* Free-tier concept-map cap (PAY-01 / PAY-06 contextual prompt) */}
                  {g.paywall?.capped && (
                    <UpgradePrompt
                      source="concept_cap"
                      jobId={id}
                      variant="warning"
                      icon="bi-diagram-3"
                      cta={`See all ${g.paywall.concepts_total} on Pro`}
                      message={
                        <>Showing <strong>{g.paywall.concepts_shown}</strong> of{' '}
                        <strong>{g.paywall.concepts_total}</strong> concepts on the Free plan.</>
                      }
                    />
                  )}

                  {/* Concept-map rating prompt (ACT-02) — shown once per user/doc */}
                  {rated === false && (
                    <div className="alert alert-light border d-flex align-items-center justify-content-between flex-wrap gap-2" role="group" aria-label="Rate the concept list">
                      <span style={{ color: 'var(--ink)' }}>Are these the right concepts?</span>
                      <div className="d-flex gap-2">
                        <button className="btn btn-outline-success btn-sm" onClick={() => onRate('up')} disabled={ratingBusy} aria-label="Thumbs up">
                          <i className="bi bi-hand-thumbs-up" aria-hidden="true" /> Yes
                        </button>
                        <button className="btn btn-outline-secondary btn-sm" onClick={() => onRate('down')} disabled={ratingBusy} aria-label="Thumbs down">
                          <i className="bi bi-hand-thumbs-down" aria-hidden="true" /> Not quite
                        </button>
                      </div>
                    </div>
                  )}
                  {rated === true && (
                    <p className="form-text" style={{ marginTop: '-0.25rem' }}>Thanks for the feedback.</p>
                  )}

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

              {/* ── Chapter guide tab (OUT-03) ── */}
              {tab === 'chapters' && (
                g.chapter_guide_locked ? (
                  <UpgradePrompt
                    source="chapter_guide"
                    jobId={id}
                    icon="bi-lock"
                    message="The Chapter Guide — per-chapter summaries, concepts introduced, and prerequisites — is a Pro feature."
                  />
                ) : g.chapter_guide?.length ? (
                  <div style={{ maxHeight: '62vh', overflowY: 'auto', paddingRight: '0.5rem' }}>
                    <div className="d-flex flex-column gap-3">
                    {g.chapter_guide.map((ch, i) => (
                      <div className="card" key={i}>
                        <div className="card-body" style={{ padding: '1.1rem 1.25rem' }}>
                          <div className="section-heading mb-1">{ch.chapter}</div>
                          <p className="mb-2" style={{ color: 'var(--ink)' }}>{ch.summary}</p>
                          {ch.concepts_introduced.length > 0 && (
                            <div className="mb-1" style={{ fontSize: '0.875rem' }}>
                              <span style={{ color: 'var(--muted)' }}>Introduces: </span>
                              {ch.concepts_introduced.map((c) => (
                                <span key={c.id} className="badge text-bg-secondary me-1 mb-1">{c.name}</span>
                              ))}
                            </div>
                          )}
                          {ch.prerequisites.length > 0 && (
                            <div style={{ fontSize: '0.875rem' }}>
                              <span style={{ color: 'var(--muted)' }}>Prerequisites: </span>
                              {ch.prerequisites.map((c) => (
                                <span key={c.id} className="badge rounded-pill text-bg-light border me-1 mb-1">{c.name}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    </div>
                  </div>
                ) : (
                  <p style={{ color: 'var(--muted)' }}>No chapters were detected in this document.</p>
                )
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

      <ConfirmDialog
        open={deleteDialogOpen}
        title="Delete document?"
        message={`"${job.title}" will be permanently deleted and cannot be recovered.`}
        confirmLabel="Delete"
        danger
        busy={deleteBusy}
        onConfirm={confirmDelete}
        onCancel={() => setDeleteDialogOpen(false)}
      />

      <ConfirmDialog
        open={reprocessDialogOpen}
        title="Re-process document?"
        message="This re-runs extraction on the source PDF and replaces the current Brief, Concept Map, and Chapter Guide. Chat history is kept."
        confirmLabel="Re-process"
        danger={false}
        busy={reprocessBusy}
        onConfirm={confirmReprocess}
        onCancel={() => setReprocessDialogOpen(false)}
      />
    </div>
  );
}
