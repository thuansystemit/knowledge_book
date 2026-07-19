# Issue: OCR "Low Scan Quality" False-Positive Warning

| | |
|---|---|
| **Document** | Issue / Bug-fix Tracking |
| **Product** | KnowledgeBook (Document Knowledge Graph) |
| **Component** | `extraction-service` — OCR quality gate (ING-06) |
| **Date opened** | 2026-07-19 |
| **Status** | IN PROGRESS — OCRQ-01..05 fixed; OCRQ-06 (backfill of already-processed docs) open |
| **Severity** | S3 (Medium) — no data loss; erodes user trust with a misleading warning |
| **Reporter** | pvthuan (verified via `document-extractor` agent) |
| **Parents** | `FEATURE-extraction-fine-tuning.md`, `SPIKE-week1-pdf-ocr.md`, `ARCHITECTURE-mvp.md` |
| **Companion** | `ISSUE-ocr-quality-false-positive.ctx.md` (AI-agent digest) |

---

## 0. How to read & update this document (the standard)

This document follows the KnowledgeBook **issue-tracking standard** so that both humans
and AI agents can act on it without re-investigating from scratch. Every issue doc in
`docs/ISSUE-*.md` MUST contain, in order:

1. **Header table** — identity, status, severity, ownership, parent docs, companion.
2. **§1 Summary** — one paragraph a newcomer can read in 30 seconds.
3. **§2 Evidence** — reproducible, dated, with concrete data (IDs, values, file:line).
4. **§3 Root cause** — the *why*, pointing at exact `file:line` in the codebase.
5. **§4 Fix tasks** — a table of atomic tasks with **stable IDs** (`OCRQ-NN`), each with
   impact, risk, and the exact files/lines to change.
6. **§5 Acceptance criteria** — objective, testable pass/fail conditions.
7. **§6 Verification plan** — how to prove the fix works (commands, expected output).
8. **§7 Out of scope / non-goals** — what this issue deliberately does NOT change.
9. **§8 Changelog** — dated status transitions.

**Rules for both humans and AI agents:**
- **Task IDs are immutable.** Never renumber `OCRQ-NN`. Mark done tasks `[x]`; never delete them.
- **Cite evidence, don't assert.** Every root-cause claim links to a `file:line` or a data value.
- **Keep the `.ctx.md` companion in sync** — it is the self-contained AI digest of this file.
- **Update §8 Changelog** on every status change; convert relative dates to absolute (YYYY-MM-DD).
- **Status vocabulary:** `OPEN` → `IN PROGRESS` → `FIXED` (code merged) → `VERIFIED` (acceptance met) → `CLOSED`.
- An AI agent picking this up should read `.ctx.md` first, then this file's §3–§6, then touch code.

---

## 1. Summary

The extraction UI shows a scary warning — *"Low scan quality. This document was read by
OCR at 44.3% average confidence on 12 page(s). Concepts and answers may contain
recognition errors — verify against the source PDF."* — on documents whose extracted
content is actually **correct**. Investigation of a concrete case ("Designing
Data-Intensive Applications", job `24a2c7e7ea1046ec9b3c42ce6ef477c2`) confirmed the
warning is a **false positive**: the PDF is a native-text (digitally typeset) document,
OCR only ran on 12 non-content pages (4 of them intentionally **blank** separator pages),
and all 99 spot-checked concepts matched the source text. The low average is a
measurement artifact — blank pages OCR at ~0% and drag the mean below the 70% threshold.

---

## 2. Evidence

### 2.1 The warning (frontend)
Rendered in `frontend/src/routes/DocumentDetailPage.tsx:269-276` whenever
`graph.ocr_quality.low_confidence === true`. Text + page count + `mean_confidence` are
interpolated verbatim.

### 2.2 The offending metadata (backend, from DB)
Job `24a2c7e7ea1046ec9b3c42ce6ef477c2` — *Designing Data-Intensive Applications*:
```json
{"ocr_used": true, "mean_confidence": 44.3, "low_confidence": true,
 "threshold": 70.0,
 "low_pages": [23, 47, 89, 131, 171, 219, 241, 293, 341, 409, 459, 509]}
```

### 2.3 Ground-truth check (via `document-extractor` agent, 2026-07-19)
- The PDF is **native text**, not a scan: producer `AH CSS Formatter V6.0`, embedded
  fonts (MinionPro, UbuntuMono, GuardianSans). ~96% of pages have a clean text layer;
  OCR was never needed for them.
- The 12 "low" pages are **non-content pages**:
  - **4 are intentionally blank** chapter-separator pages (~70-byte content streams) →
    OCR confidence ≈ 0% → these dominate the average.
  - The rest are **bibliography / part-intro** pages (DOIs, URLs, sparse text) that OCR
    legitimately scores low but that contribute little/no concept content.
- **0 of 99** concepts attributed to those pages were corrupted. Samples verified against
  the book text: *Edgar Codd*, *Split Brain*, *Eventual Consistency*, *Index*,
  *Batch Processing*, *Exactly-once semantics* — all faithful.
- The "garbling" originally suspected (`SPARQL, 59-59`) is a **legitimate index entry**
  (single-page span), not an OCR error.

**Conclusion:** the score is real but the *interpretation* ("content may be wrong") is
false for native-text PDFs and for documents whose low pages are blank/furniture.

---

## 3. Root cause

All in `extraction-service/app/extraction/text_extractor.py::_from_pdf`:

| # | Cause | Location |
|---|---|---|
| RC-1 | **Blank pages are sent to OCR.** A page routes to OCR whenever its text layer is under `_PAGE_TEXT_MIN_CHARS`. A blank separator page has 0 chars, so it is OCR'd — and scores ≈0%. | `text_extractor.py:108-109` |
| RC-2 | **The mean averages in those near-0 pages.** `mean_confidence` is computed over *all* OCR'd pages with no filtering of blank/empty results, so a handful of blank pages collapse the average. | `text_extractor.py:117-124` |
| RC-3 | **No native-text-PDF detection.** There is no document-level check that most pages already have a clean text layer; a 4%-OCR document is treated the same as a 100%-scanned one. | `text_extractor.py:104-131` |
| RC-4 | **Document-level warning from a page-subset metric.** `low_confidence` is a single boolean derived from the average, then shown as a whole-document warning implying *all* concepts are suspect. | `text_extractor.py:128`; consumed at `frontend/.../DocumentDetailPage.tsx:269` |

---

## 4. Fix tasks

> IDs are stable and immutable. Check off `[x]` when merged; record in §8.

| ID | Task | Impact | Risk | Files / lines |
|---|---|---|---|---|
| **OCRQ-01** | ✅ **DONE.** Exclude pages OCR returns empty/whitespace text for from the confidence set (blank separators, image-only covers). Implemented in `_summarize_ocr_quality` (`if not txt.strip(): continue`). | Removes the ~0% samples that dominate the mean | Low | `text_extractor.py` `_summarize_ocr_quality` |
| **OCRQ-02** | ✅ **DONE.** Empty OCR results skipped from `confs` and `low_pages`; mean reflects only pages with real recognized text. | Mean reflects only pages with actual recognized text | Low | `text_extractor.py` `_summarize_ocr_quality` |
| **OCRQ-03** | ✅ **DONE.** Native-text gate: `ocr_page_ratio = recognised_pages/total_pages`; doc-level `low_confidence` only trips when `ocr_page_ratio >= OCR_DOC_MIN_RATIO` (default 0.5). New setting `ocr_doc_min_ratio` in `config.py`. | Kills the false positive for mostly-digital PDFs | Medium | `text_extractor.py` `_summarize_ocr_quality`; `config.py` |
| **OCRQ-04** | ✅ **DONE (partial).** `ocr_page_ratio` now added to the `quality` dict (surfaced in `ocr_quality`). Blank-excluded `low_pages` already covered by OCRQ-01/02. A separate `content_low_pages` field was not needed. | Enables accurate UX | Low | `text_extractor.py` `_summarize_ocr_quality` |
| **OCRQ-05** | ✅ **DONE.** UI now branches: strong `alert-warning` "Low scan quality" only when `low_confidence` (genuine scan, backend-gated by OCRQ-03); otherwise a soft `alert-info` page-scoped note when OCR ran on a few pages of a mostly born-digital PDF. `ocr_page_ratio` added to the frontend `ocr_quality` type. | Trustworthy messaging | Low | `frontend/src/routes/DocumentDetailPage.tsx:266-289`; `frontend/src/api/jobs.api.ts:25-29` |
| **OCRQ-06** *(optional)* | **Backfill existing jobs.** Recompute `ocr_quality` / clear stale `low_confidence` for already-processed native-text docs, OR document that the flag self-corrects on reprocess. No re-OCR needed for the ratio gate. | Fixes historical false positives | Low | one-off script under `scripts/` |

---

## 5. Acceptance criteria

- **AC-1** For job `24a2c7e7ea1046ec9b3c42ce6ef477c2` (DDIA), after reprocess: the
  document-level `low_confidence` flag is **false** (native-text gate, OCRQ-03), and the
  UI shows no "Low scan quality" banner (OCRQ-05).
- **AC-2** Blank separator pages do **not** appear in `low_pages` and do **not** affect
  `mean_confidence` (OCRQ-01/02).
- **AC-3** A genuinely scanned, low-quality PDF (high `ocr_page_ratio`, low mean) **still**
  raises `low_confidence` and shows the warning — no regression of the true positive.
- **AC-4** `ocr_quality` now includes `ocr_page_ratio` and a blank-excluded low-page count.
- **AC-5** Existing extraction eval harness (`scripts/eval_extraction.py`) passes; add a
  fixture asserting AC-2/AC-3 behaviour.

---

## 6. Verification plan

1. **Unit** — feed `_from_pdf` a synthetic PDF: 10 native-text pages + 2 blank pages.
   Assert `low_confidence is False`, `low_pages == []` (blanks excluded), `ocr_page_ratio`
   ≈ 0.17.
2. **Regression (true positive)** — feed a fully image-only, low-DPI scan; assert
   `low_confidence is True` and the warning renders.
3. **Real case** — reprocess DDIA (`POST /api/jobs/{id}/reprocess`) and confirm AC-1 in
   the UI and in `graph.ocr_quality`.
4. **Command sanity**:
   ```bash
   docker exec extraction-service-db-1 psql -U kb -d kb -tAc \
     "select graph::json->'ocr_quality' from jobs where id='24a2c7e7ea1046ec9b3c42ce6ef477c2';"
   # expect: low_confidence:false, ocr_page_ratio present
   ```

---

## 7. Out of scope / non-goals

- Not changing the OCR engine, DPI, or Tesseract config (`_OCR_CONFIG`).
- Not improving OCR accuracy on genuinely scanned documents — this issue is purely about
  the **false-positive warning** and confidence accounting.
- Not touching concept-extraction quality (covered by `FEATURE-extraction-fine-tuning.md`).
- Concept de-duplication (`Data Model` vs `Data Models`) is a separate extraction concern,
  noted here only as an incidental finding.

---

## 8. Changelog

| Date | Status | Note |
|---|---|---|
| 2026-07-19 | OPEN | Issue filed. Root cause identified in `text_extractor.py`; verified false-positive on DDIA via `document-extractor` agent. Fix tasks OCRQ-01..06 defined. |
| 2026-07-19 | IN PROGRESS | OCRQ-01/02/03/04 implemented: confidence accounting extracted to pure `_summarize_ocr_quality`; blank pages excluded from mean/low_pages; native-text gate via new `ocr_doc_min_ratio` (default 0.5); `ocr_page_ratio` added to `ocr_quality`. Unit tests in `tests/test_ocr_quality.py` (5 cases, AC-1/2/3 covered) — all pass. DDIA case now yields `low_confidence:false`; genuine full scan still flags true. Images rebuilt. |
| 2026-07-19 | IN PROGRESS | OCRQ-05 implemented: `DocumentDetailPage` branches strong `alert-warning` (genuine scan) vs. soft `alert-info` page-scoped note (mostly-digital PDF); frontend `ocr_quality` type extended with `ocr_page_ratio`. Frontend typecheck passes; container rebuilt and new copy verified in the served bundle. **Caveat:** documents processed *before* this fix (e.g. DDIA) still carry the old `ocr_quality` (`low_confidence:true`, no `ocr_page_ratio`) and will keep showing the strong banner until reprocessed — that is OCRQ-06. |

---

*See `ISSUE-ocr-quality-false-positive.ctx.md` for the self-contained AI-agent digest.*
