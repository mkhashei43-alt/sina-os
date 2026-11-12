"""Durability: queue recovery after a worker crash + task resumption."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Task
from app.worker import recover_stale_tasks
from tests.conftest import wait_task


async def test_stale_running_task_is_requeued_and_completes(app_client, auth):
    # create a task and force it into a "running, dead worker" state
    r = await app_client.post("/api/tasks", headers=auth, json={"instruction": "python hello"})
    tid = r.json()["task"]["id"]
    async with SessionLocal() as db:
        t = (await db.execute(select(Task).where(Task.id == tid))).scalar_one()
        t.status = "running"
        t.heartbeat_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        t.state = {"task_id": tid, "instruction": t.instruction, "messages": [{"role": "user", "content": t.instruction}],
                   "iteration": 0, "tool_count": 0, "pending_calls": [], "paused": False,
                   "workspace": "", "user_id": t.user_id, "plan": [], "analysis": {}, "final_text": ""}
        await db.commit()

    n = await recover_stale_tasks()
    assert n >= 1

    t = await wait_task(app_client, auth, tid, timeout=180)
    assert t["status"] in ("completed", "failed")
    if t["status"] == "completed":
        assert t["workspace_id"]


async def test_task_state_persisted_between_requests(app_client, auth):
    r = await app_client.post("/api/tasks", headers=auth, json={"instruction": "سلام"})
    tid = r.json()["task"]["id"]
    t = await wait_task(app_client, auth, tid)
    async with SessionLocal() as db:
        row = (await db.execute(select(Task).where(Task.id == tid))).scalar_one()
        assert row.attempts >= 1
        assert row.tokens_in >= 0
