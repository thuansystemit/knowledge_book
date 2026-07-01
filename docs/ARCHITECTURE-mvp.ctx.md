# CTX: MVP Architecture

> **AI digest of `ARCHITECTURE-mvp.md`. Self-contained — read this alone; you do NOT need the full `.md`.**
> Parents: `PRD-knowledge-graph-mvp.md` v1.0, `SPIKE-week1-pdf-ocr.md` v1.0 (+ their `.ctx.md`). Convention: paired `*.ctx.md`, keep in sync, work inline.
> Audience: externally reviewed by OpenAI — decisions are traced to PRD budgets, no hand-waving.

## What this is
Smallest architecture delivering the 4 MVP outputs (Brief, Concept Map, Chapter Guide, grounded Q&A) for digital AND scanned PDFs within PRD cost/latency/quality budgets. Choices marked _(spike-pending)_ confirmed by Week-1 spike.

## Architectural drivers (each traced to a PRD budget)
- Async long-running ingestion (scanned ≤12min p90) → background job + progress, NOT request/response.
- Process-once/serve-many (cost <$1 digital/<$2 scanned; Q&A ≤8s) → cache extractions; Q&A never reprocesses book.
- 100% citation coverage + confidence → every node/edge + every LLM call emits provenance.
- Graceful OCR degradation (quality gate, no silent fail) → ingestion is a state machine with explicit low_confidence path.
- Hallucinated edges <15%, explicit-only → constrained source-anchored relation extraction; cross-chapter inference OUT of MVP.

## Components
Web/API (FastAPI) · Job Orchestrator (queue + per-doc state machine, retries, cost ledger; Celery/RQ+Postgres) · Object Store (S3-compat, PDFs+page images) · Ingestion Worker (type-detect→extract/OCR→quality gate→struct parse→chunk; PyMuPDF + OCR spike-pending) · Extraction Worker (per-chunk concepts+relations, LLM cheap tier, +confidence+cites) · Entity Resolution (lexical conservative under-merge MVP) · Summarize Worker (Brief/Map/Guide from graph, LLM strong tier) · Graph Store (JSON per PDF) · Vector Index (chunk embeddings, pgvector/FAISS) · Q&A Service (RAG retrieve→LLM→cite, strong tier).

## Ingestion state machine (auditable, no silent fail)
UPLOADED→DETECTING_TYPE→{digital:EXTRACTING_TEXT | scanned:OCR_RUNNING→OCR_QUALITY_CHECK | hybrid:both}→PARSING_STRUCTURE(+low_confidence flag if gate trips, propagates to banner)→CHUNKING→EXTRACTING_ENTITIES(parallel fan-out per chunk)→RESOLVING_ENTITIES→SUMMARIZING→INDEXING→READY|FAILED(reason). Every transition persisted w/ timestamp (drives progress UI + latency analysis). FAILED always carries machine+human reason.

## Flows
**Ingest:** POST /documents→store PDF+Job(UPLOADED)→orchestrator runs state machine→chunks→parallel extraction(nodes/edges+source_refs+confidence)→entity merge→graph→summaries→embed→READY; client polls status.
**Q&A:** POST /documents/{id}/qa→embed question→vector search that doc's chunks→top-k→LLM grounded on retrieved chunks only→answer+chapter cites; low retrieval→"not covered"; cost = k chunks, NOT whole book (why ≤8s + cheap).

## Storage mapping
Object store: raw PDF + page images. Postgres (Job/State DB): jobs, state transitions, per-doc cost ledger, users. Graph store (JSONB/doc): one graph/PDF, nodes+edges each w/ source_refs[]+confidence+extraction_method. Vector index (pgvector/FAISS): chunk embeddings + chunk→chapter map. **Recommendation: Postgres for everything except blobs at MVP** (JSONB graph + pgvector + jobs in one DB); split only when scale demands. Co-locate chunks w/ graph keyed by chapter_id → O(1) citation resolution.

## Cost/perf design (cost cap is a constraint, not afterthought)
Per-doc cost ledger on job row; hard cap aborts→FAILED(cost_cap) before overrun. Model tiering: cheap/fast for high-volume per-chunk extraction, strong for low-volume Brief+Q&A. Idempotency+cache keyed hash(chunk_text+prompt_version)→retries reuse, no double-spend. Parallel chunk fan-out makes latency budgets reachable (bound concurrency to rate limits+cap). Q&A retrieval-bounded (k chunks).

## ADRs
AD-1 async state-machine ingestion (Accepted) · AD-2 Postgres single store JSONB+pgvector+jobs (Accepted, revisit P2) · AD-3 JSON graph per doc, no graph DB yet (Accepted) · AD-4 RAG-over-chunks Q&A not graph-grounded (Accepted) · AD-5 two-tier LLM cheap-extract/strong-synth+Q&A (Accepted) · AD-6 conservative lexical entity resolution (Accepted) · AD-7 OCR+parser stack = PyMuPDF + cloud-OCR/Tesseract (PENDING Week-1 spike) · AD-8 per-doc hard cost cap+ledger (Accepted).

## Cross-cutting
Privacy: retention flag per doc supports store-or-discard (PRD Q3); per-user isolation day 1. Observability: per-stage logs + metrics (stage latency, per-doc cost, OCR confidence dist, sampled precision, Q&A latency) map 1:1 to PRD success metrics. Failure isolation: failed chunk degrades coverage+flag, doesn't fail whole doc. Idempotent retries via content-hash keys.

## Out of scope (P2+)
graph DB · semantic entity resolution · visual graph explorer backend · cross-chapter inference service · multi-doc graph · autoscaling beyond single worker pool · fine-tuned models.

## Open questions (arch)
1 managed queue vs self-hosted (infra, Week 1) · 2 OCR+parser stack (blocked on spike, AD-7) · 3 blob retention (blocked on PRD Q3) · 4 embedding+LLM model IDs (confirm vs Claude API ref + spike cost) · 5 single-DB scaling ceiling threshold (doc count/QPS triggering AD-2 split).
