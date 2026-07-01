import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { logout as apiLogout } from '../api/auth.api';

const NAV = [
  { to: '/documents', label: 'Documents', roles: ['admin', 'analyst'] },
  { to: '/documents/new', label: 'New extraction', roles: ['admin', 'analyst'] },
  { to: '/admin/users', label: 'Users', roles: ['admin'] },
];

export function AppLayout() {
  const { user, clear } = useAuthStore();
  const navigate = useNavigate();
  const [menu, setMenu] = useState(false);

  const onLogout = async () => {
    try { await apiLogout(); } finally {
      clear();
      navigate('/login', { replace: true });
    }
  };

  const initials = (user?.name || user?.email || '?')
    .split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((s) => s[0]?.toUpperCase()).join('');

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">📚 KnowledgeBook</div>
        <nav>
          {NAV.filter((n) => user && n.roles.includes(user.role)).map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/documents'}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="spacer" />
          <div className="usermenu">
            <button className="avatar" onClick={() => setMenu((m) => !m)}>
              {initials}
            </button>
            {menu && (
              <div className="menu" onMouseLeave={() => setMenu(false)}>
                <div className="menu-head">
                  <strong>{user?.name || user?.email}</strong>
                  <span className="role-badge">{user?.role}</span>
                </div>
                <button className="menu-item" onClick={onLogout}>Log out</button>
              </div>
            )}
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
