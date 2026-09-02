"""Fail-open UGAMAP telemetry client for the independent Data Relay Server.

No credentials are stored in source. Configure DRS_URL and DRS_SERVICE_KEY in the
UGAMAP deployment environment. Relay failures never fail a UGAMAP request.
"""
from __future__ import annotations

import json
import os
import threading
import time
from urllib import request

DRS_URL = os.getenv("DRS_URL", "").rstrip("/")
DRS_SERVICE_ID = os.getenv("DRS_SERVICE_ID", "ugamap")
DRS_SERVICE_KEY = os.getenv("DRS_SERVICE_KEY", "")
_TIMEOUT = float(os.getenv("DRS_TIMEOUT_SECONDS", "1.5"))

_SENSITIVE = {
    "authorization", "cookie", "set-cookie", "password", "passwd", "secret",
    "token", "access_token", "refresh_token", "api_key", "apikey", "private_key",
}


def _clean(value):
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if str(k).lower() in _SENSITIVE else _clean(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value[:100]]
    if isinstance(value, str):
        return value[:4000]
    return value


def configured() -> bool:
    return bool(DRS_URL and DRS_SERVICE_KEY)


def _post_event(event: dict) -> None:
    if not configured():
        return
    body = json.dumps(event, separators=(",", ":")).encode("utf-8")
    req = request.Request(
        DRS_URL + "/events",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Service-ID": DRS_SERVICE_ID,
            "X-Service-Key": DRS_SERVICE_KEY,
        },
    )
    try:
        with request.urlopen(req, timeout=_TIMEOUT):
            pass
    except Exception:
        # Observability is deliberately outside UGAMAP's critical path.
        pass


def emit(category: str, severity: str = "info", payload: dict | None = None) -> None:
    event = {
        "category": category,
        "severity": severity,
        "source": "ugamap",
        "timestamp": time.time(),
        "payload": _clean(payload or {}),
    }
    threading.Thread(target=_post_event, args=(event,), daemon=True).start()
