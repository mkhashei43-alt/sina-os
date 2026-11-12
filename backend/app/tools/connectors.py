"""اتصال‌های عمومی: با توکنِ خودِ کاربر، هر سرویس معروفی را صدا می‌زنند.

ابزارها:
  http_api       درخواست REST به هر سرویسِ ثبت‌شده در کتالوگ (با فهرست میزبان مجاز)
  llm_ask        پرسش از هر ارائه‌دهندهٔ مدل سازگار با OpenAI (OpenAI، Groq، DeepSeek، …)
  search_api     جست‌وجوی وب با کلید کاربر (Brave، Tavily، SerpAPI، Google CSE، Exa)
  email_send     ارسال ایمیل (Resend، SendGrid، Mailgun، Postmark)
  sms_send       ارسال پیامک (Twilio، کاوه‌نگار)
  messaging_send ارسال پیام در Slack/Discord/Telegram/WhatsApp

امنیت:
  * فقط میزبان همان سرویس (base_url) مجاز است → جلوگیری از SSRF
  * توکن‌ها هرگز در خروجی چاپ نمی‌شوند (redact)
  * هر درخواستِ تغییردهنده (POST/PUT/PATCH/DELETE) نیازمند تأیید انسانی است
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
from sqlalchemy import select

from ..crypto import decrypt_json
from ..db import SessionLocal
from ..integrations.catalog import CATALOG, get_provider
from ..models import Integration
from ..security import sanitize_output
from .base import Tool, ToolContext, ToolResult, registry

TOKEN_FIELDS = ("api_key", "token", "access_token", "secret_key", "bearer_token",
                "bot_token", "auth_token", "api_token", "personal_access_token")
USER_FIELDS = ("username", "email", "account_sid", "client_id", "consumer_key")
PASS_FIELDS = ("password", "auth_token", "secret", "app_password", "consumer_secret",
               "client_secret", "api_key")
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


async def _config(user_id: str, kind: str) -> dict | None:
    async with SessionLocal() as db:
        row = (await db.execute(
            select(Integration).where(Integration.user_id == user_id, Integration.kind == kind,
                                      Integration.enabled == True)  # noqa: E712
        )).scalar_one_or_none()
        return decrypt_json(row.config_enc) if row else None


def _first(cfg: dict, names: tuple[str, ...]) -> str:
    for n in names:
        v = cfg.get(n)
        if v:
            return str(v)
    return ""


def _redact(text: str, cfg: dict) -> str:
    for _, v in cfg.items():
        s = str(v or "")
        if len(s) >= 8:
            text = text.replace(s, "***")
    return text


def _fill(template: str, cfg: dict, args: dict) -> tuple[str, list[str]]:
    """جایگزینی {placeholder} از تنظیمات/آرگومان‌ها؛ فهرست جای‌های خالی را برمی‌گرداند."""
    missing: list[str] = []

    def repl(m: re.Match) -> str:
        key = m.group(1)
        val = args.get(key) or cfg.get(key)
        if val in (None, ""):
            missing.append(key)
            return ""
        return str(val)

    return re.sub(r"\{(\w+)\}", repl, template), missing


def _apply_auth(cfg: dict, spec: dict, headers: dict, params: dict) -> httpx.Auth | tuple | None:
    auth = spec.get("auth") or "bearer"
    token = _first(cfg, TOKEN_FIELDS + ("merchant_id",))
    if auth == "none":
        return None
    if auth == "bearer":
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return None
    if auth.startswith("header:"):
        name = auth.split(":", 1)[1]
        if token:
            headers[name] = token
        return None
    if auth.startswith("query:"):
        name = auth.split(":", 1)[1]
        if token:
            params[name] = token
        return None
    if auth == "basic":
        user = _first(cfg, USER_FIELDS) or "user"
        secret = _first(cfg, PASS_FIELDS) or token
        if user and secret:
            return (user, secret)
    return None


class HttpApiTool(Tool):
    name = "http_api"
    risk = "confirm"
    description = (
        "Call any API the user has connected with their own token (see `provider`). "
        "Use action presets from the provider catalog (e.g. provider=github, action=repos) or an explicit "
        "method+path. Placeholders like {repo} or {zone_id} are filled from the saved credentials. "
        "GET requests run immediately; POST/PUT/PATCH/DELETE need human approval."
    )
    parameters = {
        "type": "object",
        "properties": {
            "provider": {"type": "string", "description": "catalog key, e.g. notion | stripe | vercel | slack"},
            "action": {"type": "string", "description": "preset action name from the catalog"},
            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"], "default": "GET"},
            "path": {"type": "string", "description": "API path (relative to base), may contain {placeholders}"},
            "query": {"type": "object", "description": "query string parameters"},
            "body": {"type": "object", "description": "JSON body"},
            "form": {"type": "object", "description": "form-encoded body"},
            "headers": {"type": "object", "description": "extra headers (never for auth)"},
        },
        "required": ["provider"],
    }

    def risk_for(self, args: dict) -> str:
        m = (args.get("method") or "GET").upper()
        if args.get("action"):
            act = (get_provider(str(args.get("provider"))) or {}).get("actions", {}).get(args["action"]) or {}
            m = (act.get("method") or m).upper()
        return "safe" if m in SAFE_METHODS else "confirm"

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        key = str(args.get("provider") or "").lower()
        spec = get_provider(key)
        if not spec:
            return ToolResult(False, f"سرویس «{key}» در کتالوگ نیست. یکی از این‌ها: "
                                     + ", ".join(sorted(CATALOG))[:800])
        cfg = await _config(ctx.user_id, key)
        if not cfg:
            return ToolResult(False, f"کلید «{spec['name']}» ثبت نشده است. از صفحهٔ اتصال‌ها یا دستور "
                                     f"`sina token add {key}` اضافه کنید. راهنما: {spec['docs']}")

        action = args.get("action") or ""
        preset: dict[str, Any] = spec.get("actions", {}).get(action, {}) if action else {}
        if action and not preset:
            return ToolResult(False, f"عملیات «{action}» برای {spec['name']} تعریف نشده. "
                                     f"گزینه‌ها: {', '.join(spec.get('actions', {})) or '—'}")

        method = (args.get("method") or preset.get("method") or "GET").upper()
        raw_path = args.get("path") or preset.get("path") or ""
        base = (cfg.get("base_url") or spec["base"]).rstrip("/")
        base, miss_b = _fill(base, cfg, args)
        if miss_b:
            return ToolResult(False, f"فیلدهای ضروری برای آدرس سرویس خالی‌اند: {', '.join(sorted(set(miss_b)))}")
        path, miss = _fill(raw_path, cfg, args)
        if miss:
            return ToolResult(False, f"این فیلدها باید در تنظیمات {spec['name']} پر شوند: {', '.join(sorted(set(miss)))}")

        url = base + (path if path.startswith("/") else ("/" + path if path else ""))
        if not url.startswith(("http://", "https://")):
            return ToolResult(False, "آدرس باید http/https باشد")
        # ---- محافظت SSRF: فقط همان میزبان ----
        if urlparse(url).netloc.lower() != urlparse(base).netloc.lower():
            return ToolResult(False, "دسترسی به میزبان غیرمجاز: فقط آدرس پایهٔ همین سرویس مجاز است")

        headers = {"Accept": "application/json", **(args.get("headers") or {})}
        params: dict[str, Any] = dict(args.get("query") or {})
        auth = _apply_auth(cfg, spec, headers, params)
        if key == "notion":
            headers.setdefault("Notion-Version", "2022-06-28")
        if key == "github":
            headers.setdefault("Accept", "application/vnd.github+json")

        try:
            async with httpx.AsyncClient(timeout=min(ctx.timeout, 60), auth=auth, follow_redirects=True) as c:
                r = await c.request(method, url, headers=headers, params=params or None,
                                    json=args.get("body"), data=args.get("form"))
        except httpx.HTTPError as e:
            return ToolResult(False, f"خطای شبکه: {type(e).__name__}: {e}")

        body_text = r.text[:120_000]
        pretty = body_text
        try:
            pretty = json.dumps(r.json(), ensure_ascii=False, indent=1)[:60_000]
        except Exception:
            pass
        pretty = sanitize_output(_redact(pretty, cfg))
        ok = r.status_code < 400
        head = f"[{spec['name']}] {method} {path or '/'} → {r.status_code}\n"
        if not ok:
            head += "راهنما: کد 401/403 یعنی توکن نامعتبر یا دسترسی کم؛ 404 یعنی مسیر/شناسه اشتباه.\n"
        return ToolResult(ok, (head + pretty)[:60_000],
                          {"provider": key, "status": r.status_code, "url": url}, r.status_code)


class LlmAskTool(Tool):
    name = "llm_ask"
    risk = "safe"
    description = (
        "Ask any AI model the user has a key for (provider: openai | anthropic | google_gemini | groq | "
        "deepseek | mistral | xai | together | perplexity | openrouter | ollama). Good for a second opinion, "
        "cheap bulk work, or a model different from the agent's own."
    )
    parameters = {
        "type": "object",
        "properties": {
            "provider": {"type": "string"},
            "prompt": {"type": "string"},
            "system": {"type": "string", "description": "optional system instruction"},
            "model": {"type": "string", "description": "override model name"},
            "max_tokens": {"type": "integer", "default": 1024},
        },
        "required": ["provider", "prompt"],
    }

    DEFAULT_MODELS = {
        "openai": "gpt-4o-mini", "groq": "llama-3.3-70b-versatile", "deepseek": "deepseek-chat",
        "mistral": "mistral-small-latest", "xai": "grok-2-latest", "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "perplexity": "sonar", "openrouter": "openai/gpt-4o-mini", "ollama": "llama3.2",
        "anthropic": "claude-3-5-sonnet-latest", "google_gemini": "gemini-2.0-flash",
    }

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        key = str(args.get("provider") or "").lower()
        spec = get_provider(key)
        if not spec or spec["category"] != "ai":
            return ToolResult(False, "این ارائه‌دهنده مدل نیست. یکی از: " + ", ".join(
                k for k, v in CATALOG.items() if v["category"] == "ai"))
        cfg = await _config(ctx.user_id, key)
        if not cfg:
            return ToolResult(False, f"کلید «{spec['name']}» ثبت نشده. `sina token add {key}` — راهنما: {spec['docs']}")
        model = args.get("model") or cfg.get("model") or self.DEFAULT_MODELS.get(key, "")
        prompt = args.get("prompt") or ""
        if not prompt:
            return ToolResult(False, "پارامتر prompt لازم است")
        max_tokens = int(args.get("max_tokens") or 1024)
        base = (cfg.get("base_url") or spec["base"]).rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=min(ctx.timeout, 90)) as c:
                if key == "anthropic":
                    r = await c.post(f"{base}/messages",
                                     headers={"x-api-key": cfg["api_key"], "anthropic-version": "2023-06-01"},
                                     json={"model": model, "max_tokens": max_tokens,
                                           "system": args.get("system") or "You are a helpful assistant.",
                                           "messages": [{"role": "user", "content": prompt}]})
                    r.raise_for_status()
                    text = "".join(b.get("text", "") for b in r.json().get("content", []))
                elif key == "google_gemini":
                    r = await c.post(f"{base}/models/{model}:generateContent",
                                     params={"key": cfg["api_key"]},
                                     json={"contents": [{"parts": [{"text": prompt}]}]})
                    r.raise_for_status()
                    cands = r.json().get("candidates") or [{}]
                    text = "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))
                elif key == "ollama":
                    r = await c.post(f"{base}/api/chat", json={
                        "model": model, "stream": False,
                        "messages": ([{"role": "system", "content": args["system"]}] if args.get("system") else [])
                        + [{"role": "user", "content": prompt}]})
                    r.raise_for_status()
                    text = (r.json().get("message") or {}).get("content", "")
                else:
                    headers = {"Authorization": f"Bearer {cfg.get('api_key') or cfg.get('token') or ''}"}
                    r = await c.post(f"{base}/chat/completions", headers=headers, json={
                        "model": model, "max_tokens": max_tokens,
                        "messages": ([{"role": "system", "content": args["system"]}] if args.get("system") else [])
                        + [{"role": "user", "content": prompt}]})
                    r.raise_for_status()
                    text = ((r.json().get("choices") or [{}])[0].get("message") or {}).get("content", "")
        except httpx.HTTPStatusError as e:
            return ToolResult(False, f"{spec['name']} → HTTP {e.response.status_code}: {e.response.text[:300]}")
        except httpx.HTTPError as e:
            return ToolResult(False, f"خطای شبکه: {type(e).__name__}: {e}")
        return ToolResult(True, sanitize_output(_redact(text, cfg))[:40_000],
                          {"provider": key, "model": model})


class SearchApiTool(Tool):
    name = "search_api"
    risk = "safe"
    description = ("Web search using the user's own API key. Providers: brave | tavily | serpapi | "
                   "google_cse | exa (auto-picks whichever is connected).")
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "count": {"type": "integer", "default": 5},
                       "provider": {"type": "string", "description": "optional: force a provider"}},
        "required": ["query"],
    }

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        q = (args.get("query") or "").strip()
        n = max(1, min(int(args.get("count") or 5), 10))
        if not q:
            return ToolResult(False, "پارامتر query لازم است")
        order = [args["provider"].lower()] if args.get("provider") else \
            ["brave", "tavily", "serpapi", "google_cse", "exa"]
        for key in order:
            cfg = await _config(ctx.user_id, key)
            if not cfg:
                continue
            try:
                async with httpx.AsyncClient(timeout=30) as c:
                    if key == "brave":
                        r = await c.get("https://api.search.brave.com/res/v1/web/search",
                                        headers={"X-Subscription-Token": cfg["api_key"],
                                                 "Accept": "application/json"},
                                        params={"q": q, "count": n})
                        r.raise_for_status()
                        items = (r.json().get("web") or {}).get("results", [])
                        out = "\n".join(f"{i+1}. {x['title']}\n   {x['url']}\n   {x.get('description','')[:200]}"
                                        for i, x in enumerate(items))
                    elif key == "tavily":
                        r = await c.post("https://api.tavily.com/search",
                                         json={"api_key": cfg["api_key"], "query": q, "max_results": n})
                        r.raise_for_status()
                        items = r.json().get("results", [])
                        out = "\n".join(f"{i+1}. {x.get('title','')}\n   {x.get('url','')}\n   {(x.get('content') or '')[:200]}"
                                        for i, x in enumerate(items))
                    elif key == "serpapi":
                        r = await c.get("https://serpapi.com/search.json",
                                        params={"q": q, "api_key": cfg["api_key"], "num": n})
                        r.raise_for_status()
                        items = r.json().get("organic_results", [])[:n]
                        out = "\n".join(f"{i+1}. {x.get('title','')}\n   {x.get('link','')}\n   {(x.get('snippet') or '')[:200]}"
                                        for i, x in enumerate(items))
                    elif key == "google_cse":
                        r = await c.get("https://www.googleapis.com/customsearch/v1",
                                        params={"q": q, "key": cfg["api_key"], "cx": cfg.get("cx", ""), "num": n})
                        r.raise_for_status()
                        items = r.json().get("items", [])
                        out = "\n".join(f"{i+1}. {x.get('title','')}\n   {x.get('link','')}\n   {(x.get('snippet') or '')[:200]}"
                                        for i, x in enumerate(items))
                    else:  # exa
                        r = await c.post("https://api.exa.ai/search",
                                         headers={"x-api-key": cfg["api_key"]},
                                         json={"query": q, "numResults": n})
                        r.raise_for_status()
                        items = r.json().get("results", [])
                        out = "\n".join(f"{i+1}. {x.get('title','')}\n   {x.get('url','')}\n   {(x.get('text') or '')[:200]}"
                                        for i, x in enumerate(items))
                return ToolResult(True, f"[{key}] نتایج «{q}»:\n{out or 'نتیجه‌ای یافت نشد'}",
                                  {"provider": key, "count": len(items)})
            except httpx.HTTPError as e:
                return ToolResult(False, f"{key} خطا داد: {type(e).__name__}: {e}")
        return ToolResult(False, "هیچ کلید جست‌وجویی ثبت نشده. `sina token add brave` یا Tavily/SerpAPI را اضافه کنید.")


async def _post_json(url: str, headers: dict, data: Any = None, json_body: Any = None,
                     auth: Any = None, form: bool = False) -> httpx.Response:
    async with httpx.AsyncClient(timeout=45, auth=auth) as c:
        return await c.post(url, headers=headers, data=data, json=json_body)


class EmailSendTool(Tool):
    name = "email_send"
    risk = "confirm"
    description = "Send an email using the user's own provider (resend | sendgrid | mailgun | postmark)."
    parameters = {
        "type": "object",
        "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "text": {"type": "string"},
                       "html": {"type": "string"}, "provider": {"type": "string"}},
        "required": ["to", "subject"],
    }

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        to, subject = args.get("to") or "", args.get("subject") or ""
        text, html = args.get("text") or "", args.get("html") or ""
        if not to or not subject:
            return ToolResult(False, "to و subject لازم است")
        for key in ([args["provider"].lower()] if args.get("provider") else ["resend", "sendgrid", "mailgun", "postmark"]):
            cfg = await _config(ctx.user_id, key)
            if not cfg:
                continue
            sender = cfg.get("from") or ""
            try:
                if key == "resend":
                    r = await _post_json("https://api.resend.com/emails",
                                         {"Authorization": f"Bearer {cfg['api_key']}"},
                                         json_body={"from": sender, "to": [to], "subject": subject,
                                                    "text": text or None, "html": html or None})
                elif key == "sendgrid":
                    content = [{"type": "text/plain", "value": text or " "}]
                    if html:
                        content.append({"type": "text/html", "value": html})
                    r = await _post_json("https://api.sendgrid.com/v3/mail/send",
                                         {"Authorization": f"Bearer {cfg['api_key']}",
                                          "Content-Type": "application/json"},
                                         json_body={"personalizations": [{"to": [{"email": to}]}],
                                                    "from": {"email": sender}, "subject": subject,
                                                    "content": content})
                elif key == "mailgun":
                    r = await _post_json(f"https://api.mailgun.net/v3/{cfg.get('domain','')}/messages",
                                         {}, data={"from": sender, "to": to, "subject": subject,
                                                   "text": text, "html": html},
                                         auth=("api", cfg["api_key"]), form=True)
                else:  # postmark
                    r = await _post_json("https://api.postmarkapp.com/email",
                                         {"X-Postmark-Server-Token": cfg["api_key"],
                                          "Content-Type": "application/json"},
                                         json_body={"From": sender, "To": to, "Subject": subject,
                                                    "TextBody": text, "HtmlBody": html or None})
            except httpx.HTTPError as e:
                return ToolResult(False, f"{key}: {type(e).__name__}: {e}")
            ok = r.status_code < 400
            return ToolResult(ok, f"[{key}] {r.status_code} — ایمیل به {to} " + ("ارسال شد" if ok else "ارسال نشد: " + r.text[:300]),
                              {"provider": key, "status": r.status_code}, r.status_code)
        return ToolResult(False, "هیچ ارائه‌دهندهٔ ایمیلی ثبت نشده (resend/sendgrid/mailgun/postmark).")


class SmsSendTool(Tool):
    name = "sms_send"
    risk = "confirm"
    description = "Send an SMS using the user's own provider (twilio | kavenegar)."
    parameters = {
        "type": "object",
        "properties": {"to": {"type": "string"}, "text": {"type": "string"}, "provider": {"type": "string"}},
        "required": ["to", "text"],
    }

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        to, text = args.get("to") or "", args.get("text") or ""
        if not to or not text:
            return ToolResult(False, "to و text لازم است")
        for key in ([args["provider"].lower()] if args.get("provider") else ["twilio", "kavenegar"]):
            cfg = await _config(ctx.user_id, key)
            if not cfg:
                continue
            try:
                if key == "twilio":
                    sid = cfg["account_sid"]
                    r = await _post_json(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                                         {}, data={"To": to, "From": cfg.get("from", ""), "Body": text},
                                         auth=(sid, cfg["auth_token"]), form=True)
                else:  # kavenegar
                    r = await _post_json(f"https://api.kavenegar.com/v1/{cfg['api_key']}/sms/send.json",
                                         {}, data={"receptor": to, "sender": cfg.get("sender", ""), "message": text},
                                         form=True)
            except httpx.HTTPError as e:
                return ToolResult(False, f"{key}: {type(e).__name__}: {e}")
            ok = r.status_code < 400
            return ToolResult(ok, f"[{key}] {r.status_code}: " + (f"پیامک به {to} ارسال شد" if ok else r.text[:300]),
                              {"provider": key, "status": r.status_code}, r.status_code)
        return ToolResult(False, "هیچ ارائه‌دهندهٔ پیامکی ثبت نشده (twilio/kavenegar).")


class MessagingSendTool(Tool):
    name = "messaging_send"
    risk = "confirm"
    description = ("Post a message with the user's own bot: slack (channel id/name) | discord (channel id) | "
                   "telegram (chat id) | whatsapp (phone id).")
    parameters = {
        "type": "object",
        "properties": {"provider": {"type": "string"}, "channel": {"type": "string"},
                       "text": {"type": "string"}},
        "required": ["provider", "text"],
    }

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        key = (args.get("provider") or "").lower()
        text = args.get("text") or ""
        channel = args.get("channel") or ""
        cfg = await _config(ctx.user_id, key)
        if not cfg:
            return ToolResult(False, f"کلید «{key}» ثبت نشده. `sina token add {key}`")
        if not text:
            return ToolResult(False, "پارامتر text لازم است")
        try:
            if key == "slack":
                r = await _post_json("https://slack.com/api/chat.postMessage",
                                     {"Authorization": f"Bearer {cfg['bot_token']}"},
                                     json_body={"channel": channel or cfg.get("channel") or "#general", "text": text})
                data = r.json()
                return ToolResult(bool(data.get("ok")), f"Slack: {data.get('ok')} {data.get('error') or ''}".strip())
            if key == "discord":
                ch = channel or cfg.get("channel_id") or ""
                if not ch:
                    return ToolResult(False, "channel (شناسهٔ کانال دیسکورد) لازم است")
                r = await _post_json(f"https://discord.com/api/v10/channels/{ch}/messages",
                                     {"Authorization": f"Bot {cfg['bot_token']}"}, json_body={"content": text})
                ok = r.status_code < 400
                return ToolResult(ok, f"Discord {r.status_code}" + ("" if ok else f": {r.text[:200]}"))
            if key == "telegram":
                chat = channel or cfg.get("chat_id") or ""
                r = await _post_json(f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage",
                                     {}, json_body={"chat_id": chat, "text": text})
                ok = r.status_code < 400
                return ToolResult(ok, f"Telegram {r.status_code}" + ("" if ok else f": {r.text[:200]}"))
            if key == "whatsapp":
                phone = cfg.get("phone_id") or ""
                r = await _post_json(f"https://graph.facebook.com/v21.0/{phone}/messages",
                                     {"Authorization": f"Bearer {cfg['access_token']}"},
                                     json_body={"messaging_product": "whatsapp", "to": channel, "type": "text",
                                                "text": {"body": text}})
                ok = r.status_code < 400
                return ToolResult(ok, f"WhatsApp {r.status_code}" + ("" if ok else f": {r.text[:200]}"))
        except httpx.HTTPError as e:
            return ToolResult(False, f"خطای شبکه: {type(e).__name__}: {e}")
        return ToolResult(False, "provider پشتیبانی‌شده: slack | discord | telegram | whatsapp")


registry.register(HttpApiTool())
registry.register(LlmAskTool())
registry.register(SearchApiTool())
registry.register(EmailSendTool())
registry.register(SmsSendTool())
registry.register(MessagingSendTool())
