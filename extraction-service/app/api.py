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

from fastapi import Depends, FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_, select

from app import job_events
from app.access import general_category_id, require_category, require_job_access, visible_category_ids
from app.admin_routes import router as admin_router
from app.activation_routes import router as activation_router
from app.auth_routes import router as auth_router
from app.billing_routes import router as billing_router
from app.category_routes import router as category_router
from app.chat_routes import router as chat_router
from app.config import get_settings
from app.db import Base, engine, get_db, session_scope
from app.deps import get_current_user, require_role
from app.migrations import run_categories, run_models, run_plans, run_tenancy
from app.model_resolver import get_catalog, invalidate_catalog, resolve as resolve_model, system_default
from app.models import DocumentFile, Job, OrgModelPolicy, User, UserSettings
from app.observability import audit
from app.plans import (
    apply_free_tier_caps, enforce_scanned_allowed, enforce_upload_quota,
    usage as plan_usage,
)
from app.ratelimit import upload_limit
from app.security import hash_password, make_stream, safe_decode
from app.tasks import retry_extraction, run_extraction

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
app.include_router(category_router)
app.include_router(billing_router)
app.include_router(activation_router)


@app.on_event("startup")
def _startup() -> None:
    Base.metadata.create_all(engine)
    # Must run before any `User` ORM query below: the User model maps the plan/
    # stripe columns, so a SELECT emitted by run_tenancy/_bootstrap_admin fails
    # until these columns exist (PAY-01/02/03, PAY-04).
    run_plans()                     # users.plan + stripe columns + backfill
    org_id = run_tenancy()          # org_id column + default org + backfill (EF-12)
    run_models()                    # jobs model columns + seed catalog (EF-28)
    _bootstrap_admin(org_id)
    run_categories()                # categories + grants + General backfill (EF-27)


def _bootstrap_admin(org_id: str) -> None:
    """Seed the first admin from env vars iff the users table is empty."""
    cfg = get_settings()
    with session_scope() as db:
        if db.scalar(select(User).limit(1)) is not None:
            return
        db.add(User(org_id=org_id, email=cfg.admin_email,
                    password_hash=hash_password(cfg.admin_password),
                    name="Administrator", role="admin"))
        audit("ADMIN_BOOTSTRAPPED", email=cfg.admin_email)


@app.post("/api/jobs")
async def create_job(file: UploadFile,
                     model: str | None = Form(default=None),
                     category_id: str | None = Form(default=None),
                     user: User = Depends(require_role("admin", "analyst")),
                     _rl: None = Depends(upload_limit),
                     db=Depends(get_db)):
    cfg = get_settings()
    # Monthly plan quota (PAY-01/02/03): block at-quota users with an upgrade
    # message before doing any file work. Admins are exempt.
    enforce_upload_quota(db, user, cfg)
    data = await file.read()
    if len(data) > cfg.max_file_bytes:
        raise HTTPException(413, f"file too large (> {cfg.max_file_bytes} bytes)")

    # Free tier is digital-only (PAY-01): classify and block scanned/hybrid PDFs
    # with an upgrade prompt. Only Free, non-admin users pay this classification
    # cost; fail-open if classification errors (the pipeline handles bad files).
    if user.role != "admin" and (user.plan or "free") == "free":
        try:
            from app.extraction.text_extractor import classify_pdf
            label, _ = classify_pdf(data)
        except Exception:
            label = "digital"  # fail-open — let the normal pipeline surface errors
        enforce_scanned_allowed(user, label)
    title = (file.filename or "document").rsplit(".", 1)[0]

    # Category ACL (EF-27): must have `upload` on the target category.
    cat = category_id or general_category_id(db, user.org_id)
    if not cat:
        raise HTTPException(400, "no category available")
    require_category(db, user, cat, "upload")

    provider, model_id = resolve_model(db, user, model, "extraction")
    job = Job(org_id=user.org_id, user_id=user.id, title=title, status="running", events=[],
              extraction_model=model_id, llm_provider=provider, category_id=cat)
    db.add(job)
    db.commit()
    # Keep the original file so the user can view the source and compare it with
    # chat answers.
    db.add(DocumentFile(job_id=job.id, filename=file.filename or "document.pdf",
                        mime=file.content_type or "application/pdf", data=data))
    db.commit()
    audit("JOB_START", job=job.id, user=user.id, title=title, bytes=len(data))
    run_extraction.delay(job.id)   # durable: runs in a Celery worker
    return {"job_id": job.id, "title": title}


@app.get("/api/jobs")
def list_jobs(category_id: str | None = None,
              user: User = Depends(get_current_user), db=Depends(get_db)):
    q = select(Job).order_by(Job.created_at.desc())
    if user.role != "admin":
        # Category ACL: jobs in a category the user can view, or their own.
        vis = visible_category_ids(db, user)
        q = q.where(or_(Job.category_id.in_(vis), Job.user_id == user.id))
    if category_id:
        q = q.where(Job.category_id == category_id)
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
    job = require_job_access(db, user, job_id)
    d = job.detail()
    # Free-tier concept-map cap (PAY-01): trims the served graph + adds paywall
    # metadata for the upgrade prompt. Non-mutating; paid/admin pass through.
    d["graph"] = apply_free_tier_caps(d.get("graph"), user, get_settings())
    # Cheap existence check (selects the key only, not the blob).
    d["has_pdf"] = db.scalar(select(DocumentFile.job_id).where(DocumentFile.job_id == job_id)) is not None
    return d


@app.get("/api/jobs/{job_id}/pdf")
def get_pdf(job_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    require_job_access(db, user, job_id)
    f = db.get(DocumentFile, job_id)
    if not f:
        raise HTTPException(404, "no source file stored for this document")
    return Response(content=f.data, media_type=f.mime or "application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{f.filename}"'})


@app.post("/api/jobs/{job_id}/retry-failed")
def retry_failed_chunks(job_id: str,
                        user: User = Depends(require_role("admin", "analyst")),
                        _rl: None = Depends(upload_limit),
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
    audit("RETRY_START", job=job_id, failed=len(failed))
    retry_extraction.delay(job_id)   # durable: runs in a Celery worker
    return {"job_id": job_id, "retrying": len(failed)}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    job = _owned_job(job_id, user, db)
    db.delete(job)
    db.commit()
    job_events.reset(job_id)   # drop any Redis stream for this job
    return {"ok": True}


@app.post("/api/jobs/{job_id}/stream-token")
def stream_token(job_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    require_job_access(db, user, job_id)
    return {"token": make_stream(user.id, job_id)}


@app.get("/api/jobs/{job_id}/events")
def stream_events(job_id: str, t: str = "", db=Depends(get_db)):
    # EventSource can't send Authorization headers, so auth rides in `t`.
    claims = safe_decode(t, "stream")
    if not claims or claims.get("job") != job_id:
        raise HTTPException(401, "invalid stream token")
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "job not found")

    # Capture what the generator needs before the request session closes.
    running = job.status == "running"
    db_events = list(job.events or [])
    has_redis_stream = job_events.history_len(job_id) > 0

    def gen():
        if has_redis_stream or running:
            # Live/recent job — replay Redis history then follow live until done
            # (works across replicas; the worker publishes, any API serves it).
            for ev in job_events.subscribe(job_id):
                yield f"data: {json.dumps(ev)}\n\n"
        else:
            # Finished and expired from Redis — replay persisted DB events.
            for ev in db_events:
                yield f"data: {json.dumps(ev)}\n\n"
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/models")
def list_models(user: User = Depends(get_current_user), db=Depends(get_db)):
    """Models available to the caller (catalog filtered by org policy) + defaults."""
    catalog = get_catalog()
    policy = db.get(OrgModelPolicy, user.org_id) if user.org_id else None
    allowed = set(policy.allowed_models) if policy and policy.allowed_models else {m["model_id"] for m in catalog}
    models = [m for m in catalog if m["model_id"] in allowed]
    us = db.get(UserSettings, user.id)
    return {
        "models": models,
        "default_extraction_model": (us.default_extraction_model if us else None) or system_default(),
        "default_chat_model": (us.default_chat_model if us else None) or system_default(),
        "require_byo_key": bool(policy.require_byo_key) if policy else False,
        # "retrieval" -> chat answers come from the extracted graph, no LLM at
        # query time, so the per-answer model picker is irrelevant.
        "chat_mode": get_settings().chat_mode,
    }


class ModelDefaultsIn(BaseModel):
    default_extraction_model: str | None = None
    default_chat_model: str | None = None


@app.put("/api/me/model-defaults")
def set_model_defaults(body: ModelDefaultsIn, user: User = Depends(get_current_user), db=Depends(get_db)):
    us = db.get(UserSettings, user.id) or UserSettings(user_id=user.id)
    if body.default_extraction_model is not None:
        us.default_extraction_model = body.default_extraction_model or None
    if body.default_chat_model is not None:
        us.default_chat_model = body.default_chat_model or None
    db.merge(us)
    db.commit()
    return {"ok": True}


class ModelPolicyIn(BaseModel):
    allowed_models: list[str] | None = None
    default_extraction_model: str | None = None
    default_chat_model: str | None = None
    require_byo_key: bool | None = None


@app.put("/api/orgs/{org_id}/model-policy")
def set_model_policy(org_id: str, body: ModelPolicyIn,
                     admin: User = Depends(require_role("admin")), db=Depends(get_db)):
    if admin.org_id and admin.org_id != org_id:
        raise HTTPException(403, "not your organization")
    p = db.get(OrgModelPolicy, org_id) or OrgModelPolicy(org_id=org_id)
    if body.allowed_models is not None:
        p.allowed_models = body.allowed_models
    if body.default_extraction_model is not None:
        p.default_extraction_model = body.default_extraction_model or None
    if body.default_chat_model is not None:
        p.default_chat_model = body.default_chat_model or None
    if body.require_byo_key is not None:
        p.require_byo_key = body.require_byo_key
    db.merge(p)
    db.commit()
    invalidate_catalog()  # policy affects resolution; drop cache fleet-wide
    return {"ok": True}


@app.get("/api/admin/model-assignments")
def admin_model_assignments(admin: User = Depends(require_role("admin")), db=Depends(get_db)):
    """Configuration page data: every user in the org + their assigned models,
    plus the org policy and the catalog (allowed models)."""
    catalog = get_catalog()
    policy = db.get(OrgModelPolicy, admin.org_id) if admin.org_id else None
    allowed = set(policy.allowed_models) if policy and policy.allowed_models else {m["model_id"] for m in catalog}
    models = [m for m in catalog if m["model_id"] in allowed]

    users = db.scalars(select(User).where(User.org_id == admin.org_id).order_by(User.email)).all()
    uids = [u.id for u in users]
    settings = {s.user_id: s for s in db.scalars(
        select(UserSettings).where(UserSettings.user_id.in_(uids))).all()} if uids else {}

    return {
        "org_id": admin.org_id,
        "system_default": system_default(),
        "models": models,
        "policy": {
            "allowed_models": policy.allowed_models if policy else [],
            "default_extraction_model": policy.default_extraction_model if policy else None,
            "default_chat_model": policy.default_chat_model if policy else None,
            "require_byo_key": bool(policy.require_byo_key) if policy else False,
        },
        "users": [{
            "id": u.id, "email": u.email, "name": u.name, "role": u.role,
            "default_extraction_model": (settings.get(u.id).default_extraction_model if settings.get(u.id) else None),
            "default_chat_model": (settings.get(u.id).default_chat_model if settings.get(u.id) else None),
        } for u in users],
    }


@app.put("/api/admin/users/{user_id}/model-defaults")
def admin_set_user_models(user_id: str, body: ModelDefaultsIn,
                          admin: User = Depends(require_role("admin")), db=Depends(get_db)):
    """Admin assigns a specific user's default models (EF-28). Empty string
    clears the assignment → the user falls back to org/system default."""
    target = db.get(User, user_id)
    if not target or target.org_id != admin.org_id:
        raise HTTPException(404, "user not found in this organization")
    catalog_ids = {m["model_id"] for m in get_catalog()}
    for m in (body.default_extraction_model, body.default_chat_model):
        if m and m not in catalog_ids:
            raise HTTPException(400, f"unknown model: {m}")
    us = db.get(UserSettings, user_id) or UserSettings(user_id=user_id)
    if body.default_extraction_model is not None:
        us.default_extraction_model = body.default_extraction_model or None
    if body.default_chat_model is not None:
        us.default_chat_model = body.default_chat_model or None
    db.merge(us)
    db.commit()
    audit("ADMIN_SET_USER_MODELS", admin=admin.id, target=user_id)
    return {"ok": True}


@app.get("/api/usage")
def get_usage(user: User = Depends(get_current_user), db=Depends(get_db)):
    """Current user's plan + monthly upload usage (PAY-06 / ACT). Drives the
    frontend quota meter and contextual upgrade prompts."""
    return plan_usage(db, user, get_settings())


@app.get("/api/health")
def health():
    from app.redis_client import ping as redis_ping
    cfg = get_settings()
    return {"ok": True, "provider": cfg.provider, "model": cfg.ollama_model,
            "redis": redis_ping()}
