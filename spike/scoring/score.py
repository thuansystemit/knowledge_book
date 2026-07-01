"""Scores an extraction against ground-truth sample pages and logs results.

Compares extractions/<DOC>/<TOOL>/p<NN>.txt vs. ground_truth/<DOC>/p<NN>.txt
for every ground-truth page present, computes the requested metric, logs each
page + the mean.

Usage:
    python score.py --doc D1 --tool pymupdf  --metric char_fidelity
    python score.py --doc D5 --tool tesseract --metric word_accuracy
"""
from __future__ import annotations
import argparse
import os

import metrics
from resultlog import log

BASE = os.path.join(os.path.dirname(__file__), "..")
GT = os.path.join(BASE, "ground_truth")
EXT = os.path.join(BASE, "extractions")

METRICS = {
    "char_fidelity": metrics.char_fidelity,
    "word_accuracy": metrics.word_accuracy,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True)
    ap.add_argument("--tool", required=True)
    ap.add_argument("--metric", required=True, choices=list(METRICS))
    args = ap.parse_args()

    fn = METRICS[args.metric]
    gt_dir = os.path.join(GT, args.doc)
    ext_dir = os.path.join(EXT, args.doc, args.tool)
    if not os.path.isdir(gt_dir):
        raise SystemExit(f"No ground truth at {gt_dir} — add 5 sample pages first.")

    scores = []
    for page_file in sorted(os.listdir(gt_dir)):
        if not page_file.endswith(".txt"):
            continue
        ref = open(os.path.join(gt_dir, page_file)).read()
        ext_path = os.path.join(ext_dir, page_file)
        if not os.path.exists(ext_path):
            print(f"[warn] missing extraction {ext_path} — skipping page")
            continue
        hyp = open(ext_path).read()
        val = fn(hyp, ref)
        page_no = page_file.removeprefix("p").removesuffix(".txt")
        log(args.doc, args.tool, args.metric, round(val, 4), page=page_no)
        scores.append(val)
        print(f"  {args.doc} p{page_no} {args.metric}={val:.4f}")

    if scores:
        mean = sum(scores) / len(scores)
        log(args.doc, args.tool, f"{args.metric}_mean", round(mean, 4))
        print(f"{args.doc} {args.tool} {args.metric} mean = {mean:.4f}  (n={len(scores)})")
    else:
        print("No pages scored — check ground_truth and extraction paths.")


if __name__ == "__main__":
    main()
