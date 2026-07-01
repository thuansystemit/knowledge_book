"""HTTP API for the dashboard (Sprint 1a: auth + per-user persistence).

Endpoints (all /api/jobs/* now require auth):
  POST /api/jobs                     multipart {file} -> {job_id}   (admin|analyst)
  GET  /api/jobs                     list caller's jobs (admin: all)
  GET  /api/jobs/{id}                full job + graph (owner or admin)
  POST /api/jobs/{id}/stream-token   short-lived token for the SSE stream
  GET  /api/jobs/{id}/events?t=...   SSE stage stream (auth via stream token)

Plus /auth/* (auth_routes) and /admin/* (admin_routes).

Jobs are persisted to Postgres (survive restart, per-user). A small in-memory
registry holds the live event queue for a *currently running* job so the SSE
stream is real-time; finished jobs replay their persisted events. Single-process
MVP — multi-worker durability (Redis pub/sub) is deferred per ARCHITECTURE."""
from __future__ import annotations

import json
import threading

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.admin_routes import router as admin_router
from app.auth_routes import router as auth_router
from app.chat_routes import router as chat_router
from app.config import get_settings
from app.db import Base, engine, get_db, session_scope
from app.deps import get_current_user, require_role
from app.llm.factory import get_provider
from app.models import Job, User
from app.observability import audit
from app.security import hash_password, make_stream, safe_decode
from app.pipeline import retry_failed, run as run_pipeline

app = FastAPI(title="KnowledgeBook Extraction API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,   # refresh cookie travels with withCredentials requests
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(chat_router)

# job_id -> {"events": list, "cond": threading.Condition, "done": bool}
# An append-only event list guarded by a condition variable. Any number of SSE
# subscribers (including a page reload that reconnects) can replay the full
# history from index 0 and then follow live updates — which is what makes
# progress survive a refresh.
LIVE: dict[str, dict] = {}


@app.on_event("startup")
def _startup() -> None:
    Base.metadata.create_all(engine)
    _bootstrap_admin()


def _bootstrap_admin() -> None:
    """Seed the first admin from env vars iff the users table is empty."""
    cfg = get_settings()
    with session_scope() as db:
        if db.scalar(select(User).limit(1)) is not None:
            return
        db.add(User(email=cfg.admin_email, password_hash=hash_password(cfg.admin_password),
                    name="Administrator", role="admin"))
        audit("ADMIN_BOOTSTRAPPED", email=cfg.admin_email)


def _run_job(job_id: str, data: bytes) -> None:
    cfg = get_settings()
    live = LIVE[job_id]
    cond = live["cond"]

    def on_event(ev: dict) -> None:
        with cond:
            live["events"].append(ev)
            cond.notify_all()

    status, graph, error = "done", None, None
    try:
        with session_scope() as db:
            title = db.get(Job, job_id).title
        provider = get_provider()
        graph = run_pipeline(data, title, provider, cfg, on_event=on_event)
    except Exception as e:
        status, error = "error", str(e)
        audit("JOB_ERROR", job=job_id, error=str(e))
        on_event({"stage": "done", "status": "error", "detail": str(e)})
    finally:
        # Persist the full result so it survives a restart / cross-process reads.
        with session_scope() as db:
            job = db.get(Job, job_id)
            if job:
                job.status = status
                job.graph = graph
                job.events = live["events"]
                job.error = error
        with cond:
            live["done"] = True
            cond.notify_all()


def _retry_job(job_id: str) -> None:
    """Re-run the job's failed chunks and merge them into its existing graph."""
    cfg = get_settings()
    live = LIVE[job_id]
    cond = live["cond"]

    def on_event(ev: dict) -> None:
        with cond:
            live["events"].append(ev)
            cond.notify_all()

    status, error, new_graph = "done", None, None
    try:
        with session_scope() as db:
            job = db.get(Job, job_id)
            graph, title = job.graph, job.title
        provider = get_provider()
        new_graph = retry_failed(graph, title, provider, cfg, on_event=on_event)
    except Exception as e:
        status, error = "error", str(e)
        audit("RETRY_ERROR", job=job_id, error=str(e))
        on_event({"stage": "done", "status": "error", "detail": str(e)})
    finally:
        with session_scope() as db:
            job = db.get(Job, job_id)
            if job:
                job.status = status
                if new_graph is not None:
                    job.graph = new_graph
                job.events = live["events"]
                job.error = error
        with cond:
            live["done"] = True
            cond.notify_all()


@app.post("/api/jobs")
async def create_job(file: UploadFile,
                     user: User = Depends(require_role("admin", "analyst")),
                     db=Depends(get_db)):
    cfg = get_settings()
    data = await file.read()
    if len(data) > cfg.max_file_bytes:
        raise HTTPException(413, f"file too large (> {cfg.max_file_bytes} bytes)")
    title = (file.filename or "document").rsplit(".", 1)[0]

    job = Job(user_id=user.id, title=title, status="running", events=[])
    db.add(job)
    db.commit()
    LIVE[job.id] = {"events": [], "cond": threading.Condition(), "done": False}
    audit("JOB_START", job=job.id, user=user.id, title=title, bytes=len(data))
    threading.Thread(target=_run_job, args=(job.id, data), daemon=True).start()
    return {"job_id": job.id, "title": title}


@app.get("/api/jobs")
def list_jobs(user: User = Depends(get_current_user), db=Depends(get_db)):
    q = select(Job).order_by(Job.created_at.desc())
    if user.role != "admin":
        q = q.where(Job.user_id == user.id)
    return [j.summary() for j in db.scalars(q).all()]


def _owned_job(job_id: str, user: User, db) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "not your job")
    return job


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    return _owned_job(job_id, user, db).detail()


@app.post("/api/jobs/{job_id}/retry-failed")
def retry_failed_chunks(job_id: str,
                        user: User = Depends(require_role("admin", "analyst")),
                        db=Depends(get_db)):
    """Re-extract the chunks that failed and merge them into the existing graph
    (append, not a new job). Runs in the background; watch via the SSE stream."""
    job = _owned_job(job_id, user, db)
    if job.status == "running":
        raise HTTPException(409, "job is already running")
    failed = (job.graph or {}).get("failed_chunks") or []
    if not failed:
        raise HTTPException(400, "no failed chunks to retry")
    job.status = "running"
    job.events = []
    db.commit()
    LIVE[job_id] = {"events": [], "cond": threading.Condition(), "done": False}
    audit("RETRY_START", job=job_id, failed=len(failed))
    threading.Thread(target=_retry_job, args=(job_id,), daemon=True).start()
    return {"job_id": job_id, "retrying": len(failed)}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    job = _owned_job(job_id, user, db)
    db.delete(job)
    db.commit()
    LIVE.pop(job_id, None)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/stream-token")
def stream_token(job_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    _owned_job(job_id, user, db)
    return {"token": make_stream(user.id, job_id)}


@app.get("/api/jobs/{job_id}/events")
def stream_events(job_id: str, t: str = "", db=Depends(get_db)):
    # EventSource can't send Authorization headers, so auth rides in `t`.
    claims = safe_decode(t, "stream")
    if not claims or claims.get("job") != job_id:
        raise HTTPException(401, "invalid stream token")
    if not db.get(Job, job_id):
        raise HTTPException(404, "job not found")

    live = LIVE.get(job_id)

    def gen():
        if live is None:
            # No live registry (finished long ago / pre-restart) — replay the
            # persisted events from the DB, then end.
            job = db.get(Job, job_id)
            for ev in (job.events or []):
                yield f"data: {json.dumps(ev)}\n\n"
            yield "event: end\ndata: {}\n\n"
            return
        # Live job: replay everything emitted so far (so a reconnecting client
        # after a refresh sees full progress), then follow new events until done.
        cond = live["cond"]
        idx = 0
        while True:
            with cond:
                while idx >= len(live["events"]) and not live["done"]:
                    cond.wait(timeout=15)  # periodic wake keeps the loop responsive
                batch = live["events"][idx:]
                idx += len(batch)
                finished = live["done"] and idx >= len(live["events"])
            for ev in batch:
                yield f"data: {json.dumps(ev)}\n\n"
            if finished:
                yield "event: end\ndata: {}\n\n"
                return

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/health")
def health():
    cfg = get_settings()
    return {"ok": True, "provider": cfg.provider, "model": cfg.ollama_model}
