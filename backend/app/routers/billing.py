"""اشتراک مشتری: پلن فعلی، مصرف سهمیه، درخواست ارتقا و تاریخچهٔ پرداخت."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import audit
from ..config import get_settings
from ..db import get_session
from ..deps import get_current_user
from ..models import PlanRequest, Tenant, User
from ..plans import PLANS, public_catalog
from ..services.tenancy import effective_plan, ensure_tenant, quota_snapshot

router = APIRouter(prefix="/billing", tags=["billing"])
_settings = get_settings()


@router.get("/me")
async def my_subscription(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> dict:
    snap = await quota_snapshot(db, user)
    rows = (await db.execute(
        select(PlanRequest).where(PlanRequest.tenant_id == (snap["tenant"] or {}).get("id"))
        .order_by(PlanRequest.created_at.desc()).limit(20)
    )).scalars().all()
    snap["requests"] = [{
        "id": r.id, "plan": r.plan, "months": r.months, "amount_toman": r.amount_toman,
        "status": r.status, "reference": r.reference, "note": r.note,
        "created_at": r.created_at, "decided_at": r.decided_at,
    } for r in rows]
    snap["catalog"] = public_catalog()
    snap["payment"] = {"card": _settings.support_email or "", "telegram": _settings.support_telegram}
    return snap


class UpgradeIn(BaseModel):
    plan: str
    months: int = 1
    reference: str = ""
    note: str = ""


@router.post("/request")
async def request_plan(body: UpgradeIn, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_session)) -> dict:
    if body.plan not in PLANS:
        raise HTTPException(400, "پلن نامعتبر است")
    if body.months not in (1, 3, 6, 12):
        raise HTTPException(400, "دوره باید ۱، ۳، ۶ یا ۱۲ ماه باشد")
    tenant = await ensure_tenant(db, user)
    pending = (await db.execute(
        select(PlanRequest).where(PlanRequest.tenant_id == tenant.id, PlanRequest.status == "pending")
    )).scalars().all()
    if len(pending) >= 3:
        raise HTTPException(429, "درخواست‌های در انتظار زیادی دارید؛ تا بررسی قبلی صبر کنید")
    amount = PLANS[body.plan].price_toman * body.months
    if PLANS[body.plan].key == effective_plan(tenant).key:
        raise HTTPException(400, "همین حالا روی این پلن هستید")
    req = PlanRequest(tenant_id=tenant.id, plan=body.plan, months=body.months,
                      amount_toman=amount, reference=body.reference[:120], note=body.note[:1000])
    db.add(req)
    await db.commit()
    await db.refresh(req)
    await audit(db, user_id=user.id, action="billing.request", actor="web", target=req.id,
                detail={"plan": body.plan, "months": body.months, "amount": amount})
    return {"ok": True, "request_id": req.id, "amount_toman": amount,
            "message": "درخواست ثبت شد؛ پس از تأیید پرداخت، پلن فعال می‌شود."}


@router.post("/cancel-request/{request_id}")
async def cancel_request(request_id: str, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_session)) -> dict:
    tenant = await ensure_tenant(db, user)
    req = (await db.execute(select(PlanRequest).where(
        PlanRequest.id == request_id, PlanRequest.tenant_id == tenant.id))).scalar_one_or_none()
    if not req:
        raise HTTPException(404, "درخواست یافت نشد")
    if req.status != "pending":
        raise HTTPException(400, "این درخواست بررسی شده است")
    req.status = "rejected"
    req.note = (req.note + "\n[لغو توسط مشتری]").strip()
    req.decided_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}


@router.get("/invoice/{request_id}")
async def invoice(request_id: str, user: User = Depends(get_current_user),
                  db: AsyncSession = Depends(get_session)) -> dict:
    tenant = await ensure_tenant(db, user)
    req = (await db.execute(select(PlanRequest).where(
        PlanRequest.id == request_id, PlanRequest.tenant_id == tenant.id))).scalar_one_or_none()
    if not req:
        raise HTTPException(404, "فاکتور یافت نشد")
    return {"id": req.id, "tenant": tenant.name, "plan": PLANS.get(req.plan).name if req.plan in PLANS else req.plan,
            "months": req.months, "amount_toman": req.amount_toman, "status": req.status,
            "reference": req.reference, "created_at": req.created_at, "decided_at": req.decided_at}


class TenantProfileIn(BaseModel):
    name: str | None = None


@router.patch("/profile")
async def update_profile(body: TenantProfileIn, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_session)) -> dict:
    tenant = await ensure_tenant(db, user)
    if body.name:
        tenant.name = body.name[:160]
        await db.commit()
    return {"ok": True, "name": tenant.name}
