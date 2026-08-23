"""
Shipment / Parcel Management module for Uganda National Grid (UGAMAP)
--------------------------------------------------------------------
Drop into repo root alongside main.py, then in main.py add:

    from shipments import router as shipments_router
    app.include_router(shipments_router)

Tracking numbers follow the same style as your grid IDs (UG-ENT-000001)
so it feels consistent: UG-SHIP-000001, UG-SHIP-000002, ...

Covers: create shipment, look up by tracking number, update status,
list by sender/receiver/status, and a status-history timeline per
shipment (so customers can see "Picked up -> In transit -> Delivered").
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/shipments", tags=["shipments"])

DB_PATH = Path(__file__).parent / "shipments_database.json"

STATUS_FLOW = [
    "created",
    "picked_up",
    "in_transit",
    "out_for_delivery",
    "delivered",
    "failed_delivery",
    "returned",
]


def _load():
    if not DB_PATH.exists():
        data = {"shipments": [], "next_number": 1}
        _save(data)
        return data
    return json.loads(DB_PATH.read_text())


def _save(data):
    DB_PATH.write_text(json.dumps(data, indent=2, default=str))


def _next_tracking_number(data):
    n = data["next_number"]
    data["next_number"] += 1
    return f"UG-SHIP-{n:06d}"


# ---------- models ----------

class Party(BaseModel):
    name: str
    phone: Optional[str] = None
    address: str            # can be a grid ID (e.g. UG-ENT-000400) or free text


class ShipmentCreate(BaseModel):
    sender: Party
    receiver: Party
    description: Optional[str] = None
    weight_kg: Optional[float] = None


class StatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None
    location: Optional[str] = None


# ---------- endpoints ----------

@router.post("")
def create_shipment(shipment: ShipmentCreate):
    data = _load()
    tracking_number = _next_tracking_number(data)
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "tracking_number": tracking_number,
        "sender": shipment.sender.dict(),
        "receiver": shipment.receiver.dict(),
        "description": shipment.description,
        "weight_kg": shipment.weight_kg,
        "status": "created",
        "created_at": now,
        "history": [{"status": "created", "note": "Shipment registered", "at": now}],
    }
    data["shipments"].append(record)
    _save(data)
    return record


@router.get("/{tracking_number}")
def get_shipment(tracking_number: str):
    data = _load()
    for s in data["shipments"]:
        if s["tracking_number"] == tracking_number:
            return s
    raise HTTPException(404, "No shipment found with that tracking number")


@router.get("")
def list_shipments(
    status: Optional[str] = None,
    sender_phone: Optional[str] = None,
    receiver_phone: Optional[str] = None,
):
    data = _load()
    results = data["shipments"]
    if status:
        results = [s for s in results if s["status"] == status]
    if sender_phone:
        results = [s for s in results if s["sender"].get("phone") == sender_phone]
    if receiver_phone:
        results = [s for s in results if s["receiver"].get("phone") == receiver_phone]
    return results


@router.patch("/{tracking_number}/status")
def update_status(tracking_number: str, update: StatusUpdate):
    if update.status not in STATUS_FLOW:
        raise HTTPException(400, f"status must be one of {STATUS_FLOW}")
    data = _load()
    for s in data["shipments"]:
        if s["tracking_number"] == tracking_number:
            s["status"] = update.status
            s["history"].append({
                "status": update.status,
                "note": update.note,
                "location": update.location,
                "at": datetime.now(timezone.utc).isoformat(),
            })
            _save(data)
            return s
    raise HTTPException(404, "No shipment found with that tracking number")
