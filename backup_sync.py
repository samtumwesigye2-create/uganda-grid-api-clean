"""Best-effort backup client shared by UGAMAP and UGASHIP."""
import json
import os
import threading
import time
import urllib.request
from datetime import datetime, timezone

BACKUP_SERVICE_URL=os.environ.get("BACKUP_SERVICE_URL","https://uga-backup-service-production.up.railway.app").rstrip("/")
BACKUP_SYNC_TOKEN=os.environ.get("BACKUP_SYNC_TOKEN","").strip()
_status_lock=threading.Lock()
_status={"last_attempt":None,"last_success":None,"last_error":None}


def sync_client_status():
    with _status_lock:return dict(_status)


def _set(**values):
    with _status_lock:_status.update(values)


def _send(payload):
    if not BACKUP_SYNC_TOKEN:
        _set(last_error="BACKUP_SYNC_TOKEN not configured")
        return
    for attempt in range(3):
        now=datetime.now(timezone.utc).isoformat();_set(last_attempt=now)
        try:
            req=urllib.request.Request(f"{BACKUP_SERVICE_URL}/sync",data=json.dumps(payload,default=str).encode("utf-8"),method="POST",headers={"Content-Type":"application/json","x-backup-token":BACKUP_SYNC_TOKEN})
            with urllib.request.urlopen(req,timeout=6) as response:
                response.read()
                if 200<=response.status<300:
                    _set(last_success=datetime.now(timezone.utc).isoformat(),last_error=None)
                    return
                raise RuntimeError(f"backup HTTP {response.status}")
        except Exception as exc:
            _set(last_error=f"{type(exc).__name__}: {exc}"[:240])
            if attempt<2:time.sleep(1.5*(attempt+1))


def backup_event(source,entity_type,entity_id,action,data=None):
    payload={"source":source,"entity_type":entity_type,"entity_id":str(entity_id),"action":action,"data":data or {},"source_updated_at":datetime.now(timezone.utc).isoformat()}
    threading.Thread(target=_send,args=(payload,),daemon=True).start()


def ugamap_backup(entity_type,entity_id,action,data=None):backup_event("UGAMAP",entity_type,entity_id,action,data)
def ugaship_backup(entity_type,entity_id,action,data=None):backup_event("UGASHIP",entity_type,entity_id,action,data)
