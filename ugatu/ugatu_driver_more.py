from __future__ import annotations

import os
import sqlite3
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/ugatu/driver-more", tags=["UGATU Driver More"])
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")

EVENT_TO_UCODE = {
    "ACCEPT_VEHICLE": "U-1910",
    "PRE_TRIP": "U-1920",
    "FUEL": "U-1950",
    "CHARGE": "U-1950",
    "ODOMETER": "U-1950",
    "DEFECT": "U-1960",
    "BREAKDOWN": "U-1970",
    "POST_TRIP": "U-1980",
}


class VehicleEventIn(BaseModel):
    event_type: str
    odometer: float | None = Field(default=None, ge=0)
    fuel_amount: float | None = Field(default=None, ge=0)
    charge_kwh: float | None = Field(default=None, ge=0)
    severity: str = "NORMAL"
    out_of_service: bool = False
    notes: str = ""


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _driver(passcode: str) -> Dict[str, Any]:
    if not passcode:
        raise HTTPException(401, "Driver passcode required")
    c = _conn()
    try:
        row = c.execute("SELECT * FROM drivers WHERE passcode=? AND is_active=1", (passcode,)).fetchone()
    finally:
        c.close()
    if not row:
        raise HTTPException(401, "Invalid driver passcode")
    return dict(row)


def _ensure(c: sqlite3.Connection) -> None:
    c.execute(
        """CREATE TABLE IF NOT EXISTS ugatu_driver_vehicle_events (
        id TEXT PRIMARY KEY,
        driver_id TEXT NOT NULL,
        vehicle_id TEXT,
        ucode TEXT NOT NULL,
        event_type TEXT NOT NULL,
        odometer REAL,
        fuel_amount REAL,
        charge_kwh REAL,
        severity TEXT NOT NULL DEFAULT 'NORMAL',
        out_of_service INTEGER NOT NULL DEFAULT 0,
        notes TEXT,
        created_at REAL NOT NULL
        )"""
    )


def _vehicle(c: sqlite3.Connection, driver: Dict[str, Any]):
    if not driver.get("vehicle_id"):
        return None
    return c.execute("SELECT * FROM vehicles WHERE id=?", (driver["vehicle_id"],)).fetchone()


@router.get("")
def more_center(x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    c = _conn()
    try:
        _ensure(c)
        vehicle = _vehicle(c, d)
        active_count = c.execute(
            "SELECT COUNT(*) n FROM dispatch_tasks WHERE driver_id=? AND status NOT IN ('completed','failed','cancelled','dropped_off_customer','dropped_off_warehouse')",
            (d["id"],),
        ).fetchone()["n"]
        recent_events = c.execute(
            "SELECT * FROM ugatu_driver_vehicle_events WHERE driver_id=? ORDER BY created_at DESC LIMIT 12",
            (d["id"],),
        ).fetchall()
        dispatch_history = c.execute(
            """SELECT h.status,h.note,h.photo_url,h.created_at,t.id task_id,t.task_number,t.task_type,t.location_text,t.shipment_number
            FROM dispatch_task_history h JOIN dispatch_tasks t ON t.id=h.task_id
            WHERE t.driver_id=? ORDER BY h.created_at DESC LIMIT 20""",
            (d["id"],),
        ).fetchall()
        returns = c.execute(
            """SELECT * FROM dispatch_tasks WHERE driver_id=? AND (
            task_type='dropoff_warehouse' OR lower(COALESCE(notes,'')) LIKE '%return%'
            ) ORDER BY created_at DESC LIMIT 20""",
            (d["id"],),
        ).fetchall()
    finally:
        c.close()

    safe_driver = {
        "id": d.get("id"),
        "name": d.get("name"),
        "phone": d.get("phone"),
        "status": d.get("status"),
        "last_ping_at": d.get("last_ping_at"),
    }
    return {
        "driver": safe_driver,
        "vehicle": dict(vehicle) if vehicle else None,
        "active_task_count": int(active_count),
        "vehicle_events": [dict(x) for x in recent_events],
        "dispatch_history": [dict(x) for x in dispatch_history],
        "returns": [dict(x) for x in returns],
    }


@router.post("/vehicle-event")
def record_vehicle_event(payload: VehicleEventIn, x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    event_type = payload.event_type.strip().upper()
    if event_type not in EVENT_TO_UCODE:
        raise HTTPException(400, "Unsupported vehicle event")
    severity = payload.severity.strip().upper() or "NORMAL"
    if severity not in {"NORMAL", "WARNING", "HIGH", "CRITICAL"}:
        raise HTTPException(400, "Invalid severity")
    if event_type in {"DEFECT", "BREAKDOWN"} and not payload.notes.strip():
        raise HTTPException(400, "Describe the defect or breakdown")

    c = _conn()
    try:
        _ensure(c)
        vehicle = _vehicle(c, d)
        if not vehicle and event_type != "ODOMETER":
            raise HTTPException(409, "No vehicle is assigned to this driver")
        eid = str(uuid.uuid4())
        ucode = EVENT_TO_UCODE[event_type]
        now = time.time()
        c.execute(
            "INSERT INTO ugatu_driver_vehicle_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                eid, d["id"], d.get("vehicle_id"), ucode, event_type,
                payload.odometer, payload.fuel_amount, payload.charge_kwh,
                severity, int(payload.out_of_service), payload.notes.strip()[:2000], now,
            ),
        )
        # Safety-critical driver reports can take the assigned vehicle out of service,
        # but drivers cannot return a vehicle to service from this endpoint.
        if d.get("vehicle_id") and payload.out_of_service and event_type in {"DEFECT", "BREAKDOWN"}:
            c.execute("UPDATE vehicles SET status='maintenance' WHERE id=?", (d["vehicle_id"],))
        c.commit()
    finally:
        c.close()
    return {"id": eid, "ucode": ucode, "event_type": event_type, "recorded": True, "out_of_service": bool(payload.out_of_service)}


@router.get("/history")
def vehicle_history(x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    c = _conn()
    try:
        _ensure(c)
        rows = c.execute(
            "SELECT * FROM ugatu_driver_vehicle_events WHERE driver_id=? ORDER BY created_at DESC LIMIT 100",
            (d["id"],),
        ).fetchall()
    finally:
        c.close()
    return {"count": len(rows), "results": [dict(x) for x in rows]}
