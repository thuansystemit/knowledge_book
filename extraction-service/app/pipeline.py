"""End-to-end pipeline: PDF bytes -> knowledge graph (+ optional Brief).

Stages (PRD §7 pipeline, MVP subset):
  1. classify + extract text (OCR fallback for scanned pages)
  2. chunk into section-level prose chunks (page + chapter anchored)
  3. per-chunk LLM concept/relation extraction (map)
  4. merge + dedup into one graph (reduce)
  5. (optional) synthesise the executive Brief from the graph
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Callable, Optional

from app import chapter_guide, chunk_cache, embeddings
from app.config import Settings
from app.costs import CostLedger
from app.domain.graph_schema import NODE_TYPES  # noqa: F401  (kept for callers)
from app.extraction.chunker import chunk_text
from app.extraction.text_extractor import classify_pdf, extract_text_with_quality
from app.graph_builder import GraphBuilder
from app.llm.provider import LlmProvider
from app.observability import audit

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def _load_prompt(name: str) -> str:
    with open(os.path.join(_PROMPT_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def run(
    data: bytes,
    doc_title: str,
    provider: LlmProvider,
    cfg: Settings,
    on_event: Optional[Callable[[dict], None]] = None,
    make_provider: Optional[Callable[[], LlmProvider]] = None,
) -> dict:
    """Run the pipeline. `on_event` (optional) receives stage-progress dicts so a
    UI can render the workflow live: {stage, status, detail?, index?, total?}."""

    # Per-stage wall-clock timing (ACT-05): record the first "running" and the
    # matching "done"/"error" for each stage.
    _t0 = time.monotonic()
    _stage_start: dict[str, float] = {}
    stage_timings: dict[str, float] = {}

    def emit(stage: str, status: str = "running", **fields) -> None:
        now = time.monotonic()
        if status == "running" and stage not in _stage_start:
            _stage_start[stage] = now
        elif status in ("done", "error") and stage in _stage_start:
            stage_timings[stage] = round(now - _stage_start[stage], 3)
        if on_event:
            on_event({"stage": stage, "status": status, **fields})

    emit("classify")
    pdf_type, frac = classify_pdf(data)
    audit("PDF_CLASSIFIED", type=pdf_type, digital_page_fraction=round(frac, 3))
    emit("classify", "done", detail=f"{pdf_type} ({frac:.0%} digital pages)")

    emit("extract_text")
    text, ocr_quality = extract_text_with_quality(data, "application/pdf")
    if len(text.strip()) < cfg.min_chars:
        emit("extract_text", "error", detail="unreadable PDF")
        raise ValueError(f"extracted text too short ({len(text.strip())} chars) — unreadable PDF")
    if ocr_quality.get("low_confidence"):
        emit("extract_text", "done",
             detail=f"{len(text):,} chars — low OCR quality ({ocr_quality.get('mean_confidence')}%)")
    else:
        emit("extract_text", "done", detail=f"{len(text):,} chars")

    emit("chunk")
    chunks = chunk_text(text, cfg.chunk_tokens, cfg.chunk_overlap)
    audit("CHUNKED", chunks=len(chunks))
    emit("chunk", "done", detail=f"{len(chunks)} chunks")

    kg_prompt = _load_prompt("kg_extract.txt")
    builder = GraphBuilder()
    failed: list[dict] = []
    ledger = CostLedger()   # per-document cost accounting + hard cap (EXT-02)

    chunk_dicts = [{"index": ch.index, "chapter": ch.chapter, "page_start": ch.page_start,
                    "page_end": ch.page_end, "content": ch.content} for ch in chunks]
    model_id = getattr(provider, "model", None)
    concurrency = max(1, cfg.extract_concurrency)
    total = len(chunk_dicts)
    emit("extract", total=total, index=0)
    done = 0

    if concurrency > 1 and make_provider is not None and total > 1:
        # Parallel fan-out (EXT-04): call chunks concurrently on per-thread
        # providers; merge in this thread (GraphBuilder/ledger stay single-threaded).
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed
        _tl = threading.local()

        def _tl_provider() -> LlmProvider:
            p = getattr(_tl, "p", None)
            if p is None:
                p = make_provider(); _tl.p = p
            return p

        def _work(cd: dict):
            return cd, _call_chunk(_tl_provider(), kg_prompt, doc_title, cd, cfg)

        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = [ex.submit(_work, cd) for cd in chunk_dicts]
            try:
                for fut in as_completed(futures):
                    cd, result = fut.result()
                    if not _merge_chunk_result(builder, ledger, model_id, cd, result, cfg):
                        failed.append(cd)
                    done += 1
                    _enforce_cost_cap(ledger, cfg, emit)   # abort before overrunning
                    emit("extract", total=total, index=done)
            except CostCapExceeded:
                ex.shutdown(cancel_futures=True)
                raise
    else:
        for cd in chunk_dicts:
            if not _extract_chunk(provider, kg_prompt, doc_title, cd, builder, cfg, ledger):
                failed.append(cd)
            done += 1
            _enforce_cost_cap(ledger, cfg, emit)
            emit("extract", total=total, index=done,
                 detail=f"chapter: {cd['chapter'] or '(unknown)'}")
    emit("extract", "done", total=total, detail=f"{len(failed)} chunk error(s)")

    emit("merge")
    graph = builder.build()
    graph["document"] = {"title": doc_title, "pdf_type": pdf_type, "pages_chunked": len(chunks)}
    # Persist section chunks for zero-LLM retrieval chat (RC-10): excerpt lookup
    # composes cited answers from this text without a query-time model. Stored in
    # the graph JSON so chat.py stays a pure function over the graph.
    graph["chunks"] = [
        {"index": ch.index, "chapter": ch.chapter, "page_start": ch.page_start,
         "page_end": ch.page_end, "content": ch.content}
        for ch in chunks
    ]
    # Semantic vectors for retrieval (RC-14) — optional + fail-safe: only when an
    # embedding model is configured, and any failure leaves the graph lexical-only.
    if embeddings.enabled(cfg):
        try:
            nv = embeddings.embed_texts(
                [f"{n['name']}: {n.get('definition', '')}" for n in graph["nodes"]], cfg)
            cv = embeddings.embed_texts([c["content"] for c in graph["chunks"]], cfg)
            if nv and cv:
                graph["node_vectors"] = [[round(x, 5) for x in v] for v in nv]
                graph["chunk_vectors"] = [[round(x, 5) for x in v] for v in cv]
                graph["embedding_model"] = cfg.embedding_model
                audit("EMBEDDED", nodes=len(nv), chunks=len(cv))
        except Exception as e:
            audit("EMBED_SKIPPED", error=str(e))
    # Keep the failed chunks' text so they can be retried + merged into THIS graph
    # later (retry_failed / POST /api/jobs/{id}/retry-failed) rather than re-running
    # the whole document.
    graph["failed_chunks"] = failed
    graph["ocr_quality"] = ocr_quality   # OCR confidence gate (ING-06)
    graph["warnings"] = _warnings(len(failed), pdf_type)
    if ocr_quality.get("low_confidence"):
        graph["warnings"].append(
            f"Low OCR quality (mean confidence {ocr_quality.get('mean_confidence')}%"
            f" on {len(ocr_quality.get('low_pages') or [])} page(s)) — text may contain errors")
    audit("GRAPH_BUILT", **graph["stats"], chunk_errors=len(failed))
    emit("merge", "done", detail=f"{graph['stats']['node_count']} concepts, "
                                 f"{graph['stats']['edge_count']} relations")

    if cfg.generate_brief:
        emit("brief")
        graph["brief"] = _make_brief(graph, doc_title, provider, ledger)
        emit("brief", "done")

    # Chapter Guide (OUT-03) — deterministic, no extra LLM call.
    graph["chapter_guide"] = chapter_guide.build(graph)

    # Figure/table captions (HAR-02) — structured, from the extracted text.
    if cfg.extract_captions:
        graph["captions"] = _extract_captions(text)

    graph["cost"] = ledger.summary()
    # ACT-04: flag documents whose LLM spend approaches the per-doc cap so the
    # ops dashboard can warn (the hard abort at 100% lives in _enforce_cost_cap).
    _cap = cfg.max_doc_cost_usd
    if _cap:
        _ratio = round(ledger.usd / _cap, 3)
        graph["cost"]["cap_usd"] = _cap
        graph["cost"]["cap_ratio"] = _ratio
        graph["cost"]["cap_warning"] = _ratio >= 0.8
    audit("COST_LEDGER", **graph["cost"])
    graph["stage_timings"] = {**stage_timings, "total_s": round(time.monotonic() - _t0, 3)}
    emit("done", "done", **graph["stats"])
    return graph


_CAPTION_RE = re.compile(
    r"^\s*((?:figure|fig\.?|table|exhibit)\s+\d+[.:]\s*.{2,140})",
    re.IGNORECASE | re.MULTILINE)


def _extract_captions(text: str) -> list[dict]:
    """Figure/table captions (HAR-02): lines like "Figure 3: …" / "Table 2. …"
    as structured {kind, label} entries. Deduped, capped."""
    out: list[dict] = []
    seen: set[str] = set()
    for m in _CAPTION_RE.finditer(text or ""):
        label = " ".join(m.group(1).split())
        key = label.lower()[:60]
        if key in seen:
            continue
        seen.add(key)
        kind = "table" if label.lower().startswith(("table", "exhibit")) else "figure"
        out.append({"kind": kind, "label": label})
    return out[:60]


def _chunk_header(doc_title: str, chunk: dict) -> str:
    return (
        f"Document: {doc_title}\nChapter/Section: {chunk['chapter'] or '(unknown)'}\n"
        f"Pages: {chunk['page_start']}-{chunk['page_end']}\n\nExcerpt:\n{chunk['content']}"
    )


class CostCapExceeded(RuntimeError):
    """Raised to abort a document whose accrued LLM cost exceeds the cap (EXT-02).
    The message begins with `cost_cap` so the job records FAILED(cost_cap)."""


def _enforce_cost_cap(ledger: CostLedger, cfg: Settings, emit) -> None:
    cap = cfg.max_doc_cost_usd
    if cap and ledger.usd > cap:
        detail = f"cost_cap: spent ${ledger.usd:.2f} exceeds ${cap:.2f} budget"
        emit("extract", "error", detail=detail)
        raise CostCapExceeded(detail)


def _call_chunk(provider: LlmProvider, kg_prompt: str, doc_title: str,
                chunk: dict, cfg: Settings) -> dict:
    """Extract one chunk: cache lookup + LLM call + parse. Touches **no shared
    state** (only its own `provider`), so it is safe to run in a thread pool for
    the parallel fan-out (EXT-04). Returns a result dict merged later by
    `_merge_chunk_result`: {parsed, usage, cache_key, raw, from_cache}."""
    header = _chunk_header(doc_title, chunk)
    model_id = getattr(provider, "model", None)
    ck = chunk_cache.key(model_id, kg_prompt, header) if chunk_cache.enabled(cfg) else None

    # EXT-03: reuse a cached extraction — no LLM call, no cost.
    if ck:
        cached = chunk_cache.get(ck)
        if cached is not None:
            try:
                return {"parsed": json.loads(cached), "usage": None,
                        "cache_key": ck, "raw": None, "from_cache": True}
            except Exception:
                pass  # corrupt cache entry -> fall through to the LLM

    if cfg.chunk_throttle_ms > 0:
        time.sleep(cfg.chunk_throttle_ms / 1000.0)

    last_err = None
    for attempt in range(cfg.chunk_retries + 1):
        try:
            raw = provider.complete_json(kg_prompt, header, max_tokens=8000)
            parsed = json.loads(raw)
            if attempt > 0:
                audit("CHUNK_RECOVERED", index=chunk["index"], attempt=attempt + 1)
            return {"parsed": parsed, "usage": getattr(provider, "last_usage", None),
                    "cache_key": ck, "raw": raw, "from_cache": False}
        except Exception as e:
            last_err = e
            audit("CHUNK_RETRY", index=chunk["index"], attempt=attempt + 1, error=str(e))
    audit("CHUNK_FAILED", index=chunk["index"], error=str(last_err))
    return {"parsed": None, "usage": None, "cache_key": ck, "raw": None, "from_cache": False}


def _merge_chunk_result(builder: GraphBuilder, ledger: CostLedger | None,
                        model_id: str | None, chunk: dict, result: dict,
                        cfg: Settings) -> bool:
    """Merge one chunk's result into the graph (main thread only — GraphBuilder,
    the cost ledger, and cache writes are single-threaded here)."""
    parsed = result.get("parsed")
    if parsed is None:
        return False
    source_ref = {"chapter": chunk["chapter"], "page_start": chunk["page_start"],
                  "page_end": chunk["page_end"]}
    builder.add_chunk(parsed, source_ref)
    if result.get("from_cache"):
        audit("CHUNK_CACHE_HIT", index=chunk["index"])
        return True
    if ledger is not None:
        ledger.add(model_id, result.get("usage"))
    if result.get("cache_key") and result.get("raw"):
        chunk_cache.put(result["cache_key"], result["raw"], cfg.chunk_cache_ttl_days * 86400)
    return True


def _extract_chunk(provider: LlmProvider, kg_prompt: str, doc_title: str,
                   chunk: dict, builder: GraphBuilder, cfg: Settings,
                   ledger: CostLedger | None = None) -> bool:
    """Sequential extract-one-chunk (call + merge). Used by retry_failed and the
    single-threaded path."""
    result = _call_chunk(provider, kg_prompt, doc_title, chunk, cfg)
    return _merge_chunk_result(builder, ledger, getattr(provider, "model", None),
                               chunk, result, cfg)


def _warnings(failed_count: int, pdf_type: str) -> list[str]:
    warns = []
    if failed_count:
        warns.append(f"{failed_count} chunk(s) failed extraction")
    if pdf_type and pdf_type != "digital":
        warns.append(f"PDF classified as {pdf_type}; OCR text may be lower quality")
    return warns


def retry_failed(
    graph: dict,
    doc_title: str,
    provider: LlmProvider,
    cfg: Settings,
    on_event: Optional[Callable[[dict], None]] = None,
) -> dict:
    """Re-extract only the chunks that failed last time and MERGE them into the
    existing graph (append, don't rebuild). Returns the updated graph with a
    refreshed `failed_chunks` list — chunks that recover are removed."""

    def emit(stage: str, status: str = "running", **fields) -> None:
        if on_event:
            on_event({"stage": stage, "status": status, **fields})

    failed = list(graph.get("failed_chunks") or [])
    if not failed:
        return graph

    kg_prompt = _load_prompt("kg_extract.txt")
    builder = GraphBuilder.from_graph(graph)   # seed with the existing graph
    still_failed: list[dict] = []
    ledger = CostLedger()

    emit("extract", total=len(failed), index=0, detail="retrying failed chunks")
    for i, chunk in enumerate(failed, 1):
        if not _extract_chunk(provider, kg_prompt, doc_title, chunk, builder, cfg, ledger):
            still_failed.append(chunk)
        _enforce_cost_cap(ledger, cfg, emit)
        emit("extract", total=len(failed), index=i,
             detail=f"chapter: {chunk.get('chapter') or '(unknown)'}")
    emit("extract", "done", total=len(failed), detail=f"{len(still_failed)} still failed")

    emit("merge")
    new_graph = builder.build()
    doc = graph.get("document") or {}
    new_graph["document"] = doc
    new_graph["brief"] = graph.get("brief")          # preserve the existing Brief
    new_graph["chunks"] = graph.get("chunks")        # preserve persisted chunks (RC-10)
    for _k in ("node_vectors", "chunk_vectors", "embedding_model", "ocr_quality", "captions"):
        if graph.get(_k) is not None:
            new_graph[_k] = graph[_k]
    new_graph["chapter_guide"] = chapter_guide.build(new_graph)   # OUT-03 (recompute)
    new_graph["failed_chunks"] = still_failed
    new_graph["warnings"] = _warnings(len(still_failed), doc.get("pdf_type", ""))
    # Accumulate retry cost onto the document's existing ledger (EXT-02).
    prev = graph.get("cost") or {}
    add = ledger.summary()
    new_graph["cost"] = {
        "calls": prev.get("calls", 0) + add["calls"],
        "input_tokens": prev.get("input_tokens", 0) + add["input_tokens"],
        "output_tokens": prev.get("output_tokens", 0) + add["output_tokens"],
        "usd": round(prev.get("usd", 0.0) + add["usd"], 4),
    }
    audit("RETRY_DONE", recovered=len(failed) - len(still_failed), remaining=len(still_failed),
          **new_graph["stats"])
    emit("merge", "done", detail=f"{new_graph['stats']['node_count']} concepts, "
                                 f"{new_graph['stats']['edge_count']} relations")
    emit("done", "done", **new_graph["stats"])
    return new_graph


def _make_brief(graph: dict, doc_title: str, provider: LlmProvider,
                ledger: CostLedger | None = None) -> Optional[dict]:
    """Synthesise the executive Brief from the top concepts/relations."""
    top_nodes = graph["nodes"][:25]
    concept_lines = [f"- {n['name']} ({n['type']}): {n['definition']}" for n in top_nodes]
    names = {n["id"] for n in top_nodes}
    rel_lines = [
        f"- {e['source']} --{e['type']}--> {e['target']}"
        for e in graph["edges"] if e["source"] in names and e["target"] in names
    ][:40]
    payload = (
        f"Document: {doc_title}\n\nTop concepts:\n" + "\n".join(concept_lines)
        + "\n\nKey relations:\n" + "\n".join(rel_lines)
    )
    try:
        raw = provider.complete_json(_load_prompt("brief.txt"), payload, max_tokens=2048)
        if ledger is not None:
            ledger.add(getattr(provider, "model", None),
                       getattr(provider, "last_usage", None), stage="brief")
        return json.loads(raw)
    except Exception as e:
        audit("BRIEF_FAILED", error=str(e))
        return None
