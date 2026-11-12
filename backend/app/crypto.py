"""Small Fernet wrapper for integration secrets stored at rest."""
from __future__ import annotations

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


def _fernet() -> Fernet:
    s = get_settings()
    if s.secrets_encryption_key:
        key = s.secrets_encryption_key.encode()
    else:  # derive a stable key from jwt secret (documented trade-off)
        digest = hashlib.sha256((s.jwt_secret + ":integration-secrets").encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_json(data: dict) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_json(token: str) -> dict:
    if not token:
        return {}
    try:
        return json.loads(_fernet().decrypt(token.encode()))
    except (InvalidToken, json.JSONDecodeError):
        return {}
