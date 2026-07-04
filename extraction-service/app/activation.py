"""Activation instrumentation (ACT-01/02/03) — feeds the GTM launch gates.

Records three idempotent signals per (user, document):
- `view`   — the user loaded the Concept Map (ACT-01)
- `rating` — thumbs up/down on the concept list (ACT-02)
- `qa`     — the user asked at least one Q&A question (ACT-03)

Idempotent per kind (one row per user/job/kind), so the activation rate is a
clean count of pairs. A document is **activated** when a `view` also has a
`rating` or a `qa`. `record_qa` is called from the chat handler so Q&A tracking
needs no frontend wiring.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ActivationEvent
from app.observability import audit


def _existing(db: Session, user_id: str, job_id: str, kind: str) -> ActivationEvent | None:
    return db.scalar(select(ActivationEvent).where(
        ActivationEvent.user_id == user_id,
        ActivationEvent.job_id == job_id,
        ActivationEvent.kind == kind))


def _record(db: Session, *, user_id: str, job_id: str, kind: str,
            org_id: str | None = None, value: str | None = None,
            session_id: str | None = None) -> ActivationEvent:
    """Insert one (user, job, kind) row, or update value on an existing one."""
    row = _existing(db, user_id, job_id, kind)
    if row is None:
        row = ActivationEvent(org_id=org_id, user_id=user_id, job_id=job_id,
                              kind=kind, value=value, session_id=session_id)
        db.add(row)
    elif value is not None:
        row.value = value  # allow re-rating
    db.commit()
    return row


def record_view(db: Session, user_id: str, job_id: str, *, org_id: str | None = None,
                session_id: str | None = None) -> None:
    _record(db, user_id=user_id, job_id=job_id, kind="view",
            org_id=org_id, session_id=session_id)
    audit("ACT_VIEW", user=user_id, job=job_id)


def record_rating(db: Session, user_id: str, job_id: str, rating: str, *,
                  org_id: str | None = None) -> None:
    _record(db, user_id=user_id, job_id=job_id, kind="rating",
            org_id=org_id, value=rating)
    audit("ACT_RATING", user=user_id, job=job_id, rating=rating)


def record_qa(db: Session, user_id: str, job_id: str, *, org_id: str | None = None) -> None:
    _record(db, user_id=user_id, job_id=job_id, kind="qa", org_id=org_id)
    audit("ACT_QA", user=user_id, job=job_id)


def status_for(db: Session, user_id: str, job_id: str) -> dict:
    """What has this user done on this doc — drives the UI (show/hide the rating
    prompt, avoid re-firing the view event)."""
    rating = _existing(db, user_id, job_id, "rating")
    return {
        "viewed": _existing(db, user_id, job_id, "view") is not None,
        "rated": rating is not None,
        "rating": rating.value if rating else None,
    }


def summary_metrics(db: Session) -> dict:
    """Activation-rate rollup for the GTM gates G-03/G-04 (admin dashboard).

    activation_rate = views that also have a rating or qa, over all views.
    thumbs_up_rate  = up ratings over all ratings.
    qa_cosession_rate = views that also have a qa, over all views."""
    def pairs(kind: str) -> set[tuple[str, str]]:
        rows = db.execute(select(ActivationEvent.user_id, ActivationEvent.job_id)
                          .where(ActivationEvent.kind == kind)).all()
        return {(r[0], r[1]) for r in rows}

    views, ratings, qas = pairs("view"), pairs("rating"), pairs("qa")
    activated = {p for p in views if p in ratings or p in qas}
    ups = int(db.scalar(select(func.count()).select_from(ActivationEvent)
                        .where(ActivationEvent.kind == "rating",
                               ActivationEvent.value == "up")) or 0)
    total_ratings = int(db.scalar(select(func.count()).select_from(ActivationEvent)
                                  .where(ActivationEvent.kind == "rating")) or 0)
    nv = len(views)
    return {
        "views": nv,
        "activated": len(activated),
        "activation_rate": round(len(activated) / nv, 3) if nv else None,
        "thumbs_up_rate": round(ups / total_ratings, 3) if total_ratings else None,
        "qa_cosession_rate": round(len(views & qas) / nv, 3) if nv else None,
    }
