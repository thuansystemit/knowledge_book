import { useEffect, useState } from 'react';
import {
  addPermission, createCategory, deleteCategory,
  listCategories, listPermissions, revokePermission,
  type Category, type CatPermission,
} from '../../api/categories.api';
import { listUsers, type AdminUser } from '../../api/users.api';
import { getApiError } from '../../lib/utils';
import { Select } from '../../components/Select';

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
  const [grantErr, setGrantErr] = useState<string | null>(null);
  // Cache perms per category for table display
  const [catPerms, setCatPerms] = useState<Record<string, CatPermission[]>>({});

  const load = () =>
    listCategories().then((cs) => {
      setCats(cs);
      // Refresh all perms for display
      Promise.all(cs.map((c) => listPermissions(c.id).then((p) => [c.id, p] as const)))
        .then((pairs) =>
          setCatPerms(Object.fromEntries(pairs)),
        )
        .catch(() => {});
    });

  useEffect(() => {
    load();
    listUsers().then(setUsers).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    try {
      await createCategory(name.trim());
      setName('');
      load();
    } catch (e: unknown) {
      setErr(getApiError(e, 'Failed to create'));
    }
  };

  const remove = async (c: Category) => {
    if (!confirm(`Delete category "${c.name}"?`)) return;
    try {
      await deleteCategory(c.id);
      if (manage?.id === c.id) setManage(null);
      load();
    } catch (e: unknown) {
      alert(getApiError(e, 'Failed to delete'));
    }
  };

  const openManage = async (c: Category) => {
    setManage(c);
    setGrantErr(null);
    const p = await listPermissions(c.id);
    setPerms(p);
  };

  const grant = async () => {
    if (!manage || !grantUser) return;
    setGrantErr(null);
    try {
      await addPermission(manage.id, grantUser, grantType);
      const p = await listPermissions(manage.id);
      setPerms(p);
      setCatPerms((prev) => ({ ...prev, [manage.id]: p }));
      setGrantUser('');
    } catch (e: unknown) {
      setGrantErr(getApiError(e, 'Failed to grant permission'));
    }
  };

  const revoke = async (p: CatPermission) => {
    if (!manage) return;
    await revokePermission(manage.id, p.id);
    const next = await listPermissions(manage.id);
    setPerms(next);
    setCatPerms((prev) => ({ ...prev, [manage.id]: next }));
  };

  const userName = (id: string) => users.find((u) => u.id === id)?.email ?? id;

  /** Derive role-like labels for "CAN UPLOAD" column: show admin/editor pills */
  const uploadRoles = (cid: string) => {
    const p = catPerms[cid] ?? [];
    const types = Array.from(new Set(
      p.filter((x) => x.grant_type === 'upload' || x.grant_type === 'manage')
        .map((x) => x.grant_type === 'manage' ? 'Admin' : 'Editor'),
    ));
    return types.length > 0 ? types : ['Admin'];
  };

  /** Derive "CAN VIEW & CHAT" plain text */
  const viewLabel = (cid: string) => {
    const p = catPerms[cid] ?? [];
    const grantees = p.filter((x) =>
      ['view', 'upload', 'manage'].includes(x.grant_type),
    );
    if (grantees.length === 0) return 'Admin only';
    if (grantees.some((x) => x.grant_type === 'view')) return 'Everyone';
    return 'Admin, Viewer';
  };

  return (
    <div>
      {/* ── Page header ── */}
      <div className="d-flex align-items-start justify-content-between mb-1">
        <div>
          <h1 className="page-title">Category access control</h1>
          <p className="page-subtitle mt-2">
            A category must exist before documents can be filed into it. Access is granted per role.
          </p>
        </div>
        <button
          className="btn btn-primary flex-shrink-0 ms-4"
          style={{ marginTop: '0.25rem' }}
          onClick={() => {
            const n = prompt('New category name:');
            if (n?.trim()) {
              setName(n.trim());
              createCategory(n.trim()).then(() => load()).catch((e) => alert(getApiError(e, 'failed')));
            }
          }}
        >
          + New category
        </button>
      </div>

      {err && (
        <div className="alert alert-danger mb-3" role="alert">
          <i className="bi bi-exclamation-circle me-2"></i>
          {err}
        </div>
      )}

      {/* ── Main table ── */}
      <div className="row g-3 mt-1">
        <div className={manage ? 'col-lg-7' : 'col-12'}>
          <div className="card">
            <div className="table-responsive">
              <table className="table table-hover align-middle mb-0">
                <thead className="table-light">
                  <tr>
                    <th className="ps-4">Category</th>
                    <th>Documents</th>
                    <th>Can Upload</th>
                    <th>Can View &amp; Chat</th>
                    <th className="pe-4">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {cats.map((c) => (
                    <tr key={c.id}>
                      <td className="ps-4" style={{ fontWeight: 600, color: 'var(--ink)' }}>
                        {c.name}
                      </td>
                      <td style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--body)' }}>
                        {c.doc_count}
                      </td>
                      <td>
                        {uploadRoles(c.id).map((r) => (
                          <span key={r} className="role-pill">{r}</span>
                        ))}
                      </td>
                      <td style={{ color: 'var(--body)' }}>{viewLabel(c.id)}</td>
                      <td className="pe-4">
                        <button
                          className="tbl-action me-2"
                          onClick={() => openManage(c)}
                          aria-label={`Edit permissions for ${c.name}`}
                        >
                          Edit
                        </button>
                        {c.name !== 'General' && (
                          <>
                            <span style={{ color: 'var(--border)' }}>·</span>
                            <button
                              className="tbl-action ms-2"
                              onClick={() => remove(c)}
                              aria-label={`Delete ${c.name}`}
                            >
                              Delete
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <p style={{ fontSize: '0.8125rem', color: 'var(--muted)', marginTop: '0.875rem' }}>
            Only Admins manage categories and access. Editors and Viewers only see categories they've been granted.
          </p>
        </div>

        {/* ── Permissions side panel ── */}
        {manage && (
          <div className="col-lg-5">
            <div className="card">
              <div className="card-body" style={{ padding: '1.25rem 1.5rem' }}>
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <h2 className="section-heading mb-0">
                    Permissions — {manage.name}
                  </h2>
                  <button
                    className="btn-close"
                    onClick={() => setManage(null)}
                    aria-label="Close"
                    style={{ fontSize: '0.75rem' }}
                  ></button>
                </div>

                {/* Grant form */}
                <div className="d-flex gap-2 mb-3">
                  <Select
                    value={grantUser}
                    onChange={setGrantUser}
                    options={[
                      { value: '', label: 'Select user…' },
                      ...users.map((u) => ({ value: u.id, label: u.email })),
                    ]}
                    size="sm"
                  />
                  <Select
                    value={grantType}
                    onChange={setGrantType}
                    options={GRANTS.map((g) => ({ value: g, label: g }))}
                    size="sm"
                    width={110}
                    className="flex-shrink-0"
                  />
                  <button
                    className="btn btn-sm btn-primary flex-shrink-0"
                    disabled={!grantUser}
                    onClick={grant}
                  >
                    Grant
                  </button>
                </div>

                {grantErr && (
                  <div className="alert alert-danger py-2 mb-3" role="alert" style={{ fontSize: '0.8125rem' }}>
                    <i className="bi bi-exclamation-circle me-2"></i>
                    {grantErr}
                  </div>
                )}

                {/* Permission list */}
                {perms.length === 0 ? (
                  <p style={{ fontSize: '0.875rem', color: 'var(--muted)', margin: 0 }}>
                    No grants yet — this category is admin-only.
                  </p>
                ) : (
                  <div>
                    {perms.map((p) => (
                      <div
                        key={p.id}
                        className="d-flex justify-content-between align-items-center"
                        style={{
                          padding: '0.5rem 0',
                          borderBottom: '1px solid var(--border)',
                          fontSize: '0.875rem',
                        }}
                      >
                        <span>
                          {userName(p.user_id)}{' '}
                          <span className="role-pill ms-1">{p.grant_type}</span>
                        </span>
                        <button
                          className="btn btn-sm btn-outline-danger"
                          onClick={() => revoke(p)}
                        >
                          Revoke
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Inline create form for quick add */}
                <div className="mt-4 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
                  <h3 style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--muted)', marginBottom: '0.5rem' }}>
                    ADD CATEGORY
                  </h3>
                  <form className="d-flex gap-2" onSubmit={create}>
                    <input
                      className="form-control form-control-sm"
                      placeholder="Category name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                    <button className="btn btn-sm btn-primary flex-shrink-0" disabled={!name.trim()}>
                      Add
                    </button>
                  </form>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
