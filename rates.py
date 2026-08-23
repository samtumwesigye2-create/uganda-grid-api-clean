"""
Shipping rate calculation for UGAMAP shipments.
Distance component uses real road km via Valhalla (the same routing
engine your nav app already calls — no new API key needed). Weight
component is a flat per-kg charge. Speed tiers apply a multiplier.

⚠️ resolve_coordinates() guesses at your entebbe_database.json shape.
If grid-ID lookups return None when they shouldn't, tell me the actual
structure of that file (a sample entry) and I'll fix the field names.
"""
import json
from pathlib import Path
from typing import Optional, Tuple

import requests

VALHALLA_URL = "https://valhalla1.openstreetmap.de/route"
GRID_DB_PATH = Path(__file__).parent / "entebbe_database.json"
CURRENCY = "UGX"

# total = (BASE_FEE + PER_KM * distance_km + PER_KG * weight_kg) * tier_multiplier
# Tune these three to your real costs.
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


def _load_grid_db():
    if not GRID_DB_PATH.exists():
        return {}
    return json.loads(GRID_DB_PATH.read_text())


def resolve_coordinates(address_or_grid_id: str) -> Optional[Tuple[float, float]]:
    """Look up (lat, lon) for a grid ID like 'UG-ENT-000001'."""
    db = _load_grid_db()
    if isinstance(db, dict):
        entry = db.get(address_or_grid_id)
        if entry and "lat" in entry and "lon" in entry:
            return float(entry["lat"]), float(entry["lon"])
    if isinstance(db, list):
        for row in db:
            if row.get("grid_id") == address_or_grid_id or row.get("id") == address_or_grid_id:
                if "lat" in row and "lon" in row:
                    return float(row["lat"]), float(row["lon"])
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
