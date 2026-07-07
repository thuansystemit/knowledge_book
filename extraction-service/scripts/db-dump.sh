#!/usr/bin/env bash
# Dump the entire KnowledgeBook Postgres DB to a gzip'd SQL file.
#
# Postgres is the single source of truth: this one file contains users, plans,
# jobs + their full graph JSON (nodes/edges/brief/chunks/embeddings/chapter
# guide), the raw uploaded PDFs, chat history, categories+ACL, and activation
# data. Redis (cache/broker) is transient and NOT needed.
#
#   Usage:  ./scripts/db-dump.sh [output-file.sql.gz]
#   e.g.    ./scripts/db-dump.sh                       # timestamped default name
#           ./scripts/db-dump.sh demo.sql.gz
set -euo pipefail
cd "$(dirname "$0")/.."                                  # -> extraction-service/

OUT="${1:-kb-dump-$(date +%Y%m%d-%H%M%S).sql.gz}"

echo "Dumping KnowledgeBook DB (users · jobs+graphs · PDFs · chat · categories)…"
docker compose exec -T db pg_dump -U kb -d kb \
  --no-owner --no-privileges --clean --if-exists \
  | gzip > "$OUT"

echo "Wrote $OUT ($(du -h "$OUT" | cut -f1))"
echo "Copy it to the other host and run:  ./scripts/db-restore.sh $OUT"
