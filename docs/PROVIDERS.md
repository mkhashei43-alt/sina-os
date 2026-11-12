# 🔌 سرویس‌های پشتیبانی‌شده

سینا OS با **73 سرویس** کار می‌کند. برای هر سرویس فقط کلید خودتان را لازم دارید:
از کنسول (تب اتصال‌ها) یا با دستور `python sina.py token add <key>`.

> توکن‌ها با Fernet رمزنگاری و در همان کامپیوتر ذخیره می‌شوند؛ هرگز به مدل زبانی فرستاده نمی‌شوند و در لاگ/پاسخ API نمایش داده نمی‌شوند.

## هوش مصنوعی (15)

| کلید | سرویس | فیلدها | عملیات آماده | مستندات |
|---|---|---|---|---|
| `anthropic` | Anthropic (Claude) | api_key | messages, models | [راهنما](https://console.anthropic.com/settings/keys) |
| `cohere` | Cohere | api_key | chat, embed | [راهنما](https://dashboard.cohere.com/api-keys) |
| `deepseek` | DeepSeek | api_key | chat | [راهنما](https://platform.deepseek.com/api_keys) |
| `fireworks` | Fireworks AI | api_key | chat | [راهنما](https://fireworks.ai/account/api-keys) |
| `google_gemini` | Google Gemini | api_key | generate, models | [راهنما](https://aistudio.google.com/apikey) |
| `groq` | Groq | api_key | chat, models | [راهنما](https://console.groq.com/keys) |
| `huggingface` | Hugging Face *(مدل‌های رایگان با محدودیت نرخ)* | api_key | models | [راهنما](https://huggingface.co/settings/tokens) |
| `mistral` | Mistral AI | api_key | chat | [راهنما](https://console.mistral.ai/api-keys) |
| `ollama` | Ollama (محلی) *(بدون توکن؛ مدل روی کامپیوتر خودتان اجرا می‌شود)* | base_url, model | chat, tags | [راهنما](https://ollama.com/download) |
| `openai` | OpenAI | api_key | chat, models, images, embeddings | [راهنما](https://platform.openai.com/api-keys) |
| `openrouter` | OpenRouter | api_key, model | chat, models | [راهنما](https://openrouter.ai/keys) |
| `perplexity` | Perplexity | api_key | chat | [راهنما](https://www.perplexity.ai/settings/api) |
| `replicate` | Replicate | api_key | models, predictions | [راهنما](https://replicate.com/account/api-tokens) |
| `together` | Together AI | api_key | chat | [راهنما](https://api.together.ai/settings/api-keys) |
| `xai` | xAI (Grok) | api_key | chat | [راهنما](https://console.x.ai/) |

## جست‌وجو (6)

| کلید | سرویس | فیلدها | عملیات آماده | مستندات |
|---|---|---|---|---|
| `brave` | Brave Search | api_key | web | [راهنما](https://api.search.brave.com/app/keys) |
| `exa` | Exa | api_key | search | [راهنما](https://dashboard.exa.ai/api-keys) |
| `firecrawl` | Firecrawl | api_key | scrape, search | [راهنما](https://www.firecrawl.dev/app/api-keys) |
| `google_cse` | Google Custom Search | api_key, cx | search | [راهنما](https://developers.google.com/custom-search/v1/introduction) |
| `serpapi` | SerpAPI | api_key | google | [راهنما](https://serpapi.com/manage-api-key) |
| `tavily` | Tavily | api_key | search | [راهنما](https://app.tavily.com/home) |

## پیام‌رسان (6)

| کلید | سرویس | فیلدها | عملیات آماده | مستندات |
|---|---|---|---|---|
| `discord` | Discord *(برای ارسال پیام: POST /channels/{channel_id}/messages)* | bot_token | me, guilds | [راهنما](https://discord.com/developers/applications) |
| `slack` | Slack | bot_token | auth, channels, post | [راهنما](https://api.slack.com/apps) |
| `telegram` | Telegram Bot | bot_token, chat_id | me, updates | [راهنما](https://t.me/BotFather) |
| `twilio` | Twilio (SMS) | account_sid, auth_token, from | send | [راهنما](https://console.twilio.com/) |
| `whatsapp` | WhatsApp Cloud API | access_token, phone_id | send | [راهنما](https://developers.facebook.com/apps) |
| `kavenegar` | کاوه‌نگار (پیامک) | api_key, sender | send | [راهنما](https://kavenegar.com/) |

## ایمیل (4)

| کلید | سرویس | فیلدها | عملیات آماده | مستندات |
|---|---|---|---|---|
| `mailgun` | Mailgun | api_key, domain, from | send | [راهنما](https://app.mailgun.com/settings/api_security) |
| `postmark` | Postmark | api_key, from | send | [راهنما](https://account.postmarkapp.com/servers) |
| `resend` | Resend | api_key, from | send | [راهنما](https://resend.com/api-keys) |
| `sendgrid` | SendGrid | api_key, from | send | [راهنما](https://app.sendgrid.com/settings/api_keys) |

## توسعه (10)

| کلید | سرویس | فیلدها | عملیات آماده | مستندات |
|---|---|---|---|---|
| `bitbucket` | Bitbucket | username, app_password | repos | [راهنما](https://bitbucket.org/account/settings/app-passwords/) |
| `cloudflare` | Cloudflare | api_token, zone_id | zones, dns | [راهنما](https://dash.cloudflare.com/profile/api-tokens) |
| `dockerhub` | Docker Hub | username, password | repos | [راهنما](https://hub.docker.com/settings/security) |
| `github` | GitHub | token, owner, repo | me, repos, issues | [راهنما](https://github.com/settings/tokens) |
| `gitlab` | GitLab | token | me, projects | [راهنما](https://gitlab.com/-/user_settings/personal_access_tokens) |
| `netlify` | Netlify | token | sites | [راهنما](https://app.netlify.com/user/applications#personal-access-tokens) |
| `railway` | Railway *(GraphQL)* | api_token | — | [راهنما](https://railway.app/account/tokens) |
| `render` | Render | api_key | services | [راهنما](https://dashboard.render.com/u/settings#api-keys) |
| `supabase` | Supabase | access_token | projects | [راهنما](https://supabase.com/dashboard/account/tokens) |
| `vercel` | Vercel | token | projects, deployments | [راهنما](https://vercel.com/account/tokens) |

## زیرساخت (3)

| کلید | سرویس | فیلدها | عملیات آماده | مستندات |
|---|---|---|---|---|
| `digitalocean` | DigitalOcean | api_token | droplets, domains | [راهنما](https://cloud.digitalocean.com/account/api/tokens) |
| `hetzner` | Hetzner Cloud | api_token | servers | [راهنما](https://console.hetzner.cloud/) |
| `sentry` | Sentry | auth_token, org | issues | [راهنما](https://sentry.io/settings/account/api/auth-tokens/) |

## بهره‌وری (12)

| کلید | سرویس | فیلدها | عملیات آماده | مستندات |
|---|---|---|---|---|
| `airtable` | Airtable | api_key, base_id | records | [راهنما](https://airtable.com/create/tokens) |
| `asana` | Asana | token | projects | [راهنما](https://app.asana.com/0/my-apps) |
| `clickup` | ClickUp | api_key | teams | [راهنما](https://app.clickup.com/settings/apps) |
| `dropbox` | Dropbox | access_token | files | [راهنما](https://www.dropbox.com/developers/apps) |
| `figma` | Figma | token | me | [راهنما](https://www.figma.com/developers/api#access-tokens) |
| `google_drive` | Google Drive | access_token | files | [راهنما](https://console.cloud.google.com/apis/credentials) |
| `google_sheets` | Google Sheets | api_key, spreadsheet_id | values | [راهنما](https://console.cloud.google.com/apis/credentials) |
| `jira` | Jira Cloud | api_token, email, domain | issues | [راهنما](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `linear` | Linear *(GraphQL)* | api_key | — | [راهنما](https://linear.app/settings/api) |
| `notion` | Notion *(هدر Notion-Version: 2022-06-28 لازم است (خودکار اضافه می‌شود))* | token | search, users | [راهنما](https://www.notion.so/my-integrations) |
| `todoist` | Todoist | api_key | tasks | [راهنما](https://app.todoist.com/app/settings/integrations/developer) |
| `trello` | Trello | api_key, token | boards | [راهنما](https://trello.com/power-ups/admin) |

## شبکهٔ اجتماعی (6)

| کلید | سرویس | فیلدها | عملیات آماده | مستندات |
|---|---|---|---|---|
| `instagram` | Instagram Graph | access_token, ig_user_id | media | [راهنما](https://developers.facebook.com/docs/instagram-api) |
| `linkedin` | LinkedIn | access_token | me | [راهنما](https://www.linkedin.com/developers/apps) |
| `reddit` | Reddit | access_token | me | [راهنما](https://www.reddit.com/prefs/apps) |
| `tiktok` | TikTok for Developers | access_token | me | [راهنما](https://developers.tiktok.com/) |
| `x_twitter` | X (Twitter) | bearer_token | tweets, me | [راهنما](https://developer.x.com/en/portal/dashboard) |
| `youtube` | YouTube Data | api_key | search, video | [راهنما](https://console.cloud.google.com/apis/credentials) |

## فروش و پرداخت (6)

| کلید | سرویس | فیلدها | عملیات آماده | مستندات |
|---|---|---|---|---|
| `paypal` | PayPal | client_id, secret | — | [راهنما](https://developer.paypal.com/dashboard/applications/live) |
| `shopify` | Shopify | shop, access_token | products, orders | [راهنما](https://admin.shopify.com/) |
| `stripe` | Stripe | secret_key | balance, charges, customers, payment_links | [راهنما](https://dashboard.stripe.com/apikeys) |
| `woocommerce` | WooCommerce | domain, consumer_key, consumer_secret | products, orders | [راهنما](https://woocommerce.com/document/woocommerce-rest-api/) |
| `idpay` | آیدی‌پی | api_key | payment, verify | [راهنما](https://idpay.ir/panel) |
| `zarinpal` | زرین‌پال | merchant_id | request, verify | [راهنما](https://www.zarinpal.com/panel) |

## داده و نقشه (5)

| کلید | سرویس | فیلدها | عملیات آماده | مستندات |
|---|---|---|---|---|
| `google_maps` | Google Maps | api_key | geocode | [راهنما](https://console.cloud.google.com/apis/credentials) |
| `mapbox` | Mapbox | access_token | geocode | [راهنما](https://account.mapbox.com/access-tokens/) |
| `openweather` | OpenWeather | api_key | current | [راهنما](https://home.openweathermap.org/api_keys) |
| `postgres` | PostgreSQL (خارجی) *(DSN در ابزار SQL استفاده می‌شود؛ فایل‌های محلی هم پشتیبانی می‌شود)* | dsn | — | [راهنما](https://www.postgresql.org/docs/current/libpq-connect.html) |
| `stooq` | بورس و ارز (Stooq) | none | quote | [راهنما](https://stooq.com/) |

## سرویسی نیست؟ خودتان اضافه کنید

فایل `backend/app/integrations/catalog.py` را ببینید؛ هر سرویس یک دیکشنری ساده است:

```python
P("myservice", "سرویس من", "dev", "https://api.myservice.com/v1", ["api_key"],
  "https://myservice.com/docs/api-keys", auth="bearer",
  actions={"list": {"method": "GET", "path": "/items", "desc": "فهرست آیتم‌ها"}})
```

همین! بعد از ری‌استارت، عامل می‌تواند با ابزار `http_api` و `provider=myservice` آن را صدا بزند.

## ابزارهای عمومی که از کلید شما استفاده می‌کنند

| ابزار | کاربرد |
|---|---|
| `http_api` | هر درخواست REST به سرویس‌های بالا (فقط به همان میزبان مجاز) |
| `llm_ask` | پرسش از هر مدل با کلید شما (نظر دوم، کار ارزان، مدل متفاوت) |
| `search_api` | جست‌وجوی وب با کلید Brave/Tavily/SerpAPI/Google/Exa |
| `email_send` | ارسال ایمیل با Resend/SendGrid/Mailgun/Postmark |
| `sms_send` | پیامک با Twilio یا کاوه‌نگار |
| `messaging_send` | پیام در Slack/Discord/Telegram/WhatsApp |
| `ssh` · `github` · `cloudflare` · `telegram` | ابزارهای اختصاصی با عملکرد کامل |