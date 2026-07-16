-- EFT-03: Backfill — strip C0 control characters (except tab/newline/CR/FF)
-- from existing jobs.graph JSON column. Idempotent: safe to run multiple times.
--
-- Run against the kb database:
--   docker compose exec db psql -U kb -d kb -f /path/to/backfill_sanitize_graph.sql
-- Or pipe it in:
--   cat scripts/backfill_sanitize_graph.sql | docker compose exec -T db psql -U kb -d kb

UPDATE jobs
SET graph = regexp_replace(graph::text, E'[\\x00-\\x08\\x0b\\x0e-\\x1f]', '', 'g')::json
WHERE graph IS NOT NULL;
