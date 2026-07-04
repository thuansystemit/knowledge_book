"""Idempotent schema/data migrations run at startup (enterprise backbone — Step 6).

For now these are hand-written, idempotent Postgres statements (safe to run on
every boot). They evolve the LIVE database that was originally created by
`create_all`, which cannot ALTER existing tables. This is the low-risk path to
introduce `org_id`; formalizing to Alembic (AQ-2) — and the UUID-PK migration —
is a planned follow-up.

`run_tenancy()`:
  1. adds the `org_id` column (+ index) to pre-existing tenant tables (idempotent),
  2. auto-creates a single **Default** organization if none exists (AQ-4 — makes
     on-prem/single-tenant "just work" with the same schema as SaaS),
  3. backfills every existing row's `org_id` to that org.
Returns the default org id.
"""
from __future__ import annotations

from sqlalchemy import select, text, update

from app.config import get_settings
from app.db import engine, session_scope
from app.models import Category, CategoryPermission, Job, ModelCatalog, Organization, User
from app.observability import audit

_TENANT_TABLES = ("users", "jobs", "chat_sessions")


def run_tenancy() -> str:
    # 1. Ensure the org_id column + index exist on pre-existing tables.
    with engine.begin() as conn:
        for tbl in _TENANT_TABLES:
            conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS org_id VARCHAR(32)"))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{tbl}_org_id ON {tbl} (org_id)"))

    # 2. Auto-create the default org if the tenant space is empty.
    with session_scope() as db:
        org = db.scalar(select(Organization).limit(1))
        if org is None:
            org = Organization(name="Default", slug="default", tier="enterprise")
            db.add(org)
            db.flush()
            audit("DEFAULT_ORG_CREATED", org=org.id)
        org_id = org.id

    # 3. Backfill existing rows to the default org.
    with engine.begin() as conn:
        for tbl in _TENANT_TABLES:
            conn.execute(text(f"UPDATE {tbl} SET org_id = :oid WHERE org_id IS NULL"),
                         {"oid": org_id})
    return org_id


def run_models() -> None:
    """Add model columns to `jobs` (idempotent) and seed the model catalog
    (EF-28 / D14). Seeds are added only if missing — admin edits are preserved."""
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS extraction_model VARCHAR(100)"))
        conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS llm_provider VARCHAR(20)"))
        conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(8,4)"))  # EXT-02
        conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS duration_ms INTEGER"))     # ACT-05
        conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS latency_ms INTEGER"))  # ACT-07

    cfg = get_settings()
    seeds = [
        {"provider": "ollama", "model_id": cfg.ollama_model or "qwen2.5:3b",
         "label": "Free — Basic (local)", "is_local": True, "sort_order": 10, "ce": 0, "cc": 0},
        {"provider": "claude", "model_id": "claude-sonnet-4-6",
         "label": "Best — Balanced (Claude)", "is_local": False, "sort_order": 20, "ce": 2, "cc": 0.1},
        {"provider": "claude", "model_id": "claude-opus-4-8",
         "label": "Max — Claude Opus", "is_local": False, "sort_order": 30, "ce": 3, "cc": 0.2},
        {"provider": "openai", "model_id": "gpt-4o",
         "label": "Best — Alternative (GPT-4o)", "is_local": False, "sort_order": 40, "ce": 2, "cc": 0.1},
    ]
    with session_scope() as db:
        for s in seeds:
            if db.scalar(select(ModelCatalog).where(ModelCatalog.model_id == s["model_id"])):
                continue
            db.add(ModelCatalog(
                provider=s["provider"], model_id=s["model_id"], label=s["label"],
                is_local=s["is_local"], sort_order=s["sort_order"],
                credit_cost_extraction=s["ce"], credit_cost_chat=s["cc"]))


def run_plans() -> None:
    """Add `users.plan` (idempotent). Backfills existing rows to 'free'; admins
    are quota-exempt at enforcement time regardless of plan. Consumer plans
    (free|pro|scholar) are orthogonal to RBAC role (PAY-01/02/03)."""
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan VARCHAR(16) DEFAULT 'free'"))
        conn.execute(text("UPDATE users SET plan = 'free' WHERE plan IS NULL"))
        # Stripe billing linkage (PAY-04).
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_status VARCHAR(20) DEFAULT 'none'"))
        conn.execute(text("UPDATE users SET plan_status = 'none' WHERE plan_status IS NULL"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(64)"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(64)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_stripe_customer_id ON users (stripe_customer_id)"))


def run_categories() -> None:
    """Add `jobs.category_id` (idempotent) and, per org, ensure a 'General'
    category, backfill existing jobs into it, and grant existing non-admin users
    `upload` on it (EF-27 backfill; zero behaviour change on migration day)."""
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS category_id VARCHAR(32)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_category_id ON jobs (category_id)"))

    with session_scope() as db:
        for org in db.scalars(select(Organization)).all():
            gen = db.scalar(select(Category).where(Category.org_id == org.id, Category.name == "General"))
            if gen is None:
                gen = Category(org_id=org.id, name="General",
                               description="Default category", created_by="system")
                db.add(gen)
                db.flush()
            db.execute(update(Job).where(Job.org_id == org.id, Job.category_id.is_(None))
                       .values(category_id=gen.id))
            for u in db.scalars(select(User).where(User.org_id == org.id)).all():
                if u.role == "admin":
                    continue  # admins are super-users; no explicit grant needed
                has = db.scalar(select(CategoryPermission).where(
                    CategoryPermission.category_id == gen.id,
                    CategoryPermission.subject_type == "user",
                    CategoryPermission.subject_id == u.id))
                if not has:
                    db.add(CategoryPermission(category_id=gen.id, subject_type="user",
                                              subject_id=u.id, grant_type="upload",
                                              granted_by="system"))
