"""Password hashing + JWT minting/verification (Sprint 1a).

Three token kinds, all HS256 over JWT_SECRET:
  - access : short-lived (ACCESS_TTL_MIN), sent as `Authorization: Bearer`.
  - refresh: long-lived (REFRESH_TTL_DAYS), carries a jti -> RefreshToken row,
             stored in an HttpOnly cookie. Rotated on use, revocable on logout.
  - stream : 60s, scoped to one job_id, for the SSE endpoint (EventSource can't
             send Authorization headers, so the token rides in `?t=`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_ALG = "HS256"


def hash_password(raw: str) -> str:
    return _pwd.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return _pwd.verify(raw, hashed)


def _encode(claims: dict, ttl: timedelta) -> str:
    cfg = get_settings()
    now = datetime.now(timezone.utc)
    payload = {**claims, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, cfg.jwt_secret, algorithm=_ALG)


def decode(token: str) -> dict:
    """Decode + verify. Raises jose.JWTError on invalid/expired."""
    cfg = get_settings()
    return jwt.decode(token, cfg.jwt_secret, algorithms=[_ALG])


def make_access(user_id: str, role: str) -> str:
    cfg = get_settings()
    return _encode({"sub": user_id, "role": role, "type": "access"},
                   timedelta(minutes=cfg.access_ttl_min))


def make_refresh(user_id: str, jti: str) -> str:
    cfg = get_settings()
    return _encode({"sub": user_id, "jti": jti, "type": "refresh"},
                   timedelta(days=cfg.refresh_ttl_days))


def make_stream(user_id: str, job_id: str) -> str:
    cfg = get_settings()
    return _encode({"sub": user_id, "job": job_id, "type": "stream"},
                   timedelta(seconds=cfg.stream_token_ttl_sec))


def make_chat_stream(user_id: str, job_id: str, message_id: str) -> str:
    cfg = get_settings()
    return _encode({"sub": user_id, "job": job_id, "msg": message_id, "type": "chat-stream"},
                   timedelta(seconds=cfg.chat_stream_token_ttl_sec))


def safe_decode(token: str, expected_type: str) -> dict | None:
    """Decode and require `type`; return None on any failure (no raise)."""
    try:
        claims = decode(token)
    except JWTError:
        return None
    return claims if claims.get("type") == expected_type else None
