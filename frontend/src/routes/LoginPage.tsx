import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api/auth.api';
import { useAuthStore } from '../store/authStore';

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
      navigate(user.role === 'admin' ? '/admin/users' : '/documents', { replace: true });
    } catch {
      setErr('Invalid email or password.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="d-flex align-items-center justify-content-center min-vh-100 p-3">
      <div className="card shadow-sm border-0 rounded-4" style={{ width: 400 }}>
        <div className="card-body p-4 p-md-5">
          <div className="app-brand fs-4 mb-1 d-flex align-items-center gap-2">
            <i className="bi bi-diagram-3-fill" style={{ color: '#4f46e5' }}></i>KnowledgeBook
          </div>
          <p className="text-secondary mb-4">Sign in to your workspace</p>
          <form onSubmit={submit}>
            <div className="mb-3">
              <label className="form-label small fw-semibold text-secondary">Email</label>
              <input className="form-control" value={email} autoFocus
                onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="mb-3">
              <label className="form-label small fw-semibold text-secondary">Password</label>
              <input type="password" className="form-control" value={password}
                onChange={(e) => setPassword(e.target.value)} />
            </div>
            {err && <div className="alert alert-danger py-2 small">{err}</div>}
            <button className="btn btn-primary w-100 fw-semibold py-2" disabled={busy || !email || !password}>
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
