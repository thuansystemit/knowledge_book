# Phase-1 Implementation Plan: Document Knowledge Graph (MVP)

| | |
|---|---|
| **Document** | Implementation / Sprint Plan — Phase 1 (MVP) |
| **Version** | 1.0 |
| **Date** | 2026-06-29 |
| **Status** | DRAFT — for engineering review |
| **Owner** | Engineering Lead |
| **Parents** | `PRD-knowledge-graph-mvp.md` v1.0, `ARCHITECTURE-mvp.md` v1.0, `SPIKE-week1-pdf-ocr.md` v1.0 |
| **Duration** | ~11 weeks (1 spike week + 5 two-week sprints), 2 engineers |

> Strategy: **risk-first**. The Week-1 spike retires the ingestion/OCR unknowns before we commit pipeline code. Each sprint ends on an **acceptance gate** that maps to specific items in the PRD's MVP Definition of Done (§4.5). Nothing is "done" on assertion — only against the gate.

---

## 1. Approach & sequencing rationale

We build the pipeline in the order risk flows through it:

1. **Retire ingestion risk first** (spike) — it's the source of ~40% of real-world failures and gates the OCR vendor/parser decision (AD-7).
2. **Build the spine before the branches** — ingestion → extraction → graph must exist before summaries and Q&A have anything to consume.
3. **Outputs after the graph** — the four outputs are graph-grounded, so the graph + chunks must be real first.
4. **Harden last** — quality gate polish, hard layouts, cost/latency tuning, and the full acceptance run happen once the happy path works end-to-end.

This ordering means we have a **thin end-to-end slice** (upload a clean digital PDF → get a Brief) by end of Sprint 3, then widen it.

---

## 2. Team & cadence assumptions

- **2 engineers.** E1 = backend/pipeline + orchestration; E2 = ingestion/ML (parsing, OCR, extraction, embeddings). Both full-stack enough to pair on the UI in Sprint 4.
- **2-week sprints**, demo + gate review at each boundary.
- Spike is **Sprint 0** (1 week) and runs before sprint cadence starts.
- Assumes the three PRD blocking decisions (Q1 hallucination bar, Q2 OCR vendor, Q3 privacy) are resolved by the dates in §7. **Q2 is resolved by the spike itself.**

---

## 3. Workstreams (epics) → architecture components

| Epic | Delivers | Arch component(s) |
|---|---|---|
| **E-INGEST** | Upload, type-detect, digital extract, OCR, quality gate, structural parse, chunk | Ingestion Worker, Object/Job store |
| **E-ORCH** | Job orchestrator, state machine, cost ledger, retries | Job Orchestrator, Job/State DB |
| **E-EXTRACT** | Per-chunk concept/relation extraction with provenance | Extraction Worker |
| **E-GRAPH** | Entity resolution, graph store, citation resolution | Entity Resolution, Graph Store |
| **E-OUTPUTS** | Brief, Concept Map, Chapter Guide | Summarize Worker |
| **E-QA** | Embeddings, retrieval, grounded answers + citations | Vector Index, Q&A Service |
| **E-UI** | Upload → progress → outputs → Q&A | Web/API service, frontend |
| **E-OBS** | Cost telemetry, stage metrics, acceptance harness | Cross-cutting observability |

---

## 4. Sprint plan

### Sprint 0 — Spike (Week 1, w/c 2026-06-29)
**Goal:** retire ingestion/OCR risk; choose the stack.
- Execute `SPIKE-week1-pdf-ocr.md` in full (corpus, scoring harness, OCR cloud-vs-Tesseract, type-detect, hard-layout).
- **Gate:** decision matrix filled; PRD Q2 + Q4 resolved with measured numbers; AD-7 closed. Go/no-go on the < $2/scanned cap confirmed with real cost data.

### Sprint 1 — Ingestion spine (Weeks 2–3) — E-ORCH, E-INGEST
**Goal:** a PDF can be uploaded and fully ingested to chunks, with state visible.
- API `POST /documents`, object-store upload, Job creation.
- Job orchestrator + **ingestion state machine** (all states, persisted transitions, `FAILED(reason)`).
- Type detection (from spike heuristic), digital text extraction (PyMuPDF), **OCR integration** (chosen engine), **OCR quality gate** + `low_confidence` flag.
- Structural parsing (chapter/section detection) + section-level chunking with `[Doc][Chapter][Section]` context.
- **Gate:** upload a digital AND a scanned PDF → reach `CHUNKING`→done with correct type routing; quality gate trips a banner flag on the low-DPI doc; no silent failure. *(DoD: upload both types; type-detect ≥95%; scanned→OCR+gate.)*

### Sprint 2 — Extraction + cost control (Weeks 4–5) — E-EXTRACT, E-ORCH
**Goal:** chunks become candidate nodes/edges with provenance, under a cost cap.
- Extraction worker: per-chunk concept/principle/example/relation extraction (cheap LLM tier), emitting `source_refs[] + confidence + extraction_method`.
- Parallel fan-out with bounded concurrency.
- **Per-document cost ledger + hard cap** (→ `FAILED(cost_cap)`); idempotent caching keyed on `hash(chunk_text + prompt_version)`.
- **Gate:** a full book produces candidate nodes/edges, every one carrying a source citation + confidence; per-doc cost recorded and under cap on the spike corpus. *(DoD: edges explicit/cited only; cost telemetry.)*

### Sprint 3 — Graph + the three summary outputs (Weeks 6–7) — E-GRAPH, E-OUTPUTS
**Goal:** thin end-to-end slice — upload → graph → Brief/Map/Guide.
- Entity resolution (conservative lexical merge → canonical IDs); graph store (JSONB per PDF); chunk↔chapter co-location for O(1) citation.
- Summarize worker: **The Brief**, **The Concept Map** (15–25, deduped), **The Chapter Guide** — all graph-grounded, all cited.
- **Gate:** for a clean digital book, all three outputs render with 100% citation coverage + visible confidence; concept precision ≥ 80% on a manual check of ≥ 2 corpus books. *(DoD: outputs + citations + confidence; concept precision ≥80%.)*

### Sprint 4 — Q&A + UI (Weeks 8–9) — E-QA, E-UI
**Goal:** the fourth output + the user-facing product.
- Embedding index (pgvector) over chunks; Q&A service (retrieve top-k → grounded answer + chapter citations → "not covered" path).
- Web UI: upload → live progress (from state machine) → view all four outputs → ask Q&A → "verify" affordance (click claim → source excerpt).
- **Gate:** end-to-end in the browser for both a digital and a scanned book; Q&A median ≤ 8 s and cites chapters; "not covered" works. *(DoD: Q&A grounded+cited; all four outputs in UI.)*

### Sprint 5 — Hardening + acceptance (Weeks 10–11) — E-OBS, all
**Goal:** meet every non-functional budget and pass the MVP Definition of Done.
- Two-column / table handling (Should-scope) via the spike's chosen layout strategy.
- Cost/latency tuning to hit p90 budgets; observability dashboards (stage latency, per-doc cost, OCR confidence dist, Q&A latency) wired to PRD success metrics.
- **Full acceptance run on the 10-book test set**; blind-review the Briefs (≥ 8/10 "accurate").
- **Gate:** every checkbox in PRD §4.5 MVP Definition of Done passes. Ship-ready. *(DoD: latency p90; ≥8/10 Briefs accurate; cost caps; no silent failures.)*

---

## 5. Milestones

| Milestone | Target (w/c) | Meaning |
|---|---|---|
| M0 — Stack chosen | 2026-06-29 | Spike done; OCR/parser locked; cost go/no-go |
| M1 — Ingestion works | 2026-07-13 | Any PDF → chunks, both types, quality gate |
| M2 — Graph exists | 2026-07-27 | Candidate graph w/ provenance, under cost cap |
| M3 — Thin slice | 2026-08-10 | Upload → Brief/Map/Guide for a digital book |
| M4 — Feature-complete | 2026-08-24 | All 4 outputs + UI, both PDF types |
| M5 — MVP ship-ready | 2026-09-07 | Full DoD passes on 10-book set |

---

## 6. Critical path & dependencies

```
Spike(AD-7) ─► Ingestion ─► Extraction ─► Graph ─► Outputs ─► (UI)
                                            └─────► Q&A ──────► (UI) ─► Hardening/Acceptance
```
- **Hard dependency:** nothing in Extraction starts until the spike fixes the OCR/parser stack (AD-7).
- **Parallelizable:** within Sprint 4, Q&A (E2) and UI scaffolding (E1) run in parallel; they converge at the Sprint-4 gate.
- **External blockers:** PRD Q1 (hallucination bar) needed before Sprint 2 extraction-prompt tuning; PRD Q3 (privacy) needed before Sprint 1 storage code finalizes blob retention.

---

## 7. Decisions needed (with by-when)

| Decision | Needed by | Owner | Source |
|---|---|---|---|
| Q2 OCR vendor + cost | End of Sprint 0 | Eng | Resolved by spike |
| Q4 PDF parser | End of Sprint 0 | Eng | Resolved by spike |
| Q1 acceptable hallucination rate + detection | Start of Sprint 2 | Product | PRD §10 |
| Q3 raw-doc storage vs. discard | Start of Sprint 1 | Product + Legal | PRD §10 |
| Managed queue vs. self-hosted | Start of Sprint 1 | Eng + Infra | Arch §10 |
| LLM/embedding model IDs + tiers | Start of Sprint 2 | Eng | Arch §10 (+ Claude API ref) |

---

## 8. Risk burn-down (when each PRD risk is addressed)

| PRD Risk | Addressed in | How |
|---|---|---|
| R2/R3 OCR quality + cost | Sprint 0 | Spike measures accuracy + per-doc cost vs. cap |
| R4 structural parse failure | Sprint 1 + Sprint 5 | Heuristic in S1; layout parser hardening in S5 |
| R1 hallucinated relationships | Sprint 2 | Explicit-only, source-anchored extraction; confidence gating |
| R5 entity-resolution noise | Sprint 3 | Conservative under-merge; manual precision check at gate |
| R7 cost unit-economics | Sprint 2 | Cost ledger + hard cap from the first extraction code |
| R6 user distrust | Sprint 4 | "Verify" affordance + visible confidence in UI |

---

## 9. Out of scope (Phase 2+)

Per PRD/architecture: graph DB, semantic entity resolution, visual graph explorer, cross-chapter inference, multi-document graph, autoscaling, fine-tuned models, team/org collaboration.

---

## 10. Definition of Done → sprint traceability

| PRD §4.5 DoD item | Satisfied by |
|---|---|
| Upload digital + scanned → 4 outputs | S1 (ingest) + S3/S4 (outputs) |
| Type detection ≥ 95%, OCR + quality gate | S0 (validate) + S1 (build) |
| 100% citation coverage + confidence | S2 (provenance) + S3 (render) |
| Concept precision ≥ 80%, edges explicit-only | S2 + S3 (gate check) |
| Q&A grounded + cited + "not covered" | S4 |
| Per-doc cost under cap + telemetry | S2 (ledger) + S5 (tuning) |
| Latency p90 budgets | S5 |
| Low-confidence OCR banner, no silent fail | S1 (state machine) + S5 (polish) |
| ≥ 8/10 Briefs rated accurate | S5 (blind review) |

---

*End of Phase-1 Plan v1.0.*
