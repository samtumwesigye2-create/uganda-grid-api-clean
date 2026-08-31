"""Automatic best-effort reconciliation into the independent backup service."""
import hashlib
import json
import os
import sqlite3
import threading
import time
import urllib.request

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
BACKUP_SERVICE_URL=os.environ.get("BACKUP_SERVICE_URL","https://uga-backup-service-production.up.railway.app").rstrip("/")
BACKUP_SYNC_TOKEN=os.environ.get("BACKUP_SYNC_TOKEN","").strip()
POLL_SECONDS=max(15,int(os.environ.get("BACKUP_RECONCILE_SECONDS","30")))
SHIP_DB=os.path.join(BASE_DIR,"data_hub.db")
ADDRESS_FILE=os.path.join(BASE_DIR,"entebbe_database.json")
_started=False
_lock=threading.Lock()
_last_ship_hash=None
_last_address_hash=None
_previous_shipment_ids=set()
_previous_address_ids=set()


def _hash(records):
    raw=json.dumps(records,sort_keys=True,separators=(",",":"),default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _request(path,payload,timeout=20):
    if not BACKUP_SYNC_TOKEN:return None
    req=urllib.request.Request(f"{BACKUP_SERVICE_URL}{path}",data=json.dumps(payload,default=str).encode("utf-8"),method="POST",headers={"Content-Type":"application/json","x-backup-token":BACKUP_SYNC_TOKEN})
    with urllib.request.urlopen(req,timeout=timeout) as response:return response.read()


def _bulk(source,entity_type,records):
    for i in range(0,len(records),500):
        _request("/sync/bulk",{"source":source,"entity_type":entity_type,"records":records[i:i+500]},30)


def _delete(source,entity_type,entity_id):
    _request("/sync",{"source":source,"entity_type":entity_type,"entity_id":str(entity_id),"action":"delete","data":{}})


def _read_shipments():
    if not os.path.exists(SHIP_DB):return []
    conn=sqlite3.connect(SHIP_DB);conn.row_factory=sqlite3.Row
    try:
        if not conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shipments'").fetchone():return []
        return [dict(r) for r in conn.execute("SELECT * FROM shipments").fetchall()]
    finally:conn.close()


def _sync_shipments():
    global _last_ship_hash,_previous_shipment_ids
    rows=_read_shipments();rows.sort(key=lambda r:str(r.get("id") or r.get("shipment_number") or ""))
    digest=_hash(rows)
    if digest==_last_ship_hash:return
    current={str(r.get("id") or r.get("shipment_number")) for r in rows if r.get("id") or r.get("shipment_number")}
    if rows:_bulk("UGASHIP","shipment",rows)
    for entity_id in _previous_shipment_ids-current:_delete("UGASHIP","shipment",entity_id)
    _previous_shipment_ids=current;_last_ship_hash=digest


def _read_addresses():
    if not os.path.exists(ADDRESS_FILE):return []
    try:
        with open(ADDRESS_FILE,"r",encoding="utf-8") as fh:data=json.load(fh)
    except (OSError,json.JSONDecodeError):return []
    if not isinstance(data,list):return []
    out=[]
    for row in data:
        if not isinstance(row,dict):continue
        entity_id=row.get("grid_id") or row.get("id")
        if entity_id is None:continue
        item=dict(row);item["id"]=str(entity_id);out.append(item)
    out.sort(key=lambda r:r["id"])
    return out


def _sync_addresses():
    global _last_address_hash,_previous_address_ids
    rows=_read_addresses();digest=_hash(rows)
    if digest==_last_address_hash:return
    current={r["id"] for r in rows}
    if rows:_bulk("UGAMAP","address",rows)
    for entity_id in _previous_address_ids-current:_delete("UGAMAP","address",entity_id)
    _previous_address_ids=current;_last_address_hash=digest


def _worker():
    while True:
        try:
            if BACKUP_SYNC_TOKEN:
                _sync_shipments();_sync_addresses()
        except Exception as exc:print(f"[backup-reconcile] {type(exc).__name__}: {exc}")
        time.sleep(POLL_SECONDS)


def start_backup_reconciler():
    global _started
    with _lock:
        if _started:return
        _started=True
        threading.Thread(target=_worker,name="uga-backup-reconcile",daemon=True).start()

start_backup_reconciler()
