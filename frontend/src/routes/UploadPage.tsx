import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createJob } from '../api/jobs.api';
import { getModels, type ModelOption } from '../api/models.api';
import { listCategories, type Category } from '../api/categories.api';
import { getApiError } from '../lib/utils';
import { useAuthStore } from '../store/authStore';
import { ROLE_LABEL } from '../lib/constants';
import { Select } from '../components/Select';

export function UploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const user = useAuthStore((s) => s.user);

  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [model, setModel] = useState<string>('');
  const [cats, setCats] = useState<Category[]>([]);
  const [lockedCats, setLockedCats] = useState<Category[]>([]);
  const [category, setCategory] = useState<string>('');

  useEffect(() => {
    getModels()
      .then((m) => {
        setModels(m.models);
        setModel(m.default_extraction_model);
      })
      .catch(() => {});

    listCategories()
      .then((all) => {
        const uploadable = all.filter(
          (c) => c.my_grant === 'upload' || c.my_grant === 'manage',
        );
        const locked = all.filter(
          (c) => !uploadable.find((u) => u.id === c.id),
        );
        setCats(uploadable);
        setLockedCats(locked);
        const general = uploadable.find((c) => c.name === 'General') ?? uploadable[0];
        if (general) setCategory(general.id);
      })
      .catch(() => {});
  }, []);

  const start = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const { job_id } = await createJob(file, model || undefined, category || undefined);
      navigate(`/documents/${job_id}`);
    } catch (err: unknown) {
      setError(getApiError(err, 'Upload failed'));
      setBusy(false);
    }
  };

  const currentModel = models.find((m) => m.model_id === model);
  const roleLabel = user ? (ROLE_LABEL[user.role] ?? user.role) : '';

  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>
      {/* "Signed in as" pill — top right of content area */}
      <div className="d-flex justify-content-end mb-3">
        <span className="signed-in-pill">
          Signed in as <strong>&nbsp;{roleLabel}</strong>
        </span>
      </div>

      {/* Centered header */}
      <div className="text-center mb-4">
        <h1 className="page-title mb-2">Add a document to your archive</h1>
        <p className="page-subtitle">Sort it into a category so it's easy to find later.</p>
      </div>

      {/* Drop zone */}
      <div
        className={`drop-zone${drag ? ' drop-zone--drag' : ''}${busy ? ' drop-zone--busy' : ''}`}
        onDragOver={(e) => { e.preventDefault(); if (!busy) setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          const f = e.dataTransfer.files?.[0];
          if (f && !busy) start(f);
        }}
        onClick={() => !busy && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !busy) inputRef.current?.click();
        }}
        aria-label="Drop a file here or click to browse"
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.docx,.txt"
          hidden
          onChange={(e) => e.target.files?.[0] && start(e.target.files[0])}
        />

        {/* Square icon (terracotta rounded square with white box icon) */}
        <div className="drop-zone-icon" aria-hidden="true">
          <i className={`bi ${busy ? 'bi-hourglass-split' : 'bi-stop-fill'}`}></i>
        </div>

        <p className="fw-semibold mb-1" style={{ fontSize: '0.9375rem', color: 'var(--ink)' }}>
          {busy ? 'Uploading…' : 'Drop files, or click to choose'}
        </p>
        <p className="mb-0" style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>
          PDF, DOCX, TXT — up to 25MB each
        </p>
      </div>

      {error && (
        <div className="alert alert-danger mt-3" role="alert">
          <i className="bi bi-exclamation-circle me-2"></i>
          {error}
        </div>
      )}

      {/* Category selector */}
      {(cats.length > 0 || lockedCats.length > 0) && (
        <div className="mt-4">
          <div className="d-flex justify-content-between align-items-baseline mb-1">
            <span className="form-label mb-0">Category</span>
            <span style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>
              Showing categories available to your role
            </span>
          </div>
          <div className="cat-pills">
            {cats.map((c) => (
              <button
                key={c.id}
                type="button"
                className={`cat-pill${category === c.id ? ' cat-pill--selected' : ''}`}
                onClick={() => setCategory(c.id)}
                disabled={busy}
              >
                {c.name}
              </button>
            ))}
            {lockedCats.map((c) => (
              <span key={c.id} className="cat-pill cat-pill--locked">
                <i className="bi bi-lock" style={{ fontSize: '0.75rem' }}></i>
                {c.name} · Admin only
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Model selector (keep functionality, style as a small select) */}
      {models.length > 0 && (
        <div className="mt-3">
          <label className="form-label" htmlFor="upload-model">Extraction model</label>
          <div style={{ maxWidth: 320 }}>
            <Select
              id="upload-model"
              value={model}
              onChange={setModel}
              options={models.map((m) => ({
                value: m.model_id,
                label:
                  m.label +
                  (!m.is_local
                    ? ` · ${m.credit_cost_extraction} credit${m.credit_cost_extraction === 1 ? '' : 's'}/doc`
                    : ''),
              }))}
              disabled={busy}
            />
          </div>
          {currentModel && !currentModel.is_local && (
            <div className="form-text mt-1" style={{ color: '#d97706' }}>
              <i className="bi bi-stars me-1"></i>
              Premium model — higher accuracy, billed per document.
            </div>
          )}
          {currentModel?.is_local && (
            <div className="form-text mt-1">
              Free, runs locally. Pick a premium model for faster or higher-accuracy extraction.
            </div>
          )}
        </div>
      )}

      {/* Primary CTA */}
      <div className="text-center mt-4">
        <button
          type="button"
          className="btn btn-primary px-5 py-2"
          disabled={busy || !category}
          onClick={() => inputRef.current?.click()}
        >
          {busy ? (
            <>
              <span
                className="spinner-border spinner-border-sm me-2"
                role="status"
                aria-hidden="true"
              ></span>
              Uploading…
            </>
          ) : (
            'Add to archive'
          )}
        </button>
      </div>
    </div>
  );
}
