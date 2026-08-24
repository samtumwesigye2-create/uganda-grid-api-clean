import math
import os
import sqlite3
import time
import uuid

from fastapi import APIRouter, Form, Header, HTTPException, Query
from fastapi.responses import HTMLResponse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
ADMIN_PASSCODE = os.environ.get("ADMIN_PASSCODE", "uganda2026")

router = APIRouter()

SPEED_TIERS = {
    "seven_day": {"label": "7-Day", "multiplier": 1.0, "eta_days": 7},
    "three_day": {"label": "3-Day", "multiplier": 1.3, "eta_days": 3},
    "two_day": {"label": "2-Day", "multiplier": 1.6, "eta_days": 2},
    "one_day": {"label": "1-Day", "multiplier": 2.0, "eta_days": 1},
    "overnight": {"label": "Overnight", "multiplier": 2.6, "eta_days": 1},
    "express": {"label": "Express", "multiplier": 3.5, "eta_days": 0},
}

BASE_RATE_PER_KG = 1500
BASE_RATE_PER_KM = 200
MINIMUM_CHARGE = 3000


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS shipments (
            id TEXT PRIMARY KEY,
            shipment_number TEXT UNIQUE NOT NULL,
            pickup TEXT NOT NULL,
            delivery TEXT NOT NULL,
            weight_kg REAL NOT NULL,
            distance_km REAL NOT NULL,
            speed_tier TEXT NOT NULL,
            rate_ugx REAL NOT NULL,
            status TEXT NOT NULL,
            sender_name TEXT,
            sender_phone TEXT,
            recipient_name TEXT,
            recipient_phone TEXT,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS shipment_counter (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            next_number INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO shipment_counter (id, next_number) VALUES (1, 1)"
    )
    conn.commit()
    conn.close()


init_db()


def check_admin(x_admin_passcode: str):
    if x_admin_passcode != ADMIN_PASSCODE:
        raise HTTPException(status_code=401, detail="Invalid passcode")


def next_shipment_number():
    conn = get_conn()
    cur = conn.execute("SELECT next_number FROM shipment_counter WHERE id = 1")
    n = cur.fetchone()["next_number"]
    conn.execute("UPDATE shipment_counter SET next_number = ? WHERE id = 1", (n + 1,))
    conn.commit()
    conn.close()
    return f"UG-SHIP-{n:06d}"


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def lookup_coords(grid_id_or_address: str, addresses):
    query = grid_id_or_address.strip().lower()
    for item in addresses:
        if str(item.get("grid_id", "")).strip().lower() == query:
            return float(item.get("latitude", 0)), float(item.get("longitude", 0))
    for item in addresses:
        if query in str(item.get("address", "")).strip().lower():
            return float(item.get("latitude", 0)), float(item.get("longitude", 0))
    return None


def calculate_rate(distance_km: float, weight_kg: float, speed_tier: str):
    tier = SPEED_TIERS.get(speed_tier)
    if not tier:
        raise HTTPException(status_code=400, detail="Invalid speed tier")
    base = (weight_kg * BASE_RATE_PER_KG) + (distance_km * BASE_RATE_PER_KM)
    rate = max(base * tier["multiplier"], MINIMUM_CHARGE)
    return round(rate, -1)


def register_rate_routes(addresses_ref):
    @router.get("/ship/rates")
    def get_rates(
        pickup: str = Query(...),
        delivery: str = Query(...),
        weight_kg: float = Query(..., gt=0),
    ):
        addresses = addresses_ref()
        p = lookup_coords(pickup, addresses)
        d = lookup_coords(delivery, addresses)
        if not p or not d:
            raise HTTPException(status_code=404, detail="Pickup or delivery address not found in grid database")

        distance_km = round(haversine_km(p[0], p[1], d[0], d[1]), 2)

        quotes = []
        for key, tier in SPEED_TIERS.items():
            rate = calculate_rate(distance_km, weight_kg, key)
            quotes.append({
                "speed_tier": key,
                "label": tier["label"],
                "eta_days": tier["eta_days"],
                "rate_ugx": rate,
            })

        return {
            "pickup": pickup,
            "delivery": delivery,
            "weight_kg": weight_kg,
            "distance_km": distance_km,
            "quotes": quotes,
        }

    @router.post("/ship/create")
    def create_shipment(
        pickup: str = Form(...),
        delivery: str = Form(...),
        weight_kg: float = Form(..., gt=0),
        speed_tier: str = Form(...),
        sender_name: str = Form(""),
        sender_phone: str = Form(""),
        recipient_name: str = Form(""),
        recipient_phone: str = Form(""),
    ):
        addresses = addresses_ref()
        p = lookup_coords(pickup, addresses)
        d = lookup_coords(delivery, addresses)
        if not p or not d:
            raise HTTPException(status_code=404, detail="Pickup or delivery address not found in grid database")

        distance_km = round(haversine_km(p[0], p[1], d[0], d[1]), 2)
        rate = calculate_rate(distance_km, weight_kg, speed_tier)
        shipment_id = str(uuid.uuid4())
        shipment_number = next_shipment_number()

        conn = get_conn()
        conn.execute(
            """
            INSERT INTO shipments
            (id, shipment_number, pickup, delivery, weight_kg, distance_km,
             speed_tier, rate_ugx, status, sender_name, sender_phone,
             recipient_name, recipient_phone, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                shipment_id, shipment_number, pickup, delivery, weight_kg,
                distance_km, speed_tier, rate, "pending_payment",
                sender_name, sender_phone, recipient_name, recipient_phone,
                time.time(),
            ),
        )
        conn.commit()
        conn.close()

        return {
            "id": shipment_id,
            "shipment_number": shipment_number,
            "rate_ugx": rate,
            "distance_km": distance_km,
            "status": "pending_payment",
            "receipt_url": f"/ship/receipt/{shipment_number}",
        }


@router.post("/ship/{shipment_number}/pay")
def mark_paid(shipment_number: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM shipments WHERE shipment_number = ?", (shipment_number,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Shipment not found")
    conn.execute(
        "UPDATE shipments SET status = 'paid' WHERE shipment_number = ?",
        (shipment_number,),
    )
    conn.commit()
    conn.close()
    return {"shipment_number": shipment_number, "status": "paid"}


@router.get("/ship/receipt/{shipment_number}", response_class=HTMLResponse)
def receipt(shipment_number: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM shipments WHERE shipment_number = ?", (shipment_number,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Shipment not found")

    tier = SPEED_TIERS.get(row["speed_tier"], {"label": row["speed_tier"]})
    date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(row["created_at"]))

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Receipt — {row['shipment_number']}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width:480px; margin:30px auto; padding:20px; color:#111; }}
  h1 {{ font-size:20px; border-bottom:2px solid #111; padding-bottom:10px; }}
  table {{ width:100%; border-collapse:collapse; margin-top:16px; }}
  td {{ padding:6px 0; border-bottom:1px solid #eee; }}
  td:first-child {{ color:#666; width:45%; }}
  .total {{ font-size:18px; font-weight:bold; margin-top:16px; }}
  .status {{ display:inline-block; padding:4px 10px; border-radius:6px; font-size:13px; }}
  .paid {{ background:#d4f4dd; color:#1a7a37; }}
  .pending {{ background:#fde8d4; color:#a35b00; }}
  button {{ margin-top:20px; padding:10px 16px; border:none; border-radius:6px; background:#e2593a; color:#fff; font-size:15px; }}
</style>
</head>
<body>
  <h1>Uganda National Grid — Shipping Receipt</h1>
  <p>Receipt #: <strong>{row['shipment_number']}</strong><br>Date: {date_str}</p>
  <span class="status {'paid' if row['status'] == 'paid' else 'pending'}">
    {'PAID' if row['status'] == 'paid' else 'PENDING PAYMENT'}
  </span>
  <table>
    <tr><td>Pickup</td><td>{row['pickup']}</td></tr>
    <tr><td>Delivery</td><td>{row['delivery']}</td></tr>
    <tr><td>Weight</td><td>{row['weight_kg']} kg</td></tr>
    <tr><td>Distance</td><td>{row['distance_km']} km</td></tr>
    <tr><td>Speed</td><td>{tier.get('label', row['speed_tier'])}</td></tr>
    <tr><td>Sender</td><td>{row['sender_name'] or '—'} {row['sender_phone'] or ''}</td></tr>
    <tr><td>Recipient</td><td>{row['recipient_name'] or '—'} {row['recipient_phone'] or ''}</td></tr>
  </table>
  <div class="total">Total: UGX {row['rate_ugx']:,.0f}</div>
  <button onclick="window.print()">Print Receipt</button>
</body>
</html>
"""


@router.get("/ship/list")
def list_shipments(
    status: str = Query(default=""),
    x_admin_passcode: str = Header(default=""),
):
    check_admin(x_admin_passcode)
    conn = get_conn()
    query = "SELECT * FROM shipments"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}
