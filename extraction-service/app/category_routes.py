"""/api/categories* — admin-governed categories + per-category grants (EF-27)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access import grant_level, require_category
from app.db import get_db
from app.deps import get_current_user, require_role
from app.models import Category, CategoryPermission, Job, User

router = APIRouter(prefix="/api/categories", tags=["categories"])

_GRANTS = ("view", "upload", "manage")
_LEVEL_NAME = {0: None, 1: "view", 2: "upload", 3: "manage"}


class CategoryIn(BaseModel):
    name: str
    description: str | None = None


class GrantIn(BaseModel):
    user_id: str
    grant_type: str


def _cat_public(c: Category, my_grant: str | None, doc_count: int) -> dict:
    return {"id": c.id, "name": c.name, "description": c.description,
            "my_grant": my_grant, "doc_count": doc_count}


@router.get("")
def list_categories(user: User = Depends(get_current_user), db=Depends(get_db)):
    cats = db.scalars(select(Category).where(Category.org_id == user.org_id)
                      .order_by(Category.name)).all()
    out = []
    for c in cats:
        lvl = grant_level(db, user, c.id)
        if lvl == 0 and user.role != "admin":
            continue  # invisible without a grant (default-deny)
        n = db.scalar(select(func.count()).select_from(Job).where(Job.category_id == c.id)) or 0
        out.append(_cat_public(c, _LEVEL_NAME[lvl], n))
    return out


@router.post("")
def create_category(body: CategoryIn, admin: User = Depends(require_role("admin")), db=Depends(get_db)):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    if db.scalar(select(Category).where(Category.org_id == admin.org_id, Category.name == name)):
        raise HTTPException(409, "a category with that name already exists")
    c = Category(org_id=admin.org_id, name=name, description=body.description, created_by=admin.id)
    db.add(c)
    db.commit()
    return _cat_public(c, "manage", 0)


@router.patch("/{category_id}")
def update_category(category_id: str, body: CategoryIn,
                    admin: User = Depends(require_role("admin")), db=Depends(get_db)):
    c = _org_category(db, admin, category_id)
    if body.name:
        c.name = body.name.strip()
    c.description = body.description
    db.commit()
    return _cat_public(c, "manage", 0)


@router.delete("/{category_id}")
def delete_category(category_id: str, admin: User = Depends(require_role("admin")), db=Depends(get_db)):
    c = _org_category(db, admin, category_id)
    # D9: never auto-delete/migrate documents — block if any exist.
    n = db.scalar(select(func.count()).select_from(Job).where(Job.category_id == category_id)) or 0
    if n:
        raise HTTPException(409, f"category has {n} document(s); reassign or delete them first")
    for p in db.scalars(select(CategoryPermission).where(CategoryPermission.category_id == category_id)).all():
        db.delete(p)
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.get("/{category_id}/permissions")
def list_permissions(category_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    _org_category(db, user, category_id)
    require_category(db, user, category_id, "manage")
    rows = db.scalars(select(CategoryPermission).where(
        CategoryPermission.category_id == category_id)).all()
    return [{"id": p.id, "user_id": p.subject_id, "grant_type": p.grant_type} for p in rows]


@router.post("/{category_id}/permissions")
def add_permission(category_id: str, body: GrantIn,
                   user: User = Depends(get_current_user), db=Depends(get_db)):
    _org_category(db, user, category_id)
    require_category(db, user, category_id, "manage")
    if body.grant_type not in _GRANTS:
        raise HTTPException(400, f"grant_type must be one of {_GRANTS}")
    target = db.get(User, body.user_id)
    if not target or target.org_id != user.org_id:
        raise HTTPException(404, "user not found in this organization")
    existing = db.scalar(select(CategoryPermission).where(
        CategoryPermission.category_id == category_id,
        CategoryPermission.subject_type == "user",
        CategoryPermission.subject_id == body.user_id))
    if existing:
        existing.grant_type = body.grant_type
    else:
        db.add(CategoryPermission(category_id=category_id, subject_type="user",
                                  subject_id=body.user_id, grant_type=body.grant_type,
                                  granted_by=user.id))
    db.commit()
    return {"ok": True}


@router.delete("/{category_id}/permissions/{perm_id}")
def revoke_permission(category_id: str, perm_id: str,
                      user: User = Depends(get_current_user), db=Depends(get_db)):
    _org_category(db, user, category_id)
    require_category(db, user, category_id, "manage")
    p = db.get(CategoryPermission, perm_id)
    if p and p.category_id == category_id:
        db.delete(p)
        db.commit()
    return {"ok": True}


def _org_category(db: Session, user: User, category_id: str) -> Category:
    c = db.get(Category, category_id)
    if not c or c.org_id != user.org_id:
        raise HTTPException(404, "category not found")
    return c
