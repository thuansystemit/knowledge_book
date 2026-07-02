"""Category-scoped authorization (EF-27 enforcement — the single hard-to-bypass
check applied to every document/chat/pdf route).

Grant hierarchy: view(1) < upload(2) < manage(3). A global `admin` is a
super-user. Access is default-deny: no grant on a document's category means the
document is invisible. The document's owner retains access to their own upload."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, CategoryPermission, Job, User

_LEVEL = {"view": 1, "upload": 2, "manage": 3}


def grant_level(db: Session, user: User, category_id: str | None) -> int:
    """Max grant level the user has on a category (3 for admin, 0 for none)."""
    if user.role == "admin":
        return 3
    if not category_id:
        return 0
    perms = db.scalars(select(CategoryPermission).where(
        CategoryPermission.category_id == category_id,
        CategoryPermission.subject_type == "user",
        CategoryPermission.subject_id == user.id)).all()
    return max((_LEVEL.get(p.grant_type, 0) for p in perms), default=0)


def has_grant(db: Session, user: User, category_id: str | None, minimum: str) -> bool:
    return grant_level(db, user, category_id) >= _LEVEL[minimum]


def require_category(db: Session, user: User, category_id: str, minimum: str) -> None:
    if not has_grant(db, user, category_id, minimum):
        raise HTTPException(403, f"requires '{minimum}' permission on this category")


def can_access_job(db: Session, user: User, job: Job) -> bool:
    """True if the user may view a job: admin, the owner, or has `view` on its
    category."""
    if user.role == "admin" or job.user_id == user.id:
        return True
    return has_grant(db, user, job.category_id, "view")


def require_job_access(db: Session, user: User, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if not can_access_job(db, user, job):
        raise HTTPException(403, "you do not have access to this document")
    return job


def visible_category_ids(db: Session, user: User) -> set[str]:
    """Category ids the user can at least view (for filtering the library)."""
    if user.role == "admin":
        return {c for (c,) in db.execute(
            select(Category.id).where(Category.org_id == user.org_id)).all()}
    return {p.category_id for p in db.scalars(select(CategoryPermission).where(
        CategoryPermission.subject_type == "user",
        CategoryPermission.subject_id == user.id)).all()}


def general_category_id(db: Session, org_id: str | None) -> str | None:
    if not org_id:
        return None
    c = db.scalar(select(Category).where(Category.org_id == org_id, Category.name == "General"))
    return c.id if c else None
