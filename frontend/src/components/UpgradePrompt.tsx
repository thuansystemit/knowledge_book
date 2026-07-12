import { useNavigate } from 'react-router-dom';
import { trackUpgradeClick, type UpgradeSource } from '../api/activation.api';

/**
 * PAY-06: a contextual paywall upgrade prompt. Each gate passes a specific
 * `message` and `source`; clicking the CTA records a conversion event (which
 * gate it came from) and then routes to billing.
 */
export function UpgradePrompt({
  source, message, jobId, cta = 'Upgrade to Pro',
  variant = 'info', icon = 'bi-stars', compact = false,
}: {
  source: UpgradeSource;
  message: React.ReactNode;
  jobId?: string;
  cta?: string;
  variant?: 'info' | 'warning' | 'secondary';
  icon?: string;
  compact?: boolean;
}) {
  const navigate = useNavigate();
  const go = () => {
    void trackUpgradeClick(source, jobId);
    navigate('/billing');
  };
  return (
    <div
      className={`alert alert-${variant} d-flex align-items-center justify-content-between flex-wrap gap-2 ${compact ? 'py-2 mb-2' : ''}`}
      role="status"
    >
      <span>
        <i className={`bi ${icon} me-2`} aria-hidden="true" />
        {message}
      </span>
      <button className="btn btn-primary btn-sm flex-shrink-0" onClick={go}>{cta}</button>
    </div>
  );
}
