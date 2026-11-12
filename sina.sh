#!/usr/bin/env bash
# Sina OS — Linux / macOS
set -e
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python
exec "$PY" sina.py "$@"
