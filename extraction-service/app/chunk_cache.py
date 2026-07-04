"""Idempotent chunk-extraction cache (EXT-03).

Keys a chunk's extraction result by hash(model + prompt + chunk input), so a
re-process (OUT-07) or a retry reuses the cached JSON instead of re-calling the
LLM — no duplicate cost. The prompt text and model id are part of the key, so a
prompt change or model switch invalidates the cache automatically.

Redis-backed and **fail-open**: if the cache is disabled or Redis is unavailable,
`get` returns None and `put` is a no-op, so extraction always proceeds.
"""
from __future__ import annotations

import hashlib

from app.config import Settings
from app.redis_client import get_redis

_PREFIX = "chunkcache:"


def enabled(cfg: Settings) -> bool:
    return cfg.chunk_cache_enabled


def key(model_id: str | None, prompt: str, chunk_input: str) -> str:
    h = hashlib.sha256()
    h.update((model_id or "").encode("utf-8"))
    h.update(b"\x00")
    h.update((prompt or "").encode("utf-8"))
    h.update(b"\x00")
    h.update((chunk_input or "").encode("utf-8"))
    return _PREFIX + h.hexdigest()


def get(k: str) -> str | None:
    try:
        return get_redis().get(k)
    except Exception:
        return None  # fail-open — treat as a miss


def put(k: str, value: str, ttl_sec: int) -> None:
    try:
        get_redis().set(k, value, ex=ttl_sec if ttl_sec > 0 else None)
    except Exception:
        pass  # fail-open — caching is best-effort
