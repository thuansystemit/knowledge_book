"""Per-document cost ledger (EXT-02).

Turns LLM token usage into an estimated USD cost and accumulates it across a
document's extraction so the pipeline can (a) persist a real per-doc cost for the
ops dashboard and (b) hard-abort a job before it overruns a cost cap.

Prices are USD per 1M tokens (input, output), keyed by model id. Local models
(Ollama) and unknown models cost 0 — so the default local setup accrues no cost
and never trips the cap. Prices can be overridden via the `LLM_PRICES_USD` env
var as `model:in/out,model:in/out` without a code change.
"""
from __future__ import annotations

import os

# USD per 1,000,000 tokens: model_id -> (input, output). Approximate list prices;
# override via LLM_PRICES_USD. Anything not listed is treated as free (0/0).
_DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "gpt-4o": (2.5, 10.0),
}


def _load_price_overrides() -> dict[str, tuple[float, float]]:
    raw = os.environ.get("LLM_PRICES_USD", "").strip()
    if not raw:
        return {}
    out: dict[str, tuple[float, float]] = {}
    for part in raw.split(","):
        if ":" not in part or "/" not in part:
            continue
        model, io = part.split(":", 1)
        try:
            i, o = io.split("/", 1)
            out[model.strip()] = (float(i), float(o))
        except ValueError:
            continue
    return out


def prices_for(model_id: str | None) -> tuple[float, float]:
    if not model_id:
        return (0.0, 0.0)
    overrides = _load_price_overrides()
    return overrides.get(model_id) or _DEFAULT_PRICES.get(model_id, (0.0, 0.0))


def usd_for(model_id: str | None, input_tokens: int, output_tokens: int) -> float:
    pin, pout = prices_for(model_id)
    return (input_tokens * pin + output_tokens * pout) / 1_000_000.0


class CostLedger:
    """Accumulates token usage + estimated USD across a document's LLM calls."""

    def __init__(self) -> None:
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.usd = 0.0
        # ACT-04: per-stage breakdown (e.g. "extraction", "brief") so ops can see
        # where a document's LLM spend went, not just the total.
        self.by_stage: dict[str, dict] = {}

    def add(self, model_id: str | None, usage: dict | None,
            stage: str = "extraction") -> None:
        """Record one LLM call against a pipeline stage. `usage` is
        `{input_tokens, output_tokens}` or None (local/free model) — a missing/None
        usage adds a call at zero cost."""
        self.calls += 1
        st = self.by_stage.setdefault(
            stage, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "usd": 0.0})
        st["calls"] += 1
        if not usage:
            return
        i = int(usage.get("input_tokens") or 0)
        o = int(usage.get("output_tokens") or 0)
        add_usd = usd_for(model_id, i, o)
        self.input_tokens += i
        self.output_tokens += o
        self.usd += add_usd
        st["input_tokens"] += i
        st["output_tokens"] += o
        st["usd"] += add_usd

    def summary(self) -> dict:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "usd": round(self.usd, 4),
            "by_stage": {k: {**v, "usd": round(v["usd"], 4)}
                         for k, v in self.by_stage.items()},
        }
