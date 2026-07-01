# Week-1 PDF + OCR Spike — Harness

Reproducible harness for the spike defined in `../docs/SPIKE-week1-pdf-ocr.md`.
**Goal: evidence + a decision, not production code.** Scripts here are throwaway.

## Layout
```
spike/
  corpus/manifest.csv     # the fixed 10-doc spec (D1..D10); drop PDFs in corpus/pdfs/
  corpus/pdfs/            # actual PDF files (gitignored — may be copyrighted)
  ground_truth/<ID>/p<NN>.txt   # 5 hand-verified sample pages per doc
  scoring/                # runnable measurement scripts
  results/results.csv     # raw output: one row per doc x tool x metric
```

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Tesseract binary must be installed separately:
#   macOS: brew install tesseract
```

## Run order (mirrors the day plan)
```bash
# Day 2 — digital extraction + char fidelity (H1, H6)
python scoring/extract_digital.py --doc D1
python scoring/score.py --doc D1 --tool pymupdf --metric char_fidelity

# Day 3 — OCR accuracy + cost/latency (H3, H4, H5)
python scoring/ocr_tesseract.py --doc D5
python scoring/score.py --doc D5 --tool tesseract --metric word_accuracy
#   (cloud OCR runner is vendor-specific; add scoring/ocr_cloud.py once vendor chosen)

# Day 4 — type detection (H2)
python scoring/type_detect.py --all
```

## Ground-truth rule
5 representative pages per doc (front/middle/back). Hand-verify or use legally available
publisher text. Do NOT transcribe whole books. Store as `ground_truth/<ID>/p<NN>.txt`,
where `<NN>` is the 1-based PDF page number.

## Reproducibility
- Pin tool versions in `requirements.txt`.
- `results/results.csv` is append-only and committed — raw numbers, no cherry-picking.
- Every row records `doc,tool,metric,value,page,timestamp` so a reviewer can re-run.
