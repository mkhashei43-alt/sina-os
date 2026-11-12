"""Test bootstrap: isolated sqlite DB + workspace + mock LLM, in-process app."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

TMP = tempfile.mkdtemp(prefix="sina-test-")
os.environ.update({
    "ENV": "test",
    "SINA_LLM": "mock",
    "DATABASE_URL": f"sqlite+aiosqlite:///{TMP}/test.db",
    "WORKSPACE_ROOT": f"{TMP}/sina-ai",
    "JWT_SECRET": "test-secret-0123456789abcdef0123456789",
    "ADMIN_EMAIL": "admin@sina.local",
    "ADMIN_PASSWORD": "admin123!change",
    "EXEC_TIMEOUT_SECONDS": "60",
    "RATE_LIMIT_SIGNUP_PER_MIN": "1000",
    "PLATFORM_ADMIN_EMAILS": "admin@sina.local",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def app_client():
    from app.main import app

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def token(app_client) -> str:
    r = await app_client.post("/api/auth/login", json={"email": "admin@sina.local", "password": "admin123!change"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def auth(token) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def wait_task(client, auth, task_id: str, timeout: float = 120.0) -> dict:
    import time
    start = time.time()
    while time.time() - start < timeout:
        r = await client.get(f"/api/tasks/{task_id}", headers=auth)
        d = r.json()
        if d["status"] in ("completed", "failed", "cancelled", "waiting_approval"):
            return d
        await asyncio.sleep(0.4)
    return (await client.get(f"/api/tasks/{task_id}", headers=auth)).json()
