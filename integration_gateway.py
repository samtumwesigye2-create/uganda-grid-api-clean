"""Secure integration gateway for external systems.

Connectors are configured through INTEGRATION_CONNECTORS_JSON. Secrets and
destination URLs never enter the application database.
"""
import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Form, Header, HTTPException, Query, Request

from auth import require_permission

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
POLL_SECONDS = max(2, int(os.environ.get("INTEGRATION_POLL_SECONDS", "5")))
MAX_ATTEMPTS = max(1, int(os.environ.get("INTEGRATION_MAX_ATTEMPTS", "5")))
router = APIRouter(prefix="/integration", tags=["Integration Gateway"])
_worker_started = False
_worker_lock = threading.Lock()


def db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def connectors():
    try:
        raw = json.loads(os.environ.get("INTEGRATION_CONNECTORS_JSON", "{}") or "{}")
    except json.JSONDecodeError:
        return {}
    out = {}
    for connector_id, item in raw.items() if isinstance(raw, dict) else []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("webhook_url") or "").strip()
        parsed = urlparse(url) if url else None
        if url and (parsed.scheme != "https" or not parsed.netloc):
            continue
        out[str(connector_id)] = {
            "name": str(item.get("name") or connector_id),
            "webhook_url": url,
            "secret": str(item.get("secret") or ""),
            "enabled": bool(item.get("enabled", True)),
            "subscriptions": [str(x) for x in item.get("subscriptions", ["*"])],
            "field_map": item.get("field_map") if isinstance(item.get("field_map"), dict) else {},
            "headers": item.get("headers") if isinstance(item.get("headers"), dict) else {},
        }
    return out


def init_db():
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS integration_events(
        id TEXT PRIMARY KEY,idempotency_key TEXT UNIQUE NOT NULL,direction TEXT NOT NULL,
        connector_id TEXT NOT NULL,event_type TEXT NOT NULL,payload_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'received',attempts INTEGER NOT NULL DEFAULT 0,
        next_attempt_at REAL,last_error TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL,
        delivered_at REAL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS integration_audit(
        id TEXT PRIMARY KEY,event_id TEXT,event_type TEXT NOT NULL,connector_id TEXT,
        action TEXT NOT NULL,detail TEXT,created_at REAL NOT NULL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_integration_queue ON integration_events(status,next_attempt_at,created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_integration_audit ON integration_audit(created_at)")
    conn.commit()
    conn.close()


def audit(conn, event_id, event_type, connector_id, action, detail=""):
    conn.execute("INSERT INTO integration_audit VALUES(?,?,?,?,?,?,?)", (str(uuid.uuid4()), event_id, event_type, connector_id, action, detail[:1000], time.time()))


def mapped(payload, field_map):
    result = dict(payload)
    for source, target in field_map.items():
        if source in payload and target:
            result[str(target)] = result.pop(source)
    return result


def signature(secret, body):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def queue_event(connector_id, event_type, payload, idempotency_key, direction="outbound"):
    conn = db()
    existing = conn.execute("SELECT * FROM integration_events WHERE idempotency_key=?", (idempotency_key,)).fetchone()
    if existing:
        conn.close()
        return dict(existing), False
    event_id = str(uuid.uuid4()); now = time.time()
    conn.execute("INSERT INTO integration_events(id,idempotency_key,direction,connector_id,event_type,payload_json,status,attempts,next_attempt_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (event_id,idempotency_key,direction,connector_id,event_type,json.dumps(payload,separators=(",",":"),default=str),"queued" if direction=="outbound" else "received",0,now if direction=="outbound" else None,now,now))
    audit(conn,event_id,event_type,connector_id,"queued" if direction=="outbound" else "received")
    conn.commit(); row=conn.execute("SELECT * FROM integration_events WHERE id=?",(event_id,)).fetchone();conn.close()
    return dict(row), True


def deliver(row, config):
    payload = mapped(json.loads(row["payload_json"]), config["field_map"])
    envelope = {"event_id":row["id"],"event_type":row["event_type"],"source":"UGA Integration Gateway","occurred_at":now_iso(),"data":payload}
    body = json.dumps(envelope,separators=(",",":"),default=str).encode()
    headers = {"Content-Type":"application/json","User-Agent":"UGA-Integration-Gateway/1.0","X-UGA-Event-ID":row["id"],"X-UGA-Idempotency-Key":row["idempotency_key"]}
    headers.update({str(k):str(v) for k,v in config["headers"].items()})
    if config["secret"]:headers["X-UGA-Signature"]=signature(config["secret"],body)
    req=urllib.request.Request(config["webhook_url"],data=body,method="POST",headers=headers)
    with urllib.request.urlopen(req,timeout=12) as response:
        response.read(4096)
        if not 200 <= response.status < 300:raise RuntimeError(f"HTTP {response.status}")


def process_one():
    conn=db();now=time.time();row=conn.execute("SELECT * FROM integration_events WHERE status IN ('queued','retry') AND COALESCE(next_attempt_at,0)<=? ORDER BY created_at LIMIT 1",(now,)).fetchone()
    if not row:conn.close();return False
    conn.execute("UPDATE integration_events SET status='sending',attempts=attempts+1,updated_at=? WHERE id=?",(now,row["id"]));conn.commit();row=dict(conn.execute("SELECT * FROM integration_events WHERE id=?",(row["id"],)).fetchone());conn.close()
    config=connectors().get(row["connector_id"])
    error=None
    try:
        if not config or not config["enabled"]:raise RuntimeError("Connector is missing or disabled")
        if not config["webhook_url"]:raise RuntimeError("Connector has no outbound webhook URL")
        deliver(row,config)
    except Exception as exc:error=f"{type(exc).__name__}: {exc}"[:500]
    conn=db()
    if error:
        dead=row["attempts"]>=MAX_ATTEMPTS;delay=min(300,2**row["attempts"])
        conn.execute("UPDATE integration_events SET status=?,next_attempt_at=?,last_error=?,updated_at=? WHERE id=?",("dead_letter" if dead else "retry",None if dead else time.time()+delay,error,time.time(),row["id"]))
        audit(conn,row["id"],row["event_type"],row["connector_id"],"dead_letter" if dead else "retry",error)
    else:
        conn.execute("UPDATE integration_events SET status='delivered',last_error=NULL,delivered_at=?,updated_at=? WHERE id=?",(time.time(),time.time(),row["id"]))
        audit(conn,row["id"],row["event_type"],row["connector_id"],"delivered")
    conn.commit();conn.close();return True


def worker():
    while True:
        try:
            if not process_one():time.sleep(POLL_SECONDS)
        except Exception:time.sleep(POLL_SECONDS)


def start_worker():
    global _worker_started
    with _worker_lock:
        if _worker_started:return
        _worker_started=True;threading.Thread(target=worker,name="uga-integration-gateway",daemon=True).start()


@router.get("/status")
def status(x_access_code:str=Header(default="")):
    require_permission(x_access_code,"integration:read");conn=db()
    counts={r["status"]:r["n"] for r in conn.execute("SELECT status,COUNT(*) n FROM integration_events GROUP BY status").fetchall()};conn.close()
    configured=connectors()
    return {"status":"operational","worker_running":_worker_started,"connectors":len(configured),"enabled_connectors":sum(1 for x in configured.values() if x["enabled"]),"events":counts,"checked_at":now_iso()}


@router.get("/connectors")
def list_connectors(x_access_code:str=Header(default="")):
    require_permission(x_access_code,"integration:read")
    return {"results":[{"id":key,"name":item["name"],"enabled":item["enabled"],"outbound_configured":bool(item["webhook_url"]),"signed":bool(item["secret"]),"subscriptions":item["subscriptions"],"mapped_fields":len(item["field_map"])} for key,item in connectors().items()]}


@router.post("/events")
def create_event(connector_id:str=Form(...),event_type:str=Form(...),payload_json:str=Form(...),idempotency_key:str=Form(""),x_access_code:str=Header(default="")):
    require_permission(x_access_code,"integration:write");config=connectors().get(connector_id)
    if not config or not config["enabled"]:raise HTTPException(404,"Connector not found or disabled")
    if "*" not in config["subscriptions"] and event_type not in config["subscriptions"]:raise HTTPException(403,"Connector is not subscribed to this event type")
    try:payload=json.loads(payload_json)
    except json.JSONDecodeError as exc:raise HTTPException(400,"payload_json must be valid JSON") from exc
    if not isinstance(payload,dict):raise HTTPException(400,"Event payload must be a JSON object")
    row,created=queue_event(connector_id,event_type,payload,idempotency_key.strip() or str(uuid.uuid4()))
    return {"event_id":row["id"],"status":row["status"],"created":created,"idempotent":True}


@router.post("/webhooks/{connector_id}")
async def receive_webhook(connector_id:str,request:Request,x_uga_signature:str=Header(default=""),x_uga_idempotency_key:str=Header(default=""),x_uga_event_type:str=Header(default="event.received")):
    config=connectors().get(connector_id)
    if not config or not config["enabled"]:raise HTTPException(404,"Connector not found or disabled")
    body=await request.body()
    if len(body)>2_000_000:raise HTTPException(413,"Webhook payload too large")
    if not config["secret"]:raise HTTPException(503,"Inbound webhook secret is not configured")
    expected=signature(config["secret"],body)
    if not hmac.compare_digest(expected,x_uga_signature):raise HTTPException(401,"Invalid webhook signature")
    try:payload=json.loads(body)
    except json.JSONDecodeError as exc:raise HTTPException(400,"Webhook body must be valid JSON") from exc
    if not isinstance(payload,dict):raise HTTPException(400,"Webhook body must be a JSON object")
    key=x_uga_idempotency_key.strip() or hashlib.sha256(body).hexdigest()
    row,created=queue_event(connector_id,x_uga_event_type,payload,key,"inbound")
    return {"accepted":True,"event_id":row["id"],"duplicate":not created}


@router.get("/events")
def events(status:str=Query(""),connector_id:str=Query(""),limit:int=Query(100,ge=1,le=500),x_access_code:str=Header(default="")):
    require_permission(x_access_code,"integration:read");conn=db();query="SELECT id,idempotency_key,direction,connector_id,event_type,status,attempts,last_error,created_at,updated_at,delivered_at FROM integration_events WHERE 1=1";args=[]
    if status:query+=" AND status=?";args.append(status)
    if connector_id:query+=" AND connector_id=?";args.append(connector_id)
    query+=" ORDER BY created_at DESC LIMIT ?";args.append(limit);rows=[dict(r) for r in conn.execute(query,args).fetchall()];conn.close();return {"count":len(rows),"results":rows}


@router.post("/events/{event_id}/retry")
def retry_event(event_id:str,x_access_code:str=Header(default="")):
    require_permission(x_access_code,"integration:write");conn=db();row=conn.execute("SELECT * FROM integration_events WHERE id=?",(event_id,)).fetchone()
    if not row:conn.close();raise HTTPException(404,"Integration event not found")
    if row["direction"]!="outbound":conn.close();raise HTTPException(400,"Only outbound events can be retried")
    conn.execute("UPDATE integration_events SET status='retry',attempts=0,next_attempt_at=?,last_error=NULL,updated_at=? WHERE id=?",(time.time(),time.time(),event_id));audit(conn,event_id,row["event_type"],row["connector_id"],"manual_retry");conn.commit();conn.close();return {"event_id":event_id,"status":"retry"}


init_db()
start_worker()
