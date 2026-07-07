# Conformance & Gap Analysis — Implementation vs. Design Docs

| | |
|---|---|
| **Document** | Conformance / Gap Analysis |
| **Date** | 2026-07-06 |
| **Audited against** | `monetization-pricing.md` (v1.0), `ARCHITECTURE-enterprise.md` (v1.0) |
| **Method** | Static read of `extraction-service/app/*` (no runtime execution) |
| **Auditor** | Engineering |

> **How to read status:** ✅ Match · ⚠️ Partial / diverges · ❌ Not implemented.
> "Diverges" ≠ "broken" — several divergences are deliberate product evolutions
> (noted inline). Prices in `$` live in Stripe price IDs, not code, and were not
> verified here.

---

## 1. Executive Summary

- **Monetization:** ~85% implemented. Tier model, quotas, and feature-gating match
  the pricing doc exactly. Gaps: the 25-doc credit pack, paid-tier scanned
  sub-limits, and the student discount. Free-tier Q&A is implemented as a
  downgraded retrieval chat rather than a hard lock (deliberate — RC-20).
- **Architecture (11-step migration):** ~70% implemented. Redis, Celery,
  stateless SSE, multi-tenancy, category ACL, and config-as-data (model
  selection) are done. Remaining: secrets management, observability seams,
  BYO-key credential resolution, unified enforcement, and multi-replica deploy.
- **Security / enforcement:** **No unauthorized data-serving route found.** Every
  job/chat/document/activation route enforces access. Two structural divergences
  from the doc's `enforce_job_access` design exist but **fail closed** (details in
  §4).

---

## 2. Monetization Conformance

| # | Doc requirement | Implementation | Status |
|---|---|---|---|
| M1 | Free / Pro / Scholar tiers; Team deferred to Phase 2 | `plans.py PLANS=("free","pro","scholar")` — no Team | ✅ |
| M2 | Quotas: Free 2, Pro 20, Scholar 60 docs/mo | `config.py` `plan_free_docs=2`, `plan_pro_docs=20`, `plan_scholar_docs=60` | ✅ |
| M3 | Free concept map capped at 10 (25 on paid) | `plan_free_concepts=10`, `apply_free_tier_caps()` | ⚠️ Free cap ✅; paid **not** hard-capped at 25 (uncapped) |
| M4 | Free: scanned PDFs blocked | `enforce_scanned_allowed()` → 402 for free + scanned/hybrid | ✅ |
| M5 | Free: Chapter Guide withheld | `apply_free_tier_caps()` sets `chapter_guide_locked` | ✅ |
| M6 | Export = Pro/Scholar only | `can_export()` gates `/export` → 402 | ✅ |
| M7 | Credits never expire | `User.credits` integer, spent in `enforce_upload_quota()` | ✅ |
| M8 | Annual billing option | `stripe_price_*_annual`, `interval in ("monthly","annual")` | ✅ (doc *recommended deferring* to Month 2; shipped early — not a conflict) |
| M9 | Stripe webhook = source of truth | `billing.handle_event()` sets plan from verified events | ✅ |
| M10 | **Credit packs: 5-doc/$5, 10-doc/$9, 25-doc/$20** | `credit_packs()` has **only 5 and 10**; no per-plan gating | ❌ 25-doc pack missing; packs not plan-restricted |
| M11 | **Free = no Grounded Q&A (Output 4)** | Free gets zero-LLM **retrieval chat**; LLM chat gated to Pro+ (`effective_chat_mode`) | ⚠️ Deliberate divergence (RC-20 value ladder) |
| M12 | **Pro 5 scanned/mo, Scholar 20 scanned/mo** sub-limits | Only a combined total-doc quota; no separate scanned counter for paid | ❌ Not enforced |
| M13 | Student .edu discount (3 mo free Pro) | Not implemented (`allow_promotion_codes=True` gives generic promo support) | ❌ Missing |

---

## 3. Architecture Migration Conformance

Ordered by the doc's 11-step migration sequence (§9).

| Step | Concern (EF) | Status | Evidence / Notes |
|---|---|---|---|
| 1 | Redis | ✅ | `redis:7-alpine` in compose; `redis_client.py` |
| 2 | Celery job queue (EF-01) | ✅ | `celery_app.py`, `tasks.py` (`run_extraction`, `retry_extraction`), `worker` service; daemon threads gone |
| 3 | Stateless SSE via Redis pub/sub + List (EF-03) | ✅ | `job_events.py` (`rpush`/`publish`/`lrange`/`pubsub`/`subscribe`); DB fallback for expired streams |
| 4 | Rate limiting (EF-02) | ⚠️ | Custom Redis fixed-window (`ratelimit.py`), **not slowapi**. Only `upload` + `chat` buckets — no login/register/general limits or nginx `limit_req` |
| 5 | Secrets management (EF-05) | ❌ | No `SecretProvider`/Vault; still raw `.env` |
| 6 | Observability seams (EF-07) | ⚠️ | Still `audit()` JSON-lines; custom `/api/admin/metrics` (not Prometheus format); no structlog/OTel |
| 7 | Multi-tenancy — nullable `org_id` (EF-12) | ✅ | `Organization` table; `org_id` on users/jobs/categories/chat |
| 8 | Config-as-data (D14/EF-28) | ⚠️ | `ModelCatalog`/`OrgModelPolicy`/`UserSettings` + `model_resolver.resolve()` precedence ✅. **BYO-key / platform-key / AIRGAP credential resolution not built** |
| 9 | Category ACL (EF-27) | ✅ | `Category`, `CategoryPermission`, `access.py` grant hierarchy |
| 10 | Unified enforcement layer | ⚠️ | Helper `require_job_access()` exists but is called **imperatively**, and inconsistently (see §4), rather than as the single `Depends()` choke-point the doc specifies |
| 11 | Multi-replica API + nginx LB | ❌ | Single `api` service; no `replicas:`/nginx upstream (code is stateless-ready) |

### 3.1 Data model deltas (doc §10 vs `models.py`)

| Table | Status |
|---|---|
| `organizations`, `categories`, `category_permissions`, `model_catalog`, `org_model_policies`, `user_settings` | ✅ Present |
| `org_api_keys` (BYO encrypted keys) | ❌ Missing |
| `credit_ledger` | ❌ Missing — credits are a plain `User.credits` int, not an auditable ledger |

---

## 4. Security / Enforcement Audit (route-by-route)

**Question:** with no unified `enforce_job_access` dependency, does every
resource route actually enforce access? **Answer: yes — no bypass found.**

Two helpers are in play:
- `require_job_access(db, user, job_id)` — admin **or** owner **or** `view` grant on
  the job's category (EF-27-aware).
- `_owned_job(job_id, user, db)` — admin **or** owner only (ignores category grants).

### Route coverage matrix

| Route | Check | Verdict |
|---|---|---|
| `GET /api/jobs` | `visible_category_ids` filter + own | ✅ scoped |
| `GET /api/jobs/{id}` | `require_job_access` | ✅ |
| `GET /api/jobs/{id}/export` | `require_job_access` + `can_export` | ✅ |
| `GET /api/jobs/{id}/pdf` | `require_job_access` | ✅ |
| `POST /api/jobs/{id}/retry-failed` | `require_role(admin,analyst)` + `_owned_job` | ✅ (stricter) |
| `POST /api/jobs/{id}/reprocess` | `require_role(admin,analyst)` + `_owned_job` | ✅ (stricter) |
| `DELETE /api/jobs/{id}` | `_owned_job` | ✅ (stricter) |
| `POST /api/jobs/{id}/stream-token` | `require_job_access` → mints job-scoped token | ✅ |
| `GET /api/jobs/{id}/events` (SSE) | stream token, `claims.job != job_id` → 401 | ✅ |
| `POST /api/jobs/{id}/chat` | `_owned_job` + `chat_limit` | ✅ (stricter) |
| `GET /api/jobs/{id}/chat/{msg}/stream` (SSE) | chat-stream token, `job`+`msg` bound → 401 | ✅ |
| `GET /api/jobs/{id}/chat/history` | `_owned_job` | ✅ |
| `DELETE /api/jobs/{id}/chat` | `_owned_job` | ✅ |
| `POST /activation/view`, `/rate`, `GET /status/{id}` | `require_job_access` | ✅ |
| `PUT /api/orgs/{org_id}/model-policy` | `require_role(admin)` + `admin.org_id != org_id → 403` | ✅ org-scoped |
| `POST /categories/{id}/permissions` | `_org_category` + `require_category(manage)` + `target.org_id == user.org_id` | ✅ blocks cross-org grants |

### Findings (none are exploitable leaks; all fail closed)

- **S1 — Inconsistent access model (medium, correctness).** Read routes use the
  category-aware `require_job_access`; chat/retry/reprocess/delete use
  `_owned_job` (owner-or-admin only). **Effect:** category sharing grants *view/
  export/pdf* but silently **not** chat/retry/reprocess/delete. Fails closed, so
  it is a feature gap, not a hole. The doc's design intends one
  `enforce_job_access(min_grant=...)` for all.
- **S2 — Misleading comment (low).** `chat_routes.py:59` claims chat is "gated by
  `_owned_job` (admin, owner, or a `view` grant on the category)", but `_owned_job`
  does **not** consult category grants. Comment contradicts code (see S1).
- **S3 — Implicit tenant isolation (medium, defense-in-depth).** The job-access
  path never checks `job.org_id == user.org_id` explicitly. Isolation holds today
  because (a) ownership is by `user_id` and (b) cross-org grants are blocked at
  creation (`target.org_id == user.org_id`). The doc's §3.5 design uses an
  explicit org check as a second layer. **Risk:** any future path that reassigns
  `org_id` or creates a grant without the org check would breach isolation with no
  backstop.
- **S4 — `require_byo_key` stored but not enforced (medium).** `OrgModelPolicy`
  has a `require_byo_key` flag settable via the API, but `model_resolver.resolve()`
  ignores it (no BYO-key path exists — see §3.1 `org_api_keys` missing). A policy
  that claims to require customer keys does nothing.
- **S5 — Global admin is cross-org superuser (info).** `role == "admin"` returns
  max grant everywhere and bypasses org scoping. `access.py` documents this as
  intended ("a global admin is a super-user"); the enterprise doc instead scopes
  admin to their org. Confirm this matches the intended enterprise RBAC.

---

## 5. Prioritized Remediation Backlog

**P0 — correctness / policy integrity**
- [ ] S1/S2: Unify job access on a single `enforce_job_access(min_grant)` used by
      **all** job/chat routes; decide whether chat/retry/reprocess honor category
      grants, and fix the comment. (Delivers doc Step 10.)
- [ ] S4: Either enforce `require_byo_key` in `resolve()` or hide the flag until
      the BYO-key path (`org_api_keys`) ships.

**P1 — enterprise gaps the docs call for**
- [ ] S3: Add an explicit `job.org_id == user.org_id` assertion in the access path
      as defense-in-depth.
- [ ] `org_api_keys` table + AES-256-GCM BYO-key encryption + credential
      resolution (BYO / platform / AIRGAP) — doc §3.3, §5.
- [ ] Secrets management: `SecretProvider` (`env` | `vault`) — doc §5, Step 5.
- [ ] Observability seams: structlog + Prometheus `/metrics` + health checks —
      doc §6, Step 6.
- [ ] `credit_ledger` table to replace the bare `User.credits` counter (auditable
      transactions) — doc §10.

**P2 — monetization completeness**
- [ ] 25-doc credit pack + per-plan pack gating (M10).
- [ ] Paid-tier scanned sub-limits: Pro 5/mo, Scholar 20/mo (M12).
- [ ] Student .edu discount mechanics (M13).
- [ ] Decide whether to hard-cap paid concept maps at 25 (M3).

**P3 — scale-out**
- [ ] Rate limiting: extend buckets to login/register/general + nginx `limit_req`
      (M/EF-02, Step 4).
- [ ] Multi-replica API + nginx load balancer (Step 11).

---

*Generated from a static code audit; verify P0/P1 items against runtime behavior
before closing.*
