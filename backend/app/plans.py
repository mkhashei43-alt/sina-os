"""پلن‌های فروش سینا کلود — تنها منبع حقیقت برای قیمت‌ها و سهمیه‌ها.

هر تغییر در این فایل روی کل سامانه اعمال می‌شود (فرانت‌اند پلن‌ها را از API می‌خواند).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    price_toman: int          # قیمت ماهانه به تومان (۰ = رایگان)
    tasks_per_day: int
    tokens_per_month: int
    workspaces: int
    credentials: int
    max_concurrent_tasks: int
    features: tuple[str, ...]
    highlight: bool = False
    badge: str = ""


PLANS: dict[str, Plan] = {
    "free": Plan(
        key="free", name="رایگان", price_toman=0,
        tasks_per_day=10, tokens_per_month=400_000, workspaces=2, credentials=2,
        max_concurrent_tasks=1,
        features=(
            "۱۰ کار در روز",
            "۴۰۰ هزار توکن در ماه",
            "همهٔ ابزارها (فایل، ترمینال، پایتون، مرورگر، وب)",
            "۲ فضای‌کار · ۲ اتصال خارجی",
            "حافظهٔ برداری و تاریخچهٔ کامل",
        ),
    ),
    "pro": Plan(
        key="pro", name="حرفه‌ای", price_toman=890_000,
        tasks_per_day=150, tokens_per_month=6_000_000, workspaces=15, credentials=12,
        max_concurrent_tasks=3,
        features=(
            "۱۵۰ کار در روز",
            "۶ میلیون توکن در ماه",
            "SSH به سرور، Cloudflare، GitHub، تلگرام",
            "۱۵ فضای‌کار · ۱۲ اتصال خارجی",
            "اجرای هم‌زمان ۳ کار",
            "پشتیبانی اولویت‌دار",
        ),
        highlight=True, badge="پرفروش‌ترین",
    ),
    "business": Plan(
        key="business", name="کسب‌وکار", price_toman=2_400_000,
        tasks_per_day=800, tokens_per_month=30_000_000, workspaces=60, credentials=60,
        max_concurrent_tasks=8,
        features=(
            "۸۰۰ کار در روز",
            "۳۰ میلیون توکن در ماه",
            "همهٔ اتصال‌ها بدون محدودیت عملی",
            "۶۰ فضای‌کار · ۶۰ اتصال خارجی",
            "اجرای هم‌زمان ۸ کار",
            "مدل اختصاصی و کلید OpenRouter خودتان",
            "پشتیبانی اختصاصی + گزارش ماهانه",
        ),
    ),
}

# دورهٔ آزمایشی: ۷ روز با سهمیهٔ پلن حرفه‌ای
TRIAL_DAYS = 7
TRIAL_PLAN = "pro"

ORDER = ["free", "pro", "business"]


def get_plan(key: str | None) -> Plan:
    return PLANS.get((key or "free").lower(), PLANS["free"])


def plan_rank(key: str | None) -> int:
    return ORDER.index(get_plan(key).key)


def public_catalog() -> list[dict]:
    return [
        {**asdict(p), "features": list(p.features),
         "price_irr": p.price_toman * 10,
         "yearly_toman": int(p.price_toman * 10)}
        for p in (PLANS[k] for k in ORDER)
    ]
