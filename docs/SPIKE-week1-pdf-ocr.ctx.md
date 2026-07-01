# CTX: Week-1 PDF+OCR Spike Plan

> **AI digest of `SPIKE-week1-pdf-ocr.md`. Self-contained — read this alone; you do NOT need the full `.md`.**
> Parent: `PRD-knowledge-graph-mvp.md` v1.0 (+ its `.ctx.md`). Convention: every phase doc has a paired `*.ctx.md`; keep in sync; work inline.
> Audience note: deliverables reviewed externally by OpenAI — every number reproducible, no cherry-picking.

## Purpose
5-day timeboxed spike (1–2 eng) to RETIRE RISK on the ingestion path, not build product. Output = **evidence + decisions**, throwaway scripts OK. Resolves PRD blocking open questions **Q2 (OCR vendor+cost)** and **Q4 (PDF parser validation)**; informs **Q1 (hallucination baseline depends on text quality)** and **Q3 (privacy: is cloud OCR's advantage worth the data exposure)**. Skipping it risks picking a stack that blows the <$2/scanned cap, misses 95% OCR accuracy, or fails on two-column/tables — discovered too late.

## Hypotheses (falsifiable, each has a pass condition)
- **H1** PyMuPDF ≥98% char fidelity + correct reading order on clean digital.
- **H2** digital/scanned/hybrid auto-detect ≥95% via cheap text-layer-coverage heuristic.
- **H3** managed cloud OCR ≥95% word accuracy on clean 300DPI scans; graceful on skew/low-DPI.
- **H4** Tesseract within 3pp of cloud on clean scans → viable $0 fallback.
- **H5** scanned per-300pp-doc OCR cost < $2 cap (parallelized).
- **H6** chapter/heading recoverable ≥90% (font/position digital; OCR coords scanned) on TOC docs.
- **H7** two-column/tables need a managed layout parser (heuristics insufficient) — show failure + measure parser improvement.

## Corpus (fixed, 10 docs, version-controlled)
D1 clean digital book · D2 digital w/ TOC · D3 two-column paper · D4 table-heavy report · D5/D6 clean 300DPI scans · D7 skewed scan · D8 low-DPI/noisy scan · D9 hybrid · D10 two-column scan (worst case).
**Ground truth = 5 representative pages/doc** (front/middle/back), hand-verified or publisher text. Do NOT transcribe whole books.

## Candidates
Digital: PyMuPDF (primary) vs pdfplumber (tables). OCR: one managed cloud OCR vs Tesseract (local). Hard layout: one managed layout parser (LlamaParse-class) for D3/D4/D10.

## Metrics (script-computed → results.csv, one row per doc×tool×metric)
char fidelity (1−Levenshtein/len) ≥98% digital · OCR word acc (1−WER) ≥95% clean · type-detect ≥95% · chapter detection ≥90% (TOC docs) · reading-order 0–2 manual ≥1.5 single-col · per-doc cost <$2 scanned/<$1 digital · latency ≤5min digital/≤12min scanned p90 proxy.

## Day plan
D1 pin corpus + ground-truth + scoring harness · D2 digital (PyMuPDF/pdfplumber, H1/H6/reading-order) · D3 OCR cloud-vs-Tesseract on D5–D10 (H3/H4/H5 acc+cost+latency) · D4 type-detect H2 full corpus + hard-layout H7 heuristic-vs-parser · D5 consolidate, fill decision matrix, write findings, update PRD Qs.

## Spike Definition of Done (all checked into `spike/`)
pinned corpus + ground truth · reproducible scoring scripts + requirements.txt · raw results.csv (all doc×tool×metric) · qualitative failure notes + screenshots · filled decision matrix w/ recommendation per choice · PRD Q2+Q4 marked resolved (stack+rationale+numbers), Q1/Q3 updated · "what surprised us" risk note.
**Non-goal:** no production ingestion code, no UI, no pipeline wiring.

## Decision matrix (fill by D5)
digital parser (PyMuPDF/pdfplumber) · OCR primary (cloud/Tesseract) · OCR fallback (Tesseract/none) · type-detect method · hard-layout strategy (heuristic/managed parser) · scanned-cost go/no-go vs $2 cap. Each row = chosen + measured evidence + confidence.

## Spike risks → mitigations
unrepresentative corpus → fix 10-doc spread incl. worst cases · ground-truth balloon → hard 5 pages/doc · cloud OCR access delay → start Day-0, Tesseract parallel track · scope creep → hard timebox, throwaway scripts, daily exit artifacts · cost at n=10 unrealistic → extrapolate per-page×300, flag assumption.

## Feeds back into
PRD Q2/Q4 resolved · Q1 quality baseline · Q3 cloud-vs-local OCR gap → privacy trade-off · Architecture phase: confirmed ingestion components + cost/latency inputs.
