"""Consumer subscription plans + monthly upload quota (PAY-01/02/03).

Implements the Free/Pro/Scholar tiers from `docs/monetization-pricing.md`. This
is orthogonal to RBAC (`User.role`): `plan` governs how many documents a user may
process per calendar month, not what they are permitted to do.

Enforcement is intentionally simple and correct: count the user's jobs created
since the start of the current UTC calendar month; block the upload with a clear
`402 Payment Required` + upgrade message once the plan quota is reached — never a
generic error (PAY-06). Admins are exempt (super-user, consistent with the rest
of the codebase). Limits are env-tunable via `Settings` so pricing experiments
need no code change.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Job, User

PLANS = ("free", "pro", "scholar")
_PLAN_RANK = {"free": 0, "pro": 1, "scholar": 2}


def can_export(user: User) -> bool:
    """Exporting outputs is a Pro/Scholar feature (OUT-06); admins always can."""
    return user.role == "admin" or (user.plan or "free") in ("pro", "scholar")


def effective_chat_mode(user: User, cfg: Settings) -> str:
    """The chat mode this user actually gets (RC-20 value ladder).

    Free = zero-LLM retrieval chat; Pro/Scholar (and admins) = LLM-synthesized
    chat when the server is in LLM mode. Returns "llm" only when the server is
    configured for LLM *and* the user's plan meets `chat_llm_min_plan` (or the
    user is an admin); otherwise "retrieval"."""
    if cfg.chat_mode != "llm":
        return "retrieval"
    if user.role == "admin":
        return "llm"
    need = _PLAN_RANK.get(cfg.chat_llm_min_plan, 1)
    return "llm" if _PLAN_RANK.get(user.plan or "free", 0) >= need else "retrieval"


def monthly_limit(plan: str, cfg: Settings) -> int:
    """Documents allowed per calendar month for a plan (0 = unlimited)."""
    return {
        "free": cfg.plan_free_docs,
        "pro": cfg.plan_pro_docs,
        "scholar": cfg.plan_scholar_docs,
    }.get(plan or "free", cfg.plan_free_docs)


def _month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def used_this_month(db: Session, user: User, now: datetime | None = None) -> int:
    """Count of documents this user has started processing in the current month."""
    start = _month_start(now)
    return int(db.scalar(
        select(func.count(Job.id)).where(
            Job.user_id == user.id, Job.created_at >= start)
    ) or 0)


def usage(db: Session, user: User, cfg: Settings) -> dict:
    """Plan-usage snapshot for the current user (drives the frontend meter +
    contextual upgrade prompts). `remaining=None` means unlimited."""
    limit = monthly_limit(user.plan, cfg)
    used = used_this_month(db, user)
    # First moment of next month = when the quota resets.
    ms = _month_start()
    resets_at = (ms.replace(year=ms.year + 1, month=1) if ms.month == 12
                 else ms.replace(month=ms.month + 1))
    unlimited = limit <= 0 or user.role == "admin"
    return {
        "plan": user.plan,
        "limit": None if unlimited else limit,
        "used": used,
        "remaining": None if unlimited else max(limit - used, 0),
        "resets_at": resets_at.isoformat(),
    }


def enforce_scanned_allowed(user: User, pdf_label: str) -> None:
    """Free tier is digital-only (PAY-01). Block scanned/hybrid PDFs with a 402 +
    upgrade message. Admins and paid plans always pass. `pdf_label` comes from
    `classify_pdf` (digital|scanned|hybrid|empty)."""
    if user.role == "admin":
        return
    if (user.plan or "free") == "free" and pdf_label in ("scanned", "hybrid"):
        raise HTTPException(
            402,
            "Scanned PDFs require a Pro plan. Upgrade to Pro to process this document.",
        )


def apply_free_tier_caps(graph: dict | None, user: User, cfg: Settings) -> dict | None:
    """Cap the concept map for Free users (PAY-01). Applied at serving time so an
    upgrade instantly reveals the full graph — nothing is dropped from storage.

    Returns a shallow copy with the node list truncated to the highest-confidence
    `plan_free_concepts` nodes (already sorted desc by `graph_builder.build`),
    edges filtered to surviving nodes, and a `paywall` block for the UI. Admins,
    paid plans, and uncapped/under-cap graphs pass through unchanged."""
    if not graph or user.role == "admin" or (user.plan or "free") != "free":
        return graph
    capped = dict(graph)  # shallow copy — never mutate the stored ORM JSON

    # Chapter Guide is a Pro/Scholar feature (PAY-01): withhold it, flag as locked.
    if capped.get("chapter_guide"):
        capped["chapter_guide"] = []
        capped["chapter_guide_locked"] = True

    # Concept-map cap: keep the highest-confidence `plan_free_concepts` nodes.
    cap = cfg.plan_free_concepts
    nodes = graph.get("nodes") or []
    total = len(nodes)
    if cap > 0 and total > cap:
        kept = nodes[:cap]
        kept_ids = {n.get("id") for n in kept}
        capped["nodes"] = kept
        capped["edges"] = [e for e in (graph.get("edges") or [])
                           if e.get("source") in kept_ids and e.get("target") in kept_ids]
        capped["paywall"] = {"capped": True, "concepts_shown": cap, "concepts_total": total}
    return capped


def enforce_upload_quota(db: Session, user: User, cfg: Settings) -> None:
    """Raise 402 with a plan-specific upgrade message if the user is at quota.

    Admins and unlimited plans (limit <= 0) always pass. Call this at the start
    of the upload handler, before any file work is done."""
    if user.role == "admin":
        return
    limit = monthly_limit(user.plan, cfg)
    if limit <= 0:
        return
    used = used_this_month(db, user)
    if used >= limit:
        nxt = "Pro (20 docs/mo)" if user.plan == "free" else "a higher plan"
        raise HTTPException(
            402,
            f"You've used all {limit} documents on your {user.plan.capitalize()} "
            f"plan this month. Upgrade to {nxt} to keep going.",
        )
