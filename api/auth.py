"""Minimal operator auth for the write endpoints (park / checkout).

Deliberately simple: one shared operator password (env var), a
stateless HMAC-signed bearer token with an expiry. No user table, no
password hashing library, because there's exactly one credential to
check and nothing is stored at rest. If this ever needs per-user
accounts or roles, replace this module rather than growing it.

Required env vars:
  OPERATOR_PASSWORD  - the shared password operators log in with
  SECRET_KEY         - random string used to sign tokens (NOT the password)
"""

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Header, HTTPException

TOKEN_TTL_SECONDS = 12 * 60 * 60  # 12 hours


def _secret() -> bytes:
    secret = os.environ.get("SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "SECRET_KEY environment variable is not set. "
            "Add it in Vercel: Project Settings -> Environment Variables "
            "(use a long random string, e.g. `openssl rand -hex 32`)."
        )
    return secret.encode()


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded)


def _sign(payload_b64: str) -> str:
    sig = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).digest()
    return _b64encode(sig)


def create_token() -> str:
    """Issue a signed token that's valid for TOKEN_TTL_SECONDS."""
    payload = {"exp": int(time.time()) + TOKEN_TTL_SECONDS}
    payload_b64 = _b64encode(json.dumps(payload).encode())
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_token(token: str) -> bool:
    """Check a token's signature and expiry. Never raises on bad input."""
    if not token or "." not in token:
        return False
    payload_b64, _, sig = token.partition(".")
    if not hmac.compare_digest(_sign(payload_b64), sig):
        return False
    try:
        payload = json.loads(_b64decode(payload_b64))
    except Exception:
        return False
    return isinstance(payload, dict) and payload.get("exp", 0) > time.time()


def check_password(password: str) -> bool:
    """Timing-safe comparison against OPERATOR_PASSWORD."""
    expected = os.environ.get("OPERATOR_PASSWORD")
    if not expected:
        raise RuntimeError(
            "OPERATOR_PASSWORD environment variable is not set. "
            "Add it in Vercel: Project Settings -> Environment Variables."
        )
    return hmac.compare_digest(password or "", expected)


def require_auth(authorization: str = Header(default=None)) -> None:
    """FastAPI dependency: raises 401 unless a valid bearer token is present.

    Usage: @app.post("/api/park", dependencies=[Depends(require_auth)])
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Login required. Include 'Authorization: Bearer <token>'.",
        )
    token = authorization[len("Bearer "):]
    if not verify_token(token):
        raise HTTPException(
            status_code=401,
            detail="Session expired or invalid. Please log in again.",
        )
