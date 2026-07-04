"""/billing/* — Stripe checkout, portal, and webhook (PAY-04).

- `POST /billing/checkout` (auth): start a hosted subscription checkout; returns
  the Stripe URL the SPA redirects to.
- `POST /billing/portal` (auth): open the Stripe billing portal to manage/cancel.
- `POST /billing/webhook` (no auth): Stripe -> us. Signature-verified; the raw
  request body is required, so this handler reads `request.body()` directly.
- `GET /billing/config` (auth): tells the SPA whether billing is live and which
  (plan, interval) combos have a configured price, to show/hide upgrade buttons.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import billing
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutIn(BaseModel):
    plan: str       # pro | scholar
    interval: str = "monthly"  # monthly | annual


@router.get("/config")
def billing_config(user: User = Depends(get_current_user)):
    cfg = get_settings()
    live = billing.configured(cfg)
    prices = billing._price_map(cfg)
    available = {f"{plan}_{interval}": bool(pid)
                 for (plan, interval), pid in prices.items()}
    return {"enabled": live, "available": available,
            "current_plan": user.plan, "plan_status": user.plan_status}


@router.post("/checkout")
def checkout(body: CheckoutIn, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    cfg = get_settings()
    url = billing.create_checkout_session(db, user, body.plan, body.interval, cfg)
    return {"url": url}


@router.post("/portal")
def portal(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = get_settings()
    return {"url": billing.create_portal_session(db, user, cfg)}


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    cfg = get_settings()
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    event = billing.construct_event(payload, sig, cfg)
    billing.handle_event(db, event, cfg)
    return {"received": True}
