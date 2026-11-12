"""چند‌مستأجری: دسترسی به مستأجر، شمارش سهمیه و اعمال محدودیت پلن."""
from __future__ import annotations

import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Integration, ModelUsage, Task, Tenant, User, Workspace
from ..plans import Plan, TRIAL_DAYS, TRIAL_PLAN, get_plan
from ..utils import aware

_settings = get_settings()


def is_platform_admin(user: User | None) -> bool:
    if not user:
        return False
    emails = {e.strip().lower() for e in (_settings.platform_admin_emails or "").split(",") if e.strip()}
    return bool(user.email and user.email.lower() in emails)


def slugify(name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF]+", "-", unicodedata.normalize("NFKC", name or "tenant")).strip("-").lower()
    base = re.sub(r"-{2,}", "-", base)[:40] or "tenant"
    return f"{base}-{secrets.token_hex(3)}"


async def get_tenant(db: AsyncSession, user: User) -> Tenant | None:
    if not user.tenant_id:
        return None
    return (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one_or_none()


async def ensure_tenant(db: AsyncSession, user: User) -> Tenant:
    """برای اکانت‌های قدیمی (نصب تک‌کاربره) یک مستأجر می‌سازد."""
    tenant = await get_tenant(db, user)
    if tenant:
        return tenant
    tenant = Tenant(name=(user.name or user.email.split("@")[0])[:160], slug=slugify(user.email.split("@")[0]),
                    plan="business", status="active", owner_user_id=user.id,
                    notes="مهاجرت‌شده از نصب تک‌کاربره")
    db.add(tenant)
    await db.flush()
    user.tenant_id = tenant.id
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def create_tenant(db: AsyncSession, *, name: str, email: str, trial: bool = True) -> Tenant:
    tenant = Tenant(
        name=name[:160] or email, slug=slugify(name or email.split("@")[0]),
        plan=TRIAL_PLAN if trial else "free",
        status="trial" if trial else "active",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS) if trial else None,
    )
    db.add(tenant)
    await db.flush()
    return tenant


def trial_days_left(tenant: Tenant | None) -> int | None:
    if not tenant or tenant.status != "trial" or not tenant.trial_ends_at:
        return None
    delta = (aware(tenant.trial_ends_at) - datetime.now(timezone.utc)).days
    return max(delta, 0)


def effective_plan(tenant: Tenant | None) -> Plan:
    """پایان دورهٔ آزمایشی → پلن رایگان."""
    if tenant is None:
        return get_plan("business")
    if tenant.status == "trial" and (trial_days_left(tenant) or 0) <= 0:
        return get_plan("free")
    return get_plan(tenant.plan)


def assert_usable(tenant: Tenant | None) -> None:
    if tenant is None:
        return
    if tenant.status == "suspended":
        raise HTTPException(403, "این حساب موقتاً تعلیق شده است" +
                            (f": {tenant.suspended_reason}" if tenant.suspended_reason else ""))
    if tenant.status == "closed":
        raise HTTPException(403, "این حساب بسته شده است")


async def tenant_usage(db: AsyncSession, tenant: Tenant | None, user_id: str | None = None) -> dict:
    """مصرف واقعی: کارهای امروز، توکن‌های این ماه، فضاهای‌کار و اتصال‌ها."""
    if tenant is None and not user_id:
        return {"tasks_today": 0, "tokens_month": 0, "workspaces": 0, "credentials": 0}
    uids = [user_id] if tenant is None else [
        r for (r,) in (await db.execute(select(User.id).where(User.tenant_id == tenant.id))).all()
    ]
    if not uids:
        uids = [user_id] if user_id else []
    if not uids:
        return {"tasks_today": 0, "tokens_month": 0, "workspaces": 0, "credentials": 0}

    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    tasks_today = (await db.execute(
        select(func.count()).select_from(Task).where(Task.user_id.in_(uids), Task.created_at >= day_ago)
    )).scalar_one() or 0
    tokens_month = (await db.execute(
        select(func.coalesce(func.sum(ModelUsage.tokens_in + ModelUsage.tokens_out), 0))
        .where(ModelUsage.user_id.in_(uids), ModelUsage.created_at >= month_start)
    )).scalar_one() or 0
    workspaces = (await db.execute(
        select(func.count()).select_from(Workspace).where(Workspace.user_id.in_(uids), Workspace.status != "deleted")
    )).scalar_one() or 0
    credentials = (await db.execute(
        select(func.count()).select_from(Integration).where(Integration.user_id.in_(uids))
    )).scalar_one() or 0
    return {"tasks_today": int(tasks_today), "tokens_month": int(tokens_month),
            "workspaces": int(workspaces), "credentials": int(credentials)}


def limits_dict(plan: Plan) -> dict:
    return {"tasks_per_day": plan.tasks_per_day, "tokens_per_month": plan.tokens_per_month,
            "workspaces": plan.workspaces, "credentials": plan.credentials,
            "max_concurrent_tasks": plan.max_concurrent_tasks}


async def quota_snapshot(db: AsyncSession, user: User) -> dict:
    tenant = await get_tenant(db, user)
    plan = effective_plan(tenant)
    usage = await tenant_usage(db, tenant, user.id)
    lim = limits_dict(plan)
    return {
        "tenant": {"id": tenant.id, "name": tenant.name, "slug": tenant.slug,
                   "plan": plan.key, "plan_name": plan.name, "status": tenant.status,
                   "trial_days_left": trial_days_left(tenant)} if tenant else None,
        "plan": {"key": plan.key, "name": plan.name, "price_toman": plan.price_toman,
                 **lim, "features": list(plan.features)},
        "usage": {**usage,
                  "tasks_left_today": max(lim["tasks_per_day"] - usage["tasks_today"], 0),
                  "tokens_left": max(lim["tokens_per_month"] - usage["tokens_month"], 0),
                  "tasks_pct": min(round(usage["tasks_today"] / max(lim["tasks_per_day"], 1) * 100), 100),
                  "tokens_pct": min(round(usage["tokens_month"] / max(lim["tokens_per_month"], 1) * 100), 100)},
        "platform_admin": is_platform_admin(user),
    }


async def enforce_task_quota(db: AsyncSession, user: User) -> None:
    """قبل از ساخت کار صدا زده می‌شود. مدیر پلتفرم و مستأجر بدون سقف مستثنا هستند."""
    if is_platform_admin(user):
        return
    tenant = await get_tenant(db, user)
    if tenant is None:
        return
    assert_usable(tenant)
    plan = effective_plan(tenant)
    usage = await tenant_usage(db, tenant)
    if usage["tasks_today"] >= plan.tasks_per_day:
        raise HTTPException(429, f"سهمیهٔ روزانهٔ پلن «{plan.name}» ({plan.tasks_per_day} کار در روز) تمام شده است. "
                                 "برای ادامه، پلن را ارتقا دهید.")
    if usage["tokens_month"] >= plan.tokens_per_month:
        raise HTTPException(429, f"سهمیهٔ ماهانهٔ توکن پلن «{plan.name}» تمام شده است. پلن را ارتقا دهید یا "
                                 "کلید OpenRouter خودتان را در بخش اتصال‌ها ثبت کنید.")


async def enforce_token_budget(db: AsyncSession, tenant_id: str | None) -> None:
    """در زمان اجرای کار: اگر بودجهٔ ماه تمام شده باشد، اجرای بیشتر متوقف می‌شود."""
    if not tenant_id:
        return
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        return
    plan = effective_plan(tenant)
    usage = await tenant_usage(db, tenant)
    if usage["tokens_month"] >= plan.tokens_per_month:
        raise HTTPException(429, f"بودجهٔ توکن ماهانهٔ پلن «{plan.name}» تمام شد؛ اجرای کار متوقف شد.")
