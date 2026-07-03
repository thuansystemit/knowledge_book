import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { logout as apiLogout, getMe } from '../api/auth.api';
import { getModels } from '../api/models.api';
import { setMyModelDefaults } from '../api/me.api';
import { ROLE_LABEL } from '../lib/constants';
import { Select } from '../components/Select';
import { getApiError } from '../lib/utils';
import type { ModelOption } from '../api/models.api';
import type { User } from '../store/authStore';

function formatMemberSince(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

function buildInitials(u: User | null): string {
  return (u?.name || u?.email || '?')
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase())
    .join('');
}

export function ProfilePage() {
  const { user, setAuth, clear, accessToken } = useAuthStore();
  const navigate = useNavigate();

  const [profile, setProfile] = useState<User | null>(user);
  const [profileLoading, setProfileLoading] = useState(true);

  const [models, setModels] = useState<ModelOption[]>([]);
  const [extractionModel, setExtractionModel] = useState('');
  const [chatModel, setChatModel] = useState('');
  const [modelSaving, setModelSaving] = useState(false);
  const [modelSuccess, setModelSuccess] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);

  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    // Refresh profile from server so created_at and live fields are accurate
    getMe()
      .then((me) => {
        setProfile(me);
        if (accessToken) setAuth(accessToken, me);
      })
      .catch(() => {
        setProfile(user);
      })
      .finally(() => setProfileLoading(false));

    getModels()
      .then((res) => setModels(res.models))
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const onLogout = async () => {
    setLoggingOut(true);
    try {
      await apiLogout();
    } finally {
      clear();
      navigate('/login', { replace: true });
    }
  };

  const onSaveModelPrefs = async () => {
    setModelSaving(true);
    setModelSuccess(false);
    setModelError(null);
    try {
      await setMyModelDefaults({
        default_extraction_model: extractionModel || null,
        default_chat_model: chatModel || null,
      });
      setModelSuccess(true);
    } catch (e: unknown) {
      setModelError(getApiError(e, 'Failed to save preferences'));
    } finally {
      setModelSaving(false);
    }
  };

  const initials = buildInitials(profile);
  const roleLabel = ROLE_LABEL[profile?.role ?? ''] ?? profile?.role ?? '';

  const modelSelectOptions = [
    { value: '', label: 'System default' },
    ...models.map((m) => ({ value: m.model_id, label: m.label })),
  ];

  return (
    <div>
      {/* Page header */}
      <div className="mb-4">
        <h1 className="page-title">Your profile</h1>
        <p className="page-subtitle">Manage your account details and preferences</p>
      </div>

      <div style={{ maxWidth: 680 }}>
        {/* ── Identity card ── */}
        <div className="card mb-4">
          <div className="card-body" style={{ padding: '1.5rem' }}>
            <div className="d-flex align-items-start gap-4">
              {/* Large circular avatar */}
              <div
                aria-hidden="true"
                style={{
                  width: 72,
                  height: 72,
                  borderRadius: '50%',
                  background: 'var(--brand-light)',
                  color: 'var(--brand)',
                  fontSize: '1.5rem',
                  fontWeight: 700,
                  letterSpacing: '0.025em',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: '2px solid var(--brand-muted)',
                  flexShrink: 0,
                  userSelect: 'none',
                }}
              >
                {initials}
              </div>

              {/* Text block */}
              <div style={{ flex: 1, minWidth: 0 }}>
                {/* Name */}
                <div
                  style={{
                    fontFamily: "'Playfair Display', Georgia, 'Times New Roman', serif",
                    fontSize: '1.25rem',
                    fontWeight: 700,
                    color: 'var(--ink)',
                    lineHeight: 1.2,
                    marginBottom: '0.25rem',
                  }}
                >
                  {profileLoading ? (
                    <span style={{ color: 'var(--muted)', fontStyle: 'italic' }}>Loading…</span>
                  ) : (
                    profile?.name || profile?.email
                  )}
                </div>

                {/* Email */}
                {profile?.email && (
                  <div style={{ fontSize: '0.875rem', color: 'var(--muted)', marginBottom: '0.5rem' }}>
                    {profile.email}
                  </div>
                )}

                {/* Role + status row */}
                <div className="d-flex align-items-center flex-wrap gap-2">
                  <span className="role-pill">{roleLabel}</span>

                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      fontSize: '0.8125rem',
                      color: profile?.is_active ? '#15803d' : 'var(--muted)',
                    }}
                  >
                    <span
                      style={{
                        width: 7,
                        height: 7,
                        borderRadius: '50%',
                        background: profile?.is_active ? '#22c55e' : 'var(--border)',
                        flexShrink: 0,
                      }}
                    />
                    {profile?.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>

                {/* Member since (hidden when created_at absent) */}
                {profile?.created_at && (
                  <div
                    style={{
                      fontSize: '0.8125rem',
                      color: 'var(--muted)',
                      marginTop: '0.5rem',
                    }}
                  >
                    Member since {formatMemberSince(profile.created_at)}
                  </div>
                )}
              </div>
            </div>

            {/* Divider + logout */}
            <div
              style={{
                borderTop: '1px solid var(--border)',
                marginTop: '1.25rem',
                paddingTop: '1.25rem',
              }}
            >
              <button
                className="btn btn-outline-danger btn-sm"
                onClick={onLogout}
                disabled={loggingOut}
              >
                <i className="bi bi-box-arrow-right me-1" aria-hidden="true" />
                {loggingOut ? 'Signing out…' : 'Sign out'}
              </button>
            </div>
          </div>
        </div>

        {/* ── Model preferences card ── */}
        <div className="card">
          <div className="card-header">
            <div className="section-heading">Model preferences</div>
          </div>
          <div className="card-body" style={{ padding: '1.25rem' }}>
            <p className="form-text mb-3" style={{ marginTop: 0 }}>
              Set your personal default models for extraction and chat. These override the
              organisation default for documents you create. The server does not provide a way
              to read your currently-saved defaults, so the selectors start at{' '}
              <strong>System default</strong> each time you visit. Choose a model and press{' '}
              <strong>Save preferences</strong> to update your preference.
            </p>

            <div className="row g-3">
              <div className="col-sm-6">
                <label className="form-label" htmlFor="pref-extraction">
                  Extraction model
                </label>
                <Select
                  id="pref-extraction"
                  value={extractionModel}
                  onChange={setExtractionModel}
                  options={modelSelectOptions}
                  placeholder="System default"
                  ariaLabel="Extraction model"
                  disabled={models.length === 0}
                />
              </div>
              <div className="col-sm-6">
                <label className="form-label" htmlFor="pref-chat">
                  Chat model
                </label>
                <Select
                  id="pref-chat"
                  value={chatModel}
                  onChange={setChatModel}
                  options={modelSelectOptions}
                  placeholder="System default"
                  ariaLabel="Chat model"
                  disabled={models.length === 0}
                />
              </div>
            </div>

            {modelError && (
              <div className="alert alert-danger mt-3" role="alert">
                {modelError}
              </div>
            )}
            {modelSuccess && (
              <div className="alert alert-success mt-3" role="status">
                Preferences saved.
              </div>
            )}

            <div className="mt-3">
              <button
                className="btn btn-primary btn-sm"
                onClick={onSaveModelPrefs}
                disabled={modelSaving || models.length === 0}
              >
                {modelSaving ? 'Saving…' : 'Save preferences'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
