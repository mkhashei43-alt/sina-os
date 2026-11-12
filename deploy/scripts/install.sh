#!/usr/bin/env bash
# Sina AI OS — one-shot installer for a fresh Ubuntu 22.04/24.04 server.
# Non-destructive: installs Docker only if missing, never edits existing nginx configs.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

say() { printf '\n\033[1;36m▸ %s\033[0m\n' "$*"; }
die() { printf '\033[1;31m✖ %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "این اسکریپت را با sudo اجرا کنید"

say "بررسی پیش‌نیازها"
if ! command -v docker >/dev/null 2>&1; then
  say "نصب Docker (فقط در صورت نبودن)"
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
else
  say "Docker از قبل نصب است — تغییری داده نشد"
fi
docker compose version >/dev/null || die "docker compose plugin یافت نشد"

if [[ ! -f .env ]]; then
  say "ساخت .env از نمونه"
  cp .env.example .env
  JWT=$(openssl rand -hex 32)
  DBPW=$(openssl rand -hex 16)
  FKEY=$(python3 - <<'PY' 2>/dev/null || echo ""
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
)
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${JWT}|" .env
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DBPW}|" .env
  [[ -n "${FKEY:-}" ]] && sed -i "s|^SECRETS_ENCRYPTION_KEY=.*|SECRETS_ENCRYPTION_KEY=${FKEY}|" .env
  say "⚠️  فایل .env ساخته شد. ADMIN_PASSWORD و OPENROUTER_API_KEY را ویرایش کنید سپس دوباره اجرا کنید."
  exit 0
fi

say "ساخت و راه‌اندازی سرویس‌ها"
docker compose pull --quiet db redis || true
docker compose build
docker compose up -d

say "اجرای مهاجرت‌های پایگاه‌داده"
docker compose exec -T api alembic upgrade head

say "انتظار برای سلامت سرویس‌ها"
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -fsS http://127.0.0.1:8000/health && echo

cat <<EOF

✅ Sina AI OS بالا آمد.
   داشبورد:  http://127.0.0.1:3000   (یا از طریق nginx با دامنه شما)
   API Docs: http://127.0.0.1:8000/api/docs

مرحله بعد:
   1) .env را ویرایش کنید (OPENROUTER_API_KEY، ADMIN_PASSWORD، TELEGRAM_*)
   2) docker compose up -d --force-recreate api worker telegram
   3) برای پروکسی عمومی: docker compose --profile proxy up -d nginx
      و دامنه/گواهی را در deploy/nginx/ تنظیم کنید.
EOF
