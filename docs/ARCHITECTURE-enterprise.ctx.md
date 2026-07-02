# CTX: Enterprise Architecture — KnowledgeBook

> **AI digest of `ARCHITECTURE-enterprise.md`. Self-contained — read this alone; you do NOT need the full `.md`.**
> Date: 2026-07-02. Status: DESIGN v1.0. Convention: paired `*.ctx.md`; keep in sync; work inline.

---

## Target System — Components

| Component | Responsibility | Tech |
|-----------|---------------|------|
| **API Fleet** | Stateless HTTP + SSE; subscribes Redis pub/sub for event fan-out; config cache reads; chat streaming in-process | FastAPI + uvicorn, N replicas |
| **Celery Workers** | Execute extraction jobs + retry-failed; publish progress events to Redis; persist results to Postgres | Celery 5.x, Redis broker, prefork, concurrency=2 |
| **Redis** | Celery broker (DB 0); pub/sub channels (job/chat/config invalidation); config/policy cache; rate-limit counters (DB 1) | Redis 7, single instance (Sentinel later) |
| **Postgres 16** | Source of truth: users, orgs, jobs, document_files, chat_sessions, chat_messages, categories, category_permissions, model_catalog, org_model_policies, org_api_keys, user_settings, credit_ledger, refresh_tokens | Existing, schema extended |
| **Load Balancer** | TLS termination, rate limiting (nginx limit_req), round-robin to API fleet | nginx or ALB |
| **Secret Store** | JWT_SECRET, platform API keys, DB encryption key (for BYO-key AES-256-GCM) | Vault / AWS SM / K8s Secrets (deploy-dependent) |
| **LLM Providers** | Extraction + chat completions | ollama / claude / openai (existing factory, extended with credential resolution) |

---

## SSE Streaming — Cross-Replica Design (the hard problem)

**Job progress SSE** (replaces in-memory `LIVE` dict + `threading.Condition`):

- **Worker** publishes events via Redis pipeline: `RPUSH job:{id}:events <json>` + `PUBLISH job:{id}:live <json>`. On terminal event: also `SET job:{id}:done 1 EX 3600`.
- **Any API replica** serves SSE by:
  1. If `job:{id}:done` exists: `LRANGE 0 -1` (replay all), emit `event: end`, return.
  2. If `job:{id}:events` doesn't exist (old/pre-migration job): read `job.events` from Postgres, replay, end.
  3. Live job: `LRANGE 0 -1` (replay history), then `SUBSCRIBE job:{id}:live` and yield new events until `done` event. After subscribe, re-LRANGE from last index to close the race gap.
  4. Heartbeat `: heartbeat\n\n` every 15s to keep connection alive.
- **Reconnect (browser refresh):** Client opens new SSE connection (any replica). Replay from Redis List + follow live. Existing `?t=stream_token` auth preserved.
- **TTL cleanup:** Redis event lists expire 1h after job completion. Postgres `job.events` is the permanent record.

**Chat token SSE** stays in-process (no change needed):
- Chat SSE is self-contained: stream-token auth → load context from Postgres → call `provider.stream_chat()` → yield tokens directly.
- No worker, no cross-replica coordination. LLM streaming iterator consumed synchronously in the response generator.
- Enforcement middleware wraps the route before streaming starts.

---

## Celery Job Lifecycle

- **Queue:** single `extraction` queue. Tasks: `run_extraction(job_id)`, `retry_failed_chunks(job_id)`.
- **Config:** `acks_late=True`, `reject_on_worker_lost=True` (crash recovery). `soft_time_limit=900`, `time_limit=960`.
- **State transitions:** `queued → running → done | error`. Postgres is source of truth. `POST /api/jobs` sets `status=queued` + dispatches Celery task.
- **Idempotency:** Task checks `job.status != "queued"` at start; skips if already processed.
- **Retries:** Celery-level `max_retries=2` for transient failures. Chunk-level `chunk_retries=2` (existing) for LLM parse errors.
- **Cost cap:** Existing per-doc cost ledger preserved. Cap exceeded → `status=error, error="cost_cap"`.
- **Events:** Worker publishes to Redis (see SSE section above). On completion, persists event list to `job.events` in Postgres.

---

## Config-as-Data (D14 / EF-28)

**Per-request model resolution — precedence chain:**
1. Request `model` param (explicit)
2. `user_settings.default_extraction_model` / `default_chat_model`
3. `org_model_policies.default_extraction_model` / `default_chat_model`
4. System default: `qwen2.5:3b` via Ollama (free-local)

**Validation:** Against `org_model_policies.allowed_models[]` (if org exists). AIRGAP_MODE=true → local models only.

**Credential resolution:**
- BYO-key: decrypt from `org_api_keys` (AES-256-GCM, encryption key from secret store)
- Platform key: from secret store (Team tier, credit-gated)
- Local (Ollama): no key needed

**Cache:** Redis cache with 60s TTL (`config:model_catalog`, `config:org_policy:{org_id}`). Invalidation: admin write → delete cached keys + `PUBLISH config:invalidate` → all API replicas clear local cache. Propagation < 1s.

**New tables:** `model_catalog`, `org_model_policies`, `org_api_keys`, `user_settings`.

---

## Multi-Tenancy + Enforcement Layer

**Tenancy (EF-12):**
- `org_id` added as **nullable FK** to `users`, `jobs`, `chat_sessions`. `NULL` = personal/on-prem/legacy.
- New `orgs` table: `id, name, tier (team|business|enterprise), is_active`.
- Request-scoped `TenantContext(user_id, user_role, org_id, org_tier)` via FastAPI dependency.
- `tenant_filter(query, model_class, tenant)`: if org_id → filter by org; else if admin → see all; else → filter by user_id.

**Category ACL (EF-27):**
- `categories(id, org_id nullable, name, created_by)`, `category_permissions(category_id, subject_type, subject_id, grant_type view|upload|manage)`.
- `jobs.category_id` nullable FK. Backfill: "General" category + `upload` grant for all existing users.
- `require_category_grant(job.category_id, min_grant, tenant)`: checks grant hierarchy.

**Unified enforcement (`enforce_job_access`):**
- Single FastAPI dependency that returns the `Job` object. Routes MUST use it to get a Job — cannot bypass.
- Checks: (1) job exists, (2) tenant scope, (3) category ACL, (4) returns Job.
- Replaces all per-route `_owned_job()` calls. One file (`app/enforcement.py`), < 50 lines.
- Model policy + credits check (`enforce_model_policy`) applied on mutations (job creation, chat) via separate dependency, composed with `enforce_job_access`.

---

## Rate Limiting (EF-02)

`slowapi` + Redis backend. Limits: 5 uploads/hr/user, 10 chats/min/user, 10 logins/min/IP, 60 req/min/user default. nginx `limit_req_zone` for DDoS layer.

## Secrets (EF-05)

`SecretProvider` interface: `EnvSecretProvider` (backward-compatible `.env`), `VaultSecretProvider` (cloud). Toggle via `SECRET_PROVIDER=env|vault`. BYO-keys: AES-256-GCM, encryption key in KMS/Vault.

## Observability (EF-07)

`structlog` (JSON logs + trace_id/org_id/user_id), `prometheus-fastapi-instrumentator` (`/metrics`), extended `/api/health` (DB + Redis + worker heartbeat). Sentry for error alerting.

## Backups (EF-06)

`pg_dump` daily + WAL archiving for PITR. Redis not backed up (ephemeral). Monthly restore test.

---

## ADRs (Summary)

| ID | Decision | Chosen | Rejected | Key Reason |
|----|---------|--------|---------|-----------|
| ADR-E1 | Job queue | Celery + Redis | arq, Dramatiq, RQ, pg-based | Redis already required for SSE + cache; Celery `acks_late` for crash recovery; mature ecosystem |
| ADR-E2 | SSE fan-out | Redis Pub/Sub + List | Redis Streams, PG LISTEN/NOTIFY | Pub/Sub=notification, List=history matches existing LIVE dict pattern; Streams add unnecessary consumer-group complexity |
| ADR-E3 | SQLAlchemy mode | Keep sync (psycopg2) | Async (asyncpg) | Zero migration effort; Celery workers are sync; LLM calls are the real bottleneck, not DB |
| ADR-E4 | Tenant scoping | FastAPI dependency | PostgreSQL RLS, ORM event hooks | Explicit, testable, works with existing sync SA; RLS + connection pooling is complex; enforcement layer makes bypass nearly impossible |

---

## Migration Order (incremental, each step independently deployable)

1. **Add Redis** to docker-compose (1 day) — no code change
2. **Celery + stateless SSE** (2-3 weeks) — EF-01 + EF-03: replaces daemon threads + LIVE dict with Celery tasks + Redis pub/sub+list
3. **Rate limiting** (2-3 days) — EF-02: slowapi + Redis
4. **Secrets management** (3-5 days) — EF-05: SecretProvider interface (parallel with 3)
5. **Observability** (3-5 days) — EF-07: structlog + prometheus (parallel with 3-4)
6. **Multi-tenancy foundation** (1-2 weeks) — EF-12: orgs table + nullable org_id + TenantContext
7. **Config-as-data** (2-3 weeks) — D14/EF-28: model_catalog + resolution + cache + invalidation
8. **Category ACL** (1-2 weeks) — EF-27: categories + grants + require_category_grant
9. **Enforcement layer** (1 week) — unify: enforce_job_access replaces _owned_job everywhere
10. **Multi-replica API** (1-2 days) — EF-17: scale horizontally (API is stateless after step 2)

Total: ~10-14 weeks. Steps 3/4/5 parallelizable.

---

## Open Questions

| # | Question | Blocking |
|---|---------|---------|
| AQ-1 | Redis: single instance vs Sentinel for P0? | Step 1 |
| AQ-2 | Alembic vs current `create_all` for migrations? | Step 6 |
| AQ-3 | Credit ledger: reserve-then-deduct vs check-then-deduct? | Step 7 |
| AQ-4 | On-prem: auto-create org for single-tenant installs? | Step 6 |
| AQ-5 | Chat SSE: persist to Redis List for cross-replica replay? (currently not needed) | Step 10 |
| AQ-6 | SSE: use `Last-Event-ID` for skip-ahead on reconnect? | Step 2 |

---

`pull_hint: "Mermaid diagrams (component + sequence + config flow), full ADR trade-off tables, enforcement code patterns, docker-compose target, detailed step-by-step migration → ARCHITECTURE-enterprise.md"`
