"""
Shipping rate calculation for UGAMAP shipments.
Distance component uses real road km via Valhalla (the same routing
engine your nav app already calls). Weight component is a flat
per-kg charge. Speed tiers apply a multiplier.

resolve_coordinates() reads entebbe_database.json directly, using the
same case-insensitive substring match on grid_id/address as main.py's
/search endpoint. No PUBLIC_BASE_URL or self-HTTP-call needed.

INTERNATIONAL SHIPPING: there is no live carrier API wired in, so
international pricing below is a flat, manually-set table by
destination zone (base fee + per-kg rate) rather than a real-time
quote from FedEx/DHL/UPS/etc. Edit INTERNATIONAL_ZONES with your own
real numbers before relying on this for actual pricing — the values
here are placeholders.
"""
import json
from pathlib import Path
from typing import Optional, Tuple

import requests

VALHALLA_URL = "https://valhalla1.openstreetmap.de/route"
CURRENCY = "UGX"

BASE_FEE = 3000     # UGX flat handling fee
PER_KM = 150        # UGX per road km
PER_KG = 500        # UGX per kg

SPEED_TIERS = {
    "seven_day": {"label": "Standard (7 days)", "multiplier": 1.0, "eta_days": 7},
    "three_day": {"label": "3-Day",             "multiplier": 1.3, "eta_days": 3},
    "two_day":   {"label": "2-Day",             "multiplier": 1.6, "eta_days": 2},
    "one_day":   {"label": "1-Day",             "multiplier": 2.0, "eta_days": 1},
    "overnight": {"label": "Overnight",         "multiplier": 2.6, "eta_days": 1},
    "express":   {"label": "Express (same day)", "multiplier": 3.5, "eta_days": 0},
}

# ---------------------------------------------------------------------
# International zones — PLACEHOLDER rates. These are not pulled from
# any carrier; set your own base_fee / per_kg numbers before using
# this for real customer-facing pricing.
# ---------------------------------------------------------------------
INTERNATIONAL_ZONES = {
    "east_africa": {
        "label": "East Africa (Kenya, Tanzania, Rwanda, S. Sudan, Burundi, DRC)",
        "base_fee": 15000, "per_kg": 8000, "eta_days": "3-5",
    },
    "rest_of_africa": {
        "label": "Rest of Africa",
        "base_fee": 20000, "per_kg": 12000, "eta_days": "5-10",
    },
    "middle_east": {
        "label": "Middle East",
        "base_fee": 25000, "per_kg": 18000, "eta_days": "5-9",
    },
    "europe": {
        "label": "Europe",
        "base_fee": 30000, "per_kg": 25000, "eta_days": "5-10",
    },
    "asia": {
        "label": "Asia",
        "base_fee": 30000, "per_kg": 22000, "eta_days": "7-14",
    },
    "north_america": {
        "label": "North America (USA, Canada)",
        "base_fee": 35000, "per_kg": 30000, "eta_days": "7-14",
    },
    "rest_of_world": {
        "label": "Rest of World",
        "base_fee": 40000, "per_kg": 35000, "eta_days": "10-20",
    },
}

_DB_PATH = Path(__file__).parent / "entebbe_database.json"
_cache = None


def _addresses():
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(_DB_PATH.read_text(encoding="utf-8"))
        except Exception:
            _cache = []
    return _cache


def resolve_coordinates(address_or_grid_id: str) -> Optional[Tuple[float, float]]:
    """Look up (lat, lon) for a grid ID or address by matching directly
    against the local database — same matching rule as main.py's
    /search endpoint (case-insensitive substring on grid_id or address)."""
    query = address_or_grid_id.strip().lower()
    if not query:
        return None
    for item in _addresses():
        grid_id = str(item.get("grid_id", "")).strip().lower()
        address = str(item.get("address", "")).strip().lower()
        if query in grid_id or query in address:
            try:
                return float(item["latitude"]), float(item["longitude"])
            except (KeyError, ValueError, TypeError):
                continue
    return None


def road_distance_km(origin: Tuple[float, float], destination: Tuple[float, float]) -> float:
    payload = {
        "locations": [
            {"lat": origin[0], "lon": origin[1]},
            {"lat": destination[0], "lon": destination[1]},
        ],
        "costing": "auto",
        "units": "kilometers",
    }
    resp = requests.post(VALHALLA_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()["trip"]["summary"]["length"]


def quote_all_tiers(distance_km: float, weight_kg: float) -> list:
    return [quote(distance_km, weight_kg, speed) for speed in SPEED_TIERS]


def quote(distance_km: float, weight_kg: float, speed: str) -> dict:
    if speed not in SPEED_TIERS:
        raise ValueError(f"speed must be one of {list(SPEED_TIERS)}")
    tier = SPEED_TIERS[speed]
    subtotal = BASE_FEE + PER_KM * distance_km + PER_KG * weight_kg
    total = round(subtotal * tier["multiplier"])
    return {
        "distance_km": round(distance_km, 1),
        "weight_kg": weight_kg,
        "speed": speed,
        "speed_label": tier["label"],
        "eta_days": tier["eta_days"],
        "base_fee": BASE_FEE,
        "distance_cost": round(PER_KM * distance_km),
        "weight_cost": round(PER_KG * weight_kg),
        "multiplier": tier["multiplier"],
        "total": total,
        "currency": CURRENCY,
    }


def quote_international(zone: str, weight_kg: float) -> dict:
    if zone not in INTERNATIONAL_ZONES:
        raise ValueError(f"zone must be one of {list(INTERNATIONAL_ZONES)}")
    z = INTERNATIONAL_ZONES[zone]
    weight_cost = round(z["per_kg"] * weight_kg)
    total = round(z["base_fee"] + weight_cost)
    return {
        "zone": zone,
        "zone_label": z["label"],
        "weight_kg": weight_kg,
        "eta_days": z["eta_days"],
        "base_fee": z["base_fee"],
        "weight_cost": weight_cost,
        "total": total,
        "currency": CURRENCY,
    }
