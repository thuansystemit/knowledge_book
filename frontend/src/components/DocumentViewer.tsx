import { useEffect, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { fetchPdfObjectUrl } from '../api/jobs.api';

// pdf.js worker (matched to the installed version) from CDN — consistent with
// the app's other CDN assets, avoids bundling the worker.
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const clamp = (z: number) => Math.min(3, Math.max(0.4, z));

/** Renders the stored source PDF with pdf.js, with zoom + page controls, so the
 * user can inspect the source and compare it against chat answers. */
export function DocumentViewer({ jobId, hasPdf }: { jobId: string; hasPdf?: boolean }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1); // 1.0 == fit container width
  const wrapRef = useRef<HTMLDivElement>(null);
  const [cw, setCw] = useState(760);

  useEffect(() => {
    if (!hasPdf) return;
    let objUrl: string | null = null;
    let alive = true;
    fetchPdfObjectUrl(jobId)
      .then((u) => { if (alive) { objUrl = u; setUrl(u); } else URL.revokeObjectURL(u); })
      .catch(() => alive && setError('Could not load the source file.'));
    return () => { alive = false; if (objUrl) URL.revokeObjectURL(objUrl); };
  }, [jobId, hasPdf]);

  useEffect(() => {
    const measure = () => setCw((wrapRef.current?.clientWidth ?? 780) - 24);
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, []);

  if (!hasPdf) {
    return (
      <div className="alert alert-secondary mb-0">
        <i className="bi bi-info-circle me-2"></i>
        No source file is stored for this document — it was extracted before file
        storage was added. Re-upload the PDF to view it here and compare against chat.
      </div>
    );
  }
  if (error) return <div className="alert alert-danger mb-0">{error}</div>;
  if (!url) return <p className="text-secondary">Loading document…</p>;

  const pageWidth = Math.round(cw * zoom);

  return (
    <div ref={wrapRef}>
      {/* toolbar */}
      <div className="d-flex align-items-center gap-2 mb-2 flex-wrap">
        <div className="btn-group btn-group-sm" role="group">
          <button className="btn btn-outline-secondary" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
            <i className="bi bi-chevron-left"></i>
          </button>
          <span className="btn btn-outline-secondary disabled">{page} / {numPages || '…'}</span>
          <button className="btn btn-outline-secondary" disabled={page >= numPages} onClick={() => setPage((p) => Math.min(numPages, p + 1))}>
            <i className="bi bi-chevron-right"></i>
          </button>
        </div>

        <div className="btn-group btn-group-sm ms-auto" role="group">
          <button className="btn btn-outline-secondary" title="Zoom out" onClick={() => setZoom((z) => clamp(z - 0.25))}>
            <i className="bi bi-zoom-out"></i>
          </button>
          <span className="btn btn-outline-secondary disabled" style={{ width: 66 }}>{Math.round(zoom * 100)}%</span>
          <button className="btn btn-outline-secondary" title="Zoom in" onClick={() => setZoom((z) => clamp(z + 0.25))}>
            <i className="bi bi-zoom-in"></i>
          </button>
        </div>
        <button className="btn btn-sm btn-outline-secondary" onClick={() => setZoom(1)} title="Fit width">
          <i className="bi bi-arrows-fullscreen me-1"></i>Fit
        </button>
        <a className="btn btn-sm btn-outline-secondary" href={url} target="_blank" rel="noreferrer" title="Open in new tab">
          <i className="bi bi-box-arrow-up-right"></i>
        </a>
      </div>

      {/* page area */}
      <div className="pdf-scroll d-flex justify-content-center">
        <Document
          file={url}
          onLoadSuccess={({ numPages }) => setNumPages(numPages)}
          onLoadError={() => setError('Failed to render the PDF.')}
          loading={<p className="text-secondary p-4">Rendering…</p>}
        >
          <Page
            pageNumber={page}
            width={pageWidth}
            renderTextLayer={false}
            renderAnnotationLayer={false}
          />
        </Document>
      </div>
    </div>
  );
}
