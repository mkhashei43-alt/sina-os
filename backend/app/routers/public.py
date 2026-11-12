"""عمومی: لندینگ فروش، پلن‌ها، ثبت‌نام مشتری، وضعیت پایگاه.

این روتر بدون احراز هویت است؛ با محدودیت نرخ و اعتبارسنجی سخت‌گیرانه محافظت می‌شود.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import audit
from ..config import get_settings
from ..db import get_session
from ..models import PlanRequest, Session, Task, Tenant, User
from ..plans import PLANS, TRIAL_DAYS, public_catalog
from ..security import create_access_token, hash_password, rate_limiter
from ..services.tenancy import create_tenant, slugify

router = APIRouter(prefix="/public", tags=["public"])
_settings = get_settings()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


@router.get("/meta")
async def meta(db: AsyncSession = Depends(get_session)) -> dict:
    """اطلاعات نمایشی لندینگ (بدون هیچ دادهٔ حساسی)."""
    tenants = (await db.execute(select(func.count()).select_from(Tenant))).scalar_one() or 0
    tasks = (await db.execute(select(func.count()).select_from(Task))).scalar_one() or 0
    return {
        "brand": _settings.sales_brand,
        "signup_enabled": _settings.signup_enabled,
        "trial_days": TRIAL_DAYS,
        "support_telegram": _settings.support_telegram,
        "support_email": _settings.support_email,
        "stats": {"customers": int(tenants), "tasks": int(tasks)},
        "plans": public_catalog(),
    }


class SignupIn(BaseModel):
    name: str
    email: str
    password: str
    company: str = ""
    plan: str = "trial"
    accept_terms: bool = True

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("ایمیل نامعتبر است")
        return v

    @field_validator("password")
    @classmethod
    def _pw(cls, v: str) -> str:
        if len(v or "") < 8:
            raise ValueError("رمز عبور باید حداقل ۸ کاراکتر باشد")
        if v.lower() in {"12345678", "password", "qwerty123", "admin123"}:
            raise ValueError("رمز عبور بسیار ساده است")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) < 2:
            raise ValueError("نام را کامل وارد کنید")
        return v[:160]


@router.post("/signup")
async def signup(body: SignupIn, request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    if not _settings.signup_enabled:
        raise HTTPException(403, "ثبت‌نام فعلاً بسته است")
    ip = request.client.host if request.client else ""
    if not rate_limiter.allow(f"signup:{ip}", _settings.rate_limit_signup_per_min):
        raise HTTPException(429, "تعداد ثبت‌نام از این IP زیاد است؛ یک دقیقه بعد دوباره تلاش کنید")
    if not body.accept_terms:
        raise HTTPException(400, "پذیرش قوانین استفاده الزامی است")

    exists = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "این ایمیل قبلاً ثبت شده است — وارد شوید")

    tenant = await create_tenant(db, name=body.company.strip() or body.name, email=body.email, trial=True)
    user = User(email=body.email, password_hash=hash_password(body.password), name=body.name,
                role="owner", tenant_id=tenant.id)
    db.add(user)
    await db.flush()
    tenant.owner_user_id = user.id
    await db.commit()
    await db.refresh(user)
    await db.refresh(tenant)

    token, jti, exp = create_access_token(user.id, user.role)
    db.add(Session(user_id=user.id, jti=jti, expires_at=exp, ip=ip,
                   user_agent=(request.headers.get("user-agent") or "")[:255]))
    await db.commit()
    await audit(db, user_id=user.id, action="tenant.signup", actor="web", target=tenant.id, ip=ip,
                detail={"plan": tenant.plan, "email": body.email})

    return {
        "access_token": token, "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role},
        "tenant": {"id": tenant.id, "name": tenant.name, "slug": tenant.slug,
                   "plan": tenant.plan, "status": tenant.status,
                   "trial_days": TRIAL_DAYS},
    }


@router.get("/plans")
async def plans() -> list[dict]:
    return public_catalog()


class ContactIn(BaseModel):
    name: str = ""
    contact: str
    message: str = ""


@router.post("/contact")
async def contact(body: ContactIn, request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    """درخواست مشاوره/فروش سازمانی — در پنل ادمین به‌صورت یادداشت ثبت می‌شود."""
    ip = request.client.host if request.client else ""
    if not rate_limiter.allow(f"contact:{ip}", 5):
        raise HTTPException(429, "تعداد درخواست زیاد است؛ کمی بعد تلاش کنید")
    await audit(db, user_id=None, action="sales.lead", actor="web", ip=ip,
                target=(body.contact or "")[:120],
                detail={"name": body.name[:80], "message": body.message[:1000]})
    return {"ok": True, "message": "درخواست شما ثبت شد؛ کارشناس فروش تماس می‌گیرد."}


@router.get("/check-slug/{slug}")
async def check_slug(slug: str, db: AsyncSession = Depends(get_session)) -> dict:
    clean = slugify(slug)[:40]
    row = (await db.execute(select(Tenant).where(Tenant.slug == clean))).scalar_one_or_none()
    return {"slug": clean, "available": row is None, "plans": list(PLANS)}
