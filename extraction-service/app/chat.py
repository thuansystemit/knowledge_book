"""Graph-grounded chat: select a relevant slice of the stored knowledge graph
for a question and build the system prompt + citations from it.

No embeddings / RAG — grounding is the graph we already have (nodes, edges,
brief, source_refs). Retrieval is keyword overlap + optional chapter scoping."""
from __future__ import annotations

import math
import os
import re

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")
_CHAPTER_RE = re.compile(r"chapter\s+(\d+|[ivxlc]+)", re.IGNORECASE)
_STOP = {"the", "a", "an", "of", "to", "and", "or", "is", "are", "what", "how",
         "does", "do", "in", "on", "for", "this", "that", "it", "as", "with",
         "summarize", "summarise", "explain", "tell", "me", "about", "book",
         # common function/filler words — drop so ranking keys on content, not
         # incidental connectors (improves precision).
         "so", "every", "one", "two", "keep", "from", "by", "at", "be", "can",
         "i", "my", "your", "you", "we", "they", "them", "their", "its", "then",
         "than", "when", "where", "which", "who", "will", "would", "should",
         "could", "may", "might", "if", "but", "not", "no", "up", "out", "into",
         "some", "any", "all", "each", "more", "most", "other", "others", "such",
         "very", "just", "also", "use", "using", "used", "make", "get", "many",
         "much", "over", "out", "there", "here", "these", "those", "was", "were",
         "has", "have", "had", "been", "being", "our", "us", "am",
         # filler verbs/quantifiers so thin follow-ups ("give me examples of it")
         # resolve to the prior topic instead of matching the filler word.
         "give", "show", "list", "want", "need", "like", "more", "less", "please"}


def _load_prompt(name: str) -> str:
    with open(os.path.join(_PROMPT_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def _extract_chapter_ref(question: str) -> str | None:
    m = _CHAPTER_RE.search(question)
    return m.group(0) if m else None


def retrieve(graph: dict, question: str) -> tuple[list[dict], list[dict], dict]:
    """Select the relevant graph slice for a question.

    Pure, zero-LLM retrieval (keyword overlap + optional chapter scoping). Shared
    by both chat modes: `build_context` (LLM) and `compose_answer` (retrieval).
    Returns (relevant_nodes, related_edges, brief)."""
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
    return relevant, rel_edges, brief


def _citations(relevant: list[dict]) -> list[dict]:
    """Deduped source refs for the grounding concepts (capped)."""
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
    return citations[:12]


def build_context(graph: dict, question: str) -> tuple[str, list[dict]]:
    """Return (system_prompt, citations) grounded on the relevant graph subset."""
    relevant, rel_edges, brief = retrieve(graph, question)

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
    return system_prompt, _citations(relevant)


_SUMMARY_HINTS = ("summar", "thesis", "overview", "main point", "main idea",
                  "what is this", "what's this", "about this document", "tl;dr", "gist")


def _is_summary_question(question: str) -> bool:
    q = question.lower()
    return any(h in q for h in _SUMMARY_HINTS)


# Light suffix-stripping stemmer (RC-11/RC-13): folds morphological variants
# (plurals, tenses) so "prototypes"↔"prototyping", "refactor"↔"refactoring",
# "caches"↔"caching" match. Suffixes are prefix-preserving so stemmed query terms
# remain substrings of the source text (keeps `_best_excerpt` highlighting working).
_SUFFIXES = ("ization", "isation", "ations", "ation", "ings", "ing",
             "edly", "edness", "ed", "ly", "ies", "es", "s")


def _stem(w: str) -> str:
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)]
    return w


def _tokens(text: str) -> list[str]:
    """Stemmed, stop-word-filtered tokens (RC-11). Drops single-char tokens too,
    so contraction fragments ("don't" -> "don"/"t") don't create noise matches."""
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) > 1 and w not in _STOP]


# Curated technical-synonym lexicon (RC-13): topically-related software terms so
# paraphrased questions reach the right concept ("duplicating"->"repeat",
# "interdependent"->"independent", "stub/throwaway"->"prototype"). This is a
# limited hand lexicon on purpose — broad open-domain synonymy is what embeddings
# (RC-14) are for. Groups are software-specific to avoid matching off-topic queries.
_SYNONYM_GROUPS = [
    {"duplicate", "duplicating", "duplication", "redundant", "redundancy", "repeat", "repeating", "repetition"},
    {"coupled", "coupling", "decoupled", "decoupling", "independent", "independence", "interdependent", "interdependence", "orthogonal", "dependency", "dependencies", "dependent"},
    {"prototype", "prototypes", "prototyping", "throwaway", "disposable", "stub", "mockup", "spike", "sketch"},
    {"refactor", "refactoring", "restructure", "restructuring", "rework", "cleanup"},
    {"cache", "caching", "caches", "memoize", "memoization"},
    {"drawback", "drawbacks", "limitation", "limitations", "downside", "disadvantage", "tradeoff"},
    {"fast", "faster", "speed", "performance", "latency", "throughput", "slow"},
    {"bug", "bugs", "defect", "defects", "error", "errors", "fault", "issue"},
    {"test", "testing", "tests", "verification", "validation"},
    {"concurrency", "concurrent", "parallel", "parallelism", "threading", "async", "asynchronous"},
    {"maintainable", "maintainability", "maintenance"},
    {"readable", "readability", "clarity", "clear"},
    {"secure", "security", "authentication", "authorization", "auth"},
    {"abstraction", "abstract", "encapsulation", "encapsulate"},
]


def _build_synonyms() -> dict[str, set[str]]:
    m: dict[str, set[str]] = {}
    for group in _SYNONYM_GROUPS:
        stems = {_stem(w) for w in group}
        for s in stems:
            m.setdefault(s, set()).update(stems - {s})
    return m


_SYNONYMS = _build_synonyms()


def _expand(stems: set[str]) -> set[str]:
    """Grow a stem set with its curated synonyms (RC-13)."""
    out = set(stems)
    for s in stems:
        out |= _SYNONYMS.get(s, set())
    return out


def _q_words(question: str) -> set[str]:
    return _expand(set(_tokens(question)))


def _idf(docs: list[set[str]]) -> dict[str, float]:
    """Inverse-document-frequency over a small corpus of token sets (RC-11): rare
    terms weigh more than common ones, so ranking isn't dominated by filler words."""
    n = len(docs) or 1
    df: dict[str, int] = {}
    for d in docs:
        for t in d:
            df[t] = df.get(t, 0) + 1
    return {t: math.log(1 + n / c) for t, c in df.items()}


def _rank_chunks(graph: dict, q_words: set[str], k: int = 2,
                 min_overlap: int = 1) -> list[dict]:
    """Rank persisted section chunks (RC-10) by IDF-weighted stem overlap — pure
    lexical, no model (RC-11). Keeps only chunks sharing ≥ `min_overlap` stems,
    ranks the survivors by summed IDF, returns the top-k."""
    if not q_words:
        return []
    chunks = graph.get("chunks") or []
    docs = [set(_tokens(c.get("content", ""))) for c in chunks]
    idf = _idf(docs)
    scored: list[tuple[float, dict]] = []
    for c, d in zip(chunks, docs):
        common = q_words & d
        if len(common) >= min_overlap:
            scored.append((sum(idf.get(t, 0.0) for t in common), c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:k]]


def _match_concepts(graph: dict, q_words: set[str]) -> list[dict]:
    """Concept nodes sharing ≥1 stem with the question, ranked by IDF-weighted
    overlap (RC-11) — a *real* match, unlike `retrieve`'s top-N fallback which is
    for grounding the LLM (RC-15). Stemming folds plural/tense variants (RC-13)."""
    if not q_words:
        return []
    nodes = graph.get("nodes") or []
    docs = [set(_tokens(f"{n.get('name','')} {n.get('definition','')}")) for n in nodes]
    idf = _idf(docs)
    scored: list[tuple[float, dict]] = []
    for n, d in zip(nodes, docs):
        common = q_words & d
        if common:
            # A name-token match is a strong signal — weight it above definition-only hits.
            name_stems = set(_tokens(n.get("name", "")))
            bonus = 2.0 * sum(idf.get(t, 0.0) for t in (common & name_stems))
            scored.append((sum(idf.get(t, 0.0) for t in common) + bonus, n))
    scored.sort(key=lambda x: -x[0])
    return [n for _, n in scored]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _semantic_indices(query_vec: list[float], vectors: list, k: int,
                      threshold: float) -> list[int]:
    """Indices of the top-k stored vectors with cosine >= threshold (RC-14)."""
    scored = [(i, _cosine(query_vec, v)) for i, v in enumerate(vectors or [])]
    scored = [(i, s) for i, s in scored if s >= threshold]
    scored.sort(key=lambda x: -x[1])
    return [i for i, _ in scored[:k]]


def _best_excerpt(content: str, q_words: set[str], width: int = 360) -> str:
    """A ~width-char verbatim window centred on the first keyword hit (RC-12)."""
    text = " ".join((content or "").split())
    if not text:
        return ""
    low = text.lower()
    pos = next((low.find(w) for w in sorted(q_words, key=len, reverse=True)
                if low.find(w) >= 0), 0)
    start = max(0, pos - width // 2)
    end = min(len(text), start + width)
    snippet = text[start:end].strip()
    return ("… " if start > 0 else "") + snippet + (" …" if end < len(text) else "")


def _chunk_citation(c: dict) -> dict:
    return {"node_id": None, "name": "source excerpt", "chapter": c.get("chapter"),
            "page_start": c.get("page_start"), "page_end": c.get("page_end")}


# Anaphora that signal a follow-up leaning on the previous turn's topic (RC-17).
_ANAPHORA = {"it", "its", "they", "them", "their", "that", "this", "these",
             "those", "one", "ones", "he", "she", "his", "her", "theirs"}


def _is_followup(question: str, content_tokens: set[str]) -> bool:
    """A thin, anaphoric question ("and its drawbacks?") that only makes sense
    with the previous turn's topic carried in (RC-17)."""
    raw = set(re.findall(r"[a-z]+", question.lower()))
    return len(content_tokens) <= 1 and bool(raw & _ANAPHORA)


def compose_answer(graph: dict, question: str,
                   prev_question: str | None = None,
                   query_vector: list[float] | None = None,
                   sim_threshold: float = 0.55,
                   semantic_node_idx: list[int] | None = None,
                   semantic_chunk_idx: list[int] | None = None) -> tuple[str, list[dict], bool]:
    """Deterministically compose an answer from the extracted graph — no LLM.

    Stitches the retrieved concept definitions, relationships, and (for
    summary-style questions) the document brief into a readable response.
    `prev_question` (the previous user turn) lets a thin follow-up like "and its
    drawbacks?" inherit the earlier topic (RC-17). Returns
    (answer_text, citations, weak) where `weak` is True when nothing matched and
    the answer is a not-covered / overview fallback (drives the RC-22 upgrade prompt)."""
    brief = graph.get("brief") or {}
    q_words = _q_words(question)

    # RC-17: carry the previous turn's topic into an anaphoric follow-up.
    if prev_question and _is_followup(question, set(_tokens(question))):
        q_words |= _q_words(prev_question)

    # Summary / thesis questions: answer straight from the brief when available.
    if _is_summary_question(question) and (brief.get("thesis") or brief.get("summary")):
        parts = []
        if brief.get("thesis"):
            parts.append(f"The document's central thesis is: {brief['thesis']}")
        if brief.get("summary"):
            parts.append(brief["summary"])
        return "\n\n".join(parts), _citations(retrieve(graph, question)[0]), False

    # RC-15: only answer on a *real* keyword match. Concept name/definition hits
    # are strong signal (>=1 keyword); chunk excerpts need >=2 to avoid surfacing
    # a passage that merely shares one common word.
    concept_hits = _match_concepts(graph, q_words)
    chunk_hits = _rank_chunks(graph, q_words, k=2, min_overlap=2)

    # RC-14 / OUT-04: augment lexical hits with semantic (embedding) matches —
    # catches open-domain paraphrases that share no words. Candidate indices come
    # from pgvector (`semantic_*_idx`, resolved by the caller with a DB session)
    # when available, else from the in-JSON cosine scan (legacy jobs / no DB).
    # Either way the ANSWER is still composed from the graph nodes/chunks below —
    # the vector store only widens the candidate set, it never produces text.
    if query_vector is not None or semantic_node_idx is not None:
        nodes = graph.get("nodes") or []
        node_idx = (semantic_node_idx if semantic_node_idx is not None
                    else _semantic_indices(query_vector, graph.get("node_vectors"), 5, sim_threshold))
        have = {n["id"] for n in concept_hits}
        for i in node_idx:
            if i < len(nodes) and nodes[i].get("id") not in have:
                concept_hits.append(nodes[i]); have.add(nodes[i].get("id"))
        chunks = graph.get("chunks") or []
        chunk_idx = (semantic_chunk_idx if semantic_chunk_idx is not None
                     else _semantic_indices(query_vector, graph.get("chunk_vectors"), 2, sim_threshold))
        have_c = {c.get("index") for c in chunk_hits}
        extra = [chunks[i] for i in chunk_idx
                 if i < len(chunks) and chunks[i].get("index") not in have_c]
        chunk_hits = (chunk_hits + extra)[:3]

    # Confidence gate: nothing matched -> be honest rather than guess.
    if not concept_hits and not chunk_hits:
        if brief.get("summary"):
            return (
                "I couldn't find anything in this document matching your question. "
                f"Here is the document overview:\n\n{brief['summary']}"
            ), [], True
        return (
            "This document doesn't appear to cover that. Try a specific term from "
            "the document, or rephrase your question."
        ), [], True

    parts: list[str] = []
    citations = _citations(concept_hits[:5])

    # Concept definitions (the core of the answer).
    for n in concept_hits[:5]:
        definition = (n.get("definition") or "").strip()
        if definition:
            parts.append(f"**{n['name']}** — {definition}")

    # Relationships among the matched concepts only.
    matched_ids = {n["id"] for n in concept_hits[:5]}
    rels = []
    for e in graph.get("edges") or []:
        if e.get("source") in matched_ids and e.get("target") in matched_ids:
            ev = f" ({e['evidence']})" if e.get("evidence") else ""
            rels.append(f"- {e['source']} {str(e.get('type', 'relates to')).lower()} {e['target']}{ev}")
        if len(rels) >= 5:
            break
    if rels:
        parts.append("How these connect:\n" + "\n".join(rels))

    # Verbatim source excerpts from the persisted chunks (RC-12).
    for c in chunk_hits:
        excerpt = _best_excerpt(c.get("content", ""), q_words)
        if excerpt:
            cite = f"{c.get('chapter') or '?'} p.{c.get('page_start')}-{c.get('page_end')}"
            parts.append(f"From the document ({cite}):\n> {excerpt}")
            citations.append(_chunk_citation(c))

    # A concept matched but had no definition/edges and no excerpt cleared the bar:
    # still better to name the concept than to claim the doc doesn't cover it.
    if not parts and concept_hits:
        names = ", ".join(n["name"] for n in concept_hits[:5])
        parts.append(f"This document discusses: {names}.")

    return "\n\n".join(parts), citations[:12], False
