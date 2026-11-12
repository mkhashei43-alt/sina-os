# ⚡ شروع سریع (vibe-coding style)

سینا OS یک عامل هوشمند است که **روی کامپیوتر خودتان** اجرا می‌شود؛ با **توکن‌های خودتان**.
هیچ دیتایی جز به سرویسی که خودتان کلیدش را داده‌اید نمی‌رود.

---

## ۱. پیش‌نیاز

فقط **Python ۳.۱۰ یا بالاتر** → <https://python.org/downloads>
(هنگام نصب در ویندوز، تیک **Add python.exe to PATH** را بزنید.)

> Node.js، Docker یا دیتابیس لازم نیست. نصب‌شده‌ها به‌طور خودکار شناسایی می‌شوند.

## ۲. اجرا با یک دستور

### ویندوز
```powershell
git clone https://github.com/mkhashei43-alt/sina-os && cd sina-os
sina.cmd
```
یا فقط روی `sina.bat` دابل‌کلیک کنید.

### macOS
```bash
git clone https://github.com/mkhashei43-alt/sina-os && cd sina-os
./sina.sh          # یا دابل‌کلیک روی sina.command
```

### Linux
```bash
git clone https://github.com/mkhashei43-alt/sina-os && cd sina-os
./sina.sh
```

### بدون Git (فقط دانلود ZIP)
ZIP را دانلود، اکسترکت و `sina.py` را اجرا کنید:
```bash
python sina.py
```

**اولین اجرا** چه می‌کند؟
1. محیط مجازی می‌سازد (`.venv`)
2. وابستگی‌ها را نصب می‌کند (~۲ تا ۴ دقیقه، یک‌بار)
3. فایل `backend/.env` و رمز مدیر را می‌سازد و **در ترمینال چاپ می‌کند**
4. سرور را روی `http://127.0.0.1:8765` بالا می‌آورد و مرورگر را باز می‌کند

> 🔑 رمزی که در ترمینال چاپ می‌شود را نگه دارید؛ با `admin@sina.local` وارد شوید.

## ۳. اولین اجرا در ۶۰ ثانیه

1. **اتصال‌ها** را باز کنید → یکی از این‌ها را وصل کنید:
   - **OpenRouter** (پیشنهاد می‌شود: یک کلید = صدها مدل، مدل‌های `:free` رایگان)
   - یا هر کدام از OpenAI / Anthropic / Gemini / Groq / DeepSeek
2. روی کارت سرویس کلیک کنید، کلید را بچسبانید، **ذخیره**.
3. در تب «گفتگو» بنویسید:
   ```
   یک اسکریپت پایتون بساز که قیمت سه ارز را از یک API بگیرد و در فایل CSV ذخیره کند، اجرا کن و نتیجه را نشان بده.
   ```

## ۴. حالت‌های دیگر اجرا

| دستور | کاربرد |
|---|---|
| `python sina.py` | اجرا + مرورگر |
| `python sina.py run --port 9000 --no-browser` | پورت دلخواه، بدون مرورگر |
| `python sina.py doctor` | بررسی سلامت نصب |
| `python sina.py providers` | فهرست ۷۳ سرویس پشتیبانی‌شده |
| `python sina.py token add openai` | افزودن کلید از ترمینال |
| `python sina.py token list` | سرویس‌های متصل |
| `python sina.py ask "..."` | اجرای کار از ترمینال (بدون UI) |
| `docker compose -f docker-compose.oss.yml up -d` | اجرا با داکر |

## ۵. داشبورد کامل (اختیاری)

کنسول داخلی سریع است و به Node نیاز ندارد. اگر داشبورد Next.js را می‌خواهید:

```bash
cd frontend && npm install && npm run build
cd .. && npm run --prefix frontend start   # پورت 3000
python sina.py run --no-browser            # API روی 8765
```

## ۶. اجرای روی GitHub (Codespaces)

اگر مخزن را روی GitHub دارید، بدون نصب چیزی:

1. در صفحهٔ مخزن → **Code ▾ → Codespaces → Create codespace on main**
2. محیط خودکار ساخته می‌شود و سینا روی پورت `8765` بالا می‌آید (مرورگر باز می‌شود).
3. کلیدها را همان‌جا وارد کنید؛ فایل `.env` هرگز commit نمی‌شود (در `.gitignore`).

GitHub Actions هم در هر push تست‌ها (~۶۱ تست) و build فرانت را اجرا می‌کند.

## ۷. رفع اشکال

| مشکل | راه‌حل |
|---|---|
| `python` شناخته نمی‌شود | پایتون را با گزینهٔ **Add to PATH** نصب کنید یا `py -3 sina.py` را بزنید |
| پورت اشغال است | `python sina.py run --port 8899` |
| رمز مدیر را گم کردم | در `backend/.env` مقدار `ADMIN_PASSWORD` را عوض کنید و `sina.py` را دوباره اجرا کنید¹ |
| خطای 401 از مدل | کلید را در اتصال‌ها دوباره ثبت کنید؛ کلیدهای `free` روزانه محدودند |
| ویندوز: خطای اجرای اسکریپت | `Set-ExecutionPolicy -Scope Process RemoteSigned` |

¹ برای اعمال رمز جدید روی دیتابیس موجود: `rm data/sina.db` (داده‌ها پاک می‌شود) یا از داخل کنسول رمز را تغییر دهید.
