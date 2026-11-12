"""Sina OS — CLI محلی (بدون نیاز به وب).

    sina doctor              بررسی سلامت نصب
    sina providers           فهرست سرویس‌های پشتیبانی‌شده
    sina token add <key>     افزودن توکن سرویس (تعاملی)
    sina token list          سرویس‌های متصل
    sina token rm <key>      حذف توکن
    sina models              مدل‌های پیش‌فرض
    sina ask "..."           اجرای یک کار از خط فرمان
"""
from __future__ import annotations

import asyncio
import getpass
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SECRET_HINTS = ("key", "token", "secret", "password", "private", "dsn", "sid", "merchant")


def _ask_field(name: str) -> str:
    hidden = any(h in name.lower() for h in SECRET_HINTS)
    label = f"  {name}: "
    return getpass.getpass(label) if hidden else input(label)


async def _session():
    from app.db import SessionLocal, init_db
    await init_db()
    return SessionLocal()


async def _admin_user(db):
    from sqlalchemy import select
    from app.models import User
    from app.config import get_settings
    s = get_settings()
    user = (await db.execute(select(User).where(User.email == s.admin_email.lower()))).scalar_one_or_none()
    if not user:
        print("✗ کاربر مدیر پیدا نشد. یک‌بار `sina run` را اجرا کنید تا ساخته شود.")
        raise SystemExit(1)
    return user


def cmd_doctor() -> None:
    import platform, shutil
    from app.config import get_settings
    print("🩺 بررسی نصب سینا OS")
    print(f"  پایتون      {platform.python_version()}  ({platform.system()})")
    ok = True
    for mod in ("fastapi", "sqlalchemy", "httpx", "langgraph", "pydantic"):
        try:
            __import__(mod)
            print(f"  بستهٔ {mod:<12} ✓")
        except Exception as e:
            ok = False
            print(f"  بستهٔ {mod:<12} ✗ ({e})")
    s = get_settings()
    print(f"  دیتابیس     {s.database_url}")
    print(f"  فضای‌کار    {s.workspace_path}")
    print(f"  مدل پیش‌فرض {s.default_model}")
    print(f"  OpenRouter  {'✓ تنظیم شده' if s.openrouter_api_key else '✗ تنظیم نشده (مدل‌های :free کار می‌کنند)'}")
    print(f"  Node.js     {shutil.which('node') or 'نصب نیست (کنسول داخلی استفاده می‌شود)'}")
    print("  نتیجه:", "سالم ✅" if ok else "نیاز به نصب مجدد ❌")


async def cmd_token_add(key: str) -> None:
    from app.crypto import encrypt_json
    from app.integrations.catalog import get_provider
    from app.models import Integration
    from sqlalchemy import select
    spec = get_provider(key)
    if not spec:
        print(f"✗ سرویس «{key}» شناخته نمی‌شود. با `sina providers` فهرست را ببینید.")
        raise SystemExit(1)
    print(f"\n🔑 {spec['name']}  ({spec['category']})")
    print(f"   مستندات توکن: {spec['docs']}")
    if spec.get("note"):
        print(f"   نکته: {spec['note']}")
    print("   (برای رد کردن یک فیلد، Enter بزنید)\n")
    cfg: dict[str, str] = {}
    for f in spec["fields"]:
        if f == "none":
            continue
        v = _ask_field(f).strip()
        if v:
            cfg[f] = v
    if not cfg:
        print("✗ هیچ مقداری وارد نشد.")
        return
    async with await _session() as db:
        user = await _admin_user(db)
        row = (await db.execute(select(Integration).where(
            Integration.user_id == user.id, Integration.kind == key))).scalar_one_or_none()
        if row:
            row.config_enc = encrypt_json({**(__import__("app.crypto", fromlist=["decrypt_json"]).decrypt_json(row.config_enc)), **cfg})
            row.enabled = True
        else:
            db.add(Integration(user_id=user.id, kind=key, name=spec["name"],
                               config_enc=encrypt_json(cfg), enabled=True))
        await db.commit()
    print(f"✓ {spec['name']} ذخیره شد (رمزنگاری‌شده). عامل الان می‌تواند از آن استفاده کند.")


async def cmd_token_list() -> None:
    from app.crypto import decrypt_json
    from app.models import Integration
    from sqlalchemy import select
    async with await _session() as db:
        user = await _admin_user(db)
        rows = (await db.execute(select(Integration).where(Integration.user_id == user.id))).scalars().all()
    if not rows:
        print("هیچ سرویسی متصل نشده. مثال: `sina token add openai`")
        return
    print(f"{'سرویس':<18} {'وضعیت':<10} فیلدها")
    for r in rows:
        fields = ", ".join(sorted(k for k in decrypt_json(r.config_enc)))
        print(f"{r.kind:<18} {'فعال' if r.enabled else 'خاموش':<10} {fields}")


async def cmd_token_rm(key: str) -> None:
    from app.models import Integration
    from sqlalchemy import select
    async with await _session() as db:
        user = await _admin_user(db)
        row = (await db.execute(select(Integration).where(
            Integration.user_id == user.id, Integration.kind == key))).scalar_one_or_none()
        if not row:
            print("چنین اتصالی وجود ندارد.")
            return
        await db.delete(row)
        await db.commit()
    print(f"✓ اتصال «{key}» حذف شد.")


def cmd_providers(category: str = "") -> None:
    from app.integrations.catalog import CATALOG, CATEGORY_FA
    groups: dict[str, list] = {}
    for k, v in CATALOG.items():
        if category and v["category"] != category:
            continue
        groups.setdefault(v["category"], []).append((k, v["name"]))
    for cat, items in groups.items():
        print(f"\n{CATEGORY_FA.get(cat, cat)}  ({len(items)})")
        for k, n in sorted(items, key=lambda x: x[1]):
            print(f"  {k:<14} {n}")
    print(f"\nمجموع: {sum(len(v) for v in groups.values())} سرویس — افزودن: sina token add <key>")


async def cmd_ask(instruction: str) -> None:
    """اجرای یک کار از CLI (بدون UI) و نمایش نتیجه."""
    from app.models import Task, User, Conversation
    from sqlalchemy import select
    from app.agent.runner import AgentRunner
    async with await _session() as db:
        user = await _admin_user(db)
        conv = Conversation(user_id=user.id, title=instruction[:60])
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        task = Task(user_id=user.id, conversation_id=conv.id, title=instruction[:80],
                    instruction=instruction, kind="chat", status="queued", channel="cli")
        db.add(task)
        await db.commit()
        await db.refresh(task)
        print(f"▶ کار {task.id[:8]} شروع شد…")
        runner = AgentRunner()
        await runner.run(task.id)
        await db.refresh(task)
        print(f"\nوضعیت: {task.status}")
        print(task.result or task.error or "(بدون خروجی)")


async def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print(__doc__)
        return
    cmd = argv[1]
    if cmd == "doctor":
        cmd_doctor()
    elif cmd == "providers":
        cmd_providers(argv[2] if len(argv) > 2 else "")
    elif cmd == "token":
        sub = argv[2] if len(argv) > 2 else "list"
        if sub == "add" and len(argv) > 3:
            await cmd_token_add(argv[3].lower())
        elif sub == "rm" and len(argv) > 3:
            await cmd_token_rm(argv[3].lower())
        else:
            await cmd_token_list()
    elif cmd == "ask" and len(argv) > 2:
        await cmd_ask(" ".join(argv[2:]))
    elif cmd == "models":
        from app.config import get_settings
        s = get_settings()
        print(json.dumps({"default": s.default_model, "coding": s.coding_model,
                          "reasoning": s.reasoning_model}, ensure_ascii=False, indent=1))
    else:
        print(__doc__)


if __name__ == "__main__":
    asyncio.run(main(sys.argv))
