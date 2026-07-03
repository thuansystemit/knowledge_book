import { APP_NAME } from '../lib/constants';

/** Full-viewport loading indicator — shown while the app bootstraps. */
export function PageSpinner() {
  return (
    <div className="page-spinner-wrap">
      <div className="page-spinner-brand">{APP_NAME}</div>
      <div
        className="spinner-border"
        role="status"
        style={{ width: 20, height: 20, color: 'var(--brand)', borderWidth: 2 }}
      >
        <span className="visually-hidden">Loading…</span>
      </div>
    </div>
  );
}
