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
from sqlalchemy import func, or_, select, text

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
from app.interview_prep_routes import router as interview_prep_router
from app.migrations import (
    run_categories, run_interview_prep, run_interview_prep_versioning,
    run_models, run_plans, run_tenancy,
)
from app.model_resolver import get_catalog, invalidate_catalog, resolve as resolve_model, system_default
from app.models import ChatMessage, DocumentFile, Job, OrgModelPolicy, User, UserSettings
from app.observability import audit
from app import export as export_mod
from app.plans import (
    apply_free_tier_caps, can_export, effective_chat_mode, enforce_scanned_allowed,
    enforce_upload_quota, usage as plan_usage,
)
from app.ratelimit import upload_limit
from app.security import hash_password, make_stream, safe_decode
from app.tasks import backfill_briefs, retry_extraction, run_extraction

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
app.include_router(interview_prep_router)


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
    run_interview_prep()            # interview_prep_plans + questions tables (IP-01)
    run_interview_prep_versioning() # version + is_current columns + indexes (IP-06)


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


@app.get("/api/jobs/{job_id}/export")
def export_job(job_id: str, fmt: str = "md",
               user: User = Depends(get_current_user), db=Depends(get_db)):
    """Export the document's outputs as Markdown or JSON (OUT-06). Pro/Scholar only."""
    job = require_job_access(db, user, job_id)
    if not can_export(user):
        raise HTTPException(402, "Exporting is a Pro feature. Upgrade to download your outputs.")
    graph = job.graph or {}
    if not graph:
        raise HTTPException(409, "document is not ready")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (job.title or "document"))[:80]
    if fmt == "json":
        body = export_mod.to_json(graph, job.title)
        return Response(content=body, media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{safe}.json"'})
    body = export_mod.to_markdown(graph, job.title)
    return Response(content=body, media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{safe}.md"'})


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


@app.post("/api/jobs/{job_id}/reprocess")
def reprocess_job(job_id: str,
                  user: User = Depends(require_role("admin", "analyst")),
                  _rl: None = Depends(upload_limit),
                  db=Depends(get_db)):
    """Re-run the full extraction on the stored source PDF, replacing the outputs
    (OUT-07). Idempotent chunk caching (EXT-03) limits redundant LLM calls. Runs
    in the background; watch via the SSE stream. Does not consume upload quota."""
    job = _owned_job(job_id, user, db)
    if job.status == "running":
        raise HTTPException(409, "job is already running")
    if not db.scalar(select(DocumentFile.job_id).where(DocumentFile.job_id == job_id)):
        raise HTTPException(409, "no source file stored — cannot re-process")
    job.status = "running"
    job.events = []
    job.error = None
    db.commit()
    audit("REPROCESS_START", job=job_id, user=user.id)
    run_extraction.delay(job_id)   # replaces job.graph on completion
    return {"job_id": job_id, "reprocessing": True}


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
    _cfg = get_settings()
    _mode = effective_chat_mode(user, _cfg)
    return {
        "models": models,
        "default_extraction_model": (us.default_extraction_model if us else None) or system_default(),
        "default_chat_model": (us.default_chat_model if us else None) or system_default(),
        "require_byo_key": bool(policy.require_byo_key) if policy else False,
        # "retrieval" -> chat answers come from the extracted graph, no LLM at
        # query time, so the per-answer model picker is irrelevant. The mode is
        # per-user: Free plans get retrieval, Pro/Scholar get LLM (RC-20).
        "chat_mode": _mode,
        # PAY-06: true when upgrading would unlock AI chat (system supports LLM
        # but this user is on retrieval) — drives the Q&A-specific upgrade prompt.
        "chat_upgrade_available": _cfg.chat_mode == "llm" and _mode == "retrieval",
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


@app.get("/api/admin/costs")
def admin_costs(admin: User = Depends(require_role("admin")), db=Depends(get_db)):
    """Per-document cost telemetry for the ops dashboard (ACT-04 / EXT-02)."""
    cnt, total, avg, mx = db.execute(
        select(func.count(Job.id), func.coalesce(func.sum(Job.cost_usd), 0),
               func.coalesce(func.avg(Job.cost_usd), 0), func.coalesce(func.max(Job.cost_usd), 0))
        .where(Job.cost_usd.isnot(None))).one()
    top = db.scalars(select(Job).where(Job.cost_usd.isnot(None))
                     .order_by(Job.cost_usd.desc()).limit(10)).all()
    cap = get_settings().max_doc_cost_usd
    warn_at = round(0.8 * cap, 4) if cap else None
    # ACT-04: how many processed docs crossed 80% of the per-doc cap.
    near_cap = int(db.scalar(select(func.count(Job.id)).where(
        Job.cost_usd.isnot(None), Job.cost_usd >= 0.8 * cap)) or 0) if cap else 0

    def _top(j):
        c = float(j.cost_usd)
        stages = ((j.graph or {}).get("cost") or {}).get("by_stage") if j.graph else None
        return {
            "job_id": j.id, "title": j.title, "cost_usd": c,
            "cap_pct": round(c / cap, 3) if cap else None,
            "warn": bool(cap and c >= 0.8 * cap),
            "by_stage": {k: round(v.get("usd", 0), 4) for k, v in stages.items()} if stages else None,
        }

    return {
        "documents": int(cnt), "total_usd": round(float(total), 4),
        "avg_usd": round(float(avg), 4), "max_usd": round(float(mx), 4),
        "cap_usd": cap, "warn_threshold_usd": warn_at, "near_cap_count": near_cap,
        "top": [_top(j) for j in top],
    }


class BackfillBriefsIn(BaseModel):
    doc_ids: list[str] | None = None
    all_missing: bool = False


@app.post("/api/admin/backfill-briefs")
def backfill_briefs_endpoint(body: BackfillBriefsIn,
                             admin: User = Depends(require_role("admin")),
                             db=Depends(get_db)):
    """EFT-08: queue Brief regeneration for docs with `brief: null` (or a given
    list). Runs async in the worker; existing graph/chunks are untouched."""
    if body.all_missing:
        # graph is a `json` column (not jsonb) and may hold control chars, so
        # match on the text form rather than a jsonb operator.
        rows = db.execute(text(
            "SELECT id FROM jobs WHERE status='done' AND graph IS NOT NULL "
            r"AND graph::text ~ '\"brief\":\s*null'")).all()
        ids = [r[0] for r in rows]
    else:
        ids = list(body.doc_ids or [])
    if not ids:
        return {"queued": 0, "job_ids": []}
    backfill_briefs.delay(ids)
    return {"queued": len(ids), "job_ids": ids}


def _percentile(values: list[float], p: float):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    return round(s[f] + (s[f + 1] - s[f]) * (k - f)) if f + 1 < len(s) else round(s[f])


@app.get("/api/admin/metrics")
def admin_metrics(admin: User = Depends(require_role("admin")), db=Depends(get_db)):
    """Latency observability (ACT-05 pipeline + ACT-07 Q&A) for the ops dashboard."""
    # Pipeline end-to-end (ACT-05)
    durs = [int(d) for (d,) in db.execute(
        select(Job.duration_ms).where(Job.duration_ms.isnot(None))).all()]
    stage_vals: dict[str, list[float]] = {}
    for (g,) in db.execute(select(Job.graph).where(
            Job.status == "done", Job.duration_ms.isnot(None))
            .order_by(Job.created_at.desc()).limit(30)).all():
        for k, v in ((g or {}).get("stage_timings") or {}).items():
            if k != "total_s":
                stage_vals.setdefault(k, []).append(v * 1000)
    p90 = _percentile(durs, 0.9)
    # Q&A answer latency (ACT-07)
    lats = [int(x) for (x,) in db.execute(
        select(ChatMessage.latency_ms).where(ChatMessage.latency_ms.isnot(None))).all()]
    qa_median = _percentile(lats, 0.5)
    # OCR confidence distribution (ACT-06)
    confs = [float(c) for (c,) in db.execute(
        select(Job.ocr_confidence).where(Job.ocr_confidence.isnot(None))).all()]
    thr = get_settings().ocr_min_confidence
    buckets = {"0-50": 0, "50-70": 0, "70-85": 0, "85-100": 0}
    for c in confs:
        key = "0-50" if c < 50 else "50-70" if c < 70 else "70-85" if c < 85 else "85-100"
        buckets[key] += 1
    low = sum(1 for c in confs if c < thr)
    return {
        "pipeline": {
            "count": len(durs),
            "p50_ms": _percentile(durs, 0.5), "p90_ms": p90,
            "max_ms": max(durs) if durs else None,
            "budget_digital_ms": 300000, "budget_scanned_ms": 720000,
            "over_budget": bool(p90 and p90 > 720000),
            "stage_p90_ms": {k: _percentile(v, 0.9) for k, v in stage_vals.items()},
        },
        "qa": {
            "count": len(lats),
            "median_ms": qa_median, "p95_ms": _percentile(lats, 0.95),
            "budget_ms": 8000, "over_budget": bool(qa_median and qa_median > 8000),
        },
        "ocr": {
            "count": len(confs),
            "median": _percentile(confs, 0.5),
            "threshold": thr,
            "low_confidence": low,
            "low_confidence_rate": round(low / len(confs), 3) if confs else None,
            "histogram": buckets,
        },
    }


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
