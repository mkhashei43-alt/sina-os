"""Conversations & messages."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import get_current_user
from ..models import Conversation, Message, Task, User

router = APIRouter(prefix="/conversations", tags=["chat"])


@router.get("")
async def list_conversations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(Conversation).where(Conversation.user_id == user.id, Conversation.archived == False)  # noqa: E712
                             .order_by(Conversation.updated_at.desc()).limit(100))).scalars().all()
    return [{"id": c.id, "title": c.title, "channel": c.channel, "created_at": c.created_at, "updated_at": c.updated_at} for c in rows]


class ConvIn(BaseModel):
    title: str = "گفت‌وگوی جدید"
    project_id: str | None = None


@router.post("")
async def create_conversation(body: ConvIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    c = Conversation(user_id=user.id, title=body.title, project_id=body.project_id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return {"id": c.id, "title": c.title}


@router.get("/{conv_id}/messages")
async def messages(conv_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    c = (await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "گفت‌وگو یافت نشد")
    rows = (await db.execute(select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at))).scalars().all()
    tasks = (await db.execute(select(Task).where(Task.conversation_id == conv_id).order_by(Task.created_at))).scalars().all()
    return {
        "conversation": {"id": c.id, "title": c.title},
        "messages": [{"id": m.id, "role": m.role, "content": m.content, "task_id": m.task_id,
                      "meta": m.meta, "created_at": m.created_at} for m in rows],
        "tasks": [{"id": t.id, "status": t.status, "instruction": t.instruction, "result": t.result,
                   "created_at": t.created_at} for t in tasks],
    }


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    c = (await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "گفت‌وگو یافت نشد")
    c.archived = True
    await db.commit()
    return {"ok": True}
