"""Per-request model resolution — config-as-data, no restart (EF-28 / D14).

The catalog + org policy + user settings live in Postgres and are read per
request; the catalog is Redis-cached (60s TTL) and invalidated fleet-wide on
admin edits. Precedence: request → user default → org policy default →
system default (free local). This is what lets a user pick a model that takes
effect immediately, with no container restart."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ModelCatalog, OrgModelPolicy, UserSettings
from app.redis_client import get_redis

_CATALOG_KEY = "cfg:model_catalog"
_TTL = 60


def get_catalog() -> list[dict]:
    """Enabled models (Redis-cached read of `model_catalog`)."""
    r = get_redis()
    try:
        cached = r.get(_CATALOG_KEY)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    from app.db import session_scope
    with session_scope() as db:
        rows = db.scalars(
            select(ModelCatalog).where(ModelCatalog.is_enabled.is_(True))
            .order_by(ModelCatalog.sort_order)
        ).all()
        data = [{"model_id": m.model_id, "provider": m.provider, "label": m.label,
                 "is_local": m.is_local,
                 "credit_cost_extraction": float(m.credit_cost_extraction or 0),
                 "credit_cost_chat": float(m.credit_cost_chat or 0)} for m in rows]
    try:
        r.set(_CATALOG_KEY, json.dumps(data), ex=_TTL)
    except Exception:
        pass
    return data


def invalidate_catalog() -> None:
    try:
        get_redis().delete(_CATALOG_KEY)
    except Exception:
        pass


def system_default() -> str:
    return get_settings().ollama_model or "qwen2.5:3b"


def provider_for(model_id: str) -> str:
    for m in get_catalog():
        if m["model_id"] == model_id:
            return m["provider"]
    return "ollama"


def resolve(db: Session, user, requested: str | None, kind: str) -> tuple[str, str]:
    """Return (provider, model_id) for `kind` in {"extraction","chat"} using the
    D14 precedence chain, constrained to the org's allowed models."""
    catalog = get_catalog()
    by_id = {m["model_id"]: m for m in catalog}
    allowed = set(by_id)

    policy = db.get(OrgModelPolicy, user.org_id) if getattr(user, "org_id", None) else None
    if policy and policy.allowed_models:
        allowed &= set(policy.allowed_models)

    us = db.get(UserSettings, user.id)
    user_default = (us.default_extraction_model if kind == "extraction" else us.default_chat_model) if us else None
    org_default = (policy.default_extraction_model if kind == "extraction" else policy.default_chat_model) if policy else None
    sysd = system_default()

    for candidate in (requested, user_default, org_default, sysd):
        if candidate and candidate in allowed and candidate in by_id:
            return by_id[candidate]["provider"], candidate

    # Fallback: system default if allowed, else any allowed model.
    if sysd in by_id and (not allowed or sysd in allowed):
        return by_id[sysd]["provider"], sysd
    for mid in allowed:
        return by_id[mid]["provider"], mid
    return "ollama", sysd
