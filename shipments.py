"""
Shipment / Parcel Management module for Uganda National Grid (UGAMAP)
--------------------------------------------------------------------
Drop into repo root alongside main.py, then in main.py add (if not
already added):

    from shipments import router as shipments_router
    app.include_router(shipments_router)

Also add to main.py, near your other imports, if not already present:

    from fastapi.responses import HTMLResponse

Requires payments.py (Flutterwave) and rates.py (quoting) to be in the
same directory.

Env vars needed (Railway/Render -> Variables):
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
    "delivered", "failed_delivery", "returned", "cancelled",
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
    country: Optional[str] = "Uganda"


class CustomsInfo(BaseModel):
    declared_value: Optional[float] = None
    declared_value_currency: Optional[str] = "USD"
    description: Optional[str] = None
    hs_code: Optional[str] = None


class ShipmentCreate(BaseModel):
    sender: Party
    receiver: Party
    description: Optional[str] = None
    weight_kg: Optional[float] = None
    speed: Optional[str] = None      # one of rates.SPEED_TIERS keys (domestic)
    zone: Optional[str] = None       # one of rates.INTERNATIONAL_ZONES keys (international)
    customs: Optional[CustomsInfo] = None
    price: Optional[float] = None
    currency: Optional[str] = None


class ShipmentEdit(BaseModel):
    description: Optional[str] = None
    weight_kg: Optional[float] = None
    speed: Optional[str] = None
    zone: Optional[str] = None
    customs: Optional[CustomsInfo] = None
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


class InternationalQuoteRequest(BaseModel):
    zone: str
    weight_kg: float


def _is_international(sender: dict, receiver: dict) -> bool:
    origin_country = (sender.get("country") or "Uganda").strip().lower()
    dest_country = (receiver.get("country") or "Uganda").strip().lower()
    return origin_country != dest_country


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


@router.get("/zones")
def list_international_zones():
    """List available international shipping zones with their (manually
    set) base fee, per-kg rate, and estimated transit time."""
    return rates.INTERNATIONAL_ZONES


@router.post("/quote/international")
def get_international_quote(req: InternationalQuoteRequest):
    try:
        return rates.quote_international(req.zone, req.weight_kg)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------- shipment CRUD ----------

@router.post("")
def create_shipment(shipment: ShipmentCreate):
    data = _load()
    tracking_number = _next_tracking_number(data)
    now = datetime.now(timezone.utc).isoformat()

    sender_dict = shipment.sender.dict()
    receiver_dict = shipment.receiver.dict()
    international = _is_international(sender_dict, receiver_dict)

    speed_label = rates.SPEED_TIERS[shipment.speed]["label"] if shipment.speed in rates.SPEED_TIERS else None
    zone_label = rates.INTERNATIONAL_ZONES[shipment.zone]["label"] if shipment.zone in rates.INTERNATIONAL_ZONES else None

    record = {
        "tracking_number": tracking_number,
        "sender": sender_dict,
        "receiver": receiver_dict,
        "international": international,
        "description": shipment.description,
        "weight_kg": shipment.weight_kg,
        "speed": shipment.speed,
        "speed_label": speed_label,
        "zone": shipment.zone,
        "zone_label": zone_label,
        "customs": shipment.customs.dict() if shipment.customs else None,
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
    international: Optional[bool] = None,
):
    data = _load()
    results = data["shipments"]
    if status:
        results = [s for s in results if s["status"] == status]
    if sender_phone:
        results = [s for s in results if s["sender"].get("phone") == sender_phone]
    if receiver_phone:
        results = [s for s in results if s["receiver"].get("phone") == receiver_phone]
    if international is not None:
        results = [s for s in results if bool(s.get("international")) == international]
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


@router.patch("/{tracking_number}")
def edit_shipment(tracking_number: str, edit: ShipmentEdit):
    """Edit description/weight/tier/price on a shipment that hasn't been paid yet."""
    data = _load()
    s = _find(data, tracking_number)
    if not s:
        raise HTTPException(404, "No shipment found with that tracking number")
    if s.get("payment_status") == "paid":
        raise HTTPException(400, "Cannot edit a shipment that has already been paid.")

    changed = []
    if edit.description is not None:
        s["description"] = edit.description
        changed.append("description")
    if edit.weight_kg is not None:
        s["weight_kg"] = edit.weight_kg
        changed.append("weight_kg")
    if edit.speed is not None:
        if edit.speed not in rates.SPEED_TIERS:
            raise HTTPException(400, f"speed must be one of {list(rates.SPEED_TIERS.keys())}")
        s["speed"] = edit.speed
        s["speed_label"] = rates.SPEED_TIERS[edit.speed]["label"]
        changed.append("speed")
    if edit.zone is not None:
        if edit.zone not in rates.INTERNATIONAL_ZONES:
            raise HTTPException(400, f"zone must be one of {list(rates.INTERNATIONAL_ZONES.keys())}")
        s["zone"] = edit.zone
        s["zone_label"] = rates.INTERNATIONAL_ZONES[edit.zone]["label"]
        changed.append("zone")
    if edit.customs is not None:
        s["customs"] = edit.customs.dict()
        changed.append("customs")
    if edit.price is not None:
        s["price"] = edit.price
        s["payment_status"] = "unpaid"
        changed.append("price")
    if edit.currency is not None:
        s["currency"] = edit.currency
        changed.append("currency")

    if changed:
        s["history"].append({
            "status": s["status"],
            "note": f"Updated: {', '.join(changed)}",
            "at": datetime.now(timezone.utc).isoformat(),
        })
        _save(data)
    return s


@router.post("/{tracking_number}/cancel")
def cancel_shipment(tracking_number: str, note: Optional[str] = None):
    """Cancel a shipment that hasn't been paid yet."""
    data = _load()
    s = _find(data, tracking_number)
    if not s:
        raise HTTPException(404, "No shipment found with that tracking number")
    if s.get("payment_status") == "paid":
        raise HTTPException(400, "Cannot cancel a paid shipment — contact support for a refund instead.")
    if s["status"] == "cancelled":
        raise HTTPException(400, "Shipment is already cancelled.")

    s["status"] = "cancelled"
    s["history"].append({
        "status": "cancelled",
        "note": note or "Cancelled",
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

    service_row_label = "Service"
    service_row_value = s.get('speed_label') or s.get('zone_label') or s.get('speed') or s.get('zone') or '—'

    price_row = ""
    if s.get("price"):
        price_row = f"""
        <tr><td>{service_row_label}</td><td>{service_row_value}</td></tr>
        <tr><td>Weight</td><td>{s.get('weight_kg') or '—'} kg</td></tr>
        <tr><td><strong>Total</strong></td><td><strong>{s['price']:,.0f} {s.get('currency', 'UGX')}</strong></td></tr>
        <tr><td>Payment status</td><td>{s.get('payment_status') or 'unpaid'}</td></tr>
        """

    customs_row = ""
    if s.get("international") and s.get("customs"):
        c = s["customs"]
        customs_row = f"""
        <tr><td>Declared value</td><td>{c.get('declared_value') or '—'} {c.get('declared_value_currency') or ''}</td></tr>
        <tr><td>Customs description</td><td>{c.get('description') or '—'}</td></tr>
        <tr><td>HS code</td><td>{c.get('hs_code') or '—'}</td></tr>
        """

    international_row = ""
    if s.get("international"):
        international_row = '<tr><td>Shipment type</td><td>International</td></tr>'

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
        <tr><td>From</td><td>{s['sender']['name']}, {s['sender']['address']}, {s['sender'].get('country', 'Uganda')}</td></tr>
        <tr><td>To</td><td>{s['receiver']['name']}, {s['receiver']['address']}, {s['receiver'].get('country', 'Uganda')}</td></tr>
        {international_row}
        <tr><td>Description</td><td>{s.get('description') or '—'}</td></tr>
        {price_row}
        {customs_row}
        <tr><td>Status</td><td>{s['status']}</td></tr>
        <tr><td>Created</td><td>{s['created_at']}</td></tr>
      </table>
      <button onclick="window.print()">Print receipt</button>
    </body>
    </html>
    """)
