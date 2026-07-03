import { NavLink, Outlet } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { APP_NAME, canUpload } from '../lib/constants';

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
  const { user } = useAuthStore();

  const isAdmin = user?.role === 'admin';
  const mayUpload = canUpload(user?.role);

  const initials = (user?.name || user?.email || '?')
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase())
    .join('');

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

          {/* Avatar — navigates to /profile */}
          <NavLink
            to="/profile"
            className={({ isActive }) =>
              `user-avatar${isActive ? ' user-avatar--active' : ''}`
            }
            aria-label="Your profile"
          >
            {initials}
          </NavLink>
        </div>
      </nav>

      {/* ── Page content ── */}
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
