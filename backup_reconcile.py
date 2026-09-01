"""Automatic best-effort reconciliation into the independent backup service."""
import hashlib,json,os,sqlite3,threading,time,urllib.request
from datetime import datetime,timezone
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
BACKUP_SERVICE_URL=os.environ.get("BACKUP_SERVICE_URL","https://uga-backup-service-production.up.railway.app").rstrip("/")
BACKUP_SYNC_TOKEN=os.environ.get("BACKUP_SYNC_TOKEN","").strip();POLL_SECONDS=max(15,int(os.environ.get("BACKUP_RECONCILE_SECONDS","30")))
SHIP_DB=os.path.join(BASE_DIR,"data_hub.db");ADDRESS_FILE=os.path.join(BASE_DIR,"entebbe_database.json");STATE_FILE=os.path.join(BASE_DIR,".backup_reconcile_state.json")
_started=False;_lock=threading.Lock();_state_lock=threading.Lock();_last_ship_hash=None;_last_address_hash=None;_previous_shipment_ids=set();_previous_address_ids=set();_pending_deletions={}
_state={"running":False,"started_at":None,"last_attempt":None,"last_success":None,"last_error":None,"UGAMAP":{"records":None,"last_success":None},"UGASHIP":{"records":None,"last_success":None}}
def _now():return datetime.now(timezone.utc).isoformat()
def reconcile_status():
 with _state_lock:return json.loads(json.dumps(_state))
def _set(**values):
 with _state_lock:_state.update(values)
def _source_ok(source,count):
 now=_now()
 with _state_lock:_state[source]={"records":count,"last_success":now,"last_error":None};_state["last_success"]=now;_state["last_error"]=None
def _source_error(source,message):
 with _state_lock:
  current=dict(_state.get(source) or {});current["last_error"]=message;_state[source]=current;_state["last_error"]=message
def _hash(records):return hashlib.sha256(json.dumps(records,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
def _load_state():
 global _previous_shipment_ids,_previous_address_ids
 try:
  with open(STATE_FILE,encoding="utf-8") as f:s=json.load(f)
  _previous_shipment_ids=set(map(str,s.get("shipment_ids",[])));_previous_address_ids=set(map(str,s.get("address_ids",[])))
 except Exception:pass
def _save_state():
 try:
  tmp=STATE_FILE+".tmp"
  with open(tmp,"w",encoding="utf-8") as f:json.dump({"shipment_ids":sorted(_previous_shipment_ids),"address_ids":sorted(_previous_address_ids)},f,separators=(",",":"))
  os.replace(tmp,STATE_FILE)
 except Exception as exc:print(f"[backup-reconcile-state] {type(exc).__name__}: {exc}")
def _request(path,payload,timeout=20):
 if not BACKUP_SYNC_TOKEN:return None
 req=urllib.request.Request(f"{BACKUP_SERVICE_URL}{path}",data=json.dumps(payload,default=str).encode(),method="POST",headers={"Content-Type":"application/json","x-backup-token":BACKUP_SYNC_TOKEN})
 with urllib.request.urlopen(req,timeout=timeout) as response:return response.read()
def _bulk(source,entity_type,records):
 for i in range(0,len(records),500):_request("/sync/bulk",{"source":source,"entity_type":entity_type,"records":records[i:i+500]},30)
def _delete(source,entity_type,entity_id):_request("/sync",{"source":source,"entity_type":entity_type,"entity_id":str(entity_id),"action":"delete","data":{}})
def _safe_deletions(source,entity_type,previous,current):
 key=f"{source}:{entity_type}";missing=previous-current
 if not missing:_pending_deletions.pop(key,None);return True
 large=bool(previous) and (not current or len(missing)>max(25,int(len(previous)*0.25)))
 if large:
  signature=_hash(sorted(missing));pending=_pending_deletions.get(key)
  if not pending or pending.get("signature")!=signature:
   _pending_deletions[key]={"signature":signature,"seen":1};_source_error(source,f"Deletion protection waiting for confirmation: {len(missing)} of {len(previous)} {entity_type} removals");return False
  pending["seen"]+=1
  if pending["seen"]<3:_source_error(source,f"Deletion protection confirmation {pending['seen']}/3: {len(missing)} of {len(previous)} {entity_type} removals");return False
 _pending_deletions.pop(key,None)
 for entity_id in missing:_delete(source,entity_type,entity_id)
 return True
def _read_shipments():
 if not os.path.exists(SHIP_DB):raise FileNotFoundError(f"Shipment database missing: {SHIP_DB}")
 conn=sqlite3.connect(SHIP_DB);conn.row_factory=sqlite3.Row
 try:
  if not conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shipments'").fetchone():raise RuntimeError("shipments table missing")
  return [dict(r) for r in conn.execute("SELECT * FROM shipments").fetchall()]
 finally:conn.close()
def _sync_shipments():
 global _last_ship_hash,_previous_shipment_ids
 try:rows=_read_shipments()
 except Exception as exc:_source_error("UGASHIP",f"Source read failed: {type(exc).__name__}: {exc}"[:240]);return False
 rows.sort(key=lambda r:str(r.get("id") or r.get("shipment_number") or ""));digest=_hash(rows)
 if digest!=_last_ship_hash:
  current={str(r.get("id") or r.get("shipment_number")) for r in rows if r.get("id") or r.get("shipment_number")}
  if rows:_bulk("UGASHIP","shipment",rows)
  if not _safe_deletions("UGASHIP","shipment",_previous_shipment_ids,current):return False
  _previous_shipment_ids=current;_last_ship_hash=digest;_save_state()
 _source_ok("UGASHIP",len(rows));return True
def _read_addresses():
 if not os.path.exists(ADDRESS_FILE):raise FileNotFoundError(f"Address database missing: {ADDRESS_FILE}")
 with open(ADDRESS_FILE,encoding="utf-8") as f:data=json.load(f)
 if not isinstance(data,list):raise ValueError("Address database root must be a JSON list")
 out=[]
 for row in data:
  if isinstance(row,dict):
   entity_id=row.get("grid_id") or row.get("id")
   if entity_id is not None:item=dict(row);item["id"]=str(entity_id);out.append(item)
 out.sort(key=lambda r:r["id"]);return out
def _sync_addresses():
 global _last_address_hash,_previous_address_ids
 try:rows=_read_addresses()
 except Exception as exc:_source_error("UGAMAP",f"Source read failed: {type(exc).__name__}: {exc}"[:240]);return False
 digest=_hash(rows)
 if digest!=_last_address_hash:
  current={r["id"] for r in rows}
  if rows:_bulk("UGAMAP","address",rows)
  if not _safe_deletions("UGAMAP","address",_previous_address_ids,current):return False
  _previous_address_ids=current;_last_address_hash=digest;_save_state()
 _source_ok("UGAMAP",len(rows));return True
def _worker():
 _set(running=True,started_at=_now())
 while True:
  _set(last_attempt=_now())
  try:
   if BACKUP_SYNC_TOKEN:_sync_shipments();_sync_addresses()
   else:_set(last_error="BACKUP_SYNC_TOKEN not configured")
  except Exception as exc:_set(last_error=f"{type(exc).__name__}: {exc}"[:240]);print(f"[backup-reconcile] {type(exc).__name__}: {exc}")
  time.sleep(POLL_SECONDS)
def start_backup_reconciler():
 global _started
 with _lock:
  if _started:return
  _load_state();_started=True;threading.Thread(target=_worker,name="uga-backup-reconcile",daemon=True).start()
start_backup_reconciler()
