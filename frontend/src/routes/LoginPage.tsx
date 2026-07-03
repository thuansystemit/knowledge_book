import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api/auth.api';
import { useAuthStore } from '../store/authStore';
import { APP_NAME } from '../lib/constants';
import { AppFooter } from '../components/AppFooter';

export function LoginPage() {
  const setAuth = useAuthStore((s) => s.setAuth);
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const { access_token, user } = await login(email, password);
      setAuth(access_token, user);
      navigate(user.role === 'admin' ? '/admin/categories' : '/documents', { replace: true });
    } catch {
      setErr('Invalid email or password.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      {/* Flex-grow region that centers the login card */}
      <div className="login-main">
      <div className="login-card">
        <div className="login-brand">{APP_NAME}</div>
        <p className="page-subtitle" style={{ marginBottom: '1.75rem' }}>
          Sign in to your archive
        </p>

        <form onSubmit={submit}>
          <div className="mb-3">
            <label className="form-label" htmlFor="login-email">
              Email
            </label>
            <input
              id="login-email"
              className="form-control"
              type="email"
              value={email}
              autoFocus
              autoComplete="email"
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="mb-4">
            <label className="form-label" htmlFor="login-password">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              className="form-control"
              value={password}
              autoComplete="current-password"
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {err && (
            <div className="alert alert-danger mb-3" role="alert">
              <i className="bi bi-exclamation-circle me-2"></i>
              {err}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary w-100 py-2"
            disabled={busy || !email || !password}
          >
            {busy ? (
              <>
                <span
                  className="spinner-border spinner-border-sm me-2"
                  role="status"
                  aria-hidden="true"
                ></span>
                Signing in…
              </>
            ) : (
              'Sign in'
            )}
          </button>
        </form>
      </div>
      </div>{/* /login-main */}
      <AppFooter />
    </div>
  );
}
