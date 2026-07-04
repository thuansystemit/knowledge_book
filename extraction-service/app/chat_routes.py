"""/api/jobs/{job_id}/chat* — graph-grounded, multi-turn chat over a document.

Streaming reuses the app's SSE + short-lived stream-token pattern (EventSource
can't send auth headers, so the token rides in ?t=)."""
from __future__ import annotations

import json
import re
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import require_job_access
from app import embeddings
from app.chat import build_context, compose_answer
from app.config import get_settings
from app.db import get_db, session_scope
from app.deps import get_current_user
from app.llm.factory import get_provider
from app.model_resolver import provider_for, resolve as resolve_model, system_default
from app.models import ChatMessage, ChatSession, Job, User
from app.plans import effective_chat_mode
from app.observability import audit
from app.ratelimit import chat_limit
from app.security import make_chat_stream, safe_decode

router = APIRouter(tags=["chat"])


class AskIn(BaseModel):
    question: str
    model: str | None = None


def _owned_job(job_id: str, user: User, db: Session) -> Job:
    # Category-aware access (EF-27): admin, owner, or `view` grant on the category.
    return require_job_access(db, user, job_id)


def _get_or_create_session(db: Session, job_id: str, user_id: str) -> ChatSession:
    s = db.scalar(select(ChatSession).where(
        ChatSession.job_id == job_id, ChatSession.user_id == user_id))
    if s is None:
        job = db.get(Job, job_id)
        s = ChatSession(org_id=job.org_id if job else None, job_id=job_id, user_id=user_id)
        db.add(s)
        db.commit()
    return s


@router.post("/api/jobs/{job_id}/chat")
def ask(job_id: str, body: AskIn,
        user: User = Depends(get_current_user),
        _rl: None = Depends(chat_limit), db=Depends(get_db)):
    # Any role may chat, gated per-document by `_owned_job` (admin, owner, or a
    # `view` grant on the category). Chat is a read-only lookup over a document
    # the user can already see — viewers included.
    job = _owned_job(job_id, user, db)
    if job.status != "done" or not job.graph:
        raise HTTPException(409, "document is not ready for chat")
    question = (body.question or "").strip()
    if not question:
        raise HTTPException(400, "empty question")

    session = _get_or_create_session(db, job_id, user.id)
    # Only resolve a model when an LLM will actually answer; retrieval mode needs
    # none (and avoids per-role model-policy checks for viewers).
    # RC-20 value ladder: Free plans always get retrieval (no LLM model resolved),
    # Pro/Scholar (and admins) get LLM when the server is in LLM mode.
    llm = effective_chat_mode(user, get_settings()) == "llm"
    model_id = resolve_model(db, user, body.model, "chat")[1] if llm else None
    msg = ChatMessage(session_id=session.id, role="user", content=question, model=model_id)
    db.add(msg)
    db.commit()
    audit("CHAT_ASK", job=job_id, user=user.id, msg=msg.id)
    # Activation: user asked ≥1 Q&A on this doc (ACT-03). Idempotent; best-effort.
    try:
        from app import activation
        activation.record_qa(db, user.id, job_id, org_id=job.org_id)
    except Exception:
        pass
    return {"message_id": msg.id, "stream_token": make_chat_stream(user.id, job_id, msg.id)}


@router.get("/api/jobs/{job_id}/chat/{msg_id}/stream")
def stream_answer(job_id: str, msg_id: str, t: str = "", db=Depends(get_db)):
    claims = safe_decode(t, "chat-stream")
    if not claims or claims.get("job") != job_id or claims.get("msg") != msg_id:
        raise HTTPException(401, "invalid stream token")

    job = db.get(Job, job_id)
    user_msg = db.get(ChatMessage, msg_id)
    if not job or not user_msg:
        raise HTTPException(404, "not found")
    session = db.get(ChatSession, user_msg.session_id)
    user = db.get(User, claims.get("sub"))

    cfg = get_settings()
    # Per-user chat mode (RC-20): Free -> retrieval, Pro/Scholar/admin -> LLM.
    mode = effective_chat_mode(user, cfg) if user else "retrieval"
    # Build the conversation history (chronological), capped to the last N turns.
    history_rows = db.scalars(
        select(ChatMessage).where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in history_rows][-cfg.chat_history_turns:]

    # Retrieval mode (default): compose the answer deterministically from the
    # extracted graph — no query-time LLM call. Reuses the same SSE contract
    # (one token frame + a done frame) so the frontend is unchanged.
    if mode != "llm":
        _qa_t0 = time.monotonic()
        # Previous user turn (for anaphoric follow-ups, RC-17).
        prev_q = next((m.content for m in reversed(history_rows)
                       if m.role == "user" and m.id != user_msg.id), None)
        # RC-14: embed the question for semantic matching (None if disabled/failed).
        qvec = embeddings.embed_query(user_msg.content, cfg) if embeddings.enabled(cfg) else None
        answer, citations, weak = compose_answer(
            job.graph, user_msg.content, prev_q,
            query_vector=qvec, sim_threshold=cfg.embedding_sim_threshold)
        qa_latency_ms = int((time.monotonic() - _qa_t0) * 1000)  # ACT-07
        # RC-22: on a weak/not-covered answer, prompt the user to upgrade — but
        # only when upgrading would actually unlock LLM chat (server in LLM mode
        # and this user is gated out by plan; admins never see it).
        can_upgrade = (cfg.chat_mode == "llm" and user is not None
                       and user.role != "admin"
                       and effective_chat_mode(user, cfg) == "retrieval")
        show_upgrade = bool(weak and can_upgrade)

        def gen_retrieval():
            with session_scope() as s:
                s.add(ChatMessage(session_id=session.id, role="assistant",
                                  content=answer, citations=citations,
                                  model="retrieval-v1", latency_ms=qa_latency_ms))
            # Stream word-by-word for a natural typing effect (like ChatGPT/Claude)
            # instead of dumping the whole answer at once. The frontend already
            # appends token frames incrementally, so no UI change is needed.
            delay = max(cfg.retrieval_stream_delay_ms, 0) / 1000.0
            tokens = re.findall(r"\S+\s*", answer) or [answer]
            for tok in tokens:
                yield f"data: {json.dumps({'token': tok})}\n\n"
                if delay:
                    time.sleep(delay)
            yield f"data: {json.dumps({'done': True, 'citations': citations, 'upgrade': show_upgrade})}\n\n"
            yield "event: end\ndata: {}\n\n"

        return StreamingResponse(gen_retrieval(), media_type="text/event-stream")

    # LLM mode: stream a generated answer from the configured chat model.
    system_prompt, citations = build_context(job.graph, user_msg.content)
    model_id = user_msg.model or system_default()
    provider_name = provider_for(model_id)

    def gen():
        provider = get_provider(provider_name, model_id)
        parts: list[str] = []
        _t0 = time.monotonic()
        try:
            for token in provider.stream_chat(system_prompt, history, max_tokens=2048):
                parts.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:  # e.g. LLM host unreachable
            audit("CHAT_STREAM_ERROR", job=job_id, error=str(e))
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "event: end\ndata: {}\n\n"
            return
        answer = "".join(parts).strip()
        latency_ms = int((time.monotonic() - _t0) * 1000)  # ACT-07 (generation time)
        # Persist the assistant message.
        with session_scope() as s:
            s.add(ChatMessage(session_id=session.id, role="assistant",
                              content=answer, citations=citations,
                              model=getattr(provider, "model", provider.name),
                              latency_ms=latency_ms))
        yield f"data: {json.dumps({'done': True, 'citations': citations})}\n\n"
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/api/jobs/{job_id}/chat/history")
def history(job_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    _owned_job(job_id, user, db)
    session = db.scalar(select(ChatSession).where(
        ChatSession.job_id == job_id, ChatSession.user_id == user.id))
    if not session:
        return {"session_id": None, "messages": []}
    rows = db.scalars(select(ChatMessage).where(ChatMessage.session_id == session.id)
                      .order_by(ChatMessage.created_at)).all()
    return {"session_id": session.id, "messages": [m.public() for m in rows]}


@router.delete("/api/jobs/{job_id}/chat")
def clear(job_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    _owned_job(job_id, user, db)
    session = db.scalar(select(ChatSession).where(
        ChatSession.job_id == job_id, ChatSession.user_id == user.id))
    if session:
        db.delete(session)
        db.commit()
    return {"ok": True}
