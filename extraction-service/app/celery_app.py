"""Celery app (enterprise backbone — Step 2, EF-01).

Durable job execution on a Redis broker, replacing daemon threads. `acks_late`
+ `task_reject_on_worker_lost` mean a job survives a worker crash (the message is
re-delivered and the task re-runs) instead of being silently lost on restart.
Postgres remains the source of truth for job state."""
from __future__ import annotations

from celery import Celery

from app.config import get_settings

_cfg = get_settings()

celery_app = Celery(
    "knowledgebook",
    broker=_cfg.redis_url,
    backend=_cfg.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_default_queue="extraction",
    task_acks_late=True,                 # ack only after the task finishes
    task_reject_on_worker_lost=True,     # re-queue if the worker dies mid-task
    worker_prefetch_multiplier=1,        # one long job at a time per worker slot
    task_ignore_result=True,             # Postgres is the source of truth
    broker_connection_retry_on_startup=True,
)
