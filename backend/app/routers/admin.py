"""پنل مدیریت پلتفرم (فروشنده): مشتری‌ها، پلن، تعلیق، تأیید پرداخت، درآمد.

دسترسی فقط برای ایمیل‌های `PLATFORM_ADMIN_EMAILS`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import audit
from ..db import get_session
from ..deps import get_current_user
from ..models import AuditLog, ModelUsage, PlanRequest, Task, Tenant, User
from ..plans import PLANS, public_catalog
from ..services.tenancy import is_platform_admin, tenant_usage, trial_days_left

router = APIRouter(prefix="/admin", tags=["admin"])


async def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    if not is_platform_admin(user):
        raise HTTPException(403, "دسترسی به پنل مدیریت پلتفرم ندارید")
    return user


@router.get("/overview")
async def overview(admin: User = Depends(require_platform_admin), db: AsyncSession = Depends(get_session)) -> dict:
    tenants = (await db.execute(select(Tenant))).scalars().all()
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    revenue = (await db.execute(
        select(func.coalesce(func.sum(PlanRequest.amount_toman), 0)).where(
            PlanRequest.status == "approved", PlanRequest.decided_at >= month_start)
    )).scalar_one() or 0
    tokens = (await db.execute(
        select(func.coalesce(func.sum(ModelUsage.tokens_in + ModelUsage.tokens_out), 0))
        .where(ModelUsage.created_at >= month_start)
    )).scalar_one() or 0
    tasks = (await db.execute(select(func.count()).select_from(Task))).scalar_one() or 0
    pending = (await db.execute(
        select(func.count()).select_from(PlanRequest).where(PlanRequest.status == "pending")
    )).scalar_one() or 0
    by_plan: dict[str, int] = {}
    for t in tenants:
        by_plan[t.plan] = by_plan.get(t.plan, 0) + 1
    return {
        "tenants": len(tenants), "active": sum(1 for t in tenants if t.status in ("active", "trial")),
        "trials": sum(1 for t in tenants if t.status == "trial"),
        "suspended": sum(1 for t in tenants if t.status == "suspended"),
        "mrr_toman": revenue, "pending_requests": int(pending), "tasks_total": int(tasks),
        "tokens_month": int(tokens), "by_plan": by_plan,
    }


@router.get("/tenants")
async def list_tenants(q: str = "", limit: int = 100, admin: User = Depends(require_platform_admin),
                       db: AsyncSession = Depends(get_session)) -> list[dict]:
    stmt = select(Tenant).order_by(Tenant.created_at.desc()).limit(min(limit, 300))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(Tenant.name).like(like) | func.lower(Tenant.slug).like(like))
    rows = (await db.execute(stmt)).scalars().all()
    out = []
    for t in rows:
        owner = None
        if t.owner_user_id:
            owner = (await db.execute(select(User).where(User.id == t.owner_user_id))).scalar_one_or_none()
        usage = await tenant_usage(db, t)
        out.append({
            "id": t.id, "name": t.name, "slug": t.slug, "plan": t.plan, "status": t.status,
            "trial_days_left": trial_days_left(t), "created_at": t.created_at,
            "owner_email": owner.email if owner else "", "owner_name": owner.name if owner else "",
            "usage": usage, "notes": t.notes,
        })
    return out


class TenantPatch(BaseModel):
    plan: str | None = None
    status: str | None = None
    extend_trial_days: int | None = None
    notes: str | None = None
    suspended_reason: str | None = None


@router.patch("/tenants/{tenant_id}")
async def patch_tenant(tenant_id: str, body: TenantPatch, admin: User = Depends(require_platform_admin),
                       db: AsyncSession = Depends(get_session)) -> dict:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "مشتری یافت نشد")
    if body.plan:
        if body.plan not in PLANS:
            raise HTTPException(400, "پلن نامعتبر")
        tenant.plan = body.plan
    if body.status:
        if body.status not in ("trial", "active", "suspended", "closed"):
            raise HTTPException(400, "وضعیت نامعتبر")
        tenant.status = body.status
        tenant.suspended_reason = body.suspended_reason or ""
    if body.extend_trial_days:
        base = tenant.trial_ends_at or datetime.now(timezone.utc)
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        tenant.trial_ends_at = base + timedelta(days=body.extend_trial_days)
        tenant.status = "trial"
    if body.notes is not None:
        tenant.notes = body.notes[:2000]
    await db.commit()
    await audit(db, user_id=admin.id, action="admin.tenant_patch", actor="web", target=tenant.id,
                detail=body.model_dump(exclude_none=True))
    return {"ok": True}


@router.get("/requests")
async def list_requests(status: str = "pending", admin: User = Depends(require_platform_admin),
                        db: AsyncSession = Depends(get_session)) -> list[dict]:
    stmt = select(PlanRequest).order_by(PlanRequest.created_at.desc()).limit(200)
    if status and status != "all":
        stmt = stmt.where(PlanRequest.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    out = []
    for r in rows:
        t = (await db.execute(select(Tenant).where(Tenant.id == r.tenant_id))).scalar_one_or_none()
        out.append({"id": r.id, "tenant": t.name if t else r.tenant_id, "tenant_id": r.tenant_id,
                    "plan": r.plan, "months": r.months, "amount_toman": r.amount_toman,
                    "status": r.status, "reference": r.reference, "note": r.note,
                    "created_at": r.created_at, "decided_at": r.decided_at})
    return out


class DecisionIn(BaseModel):
    approve: bool
    note: str = ""


@router.post("/requests/{request_id}/decide")
async def decide_request(request_id: str, body: DecisionIn,
                         admin: User = Depends(require_platform_admin),
                         db: AsyncSession = Depends(get_session)) -> dict:
    req = (await db.execute(select(PlanRequest).where(PlanRequest.id == request_id))).scalar_one_or_none()
    if not req:
        raise HTTPException(404, "درخواست یافت نشد")
    if req.status != "pending":
        raise HTTPException(400, "این درخواست قبلاً بررسی شده است")
    tenant = (await db.execute(select(Tenant).where(Tenant.id == req.tenant_id))).scalar_one_or_none()
    req.status = "approved" if body.approve else "rejected"
    req.decided_by = admin.id
    req.decided_at = datetime.now(timezone.utc)
    if body.note:
        req.note = (req.note + f"\n[مدیر] {body.note}").strip()
    if body.approve and tenant:
        tenant.plan = req.plan
        tenant.status = "active"
        tenant.trial_ends_at = None
        # تمدید: تاریخ انقضای اشتراک در settings نگه داشته می‌شود
        cur = tenant.settings or {}
        base = datetime.now(timezone.utc)
        prev = cur.get("paid_until")
        if prev:
            try:
                p = datetime.fromisoformat(prev)
                if p > base:
                    base = p
            except ValueError:
                pass
        cur["paid_until"] = (base + timedelta(days=30 * req.months)).isoformat()
        tenant.settings = cur
    await db.commit()
    await audit(db, user_id=admin.id, action="admin.plan_decision", actor="web", target=req.id,
                detail={"approve": body.approve, "plan": req.plan})
    return {"ok": True, "status": req.status}


@router.get("/audit")
async def recent_audit(limit: int = 100, action: str = "", admin: User = Depends(require_platform_admin),
                       db: AsyncSession = Depends(get_session)) -> list[dict]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 500))
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    rows = (await db.execute(stmt)).scalars().all()
    return [{"id": a.id, "action": a.action, "target": a.target, "actor": a.actor,
             "detail": a.detail, "ip": a.ip, "created_at": a.created_at} for a in rows]


@router.get("/plans")
async def plans(admin: User = Depends(require_platform_admin)) -> list[dict]:
    return public_catalog()
