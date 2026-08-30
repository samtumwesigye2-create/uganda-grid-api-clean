"""
auth_shared.py
Drop into BOTH backends (website + UGAMAP).
Requires: pip install itsdangerous

Set on BOTH deployments (same value):
    SESSION_SECRET=<random string>
Generate with: python -c "import secrets; print(secrets.token_hex(32))"
"""

import os
import time
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request, Response, HTTPException

SESSION_SECRET = os.environ.get("SESSION_SECRET")
if not SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET env var is not set")

COOKIE_DOMAIN = os.environ.get("SESSION_COOKIE_DOMAIN", ".ugandagrid.com")
COOKIE_NAME = "ugandagrid_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 14  # 14 days

_serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="ugandagrid-session")


def create_session_cookie(response: Response, user_id: str, extra: dict | None = None) -> None:
    payload = {"uid": user_id, "iat": int(time.time())}
    if extra:
        payload.update(extra)
    token = _serializer.dumps(payload)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        domain=COOKIE_DOMAIN,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, domain=COOKIE_DOMAIN, path="/")


def read_session(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        return _serializer.loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


def require_session(request: Request) -> dict:
    session = read_session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return session
