"""Fail-open UGACORE adapter for UGAFORCE-HR.

UGAFORCE-HR remains authoritative for HR business data and its local audit log.
This adapter only forwards cross-cutting monitoring/audit signals when UGACORE
is configured. A slow or unavailable platform service must never break an HR
user request.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.request
from typing import Any

UGACORE_URL = os.getenv("UGACORE_URL", "").rstrip("/")
SERVICE_ID = os.getenv("UGACORE_SERVICE_ID", "ugaforce-hr")
SERVICE_KEY = os.getenv("UGACORE_SERVICE_KEY", "")
TIMEOUT_SECONDS = float(os.getenv("UGACORE_TIMEOUT_SECONDS", "1.5"))


def _post(path: str, payload: dict[str, Any]) -> None:
    if not UGACORE_URL or not SERVICE_KEY:
        return
    try:
        body = json.dumps(payload, default=str).encode("utf-8")
        request = urllib.request.Request(
            f"{UGACORE_URL}{path}",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Service-ID": SERVICE_ID,
                "X-Service-Key": SERVICE_KEY,
            },
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS):
            pass
    except Exception:
        # Deliberately fail-open. Local HR transactions/audit remain authoritative.
        return


def _background(path: str, payload: dict[str, Any]) -> None:
    threading.Thread(target=_post, args=(path, payload), daemon=True).start()


def heartbeat(status: str = "online", **metadata: Any) -> None:
    _background("/monitoring/heartbeat", {"service": SERVICE_ID, "status": status, "metadata": metadata})


def mirror_audit(action: str, entity_type: str, entity_id: str, actor_id: str | None = None, **metadata: Any) -> None:
    """Mirror an HR audit event to UGACORE; never replaces the local HR audit log."""
    _background(
        "/audit/events",
        {
            "service": SERVICE_ID,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "actor_id": actor_id,
            "metadata": metadata,
        },
    )
