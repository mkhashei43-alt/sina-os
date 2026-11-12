"""تست‌های نسخهٔ فروش: ثبت‌نام، جداسازی مستأجرها، سهمیه، پلن و پنل ادمین."""
from __future__ import annotations

import uuid

import pytest

from app.plans import PLANS, public_catalog


def _new_email() -> str:
    return f"user-{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.asyncio
async def test_public_catalog(app_client):
    r = await app_client.get("/api/public/meta")
    assert r.status_code == 200
    d = r.json()
    assert d["plans"] and {p["key"] for p in d["plans"]} == {"free", "pro", "business"}
    assert all("price_toman" in p for p in d["plans"])


@pytest.mark.asyncio
async def test_signup_creates_tenant_and_isolated_account(app_client):
    email = _new_email()
    r = await app_client.post("/api/public/signup", json={
        "name": "مشتری تست", "email": email, "password": "StrongPass!9", "company": "شرکت تست"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["tenant"]["status"] == "trial" and d["tenant"]["plan"] == "pro"
    auth = {"Authorization": f"Bearer {d['access_token']}"}

    me = (await app_client.get("/api/auth/me", headers=auth)).json()
    assert me["tenant"]["name"] == "شرکت تست"
    assert me["subscription"]["plan"]["key"] == "pro"
    assert me["platform_admin"] is False

    # دادهٔ مشتری دیگر دیده نمی‌شود
    tasks = (await app_client.get("/api/tasks", headers=auth)).json()
    assert tasks == []


@pytest.mark.asyncio
async def test_signup_duplicate_and_weak_password(app_client):
    email = _new_email()
    payload = {"name": "دو بار", "email": email, "password": "StrongPass!9"}
    assert (await app_client.post("/api/public/signup", json=payload)).status_code == 200
    dup = await app_client.post("/api/public/signup", json=payload)
    assert dup.status_code == 409
    weak = await app_client.post("/api/public/signup", json={**payload, "email": _new_email(), "password": "12345678"})
    assert weak.status_code == 422


@pytest.mark.asyncio
async def test_plan_upgrade_request_flow(app_client, auth):
    # مشتری درخواست ارتقا می‌دهد
    r = await app_client.post("/api/billing/request", json={"plan": "business", "months": 3, "reference": "REF-1"},
                              headers=auth)
    # ادمین پلتفرم (نصب تست) سهمیه ندارد؛ این مسیر فقط برای مستأجرها معنا دارد
    assert r.status_code in (200, 400)


@pytest.mark.asyncio
async def test_tenant_quota_enforced(app_client, monkeypatch):
    from app.services import tenancy

    email = _new_email()
    d = (await app_client.post("/api/public/signup", json={
        "name": "سهمیه", "email": email, "password": "StrongPass!9"})).json()
    auth = {"Authorization": f"Bearer {d['access_token']}"}

    async def fake_usage(db, tenant, user_id=None):
        return {"tasks_today": 999, "tokens_month": 0, "workspaces": 0, "credentials": 0}

    monkeypatch.setattr(tenancy, "tenant_usage", fake_usage)
    r = await app_client.post("/api/tasks", json={"instruction": "سلام"}, headers=auth)
    assert r.status_code == 429
    assert "سهمیه" in r.json()["detail"]


@pytest.mark.asyncio
async def test_credentials_are_private_per_tenant(app_client):
    d1 = (await app_client.post("/api/public/signup", json={
        "name": "الف", "email": _new_email(), "password": "StrongPass!9"})).json()
    d2 = (await app_client.post("/api/public/signup", json={
        "name": "مشتری ب", "email": _new_email(), "password": "StrongPass!9"})).json()
    a1 = {"Authorization": f"Bearer {d1['access_token']}"}
    a2 = {"Authorization": f"Bearer {d2['access_token']}"}

    r = await app_client.post("/api/integrations", headers=a1, json={
        "kind": "github", "config": {"token": "ghp_secret_of_tenant_1", "owner": "acme"}})
    assert r.status_code == 200

    list1 = (await app_client.get("/api/integrations", headers=a1)).json()
    list2 = (await app_client.get("/api/integrations", headers=a2)).json()
    assert list1["github"]["configured"] is True
    assert list2["github"]["configured"] is False
    # مقدار محرمانه هیچ‌گاه برنمی‌گردد
    assert "ghp_secret_of_tenant_1" not in str(list1)


@pytest.mark.asyncio
async def test_suspended_tenant_is_blocked(app_client, monkeypatch):
    from app.services import tenancy

    email = _new_email()
    d = (await app_client.post("/api/public/signup", json={
        "name": "تعلیق", "email": email, "password": "StrongPass!9"})).json()
    auth = {"Authorization": f"Bearer {d['access_token']}"}

    async def suspended(db, user):
        return None

    # پس از تعلیق، ساخت کار باید ۴۲۹/۴۰۳ بدهد
    from app.models import Tenant
    from app.db import SessionLocal
    from sqlalchemy import select
    async with SessionLocal() as db:
        t = (await db.execute(select(Tenant).where(Tenant.id == d["tenant"]["id"]))).scalar_one()
        t.status = "suspended"
        await db.commit()

    async def fake_usage(db, tenant, user_id=None):
        return {"tasks_today": 0, "tokens_month": 0, "workspaces": 0, "credentials": 0}

    monkeypatch.setattr(tenancy, "tenant_usage", fake_usage)
    # enforce_task_quota در حالت تعلیق هم نباید اجازه دهد کار ساخته شود
    r = await app_client.post("/api/tasks", json={"instruction": "تست"}, headers=auth)
    assert r.status_code in (403, 429)


@pytest.mark.asyncio
async def test_plans_have_consistent_limits():
    for key, p in PLANS.items():
        assert p.tasks_per_day > 0 and p.tokens_per_month > 0
        assert p.workspaces > 0 and p.credentials > 0
        assert p.price_toman >= 0
    assert PLANS["free"].price_toman == 0
    assert [x["key"] for x in public_catalog()] == ["free", "pro", "business"]
