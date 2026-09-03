from __future__ import annotations

import os
import sqlite3
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .ugatu_engine import engine
from .ugatu_models import ExecuteRequest

router = APIRouter(prefix="/api/ugatu/driver-dashboard", tags=["UGATU Driver Dashboard"])
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
FINAL = {"completed", "failed", "cancelled", "dropped_off_customer", "dropped_off_warehouse"}


class RouteStartIn(BaseModel):
    client_request_id: str
    device_id: str = "DRIVER-IPAD"


def _conn():
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


def _ensure(c):
    c.execute("""CREATE TABLE IF NOT EXISTS ugatu_driver_shifts (
        id TEXT PRIMARY KEY, driver_id TEXT NOT NULL, started_at REAL NOT NULL,
        ended_at REAL, status TEXT NOT NULL DEFAULT 'ACTIVE'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS ugatu_driver_vehicle_events (
        id TEXT PRIMARY KEY, driver_id TEXT NOT NULL, vehicle_id TEXT, ucode TEXT NOT NULL,
        event_type TEXT NOT NULL, odometer REAL, fuel_amount REAL, charge_kwh REAL,
        severity TEXT NOT NULL DEFAULT 'NORMAL', out_of_service INTEGER NOT NULL DEFAULT 0,
        notes TEXT, created_at REAL NOT NULL
    )""")


def _shift(c, driver_id: str):
    return c.execute("SELECT * FROM ugatu_driver_shifts WHERE driver_id=? AND status='ACTIVE' ORDER BY started_at DESC LIMIT 1", (driver_id,)).fetchone()


def _readiness(c, d: Dict[str, Any]) -> Dict[str, Any]:
    vehicle = c.execute("SELECT * FROM vehicles WHERE id=?", (d.get("vehicle_id"),)).fetchone() if d.get("vehicle_id") else None
    shift = _shift(c, d["id"])
    midnight = time.time() - 18 * 3600
    pretrip = None
    if vehicle:
        pretrip = c.execute("""SELECT * FROM ugatu_driver_vehicle_events
            WHERE driver_id=? AND vehicle_id=? AND event_type='PRE_TRIP' AND created_at>=?
            ORDER BY created_at DESC LIMIT 1""", (d["id"], vehicle["id"], midnight)).fetchone()
    reasons = []
    if not shift:
        reasons.append("SHIFT_NOT_STARTED")
    if not vehicle:
        reasons.append("NO_VEHICLE_ASSIGNED")
    elif str(vehicle["status"] or "").lower() == "maintenance":
        reasons.append("VEHICLE_OUT_OF_SERVICE")
    if vehicle and not pretrip:
        reasons.append("PRE_TRIP_REQUIRED")
    if pretrip and int(pretrip["out_of_service"] or 0):
        reasons.append("PRE_TRIP_OUT_OF_SERVICE")
    return {
        "ready": not reasons,
        "reasons": reasons,
        "shift_active": bool(shift),
        "vehicle": dict(vehicle) if vehicle else None,
        "pretrip_complete": bool(pretrip),
        "pretrip_at": pretrip["created_at"] if pretrip else None,
    }


@router.get("")
def dashboard(x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    c = _conn()
    try:
        _ensure(c)
        rows = [dict(x) for x in c.execute("SELECT * FROM dispatch_tasks WHERE driver_id=? AND status NOT IN ('completed','failed','cancelled','dropped_off_customer','dropped_off_warehouse') ORDER BY created_at", (d["id"],)).fetchall()]
        readiness = _readiness(c, d)
    finally:
        c.close()
    pickups = sum(1 for x in rows if str(x.get("task_type") or "").lower() == "pickup")
    deliveries = len(rows) - pickups
    urgent = sum(1 for x in rows if any(k in str(x.get("notes") or "").lower() for k in ("urgent", "priority", "asap", "expedite")))
    next_stop = rows[0] if rows else None
    eta = None
    if next_stop and next_stop.get("scheduled_at"):
        eta = max(0, int((float(next_stop["scheduled_at"]) - time.time()) / 60))
    return {
        "driver": {"id": d["id"], "name": d.get("name"), "status": d.get("status")},
        "active_stops": len(rows), "pickups": pickups, "deliveries": deliveries,
        "urgent": urgent, "next_stop": next_stop, "eta_minutes": eta,
        "readiness": readiness,
    }


@router.post("/shift/start")
def start_shift(x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    c = _conn()
    try:
        _ensure(c)
        current = _shift(c, d["id"])
        if current:
            return {"started": False, "already_active": True, "shift": dict(current)}
        sid = str(uuid.uuid4()); now = time.time()
        c.execute("INSERT INTO ugatu_driver_shifts(id,driver_id,started_at,status) VALUES(?,?,?,'ACTIVE')", (sid, d["id"], now))
        c.execute("UPDATE drivers SET status='on_duty' WHERE id=?", (d["id"],))
        c.commit()
        return {"started": True, "shift": {"id": sid, "started_at": now, "status": "ACTIVE"}}
    finally:
        c.close()


@router.post("/shift/end")
def end_shift(x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    c = _conn()
    try:
        _ensure(c)
        active = c.execute("SELECT COUNT(*) n FROM dispatch_tasks WHERE driver_id=? AND status NOT IN ('completed','failed','cancelled','dropped_off_customer','dropped_off_warehouse')", (d["id"],)).fetchone()["n"]
        if active:
            raise HTTPException(409, f"Cannot end shift with {active} active stop(s)")
        shift = _shift(c, d["id"])
        if not shift:
            return {"ended": False, "already_closed": True}
        now = time.time()
        c.execute("UPDATE ugatu_driver_shifts SET ended_at=?,status='ENDED' WHERE id=?", (now, shift["id"]))
        c.execute("UPDATE drivers SET status='off_duty' WHERE id=?", (d["id"],))
        c.commit()
        return {"ended": True, "ended_at": now}
    finally:
        c.close()


@router.post("/route/start")
def protected_route_start(payload: RouteStartIn, x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    c = _conn()
    try:
        _ensure(c)
        readiness = _readiness(c, d)
        rows = [dict(x) for x in c.execute("SELECT * FROM dispatch_tasks WHERE driver_id=? AND status NOT IN ('completed','failed','cancelled','dropped_off_customer','dropped_off_warehouse') ORDER BY created_at", (d["id"],)).fetchall()]
    finally:
        c.close()
    if not readiness["ready"]:
        raise HTTPException(409, detail={"message": "Route start blocked by readiness gate", **readiness})
    if not rows:
        raise HTTPException(409, "No active stops assigned")
    result = engine.execute(ExecuteRequest(
        ucode="U-1810",
        parameters={"planned_stop_count": len(rows), "pickup_count": sum(1 for x in rows if x.get('task_type') == 'pickup'), "readiness_verified": True},
        client_request_id=payload.client_request_id,
        actor_id=d["id"], role="DRIVER", device_id=payload.device_id,
    ))
    return {"started": True, "stop_count": len(rows), "readiness": readiness, "ugatu": result.model_dump()}
