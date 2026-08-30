"""
auth.py — Staff accounts and permission-based delegation.

The master ADMIN_PASSCODE (env var) always has full access to everything —
this doesn't change or replace it. This adds staff accounts *underneath*
it: each staff member gets their own passcode and a specific list of
permissions, so the admin can delegate narrow slices of access (e.g.
"can receive/dispatch stock but can't delete products") instead of
handing out the master passcode.

Permission strings in use across the app:
  inventory:read   inventory:write   inventory:delete
  invoicing:read   invoicing:write   invoicing:delete
  commercial:read  commercial:write
  shipments:read   shipments:write

Only the master passcode can create, edit, or delete staff accounts —
delegation itself is never delegatable.
"""

import os
import sqlite3
import time
import uuid
from fastapi import APIRouter, Form, Header, HTTPException

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
ADMIN_PASSCODE = os.environ.get("ADMIN_PASSCODE", "uganda2026")

router = APIRouter()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS staff (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            passcode TEXT UNIQUE NOT NULL,
            permissions TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


def is_master(access_code: str) -> bool:
    return access_code == ADMIN_PASSCODE


def require_permission(access_code: str, permission: str):
    """Call this instead of a flat passcode check. Master passcode always
    passes. Otherwise looks up the staff record by passcode and checks the
    specific permission is in their granted list."""
    if is_master(access_code):
        return
    if not access_code:
        raise HTTPException(status_code=401, detail="Access code required")

    conn = get_conn()
    staff = conn.execute(
        "SELECT * FROM staff WHERE passcode = ? AND is_active = 1", (access_code,)
    ).fetchone()
    conn.close()

    if not staff:
        raise HTTPException(status_code=401, detail="Invalid access code")

    granted = [p.strip() for p in staff["permissions"].split(",") if p.strip()]
    if permission not in granted:
        raise HTTPException(
            status_code=403,
            detail=f"'{staff['name']}' does not have the '{permission}' permission",
        )


def require_master(access_code: str):
    if not is_master(access_code):
        raise HTTPException(status_code=401, detail="Master admin passcode required")


@router.post("/staff")
def create_staff(
    name: str = Form(...),
    passcode: str = Form(...),
    permissions: str = Form(...),  # comma-separated, e.g. "inventory:read,inventory:write"
    x_admin_passcode: str = Header(default=""),
):
    require_master(x_admin_passcode)
    if passcode == ADMIN_PASSCODE:
        raise HTTPException(status_code=400, detail="Staff passcode cannot match the master passcode")

    conn = get_conn()
    existing = conn.execute("SELECT id FROM staff WHERE passcode = ?", (passcode,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="That passcode is already in use")

    staff_id = str(uuid.uuid4())
    clean_permissions = ",".join(p.strip() for p in permissions.split(",") if p.strip())
    conn.execute(
        "INSERT INTO staff (id, name, passcode, permissions, is_active, created_at) VALUES (?,?,?,?,?,?)",
        (staff_id, name, passcode, clean_permissions, 1, time.time()),
    )
    conn.commit()
    conn.close()
    return {"id": staff_id, "name": name, "permissions": clean_permissions.split(",")}


@router.get("/staff")
def list_staff(x_admin_passcode: str = Header(default="")):
    require_master(x_admin_passcode)
    conn = get_conn()
    rows = conn.execute("SELECT id, name, permissions, is_active, created_at FROM staff").fetchall()
    conn.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


@router.put("/staff/{staff_id}")
def update_staff(
    staff_id: str,
    name: str = Form(None),
    permissions: str = Form(None),
    is_active: bool = Form(None),
    x_admin_passcode: str = Header(default=""),
):
    require_master(x_admin_passcode)
    conn = get_conn()
    staff = conn.execute("SELECT * FROM staff WHERE id = ?", (staff_id,)).fetchone()
    if not staff:
        conn.close()
        raise HTTPException(status_code=404, detail="Staff member not found")

    new_name = name if name is not None else staff["name"]
    new_permissions = (
        ",".join(p.strip() for p in permissions.split(",") if p.strip())
        if permissions is not None else staff["permissions"]
    )
    new_is_active = int(is_active) if is_active is not None else staff["is_active"]

    conn.execute(
        "UPDATE staff SET name = ?, permissions = ?, is_active = ? WHERE id = ?",
        (new_name, new_permissions, new_is_active, staff_id),
    )
    conn.commit()
    conn.close()
    return {"id": staff_id, "name": new_name, "permissions": new_permissions.split(","), "is_active": bool(new_is_active)}


@router.delete("/staff/{staff_id}")
def delete_staff(staff_id: str, x_admin_passcode: str = Header(default="")):
    require_master(x_admin_passcode)
    conn = get_conn()
    result = conn.execute("DELETE FROM staff WHERE id = ?", (staff_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return {"id": staff_id, "deleted": True}
