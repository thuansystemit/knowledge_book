"""ORM models: User, Job, RefreshToken (Sprint 1a).

Roles: admin | analyst | viewer (viewer reserved for Sprint 2 share links).
Jobs are owned by a user; the extracted graph + event history are persisted as
JSON so results survive a restart and can be re-opened from the library."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, Numeric,
    String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

ROLES = ("admin", "analyst", "viewer")


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    """Tenant (EF-12). SaaS = many orgs; on-prem = a single auto-created org."""
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), default="Default")
    slug: Mapped[str] = mapped_column(String(63), unique=True, index=True, default="default")
    tier: Mapped[str] = mapped_column(String(20), default="enterprise")  # team|business|enterprise
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120), default="")
    role: Mapped[str] = mapped_column(String(16), default="analyst")
    # Consumer subscription plan (monetization-pricing.md; PAY-01/02/03).
    # Orthogonal to `role` (RBAC): governs monthly upload quota, not permissions.
    plan: Mapped[str] = mapped_column(String(16), default="free")  # free|pro|scholar
    # Stripe billing linkage (PAY-04). Set by checkout + kept in sync by webhooks.
    plan_status: Mapped[str] = mapped_column(String(20), default="none")  # none|active|past_due|canceled
    # Non-expiring extra-document credits (PAY-05); consumed after the monthly quota.
    credits: Mapped[int] = mapped_column(Integer, default=0)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def public(self) -> dict:
        return {
            "id": self.id, "email": self.email, "name": self.name,
            "role": self.role, "plan": self.plan, "plan_status": self.plan_status,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|done|error
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    events: Mapped[list] = mapped_column(JSON, default=list)
    graph: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Estimated per-document LLM cost in USD (EXT-02) — for the ops dashboard.
    cost_usd: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    # End-to-end pipeline wall-clock (ACT-05) — for the latency dashboard.
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Mean OCR word confidence 0-100 (ACT-06); null when the doc needed no OCR.
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    user: Mapped[User] = relationship()

    def summary(self) -> dict:
        stats = (self.graph or {}).get("stats", {}) if self.graph else {}
        return {
            "job_id": self.id, "title": self.title, "status": self.status,
            "node_count": stats.get("node_count"), "edge_count": stats.get("edge_count"),
            "cost_usd": float(self.cost_usd) if self.cost_usd is not None else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def detail(self) -> dict:
        return {
            "job_id": self.id, "title": self.title, "status": self.status,
            "error": self.error, "events": self.events or [], "graph": self.graph,
            "user_id": self.user_id,
        }


class DocumentFile(Base):
    """The original uploaded file for a job, so the user can view the source and
    compare it with chat answers. One row per job (keyed by job_id)."""
    __tablename__ = "document_files"

    job_id: Mapped[str] = mapped_column(String(32), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), default="document.pdf")
    mime: Mapped[str] = mapped_column(String(100), default="application/pdf")
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ActivationEvent(Base):
    """Activation instrumentation for the GTM launch gates (ACT-01/02/03).

    One row per (user, job, kind); kinds are `view` (Concept Map first viewed),
    `rating` (thumbs up/down on the concept list), and `qa` (asked ≥1 Q&A on the
    doc). Idempotent per kind so the activation rate is a clean count of pairs.
    A doc is "activated" when a `view` pair also has a `rating` or a `qa`."""
    __tablename__ = "activation_events"
    __table_args__ = (UniqueConstraint("user_id", "job_id", "kind", name="uq_activation_user_job_kind"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    job_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(16))          # view | rating | qa
    value: Mapped[str | None] = mapped_column(String(16), nullable=True)  # rating: up|down
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Category(Base):
    """Admin-created document category / collection (EF-27). A "category" is the
    deal-room / matter folder in the legal wedge. Access to it (and its docs) is
    governed by CategoryPermission — default-deny."""
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_category_org_name"),)


class CategoryPermission(Base):
    """Per-category grant (EF-27, D8: subject_type='user' in v1; 'role' reserved
    for v2). Hierarchy: view < upload < manage (manage = membership only, D10)."""
    __tablename__ = "category_permissions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    category_id: Mapped[str] = mapped_column(String(32), ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    subject_type: Mapped[str] = mapped_column(String(10), default="user")  # user|role
    subject_id: Mapped[str] = mapped_column(String(32), index=True)
    grant_type: Mapped[str] = mapped_column(String(10))  # view|upload|manage
    granted_by: Mapped[str] = mapped_column(String(32))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (UniqueConstraint("category_id", "subject_type", "subject_id",
                                       name="uq_catperm_cat_subject"),)


class ModelCatalog(Base):
    """Available LLM models (EF-28 / D14 config-as-data). Read per request +
    Redis-cached; admin-editable without a restart."""
    __tablename__ = "model_catalog"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(20))  # ollama|claude|openai
    model_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(255))
    is_local: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(default=100)
    credit_cost_extraction: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    credit_cost_chat: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class OrgModelPolicy(Base):
    """Per-org governance of model choice (EF-28)."""
    __tablename__ = "org_model_policies"

    org_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    allowed_models: Mapped[list] = mapped_column(JSON, default=list)  # model_ids; empty => all enabled
    default_extraction_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_chat_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    require_byo_key: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class UserSettings(Base):
    """Per-user default model preferences (D14 precedence chain)."""
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    default_extraction_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_chat_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class ChatSession(Base):
    """One chat thread per (job, user). Lazily created on the first question."""
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    job_id: Mapped[str] = mapped_column(String(32), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (UniqueConstraint("job_id", "user_id", name="uq_chat_session_job_user"),)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(32), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # 'user' | 'assistant'
    content: Mapped[str] = mapped_column(Text, default="")
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Answer latency in ms (ACT-07) — set on assistant messages only.
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def public(self) -> dict:
        return {
            "id": self.id, "role": self.role, "content": self.content,
            "citations": self.citations, "model": self.model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class InterviewPrepPlan(Base):
    """One interview-prep plan per (user, track). Holds the generated study plan,
    checklist, and metadata; individual questions live in InterviewPrepQuestion."""
    __tablename__ = "interview_prep_plans"
    # Version history (interview-prep-versioning): each regeneration is a new row.
    # UNIQUE(user_id, track, version) numbers versions 1..N; the partial unique
    # index guarantees at most one `is_current` row per (user, track).
    __table_args__ = (
        UniqueConstraint("user_id", "track", "version", name="uq_prep_user_track_ver"),
        Index("uix_prep_current", "user_id", "track", unique=True,
              postgresql_where=text("is_current = true")),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    org_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    track: Mapped[str] = mapped_column(String(32))  # junior_backend | senior_backend | system_design
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|generating|done|error
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    plan_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class InterviewPrepQuestion(Base):
    """Individual question generated by an interview-prep plan."""
    __tablename__ = "interview_prep_questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    plan_id: Mapped[str] = mapped_column(String(32), ForeignKey("interview_prep_plans.id", ondelete="CASCADE"), index=True)
    track: Mapped[str] = mapped_column(String(32))
    topic: Mapped[str] = mapped_column(String(255))
    question: Mapped[str] = mapped_column(Text)
    model_answer: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(8))  # easy|medium|hard
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RefreshToken(Base):
    """One row per issued refresh token (rotation + revocation). The cookie holds
    a JWT carrying this row's id (jti); refresh rotates (revoke old, issue new),
    logout revokes."""
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
