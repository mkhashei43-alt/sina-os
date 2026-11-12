#!/usr/bin/env python3
"""Sina OS — نصب و اجرای تک‌دستوری روی Windows، Linux و macOS.

    python sina.py            نصب خودکار + اجرا + باز کردن مرورگر
    python sina.py doctor     بررسی سلامت
    python sina.py token add openai
    python sina.py providers
    python sina.py ask "..."

روی سیستم‌های دیگر:
    macOS/Linux :  ./sina.sh            یا   ./sina.command (دابل‌کلیک)
    Windows     :  sina.cmd            یا   دابل‌کلیک روی sina.bat
"""
from __future__ import annotations

import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
VENV = ROOT / ".venv"
MIN_PY = (3, 10)

BANNER = r"""
   _____ _                 ____  _____
  / ____(_)               / __ \/ ____|
 | (___  _ _ __   __ _    | |  | | (___
  \___ \| | '_ \ / _` |   | |  | |\___ \
  ____) | | | | | (_| |   | |__| |____) |
 |_____/|_|_| |_|\__,_|    \____/|_____/     نسخهٔ متن‌باز
"""


def say(msg: str) -> None:
    print(msg, flush=True)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if platform.system() == "Windows" else "bin/python")


def in_our_venv() -> bool:
    try:
        return Path(sys.executable).resolve().parent == venv_python().resolve().parent
    except OSError:
        return False


def ensure_python_version() -> None:
    if sys.version_info < MIN_PY:
        say(f"✗ پایتون {MIN_PY[0]}.{MIN_PY[1]}+ لازم است (نسخهٔ فعلی {platform.python_version()}).\n"
            "  دانلود: https://www.python.org/downloads/")
        raise SystemExit(1)


def ensure_venv() -> None:
    """ساخت محیط مجازی و نصب وابستگی‌ها (فقط بار اول)."""
    marker = VENV / ".installed"
    if marker.exists() and venv_python().exists():
        return
    say("📦 ساخت محیط مجازی…")
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    py = str(venv_python())
    say("📥 نصب وابستگی‌ها (۲ تا ۴ دقیقه، فقط یک‌بار)…")
    subprocess.check_call([py, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    req = BACKEND / "requirements.txt"
    subprocess.check_call([py, "-m", "pip", "install", "--quiet", "-r", str(req)])
    marker.write_text("ok", encoding="utf-8")
    say("✓ نصب کامل شد.\n")


def ensure_env() -> Path:
    env_path = BACKEND / ".env"
    if env_path.exists():
        return env_path
    data_dir = ROOT / "data"
    (data_dir / "sina-ai").mkdir(parents=True, exist_ok=True)
    password = secrets.token_urlsafe(9)
    content = f"""# ---- سینا OS: تنظیمات محلی (خودکار ساخته شد) ----
ENV=local
DEBUG=false
AUTO_CREATE_TABLES=true
SERVE_CONSOLE=true

DATABASE_URL=sqlite+aiosqlite:///{data_dir.as_posix()}/sina.db
WORKSPACE_ROOT={data_dir.as_posix()}/sina-ai

JWT_SECRET={secrets.token_urlsafe(48)}
ADMIN_EMAIL=admin@sina.local
ADMIN_PASSWORD={password}
ADMIN_NAME=مدیر

# --- مدل‌ها (OpenRouter؛ مدل‌های رایگان با :free) ---
OPENROUTER_API_KEY=
DEFAULT_MODEL=deepseek/deepseek-chat-v3.1:free
CODING_MODEL=qwen/qwen3-coder:free
REASONING_MODEL=deepseek/deepseek-r1-0528:free
MODEL_FALLBACKS=meta-llama/llama-3.3-70b-instruct:free,google/gemma-3-27b-it:free
LLM_MAX_TOKENS=4096

# --- اجرا ---
EXEC_TIMEOUT_SECONDS=120
MAX_UPLOAD_MB=25
REQUIRE_APPROVAL_LEVELS=confirm,admin

# --- نسخهٔ فروش (اختیاری) ---
SIGNUP_ENABLED=false
PLATFORM_ADMIN_EMAILS=admin@sina.local
SALES_BRAND=سینا OS
"""
    env_path.write_text(content, encoding="utf-8")
    try:
        env_path.chmod(0o600)
    except OSError:
        pass
    say("\n" + "=" * 64)
    say("  🔑 حساب مدیر ساخته شد — این را جایی امن نگه دارید:")
    say(f"     ایمیل : admin@sina.local")
    say(f"     رمز   : {password}")
    say(f"     فایل  : {env_path}")
    say("=" * 64 + "\n")
    return env_path


def free_port(start: int = 8765) -> int:
    for p in range(start, start + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start


def run_server(args: list[str]) -> None:
    ensure_python_version()
    say(BANNER)
    ensure_venv()
    ensure_env()
    if not in_our_venv():
        py = str(venv_python())
        raise SystemExit(subprocess.call([py, str(Path(__file__).resolve()), "run", *args]))

    port = None
    for i, a in enumerate(args):
        if a in ("--port", "-p") and i + 1 < len(args):
            port = int(args[i + 1])
    port = port or int(os.getenv("SINA_PORT", "0")) or free_port()
    say(f"🚀 سرور روی http://127.0.0.1:{port} بالا می‌آید…")
    say("   برای توقف: Ctrl+C\n")

    env = os.environ.copy()
    env.setdefault("SINA_CONSOLE", "1")
    cmd = [str(venv_python()), "-m", "uvicorn", "app.main:app",
           "--host", "127.0.0.1", "--port", str(port)]
    if "--no-browser" not in args:
        def opener() -> None:
            for _ in range(60):
                time.sleep(0.5)
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        webbrowser.open(f"http://127.0.0.1:{port}/")
                        return
                except OSError:
                    continue
        import threading
        threading.Thread(target=opener, daemon=True).start()
    try:
        subprocess.call(cmd, cwd=str(BACKEND), env=env)
    except KeyboardInterrupt:
        say("\n👋 خداحافظ.")


def cli_passthrough(argv: list[str]) -> int:
    """اجرای app.cli داخل محیط مجازی."""
    ensure_venv()
    env = os.environ.copy()
    py = str(venv_python())
    return subprocess.call([py, "-m", "app.cli", *argv], cwd=str(BACKEND), env=env)


def doctor_quick() -> int:
    say(BANNER)
    say(f"  پایتون     {platform.python_version()}  ({platform.system()} {platform.machine()})")
    say(f"  Node.js    {shutil.which('node') or '— (کنسول داخلی استفاده می‌شود، مشکلی نیست)'}")
    say(f"  Docker     {shutil.which('docker') or '— (اختیاری)'}")
    say(f"  محیط مجازی {'✓ آماده' if (VENV / '.installed').exists() else '✗ نصب نشده (با `python sina.py` نصب می‌شود)'}")
    say(f"  فایل env   {'✓' if (BACKEND / '.env').exists() else '✗'}")
    return 0


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args or args[0] in ("run", "start", "serve"):
        run_server(args[1:])
        return 0
    if args[0] in ("doctor", "--doctor"):
        return doctor_quick()
    if args[0] in ("version", "--version", "-v"):
        say("Sina OS 1.0.0 (open source edition)")
        return 0
    if args[0] in ("help", "--help", "-h"):
        say(__doc__)
        return 0
    return cli_passthrough(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except KeyboardInterrupt:
        say("\n👋 خداحافظ.")
