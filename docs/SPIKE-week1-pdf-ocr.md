# Spike Plan: Week-1 PDF Parsing + OCR De-Risking

| | |
|---|---|
| **Document** | Technical Spike Plan |
| **Spike** | PDF parsing + OCR — ingestion path validation |
| **Version** | 1.0 |
| **Date** | 2026-06-28 |
| **Status** | DRAFT — ready to execute |
| **Owner** | Engineering |
| **Parent** | `PRD-knowledge-graph-mvp.md` v1.0 (resolves Open Questions Q2, Q4; informs Q1, Q3) |
| **Timebox** | 5 working days, 1–2 engineers. **Hard stop** — a spike is for learning, not production code. |

> A spike is a timeboxed experiment to buy information and retire risk, not to build the product. Output is **evidence + a decision**, not a feature. Every measurement below is reproducible from the same corpus and scripts so a reviewer can re-run it.

---

## 1. Why this spike (risk being retired)

The PRD identifies ingestion (PDF parse + OCR) as the source of ~40% of real-world quality failures, and pulling OCR into the MVP makes vendor choice and cost MVP-critical. Two PRD open questions are **blocking** and depend on evidence we do not yet have:

- **Q2 (blocking):** OCR vendor choice + unit cost.
- **Q4 (blocking):** PDF parser validation on representative documents.

This spike retires those by measuring real parsers/OCR engines against a controlled corpus. It also feeds **Q1** (hallucination/quality baseline depends on extraction text quality) and **Q3** (privacy — whether a managed cloud OCR is viable depends on its measured advantage over local).

**If we skip this spike,** we risk picking an OCR/parser stack that blows the cost cap (<$2/scanned doc), misses the 95% OCR-accuracy bar, or fails on two-column/table layouts — discovered weeks into the build, forcing a pipeline rewrite.

---

## 2. Hypotheses to test (falsifiable)

Each hypothesis has an explicit pass condition. The spike's job is to confirm or kill each one.

| # | Hypothesis | Pass condition |
|---|---|---|
| **H1** | PyMuPDF extracts clean digital PDFs with ≥ 98% character fidelity and usable reading order. | ≥ 98% char fidelity on ≥ 3/3 digital docs; reading order correct on single-column. |
| **H2** | We can auto-detect digital vs. scanned vs. hybrid PDFs cheaply and reliably. | ≥ 95% correct classification on the 10-doc corpus using a cheap heuristic (text-layer coverage ratio). |
| **H3** | A managed cloud OCR service hits ≥ 95% word accuracy on clean 300 DPI scans. | ≥ 95% word accuracy on ≥ 2/2 clean scans; degraded but graceful on skewed/low-DPI. |
| **H4** | Tesseract is a viable offline fallback for *clean* scans (cost $0). | Within 3 percentage points of cloud OCR word accuracy on clean scans. |
| **H5** | Scanned-doc unit cost stays under the $2/doc cap at MVP volumes. | Measured per-300pp-doc OCR cost < $2 (cloud) with parallelization. |
| **H6** | Heading/chapter structure is recoverable from font/position cues (digital) and from OCR coordinates (scanned). | ≥ 90% chapters detected with correct titles on docs that have a TOC. |
| **H7** | Two-column / table layouts need a dedicated layout parser (heuristics insufficient). | Demonstrate heuristic failure + measure a managed layout parser's improvement on the two-column + table docs. |

---

## 3. Test corpus (controlled, 10 documents)

The corpus is fixed and version-controlled so results are reproducible. Each doc gets a small **ground-truth sample** (see §4) — we do NOT hand-transcribe whole books.

| ID | Type | Characteristic | Purpose |
|---|---|---|---|
| D1 | Digital | Clean single-column technical book (e.g. The Pragmatic Programmer) | H1, H6 baseline |
| D2 | Digital | Has TOC + numbered chapters | H6 structure |
| D3 | Digital | Two-column academic paper | H7 |
| D4 | Digital | Table/figure-heavy report | H7 |
| D5 | Scanned | Clean 300 DPI book scan | H3, H4 |
| D6 | Scanned | Clean 300 DPI, different font | H3, H4 |
| D7 | Scanned | Skewed / rotated pages | H3 robustness |
| D8 | Scanned | Low-DPI (≤150) / noisy | H3 quality-gate trigger |
| D9 | Hybrid | Digital text + scanned inserts | H2 routing |
| D10 | Scanned | Two-column scanned | H3 + H7 worst case |

**Ground-truth method:** for each doc, select **5 representative pages** spread across front/middle/back. Hand-verify text on those pages (or use publisher text where legally available) as the accuracy reference. This keeps effort bounded while giving a statistically useful sample.

---

## 4. Methodology & metrics

### Candidates under test
- **Digital parse:** PyMuPDF (primary), pdfplumber (comparison on tables).
- **OCR:** one managed cloud OCR (Document-AI / Textract-class) vs. Tesseract (local).
- **Layout (hard docs):** one managed layout parser (e.g. LlamaParse-class) for D3/D4/D10.

### Metrics (all computed by script, logged to CSV)
| Metric | Definition | Target |
|---|---|---|
| **Char fidelity** | 1 − (Levenshtein / ref_len) on sample pages | ≥ 98% digital |
| **OCR word accuracy** | 1 − WER on sample pages | ≥ 95% clean scan |
| **Type-detect accuracy** | correct/total classifications | ≥ 95% |
| **Chapter detection** | correct-title chapters / total chapters | ≥ 90% (docs w/ TOC) |
| **Reading-order correctness** | manual 0–2 score per sample page | ≥ 1.5 avg single-column |
| **Per-doc cost** | OCR/parse API spend per 300pp-equivalent | < $2 scanned, < $1 digital |
| **Per-doc latency** | wall-clock, parallelized | ≤ 5min digital / ≤ 12min scanned (p90 proxy) |

### Procedure
1. Pin corpus + tool versions in the repo (`spike/corpus/`, `spike/requirements.txt`).
2. Run each candidate over all applicable docs; capture text, coords, confidence, timing, cost.
3. Score against ground-truth sample pages with the scoring script.
4. Record every result in `spike/results/results.csv` (one row per doc×tool×metric) — raw, no cherry-picking.
5. Note qualitative failures (column bleed, table collapse, header/footer noise) with page screenshots.

---

## 5. Day-by-day plan (timeboxed)

| Day | Focus | Exit artifact |
|---|---|---|
| **1** | Assemble + pin corpus; build ground-truth sample pages; scaffold scoring scripts (Levenshtein/WER, type-detect). | Reproducible corpus + scoring harness. |
| **2** | Digital path: PyMuPDF (+pdfplumber on tables). Measure H1, H6, reading order. | `results.csv` digital rows + structure findings. |
| **3** | OCR path: cloud OCR vs. Tesseract on D5–D10. Measure H3, H4, H5 (accuracy + cost + latency). | OCR accuracy/cost table. |
| **4** | Type detection (H2) on full corpus; hard layouts (H7) — heuristic vs. managed layout parser on D3/D4/D10. | Detection accuracy + layout comparison. |
| **5** | Consolidate evidence; fill decision matrix; write findings + recommendation; update PRD open questions. | **Spike report + decisions** (this doc's §7). |

---

## 6. Deliverables (Definition of Done for the spike)

The spike is done when ALL exist and are checked in under `spike/`:

- [ ] Pinned corpus (`spike/corpus/`) + ground-truth sample pages.
- [ ] Reproducible scoring scripts (`spike/scoring/`) + `requirements.txt`.
- [ ] Raw results CSV (`spike/results/results.csv`) — every doc×tool×metric.
- [ ] Qualitative failure notes + screenshots for layout issues.
- [ ] A filled **decision matrix** (§7) with a clear recommendation per choice.
- [ ] PRD open questions Q2 + Q4 marked **resolved** with the chosen stack + rationale + measured numbers; Q1/Q3 updated with evidence.
- [ ] A one-paragraph "what surprised us" note (risks discovered).

> Explicit non-goal: no production ingestion code, no UI, no pipeline wiring. Throwaway scripts are expected and acceptable.

---

## 7. Decision matrix (to be filled by Day 5)

| Decision | Candidates | Chosen | Measured evidence | Confidence |
|---|---|---|---|---|
| Digital PDF parser | PyMuPDF / pdfplumber | _TBD_ | char fidelity, reading order | _TBD_ |
| OCR engine (primary) | Cloud OCR / Tesseract | _TBD_ | word acc, cost, latency | _TBD_ |
| OCR fallback | Tesseract / none | _TBD_ | clean-scan accuracy gap | _TBD_ |
| Type detection method | text-layer ratio heuristic / other | _TBD_ | detect accuracy | _TBD_ |
| Hard-layout strategy | heuristic / managed layout parser | _TBD_ | two-column + table quality | _TBD_ |
| Scanned cost viability | — | go / no-go vs. $2 cap | per-doc cost | _TBD_ |

---

## 8. Risks to the spike itself

| Risk | Mitigation |
|---|---|
| Corpus not representative → false confidence | Fix the 10-doc spread up front; include worst cases (D7, D8, D10). |
| Ground-truth effort balloons | Hard-limit to 5 sample pages/doc. |
| Cloud OCR signup/credentials delay | Start vendor access Day 0; Tesseract works offline as parallel track. |
| Scope creep into building the pipeline | Hard timebox; throwaway scripts only; daily exit artifacts. |
| Cost measurement unrealistic at n=10 | Extrapolate per-page cost × 300pp; flag assumption explicitly. |

---

## 9. Feeds back into

- **PRD Q2, Q4** → resolved (chosen OCR + parser, with numbers).
- **PRD Q1** → extraction text-quality baseline informs achievable hallucination/precision targets.
- **PRD Q3** → measured cloud-vs-local OCR gap informs the privacy/storage trade-off (is cloud OCR worth the data exposure?).
- **Architecture phase** → confirmed ingestion components + cost/latency inputs for the pipeline design.

---

*End of Spike Plan v1.0.*
