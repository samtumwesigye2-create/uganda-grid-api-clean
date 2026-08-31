"""Small readiness endpoint for the UGAMAP/UGASHIP backup connection."""

import json
import os
import urllib.request

from fastapi import APIRouter

router = APIRouter()

BACKUP_SERVICE_URL = os.environ.get(
    "BACKUP_SERVICE_URL",
    "https://uga-backup-service-production.up.railway.app",
).rstrip("/")


@router.get("/backup/status", tags=["Backup"])
def backup_status():
    token_configured = bool(os.environ.get("BACKUP_SYNC_TOKEN", "").strip())
    reachable = False
    remote = None
    error = None

    try:
        with urllib.request.urlopen(f"{BACKUP_SERVICE_URL}/health", timeout=4) as response:
            remote = json.loads(response.read().decode("utf-8"))
            reachable = 200 <= response.status < 300
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:180]

    return {
        "backup_enabled": token_configured,
        "backup_service_reachable": reachable,
        "sync_ready": token_configured and reachable,
        "remote_health": remote,
        "error": error,
    }
