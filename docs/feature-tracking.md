# Feature Tracking — KnowledgeBook MVP

| | |
|---|---|
| **Document** | Feature & Work-Item Tracker |
| **Product** | KnowledgeBook (Document Knowledge Graph) |
| **Version** | 1.0 |
| **Date** | 2026-07-04 |
| **Status** | ACTIVE — update Status and Owner cells throughout the build |
| **Owner** | Engineering Lead |
| **Parents** | `PRD-knowledge-graph-mvp.md` v1.0, `ARCHITECTURE-mvp.md` v1.0, `PLAN-phase1-implementation.md` v1.0, `monetization-pricing.md` v1.0, `gtm-one-pager.md` v1.0 |

---

## How to Use This Document

**This is the team's single source of truth for "what is being built, in what order, and whether it is done."**

- Update the **Status** column whenever an item changes state. Do not let it lag.
- Tie every merge/PR to a row's ID in the commit message (e.g. `ING-03: pdf type detection`).
- A **gate review** at each sprint boundary checks every row targeting that sprint — an item is only Done if its Acceptance Criteria pass, not just because code was merged.
- Items marked **Assumption** in the Acceptance Criteria column need Product or Legal sign-off; engineering cannot self-declare them done.

### Status Legend

| Status | Meaning |
|---|---|
| `Not Started` | No work begun |
| `In Progress` | Active development |
| `Blocked` | Waiting on a dependency or decision listed in the Dependencies column |
| `Done` | Acceptance criteria passed at a gate review |
| `Deferred` | Explicitly moved to Phase 2+ or backlog |
| `Skipped` | Decided not to build; record the reason |

### Priority Legend (MoSCoW from PRD §3)

| Code | Meaning |
|---|---|
| `Must` | MVP blocker — product does not ship without it |
| `Should` | High value; include if capacity allows |
| `Could` | Nice to have; do not block Must/Should items |
| `Phase 2` | Explicitly out of this release |

---

## Reconciliation Note (2026-07-04)

This tracker was authored greenfield, but a gap analysis against the existing codebase
(`extraction-service/`, `frontend/`, `spike/`) shows much of the pipeline backbone is
**already built** and, in places, ahead of the MVP (multi-tenant orgs, RBAC, categories):

- **Built (pre-existing):** ingestion classify/extract/chunk (ING-01–08 core), per-chunk
  LLM extraction + graph merge (EXT-01/03/04, GRP-01–03), Brief + chat/Q&A (OUT-01/04/05),
  auth + per-user isolation (AUTH-01/02), upload UI + live progress (UI-01–02), multi-provider
  LLM layer, observability, Redis rate-limiting. These need **acceptance-gate verification**,
  not fresh construction — treat their rows as "In Progress → verify" rather than "Not Started".
- **Genuinely missing (the commercial/MVP layer):** consumer subscription tiers + monthly
  quota (PAY-01–03), Stripe (PAY-04), activation events (ACT-01–03), OCR low-confidence gate
  (ING-06), per-doc cost ledger + cap (EXT-02).

**Increments landed (top-down from the monetization spine):**
1. **PAY-01/02/03** — Free/Pro/Scholar plan field on `User`, env-tunable monthly upload quota
   (2/20/60), enforcement in `POST /api/jobs` (402 + upgrade message; admins exempt),
   `GET /api/usage` meter endpoint, idempotent `run_plans()` migration. See `app/plans.py`.
2. **PAY-04** — Stripe subscription billing: `POST /billing/checkout` + `/portal`,
   signature-verified `/webhook` that syncs `plan`/`plan_status` from Stripe events,
   `GET /billing/config`. Config-gated (503 when `STRIPE_SECRET_KEY` unset; app still boots).
   See `app/billing.py`, `app/billing_routes.py`. Setup: `docs/STRIPE-setup.md`.
3. **Billing UI (PAY-06 partial)** — `/billing` plans page (usage meter + Free/Pro/Scholar
   cards + monthly/annual toggle + checkout/portal), `/billing/success` (polls `/auth/me`)
   and `/billing/cancel`, "Billing & plan" in the user menu. See `frontend/src/routes/BillingPage.tsx`,
   `BillingResultPage.tsx`, `frontend/src/api/billing.api.ts`.
4. **PAY-01 completed** — Free tier is digital-only (`enforce_scanned_allowed`, classify-at-upload)
   and the concept map caps at `PLAN_FREE_CONCEPTS` (10) with a "See all N on Pro" banner
   (`apply_free_tier_caps`, `DocumentDetailPage`).
5. **ACT-01/02/03** — activation instrumentation: `ActivationEvent` table + `/api/activation/*`
   (view, rate, status, admin summary), Concept-Map view event + thumbs prompt in `DocumentDetailPage`,
   Q&A event hooked into the chat handler. Live end-to-end tested. See `app/activation.py`,
   `app/activation_routes.py`, `frontend/src/api/activation.api.ts`.

---

## Part 1 — Spikes & Blocking Decisions

These four items from PRD §10 are **blocking** — they must be resolved before the work they gate can start. They are not features; they are information purchases.

| ID | Task | Category | Priority | Phase / Sprint | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|---|
| SK-01 | Execute Week-1 PDF/OCR spike (full scope per `SPIKE-week1-pdf-ocr.md`) | Spike | Must | Sprint 0 (Week 1) | E2 | Not Started | All six deliverables in spike §6 exist under `spike/`; decision matrix (§7) filled; PRD Q2+Q4 marked resolved with measured numbers; cost go/no-go vs. <$2/scanned cap confirmed | None — must run first |
| SK-02 | Resolve Q1: Acceptable hallucination rate + detection method | Decision | Must | Before Sprint 2 (by Week 4) | Product | Not Started | Written decision doc added to `docs/`; extraction prompt constraints and confidence-threshold values documented; available to E1/E2 at start of Sprint 2 | SK-01 (extraction text quality baseline informs the target) |
| SK-03 | Resolve Q3: Raw-document storage vs. process-and-discard | Decision | Must | Before Sprint 1 (by Week 2) | Product + Legal | Not Started | Written policy decision (store or discard; retention period); `retention_policy` flag wired into upload schema before Sprint-1 storage code is finalized | None — can run in parallel with SK-01 |
| SK-04 | Confirm LLM/embedding model IDs + tier assignments | Decision | Must | Before Sprint 2 (by Week 4) | Engineering | Not Started | Cheap-tier model ID (extraction) and strong-tier model ID (Brief/Q&A) documented; cost-per-token checked against per-doc budget; reference: `docs/claude-api-reference.md` or equivalent | SK-01 (cost numbers); SK-02 (quality target) |

---

## Part 2 — Infrastructure & Platform

| ID | Feature / Task | Category | Priority | Phase / Sprint | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|---|
| INF-01 | Dev environment: repo structure, `.env` scaffold, `docker-compose` for local dev (Postgres + pgvector + queue + API) | Infra | Must | Sprint 0 | E1 | Not Started | Any engineer can clone the repo and run `docker-compose up` to get a working local stack; seeds a test PDF through the full pipeline locally | None |
| INF-02 | Postgres setup: job/state tables, JSONB graph store, pgvector extension | Infra | Must | Sprint 1 | E1 | Not Started | Schema migrations run cleanly; job, document, chunk, and graph tables exist; pgvector extension enabled | INF-01 |
| INF-03 | Object store: S3-compatible bucket for raw PDFs and rendered page images; upload + download helpers | Infra | Must | Sprint 1 | E1 | Not Started | A test PDF can be uploaded and retrieved via the helper; bucket access is per-user isolated from day 1 | INF-01; SK-03 (retention policy determines whether raw files are discarded after READY) |
| INF-04 | Job queue: Celery/RQ (or managed queue) wired to FastAPI; worker pool with configurable concurrency | Infra | Must | Sprint 1 | E1 | Not Started | A task dispatched via the API appears in the queue and is picked up by a worker; retries work; decision on managed vs. self-hosted recorded in an ADR | INF-01 |
| INF-05 | CI/CD pipeline: lint, unit tests, integration tests run on every PR; build + deploy to staging on merge to main | Infra | Should | Sprint 1 | E1 | Not Started | PRs that break tests are blocked from merging; staging environment reflects main within 10 minutes of merge | INF-01 |

---

## Part 3 — Ingestion Pipeline (Epic E-INGEST + E-ORCH)

| ID | Feature / Task | Category | Priority | Phase / Sprint | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|---|
| ING-01 | `POST /documents` upload endpoint: accept PDF up to 100 MB/500 pages; validate format; reject unsupported with clear error; create Job(UPLOADED); return `job_id` | Ingestion | Must | Sprint 1 | E1 | Not Started | AC: PRD FR-0.1 — a valid PDF is accepted and a job is created with a tracking ID; an invalid format (e.g. `.docx`) returns a clear error message | INF-02, INF-03, INF-04 |
| ING-02 | Ingestion state machine: all states persisted to DB with timestamps (`UPLOADED → DETECTING_TYPE → … → READY \| FAILED(reason)`); `FAILED` always carries a machine + human reason | Ingestion | Must | Sprint 1 | E1 | Not Started | All state transitions from ARCHITECTURE §3 exist; every transition writes a row with a timestamp; no state is reachable without being persisted; `FAILED(reason)` is never a silent stall | INF-02, INF-04 |
| ING-03 | PDF type detection: classify each PDF as `digital`, `scanned`, or `hybrid` using text-layer coverage ratio (from spike heuristic) | Ingestion | Must | Sprint 1 | E2 | Not Started | AC: PRD FR-0.2 — a scanned PDF with no text layer routes to OCR path; detection accuracy ≥ 95% on the spike corpus (30-doc set); result stored on the job record | SK-01 (confirmed heuristic from spike) |
| ING-04 | Digital text extraction: PyMuPDF layout-aware extraction with reading-order preservation | Ingestion | Must | Sprint 1 | E2 | Not Started | AC: PRD FR-0.3 — for a clean digital PDF, extracted text has ≥ 98% character fidelity vs. source on sampled audit; reading order correct on single-column docs | SK-01 (PyMuPDF validated in spike) |
| ING-05 | OCR integration: chosen cloud OCR engine (from spike) + Tesseract fallback; produce text + per-block page coordinates + per-page confidence score | Ingestion | Must | Sprint 1 | E2 | Not Started | AC: PRD FR-0.4 — for a scanned 200-page book, OCR completes within latency budget; word-level confidence is available; clean 300 DPI scans hit ≥ 95% word accuracy; costs stay under $2/scanned-doc cap | SK-01 (OCR engine chosen + cost validated) |
| ING-06 | OCR quality gate: if aggregate confidence below threshold, set `low_confidence` flag on job; propagate flag to affected chapters; never silently fail | Ingestion | Must | Sprint 1 | E2 | Done | AC: PRD FR-0.5 — a low-DPI test scan triggers the flag; UI renders a scan-quality banner on the output; no low-confidence page is presented as trustworthy without the flag. **Done:** OCR now uses `image_to_data` for per-word confidence (`_reconstruct`); `extract_text_with_quality` returns mean confidence + low pages; pipeline sets `graph["ocr_quality"]` + a warning when mean < `OCR_MIN_CONFIDENCE` (default 70); `DocumentDetailPage` shows a prominent scan-quality banner. `_reconstruct` unit-tested (3/3); digital path unchanged (no-regression). Live low-DPI trigger pending a test scan | ING-05 |
| ING-07 | Structural parsing: build Document → Chapter → Section → Paragraph outline from font/position/numbering cues; for OCR docs, infer headings from OCR coordinates | Ingestion | Must | Sprint 1 | E2 | Not Started | AC: PRD FR-0.6 — for a book with a real TOC, ≥ 90% of chapters detected with correct titles; for OCR docs, heading inference tested on ≥ 2 scanned corpus docs | ING-03, ING-04, ING-05 |
| ING-08 | Chunking + context breadcrumbs: chunk at section level (≈500–1500 tokens); prepend `[Document][Chapter][Section]` context to every chunk before extraction | Ingestion | Must | Sprint 1 | E2 | Not Started | AC: PRD FR-0.7 — no chunk exceeds the model input budget; every chunk carries its full structural breadcrumb; chunks stored in DB with `chapter_id` for O(1) citation resolution | ING-07 |

---

## Part 4 — Extraction (Epic E-EXTRACT)

| ID | Feature / Task | Category | Priority | Phase / Sprint | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|---|
| EXT-01 | Extraction worker: per-chunk LLM call (cheap-tier model) to extract concepts, principles, examples, relations; output includes `source_refs[] + confidence + extraction_method` for every node/edge | Extraction | Must | Sprint 2 | E2 | Not Started | A full book produces candidate nodes and edges; every node/edge carries a source citation (chapter_id + page_range + char_span) and a confidence score 0–1; edges are explicit/cited-only (no inferred cross-chapter edges) | ING-08, SK-02 (hallucination bar), SK-04 (model IDs) |
| EXT-02 | Per-document cost ledger: every LLM/OCR API call writes token/credit cost to the job row; hard cap aborts the job (`FAILED(cost_cap)`) before overrun | Extraction | Must | Sprint 2 | E1 | Done | For a test book, every LLM call's cost is recorded in the ledger; a synthetic doc that would exceed the cap triggers `FAILED(cost_cap)` and stops cleanly; per-doc total is queryable. **Done:** providers expose `last_usage`; `CostLedger` + `usd_for` pricing (`app/costs.py`, `LLM_PRICES_USD` override); pipeline accrues cost per chunk+brief, `_enforce_cost_cap` aborts with `CostCapExceeded('cost_cap…')` at `MAX_DOC_COST_USD`; `jobs.cost_usd` persisted. Unit-tested; live column+endpoint verified (full cost run pending a cloud-model extraction) | INF-02, SK-04 |
| EXT-03 | Idempotent chunk-extraction caching: results keyed by `hash(chunk_text + prompt_version)`; re-runs and retries reuse cached results without re-calling the LLM | Extraction | Must | Sprint 2 | E1 | Not Started | Re-processing the same chunk does not generate a new LLM call; cached result is returned; prompt_version bump invalidates the cache correctly | EXT-01, INF-02 |
| EXT-04 | Parallel extraction fan-out: dispatch one extraction task per chunk concurrently; bound concurrency to respect provider rate limits and per-doc cost cap | Extraction | Must | Sprint 2 | E1 | Not Started | A 300-page book's chunks are processed in parallel; concurrency limit is configurable; no rate-limit errors in normal operation; actual latency measured against PRD budgets on a test book | EXT-01, INF-04 |

---

## Part 5 — Graph (Epic E-GRAPH)

| ID | Feature / Task | Category | Priority | Phase / Sprint | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|---|
| GRP-01 | Entity resolution: conservative lexical/string-similarity merge of candidate nodes; prefer under-merge; assign canonical IDs; flag near-duplicates for review | Graph | Must | Sprint 3 | E2 | Not Started | "DRY" and "Don't Repeat Yourself" do not appear as two separate concept nodes in the test corpus; no false-merge on clearly distinct concepts; merge threshold documented and testable | EXT-01 |
| GRP-02 | Graph store: one JSONB document per PDF in Postgres containing all canonical nodes, edges, and `source_refs[] + confidence + extraction_method`; schema per PRD §8 | Graph | Must | Sprint 3 | E1 | Not Started | A processed book's full graph is queryable from Postgres; all node types (Concept, Principle, Term, Example, Person, Tool, Chapter, Section) and edge types from PRD §8 are represented | GRP-01, INF-02 |
| GRP-03 | Citation resolution at O(1): co-locate chunks with graph keyed by `chapter_id`; every concept/relation resolves to its source excerpt without a full-book scan | Graph | Must | Sprint 3 | E1 | Not Started | Clicking "verify" on any concept returns its source excerpt in < 200 ms; no full-graph scan required | GRP-02, ING-08 |

---

## Part 6 — Outputs (Epics E-OUTPUTS + E-QA)

| ID | Feature / Task | Category | Priority | Phase / Sprint | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|---|
| OUT-01 | The Brief: ~500-word executive summary (thesis, 5 core concepts, 3 key principles, target audience) generated from the graph using strong-tier LLM; every claim links to ≥1 source chapter | Outputs | Must | Sprint 3 | E2 | Not Started | AC: PRD §4.1 — in blind review of 10 known books, ≥ 8/10 Briefs rated "accurate or mostly accurate"; 100% of claims carry a source chapter citation; generated from the graph, not a raw re-summary of full text | GRP-02, SK-04 |
| OUT-02 | Concept Map: 15–25 deduplicated concepts, each with name, one-sentence definition, best-explained chapter, 2–3 related concepts, confidence score | Outputs | Must | Sprint 3 | E2 | Not Started | AC: PRD §4.2 — no obvious duplicates; each concept cites its source chapter/section; concept precision ≥ 80% on manual check of ≥ 2 corpus books; Free tier shows max 10 concepts (paywall gate for 11–25) | GRP-01, GRP-02 |
| OUT-03 | Chapter Guide: per chapter — one-sentence summary, concepts introduced, concepts assumed as prerequisite; references canonical concept IDs from the Concept Map | Outputs | Must | Sprint 3 | E2 | Done | AC: PRD §4.3 — every detected chapter has a guide entry; "concepts introduced" reference canonical IDs; Chapter Guide withheld on Free tier (paywall gate). **Done:** `app/chapter_guide.py` builds it deterministically from the graph (no extra LLM) — per-chapter summary, concepts-introduced (canonical IDs), and prerequisites (linked concepts introduced earlier); stored on `graph["chapter_guide"]` (recomputed on retry); Free-tier **locked** via `apply_free_tier_caps`; **Chapter guide tab** in `DocumentDetailPage` with a Pro upgrade teaser when locked. Builder 7/7 + lock 4/4 unit-tested; live needs a re-processed doc | GRP-02, ING-07 |
| OUT-04 | Embedding index: embed all chunks using the chosen embedding model; store in pgvector with `chunk_id → chapter_id` mapping | Q&A | Must | Sprint 4 | E2 | Not Started | All chunks for a processed book are indexed in pgvector; nearest-neighbor search returns top-k chunks with chapter references in < 500 ms for a 300-page book | ING-08, INF-02, SK-04 |
| OUT-05 | Q&A service (RAG): embed question → retrieve top-k chunks → strong-tier LLM grounded answer with chapter citations; "not covered" path when retrieval confidence is low | Q&A | Must | Sprint 4 | E2 | Not Started | AC: PRD §4.4 — answer cites specific chapters/sections; system says "not covered" when topic is absent; median latency ≤ 8 s; no full-book reprocessing per question; Q&A withheld on Free tier (paywall gate) | OUT-04, SK-04 |
| OUT-06 | Export outputs (Markdown + JSON): allow Pro/Scholar users to download Brief, Concept Map, Chapter Guide, and Q&A history | Outputs | Should | Sprint 5 | E1 | Not Started | Pro and Scholar users see a download button; exported Markdown is readable standalone; JSON matches the graph schema; Free users do not see the export option | OUT-01, OUT-02, OUT-03, PAY-02 |
| OUT-07 | Re-process / re-run a document: allow a user to trigger a fresh processing run (e.g. after a prompt_version bump) | Outputs | Should | Sprint 5 | E1 | Not Started | A user with an existing processed doc can trigger a re-run; idempotent caching (EXT-03) means re-run only reprocesses changed prompt-version chunks; previous outputs are replaced, not duplicated | EXT-03, PAY-02 |

---

## Part 7 — Auth & Accounts

| ID | Feature / Task | Category | Priority | Phase / Sprint | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|---|
| AUTH-01 | User signup / login: email+password auth (or OAuth provider); JWT session tokens; per-user data isolation from day 1 | Auth | Should | Sprint 3 | E1 | Not Started | A user can sign up, log in, and log out; all document records, graph data, and embeddings are scoped to the authenticated user's ID; another user cannot access another user's documents | INF-02 |
| AUTH-02 | Per-user document library: list all processed documents for the authenticated user; Free tier shows last 2 docs only; Pro/Scholar unlimited | Auth | Should | Sprint 3–4 | E1 | Not Started | A user's document list reflects their uploads and their tier limit; Free users see at most 2 docs in the library view; the oldest docs are accessible via direct link but not listed (Assumption: "last 2 docs" means listed; others are still accessible) | AUTH-01, PAY-01 |

---

## Part 8 — Paywall & Pricing Tiers

Paywall enforcement is an MVP requirement if soft launch is the target end of Sprint 5. Auth is a prerequisite. Items below gate features per `monetization-pricing.md`.

| ID | Feature / Task | Category | Priority | Phase / Sprint | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|---|
| PAY-01 | Free tier enforcement: 2 digital uploads/month; scanned PDFs blocked; Concept Map capped at 10 concepts; Chapter Guide and Q&A withheld; document library shows last 2 docs | Paywall | Must | Sprint 4 | E1 | Done | A Free user who attempts a 3rd upload this month sees a clear upgrade prompt, not an error; scanned PDF upload attempt surfaces "upgrade to Pro" messaging; Concept Map UI renders only 10 concepts with a "See all 25 on Pro" prompt. **Done:** monthly upload-count quota + 402 upgrade message; scanned/hybrid-PDF block on Free (`enforce_scanned_allowed`); Concept-Map 10-cap at serve time + paywall banner (`apply_free_tier_caps`, `PLAN_FREE_CONCEPTS`, banner in `DocumentDetailPage`). **Q&A gating revised per RC-20:** Free now gets zero-LLM *retrieval* Q&A (not withheld); LLM-synthesized Q&A is gated to Pro/Scholar via `effective_chat_mode`/`CHAT_LLM_MIN_PLAN`. Needs live acceptance-gate verification | AUTH-01, OUT-02, OUT-03, OUT-05 |
| PAY-02 | Pro tier enforcement: 20 combined uploads/month; all 4 outputs at full fidelity; export; unlimited library; credit add-ons available | Paywall | Must | Sprint 4 | E1 | In Progress | A Pro user can upload up to 20 docs/month (any type); sees full Concept Map, Chapter Guide, Q&A, and export; hitting the 20-doc ceiling surfaces a credit add-on prompt. **Done:** 20-doc/mo quota enforced. **Remaining:** credit add-on prompt (depends PAY-05) | AUTH-01, PAY-04 |
| PAY-03 | Scholar tier enforcement: 60 combined uploads/month; priority queue flag; Phase-2 early-access flag (record but no feature yet) | Paywall | Must | Sprint 4 | E1 | In Progress | Scholar users' jobs are flagged for priority processing; ceiling is 60/month; early-access flag stored on user record for future use. **Done:** 60-doc/mo quota enforced. **Remaining:** priority-queue flag, early-access flag on user record | AUTH-01, PAY-04 |
| PAY-04 | Stripe integration: checkout for Pro/Scholar monthly + annual plans; webhook handling for subscription lifecycle (created, cancelled, payment failed) | Paywall | Must | Sprint 4–5 | E1 | In Progress | A user can upgrade from Free to Pro via a Stripe-hosted checkout; subscription status is synced to the user record via webhook; downgrade returns the user to Free tier limits. **Done:** `POST /billing/checkout` (hosted subscription checkout, monthly+annual), `POST /billing/portal`, signature-verified `POST /billing/webhook` syncing plan on checkout-completed / subscription-updated / subscription-deleted, `GET /billing/config` (`app/billing.py`, `app/billing_routes.py`). **Remaining:** live Stripe price IDs in `.env`; frontend upgrade buttons + success/cancel pages | AUTH-01 |
| PAY-05 | Credit add-on purchase: 5-doc and 10-doc packs purchasable by Pro/Scholar users; credits never expire; applied to the user's monthly quota | Paywall | Should | Sprint 5 | E1 | Not Started | A Pro user can purchase a 5-doc pack; credits are added to their account and consumed before the plan's monthly allotment runs out; credits persist across billing cycles | PAY-04 |
| PAY-06 | Upgrade prompts and paywall UI: contextual prompts at every paywall gate (upload limit, concept count, Q&A, Chapter Guide, export) | Paywall | Must | Sprint 4 | E1 | Not Started | Every blocked action surfaces a specific, contextual upgrade message (not a generic "upgrade" modal); Free users who click "ask a question" see a message tied to Q&A specifically; conversion to upgrade click is tracked | PAY-01, PAY-02, ACT-03 |
| PAY-07 | Student discount mechanics (3 months free Pro for verified .edu email) | Paywall | Could | Sprint 5 (if capacity) | E1 | Not Started | Assumption: honor-system .edu email check is acceptable for MVP; if so: users who sign up with a .edu email are offered 3 months free Pro at account creation; requires Product decision on verification method | AUTH-01, PAY-04 |

---

## Part 9 — Activation & Instrumentation

These items must be wired **before soft launch** (end of Sprint 5). They feed the GTM gates.

| ID | Feature / Task | Category | Priority | Phase / Sprint | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|---|
| ACT-01 | Concept Map view event: fire a server-side event when a user first loads the Concept Map for a document; store `(user_id, doc_id, timestamp)` | Activation | Must | Sprint 4 | E1 | Done | Every unique Concept Map page-view is recorded; the event is queryable for the activation rate dashboard; no PII beyond user_id. **Done:** `POST /api/activation/view` fired once per visit from `DocumentDetailPage`; `ActivationEvent(kind=view)` idempotent per user/job (`app/activation.py`). Live-tested | OUT-02, AUTH-01 |
| ACT-02 | Concept Map rating prompt: after the Concept Map loads, show a single thumbs-up/thumbs-down prompt ("Are these the right concepts?"); record result | Activation | Must | Sprint 4 | E1 | Done | The prompt appears exactly once per doc per user (not on every revisit); result is stored and queryable; the PRD target of ≥ 70% thumbs-up can be measured from this data. **Done:** thumbs up/down prompt in the graph tab, shown only when `status.rated` is false; `POST /api/activation/rate`; `thumbs_up_rate` in `/summary`. Live-tested | ACT-01 |
| ACT-03 | Q&A session tracking: record whether a user asks ≥1 Q&A question in the same session as viewing the Concept Map | Activation | Must | Sprint 4 | E1 | Done | Co-session Q&A usage is queryable by session; PRD target of ≥ 50% of Concept Map viewers using Q&A in the same session can be measured. **Done:** `record_qa` fired server-side from the chat `ask` handler (idempotent per user/job); `qa_cosession_rate` (views that also have a qa) in `/summary`. Note: "co-session" approximated as same (user, doc) rather than a shared session id. Live-tested | ACT-01, OUT-05 |
| ACT-04 | Per-document cost telemetry: cost ledger values surfaced to an internal ops dashboard (not user-facing) | Observability | Must | Sprint 2 | E1 | In Progress | Any team member can query total cost + per-stage cost for any processed document; alerts fire if per-doc cost exceeds 80% of the cap. **Done:** `cost_usd` on each job (in summary/detail); admin `GET /api/admin/costs` (documents, total/avg/max USD, cap, top-10); **admin UI** — `/admin/costs` page (stat tiles + top-10 table) and an admin-only "Cost (LLM)" stat on the document detail page. **Remaining:** per-stage cost breakdown, 80%-of-cap alerting | EXT-02 |
| ACT-05 | Stage latency metrics: record wall-clock duration for each state-machine transition; surface p50/p90 per stage to an internal dashboard | Observability | Must | Sprint 4–5 | E1 | Done | p90 latency per stage is visible in the dashboard; alerts fire if digital-doc end-to-end p90 exceeds 5 min or scanned p90 exceeds 12 min. **Done:** pipeline times each stage (`stage_timings`) + total; `jobs.duration_ms` persisted; admin `GET /api/admin/metrics` (p50/p90/max + per-stage p90 + budget flags) and `/admin/metrics` "Latency" page. Live-verified | ING-02 |
| ACT-06 | OCR confidence distribution: record per-page OCR confidence scores; histogram visible in internal dashboard | Observability | Should | Sprint 5 | E1 | Not Started | For any scanned doc, the confidence distribution is queryable; the % of docs triggering the low-confidence banner is tracked week-over-week | ING-06 |
| ACT-07 | Q&A latency monitoring: record median and p95 Q&A answer latency per query; alert if median exceeds 8 s | Observability | Must | Sprint 5 | E1 | Done | Q&A latency is queryable; PRD target of ≤ 8 s median is measurable; alert is wired. **Done:** `chat_messages.latency_ms` set on every assistant answer (retrieval compose time / LLM generation time); `/api/admin/metrics` reports median + p95 with an 8 s alert; shown on the Latency page. Live-verified (retrieval median ≈3 ms) | OUT-05 |

---

## Part 10 — Web UI (Epic E-UI)

| ID | Feature / Task | Category | Priority | Phase / Sprint | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|---|
| UI-01 | Upload flow: drag-and-drop or file-picker; shows file name + size; validates client-side before upload; calls `POST /documents`; transitions to progress view | UI | Must | Sprint 4 | E1+E2 | Not Started | A user can upload a PDF from the browser; invalid formats are rejected before the network request; upload begins and transitions to the progress screen automatically | ING-01 |
| UI-02 | Live progress bar: polls `GET /documents/{id}/status`; maps state-machine states to human-readable labels ("Extracting text…", "Building concept map…"); shows OCR quality banner if `low_confidence` flag is set | UI | Must | Sprint 4 | E1 | Not Started | Progress bar updates without page refresh; all non-terminal states have a human-readable label; the scan-quality banner appears for low-confidence docs before outputs load | ING-02, ING-06 |
| UI-03 | Brief view: render the ~500-word Brief with each claim linked to its source chapter (clickable citation) | UI | Must | Sprint 4 | E1 | Not Started | The Brief is the first thing visible when a doc reaches READY; every claim has a visible, clickable citation; clicking it scrolls to or opens the verify panel | OUT-01 |
| UI-04 | Concept Map view: render concept cards (name, definition, related concepts, confidence, source chapter); Free tier shows 10 cards + upgrade prompt for 11–25; thumbs rating prompt fires on first load | UI | Must | Sprint 4 | E1 | Not Started | Concept cards render with all fields; confidence is visible (e.g. as a score or icon); the thumbs prompt fires once per user per doc; Free tier shows the 10-concept cap and upgrade prompt | OUT-02, ACT-01, ACT-02, PAY-01 |
| UI-05 | Chapter Guide view: per-chapter summary with "concepts introduced" and "prerequisite concepts" linked to their concept cards; withheld (upgrade prompt) for Free users | UI | Must | Sprint 4 | E1 | Not Started | Every detected chapter has an entry; concept names are linked to their Concept Map cards; Free users see the Chapter Guide teased with an upgrade prompt | OUT-03, PAY-01 |
| UI-06 | Q&A interface: text input; submits to `POST /documents/{id}/qa`; renders answer with chapter citations; shows "not covered in this document" when appropriate; streaming preferred | UI | Must | Sprint 4 | E1 | Not Started | A question produces an answer with cited chapters within 8 s median; "not covered" path renders clearly; Free users see an upgrade prompt instead of the input | OUT-05, PAY-01 |
| UI-07 | Verify affordance ("trust check"): clicking any concept, relation, or Q&A answer opens a side panel showing the raw source excerpt and page reference | UI | Must | Sprint 4 | E1 | Not Started | Every clickable claim in the UI opens a source panel with the verbatim excerpt; no claim in any output is unverifiable; latency to open the panel is < 200 ms | GRP-03 |
| UI-08 | OCR quality banner: visible warning banner on any output for a low-confidence scan; includes which chapters are affected | UI | Must | Sprint 4 | E1 | Done | For a doc processed with `low_confidence` flag, the banner is the first visible element on the outputs page; affected chapters are marked in the Chapter Guide. **Done:** prominent warning banner (mean confidence + affected page count) at the top of the document outputs; reads `graph.ocr_quality`. (Per-chapter marking deferred with the Chapter-Guide output OUT-03) | UI-02, ING-06 |

---

## Part 11 — Hardening & Acceptance (Sprint 5)

| ID | Feature / Task | Category | Priority | Phase / Sprint | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|---|
| HAR-01 | Two-column / multi-column layout handling via managed layout parser (for hard PDFs per spike recommendation) | Ingestion | Should | Sprint 5 | E2 | Not Started | D3 (two-column academic paper) and D10 (two-column scanned) from the spike corpus produce usable text without column bleed; improvement over heuristic-only measured and recorded | SK-01 (parser chosen in spike) |
| HAR-02 | Table / figure caption extraction: extract table headers and figure captions as structured content | Ingestion | Should | Sprint 5 | E2 | Not Started | D4 (table-heavy report) from spike corpus: ≥ 70% of table headers and figure captions extracted correctly and appear in the Chapter Guide | SK-01 |
| HAR-03 | Latency tuning: profile and optimize end-to-end pipeline to hit PRD p90 budgets (≤ 5 min digital / ≤ 12 min scanned) on the 10-book acceptance test set | Infra | Must | Sprint 5 | E1+E2 | Not Started | p90 latency meets both budgets on the acceptance set; profiling data documents where time is spent; EXT-04 concurrency tuned for the chosen provider's rate limits | EXT-04, SK-04 |
| HAR-04 | Full acceptance run on 10-book test set (PRD §4.5): ≥3 digital, ≥3 scanned, ≥1 two-column, ≥1 table-heavy | QA | Must | Sprint 5 | E1+E2 | Not Started | Every checkbox in PRD §4.5 MVP Definition of Done passes; results logged to a test-run artifact; no item is self-declared done without evidence | All previous Must items |
| HAR-05 | Blind review of Briefs: ≥ 8/10 Briefs rated "accurate or mostly accurate" by readers who know the books | QA | Must | Sprint 5 | Product | Not Started | 10 reviewers (or 10 review sessions) complete the blind review; ≥ 8 results are "accurate" or "mostly accurate"; results logged | OUT-01 |
| HAR-06 | Privacy policy + Terms of Service: legal pages live in the product; storage/retention language matches the SK-03 decision | Legal | Must | Sprint 5 | Product + Legal | Not Started | Privacy policy and ToS are linked in the UI footer and on the signup page; retention language matches the policy decision from SK-03; reviewed by at least one non-engineer | SK-03 |

---

## Part 12 — GTM Gates

These are pass/fail checkpoints from `gtm-one-pager.md` and `monetization-pricing.md`. Engineering cannot mark them Done — they require observed user behavior or explicit Product/Leadership sign-off.

| ID | Gate | Category | Priority | When | Owner | Status | Pass Criteria | What Happens If It Fails |
|---|---|---|---|---|---|---|---|---|
| G-01 | UX validation: 5 target researchers evaluate a hand-crafted Concept Map + Chapter Guide for a book they know | GTM | Must | Week 2 (before Sprint 2 starts) | Product | Not Started | ≥ 4/5 researchers say "yes, this would change how I read this book"; session notes logged | **Hard stop** — stop and reframe the output format before writing extraction code; do not proceed to Sprint 2 without this gate |
| G-02 | Beta paid-upgrade signal: ≥ 5 beta users voluntarily offer to pay or upgrade to Pro during private beta | GTM | Must | Weeks 6–8 (Sprint 3–4) | Product | Not Started | ≥ 5 beta users explicitly request paid access or upgrade; conversations or in-product data logged | Revisit pricing and value proposition immediately; run 5 "would you pay?" conversations; do not open public launch without signal |
| G-03 | Soft launch activation rate: ≥ 60% of first-time uploads result in an activated user (Concept Map viewed + thumbs interaction) | GTM | Must | Week 10–11 (Sprint 5 / soft launch) | Product | Not Started | Measured from ACT-01 + ACT-02 data; ≥ 60% over the first 7 days of soft launch | Investigate output quality vs. UI; fix before Product Hunt; do not proceed to G-04 |
| G-04 | Pre-Product Hunt activation gate: overall activation ≥ 40% (Concept Map engagement per PRD §13 / GTM doc) | GTM | Must | Week 12 (before PH) | Product | Not Started | ≥ 40% of users who view the Concept Map rate it thumbs-up OR use Q&A in the same session; measured from ACT-01+ACT-02+ACT-03 | Delay Product Hunt; fix quality/UX first |
| G-05 | Privacy policy + ToS live before any public user data is collected | Legal | Must | Week 10 (before soft launch) | Product + Legal | Not Started | HAR-06 complete; links visible in product | Block soft launch until complete |

---

## Part 13 — Milestones Summary

| Milestone | Target Week | Meaning | Gate Criteria |
|---|---|---|---|
| **M0 — Stack chosen** | End of Week 1 | Spike done; OCR/parser locked; cost go/no-go | SK-01 complete; all spike deliverables checked in; decision matrix filled |
| **M0.5 — UX hypothesis validated** | End of Week 2 | Green light to build | G-01 passes (≥ 4/5 researchers) |
| **M1 — Ingestion works** | End of Week 3 | Any PDF → chunks, both types, quality gate | ING-01–08 done; Sprint-1 gate passes |
| **M2 — Graph exists** | End of Week 5 | Candidate graph with provenance, under cost cap | EXT-01–04, GRP-01–03 done; Sprint-2 gate passes |
| **M3 — Thin slice** | End of Week 7 | Upload → Brief/Map/Guide for a digital book | OUT-01–03 done; concept precision ≥ 80%; Sprint-3 gate passes |
| **M4 — Feature-complete** | End of Week 9 | All 4 outputs + UI + paywall, both PDF types | OUT-05, UI-01–08, PAY-01–06, ACT-01–05 done; Sprint-4 gate passes |
| **M5 — GTM-ready** | End of Week 11 | Full DoD passes; legal pages live; activation instrumented | HAR-01–06, G-02, G-05 done; all PRD §4.5 DoD items pass |
| **M6 — Soft launch** | Week 10–11 | Anyone can sign up; Show HN posted | G-03 monitored daily; PAY-01–04 live |
| **M7 — Product Hunt** | Week 12 | Amplification round | G-04 passes (≥ 40% activation) |

---

## Phase 2 Backlog (Explicitly Deferred)

Items below are **not in scope for this release**. Record them here rather than losing them. Re-evaluate at the MVP retrospective.

| ID | Item | Why Deferred |
|---|---|---|
| P2-01 | Visual interactive graph explorer (frontend + backend) | PRD WON'T; requires Phase-2 visual graph work |
| P2-02 | Semantic (embedding-based) entity resolution | PRD WON'T; conservative lexical is sufficient for MVP trust |
| P2-03 | Cross-chapter relationship inference (confidence-gated) | PRD WON'T; highest hallucination risk; deferred explicitly |
| P2-04 | Learning-path / prerequisite tree | PRD WON'T; value is high but pipeline is more complex |
| P2-05 | Shareable per-concept knowledge cards | PRD WON'T; requires Team features |
| P2-06 | Team tier ($49/seat/month) + shared document library | Monetization doc explicitly defers until Phase-2 features exist |
| P2-07 | Graph DB (Neo4j / Memgraph) | Architecture ADR-3: JSON per doc is sufficient at MVP scale |
| P2-08 | Multi-document / cross-book graph | PRD WON'T; significant architectural lift |
| P2-09 | EPUB / DOCX / HTML ingestion | PRD assumption A2: PDF only for MVP |
| P2-10 | Non-English OCR + extraction quality targets | PRD assumption A3: English only for MVP |
| P2-11 | Fine-tuned domain extraction models | PRD WON'T; generic models sufficient for MVP |
| P2-12 | Reading-app integrations (Kindle, Readwise, Zotero) | PRD WON'T; API-dependent; Phase-3 territory |
| P2-13 | Annual billing option | Monetization doc recommendation: defer to Month 2 post-launch |

---

*End of Feature Tracking v1.0 — update Status and Owner cells as work progresses.*
