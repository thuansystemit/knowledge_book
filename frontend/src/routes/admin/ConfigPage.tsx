import { useEffect, useState } from 'react';
import {
  getModelAssignments, setOrgModelPolicy, setUserModelDefaults,
  type ModelAssignments, type UserModelRow,
} from '../../api/config.api';
import { Select } from '../../components/Select';

export function ConfigPage() {
  const [data, setData] = useState<ModelAssignments | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [byo, setByo] = useState(false);

  const load = () =>
    getModelAssignments().then((d) => { setData(d); setByo(d.policy.require_byo_key); });
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const flash = (msg: string) => {
    setSaved(msg);
    setTimeout(() => setSaved(null), 1800);
  };

  const assign = async (
    u: UserModelRow,
    field: 'default_extraction_model' | 'default_chat_model',
    value: string,
  ) => {
    const body = field === 'default_extraction_model'
      ? { default_extraction_model: value || undefined }
      : { default_chat_model: value || undefined };
    await setUserModelDefaults(u.id, body);
    setData((d) => {
      if (!d) return d;
      const users = d.users.map((x) => {
        if (x.id !== u.id) return x;
        return field === 'default_extraction_model'
          ? { ...x, default_extraction_model: value || null }
          : { ...x, default_chat_model: value || null };
      });
      return { ...d, users };
    });
    flash(`Saved ${u.email}`);
  };

  const saveByo = async (v: boolean) => {
    if (!data) return;
    setByo(v);
    await setOrgModelPolicy(data.org_id, { require_byo_key: v });
    flash('Organization policy saved');
  };

  if (!data) return (
    <div className="d-flex align-items-center gap-2 mt-4" style={{ color: 'var(--muted)', fontSize: '0.875rem' }}>
      <div className="spinner-border spinner-border-sm" role="status" style={{ color: 'var(--brand)' }}></div>
      Loading…
    </div>
  );

  const label = (id: string | null) =>
    id ? (data.models.find((m) => m.model_id === id)?.label ?? id) : null;
  const defaultHint = `Default (${label(data.system_default) ?? data.system_default})`;

  return (
    <div>
      <div className="mb-4">
        <h1 className="page-title">Configuration</h1>
        <p className="page-subtitle">
          Assign the LLM model each user gets for extraction and chat. Blank = organization/system default.
        </p>
      </div>

      {/* Floating save toast */}
      {saved && (
        <div
          className="alert alert-success position-fixed"
          style={{ zIndex: 1080, top: '1rem', right: '1rem' }}
          role="status"
          aria-live="polite"
        >
          <i className="bi bi-check-circle me-2"></i>{saved}
        </div>
      )}

      {/* Org policy */}
      <div className="card mb-3">
        <div className="card-body" style={{ padding: '1.25rem 1.5rem' }}>
          <h2 className="section-heading mb-3">Organization policy</h2>
          <div className="form-check form-switch mb-2">
            <input
              className="form-check-input"
              type="checkbox"
              id="byo-key"
              checked={byo}
              onChange={(e) => saveByo(e.target.checked)}
            />
            <label className="form-check-label" htmlFor="byo-key">
              Require bring-your-own API key for premium models
            </label>
          </div>
          <div className="form-text">
            System default model:{' '}
            <span style={{ fontWeight: 600, color: '#334155' }}>
              {label(data.system_default) ?? data.system_default}
            </span>
          </div>
        </div>
      </div>

      {/* Per-user model table */}
      <div className="card">
        <div className="card-header">
          <h2 className="section-heading">Per-user models</h2>
        </div>
        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th className="ps-4">User</th>
                <th>Role</th>
                <th style={{ minWidth: 220 }}>Extraction model</th>
                <th style={{ minWidth: 220 }}>Chat model</th>
              </tr>
            </thead>
            <tbody>
              {data.users.map((u) => (
                <tr key={u.id}>
                  <td className="ps-4">
                    <div style={{ fontWeight: 500 }}>{u.email}</div>
                    {u.name && (
                      <div style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>{u.name}</div>
                    )}
                  </td>
                  <td>
                    <span className="badge text-bg-light text-uppercase">{u.role}</span>
                  </td>
                  <td>
                    <Select
                      value={u.default_extraction_model ?? ''}
                      onChange={(v) => assign(u, 'default_extraction_model', v)}
                      options={[
                        { value: '', label: defaultHint },
                        ...data.models.map((m) => ({ value: m.model_id, label: m.label })),
                      ]}
                      size="sm"
                    />
                  </td>
                  <td>
                    <Select
                      value={u.default_chat_model ?? ''}
                      onChange={(v) => assign(u, 'default_chat_model', v)}
                      options={[
                        { value: '', label: defaultHint },
                        ...data.models.map((m) => ({ value: m.model_id, label: m.label })),
                      ]}
                      size="sm"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
