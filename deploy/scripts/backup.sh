#!/usr/bin/env bash
# Backup Postgres + workspace volumes into ./backups/sina-YYYYmmdd-HHMM.tar.gz
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
STAMP=$(date +%Y%m%d-%H%M%S)
DEST="${1:-$ROOT/backups}"
mkdir -p "$DEST"

echo "▸ dumping database…"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' > "$DEST/db-$STAMP.sql"

echo "▸ archiving workspace volume…"
docker run --rm -v sina-ai-os_sina-data:/data:ro -v "$DEST":/backup alpine \
  tar czf "/backup/workspace-$STAMP.tar.gz" -C /data . 2>/dev/null || \
docker run --rm -v "sina_ai_data:/data:ro" -v "$DEST":/backup alpine \
  tar czf "/backup/workspace-$STAMP.tar.gz" -C /data .

echo "▸ rotating backups older than 14 days…"
find "$DEST" -name 'db-*.sql' -mtime +14 -delete
find "$DEST" -name 'workspace-*.tar.gz' -mtime +14 -delete

echo "✅ backup: $DEST/db-$STAMP.sql + workspace-$STAMP.tar.gz"
