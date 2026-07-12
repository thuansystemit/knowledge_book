import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  createPlan, getPlan, listPlans, listVersions, pinVersion, regeneratePlan,
  TRACKS, type PrepPlan, type PrepPlanDetail, type Track, type VersionMeta,
} from '../api/interview-prep.api';
import { getApiError } from '../lib/utils';
import { TrackCard } from '../components/interview-prep/TrackCard';
import { PrepProgressPanel } from '../components/interview-prep/PrepProgressPanel';
import { PrepPlanView } from '../components/interview-prep/PrepPlanView';
import { VersionSwitcher } from '../components/interview-prep/VersionSwitcher';

export function InterviewPrepPage() {
  const [plans, setPlans] = useState<PrepPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyTrack, setBusyTrack] = useState<Track | null>(null);
  const [pinBusy, setPinBusy] = useState(false);

  const [searchParams, setSearchParams] = useSearchParams();
  const selectedTrack = (searchParams.get('track') as Track | null) ?? null;

  // Version state for the selected track.
  const [versions, setVersions] = useState<VersionMeta[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [detail, setDetail] = useState<PrepPlanDetail | null>(null);

  const load = useCallback(async () => {
    try {
      setPlans(await listPlans());
    } catch (e) {
      setError(getApiError(e, 'Failed to load your prep plans'));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const trackPlans = plans.filter((p) => p.track === selectedTrack);
  const currentPlan = trackPlans.find((p) => p.is_current) ?? null;
  const inProgress = trackPlans.find((p) => p.status === 'pending' || p.status === 'generating') ?? null;
  const anchorId = currentPlan?.id ?? inProgress?.id ?? null;

  // Load the version list + choose a default selected version for the track.
  useEffect(() => {
    let cancelled = false;
    if (!selectedTrack || !anchorId) { setVersions([]); setSelectedVersionId(null); return; }
    listVersions(anchorId)
      .then((vl) => {
        if (cancelled) return;
        setVersions(vl.versions);
        setSelectedVersionId((prev) => {
          if (prev && vl.versions.some((v) => v.id === prev)) return prev;
          const cur = vl.versions.find((v) => v.is_current)
            ?? vl.versions.find((v) => v.status === 'done')
            ?? vl.versions[0];
          return cur?.id ?? null;
        });
      })
      .catch(() => { if (!cancelled) setVersions([]); });
    return () => { cancelled = true; };
  }, [selectedTrack, anchorId]);

  // Fetch full detail for the selected version (when it's a done version).
  const detailFetchedFor = useRef<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    const meta = versions.find((v) => v.id === selectedVersionId);
    if (meta && meta.status === 'done' && selectedVersionId) {
      if (detailFetchedFor.current !== selectedVersionId) {
        detailFetchedFor.current = selectedVersionId;
        setDetail(null);
        getPlan(selectedVersionId)
          .then((d) => { if (!cancelled) setDetail(d); })
          .catch(() => { if (!cancelled) { detailFetchedFor.current = null; setDetail(null); } });
      }
    } else {
      detailFetchedFor.current = null;
      setDetail(null);
    }
    return () => { cancelled = true; };
  }, [selectedVersionId, versions]);

  const openTrack = (plan: PrepPlan) => { setError(null); setSelectedVersionId(null); setSearchParams({ track: plan.track }); };
  const back = () => { setSearchParams({}, { replace: true }); };

  const generate = async (track: Track) => {
    setBusyTrack(track); setError(null);
    try {
      await createPlan(track);
      setSelectedVersionId(null);
      await load();
      setSearchParams({ track });
    } catch (e) { setError(getApiError(e, 'Failed to start generation')); }
    finally { setBusyTrack(null); }
  };

  const regenerate = async () => {
    if (!selectedTrack || !anchorId) return;
    setBusyTrack(selectedTrack); setError(null);
    try {
      await regeneratePlan(anchorId);
      setSelectedVersionId(null); // jump to the new in-progress version
      await load();
    } catch (e) { setError(getApiError(e, 'Failed to regenerate')); }
    finally { setBusyTrack(null); }
  };

  const onProgressComplete = useCallback(async () => {
    detailFetchedFor.current = null;
    setSelectedVersionId(null); // re-default to the new current version
    await load();
  }, [load]);

  const pin = async () => {
    if (!selectedVersionId) return;
    setPinBusy(true); setError(null);
    try {
      const d = await pinVersion(selectedVersionId);
      setDetail(d);
      await load();
    } catch (e) { setError(getApiError(e, 'Failed to pin version')); }
    finally { setPinBusy(false); }
  };

  const selectedMeta = versions.find((v) => v.id === selectedVersionId) ?? null;
  const viewingCurrent = selectedMeta?.is_current ?? true;
  const nextVersionNum = (versions.reduce((m, v) => Math.max(m, v.version), 0) || 0) + 1;
  const hasSelectedTrack = !!selectedTrack;

  return (
    <div className="container py-4" style={{ maxWidth: 960 }}>
      <div className="d-flex align-items-center justify-content-between mb-1">
        <h2 className="mb-0" style={{ color: 'var(--ink)' }}>Interview Prep</h2>
        {hasSelectedTrack && (
          <button className="btn btn-link btn-sm" onClick={back}>
            <i className="bi bi-arrow-left me-1" aria-hidden="true" />All tracks
          </button>
        )}
      </div>
      <p className="text-muted mb-4" style={{ fontSize: '0.9rem' }}>
        Generate a study plan, checklist, and practice questions grounded in the
        technical documents in your library. Each regeneration is saved as a new version.
      </p>

      {error && (
        <div className="alert alert-danger" role="alert">
          <i className="bi bi-exclamation-circle me-2" aria-hidden="true" />{error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-5">
          <span className="spinner-border text-primary" role="status" aria-hidden="true" />
        </div>
      ) : !hasSelectedTrack ? (
        /* ── Track picker ── */
        <div className="row g-3">
          {TRACKS.map((t) => (
            <div className="col-12 col-md-4" key={t.id}>
              <TrackCard
                track={t.id}
                label={t.label}
                blurb={t.blurb}
                plan={plans.find((p) => p.track === t.id && p.is_current)
                  ?? plans.find((p) => p.track === t.id)}
                busy={busyTrack === t.id}
                onGenerate={generate}
                onView={openTrack}
              />
            </div>
          ))}
        </div>
      ) : (
        /* ── Selected-track detail ── */
        <div>
          {/* In-progress generation strip (shown above the current version) */}
          {inProgress && (
            <div className="mb-3">
              <PrepProgressPanel planId={inProgress.id} onComplete={onProgressComplete} />
            </div>
          )}

          {/* Version switcher + regenerate */}
          {versions.length > 0 && (
            <div className="d-flex flex-wrap align-items-center justify-content-between">
              <VersionSwitcher versions={versions} selectedId={selectedVersionId ?? ''} onChange={setSelectedVersionId} />
              <button
                className="btn btn-outline-primary btn-sm mb-3"
                onClick={regenerate}
                disabled={!!inProgress || busyTrack === selectedTrack}
                title={inProgress ? 'A generation is already running' : undefined}
              >
                <i className="bi bi-arrow-repeat me-1" aria-hidden="true" />
                Regenerate → v{nextVersionNum}
              </button>
            </div>
          )}

          {/* Read-only banner for historical (non-current) versions */}
          {selectedMeta && !viewingCurrent && (
            <div className="alert alert-secondary d-flex align-items-center justify-content-between flex-wrap gap-2" role="status">
              <span>
                <i className="bi bi-clock-history me-2" aria-hidden="true" />
                You’re viewing <strong>v{selectedMeta.version}</strong> — a past version (read-only).
              </span>
              {selectedMeta.status === 'done' && (
                <button className="btn btn-primary btn-sm" onClick={pin} disabled={pinBusy}>
                  {pinBusy ? 'Pinning…' : 'Pin as Current'}
                </button>
              )}
            </div>
          )}

          {/* Selected version body */}
          {selectedMeta?.status === 'error' ? (
            <div className="alert alert-warning">
              <div className="fw-semibold mb-1">
                <i className="bi bi-exclamation-triangle me-2" aria-hidden="true" />
                This version failed to generate
              </div>
              <div className="mb-2">{selectedMeta.error}</div>
              {!inProgress && (
                <button className="btn btn-outline-secondary btn-sm" onClick={regenerate}>Try again</button>
              )}
            </div>
          ) : detail ? (
            <PrepPlanView plan={detail} />
          ) : selectedMeta?.status === 'done' ? (
            <div className="text-center py-5">
              <span className="spinner-border text-primary" role="status" aria-hidden="true" />
            </div>
          ) : !inProgress && versions.length === 0 ? (
            <div className="text-muted py-4">No versions yet.</div>
          ) : null}
        </div>
      )}
    </div>
  );
}
