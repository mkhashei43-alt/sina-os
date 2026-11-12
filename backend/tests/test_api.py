"""API-level integration tests (auth, conversations, tasks, memory, system)."""
from __future__ import annotations

from tests.conftest import wait_task


async def test_me(app_client, auth):
    r = await app_client.get("/api/auth/me", headers=auth)
    assert r.status_code == 200 and r.json()["role"] == "owner"


async def test_conversation_flow(app_client, auth):
    c = (await app_client.post("/api/conversations", headers=auth, json={"title": "تست"})).json()
    r = await app_client.get(f"/api/conversations/{c['id']}/messages", headers=auth)
    assert r.status_code == 200 and r.json()["messages"] == []


async def test_task_lifecycle_mock(app_client, auth):
    r = await app_client.post("/api/tasks", headers=auth, json={"instruction": "سلام، یک تست کوتاه"})
    assert r.status_code == 200
    t = await wait_task(app_client, auth, r.json()["task"]["id"])
    assert t["status"] == "completed"
    assert t["steps"], "steps must be persisted"
    assert any(s["phase"] == "report" for s in t["steps"])


async def test_task_cancel(app_client, auth):
    r = await app_client.post("/api/tasks", headers=auth, json={"instruction": "python: یک برنامه بساز"})
    tid = r.json()["task"]["id"]
    c = await app_client.post(f"/api/tasks/{tid}/cancel", headers=auth)
    assert c.status_code == 200
    st = (await app_client.get(f"/api/tasks/{tid}", headers=auth)).json()["status"]
    assert st in ("cancelled", "completed", "failed")


async def test_task_requires_instruction(app_client, auth):
    r = await app_client.post("/api/tasks", headers=auth, json={"instruction": ""})
    assert r.status_code == 422


async def test_memory_crud_and_search(app_client, auth):
    r = await app_client.post("/api/memory", headers=auth, json={"content": "کاربر پروژه‌های پایتون را ترجیح می‌دهد", "kind": "preference"})
    assert r.status_code == 200
    mem_id = r.json()["id"]
    search = await app_client.get("/api/memory", headers=auth, params={"q": "پروژه پایتون"})
    assert any(m["id"] == mem_id for m in search.json())
    d = await app_client.delete(f"/api/memory/{mem_id}", headers=auth)
    assert d.status_code == 200


async def test_projects_and_workspace(app_client, auth):
    p = await app_client.post("/api/projects", headers=auth, json={"name": "فروشگاه", "description": "فروشگاه اینترنتی", "stack": ["python", "fastapi"]})
    assert p.status_code == 200 and p.json()["workspace_id"]
    lst = await app_client.get("/api/projects", headers=auth)
    assert any(x["name"] == "فروشگاه" for x in lst.json())


async def test_workspace_file_upload_and_read(app_client, auth):
    ws = (await app_client.post("/api/workspaces", headers=auth, json={"name": "upload-test"})).json()
    files = {"file": ("hello.txt", b"sina upload", "text/plain")}
    r = await app_client.post(f"/api/workspaces/{ws['id']}/upload", headers=auth, params={"path": "."}, files=files)
    assert r.status_code == 200
    rd = await app_client.get(f"/api/workspaces/{ws['id']}/file", headers=auth, params={"path": "hello.txt"})
    assert rd.json()["content"] == "sina upload"


async def test_chat_attachment_upload(app_client, auth):
    files = {"file": ("note.txt", b"hello", "text/plain")}
    r = await app_client.post("/api/uploads", headers=auth, files=files)
    assert r.status_code == 200 and r.json()["bytes"] == 5


async def test_system_stats_and_tools(app_client, auth):
    s = (await app_client.get("/api/system/stats", headers=auth)).json()
    assert "cpu" in s and "memory" in s and "disk" in s
    tools = (await app_client.get("/api/system/tools", headers=auth)).json()
    names = {t["name"] for t in tools}
    assert {"files", "terminal", "python_exec", "web_search"} <= names


async def test_usage_and_logs(app_client, auth):
    u = (await app_client.get("/api/usage/summary", headers=auth)).json()
    assert "totals" in u
    logs = (await app_client.get("/api/logs", headers=auth)).json()
    assert any(l["action"].startswith("auth.login") for l in logs)


async def test_integrations_never_leak_secret(app_client, auth):
    r = await app_client.post("/api/integrations", headers=auth, json={
        "kind": "github", "config": {"token": "ghp_supersecret_token", "owner": "me", "repo": "r"}, "enabled": True})
    assert r.status_code == 200
    lst = (await app_client.get("/api/integrations", headers=auth)).json()
    body = str(lst)
    assert "ghp_supersecret_token" not in body
    assert "token" in lst["github"]["fields_configured"]


async def test_approval_flow(app_client, auth):
    """A paused task with a pending high-risk call can be approved and resumes."""
    from app.db import SessionLocal
    from app.models import Approval, Task
    from sqlalchemy import select

    r = await app_client.post("/api/tasks", headers=auth, json={"instruction": "سلام"})
    tid = r.json()["task"]["id"]
    async with SessionLocal() as db:
        t = (await db.execute(select(Task).where(Task.id == tid))).scalar_one()
        t.status = "waiting_approval"
        t.state = {"task_id": tid, "instruction": t.instruction, "messages": [{"role": "user", "content": "x"}],
                   "pending_calls": [{"id": "c1", "name": "terminal", "arguments": {"command": "rm -rf ./tmp"}, "approved": False}],
                   "paused": True, "workspace": str(t.workspace_id), "user_id": t.user_id}
        ap = Approval(task_id=tid, user_id=t.user_id, kind="tool", description="تست", payload={"risk": "confirm"})
        db.add(ap)
        await db.commit()
        ap_id = ap.id
    d = await app_client.post(f"/api/tasks/{tid}/approvals/{ap_id}", headers=auth, json={"approve": True})
    assert d.status_code == 200
    assert d.json()["status"] == "queued"
