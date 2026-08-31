"""Best-effort backup client shared by UGAMAP and UGASHIP.

The production app never fails because the backup service is unavailable.
Configure in Railway:
  BACKUP_SERVICE_URL=https://uga-backup-service-production.up.railway.app
  BACKUP_SYNC_TOKEN=<same sync token configured on uga-backup-service>
"""
import json
import os
import threading
import urllib.request
from datetime import datetime, timezone

BACKUP_SERVICE_URL = os.environ.get("BACKUP_SERVICE_URL", "https://uga-backup-service-production.up.railway.app").rstrip("/")
BACKUP_SYNC_TOKEN = os.environ.get("BACKUP_SYNC_TOKEN", "")


def _send(payload: dict) -> None:
    if not BACKUP_SYNC_TOKEN:
        return
    try:
        req = urllib.request.Request(
            f"{BACKUP_SERVICE_URL}/sync",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-backup-token": BACKUP_SYNC_TOKEN,
            },
        )
        with urllib.request.urlopen(req, timeout=4) as response:
            response.read()
    except Exception:
        # Backup must never block or break UGAMAP/UGASHIP production traffic.
        pass


def backup_event(source: str, entity_type: str, entity_id: str, action: str, data=None) -> None:
    payload = {
        "source": source,
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "action": action,
        "data": data or {},
        "source_updated_at": datetime.now(timezone.utc).isoformat(),
    }
    threading.Thread(target=_send, args=(payload,), daemon=True).start()


def ugamap_backup(entity_type: str, entity_id: str, action: str, data=None) -> None:
    backup_event("UGAMAP", entity_type, entity_id, action, data)


def ugaship_backup(entity_type: str, entity_id: str, action: str, data=None) -> None:
    backup_event("UGASHIP", entity_type, entity_id, action, data)
