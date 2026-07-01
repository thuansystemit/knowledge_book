"""Day 2 — digital extraction via PyMuPDF (H1). Writes per-page extracted text
to extractions/<DOC>/pymupdf/p<NN>.txt so score.py can compare to ground truth.

Usage: python extract_digital.py --doc D1
"""
from __future__ import annotations
import argparse
import csv
import os

import fitz  # PyMuPDF

CORPUS = os.path.join(os.path.dirname(__file__), "..", "corpus")
PDFS = os.path.join(CORPUS, "pdfs")
OUT = os.path.join(os.path.dirname(__file__), "..", "extractions")


def extract(doc_id: str, filename: str) -> None:
    path = os.path.join(PDFS, filename)
    if not os.path.exists(path):
        print(f"[skip] {doc_id}: {path} not found")
        return
    outdir = os.path.join(OUT, doc_id, "pymupdf")
    os.makedirs(outdir, exist_ok=True)
    doc = fitz.open(path)
    for i, page in enumerate(doc, 1):
        # "text" preserves reading order best-effort; "blocks" available for
        # layout analysis on two-column docs (H7) if needed.
        text = page.get_text("text")
        with open(os.path.join(outdir, f"p{i:02d}.txt"), "w") as f:
            f.write(text)
    print(f"{doc_id}: extracted {len(doc)} pages -> {outdir}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True)
    args = ap.parse_args()
    rows = {r["id"]: r for r in csv.DictReader(open(os.path.join(CORPUS, "manifest.csv")))}
    r = rows[args.doc]
    extract(r["id"], r["pdf_filename"])


if __name__ == "__main__":
    main()
