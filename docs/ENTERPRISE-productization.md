# ENTERPRISE Productization Strategy — KnowledgeBook
**Date:** 2026-07-02  **Author:** @product-manager  **Status:** STRATEGY DRAFT v1.0
**Audience:** Founder + first sales / technical hires

---

## Executive Summary

KnowledgeBook is a working product with a genuine enterprise differentiator: it turns any dense PDF (including scanned) into a verifiable knowledge graph where every claim traces back to a source page. The graph-plus-citation model, combined with local-first / air-gapped deployment capability, is a rare combination in this space. The path to a first paying enterprise customer is 3–4 months of targeted productionization work, not a rebuild.

The single biggest risk is answer quality: the default 3B Ollama model is too weak for enterprise trust. Switch the default to Claude for all demos and first customers immediately.

---

## 1. Market & Positioning

### 1.1 Who Buys This

The fundamental pain KnowledgeBook solves: **knowledge workers spend 4–8 hours reading a dense 200-page document before they can use it.** The product cuts that to 20 minutes and then lets them query it safely.

**Primary ICPs (Ideal Customer Profiles):**

| ICP | Wedge Use Case | Volume of Docs | Why They Pay |
|-----|---------------|---------------|--------------|
| Mid-size law firms (50–500 lawyers) | M&A due diligence, regulatory filings, contract review | 10–50 docs/deal, many deals | Speed to insight is billable leverage; citations required for liability |
| Management consulting firms | Rapid client/industry research, RFP responses, case research | 5–20 docs/engagement | Analyst productivity is a direct cost driver |
| Pharma / life sciences | Clinical trial documents, regulatory submissions (FDA/EMA), formulary reviews | 50–200pp technical PDFs | Compliance requires traceability; scanned legacy docs are common |
| Government & defense contractors | Policy analysis, procurement documents, intelligence briefs | Classified / air-gapped environments | Cannot use cloud tools; local-first is mandatory |
| Corporate legal / compliance teams | Internal policy libraries, vendor contracts, litigation discovery | Library of recurring documents | Audit trail required; paralegal productivity |

**Buyer vs. User personas:**

| Role | Persona | Pain | What They Need to Approve a Deal |
|------|---------|------|----------------------------------|
| **Economic buyer** | VP Knowledge Management, Head of Legal Ops, Chief Compliance Officer, CTO (SMB) | "We pay analysts to read PDFs" | ROI in hours saved; compliance story; reference customers |
| **Technical gatekeeper** | IT Security, InfoSec, CISO | "Does this send our docs to some cloud LLM?" | SOC 2, SSO, data residency, on-prem option |
| **Champion (user)** | Senior Associate, Research Analyst, Regulatory Affairs Manager | "I spend 6 hours reading before I can contribute" | Demo quality; citation accuracy; speed |

### 1.2 The Wedge

**Lead with legal due diligence.** Reason: (a) lawyers already pay for expensive information tools and understand ROI in hours, (b) citation fidelity is non-negotiable — lawyers cannot quote a document they cannot verify, and our source-PDF viewer + page citations is purpose-built for this, (c) the scanned PDF capability handles legacy documents that ChatPDF-class tools drop, (d) deal sizes are $20k–$80k/year for even small firm deployments.

### 1.3 Value Proposition (Crisp)

> **"KnowledgeBook turns any document — even a scanned PDF — into a navigable knowledge map your team can query, with every answer traced back to the source page. Runs entirely on your infrastructure, no document ever leaves your network."**

Three proof points to back it up in a demo:
1. Upload a 200-page scanned contract → knowledge graph in under 12 minutes.
2. Ask a natural language question → answer with chapter/page citations.
3. Click a citation → source PDF viewer jumps to the exact page.

### 1.4 Competitive Landscape

| Competitor | What They Do | Why We Win |
|-----------|-------------|------------|
| **ChatPDF / AskYourPDF** | Upload-and-chat, RAG-based, cloud-only | No knowledge graph; no citations traceable to page; no scanned support; no on-prem; consumer quality |
| **Adobe Acrobat AI** | Document chat inside Acrobat | Digital PDFs only; no graph; locked to Adobe ecosystem; no on-prem |
| **Microsoft 365 Copilot** | Document Q&A inside Office suite | Requires full M365; no graph structure; citations unreliable; no on-prem; hallucination risk not mitigated |
| **Kensho (S&P) / Relativity** | Domain-specific (finance/legal) | Expensive ($100k+), domain-locked, not general-purpose, cloud-only |
| **Custom RAG builds** | Internal ML team builds their own | 3–6 month build time, MLOps overhead, no UI, no graph structure — KnowledgeBook is the turnkey alternative |
| **Notion AI / Confluence AI** | Workspace Q&A | Workspace tool, not document-deep analysis; no graph; no scanned support |

**Unique moat (defend this):**
1. **Local-first / air-gapped** — only general-purpose document-understanding tool that runs entirely offline with a local LLM. This is a hard technical moat; competitors are cloud-only by architecture.
2. **Knowledge graph with 100% source citations** — not a black-box summary; every node and edge traces to a chapter + page range. Verifiable, auditable, legally defensible.
3. **Scanned PDF + OCR** — handles the legacy document libraries that block most enterprises from adopting digital-only tools.
4. **Graph-grounded chat** — answers are bounded by extracted concepts; the "not covered" response is a feature, not a bug. Lower hallucination surface than pure RAG.

---

## 2. Packaging & Pricing

### 2.1 Recommended Tiers

| | **Team** | **Business** | **Enterprise** |
|--|---------|-------------|---------------|
| **Price** | $49/seat/month (min 5 seats) | $149/seat/month (min 10 seats) | $30,000–$80,000/year (site license) |
| **Min ARR** | ~$2,940/year | ~$17,880/year | $30,000+/year |
| **LLM** | Hosted (your Claude/OpenAI key) | BYO-key required | BYO-key or local Ollama on-prem |
| **Documents/month** | 50 across team | 300 across team | Unlimited (volume commitments negotiated) |
| **PDF size limit** | 100MB | 500MB | Unlimited |
| **RBAC** | Admin/analyst/viewer (as-built) | Same + workspace-level permissions | Full granular RBAC + org hierarchy |
| **SSO** | None (email/password) | OIDC (Google, Entra) | SAML 2.0 + OIDC + SCIM |
| **MFA** | None | TOTP | TOTP + hardware key |
| **Audit log** | None | 90-day log | Full audit log, configurable retention |
| **Deployment** | SaaS multi-tenant | SaaS (shared or dedicated) | SaaS dedicated or on-prem / air-gapped |
| **Data retention** | 30 days | 90 days | Configurable (1–7 years) |
| **Support** | Email (48h SLA) | Priority email (24h) + Slack | Dedicated CSM + 99.9% SLA |
| **API access** | None | Read API only | Full API + webhooks |
| **Compliance** | None | GDPR DPA available | SOC 2 Type II + GDPR DPA + HIPAA BAA (roadmap) |

### 2.2 Pricing Model Rationale

**Why per-seat (not per-document)?**
- Per-seat aligns incentives: customers want to process more documents (more value), not be charged more for using the product.
- Per-document pricing creates friction ("should I upload this or not?") that slows adoption.
- Exception: add-on per-document overage ($3/doc over the monthly limit) for burst usage on Team/Business.

**BYO-key as a Business/Enterprise requirement — not a nice-to-have.** This is the most important pricing decision. At $49/seat, if you absorb Claude API costs (~$0.30–$1.00/document), margins collapse at any meaningful usage. Push BYO-key from Business tier upward. This also eliminates your LLM data-processing liability — their key, their data agreement with Anthropic/OpenAI.

**On-prem premium:** On-prem/air-gapped deployments should carry a 30–50% premium over equivalent SaaS pricing because of the support cost. Customers in this tier provide their own infrastructure and LLM — your COGS drop to near zero.

### 2.3 COGS / Margin Model

| Scenario | COGS/user/month | Revenue/user/month | Gross Margin |
|---------|----------------|-------------------|-------------|
| Team (hosted LLM, 5 docs/user) | ~$1.50 (LLM) + ~$1 (infra) | $49 | ~95% |
| Team (hosted LLM, 15 docs/user) | ~$5 (LLM) + ~$1 (infra) | $49 | ~88% |
| Business (BYO-key) | ~$1 (infra only) | $149 | ~99% |
| Enterprise SaaS dedicated | ~$3 (infra, amortized) | $2,500–$6,700/seat eq. | ~99% |
| Enterprise on-prem | ~$0.50 (support amortized) | $2,500–$6,700/seat eq. | ~99% |

**Recommendation:** Keep Team tier doc cap at 50/month to protect margins while still converting prospects. Upsell signal: when a team hits the cap, sales gets an automated trigger.

---

## 3. Enterprise Feature Gap → Requirements

The gaps below are ordered by: **P0 = must resolve before first paying customer, P1 = required to close enterprise deals, P2 = required for GA.**

| # | Requirement | Why Enterprises Require It | Priority | Effort |
|---|------------|---------------------------|---------|--------|
| **EF-01** | **Job queue + worker fleet (Celery + Redis)** | Current in-process threads die on restart; no HA possible; a single slow document blocks all users | P0 | L |
| **EF-02** | **Rate limiting (per-user, per-endpoint)** | A single misbehaving user can DoS the API today; required before any public-facing sale | P0 | S |
| **EF-03** | **Stateless API (move stream registry + job state to Redis)** | Horizontal scaling impossible while in-memory state exists; also, session survivability on deploy | P0 | M |
| **EF-04** | **BYO-LLM / BYO-key** | Enterprise customers will not send confidential documents to your cloud LLM account | P0 | S (mostly already there — formalize in pricing/UX) |
| **EF-05** | **Secrets management (not raw .env)** | Raw .env in a container image or repo is a SOC 2 audit failure; use AWS Secrets Manager / Vault / K8s secrets | P0 | S |
| **EF-06** | **Postgres backup + tested restore** | No backup = no SLA; enterprise procurement asks for DR RPO/RTO | P0 | S |
| **EF-07** | **Basic observability (structured logs, metrics, error alerting)** | Ops team needs to know when something breaks before the customer does | P0 | M |
| **EF-08** | **Automated tests + CI/CD** | Evidence of a software quality process; also enables safe iteration once customers are live | P0 | M |
| **EF-09** | **SSO — OIDC (Google, Azure Entra)** | IT will reject any SaaS tool that requires password-only accounts for employees | P1 | M |
| **EF-10** | **MFA (TOTP)** | Security baseline; most enterprise security policies mandate it for any external tool | P1 | S |
| **EF-11** | **Audit log** | "Who uploaded/deleted/queried which document, when" — required for SOC 2 CC6 and legal hold; also a customer trust feature | P1 | M |
| **EF-12** | **Multi-tenancy (orgs + workspaces)** | Multiple teams/departments must be isolated; data must not bleed across business units or clients | P1 | L |
| **EF-13** | **Granular RBAC + permissions** | Workspace-level read/write/admin; per-document sharing; current flat roles insufficient for enterprise | P1 | M |
| **EF-14** | **Admin console (UI)** | Self-service user provisioning, usage dashboards, quota management — reduces support burden; IT/admin expectation | P1 | M |
| **EF-15** | **SSO — SAML 2.0** | Required by large enterprise IT (Okta, Ping, ADFS don't always do OIDC); gating item for legal/gov deals | P1 | M |
| **EF-16** | **SCIM provisioning** | Automated user lifecycle: users added/removed in IdP automatically propagate; IT will not manually manage accounts | P1 | M |
| **EF-17** | **Horizontal scaling** | Without it, no SLA commitment is credible; required as customer count grows | P1 | L (depends on EF-01/EF-03) |
| **EF-18** | **Usage metering + quotas + billing integration** | Track docs processed per org, enforce seat/doc limits, trigger upsell alerts, integrate with Stripe/billing | P1 | L |
| **EF-19** | **On-prem / air-gapped deployment package** | Legal, defense, pharma won't use cloud; this is the product's biggest differentiation; needs Helm chart + ops runbook | P1 | L |
| **EF-20** | **API + webhooks** | Enterprise customers integrate KnowledgeBook into existing workflows (SharePoint, Confluence, internal portals) | P1 | M |
| **EF-21** | **Data isolation + residency options** | GDPR requires EU data stays in EU; some customers demand single-tenant Postgres | P2 | L |
| **EF-22** | **GDPR DPA (Data Processing Agreement)** | Required for any EU customer to legally sign a contract; relatively low effort | P2 | S |
| **EF-23** | **Encryption at rest (Postgres + S3/blob)** | Security baseline; SOC 2 CC requirement | P2 | S |
| **EF-24** | **SOC 2 Type II** | Most enterprise procurement gates require it; 12-month observation window — start now | P2 | L (time-gated) |
| **EF-25** | **HIPAA BAA** | Enables healthcare deals; adds to total addressable market | P2 | M (after SOC 2) |
| **EF-26** | **Pen test + vulnerability disclosure policy** | Enterprise security teams will ask for it; also surfaces real issues before a breach does | P2 | M |
| **EF-27** | **Category-based document management with per-category ACL** | Enterprise governance requires least-privilege access: users should see only the documents relevant to their role/matter/project. Without categories, every user sees every document — unacceptable in legal (ethical walls), consulting (client separation), and compliance (regulatory product-line isolation) | P1 | M |
| **EF-28** | **User-selectable LLM model with free default and paid premium tiers** | Self-serve teams need a quality upgrade path without requiring an API key; enterprises need model governance (restrict which models their org uses and how they are paid for). The free local model is the on-ramp; premium cloud models are the monetized upsell for accuracy-critical work. | P1 | M |

**Effort key:** S = 1–2 weeks, M = 3–6 weeks, L = 6–12 weeks (including design, test, rollout).

### 3.1 EF-27: Category-Based Document Management — Full Design

#### Why enterprises require it

Today KnowledgeBook has a flat document library: every authenticated user (analyst/viewer) can see every document in the deployment. This is acceptable for a single-user trial but fails the moment a second team exists.

For the legal due-diligence wedge, a **category is a deal room or matter folder**: "Project Phoenix M&A", "Litigation: Smith v. Jones", "Regulatory Filing Q3". Associates working on Matter A must not see Matter B — this is not just a preference, it is an ethical wall enforced by bar rules. For consulting firms it is client confidentiality. For pharma it is regulatory product-line separation.

Categories also unlock **collaborative upload**: multiple analysts can contribute documents to the same matter without giving each other access to unrelated matters.

#### Permission model

**Global roles remain unchanged** (admin / analyst / viewer). They determine what a user CAN be granted, but do not implicitly grant category access.

**Category-level grants are additive and hierarchical:**

| Grant | What it allows |
|-------|---------------|
| `view` | See the category; list its documents; read Brief/Graph/Chat; use source PDF viewer |
| `upload` | Implies `view` + can upload new documents into the category |
| `manage` | Implies `upload` + can add/remove user grants on this category (delegated category manager) |

**Authorization rules:**
- Global `admin` is always a super-user: sees and manages all categories without needing a grant.
- All other users: default-deny. No grant on a category = category does not exist from their perspective (not even the name is visible).
- A category grant can exceed the user's global role (e.g., a globally-viewer user with an `upload` grant on a specific category may upload to it). Category grants are targeted elevations.
- A `manage`-grant holder can add/modify grants for other users up to their own level, but cannot self-elevate or grant `manage` to others — only admins can issue `manage` grants.

**v1 scope:** grants are per-user only. Role-level grants ("all analysts get `view` on General") are deferred to v2 — they add significant complexity and are not required to land the first enterprise deal. Decide this now (see D8).

**Relationship to EF-12 and EF-13:** EF-27 is an extension of EF-13 (granular RBAC) but has its own ID because it introduces a new authorization model (resource-scoped ACL on a new object type) and a new data model. It has a soft dependency on EF-12 (multi-tenancy/orgs): in a single-tenant deployment, categories exist globally; once EF-12 lands, `category.org_id` scopes them per-org. EF-27 can ship before EF-12.

#### Data model

```sql
-- New table: categories
CREATE TABLE categories (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      UUID REFERENCES orgs(id) ON DELETE CASCADE,  -- null until EF-12; required after
  name        TEXT NOT NULL,
  description TEXT,
  created_by  UUID NOT NULL REFERENCES users(id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(org_id, name)
);

-- New table: per-category grants
CREATE TABLE category_permissions (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id  UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
  subject_type TEXT NOT NULL CHECK (subject_type IN ('user', 'role')),
  subject_id   TEXT NOT NULL,   -- user UUID (as text) or role name
  grant_type   TEXT NOT NULL CHECK (grant_type IN ('view', 'upload', 'manage')),
  granted_by   UUID NOT NULL REFERENCES users(id),
  granted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(category_id, subject_type, subject_id)
  -- one row per subject per category; manage implies upload implies view (enforced in application layer)
);

-- Alter existing jobs table
ALTER TABLE jobs ADD COLUMN category_id UUID REFERENCES categories(id) ON DELETE RESTRICT;
```

**Migration / backfill (zero downtime):**
1. Create a system-generated `"General"` category (owned by the seeded admin).
2. `UPDATE jobs SET category_id = <general_category_id> WHERE category_id IS NULL`.
3. For every existing non-admin user: insert a `category_permissions` row granting `upload` on `"General"`. This exactly preserves pre-migration behavior — everyone can see and upload to the general pool.
4. Make `jobs.category_id NOT NULL` in a subsequent migration once all rows are backfilled.

#### API additions and enforcement

**New category management endpoints (all authenticated):**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/categories` | admin only | Create category |
| `GET` | `/api/categories` | any user | Returns only categories with view+ grant (admin: all) |
| `PUT` | `/api/categories/{id}` | admin only | Rename / update description |
| `DELETE` | `/api/categories/{id}` | admin only | Returns 409 if documents exist — never cascade-delete |
| `GET` | `/api/categories/{id}/permissions` | admin or manage-grant | List grants |
| `POST` | `/api/categories/{id}/permissions` | admin or manage-grant | Add/update grant for a user |
| `DELETE` | `/api/categories/{id}/permissions/{perm_id}` | admin or manage-grant | Revoke grant |

**Modified endpoints — category ACL enforcement (server-side, no exceptions):**

Every existing job-scoped route must enforce category access. The recommended implementation pattern is a single FastAPI `Depends` function `require_category_grant(job_id, min_grant: Literal["view","upload","manage"])` that: resolves `job.category_id`, queries `category_permissions` for the calling user, and raises `HTTP 403` if the grant is insufficient. Apply this dependency to every route in `chat_routes.py`, `job_routes.py`, and any PDF/brief/graph endpoint.

| Modified endpoint | Required grant |
|------------------|---------------|
| `POST /api/jobs` (upload) | `upload` on the supplied `category_id` |
| `GET /api/jobs` (list) | filter results to categories with `view+` |
| `GET /api/jobs/{id}` | `view` on job's category |
| `GET /api/jobs/{id}/brief` | `view` |
| `GET /api/jobs/{id}/graph` | `view` |
| `GET /api/jobs/{id}/pdf` | `view` |
| `POST /api/jobs/{id}/chat` | `view` |
| `GET /api/jobs/{id}/chat/*/stream` | `view` (check at session creation, not just stream time) |
| `GET /api/jobs/{id}/chat/history` | `view` |

**UI additions:**
- Document library: left sidebar showing the user's accessible categories. Clicking a category filters the document list.
- Upload dialog: category selector (only categories where user has `upload` grant; no selector shown if only one category is accessible).
- Admin console: "Categories" tab — create/rename/delete; member list with grant-level selector (view / upload / manage).
- Document card: category badge for visual orientation.

#### Risks and edge cases

**1. Default-deny is non-negotiable.** If a user has no grant on a category, they must see nothing from it — not the category name, not a document count, not a chat snippet. Any partial exposure is a governance failure. Test this explicitly with a user who has zero grants.

**2. Category deletion with documents inside.** Return `HTTP 409 Conflict` with the count of documents. Admin must either delete the documents or reassign them to another category first. Never cascade-delete documents when a category is deleted — this would permanently destroy user work.

**3. Cross-category chat leakage.** Chat grounding is per-document graph only (the graph is stored per-job, not shared across documents). There is no mechanism for a document in Category A to leak context into a chat session for a document in Category B. The enforcement risk is only a missed `require_category_grant` call on a chat endpoint — the single-dependency pattern eliminates this.

**4. Grant revocation and existing chat sessions.** When a user's grant is revoked, their existing chat session for a document in that category must become inaccessible immediately. Check grant at session-load time (on every `/chat/history` and `/chat/stream` call), not just at session-creation time.

**5. Privilege escalation via manage-grant.** A `manage`-grant holder can add users at `view` or `upload` level. They cannot issue `manage` grants — only admins can. Enforce this server-side: if the caller is not admin and the requested `grant_type` is `manage`, return 403.

**6. Admin-only category creation.** The `manage` grant covers membership management for an existing category, not category creation. Only admins create (and delete) categories. This prevents category proliferation and ensures the admin governs the taxonomy.

#### Effort and placement

**Effort: M (3–5 weeks)**
- Week 1: data model + Alembic migration + backfill + `require_category_grant` FastAPI dependency
- Weeks 1.5: enforce on all backend endpoints + category CRUD API
- Weeks 1.5: frontend (category sidebar, upload selector, admin tab)
- Week 0.5: integration tests + migration dry-run on production copy

**Priority: P1** — not a hard blocker for the very first Team/Business sale to a single team, but a gate for any enterprise sale involving multiple teams, practice groups, or client matters. For the legal design-partner cohort specifically, this is likely to come up in the first conversation.

**Optional early subset (Phase 0-adjacent, ~2 weeks):** A simplified v1 with no `manage` grant and no delegation — admins create categories, admins assign view/upload per user. No self-service. This is sufficient for the first design partner's deal-room use case and can be built before Phase 1 multi-tenancy if the partner requests it.

### 3.2 EF-28: User-Selectable LLM Model — Full Design

#### Restated requirement and why it matters

Today the LLM used for extraction and chat is set by the operator via environment variables — a global, all-users-get-the-same-model setting. There is no user-facing choice. This creates two problems:

1. **Self-serve users (Team tier)** have no way to get better results without the operator reconfiguring the entire platform. The default local 3B model is free but weak; users have no upgrade path short of the operator switching everyone to a paid provider.
2. **Enterprise admins** need model governance: control which models their org is allowed to use, set per-org defaults, and enforce whether users pay via platform credits or their own API keys.

The business case is a **freemium conversion lever**: the free local model is the on-ramp that gets users in the door; premium cloud models (Claude, OpenAI) are the "this is so much better" upgrade that converts free users to paying and paying users to higher tiers.

The honest answer to "why would I pay?" is grounded in the quality risk already documented in Section 6: `qwen2.5:3b` frequently ignores grounding constraints and hallucinates. Claude or GPT-4o follow those constraints reliably. Model choice is therefore not a feature preference — it is the primary trust upgrade.

#### Recommended monetization model: Hybrid

Do not abandon the BYO-key recommendation from D3. Instead, extend it with a credits path for Team-tier users who do not have API keys.

| Tier | Premium model access | How they pay |
|------|---------------------|-------------|
| **Team** | Available via **platform credit packs** (you mark up the API cost) | Purchase credits through the platform (Stripe); credits deducted per premium extraction or chat session |
| **Business** | Available via **BYO API key** per org; admin stores their Anthropic/OpenAI key | They pay their provider directly; zero LLM COGS for you |
| **Enterprise** | BYO-key required; admin may also enforce "BYO-key only" policy to block credits | They pay their provider directly; admin governs which models are permitted |

**Why hybrid and not credits-everywhere or BYO-everywhere?**
- Credits for Business/Enterprise would require you to mark up on a tier where customers actively compare your prices to direct API costs — a margin and trust problem.
- BYO-key for Team/self-serve requires users to have an Anthropic or OpenAI account before they see value — kills the on-ramp. Credits remove that friction.
- Hybrid gives each tier the right incentive structure.

**Credit pricing hypothesis (validate with first 5 customers):**

| Credit pack | Price | Credits included | Effective $/credit |
|------------|-------|-----------------|-------------------|
| Starter | $10 | 15 credits | $0.67/credit |
| Standard | $25 | 45 credits | $0.55/credit |
| Pro | $50 | 100 credits | $0.50/credit |

**Credit cost per model (per document extraction):**

| Model | API cost estimate (300pp doc) | Credits charged | Your margin |
|-------|------------------------------|----------------|-------------|
| qwen2.5:3b (local) | ~$0 | 0 (free) | — |
| claude-3-haiku | ~$0.15 | 1 credit (~$0.55) | ~73% |
| claude-3-5-sonnet | ~$0.45 | 2 credits (~$1.10) | ~59% |
| gpt-4o | ~$0.50 | 2 credits (~$1.10) | ~54% |

Premium chat sessions cost 0.1 credit per message (10 messages = 1 credit equivalent). These margins are directionally right — validate against real usage before locking in.

**Credit balance check before dispatch:** Check balance BEFORE starting any premium job. If insufficient credits, return an error (never silently downgrade to the local model — that would feel like a bait-and-switch and destroy trust). The existing per-document cost cap in dollars translates to a credit pre-flight check for premium jobs.

#### Model quality map (shown in the UI)

The model picker must show more than just a model name — it must show the tradeoff in terms users understand:

| Model | Label | Quality | Speed | Cost |
|-------|-------|---------|-------|------|
| qwen2.5:3b (local) | Free — Basic | Weaker grounding; may hallucinate | Variable (local hardware) | Free |
| claude-3-haiku | Good — Fast | Reliable grounding | Fast | 1 credit/doc |
| claude-3-5-sonnet | Best — Balanced | Excellent grounding; recommended for legal/compliance | Medium | 2 credits/doc |
| gpt-4o | Best — Alternative | Excellent grounding | Medium | 2 credits/doc |

Display a quality warning inline when the free model is selected: "Free model may produce less accurate results. Upgrade to a premium model for legal or compliance use."

#### Where model choice is exposed and gated

**Per-job (extraction model):** Model selector in the upload dialog, displayed as "Extraction quality" with the quality/cost labels above. Defaults to the org-configured default (or the free model if no policy is set). Available models filtered to what the user's tier + org policy allows.

**Per-chat session (chat model):** Model selector in the Chat tab header. Independent from the extraction model — a user may extract with claude-sonnet for a high-quality graph, then chat with the free model to avoid spending more credits. Or vice versa. Both choices are stored.

**Admin model policy (per org):** Admin sets (a) the allowed models list for the org, (b) the default extraction and chat model, (c) whether users must use BYO-key (blocking credits). This is the governance layer that lets an Enterprise admin say "all extraction must use claude-sonnet via our BYO key; no other model is permitted."

#### Data model additions

```sql
-- Extend existing jobs table
ALTER TABLE jobs ADD COLUMN extraction_model TEXT;    -- model slug: 'qwen2.5:3b', 'claude-3-5-sonnet', etc.
ALTER TABLE jobs ADD COLUMN llm_provider    TEXT;    -- 'ollama'|'claude'|'openai'
-- chat_messages.model already exists — no change needed

-- New: per-org model governance
CREATE TABLE org_model_policies (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                    UUID REFERENCES orgs(id) ON DELETE CASCADE,  -- null = platform-wide default
  allowed_models            TEXT[] NOT NULL DEFAULT ARRAY['qwen2.5:3b'],
  default_extraction_model  TEXT NOT NULL DEFAULT 'qwen2.5:3b',
  default_chat_model        TEXT NOT NULL DEFAULT 'qwen2.5:3b',
  require_byo_key           BOOLEAN NOT NULL DEFAULT false,
  -- if true, credits not accepted; premium use requires a stored BYO-key
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- New: credit ledger (Team tier; pairs with EF-18 usage metering)
CREATE TABLE credit_ledger (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES orgs(id),
  user_id           UUID NOT NULL REFERENCES users(id),
  amount            NUMERIC(10,4) NOT NULL,       -- positive = purchase/grant, negative = spend
  credit_type       TEXT NOT NULL CHECK (credit_type IN ('purchase','spend','refund','admin_grant')),
  model_used        TEXT,
  job_id            UUID REFERENCES jobs(id),
  chat_message_id   UUID REFERENCES chat_messages(id),
  external_charge_id TEXT,                        -- Stripe PaymentIntent ID
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Balance: SELECT COALESCE(SUM(amount),0) FROM credit_ledger WHERE org_id = ?

-- New: BYO API keys per org (Business/Enterprise; encrypted at rest)
CREATE TABLE org_api_keys (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  provider      TEXT NOT NULL CHECK (provider IN ('openai','claude')),
  encrypted_key BYTEA NOT NULL,  -- AES-256-GCM; encryption key from KMS/Vault (never in DB)
  key_hint      TEXT,            -- last 4 chars for display ("...ab3f") — never the full key
  created_by    UUID NOT NULL REFERENCES users(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(org_id, provider)
);
```

**Interaction with existing per-document cost cap:** The cost cap in the `jobs` table currently tracks dollar spend. Extend it: for credit-mode jobs, also check `credit_balance >= estimated_credits_for_model` at job creation time. Add `credits_charged NUMERIC` to `jobs` for ledger reconciliation.

#### API additions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/models` | any authenticated | Returns available models for caller (filtered by tier + org policy + credit balance + deployment mode) |
| `POST` | `/api/orgs/{id}/model-policy` | admin | Set allowed models, defaults, BYO-key requirement |
| `GET` | `/api/orgs/{id}/credits` | admin or self | Current credit balance + recent ledger entries |
| `POST` | `/api/orgs/{id}/credits/purchase` | admin or self | Initiate Stripe Checkout for a credit pack (ties to EF-18) |
| `POST` | `/api/orgs/{id}/api-keys` | admin | Store encrypted BYO API key; validates key against provider before storing |
| `DELETE` | `/api/orgs/{id}/api-keys/{provider}` | admin | Revoke BYO key |
| `GET` | `/api/orgs/{id}/usage` | admin | Usage breakdown by model, user, date (ties to EF-18) |

**Modified endpoints:**
- `POST /api/jobs` — accept optional `model` parameter; validate against org policy + credits/BYO-key; store `extraction_model` + `llm_provider` on job row; pre-flight credit check.
- `POST /api/jobs/{id}/chat` — accept optional `model` parameter for chat session; validate; store on message row.

#### Config delivery — DB-resolved per request, no restart (see D14)

Per-user model selection **must not** be driven by environment variables. The current `CHAT_PROVIDER` / `CHAT_MODEL` are read at container boot, so any change needs a restart — unacceptable when many users each choose their own model live.

**The rule: configuration-as-data, resolved on every request.** All model/policy/credential state lives in Postgres and is read per request; the existing `get_provider(provider, model, api_key)` factory already accepts a per-call model override, so this is a routing change, not a new abstraction.

- **Resolution precedence** (per request): explicit request `model` → `user_settings` default → `org_model_policies` default → system default (free local `qwen2.5:3b`). Validate against `org_model_policies` (allowed + `require_byo_key`); resolve credentials from `org_api_keys` (BYO, decrypted) or the secret store (platform).
- **No reload:** an admin editing `model_catalog`/policy, or a user changing their pick, is a DB write that takes effect on that user's **next request** — no restart, no redeploy. This also retires the legacy "edit `.env` → restart" behaviour.
- **At scale (many users, multi-replica):** cache `model_catalog` + `org_model_policies` with a 30–60s TTL and invalidate via **Redis pub/sub** (the same Redis introduced for EF-01/EF-03) for instant, fleet-wide propagation; all replicas read the same DB so behaviour is consistent. This is precisely the stateless-config shape EF-03 requires.

#### Effort and roadmap placement

**Effort: M (4–6 weeks total), but splits cleanly into two deliverable slices:**

**Slice A — Model picker + org policy + BYO-key storage (no credits):** S/M, 2–3 weeks. Unlocks Business/Enterprise model governance and BYO-key per org immediately. No payment integration needed.

**Slice B — Credit system (purchase + ledger + balance enforcement):** M, 3–4 weeks. Required for Team-tier premium model access. Pairs with EF-18 (billing integration).

**Priority:** P1. Slice A can ship early in Phase 1 (pairs with BYO-key formalization EF-04 and org policy EF-12). Slice B pairs with EF-18 billing.

#### Risks and edge cases

**1. Cost runaway on platform-provided keys.** Pre-flight credit balance check is non-negotiable. The sequence must be: check balance → reserve credits → dispatch job → deduct on completion. Do NOT deduct speculatively; do NOT allow dispatch without reservation. A failed/aborted job returns the reserved credits to balance.

**2. BYO-key secret storage.** Encrypt at rest with AES-256-GCM; encryption key stored in KMS/Vault, NOT in the database. Store only the key hint (last 4 chars) for display. Validate the key against the provider API on entry — reject invalid keys immediately, never store them silently. Log key creation/revocation in audit log (EF-11) without logging the key itself.

**3. Per-model availability and rate limits.** Claude/OpenAI can throttle or experience outages. Error response must be "model temporarily unavailable — please retry or choose another model." Never silently fall back to the local model; that would deliver wrong-quality results the user did not choose.

**4. Air-gapped / on-prem deployments.** Premium cloud models are unreachable in an air-gapped environment. Detect via `AIRGAP_MODE=true` env flag. `GET /api/models` returns only local models in this mode. No credit system UI is shown. No BYO-key UI for cloud providers. This is the correct behavior — on-prem customers chose local for a reason.

**5. Extraction model vs. chat model coupling.** These are independent decisions; do not force them to match. A user extracting with claude-sonnet (to get a high-quality graph) and chatting with qwen2.5:3b (to save credits) is a valid and economically rational choice. The graph is already extracted — chat quality depends only on the chat model.

**6. Setting user expectations.** The model picker must show quality, speed, and cost — not just a model slug. "qwen2.5:3b" means nothing to a paralegal. "Free — Basic accuracy (may miss nuance in legal language)" is actionable. Display a quality caveat inline when the free model is selected, especially if the document was uploaded for legal or compliance use.

**7. Credit abuse and account sharing.** Tie credit balance to org (not individual users) so sharing within the org is allowed but cross-org sharing is not. Rate-limit premium model requests per org per hour. Require verified Stripe payment before any credit purchase — no trial credits for premium models (the free local model IS the trial).

### 4.1 Must Change Before First Paying Customer

**1. Replace background threads with a proper job queue (EF-01 — highest priority item in the entire list).**
The current architecture runs PDF ingestion in Python background threads inside the FastAPI process. A server restart loses every running job with no recovery. This is incompatible with any paid customer.
- Use Celery + Redis (or RQ + Redis). Celery is recommended: mature, documented, battle-tested.
- Benefits: jobs survive restarts, retries are durable, worker fleet can scale independently, no state lost.
- Effort: L. This is the biggest single engineering investment before first sale.

**2. Stateless API (EF-03).**
The SSE stream registry (stream token → active generator) is in-process memory. Move it to Redis pub/sub or a Redis hash. This enables multiple API replicas.

**3. Rate limiting (EF-02).**
Add per-user per-endpoint rate limits before any public-facing URL exists. Use `slowapi` (Redis-backed) or nginx rate limit at the ingress. Minimum: 10 requests/minute on chat, 5 document uploads/hour per user.

**4. Secrets out of .env (EF-05).**
In production: use environment injection via Docker secrets, AWS Secrets Manager, or Vault. Never store secrets in a file committed to or shipped with the container. Document this explicitly in the deployment guide.

**5. Postgres backup (EF-06).**
Daily automated snapshots with tested point-in-time restore. On AWS: RDS automated backups. On-prem: pg_dump cron + offsite copy. Document RPO (24h) and RTO (4h) as initial SLA targets.

**6. Basic observability (EF-07).**
Minimum viable: structured JSON logs (already have stage logs), a `/metrics` endpoint (prometheus-fastapi-instrumentator), and an alert when error rate > 5% or job failure rate > 20%. Use Grafana Cloud free tier initially.

**7. Automated tests (EF-08).**
Minimum: integration tests covering the full ingestion pipeline on a 5-page test PDF, auth token lifecycle (login/refresh/logout), chat stream (unit), and RBAC enforcement on key endpoints. Target: green CI on every merge.

### 4.2 Before GA Enterprise

**Horizontal scaling:** Once EF-01/EF-03 are done, the API tier is stateless. Add a load balancer (nginx or ALB) in front of 2+ API replicas. Worker fleet scales independently via Celery `--concurrency`. Add auto-scaling triggers on queue depth.

**HA Postgres:** RDS Multi-AZ or Patroni. Minimum for a 99.5% SLA commitment.

**Security hardening:**
- Enforce TLS everywhere (terminate at load balancer, even internal connections).
- Encrypt Postgres at rest (RDS default; on-prem: LUKS or Postgres TDE).
- Encrypt S3/blob storage (SSE-S3 or SSE-KMS).
- Rotate JWT signing keys on a schedule.
- Add CORS policy that restricts to known frontend origins.
- Pin Docker base images; scan with Trivy in CI.

**SOC 2 Type II — start the 12-month clock as early as possible.** The observation period is time-gated; no amount of engineering investment accelerates it once started. Recommended: engage an auditor (Vanta, Drata, or Secureframe for assisted compliance) in Month 2 and start the observation period. Budget $15k–$30k/year for the audit + tooling.

### 4.3 SLO Targets (GA)

| SLO | Target | How Measured |
|-----|--------|-------------|
| API availability | 99.9% monthly | Uptime Robot or Datadog synthetic |
| Ingestion job success rate | 95% of submitted jobs reach READY | Celery task success metric |
| Chat response time (p95) | < 8s first token | SSE stream timing metric |
| Document ingestion latency (p90) | Digital ≤5min, scanned ≤15min | Job state transition timestamps |
| Error rate (API 5xx) | < 0.5% of requests | nginx/API metrics |

---

## 5. Deployment Models

### 5.1 Three Options

**A. SaaS Multi-tenant**
- You host everything; customers get a login.
- Fastest time to market. Lowest customer ops overhead. Shared infrastructure, lower per-customer cost.
- Problem: hardest to sell to regulated industries (legal, pharma, defense). Requires SOC 2 before enterprise deals.
- Best for: Team + Business tiers.

**B. SaaS Single-tenant / Dedicated Cloud**
- Customer gets their own isolated deployment on your cloud (separate DB, separate workers, separate domain).
- Premium pricing ($40k+/year). You manage it; they get full isolation. Good middle ground before on-prem.
- Works for: Enterprise tier customers who trust cloud but need isolation.

**C. Self-hosted / On-premises / Air-gapped**
- Customer installs on their own infrastructure. They manage it; you provide the package.
- Highest deal value ($50k–$150k/year + professional services for install). Zero LLM COGS (customer runs local Ollama or their own model).
- **This is the product's strongest differentiator.** The architecture is already local-first; docker compose already runs on a single host.
- For air-gapped: package as a tarball + helm chart + offline model weights. No internet required.

### 5.2 Recommendation

**Lead with SaaS multi-tenant for Team/Business. Offer dedicated or on-prem as the Enterprise option from day one in sales conversations.**

Do not wait until you have 20 SaaS customers before building the on-prem story. Regulated-industry deals take 3–6 months and often start with "can this run on our network?" as the first question. The answer needs to be "yes" with a concrete deployment guide in hand.

**Immediate actions:**
1. Package the current docker-compose into a versioned release artifact with a documented deployment guide.
2. Create a helm chart (or docker-compose production-ready variant) for the on-prem offering.
3. Test the full stack in a fully air-gapped environment (no outbound internet) with a local Ollama model.

---

## 6. Grounding Quality as a Product Risk

### 6.1 The Problem

KnowledgeBook's chat is grounded on the extracted knowledge graph — not on raw text chunks. This is a strength (structured, citeable) and a limitation (no prose fidelity; cannot quote verbatim text; answers are only as good as what was extracted).

The second problem is the default model: `qwen2.5:3b` is a weak model that frequently ignores system-prompt instructions to "use only the provided context." In practice, it hallucinates. This is acceptable for local offline use; it is **fatal for an enterprise demo or paid customer.**

### 6.2 When Does This Matter?

| Use Case | Graph-only Quality | Acceptable? |
|---------|-------------------|-------------|
| "What are the 5 key concepts?" | High — well-extracted | Yes |
| "Summarize chapter 3" | Medium — depends on extraction coverage | Yes (with caveats) |
| "What does the contract say about termination for cause?" | Low — needs verbatim prose | **No for legal use** |
| "Is X drug contraindicated for Y condition?" | Low — needs precise clinical language | **No for pharma/medical** |
| "What is the author's argument about X?" | Medium-high — graph captures relationships | Acceptable |

### 6.3 Recommendations

**Immediate (before any demo or first customer):**
Switch the default LLM to Claude (claude-3-5-sonnet or claude-3-haiku for cost). Set `CHAT_PROVIDER=claude` in your standard deployment. Claude follows grounding instructions reliably. qwen2.5:3b does not. This is a one-line environment variable change with enormous impact on perceived quality.

**Q2 (before signing legal/compliance customers):**
Implement hybrid RAG. The existing architecture already planned for pgvector and chunk storage — this was deferred in the MVP, not abandoned. With hybrid RAG, the graph provides structure (concept map, relationships, chapter outline) and raw chunks provide prose fidelity (verbatim quotes, precise language). The chat API contract does not need to change; this is a grounding layer upgrade.

**Q3–Q4 (for on-prem customers who cannot use Claude):**
Fine-tuned local model for grounding. This is a significant investment (requires training data, GPU infrastructure) but is the only path to high-quality local-only inference. Alternatively, recommend `llama-3.1-8b` or `mistral-7b` as intermediate models superior to the 3B.

### 6.4 Market the Escape Hatch

The source PDF viewer + citation links are not a workaround; they are a differentiator. Market the "verify" affordance: "Every answer shows the chapter and page. Click it to see the source text." This positions KnowledgeBook's answer quality as inherently auditable, unlike competitors where you have to trust the black box.

---

## 7. Roadmap (MoSCoW + Phased)

### 7.1 Phase 0 — MVP for First Paying Customer (Now → Month 3)

**Goal:** Close first paid deal (Team or Business tier) with a law firm or consulting team.

| Priority | Item | Effort | Note |
|---------|------|--------|------|
| M | Job queue (Celery + Redis) [EF-01] | L | Ship-blocker |
| M | Rate limiting [EF-02] | S | Ship-blocker |
| M | Stateless API / Redis state [EF-03] | M | Ship-blocker |
| M | Switch default demo LLM to Claude | S | Immediate |
| M | Secrets management [EF-05] | S | Security baseline |
| M | Postgres backup + tested restore [EF-06] | S | SLA prerequisite |
| M | Basic observability [EF-07] | M | Ops baseline |
| M | Automated tests + CI/CD [EF-08] | M | Quality signal |
| M | BYO-key pricing + UX formalization [EF-04] | S | Pricing model |
| S | OIDC SSO (Google + Entra) [EF-09] | M | Accelerates Team/Business deals |
| S | Admin console v1 (user management only) [EF-14] | M | IT expectation |
| S | On-prem deployment guide + versioned release | M | Sales enablement |
| W | Multi-tenancy, SAML, audit log | — | Phase 1 |

**Phase 0 exit gate:** One paid customer, >0 documents processed in production, no job loss on deploy.

### 7.2 Phase 1 — Design Partner / Beta (Month 3–6)

**Goal:** 5–10 design partners using the product weekly; 3+ converted to paid enterprise deals.

| Priority | Item | Effort | Note |
|---------|------|--------|------|
| M | Multi-tenancy: orgs + workspaces [EF-12] | L | Gate for multi-team enterprise |
| M | SAML 2.0 SSO [EF-15] | M | Gate for large enterprise IT |
| M | SCIM provisioning [EF-16] | M | IT requirement |
| M | MFA (TOTP) [EF-10] | S | Security baseline |
| M | Audit log [EF-11] | M | SOC 2 prerequisite; customer trust |
| M | Granular RBAC + permissions [EF-13] | M | Multi-team isolation |
| M | Category-based document management + per-category ACL [EF-27] | M | Legal deal rooms; multi-team governance; pairs with EF-12/EF-13 |
| M | Model picker + org model policy + BYO-key storage — Slice A [EF-28] | S/M | Unlocks Business/Enterprise model governance; pairs with EF-04/EF-12 |
| M | Credit system for premium models on Team tier — Slice B [EF-28] | M | Self-serve upsell lever; pairs with EF-18 billing |
| M | Usage metering + quotas [EF-18] | L | Billing prerequisite |
| M | Hybrid RAG (pgvector + chunk storage) | L | Quality gate for legal/compliance |
| S | Horizontal scaling (multi-replica API + worker) [EF-17] | M (depends on P0) | HA prerequisite |
| S | API v1 + webhooks [EF-20] | M | Integration requirement |
| S | Admin console v2 (usage dashboards) [EF-14] | M | Self-service |
| S | GDPR DPA [EF-22] | S | EU customer prerequisite |
| S | Encryption at rest [EF-23] | S | SOC 2 prerequisite |
| W | SOC 2 observation period started | — | Start clock |

**Phase 1 exit gate:** 3 design partners processed >20 documents each; SAML login works; multi-tenancy tested with 2 separate org datasets.

### 7.3 Phase 2 — GA Enterprise (Month 6–12)

**Goal:** Open sales motion; 5+ enterprise contracts signed ($30k+ ARR each).

| Priority | Item | Effort | Note |
|---------|------|--------|------|
| M | SOC 2 Type II (observation complete) [EF-24] | L (time-gated) | Enterprise procurement gate |
| M | Pen test + vulnerability disclosure [EF-26] | M | Enterprise security review |
| M | On-prem / air-gapped Helm chart + runbook [EF-19] | L | Differentiator for regulated industries |
| M | Data residency options [EF-21] | L | EU/GDPR; regional cloud |
| M | Billing integration (Stripe) | M | Self-service purchase |
| S | HIPAA BAA [EF-25] | M | Healthcare vertical |
| S | ISO 27001 (if targeting EU enterprise) | L | EU procurement |
| S | Fine-tuned local grounding model | L | On-prem quality uplift |
| S | Multi-document graph | L | Product expansion (Phase 3 PRD) |

### 7.4 The 5 Decisions That Most Shape the Plan

These are the decisions to make in the next 4 weeks. Wrong calls here create 3–6 month delays.

1. **Cloud-first vs. on-prem-first.** If your first design partners are in regulated industries (legal, defense, pharma), you must deliver an on-prem story in Phase 0, not Phase 2. If they are in consulting or corporate strategy, SaaS is fine. Pick your first ICP now and sequence accordingly.

2. **BYO-key required from Business tier up (yes or no).** Recommended: yes. Postponing this means absorbing LLM COGS at scale, which kills margins. Formalize BYO-key in the pricing page and onboarding flow immediately.

3. **Hybrid RAG timing.** If you plan to sell to legal or compliance teams, hybrid RAG must be in Phase 1, not Phase 2. Graph-only chat is insufficient for "what exactly does clause 8.3 say" queries. Decide now: commit to Phase 1 hybrid RAG or explicitly exclude legal/compliance from Phase 1 targeting.

4. **SOC 2 start date.** Every month you delay starting the observation period is a month of delay to your first enterprise deal that requires it. Start the clock in Month 2. Engage Vanta or Drata to speed up control implementation.

5. **Vertical focus for first 10 customers.** Legal due diligence is the recommended wedge (high pain, high willingness to pay, citations map directly to the product). Consulting is the runner-up (lower trust bar, faster sales cycles). Do not try to sell to pharma without hybrid RAG and HIPAA BAA in place. Choose one vertical and execute deeply rather than spreading thin.

---

## 8. Success Metrics & Go-to-Market

### 8.1 Product Metrics

| Metric | What It Measures | Target (6-month) |
|--------|-----------------|-----------------|
| **Activation rate** | % of signups who process ≥1 document in first session | ≥70% |
| **Chat engagement rate** | % of processed documents where user asks ≥1 chat question | ≥50% |
| **Time to first insight** | Minutes from upload to first chat question | ≤20 min (p50) |
| **Graph accuracy (sampled)** | % of extracted concepts rated accurate by domain expert review | ≥80% |
| **Trust score** | % of chat answers user does not flag as wrong | ≥85% |
| **Month-2 return rate** | % of Month-1 users who process a second document in Month 2 | ≥40% |
| **Seat expansion rate** | % of Team accounts that expand to Business or add seats in 6 months | ≥25% |
| **Document volume per user/month** | Engagement depth proxy | ≥5 docs/user |

### 8.2 Business Metrics

| Metric | Target (12-month) |
|--------|-----------------|
| Design partners (active, processing ≥5 docs/month) | 10 |
| Paying customers | 5+ |
| ARR | $150k+ |
| Avg deal size | $20k–$50k |
| CAC | <$5,000 for SMB, <$15,000 for enterprise |
| Gross margin (target) | ≥85% (achieved via BYO-key enforcement) |

### 8.3 GTM Motion

**Step 1: Design partners (now → Month 3)**
Identify 5–10 law firms, consulting firms, or corporate legal teams. Offer free access for 90 days in exchange for weekly 30-minute feedback calls and permission to use their success as a case study. Goal: product-market fit signal, testimonials, 3 paid conversions at end of trial. Specific targets: mid-size law firm M&A teams (50–200 lawyers), consulting firm knowledge management leads, pharmaceutical regulatory affairs managers.

**Step 2: Content-led inbound**
Build one case study per design partner (anonymized if needed). A concrete headline: "How [firm] analyzed a 400-page regulatory filing in 18 minutes instead of 6 hours." Distribute via LinkedIn (target: legal tech, knowledge management, BI/analytics communities) and legal tech newsletters (LegalTech Hub, Above the Law for tech buyers).

**Step 3: Conferences (Month 4–8)**
- ILTA (International Legal Technology Association) annual — the primary event for legal tech buyers.
- LegalWeek — enterprise legal buyers.
- SXSW Government / CES for gov/defense adjacency.

**Step 4: Land-and-expand**
A team of 5 lawyers becomes a department of 50. One department becomes an enterprise site license. Structure the Team tier to make it trivially easy for a champion to share their account with colleagues; make the upgrade to Business/Enterprise frictionless once the champion demonstrates value to a manager.

### 8.4 Top Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Demo hallucination destroys trust | High (if using Ollama 3B) | Critical | Switch demo default to Claude immediately |
| Enterprise procurement cycle (6–12 months) exceeds runway | Medium | High | Design partners with fast 90-day trial-to-paid pathway; target SMB legal first |
| Microsoft Copilot / Adobe AI adds graph-style citations | Medium | High | Accelerate on-prem story; graph + local = moat Microsoft cannot replicate |
| SOC 2 takes longer than expected | Low-Medium | High | Start Vanta/Drata onboarding in Month 2; block on nothing else |
| LLM COGS eats margins on Team tier | Medium | Medium | Cap at 50 docs/month; enforce BYO-key from Business tier |
| Hybrid RAG underdelivers on quality | Low | High | Prototype early (Month 2); fallback = explicit "verify in source" UX |
| Key person dependency (1–2 engineers) | High | High | Document architecture; write ops runbooks; hire second engineer before GA |

---

## 9. Key Open Decisions for the Founder

These are decisions only you can make. Each one gates a set of downstream work.

| # | Decision | Options | Recommendation | Deadline |
|---|---------|---------|---------------|---------|
| D1 | First ICP / vertical | Legal vs. consulting vs. pharma vs. gov | **Legal due diligence** — highest willingness to pay; citations = perfect fit | Week 1 |
| D2 | Cloud-first vs. on-prem-first | SaaS launch → later on-prem vs. on-prem-ready from day 1 | **On-prem-ready from day 1** (it's already mostly there); don't backtrack later | Week 1 |
| D3 | BYO-key enforcement level | Team = hosted LLM; Business+ = BYO-key required | **Yes — enforce BYO-key from Business tier up.** | Week 2 |
| D4 | Hybrid RAG timing | Phase 1 (Month 3–6) vs. Phase 2 (Month 6–12) | **Phase 1** if targeting legal/compliance. Phase 2 if targeting consulting only. | Week 2 |
| D5 | SOC 2 start | Start now vs. wait for first enterprise request | **Start now.** The clock doesn't run faster with more customers. | Month 2 |
| D6 | Celery/Redis vs. alternative job queue | Celery+Redis, RQ+Redis, Postgres-based (pg-boss) | **Celery+Redis** — most documented, scales to worker fleet easily | Week 2 |
| D7 | Design partner target profiles | 5–10 orgs — which specific firms/companies? | Build a list of 20 targets and begin outreach immediately | Week 2 |
| D8 | EF-27: user-level vs. role-level grants in v1 | User-level only (simpler) vs. also grant to global roles (e.g., "all analysts get view on General") | **User-level only in v1.** Role-level adds schema complexity and edge cases (role changes retroactively affect access); add in v2. Decide before writing the data model. | Phase 1 start |
| D9 | EF-27: category deletion policy when documents exist | Block with 409 (recommended) vs. soft-archive the category vs. force-migrate docs to a default category | **Block with 409.** Never auto-delete or auto-migrate documents. Admin must explicitly reassign or delete docs first. Data safety is non-negotiable. | Phase 1 start |
| D10 | EF-27: scope of the "manage" grant | Membership-only (add/remove user grants) vs. also includes rename/edit of the category itself | **Membership-only.** Category rename/delete = admin-only. This prevents a delegated manager from restructuring the taxonomy without admin oversight. | Phase 1 start |
| D11 | EF-28: premium model monetization model for Team tier | Credits+markup (platform charges) vs. BYO-key everywhere vs. hybrid (credits for Team; BYO-key for Business+) | **Hybrid.** Credits for Team removes the "go sign up for Anthropic first" friction that kills self-serve conversion. BYO-key stays for Business/Enterprise to protect margins and avoid price-comparison problems. | Phase 1 start |
| D12 | EF-28: expose model choice on chat in v1 or extraction-only first | Both extraction + chat in v1 vs. extraction-only (simpler) | **Both in v1.** `chat_messages.model` already stored; provider abstraction already has `CHAT_PROVIDER`/`CHAT_MODEL`; adding a per-session model param is trivial relative to extraction model routing. No reason to defer. | Phase 1 start |
| D13 | EF-28: credit pricing unit | Per-document (simple) vs. per-1k-tokens (precise) vs. abstract credit packs (user-friendly) | **Credit packs.** Token math is opaque to end users. Credit packs (e.g., 1 credit = 1 premium extraction or 10 premium chat messages) are simple to understand and easy to price-adjust without changing the UX. Store per-model credit cost in a config table to allow updates without code deploys. | Phase 1 start |
| D14 | EF-28/EF-03: how per-user model config is applied at scale **without a restart** | Env-driven (`CHAT_PROVIDER`/`CHAT_MODEL`, needs container restart) vs. **DB-resolved per request** (configuration-as-data) | **DECIDED — DB-resolved per request.** Per-user/per-org model choice, org policy, and credentials live in Postgres and are resolved on *every* request — precedence: explicit request pick → user default → org default → system default (free local `qwen2.5:3b`) — validated against `org_model_policies` (allowed models + credits/BYO-key). Env is only for bootstrap/system defaults; premium keys come from the secret store (platform) or encrypted DB (BYO). A change (admin edits `model_catalog`, or a user changes their pick) is a DB write that takes effect on the next request — **no reload, no redeploy**. At scale: cache `model_catalog`/policies with a 30–60s TTL and invalidate via **Redis pub/sub** (the same Redis introduced for EF-01/EF-03) for instant, fleet-wide propagation. This retires the current "edit `.env` → restart" limitation and is the required shape for the stateless multi-replica API (EF-03). | Phase 1 start |
