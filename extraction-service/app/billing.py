"""Stripe subscription billing (PAY-04).

Bridges the Stripe-hosted checkout to the consumer plan model in `app/plans.py`.
Design goals:

- **Optional / config-gated.** If `STRIPE_SECRET_KEY` is blank the app still boots
  and billing endpoints return 503 (on-prem/enterprise deploys need no Stripe).
  The Stripe SDK is imported lazily so it is not a hard dependency at import time.
- **Webhook is the source of truth.** Checkout only *starts* an upgrade; the
  user's `plan`/`plan_status` are set from verified webhook events so a closed
  browser tab or a later cancel/downgrade still syncs correctly.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import User
from app.observability import audit

_INTERVALS = ("monthly", "annual")


def configured(cfg: Settings) -> bool:
    return bool(cfg.stripe_secret_key)


def _stripe(cfg: Settings):
    """Lazy-load + configure the Stripe SDK. Raises 503 if unavailable."""
    if not configured(cfg):
        raise HTTPException(503, "billing is not configured")
    try:
        import stripe  # noqa: PLC0415 (intentional lazy import)
    except ImportError:  # pragma: no cover - SDK missing in a non-billing deploy
        raise HTTPException(503, "billing SDK not installed")
    stripe.api_key = cfg.stripe_secret_key
    return stripe


def _price_map(cfg: Settings) -> dict[tuple[str, str], str]:
    return {
        ("pro", "monthly"): cfg.stripe_price_pro_monthly,
        ("pro", "annual"): cfg.stripe_price_pro_annual,
        ("scholar", "monthly"): cfg.stripe_price_scholar_monthly,
        ("scholar", "annual"): cfg.stripe_price_scholar_annual,
    }


def price_for(plan: str, interval: str, cfg: Settings) -> str:
    if plan not in ("pro", "scholar"):
        raise HTTPException(400, "plan must be 'pro' or 'scholar'")
    if interval not in _INTERVALS:
        raise HTTPException(400, "interval must be 'monthly' or 'annual'")
    price = _price_map(cfg).get((plan, interval), "")
    if not price:
        raise HTTPException(503, f"no Stripe price configured for {plan}/{interval}")
    return price


def plan_for_price(price_id: str, cfg: Settings) -> str | None:
    """Reverse-map a Stripe price id to a plan name (for subscription events)."""
    for (plan, _interval), pid in _price_map(cfg).items():
        if pid and pid == price_id:
            return plan
    return None


def ensure_customer(db: Session, user: User, cfg: Settings) -> str:
    """Return the user's Stripe customer id, creating one on first use."""
    if user.stripe_customer_id:
        return user.stripe_customer_id
    stripe = _stripe(cfg)
    customer = stripe.Customer.create(email=user.email, name=user.name or None,
                                      metadata={"user_id": user.id})
    user.stripe_customer_id = customer["id"]
    db.commit()
    return customer["id"]


def create_checkout_session(db: Session, user: User, plan: str, interval: str,
                            cfg: Settings) -> str:
    """Create a Stripe-hosted subscription Checkout Session; return its URL."""
    stripe = _stripe(cfg)
    price = price_for(plan, interval, cfg)
    customer_id = ensure_customer(db, user, cfg)
    base = cfg.frontend_base_url.rstrip("/")
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        client_reference_id=user.id,
        line_items=[{"price": price, "quantity": 1}],
        success_url=f"{base}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/billing/cancel",
        metadata={"user_id": user.id, "plan": plan},
        subscription_data={"metadata": {"user_id": user.id, "plan": plan}},
        allow_promotion_codes=True,
    )
    audit("BILLING_CHECKOUT_CREATED", user=user.id, plan=plan, interval=interval)
    return session["url"]


def create_portal_session(db: Session, user: User, cfg: Settings) -> str:
    """Create a Stripe billing-portal session so the user can manage/cancel."""
    if not user.stripe_customer_id:
        raise HTTPException(400, "no active subscription to manage")
    stripe = _stripe(cfg)
    base = cfg.frontend_base_url.rstrip("/")
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id, return_url=f"{base}/account")
    return session["url"]


def construct_event(payload: bytes, sig_header: str | None, cfg: Settings):
    """Verify the webhook signature and return the parsed event."""
    if not cfg.stripe_webhook_secret:
        raise HTTPException(503, "webhook secret not configured")
    stripe = _stripe(cfg)
    try:
        return stripe.Webhook.construct_event(payload, sig_header, cfg.stripe_webhook_secret)
    except Exception:  # signature/parse failure -> reject
        raise HTTPException(400, "invalid webhook signature")


# --- webhook event handling -------------------------------------------------

def _user_by_customer(db: Session, customer_id: str | None) -> User | None:
    if not customer_id:
        return None
    return db.scalar(select(User).where(User.stripe_customer_id == customer_id))


def _apply_active(user: User, plan: str, subscription_id: str | None) -> None:
    user.plan = plan
    user.plan_status = "active"
    if subscription_id:
        user.stripe_subscription_id = subscription_id


def _downgrade(user: User, status: str = "canceled") -> None:
    user.plan = "free"
    user.plan_status = status
    user.stripe_subscription_id = None


def handle_event(db: Session, event: dict, cfg: Settings) -> None:
    """Update the user's plan from a verified Stripe event. Idempotent: Stripe
    may deliver the same event more than once."""
    etype = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}

    if etype == "checkout.session.completed":
        user = db.get(User, obj.get("client_reference_id")) or \
            _user_by_customer(db, obj.get("customer"))
        if not user:
            return
        plan = (obj.get("metadata") or {}).get("plan") or "pro"
        if obj.get("customer"):
            user.stripe_customer_id = obj["customer"]
        _apply_active(user, plan, obj.get("subscription"))
        db.commit()
        audit("BILLING_ACTIVATED", user=user.id, plan=plan)

    elif etype == "customer.subscription.updated":
        user = _user_by_customer(db, obj.get("customer"))
        if not user:
            return
        status = obj.get("status", "")
        items = ((obj.get("items") or {}).get("data") or [{}])
        price_id = ((items[0].get("price") or {}).get("id")) if items else None
        plan = plan_for_price(price_id, cfg) or user.plan
        if status in ("active", "trialing"):
            _apply_active(user, plan, obj.get("id"))
        elif status in ("past_due", "unpaid"):
            user.plan_status = "past_due"
        elif status == "canceled":
            _downgrade(user)
        db.commit()
        audit("BILLING_SUB_UPDATED", user=user.id, status=status, plan=user.plan)

    elif etype == "customer.subscription.deleted":
        user = _user_by_customer(db, obj.get("customer"))
        if not user:
            return
        _downgrade(user)
        db.commit()
        audit("BILLING_SUB_DELETED", user=user.id)
