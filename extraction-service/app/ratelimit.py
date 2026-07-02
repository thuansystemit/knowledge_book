"""Redis-backed per-user rate limiting (enterprise backbone — Step 3, EF-02).

Fixed-window counters keyed by (bucket, user, window). Works across API replicas
because the counter lives in Redis. **Fail-open:** if Redis is unavailable the
request is allowed (rate limiting is best-effort; never block legitimate traffic
on a limiter outage). A limit of 0 disables the bucket."""
from __future__ import annotations

import time

from fastapi import Depends, HTTPException

from app.config import get_settings
from app.deps import get_current_user
from app.models import User
from app.redis_client import get_redis


def _check(subject: str, bucket: str, limit: int, window_sec: int) -> None:
    if limit <= 0:
        return  # disabled
    key = f"rl:{bucket}:{subject}:{int(time.time()) // window_sec}"
    try:
        n = get_redis().incr(key)
        if n == 1:
            get_redis().expire(key, window_sec)
    except Exception:
        return  # fail-open on Redis trouble
    if n > limit:
        ttl = 0
        try:
            ttl = get_redis().ttl(key)
        except Exception:
            pass
        raise HTTPException(429, f"rate limit exceeded for '{bucket}'",
                            headers={"Retry-After": str(max(int(ttl), 1))})


def upload_limit(user: User = Depends(get_current_user)) -> None:
    cfg = get_settings()
    _check(user.id, "upload", cfg.rate_upload_per_hour, 3600)


def chat_limit(user: User = Depends(get_current_user)) -> None:
    cfg = get_settings()
    _check(user.id, "chat", cfg.rate_chat_per_min, 60)
