# Architecture: Document Knowledge Graph (MVP)

| | |
|---|---|
| **Document** | System Architecture — MVP |
| **Version** | 1.0 |
| **Date** | 2026-06-28 |
| **Status** | DRAFT — for engineering review |
| **Owner** | Engineering / Architecture |
| **Parent** | `PRD-knowledge-graph-mvp.md` v1.0, `SPIKE-week1-pdf-ocr.md` v1.0 |

> Scope: the smallest architecture that delivers the four MVP outputs (Brief, Concept Map, Chapter Guide, grounded Q&A) for **digital and scanned** PDFs, within the PRD's cost/latency/quality budgets. Component choices marked _(spike-pending)_ are confirmed by the Week-1 spike.

---

## 1. Architectural drivers (from the PRD)

These non-functionals shape every decision below; each is traced to a PRD budget:

- **Async, long-running ingestion.** Scanned 300pp ≤ 12 min p90 → processing cannot be request/response; must be a background job with progress.
- **Process-once / serve-many.** Cost cap < $1 digital / < $2 scanned and Q&A ≤ 8 s → extraction results must be cached and reused; Q&A never reprocesses the book.
- **100% citation coverage + confidence.** Every node/edge carries `source_refs[] + confidence` → the data model and every LLM call must emit provenance.
- **Graceful OCR degradation.** Quality gate + no silent failure → ingestion is a state machine with an explicit `low_confidence` path.
- **Conservative extraction.** Hallucinated edges < 15%, edges explicit-only → relationship extraction is constrained and source-anchored; cross-chapter inference is out of MVP.

---

## 2. Component overview

```
                                  ┌──────────────┐
   Browser ──HTTPS──► API Gateway ─► Web/API svc │
                                  └──────┬───────┘
                          upload │       │ status / outputs / Q&A
                                 ▼       ▼
        ┌────────────┐    ┌─────────────────────┐     ┌──────────────┐
        │ Object     │◄───┤ Job Orchestrator    │────►│ Job/State DB │
        │ Store (PDF)│    │ (queue + state mach.)│     │ (Postgres)   │
        └────────────┘    └─────────┬───────────┘     └──────────────┘
                                    │ dispatch stages
            ┌───────────────────────┼───────────────────────────┐
            ▼                       ▼                            ▼
   ┌─────────────────┐   ┌────────────────────┐      ┌────────────────────┐
   │ Ingestion Worker│   │ Extraction Worker  │      │ Summarize Worker   │
   │ type-detect     │   │ per-chunk concepts │      │ Brief/Map/Guide    │
   │ digital extract │   │ + relations (LLM)  │      │ (graph-grounded)   │
   │ OCR + quality   │   │ confidence + cites │      └─────────┬──────────┘
   │ struct parse    │   └─────────┬──────────┘                │
   │ chunk           │             ▼                           │
   └────────┬────────┘   ┌────────────────────┐                │
            │            │ Entity Resolution  │                │
            │            │ + Graph Merge      │                │
            │            └─────────┬──────────┘                │
            ▼                      ▼                           ▼
                       ┌────────────────────────────────────────────┐
                       │ Graph Store (JSON/doc per PDF)  +  Vector   │
                       │ Index (chunk embeddings for Q&A)           │
                       └───────────────────┬────────────────────────┘
                                           ▲
                                  ┌────────┴────────┐
                                  │ Q&A Service     │  (RAG: retrieve → LLM → cite)
                                  └─────────────────┘
```

### Responsibilities
| Component | Responsibility | MVP choice |
|---|---|---|
| **Web/API service** | Upload, auth, job status, serve outputs, Q&A endpoint | Python (FastAPI) |
| **Job Orchestrator** | Queue + per-document **state machine**, retries, cost accounting | Celery/RQ + Postgres (or a managed queue) |
| **Object Store** | Raw PDFs + rendered page images | S3-compatible |
| **Ingestion Worker** | type-detect → extract/OCR → quality gate → structural parse → chunk | PyMuPDF + OCR _(spike-pending)_ |
| **Extraction Worker** | Per-chunk concept/relation extraction with provenance | LLM (cheap tier) |
| **Entity Resolution** | Dedup → canonical IDs (conservative under-merge) | Lexical similarity (MVP) |
| **Summarize Worker** | Brief, Concept Map, Chapter Guide from the graph | LLM (strong tier) |
| **Graph Store** | One JSON graph doc per PDF | Postgres JSONB / document store |
| **Vector Index** | Chunk embeddings for Q&A retrieval | pgvector / FAISS |
| **Q&A Service** | RAG: retrieve chunks → grounded answer + citations | LLM (strong tier) |

---

## 3. Ingestion state machine

Explicit states make the OCR quality gate and "no silent failure" auditable:

```
UPLOADED
  → DETECTING_TYPE
     → (digital)  EXTRACTING_TEXT ─┐
     → (scanned)  OCR_RUNNING ──────► OCR_QUALITY_CHECK
     → (hybrid)   both paths ───────┘        │
                                    ├─ ok ───► PARSING_STRUCTURE
                                    └─ low ──► PARSING_STRUCTURE (+low_confidence flag, banner)
  → CHUNKING
  → EXTRACTING_ENTITIES        (fan-out per chunk, parallel)
  → RESOLVING_ENTITIES
  → SUMMARIZING                (Brief, Map, Guide)
  → INDEXING                   (embeddings)
  → READY  |  FAILED(reason)
```

- Every transition is persisted in the Job/State DB with a timestamp → drives the UI progress bar and post-hoc latency analysis.
- `FAILED` always carries a machine + human reason (e.g. `unsupported_pdf`, `ocr_zero_text`). Never a silent stall.
- The `low_confidence` flag propagates to outputs so affected chapters render the scan-quality banner (PRD FR-0.5).

---

## 4. Key flows

### 4.1 Drop-a-PDF (ingestion)
```
1. Client POST /documents (multipart) → API stores PDF in object store, creates Job(UPLOADED), returns job_id.
2. Orchestrator advances the state machine, dispatching stage workers.
3. Ingestion worker: detect → extract/OCR (+quality gate) → parse structure → chunk; writes chunks + structure.
4. Extraction workers (parallel, one per chunk): emit candidate nodes/edges with source_refs + confidence.
5. Entity resolution merges candidates → canonical graph (JSON).
6. Summarize worker generates Brief/Map/Guide from the graph (grounded, cited).
7. Indexing embeds chunks → vector index. Job → READY.
8. Client polls GET /documents/{id}/status; on READY, GET outputs.
```

### 4.2 Q&A (interactive, must be cheap + fast)
```
1. Client POST /documents/{id}/qa {question}.
2. Embed question → vector search over that doc's chunk index → top-k chunks.
3. LLM answers grounded ONLY on retrieved chunks; returns answer + chapter citations.
4. If retrieval confidence is low / no relevant chunks → "not covered in this document."
   No full-book reprocessing; cost is k-chunks per question, not the whole book.
```

---

## 5. Data model & storage mapping

| Store | Holds | Why |
|---|---|---|
| **Object store** | raw PDF, rendered page images | large binaries, cheap |
| **Job/State DB (Postgres)** | jobs, state transitions, per-doc cost ledger, users | transactional, queryable for ops |
| **Graph store (JSONB/doc)** | one graph per PDF: nodes, edges, each with `source_refs[] + confidence + extraction_method` | MVP-simple; graph DB deferred to Phase 2 |
| **Vector index (pgvector/FAISS)** | chunk embeddings + chunk→chapter map | Q&A retrieval |

Node/edge schema is defined in the PRD §8 (Concept/Principle/Term/Example/Person/Chapter/Tool; `is_prerequisite_of`, `relates_to`, `contrasts_with`, `exemplifies`, `is_part_of`, `leads_to`, `defined_in`, `cited_in`). Architecture adds: **co-locate chunks with the graph** keyed by `chapter_id` so citations resolve in O(1).

> Recommendation: use **Postgres for everything except blobs** at MVP (JSONB graph + pgvector + jobs in one DB). Minimizes infra; one backup/restore story. Split out only when scale demands (Phase 2).

---

## 6. Cost & performance design

The cost cap is an architectural constraint, not an afterthought:

- **Per-document cost ledger.** Every LLM/OCR call writes token/credit cost to the job row. A **hard cap** aborts the job (→ `FAILED(cost_cap)`) before overrun. Makes the <$1/<$2 budget enforceable and observable.
- **Model tiering.** High-volume per-chunk extraction → cheap/fast model; low-volume, high-stakes Brief + Q&A → strong model. (Concrete model IDs per the Claude API reference; tier choice validated against quality on the spike corpus.)
- **Idempotency + caching.** Chunk extraction keyed by `hash(chunk_text + prompt_version)` → re-runs and retries reuse cached results; no double spend.
- **Parallel fan-out** of per-chunk extraction is what makes the latency budgets reachable; bound concurrency to respect provider rate limits + cost cap.
- **Q&A is retrieval-bounded** (k chunks), structurally cheap — the reason Q&A can be ≤ 8 s and not blow cost.

---

## 7. Architecture Decision Records (ADRs)

| # | Decision | Rationale | Status |
|---|---|---|---|
| **AD-1** | Async job + state-machine ingestion (not request/response) | 12-min scanned processing; need progress + retries + auditable OCR gate | Accepted |
| **AD-2** | Postgres as the single store (JSONB graph + pgvector + jobs) | Minimize infra; one consistency/backup story; graph small at MVP | Accepted (revisit Phase 2) |
| **AD-3** | JSON graph per document, no graph DB yet | MVP graphs are <few-hundred nodes; graph DB is premature infra | Accepted |
| **AD-4** | RAG-over-chunks for Q&A (not graph-grounded) | Sufficient + cheap for MVP; graph-grounded answering is a Phase-2 upgrade | Accepted |
| **AD-5** | Two-tier LLM (cheap extract / strong synthesize+Q&A) | Cost control without sacrificing high-stakes output quality | Accepted |
| **AD-6** | Conservative lexical entity resolution | Under-merge beats false-merge for trust; semantic resolution Phase 2 | Accepted |
| **AD-7** | OCR engine + PDF parser | _Spike-pending_ — PyMuPDF + managed-cloud-OCR/Tesseract are the leading candidates | Pending (Week-1 spike) |
| **AD-8** | Per-document hard cost cap with ledger | Makes the PRD cost budget enforceable, not aspirational | Accepted |

---

## 8. Cross-cutting concerns

- **Security/privacy.** Raw PDFs may be sensitive; storage-vs-discard is a PRD open question (Q3). Architecture supports both via a retention flag on the document (discard blobs after READY if policy requires). Per-user data isolation from day 1.
- **Observability.** Structured logs per job stage; metrics: stage latency, per-doc cost, OCR confidence distribution, extraction precision (sampled), Q&A latency. These map 1:1 to the PRD success metrics.
- **Failure isolation.** A failed chunk extraction degrades that chunk (lower coverage + flag), it does not fail the whole document.
- **Idempotent retries** at every stage via content-hash keys.

---

## 9. Out of scope (MVP) — deferred to Phase 2+

Graph DB; semantic entity resolution; visual graph explorer backend; cross-chapter relationship inference service; multi-document graph; horizontal autoscaling beyond a single worker pool; fine-tuned extraction models.

---

## 10. Open questions (architecture)

1. **Managed queue vs. self-hosted (Celery/RQ)?** Depends on deploy target — resolve with infra in Week 1.
2. **OCR + parser stack** — blocked on the Week-1 spike (AD-7).
3. **Blob retention policy** — blocked on PRD Q3 (privacy decision).
4. **Embedding + LLM provider/model IDs** — confirm against the Claude API reference + spike cost numbers before locking tiers.
5. **Single-DB scaling ceiling** — define the threshold (doc count / QPS) that triggers the AD-2 split.

---

*End of Architecture v1.0.*
