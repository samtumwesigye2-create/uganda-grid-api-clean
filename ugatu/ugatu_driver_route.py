from __future__ import annotations

import os
import sqlite3
import time
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from .ugatu_engine import engine
from .ugatu_models import ExecuteRequest

router = APIRouter(prefix="/api/ugatu/driver-route", tags=["UGATU Driver Route"])
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")


class DynamicPickupRequest(BaseModel):
    client_request_id: str = Field(min_length=4, max_length=120)
    location_text: str = Field(min_length=2, max_length=300)
    shipment_number: str | None = None
    package_id: str | None = None
    freight_id: str | None = None
    notes: str = ""
    latitude: float | None = None
    longitude: float | None = None


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _driver(passcode: str):
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


def _ensure_dynamic_table(c: sqlite3.Connection) -> None:
    c.execute(
        """CREATE TABLE IF NOT EXISTS ugatu_dynamic_pickups (
        client_request_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        driver_id TEXT NOT NULL,
        package_or_freight_id TEXT,
        created_at REAL NOT NULL
        )"""
    )


def _next_task_number(c: sqlite3.Connection) -> str:
    row = c.execute("SELECT next_number FROM dispatch_task_counter WHERE id=1").fetchone()
    if not row:
        c.execute("INSERT INTO dispatch_task_counter(id,next_number) VALUES(1,2)")
        return "UG-TASK-000001"
    n = int(row["next_number"])
    c.execute("UPDATE dispatch_task_counter SET next_number=? WHERE id=1", (n + 1,))
    return f"UG-TASK-{n:06d}"


@router.get("/manifest")
def manifest(x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    c = _conn()
    try:
        active = c.execute(
            """SELECT * FROM dispatch_tasks
               WHERE driver_id=? AND status NOT IN
               ('completed','failed','cancelled','dropped_off_customer','dropped_off_warehouse')
               ORDER BY created_at""",
            (d["id"],),
        ).fetchall()
        _ensure_dynamic_table(c)
        dyn = c.execute(
            """SELECT udp.*, dt.task_number, dt.shipment_number, dt.location_text, dt.status
               FROM ugatu_dynamic_pickups udp
               JOIN dispatch_tasks dt ON dt.id=udp.task_id
               WHERE udp.driver_id=? ORDER BY udp.created_at DESC LIMIT 100""",
            (d["id"],),
        ).fetchall()
    finally:
        c.close()

    active_rows = [dict(x) for x in active]
    pickup_rows = [x for x in active_rows if str(x.get("task_type", "")).lower() == "pickup"]
    custody_rows = [x for x in active_rows if str(x.get("status", "")).lower() == "picked_up"]
    return {
        "driver_id": d["id"],
        "active_count": len(active_rows),
        "pickup_count": len(pickup_rows),
        "custody_count": len(custody_rows),
        "unaccounted_count": len(custody_rows),
        "active": active_rows,
        "dynamic_pickups": [dict(x) for x in dyn],
    }


@router.post("/dynamic-pickup")
def create_dynamic_pickup(payload: DynamicPickupRequest, x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    item_id = (payload.package_id or payload.freight_id or "").strip() or None
    c = _conn()
    try:
        _ensure_dynamic_table(c)
        prior = c.execute(
            "SELECT task_id FROM ugatu_dynamic_pickups WHERE client_request_id=?",
            (payload.client_request_id,),
        ).fetchone()
        if prior:
            task = c.execute("SELECT * FROM dispatch_tasks WHERE id=?", (prior["task_id"],)).fetchone()
            return {"created": False, "duplicate": True, "task": dict(task) if task else {"id": prior["task_id"]}}

        task_id = str(uuid.uuid4())
        task_number = _next_task_number(c)
        notes = "UGATU dynamic pickup"
        if item_id:
            notes += f" | item:{item_id}"
        if payload.notes:
            notes += f" | {payload.notes}"
        now = time.time()
        c.execute(
            """INSERT INTO dispatch_tasks
               (id,task_number,shipment_number,task_type,location_text,latitude,longitude,
                driver_id,vehicle_id,status,notes,scheduled_at,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                task_id,
                task_number,
                payload.shipment_number or None,
                "pickup",
                payload.location_text,
                payload.latitude,
                payload.longitude,
                d["id"],
                d.get("vehicle_id") or None,
                "assigned",
                notes,
                now,
                now,
            ),
        )
        c.execute(
            "INSERT INTO dispatch_task_history VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), task_id, "assigned", "UGATU dynamic pickup created", None, now),
        )
        c.execute(
            "INSERT INTO ugatu_dynamic_pickups VALUES (?,?,?,?,?)",
            (payload.client_request_id, task_id, d["id"], item_id, now),
        )
        c.commit()
    except sqlite3.Error as exc:
        c.rollback()
        raise HTTPException(500, f"Could not create dynamic pickup: {exc}") from exc
    finally:
        c.close()

    command = engine.execute(
        ExecuteRequest(
            ucode="U-1860",
            parameters={
                "task_id": task_id,
                "task_number": task_number,
                "shipment_id": payload.shipment_number,
                "package_id": item_id,
                "location_text": payload.location_text,
                "dynamic_stop_type": "PICKUP",
            },
            client_request_id=f"{payload.client_request_id}-U1860",
            actor_id=d["id"],
            role="DRIVER",
            device_id="DRIVER-IPAD",
        )
    )
    return {
        "created": True,
        "task": {"id": task_id, "task_number": task_number, "status": "assigned", "task_type": "pickup"},
        "ugatu": command.model_dump(),
    }


@router.post("/complete-route")
def complete_route(payload: Dict[str, Any], x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    c = _conn()
    try:
        open_rows = c.execute(
            """SELECT id,task_number,status,task_type FROM dispatch_tasks
               WHERE driver_id=? AND status NOT IN
               ('completed','failed','cancelled','dropped_off_customer','dropped_off_warehouse')""",
            (d["id"],),
        ).fetchall()
    finally:
        c.close()
    if open_rows:
        raise HTTPException(
            409,
            detail={"message": "Route cannot close while active stops remain", "active_stops": [dict(x) for x in open_rows]},
        )
    request_id = str(payload.get("client_request_id") or f"ROUTE-{uuid.uuid4()}")
    result = engine.execute(
        ExecuteRequest(
            ucode="U-1890",
            parameters={"driver_id": d["id"], "reconciled": True, "unaccounted_count": 0},
            client_request_id=request_id,
            actor_id=d["id"],
            role="DRIVER",
            device_id=str(payload.get("device_id") or "DRIVER-IPAD"),
        )
    )
    return {"completed": True, "unaccounted_count": 0, "ugatu": result.model_dump()}
