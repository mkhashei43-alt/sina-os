"""Tasks: create, list, inspect, cancel, approve, live event stream."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import audit
from ..db import get_session
from ..deps import get_current_user
from ..events import broker
from ..models import Approval, Conversation, Message, Task, TaskStep, ToolCall, ToolResult, User
from ..services.tenancy import enforce_task_quota

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskIn(BaseModel):
    instruction: str = Field(min_length=1, max_length=20000)
    conversation_id: str | None = None
    project_id: str | None = None
    channel: str = "web"


def task_dict(t: Task) -> dict:
    return {
        "id": t.id, "title": t.title or t.instruction[:80], "instruction": t.instruction,
        "kind": t.kind, "status": t.status, "risk": t.risk, "plan": t.plan or [],
        "result": t.result, "error": t.error, "channel": t.channel,
        "conversation_id": t.conversation_id, "project_id": t.project_id,
        "workspace_id": t.workspace_id, "tokens_in": t.tokens_in, "tokens_out": t.tokens_out,
        "cost_usd": t.cost_usd, "created_at": t.created_at, "updated_at": t.updated_at,
        "finished_at": t.finished_at,
    }


@router.post("")
async def create_task(body: TaskIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await enforce_task_quota(db, user)
    conv_id = body.conversation_id
    if conv_id:
        conv = (await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id))).scalar_one_or_none()
        if not conv:
            raise HTTPException(404, "گفت‌وگو یافت نشد")
    else:
        conv = Conversation(user_id=user.id, title=body.instruction[:60], project_id=body.project_id, channel=body.channel)
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        conv_id = conv.id
    db.add(Message(conversation_id=conv_id, role="user", content=body.instruction))
    task = Task(user_id=user.id, conversation_id=conv_id, project_id=body.project_id,
                title=body.instruction[:80], instruction=body.instruction,
                kind="chat", status="queued", channel=body.channel)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await audit(db, user_id=user.id, action="task.create", actor=body.channel, target=task.id,
                detail={"instruction": body.instruction[:200]})
    await broker.publish(f"task:{task.id}", "task.created", {"task_id": task.id, "status": "queued"})
    await broker.publish(f"user:{user.id}", "task.created", {"task_id": task.id, "status": "queued"})
    return {"task": task_dict(task), "conversation_id": conv_id}


@router.get("")
async def list_tasks(status: str | None = None, limit: int = 50, user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_session)):
    q = select(Task).where(Task.user_id == user.id).order_by(Task.created_at.desc()).limit(min(limit, 200))
    if status:
        q = q.where(Task.status == status)
    rows = (await db.execute(q)).scalars().all()
    return [task_dict(t) for t in rows]


@router.get("/{task_id}")
async def get_task(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    t = (await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "کار یافت نشد")
    steps = (await db.execute(select(TaskStep).where(TaskStep.task_id == task_id).order_by(TaskStep.idx))).scalars().all()
    calls = (await db.execute(select(ToolCall).where(ToolCall.task_id == task_id).order_by(ToolCall.created_at))).scalars().all()
    approvals = (await db.execute(select(Approval).where(Approval.task_id == task_id).order_by(Approval.created_at))).scalars().all()
    results = {}
    if calls:
        rr = (await db.execute(select(ToolResult).where(ToolResult.tool_call_id.in_([c.id for c in calls])))).scalars().all()
        results = {r.tool_call_id: {"ok": r.ok, "output": r.output[-4000:]} for r in rr}
    return {
        **task_dict(t),
        "steps": [{"idx": s.idx, "phase": s.phase, "status": s.status, "summary": s.summary, "created_at": s.created_at} for s in steps],
        "tool_calls": [{"id": c.id, "tool": c.tool_name, "args": c.args, "status": c.status, "risk": c.risk,
                        "exit_code": c.exit_code, "duration_ms": c.duration_ms, "created_at": c.created_at,
                        "result": results.get(c.id)} for c in calls],
        "approvals": [{"id": a.id, "status": a.status, "description": a.description, "payload": a.payload} for a in approvals],
    }


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    t = (await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "کار یافت نشد")
    if t.status in ("completed", "cancelled", "failed"):
        return {"ok": True, "status": t.status}
    t.cancel_requested = True
    if t.status in ("queued", "waiting_approval"):
        t.status = "cancelled"
        t.finished_at = datetime.now(timezone.utc)
    await db.commit()
    await audit(db, user_id=user.id, action="task.cancel", actor="web", target=task_id)
    await broker.publish(f"task:{task_id}", "task.status", {"status": t.status})
    return {"ok": True, "status": t.status}


class DecisionIn(BaseModel):
    approve: bool


@router.post("/{task_id}/approvals/{approval_id}")
async def decide_approval(task_id: str, approval_id: str, body: DecisionIn,
                          user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    ap = (await db.execute(select(Approval).where(Approval.id == approval_id, Approval.task_id == task_id))).scalar_one_or_none()
    t = (await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))).scalar_one_or_none()
    if not ap or not t:
        raise HTTPException(404, "درخواست تأیید یافت نشد")
    if ap.status != "pending":
        raise HTTPException(400, "این درخواست قبلاً بررسی شده است")
    ap.status = "approved" if body.approve else "rejected"
    ap.decided_by = user.id
    ap.decided_at = datetime.now(timezone.utc)
    state = dict(t.state or {})
    pending = state.get("pending_calls") or []
    if pending:
        if body.approve:
            pending[0]["approved"] = True
        else:
            # drop the call, feed a denial to the model
            state.setdefault("messages", []).append({
                "role": "tool", "tool_call_id": pending[0].get("id"), "name": pending[0].get("name"),
                "content": "❌ کاربر این عملیات را رد کرد. مسیر جایگزین امن‌تری انتخاب کن یا توضیح بده.",
            })
            pending = pending[1:]
    state["pending_calls"] = pending
    state["paused"] = False
    t.state = state
    t.status = "queued"
    await db.commit()
    await audit(db, user_id=user.id, action="approval.decide", actor="web", target=task_id,
                detail={"approval_id": approval_id, "approve": body.approve})
    await broker.publish(f"task:{task_id}", "task.status", {"status": "queued"})
    return {"ok": True, "status": t.status}


@router.post("/{task_id}/continue")
async def continue_task(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    t = (await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "کار یافت نشد")
    if t.status in ("failed", "cancelled") and t.state:
        t.status = "queued"
        t.cancel_requested = False
        await db.commit()
        return {"ok": True, "status": "queued"}
    raise HTTPException(400, "این کار قابل ادامه نیست")


@router.get("/{task_id}/events")
async def task_events(task_id: str, request: Request, user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_session)):
    t = (await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "کار یافت نشد")

    async def gen():
        yield f"event: snapshot\ndata: {json.dumps({'task': task_dict(t)}, default=str, ensure_ascii=False)}\n\n"
        async for ev in broker.subscribe(f"task:{task_id}"):
            if await request.is_disconnected():
                break
            yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], ensure_ascii=False, default=str)}\n\n"
            if ev["event"] == "task.done":
                break

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{task_id}/logs")
async def task_logs(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    t = (await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "کار یافت نشد")
    calls = (await db.execute(select(ToolCall).where(ToolCall.task_id == task_id).order_by(ToolCall.created_at))).scalars().all()
    out = []
    for c in calls:
        r = (await db.execute(select(ToolResult).where(ToolResult.tool_call_id == c.id))).scalar_one_or_none()
        out.append({"tool": c.tool_name, "args": c.args, "status": c.status, "exit_code": c.exit_code,
                    "duration_ms": c.duration_ms, "output": (r.output if r else "")[-8000:]})
    return out
