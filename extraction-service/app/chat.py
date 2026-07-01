"""Graph-grounded chat: select a relevant slice of the stored knowledge graph
for a question and build the system prompt + citations from it.

No embeddings / RAG — grounding is the graph we already have (nodes, edges,
brief, source_refs). Retrieval is keyword overlap + optional chapter scoping."""
from __future__ import annotations

import os
import re

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")
_CHAPTER_RE = re.compile(r"chapter\s+(\d+|[ivxlc]+)", re.IGNORECASE)
_STOP = {"the", "a", "an", "of", "to", "and", "or", "is", "are", "what", "how",
         "does", "do", "in", "on", "for", "this", "that", "it", "as", "with",
         "summarize", "summarise", "explain", "tell", "me", "about", "book"}


def _load_prompt(name: str) -> str:
    with open(os.path.join(_PROMPT_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def _extract_chapter_ref(question: str) -> str | None:
    m = _CHAPTER_RE.search(question)
    return m.group(0) if m else None


def build_context(graph: dict, question: str) -> tuple[str, list[dict]]:
    """Return (system_prompt, citations) grounded on the relevant graph subset."""
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    brief = graph.get("brief") or {}

    chapter = _extract_chapter_ref(question)
    if chapter:
        # Chapter-scoped: everything tagged to that chapter.
        relevant = [n for n in nodes
                    if any(chapter.lower() in (r.get("chapter") or "").lower()
                           for r in n.get("source_refs", []))]
        relevant = relevant[:30] or nodes[:20]
    else:
        # Keyword overlap between the question and node name/definition.
        q_words = {w for w in re.findall(r"[a-z0-9]+", question.lower()) if w not in _STOP}
        scored = []
        for n in nodes:
            text = f"{n['name']} {n.get('definition','')}".lower()
            n_words = set(re.findall(r"[a-z0-9]+", text))
            overlap = len(q_words & n_words)
            if overlap:
                scored.append((overlap, n))
        scored.sort(key=lambda x: -x[0])
        relevant = [n for _, n in scored[:20]] or nodes[:15]

    node_ids = {n["id"] for n in relevant}
    rel_edges = [e for e in edges if e["source"] in node_ids or e["target"] in node_ids][:30]

    lines = []
    if brief:
        if brief.get("thesis"):
            lines.append(f"Document thesis: {brief['thesis']}")
        if brief.get("summary"):
            lines.append(f"Overview: {brief['summary']}")
        lines.append("")
    lines.append("Relevant concepts:")
    for n in relevant:
        refs = ", ".join(f"{r.get('chapter') or '?'} p.{r.get('page_start')}-{r.get('page_end')}"
                         for r in n.get("source_refs", []))
        lines.append(f"- {n['name']} ({n['type']}): {n.get('definition','')} [{refs}]")
    if rel_edges:
        lines.append("\nRelationships:")
        for e in rel_edges:
            ev = f" — {e['evidence']}" if e.get("evidence") else ""
            lines.append(f"- {e['source']} --{e['type']}--> {e['target']}{ev}")

    context = "\n".join(lines)
    system_prompt = _load_prompt("chat_answer.txt").replace("{context}", context)

    # Citations: the source_refs of the concepts we grounded on (deduped).
    citations, seen = [], set()
    for n in relevant:
        for r in n.get("source_refs", []):
            key = (n["id"], r.get("chapter"), r.get("page_start"), r.get("page_end"))
            if key in seen:
                continue
            seen.add(key)
            citations.append({
                "node_id": n["id"], "name": n["name"],
                "chapter": r.get("chapter"), "page_start": r.get("page_start"),
                "page_end": r.get("page_end"),
            })
    return system_prompt, citations[:12]
