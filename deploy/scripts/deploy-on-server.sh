#!/usr/bin/env bash
# ============================================================================
# Sina AI OS — deploy ON THE SERVER (run as root, from the project directory)
#
#   tar xzf sina-ai-os.tar.gz -C /opt && cd /opt/sina-ai-os
#   sudo ./deploy/scripts/deploy-on-server.sh
#
# Non-destructive by design:
#   * does NOT stop/remove existing containers
#   * does NOT touch existing nginx configs (adds one new site file)
#   * uses free host ports (18000/13000) because 8000 is already taken
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
DOMAIN="${DOMAIN:-agent.rajastore.ir}"
say()  { printf '\n\033[1;36m▸ %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✖ %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "با sudo اجرا کنید"
[[ -f .env ]] || die "فایل .env یافت نشد (کنار docker-compose.yml)"
# safe env reader: values may contain spaces / unicode — never `source` the file
env_get() { grep -E "^$1=" .env | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }
API_PORT="$(env_get SINA_API_PORT)";   API_PORT="${API_PORT:-18000}"
WEB_PORT="$(env_get SINA_WEB_PORT)";   WEB_PORT="${WEB_PORT:-13000}"
ADMIN_EMAIL_V="$(env_get ADMIN_EMAIL)"
TELEGRAM_BOT_TOKEN="$(env_get TELEGRAM_BOT_TOKEN)"
POSTGRES_USER_V="$(env_get POSTGRES_USER)";   POSTGRES_USER_V="${POSTGRES_USER_V:-sina}"
POSTGRES_DB_V="$(env_get POSTGRES_DB)";       POSTGRES_DB_V="${POSTGRES_DB_V:-sina}"
ok "پورت‌ها: api=${API_PORT} web=${WEB_PORT}"

say "۱. بررسی پیش‌نیازها"
command -v docker >/dev/null || die "Docker نصب نیست"
docker compose version >/dev/null || die "docker compose plugin نصب نیست"
ok "docker $(docker --version | cut -d' ' -f3 | tr -d ,) / compose $(docker compose version --short 2>/dev/null || echo ok)"

say "۲. بررسی منابع و تداخل پورت"
MEM_MB=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
SWAP_MB=$(awk '/SwapTotal/{print int($2/1024)}' /proc/meminfo)
if [[ $MEM_MB -lt 1800 && $SWAP_MB -lt 512 ]]; then
  warn "رم ${MEM_MB}MB و swap ${SWAP_MB}MB — build ممکن است شکست بخورد؛ افزودن swap توصیه می‌شود:"
  warn "  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile"
fi
DISK_FREE_GB=$(df --output=avail -BG / | tail -1 | tr -dc 0-9)
[[ ${DISK_FREE_GB:-0} -lt 6 ]] && warn "فضای دیسک کم است (${DISK_FREE_GB}GB) — حداقل ۶ گیگ لازم است"
for port in "$API_PORT" "$WEB_PORT"; do
  if ss -tln | awk '{print $4}' | grep -q ":${port}$"; then
    die "پورت $port اشغال است. در .env مقدار SINA_API_PORT/SINA_WEB_PORT را عوض کنید."
  fi
  ok "پورت $port آزاد است"
done
PORT_8000_OWNER="$(ss -tlnp 2>/dev/null | awk '/:8000 /{print $NF}' | head -1 || true)"
[[ -n "$PORT_8000_OWNER" ]] && warn "پورت 8000 توسط سرویس دیگری در استفاده است → ما از $API_PORT استفاده می‌کنیم"

say "۳. ساخت و راه‌اندازی سرویس‌های سینا (فقط سرویس‌های همین پروژه)"
docker compose pull --quiet db redis 2>/dev/null || true
SERVICES="api worker frontend"
[[ -n "${TELEGRAM_BOT_TOKEN:-}" ]] && SERVICES="$SERVICES telegram"
echo "  سرویس‌ها: $SERVICES$([[ -z "${TELEGRAM_BOT_TOKEN:-}" ]] && echo '  (تلگرام: توکن تنظیم نشده → رد شد)')"
docker compose build $SERVICES
docker compose up -d db redis
echo "  در انتظار پایگاه‌داده…"
for i in $(seq 1 40); do
  docker compose exec -T db pg_isready -U "${POSTGRES_USER_V}" -d "${POSTGRES_DB_V}" >/dev/null 2>&1 && break
  sleep 2
done
docker compose ps

say "۴. اجرای مهاجرت پایگاه‌داده (قبل از استارت اپلیکیشن)"
# first deploy on a pre-populated DB? stamp the initial revision, then upgrade
REV_INITIAL=$(ls backend/migrations/versions/ | grep -m1 "_initial_schema" | sed -E "s/^([a-z0-9]+)_.*/\1/")
TABLES=$(docker compose exec -T db psql -U "${POSTGRES_USER_V}" -d "${POSTGRES_DB_V}" -tAc \
  "select count(*) from information_schema.tables where table_schema='public';" | tr -d '[:space:]')
if [[ "${TABLES:-0}" -ge 16 ]] && ! docker compose run --rm --no-deps api alembic current 2>/dev/null | grep -q "[a-z0-9]\{12\}"; then
  warn "پایگاه‌داده از قبل جدول دارد → stamp روی نسخهٔ اولیه"
  docker compose run --rm --no-deps api alembic stamp "$REV_INITIAL"
fi
docker compose run --rm --no-deps api alembic upgrade head && ok "مهاجرت انجام شد"

say "۵. استارت اپلیکیشن"
docker compose up -d $SERVICES
ok "سرویس‌ها بالا آمدند"

say "۶. انتظار برای سلامت سرویس‌ها"
healthy=0
for i in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then healthy=1; break; fi
  sleep 2
done
[[ $healthy -eq 1 ]] || { docker compose logs --tail=60 api; die "API سالم نشد"; }
ok "API: $(curl -fsS http://127.0.0.1:${API_PORT}/health)"
ok "WEB: HTTP $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:${WEB_PORT}/login)"

say "۷. افزودن server block به nginx موجود (بدون تغییر کانفیگ‌های دیگر)"
CERT_DIR=""
for d in /etc/letsencrypt/live/*/; do
  [[ -f "$d/fullchain.pem" ]] || continue
  if openssl x509 -in "$d/fullchain.pem" -noout -text 2>/dev/null | grep -qE "DNS:\*\.rajastore\.ir|DNS:${DOMAIN}"; then CERT_DIR="$d"; break; fi
done
[[ -n "$CERT_DIR" ]] || die "گواهی TLS مناسب برای $DOMAIN پیدا نشد"
ok "گواهی: ${CERT_DIR}fullchain.pem"

SITE=/etc/nginx/sites-available/${DOMAIN}.conf
BACKUP_DIR=/root/sina-backups; mkdir -p "$BACKUP_DIR"
tar czf "$BACKUP_DIR/nginx-full-$(date +%Y%m%d-%H%M%S).tar.gz" -C /etc nginx 2>/dev/null && ok "بکاپ کامل /etc/nginx گرفته شد"
if [[ -f "$SITE" ]]; then cp "$SITE" "$BACKUP_DIR/${DOMAIN}.conf.$(date +%s).bak"; warn "فایل قبلی بکاپ گرفته شد"; fi
sed -e "s|/etc/letsencrypt/live/rajastore.ir/fullchain.pem|${CERT_DIR}fullchain.pem|" \
    -e "s|/etc/letsencrypt/live/rajastore.ir/privkey.pem|${CERT_DIR}privkey.pem|" \
    -e "s|127.0.0.1:18000|127.0.0.1:${API_PORT}|" \
    -e "s|127.0.0.1:13000|127.0.0.1:${WEB_PORT}|" \
    "$ROOT/deploy/nginx/host-agent.rajastore.ir.conf" > "$SITE"
ln -sf "$SITE" /etc/nginx/sites-enabled/${DOMAIN}.conf
nginx -t || { rm -f /etc/nginx/sites-enabled/${DOMAIN}.conf; die "کانفیگ nginx نامعتبر است — برگردانده شد"; }
systemctl reload nginx
ok "nginx reload شد (سایر سایت‌ها دست‌نخورده)"

say "۸. تست نهایی از بیرون"
sleep 2
for url in "https://${DOMAIN}/health" "https://${DOMAIN}/login" "https://${DOMAIN}/api/health"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$url" || echo 000)
  [[ "$code" == "200" ]] && ok "$url → $code" || warn "$url → $code"
done

cat <<EOF

✅ استقرار کامل شد
   داشبورد:  https://${DOMAIN}
   API Docs: https://${DOMAIN}/api/docs
   ورود با:  ${ADMIN_EMAIL_V} / (ADMIN_PASSWORD در .env)

بکاپ کانفیگ‌های قبلی nginx: ${BACKUP_DIR}
EOF
