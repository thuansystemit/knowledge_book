import { Link, Outlet } from 'react-router-dom';
import { APP_NAME } from '../lib/constants';
import { AppFooter } from './AppFooter';

/**
 * Intentionally public layout — no authentication required.
 *
 * Used for legal pages (About, Privacy, Terms) so they are reachable from the
 * login page footer and from external links without forcing a login redirect.
 * Renders a minimal branded top bar (wordmark only, no user nav), the routed
 * page content, and the shared AppFooter.
 *
 * An authenticated user who navigates to a legal page will also land here
 * (showing the brand + footer rather than the full app nav). That is the
 * accepted trade-off — do NOT wrap this in ProtectedRoute or AppLayout.
 */
export function PublicLayout() {
  return (
    <div className="app-shell">
      {/* Minimal top bar — brand wordmark only, no auth-dependent nav items */}
      <header className="app-topnav" role="banner">
        <Link to="/login" className="app-brand" aria-label={APP_NAME}>
          {APP_NAME}
        </Link>
      </header>

      <main className="app-main">
        <Outlet />
      </main>

      <AppFooter />
    </div>
  );
}
