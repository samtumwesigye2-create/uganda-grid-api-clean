from __future__ import annotations

import math
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
IN_PROGRESS = {"en_route_pickup", "arrived_pickup", "picked_up", "en_route_dropoff", "arrived_dropoff"}


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


def _haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    try:
        p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
        dp = math.radians(float(lat2) - float(lat1))
        dl = math.radians(float(lon2) - float(lon1))
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    except (TypeError, ValueError):
        return None


def _delivery_destination(c, task: Dict[str, Any]) -> Dict[str, Any]:
    shipment = task.get("shipment_number")
    if not shipment:
        return {}
    try:
        order = c.execute("SELECT delivery_address,delivery_grid_id FROM orders WHERE shipment_number=? ORDER BY updated_at DESC LIMIT 1", (shipment,)).fetchone()
        if order:
            return {"delivery_address": order["delivery_address"] or "", "delivery_grid_id": order["delivery_grid_id"] or ""}
    except sqlite3.Error:
        pass
    return {}


def _leg_mode(task: Dict[str, Any]) -> str:
    status = str(task.get("status") or "").lower()
    ttype = str(task.get("task_type") or "").lower()
    notes = str(task.get("notes") or "").lower()
    pickup_only = "pickup_only" in ttype or "[pickup_only]" in notes
    if "warehouse_transfer" in ttype or "handoff" in ttype:
        return "HANDOFF"
    if "pickup" in ttype and status in {"picked_up", "en_route_dropoff", "arrived_dropoff"} and not pickup_only:
        return "DELIVERY"
    if "pickup" in ttype:
        return "PICKUP"
    return "DELIVERY"


def _sequence(c, d: Dict[str, Any], rows: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    now = time.time()
    out = []
    for task in rows:
        t = dict(task)
        status = str(t.get("status") or "").lower()
        notes = str(t.get("notes") or "").lower()
        urgent = any(k in notes for k in ("urgent", "priority", "asap", "expedite"))
        scheduled = float(t["scheduled_at"]) if t.get("scheduled_at") else None
        overdue = bool(scheduled and scheduled < now)
        dist = _haversine_km(d.get("current_lat"), d.get("current_lon"), t.get("latitude"), t.get("longitude"))
        mode = _leg_mode(t)
        delivery = _delivery_destination(c, t) if mode == "DELIVERY" else {}
        navigation_destination = delivery.get("delivery_grid_id") or delivery.get("delivery_address") or (
            f"{t.get('latitude')},{t.get('longitude')}" if t.get("latitude") is not None and t.get("longitude") is not None else t.get("location_text") or ""
        )
        # Keep work already in progress first, then urgent/overdue/time-window work, then nearer stops.
        score = 0.0
        reason = "NEXT PLANNED STOP"
        if status in IN_PROGRESS:
            score -= 100000
            reason = "CONTINUE ACTIVE STOP"
        if urgent:
            score -= 30000
            reason = "URGENT / PRIORITY"
        if overdue:
            score -= 20000
            reason = "SCHEDULE WINDOW DUE"
        if scheduled:
            score += max(-5000, min(5000, (scheduled - now) / 60.0))
        if dist is not None:
            score += dist * 12
        else:
            score += 1000
        drive_eta = None
        if dist is not None:
            # Low-confidence road estimate: 1.25 road-factor at 30 km/h; UGAMAP can replace this with live routing later.
            drive_eta = max(1, int(round((dist * 1.25 / 30.0) * 60)))
        t.update({
            "leg_mode": mode,
            "priority_reason": reason,
            "urgent": urgent,
            "overdue": overdue,
            "distance_km_straight_line": round(dist, 1) if dist is not None else None,
            "eta_minutes": drive_eta,
            "eta_confidence": "LOW" if drive_eta is not None else "UNKNOWN",
            "scheduled_in_minutes": int(round((scheduled - now) / 60)) if scheduled else None,
            "navigation_destination": navigation_destination,
            "delivery_grid_id": delivery.get("delivery_grid_id") or "",
            "delivery_address": delivery.get("delivery_address") or "",
            "sequence_score": score,
        })
        out.append(t)
    out.sort(key=lambda x: (x["sequence_score"], float(x.get("scheduled_at") or 9e18), float(x.get("created_at") or 0)))
    for i, item in enumerate(out, 1):
        item["sequence"] = i
        item.pop("sequence_score", None)
    return out


@router.get("")
def dashboard(x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    c = _conn()
    try:
        _ensure(c)
        rows = [dict(x) for x in c.execute("SELECT * FROM dispatch_tasks WHERE driver_id=? AND status NOT IN ('completed','failed','cancelled','dropped_off_customer','dropped_off_warehouse') ORDER BY created_at", (d["id"],)).fetchall()]
        readiness = _readiness(c, d)
        sequence = _sequence(c, d, rows)
    finally:
        c.close()
    pickups = sum(1 for x in sequence if x["leg_mode"] == "PICKUP")
    deliveries = sum(1 for x in sequence if x["leg_mode"] in {"DELIVERY", "HANDOFF"})
    urgent = sum(1 for x in sequence if x["urgent"])
    next_stop = sequence[0] if sequence else None
    return {
        "driver": {"id": d["id"], "name": d.get("name"), "status": d.get("status")},
        "active_stops": len(sequence), "pickups": pickups, "deliveries": deliveries,
        "urgent": urgent, "next_stop": next_stop,
        "eta_minutes": next_stop.get("eta_minutes") if next_stop else None,
        "eta_confidence": next_stop.get("eta_confidence") if next_stop else "UNKNOWN",
        "sequence": sequence,
        "sequencing_policy": "ACTIVE_WORK > URGENT > DUE_WINDOW > PROXIMITY",
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
        sequence = _sequence(c, d, rows)
    finally:
        c.close()
    if not readiness["ready"]:
        raise HTTPException(409, detail={"message": "Route start blocked by readiness gate", **readiness})
    if not rows:
        raise HTTPException(409, "No active stops assigned")
    result = engine.execute(ExecuteRequest(
        ucode="U-1810",
        parameters={"planned_stop_count": len(rows), "pickup_count": sum(1 for x in sequence if x['leg_mode'] == 'PICKUP'), "readiness_verified": True, "initial_next_stop_id": sequence[0]["id"] if sequence else None},
        client_request_id=payload.client_request_id,
        actor_id=d["id"], role="DRIVER", device_id=payload.device_id,
    ))
    return {"started": True, "stop_count": len(rows), "readiness": readiness, "next_stop": sequence[0] if sequence else None, "ugatu": result.model_dump()}
