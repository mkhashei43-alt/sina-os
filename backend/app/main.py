"""Sina AI OS — FastAPI application."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from .audit import setup_logging
from .config import get_settings
from .db import SessionLocal, init_db
from .events import broker
from .models import User
from .routers import admin, auth, billing, chat, platform, public, tasks, workspaces
from .security import hash_password

setup_logging()
log = logging.getLogger("sina.api")
_settings = get_settings()


async def seed_admin() -> None:
    """اکانت مالک + مستأجر پیش‌فرض (نسخهٔ شخصی هم یک مشتری از همان پلتفرم است)."""
    from .models import Tenant
    from .services.tenancy import slugify

    async with SessionLocal() as db:
        existing = (await db.execute(
            select(User).where(User.email == _settings.admin_email.lower()))).scalar_one_or_none()
        if not existing and _settings.seed_admin:
            existing = User(email=_settings.admin_email.lower(),
                            password_hash=hash_password(_settings.admin_password),
                            name="مدیر سیستم", role="owner")
            db.add(existing)
            await db.flush()
            log.warning("seeded owner account %s — change the password immediately", _settings.admin_email)
        if existing and not existing.tenant_id:
            tenant = Tenant(name="حساب اصلی", slug=slugify("main"), plan="business", status="active",
                            owner_user_id=existing.id, notes="مستأجر پیش‌فرض نصب")
            db.add(tenant)
            await db.flush()
            existing.tenant_id = tenant.id
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_admin()
    await broker.start()
    worker_task = None
    if _settings.env != "prod" or __import__("os").getenv("SINA_EMBEDDED_WORKER") == "1":
        from .worker import scheduler_loop, worker_loop
        stop = asyncio.Event()
        worker_task = asyncio.create_task(worker_loop(stop))
        app.state._sched = asyncio.create_task(scheduler_loop(stop))
        app.state._stop = stop
        log.info("embedded agent worker started")
    try:
        yield
    finally:
        if worker_task:
            app.state._stop.set()
            worker_task.cancel()
            app.state._sched.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker_task
        await broker.stop()


app = FastAPI(title="Sina AI OS API", version="1.0.0", lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, public.router, billing.router, admin.router, chat.router, tasks.router,
          workspaces.router, workspaces.uploads_router, platform.router):
    app.include_router(r, prefix=_settings.api_prefix)


# ---------------------------------------------------------------- کنسول داخلی
_CONSOLE = Path(__file__).resolve().parent / "static" / "console.html"


@app.get("/", include_in_schema=False)
async def console_home():
    from fastapi.responses import FileResponse, HTMLResponse
    if _settings.serve_console and _CONSOLE.exists():
        return FileResponse(_CONSOLE, media_type="text/html")
    return HTMLResponse("<h3>Sina OS API</h3><p><a href='/api/docs'>/api/docs</a></p>")


@app.get("/console", include_in_schema=False)
async def console_alias():
    return await console_home()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sina-api", "version": "1.0.0"}


@app.get("/api/health")
async def api_health():
    db_ok = True
    try:
        async with SessionLocal() as db:
            await db.execute(select(User.id).limit(1))
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "db": db_ok,
            "provider": "openrouter" if _settings.openrouter_api_key else "mock",
            "env": _settings.env}


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "خطای داخلی سرور"})
