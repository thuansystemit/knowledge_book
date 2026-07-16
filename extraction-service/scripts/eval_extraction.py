#!/usr/bin/env python3
"""EFT-09 — extraction eval harness.

Runs the extraction pipeline over a set of PDFs and records quality/reliability
metrics so prompt/model/JSON-mode changes can be measured (not guessed).

Usage (inside the worker/api container, which has the app + provider config):
  python scripts/eval_extraction.py run  --tag baseline  tests/eval/*.pdf
  python scripts/eval_extraction.py run  --tag jsonmode  tests/eval/*.pdf
  python scripts/eval_extraction.py compare baseline jsonmode

Metrics per doc: chunk_success_rate, brief_present, concepts, relations, cost_usd,
latency_total_s. Results are written to tests/eval/results/{tag}_{ts}.json.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings          # noqa: E402
from app.llm.factory import get_provider     # noqa: E402
from app.pipeline import run as run_pipeline  # noqa: E402

_RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                            "tests", "eval", "results")


class _StubProvider:
    """Deterministic offline provider (CI / `--stub`): returns valid extraction
    JSON so the pipeline + harness run end-to-end without a live model. Dedup by
    canonical key means the six concepts survive across chunks (>=5)."""
    name = "stub"
    model = "stub"
    last_usage = None

    def complete_json(self, system_prompt: str, user_text: str,
                      max_tokens: int = 8000, temperature=None) -> str:
        return json.dumps({
            "concepts": [
                {"name": "REST API", "type": "Concept", "definition": "An HTTP interface.", "confidence": 0.9},
                {"name": "Caching", "type": "Concept", "definition": "Reusing computed results.", "confidence": 0.9},
                {"name": "Idempotency", "type": "Principle", "definition": "Safe to repeat.", "confidence": 0.85},
                {"name": "Load balancing", "type": "Concept", "definition": "Spreading traffic.", "confidence": 0.85},
                {"name": "Sharding", "type": "Concept", "definition": "Partitioning data.", "confidence": 0.85},
                {"name": "Consistency", "type": "Principle", "definition": "Replica agreement.", "confidence": 0.8},
            ],
            "relations": [
                {"source": "Caching", "target": "REST API", "type": "relates_to",
                 "evidence": "APIs cache responses.", "confidence": 0.7},
                {"source": "Sharding", "target": "Consistency", "type": "leads_to",
                 "evidence": "Sharding complicates consistency.", "confidence": 0.7},
            ],
        })


def _eval_one(path: str, cfg, stub: bool = False) -> dict:
    with open(path, "rb") as f:
        data = f.read()
    title = os.path.basename(path)
    make = (lambda: _StubProvider()) if stub else (lambda: get_provider())
    provider = make()
    t0 = time.monotonic()
    try:
        graph = run_pipeline(data, title, provider, cfg, make_provider=make)
    except Exception as e:
        return {"doc": title, "error": str(e), "ok": False}
    stats = graph.get("stats", {})
    chunks_total = (graph.get("document") or {}).get("pages_chunked") or len(graph.get("chunks") or [])
    failed = len(graph.get("failed_chunks") or [])
    ok_chunks = max(0, chunks_total - failed)
    return {
        "doc": title, "ok": True,
        "concepts": stats.get("node_count", 0),
        "relations": stats.get("edge_count", 0),
        "chunk_success_rate": round(ok_chunks / chunks_total, 3) if chunks_total else None,
        "chunk_errors": failed,
        "brief_present": graph.get("brief") is not None,
        "cost_usd": (graph.get("cost") or {}).get("usd"),
        "latency_total_s": (graph.get("stage_timings") or {}).get("total_s",
                                                                  round(time.monotonic() - t0, 3)),
    }


def _aggregate(docs: list[dict]) -> dict:
    ran = [d for d in docs if d.get("ok")]
    n = len(ran) or 1
    def avg(k):
        vals = [d[k] for d in ran if d.get(k) is not None]
        return round(sum(vals) / len(vals), 3) if vals else None
    return {
        "docs_run": len(ran), "docs_errored": len(docs) - len(ran),
        "brief_present_rate": round(sum(1 for d in ran if d.get("brief_present")) / n, 3),
        "avg_chunk_success_rate": avg("chunk_success_rate"),
        "avg_concepts": avg("concepts"), "avg_relations": avg("relations"),
        "avg_cost_usd": avg("cost_usd"), "avg_latency_total_s": avg("latency_total_s"),
    }


def cmd_run(args) -> int:
    cfg = get_settings()
    paths = [p for pat in args.pdfs for p in glob.glob(pat)]
    if not paths:
        print("no PDFs matched", file=sys.stderr)
        return 2
    docs = [_eval_one(p, cfg, stub=args.stub) for p in paths]
    summary = _aggregate(docs)
    out = {"tag": args.tag, "ts": datetime.now(timezone.utc).isoformat(),
           "summary": summary, "docs": docs}
    os.makedirs(_RESULTS_DIR, exist_ok=True)
    fname = os.path.join(_RESULTS_DIR, f"{args.tag}_{int(time.time())}.json")
    with open(fname, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(summary, indent=2))
    print(f"\nwrote {fname}")
    # CI-style thresholds (opt-in via --assert).
    if args.assert_thresholds:
        ok = (summary["brief_present_rate"] == 1.0
              and (summary["avg_chunk_success_rate"] or 0) >= 0.90
              and (summary["avg_concepts"] or 0) >= 5)
        print("THRESHOLDS:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    return 0


def _latest(tag: str) -> dict | None:
    files = sorted(glob.glob(os.path.join(_RESULTS_DIR, f"{tag}_*.json")))
    if not files:
        return None
    with open(files[-1]) as f:
        return json.load(f)


def cmd_compare(args) -> int:
    a, b = _latest(args.tag1), _latest(args.tag2)
    if not a or not b:
        print("missing results for one/both tags", file=sys.stderr)
        return 2
    keys = ["docs_run", "brief_present_rate", "avg_chunk_success_rate",
            "avg_concepts", "avg_relations", "avg_cost_usd", "avg_latency_total_s"]
    w = max(len(k) for k in keys)
    print(f"{'metric':<{w}}  {args.tag1:>14}  {args.tag2:>14}")
    print("-" * (w + 34))
    for k in keys:
        print(f"{k:<{w}}  {str(a['summary'].get(k)):>14}  {str(b['summary'].get(k)):>14}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Extraction eval harness (EFT-09)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--tag", required=True)
    r.add_argument("--assert", dest="assert_thresholds", action="store_true",
                   help="exit non-zero if CI thresholds fail")
    r.add_argument("--stub", action="store_true",
                   help="use a deterministic offline provider (CI / no live model)")
    r.add_argument("pdfs", nargs="+")
    c = sub.add_parser("compare")
    c.add_argument("tag1")
    c.add_argument("tag2")
    args = ap.parse_args()
    return cmd_run(args) if args.cmd == "run" else cmd_compare(args)


if __name__ == "__main__":
    raise SystemExit(main())
