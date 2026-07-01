import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createJob } from '../api/jobs.api';

export function UploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const { job_id } = await createJob(file);
      // Go straight to the document page — its URL is trackable across refreshes.
      navigate(`/documents/${job_id}`);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? 'upload failed');
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="page-head"><h1>New extraction</h1></div>
      <div className="panel upload-panel">
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          hidden
          onChange={(e) => e.target.files?.[0] && start(e.target.files[0])}
        />
        <button className="btn" disabled={busy} onClick={() => inputRef.current?.click()}>
          {busy ? 'Uploading…' : 'Upload a PDF'}
        </button>
        <span className="muted">Digital or scanned — OCR runs automatically.</span>
      </div>
      {error && <div className="panel err">Error: {error}</div>}
    </div>
  );
}
