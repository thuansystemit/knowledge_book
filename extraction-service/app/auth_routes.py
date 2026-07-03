"""/auth/* — login, refresh, logout, me (Sprint 1a).

Token model (toeic pattern): access token returned in the JSON body (held in
memory by the SPA), refresh token in an HttpOnly cookie. Refresh rotates the
stored token row; logout revokes it."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import RefreshToken, User
from app.security import make_access, make_refresh, safe_decode, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE = "kb_refresh"


class LoginIn(BaseModel):
    email: str  # lookup only — no format validation (allows internal .local addrs)
    password: str


def _secure_flag(cfg) -> bool:
    # The refresh cookie is HttpOnly always. Mark it Secure when configured
    # (COOKIE_SECURE, i.e. behind HTTPS) — and force Secure when SameSite=None,
    # which browsers otherwise reject.
    return cfg.cookie_secure or cfg.cookie_samesite.lower() == "none"


def _issue_refresh(db: Session, user: User, resp: Response) -> None:
    cfg = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(days=cfg.refresh_ttl_days)
    row = RefreshToken(user_id=user.id, expires_at=expires)
    db.add(row)
    db.commit()
    token = make_refresh(user.id, row.id)
    resp.set_cookie(
        _COOKIE, token, httponly=True, secure=_secure_flag(cfg),
        samesite=cfg.cookie_samesite, max_age=cfg.refresh_ttl_days * 86400, path="/auth",
    )


@router.post("/login")
def login(body: LoginIn, resp: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "invalid credentials")
    _issue_refresh(db, user, resp)
    return {"access_token": make_access(user.id, user.role), "user": user.public()}


@router.post("/refresh")
def refresh(resp: Response, kb_refresh: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    if not kb_refresh:
        raise HTTPException(401, "no refresh cookie")
    claims = safe_decode(kb_refresh, "refresh")
    if not claims:
        raise HTTPException(401, "invalid refresh token")
    row = db.get(RefreshToken, claims.get("jti"))
    if not row or row.revoked or row.user_id != claims.get("sub"):
        raise HTTPException(401, "refresh token revoked")
    if row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(401, "refresh token expired")
    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "user inactive")
    # Rotate: revoke the used token, issue a fresh one.
    row.revoked = True
    db.commit()
    _issue_refresh(db, user, resp)
    return {"access_token": make_access(user.id, user.role), "user": user.public()}


@router.post("/logout")
def logout(resp: Response, kb_refresh: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    if kb_refresh:
        claims = safe_decode(kb_refresh, "refresh")
        if claims:
            row = db.get(RefreshToken, claims.get("jti"))
            if row:
                row.revoked = True
                db.commit()
    cfg = get_settings()
    resp.delete_cookie(_COOKIE, path="/auth", httponly=True,
                       secure=_secure_flag(cfg), samesite=cfg.cookie_samesite)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user.public()
