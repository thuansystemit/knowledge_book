"""OUT-04: pgvector store integration test (sync / KNN search / idempotency /
cleanup). Requires a live pgvector-enabled Postgres reachable via DATABASE_URL —
skips otherwise, so it is safe to collect in a DB-less CI run.

Not in the CI file list (CI has no Postgres); run locally with:
    docker exec extraction-service-worker-1 python -m pytest tests/test_embeddings_store.py -q
"""
import pytest

pytest.importorskip("sqlalchemy")
from sqlalchemy import text  # noqa: E402


def _db_or_skip():
    try:
        from app.db import session_scope
        with session_scope() as db:
            db.execute(text("SELECT 1 FROM chunk_embeddings LIMIT 1"))
        return session_scope
    except Exception as e:  # no DB / no table / no pgvector -> skip, don't fail
        pytest.skip(f"pgvector DB not available: {e}")


def test_sync_search_idempotent_delete():
    session_scope = _db_or_skip()
    import uuid
    from app import embeddings_store as es
    with session_scope() as db:
        # Create a THROWAWAY job so the test never touches real data (the FK needs
        # a real jobs row; dropping it at the end cascade-deletes the embeddings).
        uid = db.execute(text("SELECT id FROM users LIMIT 1")).scalar()
        if not uid:
            pytest.skip("no users in DB to own a test job")
        job_id = "test_" + uuid.uuid4().hex[:24]
        org_id, cat_id = None, None
        db.execute(text(
            "INSERT INTO jobs (id, user_id, title, status, events, created_at, updated_at) "
            "VALUES (:i, :u, 'pgvector-test', 'done', '[]', now(), now())"),
            {"i": job_id, "u": uid})

        nv = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.9, 0.1, 0.0]]
        # chunk 0 has TWO sub-passages (OUT-04e), chunk 1 has one
        chunk_rows = [(0, 0, [0.0, 0.0, 1.0]), (0, 1, [0.3, 0.3, 0.9]),
                      (1, 0, [1.0, 1.0, 0.0])]
        try:
            assert es.sync_job(db, job_id, org_id, cat_id, "test", nv, chunk_rows) == 6
            assert es.has_rows(db, job_id) is True

            # cosine KNN: query == node 0 -> node 0 first, then the near [0.9,0.1,0]
            assert es.search(db, job_id, "node", [1.0, 0.0, 0.0], 3, 0.5)[:2] == [0, 2]
            # threshold filters an orthogonal query
            assert es.search(db, job_id, "node", [0.0, 0.0, 1.0], 3, 0.5) == []
            # chunk search near [0,0,1] -> chunk 0 via its best sub-passage,
            # deduped to the parent index (not two rows for chunk 0)
            chits = es.search(db, job_id, "chunk", [0.0, 0.0, 1.0], 3, 0.5)
            assert chits[0] == 0 and chits.count(0) == 1, chits
            # re-sync replaces (no duplicate rows)
            es.sync_job(db, job_id, org_id, cat_id, "test", nv, chunk_rows)
            cnt = db.execute(text("SELECT count(*) FROM chunk_embeddings WHERE job_id=:j"),
                             {"j": job_id}).scalar()
            assert cnt == 6
        finally:
            # Drop the throwaway job — FK ON DELETE CASCADE removes its embeddings.
            db.execute(text("DELETE FROM jobs WHERE id = :i"), {"i": job_id})
            db.commit()
        assert es.has_rows(db, job_id) is False
