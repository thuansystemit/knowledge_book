import { useEffect, useState } from 'react';
import { useAuthStore } from '../store/authStore';
import { getMe } from '../api/auth.api';
import {
  createCheckout, getBillingConfig, getUsage, openPortal,
  type BillingConfig, type Interval, type Plan, type Usage,
} from '../api/billing.api';
import { getApiError } from '../lib/utils';

// Display pricing (source of truth for amounts is Stripe; these mirror
// docs/monetization-pricing.md for the UI). Checkout is driven by (plan,
// interval) — the server resolves the actual Stripe price.
const PLANS: Array<{
  id: Plan;
  name: string;
  monthly: number;
  annual: number;
  blurb: string;
  features: string[];
}> = [
  {
    id: 'free', name: 'Free', monthly: 0, annual: 0,
    blurb: 'Try it on a couple of documents a month.',
    features: ['2 documents / month', 'Digital PDFs only', 'Brief + 10-concept map', 'No Q&A or Chapter Guide'],
  },
  {
    id: 'pro', name: 'Pro', monthly: 19, annual: 180,
    blurb: 'For researchers and practitioners who read every week.',
    features: ['20 documents / month', 'Digital + scanned PDFs', 'All 4 outputs, full concept map', 'Q&A + Chapter Guide', 'Markdown / JSON export'],
  },
  {
    id: 'scholar', name: 'Scholar', monthly: 35, annual: 336,
    blurb: 'For heavy readers who process dozens of documents.',
    features: ['60 documents / month', 'Everything in Pro', 'Priority processing queue', 'Early access to new features'],
  },
];

function planRank(p: Plan): number {
  return { free: 0, pro: 1, scholar: 2 }[p];
}

export function BillingPage() {
  const { user, accessToken, setAuth } = useAuthStore();
  const [usage, setUsage] = useState<Usage | null>(null);
  const [config, setConfig] = useState<BillingConfig | null>(null);
  const [interval, setInterval] = useState<Interval>('monthly');
  const [busy, setBusy] = useState<Plan | 'portal' | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getUsage().then(setUsage).catch(() => {});
    getBillingConfig().then(setConfig).catch(() => {});
    // Keep the store's plan fresh in case a webhook landed since login.
    getMe().then((me) => { if (accessToken) setAuth(accessToken, me); }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const currentPlan: Plan = usage?.plan ?? user?.plan ?? 'free';
  const hasSubscription = currentPlan !== 'free' && user?.plan_status === 'active';

  const onUpgrade = async (plan: Plan) => {
    if (plan === 'free') return;
    setBusy(plan); setError(null);
    try {
      const url = await createCheckout(plan, interval);
      window.location.href = url; // hand off to Stripe-hosted checkout
    } catch (e) {
      setError(getApiError(e, 'Could not start checkout. Please try again.'));
      setBusy(null);
    }
  };

  const onManage = async () => {
    setBusy('portal'); setError(null);
    try {
      window.location.href = await openPortal();
    } catch (e) {
      setError(getApiError(e, 'Could not open the billing portal.'));
      setBusy(null);
    }
  };

  const pct = usage && usage.limit
    ? Math.min(100, Math.round((usage.used / usage.limit) * 100))
    : 0;
  const atLimit = usage?.remaining === 0;

  return (
    <div>
      <div className="mb-4">
        <h1 className="page-title">Plans &amp; billing</h1>
        <p className="page-subtitle">Manage your subscription and monthly usage</p>
      </div>

      {error && <div className="alert alert-danger" role="alert">{error}</div>}

      {/* ── Usage meter ── */}
      {usage && (
        <div className="card mb-4" style={{ maxWidth: 960 }}>
          <div className="card-body" style={{ padding: '1.25rem' }}>
            <div className="d-flex align-items-center justify-content-between flex-wrap gap-2 mb-2">
              <div>
                <span className="section-heading">Current plan: </span>
                <span style={{ textTransform: 'capitalize', fontWeight: 700 }}>{currentPlan}</span>
                {user?.plan_status === 'past_due' && (
                  <span className="badge bg-warning text-dark ms-2">Payment past due</span>
                )}
              </div>
              {usage.limit === null ? (
                <span style={{ color: 'var(--muted)', fontSize: '0.875rem' }}>Unlimited documents this month</span>
              ) : (
                <span style={{ color: atLimit ? '#b91c1c' : 'var(--muted)', fontSize: '0.875rem' }}>
                  {usage.used} / {usage.limit} documents used this month
                </span>
              )}
            </div>
            {usage.limit !== null && (
              <div className="progress" style={{ height: 8 }} role="progressbar"
                   aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
                <div className={`progress-bar${atLimit ? ' bg-danger' : ''}`} style={{ width: `${pct}%` }} />
              </div>
            )}
            {atLimit && currentPlan === 'free' && (
              <p className="form-text mt-2 mb-0">
                You&apos;ve used your free documents this month. Upgrade below to keep going.
              </p>
            )}
            {hasSubscription && (
              <div className="mt-3">
                <button className="btn btn-outline-secondary btn-sm" onClick={onManage} disabled={busy === 'portal'}>
                  {busy === 'portal' ? 'Opening…' : 'Manage subscription'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Billing-disabled notice (on-prem / Stripe not configured) */}
      {config && !config.enabled && (
        <div className="alert alert-info" role="status" style={{ maxWidth: 960 }}>
          Online upgrades aren&apos;t available on this deployment. Contact your administrator to change plans.
        </div>
      )}

      {/* ── Interval toggle ── */}
      <div className="btn-group mb-3" role="group" aria-label="Billing interval">
        <button type="button" className={`btn btn-sm ${interval === 'monthly' ? 'btn-primary' : 'btn-outline-secondary'}`}
                onClick={() => setInterval('monthly')}>Monthly</button>
        <button type="button" className={`btn btn-sm ${interval === 'annual' ? 'btn-primary' : 'btn-outline-secondary'}`}
                onClick={() => setInterval('annual')}>Annual <span style={{ opacity: 0.85 }}>· save ~2 months</span></button>
      </div>

      {/* ── Plan cards ── */}
      <div className="row g-3" style={{ maxWidth: 960 }}>
        {PLANS.map((p) => {
          const isCurrent = p.id === currentPlan;
          const price = interval === 'monthly' ? p.monthly : p.annual;
          const priceKey = `${p.id}_${interval}`;
          const priceAvailable = p.id === 'free' || (config?.available?.[priceKey] ?? false);
          const isDowngrade = planRank(p.id) < planRank(currentPlan);
          return (
            <div key={p.id} className="col-md-4">
              <div className="card h-100" style={isCurrent ? { borderColor: 'var(--brand)', borderWidth: 2 } : undefined}>
                <div className="card-body d-flex flex-column" style={{ padding: '1.25rem' }}>
                  <div className="d-flex align-items-center justify-content-between">
                    <div className="section-heading">{p.name}</div>
                    {isCurrent && <span className="role-pill">Current</span>}
                  </div>
                  <div style={{ margin: '0.5rem 0' }}>
                    <span style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--ink)' }}>${price}</span>
                    <span style={{ color: 'var(--muted)' }}>/{interval === 'monthly' ? 'mo' : 'yr'}</span>
                  </div>
                  <p className="form-text" style={{ marginTop: 0 }}>{p.blurb}</p>
                  <ul style={{ paddingLeft: '1.1rem', margin: '0.5rem 0 1rem', color: 'var(--ink)', fontSize: '0.875rem' }}>
                    {p.features.map((f) => (
                      <li key={f} style={{ marginBottom: '0.25rem' }}>{f}</li>
                    ))}
                  </ul>
                  <div className="mt-auto">
                    {isCurrent ? (
                      <button className="btn btn-outline-secondary w-100" disabled>Current plan</button>
                    ) : p.id === 'free' || isDowngrade ? (
                      <button className="btn btn-outline-secondary w-100" onClick={onManage}
                              disabled={!hasSubscription || busy === 'portal'}
                              title={hasSubscription ? 'Manage in the billing portal' : undefined}>
                        {isDowngrade ? 'Change in portal' : 'Downgrade'}
                      </button>
                    ) : (
                      <button className="btn btn-primary w-100"
                              onClick={() => onUpgrade(p.id)}
                              disabled={busy !== null || !config?.enabled || !priceAvailable}
                              title={!priceAvailable ? 'Not available' : undefined}>
                        {busy === p.id ? 'Redirecting…' : `Upgrade to ${p.name}`}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
