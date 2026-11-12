#!/usr/bin/env bash
# Verifies the whole stack: containers, API, DB, Redis, provider, disk.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; cd "$ROOT"
fail=0
chk() { printf '%-42s' "$1"; shift; if "$@" >/dev/null 2>&1; then echo "✓"; else echo "✗"; fail=1; fi; }

chk "docker daemon" docker info
chk "api /health" curl -fsS http://127.0.0.1:8000/health
chk "database" docker compose exec -T db pg_isready -U "${POSTGRES_USER:-sina}" -d "${POSTGRES_DB:-sina}"
chk "redis" docker compose exec -T redis redis-cli ping
chk "frontend" curl -fsS http://127.0.0.1:3000/login
chk "disk < 90%" bash -c '[ "$(df --output=pcent / | tail -1 | tr -dc 0-9)" -lt 90 ]'

echo; docker compose ps
exit $fail
