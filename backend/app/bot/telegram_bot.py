"""Telegram bot (aiogram 3) — thin client of the same Sina AI OS backend.

Security: only ids listed in TELEGRAM_ALLOWED_IDS may use the bot; the bot
authenticates to the API with a dedicated account and never exposes secrets.
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

log = logging.getLogger("sina.telegram")
API = os.getenv("SINA_API_URL", "http://api:8000").rstrip("/")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BOT_EMAIL = os.getenv("TELEGRAM_BOT_EMAIL", os.getenv("ADMIN_EMAIL", "admin@sina.local"))
BOT_PASSWORD = os.getenv("TELEGRAM_BOT_PASSWORD", os.getenv("ADMIN_PASSWORD", ""))
ALLOWED = {int(x) for x in os.getenv("TELEGRAM_ALLOWED_IDS", "").split(",") if x.strip().lstrip("-").isdigit()}

_token: str | None = None
_poll_tasks: dict[int, int] = {}  # chat_id -> task_id index into active list


async def api_login() -> str:
    global _token
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{API}/api/auth/login", json={"email": BOT_EMAIL, "password": BOT_PASSWORD})
        r.raise_for_status()
        _token = r.json()["access_token"]
    return _token


def headers() -> dict:
    return {"Authorization": f"Bearer {_token}"}


async def api(method: str, path: str, **kw):
    global _token
    if not _token:
        await api_login()
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.request(method, f"{API}/api{path}", headers=headers(), **kw)
        if r.status_code == 401:
            await api_login()
            r = await c.request(method, f"{API}/api{path}", headers=headers(), **kw)
        r.raise_for_status()
        return r.json()


def allowed(msg_or_cb) -> bool:
    uid = msg_or_cb.from_user.id if msg_or_cb.from_user else 0
    if not ALLOWED:
        return False
    return uid in ALLOWED


dp = Dispatcher()


@dp.message(Command("start"))
async def start(msg: Message):
    if not allowed(msg):
        await msg.answer("⛔ دسترسی ندارید. شناسه تلگرام شما مجاز نیست.")
        return
    await msg.answer(
        "⚡ <b>سینا AI OS</b>\n\n"
        "دستور خود را بنویسید؛ من آن را برنامه‌ریزی و با ابزارهای واقعی اجرا می‌کنم.\n\n"
        "/tasks — لیست کارها\n/status — وضعیت آخرین کار\n/cancel — لغو کار جاری\n"
        "فایل بفرستید تا در فضای‌کار ذخیره شود.",
        parse_mode="HTML",
    )


@dp.message(Command("tasks"))
async def tasks(msg: Message):
    if not allowed(msg):
        return
    items = await api("GET", "/tasks?limit=8")
    if not items:
        await msg.answer("کاری وجود ندارد.")
        return
    lines = [f"• <code>{t['id'][:8]}</code> [{t['status']}] {t['title'][:60]}" for t in items]
    await msg.answer("<b>آخرین کارها</b>\n" + "\n".join(lines), parse_mode="HTML")


@dp.message(Command("status"))
async def status(msg: Message):
    if not allowed(msg):
        return
    items = await api("GET", "/tasks?limit=1")
    if not items:
        await msg.answer("کاری در جریان نیست.")
        return
    t = await api("GET", f"/tasks/{items[0]['id']}")
    text = f"<b>{t['title'][:80]}</b>\nوضعیت: {t['status']}\nمراحل: " + ", ".join(f"{s['phase']}={s['status']}" for s in t["steps"][-5:])
    if t["result"]:
        text += "\n\n" + t["result"][:2500]
    await msg.answer(text, parse_mode="HTML")


@dp.message(Command("cancel"))
async def cancel(msg: Message):
    if not allowed(msg):
        return
    items = await api("GET", "/tasks?limit=3")
    for t in items:
        if t["status"] in ("running", "queued", "waiting_approval"):
            await api("POST", f"/tasks/{t['id']}/cancel")
            await msg.answer(f"کار <code>{t['id'][:8]}</code> لغو شد.", parse_mode="HTML")
            return
    await msg.answer("کار فعالی پیدا نشد.")


@dp.message(F.document)
async def on_document(msg: Message, bot: Bot):
    if not allowed(msg):
        return
    f = await bot.get_file(msg.document.file_id)
    data = await bot.download_file(f.file_path)
    files = {"file": (msg.document.file_name or "upload.bin", data.read())}
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{API}/api/uploads", headers=headers(), files=files)
        r.raise_for_status()
        saved = r.json()
    await msg.answer(f"📎 فایل ذخیره شد:\n<code>{saved['path']}</code>\n\nحالا بگویید با آن چه کار کنم؟", parse_mode="HTML")


@dp.message(F.text)
async def on_text(msg: Message, bot: Bot):
    if not allowed(msg):
        await msg.answer("⛔ دسترسی ندارید.")
        return
    if len(msg.text) > 8000:
        await msg.answer("متن خیلی طولانی است.")
        return
    note = await msg.answer("⏳ در حال برنامه‌ریزی و اجرا…")
    r = await api("POST", "/tasks", json={"instruction": msg.text, "channel": "telegram"})
    task_id = r["task"]["id"]
    last_state = ""
    for _ in range(600):  # up to ~5 minutes
        await asyncio.sleep(2)
        t = await api("GET", f"/tasks/{task_id}")
        st = t["status"]
        if st != last_state:
            last_state = st
            label = {"queued": "در صف", "running": "در حال اجرا", "waiting_approval": "در انتظار تأیید",
                     "completed": "تکمیل شد", "failed": "ناموفق", "cancelled": "لغو شد"}.get(st, st)
            await note.edit_text(f"وضعیت: {label} — کار <code>{task_id[:8]}</code>", parse_mode="HTML")
        if st == "waiting_approval":
            ap = next((a for a in t["approvals"] if a["status"] == "pending"), None)
            if ap:
                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✅ تأیید", callback_data=f"ap|{task_id}|{ap['id']}|1"),
                    InlineKeyboardButton(text="❌ رد", callback_data=f"ap|{task_id}|{ap['id']}|0"),
                ]])
                await bot.send_message(msg.chat.id, f"⚠️ نیاز به تأیید:\n{ap['description']}", reply_markup=kb)
                last_state = "approval_sent"
        if st in ("completed", "failed", "cancelled"):
            text = t["result"] if st == "completed" else (t.get("error") or st)
            chunks = [text[i:i + 4000] for i in range(0, min(len(text), 12000), 4000)] or ["(بدون خروجی)"]
            for ch in chunks:
                await bot.send_message(msg.chat.id, ch)
            return
    await msg.answer("⌛ زمان انتظار تمام شد. با /status وضعیت را بررسی کنید.")


@dp.callback_query(F.data.startswith("ap|"))
async def on_approval(cb: CallbackQuery):
    if not allowed(cb):
        await cb.answer("دسترسی ندارید", show_alert=True)
        return
    _, task_id, ap_id, decision = cb.data.split("|")
    await api("POST", f"/tasks/{task_id}/approvals/{ap_id}", json={"approve": decision == "1"})
    await cb.answer("ثبت شد")
    await cb.message.edit_text(("✅ تأیید شد و کار ادامه می‌یابد." if decision == "1" else "❌ عملیات رد شد."))


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN تنظیم نشده است")
    if not ALLOWED:
        log.warning("TELEGRAM_ALLOWED_IDS خالی است — ربات به هیچ کاربری پاسخ نمی‌دهد")
    await api_login()
    bot = Bot(BOT_TOKEN)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
