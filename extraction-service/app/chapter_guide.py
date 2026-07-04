"""Chapter Guide output (OUT-03) — built deterministically from the graph.

For each detected chapter: a one-line summary, the **concepts introduced** (their
canonical concept IDs, so the UI links to the Concept Map), and **prerequisite
concepts** (concepts a chapter's ideas link to but that were introduced in an
earlier chapter). No LLM call — derived from the extracted nodes, edges, and
chunks, so it's free, instant, and consistent with the retrieval-first design.
"""
from __future__ import annotations

_UNKNOWN = "(unknown)"


def _home_chapters(nodes: list[dict]) -> tuple[dict, dict]:
    """Map each concept id -> the chapter it is *introduced* in (earliest source
    ref by page), and each chapter -> its earliest page (for ordering)."""
    home: dict[str, str] = {}
    chapter_page: dict[str, float] = {}
    for n in nodes:
        refs = n.get("source_refs") or []
        if not refs:
            continue
        best = min(refs, key=lambda r: (r.get("page_start") if r.get("page_start") is not None else 1e18))
        ch = best.get("chapter") or _UNKNOWN
        home[n["id"]] = ch
        ps = best.get("page_start") if best.get("page_start") is not None else 1e18
        chapter_page[ch] = min(chapter_page.get(ch, 1e18), ps)
    return home, chapter_page


def build(graph: dict | None) -> list[dict]:
    """Return the chapter guide: a list of per-chapter entries, ordered by first
    appearance in the document."""
    if not graph:
        return []
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    chunks = graph.get("chunks") or []
    if not nodes:
        return []

    home, chapter_page = _home_chapters(nodes)
    # Fold in chapters seen only in chunks, so every detected chapter has an entry.
    for c in chunks:
        ch = c.get("chapter") or _UNKNOWN
        ps = c.get("page_start") if c.get("page_start") is not None else 1e18
        chapter_page[ch] = min(chapter_page.get(ch, 1e18), ps)

    introduced: dict[str, list[dict]] = {}
    for n in nodes:
        ch = home.get(n["id"])
        if ch is not None:
            introduced.setdefault(ch, []).append(n)

    chapters = sorted(chapter_page.keys(), key=lambda ch: chapter_page[ch])
    order = {ch: i for i, ch in enumerate(chapters)}
    names = {n["id"]: n.get("name", n["id"]) for n in nodes}

    guide: list[dict] = []
    for ch in chapters:
        concs = sorted(introduced.get(ch, []), key=lambda n: -(n.get("confidence") or 0))
        conc_ids = {n["id"] for n in concs}

        # Prerequisites: concepts these link to that were introduced earlier.
        prereq_ids: set[str] = set()
        for e in edges:
            pair = ((e.get("source"), e.get("target")), (e.get("target"), e.get("source")))
            for a, b in pair:
                if a in conc_ids and b not in conc_ids:
                    bh = home.get(b)
                    if bh is not None and order.get(bh, 1e9) < order[ch]:
                        prereq_ids.add(b)

        top = [n.get("name", n["id"]) for n in concs[:5]]
        if top:
            summary = f"Introduces {len(concs)} concept(s): " + ", ".join(top) + \
                      ("…" if len(concs) > 5 else ".")
        else:
            summary = "No new concepts detected in this chapter."

        guide.append({
            "chapter": ch,
            "summary": summary,
            "concepts_introduced": [{"id": n["id"], "name": n.get("name", n["id"])} for n in concs],
            "prerequisites": [{"id": pid, "name": names.get(pid, pid)} for pid in sorted(prereq_ids)],
        })
    return guide
