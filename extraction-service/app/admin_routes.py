"""/admin/* — user management (Admin only, Sprint 1a).

Admin-only account creation (per product decision): no self-registration."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_role
from app.models import ROLES, User
from app.security import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])


class CreateUserIn(BaseModel):
    email: str   # internal tool: allow .local etc.; minimal '@' check below
    password: str
    name: str = ""
    role: str = "analyst"


class UpdateUserIn(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


@router.get("/users")
def list_users(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return [u.public() for u in db.scalars(select(User).order_by(User.created_at)).all()]


@router.post("/users")
def create_user(body: CreateUserIn, admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    if body.role not in ROLES:
        raise HTTPException(400, f"role must be one of {ROLES}")
    if "@" not in body.email or len(body.email) < 3:
        raise HTTPException(400, "invalid email")
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "email already exists")
    # New users belong to the creating admin's org — otherwise org-scoped
    # operations (category grants, model defaults) reject them as out-of-org.
    user = User(org_id=admin.org_id, email=body.email, password_hash=hash_password(body.password),
                name=body.name, role=body.role)
    db.add(user)
    db.commit()
    return user.public()


@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UpdateUserIn,
                admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "user not found")
    if body.role is not None:
        if body.role not in ROLES:
            raise HTTPException(400, f"role must be one of {ROLES}")
        user.role = body.role
    if body.is_active is not None:
        # Guard: an admin can't deactivate themselves out of the system.
        if user.id == admin.id and not body.is_active:
            raise HTTPException(400, "cannot deactivate your own account")
        user.is_active = body.is_active
    if body.password:
        user.password_hash = hash_password(body.password)
    db.commit()
    return user.public()
