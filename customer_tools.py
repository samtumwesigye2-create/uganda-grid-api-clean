import os
import sqlite3
import time
import uuid
from fastapi import APIRouter, Form, HTTPException

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
router = APIRouter()

ALLOWED_TYPES = {"schedule_pickup", "hold_delivery", "change_address", "po_box", "delivery_alerts"}


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("""
      CREATE TABLE IF NOT EXISTS customer_service_requests (
        id TEXT PRIMARY KEY,
        request_type TEXT NOT NULL,
        name TEXT,
        email TEXT,
        phone TEXT,
        tracking_number TEXT,
        address TEXT,
        details TEXT,
        status TEXT NOT NULL,
        created_at REAL NOT NULL
      )
    """)
    c.commit()
    return c


@router.post("/customer-tools/request")
def create_customer_request(
    request_type: str = Form(...),
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    tracking_number: str = Form(""),
    address: str = Form(""),
    details: str = Form(""),
):
    request_type = request_type.strip().lower()
    if request_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported request type")
    if not (email.strip() or phone.strip()):
        raise HTTPException(status_code=400, detail="Email or phone is required")
    rid = "UG-REQ-" + uuid.uuid4().hex[:10].upper()
    c = _conn()
    c.execute(
        "INSERT INTO customer_service_requests VALUES (?,?,?,?,?,?,?,?,?,?)",
        (rid, request_type, name.strip(), email.strip(), phone.strip(), tracking_number.strip().upper(), address.strip(), details.strip()[:1000], "received", time.time()),
    )
    c.commit(); c.close()
    return {"request_id": rid, "status": "received", "request_type": request_type}


@router.get("/customer-tools/request/{request_id}")
def get_customer_request(request_id: str):
    c = _conn()
    row = c.execute("SELECT id, request_type, status, created_at FROM customer_service_requests WHERE id = ?", (request_id.strip().upper(),)).fetchone()
    c.close()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    return dict(row)
