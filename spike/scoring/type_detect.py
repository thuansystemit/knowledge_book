"""Hypothesis H2: classify digital / scanned / hybrid cheaply.

Heuristic: per page, measure the *text-layer coverage ratio* = chars of real
embedded text relative to page area. Pages with a healthy text layer are
"digital"; pages with near-zero text but image content are "scanned". A doc
with a mix is "hybrid". This is intentionally cheap (no OCR, no ML).

Usage:
    python type_detect.py --doc D5
    python type_detect.py --all
"""
from __future__ import annotations
import argparse
import csv
import os

import fitz  # PyMuPDF

from resultlog import log

CORPUS = os.path.join(os.path.dirname(__file__), "..", "corpus")
PDFS = os.path.join(CORPUS, "pdfs")

# Tunable thresholds — to be calibrated on Day 4 against manifest ground truth.
CHARS_PER_PAGE_DIGITAL = 200   # >= this many extracted chars => page has a text layer
HYBRID_MIN_FRACTION = 0.15     # if 15%-85% of pages are digital => hybrid


def classify(pdf_path: str) -> tuple[str, float]:
    doc = fitz.open(pdf_path)
    pages = len(doc)
    if pages == 0:
        return "empty", 0.0
    digital_pages = 0
    for page in doc:
        text = page.get_text("text") or ""
        if len(text.strip()) >= CHARS_PER_PAGE_DIGITAL:
            digital_pages += 1
    frac = digital_pages / pages
    if frac >= 1 - HYBRID_MIN_FRACTION:
        label = "digital"
    elif frac <= HYBRID_MIN_FRACTION:
        label = "scanned"
    else:
        label = "hybrid"
    return label, frac


def run_doc(doc_id: str, filename: str) -> None:
    path = os.path.join(PDFS, filename)
    if not os.path.exists(path):
        print(f"[skip] {doc_id}: {path} not found (drop the PDF in corpus/pdfs/)")
        return
    label, frac = classify(path)
    print(f"{doc_id}: classified={label} (digital_page_fraction={frac:.2f})")
    log(doc_id, "type_detect", "classification", label)
    log(doc_id, "type_detect", "digital_page_fraction", round(frac, 3))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", help="single doc id, e.g. D5")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(os.path.join(CORPUS, "manifest.csv"))))
    by_id = {r["id"]: r for r in rows}

    if args.all:
        for r in rows:
            run_doc(r["id"], r["pdf_filename"])
    elif args.doc:
        r = by_id[args.doc]
        run_doc(r["id"], r["pdf_filename"])
    else:
        ap.error("pass --doc <ID> or --all")


if __name__ == "__main__":
    main()
