"""Interview-prep generation (IP-02): corpus-grounded study plan + questions.

A Celery task calls `generate_plan(plan_id)`. It scopes the corpus to exactly the
documents the user can already view (`visible_category_ids` ∪ own jobs — mirrors
`access.can_access_job`), retrieves relevant graph nodes per curriculum topic with
the existing zero-LLM `chat.retrieve`, asks the LLM for a structured JSON plan, and
persists it. Progress is streamed over the same Redis mechanism as jobs, namespaced
`prep:{plan_id}` so it can never collide with a real job stream.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from sqlalchemy import or_, select

from app import chat, job_events
from app.access import visible_category_ids
from app.config import get_settings
from app.costs import usd_for
from app.db import session_scope
from app.llm.factory import get_prep_provider
from app.models import InterviewPrepPlan, InterviewPrepQuestion, Job, User

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")

# Per-track curriculum (ctx §"Track curricula"). Order is the study order.
TRACK_CURRICULUM: dict[str, list[str]] = {
    "junior_backend": [
        "HTTP and REST basics", "CRUD API design", "SQL fundamentals",
        "ACID transactions", "authentication and JWT", "caching basics",
        "Docker and containers", "Git workflow", "error handling", "logging",
    ],
    "senior_backend": [
        "API design patterns REST gRPC GraphQL", "database indexing and query optimisation",
        "caching strategies and invalidation", "microservices and service decomposition",
        "distributed transactions", "asynchronous messaging queues",
        "observability metrics tracing logging", "security best practices",
        "performance profiling", "scalability patterns",
    ],
    "system_design": [
        "requirements gathering and capacity estimation", "CAP theorem and consistency models",
        "load balancing", "horizontal and vertical scaling",
        "database selection and sharding", "caching tiers Redis CDN",
        "asynchronous architectures Kafka SQS", "API gateways and rate limiting",
        "data replication and eventual consistency", "monitoring and alerting",
        "distributed transactions and sagas",
    ],
}

TRACKS = tuple(TRACK_CURRICULUM.keys())

_PROMPT_FILE = {
    "junior_backend": "interview_prep_junior.txt",
    "senior_backend": "interview_prep_senior.txt",
    "system_design": "interview_prep_sysdesign.txt",
}

_DIFFICULTIES = {"easy", "medium", "hard"}

# Generous token budget per batch: reasoning models spend tokens "thinking"
# before emitting JSON, so a small cap truncates the object and parsing fails.
PREP_MAX_TOKENS = 8000


# --------------------------------------------------------------------------- SSE
# Reuse job_events with a `prep:{plan_id}` id so the Redis keys become
# `job:prep:{id}:events` etc. — an isolated namespace, no new module (resolved Q4).
def _sid(plan_id: str) -> str:
    return f"prep:{plan_id}"


def prep_reset(plan_id: str) -> None:
    job_events.reset(_sid(plan_id))


def prep_publish(plan_id: str, event: dict) -> None:
    job_events.publish(_sid(plan_id), event)


def prep_mark_done(plan_id: str) -> None:
    job_events.mark_done(_sid(plan_id))


def prep_history_len(plan_id: str) -> int:
    return job_events.history_len(_sid(plan_id))


def prep_subscribe(plan_id: str):
    return job_events.subscribe(_sid(plan_id))


# ------------------------------------------------------------------- generation
def _load_prompt(track: str) -> str:
    with open(os.path.join(_PROMPT_DIR, _PROMPT_FILE[track]), "r", encoding="utf-8") as f:
        return f.read()


def _batched(seq: list, n: int):
    for i in range(0, len(seq), max(1, n)):
        yield seq[i:i + n]


def _topic_context(job_graphs: list[tuple], topic: str, cap: int) -> tuple[list[str], list[str], int]:
    """Aggregate the most relevant concept lines for `topic` across every viewable
    document. Returns (context_lines, source_docs, node_count)."""
    seen: set[str] = set()
    lines: list[str] = []
    sources: set[str] = set()
    for _jid, title, graph in job_graphs:
        relevant, _edges, _brief = chat.retrieve(graph or {}, topic)
        if relevant:
            sources.add(title)
        for n in relevant:
            nid = n.get("id")
            if nid in seen:
                continue
            seen.add(nid)
            definition = (n.get("definition") or "").strip()
            lines.append(f"- {n.get('name')} ({n.get('type', 'concept')}): {definition} "
                         f"[source: {title}]")
            if len(lines) >= cap:
                return lines, sorted(sources), len(lines)
    return lines, sorted(sources), len(lines)


def _coerce_questions(raw_questions, track: str) -> list[dict]:
    out = []
    for q in raw_questions or []:
        if not isinstance(q, dict) or not q.get("question"):
            continue
        diff = str(q.get("difficulty", "medium")).lower()
        if diff not in _DIFFICULTIES:
            diff = "medium"
        cites = q.get("citations")
        if not isinstance(cites, list):
            cites = []
        out.append({
            "track": track,
            "topic": str(q.get("topic", ""))[:255],
            "question": str(q.get("question", "")),
            "model_answer": str(q.get("model_answer", "")),
            "difficulty": diff,
            "citations": cites,
        })
    return out


def generate_plan(plan_id: str) -> None:
    """Full IP-02 generation body. Raises on failure (the Celery wrapper records
    the error + emits a terminal event)."""
    cfg = get_settings()
    prep_reset(plan_id)

    # --- Load plan + scope corpus (RBAC invariant #1/#2). Snapshot everything the
    # slow LLM phase needs so we don't hold a DB session open across network calls.
    with session_scope() as db:
        plan = db.get(InterviewPrepPlan, plan_id)
        if not plan:
            return
        user = db.get(User, plan.user_id)
        if not user:
            plan.status = "error"
            plan.error = "user not found"
            prep_publish(plan_id, {"stage": "done", "status": "error", "detail": plan.error})
            prep_mark_done(plan_id)
            return
        track = plan.track
        plan.status = "generating"
        plan.error = None
        visible = visible_category_ids(db, user)
        plan.category_ids = sorted(visible)  # write-once provenance snapshot
        jobs = db.scalars(
            select(Job).where(
                Job.status == "done",
                Job.graph.isnot(None),
                or_(Job.user_id == user.id, Job.category_id.in_(list(visible))),
            )
        ).all()
        job_graphs = [(j.id, j.title, j.graph) for j in jobs]

    prep_publish(plan_id, {"stage": "scanning", "detail": f"Found {len(job_graphs)} document(s) in your library."})

    if not job_graphs:
        with session_scope() as db:
            plan = db.get(InterviewPrepPlan, plan_id)
            if plan:
                plan.status = "error"
                plan.error = "no documents in your library"
        prep_publish(plan_id, {"stage": "done", "status": "error", "detail": "no documents in your library"})
        prep_mark_done(plan_id)
        return

    curriculum = TRACK_CURRICULUM[track]

    # --- Retrieval phase (zero-LLM) -----------------------------------------
    topic_ctx: dict[str, dict] = {}
    for topic in curriculum:
        prep_publish(plan_id, {"stage": "scanning", "detail": f"Scanning corpus for '{topic}'…"})
        lines, sources, count = _topic_context(job_graphs, topic, cfg.prep_max_context_nodes)
        topic_ctx[topic] = {"lines": lines, "sources": sources, "count": count}

    covered = [t for t in curriculum if topic_ctx[t]["count"] >= 2]
    thin = [t for t in curriculum if topic_ctx[t]["count"] < 2]

    # --- Generation phase (LLM, batched to cut round-trips) -----------------
    provider = get_prep_provider()
    model_id = getattr(provider, "model", None)
    system_prompt = _load_prompt(track)

    study_path: list[dict] = []
    checklist: dict[str, list[str]] = {}
    all_questions: list[dict] = []
    total_usd = 0.0
    order = 1

    failed_batches: list[str] = []
    for batch in _batched(curriculum, cfg.prep_topics_per_batch):
        prep_publish(plan_id, {"stage": "generating", "detail": f"Drafting: {', '.join(batch)}…"})
        ctx_blocks = []
        for topic in batch:
            info = topic_ctx[topic]
            block = f"### Topic: {topic}\nCoverage: {info['count']} concept(s)"
            block += " (THIN — flag as thin_coverage)\n" if info["count"] < 2 else "\n"
            block += "\n".join(info["lines"]) if info["lines"] else "(no relevant material found in the corpus)"
            ctx_blocks.append(block)
        user_text = (
            f"Track: {track}\nGenerate the interview-prep content for ONLY these "
            f"topics:\n\n" + "\n\n".join(ctx_blocks)
        )

        # A reasoning model (e.g. qwen) can spend its budget "thinking" and get
        # truncated before a complete JSON object exists — extract_json_object then
        # raises. Give it generous headroom and retry once. A single unparseable
        # batch must NOT fail the whole plan: skip it and keep what did generate.
        data = None
        for _attempt in range(2):
            try:
                raw = provider.complete_json(system_prompt, user_text, max_tokens=PREP_MAX_TOKENS)
                usage = getattr(provider, "last_usage", None)
                if usage:
                    total_usd += usd_for(model_id, usage.get("input_tokens", 0), usage.get("output_tokens", 0))
                else:
                    total_usd += usd_for(model_id, (len(system_prompt) + len(user_text)) // 4, len(raw) // 4)
                data = json.loads(raw)
                break
            except Exception:  # noqa: BLE001 — LLM/parse failure: retry, then skip
                continue

        if total_usd > cfg.max_prep_cost_usd:
            raise RuntimeError(
                f"interview-prep cost cap exceeded: ${total_usd:.4f} > ${cfg.max_prep_cost_usd:.2f}"
            )

        if data is None:
            failed_batches.extend(batch)
            prep_publish(plan_id, {"stage": "generating",
                                   "detail": f"Skipped {', '.join(batch)} (model output was not valid JSON)."})
            continue

        for sp in data.get("study_path", []) or []:
            if not isinstance(sp, dict):
                continue
            study_path.append({
                "order": order,
                "topic": sp.get("topic", ""),
                "description": sp.get("description", ""),
                "time_estimate_hours": sp.get("time_estimate_hours"),
                "source_docs": sp.get("source_docs") or topic_ctx.get(sp.get("topic", ""), {}).get("sources", []),
            })
            order += 1
        for topic_name, items in (data.get("checklist") or {}).items():
            if isinstance(items, list):
                checklist[topic_name] = [str(i) for i in items]
        all_questions.extend(_coerce_questions(data.get("questions"), track))

    # Only a *total* failure (no questions from any batch) is an error.
    if not all_questions:
        raise RuntimeError(
            "the model did not return usable content for any topic — please try again"
        )

    # --- Persist ------------------------------------------------------------
    plan_data = {
        "track": track,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model_id,
        "corpus_coverage": {
            "total_docs_scanned": len(job_graphs),
            "topics_with_coverage": len(covered),
            "topics_without_coverage": thin,
        },
        "study_path": study_path,
        "checklist": checklist,
    }

    with session_scope() as db:
        plan = db.get(InterviewPrepPlan, plan_id)
        if not plan:
            return
        db.query(InterviewPrepQuestion).filter(
            InterviewPrepQuestion.plan_id == plan_id
        ).delete(synchronize_session=False)
        for i, q in enumerate(all_questions):
            db.add(InterviewPrepQuestion(
                plan_id=plan_id, track=q["track"], topic=q["topic"],
                question=q["question"], model_answer=q["model_answer"],
                difficulty=q["difficulty"], citations=q["citations"], sort_order=i,
            ))
        plan.plan_data = plan_data
        plan.model = model_id
        plan.cost_usd = round(total_usd, 4)
        plan.status = "done"
        plan.error = None
        # Version history (IP-08): this new version becomes current; demote all
        # siblings. NO prune — retention is unlimited. The partial unique index
        # `uix_prep_current` validates "one current per (user, track)" at commit.
        db.query(InterviewPrepPlan).filter(
            InterviewPrepPlan.user_id == plan.user_id,
            InterviewPrepPlan.track == plan.track,
            InterviewPrepPlan.id != plan.id,
        ).update({"is_current": False}, synchronize_session=False)
        plan.is_current = True

    prep_publish(plan_id, {"stage": "done", "status": "done",
                           "detail": f"{len(all_questions)} question(s) ready."})
    prep_mark_done(plan_id)
