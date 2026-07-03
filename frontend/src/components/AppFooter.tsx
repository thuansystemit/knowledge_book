import { Link } from 'react-router-dom';
import { APP_NAME } from '../lib/constants';

export function AppFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="app-footer" role="contentinfo">
      <div className="app-footer-inner">
        <nav className="app-footer-links" aria-label="Legal navigation">
          <Link to="/about">About</Link>
          <Link to="/privacy">Privacy</Link>
          <Link to="/terms">Terms &amp; Conditions</Link>
        </nav>
        <p className="app-footer-copy">
          &copy; {year} {APP_NAME}. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
