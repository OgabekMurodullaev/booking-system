#!/bin/sh
# Daily Postgres backup: gzip a pg_dump, keep 7 days. Run from the repo root on the VPS (see
# docs/DEPLOY.md for the cron line). Reads Postgres creds from deploy/.env so it never
# hardcodes a password.
set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/deploy/docker-compose.prod.yml"
ENV_FILE="$REPO_ROOT/deploy/.env"
BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups}"
RETENTION_DAYS=7

# shellcheck disable=SC1090
[ -f "$ENV_FILE" ] && . "$ENV_FILE"
POSTGRES_DB="${POSTGRES_DB:-booking}"
POSTGRES_USER="${POSTGRES_USER:-booking}"

mkdir -p "$BACKUP_DIR"
timestamp=$(date +%Y%m%d-%H%M%S)
out_file="$BACKUP_DIR/booking-${timestamp}.sql.gz"

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$out_file"

echo "Backup written to $out_file"

find "$BACKUP_DIR" -name 'booking-*.sql.gz' -mtime "+${RETENTION_DAYS}" -delete
