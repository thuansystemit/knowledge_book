# CTX: OCR "Low Scan Quality" false-positive warning

> **AI digest of `ISSUE-ocr-quality-false-positive.md`. Self-contained — read this alone.**
> Status: IN PROGRESS (2026-07-19). OCRQ-01..05 DONE; OCRQ-06 (backfill of pre-fix docs) open. Severity S3. Convention: paired `*.ctx.md`; keep in sync.
> Standard: `docs/ISSUE-*.md` = header table → summary → evidence → root cause → fix tasks (stable IDs) → acceptance → verification → non-goals → changelog. Task IDs immutable; check off, never delete.

## What / why it matters
The UI shows *"Low scan quality … read by OCR at 44.3% average confidence on 12 page(s) … may contain recognition errors"* on documents whose extracted content is actually **correct**. It is a **false positive** that erodes user trust. No data loss. This is a warning/measurement bug, NOT an extraction-quality bug.

## Verified case (ground truth)
- Job `24a2c7e7ea1046ec9b3c42ce6ef477c2` = "Designing Data-Intensive Applications" (Kleppmann).
- `ocr_quality = {ocr_used:true, mean_confidence:44.3, low_confidence:true, threshold:70.0, low_pages:[23,47,89,131,171,219,241,293,341,409,459,509]}`.
- PDF is **native-text** (producer `AH CSS Formatter V6.0`, embedded fonts), NOT a scan. ~96% of pages have a clean text layer; OCR only ran on 12 pages.
- 4 of the 12 low pages are **intentionally blank** separator pages → OCR ≈0% → they drag the mean below 70%. Rest are bibliography/part-intro furniture.
- `document-extractor` agent (2026-07-19) checked 99 concepts on those pages vs the book: **0 corrupted**. (`SPARQL, 59-59` = valid index entry, not garbling.)

## Root cause — all in `extraction-service/app/extraction/text_extractor.py::_from_pdf`
- **RC-1** blank pages get OCR'd: page routes to OCR when text-layer chars `< _PAGE_TEXT_MIN_CHARS` → blank (0 chars) qualifies → scores ~0%. `text_extractor.py:108-109`.
- **RC-2** `mean_confidence` averages in those ~0% blank pages (no filtering). `text_extractor.py:117-124`.
- **RC-3** no native-text-PDF detection; a 4%-OCR doc treated like a 100%-scanned doc. `text_extractor.py:104-131`.
- **RC-4** a page-subset average becomes a document-level `low_confidence` boolean, shown as a whole-doc warning. `text_extractor.py:128` → `frontend/src/routes/DocumentDetailPage.tsx:269-276`.

## Fix tasks (stable IDs — do not renumber)
| ID | Task | Files |
|---|---|---|
| OCRQ-01 ✅ | Exclude empty-OCR (blank) pages from confidence set | done — `_summarize_ocr_quality` |
| OCRQ-02 ✅ | Exclude empty OCR results from `mean_confidence`/`low_pages` | done — `_summarize_ocr_quality` |
| OCRQ-03 ✅ | Native-text gate: `ocr_page_ratio`; doc `low_confidence` only if `>= OCR_DOC_MIN_RATIO` (default 0.5) | done — `_summarize_ocr_quality` + `config.ocr_doc_min_ratio` |
| OCRQ-04 ✅ | Add `ocr_page_ratio` to `ocr_quality` dict | done — `_summarize_ocr_quality` |
| OCRQ-05 ✅ | UI branch: strong `alert-warning` when `low_confidence` (genuine scan, backend-gated); else soft `alert-info` page-scoped note; `ocr_page_ratio` added to FE type | done — `DocumentDetailPage.tsx:266-289`, `jobs.api.ts:25-29` |
| OCRQ-06 ⬜ (opt) | Backfill/reprocess historical native-text docs to clear stale flag | `scripts/` |

**Implementation note:** confidence accounting lives in pure helper `_summarize_ocr_quality(recognised, total_pages, threshold, min_ratio)` in `text_extractor.py` (called by `_from_pdf`). Tests: `tests/test_ocr_quality.py` (5 cases). Note `low_confidence` now needs BOTH mean<threshold AND ratio>=min_ratio — reprocessing a native-text doc clears the stale flag (relevant to OCRQ-06).

## Acceptance (objective)
- AC-1: DDIA reprocess → doc-level `low_confidence == false`, no UI banner.
- AC-2: blank pages absent from `low_pages`, don't affect `mean_confidence`.
- AC-3: genuinely scanned low-quality PDF STILL warns (no true-positive regression).
- AC-4: `ocr_quality` includes `ocr_page_ratio` + blank-excluded low count.
- AC-5: `scripts/eval_extraction.py` passes; add fixture for AC-2/AC-3.

## Guardrails / non-goals
- Do NOT change OCR engine/DPI/`_OCR_CONFIG` or try to improve scan accuracy.
- Do NOT touch concept extraction quality (that's `FEATURE-extraction-fine-tuning.md`).
- Concept dedup (`Data Model` vs `Data Models`) is incidental, out of scope.
- Preserve the true-positive path: real scans must still raise the warning.

## Key file pointers
- `extraction-service/app/extraction/text_extractor.py` — `_from_pdf` (lines ~96-134), `_ocr_pdf_pages`, `_reconstruct`.
- `extraction-service/app/config.py` — `ocr_min_confidence` (threshold 70), add `ocr_doc_min_ratio`.
- `extraction-service/app/api.py:537-538` — metrics surface of low-confidence.
- `frontend/src/routes/DocumentDetailPage.tsx:269-276` — the warning render.
- `frontend/src/api/jobs.api.ts:26` — `ocr_quality` typing (extend for new fields).
