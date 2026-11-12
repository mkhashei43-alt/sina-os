#!/usr/bin/env bash
# Restore from backups produced by backup.sh
#   ./restore.sh backups/db-20260101-1200.sql backups/workspace-20260101-1200.tar.gz
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
DB_FILE="${1:?usage: restore.sh <db.sql> [workspace.tar.gz]}"
WS_FILE="${2:-}"

[[ -f "$DB_FILE" ]] || { echo "✖ فایل پایگاه‌داده یافت نشد"; exit 1; }

echo "▸ توقف سرویس‌های وابسته…"
docker compose stop api worker telegram || true

echo "▸ بازگردانی پایگاه‌داده…"
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=0' < "$DB_FILE"

if [[ -n "$WS_FILE" && -f "$WS_FILE" ]]; then
  echo "▸ بازگردانی فضای‌کار…"
  docker run --rm -v sina-ai-os_sina-data:/data -v "$(realpath "$WS_FILE")":/restore.tar.gz:ro alpine \
    sh -c 'cd /data && tar xzf /restore.tar.gz'
fi

echo "▸ راه‌اندازی مجدد…"
docker compose up -d
echo "✅ بازگردانی کامل شد"
