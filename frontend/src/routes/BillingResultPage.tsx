import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { getMe } from '../api/auth.api';

/**
 * Post-checkout landing pages. Stripe redirects the browser here; the plan is
 * actually applied by the webhook, which may land a moment later — so the
 * success page polls /auth/me a few times until the plan flips off `free`.
 */
export function BillingSuccessPage() {
  const { user, accessToken, setAuth } = useAuthStore();
  const [confirmed, setConfirmed] = useState(user?.plan && user.plan !== 'free');

  useEffect(() => {
    let tries = 0;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      tries += 1;
      try {
        const me = await getMe();
        if (accessToken) setAuth(accessToken, me);
        if (me.plan && me.plan !== 'free') { setConfirmed(true); return; }
      } catch { /* ignore transient errors */ }
      if (tries < 5) timer = setTimeout(poll, 1500);
    };
    poll();
    return () => clearTimeout(timer);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ maxWidth: 560, margin: '2rem auto', textAlign: 'center' }}>
      <div className="card">
        <div className="card-body" style={{ padding: '2rem' }}>
          <i className="bi bi-check-circle-fill" style={{ fontSize: '2.5rem', color: '#22c55e' }} aria-hidden="true" />
          <h1 className="page-title mt-2">You&apos;re all set</h1>
          {confirmed ? (
            <p className="page-subtitle">
              Your <strong style={{ textTransform: 'capitalize' }}>{user?.plan}</strong> plan is active.
              Enjoy the higher monthly limit and full outputs.
            </p>
          ) : (
            <p className="page-subtitle">
              Payment received — we&apos;re activating your plan. This usually takes a few seconds.
            </p>
          )}
          <div className="d-flex gap-2 justify-content-center mt-3">
            <Link to="/documents/new" className="btn btn-primary btn-sm">Upload a document</Link>
            <Link to="/billing" className="btn btn-outline-secondary btn-sm">View plan</Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export function BillingCancelPage() {
  return (
    <div style={{ maxWidth: 560, margin: '2rem auto', textAlign: 'center' }}>
      <div className="card">
        <div className="card-body" style={{ padding: '2rem' }}>
          <i className="bi bi-x-circle" style={{ fontSize: '2.5rem', color: 'var(--muted)' }} aria-hidden="true" />
          <h1 className="page-title mt-2">Checkout canceled</h1>
          <p className="page-subtitle">No charge was made. You can upgrade any time.</p>
          <div className="mt-3">
            <Link to="/billing" className="btn btn-primary btn-sm">Back to plans</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
