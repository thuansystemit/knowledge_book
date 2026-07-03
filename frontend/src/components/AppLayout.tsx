import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { logout as apiLogout } from '../api/auth.api';
import { APP_NAME, ROLE_LABEL, canUpload } from '../lib/constants';
import { AppFooter } from './AppFooter';

// Primary nav links. `uploader: true` items are hidden from roles that can't
// upload (viewers).
const PRIMARY_NAV = [
  { to: '/documents/new', label: 'Upload',    end: true, uploader: true },
  { to: '/documents',     label: 'Documents', end: true },
];

// Admin-only nav links shown inline (styled same as primary)
const ADMIN_NAV = [
  { to: '/admin/users',  label: 'Users'  },
  { to: '/admin/config', label: 'Config' },
];

export function AppLayout() {
  const { user, clear } = useAuthStore();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const isAdmin = user?.role === 'admin';
  const mayUpload = canUpload(user?.role);

  const initials = (user?.name || user?.email || '?')
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase())
    .join('');

  // Close the user menu on outside click or Escape.
  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setMenuOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  const onLogout = async () => {
    setMenuOpen(false);
    try { await apiLogout(); } finally { clear(); navigate('/login', { replace: true }); }
  };

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `topnav-link${isActive ? ' active' : ''}`;

  return (
    <div className="app-shell">
      {/* ── Top navigation ── */}
      <nav className="app-topnav" role="navigation" aria-label="Main navigation">
        {/* Wordmark */}
        <NavLink to="/documents" className="app-brand" aria-label={APP_NAME}>
          {APP_NAME}
        </NavLink>

        {/* Primary links */}
        <div className="topnav-links">
          {PRIMARY_NAV.filter((n) => !n.uploader || mayUpload).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={navLinkClass}>
              {n.label}
            </NavLink>
          ))}

          {/* Admin-only extra links */}
          {isAdmin && ADMIN_NAV.map((n) => (
            <NavLink key={n.to} to={n.to} className={navLinkClass}>
              {n.label}
            </NavLink>
          ))}
        </div>

        {/* Right side */}
        <div className="topnav-right">
          {/* Categories pill — admin only */}
          {isAdmin && (
            <NavLink
              to="/admin/categories"
              className={({ isActive }) =>
                `categories-pill${isActive ? ' active' : ''}`
              }
            >
              Categories
              <span className="admin-badge">ADMIN</span>
            </NavLink>
          )}

          {/* Avatar — opens a dropdown (View Profile / Logout) */}
          <div className="position-relative" ref={menuRef}>
            <button
              type="button"
              className={`user-avatar${menuOpen ? ' user-avatar--active' : ''}`}
              onClick={() => setMenuOpen((o) => !o)}
              aria-label="User menu"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
            >
              {initials}
            </button>

            {menuOpen && (
              <div
                className="dropdown-menu show"
                role="menu"
                style={{ position: 'absolute', right: 0, top: 'calc(100% + 0.5rem)', minWidth: 200 }}
              >
                {/* Signed-in-as header */}
                <div className="px-2 py-1 mb-1" style={{ borderBottom: '1px solid var(--border)' }}>
                  <div
                    style={{
                      fontWeight: 600, fontSize: '0.8125rem', color: 'var(--ink)',
                      maxWidth: 184, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}
                  >
                    {user?.name || user?.email}
                  </div>
                  {user?.role && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                      {ROLE_LABEL[user.role] ?? user.role}
                    </div>
                  )}
                </div>

                <button
                  type="button"
                  className="dropdown-item d-flex align-items-center gap-2 w-100 text-start border-0 bg-transparent"
                  role="menuitem"
                  onClick={() => { setMenuOpen(false); navigate('/profile'); }}
                >
                  <i className="bi bi-person"></i>
                  View profile
                </button>
                <button
                  type="button"
                  className="dropdown-item d-flex align-items-center gap-2 w-100 text-start border-0 bg-transparent"
                  role="menuitem"
                  onClick={onLogout}
                >
                  <i className="bi bi-box-arrow-right"></i>
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </nav>

      {/* ── Page content ── */}
      <main className="app-main">
        <Outlet />
      </main>

      {/* ── Footer ── */}
      <AppFooter />
    </div>
  );
}
