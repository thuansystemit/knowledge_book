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
      <div className="page-head"><h1>Users</h1></div>

      <div className="panel">
        <h2>Create user</h2>
        <form className="user-form" onSubmit={create}>
          <input placeholder="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <input placeholder="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input placeholder="password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <button className="btn" disabled={!form.email || !form.password}>Add</button>
        </form>
        {err && <p className="err">{err}</p>}
      </div>

      <div className="panel">
        <table className="tbl">
          <thead><tr><th>Email</th><th>Name</th><th>Role</th><th>Active</th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>{u.name || '—'}</td>
                <td>
                  <select value={u.role} disabled={u.id === me?.id} onChange={(e) => changeRole(u, e.target.value)}>
                    {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </td>
                <td>
                  <button
                    className={`pill ${u.is_active ? 'on' : 'off'}`}
                    disabled={u.id === me?.id}
                    onClick={() => toggleActive(u)}
                    title={u.id === me?.id ? 'You cannot change your own account' : ''}
                  >
                    {u.is_active ? 'active' : 'inactive'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
