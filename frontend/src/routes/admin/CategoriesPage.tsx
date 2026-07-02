import { useEffect, useState } from 'react';
import {
  addPermission, createCategory, deleteCategory, listCategories, listPermissions,
  revokePermission, type Category, type CatPermission,
} from '../../api/categories.api';
import { listUsers, type AdminUser } from '../../api/auth.api';

const GRANTS = ['view', 'upload', 'manage'];

export function CategoriesPage() {
  const [cats, setCats] = useState<Category[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [name, setName] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [manage, setManage] = useState<Category | null>(null);
  const [perms, setPerms] = useState<CatPermission[]>([]);
  const [grantUser, setGrantUser] = useState('');
  const [grantType, setGrantType] = useState('view');

  const load = () => listCategories().then(setCats);
  useEffect(() => { load(); listUsers().then(setUsers).catch(() => {}); }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(null);
    try { await createCategory(name.trim()); setName(''); load(); }
    catch (e: any) { setErr(e?.response?.data?.detail ?? 'failed to create'); }
  };
  const remove = async (c: Category) => {
    if (!confirm(`Delete category "${c.name}"?`)) return;
    try { await deleteCategory(c.id); if (manage?.id === c.id) setManage(null); load(); }
    catch (e: any) { alert(e?.response?.data?.detail ?? 'failed to delete'); }
  };
  const openManage = async (c: Category) => { setManage(c); setPerms(await listPermissions(c.id)); };
  const grant = async () => {
    if (!manage || !grantUser) return;
    await addPermission(manage.id, grantUser, grantType);
    setPerms(await listPermissions(manage.id)); setGrantUser('');
  };
  const revoke = async (p: CatPermission) => {
    if (!manage) return;
    await revokePermission(manage.id, p.id);
    setPerms(await listPermissions(manage.id));
  };

  const userName = (id: string) => users.find((u) => u.id === id)?.email ?? id;

  return (
    <div>
      <h1 className="h3 fw-bold mb-4">Categories</h1>

      <div className="card border-0 shadow-sm rounded-4 mb-3">
        <div className="card-body p-4">
          <h2 className="h6 fw-bold mb-3">Create category</h2>
          <form className="d-flex gap-2" onSubmit={create}>
            <input className="form-control" placeholder="Category name" value={name} onChange={(e) => setName(e.target.value)} />
            <button className="btn btn-primary" disabled={!name.trim()}>Add</button>
          </form>
          {err && <div className="alert alert-danger py-2 small mt-3 mb-0">{err}</div>}
        </div>
      </div>

      <div className="row g-3">
        <div className={manage ? 'col-lg-7' : 'col-12'}>
          <div className="card border-0 shadow-sm rounded-4">
            <div className="table-responsive">
              <table className="table table-hover align-middle mb-0">
                <thead className="table-light">
                  <tr className="small text-secondary text-uppercase">
                    <th className="ps-4">Name</th><th>Docs</th><th className="pe-4 text-end">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {cats.map((c) => (
                    <tr key={c.id}>
                      <td className="ps-4 fw-semibold">{c.name}</td>
                      <td>{c.doc_count}</td>
                      <td className="pe-4 text-end">
                        <button className="btn btn-sm btn-outline-secondary me-2" onClick={() => openManage(c)}>
                          <i className="bi bi-people me-1"></i>Permissions
                        </button>
                        {c.name !== 'General' && (
                          <button className="btn btn-sm btn-outline-danger" onClick={() => remove(c)}>Delete</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {manage && (
          <div className="col-lg-5">
            <div className="card border-0 shadow-sm rounded-4">
              <div className="card-body p-4">
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <h2 className="h6 fw-bold mb-0">Permissions · {manage.name}</h2>
                  <button className="btn-close" onClick={() => setManage(null)}></button>
                </div>
                <div className="d-flex gap-2 mb-3">
                  <select className="form-select form-select-sm" value={grantUser} onChange={(e) => setGrantUser(e.target.value)}>
                    <option value="">Select user…</option>
                    {users.map((u) => <option key={u.id} value={u.id}>{u.email}</option>)}
                  </select>
                  <select className="form-select form-select-sm" style={{ width: 120 }} value={grantType} onChange={(e) => setGrantType(e.target.value)}>
                    {GRANTS.map((g) => <option key={g} value={g}>{g}</option>)}
                  </select>
                  <button className="btn btn-sm btn-primary" disabled={!grantUser} onClick={grant}>Grant</button>
                </div>
                {perms.length === 0 ? (
                  <p className="text-secondary small mb-0">No grants yet — this category is admin-only.</p>
                ) : (
                  <ul className="list-group list-group-flush">
                    {perms.map((p) => (
                      <li key={p.id} className="list-group-item d-flex justify-content-between align-items-center px-0">
                        <span>{userName(p.user_id)} <span className="badge text-bg-light ms-1">{p.grant_type}</span></span>
                        <button className="btn btn-sm btn-outline-danger" onClick={() => revoke(p)}>Revoke</button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
