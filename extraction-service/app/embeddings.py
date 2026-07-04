"""Semantic-retrieval embeddings (RC-14).

An *embedding* model (not a generative LLM — no token-billed generation) turns
text into vectors so the chat can match a question by meaning, closing the
open-domain-paraphrase gap that stemming (RC-11) and synonyms (RC-13) cannot.

Fully optional and fail-safe: with `EMBEDDING_MODEL` blank the module is disabled
and retrieval stays lexical. Any embedding failure (model unavailable, host down)
returns None so the caller falls back to lexical — extraction and chat never break.

Storage note: vectors are kept in the graph JSON alongside chunks (gated on
enable). The production path for scale is a pgvector index (OUT-04); this keeps
RC-14 self-contained for the MVP.
"""
from __future__ import annotations

import json
import math
import urllib.request

from app.config import Settings
from app.observability import audit


def enabled(cfg: Settings) -> bool:
    return bool(cfg.embedding_model)


def _ollama_embed(texts: list[str], cfg: Settings) -> list[list[float]]:
    base = cfg.ollama_base_url.rstrip("/")
    out: list[list[float]] = []
    for t in texts:
        body = json.dumps({"model": cfg.embedding_model, "prompt": t}).encode("utf-8")
        req = urllib.request.Request(f"{base}/api/embeddings", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            out.append(json.loads(r.read()).get("embedding") or [])
    return out


def _openai_embed(texts: list[str], cfg: Settings) -> list[list[float]]:
    from openai import OpenAI  # lazy — only when configured
    client = OpenAI(api_key=cfg.openai_api_key, max_retries=2)
    resp = client.embeddings.create(model=cfg.embedding_model, input=texts)
    return [d.embedding for d in resp.data]


def embed_texts(texts: list[str], cfg: Settings) -> list[list[float]] | None:
    """Embed a batch of texts. Returns None if disabled or on any failure so the
    caller falls back to lexical retrieval."""
    if not enabled(cfg) or not texts:
        return None
    try:
        if cfg.embedding_provider == "openai":
            return _openai_embed(texts, cfg)
        return _ollama_embed(texts, cfg)
    except Exception as e:  # host down, model missing, etc. — degrade gracefully
        audit("EMBED_FAILED", provider=cfg.embedding_provider, error=str(e))
        return None


def embed_query(text: str, cfg: Settings) -> list[float] | None:
    vecs = embed_texts([text], cfg)
    return vecs[0] if vecs else None


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors (0 if either is empty/zero)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def rank_by_similarity(query_vec: list[float], vectors: list[list[float]],
                       k: int, threshold: float) -> list[tuple[int, float]]:
    """Indices of the top-k vectors with cosine >= threshold, most similar first."""
    if not query_vec or not vectors:
        return []
    scored = [(i, cosine(query_vec, v)) for i, v in enumerate(vectors)]
    scored = [(i, s) for i, s in scored if s >= threshold]
    scored.sort(key=lambda x: -x[1])
    return scored[:k]
