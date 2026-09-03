from __future__ import annotations

import os
import sqlite3
import time
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/api/ugatu/driver-center", tags=["UGATU Driver Center"])
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
FINAL = {"completed", "failed", "cancelled", "dropped_off_customer", "dropped_off_warehouse"}


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
        """CREATE TABLE IF NOT EXISTS ugatu_driver_alert_reads (
        driver_id TEXT NOT NULL,
        alert_id TEXT NOT NULL,
        read_at REAL NOT NULL,
        PRIMARY KEY(driver_id, alert_id)
        )"""
    )


def _alert(task: Dict[str, Any], kind: str, title: str, message: str, priority: str, ucode: str) -> Dict[str, Any]:
    return {
        "id": f"{kind}:{task.get('id')}",
        "kind": kind,
        "title": title,
        "message": message,
        "priority": priority,
        "ucode": ucode,
        "task_id": task.get("id"),
        "task_number": task.get("task_number"),
        "shipment_number": task.get("shipment_number"),
        "task_type": task.get("task_type"),
        "status": task.get("status"),
        "location_text": task.get("location_text"),
        "latitude": task.get("latitude"),
        "longitude": task.get("longitude"),
        "created_at": task.get("created_at"),
    }


@router.get("")
def driver_center(x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    c = _conn()
    try:
        _ensure(c)
        rows = c.execute(
            "SELECT * FROM dispatch_tasks WHERE driver_id=? ORDER BY created_at DESC LIMIT 150",
            (d["id"],),
        ).fetchall()
        vehicle = None
        if d.get("vehicle_id"):
            vehicle = c.execute("SELECT * FROM vehicles WHERE id=?", (d["vehicle_id"],)).fetchone()
        reads = {r["alert_id"] for r in c.execute("SELECT alert_id FROM ugatu_driver_alert_reads WHERE driver_id=?", (d["id"],)).fetchall()}
    finally:
        c.close()

    alerts = []
    now = time.time()
    for raw in rows:
        t = dict(raw)
        status = str(t.get("status") or "assigned").lower()
        if status in FINAL:
            continue
        task_type = str(t.get("task_type") or "").lower()
        notes = str(t.get("notes") or "")
        urgent = any(k in notes.lower() for k in ("urgent", "priority", "asap", "expedite"))
        if status == "assigned":
            alerts.append(_alert(t, "assignment", "New Assignment", f"{t.get('task_number')} · {t.get('location_text')}", "HIGH" if urgent else "NORMAL", "U-2020"))
        if task_type == "pickup":
            alerts.append(_alert(t, "pickup", "Pickup Task", f"Pickup at {t.get('location_text')}", "HIGH" if urgent else "NORMAL", "U-2040"))
        if urgent:
            alerts.append(_alert(t, "urgent", "Priority / Urgent Job", f"{t.get('task_number')} requires priority handling", "URGENT", "U-2080"))
        if status in {"arrived_pickup", "arrived_dropoff"} and not t.get("photo_url"):
            alerts.append(_alert(t, "document", "Proof Required", "A proof photo/document is required before this stop can close.", "HIGH", "U-2050"))
        scheduled = t.get("scheduled_at")
        if scheduled and float(scheduled) < now and status == "assigned":
            alerts.append(_alert(t, "late", "Stop Needs Attention", f"Scheduled time has passed for {t.get('task_number')}", "HIGH", "U-2060"))

    if vehicle and str(vehicle["status"]).lower() == "maintenance":
        alerts.append({
            "id": f"vehicle:{vehicle['id']}:maintenance",
            "kind": "vehicle",
            "title": "Vehicle Alert",
            "message": f"Vehicle {vehicle['plate_number']} is marked maintenance.",
            "priority": "URGENT",
            "ucode": "U-2070",
            "vehicle_id": vehicle["id"],
            "task_id": None,
            "created_at": now,
        })

    for a in alerts:
        a["read"] = a["id"] in reads
    order = {"URGENT": 0, "HIGH": 1, "NORMAL": 2}
    alerts.sort(key=lambda a: (a["read"], order.get(a.get("priority"), 3), -(a.get("created_at") or 0)))
    unread = sum(1 for a in alerts if not a["read"])
    return {"driver_id": d["id"], "count": len(alerts), "unread_count": unread, "results": alerts}


@router.post("/{alert_id:path}/read")
def mark_read(alert_id: str, x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    c = _conn()
    try:
        _ensure(c)
        c.execute(
            "INSERT OR REPLACE INTO ugatu_driver_alert_reads(driver_id,alert_id,read_at) VALUES (?,?,?)",
            (d["id"], alert_id, time.time()),
        )
        c.commit()
    finally:
        c.close()
    return {"alert_id": alert_id, "read": True}
