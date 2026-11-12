#!/usr/bin/env bash
# نصب سریع از GitHub:  curl -fsSL https://raw.githubusercontent.com/mkhashei43-alt/sina-os/main/install.sh | bash
set -euo pipefail
REPO="${SINA_REPO:-https://github.com/mkhashei43-alt/sina-os}"
DIR="${SINA_DIR:-$HOME/sina-os}"
PY="$(command -v python3 || command -v python || true)"
[ -z "$PY" ] && { echo "✗ پایتون ۳.۱۰+ لازم است → https://python.org/downloads"; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)' || { echo "✗ نسخهٔ پایتون قدیمی است"; exit 1; }
if [ -d "$DIR/.git" ]; then echo "↻ به‌روزرسانی $DIR"; git -C "$DIR" pull --ff-only; else
  echo "⬇ دریافت سینا OS در $DIR"; git clone --depth 1 "$REPO" "$DIR"; fi
cd "$DIR" && chmod +x sina.sh sina.command 2>/dev/null || true
echo "✅ نصب شد. اجرا: cd $DIR && ./sina.sh"
