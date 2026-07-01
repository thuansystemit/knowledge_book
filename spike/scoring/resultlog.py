"""Append-only result logger. Every measurement lands here as one CSV row so
results are raw and reproducible (no cherry-picking)."""
from __future__ import annotations
import csv
import os
from datetime import datetime, timezone

RESULTS = os.path.join(os.path.dirname(__file__), "..", "results", "results.csv")
HEADER = ["doc", "tool", "metric", "value", "page", "timestamp"]


def log(doc: str, tool: str, metric: str, value, page: str | int = "") -> None:
    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    new = not os.path.exists(RESULTS)
    with open(RESULTS, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(HEADER)
        w.writerow([
            doc, tool, metric, value, page,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ])
