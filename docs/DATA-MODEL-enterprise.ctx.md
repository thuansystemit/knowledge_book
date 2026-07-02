# CTX: Enterprise Data Model -- KnowledgeBook

> **AI digest of `DATA-MODEL-enterprise.md`. Self-contained -- read this alone; pull the full `.md` only for DDL detail, index rationale, credit flow, or cascade table.**
> Date: 2026-07-02. Status: FINALIZED. Convention: paired `*.ctx.md`; keep in sync; work inline.

---

## Resolved Decisions

| ID | Decision | Detail |
|----|---------|--------|
| AQ-2 | **Alembic** (not `create_all`) | `create_all` cannot ALTER existing columns, backfill data, or add constraints on populated tables. Alembic is SQLAlchemy-native, zero ORM changes. Stamp existing DB, then forward-only migrations. |
| AQ-3 | **Reserve-then-deduct** (two-phase credits) | Prevents TOCTOU double-spend. `credit_reservations` row inserted atomically with `SELECT FOR UPDATE` on `credit_balances`. On job success: delete reservation, insert `credit_ledger` spend. On failure: delete reservation, restore balance. Stale reservation sweep every 15 min (expires_at). |
| AQ-4 | **Auto-create default org** on first boot | Migration checks `COUNT(*) FROM organizations`; if 0, inserts `(name='Default', slug='default', tier='enterprise')`. All users/jobs backfilled to this org. Same schema for SaaS multi-tenant and on-prem single-tenant. |

## ID Strategy

**Migrate `String(32)` hex to native `UUID` type** via `ALTER COLUMN ... TYPE UUID USING id::uuid`. Safe at current volumes. Dependency order: users -> jobs -> document_files/chat_sessions/refresh_tokens -> chat_messages.

---

## Table Signatures (New)

```
organizations(id UUID PK, name VARCHAR(255) NN, slug VARCHAR(63) NN UK, tier VARCHAR(20) NN CHECK team|business|enterprise, is_active BOOL NN, created_at TIMESTAMPTZ NN, updated_at TIMESTAMPTZ NN)

categories(id UUID PK, org_id UUID NN FK->organizations, name VARCHAR(255) NN, description TEXT, created_by UUID NN FK->users, created_at, updated_at, UNIQUE(org_id,name))

category_permissions(id UUID PK, category_id UUID NN FK->categories CASCADE, subject_type VARCHAR(10) NN CHECK user|role, subject_id UUID NN, grant_type VARCHAR(10) NN CHECK view|upload|manage, granted_by UUID NN FK->users, granted_at TIMESTAMPTZ NN, UNIQUE(category_id,subject_type,subject_id))

model_catalog(id UUID PK, provider VARCHAR(20) NN CHECK ollama|claude|openai, model_id VARCHAR(100) NN UK, label VARCHAR(255) NN, tier_availability VARCHAR(20) NN, credit_cost_extraction NUMERIC(6,2) NN, credit_cost_chat NUMERIC(6,2) NN, is_local BOOL NN, is_enabled BOOL NN, sort_order INT NN, created_at, updated_at)

org_model_policies(org_id UUID PK FK->organizations CASCADE, allowed_models JSONB NN, default_extraction_model VARCHAR(100), default_chat_model VARCHAR(100), require_byo_key BOOL NN, updated_at)

user_settings(user_id UUID PK FK->users CASCADE, default_extraction_model VARCHAR(100), default_chat_model VARCHAR(100), updated_at)

org_api_keys(id UUID PK, org_id UUID NN FK->organizations CASCADE, provider VARCHAR(20) NN CHECK claude|openai, encrypted_key BYTEA NN, key_hint VARCHAR(12) NN, created_by UUID NN FK->users, is_active BOOL NN, created_at, rotated_at, UNIQUE(org_id,provider))

credit_balances(org_id UUID PK FK->organizations CASCADE, balance NUMERIC(12,2) NN CHECK>=0, updated_at)

credit_ledger(id UUID PK, org_id UUID NN FK->organizations, user_id UUID FK->users, amount NUMERIC(10,2) NN, credit_type VARCHAR(20) NN CHECK purchase|spend|refund|adjustment|expiry, model_used VARCHAR(100), job_id UUID FK->jobs SET NULL, external_charge_id VARCHAR(255), description TEXT, created_at TIMESTAMPTZ NN)

credit_reservations(id UUID PK, org_id UUID NN FK->organizations, user_id UUID NN FK->users, job_id UUID NN FK->jobs CASCADE, amount NUMERIC(10,2) NN CHECK>0, created_at, expires_at DEFAULT NOW()+30min)

audit_log(id UUID PK, org_id UUID NN FK->organizations, actor_id UUID FK->users, action VARCHAR(100) NN, target_type VARCHAR(50), target_id UUID, metadata JSONB, ip_address INET, created_at TIMESTAMPTZ NN)
```

## Modified Tables

```
users       + org_id UUID NN FK->organizations (nullable first, backfill, enforce)
jobs        + org_id UUID NN FK->organizations
            + category_id UUID NN FK->categories ON DELETE RESTRICT (nullable first, backfill, enforce)
            + extraction_model VARCHAR(100)
            + llm_provider VARCHAR(20)
chat_sessions + org_id UUID NN FK->organizations (nullable first, backfill, enforce)
```

All existing PK/FK columns: `String(32)` -> `UUID` type migration.

---

## Key Relationships

- `organizations` 1->N `users`, `jobs`, `categories`, `audit_log`, `credit_ledger`
- `organizations` 1->1 `org_model_policies`, `credit_balances`
- `organizations` 1->N `org_api_keys` (max 1 per provider via UNIQUE)
- `categories` 1->N `jobs` (ON DELETE RESTRICT -- D9)
- `categories` 1->N `category_permissions` (CASCADE)
- `category_permissions`: v1 subject_type='user' only (D8); 'role' column present for v2
- `users` 1->1 `user_settings`
- D14 precedence: request model -> user_settings -> org_model_policies -> free-local

## Credit Flow (AQ-3)

1. Job dispatch: `SELECT balance FOR UPDATE` on `credit_balances` -> check >= cost -> decrement -> insert `credit_reservations`
2. Job success: delete reservation -> insert `credit_ledger` (amount=-cost, type='spend')
3. Job failure: delete reservation -> restore balance -> insert `credit_ledger` (amount=0, type='refund')
4. Stale sweep: delete reservations where `expires_at < NOW()` -> restore balances

## Backfill Strategy (Tenancy + Categories)

1. Create default org
2. `UPDATE users SET org_id = <default>` (all existing users)
3. `UPDATE jobs SET org_id = <user's org>` (derived from user)
4. `UPDATE chat_sessions SET org_id = <job's org>` (derived from job)
5. Enforce NOT NULL on org_id columns
6. Create "General" category per org
7. `UPDATE jobs SET category_id = <general>` (all existing jobs)
8. Grant existing non-admin users `upload` on "General"
9. Enforce NOT NULL on category_id

## Migration Order (20 Alembic revisions)

Phase A (tenancy): 001_init -> 002_uuid_migration -> 003_create_orgs -> 004_add_org_id_nullable -> 005_backfill_default_org -> 006_enforce_not_null
Phase B (categories): 007_create_categories -> 008_create_category_permissions -> 009_add_category_id -> 010_backfill_general -> 011_enforce_category_not_null
Phase C (models): 012_model_catalog -> 013_org_model_policies -> 014_user_settings -> 015_org_api_keys -> 016_jobs_model_columns
Phase D (credits): 017_credit_balances -> 018_credit_ledger -> 019_credit_reservations
Phase E (audit): 020_audit_log

## Key Indexes

- `idx_jobs_org_category_status (org_id, category_id, status)` -- tenant+category filtered doc list
- `idx_jobs_user_category (user_id, category_id)` -- user's docs in category
- `idx_catperm_subject (subject_type, subject_id)` -- ACL resolution per request
- `idx_credit_ledger_org_created (org_id, created_at DESC)` -- billing history
- `idx_audit_log_org_created (org_id, created_at DESC)` -- audit page
- `idx_credit_reservations_expires (expires_at)` -- stale sweep

## Encryption

BYO keys: AES-256-GCM in `org_api_keys.encrypted_key` (BYTEA). Encryption key from `SECRET_PROVIDER` (Vault/KMS/env), NEVER in DB. `key_hint` = last 4 chars only.

## Risks Flagged

1. BYTEA PDFs in Postgres: acceptable for v1 (small volume); plan migration path to S3/MinIO for SaaS scale
2. Audit log growth: partition by month at scale; retention policy per tier
3. JSON columns (events, graph): migrate to JSONB if ever queried with JSON operators
4. Single-org-per-user: sufficient for v1; junction table migration path if multi-org needed

---

`pull_hint: "Full DDL, credit flow diagram, cascade policy table, index rationale, GDPR/PII table, UUID migration SQL, audit action reference -> DATA-MODEL-enterprise.md"`
