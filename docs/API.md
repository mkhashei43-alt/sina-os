# مستندات API — Sina AI OS

پیشوند: `/api` · احراز هویت: `Authorization: Bearer <JWT>` (برای SSE می‌توان `?token=` داد)
مستندات تعاملی: `/api/docs` (Swagger) و `/api/openapi.json`

## احراز هویت

| متد | مسیر | توضیح |
|---|---|---|
| POST | `/auth/login` | `{email, password}` → `{access_token, user}` · محدودیت نرخ ۱۰/دقیقه بر IP |
| POST | `/auth/logout` | ابطال نشست جاری |
| GET | `/auth/me` | پروفایل کاربر جاری |
| POST | `/auth/password` | `{current, next}` تغییر رمز |

## گفتگوها

| متد | مسیر | توضیح |
|---|---|---|
| GET | `/conversations` | لیست گفتگوها |
| POST | `/conversations` | `{title?, project_id?}` |
| GET | `/conversations/{id}/messages` | پیام‌ها + کارهای مرتبط |
| DELETE | `/conversations/{id}` | آرشیو |

## کارها (Agent)

| متد | مسیر | توضیح |
|---|---|---|
| POST | `/tasks` | `{instruction, conversation_id?, project_id?, channel}` → `{task, conversation_id}` |
| GET | `/tasks?status=&limit=` | لیست کارها |
| GET | `/tasks/{id}` | جزئیات + `steps` + `tool_calls` + `approvals` |
| POST | `/tasks/{id}/cancel` | لغو (queued فوری، running در مرز گام بعدی) |
| POST | `/tasks/{id}/approvals/{approval_id}` | `{approve: bool}` → ادامه/رد عملیات پرخطر |
| POST | `/tasks/{id}/continue` | ادامهٔ کار متوقف/ناموفق از وضعیت ذخیره‌شده |
| GET | `/tasks/{id}/logs` | خروجی کامل ابزارها |
| GET | `/tasks/{id}/events` | **SSE**: `snapshot, task.created, task.status, task.plan, task.step, message.delta, tool.start, tool.end, approval.request, task.done` |

نمونهٔ SSE:
```
event: tool.start
data: {"tool":"python_exec","args":{"operation":"run_file","path":"app/calculator.py"},"risk":"safe"}

event: tool.end
data: {"tool":"python_exec","ok":true,"exit_code":0,"duration_ms":412,"output":"calculator ready: 5\n[exit_code=0]"}
```

## فضای‌کار و فایل

| متد | مسیر | توضیح |
|---|---|---|
| GET/POST | `/workspaces` | لیست / ساخت `{name, project_id?}` |
| DELETE | `/workspaces/{id}` | حذف (فقط زیر ریشهٔ مجاز) |
| GET | `/workspaces/{id}/files?path=.` | لیست پوشه |
| GET | `/workspaces/{id}/file?path=&download=` | خواندن/دانلود |
| POST | `/workspaces/{id}/upload?path=` | آپلود (چندبخشی) |
| POST | `/workspaces/{id}/mkdir` | ساخت پوشه |
| DELETE | `/workspaces/{id}/file?path=` | حذف فایل/پوشه |
| POST | `/workspaces/{id}/exec` | اجرای دستور (با طبقه‌بندی ریسک، ۴۰۳ برای دستور مسدود) |
| POST | `/uploads` | آپلود پیوست گفتگو |

## وب (صفحهٔ مرورگر)

| متد | مسیر | توضیح |
|---|---|---|
| GET | `/web/search?q=&limit=` | جست‌وجوی DuckDuckGo HTML |
| GET | `/web/fetch?url=` | استخراج متن/لینک صفحه (بدون اجرای JS) |

## حافظه، پروژه، یکپارچه‌سازی

| متد | مسیر | توضیح |
|---|---|---|
| GET/POST | `/memory` | لیست/جست‌وجو (`?q=`) و افزودن `{content, kind}` |
| DELETE | `/memory/{id}` | حذف |
| GET/POST | `/projects` | لیست/ساخت (فضای‌کار خودکار) |
| GET | `/integrations` | وضعیت هر یکپارچه‌سازی (بدون اسرار) |
| POST | `/integrations` | `{kind, config, enabled, permissions}` — مقادیر رمزنگاری‌شده |
| DELETE | `/integrations/{kind}` | حذف |

## مدل‌ها، تنظیمات، مصرف، سیستم

| متد | مسیر | توضیح |
|---|---|---|
| GET | `/models` | provider + کاتالوگ مدل‌ها (اگر کلید تنظیم باشد) |
| POST | `/models` | `{default_model?, coding_model?, reasoning_model?}` (نقش owner/admin) |
| GET | `/settings` | نمای تنظیمات و محدودیت‌ها |
| GET | `/usage/summary?days=30` | توکن/هزینه به تفکیک مدل و روز |
| GET | `/logs?limit=&action=` | لاگ ممیزی |
| GET | `/system/health` | سلامت API |
| GET | `/system/stats` | CPU/RAM/Disk/Docker/پورت‌ها/فرآیندها |
| GET | `/system/tools` | ابزارهای ثبت‌شده و سطح ریسک |
| GET | `/events` | SSE رویدادهای کاربر (اعلان کار جدید و …) |

## کدهای خطا

| کد | معنا |
|---|---|
| 400 | ورودی نامعتبر / مسیر ناامن / عملیات غیرمجاز |
| 401 | نبود/انقضای توکن یا نشست ابطال‌شده |
| 403 | نقش ناکافی یا دستور مسدودشده |
| 404 | منبع یافت نشد |
| 413 | حجم آپلود بیش از حد |
| 422 | خطای اعتبارسنجی Pydantic |
| 429 | محدودیت نرخ |
| 502 | خطای سرویس خارجی (وب/مدل) |
