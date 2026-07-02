"""Shared Redis client (enterprise backbone — Step 1).

A lazily-created, process-wide connection pool. Redis underpins the next
migration steps: Celery broker/result (EF-01), cross-replica SSE pub/sub
(EF-03), and the config-as-data cache with pub/sub invalidation (D14)."""
from __future__ import annotations

from functools import lru_cache

import redis

from app.config import get_settings


@lru_cache(maxsize=1)
def get_redis() -> "redis.Redis":
    """Process-wide Redis client (decodes responses to str)."""
    cfg = get_settings()
    return redis.Redis.from_url(cfg.redis_url, decode_responses=True)


def ping() -> bool:
    """True if Redis is reachable — used by the health check."""
    try:
        return bool(get_redis().ping())
    except Exception:
        return False
