# Data migration — move extracted documents to another server

KnowledgeBook keeps **Postgres as the single source of truth** — users, plans,
jobs and their **full graph JSON** (concepts, edges, brief, persisted chunks,
embeddings, chapter guide, captions), the **raw uploaded PDFs** (stored in the DB,
not on disk/S3), chat history, categories + ACLs, and activation data. So one
Postgres dump captures the *entire* extracted state. Redis (broker/cache) is
transient and does **not** need to move.

Typical flow: **extract on server A → dump → restore on server B (a demo host)**.

## Two commands

On the source host (A):
```bash
cd extraction-service
./scripts/db-dump.sh                 # writes kb-dump-<timestamp>.sql.gz (incl. PDFs)
```

Copy the file to the target host (B), then:
```bash
cd extraction-service
docker compose up -d                 # start the stack (db, redis, api, worker, frontend)
./scripts/db-restore.sh kb-dump-<timestamp>.sql.gz
```
`db-restore.sh` stops api/worker, replaces the DB (the dump is `--clean`), and
restarts them. That's it — every document, graph, PDF, and chat is now on B.

## The no-LLM demo win

Because **retrieval-mode chat is zero-LLM** and the graph + chunks live in the
dump, the demo host needs **no LLM and no API keys** to show already-extracted
documents: browse the knowledge graph, Brief, Chapter Guide, **grounded chat**,
and the source-PDF viewer — nothing calls out. Just `db + redis + api + frontend`.

(New extractions or LLM-mode chat on B would still need `LLM_PROVIDER` / keys.)

## Gotchas / checklist for host B (`extraction-service/.env`)

| Setting | Why |
|---|---|
| `JWT_SECRET` | Set the **same value** as host A to keep existing logins valid; otherwise users just re-login (password hashes are in the dump). |
| `STRIPE_SECRET_KEY` | Leave **blank** for a demo — billing is config-gated off, and copied `stripe_customer_id`s only mean anything against the original Stripe account. |
| `CHAT_MODE=retrieval` | Default; gives full zero-LLM chat with no external calls. Only set `llm` (+ provider keys) if you want AI-generated answers on B. |
| Redis chunk cache | Cold on B — irrelevant unless you **re-process** a document (you won't for a demo). |
| `DATABASE_URL` | Keep the compose default so the app points at the restored DB. |

## Alternatives

- **Whole-DB, no scripts:** `docker compose exec -T db pg_dump -U kb -d kb | gzip > x.sql.gz` and restore with `psql`. The scripts above just wrap this safely.
- **Per-document outputs only:** the in-app **Export** (OUT-06) downloads one document's Brief/Concept-Map/Chapter-Guide as Markdown/JSON — good for sharing results, but it does not include the PDF, users, or chat.
