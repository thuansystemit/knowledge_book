import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { logout as apiLogout } from '../api/auth.api';

const NAV = [
  { to: '/documents', label: 'Documents', icon: 'bi-folder2-open', roles: ['admin', 'analyst'] },
  { to: '/documents/new', label: 'New extraction', icon: 'bi-plus-circle', roles: ['admin', 'analyst'] },
  { to: '/admin/categories', label: 'Categories', icon: 'bi-folder', roles: ['admin'] },
  { to: '/admin/users', label: 'Users', icon: 'bi-people', roles: ['admin'] },
];

export function AppLayout() {
  const { user, clear } = useAuthStore();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const onLogout = async () => {
    try { await apiLogout(); } finally { clear(); navigate('/login', { replace: true }); }
  };

  const initials = (user?.name || user?.email || '?')
    .split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((s) => s[0]?.toUpperCase()).join('');

  return (
    <div className="d-flex" style={{ minHeight: '100vh' }}>
      {/* Sidebar */}
      <aside className="text-white p-3 flex-shrink-0" style={{ width: 240, background: '#0f172a' }}>
        <div className="app-brand fs-5 mb-4 px-2 d-flex align-items-center gap-2">
          <i className="bi bi-diagram-3-fill text-indigo-400" style={{ color: '#818cf8' }}></i>
          KnowledgeBook
        </div>
        <nav className="d-flex flex-column gap-1">
          {NAV.filter((n) => user && n.roles.includes(user.role)).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/documents'}
              className={({ isActive }) => `side-link${isActive ? ' active' : ''}`}>
              <i className={`bi ${n.icon}`}></i>{n.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main */}
      <div className="flex-grow-1 d-flex flex-column" style={{ minWidth: 0 }}>
        <header className="bg-white border-bottom d-flex align-items-center justify-content-end px-4"
          style={{ height: 60 }}>
          <div className="dropdown">
            <button className="btn btn-light rounded-circle fw-bold d-flex align-items-center justify-content-center"
              style={{ width: 40, height: 40, background: '#eef2ff', color: '#4f46e5' }}
              onClick={() => setOpen((o) => !o)}>
              {initials}
            </button>
            {open && (
              <div className="dropdown-menu dropdown-menu-end show mt-2" style={{ right: 0 }}
                onMouseLeave={() => setOpen(false)}>
                <div className="px-3 py-2 border-bottom">
                  <div className="fw-semibold text-truncate" style={{ maxWidth: 200 }}>{user?.name || user?.email}</div>
                  <span className="badge text-bg-light text-uppercase">{user?.role}</span>
                </div>
                <button className="dropdown-item" onClick={onLogout}>
                  <i className="bi bi-box-arrow-right me-2"></i>Log out
                </button>
              </div>
            )}
          </div>
        </header>

        <main className="p-4" style={{ maxWidth: 1120, width: '100%' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
