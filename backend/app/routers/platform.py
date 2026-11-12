"""Projects, memory, integrations, system monitor, settings, usage, logs, global events."""
from __future__ import annotations

import json
import os
import platform as pyplatform
import socket
import time
from datetime import datetime, timedelta, timezone

import psutil
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import audit
from ..config import get_settings
from ..crypto import decrypt_json, encrypt_json
from ..db import get_session
from ..deps import get_current_user, require_roles
from ..events import broker
from ..models import (
    AuditLog, Conversation, Integration, Memory, Message, ModelUsage, Project, Task, ToolCall, User, Workspace,
)
from ..providers import get_provider
from ..services.memory import remember
from ..tools import registry

router = APIRouter(tags=["platform"])
_settings = get_settings()


# ---------------------------------------------------------------- projects
class ProjectIn(BaseModel):
    name: str
    description: str = ""
    stack: list[str] = []


@router.get("/projects")
async def list_projects(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc()))).scalars().all()
    out = []
    for p in rows:
        tasks = (await db.execute(select(func.count()).select_from(Task).where(Task.project_id == p.id))).scalar()
        out.append({"id": p.id, "name": p.name, "description": p.description, "status": p.status,
                    "stack": p.stack, "workspace_id": p.workspace_id, "tasks": tasks, "created_at": p.created_at})
    return out


@router.post("/projects")
async def create_project(body: ProjectIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    slug = "".join(c.lower() if c.isalnum() else "-" for c in body.name)[:60].strip("-") or "project"
    p = Project(user_id=user.id, name=body.name, slug=slug, description=body.description, stack=body.stack)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    ws_path = _settings.workspace_path / "projects" / f"{slug}-{p.id[:6]}"
    ws_path.mkdir(parents=True, exist_ok=True)
    ws = Workspace(user_id=user.id, project_id=p.id, name=p.name, path=str(ws_path))
    db.add(ws)
    await db.commit()
    await db.refresh(ws)
    p.workspace_id = ws.id
    await db.commit()
    await remember(db, user_id=user.id, kind="project", project_id=p.id,
                   content=f"پروژه «{p.name}»: {body.description} | stack: {', '.join(body.stack)}", importance=0.8)
    return {"id": p.id, "name": p.name, "workspace_id": ws.id}


# ---------------------------------------------------------------- memory
class MemoryIn(BaseModel):
    content: str
    kind: str = "fact"
    project_id: str | None = None
    tags: list[str] = []


@router.get("/memory")
async def list_memory(q: str | None = None, kind: str | None = None, limit: int = 100,
                      user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    from ..services.memory import recall
    if q:
        items = await recall(db, user_id=user.id, query=q, limit=min(limit, 50), min_score=0.01)
        return [{"id": m.id, "kind": m.kind, "content": m.content, "tags": m.tags,
                 "importance": m.importance, "score": round(s, 3), "created_at": m.created_at} for s, m in items]
    query = select(Memory).where(Memory.user_id == user.id).order_by(Memory.created_at.desc()).limit(min(limit, 300))
    if kind:
        query = query.where(Memory.kind == kind)
    rows = (await db.execute(query)).scalars().all()
    return [{"id": m.id, "kind": m.kind, "content": m.content, "tags": m.tags, "project_id": m.project_id,
             "importance": m.importance, "has_embedding": bool(m.embedding), "created_at": m.created_at} for m in rows]


@router.post("/memory")
async def create_memory(body: MemoryIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    m = await remember(db, user_id=user.id, content=body.content, kind=body.kind,
                       project_id=body.project_id, tags=body.tags, source="user")
    return {"id": m.id}


@router.delete("/memory/{mem_id}")
async def delete_memory(mem_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    m = (await db.execute(select(Memory).where(Memory.id == mem_id, Memory.user_id == user.id))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "یادداشت یافت نشد")
    await db.delete(m)
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- integrations
SECRET_FIELDS = {"private_key", "password", "token", "api_token", "bot_token", "api_key",
                  "secret_key", "bearer_token", "auth_token", "access_token", "secret",
                  "consumer_secret", "client_secret", "app_password", "merchant_id"}

INTEGRATION_FIELDS = {
    "ssh": ["host", "port", "username", "private_key", "password", "allowed_hosts"],
    "github": ["token", "owner", "repo"],
    "cloudflare": ["api_token", "zone_id"],
    "telegram": ["bot_token", "chat_id"],
    "openrouter": ["api_key"],
    "search": ["provider", "api_key"],
}

INTEGRATION_CAPS = {
    "ssh": "اجرای دستور، آپلود/دانلود فایل و مدیریت سرویس روی سرور مجاز خودتان (تغییرات نیازمند تأیید)",
    "github": "ریپازیتوری، فایل، ایشو و Pull Request در گیت‌هاب",
    "cloudflare": "مدیریت رکوردهای DNS و پاک‌سازی کش دامنه‌های خودتان",
    "telegram": "ارسال پیام و فایل از طریق ربات تلگرام خودتان",
    "openrouter": "کلید OpenRouter خودتان (توکن‌ها از اعتبار شخصی شما کم می‌شود)",
    "search": "کلید جست‌وجوی وب جایگزین",
}


# --- اتصال‌های کتالوگی (توکن سرویس‌های بزرگ) ---
from ..integrations.catalog import CATALOG, CATEGORY_FA, catalog_list  # noqa: E402

INTEGRATION_FIELDS.update({k: v["fields"] for k, v in CATALOG.items()})
INTEGRATION_CAPS.update({k: f"{v['name']} — " + {
    "ai": "مدل/تولید محتوا", "search": "جست‌وجوی وب", "messaging": "ارسال پیام",
    "email": "ارسال ایمیل", "dev": "توسعه و استقرار", "infra": "سرور و زیرساخت",
    "productivity": "اسناد و تسک", "social": "شبکهٔ اجتماعی", "commerce": "فروش و پرداخت",
    "data": "داده و نقشه",
}.get(v["category"], "") for k, v in CATALOG.items()})


@router.get("/integrations/catalog")
async def integrations_catalog():
    """فهرست عمومی سرویس‌های پشتیبانی‌شده (بدون مقدار محرمانه)."""
    return {"categories": CATEGORY_FA, "providers": catalog_list(),
            "count": len(CATALOG)}


@router.get("/integrations")
async def list_integrations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(Integration).where(Integration.user_id == user.id))).scalars().all()
    out = {i.kind: {"id": i.id, "kind": i.kind, "name": i.name, "enabled": i.enabled,
                    "permissions": i.permissions, "configured": bool(i.config_enc),
                    "fields_configured": sorted(k for k in decrypt_json(i.config_enc) if k != "__meta__"),
                    "masked": {k: "••••••" for k in decrypt_json(i.config_enc) if k in SECRET_FIELDS},
                    "capabilities": INTEGRATION_CAPS.get(i.kind, ""),
                    "available_fields": INTEGRATION_FIELDS.get(i.kind, [])} for i in rows}
    for kind in INTEGRATION_FIELDS:
        out.setdefault(kind, {"kind": kind, "enabled": False, "configured": False, "fields_configured": [],
                              "available_fields": INTEGRATION_FIELDS[kind], "permissions": {},
                              "capabilities": INTEGRATION_CAPS.get(kind, "")})
    return out


class IntegrationIn(BaseModel):
    kind: str
    name: str = ""
    config: dict = {}
    enabled: bool = True
    permissions: dict = {}


@router.post("/integrations")
async def upsert_integration(body: IntegrationIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    if body.kind not in INTEGRATION_FIELDS:
        raise HTTPException(400, "نوع یکپارچه‌سازی پشتیبانی نمی‌شود")
    row = (await db.execute(select(Integration).where(Integration.user_id == user.id, Integration.kind == body.kind))).scalar_one_or_none()
    merged = dict(decrypt_json(row.config_enc)) if row else {}
    merged.update({k: v for k, v in body.config.items() if v not in (None, "")})
    if row:
        row.config_enc = encrypt_json(merged)
        row.name = body.name or row.name
        row.enabled = body.enabled
        row.permissions = body.permissions or row.permissions
    else:
        db.add(Integration(user_id=user.id, kind=body.kind, name=body.name or body.kind,
                           config_enc=encrypt_json(merged), enabled=body.enabled, permissions=body.permissions))
    await db.commit()
    await audit(db, user_id=user.id, action="integration.save", actor="web", target=body.kind,
                detail={"fields": sorted(k for k in merged)})
    return {"ok": True}


@router.delete("/integrations/{kind}")
async def delete_integration(kind: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = (await db.execute(select(Integration).where(Integration.user_id == user.id, Integration.kind == kind))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "یکپارچه‌سازی یافت نشد")
    await db.delete(row)
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- models & settings
@router.get("/models")
async def models(user: User = Depends(get_current_user)):
    prov = get_provider()
    info = {"provider": prov.name, "configured": bool(getattr(prov, "configured", False)),
            "default_model": _settings.default_model, "coding_model": _settings.coding_model,
            "reasoning_model": _settings.reasoning_model}
    catalog = []
    if getattr(prov, "configured", False) and hasattr(prov, "list_models"):
        try:
            catalog = (await prov.list_models())[:200]
        except Exception as e:
            info["error"] = f"دریافت فهرست مدل‌ها ناموفق: {e}"
    return {**info, "catalog": catalog}


class ModelSettingsIn(BaseModel):
    default_model: str | None = None
    coding_model: str | None = None
    reasoning_model: str | None = None


@router.post("/models")
async def set_models(body: ModelSettingsIn, user: User = Depends(require_roles("owner", "admin")),
                     db: AsyncSession = Depends(get_session)):
    us = dict(user.settings or {})
    models = dict(us.get("models") or {})
    for f in ("default_model", "coding_model", "reasoning_model"):
        v = getattr(body, f)
        if v:
            models[f] = v
    us["models"] = models
    user.settings = us
    await db.commit()
    await audit(db, user_id=user.id, action="settings.models", actor="web", detail=models)
    return {"ok": True, "models": models}


@router.get("/settings")
async def get_settings_view(user: User = Depends(get_current_user)):
    return {
        "app": {"name": _settings.app_name, "env": _settings.env},
        "models": {"default": (user.settings or {}).get("models", {}).get("default_model") or _settings.default_model,
                   "coding": (user.settings or {}).get("models", {}).get("coding_model") or _settings.coding_model,
                   "reasoning": (user.settings or {}).get("models", {}).get("reasoning_model") or _settings.reasoning_model},
        "limits": {"exec_timeout": _settings.exec_timeout_seconds, "max_upload_mb": _settings.max_upload_mb,
                   "max_agent_iterations": _settings.max_agent_iterations,
                   "max_tool_calls": _settings.max_tool_calls_per_task,
                   "approval_levels": sorted(_settings.approval_levels)},
        "pip_allowlist": sorted(_settings.pip_allow),
        "provider_configured": bool(_settings.openrouter_api_key),
        "telegram_configured": bool(_settings.telegram_bot_token),
    }


# ---------------------------------------------------------------- usage & logs
@router.get("/usage/summary")
async def usage_summary(days: int = 30, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (await db.execute(select(ModelUsage).where(ModelUsage.user_id == user.id, ModelUsage.created_at >= since))).scalars().all()
    by_model: dict[str, dict] = {}
    by_day: dict[str, dict] = {}
    for r in rows:
        m = by_model.setdefault(r.model, {"model": r.model, "calls": 0, "tokens_in": 0, "tokens_out": 0, "cost": 0.0})
        m["calls"] += 1; m["tokens_in"] += r.tokens_in; m["tokens_out"] += r.tokens_out; m["cost"] += r.cost_usd
        d = r.created_at.strftime("%Y-%m-%d")
        dd = by_day.setdefault(d, {"date": d, "cost": 0.0, "calls": 0})
        dd["cost"] += r.cost_usd; dd["calls"] += 1
    return {
        "totals": {"calls": len(rows), "tokens_in": sum(r.tokens_in for r in rows),
                   "tokens_out": sum(r.tokens_out for r in rows), "cost_usd": round(sum(r.cost_usd for r in rows), 4)},
        "by_model": sorted(by_model.values(), key=lambda x: -x["cost"]),
        "by_day": sorted(by_day.values(), key=lambda x: x["date"]),
    }


@router.get("/logs")
async def logs(limit: int = 200, action: str | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    q = select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.created_at.desc()).limit(min(limit, 500))
    if action:
        q = q.where(AuditLog.action.like(f"{action}%"))
    rows = (await db.execute(q)).scalars().all()
    return [{"id": a.id, "action": a.action, "actor": a.actor, "target": a.target, "detail": a.detail,
             "ip": a.ip, "created_at": a.created_at} for a in rows]


# ---------------------------------------------------------------- system monitor
@router.get("/system/health")
async def health():
    return {"status": "ok", "app": _settings.app_name, "time": datetime.now(timezone.utc).isoformat()}


@router.get("/system/stats")
async def stats(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    vm = psutil.virtual_memory()
    du = psutil.disk_usage(str(_settings.workspace_path))
    counts = {}
    for name, model in (("tasks", Task), ("conversations", Conversation), ("memories", Memory)):
        counts[name] = (await db.execute(select(func.count()).select_from(model).where(model.user_id == user.id))).scalar()
    running = (await db.execute(select(func.count()).select_from(Task).where(Task.user_id == user.id, Task.status == "running"))).scalar()
    listening: list[int] = []
    try:
        listening = sorted({c.laddr.port for c in psutil.net_connections(kind="inet") if c.status == psutil.CONN_LISTEN})[:30]
    except (psutil.AccessDenied, PermissionError):
        pass
    top = sorted(psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
                 key=lambda p: p.info.get("cpu_percent") or 0, reverse=True)[:8]
    # The API/worker deliberately have NO docker socket: code execution happens
    # inside the already-isolated worker container. Report it honestly.
    socket_present = os.path.exists("/var/run/docker.sock")
    docker_up = False
    if socket_present:
        try:
            import shutil as sht
            if sht.which("docker"):
                docker_up = os.system("docker info >/dev/null 2>&1") == 0
        except Exception:
            docker_up = False
    return {
        "host": {"hostname": socket.gethostname(), "os": f"{pyplatform.system()} {pyplatform.release()}",
                 "python": pyplatform.python_version(), "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 1)},
        "cpu": {"percent": psutil.cpu_percent(interval=None), "cores": psutil.cpu_count(), "load": os.getloadavg() if hasattr(os, "getloadavg") else []},
        "memory": {"percent": vm.percent, "used_gb": round(vm.used / 2**30, 2), "total_gb": round(vm.total / 2**30, 2)},
        "disk": {"percent": du.percent, "used_gb": round(du.used / 2**30, 2), "total_gb": round(du.total / 2**30, 2)},
        "docker": {
            "available": docker_up,
            "socket_mounted": socket_present,
            "isolation": "container" if not socket_present else "docker-socket",
            "note": ("اجرای کد داخل کانتینر ورکر (بدون سوکت داکر روی میزبان)" if not socket_present
                     else "ورکر به سوکت داکر دسترسی دارد"),
        },
        "counts": {**counts, "running_tasks": running},
        "ports": listening,
        "top_processes": [{"pid": p.info["pid"], "name": p.info["name"], "cpu": p.info["cpu_percent"],
                           "mem": round(p.info["memory_percent"] or 0, 1)} for p in top],
    }


@router.get("/system/tools")
async def tools_list(user: User = Depends(get_current_user)):
    return [{"name": t.name, "description": t.description, "risk": t.risk} for t in registry.all()]


# ---------------------------------------------------------------- global events
@router.get("/events")
async def global_events(request: Request, user: User = Depends(get_current_user)):
    async def gen():
        yield "event: ready\ndata: {}\n\n"
        async for ev in broker.subscribe(f"user:{user.id}", heartbeat=20.0):
            if await request.is_disconnected():
                break
            yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- web tools (used by Browser page)
@router.get("/web/search")
async def web_search_endpoint(q: str, limit: int = 8, user: User = Depends(get_current_user)):
    from ..tools.web import ddg_search
    try:
        results = await ddg_search(q, min(limit, 15))
    except Exception as e:
        raise HTTPException(502, f"جست‌وجو ناموفق: {e}")
    return {"query": q, "results": results}


@router.get("/web/fetch")
async def web_fetch_endpoint(url: str, user: User = Depends(get_current_user)):
    import httpx as _httpx
    from ..tools.web import extract_text
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "فقط http/https مجاز است")
    try:
        async with _httpx.AsyncClient(timeout=25, follow_redirects=True,
                                      headers={"User-Agent": "Mozilla/5.0 SinaAIOS/1.0"}) as c:
            r = await c.get(url)
            r.raise_for_status()
    except Exception as e:
        raise HTTPException(502, f"دریافت صفحه ناموفق: {e}")
    ctype = r.headers.get("content-type", "")
    if "html" in ctype:
        text, links = extract_text(r.text, 20000)
    else:
        text, links = r.text[:20000], []
    return {"url": str(r.url), "status": r.status_code, "content_type": ctype, "text": text, "links": links[:60]}
