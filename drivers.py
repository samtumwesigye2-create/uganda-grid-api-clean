"""
drivers.py — Driver management: fleet, dispatch tasks, live location,
photo-verified pickups/dropoffs.

Photo proof is REQUIRED (not optional) on the three statuses that
represent a physical handoff: picked_up, dropped_off_customer,
dropped_off_warehouse. This is enforced server-side so a driver can't
skip proof under time pressure — 20 assigned dropoffs means 20 photos,
guaranteed by the API itself, not by UI discipline.

Driver auth is passcode-based, same pattern as staff (auth.py).
"""

import os
import sqlite3
import time
import uuid

from fastapi import APIRouter, Form, Header, HTTPException, Query, UploadFile, File

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
ADMIN_PASSCODE = os.environ.get("ADMIN_PASSCODE", "uganda2026")

UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_PHOTO_BYTES = 15 * 1024 * 1024

router = APIRouter()

TASK_STATUSES = [
    "assigned", "en_route_pickup", "arrived_pickup", "picked_up",
    "en_route_dropoff", "arrived_dropoff", "dropped_off_customer",
    "dropped_off_warehouse", "completed", "failed", "cancelled",
]
PHOTO_REQUIRED_STATUSES = {"picked_up", "dropped_off_customer", "dropped_off_warehouse"}
DRIVER_STATUSES = ["available", "on_duty", "off_duty"]
VEHICLE_STATUSES = ["available", "in_use", "maintenance"]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vehicles (
            id TEXT PRIMARY KEY,
            plate_number TEXT UNIQUE NOT NULL,
            vehicle_type TEXT NOT NULL,
            capacity_kg REAL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'available',
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS drivers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            passcode TEXT UNIQUE NOT NULL,
            vehicle_id TEXT,
            status TEXT NOT NULL DEFAULT 'off_duty',
            current_lat REAL,
            current_lon REAL,
            last_ping_at REAL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dispatch_tasks (
            id TEXT PRIMARY KEY,
            task_number TEXT UNIQUE NOT NULL,
            shipment_number TEXT,
            task_type TEXT NOT NULL,
            location_text TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            driver_id TEXT,
            vehicle_id TEXT,
            status TEXT NOT NULL DEFAULT 'assigned',
            photo_url TEXT,
            notes TEXT,
            scheduled_at REAL,
            created_at REAL NOT NULL,
            completed_at REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dispatch_task_counter (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            next_number INTEGER NOT NULL
        )
        """
    )
    conn.execute("INSERT OR IGNORE INTO dispatch_task_counter (id, next_number) VALUES (1, 1)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS driver_location_pings (
            id TEXT PRIMARY KEY,
            driver_id TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dispatch_task_history (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT,
            photo_url TEXT,
            created_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


def check_admin(x_admin_passcode: str):
    if x_admin_passcode != ADMIN_PASSCODE:
        raise HTTPException(status_code=401, detail="Invalid passcode")


def get_driver_by_passcode(passcode: str):
    if not passcode:
        return None
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM drivers WHERE passcode = ? AND is_active = 1", (passcode,)
    ).fetchone()
    conn.close()
    return row


def require_driver(x_driver_passcode: str):
    driver = get_driver_by_passcode(x_driver_passcode)
    if not driver:
        raise HTTPException(status_code=401, detail="Invalid driver passcode")
    return driver


def next_task_number():
    conn = get_conn()
    n = conn.execute("SELECT next_number FROM dispatch_task_counter WHERE id = 1").fetchone()["next_number"]
    conn.execute("UPDATE dispatch_task_counter SET next_number = ? WHERE id = 1", (n + 1,))
    conn.commit()
    conn.close()
    return f"UG-TASK-{n:06d}"


def log_task_history(conn, task_id, status, note, photo_url):
    conn.execute(
        """
        INSERT INTO dispatch_task_history (id, task_id, status, note, photo_url, created_at)
        VALUES (?,?,?,?,?,?)
        """,
        (str(uuid.uuid4()), task_id, status, note, photo_url, time.time()),
    )


# --- Vehicles (admin only) ---

@router.post("/fleet/vehicles")
def create_vehicle(
    plate_number: str = Form(...),
    vehicle_type: str = Form(...),
    capacity_kg: float = Form(0),
    x_admin_passcode: str = Header(default=""),
):
    check_admin(x_admin_passcode)
    conn = get_conn()
    existing = conn.execute("SELECT id FROM vehicles WHERE plate_number = ?", (plate_number,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="A vehicle with this plate number already exists")
    vehicle_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO vehicles (id, plate_number, vehicle_type, capacity_kg, status, created_at) VALUES (?,?,?,?,?,?)",
        (vehicle_id, plate_number, vehicle_type, capacity_kg, "available", time.time()),
    )
    conn.commit()
    conn.close()
    return {"id": vehicle_id, "plate_number": plate_number, "vehicle_type": vehicle_type}


@router.get("/fleet/vehicles")
def list_vehicles(x_admin_passcode: str = Header(default="")):
    check_admin(x_admin_passcode)
    conn = get_conn()
    rows = conn.execute("SELECT * FROM vehicles ORDER BY created_at DESC").fetchall()
    conn.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


@router.put("/fleet/vehicles/{vehicle_id}")
def update_vehicle(
    vehicle_id: str,
    plate_number: str = Form(None),
    vehicle_type: str = Form(None),
    capacity_kg: float = Form(None),
    status: str = Form(None),
    x_admin_passcode: str = Header(default=""),
):
    check_admin(x_admin_passcode)
    if status is not None and status not in VEHICLE_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    conn = get_conn()
    row = conn.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Vehicle not found")
    conn.execute(
        "UPDATE vehicles SET plate_number=?, vehicle_type=?, capacity_kg=?, status=? WHERE id=?",
        (
            plate_number if plate_number is not None else row["plate_number"],
            vehicle_type if vehicle_type is not None else row["vehicle_type"],
            capacity_kg if capacity_kg is not None else row["capacity_kg"],
            status if status is not None else row["status"],
            vehicle_id,
        ),
    )
    conn.commit()
    conn.close()
    return {"id": vehicle_id, "updated": True}


@router.delete("/fleet/vehicles/{vehicle_id}")
def delete_vehicle(vehicle_id: str, x_admin_passcode: str = Header(default="")):
    check_admin(x_admin_passcode)
    conn = get_conn()
    result = conn.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return {"id": vehicle_id, "deleted": True}


# --- Drivers (admin creates/manages; driver self-service via passcode) ---

@router.post("/fleet/drivers")
def create_driver(
    name: str = Form(...),
    phone: str = Form(""),
    passcode: str = Form(...),
    vehicle_id: str = Form(""),
    x_admin_passcode: str = Header(default=""),
):
    check_admin(x_admin_passcode)
    conn = get_conn()
    existing = conn.execute("SELECT id FROM drivers WHERE passcode = ?", (passcode,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="That passcode is already in use")
    driver_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO drivers (id, name, phone, passcode, vehicle_id, status, is_active, created_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (driver_id, name, phone, passcode, vehicle_id or None, "off_duty", 1, time.time()),
    )
    conn.commit()
    conn.close()
    return {"id": driver_id, "name": name}


@router.get("/fleet/drivers")
def list_drivers(x_admin_passcode: str = Header(default="")):
    check_admin(x_admin_passcode)
    conn = get_conn()
    rows = conn.execute("SELECT * FROM drivers ORDER BY created_at DESC").fetchall()
    conn.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


@router.put("/fleet/drivers/{driver_id}")
def update_driver(
    driver_id: str,
    name: str = Form(None),
    phone: str = Form(None),
    vehicle_id: str = Form(None),
    is_active: bool = Form(None),
    x_admin_passcode: str = Header(default=""),
):
    check_admin(x_admin_passcode)
    conn = get_conn()
    row = conn.execute("SELECT * FROM drivers WHERE id = ?", (driver_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Driver not found")
    conn.execute(
        "UPDATE drivers SET name=?, phone=?, vehicle_id=?, is_active=? WHERE id=?",
        (
            name if name is not None else row["name"],
            phone if phone is not None else row["phone"],
            vehicle_id if vehicle_id is not None else row["vehicle_id"],
            int(is_active) if is_active is not None else row["is_active"],
            driver_id,
        ),
    )
    conn.commit()
    conn.close()
    return {"id": driver_id, "updated": True}


@router.delete("/fleet/drivers/{driver_id}")
def delete_driver(driver_id: str, x_admin_passcode: str = Header(default="")):
    check_admin(x_admin_passcode)
    conn = get_conn()
    result = conn.execute("DELETE FROM drivers WHERE id = ?", (driver_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Driver not found")
    return {"id": driver_id, "deleted": True}


# --- Driver self-service (auth via x-driver-passcode header) ---

@router.get("/driver/me")
def driver_me(x_driver_passcode: str = Header(default="")):
    driver = require_driver(x_driver_passcode)
    return dict(driver)


@router.post("/driver/location")
def post_location(
    latitude: float = Form(...),
    longitude: float = Form(...),
    x_driver_passcode: str = Header(default=""),
):
    driver = require_driver(x_driver_passcode)
    conn = get_conn()
    conn.execute(
        "UPDATE drivers SET current_lat=?, current_lon=?, last_ping_at=? WHERE id=?",
        (latitude, longitude, time.time(), driver["id"]),
    )
    conn.execute(
        "INSERT INTO driver_location_pings (id, driver_id, latitude, longitude, created_at) VALUES (?,?,?,?,?)",
        (str(uuid.uuid4()), driver["id"], latitude, longitude, time.time()),
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


@router.post("/driver/status")
def set_driver_status(
    status: str = Form(...),
    x_driver_passcode: str = Header(default=""),
):
    driver = require_driver(x_driver_passcode)
    if status not in DRIVER_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    conn = get_conn()
    conn.execute("UPDATE drivers SET status=? WHERE id=?", (status, driver["id"]))
    conn.commit()
    conn.close()
    return {"status": status}


@router.get("/driver/tasks")
def my_tasks(x_driver_passcode: str = Header(default="")):
    driver = require_driver(x_driver_passcode)
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM dispatch_tasks WHERE driver_id = ? AND status NOT IN ('completed','cancelled') ORDER BY created_at ASC",
        (driver["id"],),
    ).fetchall()
    conn.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


# --- Dispatch tasks (admin creates/assigns; driver updates own tasks) ---

@router.post("/dispatch/tasks")
def create_task(
    task_type: str = Form(...),
    location_text: str = Form(...),
    latitude: float = Form(None),
    longitude: float = Form(None),
    shipment_number: str = Form(""),
    driver_id: str = Form(""),
    vehicle_id: str = Form(""),
    notes: str = Form(""),
    scheduled_at: float = Form(None),
    x_admin_passcode: str = Header(default=""),
):
    check_admin(x_admin_passcode)
    if task_type not in ("pickup", "dropoff_customer", "dropoff_warehouse", "warehouse_transfer"):
        raise HTTPException(status_code=400, detail="Invalid task_type")

    task_id = str(uuid.uuid4())
    task_number = next_task_number()

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO dispatch_tasks
        (id, task_number, shipment_number, task_type, location_text, latitude, longitude,
         driver_id, vehicle_id, status, notes, scheduled_at, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (task_id, task_number, shipment_number or None, task_type, location_text,
         latitude, longitude, driver_id or None, vehicle_id or None, "assigned",
         notes, scheduled_at, time.time()),
    )
    log_task_history(conn, task_id, "assigned", "Task created", None)
    conn.commit()
    conn.close()

    return {"id": task_id, "task_number": task_number, "status": "assigned"}


@router.get("/dispatch/tasks")
def list_tasks(
    status: str = Query(default=""),
    driver_id: str = Query(default=""),
    x_admin_passcode: str = Header(default=""),
):
    check_admin(x_admin_passcode)
    conn = get_conn()
    query = "SELECT * FROM dispatch_tasks WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if driver_id:
        query += " AND driver_id = ?"
        params.append(driver_id)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


@router.put("/dispatch/tasks/{task_id}/assign")
def reassign_task(
    task_id: str,
    driver_id: str = Form(""),
    vehicle_id: str = Form(""),
    x_admin_passcode: str = Header(default=""),
):
    check_admin(x_admin_passcode)
    conn = get_conn()
    row = conn.execute("SELECT * FROM dispatch_tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    conn.execute(
        "UPDATE dispatch_tasks SET driver_id=?, vehicle_id=? WHERE id=?",
        (driver_id or None, vehicle_id or None, task_id),
    )
    log_task_history(conn, task_id, row["status"], "Reassigned", None)
    conn.commit()
    conn.close()
    return {"id": task_id, "reassigned": True}


@router.post("/dispatch/tasks/{task_id}/status")
async def update_task_status(
    task_id: str,
    status: str = Form(...),
    note: str = Form(""),
    photo: UploadFile = File(None),
    x_driver_passcode: str = Header(default=""),
    x_admin_passcode: str = Header(default=""),
):
    """Photo is REQUIRED for picked_up / dropped_off_customer /
    dropped_off_warehouse — enforced here, not just in the UI, so proof
    can't be skipped."""
    driver = None
    if x_admin_passcode == ADMIN_PASSCODE:
        pass  # admin override, always allowed, still must supply photo below if required
    else:
        driver = require_driver(x_driver_passcode)

    if status not in TASK_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    if status in PHOTO_REQUIRED_STATUSES and (photo is None or not photo.filename):
        raise HTTPException(
            status_code=400,
            detail=f"A photo is required to mark this task as '{status.replace('_', ' ')}'",
        )

    conn = get_conn()
    row = conn.execute("SELECT * FROM dispatch_tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")

    if driver and row["driver_id"] != driver["id"]:
        conn.close()
        raise HTTPException(status_code=403, detail="This task is not assigned to you")

    photo_url = None
    if photo is not None and photo.filename:
        if photo.content_type not in ALLOWED_PHOTO_TYPES:
            conn.close()
            raise HTTPException(status_code=400, detail="Unsupported photo type")
        contents = await photo.read()
        if len(contents) > MAX_PHOTO_BYTES:
            conn.close()
            raise HTTPException(status_code=400, detail="Photo too large (max 15MB)")
        ext = os.path.splitext(photo.filename)[1][:10]
        filename = str(uuid.uuid4()) + ext
        filepath = os.path.join(UPLOADS_DIR, filename)
        with open(filepath, "wb") as out:
            out.write(contents)
        photo_url = "/uploads/" + filename

    completed_at = time.time() if status in ("completed", "dropped_off_customer", "dropped_off_warehouse") else row["completed_at"]

    conn.execute(
        "UPDATE dispatch_tasks SET status=?, photo_url=COALESCE(?, photo_url), completed_at=? WHERE id=?",
        (status, photo_url, completed_at, task_id),
    )
    log_task_history(conn, task_id, status, note, photo_url)
    conn.commit()
    conn.close()

    return {"id": task_id, "status": status, "photo_url": photo_url}


@router.get("/dispatch/tasks/{task_id}/history")
def task_history(task_id: str, x_admin_passcode: str = Header(default="")):
    check_admin(x_admin_passcode)
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM dispatch_task_history WHERE task_id = ? ORDER BY created_at ASC", (task_id,)
    ).fetchall()
    conn.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


@router.get("/dispatch/photo-audit")
def photo_audit(
    driver_id: str = Query(default=""),
    x_admin_passcode: str = Header(default=""),
):
    """Reconciliation view: for every task that reached a proof-required
    status, confirm a photo actually exists. Flags any gap — this is how
    you verify '20 dropoffs = 20 photos' at a glance."""
    check_admin(x_admin_passcode)
    conn = get_conn()
    query = "SELECT * FROM dispatch_tasks WHERE status IN ('picked_up','dropped_off_customer','dropped_off_warehouse')"
    params = []
    if driver_id:
        query += " AND driver_id = ?"
        params.append(driver_id)
    rows = conn.execute(query, params).fetchall()
    conn.close()

    total = len(rows)
    with_photo = sum(1 for r in rows if r["photo_url"])
    missing = [dict(r) for r in rows if not r["photo_url"]]

    return {
        "total_proof_required_tasks": total,
        "tasks_with_photo": with_photo,
        "tasks_missing_photo": len(missing),
        "missing": missing,
    }
