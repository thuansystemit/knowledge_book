import { useEffect, useState } from 'react';
import { listUsers, createUser, updateUser, type AdminUser } from '../../api/users.api';
import { useAuthStore } from '../../store/authStore';
import { getApiError } from '../../lib/utils';
import { Select } from '../../components/Select';

const ROLES = ['admin', 'analyst', 'viewer'];

export function UsersPage() {
  const me = useAuthStore((s) => s.user);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [form, setForm] = useState({ email: '', password: '', name: '', role: 'analyst' });
  const [err, setErr] = useState<string | null>(null);

  const load = () => listUsers().then(setUsers);
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    try {
      await createUser(form);
      setForm({ email: '', password: '', name: '', role: 'analyst' });
      load();
    } catch (err: unknown) {
      setErr(getApiError(err, 'failed to create user'));
    }
  };

  const changeRole   = async (u: AdminUser, role: string) => { await updateUser(u.id, { role }); load(); };
  const toggleActive = async (u: AdminUser) => { await updateUser(u.id, { is_active: !u.is_active }); load(); };

  return (
    <div>
      <h1 className="page-title mb-4">Users</h1>

      {/* Create form */}
      <div className="card mb-3">
        <div className="card-body" style={{ padding: '1.25rem 1.5rem' }}>
          <h2 className="section-heading mb-3">Create user</h2>
          <form className="row g-2 align-items-end" onSubmit={create}>
            <div className="col-md">
              <label className="form-label" htmlFor="new-email">Email</label>
              <input
                id="new-email"
                className="form-control"
                placeholder="user@example.com"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div className="col-md">
              <label className="form-label" htmlFor="new-name">Name</label>
              <input
                id="new-name"
                className="form-control"
                placeholder="Full name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="col-md">
              <label className="form-label" htmlFor="new-password">Password</label>
              <input
                id="new-password"
                className="form-control"
                type="password"
                placeholder="Password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </div>
            <div className="col-md-2">
              <label className="form-label" htmlFor="new-role">Role</label>
              <Select
                id="new-role"
                value={form.role}
                onChange={(role) => setForm({ ...form, role })}
                options={ROLES.map((r) => ({ value: r, label: r }))}
              />
            </div>
            <div className="col-md-auto">
              <button className="btn btn-primary" disabled={!form.email || !form.password}>
                Add user
              </button>
            </div>
          </form>
          {err && (
            <div className="alert alert-danger mt-3 mb-0" role="alert">
              <i className="bi bi-exclamation-circle me-2"></i>{err}
            </div>
          )}
        </div>
      </div>

      {/* Users table */}
      <div className="card">
        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th className="ps-4">Email</th>
                <th>Name</th>
                <th>Role</th>
                <th className="pe-4">Status</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="ps-4" style={{ fontWeight: 500 }}>{u.email}</td>
                  <td style={{ color: u.name ? 'inherit' : 'var(--muted)' }}>{u.name || '—'}</td>
                  <td>
                    <Select
                      value={u.role}
                      onChange={(role) => changeRole(u, role)}
                      options={ROLES.map((r) => ({ value: r, label: r }))}
                      disabled={u.id === me?.id}
                      size="sm"
                      width={130}
                    />
                  </td>
                  <td className="pe-4">
                    <button
                      className={`btn btn-sm ${u.is_active ? 'btn-outline-secondary' : 'btn-outline-secondary'}`}
                      disabled={u.id === me?.id}
                      onClick={() => toggleActive(u)}
                      title={u.id === me?.id ? 'You cannot change your own account' : ''}
                      style={u.is_active
                        ? { color: '#15803d', borderColor: 'rgba(22,163,74,.3)', background: 'rgba(22,163,74,.07)' }
                        : undefined
                      }
                    >
                      {u.is_active ? 'Active' : 'Inactive'}
                    </button>
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
