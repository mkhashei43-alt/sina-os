"""Audit logging + structured logging setup."""
from __future__ import annotations

import logging
import sys

from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditLog


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
        stream=sys.stdout,
    )


async def audit(
    db: AsyncSession,
    *,
    user_id: str | None,
    action: str,
    actor: str = "system",
    target: str = "",
    detail: dict | None = None,
    ip: str = "",
) -> None:
    try:
        db.add(AuditLog(user_id=user_id, action=action, actor=actor,
                        target=target[:255], detail=detail or {}, ip=ip))
        await db.commit()
    except Exception:  # audit must never break the request path
        logging.getLogger("sina.audit").exception("failed to write audit log")
