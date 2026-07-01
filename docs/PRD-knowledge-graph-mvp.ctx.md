# CTX: PRD — Document Knowledge Graph MVP

> **AI digest of `PRD-knowledge-graph-mvp.md`. Self-contained — read this alone; you do NOT need the full `.md`.**
> Pairs with: `PRD-knowledge-graph-mvp.md` (v1.0, 2026-06-28, DRAFT).
> Convention: every phase doc has a `*.ctx.md` AI digest. Keep this in sync when the `.md` changes.

## What this product is
AI system that ingests a long document (200–400pp book/report/paper, PDF) and builds a **knowledge graph** of concepts + relationships so a human understands it fast without reading it all. **Not summarization** — a navigable semantic map. Working title: "KnowledgeBook".

## Locked product decisions (do not relitigate)
1. **All four outputs ship together** as co-equal heroes: Brief, Concept Map, Chapter Guide, grounded Q&A.
2. **OCR is table-stakes in MVP** — scanned/image PDFs supported at launch (NOT deferred). This expanded scope from the original digital-only plan.
3. Full MVP PRD already written (v1.0).

## The four MVP outputs (all Must, all source-cited)
- **Brief** — ~500-word exec summary: thesis, 5 core concepts, 3 principles, audience. Graph-grounded, every claim cites ≥1 chapter.
- **Concept Map** — 15–25 concepts; each: name, 1-sentence definition, best chapter, 2–3 related concepts, confidence. Deduped. Precision target ≥80%.
- **Chapter Guide** — per chapter: 1-sentence summary, concepts introduced, prerequisite concepts.
- **Q&A** — NL question → grounded answer + chapter citations; says "not covered" instead of fabricating; reuses cache (no full-book reprocess); ≤8s median.

## Assumptions (challengeable)
A1 non-fiction/technical structured docs (not fiction). A2 PDF-only MVP (no EPUB/DOCX/HTML). A3 English-only quality targets. A4 managed cloud OCR available + acceptable (pending privacy decision). A5 conservative under-merge is the right entity-resolution trust trade-off. A6 RAG-over-chunks Q&A sufficient for MVP (graph-grounded = Phase 2). A7 budgets assume parallel per-chunk + aggressive caching.

## MVP Definition of Done (on 10-book test set: ≥3 digital, ≥3 scanned, ≥1 two-column, ≥1 table-heavy)
digital+scanned upload → all 4 outputs · type-detect ≥95% · scanned→OCR+quality-gate · 100% citation coverage + visible confidence · concept precision ≥80% · edges explicit/cited only · Q&A grounded+cited, "not covered" when apt · cost < $1 digital / < $2 scanned (telemetry) · latency p90 met · low-confidence OCR banner, no silent fail · ≥8/10 Briefs rated accurate by readers who know the book.

## Pipeline (where OCR fits)
`Upload → [1] type-detect (digital/scanned/hybrid) → [2a] digital text extract OR [2b] OCR (+coords+confidence, QUALITY GATE) → [3] structural parse (Doc▸Chapter▸Section▸Paragraph) → [4] chunk + prepend [Doc][Chapter][Section] context → [5] parallel per-chunk entity+relation extraction (confidence-scored) → [6] conservative entity-resolution/dedup (canonical IDs, prefer UNDER-merge) → [7] graph-grounded summaries (Brief/Map/Guide) → [8] serve: JSON graph + embedding index for Q&A`
- Hardest failure points: PDF/OCR parsing (~40% of real-world quality failures), entity resolution (graph quality), and cross-chapter inference (highest hallucination → **OUT of MVP**).

## Data model
- **Nodes:** Concept, Principle, Term, Example, Person, Chapter/Section, Tool.
- **Edges:** is_prerequisite_of (highest value), relates_to, contrasts_with, exemplifies, is_part_of, leads_to/enables, defined_in, cited_in.
- **Every node+edge carries:** `source_refs[]` (chapter_id+page_range+char_span), `confidence` (0–1), `extraction_method` (explicit|inferred). 100% citation coverage required.
- MVP storage = one JSON graph per PDF + embedding index. Graph DB deferred to Phase 2.

## Recommended technical defaults (validate in Week-1 spike before finalizing)
- **Digital PDF parser:** PyMuPDF (fitz) — fast, layout/coords, font-metadata heading heuristics.
- **OCR:** managed cloud Document-AI/Textract-class service primary; **Tesseract** offline fallback for clean scans.
- **Hard layouts (two-column/tables):** managed layout parser (e.g. LlamaParse) — Should-scope.
- **LLM tiers:** cheap/fast model for high-volume per-chunk extraction; stronger model only for Brief/synthesis (cost control).
- **Q&A:** RAG over chunks (FAISS/pgvector) acceptable for MVP.
- **Entity resolution MVP:** conservative lexical/string-similarity; under-merge beats false-merge (trust).

## Non-functional budgets
- Latency p90: digital 300pp ≤5min; **scanned 300pp ≤12min** (OCR adds a step — set UI expectations); Q&A ≤8s median.
- Cost/doc: **≤$1 digital, ≤$2 scanned** (MVP); hard per-doc cap enforced. Target ≤$0.30 by Phase 2.
- Quality: concept precision ≥80%; hallucinated edges <15% (MVP edges = explicit/cited only); OCR word-accuracy ≥95% on clean 300DPI; OCR quality gate shows banner + flags low-confidence pages (never silent-drop, never present low-confidence as trustworthy).
- Privacy/retention: store-vs-discard is an OPEN blocking decision.

## Scope (MoSCoW)
- **Must:** digital + scanned(OCR) ingest, type detection, quality gate, structural parse, per-chunk extraction, conservative dedup, the 4 outputs, citations+confidence, web UI (upload→progress→outputs), cost caps+telemetry.
- **Should:** two-column/table handling, re-process, export MD/JSON, basic auth + per-user library.
- **Could:** visual graph explorer, semantic entity resolution, cross-chapter inference (gated), learning-path tree, shareable concept cards.
- **Won't (now):** multi-doc/cross-book graph, fine-tuned domain models, reading-app integrations, team/org collab, real-time annotation.

## Roadmap
- **MVP ≈9–11 weeks, 2 eng** (was 6–8 digital-only; +~3wks for OCR path/quality-gate/type-detection/scanned structural parse + higher cost/latency).
- **Phase 2 (~3mo):** semantic entity resolution, visual graph explorer, confidence-gated cross-chapter inference, learning-path tree, two-column/table hardening, feedback loop.
- **Phase 3 (6mo+):** multi-doc graph, domain-tuned extraction, reading-app integrations + public API, team/org shared graphs.

## Top risks → mitigations
- Hallucinated relationships (H/H) → cite every edge, show confidence, MVP=explicit-only.
- OCR quality on poor scans (H/H) → quality gate + warning banner, managed OCR primary, flag low-confidence.
- OCR cost/latency blowup (M/H) → hard cap, Tesseract fallback for clean scans, cache, UI expectations.
- Structural parse failure on two-column/tables (H/M) → managed layout parser (Should), explicit failure not silent.
- Entity-resolution noise (H/M) → conservative under-merge MVP; semantic in Phase 2.
- User distrust (M/H) → "verify" affordance: click claim → source excerpt; confidence everywhere.

## Success metrics
Activation ≥70% rate concepts accurate · Time-to-value ≥80% orient (thesis+3 concepts) in 10min · Q&A engagement ≥50% · Trust <15% concepts flagged wrong · OCR ≥70% docs no low-confidence banner · Retention ≥30% 2nd doc in 30d · Cost <$1 digital/<$2 scanned.

## OPEN — blocking, resolve Week 1
1. Acceptable hallucination rate + detection method (product decision; sets cost/quality trade-off).
2. OCR vendor choice + unit cost (now MVP-critical; spike on clean/skewed/two-column/low-DPI scans).
3. Data privacy/storage policy: store raw docs vs. process-and-discard (drives architecture + legal posture).
4. PDF parser validation: 1-day spike on 5 representative PDFs (incl. scanned, two-column, table-heavy).

## Next-step options offered to user (pending choice)
(a) Run Week-1 PDF+OCR parsing spike · (b) architect agent designs pipeline from PRD · (c) edit PRD first.

## Process note
Earlier the product-manager subagent deadlocked refusing coordinator-relayed user confirmation (no direct user→subagent channel exists). PRD was authored inline instead. Per project convention: **work inline, not via subagents** for these phase docs.
