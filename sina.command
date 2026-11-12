#!/usr/bin/env bash
# macOS: دابل‌کلیک برای اجرا
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"
exec "$PY" sina.py "$@"
