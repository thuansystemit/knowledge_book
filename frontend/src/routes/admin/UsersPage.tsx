import { useEffect, useState } from 'react';
import { listUsers, createUser, updateUser, type AdminUser } from '../../api/auth.api';
import { useAuthStore } from '../../store/authStore';

const ROLES = ['admin', 'analyst', 'viewer'];

export function UsersPage() {
  const me = useAuthStore((s) => s.user);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [form, setForm] = useState({ email: '', password: '', name: '', role: 'analyst' });
  const [err, setErr] = useState<string | null>(null);

  const load = () => listUsers().then(setUsers);
  useEffect(() => { load(); }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    try {
      await createUser(form);
      setForm({ email: '', password: '', name: '', role: 'analyst' });
      load();
    } catch (e: any) {
      setErr(e?.response?.data?.detail ?? 'failed to create user');
    }
  };
  const changeRole = async (u: AdminUser, role: string) => { await updateUser(u.id, { role }); load(); };
  const toggleActive = async (u: AdminUser) => { await updateUser(u.id, { is_active: !u.is_active }); load(); };

  return (
    <div>
      <h1 className="h3 fw-bold mb-4">Users</h1>

      <div className="card border-0 shadow-sm rounded-4 mb-3">
        <div className="card-body p-4">
          <h2 className="h6 fw-bold mb-3">Create user</h2>
          <form className="row g-2 align-items-end" onSubmit={create}>
            <div className="col-md"><input className="form-control" placeholder="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
            <div className="col-md"><input className="form-control" placeholder="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="col-md"><input className="form-control" type="password" placeholder="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
            <div className="col-md-2">
              <select className="form-select" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div className="col-md-auto"><button className="btn btn-primary" disabled={!form.email || !form.password}>Add</button></div>
          </form>
          {err && <div className="alert alert-danger py-2 small mt-3 mb-0">{err}</div>}
        </div>
      </div>

      <div className="card border-0 shadow-sm rounded-4">
        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr className="small text-secondary text-uppercase">
                <th className="ps-4">Email</th><th>Name</th><th>Role</th><th className="pe-4">Active</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="ps-4">{u.email}</td>
                  <td>{u.name || '—'}</td>
                  <td>
                    <select className="form-select form-select-sm" style={{ width: 130 }}
                      value={u.role} disabled={u.id === me?.id} onChange={(e) => changeRole(u, e.target.value)}>
                      {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td className="pe-4">
                    <button className={`btn btn-sm ${u.is_active ? 'btn-success' : 'btn-outline-secondary'}`}
                      disabled={u.id === me?.id} onClick={() => toggleActive(u)}
                      title={u.id === me?.id ? 'You cannot change your own account' : ''}>
                      {u.is_active ? 'active' : 'inactive'}
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
