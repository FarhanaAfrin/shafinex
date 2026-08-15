"""Single-user bearer auth.

No user table: one password in an env var, exchanged for an HMAC-signed token
with an expiry. Stdlib only — nothing to keep patched.
"""

from typing import Optional

import base64
import hmac
import json
import time
from hashlib import sha256

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

bearer_scheme = HTTPBearer(auto_error=False)


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(payload: str) -> str:
    secret = get_settings().secret_key.encode()
    return _b64e(hmac.new(secret, payload.encode(), sha256).digest())


def create_token() -> tuple[str, int]:
    settings = get_settings()
    expires_at = int(time.time()) + settings.token_ttl_days * 86400
    payload = _b64e(json.dumps({"sub": "owner", "exp": expires_at}).encode())
    return f"{payload}.{_sign(payload)}", expires_at


def verify_password(password: str) -> bool:
    return hmac.compare_digest(password or "", get_settings().app_password)


def _token_is_valid(token: str) -> bool:
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return False
    if not hmac.compare_digest(signature, _sign(payload)):
        return False
    try:
        data = json.loads(_b64d(payload))
    except (ValueError, json.JSONDecodeError):
        return False
    return int(data.get("exp", 0)) > time.time()


def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> str:
    if credentials is None or not _token_is_valid(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "owner"
