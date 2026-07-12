import { useEffect, useRef, useState } from 'react';
import { subscribePrepStream, type PrepStatus } from '../../api/interview-prep.api';

/**
 * Live generation progress for a plan. Opens the SSE stream on mount, renders the
 * running list of stage details, and calls `onComplete(status)` on the terminal
 * frame so the parent can refetch the finished plan.
 */
export function PrepProgressPanel({
  planId, onComplete,
}: {
  planId: string;
  onComplete: (status: PrepStatus) => void;
}) {
  const [lines, setLines] = useState<string[]>([]);
  const doneRef = useRef(false);

  useEffect(() => {
    doneRef.current = false;
    setLines([]);
    const unsub = subscribePrepStream(
      planId,
      (e) => { if (e.detail) setLines((l) => [...l, e.detail as string]); },
      (status) => { if (!doneRef.current) { doneRef.current = true; onComplete(status); } },
      (msg) => { if (!doneRef.current) { doneRef.current = true; setLines((l) => [...l, `Error: ${msg}`]); } },
    );
    return unsub;
  }, [planId, onComplete]);

  return (
    <div className="card" style={{ border: '1px solid var(--border)' }}>
      <div className="card-body">
        <div className="d-flex align-items-center gap-2 mb-3">
          <span className="spinner-border spinner-border-sm text-primary" role="status" aria-hidden="true" />
          <strong style={{ color: 'var(--ink)' }}>Building your prep plan…</strong>
        </div>
        <ul className="list-unstyled mb-0" style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>
          {lines.map((l, i) => (
            <li key={i} className="d-flex align-items-center gap-2 py-1">
              <i className="bi bi-check2 text-success" aria-hidden="true" />
              {l}
            </li>
          ))}
          {lines.length === 0 && <li className="py-1">Scanning your library…</li>}
        </ul>
      </div>
    </div>
  );
}
