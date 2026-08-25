"""
shipments.py — Ship & Mail: rate calculation, shipment creation, receipts.

Covers both domestic (Uganda grid-to-grid) and international shipping.
"""

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

INTL_TIERS = {
    "intl_standard": {"label": "International Standard", "multiplier": 1.0, "eta_days": 14},
    "intl_express": {"label": "International Express", "multiplier": 1.8, "eta_days": 5},
}

INTL_ZONE_MAP = {
    "kenya": 1, "tanzania": 1, "rwanda": 1, "burundi": 1, "south sudan": 1,
    "democratic republic of congo": 1, "dr congo": 1,
    "nigeria": 2, "ghana": 2, "south africa": 2, "egypt": 2, "ethiopia": 2,
    "morocco": 2, "senegal": 2, "tunisia": 2,
    "united kingdom": 3, "uk": 3, "germany": 3, "france": 3, "netherlands": 3,
    "italy": 3, "spain": 3, "sweden": 3, "belgium": 3, "uae": 3,
    "united arab emirates": 3, "india": 3, "china": 3,
    "united states": 4, "usa": 4, "us": 4, "canada": 4, "australia": 4,
    "brazil": 4, "japan": 4, "south korea": 4,
}
DEFAULT_ZONE = 4

ZONE_RATES = {
    1: {"base": 15000, "per_kg": 6000},
    2: {"base": 25000, "per_kg": 9000},
    3: {"base": 40000, "per_kg": 14000},
    4: {"base": 55000, "per_kg": 20000},
}

DELIVERY_STATUSES = [
    "created", "picked_up", "in_transit", "out_for_delivery",
    "delivered", "failed_delivery", "returned", "cancelled",
]


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
            shipment_type TEXT DEFAULT 'domestic',
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
    conn.execute("INSERT OR IGNORE INTO shipment_counter (id, next_number) VALUES (1, 1)")

    # --- Status history: every status a shipment has passed through, in order.
    # Powers the customer-facing tracking box (click status -> timeline).
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS shipment_status_history (
            id TEXT PRIMARY KEY,
            shipment_number TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT,
            created_at REAL NOT NULL
        )
        """
    )

    try:
        conn.execute("ALTER TABLE shipments ADD COLUMN shipment_type TEXT DEFAULT 'domestic'")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE shipments ADD COLUMN delivery_status TEXT DEFAULT 'created'")
    except sqlite3.OperationalError:
        pass

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


def log_status(shipment_number: str, status: str, note: str = ""):
    """Append one entry to the shipment's status history timeline."""
    conn = get_conn()
    conn.execute(
        "INSERT INTO shipment_status_history (id, shipment_number, status, note, created_at) VALUES (?,?,?,?,?)",
        (str(uuid.uuid4()), shipment_number, status, note, time.time()),
    )
    conn.commit()
    conn.close()


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


def get_zone(country: str) -> int:
    return INTL_ZONE_MAP.get(country.strip().lower(), DEFAULT_ZONE)


def calculate_international_rate(zone: int, weight_kg: float, speed_tier: str):
    tier = INTL_TIERS.get(speed_tier)
    if not tier:
        raise HTTPException(status_code=400, detail="Invalid speed tier")
    zone_rate = ZONE_RATES[zone]
    base = zone_rate["base"] + (weight_kg * zone_rate["per_kg"])
    rate = base * tier["multiplier"]
    return round(rate, -1)


def all_tier_labels():
    return {**SPEED_TIERS, **INTL_TIERS}


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
                "speed_tier": key, "label": tier["label"],
                "eta_days": tier["eta_days"], "rate_ugx": rate,
            })

        return {
            "pickup": pickup, "delivery": delivery, "weight_kg": weight_kg,
            "distance_km": distance_km, "quotes": quotes,
        }

    @router.get("/ship/international/rates")
    def get_international_rates(
        country: str = Query(...),
        weight_kg: float = Query(..., gt=0),
    ):
        zone = get_zone(country)
        quotes = []
        for key, tier in INTL_TIERS.items():
            rate = calculate_international_rate(zone, weight_kg, key)
            quotes.append({
                "speed_tier": key, "label": tier["label"],
                "eta_days": tier["eta_days"], "rate_ugx": rate,
            })
        return {"country": country, "zone": zone, "weight_kg": weight_kg, "quotes": quotes}

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
             recipient_name, recipient_phone, shipment_type, delivery_status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (shipment_id, shipment_number, pickup, delivery, weight_kg,
             distance_km, speed_tier, rate, "pending_payment",
             sender_name, sender_phone, recipient_name, recipient_phone,
             "domestic", "created", time.time()),
        )
        conn.commit()
        conn.close()

        log_status(shipment_number, "created")

        return {
            "id": shipment_id, "shipment_number": shipment_number, "rate_ugx": rate,
            "distance_km": distance_km, "status": "pending_payment",
            "delivery_status": "created", "receipt_url": f"/ship/receipt/{shipment_number}",
        }

    @router.post("/ship/international/create")
    def create_international_shipment(
        country: str = Form(...),
        recipient_address: str = Form(...),
        weight_kg: float = Form(..., gt=0),
        speed_tier: str = Form(...),
        sender_name: str = Form(""),
        sender_phone: str = Form(""),
        recipient_name: str = Form(""),
        recipient_phone: str = Form(""),
    ):
        zone = get_zone(country)
        rate = calculate_international_rate(zone, weight_kg, speed_tier)

        shipment_id = str(uuid.uuid4())
        shipment_number = next_shipment_number()

        conn = get_conn()
        conn.execute(
            """
            INSERT INTO shipments
            (id, shipment_number, pickup, delivery, weight_kg, distance_km,
             speed_tier, rate_ugx, status, sender_name, sender_phone,
             recipient_name, recipient_phone, shipment_type, delivery_status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (shipment_id, shipment_number, "Uganda (origin)",
             f"{country} — {recipient_address}", weight_kg, 0,
             speed_tier, rate, "pending_payment",
             sender_name, sender_phone, recipient_name, recipient_phone,
             "international", "created", time.time()),
        )
        conn.commit()
        conn.close()

        log_status(shipment_number, "created")

        return {
            "id": shipment_id, "shipment_number": shipment_number, "rate_ugx": rate,
            "status": "pending_payment", "delivery_status": "created",
            "receipt_url": f"/ship/receipt/{shipment_number}",
        }

    @router.post("/ship/{shipment_number}/pay")
    def mark_paid(shipment_number: str):
        conn = get_conn()
        row = conn.execute("SELECT * FROM shipments WHERE shipment_number = ?", (shipment_number,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Shipment not found")
        conn.execute("UPDATE shipments SET status = 'paid' WHERE shipment_number = ?", (shipment_number,))
        conn.commit()
        conn.close()
        return {"shipment_number": shipment_number, "status": "paid"}

    @router.post("/ship/{shipment_number}/status")
    def update_delivery_status(
        shipment_number: str,
        delivery_status: str = Form(...),
        note: str = Form(""),
        x_admin_passcode: str = Header(default=""),
    ):
        check_admin(x_admin_passcode)
        if delivery_status not in DELIVERY_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        conn = get_conn()
        row = conn.execute("SELECT * FROM shipments WHERE shipment_number = ?", (shipment_number,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Shipment not found")
        conn.execute(
            "UPDATE shipments SET delivery_status = ? WHERE shipment_number = ?",
            (delivery_status, shipment_number),
        )
        conn.commit()
        conn.close()

        log_status(shipment_number, delivery_status, note)

        return {"shipment_number": shipment_number, "delivery_status": delivery_status}

    @router.get("/ship/{shipment_number}/track")
    def track_shipment(shipment_number: str):
        """Public tracking endpoint — no admin passcode required.
        Returns current status + full history timeline for the customer-facing
        tracking box. Deliberately omits rate, phone numbers, and other
        admin-only fields."""
        conn = get_conn()
        row = conn.execute(
            """
            SELECT shipment_number, pickup, delivery, delivery_status,
                   shipment_type, created_at
            FROM shipments WHERE shipment_number = ?
            """,
            (shipment_number,),
        ).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Shipment not found")

        history_rows = conn.execute(
            """
            SELECT status, note, created_at
            FROM shipment_status_history
            WHERE shipment_number = ?
            ORDER BY created_at ASC
            """,
            (shipment_number,),
        ).fetchall()
        conn.close()

        return {
            "shipment_number": row["shipment_number"],
            "pickup": row["pickup"],
            "delivery": row["delivery"],
            "current_status": row["delivery_status"],
            "shipment_type": row["shipment_type"],
            "history": [
                {
                    "status": h["status"],
                    "note": h["note"],
                    "at": time.strftime("%Y-%m-%d %H:%M", time.localtime(h["created_at"])),
                }
                for h in history_rows
            ],
        }

    @router.put("/ship/{shipment_number}")
    def update_shipment(
        shipment_number: str,
        pickup: str = Form(None),
        delivery: str = Form(None),
        weight_kg: float = Form(None),
        speed_tier: str = Form(None),
        rate_ugx: float = Form(None),
        sender_name: str = Form(None),
        sender_phone: str = Form(None),
        recipient_name: str = Form(None),
        recipient_phone: str = Form(None),
        x_admin_passcode: str = Header(default=""),
    ):
        """Admin override: edit any field of an existing shipment directly.
        rate_ugx can be set explicitly rather than recalculated, since admin
        may be correcting a route/weight change manually."""
        check_admin(x_admin_passcode)
        conn = get_conn()
        row = conn.execute("SELECT * FROM shipments WHERE shipment_number = ?", (shipment_number,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Shipment not found")

        new_pickup = pickup if pickup is not None else row["pickup"]
        new_delivery = delivery if delivery is not None else row["delivery"]
        new_weight = weight_kg if weight_kg is not None else row["weight_kg"]
        new_speed_tier = speed_tier if speed_tier is not None else row["speed_tier"]
        new_rate = rate_ugx if rate_ugx is not None else row["rate_ugx"]
        new_sender_name = sender_name if sender_name is not None else row["sender_name"]
        new_sender_phone = sender_phone if sender_phone is not None else row["sender_phone"]
        new_recipient_name = recipient_name if recipient_name is not None else row["recipient_name"]
        new_recipient_phone = recipient_phone if recipient_phone is not None else row["recipient_phone"]

        conn.execute(
            """
            UPDATE shipments SET pickup=?, delivery=?, weight_kg=?, speed_tier=?,
            rate_ugx=?, sender_name=?, sender_phone=?, recipient_name=?, recipient_phone=?
            WHERE shipment_number=?
            """,
            (new_pickup, new_delivery, new_weight, new_speed_tier, new_rate,
             new_sender_name, new_sender_phone, new_recipient_name, new_recipient_phone,
             shipment_number),
        )
        conn.commit()
        conn.close()
        return {
            "shipment_number": shipment_number, "pickup": new_pickup, "delivery": new_delivery,
            "weight_kg": new_weight, "speed_tier": new_speed_tier, "rate_ugx": new_rate,
        }

    @router.delete("/ship/{shipment_number}")
    def delete_shipment(shipment_number: str, x_admin_passcode: str = Header(default="")):
        check_admin(x_admin_passcode)
        conn = get_conn()
        result = conn.execute("DELETE FROM shipments WHERE shipment_number = ?", (shipment_number,))
        conn.commit()
        conn.close()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Shipment not found")
        return {"shipment_number": shipment_number, "deleted": True}

    @router.get("/ship/receipt/{shipment_number}", response_class=HTMLResponse)
    def receipt(shipment_number: str):
        conn = get_conn()
        row = conn.execute("SELECT * FROM shipments WHERE shipment_number = ?", (shipment_number,)).fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Shipment not found")

        tier = all_tier_labels().get(row["speed_tier"], {"label": row["speed_tier"]})
        date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(row["created_at"]))
        is_intl = row["shipment_type"] == "international"
        delivery_status = row["delivery_status"] or "created"

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
                .status {{ display:inline-block; padding:4px 10px; border-radius:6px; font-size:13px; margin-right:6px; }}
                .paid {{ background:#d4f4dd; color:#1a7a37; }}
                .pending {{ background:#fde8d4; color:#a35b00; }}
                .delivery {{ background:#dbe6ff; color:#2a3a7a; }}
                button {{ margin-top:20px; padding:10px 16px; border:none; border-radius:6px; background:#e2593a; color:#fff; font-size:15px; margin-right:8px; cursor:pointer; }}
                a.trackBtn {{ display:inline-block; margin-top:20px; padding:10px 16px; border-radius:6px; background:#3b5bfd; color:#fff; font-size:15px; text-decoration:none; }}
            </style>
        </head>
        <body>
            <h1>Uganda National Grid — Shipping Receipt</h1>
            <p>Receipt #: <strong>{row['shipment_number']}</strong><br>Date: {date_str}</p>
            <span class="status {'paid' if row['status'] == 'paid' else 'pending'}">
                {'PAID' if row['status'] == 'paid' else 'PENDING PAYMENT'}
            </span>
            <span class="status delivery">{delivery_status.replace('_', ' ').upper()}</span>
            <table>
                <tr><td>Type</td><td>{'International' if is_intl else 'Domestic'}</td></tr>
                <tr><td>Pickup</td><td>{row['pickup']}</td></tr>
                <tr><td>Delivery</td><td>{row['delivery']}</td></tr>
                <tr><td>Weight</td><td>{row['weight_kg']} kg</td></tr>
                {'' if is_intl else f"<tr><td>Distance</td><td>{row['distance_km']} km</td></tr>"}
                <tr><td>Speed</td><td>{tier.get('label', row['speed_tier'])}</td></tr>
                <tr><td>Sender</td><td>{row['sender_name'] or '—'} {row['sender_phone'] or ''}</td></tr>
                <tr><td>Recipient</td><td>{row['recipient_name'] or '—'} {row['recipient_phone'] or ''}</td></tr>
            </table>
            <div class="total">Total: UGX {row['rate_ugx']:,.0f}</div>
            <div>
                <button onclick="window.print()">Print Receipt</button>
                <a class="trackBtn" href="/track?ship={row['shipment_number']}">Track This Shipment</a>
            </div>
        </body>
        </html>
        """

    @router.get("/ship/list")
    def list_shipments(
        status: str = Query(default=""),
        delivery_status: str = Query(default=""),
        x_admin_passcode: str = Header(default=""),
    ):
        check_admin(x_admin_passcode)
        conn = get_conn()
        query = "SELECT * FROM shipments WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if delivery_status:
            query += " AND delivery_status = ?"
            params.append(delivery_status)
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return {"count": len(rows), "results": [dict(r) for r in rows]}
