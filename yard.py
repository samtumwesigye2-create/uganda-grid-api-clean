import os
import sqlite3
import time
import uuid

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from auth import require_permission

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
router = APIRouter(prefix="/yard", tags=["yard"])

UNIT_STATUSES = {"expected", "checked_in", "staged", "at_dock", "loading", "unloading", "released", "departed", "cancelled"}
BAY_STATUSES = {"available", "reserved", "occupied", "blocked", "maintenance"}
GATE_STATUSES = {"open", "closed", "restricted"}

class YardUnitCreate(BaseModel):
    unit_number: str
    unit_type: str = "trailer"
    carrier: str = ""
    plate_number: str = ""
    shipment_number: str = ""
    order_number: str = ""
    appointment_time: float | None = None
    notes: str = ""

class YardUnitUpdate(BaseModel):
    status: str | None = None
    bay_id: str | None = None
    gate_id: str | None = None
    notes: str | None = None

class ResourceCreate(BaseModel):
    resource_id: str
    name: str

class ResourceStatus(BaseModel):
    status: str


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = conn()
    c.execute("""
      CREATE TABLE IF NOT EXISTS yard_units (
        id TEXT PRIMARY KEY,
        unit_number TEXT UNIQUE NOT NULL,
        unit_type TEXT NOT NULL,
        carrier TEXT,
        plate_number TEXT,
        shipment_number TEXT,
        order_number TEXT,
        appointment_time REAL,
        status TEXT NOT NULL,
        bay_id TEXT,
        gate_id TEXT,
        checked_in_at REAL,
        departed_at REAL,
        notes TEXT,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
      )
    """)
    c.execute("""
      CREATE TABLE IF NOT EXISTS yard_bays (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
      )
    """)
    c.execute("""
      CREATE TABLE IF NOT EXISTS yard_gates (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
      )
    """)
    c.execute("""
      CREATE TABLE IF NOT EXISTS yard_history (
        id TEXT PRIMARY KEY,
        unit_id TEXT,
        event TEXT NOT NULL,
        detail TEXT,
        created_at REAL NOT NULL
      )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_yard_units_status ON yard_units(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_yard_units_unit_number ON yard_units(unit_number)")
    c.commit(); c.close()

init_db()


def read_access(code: str):
    require_permission(code, "shipments:read")


def write_access(code: str):
    require_permission(code, "shipments:write")


def log(c, unit_id: str | None, event: str, detail: str = ""):
    c.execute("INSERT INTO yard_history (id,unit_id,event,detail,created_at) VALUES (?,?,?,?,?)",
              (str(uuid.uuid4()), unit_id, event, detail[:1000], time.time()))


def get_unit(c, key: str):
    return c.execute("SELECT * FROM yard_units WHERE id=? OR unit_number=?", (key, key.upper())).fetchone()


@router.get("/summary")
def summary(x_access_code: str = Header(default="")):
    read_access(x_access_code)
    c = conn()
    total = c.execute("SELECT COUNT(*) n FROM yard_units WHERE status NOT IN ('departed','cancelled')").fetchone()["n"]
    arrivals = c.execute("SELECT COUNT(*) n FROM yard_units WHERE status IN ('expected','checked_in')").fetchone()["n"]
    bays = c.execute("SELECT status,COUNT(*) n FROM yard_bays GROUP BY status").fetchall()
    gates = c.execute("SELECT status,COUNT(*) n FROM yard_gates GROUP BY status").fetchall()
    c.close()
    return {
        "active_units": total,
        "arrivals": arrivals,
        "bays": {r["status"]: r["n"] for r in bays},
        "gates": {r["status"]: r["n"] for r in gates},
    }


@router.post("/units")
def create_unit(payload: YardUnitCreate, x_access_code: str = Header(default="")):
    write_access(x_access_code)
    number = payload.unit_number.strip().upper()
    if not number:
        raise HTTPException(status_code=400, detail="Unit number is required")
    c = conn()
    if c.execute("SELECT 1 FROM yard_units WHERE unit_number=?", (number,)).fetchone():
        c.close(); raise HTTPException(status_code=409, detail="Yard unit already exists")
    uid = str(uuid.uuid4()); now = time.time()
    c.execute("""INSERT INTO yard_units
      (id,unit_number,unit_type,carrier,plate_number,shipment_number,order_number,appointment_time,status,bay_id,gate_id,checked_in_at,departed_at,notes,created_at,updated_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (uid, number, payload.unit_type.strip().lower() or "trailer", payload.carrier.strip(), payload.plate_number.strip().upper(),
       payload.shipment_number.strip().upper(), payload.order_number.strip().upper(), payload.appointment_time, "expected", "", "", None, None,
       payload.notes.strip()[:2000], now, now))
    log(c, uid, "expected", "Yard unit created")
    c.commit(); row = get_unit(c, uid); out = dict(row); c.close(); return out


@router.get("/units")
def list_units(status: str = Query(default=""), q: str = Query(default=""), limit: int = Query(default=200, ge=1, le=500), x_access_code: str = Header(default="")):
    read_access(x_access_code)
    c = conn(); where=[]; args=[]
    if status:
        if status not in UNIT_STATUSES: c.close(); raise HTTPException(status_code=400, detail="Invalid status")
        where.append("status=?"); args.append(status)
    if q.strip():
        term = "%" + q.strip() + "%"
        where.append("(unit_number LIKE ? OR carrier LIKE ? OR plate_number LIKE ? OR shipment_number LIKE ? OR order_number LIKE ?)")
        args += [term, term, term, term, term]
    sql = "SELECT * FROM yard_units" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    rows = c.execute(sql, args).fetchall(); c.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


@router.get("/units/{unit_id}")
def unit_detail(unit_id: str, x_access_code: str = Header(default="")):
    read_access(x_access_code)
    c = conn(); row = get_unit(c, unit_id)
    if not row: c.close(); raise HTTPException(status_code=404, detail="Yard unit not found")
    out = dict(row)
    out["history"] = [dict(x) for x in c.execute("SELECT event,detail,created_at FROM yard_history WHERE unit_id=? ORDER BY created_at", (row["id"],)).fetchall()]
    c.close(); return out


@router.put("/units/{unit_id}")
def update_unit(unit_id: str, payload: YardUnitUpdate, x_access_code: str = Header(default="")):
    write_access(x_access_code)
    c = conn(); row = get_unit(c, unit_id)
    if not row: c.close(); raise HTTPException(status_code=404, detail="Yard unit not found")
    data = dict(row); now = time.time()
    if payload.status is not None:
        status = payload.status.strip().lower()
        if status not in UNIT_STATUSES: c.close(); raise HTTPException(status_code=400, detail="Invalid status")
        data["status"] = status
        if status == "checked_in" and not data.get("checked_in_at"): data["checked_in_at"] = now
        if status == "departed": data["departed_at"] = now
    if payload.bay_id is not None: data["bay_id"] = payload.bay_id.strip()
    if payload.gate_id is not None: data["gate_id"] = payload.gate_id.strip()
    if payload.notes is not None: data["notes"] = payload.notes.strip()[:2000]
    c.execute("""UPDATE yard_units SET status=?,bay_id=?,gate_id=?,checked_in_at=?,departed_at=?,notes=?,updated_at=? WHERE id=?""",
              (data["status"], data["bay_id"], data["gate_id"], data["checked_in_at"], data["departed_at"], data["notes"], now, row["id"]))
    log(c, row["id"], data["status"], f"bay={data['bay_id']} gate={data['gate_id']}")
    c.commit(); out = dict(get_unit(c, row["id"])); c.close(); return out


@router.post("/bays")
def create_bay(payload: ResourceCreate, x_access_code: str = Header(default="")):
    write_access(x_access_code)
    rid = payload.resource_id.strip().upper(); name = payload.name.strip()
    if not rid or not name: raise HTTPException(status_code=400, detail="Bay id and name are required")
    c = conn(); now = time.time()
    try:
        c.execute("INSERT INTO yard_bays (id,name,status,created_at,updated_at) VALUES (?,?,?,?,?)", (rid,name,"available",now,now))
        c.commit()
    except sqlite3.IntegrityError:
        c.close(); raise HTTPException(status_code=409, detail="Bay already exists")
    c.close(); return {"id": rid, "name": name, "status": "available"}


@router.get("/bays")
def list_bays(x_access_code: str = Header(default="")):
    read_access(x_access_code)
    c = conn(); rows = c.execute("SELECT * FROM yard_bays ORDER BY id").fetchall(); c.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


@router.put("/bays/{bay_id}/status")
def set_bay_status(bay_id: str, payload: ResourceStatus, x_access_code: str = Header(default="")):
    write_access(x_access_code)
    status = payload.status.strip().lower()
    if status not in BAY_STATUSES: raise HTTPException(status_code=400, detail="Invalid bay status")
    c = conn(); r = c.execute("UPDATE yard_bays SET status=?,updated_at=? WHERE id=?", (status,time.time(),bay_id.upper())); c.commit(); c.close()
    if r.rowcount == 0: raise HTTPException(status_code=404, detail="Bay not found")
    return {"id": bay_id.upper(), "status": status}


@router.post("/gates")
def create_gate(payload: ResourceCreate, x_access_code: str = Header(default="")):
    write_access(x_access_code)
    rid = payload.resource_id.strip().upper(); name = payload.name.strip()
    if not rid or not name: raise HTTPException(status_code=400, detail="Gate id and name are required")
    c = conn(); now = time.time()
    try:
        c.execute("INSERT INTO yard_gates (id,name,status,created_at,updated_at) VALUES (?,?,?,?,?)", (rid,name,"open",now,now))
        c.commit()
    except sqlite3.IntegrityError:
        c.close(); raise HTTPException(status_code=409, detail="Gate already exists")
    c.close(); return {"id": rid, "name": name, "status": "open"}


@router.get("/gates")
def list_gates(x_access_code: str = Header(default="")):
    read_access(x_access_code)
    c = conn(); rows = c.execute("SELECT * FROM yard_gates ORDER BY id").fetchall(); c.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


@router.put("/gates/{gate_id}/status")
def set_gate_status(gate_id: str, payload: ResourceStatus, x_access_code: str = Header(default="")):
    write_access(x_access_code)
    status = payload.status.strip().lower()
    if status not in GATE_STATUSES: raise HTTPException(status_code=400, detail="Invalid gate status")
    c = conn(); r = c.execute("UPDATE yard_gates SET status=?,updated_at=? WHERE id=?", (status,time.time(),gate_id.upper())); c.commit(); c.close()
    if r.rowcount == 0: raise HTTPException(status_code=404, detail="Gate not found")
    return {"id": gate_id.upper(), "status": status}
