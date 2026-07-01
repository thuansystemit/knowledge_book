"""SQLAlchemy engine + session (Sprint 1a persistence).

Single sync engine against PostgreSQL (DATABASE_URL). `get_db` is the FastAPI
dependency; `session_scope` is for the background worker thread, which needs its
own session outside the request lifecycle."""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

_cfg = get_settings()
# pool_pre_ping avoids stale connections after the DB container restarts.
engine = create_engine(_cfg.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    """Transactional scope for the worker thread."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
