# مشارکت در سینا OS

ممنون که وقت می‌گذارید! 🎉

## راه‌اندازی محیط توسعه

```bash
python sina.py            # نصب + اجرا (یک‌بار)
cd backend && python -m pytest -q   # اجرای تست‌ها
```

برای داشبورد Next.js:
```bash
cd frontend && npm install && npm run dev
```

## قواعد کد

- **پایتون**: ۳.۱۰+، تایپ‌هینت، async/await، بدون وابستگی سنگین جدید بدون بحث در Issue.
- **امنیت**: هر ابزار جدید باید `risk` مناسب داشته باشد (`safe` / `confirm` / `admin`)؛
  هیچ رازی در کد یا لاگ ننویسید؛ ورودی‌ها را ولیدیت کنید و دسترسی فایل را با `safe_join` محدود کنید.
- **بدون ادعای بی‌پشتوانه**: اگر قابلیتی کامل نیست، صادقانه در README «آزمایشی» علامت بزنید.
- **فارسی/RTL**: متن‌های UI فارسیِ روان، اعداد فارسی در نمایش.

## افزودن یک سرویس جدید (ساده‌ترین راه)

۱. در `backend/app/integrations/catalog.py` یک ورودی اضافه کنید:
```python
P("myservice", "سرویس من", "dev", "https://api.myservice.com/v1", ["api_key"],
  "https://myservice.com/api-keys", auth="bearer",
  actions={"list": {"method": "GET", "path": "/items", "desc": "فهرست آیتم‌ها"}})
```
۲. تست: `python sina.py providers` و `python sina.py token add myservice`
۳. در کنسول، تب «اتصال‌ها» باید کارت جدید را نشان دهد.
۴. اگر منطق پیچیده‌تری لازم است، یک `Tool` در `backend/app/tools/` بسازید و در
   `backend/app/tools/__init__.py` ثبت کنید.

## افزودن تست

هر تغییر رفتار باید تست داشته باشد: `backend/tests/`. الگوی تست‌های موجود را ببینید
(`app_client`, `auth`, `wait_task` در `conftest.py`).

## Pull Request

1. شاخهٔ جدید: `git checkout -b feat/my-feature`
2. Commit با پیام واضح (`feat: add Notion databases action`)
3. `python -m pytest -q` باید سبز باشد
4. PR باز کنید و در توضیح بنویسید **چه چیزی، چرا، و چطور تست شد**.

## گزارش باگ / درخواست قابلیت

از قالب‌های Issue استفاده کنید و این‌ها را بنویسید: سیستم‌عامل، نسخهٔ پایتون،
مرحله‌های بازتولید، و پیام خطا (بدون توکن!).
