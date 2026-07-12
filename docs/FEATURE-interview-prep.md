# Feature: Interview Prep

| | |
|---|---|
| **Document** | Feature Spec + Delivery Plan |
| **Version** | 1.0 |
| **Date** | 2026-07-08 |
| **Status** | PLANNED (not started) |
| **Parents** | `PRD-knowledge-graph-mvp.md`, `ARCHITECTURE-mvp.md`, `FEATURE-document-chat.md` |
| **Feature ID** | interview-prep |

> Lets a logged-in user generate a **personalized interview preparation plan** —
> study path, topic checklist, practice questions, and mock Q&A — grounded
> entirely in the technical documents they have already ingested into
> KnowledgeBook. Three tracks are supported: **Junior Backend**, **Senior
> Backend**, and **System Design**.

---

## 1. Problem statement

Engineers preparing for technical interviews have rich personal document
libraries — textbooks, architecture notes, design documents — but no structured
way to convert them into targeted practice material. KnowledgeBook already
extracts, indexes, and makes those documents searchable. This feature adds a
dedicated generation layer that turns the user's existing corpus into an
interview-ready study plan, grounded in sources the user has already vetted.

**Current pain:** a user who ingested "The Pragmatic Programmer" and a set of
system-design articles must manually re-read them and create flashcards or
question lists by hand. The knowledge is already in the graph — it just isn't
surfaced in a study-ready format.

---

## 2. Target users

| Persona | Key need | Estimated reach |
|---|---|---|
| Junior engineer (0–3 yrs) preparing for first backend role | Knows what topics exist but does not know what depth interviewers expect | Large — the primary consumer segment |
| Mid-level engineer targeting Staff / Senior promotion | Needs scenario-based depth and system-design confidence | Mid-size — growing with the product |
| Scholar-tier student preparing for internship or new-grad | Needs structured reading order across multiple textbooks | Growing — Scholar plan users |

---

## 3. The three tracks

Each track defines a **fixed curriculum** (ordered topic list), a **difficulty
profile**, and a **question style**. The curriculum is the skeleton; the corpus
provides the flesh.

### 3.1 Junior Backend

**Goal:** Prove foundational command of backend concepts. Interviewers expect
clean definitions and the ability to apply patterns in simple scenarios.

| Dimension | Value |
|---|---|
| Topics (ordered) | HTTP & REST, CRUD APIs, SQL fundamentals, ACID transactions, authentication & JWT, caching basics (Redis), Docker & containers, Git workflow, error handling, logging |
| Difficulty profile | 70 % easy · 25 % medium · 5 % hard |
| Question style | "Define X", "explain the difference between X and Y", simple "write a route that does Z" (conceptual, no live coding) |
| Questions generated | 15–20 |

### 3.2 Senior Backend

**Goal:** Demonstrate trade-off awareness, depth of design judgment, and
distributed-systems literacy. Interviewers look for "why", not just "what".

| Dimension | Value |
|---|---|
| Topics (ordered) | API design patterns (REST vs gRPC vs GraphQL), database indexing & query optimisation, caching strategies & invalidation, microservices & service decomposition, distributed transactions, asynchronous messaging (queues), observability (metrics/tracing/logging), security best practices, performance profiling, scalability patterns |
| Difficulty profile | 10 % easy · 50 % medium · 40 % hard |
| Question style | Trade-off analysis, scenario-based ("your API latency spikes under load — walk me through your investigation"), "design a subsystem" mini-questions |
| Questions generated | 20–25 |

### 3.3 System Design

**Goal:** Demonstrate the ability to decompose a vague problem into a working
distributed architecture, with explicit discussion of CAP theorem, consistency,
and operational concerns. The canonical final-round screen.

| Dimension | Value |
|---|---|
| Topics (ordered) | Requirements gathering & estimation, CAP theorem & consistency models, load balancing, horizontal vs vertical scaling, database selection & sharding, caching tiers (in-process / Redis / CDN), asynchronous architectures (Kafka / SQS), API gateways & rate limiting, data replication & eventual consistency, monitoring & alerting, distributed transactions & sagas |
| Difficulty profile | 5 % easy · 30 % medium · 65 % hard |
| Question style | Open-ended "design X" (e.g. "design a URL shortener"), follow-up probing ("how would you handle 10× traffic?"), architecture trade-off narratives |
| Questions generated | 10–15 (each carries more depth than a factual question) |

---

## 4. RAG grounding approach

Interview Prep reuses the existing retrieval infrastructure — **no new embedding
or chunking work is required**.

### 4.1 Corpus scoping (RBAC-safe)

At plan generation time the worker calls `visible_category_ids(db, user)` from
`app/access.py` and snapshots the result on the plan row. It then queries:

```sql
SELECT * FROM jobs
WHERE  status = 'done'
  AND  graph IS NOT NULL
  AND  (user_id = :user_id OR category_id = ANY(:visible_category_ids))
```

This exactly mirrors `can_access_job` — the user sees exactly the same corpus
in their prep plan as they do in the library. The snapshot is stored so that
if category grants change later the plan still shows which documents were used.

### 4.2 Per-topic retrieval

For every topic in the track's ordered curriculum the worker calls
`chat.retrieve(graph, topic_query)` from `app/chat.py` on each in-scope job,
collecting the top relevant nodes and edges. The aggregated context (deduped by
node ID across documents) is what feeds the LLM prompt.

If `EMBEDDING_MODEL` is configured, `embeddings.embed_query(topic_query, cfg)`
augments the keyword retrieval with cosine ranking (the same `_semantic_indices`
path used in `compose_answer`).

### 4.3 LLM generation

The aggregated retrieval context is passed to the LLM (configurable — reuses
`PREP_PROVIDER`/`PREP_MODEL`, defaults to `CHAT_PROVIDER`/`CHAT_MODEL`) with
a track-specific system prompt that instructs it to:

- produce a structured JSON response (study path, per-topic checklist, questions
  with difficulty tags and model answers, citations)
- ground every question and answer in the supplied context only
- flag topics where coverage is thin (corpus does not cover this topic well)

Thin-coverage topics are surfaced to the user as a warning chip on the relevant
section ("Your documents have limited material on this topic — consider adding
resources").

### 4.4 Cost control

Each generation task uses the existing `CostLedger` mechanism (`app/costs.py`)
to track LLM spend and enforces `MAX_PREP_COST_USD` (default `0.50`). If the
cap would be exceeded the task aborts with `status = 'error'` and a descriptive
message; partial results up to that point are discarded.

---

## 5. Data model

Two new tables. Both added via the app's startup `create_all` + idempotent
migration helper (same pattern as `run_plans`, `run_categories`).

### `interview_prep_plans`

```
id              String(32)  PK, default uuid4().hex
user_id         String(32)  FK users.id, index
org_id          String(32)  nullable, index
track           String(32)  'junior_backend' | 'senior_backend' | 'system_design'
status          String(16)  'pending' | 'generating' | 'done' | 'error'
error           Text        nullable
category_ids    JSON        list[str] — snapshot of visible_category_ids at generation time
plan_data       JSON        nullable — full generated output (see §5.3)
model           String(100) nullable — model that produced this plan
cost_usd        Numeric(8,4) nullable
created_at      DateTime(timezone=True)
updated_at      DateTime(timezone=True), onupdate=now
```

`UNIQUE(user_id, track)` — one active plan per user per track. A regenerate
request updates the existing row (status → pending) rather than creating a new
one.

### `interview_prep_questions`

```
id              String(32)  PK, default uuid4().hex
plan_id         String(32)  FK interview_prep_plans.id ON DELETE CASCADE, index
track           String(32)
topic           String(255)
question        Text
model_answer    Text
difficulty      String(8)   'easy' | 'medium' | 'hard'
citations       JSON        list[{node_id, name, chapter, page_start, page_end, doc_title}]
sort_order      Integer     display order within the plan
created_at      DateTime(timezone=True)
```

### 5.3 `plan_data` JSON shape

```json
{
  "track": "junior_backend",
  "generated_at": "2026-07-08T12:00:00Z",
  "model": "claude-3-5-haiku-20241022",
  "corpus_coverage": {
    "total_docs_scanned": 3,
    "topics_with_coverage": 8,
    "topics_without_coverage": ["Kubernetes", "gRPC"]
  },
  "study_path": [
    {
      "order": 1,
      "topic": "REST API Design",
      "description": "one-sentence rationale for this position in the path",
      "time_estimate_hours": 3,
      "source_docs": ["The Pragmatic Programmer"]
    }
  ],
  "checklist": {
    "REST API Design": [
      "Understand the six REST constraints",
      "Know idempotent vs safe HTTP methods",
      "Be able to version an API without breaking clients"
    ]
  }
}
```

`plan_data` holds the study path, checklist, and corpus metadata. Questions are
stored in `interview_prep_questions` rows (relational, easier to query and
paginate) with a `plan_id` foreign key.

---

## 6. API endpoints

All endpoints live under `/api/interview-prep`. Auth is `Bearer` JWT via
`get_current_user`. RBAC rules are stated per endpoint.

| Method | Path | Auth / RBAC | Purpose |
|---|---|---|---|
| POST | `/api/interview-prep` | Bearer; any role | Create (or reset) a plan for the given track |
| GET | `/api/interview-prep` | Bearer; any role | List caller's plans (admin: all plans in org) |
| GET | `/api/interview-prep/{plan_id}` | Bearer; owner or admin | Full plan + questions |
| POST | `/api/interview-prep/{plan_id}/regenerate` | Bearer; owner or admin | Re-queue the generation task |
| POST | `/api/interview-prep/{plan_id}/stream-token` | Bearer; owner or admin | Issue a short-lived SSE token |
| GET | `/api/interview-prep/{plan_id}/events?t=` | SSE stream token | Real-time generation progress |
| DELETE | `/api/interview-prep/{plan_id}` | Bearer; owner or admin | Delete plan + questions |

### 6.1 Create — `POST /api/interview-prep`

Request body:
```json
{ "track": "junior_backend" }
```

Behaviour: if a plan with `(user_id, track)` already exists, reset it to
`status = 'pending'` and re-queue the Celery task (idempotent upsert). If the
plan does not yet exist, create it. Returns immediately.

RBAC check: `get_current_user` (any authenticated role). No category check here
— the Celery worker does the scoping at generation time.

Response:
```json
{ "plan_id": "abc123", "status": "pending" }
```

HTTP 400 if `track` is not one of the three valid values.

### 6.2 Get plan — `GET /api/interview-prep/{plan_id}`

RBAC: `plan.user_id == user.id` **or** `user.role == 'admin'`. Returns 403
otherwise, 404 if the plan does not exist.

Response: plan row (all columns) + `questions` list (all rows for this
plan, ordered by `sort_order`).

### 6.3 Regenerate — `POST /api/interview-prep/{plan_id}/regenerate`

RBAC: same as get. Resets `status = 'pending'`, clears `plan_data`, deletes
existing question rows, and dispatches `generate_interview_prep.delay(plan_id)`.

### 6.4 Stream token + SSE

Mirrors the existing chat-stream pattern exactly: `make_prep_stream(user_id,
plan_id)` in `app/security.py` issues a short-lived JWT (`typ = 'prep-stream'`,
TTL = `PREP_STREAM_TOKEN_TTL_SEC`, default 300 s). The SSE endpoint validates
it and streams Redis events published by the Celery task.

Event frames:
```
data: {"stage": "scanning", "detail": "Scanning 3 documents…"}
data: {"stage": "generating", "detail": "Generating questions for REST API Design…"}
data: {"stage": "done", "status": "done"}
event: end
data: {}
```

### 6.5 List plans — `GET /api/interview-prep`

Returns all three track slots for the calling user (even if not yet generated),
so the frontend can show which tracks are available, which are pending, and
which are ready. Admin users see all plans in the org (paginated, 50 per page).

---

## 7. Async generation (Celery task)

New task `generate_interview_prep(plan_id: str)` in `app/tasks.py`.

### Execution steps

```
1. Load plan from DB (track, user_id, org_id)
2. Load user from DB
3. Call visible_category_ids(db, user) → snapshot → store on plan.category_ids
4. Query jobs: status=done, graph not null, (user_id=user OR category_id IN visible)
5. If no jobs found → status = 'error', message = "no documents in your library"
6. For each topic in TRACK_CURRICULUM[track] (ordered):
   a. Publish stage event {"stage": "scanning", "detail": f"Scanning topic: {topic}"}
   b. For each job, call chat.retrieve(job.graph, topic)
   c. Aggregate top nodes (dedup by node id); collect citations
   d. Optionally augment via embeddings.embed_query + semantic indices
7. Build the LLM prompt (track-specific system prompt + aggregated context)
8. Publish {"stage": "generating", "detail": "Drafting questions…"}
9. Call provider.chat(...) (non-streaming; structured JSON output via llm/_json.py)
10. Parse response; enforce MAX_PREP_COST_USD (abort if exceeded)
11. Persist plan_data on plan row
12. Bulk-insert interview_prep_questions rows
13. Update plan.status = 'done', plan.cost_usd, plan.model
14. Publish {"stage": "done", "status": "done"}
```

If any step raises an exception, update `plan.status = 'error'`,
`plan.error = str(e)`, publish a `{"stage": "done", "status": "error"}` event.

The task is dispatched via `generate_interview_prep.delay(plan_id)` and
registered in `app/celery_app.py`. It reuses `session_scope` and `get_settings`
exactly as `run_extraction` does.

---

## 8. Frontend

### 8.1 Route

`/interview-prep` — added to `App.tsx` inside the `ProtectedRoute`/`AppLayout`
block (same level as `/documents`). No role restriction beyond authentication
(viewers included).

### 8.2 Page: `InterviewPrepPage.tsx`

**State machine for the page:**

| State | What the user sees |
|---|---|
| `no_docs` | Warning banner: "You have no processed documents. Upload at least one before generating a prep plan." |
| `pick_track` | Three track cards (Junior Backend / Senior Backend / System Design), each with a one-sentence description and a "Generate Plan" button. If a plan for that track already exists, the button says "View Plan" or "Regenerate". |
| `generating` | Progress panel with a spinner, current stage label, and a list of stages completed so far. The user can navigate away and come back. |
| `ready` | Full plan view — tabs for Study Path, Checklist, Practice Questions. Each question shows difficulty badge, question text, and a collapsed "Model Answer" panel. Thin-coverage topics show a warning chip. A "Regenerate" button in the page header triggers the regenerate endpoint. |
| `error` | Error card with the error message and a "Try Again" button. |

### 8.3 Components

| Component | Location | Purpose |
|---|---|---|
| `InterviewPrepPage` | `routes/InterviewPrepPage.tsx` | Top-level route; loads plan list; owns page state |
| `TrackCard` | `components/interview-prep/TrackCard.tsx` | Single track picker card with status badge |
| `PrepPlanView` | `components/interview-prep/PrepPlanView.tsx` | Renders a ready plan — study path + checklist + questions |
| `PrepProgressPanel` | `components/interview-prep/PrepProgressPanel.tsx` | SSE-driven progress display during generation |
| `QuestionCard` | `components/interview-prep/QuestionCard.tsx` | Question text + difficulty badge + collapsible model answer + citation chips |

### 8.4 API client: `api/interview-prep.api.ts`

Functions:
- `createPlan(track)` → `POST /api/interview-prep`
- `listPlans()` → `GET /api/interview-prep`
- `getPlan(planId)` → `GET /api/interview-prep/{plan_id}`
- `regeneratePlan(planId)` → `POST /api/interview-prep/{plan_id}/regenerate`
- `getStreamToken(planId)` → `POST /api/interview-prep/{plan_id}/stream-token`
- `subscribePrepStream(planId, token, onEvent)` → `EventSource` (same pattern as `api/chat.api.ts subscribeChatStream`)
- `deletePlan(planId)` → `DELETE /api/interview-prep/{plan_id}`

---

## 9. RBAC summary

| Action | Who | How enforced |
|---|---|---|
| Create a prep plan | Any authenticated user (admin, analyst, viewer) | `get_current_user` — no role gate; any role can generate a plan |
| Corpus scoping | Automatic — worker uses `visible_category_ids` | Jobs only included if `user_id = caller` or `category_id IN visible_category_ids` |
| View own plan | Plan owner | `plan.user_id == user.id` check in route handler |
| View any plan | Admin only | `user.role == 'admin'` check |
| Regenerate | Owner or admin | Same as view |
| Delete | Owner or admin | Same as view |
| Viewers see shared plans | Not in scope (Phase 2) | Admin-curated shared question banks are deferred |

**Critical invariant:** The corpus a plan is generated from is always a subset
of what `visible_category_ids` + own jobs returns — the same check used by
`can_access_job`. A user can never read content from a document they could not
already see via the library.

---

## 10. Configuration (env)

| Var | Default | Meaning |
|---|---|---|
| `PREP_PROVIDER` | `CHAT_PROVIDER` (fallback to main `LLM_PROVIDER`) | LLM provider for plan generation |
| `PREP_MODEL` | `CHAT_MODEL` (fallback to provider default) | Model for generation |
| `MAX_PREP_COST_USD` | `0.50` | Hard abort cost cap per generation run |
| `PREP_STREAM_TOKEN_TTL_SEC` | `300` | SSE token lifetime |
| `PREP_MAX_CONTEXT_NODES` | `40` | Max graph nodes fed per topic into the LLM prompt |
| `PREP_TOPICS_PER_BATCH` | `3` | Topics bundled per LLM call (reduces round trips) |

---

## 11. Telemetry & acceptance criteria

### Acceptance criteria (per ticket)

| ID | Criterion |
|---|---|
| IP-01 AC | `interview_prep_plans` and `interview_prep_questions` tables created by startup migration; all columns present |
| IP-02 AC | A generation task for a user with 1 processed document completes without error; `plan_data` is non-null and parseable; at least 5 questions exist in `interview_prep_questions` |
| IP-03 AC | All endpoints return correct HTTP status codes for valid and invalid requests; RBAC blocks cross-user access (403); stream token correctly scoped |
| IP-04 AC | `/interview-prep` page renders in Chromium; track picker shows 3 cards; generating state shows live stage labels via SSE; ready state shows questions with collapsed answers |
| IP-05 AC | A user whose `visible_category_ids` is empty (no category grants and no own jobs) receives `status = 'error'` with message "no documents in your library"; they cannot see content from any other user's documents |

### Success metrics (post-launch measurement)

| Metric | Target | How measured |
|---|---|---|
| Plan generation success rate | ≥ 90 % of plan creation requests reach `status = done` | Count `status = done` / total in `interview_prep_plans` |
| Generation latency (p90) | ≤ 120 s end-to-end | `updated_at − created_at` on done plans |
| Questions per plan | ≥ 10 (min usable) | `COUNT` of `interview_prep_questions` rows per plan |
| 7-day retention on prep page | ≥ 30 % of users who generated a plan return within 7 days | New activation event `kind = prep_view` |
| Cost per plan | ≤ $0.20 median | `cost_usd` column |

---

## 12. Milestones & sprint mapping

| Milestone | Target | Items |
|---|---|---|
| **M-IP-1 — Data layer** | Sprint N | IP-01: tables + migration |
| **M-IP-2 — Backend complete** | Sprint N | IP-02: Celery task; IP-03: API endpoints + SSE |
| **M-IP-3 — Frontend complete** | Sprint N+1 | IP-04: InterviewPrepPage + components |
| **M-IP-4 — Hardening** | Sprint N+1 | IP-05: RBAC edge cases; empty corpus; cost cap; acceptance criteria pass |

---

## 13. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Hallucinated questions**: LLM generates questions not grounded in the corpus | High | High — user studies wrong material | Strict system prompt; cite every question to a node; surface thin-coverage warnings; reviewer spot-check in acceptance run |
| **Stale corpus**: user's documents are old; generated questions reflect outdated patterns | Medium | Medium | Show `generated_at` timestamp prominently; "Regenerate" button always visible; warn when corpus has no docs updated in > 6 months |
| **Generation cost overrun**: large corpus + many topics = many LLM calls | Medium | Medium | `MAX_PREP_COST_USD` hard cap; batch topics per LLM call; chunk-cache is not applicable here (questions are unique per user) |
| **Empty corpus (no docs)**: user has no viewable jobs | Medium | Low — graceful error | Detect at task start; return clear error state in UI; surface an upload prompt |
| **Model quality variance**: local Ollama model produces poor questions for System Design track | High | Medium — user gets low-quality plan | Default `PREP_PROVIDER=claude` for prod; document the local fallback as low-fidelity |
| **Plan staleness**: user's category grants change after generation | Low | Low — plan is a snapshot | Show the `category_ids` snapshot to the user ("Generated from N documents"); "Regenerate" re-scopes to current grants |

---

## 14. Future (Phase 2 — out of scope now)

- **Mock interview mode**: interactive Q&A loop where the user types an answer,
  and the system evaluates it against the model answer using the LLM. Requires
  a new endpoint and a separate session model.
- **Admin-curated shared question banks**: admins can publish a curated question
  set visible to all users in the org, beyond the personal corpus. Requires a
  `subject_type = 'org'` extension to the permission model.
- **Multi-document cross-corpus synthesis**: generate questions that synthesise
  across multiple books simultaneously (e.g. "what does the CAP theorem material
  say vs the database internals book"). Deferred — high coordination complexity.
- **Export prep plan** as Markdown / Anki deck: useful for offline study.

---

## 15. Files

| File | Change |
|---|---|
| `app/models.py` | Add `InterviewPrepPlan`, `InterviewPrepQuestion` ORM models |
| `app/migrations.py` | Add `run_interview_prep()` — idempotent table creation |
| `app/api.py` | Call `run_interview_prep()` on startup; include `interview_prep_router` |
| `app/prompts/interview_prep_junior.txt` | System prompt for Junior Backend generation |
| `app/prompts/interview_prep_senior.txt` | System prompt for Senior Backend generation |
| `app/prompts/interview_prep_sysdesign.txt` | System prompt for System Design generation |
| `app/interview_prep.py` (new) | Track curricula, corpus aggregation, LLM call, parsing |
| `app/interview_prep_routes.py` (new) | All `/api/interview-prep/*` routes |
| `app/tasks.py` | Add `generate_interview_prep` Celery task |
| `app/security.py` | Add `make_prep_stream` (mirrors `make_chat_stream`) |
| `app/config.py` | Add `prep_provider`, `prep_model`, `max_prep_cost_usd`, `prep_stream_token_ttl_sec`, `prep_max_context_nodes`, `prep_topics_per_batch` |
| `frontend/src/api/interview-prep.api.ts` (new) | API client |
| `frontend/src/routes/InterviewPrepPage.tsx` (new) | Top-level route |
| `frontend/src/components/interview-prep/TrackCard.tsx` (new) | Track picker card |
| `frontend/src/components/interview-prep/PrepPlanView.tsx` (new) | Plan tabs view |
| `frontend/src/components/interview-prep/PrepProgressPanel.tsx` (new) | SSE progress |
| `frontend/src/components/interview-prep/QuestionCard.tsx` (new) | Question + answer |
| `frontend/src/App.tsx` | Add `/interview-prep` route |

---

*End of Feature Spec v1.0.*
