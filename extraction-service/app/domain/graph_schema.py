"""Knowledge-graph schema — node and edge types per the PRD (§8).

Node types:  Concept, Principle, Term, Example, Person, Tool
Edge types:  is_prerequisite_of, relates_to, contrasts_with, exemplifies,
             is_part_of, leads_to, defined_in, cited_in

Every node and edge carries `source_refs` (chapter + page range) and a
`confidence` score, and `extraction_method` ("explicit" | "inferred"). MVP keeps
edges to explicit, source-cited statements (PRD risk R1: no hallucinated edges)."""
from __future__ import annotations

NODE_TYPES = {"Concept", "Principle", "Term", "Example", "Person", "Tool"}

EDGE_TYPES = {
    "is_prerequisite_of",
    "relates_to",
    "contrasts_with",
    "exemplifies",
    "is_part_of",
    "leads_to",
    "defined_in",
    "cited_in",
}


def canonical_key(name: str) -> str:
    """Normalised key for conservative dedup: lowercase, collapse whitespace,
    strip surrounding punctuation. Deliberately conservative — we prefer two
    separate nodes over a wrong merge (PRD AD-6 / risk R5)."""
    return " ".join((name or "").lower().split()).strip(" .,:;\"'")
