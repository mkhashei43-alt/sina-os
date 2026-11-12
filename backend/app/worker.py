"""Agent worker: durable task queue on the database + recovery + scheduler.

Run standalone (docker service `worker`) or embedded in the API via SINA_EMBEDDED_WORKER=1.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .agent.runner import get_runner
from .config import get_settings
from .db import SessionLocal, init_db
from .events import broker
from .models import ScheduledJob, Task
from .audit import setup_logging
from .utils import aware

log = logging.getLogger("sina.worker")
POLL_INTERVAL = 1.5
STALE_AFTER = timedelta(minutes=3)


async def recover_stale_tasks() -> int:
    """Requeue tasks whose worker died mid-run (heartbeat too old)."""
    cutoff = datetime.now(timezone.utc) - STALE_AFTER
    async with SessionLocal() as db:
        rows = (await db.execute(select(Task).where(Task.status == "running"))).scalars().all()
        n = 0
        for t in rows:
            hb = aware(t.heartbeat_at)
            if hb is None or hb < cutoff:
                t.status = "queued"
                t.error = "recovered after worker restart"
                n += 1
        await db.commit()
    if n:
        log.warning("recovered %s stale task(s)", n)
    return n


async def claim_next() -> str | None:
    async with SessionLocal() as db:
        task = (await db.execute(
            select(Task).where(Task.status == "queued").order_by(Task.created_at).limit(1)
        )).scalar_one_or_none()
        if not task:
            return None
        task.status = "running"
        task.heartbeat_at = datetime.now(timezone.utc)
        await db.commit()
        return task.id


async def heartbeat(task_id: str) -> None:
    async with SessionLocal() as db:
        t = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
        if t:
            t.heartbeat_at = datetime.now(timezone.utc)
            await db.commit()


async def _run_with_heartbeat(task_id: str) -> None:
    hb_task = asyncio.create_task(_heartbeat_loop(task_id))
    try:
        runner = get_runner()
        await runner.run(task_id)
    except Exception as e:
        log.exception("task %s crashed in worker", task_id)
        async with SessionLocal() as db:
            t = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
            if t and t.status in ("running", "queued"):
                t.status = "failed"
                t.error = f"worker crash: {type(e).__name__}: {e}"[:2000]
                await db.commit()
    finally:
        hb_task.cancel()


async def _heartbeat_loop(task_id: str) -> None:
    while True:
        await asyncio.sleep(15)
        try:
            await heartbeat(task_id)
        except Exception:
            pass


async def worker_loop(stop: asyncio.Event) -> None:
    log.info("agent worker started")
    await recover_stale_tasks()
    while not stop.is_set():
        try:
            task_id = await claim_next()
            if task_id:
                log.info("running task %s", task_id)
                await _run_with_heartbeat(task_id)
                continue
        except Exception:
            log.exception("worker iteration failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=POLL_INTERVAL)
        except asyncio.TimeoutError:
            pass
    log.info("agent worker stopped")


async def scheduler_loop(stop: asyncio.Event) -> None:
    """Minimal cron-ish scheduler (every minute) for enabled scheduled_jobs."""
    while not stop.is_set():
        try:
            async with SessionLocal() as db:
                jobs = (await db.execute(select(ScheduledJob).where(ScheduledJob.enabled == True))).scalars().all()  # noqa: E712
                now = datetime.now(timezone.utc)
                for job in jobs:
                    due = aware(job.last_run_at) is None or (now - aware(job.last_run_at)) >= timedelta(hours=1)
                    if due:
                        db.add(Task(user_id=job.user_id, title=f"scheduled: {job.name}", instruction=job.instruction,
                                    kind="chat", status="queued", channel="scheduler"))
                        job.last_run_at = now
                        job.last_status = "queued"
                await db.commit()
        except Exception:
            log.exception("scheduler failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass


async def main() -> None:
    setup_logging()
    await init_db()
    await broker.start()
    stop = asyncio.Event()

    def _stop(*_):
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass
    await asyncio.gather(worker_loop(stop), scheduler_loop(stop))
    await broker.stop()


if __name__ == "__main__":
    asyncio.run(main())
