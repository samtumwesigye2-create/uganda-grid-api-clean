"""Readiness, live-sync, reconciliation and freshness diagnostics."""
import json,os,urllib.request
from datetime import datetime,timezone
from fastapi import APIRouter
from backup_sync import sync_client_status
from backup_reconcile import reconcile_status
router=APIRouter();BACKUP_SERVICE_URL=os.environ.get("BACKUP_SERVICE_URL","https://uga-backup-service-production.up.railway.app").rstrip("/")
MAX_BACKUP_AGE_SECONDS=max(300,int(os.environ.get("MAX_BACKUP_AGE_SECONDS","900")))
def _dt(iso):
 if not iso:return None
 try:return datetime.fromisoformat(iso.replace("Z","+00:00"))
 except Exception:return None
def _age(iso):
 d=_dt(iso)
 return max(0,(datetime.now(timezone.utc)-d).total_seconds()) if d else None
def _freshness(state):
 state=state or {};iso=state.get("last_success");age=_age(iso);err=state.get("last_error");return {"last_success":iso,"age_seconds":round(age,1) if age is not None else None,"last_error":err,"fresh":age is not None and age<=MAX_BACKUP_AGE_SECONDS and not err,"records":state.get("records")}
def _live_freshness(state):
 state=state or {};iso=state.get("last_success");age=_age(iso);err=state.get("last_error") or None;return {"last_success":iso,"age_seconds":round(age,1) if age is not None else None,"last_error":err,"fresh":age is not None and age<=MAX_BACKUP_AGE_SECONDS and not err,"completed":state.get("completed",0),"failed":state.get("failed",0),"dropped":state.get("dropped",0)}
@router.get("/backup/status",tags=["Backup"])
def backup_status():
 token=bool(os.environ.get("BACKUP_SYNC_TOKEN","").strip());reachable=False;db_ok=False;remote=None;error=None
 try:
  with urllib.request.urlopen(f"{BACKUP_SERVICE_URL}/health",timeout=4) as response:remote=json.loads(response.read().decode());reachable=200<=response.status<300;db_ok=remote.get("database")=="connected"
 except Exception as exc:error=f"{type(exc).__name__}: {exc}"[:180]
 client=sync_client_status();reconcile=reconcile_status();ugamap=_freshness(reconcile.get("UGAMAP"));ugaship=_freshness(reconcile.get("UGASHIP"));live_sources={"UGAMAP":_live_freshness(client.get("UGAMAP")),"UGASHIP":_live_freshness(client.get("UGASHIP"))};fresh=ugamap["fresh"] and ugaship["fresh"];ready=token and reachable and db_ok;records=(remote or {}).get("records",{});queue={"queued":client.get("queued",0),"active":client.get("active",0),"completed":client.get("completed",0),"failed":client.get("failed",0),"dropped":client.get("dropped",0),"max_workers":client.get("max_workers"),"max_outstanding":client.get("max_outstanding")}
 reasons=[]
 if not token:reasons.append("sync token missing")
 if not reachable:reasons.append("backup service unreachable")
 if reachable and not db_ok:reasons.append("backup database disconnected")
 if not ugamap["fresh"]:reasons.append("UGAMAP reconciliation stale or unhealthy")
 if not ugaship["fresh"]:reasons.append("UGASHIP reconciliation stale or unhealthy")
 if queue["dropped"]:reasons.append(f"{queue['dropped']} live sync events dropped; reconciliation required")
 health="healthy" if ready and fresh and not queue["dropped"] else ("degraded" if ready else "unavailable")
 return {"status":health,"status_reasons":reasons,"backup_enabled":token,"backup_service_reachable":reachable,"backup_database_connected":db_ok,"sync_ready":ready,"backup_fresh":fresh,"source_freshness":{"UGAMAP":ugamap,"UGASHIP":ugaship},"live_sync_sources":live_sources,"sync_queue":queue,"max_backup_age_seconds":MAX_BACKUP_AGE_SECONDS,"backup_counts":{"UGAMAP":records.get("UGAMAP"),"UGASHIP":records.get("UGASHIP"),"deleted":records.get("deleted"),"snapshots":records.get("snapshots")},"reconciliation":reconcile,"backup_service":BACKUP_SERVICE_URL,"checked_at":datetime.now(timezone.utc).isoformat(),"last_sync_attempt":client.get("last_attempt"),"last_sync_success":client.get("last_success"),"last_sync_error":client.get("last_error"),"remote_last_activity":(remote or {}).get("last_activity"),"remote_health":remote,"error":error}
