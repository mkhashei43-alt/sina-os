# استقرار و بهره‌برداری — Sina AI OS

## ۱. پیش‌نیاز سرور

* Ubuntu 22.04/24.04، حداقل ۲ vCPU / ۲ گیگ رم / ۲۰ گیگ دیسک (برای Playwright و build فرانت ۴ گیگ توصیه می‌شود)
* دسترسی root یا sudo
* دامنه (اختیاری برای TLS)

## ۲. نصب

```bash
git clone <repo> sina-ai-os && cd sina-ai-os
sudo ./deploy/scripts/install.sh     # بار اول: نصب Docker + ساخت .env
nano .env                            # OPENROUTER_API_KEY, ADMIN_PASSWORD, JWT_SECRET, TELEGRAM_*
sudo ./deploy/scripts/install.sh     # build + up + alembic upgrade head
```

سلامت:

```bash
sudo ./deploy/scripts/healthcheck.sh
curl -s localhost:8000/api/health
```

## ۳. سرویس‌ها

| سرویس | نقش | پورت میزبان |
|---|---|---|
| api | FastAPI + SSE | 127.0.0.1:8000 |
| worker | Agent loop + scheduler | — |
| frontend | Next.js | 127.0.0.1:3000 |
| telegram | ربات تلگرام | — |
| db / redis | داده و رویداد | داخلی |
| nginx (profile) | پروکسی/TLS | 80/443 |

## ۴. دستورهای روزمره

```bash
docker compose ps
docker compose logs -f api worker
docker compose restart worker
docker compose up -d --build api worker        # پس از تغییر کد
docker compose exec api alembic upgrade head   # مهاجرت
docker compose exec api python -m app.worker   # اجرای دستی ورکر (دیباگ)
```

## ۵. بکاپ

```bash
# روزانه با cron:
0 3 * * * cd /opt/sina-ai-os && ./deploy/scripts/backup.sh /var/backups/sina
```

بازگردانی:

```bash
./deploy/scripts/restore.sh /var/backups/sina/db-XXXX.sql /var/backups/sina/workspace-XXXX.tar.gz
```

## ۶. nginx و دامنه

`deploy/nginx/sina.conf` را با دامنه و مسیر گواهی خود ویرایش کنید و:

```bash
docker compose --profile proxy up -d nginx
```

اگر nginx میزبان دارید، به‌جای این کانتینر، دو `location` زیر را به کانفیگ موجود اضافه کنید (بدون بازنویسی):

```nginx
location /api/ { proxy_pass http://127.0.0.1:8000; proxy_buffering off; proxy_read_timeout 3600s; proxy_set_header Host $host; }
location /     { proxy_pass http://127.0.0.1:3000; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; }
```

## ۷. مدل‌ها و اعتبار OpenRouter

**وضعیت این استقرار:** دامنهٔ `agent.rajastore.ir` → `91.107.254.187`؛ کلید OpenRouter از نوع **free-tier** با `total_credits: 0`.
بنابراین پیش‌فرض‌ها روی مدل‌های رایگان تنظیم شده‌اند (۵۰ درخواست رایگان در روز):

```env
DEFAULT_MODEL=google/gemma-4-31b-it:free
CODING_MODEL=google/gemma-4-31b-it:free
REASONING_MODEL=nvidia/nemotron-3.5-lightning:free
MODEL_FALLBACKS=nvidia/nemotron-3.5-lightning:free,google/gemma-4-31b-it:free,liquid/lfm-3-1.7b:free
LLM_MAX_TOKENS=2048
```

**برای استفاده از مدل‌های قوی‌تر:** در <https://openrouter.ai/settings/credits> حساب را شارژ کنید، سپس:

```env
DEFAULT_MODEL=openai/gpt-4o-mini
CODING_MODEL=anthropic/claude-sonnet-4.5
REASONING_MODEL=openai/o3-mini
```
و `docker compose up -d --force-recreate api worker`.

> ⚠️ خطای `402` یعنی موجودی کافی نیست؛ `LLM_MAX_TOKENS` را کم کنید یا مدل `:free` بگذارید.
> خطای `429` روی مدل‌های رایگان طبیعی است — زنجیرهٔ fallback خودکار مدل بعدی را امتحان می‌کند.

سپس `docker compose up -d --force-recreate api worker`.

## ۸. فعال‌سازی Playwright (مرورگر واقعی)

```bash
docker compose exec -u root worker bash -lc "pip install playwright && playwright install --with-deps chromium"
docker compose restart worker
```

بدون این کار، ابزار `browser` پیام روشن «نصب نیست» می‌دهد و `web_fetch` جایگزین است.

## ۹. عیب‌یابی

| نشانه | بررسی |
|---|---|
| کارها در «در صف» می‌مانند | `docker compose logs worker`؛ سلامت DB؛ در dev مطمئن شوید worker اجرا می‌شود |
| خطای `asyncpg` | `POSTGRES_*` و سلامت db |
| استریم قطع می‌شود | در پروکسی `proxy_buffering off` |
| مدل پاسخ نمی‌دهد | `OPENROUTER_API_KEY`، لاگ `sina.openrouter`، سهمیه |
| «در انتظار تأیید» ماند | تأیید از داشبورد/تلگرام یا کاهش `REQUIRE_APPROVAL_LEVELS` |

## ۱۰. ارتقا

```bash
git pull
docker compose build api worker frontend telegram
docker compose up -d
docker compose exec api alembic upgrade head
```
