#!/usr/bin/env bash
# Restore a KnowledgeBook DB dump into the compose Postgres (the target/demo host).
#
# WARNING: this REPLACES the current database contents with the dump.
# The dump was made with --clean, so it drops + recreates every object. We stop
# the api/worker first (to free DB connections) and restart them after.
#
#   Usage:  ./scripts/db-restore.sh <dump.sql.gz | dump.sql>
set -euo pipefail
cd "$(dirname "$0")/.."                                  # -> extraction-service/

IN="${1:?usage: ./scripts/db-restore.sh <dump.sql[.gz]>}"
[ -f "$IN" ] || { echo "file not found: $IN" >&2; exit 1; }

echo "!! This will REPLACE the current 'kb' database with: $IN"
read -r -p "Continue? [y/N] " ans
[ "$ans" = "y" ] || [ "$ans" = "Y" ] || { echo "aborted."; exit 1; }

# Make sure Postgres is up; free connections held by the app.
docker compose up -d db >/dev/null
docker compose stop api worker >/dev/null 2>&1 || true

CAT=cat
case "$IN" in *.gz) CAT="gunzip -c";; esac

echo "Restoring…"
$CAT "$IN" | docker compose exec -T db psql -U kb -d kb -v ON_ERROR_STOP=1 -q

docker compose up -d api worker >/dev/null
echo "Done. Restored $IN and restarted api/worker."
echo "Tip: for a no-LLM demo, leave STRIPE_SECRET_KEY blank and set the same"
echo "     JWT_SECRET as the source host to keep existing logins (or just re-login)."
