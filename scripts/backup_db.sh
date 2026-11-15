#!/usr/bin/env bash
set -euo pipefail
cd /opt/mirage
umask 077
BACKUP_DIR=/var/backups/mirage
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TEMP_FILE="${BACKUP_DIR}/.mirage_${STAMP}.sql.gz.tmp"
FINAL_FILE="${BACKUP_DIR}/mirage_${STAMP}.sql.gz"

if ! docker compose ps --status running --services | grep -qx db; then
  echo "PostgreSQL container is not running; backup skipped." >&2
  exit 1
fi

docker compose exec -T db pg_dump -U mirage -d mirage --no-owner --no-acl | gzip -9 > "$TEMP_FILE"
test -s "$TEMP_FILE"
mv "$TEMP_FILE" "$FINAL_FILE"
chmod 600 "$FINAL_FILE"
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'mirage_*.sql.gz' -mtime +7 -delete
printf 'Backup created: %s\n' "$FINAL_FILE"
