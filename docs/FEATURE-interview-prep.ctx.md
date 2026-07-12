# CTX: Interview Prep (corpus-grounded study plan generation)

> **AI digest of `FEATURE-interview-prep.md`. Self-contained — read this alone.**
> Status: PLANNED, not started (2026-07-08). Convention: paired `*.ctx.md`; keep in sync.

## What
Any authenticated user picks a track (`junior_backend` | `senior_backend` | `system_design`). A Celery task retrieves relevant graph nodes from every document the user can already view (RBAC-scoped), passes them to the LLM, and persists a structured prep plan (study path + per-topic checklist + practice questions + model answers with citations). A dedicated frontend page renders the plan with live SSE progress during generation.

## Locked decisions
- **Reuse `chat.retrieve()` + `embeddings.embed_query()`** — no new retrieval infra.
- **Corpus scope = `visible_category_ids(user)` + own jobs** — exactly mirrors `can_access_job`; snapshot stored on plan row.
- **Async Celery** — generation can take 30–120 s; SSE progress via Redis `job_events`-style pattern.
- **UNIQUE(user_id, track)** on plans — upsert on re-generate; no duplicate rows per user per track.
- **Non-streaming LLM call** — structured JSON response via `app/llm/_json.py`; not SSE token-by-token.
- **`MAX_PREP_COST_USD` = 0.50 default** — hard abort if exceeded, same pattern as `_enforce_cost_cap`.
- Deferred: mock-interview interactive mode, admin-curated question banks, Anki export.

## Track curricula (TRACK_CURRICULUM dict in app/interview_prep.py)
```python
TRACK_CURRICULUM = {
    "junior_backend": [
        "HTTP and REST basics", "CRUD API design", "SQL fundamentals",
        "ACID transactions", "authentication and JWT", "caching basics",
        "Docker and containers", "Git workflow", "error handling", "logging"
    ],
    "senior_backend": [
        "API design patterns REST gRPC GraphQL", "database indexing and query optimisation",
        "caching strategies and invalidation", "microservices and service decomposition",
        "distributed transactions", "asynchronous messaging queues",
        "observability metrics tracing logging", "security best practices",
        "performance profiling", "scalability patterns"
    ],
    "system_design": [
        "requirements gathering and capacity estimation", "CAP theorem and consistency models",
        "load balancing", "horizontal and vertical scaling",
        "database selection and sharding", "caching tiers Redis CDN",
        "asynchronous architectures Kafka SQS", "API gateways and rate limiting",
        "data replication and eventual consistency", "monitoring and alerting",
        "distributed transactions and sagas"
    ],
}
```

## Data model (two new tables)
`interview_prep_plans(id PK, user_id FK users.id idx, org_id idx, track VARCHAR(32), status VARCHAR(16) [pending|generating|done|error], error TEXT NULL, category_ids JSON, plan_data JSON NULL, model VARCHAR(100) NULL, cost_usd NUMERIC(8,4) NULL, created_at, updated_at; UNIQUE(user_id, track))`

`interview_prep_questions(id PK, plan_id FK interview_prep_plans.id CASCADE idx, track VARCHAR(32), topic VARCHAR(255), question TEXT, model_answer TEXT, difficulty VARCHAR(8) [easy|medium|hard], citations JSON, sort_order INT, created_at)`

`plan_data` JSON keys: `track`, `generated_at`, `model`, `corpus_coverage{total_docs_scanned, topics_with_coverage, topics_without_coverage[]}`, `study_path[{order, topic, description, time_estimate_hours, source_docs[]}]`, `checklist{topic_name: [str]}`.
Questions are rows in `interview_prep_questions`, not embedded in `plan_data`.

## Migration
Add `run_interview_prep()` to `app/migrations.py`. Call from `_startup()` in `app/api.py` after `run_categories()`. Pattern: `inspect(engine).has_table('interview_prep_plans') or Base.metadata.create_all(engine, tables=[...])`.

## Celery task (app/tasks.py)
```python
@celery_app.task(name="generate_interview_prep")
def generate_interview_prep(plan_id: str) -> None:
    # 1. load plan + user from DB
    # 2. visible_category_ids(db, user) → snapshot → plan.category_ids
    # 3. query jobs: status=done, graph not null, (user_id=user OR category_id IN visible)
    # 4. if no jobs: plan.status='error', plan.error='no documents in your library'; return
    # 5. for topic in TRACK_CURRICULUM[plan.track]:
    #      for each job: chat.retrieve(job.graph, topic) → collect top nodes (dedup by id)
    #      optionally: embed_query(topic, cfg) + semantic indices
    #    publish prep_events.publish(plan_id, {"stage":"scanning","detail":f"Scanning {topic}…"})
    # 6. build LLM prompt (load prompts/interview_prep_{track}.txt, inject context)
    #    publish {"stage":"generating","detail":"Drafting questions…"}
    # 7. provider.chat(system, messages, max_tokens=4096) — non-streaming
    #    enforce MAX_PREP_COST_USD via CostLedger pattern
    # 8. parse JSON response → plan_data dict + list[question dicts]
    # 9. bulk insert interview_prep_questions; update plan.plan_data, .status='done', .cost_usd, .model
    # 10. publish {"stage":"done","status":"done"}; prep_events.mark_done(plan_id)
    # on any exception: plan.status='error', plan.error=str(e)
```

Use `session_scope()` (context manager from `app/db`) for all DB writes, same as `run_extraction`.
Publish events via a `prep_events` module (mirrors `app/job_events.py` but keyed `prep:{plan_id}` in Redis).

## Corpus query (in the task, not the route)
```python
from sqlalchemy import or_, select
jobs = db.scalars(
    select(Job).where(
        Job.status == "done",
        Job.graph.isnot(None),
        or_(Job.user_id == user.id,
            Job.category_id.in_(list(visible_cat_ids)))
    )
).all()
```

## API (app/interview_prep_routes.py)
All under `/api/interview-prep`, tag `["interview-prep"]`.

| Method | Path | RBAC check | Notes |
|---|---|---|---|
| POST | `/api/interview-prep` | `get_current_user` (any role) | upsert plan; dispatch task; 400 if bad track |
| GET | `/api/interview-prep` | any role | own plans; admin gets org-all (paginated 50) |
| GET | `/api/interview-prep/{plan_id}` | owner or admin | include questions list |
| POST | `/api/interview-prep/{plan_id}/regenerate` | owner or admin | reset status+data; dispatch task |
| POST | `/api/interview-prep/{plan_id}/stream-token` | owner or admin | `make_prep_stream(user.id, plan_id)` |
| GET | `/api/interview-prep/{plan_id}/events?t=` | prep-stream JWT | SSE; validates `safe_decode(t, 'prep-stream')` |
| DELETE | `/api/interview-prep/{plan_id}` | owner or admin | cascades questions |

Owner-or-admin check: `_require_plan_access(plan, user)` — raise 403 if `plan.user_id != user.id and user.role != 'admin'`.
Register router in `app/api.py`: `app.include_router(interview_prep_router)`.

## SSE pattern (reuse)
`make_prep_stream(user_id, plan_id)` in `app/security.py` — JWT `typ='prep-stream'`, TTL `cfg.prep_stream_token_ttl_sec` (default 300). Event frames identical to job events: `data: {json}\n\n`, terminated by `event: end\ndata: {}\n\n`. Frontend `EventSource` pattern identical to chat stream.

## Config additions (app/config.py Settings)
```python
prep_provider: str = ""           # default: falls back to chat_provider then LLM_PROVIDER
prep_model: str = ""              # default: falls back to chat_model then provider default
max_prep_cost_usd: float = 0.50
prep_stream_token_ttl_sec: int = 300
prep_max_context_nodes: int = 40  # max nodes per topic fed to LLM
prep_topics_per_batch: int = 3    # topics per LLM call (reduce round trips)
```

## LLM provider wiring
Use `get_prep_provider()` in `app/llm/factory.py` (mirrors `get_chat_provider()`): read `cfg.prep_provider`/`cfg.prep_model`; fall back to `get_chat_provider()`.
Call `provider.chat(system, messages, max_tokens=4096)` — NOT `stream_chat`. All three providers already support non-streaming via their sync `complete`/`chat` method if it exists; verify or add a `chat()` method to the protocol if missing.

## Prompts (app/prompts/)
Three files: `interview_prep_junior.txt`, `interview_prep_senior.txt`, `interview_prep_sysdesign.txt`.
Each must instruct the model to: output strict JSON (study_path array, checklist dict, questions array with {topic, question, model_answer, difficulty, citations}); ground every item in the supplied context only; flag topics as thin-coverage when context is sparse (< 2 relevant nodes).

## Frontend (React + TS + Vite)
Route: `/interview-prep` in `App.tsx` inside `<ProtectedRoute><AppLayout>` block — no role restriction beyond auth.

New files:
- `frontend/src/routes/InterviewPrepPage.tsx` — owns page state machine (no_docs|pick_track|generating|ready|error); fetches `listPlans()` on mount; selects a plan by track
- `frontend/src/components/interview-prep/TrackCard.tsx` — card per track with status badge (Not Started / Generating / Ready); "Generate" or "View / Regenerate" CTA
- `frontend/src/components/interview-prep/PrepProgressPanel.tsx` — EventSource over SSE stream; stage label list; auto-transitions to ready on `done` event
- `frontend/src/components/interview-prep/PrepPlanView.tsx` — three tabs: Study Path (ordered list) | Checklist (expandable per topic) | Practice Questions
- `frontend/src/components/interview-prep/QuestionCard.tsx` — difficulty badge (easy=green, medium=amber, hard=red), question text, collapsible model answer, citation chips (same chip style as ChatTab)
- `frontend/src/api/interview-prep.api.ts` — `createPlan`, `listPlans`, `getPlan`, `regeneratePlan`, `getStreamToken`, `subscribePrepStream` (EventSource), `deletePlan`

## RBAC invariants (must hold end-to-end)
1. A plan's corpus = `visible_category_ids(user) ∪ {jobs where user_id == user}` at generation time — never more.
2. Category snapshot on `plan.category_ids` is write-once at generation start; shown to user as provenance.
3. Cross-user plan access always raises 403 for non-admin users — no exceptions.
4. No role can trigger plan generation that reads documents they cannot already access via the library.

## Files
`app/models.py` (InterviewPrepPlan, InterviewPrepQuestion) · `app/migrations.py` (run_interview_prep) · `app/api.py` (include router + startup call) · `app/interview_prep.py` (new — curricula, context aggregation, LLM call, JSON parsing) · `app/interview_prep_routes.py` (new — all routes) · `app/tasks.py` (generate_interview_prep task) · `app/security.py` (make_prep_stream) · `app/config.py` (6 new settings) · `app/llm/factory.py` (get_prep_provider) · `app/prompts/interview_prep_{junior,senior,sysdesign}.txt` (3 new prompts) · `frontend/src/api/interview-prep.api.ts` (new) · `frontend/src/routes/InterviewPrepPage.tsx` (new) · `frontend/src/components/interview-prep/{TrackCard,PrepPlanView,PrepProgressPanel,QuestionCard}.tsx` (4 new) · `frontend/src/App.tsx` (add route)
