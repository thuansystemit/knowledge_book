import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createJob } from '../api/jobs.api';
import { getModels, type ModelOption } from '../api/models.api';
import { listCategories, type Category } from '../api/categories.api';

export function UploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [model, setModel] = useState<string>('');
  const [cats, setCats] = useState<Category[]>([]);
  const [category, setCategory] = useState<string>('');

  useEffect(() => {
    getModels().then((m) => {
      setModels(m.models);
      setModel(m.default_extraction_model);
    }).catch(() => { /* models optional */ });
    listCategories().then((cs) => {
      const uploadable = cs.filter((c) => c.my_grant === 'upload' || c.my_grant === 'manage');
      setCats(uploadable);
      const general = uploadable.find((c) => c.name === 'General') ?? uploadable[0];
      if (general) setCategory(general.id);
    }).catch(() => {});
  }, []);

  const start = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const { job_id } = await createJob(file, model || undefined, category || undefined);
      navigate(`/documents/${job_id}`);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? 'upload failed');
      setBusy(false);
    }
  };

  const current = models.find((m) => m.model_id === model);

  return (
    <div>
      <h1 className="h3 fw-bold mb-4">New extraction</h1>
      <div className="card border-0 shadow-sm rounded-4" style={{ maxWidth: 640 }}>
        <div className="card-body p-4">
          {cats.length > 0 && (
            <div className="mb-3">
              <label className="form-label small fw-semibold text-secondary">Category</label>
              <select className="form-select" value={category} onChange={(e) => setCategory(e.target.value)} disabled={busy}>
                {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          )}
          {models.length > 0 && (
            <div className="mb-3">
              <label className="form-label small fw-semibold text-secondary">Extraction model</label>
              <select className="form-select" value={model} onChange={(e) => setModel(e.target.value)} disabled={busy}>
                {models.map((m) => (
                  <option key={m.model_id} value={m.model_id}>
                    {m.label}{m.is_local ? '' : ` · ${m.credit_cost_extraction} credit${m.credit_cost_extraction === 1 ? '' : 's'}/doc`}
                  </option>
                ))}
              </select>
              {current && !current.is_local && (
                <div className="form-text text-warning-emphasis">
                  <i className="bi bi-stars me-1"></i>Premium model — higher accuracy, billed per document.
                </div>
              )}
              {current?.is_local && (
                <div className="form-text">Free, runs locally. Pick a premium model for faster / higher-accuracy extraction.</div>
              )}
            </div>
          )}
          <div
            className={`border border-2 border-dashed rounded-4 text-center p-5 ${drag ? 'border-primary bg-light' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) start(f); }}
            style={{ cursor: busy ? 'default' : 'pointer' }}
            onClick={() => !busy && inputRef.current?.click()}
          >
            <input ref={inputRef} type="file" accept="application/pdf" hidden
              onChange={(e) => e.target.files?.[0] && start(e.target.files[0])} />
            <i className={`bi ${busy ? 'bi-hourglass-split' : 'bi-cloud-arrow-up'} fs-1 text-primary`}></i>
            <p className="fw-semibold mt-3 mb-1">{busy ? 'Uploading…' : 'Drop a PDF here or click to browse'}</p>
            <p className="text-secondary small mb-0">Digital or scanned — OCR runs automatically.</p>
          </div>
          {error && <div className="alert alert-danger py-2 small mt-3 mb-0">{error}</div>}
        </div>
      </div>
    </div>
  );
}
