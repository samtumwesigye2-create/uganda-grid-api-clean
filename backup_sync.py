"""Best-effort backup client shared by UGAMAP and UGASHIP."""
import json
import os
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

BACKUP_SERVICE_URL=os.environ.get("BACKUP_SERVICE_URL","https://uga-backup-service-production.up.railway.app").rstrip("/")
BACKUP_SYNC_TOKEN=os.environ.get("BACKUP_SYNC_TOKEN","").strip()
_MAX_WORKERS=4
_MAX_OUTSTANDING=100
_executor=ThreadPoolExecutor(max_workers=_MAX_WORKERS,thread_name_prefix="uga-backup-sync")
_slots=threading.BoundedSemaphore(_MAX_OUTSTANDING)
_status_lock=threading.Lock()
_status={"last_attempt":None,"last_success":None,"last_error":None,"queued":0,"active":0,"completed":0,"failed":0,"dropped":0,"max_workers":_MAX_WORKERS,"max_outstanding":_MAX_OUTSTANDING,"UGAMAP":{"completed":0,"failed":0,"dropped":0,"last_success":None,"last_error":None},"UGASHIP":{"completed":0,"failed":0,"dropped":0,"last_success":None,"last_error":None}}

def sync_client_status():
    with _status_lock:return json.loads(json.dumps(_status))
def _set(**values):
    with _status_lock:_status.update(values)
def _change(key,delta):
    with _status_lock:_status[key]=max(0,int(_status.get(key,0))+delta)
def _source_change(source,key,delta=0,value=None):
    if source not in ("UGAMAP","UGASHIP"):return
    with _status_lock:
        state=_status[source]
        if value is not None:state[key]=value
        else:state[key]=max(0,int(state.get(key,0))+delta)
def _send(payload):
    source=payload.get("source");_change("queued",-1);_change("active",1);success=False;error=None
    try:
        if not BACKUP_SYNC_TOKEN:
            error="BACKUP_SYNC_TOKEN not configured";_set(last_error=error);return
        for attempt in range(3):
            _set(last_attempt=datetime.now(timezone.utc).isoformat())
            try:
                req=urllib.request.Request(f"{BACKUP_SERVICE_URL}/sync",data=json.dumps(payload,default=str).encode("utf-8"),method="POST",headers={"Content-Type":"application/json","x-backup-token":BACKUP_SYNC_TOKEN})
                with urllib.request.urlopen(req,timeout=6) as response:
                    response.read()
                    if 200<=response.status<300:
                        success=True;now=datetime.now(timezone.utc).isoformat();_set(last_success=now,last_error=None);_source_change(source,"last_success",value=now);_source_change(source,"last_error",value="");return
                    raise RuntimeError(f"backup HTTP {response.status}")
            except Exception as exc:
                error=f"{type(exc).__name__}: {exc}"[:240];_set(last_error=error)
                if attempt<2:time.sleep(1.5*(attempt+1))
    finally:
        _change("active",-1);_change("completed",1);_source_change(source,"completed",1)
        if not success:_change("failed",1);_source_change(source,"failed",1);_source_change(source,"last_error",value=error or "backup sync failed")
        _slots.release()
def backup_event(source,entity_type,entity_id,action,data=None):
    payload={"source":source,"entity_type":entity_type,"entity_id":str(entity_id),"action":action,"data":data or {},"source_updated_at":datetime.now(timezone.utc).isoformat()}
    if not _slots.acquire(blocking=False):
        error="backup sync backlog full; event left for reconciliation";_change("dropped",1);_change("failed",1);_source_change(source,"dropped",1);_source_change(source,"failed",1);_source_change(source,"last_error",value=error);_set(last_error=error);return
    _change("queued",1)
    try:_executor.submit(_send,payload)
    except Exception as exc:
        error=f"queue error: {type(exc).__name__}: {exc}"[:240];_change("queued",-1);_change("failed",1);_source_change(source,"failed",1);_source_change(source,"last_error",value=error);_slots.release();_set(last_error=error)
def ugamap_backup(entity_type,entity_id,action,data=None):backup_event("UGAMAP",entity_type,entity_id,action,data)
def ugaship_backup(entity_type,entity_id,action,data=None):backup_event("UGASHIP",entity_type,entity_id,action,data)
