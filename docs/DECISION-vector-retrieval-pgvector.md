# Decision: Vector Retrieval via pgvector (finish OUT-04)

| | |
|---|---|
| **Document** | Architecture Decision Record (ADR) + implementation log |
| **Product** | KnowledgeBook (Document Knowledge Graph) |
| **Component** | `extraction-service` — semantic retrieval for document chat |
| **Date** | 2026-07-19 |
| **Status** | ACCEPTED — core wired & verified; follow-ups tracked in §7 |
| **Deciders** | pvthuan |
| **Parents** | `feature-tracking.md` (OUT-04, INF-02, RC-14), `ARCHITECTURE-mvp.md` |
| **Supersedes** | The in-JSON vector storage note in `app/embeddings.py:11-13` |

---

## 0. How to read (standard)

ADR format: **Context → Options → Decision → Consequences → Implementation → Verification → Follow-ups → Changelog.** Same conventions as `docs/ISSUE-*.md`: cite `file:line`, keep it self-describing for humans and AI agents.

---

## 1. Context

The user asked whether to add **ChromaDB** to enable "document chat without LLMs," and what impact that has on the knowledge-graph feature. Investigation (see the `document-extractor` agent analysis, 2026-07-19) found:

- **No-LLM chat already ships and is the default.** `CHAT_MODE` defaults to `"retrieval"` (`app/config.py:164`); `compose_answer` (`app/chat.py:301`) produces a deterministic, graph-grounded, cited answer with **zero generative-LLM calls**.
- **Optional semantic embeddings already exist (RC-14).** `app/embeddings.py` uses an *embedding* model (not a generative LLM). Vectors were stored **inside the `jobs.graph` JSON** (`node_vectors`, `chunk_vectors`) and searched with **O(n) Python cosine** (`app/chat.py::_semantic_indices`).
- **The OUT-04/INF-02 pgvector plan was marked "Done" in the tracker but never actually wired.** No `vector` column, no embeddings table, no `<=>` query existed; the DB image (`postgres:16-alpine`) did not even ship the `vector` extension. Confirmed 2026-07-19.

So the real gaps were **not** "no-LLM chat" (exists) but: O(n) cosine that doesn't scale, vector bloat in the `graph` JSON column, and no cross-document search.

## 2. Options considered

| | (A) ChromaDB | **(B) pgvector** | (C) Status quo (in-JSON) |
|---|---|---|---|
| New infra to operate | Yes (new service, volume, backups) | **No — Postgres already runs** | No |
| Transaction consistency w/ graph | Two-phase, split-brain risk | **Same DB, same commit** | Atomic |
| Tenant isolation | App-enforced metadata filter | **SQL WHERE, same as all data** | Per-job |
| Cross-document search | Yes | **Yes (SQL WHERE)** | Impossible |
| JSON bloat removed | Yes | Yes | No |
| Effort | New dep + service + sync code | **1 table + migration + few queries** | Zero |

## 3. Decision

**Chosen: (B) pgvector.** It closes the real gaps (scalable ANN-ready search, cross-document capability, removes JSON bloat) **without new infrastructure**, keeps vectors in the same transactional store and tenant model as the rest of the data, and simply finishes the already-planned OUT-04. ChromaDB's only edge (independently scaling vector search to millions of docs) is not this product's trajectory and costs a new failure domain.

**Grounding invariant (non-negotiable):** pgvector only returns *candidate indices* into the job's graph; the answer is still composed from the knowledge graph (definitions, edges, `source_refs`) by `compose_answer`. The vector store never produces answer text. This preserves the KG's differentiator (relationship-aware, cited answers) and avoids drift to plain chunk-RAG.

## 4. Consequences

- **Positive:** SQL-side cosine KNN (`<=>`), ANN-index-ready, cross-doc-ready, FK `ON DELETE CASCADE` cleans up embeddings on job delete for free, single `pg_dump` still backs up everything.
- **Cost:** the DB image must be `pgvector/pgvector:pg16` (the alpine image has no `vector`). Existing data migrated via dump→restore (musl→glibc, so raw volume reuse was avoided). 24 jobs / 3 users / 24 PDFs preserved.
- **Backward compatibility:** jobs embedded before this change keep their `graph["*_vectors"]`; the read path falls back to the in-JSON cosine scan when a job has no rows in `chunk_embeddings` (`embeddings_store.has_rows`).

## 5. Implementation (what shipped)

| Area | File | Change |
|---|---|---|
| DB image | `docker-compose.yml` | `db.image` → `pgvector/pgvector:pg16` |
| Migration | `app/migrations.py::run_pgvector` (+ registered in `app/api.py`) | `CREATE EXTENSION vector`; `chunk_embeddings(job_id FK CASCADE, org_id, category_id, kind, idx, model, embedding vector, PK(job_id,kind,idx))` + indexes |
| Store | `app/embeddings_store.py` (new) | `sync_job` (delete+insert), `search` (`<=>` cosine KNN, threshold), `has_rows`, `delete_job`. Vectors passed as pgvector text literals → **no new pip dependency** |
| Write path | `app/tasks.py::_sync_embeddings` | Called after graph save in `run_extraction` + `retry_extraction`; fail-safe (never breaks the job) |
| Read path | `app/chat.py::compose_answer` (+ `app/chat_routes.py`) | New `semantic_node_idx`/`semantic_chunk_idx` params; route resolves them via pgvector when `has_rows`, else JSON fallback. Grounding unchanged |
| Tests | `tests/test_chat_semantic.py`, `tests/test_embeddings_store.py`, CI `ci.yml` | Read-path grounding (DB-free, in CI) + store integration (skips without a pgvector DB) |

**Design notes:** `embedding` is an unspecified-dimension `vector`, so switching embedding models (different dims) needs no migration. Per-job search is an exact seq-scan over a few hundred rows (fast); an ANN index (ivfflat/hnsw) needs a pinned dimension — see §7.

## 5a. Embedding model wiring (end-to-end demo, 2026-07-19)

Wired a real embedding model to light up the pgvector path end-to-end:

- **Model:** `nvidia/nv-embedqa-e5-v5` (1024-dim, retrieval-tuned) on the existing
  NVIDIA OpenAI-compatible endpoint. (`qwen/qwen3.5-122b-a10b` was requested but is
  a *generative* model — `/v1/embeddings` returns 404; a dedicated embedding model
  is required.)
- **`app/embeddings.py` changes:** (1) send `base_url` (previously missing — would
  have hit api.openai.com); (2) asymmetric **`input_type`** — documents embed as
  `passage`, the query as `query` (NVIDIA e5 requirement); (3) batch by 50; (4)
  `_cap` truncation — e5 has a hard **512-token** limit, so long chunks 400 without it.
- **New config:** `EMBEDDING_INPUT_TYPE` (default blank = symmetric/Ollama),
  `EMBEDDING_MAX_CHARS` (default 1800). Set in the override:
  `EMBEDDING_PROVIDER=openai`, `EMBEDDING_MODEL=nvidia/nv-embedqa-e5-v5`,
  `EMBEDDING_INPUT_TYPE=passage`, `EMBEDDING_MAX_CHARS=1200`,
  `EMBEDDING_SIM_THRESHOLD=0.45` (e5 query/passage cosines run ~0.45–0.6, so the
  0.55 default was too strict).
- **Demo:** backfilled embeddings for job `9c374d85…` (*Effective Indexing in
  Postgres*, 32 nodes + 4 chunks → 36 rows, dim 1024) without re-extraction. A
  keyword-free paraphrase ("make lookups faster without scanning every row")
  matched the concept **Sequential Scan** via pgvector `<=>` and produced a
  grounded, cited answer (lexical-only would have returned nothing).

## 6. Verification (2026-07-19)

- DB migrated: 24 jobs / 3 users / 24 PDFs restored; `vector` 0.8.5 enabled; `chunk_embeddings` created with FK CASCADE + indexes.
- Store integration test against the live DB: cosine KNN ordering correct, threshold filters orthogonal vectors, re-sync idempotent (no dupes), `delete_job` clears rows.
- Read-path unit tests: a non-lexical concept is surfaced only via the passed semantic index and still produces a **grounded citation**; empty candidates → honest "not covered"; legacy JSON fallback works; out-of-range indices ignored safely.
- Full suite: **45 passed**. `compileall app` clean. All services healthy; `/` returns 200.

## 7. Follow-ups (not blocking)

- **OUT-04b — ANN index + pinned dim.** Add `EMBEDDING_DIM` and an `ivfflat`/`hnsw` index once a model dim is fixed; needed for large cross-org search. Today: exact per-job search.
- **OUT-04c — strip JSON vectors. ✅ DONE (new jobs).** Embedding moved from `pipeline` to `tasks` (OUT-04e), so newly extracted/backfilled jobs no longer write `node_vectors`/`chunk_vectors` into `graph` JSON — the pgvector table is the sole store. The 24 pre-existing jobs still carry stale JSON vectors (harmless; `has_rows` routes them to the table). A one-line UPDATE can null those out if desired.
- **OUT-04d — cross-document / library chat.** The table + `org_id`/`category_id` columns make this possible; the chat UI + `chat.retrieve` do not yet expose it.
- **OUT-04e — sub-chunk embedding. ✅ DONE.** Chunks are split into ~`EMBEDDING_SUBCHUNK_CHARS`
  (default 1000) sub-passages (`embeddings.split_passages` / `embed_graph`); each is
  embedded and stored as its own row under a new `sub` column, all mapped to the
  parent `graph["chunks"]` index. `search` dedups to the best sub-passage per chunk
  via `DISTINCT ON (idx)`, so callers still get distinct parent indices. Embedding
  moved out of `pipeline` into `tasks` (single source of truth; graph JSON no longer
  carries vectors). Re-backfilled all 24 jobs: chunk vectors **~1,341 → 13,262
  sub-passages** (22,546 total). Verified a query matched content in `sub 4`/`sub 6`
  of long chunks — passages the old truncation missed entirely.
- **OUT-04f — embedding backfill for existing jobs. ✅ DONE.** `backfill_embeddings`
  Celery task + `POST /api/admin/backfill-embeddings` (admin, `all_missing` or
  `doc_ids`), following the EFT-08 `backfill_briefs` pattern. Embeds each job's
  existing graph — no re-extraction — and `sync_job`s to pgvector; idempotent,
  fail-safe per doc. **Ran over all 24 jobs → 10,625 vectors indexed.** Added
  **adaptive truncation** to `embeddings.py` (shrink-and-retry on a token-limit
  400) after dense chunks 400'd even at 1200 chars — the embed path is now robust
  to any content density. Threshold tuned to **0.40** (e5 asymmetric cosines run
  ~0.40–0.55; verbose NL queries against short node embeddings score ~0.42).
- **Tracker hygiene:** INF-02 and OUT-04 were marked Done without being wired — corrected in `feature-tracking.md`.

## 8. Changelog

| Date | Status | Note |
|---|---|---|
| 2026-07-19 | ACCEPTED | Chose pgvector over ChromaDB. Wired migration + store + write/read paths; DB image swapped to `pgvector/pgvector:pg16` with dump→restore data migration. 45 tests pass. Follow-ups in §7. |
| 2026-07-19 | ACCEPTED | Wired real embeddings (`nvidia/nv-embedqa-e5-v5`): `embeddings.py` base_url + asymmetric `input_type` + batching + token-cap; config `EMBEDDING_INPUT_TYPE`/`EMBEDDING_MAX_CHARS`; threshold tuned to 0.45. Demo backfill on 1 job proved the paraphrase→pgvector→graph-grounded-answer path end-to-end. Added follow-ups OUT-04e/f (§7). |
| 2026-07-20 | ACCEPTED | OUT-04f done: `backfill_embeddings` task + admin endpoint; backfilled all 24 jobs → 10,625 vectors. Added adaptive shrink-and-retry truncation (dense chunks 400'd at fixed cap). Threshold → 0.40. Verified pgvector surfaces correct concepts (Split Brain, Sequential Scan) for keyword-free queries. 45 tests pass. |
| 2026-07-20 | ACCEPTED | OUT-04e done: sub-chunk embedding. `split_passages`/`embed_graph`, new `sub` column + composite PK (idempotent migration), `DISTINCT ON` dedup in `search`. Embedding centralized in `tasks` (removed from `pipeline`; graph JSON no longer stores vectors). Re-backfilled all 24 jobs → 22,546 vectors (chunk sub-passages ~1,341→13,262). Verified deep-chunk (`sub 4/6`) matches the old truncation missed. 49 tests pass. |
