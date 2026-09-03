"""Vector 5250 production integration entrypoint.

Vector 5250 is an independent enterprise operations system and system of record.
It keeps its own persistence, command set and audit/event journal. Integration
with UGATU/UGASHIP/Warehouse happens through explicit adapters/events only.
"""
from pathlib import Path
import json
import os
import sqlite3
import time
import uuid
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse

from auth import ADMIN_PASSCODE, require_permission
from data_relay_client import emit as relay_emit

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("VECTOR5250_DB_PATH") or (BASE_DIR / "vector5250.db"))

app = FastAPI(title="Vector 5250", version="1.1.0")

# Vector-native operator commands. These are NOT replacements for UGATU U-Codes.
COMMANDS = {
    "MIGO": {"screen": "SCAN", "label": "Goods Movement"},
    "MB51": {"screen": "INVENTORY", "label": "Inventory Movement History"},
    "MB52": {"screen": "INVENTORY", "label": "Inventory Lookup"},
    "MI01": {"screen": "CYCLE", "label": "Create Physical Inventory Count"},
    "MI04": {"screen": "CYCLE", "label": "Enter Count"},
    "MB5T": {"screen": "TRANSFERS", "label": "Stock in Transfer"},
    "VL06O": {"screen": "OUTBOUND", "label": "Outbound Monitor"},
    "LT03": {"screen": "PICKING", "label": "Create Pick Task"},
    "ZV5250": {"screen": "MENU", "label": "Vector 5250 Home"},
}

# Interoperability hints only. This adapter map does not mutate the UGATU registry
# and is never used as Vector 5250's internal command identity.
UGATU_INTEROP_MAP = {
    "MIGO": ["U-4030", "U-4340"],
    "MB51": ["U-4190"],
    "MB52": ["U-4110"],
    "MI01": ["U-4150"],
    "MI04": ["U-4150"],
    "MB5T": ["U-4400"],
    "VL06O": ["U-4200"],
    "LT03": ["U-4230"],
}


def _db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _db()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS vector_events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                command TEXT,
                object_type TEXT,
                object_id TEXT,
                payload_json TEXT NOT NULL,
                actor_id TEXT,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS vector_inventory (
                warehouse_id TEXT NOT NULL,
                sku TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL,
                PRIMARY KEY (warehouse_id, sku)
            );
            CREATE TABLE IF NOT EXISTS vector_transactions (
                id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                status TEXT NOT NULL,
                reference TEXT,
                actor_id TEXT,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


_init_db()


def _identity(access_code: str):
    # Reuse shared identity/permission enforcement without sharing operational data.
    require_permission(access_code, "inventory:read")
    if access_code == ADMIN_PASSCODE:
        return {"id": "MASTER", "name": "Master Administrator", "role": "ADMIN", "permissions": ["*"]}
    shared_db = BASE_DIR / "data_hub.db"
    conn = sqlite3.connect(shared_db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id,name,permissions,is_active FROM staff WHERE passcode=? AND is_active=1",
            (access_code,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid access code")
    permissions = [p.strip() for p in (row["permissions"] or "").split(",") if p.strip()]
    role = "SUPERVISOR" if "inventory:write" in permissions else "OPERATOR"
    return {"id": row["id"], "name": row["name"], "role": role, "permissions": permissions}


def _record_event(event_type: str, payload: dict, actor_id: str = "SYSTEM", command: str | None = None):
    event_id = f"VEC-{uuid.uuid4()}"
    now = time.time()
    conn = _db()
    try:
        conn.execute(
            "INSERT INTO vector_events(id,event_type,command,object_type,object_id,payload_json,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (event_id, event_type, command, payload.get("object_type"), payload.get("object_id"), json.dumps(payload, separators=(",", ":")), actor_id, now),
        )
        conn.commit()
    finally:
        conn.close()
    relay_emit("vector5250_event", "info", {"event_id": event_id, "event_type": event_type, "command": command, "actor_id": actor_id, **payload})
    return event_id


@app.get("/vector5250", response_class=HTMLResponse)
def vector5250_ui():
    path = BASE_DIR / "vector5250" / "vector5250.html"
    return HTMLResponse(path.read_text(encoding="utf-8"), headers={"Cache-Control": "no-cache, no-store"})


@app.get("/api/vector5250/status")
def status():
    conn = _db()
    try:
        event_count = conn.execute("SELECT COUNT(*) n FROM vector_events").fetchone()["n"]
        tx_count = conn.execute("SELECT COUNT(*) n FROM vector_transactions").fetchone()["n"]
    finally:
        conn.close()
    return {
        "system": "Vector 5250",
        "version": "1.1.0",
        "mode": "independent-integrated",
        "system_of_record": "Vector 5250",
        "database": str(DB_PATH.name),
        "relay_monitoring": True,
        "ugatu_registry_modified": False,
        "ugatu_relationship": "interoperability adapter only",
        "events": event_count,
        "transactions": tx_count,
        "generated_at": time.time(),
    }


@app.get("/api/vector5250/session")
def session(x_access_code: str = Header(default="")):
    me = _identity(x_access_code)
    _record_event("session.opened", {"role": me["role"]}, actor_id=me["id"])
    return me


@app.get("/api/vector5250/dashboard")
def dashboard(warehouse_id: str = Query("main"), x_access_code: str = Header(default="")):
    me = _identity(x_access_code)
    conn = _db()
    try:
        total_skus = conn.execute("SELECT COUNT(*) n FROM vector_inventory WHERE warehouse_id=?", (warehouse_id,)).fetchone()["n"]
        total_units = conn.execute("SELECT COALESCE(SUM(quantity),0) n FROM vector_inventory WHERE warehouse_id=?", (warehouse_id,)).fetchone()["n"]
        today = time.time() - 86400
        rows = conn.execute(
            "SELECT command,COUNT(*) n FROM vector_transactions WHERE created_at>=? GROUP BY command",
            (today,),
        ).fetchall()
        counts = {r["command"]: r["n"] for r in rows}
    finally:
        conn.close()
    return {
        "system": "Vector 5250",
        "source": "vector5250.db",
        "warehouse_id": warehouse_id,
        "inventory": {"skus": total_skus, "units": total_units},
        "today": {
            "receiving": counts.get("MIGO", 0),
            "picking": counts.get("LT03", 0),
            "dispatch": counts.get("VL06O", 0),
            "putaway": 0,
        },
        "alerts": [],
        "actor_id": me["id"],
        "generated_at": time.time(),
    }


@app.get("/api/vector5250/commands")
def commands(x_access_code: str = Header(default="")):
    _identity(x_access_code)
    return {"count": len(COMMANDS), "results": COMMANDS, "namespace": "VECTOR5250"}


@app.get("/api/vector5250/resolve/{command}")
def resolve_command(command: str, x_access_code: str = Header(default="")):
    me = _identity(x_access_code)
    key = command.strip().upper()
    item = COMMANDS.get(key)
    if not item:
        raise HTTPException(status_code=404, detail="Vector 5250 command not found")
    _record_event("command.resolved", {"vector_command": key, "screen": item["screen"]}, actor_id=me["id"], command=key)
    return {"command": key, **item, "canonical": "VECTOR5250", "ugatu_interop": UGATU_INTEROP_MAP.get(key, [])}
