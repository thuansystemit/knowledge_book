"""FastAPI auth dependencies: current user + role gates."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import safe_decode


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    claims = safe_decode(authorization.split(" ", 1)[1], "access")
    if not claims:
        raise HTTPException(401, "invalid or expired token")
    user = db.get(User, claims["sub"])
    if not user or not user.is_active:
        raise HTTPException(401, "user not found or inactive")
    return user


def require_role(*roles: str):
    """Dependency factory: gate an endpoint to specific roles."""
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"requires role: {' or '.join(roles)}")
        return user
    return _dep
