---
doc: 01-product-spec
agent: product-manager
phase: 1
status: complete
human_doc: 01-product-spec.md
next: [requirements-analyst]
feature: auth-ui-uplift
provides:
  stories:
    US-001: Login and logout — JWT access token + HttpOnly refresh cookie + idle timeout
    US-002: Protected app shell with role-gated nav (Admin/Analyst/Viewer)
    US-003: Per-user document library with persistent job history (DB, survive restart)
    US-004: Upload + run extraction restyled, SSE stream-token auth
    US-005: Document detail — 4-tab view (Brief / Graph / Chapter Guide / Q&A)
    US-006: Admin user management (create/role/deactivate)
    US-007: Admin LLM config (provider/model/API key, masked)
  metric: "SSE stream inaccessible without auth; login→extraction < 2 min; documents survive restart"
mvp: "Sprint 1: login/logout + Admin+Analyst roles + protected shell + upload page + document library + job persistence"
out_of_scope: [self-registration, social-auth, audit-log-ui, i18n, 2FA, idle-timeout-sprint1]
users: [Admin, Analyst, Viewer]
top_rice: "US-001 Login and logout (score 75)"
constraints:
  - "Admin-only user creation in MVP (no open registration)"
  - "SSE auth via short-lived stream token, NOT Authorization header (EventSource limitation)"
  - "Access token in zustand memory only — never localStorage"
  - "LLM API keys never returned in plaintext from any endpoint"
  - "First admin seeded via ADMIN_EMAIL + ADMIN_PASSWORD env vars"
open:
  - "SQLite vs Postgres for initial DB (blocks Sprint 1 backend)"
  - "Admin-only creation vs invite-link flow (blocks Sprint 1 scope)"
pull_hint: "Full RBAC matrix, all 7 ACs, MoSCoW table, SSE auth design, backend migration plan → 01-product-spec.md"
---
