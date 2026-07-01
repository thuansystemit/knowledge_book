"""Tiny structured audit logger — one JSON line per event to stderr.

Keeps the dependency surface at zero; downstream we can swap this for real
structured logging without touching call sites."""
from __future__ import annotations

import json
import sys
import time


def audit(event: str, **fields) -> None:
    rec = {"ts": round(time.time(), 3), "event": event, **fields}
    print(json.dumps(rec, ensure_ascii=False), file=sys.stderr, flush=True)
