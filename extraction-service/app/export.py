"""Export a document's outputs as standalone Markdown or JSON (OUT-06).

Markdown is human-readable on its own (Brief + Concept Map + Chapter Guide +
Relationships). JSON is the clean graph schema — nodes, edges, brief, and chapter
guide — with internal/heavy fields (embeddings, chunks, cost, timings, paywall)
stripped out.
"""
from __future__ import annotations

import json

# Internal/heavy graph keys that should never leave in an export.
_STRIP = {"chunks", "node_vectors", "chunk_vectors", "embedding_model", "cost",
          "stage_timings", "failed_chunks", "paywall", "chapter_guide_locked",
          "ocr_quality", "warnings"}


def to_json(graph: dict, title: str) -> str:
    clean = {"title": title}
    clean.update({k: v for k, v in (graph or {}).items() if k not in _STRIP})
    return json.dumps(clean, ensure_ascii=False, indent=2)


def _refs(node: dict) -> str:
    out = []
    for r in node.get("source_refs", []) or []:
        ch = r.get("chapter") or "?"
        out.append(f"{ch} p.{r.get('page_start')}-{r.get('page_end')}")
    return "; ".join(out)


def to_markdown(graph: dict, title: str) -> str:
    graph = graph or {}
    L: list[str] = [f"# {title}", ""]

    brief = graph.get("brief") or {}
    if brief:
        L.append("## Brief")
        if brief.get("thesis"):
            L += [f"**Thesis:** {brief['thesis']}", ""]
        if brief.get("audience"):
            L += [f"**Audience:** {brief['audience']}", ""]
        if brief.get("summary"):
            L += [brief["summary"], ""]
        if brief.get("core_concepts"):
            L += ["**Core concepts:** " + ", ".join(brief["core_concepts"]), ""]
        if brief.get("key_principles"):
            L += ["**Key principles:** " + ", ".join(brief["key_principles"]), ""]

    nodes = graph.get("nodes") or []
    if nodes:
        L += ["## Concept Map", ""]
        for n in nodes:
            refs = _refs(n)
            defn = (n.get("definition") or "").strip()
            tail = f"  _[{refs}]_" if refs else ""
            L.append(f"- **{n.get('name')}** ({n.get('type')}) — {defn}{tail}")
        L.append("")

    guide = graph.get("chapter_guide") or []
    if guide:
        L += ["## Chapter Guide", ""]
        for ch in guide:
            L.append(f"### {ch.get('chapter')}")
            if ch.get("summary"):
                L += [ch["summary"], ""]
            intro = ", ".join(c.get("name", "") for c in ch.get("concepts_introduced") or [])
            prereq = ", ".join(c.get("name", "") for c in ch.get("prerequisites") or [])
            if intro:
                L.append(f"- **Introduces:** {intro}")
            if prereq:
                L.append(f"- **Prerequisites:** {prereq}")
            L.append("")

    edges = graph.get("edges") or []
    if edges:
        L += ["## Relationships", ""]
        for e in edges:
            L.append(f"- {e.get('source')} —{e.get('type')}→ {e.get('target')}")
        L.append("")

    return "\n".join(L).rstrip() + "\n"
