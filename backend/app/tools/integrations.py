"""ابزارهای اتصال خارجی: SSH، GitHub، Cloudflare، تلگرام.

هر ابزار کلیدهای *خودِ همان مشتری* را از جدول integrations (رمزنگاری‌شده)
می‌خواند؛ هیچ کلید مشترکی بین مستأجرها وجود ندارد. عملیات تغییردهنده risk=confirm
دارند و تا تأیید صریح کاربر اجرا نمی‌شوند.
"""
from __future__ import annotations

import asyncio
import base64
import tempfile
from pathlib import Path

import httpx
from sqlalchemy import select

from ..config import get_settings
from ..crypto import decrypt_json
from ..db import SessionLocal
from ..models import Integration
from ..security import sanitize_output
from .base import Tool, ToolContext, ToolResult, registry

_settings = get_settings()


async def _config(user_id: str, kind: str) -> dict | None:
    async with SessionLocal() as db:
        row = (await db.execute(
            select(Integration).where(Integration.user_id == user_id, Integration.kind == kind,
                                      Integration.enabled == True)  # noqa: E712
        )).scalar_one_or_none()
        return decrypt_json(row.config_enc) if row else None


# ---------------------------------------------------------------- SSH
class SSHTool(Tool):
    name = "ssh"
    risk = "confirm"
    description = (
        "Run a shell command or transfer a file on the customer's own authorized server over SSH. "
        "Operations: exec (run command), upload (write a text file on the server), download (read a text file), "
        "service (systemctl status|restart|start|stop <name>). Write/destructive commands require human approval."
    )
    parameters = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["exec", "upload", "download", "service"], "default": "exec"},
            "command": {"type": "string", "description": "shell command for exec"},
            "path": {"type": "string", "description": "remote file path for upload/download"},
            "content": {"type": "string", "description": "file body for upload"},
            "service": {"type": "string", "description": "systemd unit name, e.g. nginx"},
            "action": {"type": "string", "enum": ["status", "restart", "start", "stop"], "default": "status"},
            "host": {"type": "string", "description": "optional host override (must be in the allowlist)"},
        },
        "required": [],
    }

    async def _run_ssh(self, cfg: dict, remote_cmd: str, timeout: int, stdin_data: bytes | None = None):
        host = cfg["host"]
        port = str(cfg.get("port") or 22)
        user = cfg.get("username") or "root"
        allowed = {h.strip() for h in str(cfg.get("allowed_hosts") or "").split(",") if h.strip()}
        if allowed and host not in allowed:
            return None, None, -1
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes",
                   "-o", "ConnectTimeout=15", "-p", port]
        key_path = None
        if cfg.get("private_key"):
            tf = tempfile.NamedTemporaryFile("w", suffix=".key", delete=False)
            tf.write(cfg["private_key"])
            tf.close()
            Path(tf.name).chmod(0o600)
            key_path = tf.name
            ssh_cmd += ["-i", key_path]
        ssh_cmd += [f"{user}@{host}", remote_cmd]
        try:
            proc = await asyncio.create_subprocess_exec(
                *ssh_cmd, stdin=asyncio.subprocess.PIPE if stdin_data else None,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            try:
                out, err = await asyncio.wait_for(proc.communicate(input=stdin_data), timeout)
            except asyncio.TimeoutError:
                proc.kill()
                return None, None, -2
            return out, err, proc.returncode
        except FileNotFoundError:
            return None, "کلاینت ssh روی این سرور نصب نیست".encode(), -3
        finally:
            if key_path:
                Path(key_path).unlink(missing_ok=True)

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        cfg = await _config(ctx.user_id, "ssh")
        if not cfg or not cfg.get("host"):
            return ToolResult(False, "اتصال SSH پیکربندی نشده است. در صفحه «یکپارچه‌سازی» میزبان و کلید را ثبت کنید.")
        if args.get("host") and args["host"] != cfg["host"]:
            return ToolResult(False, "اجرای دستور روی میزبان دیگر مجاز نیست؛ ابتدا اتصال را در تنظیمات ثبت کنید.")
        op = args.get("operation") or "exec"
        timeout = min(ctx.timeout, 90)

        if op == "exec":
            cmd = (args.get("command") or "").strip()
            if not cmd:
                return ToolResult(False, "پارامتر command لازم است")
            out, err, code = await self._run_ssh(cfg, cmd, timeout)
        elif op == "service":
            svc = (args.get("service") or "").strip()
            act = args.get("action") or "status"
            if not svc or not svc.replace("-", "").replace("_", "").replace(".", "").isalnum():
                return ToolResult(False, "نام سرویس نامعتبر است")
            cmd = {"status": f"systemctl status --no-pager -n 30 {svc}",
                   "restart": f"systemctl restart {svc} && systemctl is-active {svc}",
                   "start": f"systemctl start {svc} && systemctl is-active {svc}",
                   "stop": f"systemctl stop {svc} && echo stopped"}[act]
            out, err, code = await self._run_ssh(cfg, cmd, timeout)
        elif op == "upload":
            path, content = args.get("path") or "", args.get("content") or ""
            if not path:
                return ToolResult(False, "پارامتر path لازم است")
            b64 = base64.b64encode(content.encode()).decode()
            out, err, code = await self._run_ssh(cfg, f"mkdir -p \"$(dirname '{path}')\" && printf %s '{b64}' | base64 -d > '{path}' && wc -c < '{path}'", timeout)
        elif op == "download":
            path = args.get("path") or ""
            if not path:
                return ToolResult(False, "پارامتر path لازم است")
            out, err, code = await self._run_ssh(cfg, f"base64 -w0 '{path}'", timeout)
            if code == 0 and out:
                try:
                    text = base64.b64decode(out).decode(errors="replace")
                    return ToolResult(True, sanitize_output(text)[:60000], {"host": cfg["host"], "path": path}, 0)
                except Exception:
                    return ToolResult(False, "رمزگشایی محتوا ناموفق بود")
        else:
            return ToolResult(False, "عملیات ناشناخته")

        if code == -1:
            return ToolResult(False, "این میزبان در فهرست مجاز نیست")
        if code == -2:
            return ToolResult(False, "⏱ اجرای دستور SSH از حد زمان فراتر رفت")
        text = sanitize_output((out or b"").decode(errors="replace") + (("\n" + err.decode(errors="replace")) if err else ""))
        data = {"host": cfg["host"], "operation": op}
        if op == "upload":
            data["bytes"] = int(text.strip() or 0)
        return ToolResult(code == 0, text[:20000], data, code)


# ---------------------------------------------------------------- GitHub
class GitHubTool(Tool):
    name = "github"
    risk = "confirm"
    description = (
        "Manage the customer's GitHub with their own token. Operations: list_repos, repo_info, list_files, "
        "read_file, create_or_update_file, list_issues, create_issue, list_prs, create_pr, create_repo, branches."
    )
    parameters = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": [
                "list_repos", "repo_info", "list_files", "read_file", "create_or_update_file",
                "list_issues", "create_issue", "list_prs", "create_pr", "create_repo", "branches"]},
            "repo": {"type": "string", "description": "owner/name"},
            "path": {"type": "string"},
            "content": {"type": "string"},
            "message": {"type": "string"},
            "branch": {"type": "string", "default": "main"},
            "head": {"type": "string", "description": "source branch for PR"},
            "base": {"type": "string", "description": "target branch for PR", "default": "main"},
            "title": {"type": "string"},
            "body": {"type": "string"},
            "name": {"type": "string", "description": "repo name for create_repo"},
            "private": {"type": "boolean", "default": True},
        },
        "required": ["operation"],
    }

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        cfg = await _config(ctx.user_id, "github")
        if not cfg or not cfg.get("token"):
            return ToolResult(False, "اتصال GitHub پیکربندی نشده است.")
        hdr = {"Authorization": f"Bearer {cfg['token']}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
        repo = args.get("repo") or (f"{cfg.get('owner')}/{cfg.get('repo')}" if cfg.get("repo") else "")
        api = "https://api.github.com"
        op = args["operation"]
        async with httpx.AsyncClient(timeout=40, headers=hdr) as c:
            try:
                if op == "list_repos":
                    r = await c.get(f"{api}/user/repos", params={"per_page": 50, "sort": "updated"})
                    r.raise_for_status()
                    return ToolResult(True, "\n".join(
                        f"{x['full_name']} ({'private' if x['private'] else 'public'}, {x['default_branch']})"
                        for x in r.json()))
                if op == "create_repo":
                    name = args.get("name") or ""
                    if not name:
                        return ToolResult(False, "نام ریپازیتوری لازم است")
                    r = await c.post(f"{api}/user/repos", json={"name": name, "private": bool(args.get("private", True)),
                                                                "description": args.get("body") or ""})
                    r.raise_for_status()
                    d = r.json()
                    return ToolResult(True, f"ریپازیتوری ساخته شد: {d['full_name']}\n{d['html_url']}", d)
                if not repo:
                    return ToolResult(False, "پارامتر repo لازم است (owner/name)")
                if op == "repo_info":
                    r = await c.get(f"{api}/repos/{repo}")
                    r.raise_for_status(); d = r.json()
                    return ToolResult(True, f"{d['full_name']}\nstars={d['stargazers_count']} branch={d['default_branch']}\n{d.get('description') or ''}")
                if op == "branches":
                    r = await c.get(f"{api}/repos/{repo}/branches", params={"per_page": 50})
                    r.raise_for_status()
                    return ToolResult(True, "\n".join(x["name"] for x in r.json()))
                if op == "list_files":
                    r = await c.get(f"{api}/repos/{repo}/contents/{args.get('path', '')}",
                                    params={"ref": args.get("branch", "main")})
                    r.raise_for_status()
                    return ToolResult(True, "\n".join(f"{x['type']:5} {x['path']}" for x in r.json()))
                if op == "read_file":
                    r = await c.get(f"{api}/repos/{repo}/contents/{args.get('path', '')}",
                                    params={"ref": args.get("branch", "main")})
                    r.raise_for_status(); d = r.json()
                    return ToolResult(True, base64.b64decode(d["content"]).decode(errors="replace")[:20000])
                if op == "create_or_update_file":
                    path = args.get("path") or ""
                    if not path:
                        return ToolResult(False, "مسیر فایل لازم است")
                    sha = None
                    existing = await c.get(f"{api}/repos/{repo}/contents/{path}",
                                           params={"ref": args.get("branch", "main")})
                    if existing.status_code == 200:
                        sha = existing.json().get("sha")
                    body = {"message": args.get("message") or f"update {path}",
                            "content": base64.b64encode((args.get("content") or "").encode()).decode(),
                            "branch": args.get("branch", "main")}
                    if sha:
                        body["sha"] = sha
                    r = await c.put(f"{api}/repos/{repo}/contents/{path}", json=body)
                    r.raise_for_status()
                    return ToolResult(True, f"کامیت انجام شد: {path}", r.json())
                if op == "list_issues":
                    r = await c.get(f"{api}/repos/{repo}/issues", params={"state": "open", "per_page": 30})
                    r.raise_for_status()
                    return ToolResult(True, "\n".join(f"#{i['number']} {i['title']}" for i in r.json()))
                if op == "create_issue":
                    r = await c.post(f"{api}/repos/{repo}/issues",
                                     json={"title": args.get("title") or "issue", "body": args.get("body") or ""})
                    r.raise_for_status(); d = r.json()
                    return ToolResult(True, f"ایشو #{d['number']} ساخته شد: {d['html_url']}", d)
                if op == "list_prs":
                    r = await c.get(f"{api}/repos/{repo}/pulls", params={"state": "open", "per_page": 30})
                    r.raise_for_status()
                    return ToolResult(True, "\n".join(f"#{p['number']} {p['title']} ({p['head']['ref']}→{p['base']['ref']})"
                                                      for p in r.json()))
                if op == "create_pr":
                    r = await c.post(f"{api}/repos/{repo}/pulls", json={
                        "title": args.get("title") or "PR", "body": args.get("body") or "",
                        "head": args.get("head") or "feature", "base": args.get("base") or "main"})
                    r.raise_for_status(); d = r.json()
                    return ToolResult(True, f"Pull Request #{d['number']}: {d['html_url']}", d)
            except httpx.HTTPStatusError as e:
                return ToolResult(False, f"GitHub API {e.response.status_code}: {e.response.text[:300]}")
        return ToolResult(False, "عملیات ناشناخته")


# ---------------------------------------------------------------- Cloudflare
class CloudflareTool(Tool):
    name = "cloudflare"
    risk = "confirm"
    description = (
        "Manage the customer's Cloudflare zone with their token. Operations: list_zones, list_dns, create_dns, "
        "update_dns, delete_dns, purge_cache. DNS changes and cache purge need approval."
    )
    parameters = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["list_zones", "list_dns", "create_dns", "update_dns",
                                                     "delete_dns", "purge_cache"]},
            "zone": {"type": "string", "description": "zone name or id (defaults to configured zone)"},
            "type": {"type": "string", "description": "A|AAAA|CNAME|TXT|MX|NS"},
            "name": {"type": "string", "description": "record name e.g. app.example.com"},
            "content": {"type": "string", "description": "target IP or hostname"},
            "ttl": {"type": "integer", "default": 1},
            "proxied": {"type": "boolean", "default": True},
            "record_id": {"type": "string"},
        },
        "required": ["operation"],
    }

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        cfg = await _config(ctx.user_id, "cloudflare")
        if not cfg or not cfg.get("api_token"):
            return ToolResult(False, "اتصال Cloudflare پیکربندی نشده است.")
        hdr = {"Authorization": f"Bearer {cfg['api_token']}", "Content-Type": "application/json"}
        api = "https://api.cloudflare.com/client/v4"
        zone = cfg.get("zone_id")
        op = args["operation"]
        try:
            async with httpx.AsyncClient(timeout=40, headers=hdr) as c:
                if op == "list_zones":
                    r = await c.get(f"{api}/zones", params={"per_page": 50})
                    r.raise_for_status()
                    return ToolResult(True, "\n".join(f"{z['name']} — {z['id']}" for z in r.json().get("result", [])))
                if not zone:
                    return ToolResult(False, "zone_id در تنظیمات Cloudflare ثبت نشده است")
                base = f"{api}/zones/{zone}/dns_records"
                if op == "list_dns":
                    r = await c.get(base, params={"per_page": 100})
                    r.raise_for_status()
                    return ToolResult(True, "\n".join(
                        f"{x['id']}  {x['type']} {x['name']} → {x['content']} (proxied={x.get('proxied')})"
                        for x in r.json().get("result", [])))
                if op == "create_dns":
                    if not (args.get("name") and args.get("content")):
                        return ToolResult(False, "name و content لازم است")
                    body = {"type": args.get("type") or "A", "name": args["name"], "content": args["content"],
                            "ttl": int(args.get("ttl") or 1), "proxied": bool(args.get("proxied", True))}
                    r = await c.post(base, json=body)
                    r.raise_for_status()
                    d = r.json()["result"]
                    return ToolResult(True, f"رکورد ساخته شد: {d['type']} {d['name']} → {d['content']}", d)
                if op == "update_dns":
                    if not args.get("record_id"):
                        return ToolResult(False, "record_id لازم است")
                    body = {"type": args.get("type") or "A", "name": args["name"], "content": args["content"],
                            "ttl": int(args.get("ttl") or 1), "proxied": bool(args.get("proxied", True))}
                    r = await c.put(f"{base}/{args['record_id']}", json=body)
                    r.raise_for_status()
                    return ToolResult(True, "رکورد به‌روزرسانی شد", r.json()["result"])
                if op == "delete_dns":
                    if not args.get("record_id"):
                        return ToolResult(False, "record_id لازم است")
                    r = await c.delete(f"{base}/{args['record_id']}")
                    r.raise_for_status()
                    return ToolResult(True, "رکورد حذف شد")
                if op == "purge_cache":
                    r = await c.post(f"{api}/zones/{zone}/purge_cache", json={"purge_everything": True})
                    r.raise_for_status()
                    return ToolResult(True, "کش Cloudflare پاک شد")
        except httpx.HTTPStatusError as e:
            return ToolResult(False, f"Cloudflare API {e.response.status_code}: {e.response.text[:300]}")
        return ToolResult(False, "عملیات ناشناخته")


# ---------------------------------------------------------------- Telegram (customer's own bot)
class TelegramTool(Tool):
    name = "telegram"
    risk = "confirm"
    description = (
        "Send messages/files through the customer's own Telegram bot and read recent updates. "
        "Operations: send_message, send_file (workspace path), get_me, get_updates, set_chat."
    )
    parameters = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["send_message", "send_file", "get_me", "get_updates"]},
            "chat_id": {"type": "string", "description": "numeric chat id or @channel; defaults to saved chat"},
            "text": {"type": "string"},
            "path": {"type": "string", "description": "workspace-relative file path for send_file"},
            "parse_mode": {"type": "string", "enum": ["Markdown", "HTML", ""], "default": ""},
        },
        "required": ["operation"],
    }

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        cfg = await _config(ctx.user_id, "telegram")
        if not cfg or not cfg.get("bot_token"):
            return ToolResult(False, "اتصال تلگرام پیکربندی نشده است (توکن ربات خودتان را در تنظیمات ثبت کنید).")
        token = cfg["bot_token"]
        api = f"https://api.telegram.org/bot{token}"
        op = args["operation"]
        chat_id = str(args.get("chat_id") or cfg.get("chat_id") or "")
        try:
            async with httpx.AsyncClient(timeout=45) as c:
                if op == "get_me":
                    r = await c.get(f"{api}/getMe")
                    r.raise_for_status(); d = r.json()["result"]
                    return ToolResult(True, f"@{d.get('username')} (id={d.get('id')})", d)
                if op == "get_updates":
                    r = await c.get(f"{api}/getUpdates", params={"limit": 20})
                    r.raise_for_status()
                    out = []
                    for u in r.json().get("result", []):
                        msg = u.get("message") or {}
                        out.append(f"{msg.get('chat', {}).get('id')}: {msg.get('from', {}).get('first_name', '')} — {(msg.get('text') or '')[:120]}")
                    return ToolResult(True, "\n".join(out) or "به‌روزرسانی جدیدی نیست")
                if not chat_id:
                    return ToolResult(False, "chat_id لازم است (یک‌بار در تنظیمات ذخیره کنید)")
                if op == "send_message":
                    body = {"chat_id": chat_id, "text": args.get("text") or ""}
                    if args.get("parse_mode"):
                        body["parse_mode"] = args["parse_mode"]
                    r = await c.post(f"{api}/sendMessage", json=body)
                    r.raise_for_status()
                    return ToolResult(True, "پیام تلگرام ارسال شد", r.json().get("result", {}))
                if op == "send_file":
                    rel = (args.get("path") or "").lstrip("/")
                    fp = (ctx.workspace_root / rel).resolve()
                    root = ctx.workspace_root.resolve()
                    if not str(fp).startswith(str(root)) or not fp.is_file():
                        return ToolResult(False, "فایل در فضای‌کار یافت نشد")
                    if fp.stat().st_size > 45 * 1024 * 1024:
                        return ToolResult(False, "حجم فایل بیش از حد مجاز تلگرام (۴۵ مگابایت) است")
                    with open(fp, "rb") as fh:
                        r = await c.post(f"{api}/sendDocument", data={"chat_id": chat_id},
                                         files={"document": (fp.name, fh)})
                    r.raise_for_status()
                    return ToolResult(True, f"فایل {fp.name} ارسال شد")
        except httpx.HTTPStatusError as e:
            return ToolResult(False, f"Telegram API {e.response.status_code}: {e.response.text[:300]}")
        return ToolResult(False, "عملیات ناشناخته")


registry.register(SSHTool())
registry.register(GitHubTool())
registry.register(CloudflareTool())
registry.register(TelegramTool())
