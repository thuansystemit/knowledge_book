# CTX: Enterprise Productization Strategy — KnowledgeBook

> **AI digest of `ENTERPRISE-productization.md`. Self-contained — read this alone; you do NOT need the full `.md`.**
> Date: 2026-07-02. Status: STRATEGY DRAFT v1.0. Convention: paired `*.ctx.md`; keep in sync; work inline.

---

## Positioning

**Product:** KnowledgeBook — PDF → knowledge graph (concepts + relationships, 100% source-cited) + multi-turn graph-grounded chat + source PDF viewer.

**Primary ICP:** Mid-size law firms (M&A due diligence), management consulting firms, pharma/regulatory affairs, gov/defense (air-gapped). Lead wedge = **legal due diligence**.

**Buyer persona:** VP Knowledge Management / Head of Legal Ops / CTO (SMB). Technical gatekeeper: CISO / IT Security (blocks on SSO, data residency, SOC 2). Champion: Senior Associate / Research Analyst.

**Core differentiation (moat, in priority order):**
1. Local-first / air-gapped deployment — only general-purpose document understanding tool that runs fully offline. Architecture already supports it.
2. Knowledge graph with 100% source citations — every node/edge traces to chapter + page. Verifiable, auditable.
3. Scanned PDF + OCR — handles legacy documents; competitors are digital-only.
4. Graph-grounded chat with "not covered" guard — lower hallucination surface than pure RAG.

**One-line value prop:** "Turn any PDF — even a scanned one — into a navigable knowledge map your team can query, with every answer traced to the source page. Runs on your network."

---

## Tiers & Pricing

| Tier | Price | Key Gating |
|------|-------|-----------|
| **Team** | $49/seat/month, min 5 seats | Hosted LLM (your API key); 50 docs/month; email/password auth only |
| **Business** | $149/seat/month, min 10 seats | BYO-key required; OIDC SSO; audit log 90d; priority support |
| **Enterprise** | $30k–$80k/year site license | SAML + SCIM + MFA; on-prem or dedicated cloud; full audit log; SLA 99.9% |

**Pricing model:** Per-seat (not per-document). Add-on overage: $3/doc over monthly limit.
**Critical:** BYO-key required from Business tier up — eliminates LLM COGS, targets ~99% gross margin on Business/Enterprise. Team tier: ~88–95% margin depending on usage.

---

## Enterprise Feature Gaps — Prioritized

### P0 — Must resolve before first paying customer

| ID | Requirement | Effort |
|----|------------|--------|
| EF-01 | Job queue + worker fleet (Celery + Redis) — current in-process threads lost on restart | L |
| EF-02 | Rate limiting per-user per-endpoint | S |
| EF-03 | Stateless API: move in-memory stream registry + job state to Redis | M |
| EF-04 | BYO-key pricing + UX formalized | S |
| EF-05 | Secrets management (not raw .env) | S |
| EF-06 | Postgres backup + tested restore | S |
| EF-07 | Basic observability (structured logs, /metrics, error alerting) | M |
| EF-08 | Automated tests + CI/CD | M |

**Immediate non-code action:** Switch default demo + customer LLM to Claude (`CHAT_PROVIDER=claude`). qwen2.5:3b ignores grounding instructions and hallucinates. This is a deal-killer in demos.

### P1 — Required to close enterprise deals (Month 3–6)

| ID | Requirement | Effort |
|----|------------|--------|
| EF-09 | SSO — OIDC (Google, Entra) | M |
| EF-10 | MFA (TOTP) | S |
| EF-11 | Audit log | M |
| EF-12 | Multi-tenancy: orgs + workspaces | L |
| EF-13 | Granular RBAC + permissions | M |
| EF-14 | Admin console (user mgmt + usage dashboards) | M |
| EF-15 | SSO — SAML 2.0 | M |
| EF-16 | SCIM provisioning | M |
| EF-17 | Horizontal scaling (multi-replica API + worker fleet) | L |
| EF-18 | Usage metering + quotas + billing integration | L |
| EF-19 | On-prem / air-gapped deployment (Helm chart + runbook) | L |
| EF-20 | API v1 + webhooks | M |
| EF-27 | Category-based document management + per-category ACL | M |
| EF-28 | User-selectable LLM model; free default + paid premium; credit system (Team) + BYO-key (Business/Enterprise) | M |

### P2 — GA Enterprise (Month 6–12)

| ID | Requirement | Effort |
|----|------------|--------|
| EF-21 | Data isolation + residency options | L |
| EF-22 | GDPR DPA | S |
| EF-23 | Encryption at rest (Postgres + blob) | S |
| EF-24 | SOC 2 Type II (12-month observation window — start Month 2) | L/time-gated |
| EF-25 | HIPAA BAA | M |
| EF-26 | Pen test + vulnerability disclosure policy | M |

**Effort key:** S = 1–2wks, M = 3–6wks, L = 6–12wks.

---

## Productionization Must-Haves

**Architecture changes before first sale (P0):**
- EF-01 Celery+Redis: highest-priority single item. In-process threads → durable job queue. Workers scale independently.
- EF-03 Stateless API: Redis pub/sub for SSE stream registry. Enables multi-replica deployment.
- Rate limit: `slowapi` (Redis-backed) or nginx limit_req. Cap: 10 chat req/min, 5 uploads/hour per user.

**Security baseline (P0/P1):**
- Secrets: AWS Secrets Manager / Vault / K8s secrets — never raw .env in production.
- TLS: terminate at load balancer; enforce on all internal connections.
- Postgres + blob encryption at rest.
- JWT key rotation on schedule.
- Docker image pinning + Trivy scan in CI.

**SOC 2 Type II path:**
- Month 2: Engage Vanta/Drata; start 12-month observation clock. Budget $15k–$30k/year.
- Month 4–6: SOC 2 Type I (controls documented). Audit log (EF-11) and access controls (EF-09/EF-10/EF-13) must be live.
- Month 14: SOC 2 Type II report available. Enterprise procurement gate cleared.

**SLOs (GA targets):** API availability 99.9%; ingestion success rate 95%; chat p95 < 8s first token; digital ingestion p90 ≤5min, scanned ≤15min.

---

## EF-27: Category-Based Document Management — Design Digest

**What it is:** Documents are organized into admin-created categories (deal rooms / matter folders). Access to a category — and every document inside it — is controlled by a per-category ACL. Without a grant, a category does not exist from a user's perspective (default-deny).

**Why it matters:** The legal wedge requires it. A law firm's M&A matter ("Project Phoenix") must be invisible to associates on an unrelated litigation matter. This is an ethical wall. For consulting: client confidentiality. For pharma: regulatory product-line separation.

**Permission model (v1):**
- Grant types (hierarchical): `view` → `upload` (implies view) → `manage` (implies upload; enables delegated membership management for that category only).
- Global `admin` = super-user; no grant needed.
- All other users: default-deny. Category grants are additive and can exceed global role.
- `manage` grants: only admins can issue them. A manage-holder can add/remove `view`/`upload` grants for others but cannot self-elevate or grant `manage`.
- v1: user-level grants only. Role-level grants deferred to v2 (see D8).

**Relationship to EF-12/EF-13:** Extension of EF-13 (granular RBAC); own EF-ID because it introduces a new authorization object (category) and a resource-scoped ACL model. Soft dep on EF-12: `category.org_id` is nullable until EF-12 lands. Can ship before EF-12.

**Data model (new tables):**
- `categories(id, org_id nullable FK, name, description, created_by FK users, timestamps)` — UNIQUE(org_id, name).
- `category_permissions(id, category_id FK CASCADE, subject_type user|role, subject_id, grant_type view|upload|manage, granted_by, granted_at)` — UNIQUE(category_id, subject_type, subject_id).
- `jobs.category_id UUID FK categories ON DELETE RESTRICT` (new column).

**Migration/backfill:** Create "General" category; assign all existing jobs to it; grant existing non-admin users `upload` on "General". Zero behavior change on migration day.

**Enforcement pattern:** Single FastAPI `Depends` — `require_category_grant(job_id, min_grant)` — resolves `job.category_id`, checks grant, raises HTTP 403. Apply to every job-scoped route (list, get, brief, graph, chat, pdf, stream). One place; cannot be forgotten per-route.

**Key risks:**
- **Category deletion with docs:** Return 409; never cascade-delete documents. Block enforced server-side.
- **Grant revocation:** Check grant at every request on the session, not just at session creation. Revoked = immediate lockout.
- **Privilege escalation via manage-grant:** Manage-holders cannot issue manage grants; only admins can.
- **Chat leakage:** Graph grounding is per-document; no cross-category context bleed. Risk is only a missed enforcement call — single-dependency pattern eliminates it.

**Optional early v1 subset (~2 weeks, Phase 0-adjacent):** Admin creates categories + assigns view/upload per user; no manage grant/delegation. Sufficient for legal design partner deal rooms before Phase 1 full implementation.

---

## EF-28: User-Selectable LLM Model — Design Digest

**What it is:** End users pick the LLM for extraction (per job) and chat (per session). Free default = qwen2.5:3b (local, already deployed). Premium = Claude/OpenAI cloud models, gated by tier and paid via credits (Team) or BYO-key (Business/Enterprise). Provider abstraction (`ollama|claude|openai`) and `CHAT_PROVIDER`/`CHAT_MODEL` env vars already exist — this promotes that setting from operator-level to user-level.

**Recommended monetization: HYBRID**
- **Team tier:** platform credit packs (you buy Anthropic/OpenAI API capacity, mark it up ~50–70%). Credits remove the "sign up for Anthropic first" friction that kills self-serve conversion.
- **Business/Enterprise:** BYO-key required (zero LLM COGS for you; they pay provider directly). Admin stores encrypted key; org model policy controls which models are allowed and sets defaults.
- Do NOT add credits to Business/Enterprise — customers will compare your credit prices to direct API costs and resent the markup.

**Credit pricing (Team tier hypothesis):**
- Credit packs: $10 = 15 credits / $25 = 45 credits / $50 = 100 credits.
- Model costs: haiku = 1 credit/doc, sonnet/gpt-4o = 2 credits/doc, opus = 3 credits/doc.
- Chat: 0.1 credit/message. Margins: 54–73% after API cost.
- Pre-flight balance check required before every premium dispatch (never dispatch first, charge later).

**Quality map shown in UI:**
| Model | Label | Notes |
|-------|-------|-------|
| qwen2.5:3b | Free — Basic | Weaker grounding; show inline warning for legal/compliance use |
| claude-3-haiku | Good — Fast | 1 credit/doc |
| claude-3-5-sonnet | Best — Balanced | 2 credits/doc; recommended for legal |
| gpt-4o | Best — Alternative | 2 credits/doc |

**Data model additions:**
- `jobs.extraction_model TEXT`, `jobs.llm_provider TEXT` (new columns; `chat_messages.model` already exists).
- `org_model_policies(org_id, allowed_models[], default_extraction_model, default_chat_model, require_byo_key)`.
- `credit_ledger(org_id, user_id, amount, credit_type purchase|spend|refund, model_used, job_id, external_charge_id)` — balance = SUM(amount) per org.
- `org_api_keys(org_id, provider openai|claude, encrypted_key BYTEA, key_hint)` — AES-256-GCM; encryption key in KMS/Vault; never in DB.

**API:** `GET /api/models` (filtered by tier + org policy + credits + AIRGAP_MODE); `POST /api/orgs/{id}/model-policy` (admin); `POST /api/orgs/{id}/credits/purchase` (Stripe; pairs with EF-18); `POST/DELETE /api/orgs/{id}/api-keys` (admin; validate key on store). Modify `POST /api/jobs` and `POST /api/jobs/{id}/chat` to accept optional `model` param.

**Config delivery — DB-resolved per request, NO restart (D14):** Do NOT drive per-user model choice from env (`CHAT_PROVIDER`/`CHAT_MODEL` are boot-time → need a restart). Resolve the effective model on every request from Postgres via `get_provider(provider, model, api_key)` (which already accepts a model override). Precedence: request `model` → `user_settings` default → `org_model_policies` default → free-local. Validate against org policy; resolve credentials (BYO from `org_api_keys`, platform from secret store). A DB write (admin edits `model_catalog`, user changes pick) applies on the next request — no reload. Scale: 30–60s TTL cache of catalog/policies + Redis pub/sub invalidation (same Redis as EF-01/EF-03) for instant fleet-wide propagation. This is also what EF-03 (stateless API) requires.

**Deployment mode gate:** If `AIRGAP_MODE=true`, `GET /api/models` returns local models only; no credit UI; no cloud provider keys accepted. On-prem customers chose offline for a reason — do not offer cloud model UI.

**Key risks:**
- Cost runaway: reserve credits pre-dispatch; return reserved credits on failed/aborted jobs. Never dispatch without balance check.
- BYO-key secrets: AES-256-GCM encrypted; KMS key; key_hint only in UI; validate before storing; log in audit log (EF-11) without logging key value.
- Model unavailability: return explicit "model unavailable" error; never silent fallback to local (user gets wrong-quality result they did not choose).
- Extraction vs. chat model are independent — do not couple. User may extract with premium (graph quality) and chat with local (cost saving). Both valid.

**Delivery split:** Slice A (model picker + org policy + BYO-key storage, no credits) = S/M, ships early Phase 1. Slice B (credit system + Stripe) = M, pairs with EF-18.

---

## Deployment Recommendation

**Lead with SaaS multi-tenant (Team/Business). Offer dedicated cloud or on-prem as the Enterprise option from day one in sales.**

- Do NOT defer on-prem to Phase 2. Regulated-industry prospects ask "can this run on our network?" on the first call. Answer must be "yes" with a deployment guide in hand.
- Immediate: package current docker-compose as a versioned release artifact. Test full stack air-gapped (no outbound internet) with local Ollama.
- Medium-term: Helm chart for Kubernetes deployment.
- On-prem pricing carries 30–50% premium over equivalent SaaS; customer provides infrastructure + LLM → your COGS ≈ $0.

---

## Grounding Quality — Key Risk

**Problem:** Graph-only chat cannot provide verbatim prose (no chunks stored). qwen2.5:3b ignores grounding constraints → hallucinates → fatal in demos/legal use.

**Fix sequence:**
1. **Immediate:** `CHAT_PROVIDER=claude` as default everywhere. One-line env change. Non-negotiable before any demo.
2. **Month 3–6 (Phase 1):** Hybrid RAG — add pgvector + chunk persistence (already in PRD architecture, deferred). Graph provides structure; chunks provide prose fidelity. Required before signing legal/compliance customers.
3. **Month 9–12:** Evaluate fine-tuned local model for on-prem grounding quality (llama-3.1-8b or mistral-7b intermediate step).

**Market the escape hatch:** "Click any citation → source PDF viewer jumps to the exact page." Position as auditability, not limitation.

---

## Phased Roadmap

| Phase | Timeline | Goal | Key Deliverables |
|-------|---------|------|-----------------|
| **P0** | Now → Month 3 | First paying customer | EF-01/02/03/04/05/06/07/08; Claude default; on-prem guide; OIDC SSO |
| **P1** | Month 3–6 | 5–10 design partners; 3 enterprise deals | EF-09–20, EF-27, EF-28; hybrid RAG; multi-tenancy; SAML; audit log; metering; credit system |
| **P2** | Month 6–12 | GA enterprise; SOC 2 | EF-21–26; SOC 2 Type II; Helm chart on-prem; billing; pen test |

---

## Open Decisions (blocking — decide in next 2 weeks)

| # | Decision | Recommendation |
|---|---------|---------------|
| D1 | First ICP / vertical | Legal due diligence (highest WTP, citations = natural fit) |
| D2 | Cloud-first vs. on-prem-first from day 1 | On-prem-ready from day 1 (already architected; don't backtrack) |
| D3 | BYO-key enforcement | Required from Business tier up |
| D4 | Hybrid RAG timing | Phase 1 if targeting legal/compliance; Phase 2 if consulting-only |
| D5 | SOC 2 start date | Month 2 — clock is time-gated; start immediately |
| D6 | Job queue choice | Celery + Redis |
| D7 | Design partner target list | Build 20-org outreach list immediately |
| D8 | EF-27: user-level vs. role-level grants in v1 | **User-level only.** Role-level (e.g., "all analysts get view on General") deferred to v2. Decide before writing migration. |
| D9 | EF-27: category deletion policy with documents inside | **Block with HTTP 409.** Admin must reassign/delete docs first. Never auto-delete or auto-migrate. |
| D10 | EF-27: scope of "manage" grant | **Membership-only** (add/remove user grants). Category rename/delete = admin-only. Prevents delegated managers from restructuring taxonomy. |
| D11 | EF-28: premium model monetization for Team tier | **Hybrid: credits for Team, BYO-key for Business/Enterprise.** Credits remove "sign up for Anthropic first" friction from self-serve; BYO-key protects margins and avoids markup resentment at higher tiers. |
| D12 | EF-28: model choice on chat in v1 — both or extraction-only? | **Both (extraction + chat) in v1.** `chat_messages.model` already stored; provider abstraction already supports per-session model; incremental cost is minimal. No reason to defer. |
| D13 | EF-28: credit pricing unit | **Credit packs** (not per-token, not per-doc raw). User-facing simplicity: 1 credit = 1 premium extraction or 10 premium chat messages. Store per-model credit cost in a config table to allow repricing without code deploy. |
| D14 | EF-28/EF-03: apply per-user model config WITHOUT restart | **DECIDED — configuration-as-data (DB-resolved per request), not env.** Model choice + `org_model_policies` + credentials live in Postgres; resolved on every request (precedence: request pick → user default → org default → free-local `qwen2.5:3b`). Env only for bootstrap/system defaults; premium keys from secret store (platform) or encrypted DB (BYO). A DB write (admin edits `model_catalog`, or user changes pick) takes effect on next request — no reload/redeploy. At scale: 30–60s cache of catalog/policies + **Redis pub/sub** invalidation (same Redis as EF-01/EF-03) for instant fleet-wide propagation. Retires "edit `.env` → restart"; required for stateless multi-replica API (EF-03). |

---

## Success Metrics (6-month targets)

Activation ≥70% · Chat engagement rate ≥50% · Graph accuracy (sampled) ≥80% · Trust score (no-flag rate) ≥85% · Month-2 return ≥40% · Design partners active = 10 · ARR = $150k+ · Gross margin ≥85%.

---

## Top Risks

1. Demo hallucination (qwen2.5:3b) destroys trust → fix immediately with Claude default.
2. Enterprise procurement cycle (6–12 months) exceeds runway → design partners with 90-day trial-to-paid pathway; target SMB legal first.
3. Microsoft/Adobe adds graph-style citations → on-prem + local-first moat they cannot replicate.
4. SOC 2 delay → start Vanta onboarding Month 2.
5. LLM COGS on Team tier → hard 50-doc/month cap + BYO-key from Business up.

---

`pull_hint: "Full tier table, effort table, GTM motion, risk table, EF-27 full data model + API table + UI notes, EF-28 credit pricing tables + model quality map + full data model + API table + risk detail, decision log → ENTERPRISE-productization.md"`
