"""Vector 5250 production integration entrypoint.

Vector 5250 is an independent enterprise operations system and system of record.
It keeps its own persistence, command set, custody state and audit/event journal.
Cross-system integration is API/event based. Relay monitors integrity and the
backup service receives a best-effort replicated event stream.
"""
from pathlib import Path
import json
import os
import sqlite3
import time
import uuid
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from auth import ADMIN_PASSCODE, require_permission
from data_relay_client import emit as relay_emit
from backup_sync import vector5250_backup, sync_client_status

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("VECTOR5250_DB_PATH") or (BASE_DIR / "vector5250.db"))

app = FastAPI(title="Vector 5250", version="1.2.0")

COMMANDS = {
    "MIGO": {"screen": "RECEIVING", "label": "Goods Receipt / Movement"},
    "VRCV": {"screen": "RECEIVING", "label": "Receive Inbound Freight"},
    "VSCAN": {"screen": "SCAN", "label": "Scan Package / Freight"},
    "VCUST": {"screen": "CUSTODY", "label": "Custody Ledger"},
    "MB51": {"screen": "INVENTORY", "label": "Inventory Movement History"},
    "MB52": {"screen": "INVENTORY", "label": "Inventory Lookup"},
    "MI01": {"screen": "CYCLE", "label": "Create Physical Inventory Count"},
    "MI04": {"screen": "CYCLE", "label": "Enter Count"},
    "MB5T": {"screen": "TRANSFERS", "label": "Stock in Transfer"},
    "VL06O": {"screen": "OUTBOUND", "label": "Outbound Monitor"},
    "LT03": {"screen": "PICKING", "label": "Create Pick Task"},
    "ZV5250": {"screen": "MENU", "label": "Vector 5250 Home"},
}

UGATU_INTEROP_MAP = {
    "MIGO": ["U-4030"], "VRCV": ["U-4030"], "VSCAN": ["U-1510", "U-1520"],
    "VCUST": ["U-1590"], "MB51": ["U-4190"], "MB52": ["U-4110"],
    "MI01": ["U-4150"], "MI04": ["U-4150"], "MB5T": ["U-4400"],
    "VL06O": ["U-4200"], "LT03": ["U-4230"],
}

class ReceiveRequest(BaseModel):
    reference: str = Field(min_length=1, max_length=120)
    warehouse_id: str = Field(default="main", min_length=1, max_length=80)
    sku: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0)
    unit_type: str = Field(default="package", pattern="^(package|freight|pallet)$")
    location: str | None = Field(default=None, max_length=120)
    condition: str = Field(default="good", max_length=40)
    notes: str | None = Field(default=None, max_length=1000)
    client_request_id: str | None = Field(default=None, max_length=160)

class ScanRequest(BaseModel):
    code: str = Field(min_length=1, max_length=200)
    warehouse_id: str = Field(default="main", min_length=1, max_length=80)
    reference: str | None = Field(default=None, max_length=120)
    scan_type: str = Field(default="package", pattern="^(package|freight|pallet|location)$")
    action: str = Field(default="receive", pattern="^(receive|verify|move|load|unload|handoff)$")
    location: str | None = Field(default=None, max_length=120)
    client_request_id: str | None = Field(default=None, max_length=160)


def _db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _db()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS vector_events(
          id TEXT PRIMARY KEY,event_type TEXT NOT NULL,command TEXT,object_type TEXT,
          object_id TEXT,payload_json TEXT NOT NULL,actor_id TEXT,created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS vector_inventory(
          warehouse_id TEXT NOT NULL,sku TEXT NOT NULL,quantity REAL NOT NULL DEFAULT 0,
          updated_at REAL NOT NULL,PRIMARY KEY(warehouse_id,sku));
        CREATE TABLE IF NOT EXISTS vector_transactions(
          id TEXT PRIMARY KEY,command TEXT NOT NULL,status TEXT NOT NULL,reference TEXT,
          actor_id TEXT,payload_json TEXT NOT NULL,client_request_id TEXT UNIQUE,created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS vector_receipts(
          id TEXT PRIMARY KEY,reference TEXT NOT NULL,warehouse_id TEXT NOT NULL,sku TEXT NOT NULL,
          quantity REAL NOT NULL,unit_type TEXT NOT NULL,location TEXT,condition TEXT NOT NULL,
          status TEXT NOT NULL,actor_id TEXT NOT NULL,created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS vector_scans(
          id TEXT PRIMARY KEY,code TEXT NOT NULL,warehouse_id TEXT NOT NULL,reference TEXT,
          scan_type TEXT NOT NULL,action TEXT NOT NULL,location TEXT,actor_id TEXT NOT NULL,
          created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS vector_custody(
          id TEXT PRIMARY KEY,object_code TEXT NOT NULL,warehouse_id TEXT NOT NULL,custodian_type TEXT NOT NULL,
          custodian_id TEXT NOT NULL,state TEXT NOT NULL,reference TEXT,location TEXT,
          actor_id TEXT NOT NULL,created_at REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_vector_receipts_ref ON vector_receipts(reference);
        CREATE INDEX IF NOT EXISTS idx_vector_scans_code ON vector_scans(code);
        CREATE INDEX IF NOT EXISTS idx_vector_custody_code ON vector_custody(object_code,created_at);
        """)
        cols={r['name'] for r in conn.execute('PRAGMA table_info(vector_transactions)').fetchall()}
        if 'client_request_id' not in cols:
            conn.execute('ALTER TABLE vector_transactions ADD COLUMN client_request_id TEXT')
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_vector_tx_client_request ON vector_transactions(client_request_id)')
        conn.commit()
    finally: conn.close()

_init_db()


def _identity(access_code: str, write: bool = False):
    require_permission(access_code, "inventory:write" if write else "inventory:read")
    if access_code == ADMIN_PASSCODE:
        return {"id":"MASTER","name":"Master Administrator","role":"ADMIN","permissions":["*"]}
    shared_db = BASE_DIR / "data_hub.db"
    conn = sqlite3.connect(shared_db); conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT id,name,permissions,is_active FROM staff WHERE passcode=? AND is_active=1",(access_code,)).fetchone()
    finally: conn.close()
    if not row: raise HTTPException(status_code=401, detail="Invalid access code")
    permissions=[p.strip() for p in (row['permissions'] or '').split(',') if p.strip()]
    role="SUPERVISOR" if "inventory:write" in permissions else "OPERATOR"
    return {"id":row['id'],"name":row['name'],"role":role,"permissions":permissions}


def _record_event(event_type: str, payload: dict, actor_id: str="SYSTEM", command: str|None=None):
    event_id=f"VEC-{uuid.uuid4()}"; now=time.time()
    conn=_db()
    try:
        conn.execute("INSERT INTO vector_events VALUES(?,?,?,?,?,?,?,?)",(event_id,event_type,command,payload.get('object_type'),payload.get('object_id'),json.dumps(payload,separators=(',',':')),actor_id,now)); conn.commit()
    finally: conn.close()
    envelope={"event_id":event_id,"event_type":event_type,"command":command,"actor_id":actor_id,**payload}
    relay_emit("vector5250_event","info",envelope)
    vector5250_backup("event",event_id,event_type,envelope)
    return event_id


def _transaction(command: str, reference: str|None, actor_id: str, payload: dict, client_request_id: str|None=None):
    conn=_db()
    try:
        if client_request_id:
            old=conn.execute("SELECT * FROM vector_transactions WHERE client_request_id=?",(client_request_id,)).fetchone()
            if old: return dict(old), True
        tx_id=f"VTX-{uuid.uuid4()}"; now=time.time()
        conn.execute("INSERT INTO vector_transactions(id,command,status,reference,actor_id,payload_json,client_request_id,created_at) VALUES(?,?,?,?,?,?,?,?)",(tx_id,command,"COMPLETED",reference,actor_id,json.dumps(payload,separators=(',',':')),client_request_id,now)); conn.commit()
        row=conn.execute("SELECT * FROM vector_transactions WHERE id=?",(tx_id,)).fetchone()
    finally: conn.close()
    vector5250_backup("transaction",tx_id,"COMPLETED",{"command":command,"reference":reference,"actor_id":actor_id,"payload":payload})
    return dict(row), False

@app.get("/vector5250", response_class=HTMLResponse)
def vector5250_ui():
    return HTMLResponse((BASE_DIR/"vector5250"/"vector5250.html").read_text(encoding="utf-8"),headers={"Cache-Control":"no-cache, no-store"})

@app.get("/api/vector5250/status")
def status():
    conn=_db()
    try:
        events=conn.execute("SELECT COUNT(*) n FROM vector_events").fetchone()['n']; txs=conn.execute("SELECT COUNT(*) n FROM vector_transactions").fetchone()['n']; receipts=conn.execute("SELECT COUNT(*) n FROM vector_receipts").fetchone()['n']
    finally: conn.close()
    backup=sync_client_status().get("VECTOR5250",{})
    return {"system":"Vector 5250","version":"1.2.0","phase":2,"mode":"independent-integrated","system_of_record":"Vector 5250","database":DB_PATH.name,"relay_monitoring":True,"backup_replication":True,"backup_status":backup,"ugatu_registry_modified":False,"ugatu_relationship":"interoperability adapter only","events":events,"transactions":txs,"receipts":receipts,"generated_at":time.time()}

@app.get("/api/vector5250/session")
def session(x_access_code: str=Header(default="")):
    me=_identity(x_access_code); _record_event("session.opened",{"role":me['role']},actor_id=me['id']); return me

@app.get("/api/vector5250/dashboard")
def dashboard(warehouse_id: str=Query("main"),x_access_code: str=Header(default="")):
    me=_identity(x_access_code); conn=_db()
    try:
        total_skus=conn.execute("SELECT COUNT(*) n FROM vector_inventory WHERE warehouse_id=?",(warehouse_id,)).fetchone()['n']; total_units=conn.execute("SELECT COALESCE(SUM(quantity),0) n FROM vector_inventory WHERE warehouse_id=?",(warehouse_id,)).fetchone()['n']; today=time.time()-86400
        receiving=conn.execute("SELECT COUNT(*) n FROM vector_receipts WHERE warehouse_id=? AND created_at>=?",(warehouse_id,today)).fetchone()['n']; scans=conn.execute("SELECT COUNT(*) n FROM vector_scans WHERE warehouse_id=? AND created_at>=?",(warehouse_id,today)).fetchone()['n']
    finally: conn.close()
    return {"system":"Vector 5250","source":DB_PATH.name,"warehouse_id":warehouse_id,"inventory":{"skus":total_skus,"units":total_units},"today":{"receiving":receiving,"scans":scans,"picking":0,"dispatch":0,"putaway":0},"alerts":[],"actor_id":me['id'],"generated_at":time.time()}

@app.get("/api/vector5250/commands")
def commands(x_access_code: str=Header(default="")):
    _identity(x_access_code); return {"count":len(COMMANDS),"results":COMMANDS,"namespace":"VECTOR5250"}

@app.get("/api/vector5250/resolve/{command}")
def resolve_command(command: str,x_access_code: str=Header(default="")):
    me=_identity(x_access_code); key=command.strip().upper(); item=COMMANDS.get(key)
    if not item: raise HTTPException(status_code=404, detail="Vector 5250 command not found")
    _record_event("command.resolved",{"vector_command":key,"screen":item['screen']},actor_id=me['id'],command=key)
    return {"command":key,**item,"canonical":"VECTOR5250","ugatu_interop":UGATU_INTEROP_MAP.get(key,[])}

@app.post("/api/vector5250/receiving")
def receive(req: ReceiveRequest,x_access_code: str=Header(default="")):
    me=_identity(x_access_code,write=True); payload=req.model_dump(); tx,replayed=_transaction("VRCV",req.reference,me['id'],payload,req.client_request_id)
    if replayed: return {"replayed":True,"transaction_id":tx['id'],"reference":req.reference}
    receipt_id=f"VRC-{uuid.uuid4()}"; now=time.time(); conn=_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO vector_receipts VALUES(?,?,?,?,?,?,?,?,?,?,?)",(receipt_id,req.reference,req.warehouse_id,req.sku,req.quantity,req.unit_type,req.location,req.condition,"RECEIVED",me['id'],now))
        conn.execute("INSERT INTO vector_inventory(warehouse_id,sku,quantity,updated_at) VALUES(?,?,?,?) ON CONFLICT(warehouse_id,sku) DO UPDATE SET quantity=quantity+excluded.quantity,updated_at=excluded.updated_at",(req.warehouse_id,req.sku,req.quantity,now))
        custody_id=f"VCU-{uuid.uuid4()}"
        conn.execute("INSERT INTO vector_custody VALUES(?,?,?,?,?,?,?,?,?,?)",(custody_id,req.sku,req.warehouse_id,"WAREHOUSE",req.warehouse_id,"IN_CUSTODY",req.reference,req.location,me['id'],now)); conn.commit()
    except Exception: conn.rollback(); raise
    finally: conn.close()
    event_id=_record_event("receiving.completed",{"object_type":req.unit_type,"object_id":req.sku,"reference":req.reference,"warehouse_id":req.warehouse_id,"quantity":req.quantity,"location":req.location,"transaction_id":tx['id'],"custody_id":custody_id},actor_id=me['id'],command="VRCV")
    vector5250_backup("receipt",receipt_id,"RECEIVED",{"reference":req.reference,"warehouse_id":req.warehouse_id,"sku":req.sku,"quantity":req.quantity,"unit_type":req.unit_type,"location":req.location,"condition":req.condition,"custody_id":custody_id})
    return {"receipt_id":receipt_id,"transaction_id":tx['id'],"event_id":event_id,"custody_id":custody_id,"status":"RECEIVED","replayed":False}

@app.post("/api/vector5250/scan")
def scan(req: ScanRequest,x_access_code: str=Header(default="")):
    me=_identity(x_access_code,write=True); payload=req.model_dump(); tx,replayed=_transaction("VSCAN",req.reference,me['id'],payload,req.client_request_id)
    if replayed: return {"replayed":True,"transaction_id":tx['id'],"code":req.code}
    scan_id=f"VSC-{uuid.uuid4()}"; now=time.time(); conn=_db()
    try:
        conn.execute("INSERT INTO vector_scans VALUES(?,?,?,?,?,?,?,?,?)",(scan_id,req.code,req.warehouse_id,req.reference,req.scan_type,req.action,req.location,me['id'],now)); conn.commit()
    finally: conn.close()
    event_id=_record_event("scan.recorded",{"object_type":req.scan_type,"object_id":req.code,"reference":req.reference,"warehouse_id":req.warehouse_id,"action":req.action,"location":req.location,"transaction_id":tx['id']},actor_id=me['id'],command="VSCAN")
    vector5250_backup("scan",scan_id,req.action.upper(),payload)
    return {"scan_id":scan_id,"transaction_id":tx['id'],"event_id":event_id,"status":"RECORDED","replayed":False}

@app.get("/api/vector5250/custody/{object_code}")
def custody(object_code: str,x_access_code: str=Header(default="")):
    _identity(x_access_code); conn=_db()
    try: rows=conn.execute("SELECT * FROM vector_custody WHERE object_code=? ORDER BY created_at DESC",(object_code,)).fetchall()
    finally: conn.close()
    return {"object_code":object_code,"count":len(rows),"history":[dict(r) for r in rows]}

@app.get("/api/vector5250/backup-status")
def backup_status(x_access_code: str=Header(default="")):
    _identity(x_access_code); s=sync_client_status(); return {"system":"Vector 5250","source":"VECTOR5250","backup_service_configured":bool(os.environ.get('BACKUP_SYNC_TOKEN','').strip()),"status":s.get('VECTOR5250',{}),"global":{k:s.get(k) for k in ('last_attempt','last_success','last_error','queued','active','completed','failed','dropped')}}
