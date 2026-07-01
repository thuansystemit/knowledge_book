# Product Spec — KnowledgeBook Auth + UI Uplift
**Date:** 2026-06-29  **Author:** @product-manager  **Status:** DRAFT
**Feature ID:** auth-ui-uplift

---

## Problem Statement

KnowledgeBook currently has no authentication, no user identity, and a single-page UI that
handles exactly one job at a time with no history. All jobs are stored globally in-memory
(lost on restart). The UI is visually bare with no layout chrome, navigation, or role
differentiation. To graduate from a personal dev tool to a shared team product — which is
the explicit goal ("add RBAC and login/logout, match toeic_app standard") — the entire auth
layer, job persistence, and UI shell must be built from scratch.

The benchmark is the sibling `toeic_app` frontend: react-router, AppLayout with nav +
header/user menu, ProtectedRoute, login/register/forgot/reset pages, role-based navigation,
react-query data fetching, tailwind styling, and the JWT access-token + HttpOnly refresh-
cookie pattern.

---

## Target Users

| Persona | Key need | Estimated reach (users/quarter) |
|---------|----------|---------------------------------|
| Researcher / Analyst | Upload PDFs, run extractions, view and revisit graphs | 10–50 (initial team) |
| Busy Practitioner (PM, manager) | View and share graphs without uploading | 20–100 (consumers) |
| Admin | Manage users, configure LLM provider/model/API keys | 1–3 |

---

## 1. Roles & Personas

### Recommended Role Model: 3 roles

**Admin**
The system operator. Responsible for configuring LLM providers (switching between Ollama,
Claude, OpenAI, setting API keys), managing user accounts, and viewing audit trails.
There will typically be 1–3 Admins in a team deployment.

**Analyst** (default role on creation)
The primary user. Can upload PDFs, run extractions, view their own documents, delete their
own documents, and share read-only links to their graphs. This maps to the Researcher,
Practitioner, and Student personas from the PRD.

**Viewer**
Read-only consumer. Cannot upload or trigger jobs. Can view any graph/brief that an Analyst
or Admin has shared with them via a share link. This maps to the "Team Lead/Sharer" use
case from the PRD — the sharer is an Analyst, the recipients are Viewers.

### Why not more roles?
"Moderator" or "Editor" roles are unnecessary at this scale. The Analyst/Viewer split is the
minimal meaningful distinction for the sharing use case. Roles can be extended later.

---

## 2. RBAC Matrix

| Capability | Admin | Analyst | Viewer |
|---|:---:|:---:|:---:|
| Login / logout | yes | yes | yes |
| Upload PDF / create extraction job | yes | yes | no |
| View own document list | yes | yes (own only) | no |
| View all documents (global) | yes | no | no |
| View a shared graph via share link | yes | yes | yes |
| Delete own document + job | yes | yes | no |
| Delete any document | yes | no | no |
| **LLM provider / model config** | **yes** | **no** | **no** |
| **API key management** | **yes** | **no** | **no** |
| **User management (create/edit/role/deactivate)** | **yes** | **no** | **no** |
| View audit log | yes | no | no |
| Re-run extraction on a document | yes | yes (own only) | no |
| Export graph / brief (JSON / Markdown) | yes | yes | yes (shared only) |

High-stakes capabilities (bolded) are Admin-only. There is no self-service role escalation.

---

## 3. Authentication Design

### Recommendation: adopt the toeic_app pattern verbatim

The toeic pattern — short-lived JWT access token held in zustand in-memory state (never
localStorage), paired with an HttpOnly SameSite=Strict refresh cookie and a `/auth/refresh`
silent replay interceptor — is the right architecture for this app. Reasons:

1. The access token is never written to disk/storage, protecting against XSS token theft.
2. The refresh cookie is HttpOnly, protecting against JS access entirely.
3. The token replay interceptor is already written and proven in toeic. Copying it avoids
   re-solving a subtle concurrency bug (multiple inflight requests all racing to refresh).
4. The backend is FastAPI, same as toeic's sibling services, so the JWT/cookie middleware
   pattern is already understood.

### Auth endpoints required (new on the FastAPI backend)

```
POST /auth/login          → { access_token } + Set-Cookie: refresh_token (HttpOnly)
POST /auth/logout         → clears the refresh cookie, invalidates refresh token in DB
POST /auth/refresh        → reads HttpOnly cookie, issues new access_token
POST /auth/register       → Admin-only in MVP (creates a new user)
POST /auth/forgot-password  → sends reset email (Sprint 2 — requires SMTP config)
POST /auth/reset-password   → validates reset token, sets new password (Sprint 2)
GET  /auth/me             → returns current user profile + role
```

### SSE endpoint authentication — the hard problem

`EventSource` (the browser's native SSE API) cannot send custom headers, including
`Authorization: Bearer <token>`. The current `/api/jobs/{id}/events` endpoint is therefore
impossible to protect with standard Bearer auth.

**Recommended solution: short-lived signed job token**

1. After `POST /api/jobs` returns a `job_id`, the client immediately calls
   `POST /api/jobs/{id}/stream-token` (authenticated with Bearer) which returns a
   single-use, 60-second signed token.
2. The client opens `EventSource('/api/jobs/{id}/events?t=<token>')`.
3. The backend validates the token on SSE connection, then streams as today.

This is clean, standard, and does not require the browser to send cookies with CORS
(which has its own SameSite complexity). The 60-second window is safe because the client
opens the SSE connection immediately after getting the token.

### Registration policy

For MVP: **admin-only user creation**. KnowledgeBook uses expensive cloud LLM API calls
(Claude, OpenAI) that cost real money. Open self-registration is a cost liability. An admin
creates user accounts manually. Add self-registration behind a feature flag in Sprint 2
if needed.

### Bootstrap: first admin

When the users table is empty, the backend accepts a `POST /auth/bootstrap` call (disabled
once any user exists) to create the initial admin with email + password from the request
body. Alternatively, seed via an `ADMIN_EMAIL` / `ADMIN_PASSWORD` env var pair at first
startup. The env-var approach is simpler for Docker deployments.

### Idle timeout

Implement: after 60 minutes of inactivity, clear the zustand auth state and redirect to
`/login`. The toeic `IdleTimeout.tsx` component can be copied directly.

### Token lifetimes

Access token: 15 minutes. Refresh token: 7 days (rolling). These are the toeic defaults
and are appropriate.

---

## 4. UI / Information Architecture

### Public routes (no auth required)

```
/login                  LoginPage
/forgot-password        ForgotPasswordPage
/reset-password         ResetPasswordPage
/register               RegisterPage (admin-initiated; may be a token-gated invite link)
```

These share an `AuthShell` layout (centered card, no nav) — copy directly from toeic.

### Authenticated app shell

`AppLayout` wraps all authenticated routes. It provides:
- **Left sidebar / top nav** with role-gated items:
  - Documents (all authenticated users)
  - Upload (Analyst + Admin)
  - Admin section (Admin only): Users, Config, Audit Log
- **Header** with: product logo/name, current user display name + avatar/initials, dropdown
  user menu (Profile, Settings, Logout)

Wrap every authenticated route in `ProtectedRoute` — copy from toeic. `roleHome.ts` maps
Admin → `/admin/users`, Analyst → `/documents`, Viewer → shown a "you have no documents
yet, share a link with me" landing.

### Authenticated screens

| Route | Screen | Role | Notes |
|---|---|---|---|
| `/documents` | Document Library | Admin, Analyst | List of jobs with status (running/done/error), filename, date, stats. Polling via react-query. Admin sees all; Analyst sees own. |
| `/documents/new` | Upload + Workflow | Admin, Analyst | The existing App.tsx core flow, restyled inside AppLayout. Drag-and-drop upload, SSE pipeline stages, redirects to `/documents/:id` on completion. |
| `/documents/:id` | Document Detail | Admin, Analyst (own), Viewer (shared) | Tabbed: Brief / Graph Explorer / Chapter Guide / Q&A. The existing GraphView + Brief become tabs here. |
| `/documents/:id/share` | Share Settings | Admin, Analyst (own) | Generate/revoke a public share link. |
| `/admin/users` | User Management | Admin only | List users, create user, edit role, deactivate. |
| `/admin/config` | LLM Config | Admin only | Current provider, model, masked API key. Save triggers backend `.env` or DB update. |
| `/admin/audit` | Audit Log | Admin only | The existing `audit()` calls surfaced as a table. Sprint 3+. |

### What to copy from toeic vs build new

**Copy (adapt only):**
- `src/store/authStore.ts` — swap user schema to match KnowledgeBook roles
- `src/api/client.ts` — copy axios instance with refresh interceptor verbatim
- `components/ProtectedRoute.tsx` — copy verbatim
- `AuthShell.tsx`, `PublicLayout.tsx` — copy verbatim
- `IdleTimeout.tsx` — copy verbatim
- `lib/roleHome.ts` — update role names only
- Login, ForgotPassword, ResetPassword pages — copy, update copy/branding
- `AppLayout.tsx` — copy structure, replace nav items

**Build new:**
- Document Library page (list + status polling)
- Upload + Workflow page (restyled from existing App.tsx)
- Document Detail page (tabs: Brief, Graph, Chapter Guide, Q&A)
- Share link modal
- Admin: Users page (CRUD)
- Admin: LLM Config page (form → PUT /admin/config)

**Keep from existing frontend:**
- `GraphView` component (react-force-graph-2d) — keep as-is, embed in the Graph tab
- `WorkflowStages` component — keep as-is, embed in Upload page
- The SSE subscription logic in `api.ts` — keep, add token-param support

---

## 5. Backend Implications

### What must change in FastAPI

**1. Persistence: in-memory JOBS dict → database**

The global `JOBS: dict[str, Job]` in `api.py` is the most critical piece of technical debt.
It must be replaced with a proper persistence layer before auth can work, because:
- Per-user visibility requires querying jobs by `user_id`
- Jobs are lost on restart — unacceptable once users rely on them
- A single process can only scale to one CPU core

Recommendation for MVP: **PostgreSQL** (already called out in `ARCHITECTURE-mvp.md`).
Tables: `users`, `jobs`, `refresh_tokens`. Use SQLAlchemy + asyncpg (or sync psycopg2 for
simplicity in MVP given the existing threading model).

If Postgres feels heavy for the current stage: SQLite via SQLAlchemy is a valid stepping
stone — same schema, trivial migration path, no extra Docker service.

**2. Auth middleware**

Add a FastAPI dependency `get_current_user()` using python-jose (JWT decode) + DB lookup.
All existing `/api/jobs/*` endpoints get this dependency. Role checks via a second
dependency `require_role(role: str)`.

**3. Job model gains user_id**

```python
@dataclass
class Job:
    id: str
    user_id: str        # NEW — foreign key to users.id
    title: str
    status: str
    ...
```

`GET /api/jobs/{id}` checks that `job.user_id == current_user.id` (or user is Admin).
`POST /api/jobs` sets `job.user_id = current_user.id`.

**4. New endpoints**

```
GET  /api/jobs              List user's jobs (Admin: all jobs)
POST /api/jobs/{id}/stream-token   Issue 60-sec SSE token
PUT  /admin/config          Update LLM settings (Admin only)
GET  /admin/config          Read current config, mask API keys (Admin only)
GET  /admin/users           List users (Admin only)
POST /admin/users           Create user (Admin only)
PATCH /admin/users/{id}     Update role / deactivate (Admin only)
```

**5. Password hashing**

Use `passlib[bcrypt]`. Never store plaintext passwords.

**6. Config management**

The current `.env` file approach works but requires container restarts to pick up changes.
For the Admin Config UI to work without restarts, store LLM provider config in a `settings`
DB table (single row) and have `get_settings()` read from DB first, env vars as fallback.

**7. CORS**

Tighten CORS for production. Currently allows `localhost:5173` only. In production, allow
only the frontend's actual origin.

---

## User Stories

### US-001: Login and logout
As an authenticated user,
I want to log in with email + password and log out,
So that my documents and usage are private to my account.

**Acceptance Criteria:**
- [ ] Given valid credentials, when I submit the login form, then I receive an access token and am redirected to my role home
- [ ] Given invalid credentials, when I submit the login form, then I see an error message and am not redirected
- [ ] Given I am logged in, when I click Logout, then my access token is cleared and I am redirected to /login
- [ ] Given my access token has expired (15 min), when I make an API call, then the client silently refreshes and replays without prompting me
- [ ] Given 60 minutes of inactivity, when the idle timer fires, then I am logged out and redirected to /login

**Out of scope for this story:** Social auth, 2FA, remember-me beyond 7-day refresh token
**RICE Score:** Reach=50 × Impact=3 × Confidence=100% / Effort=2 = **75**

---

### US-002: Protected app shell with role-gated navigation
As an authenticated user,
I want to see an app shell with navigation appropriate to my role,
So that I can navigate the product and only see what I am allowed to access.

**Acceptance Criteria:**
- [ ] Given I am an Analyst, when I log in, then I see Documents + Upload in the nav, and no Admin section
- [ ] Given I am an Admin, when I log in, then I see Documents, Upload, and the Admin section (Users, Config) in the nav
- [ ] Given I am a Viewer, when I navigate to /documents, then I see a "no documents — get a share link" empty state
- [ ] Given I navigate to a protected route while unauthenticated, then I am redirected to /login with the intended URL preserved (redirect-after-login)
- [ ] Given I am an Analyst and navigate to /admin/users, then I receive a 403 page

**Out of scope:** Route-level animations, breadcrumbs
**RICE Score:** Reach=50 × Impact=2 × Confidence=100% / Effort=1.5 = **67**

---

### US-003: Per-user document library with persistent job history
As an Analyst,
I want to see a list of all my documents (past and current jobs) with their status,
So that I can revisit previous extractions without losing them on server restart.

**Acceptance Criteria:**
- [ ] Given I have uploaded 3 PDFs in previous sessions, when I log in and go to Documents, then I see all 3 with their status and metadata
- [ ] Given a job is running, when I view Documents, then its row shows a "running" indicator with elapsed time
- [ ] Given I am an Admin, when I view Documents, then I can toggle between "My documents" and "All documents"
- [ ] Given a job has errored, when I view its row, then I see an error badge with a short message
- [ ] Jobs must survive server restart (persisted to database)

**Out of scope:** Pagination (deferred until >50 docs), search/filter
**RICE Score:** Reach=50 × Impact=2 × Confidence=90% / Effort=3 = **30**

---

### US-004: Upload and run extraction (restyled)
As an Analyst,
I want to upload a PDF and watch the extraction pipeline stages run,
So that I can track progress and be redirected to my result when done.

**Acceptance Criteria:**
- [ ] Given I am on the Upload page, when I drop a PDF or click the upload button, then the job starts and I see the pipeline stages render in real time (SSE)
- [ ] Given the extraction completes, when the SSE stream ends, then I am automatically navigated to /documents/:id
- [ ] Given the SSE stream requires auth, when I open EventSource, then a short-lived stream token is used as a query parameter (not the access token itself)
- [ ] Given the file exceeds the configured max size, when I submit, then I see a clear error before any upload occurs

**Out of scope:** Drag-and-drop multi-file, batch upload
**RICE Score:** Reach=50 × Impact=2 × Confidence=95% / Effort=2 = **47.5**

---

### US-005: Document detail view (Brief + Graph + Chapter Guide + Q&A)
As any authenticated user with access to a document,
I want to view all four outputs of an extraction (Brief, Concept Map, Chapter Guide, Q&A) in a single tabbed view,
So that I can explore the document's knowledge structure without navigating away.

**Acceptance Criteria:**
- [ ] Given a completed job, when I navigate to /documents/:id, then I see four tabs: Brief, Graph, Chapter Guide, Q&A
- [ ] Given I click the Graph tab, then the force-directed graph renders with node click behavior as today
- [ ] Given I click the Brief tab, then thesis, core concepts, key principles, and summary render
- [ ] Given a job is still running, when I navigate to its detail page, then I see the pipeline progress view (not the tabs)

**Out of scope:** Inline editing of the extracted graph, custom node colors
**RICE Score:** Reach=50 × Impact=2 × Confidence=85% / Effort=2.5 = **34**

---

### US-006: Admin user management
As an Admin,
I want to create, view, edit roles for, and deactivate user accounts,
So that I control who has access to the system and at what permission level.

**Acceptance Criteria:**
- [ ] Given I am on /admin/users, when I click Create User, then I can enter email + role and the user is created (they receive an invite email or a one-time password)
- [ ] Given I select a user, when I change their role from Analyst to Viewer, then their next API call respects the new role
- [ ] Given I deactivate a user, when they try to log in, then they receive "account disabled"
- [ ] Given I am not an Admin and I navigate to /admin/users, then I get a 403

**Out of scope:** Self-service profile editing, avatar upload, org-level teams
**RICE Score:** Reach=3 × Impact=3 × Confidence=100% / Effort=2 = **4.5** (low reach, required for launch)

---

### US-007: Admin LLM config
As an Admin,
I want to view and change the active LLM provider, model, and API keys from the UI,
So that I can switch from Ollama to Claude or OpenAI without SSH access to the server.

**Acceptance Criteria:**
- [ ] Given I am on /admin/config, when the page loads, then I see the current provider, model name, and a masked API key (last 4 chars)
- [ ] Given I change the provider to "claude" and enter a new API key, when I save, then the next extraction job uses the new provider
- [ ] Given I enter an invalid API key, when I save, then the backend validates the key (test call) and returns an error
- [ ] Given I am not an Admin, then the /admin/config page and PUT /admin/config endpoint both return 403

**Out of scope:** Multiple provider profiles, per-user provider selection
**RICE Score:** Reach=3 × Impact=2 × Confidence=90% / Effort=1.5 = **3.6** (required for Admin UX)

---

## Prioritized Backlog

| # | Story ID | Title | RICE Score | Priority | Target Sprint |
|---|----------|-------|-----------|---------|--------------|
| 1 | US-001 | Login and logout | 75 | P0 | Sprint 1 |
| 2 | US-002 | Protected app shell + role nav | 67 | P0 | Sprint 1 |
| 3 | US-004 | Upload + run extraction (restyled) | 47.5 | P0 | Sprint 1 |
| 4 | US-003 | Document library + persistence | 30 | P0 | Sprint 1 |
| 5 | US-005 | Document detail (4-tab view) | 34 | P1 | Sprint 2 |
| 6 | US-006 | Admin user management | 4.5 | P1 | Sprint 2 |
| 7 | US-007 | Admin LLM config | 3.6 | P1 | Sprint 2 |

Note: US-006 and US-007 have low RICE scores due to low reach (Admins only) but are
classified P1 because the product cannot be operated without them.

---

## MVP Scope

**MUST ship (Sprint 1 — "Login + Protected Shell + Core Flow"):**
- Login / logout with JWT + HttpOnly refresh cookie (US-001)
- Protected app shell with role-gated nav: Admin + Analyst roles only (US-002)
- Upload + workflow page restyled inside AppLayout, SSE token auth (US-004)
- Job persistence to DB: survive restarts, per-user visibility (US-003 — backend portion)
- Document library page with status polling (US-003 — frontend portion)
- Backend: users table, /auth/* endpoints, role middleware on all /api/* endpoints
- Admin bootstrap: ADMIN_EMAIL + ADMIN_PASSWORD env var seed

**SHOULD ship (Sprint 2 — "Full Product Experience"):**
- Document detail page with 4 tabs (Brief / Graph / Chapter Guide / Q&A) (US-005)
- Admin: User Management page (US-006)
- Admin: LLM Config page (US-007)
- Viewer role + public share links
- Password reset via email (requires SMTP config)

**WILL NOT ship (this release):**
- Self-registration (open sign-up) — reason: cost liability with LLM API keys
- Social auth (Google/GitHub) — reason: scope; add in a later sprint
- Audit log UI — reason: the audit() calls exist in the backend; surfacing them in the UI
  is a Sprint 3 item
- i18n — reason: existing toeic i18next setup is English-only anyway for this product
- 2FA / MFA — reason: not needed at team scale
- Idle timeout — reason: nice-to-have, not a security requirement for internal tool;
  defer to Sprint 2

---

## Success Metrics

| Metric | Current baseline | Target | How measured |
|--------|-----------------|--------|-------------|
| Auth setup time (first admin + first user) | N/A (no auth) | < 5 minutes from fresh deploy | Manual test |
| Login → first extraction complete | N/A | < 2 minutes | Automated E2E test |
| Documents survive server restart | 0% (in-memory) | 100% | Integration test |
| SSE stream accessible without valid auth | 100% (no auth today) | 0% | Security test |
| UI matches toeic visual standard | No (bare) | Yes (AppLayout + tailwind + react-query) | Design review |

---

## Open Questions

| # | Question | Owner | Due date |
|---|----------|-------|---------|
| 1 | SQLite (simpler, single-container) vs PostgreSQL (already in ARCHITECTURE-mvp.md) for initial auth/jobs DB? | Eng | Before Sprint 1 starts |
| 2 | Self-registration: admin-only creation (recommended) or invite-link flow? Decision affects Sprint 1 scope. | Product | Before Sprint 1 starts |
| 3 | LLM config stored in DB table (live-switchable) vs `.env` file (needs restart)? | Eng | Sprint 2 planning |
| 4 | Share links: token-in-URL (simple) vs viewer account required (more controlled)? | Product | Sprint 2 planning |
| 5 | SMTP for password reset: which provider? (SendGrid, AWS SES, etc.) | Ops | Sprint 2 planning |

---

## 6. Risks

### Security risks

**SSE auth gap (HIGH — fix in Sprint 1)**
Current job IDs are `uuid4().hex[:12]` — 48-bit entropy. That is guessable at scale. The
SSE endpoint has no auth. Any user who knows or guesses a job ID can stream its results.
Fix: per the stream-token design in US-004. Until fixed, the SSE stream leaks document
content to unauthenticated parties.

**Default admin bootstrap (MEDIUM)**
If the bootstrap mechanism is poorly implemented (e.g., the bootstrap endpoint is never
disabled), an attacker can create their own admin. Use env-var seeding with a one-time flag
in the DB ("bootstrapped = true"), or simply check `SELECT COUNT(*) FROM users == 0`.

**API key exposure (MEDIUM)**
The `/admin/config` GET endpoint must never return raw API keys. Return only the provider
name, model name, and masked key (e.g., `sk-...abc123` → `sk-...XXXab`c`123`). The full
key is write-only from the UI.

**Token storage (LOW — already solved by adopting toeic pattern)**
Access token in zustand (React in-memory state) is correct. Do not put it in localStorage
or sessionStorage. The toeic pattern already solves this.

### Scope risk (HIGH)

This is a large architectural jump. The backend needs:
1. A database (new service or SQLite file)
2. Full user/auth system from scratch
3. Job model redesign (global in-memory → per-user persistent)
4. 6+ new endpoints

This is at minimum 3–4 weeks of backend work before the frontend auth work produces value.
Recommend: **backend sprint first** (Sprint 0 or 1a: DB + auth + job persistence with
no UI change), then **frontend sprint** (Sprint 1b: full UI uplift). Do not try to do
both simultaneously.

### Dependency risk (MEDIUM)

The toeic_app is the reference implementation but lives in a separate repo. Establish early
which files will be copied vs shared as a package. Copying (vendoring) is simpler for a
two-person team; a shared component library adds maintenance overhead.
