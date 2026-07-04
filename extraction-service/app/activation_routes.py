"""/api/activation/* — activation instrumentation endpoints (ACT-01/02/03).

The frontend fires `view` when the Concept Map first renders and `rate` when the
user clicks thumbs up/down. Q&A activation is recorded server-side in the chat
handler, so it needs no endpoint here. `summary` is the admin activation-rate
rollup for the GTM gates.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import activation
from app.access import require_job_access
from app.db import get_db
from app.deps import get_current_user, require_role
from app.models import User

router = APIRouter(prefix="/api/activation", tags=["activation"])


class ViewIn(BaseModel):
    job_id: str
    session_id: str | None = None


class RateIn(BaseModel):
    job_id: str
    rating: str  # up | down


@router.post("/view")
def view(body: ViewIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = require_job_access(db, user, body.job_id)  # 403/404 if not permitted
    activation.record_view(db, user.id, body.job_id, org_id=job.org_id, session_id=body.session_id)
    return {"ok": True}


@router.post("/rate")
def rate(body: RateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.rating not in ("up", "down"):
        raise HTTPException(400, "rating must be 'up' or 'down'")
    job = require_job_access(db, user, body.job_id)
    activation.record_rating(db, user.id, body.job_id, body.rating, org_id=job.org_id)
    return {"ok": True}


@router.get("/status/{job_id}")
def status(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_job_access(db, user, job_id)
    return activation.status_for(db, user.id, job_id)


@router.get("/summary")
def summary(admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return activation.summary_metrics(db)
