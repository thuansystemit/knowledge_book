"""Redis-backed job progress stream (enterprise backbone — Step 2, EF-03).

Replaces the in-memory append-only list + condition variable so that a Celery
worker (a *separate process*) can produce progress events and ANY API replica
can serve the SSE stream for them. This is the cross-replica fan-out:

  - Redis **List** `job:{id}:events`  — append-only history (enables refresh/replay).
  - Redis **channel** `job:{id}:chan` — pub/sub wake-up on each new event.
  - Redis **key** `job:{id}:done`     — terminal flag.

`subscribe()` mirrors the old condition-variable loop: the List is the source of
truth (poll by index); the channel just wakes the reader promptly; the done flag
ends the stream. A late subscriber (page refresh) replays the whole List first.
"""
from __future__ import annotations

import json
from typing import Iterator

from app.redis_client import get_redis

_TTL = 3600  # keep a finished job's stream in Redis for 1h (then DB replay)


def _keys(job_id: str) -> tuple[str, str, str]:
    return f"job:{job_id}:events", f"job:{job_id}:done", f"job:{job_id}:chan"


def reset(job_id: str) -> None:
    """Clear any prior stream for this job (fresh start / crash re-run)."""
    ek, dk, _ = _keys(job_id)
    get_redis().delete(ek, dk)


def publish(job_id: str, event: dict) -> None:
    r = get_redis()
    ek, _, ch = _keys(job_id)
    r.rpush(ek, json.dumps(event))
    r.expire(ek, _TTL)
    r.publish(ch, "1")


def mark_done(job_id: str) -> None:
    r = get_redis()
    _, dk, ch = _keys(job_id)
    r.set(dk, "1", ex=_TTL)
    r.publish(ch, "1")


def history_len(job_id: str) -> int:
    ek, _, _ = _keys(job_id)
    return get_redis().llen(ek)


def all_events(job_id: str) -> list[dict]:
    ek, _, _ = _keys(job_id)
    return [json.loads(x) for x in get_redis().lrange(ek, 0, -1)]


def subscribe(job_id: str) -> Iterator[dict]:
    """Yield event dicts: replay history, then follow live until done."""
    r = get_redis()
    ek, dk, ch = _keys(job_id)
    ps = r.pubsub()
    ps.subscribe(ch)
    idx = 0
    try:
        while True:
            for raw in r.lrange(ek, idx, -1):
                idx += 1
                yield json.loads(raw)
            if r.exists(dk) and idx >= r.llen(ek):
                return
            # Block for a wake-up (or time out to re-poll defensively).
            ps.get_message(timeout=15)
    finally:
        try:
            ps.close()
        except Exception:
            pass
