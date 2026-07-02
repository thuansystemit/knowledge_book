# Data Model -- Enterprise KnowledgeBook

**Date:** 2026-07-02  
**Author:** @data-modeler  
**Status:** FINALIZED  
**Sources:** `ENTERPRISE-productization.ctx.md` (EF-01..EF-28, D1..D14), `ARCHITECTURE-enterprise.ctx.md` (ADR-E1..E4, AQ-1..AQ-6), current SQLAlchemy models (`extraction-service/app/models.py`)

---

## Resolved Open Questions

### AQ-2: Alembic vs. current `create_all`

**Decision: Adopt Alembic immediately.**

Rationale: The multi-tenancy rollout (nullable `org_id` -> backfill -> NOT NULL enforcement) is a multi-step data migration that `create_all` cannot express. `create_all` only adds missing tables/columns; it cannot alter existing columns, backfill data, add constraints to populated tables, or create partial indexes. Alembic is the SQLAlchemy-native migration tool and requires zero ORM changes (ADR-E3 keeps sync SQLAlchemy). The migration is already incremental -- each Alembic revision maps to one deployable step.

Implementation: `alembic init alembic` in `extraction-service/`, point `env.py` at the existing `Base.metadata`, stamp the current production DB with an initial revision (`alembic stamp head`), then author forward migrations. All new tables and column additions go through Alembic revisions, never `create_all`.

### AQ-3: Credit ledger -- reserve-then-deduct vs. check-then-deduct

**Decision: Reserve-then-deduct (two-phase).**

Rationale: check-then-deduct has a TOCTOU race -- two concurrent requests can both see sufficient balance then both spend, overdrawing the account. Reserve-then-deduct prevents this: a `credit_reservations` row is inserted (and the reserved amount is subtracted from available balance atomically via `SELECT ... FOR UPDATE` on the org's balance), then on job completion the reservation is converted to a spend entry (or released on failure/abort). This is the standard pattern for financial ledgers and prevents double-spend without requiring serializable isolation level.

Mechanics:
1. `POST /api/jobs` (premium model) -> insert `credit_reservations` row with estimated cost. Use `SELECT ... FOR UPDATE` on `credit_balances` to atomically check + decrement available balance. If insufficient, return 402.
2. Job completes successfully -> delete reservation, insert `credit_ledger` spend entry with actual cost. Update `credit_balances.balance`.
3. Job fails/aborts -> delete reservation, restore balance to `credit_balances`. Optionally insert a zero-amount ledger entry for audit trail.
4. Stale reservations (worker crash) -> background sweep expires reservations older than 2x `soft_time_limit` (30 min), restores balance, logs incident.

### AQ-4: On-prem / single-tenant auto-create

**Decision: Auto-create a default organization on first boot when no orgs exist.**

Implementation: An Alembic data migration (or application startup hook) checks `SELECT COUNT(*) FROM organizations`. If zero, inserts a row `(id=<uuid>, name='Default', slug='default', tier='enterprise', is_active=true)`. All existing users are assigned `org_id` = this default org during the tenancy backfill migration. On-prem installs never create additional orgs. SaaS installs create orgs via the admin API. Same schema, same code, zero branching.

---

## ID Strategy

**Decision: Migrate from `String(32)` hex to native `UUID` column type.**

Rationale: Postgres `UUID` type is 16 bytes (vs. 32 bytes for hex string), has native indexing support, and is the standard for distributed systems. The existing 32-char hex strings are valid UUID hex representations (`uuid.uuid4().hex`) and can be cast to `UUID` type with `::uuid` without data loss.

Migration impact: This is a type-change migration on every table with a `String(32)` PK or FK. It must be done carefully:
1. Add new `UUID` columns alongside existing `String(32)` columns (or use `ALTER COLUMN ... TYPE UUID USING id::uuid` which Postgres supports for hex-to-UUID cast).
2. The `USING` cast approach is simpler and can be done in a single `ALTER TABLE` per table, but locks the table briefly. For the current data volumes (pre-enterprise, likely < 100k rows), this is acceptable.
3. Execute in dependency order: parent tables first (users), then child tables (jobs, chat_sessions, refresh_tokens), then grandchild tables (document_files, chat_messages).
4. Update SQLAlchemy models to use `Uuid` mapped type with `default=uuid.uuid4`.

**If the team judges the type migration too risky for the first release**, keep `VARCHAR(32)` and add new tables with `UUID`. I recommend doing the conversion early (small data volume = low risk) rather than later (large data volume = high risk + longer lock).

The DDL below uses `UUID` as the target type.

---

## Entity Registry

| Entity | Table Name | Owner Service | New? | Volume Estimate | Retention |
|--------|-----------|--------------|------|----------------|----------|
| Organization | `organizations` | API | NEW | 10s (SaaS) / 1 (on-prem) | Permanent |
| User | `users` | API | MODIFIED (+org_id) | 100s-1000s | Permanent (soft-delete via is_active) |
| Job (Document) | `jobs` | API + Worker | MODIFIED (+org_id, category_id, extraction_model, llm_provider) | 1000s-10000s | Permanent (user-deletable) |
| Document File | `document_files` | API | UNCHANGED | 1:1 with jobs | Same as job |
| Chat Session | `chat_sessions` | API | MODIFIED (+org_id) | 1:1 per (job, user) | Same as job |
| Chat Message | `chat_messages` | API | UNCHANGED (model col exists) | 10s per session | Same as session |
| Refresh Token | `refresh_tokens` | API | UNCHANGED | Transient | Expire + sweep |
| Category | `categories` | API | NEW | 10s-100s per org | Permanent (RESTRICT on delete) |
| Category Permission | `category_permissions` | API | NEW | 100s per org | Permanent |
| Model Catalog | `model_catalog` | API | NEW | 10-20 rows (global) | Permanent |
| Org Model Policy | `org_model_policies` | API | NEW | 1 per org | Permanent |
| User Settings | `user_settings` | API | NEW | 1 per user | Permanent |
| Org API Key | `org_api_keys` | API | NEW | 1-3 per org | Permanent (revocable) |
| Credit Balance | `credit_balances` | API | NEW | 1 per org | Permanent |
| Credit Ledger | `credit_ledger` | API | NEW | 100s-1000s per org | 2 years (financial) |
| Credit Reservation | `credit_reservations` | API + Worker | NEW | Transient (< active jobs) | Auto-expire |
| Audit Log | `audit_log` | API | NEW | 1000s/month per org | 90d (Business) / unlimited (Enterprise) |

---

## ERD (Mermaid)

```mermaid
erDiagram
    ORGANIZATIONS {
        uuid id PK
        varchar name
        varchar slug UK
        varchar tier
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }

    USERS {
        uuid id PK
        uuid org_id FK
        varchar email UK
        varchar password_hash
        varchar name
        varchar role
        boolean is_active
        timestamptz created_at
    }

    CATEGORIES {
        uuid id PK
        uuid org_id FK
        varchar name
        text description
        uuid created_by FK
        timestamptz created_at
        timestamptz updated_at
    }

    CATEGORY_PERMISSIONS {
        uuid id PK
        uuid category_id FK
        varchar subject_type
        uuid subject_id
        varchar grant_type
        uuid granted_by FK
        timestamptz granted_at
    }

    JOBS {
        uuid id PK
        uuid org_id FK
        uuid user_id FK
        uuid category_id FK
        varchar title
        varchar status
        text error
        json events
        json graph
        varchar extraction_model
        varchar llm_provider
        timestamptz created_at
        timestamptz updated_at
    }

    DOCUMENT_FILES {
        uuid job_id PK_FK
        varchar filename
        varchar mime
        bytea data
        timestamptz created_at
    }

    CHAT_SESSIONS {
        uuid id PK
        uuid org_id FK
        uuid job_id FK
        uuid user_id FK
        timestamptz created_at
        timestamptz updated_at
    }

    CHAT_MESSAGES {
        uuid id PK
        uuid session_id FK
        varchar role
        text content
        jsonb citations
        varchar model
        timestamptz created_at
    }

    REFRESH_TOKENS {
        uuid id PK
        uuid user_id FK
        boolean revoked
        timestamptz expires_at
        timestamptz created_at
    }

    MODEL_CATALOG {
        uuid id PK
        varchar provider
        varchar model_id UK
        varchar label
        varchar tier_availability
        numeric credit_cost_extraction
        numeric credit_cost_chat
        boolean is_local
        boolean is_enabled
        int sort_order
        timestamptz created_at
        timestamptz updated_at
    }

    ORG_MODEL_POLICIES {
        uuid org_id PK_FK
        jsonb allowed_models
        varchar default_extraction_model
        varchar default_chat_model
        boolean require_byo_key
        timestamptz updated_at
    }

    USER_SETTINGS {
        uuid user_id PK_FK
        varchar default_extraction_model
        varchar default_chat_model
        timestamptz updated_at
    }

    ORG_API_KEYS {
        uuid id PK
        uuid org_id FK
        varchar provider
        bytea encrypted_key
        varchar key_hint
        uuid created_by FK
        boolean is_active
        timestamptz created_at
        timestamptz rotated_at
    }

    CREDIT_BALANCES {
        uuid org_id PK_FK
        numeric balance
        timestamptz updated_at
    }

    CREDIT_LEDGER {
        uuid id PK
        uuid org_id FK
        uuid user_id FK
        numeric amount
        varchar credit_type
        varchar model_used
        uuid job_id FK
        varchar external_charge_id
        text description
        timestamptz created_at
    }

    CREDIT_RESERVATIONS {
        uuid id PK
        uuid org_id FK
        uuid user_id FK
        uuid job_id FK
        numeric amount
        timestamptz created_at
        timestamptz expires_at
    }

    AUDIT_LOG {
        uuid id PK
        uuid org_id FK
        uuid actor_id FK
        varchar action
        varchar target_type
        uuid target_id
        jsonb metadata
        inet ip_address
        timestamptz created_at
    }

    ORGANIZATIONS ||--o{ USERS : "employs"
    ORGANIZATIONS ||--o{ CATEGORIES : "owns"
    ORGANIZATIONS ||--o{ JOBS : "contains"
    ORGANIZATIONS ||--o{ CHAT_SESSIONS : "scopes"
    ORGANIZATIONS ||--|| ORG_MODEL_POLICIES : "configures"
    ORGANIZATIONS ||--o{ ORG_API_KEYS : "stores"
    ORGANIZATIONS ||--|| CREDIT_BALANCES : "has"
    ORGANIZATIONS ||--o{ CREDIT_LEDGER : "tracks"
    ORGANIZATIONS ||--o{ CREDIT_RESERVATIONS : "reserves"
    ORGANIZATIONS ||--o{ AUDIT_LOG : "logs"
    USERS ||--o{ JOBS : "creates"
    USERS ||--o{ CHAT_SESSIONS : "participates"
    USERS ||--o{ REFRESH_TOKENS : "authenticates"
    USERS ||--|| USER_SETTINGS : "configures"
    USERS ||--o{ CATEGORY_PERMISSIONS : "granted"
    CATEGORIES ||--o{ JOBS : "organizes"
    CATEGORIES ||--o{ CATEGORY_PERMISSIONS : "controls"
    JOBS ||--|| DOCUMENT_FILES : "stores"
    JOBS ||--o{ CHAT_SESSIONS : "discussed_in"
    CHAT_SESSIONS ||--o{ CHAT_MESSAGES : "contains"
```

---

## DDL

### New Tables

```sql
-- =============================================================
-- organizations
-- =============================================================
CREATE TABLE organizations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(63)  NOT NULL UNIQUE,
    tier            VARCHAR(20)  NOT NULL DEFAULT 'team'
                        CHECK (tier IN ('team', 'business', 'enterprise')),
    is_active       BOOLEAN      NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE organizations IS 'Tenant root. Single row for on-prem; multiple for SaaS.';
COMMENT ON COLUMN organizations.tier IS 'Pricing tier: team|business|enterprise. Controls feature gates + credit/BYO-key policy.';

-- =============================================================
-- categories
-- =============================================================
CREATE TABLE categories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID         NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    created_by      UUID         NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, name)
);

COMMENT ON TABLE categories IS 'Admin-created document categories (deal rooms / matters). D9: delete blocked if docs exist (app-enforced RESTRICT).';

-- =============================================================
-- category_permissions
-- =============================================================
CREATE TABLE category_permissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id     UUID         NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    subject_type    VARCHAR(10)  NOT NULL DEFAULT 'user'
                        CHECK (subject_type IN ('user', 'role')),
    subject_id      UUID         NOT NULL,
    grant_type      VARCHAR(10)  NOT NULL
                        CHECK (grant_type IN ('view', 'upload', 'manage')),
    granted_by      UUID         NOT NULL REFERENCES users(id),
    granted_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (category_id, subject_type, subject_id)
);

COMMENT ON TABLE category_permissions IS 'Per-category ACL. v1: subject_type=user only (D8). subject_type=role reserved for v2 — column present to avoid schema change.';
COMMENT ON COLUMN category_permissions.subject_id IS 'user.id when subject_type=user; role name hash/id when subject_type=role (v2).';
COMMENT ON COLUMN category_permissions.grant_type IS 'Hierarchical: view < upload < manage (D10: manage = membership only).';

-- =============================================================
-- model_catalog
-- =============================================================
CREATE TABLE model_catalog (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider                VARCHAR(20)   NOT NULL
                                CHECK (provider IN ('ollama', 'claude', 'openai')),
    model_id                VARCHAR(100)  NOT NULL UNIQUE,
    label                   VARCHAR(255)  NOT NULL,
    tier_availability       VARCHAR(20)   NOT NULL DEFAULT 'all'
                                CHECK (tier_availability IN ('all', 'team', 'business', 'enterprise')),
    credit_cost_extraction  NUMERIC(6,2)  NOT NULL DEFAULT 0,
    credit_cost_chat        NUMERIC(6,2)  NOT NULL DEFAULT 0,
    is_local                BOOLEAN       NOT NULL DEFAULT false,
    is_enabled              BOOLEAN       NOT NULL DEFAULT true,
    sort_order              INTEGER       NOT NULL DEFAULT 100,
    created_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE model_catalog IS 'Config-as-data (D14). Repriced/toggled via admin API; resolved per-request. Cached in Redis 60s.';
COMMENT ON COLUMN model_catalog.credit_cost_extraction IS 'Credits charged per extraction job. 0 = free/local.';
COMMENT ON COLUMN model_catalog.credit_cost_chat IS 'Credits charged per chat message. 0 = free/local.';
COMMENT ON COLUMN model_catalog.is_local IS 'true = available in AIRGAP_MODE. Local models have zero credit cost.';

-- Seed data (inserted by migration, not by application):
-- INSERT INTO model_catalog (provider, model_id, label, credit_cost_extraction, credit_cost_chat, is_local, sort_order) VALUES
--   ('ollama',  'qwen2.5:3b',           'Free -- Basic',            0,   0,     true,  10),
--   ('claude',  'claude-3-haiku',        'Good -- Fast',             1,   0.1,   false, 20),
--   ('claude',  'claude-3-5-sonnet',     'Best -- Balanced',         2,   0.1,   false, 30),
--   ('openai',  'gpt-4o',               'Best -- Alternative',      2,   0.1,   false, 40);

-- =============================================================
-- org_model_policies (1:1 with organizations)
-- =============================================================
CREATE TABLE org_model_policies (
    org_id                   UUID PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    allowed_models           JSONB        NOT NULL DEFAULT '[]'::jsonb,
    default_extraction_model VARCHAR(100),
    default_chat_model       VARCHAR(100),
    require_byo_key          BOOLEAN      NOT NULL DEFAULT false,
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE org_model_policies IS 'Per-org model governance. allowed_models=[] means all enabled models allowed. D14 precedence chain step 3.';
COMMENT ON COLUMN org_model_policies.allowed_models IS 'JSON array of model_id strings from model_catalog. Empty array = all enabled models.';

-- =============================================================
-- user_settings (1:1 with users)
-- =============================================================
CREATE TABLE user_settings (
    user_id                  UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    default_extraction_model VARCHAR(100),
    default_chat_model       VARCHAR(100),
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE user_settings IS 'Per-user model preferences. D14 precedence chain step 2.';

-- =============================================================
-- org_api_keys
-- =============================================================
CREATE TABLE org_api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID         NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    provider        VARCHAR(20)  NOT NULL
                        CHECK (provider IN ('claude', 'openai')),
    encrypted_key   BYTEA        NOT NULL,
    key_hint        VARCHAR(12)  NOT NULL,
    created_by      UUID         NOT NULL REFERENCES users(id),
    is_active       BOOLEAN      NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    rotated_at      TIMESTAMPTZ,
    UNIQUE (org_id, provider)
);

COMMENT ON TABLE org_api_keys IS 'BYO API keys (Business/Enterprise). AES-256-GCM encrypted; encryption key lives in KMS/Vault, NEVER in DB.';
COMMENT ON COLUMN org_api_keys.encrypted_key IS 'AES-256-GCM ciphertext (nonce || ciphertext || tag). Decryption key from SECRET_PROVIDER.';
COMMENT ON COLUMN org_api_keys.key_hint IS 'Last 4 chars of the plaintext key, for UI display (e.g., "...aBcD"). Never the full key.';

-- =============================================================
-- credit_balances (1:1 with organizations)
-- =============================================================
CREATE TABLE credit_balances (
    org_id          UUID PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    balance         NUMERIC(12,2) NOT NULL DEFAULT 0
                        CHECK (balance >= 0),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE credit_balances IS 'Materialized credit balance per org. Source of truth for available credits. Updated atomically via SELECT FOR UPDATE.';

-- =============================================================
-- credit_ledger (append-only)
-- =============================================================
CREATE TABLE credit_ledger (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID          NOT NULL REFERENCES organizations(id),
    user_id             UUID          REFERENCES users(id),
    amount              NUMERIC(10,2) NOT NULL,
    credit_type         VARCHAR(20)   NOT NULL
                            CHECK (credit_type IN ('purchase', 'spend', 'refund', 'adjustment', 'expiry')),
    model_used          VARCHAR(100),
    job_id              UUID          REFERENCES jobs(id) ON DELETE SET NULL,
    external_charge_id  VARCHAR(255),
    description         TEXT,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE credit_ledger IS 'Immutable financial log. amount is positive for purchase/refund, negative for spend. Balance integrity: SUM(amount) per org should equal credit_balances.balance (reconciliation query).';
COMMENT ON COLUMN credit_ledger.external_charge_id IS 'Stripe charge/payment_intent ID for purchases.';

-- =============================================================
-- credit_reservations (transient)
-- =============================================================
CREATE TABLE credit_reservations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID          NOT NULL REFERENCES organizations(id),
    user_id         UUID          NOT NULL REFERENCES users(id),
    job_id          UUID          NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    amount          NUMERIC(10,2) NOT NULL CHECK (amount > 0),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ   NOT NULL DEFAULT (NOW() + INTERVAL '30 minutes')
);

COMMENT ON TABLE credit_reservations IS 'Two-phase credit reservation (AQ-3 resolved). Created on job dispatch; deleted on completion (converted to ledger spend) or failure (balance restored). Stale reservations expired by background sweep.';

-- =============================================================
-- audit_log (append-only, partitioned by month recommended at scale)
-- =============================================================
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID         NOT NULL REFERENCES organizations(id),
    actor_id        UUID         REFERENCES users(id),
    action          VARCHAR(100) NOT NULL,
    target_type     VARCHAR(50),
    target_id       UUID,
    metadata        JSONB,
    ip_address      INET,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE audit_log IS 'Append-only enterprise audit trail (EF-11). Retention: 90d for Business tier, unlimited for Enterprise. Never UPDATE or DELETE rows — use a retention policy (pg_partman or scheduled DELETE).';
COMMENT ON COLUMN audit_log.action IS 'Verb: user.login, user.logout, job.create, job.delete, category.create, grant.add, grant.remove, api_key.store, api_key.rotate, model_policy.update, credits.purchase, etc.';
COMMENT ON COLUMN audit_log.metadata IS 'Structured context. NEVER include secrets, passwords, or API key values. Include: model selected, grant_type, category name, etc.';
```

### Modifications to Existing Tables

```sql
-- =============================================================
-- users: add org_id (nullable first, then NOT NULL after backfill)
-- =============================================================
-- Phase 1: add nullable column
ALTER TABLE users ADD COLUMN org_id UUID REFERENCES organizations(id);

-- Phase 2: backfill (after default org exists)
-- UPDATE users SET org_id = '<default-org-uuid>' WHERE org_id IS NULL;

-- Phase 3: enforce NOT NULL
-- ALTER TABLE users ALTER COLUMN org_id SET NOT NULL;

-- =============================================================
-- jobs: add org_id, category_id, extraction_model, llm_provider
-- =============================================================
-- Phase 1: add nullable columns
ALTER TABLE jobs ADD COLUMN org_id UUID REFERENCES organizations(id);
ALTER TABLE jobs ADD COLUMN category_id UUID REFERENCES categories(id) ON DELETE RESTRICT;
ALTER TABLE jobs ADD COLUMN extraction_model VARCHAR(100);
ALTER TABLE jobs ADD COLUMN llm_provider VARCHAR(20);

-- Phase 2: backfill org_id from user's org; category_id from "General" category
-- UPDATE jobs SET org_id = (SELECT org_id FROM users WHERE users.id = jobs.user_id);
-- UPDATE jobs SET category_id = (SELECT id FROM categories WHERE org_id = jobs.org_id AND name = 'General');

-- Phase 3: enforce NOT NULL on org_id and category_id
-- ALTER TABLE jobs ALTER COLUMN org_id SET NOT NULL;
-- ALTER TABLE jobs ALTER COLUMN category_id SET NOT NULL;

-- =============================================================
-- chat_sessions: add org_id
-- =============================================================
ALTER TABLE chat_sessions ADD COLUMN org_id UUID REFERENCES organizations(id);

-- Backfill from job's org_id:
-- UPDATE chat_sessions SET org_id = (SELECT org_id FROM jobs WHERE jobs.id = chat_sessions.job_id);

-- Enforce NOT NULL:
-- ALTER TABLE chat_sessions ALTER COLUMN org_id SET NOT NULL;
```

### UUID Type Migration (existing tables)

```sql
-- Execute in dependency order. Each ALTER locks the table briefly.
-- Safe at current data volumes (< 100k rows). Schedule during maintenance window.

-- 1. Parent tables first
ALTER TABLE users ALTER COLUMN id TYPE UUID USING id::uuid;
ALTER TABLE users ALTER COLUMN id SET DEFAULT gen_random_uuid();

-- 2. Update FK columns in child tables
ALTER TABLE jobs ALTER COLUMN id TYPE UUID USING id::uuid;
ALTER TABLE jobs ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
ALTER TABLE jobs ALTER COLUMN id SET DEFAULT gen_random_uuid();

ALTER TABLE document_files ALTER COLUMN job_id TYPE UUID USING job_id::uuid;

ALTER TABLE chat_sessions ALTER COLUMN id TYPE UUID USING id::uuid;
ALTER TABLE chat_sessions ALTER COLUMN job_id TYPE UUID USING job_id::uuid;
ALTER TABLE chat_sessions ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
ALTER TABLE chat_sessions ALTER COLUMN id SET DEFAULT gen_random_uuid();

ALTER TABLE chat_messages ALTER COLUMN id TYPE UUID USING id::uuid;
ALTER TABLE chat_messages ALTER COLUMN session_id TYPE UUID USING session_id::uuid;
ALTER TABLE chat_messages ALTER COLUMN id SET DEFAULT gen_random_uuid();

ALTER TABLE refresh_tokens ALTER COLUMN id TYPE UUID USING id::uuid;
ALTER TABLE refresh_tokens ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
ALTER TABLE refresh_tokens ALTER COLUMN id SET DEFAULT gen_random_uuid();
```

---

## Index Plan

| Index Name | Table | Columns / Expression | Type | Rationale (Query Pattern) |
|-----------|-------|---------------------|------|--------------------------|
| `idx_users_org_id` | users | `org_id` | btree | Tenant-scoped user listing; admin console user management |
| `idx_users_email` | users | `email` | btree (UNIQUE, already exists) | Login lookup |
| `idx_jobs_org_id` | jobs | `org_id` | btree | Tenant-scoped job listing (all docs in an org) |
| `idx_jobs_user_category` | jobs | `(user_id, category_id)` | btree | "My documents in category X" -- the hot path for document listing |
| `idx_jobs_org_category_status` | jobs | `(org_id, category_id, status)` | btree | Admin view: all docs in a category within org, filtered by status |
| `idx_jobs_org_created` | jobs | `(org_id, created_at DESC)` | btree | Recent documents across org (admin dashboard) |
| `idx_categories_org_id` | categories | `org_id` | btree | List categories for an org |
| `idx_catperm_category` | category_permissions | `category_id` | btree | List all grants for a category (admin view) |
| `idx_catperm_subject` | category_permissions | `(subject_type, subject_id)` | btree | "Which categories can user X access?" -- resolved on every job-scoped request |
| `idx_chat_sessions_org_job` | chat_sessions | `(org_id, job_id)` | btree | Tenant-scoped session lookup |
| `idx_credit_ledger_org_created` | credit_ledger | `(org_id, created_at DESC)` | btree | Credit history for an org (admin billing page) |
| `idx_credit_ledger_org_type` | credit_ledger | `(org_id, credit_type)` | btree | Filtered ledger view (purchases only, spends only) |
| `idx_credit_reservations_org` | credit_reservations | `org_id` | btree | Sum active reservations for balance check |
| `idx_credit_reservations_expires` | credit_reservations | `expires_at` | btree | Background sweep for stale reservations |
| `idx_audit_log_org_created` | audit_log | `(org_id, created_at DESC)` | btree | Audit log page -- always filtered by org, sorted by time |
| `idx_audit_log_org_action` | audit_log | `(org_id, action)` | btree | Filtered audit log (e.g., all login events) |
| `idx_audit_log_actor` | audit_log | `actor_id` | btree | "What did user X do?" investigation query |
| `idx_org_api_keys_org` | org_api_keys | `(org_id, provider)` | btree (UNIQUE) | Credential resolution: find BYO key for provider within org |
| `idx_model_catalog_enabled` | model_catalog | `(is_enabled, sort_order)` | btree, partial WHERE is_enabled | `GET /api/models` -- list enabled models sorted by display order |

---

## Referential Integrity and Cascade Policy

| Parent | Child | FK Column | ON DELETE | Rationale |
|--------|-------|-----------|-----------|-----------|
| organizations | users | org_id | NO ACTION (app prevents) | Never delete an org with users. Deactivate org instead. |
| organizations | categories | org_id | CASCADE | If an org IS deleted (e.g., data purge), its categories go too. |
| organizations | jobs | org_id | NO ACTION | Jobs are the core asset. Prevent org deletion if jobs exist. |
| organizations | org_model_policies | org_id | CASCADE | Config follows org lifecycle. |
| organizations | org_api_keys | org_id | CASCADE | Keys follow org lifecycle. |
| organizations | credit_balances | org_id | CASCADE | Balance follows org lifecycle. |
| organizations | credit_ledger | org_id | NO ACTION | Financial records are retained even if org is deactivated. |
| organizations | audit_log | org_id | NO ACTION | Audit records must survive org deactivation. |
| users | jobs | user_id | NO ACTION | Never delete jobs when deactivating a user. |
| users | chat_sessions | user_id | NO ACTION | Preserve chat history. |
| users | refresh_tokens | user_id | CASCADE | Tokens are disposable auth state. |
| users | user_settings | user_id | CASCADE | Settings follow user lifecycle. |
| categories | jobs | category_id | RESTRICT | **D9: Block category deletion if docs exist.** App returns 409. |
| categories | category_permissions | category_id | CASCADE | Grants are meaningless without the category. |
| jobs | document_files | job_id | CASCADE | File is part of the job. |
| jobs | chat_sessions | job_id | CASCADE | Sessions are scoped to the job. |
| chat_sessions | chat_messages | session_id | CASCADE | Messages are part of the session. |

---

## Credit System Design (AQ-3: Reserve-Then-Deduct)

### Tables

- **`credit_balances`**: Materialized balance per org. Single source of truth for "can this org afford X?" Atomically updated via `SELECT ... FOR UPDATE` + `UPDATE`.
- **`credit_reservations`**: Transient rows. Created when a premium job is dispatched. Deleted on completion or failure.
- **`credit_ledger`**: Append-only financial log. Every balance change is recorded here. `SUM(amount) WHERE org_id = X` should equal `credit_balances.balance` (reconciliation invariant).

### Flow

```
1. User submits job with premium model
   |
   v
2. Resolve model -> look up credit_cost_extraction from model_catalog
   |
   v
3. BEGIN TRANSACTION
   |  SELECT balance FROM credit_balances WHERE org_id = ? FOR UPDATE
   |  IF balance < cost -> ROLLBACK, return HTTP 402
   |  UPDATE credit_balances SET balance = balance - cost
   |  INSERT INTO credit_reservations (org_id, user_id, job_id, amount)
   |  COMMIT
   |
   v
4. Dispatch Celery task
   |
   +-- SUCCESS:
   |     BEGIN
   |     DELETE FROM credit_reservations WHERE job_id = ?
   |     INSERT INTO credit_ledger (org_id, user_id, amount, credit_type, model_used, job_id)
   |       VALUES (?, ?, -cost, 'spend', 'claude-3-5-sonnet', ?)
   |     COMMIT
   |
   +-- FAILURE / ABORT:
         BEGIN
         DELETE FROM credit_reservations WHERE job_id = ?
         UPDATE credit_balances SET balance = balance + cost WHERE org_id = ?
         INSERT INTO credit_ledger (org_id, user_id, amount, credit_type, model_used, job_id, description)
           VALUES (?, ?, 0, 'refund', 'claude-3-5-sonnet', ?, 'Job failed; credits restored')
         COMMIT
```

### Credit Purchase

```sql
BEGIN;
  INSERT INTO credit_ledger (org_id, user_id, amount, credit_type, external_charge_id, description)
    VALUES ($org, $user, 45.00, 'purchase', 'pi_abc123', '45-credit pack');
  UPDATE credit_balances SET balance = balance + 45.00, updated_at = NOW() WHERE org_id = $org;
COMMIT;
```

### Reconciliation Query (Periodic Health Check)

```sql
SELECT cb.org_id, cb.balance AS materialized,
       COALESCE(SUM(cl.amount), 0) AS computed,
       cb.balance - COALESCE(SUM(cl.amount), 0) AS drift
FROM credit_balances cb
LEFT JOIN credit_ledger cl ON cl.org_id = cb.org_id
GROUP BY cb.org_id, cb.balance
HAVING cb.balance != COALESCE(SUM(cl.amount), 0);
```

### Stale Reservation Sweep (Background Job, Every 15 Minutes)

```sql
-- Expire reservations older than 30 minutes (2x Celery soft_time_limit / 60)
WITH expired AS (
    DELETE FROM credit_reservations
    WHERE expires_at < NOW()
    RETURNING org_id, amount, job_id
)
UPDATE credit_balances cb
SET balance = cb.balance + expired.amount,
    updated_at = NOW()
FROM expired
WHERE cb.org_id = expired.org_id;
-- Also insert refund entries in credit_ledger for each expired reservation (application code).
```

---

## Encryption Note (org_api_keys)

The `encrypted_key` column stores AES-256-GCM ciphertext. The ciphertext format is: `nonce (12 bytes) || ciphertext (variable) || authentication tag (16 bytes)`.

The encryption key (Data Encryption Key, DEK) is NOT stored in Postgres. It is retrieved at runtime from the `SECRET_PROVIDER`:
- **Cloud (Vault / AWS Secrets Manager):** DEK stored as a named secret (e.g., `knowledgebook/byo-key-dek`). Rotated via KMS envelope encryption.
- **On-prem (env):** DEK in `BYO_KEY_ENCRYPTION_KEY` env var. Documented in the on-prem deployment guide.

Application code pattern:
```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
dek = secret_provider.get("byo-key-dek")  # 32 bytes
aesgcm = AESGCM(dek)
# Encrypt: nonce = os.urandom(12); ct = aesgcm.encrypt(nonce, plaintext_key, None)
# Store: nonce + ct (BYTEA)
# Decrypt: aesgcm.decrypt(stored[:12], stored[12:], None)
```

Audit: every `org_api_keys` INSERT/UPDATE/DELETE is logged in `audit_log` with `action='api_key.store'|'api_key.rotate'|'api_key.revoke'`. The `metadata` field includes `provider` and `key_hint` but NEVER the plaintext or ciphertext.

---

## Migration Plan (Alembic Revisions -- Ordered, Each Independently Deployable)

### Phase A: Foundation (Migration Infrastructure + Tenancy)

| # | Revision | Operation | Reversible? | Rollback | Deploy Step |
|---|----------|-----------|-------------|----------|-------------|
| 1 | `001_init_alembic` | Stamp existing schema; no DDL changes. `alembic stamp head` on existing DB. | N/A | N/A | Arch step 6 |
| 2 | `002_uuid_type_migration` | `ALTER COLUMN ... TYPE UUID USING id::uuid` on all 6 existing tables. Drop old defaults, set `gen_random_uuid()`. | Yes | `ALTER COLUMN ... TYPE VARCHAR(32) USING id::text` (hex re-encoding needed) | Arch step 6 |
| 3 | `003_create_organizations` | `CREATE TABLE organizations` | Yes | `DROP TABLE organizations` | Arch step 6 |
| 4 | `004_add_org_id_nullable` | `ALTER TABLE users/jobs/chat_sessions ADD COLUMN org_id UUID REFERENCES organizations(id)`. All nullable. Add indexes. | Yes | `ALTER TABLE ... DROP COLUMN org_id` | Arch step 6 |
| 5 | `005_seed_default_org_backfill` | Insert default org. `UPDATE users/jobs/chat_sessions SET org_id = <default>`. | Yes (set org_id back to NULL) | Manual: `UPDATE ... SET org_id = NULL` | Arch step 6 |
| 6 | `006_enforce_org_id_not_null` | `ALTER TABLE users/jobs/chat_sessions ALTER COLUMN org_id SET NOT NULL` | Yes | `ALTER COLUMN org_id DROP NOT NULL` | Arch step 6 |

### Phase B: Categories + ACL

| # | Revision | Operation | Reversible? | Rollback | Deploy Step |
|---|----------|-----------|-------------|----------|-------------|
| 7 | `007_create_categories` | `CREATE TABLE categories` + indexes | Yes | `DROP TABLE categories` | Arch step 8 |
| 8 | `008_create_category_permissions` | `CREATE TABLE category_permissions` + indexes | Yes | `DROP TABLE category_permissions` | Arch step 8 |
| 9 | `009_add_jobs_category_id` | `ALTER TABLE jobs ADD COLUMN category_id UUID REFERENCES categories(id) ON DELETE RESTRICT`. Nullable. | Yes | `DROP COLUMN category_id` | Arch step 8 |
| 10 | `010_seed_general_category_backfill` | Per org: insert "General" category. `UPDATE jobs SET category_id = <general>`. Grant existing non-admin users `upload` on "General". | Yes | Delete grants, set category_id = NULL, delete General categories | Arch step 8 |
| 11 | `011_enforce_category_id_not_null` | `ALTER TABLE jobs ALTER COLUMN category_id SET NOT NULL` | Yes | `DROP NOT NULL` | Arch step 8 |

### Phase C: Model Catalog + Config-as-Data

| # | Revision | Operation | Reversible? | Rollback | Deploy Step |
|---|----------|-----------|-------------|----------|-------------|
| 12 | `012_create_model_catalog` | `CREATE TABLE model_catalog` + seed rows (qwen, haiku, sonnet, gpt-4o) | Yes | `DROP TABLE model_catalog` | Arch step 7 |
| 13 | `013_create_org_model_policies` | `CREATE TABLE org_model_policies` | Yes | `DROP TABLE` | Arch step 7 |
| 14 | `014_create_user_settings` | `CREATE TABLE user_settings` | Yes | `DROP TABLE` | Arch step 7 |
| 15 | `015_create_org_api_keys` | `CREATE TABLE org_api_keys` | Yes | `DROP TABLE` | Arch step 7 |
| 16 | `016_add_jobs_model_columns` | `ALTER TABLE jobs ADD COLUMN extraction_model VARCHAR(100), ADD COLUMN llm_provider VARCHAR(20)` | Yes | `DROP COLUMN` x2 | Arch step 7 |

### Phase D: Credits

| # | Revision | Operation | Reversible? | Rollback | Deploy Step |
|---|----------|-----------|-------------|----------|-------------|
| 17 | `017_create_credit_balances` | `CREATE TABLE credit_balances`. Seed one row per existing org with `balance=0`. | Yes | `DROP TABLE` | Arch step 7 |
| 18 | `018_create_credit_ledger` | `CREATE TABLE credit_ledger` + indexes | Yes | `DROP TABLE` | Arch step 7 |
| 19 | `019_create_credit_reservations` | `CREATE TABLE credit_reservations` + indexes | Yes | `DROP TABLE` | Arch step 7 |

### Phase E: Audit

| # | Revision | Operation | Reversible? | Rollback | Deploy Step |
|---|----------|-----------|-------------|----------|-------------|
| 20 | `020_create_audit_log` | `CREATE TABLE audit_log` + indexes | Yes | `DROP TABLE` | Arch step 6-9 (can deploy early) |

---

## GDPR / PII Notes (EF-22)

| Table | PII Columns | Handling |
|-------|------------|---------|
| users | email, name, password_hash | Soft-delete (is_active=false). On GDPR erasure request: pseudonymize email/name, clear password_hash, log in audit_log. |
| jobs | title (may contain PII if user-named), graph (extracted content from user's documents) | On user erasure: delete jobs + cascade to document_files, chat_sessions, chat_messages. Or anonymize user_id if audit trail must survive. |
| document_files | data (the PDF itself -- may contain PII) | Deleted with job (CASCADE). This is the highest-sensitivity column. |
| chat_messages | content (user questions + assistant responses may reference PII from documents) | Deleted with session (CASCADE via job). |
| audit_log | actor_id, ip_address, metadata (may contain user identifiers) | Retain for compliance. On erasure: pseudonymize actor_id, null ip_address. Do NOT delete audit records -- they are the compliance proof. |
| org_api_keys | encrypted_key (not PII but sensitive) | Deleted with org (CASCADE). On key rotation: mark old row is_active=false. |
| credit_ledger | user_id | Financial records: retain for accounting. Pseudonymize user_id on erasure. |

**Data residency (EF-21):** The schema supports data residency by deploying separate Postgres instances per region. The `organizations.tier` and a future `organizations.region` column can drive routing. No schema change needed -- this is a deployment concern.

---

## Risks and Recommendations

### 1. BYTEA PDFs in Postgres (document_files.data)

**Risk:** Storing binary PDF data in Postgres BYTEA works fine at small scale but degrades as data grows:
- Table bloat: 10,000 PDFs at 5MB average = 50GB in Postgres. Vacuuming, backups, and restores become slow.
- pg_dump duration: proportional to total data size. 50GB+ adds significant backup time.
- Memory pressure: large BYTEA reads can spike backend memory.

**Recommendation for v1:** Keep BYTEA. The current user base is small, and moving to object storage adds infrastructure complexity (S3/MinIO + pre-signed URLs). The schema change is minimal when the time comes:
1. Add `document_files.storage_url TEXT` (nullable).
2. Migrate existing data to S3/MinIO, populate `storage_url`.
3. Application code: if `storage_url` is set, redirect to pre-signed URL; else serve from `data`.
4. Eventually drop the `data` column.

**For on-prem / air-gapped:** BYTEA is actually simpler (no MinIO dependency). Consider keeping BYTEA as the on-prem default and using object storage only for SaaS.

### 2. Audit Log Growth

**Risk:** Append-only audit_log grows unbounded. At high volume (1000 events/day/org, 100 orgs), that is 36.5M rows/year.

**Recommendation:** Implement table partitioning by month (`audit_log_2026_07`, etc.) using Postgres declarative partitioning or `pg_partman`. Retention policy: drop partitions older than 90 days for Business tier, retain all for Enterprise. Partitioning also speeds up time-range queries.

### 3. Credit Balance Race Conditions

**Risk:** Concurrent premium job submissions from the same org could race on `credit_balances`.

**Mitigation:** The `SELECT ... FOR UPDATE` in the reservation flow serializes concurrent updates to the same org's balance row. This is correct but creates a brief serialization point. At KnowledgeBook's expected concurrency (tens of concurrent users per org, not thousands), this is not a bottleneck. If it becomes one, the ledger can be sharded by user within org, but that is premature optimization.

### 4. JSON Columns (jobs.events, jobs.graph)

**Observation:** `events` and `graph` are stored as `JSON` (not `JSONB`). If these are ever queried with JSON operators (e.g., filtering jobs by graph stats), they should be migrated to `JSONB`. For now, they are only read as opaque blobs, so `JSON` is acceptable. The `citations` column on `chat_messages` should also be `JSONB` if filtered/indexed.

### 5. Single User per Org (v1)

**Decision:** A user belongs to exactly one organization (via `users.org_id`). This is the simplest model and sufficient for v1. If multi-org membership is needed later (e.g., a consultant working across client orgs), introduce a `user_org_memberships` junction table and move `org_id` off `users`. The current schema does NOT prevent this future migration.

---

## Tenant Scoping Support

The architecture (ADR-E4) enforces tenant scoping via a FastAPI dependency, not PostgreSQL RLS. The schema supports this by ensuring every tenant-owned table has an `org_id` column:

```
organizations (root)
  +-- users.org_id
  +-- jobs.org_id
  +-- chat_sessions.org_id
  +-- categories.org_id
  +-- credit_balances.org_id
  +-- credit_ledger.org_id
  +-- credit_reservations.org_id
  +-- org_model_policies.org_id
  +-- org_api_keys.org_id
  +-- audit_log.org_id
```

The `tenant_filter(query, model_class, tenant)` function appends `.where(model_class.org_id == tenant.org_id)` to every query. This is simple, explicit, and testable.

**On-prem / single-tenant (AQ-4):** The default org is auto-created. All users and data belong to it. The `tenant_filter` still runs but always matches the single org. Zero code branching.

---

## Audit Log Actions (Reference)

| Action | Target Type | When |
|--------|------------|------|
| `user.login` | user | Successful login |
| `user.login_failed` | user | Failed login attempt |
| `user.logout` | user | Explicit logout |
| `user.create` | user | Admin creates user |
| `user.update` | user | Role/name/active change |
| `user.deactivate` | user | Admin deactivates user |
| `job.create` | job | Document uploaded |
| `job.delete` | job | Document deleted |
| `category.create` | category | Admin creates category |
| `category.update` | category | Admin renames/updates |
| `category.delete` | category | Admin deletes (empty) category |
| `grant.add` | category_permission | Grant issued |
| `grant.remove` | category_permission | Grant revoked |
| `api_key.store` | org_api_key | BYO key stored |
| `api_key.rotate` | org_api_key | BYO key rotated |
| `api_key.revoke` | org_api_key | BYO key revoked |
| `model_policy.update` | org_model_policy | Admin changes model policy |
| `credits.purchase` | credit_ledger | Credit pack purchased |
| `org.create` | organization | Org created |
| `org.update` | organization | Org settings changed |
