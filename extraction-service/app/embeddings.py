"""Semantic-retrieval embeddings (RC-14).

An *embedding* model (not a generative LLM — no token-billed generation) turns
text into vectors so the chat can match a question by meaning, closing the
open-domain-paraphrase gap that stemming (RC-11) and synonyms (RC-13) cannot.

Fully optional and fail-safe: with `EMBEDDING_MODEL` blank the module is disabled
and retrieval stays lexical. Any embedding failure (model unavailable, host down)
returns None so the caller falls back to lexical — extraction and chat never break.

Storage note: this module computes the vectors; `app/embeddings_store.py`
persists them to the pgvector `chunk_embeddings` table for SQL-side `<=>` search
(OUT-04). They are also still written into the graph JSON as a backward-compatible
fallback for jobs indexed before that table existed (see `chat_routes` /
`embeddings_store.has_rows`).
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


_EMBED_BATCH = 50  # NVIDIA / OpenAI embedding endpoints cap batch size + tokens


def _embed_batch(client, cfg: Settings, batch: list[str], input_type: str | None,
                 max_chars: int) -> list[list[float]]:
    """Embed one batch, adaptively shrinking on a token-limit 400. A fixed char cap
    can't be safe across content densities (dense/code text packs more tokens per
    char), so if the endpoint rejects the input as too long we truncate harder and
    retry down to a floor. This makes the embed path robust for any chunk."""
    trunc = [t[:max_chars] for t in batch] if max_chars > 0 else batch
    kwargs: dict = {"model": cfg.embedding_model, "input": trunc}
    # NVIDIA e5/embedqa models require input_type ("passage" for documents,
    # "query" for the question) — asymmetric retrieval embeddings.
    if input_type:
        kwargs["extra_body"] = {"input_type": input_type}
    try:
        return [d.embedding for d in client.embeddings.create(**kwargs).data]
    except Exception as e:
        if "maximum allowed token" in str(e).lower() and max_chars > 300:
            return _embed_batch(client, cfg, batch, input_type, int(max_chars * 0.6))
        raise


def _openai_embed(texts: list[str], cfg: Settings,
                  input_type: str | None = None) -> list[list[float]]:
    from openai import OpenAI  # lazy — only when configured

    # base_url routes to the configured OpenAI-compatible host (e.g. NVIDIA);
    # without it embeddings would wrongly hit api.openai.com.
    client = OpenAI(api_key=cfg.openai_api_key,
                    base_url=(cfg.openai_base_url or None), max_retries=2)
    cap = cfg.embedding_max_chars or 0
    out: list[list[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH):
        out.extend(_embed_batch(client, cfg, texts[i:i + _EMBED_BATCH], input_type,
                                cap or 10 ** 9))
    return out


def embed_texts(texts: list[str], cfg: Settings,
                input_type: str | None = None) -> list[list[float]] | None:
    """Embed a batch of texts (documents/passages by default). Returns None if
    disabled or on any failure so the caller falls back to lexical retrieval.
    `input_type` defaults to `EMBEDDING_INPUT_TYPE` (NVIDIA asymmetric models);
    blank = not sent (Ollama / OpenAI-native models ignore it)."""
    if not enabled(cfg) or not texts:
        return None
    try:
        if cfg.embedding_provider == "openai":
            return _openai_embed(texts, cfg, input_type or (cfg.embedding_input_type or None))
        return _ollama_embed(texts, cfg)
    except Exception as e:  # host down, model missing, etc. — degrade gracefully
        audit("EMBED_FAILED", provider=cfg.embedding_provider, error=str(e))
        return None


def embed_query(text: str, cfg: Settings) -> list[float] | None:
    # The query side of an asymmetric model uses input_type "query"; symmetric
    # models (blank EMBEDDING_INPUT_TYPE) send nothing.
    q_type = "query" if cfg.embedding_input_type else None
    vecs = embed_texts([text], cfg, input_type=q_type)
    return vecs[0] if vecs else None


def split_passages(text: str, size: int) -> list[str]:
    """Split a chunk into ~`size`-char sub-passages for embedding (OUT-04e).

    A chunk can be far larger than an embedding model's token window (NVIDIA e5 =
    512 tokens); embedding only its leading window loses the rest. Splitting into
    sub-passages and embedding each — then deduping back to the parent chunk at
    query time — gives full-coverage semantic retrieval. Non-overlapping windows;
    adaptive truncation still guards any unusually dense sub-passage."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    return [text[i:i + size] for i in range(0, len(text), size) if text[i:i + size].strip()]


def embed_graph(nodes: list[dict], chunks: list[dict], cfg: Settings):
    """Embed a graph's concepts (one vector each) and chunks (sub-passage vectors,
    OUT-04e). Returns `(node_vectors, chunk_rows)` where `chunk_rows` is a list of
    `(chunk_idx, sub_idx, vector)` mapping every sub-passage back to its parent
    `graph["chunks"]` index. Returns None on any embedding failure so the caller
    degrades to lexical retrieval. Used by the extraction save + backfill paths."""
    if not enabled(cfg):
        return None
    ntexts = [f"{n.get('name', '')}: {n.get('definition', '')}" for n in nodes]
    nv = embed_texts(ntexts, cfg) if ntexts else []
    if nv is None:
        return None
    sub_texts: list[str] = []
    owners: list[int] = []
    for ci, c in enumerate(chunks):
        for passage in split_passages(c.get("content", ""), cfg.embedding_subchunk_chars):
            sub_texts.append(passage)
            owners.append(ci)
    sv = embed_texts(sub_texts, cfg) if sub_texts else []
    if sv is None:
        return None
    chunk_rows: list[tuple[int, int, list[float]]] = []
    per_chunk: dict[int, int] = {}
    for owner, vec in zip(owners, sv):
        sub = per_chunk.get(owner, 0)
        per_chunk[owner] = sub + 1
        chunk_rows.append((owner, sub, vec))
    return nv, chunk_rows


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
