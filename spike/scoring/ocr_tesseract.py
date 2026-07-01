"""Day 3 — local OCR fallback via Tesseract (H4). Renders each PDF page to an
image and OCRs it, recording per-page latency. Writes extractions/<DOC>/tesseract/p<NN>.txt.

Requires the `tesseract` binary (brew install tesseract).
Usage: python ocr_tesseract.py --doc D5 [--dpi 300]
"""
from __future__ import annotations
import argparse
import csv
import os
import time

import fitz  # PyMuPDF (render to image)
import pytesseract
from PIL import Image

from resultlog import log

CORPUS = os.path.join(os.path.dirname(__file__), "..", "corpus")
PDFS = os.path.join(CORPUS, "pdfs")
OUT = os.path.join(os.path.dirname(__file__), "..", "extractions")


def ocr_doc(doc_id: str, filename: str, dpi: int) -> None:
    path = os.path.join(PDFS, filename)
    if not os.path.exists(path):
        print(f"[skip] {doc_id}: {path} not found")
        return
    outdir = os.path.join(OUT, doc_id, "tesseract")
    os.makedirs(outdir, exist_ok=True)
    doc = fitz.open(path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    total_t = 0.0
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        t0 = time.perf_counter()
        text = pytesseract.image_to_string(img)
        dt = time.perf_counter() - t0
        total_t += dt
        with open(os.path.join(outdir, f"p{i:02d}.txt"), "w") as f:
            f.write(text)
    log(doc_id, "tesseract", "ocr_latency_sec_total", round(total_t, 2))
    log(doc_id, "tesseract", "ocr_latency_sec_per_page", round(total_t / max(len(doc), 1), 2))
    print(f"{doc_id}: OCR'd {len(doc)} pages @ {dpi}dpi in {total_t:.1f}s -> {outdir}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True)
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()
    rows = {r["id"]: r for r in csv.DictReader(open(os.path.join(CORPUS, "manifest.csv")))}
    r = rows[args.doc]
    ocr_doc(r["id"], r["pdf_filename"], args.dpi)


if __name__ == "__main__":
    main()
