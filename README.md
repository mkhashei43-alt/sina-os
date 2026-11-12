<div align="center">

# ⚡ Sina OS — عامل هوشمند خودمختار (نسخهٔ متن‌باز)

**به فارسی بگویید چه می‌خواهید؛ خودش انجام می‌دهد.**
روی کامپیوتر خودتان اجرا می‌شود، با **توکن‌های خودتان**، بدون وابستگی به هیچ سرویس ابریِ اجباری.

[![CI](https://github.com/mkhashei43-alt/sina-os/actions/workflows/ci.yml/badge.svg)](https://github.com/mkhashei43-alt/sina-os/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#-نصب-در-یک-دستور)

</div>

---

## 🚀 نصب در یک دستور

```bash
git clone https://github.com/mkhashei43-alt/sina-os && cd sina-os && ./sina.sh
```
```powershell
git clone https://github.com/mkhashei43-alt/sina-os; cd sina-os; .\sina.cmd   # ویندوز
```

روی macOS می‌توانید روی `sina.command` دابل‌کلیک کنید.
لانچر خودش محیط مجازی می‌سازد، وابستگی‌ها را نصب می‌کند، رمز مدیر را می‌سازد و
مرورگر را روی <http://127.0.0.1:8765> باز می‌کند. **نه Node لازم است، نه داکر، نه دیتابیس.**

> جزئیات بیشتر (و حالت‌های جایگزین): [docs/QUICKSTART.md](docs/QUICKSTART.md)

## 🧠 چه کاری می‌کند؟

| | مثال دستور به فارسی |
|---|---|
| 💻 **کد و اجرا** | «یک اسکریپت بساز که CSV را تحلیل کند، اجرا کن و نمودار بده» |
| 🖥️ **سرور (SSH)** | «روی سرورم وضعیت nginx را چک کن و لاگ خطاها را بیاور» |
| ☁️ **Cloudflare** | «ساب‌دامین `app` را به IP سرورم وصل کن» |
| 🐙 **GitHub** | «ریپازیتوری جدید بساز، کد را کامیت کن و PR بزن» |
| ✈️ **تلگرام/اسلک/دیسکورد** | «گزارش امروز را به کانال تیم بفرست» |
| 🔎 **جست‌وجو** | «قیمت رقبا را جمع کن و مقایسه بده» |
| 🧾 **هر API دیگری** | «با توکن Notion که دادم، تسک‌های امروز را لیست کن» |

**۷۳ سرویس آماده** شامل OpenAI، Anthropic، Gemini، Groq، DeepSeek، xAI، Mistral، Perplexity،
GitHub، GitLab، Cloudflare، Vercel، Netlify، Supabase، DigitalOcean، Hetzner، Notion، Airtable،
Linear، Jira، Asana، Slack، Discord، Stripe، Shopify، WooCommerce، زرین‌پال، آیدی‌پی،
Resend، SendGrid، Mailgun، Twilio، کاوه‌نگار، Brave، Tavily، SerpAPI، YouTube، X، Reddit و…
→ فهرست کامل: [docs/PROVIDERS.md](docs/PROVIDERS.md)

## 🔑 توکن‌ها

- **کلید خودتان** را در تب «اتصال‌ها» وارد می‌کنید (یا `python sina.py token add openai`).
- با **Fernet رمزنگاری** و در دیتابیس محلی ذخیره می‌شود؛ کلید رمزنگاری در همان دستگاه است.
- هرگز به مدل زبانی فرستاده نمی‌شود، در لاگ چاپ نمی‌شود و در پاسخ API ماسک است (`••••••`).
- پیشنهاد: یک کلید **OpenRouter** بگیرید (`openrouter.ai/keys`) — با یک کلید به صدها مدل
  دسترسی دارید و مدل‌های `:free` بدون هزینه کار می‌کنند.

## 🛡️ کنترل شما

| ریسک | رفتار |
|---|---|
| خواندن فایل، محاسبه، جست‌وجو، ساخت فایل در فضای‌کار | خودکار |
| دستور تغییردهنده روی **سرور**، DNS، کامیت، ارسال پیام/ایمیل/پیامک | **توقف و گرفتن تأیید شما** |
| دستورهای خطرناک (`mkfs`, `dd`, `sudo`, `systemctl`, …) | مسدود یا نیازمند تأیید مدیریتی |
| اجرای کد | داخل فضای‌کار جدا با زمان‌بند و سقف خروجی |

## 🧩 معماری

```
┌──────────────┐   REST/SSE   ┌──────────────────────────────┐
│  کنسول وب    │ ───────────► │  FastAPI (backend/app)       │
│ (بدون Node)  │              │  ├─ Agent runner (LangGraph) │
└──────────────┘              │  ├─ Tools: files, terminal,  │
┌──────────────┐              │  │   python, browser, ssh,   │
│ داشبورد Next │ ───────────► │  │   github, cloudflare,     │
│  (اختیاری)   │              │  │   http_api, llm_ask, …    │
└──────────────┘              │  ├─ Provider: OpenRouter +   │
                              │  │   کلیدهای خودِ کاربر      │
┌──────────────┐              │  └─ SQLite / Postgres        │
│  CLI (sina)  │ ───────────► │                              │
└──────────────┘              └──────────────────────────────┘
```

- **حافظهٔ برداری** (pgvector در Postgres، جست‌وجوی متنی در SQLite)
- **بازیابی پس از کرش**: وضعیت هر کار بعد از هر مرحله ذخیره می‌شود
- **استریم زنده** با SSE
- **چند‌کاربره/فروش** به‌صورت اختیاری (`SIGNUP_ENABLED=true`) — [docs/SAAS.md](docs/SAAS.md)

## 🐳 داکر (اختیاری)

```bash
docker compose -f docker-compose.oss.yml up -d     # → http://localhost:8765
```

## ☁️ اجرا روی GitHub

- **Codespaces**: از صفحهٔ مخزن → `Code ▾ → Codespaces → Create codespace` — خودکار آماده می‌شود.
- **Actions**: هر push تست‌ها را اجرا می‌کند (`.github/workflows/ci.yml`).
- **انتشار ایمیج**: با زدن تگ `v1.0.0` ایمیج روی `ghcr.io` منتشر می‌شود.

## 🧪 تست‌ها

```bash
cd backend
pip install -r requirements.txt pytest pytest-asyncio httpx
python -m pytest -q          # ۶۱ تست: API، ابزارها، امنیت، عامل E2E، بازیابی، SaaS
```

## 📚 مستندات

| فایل | موضوع |
|---|---|
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | نصب و اجرا در هر سیستم‌عامل |
| [docs/PROVIDERS.md](docs/PROVIDERS.md) | ۷۳ سرویس و نحوهٔ گرفتن توکن |
| [docs/API.md](docs/API.md) | مرجع API |
| [docs/SECURITY.md](docs/SECURITY.md) | مدل تهدید و کنترل‌ها |
| [docs/SAAS.md](docs/SAAS.md) | حالت چند‌مستأجری/فروش |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | استقرار با داکر روی سرور |
| [CONTRIBUTING.md](CONTRIBUTING.md) | مشارکت در توسعه |

## 📄 مجوز

MIT — استفادهٔ شخصی و تجاری آزاد است. [LICENSE](LICENSE)

<div align="center"><sub>ساخته‌شده برای فارسی‌زبان‌ها · RTL-first · بدون قفلِ فروشنده</sub></div>
