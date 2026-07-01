# CTX: Phase-1 Implementation Plan (MVP)

> **AI digest of `PLAN-phase1-implementation.md`. Self-contained — read this alone; you do NOT need the full `.md`.**
> Parents: PRD v1.0, ARCHITECTURE-mvp v1.0, SPIKE-week1-pdf-ocr v1.0 (+ their `.ctx.md`). Convention: paired `*.ctx.md`, keep in sync, work inline.
> Audience: externally reviewed by OpenAI — every sprint ends on a measurable gate tied to PRD DoD; no "done" by assertion.

## Shape
~11 weeks, 2 engineers (E1 backend/pipeline+orchestration; E2 ingestion/ML). Sprint 0 = 1-week spike, then 5×2-week sprints. Risk-first ordering: retire ingestion/OCR risk → build spine (ingest→extract→graph) → outputs+Q&A → harden. Thin end-to-end slice (digital PDF → Brief) by end of Sprint 3.

## Workstreams → arch components
E-INGEST (Ingestion Worker, Object/Job store) · E-ORCH (Orchestrator, Job/State DB) · E-EXTRACT (Extraction Worker) · E-GRAPH (Entity Resolution, Graph Store) · E-OUTPUTS (Summarize Worker) · E-QA (Vector Index, Q&A) · E-UI (Web/API+frontend) · E-OBS (observability+acceptance harness).

## Sprints (each ends on a gate)
- **S0 Spike (Wk1, w/c 2026-06-29):** run full spike; GATE = decision matrix filled, PRD Q2+Q4 resolved w/ numbers, AD-7 closed, $2/scanned cap go/no-go.
- **S1 Ingestion spine (Wk2-3):** POST /documents, object store, Job, orchestrator + state machine (persisted transitions, FAILED(reason)), type-detect, PyMuPDF digital extract, OCR integration + quality gate + low_confidence flag, structural parse + contextualized chunking. GATE = upload digital AND scanned → chunks, correct routing, banner on low-DPI, no silent fail.
- **S2 Extraction + cost (Wk4-5):** per-chunk concept/relation extraction (cheap LLM tier) emitting source_refs+confidence+extraction_method; parallel bounded fan-out; per-doc cost ledger + HARD CAP (FAILED(cost_cap)); idempotent cache hash(chunk+prompt_version). GATE = full book → candidate nodes/edges all cited+confidence; per-doc cost under cap.
- **S3 Graph + 3 summaries (Wk6-7):** conservative lexical entity resolution→canonical IDs; JSONB graph per PDF; chunk↔chapter O(1) citation; Brief + Concept Map (15-25 deduped) + Chapter Guide, graph-grounded+cited. GATE = 3 outputs render w/ 100% citation + confidence; concept precision ≥80% on ≥2 books.
- **S4 Q&A + UI (Wk8-9):** pgvector embeddings; Q&A retrieve top-k→grounded answer+chapter cites→"not covered"; Web UI upload→live progress→4 outputs→Q&A→"verify" affordance (click claim→source excerpt). GATE = browser e2e both PDF types; Q&A median ≤8s + cites; "not covered" works.
- **S5 Hardening + acceptance (Wk10-11):** two-column/table (Should) via spike's layout strategy; cost/latency tuning to p90; observability dashboards mapped to success metrics; FULL acceptance on 10-book set + blind-review Briefs (≥8/10 accurate). GATE = every PRD §4.5 DoD checkbox passes; ship-ready.

## Milestones (w/c)
M0 stack chosen 2026-06-29 · M1 ingestion works 2026-07-13 · M2 graph exists 2026-07-27 · M3 thin slice 2026-08-10 · M4 feature-complete 2026-08-24 · M5 MVP ship-ready 2026-09-07.

## Critical path
Spike(AD-7)→Ingestion→Extraction→Graph→{Outputs, Q&A}→UI→Hardening/Acceptance. Hard dep: Extraction blocked until spike fixes OCR/parser. Parallel: S4 Q&A (E2) ∥ UI scaffold (E1). External blockers: PRD Q1 before S2 prompt tuning; PRD Q3 before S1 blob-retention code.

## Decisions needed (by-when)
Q2 OCR vendor + Q4 parser = end S0 (spike) · Q1 hallucination bar = start S2 (Product) · Q3 storage vs discard = start S1 (Product+Legal) · managed-vs-self-hosted queue = start S1 (Eng+Infra) · LLM/embedding model IDs+tiers = start S2 (Eng, vs Claude API ref).

## Risk burn-down
R2/R3 OCR quality+cost→S0 · R4 parse failure→S1+S5 · R1 hallucination→S2 (explicit-only, source-anchored, confidence-gated) · R5 entity noise→S3 (under-merge+manual check) · R7 cost economics→S2 (ledger+cap from first extraction code) · R6 distrust→S4 (verify affordance + visible confidence).

## DoD → sprint traceability
upload both→4 outputs: S1+S3/S4 · type-detect≥95%+OCR gate: S0+S1 · 100% citation+confidence: S2+S3 · precision≥80%+edges explicit-only: S2+S3 · Q&A grounded/cited/"not covered": S4 · cost under cap+telemetry: S2+S5 · latency p90: S5 · low-confidence banner+no silent fail: S1+S5 · ≥8/10 Briefs accurate: S5.

## Out of scope (P2+)
graph DB · semantic entity resolution · visual graph explorer · cross-chapter inference · multi-doc graph · autoscaling · fine-tuned models · team/org collab.
