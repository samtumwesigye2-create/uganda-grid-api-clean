from __future__ import annotations

import os
import sqlite3
from typing import Any

from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/api/ugatu/driver-orders", tags=["UGATU Driver Orders"])
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _driver(passcode: str) -> dict[str, Any]:
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


def _table_columns(c: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(x["name"]) for x in c.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def _shipment(c: sqlite3.Connection, shipment_number: str | None) -> dict[str, Any] | None:
    if not shipment_number:
        return None
    try:
        row = c.execute("SELECT * FROM shipments WHERE shipment_number=?", (shipment_number,)).fetchone()
        return dict(row) if row else None
    except sqlite3.Error:
        return None


def _order(c: sqlite3.Connection, shipment_number: str | None) -> dict[str, Any] | None:
    if not shipment_number:
        return None
    try:
        row = c.execute("SELECT * FROM orders WHERE shipment_number=? ORDER BY updated_at DESC LIMIT 1", (shipment_number,)).fetchone()
        if not row:
            return None
        out = dict(row)
        out["items"] = [dict(x) for x in c.execute(
            "SELECT sku,name,quantity,unit_price,line_total FROM order_items WHERE order_id=? ORDER BY rowid",
            (row["id"],),
        ).fetchall()]
        return out
    except sqlite3.Error:
        return None


def _freight_summary(order: dict[str, Any] | None, shipment: dict[str, Any] | None, task: dict[str, Any]) -> dict[str, Any]:
    items = (order or {}).get("items") or []
    quantity = sum(float(x.get("quantity") or 0) for x in items)
    return {
        "item_count": len(items),
        "quantity": quantity,
        "weight_kg": (shipment or {}).get("weight_kg"),
        "shipment_type": (shipment or {}).get("shipment_type"),
        "speed_tier": (shipment or {}).get("speed_tier"),
        "items": items[:25],
        "package_or_freight_id": task.get("package_id") or task.get("freight_id") or task.get("item_id"),
    }


@router.get("")
def driver_orders(x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    c = _conn()
    try:
        rows = c.execute(
            """SELECT * FROM dispatch_tasks
               WHERE driver_id=? AND status NOT IN ('completed','failed','cancelled')
               ORDER BY created_at""",
            (d["id"],),
        ).fetchall()
        results = []
        for row in rows:
            task = dict(row)
            ship = _shipment(c, task.get("shipment_number"))
            order = _order(c, task.get("shipment_number"))
            task_type = str(task.get("task_type") or "").lower()
            service_type = "PICKUP" if "pickup" in task_type else ("HANDOFF" if "warehouse_transfer" in task_type else "DELIVERY")
            customer_name = (order or {}).get("customer_name") or (ship or {}).get("recipient_name") or (ship or {}).get("sender_name") or "Customer"
            customer_phone = (order or {}).get("customer_phone") or (ship or {}).get("recipient_phone") or (ship or {}).get("sender_phone") or ""
            destination = task.get("location_text") or (order or {}).get("delivery_address") or (ship or {}).get("delivery") or ""
            grid_id = (order or {}).get("delivery_grid_id") or ""
            results.append({
                "task_id": task.get("id"),
                "task_number": task.get("task_number"),
                "task_type": task.get("task_type"),
                "service_type": service_type,
                "status": task.get("status"),
                "shipment_number": task.get("shipment_number"),
                "order_number": (order or {}).get("order_number"),
                "order_status": (order or {}).get("status"),
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "location_text": destination,
                "delivery_grid_id": grid_id,
                "latitude": task.get("latitude"),
                "longitude": task.get("longitude"),
                "notes": task.get("notes") or (order or {}).get("notes") or "",
                "freight": _freight_summary(order, ship, task),
                "documents": {
                    "bill_of_lading": "/business-documents/bill-of-lading.html",
                    "receipt": "/business-documents/receipt.html",
                },
            })
    finally:
        c.close()
    return {
        "driver_id": d["id"],
        "count": len(results),
        "pickup_count": sum(1 for x in results if x["service_type"] == "PICKUP"),
        "delivery_count": sum(1 for x in results if x["service_type"] == "DELIVERY"),
        "handoff_count": sum(1 for x in results if x["service_type"] == "HANDOFF"),
        "results": results,
    }


@router.get("/{task_id}")
def driver_order_detail(task_id: str, x_driver_passcode: str = Header(default="")):
    d = _driver(x_driver_passcode)
    c = _conn()
    try:
        task = c.execute("SELECT * FROM dispatch_tasks WHERE id=? AND driver_id=?", (task_id, d["id"])).fetchone()
        if not task:
            raise HTTPException(404, "Driver order not found")
        taskd = dict(task)
        ship = _shipment(c, taskd.get("shipment_number"))
        order = _order(c, taskd.get("shipment_number"))
    finally:
        c.close()
    return {"task": taskd, "shipment": ship, "order": order, "freight": _freight_summary(order, ship, taskd)}
