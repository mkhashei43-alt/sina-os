"""Auth: login, logout, me, session management."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
import re

from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import audit
from ..config import get_settings
from ..db import get_session
from ..deps import get_current_user
from ..models import Session, Tenant, User
from ..security import create_access_token, rate_limiter, verify_password
from ..services.tenancy import assert_usable, effective_plan, ensure_tenant, is_platform_admin, quota_snapshot, trial_days_left

router = APIRouter(prefix="/auth", tags=["auth"])
_settings = get_settings()


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")


class LoginIn(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        if not EMAIL_RE.match(v.strip()):
            raise ValueError("ایمیل نامعتبر است")
        return v.strip().lower()


async def get_tenant_for(db: AsyncSession, user: User):
    return (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one_or_none() if user.tenant_id else None


@router.post("/login")
async def login(body: LoginIn, request: Request, db: AsyncSession = Depends(get_session)):
    ip = request.client.host if request.client else ""
    if not rate_limiter.allow(f"login:{ip}", _settings.rate_limit_auth_per_min):
        raise HTTPException(429, "تعداد تلاش‌ها بیش از حد مجاز است؛ کمی بعد دوباره امتحان کنید")
    user = (await db.execute(select(User).where(User.email == body.email.lower()))).scalar_one_or_none()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        await audit(db, user_id=user.id if user else None, action="auth.login_failed", actor="web", ip=ip,
                    detail={"email": body.email})
        raise HTTPException(401, "ایمیل یا رمز عبور نادرست است")
    tenant = await get_tenant_for(db, user)
    if tenant and tenant.status == "closed":
        raise HTTPException(403, "این حساب بسته شده است؛ با پشتیبانی تماس بگیرید")
    token, jti, exp = create_access_token(user.id, user.role)
    db.add(Session(user_id=user.id, jti=jti, expires_at=exp, ip=ip,
                   user_agent=(request.headers.get("user-agent") or "")[:255]))
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await audit(db, user_id=user.id, action="auth.login", actor="web", ip=ip)
    return {
        "access_token": token, "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
                 "tenant_id": user.tenant_id,
                 "tenant_name": tenant.name if tenant else "",
                 "plan": effective_plan(tenant).key,
                 "platform_admin": is_platform_admin(user)},
    }


@router.post("/logout")
async def logout(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    auth = request.headers.get("authorization", "")
    from ..security import decode_token
    payload = decode_token(auth.replace("Bearer ", "").strip()) or {}
    if payload.get("jti"):
        sess = (await db.execute(select(Session).where(Session.jti == payload["jti"]))).scalar_one_or_none()
        if sess:
            sess.revoked = True
            await db.commit()
    await audit(db, user_id=user.id, action="auth.logout", actor="web")
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    tenant = await ensure_tenant(db, user)
    snap = await quota_snapshot(db, user)
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
            "telegram_id": user.telegram_id, "settings": user.settings or {},
            "tenant": snap["tenant"], "subscription": {"plan": snap["plan"], "usage": snap["usage"]},
            "platform_admin": snap["platform_admin"]}


class PasswordChangeIn(BaseModel):
    current: str
    next: str


@router.post("/password")
async def change_password(body: PasswordChangeIn, user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_session)):
    if len(body.next) < 8:
        raise HTTPException(400, "رمز جدید باید حداقل ۸ کاراکتر باشد")
    if not verify_password(body.current, user.password_hash):
        raise HTTPException(400, "رمز فعلی نادرست است")
    from ..security import hash_password
    user.password_hash = hash_password(body.next)
    await db.commit()
    await audit(db, user_id=user.id, action="auth.password_change", actor="web")
    return {"ok": True}
