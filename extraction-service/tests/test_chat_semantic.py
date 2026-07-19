"""OUT-04: compose_answer honours pgvector-resolved semantic candidate indices
while keeping the knowledge graph the source of the answer (grounding stays
authoritative — the vector store only widens the candidate set).

DB-free: exercises the index-passing contract, not the pgvector SQL (that is
covered by the embeddings_store integration check against a live pgvector DB)."""
from app.chat import compose_answer

# n0 shares NO keyword with the question, so lexical `_match_concepts` misses it.
# It can only enter the answer via a semantic candidate index.
GRAPH = {
    "nodes": [
        {"id": "n0", "name": "Quorum", "type": "Concept",
         "definition": "A voting threshold for agreement across distributed replicas.",
         "source_refs": [{"chapter": "Ch8", "page_start": 10, "page_end": 12}]},
        {"id": "n1", "name": "Marsupial", "type": "Concept",
         "definition": "An unrelated animal classification.", "source_refs": []},
    ],
    "chunks": [],
    "edges": [],
    "brief": {},
}
Q = "explain xyzzy plugh"  # no overlap with any node name/definition


def test_semantic_node_index_includes_nonlexical_concept():
    """A node with no keyword overlap is surfaced when its index is passed."""
    ans, cites, weak = compose_answer(GRAPH, Q, semantic_node_idx=[0], semantic_chunk_idx=[])
    assert weak is False
    assert "Quorum" in ans
    assert any(c["node_id"] == "n0" for c in cites)   # grounded citation preserved


def test_empty_semantic_index_yields_no_match():
    """Empty candidate lists (pgvector found nothing above threshold) -> honest
    not-covered answer, not a hallucinated one."""
    ans, cites, weak = compose_answer(GRAPH, Q, semantic_node_idx=[], semantic_chunk_idx=[])
    assert weak is True
    assert cites == []


def test_legacy_json_vector_fallback_still_works():
    """When no pgvector indices are passed but query_vector + in-JSON node_vectors
    exist (legacy jobs), the in-JSON cosine path still augments the candidates."""
    g = dict(GRAPH)
    g["node_vectors"] = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]  # aligns with nodes
    ans, cites, weak = compose_answer(
        g, Q, query_vector=[1.0, 0.0, 0.0], sim_threshold=0.5)
    assert weak is False
    assert "Quorum" in ans


def test_out_of_range_index_is_ignored_safely():
    """A stale index past the node list (e.g. after a graph shrink) is skipped,
    not an IndexError."""
    ans, cites, weak = compose_answer(GRAPH, Q, semantic_node_idx=[0, 99], semantic_chunk_idx=[])
    assert "Quorum" in ans  # valid index kept, bogus one dropped
