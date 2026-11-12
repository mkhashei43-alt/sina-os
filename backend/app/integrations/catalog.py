"""کتالوگ اتصال‌ها — توکن/کلید خودِ کاربر برای سرویس‌های بزرگ و معروف.

هر آیتم مشخص می‌کند：
  name      نام نمایشی
  category  دسته (ai | search | messaging | email | dev | productivity | social | commerce | infra | data)
  fields    فیلدهایی که کاربر پر می‌کند (نام، کلید، دامنه...)
  base      آدرس پایهٔ API
  auth      نحوهٔ احراز هویت: bearer | header:<NAME> | query:<name> | basic | key_header:<NAME>
  header    (اختیاری) نام هدر احراز در صورت متفاوت بودن
  docs      لینک مستندات گرفتن توکن
  actions   عملیات آمادهٔ پرکاربرد (متد + مسیر + توضیح)

توکن‌ها رمزنگاری‌شده در دیتابیس محلی ذخیره می‌شوند و هرگز به مدل زبانی فرستاده نمی‌شوند.
"""
from __future__ import annotations

from typing import Any

CATALOG: dict[str, dict[str, Any]] = {}


def P(key: str, name: str, category: str, base: str, fields: list[str], docs: str,
      auth: str = "bearer", header: str = "", actions: dict | None = None,
      note: str = "") -> None:
    CATALOG[key] = {
        "key": key, "name": name, "category": category, "base": base,
        "fields": fields, "docs": docs, "auth": auth, "header": header,
        "actions": actions or {}, "note": note,
    }


# ------------------------------------------------------------------ هوش مصنوعی
P("openai", "OpenAI", "ai", "https://api.openai.com/v1", ["api_key"],
  "https://platform.openai.com/api-keys", auth="bearer",
  actions={"chat": {"method": "POST", "path": "/chat/completions", "desc": "گفتگو با مدل"},
           "models": {"method": "GET", "path": "/models", "desc": "فهرست مدل‌ها"},
           "images": {"method": "POST", "path": "/images/generations", "desc": "تولید تصویر"},
           "embeddings": {"method": "POST", "path": "/embeddings", "desc": "بردار متن"}})
P("anthropic", "Anthropic (Claude)", "ai", "https://api.anthropic.com/v1", ["api_key"],
  "https://console.anthropic.com/settings/keys", auth="header:x-api-key",
  actions={"messages": {"method": "POST", "path": "/messages", "desc": "پیام به Claude"},
           "models": {"method": "GET", "path": "/models", "desc": "فهرست مدل‌ها"}})
P("google_gemini", "Google Gemini", "ai", "https://generativelanguage.googleapis.com/v1beta",
  ["api_key"], "https://aistudio.google.com/apikey", auth="query:key",
  actions={"generate": {"method": "POST", "path": "/models/gemini-2.0-flash:generateContent", "desc": "تولید متن"},
           "models": {"method": "GET", "path": "/models", "desc": "فهرست مدل‌ها"}})
P("groq", "Groq", "ai", "https://api.groq.com/openai/v1", ["api_key"],
  "https://console.groq.com/keys", actions={"chat": {"method": "POST", "path": "/chat/completions", "desc": "گفتگو (سریع)"},
                                            "models": {"method": "GET", "path": "/models", "desc": "مدل‌ها"}})
P("deepseek", "DeepSeek", "ai", "https://api.deepseek.com/v1", ["api_key"],
  "https://platform.deepseek.com/api_keys", actions={"chat": {"method": "POST", "path": "/chat/completions", "desc": "گفتگو"}})
P("mistral", "Mistral AI", "ai", "https://api.mistral.ai/v1", ["api_key"],
  "https://console.mistral.ai/api-keys", actions={"chat": {"method": "POST", "path": "/chat/completions", "desc": "گفتگو"}})
P("xai", "xAI (Grok)", "ai", "https://api.x.ai/v1", ["api_key"],
  "https://console.x.ai/", actions={"chat": {"method": "POST", "path": "/chat/completions", "desc": "گفتگو"}})
P("together", "Together AI", "ai", "https://api.together.xyz/v1", ["api_key"],
  "https://api.together.ai/settings/api-keys", actions={"chat": {"method": "POST", "path": "/chat/completions", "desc": "گفتگو"}})
P("fireworks", "Fireworks AI", "ai", "https://api.fireworks.ai/inference/v1", ["api_key"],
  "https://fireworks.ai/account/api-keys", actions={"chat": {"method": "POST", "path": "/chat/completions", "desc": "گفتگو"}})
P("perplexity", "Perplexity", "ai", "https://api.perplexity.ai", ["api_key"],
  "https://www.perplexity.ai/settings/api", actions={"chat": {"method": "POST", "path": "/chat/completions", "desc": "پاسخ با منابع وب"}})
P("cohere", "Cohere", "ai", "https://api.cohere.com/v2", ["api_key"],
  "https://dashboard.cohere.com/api-keys", actions={"chat": {"method": "POST", "path": "/chat", "desc": "گفتگو"},
                                                   "embed": {"method": "POST", "path": "/embed", "desc": "بردار متن"}})
P("huggingface", "Hugging Face", "ai", "https://api-inference.huggingface.co", ["api_key"],
  "https://huggingface.co/settings/tokens", actions={"models": {"method": "GET", "path": "/models", "desc": "مدل‌ها"}},
  note="مدل‌های رایگان با محدودیت نرخ")
P("replicate", "Replicate", "ai", "https://api.replicate.com/v1", ["api_key"],
  "https://replicate.com/account/api-tokens", actions={"models": {"method": "GET", "path": "/models", "desc": "مدل‌ها"},
                                                      "predictions": {"method": "POST", "path": "/predictions", "desc": "اجرای مدل"}})
P("openrouter", "OpenRouter", "ai", "https://openrouter.ai/api/v1", ["api_key", "model"],
  "https://openrouter.ai/keys", actions={"chat": {"method": "POST", "path": "/chat/completions", "desc": "گفتگو با صدها مدل"},
                                         "models": {"method": "GET", "path": "/models", "desc": "فهرست مدل‌ها"}})
P("ollama", "Ollama (محلی)", "ai", "http://localhost:11434", ["base_url", "model"],
  "https://ollama.com/download", auth="none",
  actions={"chat": {"method": "POST", "path": "/api/chat", "desc": "گفتگو با مدل محلی"},
           "tags": {"method": "GET", "path": "/api/tags", "desc": "مدل‌های نصب‌شده"}},
  note="بدون توکن؛ مدل روی کامپیوتر خودتان اجرا می‌شود")

# ------------------------------------------------------------------ جست‌وجو
P("brave", "Brave Search", "search", "https://api.search.brave.com/res/v1", ["api_key"],
  "https://api.search.brave.com/app/keys", auth="header:X-Subscription-Token",
  actions={"web": {"method": "GET", "path": "/web/search", "desc": "جست‌وجوی وب"}})
P("tavily", "Tavily", "search", "https://api.tavily.com", ["api_key"],
  "https://app.tavily.com/home", auth="bearer",
  actions={"search": {"method": "POST", "path": "/search", "desc": "جست‌وجوی آماده برای LLM"}})
P("serpapi", "SerpAPI", "search", "https://serpapi.com", ["api_key"],
  "https://serpapi.com/manage-api-key", auth="query:api_key",
  actions={"google": {"method": "GET", "path": "/search.json", "desc": "نتایج گوگل"}})
P("google_cse", "Google Custom Search", "search", "https://www.googleapis.com/customsearch/v1",
  ["api_key", "cx"], "https://developers.google.com/custom-search/v1/introduction",
  auth="query:key", actions={"search": {"method": "GET", "path": "", "desc": "جست‌وجوی گوگل"}})
P("exa", "Exa", "search", "https://api.exa.ai", ["api_key"], "https://dashboard.exa.ai/api-keys",
  auth="header:x-api-key", actions={"search": {"method": "POST", "path": "/search", "desc": "جست‌وجوی معنایی"}})
P("firecrawl", "Firecrawl", "search", "https://api.firecrawl.dev/v1", ["api_key"],
  "https://www.firecrawl.dev/app/api-keys", actions={"scrape": {"method": "POST", "path": "/scrape", "desc": "استخراج محتوای سایت"},
                                                    "search": {"method": "POST", "path": "/search", "desc": "جست‌وجو + محتوا"}})

# ------------------------------------------------------------------ پیام‌رسان
P("telegram", "Telegram Bot", "messaging", "https://api.telegram.org", ["bot_token", "chat_id"],
  "https://t.me/BotFather", auth="query:token",
  actions={"me": {"method": "GET", "path": "/getMe", "desc": "اطلاعات ربات"},
           "updates": {"method": "GET", "path": "/getUpdates", "desc": "آخرین پیام‌ها"}})
P("discord", "Discord", "messaging", "https://discord.com/api/v10", ["bot_token"],
  "https://discord.com/developers/applications", auth="header:Authorization",
  actions={"me": {"method": "GET", "path": "/users/@me", "desc": "اطلاعات ربات"},
           "guilds": {"method": "GET", "path": "/users/@me/guilds", "desc": "سرورها"}},
  note="برای ارسال پیام: POST /channels/{channel_id}/messages")
P("slack", "Slack", "messaging", "https://slack.com/api", ["bot_token"],
  "https://api.slack.com/apps", actions={"auth": {"method": "GET", "path": "/auth.test", "desc": "تست توکن"},
                                         "channels": {"method": "GET", "path": "/conversations.list", "desc": "کانال‌ها"},
                                         "post": {"method": "POST", "path": "/chat.postMessage", "desc": "ارسال پیام"}})
P("whatsapp", "WhatsApp Cloud API", "messaging", "https://graph.facebook.com/v21.0", ["access_token", "phone_id"],
  "https://developers.facebook.com/apps", auth="bearer",
  actions={"send": {"method": "POST", "path": "/{phone_id}/messages", "desc": "ارسال پیام متنی"}})
P("twilio", "Twilio (SMS)", "messaging", "https://api.twilio.com/2010-04-01", ["account_sid", "auth_token", "from"],
  "https://console.twilio.com/", auth="basic",
  actions={"send": {"method": "POST", "path": "/Accounts/{account_sid}/Messages.json", "desc": "ارسال پیامک"}})
P("kavenegar", "کاوه‌نگار (پیامک)", "messaging", "https://api.kavenegar.com/v1", ["api_key", "sender"],
  "https://kavenegar.com/", auth="none",
  actions={"send": {"method": "GET", "path": "/{api_key}/sms/send.json", "desc": "ارسال پیامک"}})

# ------------------------------------------------------------------ ایمیل
P("resend", "Resend", "email", "https://api.resend.com", ["api_key", "from"],
  "https://resend.com/api-keys", actions={"send": {"method": "POST", "path": "/emails", "desc": "ارسال ایمیل"}})
P("sendgrid", "SendGrid", "email", "https://api.sendgrid.com/v3", ["api_key", "from"],
  "https://app.sendgrid.com/settings/api_keys", actions={"send": {"method": "POST", "path": "/mail/send", "desc": "ارسال ایمیل"}})
P("mailgun", "Mailgun", "email", "https://api.mailgun.net/v3", ["api_key", "domain", "from"],
  "https://app.mailgun.com/settings/api_security", auth="basic",
  actions={"send": {"method": "POST", "path": "/{domain}/messages", "desc": "ارسال ایمیل"}})
P("postmark", "Postmark", "email", "https://api.postmarkapp.com", ["api_key", "from"],
  "https://account.postmarkapp.com/servers", auth="header:X-Postmark-Server-Token",
  actions={"send": {"method": "POST", "path": "/email", "desc": "ارسال ایمیل"}})

# ------------------------------------------------------------------ توسعه و زیرساخت
P("github", "GitHub", "dev", "https://api.github.com", ["token", "owner", "repo"],
  "https://github.com/settings/tokens", auth="bearer",
  actions={"me": {"method": "GET", "path": "/user", "desc": "پروفایل"},
           "repos": {"method": "GET", "path": "/user/repos", "desc": "ریپازیتوری‌ها"},
           "issues": {"method": "GET", "path": "/repos/{repo}/issues", "desc": "ایشوها"}})
P("gitlab", "GitLab", "dev", "https://gitlab.com/api/v4", ["token"],
  "https://gitlab.com/-/user_settings/personal_access_tokens", auth="header:PRIVATE-TOKEN",
  actions={"me": {"method": "GET", "path": "/user", "desc": "پروفایل"},
           "projects": {"method": "GET", "path": "/projects", "desc": "پروژه‌ها"}})
P("bitbucket", "Bitbucket", "dev", "https://api.bitbucket.org/2.0", ["username", "app_password"],
  "https://bitbucket.org/account/settings/app-passwords/", auth="basic",
  actions={"repos": {"method": "GET", "path": "/repositories", "desc": "ریپازیتوری‌ها"}})
P("vercel", "Vercel", "dev", "https://api.vercel.com", ["token"],
  "https://vercel.com/account/tokens", auth="bearer",
  actions={"projects": {"method": "GET", "path": "/v9/projects", "desc": "پروژه‌ها"},
           "deployments": {"method": "GET", "path": "/v6/deployments", "desc": "استقرارها"}})
P("netlify", "Netlify", "dev", "https://api.netlify.com/api/v1", ["token"],
  "https://app.netlify.com/user/applications#personal-access-tokens",
  actions={"sites": {"method": "GET", "path": "/sites", "desc": "سایت‌ها"}})
P("cloudflare", "Cloudflare", "dev", "https://api.cloudflare.com/client/v4", ["api_token", "zone_id"],
  "https://dash.cloudflare.com/profile/api-tokens", auth="bearer",
  actions={"zones": {"method": "GET", "path": "/zones", "desc": "دامنه‌ها"},
           "dns": {"method": "GET", "path": "/zones/{zone_id}/dns_records", "desc": "رکوردهای DNS"}})
P("supabase", "Supabase", "dev", "https://api.supabase.com/v1", ["access_token"],
  "https://supabase.com/dashboard/account/tokens", auth="bearer",
  actions={"projects": {"method": "GET", "path": "/projects", "desc": "پروژه‌ها"}})
P("railway", "Railway", "dev", "https://backboard.railway.app/graphql/v2", ["api_token"],
  "https://railway.app/account/tokens", auth="bearer", note="GraphQL")
P("render", "Render", "dev", "https://api.render.com/v1", ["api_key"],
  "https://dashboard.render.com/u/settings#api-keys", auth="bearer",
  actions={"services": {"method": "GET", "path": "/services", "desc": "سرویس‌ها"}})
P("digitalocean", "DigitalOcean", "infra", "https://api.digitalocean.com/v2", ["api_token"],
  "https://cloud.digitalocean.com/account/api/tokens", auth="bearer",
  actions={"droplets": {"method": "GET", "path": "/droplets", "desc": "سرورها"},
           "domains": {"method": "GET", "path": "/domains", "desc": "دامنه‌ها"}})
P("hetzner", "Hetzner Cloud", "infra", "https://api.hetzner.cloud/v1", ["api_token"],
  "https://console.hetzner.cloud/", auth="bearer",
  actions={"servers": {"method": "GET", "path": "/servers", "desc": "سرورها"}})
P("dockerhub", "Docker Hub", "dev", "https://hub.docker.com/v2", ["username", "password"],
  "https://hub.docker.com/settings/security", auth="basic",
  actions={"repos": {"method": "GET", "path": "/repositories/{username}", "desc": "ریپازیتوری‌های ایمیج"}})
P("sentry", "Sentry", "infra", "https://sentry.io/api/0", ["auth_token", "org"],
  "https://sentry.io/settings/account/api/auth-tokens/", auth="bearer",
  actions={"issues": {"method": "GET", "path": "/projects/", "desc": "پروژه‌ها"}})
P("postgres", "PostgreSQL (خارجی)", "data", "postgresql://", ["dsn"],
  "https://www.postgresql.org/docs/current/libpq-connect.html", auth="none",
  note="DSN در ابزار SQL استفاده می‌شود؛ فایل‌های محلی هم پشتیبانی می‌شود")

# ------------------------------------------------------------------ بهره‌وری
P("notion", "Notion", "productivity", "https://api.notion.com/v1", ["token"],
  "https://www.notion.so/my-integrations", auth="bearer",
  actions={"search": {"method": "POST", "path": "/search", "desc": "جست‌وجو در ورک‌اسپیس"},
           "users": {"method": "GET", "path": "/users", "desc": "کاربران"}},
  note="هدر Notion-Version: 2022-06-28 لازم است (خودکار اضافه می‌شود)")
P("airtable", "Airtable", "productivity", "https://api.airtable.com/v0", ["api_key", "base_id"],
  "https://airtable.com/create/tokens", auth="bearer",
  actions={"records": {"method": "GET", "path": "/{base_id}/{table}", "desc": "رکوردهای جدول"}})
P("linear", "Linear", "productivity", "https://api.linear.app/graphql", ["api_key"],
  "https://linear.app/settings/api", auth="header:Authorization", note="GraphQL")
P("jira", "Jira Cloud", "productivity", "https://api.atlassian.com", ["api_token", "email", "domain"],
  "https://id.atlassian.com/manage-profile/security/api-tokens", auth="basic",
  actions={"issues": {"method": "GET", "path": "/ex/jira/{domain}/rest/api/3/search", "desc": "ایشوها"}})
P("asana", "Asana", "productivity", "https://app.asana.com/api/1.0", ["token"],
  "https://app.asana.com/0/my-apps", auth="bearer",
  actions={"projects": {"method": "GET", "path": "/projects", "desc": "پروژه‌ها"}})
P("trello", "Trello", "productivity", "https://api.trello.com/1", ["api_key", "token"],
  "https://trello.com/power-ups/admin", auth="query:key",
  actions={"boards": {"method": "GET", "path": "/members/me/boards", "desc": "بردها"}})
P("clickup", "ClickUp", "productivity", "https://api.clickup.com/api/v2", ["api_key"],
  "https://app.clickup.com/settings/apps", actions={"teams": {"method": "GET", "path": "/team", "desc": "فضاهای کاری"}})
P("todoist", "Todoist", "productivity", "https://api.todoist.com/rest/v2", ["api_key"],
  "https://app.todoist.com/app/settings/integrations/developer", actions={"tasks": {"method": "GET", "path": "/tasks", "desc": "کارها"}})
P("google_sheets", "Google Sheets", "productivity", "https://sheets.googleapis.com/v4", ["api_key", "spreadsheet_id"],
  "https://console.cloud.google.com/apis/credentials", auth="query:key",
  actions={"values": {"method": "GET", "path": "/spreadsheets/{spreadsheet_id}/values/A1:Z100", "desc": "خواندن سلول‌ها"}})
P("google_drive", "Google Drive", "productivity", "https://www.googleapis.com/drive/v3", ["access_token"],
  "https://console.cloud.google.com/apis/credentials", auth="bearer",
  actions={"files": {"method": "GET", "path": "/files", "desc": "فایل‌ها"}})
P("dropbox", "Dropbox", "productivity", "https://api.dropboxapi.com/2", ["access_token"],
  "https://www.dropbox.com/developers/apps", auth="bearer",
  actions={"files": {"method": "POST", "path": "/files/list_folder", "desc": "فهرست فایل‌ها"}})
P("figma", "Figma", "productivity", "https://api.figma.com/v1", ["token"],
  "https://www.figma.com/developers/api#access-tokens", auth="header:X-Figma-Token",
  actions={"me": {"method": "GET", "path": "/me", "desc": "پروفایل"}})

# ------------------------------------------------------------------ شبکه‌های اجتماعی
P("x_twitter", "X (Twitter)", "social", "https://api.x.com/2", ["bearer_token"],
  "https://developer.x.com/en/portal/dashboard", auth="bearer",
  actions={"tweets": {"method": "GET", "path": "/tweets/search/recent", "desc": "جست‌وجوی توییت"},
           "me": {"method": "GET", "path": "/users/me", "desc": "پروفایل"}})
P("reddit", "Reddit", "social", "https://oauth.reddit.com", ["access_token"],
  "https://www.reddit.com/prefs/apps", auth="bearer",
  actions={"me": {"method": "GET", "path": "/api/v1/me", "desc": "پروفایل"}})
P("linkedin", "LinkedIn", "social", "https://api.linkedin.com/v2", ["access_token"],
  "https://www.linkedin.com/developers/apps", auth="bearer",
  actions={"me": {"method": "GET", "path": "/userinfo", "desc": "پروفایل"}})
P("youtube", "YouTube Data", "social", "https://www.googleapis.com/youtube/v3", ["api_key"],
  "https://console.cloud.google.com/apis/credentials", auth="query:key",
  actions={"search": {"method": "GET", "path": "/search", "desc": "جست‌وجوی ویدیو"},
           "video": {"method": "GET", "path": "/videos", "desc": "جزئیات ویدیو"}})
P("instagram", "Instagram Graph", "social", "https://graph.facebook.com/v21.0", ["access_token", "ig_user_id"],
  "https://developers.facebook.com/docs/instagram-api", auth="query:access_token",
  actions={"media": {"method": "GET", "path": "/{ig_user_id}/media", "desc": "پست‌ها"}})
P("tiktok", "TikTok for Developers", "social", "https://open.tiktokapis.com/v2", ["access_token"],
  "https://developers.tiktok.com/", auth="bearer", actions={"me": {"method": "GET", "path": "/user/info/", "desc": "پروفایل"}})

# ------------------------------------------------------------------ فروش و پرداخت
P("stripe", "Stripe", "commerce", "https://api.stripe.com/v1", ["secret_key"],
  "https://dashboard.stripe.com/apikeys", auth="bearer",
  actions={"balance": {"method": "GET", "path": "/balance", "desc": "موجودی"},
           "charges": {"method": "GET", "path": "/charges", "desc": "پرداخت‌ها"},
           "customers": {"method": "GET", "path": "/customers", "desc": "مشتری‌ها"},
           "payment_links": {"method": "POST", "path": "/payment_links", "desc": "ساخت لینک پرداخت"}})
P("paypal", "PayPal", "commerce", "https://api-m.paypal.com", ["client_id", "secret"],
  "https://developer.paypal.com/dashboard/applications/live", auth="basic")
P("shopify", "Shopify", "commerce", "https://{shop}.myshopify.com/admin/api/2024-10", ["shop", "access_token"],
  "https://admin.shopify.com/", auth="header:X-Shopify-Access-Token",
  actions={"products": {"method": "GET", "path": "/products.json", "desc": "محصولات"},
           "orders": {"method": "GET", "path": "/orders.json", "desc": "سفارش‌ها"}})
P("woocommerce", "WooCommerce", "commerce", "https://{domain}/wp-json/wc/v3", ["domain", "consumer_key", "consumer_secret"],
  "https://woocommerce.com/document/woocommerce-rest-api/", auth="query:consumer_key",
  actions={"products": {"method": "GET", "path": "/products", "desc": "محصولات"},
           "orders": {"method": "GET", "path": "/orders", "desc": "سفارش‌ها"}})
P("zarinpal", "زرین‌پال", "commerce", "https://payment.zarinpal.com/pg/v4", ["merchant_id"],
  "https://www.zarinpal.com/panel", auth="none",
  actions={"request": {"method": "POST", "path": "/payment/request.json", "desc": "ساخت تراکنش"},
           "verify": {"method": "POST", "path": "/payment/verify.json", "desc": "تأیید تراکنش"}})
P("idpay", "آیدی‌پی", "commerce", "https://api.idpay.ir/v1.1", ["api_key"],
  "https://idpay.ir/panel", auth="header:X-API-KEY",
  actions={"payment": {"method": "POST", "path": "/payment", "desc": "ساخت تراکنش"},
           "verify": {"method": "POST", "path": "/payment/verify", "desc": "تأیید"}})

# ------------------------------------------------------------------ داده و نقشه
P("openweather", "OpenWeather", "data", "https://api.openweathermap.org/data/2.5", ["api_key"],
  "https://home.openweathermap.org/api_keys", auth="query:appid",
  actions={"current": {"method": "GET", "path": "/weather", "desc": "هوای فعلی"}})
P("google_maps", "Google Maps", "data", "https://maps.googleapis.com/maps/api", ["api_key"],
  "https://console.cloud.google.com/apis/credentials", auth="query:key",
  actions={"geocode": {"method": "GET", "path": "/geocode/json", "desc": "تبدیل آدرس به مختصات"}})
P("mapbox", "Mapbox", "data", "https://api.mapbox.com", ["access_token"],
  "https://account.mapbox.com/access-tokens/", auth="query:access_token",
  actions={"geocode": {"method": "GET", "path": "/geocoding/v5/mapbox.places/{query}.json", "desc": "جغرافیایی"}})
P("stooq", "بورس و ارز (Stooq)", "data", "https://stooq.com/q", ["none"],
  "https://stooq.com/", auth="none",
  actions={"quote": {"method": "GET", "path": "/d/l/", "desc": "قیمت سهام/ارز (CSV)"}})


def catalog_list() -> list[dict]:
    """فهرست عمومی برای UI — بدون هیچ مقدار محرمانه‌ای."""
    order = {"ai": 0, "search": 1, "messaging": 2, "email": 3, "dev": 4, "infra": 5,
             "productivity": 6, "social": 7, "commerce": 8, "data": 9}
    items = sorted(CATALOG.values(), key=lambda x: (order.get(x["category"], 99), x["name"]))
    return [{k: v for k, v in it.items()} for it in items]


def get_provider(key: str) -> dict | None:
    return CATALOG.get((key or "").strip().lower())


CATEGORY_FA = {
    "ai": "هوش مصنوعی", "search": "جست‌وجو", "messaging": "پیام‌رسان", "email": "ایمیل",
    "dev": "توسعه", "infra": "زیرساخت", "productivity": "بهره‌وری", "social": "شبکهٔ اجتماعی",
    "commerce": "فروش و پرداخت", "data": "داده و نقشه",
}
