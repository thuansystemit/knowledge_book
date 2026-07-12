"""Celery tasks (enterprise backbone — Step 2). The extraction and retry work
that used to run in daemon threads now runs in a durable worker. Progress is
published to Redis (app.job_events) so any API replica can stream it; Postgres
is updated with the final result. The source PDF is read from the DB by job_id
(not passed through the broker)."""
from __future__ import annotations

import traceback

from app import job_events
from app.celery_app import celery_app
from app.config import get_settings
from app.db import session_scope
from app.llm.factory import get_provider
from app.models import DocumentFile, Job
from app.observability import audit
from app.pipeline import retry_failed, run as run_pipeline


@celery_app.task(name="run_extraction")
def run_extraction(job_id: str) -> None:
    cfg = get_settings()
    job_events.reset(job_id)  # fresh stream (also clean on a crash re-run)

    def on_event(ev: dict) -> None:
        job_events.publish(job_id, ev)

    status, graph, error = "done", None, None
    try:
        with session_scope() as db:
            job = db.get(Job, job_id)
            if job is None:
                return
            title = job.title
            provider_name, model_id = job.llm_provider, job.extraction_model
            f = db.get(DocumentFile, job_id)
            data = bytes(f.data) if f else None
        if data is None:
            raise ValueError("source file missing")
        def make_provider():   # fresh provider per worker thread (EXT-04 parallel)
            return get_provider(provider_name or None, model_id or None)
        provider = make_provider()
        graph = run_pipeline(data, title, provider, cfg, on_event=on_event,
                             make_provider=make_provider)
        # ACT-04: alert when a document's LLM cost crossed 80% of the cap.
        _cost = (graph or {}).get("cost") or {}
        if _cost.get("cap_warning"):
            audit("COST_ALERT", job=job_id, usd=_cost.get("usd"),
                  cap=_cost.get("cap_usd"), ratio=_cost.get("cap_ratio"))
    except Exception as e:
        status, error = "error", str(e)
        # Include the traceback tail in ops logs so a bare message like
        # "'str' object has no attribute 'get'" is diagnosable without a repro.
        audit("JOB_ERROR", job=job_id, error=str(e),
              trace=traceback.format_exc()[-2000:])
        on_event({"stage": "done", "status": "error", "detail": str(e)})
    finally:
        with session_scope() as db:
            job = db.get(Job, job_id)
            if job:
                job.status = status
                job.graph = graph
                job.events = job_events.all_events(job_id)
                job.error = error
                job.cost_usd = (graph or {}).get("cost", {}).get("usd") if graph else None
                _total = (graph or {}).get("stage_timings", {}).get("total_s") if graph else None
                job.duration_ms = int(_total * 1000) if _total else None
                job.ocr_confidence = (graph or {}).get("ocr_quality", {}).get("mean_confidence") if graph else None
        job_events.mark_done(job_id)


@celery_app.task(name="generate_interview_prep")
def generate_interview_prep(plan_id: str) -> None:
    from app.interview_prep import generate_plan
    try:
        generate_plan(plan_id)
    except Exception as e:
        from app.interview_prep import prep_publish, prep_mark_done
        try:
            with session_scope() as db:
                from app.models import InterviewPrepPlan
                plan = db.get(InterviewPrepPlan, plan_id)
                if plan:
                    plan.status = "error"
                    plan.error = str(e)
        except Exception:
            pass
        prep_publish(plan_id, {"stage": "done", "status": "error", "detail": str(e)})
        prep_mark_done(plan_id)


@celery_app.task(name="retry_extraction")
def retry_extraction(job_id: str) -> None:
    """Re-run the job's failed chunks and merge them into its existing graph."""
    cfg = get_settings()
    job_events.reset(job_id)

    def on_event(ev: dict) -> None:
        job_events.publish(job_id, ev)

    status, error, new_graph = "done", None, None
    try:
        with session_scope() as db:
            job = db.get(Job, job_id)
            if job is None:
                return
            graph, title = job.graph, job.title
            provider_name, model_id = job.llm_provider, job.extraction_model
        provider = get_provider(provider_name or None, model_id or None)
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
                    job.cost_usd = (new_graph.get("cost") or {}).get("usd")
                job.events = job_events.all_events(job_id)
                job.error = error
        job_events.mark_done(job_id)
