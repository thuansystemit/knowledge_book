# PRD: Document Knowledge Graph — AI-Powered Deep Reading Accelerator (MVP)

| | |
|---|---|
| **Document** | Product Requirements Document — MVP |
| **Product** | Document Knowledge Graph (working title: "KnowledgeBook") |
| **Version** | 1.0 |
| **Date** | 2026-06-28 |
| **Status** | DRAFT — for engineering review |
| **Owner** | Product |

> Source of decisions: ideation brief (2026-06-28) + three locked product decisions:
> (1) all four outputs ship together as co-equal heroes; (2) **OCR is table-stakes for MVP** (scanned PDFs supported at launch); (3) build the full MVP spec now.

---

## 1. Problem Statement & Goals

Knowledge workers must absorb long-form documents (200–400 page technical books, reports, papers) but cannot afford to read them end-to-end. A 300-page book holds perhaps 15–20 genuinely novel ideas buried in hundreds of pages of elaboration and repetition. Today people either skim badly (miss nuance), read slowly (high time cost), or never finish (zero ROI).

This is **not a summarization problem** — linear summaries lose structure. The goal is a **navigable semantic map**: ingest a document, build a knowledge graph of its concepts and relationships, and let a person understand it fast and then drill into exactly what matters.

**"Understand fast" is achieved when a user can:**
- State the thesis in one sentence
- Name 5–10 core concepts with working definitions
- Explain how ≥3 of those concepts relate
- Find which chapter/section covers any given concept
- Judge whether the ideas are credible and applicable

**Primary goal of the MVP:** a user uploads a PDF (digital *or scanned*) and, within minutes, receives a Brief, a Concept Map, a Chapter Guide, and grounded Q&A — accurate enough that they'd rate it "more useful than searching the web for this book's key ideas."

---

## 2. Target Personas & Primary JTBD

| Persona | Who | Primary Job-to-be-Done | "Done" looks like |
|---|---|---|---|
| **A. Researcher / Analyst** | Reads 5–10 papers/books/month | Extract concepts precisely, connect to prior knowledge | "I know the 10 core claims and can cite them." |
| **B. Busy Practitioner** | Eng manager, consultant, PM | Get actionable takeaways for decisions | "I can apply 3 things this week." |
| **C. Student / Learner** | Working a curriculum | Find concepts + prerequisite order | "I know what to read, in what order." |
| **D. Team Lead / Sharer** | Wants to brief a team | Share key ideas without everyone reading | "I send a link; the team gets the thesis in 10 min." |

**Ranked JTBD:** (1) Orient fast → (2) Extract concepts → (3) Find relationships → (4) Prioritize reading → (5) Answer specific questions → (6) Share understanding.

---

## 2.5 Assumptions & Constraints

These are explicit so a reviewer can challenge them directly:

- **A1.** Target documents are predominantly non-fiction/technical (books, reports, papers) with chapter/section structure. Fiction and unstructured prose are not optimized for.
- **A2.** Input is PDF only for MVP (digital or scanned). EPUB/DOCX/HTML are out of scope.
- **A3.** Documents are in English for MVP; OCR and extraction quality targets apply to English only.
- **A4.** A managed cloud OCR service is available and acceptable for data handling (subject to the privacy decision, §10 Q3).
- **A5.** "Conservative under-merge" in entity resolution is the right trust trade-off for MVP (duplicate nodes are tolerable; false merges are not).
- **A6.** Q&A grounded via RAG over chunks is sufficient for MVP; graph-grounded answering is a Phase-2 quality upgrade, not a launch blocker.
- **A7.** Cost/latency budgets (§6) assume parallelized per-chunk processing and aggressive caching (process-once / serve-many).

## 3. Scope (MoSCoW)

### MUST (MVP)
- **Ingest digital PDFs** (real text layer)
- **Ingest scanned/image PDFs via OCR** *(pulled into MVP per product decision)*
- PDF type auto-detection (digital vs. scanned) and routing
- Chapter/section boundary detection (heuristic)
- Per-chapter entity extraction (concepts, principles, examples, people, tools)
- Conservative entity deduplication (string/lexical similarity; prefer under-merging)
- **Output 1 — The Brief** (executive summary)
- **Output 2 — The Concept Map** (15–25 concepts, text-based)
- **Output 3 — The Chapter Guide**
- **Output 4 — Grounded Q&A** with chapter citations
- Source citations + confidence scores on every concept and relationship
- Web UI: upload → progress → view all four outputs
- Per-document cost cap + cost telemetry

### SHOULD
- Two-column / multi-column layout handling
- Table/figure caption extraction
- Re-process / re-run a document
- Export outputs (Markdown / JSON)
- Basic auth & per-user document library

### COULD
- Visual interactive graph explorer
- Semantic (embedding-based) entity resolution
- Cross-chapter relationship inference (gated by confidence)
- Learning-path / prerequisite tree
- Shareable per-concept knowledge cards

### WON'T (this release)
- Multi-document / cross-book graph
- Fine-tuned domain extraction models
- Reading-app integrations (Kindle, Readwise)
- Team/org collaboration & permissions
- Real-time collaborative annotation

---

## 4. Functional Requirements & Acceptance Criteria

### 4.0 Ingestion + OCR Pipeline (Must)

**FR-0.1 Upload & validation.** Accept PDF up to 100 MB / 500 pages. Reject unsupported formats with a clear message.
- *AC:* Given a valid PDF, when uploaded, then it is accepted and a processing job is created with a tracking ID.

**FR-0.2 PDF type detection.** Auto-classify each PDF as `digital` (extractable text layer), `scanned` (image-only), or `hybrid` (mixed) before extraction.
- *AC:* Given a scanned PDF with no text layer, when classified, then it is routed to the OCR path (not the digital text path).
- *AC:* Detection accuracy ≥ 95% on a 30-document labeled test set.

**FR-0.3 Digital text extraction.** Extract text with layout/reading-order preservation for digital PDFs.
- *AC:* For a clean digital PDF, extracted text has ≥ 98% character fidelity vs. source on a sampled audit.

**FR-0.4 OCR extraction (scanned/hybrid).** Run OCR to produce text + per-block page coordinates and a per-page confidence score.
- *AC:* For a scanned 200-page book, OCR completes within the latency budget (§6) and yields word-level confidence.
- *AC:* OCR word-accuracy ≥ 95% on clean scans (300 DPI); pages below a confidence threshold are flagged, not silently dropped.

**FR-0.5 OCR quality gate.** If aggregate OCR confidence is below threshold, surface a warning ("low-quality scan — results may be incomplete") rather than failing silently or presenting unreliable output as trustworthy.
- *AC:* Given a low-confidence scan, when processing finishes, then the user sees a quality banner and affected chapters are marked.

**FR-0.6 Structural parsing.** Build a Document → Chapter → Section → Paragraph outline; for OCR docs, infer headings from font-size/position/numbering cues.
- *AC:* For a book with a real TOC, ≥ 90% of chapters are detected with correct titles.

**FR-0.7 Chunk + contextualize.** Chunk at section level (≈500–1500 tokens), prepending `[Document][Chapter][Section]` context to each chunk before extraction.
- *AC:* No chunk exceeds the model input budget; every chunk carries its structural breadcrumb.

### 4.1 Output 1 — The Brief (Must)

A ~500-word executive summary: thesis, 5 core concepts, 3 key principles, target audience.
- *AC:* Generated from the graph/extractions (not a raw re-summarize of full text).
- *AC:* Every claim links to ≥1 source chapter.
- *AC:* In blind review of 10 known books, ≥ 8 briefs are rated "accurate or mostly accurate" by a reader who knows the book.

### 4.2 Output 2 — The Concept Map (Must)

15–25 concepts, each with: name, one-sentence definition, best-explained chapter, 2–3 related concepts, confidence score.
- *AC:* Concepts are deduplicated (no obvious "DRY" vs. "Don't Repeat Yourself" split for the same idea).
- *AC:* Each concept cites the chapter/section it was extracted from.
- *AC:* Precision ≥ 80% (concepts a domain reader agrees are real and important) on the test set.

### 4.3 Output 3 — The Chapter Guide (Must)

Per chapter: one-sentence summary, concepts introduced, concepts assumed as prerequisite.
- *AC:* Every detected chapter has a guide entry.
- *AC:* "Concepts introduced" reference canonical concept IDs from the Concept Map.

### 4.4 Output 4 — Grounded Q&A (Must)

User asks a natural-language question; system returns an answer grounded on retrieved chunks/graph nodes with chapter citations.
- *AC:* Given "What does this book say about testing?", then the answer cites specific chapter(s)/section(s).
- *AC:* If the book does not cover the topic, the system says so rather than fabricating.
- *AC:* Median answer latency ≤ 8 s; answers reuse cached extractions (no full-book reprocessing per question).

---

## 4.5 MVP Definition of Done

The MVP is "done" when all of the following hold on the acceptance test set (10 known books: ≥3 digital, ≥3 scanned, ≥1 two-column, ≥1 table-heavy):

- [ ] A user can upload a **digital and a scanned** PDF and receive all four outputs.
- [ ] PDF type detection ≥ 95% accurate; scanned PDFs route through OCR with a quality gate.
- [ ] All four outputs render with **100% citation coverage** and visible confidence.
- [ ] Concept precision ≥ 80%; relationship edges are explicit/source-cited only.
- [ ] Q&A returns grounded, cited answers and says "not covered" when appropriate.
- [ ] Per-document cost stays under the cap (< $1 digital / < $2 scanned); telemetry confirms.
- [ ] Latency budgets met at p90 (§6).
- [ ] Low-confidence OCR surfaces a banner; no silent failures.
- [ ] Blind reviewers who know the book rate ≥ 8/10 Briefs "accurate or mostly accurate."

## 5. User Stories (Given / When / Then)

**US-1 — Upload a scanned book**
Given I have a scanned 220-page PDF, when I upload it, then the system detects it is scanned, runs OCR, shows live progress, and on completion presents all four outputs with a scan-quality banner if confidence was low.

**US-2 — Orient fast**
Given processing is complete, when I open the document, then I see The Brief first and can state the thesis and 3 concepts within 10 minutes.

**US-3 — Explore a concept**
Given the Concept Map, when I click a concept, then I see its definition, source chapter, related concepts, and confidence.

**US-4 — Prioritize reading**
Given the Chapter Guide, when I scan it, then I can identify which chapters are essential vs. supplementary and what prerequisites each assumes.

**US-5 — Ask a question**
Given the document is processed, when I ask a natural-language question, then I get a grounded answer with chapter citations, or an explicit "not covered."

**US-6 — Trust check**
Given any concept or answer, when I want to verify it, then I can view the source excerpt/chapter that produced it.

---

## 6. Non-Functional Requirements

| Area | Target |
|---|---|
| **Latency — digital PDF (300 pp)** | End-to-end processing ≤ 5 min (p90) |
| **Latency — scanned PDF (300 pp)** | End-to-end ≤ 12 min (p90) — OCR adds a major step; set expectations in UI |
| **Latency — Q&A** | ≤ 8 s median |
| **Cost — digital doc** | ≤ $1.00 per document (MVP), target ≤ $0.30 by Phase 2 |
| **Cost — scanned doc** | ≤ $2.00 per document (OCR + extra passes); hard cap per doc enforced |
| **Concept precision** | ≥ 80% on test set |
| **Hallucinated relationships** | < 15% of relationship edges flagged incorrect; MVP limits edges to explicit, source-cited statements |
| **OCR word accuracy** | ≥ 95% on clean 300 DPI scans |
| **Citation coverage** | 100% of concepts and Q&A answers carry a source reference |
| **Privacy / retention** | Documents processed and stored per a defined retention policy (default: stored for the user's library; deletable on request). Raw-document storage vs. process-and-discard is an open decision (§10). |
| **Caching** | Extraction results cached; Q&A and re-views never reprocess the full book |

---

## 7. System Pipeline (Conceptual)

```
DROP A PDF
   │
   ▼
[1] INGESTION + TYPE DETECTION
    digital? scanned? hybrid?
   │
   ├── digital ──► [2a] TEXT EXTRACTION (layout-aware)
   │
   └── scanned/hybrid ──► [2b] OCR  ──► text + coords + confidence
                                   │     (OCR QUALITY GATE)
   ▼ (merge)
[3] STRUCTURAL PARSING  → Document ▸ Chapter ▸ Section ▸ Paragraph
   │
   ▼
[4] CHUNK + CONTEXTUALIZE  (prepend [Doc][Chapter][Section])
   │
   ▼
[5] PARALLEL ENTITY + RELATION EXTRACTION (per chunk, confidence-scored)
   │
   ▼
[6] ENTITY RESOLUTION + GRAPH MERGE  (conservative dedup, canonical IDs)
   │
   ▼
[7] SUMMARIZATION LAYER  → Brief · Concept Map · Chapter Guide  (graph-grounded, cited)
   │
   ▼
[8] SERVE + INDEX  → graph store (JSON for MVP) + embeddings for Q&A
   │
   ▼
USER EXPLORES + ASKS Q&A
```

**Where the hard problems live:** PDF/OCR parsing (steps 1–2) cause ~40% of real-world quality failures; entity resolution (step 6) determines graph quality; cross-chapter inference (deferred) is the highest hallucination risk and is **out of MVP**.

---

## 8. Data Model Sketch

### Node types
| Type | Key fields |
|---|---|
| `Concept` | id, name (canonical), definition, confidence, source_refs[] |
| `Principle` | id, statement, stance, confidence, source_refs[] |
| `Term` | id, term, definition, defined_in (section ref) |
| `Example` | id, text, illustrates → Concept.id, source_refs[] |
| `Person` | id, name, role/context |
| `Chapter` / `Section` | id, title, order_index, page_range |
| `Tool` | id, name, kind (language/framework/tool) |

### Edge types
| Edge | Meaning | Notes |
|---|---|---|
| `is_prerequisite_of` | A before B | highest value (Students) |
| `relates_to` | semantic/co-occurrence | weak; for exploration |
| `contrasts_with` | explicit comparison/opposite | high signal |
| `exemplifies` | Example → Concept | enables "show me an example" |
| `is_part_of` | Concept → Chapter / taxonomy | navigation |
| `leads_to` / `enables` | causal/consequential | Practitioner value |
| `defined_in` | Term → Section | lookup |
| `cited_in` | Person → Section | lineage |

### Shared fields (every node & edge)
`source_refs[]` (chapter_id + page_range + char_span), `confidence` (0–1), `extraction_method` (explicit vs. inferred), `created_at`.

**MVP storage:** one JSON graph document per source PDF + an embedding index for Q&A. Defer a real graph DB (Neo4j/Memgraph) to Phase 2.

---

## 9. Dependencies & Key Technical Decisions (with recommended defaults)

| Decision | Recommended default | Rationale |
|---|---|---|
| **PDF parser (digital)** | **PyMuPDF (fitz)** | Fast, accurate text + layout/coords, permissive enough for MVP; good chapter/heading heuristics via font metadata. |
| **OCR engine** | **Cloud OCR API (e.g. a managed Document AI / Textract-class service) as primary; Tesseract as offline fallback** | Managed OCR gives far better accuracy on real-world scans + layout/coords out of the box; Tesseract avoids per-page cost for clean scans and provides a no-network fallback. Validate both in a spike. |
| **Layout/structure for hard PDFs** | Consider **LlamaParse / managed layout parser** for two-column & tables (Should-scope) | Heuristic parsing breaks on multi-column; budget a parser for these in Phase 1 "Should." |
| **LLM tiers** | Cheaper/faster model for per-chunk extraction; stronger model for the Brief + any relationship synthesis | Controls cost; extraction is high-volume, synthesis is low-volume/high-stakes. |
| **Embeddings (Q&A retrieval)** | Standard text-embedding model + lightweight vector index (e.g. FAISS/pgvector) | RAG over chunks is sufficient for MVP Q&A. |
| **Graph storage** | JSON per document (MVP) → graph DB (Phase 2) | Avoid premature infra. |
| **Entity resolution (MVP)** | Conservative lexical/string-similarity merge; prefer under-merge | False merges are worse than duplicates for trust. Semantic resolution is Phase 2. |

> Provider/model selection for extraction vs. synthesis, and the OCR vendor, must be validated by a Week-1 spike against a real cost/accuracy test set before the pipeline is finalized.

---

## 10. Open Questions & Next Steps

### Blocking (resolve Week 1)
1. **Acceptable hallucination rate + detection method** — sets the cost/quality trade-off across the whole pipeline. *(Product decision.)*
2. **OCR vendor choice + unit cost** — now MVP-critical; needs a spike on representative scans (clean, skewed, two-column, low-DPI).
3. **Data privacy / storage policy** — store raw documents or process-and-discard? Drives architecture + any enterprise/legal posture.
4. **PDF parsing library validation** — 1-day spike on 5 representative PDFs (incl. scanned, two-column, table-heavy).

### Non-blocking (can start with defaults)
5. Graph store: JSON now, graph DB later.
6. Q&A grounding: RAG-over-chunks acceptable for MVP; revisit graph-grounded answering in Phase 2.
7. Monetization model (per-doc credits vs. subscription) — informs cost sensitivity; decide post-MVP.

### Recommended next steps
1. Resolve blocking questions 1–3 this week.
2. Run the **PDF + OCR parsing spike** on 5 representative docs; measure extraction quality and per-doc cost (digital vs. scanned).
3. Prototype entity extraction on a single known chapter; measure concept precision/recall vs. a human baseline.
4. Define the entity-resolution merge threshold using 20 near-duplicate pairs from the prototype.
5. Validate the UX hypothesis with 5 target users using a hand-crafted Concept Map + Chapter Guide for a book they know ("Would this change how you read this book?" — need ≥4/5 yes).

---

## 11. Phased Roadmap (updated for OCR-in-MVP)

### Phase 1 — MVP (≈ 9–11 weeks, 2 engineers)
*Original digital-only estimate was 6–8 weeks; pulling OCR forward adds ~3 weeks for the OCR path, quality gate, type detection, and scanned-doc structural parsing, plus higher per-doc cost/latency.*
- Ingestion + **digital and scanned (OCR)** extraction with quality gate
- Structural parsing + contextualized chunking
- Per-chunk extraction + conservative dedup
- Four outputs: Brief, Concept Map, Chapter Guide, Q&A — all source-cited
- Web UI (upload → progress → outputs), cost caps + telemetry

### Phase 2 (≈ 3 months post-MVP)
- Semantic (embedding-based) entity resolution
- Visual interactive graph explorer
- Cross-chapter relationship inference (confidence-gated)
- Learning path / prerequisite tree
- Two-column/table-aware parsing hardening
- User feedback loop ("was this relationship correct?")

### Phase 3 (6+ months)
- Multi-document / cross-book graph
- Domain-tuned extraction
- Reading-app integrations & public API
- Team/org shared knowledge graphs

---

## 12. Risks & Mitigations

| # | Risk | Prob | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **Hallucinated relationships** | High | High | Source-cite every edge; show confidence; MVP limits to explicit statements, not inferred. |
| R2 | **OCR quality on poor scans** (skew, low DPI, handwriting) | High | High | Quality gate + warning banner; managed OCR primary; flag low-confidence pages; never present low-confidence as trustworthy. |
| R3 | **OCR cost/latency blowup** | Med | High | Per-doc hard cost cap; Tesseract fallback for clean scans; cache aggressively; set UI expectations for scanned docs. |
| R4 | **PDF structural parsing failure** (two-column, tables) | High | Med | Type detection + heuristic + managed layout parser for hard cases (Should-scope); explicit failure, not silent. |
| R5 | **Entity-resolution noise** (near-duplicates) | High | Med | Conservative under-merge in MVP; semantic resolution in Phase 2. |
| R6 | **User distrust of AI output** | Med | High | "Verify" affordance: click any claim → see source excerpt; confidence everywhere. |
| R7 | **Cost unit-economics** | Med | High | Process-once/serve-many caching; cheap model for extraction, strong model only for synthesis; per-doc caps. |

---

## 13. Success Metrics

| Metric | Target |
|---|---|
| **Activation** — concept list rated "accurate/mostly accurate" | ≥ 70% of users |
| **Time-to-value** — "orient fast" (thesis + 3 concepts) within 10 min | ≥ 80% of users |
| **Engagement** — viewers who also use Q&A in same session | ≥ 50% |
| **Trust** — concept nodes flagged "incorrect" by users | < 15% |
| **OCR quality** — scanned docs processed without low-confidence banner | ≥ 70% |
| **Retention** — upload a 2nd document within 30 days | ≥ 30% |
| **Cost** — per document | < $1 digital / < $2 scanned (MVP) |

---

*End of PRD v1.0.*
