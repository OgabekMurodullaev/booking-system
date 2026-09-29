#!/bin/sh
# Shared entrypoint for the web/worker/beat services in docker-compose.prod.yml (mounted in,
# not baked into the image — see docs/DEPLOY.md for why). Waits for Postgres, applies
# migrations, collects static files, then hands off to the service's real command.
set -eu

echo "Waiting for the database..."
attempt=0
max_attempts=30
until python -c "
import os
import psycopg
psycopg.connect(os.environ['DATABASE_URL']).close()
" 2>/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge "$max_attempts" ]; then
    echo "Database never became reachable after ${max_attempts} attempts." >&2
    exit 1
  fi
  sleep 1
done
echo "Database is up."

# Safe to run from all three services: both commands are idempotent no-ops when there's
# nothing new to apply/collect.
python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
