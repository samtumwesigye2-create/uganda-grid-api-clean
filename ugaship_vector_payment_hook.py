"""Automatic paid-shipment custody handoff from UGASHIP to UNG-VECTOR.

Payment is never rolled back because VECTOR is unavailable. Instead, the handoff
is persisted as pending and retried safely. A permanent UG-SHIP number is used
as VECTOR's cross-system reference.
"""
from __future__ import annotations

import os
import time
import requests
from fastapi import APIRouter, Header, HTTPException

import shipments

router = APIRouter(tags=["UGASHIP VECTOR payment handoff"])
VECTOR_API_URL = os.environ.get("VECTOR_API_URL", "https://ung-vector-production.up.railway.app").rstrip("/")
VECTOR_TIMEOUT = float(os.environ.get("VECTOR_TIMEOUT_SECONDS", "8"))
VECTOR_SERVICE_TOKEN = os.environ.get("UGASHIP_VECTOR_SERVICE_TOKEN", "").strip()
ADMIN_PASSCODE = os.environ.get("ADMIN_PASSCODE", "")
INTAKE_SKU = os.environ.get("UGASHIP_VECTOR_INTAKE_SKU", "UGASHIP-PARCEL")
INTAKE_LOCATION = os.environ.get("UGASHIP_VECTOR_INTAKE_LOCATION", "UGASHIP-INTAKE")
_INSTALLED = False
_ORIGINAL_FINALIZE = None


def _ensure_outbox():
    conn = shipments.get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vector_handoffs (
            shipment_number TEXT PRIMARY KEY,
            movement_type TEXT NOT NULL,
            sku TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            from_location TEXT,
            to_location TEXT,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            vector_movement_id TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.commit(); conn.close()


def _authorization():
    if not VECTOR_SERVICE_TOKEN:
        raise RuntimeError("UGASHIP_VECTOR_SERVICE_TOKEN is not configured")
    return {"Authorization": f"Bearer {VECTOR_SERVICE_TOKEN}", "Accept": "application/json"}


def _vector(method: str, path: str, payload: dict | None = None):
    r = requests.request(method, f"{VECTOR_API_URL}{path}", json=payload, headers=_authorization(), timeout=VECTOR_TIMEOUT)
    try:
        body = r.json()
    except ValueError:
        body = {"detail": "invalid JSON from VECTOR"}
    if r.status_code >= 400:
        raise RuntimeError(str(body.get("detail") or f"VECTOR HTTP {r.status_code}"))
    return body


def _queue(shipment_number: str):
    _ensure_outbox()
    now = time.time()
    conn = shipments.get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO vector_handoffs
           (shipment_number,movement_type,sku,quantity,from_location,to_location,status,attempts,created_at,updated_at)
           VALUES(?,?,?,?,?,?,?,0,?,?)""",
        (shipment_number, "receive", INTAKE_SKU, 1, None, INTAKE_LOCATION, "pending", now, now),
    )
    conn.commit(); conn.close()


def _mark(shipment_number: str, status: str, error: str = "", movement_id: str | None = None):
    conn = shipments.get_conn()
    conn.execute(
        """UPDATE vector_handoffs
           SET status=?, attempts=attempts+1, last_error=?, vector_movement_id=COALESCE(?,vector_movement_id), updated_at=?
           WHERE shipment_number=?""",
        (status, error[:1000], movement_id, time.time(), shipment_number),
    )
    conn.commit(); conn.close()


def _send(shipment_number: str):
    _queue(shipment_number)
    conn = shipments.get_conn()
    row = conn.execute("SELECT * FROM vector_handoffs WHERE shipment_number=?", (shipment_number,)).fetchone()
    conn.close()
    if not row:
        raise RuntimeError("handoff outbox row missing")
    if row["status"] == "sent":
        return {"status": "sent", "idempotent_replay": True, "vector_movement_id": row["vector_movement_id"]}

    try:
        existing = _vector("GET", "/v1/movements")
        items = existing if isinstance(existing, list) else existing.get("results", []) if isinstance(existing, dict) else []
        for movement in items:
            if str(movement.get("reference") or "") == shipment_number and movement.get("movement_type") == row["movement_type"]:
                mid = str(movement.get("id") or "") or None
                _mark(shipment_number, "sent", movement_id=mid)
                return {"status": "sent", "idempotent_replay": True, "movement": movement}

        payload = {
            "sku": row["sku"], "quantity": int(row["quantity"]), "movement_type": row["movement_type"],
            "from_location": row["from_location"], "to_location": row["to_location"], "reference": shipment_number,
        }
        movement = _vector("POST", "/v1/movements", payload)
        mid = str(movement.get("id") or "") if isinstance(movement, dict) else ""
        _mark(shipment_number, "sent", movement_id=mid or None)
        return {"status": "sent", "idempotent_replay": False, "movement": movement}
    except Exception as exc:
        _mark(shipment_number, "pending", error=f"{type(exc).__name__}: {exc}")
        return {"status": "pending", "error": f"{type(exc).__name__}: {exc}"}


def install_payment_hook():
    global _INSTALLED, _ORIGINAL_FINALIZE
    if _INSTALLED:
        return
    _ensure_outbox()
    _ORIGINAL_FINALIZE = shipments._finalize_payment

    def wrapped_finalize(row, method_label: str, amount_paid: float = None):
        shipment_number = _ORIGINAL_FINALIZE(row, method_label, amount_paid)
        # Only permanent paid shipment numbers enter VECTOR custody.
        if str(shipment_number).startswith("UG-SHIP-"):
            _send(shipment_number)
        return shipment_number

    shipments._finalize_payment = wrapped_finalize
    _INSTALLED = True


def _admin(value: str):
    if not ADMIN_PASSCODE or value != ADMIN_PASSCODE:
        raise HTTPException(status_code=401, detail="Invalid passcode")


@router.get("/ship/integration/vector/payment-handoffs/{shipment_number}")
def payment_handoff_status(shipment_number: str, x_admin_passcode: str = Header(default="")):
    _admin(x_admin_passcode)
    _ensure_outbox()
    conn = shipments.get_conn()
    row = conn.execute("SELECT * FROM vector_handoffs WHERE shipment_number=?", (shipment_number,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="VECTOR handoff not found")
    return dict(row)


@router.post("/ship/integration/vector/payment-handoffs/{shipment_number}/retry")
def retry_payment_handoff(shipment_number: str, x_admin_passcode: str = Header(default="")):
    _admin(x_admin_passcode)
    _queue(shipment_number)
    return _send(shipment_number)


@router.get("/ship/integration/vector/payment-handoffs")
def list_payment_handoffs(status: str = "", x_admin_passcode: str = Header(default="")):
    _admin(x_admin_passcode)
    _ensure_outbox()
    conn = shipments.get_conn()
    if status:
        rows = conn.execute("SELECT * FROM vector_handoffs WHERE status=? ORDER BY updated_at DESC LIMIT 100", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM vector_handoffs ORDER BY updated_at DESC LIMIT 100").fetchall()
    conn.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}
