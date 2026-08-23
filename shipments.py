"""
Shipment / Parcel Management module for Uganda National Grid (UGAMAP)
--------------------------------------------------------------------
Drop into repo root alongside main.py (replaces the earlier version),
then in main.py add (same as before, no change needed if already added):

    from shipments import router as shipments_router
    app.include_router(shipments_router)

Also add to main.py, near your other imports, if not already present:

    from fastapi.responses import HTMLResponse

New in this version: rate quoting (rates.py), Flutterwave payment
(payments.py), and a printable HTML receipt.

Env vars needed (Railway/Render → Variables):
    FLW_SECRET_KEY   - your Flutterwave secret key
    PUBLIC_BASE_URL  - e.g. https://uganda-grid-api-clean-production.up.railway.app
                       (used to build the Flutterwave redirect URL)
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import rates
import payments

router = APIRouter(prefix="/api/shipments", tags=["shipments"])

DB_PATH = Path(__file__).parent / "shipments_database.json"

STATUS_FLOW = [
    "created", "picked_up", "in_transit", "out_for_delivery",
    "delivered", "failed_delivery", "returned",
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


def _find(data, tracking_number):
    for s in data["shipments"]:
        if s["tracking_number"] == tracking_number:
            return s
    return None


# ---------- models ----------

class Party(BaseModel):
    name: str
    phone: Optional[str] = None
    address: str


class ShipmentCreate(BaseModel):
    sender: Party
    receiver: Party
    description: Optional[str] = None
    weight_kg: Optional[float] = None
    speed: Optional[str] = None      # one of rates.SPEED_TIERS keys
    price: Optional[float] = None
    currency: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None
    location: Optional[str] = None


class QuoteRequest(BaseModel):
    origin: str          # grid ID or address
    destination: str
    weight_kg: float


# ---------- quoting ----------

@router.post("/quote")
def get_quote(req: QuoteRequest):
    origin_coords = rates.resolve_coordinates(req.origin)
    dest_coords = rates.resolve_coordinates(req.destination)
    if not origin_coords or not dest_coords:
        raise HTTPException(
            400,
            "Could not resolve one or both addresses to coordinates. "
            "Use a known grid ID (e.g. UG-ENT-000001)."
        )
    try:
        distance_km = rates.road_distance_km(origin_coords, dest_coords)
    except Exception as e:
        raise HTTPException(502, f"Routing service error: {e}")

    return rates.quote_all_tiers(distance_km, req.weight_kg)


# ---------- shipment CRUD ----------

@router.post("")
def create_shipment(shipment: ShipmentCreate):
    data = _load()
    tracking_number = _next_tracking_number(data)
    now = datetime.now(timezone.utc).isoformat()

    speed_label = rates.SPEED_TIERS[shipment.speed]["label"] if shipment.speed in rates.SPEED_TIERS else None

    record = {
        "tracking_number": tracking_number,
        "sender": shipment.sender.dict(),
        "receiver": shipment.receiver.dict(),
        "description": shipment.description,
        "weight_kg": shipment.weight_kg,
        "speed": shipment.speed,
        "speed_label": speed_label,
        "price": shipment.price,
        "currency": shipment.currency or "UGX",
        "payment_status": "unpaid" if shipment.price else None,
        "payment_tx_ref": None,
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
    s = _find(data, tracking_number)
    if not s:
        raise HTTPException(404, "No shipment found with that tracking number")
    return s


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
    s = _find(data, tracking_number)
    if not s:
        raise HTTPException(404, "No shipment found with that tracking number")
    s["status"] = update.status
    s["history"].append({
        "status": update.status,
        "note": update.note,
        "location": update.location,
        "at": datetime.now(timezone.utc).isoformat(),
    })
    _save(data)
    return s


# ---------- payment ----------

@router.post("/{tracking_number}/pay")
def start_payment(tracking_number: str):
    data = _load()
    s = _find(data, tracking_number)
    if not s:
        raise HTTPException(404, "No shipment found with that tracking number")
    if not s.get("price"):
        raise HTTPException(400, "This shipment has no price set — get a quote first.")
    if s.get("payment_status") == "paid":
        raise HTTPException(400, "This shipment is already paid.")

    tx_ref = f"{tracking_number}-{uuid.uuid4().hex[:8]}"
    base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    redirect_url = f"{base_url}/api/shipments/{tracking_number}/payment-callback"

    try:
        link = payments.initiate_payment(
            tx_ref=tx_ref,
            amount=s["price"],
            currency=s.get("currency", "UGX"),
            customer_email=s["sender"].get("email") or "customer@ugamap.app",
            customer_name=s["sender"]["name"],
            redirect_url=redirect_url,
        )
    except Exception as e:
        raise HTTPException(502, f"Payment provider error: {e}")

    s["payment_tx_ref"] = tx_ref
    _save(data)
    return {"payment_link": link, "tx_ref": tx_ref}


@router.get("/{tracking_number}/payment-callback", response_class=HTMLResponse)
def payment_callback(
    tracking_number: str,
    status: Optional[str] = Query(None),
    tx_ref: Optional[str] = Query(None),
    transaction_id: Optional[str] = Query(None),
):
    """Flutterwave redirects the customer's browser here after checkout."""
    data = _load()
    s = _find(data, tracking_number)
    if not s:
        return HTMLResponse("<h1>Shipment not found</h1>", status_code=404)

    verified_ok = False
    if status == "successful" and transaction_id:
        try:
            verification = payments.verify_payment(transaction_id)
            if (
                verification.get("status") == "successful"
                and verification.get("tx_ref") == s.get("payment_tx_ref")
                and float(verification.get("amount", 0)) >= float(s["price"])
            ):
                verified_ok = True
        except Exception:
            verified_ok = False

    if verified_ok:
        s["payment_status"] = "paid"
        s["history"].append({
            "status": s["status"],
            "note": f"Payment confirmed ({transaction_id})",
            "at": datetime.now(timezone.utc).isoformat(),
        })
        _save(data)
        message = "Payment confirmed — thank you!"
    else:
        message = "Payment was not confirmed. If you were charged, contact support with your tracking number."

    return HTMLResponse(f"""
    <html><body style="font-family: sans-serif; padding: 40px; text-align: center;">
      <h1>{message}</h1>
      <p>Tracking number: <strong>{tracking_number}</strong></p>
      <p><a href="/admin">Back to UGAMAP Admin</a></p>
    </body></html>
    """)


# ---------- receipt ----------

@router.get("/{tracking_number}/receipt", response_class=HTMLResponse)
def receipt(tracking_number: str):
    data = _load()
    s = _find(data, tracking_number)
    if not s:
        return HTMLResponse("<h1>Shipment not found</h1>", status_code=404)

    price_row = ""
    if s.get("price"):
        price_row = f"""
        <tr><td>Service</td><td>{s.get('speed_label') or s.get('speed') or '—'}</td></tr>
        <tr><td>Weight</td><td>{s.get('weight_kg') or '—'} kg</td></tr>
        <tr><td><strong>Total</strong></td><td><strong>{s['price']:,.0f} {s.get('currency', 'UGX')}</strong></td></tr>
        <tr><td>Payment status</td><td>{s.get('payment_status') or 'unpaid'}</td></tr>
        """

    return HTMLResponse(f"""
    <html>
    <head>
      <title>Receipt — {tracking_number}</title>
      <style>
        body {{ font-family: -apple-system, sans-serif; max-width: 480px; margin: 30px auto; color: #111; }}
        h1 {{ font-size: 1.3rem; margin-bottom: 0; }}
        .muted {{ color: #666; font-size: 0.85rem; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        td {{ padding: 8px 4px; border-bottom: 1px solid #eee; font-size: 0.9rem; }}
        button {{ margin-top: 20px; padding: 10px 18px; font-size: 0.95rem; }}
        @media print {{ button {{ display: none; }} }}
      </style>
    </head>
    <body>
      <h1>UGAMAP Shipment Receipt</h1>
      <p class="muted">Tracking number: {tracking_number}</p>
      <table>
        <tr><td>From</td><td>{s['sender']['name']}, {s['sender']['address']}</td></tr>
        <tr><td>To</td><td>{s['receiver']['name']}, {s['receiver']['address']}</td></tr>
        <tr><td>Description</td><td>{s.get('description') or '—'}</td></tr>
        {price_row}
        <tr><td>Status</td><td>{s['status']}</td></tr>
        <tr><td>Created</td><td>{s['created_at']}</td></tr>
      </table>
      <button onclick="window.print()">Print receipt</button>
    </body>
    </html>
    """)
