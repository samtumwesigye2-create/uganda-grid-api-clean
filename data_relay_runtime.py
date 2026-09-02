"""UGAMAP Data Relay Server (DRS): unified observability event ingestion, audit, retention and alerts."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import uuid
from collections import Counter
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from auth import require_permission

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("DATA_RELAY_DB", os.path.join(BASE, "data_hub.db"))
RETENTION_DAYS = int(os.environ.get("DATA_RELAY_RETENTION_DAYS", "90"))
CPU_ALERT = float(os.environ.get("DATA_RELAY_CPU_ALERT", "90"))
MEMORY_ALERT = float(os.environ.get("DATA_RELAY_MEMORY_ALERT", "90"))
DISK_ALERT = float(os.environ.get("DATA_RELAY_DISK_ALERT", "90"))
SLOW_QUERY_MS = float(os.environ.get("DATA_RELAY_SLOW_QUERY_MS", "1000"))
REPLICATION_LAG_SECONDS = float(os.environ.get("DATA_RELAY_REPLICATION_LAG_SECONDS", "30"))
BRUTE_FORCE_ATTEMPTS = int(os.environ.get("DATA_RELAY_BRUTE_FORCE_ATTEMPTS", "5"))
BRUTE_FORCE_WINDOW_SECONDS = int(os.environ.get("DATA_RELAY_BRUTE_FORCE_WINDOW_SECONDS", "300"))
router = APIRouter(prefix="/platform/data-relay", tags=["platform-data-relay"])

CATEGORIES = {
    "system_metric", "application_log", "user_interaction", "database_activity",
    "api_call", "security_event", "error", "communication", "file_transfer",
    "alert_prediction",
}
SECRET_KEYS = {
    "password", "passwd", "secret", "token", "access_token", "refresh_token",
    "authorization", "cookie", "set-cookie", "api_key", "apikey", "private_key",
}


def _conn():
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    return c


def _now() -> float:
    return time.time()


def _read(code: str): require_permission(code, "shipments:read")
def _write(code: str): require_permission(code, "shipments:write")


def _scrub(value: Any):
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if str(k).lower() in SECRET_KEYS else _scrub(v)) for k, v in value.items()}
    if isinstance(value, list): return [_scrub(v) for v in value]
    if isinstance(value, str) and len(value) > 12000: return value[:12000] + "…[TRUNCATED]"
    return value


def _init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS data_relay_events(id TEXT PRIMARY KEY,category TEXT NOT NULL,source TEXT NOT NULL,severity TEXT NOT NULL,actor TEXT,action TEXT,resource TEXT,status TEXT,duration_ms REAL,trace_id TEXT,payload_json TEXT NOT NULL,created_at REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_relay_events_time ON data_relay_events(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_relay_events_category ON data_relay_events(category, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_relay_events_source ON data_relay_events(source, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_relay_events_trace ON data_relay_events(trace_id);
        CREATE TABLE IF NOT EXISTS data_relay_rules(id TEXT PRIMARY KEY,name TEXT NOT NULL,category TEXT,severity TEXT,source TEXT,threshold_count INTEGER NOT NULL DEFAULT 1,window_seconds INTEGER NOT NULL DEFAULT 300,alert_severity TEXT NOT NULL DEFAULT 'warning',enabled INTEGER NOT NULL DEFAULT 1,created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS data_relay_alerts(id TEXT PRIMARY KEY,rule_id TEXT,title TEXT NOT NULL,severity TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',evidence_json TEXT NOT NULL,created_at REAL NOT NULL,resolved_at REAL);
    """)
    c.commit(); c.close()

_init()

class EventIn(BaseModel):
    category: str
    source: str = Field(min_length=1, max_length=120)
    severity: str = "info"
    actor: str = ""
    action: str = ""
    resource: str = ""
    status: str = ""
    duration_ms: Optional[float] = None
    trace_id: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)

class BatchIn(BaseModel): events: List[EventIn] = Field(min_length=1, max_length=500)
class RuleIn(BaseModel):
    name: str; category: str = ""; severity: str = ""; source: str = ""
    threshold_count: int = Field(default=1, ge=1, le=100000)
    window_seconds: int = Field(default=300, ge=1, le=604800)
    alert_severity: str = "warning"


def _validate_event(p: EventIn):
    if p.category not in CATEGORIES:
        raise HTTPException(status_code=422, detail={"category": "unsupported", "allowed": sorted(CATEGORIES)})


def _insert_event(c, p: EventIn):
    _validate_event(p)
    eid = "EVT-" + uuid.uuid4().hex[:16].upper(); clean = _scrub(p.payload); t = _now()
    c.execute("INSERT INTO data_relay_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (eid,p.category,p.source,p.severity.lower(),p.actor,p.action,p.resource,p.status,p.duration_ms,p.trace_id,json.dumps(clean,separators=(",",":"),ensure_ascii=False),t))
    return eid


def _open_alert(c, title: str, severity: str, evidence: dict, rule_id: str = "builtin", dedupe_seconds: int = 300):
    cutoff = _now() - dedupe_seconds
    prior = c.execute("SELECT id FROM data_relay_alerts WHERE title=? AND status='open' AND created_at>=? LIMIT 1", (title, cutoff)).fetchone()
    if prior: return None
    aid = "ALT-" + uuid.uuid4().hex[:12].upper()
    c.execute("INSERT INTO data_relay_alerts VALUES (?,?,?,?,?,?,?,?)", (aid,rule_id,title,severity,"open",json.dumps(_scrub(evidence),separators=(",",":")),_now(),None))
    return aid


def _metric(payload: dict, *names):
    for n in names:
        v = payload.get(n)
        if isinstance(v, (int, float)): return float(v)
    return None


def _automatic_alerts(c, event_id: str, p: EventIn):
    """Built-in surge-room alerts requested for 24/7 monitoring."""
    alerts=[]; sev=p.severity.lower(); payload=p.payload or {}; evidence={"event_id":event_id,"source":p.source,"category":p.category,"trace_id":p.trace_id}
    if p.category == "error" and sev in {"critical","fatal","emergency"}:
        a=_open_alert(c,f"Critical error: {p.source}","critical",evidence); alerts += [a] if a else []
    if p.category == "system_metric":
        for label,val,limit in (
            ("CPU",_metric(payload,"cpu_percent","cpu_usage_percent","cpu"),CPU_ALERT),
            ("Memory",_metric(payload,"memory_percent","memory_usage_percent","memory"),MEMORY_ALERT),
            ("Disk",_metric(payload,"disk_percent","disk_usage_percent","disk"),DISK_ALERT),
        ):
            if val is not None and val >= limit:
                a=_open_alert(c,f"High {label}: {p.source}","critical",{**evidence,"value":val,"threshold":limit}); alerts += [a] if a else []
    if p.category == "database_activity":
        qms = p.duration_ms if p.duration_ms is not None else _metric(payload,"query_ms","duration_ms")
        if qms is not None and qms >= SLOW_QUERY_MS:
            a=_open_alert(c,f"Slow database query: {p.source}","warning",{**evidence,"query_ms":qms,"threshold_ms":SLOW_QUERY_MS}); alerts += [a] if a else []
        lag=_metric(payload,"replication_lag_seconds","replica_lag_seconds","replication_lag")
        if lag is not None and lag >= REPLICATION_LAG_SECONDS:
            a=_open_alert(c,f"Replication lag: {p.source}","critical",{**evidence,"lag_seconds":lag,"threshold_seconds":REPLICATION_LAG_SECONDS}); alerts += [a] if a else []
    if p.category == "security_event" and p.action.lower() in {"failed_login","login_failed","authentication_failed"}:
        since=_now()-BRUTE_FORCE_WINDOW_SECONDS
        clauses=["category='security_event'","created_at>=?","action IN ('failed_login','login_failed','authentication_failed')"]; args=[since]
        if p.actor: clauses.append("actor=?"); args.append(p.actor)
        elif p.source: clauses.append("source=?"); args.append(p.source)
        count=c.execute("SELECT COUNT(*) n FROM data_relay_events WHERE "+" AND ".join(clauses),args).fetchone()["n"]
        if count >= BRUTE_FORCE_ATTEMPTS:
            a=_open_alert(c,f"Brute force login attempts: {p.actor or p.source}","critical",{**evidence,"failed_attempts":count,"window_seconds":BRUTE_FORCE_WINDOW_SECONDS},dedupe_seconds=BRUTE_FORCE_WINDOW_SECONDS); alerts += [a] if a else []
    return alerts


def _evaluate_rules(c, event_id: str, p: EventIn):
    alerts=[]; t=_now()
    for r in c.execute("SELECT * FROM data_relay_rules WHERE enabled=1"):
        if r["category"] and r["category"] != p.category: continue
        if r["severity"] and r["severity"] != p.severity.lower(): continue
        if r["source"] and r["source"] != p.source: continue
        since=t-int(r["window_seconds"]); clauses=["created_at>=?"]; args=[since]
        for column,value in (("category",r["category"]),("severity",r["severity"]),("source",r["source"])):
            if value: clauses.append(f"{column}=?"); args.append(value)
        count=c.execute("SELECT COUNT(*) n FROM data_relay_events WHERE "+" AND ".join(clauses),args).fetchone()["n"]
        if count >= int(r["threshold_count"]):
            aid=_open_alert(c,f"{r['name']} ({count} events/{r['window_seconds']}s)",r["alert_severity"],{"event_id":event_id,"count":count,"window_seconds":r["window_seconds"]},r["id"],int(r["window_seconds"]))
            if aid: alerts.append(aid)
    return alerts

@router.get("/health")
def health():
    t0=time.perf_counter(); c=_conn(); c.execute("SELECT 1").fetchone(); c.close(); disk=shutil.disk_usage(BASE)
    return {"status":"healthy","service":"UGAMAP Data Relay Server","database_latency_ms":round((time.perf_counter()-t0)*1000,3),"retention_days":RETENTION_DAYS,"categories":sorted(CATEGORIES),"disk_free_bytes":disk.free,"automatic_alerts":{"critical_errors":True,"high_cpu_percent":CPU_ALERT,"high_memory_percent":MEMORY_ALERT,"high_disk_percent":DISK_ALERT,"brute_force_attempts":BRUTE_FORCE_ATTEMPTS,"brute_force_window_seconds":BRUTE_FORCE_WINDOW_SECONDS,"slow_query_ms":SLOW_QUERY_MS,"replication_lag_seconds":REPLICATION_LAG_SECONDS},"timestamp":_now()}

@router.post("/events")
def ingest(p:EventIn,x_access_code:str=Header(default="")):
    _write(x_access_code); c=_conn(); eid=_insert_event(c,p); alerts=_automatic_alerts(c,eid,p)+_evaluate_rules(c,eid,p); c.commit(); c.close(); return {"accepted":True,"event_id":eid,"alerts":alerts}

@router.post("/events/batch")
def ingest_batch(p:BatchIn,x_access_code:str=Header(default="")):
    _write(x_access_code); c=_conn(); ids=[]; alerts=[]
    for event in p.events:
        eid=_insert_event(c,event); ids.append(eid); alerts.extend(_automatic_alerts(c,eid,event)); alerts.extend(_evaluate_rules(c,eid,event))
    c.commit(); c.close(); return {"accepted":len(ids),"event_ids":ids,"alerts":alerts}

@router.get("/events")
def events(category:str="",source:str="",severity:str="",trace_id:str="",since:float=0,limit:int=Query(default=100,ge=1,le=1000),x_access_code:str=Header(default="")):
    _read(x_access_code); clauses=[]; args=[]
    for col,val in (("category",category),("source",source),("severity",severity),("trace_id",trace_id)):
        if val: clauses.append(f"{col}=?"); args.append(val)
    if since: clauses.append("created_at>=?"); args.append(since)
    q="SELECT * FROM data_relay_events" + ((" WHERE "+" AND ".join(clauses)) if clauses else "") + " ORDER BY created_at DESC LIMIT ?"; args.append(limit)
    c=_conn(); rows=[]
    for r in c.execute(q,args): item=dict(r); item["payload"]=json.loads(item.pop("payload_json") or "{}"); rows.append(item)
    c.close(); return {"results":rows}

@router.post("/rules")
def create_rule(p:RuleIn,x_access_code:str=Header(default="")):
    _write(x_access_code)
    if p.category and p.category not in CATEGORIES: raise HTTPException(status_code=422,detail="Unsupported category")
    rid="RLY-"+uuid.uuid4().hex[:10].upper(); c=_conn(); c.execute("INSERT INTO data_relay_rules VALUES (?,?,?,?,?,?,?,?,?,?)",(rid,p.name,p.category,p.severity.lower(),p.source,p.threshold_count,p.window_seconds,p.alert_severity,1,_now())); c.commit(); c.close(); return {"id":rid,"enabled":True}

@router.get("/rules")
def rules(x_access_code:str=Header(default="")):
    _read(x_access_code); c=_conn(); rows=[dict(r) for r in c.execute("SELECT * FROM data_relay_rules ORDER BY created_at DESC")]; c.close(); return {"results":rows}

@router.get("/alerts")
def alerts(status:str="open",x_access_code:str=Header(default="")):
    _read(x_access_code); c=_conn(); q="SELECT * FROM data_relay_alerts"; args=[]
    if status: q+=" WHERE status=?"; args.append(status)
    rows=[dict(r) for r in c.execute(q+" ORDER BY created_at DESC LIMIT 500",args)]; c.close(); return {"results":rows}

@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id:str,x_access_code:str=Header(default="")):
    _write(x_access_code); c=_conn(); n=c.execute("UPDATE data_relay_alerts SET status='resolved',resolved_at=? WHERE id=?",(_now(),alert_id)).rowcount; c.commit(); c.close(); return {"resolved":bool(n),"id":alert_id}

@router.post("/retention/purge")
def purge(days:int=Query(default=RETENTION_DAYS,ge=1,le=3650),x_access_code:str=Header(default="")):
    _write(x_access_code); cutoff=_now()-days*86400; c=_conn(); n=c.execute("DELETE FROM data_relay_events WHERE created_at<?",(cutoff,)).rowcount; c.commit(); c.close(); return {"deleted":n,"cutoff":cutoff,"retention_days":days}

@router.get("/dashboard")
def dashboard(window_seconds:int=Query(default=3600,ge=60,le=604800),x_access_code:str=Header(default="")):
    _read(x_access_code); since=_now()-window_seconds; c=_conn(); rows=[dict(r) for r in c.execute("SELECT category,severity,source,status,duration_ms FROM data_relay_events WHERE created_at>=?",(since,))]; open_alerts=c.execute("SELECT COUNT(*) n FROM data_relay_alerts WHERE status='open'").fetchone()["n"]; total=c.execute("SELECT COUNT(*) n FROM data_relay_events").fetchone()["n"]; critical=c.execute("SELECT COUNT(*) n FROM data_relay_alerts WHERE status='open' AND severity='critical'").fetchone()["n"]; c.close(); durations=[float(r["duration_ms"]) for r in rows if r["duration_ms"] is not None]
    return {"service":"UGAMAP Data Relay Server","window_seconds":window_seconds,"events_in_window":len(rows),"events_total":total,"open_alerts":open_alerts,"critical_alerts":critical,"by_category":dict(Counter(r["category"] for r in rows)),"by_severity":dict(Counter(r["severity"] for r in rows)),"by_source":dict(Counter(r["source"] for r in rows).most_common(20)),"average_duration_ms":round(sum(durations)/len(durations),3) if durations else None,"automatic_triggers":["critical errors","high CPU/memory/disk","brute force login attempts","slow database queries","replication lag"],"timestamp":_now()}
