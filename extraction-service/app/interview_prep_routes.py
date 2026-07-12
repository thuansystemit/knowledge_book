"""/api/interview-prep* — corpus-grounded interview preparation (IP-03).

RBAC (ctx §"RBAC invariants"): any authenticated role may create/own a plan; the
corpus is scoped inside the Celery task, never here. Cross-user read/write always
403s for non-admins. Admins may list plans across their org.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.interview_prep import (
    TRACKS, prep_history_len, prep_subscribe,
)
from app.models import InterviewPrepPlan, InterviewPrepQuestion, User
from app.security import make_prep_stream, safe_decode
from app.tasks import generate_interview_prep

router = APIRouter(prefix="/api/interview-prep", tags=["interview-prep"])


class CreatePlanIn(BaseModel):
    track: str


def _plan_public(plan: InterviewPrepPlan) -> dict:
    return {
        "id": plan.id, "track": plan.track, "status": plan.status,
        "version": plan.version, "is_current": plan.is_current,
        "error": plan.error, "category_ids": plan.category_ids,
        "plan_data": plan.plan_data, "model": plan.model,
        "cost_usd": float(plan.cost_usd) if plan.cost_usd is not None else None,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }


def _create_new_version(track: str, user: User, db: Session) -> InterviewPrepPlan:
    """IP-07: insert a fresh pending version row (never mutate an existing one).
    409 if a generation for this (user, track) is already in flight."""
    in_flight = db.scalar(select(InterviewPrepPlan).where(
        InterviewPrepPlan.user_id == user.id,
        InterviewPrepPlan.track == track,
        InterviewPrepPlan.status.in_(["pending", "generating"]),
    ))
    if in_flight:
        raise HTTPException(409, "A generation is already in progress for this track.")
    next_ver = (db.scalar(select(func.max(InterviewPrepPlan.version)).where(
        InterviewPrepPlan.user_id == user.id,
        InterviewPrepPlan.track == track,
    )) or 0) + 1
    plan = InterviewPrepPlan(user_id=user.id, org_id=user.org_id, track=track,
                             status="pending", version=next_ver, is_current=False)
    db.add(plan)
    db.flush()
    return plan


def _question_public(q: InterviewPrepQuestion) -> dict:
    return {
        "id": q.id, "topic": q.topic, "question": q.question,
        "model_answer": q.model_answer, "difficulty": q.difficulty,
        "citations": q.citations, "sort_order": q.sort_order,
    }


def _require_plan_access(plan: InterviewPrepPlan | None, user: User) -> InterviewPrepPlan:
    if not plan:
        raise HTTPException(404, "plan not found")
    if plan.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "you do not have access to this plan")
    return plan


@router.post("")
def create_plan(body: CreatePlanIn, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    if body.track not in TRACKS:
        raise HTTPException(400, f"invalid track; must be one of {', '.join(TRACKS)}")
    plan = _create_new_version(body.track, user, db)
    plan_id = plan.id
    db.commit()
    generate_interview_prep.delay(plan_id)
    return _plan_public(plan)


@router.get("")
def list_plans(all_versions: bool = Query(default=False),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Default view is one row per track: the current (done) version plus any
    # in-flight generation (pending/generating), so a track mid-generation still
    # shows up. Admins may pass ?all_versions=true to see the full history.
    stmt = select(InterviewPrepPlan)
    if user.role == "admin":
        stmt = stmt.where(InterviewPrepPlan.org_id == user.org_id)
    else:
        stmt = stmt.where(InterviewPrepPlan.user_id == user.id)
    if not (user.role == "admin" and all_versions):
        stmt = stmt.where(or_(
            InterviewPrepPlan.is_current.is_(True),
            InterviewPrepPlan.status.in_(["pending", "generating"]),
        ))
    stmt = stmt.order_by(InterviewPrepPlan.updated_at.desc()).limit(50)
    return {"plans": [_plan_public(p) for p in db.scalars(stmt).all()]}


@router.get("/{plan_id}")
def get_plan(plan_id: str, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    plan = _require_plan_access(db.get(InterviewPrepPlan, plan_id), user)
    questions = db.scalars(select(InterviewPrepQuestion).where(
        InterviewPrepQuestion.plan_id == plan_id
    ).order_by(InterviewPrepQuestion.sort_order)).all()
    return {**_plan_public(plan), "questions": [_question_public(q) for q in questions]}


@router.post("/{plan_id}/regenerate")
def regenerate_plan(plan_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    # Regenerate = a NEW version (IP-07). The old version's row + questions are
    # left untouched, so it stays viewable while (and if) the new one generates.
    old = _require_plan_access(db.get(InterviewPrepPlan, plan_id), user)
    plan = _create_new_version(old.track, user, db)
    new_id = plan.id
    db.commit()
    generate_interview_prep.delay(new_id)
    return _plan_public(plan)


@router.post("/{plan_id}/stream-token")
def stream_token(plan_id: str, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    _require_plan_access(db.get(InterviewPrepPlan, plan_id), user)
    return {"token": make_prep_stream(user.id, plan_id)}


@router.get("/{plan_id}/events")
def stream_events(plan_id: str, t: str = Query(default=""), db: Session = Depends(get_db)):
    # EventSource can't send Authorization headers — auth rides in `t`.
    claims = safe_decode(t, "prep-stream")
    if not claims or claims.get("plan") != plan_id:
        raise HTTPException(401, "invalid stream token")
    plan = db.get(InterviewPrepPlan, plan_id)
    if not plan:
        raise HTTPException(404, "plan not found")

    active = plan.status in ("pending", "generating")
    has_stream = prep_history_len(plan_id) > 0
    snapshot = {"stage": "done", "status": plan.status, "detail": plan.error or ""}

    def gen():
        if has_stream or active:
            for ev in prep_subscribe(plan_id):
                yield f"data: {json.dumps(ev)}\n\n"
        else:
            # Finished and expired from Redis — emit a single terminal snapshot.
            yield f"data: {json.dumps(snapshot)}\n\n"
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/{plan_id}/versions")
def list_versions(plan_id: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    """IP-10: all versions for the plan's (user, track), newest first. Lightweight
    — no plan_data or questions, just per-version metadata + a question count."""
    plan = _require_plan_access(db.get(InterviewPrepPlan, plan_id), user)
    rows = db.scalars(select(InterviewPrepPlan).where(
        InterviewPrepPlan.user_id == plan.user_id,
        InterviewPrepPlan.track == plan.track,
    ).order_by(InterviewPrepPlan.version.desc())).all()
    ids = [p.id for p in rows]
    counts = dict(db.execute(
        select(InterviewPrepQuestion.plan_id, func.count(InterviewPrepQuestion.id))
        .where(InterviewPrepQuestion.plan_id.in_(ids))
        .group_by(InterviewPrepQuestion.plan_id)).all()) if ids else {}
    return {
        "track": plan.track,
        "versions": [{
            "id": p.id, "version": p.version, "is_current": p.is_current,
            "status": p.status, "model": p.model,
            "cost_usd": float(p.cost_usd) if p.cost_usd is not None else None,
            "question_count": counts.get(p.id, 0),
            "generated_at": (p.plan_data or {}).get("generated_at") if p.plan_data else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "error": p.error,
        } for p in rows],
    }


@router.post("/{plan_id}/pin")
def pin_version(plan_id: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    """IP-11: make a historical done version current again (rollback)."""
    plan = _require_plan_access(db.get(InterviewPrepPlan, plan_id), user)
    if plan.status != "done":
        raise HTTPException(422, "Only completed versions can be pinned.")
    db.query(InterviewPrepPlan).filter(
        InterviewPrepPlan.user_id == plan.user_id,
        InterviewPrepPlan.track == plan.track,
        InterviewPrepPlan.id != plan.id,
    ).update({"is_current": False}, synchronize_session=False)
    plan.is_current = True
    db.commit()
    questions = db.scalars(select(InterviewPrepQuestion).where(
        InterviewPrepQuestion.plan_id == plan_id
    ).order_by(InterviewPrepQuestion.sort_order)).all()
    return {**_plan_public(plan), "questions": [_question_public(q) for q in questions]}


@router.delete("/{plan_id}")
def delete_plan(plan_id: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    # Delete ONE version. If it was current, promote the newest remaining done
    # version to current so the track still has a current plan.
    plan = _require_plan_access(db.get(InterviewPrepPlan, plan_id), user)
    was_current, uid, track = plan.is_current, plan.user_id, plan.track
    db.query(InterviewPrepQuestion).filter(
        InterviewPrepQuestion.plan_id == plan_id).delete(synchronize_session=False)
    db.delete(plan)
    db.flush()
    new_current_id = None
    if was_current:
        repl = db.scalar(select(InterviewPrepPlan).where(
            InterviewPrepPlan.user_id == uid,
            InterviewPrepPlan.track == track,
            InterviewPrepPlan.status == "done",
        ).order_by(InterviewPrepPlan.version.desc()))
        if repl:
            repl.is_current = True
            new_current_id = repl.id
    db.commit()
    return {"ok": True, "new_current_id": new_current_id}
