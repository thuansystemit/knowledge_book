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
from typing import Callable, Optional

from app.config import Settings
from app.domain.graph_schema import NODE_TYPES  # noqa: F401  (kept for callers)
from app.extraction.chunker import chunk_text
from app.extraction.text_extractor import classify_pdf, extract_text
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
) -> dict:
    """Run the pipeline. `on_event` (optional) receives stage-progress dicts so a
    UI can render the workflow live: {stage, status, detail?, index?, total?}."""

    def emit(stage: str, status: str = "running", **fields) -> None:
        if on_event:
            on_event({"stage": stage, "status": status, **fields})

    emit("classify")
    pdf_type, frac = classify_pdf(data)
    audit("PDF_CLASSIFIED", type=pdf_type, digital_page_fraction=round(frac, 3))
    emit("classify", "done", detail=f"{pdf_type} ({frac:.0%} digital pages)")

    emit("extract_text")
    text = extract_text(data, "application/pdf")
    if len(text.strip()) < cfg.min_chars:
        emit("extract_text", "error", detail="unreadable PDF")
        raise ValueError(f"extracted text too short ({len(text.strip())} chars) — unreadable PDF")
    emit("extract_text", "done", detail=f"{len(text):,} chars")

    emit("chunk")
    chunks = chunk_text(text, cfg.chunk_tokens, cfg.chunk_overlap)
    audit("CHUNKED", chunks=len(chunks))
    emit("chunk", "done", detail=f"{len(chunks)} chunks")

    kg_prompt = _load_prompt("kg_extract.txt")
    builder = GraphBuilder()
    failed: list[dict] = []

    emit("extract", total=len(chunks), index=0)
    for ch in chunks:
        chunk = {"index": ch.index, "chapter": ch.chapter,
                 "page_start": ch.page_start, "page_end": ch.page_end, "content": ch.content}
        if not _extract_chunk(provider, kg_prompt, doc_title, chunk, builder, cfg):
            failed.append(chunk)
        emit("extract", total=len(chunks), index=ch.index + 1,
             detail=f"chapter: {ch.chapter or '(unknown)'}")
    emit("extract", "done", total=len(chunks), detail=f"{len(failed)} chunk error(s)")

    emit("merge")
    graph = builder.build()
    graph["document"] = {"title": doc_title, "pdf_type": pdf_type, "pages_chunked": len(chunks)}
    # Keep the failed chunks' text so they can be retried + merged into THIS graph
    # later (retry_failed / POST /api/jobs/{id}/retry-failed) rather than re-running
    # the whole document.
    graph["failed_chunks"] = failed
    graph["warnings"] = _warnings(len(failed), pdf_type)
    audit("GRAPH_BUILT", **graph["stats"], chunk_errors=len(failed))
    emit("merge", "done", detail=f"{graph['stats']['node_count']} concepts, "
                                 f"{graph['stats']['edge_count']} relations")

    if cfg.generate_brief:
        emit("brief")
        graph["brief"] = _make_brief(graph, doc_title, provider)
        emit("brief", "done")

    emit("done", "done", **graph["stats"])
    return graph


def _chunk_header(doc_title: str, chunk: dict) -> str:
    return (
        f"Document: {doc_title}\nChapter/Section: {chunk['chapter'] or '(unknown)'}\n"
        f"Pages: {chunk['page_start']}-{chunk['page_end']}\n\nExcerpt:\n{chunk['content']}"
    )


def _extract_chunk(provider: LlmProvider, kg_prompt: str, doc_title: str,
                   chunk: dict, builder: GraphBuilder, cfg: Settings) -> bool:
    """Extract one chunk into the builder, retrying transient model failures.
    Returns True on success. Shared by the main run and retry_failed."""
    source_ref = {"chapter": chunk["chapter"], "page_start": chunk["page_start"],
                  "page_end": chunk["page_end"]}
    header = _chunk_header(doc_title, chunk)
    last_err = None
    for attempt in range(cfg.chunk_retries + 1):
        try:
            raw = provider.complete_json(kg_prompt, header, max_tokens=8000)
            builder.add_chunk(json.loads(raw), source_ref)
            if attempt > 0:
                audit("CHUNK_RECOVERED", index=chunk["index"], attempt=attempt + 1)
            return True
        except Exception as e:
            last_err = e
            audit("CHUNK_RETRY", index=chunk["index"], attempt=attempt + 1, error=str(e))
    audit("CHUNK_FAILED", index=chunk["index"], error=str(last_err))
    return False


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

    emit("extract", total=len(failed), index=0, detail="retrying failed chunks")
    for i, chunk in enumerate(failed, 1):
        if not _extract_chunk(provider, kg_prompt, doc_title, chunk, builder, cfg):
            still_failed.append(chunk)
        emit("extract", total=len(failed), index=i,
             detail=f"chapter: {chunk.get('chapter') or '(unknown)'}")
    emit("extract", "done", total=len(failed), detail=f"{len(still_failed)} still failed")

    emit("merge")
    new_graph = builder.build()
    doc = graph.get("document") or {}
    new_graph["document"] = doc
    new_graph["brief"] = graph.get("brief")          # preserve the existing Brief
    new_graph["failed_chunks"] = still_failed
    new_graph["warnings"] = _warnings(len(still_failed), doc.get("pdf_type", ""))
    audit("RETRY_DONE", recovered=len(failed) - len(still_failed), remaining=len(still_failed),
          **new_graph["stats"])
    emit("merge", "done", detail=f"{new_graph['stats']['node_count']} concepts, "
                                 f"{new_graph['stats']['edge_count']} relations")
    emit("done", "done", **new_graph["stats"])
    return new_graph


def _make_brief(graph: dict, doc_title: str, provider: LlmProvider) -> Optional[dict]:
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
        return json.loads(raw)
    except Exception as e:
        audit("BRIEF_FAILED", error=str(e))
        return None
