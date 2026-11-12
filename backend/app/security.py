"""Password hashing (scrypt, stdlib), JWT auth, rate limiting, path safety."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

from .config import get_settings

_settings = get_settings()
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT["n"], r=_SCRYPT["r"], p=_SCRYPT["p"], dklen=32)
    return "scrypt$%d$%d$%d$%s$%s" % (
        _SCRYPT["n"], _SCRYPT["r"], _SCRYPT["p"],
        base64.b64encode(salt).decode(), base64.b64encode(dk).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, dk_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
        dk = hashlib.scrypt(password.encode(), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def create_access_token(user_id: str, role: str, minutes: int | None = None) -> tuple[str, str, datetime]:
    jti = uuid.uuid4().hex
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes or _settings.access_token_minutes)
    payload = {"sub": user_id, "role": role, "jti": jti, "exp": exp, "iat": datetime.now(timezone.utc)}
    token = jwt.encode(payload, _settings.jwt_secret, algorithm="HS256")
    return token, jti, exp


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, _settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


# ---------------- path safety ----------------
class UnsafePathError(ValueError):
    pass


def safe_join(root: Path, user_path: str) -> Path:
    """Resolve `user_path` under `root`; reject traversal/symlink escapes."""
    if "\x00" in user_path:
        raise UnsafePathError("NUL byte in path")
    if Path(user_path).is_absolute():
        raise UnsafePathError(f"Absolute paths are not allowed: {user_path}")
    p = (root / user_path).resolve()
    root_r = root.resolve()
    if p != root_r and root_r not in p.parents:
        raise UnsafePathError(f"Path escapes sandbox root: {user_path}")
    return p


# ---------------- rate limiter (in-memory, per-process) ----------------
class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


rate_limiter = RateLimiter()


def redact(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "*" * len(value)
    return value[:keep] + "…" + value[-keep:]


SECRET_PATTERN = None

def sanitize_output(text: str) -> str:
    """Best-effort redaction of secrets in tool output / logs."""
    import re
    patterns = [
        r"(sk-[A-Za-z0-9_\-]{8})[A-Za-z0-9_\-]+",
        r"(ghp_)[A-Za-z0-9]{20,}",
        r"((?:api[_-]?key|token|password|secret)\s*[=:]\s*)(\S+)",
        r"(Authorization:\s*Bearer\s+)(\S+)",
    ]
    for pat in patterns:
        if "(" in pat and pat.count("(") >= 2:
            text = re.sub(pat, lambda m: m.group(1) + "***REDACTED***", text, flags=re.IGNORECASE)
        else:
            text = re.sub(pat, "***REDACTED***", text, flags=re.IGNORECASE)
    return text
