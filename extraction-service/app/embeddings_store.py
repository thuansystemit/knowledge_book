"""pgvector persistence + nearest-neighbour search for retrieval (OUT-04).

Finishes the OUT-04 plan that `embeddings.py` deferred: instead of keeping the
concept/chunk vectors inside the `jobs.graph` JSON and scanning them with Python
cosine (`chat._semantic_indices`, O(n) per query), the vectors live in a
dedicated `chunk_embeddings` table and are searched with pgvector's `<=>` cosine
operator inside Postgres — same DB, same transaction boundary, tenant-scoped by
the same `org_id`/`category_id` columns as everything else.

Design notes:
- **Grounding stays authoritative.** This module only returns *indices* into the
  job's `graph["nodes"]` / `graph["chunks"]`; the answer is still composed from
  the knowledge graph (definitions, edges, source_refs) by `chat.compose_answer`.
  pgvector never produces answer text — it only widens the candidate set.
- **No new dependency.** Vectors are passed as pgvector text literals (`'[..]'`)
  and cast in SQL, so we don't need the `pgvector` Python adapter.
- **Backward compatible.** Jobs embedded before this table existed keep their
  `graph["*_vectors"]`; callers fall back to the JSON path when `has_rows` is
  False (see `chat_routes`).
- The `embedding` column is an unspecified-dimension `vector`, so switching
  embedding models (different dims) needs no migration. An ANN index (ivfflat/
  hnsw) requires a fixed dim and is a documented follow-up; per-job search over a
  few hundred rows is an exact seq-scan and fast.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.observability import audit


def _to_pgvector(vec: list[float]) -> str:
    """Format a float list as a pgvector text literal: [1,2,3]."""
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def delete_job(db: Session, job_id: str) -> None:
    """Remove all embeddings for a job (idempotent). Called before re-embedding
    on reprocess/retry; job deletion is also covered by the FK ON DELETE CASCADE."""
    db.execute(text("DELETE FROM chunk_embeddings WHERE job_id = :j"), {"j": job_id})


def has_rows(db: Session, job_id: str) -> bool:
    """True if this job has embeddings in the table (vs. only legacy JSON vectors)."""
    return bool(db.execute(
        text("SELECT 1 FROM chunk_embeddings WHERE job_id = :j LIMIT 1"),
        {"j": job_id}).first())


def sync_job(db: Session, job_id: str, org_id: str | None, category_id: str | None,
             model: str | None, node_vectors: list[list[float]] | None,
             chunk_rows: list[tuple[int, int, list[float]]] | None) -> int:
    """Replace this job's embeddings (delete + insert).

    `node_vectors[i]` aligns with `graph["nodes"][i]` (one vector per concept,
    `sub`=0). `chunk_rows` is `(chunk_idx, sub_idx, vector)` — a chunk may have
    several sub-passage vectors (OUT-04e), all pointing at the same parent
    `graph["chunks"]` index. Returns rows written. Safe with empty/None (just
    clears the job's rows). The caller owns the transaction/commit."""
    delete_job(db, job_id)
    rows = []
    for idx, vec in enumerate(node_vectors or []):
        if vec:
            rows.append({"j": job_id, "o": org_id, "c": category_id, "k": "node",
                         "i": idx, "s": 0, "m": model, "e": _to_pgvector(vec)})
    for idx, sub, vec in (chunk_rows or []):
        if vec:
            rows.append({"j": job_id, "o": org_id, "c": category_id, "k": "chunk",
                         "i": idx, "s": sub, "m": model, "e": _to_pgvector(vec)})
    if rows:
        db.execute(text(
            "INSERT INTO chunk_embeddings "
            "(job_id, org_id, category_id, kind, idx, sub, model, embedding) "
            "VALUES (:j, :o, :c, :k, :i, :s, :m, CAST(:e AS vector))"), rows)
    audit("PGVECTOR_SYNC", job=job_id, rows=len(rows))
    return len(rows)


def search(db: Session, job_id: str, kind: str, query_vec: list[float],
           k: int, threshold: float) -> list[int]:
    """Top-k distinct `graph` indices for `kind` ('node'|'chunk') whose cosine
    similarity to `query_vec` is >= threshold, most similar first. pgvector `<=>`
    is cosine *distance* (similarity = 1 - distance). A chunk with several
    sub-passage vectors (OUT-04e) is deduped to its best-matching sub-passage via
    `DISTINCT ON (idx)`, so results are parent-chunk indices, never duplicated."""
    if not query_vec:
        return []
    q = _to_pgvector(query_vec)
    rows = db.execute(text(
        "SELECT idx, sim FROM ("
        " SELECT DISTINCT ON (idx) idx, 1 - (embedding <=> CAST(:q AS vector)) AS sim"
        " FROM chunk_embeddings WHERE job_id = :j AND kind = :k"
        " ORDER BY idx, embedding <=> CAST(:q AS vector)) s "
        "ORDER BY sim DESC LIMIT :lim"),
        {"q": q, "j": job_id, "k": kind, "lim": k}).all()
    return [int(idx) for idx, sim in rows if sim is not None and sim >= threshold]
