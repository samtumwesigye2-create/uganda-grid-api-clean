"""Vector 5250 integration entrypoint.

Vector 5250 is an operator console over the existing Uganda National Grid
warehouse/UGASHIP/UGATU services. It is deliberately not a second system of
record and does not create its own authentication or warehouse database.
"""
from pathlib import Path
import os
import sqlite3
import time
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse

from auth import ADMIN_PASSCODE, require_permission
from warehouse_control_tower import dashboard as warehouse_dashboard

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data_hub.db"

app = FastAPI(title="Vector 5250", version="1.0.0")

# Familiar legacy/SAP-like aliases are presentation aliases only. UGATU remains
# the canonical transaction identity underneath Vector 5250.
COMMAND_MAP = {
    "MIGO": {"screen": "SCAN", "ugatu": ["U-4030", "U-4340"], "label": "Goods Movement"},
    "MB51": {"screen": "INVENTORY", "ugatu": ["U-4190"], "label": "Inventory Movement History"},
    "MB52": {"screen": "INVENTORY", "ugatu": ["U-4110"], "label": "Inventory Lookup"},
    "MI01": {"screen": "CYCLE", "ugatu": ["U-4150"], "label": "Create Physical Inventory Count"},
    "MI04": {"screen": "CYCLE", "ugatu": ["U-4150"], "label": "Enter Count"},
    "MB5T": {"screen": "TRANSFERS", "ugatu": ["U-4400"], "label": "Stock in Transfer"},
    "VL06O": {"screen": "OUTBOUND", "ugatu": ["U-4200"], "label": "Outbound Monitor"},
    "LT03": {"screen": "PICKING", "ugatu": ["U-4230"], "label": "Create Pick Task"},
    "ZV5250": {"screen": "MENU", "ugatu": ["U-4000"], "label": "Vector 5250 Home"},
}


def _identity(access_code: str):
    require_permission(access_code, "inventory:read")
    if access_code == ADMIN_PASSCODE:
        return {"id": "MASTER", "name": "Master Administrator", "role": "ADMIN", "permissions": ["*"]}
    conn = sqlite3.connect(DB_PATH)
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


@app.get("/vector5250", response_class=HTMLResponse)
def vector5250_ui():
    path = BASE_DIR / "vector5250" / "vector5250.html"
    return HTMLResponse(path.read_text(encoding="utf-8"), headers={"Cache-Control": "no-cache, no-store"})


@app.get("/api/vector5250/status")
def status():
    return {
        "system": "Vector 5250",
        "version": "1.0.0",
        "mode": "integrated",
        "system_of_record": "UGASHIP/Warehouse shared data_hub",
        "auth": "shared staff RBAC",
        "commands": "UGATU canonical U-Codes with Vector/SAP aliases",
        "external_integrations": "UGA Integration Gateway",
        "generated_at": time.time(),
    }


@app.get("/api/vector5250/session")
def session(x_access_code: str = Header(default="")):
    return _identity(x_access_code)


@app.get("/api/vector5250/dashboard")
def dashboard(warehouse_id: str = Query("main"), x_access_code: str = Header(default="")):
    _identity(x_access_code)
    data = warehouse_dashboard(warehouse_id=warehouse_id, x_access_code=x_access_code)
    return {"system": "Vector 5250", "source": "warehouse_control_tower", **data}


@app.get("/api/vector5250/commands")
def commands(x_access_code: str = Header(default="")):
    _identity(x_access_code)
    return {"count": len(COMMAND_MAP), "results": COMMAND_MAP}


@app.get("/api/vector5250/resolve/{command}")
def resolve_command(command: str, x_access_code: str = Header(default="")):
    _identity(x_access_code)
    key = command.strip().upper()
    item = COMMAND_MAP.get(key)
    if not item:
        raise HTTPException(status_code=404, detail="Vector 5250 command alias not found")
    return {"alias": key, **item, "canonical": "UGATU"}
