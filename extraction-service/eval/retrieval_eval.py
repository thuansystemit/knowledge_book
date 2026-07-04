"""Retrieval-quality eval harness (RC-16).

Deterministic, self-contained recall@k for the zero-LLM retrieval functions in
`app.chat`. No DB, no model, no network — a fixed fixture graph + a Q→expected
set — so it runs anywhere and gates merges (non-zero exit on regression).

Run from a source checkout (CI or locally) — `app.chat` is pure, so no install,
DB, or model is needed:
    cd extraction-service && python3 eval/retrieval_eval.py

It reports recall@{1,3,5} for concept retrieval, chunk-retrieval recall, and the
honest "not covered" rate on off-topic questions, then exits 1 if recall@3 falls
below THRESHOLD. Use the printed numbers as the baseline when upgrading RC-11 to
BM25 — the harness should show a measurable lift, not a regression.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.chat import _match_concepts, _q_words, _rank_chunks, compose_answer  # noqa: E402

THRESHOLD = 0.70  # required recall@3 for the harness to pass

# --- Fixture: a small "Pragmatic Programmer"-style graph -------------------
def _node(nid, name, typ, definition, chapter, p0, p1):
    return {"id": nid, "name": name, "type": typ, "definition": definition,
            "source_refs": [{"chapter": chapter, "page_start": p0, "page_end": p1}]}


GRAPH = {
    "nodes": [
        _node("DRY", "DRY", "Principle",
              "Don't Repeat Yourself: every piece of knowledge has a single, unambiguous representation.", "Chapter 2", 30, 34),
        _node("Orthogonality", "Orthogonality", "Concept",
              "Components should be independent so a change in one does not affect others.", "Chapter 2", 41, 47),
        _node("TracerBullets", "Tracer Bullets", "Concept",
              "Build a thin end-to-end slice to get feedback and find the target early.", "Chapter 2", 48, 52),
        _node("Prototyping", "Prototyping", "Concept",
              "Throwaway code to explore risky ideas and learn before committing.", "Chapter 2", 53, 55),
        _node("Refactoring", "Refactoring", "Concept",
              "Restructure existing code to improve design without changing behaviour.", "Chapter 6", 184, 190),
        _node("Caching", "Caching", "Concept",
              "Store results to reuse them and reduce repeated work.", "Chapter 7", 220, 224),
    ],
    "edges": [
        {"source": "DRY", "target": "Orthogonality", "type": "supports", "evidence": "both reduce coupling"},
    ],
    "brief": {"thesis": "Pragmatic habits produce maintainable software.",
              "summary": "A book on pragmatic software craftsmanship."},
    "chunks": [
        {"index": 0, "chapter": "Chapter 7", "page_start": 220, "page_end": 224,
         "content": "Caching improves latency by reusing results. The drawbacks of caching are staleness and invalidation complexity, which can introduce subtle bugs."},
        {"index": 1, "chapter": "Chapter 2", "page_start": 41, "page_end": 47,
         "content": "Orthogonality means eliminating effects between unrelated things, so systems are easier to change and test."},
        {"index": 2, "chapter": "Chapter 6", "page_start": 184, "page_end": 190,
         "content": "Refactoring is disciplined restructuring; refactor early and often to keep the design healthy."},
    ],
}

# --- Eval set: question -> expected concept id (None = should be "not covered")
CONCEPT_CASES = [
    ("What is DRY?", "DRY"),
    ("explain the don't repeat yourself principle", "DRY"),
    ("how does orthogonality help?", "Orthogonality"),
    ("what are tracer bullets?", "TracerBullets"),
    ("when should I use throwaway prototyping?", "Prototyping"),
    ("tell me about refactoring code", "Refactoring"),
    ("what are the drawbacks of caching?", "Caching"),
]
# Hard paraphrase cases: the question shares NO surface keyword with the concept
# name/definition, so pure lexical overlap (RC-11 today) is expected to miss them.
# Reported separately (not gated) — this is the headroom BM25 (RC-11) / synonym
# expansion (RC-13) / embeddings (RC-14) should close. Track the number over time.
HARD_CONCEPT_CASES = [
    ("how do I avoid duplicating logic?", "DRY"),
    ("what happens when modules are too interdependent?", "Orthogonality"),
    ("stub code I plan to throw away", "Prototyping"),
]
# Morphological variants (plural/tense) that share a *stem* but not the surface
# form. Pure keyword overlap misses these; light stemming (RC-11/RC-13) catches
# them. Pre-stemming baseline was 0.00; expect ~1.00 after.
MORPH_CONCEPT_CASES = [
    ("explain prototypes", "Prototyping"),
    ("refactor the codebase", "Refactoring"),
    ("caches everywhere slow me down", "Caching"),
]
# Passage questions -> expected source chapter to appear in a chunk hit
CHUNK_CASES = [
    ("drawbacks of caching", "Chapter 7"),
    ("eliminating effects between unrelated things", "Chapter 2"),
]
OFFTOPIC = ["medieval french cuisine", "how do rockets reach orbit", "best coffee beans"]


def _recall_at_k(k: int, cases=CONCEPT_CASES) -> float:
    hits = 0
    for q, expected in cases:
        ranked = _match_concepts(GRAPH, _q_words(q))[:k]
        if any(n["id"] == expected for n in ranked):
            hits += 1
    return hits / len(cases)


def _chunk_recall() -> float:
    hits = 0
    for q, chapter in CHUNK_CASES:
        chunks = _rank_chunks(GRAPH, _q_words(q), k=3, min_overlap=1)
        if any(c.get("chapter") == chapter for c in chunks):
            hits += 1
    return hits / len(CHUNK_CASES)


def _notcovered_rate() -> float:
    ok = 0
    for q in OFFTOPIC:
        ans, _ = compose_answer(GRAPH, q)
        if "doesn't appear to cover" in ans or "couldn't find anything" in ans:
            ok += 1
    return ok / len(OFFTOPIC)


def main() -> int:
    r1, r3, r5 = _recall_at_k(1), _recall_at_k(3), _recall_at_k(5)
    cr = _chunk_recall()
    nc = _notcovered_rate()

    print("Retrieval eval (RC-16) — fixture graph, zero-LLM")
    print(f"  concept recall@1 : {r1:.2f}")
    print(f"  concept recall@3 : {r3:.2f}   (threshold {THRESHOLD:.2f})")
    print(f"  concept recall@5 : {r5:.2f}")
    print(f"  chunk recall     : {cr:.2f}")
    print(f"  not-covered rate : {nc:.2f}   (off-topic honesty)")
    morph = _recall_at_k(3, MORPH_CONCEPT_CASES)
    hard = _recall_at_k(3, HARD_CONCEPT_CASES)
    print(f"  morphological recall@3 : {morph:.2f}   (stemming — was 0.00 pre-RC-11)")
    print(f"  hard-paraphrase recall@3 : {hard:.2f}   (informational — headroom for synonyms/embeddings)")

    ok = r3 >= THRESHOLD and nc == 1.0
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
