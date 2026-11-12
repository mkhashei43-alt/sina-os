# گزارش تست — Sina AI OS

**آخرین اجرا:** 2026-11-12 · **محیط:** Debian 13 / Python 3.13 / Node 20 / SQLite (dev)

## ۱. خلاصهٔ تست‌های خودکار

```
$ cd backend && .venv/bin/python -m pytest -q
53 passed in 12.10s
```
| مجموعه | تعداد | نتیجه |
|---|---|---|
| test_security.py | 20 | ✅ |
| test_tools.py | 10 | ✅ |
| test_api.py | 13 | ✅ |
| test_agent_e2e.py | 2 | ✅ |
| test_recovery.py | 2 | ✅ |

```
$ cd frontend && npm run build
✓ Compiled successfully — 18 route (فارسی/RTL)
```

## ۲. تست زندهٔ OpenRouter (با کلید واقعی) — ✅

| بررسی | نتیجه |
|---|---|
| احراز هویت کلید | ✅ `is_free_tier: true`, `usage: 0` |
| کاتالوگ مدل‌ها | ✅ ۴۳۲ مدل دریافت شد |
| مدل پولی با اعتبار صفر | ⚠️ خطای `402` (۱۶۳۸۴ توکن درخواستی > ۹۴۳ قابل تأمین) |
| اصلاح | `LLM_MAX_TOKENS=2048` + پیش‌فرض `:free` + زنجیرهٔ fallback |
| tool-calling واقعی | ✅ فراخوانی `files` با آرگومان صحیح تولید شد |
| حلقهٔ کامل ابزار → پاسخ نهایی | ✅ «The file hello.txt has been created…» |
| استریم | ✅ (با پشتیبانی `delta.reasoning`) |
| fallback خودکار روی 429 | ✅ `gemma` → `nemotron` و ادامهٔ کار |

### تست ۱ — ساخت و اجرای کد (از طریق پروکسی داشبورد)
```
دستور: Create a Python file hello.py that prints 'Sina OK', run it, and report the output.
status: completed
tools : files(ok, "نوشته شد: hello.py") → python_exec(ok, exit 0, "Sina OK")
usage : 9031 in / 2794 out
نتیجه : گزارش فارسی شامل مسیر فایل، خروجی اجرا و کد خروجی
فایل  : hello.py در فضای‌کار موجود است
```

### تست ۲ — خوداصلاحی خطا
```
دستور: Write greet.py … run it
tools : files(ok) → python_exec(ERROR) → python_exec(ok)
```
مدل خطای اجرای اول را دید، اصلاح کرد و در تلاش دوم موفق شد — **حلقهٔ verify→repair در عمل کار می‌کند.**

### تست ۳ — جست‌وجوی وب واقعی
```
tools : web_search(ok) → ۲ نتیجه از python.org
```

### تست ۴ — هزینهٔ مدل‌های رایگان
`cost_usd = 0.0` برای همهٔ کارهای `:free` (پیش از اصلاح، هزینهٔ تخمینی نادرست ثبت می‌شد).

## ۳. سناریوی اجباری (MockProvider، برای CI بدون کلید)

دستور: «یک برنامه ساده پایتون بساز، فایل‌ها را بنویس، اجرا کن، تست‌ها را اجرا کن، خطاها را اصلاح کن و فایل‌های نهایی را ارائه بده»

راستی‌آزمایی‌ها در `test_e2e_python_project`:
1. فضای‌کار ساخته شد 2. فایل‌ها روی دیسک‌اند 3. کد واقعاً اجرا می‌شود (`calculator ready: 5`)
4. `pytest -q tests/` واقعاً exit 0 5. خروجی ابزارها در DB ذخیره شد 6. گزارش نهایی 7. فایل‌ها از API قابل دریافت

## ۴. تست بازیابی پس از مرگ ورکر

کار در وضعیت `running` با heartbeat ۳۰ دقیقه‌قبل → `recover_stale_tasks()` → `queued` → ادامه و تکمیل از وضعیت ذخیره‌شده. ✅

## ۵. تست‌های امنیتی

| تست | نتیجه |
|---|---|
| `sudo rm -rf /`, `mkfs`, `shutdown`, `iptables -F`, `curl\|sh`, fork-bomb → blocked | ✅ |
| `rm -rf ./build`, `git push`, `ssh`, `kill` → نیازمند تأیید | ✅ |
| `systemctl`, `apt install`, `pip install evil-pkg` → admin | ✅ |
| `pip install requests` → safe (allow-list) | ✅ |
| `../../etc/passwd`, مسیر مطلق, symlink escape → رد | ✅ |
| عدم افشای `ghp_...` در پاسخ API یکپارچه‌سازی | ✅ |
| redaction کلیدها در خروجی ابزار | ✅ |
| رمزنگاری Fernet اسرار در DB | ✅ |
| توکن غایب/نامعتبر → 401 | ✅ |

## ۶. آنچه هنوز تست نشده (شفاف)

* **Docker Compose**: daemon داکر در محیط ساخت موجود نیست → فقط YAML اعتبارسنجی شد؛ اجرای واقعی روی سرور شما.
* **تلگرام**: بدون توکن واقعی؛ منطق با همان API مشترک تست شده است.
* **Playwright / SSH / GitHub / Cloudflare**: نیازمند نصب مرورگر یا اعتبارنامهٔ واقعی.
* **PostgreSQL/pgvector**: مسیر dev با SQLite؛ مهاجرت Postgres روی سرور اجرا می‌شود (`alembic upgrade head`).


## نسخهٔ فروش (SaaS) — تست‌های افزوده‌شده

فایل: `backend/tests/test_saas.py` (۸ تست)

| تست | چه چیزی را تضمین می‌کند |
|---|---|
| `test_public_catalog` | پلن‌ها با قیمت و سهمیه از API عمومی خوانده می‌شوند |
| `test_signup_creates_tenant_and_isolated_account` | ثبت‌نام → مستأجر trial/pro؛ دادهٔ سایر مشتری‌ها دیده نمی‌شود |
| `test_signup_duplicate_and_weak_password` | ایمیل تکراری 409؛ رمز ضعیف 422 |
| `test_plan_upgrade_request_flow` | مسیر درخواست ارتقا پاسخ درست می‌دهد |
| `test_tenant_quota_enforced` | عبور از سهمیهٔ روزانه → 429 با پیام فارسی |
| `test_credentials_are_private_per_tenant` | کلیدهای یک مستأجر برای دیگری نامرئی است و در پاسخ API لو نمی‌رود |
| `test_suspended_tenant_is_blocked` | حساب تعلیق‌شده نمی‌تواند کار بسازد |
| `test_plans_have_consistent_limits` | سازگاری قیمت/سهمیه بین پلن‌ها |

**نتیجهٔ کل تست‌ها: `61 passed`** (۵۳ تست قبلی + ۸ تست جدید).
